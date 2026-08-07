# SDMAS Table System v3 — "The Ledger"

> The fourth normative expansion of the Corridor system (after Design System v3,
> Motion System v3, and the App Redesign). Codename: **The Ledger**.
>
> **Scope:** the complete UX specification for every data table in SDMAS —
> rosters, ledgers, registers, logs, and lists. No code. Architecture and
> specification only.
>
> **Companion docs:** `DESIGN_SYSTEM_V3.md` (§12.4 Tables, §6.3 density, §12
> palette), `MOTION_SYSTEM_V3.md` (state machine §5, table states §5.5,
> FLIP §9), `ANALYTICS_SYSTEM_V3.md` (chart-room grammar), `APP_REDESIGN_V3.md`
> (screen-by-screen layouts).

---

## 1. The philosophy: the table is the instrument

SDMAS is a school-management system whose operators spend their days in one
place: **the table**. Fee ledgers, attendance registers, student rosters, audit
logs, payment receipts — these are not "views of data," they are *instruments
of work*. The redesign treats the table as the highest-craft surface in the
product, on par with the chart room.

Three principles govern every rule in this document:

1. **The terminal decides what to show, the operator decides what to do.**
   Defaults are chosen by the machine (the sensible sort, the sensible
   columns, the sensible density); every decision the operator makes is one
   keystroke or one click away, never buried.
2. **Cells are content, rows are records, columns are categories.**
   Visual weight flows in that order: cell → row → column. A row is never
   louder than its most important cell; a column is never louder than the
   records it contains.
3. **Nothing moves that doesn't have to.** Tables are reading instruments.
   The only sanctioned motions are state acknowledgements (selection, hover,
   expand) and identity-preserving reorderings (FLIP). A table that animates
   itself is a table that cannot be read.

### 1.1 The three table classes

Every table in SDMAS is one of three instruments, and its class decides its
behavior budget:

| Class | What it is | Examples | Behavior budget |
|---|---|---|---|
| **Registry** | Master lists of entities; the "system of record" navigation | Students, teachers, sections, terms, fee types | Full: selection, bulk actions, inline edit, filters, saved views |
| **Ledger** | Financial/transactional history; append-only, audit-critical | Payments, receipts, transactions, outstanding balances, audit log | Terminal: keyboard-first, copy/paste, frozen columns, live updates; *no inline editing* |
| **Register** | Time-series operational records | Attendance registers, leave, report exports, application list | Hybrid: filters + bulk actions; read-mostly rows; batch ops over inline edit |

**Rule T1 — a table never mixes classes.** A registry may not hide ledger
semantics and vice versa. The class is declared by the page, not inferred.

---

## 2. Anatomy of the table frame

Every table renders inside one **frame** — a single surface component — so
that no page ever assembles a table by hand again.

```
┌──────────────────────────────────────────────────────────────────────┐
│ toolbar  │ title · context chip · saved-view selector  │ actions  │  │  ← page chrome (not table)
├──────────────────────────────────────────────────────────────────────┤
│ filter rail │ search box · facet chips · active-filter count · clear │  ← smart filter (§6)
├──────────────────────────────────────────────────────────────────────┤
│  ☐ │ NAME ▾  │ CLASS   │ FEES DUE ║│ STATUS │ ACTIONS ║│  (sticky)   │  ← column band (§4)
│────┼─────────┼─────────┼──────────║│────────┼─────────║│             │
│  ☑ │ Amina K.│ 4-A     │ ₦12,400 ║│  due   │ ⋯       ║│             │
│  ☐ │ Bello M.│ 3-B     │ ₦0      ║│ paid   │ ⋯       ║│             │
│    │         │         │          ║│        │         ║│             │
├──────────────────────────────────────────────────────────────────────┤
│ footer │ 48 of 1,204 rows · < 20 50 100 > · updated 2s ago            │
└──────────────────────────────────────────────────────────────────────┘
```

Frame rules:

- **T2** The frame owns: sticky band, sticky pinning seams, scroll, footer,
  and the row virtualization viewport. Pages pass columns, data, and the class.
- **T3** Vertical gridlines are banned (§12.4). Hairline row dividers only,
  `ink.200 @ 50%` in light, `ink.700 @ 50%` in dark.
- **T4** The first and last visible columns get a 4px gradient "fade out"
  under the sticky band only while scrolled (`mask-image` on the band, not the
  rows — cheap and composited).
- **T5** Numerics right-aligned, tabular numerals (`font-feature-settings:
  "tnum"`), headers for numeric columns also right-aligned so the sort arrow
  aligns over the digits (§12.4).
- **T6** The body scrolls inside the frame; the page never scrolls the table.
  Frame height is set by the page (`flex-1` of the content column).

---

## 3. The column model

### 3.1 Column types

A column's **type** is a first-class declaration that drives alignment,
rendering, filtering, sorting, copying, and keyboard behavior. Types are
extensible; the core set:

| Type | Alignment | Renderer | Sort | Filter | Notes |
|---|---|---|---|---|---|
| `text` | left | plain, ellipsis | alpha | contains | Names, notes |
| `person` | left | avatar 24 + name (name truncates, avatar never) | alpha | contains | Students, teachers, guardians |
| `numeric` | right | tabular, thousands separators | numeric | range | Counts, IDs |
| `amount` | right | currency (₦ default), `-` for zero | numeric | range | Fees, balances |
| `date` | left | localized `d MMM yyyy`, tooltip full ISO | chrono | date range | Never `YYYY-MM-DD` raw |
| `status` | left | pill badge (§12.4) | by severity order | facet | Paid/Due/Overdue, Present/Absent |
| `progress` | left | 2px mini bar + % | numeric | range | Completion, attendance % |
| `relation` | left | chip + chevron | alpha | — | "Section 4-A", "Term 2" |
| `actions` | right, sticky | ghost icon buttons, revealed on row hover | — | — | Never more than 3 visible; rest in menu |
| `expander` | left, 28px | chevron (rotates 90° on expand) | — | — | Only when rows expand (§8.1) |
| `checkbox` | left, 36px | row-selection checkbox (§7) | — | — | Only when bulk ops exist |

- **T7** Columns are declared in the page as type + key + label; the frame
  provides the renderer. **No page may hand-render a cell with ad-hoc
  Tailwind classes.** (This is the current codebase reality — every page
  inlines `render` closures with bespoke styling. That ends.)
- **T8** Widths: type-derived defaults (person 200, amount 120, status 110,
  actions 96, text flex). Pages may override; min widths are enforced:
  numeric/amount 96, person 180, status 96, date 120, actions 96.

### 3.2 Column resizing

- **T9** Resize is available on all non-frozen, non-checkbox/expander columns
  via a 6px handle at the header's right edge. Hover: the handle widens to a
  2px accent hairline. Dragging: 1:1 tracking (no easing during drag, §5.5
  dragging rule), a full-height ghost seam follows the cursor; the column
  paints live on drag for widths under 10,000px of data.
- **T10** Double-click the handle = autosize to content (max 320px, min = the
  type minimum).
- **T11** Resized widths persist to the saved view (§6.5), not to global
  storage. No view = no persistence.

### 3.3 Column pinning

- **T12** Left-pin candidates: checkbox, expander, person/name, and at most
  two more user-chosen columns. Right-pin: the actions column always
  (§12.4), plus at most one user-chosen column (e.g. balance).
- **T13** Pinned columns are always visible during horizontal scroll and
  cast a 8px soft shadow seam over the scrolling body when content passes
  beneath (`box-shadow` on the *seam*, one element, not per row — the
  box-shadow-on-many rule from §5.5).
- **T14** Pinning state lives in the saved view. Pin is toggled from the
  column menu with a pushpin icon; pinned columns show the pin filled and
  their header cell gets a 2px accent left edge (left-pinned) / right edge
  (right-pinned).

### 3.4 Column visibility

- **T15** The column menu (⋯ in the band's trailing cell) lists all columns
  with eye toggles; hidden columns are dimmed and moved to the bottom of the
  list. Toggling re-fits flex columns immediately (FLIP, no jump).
- **T16** Hiding the *identity* column (the first non-checkbox column) asks
  for confirmation once — "Without the name column this view may be
  ambiguous." One-time, dismissible.
- **T17** Visibility + order + widths + pins = the **column configuration**,
  and it is serializable into a saved view (§6.5).

---

## 4. Sorting

- **T18** Clicking a sortable header cycles none → asc → desc. The arrow is
  the only affordance; headers are not underlined on hover (they are buttons
  with a `ink.50` hover wash).
- **T19** Active sort renders the arrow filled + accent, adjacent to the
  label; secondary sorts render dimmer arrows stacked beneath. Multi-sort is
  modifier + click (`Shift`), max 3 keys, always stable (tie-break on the
  row's natural id).
- **T20** `status` columns sort by the **severity order** defined by the
  domain (Overdue → Due → Paid), never alphabetically. `person` sorts by
  last-name. These are type behaviors, not page behaviors.
- **T21** Sorting animates with FLIP (§9 of the motion spec): rows translate
  to their new positions at `slow` (260ms) with the emphasized-decelerate
  curve, identity preserved via stable keys. This is the *only* table
  reorder that may move rows — and it must, because a jump-cut sort is
  unreadable. (See the shipped `useFlipList` hook — this is its target.)
- **T22** While sorting, the body's scroll position clamps to keep the
  previously-selected row visible.

---

## 5. Density

- **T23** Two densities only (§6.3): **Comfortable** 48px rows (people:
  students, teachers, persons) and **Compact** 36px rows (ledgers, registers,
  audit). Defaults per table class: Registry → Comfortable, Ledger/Register →
  Compact. The current codebase's `compact` boolean survives as a per-page
  default; the user can override per view.
- **T24** The density toggle (Compact/Comfortable segmented control in the
  band's trailing cell) animates row heights via FLIP at `fast` (120ms),
  standard curve. Cell content is top-aligned so nothing "grows".
- **T25** Density preference persists per page, not globally — an audit
  viewer wants compact even if the student roster wants comfortable.

---

## 6. Smart filtering

The filter rail (always visible above the band, §12.4 "toolbar above, never
inline") is the single entry point for finding rows.

### 6.1 The search box

- **T26** One search box, `type=search`, 320px, grows to 480px on focus
  (width transition at `fast`, standard). Placeholder is the table's own
  hint: "Search students, IDs, guardians…" — never a bare "Search".
- **T27** Search matches across *searchable* columns only (text, person,
  relation, ID, numeric as string). Status/amount columns are not searched —
  you filter those.
- **T28** Search is debounced 180ms, then the row set updates with FLIP at
  `fast`. The count in the footer animates (count-up, §analytics live readout
  pattern) rather than flashing.

### 6.2 Facet filters

- **T29** Each filterable column exposes a facet menu from its header
  (chevron appears on hover) listing the distinct values with counts:
  `Due (14) · Paid (9) · Overdue (3)`. Selecting sets a **chip** in the
  filter rail: `STATUS: Due ×`.
- **T30** Chips: `pill` size, `ink.100` fill, close × on the right, max 6
  visible then a `+3 more` overflow chip. Chips are the *only* persistent
  filter affordance — filters never hide in a dropdown drawer.
- **T31** Range filters (amounts, dates, progress) open a small popover with
  two inputs (min/max, or from/to) and a quick preset row (e.g. "this term",
  "overdue", "> 50%"). Presets are authored by the domain, not generic.

### 6.3 The smart filter query language

For Ledger and expert Registry users, the search box accepts a light query
language:

- `overdue` — matches status facets
- `amount>5000` / `date>=2026-01-01` — range predicates on typed columns
- `paid overdue` — AND of predicates; `paid OR overdue` — OR
- `name:"Amina K"` — exact phrase in a named column

**T32** The language is *discoverable, not documented-or-else*: typing a
`>` or `:` or known facet word pops a suggestion card under the box with the
valid completions. Everything expressible in the language is also reachable
via chips — the language is a power-user accelerator, never the only path.

### 6.4 Filtering is FLIP, not re-mount

- **T33** Filtering never re-renders the world. Rows that remain keep their
  position identity (FLIP at `fast`), rows that leave animate out via the
  exit choreography (`fade + 4px slide`, `fast`), and rows that enter fade
  in. No page may show a loading skeleton for a filter change.
- **T34** The filter state is reflected in the URL query string
  (`?q=&status=due&sort=...`) so a filtered table is a shareable deep link —
  this is the same deep-link rule as the analytics function codes.

### 6.5 Saved views

- **T35** A "View" button next to the title opens the view menu: current
  inline (with unsaved-changes dot), saved views list, "Save current as…".
  A saved view captures: columns (visibility/order/widths/pins), sort,
  filters, density, page size. Not: page, scroll.
- **T36** Views are per-page + per-role (an accountant's fee-due view differs
  from a principal's). Saving overwrites with confirmation; renames and
  deletes live in the same menu.
- **T37** A dirty view (filters/columns differ from the last save) shows an
  unsaved dot; the menu entry becomes "Update saved view".

---

## 7. Selection & bulk actions

### 7.1 Row selection

- **T38** The checkbox column exists only when the page has ≥1 bulk action
  (T-class: Registry and Register). Ledgers never select — they copy (§11).
- **T39** Selection is by checkbox, by row click only when the page has no
  row-detail navigation (a row that navigates on click must not select on
  click — one primary gesture per row). Row click selects with `Shift` for
  range, `Ctrl/Cmd` for toggle.
- **T40** Selected rows: `accent` tint wash (`accent.500 @ 8%`), never full
  accent fill (§12.4). The checkbox draws its check (Draw verb, §5.5). The
  selection wash morphs in at `base` (180ms) — no flash, no bounce.

### 7.2 The bulk action bar

- **T41** When ≥1 row is selected, a **floating action bar** materializes
  pinned to the bottom of the frame (slides N at `base`, decelerate, with
  elevation + hairline): `3 selected · [Mark paid] [Export] [⋯] [Clear]`.
  It is *not* a toolbar row that pushes the table — nothing reflows.
- **T42** The bar shows the first two primary bulk actions as buttons and
  the rest in a menu; the count is live-updating as selection changes.
- **T43** Bulk destructive actions (delete, void) always route through the
  confirm dialog with the count in the copy: "Void 12 receipts? This cannot
  be undone." (§12.5).
- **T44** Selection survives pagination/virtual scrolling (it is a Set of
  ids, not a Set of rows) and is preserved across a filter change *only if*
  the filter is a refinement; changing a filter clears selection if it would
  hide selected rows. The bar announces: "3 selected · 1 filtered out".

### 7.3 Selection motion

- **T45** Checkbox group header cycles: none → all → none; the header
  checkbox shows a dash for partial selection. All three states Draw in
  `base`. The selection wash on the rows updates simultaneously at the same
  duration (motion is a state acknowledgement, not a parade).

---

## 8. Row expansion, detail, and highlighting

### 8.1 Row expansion

- **T46** Expansion is available on Register/Registry rows with rich detail
  (student summary, transaction breakdown). The expander chevron rotates 90°
  at `base`; the detail region opens via FLIP (transform-only height, §9 of
  the motion spec), contents fade in staggered 20ms, max 150ms stagger
  (§5.5 Expanded rule). Collapse reverses.
- **T47** Only one row may be expanded at a time *unless* the detail is
  "inline form" (e.g. quick-edit) — multiple open forms are a cognitive
  hazard. Expanded rows pin to the top of the viewport while open (the row
  header stays visible in the sticky band seam).
- **T48** Press `E` or Enter on a focused row toggles its expansion (see
  keyboard map §12).

### 8.2 Row highlighting

- **T49** The frame supports a *row emphasis* state distinct from selection:
  `attention` (accent-left 3px rail + `accent.500 @ 5%` wash, no checkbox)
  for "this needs your eye" (overdue fees, pending applications). It is
  driven by domain data, not by the user, and coexists with selection
  visually (emphasis rail + selection wash stack cleanly).
- **T50** Recently-changed rows (see live updates §10) hold a **status wash**
  that decays: `success @ 10%` → 0 over 1.6s with a single easing curve —
  never a blink loop.

---

## 9. Inline editing

Inline editing is for **Registry** tables and only for fields the domain
allows (a ledger amount is never inline-editable; a fee type's name is).

### 9.1 Interaction model

- **T51** Edit affordances: double-click a cell (pointer), Enter on a focused
  cell (keyboard), or the pencil from the row's action menu. Editing renders
  the cell as an input sized to the column — the cell *becomes* the field
  (no popover, no drawer — the row is the form).
- **T52** Commit: Enter or blur. Cancel: Esc (restores the pre-edit value
  with no motion — a revert is not a transition). Tab commits and moves to
  the next editable cell in the row; Shift+Tab moves back. Editing a row in
  a virtualized list scrolls the row fully into view first.
- **T53** Validation is inline and immediate: an invalid value (e.g. a
  non-numeric amount) renders the cell with a `danger` ring + a micro-label
  below the row, and the row's other edits are suspended until fixed. The
  row commits as one transaction or not at all — a row is never left
  half-committed.
- **T54** While a row is being edited, the bulk action bar is suppressed for
  that row; selection of other rows remains possible but a selected row
  cannot be edited (one intent per row).

### 9.2 Edit motion

- **T55** Entering edit: the input fades in at `fast` over the cell value,
  the value *stays in place* (no scale, no shift — the cell content is the
  subject). A `base` Draw on the focus ring. Exiting edit: same, reversed.
  Autofocus lands with the caret at the value's end for text, selected for
  numerics.

---

## 10. Live updates

Registers and Ledgers (attendance, payments, notifications) may receive live
rows over the existing SSE pipeline.

- **T56** An arriving row inserts at its sorted position via FLIP at `fast`
  with a single `success` status wash that decays over 1.6s (T50). If the
  row sorts outside the visible viewport, nothing animates — the count in
  the footer ticks up and the row is discoverable via the filter.
- **T57** A *changed* visible cell (e.g. a payment flips to "paid") gets a
  800ms status wash on that cell only — the rest of the row stays still.
  Never more than one concurrent loop: the only repeating element in the
  whole frame is the tiny sync dot in the footer ("live · updating") with
  the one-Pulse-per-moment rule (§4.5 of the motion spec).
- **T58** The footer's "updated Ns ago" timestamp refreshes on each push;
  a stale connection (> 60s) flips the chip to `updated just now · stalled`
  in amber — the terminal announces the feed's health, not just the data's.

---

## 11. Copy/paste & Excel-like interactions

The **Ledger** class is copy/paste-first. This is the Bloomberg-tape muscle
of the table.

- **T59** `Ctrl/Cmd+C` on a selection (or on the focused cell) copies the
  visible selection to the clipboard as **TSV** (tabs, `\r\n` rows) with the
  displayed values, formatted numbers as *displayed* (₦12,400) not raw. A
  transient "Copied 12 cells" toast confirms; the confirmation is a toast,
  not a visual sweep across the table (the table does not dance for the
  clipboard).
- **T60** `Ctrl/Cmd+Shift+C` copies with headers as the first row. `Ctrl/Cmd+A`
  selects the *visible* viewport's rows first; a second press extends to all
  filtered rows (Excel's behavior).
- **T61** Pasting is available only in inline-edit cells (Registry) and only
  for a single cell's value — multi-row paste is explicitly out of scope for
  v3 (data-entry flows like batch enroll are handled by dedicated bulk
  operations, not by pasting into a table).
- **T62** The context menu (right-click, or `Menu` key) is the cell's
  clipboard surface: Copy / Copy with headers / Copy row / (Edit / Delete —
  when permitted by class). All items show their shortcut.

---

## 12. Keyboard navigation

The table is fully keyboard-operable, terminal-grade.

### 12.1 Focus model

- **T63** The frame has a single tab stop (`tabindex=0` on the body
  container, `role="grid"`). Arrow keys move a **cell cursor** (a 2px accent
  focus ring, Draw-in at `fast`, keyboard-only visibility §5.5). Mouse
  interaction never shows the cursor.
- **T64** When the table is not focused, `R` and `T` shortcuts work at the
  page level only if the table is the page's primary instrument; otherwise
  the page's command palette owns letter keys. The table claims letters only
  while focused.

### 12.2 The key map

| Keys | Behavior |
|---|---|
| `↑ ↓ ← →` | Move cell cursor; at row edges, wrap to the next/prev row (grid semantics) |
| `Home` / `End` | First / last cell in the row |
| `Ctrl+Home` / `Ctrl+End` | First / last row |
| `PageUp` / `PageDown` | Scroll viewport by one page; cursor lands on the first fully-visible row |
| `Enter` | Activate: open row detail, commit edit, or expand (contextual) |
| `Space` | Toggle row selection at cursor (checkbox column) |
| `Shift+Space` | Toggle range selection from the anchor row |
| `Tab` / `Shift+Tab` | Leave the grid into the next/prev focusable element (or commit+move in edit mode) |
| `Esc` | Cancel edit / close menu / clear cursor |
| `F2` | Edit focused cell (Registry only) |
| `Ctrl+C` / `Ctrl+Shift+C` | Copy selection / with headers (§11) |
| `Ctrl+A` / `Ctrl+A` again | Visible rows → all filtered rows |
| `Alt+↑` / `Alt+↓` | Jump to sort menu on the focused column header |
| `Menu` | Open context menu at cursor cell |

- **T65** Every shortcut is discoverable from the context menu (shortcut
  labels) and the table's "?" helper in the band (opens a compact shortcut
  sheet). No keyboard feature is undocumented.
- **T66** Cell-cursor movement is animated at `instant` (75ms) with a
  **fading trail**: the ring fades from the previous cell as it Draws into
  the next — the eye tracks the cursor without a hard teleport. Nothing else
  moves.

---

## 13. Virtual scrolling

- **T67** Any table with an expected payload over 500 rows virtualizes
  (windowed rendering, 2× overscan). Virtualization is a frame concern
  (T2), invisible to pages. Non-virtualized tables are capped at 1,000
  rendered rows by policy.
- **T68** Virtualized rows must still FLIP on sort/filter — this is the
  hard problem, and the rule is: *identity keys, not indices*, and FLIP
  measurements only for rows currently mounted. Rows that leave the window
  during a sort simply re-enter at their new position (fade-in at `fast`),
  which reads identically to a full FLIP for the visible set.
- **T69** Scrollbar: overlay-style on desktop (the frame's scrollbar is thin
  — 8px — styled to match, never the OS default clunk). Scroll position is
  preserved on filter/sort *refinement* but reset on *view change*.

---

## 14. Empty, loading, error states

### 14.1 Loading

- **T70** The table's skeleton *is* the table (§13.1 of the design system):
  the frame renders real headers with shimmer rows (4 skeleton rows in
  compact density, 3 in comfortable) using the existing `skeleton-pulse`
  token. **No spinner replaces the table.**
- **T71** A load *within* a populated table (refresh, filter server round
  trip) shows nothing for ≤ 180ms (perceived instant), then a subtle 1-row
  opacity dim of stale rows + the sync-dot animating — never a full skeleton
  for a refinement.

### 14.2 Empty

- **T72** The empty state lives inside the frame (body area, §12.4), not
  as a page-level takeover. Anatomy: a duotone glyph (type-appropriate:
  receipt for payments, roster for students), a one-line title ("No fees
  due"), an optional one-line description with the *active filter* echoed
  ("No rows match the current filters — clear filters"), and a primary
  action (Clear filters / Add first student). It animates in with
  `fade-in-up-lg` at `slow` — the empty state is the moment the table
  becomes a *call to action*.
- **T73** Distinguish: filtered-empty (offers "Clear filters") from
  genuinely-empty (offers the create action). Same frame, different copy.

### 14.3 Error

- **T74** A failed load renders the frame's error state: `danger` tint,
  the error message, and a Retry button. Rows that were already shown stay
  (stale-but-honest beats blank), with a banner above the band:
  "Couldn't refresh — showing data from 2m ago." This is the terminal rule:
  never blank the instrument.

---

## 15. Context menus, tooltips, and overflow

- **T75** Right-click (or `Menu` key) opens the cell/row context menu at the
  pointer, items scoped to the cell's class: Copy family always (§11);
  Edit/Delete only for Registry; "View details" for navigable rows. The menu
  closes on Esc, click-away, or scroll. Opening is a `base` scale+fade at
  the trigger origin (source-aware anchor, §6.1 pattern).
- **T76** Cell tooltips: text/relation cells that truncate show a tooltip
  (full value) on hover after 300ms; numeric/amount cells show their
  **precise value** (raw ₦12,400.00 vs displayed ₦12,400). Status cells
  tooltip their meaning ("Overdue 14 days"). Tooltips never appear on cells
  that aren't truncated — a tooltip is a promise of hidden content.
- **T77** Multi-line cells (notes, addresses) render at one line and expand
  in place on hover-with-delay (a `fast` height FLIP) or via row expansion —
  they never make the row taller on hover (hover must not change layout,
  §5.5).

---

## 16. Motion summary (the complete table state machine)

Every state from the motion spec §5.5, bound to the table:

| State | Rule | Duration / curve | Never |
|---|---|---|---|
| Row hover | `ink.50` wash (light) / `ink.800 @ 60%` (dark); actions ghost icons fade in at 60%→100% | `fast` (120ms), standard | Scale; box-shadow per row; layout change |
| Header hover | `ink.50` wash on the header cell; sort arrow brightens | `fast` | Underline the whole header |
| Press | Header/row press = `ink.100` wash; no scale | `instant` (75ms) | Scale on dense rows (cells shift) |
| Focus (cursor) | 2px accent ring Draws into the target cell; previous ring Fades | ring `base`, trail `instant` | Ring on mouse interaction; transform |
| Disabled | No response of any kind; opacity 45% | 0ms | Hover/press/focus feedback |
| Selected | Accent wash morphs in; check Draws | wash `base`, check Draw | Pop/bounce; flash |
| Dragging (resize) | 1:1 seam tracking; no easing during drag | release settle ≤ 300ms spring | Easing mid-drag; drop without settle |
| Expanded | FLIP container growth; contents stagger 20ms | container `slow`, stagger ≤ 150ms | Animating height directly; contents sliding |
| Sort / filter / density | FLIP reorder of surviving rows; exits fade + 4px; enters fade | `fast`–`slow` per operation, emphasized-decelerate | Jump-cut reorders; re-mount skeletons; any loop |
| Live arrival | FLIP insert + decaying status wash | `fast`, wash decays 1.6s | Repeating animation; moving the whole table |
| Copy | Nothing moves; toast confirms | — | A sweep/dance over the selection |

**T78 — the table's golden motion rule:** a table's rows may move for exactly
three reasons — because they *changed order* (FLIP), because they *changed
state* (wash), or because the user *moved them* (drag). Everything else is
stillness.

---

## 17. Accessibility

- **T79** The frame is `role="grid"` with `aria-rowcount`/`aria-colcount`
  (virtualized counts are exact), row/column headers wired, and
  `aria-selected`, `aria-expanded`, `aria-sort` maintained. The cell cursor
  is a real focus target (`tabindex=0` on the active cell, `-1` elsewhere).
- **T80** Status is never color-only: pills pair color with a glyph (✓, !,
  …) or text; the status wash (T50) is accompanied by an `aria-live=polite`
  region announcing row insertions/changes in the footer (announced as
  "Payment received — 12 rows updated", not cell coordinates).
- **T81** All motion respects the three tiers (`precise` / `efficient` /
  `minimal`, motion spec §2): the `minimal` tier renders the table with zero
  transform/fade animation — state changes still update instantly, FLIP
  becomes instant jump-cut, and the cursor trail is disabled. The table is
  fully operable in every tier; motion is garnish, never the mechanism.
- **T82** Focus is never trapped in the table itself (only dialogs trap);
  Tab exits to the next control. Keyboard-driven column resize (`Alt+←/→`
  while focused on a header) moves in 8px steps with a live value readout.

---

## 18. Responsiveness (desktop-first, graceful floor)

The app is desktop-first; the table's floor is "usable on a 1280px laptop":

- **T83** Below 1024px: column count is capped via a **responsive column
  set** defined per view (identity + 3 data columns + actions); hidden
  columns are reachable from the column menu, never dropped. The filter rail
  wraps to two rows.
- **T84** Below 768px (the app's mobile floor): the table degenerates to
  **cards** — the same frame renders each row as a card (identity header,
  key-value body, actions row) with the filter rail above. This is a *mode
  of the same component*, not a second implementation, and it inherits every
  rule above (selection, bulk bar, empty states, live updates).
- **T85** Resizing the window re-fits flex columns via FLIP at `fast`; the
  resize seam never appears mid-window-drag (layout settle waits for the
  resize to end).

---

## 19. Implementation map (for the build that follows)

The spec is deliberately buildable on the existing codebase (one `Table`
component, ~50 call sites, no grid library dependency to add).

### 19.1 Component architecture

```
components/ui/table/
  frame.tsx          ← the instrument: band, body viewport, footer, virtualization
  columns.tsx        ← type system: renderers, widths, alignment (T7)
  header.tsx         ← sort, resize handles, facet menus, pin seams, column menu
  filter-rail.tsx    ← search box, chips, query language, saved views
  selection.tsx      ← checkbox column, anchor/range state, bulk action bar
  cursor.tsx         ← cell cursor, key map, keyboard controller
  row.tsx            ← identity, hover/selected/attention states, expansion FLIP
  states.tsx         ← skeleton / empty / error frames
  index.tsx          ← <DataTable class="registry|ledger|register" … />
```

Existing call sites migrate column-by-column from inline `render` closures to
the type system (T7) — this is the same PR-by-PR pattern as the analytics
chart wrapper migration. Order: (1) frame + types with zero visual change;
(2) header (sort/resize/pin) behind the current pagination; (3) filter rail;
(4) selection + bulk bar; (5) keyboard cursor; (6) virtualization; (7)
saved views; (8) ledger-only copy/paste.

### 19.2 Reuse

- FLIP: the shipped `useFlipList` / `flipElement` hooks (§9 motion spec) are
  the sort/filter/density/expansion engine.
- Tiers: the `useMotionTier` hook gates all motion (T81); `useMove` drives
  the cursor trail, bulk-bar slide, and chip/chrome transitions.
- Status language: pill badges, delta chips, and the decay-wash token come
  from the v3 palette; nothing new is invented at the component level.

---

## 20. Acceptance criteria

A table passes review when:

1. **Scan:** a ledger's most important column can be read at a glance — 5
   rows of a fee ledger read faster than the same data in cards.
2. **Three gestures:** any row reachable from any filter state in ≤ 3
   actions; any bulk op ≤ 2 actions after selection.
3. **No bespoke cells:** zero page-authored cell renderers with ad-hoc
   styling remain (T7).
4. **No layout motion:** no state change ever resizes a row or shifts a
   neighbor (M3, §5.5).
5. **Keyboard-complete:** every action in the context menu has a shortcut
   and the full key map works in all three tiers.
6. **Stable under load:** 10,000-row ledgers scroll at 60fps on a mid-range
   laptop with virtualization on; sorting a 10,000-row table reads as FLIP,
   not a jump.
7. **Accessible:** the grid passes axe with zero color-only status
   violations; the cursor is reachable by keyboard only.
