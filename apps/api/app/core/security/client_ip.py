"""Trusted-proxy-aware client IP / scheme resolution.

The API runs behind a reverse proxy (nginx) in production.  Naively using
``request.client.host`` returns the proxy's address, while blindly trusting
``X-Forwarded-For`` lets any direct client forge its IP and bypass
IP-keyed rate limiting and audit attribution.

This module resolves the *real* client IP with an explicit trusted-proxy
boundary:

* No ``X-Forwarded-For`` header  → the immediate peer is the client.
* ``X-Forwarded-For`` present AND the immediate peer is in the configured
  ``TRUSTED_PROXIES`` allowlist (IP or CIDR) → the chain is parsed
  right-to-left; the first address that is not itself a trusted proxy is
  the client.  A client can therefore never inject an address that wins
  over its own: nginx appends the real client IP to whatever the client
  sent, and that appended address is the one we return.
* ``X-Forwarded-For`` present but the immediate peer is NOT trusted →
  the header is ignored entirely (it may be spoofed) and the immediate
  peer is returned.

The same boundary governs ``X-Forwarded-Proto``.
"""

from __future__ import annotations

import ipaddress
import logging

from fastapi import Request

from app.config import settings

logger = logging.getLogger(__name__)


def _parse_ip(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    """Parse an IP literal, or ``None`` when it is not a bare IP."""
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _ip_matches(ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None, spec: str) -> bool:
    """True when *ip* falls inside the IP or CIDR *spec*."""
    if ip is None:
        return False
    spec = spec.strip()
    if not spec:
        return False
    if "/" in spec:
        try:
            return ip in ipaddress.ip_network(spec, strict=False)
        except ValueError:
            logger.debug("Ignoring malformed trusted-proxy CIDR %r", spec)
            return False
    try:
        return ip == ipaddress.ip_address(spec)
    except ValueError:
        logger.debug("Ignoring malformed trusted-proxy IP %r", spec)
        return False


def is_trusted_peer(peer_ip: str | None) -> bool:
    """True when *peer_ip* is one of the configured trusted proxies."""
    if not peer_ip:
        return False
    parsed = _parse_ip(peer_ip)
    if parsed is None:
        return False
    return any(_ip_matches(parsed, spec) for spec in settings.trusted_proxies)


def _client_from_xff(peer: str, xff: str) -> str:
    """Walk the X-Forwarded-For chain right-to-left, skipping trusted
    proxies, and return the first untrusted address."""
    chain = [part.strip() for part in xff.split(",") if part.strip()]
    if not chain:
        return peer

    for entry in reversed(chain):
        parsed = _parse_ip(entry)
        if parsed is None:
            # Hostname entry (non-standard / client-supplied).  It cannot
            # beat the real client IP that a trusted proxy appends to the
            # right of any client-supplied entries, so returning it is safe
            # in practice; treated as the client rather than a trusted hop.
            return entry
        if not any(_ip_matches(parsed, spec) for spec in settings.trusted_proxies):
            return entry

    # Every hop is a trusted proxy (e.g. proxy→proxy with no client entry
    # appended) — fall back to the leftmost address.
    return chain[0]


def get_client_ip(request: Request) -> str | None:
    """Return the real client IP address, honoring the trusted-proxy
    boundary.  ``None`` when the request has no peer (rare)."""
    peer = request.client.host if request.client else None
    if not peer:
        return None

    xff = request.headers.get("x-forwarded-for")
    if not xff or not is_trusted_peer(peer):
        return peer
    return _client_from_xff(peer, xff)


def get_client_scheme(request: Request) -> str:
    """Return the scheme as seen by the client (``https`` behind TLS
    termination), honoring the trusted-proxy boundary.

    ``X-Forwarded-Proto`` is only consulted when the immediate peer is a
    trusted proxy; otherwise the direct connection's scheme is used.
    """
    peer = request.client.host if request.client else None
    proto = request.headers.get("x-forwarded-proto")
    if proto and is_trusted_peer(peer):
        first = proto.split(",")[0].strip()
        if first:
            return first
    # Defensive: some code paths / test doubles expose a URL object without
    # a scheme attribute; scheme is best-effort request metadata.
    return getattr(request.url, "scheme", "http")
