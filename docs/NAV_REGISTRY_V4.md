# Nav-Registry v4 — Design

**Part of:** `docs/NAVIGATION_SYSTEM_V4.md` (the *Atlas*, §15) · **Status:** Draft for review · **Owner:** Product Design · **Version:** 0.1.0
**Scope:** `apps/web/src/nav/` — the single source of truth for the sidebar, the command surface, breadcrumbs, the jump map, and the context layer.
**Consumers today:** `types/roles.ts` (sidebar), `components/ui/command-palette.tsx` (Pages + Actions), `components/ui/universal-search-modal.tsx` (objects), `components/ui/breadcrumbs.tsx` (manual trails), `hooks/use-nav-persistence.ts` (recents + favorites), `hooks/use-permission.ts` (permission checks).

> *Five surfaces render navigation; today each authors its own. The registry makes navigation a **data problem**: one typed map, five selectors, and a ≤ 3-interaction audit that runs in CI.*

---

## 1. Goals & non-goals

**Goals**

1. **One source of truth.** Sidebar, command surface, breadcrumbs, jump map, and context layer all render the same registry — no surface invents navigation.
2. **Role + permission scoped, type-safe.** Filtering by role (`roles.ts`) and permission (`permissions.ts`) happens in selectors, not in the data.
3. **The ≤ 3 law is computable.** `auditReachability()` proves every route has a command, jump, or click path — in CI.
4. **Zero-maintenance breadcrumbs.** Trails derive from the route's module + object, killing per-page `Crumb[]` arrays.
5. **Stable identity for pins/recents.** Pins and recents reference registry ids, so labels, icons, and trails stay in sync when the map changes.

**Non-goals**

- Not a router. `react-router` still owns routing; the registry only *describes* routes.
- Not a permission engine. `types/permissions.ts` remains the permission source; the registry *gates on* it.
- Not a feature flag system. Feature flags remain where they are; the registry is flag-agnostic (a gated module simply isn't registered yet).

---

## 2. The type model

Everything is one of six kinds. The **route** is the atom; the **module** groups routes; the **command** is a verb; the **context rule** binds verbs to a surface; the **jump chord** is a keyboard alias; the **object type** maps entity kinds to routes.

```ts
// nav/registry.types.ts

/** A place the app can be. The atom of navigation. */
export interface NavRoute {
  /** Stable id: 'students.list', 'fees.payments'. Pins/recents/history reference this, never the path. */
  id: string
  /** URL path — the deep-link contract. Never changes once shipped. */
  to: string
  label: string
  description?: string
  /** SVG path (existing NAV_ICONS style) */
  icon?: string
  /** Palette/jump search terms: ['people', 'enroll', 'register'] */
  keywords?: string[]
  /** Permission gate, e.g. 'fees.view' */
  permission?: string
  /** Explicit role allow-list — for portal routes (student/parent workspaces) that permissions alone can't express. */
  roles?: UserRole[]
  /** Owning module id. */
  module?: ModuleId
  /** Breadcrumb trail override. Default: [Workspace] > Module > self. */
  trail?: TrailSegment[]
  /** URL patterns that keep this item highlighted (sub-route matching, replaces NavItem.matchPaths). */
  matchPaths?: string[]
  /** Attention count (sidebar badge). Static, or a live source for counts that change (alerts, dues). */
  badge?: number | (() => number)
  /** Context-navigation tabs for this surface. */
  tabs?: NavTab[]
  /** True for deep-link-only surfaces (portals, detail pages) — rendered by search, not the sidebar. */
  hidden?: boolean
}

/** One breadcrumb segment: always resolvable, usually derived. */
export interface TrailSegment {
  id: string
  label: string
  to?: string
}

/** In-page navigation: underline tabs for a module's sub-sections. */
export interface NavTab {
  id: string
  label: string
  /** Sub-route; absent = in-page tab without a URL. */
  to?: string
  /** Active pattern (defaults to to). */
  match?: string
  permission?: string
}

/** A module: a first-class sidebar row + palette group + breadcrumb segment. */
export interface NavModule {
  id: ModuleId
  label: string
  /** Sidebar group: overview | people | academics | operations | insights | system | account */
  group: NavGroupId
  icon?: string
  /** Landing route for the module. */
  home: string
  /** Routes that belong to this module (its sidebar rows + deep links). */
  routes: NavRoute[]
  permission?: string
}

/** The environment a command runs in. */
export interface CommandContext {
  navigate: (to: string) => void
  /** The current object, when the command runs on an object surface (e.g. a student 360). */
  objectId?: string | number
  params?: Record<string, string>
}

/** A verb: something the user can do. Lives in the palette, the action band, and the inspector. */
export interface NavCommand {
  id: string          // 'record-payment'
  label: string       // 'Record payment'
  description?: string
  icon?: string
  keywords?: string[]
  permission?: string
  /** Shown in the shortcuts dialog; optional. */
  shortcut?: string
  /** What it does: navigate to a route, or execute. */
  run: (ctx: CommandContext) => void
  /** Target route id/path — used by the reachability audit. */
  target?: string
  /** For palette ranking: pages and actions rank above objects at equal relevance. */
  kind: 'page' | 'action' | 'object'
}

/** Context rules: what the action band and inspector offer on a given surface. */
export interface ContextRule {
  /** Route pattern(s) this rule applies to: '/students/:id' */
  match: string | string[]
  /** The action band — exactly one primary, plus secondary. */
  primary?: NavCommand
  actions?: NavCommand[]
  /** The inspector (⌘.) sections. */
  inspector?: InspectorSection[]
}

export interface InspectorSection {
  id: string
  label: string
  kind: 'quick-actions' | 'related' | 'links' | 'history'
  /** Commands or links for this section. */
  items: (NavCommand | NavTargetLink)[]
  /** Progressive disclosure cap (default 3). */
  limit?: number
}

/** A related/contextual link (inspector sections). Named NavTargetLink to avoid colliding with react-router-dom's NavLink. */
export interface NavTargetLink {
  id: string
  label: string
  to: string
  description?: string
  icon?: string
}

/** A G-chord: two-keystroke jump, Linear-style. */
export interface JumpChord {
  chord: string       // 'gs' | 'gf' | 'gt' — the second key
  label: string       // 'Students'
  /** Route, command id, or the reserved ':back' sentinel (go to history origin). */
  target: string
}

/** Maps search-index entity types to real routes ('student' → '/students/:id'). */
export interface ObjectTypeDef {
  entityType: string
  /** Route template. */
  to: (id: number | string) => string
  /** Label template (for palette + breadcrumb object segments). */
  label?: (id: number | string) => string
  /** Permission gate, e.g. 'students.view'. */
  permission?: string
}

/** The whole map. */
export interface NavRegistry {
  modules: NavModule[]
  commands: NavCommand[]
  contextRules: ContextRule[]
  jumpMap: JumpChord[]
  objectTypes: Record<string, ObjectTypeDef>
}
```

### 2.1 Scoping rules

1. **`permission` gates, `roles` allow-lists.** Permission is the default gate (works across multi-role users via `usePermission`'s union). `roles` is reserved for portal workspaces whose routes are role-shaped, not permission-shaped (student/parent home sets).
2. **Selectors filter; data never embeds a role's tree.** The v3 per-role arrays (`adminNav`, `teacherNav`, …) dissolve into registry data + role allow-lists; the *shape* is identical for every role (Atlas §3.1 rule 3).
3. **Ids are forever.** A route id, once shipped, is a persisted contract (pins, recents, history, deep links). Renaming a label or moving a route changes `to`/`label` but never `id`; a removed route is dropped silently by consumers (Atlas §4.3).
4. **No ad-hoc navigation.** A route that isn't in the registry is unreachable by search and unauditable by the ≤ 3 law — that is the enforcement mechanism.

---

## 3. Example registry entries

```ts
// nav/registry.ts — illustrative fragments

const studentsModule: NavModule = {
  id: 'students',
  label: 'Students',
  group: 'people',
  icon: NAV_ICONS.students,
  home: '/students',
  permission: 'students.view',
  routes: [
    { id: 'students.list', to: '/students', label: 'Students', keywords: ['people', 'enroll', 'register'], matchPaths: ['/students'] },
    { id: 'students.batch', to: '/operations/batch/enroll', label: 'Batch Enroll', hidden: true, keywords: ['bulk'] },
  ],
}

const feesModule: NavModule = {
  id: 'fees',
  label: 'Fees & Finance',
  group: 'operations',
  icon: NAV_ICONS.fees,
  home: '/fees/payments',
  permission: 'fees.view',
  routes: [
    { id: 'fees.payments', to: '/fees/payments', label: 'Payments', matchPaths: ['/fees/payments'], tabs: [
        { id: 'list', label: 'List' }, { id: 'structures', label: 'Structures', to: '/fees/structures' },
        { id: 'dues', label: 'Dues', to: '/fees/dues' } ] },
    { id: 'fees.structures', to: '/fees/structures', label: 'Fee Structures' },
    { id: 'fees.dues', to: '/fees/dues', label: 'Fee Dues' },
  ],
}

const commands: NavCommand[] = [
  { id: 'record-payment', label: 'Record payment', kind: 'action', keywords: ['collect', 'fee'],
    permission: 'fees.record_payment', target: '/fees/payments',
    run: (ctx) => ctx.navigate('/fees/payments') },
  { id: 'add-student', label: 'Add student', kind: 'action', permission: 'students.create',
    target: '/students', run: (ctx) => ctx.navigate('/students') },
  { id: 'record-attendance', label: 'Record attendance', kind: 'action', permission: 'attendance.record',
    target: '/attendance/daily', run: (ctx) => ctx.navigate('/attendance/daily') },
]

const contextRules: ContextRule[] = [
  {
    match: '/students/:id',
    primary: { id: 'ctx-record-payment', label: 'Record payment', kind: 'action',
               permission: 'fees.record_payment', target: '/fees/payments',
               run: (ctx) => ctx.navigate(`/fees/payments?student=${ctx.objectId}`) },
    inspector: [
      { id: 'quick', label: 'Quick actions', kind: 'quick-actions', items: [/* ctx commands */], limit: 3 },
      { id: 'related', label: 'Related', kind: 'related', items: [/* siblings, guardian */] },
      { id: 'links', label: 'Cross-module', kind: 'links', items: [
          { id: 'l-dues', label: 'Fee dues', to: '/fees/dues?student=:id' },
          { id: 'l-att', label: 'Attendance trend', to: '/analytics/attendance?student=:id' } ] },
    ],
  },
]

const jumpMap: JumpChord[] = [
  { chord: 's', label: 'Students', target: '/students' },
  { chord: 't', label: 'Teachers', target: '/teachers' },
  { chord: 'c', label: 'Classes', target: '/academic' },
  { chord: 'a', label: 'Attendance', target: '/attendance' },
  { chord: 'f', label: 'Fees', target: '/fees/payments' },
  { chord: 'i', label: 'Command Center', target: '/command-center' },
  { chord: 'g', label: 'Go back (history)', target: ':back' },
]

const objectTypes: Record<string, ObjectTypeDef> = {
  student:  { entityType: 'student',  to: (id) => `/students/${id}`, permission: 'students.view' },
  teacher:  { entityType: 'teacher',  to: (id) => `/teachers/${id}`, permission: 'teachers.view' },
  class:    { entityType: 'class',    to: (id) => `/academic/classes/${id}` },
  payment:  { entityType: 'payment',  to: (id) => `/fees/payments/${id}` },
  // … mirrors the backend search index's INDEXABLE_ENTITY_TYPES
}
```

---

## 4. Selectors — the five consumers, one map

All selectors take the **resolved identity**: `{ role, permissions }` where `permissions` is the multi-role union from `usePermission()` (`getAllPermissionsForRoles`). Selectors are pure — the same inputs, the same map.

```ts
// nav/selectors.ts

export interface ResolvedUser { role?: UserRole; permissions: string[]; roles: UserRole[] }

/** Sidebar sections: Pinned → Recent → module groups (Atlas §4). */
export function getNavSections(
  registry: NavRegistry, user: ResolvedUser, opts: { pins?: Pin[]; recents?: Recent[] },
): NavSection[]                        // ← same shape as today's roles.ts NavSection (compat)

/** Command surface groups: Pinned → Recent → Actions → Pages (Atlas §5). */
export function buildPaletteGroups(
  registry: NavRegistry, user: ResolvedUser, opts: { pins?: Pin[]; recents?: Recent[] },
): CommandGroup[]                      // ← same shape as command-palette.tsx (compat)

/** Breadcrumb trail for a path: [Workspace] > Module > Object (Atlas §6). */
export function resolveTrail(registry: NavRegistry, pathname: string): Crumb[]

/** G-chords for this user (Atlas §13). */
export function getJumpMap(registry: NavRegistry, user: ResolvedUser): JumpChord[]

/** Context rule for the current surface (Atlas §7: action band + inspector). */
export function getContextFor(registry: NavRegistry, pathname: string, user: ResolvedUser): ContextRule | undefined

/** Object route from the search index's entity type + id (Atlas §12). */
export function resolveObjectRoute(registry: NavRegistry, entityType: string, id: number | string): string | undefined

/** The ≤ 3-interaction audit — CI gate (Atlas §1, §19). */
export function auditReachability(registry: NavRegistry, user: ResolvedUser): ReachabilityViolation[]
```

### 4.0 The palette seam (run → action)

`buildPaletteGroups` must produce the palette's exact shapes, not the registry's:

```ts
// command-palette.tsx's CommandItem / SmartSearchResult shapes
interface CommandItem { id: string; label: string; description?: string; icon?: string; action: () => void; keywords?: string[] }
interface SmartSearchResult { id: string; label: string; description: string; type: string; icon: string; action: () => void; keywords: string[] }

// selector wraps the registry into those shapes:
//   NavCommand → CommandItem        { …command, action: () => command.run(ctx) }
//   object route → SmartSearchResult { …item, type: entity_type, action: () => navigate(resolveObjectRoute(…)) }
```

The palette never imports the registry types; it consumes the seam. `SmartSearchResult.type` comes from the index's `entity_type` (already present).

### 4.1 The reachability audit

For every registry route visible to the user, exactly one of these must hold — otherwise the route is a violation:

| Path | Interactions | Check |
|---|---|---|
| Command | `⌘K` → type label/keyword → `Enter` | route has `label`/`keywords` (presence — CI-verifiable) |
| Jump | `G` chord → `Enter` | route (or its module home) has a jump chord |
| Click | sidebar module row → click, or breadcrumb crumb → click | route is a module row, or its module is in the sidebar, or route is a breadcrumb ancestor of itself |

```ts
interface ReachabilityViolation {
  routeId: string
  path: string
  reason: 'no-keywords' | 'no-module' | 'no-jump'
}
```

**What the audit can and cannot prove:** CI verifies *presence* — every visible route has searchable terms, a module, or a chord. Runtime *rank* (which result the palette shows first) depends on recency/frequency and is a runtime property, not a CI gate; the worst case is bounded by the palette's `≤ 12 results` rule, and a route with searchable terms always *surfaces*, which is all the ≤ 3 law requires. Rules: portal/hidden routes (`hidden: true`) are exempt from the sidebar-click check but must still be reachable by command. The audit runs per role × campus in CI (Atlas §19).

---

## 5. Role & permission scoping

1. **Gates compose: `permission` AND/OR `roles`.** A route is visible when it has no gate, or `permissions.includes(permission)`, or `roles` includes any of the user's roles.
2. **Multi-role is free.** Because selectors take the permission *union*, a teacher who is also an accountant sees both maps without special casing (already how `usePermission` works).
3. **Portals stay role-shaped.** Student and parent workspaces register as modules with `roles: ['student']` / `roles: ['parent']` — their routes (`/student/*`, `/parent/*`) are permission-light but role-explicit, matching today's `studentNav`/`parentNav`.
4. **Home routes come from the registry too.** `getHomeRoute(role)` (used at login) resolves from `ROLE_CONFIG.homeRoute` — kept in `roles.ts` as role metadata, not duplicated in the registry.

---

## 6. Pins & recents — ids, not paths

`use-nav-persistence.ts` stores `RecentItem { path, label, timestamp }` and favorites as bare paths. The registry upgrades this:

```ts
interface Pin { routeId: string; pinnedAt: number }
interface Recent { routeId: string; visitedAt: number; count: number }
```

1. **Pins/recents reference `routeId`.** Labels, icons, and trails render from the registry — rename a page and every pin follows. Unknown ids are dropped silently (Atlas §4.3).
2. **Recency × significance** (Atlas §8): rank = `count` weight × recency decay; object routes (a student's 360) gain a significance bonus so they outrank report pages.
3. **Compat:** the store keeps the existing localStorage keys (`sdmas::recent-items`, `sdmas::favorites`) with a versioned migration of path → id on first read; `addRecentItem(path, label)` gains an overload `addRecentItem(routeId)` and resolves through the registry.

---

## 7. The object index bridge

The universal search's local FTS5 index returns `IndexSyncItem { entity_type, entity_id, route, label, … }`. The registry's `objectTypes` is the *authoritative* route template; the index's `route` field is the *projected* value. Rule: the index writes `objectTypes[entityType].to(entityId)` — one template, one truth. `resolveObjectRoute` is the single function both the search modal and the palette use to open an object.

---

## 8. Migration from `roles.ts`

Incremental, route-stable, flag-gated — no wave breaks a deep link (Atlas §18).

| Step | Change | Safety |
|---|---|---|
| 1 · Types | Add `nav/registry.types.ts` (above) | New files only; zero behavior change |
| 2 · Registry | Port the canonical module set + commands + context rules into `nav/registry.ts` | Routes are copied verbatim from `roles.ts`; ids assigned but paths unchanged |
| 3 · Compat selectors | Re-implement `getNavSectionsForRole` / `getNavItemsForRole` over `getNavSections(...)` | `sidebar.tsx` imports the same names — no consumer change |
| 4 · Portal modules | `studentNav` / `parentNav` become role-gated modules | Portal routes unchanged |
| 5 · Palette | `buildCommandGroups` (in `app-layout.tsx`) delegates to `buildPaletteGroups` | Palette renders identically at first (same ids/labels), then gains objects + pins/recents with the Atlas command surface |
| 6 · Breadcrumbs | `use-breadcrumbs` derives trails from `resolveTrail`; pages drop their `Crumb[]` arrays one module at a time | Trail renders identically during the transition (registry trail == hand-written trail is a per-page test) |
| 7 · Audit | Wire `auditReachability` into CI (per role) | New gate; existing routes must pass before the flag flips |
| 8 · Cleanup | `roles.ts` keeps `ROLE_CONFIG`, `ROLE_BADGE_COLORS`, `getHomeRoute`; the per-role nav arrays are deleted | Delete only after every consumer migrated |

**Rollback:** every step is independently revertible; step 3's compat layer means the sidebar never depends on the new files until they're ready.

---

## 9. File layout & tests

```
apps/web/src/nav/
  registry.types.ts      — the type model (§2)
  registry.ts            — the canonical map: modules, commands, contextRules, jumpMap, objectTypes (§3)
  selectors.ts           — getNavSections, buildPaletteGroups, resolveTrail, getJumpMap,
                           getContextFor, resolveObjectRoute, auditReachability (§4)
```

**Unit tests** (`nav/__tests__/`):

1. **Scope tests** — each role resolves the expected sidebar/palette/jump subsets; multi-role union includes both; portal gating by role.
2. **Trail tests** — `resolveTrail('/students/1042')` → `[Workspace] > Students > Student 1042`; unknown path falls back to a single self crumb; tab routes keep the module crumb.
3. **Audit tests** — a route with no keywords, no module, and no chord is a violation; every route in the canonical registry passes for every role.
4. **Id-stability tests** — pins/recents keyed by id survive a label change and a move; unknown ids drop silently.
5. **Compat tests** — `getNavSectionsForRole` over the registry matches the pre-migration snapshot for every role (golden file).

---

## 10. Acceptance criteria

- All five consumers (sidebar, palette, breadcrumbs, jump map, context layer) render from `nav/registry.ts`; zero ad-hoc navigation remains.
- `auditReachability` passes for every role in CI; a route added without a ≤ 3 path fails the build.
- Breadcrumb trails derive from routes; no per-page `Crumb[]` arrays remain.
- Pins/recents store ids; labels and icons stay in sync through a rename; unknown ids drop silently.
- Every deep link from the pre-migration app resolves identically after all waves.
- The ≤ 3-interaction law holds for every registry route: command, jump, or click (§4.1).

---

*The registry is the map the Atlas promises: typed, scoped, audited — one file that knows where everything is and how to get there in fewer than three interactions.*
