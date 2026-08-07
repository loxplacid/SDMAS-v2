"""SDMAS graph layer.

The graph is a derived, read-optimised index whose source of truth remains
PostgreSQL. See ``docs/GRAPH_LAYER.md`` for the architecture spec.

This package is intentionally a scaffold: ``graph_enabled=false`` by default
and no behaviour is wired into the API until the flag is flipped.
"""
