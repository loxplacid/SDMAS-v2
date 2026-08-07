# SDMAS Design System — v3 Specification

**Codename:** *Corridor*
**Status:** Draft for review · **Owner:** Product Design · **Version:** 3.0.0
**Scope:** apps/web (desktop-first) · **Companion docs:** `docs/ARCHITECTURE.md`, `apps/web/src/index.css` (token seed)

> Every screen is a room. The system is the corridor that connects them — continuous, directional, calm.

---

## 0. How this system was derived

Three references were studied. We extracted **principles only** — no UI, no components, no visual language was copied. Each principle was then translated into an original, product-specific decision for a multi-tenant school management platform.

### Reference A — React Bits "Gooey Nav"
*What it demonstrates:* a navigation that behaves like a liquid — shapes deform and merge continuously through an SVG blur filter; one container morphs instead of vanishing; motion is the interface, not decoration.

| Extracted principle | Translation into SDMAS v3 |
|---|---|
| **Continuous identity** — one element morphs across states rather than dying and respawning | Containers morph, they never teleport: a row expands into a drawer, a table's skeleton is the table's own ghost, a menu *is* the button that opened it. |
| **Physics over keyframes** — organic deformation follows motion, not a fixed choreography | Micro-interactions use spring curves tuned to mass; nothing "pops" rigidly. |
| **Seamlessness via blur** — edges dissolve into their surroundings | Backdrop blur is a first-class material (see §11), used to fuse layers instead of boxing them. |
| **Play with purpose** — motion is the reward for interaction | Motion is budgeted and meaningful; ambient animation exists only where data is alive (live attendance, sync states). |

### Reference B — Boris FX "BCC Motion Blur ML"
*What it demonstrates:* physically-honest motion — optical flow detects direction, a "shutter" controls intensity, forward/backward vectors can be mixed, and blur separates the focused object from its surroundings.

| Extracted principle | Translation into SDMAS v3 |
|---|---|
| **Directional gravity** — motion has a direction and a source; nothing floats | Every transition enters from where it was invoked (drawers slide from the trigger edge, menus grow from the trigger). Exit is the reverse of entry — always. |
| **Velocity encodes hierarchy** — near layers move faster, far layers slower | Parallax: overlays travel 16px, the surface beneath 8px, the page behind 4px. Closer = faster. |
| **Shutter / intensity control** — blur amount is a tunable global | A global *motion budget* (§13) caps aggregate motion; every animation intensity is a token, not a hardcode. |
| **Focus through stillness** — the still object is the subject | When a dialog opens, the page behind is frozen (scroll-lock + dim) so the eye lands on the subject. |
| **"Better vs Faster" model** — performance is a design parameter | Two quality tiers: *precise* (desktop, full motion + blur) and *efficient* (reduced-motion or low-power: opacity-only ≤ 75ms). |

### Reference C — Impeccable ("Designing with…")
*What it demonstrates:* a design system as a living contract — tokens → components → surfaces; the spec is re-captured from the real product so it never drifts from code; a core loop of start → iterate → polish → maintain.

| Extracted principle | Translation into SDMAS v3 |
|---|---|
| **Capture the system, not the ideal** | This spec documents what ships. Every section has an adoption map (§22) tying it to real files today. |
| **Tokens first, components second, surfaces third** | All values are tokens; components consume tokens; no component may hardcode a value. |
| **The re-capture loop** | A governance cycle (§21): each UI PR updates the token reference; a monthly audit reconciles spec ↔ code and pays down design debt. |
| **Do's & Don'ts as first-class content** | §20 is normative, not advisory. |
| **Start → iterate → polish → maintain** | v3 ships in four waves (§22): foundations → primitives → patterns → refinement. |

### What we explicitly reject
- No blob menus, no liquid deformation in navigation.
- No motion blur applied to UI content (readability first).
- No gimmicky filter effects on text or interactive elements.

---

## 1. Visual philosophy

### 1.1 The statement

> **Quiet precision.** SDMAS is a school run at the quality of a bank. Interfaces are calm, ordered, warm, and legible — density where people work, air where people think. Every pixel earns its place; every animation says where you are and where you're going.

SDMAS is a *data-heavy operational tool* (attendance grids, fee ledgers, analytics, report builders, approval workflows) serving *diverse roles* (platform admin → teacher → accountant → parent → student). The visual language must therefore:

1. Make dense information feel effortless, not overwhelming.
2. Signal trust (money, grades, attendance are sensitive) through consistency and restraint.
3. Distinguish roles without fragmenting the system — one language, different density and emphasis.
4. Feel *premium* without feeling like a marketing site.

### 1.2 The four pillars

| Pillar | Meaning | Evidence in practice |
|---|---|---|
| **P1 · Precision over decoration** | Every pixel is intentional. Borders are hairlines, alignment is strict, typography carries hierarchy instead of color noise. | 8pt alignment, 1px hairline ring on all surfaces, single accent color. |
| **P2 · Directional gravity** | Motion always has a source, a direction, and a stop. The user can always reverse what they did. | Enter = reverse of exit; drawers/panels anchor to their trigger. |
| **P3 · Continuous identity** | A surface never dies and respawns — it morphs. The skeleton of a table is the table; a card expands into a drawer. | Skeleton mirrors layout; expandable rows; drawers that inherit the row's identity. |
| **P4 · Calm density** | Information is dense; *perception* is not. White space is a functional tool that creates reading rhythm. | Density modes (§8.3); editorial type scale; numeric discipline (§7.4). |

### 1.3 Design tensions (and their resolutions)

| Tension | Resolution |
|---|---|
| Warmth vs. trust | Warm **surfaces**, cool **ink**, electric **accent**. Warmth lives in backgrounds, trust in type. |
| Density vs. calm | Density is a user setting (§8.3), never an emergency. Default UI stays airy; ledgers default to compact. |
| Data density vs. mobile | Desktop is the native home; mobile is a *portal* (read + act on one thing), not a mirror (§19). |
| Delight vs. speed | Motion is under 500ms and directional. Speed is the delight. |

---

## 2. Design token architecture

### 2.1 Naming convention

```
{domain}.{role}.{modifier}
```

Examples:

| Domain | Role | Modifier | Token |
|---|---|---|---|
| `surface` | canvas / card / raised / overlay | — | `surface.card` |
| `text` | primary / secondary / tertiary / muted / inverse / on-accent | — | `text.secondary` |
| `border` | hairline / strong / hover | — | `border.hairline` |
| `accent` | base / hover / subtle / ring | — | `accent.ring` |
| `status` | success / warning / danger / info | fg / bg / ring | `status.success.fg` |
| `type` | scale / weight / leading / tracking | size | `type.scale.sm` |
| `space` | xs … 3xl | — | `space.md` |
| `radius` | control / surface / overlay / pill | — | `radius.surface` |
| `elevation` | rest / hover / floating / overlay / command | shadow / ring | `elevation.floating.shadow` |
| `motion` | duration / easing | name | `motion.duration.base` |
| `blur` | sm / md / lg | — | `blur.lg` |
| `glow` | focus / accent / success | spread | `glow.accent` |
| `z` | 0 … 60 | — | `z.overlay` |

### 2.2 Token classes

| Class | Behavior | Example |
|---|---|---|
| **Primitive** | Raw values, no meaning (a hex, a px, a bezier) | `brand.500 = #4F7AFF` |
| **Semantic** | Meaningful aliases resolved by theme | `accent.base = brand.500` (light) |
| **Component** | Consumed only by a single component | `table.row.hover-bg` |
| **Motion** | Durations/easings consumed by choreography | `motion.duration.base = 180ms` |

**Rule:** components reference *semantic* and *component* tokens only. Primitives are never referenced in components. This is what makes dark mode and future theming trivial.

### 2.3 Theme model

- Two themes: `light` and `dark`, selected via `data-theme` attribute (system default, user override, persisted).
- Only semantic tokens change between themes; primitives are shared.
- Dark mode is a **first-class theme**, not an inverted light mode (§6).
- Future-proofing: the same structure supports brand variants (per-institution theming in multi-tenant deployments) without touching components.

---

## 3. Color palette

### 3.1 Brand (navy + electric)

| Token | Light value | Use |
|---|---|---|
| `brand.950` | `#0B1030` | Deepest ink for dark-mode canvas, login backdrop base |
| `brand.900` | `#131F45` | Dark-mode elevated surfaces (with tint) |
| `brand.800` | `#1D2B6B` | Dark-mode surface hover |
| `brand.700` | `#2A4CC0` | Accent hover (dark mode) |
| `brand.600` | `#3560E8` | Accent hover (light mode) |
| `brand.500` | `#4F7AFF` | **Primary accent** — one job: action & selection |
| `brand.400` | `#6E8FFF` | Accent on dark surfaces |
| `brand.300` | `#94B0FF` | Accent text on dark |
| `brand.200` | `#BCCEFF` | Selected chart tint / active fills |
| `brand.100` | `#DCE6FF` | Accent-tinted surfaces, chart grid accents |
| `brand.50` | `#EEF3FF` | Accent-tinted page wash, KPI card tints |

**The accent rule:** electric blue is used for *action, selection, and the active state — nothing else*. It never colors paragraphs, never decorates, never appears as a background without a purpose.

### 3.2 Ink — warm-tinted neutrals

Warm is achieved through a *yellow undertone*, never beige-on-cold type.

| Step | Light value | Role |
|---|---|---|
| `ink.0` | `#FFFFFF` | Card surface |
| `ink.50` | `#F7F7F4` | Canvas (page background) |
| `ink.100` | `#F1F0EB` | Canvas alt / hover wash |
| `ink.200` | `#E7E6DF` | Border strong, hover borders |
| `ink.300` | `#D8D6CC` | Hairline borders, dividers |
| `ink.400` | `#B9B6AA` | Disabled text |
| `ink.500` | `#8F8C80` | Muted / tertiary text |
| `ink.600` | `#64625A` | Secondary text |
| `ink.700` | `#3F3E39` | Primary text (secondary emphasis) |
| `ink.800` | `#24241F` | Primary text |
| `ink.900` | `#14140F` | Near-black ink, headings |
| `ink.950` | `#0B0B08` | Print / inverse surfaces |

### 3.3 Semantic (status) ramps

Each status ships `fg`, `bg`, `ring` resolved tokens plus a full ramp.

| Status | Base | bg (light) | bg (dark) | Meaning in SDMAS |
|---|---|---|---|---|
| `success` | `#0F973D` | `#E9F9EE` | `#052E16` | Paid, cleared, complete, present |
| `warning` | `#D97706` | `#FEF6E6` | `#341A00` | Due, pending, partial, attention |
| `danger` | `#DC2626` | `#FAE8E8` | `#2D0909` | Overdue, failed, absent, blocked |
| `info` | `#0284C7` | `#E0F2FE` | `#0C334E` | In progress, informational |

**Status rule:** status colors are *reserved for status*. They never double as decoration, and success/danger are never used for emphasis (that's accent's job).

### 3.4 Data-visualization palette (charts)

Designed for categorical charts in analytics/attendance/finance. Colorblind-safe (Okabe-Ito inspired), distinct in both themes.

| Slot | Light | Dark | Canonical use |
|---|---|---|---|
| `dv.1` | `#4F7AFF` | `#6E8FFF` | Primary series (accent-adjacent) |
| `dv.2` | `#0FB5AE` | `#2DD4BF` | Secondary series |
| `dv.3` | `#F59E0B` | `#FBBF24` | Tertiary |
| `dv.4` | `#8B5CF6` | `#A78BFA` | Quaternary |
| `dv.5` | `#F43F5E` | `#FB7185` | Alert series |
| `dv.6` | `#10B981` | `#34D399` | Positive series |
| `dv.7` | `#64748B` | `#94A3B8` | Baseline / comparison |
| `dv.8` | `#E11D48` | `#F43F5E` | Critical series |

Rules: max 6 categorical series per chart; above that, aggregate into "Other" with a tooltip breakdown. Never encode information by hue alone — pair with patterns, labels, or direct annotation.

### 3.5 Contrast & accessibility floors

| Usage | Contrast floor |
|---|---|
| Body, small text (< 18px) | ≥ 4.5:1 (AA) |
| Large text (≥ 18px / bold ≥ 14px) | ≥ 3:1 |
| UI components, icons, borders that encode state | ≥ 3:1 |
| Disabled (not required to meet AA, but) | label must stay ≥ 3:1 against bg |
| Financial figures (ledgers, receipts) | ≥ 4.5:1 always |

---

## 4. Dark mode

### 4.1 Philosophy

Dark mode is not an inverted light mode. It is a **night light for a school office** — deep navy ink instead of pure black, warm-tinted shadows, electric glow where light mode uses hairline borders.

### 4.2 Surface model — luminance-based elevation

In dark mode, shadows are nearly invisible; **elevation is encoded by luminance and hairline**.

| Layer | Dark surface | vs. canvas |
|---|---|---|
| Canvas | `#0B1030` (brand.950) | baseline |
| Card | `#11163A` | +1 luminance step |
| Raised | `#171D47` | +2 |
| Overlay (modal/drawer) | `#1A2052` | +3 |
| Command palette | `#1A2052` + 24px blur | +3 + material |

### 4.3 Rules

1. Hairline rings (`border.hairline`) become *brighter* than the surface they outline (they define edges that shadows would in light mode).
2. Text uses warm ink (blue-tinted whites: `#E4E6EF` primary, `#9EA3BF` secondary) — never pure white (halation).
3. Accent must *lift* one step (`brand.400` for text, `brand.500` for fills) to hold contrast.
4. Glow (§11.3) is legal in dark mode; in light mode it is nearly always forbidden.
5. Charts swap to dark palette (`dv.*` dark column) automatically via theme.

---

## 5. Typography

### 5.1 The voice

Inter. A grotesque with strong numerics and a warm, human feel at small sizes — right for a product that mixes prose, tables, and IDs. It is the *only* UI family; distinction comes from weight, size, and tracking, not font changes.

| Family | Stack | Use |
|---|---|---|
| UI | Inter (variable) | Everything interactive and informational |
| Display | Inter, tight tracking | Page titles, KPI numerals, login |
| Mono | JetBrains Mono | Receipt refs, student/teacher IDs, hashes, code, timestamps in dense tables |

### 5.2 Type scale

Base unit 14px body. Editorial scaling with generous leading (v3 signature).

| Step | Size / Line-height | Tracking | Use |
|---|---|---|---|
| `display` | 40 / 44 | −0.03em | Login hero, report cover pages |
| `h1` | 26 / 32 | −0.02em | Page title (single, per page) |
| `h2` | 22 / 28 | −0.02em | Section title |
| `h3` | 18 / 24 | −0.01em | Card title |
| `h4` | 16 / 22 | −0.01em | Group label within cards |
| `body-lg` | 16 / 26 | 0 | Empty-state copy, dialogs |
| `body` | 14 / 22 | 0 | Default UI text |
| `body-sm` | 13 / 20 | 0 | Table cells, form hints |
| `caption` | 12 / 16 | +0.01em | Meta, timestamps, helper text |
| `micro` | 11 / 14 | +0.04em (uppercase) | Eyebrows, section labels, column headers |
| `tabular` | inherits size | `font-variant-numeric: tabular-nums` | **All** numerals in ledgers, KPIs, dates, IDs |
| `mono` | 13 / 20 | 0 | IDs, refs, hashes |

### 5.3 Weights

400 regular · 500 medium (default for controls) · 600 semibold (headings, emphasis) · 700 bold (KPI numerals, active nav). Avoid 800+ except display numerals.

### 5.4 Numeric discipline

- **All** financial figures, counts, dates, and identifiers render with `tabular-nums`.
- KPI numerals use 600–700 weight, `display`-ish size with −0.02em tracking, right-aligned in their cells.
- Currency is rendered with a currency code in the column header, not repeated per cell (`₹ 1,250.00` only in receipts/invoices where context demands).

---

## 6. Spacing system

### 6.1 The grid

Base unit **4px**. All spacing tokens are multiples of 4. Layout alignment is enforced on an 8px macro-grid; micro-spacing (inside controls) uses 4px steps.

| Token | Value | Typical use |
|---|---|---|
| `space.2xs` | 4 | Icon-gap, avatar stacking |
| `space.xs` | 8 | Control padding, chip gaps, form gap |
| `space.sm` | 12 | Card padding (compact), table cell padding |
| `space.md` | 16 | Default control padding, card padding |
| `space.lg` | 24 | Section gaps, card grid gutters |
| `space.xl` | 32 | Page section spacing, dialog padding |
| `space.2xl` | 48 | Page → header gap, form section breaks |
| `space.3xl` | 64+ | Empty states, hero spacing |

### 6.2 Rhythm rules

1. Vertical rhythm between stacked blocks = `space.lg` (24). Between sub-blocks = `space.sm` (12).
2. Page content max-width 1280, padding `space.xl` (32) at desktop, `space.lg` (24) at tablet.
3. Card padding: `space.md` (16) default, `space.sm` (12) compact tables.
4. Never space by eye; always by token.

### 6.3 Density modes

A real user setting (persisted), not an emergency mode:

| Mode | Row height | Cell padding | Typography |
|---|---|---|---|
| **Comfortable** (default for portals/360 views) | 48 | 16×12 | body |
| **Compact** (default for ledgers, audit logs, batch ops) | 36 | 12×8 | body-sm, tabular |

Switching density animates row heights (transform-friendly, §13) and never changes meaning. Density lives in `:root` via a single attribute.

---

## 7. Border radius

### 7.1 The scale

| Token | Value | Used by |
|---|---|---|
| `radius.control` | 8 | Inputs, buttons, selects, chips, cells |
| `radius.surface` | 12 | Cards, panels, popovers |
| `radius.overlay` | 16 | Dialogs, drawers, command palette |
| `radius.pill` | 999 | Badges, tabs (pill variant), avatars |
| `radius.squircle` | ~22% of size | App icons, product logos, KPI glyphs |

### 7.2 The rule

**Radius communicates containment.** Controls are tighter than the surfaces they sit on; overlays are the softest. A card is always more rounded than the buttons inside it. Never mix: an input (8) inside a card (12) inside a dialog (16) is the canonical stack.

---

## 8. Elevation & shadows

### 8.1 The recipe

Every shadow is **two layers + a hairline ring**:

```
shadow = ring(1px, border color) + diffuse(soft, low-opacity) + key(larger, lower-opacity)
```

The 1px hairline is the v3 signature: it keeps surfaces crisp on any background, in both themes, and survives print.

### 8.2 Elevation scale

| Layer | Light shadow | Dark strategy |
|---|---|---|
| `elevation.rest` (cards on canvas) | hairline only | hairline (brighter) only |
| `elevation.hover` | +1px diffuse | luminance +1 + hairline |
| `elevation.floating` (menus, tooltips, toasts) | 4px diffuse + hairline | luminance +2 + hairline |
| `elevation.overlay` (modals, drawers) | 16px diffuse + hairline | luminance +3 + hairline |
| `elevation.command` (palette) | 24px diffuse + 24px blur | luminance +3 + blur + hairline |
| `elevation.spotlight` (coach marks, onboarding) | 40px + colored glow | glow + hairline |

### 8.3 Z-index ladder

`0` canvas · `10` sticky header · `20` drawers/tables with sticky chrome · `30` dropdowns/popovers · `40` modals/drawers · `50` toasts · `60` command palette/spotlight. No z-indexes outside the ladder; no z-index in components other than these tokens.

---

## 9. Material: blur, glow, gradients

### 9.1 Blur

Backdrop blur is a *material*, not an effect. It exists to fuse layered chrome with content that scrolls beneath it.

| Token | Radius | Where it's legal |
|---|---|---|
| `blur.sm` | 4 | Sticky table headers (subtle) |
| `blur.md` | 12 | App header, drawer header, mobile bottom bar |
| `blur.lg` | 24 | Command palette, spotlight/coach-mark backdrop |

Rules: blur is **always** paired with a 60–80% tint of the surface behind it + a hairline; blur never sits on an opaque element (it would be invisible waste); blur never applies to text-bearing surfaces at `blur.sm`.

### 9.2 Glow

Glow is the dark-mode cousin of the hairline. Light mode: glow is forbidden except the success pulse (§13.6). Dark mode:

| Token | Use |
|---|---|
| `glow.focus` | Focus rings — 2px accent ring + 12px accent glow at 25% |
| `glow.accent` | Primary button hover, active nav rail indicator |
| `glow.success` | "All clear" / sync-complete moments (one pulse, then rest) |
| `glow.live` | Live indicators (recording attendance, streaming sync) |

### 9.3 Gradients

Two families, both **2-stop, low-contrast, luminance-safe**:

1. **Dawn** (brand): `brand.950 → brand.600` — login backdrop, empty-state canvases, report cover pages, chart area-fill undertones.
2. **Surface tint** (neutral): `ink.50 → ink.100` — subtle card differentiation, section headers in reports.

Rules: never on text under 18px; never on interactive elements (buttons get flat + hover, not gradients); gradients are decorative and must degrade gracefully to a flat color in `prefers-reduced-data` and print.

---

## 10. Iconography

### 10.1 Specification

- Stroke-based, **1.5px** weight, 24px grid, drawn at 20px visual size.
- Rounded caps and joins (2px), 45°-standardized corners.
- Sizes: `16` (inline, table actions) · `20` (default) · `24` (headers, empty states).
- Monochrome by default; inherits `currentColor`. **Never multicolor** except status dots.
- A single `icon` token per role: `icon.default`, `icon.secondary`, `icon.muted`, `icon.on-accent`.

### 10.2 Usage rules

1. Icons support, they never replace text (with the exception of universal glyphs: search, bell, chevrons, close, plus).
2. Icon + label: icon sits 8px before text, same height, `currentColor`.
3. Icon-only buttons: 36px hit target, tooltip required, `aria-label` required.
4. Animated micro-icons (legal set only): bell *settle* on new notification, spinner for loading, check *draw* on success, chevron *rotate* on expand.
5. Duotone accent variant exists for 360-hub and KPI cards only — glyph in accent-tint, key shape in ink.

---

## 11. Motion

### 11.1 Motion principles

| # | Principle | Rule |
|---|---|---|
| M1 | **Directional gravity** | Enter from the trigger; exit reverses entry. Never both-fade for spatial changes. |
| M2 | **Velocity = hierarchy** | Closer layers move faster (parallax: overlay 16px, surface 8px, page 4px). |
| M3 | **Transform only** | Animate `transform` and `opacity` exclusively. Never `width/height/top/left` (layout thrash). |
| M4 | **Short distances** | Standard travel 8–24px. Large movements are split into staged reveals. |
| M5 | **One subject per moment** | One element animates emphasis; the rest respond. No choreographed chaos. |
| M6 | **Budgeted shutter** | Global motion budget: aggregate movement per interaction is capped; ambient loops only for live data. |
| M7 | **Reduced motion is a mode, not a hack** | `prefers-reduced-motion: reduce` collapses all motion to opacity-only ≤ 75ms; `prefers-reduced-transparency` disables blur; `prefers-reduced-data` disables decorative gradients/loops. |

### 11.2 Tokens

| Duration | Value | Use |
|---|---|---|
| `instant` | 75ms | Color/hover/border micro-states |
| `fast` | 120ms | Focus, pressed, small toggles |
| `base` | 180ms | Buttons, chips, inline feedback |
| `slow` | 260ms | Menus, tooltips, table row transitions |
| `slower` | 380ms | Dialogs, drawers, toasts |
| `slowest` | 500ms | Page transitions, KPI count-ups (soft cap) |

| Easing | Curve | Use |
|---|---|---|
| `ease.standard` | cubic-bezier(0.2, 0, 0, 1) | Default UI motion |
| `ease.enter` | cubic-bezier(0.05, 0.7, 0.1, 1) | Elements arriving |
| `ease.exit` | cubic-bezier(0.3, 0, 0.8, 0.15) | Elements leaving |
| `ease.spring` | cubic-bezier(0.34, 1.56, 0.64, 1) | Micro-springs: toggles, badges, count chips |
| `ease.linear` | linear | Spinners, shimmer only |

### 11.3 Choreography library (the canonical moves)

| Move | Recipe |
|---|---|
| Page enter | fade + rise 8px, `slower`, `ease.enter` (View Transitions API) |
| List stagger | rows enter at 24ms stagger, `fast→slow`, fade + rise 4px |
| Modal | overlay fade (`base`), surface scale 0.96→1 + fade, `slowest`, spring at 70% |
| Drawer | slide from trigger edge + parallax (overlay 16px, page 8px), `slower`, `ease.enter` |
| Menu/popover | scale 0.98→1 + fade from trigger anchor, `slow`, `ease.enter` |
| Toast | slide-in from edge 16px, `slower`; auto-dismiss `slowest` exit |
| KPI count-up | 500ms `ease.enter` + tabular numerals (never more than 500ms) |
| Table row enter/update | fade, `fast`; cell value changes fade-through-50% (value "pulse") |
| Skeleton | shimmer sweep 1.6s loop, opacity 40→80 |
| Success pulse | single glow ring expand-and-fade, 1.2s, once |
| Attention ring | on the active nav item, expand 8px ring once, 2s |

---

## 12. Components

### 12.1 Buttons

| Variant | Surface | Text | Hover | Pressed | Note |
|---|---|---|---|---|---|
| `primary` | `accent.base` | `on-accent` | +1 shade | scale 0.97 | One primary per view |
| `secondary` | `surface.card` + hairline | `ink.800` | bg tint + border strong | scale 0.97 | Default action |
| `ghost` | transparent | `ink.600` | bg wash | scale 0.97 | Secondary actions in toolbars |
| `outline` | transparent | `ink.800` | hairline→accent, text→accent | scale 0.97 | Boundary emphasis |
| `danger` | `status.danger.fg` | white | darker shade | scale 0.97 | Destructive, needs confirm dialog |
| `success` | `status.success.fg` | white | darker shade | scale 0.97 | Reserved for completion moments |

Sizes: `sm` 32 / `md` 36 / `lg` 44 (heights). Loading state: spinner + label preserved (label dims to 90%, never swaps layout). Icon-only: 36×36 square. Buttons never stretch taller than 44px.

**Rules:** one primary per view · destructive actions are `danger` *and* gated by a confirm dialog · disabled buttons keep label contrast ≥ 3:1 (§3.5).

### 12.2 Inputs

- Anatomy: label (micro, uppercase optional) → field → hint/error. Label always visible (no floating-label pattern — faster scanning for a data tool).
- Field: 36px height, `radius.control` (8), hairline border, `ink.0` surface, 14px text.
- Focus: 2px accent ring at 2px offset (light) or accent glow (dark). No border-color-only focus — **never**.
- States: hover (border strong) → focus (ring) → filled (no special color) → error (danger ring + message, field stays `ink.0`) → disabled (45% + no shadow).
- Types: text, search (with ⌘K affordance in the app header), select (custom popover, §12.9), textarea (min 3 rows, auto-grow), password (reveal toggle), date (native calendar with formatting per locale), number (tabular).
- Prefix/suffix: currency, units, or icons sit inside the field separated by a hairline — never floating outside it.

### 12.3 Cards

| Card | Anatomy | Use |
|---|---|---|
| `surface` | hairline, `radius.surface`, no shadow at rest | Containers for content groups |
| `interactive` | hover: elevation.hover + cursor; arrow slides 4px | Navigable tiles, lists |
| `kpi` | big tabular numeral + label + sparkline + delta chip | Dashboards |
| `hub` | duotone icon, title, 2-line description, chevron | 360/feature navigation |
| `split` | accent 3px top rail | "This needs your attention" |

Card header pattern: title (h3) left, actions right (ghost sm). Cards never nest more than one level.

### 12.4 Tables — the workhorse

Tables are the most important component in SDMAS (ledgers, rosters, audit logs, fee dues). They get their own discipline:

- **Structure:** sticky header (blur.sm tint), hairline row dividers only (no vertical gridlines), left-aligned text, right-aligned numerics, sticky action column on the right.
- **Density:** Comfortable 48 / Compact 36 (§6.3). Default: Compact for ledgers and audit, Comfortable for people (students/teachers).
- **Selection:** checkbox column only when batch ops exist; selected rows get accent-tint wash, never full accent fill.
- **Row hover:** `ink.50` wash. Row actions (edit/delete/…): ghost icon buttons revealed on hover, always visible on touch devices.
- **Status cells:** pill badges with `status.*.bg` + `status.*.fg` — never raw colored text alone.
- **Empty/loading:** the table's skeleton *is* the table (§13.1). Empty state lives in the table body area.
- **Sorting/filtering:** column headers sortable; active sort shows arrow + accent; filters are a toolbar above the table, never inline in cells.
- **Pagination:** page-size selector (20/50/100) + keyset-style "prev/next with running count". Jump-to-page only for expert mode.

### 12.5 Dialogs

| Type | Anatomy | Motion |
|---|---|---|
| `modal` | overlay (ink.950 @ 45–60%) + surface `radius.overlay`, max-width 560, scroll-locked page | scale-in + fade; exit fade + scale-out |
| `confirm` | modal + danger accent, primary action is the dangerous one, autofocus on cancel | same as modal |
| `drawer` | anchored to trigger edge, 480px default, parallax page | slide + parallax |
| `command` | centered palette, 640px, blur.lg material, list of results | fade + rise, list stagger |
| `toast` | floating stack, bottom-right (desktop) / top (mobile), auto-dismiss | slide-in + glow ring for success |

Rules: one dialog at a time (except toasts) · escape closes · focus trapped and restored · destructive actions in confirm dialogs always ask again · dialogs carry a header (title + close) even when the title is visually minimal.

### 12.6 Navigation & app shell

- **Shell:** sidebar (256px) + header (60px) + content. Sidebar collapses to 68px rail with tooltips.
- **Header:** breadcrumbs left, global search (⌘K), notification bell, campus/organization switcher, user menu right. Header gains `blur.md` + hairline on scroll.
- **Breadcrumbs:** page > section > item, always complete, truncation at the item level.
- **Command palette (⌘K):** routes, students, teachers, quick actions (record attendance, new fee, batch enroll), recent items. Keyboard-first.
- **Organization switcher:** current campus with identity chip; switching is a page-level event (route change + reload of tenant-scoped data), so it's visually loud but safe.
- **Contextual actions:** primary action is docked bottom-right on mobile, top-right on desktop — never both.

### 12.7 Sidebars

- Groups with uppercase micro labels; items: icon (20) + label + optional badge count.
- Active item: accent-tinted wash + 3px left rail + icon at full opacity. (The rail grows in with `active-indicator` motion.)
- Collapse/expand: width animates (transform-based), icons center, tooltips replace labels.
- Secondary/inset nav (within a section, e.g. reports list): no icons, 32px rows, indented.

### 12.8 Tabs

- **Underline tabs** (default): hairline track, 2px accent underline on active with 24px travel transition. Used for sub-sections of a page.
- **Pill tabs** (segmented): container `ink.100`, active pill = `ink.0` + hairline + elevation.hover. Used for view switches (List/Grid, Day/Week/Month).
- Tabs use arrow-key navigation; `role="tablist"` semantics with full keyboard support.

### 12.9 Graphs (chart language for Recharts)

- **Gridlines:** horizontal only, `ink.200`, dashed→solid at 1px. No vertical gridlines.
- **Axes:** labels in `caption` (12px), muted; axis titles only when unit isn't obvious.
- **Tooltip:** floating card (`radius.surface`, elevation.floating), tabular numerals, series color swatches, hairlines aligned to data point.
- **Series:** categorical palette §3.4; max 6 series; area fills use 20% gradient tints of their stroke.
- **Interaction:** hover crosshair + highlight of hovered series (others dim to 40%); click-through to detail.
- **Draw-in:** lines draw left→right 500ms `slowest`, points fade in after; bars grow from baseline.
- **Sparklines** in KPI cards: 1.5px stroke, no axes, 40px tall, right side of numeral.
- **Empty chart:** no empty frame — show the empty state (§13.2) instead of an unlabeled plot area.

### 12.10 Notifications

Three layers:

1. **Toast (transient):** action feedback. Four statuses with icon + title + optional action. Auto-dismiss 5s (warning/danger persist). Max 3 visible; queue silently beyond.
2. **Bell + center (persistent):** unread dot (accent, 8px), bell settle-animation on arrival. Center is a drawer: today / earlier groups, per-item actions (mark read, deep-link).
3. **Ambient:** subtle status line for long jobs ("Exporting 1,240 rows…") with progress, cancellable.

---

## 13. Feedback states

### 13.1 Loading states

- **Skeleton-first:** every data surface ships a skeleton that mirrors its final layout *exactly* (same rows, same cells, shimmer sweep). The skeleton is the component's ghost (P3).
- Skeletons use `ink.100`/`ink.200` blocks, `radius.control`, 1.6s shimmer.
- Buttons: spinner + preserved label. Full-page load: skeleton shell, never a centered spinner.
- **Progress:** long operations get a thin 2px accent progress bar pinned under the header (indeterminate ≤ 2s, determinate beyond).

### 13.2 Empty states

Anatomy: illustration (original line-art, duotone accent) → title (h3) → one-line body → single primary action (+ optional "how it works" 3-step row for first-run). Empty states are **moments of orientation, not dead ends** — they always offer the next step. First-run pages additionally show a compact onboarding card that dismisses.

### 13.3 Error states

| Layer | Recipe |
|---|---|
| Field-level | danger ring + message below field, message ≥ 3:1 |
| Inline banner | `status.danger.bg` tint, icon, message, retry link |
| Full-page | illustration, what happened (plain language), correlation ID (mono), retry + back to safe place |
| Offline | global banner, queues writes with explicit "sent when online" state |
| Partial failure (batch ops) | success summary with failure table: "1,240 imported · 3 failed — download errors" — never all-or-nothing |

Error copy rules: state what happened, what was affected, and the next action. Never "An error occurred."

### 13.4 Success states

- Toast (success, check-draw icon) + optional glow pulse for completion moments (payment recorded, export ready).
- Inline: green check + status change reflected in the table row (the row's status badge is the success state).
- Batch completion: summary card with stats, not fireworks.

### 13.5 Interaction states (focus / hover / pressed / disabled)

| State | Buttons | Inputs | Cards / rows | Nav items |
|---|---|---|---|---|
| **Focus** | 2px accent ring, 2px offset | ring + glow (dark) | same | same |
| **Hover** | +1 shade (primary) / bg wash (ghost) | border strong | elevation.hover + wash | bg wash + text brighten |
| **Pressed** | scale 0.97 (never on dense tables) | border strong, no scale | wash deepens | wash deepens |
| **Disabled** | 45% opacity, no shadow, pointer-events off | 45%, no ring | no hover | muted icon only |

Every interactive element has all four states defined. Hover is never the only affordance (touch parity): reveal-on-hover actions are always discoverable by keyboard focus.

---

## 14. Accessibility

1. **Contrast:** floors per §3.5. Verified for both themes at every release.
2. **Focus visibility:** every interactive element has a visible focus ring. Focus order follows visual order (sidebar → header → content → overlays).
3. **Semantics:** native elements or full ARIA patterns (dialog, tablist, combobox, alert, tooltip, menu). No `div`-only interactions.
4. **Targets:** ≥ 44px touch, ≥ 32px pointer for standalone controls; row-level actions keep row itself tappable.
5. **Color is never the sole signal:** status = icon + text + color; chart series = label + color.
6. **Reduced motion / transparency / data:** M7 mode collapse (§11.1). All animation legal in `ease.exit`-only under reduced motion.
7. **Zoom:** 200% zoom with no loss of function; tables scroll horizontally, never compress.
8. **Screen readers:** toasts announce via `role="status"`; live counts via `aria-live="polite"`; loading regions `aria-busy`; form errors linked via `aria-describedby`.
9. **Dyslexia & reading:** never justify text, never letter-space body copy, generous line-height (§5.2).
10. **Language/locale:** currency, dates, and name ordering are locale-driven end to end.

---

## 15. Keyboard navigation

| Context | Behavior |
|---|---|
| Global | `⌘K` command palette · `g` then `s`/`t`/`f`/… route jumps · `/` focuses search · `?` shortcuts help · `⌘/` theme toggle |
| Tables | `↑↓` move rows · `Space` select · `Enter` open row · `F` focus filter toolbar |
| Dialog/drawer | `Esc` close · `Tab` trapped · focus returns to trigger · first actionable autofocused (except destructive: focus cancel) |
| Tabs | `←→` switch · `Home/End` bounds · `Tab` exits the group |
| Select/combobox | Typeahead · `↑↓` navigate · `Enter` select · `Esc` close |
| Sidebar | `↑↓` + `Enter`; section skip via landmarks (`H` headings) |
| Command palette | `↑↓` + `Enter` + `Esc`; `Tab` falls through to panel actions |

All shortcuts are discoverable (the `?` dialog), and none hijack browser/assistive defaults without an off switch.

---

## 16. Responsiveness

**Philosophy:** desktop is the native canvas (premium desktop app); tablet and mobile are *portals* — read and act on one thing at a time, never a squeezed desktop.

| Breakpoint | Layout strategy |
|---|---|
| ≥ 1280 (desktop) | Full shell: sidebar + header + content; tables full |
| 768–1279 (tablet) | Sidebar collapses to rail by default; tables gain column picker; drawers → full-width |
| < 768 (mobile) | Sidebar → overlay drawer + bottom tab bar (4 max, "More"); tables → card list with primary fields + swipe actions; sticky bottom primary action; FAB only for single-create screens |

- Mobile tables: a card list is a *different component*, not a media query squeeze.
- Portals (parent/student): single-column, large type (body 16), thumb-friendly targets, offline-friendly (service worker — already present via PWA).
- Print: reports, receipts, and rosters print cleanly — `@media print` strips chrome, keeps tabular numerals, page-break-aware rows.

---

## 17. Do's & Don'ts

**Do**
- Use the hairline ring on every raised surface.
- Right-align numerals, tabular-nums everywhere (§5.4).
- Enter from the trigger; exit in reverse (§11.1).
- Show the skeleton *of the actual layout*.
- Gate destructive actions behind confirm dialogs.
- Give every empty state a next step.
- Keep one primary action per view.
- Let dark mode use glow; forbid it in light mode (§4.3).
- Make disabled states readable (§3.5).

**Don't**
- Don't use accent color as decoration — action and selection only.
- Don't animate layout properties (§M3).
- Don't reveal actions only on hover without keyboard/touch parity.
- Don't color status without an icon or text companion.
- Don't use more than 6 categorical series per chart.
- Don't open more than one dialog at a time.
- Don't center long-form text or justify body copy.
- Don't hardcode values — tokens or it doesn't ship (§2.2).

---

## 18. Governance — the re-capture loop

Adapted from Reference C's core loop (start → iterate → polish → maintain):

1. **Capture:** every UI change in a PR updates the relevant token reference in this spec. A PR that changes a color/radius/duration *without* updating the spec is blocked.
2. **Iterate:** v3 ships in four waves (§22); each wave ends with a spec-vs-code reconciliation.
3. **Polish:** monthly design-debt audit — scan for drift (hardcoded values, off-grid spacing, non-token colors) and log debt items with severity.
4. **Maintain:** the spec is versioned with the app (`3.0.x`); breaking visual changes bump the minor; new tokens bump the patch. `prefers-reduced-*` support is a non-negotiable release gate.

---

## 19. Versioning & changelog

| Version | Change |
|---|---|
| 3.0.0 | Initial v3 specification (this document) |

---

## 20. Adoption map — current codebase → v3

Grounded in the repo today (`apps/web`): the v3 token seed already exists in `src/index.css` (navy brand, warm surfaces, editorial scale, spring physics). This map completes and disciplines it.

| Area today | v3 change |
|---|---|
| `index.css` tokens | Adopt naming convention §2.1; split primitives/semantics; add `blur.*`, `glow.*`, `dv.*` (charts), density tokens §6.3 |
| `button.tsx` variants | Map to §12.1; standardize heights (32/36/44), disabled contrast floor |
| `table.tsx` | Add sticky-header blur, numeric discipline, density modes, skeleton ghost |
| `input.tsx`, `select.tsx`, `form.tsx` | Label-above pattern, ring-only focus, prefix/suffix hairline |
| `modal.tsx`, `drawer.tsx`, `confirm-dialog.tsx` | Radius/overlay scale §7, parallax motion, focus trap audit |
| `sidebar.tsx`, `header.tsx`, `app-layout.tsx` | Blur-md chrome on scroll, active rail motion, collapse→rail parity |
| `toast.tsx`, `notification-bell.tsx` | Status iconography + glow pulse, max-3 queue, ambient progress |
| `skeleton.tsx` | Layout-mirroring ghosts per component (P3) |
| `kpi-card.tsx`, `*-chart.tsx` (Recharts) | §12.9 chart language: palette, tooltip, draw-in, empty-state |
| `empty-state.tsx`, `error-state.tsx` | §13.2–13.4 copy + illustration standards |
| `command-palette.tsx`, `keyboard-shortcuts-dialog.tsx` | §15 keyboard spec, focus behavior |
| `use-theme.ts`, `system-theme-toast.tsx` | First-class dark mode §4, `prefers-reduced-*` modes |
| Reports / exports (`jspdf`, `xlsx`) | Print discipline §16, tabular numerals in PDFs |

**Rollout waves:** W1 *Foundations* (tokens, themes, type, motion) → W2 *Primitives* (buttons, inputs, cards, badges) → W3 *Patterns* (tables, dialogs, shell, charts, notifications) → W4 *Refinement* (density modes, keyboard, a11y audit, do/don't enforcement).

---

## Appendix A — Master token table (light)

| Semantic token | Value |
|---|---|
| `surface.canvas` | `ink.50` `#F7F7F4` |
| `surface.card` | `ink.0` `#FFFFFF` |
| `surface.raised` | `ink.0` + `elevation.hover` |
| `surface.overlay` | `ink.0` + `elevation.overlay` |
| `text.primary` | `ink.900` `#14140F` |
| `text.secondary` | `ink.600` `#64625A` |
| `text.tertiary` | `ink.500` `#8F8C80` |
| `text.muted` | `ink.400` `#B9B6AA` |
| `border.hairline` | `ink.300` `#D8D6CC` |
| `border.strong` | `ink.200` `#E7E6DF` |
| `accent.base` | `brand.500` `#4F7AFF` |
| `accent.hover` | `brand.600` `#3560E8` |
| `accent.subtle` | `brand.50` `#EEF3FF` |
| `accent.ring` | `brand.500` @ 35% |
| `focus.ring` | 2px `accent.base`, offset 2px |
| `radius.control` | 8 |
| `radius.surface` | 12 |
| `radius.overlay` | 16 |

## Appendix B — Master token table (dark deltas)

| Semantic token | Dark value |
|---|---|
| `surface.canvas` | `brand.950` `#0B1030` |
| `surface.card` | `#11163A` |
| `surface.raised` | `#171D47` |
| `surface.overlay` | `#1A2052` |
| `text.primary` | `#E4E6EF` |
| `text.secondary` | `#9EA3BF` |
| `text.tertiary` | `#636B90` |
| `border.hairline` | `#232A5C` (brighter than surface) |
| `accent.base` | `brand.500` `#4F7AFF` (fills) / `brand.300` (text) |
| `focus.ring` | 2px `brand.400` + `glow.focus` |
| elevation | luminance steps (§4.2) |

---

*End of specification. Corrections, omissions, and dissent are welcome — this document is a living contract, and per the re-capture loop, it earns its place by staying true to the shipped product.*
