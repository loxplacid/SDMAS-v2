"""Production authentication security audit — behavioral regression tests.

Covers the attack surfaces mandated by the auth audit:

* invalid / nonexistent / disabled credentials
* malformed, truncated, wrong-algorithm and ``alg:none`` tokens
* expired access and refresh tokens
* refresh rotation, reuse detection and family revocation
* refresh token used as a bearer credential
* server-side logout (refresh-token invalidation)
* privilege changes during an active session
* concurrent sessions
* brute-force throttling

Every authentication failure must be a deliberate 4xx (401/422/429) —
never a generic 500.
"""

from __future__ import annotations

import secrets
from datetime import timedelta

from httpx import AsyncClient
from jose import jwt

from app.config import settings
from app.domains.auth.security import create_access_token

_ALGO = settings.jwt_algorithm


async def _register(
    client: AsyncClient, suffix: str, password: str = "Str0ng!Pass"
) -> str:
    """Register a user and return its unique login email."""
    email = f"{suffix}@audit.test"
    resp = await client.post(
        "/auth/register",
        json={
            "email": email,
            "username": suffix,
            "password": password,
            "display_name": suffix.title(),
        },
    )
    assert resp.status_code == 201, resp.text
    return email


async def _login(
    client: AsyncClient,
    login: str,
    password: str = "Str0ng!Pass",
) -> tuple[str, str]:
    resp = await client.post("/auth/login", json={"login": login, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return data["access_token"], data["refresh_token"]


def _forge_alg_none_token(sub: str = "1") -> str:
    """Hand-craft an ``alg: none`` JWT (the installed jose refuses to
    mint one, so the forgery is built manually)."""
    import base64
    import json as _json

    def b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    header = b64url(_json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64url(_json.dumps({"sub": sub, "type": "access"}).encode())
    return f"{header}.{payload}."


async def _create_campus_user(
    client: AsyncClient,
    admin_headers: dict[str, str],
    suffix: str,
) -> tuple[int, str]:
    """Create a campus-pinned user through the admin API (admin is campus
    1), so both login and permission-gated flows work.  Returns (id, email)."""
    email = f"{suffix}@audit.test"
    resp = await client.post(
        "/admin/users",
        json={
            "email": email,
            "username": suffix,
            "password": "RBACPass123!",
            "display_name": suffix.title(),
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"], email


# =====================================================================
# Invalid credentials — deliberate 4xx, no user enumeration
# =====================================================================


class TestInvalidCredentials:
    async def test_wrong_password_401(self, api_client: AsyncClient) -> None:
        email = await _register(api_client, "wrongpw")
        resp = await api_client.post(
            "/auth/login", json={"login": email, "password": "WrongPass1!"}
        )
        assert resp.status_code == 401, resp.text
        assert resp.json()["detail"] == "Invalid username or password"

    async def test_nonexistent_user_401_same_message(self, api_client: AsyncClient) -> None:
        """The same generic message as a wrong password — no enumeration."""
        resp = await api_client.post(
            "/auth/login",
            json={"login": "ghost.user@audit.test", "password": "Whatever1!"},
        )
        assert resp.status_code == 401, resp.text
        assert resp.json()["detail"] == "Invalid username or password"

    async def test_missing_password_is_422(self, api_client: AsyncClient) -> None:
        resp = await api_client.post(
            "/auth/login", json={"login": "someone@audit.test"}
        )
        assert resp.status_code == 422, resp.text

    async def test_malformed_auth_header_401(self, api_client: AsyncClient) -> None:
        for header in ("Bearer", "Bearer ", "Basic dXNlcjpwYXNz", "Token abc123"):
            resp = await api_client.get(
                "/auth/me", headers={"Authorization": header}
            )
            assert resp.status_code == 401, f"{header!r}: {resp.status_code}"

    async def test_no_credentials_401(self, api_client: AsyncClient) -> None:
        resp = await api_client.get("/auth/me")
        assert resp.status_code == 401, resp.text


# =====================================================================
# Disabled users — login and existing sessions must die
# =====================================================================


class TestDisabledUsers:
    async def test_disabled_user_cannot_login(
        self, api_client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        user_id, email = await _create_campus_user(api_client, admin_headers, "disabled")
        token, _ = await _login(api_client, email, "RBACPass123!")

        deactivate = await api_client.patch(
            f"/admin/users/{user_id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert deactivate.status_code == 200, deactivate.text

        login = await api_client.post(
            "/auth/login", json={"login": email, "password": "RBACPass123!"}
        )
        assert login.status_code == 401, login.text

        me = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 401, me.text


# =====================================================================
# Malformed tokens — 401, never 500
# =====================================================================


class TestMalformedTokens:
    async def test_garbage_token_401(self, api_client: AsyncClient) -> None:
        resp = await api_client.get(
            "/auth/me", headers={"Authorization": "Bearer not.a.jwt"}
        )
        assert resp.status_code == 401, resp.text

    async def test_truncated_token_401(self, api_client: AsyncClient) -> None:
        email = await _register(api_client, "trunc")
        token, _ = await _login(api_client, email)
        resp = await api_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token[:-12]}"}
        )
        assert resp.status_code == 401, resp.text

    async def test_wrong_algorithm_token_401(self, api_client: AsyncClient) -> None:
        forged = jwt.encode(
            {"sub": "1", "type": "access"}, key=b"x" * 64, algorithm="HS512"
        )
        resp = await api_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {forged}"}
        )
        assert resp.status_code == 401, resp.text

    async def test_alg_none_token_401(self, api_client: AsyncClient) -> None:
        forged = _forge_alg_none_token()
        resp = await api_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {forged}"}
        )
        assert resp.status_code == 401, resp.text

    async def test_refresh_token_signed_with_wrong_alg_401(
        self, api_client: AsyncClient
    ) -> None:
        forged = jwt.encode(
            {"sub": "1", "type": "refresh"}, key=b"y" * 64, algorithm="HS512"
        )
        resp = await api_client.post("/auth/refresh", json={"refresh_token": forged})
        assert resp.status_code == 401, resp.text


# =====================================================================
# Expired sessions
# =====================================================================


class TestExpiredTokens:
    async def test_expired_access_token_401(self, api_client: AsyncClient) -> None:
        email = await _register(api_client, "expireacc")
        token, _ = await _login(api_client, email)
        me = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        uid = me.json()["id"]

        expired = create_access_token(
            {"sub": str(uid), "username": "expireacc", "jti": "expired-jti"},
            expires_delta=timedelta(minutes=-1),
        )
        resp = await api_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {expired}"}
        )
        assert resp.status_code == 401, resp.text

    async def test_expired_refresh_token_401(self, api_client: AsyncClient) -> None:
        from app.domains.auth.security import create_refresh_token

        expired = create_refresh_token(
            {"sub": "999999", "username": "nobody", "jti": "expired-jti"},
            expires_delta=timedelta(days=-1),
        )
        resp = await api_client.post("/auth/refresh", json={"refresh_token": expired})
        assert resp.status_code == 401, resp.text


# =====================================================================
# Refresh rotation, reuse detection, family revocation, concurrent sessions
# =====================================================================


class TestRefreshRotationAndReuse:
    async def test_refresh_rotates_and_old_token_rejected(
        self, api_client: AsyncClient
    ) -> None:
        email = await _register(api_client, "rotator")
        _, r1 = await _login(api_client, email)

        resp = await api_client.post("/auth/refresh", json={"refresh_token": r1})
        assert resp.status_code == 200, resp.text

        reuse = await api_client.post("/auth/refresh", json={"refresh_token": r1})
        assert reuse.status_code == 401, reuse.text

    async def test_refresh_reuse_revokes_entire_family(
        self, api_client: AsyncClient
    ) -> None:
        email = await _register(api_client, "family")
        _, r_a = await _login(api_client, email)  # session A
        _, r_b = await _login(api_client, email)  # session B (concurrent)

        rotated = await api_client.post("/auth/refresh", json={"refresh_token": r_a})
        assert rotated.status_code == 200, rotated.text

        # Replay the rotated-away token → 401 AND the sibling session dies.
        reuse = await api_client.post("/auth/refresh", json={"refresh_token": r_a})
        assert reuse.status_code == 401, reuse.text
        sibling = await api_client.post("/auth/refresh", json={"refresh_token": r_b})
        assert sibling.status_code == 401, sibling.text

    async def test_concurrent_sessions_are_independent(
        self, api_client: AsyncClient
    ) -> None:
        email = await _register(api_client, "concurrent")
        _, r_a = await _login(api_client, email)
        _, r_b = await _login(api_client, email)

        a = await api_client.post("/auth/refresh", json={"refresh_token": r_a})
        assert a.status_code == 200, a.text
        b = await api_client.post("/auth/refresh", json={"refresh_token": r_b})
        assert b.status_code == 200, b.text

    async def test_refresh_token_cannot_be_used_as_bearer(
        self, api_client: AsyncClient
    ) -> None:
        email = await _register(api_client, "reffrbear")
        _, refresh = await _login(api_client, email)
        resp = await api_client.get(
            "/auth/me", headers={"Authorization": f"Bearer {refresh}"}
        )
        assert resp.status_code == 401, resp.text

    async def test_access_token_cannot_be_used_as_refresh(
        self, api_client: AsyncClient
    ) -> None:
        email = await _register(api_client, "accasref")
        access, _ = await _login(api_client, email)
        resp = await api_client.post("/auth/refresh", json={"refresh_token": access})
        assert resp.status_code == 401, resp.text


# =====================================================================
# Server-side logout — refresh tokens are revoked
# =====================================================================


class TestLogout:
    async def test_logout_revokes_all_refresh_tokens(
        self, api_client: AsyncClient
    ) -> None:
        email = await _register(api_client, "logout1")
        access, r1 = await _login(api_client, email)
        _, r2 = await _login(api_client, email)  # second concurrent session

        logout = await api_client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {access}"}
        )
        assert logout.status_code == 204, logout.text

        for token in (r1, r2):
            resp = await api_client.post("/auth/refresh", json={"refresh_token": token})
            assert resp.status_code == 401, resp.text

        # The user can start a fresh session afterwards.
        fresh = await _login(api_client, email)
        assert fresh[0] and fresh[1]

    async def test_logout_is_idempotent(self, api_client: AsyncClient) -> None:
        email = await _register(api_client, "logout2")
        access, _ = await _login(api_client, email)
        headers = {"Authorization": f"Bearer {access}"}
        first = await api_client.post("/auth/logout", headers=headers)
        assert first.status_code == 204, first.text
        second = await api_client.post("/auth/logout", headers=headers)
        assert second.status_code == 204, second.text

    async def test_logout_requires_authentication(self, api_client: AsyncClient) -> None:
        resp = await api_client.post("/auth/logout")
        assert resp.status_code == 401, resp.text

    async def test_access_token_limited_lifetime_after_logout(
        self, api_client: AsyncClient
    ) -> None:
        """Stateless-JWT semantics, pinned: after logout the access token
        still works until its short expiry (30 min), but no NEW token can
        be minted and the client discards the token."""
        email = await _register(api_client, "logout3")
        access, _ = await _login(api_client, email)

        logout = await api_client.post(
            "/auth/logout", headers={"Authorization": f"Bearer {access}"}
        )
        assert logout.status_code == 204, logout.text

        me = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {access}"})
        assert me.status_code == 200, me.text
        assert me.json()["username"] == "logout3"


# =====================================================================
# Privilege changes during an active session
# =====================================================================


class TestPrivilegeChangeDuringSession:
    async def test_access_token_carries_no_role_claim(
        self, api_client: AsyncClient
    ) -> None:
        """The JWT contains identity + campus only — never roles.  Role and
        permission changes therefore take effect on the user's very next
        request (no stale authorization baked into the token)."""
        email = await _register(api_client, "norole")
        access, _ = await _login(api_client, email)
        payload = jwt.decode(
            access, settings.jwt_secret.get_secret_value(), algorithms=[_ALGO]
        )
        assert "role" not in payload
        assert "permissions" not in payload
        assert payload["sub"]
        assert payload["type"] == "access"

    async def test_deactivation_revokes_session_immediately(
        self, api_client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        user_id, email = await _create_campus_user(api_client, admin_headers, "privesc")
        token, _ = await _login(api_client, email, "RBACPass123!")

        me = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200, me.text

        deactivate = await api_client.patch(
            f"/admin/users/{user_id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert deactivate.status_code == 200, deactivate.text

        me = await api_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 401, me.text

    async def test_deactivated_user_cannot_refresh(
        self, api_client: AsyncClient, admin_headers: dict[str, str]
    ) -> None:
        """Deactivation must terminate the session: refresh-token rotation
        (the only way to mint new access tokens) is cut off, not just login."""
        user_id, email = await _create_campus_user(api_client, admin_headers, "refkill")
        _, refresh = await _login(api_client, email, "RBACPass123!")

        deactivate = await api_client.patch(
            f"/admin/users/{user_id}",
            json={"is_active": False},
            headers=admin_headers,
        )
        assert deactivate.status_code == 200, deactivate.text

        resp = await api_client.post("/auth/refresh", json={"refresh_token": refresh})
        assert resp.status_code == 401, resp.text


# =====================================================================
# Brute-force throttling — 5 login failures per IP per minute → 429
# =====================================================================


class TestBruteForceProtection:
    async def test_login_throttled_after_5_failures(self, api_client: AsyncClient) -> None:
        email = await _register(api_client, "bruteforce")

        for _ in range(5):
            resp = await api_client.post(
                "/auth/login", json={"login": email, "password": "WrongPass1!"}
            )
            assert resp.status_code == 401, resp.text

        # The 6th attempt — even with the CORRECT password — is throttled.
        throttled = await api_client.post(
            "/auth/login", json={"login": email, "password": "Str0ng!Pass"}
        )
        assert throttled.status_code == 429, throttled.text
        assert "Retry-After" in throttled.headers
        assert throttled.json()["detail"]["retry_after_seconds"] >= 1

    async def test_refresh_throttled_after_30(self, api_client: AsyncClient) -> None:
        email = await _register(api_client, "reflimit")
        _, refresh = await _login(api_client, email)

        statuses: list[int] = []
        for _ in range(31):
            resp = await api_client.post(
                "/auth/refresh", json={"refresh_token": refresh}
            )
            statuses.append(resp.status_code)
            if resp.status_code == 200:
                refresh = resp.json()["refresh_token"]

        assert statuses.count(429) == 1, statuses
        assert statuses[-1] == 429
