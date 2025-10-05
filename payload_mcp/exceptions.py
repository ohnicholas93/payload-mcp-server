"""
Custom exceptions for Payload CMS MCP Server.
"""


class PayloadMCPError(Exception):
    """Base exception for Payload MCP server."""
    
    def __init__(self, message: str, details: dict = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigurationError(PayloadMCPError):
    """Raised when there's a configuration error."""
    pass


class AuthenticationError(PayloadMCPError):
    """Raised when JWT authentication fails."""
    pass


class APIError(PayloadMCPError):
    """Raised when API request fails."""
    
    def __init__(self, message: str, status_code: int = None, response_data: dict = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data or {}


class NotFoundError(APIError):
    """Raised when resource is not found."""
    pass


class ValidationError(PayloadMCPError):
    """Raised when data validation fails."""
    
    def __init__(self, message: str, field: str = None, value: any = None, response_data: dict = None):
        super().__init__(message)
        self.field = field
        self.value = value
        self.response_data = response_data or {}


class RateLimitError(APIError):
    """Raised when rate limit is exceeded."""
    pass


class ConnectionError(PayloadMCPError):
    """Raised when connection to Payload CMS fails."""
    pass