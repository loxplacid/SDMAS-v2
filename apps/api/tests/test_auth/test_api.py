from __future__ import annotations

from httpx import AsyncClient


class TestRegisterEndpoint:
    async def test_register_success(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/auth/register",
            json={
                "email": "api@test.com",
                "username": "apiuser",
                "password": "Str0ng!Pass",
                "display_name": "API User",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "api@test.com"
        assert data["username"] == "apiuser"
        assert "password" not in data
        assert "password_hash" not in data

    async def test_register_duplicate_email(self, api_client: AsyncClient):
        body = {
            "email": "dupapi@test.com",
            "username": "dupapi1",
            "password": "Str0ng!Pass",
            "display_name": "Dup",
        }
        resp1 = await api_client.post("/auth/register", json=body)
        assert resp1.status_code == 201
        resp2 = await api_client.post("/auth/register", json=body)
        assert resp2.status_code == 409

    async def test_register_invalid_password(self, api_client: AsyncClient):
        resp = await api_client.post(
            "/auth/register",
            json={
                "email": "weak@test.com",
                "username": "weakuser",
                "password": "short",
                "display_name": "Weak",
            },
        )
        assert resp.status_code == 422


class TestLoginEndpoint:
    async def test_login_success(self, api_client: AsyncClient):
        await api_client.post(
            "/auth/register",
            json={
                "email": "loginapi@test.com",
                "username": "loginapi",
                "password": "Str0ng!Pass",
                "display_name": "Login API",
            },
        )
        resp = await api_client.post(
            "/auth/login",
            json={"login": "loginapi@test.com", "password": "Str0ng!Pass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "expires_in" in data

    async def test_login_wrong_password(self, api_client: AsyncClient):
        await api_client.post(
            "/auth/register",
            json={
                "email": "wrongapi@test.com",
                "username": "wrongapi",
                "password": "Str0ng!Pass",
                "display_name": "Wrong",
            },
        )
        resp = await api_client.post(
            "/auth/login",
            json={"login": "wrongapi@test.com", "password": "WrongPass1!"},
        )
        assert resp.status_code == 401


class TestMeEndpoint:
    async def _register_and_login(self, api_client: AsyncClient, suffix: str):
        email = f"{suffix}@test.com"
        await api_client.post(
            "/auth/register",
            json={
                "email": email,
                "username": suffix,
                "password": "Str0ng!Pass",
                "display_name": suffix.title(),
            },
        )
        login_resp = await api_client.post(
            "/auth/login",
            json={"login": email, "password": "Str0ng!Pass"},
        )
        return login_resp.json()["access_token"]

    async def test_get_me(self, api_client: AsyncClient):
        token = await self._register_and_login(api_client, "meapi")
        resp = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["email"] == "meapi@test.com"

    async def test_get_me_no_auth(self, api_client: AsyncClient):
        resp = await api_client.get("/auth/me")
        assert resp.status_code == 401

    async def test_update_me(self, api_client: AsyncClient):
        token = await self._register_and_login(api_client, "updme")
        resp = await api_client.patch(
            "/auth/me",
            json={"display_name": "New Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "New Name"

    async def test_change_password(self, api_client: AsyncClient):
        email = "changeme@test.com"
        await api_client.post(
            "/auth/register",
            json={
                "email": email,
                "username": "changeme",
                "password": "OldPass1!",
                "display_name": "Change",
            },
        )
        login_resp = await api_client.post(
            "/auth/login",
            json={"login": email, "password": "OldPass1!"},
        )
        token = login_resp.json()["access_token"]

        resp = await api_client.patch(
            "/auth/me/password",
            json={"current_password": "OldPass1!", "new_password": "NewPass2@"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200


class TestRefreshEndpoint:
    async def test_refresh_token(self, api_client: AsyncClient):
        email = "refapi@test.com"
        await api_client.post(
            "/auth/register",
            json={
                "email": email,
                "username": "refapi",
                "password": "Str0ng!Pass",
                "display_name": "Refresh",
            },
        )
        login_resp = await api_client.post(
            "/auth/login",
            json={"login": email, "password": "Str0ng!Pass"},
        )
        refresh = login_resp.json()["refresh_token"]

        resp = await api_client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_refresh_accepts_body_not_query_param(self, api_client: AsyncClient):
        """The refresh contract is ONE coherent body-based API: passing the
        token as a query parameter is rejected (422), so the token never
        travels in URLs."""
        email = "refbody@test.com"
        await api_client.post(
            "/auth/register",
            json={
                "email": email,
                "username": "refbody",
                "password": "Str0ng!Pass",
                "display_name": "RefreshBody",
            },
        )
        login_resp = await api_client.post(
            "/auth/login",
            json={"login": email, "password": "Str0ng!Pass"},
        )
        refresh = login_resp.json()["refresh_token"]

        # Body-based is the only supported contract.
        resp = await api_client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 200

        # Query-parameter usage is rejected outright.
        resp_q = await api_client.post("/auth/refresh", params={"refresh_token": refresh})
        assert resp_q.status_code == 422
