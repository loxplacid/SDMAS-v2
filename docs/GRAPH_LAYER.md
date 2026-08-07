# SDMAS - Graph Layer

This document describes the **intended** graph layer for SDMAS v2. It is a
design/architecture spec only. It does not (yet) describe shipped behaviour;
the live system continues to run on PostgreSQL + Redis as described in
[`ARCHITECTURE.md`](ARCHITECTURE.md).

## Status

| Item | State |
|---|---|
| Embedded engine (`networkx` on Postgres) | **default**, enabled `graph_enabled=false` |
| Native engine (Neo4j / Memgraph via Bolt) | Optional, behind a feature flag |
| SQL → graph sync | Via the existing transactional outbox |
| Implementation | Scaffolded as empty package `app/graph/` |

## Overview

SDMAS v2 is a multi-tenant school platform. Most of its entities — students,
teachers, parents, invoices, attendance, exams, library, bus, classroom,
certificates, medical and disciplinary records — share relationships that are
**naturally a graph** (parent-of, teacher-of, friend-of, borrowed, attended,
paid, assigned, transferred). This layer materialises that graph as a
**derived, read-optimised index** whose source of truth remains the existing
PostgreSQL databases.

The graph supports: shortest path, relationship discovery, community
detection, centrality, recommendations, duplicate detection, anomaly
detection, dependency analysis, influence analysis, impact analysis.

## Design principles

1. **PostgreSQL remains the source of truth.** No primary write path changes.
   The graph is a mirror/projection that can be rebuilt and thrown away.
2. **Structural tenancy is reused.** Every graph query is scoped the same
   default-deny way as `multi_tenant/repository.py`: an unscoped non-platform
   caller sees nothing; a scoped caller can never traverse a cross-campus
   edge. Leakage via shortest-path, community and live-vis is structurally
   impossible.
3. **The transactional outbox triggers sync.** The layer subscribes to the
   same `outbox_events` stream the worker already consumes. Exactly-once,
   derived, no dual-write.
4. **Backend-agnostic query surface.** Application code never talks to
   Cypher or SQL directly; it uses a small declarative graph DSL that the
   planner compiles to the active engine.
5. **Drop-in, feature-flagged.** `graph_enabled=false` by default. No new
   infra, no migration churn until the flag is flipped.

## Node / edge model

A graph is a set of `(node, edge)` pairs. Node ids are the entity's existing
primary key — the graph does not introduce a second identity space.

### Nodes (labels)

| Label | Source table | Campus column | Notable properties |
|---|---|---|---|
| `STUDENT` | student | campus_id | class_id, grade, admission_date |
| `TEACHER` | teacher | campus_id | subject, class_id |
| `PARENT` | parent | campus_id | contact |
| `INVOICE` | invoice | campus_id | amount (minor units), status |
| `ATTENDANCE` | attendance | campus_id | date, status, class_id |
| `EXAM` | academic.exam | campus_id | subject, max_marks |
| `LIBRARY_ASSET` | library | campus_id | type, category |
| `BUS_ROUTE` | transport | campus_id | stops[] |
| `CLASSROOM` | institution | campus_id | room, class_level |
| `CERTIFICATE` | documents | campus_id | type, issued_date |
| `MEDICAL_RECORD` | medical | campus_id | record_type, date |
| `DISCIPLINARY_EVENT` | disciplinary | campus_id | severity |

Every node carries `tenant_id`, `campus_id`, `created_at`, `updated_at`,
`version`, and an `active` tombstone so historical edges survive soft
deletes.

### Edges (relationship types)

Edge types are directional. Properties always include `weight` (normalised
0–1 for graph algorithms), optional `from`/`to` (temporal bounds) and
`props` (free-form jsonb).

| Edge | from → to | Properties | Weight basis |
|---|---|---|---|
| `PARENT_OF` | PARENT → STUDENT | — | fixed |
| `TEACHES` | TEACHER → STUDENT | subject | fixed |
| `ASSIGNED_TO` | TEACHER → CLASSROOM | role | fixed |
| `ENROLLED_IN` | STUDENT → CLASSROOM | year, section | fixed |
| `FRIEND_OF` *(derived)* | STUDENT → STUDENT | strength | similarity |
| `BORROWED` | STUDENT → LIBRARY_ASSET | due_date, returned | overdue penalty |
| `ATTENDED` | ATTENDANCE → STUDENT | date, status | binary |
| `PAID` | PAYMENT → INVOICE | date | amount |
| `TOOK` | STUDENT → EXAM | subject | score / max |
| `TRANSFERRED` | STUDENT → CLASSROOM | from, to | fixed |
| `ISSUED` | CERTIFICATE → STUDENT | type | fixed |
| `HAS_RECORD` | MEDICAL_RECORD → STUDENT | type | fixed |
| `SUBJECT_OF` | DISCIPLINARY_EVENT → STUDENT | severity | severity |
| `ENFORCED` | TEACHER → DISCIPLINARY_EVENT | — | fixed |

`FRIEND_OF` is the only **derived** edge: built from co-enrollment /
co-attendance, refreshed by a scheduled projection job rather than stored
in the source system.

---

## Architecture layout

```
Graph API        (HTTP /api/graph/*  +  WS /api/graph/live)
   │
Graph Query Orchestrator     planner → tenancy scoping → guard → cache
   │
Graph Abstraction            model, registry, projections, property registry
   │
Storage Adapter             EmbeddedGraphStore (default) · NativeGraphStore
   │
Graph Sync                  outbox ingest → incremental appliers → rewind
   │
PostgreSQL (source of truth)
```

New package: `apps/api/app/graph/` — the only allowed import surface is
`from app.graph import ...`. It is organised as:

```
graph/
  abstraction/     model, registry, projections, edge_props
  storage/         storage, embedded, native, cache
  ingestion/       appliers, outbox_handlers, rewind, snapshots
  query/           planner, compiler, executor, scoping
  analysis/        pathfinding, centrality, community, recommendation,
                   dedupe, anomaly, dependency, influence, impact
  viz/             api, exporters
  plugins/         loader, base
  tenancy/         scoping, guards
  router.py  service.py  events.py  config.py
```

## Storage layer

Narrow interface, swappable backend:

- `upsert_nodes(records)`, `upsert_edges(edge)` — idempotent, `MERGE`.
- `delete_node/edge(node/ref)` — tombstone-aware.
- `transaction(callback)`.
- `run(plan)` — execute a compiled plan (section "Query & planner").
- `analyze(algorithm, subgraph)` — run an analysis engine.

Two implementations:

- **EmbeddedGraphStore (default)** — in-memory `networkx.MultiDiGraph`
  loaded from a Postgres adjacency projection per campus, refreshed from a
  warm process cache. No new infrastructure. Best for a single campus
  subgraph (<~50k nodes) and for analysis that naturally runs in-memory.
- **NativeGraphStore (optional, flagged)** — speaks Bolt to Neo4j /
  Memgraph. Used when cross-campus hop counts scale beyond embedded
  comfort. Same interface, only the store bean changes via
  `settings.graph.engine`.

### Postgres adjacency projection (embedded)

Kept so provenance/replay are SQL-native and the embedded graph can be
rebuilt:

- `graph_nodes(label, node_id, campus_id, version, active, props jsonb)`
  PK `(label, node_id)`.
- `graph_edges(type, src_label, src_id, dst_label, dst_id, props jsonb,
  campus_id)` — indexed on `(campus_id)` and `(campus_id, src_label,
  src_id)`.
- `graph_watermark(bucket_key PK, last_watermark bigint)` — incremental
  replay cursor.

In native mode these tables are not used.

## Synchronization with PostgreSQL

### Trigger path

```
SQL mutation commits + graph event (same atomic Postgres txn)
   → OutboxWorker delivers event
   → GraphIngestor applier (idempotent) → node/edge upsert
   → graph cache invalidation for affected plan keys
```

Appliers are pure `(entity, event_type) → projection update` functions, so
watermark replay produces identical graphs whether run live or during
a repair rewind.

### Incremental sync

- Soft deletes become tombstones (edges preserved for history).
- Derived edges (`FRIEND_OF`) are recomputed by a scheduled projection job,
  tracked by a separate derived watermark.
- Each applier updates the per-bucket watermark in the same Postgres
  transaction (embedded mode), making crash-restarts safe: a partially
  committed batch is redriven from the watermark.

### Rewind / rebuild repair

`POST /api/graph/admin/rewind?from_version=N` (platform) replays the outbox
from watermark `N` to rebuild state — the graph analogue of
`alembic upgrade head`. Also run automatically at startup if the outbox has
advanced past the graph watermark.

## Query & planner

Declarative surface DSL, helpers compiled to the active engine:

- Traversal: `neighbors(node, type, depth)`, `path(u, v, via, max_hops)`.
- Analysis: `community(subgraph)`, `centrality(metric, top)`, etc.

Planner pipeline:

1. Parse AST; validate labels/types.
2. Inject tenancy bound from `TenantContext`; reject unscoped non-platform
   (default-deny); assert cross-campus edges cannot be crossed for scoped
   callers.
3. Choose plan (shortest-path A*/Dijkstra vs degree/betweenness; prune by
   weight thresholds).
4. Cache lookup (plan key = `(tenant, ast, version)`).
5. Compile to engine (Cypher or SQL-adjacent) or run in-memory.
6. Execute, scope-guard results, serialize, audit materialisations.

## Analysis engine

Every unit works uniformly through the storage abstraction.

| Requirement | Method | Use case |
|---|---|---|
| Shortest path | A*/Dijkstra | influence chain from a risk flag to its root |
| Relationship discovery | pattern traversal | who is in a danger's circle |
| Community detection | Louvain / label-propagation | peer clusters → tutoring, group analytics |
| Centrality | degree / betweenness / PageRank | influential students & bridging teachers |
| Recommendations | personalisation / co-enrollment affinity | study-group & peer matching |
| Duplicate detection | candidate resolution (label+props hashing) | duplicate admissions / parents |
| Anomaly detection | degree & edge-weight outlier scoring | attendance spikes, overdue borrow |
| Dependency analysis | DAG / topological sort over lesson→exam→cert | promotion-block insight |
| Influence analysis | PageRank / propagation | who drives a behaviour cluster |
| Impact analysis | k-operation cascade trace | "if this class is cancelled…" |

Recurring results (community, centrality) are cached per
(tenant, plan, version).

## Caching

- **Plan/result cache (Redis, existing dependency):** for analytics-heavy
  keys, TTL-pruned, keyed by `(tenant, plan_hash, version)`.
- **In-process graph (embedded):** campus-scoped `networkx` subgraph kept
  warm; copy-on-write updates so reads are never blocked; concurrency behind
  `asyncio`; invalidated on `GRAPH_MUTATED` and by watermark drift.
- **Invalidation granularity:** node-scoped (`student_360`) rather than
  whole-cache; each node bump invalidates only affected plan keys.

## Visualization API

Tenancy-guarded, behind the same permission model as webhooks/export.

- `GET /api/graph/{campus}/node/{id}/visualization?depth=2`
- `POST /api/graph/query`
- `GET /api/graph/{campus}/overview?metric=community|degree`
- `WS /api/graph/live?campus=…` pushes `GRAPH_MUTATED` frames.
- Exporters: `graphml`, `dot`, `json` (force-graph) for the React/mobile
  clients. All gated by `export` permission.

## Plugins

- Minimal `GraphPlugin` hook points: `on_node_upserted`, `on_edge_upserted`,
  `on_snapshot`, `on_query`, plus `register_analysis(name)`.
- Plugins are enabled only via `settings.graph.plugins`; are loaded off disk,
  never default-on.
- A plugin hook failure marks the plugin "degraded" but does not abort
  ingestion; edges produced by plugins reuse the same tenancy + tombstone
  machinery and can never escape scoping guards.

## Concurrency, config, rollback

New optional deps: `networkx` and (optional native) `neo4j` / driver, both in
the `graph` extras group — the primary install path is unchanged. New
`GraphSettings` group in `app/config.py`:

- `graph_enabled` (default `false`)
- `graph.engine` (`embedded` default | `native`)
- `graph.uri`, `graph.user`, `graph.password` (native)
- `graph.cache_ttl`, `graph.rewind_lookback`, `graph.plugins`

Enabling path (reversible):

1. Ship code, `graph_enabled=false` (no code-path behaviour change).
2. Flip `embedded`: new migration adds adjacency tables and outbox
   handlers subscribed; rewind populates the index.
3. Optional: flip `engine=native` — same app, different store.

## Testing

- Unit tests (in-memory fake engine) for every analyzer and each applier.
- A `test_graph/test_tenancy_security_suite.py` styled on the existing
  **multi-tenant security suite** proving cross-campus leakage is impossible
  through graph queries, shortest-path, community, and live WebSocket frames.
- Rewind replays tested against a deterministic outbox feed (exactly-once
  on crash).

## Related docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — canonical system (the graph is an
  addition to this).
- [`TENANCY.md`](TENANCY.md) — the tenancy/scoping model this layer mirrors.
- [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) — the layer ships
  `graph_enabled=false` until the adjacency tables and outbox handlers are
  verified in an integration environment.