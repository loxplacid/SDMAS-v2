from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.auth.models import User
from app.domains.auth.repository import UserRepository


@pytest.fixture
def user_repo(db_session: AsyncSession) -> UserRepository:
    return UserRepository(db_session)


class TestUserCreate:
    @pytest.mark.asyncio
    async def test_create(self, user_repo: UserRepository):
        user = User(
            email="test@test.com",
            username="testuser",
            password_hash="hashed_pw",
            display_name="Test User",
            role="staff",
            is_active=True,
        )
        created = await user_repo.create(user)
        assert created.id is not None
        assert created.email == "test@test.com"
        assert created.username == "testuser"

    @pytest.mark.asyncio
    async def test_duplicate_email(self, user_repo: UserRepository):
        user1 = User(
            email="dup@test.com",
            username="user1",
            password_hash="hash",
            display_name="User 1",
            role="staff",
            is_active=True,
        )
        await user_repo.create(user1)

        import sqlalchemy.exc

        user2 = User(
            email="dup@test.com",
            username="user2",
            password_hash="hash",
            display_name="User 2",
            role="staff",
            is_active=True,
        )
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            await user_repo.create(user2)


class TestUserGet:
    @pytest.mark.asyncio
    async def test_get_by_id(self, user_repo: UserRepository):
        user = User(
            email="get@test.com",
            username="getuser",
            password_hash="hash",
            display_name="Get User",
            role="staff",
            is_active=True,
        )
        created = await user_repo.create(user)
        found = await user_repo.get_by_id(created.id)
        assert found.email == "get@test.com"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, user_repo: UserRepository):
        with pytest.raises(NotFoundError):
            await user_repo.get_by_id(99999)

    @pytest.mark.asyncio
    async def test_get_by_email(self, user_repo: UserRepository):
        user = User(
            email="byemail@test.com",
            username="byemail",
            password_hash="hash",
            display_name="By Email",
            role="staff",
            is_active=True,
        )
        await user_repo.create(user)
        found = await user_repo.get_by_email("byemail@test.com")
        assert found is not None
        assert found.username == "byemail"

    @pytest.mark.asyncio
    async def test_get_by_email_missing(self, user_repo: UserRepository):
        found = await user_repo.get_by_email("missing@test.com")
        assert found is None

    @pytest.mark.asyncio
    async def test_get_by_username(self, user_repo: UserRepository):
        user = User(
            email="byuser@test.com",
            username="byusername",
            password_hash="hash",
            display_name="By Username",
            role="staff",
            is_active=True,
        )
        await user_repo.create(user)
        found = await user_repo.get_by_username("byusername")
        assert found is not None
        assert found.email == "byuser@test.com"

    @pytest.mark.asyncio
    async def test_get_by_username_missing(self, user_repo: UserRepository):
        found = await user_repo.get_by_username("nobody")
        assert found is None


class TestUserList:
    @pytest.mark.asyncio
    async def test_list_all(self, user_repo: UserRepository):
        for i in range(3):
            user = User(
                email=f"list{i}@test.com",
                username=f"listuser{i}",
                password_hash="hash",
                display_name=f"List User {i}",
                role="staff",
                is_active=True,
            )
            await user_repo.create(user)
        users, total = await user_repo.list()
        assert total == 3
        assert len(users) == 3

    @pytest.mark.asyncio
    async def test_filter_by_role(self, user_repo: UserRepository):
        admin = User(
            email="admin@test.com",
            username="admin1",
            password_hash="hash",
            display_name="Admin",
            role="admin",
            is_active=True,
        )
        staff = User(
            email="staff@test.com",
            username="staff1",
            password_hash="hash",
            display_name="Staff",
            role="staff",
            is_active=True,
        )
        await user_repo.create(admin)
        await user_repo.create(staff)

        admins, total = await user_repo.list(role="admin")
        assert total == 1
        assert admins[0].username == "admin1"

    @pytest.mark.asyncio
    async def test_filter_by_active(self, user_repo: UserRepository):
        active = User(
            email="active@test.com",
            username="active1",
            password_hash="hash",
            display_name="Active",
            role="staff",
            is_active=True,
        )
        inactive = User(
            email="inactive@test.com",
            username="inactive1",
            password_hash="hash",
            display_name="Inactive",
            role="staff",
            is_active=False,
        )
        await user_repo.create(active)
        await user_repo.create(inactive)

        active_users, total = await user_repo.list(is_active=True)
        assert total == 1
        assert active_users[0].username == "active1"

    @pytest.mark.asyncio
    async def test_pagination(self, user_repo: UserRepository):
        for i in range(5):
            user = User(
                email=f"page{i}@test.com",
                username=f"pageuser{i}",
                password_hash="hash",
                display_name=f"Page {i}",
                role="staff",
                is_active=True,
            )
            await user_repo.create(user)
        users, total = await user_repo.list(skip=0, limit=2)
        assert total == 5
        assert len(users) == 2


class TestUserUpdate:
    @pytest.mark.asyncio
    async def test_update_display_name(self, user_repo: UserRepository):
        user = User(
            email="update@test.com",
            username="updateuser",
            password_hash="hash",
            display_name="Old Name",
            role="staff",
            is_active=True,
        )
        created = await user_repo.create(user)
        created.display_name = "New Name"
        updated = await user_repo.update(created)
        assert updated.display_name == "New Name"