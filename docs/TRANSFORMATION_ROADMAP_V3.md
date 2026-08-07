# SDMAS v3 Transformation Roadmap — "The Ascent"

> The strategic layer of the Corridor system — the eighth expansion, and the
> only one that is *executable process* rather than specification. Codename:
> **The Ascent**.
>
> **Scope:** the complete, prioritized program for transforming SDMAS from a
> functional school-operations web app into software that visually competes
> with the best enterprise desktop products in the world — Linear, Arc,
> Notion, Bloomberg Terminal, the AAA tier. This document orchestrates the
> eight normative specifications into twelve executable phases, scores every
> improvement on impact/complexity/user-value/effort, and sequences the work
> so value lands incrementally — a new capability per release, never a
> big-bang redesign.
>
> **Companion documents** (the source of truth this roadmap *executes*):
>
> | Doc | Codename | Covers |
> |---|---|---|
> | `DESIGN_SYSTEM_V3.md` | — | tokens, color, typography, elevation, material (P1) |
> | `MOTION_SYSTEM_V3.md` | — | the grammar: verbs, compass, clock, tiers (P8) |
> | `APP_REDESIGN_V3.md` + `_SCREENS` | — | IA, shell, screen-family templates (P3, P4) |
> | `TABLE_SYSTEM_V3.md` | The Ledger | the table instrument (P7) |
> | `COMPONENT_LIBRARY_V3.md` | The Foundry | 109-component contract library (P2) |
> | `MICRO_INTERACTIONS_V3.md` | The Gloss | 252 moment-level interactions (P8, P12) |
> | `VISUAL_EFFECTS_V3.md` | The Lens | glass, depth, light, performance model (P9) |
> | `ANALYTICS_SYSTEM_V3.md` | The Watchtower | charts, dashboards, terminal layer (P5) |
>
> **Not a duplicate of `ROADMAP.md`:** that file tracks the *backend* v2
> program (billing workers, tenant scoping, webhook ordering). The Ascent is
> the *frontend design* program. They run in parallel; cross-cutting
> dependencies are flagged in §13.

---

## 0. The thesis — the transformation is a program, not a redesign

A redesign fails when it is an event. A transformation succeeds when it is a
sequence of *ship-able moments* — each release ends with a product that looks
**better than it did**, not worse-but-on-the-way.

Three laws govern The Ascent:

1. **Ship in small verticals, not big horizontals.** Never "redesign all
   buttons." Instead: "the Ledger, complete" — one capability per release,
   with its buttons, motion, effects, and accessibility finished together.
2. **Every phase ends with the acceptance criteria of the phase that
   precedes it still green.** The parity tests from the Table System (§7)
   are the model: each migration preserves byte-parity until a deliberate
   break-point, and the break-point is called out in the release notes.
3. **The tier is the quality ceiling.** `precise` tier is the design target;
   `efficient` and `minimal` are *shipped features*, not compromises. A
   user on a low-power laptop sees a different but equally deliberate
   product (Lens §12.4).

### 0.1 Current state audit (ground truth, August 2026)

| Layer | State | Evidence |
|---|---|---|
| **Design tokens** | Shipped in CSS | `--shadow-*` light+dark, `--blur-*`, `--elevation-*` in `index.css` (DS v3 §8–9) |
| **Motion library** | Shipped | `lib/motion/`: `tokens.ts`, `use-motion-tier.ts`, `use-move.ts`, `flip.ts` (+ `useFlipList`) |
| **Choreography adoption** | Partial | Route transitions, command palette, drawer, sidebar collapse wired to `useMove` |
| **Table System** | Steps 1–2 shipped | `ui/table/`: `frame.tsx`, `columns.tsx`, `filter-model.ts`, `filter-rail.tsx`, `saved-views.ts`, `legacy.tsx`; 186 tests green |
| **Component library** | 35 of 109 in `ui/` | Legacy components exist; migration to Foundry contract is the bulk of P2 |
| **Analytics** | Legacy | 7 chart components in `ui/analytics/`; Watchtower spec (§5) unstarted |
| **App shell** | Legacy layout | `layout/` components; App Redesign P3 targets them |
| **Forms** | Legacy | No v3 form spec written; P6 needs a Forms spec + Foundry B-family migration |
| **Accessibility** | Spec floors exist | DS v3 §14, Foundry §3.5; no automated audit gate in CI yet |

### 0.2 The priority scorecard

Every improvement is scored on four axes (1–5):

- **Impact (I)** — how much of the product's perceived quality it changes.
- **Complexity (C)** — technical risk, moving parts, blast radius. *Higher is
  worse.*
- **User value (U)** — how often the user feels it.
- **Development effort (E)** — person-weeks. *Higher is worse.*

**Priority = (I × U) ÷ (C × E).** The roadmap is ordered by priority within
dependency constraints. Scores appear per phase (§1–12) and in the master
matrix (§13).

---

## Phase 1 — Design language

**Spec source:** `DESIGN_SYSTEM_V3.md` (complete). **Status:** tokens shipped
in CSS; the *language* is not yet applied to every screen.

### Goals
- Make every pixel in the product speak one language: one light source,
  one elevation story, one accent voice (Lens §1).
- Replace all raw color/radius/shadow values in components with tokens.
  Zero raw values is the acceptance bar.

### UX problems solved
- Inconsistent spacing and radius between modules (some pages still use the
  v1 8px grid, others ad-hoc values).
- Two dark modes in the wild (the CSS `[data-theme]` tokens vs. component
  hardcodes) producing "half-dark" screens.
- Elevation confusion: modal on modal, card on card, no z-ladder discipline.

### Visual improvements
- The skylight canvas gradient (Lens §5.1) behind all chrome.
- The hairline-occlusion rule kills the "stacked box" dashboard look (Lens
  §5.3).
- Accent used as a *system* (DS v3 §3.5 contrast floors, §6 color roles),
  not per-component whimsy.

### Motion improvements
- None directly — P1 is static. But the elevation tokens it lands are the
  input every P8/P9 animation reads.

### Components to redesign
- `ui/` primitives that still hardcode: audit via grep for `#hex` and
  `rgba(` in `apps/web/src/components/` (expect ~200 hits).
- The two theme files merged into one token namespace.

### Technical implementation strategy
1. Token-first: extend `index.css` until every hardcode has a token.
2. Ship a CI gate: `grep`-style lint that fails on raw `#[0-9a-fA-F]{3,8}`
   and `rgba(` in component files (exempt: the token definitions themselves,
   the aurora, shadows).
3. Convert in vertical order — the screens P3 touches first, so P1 and P3
   land together.

### Risk analysis
- **Medium.** Token swaps are mechanical but wide; the risk is *drifting*
   visual output. Mitigation: golden screenshots per module before/after.
- Dark-mode regression is the highest-probability bug class. Mitigation:
   the existing `useTheme` + a per-module contrast check (DS v3 §3.5 floors).

### Performance considerations
- **Positive:** tokens remove per-component repaint variance; the skylight is
  a single static gradient (C0, Lens §12.1).
- No animation budget consumed.

### Acceptance criteria
- Zero raw color/radius/shadow values in `apps/web/src/components/`.
- Every screen legible in both themes at the §3.5 contrast floors.
- The z-ladder is the only z-index in the app (DS v3 §8.3).
- Golden screenshots: no module changed > 8% pixels vs. pre-P1.

**Score: I 5 · C 3 · U 4 · E 3 → Priority 2.2** (the enabler; lands with P3)

---

## Phase 2 — Component system

**Spec source:** `COMPONENT_LIBRARY_V3.md` — The Foundry (109 components, 9
families, the nine-field contract). **Status:** 35 components exist in
`ui/`; none yet carry the full contract (states/variants/keyboard/ARIA as
*code*, not notes).

### Goals
- Every component ships all nine contract fields as implemented behavior.
- Replace the ad-hoc per-page component sprawl with the Foundry set.

### UX problems solved
- Inconsistent states: some buttons have hover, others don't; focus-visible
  rings vary; disabled styles vary (DS v3 §13).
- Keyboard parity: reveal-on-hover actions unreachable by keyboard on some
  components (Foundry §3).
- One-off components per page (each table had its own filter UI until the
  Ledger centralized it — the same disease exists in forms and nav).

### Visual improvements
- Uniform elevation, radius, and density across families.
- The interaction spine (Foundry §3): focus model, Escape semantics, pointer
  rules — consistent everywhere.

### Motion improvements
- Components get their Gloss entries (each Foundry component maps to its
  H/K/F-family interactions; The Gloss §4 cross-indexes them).

### Components to redesign (by family priority)
1. **A — Actions:** Button, IconButton, Toggle, SegmentedControl (the most
   touched components in the app).
2. **B — Inputs:** Input, Select, SearchInput, DatePicker (P6's dependency).
3. **C — Feedback:** Badge, Chip, Toast, Skeleton, PulseDot.
4. **D — Overlays:** Modal, Drawer, Popover, Tooltip, CommandPalette.
5. **E — Data:** DataTable (already v3), Avatar, Timeline.
6. **F–I:** Tabs, Card, AppShell, ChartFrame, RouteTransition.

### Technical implementation strategy
- The barrel pattern from `ui/table/`: keep the legacy component as a shim,
  build the v3 component beside it, parity-test byte-for-byte, then flip the
  barrel one import at a time.
- Each migration ships: component + states machine test + keyboard test +
  axe pass (Foundry §6 governance).
- Order: A → C → D → B → F → G → E → H → I (the families P3/P4/P6/P7 consume
  first).

### Risk analysis
- **Low-medium.** The parity-shim pattern already proved itself on the Table
  (186 tests green). The risk is *scope* — 74 components to migrate. The
  gate is the contract, not the count: a component that already conforms
  ships as-is.
- Version churn on ~50 call sites per component — mitigated by the barrel
  flip (one import change, no prop changes for conforming usage).

### Performance considerations
- Components get `will-change` discipline and compositor-only animations by
  contract (Foundry §3, Lens §12.2).
- Bundle size: the barrel tree-shakes; legacy shims are removed per family
  once all call sites flip.

### Acceptance criteria
- Every component in the catalog has a conforming implementation or an
  explicit `[deferred]` entry with a date.
- No component regresses its keyboard map across migrations (test suite
  per component).
- axe-clean on the component gallery page.
- `prefers-reduced-motion` passes at tier `minimal` with full function.

**Score: I 4 · C 4 · U 4 · E 5 → Priority 0.8** (longest pole; runs in
parallel with every other phase as the migration channel)

---

## Phase 3 — Navigation redesign

**Spec source:** `APP_REDESIGN_V3.md` Parts 1–2 (IA, shell, toolbar, sidebar,
palette, notification center, status bar) + `_SCREENS` templates.

### Goals
- From route-based URLs to **workspace-based IA**: Today / People / Academics
  / Finance / Operations / Analytics, each with its own rail.
- The App Window shell: unified toolbar, ⌘K palette, notification center,
  status bar (S.1–S.7).

### UX problems solved
- 30+ top-level routes with no grouping (pages/ list confirms the sprawl) —
  users cannot predict where a feature lives.
- No global command access — every action required navigation.
- No persistent status context (sync state, campus, term) — the status bar
  fixes this.
- Sidebar collapse was a feature; workspace switching is a *mental model*.

### Visual improvements
- The glass chrome (Lens §3 `glass.pane`) on header + rail.
- The sidebar morph (Lens §8.2): 256→72px FLIP reflow with label fade.
- One workspace iconography system, re-drawn to the icon grid (DS v3 §10).

### Motion improvements
- Workspace transition choreography (Motion §6.3 page transitions): content
  sweeps in from the compass direction of the new workspace.
- The palette's bloom (Gloss C13), the notification center's slide (S.6),
  the rail's reflow (P8 sidebar spec).

### Components to redesign
- `layout/` (sidebar, header, app-shell) → the App Window (S.1).
- The command palette (exists, choreographed — migrate to S.4 spec).
- Global search (new — S.5), Notification Center (S.6), Status Bar (S.7).
- Route transition wrapper (exists — P8 already wired it).

### Technical implementation strategy
1. Ship the shell *behind* the existing routes first (the App Window renders
   the current router inside it) — zero route changes, immediate shell.
2. Introduce workspaces as a grouping layer above routes (the map in §1.2 of
   the spec is the exact translation table).
3. Flip route-by-route, starting with Today (dashboard) and People.
4. ⌘K palette + status bar land with the shell; global search last (it needs
   the P5 analytics index for cross-entity search).

### Risk analysis
- **High** — navigation is the most-used surface; a broken shell breaks the
  whole app. Mitigation: the shell-behind-routes trick means the old IA is
  never removed until the new one is proven; feature-flag the workspace
  switcher.
- IA change is a *training* risk for existing users — the old route map must
  be documented in-app (help menu) for one release.

### Performance considerations
- The shell is chrome: it must be **paint-free during content changes** —
  `content-visibility: auto` on scroll regions, glass on chrome only (Lens
  §9.2: one material per layer).
- Palette is a `glass.lg` — counts against the blur budget (Lens §12.3); the
  header is `glass.md`. Within cap.

### Acceptance criteria
- 100% of current routes reachable from the new IA (translation table
  complete, tested by a route-coverage test).
- ⌘K reaches: every workspace, every entity type, every quick action.
- Sidebar collapse/expand hits 60fps on a 4k display with the Ledger open.
- All keyboard routes from DS v3 §14 work on the shell.

**Score: I 5 · C 4 · U 5 · E 4 → Priority 1.6**

---

## Phase 4 — Dashboard redesign

**Spec source:** `APP_REDESIGN_V3.md` T.1–T.3 (Workspace/List, Master–Detail,
360 Profile) + `ANALYTICS_SYSTEM_V3.md` §9 (dashboard grammar).

### Goals
- The dashboard becomes the **Today workspace**: the day's work, not a
  static chart wall.
- KPI cards become instrumented: sparkline + delta + goal arc (Watchtower
  §5), not number-in-a-box.

### UX problems solved
- The current dashboard is a read-only poster — no actions, no priorities.
- KPI cards show numbers without context (vs. previous period, vs. goal).
- No glanceable "what needs me today" — principals and bursars hunt through
  routes for urgency.

### Visual improvements
- The card grammar from Foundry G1 with the elevation travel (Gloss H04).
- The status color language (DS v3 §6) on every KPI delta — green/amber/red
  with meaning, never decoration.
- The skylight canvas + hairline occlusion stop the box-stack look.

### Motion improvements
- Count-up on load (Gloss L? animated numerals), one stagger pass (Motion
  §4.3, cascade cap), then **stillness** — live data changes pulse via the
  status wash (Gloss N-family), never loop.

### Components to redesign
- `kpi-card.tsx` → the KPI instrument (Watchtower §5: sparkline + arc +
  delta).
- The dashboard page → the Today workspace template (T.1).
- Command Center → the live floor (Watchtower §7) with the sync-dot as the
  only loop.

### Technical implementation strategy
- Rebuild Today as a new route (`/today`) rendering the T.1 template, keep
  `/` (dashboard) until parity.
- KPI instrument built as a Foundry H-family component (one component, all
  pages reuse it).
- Live metrics via the existing events stream (outbox → websocket) with
  optimistic row merge (Ledger §10 pattern).

### Risk analysis
- **Medium.** Dashboards are the first thing users judge; a *different* but
  *worse* dashboard is a release-killing outcome. Mitigation: the T.1
  template is specified to the pixel; golden screenshots per KPI.
- Live-metric loops are the top perf hazard — gated by the sync-dot only
  (Gloss "only-loop" law).

### Performance considerations
- Charts are SVG with a single rAF ticker shared with the aurora (Lens
  §12.2) — never per-chart loops.
- Virtualize the activity feed if it exceeds ~200 items.

### Acceptance criteria
- Every KPI carries delta + goal context; every delta has a tooltip
  explaining its window (Ledger §15 cell-tooltip pattern).
- "What needs me today" surfaces ≥ 1 actionable item per role in ≤ 2s.
- 60fps with all Today widgets live; tier `efficient` renders fully static
  with equal information.

**Score: I 5 · C 3 · U 5 · E 3 → Priority 2.8** (highest early payoff)

---

## Phase 5 — Data visualization redesign

**Spec source:** `ANALYTICS_SYSTEM_V3.md` — The Watchtower (complete).

### Goals
- Every chart speaks the Watchtower grammar: one chart room, one color
  language, one interaction model (§2–4).
- Drill-down, zoom, hover comparison, fullscreen, and the terminal layer
  (§6, §10).

### UX problems solved
- Current charts (7 legacy components) are disconnected: different colors
  for the same entity across charts, no drill-down, no comparison mode.
- No density control for data-dense screens (Watchtower §12).
- No fullscreen/terminal mode for boardroom or deep-analysis use.

### Visual improvements
- The chart room frame (Watchtower §2): consistent axis treatment, the
  caption hierarchy, the color-as-language system (§4) — one color per
  entity, globally.
- The sparkgrid and goal-arc instruments on KPI cards.

### Motion improvements
- Datum bloom on hover (Gloss G01), axis tick settle, the range-brush
  rubber-band (G-family). Enter = one stagger, then still.

### Components to redesign
- All 7 `analytics/` components → Watchtower catalog (ChartFrame,
  Sparkgrid, GoalArc, RangeBrush + the six chart types).
- The analytics pages → the terminal layer (§10) where density demands it.

### Technical implementation strategy
- Build the ChartFrame first — every chart is a ChartFrame child, so the
  frame standardizes axes/colors/tooltips in one place.
- Migrate one chart type per release (line → bar → heatmap → area → pie →
  radar), keeping the legacy chart until its replacement passes parity on
  sample data.
- The interaction model (§6) is one shared hook set (hover/zoom/brush), not
  per-chart code.

### Risk analysis
- **Medium.** Chart rewrite is data-dependent — golden outputs on the real
  dataset must match (numbers never change; only the drawing does).
- The terminal layer (§10) is high-density by design — it must not leak
  into the default views (it is opt-in per user).

### Performance considerations
- SVG with rAF batching (Lens §12.2); canvas only if a chart exceeds ~5k
  points (then: the Watchtower's canvas escape hatch, §14 impl map).
- Tooltips are composited layers — one at a time (Gloss single-subject law).

### Acceptance criteria
- One color per entity across all charts (verified by a color-map test).
- Every chart: hover datum readout, keyboard focus on data points, zoom
  where time-series, fullscreen where dense.
- The blur budget holds: chart rooms use zero backdrop blur.

**Score: I 4 · C 4 · U 4 · E 4 → Priority 1.0**

---

## Phase 6 — Forms redesign

**Spec source:** Foundry B-family (§B1–B14) + the Form Sheet template (T.5)
+ DS v3 §13. **Note:** no standalone forms spec exists yet — this phase
**produces one** (`FORMS_V3.md`) as its first deliverable, following the
Corridor doc pattern.

### Goals
- Every form is a **Form Sheet** (T.5): focused, single-column, keyboard-
  complete, with inline validation that never blocks typing.
- The B-family input contract: states, keyboard map, ARIA — implemented.

### UX problems solved
- Long scrolling forms with submit-at-the-bottom (the classic school-app
  disease) → step-free grouped sheets.
- Validation errors as red borders only → inline messages + rings
  (DS v3 §13: error = danger ring + message, field stays `ink.0`).
- No unsaved-change protection; no save affordance (Ctrl/Cmd+S, autosave
  where the domain allows).

### Visual improvements
- The input grammar: one border/hairline language, focus = ring not
  border-color, disabled = 45% + no shadow (DS v3 §13).
- Date/time pickers as B9/B10 (day-grid, time-scrub) instead of
  `type="date"` native widgets.

### Motion improvements
- Field-level: mask ripple (Gloss T04), validation settle (T08 — shake
  reserved for submit-failure only, then never for individual fields).
- Sheet-level: Form Sheet enter/exit as the Drawer/Sheet choreography
  (S.8), unsaved-state dot on the title.

### Components to redesign
- All raw `<input>` usages → B1–B10; the search input → B7 (exists);
  selects → B3/B4/B5; the date inputs → B9.
- The form pages across admission/registration/fees/leave/attendance.

### Technical implementation strategy
1. Write `FORMS_V3.md` (the Form Sheet law: one primary per sheet,
   inline validation grammar, keyboard map, autosave rules).
2. Ship B1–B10 as Foundry components (shim + parity pattern).
3. Migrate form-by-form, starting with the highest-frequency forms
   (admission, leave, fee payment).
4. Add a global unsaved-changes guard on the shell (P3) that every form
   inherits.

### Risk analysis
- **Medium.** Form behavior is *business logic adjacent* — a broken submit
  is worse than an ugly one. Mitigation: parity tests per form (submission
  payload byte-identical), feature-flag per form.
- Date-picker migration has the highest regression surface (native vs.
  custom semantics) — the B9 APG spec (Foundry §B9) is the contract.

### Performance considerations
- No blur on form surfaces (inputs sit on opaque sheets — Lens §9.2
  one-material rule).
- Autosave is debounced (180ms — the same debounce the Ledger search uses).

### Acceptance criteria
- Every form reachable + submittable by keyboard alone.
- Validation: no submit blocked without a visible inline message.
- Unsaved-change guard active on every form; Ctrl/Cmd+S works where
  autosave is off.
- Form Sheet parity: submission payloads identical pre/post migration.

**Score: I 4 · C 3 · U 5 · E 3 → Priority 2.2**

---

## Phase 7 — Tables redesign

**Spec source:** `TABLE_SYSTEM_V3.md` — The Ledger. **Status:** steps 1–2
shipped (frame + type system + filter rail + saved views, 186 tests).
**This phase is *already running*.** The remaining steps are the migration
order in Ledger §19.

### Goals
- Finish the Ledger: selection (§7), keyboard navigation (§12), inline
  editing (§9), column resize/pin (§3), context menus (§15), virtualization
  (§13).
- Migrate all ~50 table call sites from the legacy shim to the frame.

### UX problems solved
- Current tables are view-only lists: no selection, no bulk actions, no
  keyboard navigation, no column control.
- The register/ledger/registry class system doesn't exist in code yet —
  each page's table has its own ad-hoc behavior.

### Visual improvements
- The sticky glass band (Lens §3 `glass.bare` scroll-catch), zebra rows,
  the density classes (Ledger §5 — ledgers compact, registries comfortable).

### Motion improvements
- T78: rows move for exactly three reasons (FLIP on reorder, status wash on
  state change, user drag). The tier-gated exit choreography is shipped.

### Components to redesign
- The ~50 call sites: rosters, ledgers, registers, receipts, audit logs,
  enrollments → `DataTable` with the right `class` per site.
- `ui/table/legacy.tsx` — retired once the last call site flips.

### Technical implementation strategy
- Continue the stepwise order (Ledger §19): filter rail → selection → bulk
  actions → keyboard → inline edit → resize/pin → virtualization.
- Each step: parity test + feature test + tier test (the pattern proven in
  steps 1–2).
- Virtualization (step last) touches only the Ledger class tables (10k-row
  budget, §13).

### Risk analysis
- **Low** — the pattern is proven; the risk is momentum (a 9-step sequence
  with long tail). Mitigation: each step is independently shippable.
- Inline editing is the one behaviorally risky step — it changes data, not
  just display. The row-as-transaction model (§9) gates it.

### Performance considerations
- Virtualization is the perf payoff — 10k rows at 60fps, the acceptance
  test is already spec'd (Ledger §16).
- The frame's FLIP + filter are compositor-only; the exit choreography is
  tier-gated (already shipped).

### Acceptance criteria
- All ~50 call sites on the frame; legacy shim deleted.
- Ledger classes enforced: a ledger table can't get registry behavior.
- 10k-row scroll at 60fps on the Ledger class.
- Full keyboard map (Ledger §12) test-passing per class.

**Score: I 5 · C 3 · U 5 · E 4 → Priority 2.1** (in progress; finish it)

---

## Phase 8 — Motion system

**Spec source:** `MOTION_SYSTEM_V3.md` (grammar) + `MICRO_INTERACTIONS_V3.md`
(The Gloss — 252 entries). **Status:** the library ships
(`lib/motion/` + adoption in palette/drawer/routes/sidebar).

### Goals
- Every animation in the app is *grammar-compliant* — a verb, a direction,
  a distance class, an importance — no bespoke `@keyframes` in components.
- The Gloss catalog is the audit: every interaction has a Felt/Spec/Tier
  entry implemented.

### UX problems solved
- Inconsistent animation: some components use 150ms, some 300ms, some
  `ease-in-out` (the janky default), some `linear`.
- Animations that block: exit animations holding up navigation.
- No reduced-motion story beyond a blanket kill-switch.

### Visual improvements
- Timing *consistency* itself is the visual improvement — the app reads as
  one machine instead of five libraries.

### Motion improvements
- The full grammar: the Cardinal Compass direction semantics, the Clock
  distance classes, the spring map (Motion §3.4), the motion budget per
  interaction (§4.6).
- The Gloss's house rules become lintable: one-verb, first-75ms, exit
  compression, only-loop.

### Components to redesign
- Every component with an inline `animation:` or `transition:` in CSS →
  the `useMove`/token system.
- The legacy `animate-*` utility classes in `index.css` → grammar tokens
  (the classes stay as *aliases*, not the source of truth).

### Technical implementation strategy
1. A lint rule (or the existing motion module's export surface) that flags
   raw `transition:`/`animation:` durations in components.
2. Migrate component-by-component, reusing the motion library that exists.
3. The Gloss conformance test: every Foundry component's Gloss entries
   resolve to a token (a spec-to-code audit test).

### Risk analysis
- **Low-medium.** Animation rewrites are invisible-if-correct, obvious-if-
  broken. Mitigation: tier tests per component (the `useMotionTier` tests
  exist as the pattern).
- The danger is *over-animating* during the rewrite — the Gloss's quiet
  test (felt, not seen) is the review gate.

### Performance considerations
- Compositor-only enforced by the token system (transform/opacity).
- The motion budget (Motion §4.6) caps simultaneous animation per viewport —
  the "why is my app janky" defense.

### Acceptance criteria
- Zero raw durations/easings in components (lint-enforced).
- Every reduced-motion user gets tier `minimal` (opacity-only ≤ 75ms, full
  function).
- The Gloss's 252 entries map to tokens; the conformance test passes.

**Score: I 4 · C 3 · U 4 · E 3 → Priority 1.8** (the polish multiplier)

---

## Phase 9 — Visual effects

**Spec source:** `VISUAL_EFFECTS_V3.md` — The Lens (complete).

### Goals
- The physics model in production: one lamp, three depth currencies, the
  cost classes.
- Glass chrome, the wash, the aurora, the specular edge — subtle, tiered,
  measured.

### UX problems solved
- "Flat dashboard" feel: no depth story, no material differentiation
  between chrome/content/floating layers.
- The janky-effect trap avoided by *design*: the cost-class model (C0–C4)
  prevents the "everything glows" regression forever.

### Visual improvements
- Glass `pane`/`float`/`focus` chrome (Lens §3), the skylight (§5.1), the
  pointer wash (§5.2), the dark-mode specular edges (§10).

### Motion improvements
- The aurora (the only animated gradient), the under-glow on floats, the
  float shadow rules (§7.3). Motion blur: policy only — text never blurs.

### Components to redesign
- Chrome: header, rail, drawer, palette, modals → glass utilities.
- Login + empty states → aurora/particles (the only legal homes).

### Technical implementation strategy
- The Lens §15 implementation map is the exact order: token layer → glass
  utilities → wash → shadows → aurora → chrome retrofit → sidebar morph →
  audit.
- The blur budget (Lens §12.3) is enforced by review + a devtools counter
  script during QA.

### Risk analysis
- **Medium.** Backdrop-filter is the top GPU-cost suspect — the blur budget
  and tier collapse (Lens §12.4) are the mitigation, and they are *shipped
  behavior*, not best-effort.
- `prefers-reduced-transparency` must be tested on Windows + macOS (the two
  platforms both support it; behavior differs slightly).

### Performance considerations
- The entire §12 performance model: cost classes, 60fps contract, blur
  budget, rAF batching, tier degradation. C4 (SVG filters, text blur,
  mirrors) is a *forbidden* class — enforced in review.

### Acceptance criteria
- Blur budget never exceeded (audit script passes on every screen).
- Tier `efficient` = full function, zero backdrop-filter.
- The quiet test: at 3 feet, effects are felt, not seen.
- 60fps holds with header glass + wash + Ledger 10k rows.

**Score: I 4 · C 4 · U 4 · E 4 → Priority 1.0**

---

## Phase 10 — Accessibility

**Spec source:** DS v3 §3.5/§14, Foundry §3.5, Ledger §12, Watchtower §13.

### Goals
- WCAG 2.2 AA as a *passing CI gate*, not a design aspiration.
- Keyboard-complete: every feature reachable and operable by keyboard.
- Screen-reader: every chart has a data table equivalent; every table has
  proper row/column semantics.

### UX problems solved
- The silent majority: focus rings that vanish, contrast that fails in one
  theme, hover-only affordances, unlabeled icons.
- The keyboard gap in tables (now solved by Ledger §12 — this phase ships
  the *audit* that proves it).

### Visual improvements
- Contrast floors enforced per usage (DS v3 §3.5) — the same token changes
  that improve P1.
- Focus-visible rings everywhere; the "glow.focus" dark-mode focus (Lens
  §4) — the premium focus story, not the default browser outline.

### Motion improvements
- Reduced-motion tier `minimal` verified per component (Motion §3.4): the
  tier is a *feature*, not a fallback.

### Components to redesign
- None specifically — this is the *verification* phase. Components that
  fail the audit get fixed (expect: icon buttons without labels, custom
  selects without ARIA, charts without table equivalents).

### Technical implementation strategy
1. Install axe + a keyboard script into CI (the component test suite
  already runs; add the a11y suite).
2. Run the full audit; file findings as P1-style issues with severity.
3. Fix in the P2 migration channel (each migrated component must pass the
  audit — Foundry §6 already demands axe-clean).
4. Screen-reader passes on the top 10 user journeys.

### Risk analysis
- **Low** — this phase *measures*; the fixes ride the existing migration
  channel. The risk is discovering a systemic issue late (e.g., custom
  selects everywhere) — mitigated by the Foundry B-family contract that
  already specifies ARIA per component.

### Performance considerations
- Accessibility features cost ~nothing (focus rings, semantics); the one
  cost is `prefers-reduced-motion` handling, already free via the tier
  system.

### Acceptance criteria
- axe passes on every route in both themes (CI gate).
- Top-10 journeys operable by keyboard alone, scripted in CI.
- Charts: every series has a data table or text alternative (Watchtower
  §13).
- No component fails the Foundry §3.5 floors.

**Score: I 5 · C 2 · U 5 · E 2 → Priority 6.3** (highest ratio — do the
audit *early*, ride fixes on P2)

---

## Phase 11 — Performance optimization

**Spec source:** Lens §12 (the performance model) + Watchtower §14.

### Goals
- 60fps on the worst real screens: the Ledger at 10k rows, Today with all
  widgets live, the Watchtower's densest chart.
- Budgets: < 2s interactive on the shell, < 300ms route change (skeleton
  visible by 150ms).

### UX problems solved
- Jank on scroll with the glass header + heavy tables.
- Route-change latency that makes the app feel "web" instead of "native".

### Visual improvements
- The *stability* itself: zero layout shift during route changes, images
  sized, fonts preloaded.
- The skeleton system (Foundry C-family) replaces spinners as the loading
  language.

### Motion improvements
- Route transitions are the *mask* for loading (the exit/enter choreography
  runs while data loads — the "native" feel comes from this, not from
  speed).

### Components to redesign
- None — this is measurement + tuning across the shipped system.

### Technical implementation strategy
1. Lighthouse/WebPageTest budgets in CI (the PWA baseline exists).
2. The Lens §12.3 blur counter as a devtools script in QA.
3. Route-level code splitting (Vite) per workspace — the P3 IA gives the
  split points.
4. The Ledger virtualizer (P7's last step) is the big win; ship it with
  the perf gate.
5. Font/icon subsetting; preload the critical font.

### Risk analysis
- **Low-medium.** Perf work is additive; the risk is premature optimization
  (tuning before P3/P5/P7 land). Mitigation: run this phase's *measurement*
  gate from day one, its *fixes* after the heavy rewrites land.

### Performance considerations
- Everything in Lens §12: rAF batching, compositor-only, `content-visibility`,
  the blur budget, tier degradation for low-power.
- The single rAF loop rule: one ticker per viewport, shared.

### Acceptance criteria
- The 60fps contract (Lens §12.2) holds on the three worst screens.
- Route change < 300ms p75; skeleton by 150ms.
- Lighthouse performance ≥ 90 on the shell; bundle per workspace < 250KB
  gzipped.
- Zero layout shift (CLS < 0.05) on route changes.

**Score: I 5 · C 3 · U 5 · E 3 → Priority 2.8**

---

## Phase 12 — User delight

**Spec source:** The Gloss (252 interactions) + Lens §10 (reflections) +
Foundry §3 (interaction spine).

### Goals
- The final 5%: the moments users *tell other people about* — the palette
  bloom, the status wash, the sheet slide, the sync-dot honesty.
- Delight is **budgeted** (Gloss §5 quality budget): one delight moment per
  screen, never a confetti storm.

### UX problems solved
- The "it works but it's flat" complaint — the residual gap between a
  school app and a premium product.
- The empty/error/loading states that currently say "something broke"
  instead of "here's what to do" (Foundry C-family empty states).

### Visual improvements
- The specular edge and under-glow (dark mode), the empty-state canvases
  (skylight + frosted pane), the "first-run arrival" choreography.

### Motion improvements
- The Gloss's W-family (window/shell) and Z-family (context/system): the
  theme morph, the connection drop, the density change — the moments
  between screens, where delight lives.
- The success pulse (the one glow legal in light mode) at task completion.

### Components to redesign
- Empty states, error states, loading skeletons → the Foundry C-family
  instruments.
- The onboarding/coach-mark spotlight (Lens `elevation.spotlight`).
- Command palette finale: recent items, empty-query suggestions, the
  keyboard hint footer.

### Technical implementation strategy
- Gloss conformance: the audit test (P8) is the delight *inventory* — each
  entry that maps to a token and passes the quiet test is shipped.
- Delight moments are feature-flagged (they're the first to degrade under
  `efficient` tier, by design).

### Risk analysis
- **Low** — the risk is *over-shooting* (adding delight that isn't in the
  Gloss). Mitigation: the single-subject law (one delight per screen) is
  the review gate; the Gloss catalog is the closed set of allowed moments.

### Performance considerations
- Delight is C1 (composited) or cheaper by definition; any effect that
  needs C2/C3 has to pass the Lens §12.3 budget to be *in* the Gloss.

### Acceptance criteria
- One budgeted delight moment per screen (verified in review).
- Empty/error/loading states are instructive, branded, and tier-correct on
  every route.
- The onboarding spotlight teaches the ⌘K palette in < 60s.
- The Gloss conformance test passes at 100%.

**Score: I 4 · C 2 · U 4 · E 2 → Priority 4.0**

---

## 13. Master priority matrix

Sorted by **Priority = (I × U) ÷ (C × E)** within dependency constraints.
The *order of work* respects both the score and the arrows below.

| # | Phase | I | C | U | E | Priority | Constraint |
|---|---|---|---|---|---|---|---|
| 1 | **P10 Accessibility** (audit) | 5 | 2 | 5 | 2 | **6.3** | starts day one; fixes ride P2 |
| 2 | **P12 User delight** (budgeted) | 4 | 2 | 4 | 2 | **4.0** | after P8 grammar lands |
| 3 | **P4 Dashboard redesign** | 5 | 3 | 5 | 3 | **2.8** | after P3 shell; parallel to P7 |
| 4 | **P11 Performance** (budget gate) | 5 | 3 | 5 | 3 | **2.8** | measurement from day one; fixes after P3/P5/P7 |
| 5 | **P1 Design language** | 5 | 3 | 4 | 3 | **2.2** | lands with P3 (the token substrate) |
| 6 | **P6 Forms redesign** | 4 | 3 | 5 | 3 | **2.2** | after Foundry B-family; parallel to P3 |
| 7 | **P7 Tables redesign** | 5 | 3 | 5 | 4 | **2.1** | *in progress* — finish the Ledger |
| 8 | **P3 Navigation redesign** | 5 | 4 | 5 | 4 | **1.6** | the shell; biggest visible change |
| 9 | **P8 Motion system** | 4 | 3 | 4 | 3 | **1.8** | grammar exists; enforce + audit |
| 10 | **P5 Data visualization** | 4 | 4 | 4 | 4 | **1.0** | after P4 KPI instrument |
| 11 | **P9 Visual effects** | 4 | 4 | 4 | 4 | **1.0** | after P1 tokens + P8 grammar |
| 12 | **P2 Component system** | 4 | 4 | 4 | 5 | **0.8** | the long channel; runs *through* everything |

### 13.1 The recommended wave plan

**Wave A — foundation (weeks 1–6):** P10 audit runs from day one (free
measurement). P1 token purge + P4 Today rebuild + P7 Ledger steps 3–5
(selection, keyboard, bulk actions) — the three highest-value verticals,
each independently shippable. P12's first delight moments (empty states,
status wash) ride along.

**Wave B — the shell (weeks 7–14):** P3 App Window behind existing routes +
workspace IA + ⌘K + status bar. P1's remaining tokens land with the chrome.
P6 forms begin (B-family components first). P8 audit gate enforces the
grammar on everything new.

**Wave C — depth (weeks 15–24):** P5 Watchtower (ChartFrame first), P7
inline-edit + resize/pin + virtualization, P9 glass/wash/aurora over the
P1/P8 substrate, P12 onboarding. P11 fixes after the heavy rewrites.

**Wave D — finish (weeks 25–30):** P2 residual migrations (the long tail),
P11 final budgets, P12 final audit, the legacy shim deletion, the release
of "SDMAS v3 — The Ascent complete."

### 13.2 Cross-cutting dependencies with the backend roadmap

- Live metrics (P4) and the sync-dot depend on the events stream (backend
  roadmap item 4, webhook ordering) — flag before Wave C.
- Ledger inline editing (P7) needs the optimistic-update API conventions —
  coordinate with the audit coverage item.
- Nothing else blocks; the frontend program is backend-agnostic by design
  (the parity-shim pattern means every migration is reversible).

---

## 14. Governance

1. **One phase per release, one vertical per sprint.** A release may combine
   phases, never half-phases. A sprint may cut scope, never quality.
2. **The acceptance criteria are the Definition of Done.** A phase is not
   "done" because its spec is written — its acceptance criteria are tests.
3. **Parity is the default, break-points are announced.** Every migration
   preserves behavior until the spec calls for a change; the change is in
   the release notes with its before/after.
4. **The tier is always shipped.** No feature passes review at `precise`
   without its `efficient`/`minimal` behavior verified (Lens §12.4).
5. **The quiet test applies to the whole app** (Gloss §5): at 3 feet, the
   app should feel calm. If a release feels busier than the one before,
   the release is rejected, not celebrated.
6. **The Gloss conformance test is the delight inventory** — an interaction
   not in the catalog cannot be added ad hoc; a catalog entry not shipped
   is a debt item with a date.
