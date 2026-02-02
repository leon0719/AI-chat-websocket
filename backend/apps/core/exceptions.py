"""Custom exceptions for the application."""


class AppError(Exception):
    """Base exception for application errors."""

    def __init__(self, message: str, code: str = "APP_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class AuthenticationError(AppError):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code="AUTH_ERROR")


class AuthorizationError(AppError):
    """Authorization failed."""

    def __init__(self, message: str = "Access denied"):
        super().__init__(message, code="FORBIDDEN")


class NotFoundError(AppError):
    """Resource not found."""

    def __init__(self, message: str = "Resource not found"):
        super().__init__(message, code="NOT_FOUND")


class ValidationError(AppError):
    """Validation failed."""

    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, code="VALIDATION_ERROR")


class AIServiceError(AppError):
    """AI service error."""

    def __init__(self, message: str = "AI service error"):
        super().__init__(message, code="AI_ERROR")


class InvalidStateError(AppError):
    """Invalid application state."""

    def __init__(self, message: str = "Invalid application state"):
        super().__init__(message, code="INVALID_STATE")
