# Visual Polish Review — SDMAS v3 Implementation, Audited Against the v4 Bar

**Spec:** VISUAL_POLISH_REVIEW_V4 · **Version:** 4.0.0 · **Status:** Audit
**Applies to:** apps/web (implementation) · **Reads against:** DESIGN_SYSTEM_V3, the v4 spec family (Gloss, Corridor, Escapement, Bridge, Atlas, Quill, Vestibule)

> The goal is not to make it beautiful. The goal is to make every interaction feel *premium* —
> a desktop-grade product, not a traditional ERP. This review audits what is **actually shipped**
> (source-level, token-level, contrast-verified), names what is already right, and gives a
> prioritized, impact-scored, before/after plan to close the gap.

---

## 0. Methodology & scope

- **Source audit:** the design-token file (`src/index.css`), 10 UI primitives (Button, Card, Input,
  Select, Modal, Badge, Skeleton, EmptyState, ErrorState, PageHeader), the shell (Sidebar, Header,
  AppLayout), and the hero screens (Dashboard, Login, Risk Center, Approval Inbox, Student List).
- **Contrast audit:** every text token pair measured against WCAG 2.1 AA (script-verified, values below).
- **Motion audit:** keyframe catalog, entrance choreography, FLIP usage, reduced-motion gate.
- **Interaction audit:** focus rings, hover/pressed/disabled states, keyboard coverage, empty/loading/error flows.
- **Explicitly out of scope:** backend, data model, feature work, the v4 specs themselves (those are
  the destination; this review is the map from where the code is today).

**Scores (1–5, 5 = premium):** Hierarchy 3 · Spacing 3 · Typography 3 · Contrast 2 · Alignment 3 ·
Consistency 2 · Density 3 · Iconography 3 · Animation 4 · Accessibility 3 · Interaction 3 ·
Loading 3 · Error handling 2 · **Overall: 2.9/5 — "solid, not premium."**

---

## 1. What is already right (keep, don't touch)

1. **The token foundation is genuinely strong.** Editorial type scale, warm surfaces, a single
   electric accent with correct restraint, a complete motion-token family, and accessible focus
   states — this is the v3 identity and it reads premium.
2. **The sidebar is the best surface in the product.** Deep-navy rail, active indicator with the
   `animate-active-indicator` flourish, RailLabel/slide choreography, collapse-to-rail with
   motion tokens — already at the v4 bar.
3. **Motion discipline.** The entrance catalog (fade-in-up, scale-in-spring, stagger with
   `animationFillMode: both`) is tasteful, and the **reduced-motion gate is real and complete** —
   `0.01ms` kill-switch plus per-animation `motion-reduce` variants. Better than most products.
4. **The modal is a11y-proficient.** Escape, focus-return, overlay-click, aria-modal, labeled title.
5. **The shared primitives carry the brand consistently** — Button, Card, Badge, Input all use the
   same token grammar. The *exceptions* are the problem (below).

---

## 2. The findings — by dimension

Legend: **P** = priority (P0 ship-blocker / P1 this quarter / P2 this year) · **I** = impact
(H/M/L). Before → After per finding.

### 2.1 Contrast & accessibility (the two real P0s)

**F-01 · `--color-text-muted` fails everywhere.**
Contrast (script-verified, WCAG 2.1):
| Token | Light on surface | Light on bg | Dark on surface | Dark on bg |
|---|---|---|---|---|
| `text-muted` `#aeb4c9` / `#434a6e` | **2.06** | **1.90** | **2.04** | **2.24** | FAIL ×4 |
| `text-tertiary` `#868da6` / `#636b90` | **3.29** | **3.03** | **3.36** | **3.71** | AA-large only |

`text-muted` is the *most-used* token for metadata: placeholders, table timestamps, page subtitles
(`PageHeader`), empty-state bodies, sidebar `nav-text` 50%. None of it passes AA.
- **Before:** "Sep 12, 2025" timestamps at 2.06:1 — invisible to low-vision users, cheap-feeling to everyone.
- **After:** remap the hierarchy. `muted` → `#8b92ab` light / `#7d85a8` dark (~4.6:1), and *never* use
  it for text that carries meaning — reserve it for decorative separators and disabled placeholders
  (which WCAG exempts). `tertiary` → `#6b7186` light / `#8a91b5` dark to clear 4.5:1 at small sizes.
- **I: H · P: P0** — one token edit fixes ~200 call sites. Re-verify with the audit script in CI.

**F-02 · Sidebar `nav-text` at 50% on navy is borderline.**
`rgba(255,255,255,0.50)` on `#080c24` ≈ **4.0:1** — passes AA-large only, fails small text. Section
labels at `nav-text/30` ≈ 2.2:1 — decorative, but the collapse button ("Collapse") is interactive text.
- **After:** `nav-text` → 0.62 alpha (≈5.2:1); interactive text never below that. Section labels
  (non-interactive) may stay faint — that's a hierarchy choice, not a reading requirement.

### 2.2 Consistency & drift (the "ERP feel" culprits)

**F-03 · Radius drift: the tokens say one thing, the code says three.**
`--radius-md: 8px` is the Corridor control radius, but: Button = `rounded-[10px]`, Input = `rounded-[10px]`,
Card = `rounded-2xl (16px)`, **Login inputs & Button = `rounded-xl (12px)`**, skeleton = `rounded-lg (8px)`.
- **Before:** the login screen (the first impression!) silently uses a different control radius than
  every other form in the app. Users feel the inconsistency without naming it.
- **After:** one rule — *controls 8px, containers 12–16px, cards 16px, pills full* — enforced via
  tokens (`radius.control`, `radius.card`) and a one-line fix in each primitive. Login inherits the
  shared `Input` instead of hand-rolled markup (it already re-declares focus rings and hover states
  the shared component provides).
- **I: H · P: P0** — zero design risk, instant cohesion.

**F-04 · Page headers are three different products.**
- `PageHeader` (compact, `text-xl/2xl`) used by some list pages.
- Hand-rolled "narrative headers" (`text-3xl/4xl`, eyebrow label, dynamic copy) used by Students,
  Fees, Teachers, Approval Inbox, Risk Center, Dashboard.
- **No header at all** on several inner pages (charts, detail views).
- **After:** one header system with two tiers (default = 28px title + optional eyebrow; compact =
  20px) — the narrative treatment stays only where it earns its height (Dashboard, Risk hero), per
  the Bridge/Atlas page-chrome model. Pick one, make it the component, kill the rest.
- **I: M · P: P1**

**F-05 · Buttons carry shadows; premium buttons don't.**
`primary` has `shadow-sm hover:shadow-md`. Linear/Stripe/Raycast buttons are flat fills — shadow
signals *depth*, but buttons signal *affordance*; the shadow tax makes them feel like bootstrap.
- **Before:** every primary button floats. **After:** flat fill + 1px inner highlight; elevation is
  reserved for overlays, dropdowns, modals — where it already lives (`shadow-xl`).
- **I: M · P: P1** — one class-string change in `button.tsx`.

### 2.3 Visual hierarchy

**F-06 · The Dashboard is doing four jobs at once.**
Hero (navy, greeting, headline, 4 KPIs, 2 buttons) + Attendance Pulse card + Needs Attention column
(4 stacked alert cards) + Quick Navigation (8 tiles) — all above a single fold. Every element
competes; nothing leads.
- **After:** apply the Bridge model — one *scan target* (KPI strip), one *attention zone*, and let
  Quick Navigation collapse into the sidebar/palette (it duplicates navigation that already exists,
  plus the palette). The hero shrinks to a greeting line; the gradient stays for the Command Center,
  not the default dashboard.
- **I: H · P: P1**

**F-07 · Zebra rows fight the surface hierarchy.**
Tables use `bg-[var(--color-bg)]/40` zebra + full borders + hover tint. Three competing
row-separators on one screen.
- **After:** hairlines only (`divide-y`), zebra off by default, hover tint alone signals the row.
  (TABLE_SYSTEM_V3 already defines this grammar — the pages just don't all use it.)
- **I: M · P: P1**

**F-07b · Numeric column headers misalign with their cells.**
`frame.tsx` renders every header `text-left` unless the column declares explicit alignment — so a
right-aligned amount cell sits under a left-aligned "Amount" header. The classic ERP tell, and the
reason this audit's alignment score is a 3.
- **After:** untyped headers inherit the resolved cell alignment (`resolveColumnAlign`), so numeric
  columns align header-to-cell by default; explicit alignment still wins. One line in the frame.
- **I: M · P: P1**

### 2.4 Density & spacing

**F-08 · Desktop pages are stretched to mobile spacing.**
Content wrapper `p-8 max-w-[1400px]` + `space-y-8` + table rows at `py-3.5` = an airy, low-information
density. Great for marketing sites; wrong for an ERP where staff live in tables.
- **After:** page gutters `24–32px` on desktop (keep 16px mobile), `space-y-6`, default table row
  height 44px with an explicit `compact` 36px tier for ledger/register tables (already wired in
  `frame.tsx` via `TableClass` — flip the default). Offer a global density toggle (comfortable/compact).
- **I: H · P: P1**

**F-09 · `space-y-8` between sections is a rhythm, not a system.**
Some pages use `space-y-8`, others `space-y-6`/`space-y-5`; cards use `gap-3`/`gap-4`/`gap-6`
arbitrarily. Vertical rhythm is the cheapest premium signal and it's inconsistent.
- **After:** codify a spacing scale for sections (48px between major blocks, 24px within, 8px between
  stacked metadata) as tokens; grep for out-of-scale values.
- **I: M · P: P2**

### 2.5 Typography

**F-10 · Table numbers don't use tabular figures.**
Body sets `font-feature-settings: 'cv02','cv03','cv04','cv11','liga'` but not `tnum`. KPIs and fee
columns jitter as they count up / paginate.
- **After:** add `'tnum'` to the body feature set; add `tabular-nums` to all numeric cells and KPI
  readouts (the `AnimatedCount` components already animate; they should never jitter).
- **I: M · P: P1** — one token + one utility per numeric column.

**F-11 · `PageHeader` subtitle at `text-muted` is unreadable metadata (F-01's worst victim).**
Subtitle carries the page's context ("Manage student records") and it's at 2:1. Fixes with F-01, but
call it out: after the token fix, re-verify `PageHeader`, empty-state bodies, and table cell metadata
specifically.

### 2.6 Iconography

**F-12 · Stroke-width inconsistency.**
Icons across the app mix `strokeWidth={1.5}` and `strokeWidth={2}` with no rule; login uses
`rounded-xl` icon tiles while the rest of the app uses `rounded-lg`/`rounded-xl` arbitrarily.
- **After:** a single icon contract — 24px grid, `strokeWidth 1.5` for chrome/metadata, `2` for
  interactive affordances (arrows, chevrons, close), 2px weight diff, one tile radius.
- **I: L · P: P2**

### 2.7 Animation & interaction quality

**F-13 · Row entrance animations replay on every data change.**
`frame.tsx` gives every row `animate-fade-in` with per-index delay; on filter/sort/pagination the
whole body re-animates. It's the one motion that *costs* instead of *communicates* (and it fights
the FLIP exit choreography already in place).
- **After:** animate rows only on *mount* (first data arrival); on filter change use FLIP + exit
  fade (already implemented) and snap the survivors. The Escapement's rule — motion is for change,
  not for every render.
- **I: M · P: P1**

**F-14 · The dashboard re-plays count-ups on every visit and navigation.**
`AnimatedCount` (1000ms) runs on mount each time — including on theme toggle and route return. The
first experience is premium; the tenth is noise.
- **After:** count-up on first data arrival per session (or per page-visit when data actually
  changes); subsequent renders show the number instantly. One session-scoped flag.
- **I: L · P: P2**

**F-15 · Disabled buttons hide rather than explain.**
`disabled:opacity-45` is the only signal. For permission-gated actions (e.g. "Save" while a required
field is empty), premium apps say *why* — a disabled state plus a hint or tooltip.
- **After:** keep opacity-45 for true no-ops; add `aria-disabled` + a "why" tooltip for gated
  actions (the Quill spec's inline-validation contract covers the form half).
- **I: L · P: P2**

### 2.8 Loading experience

**F-16 · Skeleton system exists but isn't used everywhere — and the Dashboard hand-rolls it.**
`Skeleton`/`TableSkeleton`/`PageSkeleton`/`KPISkeleton` exist and are good, but: the Dashboard's
loading state is inline `bg-[var(--color-border)]` blocks (not the components), and several list
pages show blank tables or bare `Loading` spinners.
- **After:** every list/dashboard page routes through the skeleton family; the Bridge §9
  content-shaped skeleton (zero CLS, shimmer) becomes the default; the Dashboard uses `KPISkeleton`
  + `CardSkeleton`.
- **I: M · P: P1**

**F-17 · No progress granularity on slow fetches.**
All fetches show one state. A 3-second table load shows the same skeleton as a 300ms one.
- **After:** skeleton → (slow-request threshold 800ms) → progress hint ("Still loading…") or
  cancel/retry affordance. Cheap, humane, premium.
- **I: L · P: P2**

### 2.9 Error handling

**F-18 · Dashboard errors retry by reloading the page.**
`onRetry={() => window.location.reload()}` — a full reload when a refetch would do.
- **After:** `ErrorState` already has `onRetry`; wire it to refetch (the page already owns the
  fetch). Reload is the last resort, never the first.
- **I: M · P: P1**

**F-19 · Empty states are ad-hoc and inconsistent.**
The EmptyState component is good; usage isn't: `"No data"` defaults in tables (`frame.tsx`
`emptyMessage = 'No data'`), hand-rolled "No findings" (Risk), "All caught up!" (Approval Inbox) —
three different treatments of the same moment. (Vestibule owns the full fix; this review just
scores the current state.)
- **After (quick):** point the two hand-rolled states at `EmptyState`; change the table default to
  a domain-aware message. Full system per EMPTY_STATES_V4 W1.
- **I: M · P: P1**

**F-20 · Chart empties say "No data" and stop.**
Every chart's empty state is `<EmptyState title="No Data" description="…not available.">` — no
action, no explanation of what would make it appear.
- **After:** Bearing-moment copy per Vestibule §6.2 ("Widen the date range", "Record attendance")
  — one CTA, no dead ends.
- **I: M · P: P1**

### 2.10 Interaction quality & affordance

**F-21 · Hover is translate + shadow everywhere; it should be contextual.**
Cards lift (`-translate-y-0.5`), alert cards lift, nav tiles lift. Lift is one tool; applying it to
every tappable surface flattens the hierarchy (and 20+ hover-lift rules already in motion-safe).
- **After:** lift only the *primary* path (main CTA, primary card). Secondary surfaces respond with
  border-tint or background — the Gloss hover taxonomy (T-family), which the codebase already cites.
- **I: M · P: P2**

**F-22 · The header's left side is empty dead space.**
`justify-between` with an empty left group — the product identity (brand, campus, breadcrumb) has no
place on the primary chrome.
- **After:** put the current page's breadcrumb trail (Atlas §6) or the active campus/context there;
  a 60px bar with a single right-aligned cluster reads unfinished.
- **I: L · P: P2**

---

## 3. The priority table — what to do first

| # | Finding | Fix | Priority | Impact | Effort |
|---|---|---|---|---|---|
| 1 | F-01/F-11 | Contrast tokens: `muted`/`tertiary` remap | **P0** | H | S (2 files + CI script) |
| 2 | F-03 | Radius tokens + login adopts shared Input | **P0** | H | S |
| 3 | F-05 | Buttons: flat, no shadow | P1 | M | S |
| 4 | F-08/F-09 | Density: gutters, row heights, spacing scale | P1 | H | M |
| 5 | F-04 | One page-header system (two tiers) | P1 | M | M |
| 6 | F-13 | Table rows animate on mount only | P1 | M | S |
| 7 | F-06 | Dashboard: Bridge zones, KPI strip leads | P1 | H | M |
| 8 | F-16/F-18 | Skeletons everywhere; errors refetch | P1 | M | M |
| 9 | F-19/F-20 | Empty states: one component, no dead ends | P1 | M | S |
| 10 | F-07 | Tables: hairlines, no zebra | P1 | M | S |
| 11 | F-02 | Sidebar nav-text alpha | P1 | M | S |
| 12 | F-10 | Tabular numerals for numbers | P1 | M | S |
| 13 | F-12/F-14/F-15/F-17/F-21/F-22 | Icon contract, count-up gating, disabled affordance, slow-progress, contextual hover, header breadcrumb | P2 | L–M | M |

**Quick math:** P0 + P1 = 13 fixes; 8 are S-sized (one file each). The first two days of work
(token contrast + radius + buttons) remove the three things that make the app read as "ERP".

---

## 4. Before / after — the three moments that define "premium"

**The login screen.**
*Before:* hand-rolled inputs (12px radius, custom focus ring), floating shadow button, brand panel
strong but the form panel generic. *After:* shared `Input` grammar (8px radius, ring-2 focus), flat
primary button, form panel with a quiet surface treatment — the first frame reads designed, not default.

**The dashboard.**
*Before:* four competing zones, re-playing count-ups, border-heavy cards. *After:* a KPI strip that
leads, one attention zone, quick nav moved to the sidebar/palette, count-ups once per session,
hairline cards. The 8-second scan (Bridge §7.1) becomes possible.

**The list page (Students, Fees, …).**
*Before:* `text-3xl` narrative header + zebra rows + `p-8` gutters + re-animating rows + "No data"
empty. *After:* 28px header with eyebrow, hairline rows with hover-only signal, 24–32px gutters,
mount-only animation, a Bearing/Genesis empty state with one CTA. Same data, *twice* the information
density, zero clutter.

---

## 5. Implementation roadmap

| Wave | Scope | Exit criteria |
|---|---|---|
| **W1 · Contrast & radius (2–3 days)** | F-01/F-02/F-03/F-11: token remap + CI contrast script (from `scripts/contrast-audit.js`, kept and promoted deliberately — it is the acceptance gate, not a throwaway); radius tokens; login → shared Input | All text tokens ≥ 4.5:1 (script-gated); one radius language |
| **W2 · Buttons & chrome (2 days)** | F-05 flat buttons; F-04 header system; F-22 breadcrumb slot | One button treatment; one header component; header left side has a purpose |
| **W3 · Density & tables (3–4 days)** | F-07/F-08/F-09/F-10: gutters, row heights, spacing tokens, tabular figures | Desktop pages hit target density; numbers stop jittering |
| **W4 · Dashboard & motion (3–4 days)** | F-06 Bridge zones; F-13 mount-only rows; F-14 count-up gating; F-21 hover taxonomy | Dashboard = one scan target; motion replays only on real change |
| **W5 · States (3 days)** | F-16/F-17 skeletons everywhere; F-18 refetch errors; F-19/F-20 empty states | No bare spinners, no reload-on-error, no "No data" dead ends |
| **W6 · Hardening & regression (ongoing)** | F-12/F-15; visual regression suite (light/dark, all sizes); a11y pass | The polish holds; PRs can't regress contrast/radius/density |

**Sequencing rule:** W1–W2 are the "read premium at a glance" fixes (tokens + chrome). W3–W4 are the
"feels like a tool, not a brochure" fixes (density + behavior). W5 is "never a dead end". W6 keeps it true.

---

## 6. Acceptance criteria

1. **Contrast is script-gated:** all text tokens ≥ 4.5:1 on their surfaces, both themes; the audit
   script (this review's `scripts/contrast-audit.js`, promoted into CI) fails otherwise.
2. **One radius language:** controls 8px / cards 16px, tokenized; no page overrides (login verified).
3. **One header system:** two tiers, no ad-hoc page headers outside Dashboard/Risk heroes.
4. **Premium density:** desktop list pages show more rows per viewport than today; a density toggle
   exists; numbers use tabular figures.
5. **Motion only for change:** rows animate on mount; count-ups once per session; hover = contextual.
6. **No dead ends:** every empty state has a working action; every error retries by refetch; every
   loader is a shaped skeleton.
7. **Dashboard = Bridge:** one scan target, one attention zone, no duplicated navigation.
8. **Alignment is a rule, not an accident:** numeric column headers inherit cell alignment by
   default (F-07b); no left/right misalignment in any shipped table.
