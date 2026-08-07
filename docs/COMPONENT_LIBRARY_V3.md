# SDMAS Component Library v3 — "The Foundry"

> The fifth normative expansion of the Corridor system (after Design System v3,
> Motion System v3, the App Redesign, and the Table System v3). Codename:
> **The Foundry** — components are *cast*, not hand-carved: every one is poured
> from the same tokens, finished to the same standard, and stamped with the
> same contract.
>
> **Scope:** the complete specification for the SDMAS reusable component
> library — 109 components across nine families. For every component:
> purpose, states, variants, animation, spacing, colors, interaction, keyboard
> behavior, and accessibility. Architecture and specification only.
>
> **Companion docs:** `DESIGN_SYSTEM_V3.md` (tokens, §12 component rules),
> `MOTION_SYSTEM_V3.md` (move specs, tiers, the interaction state machine),
> `TABLE_SYSTEM_V3.md` (The Ledger), `ANALYTICS_SYSTEM_V3.md` (The Watchtower).

---

## 0. How this system was derived

The Foundry is an **audit-first specification**. Before any component was
invented, the existing library was inventoried and graded:

- `components/ui/` — 34 files (button, input, select, badge, card, alert,
  loading, empty/error state, modal, toast, drawer, tooltip, dropdown-menu,
  tab-group, pagination, breadcrumbs, skeleton family, animated-count, form,
  search-input, status-badge, command-palette, global-search-modal,
  confirm-dialog, page-header, keyboard-shortcuts-dialog, install-pwa,
  theme-toggle, system-theme-toast, workspace-switcher, link-child-dialog,
  route-transition, and the `table/` module: frame + columns + legacy +
  filter-rail + filter-model + saved-views).
- `components/layout/` — app-layout, sidebar, header, quick-create,
  contextual-actions, organization-switcher.
- `components/notifications/` — notification-bell.
- `components/timeline/`, `components/admin/` (role-multi-select),
  `components/analytics/` (kpi-card, five chart components, analytics-filter-bar).
- `lib/motion/` — tokens, use-move, use-motion-tier, flip (useFlipList).

**Two consequences of the audit:**
1. **Nothing in this doc is greenfield.** Every component entry marks the
   existing file as `exists · conforming`, `exists · needs migration`, or
   `new`. The governance gate (§6) is what promotes a file.
2. **No library dependency is introduced.** The foundry stays hand-rolled,
   keyboard-driven, tier-gated — matching the constraint the Table and Motion
   systems already operate under.

---

## 1. Philosophy

A component library is not a collection of widgets. It is a **manufacturing
contract**. The Foundry has four commitments:

1. **Every component earns its place.** A component exists because a page
   proved it needs it — nothing is speculative. The audit table (§5) shows
   the provenance: components are *observed*, not proposed.
2. **Every component speaks one language.** It reads tokens (`--color-*`,
   `space.*`, `radius.*`, motion tokens), never raw values. A reviewer can
   diff any two components and find the same grammar.
3. **Every component ships with its whole contract.** Nine fields (§2), no
   exceptions. An undocumented interaction state is a defect, not a detail.
4. **Every component is a service, not a decoration.** It must be operable by
   keyboard alone, readable by a screen reader, and honest under reduced
   motion — the same three obligations the Motion System sets for animation.

---

## 2. The component contract

Every Foundry component is documented with **nine fields**, in this order.
A component that cannot fill a field truthfully is either over-specified
(remove the field) or unfinished (build the field).

1. **Purpose** — the job it does, and the job it must NOT be used for.
2. **States** — the full state machine: resting, hover, focus, active,
   disabled, loading, empty, error, selected, expanded/collapsed, dragging —
   whichever apply. States are exhaustive, not illustrative.
3. **Variants** — the closed set of visual/intent variations (never
   free-form styling).
4. **Animation** — a **move spec** `(verb, direction, distance, importance)`
   from the Motion System, plus where it sits on the tier gate. No
   component may author raw animation.
5. **Spacing** — the token-level padding/margin/gap grid it renders within.
6. **Colors** — the token names it may touch, and the contrast rule that
   binds them.
7. **Interaction** — pointer + touch behavior, hover/press/drag semantics.
8. **Keyboard behavior** — full key map, tab order, focus management.
9. **Accessibility** — the WAI-ARIA pattern it follows (APG), roles, names,
   and the WCAG 2.2 AA obligations.

Governance: a component passes review only when all nine fields are true of
the code, not of the doc (§6).

---

## 3. The interaction spine — shared rules

These rules apply to every component; per-component entries only list the
delts.

### 3.1 Focus
- **Focus model:** the visible focus ring is the *only* indicator of focus.
  `focus-visible` governs it: pointer interaction never paints the ring,
  keyboard interaction always does. 2px accent ring, 2px offset (light) /
  accent glow (dark). Never border-color-only focus (§12.2 of the Design
  System).
- **Tab order:** DOM order is tab order. Components never reorder the
  DOM for visuals (`order-*`/`flex-reverse` are banned for interactive
  elements).
- **Focus trap:** modal-class components (dialog, drawer, command palette,
  global search) trap focus while open and restore it to the trigger on
  close. Focus moves into the panel on open, never left on the page behind.

### 3.2 Keyboard — the shared map
| Key | Behavior |
|---|---|
| `Tab` / `Shift+Tab` | Move focus (trap inside modal-class) |
| `Enter` | Activate (buttons, list items, form submit) |
| `Space` | Activate (buttons, checkboxes, toggles) / scroll on non-interactive |
| `Escape` | Close overlay / cancel editing / clear selection — never navigate |
| `Arrow keys` | Move within lists, tabs, sliders, calendar grids, trees |
| `Home` / `End` | First / last in a list, scrollable container, or calendar row |
| `Type-ahead` | Jump to matching item in lists and menus |
| `/` | Focus the app search (global) |

`Escape` is reserved: it only ever *backs out* — closes, cancels, unselects.
It never destroys state that can be recovered with `Ctrl+Z` or a re-open.

### 3.3 Pointer
- **Hover** never reveals functionality that keyboard users cannot reach.
  Anything hover-only must also be focus-revealed (the table's row actions,
  the tooltip trigger, the context menu's row menu — all follow this rule).
- **Press** = `mousedown`→`mouseup` on the same element; `scale 0.97` press
  feedback is the default (§12.1). Drag begins only after a 6px threshold,
  so clicks never accidentally drag.
- **Touch:** targets ≥ 44px on touch; hover-only reveals become always-visible.

### 3.4 Motion tiers
Every component's animation is gated by the tier (`useMotionTier`):
- **precise** — full choreography (move spec applies).
- **efficient** — opacity-only ≤ 75ms; spatial moves become fades or snaps.
- **minimal** — instant; no movement, no pulsing, no looping.

### 3.5 Accessibility floor
- WCAG 2.2 AA. Contrast ≥ 4.5:1 for text, ≥ 3:1 for UI graphics.
- Every interactive element has an accessible name (visible label or
  `aria-label`).
- Status is never color-only: `danger` text carries an icon or the pill
  carries the label itself.
- Live regions (`aria-live`) for toasts, notifications, and inline
  validation — polite, never assertive, except for errors on submit.
- Components follow the WAI-ARIA Authoring Practices Guide pattern named in
  their entry.

---

## 4. The catalog — 109 components, nine families

Family prefixes: **A** Actions · **B** Inputs · **C** Feedback ·
**D** Overlays · **E** Data · **F** Navigation · **G** Layout ·
**H** Analytics (The Watchtower) · **I** Shell & domain.

Notation: `[exists]` = present in the codebase today; `[migrate]` = exists,
needs the v3 contract applied; `[new]` = to be built. Move specs use the
Motion grammar `(verb, dir, distance, importance)`; tiers gate all of them.

---

### Family A — Actions

#### A1 Button `[migrate]`
- **Purpose:** the primary trigger for a single action. One primary per view.
  Never used for navigation-with-args (that is a Link or a card).
- **States:** resting · hover · focus-visible · pressed (scale 0.97) ·
  disabled (45%, label contrast ≥ 3:1) · loading (spinner replaces the icon;
  label dims to 90%, width never swaps).
- **Variants:** `primary` · `secondary` · `ghost` · `outline` · `danger` ·
  `success`. Sizes `sm` 32 / `md` 36 / `lg` 44; icon-only 36×36.
- **Animation:** `(fade, Z, D1, I2)` on content change (loading ⇄ idle);
  press `scale 0.97` at `fast`. Tier-gated: efficient keeps the fade,
  minimal drops it.
- **Spacing:** `px: space.md` (12) / gap 8; height per size; icon 16.
- **Colors:** variant token pairs from §12.1; text always `on-accent` on
  filled variants; disabled `ink.300` on `surface`.
- **Interaction:** click/Enter/Space; loading disables the pointer; type
  attribute honored (`submit` inside forms).
- **Keyboard:** native `button`; Enter/Space activate; focus ring per §3.1.
- **A11y:** native button semantics; `aria-busy` when loading; never a
  `div` styled as a button.

#### A2 IconButton `[migrate]`
- **Purpose:** a button whose content is an icon — row actions, close,
  overflow. Always carries an accessible name.
- **States:** as A1, plus the table's reveal-on-row-hover pattern (also
  focus-revealed).
- **Variants:** ghost (default) · outline · danger-ghost; sizes `sm` 28 /
  `md` 36.
- **Animation:** `(fade, Z, D1, I1)`; press 0.97. Tier-gated.
- **Spacing:** square, no padding; icon 16.
- **Colors:** `ink.600` rest → `ink.900` hover; danger variant →
  `status.danger.fg` on hover.
- **Interaction:** same as A1; never a tooltip-only name.
- **Keyboard:** native button.
- **A11y:** `aria-label` is mandatory (name-checked in review); tooltip, if
  shown, is supplementary (`aria-describedby`), never the name.

#### A3 ButtonGroup `[new]`
- **Purpose:** related actions presented as one cluster; segmented where a
  single selection is meaningful.
- **States:** per-button states; group `joined` variant collapses hairlines
  into one outline (radius: outer corners only).
- **Variants:** `joined` · `spaced` (gap 8).
- **Animation:** press 0.97 per button; selection washes `fast`.
- **Spacing:** joined — no internal gaps; spaced — gap `space.sm`.
- **Colors:** hairline `border`; active member accent.
- **Interaction:** click members; radio-group semantics when `exclusive`.
- **Keyboard:** arrow keys move between members when exclusive (APG
  toolbar/radiogroup), else Tab.
- **A11y:** `role=group`; exclusive mode `role=radiogroup` with
  arrow-key + roving tabindex.

#### A4 SplitButton `[new]`
- **Purpose:** primary action with a trailing menu of alternatives.
- **States:** primary-button states + menu states (open: chevron rotates
  `fast`).
- **Variants:** primary/secondary stems.
- **Animation:** menu `(scale, Z, D2, I2)` enter / reverse exit; chevron
  rotate 180° at `fast`.
- **Spacing:** stem 36px + divider hairline + 28px menu trigger.
- **Colors:** stem per A1; divider `divider`.
- **Interaction:** left stem fires the primary; right opens the menu
  (arrow-down also opens).
- **Keyboard:** Tab into group; `Alt+Down` opens the menu; arrows navigate;
  Enter fires the highlighted item.
- **A11y:** `aria-haspopup=menu` + `aria-expanded` on the trigger; menu per
  APG Menu Button.

#### A5 Toggle (Switch) `[new]`
- **Purpose:** a binary on/off that *changes a mode or preference* — never a
  submit trigger. Checkboxes select; toggles switch.
- **States:** off · on · hover · focus-visible · disabled · loading (indeterminate travel).
- **Variants:** label-left / label-right; `sm` 32 / `md` 40 widths.
- **Animation:** knob travel 20px at `fast` with `ease.standard`; the knob
  may spring (`ease.spring`, small object) — legal per §3.4 of Motion.
- **Spacing:** knob 16/20 inside track padding 2.
- **Colors:** track `surface-hover` off / `accent.base` on; knob `ink.0`.
- **Interaction:** click toggles; click-on-label toggles; never drags.
- **Keyboard:** Space toggles; arrow keys toggle when focused.
- **A11y:** `role=switch` + `aria-checked`; visible label; contrast ≥ 3:1
  on the track boundary.

#### A6 Checkbox `[migrate]`
- **Purpose:** multi-select from a known set; tri-state for partial groups.
- **States:** unchecked · checked · indeterminate · hover · focus ·
  disabled · error (group validation).
- **Variants:** `sm` 16 / `md` 18; label positions; standalone vs group.
- **Animation:** check mark `(draw, Z, D1, I1)` — the path strokes in;
  indeterminate dash fades `fast`.
- **Spacing:** 16px box; gap 8 to label.
- **Colors:** box hairline `border` → `accent.base` when checked; check mark
  `on-accent`.
- **Interaction:** click toggles; label click toggles; group header
  "check all" reflects tri-state.
- **Keyboard:** Space toggles; Tab navigates; group = fieldset with arrows
  (APG checkbox group).
- **A11y:** native `input[type=checkbox]` (never a styled div); the group
  uses a `fieldset`/`legend`; `aria-describedby` for errors.

#### A7 Radio / RadioGroup `[new]`
- **Purpose:** exactly-one selection from a small exclusive set.
- **States:** as A6 without indeterminate; `selected` is the only checked
  member.
- **Variants:** `sm`/`md`; horizontal/vertical layouts.
- **Animation:** dot `(scale, Z, D1, I1)` — the inner dot scales in.
- **Spacing:** 16/18px circle; gap 8 to label; group gap 12.
- **Colors:** circle hairline → `accent.base` ring when selected; dot
  `accent.base`.
- **Interaction:** click selects (deselects siblings); label click selects.
- **Keyboard:** arrows move selection (roving tabindex), Space/Enter select
  (APG radio group).
- **A11y:** native inputs in a `fieldset`/`legend`; `aria-checked` on the
  group role=radiogroup when custom-rendered.

#### A8 SegmentedControl `[migrate → TabGroup]`
- **Purpose:** one-of-N view/period switcher (Day/Week/Month, List/Grid).
- **States:** per-segment rest/hover/focus/selected/disabled.
- **Variants:** pill segments on `ink.100` track (§ pill tabs); underline
  segments for page-level switches.
- **Animation:** the selected segment's **wash slides** between options at
  `fast` (FLIP on the single wash element — one subject per moment).
- **Spacing:** segment padding `px 14 / py 6`; track padding 4.
- **Colors:** track `bg`; selected wash `ink.0` + hairline + `elevation.hover`;
  selected text `ink.900`.
- **Interaction:** click selects; the wash follows, it never fades and
  re-fades.
- **Keyboard:** arrows move selection; Enter/Space confirm (APG tabs or
  radiogroup — declared per instance).
- **A11y:** either `role=tablist` (with panels) or `radiogroup`; the moving
  wash is decorative — selection is also conveyed by text weight + color.

#### A9 Link / TextButton `[migrate]`
- **Purpose:** inline navigation (Link) or emphasis-less action (TextButton).
- **States:** rest · hover (underline) · focus-visible · visited ·
  disabled (TextButton only; Links never disable).
- **Variants:** `default` · `muted` · `accent` · `danger`.
- **Animation:** underline `(draw, W, D1, I1)` — a 2px accent hairline draws
  in on hover/focus at `fast`.
- **Spacing:** no padding (inline) / `px 10 py 6` when standalone.
- **Colors:** `ink.700` rest; accent variant `accent.base`.
- **Interaction:** click navigates/fires; `Ctrl/Cmd+click` opens new tab
  (Link).
- **Keyboard:** native anchor or button; Enter activates.
- **A11y:** real `<a>` for navigation with `href`; `aria-current` on active
  nav links; TextButton is a real button.

#### A10 ActionMenu `[migrate → DropdownMenu]`
- **Purpose:** the 3-dot menu of secondary row/record actions.
- **States:** trigger rest/hover/focus; menu open/closed; item
  rest/hover/focus/disabled/danger.
- **Variants:** `sm` 28 / `md` 36 triggers; bottom-left/right placement.
- **Animation:** menu `(scale, Z, D2, I2)` from the trigger's corner; item
  icons fade in at 20ms stagger (≤6 items).
- **Spacing:** item `px 12 py 8`; menu `py 4`; divider gap 8.
- **Colors:** menu `surface` + hairline + `shadow.lg`; danger item
  `status.danger.fg`.
- **Interaction:** click opens; outside click closes; item click fires +
  closes.
- **Keyboard:** Enter/Space/`Down` opens; arrows navigate; Enter fires;
  Escape closes and returns focus to the trigger.
- **A11y:** APG Menu Button; `aria-haspopup=menu`, `aria-expanded`,
  `role=menu`/`menuitem`.

---

### Family B — Inputs

#### B1 Input `[migrate]`
- **Purpose:** single-line text entry. The *base* all field types extend.
- **States:** rest · hover (border strong) · focus (2px ring — never
  border-color-only) · filled · error (danger ring + message) · disabled
  (45%) · read-only.
- **Variants:** size `md` 36 / `sm` 32; prefix/suffix (currency, unit, icon
  inside a hairline boundary).
- **Animation:** focus ring `(fade, Z, D1, I2)` at `fast`; error shake
  (4px, 3 ticks) once on submit-fail only.
- **Spacing:** `px 12`, height per size; label→field gap 6; hint 4.
- **Colors:** field `surface`; hairline `border` → `border-hover`;
  ring `accent-ring`; error `danger-ring`.
- **Interaction:** click focuses; autofill never restyles; clear button on
  search-type only.
- **Keyboard:** native input; Enter submits the form; Escape clears
  focus-ring states, never the value.
- **A11y:** visible label (no placeholder-as-label); `aria-invalid` +
  `aria-describedby` on error; `autocomplete` honored.

#### B2 Textarea `[new]`
- **Purpose:** multi-line text entry with optional auto-grow.
- **States:** as B1; plus overflow-scroll when `resize=manual`.
- **Variants:** fixed-height (min 3 rows) · auto-grow (max 12 rows) ·
  code/mono.
- **Animation:** auto-grow height change at `fast` (FLIP, translate-free —
  height only; neighbors never shift by a jump).
- **Spacing:** `py 10`; `px 12`; line-height 1.5.
- **Colors:** as B1.
- **Interaction:** grip-resize only when `resize=manual`; auto-grow never
  resizes above its max.
- **Keyboard:** native; Tab exits (unless `tabInsert` for code).
- **A11y:** label + `aria-describedby` counter; character count is
  supplementary, never the only validation.

#### B3 Select `[migrate]`
- **Purpose:** single choice from a known list.
- **States:** rest/hover/focus/open/disabled/error + option states
  (selected, disabled, grouped).
- **Variants:** native (small lists, fast forms) · custom popover (search
  inside when > 8 options).
- **Animation:** popover `(scale, Z, D2, I2)`; the selected row gets a
  check that draws in `(draw, Z, D1, I1)`.
- **Spacing:** trigger 36px; popover `py 4`, item `px 12 py 8`.
- **Colors:** per B1; check `accent.base`.
- **Interaction:** click opens; type-ahead jumps; option click commits.
- **Keyboard:** Space/Enter/`Down` opens; arrows move; Enter commits;
  Escape closes without committing (native behavior preserved).
- **A11y:** APG Listbox; `role=combobox`+`listbox` for custom; `aria-activedescendant`; group labels `role=group`.

#### B4 Combobox / Autocomplete `[new]`
- **Purpose:** free text with suggestions (student search, guardian picker).
- **States:** typing · open · highlighting · committed · no-results ·
  error · disabled.
- **Variants:** inline filter (list narrows while typing) · static list
  (append-selection).
- **Animation:** suggestion list `(scale, Z, D2, I2)`; the active row's wash
  slides `fast`.
- **Spacing:** input per B1; list `py 4`, row `px 12 py 8`; grouped rows 8.
- **Colors:** row wash `surface-hover`; active row `accent-subtle` + text
  `accent.base`.
- **Interaction:** typing filters; click/Enter commits; blur commits the
  visible value (policy per field); Escape reverts to the last commit.
- **Keyboard:** `Down/Up` move the active row; Enter commits; Escape
  reverts; arrows never leave the input while the list is closed.
- **A11y:** APG Combobox — `role=combobox`, `aria-expanded`,
  `aria-activedescendant`, `aria-controls`; the listbox announces via a
  polite live region.

#### B5 MultiSelect `[migrate → role-multi-select]`
- **Purpose:** choose several from a list; chips inside the field.
- **States:** open/closed · per-chip states (remove-hover) · overflow
  (`+N`) · error · disabled.
- **Animation:** chip enter `(scale, Z, D1, I1)` at 20ms stagger; chip exit
  `(scale, Z, D1, I1)` reverse at 0.7×.
- **Spacing:** field grows by chip rows (gap 4, chip `px 8 py 2`).
- **Colors:** chips `ink.100` fill + hairline; remove hover
  `danger-light`.
- **Interaction:** click chip × removes; Backspace on empty input removes
  the last chip.
- **Keyboard:** per B4 plus Backspace-delete of chips; comma commits the
  current token.
- **A11y:** APG Listbox with `aria-multiselectable=true`; each chip is a
  removable button with a name.

#### B6 NumberInput `[new]`
- **Purpose:** numeric entry with steppers and formatting (amounts, ages,
  counts).
- **States:** as B1 plus step-hover.
- **Variants:** plain · currency (₦ prefix, tabular) · percentage ·
  `readOnly` display.
- **Animation:** step buttons press 0.97; value pop on commit (scale 1→1.03
  →1, `fast`, precise tier only).
- **Spacing:** steppers 24×36 split by a hairline; `px 12`.
- **Colors:** per B1; tabular numerals always.
- **Interaction:** click steps, wheel steps when focused, arrow-up/down
  steps; clamps honor min/max; invalid input is never silently accepted.
- **Keyboard:** Up/Down step; Home/End min/max; Tab exits.
- **A11y:** `inputmode=numeric`; `aria-valuemin/max/now` when
  custom-rendered; error via `aria-invalid`.

#### B7 SearchInput `[exists]`
- **Purpose:** text search with clear affordance and optional kbd hint.
- **States:** rest · focus · filled · clearing.
- **Variants:** with kbd hint (`/`) · without; widths per rail context.
- **Animation:** clear button `(fade, Z, D1, I1)` appears on input; the
  foundry's search box widens 320→480 on focus at `fast`.
- **Spacing:** `pl 9` (icon) / `pr 8`; height 36.
- **Colors:** per B1; icon `text-muted`.
- **Interaction:** clear button empties + refocuses; Escape clears.
- **Keyboard:** `/` focuses (global); Escape clears, second Escape blurs.
- **A11y:** `type=search`; `aria-label` contextual (never bare "Search").

#### B8 PasswordInput `[new]`
- **Purpose:** secret entry with reveal.
- **States:** as B1 plus revealed/obscured.
- **Variants:** with strength meter (post-focus) · without.
- **Animation:** reveal icon crossfades `fast`; strength bar fills
  `(draw, W, D1, I2)`.
- **Spacing:** per B1; reveal button 28×36 at the field's right.
- **Colors:** strength: danger → warning → success thresholds.
- **Interaction:** reveal toggles type; meter appears after first
  character.
- **Keyboard:** native; reveal is a button (Space/Enter).
- **A11y:** never force autocomplete off unless the security policy does;
  meter text (Weak/Fair/Strong) accompanies the color.

#### B9 DatePicker `[new]`
- **Purpose:** single-date entry with a calendar popover.
- **States:** field (B1) + calendar states: day rest/hover/focus/selected/
  today/outside-month/disabled/unavailable; popover open/closed.
- **Variants:** input-first (type `2026-02-03` or pick) · button-first ·
  compact (month grid only).
- **Animation:** popover `(scale, Z, D2, I2)`; month slide `(slide, W, D2,
  I2)` with direction from nav (next=E, prev=W); the selected day pops
  `(scale, Z, D1, I1)`.
- **Spacing:** grid 7×5/6, cell 36px; month header `py 8`; popover `p 12`.
- **Colors:** today = accent ring (never fill); selected = `accent.base`
  fill; outside-month 45%; unavailable = strikethrough + 45%.
- **Interaction:** click day selects + closes (or commits on done-button
  per policy); typed dates parse leniently and normalize.
- **Keyboard:** APG Date Picker Dialog: `Up/Down` ±1 week, `Left/Right` ±1
  day, `PgUp/PgDn` ±1 month, `Home/End` week ends, Enter commits, Escape
  closes; `aria-activedescendant` on the grid.
- **A11y:** `role=dialog` with `aria-label` + `aria-modal` when popover;
  grid `role=grid`, days `role=gridcell` with full dates in names
  ("Tuesday, February 3, 2026"); `aria-disabled` for unavailable days.

#### B10 TimePicker `[new]`
- **Purpose:** time-of-day entry.
- **States:** field + wheel/list states.
- **Variants:** 12h (AM/PM) · 24h.
- **Animation:** wheel `(slide, N, D1, I2)` for the colon flip; popover per
  B9.
- **Spacing:** segments 44px; separator 8.
- **Colors:** per B1; active segment accent.
- **Interaction:** click segment, type digits, arrows nudge.
- **Keyboard:** arrows ±1 (Shift=±5), digits replace, Enter commits.
- **A11y:** a real `<input type=time>` fallback when JS-free;
  `aria-label="Time"` on the composed control.

#### B11 DateRangePicker `[new]`
- **Purpose:** from/to span selection.
- **States:** as B9 plus range: start/end/range-fill/hover-preview.
- **Variants:** two-month side-by-side · single-month condensed.
- **Animation:** as B9; the range fill draws `(draw, W, D1, I2)` between the
  anchors.
- **Spacing:** two grids with 24 gap; popover `p 12`.
- **Colors:** range fill `accent-subtle`; endpoints `accent.base`.
- **Interaction:** first click anchors start, second commits end; clicking
  before start re-anchors.
- **Keyboard:** as B9 plus Shift+arrows extends the range.
- **A11y:** the range is announced as "from [date] to [date]"; cells carry
  `aria-selected` only on endpoints.

#### B12 FileUpload `[new]`
- **Purpose:** file selection with drag-and-drop and preview.
- **States:** idle · dragover (wash) · uploading (progress) · complete
  (file chip) · error (type/size).
- **Variants:** drop-zone · button-triggered · multi-file.
- **Animation:** drop-zone wash `(fade, Z, D1, I2)`; the file chip slides in
  `(slide, E, D2, I2)`; progress bar `(draw, W, D1, I2)`.
- **Spacing:** zone `py 24 px 16`; chip gap 8.
- **Colors:** dragover `accent-subtle` + dashed accent border; error
  `danger`.
- **Interaction:** drag threshold 6px then zone highlights; drop commits;
  click opens the picker; chips remove.
- **Keyboard:** the zone is a focusable button (Enter/Space opens); the
  picker is a native input `type=file` for screen readers.
- **A11y:** native file input with `aria-describedby` for constraints;
  progress has `role=progressbar` + `aria-valuenow`.

#### B13 OTPInput `[new]`
- **Purpose:** short verification codes (6 digits).
- **States:** empty · filled · focus (next empty cell) · error · resend
  timer.
- **Variants:** boxed cells · underline cells; lengths 4/6.
- **Animation:** cell focus wash `fast`; cell fill pops `(scale, Z, D1, I1)`;
  the caret travels to the next empty cell.
- **Spacing:** cells 44×48, gap 8.
- **Colors:** per B1; error ring on all cells.
- **Interaction:** typing advances, Backspace rewinds and clears; paste
  fills left-to-right.
- **Keyboard:** digits + arrows; Enter submits; the composite is ONE
  input in the tab order.
- **A11y:** single `inputmode=numeric` with `aria-label="Verification code"`
  and auto-advancing focus — never six unlabelled boxes.

#### B14 ColorPicker `[new]` *(low priority — only if a domain need appears)*
- **Purpose:** brand/status color choice (settings screens).
- **States:** swatch rest/hover/focus/selected + popover states.
- **Variants:** preset swatches · eyedropper-free.
- **Animation:** popover `(scale, Z, D2, I2)`.
- **Spacing:** swatches 24px, gap 8.
- **Colors:** preset palette only — no free hex (keeps the brand bounded).
- **Interaction:** click selects; popover for fine value.
- **Keyboard:** arrows move swatch focus; Space selects.
- **A11y:** swatches carry names ("Brand Blue"); a text fallback shows the
  hex for contrast checks.

---

### Family C — Feedback

#### C1 Badge `[exists]`
- **Purpose:** short status/classification label (count, tier, type).
- **States:** single — rest only; optional dot.
- **Variants:** `success` · `warning` · `danger` · `info` · `neutral` ·
  `primary`; sizes `sm`/`md`.
- **Animation:** badge-pop `(scale, Z, D1, I1)` on mount when a count
  changes (precise tier only — this is the one legal count pop).
- **Spacing:** `px 8/6`, gap 6; pill radius.
- **Colors:** `status.*.light` fill + `status.*.dark` text — never raw
  colored text alone.
- **Interaction:** none; badges are never buttons.
- **Keyboard:** none; skip in tab order.
- **A11y:** text content is the name; if the badge is decorative next to a
  labeled element, `aria-hidden` + a labeled twin.

#### C2 StatusBadge `[exists]`
- **Purpose:** a domain status rendered as a pill (Paid/Due/Overdue,
  Present/Absent).
- **States:** rest only; optional pulsing dot for *live* states.
- **Variants:** mapped via `statusVariants` (the table's variant map).
- **Animation:** dot pulse only for live/attention states — one Pulse per
  moment (§4.5).
- **Spacing:** as C1.
- **Colors:** the status semantic map; severity order drives sort elsewhere.
- **Interaction:** none; a status with an action is a different component
  (status + ActionMenu).
- **Keyboard:** none.
- **A11y:** the label IS the state (no color-only); `aria-label` includes
  the status word.

#### C3 Chip `[exists → table/chip]
- **Purpose:** a removable filter/suggestion token with an explicit ×.
- **States:** rest · hover · focus-visible (× focused) · removed (exit).
- **Variants:** filter chip · suggestion chip (no ×) · tag-with-icon.
- **Animation:** enter `(scale, Z, D1, I1)` at 20ms stagger; exit reverse at
  0.7×; the removal frees space with FLIP, never a jump.
- **Spacing:** `px 10 py 4`; × hit area 20×20 inset by 4.
- **Colors:** `ink.100` fill + hairline; × hover `danger-light`.
- **Interaction:** × removes; the chip body may toggle (selected wash).
- **Keyboard:** × is a real button; Tab reaches it; Backspace removes when
  the row is focused.
- **A11y:** × has `aria-label="Remove <value>"`; the chip set is announced
  as a list.

#### C4 Tag `[new]`
- **Purpose:** a non-interactive classification label (unlike Chip, no ×).
- **States:** rest only.
- **Variants:** neutral · accent · per-domain.
- **Animation:** none (mount fade via container stagger only).
- **Spacing:** `px 8 py 2`, gap 6.
- **Colors:** as C1.
- **Interaction:** none.
- **Keyboard:** none.
- **A11y:** plain text; list semantics when a set.

#### C5 Alert `[exists]`
- **Purpose:** page-level, non-blocking status message with a possible
  action.
- **States:** info · success · warning · danger; dismissible or persistent.
- **Variants:** `inline` · `banner` (top of view).
- **Animation:** enter `(slide, S, D2, I2)`; dismiss exit reverse at 0.7×.
- **Spacing:** `px 16 py 12`, icon 20, action right.
- **Colors:** `status.*.light` wash + `status.*.dark` icon + text
  `ink.800`.
- **Interaction:** optional action button; optional ×.
- **Keyboard:** action is a button; the alert itself is not focusable
  unless it carries a live region.
- **A11y:** `role=status` (polite) for info/success; `role=alert` for
  warning/danger; icon + text (no color-only).

#### C6 InlineError `[new]`
- **Purpose:** field-level validation message.
- **States:** error · warning (soft).
- **Variants:** under-field · in-panel summary.
- **Animation:** slide-in `(slide, N, D1, I1)` at `fast`; the field ring
  appears with it (one moment, two subjects are allowed — the ring and the
  message are one unit).
- **Spacing:** `mt 6`, `px 4`.
- **Colors:** `status.danger.fg`; icon 14.
- **Interaction:** none.
- **Keyboard:** none.
- **A11y:** `aria-live=polite`; wired via `aria-describedby` to the field.

#### C7 Toast `[exists]`
- **Purpose:** transient action feedback in the corner stack.
- **States:** entering · resting · leaving; per-toast types.
- **Variants:** success · error · info; with action / without.
- **Animation:** enter `(slide, SE, D3, I2)` with 20ms stagger; exit is the
  reverse at 0.7× via `useMove.play` (unmount on finish, not on a fixed
  timeout); one success `pulse()` on the dot after 320ms.
- **Spacing:** stack gap 8; toast `px 16 py 12`, width 360 max.
- **Colors:** `surface` + hairline; type icon colored per C5.
- **Interaction:** action button; ×; auto-dismiss 4s (pause on hover).
- **Keyboard:** toasts are focusable when they have an action (Tab reaches
  them); Escape dismisses the focused toast.
- **A11y:** `role=status` for info/success, `role=alert` for errors; the
  stack is a polite live region.

#### C8 NotificationItem / Center `[new]`
- **Purpose:** the read/unread notification feed (bell popover and page).
- **States:** unread (accent hairline + dot) · read · hover · expanded
  (detail) · loading · empty.
- **Variants:** compact (popover) · full (page).
- **Animation:** unread dot pops once on arrival; list FLIPs on read-state
  changes (one subject per moment); the center slides in from E `(slide, E,
  D3, I2)`.
- **Spacing:** item `px 14 py 12`, gap 8; avatar 32.
- **Colors:** unread `accent-subtle` wash; dot `accent.base`.
- **Interaction:** click opens detail (or marks read); "mark all read".
- **Keyboard:** list = arrow-key navigation (APG listbox or tablist);
  Enter opens; Shift+M marks read.
- **A11y:** `aria-live=polite` count; each item a real button/row with the
  notification text as its name.

#### C9 NotificationBell `[exists]`
- **Purpose:** the unread-count affordance that opens C8.
- **States:** idle · unread (dot + count) · open · loading.
- **Variants:** header bell · sidebar counter.
- **Animation:** the dot springs in `(scale, spring)` then one `pulse()`,
  gated to precise tier; count changes pop once, never loop.
- **Spacing:** 36×36 hit area; dot 8 at the corner; count pill 16.
- **Colors:** bell `ink.600`; count `danger` fill (unread is attention).
- **Interaction:** click toggles the center; Shift+click opens the full page.
- **Keyboard:** Enter/Space opens; Escape closes; `aria-expanded`.
- **A11y:** `aria-label="Notifications, N unread"`; the dot is decorative.

#### C10 Spinner / Loading `[exists]`
- **Purpose:** indeterminate progress for operations of unknown length.
- **States:** spinning · paused (minimal tier).
- **Variants:** `sm` 16 / `md` 24 / `lg` 40; light/dark-on-accent.
- **Animation:** one rotation loop — the only permitted loop; minimal tier
  freezes it (a static glyph, not a hidden one).
- **Spacing:** optional label gap 8; centering by the consumer.
- **Colors:** stroke `accent.base`, track `accent-subtle`.
- **Interaction:** none; the triggering control stays disabled.
- **Keyboard:** none.
- **A11y:** `aria-hidden` when a text label already says "Loading…"; else
  `role=progressbar` with no value.

#### C11 Skeleton family `[exists]`
- **Purpose:** layout-faithful loading placeholder — the table's skeleton
  *is* the table (§13.1).
- **States:** shimmering (precise) · static (efficient/minimal).
- **Variants:** `TableSkeleton` · `CardSkeleton` · `KPISkeleton` · `Text`
  (line blocks).
- **Animation:** shimmer sweep 1.4s loop (precise only); efficient shows a
  static wash — never a blurry pulse.
- **Spacing:** mirrors the real component's grid exactly (same paddings).
- **Colors:** `surface-hover` base + `ink.100` sweep.
- **Interaction:** none; skeletons are `aria-hidden`.
- **Keyboard:** none.
- **A11y:** container `aria-busy=true` + `aria-label="Loading…"`; the
  skeleton itself is inert.

#### C12 ProgressBar `[new]`
- **Purpose:** determinate progress toward a known target.
- **States:** idle · active · complete · error (failed step).
- **Variants:** `sm` 4px / `md` 6px; label right (tabular %).
- **Animation:** fill `(draw, W, D1, I2)` — width eases, never steps; the
  % label count-ups (reuse AnimatedCount).
- **Spacing:** track full-width; label gap 8.
- **Colors:** track `surface-hover`; fill `accent.base`; error `danger`.
- **Interaction:** none.
- **Keyboard:** none.
- **A11y:** `role=progressbar` + `aria-valuenow/min/max`; label visible.

#### C13 ProgressRing `[new]`
- **Purpose:** circular completion (course completion, goal arcs).
- **States:** idle · active · complete.
- **Variants:** `sm` 40 / `md` 64 / `lg` 96; with center label.
- **Animation:** arc `(draw, E, D1, I2)` sweeps clockwise; center number
  count-ups.
- **Spacing:** ring stroke 6; label centered.
- **Colors:** track `surface-hover`; arc `accent.base`; complete `success`.
- **Interaction:** none.
- **Keyboard:** none.
- **A11y:** `role=progressbar` with the numeric value; text label beside
  the ring.

#### C14 AnimatedCount `[exists]`
- **Purpose:** count-up/count-down numeral for live readouts.
- **States:** static · animating.
- **Variants:** prefix/suffix; decimals; formatter.
- **Animation:** ease-out cubic 1.2s (400ms in tables); reduced-motion
  renders the final value instantly.
- **Spacing:** none intrinsic; tabular numerals always.
- **Colors:** inherited.
- **Interaction:** none.
- **Keyboard:** none.
- **A11y:** `aria-label` carries the exact value; the animation is
  decorative.

#### C15 PulseDot `[new]`
- **Purpose:** a live/sync indicator — the **only** loop in a UI.
- **States:** idle (breathing) · solid (connected) · off (disconnected).
- **Variants:** 8px dot · with label ("Synced 14:02").
- **Animation:** one breathing pulse loop (opacity 1→0.7→1, 2s), precise
  tier only; efficient = static fill.
- **Spacing:** 8px + optional 6px label gap.
- **Colors:** `status.success` when healthy; `status.warning` when stale.
- **Interaction:** click may open a status popover.
- **Keyboard:** button when interactive.
- **A11y:** the label, not the color, conveys state ("Live", "Offline").

#### C16 EmptyState `[exists]`
- **Purpose:** the honest nothing-here frame with an escape hatch.
- **States:** empty · filtered-empty (Clear filters) · no-permission.
- **Variants:** icon · illustration-free; with/without primary action.
- **Animation:** `(fade, Z, D2, I2)` on mount + the CTA slides up 4px at
  `fast`.
- **Spacing:** `py 48`; icon tile 48; action gap 16.
- **Colors:** icon `text-tertiary` in a `bg` tile.
- **Interaction:** the CTA is a Button.
- **Keyboard:** the CTA is first in tab order within the frame.
- **A11y:** a heading + description; never only an icon.

---

### Family D — Overlays

#### D1 Modal `[exists]`
- **Purpose:** a blocking dialog for a complete, committed task.
- **States:** closed · opening · open · closing.
- **Variants:** centered · top-sheet (form focus) · sizes `sm 420 / md 560
  / lg 720 / xl 960`.
- **Animation:** backdrop `(fade, Z, D1, I2)`; panel `(scale, Z, D4, I3)`
  380ms enter, reverse at 0.7× exit — the canonical modal spec (§6.1).
- **Spacing:** panel `p 24`; header 16; body gap 16; footer `pt 16`, gap 8.
- **Colors:** backdrop `surface-overlay`; panel `surface` + hairline +
  `shadow.xl`.
- **Interaction:** backdrop click closes only if `dismissable`; scroll
  locked behind.
- **Keyboard:** focus trap; Escape closes; focus returns to the trigger;
  initial focus on the first focusable (or the destructive-confirm default).
- **A11y:** `role=dialog` + `aria-modal=true` + labelled by its heading;
  focus trap per APG Modal Dialog.

#### D2 ConfirmDialog `[exists]`
- **Purpose:** the one gate before destructive/irreversible actions.
- **States:** as D1; danger vs neutral intents.
- **Variants:** danger · neutral · with "don't ask again".
- **Animation:** as D1; the danger button's ring draws in `fast`.
- **Spacing:** as D1; icon tile 40 (`danger-light` wash).
- **Colors:** intent tokens; the confirm button is always `danger` for
  destructive intents.
- **Interaction:** the destructive action is never the default-enter
  target; the safe action is.
- **Keyboard:** Enter = safe default; Escape = cancel; explicit
  destructive key = `Ctrl+Enter` (documented per instance).
- **A11y:** `aria-describedby` the impact sentence; the destructive button
  has a clear name ("Delete 3 records" — never bare "Delete").

#### D3 Drawer `[exists]`
- **Purpose:** a side panel for detail/edit without leaving the context.
- **States:** closed · entering · open · leaving.
- **Variants:** right (default) · left; widths `md 400 / lg 560 / xl 720`;
  full-height.
- **Animation:** `(slide, E, D3, I2)` for right / `(slide, W, …)` for left
  at `slow`, driven by `useMove` + phase frames; exit reverse at 0.7×;
  backdrop fades.
- **Spacing:** `p 20`; header sticky; footer pinned with hairline.
- **Colors:** per D1 panel.
- **Interaction:** backdrop click closes when `dismissable`; scroll of the
  page locks.
- **Keyboard:** focus trap; Escape; focus restore on close.
- **A11y:** `role=dialog` + `aria-modal`; labelled by title; `aria-describedby`
  body when the title is not enough.

#### D4 Popover `[new]`
- **Purpose:** small, transient, non-modal context content (filter panel,
  quick settings).
- **States:** closed · open; placement variants.
- **Variants:** placements (top/bottom/left/right + align); `click` ·
  `hover` · `focus` triggers.
- **Animation:** `(scale, Z, D2, I2)` from the anchor corner; exit reverse
  at 0.7×.
- **Spacing:** `p 8`; arrow 8.
- **Colors:** `surface` + hairline + `shadow.lg`.
- **Interaction:** outside click / Escape close; never traps focus (it is
  non-modal).
- **Keyboard:** focus moves into the popover on open when it has
  focusable content; Tab closes it and moves on.
- **A11y:** `role=dialog` (when interactive content) or `tooltip`-adjacent
  semantics; the anchor gets `aria-haspopup` + `aria-expanded`.

#### D5 Tooltip `[exists]`
- **Purpose:** the supplementary explanation — never the only name.
- **States:** hidden · shown (hover/focus) · shown-while-pinned.
- **Variants:** `dark` (default) · `light`; placements; with shortcut hint.
- **Animation:** `(fade, Z, D1, I1)` 120ms; no slide (a tooltip must not
  chase the cursor).
- **Spacing:** `px 8 py 4`, max-width 240.
- **Colors:** `ink.900` surface, `ink.0` text.
- **Interaction:** hover shows after 400ms, hides after 100ms; never shows
  on tap (touch users get the focus-visible reveal).
- **Keyboard:** focus-visible shows it; Tab-away hides it.
- **A11y:** `role=tooltip` via `aria-describedby` — the trigger keeps its
  own accessible name.

#### D6 DropdownMenu `[exists]`
- **Purpose:** a menu of related commands from a trigger.
- **States:** trigger + menu states per A10.
- **Variants:** placement 4 corners; with header/divider; checkable items.
- **Animation:** `(scale, Z, D2, I2)` from the trigger corner; check draw.
- **Spacing:** item `px 12 py 8`; divider gap 8; menu `py 4`.
- **Colors:** per A10; `danger` items `danger.fg`.
- **Interaction:** click trigger; outside click closes; item fires+closes.
- **Keyboard:** APG Menu Button — arrows, type-ahead, Enter, Escape returns
  focus to trigger.
- **A11y:** `role=menu`/`menuitem`; `aria-haspopup`/`expanded`.

#### D7 ContextMenu `[new]`
- **Purpose:** row/selection commands on right-click (tables, kanban).
- **States:** as D6.
- **Variants:** anchored to pointer · anchored to element.
- **Animation:** `(scale, Z, D2, I2)` at the pointer.
- **Spacing:** as D6.
- **Colors:** as D6.
- **Interaction:** right-click opens; left-click elsewhere closes; the same
  commands exist in an overflow ActionMenu (keyboard parity).
- **Keyboard:** `Shift+F10` / Menu key opens at the focused element —
  right-click is never the only path.
- **A11y:** `role=menu`; the owning element gets `aria-haspopup=menu`.

#### D8 CommandPalette `[exists]`
- **Purpose:** ⌘K — search and run any command or jump anywhere.
- **States:** closed · opening · open · filtering · empty · executing.
- **Variants:** full (with category groups) · compact.
- **Animation:** backdrop fade + panel `(scale, Z, D4, I3)` 380ms; results
  stagger in at 20ms (reading order); the sliding selection accent
  translates between rows `fast`; exit reverse at 0.7× (spec §6.10).
- **Spacing:** panel 560×420 max; rows `px 12 py 10`; group headers 8.
- **Colors:** `surface` + hairline + `shadow.xl`; accent wash slides.
- **Interaction:** typing filters (stagger collapses while typing);
  Enter runs; arrows move; click runs.
- **Keyboard:** ⌘K opens; Esc closes; `Down/Up` navigate; Enter runs;
  Tab cycles scopes (commands/actions/pages); `>` prefixes commands.
- **A11y:** `role=dialog` + `aria-modal`; listbox of results with
  `aria-activedescendant`; focus trap.

#### D9 GlobalSearchModal `[exists]`
- **Purpose:** the app-wide entity search (students, fees, records).
- **States:** as D8 plus per-entity tabs and result groups.
- **Variants:** entity-tabbed.
- **Animation:** as D8; entity tab switch washes `fast`.
- **Spacing:** panel 640 wide; results rows 44.
- **Colors:** as D8; entity icons `ink.600`.
- **Interaction:** `/` or header affordance opens; entity tab filters.
- **Keyboard:** as D8; Tab between tabs and results.
- **A11y:** as D8; each result is a row with the entity name and type.

#### D10 HoverCard `[new]`
- **Purpose:** rich preview on hover (student card, section summary) — the
  tooltip's heavier sibling.
- **States:** hidden · shown; loading; error.
- **Variants:** top/bottom; interactive content (links inside).
- **Animation:** `(scale, Z, D2, I2)` + fade; no chase.
- **Spacing:** `p 16`; header + body gap 12.
- **Colors:** `surface` + hairline + `shadow.lg`.
- **Interaction:** 300ms hover delay, 100ms leave delay (generous exit
  window so the cursor may enter the card); clicking a link inside keeps it
  open.
- **Keyboard:** focus-visible opens it; it never traps focus.
- **A11y:** links inside are real links; the card content is reachable by
  keyboard via its trigger.

#### D11 Sheet `[new]` *(mobile/compact: bottom drawer)*
- **Purpose:** the drawer's bottom counterpart under 768px.
- **States:** closed · entering · open · leaving.
- **Variants:** half · full.
- **Animation:** `(slide, N, D3, I2)` rises; drag-handle pull-to-dismiss at
  120px threshold.
- **Spacing:** handle 40×4; `p 16`; rounded top 16.
- **Colors:** `surface`; handle `surface-hover`.
- **Interaction:** drag handle or backdrop; swipe down dismisses.
- **Keyboard:** as D3 (focus trap, Escape).
- **A11y:** as D3.

#### D12 Lightbox / Preview `[new]` *(only if a document viewer appears)*
- **Purpose:** full-bleed inspection of a single artifact.
- **States:** closed · open · zoomed.
- **Variants:** image · document.
- **Animation:** `(scale, Z, D4, I3)`; zoom springs.
- **Spacing:** full viewport; close 44 top-right.
- **Colors:** `surface-overlay` strong.
- **Interaction:** click outside / × closes; wheel zooms.
- **Keyboard:** Escape; arrows navigate a set; +/- zoom.
- **A11y:** `role=dialog`; `aria-label` describes the artifact.

#### D13 KeyboardShortcutsDialog `[exists]`
- **Purpose:** the discoverable key map for the current surface.
- **States:** open/closed.
- **Variants:** global · per-surface.
- **Animation:** as D1 modal.
- **Spacing:** rows `px 12 py 8`; kbd tiles 22×22.
- **Colors:** kbd `bg` + hairline.
- **Interaction:** opens from the help menu or `?` when available.
- **Keyboard:** Escape closes; arrows scroll; `?` toggles.
- **A11y:** a definition list of key+action pairs; focus moves to the list.

#### D14 LinkChildDialog `[exists]` *(domain)*
- **Purpose:** guardian↔child linking flow.
- **States:** as D1 + search states (B4 combobox inside).
- **Variants:** single · bulk.
- **Animation:** as D1; search results stagger.
- **Spacing:** as D1; result rows 44.
- **Colors:** per D1/B4.
- **Interaction:** search, select, confirm.
- **Keyboard:** as D1 + B4.
- **A11y:** as D1; the linked child names are announced on confirm.

---

### Family E — Data

#### E1 DataTable `[exists]` — see TABLE_SYSTEM_V3 (The Ledger)
- **Purpose:** the instrument (§2 of The Ledger) — every list, roster,
  ledger, register.
- **States:** loading (skeleton-is-the-table) · empty · filtered-empty ·
  populated · error (stale-but-honest) · density ×2.
- **Variants:** `class=registry|ledger|register`; `filterable`; controlled
  (server-side) / uncontrolled (local).
- **Animation:** mount stagger 20ms; FLIP on sort/filter/density; tier-gated
  exit choreography; count-up footer.
- **Spacing:** density 48/36; cell `px 20`.
- **Colors:** hairline dividers; zebra 40% wash; accent selection wash.
- **Interaction:** row click, checkbox selection, rail filtering, row
  actions reveal.
- **Keyboard:** full map in The Ledger §12.
- **A11y:** grid semantics, `aria-sort` headers, live count.

#### E2 FilterRail `[exists]`
- **Purpose:** the single entry point for finding rows (§6 The Ledger).
- **States:** idle · searching (debounce) · filtered · no-match.
- **Variants:** with saved views · without; facet-only.
- **Animation:** chips enter/exit at 20ms; FLIP row reflow; suggestion card
  `(scale, Z, D2, I2)`.
- **Spacing:** rail gap 8; chips gap 6.
- **Colors:** chips `ink.100`; active filter button accent.
- **Interaction:** search, facets, ranges, chips, view menu.
- **Keyboard:** `/` focuses search; Tab through chips (× buttons); Escape
  closes panels.
- **A11y:** the search input labelled with the table's hint; chips announce
  removal.

#### E3 Pagination `[exists]`
- **Purpose:** page-sized navigation for server-side lists.
- **States:** page buttons rest/hover/focus/active/disabled; loading.
- **Variants:** keyset (prev/next + running count) · numbered · page-size
  selector.
- **Animation:** page change FLIPs the table body (identity preserved);
  count updates via AnimatedCount.
- **Spacing:** controls gap 4; button 32×32.
- **Colors:** active page `accent.base`; disabled 45%.
- **Interaction:** click pages; page-size select (20/50/100).
- **Keyboard:** arrows move focus between buttons; Enter activates.
- **A11y:** nav landmark; `aria-current=page`; "Page 3 of 12" announced.

#### E4 Timeline `[exists]`
- **Purpose:** chronological events (attendance history, audit trail).
- **States:** event states (normal · error · highlighted); loading; empty.
- **Variants:** vertical (default) · horizontal (progress) · compact.
- **Animation:** events stagger in from S at 20ms; new events pulse once.
- **Spacing:** rail 2px; event gap 16; dot 8/10; content gap 12.
- **Colors:** rail `divider`; dot per event type; error `danger`.
- **Interaction:** optional click-to-expand event detail.
- **Keyboard:** events are rows; arrows navigate; Enter expands.
- **A11y:** `role=list`; time via `<time>` elements; expanded state
  announced.

#### E5 Calendar `[new]`
- **Purpose:** a month grid as a standalone view (not just picker popover).
- **States:** day states as B9; week selection; multi-month.
- **Variants:** single · range · with events (dots).
- **Animation:** month `(slide, W, D2, I2)` direction-aware; event dot pops.
- **Spacing:** cell 36; header 40.
- **Colors:** per B9; event dots `accent.base`.
- **Interaction:** click day; click week header for week view.
- **Keyboard:** APG grid (§B9 map).
- **A11y:** `role=grid`; full-date names; events are decorative to the day
  name (or announced when focusable).

#### E6 Avatar `[new]`
- **Purpose:** identity glyph — photo, initials, or status ring.
- **States:** rest only; optional presence dot (live states only).
- **Variants:** sizes 24/32/40/56/80; shape round/rounded; with status ring.
- **Animation:** presence dot per C15 rules (no idle loop except live).
- **Spacing:** ring 2px offset 2.
- **Colors:** initials `accent-subtle` bg + `accent.base` text; ring per
  status.
- **Interaction:** none unless clickable (then it's an IconButton).
- **Keyboard:** n/a.
- **A11y:** `alt`/`aria-label` = the person's name; initials are
  decorative when the name is adjacent.

#### E7 AvatarGroup `[new]`
- **Purpose:** overlapping identity stack ("3 teachers").
- **States:** rest; hover reveals next.
- **Variants:** overlap 24px; with `+N` overflow.
- **Animation:** hover reveals the next avatar with FLIP overlap at `fast`.
- **Spacing:** overlap -12px; ring on each avatar 2px `surface` (the
  seam).
- **Colors:** ring matches the page surface, not white.
- **Interaction:** hover/focus expands; `+N` opens the list (C8 pattern).
- **Keyboard:** the `+N` is a button; avatars are skip-links.
- **A11y:** the group is one `aria-label`ed cluster; individual names on
  the overflow list.

#### E8 StatCard / KPI `[exists → kpi-card]`
- **Purpose:** one number plus its delta, at a glance (the KPI grammar).
- **States:** rest · delta-up · delta-down · loading (KPI skeleton) ·
  empty.
- **Variants:** `kpi` (numeral+delta+sparkline) · `hub` (duotone icon) ·
  `split` (attention rail).
- **Animation:** the delta chip `(fade, Z, D1, I1)`; count-up on load;
  negative/positive deltas tint by *good-for-goal*, never by direction.
- **Spacing:** `p 20`; numeral 28/600 tabular; label 12; delta gap 8.
- **Colors:** delta `success`/`danger` per the goal map; the number is
  always `ink.900` — the delta carries the emotion.
- **Interaction:** clickable → navigates; else inert.
- **Keyboard:** button when clickable.
- **A11y:** the numeral is the label's value ("Attendance: 94%"); the delta
  includes the direction word, not just an arrow.

#### E9 Sparkline `[new]`
- **Purpose:** the mini trend inside KPI and table rows.
- **States:** static · live (pushed) · empty.
- **Animation:** draws once `(draw, E, D1, I2)`; live updates extend the
  path (FLIP the last segment), never redraw.
- **Spacing:** 80×28 typical; stroke 1.5.
- **Colors:** single accent; threshold line optional dashed.
- **Interaction:** none (tooltip lives in the full chart).
- **Keyboard:** n/a.
- **A11y:** `aria-hidden` when the numeral states the value.

#### E10–E15 Chart family `[migrate]` — the Watchtower grammar
The five chart primitives (Bar, Line, Donut, Scatter, Funnel) plus Heatmap
are specified in full in `ANALYTICS_SYSTEM_V3.md`. Summary contract:
- **Purpose:** one comparison per chart; ≤ 6 series; tabular numerals.
- **States:** loading · empty · data · live (pushed) · error (stale-honest).
- **Variants:** per chart type; compare mode; fullscreen.
- **Animation:** enter draws once `(draw, …)`; live updates are FLIP/wash,
  never re-render pops; hover crosshair at `fast`.
- **Spacing:** chart frame per the ChartRoom spec (header/readout/footer).
- **Colors:** status language (green/amber/red = state, never decoration);
  ≤ 6 categorical hues from the palette.
- **Interaction:** hover crosshair + readout swap; click drills down;
  range brush; compare toggles.
- **Keyboard:** chart is a region; focusable points announce value + date;
  arrows move the crosshair.
- **A11y:** every chart has a text summary (`aria-label` or a sr-only
  table) — a chart is never the only carrier of its data.

#### E16 TreeView `[new]`
- **Purpose:** hierarchical navigation (academic structure, permission
  trees).
- **States:** node rest/hover/focus/selected; expanded/collapsed; loading
  (lazy nodes); drag-over.
- **Variants:** checkable (permission tree) · navigable · draggable.
- **Animation:** expand `(slide, S, D1, I2)` — children descend with a
  max-height FLIP, 4px; the chevron rotates 90°.
- **Spacing:** level indent 16; row 32; chevron 20.
- **Colors:** selected `accent-subtle` wash + accent text; guides
  `divider`.
- **Interaction:** chevron toggles; row selects; drag with 6px threshold.
- **Keyboard:** APG Tree View — `Right` expand, `Left` collapse/parent,
  `Up/Down` siblings, `Home/End`, type-ahead; `aria-expanded`,
  `aria-selected`.
- **A11y:** `role=tree`/`treeitem`; `aria-level` + `aria-owns` when
  virtualized.

#### E17 Kanban `[new]`
- **Purpose:** pipeline/status boards (admissions stages, work orders).
- **States:** column (empty/hover-over), card (rest/drag/drag-over/editing).
- **Variants:** vertical lanes · horizontal swimlanes.
- **Animation:** card drag: FLIP the board (cards reflow as the dragged
  card crosses lanes), the dragged card lifts `elevation.xl` + scale 1.02;
  drop springs home. One dragged subject at a time.
- **Spacing:** lanes gap 16; card `p 12`, gap 8; lane header 40.
- **Colors:** lane `bg`; card `surface` + hairline; drag ghost 60%.
- **Interaction:** drag with 6px threshold; click card opens detail; lane
  footer "Add".
- **Keyboard:** cards are focusable rows; arrows move between cards,
  `Shift+arrows` move between lanes (documented key map); Enter opens;
  Space+arrows = keyboard drag.
- **A11y:** lanes are lists (`role=list`); the dragged card announces
  "moving to [lane]" via a polite live region.

#### E18 VirtualList `[new]`
- **Purpose:** 10k-row ledgers and long feeds at 60fps.
- **States:** windowed rendering only; loading more (sentinel).
- **Variants:** fixed-row (table) · variable (feed).
- **Animation:** scroll is native (never animated); rows entering are FLIP
  stationary (no mount animation — windowing is not choreography).
- **Spacing:** row heights per density tokens.
- **Colors:** per host component.
- **Interaction:** scroll; keyboard scrolls the container.
- **Keyboard:** standard scrolling + Home/End to the list bounds.
- **A11y:** the full list size announced ("1,000 items"); virtual rows
  remain in the accessibility tree as the user scrolls.

---

### Family F — Navigation

#### F1 Tabs `[migrate → TabGroup]`
- **Purpose:** sibling views of the same context.
- **States:** tab rest/hover/focus/selected/disabled; panel visible/hidden.
- **Variants:** underline (default) · pill (segmented) · with icons ·
  scrollable overflow.
- **Animation:** the underline/wash slides between tabs `fast` (FLIP, one
  element); panels fade `(fade, Z, D2, I2)` — never slide (tab = context
  switch, not navigation).
- **Spacing:** tab `px 16 py 10`; panel `pt 16`.
- **Colors:** underline `accent.base`; selected text `ink.900`.
- **Interaction:** click tab; optional close on closable tabs.
- **Keyboard:** APG Tabs — `Left/Right` move, `Home/End`, Enter/Space
  activates (automatic activation); panels in tab order.
- **A11y:** `role=tablist`/`tab`/`tabpanel`; `aria-selected`,
  `aria-controls`, `tabindex=-1` roving.

#### F2 VerticalTabs `[new]`
- **Purpose:** section navigation within a settings/page rail.
- **States:** as F1; groups and headings.
- **Variants:** with group headers · icon rail.
- **Animation:** selection wash slides `fast`; content fades `(fade, Z, D2,
  I2)`.
- **Spacing:** item 36; group header `mt 16 mb 6`; rail 240.
- **Colors:** active `accent-subtle` + accent text.
- **Interaction:** click; arrow keys.
- **Keyboard:** as F1 (vertical: `Up/Down`).
- **A11y:** as F1.

#### F3 Accordion `[new]`
- **Purpose:** progressive disclosure of related sections.
- **States:** item expanded/collapsed; disabled; loading.
- **Variants:** single-open · multi-open.
- **Animation:** expand = max-height FLIP + 4px fade `fast`; the chevron
  rotates 90°; siblings FLIP as space reflows.
- **Spacing:** item `px 16 py 12`; content gap 12; dividers between.
- **Colors:** hairline dividers; header text `ink.800`.
- **Interaction:** header click toggles; whole header is the hit target.
- **Keyboard:** header is a button; Enter/Space toggles; arrows move
  between headers.
- **A11y:** `aria-expanded` + `aria-controls`; content region labelled by
  the header.

#### F4 Breadcrumbs `[exists]`
- **Purpose:** the location path; **not** a navigation menu.
- **States:** link rest/hover/focus; current (non-link); overflow.
- **Variants:** standard · with back-arrow prefix.
- **Animation:** route change slides the trail `(slide, W, D1, I1)` (back)
  / `(slide, E, …)` (forward) with the page transition.
- **Spacing:** gap 6; separators `text-muted` 14.
- **Colors:** links `ink.600` → `ink.900` hover; current `ink.400`.
- **Interaction:** click a crumb navigates; middle crumb = overflow menu
  (> 4 crumbs).
- **Keyboard:** native links; overflow is a menu (A10).
- **A11y:** `nav aria-label="Breadcrumb"`; `aria-current=page` on the last
  crumb; `ol` structure.

#### F5 Stepper `[new]`
- **Purpose:** multi-step forms and onboarding.
- **States:** step: complete · current · upcoming · error · disabled;
  vertical/horizontal.
- **Variants:** numbered · checkmarked · with descriptions.
- **Animation:** completion draws the check `(draw, Z, D1, I1)`; the
  connector line fills `(draw, E, D1, I2)`; step change slides the panel
  `(slide, E/W, D2, I2)` by direction.
- **Spacing:** node 28; connector 2px; label gap 8; step gap 24.
- **Colors:** complete `success`; current `accent.base`; upcoming
  `surface-hover`.
- **Interaction:** clicking a past step returns to it (when allowed).
- **Keyboard:** steps are buttons; Enter moves; documented per form.
- **A11y:** `aria-current=step`; completed steps announced; the panel is a
  live region.

#### F6 Sidebar `[exists]`
- **Purpose:** primary app navigation with section grouping.
- **States:** expanded · collapsed (rail) · item hover/focus/active ·
  section overflow.
- **Variants:** full · rail · with section labels · pinned items.
- **Animation:** collapse animates width at `slow` with
  emphasized-decelerate (expand) / accelerate (collapse); labels
  cross-fade + slide 4px; nav items cascade 20ms on mount; the active
  indicator bar draws 3px. Spec §6.2 governs.
- **Spacing:** item 36; section label `mt 16 mb 6`; rail 64.
- **Colors:** active item `accent-subtle` + accent text + 3px indicator.
- **Interaction:** item click navigates; chevron collapses; pin.
- **Keyboard:** native links; arrows optional in rail mode; `[` collapses
  (documented).
- **A11y:** `nav aria-label="Primary"`; `aria-current=page`; the
  collapsed rail announces expanded item names via tooltip/focus.

#### F7 AppHeader `[exists → header.tsx]`
- **Purpose:** global context: search, workspace, notifications, theme.
- **States:** per-child; sticky shadow on scroll.
- **Variants:** default · focused (search expanded).
- **Animation:** the header's elevation appears on scroll `(fade, Z, D1,
  I2)`; nothing else moves.
- **Spacing:** height 56; controls gap 8; `px 20`.
- **Colors:** `surface` + hairline (elevated).
- **Interaction:** per child (B7, C9, I5, ThemeToggle).
- **Keyboard:** Tab through the control cluster; `/` focuses search.
- **A11y:** header landmark; controls have names.

#### F8 Carousel `[new]`
- **Purpose:** sequential media/announcements (rare in a data tool — used
  only where the domain proves it).
- **States:** slide active/adjacent; paused on hover; edge states.
- **Variants:** dots · arrows · autoplay (never without pause).
- **Animation:** slide `(slide, E/W, D3, I2)` direction-aware; dots wash;
  autoplay respects reduced motion (precise only, and stops on hover/focus).
- **Spacing:** slide gap 8; controls 44.
- **Colors:** dots `text-muted` → `ink.900` active.
- **Interaction:** arrows, dots, swipe (≥ 60px), wheel when focused.
- **Keyboard:** arrows (as buttons), Home/End, Tab into slides; Escape
  exits fullscreen mode.
- **A11y:** `aria-roledescription=carousel`; `aria-live=off` when
  interactive; slides have labels; autoplay honors `prefers-reduced-motion`.

#### F9 PageHeader `[exists]`
- **Purpose:** the view's title bar: title + breadcrumb + primary actions.
- **States:** scroll-condensed (title shrinks) · actions overflow.
- **Variants:** with breadcrumbs · with tabs under.
- **Animation:** title condenses `fast` on scroll; actions menu reveals on
  overflow via FLIP.
- **Spacing:** `pt 24 pb 16`; title 24/600; action gap 8 right.
- **Colors:** title `ink.900`; subtitle `text-secondary`.
- **Interaction:** actions are buttons; overflow is an ActionMenu.
- **Keyboard:** natural order.
- **A11y:** `h1` semantics; actions named.

#### F10 WorkspaceSwitcher `[exists]`
- **Purpose:** tenant/campus switching — a loud, safe, deliberate action.
- **States:** current chip · menu · switching (loading).
- **Variants:** chip · list.
- **Animation:** switch is a page-level event (route + data reload) — the
  transition is the page transition, never a local animation.
- **Spacing:** chip `px 10 py 6`; menu per D6.
- **Colors:** current identity chip `accent-subtle`.
- **Interaction:** click opens the campus list; selecting reloads scoped
  data.
- **Keyboard:** per D6.
- **A11y:** the current workspace is announced; the switcher is a menu
  button.

#### F11 NavRail `[new]` *(desktop: icon-level primary nav)*
- **Purpose:** the always-visible icon rail for the 5–7 top destinations.
- **States:** as F6 rail.
- **Variants:** static · with expand flyout.
- **Animation:** tooltip labels `(fade, Z, D1, I1)` on hover; active dot
  draws.
- **Spacing:** rail 64; item 40.
- **Colors:** per F6.
- **Interaction:** click navigates.
- **Keyboard:** native links; arrows cycle.
- **A11y:** `nav`; tooltips carry the names.

#### F12 QuickCreate `[exists]`
- **Purpose:** the fast path to the most common new-record actions.
- **States:** trigger · menu open · per-command.
- **Variants:** `+` button · inline.
- **Animation:** menu `(scale, Z, D2, I2)`; the new-record form opens as a
  Drawer (D3).
- **Spacing:** trigger 36; menu per D6.
- **Colors:** trigger `accent.base` (the one bright create affordance).
- **Interaction:** click → menu → drawer form.
- **Keyboard:** per D6; `N` shortcut opens (documented).
- **A11y:** trigger labelled "Create"; commands named.

---

### Family G — Layout

#### G1 Card `[exists]`
- **Purpose:** the atomic content container (surfaces only; never a
  generic wrapper for interactive composition without purpose).
- **States:** rest · hover (interactive variant) · selected · loading.
- **Variants:** `surface` · `interactive` · `kpi` · `hub` · `split`
  (§12.3).
- **Animation:** interactive hover: elevation rises + 4px arrow slide at
  `fast`; split rail draws.
- **Spacing:** `p 20`; header 16; body gap 16; footer `pt 12`.
- **Colors:** `surface` + hairline; `split` rail accent 3px.
- **Interaction:** interactive variant is clickable (a Link/button role).
- **Keyboard:** interactive cards are focusable + Enter activates.
- **A11y:** card title is a heading; interactive cards are real
  links/buttons (never div-with-onClick).

#### G2 AppShell `[exists → app-layout]`
- **Purpose:** the desktop frame: sidebar + header + content + optional
  inspector.
- **States:** sidebar expanded/rail; content loading; route transition.
- **Variants:** full · rail · with right inspector.
- **Animation:** sidebar width `slow`; route transitions per §6.3; the
  content area FLIPs as panels open/close.
- **Spacing:** sidebar 240/64; header 56; content `p 24 max-w-1600`.
- **Colors:** chrome `surface`; content `bg`.
- **Interaction:** resize, collapse, navigation.
- **Keyboard:** `[` collapses sidebar (documented); route-level key map.
- **A11y:** landmarks — `nav`, `header`, `main`, `footer`; skip link
  first in tab order.

#### G3 SplitPane `[new]`
- **Purpose:** resizable side-by-side panes (detail + list, code + preview).
- **States:** drag-handle rest/hover/dragging; pane collapsed.
- **Variants:** vertical · horizontal · with collapse.
- **Animation:** dragging is 1:1 (no easing during drag — §5.5); release
  snaps to the nearest token grid at `fast`.
- **Spacing:** handle 6px hit area (2px visible); panes gap 0.
- **Colors:** handle `divider` → `accent.base` on hover/drag.
- **Interaction:** drag ≥ 6px; double-click the handle resets.
- **Keyboard:** handle focusable; arrows resize by 16px steps; Shift+arrows
  = 64px.
- **A11y:** panes are regions with labels; the handle is a slider
  (`role=separator`, `aria-valuenow`).

#### G4 Stack / G5 Grid `[new]`
- **Purpose:** token-driven arrangement primitives (no magic numbers).
- **States:** static.
- **Variants:** Stack: row/column + gap token; Grid: fixed/auto-fit with
  token gutters.
- **Animation:** none intrinsic.
- **Spacing:** gap from the space scale only.
- **Colors:** n/a.
- **Interaction:** none.
- **Keyboard:** n/a.
- **A11y:** n/a (semantic-free layout; `as` prop for the host element).

#### G6 Section `[new]`
- **Purpose:** a titled block inside a page (heading + content + optional
  actions).
- **States:** static; optional collapsed.
- **Variants:** with hairline top · with action row.
- **Animation:** collapse per F3.
- **Spacing:** `py 20`; heading 16/600; action gap 8.
- **Colors:** heading `ink.900`.
- **Interaction:** actions are buttons.
- **Keyboard:** n/a unless collapsible.
- **A11y:** heading levels passed in, never hardcoded.

#### G7 Divider `[new]`
- **Purpose:** visual separation with optional label.
- **States:** static.
- **Variants:** hairline · label-middle · vertical.
- **Animation:** none.
- **Spacing:** 1px; label `px 8`.
- **Colors:** `divider`.
- **Interaction:** none.
- **Keyboard:** n/a.
- **A11y:** decorative (`aria-hidden`) unless it carries a label
  (then a horizontal rule with text semantics).

#### G8 ScrollArea `[new]`
- **Purpose:** scrollable region with native (or styled) scrollbars and
  sticky-until-scrolled shadows.
- **States:** at-top · scrolling · at-bottom.
- **Variants:** native · custom thumb.
- **Animation:** the shadow fades in `(fade, Z, D1, I1)` when content
  passes beneath; the thumb appears on hover/scroll only.
- **Spacing:** shadow 8px; thumb 8.
- **Colors:** shadow uses the elevation gradient; thumb `ink.400`.
- **Interaction:** wheel, drag thumb, touch.
- **Keyboard:** focusable when it contains focusable content (tabindex=0
  only for scroll-only regions).
- **A11y:** `tabindex=0` + `aria-label` when the region scrolls but has no
  focusable children.

#### G9 Toolbar `[new]`
- **Purpose:** a horizontal cluster of view-level commands (filter rail
  companions, table actions).
- **States:** per-child; overflow.
- **Variants:** with search · with segments · overflow-only.
- **Animation:** overflow items move into an ActionMenu via FLIP.
- **Spacing:** gap 8; height 40; `px 4`.
- **Colors:** transparent until scrolled/elevated.
- **Interaction:** per child.
- **Keyboard:** arrows navigate between tool items (APG toolbar) or Tab —
  declared per instance.
- **A11y:** `role=toolbar` when arrows navigate; children have names.

#### G10 ErrorState `[exists]`
- **Purpose:** the honest failure frame with a retry path.
- **States:** error · retrying · offline.
- **Variants:** full-page · inline.
- **Animation:** `(fade, Z, D2, I2)`; the retry button pulses once on
  mount.
- **Spacing:** `py 48`; icon 48; message 16.
- **Colors:** icon `status.danger.fg` in a `danger-light` tile.
- **Interaction:** retry refetches; "report" optional.
- **Keyboard:** retry is first focusable.
- **A11y:** `role=alert`; the error message is text, not an icon.

---

### Family H — Analytics (The Watchtower)
Fully specified in `ANALYTICS_SYSTEM_V3.md`. The Foundry catalogs the
components the Watchtower mandates, each with the same contract:

#### H1 ChartFrame
- **Purpose:** every chart's single frame — header (title + presets +
  compare/fullscreen/export), live readout row, provenance footer.
- **States:** loading · empty · data · live · stale (honest).
- **Variants:** preset set (1D/1W/1M/1Y) · compare · fullscreen.
- **Animation:** readout swaps `(fade, Z, D1, I1)`; fullscreen `(scale, Z,
  D4, I3)`.
- **Spacing:** header 44; readout 40; footer 24.
- **Colors:** readout numeral `ink.900`; delta chips per status language.
- **Interaction:** hover crosshair swaps the readout; click drills.
- **Keyboard:** frame is a region; fullscreen via `F`.
- **A11y:** sr-only data table per chart.

#### H2 Sparkgrid
- **Purpose:** the dense terminal table where every row carries a
  sparkline.
- **States:** per E1 plus live-wash cells.
- **Variants:** density per ledger rules.
- **Animation:** row wash on live push (decaying); sparkline extends.
- **Spacing:** per E1 compact.
- **Colors:** sparklines single-hue accent.
- **Interaction:** row click drills; copy-friendly.
- **Keyboard:** per The Ledger §12.
- **A11y:** per E1.

#### H3 GoalArc / BulletChart
- **Purpose:** progress vs target (fees collected, attendance target).
- **States:** on-track · at-risk · off-track.
- **Variants:** arc · bullet.
- **Animation:** the arc draws `(draw, E, D1, I2)`; the target marker
  springs in.
- **Spacing:** arc 96; label right.
- **Colors:** the status machine: `success`/`warning`/`danger` by
  *good-for-goal*.
- **Interaction:** hover shows the gap value.
- **Keyboard:** value + target announced.
- **A11y:** `role=img` with the full sentence ("72% of the ₦4M target").

#### H4 RangeBrush
- **Purpose:** the zoom strip under time-series charts.
- **States:** rest · dragging.
- **Variants:** single window · multi.
- **Animation:** dragging 1:1; the brush window resizes live.
- **Spacing:** 24 high; handles 12.
- **Colors:** window `accent-subtle` fill + accent edges.
- **Interaction:** drag window, drag edges, click to jump.
- **Keyboard:** handle = slider semantics, arrows ±1 day.
- **A11y:** `role=slider` pairs with `aria-valuetext` dates.

#### H5 LiveReadout
- **Purpose:** the big tabular numeral + delta chip that answers "what is
  it now?"
- **States:** idle · updating · stale.
- **Variants:** per unit (₦, %, count).
- **Animation:** count-up (AnimatedCount); the delta chip pulses once on
  change.
- **Spacing:** numeral 28/600; delta gap 8.
- **Colors:** delta by the goal map.
- **Interaction:** hover swaps in the cursor value (the chart frame owns
  this).
- **Keyboard:** n/a.
- **A11y:** the numeral is the value; direction words on the delta.

#### H6 HeatBand
- **Purpose:** 24-hour activity bands (attendance by hour).
- **States:** empty · data.
- **Variants:** hour bands · weekday×hour.
- **Animation:** cells wash in with data arrival (stagger 4ms).
- **Spacing:** cell 12 with 2 gap.
- **Colors:** single-hue intensity ramp (never rainbow).
- **Interaction:** hover reveals exact value in the readout.
- **Keyboard:** cells focusable with value+label.
- **A11y:** the heatband has a text summary; cell names carry the label.

---

### Family I — Shell & domain

#### I1 RouteTransition `[exists]`
- **Purpose:** page-level enter/exit choreography (§6.3 Motion).
- **States:** entering · exiting · (rapid-nav coalescing).
- **Variants:** push (E) / pop (W); native View Transitions on precise
  tier, useMove fallback otherwise.
- **Animation:** `(slide, E/W, D4, I3)` 500ms enter / 350ms exit (0.7×);
  direction from navigation type.
- **Spacing:** n/a.
- **Colors:** n/a.
- **Interaction:** navigation triggers it; back/forward respected.
- **Keyboard:** n/a.
- **A11y:** reduced-motion tiers snap (no transition at all).

#### I2 ThemeToggle `[exists]`
- **Purpose:** light/dark/system switching.
- **States:** current mode; cycling.
- **Variants:** icon-only · label.
- **Animation:** the icon crossfades; the theme switch itself is a
  document-level wash (fade at `slow`), never per-component.
- **Spacing:** 36.
- **Colors:** per mode tokens.
- **Interaction:** click cycles light→dark→system.
- **Keyboard:** button.
- **A11y:** `aria-label="Theme: dark, switch to light"`.

#### I3 SystemThemeToast `[exists]`
- **Purpose:** announces OS theme changes to the in-app preference.
- **States:** per C7.
- **Variants:** one-shot.
- **Animation:** per C7.
- **Spacing/Colors:** per C7.
- **Interaction:** action applies.
- **Keyboard/A11y:** per C7 with `role=status`.

#### I4 InstallPWA `[exists]`
- **Purpose:** install affordance where the browser allows.
- **States:** available · installed · unsupported (hidden).
- **Variants:** header chip · standalone button.
- **Animation:** chip enters `(scale, Z, D1, I1)` when available.
- **Spacing/Colors:** per C3 chip / A1.
- **Interaction:** click installs.
- **Keyboard:** button.
- **A11y:** named per state.

#### I5 ContextualActions `[exists]`
- **Purpose:** the context-appropriate action cluster on a page (based on
  selection).
- **States:** empty (hidden) · active · disabled.
- **Variants:** toolbar · floating.
- **Animation:** appears `(slide, E, D2, I2)` with selection; disappears
  reverse; the floating variant never pushes content (overlays it).
- **Spacing:** cluster gap 8; floating `p 8` + shadow.
- **Colors:** `surface` + hairline + `shadow.lg`.
- **Interaction:** actions operate on the selection.
- **Keyboard:** actions reachable in order; Escape collapses.
- **A11y:** `aria-label="Actions for N selected"`; a live region announces
  the selection count.

#### I6 OrganizationSwitcher `[exists]`
- **Purpose:** the campus/role identity chip (see F10).
- **States:** per F10.
- **Variants:** chip · menu.
- **Animation:** per F10.
- **Spacing/Colors:** per F10.
- **Interaction:** opens the tenant list.
- **Keyboard/A11y:** per D6.

#### I7 ProtectedRoute `[exists]`
- **Purpose:** auth + permission gate around routes.
- **States:** checking · authorized · redirecting · forbidden.
- **Variants:** role-based · permission-based.
- **Animation:** the gate renders nothing (no flash of unauthorized
  content); the redirect is a route transition.
- **Spacing/Colors:** n/a.
- **Interaction:** n/a.
- **Keyboard/A11y:** n/a (the shell announces the redirect via a toast).

#### I8 RoleMultiSelect `[exists → B5]`
- **Purpose:** role assignment (admin) — B5 with role chips.
- **States/Variants:** per B5; role check semantics.
- **Animation/Spacing/Colors/Interaction/Keyboard/A11y:** per B5.

---

## 5. The audit table — provenance and status

| Component | Where | Status |
|---|---|---|
| A1 Button | `ui/button.tsx` | migrate — apply §12.1 contract verbatim |
| A2 IconButton | (within button usages) | new — extract from call sites |
| A6 Checkbox | (native, in forms) | migrate — extract to `ui/checkbox.tsx` |
| A8 SegmentedControl | `ui/tab-group.tsx` | migrate — reuse as the pill variant |
| B3 Select | `ui/select.tsx` | migrate — add popover + type-ahead |
| B5 MultiSelect | `admin/role-multi-select.tsx` | migrate — promote to `ui/` |
| B7 SearchInput | `ui/search-input.tsx` | exists — conforming |
| C1/C2 Badge/StatusBadge | `ui/badge.tsx`, `ui/status-badge.tsx` | exists — conforming |
| C3 Chip | `table/filter-rail.tsx` (internal) | migrate — extract to `ui/chip.tsx` |
| C5 Alert | `ui/alert.tsx` | exists — conforming |
| C7 Toast | `ui/toast.tsx` | exists — conforming (motion-module) |
| C9 Bell | `notifications/notification-bell.tsx` | exists — conforming |
| C10/C11 Loading/Skeleton | `ui/loading.tsx`, `ui/skeleton.tsx` | exists — conforming |
| C14 AnimatedCount | `ui/animated-count.tsx` | exists — conforming |
| C16 EmptyState | `ui/empty-state.tsx` | exists — conforming |
| D1–D3 Modal/Confirm/Drawer | `ui/modal.tsx`, `confirm-dialog.tsx`, `drawer.tsx` | exists — conforming (drawer = motion-module) |
| D5 Tooltip | `ui/tooltip.tsx` | exists — conforming |
| D6 DropdownMenu | `ui/dropdown-menu.tsx` | exists — conforming |
| D8/D9 Palette/Search | `ui/command-palette.tsx`, `global-search-modal.tsx` | exists — conforming |
| D13/D14 Shortcuts/LinkChild | `ui/keyboard-shortcuts-dialog.tsx`, `link-child-dialog.tsx` | exists — conforming |
| E1/E2 DataTable/FilterRail | `ui/table/` | exists — conforming (The Ledger) |
| E3 Pagination | `ui/pagination.tsx` | exists — conforming |
| E4 Timeline | `timeline/timeline.tsx` | exists — conforming |
| E8 KPI | `analytics/kpi-card.tsx` | migrate — bound to the goal map |
| E10–E15 Charts | `analytics/*-chart.tsx` | migrate — Watchtower grammar, kill hardcoded colors |
| F1 Tabs | `ui/tab-group.tsx` | migrate — underline + slide wash |
| F4 Breadcrumbs | `ui/breadcrumbs.tsx` | exists — conforming |
| F6/F7 Sidebar/Header | `layout/sidebar.tsx`, `header.tsx` | exists — conforming (motion-module) |
| F9 PageHeader | `ui/page-header.tsx` | exists — conforming |
| F10/F12 Workspace/QuickCreate | `layout/…` | exists — conforming |
| G1 Card | `ui/card.tsx` | exists — conforming |
| G2 AppShell | `layout/app-layout.tsx` | exists — conforming |
| G10 ErrorState | `ui/error-state.tsx` | exists — conforming |
| H1–H6 | spec-only | new — with the Watchtower build |
| Everything else | — | new — build per this catalog |

---

## 6. Governance

**The review gate.** A component is "in the Foundry" only when all of these
hold:

1. **The nine fields are true of the code.** The spec is checked against the
   implementation by a reviewer; a field that names a state the code cannot
   reach is a defect.
2. **No raw values.** Grep the component for hex codes, magic numbers
   (beyond the tokens), and hand-authored animations. Zero hits.
3. **Keyboard-complete.** The key map in the entry works, and the component
   has no mouse-only path.
4. **Axe-clean.** The component passes axe with zero color-only and
   name-missing violations.
5. **Tier-correct.** Reduced-motion runs produce no movement, and no
   spatial move runs in the efficient tier.
6. **Tested.** Every state machine in the entry is covered by a test —
   states are contracts, and contracts are tested.

**The extraction rule.** A `[migrate]` component is promoted by *extraction
with parity*: the new `ui/` file reproduces current behavior byte-for-byte
where the spec says "conforming", and the old call sites are updated in the
same PR. No migrate is shipped half-done.

**The new-component rule.** A `[new]` component is built only when a page
needs it (the provenance rule of §1). Building the catalog alphabetically is
waste; building it from the pages' demand is the Foundry's way.

---

## 7. Implementation map

The catalog is deliberately aligned with work already underway:

1. **Promote the table module's Chip** to `ui/chip.tsx` (C3) — the filter
   rail already uses it; extraction is mechanical.
2. **The header module** (The Ledger §19.1) — sort/resize/pin — establishes
   E1's header, which F1 Tabs and A8 SegmentedControl share.
3. **The date picker (B9)** — first `[new]` input, because fee/attendance
   filters need range dates (B11 follows).
4. **Extract Checkbox/Radio/Toggle** (A5–A7) from native usages — the
   selection work in The Ledger §7 needs them.
5. **The Watchtower chart wrappers** (E10–E15, H1–H6) per the analytics
   migration order.
6. **SplitPane, ScrollArea, Toolbar** (G3/G8/G9) when the inspector panel
   and the analytics command bar land.
7. **Kanban and TreeView** (E16/E17) when the admissions and permission
   screens demand them.

---

## 8. Acceptance criteria

The Foundry is complete when:

1. **Every page imports only Foundry components** — zero inline
   hand-styled elements beyond tokens.
2. **The audit table's migrate rows are all resolved** with parity.
3. **A component review can be done from the spec alone** — a reviewer
   holding `COMPONENT_LIBRARY_V3.md` can check a component against its entry
   without reading the codebase for intent.
4. **Keyboard-complete:** every key map in the catalog works in all three
   tiers.
5. **The library is export-stable:** the `components/ui/index.ts` barrel is
   the only import surface, and it never exports an undocumented component.
