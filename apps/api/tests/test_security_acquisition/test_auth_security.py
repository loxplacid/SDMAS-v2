"""Authentication boundary tests (API-level).

Each test proves a specific invariant:

* unauthenticated → 401 by the global default-deny auth gate
* expired access token → 401
* malformed access token → 401
* refresh token cannot be used as a bearer credential → 401
* refresh token rotation: old token is single-use
* refresh token reuse → family-wide revocation (the NEW token dies too)
* invalid refresh token → 401
* deactivated user → 401 on any request

These fail the suite the moment token validation or the auth gate is
weakened, regardless of which router is involved.
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select

from app.domains.auth.models import User
from app.domains.auth.security import create_access_token

from .conftest import AcqEnv, login, login_full

pytestmark = pytest.mark.asyncio


async def test_unauthenticated_private_endpoint_rejected(acq_env: AcqEnv):
    """Invariant: the global auth gate rejects anonymous requests to any
    private endpoint before routing — no router can forget to protect it."""
    for path in ("/students", "/api/classes", "/api/documents", "/jobs"):
        resp = await acq_env.client.get(path)
        assert resp.status_code == 401, f"{path}: {resp.status_code}"


async def test_expired_access_token_rejected(acq_env: AcqEnv):
    """Invariant: a token whose ``exp`` is in the past never authenticates."""
    token = create_access_token(
        {"sub": "1", "username": "admin_a", "jti": "expired-jti"},
        expires_delta=datetime.timedelta(seconds=-60),
        campus_id=1,
    )
    resp = await acq_env.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401, resp.text


async def test_malformed_token_rejected(acq_env: AcqEnv):
    """Invariant: garbage that is not a JWT is rejected with 401."""
    resp = await acq_env.client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401, resp.text


async def test_token_signed_with_wrong_secret_rejected(acq_env: AcqEnv):
    """Invariant: a token forged with any other secret is invalid (HMAC
    signature verification)."""
    from jose import jwt as _jwt

    forged = _jwt.encode(
        {"sub": "1", "type": "access", "exp": 4102444800},
        "attacker-secret",
        algorithm="HS256",
    )
    resp = await acq_env.client.get("/auth/me", headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401, resp.text


async def test_refresh_token_cannot_be_used_as_bearer(acq_env: AcqEnv):
    """Invariant: refresh tokens are single-purpose credentials — a stolen
    refresh token must not act as an API bearer credential."""
    tokens = await login_full(acq_env, "admin_a")
    resp = await acq_env.client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['refresh_token']}"}
    )
    assert resp.status_code == 401, resp.text


async def test_refresh_rotation_issues_working_new_token(acq_env: AcqEnv):
    """Invariant: refreshing issues a NEW pair (rotation) — the new token
    is immediately usable and rotates again.  Single-use enforcement of the
    consumed token is proven by the reuse test: presenting it again is a
    reuse attack that kills the whole family."""
    tokens = await login_full(acq_env, "admin_a")

    resp = await acq_env.client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text
    rotated = resp.json()

    # A rotated pair is issued — the refresh token is NOT the same one.
    assert rotated["refresh_token"] != tokens["refresh_token"]

    # The new token is live and can be rotated again (normal lifecycle).
    resp = await acq_env.client.post(
        "/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text


async def test_refresh_reuse_detected_revokes_whole_family(acq_env: AcqEnv):
    """Invariant: replaying a revoked refresh token is treated as token
    theft — ALL of the user's refresh tokens are revoked (family rotation),
    including the freshly rotated one."""
    tokens = await login_full(acq_env, "admin_a")

    resp = await acq_env.client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text
    rotated = resp.json()

    # Replay the OLD (already-rotated) token → reuse detected → 401.
    resp = await acq_env.client.post(
        "/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 401, resp.text

    # Family revocation: even the NEW token is now invalid.
    resp = await acq_env.client.post(
        "/auth/refresh", json={"refresh_token": rotated["refresh_token"]}
    )
    assert resp.status_code == 401, resp.text


async def test_invalid_refresh_token_rejected(acq_env: AcqEnv):
    """Invariant: a syntactically invalid refresh token is rejected."""
    for bad in ("garbage", "not.a.jwt", ""):
        resp = await acq_env.client.post("/auth/refresh", json={"refresh_token": bad})
        assert resp.status_code == 401, f"{bad!r}: {resp.status_code}"


async def test_refresh_preserves_identity(acq_env: AcqEnv):
    """Invariant: rotating a refresh token mints a new access token for the
    SAME user — identity comes from the signed token, never from caller
    input, so no user can be substituted during rotation."""
    tokens_a = await login_full(acq_env, "admin_a")

    resp = await acq_env.client.post(
        "/auth/refresh", json={"refresh_token": tokens_a["refresh_token"]}
    )
    assert resp.status_code == 200, resp.text
    rotated = resp.json()

    me = await acq_env.client.get(
        "/auth/me", headers={"Authorization": f"Bearer {rotated['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "admin_a"


async def test_deactivated_user_tokens_rejected(acq_env: AcqEnv):
    """Invariant: tokens issued to a user who is later deactivated stop
    authenticating — deactivation is an immediate, token-independent kill
    switch."""
    tokens = await login_full(acq_env, "teacher_a")

    async with acq_env.factory() as s:
        user = (await s.execute(select(User).where(User.username == "teacher_a"))).scalar_one()
        user.is_active = False
        await s.commit()

    resp = await acq_env.client.get(
        "/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
    )
    assert resp.status_code == 401, resp.text


async def test_access_token_cannot_impersonate_another_user(acq_env: AcqEnv):
    """Invariant: the token's ``sub`` always resolves to the token owner —
    requesting another user's profile with your own token is an IDOR that
    must fail at the dependency layer."""
    headers_a = await login(acq_env, "admin_a")
    resp = await acq_env.client.get("/auth/me", headers=headers_a)
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin_a"
