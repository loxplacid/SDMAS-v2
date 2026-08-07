# SDMAS Motion System — v4 Specification

**Codename:** *The Escapement*
**Status:** Draft for review · **Owner:** Product Design · **Version:** 4.0.0
**Scope:** apps/web (desktop-first) · **Parity note:** `docs/DESIGN_SYSTEM_DESKTOP_V3.md` §12–13 (the CustomTkinter client) implements this spec's durations, easing arrays, and spring presets as keyframe tables.
**Supersedes:** `docs/MOTION_SYSTEM_V3.md` (the *Compass*) — the v3 grammar remains normative; v4 adds the physics, the machine, and the contract.

> *Every screen is a room, and motion is how you walk through the corridor. The escapement is the mechanism that keeps the corridor on time: springs store the energy, the clock spends it, and the budget keeps the whole machine honest.*

**The purpose test:** every animation in SDMAS must answer exactly one of three questions — *where am I going* (wayfinding), *did my action land* (feedback), or *what deserves my eyes* (focus). An animation that answers none of them is decoration, and decoration is rejected.

---

## 0. What v4 changes — and what it keeps

| | Compass v3 | The Escapement v4 |
|---|---|---|
| Grammar `(verb, direction, D-class, I-level)` | Normative | **Unchanged — still normative**, extended additively only: a new **I4 — room** importance level (§9.1). No verb, direction, or D-class is re-defined. |
| Springs | One overshoot-bounded bezier, "earned" | **First-class physics system**: stiffness/damping/mass + designer presets (§4), still earned. |
| Animation engine | Grammar + `useMove` hook | **A five-layer architecture** (§3): tokens → specs → choreography → renderer → guard. |
| Shared element transitions | Implicit (continuous identity, FLIP) | **A first-class primitive** (§8): one identity travels across surfaces. |
| Easing | 5 curves | **9-curve token set** (adopts the Material-inspired tokens already in `index.css`), v3 names as aliases (§5). |
| Charts / context menus | Mentioned in passing | **Own surface rules** (§10.15, §10.16). |
| Performance | Rules | **A measurable contract** with per-surface budgets and an automatic tier-drop ladder (§12). |
| Reduced motion | Three tiers | **Provider-scoped policy** (`user`/`always`/`never`) + intensity shutter (§11). |

The v3 spec's duration table, choreography rules, worked examples, and do's/don'ts remain in force wherever v4 does not explicitly replace them.

---

## 1. Sources & extraction — principles only

| Source | What it demonstrates | Principle extracted | Translation into SDMAS |
|---|---|---|---|
| **motion.dev (Motion)** | Springs as physics (`visualDuration`/`bounce`, stiffness/damping/mass); `layoutId` shared element transitions; `<MotionConfig reducedMotion>` | **Physics presets + identity-preserving motion + provider-scoped motion policy** | A spring preset table (§4); the SharedElement primitive (§8); a MotionProvider guard layer (§3, §11). |
| **anime.js** | Timeline sequencing; `stagger(n, {from})` emanates from an origin; deep easing catalog | **Choreography as timelines; stagger has an origin** | Sequence/timeline model (§3, §7); stagger `from: first/last/center` (§7). |
| **Apple macOS** | Springs tuned to object size; sheets that relate to their parent; Reduce Motion as a mode | **Physics is per-object, not per-screen; source-aware continuity** | Spring presets keyed to object size (§4.3); enter-from-trigger (§8); designed reduced tier (§11). |
| **VisionOS** | Depth as a *place you can feel* — dimension, materials, spatial continuity | **Z is the most expensive point on the compass and the most meaningful** | Z-moves get the biggest budgets and the hardest caps (§9); depth over decoration (glow/blur only behind Z surfaces). |
| **Linear** | Speed is a feature; feedback < 150ms; no bounce on data | **The fast clock** | Feedback outruns transition, always (§6); springs never on data surfaces. |
| **ReactBits / Boris FX** (v3, retained) | Continuous identity; directional gravity; a global shutter | **The compass + the intensity token** | Retained unchanged. |

---

## 2. The purpose taxonomy — motion has three jobs, one budget

1. **Wayfinding** — spatial continuity, direction, depth (navigation, drill-down, shared elements).
2. **Feedback** — the app answers within 75ms (press, hover, focus, selection, save, sync).
3. **Focus** — one subject at a time (modals, toasts, live states, the success pulse).

**Job priority:** feedback *always* outruns wayfinding (a 75ms press beats a 380ms modal). Wayfinding never runs *on top of* feedback — a modal opening is one subject, not two.

---

## 3. The animation architecture — five layers

Every animation in SDMAS is produced by exactly one path through this stack. Nothing is authored ad hoc; anything that bypasses the stack is a bug.

```
┌─────────────────────────────────────────────────────────────┐
│ 5 · GUARD  — MotionProvider(tier, intensity, reducedMotion) │  policy: what is legal right now
├─────────────────────────────────────────────────────────────┤
│ 4 · RENDERER — WAAPI (web) · CSS instant-tier ·             │  mechanism: how it draws
│               View Transitions (pages) · Canvas (Draw)      │
├─────────────────────────────────────────────────────────────┤
│ 3 · CHOREOGRAPHY — sequence() · stagger() · sharedElement() │  orchestration: who moves, when
│               · flip() · timeline model                     │
├─────────────────────────────────────────────────────────────┤
│ 2 · SPEC — the move grammar (verb, direction, D, I)         │  intent: what the move means
├─────────────────────────────────────────────────────────────┤
│ 1 · TOKENS — durations · easings · spring presets · budget  │  physics: the raw values
└─────────────────────────────────────────────────────────────┘
```

### 3.1 Token layer (unchanged concept)

Durations (§6), easings (§5), spring presets (§4), distance classes, budget constants (§12). Single source of truth: `src/lib/motion/tokens.ts` + CSS custom properties in `src/index.css`.

### 3.2 Spec layer — the grammar (unchanged)

A move is `(verb, direction, distance-class, importance-class)` — five verbs (Slide, Scale, Fade, Draw, Pulse), five compass points (E/W/N/S/Z), four distance classes (D1–D4), and now **four importance levels** (I1–I4, §9.1). Everything else is a rule lookup. The move-spec is the *only* thing an author writes; the engine resolves it.

### 3.3 Choreography layer — the engine

| Primitive | Purpose | Renders via |
|---|---|---|
| `tween(ease)` | Timed motion on transform/opacity | WAAPI / CSS |
| `spring(preset)` | Physics motion (gesture-driven, ≤ 44px) | WAAPI spring / keyframe fallback |
| `sequence(steps)` | Timeline: steps run with defined overlap (leader-follower) | WAAPI group |
| `stagger(n, { from })` | N siblings offset by the 20ms quantum from an origin (`first`/`last`/`center`) | WAAPI delays |
| `sharedElement(id)` | One identity travels across surfaces (§8) | Motion `layoutId` / FLIP |
| `flip()` | Layout change → measure, invert, play, restore | WAAPI transform |

The engine enforces the choreography rules (§7) and the budget (§9, §12) automatically: a sequence that would exceed three simultaneous movers or 500ms is reduced by the engine, not by the author.

### 3.4 Renderer layer

| Surface | Renderer | Notes |
|---|---|---|
| Micro/instant moves (press, focus, hover wash) | CSS transition, `instant`–`fast` | Compositor-only, zero JS |
| Standard moves (menus, toasts, drawers, selection) | WAAPI `animate()` | Cancellable, owns in-flight state |
| Page transitions | View Transitions API | Snapshots treated as surfaces, `::view-transition-*` tokens |
| Draw verbs (checks, chart lines, rings) | SVG `stroke-dashoffset` / clip-path / Canvas | Fixed `draw` duration (300ms) |
| Desktop (parity) | `.after(16)` keyframe tables | See Forge spec §12–13 |

### 3.5 Guard layer

A single `MotionProvider` (web: React context; desktop: a module-level policy) owns:

- `tier` — `precise` / `efficient` / `minimal` (§11).
- `reducedMotion` — `"user"` (default, honors OS + in-app toggle) / `"always"` / `"never"`.
- `intensity` — the shutter (0–1) multiplying distances and gating Pulse/parallax/glow (§11.3).
- Telemetry — frame-drop detection; two consecutive dropped frames drop the tier automatically (§12.8).

**Rule:** no component reads `prefers-reduced-motion` or sets a duration directly. All motion policy flows through the provider.

---

## 4. Spring physics — first-class, still earned

### 4.1 The model

Springs are specified in **either** of two equivalent notations; the engine converts one to the other:

| Notation | Fields | Used by |
|---|---|---|
| **Designer preset** | `visualDuration` (seconds to rest) + `bounce` (0 = none … 1 = max) | Design specs and presets below |
| **Physical** | `stiffness` (tension), `damping` (opposing force), `mass` (weight) | Engines implementing springs (Motion, anime.js, or keyframe simulation) |

Rule: `bounce` maps to **overshoot ≤ 6% of travel, exactly once, settling ≤ 300ms** — the v3 budget, now expressed in physics terms. Two oscillations is a wobble and is a defect.

### 4.2 Legality (unchanged from v3, now enforced by the engine)

A spring is legal only when **both** hold:

1. The motion is **gesture-driven** — pointer or keyboard (press-release, toggle flick, drag release, drop) — not an automated state change.
2. The object is **≤ 44px** in its dominant dimension — toggles, badges, dots, checkbox marks, drag ghosts, bell dot.

Everything larger uses `tween` (`settle`): enter easing, zero overshoot. A modal may use a *barely-damped* spring only for its final 30% (`dampen`, §4.3).

### 4.3 The preset table

| Preset | Objects | visualDuration | bounce | Physical (≈) | Settle |
|---|---|---|---|---|---|
| `micro-spring` | dots, badges, checkbox marks, bell dot (≤ 16px) | 0.20s | 0.20 | stiffness 520 · damping 26 · mass 0.6 | ≤ 240ms |
| `toggle-spring` | switches, chips, radio dots, expander chevrons (≤ 36px) | 0.25s | 0.30 | stiffness 420 · damping 24 · mass 0.8 | ≤ 300ms |
| `press-spring` | button press-release (36–44px) | 0.12s | 0.10 | stiffness 900 · damping 30 · mass 0.7 | ≤ 200ms |
| `dampen` | modal/palette final 30% of a settle | 0.30s | 0.05 | stiffness 300 · damping 32 · mass 1.0 | ≤ 320ms |
| `drag-return` | drag ghost returning to origin | 0.25s | 0.05 | stiffness 280 · damping 34 · mass 1.0 | ≤ 300ms |

### 4.4 Fallback

Where no spring engine is available (CSS-only contexts, reduced hardware), a spring resolves to the **overshoot-bounded bezier** (`--ease-spring` / `--ease-spring-gentle`, §5) at the preset's settle duration. The felt difference must be imperceptible; if it isn't, the preset is wrong, not the fallback.

### 4.5 Anti-patterns

- Springs on cards, panels, pages, or modals — forbidden (§4.2). Data does not wobble.
- Springs on automated state changes (a badge that springs in because data arrived is a lie — only a user's own gesture earns physics).
- Bounce > 6% — one oscillation, then monotonic decay, or it's not this system.

---

## 5. The easing system — nine curves, three jobs

v4 adopts the complete token set already seeded in `src/index.css` (`--ease-*`), with v3 names kept as aliases:

| Token | Curve | Job | v3 alias |
|---|---|---|---|
| `standard` | `cubic-bezier(0.4, 0, 0.2, 1)` | Default; state changes; anything unclassified | supersedes v3 `motion.ease.standard` (was `0.2, 0, 0, 1` — corrected to the value shipped in `index.css`) |
| `decelerate` | `cubic-bezier(0, 0, 0.2, 1)` | Organic entrances — fast start, soft landing | — |
| `accelerate` | `cubic-bezier(0.4, 0, 1, 1)` | Organic exits — fast departure, sharp end | — |
| `emphasized` | `cubic-bezier(0.4, 0, 0.1, 1)` | Larger surfaces; emphasized feedback | — |
| `emphasized-decelerate` | `cubic-bezier(0.05, 0.7, 0.1, 1)` | **The only legal entrance for spatial moves** | `motion.ease.enter` |
| `emphasized-accelerate` | `cubic-bezier(0.3, 0, 0.8, 0.15)` | **The only legal exit for spatial moves** | `motion.ease.exit` |
| `spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Micro-springs (bezier fallback of §4.4) | `motion.ease.spring` |
| `spring-gentle` | `cubic-bezier(0.25, 1.3, 0.5, 1)` | Larger entries with a whisper of life (gallery cards) | — |
| `linear` | `linear` | Loops only: spinners, shimmer, determinate progress | `motion.ease.linear` |

**The three rules:**

1. **Arrivals start fast** — spatial entrances use `emphasized-decelerate` only. An entrance that eases *in* reads as hesitation.
2. **Departures leave fast** — spatial exits use `emphasized-accelerate` only. An exit that eases *out* reads as a drag. Exit = 0.7 × enter.
3. **Never ease a loop** — anything that repeats is `linear` or it is removed.

`standard` is the default *only* because state changes (color, borders) are not spatial — they crossfade, they don't travel. Where v3's easing values differ from this table (only `standard`), this table **supersedes** v3 — it records what ships in `index.css`.

---

## 6. The duration system

### 6.1 Tokens (unchanged, with frame counts)

| Token | Value | Frames @ 60fps | D-class · I-level |
|---|---|---|---|
| `instant` | 75ms | 5 | D1·I1 — press, focus ring, chevron |
| `fast` | 120ms | 7 | D1·I2, D2·I1 — hover, cell pulse, sort arrow, selection wash |
| `base` | 180ms | 11 | D2, D3·I1 — buttons, chips, search results, backdrop tint |
| `slow` | 260ms | 16 | D3 — menus, toasts, drawers, expand, sort FLIP |
| `slower` | 380ms | 23 | D4·I2 — modal surface, palette, theme wash |
| `slowest` | 500ms | 30 | D4·I3 — page transitions, KPI count-up (soft cap) |
| `draw` | 300ms | 18 | Draw verb — checks, chart lines, rings (fixed, never tuned) |

### 6.2 The clock rule (unchanged)

`duration = class floor + 8ms per 16px of travel`, rounded to the token grid, **capped at the class ceiling**. Small objects outrun large ones. A 40px toast and a 1200px page never share a duration.

### 6.3 The decision table

| | I1 feedback | I2 state | I3 context | I4 room |
|---|---|---|---|---|
| **D1 micro** | 75 | 120 | 120 | — |
| **D2 in-place** | 120 | 180 | 180 | — |
| **D3 surface** | 180 | 260 | 260 | — |
| **D4 room** | — | 380 | 500 | 500 |

Nothing is ever slower than 500ms. If a transition needs more time, it is two transitions.

---

## 7. Stagger & sequencing

### 7.1 Stagger

- Quantum: **20ms** per sibling, total **≤ 150ms**.
- Order: **reading order** (top-left → bottom-right) on entry; **reverse reading order** (last in, first out) on exit.
- Origin: `from` may be `first` (default), `last`, or `center` — anime.js-style emanations, used only where an origin is semantically meaningful (a grid expanding from a clicked tile).
- No stagger for fewer than **three** siblings (≤ 2 move together).
- **No re-stagger while typing** — search/filter results crossfade on subsequent keystrokes; stagger is a first-arrival courtesy only.

### 7.2 Sequences (the timeline model)

Multi-element choreographies are **timelines**, not parallel animations:

- **Leader-follower:** one element is the leader; followers begin at **60% of the leader's duration** (overlap), never at 0% (simultaneous) and never after 100% (dead air).
- Overlay leads (§6.3): backdrop fades `base` before the surface's `slower` arrival (leader = overlay, follower = surface).
- Cascade cap: **two levels** of orchestration per interaction (§9.3). A third level collapses to simultaneous.
- Exit reverses the timeline exactly: last-in follower exits first, at 0.7×.

### 7.3 What stagger is *not*

Stagger is not a substitute for hierarchy, and it is never applied to data that changed meaning (sorting staggers by final order; filtering staggers only the incoming set). A cascade that reads as "lag" (> 150ms total) is a bug, not drama.

---

## 8. Shared element transitions — identity travels

The v3 principle "continuous identity" becomes a **first-class primitive** in v4: when the same *thing* (a row, a thumbnail, a numeral, a bell) appears in two places across a state change, it travels between them instead of dying and respawning.

### 8.1 The primitive

`sharedElement(id)` binds one identity to a source element and a destination element. The engine measures both rects (once), and the element animates from source to destination with a `(Slide + Scale + Fade)` composition — the only legal use of Scale on a surface > 40% of the viewport is *this* (it is traveling, not growing in place).

### 8.2 Rules

1. **One shared identity per interaction.** A drawer opening may carry one traveler (the row → the drawer header); everything else follows on the timeline (§7.2).
2. **Same id = same thing.** Two elements may share an id only if they are literally the same object across states. Reusing an id for "look-alike" content is a lie the user will feel.
3. **Origin is the trigger.** The traveler starts at the exact rect of the thing the user touched; it never "flies from nowhere".
4. **Exit reverses.** Closing returns the identity to its source rect at 0.7×.
5. **Reduced motion collapses to instant swap** (§11) — identity is preserved by *state*, not by motion. The destination simply appears.
6. Travelers are transform-only; the engine never measures layout mid-flight (§12.6).

### 8.3 The catalog

| Identity | Travels from → to | When |
|---|---|---|
| Roster row → Student 360 drawer | Row's header cell → drawer header (the row *becomes* the drawer) | Drill-down |
| Modal → its trigger | Modal surface → the control that opened it (when invoked from a control) | Modal open/close from a surface trigger |
| Gallery thumbnail → lightbox | Thumb rect → full-screen rect | Artifact open |
| KPI numeral → detail chart | Card numeral → the chart's headline number | Dashboard drill-down |
| Command palette → ⌘K / search trigger | Palette rect → the field that opened it | Palette close |
| Notification bell → center drawer | Bell icon → drawer header | Center open |
| Expanded table row | Collapsed row → expanded panel (same identity) | Row expand |
| Sorted rows | Pre-sort rect → post-sort rect (identity under reorder) | Sorting (FLIP is sharedElement's list form) |

Implementation note: web renderer uses Motion's `layoutId` within a scoped `<LayoutGroup>`; the FLIP primitive (`src/lib/motion/flip.ts`) is the same mechanism for list forms. Desktop parity: geometry lerp between measured rects (Forge §12.4).

---

## 9. Motion hierarchy

### 9.1 Importance is now a four-rung ladder

| Level | Meaning | Timing | Examples |
|---|---|---|---|
| **I1 — feedback** | The user's action must feel instantaneous | Class floor | Press, focus ring, hover wash, selection |
| **I2 — state** | Notice what changed, then move on | Class middle | Menus, toasts, sort, filter, theme |
| **I3 — context** | The user is changing rooms | Class ceiling | Page transition, modal, palette, drawer |
| **I4 — room** | The whole surface re-homes (tenant, year rollover) | Slowest, deliberate | Campus switch, tenant switch |

**Hierarchy law:** higher levels may interrupt lower ones; a lower level never delays a higher one, and two levels never run the same subject.

### 9.2 The one-subject rules (unchanged)

- At most **one Z move** and **one Pulse** in flight system-wide at any moment.
- Per interaction: **≤ 3 moving elements** simultaneously; timeline **≤ 500ms**.
- A second Z mover waits its turn; it does not crowd the first.

### 9.3 Cascade cap

At most **two orchestration levels** per interaction (list → rows; drawer → fields). A third collapses to simultaneous.

### 9.4 The hierarchy of stillness

What *never* moves — these are the strongest hierarchy signals in the system:

- The page behind a modal (frozen, dimmed — the still object is the subject).
- Table cell text on row hover (only the wash moves).
- Disabled controls (no response at all).
- Window chrome (titlebar, scrollbar) during content motion.
- The element that receives focus (the ring moves, the target doesn't).
- Anything while the user is reading (no ambient motion within 400ms of a keystroke or scroll stop).

---

## 10. The surface catalog — every surface, one rule

Each entry: move-spec → resolved tokens → the one non-negotiable behavior. Durations per §6, easings per §5, springs per §4.

### 10.1 Page transitions
`(Slide E + Fade, D4, I3)` — arrive: 8px East slide + fade, 500ms `emphasized-decelerate`; depart: 8px West + fade at 0.7×. View Transitions API; back-navigation is the exact reverse (W arrival, never a fresh E enter). **Loading never transitions a page** — the skeleton is the page's ghost and appears in place (120ms). Campus/tenant switch is a deliberate **room change**: full-canvas fade to neutral (120ms), new tenant fades in (180ms).

### 10.2 Dialog animations
`(Scale Z, D4, I3)` surface + `(Fade, D3, I2)` overlay. Backdrop fades first (`base`, 180ms); surface scales 0.96 → 1 (`slower`, 380ms) with the final 30% on `dampen` (§4.3). Source-aware origin: scales from the trigger's rect (sharedElement when the trigger is a surface, §8.3) or center for keyboard invocations. Exit: surface 0.98 + fade (220ms), then overlay (120ms). Page behind is frozen. One dialog at a time.

### 10.3 Card animations
Enter: stagger 20ms (`Fade + 4px Slide` toward reading direction, ≤ 150ms). Hover: elevation +1 at `fast` (120ms); navigable cards slide their chevron 4px East at `slow` (260ms) — the arrow may outpace the lift. A 1.02× hover scale is legal **only** on gallery-style non-data cards, using `spring-gentle`. Cards in ledgers, rosters, and tables-as-cards never scale on hover.

### 10.4 Hover animations
Wash or elevation +1, `fast` (120ms), `standard`. Never layout, never travel (except the 4px chevron of §10.3), never scale on data rows. Shadows animate only on already-composited layers; ≤ 8 concurrent hover responses per viewport.

### 10.5 Focus animations
Ring fades in `fast` (120ms), ring edge draws outward `base` (180ms). The element never translates or scales. Keyboard-only visibility (web: `:focus-visible`); pointer focus is silent. The ring is the **one** animation that survives minimal tier (as instant appearance — it is state, not motion).

### 10.6 Loading animations
Skeleton: shimmer sweep 1.6s `linear` (opacity 40→80), fades in `fast`; mirrors the final layout exactly. Button loading: icon → spinner at `fast`, label dims to 90%, width never swaps. KPI count-up: 380–500ms `emphasized-decelerate`, tabular numerals. Determinate progress: `linear`, 1:1 with progress; indeterminate: linear sweep. **Outside skeletons, spinners, and progress, nothing loops.**

### 10.7 Notification animations
Bell dot: `micro-spring` on arrival, then rests (one pulse, then stillness). Center: drawer slides East `slow` (260ms) with 20ms item stagger. Toasts: §10.17. Ambient progress (exports/imports): 2px determinate bar under the header, `linear`.

### 10.8 Command palette animations
`(Scale Z + Fade, D4, I3)` from center — 0.98 → 1, `slower` (380ms), backdrop tint + blur ramp `base` (180ms). Results stagger 20ms (settle from above — N, matching the Z arrival). Keyboard selection: the accent block **slides** between rows at `fast` (120ms) — the eye tracks the block, never the text. Filtering while typing: results crossfade `fast`, no re-stagger. Exit reverses; the palette **closes into its trigger** (sharedElement with the ⌘K/search field, §8.3).

### 10.9 Search result transitions
Debounce 150ms of stillness → results crossfade `fast` (120ms); live counts update in place. Matched substrings get a one-shot highlight wash that fades over `base` (180ms). **First** results stagger (20ms); subsequent keystrokes crossfade only — typing must feel instant, not cinematic. `/` focuses search: the field's ring draws `base`, the header never moves.

### 10.10 Sidebar animations
Collapse/expand: E/W move, `slow` (260ms), `emphasized-decelerate` expand / `emphasized-accelerate` collapse; content column reflows via FLIP. Labels crossfade with 20ms stagger; icons center; rail tooltips grow South (180ms). Active indicator (3px rail): **draws** (120ms) on activation and **re-draws** when the active item changes — it moves, it never re-instantiates (continuous identity).

### 10.11 Expand / collapse
FLIP the container `slow` (260ms); contents fade in staggered (20ms, ≤ 150ms); chevron rotates `fast` (120ms, `toggle-spring` on release). **Never** animate `height` or `width`. Collapse reverses: contents fade out first (0.7×), then the container closes. Expanded row identity via §8.3.

### 10.12 Sorting
FLIP rows to their final positions `slow` (260ms); sort arrow rotates `fast`; stagger follows the **final** order; rows never cross paths in the same frame (direction purity, §4.2 Compass) — the FLIP resolves crossing into a clean cascade. Animate sorting only where the order change is visible and meaningful (≥ 10 rows); small lists sort instantly.

### 10.13 Filtering
**Condensation, not rebuild:** non-matching rows fade out `fast` (120ms) as remaining rows FLIP up `slow`; matching rows fade in after with stagger. Filter counts (KPI chips, badges) fade their numbers `fast`. A filter change never slides the whole page — only the affected surface responds.

### 10.14 Tables
Row enter: `Fade + 4px Slide`, 20ms stagger, `fast`→`base`. **Cell value update:** the changed cell washes once (`base`, 180ms), only changed cells, row stays still. Row hover: wash `fast`, revealed actions fade in `fast` + 4px East. Selection: checkbox draws `draw` (300ms), row wash morphs `base`; batch bar settles from the North `fast`. Pagination: content crossfades `fast`→`base`, scroll preserved, never slides. Expandable rows: §8.3/§10.11. Sticky header: no motion of its own. **Concurrency: ≤ 8 animated elements in a table surface at once** (§12).

### 10.15 Charts (new in v4)
- **Draw-in:** series draws from the axis at `draw` (300ms) per series, 60ms apart, reading order — the chart *builds its argument*.
- **Hover:** crosshair draws (300ms, `draw`); hovered point doubles via `micro-spring`; hovered series emphasizes (color swap `fast`), others dim to 40% (opacity `fast`) — dimming is a color/opacity move on the same layer, never a re-layout.
- **Data update:** the series **morphs** to its new values (SVG path morph — the series is a shared identity, §8.3 list form), axis ticks crossfade `fast`, tooltip fades `fast` (120ms) and tracks 1:1 (no easing while tracking).
- **Empty → data:** empty state fades to the drawn chart at `base` — never a blank plot "animating in".
- Numerals in tooltips/readouts: count-up per §10.6.

### 10.16 Context menus (new in v4)
`(Scale Z + Fade, D3, I2)` — grows from the **pointer's rect** (`slow`, 260ms), origin at the cursor; the chevron/more glyph rotates `fast`. Active row: the accent wash **slides** between rows at `fast` (120ms), Raycast rule. Submenus open **East from the item** (E, not hover-chase); never a second row of motion. Exit: reverse at 0.7×, collapsing *into* the pointer. `Esc` closes; arrow keys move the wash. Reduced motion: fade-only.

### 10.17 Toast messages
`(Slide S-East, D3, I2)` — 16px, `slow` (260ms), `emphasized-decelerate`; exit slides 8px South + fades at 0.7×. Success toasts get **one** `Pulse` glow ring (single 1.2s expand-and-fade, §11.2 of the design system). Max 3 visible; the stack FLIPs `slow` to make room. The newest toast lands at the corner; departure mirrors arrival.

### 10.18 Window transitions
The OS owns resize/minimize/maximize — SDMAS never animates window geometry. **Theme switch:** a single full-canvas wash crossfades 380ms to mask the token swap; no per-widget theme animation. Window activation/deactivation: titlebar hairline brightens (0ms — a paint, not an animation). Campus/tenant switch: room change per §10.1.

---

## 11. Reduced motion & quality tiers

### 11.1 The tiers (unchanged, provider-scoped)

| Tier | Duration cap | Verbs allowed | Blur/glow | Parallax | Loops | Entry point |
|---|---|---|---|---|---|---|
| **precise** (default) | 500ms | All five, all directions | Full | Yes | Live-only | `reducedMotion="user"`, no OS reduce |
| **efficient** | 75ms | Fade only (+ Draw for checks) | Tint only | No | None | OS `prefers-reduced-motion: reduce` |
| **minimal** | 0–120ms | Fade only, single layer | None | No | None | In-app "Reduce motion" toggle or `reduce` + `transparency` |

### 11.2 Provider semantics

`<MotionProvider reducedMotion="user" | "always" | "never">`:

- `"user"` (default): honors the OS setting plus the in-app toggle; the in-app toggle **wins** when it is set.
- `"always"`: the entire app renders at `minimal`, regardless of OS.
- `"never"`: force `precise` (development/QA only — never shipped).

### 11.3 The intensity shutter

`intensity` (0–1) multiplies **distances**, never durations (timing stays constant so the product never feels laggy), and gates Pulse, parallax, and glow:

| Setting | What the user sees |
|---|---|
| `1.0` — Full | Everything in this spec |
| `0.75` — Reduced travel | Parallax halved, pulses halved, slides capped at 12px |
| `0.4` — Efficient | Opacity-only, ≤ 75ms, no slide/scale/parallax |
| `0` — Minimal | 0ms; instant state changes; loops killed except spinner |

### 11.4 In-flight downgrade

When the tier changes mid-animation, any running animation completes its **fade only** — never its slide/scale — then ends. The checkmark Draw survives even in minimal (completion feedback is non-negotiable; it is a static reveal, not motion).

### 11.5 The static-reading rule

Every animation's **first frame is a valid resting state**; every loop has a static reading. If a surface is unreadable without its animation, the animation is wrong.

---

## 12. The performance contract

Non-negotiable; any rule in this document that violates §12 is void. Measured at the 60fps budget: **16.6ms per frame, target ≤ 8ms of actual work, main thread**.

### 12.1 The budget table

| Budget | Cap | Enforcement |
|---|---|---|
| JS main-thread work per animation | ≤ 4ms/frame | Telemetry on long tasks > 50ms |
| Animated properties | `transform`, `opacity`, `stroke-dashoffset`, `clip-path`, one backdrop `filter` only | Lint rule; code review |
| Layout-property animation | **None, ever** — every layout change is FLIP (§12.3) | Lint rule |
| Concurrent animated elements — table surface | ≤ 8 | Engine assertion |
| Concurrent animated elements — shell (sidebar, header) | ≤ 3 | Engine assertion |
| Z moves / Pulses system-wide | 1 / 1 (§9.2) | Engine assertion |
| `will-change` elements in viewport | ≤ 8, set on animation start, removed on finish | Telemetry |
| Backdrop blur layers | 1 fixed layer per Z backdrop; blur never stacked on blur | Review |
| Layout reads during animation | **None** — measurements happen once, before the move (§12.6) | Lint rule |

### 12.2 Compositor-only

Every animation must run on the compositor thread. If an element is not on a composited layer (transform/opacity are the cheapest ways to get one), the animation is downgraded to a color swap or removed.

### 12.3 FLIP for all layout changes

Sort, expand, sidebar reflow, toast stack, filter reflow: measure → invert → play transform → restore (`src/lib/motion/flip.ts` exists today). Animating raw layout properties is a release blocker.

### 12.4 Will-change discipline

Set `will-change` on the element(s) about to animate; remove it on completion. Never more than 8 in the viewport (§12.1). The engine owns this — components never set `will-change` directly.

### 12.5 Concurrency caps

§12.1. A sequence that exceeds a cap is **reduced by the engine**, not deferred by the author — a long-running animation that could not meet its tier is dropped, never stretched.

### 12.6 No reads mid-flight

`getBoundingClientRect` and friends run once, before the move starts. This is what makes FLIP and sharedElement work; violating it janks the very frame it helps.

### 12.7 Frame-drop ladder

Telemetry counts dropped frames per surface:
- **1 dropped frame:** record; no action.
- **2 consecutive dropped frames:** that surface's tier drops one level for the rest of the interaction (`precise` → `efficient`).
- **3 in any 1s window:** the whole viewport drops to `efficient` until the next interaction.

The ladder is automatic, invisible, and self-healing — performance is a design requirement, not an engineering concern.

### 12.8 Measurement

Frames: DevTools Performance / `requestAnimationFrame` gap logging. Main thread: Long Tasks API. Budgets are verified per release (roadmap W5).

---

## 13. Animation architecture — files & APIs

Grounded in the current codebase; gaps are the roadmap.

| Layer | Concept | Exists today | v4 work |
|---|---|---|---|
| Tokens | durations, easings, distances | `src/lib/motion/tokens.ts`, `src/index.css` (`--motion-*`, `--ease-*`) | Add spring presets (§4.3) as data; add budget constants (§12.1) |
| Spec | move grammar → resolved tokens | `useMove` in `src/lib/motion/use-move.ts` | Add I4 level; expose spring resolution |
| Choreography | stagger, sequence, sharedElement | `src/lib/motion/flip.ts` (`useFlipList`, `flipElement`) | New `spring.ts` (preset → engine), new `timeline.ts` (sequence + stagger-from), new `shared-element.tsx` (`layoutId` wrapper) |
| Renderer | WAAPI / CSS / View Transitions / Canvas | `route-transition.tsx` (View Transitions + WAAPI fallback), `animated-count.tsx` | Standardize renderer selection in the engine |
| Guard | tier, intensity, reducedMotion, telemetry | `src/lib/motion/use-motion-tier.ts` (reads OS + toggle) | New `motion-provider.tsx` (context: tier/intensity/reducedMotion), new `motion-budget.ts` (telemetry + ladder) |
| Surfaces | catalog consumers | `sidebar.tsx`, `drawer.tsx`, `toast.tsx`, `command-palette.tsx`, `table/frame.tsx`, `notification-bell.tsx` | Adopt shared elements (§8.3), spring presets, provider |

### 13.1 The move-spec cheat sheet (unchanged)

```
toast            → (Slide, S-East, D3, I2)      → 260ms, emphasized-decelerate
modal surface    → (Scale, Z,     D4, I3)        → 380ms, emphasized-decelerate + dampen
page forward     → (Slide, E,     D4, I3)        → 500ms, emphasized-decelerate
row hover        → (Slide, Z-micro, D2, I1)      → 120ms, standard (elevation only)
sort reorder     → (Slide, E/W,   D2, I2)        → 260ms FLIP
success check    → (Draw, —,      D1, I1)        → 300ms fixed
palette selection→ (Slide, N,     D1, I1)        → 120ms (the wash block travels)
```

---

## 14. Implementation roadmap

Each wave ships with its acceptance criteria; a wave is done when the criteria pass, not when the code merges.

| Wave | Scope | Acceptance criteria |
|---|---|---|
| **W0 · Audit (1 wk)** | Diff every shipped animation in `apps/web` against this spec | A table of every animation site: spec, tier behavior, budget conformance; list of violations as the backlog |
| **W1 · Physics (1–2 wk)** | Spring presets in `tokens.ts`; `spring.ts` engine (WAAPI spring + bezier fallback); swap all `--ease-spring`/`--ease-spring-gentle` CSS usages to engine springs | Every spring settles ≤ 300ms, overshoot ≤ 6%; zero springs on objects > 44px (lint); visual parity with the bezier fallback |
| **W2 · Choreography (1–2 wk)** | `timeline.ts` (sequence, stagger-from); adopt in table rows, palette results, notification center | Stagger quantum 20ms/≤ 150ms enforced by the engine; cascade cap 2; exit = 0.7× everywhere |
| **W3 · Identity (2 wk)** | `shared-element.tsx` (`layoutId` + `LayoutGroup`); adopt row→drawer, lightbox, KPI→detail, palette→trigger, bell→center (§8.3) | Each traveler: origin = trigger, reverse on close, instant swap under minimal tier; no sharedElement without a shared identity |
| **W4 · Guard (1–2 wk)** | `motion-provider.tsx` (tier/intensity/reducedMotion); `motion-budget.ts` (telemetry + frame-drop ladder) | Provider is the only motion policy path; ladder drops tier on 2 dropped frames; no component reads `prefers-reduced-motion` directly |
| **W5 · Hardening (2 wk)** | Charts + context menus per §10.15/§10.16; budget audit per §12; a11y pass (§11); re-capture loop | All §12.1 caps enforced by telemetry in CI; no layout-property animation in the codebase; contrast/status announcements unaffected by any tier |

**Cross-client:** every web surface in §10 has a Forge (CustomTkinter) keyframe equivalent (`DESIGN_SYSTEM_DESKTOP_V3.md` §12–13); W5 includes a reconciliation pass so the two clients render the same choreography within ±8ms.

---

## 15. Do's & Don'ts

**Do**
- Answer every press within 75ms; keep feedback faster than transition, always (§2).
- Give every move a compass direction and let semantics pick it (v3 §2.2).
- Use springs only for gesture-driven, ≤ 44px objects — and let the engine enforce it (§4.2).
- Use one shared identity per interaction, traveling from its trigger (§8.2).
- Keep one Z move and one Pulse per moment; ≤ 3 movers per interaction (§9.2).
- FLIP every layout change; transform + opacity only (§12.1, §12.3).
- Treat reduced motion as a designed tier with a static reading, not a cleanup (§11).
- Let the frame-drop ladder downgrade gracefully (§12.7).

**Don't**
- Don't invent a sixth verb, a diagonal, a new duration, or a new easing outside the tokens.
- Don't spring a panel, a page, a card, or anything over 44px (§4.2).
- Don't animate layout properties — ever (§12.1).
- Don't loop anything that isn't a spinner, shimmer, progress, or live process (§7 of v3).
- Don't re-stagger while typing (§7.1) and don't stagger fewer than three siblings.
- Don't share a `sharedElement` id between things that are not the same thing (§8.2).
- Don't let two elements fight for the viewer's eye (§9.2).
- Don't ship motion that violates §12 — performance is a design requirement.
- Don't let a screen need an animation the grammar can't express — extend the grammar, update this spec in the same commit, or delete the animation.

---

## Appendix A — Master token table

| Token | Value |
|---|---|
| `motion.duration.instant` | 75ms (5f) |
| `motion.duration.fast` | 120ms (7f) |
| `motion.duration.base` | 180ms (11f) |
| `motion.duration.slow` | 260ms (16f) |
| `motion.duration.slower` | 380ms (23f) |
| `motion.duration.slowest` | 500ms (30f) |
| `motion.duration.draw` | 300ms (18f) |
| `motion.ease.standard` | `cubic-bezier(0.4, 0, 0.2, 1)` (supersedes v3's `0.2, 0, 0, 1`) |
| `motion.ease.accelerate` | `cubic-bezier(0.4, 0, 1, 1)` |
| `motion.ease.decelerate` | `cubic-bezier(0, 0, 0.2, 1)` |
| `motion.ease.emphasized` | `cubic-bezier(0.4, 0, 0.1, 1)` |
| `motion.ease.emphasized-decelerate` | `cubic-bezier(0.05, 0.7, 0.1, 1)` (enter) |
| `motion.ease.emphasized-accelerate` | `cubic-bezier(0.3, 0, 0.8, 0.15)` (exit) |
| `motion.ease.spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` |
| `motion.ease.spring-gentle` | `cubic-bezier(0.25, 1.3, 0.5, 1)` |
| `motion.ease.linear` | `linear` |
| `motion.stagger.quantum` | 20ms (cap 150ms) |
| `motion.stagger.from` | first / last / center |
| `motion.exit.scale` | 0.7× enter duration |
| `motion.press.start` | ≤ 75ms |
| `motion.budget.movers` | 3 per interaction |
| `motion.budget.timeline` | ≤ 500ms |
| `motion.budget.cascade` | 2 levels |
| `motion.budget.table` | ≤ 8 concurrent |
| `motion.budget.shell` | ≤ 3 concurrent |
| `motion.budget.z` | 1 |
| `motion.budget.pulse` | 1 |
| `motion.budget.will-change` | ≤ 8 elements |
| `motion.intensity` | 1 · 0.75 · 0.4 · 0 |
| `motion.tier` | precise · efficient · minimal |

## Appendix B — Spring presets

| Preset | visualDuration | bounce | stiffness | damping | mass | Objects | Settle |
|---|---|---|---|---|---|---|---|
| `micro-spring` | 0.20s | 0.20 | 520 | 26 | 0.6 | dots, badges, checks, bell dot ≤ 16px | ≤ 240ms |
| `toggle-spring` | 0.25s | 0.30 | 420 | 24 | 0.8 | switches, chips, radios, chevrons ≤ 36px | ≤ 300ms |
| `press-spring` | 0.12s | 0.10 | 900 | 30 | 0.7 | button press-release 36–44px | ≤ 200ms |
| `dampen` | 0.30s | 0.05 | 300 | 32 | 1.0 | modal/palette final 30% of settle | ≤ 320ms |
| `drag-return` | 0.25s | 0.05 | 280 | 34 | 1.0 | drag ghost return | ≤ 300ms |

## Appendix C — Surface quick reference

| Surface | Move | Resolved |
|---|---|---|
| Page forward | Slide E + Fade, D4·I3 | 500ms, emphasized-decelerate, 8px |
| Page back | Slide W + Fade (reverse) | 350ms (0.7×) |
| Modal | Scale Z (0.96→1) + overlay Fade | 380ms + dampen; overlay 180ms |
| Card hover | Elevation Z-micro, D2·I1 | 120ms standard |
| Card enter | Fade + 4px Slide, stagger 20ms | ≤ 150ms |
| Focus ring | Fade fast + Draw base | 120 + 180ms |
| Skeleton | Fade fast + shimmer loop | 1.6s linear loop |
| Bell dot | micro-spring | ≤ 240ms settle |
| Palette | Scale Z + Fade, D4·I3 | 380ms; selection wash 120ms |
| Palette → trigger | sharedElement | reverse 0.7× |
| Search results | Crossfade fast (debounce 150ms) | 120ms |
| Sidebar | Slide E/W, D3·I2 | 260ms |
| Expand/collapse | FLIP slow + chevron fast | 260ms / 120ms |
| Sort | FLIP slow + arrow fast | 260ms / 120ms |
| Filter | Fade out fast + FLIP slow + fade in | ≤ 260ms |
| Table row enter | Fade + 4px Slide, stagger 20ms | ≤ 150ms |
| Cell update | One-shot wash, D2·I1 | 180ms |
| Chart draw-in | Draw per series + 60ms gap | 300ms each |
| Chart hover | Crosshair draw + point micro-spring | 300ms / 240ms |
| Context menu | Scale Z + Fade from pointer, D3·I2 | 260ms; wash slides 120ms |
| Toast | Slide S-East, D3·I2 | 260ms; exit 0.7× |
| Theme switch | Single full-canvas wash | 380ms |

---

*End of specification. Motion in SDMAS is a language, not a playlist: five verbs, five compass points, a clock, physics for gestures, and a machine that enforces the budget. If a screen needs an animation the grammar cannot express, the grammar — not the screen — is extended first, and this document is updated in the same commit. Per the re-capture loop, the Escapement earns its place by staying true to what ships.*
