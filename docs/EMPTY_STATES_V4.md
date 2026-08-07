# Empty States — The Moment Before Something Happens

**Spec:** EMPTY_STATES_V4 · **Codename:** *The Vestibule* · **Version:** 4.0.0 · **Status:** Design
**Applies to:** apps/web · **Family:** v4 design system (Gloss tokens, Corridor anatomy, Escapement motion, Atlas nav, Bridge dashboard, Quill forms)

> A school information system is, at its heart, a record of *intent*. Empty states are the product's
> answer to the first question every new user asks in every module: **"What happens now?"**
> This spec makes that answer a designed, premium, action-forward moment — never a dead end.

---

## 0. What is wrong with empty states today

The current system is one component (`components/ui/empty-state.tsx`) used ~30 ways:

| Problem | Evidence | Consequence |
|---|---|---|
| **One shape for every situation** | A single `EmptyState` with `title/description/action/icon/compact`. First-run, post-filter, and post-completion empties are indistinguishable. | Users can't tell "nothing exists yet" from "your filter matched nothing" — so they retry the wrong thing or leave. |
| **"No data" is a dead end** | Generic copy (`title="No data"`), and `contextualMessages` only maps 9 domains; `getEmptyState(domain)` silently falls back to `data` (`"No data found — The data you are looking for is not available yet."`). | The single most common empty copy in the product is a lazy placeholder. The premium bar: *never* show "No data". |
| **One action, no reasoning** | `action` is a single button. No secondary actions, no suggested paths, no "why does this matter", no template, no shortcut hint. | The user must know the next step themselves — the opposite of guidance. |
| **Filter-empty is undifferentiated** | Pages build their own ad-hoc filter-empty states (e.g. `risk-center.tsx` success-tinted "No findings", `approval-inbox.tsx` "All caught up!") with inconsistent tone and copy. | Two of the best moments in the product are hand-rolled and unrepeatable. |
| **No illustration system** | Icon is a `defaultIcons` stroke-path map, drawn at 28px. No domain art, no composition, no depth. | Empty states read as errors, not invitations. |
| **No onboarding, no templates, no setup** | Nothing in the codebase supports first-run checklists, template galleries, or quick setup. | First-run users face a blank module with a single "+ Add" button and no map of the work ahead. |
| **No AI suggestions** | Zero surfaces for intelligence ("the machine" knows what's missing — no student import, no academic year, no first class). | The product with an intelligence layer never uses it to answer "what now?". |

**The bar:** every empty page should *encourage action* — name the next step, make it one keystroke away, and make the moment itself feel considered.

---

## 1. Thesis — emptiness is a product surface, not a fallback

**The premium bar for an empty state is: it disappears by being used.** The best empty state is the one
that converts — the visitor becomes a creator in one interaction. Everything below serves that:

1. **Name the moment.** First-run ("Start your student directory"), filter-empty ("No matches for this
   filter — here's how to see more"), and done ("All caught up — here's what's next") are *different
   products*. Say which one the user is in.
2. **Lead with the next step.** Copy is imperative and forward-looking: *"Create your first class"* — not
   *"No classes yet"* (a status report reads like a failure; an instruction reads like a path).
3. **One primary action, reasoned secondaries.** Apple's rule (one unambiguous primary action) with
   Linear's practice (suggested paths for complex domains). A single button for creation; up to three
   contextually-reasoned alternatives below it.
4. **Illustration signals domain, never content.** Soft line art that says *"this is where students will
   be"* — quiet, on-token, motion-restrained. It is the *room*, not the *furniture*.
5. **Calm over clever.** Entrance is a short, single-purpose composition (fade + 4px rise + stagger).
   No ambient loops. Reduced-motion is first-class, not an afterthought.
6. **Emptiness is data.** The state knows *why* it's empty (no rows? filter? permission? not-yet-configured?)
   and the registry that describes the domain also describes the emptiness. One source of truth.

**Sister spec:** the Bridge (§5 widget lifecycle) and the Quill (§4 progressive disclosure) both already
say "empty is a designed state." This spec owns *the moment itself* — anatomy, copy, art, actions, onboarding.

---

## 2. Sources & extraction — principles only

| Source | Principle extracted |
|---|---|
| **Notion** | Inline CTA as the default mode ("Type / for commands"); template galleries inside the creation surface; collapsible setup checklists that *track progress*; soft, friendly line-art illustrations; custom emoji/tone without clutter. |
| **Linear** | Status-aware empties (fresh view / filtered / archive / search differ); "Create your first issue" verbs; suggested actions + quick setup for complex domains; keyboard-first CTA (⌘K is always reachable); subtle iconography at product fidelity. |
| **Apple HIG** | Explain *what the view is for*; one clear primary action; progressive onboarding (never a config wall); extreme restraint in illustration and motion — monochrome, small, calm. |
| **Google (form/empty conventions)** | "No results" states acknowledge the query and offer a reset/broadening action; empty-after-completion states celebrate and transition forward. |
| **In-product precedent** | `risk-center.tsx`'s success-toned "No findings" and `approval-inbox.tsx`'s "All caught up!" are the best moments already shipped — codify them. |

---

## 3. The taxonomy — five moments, one grammar

Every empty surface in the product is one of five **moment types**. The moment drives copy tone,
illustration density, action set, and animation.

| Moment | When | Tone | Primary CTA | Examples |
|---|---|---|---|---|
| **1 · Genesis** | The module has never had data (first-run). | Invitation, imperative | Create the first record | No students, no classes, no fee structure |
| **2 · Bearing** | Data exists, but this *view* is empty: filter, search, tab, or scope (year/term/class). | Orientation, neutral | Clear/broaden the view | Search no-match, "no fees for this term", "no students in this class" |
| **3 · Zenith** | The work is done (inbox zero, all approved, nothing to fix). | Celebration, quiet confidence | Suggested next thing | "All caught up!", risk center "No findings" |
| **4 · Relic** | Data existed but was removed / archived / will come later (schedule not published, results pending). | Expectation | Wait + subscribe/remind | "Results publish Feb 28", "No timetable yet" |
| **5 · Veil** | Permission or config gates the view (other role's module, academic year unselected). | Explanation | Unlock path (switch role/year, contact admin) | "Select an academic year", "Visible to admins" |

**Grammar rules:**
- **Genesis copy:** `Create your first <thing>` (title) + one sentence on why it matters (body).
- **Bearing copy:** name the constraint + the escape hatch — `No students match "xyz"` + `Clear search` / `Remove filters`.
- **Zenith copy:** positive verb + a *forward* suggestion — `All caught up` + `Review this week's rollups`.
- **Relic copy:** the date/condition of arrival + `Notify me` (if supported) as a secondary.
- **Veil copy:** what is gated + the path to see it — never a lock icon as the whole story.
- **Never** render the generic fallback (`"No data found"`). The registry makes this unrepresentable.

---

## 4. The anatomy

One component grammar, five moments. Full-canvas hero down to inline row — same order, scaled.

```
┌──────────────────────────────────────────────┐
│                                              │
│                 ◆ illustration ◆            │  ← domain art, 96–160px hero / 40px inline
│                                              │
│                 title (18/600)               │  ← imperative, forward-looking
│                                              │
│              body — one sentence             │  ← what lives here + why it matters (max ~2 lines)
│                                              │
│          [  Primary CTA  ]                   │  ← one unambiguous action
│                                              │
│        secondary · secondary · kbd hint      │  ← reasoned alternatives + shortcut (⌘K / N / /)
│                                              │
└──────────────────────────────────────────────┘
```

### 4.1 Sizes

| Size | Use | Illustration | Type | Padding |
|---|---|---|---|---|
| `hero` | Full module / first-run page | 160px, art + soft backdrop | 18px | 96px vertical |
| `card` | Table body, tab pane, section | 96px, art | 16px | 64px vertical |
| `compact` | Chart widget, inline block (Bridge/Quill) | 48px, mark | 14px | 40px vertical |
| `inline` | Row-level, empty sub-list inside a card | 24px glyph | 13px | 24px vertical |

**Fill behavior:** hero/card fill their container (`min-h` rather than fixed height, so cards that
empty and re-fill don't jump — the Bridge FLIP handles the morph). Compact/inline shrink to content.

### 4.2 Copy system (registry-driven)

The current `contextualMessages` map becomes a **copy contract** in the domain registry — every domain
declares all five moments (a domain that can't be "Zenith" simply omits it):

```ts
export interface EmptyCopy {
  genesis: { title: string; body: string }          // "Create your first class"
  bearing?: { title: string; body: string }          // "No classes match this filter"
  zenith?: { title: string; body: string }           // "All caught up"
  relic?: { title: string; body: string }            // "Results publish Feb 28"
  veil?: { title: string; body: string }             // "Select an academic year to view terms"
}
```

**Copy guidelines (normative):**
1. Imperative, positive titles — `Create your first student` over `No students yet`. (The current
   `"No students yet"` becomes `"Create your first student"`.)
2. One sentence body, ≤ ~110 chars, ending in *why it matters*: `"Your student directory is empty.
   Add your first student to begin building your school."` — keep, then tighten.
3. Never "No data", never "Nothing here", never "—". If the writer can't name the thing, the state
   shouldn't render an empty-state copy block at all.
4. Zenith bodies look forward: `"Review this week's attendance rollups."`
5. Relic bodies carry the condition: `"Published by the class teacher after the term closes."`
6. Escape hatches are verbs, not nouns: `Clear search`, `Remove filters`, `Change year`.

---

## 5. Illustrations — the room, not the furniture

### 5.1 System

A **token-driven line-art system**, not hand-drawn per-module assets:

- **Base:** 24px grid, 1.5px stroke, rounded line-caps, `currentColor` — monochrome, tinted by
  `color.muted` on surface. (Apple restraint; Linear fidelity; Notion friendliness.)
- **Composition:** the domain's *icon motif* (existing `defaultIcons` glyphs are the seed) set inside a
  **soft container**: a rounded tile (radius `corner.lg`) with a tinted wash
  (`accent.subtle` / `muted`), or — for hero only — a 3-layer depth stack
  (back tile → mid silhouette → foreground motif), all flat, all CSS, no raster.
- **Palette:** two tokens only — `--color-muted` for the art + the surface-wash token for the tile.
  Dark/light come free. No gradients in illustrations (gradients live in heroes/charts, not in
  empty states).
- **Signal rules:** Genesis = art + tinted wash (invitation). Bearing = art at 60% opacity, no wash
  (neutral). Zenith = the domain motif swapped for a success mark (check in circle) at muted tint.
  Relic = motif with a small clock/calendar badge. Veil = motif at 50% opacity behind a subtle
  scrim line — the lock is told, not drawn.

### 5.2 Delivery

- Illustrations are **inline SVG components** (no network requests, tree-shakeable), one file per
  domain under `components/empty/art/` (`students-art.tsx`, `fees-art.tsx`, …), each exporting the
  four scales from one path definition (viewBox-scaling, no duplicates).
- A `EmptyArt` registry maps `domain → art component`, so the 9 existing `defaultIcons` domains get
  art immediately and new domains opt in.

---

## 6. Actions — one primary, reasoned secondaries

### 6.1 The action model

```
EmptyStateActions
├── primary   { label, onClick }                 // the single unambiguous step (or command)
├── secondary { label, onClick | to, icon? }[]   // ≤3: alternative creation path, template,
│                                                //   import, "Notify me", "View guide"
└── hint      { keys: string[], label }?         // keyboard path: ⌘K, N, /, or G then key
```

**Rules:**
1. **Every moment has a primary.** Genesis: create. Bearing: escape hatch (clear filters). Zenith: the
   best next thing (review / create / plan). Relic: the wait action (notify) — or a button to the
   publishing surface if the viewer is the publisher. Veil: the unlock (select year / switch role).
2. **Secondary actions are reasoned, not decorative.** For Genesis with multiple viable first steps
   (Linear's multi-path rule): e.g. Students → primary *Add Student*, secondaries *Import from
   spreadsheet*, *View templates*, `N`. For complex domains, one secondary may open the **quick-setup
   checklist** (§7) instead of a second create path.
3. **Keyboard is always visible — and always honest.** If the primary maps to a shortcut, the `hint`
   renders it as a `kbd` chip next to the CTA. A hint renders **only when the page actually binds that
   key** (resolved from the Atlas shortcut registry, like the sidebar's `useKeyboardShortcut`):
   student-list binds `N`, so its empty state advertises it; a page that doesn't bind a key advertises
   nothing. Empty states never advertise dead shortcuts.
4. **The CTA and the palette are the same command.** Primary CTAs resolve from the nav-registry's
   `NavCommand` surface (via its `run → action` palette seam), so *⌘K → "Add Student"* and the
   empty-state button execute one implementation. When the CTA opens a creation form, it is the Quill
   model (`FormModel` for that domain) — an empty state can pass a template prefill (§7.2) straight
   into the form's smart defaults.
5. **Never ship an action that fails.** CTAs run the same creation surface as the header button
   (the page's existing `openCreateModal` etc.) — no empty-state-only dead buttons.

### 6.2 The five examples from the brief

| Brief example | Moment | Title | Primary | Secondaries | Hint |
|---|---|---|---|---|---|
| **No students** | Genesis | Create your first student | Add Student | Import from spreadsheet · View templates | `N` |
| **No attendance** | Relic | Attendance begins with today's roll call | Take attendance | See how attendance works | `/` |
| **No reports** | Genesis | Generate your first report | Create report | Explore report templates | `⌘K` |
| **No charts** | Bearing | No data for this range | Widen date range | Clear filters | — |
| **No fees** | Genesis | Set up your fee structure | Create fee type | Import fee structure · View guide | `N` |
| **No books** | Genesis | Start your library | Add first book | Import catalog · Browse templates | `N` |

*Hints are conditional: each renders only where the page actually binds that key (§6.1 rule 3); `⌘K`
(the Atlas command surface) is the only universally available hint.*

---

## 7. Quick setup & templates

### 7.1 Quick setup (Linear's "get started in minutes")

For setup-heavy domains (academic structure, fees), Genesis renders a **setup card** beneath the CTA —
a collapsible, progress-tracked checklist (Notion's collapsible activation checklist):

```
Setup your school's academic structure     [ 3/5 · Continue  ]
✓ Create an academic year
✓ Add your classes
✓ Create sections
○ Assign teachers
○ Enroll students
```

- The checklist lives in the **domain registry** (`setupSteps: SetupStep[]`, each `{ id, label,
  to?, command? }`), shared with the Bridge's *Today's priorities* — setup is the first priority.
- Checking a step **removes it** (Notion pattern): the checklist shrinks, the module content grows.
  Completed = the empty state retires, not scrolls.
- Progress persists (`localStorage`, keyed per domain × campus — same storage family as
  `use-nav-persistence`).
- If the user can complete the whole setup in one sitting, offer `Complete all` (runs steps in order,
  jumping via routes or the command surface).

### 7.2 Templates

- A **template gallery** opens from the secondary action *View templates* (Notion's gallery-in-place):
  a dialog (`dialog` component) of 3–6 domain templates, each a one-line preview + `Use template`
  that pre-fills the creation form (e.g. a starter fee structure, a term with default holidays).
- Templates are **data, not screens**: `{ id, name, description, payload }` where payload is the
  prefill for the existing create form. W1 ships the empty-state surfaces; templates are W4.

---

## 8. AI suggestions — the machine answers "what now?"

The product already has an intelligence layer (risk findings, detectors) and an API-first core. The
empty state is the one surface where intelligence is *most* valuable: the user is asking "what's next"
and the machine knows the school's state.

- **Genesis:** the registry's `suggest: (ctx) => Suggestion[]` hook (server-side, best-effort) can
  answer with domain-relevant setup hints: `No academic year for 2026–27 — create it to start
  enrolling.` Rendered as a single-line suggestion card under the secondaries (`A gentle suggestion`
  label, dismissible, `Learn why` tooltip — attributable, per the intelligence layer's explainability
  contract).
- **Bearing:** suggest broadened constraints: `12 students match the current year — show all years?`
- **Zenith:** suggest the next unit of work: `All caught up — generate this term's report cards.`
- **Failure is quiet:** suggestions are advisory only — never block the primary CTA, never ship on
  error, always attributable (`Because: …`).
- **Scope:** W6, after the registry and the Quill's smart-default plumbing are in place.

---

## 9. Progressive onboarding — the journey into the product

### 9.1 The activation ladder

Emptiness is a *sequence*, not a state. The product should guide a new school from zero to useful in
one sitting, using the empty surfaces themselves:

1. **Landing (hero page after first login):** the Bridge's dashboard shows its first Genesis moment —
   a *school setup* card (create academic year → add classes → add students → add teachers), which is
   the quick-setup checklist (§7.1) at dashboard scale.
2. **Each module's Genesis** carries its own checklist slot and links back to the ladder:
   `This is step 3 of 5 in your school setup` (breadcrumb-style trail, not a modal).
3. **Completion ceremony:** the first record created (first student, first class) triggers a *quiet*
   zenith moment — a success toast + the module's empty state retiring with a 200ms FLIP into the
   populated table (the Bridge's "data decides" crossfade, not confetti).
4. **Never a config wall:** at most one setup card on screen at a time; checklists collapse; the
   primary create action is always visible above the checklist.

### 9.2 Role-aware onboarding

Portals get tailored ladders from the same registry (`getNavSectionsForRole`'s sibling:
`getSetupForRole`):
- **Admin/principal:** academic structure → staff → students → fees.
- **Teacher:** classes/assignments → first attendance → first grade.
- **Parent/student:** the empty states are almost entirely *Relic/Bearing* (waiting for published
  data) — copy reframes to expectation, and the primary is "Notify me" where supported.

---

## 10. Animation — the moment arrives calm

All motion uses the Escapement tokens (`--motion-fast/slow`, ease curves) and the Gloss catalog.

### 10.1 Entrance (on mount / on filter change)

A single composition, staged by the size:

| Element | Move | Timing |
|---|---|---|
| Illustration | fade + rise 4px (`translateY(4px)→0`) | 220ms, `ease-out`, 0ms delay |
| Title | fade + rise 4px | 220ms, 40ms delay |
| Body | fade | 200ms, 80ms delay |
| CTA + secondaries | fade + rise 4px | 220ms, 120ms delay |
| Setup card / suggestion | fade | 200ms, 160ms delay |

- **Stagger = reading order** (§4.3 of the Gloss), capped at 4 movers.
- **One Z, no loops:** no ambient floating, no pulsing illustration. Calm (Apple), purposeful (Linear).
- **On filter change** (Bearing empties), the illustration **does not re-animate** — only the copy
  crossfades (200ms). The user changed the constraint, not the room.
- **Reduced motion:** `prefers-reduced-motion` → single 120ms opacity crossfade, no rise, no stagger.
  This is a token, not a media-query afterthought (the v4 motion spec's contract).

### 10.2 Exit / retirement

- Empty → data: the empty block FLIPs out over 220ms while the table fades in (the Bridge's
  per-widget crossfade). Never an abrupt swap.
- Checklist item completion: the row fades/collapses 160ms; if it was the last item, the whole setup
  card exits 220ms.

### 10.3 Micro-interactions

- CTA hover/pressed: the shared button tokens (no custom behavior).
- Secondary action hover: arrow nudges 2px East (Gloss, directional hint).
- Suggestion card: `Learn why` expands an inline tooltip (160ms); dismiss fades the card 200ms.
- Illustration: hover does **nothing** (it is not a control). If art carries a badge (Relic clock),
  the badge may gently appear at 200ms on mount only.

---

## 11. Performance

- **Inline SVG only** — no raster, no fetch, no font downloads for art. Illustrations are
  tree-shaken per domain.
- **Zero CLS:** every empty surface reserves its container (`min-h` on hero/card sizes); empty↔data
  swaps animate, so no layout jumps.
- **Budget:** entrance composition ≤ 4 animating nodes, all transform/opacity only; setup checklist
  and suggestion render below the fold of the state, no paint cost until visible.
- **Memory:** empty states mount/unmount with their page (no lingering timers; entrance uses CSS
  animations with `animation-fill-mode: both`, matching the codebase's existing pattern in
  `risk-center.tsx`).
- **Testing:** the existing `components.test.tsx` EmptyState suite extends to cover all five moments
  and four sizes; a visual regression file per size × moment (light/dark).

---

## 12. Architecture — files & APIs

### 12.1 Component system

```
apps/web/src/components/empty/
├── empty-state.tsx          // <EmptyState> — moment/size/tone driven, registry-backed
├── empty-art/
│   ├── index.ts             // <EmptyArt domain size>
│   └── <domain>-art.tsx     // students-art, attendance-art, fees-art, academic-art, …
├── empty-actions.tsx        // primary + secondaries + kbd hint (button tokens)
├── setup-checklist.tsx      // §7.1 progress-tracked checklist
├── template-gallery.tsx     // §7.2 in-place gallery dialog
├── suggestion-card.tsx      // §8 AI suggestion, dismissible + attributable
├── use-empty-state.ts       // moment resolution + telemetry hook
└── registry.ts              // EmptyCopy / SetupStep / Suggestion / moment types
```

### 12.2 The registry

```ts
export type EmptyMoment = 'genesis' | 'bearing' | 'zenith' | 'relic' | 'veil'
export type EmptySize = 'hero' | 'card' | 'compact' | 'inline'

export interface EmptyStateConfig {
  domain: string                       // matches the existing DomainContext keys
  art: ComponentType<{ size: EmptySize }>
  copy: Partial<EmptyCopy>             // per-moment copy contract (§4.2)
  actions: {
    genesis?: { primary: Cta; secondary?: Cta[] }        // Cta = {label, onClick|to, icon?, kbd?}
    bearing?: { primary: Cta; secondary?: Cta[] }        // escape hatch first
    zenith?: { primary: Cta; secondary?: Cta[] }
    relic?: { primary: Cta; secondary?: Cta[] }
    veil?: { primary: Cta; secondary?: Cta[] }
  }
  setupSteps?: SetupStep[]             // §7.1 (Genesis only)
  templates?: Template[]               // §7.2
  suggest?: (ctx: EmptyContext) => Promise<Suggestion[]>   // §8, server-side, best-effort
}
```

`EmptyContext` carries `{ role, campusId, moment, query?, filters?, year? }` — everything a
server-side suggestion or an action needs.

### 12.3 Backward compatibility

- `<EmptyState>` keeps its existing props (`title, description, action, icon, compact`) as a
  **compat layer** that maps onto the new anatomy (moment=genesis, size=card, single primary).
  Existing ~30 call sites keep working; pages migrate domain-by-domain to registry config.
- `getEmptyState(domain)` is re-implemented over the registry's `genesis` copy — the fallback to
  `data` is removed (the registry *requires* a genesis entry per domain).
- **Completeness rule:** *all 9 existing `DomainContext` keys* — `admissions`, `students`, `attendance`,
  `fees`, `academic`, `payments`, `teachers`, `reports`, and `data` — get real `EmptyStateConfig`
  entries (the `data` domain becomes an honest *Bearing* config, e.g. "No records match this view").
  No existing `getEmptyState(...)` call site may be orphaned by the fallback's removal; the migration
  is complete only when the registry covers every key the old map covered.
- The `Table.emptyMessage` prop routes through the same system (Bearing moment) so legacy tables get
  the fix for free.

### 12.4 Files touched in migration

`components/ui/empty-state.tsx` (compat) · `components/ui/index.ts` (exports) · ~9 domain pages that
use `getEmptyState` (swap to registry) · `risk-center.tsx` / `approval-inbox.tsx` (codify their
hand-rolled Zenith states into the registry) · chart components under `components/analytics/*`
(Bearing at compact size).

---

## 13. Accessibility

- **Announcement:** empty surfaces announce on mount (`role="status"`, polite) — *"No students yet.
  Add your first student."* Screen readers hear the path, not a void.
- **Focus:** the primary CTA is the natural tab stop (no autofocus — the user may want the search
  field); the keyboard hint is a real `<kbd>` with accessible label.
- **Contrast:** body copy at `text-tertiary` passes 4.5:1 on surface in both themes (token-paired,
  no alpha stacking below the contract).
- **Illustrations:** `aria-hidden="true"` (decorative — copy carries the meaning); badges on Relic
  art are also decorative with the condition restated in copy.
- **Reduced motion:** §10.1's 120ms crossfade; no entrance stagger; no parallax of any kind.
- **Checklist:** the setup checklist is a real list (`<ol>`), each step a real control with
  `aria-checked`, completable by keyboard.
- **Veil copy** never assumes the user knows what a permission is: the body says who can see this
  and what to do (`Ask an admin to enable attendance`).

---

## 14. Do's & Don'ts

| Do | Don't |
|---|---|
| Name the moment (Genesis/Bearing/Zenith/Relic/Veil) | Render one undifferentiated "No data" block |
| Imperative, forward copy — "Create your first class" | "No classes yet" status reports |
| One primary CTA + ≤3 reasoned secondaries | Action menus with unrelated options |
| Show the keyboard path (⌘K / N / /) | Hide shortcuts behind discovery |
| Calm entrance: 220ms, 4 movers, one Z | Ambient loops, floating art, confetti on first record |
| Setup checklist that shrinks as it completes | A wall of setup steps that never goes away |
| Registry-backed copy so "No data" is unrepresentable | Ad-hoc copy strings per page |
| The machine suggests, the user decides | Suggestions that block or delay the primary CTA |

---

## 15. Implementation roadmap

| Wave | Scope | Exit criteria |
|---|---|---|
| **W1 · Registry & copy (1 wk)** | `registry.ts`, `EmptyStateConfig` types, re-implement `getEmptyState` over the registry, migrate the 9 domains' copy (Genesis only), kill the `data` fallback | No "No data" copy anywhere in the app; all existing tests green |
| **W2 · Anatomy & sizes (1 wk)** | 4 sizes, hero/card fill behavior, `empty-actions`, kbd hints; compat layer for the ~30 call sites | All five moments render at all four sizes; no CLS on empty↔data swaps |
| **W3 · Illustration system (1–2 wk)** | `empty-art/` for the 9 domains, 3-layer hero stack, moment signals (wash/opacity/zenith-mark/relic-badge/veil-scrim) | Art at token fidelity in both themes; visual regression suite in CI |
| **W4 · Quick setup & templates (1 wk)** | `setup-checklist` (progress + persistence), `template-gallery` dialog, 3–6 templates for academic structure & fees | Setup checklist completes end-to-end; template prefill fills the create form |
| **W5 · Zenith & Bearing (1 wk)** | Codify `risk-center` "No findings" and `approval-inbox` "All caught up" into registry Zenith; chart Bearing at compact; filter escape hatches | The two hand-rolled states are registry config; charts explain themselves |
| **W6 · AI suggestions (1–2 wk)** | `suggestion-card`, server `suggest` endpoint (reuses the intelligence layer's attributable-reason contract), Genesis/Bearing/Zenith hints | Suggestions render, dismiss, explain; failure never blocks the primary CTA |
| **W7 · Onboarding ladder & hardening (1–2 wk)** | Role-aware setup ladder (`getSetupForRole`), completion ceremony, a11y audit (§13), reduced-motion verification, perf caps in CI | A fresh admin can go zero→first-student in one sitting; all §13 checks in CI |

**Sequencing:** W1 is the keystone (registry kills the dead end). W2–W3 make the moment *feel*
premium. W4–W5 make it *useful*. W6 makes it *smart*. W7 makes it *whole*.

---

## 16. Acceptance criteria

1. **No dead ends:** every empty surface names the moment and offers a working primary action;
   "No data" / "Nothing here" are unrepresentable in the registry.
2. **Five moments, one grammar:** Genesis, Bearing, Zenith, Relic, and Veil each have distinct,
   correct copy tone, art signal, and action set — demonstrable in the 6 brief examples (students,
   attendance, reports, charts, fees, books).
3. **One interaction to first value:** a new admin reaches "first record created" via the primary CTA
   (or its keyboard path) — never more than one click deep from the empty state.
4. **Calm:** entrance ≤ 220ms, ≤ 4 movers, transform/opacity only; reduced-motion collapses to one
   120ms crossfade; no ambient animation.
5. **Zero CLS:** empty↔data swaps animate in place; no layout jump in the table shell.
6. **Registry-driven:** copy, art, actions, setup, templates, and suggestions all resolve from
   `EmptyStateConfig`; no ad-hoc empty strings outside migrated pages.
7. **Accessibility:** `role="status"` announcements, ≥ 4.5:1 copy contrast, keyboard-complete
   checklist, decorative `aria-hidden` art.
8. **Performance:** inline SVG only; entrance budget holds in CI (visual + a11y regression gates).
