# SDMAS Dashboard System — v4 Specification

**Codename:** *The Bridge*
**Status:** Draft for review · **Owner:** Product Design · **Version:** 4.0.0
**Scope:** apps/web — the `/dashboard` home and every role dashboard (principal, accountant, staff, teacher, student, parent, command center)
**Companion docs:** `docs/DESIGN_SYSTEM_V3.md` (*Corridor* — tokens), `docs/MOTION_SYSTEM_V4.md` (*Escapement* — motion), `docs/ANALYTICS_SYSTEM_V3.md` (*Watchtower* — chart rooms, live floor, status language), `docs/MICRO_INTERACTIONS_V3.md` (*Gloss* — interaction catalog)

> *The Watchtower is the view from the top of the school. The Bridge is where the captain actually works: the strip of numbers that tell you the ship is healthy, the list of what needs you today, and the work you left half-finished yesterday — all on one screen, all within eight seconds.*

The dashboard is the **operational home** — the surface a principal, teacher, or accountant lands on and works from. It is not the analytics layer (the Watchtower owns chart rooms); it is the **orientation + action layer**: the morning scan, the priorities, the resume points, the quick actions. This spec defines its anatomy, its widget system, its modes, and its performance contract.

---

## 0. Relationship to the Watchtower

| | Watchtower (analytics) | Bridge (dashboard) |
|---|---|---|
| Job | Watch · Investigate · Decide | Orient · Act · Return |
| Content | Chart rooms, terminals, drill-downs | KPI strip, priorities, recent work, quick actions |
| Density | Comfortable, terminal-grade | Adaptive by mode (focus / productivity) |
| Motion | Draw-in, count-up, live pulse | Same tokens, lighter budget (§10) |
| Charts | Full chart rooms | **Widget-sized chart rooms** (mini variants, §7.8) |

The Bridge **embeds** the Watchtower's chart grammar at widget scale. Every rule in the Watchtower (readout-as-header, status language, provenance, draw-in on first render only) applies unchanged; this spec adds the widget frame around it.

---

## 1. Thesis — three jobs, one screen

1. **Orient** — the morning scan: is the school healthy? In ≤ 8 seconds, no label read twice.
2. **Act** — from any card to the exact place in ≤ 2 clicks or ≤ 4 keystrokes. No number is a dead end.
3. **Return** — pick up yesterday's work instantly: recent items, pinned items, in-flight jobs.

Anything that serves none of these three is rejected. Specifically rejected: hero gradients, decorative hero cards, charts that exist to fill space, marquee or ambient motion, "in case you missed it" feeds without a purpose, and any widget whose data has no owner.

**The posture:** Stripe's precision for the KPI strip, Linear's command-first speed for recent work and pins, Vercel's adaptive widget grid for structure, Manus's transparency for priorities. Data decides what we show; the user decides what stays.

---

## 2. Sources & extraction — principles only

| Source | What it demonstrates | Principle extracted | Translation into SDMAS |
|---|---|---|---|
| **Stripe Dashboard** | A 4–6 tile KPI strip with sparklines and delta chips; crosshair hover readouts; throttled, non-flickering live updates; structured empty states with one CTA | **The metric strip + the calm update** | The KPI strip (§7.1) is the top zone, always: headline numeral, sparkline, delta chip, hover preview. Live updates pulse once and rest (§7.2). |
| **Linear** | Command-first (⌘K) navigation; compact chrome; keyboard-driven "recent" surfaces; focus mode collapses chrome to maximize workspace | **Keyboard-first resumption + focus as a mode** | Recent work (§7.5) is keyboard-navigable and resume-on-Enter; Focus mode (§8.1) collapses chrome and shows one surface. |
| **Vercel** | Adaptive workspace layouts; project cards as mini-dashboards; content-shaped skeletons that prevent layout shift | **Adaptive widget grid + the layout-stable skeleton** | The layout engine (§4) reflows per role, campus, and window; every widget ships a content-shaped skeleton (§9) with zero CLS. |
| **Manus** | Agentic "today's priorities" ranked by urgency; progressive disclosure of steps; transparency microcopy ("action + item + limit"); persistent checklists | **Priorities with provenance + disclosure by depth** | Today's priorities (§7.4) rank by urgency/blocker with a stated reason; suggestions and steps disclose progressively (§7.6); long jobs run as checklists with a visible state (§7.2). |

---

## 3. The zones — anatomy of the Bridge

One vertical column, five zones, reading order:

```
┌──────────────────────────────────────────────────────────────┐
│ CONTEXT BAND   Greeting · date · term phase · campus · ⌘K     │  always present
├──────────────────────────────────────────────────────────────┤
│ KPI STRIP      4–6 live metrics (numeral + sparkline + delta) │  first scan target
├──────────────────────────────────────────────────────────────┤
│ PRIORITY BAND  Today's priorities · suggestions (chip dock)   │  what needs you
├──────────────────────────────────────────────────────────────┤
│ WORK RAILS     Recent work · pinned items (two rails)         │  resume points
├──────────────────────────────────────────────────────────────┤
│ WIDGET GRID    user-customizable dynamic cards                │  the working surface
└──────────────────────────────────────────────────────────────┘
```

### 3.1 Zone rules

1. **The KPI strip is always first** and always visible. It is the scan target; nothing may render above it except the context band.
2. **The priority band shows at most 5 items.** More is a feed, not a priority list; overflow collapses into the "All priorities" row.
3. **Work rails are two, not five** — Recent work and Pinned. A third rail ("favorites", "colleagues") is a widget, not a rail.
4. **The widget grid is the only user-mutable zone** (§5). The four zones above it are fixed anatomy; the user customizes what's below.
5. **Every zone degrades independently** — a failed widget never blocks the strip above it (best-effort per surface, per the existing teacher-dashboard pattern).
6. All numbers are `tabular-nums`. All deltas carry text ("▲2.1 vs last week"), never color alone (status language, Watchtower §4.3).

---

## 4. The layout engine

### 4.1 The grid

- **12-column grid**, `space.lg` (24px) gutters, content max-width 1440 (dashboards use more of the window than regular pages; the 1280 cap does not apply).
- **KPI strip:** `auto-fill minmax(200px, 1fr)` — 4 tiles at 1280, 6 at 1600+. Never fewer than 4 tiles visible.
- **Widget grid:** a 12-column flow with widget spans of 3/6/9/12 (1x1, 2x1, 3x1, full) — no fractional spans, no overlapping placements in the default flow. Resize is span-based, never pixel-freeform (keeps the grid calm and reflowable).
- **Adaptive reflow:** window width, role, density mode, and focus mode feed one `GridConfig`; any change reflows via **FLIP** (Escapement §12.3), never by animating layout properties.

### 4.2 Role-aware defaults

The layout engine ships a **default template per role** (the widget set + order the role gets on first visit); the user's customization overlays it:

| Role | KPI strip | Priority | Rails | Grid defaults |
|---|---|---|---|---|
| Principal | attendance %, collected, overdue, alerts, enrollment, risk | Term goals, risk alerts | Recent · Pinned | Command Center widgets, matrix heatmap, goal arcs |
| Accountant | collected today, recovery %, overdue aging, outstanding | Fee deadline clusters | Recent · Pinned | Collection trend, aging histogram, bullet grid |
| Teacher | my attendance load, classes today, pending marks, alerts | Next class, pending grading | Recent · Pinned | Class roster sparkline, timetable heat band |
| Student | attendance %, fee status, next report card | Upcoming exams, dues | Recent · Pinned | Own trend, goals |
| Parent | child attendance %, fees due, notices | Notices, payments due | Recent · Pinned | Child trend (1.5× comfort, portal rules) |

### 4.3 Persistence

- Layout + mode + strip selection persist **per role × campus** (the `useNavPersistence` pattern) in localStorage; a **Reset to default** action restores the template.
- Persisted layout is a **contract**: a widget id that no longer exists (feature removed, permission lost) is dropped silently; its slot is released, the grid reflows via FLIP. Never a broken tile.

### 4.4 Drag & reorder

- Widgets and rails reorder via **drag with FLIP reflow** (Escapement drag rules: 1:1 tracking, ghost at 60%, drop settle). Reorder is disabled for the four fixed zones.
- Dragging is opt-in per widget via the card's grip handle (hover/focus reveal, keyboard parity via `Alt+↑↓`).

---

## 5. The widget system

### 5.1 The registry

Every widget is a **registry entry** — declarative, typed, permission-scoped. No widget is authored ad hoc on a page.

| Field | Example | Rules |
|---|---|---|
| `id` | `attendance.pulse` | Stable, namespaced; persisted in layouts |
| `title` | "Attendance Pulse" | `h4`, one line |
| `kind` | `kpi` / `chart` / `list` / `timeline` / `alert` / `action` / `priority` / `recent` / `pinned` / `suggestion` | Determines anatomy + motion (§7) |
| `sizes` | `[6, 12]` | Legal spans from {3, 6, 9, 12} |
| `data` | `attendanceApi.getPulse` | Single fetch; per-widget error/empty states |
| `refresh` | `live` / `30s` / `on-visit` / `manual` | `live` only for the licensed live set (§7.2) |
| `skeleton` | shape id (§9) | Content-shaped, layout-stable |
| `permission` | `attendance.view` | Dropped silently if missing (§4.3) |
| `modes` | `all` / `focus` / `productivity` | Which modes may host it (§8) |

### 5.2 Lifecycle

```
mount → skeleton (§9) → data → idle / live (§7.2) → pause (out of view) → resume
```

1. **Pause on visibility:** a widget off-screen (IntersectionObserver) pauses its refresh loop and its live updates; it resumes on return with a **single pulse** (not a replay of everything missed).
2. **Error/empty are per-widget:** a widget that fails renders its own compact state (Corridor §13.2/13.3 patterns at card scale, per the Watchtower's §11 row) — the rest of the Bridge stays alive. Retry is local.
3. **Idle fetch:** data for widgets below the fold fetches after first paint (requestIdleCallback) — the scan target (strip + priority) loads first.
4. **Ownership:** every widget displays its data source + last-updated in a `caption` footer (provenance, Watchtower §2) — a stale widget says so.

### 5.3 Customization

- The **Add widgets** palette (⌘K → "Add widget", or a `+` in the grid header): registry entries the role may add, each with a mini preview.
- Customization = add / remove / reorder / resize (span). Everything persists (§4.3). Removing a widget never deletes its data.
- The four fixed zones are not customizable (anatomy, not content); the user customizes **what's below the line**.

### 5.4 Dynamic cards (continuous identity)

A card is one identity across its states:

- **Size morph:** resizing a card is a FLIP (Escapement §10.11) — the card *is* the widget, it grows, its contents re-flow (the chart re-axes, the list gains columns). Never a remount.
- **State morph:** card ↔ expanded preview ↔ detail surface are the same identity (§7.9 progressive disclosure) — the card expands in place, never a modal for glance-level info.
- **Density morph:** Comfortable ↔ Compact changes row heights via transform at `base` (180ms), per Corridor §6.3.

---

## 6. Context awareness

The Bridge adapts its **content and ordering** to four signals, combined:

| Signal | Effect | Example |
|---|---|---|
| **Role** | Widget set + defaults (§4.2) | Accountant sees the aging histogram; teacher doesn't |
| **Time of day** | Morning = attendance pulse first; afternoon = grading/marks; month-end = fee clusters | 8:30 AM: pulse strip leads |
| **Term phase** | Admissions season → enrollment funnel widget; exam week → results readiness; fee deadline → collection goal | March: fee goal arc surfaces |
| **Attention** | Unread alerts, in-flight jobs, near-threshold goals reorder the priority band | A risk alert outranks a routine suggestion |

**Rules:** context shifts are **quiet** — they reorder and re-surface, they never pop a modal and never animate more than one zone at once. Every context-driven change is attributable (the priority item states *why* it is here: "Fee deadline in 3 days"). A context signal with no reason attached is rejected.

---

## 7. The widget catalog

### 7.1 KPI strip (Stripe) — the scan target

- **Anatomy:** 4–6 tiles; each = label (`micro`, uppercase) → **headline numeral** (`text-2xl` w700 tabular, count-up ≤500ms, Escapement §10.6) → **sparkline** (1.5px, 40px, `dv.*`, drawn once on load) → **delta chip** (▲/▼/→ + text, status color per *goal direction*, Watchtower §4.3).
- **Hover preview:** hovering a tile swaps the delta line for a **mini chart preview** (the tile's sparkline at 2× with the crosshair readout, Gloss H13) — the headline number answers the "what", the preview answers the "why".
- **Click:** any tile drills to its room (§7.9). No tile is ever decorative.
- **Refresh:** live tiles (licensed live set, §7.2) pulse once on change; cached tiles show provenance and a quiet refresh affordance.

### 7.2 Live metrics

- **The live set is small and licensed:** attendance marked today, collected today, alerts open, jobs running, sync state. Everything else is report-cache — liveness is a property of the data, not a styling choice (Watchtower §7).
- **Transport:** SSE push-first, poll-fallback (30s), stale-marked provenance dot (brand breathing = connected; amber = stale; grey = offline).
- **Arrival:** a changed value **pulses once** (≤300ms, value only, never the whole tile); a changed row/cell gets a one-shot status wash (180ms). If three numbers change in the same second: one pulse on the loudest, washes on the rest.
- **"Since midnight" counters** count up as they arrive (watchtower pulse strip); the tile never re-renders for every tick — the SSE handler writes the numeral (Escapement §12.1).
- **Batching:** live updates batch per animation frame; at most one live update per tile per 250ms.

### 7.3 Animated KPIs

Covered by §7.1 (count-up) and §7.2 (pulse). Rules: count-up ≤ 500ms, `emphasized-decelerate`, tabular, and **never** re-count on every refresh — the value settles, pulses, and rests. A KPI that animates twice in one minute is broken.

### 7.4 Today's priorities (Manus) — the what-needs-you zone

- **Anatomy:** a vertical list of ≤ 5 priority rows, each: urgency chip (status color + glyph) → **action sentence** → **reason line** (`caption`: why it is here) → inline action.
- **The transparency microcopy formula:** `action + item + limit` — "Record attendance for Class 7A (closes in 25 min)", "Clear 12 overdue fee notices before month-end". Never "You have pending items."
- **Progressive disclosure:** a priority row expands in place (FLIP, §5.4) to reveal **steps** for multi-step tasks (a running job shows a persistent checklist: complete / processing / pending — Manus's dynamic checklist). Details never leap to a modal for glance.
- **Dismissal:** `Esc`/× removes from today (recoverable in "All priorities"); completion reorders the list.
- **Keyboard:** `↑↓` move the selection, `Enter` opens the action, `Space` dismisses.
- **Ranking:** urgency (deadline distance) × blocker weight × owner scope — the algorithm is deterministic and explainable; each row states its reason.

### 7.5 Recent work (Linear) — the resume rail

- **Anatomy:** a horizontal rail of resume cards (or compact rows in productivity mode): item icon, title, context line ("7A attendance · edited 12m ago"), a resume affordance.
- **Order:** recency × significance (a student you edited twice this week outranks a report you opened once); hover preview shows the item's state at a glance.
- **Behavior:** `Enter`/click resumes exactly where you left (deep link). Keyboard-first: `Alt+←→` moves, `Enter` resumes. ≤ 8 visible; "View all" is a list widget.
- **Privacy note:** recent work is per-user, never shared, and clears on explicit "Clear recent".

### 7.6 Pinned items

- **Pin from anywhere:** any page's contextual action menu carries "Pin to dashboard" (the existing contextual-actions pattern extends a pin affordance).
- **Anatomy:** a pinned rail next to Recent work (or merged in productivity mode): pinned items carry a pin glyph, outrank recent work, and persist per role (§4.3).
- **Behavior:** unpin from the rail; pinned items are stable under context shifts (§6) — a pin is an explicit user choice and outranks all adaptive reordering.

### 7.7 Suggestions & quick actions

- **Suggestions** (chip dock under the priority band): contextual one-tap actions ("Record attendance", "Review 3 low-attendance students", "Approve 4 leave requests"). Each chip = verb + object; clicking executes or opens the exact surface. Dismissible (`×`), snoozable (until tomorrow), sourced from the same signals as priorities (§6) — but **suggestions are optional, priorities are not**.
- **Quick actions:** one **primary action per view** (existing rule) rendered in the context band — the single most likely action for the role + time (teacher at 8 AM: "Record attendance"; accountant at month-end: "New fee structure"). Quick Create (existing `quick-create.tsx`) stays the universal fast-create; the context band action is the *intelligent default*.
- All quick actions are keyboard-reachable (`1–9` when the context band is focused, per the shortcuts sheet).

### 7.8 Interactive charts (widget-sized Watchtower rooms)

- Widgets embed **chart rooms at widget scale**: the room keeps its header (title, window presets), its **readout-as-header** (the headline number + delta live-replaces with the hovered value), and its provenance footer — shrunk, never stripped (Watchtower §2).
- Mini variants: **sparkline + sparkgrid** (strip tiles), **mini trend** (line/area, 1D/1W), **goal arc** (donut + needle, §7.4's fee goal), **bullet** (target vs actual), **heat band** (24h floor, timetable), **mini matrix** (classes × weeks).
- Interactions keep full parity: hover crosshair + readout swap (120ms), click drills (§7.9), window presets crossfade 160ms, comparison `C`. Draw-in on first render only (500ms `draw`), never on window change.
- Chart widgets respect the **≤ 6 series** and status-language rules unchanged (Watchtower §3.3, §4.3).

### 7.9 Progressive disclosure & hover previews

| Depth | Surface | When |
|---|---|---|
| 0 — Tile | KPI tile / card header | Always (the glance) |
| 1 — Preview | hover popover (mini chart / item state, Gloss O15) | Hover / focus on tile, card, recent item |
| 2 — Expand | card expands in place (FLIP, §5.4) revealing detail | "Expand" / click on preview |
| 3 — Detail | the destination surface (room, list, entity) | "Open", `Enter`, or drill click |

Rules: **no modals for glance-level info** — the expansion is in place, reversible, and the page never leaves until depth 3. Every drill ≤ 2 clicks from the dashboard (§1.2). Esc closes any open depth and returns focus to the trigger (Gloss O-rules).

---

## 8. Modes

### 8.1 Focus mode

The deep-work surface: **one widget, full width, chrome collapsed** (sidebar to rail, header minimal — Linear's focus mode).

- Entry: a per-widget "Focus" action, or `F` with a widget selected; the widget FLIPs to full canvas, chrome collapses `slow` (260ms).
- What stays: the widget + its room chrome + Esc/pop-out. Everything else hides.
- Exit: `Esc` restores the exact layout; focus returns to the widget's trigger.
- Focus mode is available to all widget kinds; charts get it natively (Watchtower fullscreen, §6.5, remains for terminal rooms).

### 8.2 Productivity mode

The throughput surface: **compact density + strip-first + keyboard hints**.

- Density → Compact (36px rows, tighter gutters, Corridor §6.3), animating at `base`.
- The widget grid reorders to a **stacked list layout** (one column, dense rows) — "scan the list, not the grid".
- Keyboard hints appear on hover/focus of interactive rows (`Enter` resume, `Space` quick action).
- KPI strip stays first and full-width; everything below compresses.
- Entry: mode toggle in the context band (persisted per role); `P` toggles. Exit restores the exact layout.

### 8.3 Mode matrix

| Mode | Chrome | Density | Widget grid | Entry |
|---|---|---|---|---|
| **Standard** | full | comfortable | grid | default |
| **Focus** | collapsed to rail | comfortable | one widget, full canvas | `F` on a widget |
| **Productivity** | full | compact | stacked list | `P` / toggle |
| **Reduced motion** | full | comfortable | grid | global tier (§10.3) |

---

## 9. Skeleton loading

The Vercel rule, made contract:

1. **Content-shaped:** every widget's skeleton mirrors its final layout *exactly* — same dimensions, same text block sizes, same chart aspect. The skeleton is the widget's ghost (Corridor P3). Zero CLS; the grid never jumps when data lands.
2. **Skeleton shapes per kind:** KPI tile (numeral block + 40px sparkline block + chip block), chart room (header block + plot block), list (3–5 row blocks), priority (5 row blocks with chip blocks).
3. **Animation:** shimmer sweep 1.6s `linear` (the licensed loop); the strip and priority band skeleton fade in `fast` (120ms); below-fold widgets render skeleton only when scrolled near (idle fetch, §5.2).
4. **Swap:** skeleton → content is a crossfade at `base` (180ms), in place — the layout was already true.
5. **Never a centered spinner** for a zone; spinners appear only inside an action (button loading, Escapement §10.6).

---

## 10. Animation strategy (the Escapement on the Bridge)

### 10.1 Zone-level moves

| Element | Move (Escapement spec) | Resolved |
|---|---|---|
| Strip enter | `Fade + 4px Slide`, D2·I2 | 180ms `base`, no stagger (the scan must not parade) |
| Priority rows | `Fade + 2px Slide`, stagger 20ms | ≤ 150ms, reading order |
| Work rails | `Slide E`, D3·I2 | 260ms `slow` |
| Widget enter (grid) | `Fade + 4px Slide`, stagger 20ms | ≤ 150ms; never re-stagger on reorder (FLIP only) |
| Card resize / reorder | FLIP | 260ms `slow`, transform-only |
| Card expand (disclosure) | FLIP | 260ms `slow` + contents stagger ≤ 150ms |
| Live value arrival | one `Pulse` | ≤ 300ms, value only (§7.2) |
| Changed cell/row | status wash | 180ms one-shot |
| Hover preview | `Fade`, D1·I1 | 120ms `fast`, 300ms trigger delay (Gloss X15) |
| Focus ring | `Fade fast + Draw base` | 120 + 180ms, element never moves |
| Mode switch | chrome `Slide E/W`, grid FLIP | 260ms; content never re-staggers |
| Skeleton → content | crossfade | 180ms in place |

### 10.2 Budget

The Bridge runs a **lighter budget** than terminal surfaces (Escapement §12.1): ≤ 3 concurrent movers during any interaction, timeline ≤ 500ms, one Z move and one Pulse system-wide, **no ambient loops** beyond the licensed four (shimmer, spinner, sync breath, progress). Live tiles pulse; they never bounce.

### 10.3 Reduced motion

All moves tier through the Escapement's provider (`precise` / `efficient` / `minimal`): `efficient` keeps washes and crossfades, `minimal` makes everything instant with a static reading. The KPI count-up collapses to the final value; live pulses become color swaps. No information hierarchy ever depends on motion.

---

## 11. Performance optimization

| Contract | Cap | Enforcement |
|---|---|---|
| First data paint (strip + priority) | ≤ 500ms after fetch resolves | idle-fetch below fold (§5.2) |
| Layout shift (CLS) | 0 during skeleton → content | content-shaped skeletons (§9) |
| Concurrent animated elements | ≤ 3 per interaction, 1 Z, 1 Pulse | Escapement engine |
| Live update render cost | write the numeral, never re-render the tile (§7.2) | SSE handler contract |
| Chart widgets | draw-in once; crossfade (160ms) on window change; ≤ 30fps of updates | Watchtower §11 |
| Recent work / priority lists | virtualize > 20 rows; ≥ 40 rows at 60fps | list widget contract |
| Grid reflow (FLIP) | measure once, transform-only, ≤ 8 FLIP elements at once | Escapement §12 |
| Fetch fan-out | strip + priority first; below-fold via idle; refetch coalescing | data layer |
| `will-change` | ≤ 8 elements, owned by the engine, removed on finish | Escapement §12.4 |

**The strip is sacred:** the KPI strip must paint within one frame of its data arriving — it is the scan target. Any optimization that risks the strip's first paint is a regression.

---

## 12. Architecture — files & APIs

Grounded in the current codebase; gaps are the roadmap.

| Layer | Concept | Exists today | v4 work |
|---|---|---|---|
| Data | per-widget fetch + best-effort failure | `pages/dashboard.tsx` (Promise.all + local error), `api/analytics/*` | `useDashboardWidget` hook (fetch/refresh/pause/error); widget registry types |
| Grid | 12-col engine, spans, FLIP reflow | `grid` utility classes, `useFlipList` (motion) | `dashboard-grid.tsx` (GridConfig, spans, persistence), `useDashboardLayout` (per role × campus) |
| Widgets | registry + kinds | `components/analytics/kpi-card.tsx`, five chart components, `components/ui/empty-state.tsx` | `widgets/` registry + `KpiTile`, `PriorityList`, `RecentRail`, `PinnedRail`, `SuggestionDock`, `ActionBand`, chart widgets (thin Watchtower-room wrappers) |
| Live | SSE live floor | SSE patterns (`/api/notifications/events`) | `useLiveMetric` (licensed live set, batching, pulse) |
| Modes | focus / productivity | — | `useDashboardMode` (context band controls, persistence) |
| Motion | Escapement moves | `lib/motion/*` | consume via `useMove`; no new motion code on the Bridge |
| Persistence | layout per role × campus | `useNavPersistence` | extend to dashboard layout |

**Rebuild path for `pages/dashboard.tsx`:** the current page (hero gradient + mini metrics + attendance pulse + needs-attention + quick nav) becomes a composition of the Bridge: context band → KPI strip → priority band → work rails → widget grid. The hero gradient is rejected (§1); the attention cards become priority rows; Quick Navigation merges into Recent work + the command palette (⌘K). The KPI tile (`components/analytics/kpi-card.tsx`) is replaced by the §7.1 anatomy — and its hardcoded Tailwind hexes die here, exactly as the Watchtower's §14 requires for chart components.

---

## 13. Implementation roadmap

| Wave | Scope | Acceptance criteria |
|---|---|---|
| **W0 · Audit (1 wk)** | Diff the 8 dashboard pages against this spec | A per-page table: zones present, widget kinds, motion conformance, budget; violations = backlog |
| **W1 · Grid & skeleton (2 wk)** | `dashboard-grid.tsx`, `useDashboardLayout`, content-shaped skeleton set | Zero CLS on every dashboard; strip paints within one frame of data; grid FLIPs on reflow; layout persists per role × campus |
| **W2 · Widget system (2–3 wk)** | Registry + kinds (KPI tile, chart rooms at widget scale, list, alert); customization (add/remove/reorder/resize) | Every dashboard is a registry composition; no ad hoc dashboard markup remains; add-widget palette works; removal drops silently |
| **W3 · Orientation surfaces (2 wk)** | Context band + KPI strip + priorities + suggestions + quick actions | Morning scan ≤ 8s; every priority row states its reason; quick action = intelligent default per role/time; all keyboard-reachable |
| **W4 · Resume surfaces (2 wk)** | Recent work + pinned rails; pin affordance from contextual actions; deep-link resume | Pin persists per role; recent work resumes exactly; keyboard-first rails; privacy rules enforced |
| **W5 · Modes & live (2 wk)** | Focus + productivity modes; live metric set + batching + pulse | Modes enter/exit exactly restore layout; live set is licensed (no drift); one pulse per change; strip never re-renders per tick |
| **W6 · Hardening (2 wk)** | Performance audit per §11; a11y pass (§14); reduced-motion verification; re-capture loop | All §11 caps verified in CI; 60fps on 40+ widgets mid-range laptop; every interaction has keyboard parity |

**Cross-client:** the Bridge has a CustomTkinter equivalent (Forge spec): the same zones render in the desktop client with keyframe motion (§12–13 of the Forge). W6 includes a parity pass (layout template equality, same live set).

---

## 14. Accessibility

1. Every zone and widget has a **textual summary** (`aria-label` pattern from the Watchtower: "Attendance, 94.2%, up 2.1 from last week") and its data is always reachable as rows.
2. Color is never the sole signal: deltas carry glyphs + text; status chips carry icons; live dots pair with a "Live"/"Stale" label.
3. Keyboard parity for every interaction: strip `↑↓` + `Enter`, priorities `↑↓`/`Enter`/`Space`, rails `Alt+←→`/`Enter`, modes `F`/`P`, customization `Alt+↑↓`, disclosure `Esc`/`Enter`.
4. Focus rings per Escapement §10.5; the focused widget never moves (expansion FLIPs *around* the focus, never the target).
5. Reduced motion tiers per §10.3; reduced transparency removes glow and wash pulses.
6. High-contrast: KPI numerals ≥ 4.5:1 in both themes (Corridor §3.5); the strip is the most important readability surface in the product.

---

## 15. Do's & Don'ts

**Do**
- Keep the KPI strip first, the scan target sacred, and every tile clickable (§3, §7.1).
- Make every widget a registry entry with a skeleton, an empty state, and provenance (§5).
- State *why* a priority or suggestion is here (Manus transparency, §6, §7.4).
- Resume work exactly where it was left (§7.5, §7.6).
- Disclose progressively: tile → preview → expand → detail, never a modal for a glance (§7.9).
- Pulse once and rest; the Bridge is calm (§7.2, §10).
- Let the user customize below the line, and only below the line (§3, §5.3).

**Don't**
- Don't put anything above the KPI strip but the context band (§3.1).
- Don't let one failed widget block the dashboard (§5.2).
- Don't animate more than one zone for a context shift (§6).
- Don't re-count a KPI on every refresh, and don't re-draw a chart on window change (§7.2, §7.8).
- Don't reveal hover-only affordances without keyboard parity (Gloss H07/F07; Corridor §13.5).
- Don't show a centered spinner where a skeleton belongs (§9).
- Don't let a pin or a recent item be overridden by adaptive reordering (§7.6).
- Don't ship a dashboard the strip doesn't paint first (§11).

---

## 16. Acceptance criteria

- The morning scan conveys the school's state in 8 seconds: strip read → priority scan → one action taken.
- Any number on the Bridge is reachable from raw rows in ≤ 2 clicks from the dashboard.
- Every dashboard page is a registry composition; zero ad hoc dashboard markup.
- Zero CLS across all skeleton → content transitions; strip paints within one frame.
- The live set is exactly the licensed set; live changes pulse once and rest.
- All interactions have keyboard parity; reduced motion leaves every surface readable and every action reachable.
- 40+ widgets render at a stable 60fps on a mid-range laptop; grid FLIPs complete in ≤ 260ms.

---

*The Bridge is where the captain works: three jobs — orient, act, return — one screen, eight seconds to scan, two clicks to act, and yesterday's work waiting where it was left. It is the calmest screen in the product, because it is the one the school runs on.*
