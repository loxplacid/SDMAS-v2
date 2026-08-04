"""Rate-limiting tests.

Two layers are proven:

* API layer — the login endpoint enforces a 5-attempts / 60 s window keyed
  by client IP.  After 5 attempts the 6th is rejected with 429 + Retry-After.
  The window is account-agnostic (per-IP), which is the documented design
  of the in-memory limiter.
* Unit layer — ``RateLimiter`` semantics: sliding window, reset, and the
  per-process assumption (two instances do NOT share state).  This last
  test documents the known limitation that the in-memory limiter is not
  shared across distributed worker processes; swapping to a Redis-backed
  limiter must keep the same interface.

NOTE: the root conftest resets ``_login_limiter`` before every test, so a
full-suite run never trips shared-IP windows accidentally.
"""

from __future__ import annotations

import pytest

from .conftest import AcqEnv

import pytest

from .conftest import AcqEnv

pytestmark = pytest.mark.asyncio


async def test_login_rate_limited_per_ip(acq_env: AcqEnv):
    """Invariant: repeated login attempts from one IP are throttled —
    the 6th attempt in a 60 s window returns 429."""
    for i in range(5):
        resp = await acq_env.client.post(
            "/auth/login",
            json={"login": "admin_a", "password": f"Wrong{i}!"},
        )
        # Wrong credentials → 401, but the attempt still consumes a slot.
        assert resp.status_code == 401, f"attempt {i + 1}: {resp.status_code}"

    resp = await acq_env.client.post(
        "/auth/login",
        json={"login": "admin_a", "password": "AdminA123!"},
    )
    assert resp.status_code == 429, resp.text
    assert "Retry-After" in resp.headers


async def test_rate_limit_is_account_agnostic_per_ip(acq_env: AcqEnv):
    """Invariant (documented design): the window is keyed by IP, not by
    account — attacking five DIFFERENT accounts from one IP still exhausts
    the shared window.  This is the defense against spraying attacks."""
    usernames = ["admin_a", "admin_b", "staff_a", "teacher_a", "student_a"]
    for username in usernames:
        resp = await acq_env.client.post(
            "/auth/login",
            json={"login": username, "password": "Wrong!"},
        )
        assert resp.status_code == 401, resp.text

    # 6th attempt from the same IP → throttled regardless of account.
    resp = await acq_env.client.post(
        "/auth/login",
        json={"login": "admin_a", "password": "AdminA123!"},
    )
    assert resp.status_code == 429, resp.text


async def test_rate_limit_does_not_block_legitimate_single_login(
    acq_env: AcqEnv,
):
    """Positive control: a single legitimate login still succeeds."""
    from app.domains.auth.router import _login_limiter
    _login_limiter.reset()

    resp = await acq_env.client.post(
        "/auth/login",
        json={"login": "admin_a", "password": "Admin_A123!"},
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# RateLimiter unit semantics
# ---------------------------------------------------------------------------


def test_rate_limiter_sliding_window():
    from app.core.security.rate_limiter import RateLimiter

    limiter = RateLimiter()
    for _ in range(5):
        allowed, _ = limiter.check("login:ip", max_requests=5, window_seconds=60)
        assert allowed is True

    allowed, retry_after = limiter.check("login:ip", max_requests=5, window_seconds=60)
    assert allowed is False
    assert retry_after >= 1


def test_rate_limiter_reset_clears_window():
    from app.core.security.rate_limiter import RateLimiter

    limiter = RateLimiter()
    for _ in range(5):
        limiter.check("login:ip", max_requests=5, window_seconds=60)
    assert limiter.check("login:ip", max_requests=5, window_seconds=60)[0] is False

    limiter.reset()
    allowed, _ = limiter.check("login:ip", max_requests=5, window_seconds=60)
    assert allowed is True


def test_rate_limiter_instances_do_not_share_state():
    """Documented assumption: the in-memory limiter is per-process.  Two
    instances (two workers) do NOT share windows — production must swap in
    a shared (Redis) backend to enforce limits across instances."""
    from app.core.security.rate_limiter import RateLimiter

    limiter_a = RateLimiter()
    limiter_b = RateLimiter()
    for _ in range(5):
        limiter_a.check("login:ip", max_requests=5, window_seconds=60)

    # Instance B has an empty window — the A-side pressure is invisible.
    allowed, _ = limiter_b.check("login:ip", max_requests=5, window_seconds=60)
    assert allowed is True
    # Instance A is still exhausted.
    allowed, _ = limiter_a.check("login:ip", max_requests=5, window_seconds=60)
    assert allowed is False
