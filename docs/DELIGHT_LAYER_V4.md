# The Delight Layer — Subtle Emotional Feedback

**Spec:** DELIGHT_LAYER_V4 · **Codename:** *The Glint* · **Version:** 4.0.0 · **Status:** Design
**Applies to:** apps/web (desktop) + apps/mobile (future touch) · **Family:** v4 design system
(Gloss tokens, Escapement motion, Corridor anatomy, Bridge dashboard, Atlas nav, Quill forms, Vestibule empty states)

> The Escapement makes motion *communicate*. The Glint makes it *feel*.
> Every interaction here communicates state — and every one of them must be **subtle enough to be
> missed, and correct enough to be missed when it's gone.** If the user notices the delight itself,
> we've overdone it; they should only notice that the product feels *alive*.

---

## 0. What is wrong with delight today

| Observation | Evidence | Consequence |
|---|---|---|
| **The motion system is deep, but the emotional moments are unowned** | `useMove`/`useFlipList`/`useMotionTier` are excellent (tier-gated, tokenized) — yet there is no celebration, no save-acknowledgment, no milestone concept anywhere in the app. | The product moves well but never *responds* emotionally. Saves just… stop loading. |
| **The one celebration primitive is orphaned** | `animate-badge-pop` exists in the CSS catalog and is used exactly once (notification unread dot). No `Confetti`, no `Checkmark` draw, no `Achievement` component. | When a milestone does happen (first student, 100% attendance), there's no vocabulary to mark it. |
| **Counters are everywhere but not delightful** | `AnimatedCount` (easeOutCubic, 1200ms) is used across dashboards — but it replays on every visit and never *stops* with a settle (a count that ends with a micro-pop reads "done"). | Numbers animate, then nothing — the beat after the count is the emotion and it's missing. |
| **Hover = one tool for everything** | Cards, nav tiles, alert cards all use `-translate-y-0.5` lift (Visual Polish Review F-21). No depth hierarchy, no elasticity. | Every hover feels the same, so none of them feel designed. |
| **No ambient atmosphere** | Gradient orbs exist only on login; dashboards are static navy heroes. | The app has no "place" feel — it's a set of screens, not a workspace. |
| **Skeleton = pulse only** | `animate-skeleton` is an opacity pulse. No shimmer, no content-shape. | Loading reads as "broken" rather than "brewing". |
| **Sound and vibration: unconsidered** | No web audio, no `navigator.vibrate`, no policy. | When (not if) someone asks for sound, it'll be bolted on ad hoc. |

**The bar:** communicate state with warmth, never with noise. Every moment has a level; every level
has a budget; every budget is tier-gated and CI-checkable.

---

## 1. Thesis — delight is a ladder, not a checkbox

Delight is the *emotional intensity* of a moment, and it must scale with the *meaning* of what just
happened. The system defines **five intensity levels** — a **whisper ladder** — and every feedback
moment in the product is assigned exactly one.

| Level | Name | What it marks | Primitive | Examples |
|---|---|---|---|---|
| **L1 · Whisper** | The micro-beat | Hover, press, focus, drag | Elastic response, depth shift | Hover a nav tile, press a button, focus a field |
| **L2 · Soft** | The acknowledgment | Any completed routine operation | Checkmark draw + settle pulse | Save, create, delete, send, approve |
| **L3 · Bright** | The progress | Work in flight, long waits | Shimmer, indeterminate progress, live step ticker | Loading a table, generating a report, agentic flow |
| **L4 · Warm** | The milestone | Rare, meaningful completions | Achievement toast + gentle burst | First record created, term closed, report published |
| **L5 · Radiant** | The summit | Highest-value product moments (once per school-year cadence) | Confetti (bounded) | Year rolled over, 100% attendance week, first full cohort graduated |

**The three rules:**

1. **State first, emotion second.** The user must always be able to read *what happened* from the
   copy and icon alone. The delight is a garnish that never carries information. (A checkmark always
   has its label; confetti always has its caption.)
2. **The ladder is an allocation, not a menu.** If everything is delightful, nothing is. L4/L5
   moments are *quota'd* (below) so they stay rare. Most of the product's life is L1/L2 — and that's
   the design working.
3. **Tier-gated by the Escapement, always.** The Glint runs *only* in the `precise` motion tier.
   `efficient` collapses every level to a ≤75ms opacity change; `minimal` is instant. This is not a
   preference — it's the contract: delight is the first thing reduced motion takes away.

---

## 2. L1 · Whisper — the physical layer

### 2.1 Elastic press (magnetic buttons, §"Magnetic buttons")

The flagship L1 interaction. The **Button** and clickable cards get a two-part physical response:

- **Hover pull:** the control translates up to **3px toward the cursor** (x-constrained to ±3px) over
  `220ms` on the spring easing (`--ease-spring-gentle`), and returns on leave. Only *primary* and
  *card* CTAs — applying it to every button would make a row of buttons crawl.
- **Press:** `scale(0.97)` at `--motion-fast` with a `--ease-spring` rebound to 1.0 (`elastic`:
  overshoot 1.02 then settle — the existing `--ease-spring` cubic-bezier already encodes this).
- **Release:** if the action completes (save succeeded), the button ends with one **L2 pulse**
  (§3.2) — press-to-result feels continuous.

**Rules:** magnetic pull is transform-only (compositor), clamped to the button bounds ±3px (never
under the cursor's pointer-events), disabled in `efficient`/`minimal`, and skipped entirely for
row-level hover (density wins — rows get the L1 depth shift below, not magnetism).

### 2.2 Hover depth (the tiered shadow system)

One shadow ladder, three depths — replaces the current one-size `-translate-y-0.5` everywhere:

| Depth | Trigger | Response | Use |
|---|---|---|---|
| `d0` | rest | `shadow-xs` (hairline) | default |
| `d1` | hover, interactive rows/cards | `shadow-sm` + `translateY(-1px)` + border-lightening | secondary surfaces |
| `d2` | hover, primary cards/CTAs | `shadow-md` + `translateY(-2px)` | primary path only |

The Escapement's rule holds: depth moves are `slide N, D2, I2` — same choreography, smaller travel.
**Direction of travel is always up-and-into the viewer** (N) for cards; rows lift by background only
(`--color-surface-hover`), never geometry — a table row that jumps breaks reading.

### 2.3 Focus beat

The existing focus ring (2px accent, `--radius-sm`) is correct; the Glint adds one micro-moment:
on `:focus-visible`, the ring *draws* in over 120ms (a 1px→2px width transition on a `::after` ring,
transform/opacity only). Cheap, accessible, and it makes keyboard users feel the same physicality
mouse users get from hover.

---

## 3. L2 · Soft — the acknowledgment layer

### 3.1 The success checkmark (draw, don't pop)

Every successful mutation in the app currently ends in a toast (`ToastProvider`, `showToast`). The
Glint upgrades the **success toast's status dot** — the checkmark lives *inside* the existing toast,
in place of the dot; it is not a second surface:

- A 16px stroke-dashoffset animation (`stroke-dasharray` draw, 180ms, `--ease-emphasized-decelerate`)
  replacing the dot.
- Followed by the *existing* one-pulse (the toast already pulses at 320ms — keep it; it's the settle).
- **Never a pop** (scale-in) for success — a pop reads as celebration; a save isn't one.

### 3.2 The button settle

After a primary action completes (the `loading` state flips), the button performs one **L2 settle
pulse** (`scale 1 → 1.02 → 1`, 300ms, spring) — the same `pulse()` primitive `useMove` already ships,
now attached to the action-complete moment. Success = pulse; error = the existing error flash
(Quill T04, no geometry shake on data forms). **One pulse per moment** (Escapement §4.5).

### 3.3 Counter settle (smooth counters / animated statistics)

`AnimatedCount` is the right primitive; it's missing its ending. The Glint defines the **counter
choreography**:

1. **Roll:** current behavior (easeOutCubic, tabular-nums — no layout shift).
2. **Settle:** at 100%, one `scale(1 → 1.035 → 1)` spring pop on the numeral (L2 pulse), 220ms.
3. **Session-once:** counters roll on first data arrival per session, then render instantly
   (Visual Polish Review F-14) — the *first* time is the delight; the tenth is the noise.
4. **Direction:** count *up* to a value, never down; decreases render instantly (a falling number
   feels like loss, not animation).

---

## 4. L3 · Bright — the progress layer

### 4.1 Shimmer loading (upgrade from pulse)

Replace the opacity-pulse `animate-skeleton` with a **shimmer**:

- A `translateX(-100% → 100%)` sweep of a translucent light band (`linear-gradient(90deg, transparent,
  var(--color-surface)/40%, transparent)`), 1.4s, `linear`, looped — over the existing content-shaped
  skeleton blocks (Vestibule/Bridge already specify content-shape).
- **Determinate when we know:** progress bars (fee collection, file upload, report generation) get a
  determinate fill with a 1.5px leading highlight, never a spinner + bar combo.
- **Indeterminate when we don't:** agentic flows (Manus pattern) use the shimmer + a live status
  ticker ("Generating report…", "Processing 214 rows…") — text changes carry the progress, the
  shimmer carries the motion. **Never** a fake percentage.

### 4.2 The step ticker

For multi-step jobs (term rollover, batch enrollment, report generation), a **step ticker** replaces
the blank spinner: N steps, current step highlighted with a draw-in check when it completes
(reusing §3.1's checkmark), 180ms per transition, capped at 6 visible steps. This is the only
delight that *reduces* anxiety — it converts "is it stuck?" into "it's on step 3 of 5".

---

## 5. L4 · Warm — the milestone layer

### 5.1 What qualifies (the milestone rubric)

A moment earns L4 if and only if it is **rare, meaningful, and consequential** — and it must be
assigned in the registry, not invented by a page:

1. **First-of-kind:** first student/teacher/class/term/payment/grade-record created in the school
   (per campus, per role).
2. **Threshold-crossing:** first time attendance clears 90%, fee collection clears 80%, a class
   reaches 100% attendance for a week.
3. **Publication:** a report card batch or term report is published (the publisher's moment — not
   the recipients').
4. **Closure:** a term/year is closed and rolled over.

**Explicitly NOT L4:** every save, every delete, every approval (L2), every login (no celebration —
it's the user's own action), and anything that happens more than ~once per week per user.

### 5.2 The achievement toast

A dedicated **AchievementToast** (not the standard toast) — larger, right-aligned, one per moment:

- Anatomy: drawn checkmark (§3.1) → label ("First student enrolled") → caption ("You're building
  your school's directory") → optional context chip (student name).
- Motion: `slide SE, D3, I3` enter (the standard toast grammar, one importance notch up), checkmark
  draw, then **one soft burst** — a 24px radial glow that expands and fades at the checkmark
  (transform/opacity only, 400ms, no particles at L4).
- Dismissal: auto after 5s (longer than the 4s standard toast — a milestone earns an extra beat) or
  click; never stacks — a second milestone during one replaces the queue, doesn't pile.
- **Announcement:** the achievement toast mounts with its own `role="status"` (not the shared
  `aria-live="polite"` toast container), so a save (L2) immediately followed by a milestone (L4)
  produces one polite live update, not two overlapping announcements — and the 5s/4s timing
  divergence stays a visual choice, never a screen-reader interrupt.

### 5.3 The quiet-first rule

L4 begins *quiet*: the checkmark and caption first, the burst 150ms later. If the user's eye is
elsewhere, they miss the burst and still see the toast. Delight is a *gradual* reveal, never a
flashbang.

---

## 6. L5 · Radiant — the confetti layer

### 6.1 When confetti is justified (Apple's discipline)

Confetti is a **summit token** — it marks the rare, high-investment, long-horizon moments that the
whole school worked toward. The product defines the full list up front; nothing else gets it:

- First full term/year **rolled over** successfully.
- A full **cohort graduated** (all records finalized + report cards published).
- **100% attendance for an entire school week** (all classes, all days) — the equivalent of closing
  all three Apple Fitness rings.

**Hard rules:**
- Quota: **≤ 3 L5 moments per school-year per campus.** If a page triggers more, it's wrong.
- Always captioned ("Term 2026–27 closed — 214 students rolled over") — confetti without a caption
  is noise.
- **Never** on routine completion, submissions, or anything transactional (a form "submitted" must
  not be confettied — users would read it as *approved*, and that false positive is dangerous).
- No loop, no rain: a single **bounded burst** — 60–80 particles, `600–900ms`, gravity-arc physics
  (CSS keyframes or a 2KB canvas; a DOM-per-particle approach is banned), origin at the moment's
  trigger point, fades to nothing. Once.

### 6.2 The confetti component

`<Confetti origin={rect} variant="school" />` — one component, one burst, autodestruct. Reduced
motion → render nothing (the caption still appears). `efficient` tier → the caption appears, the
burst is replaced by a 120ms opacity crossfade of the same glow from §5.2.

---

## 7. Ambient atmosphere (optional, off by default)

### 7.1 The ambient gradient

A **subtle, slow** background life for the app shell (not data surfaces):

- Two ultra-low-alpha (3–6%) radial orbs (accent + one semantic tint) on `--color-bg`, drifting
  ±24px on a **120s loop** (`transform`/`opacity` only, `will-change: transform`). The login screen's
  orbs are the seed; the shell gets a far quieter sibling.
- Perceptually uniform (OKLCH/LCH) gradient stops so both themes keep equal perceived lightness
  (Arc's lesson) — stops authored in OKLCH with **sRGB hex fallbacks** for engines without OKLCH
  support (the token file ships both; the fallback is a static value, never a runtime switch).
- **Rules:** only behind the chrome (nav + header + page gutters), never under tables/cards (data
  needs a still bed); respects `prefers-reduced-transparency` (tier `minimal` → off); default **on
  for the shell, off for pages** — pages earn their own atmosphere, they don't inherit noise.

### 7.2 The login moment

The one screen allowed to be *warm*: on successful sign-in, the brand panel's orbs drift toward the
form panel over 800ms (the "let me in" beat) as the app fades in — a shared-element handoff between
the two most emotional frames the user sees.

---

## 8. Contextual sound & micro-vibrations (optional, future touch)

### 8.1 Sound policy

- **Default: off.** Audio is an explicit opt-in (`Settings → Sound`), and it respects the system
  "Reduce audio feedback" where exposed. No product feature ever *requires* sound to be understood
  (every moment's copy/icon carries the state — §1 rule 1).
- When on: **ultra-short synthesized blips** via the Web Audio API (no assets to load, tree-shaken):
  - L2 save: one soft 880Hz sine `tick`, 40ms, −24dB.
  - L4 milestone: two-note rise (660→880Hz), 120ms total.
  - L5: three-note arpeggio (523→659→784Hz), 200ms.
  - Errors: a single low 220Hz thud, 60ms — never a buzz.
- A `SoundProvider` gates all playback: one AudioContext, created on first user gesture (autoplay
  policy), suspended when the tab hides, ±6dB cap, no overlapping instances (a new sound cuts the
  previous).

### 8.2 Micro-vibrations (future touch devices)

The web standard `navigator.vibrate` exists today; the API contract is designed now so the mobile
app (React Native `Vibration`) and the web share one policy:

| Moment | Pattern | Apple HIG equivalent |
|---|---|---|
| L2 save/complete | `[15]` (one light tap) | Light impact |
| L4 milestone | `[15, 40, 15]` (double tap) | Medium impact |
| L5 summit | `[15, 40, 15, 40, 30]` | Success notification |
| Error | `[40]` (one firm) | Rigid/warning |

Rules: respect `prefers-reduced-motion` **and** the OS haptics toggle; never vibrate on hover;
never on destructive-confirm (the dialog is the moment, vibration would be punitive).

---

## 9. Performance constraints (the budget)

1. **Transform/opacity only.** Every Glint animation is a compositor property. The one exception
   (stroke-dashoffset checkmark draw) is `paint`-scoped to a 16px element — accepted and documented.
   Layout-affecting delight is a bug.
2. **Durations:** micro-beats 120–300ms; settles ≤ 300ms; bursts ≤ 900ms; the *only* loops are
   shimmer (1.4s), ambient drift (120s), and spinner (1s) — the Escapement's legal-loop list.
3. **Particle ceiling:** L5 bursts ≤ 80 particles, canvas or single-element CSS, one burst per
   moment, autodestruct. No persistent particle systems.
4. **Render budget:** delight never exceeds **3 concurrent animating movers** per viewport
   (Escapement's cap, applied to the Glint). Achievement + counter settle + shimmer may coexist;
   confetti + achievement + ambient + shimmer may not — the system dequeues (the oldest moment's
   exit wins).
5. **No layout shift:** counters are `tabular-nums`; checkmarks are absolutely positioned inside
   their dot; bursts are `position: absolute` + `pointer-events: none`.
6. **FID/LCP untouched:** nothing here runs on first paint (ambient excluded, gated to post-idle),
   nothing blocks input, nothing exceeds the 60fps frame budget (all measured in the visual
   regression suite).
7. **Tier contract (normative):** `precise` = everything. `efficient` = L1/L2 reduced to opacity
   ≤75ms, L3 shimmer → pulse, L4/L5 → caption + crossfade. `minimal` = instant state, sound/vibration
   off. Verified per tier in CI.

---

## 10. Architecture — files & APIs

```
apps/web/src/components/delight/
├── index.ts                     // public exports
├── confetti.tsx                 // <Confetti> — L5 bounded burst, canvas/CSS, autodestruct
├── achievement-toast.tsx        // <AchievementToast> — L4 toast, draw + glow, no stacking
├── checkmark.tsx                // <Checkmark draw> — L2 draw + L3 step ticker primitive
├── magnetic-button.tsx          // <MagneticButton> — L1 pull + elastic press (wraps Button)
├── counter-settle.tsx           // <CounterSettle> — L2 settle pulse on <AnimatedCount>
├── ambient.tsx                  // <Ambient> — shell orbs, 120s loop, tier-gated
├── shimmer.tsx                  // <Shimmer> — sweep band over skeleton blocks
├── step-ticker.tsx              // <StepTicker> — L3 live steps + draw-in checks
├── sound-provider.tsx           // <SoundProvider> — Web Audio, opt-in, gate, no assets
├── haptics.ts                   // vibrate() policy wrapper (web) / RN parity map
├── use-delight.ts               // level resolution + quota + dequeue (one per moment)
└── registry.ts                  // milestone registry — the L4/L5 allow-list
```

**The milestone registry** (the product's integrity guard):

```ts
export type DelightLevel = 'L1' | 'L2' | 'L3' | 'L4' | 'L5'
export interface Milestone {
  id: string                    // 'first-student', 'term-rolled-over', ...
  level: DelightLevel
  quota?: number                // per school-year per campus (L5: ≤3)
  once?: boolean                // per campus (first-of-kind)
  caption: (ctx) => string
}
// resolveMilestone(ctx) → Milestone | null   — quota-checked, registry-only
// celebrate(milestone) → dequeue + play (AchievementToast / Confetti)
```

`useDelight` returns `{ level, play, dequeue }` and enforces: one L4/L5 moment at a time, quota
checking against persisted counters (keyed `sdmas::milestones::<campus>` — same storage family as
`use-nav-persistence`), and tier gating via the existing `useMotionTier`.

**Integration points:** `ToastProvider` gains the drawn checkmark (L2); `Button` gains the settle
pulse; `AnimatedCount` gains the counter settle; pages call `celebrate(milestoneId, ctx)` after a
successful mutation instead of hand-rolling `showToast`; the shell mounts `<Ambient>`; Settings
gains the Sound toggle.

---

## 11. Accessibility

- **Tier-first:** `prefers-reduced-motion` (Escapement `efficient`) collapses every level to opacity
  ≤75ms; `minimal` is instant, silent, vibration-free. This is automatic, not a media-query
  afterthought.
- **Information is never carried by delight:** copy + icon always state the outcome (§1 rule 1);
  `role="status"` on achievement toasts; the drawn checkmark has an aria-hidden twin check via the
  toast's existing `aria-live="polite"`.
- **Sound:** opt-in, gain ≤ −24dBFS, per-blip duration ≤ 200ms, no loops, and a visible toggle.
  Haptics respect the OS toggle and never accompany destructive confirms.
- **Confetti:** `prefers-reduced-motion` users get the caption only; the burst is `aria-hidden`.
- **No keyboard regression:** magnetic pull is hover-only and never affects focus order; focus
  states are unchanged (the 120ms ring draw is the only focus change, and it's invisible to
  reduced-motion).

---

## 12. Do's & Don'ts

| Do | Don't |
|---|---|
| Assign every moment exactly one ladder level | Let pages invent their own celebrations |
| Keep L4/L5 rare and quota'd (registry) | Confetti for saves, submissions, or logins |
| Draw the checkmark, settle the counter | Pop, bounce, or shake routine completions |
| Shimmer sweep + step ticker for long work | Fake percentages, indefinite spinners |
| Transform/opacity only, ≤3 movers | Layout-animate, particle systems, ambient under data |
| Tier-gate everything through the Escapement | Delight that survives reduced-motion |
| Sound default-off, synthesized, no assets | Audio assets, overlapping blips, sound-first state |

---

## 13. Implementation roadmap

| Wave | Scope | Exit criteria |
|---|---|---|
| **W1 · Whisper + Soft (1 wk)** | Magnetic press + hover depth ladder (L1); checkmark draw in toast, button settle, counter settle (L2) | Every save ends with a drawn check + settle; counters settle once per session; tier-gated |
| **W2 · Bright (1 wk)** | Shimmer sweep over skeletons, determinate/indeterminate progress, step ticker | No opacity-pulse skeletons remain; report generation shows live steps |
| **W3 · Warm (1 wk)** | Milestone registry, quota/once persistence, AchievementToast + glow burst; wire first-of-kind (student/teacher/class/term/payment) | Registry-gated L4 fires once per campus; no stacking; survives reload |
| **W4 · Radiant (1 wk)** | Confetti component (≤80 particles, bounded burst), wire the 3 summit moments (term rollover, cohort graduation, 100% week) | ≤3 L5/year enforced in CI; caption always present |
| **W5 · Atmosphere & sound (1–2 wk)** | Ambient shell orbs (OKLCH, 120s, tier-gated); SoundProvider (opt-in, synthesized) + haptics policy; Settings toggles | Ambient never under data surfaces; sound off by default, gated, tab-aware |
| **W6 · Hardening (ongoing)** | Performance budget CI (≤3 movers, no layout), per-tier visual regression, a11y pass, mobile RN parity for haptics | The budget holds in CI; reduced-motion verified per tier |

**Sequencing:** W1–W2 are the felt-every-day layer (micro-beats, saves, loading) — the 80% of the
emotional surface. W3–W4 are the rare moments that make the product *unforgettable* (and they need
the registry from W3 before confetti is safe). W5 is atmosphere + the sound policy before anyone
asks for it. W6 keeps it honest.

---

## 14. Acceptance criteria

1. **Every moment has a level:** a page cannot emit a celebration the registry doesn't own; the
   ladder is enforced by type.
2. **Saves feel done:** every successful mutation ends in a drawn checkmark + one settle pulse, and
   nothing more.
3. **Counters roll once, settle always:** session-once roll; the numeral's spring settle is the
   punctuation.
4. **Loading is bright, not broken:** shimmer everywhere, live steps for multi-step jobs, no fake
   percentages.
5. **Milestones are rare:** L4 fires once per first-of-kind; L5 ≤ 3 per school-year per campus
   (CI-checked); both always captioned.
6. **Reduced motion gets the state, not the show:** every tier verified — `efficient` = opacity
   ≤75ms, `minimal` = instant/silent/still.
7. **The budget holds:** ≤ 3 concurrent movers, transform/opacity only, ≤ 80 particles, zero layout
   shift — all in the visual regression CI.
8. **Sound is an opt-in, never a requirement:** toggled in Settings, synthesized, asset-free,
   gated by tab visibility and user preference.
