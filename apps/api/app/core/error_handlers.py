from __future__ import annotations

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    PaymentRequiredError,
    ValidationError,
)

# Document upload validation failures (oversized, disallowed extension,
# disallowed MIME content) must surface as a clean 400 — never as an
# unhandled 500 that leaks stack traces.
from app.domains.documents.validation import FileValidationError  # noqa: E402


async def not_found_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": str(exc)},
    )


async def conflict_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": str(exc)},
    )


async def validation_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": str(exc)},
    )


async def auth_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": str(exc)},
        headers={"WWW-Authenticate": "Bearer"},
    )


async def forbidden_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={"detail": str(exc)},
    )


async def payment_required_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={"detail": str(exc)},
    )


async def file_validation_handler(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )