from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ConflictError
from app.domains.auth.models import User, UserSchoolMembership
from app.domains.institution.models import Campus


class SchoolMembershipRepository:
    """Data access for user ↔ school (campus) memberships."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_for_user(self, user_id: int) -> Sequence[UserSchoolMembership]:
        result = await self.session.execute(
            select(UserSchoolMembership)
            .where(UserSchoolMembership.user_id == user_id)
            .order_by(UserSchoolMembership.campus_id)
        )
        return list(result.scalars().all())

    async def list_active_for_user(self, user_id: int) -> Sequence[UserSchoolMembership]:
        result = await self.session.execute(
            select(UserSchoolMembership).where(
                UserSchoolMembership.user_id == user_id,
                UserSchoolMembership.is_active == True,  # noqa: E712
            ).order_by(UserSchoolMembership.campus_id)
        )
        return list(result.scalars().all())

    async def get(self, user_id: int, campus_id: int) -> UserSchoolMembership | None:
        result = await self.session.execute(
            select(UserSchoolMembership).where(
                UserSchoolMembership.user_id == user_id,
                UserSchoolMembership.campus_id == campus_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, membership: UserSchoolMembership) -> UserSchoolMembership:
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def set_default(self, user_id: int, campus_id: int) -> UserSchoolMembership:
        """Mark one membership as default; clear others."""
        memberships = await self.list_for_user(user_id)
        target = None
        for m in memberships:
            if m.campus_id == campus_id:
                m.is_default = True
                target = m
            else:
                m.is_default = False
        if target is None:
            raise NotFoundError("Membership not found for this school")
        await self.session.flush()
        return target

    async def delete(self, membership: UserSchoolMembership) -> None:
        await self.session.delete(membership)
        await self.session.flush()


class SchoolMembershipService:
    """Business logic for user-to-school membership and switching."""

    def __init__(
        self,
        repo: SchoolMembershipRepository,
        session: AsyncSession,
    ) -> None:
        self.repo = repo
        self.session = session

    async def list_schools(self, user_id: int) -> list[dict]:
        """Return the user's memberships enriched with campus details."""
        memberships = await self.repo.list_for_user(user_id)
        result: list[dict] = []
        for m in memberships:
            campus = await self.session.get(Campus, m.campus_id)
            result.append(
                {
                    "campus_id": m.campus_id,
                    "campus_name": campus.name if campus else None,
                    "campus_code": campus.code if campus else None,
                    "institution_id": campus.institution_id if campus else None,
                    "role": m.role,
                    "is_default": m.is_default,
                    "is_active": m.is_active,
                }
            )
        return result

    async def switch_school(self, user: User, campus_id: int) -> UserSchoolMembership:
        """Switch the user's active school to ``campus_id``.

        Only succeeds when the user holds an *active* membership for the
        target campus — this is the server-side authorization gate that
        prevents switching to a school the user does not belong to.
        """
        membership = await self.repo.get(user.id, campus_id)
        if membership is None or not membership.is_active:
            raise NotFoundError("You are not a member of this school")

        # Persist the active campus so the JWT claim stays in sync and
        # legacy code paths (which read users.campus_id) keep working.
        user.campus_id = campus_id
        if not membership.is_default:
            await self.repo.set_default(user.id, campus_id)
        await self.session.flush()
        return membership
