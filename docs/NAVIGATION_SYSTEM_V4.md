# SDMAS Navigation System — v4 Specification

**Codename:** *The Atlas*
**Status:** Draft for review · **Owner:** Product Design · **Version:** 4.0.0
**Scope:** apps/web — the app shell (sidebar, header, command surface, breadcrumbs, context panel) and the information architecture that feeds it
**Companion docs:** `docs/DESIGN_SYSTEM_V3.md` (*Corridor* — §12.6 navigation & app shell, this document is its v4 normative expansion), `docs/MOTION_SYSTEM_V4.md` (*Escapement* — nav surface motion), `docs/DASHBOARD_SYSTEM_V4.md` (*Bridge* — the landing surface), `docs/ANALYTICS_SYSTEM_V3.md` (*Watchtower* — the command bar), `docs/DESIGN_SYSTEM_DESKTOP_V3.md` (*Forge* — desktop parity)

> *An ERP buries its depth in menus. The Atlas flattens it: every action in the school is reachable in fewer than three interactions — a command, a jump, a click. The map is not a tree; it is a compass, a set of shortcuts, and a breadcrumb trail that always knows where you are and how you got here.*

**The law:** *every action the product offers is reachable in ≤ 3 interactions.* This document defines the surfaces that make the law true, the flows that prove it, and the migration that gets there without breaking a single deep link.

---

## 0. What is wrong with the current navigation

Audited against the current shell (`sidebar.tsx`, `header.tsx`, `command-palette.tsx`, `universal-search-modal.tsx`, `roles.ts`, `use-nav-persistence.ts`):

| Defect | Evidence today | v4 answer |
|---|---|---|
| **Two command surfaces** | `⌘K` opens universal search (entities); the command palette (pages + actions) is a header button | **One unified command surface** (§5): pages + actions + entities + commands in a single `⌘K` |
| **Hierarchical sidebar** | Admin nav is 20 items in 4 sections; depth hides actions | **Flat modules + personal sections** (§4): pins, recents, then one-level modules |
| **Recents & favorites exist but are invisible** | `use-nav-persistence` stores them; the sidebar never renders them | **Pins + recents are first-class sidebar sections** (§8, §9) |
| **Breadcrumbs are per-page and manual** | `breadcrumbs.tsx` takes hand-written `Crumb[]` per page | **Object-aware, registry-driven breadcrumbs** in the header (§6) |
| **No history** | Browser back only; no "where was I" | **Session history + resume** (§10) |
| **No context panel** | Contextual actions are scattered in page toolbars | **The inspector** — a keyboard-openable context panel per surface (§7) |
| **No focus mode** | Chrome is all-or-nothing | **Focus mode** collapses chrome on demand (§14) |

---

## 1. The three-interaction law

**An interaction** is one of: a keystroke, a click, a command-enter, or a shortcut chord. The law: *from any screen, any action is reachable in ≤ 3 interactions.*

Three canonical paths make the law true for every action:

| Path | Interactions | Example |
|---|---|---|
| **Command** | `⌘K` → type → `Enter` | `⌘K` "pay ram" `Enter` → payment screen for that student |
| **Jump** | shortcut chord → `Enter` | `G` `S` → Students; `G` `F` `P` → Payments |
| **Click** | sidebar / breadcrumb / context → click | Sidebar → Fees; breadcrumb → Payments; context → "Record payment" |

The law is audited per release: every route and every command in the registry is tested for a ≤ 3-interaction path (§19). A command that needs a fourth interaction is a bug in the map, not a failing user.

---

## 2. Sources & extraction — principles only

| Source | What it demonstrates | Principle extracted | Translation into SDMAS |
|---|---|---|---|
| **Raycast** | The command palette *is* the product; recents/root/favorites at the top; every workflow is a keystroke sequence | **Search is the primary navigator** | One unified `⌘K` (§5); palette head shows pinned, recent, actions before results (§5.2); type-ahead everywhere |
| **Linear** | Collapsible sidebar (256/64) with Inbox/Projects/Teams; `G`-then-key jump chords; pin/favorite cycles; "find or create" | **The flattened module bar + jump chords** | Sidebar = pins → recents → flat modules (§4); `G` jump map (§13); pin from anywhere (§9) |
| **Arc Browser** | Spaces/profiles as workspaces; sidebar tabs; command bar; focus mode | **Workspaces as identity; focus as a mode** | Workspace switching = loud, safe room change (§11); focus mode collapses chrome (§14) |
| **Notion** | Sidebar pages + workspace; `⌘P`/`⌘K` search; favorites + recents sections; breadcrumb-ish hierarchy | **The map and the trail** | Breadcrumbs are the path back (§6); recents and favorites are persistent sidebar sections (§8–9) |

---

## 3. Information architecture — the flat model

### 3.1 The mental model

SDMAS is **object-based, not menu-based**. A module is a *collection of objects with actions*, not a folder of pages:

```
OBJECTS (the nouns)            ACTIONS (the verbs)
Students · Teachers            Record attendance · Add student · Record payment
Classes · Sections · Subjects  Create fee structure · Send notice · Approve leave
Fees · Payments · Receipts     Export report · Batch enroll · Generate report card
Leave · Admissions · Users     Roll over term · Post result · Assign marks
```

**IA rules:**

1. **One level of module depth.** A module is one sidebar row, one palette group, one breadcrumb segment. Depth lives in *objects* (the 360s, the detail pages), never in menu trees. The ERP's "Fees → Structures → Edit → Payments" becomes "Fees" (one row) with the detail surfaced by tabs and the inspector (§7).
2. **Everything is a registry entry.** Modules, commands, and routes live in one `nav-registry` (extending `roles.ts`) so the sidebar, palette, breadcrumbs, and jump map render the same truth — no surface may invent navigation the registry doesn't know (§15).
3. **Role-scoped, never role-fragmented.** The registry filters per role (as `roles.ts` does today) but the *shape* is identical across roles: pins → recents → modules → account. A teacher's map is a subset of the admin's map, never a different species.
4. **Search is the first surface, the sidebar the second, breadcrumbs the third.** The three render the same registry; a user may learn one and trust the others.

### 3.2 The module list (canonical)

| Module | Objects | Sidebar row |
|---|---|---|
| Command Center / Risk / Timeline | health surfaces | Overview group (3 rows) |
| Students · Teachers | people | People group |
| Academics (classes, sections, subjects) | structure | Academics group |
| Attendance | records | Operations group |
| Fees & Finance | dues, payments, receipts, structures | Operations group |
| Communications | messages, templates | Operations group |
| Reports & Analytics | reports, report cards, rooms | Insights group |
| Admissions · Leave | applications, requests | Operations group |
| Operations · Users · Audit | batch ops, accounts, logs | System group |

Groups are **3–4 labels max** (Overview / People / Academics / Operations / Insights / System — role-filtered). No module is more than one level deep in the sidebar.

---

## 4. Global navigation — the sidebar (v4)

```
┌──────────────────────────────┐
│ ▣ SDMAS            [⌘B ⇐]    │  brand + collapse
├──────────────────────────────┤
│ ★ Pinned                     │  §9 — user's pins (Linear-style)
│   · Class 7A · Payments      │
│ ⏱ Recent                     │  §8 — last 8, recency-ranked
│   · Student 1042 · Reports   │
├──────────────────────────────┤
│ OVERVIEW                     │  module groups (flat, §3)
│   Command Center · Risk ·    │
│ PEOPLE / ACADEMICS / ...     │
├──────────────────────────────┤
│ ◐ Campus (current)           │  workspace + campus (§11)
│   {user} ▾                   │  user menu
└──────────────────────────────┘
```

1. **Pinned section** — first, always: the user's pinned items (§9), rendered from `use-nav-persistence`. Pin/unpin in place; the section is empty-friendly (a hint row: "Pin anything with ⋆").
2. **Recent section** — second: the 8 most recent (recency × significance, §8). Shown even when pinned exists; "Clear" affordance.
3. **Module groups** — flat, one level, role-filtered from the registry. The 20-item admin tree collapses to ≤ 6 groups × ≤ 4 rows.
4. **Collapse to rail** — unchanged (260ms E/W move, Escapement §10.10); rail shows pins + modules as icons with tooltips; recents hide in the rail (the palette owns recents when collapsed).
5. **Keyboard:** when the sidebar has focus, `↑↓` moves, `Enter` opens, **type-to-filter** narrows module rows instantly (Raycast rule). `⌘B` toggles collapse (existing).
6. Badges (existing `item.badge`) stay — attention counts belong on the map.

---

## 5. The command surface — one ⌘K

The single most important change. The palette and the search modal become **one surface**; the keyboard binding that today opens only entity search (`⌘K` in `app-layout.tsx`) opens everything.

### 5.1 Anatomy (Raycast model)

```
⌘K
─────────────────────────────────
  🔍  query...            [ESC]
─────────────────────────────────
  Pinned     ▸ Class 7A · Payments        (when query is empty)
  Recent     ▸ Student 1042 · Reports
  ───────────────────────────
  Actions    ▸ Record attendance · Add student · Record payment
  Pages      ▸ Fees → Payments · Analytics
  Objects    ▸ Student 1042 · Teacher 31 (universal index, local FTS5)
─────────────────────────────────
  ↑↓ navigate   ↵ open   esc close
```

1. **Empty state = the map**: pinned, recent, and the four most-used actions (Raycast's root). The palette is useful before a key is typed.
2. **Query = everything at once**: fuzzy across pages, actions, objects (the existing FTS5 index), and commands, with the existing recency/frequency ranking (`ranking.ts`) — exact > prefix > fuzzy, recency boost, frequent boost.
3. **Prefix modes** (optional, power): `/` pages, `>` actions, `@` objects, `:` commands — discoverable via a hint row, never required.
4. **Actions run, pages navigate, objects open**: an action item executes in place (the palette closes into its trigger, sharedElement per Escapement §8.3); an object opens its 360; a page navigates. The palette never distinguishes until the result is chosen.
5. **Motion** per Escapement §10.8: backdrop `base`, surface `slower` from center, results stagger 20ms (first arrival only), selection wash slides `fast`, filter crossfades `fast`, exit 0.7× into the trigger.
6. **Migration:** the existing `command-palette.tsx` (groups: Pages + Actions) and `universal-search-modal.tsx` (entities) compose into this one surface behind a feature flag (§18 W1). The `CommandPalette`'s `smartSearch` prop is the seam — it already accepts universal search results.

### 5.2 Ranking rules

1. Pinned and recent always lead on empty query.
2. With a query: exact label match > prefix > substring > fuzzy; equal scores break by recency, then frequency, then role relevance (a teacher's "Attendance" outranks "Analytics").
3. Actions rank above pages at equal relevance (verbs are rarer than nouns), objects after.
4. Never more than 12 results; groups collapse to their top 5 with "N more" on `Enter` at the group footer.

---

## 6. Breadcrumbs — the trail is a map

1. **Registry-driven, not hand-written.** Each page declares its place in the registry (module → object); the breadcrumb component (`breadcrumbs.tsx`) renders `Workspace > Module > Object` from the route, not from a per-page `Crumb[]` array. Deep links and tabs keep the trail correct with zero per-page maintenance.
2. **In the header, always visible** (moves up from content where it is today), so the trail survives scroll and modal-less context changes.
3. **Every crumb is a navigation surface**: hover a module crumb → a mini-menu of that module's sibling objects (the map expands where the cursor is); the object crumb truncates with an ellipsis + tooltip. Keyboard: `Tab` into the trail, `←→` across crumbs, `Enter` jumps.
4. **Object-aware**: the final crumb is the current object (Student 1042) with its identity chip (status dot) — the breadcrumb states *what you are looking at*, matching the object model (§3).
5. **Motion:** crumbs crossfade `fast` on navigation (Escapement §10.1); back-navigation restores the previous trail in reverse, never a fresh fade.

---

## 7. Context navigation, quick actions & the inspector

The context layer answers "what is *here*, and what can I do *here*?" in three cooperating surfaces: in-page navigation, the action band, and the inspector.

### 7.1 Context navigation — the in-page map

1. **Underline tabs** (Corridor §12.8) are the in-page navigation for a module's sub-sections (a 360's Overview / Records / Payments / Activity; Payments' List / Structures / Dues). Tabs replace menu depth — a module is one sidebar row; its sections are tabs, never a sub-tree.
2. **Route-driven**: tabs derive from the registry's `tabs` for the current route; arrow-key navigable, `role="tablist"` semantics (the existing tab pattern, kept).
3. **The action band**: the existing `contextual-actions.tsx` bar carries the page's contextual actions — one **primary action per view** (Corridor rule). The band is keyboard-native (`1–9` when focused) and its primary is the role+time intelligent default (Bridge §7.7).

### 7.2 Quick actions — the verb rail

1. Quick actions are **registry commands** (verbs) surfaced in three places: the palette's Actions group (§5.1), the action band (§7.1), and the inspector (§7.3). Because they are registry commands, the ≤ 3 law audits them.
2. **Quick Create** (`quick-create.tsx`) remains the universal fast-create; the action band's primary is the *intelligent default*; the palette's Actions are the *full verb list*.
3. Rule: a quick action lands on the **working surface** (form, list, 360) — never on an intermediate menu. No quick action may open more than one level deep.

### 7.3 The inspector (context panel)

A right-side drawer (**`⌘.`** or the header's context button) that answers "what can I do *here*?" without leaving the surface.

1. **Content per surface** (from the registry's context rules):
   - On a student 360: quick actions (record payment, mark attendance, send notice), related objects (siblings in class, guardian), cross-module links (fee dues → payment ledger, attendance trend → Watchtower room), history (recent visits to this student).
   - On a list page: module actions, filters recap, related modules.
   - On a chart room: the room's function-code deep link, export, compare, underlying rows (Watchtower §10).
2. **It is a panel, not a modal**: the page stays interactive; the inspector slides East `slow` (260ms), the page parallaxes West 4px (Escapement parallax rule); `Esc` closes and restores focus.
3. **Progressive disclosure**: the inspector shows the three most likely actions as buttons and the rest as a compact list — never a wall.
4. **Keyboard-first**: `⌘.` opens, `↑↓`/`Enter` navigate, `Esc` closes. The inspector is reachable from any surface in one keystroke.

---

## 8. Recent items

1. **Recency × significance** (extends `use-nav-persistence`): an item's rank = recency weight × visit count × object significance (a student edited twice this week outranks a report opened once). The current `addRecentItem` (max 8, plain recency) becomes the significance-weighted feed.
2. **Surfaced in three places**: sidebar Recent section (§4), palette root (§5.1), and the Bridge's Recent rail (dashboard spec §7.5) — one store, three surfaces.
3. **Resume semantics**: a recent item deep-links to where the work actually was (a student 360's open tab, a filtered list), not just the module root — "resume" means *return to the same state*.
4. **Privacy & control**: per-user, never shared, "Clear recent" everywhere it renders, and it clears when a user is removed from the workspace.

---

## 9. Favorites (pins)

1. **Pin from anywhere**: every page's contextual action menu and every object's inspector carries **⋆ Pin to dashboard / sidebar** (persists per role × campus in `use-nav-persistence` — the `FAVORITES_KEY` store extends from paths to `{path, label, pinnedAt}`).
2. **Pinned section** in the sidebar (§4) and **Pinned block** in the palette root (§5.1) — a pin is the highest-persistence signal in the system and outranks all adaptive reordering (Bridge §7.6).
3. **Unpin in place**; pinning a page that is already a module root is allowed (a pin is a *shortcut*, not a duplicate).
4. Keyboard: `Alt+P` on any focused page/object toggles its pin.

---

## 10. History — the way back

1. **Session history** (`use-nav-history`, new): a per-session stack of visited *surfaces* (page + object + tab state). The browser back button remains the OS contract; the Atlas's history is the *semantic* trail ("I was filtering Class 7A payments").
2. **Back respects direction**: navigation back is always a W move (Escapement §10.1); the breadcrumb trail, the inspector's "recently visited", and the palette's Recent all honor the same trail.
3. **Resume after deep links**: jumping in via a notification or search push adds a "← Back to where I was" affordance (the alert's origin), so cross-module navigation never strands the user.
4. **History in the palette**: the Recent block (§5.1) is session-scoped history + older recency, so "what was I doing" and "where was I" are one query.

---

## 11. Workspace switching

1. **Two distinct switches, two distinct weights** (existing components kept): the **campus/organization switcher** (`organization-switcher.tsx`) is the loud one — switching campus is a room change: full-canvas fade to neutral (120ms), new tenant fades in (180ms), per the Corridor's §12.6 and the Bridge's room-change rule. The **role workspace switcher** (`workspace-switcher.tsx`, admin preview) is lighter — it navigates to that workspace's home and re-scopes the registry.
2. **Workspace as identity**: the current workspace (role + campus) is visible in the header and the sidebar footer with the identity chip (existing pattern); switching is deliberate, keyboard-reachable (`Ctrl+Shift+W` opens the switcher), and always reversible.
3. **Cross-workspace navigation is allowed but explicit**: a teacher previewing the admin workspace lands on the admin home with a "Back to my workspace" affordance — never silently.

---

## 12. Cross-module navigation

1. **Objects are links**: every student/teacher/class ID renders as a link to its 360 everywhere it appears (tables, alerts, charts, timeline). The universal search index already returns `route` per entity (§search-api `IndexSyncItem.route`) — the Atlas standardizes "click any object, land on its 360".
2. **Related-object rails**: 360 pages carry a "Related" rail (siblings, guardian, dues, attendance) that is itself cross-module navigation — a student's fee dues link to the payment ledger, whose rows link back.
3. **Deep links are the contract**: routes never change (§18); any surface can deep-link to any object via `route`, and the Atlas's breadcrumbs, palette, and history all resolve from the route alone.
4. **The Watchtower connection**: analytics rooms deep-link to underlying rows and objects (Watchtower §6.2, ≤3 clicks) — cross-module navigation is a *property of objects*, not a feature of pages.

---

## 13. Keyboard-first experience

### 13.1 The shortcut map (extends `keyboard-shortcuts-dialog.tsx`)

| Scope | Shortcut | Action |
|---|---|---|
| Global | `⌘K` | Command surface (everything) |
| Global | `⌘.` | Context panel (inspector) |
| Global | `⌘B` | Toggle sidebar rail |
| Global | `?` | Shortcuts dialog |
| Global | `⌘,` | Settings |
| Global | `Ctrl+Shift+W` | Workspace switcher |
| Global | `Alt+P` | Pin current page/object |
| Jump | `G` `S` / `G` `T` / `G` `C` | Students / Teachers / Classes |
| Jump | `G` `A` / `G` `F` / `G` `R` | Attendance / Fees / Reports |
| Jump | `G` `I` | Command Center (Inbox analog) |
| Jump | `G` `G` | Go back to where I was (history) |
| Sidebar | `↑↓` + type-to-filter | Navigate the map |
| Breadcrumbs | `←→` + `Enter` | Walk the trail |
| Tables/lists | `↑↓` · `Space` · `Enter` | Row nav (existing) |

### 13.2 Rules

1. **Every mouse action has a keyboard path** — hover reveals include focus parity (Gloss H07/F07); the inspector, palette, and breadcrumbs are all keyboard-native.
2. **No shortcut hijacks a system default** without an off switch; all shortcuts are discoverable in the `?` dialog.
3. **Chords are two keystrokes, then an interaction** — `G S` is a chord (one logical interaction for the ≤ 3 law: chord + Enter = 2 interactions).

---

## 14. Focus mode

1. **What it is**: chrome collapses — sidebar to rail, header to a single slim line (search + back), content full-bleed. The current surface (a 360, a chart room, a document) becomes the room.
2. **Entry**: `⌘Shift F`, or the surface's "Focus" action; chrome collapses `slow` (260ms, E/W move per Escapement §10.10). **Exit**: `Esc` or `⌘Shift F` restores the exact layout and focus.
3. **What stays**: the command surface (`⌘K`) and the inspector (`⌘.`) — the two keyboard natives — so focus mode is not a cage.
4. **Relationship to the Bridge's Focus mode**: identical mechanic (Bridge §8.1); the navigation spec contributes the *chrome* rules, the Bridge contributes the *widget* rules.

---

## 15. Architecture — files & APIs

| Layer | Exists today | v4 work |
|---|---|---|
| Registry | `types/roles.ts` (`getNavSectionsForRole`, `ROLE_CONFIG`, `getHomeRoute`) | `nav-registry.ts`: modules + commands + routes + context rules; `roles.ts` becomes the role-filter over it. Sidebar, palette, breadcrumbs, jump map all consume the registry |
| Command surface | `ui/command-palette.tsx` (Pages+Actions, `smartSearch` seam), `ui/universal-search-modal.tsx` (FTS5), `hooks/use-universal-search.ts` | One `CommandSurface` (⌘K): merge both; empty-state = pins/recents/actions; ranking per §5.2 |
| Sidebar | `layout/sidebar.tsx` | Add Pinned + Recent sections (§4, §8–9); type-to-filter; flat groups from registry |
| Breadcrumbs | `ui/breadcrumbs.tsx` (manual `Crumb[]`) | Registry-driven `use-breadcrumbs`; header placement; crumb mini-menus (§6) |
| Context layer | `layout/contextual-actions.tsx`, underline tabs (existing) | Route-driven tabs + action band from the registry (§7.1); quick actions as registry commands (§7.2); new `layout/context-panel.tsx` (inspector, §7.3) + `use-context-panel` |
| Persistence | `hooks/use-nav-persistence.ts` (recent ×8, favorites paths, collapse) | Extend: significance weighting (§8), `{path,label,pinnedAt}` pins (§9), session history (§10) |
| History | browser back only | New `hooks/use-nav-history.ts` (§10) |
| Header | `layout/header.tsx` | Unified ⌘K trigger, breadcrumb slot, context trigger, focus toggle |
| Jump map | `keyboard-shortcuts-dialog.tsx` | `G`-chords registry (§13), wired through the command surface |
| Desktop parity | Forge spec §12–13 | Same registry shape; keyframe equivalents for rail/palette/drawer |

---

## 16. User flows (the law in practice)

### Flow A — Record a payment for a student (before → after)

```
BEFORE (ERP):                       AFTER (Atlas):
1. Fees                             1. ⌘K → "pay ram"
2. Payments                         2. [Student 1042 · Pay]  ← ranked result
3. New payment                      3. Enter → payment form, student prefilled
4. Find student                       (3 interactions)
5. Fill + save
   (5 interactions)
```

### Flow B — Find and open a student (search-first)

```
⌘K → "1042" → Enter        Student 1042 360        (2 interactions)
Sidebar → Students → row   Student 1042 360        (2 interactions)
```

### Flow C — From an alert to the work (cross-module)

```
Notification: "Fee due: Student 1042"
  → click → Student 1042 360 (deep link)
  → ⌘. → inspector → "Record payment"
  → payment form, student prefilled              (3 interactions)
  → "← Back to where I was" restores the alert origin
```

### Flow D — Resume yesterday's work

```
⌘K → (empty query) → Recent → Student 1042 · Payments
  → Enter → the exact filtered list left open yesterday   (2 interactions)
```

### Flow E — Switch workspace

```
Ctrl+Shift+W → pick workspace → room change (fade 120/180ms)
  → "Back to my workspace" affordance if previewing        (2 interactions)
```

---

## 17. Interaction diagrams

### 17.1 The command surface state machine

```
         ┌────────────┐
         │   closed   │
         └─────┬──────┘
               │ ⌘K
               ▼
         ┌────────────┐  type       ┌──────────────┐
         │  root map  │───────────► │   results    │
         │ pins/recents│  no match  │ ranked list  │
         └──┬───┬───┬──┘◄──────────└──┬───┬───────┘
            │   │   │     backspace   │   │
       Enter│   │   │  ▲/▼ + Enter    │   │
            ▼   ▼   ▼                 ▼   ▼
       action  page  object        action page object
       runs   navigates opens 360  runs  navigates opens 360
            │   │   │                 │   │
            └───┴───┴──► exit 0.7× into trigger ──► closed
```

### 17.2 The three surfaces, one registry

```
        ┌──────────────────────────┐
        │       nav-registry       │  modules · commands · routes · context
        └───┬──────────┬───────────┘
     renders│          │renders
        ┌───▼───┐   ┌───▼────┐   ┌──────────────┐
        │sidebar│   │ palette │   │  breadcrumbs │
        │§4     │   │ §5      │   │  §6          │
        └───────┘   └─────────┘   └──────┬───────┘
                                         │ route → trail
                                 any deep link resolves everywhere
```

### 17.3 Sidebar interaction map

```
sidebar focus
   ├─ ↑↓  move selection
   ├─ type  filter modules (type-ahead)
   ├─ Enter  open selected
   ├─ ⌘B  collapse to rail (icons + tooltips; recents → palette)
   ├─ ⋆ on hover  pin/unpin
   └─ Esc  return focus to content
```

---

## 18. Migration strategy

Routes never change; every deep link keeps working. The Atlas lands in six non-breaking waves behind feature flags:

| Wave | Scope | Success gate |
|---|---|---|
| **W0 · Audit** | Route the audit: every action in the registry, current vs ≤3 path | The backlog: every action missing a ≤3 path, listed with its fix |
| **W1 · One ⌘K** | Merge command palette + universal search into `CommandSurface` (flag: `atlas-command`) | Both triggers (⌘K, header) open the same surface; pages/actions/objects all rank together; old modals deleted behind flag |
| **W2 · Flat sidebar** | Registry refactor; sidebar renders pins → recents → flat modules (flag: `atlas-sidebar`) | Admin tree collapses to ≤ 6 groups × ≤ 4 rows; role shape identical; rail + mobile parity |
| **W3 · Trail & pins** | Registry-driven breadcrumbs in header; crumb mini-menus; pins surfaced (§9); significance-weighted recents (§8) | Breadcrumb zero-maintenance (no per-page `Crumb[]`); pins render in sidebar + palette; recents rank by significance |
| **W4 · Context & history** | Context layer (§7: route tabs, action band, quick actions as commands, inspector); session history + resume (§10) | `⌘.` opens from any surface; tabs derive from the registry; every quick action is an auditable registry command; deep-link jumps offer "back to where I was"; history feeds palette Recent |
| **W5 · Keyboard & focus** | `G`-chords (§13); focus mode (§14); shortcuts dialog update | Every listed shortcut works and is discoverable; focus mode restores layout exactly; no hijacked defaults |
| **W6 · Hardening** | The ≤3 law audit in CI; a11y pass; reduced-motion verification; Forge parity | CI fails on any registry action without a ≤3 path; all surfaces keyboard-reachable; desktop renders the same map |

**Rollback:** each wave is independent and flag-gated; a regression reverts one flag, not the app. The unified command surface is the only wave with a cross-surface change — it is sequenced first so every later wave builds on the final interaction model.

---

## 19. Acceptance criteria

- **The law:** every action in the registry has a proven ≤ 3-interaction path; the audit is a CI gate.
- **One command surface:** `⌘K` reaches pages, actions, objects, and commands; empty query shows pins, recents, and top actions.
- **Zero-maintenance breadcrumbs:** no per-page `Crumb[]` arrays remain; the trail derives from the route.
- **Pins & recents live:** both render in sidebar and palette; per-role × campus persistence; clear/unpin everywhere.
- **Resume:** deep links and notifications always offer "back to where I was".
- **Keyboard:** 100% of interactions keyboard-reachable; every shortcut discoverable in the `?` dialog.
- **No broken links:** the route map is unchanged across all waves; the migration audit passes with zero broken deep links.

---

*The Atlas is a map that fits in one hand: a command, a jump, a click — three interactions to anywhere. The tree is gone; what remains is a registry, a trail, and a keyboard. Per the re-capture loop, the map earns its place by staying true to every route it promises.*
