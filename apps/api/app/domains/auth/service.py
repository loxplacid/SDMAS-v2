from __future__ import annotations

import datetime
import hashlib
import logging
import secrets
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.core.security import SecurityAuditLogger
from app.domains.audit.constants import (
    CREATE,
    LOGIN,
    LOGIN_FAILED,
    LOGOUT,
    PASSWORD_CHANGE,
    ROLE,
    UPDATE,
    USER,
)
from app.domains.audit.service import AuditService
from app.domains.audit.utils import safe_details
from app.domains.auth.models import RefreshToken, Role, User
from app.domains.auth.permissions import TENANT_ROLES
from app.domains.auth.repository import UserRepository
from app.domains.auth.schemas import (
    AdminUserUpdate,
    PasswordChange,
    UserCreate,
    UserLogin,
    UserUpdate,
)
from app.domains.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

logger = logging.getLogger(__name__)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.repo = user_repo

    async def register(
        self,
        data: UserCreate,
        *,
        campus_id: int | None = None,
    ) -> User:
        """Register a new user, optionally pinning them to a campus.

        Public self-service registration leaves ``campus_id`` unset;
        tenant-scoped admin creation (``/admin/users``) pins the new
        user to the acting admin's campus so the record can never
        escape the admin's tenant boundary.
        """
        existing_email = await self.repo.get_by_email(data.email)
        if existing_email is not None:
            raise ConflictError(
                f"User with email '{data.email}' is already registered"
            )

        existing_username = await self.repo.get_by_username(data.username)
        if existing_username is not None:
            raise ConflictError(
                f"User with username '{data.username}' is already registered"
            )

        password_hash = hash_password(data.password)
        user = User(
            email=data.email,
            username=data.username,
            password_hash=password_hash,
            display_name=data.display_name,
            # Security: public self-registration must never mint a
            # privileged account.  ``staff``/``admin``/etc. are granted
            # only by a tenant admin through /admin/users.  ``parent`` is
            # the least-privileged tenant role — a self-registered user
            # has no campus membership, so require_tenant_context still
            # denies every tenant-scoped route (403) until an admin
            # links them to a campus.
            role="parent",
            is_active=True,
            campus_id=campus_id,
        )
        try:
            created = await self.repo.create(user)
        except IntegrityError:
            raise ConflictError("User already exists")

        # Audit: user creation
        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                user_id=created.id,
                username=created.username,
                action=CREATE,
                resource_type=USER,
                resource_id=str(created.id),
                details=safe_details({
                    "username": created.username,
                    "email": created.email,
                    "display_name": created.display_name,
                    "role": created.role,
                }),
            )
            await self.repo.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry for user creation (non-fatal)", exc_info=True)

        # Reload with eager role loading so serialization of
        # ``user.roles`` does not trigger an async lazy load
        # (MissingGreenlet) on the freshly created user.
        result = await self.repo.session.execute(
            select(User)
            .where(User.id == created.id)
            .options(selectinload(User.assigned_roles))
        )
        return result.scalar_one()

    async def issue_tokens(
        self,
        user: User,
        *,
        campus_id: int | None = None,
        ip_address: str | None = None,
    ) -> tuple[str, str, int]:
        """Issue a fresh access + refresh token pair for a user.

        ``campus_id`` is embedded in the JWT claim so every request
        authenticated with the returned access token is scoped to that
        school. When ``campus_id`` is ``None`` the user's current
        ``user.campus_id`` is used.
        """
        token_data = {
            "sub": str(user.id),
            "username": user.username,
            "jti": secrets.token_hex(16),
        }
        effective_campus_id = user.campus_id if campus_id is None else campus_id
        access_token = create_access_token(token_data, campus_id=effective_campus_id)
        refresh_token_str = create_refresh_token(token_data, campus_id=effective_campus_id)
        refresh_hash = _hash_token(refresh_token_str)

        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=settings.refresh_token_expire_days
        )
        await self.repo.store_refresh_token(user.id, refresh_hash, expires_at)

        SecurityAuditLogger.login_success(
            user_id=user.id,
            username=user.username,
            ip_address=ip_address,
        )
        return access_token, refresh_token_str, settings.access_token_expire_minutes * 60

    async def login(
        self,
        data: UserLogin,
        ip_address: str | None = None,
    ) -> tuple[str, str, int]:
        user = await self.repo.get_by_username(data.login)
        if user is None:
            user = await self.repo.get_by_email(data.login)

        if user is None:
            SecurityAuditLogger.login_failed(
                username=data.login,
                ip_address=ip_address,
                reason="user_not_found",
            )
            await self._audit_login_failed(
                username=data.login, reason="user_not_found", ip_address=ip_address,
            )
            raise AuthenticationError("Invalid username or password")

        if not user.is_active:
            SecurityAuditLogger.login_failed(
                username=user.username,
                ip_address=ip_address,
                reason="account_inactive",
                user_id=user.id,
            )
            await self._audit_login_failed(
                username=user.username, user_id=user.id,
                reason="account_inactive", ip_address=ip_address,
                campus_id=user.campus_id,
            )
            raise AuthenticationError("Account is inactive")

        if not verify_password(data.password, user.password_hash):
            SecurityAuditLogger.login_failed(
                username=user.username,
                ip_address=ip_address,
                reason="invalid_password",
                user_id=user.id,
            )
            await self._audit_login_failed(
                username=user.username, user_id=user.id,
                reason="invalid_password", ip_address=ip_address,
                campus_id=user.campus_id,
            )
            raise AuthenticationError("Invalid username or password")

        # If the user belongs to one or more schools but has no active
        # campus yet, auto-select the default membership so the JWT claim
        # and all subsequent queries are correctly scoped.
        if user.campus_id is None:
            try:
                from app.domains.auth.membership import (
                    SchoolMembershipRepository,
                )

                memberships = await SchoolMembershipRepository(
                    self.repo.session
                ).list_active_for_user(user.id)
                if memberships:
                    default = next(
                        (m for m in memberships if m.is_default), memberships[0]
                    )
                    user.campus_id = default.campus_id
                    await self.repo.session.flush()
            except Exception:
                logger.warning(
                    "Failed to auto-select default school on login (non-fatal)",
                    exc_info=True,
                )

        access_token, refresh_token_str, _ = await self.issue_tokens(
            user, ip_address=ip_address
        )

        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                user_id=user.id,
                username=user.username,
                action=LOGIN,
                resource_type=USER,
                resource_id=str(user.id),
                details={"login_method": "password"},
                campus_id=user.campus_id,
                ip_address=ip_address,
            )
            await self.repo.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry for login (non-fatal)", exc_info=True)

        return access_token, refresh_token_str, settings.access_token_expire_minutes * 60

    async def logout(
        self,
        user: User,
        ip_address: str | None = None,
    ) -> None:
        """Invalidate the user's server-side session.

        Revokes every outstanding refresh token for the user, so no new
        access token can be minted after logout.  Already-issued access
        tokens remain valid only until their short expiry (stateless
        JWTs) — the client discards them on logout.  Idempotent.
        """
        await self.repo.revoke_all_user_tokens(user.id)

        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                user_id=user.id,
                username=user.username,
                action=LOGOUT,
                resource_type=USER,
                resource_id=str(user.id),
                campus_id=user.campus_id,
                ip_address=ip_address,
            )
            await self.repo.session.flush()
        except Exception:
            logger.warning(
                "Failed to write audit entry for logout (non-fatal)", exc_info=True
            )

    async def _audit_login_failed(
        self,
        *,
        username: str,
        reason: str,
        ip_address: str | None = None,
        user_id: int | None = None,
        campus_id: int | None = None,
    ) -> None:
        """Record a failed login attempt with the SYSTEM "unattributed"
        actor (there is no authenticated user to attribute it to).

        Best-effort — audit failure never masks the login error.
        """
        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                action=LOGIN_FAILED,
                resource_type=USER,
                resource_id=str(user_id) if user_id is not None else None,
                details={"username": username, "reason": reason},
                result="FAILURE",
                failure_reason=reason,
                ip_address=ip_address,
                campus_id=campus_id,
            )
            # Commit immediately: the login request is about to raise, which
            # would otherwise roll the shared session back and silently drop
            # the failed-login trail entry.  A failed attempt must be durable.
            await self.repo.session.commit()
        except Exception:
            logger.warning(
                "Failed to write audit entry for failed login (non-fatal)", exc_info=True
            )

    async def refresh_token(
        self,
        token: str,
        ip_address: str | None = None,
    ) -> tuple[str, str, int]:
        try:
            payload = decode_token(token)
        except ValueError:
            raise AuthenticationError("Invalid or expired refresh token")

        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token payload")

        token_hash = _hash_token(token)
        stored = await self.repo.get_refresh_token(token_hash)

        if stored is None:
            revoked = await self.repo.session.execute(
                select(RefreshToken).where(
                    RefreshToken.token_hash == token_hash,
                )
            )
            existing = revoked.scalar_one_or_none()
            if existing is not None and existing.is_revoked:
                SecurityAuditLogger.token_reuse_detected(
                    user_id=int(user_id),
                    token_type="refresh",
                    ip_address=ip_address,
                )
                await self.repo.revoke_all_user_tokens(int(user_id), except_hash=token_hash)
                # The request is about to fail, which would roll the shared
                # session back and silently undo the family revocation.
                # Commit now so the reuse containment is durable — an
                # attacker replaying a stolen refresh token must kill the
                # whole token family, not just the one token.
                await self.repo.session.commit()
            raise AuthenticationError("Invalid or expired refresh token")

        user = await self.repo.get_by_id(int(user_id))

        # Deactivated users must not be able to rotate their session:
        # a deactivation terminates refresh-token minting, not just login.
        if not user.is_active:
            raise AuthenticationError("Account is inactive")

        token_data = {"sub": str(user.id), "username": user.username, "jti": secrets.token_hex(16)}
        campus_id = user.campus_id
        access_token = create_access_token(token_data, campus_id=campus_id)
        new_refresh_str = create_refresh_token(token_data, campus_id=campus_id)
        new_refresh_hash = _hash_token(new_refresh_str)

        expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=settings.refresh_token_expire_days
        )
        await self.repo.revoke_refresh_token(stored.id, replaced_by_hash=new_refresh_hash)
        await self.repo.store_refresh_token(user.id, new_refresh_hash, expires_at)

        return access_token, new_refresh_str, settings.access_token_expire_minutes * 60

    async def get_current_user(self, token: str) -> User:
        try:
            payload = decode_token(token)
        except ValueError:
            raise AuthenticationError("Invalid or expired token")

        # Only *access* tokens authenticate API requests.  Refresh tokens
        # are single-purpose credentials (rotation + reuse detection) and
        # must not double as bearer credentials.
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type")

        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token payload")

        try:
            user = await self.repo.get_by_id(int(user_id))
        except NotFoundError:
            raise AuthenticationError("User not found")

        if not user.is_active:
            raise AuthenticationError("Account is inactive")

        return user

    async def get_user(self, user_id: int) -> User:
        return await self.repo.get_by_id(user_id)

    async def update_user(self, user_id: int, data: UserUpdate) -> User:
        user = await self.repo.get_by_id(user_id)

        if data.display_name is not None:
            user.display_name = data.display_name
        if data.email is not None:
            if data.email != user.email:
                existing = await self.repo.get_by_email(data.email)
                if existing is not None and existing.id != user_id:
                    raise ConflictError(
                        f"Email '{data.email}' is already in use"
                    )
            user.email = data.email

        return await self.repo.update(user)

    async def change_password(
        self, user_id: int, data: PasswordChange
    ) -> None:
        user = await self.repo.get_by_id(user_id)

        if not verify_password(data.current_password, user.password_hash):
            raise AuthenticationError("Current password is incorrect")

        user.password_hash = hash_password(data.new_password)
        await self.repo.update(user)

        # Audit: password change (never log the password itself)
        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                user_id=user.id,
                username=user.username,
                action=PASSWORD_CHANGE,
                resource_type=USER,
                resource_id=str(user.id),
                campus_id=user.campus_id,
            )
            await self.repo.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry for password change (non-fatal)", exc_info=True)

    async def admin_update_user(
        self, user_id: int, data: AdminUserUpdate
    ) -> User:
        user = await self.repo.get_by_id(user_id)
        before_role = user.role
        before_roles = [r.code for r in (user.assigned_roles or [])]

        if data.display_name is not None:
            user.display_name = data.display_name
        if data.email is not None:
            if data.email != user.email:
                existing = await self.repo.get_by_email(data.email)
                if existing is not None and existing.id != user_id:
                    raise ConflictError(
                        f"Email '{data.email}' is already in use"
                    )
            user.email = data.email
        if data.role is not None:
            # Security: the primary role must stay inside the tenant role
            # set.  A tenant admin must never be able to self-escalate to
            # a platform role (e.g. ``platform_admin`` -> ``platform.access``)
            # by patching their own primary role.  Mirrors the assignable
            # set enforced on the M2M endpoint (``_ASSIGNABLE_ROLES``).
            if data.role not in TENANT_ROLES:
                raise ValidationError(
                    f"Invalid role '{data.role}'. Roles must be one of: "
                    f"{', '.join(sorted(TENANT_ROLES))}"
                )
            user.role = data.role
        if data.is_active is not None:
            was_active = user.is_active
            user.is_active = data.is_active
            if was_active and not data.is_active:
                # Deactivation terminates the session: revoke every
                # outstanding refresh token so no new access token can
                # be minted after the account is disabled.
                await self.repo.revoke_all_user_tokens(user.id)
        if data.roles is not None:
            # Whitelist enforced inside _sync_user_roles — the single
            # M2M mutation point (the /roles endpoint and this PATCH
            # body both funnel through it).
            await self._sync_user_roles(user, data.roles)

        updated = await self.repo.update(user)

        # Audit: role/permission changes
        role_changed = data.role is not None and data.role != before_role
        roles_changed = data.roles is not None and set(data.roles) != set(before_roles)
        if role_changed or roles_changed:
            try:
                audit_svc = AuditService(self.repo.session)
                await audit_svc.record(
                    user_id=user_id,
                    username=updated.username,
                    action=UPDATE,
                    resource_type=ROLE,
                    resource_id=str(user_id),
                    details=safe_details({
                        "before": {"role": before_role, "roles": before_roles},
                        "after": {"role": updated.role, "roles": [r.code for r in (updated.assigned_roles or [])]},
                    }),
                )
                await self.repo.session.flush()
            except Exception:
                logger.warning("Failed to write audit entry for role change (non-fatal)", exc_info=True)

        return updated

    async def set_user_roles(
        self, user_id: int, role_codes: list[str]
    ) -> User:
        """Replace all M2M role assignments for a user.

        Does NOT change the user's primary ``role`` field.
        """
        user = await self.repo.get_by_id(user_id)
        before_roles = [r.code for r in (user.assigned_roles or [])]
        await self._sync_user_roles(user, role_codes)
        updated = await self.repo.update(user)

        # Audit: role assignment change
        try:
            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                user_id=user_id,
                username=updated.username,
                action=UPDATE,
                resource_type=ROLE,
                resource_id=str(user_id),
                details={
                    "before": {"roles": before_roles},
                    "after": {"roles": role_codes},
                },
            )
            await self.repo.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry for role assignment change (non-fatal)", exc_info=True)

        return updated

    async def _sync_user_roles(
        self, user: User, role_codes: list[str]
    ) -> None:
        """Replace M2M role assignments without touching the primary role.

        Security: role codes are whitelisted against ``TENANT_ROLES`` at
        this single mutation point, so no caller (router or service) can
        assign a platform role (``platform_admin``) that would escalate
        a tenant user to cross-tenant access.
        """
        invalid = [c for c in role_codes if c not in TENANT_ROLES]
        if invalid:
            raise ValidationError(
                "Invalid role(s) for assignment: "
                + ", ".join(sorted(set(invalid)))
                + f". Assignable roles: {', '.join(sorted(TENANT_ROLES))}"
            )
        result = await self.repo.session.execute(
            select(Role).where(Role.code.in_(role_codes))
        )
        roles = list(result.scalars().all())
        found = {r.code for r in roles}
        missing = set(role_codes) - found
        if missing:
            raise NotFoundError(f"Roles not found: {', '.join(sorted(missing))}")
        user.assigned_roles = roles

    async def list_users(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[User], int]:
        """List users, optionally restricted to a single campus.

        Tenant-scoped admins pass their own ``campus_id``; the repository
        applies the filter at query construction time so cross-tenant
        user records can never be returned.
        """
        return await self.repo.list(
            role=role, is_active=is_active,
            campus_id=campus_id, skip=skip, limit=limit,
        )
