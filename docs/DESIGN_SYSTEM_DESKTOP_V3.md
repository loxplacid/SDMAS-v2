# SDMAS Desktop Design System — CustomTkinter Specification

**Codename:** *The Forge*
**Status:** Draft for review · **Owner:** Product Design · **Version:** 3.1.0
**Scope:** `apps/desktop` — CustomTkinter client (Python 3.12, Windows-first)
**Companion docs:** `docs/DESIGN_SYSTEM_V3.md` (the *Corridor* — token source of truth), `docs/MOTION_SYSTEM_V3.md` (the *Compass* — motion grammar), `docs/MICRO_INTERACTIONS_V3.md` (the *Gloss* — interaction catalog), `docs/METADATA_PLATFORM_V3.md` (§5.2 desktop renderer plan)

> *The web is where the school looks at SDMAS. The desktop is where the school works in it. The Forge is the native workshop: denser, faster, quieter — every interaction engineered, nothing decorative.*

This specification is a **complete, self-contained design language for the CustomTkinter desktop client**. It reuses the Corridor v3 token architecture verbatim where the canvas allows, and specifies the exact translation where CustomTkinter's constraints demand a different mechanism. It is a design specification only — no code. Every value below is a contract.

---

## 0. Relationship to Corridor v3

The Forge does **not** replace Corridor v3. It is the same design system re-expressed for a native Python canvas with a different physics model:

| | Corridor v3 (web) | The Forge (desktop) |
|---|---|---|
| Rendering model | CSS: transforms, opacity, filters | Tk geometry + colors, no opacity/transform |
| Physics | Cubic-bezier, native springs | Keyframe tables driven by `.after()` |
| Elevation | Real shadows + blur | Luminance steps + hairline + halo frames |
| Density | Comfortable default | Compact default (native screen) |
| Input | Pointer + touch | Pointer + keyboard (first-class) |
| Token contract | Same | Same — the Forge consumes Corridor tokens |

**Rule:** the Forge may never introduce a color, radius, duration, or spacing value that is not a Corridor token or a delta declared in this document. Drift is a release-blocker (§18).

---

## 1. The premium thesis

The goal is not beauty. The goal is that **every interaction feels engineered** — the way a bank's vault door feels engineered. We studied seven modern products and extracted principles only; nothing was copied, everything was translated into rules for a data-dense school operations tool.

### 1.1 Study → principle → rule

| Source | What it demonstrates | Principle extracted | The Forge rule |
|---|---|---|---|
| **Apple** | Cause and effect are inseparable; sheets relate to their parent; Reduce Motion is a real mode | *The response names the gesture* | Every press answers within 75ms. Every panel enters from its trigger and exits to it. A reduced-motion tier is a first-class user setting (§12.6). |
| **Linear** | Speed is a feature; 1px hairlines; keyboard-first; no bounce on data | *The fast clock + the 1px discipline* | Feedback < 150ms, spatial change < 400ms. Every surface is defined by a 1px hairline. Every action reachable by keyboard (§16). |
| **Raycast** | Dense keyboard-first lists; high-contrast selection that *slides* with the cursor | *Selection is a traveling wash* | The active row's highlight moves between rows — it never fades and re-fades. Type-to-filter is the default search pattern. |
| **Arc Browser** | Spatial continuity — tabs glide, panes reflow; curved, confident surfaces | *Ownership by origin* | A menu grows from its trigger's corner. A drawer slides from the edge it belongs to. Radius communicates containment (§7). |
| **Notion** | Restraint is the luxury; most things should not move; calm warm neutrals | *Stillness wins ties* | When two options look equal, the one that moves less is correct (§10.7). Motion is budgeted per interaction (§12.5). |
| **Manus** | The system shows its work; status is never hidden | *Ambient transparency* | A persistent status bar reports sync, saves, and long jobs. The app never hides what it is doing (§11.5). |
| **Bklit UI** | Refined density — tight rhythm, strong hierarchy in dense panels | *Density with discipline* | A 4px grid enforced everywhere; dense panels use the compact scale, never cramming (§6). |

### 1.2 The five pillars

| Pillar | Meaning | Evidence in the Forge |
|---|---|---|
| **P1 · Precision over decoration** | Every pixel is intentional; hierarchy from typography and alignment, not color noise | 4px grid, 1px hairline on all surfaces, single accent role, tabular numerals (§5.4). |
| **P2 · Every gesture answered** | The app acknowledges within 75ms or the interaction is too heavy to ship | Press flash, hover wash, focus ring — all instant-tier (§10, §12). |
| **P3 · Keyboard is first-class** | Raycast/Linear rule: the mouse is an optimization, not a requirement | Full keyboard nav, visible focus rings, `Ctrl+K`-style command palette, type-ahead everywhere (§16). |
| **P4 · Depth by luminance, meaning by motion** | In dark mode, elevation is light; in light mode, it is shadow. Motion always carries a direction | Luminance surface ladder (§4); the five-verb grammar with the cardinal compass (§12.1). |
| **P5 · Restraint is the luxury** | Most things stay still. Motion exists for wayfinding, feedback, and focus — nothing else | Global motion budget; licensed loops only; stillness wins ties (§10.7, §12.5). |

### 1.3 What the Forge explicitly rejects

- Bounce on anything over 44px. Springs are for thumbs, not panels (§13).
- Real-time physics lag — any `.after()` loop must complete a frame in ≤ 16ms or it is simplified.
- Hover-only affordances without keyboard parity.
- Color as the only signal for any state (§16.6).
- "Beautification": decorative gradients on data surfaces, floating buttons, drop-shadows on text.

---

## 2. The CustomTkinter constraint model

The premium feel lives or dies in the translation layer. CustomTkinter v5.x gives us a fixed set of native capabilities; everything else is **specified simulation**. The entire motion and depth language of the Forge is built on this table.

### 2.1 Native vs. simulated

| Capability | Native in CTk | The Forge strategy |
|---|---|---|
| Appearance modes | ✅ `"System"` / `"Light"` / `"Dark"` | The theme switch is a first-class control in the header (§4.4). |
| Theme files | ✅ JSON theme with light/dark color pairs, `corner_radius`, `border_width` defaults | All primitive + semantic colors live in the theme file; components never hardcode a color (App. C). |
| Hover states | ✅ `hover_color` (buttons, checkboxes) · `button_hover_color` (switches) | All hover washes are native hover colors or an `.after()` color lerp; entries hover via `border_color` → `border.strong` (§10.2). |
| Corner radius | ✅ `corner_radius` on every CTk widget | Full radius scale maps 1:1 (§7). |
| Border widths | ✅ `border_width` + `border_color` | Hairlines and focus rings use borders (§8, App. C). |
| Fonts | ✅ `tkinter.font.Font` (point-based, DPI-scaled via CTk scaling) | Family fallbacks + px/point table (§5.2). |
| Layout | ✅ `pack` / `grid` / `place` | Specified per surface type (§6.4). |
| Animation | ✅ `.after(ms, cb)` loops + `.configure()` restyles | The only animation primitive; all durations/easings are keyframe tables over it (§12). |
| Custom drawing | ✅ `CTkCanvas` / `tk.Canvas` | Used for: check draws, chart lines, skeleton sweeps, hero gradients, signature illustration (§11). |
| **Real shadows** | ❌ none | **Luminance + hairline is the primary elevation language** (§9). Light mode adds the *halo*: a 1–3px offset frame of darkened surface color behind the surface. |
| **Opacity / fade** | ❌ no per-widget opacity | Fade = **color interpolation** toward the surface behind (a "wash" or "ghost" tween). Whole-window alpha exists but is reserved for overlay backdrops only. |
| **Transform / scale** | ❌ no native transform | Scale is simulated by **geometry lerp anchored at an origin** (small objects) or **canvas drawing** (checkmarks, rings). Panels never scale — they grow by geometry + border emphasis. |
| **Gradients** | ❌ no widget gradients | Flat surfaces are the default (Linear-style). One licensed canvas gradient: the login backdrop (§9.5). |
| **Blur** | ❌ no backdrop blur | Not simulated. Elevated surfaces instead get higher-contrast hairlines + one luminance step. Blur tokens from Corridor are intentionally unused on desktop. |
| **Springs / easing** | ❌ none | Expressed as **precomputed keyframe tables** (§12.3, §13) — deterministic, testable, identical on every machine. |
| Z-order / modal | ✅ `lift()`, `grab_set()`, `Toplevel` | Modal freeze uses `grab_set` + a dimmed `Toplevel` overlay (§12.4). |

### 2.2 The verb map (Corridor grammar → Forge mechanism)

Corridor defines five verbs. The Forge keeps the grammar — `(verb, direction, distance-class, importance-class)` — and redefines only the mechanism:

| Verb | Corridor (web) | The Forge (CTk) |
|---|---|---|
| **Fade** | opacity | Color lerp: interpolate `fg_color`/`text_color` from value A to value B over N frames (§12.4). |
| **Slide** | transform: translate | Geometry lerp: animate `place(x/y)` or pack order over N frames. Never animates the layout of siblings — use `place` so nothing reflows. |
| **Scale** | transform: scale | Geometry lerp anchored at an origin (≤ 44px objects) or `Canvas` coords (check draws, ring expansion). Panels use the *settle-in* pattern instead (§12.4, §13.4). |
| **Draw** | stroke-dashoffset | `Canvas` stroke growth: check marks, chart lines, focus ring expansion, sidebar indicator. |
| **Pulse** | scale 1→1.05→1 | Color or geometry micro-keyframes (e.g., success dot: brighten → restore; badge: 1-frame oversize). |

### 2.3 Frame economics

- Animation clock: `.after(16)` ≈ 60fps; every tween is precomputed as a fixed frame array, never calculated per-frame from a curve (deterministic + cheap).
- Budget per frame: a tween may restyle **one widget's colors and one geometry property**; anything larger is split (§12.5).
- All loops must have a static reading (the loop's first frame is a valid resting state).

---

## 3. Color

### 3.1 Brand — navy + electric (unchanged from Corridor, authoritative here)

| Token | Value | Role in the Forge |
|---|---|---|
| `brand.950` | `#0B1030` | Dark-mode canvas, login backdrop base |
| `brand.900` | `#131F45` | Dark-mode elevated surface tint |
| `brand.800` | `#1D2B6B` | Dark-mode hover fill |
| `brand.700` | `#2A4CC0` | Accent hover (dark) |
| `brand.600` | `#3560E8` | Accent hover (light) |
| `brand.500` | `#4F7AFF` | **Primary accent — action and selection only** |
| `brand.400` | `#6E8FFF` | Accent text/fills on dark surfaces |
| `brand.300` | `#94B0FF` | Accent text on dark |
| `brand.200` | `#BCCEFF` | Selected chart tint |
| `brand.100` | `#DCE6FF` | Accent-tinted surfaces |
| `brand.50` | `#EEF3FF` | Accent wash, selected-row tint |

**The accent rule (unchanged):** electric blue is used for *action, selection, and the active state — nothing else*. It never colors paragraphs, never decorates, never appears as a background without a purpose. In the Forge this is enforced by the theme file: no component may set `fg_color` to a brand value directly; it consumes the semantic token `accent.*`.

### 3.2 Ink — warm-tinted neutrals (light)

| Token | Value | Role |
|---|---|---|
| `ink.0` | `#FFFFFF` | Card surface |
| `ink.50` | `#F7F7F4` | Canvas (window background) |
| `ink.100` | `#F1F0EB` | Canvas alt, hover wash base |
| `ink.200` | `#E7E6DF` | Border strong, hover borders |
| `ink.300` | `#D8D6CC` | Hairline borders, dividers |
| `ink.400` | `#B9B6AA` | Disabled text |
| `ink.500` | `#8F8C80` | Muted/tertiary text |
| `ink.600` | `#64625A` | Secondary text |
| `ink.700` | `#3F3E39` | Primary text (secondary emphasis) |
| `ink.800` | `#24241F` | Primary text |
| `ink.900` | `#14140F` | Headings, near-black ink |
| `ink.950` | `#0B0B08` | Overlay backdrop (dim) |

### 3.3 Ink — dark (the night shift)

Dark mode is a *night light for a school office*, not an inversion:

| Token | Dark value | Role |
|---|---|---|
| `surface.card` (dark) | `#11163A` | Card surface — see §4.2 for the full dark ladder; the ink tokens below serve text only |
| `text.primary` (dark) | `#E4E6EF` | Primary text — blue-tinted white, never pure white (halation) |
| `text.secondary` (dark) | `#9EA3BF` | Secondary text |
| `text.tertiary` (dark) | `#636B90` | Muted text |
| `text.inverse` | `#FFFFFF` | On-accent text |
| `text.disabled` (dark) | `#4A5278` | Disabled (≥ 3:1 against surface) |

### 3.4 Status — reserved for status

| Status | fg | bg (light) | bg (dark) | Means |
|---|---|---|---|---|
| `success` | `#0F973D` | `#E9F9EE` | `#052E16` | Paid, cleared, complete, present |
| `warning` | `#D97706` | `#FEF6E6` | `#341A00` | Due, pending, partial |
| `danger` | `#DC2626` | `#FAE8E8` | `#2D0909` | Overdue, failed, absent, blocked |
| `info` | `#0284C7` | `#E0F2FE` | `#0C334E` | In progress, informational |

Status colors are **reserved for status**. They never double as decoration; success/danger are never used for emphasis (that is accent's job). Status is always conveyed as icon + text + color, never color alone (§16.6).

### 3.5 Data-viz palette (unchanged)

`dv.1–8` as in Corridor §3.4 (Okabe-Ito-inspired, colorblind-safe, dark/light pairs). Max 6 categorical series; above that, aggregate into "Other". Never encode information by hue alone.

### 3.6 Contrast floors (normative, both themes)

| Usage | Floor |
|---|---|
| Body and small text (< 18px / < 13.5pt) | ≥ 4.5:1 (AA) |
| Large text (≥ 18px bold / ≥ 14px) | ≥ 3:1 |
| UI components, icons, borders that encode state | ≥ 3:1 |
| Financial figures (ledgers, receipts) | ≥ 4.5:1 always |
| Disabled text | ≥ 3:1 against its surface (readable, not invisible) |

---

## 4. Surface hierarchy

### 4.1 The principle

**Depth is encoded by luminance in dark mode and by hairline + halo in light mode.** Corridor's shadow stack is replaced by a deterministic surface ladder — the same ladder drives both themes, only the values change.

### 4.2 The ladder

| Layer | Light surface | Dark surface | Edge treatment |
|---|---|---|---|
| **Canvas** (window) | `ink.50` `#F7F7F4` | `brand.950` `#0B1030` | none |
| **Card** | `ink.0` `#FFFFFF` | `#11163A` | 1px hairline `ink.300` / `#232A5C` |
| **Raised** (menus, tooltips, toasts) | `ink.0` + halo 1px | `#171D47` | hairline + halo (light) / brighter hairline (dark) |
| **Overlay** (dialogs, drawers) | `ink.0` + halo 3px | `#1A2052` | hairline + halo (light) / brightest hairline (dark) |
| **Command palette** | `ink.0` + halo 3px + larger radius | `#1A2052` | hairline + halo; no blur (unsupported — replaced by radius + luminance) |
| **Backdrop** (dim behind modal) | `ink.950` @ simulated 45% | `brand.950` @ simulated 60% | whole-window alpha overlay |

### 4.3 Rules

1. **Every raised surface wears a 1px hairline** — in both themes. In dark mode the hairline is *brighter* than the surface it outlines (`#232A5C` over `#11163A`); in light mode it is a warm grey `ink.300`. The hairline is the Forge's signature, exactly as in Corridor.
2. Luminance steps in dark mode are **+1** per ladder rung (canvas → card → raised → overlay), never more.
3. A surface never sits directly on another surface of the same luminance. If it must, the hairline does the separation.
4. No more than **three visible levels** in any viewport region (e.g., a dialog = backdrop + overlay surface + one nested card inside it — the nested card is hairline-only, no halo).
5. `bg_color` (transparency to parent) is the tool for embedding a control in a surface; `fg_color` is for the surface itself. Never confuse them — a button inside a card uses the card's color as its `bg_color`.

### 4.4 Theme switching

- The header carries a System/Light/Dark control (a 3-segment control per §15.8). Persisted per user.
- Theme switch is a **global state change**: surfaces re-resolve semantic tokens instantly (`instant`, 75ms). No crossfade — a native app switches like macOS, not like a marketing page. The 400ms window fade is optional and only for the whole window (`alpha`), never per-widget.

---

## 5. Typography

### 5.1 The voice

Inter remains the family of record; the desktop is Windows-first, so the fallback chain matters:

| Role | Family chain | Use |
|---|---|---|
| UI | **Inter** → Segoe UI Variable → Segoe UI | Everything interactive and informational |
| Display | Inter (tight leading) → Segoe UI Variable | Page titles, KPI numerals, login hero |
| Mono | **JetBrains Mono** → Cascadia Mono → Consolas | Receipt refs, IDs, hashes, timestamps, correlation IDs |

Ships with the installer (font files bundled + registered), falling back gracefully when absent.

### 5.2 Type scale

Sizes are design-point values in px; the implementation note is **font size in Tk points ≈ px × 0.75** (e.g., 14px → 10.5pt), applied through CTk's scaling path so DPI changes never break rhythm.

| Step | Size / Line (px) | Weight | Tracking | Use |
|---|---|---|---|---|
| `display` | 40 / 44 | 600 | −2% (via size, Tk has no tracking) | Login hero, report covers |
| `h1` | 26 / 32 | 600 | −2% | Page title (one per page) |
| `h2` | 22 / 28 | 600 | — | Section title |
| `h3` | 18 / 24 | 600 | — | Card title |
| `h4` | 16 / 22 | 500 | — | Group label in cards |
| `body-lg` | 16 / 26 | 400 | — | Empty-state copy, dialogs |
| `body` | 14 / 22 | 400 | — | Default UI text |
| `body-sm` | 13 / 20 | 400 | — | Table cells, form hints |
| `caption` | 12 / 16 | 400 | — | Meta, timestamps |
| `micro` | 11 / 14 | 500, **uppercase** | +4% | Eyebrows, column headers, section labels |
| `mono` | 13 / 20 | 400 | — | IDs, refs, hashes |
| `tabular` | inherits size | inherits | — | **All numerals** in ledgers, KPIs, dates, IDs |

### 5.3 Weights

400 regular · 500 medium (default for controls) · 600 semibold (headings, active nav, KPI) · 700 bold (display numerals only). Segoe UI Variable ships 400–700 variable; map 500→Semibold if 500 is absent in a fallback family.

### 5.4 Numeric discipline (desktop-specific note)

Tk fonts cannot enable OpenType `tnum`. The parity technique:

1. Every numeric cell is **right-aligned** inside a fixed-width column so digits share a right edge (the visible effect of tabular figures).
2. KPI numerals use `display`-size 600 weight, right-aligned, with the unit in a `caption` label below the figure — never inline.
3. Currency codes live in column headers, not per cell (`₹` once, not 1,240 times). Invoices/receipts are the licensed exception.
4. If Inter (which contains tabular figures) is present, mono/consolas are *not* used for figures — the fixed-width column rule still applies.

---

## 6. Spacing & grid

### 6.1 The grid

Base unit **4px**. All spacing tokens are multiples of 4. Macro alignment on **8px** for surfaces; micro-spacing inside controls on 4px. The grid is enforced by the layout spec (§6.4), never by eye.

| Token | Value | Typical use |
|---|---|---|
| `space.2xs` | 4 | Icon gap, checkbox mark gap |
| `space.xs` | 8 | Control padding, chip gaps, form field gaps |
| `space.sm` | 12 | Compact card padding, table cell padding |
| `space.md` | 16 | Default control padding, card padding |
| `space.lg` | 24 | Section gaps, card grid gutters |
| `space.xl` | 32 | Page section spacing, dialog padding |
| `space.2xl` | 48 | Page → header gap, form section breaks |
| `space.3xl` | 64+ | Empty states, hero spacing |

### 6.2 Rhythm rules

1. Vertical rhythm between stacked blocks = `space.lg` (24); between sub-blocks = `space.sm` (12).
2. Window content padding: `space.lg` (24) at ≥ 1280px wide, `space.md` (16) below.
3. Card padding: `space.md` (16) default; `space.sm` (12) for tables and dense panels.
4. Never space by eye; always by token. The one licensed exception is **optical alignment** of numerals and icons (left-aligned numerals next to right-aligned figures), which is specified per component, not improvised.

### 6.3 Density modes

A persisted user setting (default **Compact** on desktop — the native screen is the "working" surface):

| Mode | Row height | Cell padding | Typography |
|---|---|---|---|
| **Compact** (default: ledgers, rosters, audit) | 36 | 12×8 | body-sm, tabular |
| **Comfortable** (default: people, portals) | 48 | 16×12 | body |

Switching density animates row heights at `slow` (260ms) via geometry lerp and never changes meaning. Density lives in one global token consumed by the table component (§15.4).

### 6.4 Layout mechanics per surface

| Surface | Mechanism | Rationale |
|---|---|---|
| Fixed chrome (sidebar, header, status bar) | `place` | Absolute placement — no reflow when content changes |
| Flowing content (forms, cards, lists) | `grid`/`pack` | Native flow; alignments inherit the 8px macro grid |
| **Animated** elements (toasts, popovers, skeletons) | `place` on a dedicated overlay layer | Animating a placed widget never reflows siblings (§12.4) |
| Tables | `ttk.Treeview` | Styled per §15.4; row height via `rowheight` |

Window minimums: main 1080×680; dialogs 360×200 min, 560 width target. Resize is never a layout failure — surfaces reflow on the grid.

---

## 7. Corner radius

### 7.1 The scale

| Token | Value | Used by |
|---|---|---|
| `radius.control` | 8 | Inputs, buttons, selects, chips, cells |
| `radius.surface` | 12 | Cards, panels, popovers |
| `radius.overlay` | 16 | Dialogs, drawers, command palette |
| `radius.pill` | 999 | Badges, status pills, avatars, tab pill |

### 7.2 The rule

**Radius communicates containment.** Controls are tighter than the surfaces they sit on; overlays are the softest. The canonical stack is an input (8) inside a card (12) inside a dialog (16) — never reversed, never equalized.

### 7.3 CTk notes

- `corner_radius` maps 1:1 and is **capped at half the widget's minimum dimension** — a 24px chip cannot carry radius 12+; specify the effective radius as `min(corner_radius, height/2)`.
- CTk renders radius via a clipping path; nested widgets with `bg_color` (transparent) inherit the parent's clipping, so **radius stacks correctly** when embedded — a design requirement, not a hack.
- Icon buttons (36px) use `radius.control`; avatar (32px) uses `radius.pill`.
- The login "app icon" uses the squircle ~22% rule — implemented as a 32px canvas-drawn squircle, since CTk has no squircle.

---

## 8. Borders

### 8.1 The token set

| Token | Light | Dark | Use |
|---|---|---|---|
| `border.hairline` | `ink.300` `#D8D6CC` | `#232A5C` (brighter than surface) | Default edge of every raised surface |
| `border.strong` | `ink.200` `#E7E6DF` | `#2C346B` | Hover borders, filled-state inputs, dividers with emphasis |
| `border.hover` | accent @ 40% → `accent.base` on hover-outline | `brand.400` @ 40% | Outline buttons, selectable cards |
| `border.focus` | 2px `accent.base` | 2px `brand.400` | Focus rings (§10.1) |
| `border.danger` | `status.danger.fg` | `#F87171` | Error states |
| `border.disabled` | `ink.300` @ 60% | `#232A5C` | Disabled controls |

### 8.2 The discipline

1. Hairlines are exactly **1px** — never 0.5 (unstable on Windows scaling), never 2 on default surfaces.
2. A focus state changes `border_color` + `border_width` (1 → 2) — **never border color alone** (§10.1). The 1px growth is the ring.
3. Dividers inside surfaces are hairlines; dividers between surfaces are `border.strong`.
4. Vertical gridlines in tables are forbidden — hairlines run horizontally only (§15.4).

---

## 9. Elevation & the shadow system

### 9.1 The strategy

Corridor's shadows cannot exist in CTk. The Forge replaces them with a **two-part depth language**:

1. **Luminance ladder** (primary, both themes) — §4.2. Works in both modes; in dark mode it is the *entire* depth story.
2. **The halo** (light mode only) — a second frame behind the surface, offset 1–3px, filled with a darkened surface color at 25–35% of the surface-to-ink distance. This is the CTk-native way to simulate a soft shadow without blur.

### 9.2 The halo recipe

| Elevation layer | Halo offset | Halo color (light) | Notes |
|---|---|---|---|
| `elevation.rest` (cards on canvas) | none | — | hairline only |
| `elevation.hover` (interactive cards, hover) | 1px down | `#E7E6DF` @ 60% | appears on hover only (one `.after()` color swap) |
| `elevation.floating` (menus, tooltips, toasts) | 2px down | `#D8D6CC` @ 50% | fixed halo |
| `elevation.overlay` (dialogs, drawers) | 3px down | `#C9C6B8` @ 45% | fixed halo |
| `elevation.command` (palette) | 3px + 4px second halo | `#C9C6B8` @ 45% + `#B9B6AA` @ 25% | double halo = the "blur" replacement |

The halo is a **non-interactive child frame** placed *behind* the surface in z-order (`lower()`), with the surface's geometry + offset. It inherits the surface's radius minus 1px. In dark mode the halo is disabled entirely (luminance does the work).

### 9.3 The z-ladder

| Level | Layer | Mechanism |
|---|---|---|
| 0 | Canvas | main window |
| 10 | Sticky header, status bar | `place` pinned |
| 20 | Tables with sticky chrome | `place` pinned, no z conflict |
| 30 | Menus, popovers, tooltips | child `Toplevel` or overlay layer, `lift()` |
| 40 | Dialogs, drawers | `Toplevel` + `grab_set` (modal freeze) |
| 50 | Toasts | frameless `Toplevel`, `attributes("-topmost", True)` |
| 60 | Command palette | `Toplevel`, topmost |

Only these levels exist. No widget may set z-order outside the ladder.

### 9.4 Spotlight / coach marks

Frameless topmost `Toplevel` with a canvas-drawn dim overlay and a punched-out highlight circle around the target. One at a time; dismissed by any key.

### 9.5 Gradients — the two licensed uses

1. **Login backdrop**: a canvas-drawn linear gradient `brand.950 → brand.600` covering the window behind the login card. Canvas only; static (no animation). Everything else is flat.
2. **Chart area-fill undertone**: 20% tint drawn on the chart canvas beneath the series. Never on text, never on interactive elements, never animated.

Rule: a surface that cannot render its gradient (font/GPU constraints aside — CTk always can via canvas) must degrade to its base flat color without losing meaning. There is no other gradient in the system.

---

## 10. Interaction states

### 10.1 Focus

The focus ring is **the keyboard's cursor** — it must be instant (75ms) and unmistakable, in both themes.

- Mechanism: `border_width` 1 → 2 + `border_color` → `accent.base`/`brand.400`, on the focus-in event; a **2px gap** between ring and control is simulated by the ring living on a parent frame padded 2px, or by the widget's own 2px `bg_color` ring frame (for entries: `CTkEntry` has no ring — wrap in a `CTkFrame` of the surface color carrying the 2px border).
- **Never** a border-color-only focus change. The width change (1→2px) is the ring's readability.
- The element never translates or scales on focus (moving the target while the user tabs to it is disorienting at data density).
- The ring shows on **every** focus. Tk cannot reliably distinguish mouse focus from keyboard focus, so the desktop rule is simpler and safer than the web's: a visible ring on all focus, always. It costs mouse users nothing and guarantees keyboard users are never stranded. (The ring remains width 1→2, never border-color alone.)

### 10.2 Hover

- Filled variants deepen one shade (`hover_color`): primary `brand.600`, danger/success darker step.
- Ghost/outline variants gain a wash: `fg_color` → `ink.100` (light) / `#1D2B6B` (dark), text warms one step.
- Cards/rows: `fg_color` → wash + (interactive cards) halo appears.
- Hover starts within 75ms and lands within 120ms. `hover_color` is native; ghost washes are a one-frame `.after()` swap (no lerp needed — color < 120ms can jump, the duration is perceptual).

### 10.3 Pressed

- Corridor's `scale 0.97` is **not available** — no transform. The Forge's press is a **flash**: `fg_color` deepens one more shade (darker than hover) for the press duration (75ms), reverting on release. For primary: `brand.700`.
- On dense tables, press flash is disabled (row selection is the press) — the row wash deepens instead.
- The flash must start ≤ 75ms after press (`<ButtonPress-1>`), revert on `<ButtonRelease-1>`/leave.

### 10.4 Disabled

- 45% legibility: `fg_color` → surface-wash grey, `text_color_disabled` (native), border → `border.disabled`, cursor → arrow.
- Disabled controls do not hover, do not press, do not show focus rings, and skip the tab order unless `takefocus` is explicitly required.
- Disabled text keeps ≥ 3:1 against its surface (§3.6) — it must be *readable as disabled*, not invisible.

### 10.5 Selection

- **Selection is accent-tinted, never full-accent fill** (except checkmarks/toggles, which are the licensed accent fill).
- Table rows: `accent.subtle` wash (`brand.50` light / `#1D2B6B` dark) + the checkbox draws its check (300ms draw on canvas).
- The **active row's wash slides** between rows at `fast` (120ms) in keyboard lists (Raycast principle) — implemented as a single placed wash frame that lerps position; text never re-fades.
- Selected cards: hairline → `border.hover` (accent), leading 2px rail draws (300ms, canvas).
- Deselection is lighter than selection: wash decays at 180ms, check un-draws at 0.7× (84ms).

### 10.6 The state matrix (normative)

| State | Buttons | Inputs | Cards / rows | Nav items |
|---|---|---|---|---|
| Focus | 2px accent ring (width 1→2) | ring via wrapper frame | same | same (indicator draws) |
| Hover | `hover_color` / wash | border → `border.strong` | wash + halo (interactive) | wash + text brighten |
| Pressed | one-shade-deep flash (75ms) | border strong, no flash | row wash deepens | wash deepens |
| Disabled | 45%, no hover/press/ring | 45%, no ring | no hover | icon muted, label 45% |
| Selection | — | — | accent wash, check draw, rail | active rail + tint |

### 10.7 Stillness rule

When two implementations are otherwise equal, the one that moves less is correct. Hover reveals must have keyboard parity (focus reveals the same actions). A control with no state change on hover or press is a defect, not minimalism — except in data density where the row hover is *already* the feedback.

### 10.8 Interaction tokens (normative)

Every interaction state is a named token — the same governance rule as colors and motion. Components consume tokens; no component hardcodes a state value.

| Token | Value | Used by |
|---|---|---|
| `interaction.focus.duration` | 75ms `instant` | Focus rings on every control |
| `interaction.focus.ring` | 2px `accent.base` / `brand.400`, width 1→2 | All focusable controls (§10.1) |
| `interaction.focus.gap` | 2px (wrapper frame padding) | Entries and fields without a native border path |
| `interaction.hover.duration` | 120ms `fast` | All hover washes and tints |
| `interaction.hover.wash` | `ink.100` (light) / `#1D2B6B` (dark) | Ghost buttons, cards, rows, nav |
| `interaction.pressed.duration` | 75ms `instant` | Press flash on all buttons |
| `interaction.pressed.flash` | one shade deeper than hover (`accent.pressed` = `brand.700` for primary) | Buttons (§10.3) |
| `interaction.disabled.alpha` | 45% (color-mixed toward surface, no native alpha) | All disabled controls (§10.4) |
| `interaction.selection.wash` | `accent.subtle` `brand.50` / `#1D2B6B` | Selected rows, selected cards, active nav |
| `interaction.selection.check` | 300ms `draw` | Checkbox/row check strokes |
| `interaction.active.wash-slide` | 120ms `fast` | Raycast rule — the active row's wash slides between rows |
| `interaction.target.min` | 28px pointer · 36px preferred · 44px primary | All hit areas (§16.4) |
| `interaction.hover.reveal` | 120ms, 20ms per action | Ghost row actions, hover + focus parity |

---

## 11. Feedback states

### 11.1 Empty states

- Anatomy: signature illustration (canvas line-art, duotone: accent glyph + ink key shape) → title (`h3`) → one-line body → **single primary action**.
- Empty states are moments of orientation, not dead ends: every empty state offers the next step. First-run pages add a dismissible compact onboarding card.
- Motion: fade in at `base` (180ms), CTA slides up 4px at `fast` (120ms).
- A table with no rows shows the empty state **in the table's body area** — never a blank frame.

### 11.2 Loading states

- **Skeleton-first:** every data surface ships a skeleton mirroring its final layout exactly. Implementation: blocks of `ink.100`/`ink.200` (light) or `#1D2B6B`/`#232A5C` (dark) with the final geometry, `radius.control`.
- Shimmer (Corridor's licensed loop) becomes a **brightness pulse**: the skeleton blocks lerp toward `ink.200`→`ink.100` (light) over a 1.4s linear loop, 12 frames. A canvas "sweep" is allowed only for large surfaces.
- Buttons: label swaps to a static progress glyph (or `░` progress braille) — no spinner widget dependency; label width never swaps.
- Long operations: the **status bar** carries a 2px determinate `CTkProgressBar` (accent) pinned at the bottom edge of the main window (§11.5). Indeterminate ≤ 2s, determinate beyond.
- Skeleton → content is a crossfade at 180ms (color lerp from skeleton to real surface colors) — the layout was already true.

### 11.3 Error states

| Layer | Recipe |
|---|---|
| Field-level | `border.danger` ring (width 2) + message below in `danger` fg; message ≥ 3:1. Ring appears at 75ms; message slides down 4px at 120ms |
| Repeat offender | the field's content flashes danger-light once (200ms) — the desktop equivalent of the web shake (no geometry shake; it reads as wobble on a native app) |
| Inline banner | `status.danger.bg` tint bar, icon, plain-language message, retry link |
| Full-page | signature illustration, what happened, correlation ID (`mono`), retry + back to safe place |
| Offline | global banner at top of window; writes queue with explicit "sent when online" state |
| Partial failure (batch ops) | success summary with failure table: "1,240 imported · 3 failed — download errors" — never all-or-nothing |

Copy rules: state what happened, what was affected, and the next action. Never "An error occurred."

### 11.4 Success states

- Toast (`success` fg icon, check draw 300ms on canvas) + one glow pulse on the status dot (brighten→restore, 300ms, once).
- Inline: check + the table row's status badge is the success state — the row updates, the badge tells the truth.
- Batch completion: a summary card with statistics — not fireworks.

### 11.5 Ambient transparency (Manus principle)

A 24px **status bar** pinned at the window's bottom edge: sync state dot, last-sync time, active job with determinate progress, "Saving… → Saved" heartbeat for autosaved records. It is quiet, permanent, and honest — the app never hides what it is doing. It appears on `canvas` color with a top hairline, `caption` text, and recedes visually.

---

## 12. Motion system for the Forge

### 12.1 Grammar (unchanged from the Compass)

A move = `(verb, direction, distance-class, importance-class)`. Everything else is a rule lookup. Verbs per §2.2; the cardinal compass is unchanged: **E** = forward · **W** = back · **N** = settles from above (authority) · **S** = grounded (grows from trigger) · **Z** = depth (viewer's attention).

### 12.2 Duration tokens (unchanged values, CTk frame mapping)

| Token | Value | Frames @ 60fps | Bound to |
|---|---|---|---|
| `instant` | 75ms | 4–5 | Press flash, focus ring, chevron |
| `fast` | 120ms | 7–8 | Hover, cell pulse, active-row wash slide |
| `base` | 180ms | 11–12 | Buttons, chips, selection wash |
| `slow` | 260ms | 16 | Menus, toasts, drawers, density change |
| `slower` | 380ms | 23 | Modal surface, palette, window moves |
| `slowest` | 500ms | 30 | KPI count-up, page transitions (soft cap) |
| `draw` | 300ms | 18 | Check draws, chart lines, focus ring expansion (fixed) |

Rules (from the Compass, unchanged): feedback outruns transition · exit = 0.7 × enter · arrivals start fast, departures leave fast · loops are `linear` only.

### 12.3 Easing as keyframe tables

No bezier exists in CTk — every easing is a **precomputed progress array** sampled from the Corridor curves. A tween interpolates `from + (to − from) × k[i]` over the frame count.

| Easing | Corridor curve | Progress array `k[0..10]` (11 samples) |
|---|---|---|
| `standard` | `cubic-bezier(0.2, 0, 0, 1)` | `0, .12, .24, .36, .47, .58, .68, .78, .87, .94, 1` |
| `enter` | `cubic-bezier(0.05, 0.7, 0.1, 1)` | `0, .38, .62, .76, .85, .91, .95, .97, .99, 1, 1` |
| `exit` | `cubic-bezier(0.3, 0, 0.8, 0.15)` | `0, .02, .07, .15, .26, .39, .53, .67, .80, .91, 1` |
| `linear` | `linear` | `0, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1` |

- These are the **only four tables**. Nothing else may be invented per-interaction.
- Exits sample the `exit` table at 0.7× the enter duration.
- `spring` is not an easing table — it is a preset family (§13).

### 12.4 Choreography rules (the canonical moves)

| Move | Forge recipe |
|---|---|
| Page enter | Fade (color lerp from canvas) + rise 4px (geometry), `slower`, enter table |
| List stagger | rows enter at 20ms quantum (cap 150ms), fade + 2px rise, `fast`→`base` |
| Modal | backdrop alpha fades in (`base`), then surface rises 8px + hairline sharpens (`slower`); exit reverse at 0.7×. Backdrop = whole-window `alpha` overlay `Toplevel` with `grab_set` |
| Drawer | slides from edge via `place` x-lerp (`slow`, enter); backdrop fades `base`; exit reverse |
| Menu/popover | grows from trigger corner: 4px rise + fade from anchor (`slow`); exit reverse |
| Toast | slides in from SE corner on the toast layer (`slow`), siblings stack-shift via `place`; auto-dismiss `slowest` exit |
| KPI count-up | 500ms `enter` table over tabular numerals (never more than 500ms) |
| Table row enter/update | fade `fast`; changed cells get a 50% value wash that decays over 300ms |
| Skeleton | brightness pulse 1.4s linear loop, 12 frames |
| Success pulse | dot brighten→restore 300ms once; check draws 300ms |
| Active nav indicator | 3px rail draws from left, 300ms (canvas) |

Choreography rules (unchanged): enter = reverse of exit · stagger in reading order · one subject per moment · the last frame is the truth (end states reachable without animation) · **motion budget**: per interaction, ≤ 3 elements and ≤ 500ms of aggregate movement · parallax is dropped on desktop (no transform layers to move at different rates) — depth is luminance's job.

### 12.5 Reduced motion

- A persisted **"Reduce motion"** setting (default: off) collapses all motion to: color swaps ≤ 75ms, no geometry travel, no stagger, loops freeze on their first frame.
- `Reduce motion` is a real user setting (System Settings parity), not an OS preference — the desktop is the one place SDMAS can own this.
- Even with motion on, every loop has a static reading (§2.3).

---

## 13. Spring presets

Springs model *gesture*, not rhythm. Legal only when the motion is pointer/keyboard-driven **and** the object is ≤ 44px (Corridor §3.4). The Forge expresses springs as **precomputed keyframe sequences** — deterministic, no physics engine. Overshoot ≤ 6% of travel, settle ≤ 300ms.

### 13.1 The preset family

| Preset | Object | Travel | Keyframes `k[0..11]` (progress with overshoot) | Settle |
|---|---|---|---|---|
| **`micro-spring`** | toggles, dots, badges, checkbox marks (≤ 16px) | 1× travel | `0, .72, .98, 1.06, 1.00, 1.02, 1.00, 1.00, 1, 1, 1, 1` | 240ms |
| **`press-spring`** | button press-release (36–44px) | 0.97 → 1 | `1, .93, .965, .99, 1.005, 1.0, 1.0, 1, 1, 1, 1, 1` (geometry or flash-color equivalent) | 200ms |
| **`bell-dot`** | notification dot arrival | 0 → 1.12 → 1 | `0, .8, 1.12, .96, 1.02, 1.0, 1, 1, 1, 1, 1, 1` | 300ms |
| **`settle`** (not a spring) | panels, modals, cards (all > 44px) | landing | `enter` table §12.3, 6px rise, **zero overshoot** | 380ms |

### 13.2 Rules

1. Springs are **forbidden** on anything > 44px. A card, panel, or modal that overshoots is a defect. Large objects use `settle`.
2. Overshoot ≤ 6% of travel, exactly once, then monotonic decay. Two overshoots = a wobble.
3. Springs run at 16ms frames; if a frame budget slips, the spring **completes** (jumps to final) rather than stuttering — the last frame is the truth.
4. The `press-spring` is optional on dense tables (press flash only).

---

## 14. The micro-interaction catalog (Forge subset)

The full 252-entry Gloss catalog is the reference. This is the **normative desktop subset** — the interactions that carry the premium feel in a native app, with their Forge mechanisms.

| ID | Trigger | Felt | Forge mechanism | Duration |
|---|---|---|---|---|
| H01 | Button hover | filled deepens / ghost warms | `hover_color` (native) | 120ms |
| H02 | Button press | one-shade flash, instant answer | `fg_color` flash on press, revert on release | 75ms |
| H03 | Icon hover | icon warms `ink.600`→`ink.800` | `text_color` lerp | 120ms |
| H04 | Card hover (interactive) | halo appears, hairline warms | halo frame show + `border_color` lerp | 180ms |
| H06 | Row hover | 40% wash, content still | `fg_color` wash swap | 120ms |
| H09/F12 | Sidebar item hover/focus | 3px indicator draws left | canvas rail draw | 300ms |
| K01 | Checkbox check | box fills, check draws | box fill 75ms + canvas stroke draw 300ms | 300ms |
| K03 | Toggle flick | knob travels, track fills, micro-settle | geometry lerp 20px + `progress_color` fill, `micro-spring` | 180ms + 240ms |
| K04 | Segmented wash | selected wash slides between segments | placed wash frame lerp (Raycast rule) | 180ms |
| K05 | Tab activate | underline slides, panel crossfades | underline geometry lerp + panel color crossfade | 180ms |
| K07 | Row click drill | row flashes 40% accent wash, decays | wash in 120ms, decay 180ms, then navigate | 300ms |
| K11 | Menu trigger | chevron rotates, menu rises from anchor | chevron glyph swap + menu 4px rise | 260ms |
| F01 | Input focus | 2px accent ring blooms | wrapper `border_width` 1→2 + color | 75ms |
| F16 | Listbox active row | wash slides with arrows | placed wash frame lerp | 120ms |
| L01 | Button loading | label → progress glyph, no width swap | static glyph swap | 75ms |
| L02 | Skeleton pulse | brightness breathes | 12-frame color loop 1.4s | loop |
| L08 | Save indicator | "Saving… → Saved" + check | label swap + canvas check draw | 300ms |
| N01/N02 | Toast enter/exit | slides from SE corner, exits to it | place lerp on toast layer, exit 0.7× | 260/180ms |
| N03 | Success pulse dot | dot brightens once | color keyframes, once | 300ms |
| O01/O02 | Modal enter/exit | backdrop alpha, surface rises, exit faster | whole-window alpha + 8px rise | 380/260ms |
| X05 | Sidebar collapse | rail glides, labels re-emerge | width/place lerp 260ms; label fade (color lerp) staggered 20ms | 260ms |
| S01 | Row select | check draws, row washes accent | canvas check + wash | 300/120ms |

Rules: one subject per moment · hover reveals have keyboard parity · nothing loops except the licensed four (spinner, skeleton pulse, sync breath, progress) · an interaction that cannot be explained in one sentence is deleted.

---

## 15. Component tokens

### 15.1 Buttons

| Variant | Surface | Text | Hover | Pressed | Notes |
|---|---|---|---|---|---|
| `primary` | `accent.base` | `#FFFFFF` | `brand.600` | `brand.700` flash | One primary per view |
| `secondary` | `surface.card` + hairline | `ink.800` | wash + `border.strong` | wash deepens | Default action |
| `ghost` | transparent | `ink.600` | `ink.100` wash | wash deepens | Toolbar actions |
| `outline` | transparent | `ink.800` | hairline→accent, text→accent | border deepens | Boundary emphasis |
| `danger` | `status.danger.fg` | `#FFFFFF` | darker step | darkest flash | Needs confirm dialog |
| `success` | `status.success.fg` | `#FFFFFF` | darker step | darkest flash | Completion moments only |

Sizes (height): `sm` 32 / `md` 36 / `lg` 44. Radius `radius.control` (8). Font: `body` 500. Icon-only: 36×36, tooltip required, keyboard-reachable. Disabled per §10.4. Loading per §11.2 (label → progress glyph, width never swaps).

CTk map: `fg_color`, `hover_color`, `border_color`, `border_width`, `text_color`, `text_color_disabled`, `corner_radius`, `font`, `height`.

### 15.2 Inputs

- Anatomy: label (`micro`, uppercase) → field (36px) → hint/error. Label always visible (no floating-label — faster scanning for a data tool).
- Field: `radius.control`, hairline border, `surface.card` fill, `body` text.
- States per §10: hover (`border.strong`) → focus (2px accent ring) → error (`border.danger` + message) → disabled (45%) → filled (no special color).
- Text area: min 3 rows, grows one line at a time (geometry lerp 120ms per line).
- Search: `Ctrl+K` affordance shown in the field's right inset.
- Prefix/suffix (currency, units, icons): inside the field, separated by a hairline — never floating.
- Types: text, search, select (§15.9), textarea, password (reveal toggle), date (native calendar popover), number (tabular, step buttons).

CTk map: `CTkEntry` (`fg_color`, `border_color`, `border_width`, `text_color`, `placeholder_text_color`, `corner_radius`, `font`); ring via wrapper frame (§10.1).

### 15.3 Cards

| Card | Anatomy | Use |
|---|---|---|
| `surface` | hairline, `radius.surface`, no halo at rest | Content groups |
| `interactive` | hover: halo + border warm; cursor hand | Navigable tiles, lists |
| `kpi` | big tabular numeral + label + sparkline (canvas) + delta chip | Dashboards |
| `hub` | duotone icon, title, 2-line description, chevron | Feature navigation |
| `split` | accent 3px top rail | "Needs your attention" |

Card header: title (`h3`) left, ghost actions right. Cards never nest more than one level.

### 15.4 Tables — the workhorse (`ttk.Treeview`)

Tables are the most important component in SDMAS (ledgers, rosters, audit logs). `ttk.Treeview` styling via `ttk.Style`:

| Aspect | Spec |
|---|---|
| Row height | Compact 36 / Comfortable 48 (§6.3) via `rowheight` |
| Header | `micro` uppercase, `caption` height 36, `border.hairline` bottom only; sticky via placed header frame |
| Dividers | horizontal hairlines only — no vertical gridlines |
| Striping | off by default; `#F7F7F4`-adjacent stripe only in Comfortable mode |
| Numerics | right-aligned fixed-width columns (§5.4) |
| Selection | accent wash (`brand.50` / `#1D2B6B`), check column draws |
| Row hover | 40% wash (`ink.100` / `#1D2B6B`) |
| Actions | ghost icon buttons in a trailing column, revealed on hover **and** focus |
| Empty | empty state rendered in the body area (§11.1) |
| Sorting | click header toggles arrow (glyph swap 120ms); rows re-sort, changed cells wash |
| Pagination | page-size selector (20/50/100) + prev/next with running count |
| Sticky action column | trailing column pinned via `place` |

tint note: `ttk.Treeview` background/fieldbackground/bordercolor configured in the style; `relief="flat"`; selection colors mapped (`map("Treeview", background=...)`).

### 15.5 Dialogs & drawers

| Type | Anatomy | Motion |
|---|---|---|
| `modal` | backdrop (`alpha` overlay) + surface `radius.overlay`, max-width 560, `grab_set` freeze | backdrop `base`, surface rises 8px `slower`; exit 0.7× |
| `confirm` | modal + danger accent, primary action destructive, **autofocus on cancel** | same as modal |
| `drawer` | anchored to trigger edge, 480px default | slide `slow` + backdrop `base` |
| `command` | centered palette, 640px, double halo, keyboard-first | rise `slower`, list stagger 20ms |
| `toast` | frameless topmost layer, SE corner stack | slide `slow`, exit 0.7× |

Rules: one dialog at a time (toasts excepted) · `Esc` closes · focus is trapped (`grab_set`) and restored · destructive actions always ask again · dialogs carry a header (title + close) even when visually minimal.

### 15.6 Navigation & shell

- **Shell:** sidebar (256px, collapsible to 68px rail with tooltips) + header (56px) + content + **status bar** (24px, §11.5).
- **Header:** breadcrumbs left (`caption`, hover per H18), global search (`Ctrl+K`), theme control (§4.4), notification bell, campus/organization switcher, user menu right.
- **Breadcrumbs:** page > section > item; only the navigable crumbs respond to hover.
- **Command palette (Ctrl+K):** routes, students, teachers, quick actions (record attendance, new fee, batch enroll), recent items. Keyboard-first: type filters (Raycast rule, 120ms wash slide).
- **Organization switcher:** current campus identity chip; switching is a loud, page-level event.
- **Contextual actions:** primary action docked top-right in the header area — never floating.

### 15.7 Sidebar

- Groups with `micro` uppercase labels; items: icon (20) + label + optional badge.
- Active item: accent-tinted wash + 3px left rail (draws 300ms) + icon full opacity.
- Collapse/expand: width/place lerp `slow` (260ms), labels cross-fade with 20ms stagger, icons center, tooltips grow South (180ms).
- Inset nav (within a section): no icons, 32px rows, indented.

### 15.8 Tabs & segmented

- **Underline tabs:** hairline track, 2px accent underline slides 24px between tabs (`fast`), panels crossfade (`base`).
- **Segmented control (pill):** container `ink.100`, active pill = `surface.card` + hairline + halo; wash slides between segments (Raycast rule, 180ms). Used for view switches and the theme control.
- Arrow-key navigation; `Home`/`End` bounds.

### 15.9 Selects & menus

- `CTkOptionMenu`/`CTkComboBox` for selects; dropdown restyled: `surface.raised`, hairline, `radius.surface`, hover row = `ink.100` wash, active row = accent wash slide.
- Context menus (`tk.Menu`/custom): grow from the pointer (`slow`), `Esc` closes, arrow-key nav with the sliding active wash.
- Tooltips: `caption`, `surface.raised` + hairline, fade in 120ms after 400ms sustained hover/focus; never chase the cursor.

### 15.10 Badges, chips, avatars

- Status pill: `status.*.bg` fill + `status.*.fg` text, `radius.pill`, `caption` 500. Never raw colored text alone.
- Chips (filters): `surface.card` + hairline, removable ×; enter with `micro-spring` 120ms, exit reverse 84ms.
- Avatars: 32px, `radius.pill`, initials `body` 500; hover per H12 (slide forward 2px + ring).

### 15.11 Charts

- `Canvas`-drawn (no library dependency): horizontal-only gridlines `ink.200`, muted `caption` axis labels, series from `dv.*`, tooltip = `surface.raised` card near the point.
- Interaction: hover crosshair + hovered series brightened, others dimmed (implemented as color swaps to a muted variant); draw-in at `draw` (300ms) per series, 60ms apart.
- Sparklines in KPI cards: 1.5px stroke, no axes, 40px tall, right of the numeral.
- Empty chart = the empty state (§11.1), never an unlabeled plot.

---

## 16. Accessibility

1. **Contrast:** floors per §3.6, verified for both themes at every release (the theme file is the single point of verification).
2. **Focus visibility:** every interactive element has a visible focus ring (§10.1). Focus order follows visual order: sidebar → header → content → overlays.
3. **Keyboard navigation (normative):**

| Context | Behavior |
|---|---|
| Global | `Ctrl+K` palette · `Ctrl+/` shortcuts help · `Ctrl+,` settings · `Alt` menu mnemonics |
| Tables | `↑↓` rows · `Space` select · `Enter` open · `F` filter toolbar |
| Dialog/drawer | `Esc` close · `Tab` trapped · focus returns to trigger · safe default autofocused (destructive: focus cancel) |
| Tabs/segmented | `←→` switch · `Home`/`End` bounds |
| Selects/lists | type-ahead · `↑↓` navigate · `Enter` select · `Esc` close |
| Sidebar | `↑↓` + `Enter` |
| Palette | `↑↓` + `Enter` + `Esc` |

All shortcuts discoverable via the `Ctrl+/` dialog; none hijack system defaults.
4. **Targets:** ≥ 28px minimum for pointer controls, 36px preferred, 44px for primary actions. Row-level actions keep the row itself reachable.
5. **Color is never the sole signal:** status = icon + text + color; chart series = label + color; selection = wash + check + state text where relevant.
6. **Reduced motion** is a persisted user setting (§12.5).
7. **Zoom/DPI:** all layout flows through CTk scaling (`set_widget_scaling` / `set_window_scaling`); windows reflow on the grid at 100–200%; tables scroll horizontally, never compress.
8. **Narrator (Windows):** dialogs announce via window titles + `label` text; focusable elements carry descriptive text; the status bar is announced on state change where Tk allows. Tk's assistive reach is limited — the mitigation is *redundant textual signals everywhere* (rule 5), never color-only.
9. **Dyslexia & reading:** never justify text; generous line-height (§5.2); no letter-spaced body copy.
10. **Locale:** currency, dates, and name ordering are locale-driven end to end.

---

## 17. Do's & Don'ts

**Do**
- Use the 1px hairline on every raised surface.
- Right-align numerals in fixed-width cells (§5.4).
- Enter from the trigger; exit in reverse at 0.7× (§12).
- Show the skeleton *of the actual layout*.
- Gate destructive actions behind confirm dialogs (autofocus on cancel).
- Give every empty state a next step.
- Keep one primary action per view.
- Use the luminance ladder for depth in dark mode, halo + hairline in light (§4, §9).
- Answer every press within 75ms.

**Don't**
- Don't use accent as decoration — action and selection only.
- Don't animate anything that reflows siblings — `place` the moving thing (§6.4, §12.4).
- Don't simulate a shadow where luminance + hairline will do (halo is light-mode only).
- Don't spring a panel, a card, or anything over 44px (§13.2).
- Don't loop anything that isn't a licensed loop (§14 rules).
- Don't use hover-only affordances without keyboard parity.
- Don't color a status without an icon or text companion.
- Don't use more than 6 categorical chart series.
- Don't open more than one dialog at a time.
- Don't hardcode a value — the theme file + token maps or it doesn't ship (§2.1, App. C).

---

## 18. Governance

1. **Capture:** every desktop UI change updates the relevant token in this spec and the theme file in lockstep. A PR that changes a color/radius/duration without updating both is blocked.
2. **Re-capture:** the web and desktop spec are reconciled monthly — the Forge never drifts from Corridor's contract (§0 rule).
3. **Polish:** monthly design-debt audit — scan for hardcoded colors, off-grid geometry, off-table durations, non-ladder elevations.
4. **Versioning:** this spec versions with the app (`3.1.x`); breaking visual changes bump minor, new tokens bump patch. `Reduce motion` support and contrast verification are non-negotiable release gates.

**Rollout waves:** W1 *Foundations* (theme file, tokens, type, shell) → W2 *Primitives* (buttons, inputs, cards, badges, states) → W3 *Patterns* (tables, dialogs, nav, toasts, status bar) → W4 *Refinement* (motion tables, springs, reduced-motion, a11y audit, do/don't enforcement).

---

## Appendix A — Master token table (light)

| Semantic token | Value |
|---|---|
| `surface.canvas` | `ink.50` `#F7F7F4` |
| `surface.card` | `ink.0` `#FFFFFF` |
| `surface.raised` | `ink.0` + halo 2px |
| `surface.overlay` | `ink.0` + halo 3px |
| `text.primary` | `ink.900` `#14140F` |
| `text.secondary` | `ink.600` `#64625A` |
| `text.tertiary` | `ink.500` `#8F8C80` |
| `text.muted` | `ink.400` `#B9B6AA` |
| `text.disabled` | `ink.400` `#B9B6AA` |
| `border.hairline` | `ink.300` `#D8D6CC` |
| `border.strong` | `ink.200` `#E7E6DF` |
| `accent.base` | `brand.500` `#4F7AFF` |
| `accent.hover` | `brand.600` `#3560E8` |
| `accent.pressed` | `brand.700` `#2A4CC0` |
| `accent.subtle` | `brand.50` `#EEF3FF` |
| `focus.ring` | 2px `accent.base`, width 1→2 |
| `radius.control` | 8 · `radius.surface` 12 · `radius.overlay` 16 |
| `elevation.hover` | halo 1px · `floating` 2px · `overlay` 3px |
| `font` | Inter / JetBrains Mono (scale §5.2) |

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
| `text.disabled` | `#4A5278` |
| `border.hairline` | `#232A5C` (brighter than surface) |
| `border.strong` | `#2C346B` |
| `accent.base` | `brand.500` (fills) / `brand.300` (text) |
| `accent.subtle` | `#1D2B6B` |
| `focus.ring` | 2px `brand.400` |
| elevation | luminance steps (§4.2); halo disabled |

## Appendix C — CTk implementation map (token → widget option)

| Concern | Token | CTk surface |
|---|---|---|
| Theme colors | all primitives/semantics | theme JSON (`set_default_color_theme`) |
| Appearance | light/dark/system | `set_appearance_mode()` |
| Scaling | — | `set_widget_scaling()` / `set_window_scaling()` |
| Surface fill | `surface.*`, `accent.subtle`, status bg | `CTkFrame(fg_color=…)` |
| Hover fill | `accent.hover`, washes | `CTkButton(hover_color=…)`; frames: `.after()` lerp |
| Press flash | `accent.pressed`, darkest steps | `fg_color` swap on press/release |
| Text | `text.*` | `text_color`, `text_color_disabled`, `font` |
| Borders | `border.*` | `border_color` + `border_width` |
| Radius | `radius.*` | `corner_radius` (≤ height/2) |
| Halo/shadow | `elevation.*` | child frame, `lower()`, offset per §9.2 |
| Focus ring | `focus.ring` | wrapper frame `border_width` 1→2 |
| Toggle | — | `CTkSwitch` (`fg_color`, `progress_color`, `button_color`, `button_hover_color`) |
| Checkbox | — | `CTkCheckBox` (`checkmark_color`, `fg_color`, `hover_color`, `border_color`) |
| Segmented | — | `CTkSegmentedButton` (`selected_color`, `unselected_color`, `selected_hover_color`, `unselected_hover_color`, `text_color`, `text_color_disabled`) |
| Select/combo | — | `CTkOptionMenu` / `CTkComboBox` (dropdown_* colors) |
| Progress | `accent.base` | `CTkProgressBar` (`fg_color`, `progress_color`, `border_color`) |
| Slider | — | `CTkSlider` (`progress_color`, `button_color`, `button_hover_color`) |
| Textbox | — | `CTkTextbox` (`fg_color`, `border_color`, `text_color`, `scrollbar_*`) |
| Scroll region | — | `CTkScrollableFrame` (`fg_color`, `border_color`, `scrollbar_button_color`, `scrollbar_button_hover_color`) |
| Tables | §15.4 | `ttk.Treeview` via `ttk.Style` (rowheight, map selection/hover) |
| Draw verbs | — | `CTkCanvas`: check draws, chart lines, rails, squircle, login gradient |
| Motion | §12–13 | `.after(16)` keyframe tables (§12.3 easing arrays, §13.1 spring presets) |

*End of specification. Corrections, omissions, and dissent are welcome — the Forge is a living contract, and per the re-capture loop it earns its place by staying true to the shipped product.*
