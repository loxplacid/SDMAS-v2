from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request, status

from app.core.security import RateLimiter, SecurityAuditLogger
from app.domains.audit.constants import CREATE, USER
from app.domains.audit.utils import get_request_metadata
from app.domains.auth.dependencies import (
    get_current_user,
    get_user_service,
)
from app.domains.auth.models import User
from app.domains.auth.schemas import (
    PasswordChange,
    SchoolMembershipResponse,
    SchoolSwitchRequest,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.domains.auth.membership import (
    SchoolMembershipRepository,
    SchoolMembershipService,
)
from app.domains.auth.service import UserService
from app.infrastructure.database import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: UserCreate,
    request: Request,
    service: UserService = Depends(get_user_service),
    session = Depends(get_session),
) -> UserResponse:
    user = await service.register(data)

    # Audit: user registration with request context (IP, UA, campus)
    from app.domains.audit.service import AuditService
    import logging
    try:
        audit_svc = AuditService(session)
        meta = get_request_metadata(request)
        await audit_svc.record(
            user_id=user.id,
            username=user.username,
            action=CREATE,
            resource_type=USER,
            resource_id=str(user.id),
            details={"username": user.username, "email": user.email},
            **meta,
        )
        await session.flush()
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to write audit entry for user registration (non-fatal)",
            exc_info=True,
        )

    return UserResponse.model_validate(user)


_login_limiter = RateLimiter()


@router.post("/login", response_model=TokenResponse)
async def login(
    data: UserLogin,
    request: Request,
    service: UserService = Depends(get_user_service),
) -> TokenResponse:
    ip_address = request.client.host if request.client else None
    client_key = f"login:{ip_address or 'unknown'}"

    allowed, retry_after = _login_limiter.check(client_key, max_requests=5, window_seconds=60)
    if not allowed:
        SecurityAuditLogger.rate_limit_hit(
            key=client_key,
            ip_address=ip_address,
            path="/auth/login",
        )
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "Too many requests", "retry_after_seconds": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    access_token, refresh_token_str, expires_in = await service.login(
        data, ip_address=ip_address,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=expires_in,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    request: Request,
    refresh_token: str = Query(
        ..., description="The refresh token (query parameter)"
    ),
    service: UserService = Depends(get_user_service),
) -> TokenResponse:
    ip_address = request.client.host if request.client else None
    access, new_refresh, expires_in = await service.refresh_token(
        refresh_token, ip_address=ip_address,
    )
    return TokenResponse(
        access_token=access,
        refresh_token=new_refresh,
        expires_in=expires_in,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    data: UserUpdate,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    user = await service.update_user(current_user.id, data)
    return UserResponse.model_validate(user)


@router.patch("/me/password", status_code=status.HTTP_200_OK)
async def change_my_password(
    data: PasswordChange,
    service: UserService = Depends(get_user_service),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    await service.change_password(current_user.id, data)
    return {"detail": "Password updated"}


# ---------------------------------------------------------------------------
# School membership / active-school switching
# ---------------------------------------------------------------------------


async def get_membership_service(
    session=Depends(get_session),
) -> SchoolMembershipService:
    return SchoolMembershipService(
        SchoolMembershipRepository(session), session
    )


@router.get(
    "/schools",
    response_model=list[SchoolMembershipResponse],
    tags=["auth", "multi-tenant"],
)
async def list_my_schools(
    current_user: User = Depends(get_current_user),
    service: SchoolMembershipService = Depends(get_membership_service),
) -> list[SchoolMembershipResponse]:
    """List the schools the authenticated user belongs to."""
    schools = await service.list_schools(current_user.id)
    return [SchoolMembershipResponse(**s) for s in schools]


@router.post(
    "/schools/switch",
    response_model=TokenResponse,
    tags=["auth", "multi-tenant"],
)
async def switch_school(
    data: SchoolSwitchRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
    membership_service: SchoolMembershipService = Depends(get_membership_service),
) -> TokenResponse:
    """Switch the authenticated user's active school.

    The membership is validated server-side (the user must hold an
    active membership for the target campus). On success, fresh tokens
    carrying the new ``campus_id`` claim are issued so every subsequent
    request is scoped to the newly selected school.
    """
    await membership_service.switch_school(current_user, data.campus_id)

    ip_address = request.client.host if request.client else None
    access_token, refresh_token_str, expires_in = await service.issue_tokens(
        current_user, campus_id=data.campus_id, ip_address=ip_address
    )

    # Audit: school switch (non-fatal on failure)
    try:
        from app.domains.audit.constants import UPDATE, USER
        from app.domains.audit.service import AuditService

        audit_svc = AuditService(membership_service.session)
        await audit_svc.record(
            user_id=current_user.id,
            username=current_user.username,
            action=UPDATE,
            resource_type="school_membership",
            resource_id=str(data.campus_id),
            details={"action": "switch_active_school", "campus_id": data.campus_id},
            campus_id=data.campus_id,
            ip_address=ip_address,
        )
        await membership_service.session.flush()
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "Failed to write audit entry for school switch (non-fatal)",
            exc_info=True,
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token_str,
        expires_in=expires_in,
    )