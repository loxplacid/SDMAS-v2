from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.domains.auth.models import User
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


class UserService:
    def __init__(self, user_repo: UserRepository) -> None:
        self.repo = user_repo

    async def register(self, data: UserCreate) -> User:
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
            role="staff",
            is_active=True,
        )
        try:
            created = await self.repo.create(user)
        except IntegrityError:
            raise ConflictError("User already exists")

        return created

    async def login(self, data: UserLogin) -> tuple[str, str, int]:
        user = await self.repo.get_by_username(data.login)
        if user is None:
            user = await self.repo.get_by_email(data.login)

        if user is None:
            raise AuthenticationError("Invalid username or password")

        if not user.is_active:
            raise AuthenticationError("Account is inactive")

        if not verify_password(data.password, user.password_hash):
            raise AuthenticationError("Invalid username or password")

        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        from app.config import settings

        return access_token, refresh_token, settings.access_token_expire_minutes * 60

    async def refresh_token(
        self, token: str
    ) -> tuple[str, str, int]:
        try:
            payload = decode_token(token)
        except ValueError:
            raise AuthenticationError("Invalid or expired refresh token")

        user_id = payload.get("sub")
        if user_id is None:
            raise AuthenticationError("Invalid token payload")

        user = await self.repo.get_by_id(int(user_id))

        token_data = {"sub": str(user.id), "username": user.username}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        from app.config import settings

        return access_token, refresh_token, settings.access_token_expire_minutes * 60

    async def get_current_user(self, token: str) -> User:
        try:
            payload = decode_token(token)
        except ValueError:
            raise AuthenticationError("Invalid or expired token")

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

    async def admin_update_user(
        self, user_id: int, data: AdminUserUpdate
    ) -> User:
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
        if data.role is not None:
            user.role = data.role
        if data.is_active is not None:
            user.is_active = data.is_active

        return await self.repo.update(user)

    async def list_users(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[User], int]:
        return await self.repo.list(
            role=role, is_active=is_active, skip=skip, limit=limit
        )