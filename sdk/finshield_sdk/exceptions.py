"""FinShield SDK Exceptions."""


class FinShieldError(Exception):
    """Base exception for FinShield SDK errors."""
    
    def __init__(self, message: str, status_code: int | None = None, response_body: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body


class AuthenticationError(FinShieldError):
    """Raised when authentication fails (401)."""
    pass


class RateLimitError(FinShieldError):
    """Raised when rate limit is exceeded (429)."""
    
    def __init__(self, message: str, retry_after: int | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class ValidationError(FinShieldError):
    """Raised when request validation fails (422)."""
    pass


class ServerError(FinShieldError):
    """Raised when server returns 5xx error."""
    pass


class NotFoundError(FinShieldError):
    """Raised when resource is not found (404)."""
    pass
