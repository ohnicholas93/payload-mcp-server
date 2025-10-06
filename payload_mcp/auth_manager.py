"""
Authentication manager for handling JWT tokens and credential renewal.
"""

import asyncio
import json
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

import httpx

from .config import PayloadConfig
from .exceptions import AuthenticationError

logger = logging.getLogger(__name__)


class AuthManager:
    """Manages JWT authentication with automatic renewal."""
    
    def __init__(self, config: PayloadConfig, collection_slug: str = "users"):
        self.config = config
        self.collection_slug = collection_slug
        self.auth_token = config.auth_token
        self.token_expiry: Optional[datetime] = None
        self.credentials: Optional[Dict[str, str]] = None
        self.refresh_lock = asyncio.Lock()
        self.auth_callbacks: list[Callable[[str], None]] = []
        self.browser_auth_in_progress = False
        self.browser_auth_event = asyncio.Event()
        # Event loop where wait_for_browser_auth is awaiting; used for thread-safe signaling
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        
    def add_auth_callback(self, callback: Callable[[str], None]):
        """Add a callback to be called when authentication is renewed."""
        self.auth_callbacks.append(callback)
        
    def _notify_auth_renewed(self, new_token: str):
        """Notify all callbacks that authentication has been renewed."""
        for callback in self.auth_callbacks:
            try:
                callback(new_token)
            except Exception as e:
                logger.error(f"Error in auth callback: {e}")

        # Signal any waiter that browser auth completed successfully
        self._signal_browser_auth_completed()

    def _signal_browser_auth_completed(self):
        """
        Signal the browser authentication event in a thread-safe manner.
        This ensures that if the login occurs in a different thread/loop
        (e.g., inside AuthServer via asyncio.run), the waiting task in the
        original loop is correctly awakened.
        """
        def _set_event():
            if not self.browser_auth_event.is_set():
                self.browser_auth_event.set()
            self.browser_auth_in_progress = False

        try:
            # If we captured a loop where wait_for_browser_auth is awaiting, use it
            if self._event_loop and self._event_loop.is_running():
                # Ensure thread-safe call into the correct loop
                self._event_loop.call_soon_threadsafe(_set_event)
            else:
                # Fallback: set directly (safe when called from same loop)
                _set_event()
        except Exception as e:
            logger.error(f"Failed to signal browser auth completion: {e}")
            # Best effort fallback
            try:
                _set_event()
            except Exception:
                pass
    
    def set_credentials(self, email: str, password: str):
        """Store user credentials for automatic renewal."""
        self.credentials = {
            "email": email,
            "password": password
        }
        logger.info(f"Credentials stored for {email}")
    
    def clear_credentials(self):
        """Clear stored credentials."""
        self.credentials = None
        logger.info("Stored credentials cleared")
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers with current JWT token."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.auth_token:
            headers["Authorization"] = f"JWT {self.auth_token}"
            
        return headers
    
    async def login(self, email: str, password: str) -> Dict[str, Any]:
        """
        Login with email and password to get a new JWT token.
        
        Args:
            email: User email
            password: User password
            
        Returns:
            Login response with token and user info
            
        Raises:
            AuthenticationError: If login fails
        """
        login_url = f"{self.config.base_url.rstrip('/')}/{self.collection_slug}/login"
        
        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout,
                verify=self.config.verify_ssl
            ) as client:
                response = await client.post(
                    login_url,
                    json={"email": email, "password": password}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    token = data.get("token")
                    user = data.get("user", {})
                    exp = data.get("exp")
                    
                    if not token:
                        raise AuthenticationError("No token received from login response")
                    
                    # Update token and expiry
                    self.auth_token = token
                    self.credentials = {"email": email, "password": password}
                    
                    # Convert exp timestamp to datetime if available
                    if exp:
                        try:
                            self.token_expiry = datetime.fromtimestamp(exp)
                        except (ValueError, TypeError):
                            # If we can't parse the expiry, set a default of 1 hour
                            self.token_expiry = datetime.now() + timedelta(hours=1)
                    else:
                        # Default expiry of 1 hour if not provided
                        self.token_expiry = datetime.now() + timedelta(hours=1)
                    
                    logger.info(f"Successfully logged in as {email}")
                    self._notify_auth_renewed(token)
                    
                    return {
                        "token": token,
                        "user": user,
                        "expires_at": self.token_expiry.isoformat() if self.token_expiry else None
                    }
                else:
                    error_data = {}
                    try:
                        error_data = response.json()
                    except json.JSONDecodeError:
                        pass
                    
                    message = error_data.get("message", f"Login failed with status {response.status_code}")
                    raise AuthenticationError(f"Login failed: {message}")
                    
        except httpx.ConnectError as e:
            raise AuthenticationError(f"Failed to connect to authentication server: {str(e)}")
        except httpx.TimeoutException as e:
            raise AuthenticationError(f"Authentication request timeout: {str(e)}")
        except httpx.HTTPError as e:
            raise AuthenticationError(f"HTTP error during authentication: {str(e)}")
    
    async def _login_with_stored_credentials(self) -> bool:
        """Login using stored credentials as a fallback."""
        if not self.credentials:
            return False
            
        try:
            email = self.credentials["email"]
            password = self.credentials["password"]
            await self.login(email, password)
            return True
        except Exception as e:
            logger.error(f"Login with stored credentials failed: {str(e)}")
            # Clear credentials if they're invalid to prevent repeated attempts
            self.clear_credentials()
            return False
    
    def is_token_expired(self) -> bool:
        """Check if the current token is expired or close to expiring."""
        if not self.token_expiry:
            # If we don't have expiry info, assume token is valid
            return False
            
        # Add 5-minute buffer before expiry
        buffer_time = timedelta(minutes=5)
        return datetime.now() >= (self.token_expiry - buffer_time)
    
    async def ensure_valid_token(self) -> bool:
        """
        Ensure we have a valid token.
        
        Returns:
            True if we have a valid token, False otherwise
        """
        return bool(self.auth_token)
    
    def get_auth_status(self) -> Dict[str, Any]:
        """Get current authentication status."""
        return {
            "has_token": bool(self.auth_token),
            "has_credentials": bool(self.credentials),
            "token_expiry": self.token_expiry.isoformat() if self.token_expiry else None,
            "is_expired": self.is_token_expired() if self.token_expiry else False,
            "user_email": self.credentials.get("email") if self.credentials else None,
            "collection_slug": self.collection_slug
        }
    
    def decode_jwt_payload(self) -> Optional[Dict[str, Any]]:
        """
        Decode JWT payload without verification (for expiry info only).
        
        Returns:
            JWT payload dictionary or None if decoding fails
        """
        if not self.auth_token:
            return None
            
        try:
            # Simple base64 decode for JWT payload (middle part)
            # Note: This is not for security verification, just for extracting expiry
            import base64
            
            # Remove padding if needed
            payload_b64 = self.auth_token.split('.')[1]
            # Add padding if needed
            payload_b64 += '=' * (-len(payload_b64) % 4)
            
            payload_bytes = base64.b64decode(payload_b64)
            payload = json.loads(payload_bytes.decode('utf-8'))
            
            return payload
        except Exception as e:
            logger.debug(f"Failed to decode JWT payload: {e}")
            return None
    
    async def start_browser_auth(self) -> bool:
        """
        Start browser authentication process.
        
        Returns:
            True if browser auth was started successfully, False otherwise
        """
        if self.browser_auth_in_progress:
            logger.warning("Browser authentication already in progress")
            return False
        
        try:
            self.browser_auth_in_progress = True
            self.browser_auth_event.clear()
            
            # Import here to avoid circular imports
            from .auth_server import AuthServer
            
            # Create and start auth server
            auth_server = AuthServer()
            
            # Set up callback to handle successful authentication
            def auth_callback(result, *args):
                logger.info("Browser authentication successful")
                # Ensure the waiting loop is signaled in a thread-safe way
                self._signal_browser_auth_completed()
            
            auth_server.set_auth_manager(self, auth_callback)
            
            if not auth_server.start():
                logger.error("Failed to start authentication server")
                self.browser_auth_in_progress = False
                return False
            
            # Open browser
            if not auth_server.open_browser():
                logger.error("Failed to open browser for authentication")
                auth_server.stop()
                self.browser_auth_in_progress = False
                return False
            
            logger.info("Browser authentication started")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start browser authentication: {e}")
            self.browser_auth_in_progress = False
            return False
    
    async def wait_for_browser_auth(self, timeout: int = 300) -> bool:
        """
        Wait for browser authentication to complete.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if authentication was successful, False if timed out
        """
        # Record the current event loop to enable thread-safe signaling from other threads
        try:
            self._event_loop = asyncio.get_running_loop()
        except RuntimeError:
            # No running loop; leave as None
            self._event_loop = None

        # If the event is already set (e.g., user previously failed then retried successfully),
        # return True immediately to avoid missing the signal due to race conditions.
        if self.browser_auth_event.is_set():
            return True

        # If there is no active browser auth flow and no event set, nothing to wait for.
        if not self.browser_auth_in_progress:
            return False
        
        try:
            await asyncio.wait_for(self.browser_auth_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            logger.warning("Browser authentication timed out")
            self.browser_auth_in_progress = False
            return False
        except Exception as e:
            logger.error(f"Error waiting for browser authentication: {e}")
            self.browser_auth_in_progress = False
            return False