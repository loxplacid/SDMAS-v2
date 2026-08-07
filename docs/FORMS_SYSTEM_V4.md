# SDMAS Forms System — v4 Specification

**Codename:** *The Quill*
**Status:** Draft for review · **Owner:** Product Design · **Version:** 4.0.0
**Scope:** apps/web — every form: student, teacher, fee structure, payment, leave, inquiry, enrollment, settings, batch ops
**Companion docs:** `docs/DESIGN_SYSTEM_V3.md` (*Corridor* — §12.2 input anatomy, §13 states), `docs/MICRO_INTERACTIONS_V3.md` (*Gloss* — T-family typing/input, F-family focus, L-family loading), `docs/MOTION_SYSTEM_V4.md` (*Escapement* — motion), `docs/NAVIGATION_SYSTEM_V4.md` (*Atlas* — command surface + registry), `docs/NAV_REGISTRY_V4.md` (object types for pickers)

> *A form is a conversation with the machine: it asks, the user answers, and the machine should never ask twice, never lose an answer, and never make the user feel doubted. The Quill is that conversation, engineered.*

**The form contract:** every form must be *schema-driven, validated at the right moment, recoverable after interruption, and completable by keyboard alone* — with the least number of questions asked (smart defaults + progressive disclosure), and none of the user's work ever lost (autosave + undo).

---

## 0. What is wrong with forms today

Audited against the current system (`components/ui/form.tsx`, `input.tsx`, `select.tsx`, and ~15 pages):

| Defect | Evidence today | v4 answer |
|---|---|---|
| **Hand-written validation, per page** | every page has its own `validate()` building `Record<string,string>` errors | **One schema + one engine** (§3): rules declared once, enforced everywhere |
| **Submit-time-only validation** | errors appear on submit; nothing guides while typing | **Commit-then-change validation** (§5): on blur first, then live after touched |
| **No undo/redo** | `Cmd+Z` does nothing meaningful in forms | **Form-level undo/redo stack** (§8) |
| **No autosave** | drafts are page-specific hacks (`risk-center.tsx` local state) | **Draft persistence + autosave** (§9) with recovery |
| **No smart defaults** | every field starts empty | **Contextual defaults with preview** (§7) |
| **No relationship picker** | selects are `<option>` lists; large datasets are unscannable | **The picker** (§10) — search + recent + filters, virtualized |
| **No live formatting** | currency/dates typed raw | **Format-on-commit** (§6) |
| **Keyboard is default browser only** | Tab order is DOM order; no Cmd+Z, no palette jump | **Keyboard map + palette integration** (§11, §13) |

---

## 1. Thesis & the premium bar

Forms have one job: **capture correct data with the least friction**. Four sources, one posture:

| Source | Principle extracted | Translation into SDMAS |
|---|---|---|
| **Apple (HIG)** | Validate on *commit*, not on every keystroke; smart defaults from context; undo/redo is a system convention; errors explain how to fix | The validation timing model (§5.1); the defaults priority ladder (§7.2); `Cmd+Z` as law (§8); error copy anatomy (§5.4) |
| **Notion** | Keyboard-first inline editing; slash-commands; autosave with undo; relationship pickers as first-class objects | Fields are objects (§10); autosave is ambient (§9); `Tab`/`Enter` flow and type-ahead everywhere (§11) |
| **Google Forms** | Sections with branching logic; per-question validation; large-dataset choice search | Adaptive sections (§4); the picker's search-first dropdown (§10) |
| **Manus** | Progressive disclosure of steps; transparency ("what is happening and why"); smart defaults; dynamic checklists | Section disclosure with a stated reason (§4.4); default previews with one-tap override (§7.3) |

**Rejected:** forms as questionnaires (every field equally loud), modal-on-every-error, dead-end fields, and any form that can lose the user's work.

---

## 2. The form contract (normative)

1. **Nothing the user types is ever lost.** Autosave + draft recovery (§9) are mandatory, not optional.
2. **Nothing the user types is ever ambiguous.** Validation states *what* is wrong and *how* to fix it (§5.4).
3. **The user is never asked twice.** Smart defaults fill what the system already knows (§7); progressive disclosure hides what the answer makes irrelevant (§4).
4. **Every form is keyboard-completable** (§11) and reachable from the command surface (§13).
5. **Every action is reversible** — undo (`Cmd+Z`), redo (`Cmd+Shift+Z`), and cancel-restores-draft.

---

## 3. Architecture — the form model & engine

### 3.1 The model

One declarative `FormModel` per surface — the same pattern as the nav-registry and widget registry (data-driven, auditable, testable):

```ts
interface FormModel {
  id: string                    // 'student.create' — stable; drafts/palette reference it
  title: string
  sections: FormSection[]       // §4
  save: SavePolicy              // §9
  defaults?: DefaultRule[]      // §7
  onSubmit: (ctx: SubmitContext) => Promise<SubmitResult>
}

interface FormSection {
  id: string
  label: string
  fields: FormField[]
  /** Visibility rule — progressive disclosure (§4). */
  visibleWhen?: (values: FormValues) => boolean
  /** Staged wizard behavior (§4.3). */
  stage?: { index: number; title: string }
  /** 'required' | 'optional' | 'collapsible' */
  mode?: 'required' | 'optional' | 'collapsible'
}

interface FormField {
  id: string                    // 'first_name'
  kind: 'text' | 'number' | 'email' | 'phone' | 'date' | 'currency' | 'textarea'
      | 'select' | 'picker' | 'checkbox' | 'radio' | 'toggle' | 'segmented'
  label: string
  required?: boolean
  rules?: ValidationRule[]      // §5
  format?: FormatRule           // §6
  default?: DefaultRule         // §7
  autocomplete?: AutocompleteSource // §10/§11
  help?: ContextHelp            // §12
  placeholder?: string
  autoFocus?: boolean
  /** Grouping inside a section. */
  layout?: 'stack' | 'inline' | 'grid'
}
```

**Rule:** a form that needs behavior the model cannot express extends the model — never the page. Every field, section, and rule is registry-visible so the audit and tests can enumerate them (the ≤ friction audit, §16).

### 3.2 The engine

The `useFormEngine(model)` hook owns all state and behavior; pages stop hand-rolling it:

| Responsibility | Today (per-page `validate()`) | Engine |
|---|---|---|
| Values + dirty tracking | `useState` maps | `values`, `dirty`, `touched` |
| Validation | ad-hoc functions | rules engine, timing per §5 |
| Undo/redo | — | command stack (§8) |
| Autosave/drafts | page hacks | draft store (§9) |
| Defaults | empty initial state | resolver (§7) |
| Focus/keyboard | browser default | focus controller (§11) |

**Rule:** a page may not own form state — `useFormEngine` owns it. This is the single biggest architecture change and the foundation of everything below.

### 3.3 Component system

```
FormShell        — title, section rail, sticky action bar (primary + save state)
Section          — label, fields, disclosure (§4)
Field            — the generic wrapper: label → control → hint/help/error (§5)
Control          — Input · Textarea · Select · Picker(§10) · Checkbox · Toggle · Segmented · Date
Picker           — relationship + large-dataset search (§10)
HelpPopover      — inline context help (§12)
SaveIndicator    — "Saving… → Saved" heartbeat (§9)
UndoRedoBar      — transient "Undone / Redone" flash (§8)
```

`Field` renders `Input`-compatible markup (label-above, `aria-describedby`, error/hint slots — the existing `input.tsx` contract, extended). **Radius:** the Field adopts Corridor's `radius.control` (8px), superseding the shipped `rounded-[10px]` in `input.tsx` — a v2 remnant corrected here per the design-system re-capture loop (Corridor §18); the correction ships in W1.

---

## 4. Progressive disclosure & adaptive sections

### 4.1 The principle

**Ask only what the current answers make relevant.** A form is a tree of questions, not a list. Sections reveal, collapse, and reorder as values change — and every reveal states why.

### 4.2 Visibility rules (branching)

- `visibleWhen` per section/field (Google Forms branching, made quiet): a "Student type: Day/Boarding" toggle reveals the hostel section; "Payment method" reveals the reference-number field.
- **Rules:** revealed sections enter with `Fade + 4px Slide` (20ms stagger, ≤ 150ms — Escapement §10); hidden sections are removed from tab order and skipped by validation; a section hiding a field with a value **preserves** the value (collapsing is not deleting — undo/autosave still hold it).

### 4.3 Staged forms (wizards)

For long flows (admission, batch enrollment), sections become **stages** with a stepper: stage progress draws (Gloss K17), forward is East, back is West (Compass), per-stage validation gates advancement, and the draft autosaves between stages (§9) so a wizard is resumable mid-flow.

### 4.4 Disclosure with a reason (Manus)

A collapsed/collapsible section's header states why it's optional: "Optional — the guardian can be added later." A hidden section never just vanishes; the reason is one line, `caption`. Defaults that pre-fill a hidden section are announced the same way (§7.3).

---

## 5. Inline validation

### 5.1 The timing model (Apple)

| Moment | What validates | Why |
|---|---|---|
| **On commit (blur)** | the field just left | First check — the user is done thinking about it |
| **On change, after touched** | fields the user has edited | Live feedback without nagging untouched fields |
| **On submit** | everything, once | The gate; server errors land here too |
| **Never on mount** | nothing | A blank form is not an error |

### 5.2 The field state machine

```
untouched ──blur/commit──► touched ──invalid──► error ──fix (valid input)──► valid
   │                        │                      │
   └──── typing ────────────┘   valid on commit    └── live re-validate on change
```

A field shows an error only when it is `touched && invalid`; it clears **live** as the user fixes it (never after a second submit).

### 5.3 Animated validation

Per the Gloss T-family, at Escapement values:

| Event | Move | Notes |
|---|---|---|
| Error appears | ring → danger (75ms) + message slides down 4px (`fast`, 120ms) | T03 |
| Live fix clears | message fades out, ring → accent (`fast`) | instant relief |
| Repeated commit on an error field | the field's content flashes danger-light once, 200ms (no geometry shake — reads as wobble on data) | T04 adapted¹ |
| Character count near limit | counter warms muted → warning → danger (`fast` per threshold) | T05 |
| Number/currency commit | value re-settles with a micro-pop, tabular aligns | T07/T15 |

### 5.4 Error copy anatomy

`what is wrong + how to fix`, one line: "Enter a 10-digit phone number" (never "Invalid input"). Server errors attach to the field or render as an inline banner (Corridor §13.3) with a retry; a failed save never discards the draft (§9.5).

> ¹ **Designed deviation from the Gloss.** Gloss T04 specifies a 4px × 3 geometry shake for repeat offenders; the Quill replaces the shake with a one-shot danger-light flash because geometry shake reads as wobble on data-bearing fields (dense ERP surfaces). T04 remains the reference for non-data forms; this deviation is recorded here so the two docs don't contradict.

---

## 6. Live formatting

1. **Format on commit, normalize on input.** While typing, the value is permissive (digits only for phone); on blur it formats (`+91 98765 43210`); on parse it normalizes (Gloss T10: `3/2/26` → `03/02/2026`). Formatting never fights the fingers.
2. **Currency** (the flagship): prefix/suffix inside the field (₹, %), tabular numerals, thousands separators on blur, `₹ 0` never shown — empty renders as placeholder. Amount pop on commit (Gloss T15).
3. **Alignment is layout, not typing**: a currency field right-aligns its numeral; a phone field left-aligns. Alignment changes on focus are forbidden (the value jumps — Gloss T01: text entry is never animated).
4. **Rules:** a `FormatRule` is part of the field model (§3.1); formats are locale-driven end to end (Corridor §14.10); formatting never changes the stored value's meaning (the normalized value is what's saved).
5. **Textareas** auto-grow one line at a time as content exceeds the field (Gloss T12, 120ms per line) — the field follows the text, never a scrollbar-in-a-tiny-box.

---

## 7. Smart defaults

### 7.1 The ladder

Defaults resolve in priority order — the first hit wins:

1. **Explicit** — a user-set value (always wins; never overridden).
2. **Remembered** — the user's last value for this field on this form (per user × campus).
3. **Contextual** — from the current surface: a payment form opened from a student 360 prefills the student; a leave form prefills the applicant; term/year prefills the active term.
4. **Derived** — computable: today's date, next roll number, the active fee schedule.
5. **None** — empty, with a good placeholder.

### 7.2 What never defaults

Passwords, emails (unless editing self), amounts where a mistake is costly, and anything the user must consciously choose (consent toggles). Defaults reduce friction; they never make decisions the user should own.

### 7.3 Preview & override (Manus)

A default is **announced, not hidden**: a filled-by-default field shows a `caption` note — "Filled from the active term · change" — and a one-tap clear. A default that reveals a section states why (§4.4). Defaults are first-class in undo: `Cmd+Z` after submit reverts a default the user didn't want, and the draft store records *intent* (user-set vs default) so autosave never fights an override.

---

## 8. Undo & redo

1. **Form-level command stack** (the engine): every commit (blur with change, toggle, picker selection, default-override, section reveal) pushes a command. Coalescing: rapid typing in one field coalesces into one command per pause (≥ 800ms), so `Cmd+Z` undoes "the sentence", not "the letter".
2. **Bounds:** 50 commands; the stack lives with the draft (§9) so undo survives reload for the session.
3. **Redo:** `Cmd+Shift+Z`; the stack clears on a new edit after undo (standard semantics).
4. **Feedback:** a transient `UndoRedoBar` — "Undone · redo" (Gloss K08 check-revert rhythm) — appears at `base` (180ms) and rests; `Esc` dismisses. The flash is the only undo animation; the field value itself swaps instantly (undo is a state change, not a performance).
5. **Destructive scope:** undo never crosses the submit boundary — after a successful save, the stack resets (the saved state is the new baseline) and the draft clears (§9).
6. **Desktop parity:** the Forge's keyframe model maps `Cmd+Z` the same way (Forge §12).

---

## 9. Autosave & drafts

1. **The contract:** a form is never "unsaved" silently. The engine autosaves the draft to localStorage (per `FormModel.id` × entity × campus) on every coalesced change (800ms of stillness — Gloss L09), and the `SaveIndicator` heartbeat answers: `Saving…` → `Saved hh:mm` → rests.
2. **Server drafts:** for long/staged forms (admission), the draft also persists server-side via a **new backend capability** (a draft endpoint, W4 scope), so a wizard survives device change. localStorage is the fast path; the server is the durable path.
3. **Recovery:** on mount, if a newer draft exists than the last saved state, a banner offers **Restore draft / Discard** (never silent resurrection, never silent loss). Restoring replays the draft into the stack (undo works on the restored draft).
4. **Batching:** autosave writes are batched per frame; a save in flight coalesces with the next (never two concurrent writes of the same draft).
5. **Failure:** a failed save keeps the draft and shows `Saved locally · retry` — the user's work is never at risk and never hidden.
6. **Privacy:** drafts are per-user, cleared on successful save, and cleared on workspace switch (campus-scoped keys).

---

## 10. Relationship picker — the flagship control

Picking a student, class, teacher, or fee schedule from a large dataset is the most common *hard* form action in SDMAS. The picker replaces bare `<option>` selects.

### 10.1 Anatomy

```
[ Student ▸ ]  ──────────────────────── trigger: current value or placeholder
┌──────────────────────────────────────┐
│ 🔍 search…                    [×]    │  type-ahead (search-first)
│ ──────────                          │
│ RECENT   · Student 1042 · Class 7A  │  remembered picks (§10.3)
│ ──────────                          │
│ RESULTS  · Student 1042 — Anaya     │  ranked, virtualized
│           · Student 1187 — Rohan    │
│ FILTER   · Class: 7A ▾ · Status ▾   │  scope filters
└──────────────────────────────────────┘
```

1. **Trigger** shows the resolved value (via the nav registry's `objectTypes` label template) and opens the popover South from it (Escapement §10.16).
2. **Search-first**: typing filters instantly (the universal search index + `ranking.ts`, debounced 150ms); empty query shows **Recent + frequent** (Raycast rule) — the top of the list is already useful.
3. **Virtualized results** — a 2,000-student school renders ≤ 24 rows; the list scrolls at 60fps (§14).
4. **Keyboard**: `↑↓` moves, `Enter` commits, `Esc` closes, type-ahead is native; the active row's wash slides (120ms, Atlas palette rule).

### 10.2 Multi-select (batch)

Chips row in the field; each chip removable (`×`), chips enter with `micro-spring` (Gloss K13), the count reads "3 selected". Bulk operations (batch enroll) use the multi-picker against the same search surface.

### 10.3 Remembered picks

Per user × campus, the picker remembers the last 5 picks per entity type (the "Recent" block). Remembered picks are *picks*, not defaults (§7.1's ladder keeps them separate).

### 10.4 Deep-link parity

A picked value is a link: the chip/trigger resolves to the object's 360 via `resolveObjectRoute` (nav-registry §7) — "open the student" is one click from the picker, never a second search.

### 10.5 Auto-complete (suggestions) — scalar values, not objects

Auto-complete is the picker's sibling for **scalar values** (city, subject name, template, leave type) — text fields whose values come from a vocabulary, not from an entity set. It is a distinct control from the picker (§10.1):

1. **Pick the right control** — a field autocompletes *scalars* when the value is a string from a bounded vocabulary, and *picks objects* when the value is a relationship. A subject field autocompletes; a student field picks. The `kind: 'autocomplete'` field uses this surface; `kind: 'picker'` uses §10.1.
2. **Source contract** — an `AutocompleteSource` is either a **local vocabulary** (a small static list, filtered client-side with the existing ranking: exact > prefix > fuzzy) or a **remote endpoint** (debounced 150ms, min 2 chars, cancelled on out-of-order responses — the last query wins).
3. **Suggestion dropdown** — grows South from the field (Escapement §10.16), shows ≤ 8 suggestions, keyboard-native (`↑↓` + `Enter` commits, `Esc` closes, type-ahead continues). The active row's wash slides (120ms).
4. **Commit semantics** — choosing a suggestion sets the value *as the user typed or as the suggestion spells it*: the suggestion is canonicalized, but the user may type an unlisted value unless the field is constrained (`allowCustom: false`).
5. **Precedent** — the existing `table/filter-rail.tsx` suggestion builder (T32) is the in-repo pattern this control generalizes; the field-level control reuses its ranking and popover mechanics.

---

## 11. Keyboard-first

| Context | Behavior |
|---|---|
| Global | `Cmd+Z` undo · `Cmd+Shift+Z` redo · `Cmd+S` save now (forces autosave flush) · `Esc` close popovers/dismiss focus |
| Field flow | `Tab` next field · `Shift+Tab` previous · `Enter` commits the field (and submits the form from the last field) · `Esc` blurs into the form shell |
| Selects/pickers | type-ahead · `↑↓` · `Enter` · `Esc` (§10) |
| Checkbox/radio/toggle | `Space` · `←→` for radio groups |
| Sections | `Alt+↑↓` jump between sections; section labels are landmarks (`aria-label` per section) |
| Command surface | `Cmd+K` → "Jump to field: guardian_phone" (§13) |

**Rules:** Tab order follows visual order (section by section); a revealed section's fields are inserted into the tab order at reveal time (§4.2); disabled fields are skipped; the focus ring is the one animation that survives minimal tier (Escapement §10.5).

---

## 12. Context help

1. **Three depths** (progressive): a `caption` hint (always, one line) → a `?` popover (field-level, "why this matters" + how-to) → a docs link (rare). Never more than one depth visible at once.
2. **Help is contextual**: the hint swaps with the field's state (focus shows the focus-hint, Gloss T17); an error replaces help (the error is the help, §5.4).
3. **Manus transparency**: a field with a smart default or a hidden section shows *why* ("Filled from the active term · change"). Help never lectures; it answers.

---

## 13. Command palette integration

The Atlas command surface reaches *into* forms:

- **Jump to field:** `Cmd+K` → "jump to field" → field label → focuses it (fields are registered per visible form via the engine).
- **Form commands:** `Save now`, `Reset to defaults`, `Clear draft` are palette commands when a form is visible (verbs are registry commands, Atlas §7.2).
- **"Fill from previous":** for repeated-entry forms (enrollment), the palette offers the remembered values (§7.1.2) as one-tap fill.
- **Object pick from palette:** the picker's search surface *is* the universal search (same index, same ranking) — picking from `Cmd+K` and picking from the field are the same muscle memory.

---

## 14. Performance

| Contract | Cap | Enforcement |
|---|---|---|
| Keystroke → field render | ≤ 16ms; only the field re-renders (field-level isolation) | engine memoization; no page re-render on input |
| Validation cost | rules are pure; computed per field on commit/change only | rules engine contract |
| Picker search | ≤ 24 rows rendered; virtualized; debounced 150ms | list virtualization |
| Autosave | 1 write per 800ms of stillness; batched per frame | draft store contract |
| Undo | stack ≤ 50; coalesced ≥ 800ms pauses | engine |
| First paint of a form | fields render as one `Fade` (no per-field heroics); skeletons only for async pickers | Escapement §10 |
| Layout | no layout shift on error/help swap — messages occupy reserved slots (hint slot swaps to error slot) | CSS grid slots |

---

## 15. Architecture — files & APIs

Grounded in the current codebase; gaps are the roadmap.

| Layer | Exists today | v4 work |
|---|---|---|
| Model | — | `forms/form-model.types.ts` (FormModel, FormSection, FormField, rules, §3.1) |
| Engine | per-page `validate()` + `useState` maps | `forms/use-form-engine.ts` (values, touched, validation timing, undo/redo, defaults, focus) |
| Drafts | page hacks (`risk-center.tsx`) | `forms/draft-store.ts` (localStorage + server draft endpoint, recovery, batching) |
| Controls | `ui/input.tsx` (label/error/hint/aria), `ui/select.tsx`, textarea | Extend the Field contract; add `ui/picker.tsx` (§10), `DateField`, `CurrencyField`, `SegmentedField` |
| Validation | ad-hoc per page | `forms/rules.ts` (required, format, length, range, cross-field) + server-error adapter |
| Help | hints in `input.tsx` | `ui/help-popover.tsx`, hint-state swap (Gloss T17) |
| Motion | `lib/motion/*` | consume `useMove` per §5.3 — no new motion code |
| Command surface | `nav/*` (Atlas) | field-jump + form commands registered in the registry (§13) |

**Rebuild path:** the first forms to migrate are the highest-volume captures — payment (`payment-list.tsx`), new student, leave request (`new-leave.tsx`), new inquiry (`new-inquiry.tsx`). Each page swaps its `validate()` + state for `useFormEngine` + a `FormModel`; the visible UI stays identical until the model earns the new behaviors.

---

## 16. Implementation roadmap

| Wave | Scope | Acceptance criteria |
|---|---|---|
| **W0 · Audit** | Enumerate every form in `apps/web/src/pages` | A table per form: fields, current validation, friction gaps (no undo/autosave/defaults) |
| **W1 · Engine & model (2 wk)** | `form-model.types.ts`, `use-form-engine` (values/touched/timing), migrate 2 pilot forms | Pilot forms behave identically to today; engine passes unit tests for the state machine (§5.2) |
| **W2 · Validation & formatting (2 wk)** | rules engine, animated validation per §5.3, currency/phone/date formats per §6 | Commit-then-change timing verified; error copy follows §5.4; zero layout shift on error swap |
| **W3 · Defaults & undo (1–2 wk)** | defaults ladder (§7), command stack (§8) | Every migrated form has a default ladder and `Cmd+Z`/`Cmd+Shift+Z`; defaults announced with override |
| **W4 · Autosave & drafts (2 wk)** | draft-store, SaveIndicator heartbeat, recovery banner, server drafts for staged forms | Interrupt + reload restores the draft; saved-on-success clears; failure never loses work |
| **W5 · Picker & search (2–3 wk)** | `ui/picker.tsx` (§10), remembered picks, virtualized results; large-dataset search | A 2,000-student picker searches and commits under 300ms; keyboard-complete; deep-link parity |
| **W6 · Disclosure & help (2 wk)** | adaptive sections (§4), staged wizards, context help (§12) | Branching verified; hidden sections preserve values; help swaps with state |
| **W7 · Integration & hardening (2 wk)** | palette field-jump (§13), keyboard audit (§11), a11y (§17), performance caps (§14), reduced-motion verification, Forge parity | Every form keyboard-completable; field-jump works on visible forms; all §14 caps hold in CI; desktop renders the same model |

**Sequencing:** W1 is the keystone (no feature above works without the engine). W2–W4 are the "nothing lost, nothing ambiguous" contract. W5 is the flagship control (highest perceived value). W6–W7 complete the experience.

---

## 17. Accessibility

1. Labels are always visible and linked (`htmlFor`/`id` — the existing `input.tsx` contract); every control has `aria-describedby` → hint or error slot.
2. Errors announce via `role="alert"` on appearance; live validation progress via `aria-live="polite"` on the save heartbeat.
3. Focus: the ring is visible on every focus (Escapement §10.5); reveal of a section moves focus to its first field (never steals mid-typing); picker popovers trap focus and return it to the trigger.
4. Contrast floors per Corridor §3.5; error copy ≥ 4.5:1; color is never the only error signal (ring + message + icon).
5. Reduced motion: validation motion and section reveals collapse to instant appearance with a static reading (§5.3 per Escapement tiers).
6. Dyslexia & reading: never justify, generous line-height (Corridor §5), and the field label stays put (no floating-label pattern — Corridor §12.2).

---

## 18. Do's & Don'ts

**Do**
- Validate on commit first, then live after touched (§5.1).
- Make every error say what's wrong and how to fix it (§5.4).
- Ask only what the current answers make relevant (§4).
- Default from the ladder, announce the default, allow one-tap override (§7).
- Never lose an answer — autosave, recover, undo (§8–9).
- Make the picker search-first and keyboard-complete (§10–11).
- Format on commit; never fight the fingers while typing (§6).

**Don't**
- Don't validate an untouched field, and don't error a blank new form (§5.1).
- Don't shake, bounce, or loop validation motion (§5.3).
- Don't hide a section without a stated reason, and don't delete a hidden field's value (§4.4, §4.2).
- Don't default passwords, costly amounts, or consent (§7.2).
- Don't let `Cmd+Z` cross the submit boundary (§8.5).
- Don't render a 2,000-item `<option>` list — the picker is the floor for large datasets (§10).
- Don't let an error or help swap shift layout (§14).
- Don't ship a form the engine doesn't own (§3.2).

---

## 19. Acceptance criteria

- The 5 pilot forms (payment, new student, leave, inquiry, enrollment) pass the friction audit: defaults where the ladder allows, undo/redo live, autosave survives interruption.
- Every migrated form is keyboard-completable end to end; field-jump works from `Cmd+K`.
- A picker over the full student dataset searches and commits in < 300ms; results virtualized; remembered picks shown.
- Zero layout shift on any validation or help state change.
- Draft recovery never loses or silently resurrects work; a failed save is always recoverable.
- All motion respects the Escapement tiers; the forms engine owns all form state — no page-level `validate()` remains in migrated forms.

---

*The Quill is the conversation with the machine: ask once, never lose an answer, never doubt the user twice. Engineered so that the longest form in the school feels like one calm, recoverable, reversible conversation.*
