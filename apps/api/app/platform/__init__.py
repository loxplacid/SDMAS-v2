"""Platform-level primitives shared across domains.

``app.platform`` is the dependency-free layer that domains may import for
cross-cutting contracts (event envelopes, identity, integrity).  It must
never import ``app.domains`` — domains depend on platform, never the reverse.
"""
