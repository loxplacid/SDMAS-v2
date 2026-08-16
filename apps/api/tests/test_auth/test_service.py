from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.domains.auth.repository import UserRepository
from app.domains.auth.schemas import PasswordChange, UserCreate, UserLogin, UserUpdate
from app.domains.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.domains.auth.service import UserService


@pytest_asyncio.fixture
async def user_service(db_session: AsyncSession) -> UserService:
    repo = UserRepository(db_session)
    return UserService(repo)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pw = "secure_password"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed) is True
        assert verify_password("wrong", hashed) is False


class TestTokenGeneration:
    def test_access_token_roundtrip(self):
        token = create_access_token(
            data={"sub": "1"},
            expires_delta=timedelta(minutes=15),
        )
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert "exp" in payload

    def test_refresh_token_roundtrip(self):
        token = create_refresh_token(data={"sub": "1"})
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload.get("type") == "refresh"

    def test_invalid_token(self):
        with pytest.raises(ValueError, match="Invalid or expired"):
            decode_token("invalid.token.here")


class TestRegister:
    @pytest.mark.asyncio
    async def test_register_success(self, user_service: UserService):
        data = UserCreate(
            email="new@test.com",
            username="newuser",
            password="Str0ng!Pass",
            display_name="New User",
        )
        user = await user_service.register(data)
        assert user.email == "new@test.com"
        assert user.username == "newuser"
        assert user.password_hash != "Str0ng!Pass"
        # Public self-registration must mint the least-privileged role
        # (never staff/admin) — see API hardening.
        assert user.role == "parent"
        assert user.is_active is True

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, user_service: UserService):
        data = UserCreate(
            email="dupreg@test.com",
            username="dupreg1",
            password="Str0ng!Pass",
            display_name="Dup",
        )
        await user_service.register(data)
        duplicate = UserCreate(
            email="dupreg@test.com",
            username="dupreg2",
            password="Str0ng!Pass",
            display_name="Dup2",
        )
        with pytest.raises(ConflictError, match="already registered"):
            await user_service.register(duplicate)

    @pytest.mark.asyncio
    async def test_register_duplicate_username(self, user_service: UserService):
        data = UserCreate(
            email="user1@test.com",
            username="dupuser",
            password="Str0ng!Pass",
            display_name="User 1",
        )
        await user_service.register(data)
        duplicate = UserCreate(
            email="user2@test.com",
            username="dupuser",
            password="Str0ng!Pass",
            display_name="User 2",
        )
        with pytest.raises(ConflictError, match="already registered"):
            await user_service.register(duplicate)


class TestLogin:
    @pytest.mark.asyncio
    async def test_login_success(self, user_service: UserService):
        reg = UserCreate(
            email="login@test.com",
            username="loginuser",
            password="Str0ng!Pass",
            display_name="Login User",
        )
        await user_service.register(reg)
        token_resp = await user_service.login(
            UserLogin(login="login@test.com", password="Str0ng!Pass")
        )
        assert len(token_resp) == 3
        access, refresh, expires = token_resp
        assert isinstance(access, str)
        assert isinstance(refresh, str)
        assert isinstance(expires, int)
        payload = decode_token(access)
        assert payload["sub"] is not None

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, user_service: UserService):
        reg = UserCreate(
            email="wrongpw@test.com",
            username="wrongpw",
            password="Str0ng!Pass",
            display_name="Wrong PW",
        )
        await user_service.register(reg)
        with pytest.raises(AuthenticationError, match="Invalid"):
            await user_service.login(
                UserLogin(login="wrongpw@test.com", password="WrongPass1!")
            )


class TestGetCurrentUser:
    @pytest.mark.asyncio
    async def test_get_current_user_by_id(self, user_service: UserService):
        data = UserCreate(
            email="current@test.com",
            username="currentuser",
            password="Str0ng!Pass",
            display_name="Current User",
        )
        user = await user_service.register(data)

        token = create_access_token(data={"sub": str(user.id)})
        found = await user_service.get_current_user(token)
        assert found.username == "currentuser"

    @pytest.mark.asyncio
    async def test_get_current_user_not_found(self, user_service: UserService):
        token = create_access_token(data={"sub": "99999"})
        with pytest.raises(AuthenticationError, match="User not found"):
            await user_service.get_current_user(token)


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_update_display_name(self, user_service: UserService):
        data = UserCreate(
            email="upd@test.com",
            username="upduser",
            password="Str0ng!Pass",
            display_name="Original",
        )
        user = await user_service.register(data)
        updated = await user_service.update_user(
            user.id, UserUpdate(display_name="Updated")
        )
        assert updated.display_name == "Updated"

    @pytest.mark.asyncio
    async def test_update_not_found(self, user_service: UserService):
        with pytest.raises(NotFoundError):
            await user_service.update_user(99999, UserUpdate(display_name="Nope"))


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_change_password_success(self, user_service: UserService):
        data = UserCreate(
            email="changepw@test.com",
            username="changepw",
            password="OldPass1!",
            display_name="Change PW",
        )
        user = await user_service.register(data)
        await user_service.change_password(
            user.id,
            PasswordChange(current_password="OldPass1!", new_password="NewPass2@"),
        )
        token_resp = await user_service.login(
            UserLogin(login="changepw@test.com", password="NewPass2@")
        )
        assert token_resp is not None

    @pytest.mark.asyncio
    async def test_change_password_wrong_current(self, user_service: UserService):
        data = UserCreate(
            email="wrongpw@test.com",
            username="wrongpw2",
            password="OldPass1!",
            display_name="Wrong PW",
        )
        user = await user_service.register(data)
        with pytest.raises(AuthenticationError, match="Current password is incorrect"):
            await user_service.change_password(
                user.id,
                PasswordChange(
                    current_password="WrongOld!", new_password="NewPass2@"
                ),
            )


class TestRefreshToken:
    @pytest.mark.asyncio
    async def test_refresh_success(self, user_service: UserService):
        data = UserCreate(
            email="refresh@test.com",
            username="refreshuser",
            password="Str0ng!Pass",
            display_name="Refresh",
        )
        user = await user_service.register(data)
        _, old_refresh, _ = await user_service.login(
            UserLogin(login="refresh@test.com", password="Str0ng!Pass")
        )
        new_access, new_refresh, _ = await user_service.refresh_token(
            old_refresh
        )
        assert isinstance(new_access, str)
        assert isinstance(new_refresh, str)
        payload = decode_token(new_access)
        assert str(user.id) == payload["sub"]


class TestListUsers:
    @pytest.mark.asyncio
    async def test_list_all(self, user_service: UserService):
        for i in range(3):
            await user_service.register(
                UserCreate(
                    email=f"list{i}@test.com",
                    username=f"listuser{i}",
                    password="Str0ng!Pass",
                    display_name=f"User {i}",
                )
            )
        users, total = await user_service.list_users()
        assert len(users) == 3
        assert total == 3