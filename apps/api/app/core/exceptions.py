from __future__ import annotations


class SDMASError(Exception):
    """Base exception for all SDMAS application errors."""


class ConfigurationError(SDMASError):
    """Raised when application configuration is invalid or missing."""


class NotFoundError(SDMASError):
    """Raised when a requested resource does not exist."""


class ConflictError(SDMASError):
    """Raised when a resource conflicts with existing state."""


class ValidationError(SDMASError):
    """Raised when input validation fails."""


class AuthenticationError(SDMASError):
    """Raised when authentication fails (invalid/missing credentials)."""


class AuthorizationError(SDMASError):
    """Raised when the user lacks permission for the requested operation."""


class DatabaseError(SDMASError):
    """Raised when a database operation fails."""