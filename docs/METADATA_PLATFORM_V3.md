# SDMAS Metadata Platform v3 — "The Forge"

> The ninth expansion of the Corridor. Codename: **The Forge**.
>
> **Scope:** the complete, production-grade architecture for transforming
> SDMAS from a hand-coded application into a **metadata-driven platform** —
> an engine that *generates* screens, forms, validation, permissions, tables,
> detail pages, search, reports, dashboard widgets, navigation, APIs,
> workflows, automations, and event subscriptions from **versioned metadata**
> instead of hand-written code.
>
> **This is an architecture document. No code is implemented here.**
>
> **Grounding in the real codebase:**
>
> | Reality | Evidence |
> |---|---|
> | Live backend | FastAPI + SQLAlchemy 2 async + Pydantic v2, 33 domains (`apps/api/app/domains/`) |
> | Live database | PostgreSQL 16 (docker-compose `postgres:16-alpine`) |
> | Live frontend | React 19 + Vite + PWA + TypeScript (`apps/web/`) |
> | Existing events | Domain-event catalog (`events/catalog.py`) + transactional outbox (`events/outbox.py`) — the substrate for metadata-driven automation |
> | Existing RBAC | `auth/permission_service.py`, role→permission resolution, tenant scoping (`multi_tenant`) |
> | Existing workflows | `domains/workflow/` (models, service, router) — the substrate for metadata-attached workflow definitions |
> | Legacy desktop lineage | `_archive/legacy-v1/` — Python `mysql_provider.py`, `sqlite_provider.py`, `repository_base.py`, `crud.py`, `configuration_loader` — a proven Python+MySQL desktop-era codebase |
>
> **The strategic requirement tension, resolved:** the request specifies
> *CustomTkinter + Python + MySQL*. The live platform is *React + FastAPI +
> PostgreSQL*. The Forge does not choose between these — it is a **pluggable
> renderer / storage architecture**: one metadata core, many surfaces.
>
> - **Renderer layer** — the same metadata renders a **CustomTkinter desktop
>   client** (Python 3.12, `customtkinter`, reviving the archived desktop
>   lineage) *and* the existing **React web client** (which becomes a
>   metadata-driven SPA). Both consume the same generated-API contract.
> - **Storage layer** — a repository abstraction with **MySQL** and
>   **PostgreSQL** adapters (and SQLite for single-machine dev), so the
>   metadata tables and generated entities run on either RDBMS.
>
> **Companion docs:** `DESIGN_SYSTEM_V3.md`, `TABLE_SYSTEM_V3.md`,
> `COMPONENT_LIBRARY_V3.md`, `TRANSFORMATION_ROADMAP_V3.md`, `ARCHITECTURE.md`,
> `SECURITY_POLICY.md`, `AUTHORIZATION.md`, `TENANCY.md`.

---

## 1. System architecture

### 1.1 The thesis — metadata is the source of truth

Today, a screen = a route + a component + an API + a validator + a permission
+ a nav entry — each written by hand, each drifting. In the Forge, **one
metadata document defines an entity, and eleven artifacts derive from it**:

```
   ┌──────────────────────────────────────────────────────────┐
   │                     ENTITY METADATA                       │
   │  name · fields · relations · validation · permissions ·   │
   │  layouts · widgets · actions · events · automation ·      │
   │  reports · commands                                       │
   └──────────────────────────────┬───────────────────────────┘
                                  │
                 ┌────────────────┼────────────────────┐
                 ▼                ▼                    ▼
        ┌──────────────┐  ┌──────────────┐   ┌────────────────┐
        │  METADATA     │  │  API ENGINE  │   │  RENDERER(S)    │
        │  REGISTRY     │  │ (generated   │   │  - CustomTkinter│
        │  (validated,  │  │  FastAPI     │   │  - React web    │
        │  versioned,   │  │  endpoints)  │   │  - (future:     │
        │  hot-reloaded)│  └──────┬───────┘   │   CLI/voice)    │
        └──────┬───────┘         │            └───────┬────────┘
               │                 ▼                    │
        ┌──────┴──────────────────────────────────────┴─────────┐
        │                  GENERATED ARTIFACTS                    │
        │  forms · CRUD · validation · permissions · tables ·     │
        │  detail pages · search · reports · dashboard widgets ·  │
        │  navigation · workflows · automations · events          │
        └─────────────────────────────────────────────────────────┘
```

### 1.2 The engine layers

| Layer | Responsibility | Tech |
|---|---|---|
| **L1 Metadata store** | Versioned entity/view/action/automation/report definitions | MySQL/PostgreSQL tables (or JSON files in dev), immutable by version |
| **L2 Registry & compiler** | Load, validate, compile metadata into an in-memory dependency graph; hot reload | Python 3.12, Pydantic v2 models as the *schema of schemas* |
| **L3 Domain core** | Generated CRUD services, validation engine, permission engine, search index | FastAPI + SQLAlchemy 2 async (reuses existing domain patterns) |
| **L4 API engine** | Generated REST endpoints per entity (list/get/create/update/delete/bulk/export) | FastAPI, OpenAPI derived from metadata |
| **L5 Event & workflow bus** | Metadata-declared events, subscriptions, workflows, automations | Existing `events/` outbox + `workflow/` engine, driven by metadata |
| **L6 Renderer contract** | Typed JSON "screen descriptors" that both clients render | JSON schema (the single UI contract) |
| **L7a Renderer — desktop** | CustomTkinter client, generated windows/forms/tables from L6 | Python + customtkinter + ttk treeviews |
| **L7b Renderer — web** | React SPA rendering the same L6 descriptors | React 19 (existing web app becomes a thin shell) |
| **L8 Storage adapters** | Repository abstraction over MySQL / PostgreSQL / SQLite | SQLAlchemy dialects, one adapter per engine |

### 1.3 The three non-negotiables

1. **Metadata is code.** It lives in the repo (or a metadata database), is
   reviewed, versioned, and migrated — never edited by an admin UI directly in
   production. A metadata change is a deployment event.
2. **Generated code is never hand-patched.** Hand-written code may *extend* a
   generated surface (a custom widget, a custom validator) through declared
   plugin points, but never inside the generated output. The generated layer is
   ephemeral; the metadata is the only durable artifact.
3. **Every artifact is derivable on demand.** Given entity metadata, the API
   engine and both renderers can produce 100% of a screen. If a screen needs
   hand-coding, that is a metadata gap, logged as a platform debt item.

---

## 2. Folder structure

```
sdmas-platform/
├── pyproject.toml                 # Python 3.12, platform packages
├── platform/
│   ├── __init__.py
│   ├── metadata/                  # L1–L2: metadata lifecycle
│   │   ├── models.py              #   Pydantic v2: EntityDef, FieldDef, ...
│   │   ├── registry.py            #   loads metadata from store, builds graph
│   │   ├── compiler.py            #   validates + compiles to runtime graph
│   │   ├── hotreload.py           #   file/db watcher → rebuild + notify
│   │   ├── versioning.py          #   versions, diffs, rollbacks
│   │   └── migrations.py          #   metadata→schema migrations
│   ├── storage/                   # L8: RDBMS adapters
│   │   ├── base.py                #   Repository, StorageAdapter ABC
│   │   ├── mysql.py               #   MySQL adapter
│   │   ├── postgres.py            #   PostgreSQL adapter
│   │   └── sqlite.py              #   SQLite adapter (dev/single-machine)
│   ├── engine/                    # L3: generated core
│   │   ├── crud.py                #   generic CRUD service (one per entity)
│   │   ├── validation.py          #   rule engine (metadata → validator)
│   │   ├── permissions.py         #   rule engine (metadata → permission)
│   │   ├── search.py              #   generated search (indexed fields)
│   │   ├── events.py              #   metadata event bus bridge
│   │   ├── workflow.py            #   metadata workflow attach
│   │   └── automation.py          #   metadata automations
│   ├── api/                       # L4: generated endpoints
│   │   ├── generate.py            #   router factory: entity → APIRouter
│   │   ├── openapi.py             #   derives OpenAPI from metadata
│   │   └── dependencies.py        #   auth/tenant context (reuses auth domain)
│   ├── render/                    # L6: the screen-descriptor contract
│   │   ├── descriptor.py          #   ScreenDescriptor, FormDescriptor, ...
│   │   ├── builder.py             #   metadata → descriptor (server-side)
│   │   └── schema.json            #   the JSON schema both clients implement
│   ├── desktop/                   # L7a: CustomTkinter renderer
│   │   ├── app.py                 #   main window, navigation
│   │   ├── screen.py              #   generic Screen (renders a descriptor)
│   │   ├── widgets/               #   field widgets (Text, Date, Select, ...)
│   │   ├── table.py               #   ttk.Treeview renderer (virtual scroll)
│   │   └── theme.py               #   customtkinter theme (maps DS v3 tokens)
│   ├── plugins/                   # plugin extensions
│   │   ├── loader.py              #   discover + register plugins
│   │   ├── hooks.py               #   hook point enum (pre_save, post_render, ...)
│   │   └── manifest.py            #   plugin manifest schema
│   └── cache/
│       ├── memory.py              #   registry/dependency-graph cache
│       └── invalidation.py        #   version-aware invalidation
├── apps/
│   ├── api/                       # EXISTING FastAPI app — becomes the engine host
│   │   └── app/
│   │       ├── domains/           #   33 existing domains (become "seed metadata")
│   │       └── platform/          #   mounts the platform engine
│   ├── web/                       # EXISTING React SPA — becomes a descriptor renderer
│   │   └── src/
│   │       └── platform/          #   renderer for L6 descriptors
│   └── desktop/                   # NEW CustomTkinter client
│       ├── main.py
│       └── (mirrors platform/desktop)
├── metadata/                      # the metadata source-of-truth (versioned)
│   ├── entities/                  #   student.yaml, fee.yaml, ...
│   ├── views/                     #   student-list.yaml, fee-form.yaml, ...
│   ├── actions/                   #   bulk-enroll.yaml, record-payment.yaml
│   ├── automations/               #   fee-due-reminder.yaml
│   ├── reports/                   #   monthly-collections.yaml
│   └── workflows/                 #   admission-flow.yaml
└── migrations/
    └── metadata/                  # versioned metadata migrations
```

The `metadata/` directory is the **schema of the business**. The existing
`apps/api/app/domains/*` code becomes the **seed**: each domain's models,
validators, permissions, and workflows are *reverse-engineered into metadata*
(one migration per domain), then the hand-written code is retired behind the
generated layer.

---

## 3. Database schema

The metadata lives in its own schema (`md_*` tables) on the same RDBMS as the
business data, so transactional integrity between metadata and entities is
guaranteed.

### 3.1 Metadata tables

```sql
-- One versioned definition per entity. Immutable rows.
CREATE TABLE md_entities (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,   -- or BIGSERIAL on PG
    slug          VARCHAR(120) NOT NULL UNIQUE,        -- 'student'
    display_name  VARCHAR(200) NOT NULL,
    description   TEXT NULL,
    table_name    VARCHAR(120) NOT NULL,               -- physical table
    schema_version INT NOT NULL DEFAULT 1,
    status        ENUM('draft','active','deprecated') NOT NULL DEFAULT 'draft',
    definition    JSON NOT NULL,                        -- full EntityDef (see §6)
    created_by    BIGINT NULL,
    created_at    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at    DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
        ON UPDATE CURRENT_TIMESTAMP(6)
);

-- One row per field of an entity (denormalized for querying/versions).
CREATE TABLE md_fields (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    entity_id     BIGINT NOT NULL REFERENCES md_entities(id),
    name          VARCHAR(120) NOT NULL,               -- 'first_name'
    field_type    VARCHAR(40) NOT NULL,                -- text|number|date|enum|relation|...
    required      BOOLEAN NOT NULL DEFAULT FALSE,
    unique_       BOOLEAN NOT NULL DEFAULT FALSE,
    indexed       BOOLEAN NOT NULL DEFAULT FALSE,
    searchable    BOOLEAN NOT NULL DEFAULT FALSE,
    default_value JSON NULL,
    validation    JSON NULL,                           -- rules, see §6.3
    ui            JSON NULL,                           -- widget hint, label, layout
    position      INT NOT NULL DEFAULT 0,
    UNIQUE KEY uq_entity_field (entity_id, name)
);

CREATE TABLE md_relations (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    entity_id     BIGINT NOT NULL REFERENCES md_entities(id),
    name          VARCHAR(120) NOT NULL,               -- 'enrollments'
    target_entity VARCHAR(120) NOT NULL,               -- 'enrollment'
    kind          ENUM('one_to_one','one_to_many','many_to_one','many_to_many') NOT NULL,
    foreign_key   VARCHAR(120) NULL,                   -- column on this/target
    join_table    VARCHAR(120) NULL,                   -- for many_to_many
    on_delete     ENUM('cascade','set_null','restrict') NOT NULL DEFAULT 'restrict',
    position      INT NOT NULL DEFAULT 0
);

-- Views: list/tabular screens (a view selects fields + filters + columns).
CREATE TABLE md_views (
    id            BIGINT PRIMARY KEY AUTO_INCREMENT,
    slug          VARCHAR(120) NOT NULL,
    entity_id     BIGINT NOT NULL REFERENCES md_entities(id),
    kind          ENUM('list','form','detail','dashboard','report') NOT NULL,
    definition    JSON NOT NULL,                        -- columns, filters, layout, widgets
    version       INT NOT NULL DEFAULT 1,
    status        ENUM('draft','active') NOT NULL DEFAULT 'active',
    UNIQUE KEY uq_view_slug (slug, version)
);

-- Permissions: rule strings evaluated against the actor context (§9).
CREATE TABLE md_permissions (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    scope       VARCHAR(40) NOT NULL,                   -- 'entity.student'
    action      VARCHAR(40) NOT NULL,                   -- 'create'|'read'|'update'|'delete'|'*'
    rule        TEXT NOT NULL,                          -- permission expression language
    description TEXT NULL
);

-- Actions: commands available on an entity/view.
CREATE TABLE md_actions (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    slug        VARCHAR(120) NOT NULL,
    entity_id   BIGINT NULL REFERENCES md_entities(id), -- NULL = global action
    view_id     BIGINT NULL REFERENCES md_views(id),
    label       VARCHAR(200) NOT NULL,
    kind        ENUM('builtin','custom','workflow','plugin') NOT NULL,
    definition  JSON NOT NULL,                          -- payload schema, target, plugin ref
    permission_rule TEXT NULL
);

-- Event subscriptions: "when EVENT, run ACTION / notify / sync".
CREATE TABLE md_event_subscriptions (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    event_type   VARCHAR(120) NOT NULL,                 -- 'payment.received'
    action_ref   VARCHAR(120) NOT NULL,                 -- md_actions.slug or handler
    mode         ENUM('sync','outbox','workflow') NOT NULL DEFAULT 'outbox',
    enabled      BOOLEAN NOT NULL DEFAULT TRUE,
    position     INT NOT NULL DEFAULT 0
);

-- Automations: scheduled/cron-triggered metadata actions.
CREATE TABLE md_automations (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    slug        VARCHAR(120) NOT NULL,
    schedule    VARCHAR(64) NOT NULL,                   -- cron expression
    action_ref  VARCHAR(120) NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at DATETIME(6) NULL
);

-- Reports: metadata report definitions (query + columns + charts).
CREATE TABLE md_reports (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    slug        VARCHAR(120) NOT NULL,
    entity_id   BIGINT NOT NULL REFERENCES md_entities(id),
    definition  JSON NOT NULL,                          -- aggregations, group-by, filters, chart
    version     INT NOT NULL DEFAULT 1
);

-- Workflow definitions: states/transitions/guards (metadata-driven).
CREATE TABLE md_workflows (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    slug        VARCHAR(120) NOT NULL,
    entity_id   BIGINT NOT NULL REFERENCES md_entities(id),
    definition  JSON NOT NULL,                          -- states, events, transitions, guards
    version     INT NOT NULL DEFAULT 1
);

-- Plugin registry (extensions ship as pip-installed packages).
CREATE TABLE md_plugins (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(120) NOT NULL UNIQUE,
    version     VARCHAR(40) NOT NULL,
    entry_point  VARCHAR(200) NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    hooks       JSON NOT NULL
);
```

### 3.2 Versioning & migration

- **Immutability:** `md_entities` rows are append-only; editing an entity
  inserts a new row with `schema_version = N+1`. The active version is the
  max `schema_version` with `status='active'`.
- **Schema migration:** the compiler diffs the new metadata against the
  physical table and emits SQL DDL (add column, add index, change nullability)
  through the storage adapter — never destructive; additions first, then
  backfills, then constraints.
- **Backwards compatibility:** every API and renderer request carries the
  version of the metadata it was built for; the engine serves the
  `Accept-Version` the client understands. Old versions remain queryable for a
  grace window (configurable per entity).

### 3.3 Business data

Generated entities live in ordinary tables (e.g. `students`, `fees`) created
by metadata migrations — the same table shapes the existing SQLAlchemy models
produce. The repository adapters (§4) map CRUD to either dialect.

---

## 4. Class hierarchy

```
platform.metadata.models
  EntityDef        # Pydantic v2 — the schema of schemas
  FieldDef, RelationDef, ViewDef, ActionDef
  AutomationDef, ReportDef, WorkflowDef, EventSubscriptionDef
  PermissionRule

platform.metadata.registry
  MetadataRegistry          # loads + holds all definitions by version
    ├─ get_entity(slug, version) -> EntityDef
    ├─ get_view(slug, version)   -> ViewDef
    ├─ all_entities()            -> list[EntityDef]
    └─ subscribe(observer)       # hot-reload notification

platform.metadata.compiler
  MetadataCompiler            # validates + builds the runtime graph
    ├─ validate(EntityDef)            # cross-field checks, ref integrity
    ├─ compile_graph()                # entities → DependencyGraph
    └─ diff_schema(old, new) -> list[DDLOp]

platform.storage.base
  StorageAdapter (ABC)
    ├─ supports_dialect(dialect) -> bool
    ├─ create_table(ddl), add_column(op), ...
    └─ repository_factory(entity) -> Repository
  Repository (ABC)            # generated CRUD per entity
    ├─ list(filters, page, sort)
    ├─ get(id)
    ├─ create(data), update(id, data), delete(id)
    └─ count(filters)
  MySQLAdapter(StorageAdapter), PostgresAdapter(...), SQLiteAdapter(...)

platform.engine
  CrudService                 # generic service bound to (EntityDef, Repository)
  ValidationEngine            # metadata rules → validator callables
  PermissionEngine            # rule strings → bool(actor, resource, action)
  SearchIndex                 # generated search over searchable fields
  EventBridge                 # metadata subscription → outbox dispatch
  WorkflowEngine              # wraps existing workflow domain, metadata-driven
  AutomationScheduler         # cron → action dispatch

platform.api.generate
  EntityRouterFactory         # entity → FastAPI APIRouter (list/get/create/...)
  OpenApiBuilder              # metadata → OpenAPI schema

platform.render
  DescriptorBuilder           # EntityDef+ViewDef → ScreenDescriptor
  ScreenDescriptor            # the UI contract (see §7)
  FormDescriptor, TableDescriptor, DetailDescriptor, DashboardDescriptor

platform.desktop                # CustomTkinter renderer
  DesktopApp                   # main window + navigation (generated)
  Screen(descriptor)           # renders any ScreenDescriptor
  FieldWidgetFactory           # FieldDef+ui → widget instance
  ResultTable                  # virtual-scroll ttk.Treeview

apps/web/src/platform         # React renderer (same descriptor contract)
  useScreenDescriptor, ScreenRenderer, widgets/*

platform.plugins
  PluginLoader, HookPoint(Enum), PluginManifest
```

### 4.1 The two extension seams

1. **Plugin hooks** — `HookPoint` values (`pre_create`, `post_update`,
   `pre_render`, `after_commit`, `validate_field`, `custom_search`…). A plugin
   registers handlers against hook points; the engine calls them at the right
   moments. Metadata references plugins by manifest name (`kind='plugin'` in
   `md_actions`).
2. **Custom widgets/validators** — declared in metadata as
   `ui.widget = 'plugin:my-company/student-picker'`. The renderer resolves the
   plugin and instantiates it. Unknown widgets fail loudly at compile time,
   never at runtime.

---

## 5. Renderer design

### 5.1 The screen descriptor — one contract, two renderers

The engine never emits widgets — it emits a **ScreenDescriptor**: a typed JSON
document describing structure, fields, constraints, actions, and data bindings.
Both the CustomTkinter client and the React client render it. This is the key
to "the renderer must create the UI dynamically."

```jsonc
// example: the student form screen (descriptor served by the API)
{
  "schema": "screen/v1",
  "kind": "form",
  "entity": "student",
  "entityVersion": 12,
  "title": "Student",
  "sections": [
    {
      "id": "personal",
      "title": "Personal",
      "columns": 2,
      "fields": [
        {
          "name": "first_name",
          "type": "text",
          "label": "First name",
          "required": true,
          "max_length": 100,
          "widget": {"kind": "text", "autofocus": true}
        },
        {
          "name": "status",
          "type": "enum",
          "options": ["active", "inactive", "graduated", "transferred"],
          "widget": {"kind": "select"}
        }
      ]
    }
  ],
  "validation": [
    {"rule": "required_if", "field": "guardian_phone", "when": "status == 'active'"}
  ],
  "actions": [
    {"id": "save", "label": "Save", "kind": "submit", "permission": "student:update"},
    {"id": "cancel", "label": "Cancel", "kind": "dismiss"}
  ],
  "data": {"method": "POST", "url": "/api/g/student", "entityId": null}
}
```

**Renderer responsibilities (both clients):**
- walk the descriptor; instantiate a widget per field (mapping `field.type` +
  `widget.kind` to a concrete widget);
- enforce declarative validation client-side (instant feedback) while the
  server re-validates authoritatively;
- render actions with their permission gates;
- emit the exact payload shape the generated API expects.

### 5.2 CustomTkinter renderer specifics

- **Window = screen.** `DesktopApp` builds the navigation tree from the
  generated nav descriptor; each node opens a `Screen`.
- **Widget map** — `text → CTkEntry`, `textarea → CTkTextbox`, `number →
  CTkEntry+validation`, `date → CTkDatePicker` (custom, driven by a calendar
  popup), `enum → CTkOptionMenu`, `relation → searchable combo (CTkComboBox +
  autocomplete via the generated search API)`, `bool → CTkSwitch`.
- **Tables** — `ttk.Treeview` with column metadata, sortable headers, and a
  page-scroll lazy loader (or virtual scroll for large ledgers) hitting the
  generated list endpoint.
- **Theme** — a `customtkinter` theme mapping the DS v3 tokens (surface/ink/
  brand) so the desktop client is visually consistent with the web client.
- **Threading** — all API calls run on a worker thread (`concurrent.futures`);
  UI updates marshal back via `root.after()`. No blocking calls on the UI
  thread — this is the desktop equivalent of "no UI freezes."

### 5.3 React renderer specifics

The existing web app becomes a **thin shell** over descriptors: a generic
`ScreenRenderer` component + a widget library implementing the same contract.
This replaces per-page hand-coding over time (the Table System v3's
`DataTable` becomes the `list` widget). Page-specific React components are
retired as their views are converted to metadata.

---

## 6. Metadata specification

### 6.1 EntityDef (core)

```yaml
slug: student
display_name: Student
table_name: students
schema_version: 12
status: active
fields:
  - name: first_name
    type: text
    required: true
    max_length: 100
    searchable: true
    indexed: true
    ui: { label: First name, position: 10 }
  - name: status
    type: enum
    options: [active, inactive, graduated, transferred]
    default: active
    ui: { label: Status, widget: select }
  - name: guardian_id
    type: relation
    target: guardian
    relation_kind: many_to_one
    on_delete: restrict
relations:
  - name: enrollments
    target: enrollment
    kind: one_to_many
permissions:
  create: 'role in (admin, staff) and campus_match(actor, data)'
  read:   'role in (admin, staff, teacher) or is_self(actor, data)'
  update: 'role == admin or owns_record(actor, data)'
  delete: 'role == admin'
search:
  fields: [first_name, last_name, student_number]
  ordering: [updated_at desc]
events:
  after_create: student.created
  after_update: student.updated
  after_status_change: student.status_changed
```

### 6.2 Field types

`text`, `textarea`, `number` (int/float/currency), `date`, `datetime`,
`time`, `enum`, `bool`, `relation` (FK), `many_to_many`, `file`, `json`,
`calculated` (formula over other fields), `money` (int cents + currency).

### 6.3 Validation rules (declarative, composable)

`required`, `required_if(cond)`, `min`, `max`, `min_length`, `max_length`,
`pattern`, `email`, `phone_e164`, `unique`, `unique_scope(columns...)`,
`one_of`, `range`, `date_after/before`, `cross_field(expr)`, `formula(expr)`,
`custom(plugin:...)`. Expressions use a small, side-effect-free language
(see §9.3) evaluated by the ValidationEngine server-side.

### 6.4 Permissions (rule language)

`role in (...)`, `permission('student.view')`, `campus_match(actor, data)`,
`owns_record(actor, data)`, `is_self(actor, data)`, `field_visible(field)`,
`field_editable(field)`, boolean combinators, and `plugin:...` predicates.
The engine returns **both** an allow/deny and a **field-level mask** so a
renderer can grey out or hide fields the actor cannot edit/see (reuses the
existing role→permission service as the vocabulary provider).

### 6.5 Views, widgets, actions, events, automation, reports, commands

- **Views** — list (columns, sort, filters, row actions), form (sections,
  fields, validation, actions), detail (field groups + related-entity
  embedded lists), dashboard (widget grid), report (aggregations + charts).
- **Widgets** — declarative `widget.kind` per field (text, select, date,
  autocomplete-relation, file-upload, checkbox, radio-group, table, kpi-card,
  chart, timeline).
- **Actions** — builtin (create/update/delete/export/search) or custom
  (plugin/workflow); each carries a payload schema, target, and permission.
- **Events** — entities declare the events they emit (`student.created`,
  `payment.received`); `md_event_subscriptions` wires them to actions,
  notifications, or workflow transitions — all metadata, all through the
  existing outbox for durability.
- **Automation** — cron-triggered actions (`md_automations`), e.g. "every
  Monday 08:00 → run `fee-due-reminders` action" (which itself triggers the
  notifications workflow).
- **Reports** — metadata definitions of filters + group-by + aggregations +
  chart type + export columns; the report engine executes them against the
  storage adapter.
- **Commands** — a global command catalog (the desktop Ctrl+K / web ⌘K
  palette) generated from actions + views, so the command palette is metadata.

---

## 7. Event flow

The Forge reuses the existing transactional outbox; metadata makes the
subscriptions declarative.

```
  actor action ──► generated API ──► CrudService
        │
        ├── 1. pre hooks (plugins: pre_create, pre_update)
        ├── 2. ValidationEngine (metadata rules)
        ├── 3. PermissionEngine (allow + field mask)
        ├── 4. Repository.create/update (same transaction)
        ├── 5. EventBridge: resolve metadata subscriptions for the entity's
        │         emitted event → write OUTBOX row (same transaction)
        └── 6. post hooks (post_create, after_commit) + cache invalidation

  background worker (existing outbox_handlers):
        outbox row ──► dispatch
          ├── mode=sync     → run handlers in-process
          ├── mode=outbox   → deliver via outbox (retry/backoff/dead-letter)
          └── mode=workflow → transition the attached workflow instance
        then: run metadata subscriptions (notify, action, sync)
```

**Guarantees (inherited from the existing outbox):** atomic commit with the
business change; idempotent delivery (`event_id` unique); at-least-once with
idempotent consumers; retry/backoff; dead-letter; replayable.

---

## 8. Rendering pipeline

```
  request: GET /api/g/student/form?entityVersion=12
        │
        ▼
  1. Registry.load('student', version=12)          # cache hit? serve
        │
        ▼
  2. Compiler.validate (definition integrity)      # fail loudly
        │
        ▼
  3. PermissionEngine.mask(actor, 'student', 'form')
        │                                      # field-level visibility/editable
        ▼
  4. DescriptorBuilder → ScreenDescriptor          # static part (cached)
        │
        ▼
  5. Merge dynamic data (existing record, options, relation autocomplete)
        │
        ▼
  6. Serialize descriptor (JSON) + cache by (entity, version, role)
        │
        ▼
  7. Renderer (CustomTkinter or React) renders descriptor
```

**Hot reload:** the Registry watches the metadata store/file tree; on change
it bumps a generation counter, invalidates the cache, and notifies connected
clients (`Server-Sent Events` for web, a long-poll/websocket heartbeat for
desktop). Uncommitted screens keep rendering the old generation until they
re-request.

**Caching:**
- **Registry graph** — in-memory, immutable-per-generation (structural
  sharing; a metadata edit rebuilds only the affected subgraph).
- **Descriptors** — cached by `(entity, version, role-mask)`; invalidated on
  generation change or permission change.
- **Query results** — the existing repository-level caching, with
  version-aware invalidation (a write bumps the entity's data version).

**Dependency graph:** the compiler builds a DAG of entities (relation edges),
views (entity refs), actions (entity + view refs), workflows (entity refs),
and automations (action refs). Cycles are rejected at compile time; topological
order drives migration ordering and cache invalidation fan-out.

---

## 9. Security model

1. **Every generated endpoint is permission-gated by default.** No metadata,
   no access. The PermissionEngine evaluates `md_permissions` for the actor
   (role + campus + ownership) before any CRUD.
2. **Field-level masking** — read/create/update masks per field; the renderer
   receives only the fields the actor may see, so sensitive fields never
   reach the client.
3. **Tenant isolation preserved** — all generated repositories route through
   the existing `TenantScopedRepository` semantics (campus scoping injected
   from the auth context; verified by the multi-tenancy tests).
4. **Metadata is privileged data.** The metadata API is admin-only; metadata
   edits require a separate elevated role and are audit-logged (existing audit
   domain). Clients can never write metadata.
5. **Validation is enforced server-side** — client validation is UX; the
   engine re-validates every payload. SQL injection is impossible by
   construction: generated queries use bound parameters through the
   repository adapters (never string-built SQL from field names — field names
   come from validated metadata, and values are always bound).
6. **Expression language is side-effect-free and sandboxed** — the rule
   language (permissions, validation conditions) has no file/network/import
   access and a node budget; plugin hooks are the *only* escape hatch and run
   under the platform's plugin trust boundary.
7. **The desktop client authenticates through the same API** (OAuth-style
   bearer tokens, refresh rotation — reusing `auth/security.py`); secrets
   live in the OS keychain (or the existing secrets provider pattern), never
   in metadata.

---

## 10. Step-by-step implementation roadmap

Each step is shippable; nothing is a big-bang.

**Step 0 — Pilot the contract (weeks 1–2).** Pick ONE entity (student). Write
`metadata/entities/student.yaml` by hand; build `MetadataRegistry` +
`MetadataCompiler` + Pydantic models. Target: `registry.load('student')`
validates and serves a descriptor. *Exit: a JSON descriptor for the student
form.*

**Step 1 — Storage adapters (weeks 3–5).** Implement `StorageAdapter` ABC +
Postgres + MySQL + SQLite. Reverse-engineer the student table DDL into
`student.yaml`; compiler emits identical DDL. *Exit: metadata → real table on
both PG and MySQL.*

**Step 2 — CRUD engine + API (weeks 6–9).** `CrudService` +
`EntityRouterFactory`; generated `/api/g/student` endpoints (list/get/create/
update/delete) with permission gates + field masks, behind auth + tenant.
*Exit: the existing React student pages work against the generated API.*

**Step 3 — Validation engine (weeks 10–11).** Declarative rules from §6.3
enforced server-side; the web client's existing forms start receiving
descriptors. *Exit: student form is metadata-defined end-to-end on web.*

**Step 4 — Web renderer (weeks 12–16).** `ScreenRenderer` + widget library in
the React app; convert the highest-traffic views (student list/form/detail,
fee payment). *Exit: 5 screens fully generated, 0 hand-coded.*

**Step 5 — Desktop renderer (weeks 17–22).** CustomTkinter client: `app.py`,
`Screen`, widget factory, table, theme; auth + token refresh. *Exit: desktop
client renders the same 5 screens from the same metadata.*

**Step 6 — Events, workflows, automations (weeks 23–27).** `EventBridge`
metadata subscriptions → existing outbox; `md_workflows` wrapping the existing
workflow engine; `md_automations` cron dispatch. Convert admission workflow +
fee-due automation. *Exit: a workflow and an automation run purely from
metadata.*

**Step 7 — Reports + dashboards (weeks 28–31).** Metadata report engine;
widget grid from `md_views kind='dashboard'`; wire the Watchtower chart
components as dashboard widgets. *Exit: a dashboard is metadata.*

**Step 8 — Mass migration + retirement (weeks 32–40).** One domain per
sprint: reverse-engineer domain → metadata (automated extraction script reads
the existing SQLAlchemy models + schemas), flip call sites to generated
endpoints, retire hand-written CRUD. Keep legacy endpoints behind
`Accept-Version` for the grace window.

**Step 9 — Hardening (weeks 41–48).** Performance: descriptor caching,
hot-reload, query caching, dependency-graph invalidation; security audit
against `SECURITY_POLICY.md`; plugin SDK docs; a metadata authoring guide.

**Success criteria:** >80% of screens, forms, APIs, and workflows are
generated from metadata; hand-written code is confined to plugins and seed
domains; both renderers render identical descriptors; a metadata edit ships a
new screen without touching application code.

---

## Appendix A — The Forge vs. the existing roadmap

| Concern | `TRANSFORMATION_ROADMAP_V3.md` (The Ascent) | The Forge |
|---|---|---|
| Scope | Frontend design transformation of the current web app | Platform transformation: everything generated from metadata |
| Renderer | React web app (premium UI) | React web app **and** CustomTkinter desktop client |
| Data | PostgreSQL | PostgreSQL **and** MySQL (adapter layer) |
| Relationship | The Ascent assumes hand-coded components | The Forge makes the renderer contract the *surface* that The Ascent's design system styles |

They are complementary: The Ascent designs *how the generated UI looks*; the
Forge designs *how that UI comes to exist*. The renderer contract (§5) is the
joint — both the Design System v3 tokens and the Table System v3's `DataTable`
slot into the widget layer.
