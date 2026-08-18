"""Architectural boundary tests (static import-graph checks).

These tests enforce the domain dependency direction documented in
``docs/architecture/DOMAIN_CONTRACTS.md``:

* Router → Application Service → Domain Logic → Repository / Infrastructure
* Domain → shared platform primitives (audit, auth, events, jobs, multi_tenant,
  infrastructure)
* A domain must never import another domain's **router** (the HTTP surface of
  another domain) — that would make the dependency graph cyclic at the
  boundary and couple one domain's presentation layer to another's.
* Infrastructure must never import from ``app.domains`` (layering violation).
* Cross-domain import cycles must not grow beyond the documented allowlist.

They parse source with ``ast`` only — no imports of application code are
performed, so they are fast and safe to run anywhere.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
DOMAINS_DIR = APP_ROOT / "domains"

DOMAIN_RE = re.compile(r"^app\.domains\.([a-z0-9_]+)")


def _iter_py_files(root: Path):
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _module_for(path: Path) -> str:
    parts = path.relative_to(APP_ROOT).with_suffix("").parts
    return "app." + ".".join(parts)


def _imported_modules(path: Path) -> set[str]:
    """Module-level imported module names for *path* (no function-level)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name)
    return modules


def _top_domain(module: str) -> str | None:
    m = DOMAIN_RE.match(module)
    return m.group(1) if m else None


def _cross_domain_edges() -> dict[str, set[str]]:
    """file path -> set of (other) domains imported at module level."""
    edges: dict[str, set[str]] = {}
    for path in _iter_py_files(DOMAINS_DIR):
        mine = _module_for(path).split(".")[2]
        for module in _imported_modules(path):
            other = _top_domain(module)
            if other and other != mine:
                edges.setdefault(str(path), set()).add(other)
    return edges


def _domain_cycles() -> set[frozenset[str]]:
    """Set of domain pairs that import each other (undirected cycles)."""
    by_domain: dict[str, set[str]] = {}
    for _, others in _cross_domain_edges().items():
        pass  # handled below — need per-domain view
    for path, others in _cross_domain_edges().items():
        mine = _module_for(Path(path)).split(".")[2]
        by_domain.setdefault(mine, set()).update(others)
    cycles: set[frozenset[str]] = set()
    for a, others in by_domain.items():
        for b in others:
            if b in by_domain and a in by_domain[b] and a < b:
                cycles.add(frozenset({a, b}))
    return cycles


# Known, documented domain-level cycles.  These are tolerated by Python's
# import machinery (the app boots) but should not grow.  Each is explained
# in docs/architecture/DOMAIN_CONTRACTS.md §3.2.  ``billing-jobs`` was
# removed when JSONType moved to app/infrastructure/types.py.
KNOWN_CYCLES: set[frozenset[str]] = {
    frozenset({"audit", "auth"}),
    frozenset({"audit", "events"}),
    frozenset({"auth", "institution"}),
    frozenset({"cases", "risk"}),
    frozenset({"cases", "school_finance"}),
    frozenset({"fees", "school_finance"}),
}


def test_no_cross_domain_router_imports() -> None:
    """A domain must never import another domain's router (HTTP surface)."""
    offenders: list[str] = []
    for path, others in _cross_domain_edges().items():
        for module in _imported_modules(Path(path)):
            if module.startswith("app.domains.") and (
                module.endswith(".router") or ".router." in module
            ):
                mine = _module_for(Path(path)).split(".")[2]
                other = module.split(".")[2]
                if other != mine:
                    offenders.append(f"{path} -> {module}")
    assert not offenders, (
        "Domain boundary violation: a domain imports another domain's router "
        "(HTTP surface must stay at the top of the dependency graph):\n" + "\n".join(offenders)
    )


#: Deliberate exception: ``infrastructure/models.py`` is the model-aggregation
#: hub that registers every domain table on ``Base.metadata`` for the worker /
#: migration-init / Alembic entrypoints (see its module docstring).  It imports
#: models for their side effect only — no domain logic.  Any *other*
#: infrastructure -> domain import is a layering violation.
INFRA_MODEL_HUB = Path("app/infrastructure/models.py")


def test_no_infrastructure_domain_imports() -> None:
    """Infrastructure must never import application domains (layering).

    Sole exception: ``app/infrastructure/models.py`` (model-registration hub,
    side-effect imports only — documented in its module docstring).
    """
    offenders: list[str] = []
    for path in _iter_py_files(APP_ROOT / "infrastructure"):
        if str(path).replace("\\", "/").endswith("app/infrastructure/models.py"):
            continue
        for module in _imported_modules(path):
            if _top_domain(module) is not None:
                offenders.append(f"{path} -> {module}")
    assert not offenders, "Infrastructure -> domain import is a layering violation:\n" + "\n".join(
        offenders
    )


def test_cross_domain_cycles_do_not_grow() -> None:
    """The set of domain-level import cycles must not exceed the allowlist."""
    cycles = _domain_cycles()
    new_cycles = cycles - KNOWN_CYCLES
    assert not new_cycles, (
        "New cross-domain import cycle(s) detected — fix the dependency "
        "direction (see docs/architecture/DOMAIN_CONTRACTS.md) before adding "
        "to the allowlist:\n"
        + "\n".join(f"{sorted(c)[0]} <-> {sorted(c)[1]}" for c in sorted(new_cycles))
    )
    removed = KNOWN_CYCLES - cycles
    if removed:
        pytest.fail(
            "Cycle(s) in the allowlist no longer exist — update KNOWN_CYCLES "
            "to reflect the improvement:\n"
            + "\n".join(f"{sorted(c)[0]} <-> {sorted(c)[1]}" for c in sorted(removed))
        )


def test_cycle_allowlist_is_current() -> None:
    """Guard against a stale allowlist: every allowlisted pair must still be
    a real module-level cycle (a removed entry means the test above passes
    but the documentation may be stale)."""
    cycles = _domain_cycles()
    assert KNOWN_CYCLES == cycles, (
        "KNOWN_CYCLES does not match the actual cycle set. Actual: "
        + repr(sorted(tuple(sorted(c)) for c in cycles))
    )
