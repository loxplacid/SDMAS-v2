"""Trusted-proxy client IP resolution tests.

Proves the trusted-proxy boundary:

* a direct (untrusted) client can never forge its IP via X-Forwarded-For;
* X-Forwarded-For is only honoured when the immediate peer is a trusted
  proxy (IP or CIDR);
* multi-hop trusted chains resolve to the first untrusted hop;
* X-Forwarded-Proto follows the same boundary.
"""

from __future__ import annotations

import pytest
from starlette.requests import Request

from app.config import settings
from app.core.security.client_ip import (
    _client_from_xff,
    get_client_ip,
    get_client_scheme,
    is_trusted_peer,
)


def _make_request(
    client_host: str | None,
    headers: dict[str, str] | None = None,
) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "root_path": "",
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in (headers or {}).items()
        ],
        "client": (client_host, 1234) if client_host else None,
        "server": ("testserver", 80),
    }
    return Request(scope)


@pytest.fixture
def trusted(monkeypatch):
    """Trust loopback + the docker-network CIDR."""
    monkeypatch.setattr(
        settings, "trusted_proxies", ["127.0.0.1", "172.16.0.0/12"]
    )


# ---------------------------------------------------------------------------
# is_trusted_peer
# ---------------------------------------------------------------------------


def test_trusted_peer_exact_ip(trusted):
    assert is_trusted_peer("127.0.0.1") is True
    assert is_trusted_peer("10.0.0.9") is False


def test_trusted_peer_cidr(trusted):
    assert is_trusted_peer("172.16.5.4") is True
    assert is_trusted_peer("172.31.255.255") is True
    assert is_trusted_peer("172.32.0.1") is False


def test_trusted_peer_malformed_spec(monkeypatch):
    monkeypatch.setattr(settings, "trusted_proxies", ["not-an-ip", "10.0.0.0/8"])
    assert is_trusted_peer("10.1.2.3") is True
    assert is_trusted_peer("127.0.0.1") is False


# ---------------------------------------------------------------------------
# get_client_ip — direct client (no proxy)
# ---------------------------------------------------------------------------


def test_direct_client_without_xff_uses_peer():
    req = _make_request("203.0.113.7")
    assert get_client_ip(req) == "203.0.113.7"


def test_direct_client_with_spoofed_xff_ignores_header():
    """An untrusted client sending X-Forwarded-For must NOT be able to
    change its rate-limit/audit key."""
    req = _make_request("203.0.113.7", {"X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req) == "203.0.113.7"


def test_no_client_returns_none():
    req = _make_request(None, {"X-Forwarded-For": "1.2.3.4"})
    assert get_client_ip(req) is None


# ---------------------------------------------------------------------------
# get_client_ip — trusted proxy in front
# ---------------------------------------------------------------------------


def test_trusted_proxy_real_client(trusted):
    """Peer is the trusted proxy; XFF carries the real client."""
    req = _make_request("172.16.0.10", {"X-Forwarded-For": "203.0.113.7"})
    assert get_client_ip(req) == "203.0.113.7"


def test_trusted_proxy_spoofed_chain(trusted):
    """Client tries to spoof XFF; nginx appends the real IP, which wins."""
    req = _make_request(
        "172.16.0.10",
        {"X-Forwarded-For": "1.2.3.4, 203.0.113.7"},
    )
    assert get_client_ip(req) == "203.0.113.7"


def test_trusted_proxy_multihop(trusted):
    """Two trusted proxies in front: 172.16.0.10 (lb) → 127.0.0.1 (nginx)."""
    req = _make_request(
        "127.0.0.1",
        {"X-Forwarded-For": "203.0.113.7, 172.16.0.10"},
    )
    assert get_client_ip(req) == "203.0.113.7"


def test_trusted_proxy_all_hops_trusted(trusted):
    """Every XFF entry is itself a trusted proxy → leftmost wins."""
    req = _make_request(
        "127.0.0.1",
        {"X-Forwarded-For": "172.16.0.10, 172.16.0.11"},
    )
    assert get_client_ip(req) == "172.16.0.10"


def test_client_from_xff_hostname_entry():
    """Non-IP entries are treated as the client (defensive)."""
    assert _client_from_xff("127.0.0.1", "edge.internal, 203.0.113.9") == "203.0.113.9"


# ---------------------------------------------------------------------------
# get_client_scheme
# ---------------------------------------------------------------------------


def test_scheme_direct_client_ignores_spoofed_proto():
    req = _make_request("203.0.113.7", {"X-Forwarded-Proto": "https"})
    assert get_client_scheme(req) == "http"


def test_scheme_trusted_proxy_honors_proto(trusted):
    req = _make_request("172.16.0.10", {"X-Forwarded-Proto": "https"})
    assert get_client_scheme(req) == "https"


def test_scheme_trusted_proxy_multivalue(trusted):
    req = _make_request("172.16.0.10", {"X-Forwarded-Proto": "https, http"})
    assert get_client_scheme(req) == "https"
