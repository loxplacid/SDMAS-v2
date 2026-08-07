# SDMAS Motion System — v3 Specification

**Codename:** *The Compass*
**Status:** Draft for review · **Owner:** Product Design · **Version:** 3.0.0
**Scope:** apps/web (desktop-first) · **Companion doc:** `docs/DESIGN_SYSTEM_V3.md` (the *Corridor* system — this document is the normative expansion of its §11 *Motion*)

> Every screen is a room. Motion is how you walk through the corridor — it must always tell you where you came from, where you're going, and what deserves your eyes. Never why you should be impressed.

---

## 0. Thesis — why motion exists here

SDMAS is a data-heavy operational tool for a school run at the quality of a bank. Motion has exactly **three jobs** in this product, in order of priority:

1. **Wayfinding** — where did I come from, where am I going? (navigation, drill-down, depth).
2. **Feedback** — did my action land, and what changed? (press, sort, filter, save, sync).
3. **Focus** — what should my eyes be on right now? (modals, toasts, live states, the success pulse).

Anything that does not serve one of the three is decoration, and decoration is rejected. Concretely, we reject:

- Marquee/loop/bounce in any functional surface.
- Parallax that cannot be disabled (vestibular safety, §10).
- Springy page transitions or "elastic" navigation.
- Motion as the *only* signal for a state change (always paired with color, icon, or text — §10).
- Any animation on `width`, `height`, `top`, `left`, `margin`, or `font-size` (layout thrash, §9).

---

## 1. Sources & extraction — principles only, nothing copied

| Source | What it demonstrates | Principle extracted | Translation into SDMAS |
|---|---|---|---|
| **ReactBits** | Containers morph continuously; motion *is* the interface, not a layer on it | **Continuous identity** — an element persists across states, it never dies and respawns | Rows expand into drawers, the skeleton *is* the table, menus grow from their trigger. Nothing teleports. |
| **Boris FX (motion blur)** | Motion has velocity, direction, and a global shutter; blur separates the subject from its surroundings | **Directional gravity + intensity control** | Every move carries a semantic direction (§2.2); a global *shutter* token caps aggregate motion (§7); stillness makes the subject. |
| **Linear** | Speed is a feature; precise, short, opacity+transform-only micro-durations; no bounce on functional UI | **The fast clock** — feedback under 150ms, spatial change under 400ms, never slower than the user's patience | Duration classes (§3.1); a hard rule that *feedback* outruns *transition* (press < hover < reveal). |
| **Apple macOS** | Physics-based springs, spatial continuity, sheets that relate to their parent, Reduce Motion as a real mode | **Source-aware continuity + a true reduced tier** | Enter from the trigger, exit in reverse (§4.1); sheets are grounded things; a first-class *minimal* tier (§8). |
| **Framer** | Orchestration as a model: stagger, leader-follower, springs for gestures vs timed curves for brand rhythm | **Choreography as rules, springs for gestures only** | Stagger/cascade rules (§4.3–4.4); springs restricted to pointer-driven motion and small objects (§3.4). |

The output below is original. Where a value resembles a source's, it was chosen because it is the right physics for a *school ledger*, not borrowed.

---

## 2. The grammar — the core model

Every animation in SDMAS is described by exactly four attributes, and everything else (duration, easing, parallax, blur) is **derived** from them by rules. No animation in the product is authored directly.

> **A move = (verb, direction, distance-class, importance-class)**
> — everything else is a rule lookup.

### 2.1 The five verbs

| Verb | What it does | Legal properties | Illegality |
|---|---|---|---|
| **Slide** | Relocate an element on a plane | `translateX/Y` | Never diagonal unless the destination is diagonal (toasts at a corner). |
| **Scale** | Change apparent depth toward/away from the viewer | `scale` (with `transform-origin` at the anchor) | Never on elements > 40% of the viewport; never on text-bearing surfaces in the *efficient* tier. |
| **Fade** | Change visibility in place | `opacity` | Never the *only* verb for a spatial change (§M1). |
| **Draw** | Reveal a shape or stroke (check, chart line, focus ring) | `stroke-dashoffset`, `clip-path`, `transform` | Only on icons, charts, rings, hairlines — never on surfaces. |
| **Pulse** | One-shot attention without moving | `scale` 1 → 1.05 → 1 + `opacity` | One pulse per interaction max; never looping outside live data (§7). |

Every multi-property animation is a **composition** of these verbs with a single leader (§4.5). A modal is `Scale` (leader) + `Fade` (follower). A page transition is `Slide` (leader) + `Fade` (follower). There is no sixth verb.

### 2.2 The Cardinal Compass — direction is a semantic contract

Direction is **not a design choice** in SDMAS; it is the role an element plays in the product. The compass has five points. Naming a direction names the meaning.

| Point | The semantic | Examples | Rule |
|---|---|---|---|
| **E — East** | *Forward.* Deeper into a task. | List → detail, drill-down, next step, sidebar expanding | Forward navigation is always East; deeper = more East. |
| **W — West** | *Back.* Shallower, returning. | Back navigation, collapse, undo a drill | The reverse of any East move is West; never both-fade a return. |
| **N — North** | *Settles from above.* Authority, status, confirmation. | Banners, batch-action bars, success states, notification dot, sync status | Things that announce themselves arrive from the North and rest. |
| **S — South** | *Grounded.* Grows from the earth of the interface. | Menus/dropdowns/popovers, sheets, bottom drawers, toasts (S-East corner) | Things tethered to a trigger grow South from it; dismissal sinks South. |
| **Z — Depth** | *The viewer's attention.* Things that come forward in space. | Modals, command palette, tooltips, focus rings, hover elevation, blur backdrops | One Z move at a time (§4.5); Z is the most expensive point on the compass and is budgeted hardest (§7). |

**The direction rule:** an element's point is fixed by what it *is*, not by where it looks nice. A teacher can never "choose" to make a modal slide; a modal is a Z element, so it scales. This is what makes the system coherent across 80+ screens and infinite future ones.

### 2.3 The Clock — distance classes

Distance is measured from the element's resting position to its final position (or, for Fade/Draw/Pulse, the element's own size).

| Class | Travel | Canonical uses | Rules |
|---|---|---|---|
| **D1 — micro** | ≤ 8px | Press, focus ring, chevron rotate, checkbox check | Never exceeds 120ms. |
| **D2 — in-place** | ≤ 16px | Hover lift, cell value pulse, sort reorder (small), row hover | Never exceeds 180ms. |
| **D3 — surface** | ≤ 64px | Menu, tooltip, toast, drawer reveal, row expand | 180–260ms. |
| **D4 — room** | > 64px, ≤ viewport | Page transitions, window transitions, modal surface, palette | 380–500ms, capped. |

**Duration rule (the clock):** `duration = class floor + 8ms per 16px of travel`, rounded to the token grid, **capped at the class ceiling**. Small objects move faster than large ones; a 40px toast and a 1200px page never share a duration for the same distance class.

### 2.4 Importance — the modifier

| Importance | Meaning | Effect on timing |
|---|---|---|
| **I1 — feedback** | The user's action must feel instantaneous | Pick the *floor* of the class range. |
| **I2 — state** | The user should notice what changed, then move on | Pick the *middle* of the range. |
| **I3 — context** | The user is changing rooms; give them the arrival | Pick the *ceiling* of the range. |

A move is fully specified as `(verb, direction, D-class, I-level)`. The system resolves everything else. Example: a toast is `(Slide S, D3, I2)` → 260ms, `ease.enter`, 16px. A row hover is `(Slide Z-micro via elevation, D2, I1)` → 120ms.

---

## 3. Timing

### 3.1 Duration tokens (extends `DESIGN_SYSTEM_V3.md` §11.2)

| Token | Value | Bound to | Notes |
|---|---|---|---|
| `motion.duration.instant` | 75ms | D1 · I1 — press, focus ring, chevron | The floor for *all* feedback. |
| `motion.duration.fast` | 120ms | D1·I2, D2·I1 — hover, cell pulse, sort arrow | |
| `motion.duration.base` | 180ms | D2, D3·I1 — selection, badge swap, search results | The default UI pulse. |
| `motion.duration.slow` | 260ms | D3 — menus, toasts, drawers, row expand | |
| `motion.duration.slower` | 380ms | D4·I2 — modal surface, palette, window | |
| `motion.duration.slowest` | 500ms | D4·I3 — page transitions, KPI count-up | Soft cap. Nothing is slower. |
| `motion.duration.draw` | 300ms | Draw verb — chart lines, checkmarks | Fixed; Draw is never sped up or slowed. |

### 3.2 Easing tokens

| Token | Curve | Role | Legality rules |
|---|---|---|---|
| `motion.ease.standard` | `cubic-bezier(0.2, 0, 0, 1)` | Default UI motion, state changes | The default for anything unclassified. |
| `motion.ease.enter` | `cubic-bezier(0.05, 0.7, 0.1, 1)` | Arrivals (Slide/Scale into view) | **Never used for exits.** Fast start, soft landing. |
| `motion.ease.exit` | `cubic-bezier(0.3, 0, 0.8, 0.15)` | Departures (Slide/Scale out of view) | **Never used for entrances.** Leaves quickly, fades at the end. |
| `motion.ease.spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Micro-springs — toggles, badges, dots, drops | §3.4 restrictions. |
| `motion.ease.linear` | `linear` | Spinners, shimmer, determinate progress | The only legal loop easing. |

**The easing rules:**

1. **Arrivals start fast** — an enter that eases *in* (slow start) reads as hesitation. `ease.enter` is the only enter.
2. **Departures leave fast** — an exit that eases *out* (slow end) reads as a drag. `ease.exit` is the only exit.
3. **Never ease a loop** — anything that repeats is `linear` or it is removed.
4. **Springs are earned** (§3.4) — over-springing is the single most common amateur tell; SDMAS budgets it hard.
5. Exit duration = **0.7 × enter duration** of the same move. Elements leave faster than they arrive (attention has already been paid).

### 3.3 Transition timing — sequencing, not just duration

| Rule | Value | Example |
|---|---|---|
| Feedback begins | **≤ 75ms after the trigger** | Press response, focus ring, hover wash. If the browser can't start it in 75ms, the animation is too heavy to ship. |
| Overlay leads | Fade-in of dim/blur layer: `base` (180ms) | Modal overlay fades before the surface scales. |
| Surface follows | `slower` (380ms), starts 40–60ms after overlay | The subject arrives *after* the stage is set. |
| Exit reverses | Surface scales out (60% of its enter), then overlay fades (60%) | Leader becomes follower; first in, last out. |
| Stagger quantum | 20ms per sibling, max 150ms total | Table rows, list results, palette entries. |

### 3.4 Springs — where they are legal

Springs model *gesture*, not rhythm. Legal only when **both** of these hold:

1. The motion is driven by a pointer or keyboard gesture (drag, drop, press-release, toggle flick) — not by an automated state change.
2. The object is **small** (≤ 44px in its dominant dimension) — toggles, badges, dots, checkbox marks, drag ghosts.

Springs are expressed as an overshoot-bounded cubic-bezier (the `spring` token) with a **tuned-down overshoot**: the target overshoots by at most 6% of its travel, once, and settles within 300ms. For anything larger (cards, panels, pages, modals), springs are **forbidden** — they read as wobble on data. Modal entry may use a *barely-damped* spring only for its final 30% (§11, worked example 1).

---

## 4. Choreography — the orchestration rules

Choreography is where most design systems fail (everything animates at once, or nothing relates). SDMAS has five orchestration rules; every multi-element animation must satisfy all of them.

### 4.1 Enter = reverse of exit (always)
The exit of any element is its entrance played backwards: same axis, mirrored easing (`enter` ↔ `exit`), 0.7× duration, follower/leader roles swapped. If an element exits differently than it entered, the system is broken — the user's spatial memory is the contract.

### 4.2 Direction purity
Within one transition, **all moving elements share an axis** (E/W, N/S, or Z) unless the transition is itself a depth change. Two elements on crossing axes in the same frame read as a collision. Depth changes (Z) may combine one planar follower with the Z leader, but never two planar followers on opposite axes.

### 4.3 Stagger
Identical siblings (table rows, palette results, notification items) enter in **reading order** — top-left to bottom-right — at a **20ms quantum**, each using `Fade + 4px Slide` toward their direction, total stagger capped at 150ms. Exits stagger in **reverse reading order** (last in, first out). Stagger never applies to fewer than three siblings (three or fewer enter simultaneously).

### 4.4 Cascade cap
At most **two levels** of orchestration may run in one interaction (e.g., list → rows; drawer → fields). A third level collapses to simultaneous. Recursive choreography is forbidden.

### 4.5 One subject per moment
At any instant, at most **one element uses Z** (scale/depth) and at most one uses `Pulse`. Everything else responds with `Fade` or small `Slide`. If two things compete for the viewer's eye, neither is the subject and the design — not the animation — is wrong.

### 4.6 The motion budget per interaction
An interaction may not move more than **three elements at once** in aggregate, and its total animation timeline may not exceed **500ms** (§7 governs the global version of this).

---

## 5. The interaction state machine

Every interactive element passes through states. Each state has a fixed rule; the states are the only place micro-motion lives.

| State | Rule | Duration / easing | Never |
|---|---|---|---|
| **Hover** | Background wash or elevation +1. No layout change. No scale on rows. | `fast` (120ms), `standard` | Animating `box-shadow` on > 8 concurrent elements; moving the element. |
| **Press** | Scale 0.97 *or* shadow compression. Must start ≤ 75ms after pointer-down. | `instant` (75ms) in, `base` (180ms) release | Hover-first delays; scale on dense table rows (cells shift); haptic-less destructive actions. |
| **Focus** | 2px ring fades in; ring draws (Draw verb) 2px offset. No transform. Keyboard-only visibility. | ring fade `fast`, draw `base` | Animating the element itself; showing focus to mouse users. |
| **Disabled** | No animation of any kind. Opacity 45% + `pointer-events: none`. | 0ms | Hover/press/focus responses while disabled. |
| **Selected** | Accent wash morphs in + check Draws (if checkbox). Never a flash. | wash `base`, check `draw` | Pop or bounce on selection. |
| **Dragging** | 1:1 pointer tracking (no easing *during* the drag — easing is only on release). Ghost at 60% opacity. | release: spring settle ≤ 300ms | Easing while tracking; drop without a settle; targets that don't acknowledge (§6.15). |
| **Expanded** | Container grows via FLIP (transform-only, §9); contents Fade-in staggered 20ms. Collapse reverses. | container `slow`, contents stagger ≤ 150ms | Animating `height`; contents that slide instead of fade. |

The golden rule of the state machine: **press precedes hover** (tactile first), **feedback outruns transition** (75ms beats 380ms), and **no state animation may ever change layout** (M3).

---

## 6. Component rules

Every listed surface is a **rule**, not an animation. If you know its verb, direction, and class, you know its motion. All durations reference §3.1 tokens.

### 6.1 Modal animations
- Move: `(Scale Z, D4, I3)` for the surface; `(Fade Z-backdrop, D3, I2)` for the overlay.
- Overlay fades first (180ms); surface scales 0.96 → 1 with a spring-damped final 30% (380ms). Exit: surface scales to 0.98 + fades (220ms), then overlay fades (120ms).
- **Source-aware anchor:** if the modal was invoked from a specific control, `transform-origin` is set to the trigger's position so it appears to grow from it (FLIP, §9). If invoked from a menu/keyboard, origin is center.
- Background: scroll-locked and frozen — **the page behind never moves** when a modal opens (the still object is the subject). Dim `ink.950 @ 45–60%` fades in with the overlay.
- One modal at a time; a second sheet waits for the first to close (§Apple principle: no stacking).

### 6.2 Sidebar animations
- Collapse/expand is an **E/W move**, not a fade: the rail translates out (W) / in (E) at `slow` (260ms), `ease.enter` for expand, mirrored for collapse.
- Content reflow is **FLIP** — the content column resizes via transform-composited layout animation, never `width` animation on the sidebar itself.
- Icon/label swap inside the rail: icons `Fade`+`fast`, labels cross-fade `fast`; tooltips on the rail grow South from the icon (Z-micro, 180ms).
- Active indicator (3px rail): Draws down the item at `fast` (120ms) on activation, and re-draws when the active item changes — it moves, it never re-instantiates (continuous identity).

### 6.3 Page transitions
- Move: `(Slide E + Fade, D4, I3)` for the arriving page; the departing page slides W 8px + fades at 0.7×.
- Slide distance is deliberately **small (8px)** — data pages must not swim; the fade does the work, the slide gives direction.
- Implemented with the **View Transitions API**; the browser snapshots are treated as surfaces and given `motion.ease.enter` / `motion.ease.exit`.
- Back-navigation is the exact reverse (W arrival), never a fresh E enter.
- **Loading never transitions a page:** the skeleton *is* the page's ghost and appears in place (`Fade`, 120ms). The page never "slides in" twice.
- Campus/organization switch is deliberately louder: full-canvas fades to neutral (120ms), new tenant content fades in (180ms). A switch is a *room change*, visually admitted.

### 6.4 Table animations
- **Row enter:** `Fade + 4px Slide` (toward their row's direction), 20ms stagger, `fast`→`base`. Rows never slide long distances.
- **Row update (cell value):** the changed cell "pulses" once — fades to 50% opacity and back, or a single accent/status wash that fades out. `base` (180ms), one shot. Only *changed* cells pulse; the row itself does not.
- **Row hover:** wash `fast`; revealed actions fade in `fast` with a 4px East slide. On tables, hover never scales and never moves the row.
- **Sorting:** rows **FLIP** to their new positions (`slow`, 260ms, `standard`) — the sort arrow rotates `fast`. During reorder, stagger follows the *final* order. Rows never cross paths in the same frame (anti-collision §4.2) — the FLIP resolves crossing into a clean cascade.
- **Filtering:** non-matching rows `Fade` out at `fast` (120ms) as remaining rows FLIP up into place (`slow`); matching rows `Fade` in after with stagger. Filtering feels like condensation, not a rebuild.
- **Selection:** checkbox Draws (`draw`, 300ms), row wash morphs (`base`). The batch bar settles from the North (`fast`, 120ms).
- **Pagination:** content crossfades `fast`→`base`; scroll position is preserved; the table never slides.
- **Expandable rows:** the row expands via FLIP (`slow`), its detail content fades in staggered (≤150ms); collapse reverses. The expanded row is the same identity as the collapsed row (continuous identity) — it *was* a row, it is *now* a panel.

### 6.5 Card hover
- Move: `(Z-micro elevation, D2, I1)`. Elevation steps to `hover` at `fast` (120ms); the hairline ring brightens simultaneously. If the card is navigable, its chevron/arrow slides 4px East at `slow` (260ms) — the arrow may outpace the lift; the lift itself stays fast.
- Cards in dense grids never scale on hover; a 1.02× hover scale is legal **only** on gallery-style non-data surfaces (never ledgers, never rosters, never tables-as-cards).

### 6.6 Button hover
- `(Fade of background state, D2, I1)` at `base` (180ms) for color shifts (`+1` shade on primary, wash on ghost, border strong on secondary). Duration is `base`, not `fast`, because color crossfades at 120ms can strobe on patterned backgrounds.
- Never animates layout (label width, padding). Loading swaps the icon in place at `fast`; the label dims to 90%, never reflows.

### 6.7 Button press
- `(Scale, D1, I1)` at `instant` (75ms), scale 0.97; release returns at `base`. Destructive and danger buttons compress their shadow instead of scaling (visual weight stays heavy).
- Press feedback **must begin within 75ms** of pointer-down — this is the single most important latency number in the system.

### 6.8 Window transitions (desktop framing)
- **Resize / maximize / minimize:** no SDMAS animation — the OS owns the window's physics; animating it fights the platform.
- **Theme switch (light ↔ dark):** a full-canvas wash crossfades (380ms) to mask the token swap; content never individually animates into the new theme. The wash itself is a single fixed layer (perf-safe).
- **Window activation/deactivation:** only the titlebar hairline brightens (0ms — it's a paint, not an animation).
- **Campus switch** follows §6.3's room-change rule.

### 6.9 Notifications
- **Toast:** `(Slide S-East, D3, I2)` — 16px, `slow` (260ms), `ease.enter`. Exit slides 8px South + fades at 0.7×. Success toasts get one `Pulse` glow ring (§11.2), a single 1.2s expand-and-fade. Max 3 visible; new toasts push the stack (FLIP, `slow`).
- **Bell dot:** Scales in with `spring` (300ms settle, small object — legal §3.4) and rests. One arrival pulse, then stillness.
- **Notification center:** a drawer sliding East (`slow`, 260ms) with item stagger (20ms).
- **Ambient progress** (exports, imports): a determinate 2px bar under the header, `linear`, 1:1 with progress. Indeterminate: `linear` sweep loop 2s. Ambient is allowed to loop because it reports a live process (§7).

### 6.10 Command palette
- Move: `(Scale Z + Fade, D4, I3)` from center — 0.98 → 1, `slower` (380ms), with the `blur.lg` backdrop ramping in `base` (180ms). List results stagger 20ms.
- **Keyboard selection moves at 0ms** (the selection is wherever the focus is), but the accent selection block slides between rows at `fast` (120ms) via transform — the user's eye tracks the block, not the text.
- **Filtering while typing:** results cross-fade `fast` (120ms) — the list condenses like the table filter (§6.4); the input caret never animates.
- Exit: reverse, 0.7×. The palette closes *into* the trigger (⌘K origin or the search field) when one exists.

### 6.11 Loading
- **Skeleton:** shimmer sweep (1.6s loop, `linear`, opacity 40→80) — the *only* legal full-surface loop besides progress. Skeletons mirror the final layout exactly and fade in `fast`.
- **Button loading:** icon swaps to spinner (`fast`, 120ms), label dims. Spinner rotation `linear` 0.8s.
- **KPI count-up:** `slower`–`slowest` (380–500ms), `ease.enter`, tabular numerals only, capped at 500ms (§ design system §13.1).
- **Determinate progress:** `linear`, never eased. **Indeterminate:** linear sweep.
- Rule: outside skeletons, spinners, and progress, **nothing loops**.

### 6.12 Search
- Keystroke → results update at `fast` (120ms) cross-fade, debounce 150ms. Live counts update in place (`Fade`, `fast`) — never re-render the whole list while typing.
- Matched substrings get a one-shot highlight wash (status-tint background fading out over `base`, 180ms) — a *Draw*-like reveal, then rest.
- Result rows stagger 20ms on first results; subsequent keystrokes only cross-fade (no re-stagger — typing must feel instant, not cinematic).
- `/` focuses the search field: the field's ring Draws (`base`), the header never moves.

### 6.13 Sorting
- Covered by §6.4 — sorting is a table rule: FLIP + arrow rotate + final-order stagger. Outside tables, sorting is **not animated** (dropdown lists sort instantly; the list is small and the cost of theater exceeds the benefit).
- Rule: animate sorting only where the user can *see* the order change meaningfully (≥ 10 rows).

### 6.14 Filtering
- Condensation rule (§6.4): out = `fast` fade, reflow = FLIP `slow`, in = staggered `fast`. Filters that change counts (KPI chips, filter badges) `Fade` their numbers at `fast`.
- A filter change never slides the whole page; only the affected surface responds.

### 6.15 Selection
- Checkbox Draws (`draw`), row wash morphs `base`. Batch bar settles from the North (`fast`). Clearing selection reverses instantly (0.7×).
- **Selection never animates across rows** (no "wave" effect — it reads as an error, not delight). Multiple rows select simultaneously; only the checkbox Draws are staggered at 20ms when a batch-select happens.

### 6.16 Dragging
- 1:1 tracking, no easing while the pointer holds (direct manipulation is absolute). The dragged ghost floats at 60% opacity, +1 elevation token, hairline preserved.
- **Release:** spring settle ≤ 300ms (small object → legal spring §3.4). Drop targets acknowledge with a `Pulse` (`Pulse`, 300ms) highlight; invalid targets acknowledge with a single red `Pulse` and the ghost returns to origin with a **damped spring** (overshoot ≤ 6%, then rest).
- Drag-and-drop is for rows, tiles, and report-builder canvas items only — never for columns in dense ledgers.

### 6.17 Expanding / collapsing
- FLIP the container (`slow`, 260ms), contents fade in staggered (20ms, ≤ 150ms) — never `height` animation (§9), never contents that slide.
- The expander chevron rotates (`fast`, 120ms). Collapse reverses exactly: contents fade out first (60%), then the container closes.

### 6.18 Focus transitions
- Ring fades in `fast` (120ms), ring edge Draws outward (`base`, 180ms). The element **never translates or scales** on focus — moving the target while the user tabs to it is disorienting at data density.
- Focus *between* fields: caret jumps instantly; only the receiving field's ring fades in. No ring "travel" animation (that belongs to keyboards-and-vanity, not ledgers).
- Keyboard focus is the only way the ring appears (§5 Focus).

### 6.19 Blur transitions
- Blur is a material (§ design system §9.1) and it animates **only as a depth backdrop**: when a Z element (modal, palette) opens, its backdrop's blur ramps 0 → target radius in `base` (180ms) while its tint fades; on close it ramps down (0.7×).
- Rules: blur animates only on a **dedicated backdrop layer** (never on text-bearing surfaces); under the *efficient* tier, blur collapses to a tint-only fade (§8); under `prefers-reduced-transparency`, no blur animation at all.
- No blur "wipes" across a surface, no blur-on-hover (expensive and gimmicky).

### 6.20 Depth transitions
- Depth is the Z point of the compass: elevation changes of **one step or more** animate their shadow at `fast` (120ms) — shadows are cheap *only* if the element is already on a composited layer (§9).
- Parallax (velocity = hierarchy, M2): overlay travels 16px, surface 8px, page 4px — closer is faster, on the same axis, one transition at a time.
- **Hover lift = elevation, never z-index hops** — z-values change only on mount/unmount (§ design system §8.3 ladder).
- Depth transitions are the rarest move in the system and the most budgeted (§7).

---

## 7. The shutter — global motion budget

Borrowed in *principle* from Boris FX's shutter control, and re-invented as a product rule:

**`motion.intensity`** is a global token (0–1). It multiplies *distances* (not durations — timing stays constant so the product never feels laggy), and it gates *Pulse*, *parallax*, and *glow*.

| Setting | What the user sees | Set by |
|---|---|---|
| `1.0` — Full | All moves per this spec | Desktop, default |
| `0.75` — Reduced travel | Parallax halved, pulses halved, slides capped at 12px | `prefers-reduced-motion` *or* low-power device |
| `0.4` — Efficient | Opacity-only moves, ≤ 75ms, no slide/scale/parallax | `prefers-reduced-motion` + `prefers-reduced-transparency` |
| `0` — Minimal | 0ms; instant state changes; loops killed except the spinner | Hard reduced-motion override (§8) |

**Budget rules (global):**
1. An interaction may not move more than **3 elements simultaneously** (§4.6) and its timeline may not exceed **500ms**.
2. Ambient/looping animation is legal only for **live data** (attendance pulse, sync state, export progress). Any loop must rest at least **3 seconds for every 1 second of motion** — except spinners, shimmer, and indeterminate progress, which are functional.
3. At most one Z move and one Pulse may be in flight system-wide at any moment (§4.5).
4. The shutter is a *user* control too: an in-app "Reduce motion" toggle persists alongside the OS setting, and it wins.

---

## 8. Quality tiers — precise / efficient / minimal

Three tiers replace the design system's two and add a hard floor:

| Tier | Duration cap | Verbs allowed | Blur / glow | Parallax | Loops | Entry point |
|---|---|---|---|---|---|---|
| **precise** (default) | 500ms | All five, all directions | Full | Yes | Live-only | Desktop, `prefers-reduced-motion: no-preference` |
| **efficient** | 75ms | Fade only (+ Draw for the checkmark) | Tint only, no blur | No | None | `prefers-reduced-motion: reduce` (transitions) |
| **minimal** | 0–120ms | Fade only, single layer | None | No | None | Hard toggle or `reduce` + `transparency` |

**Tier rules:**
1. Efficient is *not* a stripped design — it is a first-class motion language (opacity-only choreography, still staggered, still sequenced). Information hierarchy never depends on motion.
2. Tier switches at runtime re-apply to **in-flight animations**: any animation still running when the preference changes completes its *fade* only (never its slide/scale).
3. The success checkmark Draws even in minimal tier — it's a static reveal, not motion, and completion feedback is non-negotiable (§0 job 2).

---

## 9. The performance contract

Non-negotiable. Any rule in this document that violates §9 is void.

1. **Transform + opacity only** (M3). Animated properties are exclusively `transform`, `opacity`, `stroke-dashoffset`, `clip-path`, and a single dedicated backdrop layer's `filter`. Everything else is a FLIP.
2. **FLIP for all layout changes** — sort, expand, sidebar reflow, toast stack. Measure → invert → play transform → restore. Never animate layout properties.
3. **`will-change` discipline:** set only on elements about to animate, removed on completion; never more than 8 elements in the whole viewport with `will-change` at once.
4. **Backdrop blur** lives on one fixed layer per Z backdrop; its `filter` animates only between `none` and the target radius (single composite, GPU-friendly). Blur is never stacked on blur.
5. **Compositor-only:** every animation must run on the compositor thread; if a frame drops below 60fps twice in a row, the animation's tier drops (§8).
6. **Concurrency caps:** ≤ 8 simultaneous animated elements in a table surface; ≤ 3 in the shell; exactly 1 Z move (§4.5).
7. **Budget per frame:** a single animation's main-thread work ≤ 4ms. Shadows animate only on already-composited layers (§6.20).
8. **No layout reads during animation** — no `getBoundingClientRect` inside animation frames; measurements happen once, before the move starts (this is what makes FLIP FLIP).

---

## 10. Accessibility — motion as a citizen, not a show

1. **Vestibular safety:** no zoom-pulse loops, no auto-play parallax without an off switch, no full-viewport slides. Any parallax is opt-out and bounded (≤ 16px aggregate). Large Z moves are tier-gated (§8).
2. **Reduced motion is a mode, not a hack:** `prefers-reduced-motion: reduce` selects *efficient*, plus the user toggle selects *minimal*. Both honor the tier rules — this is a supported, designed experience, not an afterthought.
3. **Motion is never the only signal** — every state change pairs motion with color, icon, or text (§ design system §14.5). A `role="status"` announcement accompanies toasts; live counts announce politely.
4. **No infinite attention-grabbing** — ambient loops rest (§7); live indicators can be silenced by the user.
5. **Timing and perception:** all durations ≤ 500ms; no animation waits on the user; nothing loops longer than functionally required.
6. **Focus remains visible and stable** under all tiers (§6.18) — the ring is the one animation that survives minimal mode (as a static ring + instant appearance).
7. **`prefers-reduced-transparency`** kills blur animations (§6.19); **`prefers-reduced-data`** kills decorative gradients and ambient loops per the design system.

---

## 11. Worked examples — the rules composing

Four choreographies, fully derived from the grammar. Nothing below is a new animation; it is the rules applied.

### 11.1 Opening a Student 360 detail from a roster row
1. Row's actions chevron slides East 4px (`Slide E`, D2, I1 → 120ms).
2. Drawer (the row *becomes* the drawer) FLIPs open East (`Slide E`), D3, I2 → 260ms; content column FLIPs (`slow`).
3. Page behind parallaxes West 4px while drawer travels 8px East — same axis, velocity = hierarchy (M2).
4. Drawer contents stagger in, 20ms, `Fade + 4px Slide E` ≤ 150ms.
5. Close: reverse — contents fade out first, drawer slides West, page reflows via FLIP. Total ≈ 420ms, under the 500ms budget.

### 11.2 Recording an attendance mark
1. Teacher presses a student's cell → `Press` (`instant` 75ms) scale 0.97.
2. The status badge flips to its new state: old badge fades out (`fast`), new badge fades in (`fast`) — **in place**, no slide (state change, not spatial).
3. A single `Pulse` (300ms) on the row's status dot confirms the mark.
4. A toast settles at S-East (`Slide S`, 260ms) only if the mark was part of a batch rule (e.g., "absent" auto-applied) — a single mark needs no toast; the row's own state is the feedback.

### 11.3 Command palette open + keyboard navigation
1. ⌘K → backdrop tint + blur ramp (`base`, 180ms); palette scales 0.98 → 1 from center (`Scale Z`, D4, I3 → 380ms).
2. Results stagger 20ms (`Fade + 4px Slide N` — they settle from above, matching the palette's Z arrival).
3. `↓` moves the selection: the accent block slides between rows at `fast` (120ms); the text under it never animates.
4. Typing re-filters: results cross-fade `fast` (120ms), no re-stagger.
5. `Esc` / selection → palette scales to 0.98 + fades (220ms), backdrop fades (120ms). Total exit 0.7× enter.

### 11.4 Year rollover (a page-level transition)
1. Invoking rollover opens a confirm modal (`§6.1` Z move, 380ms).
2. On commit: page transitions East (`Slide E + Fade`, D4, I3 → 500ms); departing page slides West 8px at 0.7×.
3. The rollover summary's KPIs count up (`slowest` 500ms, `ease.enter`, tabular).
4. A determinate progress bar runs `linear` under the header while the job processes — the only loop in the room, and it's functional.
5. Success: one `Pulse` glow on the completion summary, then stillness.

---

## 12. Implementation map

### 12.1 Tokens to add (`src/index.css`, extending the seed)

```
motion.intensity: 1 | 0.75 | 0.4 | 0
motion.duration.{instant,fast,base,slow,slower,slowest,draw}
motion.ease.{standard,enter,exit,spring,linear}
motion.parallax.{overlay:16px, surface:8px, page:4px}
motion.stagger.quantum: 20ms
motion.cascade.max: 2
```

All durations and easings must **replace** the current ad-hoc values in `index.css`; per the governance loop (§ design system §18), a PR that changes a duration without updating this spec is blocked.

### 12.2 Files and APIs

| Surface | Mechanism | Files today |
|---|---|---|
| Page transitions | View Transitions API (`document.startViewTransition`) | `app-layout.tsx`, route wrappers |
| Sort / expand / reflow | FLIP utility (new: `use-flip.ts`) | `table.tsx`, `drawer.tsx`, expandable rows |
| Choreography | New `use-move()` hook exposing `(verb, direction, dClass, iLevel)` → resolved tokens | new |
| Modals / palette / toasts | Existing components consume `motion.*` tokens | `modal.tsx`, `drawer.tsx`, `toast.tsx`, `command-palette.tsx` |
| Skeleton / shimmer | Existing loop, retimed to token | `skeleton.tsx` |
| Tier switching | `use-theme.ts` + `prefers-reduced-*` media queries, single `data-motion-tier` attribute | `use-theme.ts` |
| KPI count-up | Existing component, capped 500ms | `kpi-card.tsx` |

### 12.3 The move-spec cheat sheet

```
(verb, direction, distance-class, importance-class)
Example: toast            → (Slide,  S,     D3,              I2)
Example: modal surface    → (Scale,  Z,     D4,              I3)
Example: row hover        → (Slide,  Z-micro, D2,             I1)   // elevation only
Example: sort reorder     → (Slide,  E/W,   D2,              I2)   // FLIP
Example: success check    → (Draw,   —,     D1,              I1)
```

---

## 13. Do's & Don'ts

**Do**
- Give every move a direction from the compass, and let the semantics pick it (§2.2).
- Enter from the trigger; exit in reverse, at 0.7× (§4.1).
- Keep feedback under 75ms and transitions under 400ms (§3.3).
- Use FLIP for every layout change (§9.2).
- Stagger lists at 20ms, capped at 150ms, in reading order (§4.3).
- Make the page behind a modal perfectly still (§6.1).
- Treat reduced motion as a designed tier, not a cleanup (§8).

**Don't**
- Don't invent a sixth verb, a diagonal, or a new duration outside the tokens.
- Don't animate layout properties — ever (§9.1).
- Don't spring a modal, a page, or anything over 44px (§3.4).
- Don't loop anything that isn't a spinner, shimmer, or live process (§7).
- Don't let two things fight for the viewer's eye (§4.5).
- Don't fade-only a spatial change, and don't slide-only a state change (§2.1).
- Don't ship motion that violates §9 — performance is a design requirement, not an engineering concern.

---

## Appendix A — Master motion token table

| Token | Value |
|---|---|
| `motion.duration.instant` | 75ms |
| `motion.duration.fast` | 120ms |
| `motion.duration.base` | 180ms |
| `motion.duration.slow` | 260ms |
| `motion.duration.slower` | 380ms |
| `motion.duration.slowest` | 500ms |
| `motion.duration.draw` | 300ms |
| `motion.ease.standard` | `cubic-bezier(0.2, 0, 0, 1)` |
| `motion.ease.enter` | `cubic-bezier(0.05, 0.7, 0.1, 1)` |
| `motion.ease.exit` | `cubic-bezier(0.3, 0, 0.8, 0.15)` |
| `motion.ease.spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` |
| `motion.ease.linear` | `linear` |
| `motion.parallax.overlay` | 16px |
| `motion.parallax.surface` | 8px |
| `motion.parallax.page` | 4px |
| `motion.stagger.quantum` | 20ms (cap 150ms) |
| `motion.exit.scale` | 0.7× enter duration |
| `motion.press.start` | ≤ 75ms |
| `motion.budget.per-interaction` | 3 elements, ≤ 500ms |
| `motion.cascade.max` | 2 levels |

## Appendix B — Direction cheat sheet

| Element | Point | Move |
|---|---|---|
| Page forward / drill-down | E | Slide + Fade |
| Page back / collapse | W | Slide + Fade (reverse) |
| Menu, dropdown, popover, sheet, toast | S | Slide from trigger/corner |
| Banner, batch bar, success, status dot, bell | N | Slide/settle from above |
| Modal, palette, tooltip, focus ring, hover lift | Z | Scale / Draw / elevation |
| Table sort, filter, expand | E/W + Z-micro | FLIP + Fade |

---

*End of specification. Motion in SDMAS is a language, not a playlist: five verbs, five points on a compass, a clock, and rules. If a screen needs an animation that the grammar cannot express, the grammar — not the screen — is extended first, and this document is updated in the same commit. Per the re-capture loop, this spec earns its place by staying true to what ships.*
