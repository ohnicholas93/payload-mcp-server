"""
Simple HTTP server for browser-based authentication.
"""

import asyncio
import json
import logging
import webbrowser
from typing import Optional, Callable, Any
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
import urllib.parse

logger = logging.getLogger(__name__)


class AuthHandler(BaseHTTPRequestHandler):
    """HTTP request handler for authentication."""
    
    # Class-level storage for the auth manager and callback
    auth_manager = None
    auth_callback = None
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/':
            self._serve_login_page()
        else:
            self._send_404()
    
    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/login':
            self._handle_login()
        else:
            self._send_404()
    
    def _serve_login_page(self):
        """Serve the login form HTML page."""
        html = """
<!DOCTYPE html>
<html>
<head>
    <title>Payload CMS Authentication</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 400px;
            margin: 50px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="email"], input[type="password"] {
            width: 100%;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            width: 100%;
            padding: 12px;
            background-color: #007bff;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #0056b3;
        }
        .error {
            color: #dc3545;
            margin-top: 10px;
            padding: 10px;
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            border-radius: 4px;
            display: none;
        }
        .success {
            color: #155724;
            margin-top: 10px;
            padding: 10px;
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            border-radius: 4px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Payload CMS Login</h1>
        <p>Please enter your credentials to authenticate with Payload CMS.</p>
        
        <form id="loginForm">
            <div class="form-group">
                <label for="email">Email:</label>
                <input type="email" id="email" name="email" required>
            </div>
            
            <div class="form-group">
                <label for="password">Password:</label>
                <input type="password" id="password" name="password" required>
            </div>
            
            <div class="form-group">
                <label for="collection">Collection:</label>
                <input type="text" id="collection" name="collection" value="users">
            </div>
            
            <button type="submit">Login</button>
        </form>
        
        <div id="error" class="error"></div>
        <div id="success" class="success"></div>
    </div>

    <script>
        document.getElementById('loginForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const collection = document.getElementById('collection').value;
            
            const errorDiv = document.getElementById('error');
            const successDiv = document.getElementById('success');
            
            errorDiv.style.display = 'none';
            successDiv.style.display = 'none';
            
            try {
                const response = await fetch('/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: new URLSearchParams({
                        email: email,
                        password: password,
                        collection: collection
                    })
                });
                
                const result = await response.json();
                
                if (result.success) {
                    successDiv.textContent = 'Authentication successful! This window will close automatically.';
                    successDiv.style.display = 'block';
                    
                    // Close the window after a short delay
                    setTimeout(() => {
                        window.close();
                    }, 1500);
                } else {
                    errorDiv.textContent = result.message || 'Authentication failed';
                    errorDiv.style.display = 'block';
                }
            } catch (error) {
                errorDiv.textContent = 'An error occurred during authentication';
                errorDiv.style.display = 'block';
            }
        });
    </script>
</body>
</html>
        """
        
        self._send_response(200, html, 'text/html')
    
    def _handle_login(self):
        """Handle login form submission."""
        try:
            # Read form data
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            form_data = urllib.parse.parse_qs(post_data)
            
            email = form_data.get('email', [''])[0]
            password = form_data.get('password', [''])[0]
            collection = form_data.get('collection', ['users'])[0]
            
            if not email or not password:
                self._send_json_response({
                    'success': False,
                    'message': 'Email and password are required'
                })
                return
            
            # Use the auth manager to login
            if self.auth_manager:
                # Update collection if different
                if self.auth_manager.collection_slug != collection:
                    self.auth_manager.collection_slug = collection
                
                # Perform login
                result = asyncio.run(self.auth_manager.login(email, password))
                
                # Call the callback if provided
                if self.auth_callback:
                    self.auth_callback(result)
                
                self._send_json_response({
                    'success': True,
                    'message': 'Authentication successful'
                })
            else:
                self._send_json_response({
                    'success': False,
                    'message': 'Authentication manager not available'
                })
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            self._send_json_response({
                'success': False,
                'message': f'Login error: {str(e)}'
            })
    
    def _send_response(self, status_code: int, content: str, content_type: str = 'text/html'):
        """Send HTTP response."""
        self.send_response(status_code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content.encode())
    
    def _send_json_response(self, data: dict):
        """Send JSON response."""
        json_content = json.dumps(data)
        self._send_response(200, json_content, 'application/json')
    
    def _send_404(self):
        """Send 404 response."""
        self._send_response(404, 'Not Found')
    
    def log_message(self, format: str, *args: Any):
        """Override to suppress logging."""
        pass


class AuthServer:
    """Simple HTTP server for browser-based authentication."""
    
    def __init__(self, port: int = 8765):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self.server_thread: Optional[Thread] = None
        self.auth_manager = None
        self.auth_callback = None
    
    def set_auth_manager(self, auth_manager, auth_callback: Optional[Callable] = None):
        """Set the auth manager and callback for authentication."""
        self.auth_manager = auth_manager
        self.auth_callback = auth_callback
        
        # Set the class-level variables
        AuthHandler.auth_manager = auth_manager
        AuthHandler.auth_callback = auth_callback
    
    def start(self) -> bool:
        """Start the authentication server."""
        try:
            # Create HTTP server
            self.server = HTTPServer(('localhost', self.port), AuthHandler)
            
            # Start server in a separate thread
            self.server_thread = Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            
            logger.info(f"Auth server started on http://localhost:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start auth server: {e}")
            return False
    
    def stop(self):
        """Stop the authentication server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            logger.info("Auth server stopped")
    
    def open_browser(self) -> bool:
        """Open browser to the authentication page."""
        try:
            url = f"http://localhost:{self.port}"
            webbrowser.open(url)
            logger.info(f"Opened browser at {url}")
            return True
        except Exception as e:
            logger.error(f"Failed to open browser: {e}")
            return False
    
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.server is not None and self.server_thread is not None