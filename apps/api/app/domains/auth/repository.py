from __future__ import annotations

import datetime
from typing import Optional, Sequence

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.auth.models import RefreshToken, User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(self, user_id: int) -> User:
        result = await self.session.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            raise NotFoundError(f"User with id {user_id} not found")
        return user

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[User], int]:
        query = select(User)
        count_query = select(func.count(User.id))

        if role is not None:
            query = query.where(User.role == role)
            count_query = count_query.where(User.role == role)
        if is_active is not None:
            query = query.where(User.is_active == is_active)
            count_query = count_query.where(User.is_active == is_active)
        if campus_id is not None:
            # Tenant-scoped admin user management: a tenant admin may only
            # ever see users belonging to their own campus.
            query = query.where(User.campus_id == campus_id)
            count_query = count_query.where(User.campus_id == campus_id)

        query = query.offset(skip).limit(limit).order_by(User.username)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def update(self, user: User) -> User:
        await self.session.flush()
        return user

    async def store_refresh_token(
        self,
        user_id: int,
        token_hash: str,
        expires_at: datetime.datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_refresh_token(
        self, token_hash: str
    ) -> RefreshToken | None:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.datetime.now(datetime.timezone.utc),
            )
        )
        return result.scalar_one_or_none()

    async def revoke_refresh_token(
        self,
        token_id: int,
        replaced_by_hash: str | None = None,
    ) -> None:
        result = await self.session.execute(
            select(RefreshToken).where(RefreshToken.id == token_id)
        )
        token = result.scalar_one_or_none()
        if token:
            token.is_revoked = True
            token.revoked_at = datetime.datetime.now(datetime.timezone.utc)
            token.replaced_by_token_hash = replaced_by_hash
            await self.session.flush()

    async def revoke_all_user_tokens(
        self, user_id: int, except_hash: str | None = None
    ) -> None:
        query = select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,
        )
        if except_hash:
            query = query.where(RefreshToken.token_hash != except_hash)
        result = await self.session.execute(query)
        tokens = result.scalars().all()
        now = datetime.datetime.now(datetime.timezone.utc)
        for token in tokens:
            token.is_revoked = True
            token.revoked_at = now
        await self.session.flush()

    async def count_valid_tokens(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count(RefreshToken.id)).where(
                RefreshToken.user_id == user_id,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.datetime.now(datetime.timezone.utc),
            )
        )
        return result.scalar() or 0