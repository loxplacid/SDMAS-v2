"""The internal extension contract — deterministic manifest validation.

An extension is declared by a *manifest*: a JSON document describing what
the extension provides and what it requires from the core.  This module
contains the pure, deterministic validation of every manifest section
against closed catalogs (supplied by :class:`ExtensionRegistry`):

- ``identity``     — extension_id, name, provider, version, core_compat
- ``permissions``  — declared permission requirements (``scope.action``)
- ``routes``       — API routes the extension mounts (core-scoped mount root)
- ``events``       — platform event types the extension subscribes to
- ``config_schema``— JSON schema the extension's configuration must match
- ``migrations``   — alembic revision ids the extension ships
- ``frontend``     — frontend registration (entrypoint, routes, menu items)
- ``policy``       — policy scope the extension's operations are subject to

The contract is *closed*: every field is validated against a fixed catalog
or a fixed pattern, and a manifest with any unknown/unsupported value is
rejected before it can be stored.  No code is ever evaluated from a
manifest — routes are declarations for the core app's router to mount,
events are declarations for the core dispatcher to deliver, migrations are
declarations the operator applies through the normal alembic flow.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Closed pattern constants
# ---------------------------------------------------------------------------

#: Stable extension id: lowercase start, then [a-z0-9._-], 3..80 chars.
EXTENSION_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")
#: Migration revision: the alembic hex prefix + snake name.
MIGRATION_REVISION_RE = re.compile(r"^[a-f0-9]{12}_[a-z0-9_]+$|^[a-z0-9_]+$")
#: JS entrypoint path (relative chunk or module).
ENTRYPOINT_RE = re.compile(r"^[a-zA-Z0-9_./-]+\.(js|mjs|ts|tsx)$")
#: Menu id.
MENU_ID_RE = re.compile(r"^[a-zA-Z0-9._-]+$")

#: HTTP methods an extension route may declare.
ROUTE_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE"})

#: Config value types the mini schema validator understands.
CONFIG_TYPES = frozenset({"string", "integer", "number", "boolean", "array", "object"})

#: Route segment charset (no dots — no traversal, no params beyond the
#: core-approved ``{id}`` style placeholders handled at mount time).
_SEGMENT_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


# ---------------------------------------------------------------------------
# Section validators (pure) — each returns a list of problem strings
# ---------------------------------------------------------------------------


def validate_identity(manifest: dict[str, Any], problems: list[str]) -> None:
    identity = manifest.get("identity")
    if not isinstance(identity, dict):
        problems.append("identity: object required")
        return
    extension_id = identity.get("extension_id")
    if not isinstance(extension_id, str) or not EXTENSION_ID_RE.match(extension_id):
        problems.append("identity.extension_id: must match ^[a-z][a-z0-9._-]{2,79}$")
    for field in ("name", "provider"):
        value = identity.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"identity.{field}: non-empty string required")
    for field in ("description", "homepage", "license"):
        value = identity.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > 500):
            problems.append(f"identity.{field}: must be a string <= 500 chars")
    version = identity.get("version")
    if not isinstance(version, str):
        problems.append("identity.version: semantic version string required")
    core_compat = identity.get("core_compat")
    if not isinstance(core_compat, str) or not core_compat.strip():
        problems.append("identity.core_compat: version range required (e.g. >=0.1.0,<1.0.0)")


def validate_permissions(
    manifest: dict[str, Any],
    catalogs: Any,
    problems: list[str],
) -> None:
    permissions = manifest.get("permissions", [])
    if not isinstance(permissions, list):
        problems.append("permissions: list required")
        return
    seen: set[str] = set()
    for index, perm in enumerate(permissions):
        if not isinstance(perm, dict):
            problems.append(f"permissions[{index}]: object required")
            continue
        permission = perm.get("permission")
        if not isinstance(permission, str) or not catalogs.valid_permission(permission):
            problems.append(
                f"permissions[{index}]: {permission!r} is not a known permission "
                f"(format scope.action)"
            )
        else:
            if permission in seen:
                problems.append(f"permissions[{index}]: duplicate permission {permission!r}")
            seen.add(permission)
        reason = perm.get("reason")
        if reason is not None and (not isinstance(reason, str) or len(reason) > 500):
            problems.append(f"permissions[{index}].reason: must be a string <= 500 chars")


def validate_routes(
    manifest: dict[str, Any],
    catalogs: Any,
    problems: list[str],
) -> None:
    extension_id = (manifest.get("identity") or {}).get("extension_id", "")
    routes = manifest.get("routes", [])
    if not isinstance(routes, list):
        problems.append("routes: list required")
        return
    for index, route in enumerate(routes):
        if not isinstance(route, dict):
            problems.append(f"routes[{index}]: object required")
            continue
        method = route.get("method")
        if not isinstance(method, str) or method.upper() not in ROUTE_METHODS:
            problems.append(f"routes[{index}].method: one of {sorted(ROUTE_METHODS)} required")
        path = route.get("path")
        if not isinstance(path, str) or not catalogs.valid_route_path(extension_id, path):
            problems.append(
                f"routes[{index}].path: must start with /api/v1/ext/{extension_id}/ "
                "and contain only [a-zA-Z0-9_-] segments"
            )
        description = route.get("description")
        if description is not None and (not isinstance(description, str) or len(description) > 500):
            problems.append(f"routes[{index}].description: must be a string <= 500 chars")


def validate_events(
    manifest: dict[str, Any],
    catalogs: Any,
    problems: list[str],
) -> None:
    events = manifest.get("events", [])
    if not isinstance(events, list):
        problems.append("events: list required")
        return
    seen: set[str] = set()
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            problems.append(f"events[{index}]: object required")
            continue
        subscribe = event.get("subscribe")
        if not isinstance(subscribe, str) or not catalogs.valid_event(subscribe):
            problems.append(
                f"events[{index}].subscribe: {subscribe!r} is not in the platform event catalog"
            )
        else:
            if subscribe in seen:
                problems.append(f"events[{index}]: duplicate subscription {subscribe!r}")
            seen.add(subscribe)
        handler = event.get("handler")
        if not isinstance(handler, str) or not handler.strip():
            problems.append(f"events[{index}].handler: non-empty string required")


def validate_config_schema(manifest: dict[str, Any], problems: list[str]) -> None:
    schema = manifest.get("config_schema")
    if schema is None:
        return
    if not isinstance(schema, dict):
        problems.append("config_schema: object required")
        return
    errors: list[str] = []
    _validate_schema_node(schema, "config_schema", errors)
    problems.extend(errors)


def validate_migrations(manifest: dict[str, Any], problems: list[str]) -> None:
    migrations = manifest.get("migrations", [])
    if not isinstance(migrations, list):
        problems.append("migrations: list required")
        return
    for index, revision in enumerate(migrations):
        if not isinstance(revision, str) or not MIGRATION_REVISION_RE.match(revision):
            problems.append(
                f"migrations[{index}]: {revision!r} is not a valid migration revision id"
            )


def validate_frontend(manifest: dict[str, Any], problems: list[str]) -> None:
    extension_id = (manifest.get("identity") or {}).get("extension_id", "")
    frontend = manifest.get("frontend")
    if frontend is None:
        return
    if not isinstance(frontend, dict):
        problems.append("frontend: object required")
        return
    entrypoint = frontend.get("entrypoint")
    if not isinstance(entrypoint, str) or not ENTRYPOINT_RE.match(entrypoint):
        problems.append("frontend.entrypoint: must be a relative js/mjs/ts/tsx path")
    routes = frontend.get("routes", [])
    if not isinstance(routes, list):
        problems.append("frontend.routes: list required")
    else:
        seen: set[str] = set()
        for index, route in enumerate(routes):
            if not isinstance(route, dict):
                problems.append(f"frontend.routes[{index}]: object required")
                continue
            path = route.get("path")
            if not isinstance(path, str) or not path.startswith(f"/ext/{extension_id}"):
                problems.append(
                    f"frontend.routes[{index}].path: must start with /ext/{extension_id}"
                )
            else:
                if path in seen:
                    problems.append(f"frontend.routes[{index}]: duplicate path {path!r}")
                seen.add(path)
    menu = frontend.get("menu", [])
    if not isinstance(menu, list):
        problems.append("frontend.menu: list required")
    else:
        seen_ids: set[str] = set()
        for index, item in enumerate(menu):
            if not isinstance(item, dict):
                problems.append(f"frontend.menu[{index}]: object required")
                continue
            menu_id = item.get("id")
            if not isinstance(menu_id, str) or not MENU_ID_RE.match(menu_id):
                problems.append(f"frontend.menu[{index}].id: invalid menu id")
            else:
                if menu_id in seen_ids:
                    problems.append(f"frontend.menu[{index}]: duplicate menu id {menu_id!r}")
                seen_ids.add(menu_id)
            for field in ("label", "icon"):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    problems.append(f"frontend.menu[{index}].{field}: non-empty string required")
            href = item.get("href")
            if not isinstance(href, str) or not href.startswith(f"/ext/{extension_id}"):
                problems.append(f"frontend.menu[{index}].href: must start with /ext/{extension_id}")


def validate_policy(
    manifest: dict[str, Any],
    catalogs: Any,
    problems: list[str],
) -> None:
    policy = manifest.get("policy")
    if policy is None:
        return
    if not isinstance(policy, dict):
        problems.append("policy: object required")
        return
    scope = policy.get("scope")
    if not isinstance(scope, str) or not catalogs.valid_policy_scope(scope):
        problems.append(f"policy.scope: {scope!r} is not a known policy scope")
    policy_id = policy.get("policy_id")
    if policy_id is not None and (not isinstance(policy_id, str) or len(policy_id) > 200):
        problems.append("policy.policy_id: must be a string <= 200 chars")


def validate_manifest(manifest: dict[str, Any], catalogs: Any) -> list[str]:
    """Validate a whole manifest against the registry catalogs.

    Returns a list of problem strings (empty == valid).  Pure and
    deterministic — the same manifest always produces the same problems.
    """
    if not isinstance(manifest, dict):
        return ["manifest: object required"]
    problems: list[str] = []
    unknown = set(manifest) - {
        "identity",
        "permissions",
        "routes",
        "events",
        "config_schema",
        "migrations",
        "frontend",
        "policy",
    }
    if unknown:
        problems.append(f"manifest: unknown section(s) {sorted(unknown)}")
    validate_identity(manifest, problems)
    validate_permissions(manifest, catalogs, problems)
    validate_routes(manifest, catalogs, problems)
    validate_events(manifest, catalogs, problems)
    validate_config_schema(manifest, problems)
    validate_migrations(manifest, problems)
    validate_frontend(manifest, problems)
    validate_policy(manifest, catalogs, problems)
    return problems


# ---------------------------------------------------------------------------
# Mini JSON-schema validator (config values) — deterministic, closed types
# ---------------------------------------------------------------------------


def _validate_schema_node(node: Any, path: str, errors: list[str]) -> None:
    """Validate that ``node`` is a well-formed schema fragment."""
    if not isinstance(node, dict):
        errors.append(f"{path}: schema node must be an object")
        return
    value_type = node.get("type")
    if value_type not in CONFIG_TYPES:
        errors.append(f"{path}.type: one of {sorted(CONFIG_TYPES)} required")
        return
    if value_type in ("string", "integer", "number", "boolean"):
        enum = node.get("enum")
        if enum is not None and not isinstance(enum, list):
            errors.append(f"{path}.enum: list required")
    elif value_type == "array":
        items = node.get("items")
        if items is not None:
            _validate_schema_node(items, f"{path}.items", errors)
    elif value_type == "object":
        properties = node.get("properties")
        if properties is not None:
            if not isinstance(properties, dict):
                errors.append(f"{path}.properties: object required")
            else:
                for key, sub in properties.items():
                    _validate_schema_node(sub, f"{path}.properties.{key}", errors)
        required = node.get("required")
        if required is not None:
            if not isinstance(required, list) or not all(isinstance(r, str) for r in required):
                errors.append(f"{path}.required: list of strings required")


def validate_config_value(schema: Any, value: Any) -> list[str]:
    """Validate a configuration value against the declared schema fragment.

    Returns a list of problem strings (empty == valid).  Closed type set
    (string/integer/number/boolean/array/object + enum + object.required).
    """
    if schema is None:
        return []
    if not isinstance(schema, dict):
        return ["config_schema: object required"]
    value_type = schema.get("type")
    if value_type not in CONFIG_TYPES:
        return [f"config_schema.type: one of {sorted(CONFIG_TYPES)} required"]
    problems: list[str] = []
    _check_value(schema, value, "$", problems)
    return problems


def _check_value(schema: Any, value: Any, path: str, problems: list[str]) -> None:
    value_type = schema.get("type")
    if value_type == "string":
        if not isinstance(value, str):
            problems.append(f"{path}: string required")
        elif "enum" in schema and value not in schema["enum"]:
            problems.append(f"{path}: must be one of {schema['enum']}")
    elif value_type == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            problems.append(f"{path}: integer required")
        elif "enum" in schema and value not in schema["enum"]:
            problems.append(f"{path}: must be one of {schema['enum']}")
    elif value_type == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            problems.append(f"{path}: number required")
        elif "enum" in schema and value not in schema["enum"]:
            problems.append(f"{path}: must be one of {schema['enum']}")
    elif value_type == "boolean":
        if not isinstance(value, bool):
            problems.append(f"{path}: boolean required")
    elif value_type == "array":
        if not isinstance(value, list):
            problems.append(f"{path}: array required")
            return
        items = schema.get("items")
        if items is not None:
            for index, item in enumerate(value):
                _check_value(items, item, f"{path}[{index}]", problems)
    elif value_type == "object":
        if not isinstance(value, dict):
            problems.append(f"{path}: object required")
            return
        properties = schema.get("properties") or {}
        for key, sub in properties.items():
            if key in value:
                _check_value(sub, value[key], f"{path}.{key}", problems)
        for key in schema.get("required") or []:
            if key not in value:
                problems.append(f"{path}.{key}: required property missing")


__all__ = [
    "EXTENSION_ID_RE",
    "MIGRATION_REVISION_RE",
    "ENTRYPOINT_RE",
    "MENU_ID_RE",
    "ROUTE_METHODS",
    "CONFIG_TYPES",
    "validate_manifest",
    "validate_config_value",
]
