# SDMAS Micro-Interactions v3 — "The Gloss"

> The sixth normative expansion of the Corridor system (after Design System
> v3, Motion System v3, the App Redesign, the Table System v3, and the
> Component Library v3). Codename: **The Gloss** — the finish that makes a
> tool feel engineered rather than assembled.
>
> **Scope:** 252 micro-interactions across 15 interaction families. Each entry
> specifies the felt effect, the exact move-spec + duration + easing, the
> reduced-motion tier behavior, and *why* it raises perceived quality. This is
> the **implementation layer** of `MOTION_SYSTEM_V3.md` (the grammar) bound to
> the components of `COMPONENT_LIBRARY_V3.md` (the parts).
>
> **Companion docs:** `MOTION_SYSTEM_V3.md` (move specs, durations, tiers,
> choreography), `DESIGN_SYSTEM_V3.md` (tokens), `COMPONENT_LIBRARY_V3.md`
> (component IDs cited throughout), `TABLE_SYSTEM_V3.md` (The Ledger),
> `ANALYTICS_SYSTEM_V3.md` (The Watchtower).

---

## 0. How this was derived

Six sources, principles only — nothing copied, everything adapted to a
data-tool's restraint:

| Source | Principle extracted | Where it lands here |
|---|---|---|
| **Apple** | Cause and effect are inseparable: the response names the gesture. A click that does nothing is a lie. | §3 rules 1–3; the 75ms feedback floor |
| **Notion** | Restraint is the luxury: most things should *not* move. The felt quality is in what stays still. | §3 rule 6 (stillness); hover entries that wash, never bounce |
| **Linear** | State changes are answered instantly and precisely — a checkbox check that draws, a save that ticks. | K-family (press), N-family (feedback), the draw verb |
| **Arc Browser** | Spatial continuity: the moving element *is* the navigation — tabs that glide, panes that reflow. | P-family, D-family FLIP, sidebar choreography |
| **Framer** | Material physics on small objects only — springs for thumbs, never for panels. | §3 rule 4; spring legality per §3.4 of Motion |
| **ReactBits** | Micro-choreography: several tiny motions compose into one readable gesture (enter + accent + wash). | §2 anatomy; stagger and cascade rules |

The existing grammar is normative: every entry below is written in the
move-spec language `(verb, direction, distance, importance)`, uses the
duration table (instant 75 / fast 120 / base 180 / slow 260 / slower 380 /
slowest 500 / draw 300 ms), obeys exit = 0.7 × enter, and degrades through
the three tiers (precise / efficient / minimal).

---

## 1. Philosophy

A micro-interaction is **one cause, one felt effect, one subject** — the
smallest unit of perceived quality. It is not decoration; it is the
application *answering*. The Gloss is complete when:

1. **Every gesture is answered within 75ms** — the user never wonders
   whether the app heard them.
2. **Every state change is legible** — something visibly became different,
   and it is obvious *what*.
3. **Nothing moves that the user did not touch** — stillness is a feature.
4. **Every motion has a reason** — an interaction that cannot be explained
   in one sentence is deleted.

**What The Gloss is not:** hover zoom on data, bounce-on-everything,
looping attention seekers, and motion that delays the user. A
micro-interaction that costs a second of the user's time is a defect.

---

## 2. Anatomy — the four fields

Every entry in the catalog is four lines:

- **Felt** — what the user perceives (the cause-effect story, not the CSS).
- **Spec** — the move spec `(verb, dir, distance, importance)`, duration,
  easing. Exits are always 0.7× their enter unless stated.
- **Tier** — precise / efficient (opacity-only ≤75ms) / minimal (instant).
  Entries state their own degradation.
- **Why** — the perceived-quality argument, one line. If the argument
  cannot be made, the interaction does not ship.

Cross-references cite Foundry components (`A1 Button`, `E1 DataTable` …)
from `COMPONENT_LIBRARY_V3.md`.

---

## 3. The house rules — laws every entry obeys

1. **75ms floor.** Feedback begins within 75ms of the trigger or it is too
   heavy to ship. Hover washes, press scales, focus rings — all instant-tier
   work.
2. **One subject per moment.** A trigger produces exactly one primary
   moving element. Secondary elements (backdrop, staggered siblings) are
   followers on the same clock.
3. **Exit = reverse, at 0.7×.** Departures mirror arrivals and leave faster.
   First in, last out.
4. **Springs are earned.** Legal only for gesture-driven, ≤44px objects
   (§3.4 of Motion). Overshoot ≤ 6%, settle ≤ 300ms. Panels, pages, cards:
   never.
5. **Direction is a contract** (§2.2 of Motion). E = forward, W = back,
   S = grounded, Z = depth. Back-navigation is always a W-arrival.
6. **Stillness wins ties.** When two options look equal, the one that moves
   less is correct.
7. **No loops except the licensed four.** Spinner rotation, skeleton
   shimmer, sync-breath, heat-band wash. Everything else ends.
8. **Loops die under efficient, freeze under minimal.** Any repeating motion
   must have a static reading.
9. **Stagger quantum = 20ms, cap 150ms.** Longer cascades read as lag.
10. **The last frame is the truth.** End states must be reachable without
    the animation (tiers, no-WAAPI fallbacks) — the Gloss never gags.

---

## 4. The catalog — 252 micro-interactions, 15 families

Family keys: **H** Hover · **K** Press & click · **F** Focus ·
**T** Typing & inputs · **S** Selection · **L** Loading & saving ·
**D** Drag & drop · **X** Expand & collapse · **O** Overlays & dialogs ·
**N** Notifications & feedback · **P** Page & navigation ·
**C** Search & command · **G** Graphics & charts · **W** Window & shell ·
**Z** Context & system.

---

### H — Hover (24)

**H01 — Button tint** · pointer enters `A1 Button`
Felt · the button states its temperature: filled variants deepen a shade, ghost variants gain a wash.
Spec · `(fade, Z, D1, I1)` · 120ms fast · standard.
Tier · efficient 60ms fade; minimal none.
Why · the first 75ms of contact; without it the cursor feels ignored.

**H02 — Button press** · pointer presses down
Felt · the button physically answers — scale 0.97, then springs back on release.
Spec · `(scale, Z, D1, I1)` · 75ms instant down / spring back ≤ 300ms (≤44px object, legal).
Tier · minimal: none.
Why · the single most-felt interaction in the app; it is the handshake.

**H03 — Icon button tint** · pointer enters `A2 IconButton`
Felt · the icon warms from `ink.600` to `ink.900`; the 32px hit area stays put.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · 60ms.
Why · icons that "fill with intent" read as alive without shifting layout.

**H04 — Card lift** · pointer enters `G1 Card` interactive variant
Felt · the card rises 2px and its shadow deepens — the surface announces it is reachable.
Spec · `(scale, Z, D1, I2)` translate 2px · 180ms base, enter ease.
Tier · efficient: shadow + hairline only, no travel; minimal none.
Why · elevation is the classic premium affordance — but only 2px, because a card that floats is a card that wobbles.

**H05 — Card arrow slide** · pointer enters `G1` hub/interactive
Felt · the chevron slides 4px toward the destination; the title never moves.
Spec · `(slide, E, D1, I1)` · 180ms · standard.
Tier · fade only.
Why · the arrow travels while the text stays — movement is *direction*, not chaos.

**H06 — Table row wash** · pointer enters `E1 DataTable` row
Felt · the row wakes with a 40% wash; content and dividers stay pixel-still.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · 60ms.
Why · the Ledger rule: a row that never "jumps" reads as engineered.

**H07 — Row actions reveal** · pointer enters a row's action cell
Felt · ghost icon actions fade in *and* gain focus-reveal parity — keyboard users get the same reveal.
Spec · `(fade, Z, D1, I1)` · 120ms, 20ms per action.
Tier · efficient: always visible at 60% (no hover-only on touch).
Why · hover reveals nothing the keyboard cannot reach; the reveal is a courtesy, not a gate.

**H08 — Cell hover (grid)** · pointer enters a numeric cell
Felt · the cell warms slightly and the tabular numeral gains weight; alignment never shifts.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · 60ms.
Why · the eye is guided to the readable value without the grid moving.

**H09 — Sidebar item** · pointer enters `F6 Sidebar` item
Felt · a left 3px indicator bar draws and the label warms.
Spec · `(draw, E, D1, I1)` 300ms draw; text `(fade, Z, D1, I1)` 120ms.
Tier · efficient: wash only.
Why · the indicator *draws toward* the item — the destination announces itself.

**H10 — Nav underline** · pointer enters `F1 Tabs` / `A9 Link`
Felt · a 2px accent hairline draws in from the left edge.
Spec · `(draw, W, D1, I1)` · 300ms draw (fast-feel via quick start).
Tier · efficient: static underline.
Why · a drawn underline is directional; a faded one is ambiguous.

**H11 — Chip hover** · pointer enters `C3 Chip`
Felt · the chip's hairline strengthens and the × warms to danger-light.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · 60ms.
Why · the removable affordance announces itself exactly where the user's cursor already is.

**H12 — Avatar ring** · pointer enters `E6 Avatar` in a group
Felt · the overlapping avatar slides forward 2px and its surface ring appears.
Spec · `(slide, S, D1, I1)` · 120ms.
Tier · none.
Why · identity surfaces on contact — who am I looking at, confirmed in 120ms.

**H13 — Chart point hover** · pointer enters a chart point (Watchtower)
Felt · the point doubles in radius and its halo fades in; the readout in the header swaps to the hovered value.
Spec · point `(scale, Z, D1, I1)` 120ms; readout swap `(fade, Z, D1, I1)` 120ms (two subjects, one gesture — the point and its echo).
Tier · efficient: readout swap only.
Why · hover is interrogation: the point answers with its number.

**H14 — Chart bar hover** · pointer enters a bar
Felt · the bar brightens a shade and a vertical hairline crosshair sweeps to its center.
Spec · wash `(fade, Z, D1, I1)` 120ms; crosshair `(draw, S, D1, I2)` 300ms.
Tier · wash only.
Why · the crosshair *travels* — it connects the bar to the time axis, which is the chart's whole argument.

**H15 — Heatmap cell hover** · pointer enters `H6 HeatBand` cell
Felt · the cell brightens to full intensity and its value appears in the readout.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · 60ms.
Why · intensity ramps read as data; a hover that brightens says "I am the value here."

**H16 — Timeline node** · pointer enters `E4 Timeline` event
Felt · the dot rings (2px halo) and the row washes.
Spec · halo `(scale, Z, D1, I1)` 120ms spring (8px dot — legal).
Tier · wash only.
Why · the event's moment is *here* — the halo is the timestamp made visible.

**H17 — Kanban card** · pointer enters `E17 Kanban` card
Felt · the card's shadow lifts a notch and its border warms.
Spec · `(scale, Z, D1, I1)` · 120ms.
Tier · none.
Why · cards are handles — they must *offer* to be moved.

**H18 — Breadcrumb** · pointer enters `F4 Breadcrumbs` crumb
Felt · the crumb darkens and the separator stays muted; current crumb ignores hover.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · 60ms.
Why · only the *path you can still take* responds.

**H19 — Toggle track** · pointer enters `A5 Toggle`
Felt · the track warms toward accent before the switch is touched.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · none.
Why · anticipation: the track concedes before the knob commits.

**H20 — Accordion header** · pointer enters `F3 Accordion` header
Felt · the header washes and the chevron warms.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · 60ms.
Why · the whole header is the target — the wash says so.

**H21 — Toolbar icon** · pointer enters `G9 Toolbar` item
Felt · the icon gains a 40% circular wash, nothing else.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · none.
Why · toolbars are dense; the wash is the smallest legible answer.

**H22 — Tree node** · pointer enters `E16 TreeView` node
Felt · the row washes and the disclosure chevron warms.
Spec · `(fade, Z, D1, I1)` · 120ms.
Tier · 60ms.
Why · deep hierarchies need the current row to be obvious without moving.

**H23 — Notification item** · pointer enters `C8 NotificationItem`
Felt · unread items keep their accent hairline; the row warms and the dot stops pulsing while hovered.
Spec · row `(fade, Z, D1, I1)` 120ms; dot pause (state change, no motion).
Tier · 60ms.
Why · hover is attention — the live dot defers to it.

**H24 — Drop-zone** · pointer (drag payload) enters `B12 FileUpload` zone
Felt · the zone's dashed border solidifies into accent and the wash fills.
Spec · `(fade, Z, D1, I2)` · 180ms base.
Tier · efficient: border color only.
Why · the zone *invites* before the drop; a drag that silently accepts feels accidental.

---

### K — Press & click (20)

**K01 — Checkbox check** · click `A6 Checkbox`
Felt · the box fills accent and the checkmark draws in one stroke.
Spec · box `(fade, Z, D1, I1)` 75ms; check `(draw, Z, D1, I1)` 300ms draw, 40ms after the box.
Tier · efficient: fill only; minimal: instant state.
Why · the draw is the confirmation — the check writes itself, the user reads it.

**K02 — Radio dot** · click `A7 Radio`
Felt · the outer ring warms and the inner dot pops.
Spec · dot `(scale, Z, D1, I1)` 120ms spring (16px — legal).
Tier · 60ms fade.
Why · one exclusive dot, one pop — selection made physical.

**K03 — Toggle flick** · click `A5 Toggle`
Felt · the knob travels 20px and the track fills; release lands with a micro-spring.
Spec · `(slide, E/W, D1, I1)` 180ms base, track fill same clock, spring settle ≤ 300ms.
Tier · efficient: knob only, no spring.
Why · the flick is the archetypal switch feel — but on 180ms, not 400, because data tools don't luxuriate.

**K04 — Segmented wash** · click `A8 SegmentedControl` segment
Felt · the selected wash *slides* from the old segment to the new one; text weight changes with it.
Spec · `(slide, E/W, D1, I2)` 180ms, FLIP on the single wash element.
Tier · efficient: crossfade.
Why · one element carries the whole answer — the wash traveling IS the selection.

**K05 — Tab activate** · click `F1 Tabs` tab
Felt · the underline slides to the tab; the panel crossfades in.
Spec · underline `(slide, E/W, D1, I1)` 180ms; panel `(fade, Z, D2, I2)` 180ms.
Tier · efficient: fades only.
Why · the underline slides (the tab that owns the page), the panel fades (content swap, never a slide).

**K06 — Card select** · click `G1` interactive card
Felt · the card's hairline becomes accent and a 2px rail draws on the leading edge.
Spec · rail `(draw, E, D1, I1)` 300ms; hairline fade 120ms.
Tier · hairline only.
Why · selection is stated by a *drawn boundary*, not a flash.

**K07 — Row click (drill)** · click `E1` row
Felt · the row flashes a 40% accent wash that decays over 300ms, then navigation begins.
Spec · wash `(fade, Z, D1, I1)` 180ms in, decay out; the route transition is P01.
Tier · efficient: wash only.
Why · the row acknowledges the tap before the page leaves — the last frame of the old context.

**K08 — Click-to-copy** · click a copyable value
Felt · the icon swaps to a check that draws; 1.6s later it fades back.
Spec · check `(draw, Z, D1, I1)` 300ms; revert `(fade, Z, D1, I1)` 160ms after a 1.6s hold.
Tier · efficient: icon swap only.
Why · the check is the receipt; the slow revert is the calm.

**K09 — Delete danger** · click a destructive `A1` button
Felt · the button's ring flashes danger-light for 200ms before the confirm dialog opens (K10).
Spec · ring `(fade, Z, D1, I1)` 120ms; dialog per O01.
Tier · none (the confirm dialog still opens).
Why · the flash says "this one is different" — anticipation before destruction.

**K10 — Confirm gate** · click `D2 ConfirmDialog` confirm
Felt · the confirm button darkens, the backdrop holds, the destructive action fires with the button's press.
Spec · press per K02; no extra flourish — destruction is answered by *results*, not confetti.
Tier · n/a.
Why · the most important click in the app must feel *final*, not festive.

**K11 — Menu trigger** · click `D6 DropdownMenu` / `A10 ActionMenu` trigger
Felt · the chevron rotates 180° and the menu scales from the trigger's corner.
Spec · chevron 180ms; menu `(scale, Z, D2, I2)` 260ms slow, origin at the anchor.
Tier · efficient: fade only.
Why · the menu grows *from* the trigger — spatial ownership, the Arc principle.

**K12 — Date day select** · click a day in `B9 DatePicker`
Felt · the day pops to accent fill with a small scale settle, then the popover closes.
Spec · `(scale, Z, D1, I1)` 120ms spring (36px — legal); close per O05.
Tier · efficient: fill only.
Why · the chosen day lands with a tiny *click* — commitment made physical.

**K13 — Chip add** · click a facet value
Felt · the chip enters with a scale-settle into the rail and the row set FLIPs.
Spec · chip `(scale, Z, D1, I1)` 120ms; rail FLIP 260ms.
Tier · efficient: fade.
Why · the filter commits in two beats: the chip lands, the rows reflow.

**K14 — Chip remove** · click a chip's ×
Felt · the chip scales out and the × stays put; the rail FLIPs closed.
Spec · chip exit `(scale, Z, D1, I1)` reverse 0.7× (84ms); FLIP 260ms.
Tier · efficient: instant removal.
Why · the × is the anchor — the chip leaves, the cursor stays.

**K15 — Pagination page** · click `E3 Pagination` page
Felt · the new page button fills accent and the table body FLIPs to the new page's identity.
Spec · button 120ms; body FLIP 260ms.
Tier · efficient: fades.
Why · page change is a reflow, not a reload — the body keeps its rows' identities.

**K16 — Sort header** · click `E1` sortable header
Felt · the sort arrow pops between states (none → up → down) and the rows FLIP.
Spec · arrow `(fade, Z, D1, I1)` 120ms; rows FLIP 260ms.
Tier · efficient: arrow swap.
Why · the arrow is the cause, the FLIP is the effect — one gesture, one story.

**K17 — Stepper complete** · click past a `F5 Stepper` step
Felt · the step's circle fills success and the check draws.
Spec · fill 120ms; check `(draw, Z, D1, I1)` 300ms.
Tier · efficient: fill only.
Why · completion is *written*, not flashed — progress becomes durable.

**K18 — Rating pop** · click a star (if ratings appear)
Felt · the clicked star and its left siblings pop in sequence, right-to-left.
Spec · 20ms stagger, `(scale, Z, D1, I1)` 120ms each, cap 150ms.
Tier · efficient: static fill.
Why · the cascade is the reward for choosing — brief, bounded, over.

**K19 — Tab close** · click a closable tab's ×
Felt · the tab compresses toward the × and the neighboring tabs FLIP to close the gap.
Spec · compress 180ms; FLIP 260ms.
Tier · efficient: fade.
Why · the tab dies where the × was, and the row sews itself shut.

**K20 — Fullscreen toggle** · click the Watchtower fullscreen
Felt · the chart frame scales to the viewport with the overlay dimming behind.
Spec · `(scale, Z, D4, I3)` 380ms slower; overlay fade 180ms first.
Tier · efficient: fade.
Why · fullscreen is a *transition to a place*, not a resize — the frame travels.

---

### F — Focus (16)

**F01 — Input focus ring** · keyboard focuses `B1 Input`
Felt · a 2px accent ring blooms 2px around the field; the border never changes color alone.
Spec · `(fade, Z, D1, I1)` 75ms instant.
Tier · minimal: none (ring is state, always visible to keyboard users).
Why · the ring is the keyboard's cursor — it must be instant and unmistakable.

**F02 — Input focus (pointer)** · mouse focuses `B1`
Felt · nothing animates; the ring appears only if the browser's focus-visible says so.
Spec · n/a — pointer focus is silent.
Tier · n/a.
Why · the ring belongs to the keyboard; pointer users already know where they are.

**F03 — Search widen** · focus `B7 SearchInput` / `C-family` search
Felt · the search field widens 320→480px; the kbd hint (`/`) fades away.
Spec · width `(slide, E, D1, I2)` 180ms base; hint `(fade, Z, D1, I1)` 75ms.
Tier · efficient: no travel.
Why · the field *opens* for the query — focus is an invitation to type more.

**F04 — Clear affordance** · type into a searchable input
Felt · the × fades in at the field's right; the kbd hint yields to it.
Spec · `(fade, Z, D1, I1)` 75ms instant.
Tier · minimal: none.
Why · the escape hatch appears exactly when there is something to clear.

**F05 — Select open** · focus/activate `B3 Select`
Felt · the chevron rotates and the list scales from the trigger.
Spec · per K11.
Tier · per K11.
Why · the list claims ownership of the trigger's corner.

**F06 — Combobox list** · type in `B4 Combobox`
Felt · the suggestion list scales in and the active row's wash slides as arrows move.
Spec · list `(scale, Z, D2, I2)` 260ms; wash `(slide, N, D1, I1)` 120ms.
Tier · efficient: fades.
Why · the list arrives as the first keystroke lands — search feels like conjuring.

**F07 — Row actions focus** · Tab reaches a table row's action cell
Felt · the ghost actions reveal (same as H07) — keyboard parity with hover.
Spec · per H07.
Tier · per H07.
Why · no mouse-only paths; the Gloss never strands the keyboard.

**F08 — Tooltip focus** · focus `D5 Tooltip` trigger
Felt · the tooltip fades in after 400ms of sustained focus.
Spec · `(fade, Z, D1, I1)` 120ms.
Tier · none.
Why · the tooltip treats focus like hover — parity is non-negotiable.

**F09 — Date grid focus** · arrow-key inside `B9 DatePicker` grid
Felt · the active day's ring travels with the arrows; the header date readout updates.
Spec · ring `(fade, Z, D1, I1)` 75ms per move; readout `(fade, Z, D1, I1)` 120ms.
Tier · efficient: readout only.
Why · the ring follows the cursor without scrolling the grid — the calendar is a *surface*, not a page.

**F10 — Dialog initial focus** · `D1 Modal` opens
Felt · the first focusable (or the safe default) receives the ring as the panel settles.
Spec · ring 75ms, timed with the panel's landing (O01).
Tier · minimal: ring only.
Why · the dialog states its keyboard entry point before the user asks.

**F11 — Kbd hint** · focus the app header search
Felt · the `⌘K`/`/` tile highlights; nothing else moves.
Spec · `(fade, Z, D1, I1)` 75ms.
Tier · none.
Why · the shortcut is reaffirmed at the exact moment it is useful.

**F12 — Sidebar item focus** · Tab reaches `F6` item
Felt · the item's indicator draws and the label warms (H09's focus twin).
Spec · per H09.
Tier · per H09.
Why · navigation announces itself identically to pointer and keyboard.

**F13 — Checkbox focus ring** · focus `A6`
Felt · a 2px ring around the box, offset 2px.
Spec · 75ms instant.
Tier · minimal: none.
Why · the box is small; the ring must be precise, never fuzzy.

**F14 — Tab focus** · focus `F1` tab
Felt · a full 2px ring around the tab; the underline stays put until activation.
Spec · 75ms.
Tier · minimal: none.
Why · focus and selection are different states — the ring says "keyboard here", the underline says "this is active".

**F15 — Command palette focus** · open `D8 CommandPalette`
Felt · the input receives focus and its caret blinks; results stagger in around it.
Spec · per O11; results per C03.
Tier · per O11.
Why · the palette is a text field first — the caret is the cursor of command.

**F16 — Listbox active row** · arrows in `D6` / `B3` / `B4` lists
Felt · the active row's wash slides from row to row, never fading and re-fading.
Spec · `(slide, N, D1, I1)` 120ms.
Tier · efficient: no wash movement (row swap only).
Why · the eye tracks the wash, not the text — the selection *travels*.

---

### T — Typing & inputs (18)

**T01 — Keystroke echo** · type in any input
Felt · characters appear at native speed; the caret moves without animation.
Spec · none — text entry is never animated.
Tier · n/a.
Why · the word is the feedback; animating it would be noise between the fingers and the field.

**T02 — Search debounce pulse** · type in `B7` search
Felt · after 180ms of stillness the results FLIP; the input's own border does not pulse (the results ARE the pulse).
Spec · results FLIP 260ms.
Tier · efficient: crossfade.
Why · the debounce is a *silence*, not a spinner — the app waits with you.

**T03 — Validation error** · submit with an invalid `B1`
Felt · the ring turns danger and the inline message slides in below.
Spec · ring 75ms; message `(slide, N, D1, I1)` 120ms.
Tier · efficient: ring only.
Why · the error arrives at the field, not in a distant banner — cause and effect share a coordinate.

**T04 — Error shake** · submit an *already-touched* invalid field again
Felt · the field shakes 4px, three ticks, once.
Spec · `(slide, E/W, D1, I1)` 4px × 3, 300ms total, then still.
Tier · minimal: none.
Why · the shake is the second warning — the first warning was the message; repeat offenders get the nudge.

**T05 — Character count** · type near a limit
Felt · the counter warms from muted to warning as the limit approaches, then danger.
Spec · `(fade, Z, D1, I1)` 120ms per threshold.
Tier · none (color + number).
Why · the count states the runway without ever being a modal.

**T06 — OTP advance** · type a digit in `B13 OTPInput`
Felt · the digit pops in and the caret travels to the next empty cell.
Spec · digit `(scale, Z, D1, I1)` 75ms; caret travel is instant (focus).
Tier · minimal: none.
Why · the code assembles itself left-to-right — the travel *is* the progress.

**T07 — Number step** · press `B6 NumberInput` stepper
Felt · the value pops (1→1.03→1 scale) and the tabular numeral re-settles.
Spec · `(scale, Z, D1, I1)` 120ms.
Tier · none.
Why · the pop marks a *committed increment* — fast, small, over.

**T08 — Password reveal** · toggle `B8 PasswordInput`
Felt · the eye icon crossfades between open/closed and the dots swap to text.
Spec · icon `(fade, Z, D1, I1)` 75ms.
Tier · none.
Why · the swap is instantaneous — a secret is revealed, not choreographed.

**T09 — Suggestion insert** · commit a `B4` suggestion
Felt · the suggestion's text lands in the field and the list closes; the field's ring stays.
Spec · list close per O09; no text animation.
Tier · per O09.
Why · the committed value is the result — animating the text itself would be redundant.

**T10 — Date typing normalize** · type `3/2/2026` in `B9`
Felt · as the field parses, it normalizes to `03/02/2026` with a subtle tabular re-set.
Spec · `(fade, Z, D1, I1)` 75ms on normalization.
Tier · none.
Why · the field *confirms understanding* the moment it understands — the normalize is the nod.

**T11 — Tag commit** · type a term and press Enter
Felt · the term becomes a `C4 Tag` chip that pops into the field's chip row.
Spec · chip `(scale, Z, D1, I1)` 120ms.
Tier · 60ms.
Why · free text becomes a structured object with one pop — input converted to data.

**T12 — Textarea autogrow** · type past the bottom of `B2 Textarea`
Felt · the field grows one line at a time; content never jumps.
Spec · height `(slide, S, D1, I1)` 120ms per line.
Tier · efficient: no travel.
Why · the field follows the text instead of fighting it — a wall that grows.

**T13 — Clear button** · click the search ×
Felt · the field empties and the × fades; the results FLIP back.
Spec · × `(fade, Z, D1, I1)` 75ms; FLIP 260ms.
Tier · minimal: instant.
Why · clearing is one action with two echoes — the field and the world both reset.

**T14 — Fill state** · a field receives a value
Felt · the field gains its label's full weight and hairline; no celebration.
Spec · `(fade, Z, D1, I1)` 75ms.
Tier · none.
Why · a filled field is a *state*, not an event — it announces once, quietly.

**T15 — Amount pop** · a currency field commits
Felt · the tabular numeral re-settles with a micro-pop and the ₦ prefix aligns.
Spec · `(scale, Z, D1, I1)` 75ms.
Tier · none.
Why · money snaps to its grid — alignment is the premium detail.

**T16 — IME composition** · type in a composing field (search)
Felt · results pause during composition and resume on commit.
Spec · n/a — logic, not motion.
Tier · n/a.
Why · respecting IME is invisible quality — the app never fights the user's keyboard.

**T17 — Inline hint swap** · an input's hint changes with focus
Felt · the helper text crossfades to the focus hint.
Spec · `(fade, Z, D1, I1)` 120ms.
Tier · 60ms.
Why · the field teaches at the moment of attention — help where the eyes are.

**T18 — Undo field** · type after an undo
Felt · the restored value re-settles with a subtle wash (the cell that came back).
Spec · wash `(fade, Z, D1, I1)` 120ms, decays.
Tier · none.
Why · restored text wears a memory — the wash says "this just came back".

---

### S — Selection (16)

**S01 — Row select** · click `E1` row checkbox
Felt · the box draws its check and the row gains an accent wash.
Spec · check `(draw, Z, D1, I1)` 300ms; wash `(fade, Z, D1, I1)` 120ms.
Tier · efficient: wash only.
Why · the check is the cause; the row wash is the consequence — selection is a sentence, not a flash.

**S02 — Select-all** · click the header checkbox
Felt · every row's box draws in sequence (20ms stagger, cap 150ms) and the bulk bar slides up.
Spec · stagger per §3.9; bar per S06.
Tier · efficient: bars only.
Why · the cascade reads as "the whole table agreed" — a single gesture with a visible scope.

**S03 — Bulk bar rise** · first row selected
Felt · a floating bar slides up from the table's bottom edge, overlaying nothing.
Spec · `(slide, N, D2, I2)` 260ms slow.
Tier · efficient: fade.
Why · the bar *arrives* when there is work to do and leaves when there isn't — it never pushes content.

**S04 — Selection count** · selection count changes
Felt · the count numerals count-up (or -down) in the bulk bar.
Spec · AnimatedCount 400ms.
Tier · reduced: instant value.
Why · the count is alive without being loud — the number answers itself.

**S05 — Marquee** · drag across rows
Felt · a translucent selection rectangle tracks the cursor 1:1; rows wash as it passes.
Spec · drag is 1:1 (no easing); row washes trail at 60ms.
Tier · efficient: washes only.
Why · the rectangle is the cursor's shadow — selection follows the hand, not an animation.

**S06 — Range extend** · Shift-click a second row
Felt · the intermediate rows wash inward from both anchors, meeting in the middle.
Spec · 20ms per row inward, cap 150ms.
Tier · efficient: instant.
Why · the range *fills in* — the eye sees the interval being claimed.

**S07 — Keyboard extend** · Shift+arrows from a cursor
Felt · the selection edge advances with the cursor's fading trail.
Spec · cursor trail per P-family table cursor rules (120ms per move).
Tier · minimal: none.
Why · the trail is the keyboard's mouse — it must track like one.

**S08 — Bulk action fire** · click a bulk bar action
Felt · the bar compresses, the action runs, rows exit (E1 exit choreography).
Spec · bar 180ms; rows per E1 (fade-out-down, precise tier).
Tier · efficient: instant.
Why · the bar's collapse is the commitment — then the table tells the result.

**S09 — Deselect** · click a selected row
Felt · the wash decays and the check un-draws.
Spec · wash decay 180ms; check reverse 84ms (0.7× of 120).
Tier · efficient: instant.
Why · deselection is a release — it should feel lighter than selection.

**S10 — Chip multi-select** · toggle `C3` chips
Felt · chips pop in/out and the rail FLIPs; the filter count in the trigger updates.
Spec · chip per K13/K14; count 120ms.
Tier · per K13/K14.
Why · the chips are the state; the count is the summary — two beats, one meaning.

**S11 — Cell select (grid)** · click a table cell
Felt · the cell gains a 2px accent inset ring; the cursor lands.
Spec · 75ms instant.
Tier · minimal: none.
Why · the inset ring is the cursor's seat — precise, square, quiet.

**S12 — Text select** · drag-select text in a cell
Felt · native selection highlight; nothing animates.
Spec · n/a.
Tier · n/a.
Why · text selection is the browser's job — the Gloss stays out of the way.

**S13 — Kanban card select** · click `E17` card
Felt · the card's hairline becomes accent and lifts 1px.
Spec · 120ms.
Tier · none.
Why · the card is a thing to move — selection should feel physical, not flat.

**S14 — List multi-select** · cmd/ctrl-click list rows
Felt · rows accumulate washes; the bar count climbs.
Spec · per S01 + S04.
Tier · per S01.
Why · accumulation is a rhythm — each row joins the set with its own beat.

**S15 — Image multi-select** · toggle gallery thumbnails
Felt · each thumb gains an accent corner check and a 2px border.
Spec · check `(draw, Z, D1, I1)` 300ms; border 75ms.
Tier · efficient: border.
Why · visual selection needs the check *on* the object — the corner is where the eye goes.

**S16 — Collapse to context** · select in a narrow pane
Felt · the selection summary compresses into a compact chip in the header.
Spec · `(fade, Z, D1, I1)` 180ms.
Tier · none.
Why · the selection survives the pane's shrinking — context follows the user.

---

### L — Loading & saving (20)

**L01 — Button loading** · submit a slow action
Felt · the button's icon crossfades to a spinner; the label dims to 90% (width never swaps).
Spec · swap `(fade, Z, D1, I1)` 75ms; spinner rotates (licensed loop).
Tier · minimal: static glyph.
Why · the button becomes the status — no layout jump, no spinner appearing elsewhere.

**L02 — Skeleton shimmer** · table/card content loads
Felt · a light sweep travels the skeleton's shapes every 1.4s.
Spec · shimmer `(slide, E, D1, I1)` linear 1.4s loop.
Tier · efficient: static wash; minimal: none.
Why · shimmer reads as "material arriving" — a still skeleton reads as "broken".

**L03 — Skeleton → content** · data arrives
Felt · the skeleton crossfades to the real content in place; nothing shifts.
Spec · `(fade, Z, D2, I2)` 180ms.
Tier · efficient: 60ms.
Why · the swap is a *reveal*, not a reload — the layout was already true.

**L04 — Page first paint** · route's initial data loads
Felt · the page's frames appear in reading order (header → primary → secondary) with a 40ms stagger.
Spec · 40ms stagger, `(fade, Z, D1, I1)` 180ms each, cap 200ms.
Tier · efficient: single fade.
Why · the page composes itself in the order the user will read it — orientation beats speed.

**L05 — Pagination load** · fetch page 3
Felt · the table body crossfades at 50% and the new page settles in.
Spec · crossfade 180ms; rows per E1.
Tier · efficient: 60ms.
Why · the table never blanks — the page change is a re-settle, not a disappearance.

**L06 — Lazy sentinel** · scroll into an infinite list's end
Felt · a 40px sentinel spinner fades in at the list's foot.
Spec · `(fade, Z, D1, I1)` 75ms; spinner loop.
Tier · minimal: static.
Why · the list *admits* it is fetching at the exact edge — honest, local, quiet.

**L07 — Image blur-up** · a thumbnail's data loads
Felt · a 20px blurred placeholder sharpens to full over 400ms.
Spec · filter `(fade, Z, D1, I1)` 400ms, once.
Tier · efficient: immediate.
Why · the image *arrives* rather than snapping — but fast, because a school's photos are not art galleries.

**L08 — Save indicator** · a record saves
Felt · the save control ticks "Saving…" → "Saved" with a check that draws, then fades to mute.
Spec · check `(draw, Z, D1, I1)` 300ms; fade 180ms after 1.6s.
Tier · efficient: text swap.
Why · the check is the receipt (K08's sibling) — persistence made visible.

**L09 — Autosave debounce** · stop typing in an autosaved field
Felt · 800ms of silence → a quiet "Saved" pulse at the field's corner.
Spec · `(fade, Z, D1, I1)` 120ms.
Tier · none.
Why · autosave should be *felt* as a heartbeat, not announced like a trumpet.

**L10 — Sync pulse** · a push updates live data
Felt · the sync dot breathes once (1→0.7→1) and the changed rows wash.
Spec · breath 2s loop (licensed); wash 120ms decay 300ms.
Tier · efficient: wash; minimal: none.
Why · the dot is the pulse; the wash is the where — together they say "live, and here".

**L11 — Import progress** · a CSV import runs
Felt · the progress bar fills with the row count counting up; the file chip stays.
Spec · bar `(draw, W, D1, I2)` 300ms per update chunk; count AnimatedCount.
Tier · efficient: bar only.
Why · import is a *journey* — the bar and count let the user measure it.

**L12 — Export progress** · a report exports
Felt · the export button's label ticks through "Preparing → Bundling → Done"; the check draws at the end.
Spec · label swaps 75ms; check `(draw, Z, D1, I1)` 300ms.
Tier · efficient: label only.
Why · export is invisible work — the label sequence makes it a story.

**L13 — Download complete** · a file lands
Felt · the toast confirms with a check; the browser's own download chime is the audio twin.
Spec · per N01/N06.
Tier · per N.
Why · the toast is the app's acknowledgment that the browser already gave — consistency.

**L14 — Retry** · a failed load retries
Felt · the retry button presses, the error frame crossfades to the skeleton, then to content.
Spec · press per K02; skeleton swap per L03.
Tier · per L03.
Why · retry is a *second attempt*, visibly — the user sees the machine try again.

**L15 — Stale pulse** · data ages past its freshness window
Felt · the sync dot turns warning and pulses once; the readout gains a subtle amber wash.
Spec · one pulse (never a loop).
Tier · minimal: none.
Why · staleness is announced once, then lives in the dot — honest without nagging.

**L16 — Offline banner** · the connection drops
Felt · a banner slides down from the top, overlaying nothing, with a soft red wash.
Spec · `(slide, S, D2, I2)` 260ms slow.
Tier · efficient: fade.
Why · the banner is the app's honesty — it arrives the way bad news should: clear and low.

**L17 — Reconnect** · the connection returns
Felt · the banner's text swaps to "Reconnected" with a success tint, holds 1.2s, slides away.
Spec · swap 75ms; exit `(slide, N, D2, I2)` reverse 0.7×.
Tier · efficient: fade.
Why · recovery is announced and dismissed — the app returns to work, quietly.

**L18 — KPI count-up** · a stat card's data arrives
Felt · the numeral counts from its previous value to the new one.
Spec · AnimatedCount 500ms slowest, ease-out.
Tier · reduced: final value.
Why · the number *arrives* at its magnitude — counting is comprehension.

**L19 — Chart draw-in** · a chart's data arrives
Felt · the series draws from the axis to its shape over 300ms.
Spec · `(draw, E/W, D1, I2)` 300ms, one series after another (60ms gap).
Tier · efficient: fade-in only.
Why · the chart *builds* its argument in reading order — the eye follows the hand.

**L20 — Empty result** · a query returns nothing
Felt · the empty state fades in with its CTA sliding up 4px.
Spec · `(fade, Z, D2, I2)` 180ms; CTA `(slide, S, D1, I1)` 120ms.
Tier · efficient: 60ms.
Why · nothing found is still an answer — delivered with the same dignity as data.

---

### D — Drag & drop (14)

**D01 — Drag engage** · a draggable is pressed and moved 6px
Felt · the object's shadow lifts and a 60% ghost separates from the cursor.
Spec · lift `(scale, Z, D1, I1)` 120ms after the 6px threshold.
Tier · minimal: instant ghost.
Why · the 6px threshold means clicks never drag; the lift means dragging is visible.

**D02 — Drag travel** · the ghost moves
Felt · the ghost tracks the cursor 1:1 with zero lag.
Spec · 1:1, no easing (dragging rule, §5.5 of Motion).
Tier · n/a.
Why · lag in a drag is the fastest way to feel cheap — the ghost is the cursor.

**D03 — Drop target glow** · the payload enters a valid drop zone
Felt · the zone's border solidifies accent and a soft glow rises.
Spec · `(fade, Z, D1, I2)` 180ms.
Tier · efficient: border.
Why · validity is *offered* before the drop — the zone says "here" before the release.

**D04 — Kanban lane reflow** · the card crosses a lane boundary
Felt · the destination lane's cards FLIP apart to make room; the card hovers over the gap.
Spec · FLIP 260ms slow.
Tier · efficient: instant reflow.
Why · the lane *makes room* before the drop — anticipation, the Arc principle.

**D05 — Drop commit** · the card releases over a valid lane
Felt · the card springs home (scale 1.02 → 1, overshoot ≤ 6%) and the lane settles.
Spec · spring 300ms (≤44px? no — cards are large, so: settle 260ms, no spring — §3.4 forbids springs on large objects).
Tier · efficient: snap.
Why · the drop lands with a *settle*, not a bounce — cards are data, not toys.

**D06 — Drop cancel** · the payload releases outside any target
Felt · the ghost fades and the object returns to its origin with a short FLIP.
Spec · `(fade, Z, D1, I1)` 120ms; return FLIP 260ms.
Tier · efficient: snap.
Why · a canceled drag returns *politely* — no retracing, no lingering ghost.

**D07 — Table row reorder** · a row drags past another (if reorder is enabled)
Felt · the row below yields its slot with a FLIP; the dragged row glides into the gap.
Spec · FLIP 260ms.
Tier · efficient: snap.
Why · rows part like water around the dragged row — the list *sews* itself.

**D08 — File drop zone** · files hover over `B12` zone
Felt · the zone washes accent and the dashed border solidifies (H24's deep state).
Spec · per H24.
Tier · per H24.
Why · the zone's invitation deepens with proximity — two stages, one message.

**D09 — File drop commit** · files release onto the zone
Felt · the files become chips that slide in from the drop point, E-ward.
Spec · `(slide, E, D2, I2)` 180ms each, 20ms stagger, cap 150ms.
Tier · efficient: fade.
Why · the files *arrive* from where they were dropped — spatial continuity.

**D10 — SplitPane drag** · drag `G3 SplitPane` handle
Felt · the divider tracks 1:1; on release it snaps to the nearest token grid.
Spec · 1:1 during drag; snap `(slide, E/W, D1, I1)` 120ms.
Tier · n/a.
Why · live tracking, then a tidy grid landing — the pane lands where the design would put it.

**D11 — Slider thumb** · drag `B6`-style slider
Felt · the thumb tracks 1:1 and the track fills with it; the value readout follows.
Spec · 1:1; readout 75ms.
Tier · n/a.
Why · the thumb is the hand — the fill is its shadow.

**D12 — Multi-drag stack** · drag several selected items
Felt · the selected set lifts together as one ghost with a count badge.
Spec · lift 120ms; count pop 75ms.
Tier · minimal: ghost only.
Why · the count badge says "I am moving 4 things" — the stack is honest about its weight.

**D13 — Pin drag (sidebar)** · drag a `F6` item to pin
Felt · the pinned slot glows and the item snaps in with a 2px settle.
Spec · glow 180ms; snap 260ms.
Tier · efficient: snap.
Why · pinning is a commitment — the snap is the sound of the promise.

**D14 — Scrollbar thumb** · drag `G8 ScrollArea` thumb
Felt · the thumb tracks 1:1; content follows with native physics.
Spec · 1:1 (native scroll is never animated).
Tier · n/a.
Why · scroll is the body's motion — the Gloss never fights the browser's.

---

### X — Expand & collapse (16)

**X01 — Accordion open** · click `F3` header
Felt · the section's content descends (max-height FLIP) and the chevron rotates 90°.
Spec · FLIP 260ms slow; chevron 180ms.
Tier · efficient: fade.
Why · content *descends into place* — the space is made, not revealed.

**X02 — Row detail expand** · expand an `E1` row
Felt · the detail row slides open beneath; the parent row's chevron rotates.
Spec · `(slide, S, D1, I2)` 260ms; siblings FLIP.
Tier · efficient: fade.
Why · the detail is a *drawer under the row* — spatial, not modal.

**X03 — Tree expand** · click `E16` node chevron
Felt · children descend with a 4px fade-slide; indentation guides extend.
Spec · `(slide, S, D1, I2)` 260ms.
Tier · efficient: fade.
Why · hierarchy grows downward like a root — the tree *plants* its branches.

**X04 — Section collapse** · collapse `G6 Section`
Felt · the section folds to its header; the page FLIPs to reclaim the space.
Spec · 260ms FLIP.
Tier · efficient: instant.
Why · collapsed space is returned instantly to the user — a slow reclaim reads as hesitation.

**X05 — Sidebar collapse** · click `F6` rail toggle
Felt · the rail narrows with the labels cross-fading out and icons centering.
Spec · width `(slide, E/W, D1, I2)` 260ms slow, emphasized-decelerate in / accelerate out (spec §6.2).
Tier · efficient: snap.
Why · the sidebar *glides* to rail — the app's frame breathes, never snaps.

**X06 — Rail label crossfade** · the rail expands
Felt · labels fade in and slide 4px from the icon column, 20ms stagger.
Spec · `(slide, E, D1, I1)` 120ms each, 20ms stagger.
Tier · efficient: fade.
Why · the labels *re-emerge* into existence — the rail's memory returns.

**X07 — Popover open** · click `D4 Popover` trigger
Felt · the popover scales from the anchor corner with the backdrop-free page staying put.
Spec · `(scale, Z, D2, I2)` 260ms slow.
Tier · efficient: fade.
Why · the popover *grows from its anchor* — ownership by origin.

**X08 — Menu open** · click `D6` trigger (K11's twin for menus)
Felt · per K11.
Spec · per K11.
Tier · per K11.
Why · menus claim their trigger's corner — consistency across all menus.

**X09 — Dropdown options** · open `B3 Select`
Felt · the option list scales from the field; the field's chevron rotates.
Spec · per K11.
Tier · per K11.
Why · the list is the field's *extension* — it grows from where the answer goes.

**X10 — Calendar month slide** · navigate months in `B9`
Felt · the grid slides out E/W (next=E, prev=W) while the new month slides in on top.
Spec · `(slide, E/W, D2, I2)` 260ms.
Tier · efficient: crossfade.
Why · the calendar moves *with* the gesture — forward is East, always.

**X11 — Drawer open** · open `D3 Drawer`
Felt · the drawer slides from its edge while the page dims behind.
Spec · `(slide, E/W, D3, I2)` 260ms slow; backdrop fade 180ms (overlay leads).
Tier · efficient: fade both.
Why · the drawer *pushes in* from the edge — the page recedes, the panel arrives.

**X12 — Stepper advance** · move to the next `F5` step
Felt · the step's check draws and the panel slides E; the connector fills.
Spec · panel `(slide, E, D2, I2)` 260ms; connector `(draw, E, D1, I1)` 300ms.
Tier · efficient: crossfade.
Why · progress is *directional* — forward is East, and the connector agrees.

**X13 — Tabs panel** · switch `F1` tab (K05's twin)
Felt · per K05.
Spec · per K05.
Tier · per K05.
Why · tab switching is a crossfade, never a slide — content is context, not motion.

**X14 — Command palette expand** · open `D8`
Felt · the palette scales from the center of the screen while the page dims and blurs.
Spec · `(scale, Z, D4, I3)` 380ms slower; backdrop 180ms leads.
Tier · efficient: fade.
Why · the palette is a *surface above the app* — Z-direction, the Arc spatial stack.

**X15 — Hover card reveal** · hover a `D10 HoverCard` trigger
Felt · the card scales from the trigger after 300ms; the exit window is generous (100ms).
Spec · `(scale, Z, D2, I2)` 260ms.
Tier · efficient: fade.
Why · the card *offers* itself slowly but *survives* cursor travel — hover with forgiveness.

**X16 — Row group expand** · expand a grouped table row
Felt · the group's member rows FLIP down beneath it, chevron rotating.
Spec · FLIP 260ms.
Tier · efficient: fade.
Why · groups *open like drawers* — same grammar as X02, one component family.

---

### O — Overlays & dialogs (16)

**O01 — Modal enter** · open `D1 Modal`
Felt · the backdrop fades in, then the panel scales from 0.97 with a barely-damped landing.
Spec · backdrop `(fade, Z, D1, I2)` 180ms; panel `(scale, Z, D4, I3)` 380ms, starts 40ms after the backdrop (spec §6.1).
Tier · efficient: fades.
Why · the stage sets, then the subject arrives — the canonical modal rhythm.

**O02 — Modal exit** · close `D1`
Felt · the panel scales out (60% of its enter) and the backdrop fades behind it.
Spec · panel 260ms, backdrop 120ms; leader becomes follower.
Tier · efficient: fades.
Why · first in, last out — the modal leaves the way it came, faster.

**O03 — Confirm emphasis** · a `D2` dialog's danger button focuses
Felt · the danger ring draws around the destructive button while the safe button dims slightly.
Spec · ring `(draw, Z, D1, I1)` 300ms; dim 75ms.
Tier · minimal: none.
Why · the dialog *steers* the user to the safe path without trapping them.

**O04 — Drawer exit** · close `D3`
Felt · the panel slides back to its edge and the backdrop fades.
Spec · `(slide, E/W, D3, I2)` reverse 0.7× (180ms); backdrop 120ms.
Tier · efficient: fades.
Why · the drawer *retreats* to the edge it came from — spatial memory.

**O05 — Popover close** · dismiss `D4`
Felt · the popover scales back to its anchor corner.
Spec · reverse 0.7× (180ms).
Tier · efficient: fade.
Why · the popover returns to its origin — the anchor is the popover's home.

**O06 — Context menu at pointer** · right-click a row
Felt · the menu scales from the cursor's position.
Spec · `(scale, Z, D2, I2)` 260ms, origin at the pointer.
Tier · efficient: fade.
Why · the menu *answers the cursor* — the right-click's echo.

**O07 — Tooltip fade** · trigger `D5`
Felt · the tooltip fades in 4px above the target after 400ms.
Spec · `(fade, Z, D1, I1)` 120ms; no slide (never chases).
Tier · none.
Why · a tooltip that slides chases the cursor; one that fades waits for it.

**O08 — Sheet rise** · open `D11 Sheet`
Felt · the sheet rises from the bottom with the handle staying put; the backdrop dims.
Spec · `(slide, N, D3, I2)` 260ms; backdrop 180ms.
Tier · efficient: fades.
Why · the sheet *rises from the floor* — bottom sheets come from the bottom.

**O09 — Command palette exit** · dismiss `D8`
Felt · the palette scales down and the backdrop fades; focus returns to the trigger.
Spec · reverse 0.7× (266ms); backdrop 120ms.
Tier · efficient: fades.
Why · the palette departs faster than it arrived — attention has been paid.

**O10 — Global search enter** · open `D9`
Felt · per O01's rhythm with the entity tabs already visible.
Spec · per O01.
Tier · per O01.
Why · search is a place — it gets the modal's welcome.

**O11 — Lightbox open** · open `D12`
Felt · the artifact scales from its thumbnail's rect to full view.
Spec · `(scale, Z, D4, I3)` 380ms with the FLIP origin at the thumb.
Tier · efficient: fade.
Why · the artifact *grows from where it was* — spatial continuity, the Arc signature.

**O12 — Dialog stack** · a second dialog opens above the first
Felt · the first dialog dims 10% and stays; the second scales in above.
Spec · dim 120ms; second per O01.
Tier · efficient: fades.
Why · stacking is *depth* — each layer visibly lower than the last.

**O13 — Modal backdrop click** · click outside a `dismissable` modal
Felt · the backdrop pulses once (10% darker) before closing — a "yes, I heard that".
Spec · pulse 120ms; then O02.
Tier · minimal: instant close.
Why · the pulse acknowledges the click's target before honoring it — no dead clicks.

**O14 — Toast stack shift** · a second toast arrives
Felt · the stack FLIPs to make room; the newest toast lands at the corner.
Spec · FLIP 260ms; toast per N01.
Tier · efficient: fades.
Why · the stack *reflows* like a deck of cards — order is preserved, always.

**O15 — Inline preview popover** · hover a table cell's truncated value
Felt · a mini-panel fades in showing the full value.
Spec · `(fade, Z, D1, I1)` 120ms.
Tier · none.
Why · truncated data gets a *second reading* — the popover is the margin note.

**O16 — Wizard panel** · a multi-dialog flow advances
Felt · the outgoing panel slides W while the incoming slides E, crossfading.
Spec · `(slide, E/W, D2, I2)` 260ms, direction by flow.
Tier · efficient: crossfade.
Why · the flow moves *forward* even inside a dialog — progress is spatial.

---

### N — Notifications & feedback (16)

**N01 — Toast enter** · a toast fires
Felt · the toast slides in from the corner (SE) with a fade; siblings FLIP.
Spec · `(slide, SE, D3, I2)` 260ms slow, 20ms stagger per sibling (spec §6.9).
Tier · efficient: fade.
Why · corner toasts *arrive from the corner* — the SE vector is the inbox's direction.

**N02 — Toast exit** · a toast dismisses
Felt · the toast slides out toward the corner it came from, then unmounts on finish.
Spec · reverse 0.7× (180ms); unmount on the exit's onfinish — never a fixed timeout.
Tier · efficient: fade.
Why · the toast leaves *toward home* — departure mirrors arrival.

**N03 — Success pulse dot** · a success toast lands
Felt · after 320ms the toast's status dot pulses once (scale 1→1.05→1).
Spec · `(pulse, Z, D1, I1)` 300ms, once (spec §4.5: one Pulse per moment).
Tier · minimal: none.
Why · one pulse says "done" without looping — a heartbeat, not a siren.

**N04 — Bell dot** · a notification arrives
Felt · the bell's unread dot springs in (0→1.12→1) then settles; the count pops once.
Spec · spring 300ms (8px — legal); count `(scale, Z, D1, I1)` 120ms.
Tier · efficient: dot only.
Why · the dot *lands* — arrivals are events, and events have weight.

**N05 — Unread item** · a notification list updates
Felt · the new item slides in at the top with an accent hairline and a brief wash.
Spec · `(slide, N, D2, I2)` 260ms; wash 300ms decay.
Tier · efficient: wash.
Why · newness is *worn* then retired — the hairline stays, the wash leaves.

**N06 — Mark read** · a notification is opened
Felt · the accent hairline fades and the dot empties; the row dims a shade.
Spec · `(fade, Z, D1, I1)` 120ms.
Tier · minimal: instant.
Why · reading is a *transaction* — the receipt is the state change itself.

**N07 — Sync breath** · live data is current
Felt · the sync dot breathes slowly (1→0.7→1, 2s) — the only licensed ambient loop.
Spec · 2s linear loop.
Tier · efficient: static fill; minimal: none.
Why · the breath is the app's resting heartbeat — presence without demand.

**N08 — Alert slide** · a `C5 Alert` appears
Felt · the alert slides down from its container's top edge and settles.
Spec · `(slide, S, D2, I2)` 260ms.
Tier · efficient: fade.
Why · alerts *drop in* — they are interruptions that own their moment.

**N09 — Alert dismiss** · close a `C5`
Felt · the alert folds up and the content below FLIPs to reclaim the space.
Spec · reverse 0.7× (180ms); FLIP 260ms.
Tier · efficient: fades.
Why · dismissed alerts *return their space* instantly — the page heals itself.

**N10 — Inline error slide** · `C6 InlineError` appears
Felt · the message slides 4px up and the field ring turns (T03's twin).
Spec · per T03.
Tier · per T03.
Why · the error is *local* — it lives at the field that failed.

**N11 — Warning banner** · a deprecation/attention banner
Felt · the banner slides down with an amber wash; the action button is already there.
Spec · per N08 with amber tokens.
Tier · efficient: fade.
Why · warnings are calmer than errors — the motion matches the temperature.

**N12 — Auto-dismiss ring** · a toast nears its 4s limit
Felt · a thin progress ring ticks around the toast's corner over the final second.
Spec · `(draw, E, D1, I1)` 300ms arc over 1s, linear.
Tier · minimal: none.
Why · the ring *predicts* the dismissal — the toast leaves with notice, not surprise.

**N13 — Undo toast** · a destructive-undo action
Felt · the toast offers "Undo"; pressing it reverses the action with a soft wash on the restored rows.
Spec · per N01; undo wash 300ms decay.
Tier · per N01.
Why · undo is the safety net — its motion is calm because it was always there.

**N14 — Empty state** · a feed/list empties (C16)
Felt · the empty frame fades in with its CTA (L20's twin).
Spec · per L20.
Tier · per L20.
Why · emptiness is an answer, delivered politely.

**N15 — Retry success** · a failed retry succeeds
Felt · the error frame's retry button flashes success for a beat before content returns.
Spec · flash 120ms; content per L03.
Tier · efficient: content only.
Why · the machine's recovery is *celebrated once, briefly* — then work resumes.

**N16 — "Updated" pulse** · a record updates elsewhere (live view)
Felt · the changed row washes once, then stills.
Spec · wash 120ms in, 300ms decay.
Tier · efficient: none.
Why · remote changes are announced *at the row* — the where is the what.

---

### P — Page & navigation (18)

**P01 — Route enter** · navigate forward
Felt · the arriving page slides from E and fades, layered over the departing one.
Spec · `(slide, E, D4, I3)` 500ms slowest, enter ease (spec §6.3).
Tier · efficient: crossfade; minimal: none.
Why · forward travel is *East* — the page arrives from where the future is.

**P02 — Route exit** · the old page departs
Felt · the departing page slides W at 0.7× while the new one lands.
Spec · `(slide, W, D4, I3)` reverse 0.7× (350ms), exit ease.
Tier · efficient: crossfade.
Why · the old page leaves *West* — the past retreats in the direction it came.

**P03 — Back navigation** · the user presses Back
Felt · the arriving page slides from W (memory, not momentum).
Spec · `(slide, W, D4, I3)` 500ms, direction from navigation type.
Tier · efficient: crossfade.
Why · back is *West always* — direction is a contract, never a decoration.

**P04 — Rapid navigation coalesce** · two routes fire in 300ms
Felt · the first transition cancels cleanly; only the last destination lands.
Spec · cancel 75ms (no mid-air frames).
Tier · n/a.
Why · the app never *stutters* between destinations — coalescing is the premium tell.

**P05 — Active nav indicator** · the current route's sidebar item
Felt · a 3px accent bar draws at the item's left edge on activation.
Spec · `(draw, E, D1, I1)` 300ms.
Tier · minimal: static bar.
Why · the indicator *grows* with the page — the nav item claims its page.

**P06 — Sidebar cascade** · the app mounts
Felt · nav items cascade in from E, 20ms apart, reading top-down.
Spec · `(slide, E, D1, I1)` 120ms each, 20ms stagger, cap 150ms.
Tier · efficient: single fade.
Why · the navigation *introduces itself* in reading order — the frame orients.

**P07 — Breadcrumb slide** · the route changes
Felt · the crumb trail slides W (back) or E (forward) with the page.
Spec · per P01/P03 on the same clock.
Tier · efficient: none.
Why · the trail moves *with* the page — the path is the journey's echo.

**P08 — Pagination FLIP** · page change (K15's twin)
Felt · per K15.
Spec · per K15.
Tier · per K15.
Why · paging is a reflow with identity — the same row is never re-born.

**P09 — Filter FLIP** · the filter rail changes (The Ledger T33)
Felt · rows that remain FLIP to their new places; rows that leave fade out-down; rows that enter fade in.
Spec · FLIP 260ms; exit `(fade, Z, D1, I1)` 180ms.
Tier · efficient: crossfade; minimal: snap.
Why · filtering is *re-composition*, never a reload — identity survives the query.

**P10 — Sort FLIP** · a column sorts (K16's twin)
Felt · per K16.
Spec · per K16.
Tier · per K16.
Why · sorted rows *travel* to their rank — the order is the story.

**P11 — Density change** · the table switches comfortable ⇄ compact
Felt · every row's height animates together and the header re-settles.
Spec · height FLIP 260ms (many subjects, one clock — the density is the subject).
Tier · efficient: snap.
Why · density change is a *re-spacing* — rows breathe in or out as one.

**P12 — Scroll elevation** · the page scrolls under the header
Felt · the header gains a hairline and a soft shadow as content passes beneath.
Spec · `(fade, Z, D1, I1)` 180ms.
Tier · none.
Why · the header *acknowledges* depth the moment content slides under it.

**P13 — Scroll shadow (panels)** · content scrolls in a `G8 ScrollArea`
Felt · a shadow fades at the scroll edge when content is beneath.
Spec · `(fade, Z, D1, I1)` 180ms.
Tier · none.
Why · the edge shadow is the depth cue — the panel *knows* it holds more.

**P14 — Window focus highlight** · the app window gains focus (desktop)
Felt · the window's frame brightens a shade and the active surface warms.
Spec · `(fade, Z, D1, I1)` 180ms.
Tier · none.
Why · focus is *state* — the frame announces which surface the keyboard owns.

**P15 — Window blur dim** · the app loses focus
Felt · the frame dims 8% and all attention pulses pause.
Spec · `(fade, Z, D1, I1)` 180ms.
Tier · none.
Why · the app *excuses itself* when it isn't watched — loops pause with the user.

**P16 — Fullscreen enter** · the app enters fullscreen
Felt · the chrome (header/sidebar) folds away with a 260ms FLIP; content reflows.
Spec · FLIP 260ms.
Tier · efficient: snap.
Why · fullscreen is the app *making room* — the furniture moves aside.

**P17 — Workspace switch** · the campus changes
Felt · the page dims 10%, the shell's data crossfades, the page transition lands.
Spec · dim 120ms; crossfade 180ms; route per P01.
Tier · efficient: crossfade.
Why · switching worlds is a *page-level event* — loud enough to be deliberate, calm enough to be safe.

**P18 — Route error** · a route fails to load
Felt · the error frame replaces the page with the retry CTA (G10).
Spec · per G10 entry.
Tier · per G10.
Why · a failed route is answered *in place* — the shell never blanks.

---

### C — Search & command (16)

**C01 — Palette open** · ⌘K (X14's twin)
Felt · per X14.
Spec · per X14.
Tier · per X14.
Why · the palette is the app's *front door* — it gets the full Z-arrival.

**C02 — Query typing** · type in the palette
Felt · results re-rank live; the stagger collapses to zero while typing (crossfade at `fast`).
Spec · crossfade 120ms.
Tier · minimal: instant.
Why · results *yield* to the keystroke — the list never staggers against the fingers.

**C03 — Result stagger** · the palette opens
Felt · results fade in top-down at 20ms, reading order.
Spec · `(fade, Z, D1, I1)` 120ms each, 20ms stagger, cap 150ms.
Tier · efficient: single fade.
Why · the palette *composes itself* in the order the eye will scan.

**C04 — Selection accent slide** · arrows move through results
Felt · the accent wash slides between rows; the text does not move.
Spec · `(slide, N, D1, I1)` 120ms.
Tier · efficient: wash swap.
Why · the eye tracks the block, not the text — the palette's cursor is a block.

**C05 — Command run** · Enter on a command
Felt · the row flashes accent, the palette scales out, the destination lands.
Spec · flash 75ms; exit per O09; route per P01.
Tier · efficient: fades.
Why · the run is a *launch* — flash, fold, land.

**C06 — Scope switch** · Tab through command/action/page scopes
Felt · the scope chip's active state slides between the three labels.
Spec · `(slide, E/W, D1, I1)` 120ms.
Tier · efficient: crossfade.
Why · scopes are segments — the wash travels (K04's grammar).

**C07 — No results** · a query finds nothing
Felt · the empty line fades in with a "no matches" hint and the query echoed in quotes.
Spec · `(fade, Z, D1, I1)` 120ms.
Tier · none.
Why · the palette *repeats the query back* — "nothing" is specific, not generic.

**C08 — Search snippet highlight** · results in the global search
Felt · the matched substring gains a subtle highlight that draws in with the result.
Spec · highlight 120ms after the row lands.
Tier · none.
Why · the match is *pointed at* — the user sees why this row answered.

**C09 — History recents** · the palette opens with no query
Felt · recent commands appear with a clock icon, top-down stagger.
Spec · per C03.
Tier · per C03.
Why · recents *introduce themselves* — the palette remembers without being asked.

**C10 — Deep-link load** · a shared filter URL opens
Felt · the table's rows FLIP to the shared filter state on first paint.
Spec · FLIP 260ms after mount.
Tier · efficient: snap.
Why · arriving at a filtered view is a *re-arrival* — the table composes itself.

**C11 — Clear search** · the palette's × or Escape
Felt · the query clears, results snap back to recents, the field keeps focus.
Spec · recents per C09.
Tier · per C09.
Why · clearing *returns home* — the palette's default state is a place.

**C12 — Escape cascade** · Escape closes the palette
Felt · the palette scales out; a second Escape (already closed) does nothing.
Spec · per O09.
Tier · per O09.
Why · Escape *backs out once* — the cascade never double-fires.

**C13 — Search focus from anywhere** · `/` pressed
Felt · the header search's ring appears as focus travels to it; the page stays.
Spec · ring 75ms.
Tier · minimal: none.
Why · the `/` travel is *teleportation* — instant, no scrolling tour.

**C14 — Filter suggestion insert** · click a `T32`-style completion
Felt · the completion term lands in the box and the suggestion card folds.
Spec · card fold 180ms reverse.
Tier · efficient: fade.
Why · the suggestion *commits* by folding — the card closes on the chosen path.

**C15 — Kbd hint pulse** · the user pauses on the search field
Felt · the `/` tile warms for a beat to reaffirm the shortcut.
Spec · `(fade, Z, D1, I1)` 75ms, once per focus.
Tier · none.
Why · shortcuts are *taught in situ* — the hint appears where the hands already are.

**C16 — Search results count** · results change
Felt · the count readout updates (AnimatedCount) under the results.
Spec · 400ms.
Tier · reduced: instant.
Why · the count is the scope — the user always knows how much was found.

---

### G — Graphics & charts (16)

**G01 — Line trace** · a line chart draws
Felt · the line traces from the first point to the last over 300ms.
Spec · `(draw, E, D1, I2)` 300ms draw.
Tier · efficient: fade-in.
Why · the line *writes itself* — the eye follows the pen.

**G02 — Bar grow** · a bar chart draws
Felt · bars grow from the axis to their value, left-to-right.
Spec · `(draw, N, D1, I2)` 300ms, 60ms stagger.
Tier · efficient: fade.
Why · bars *rise from the baseline* — the axis is the floor, and the bars stand on it.

**G03 — Donut sweep** · a donut draws
Felt · the arc sweeps clockwise from 12 o'clock.
Spec · `(draw, E, D1, I2)` 300ms.
Tier · efficient: fade.
Why · the sweep *starts at 12* — the clock is the reader's reference.

**G04 — Heat cell fill** · a heatmap's data lands
Felt · cells fill to their intensity, 4ms stagger in reading order.
Spec · `(fade, Z, D1, I1)` 120ms each, 4ms stagger, cap 150ms.
Tier · efficient: static.
Why · the grid *completes itself* like pixels — density arrives as one image.

**G05 — Crosshair travel** · hover a chart (H14's twin)
Felt · per H14.
Spec · per H14.
Tier · per H14.
Why · the crosshair is the chart's *pointer* — it must track like one.

**G06 — Readout swap** · hover changes the value (Watchtower)
Felt · the header's big numeral crossfades to the hovered value with a tabular re-set.
Spec · `(fade, Z, D1, I1)` 120ms.
Tier · efficient: none.
Why · the readout *answers the cursor* — the number replaces itself, never jumps.

**G07 — Range brush** · drag `H4 RangeBrush`
Felt · the brush window tracks 1:1 and the chart re-bins live.
Spec · 1:1; re-bin crossfade 120ms.
Tier · n/a.
Why · the zoom is *direct manipulation* — the brush is the hand.

**G08 — Sparkline extend** · live data pushes a new point
Felt · the sparkline's last segment extends and the new point pops once.
Spec · segment 120ms; point `(scale, Z, D1, I1)` 75ms.
Tier · minimal: none.
Why · live data *arrives at the edge* — the sparkline is a heartbeat line.

**G09 — Live wash** · a metric updates
Felt · the changed bar/point washes once (accent → rest) while others stay still.
Spec · wash 120ms in, 300ms decay.
Tier · efficient: none.
Why · one subject per moment — only the *changed* thing moves.

**G10 — Compare toggle** · compare mode on
Felt · the second series fades in from the axis and the legend gains its entry.
Spec · `(fade, Z, D2, I2)` 260ms.
Tier · efficient: crossfade.
Why · comparison is *layering* — the new series joins, the old one stays.

**G11 — Series toggle** · legend item clicked
Felt · the series fades out and the remaining charts FLIP to refit.
Spec · fade 180ms; FLIP 260ms.
Tier · efficient: fades.
Why · hiding a series *re-composes* the chart — the axes refit honestly.

**G12 — Drill-down** · click a chart segment
Felt · the chart crossfades to the detail view with the clicked segment's slice expanding briefly.
Spec · slice 120ms; crossfade 260ms.
Tier · efficient: crossfade.
Why · the clicked thing *claims* the drill — the eye stays on the same subject.

**G13 — Axis tick fade** · axes adjust
Felt · ticks fade out and the new ones fade in; the grid lines never pop.
Spec · `(fade, Z, D1, I1)` 180ms.
Tier · minimal: instant.
Why · axes are furniture — they change quietly or not at all.

**G14 — Chart empty draw** · a chart with no data
Felt · the empty frame fades in with a "no data for this period" line.
Spec · per L20.
Tier · per L20.
Why · an empty chart is an *answer* — the frame says so, politely.

**G15 — Goal arc settle** · `H3 GoalArc` updates
Felt · the arc draws to its new value and the target marker springs in.
Spec · arc `(draw, E, D1, I2)` 300ms; marker spring (small — legal).
Tier · efficient: crossfade.
Why · progress to goal is a *toward* — the arc draws toward the target, never away.

**G16 — Fullscreen chart** · K20's twin
Felt · per K20.
Spec · per K20.
Tier · per K20.
Why · charts get the fullscreen Z-transition — data deserves the frame.

---

### W — Window & shell (14)

**W01 — Window drag** · drag the title bar (desktop)
Felt · the window tracks the cursor 1:1; content is frozen for the drag's duration.
Spec · 1:1; content freeze is a state, not an animation.
Tier · n/a.
Why · a dragged window must feel *attached* — lag is the cheapest feeling in desktop.

**W02 — Window snap preview** · drag toward a screen edge
Felt · a translucent half/quarter preview fills the target zone.
Spec · preview `(fade, Z, D1, I1)` 120ms.
Tier · none.
Why · the snap *previews its promise* — the window asks before it commits.

**W03 — Window snap** · release over a zone
Felt · the window lands in the zone with a 200ms settle.
Spec · `(scale, Z, D1, I1)` 200ms.
Tier · minimal: instant.
Why · the settle is the snap's *click* — arrangement made audible by motion.

**W04 — Window resize** · drag an edge
Felt · the window tracks 1:1; content reflows live.
Spec · 1:1, no easing.
Tier · n/a.
Why · resize is the body's motion — the window never animates itself.

**W05 — Window minimize** · minimize to dock
Felt · the window scales toward its dock icon and disappears.
Spec · `(scale, Z, D2, I2)` 200ms toward the dock origin.
Tier · minimal: instant.
Why · the window *travels home* — the dock is its origin.

**W06 — Window restore** · click the dock icon
Felt · the window scales back from the dock icon to its frame.
Spec · reverse of W05.
Tier · minimal: instant.
Why · restore *returns from home* — the same path, reversed.

**W07 — App launch** · the shell boots
Felt · the frame fades in with the sidebar cascading (P06) after the boot splash.
Spec · splash `(fade, Z, D2, I2)` 200ms; shell per P06.
Tier · minimal: instant.
Why · launch is an *arrival* — the app composes itself once, then goes to work.

**W08 — Theme switch** · toggle `I2 ThemeToggle`
Felt · the whole surface crossfades to the new palette over 260ms; the toggle's icon crossfades.
Spec · document wash `(fade, Z, D1, I2)` 260ms.
Tier · minimal: instant.
Why · the theme change is a *document-level event* — it washes, it doesn't pop.

**W09 — Install prompt** · `I4 InstallPWA` appears
Felt · the install chip scales in at the header's edge.
Spec · `(scale, Z, D1, I1)` 120ms.
Tier · none.
Why · the offer *arrives once* — install is an invitation, not a campaign.

**W10 — Workspace dim** · switch campuses (P17's twin)
Felt · per P17.
Spec · per P17.
Tier · per P17.
Why · tenant switches are loud by design — the dim is the "hold on".

**W11 — Keyboard shortcuts dialog** · `D13` opens
Felt · per O01; the kbd tiles cascade in at 20ms.
Spec · per O01 + C03 stagger.
Tier · per O01.
Why · the key map *introduces itself* — discovery is a composition.

**W12 — Focus ring on window** · the window gains keyboard focus
Felt · a 2px accent frame ring appears around the window's edge.
Spec · 75ms instant.
Tier · minimal: none.
Why · the window's keyboard ownership is *stated*, never guessed.

**W13 — Command palette overlay** · the palette dims the app
Felt · the app behind blurs subtly (8px) and dims; the palette sits above.
Spec · blur+dim `(fade, Z, D1, I2)` 180ms.
Tier · efficient: dim only.
Why · the app *recedes* so the palette can command — depth by subtraction.

**W14 — Splash boot** · the first paint
Felt · the logo mark scales in 0.9→1 with a 2px settle, then the shell arrives.
Spec · `(scale, Z, D2, I2)` 260ms, once.
Tier · minimal: instant.
Why · the boot is the *first handshake* — one beat, then work.

---

### Z — Context & system (12)

**Z01 — Right-click** · context menu (O06's trigger)
Felt · per O06.
Spec · per O06.
Tier · per O06.
Why · the cursor's menu must be the cursor's — same origin, same speed.

**Z02 — Copy feedback** · ⌘C on a selection
Felt · the selection flashes a brief 20% accent wash, then returns.
Spec · flash 75ms, decay 200ms.
Tier · minimal: none.
Why · the copy is *acknowledged at the source* — the selection knows it was taken.

**Z03 — Paste commit** · ⌘V into a grid
Felt · the pasted cells wash in sequence, row-major.
Spec · 40ms per row, cap 200ms.
Tier · efficient: none.
Why · pasted data *claims its cells* — the grid shows what arrived.

**Z04 — Undo** · ⌘Z after an action
Felt · the reverted rows wash and the action's toast dismisses.
Spec · wash 300ms decay; toast per N02.
Tier · efficient: none.
Why · undo *wears its memory* — the restored state acknowledges its return.

**Z05 — Keyboard hint pulse** · hover a control with a shortcut
Felt · the shortcut tile warms beside the control's label.
Spec · `(fade, Z, D1, I1)` 75ms.
Tier · none.
Why · shortcuts are *taught at the control* — the hint is the label's shadow.

**Z06 — Haptic analog** · a toggle or check commits
Felt · the press gives a 4px micro-settle on the element (the visual haptic).
Spec · 75ms instant.
Tier · minimal: none.
Why · the settle is the *tap you feel* — desktop's haptic is visual.

**Z07 — Overscroll glow** · scroll past a list's end
Felt · the edge glows a soft accent for 200ms, then releases.
Spec · `(fade, Z, D1, I1)` 200ms, once per overscroll.
Tier · minimal: none.
Why · the edge *answers the pull* — the list knows it has ended.

**Z08 — Scroll momentum** · flick a list
Felt · native momentum physics — never customized.
Spec · n/a.
Tier · n/a.
Why · momentum is the body's physics; the Gloss never overrides the browser's.

**Z09 — First-run tour** · a new surface's first visit
Felt · three sequential hints point at key controls with a soft spotlight.
Spec · each `(fade, Z, D1, I1)` 180ms, 600ms apart.
Tier · minimal: static hints.
Why · the tour *teaches once* — after dismissal it never returns.

**Z10 — Reduced-motion crossfade** · the tier changes to minimal
Felt · every live loop freezes and every transform snaps; the app crossfades once.
Spec · one document wash 260ms.
Tier · this IS the minimal tier.
Why · switching to reduced motion is itself a moment — acknowledged once, then still.

**Z11 — Focus migration** · focus moves between app regions (Tab)
Felt · the ring travels instantly; the page never scrolls out of the user's hands.
Spec · 75ms.
Tier · minimal: none.
Why · focus travel is *teleportation* — the ring arrives before the eye.

**Z12 — Everything ends** · the last micro-interaction
Felt · when an action completes, the UI returns to stillness.
Spec · the final frame holds; no lingering tails, no afterglow.
Tier · n/a.
Why · the Gloss's best quality is *knowing when to stop* — stillness is the product.

---

## 5. The quality budget

Perceived quality is a budget, not a list. SDMAS spends it under these
caps:

| Moment | Budget |
|---|---|
| Hover/press/focus feedback | ≤ 75ms to *begin*, ≤ 180ms total |
| Overlay enter | 380ms surface after 180ms backdrop |
| Page transition | 500ms one-way, 350ms back |
| Stagger | 20ms quantum, 150ms absolute cap |
| Loops | 4 licensed, all frozen in efficient, static in minimal |
| Springs | ≤ 44px objects, gesture-driven, ≤ 6% overshoot, ≤ 300ms |
| The user's wait | never increased by the Gloss — animation runs *with* the data, never before it |

---

## 6. Governance

A micro-interaction ships when:

1. **It has a one-sentence reason** (§1 rule 4) — no reason, no entry.
2. **It obeys the house rules** (§3) — verified by review against this doc.
3. **It degrades through the tiers** — the efficient and minimal behaviors
   named in its entry are implemented and tested.
4. **It never delays the user** — the animation is not in the critical path
   of the data it frames.
5. **It is implemented with the motion module** — move specs, `useMove`,
   `useFlipList`, and tokens only. No hand-written keyframes in components.
6. **Its end state is reachable without it** — the last frame is the truth
   under every tier and every browser.

**The delete list.** Any interaction that animates the user's *reading*
text, loops without license, springs a panel, or answers a click with
anything slower than the exit scale is cut on sight.

---

## 7. Implementation map

The Gloss is applied in the same PR order as the Foundry, because the
micro-interactions live *in* the components:

1. **Hover + press + focus** (H01–H03, K01–K03, F01–F04) — lands with the
   Button/Input/Checkbox extraction (Foundry step 4).
2. **Table choreography** (H06–H08, K07, K15–K16, P09–P11) — lands with the
   Ledger's header/selection steps; the FLIP engine already exists.
3. **Overlays** (O01–O05, X07–X11) — the modal/drawer/popover entries are
   mostly shipped; the remaining gaps are the exit-path tests.
4. **Notifications** (N01–N06) — shipped with the toast/bell; the additions
   are N12's auto-dismiss ring and N16's live wash.
5. **Search & command** (C01–C16) — lands with the palette's existing
   choreography; additions are C08 and C10.
6. **Charts** (G01–G16) — lands with the Watchtower chart wrappers.
7. **Window & shell** (W01–W14) — desktop-framing work, per the App
   Redesign.
8. **Every entry gets a test** — a micro-interaction is tested by its tier
   behavior: precise asserts the move, efficient asserts the fade, minimal
   asserts the snap.

---

## 8. Acceptance criteria

The Gloss is complete when:

1. **Every interactive element answers within 75ms.**
2. **No animation in the app lacks a line in this document** — the catalog
   is exhaustive, not illustrative.
3. **Reduced-motion users see zero movement** and the same information.
4. **No loop runs outside the licensed four.**
5. **A blindfolded reviewer** can predict the tier behavior of any entry
   from its spec line alone.
6. **The app still feels fast** — total animation budget never adds more
   than ~400ms of latency to any task the user is trying to finish.
