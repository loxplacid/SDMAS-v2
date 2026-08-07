# SDMAS Visual Effects v3 — "The Lens"

> The seventh normative expansion of the Corridor system (after Design System v3,
> Motion System v3, the App Redesign, The Ledger, The Foundry, and The Gloss).
> Codename: **The Lens**.
>
> **Scope:** the complete specification of the visual-effects layer — glass,
> blur, depth, light, gradients, particles, glow, and reflection — as one
> coherent *physics model*. Subtle elegance is a constraint, not an aspiration.
> Performance is a design input: every effect has a cost class and a tier.
>
> **Companion docs:** `DESIGN_SYSTEM_V3.md` (§8 Elevation & shadows, §9 Material:
> blur/glow/gradients, §11 Color), `MOTION_SYSTEM_V3.md` (the grammar every
> moving effect obeys), `COMPONENT_LIBRARY_V3.md` (the Foundry — every effect is
> anchored to a component ID), `MICRO_INTERACTIONS_V3.md` (The Gloss — the
> moment-by-moment experience of these effects).
>
> **Sources studied for principles only — nothing copied:** ReactBits (effects
> as first-class citizens, container-level morphing), BorisFX (physically-honest
> blur, the shutter model, optical-flow direction), Apple VisionOS (glass as a
> material with depth, not a decoration; light responding to position), modern
> AAA software (ambient occlusion logic, layered fog, screen-space effects that
> respect a budget). Every effect below is original to SDMAS.

---

## 0. Thesis — light is the interface

A premium surface is not made of *effects* — it is made of **light behaving
consistently**. Every rectangle in SDMAS exists inside one room with one lamp.

- **One light.** All surfaces are lit from the top-center of the window.
  Shadows fall down, never up, never sideways. A surface that breaks this rule
  reads as a different application bolted on.
- **Light, not decoration.** An effect earns its place by encoding *hierarchy*
  — which surface is above, which is alive, which is safe. If the effect does
  not answer a hierarchy question, it is noise.
- **The lens is quiet.** The user notices the *things* (the data, the cards,
  the focus ring), never the glass between them and the data. If an effect
  draws attention to itself, it has failed. Ninety percent of the lens is
  invisible on purpose; the ten percent that shows is the depth the eye needs
  to parse the stack.
- **Cost is a design parameter.** An effect that costs more than it encodes is
  not "nice" — it is a defect. This spec assigns every effect a cost class and
  a tier degradation. (See §12.)

The rules below are stated as *physics* — the lamp, the materials, the air —
because a physical model self-checks. An architect cannot mis-place a shadow if
the shadow is defined by "the lamp is up".

---

## 1. The lighting model

### 1.1 The lamp

```
Position   : top-center of the window, at elevation +1200px
Kind       : soft directional (key) + ambient fill
Key        : casts shadows directly below surfaces, offset (0, 1px .. 24px)
Ambient    : keeps shadowed faces readable — no pure-black cavities
Color      : light mode: neutral ink at low opacity; dark mode: black with a
             warm 2% tint (matches DS v3 §7 dark-mode warmth)
Falloff    : shadow opacity scales with elevation token, never with distance
             from window edge (the lamp is infinite in x and y)
```

Every shadow in SDMAS is the answer to one question: *how far is this surface
above the canvas?* The answer comes from the elevation token (§2), never from a
hardcoded `box-shadow`.

### 1.2 The three depth currencies

A surface's height above the canvas is communicated by **three currencies**,
used in strict proportion:

| Currency | What it encodes | Rules |
|---|---|---|
| **Shadow** | distance from canvas | Always present at `elevation.rest` or above; the hairline keeps it crisp in dark mode where shadows nearly vanish (DS v3 §8.2) |
| **Blur** | separation from the layer *behind* | Legal only where content scrolls or moves beneath (DS v3 §9.1); blur on an opaque layer is invisible waste |
| **Tint** | how much the surface "borrows" the environment | Glass tints 60–80% of the surface behind it; opaque surfaces tint 0% |

A surface may use all three, but each must earn its presence. A card at rest
uses shadow + hairline, **zero** blur, **zero** glow. Glow is earned only by
aliveness (focus, active, live) — never by altitude.

### 1.3 Focus & aliveness vs. elevation

Two independent axes, never conflated:

- **Elevation** = altitude above canvas. Changes only on explicit
  rest/hover/floating/overlay moves (Gloss K03, H04).
- **Aliveness** = is this surface responding to me? Encoded by glow, ring,
  or tint change — never by *raising* the surface.

A focused button does **not** lift. A hovering button does not glow in light
mode. Glow and shadow answer different questions; mixing them is how web
dashboards get their "everything is glowing" look. SDMAS forbids it (§11.3 of
DS v3 already forbids glow in light mode except success — The Lens extends this
to *any* blur that has no scrolling partner).

---

## 2. Elevation & dynamic shadows

### 2.1 The elevation scale (extends DS v3 §8.2)

DS v3 defines the elevation *names*. The Lens defines their **dynamic
behavior**:

| Elevation | Altitude | Dynamic behavior |
|---|---|---|
| `elevation.rest` | 0 | Static hairline + ring token. Never animates. |
| `elevation.hover` | +1px | Shadow **travels** with the pointer-enter, 180ms base (Gloss H04). Returns with exit ease. |
| `elevation.floating` | 4px | Menus, tooltips, toasts. Static altitude — animates only on enter/exit (Gloss O-family). |
| `elevation.overlay` | 16px | Modals, drawers. Static. Blur *behind* animates in with the overlay (Gloss O01 curtain). |
| `elevation.command` | 24px + blur | Command palette. The palette's shadow uses the **existing** `--shadow-2xl`; the *backdrop* is the blur, not the panel. |
| `elevation.spotlight` | 40px + glow | Coach marks. The only elevation that may carry colored glow in light mode. |

### 2.2 Dynamic shadow law

**Shadows may not animate continuously.** A shadow interpolates on two
occasions only:

1. **Enter/exit** of an overlay (in with the subject, out with the subject,
   never alone),
2. **Rest → hover** transitions of interactive cards and buttons.

All other shadow change is instant. A shadow that "breathes" or follows the
cursor is a violation — the lamp is fixed; the eye tracks the *surface*, not
its shadow.

### 2.3 The shadow stack

Every shadow is the existing DS v3 recipe **plus one optional glow layer**:

```
shadow = ring(1px, border color)                       # crisp edge, both themes
       + diffuse(soft, low opacity)                    # bulk altitude
       + key(larger, lower opacity)                    # directionality (down)
       + glowLayer  (DARK MODE ONLY, §4)               # luminance, never in light
```

No new shadow tokens are introduced. The Lens maps existing tokens:

| Elevation | Light tokens | Dark tokens |
|---|---|---|
| rest | `--shadow-sm` | `--shadow-xs` (brighter hairline) |
| hover | `--shadow-md` | `--shadow-md` (dark-mode shadows already carry higher opacity — DS v3 §8.2 luminance strategy) |
| floating | `--shadow-lg` | `--shadow-lg` |
| overlay | `--shadow-xl` | `--shadow-xl` |
| command | `--shadow-2xl` | `--shadow-elevated` |
| spotlight | `--shadow-elevated` + `glow.accent` | `--shadow-elevated` + `glow.accent` |

### 2.4 Motion-blurred shadows (the AAA trick, cheap)

BorisFX's motion-blur insight, reduced to one law: **a surface in motion casts
a shadow that *trails* — the faster the move, the shorter and weaker the
shadow.** Implemented as a `filter: drop-shadow` on the moving layer during
transition, or — the cheaper route — a scale-preserving `translate` with the
shadow *inside* the animated layer so the GPU composites one element. The
palette slide (Gloss C13) and drawer slide (Gloss O03) use this.

Rule: the trailing shadow is **at most 60ms of the move's duration** and
**never on text-bearing surfaces**. This is a blur *of the shadow*, never of
the text (readability first — DS v3 §1, the BorisFX principle already adopted).

---

## 3. Glass — the visionOS material, reduced

VisionOS glass is depth *and* translucency *and* a specular edge. SDMAS glass is
the same idea at web cost. Glass here means: **a surface that passes light from
behind it, tinted by the theme and edged by a hairline.**

### 3.1 The four glass states

| State | Recipe | Legal homes |
|---|---|---|
| **`glass.pane`** — quiet chrome | `backdrop-blur(8px)` + 72% surface tint + hairline | App header, sidebar rail (collapsed), drawer header, sticky table band |
| **`glass.float`** — floating layer | `backdrop-blur(16px)` + 64% tint + hairline + elevation.floating | Tooltips, menus, toasts, the notification bell popover |
| **`glass.focus`** — the palette | `backdrop-blur(24px)` + 60% tint + hairline + elevation.command | Command palette, spotlight backdrop |
| **`glass.bare`** — seam, no blur | tint only (no `backdrop-filter`) | Scroll-catch bands, table header pin seams, any surface already over opaque content |

### 3.2 Glass rules (the lens's ten commandments)

1. **Blur is always paired with 60–80% tint.** A blur with no tint is the
   "80s terminal" artifact — unreadable and unhinged. Every `glass.*` token is
   (blur, tint, hairline) as one unit.
2. **No blur without a partner.** The surface behind must scroll, move, or
   change. Blur over a static wall is invisible waste (DS v3 §9.1) and is the
   single most common "why is my app slow" cause.
3. **Text never sits directly on blurred content.** Text lives on the tinted
   glass (60–80% opaque), which keeps contrast in the AA range without a shadow
   hack. If text must float above raw content, it gets the surface tint behind
   it — never `text-shadow` fog.
4. **`backdrop-filter` is the only blur mechanism.** No SVG-filter glass, no
   duplicate-layer trick. One mechanism, one cost model (§12).
5. **No saturation boosts.** `backdrop-filter: saturate()` is a flashy
   signature of copied design systems. The Lens is neutral: **blur + tint
   only**. The light behind the glass is the theme's light, un-amplified.
6. **Corners belong to the surface.** A glass pane may sit on the radius scale
   (`--radius-md` at rest, `--radius-lg` when floating) — but the blur radius
   never exceeds 24px and the glass never has *its own* inner glow in light
   mode.
7. **`prefers-reduced-transparency` collapses glass to tint-only** — the
   surface becomes opaque `surface.1` with the hairline preserved. Hierarchy
   survives; glass does not.
8. **Glass is never interactive by itself.** A glass backdrop (overlay dim) is
   a passive layer; clicking it dismisses (APG dialog-dismiss), but it never
   has hover/focus states of its own.
9. **The dark-mode hairline brightens** (DS v3 §8.2) so glass reads *against*
   dark content; in light mode the hairline is the only edge a glass pane gets
   — no drop-shadow on panes below `elevation.floating`.
10. **Cost floor:** a screen may host at most **one `glass.lg` blur, two
    `glass.md`, and four `glass.sm`** simultaneously. See §12.3.

### 3.3 Frosted glass (non-interactive)

`glass.frosted` — a *static* decorative pane: card front panels on the login
screen, report cover art, empty-state canvases. Recipe: `glass.md` blur over a
`Dawn` gradient base, at 55% tint. Frosted panes never animate their blur and
never host interactive controls (buttons live on the opaque part of the
surface). Frosted is the *only* place a decorative gradient and a blur co-exist.

---

## 4. Glow — the dark cousin

DS v3 §9.2 defines *when* glow is legal. The Lens defines *how* glow is
rendered so it never looks cheap:

### 4.1 The glow recipe

```
glow = radial-gradient(fade-to-edge) OR box-shadow with 0 blur-direction
```

| Token | Recipe | Rules |
|---|---|---|
| `glow.focus` | 2px accent ring + 12px accent glow @ 25% | Ring is `outline`, glow is `box-shadow` — the ring survives `prefers-reduced-transparency` |
| `glow.accent` | 8px accent glow @ 18% | Primary button hover (dark only), active nav-rail indicator |
| `glow.success` | one expanding ring, 1.2s, once | The only glow legal in light mode (DS v3 §13.6); fades to `transparent`, never loops |
| `glow.live` | PulseDot — the only repeating glow | 2px dot, 4px halo, 2s period, **opacity-only** animation |

### 4.2 Glow laws

1. **Glow is luminance, not light.** It never competes with shadows; a surface
   with a glow must not also carry an elevation above `floating`.
2. **Glow never animates position.** It scales and fades (opacity + scale only,
   GPU-composite). A glow that "chases" the pointer is a violation.
3. **One glow per surface.** A surface may be focused *or* hovered *or* live —
   never two glows at once. The hierarchy question has one answer.
4. **Glow decay is exponential.** The `glow.success` ring expands at `ease-out`
   and dies; there is no sustained pulse outside `glow.live`. Sustained
   animation is how apps feel like arcades.

---

## 5. Ambient lighting — the room

Ambient light is what keeps flat surfaces from looking flat. SDMAS uses three
instruments, all extremely quiet:

### 5.1 The skylight gradient

A **very** low-contrast vertical gradient on the app canvas (behind all
chrome): `surface.0 → surface.1` over the full window height, static, painted
once. It gives the room a ceiling without a single moving pixel. In dark mode
the skylight runs `ink.950 → ink.900` — the "night office" warmth from DS v3
§7.

### 5.2 The wash

Interactive surfaces get a **hover wash** — the existing Ghost-button fill
technique generalized: a `radial-gradient` at the pointer position on
interactive rows/cards, opacity 0 → 1 on hover. This is the *cheap* ambient
answer to "the light follows the hand" — implemented as one CSS variable
(`--wash-x`, `--wash-y`) set on pointermove, **throttled to 60ms** (never per
frame), and cleared on leave.

- Cost class: **free** (composited; the gradient is one layer per surface).
- Wash is **tab-key-disabled on arrival**: a keyboard-focus moves the wash to
  the element center — hover secrets stay a pointer affair (Gloss law, Foundry
  §3).

### 5.3 Ambient occlusion — fake it with the hairline

AAA ambient occlusion darkens *cavities*. The web equivalent, at zero cost, is
the **hairline ring** (already in every DS v3 shadow) — the cavity between
surfaces is the 1px border, darkened in light mode, brightened in dark. The
Lens declares the hairline the **official ambient-occlusion mechanism**:
**two adjacent surfaces may never be delineated by two shadows** — one hairline
between them is the occlusion. This kills the "every card has its own shadow"
pile-up that makes dashboards look like stacked boxes.

---

## 6. Gradient overlays

DS v3 §9.3 defines the two gradient families (Dawn, Surface tint) and their
rules. The Lens adds their *physical* behavior:

### 6.1 Animated gradients — when and how

Animated gradients are the most-abused effect on the web. SDMAS allows exactly
**one** class of animated gradient: the **aurora**, and exactly one home: the
login screen and empty-state canvases.

- **Aurora** = two `Dawn` blobs (radial-gradients, low-opacity, 120px blur
  radius) drifting at **0.05 px/frame max** — imperceptible speed — over a
  static Dawn base.
- **Cost floor:** the blobs are `will-change: transform` + `transform:
  translate` (composited), the base is static, and the whole animation pauses
  on `document.hidden` and under `prefers-reduced-data`.
- **The rule:** any other gradient that animates — shimmer on buttons,
  rainbow borders, liquid headers — is forbidden. Shimmer is allowed on
  *skeletons* only (Gloss L03, opacity-only).

### 6.2 Gradient overlays on media

Images (report covers, profile photos) get **one** optional overlay: a
bottom-fade `Dawn` at 12–18% for text legibility. It is static, non-blurred,
and must be removable in `prefers-reduced-data`. No duotones, no hue-rotated
gradients — the room has one lamp.

### 6.3 Degradation

- `prefers-reduced-data`: gradients flatten to the *base* color (DS v3 §9.3).
- Print: all gradients flatten (they already do — DS v3 §9.3).

---

## 7. Background particles & floating elements

### 7.1 The particle policy

SDMAS is a school-operations instrument. Particles are legal in exactly one
context: **the login backdrop** (and a *static* nodule version on empty-state
canvases). The policy is `≤ 12` particles, `≤ 8px` diameter, opacity 6–14%,
**opacity-only drift** (no physics), paused on `prefers-reduced-motion`,
removed on `prefers-reduced-data`.

**No particles anywhere else. No confetti, no sparkles, no "magic dust."** A
classroom roll is not a celebration — the success pulse (Gloss) carries all
the joy.

### 7.2 Floating elements

"Floating" in SDMAS means **floating above canvas**, not *bobbing*. The
Gloss defines the float lifecycle (H04 lift, K03 handshake). The Lens adds:

- **No idle bobbing.** A card that floats is either resting at its altitude or
  responding to the pointer. Continuous vertical oscillation is forbidden —
  it is the signature of a "template dashboard."
- **Parallax on scroll: none.** Content scrolls, chrome doesn't. The lens does
  not bend the world.
- **One floating subject per viewport.** Two elements drifting at once cancel
  each other's depth message.

### 7.3 The float shadow rule

A floating element's shadow *lands* on the canvas — it does not follow the
element into the air. Implement the shadow on a **sibling underlayer** that
fades with distance (the element rises → shadow softens → blur grows 8→12px)
or — the default — keep the shadow static inside the elevated layer. Simplicity
wins: the static shadow is the default; the rising-shadow is reserved for the
spotlight/onboarding only.

---

## 8. Gooey transitions & shape morphing

ReactBits's gooey-nav insight is **containers that morph instead of vanishing**.
SDMAS adopts the principle (one shape changes into another) without the goo
filter: **gooey is a transition policy, not an SVG filter.**

### 8.1 The morph rules

1. **Morph replaces fade-in/fade-out** for *structural* chrome: the nav rail
   expanding, a panel sliding to its new width, the sidebar collapse (already
   choreographed via the Motion grammar). One container interpolates; the old
   one never flickers out.
2. **The interpolated property is layout-geometry** (width, height, transform)
   — **not** `border-radius` on text-bearing surfaces (radius morphs at
   `--radius-md` are legal on icon tiles and avatars only, where no glyph is
   distorted).
3. **Morphs obey the Motion grammar's choreography** (§4 of MOTION_SYSTEM_V3):
   one subject per moment, enter = reverse of exit, stagger caps.
4. **No liquid blobs.** The actual SVG `feGaussianBlur` gooey filter is
   forbidden (cost + indistinct edges read as a bug in a data instrument). The
   *concept* — continuity of shape — is the adoption.

### 8.2 The sidebar morph (the flagship)

The AppLayout sidebar collapse is the model morph: width 256 → 72, the icon
grid re-flows with FLIP, the label column fades at 40% of the move (label
legibility during a width morph is never compromised), and the rail's glass
tint stays constant so the morph reads as *one pane resizing*, not two panes
swapping.

---

## 9. Surface layering — the stack grammar

### 9.1 The layer names

Every pixel in the app belongs to one of these layers:

| Layer | Material | Owns |
|---|---|---|
| **Canvas** | `surface.0` + skylight | page background |
| **Chrome** | `glass.pane` | header, rail, footer |
| **Content** | `surface.1` | cards, table bands |
| **Floating** | `glass.float` | menus, tooltips, toasts |
| **Overlay** | `glass.focus` / tinted dim | modals, drawers, palette |
| **Spotlight** | `elevation.spotlight` + glow | coach marks, onboarding |

### 9.2 Layering laws

1. **A layer may only rest on the layer below it.** Chrome rests on canvas,
   content on chrome/canvas, floating on content, overlay on everything. A card
   floating *over* the rail, or a tooltip *inside* the header, is a stack bug.
2. **One material per layer.** A modal's backdrop is tint+blur; its panel is
   opaque surface — the panel does **not** get glass too. Glass-on-glass is how
   apps get the "fog" look.
3. **The z-ladder is the layer order** (DS v3 §8.3). Layers are z-index, not
   suggestions.
4. **Blur count is a per-viewport budget** (§12.3), enforced at review:
   a modal (overlay blur) + its backdrop (dim) + the palette (glass.focus) is
   already three blurs — no fourth may open without closing one.

### 9.3 The seam rule

Where two layers meet, exactly one of these is present: **a hairline, a
shadow, or a blur seam**. Never two, never none. The scroll-catch band on the
sticky table header is a blur seam (`glass.bare` + tint); the drawer edge is a
shadow + hairline; the modal backdrop is a blur seam with no hairline (the
backdrop's job is to *dissolve*, not outline).

---

## 10. Reflections & specular edges

Soft reflections are the most subtle instrument in the lens — and the easiest
to overdo.

### 10.1 The specular edge

Premium surfaces get a **specular top edge**: a 1px gradient line
`rgba(255,255,255,0.08) → transparent` along the top of *elevated* surfaces —
dark mode only, on `glass.float` and `glass.focus`. It is the "light catching
the rim" of the glass. Light mode does not get specular edges (the hairline is
the edge).

### 10.2 Reflection surfaces

**No mirror reflections.** A flipped, fading copy of a chart under the chart is
the signature of a 2015 dashboard template. SDMAS's "reflection" is the
**under-glow** — a soft tint of the surface's accent at 6–10% opacity, 20px
below the floating element, baked into the floating shadow. It suggests the
surface reflects *the room*, not itself. Legal only for `glass.float` over
content, dark mode only.

---

## 11. Motion blur (real)

The BorisFX lesson, honored properly: motion blur communicates *direction and
speed*. UI is not video — full motion blur on text destroys readability. The
Lens's policy:

1. **UI content: no motion blur.** Text, icons, and data glyphs never blur
   (DS v3 §1, the adopted "readability first" principle). This is absolute.
2. **The trail substitute:** direction is already encoded by the Cardinal
   Compass (Motion §2.2) — an element exiting East *is* moving East. Adding
   blur is redundant.
3. **One legal use: the ghosted trail on drag-and-drop.** When a row is picked
   up (Gloss D02), the *original position* keeps a ghost — the ghost is the
   drop-shadow of the motion, not a blur of the row. Implemented as an
   opacity-fading copy, 120ms. This is the closest SDMAS comes to motion blur,
   and it is still composited.
4. **What BorisFX's shutter means to us:** the shutter is a *global intensity
   knob*. SDMAS's shutter is the **Motion tier** (Motion §3.4): `precise` opens
   the shutter (full effect), `efficient` closes it (opacity-only ≤ 75ms),
   `minimal` closes it entirely. One knob, three stops — the shutter is a
   design input, not a per-effect toggle.

---

## 12. The performance model

### 12.1 Cost classes

Every effect in The Lens is stamped with a cost class. Review gate: an effect
may only be used at a class the *tier* allows.

| Class | Mechanism | GPU/compositor | Examples |
|---|---|---|---|
| **C0 — free** | none (tokens only) | — | hairline, tint, elevation shadows |
| **C1 — composited** | `transform`/`opacity` only | yes, always | lifts, fades, washes, glow scale |
| **C2 — backdrop** | `backdrop-filter` | yes, sampled per frame | all `glass.*` |
| **C3 — repaint** | paint-affecting (radius, gradient-position, box-shadow mutation) | no — raster | aurora blobs (blur radius), specular edges at rest |
| **C4 — forbidden** | SVG filters, canvas re-render loops, `filter: blur()` on text, per-frame `box-shadow` animation | — | gooey SVG, mirror reflections, text blur |

**The law:** C1 is unlimited within the motion budget (Motion §13). C2 is
budgeted (§12.3). C3 is limited to two instances total (the login aurora + one
specular edge). C4 never ships.

### 12.2 The 60fps contract

- Every animation runs on the compositor: `transform` and `opacity` only,
  `will-change` declared on the animated element, no layout thrash in the
  rAF loop.
- The **frame budget** is 8ms paint + 8ms composite; any effect measured over
  it degrades a tier (§12.4).
- **The rAF count:** at most one rAF loop per viewport (the wash throttle and
  the aurora share the app's single ticker; the Ledger's virtualizer is the
  second, and they never run in the same viewport).
- `document.hidden` freezes every loop. Not *slows* — freezes.

### 12.3 The blur budget

| Metric | Cap |
|---|---|
| `glass.lg` (24px) per viewport | 1 |
| `glass.md` (12–16px) per viewport | 2 |
| `glass.sm` (4–8px) per viewport | 4 |
| Total `backdrop-filter` layers per viewport | 7 |
| Total blur *area* per viewport | ≤ 30% of viewport pixels |

The sticky table header counts as one `glass.sm`. The app header is one
`glass.md`. The command palette is one `glass.lg`. A modal open **over** the
header does not double-charge the header (the header is behind the dim and the
browser culls it) — but opening the palette while a modal is open is charged
to both (1 lg + 1 md = still inside the 7-layer cap, and the modals' layer
drops when the palette claims `glass.lg` priority — the palette outranks).

**Priority order when over budget:** command palette → modal → drawer header →
app header → sticky band → decorative glass. Decorative glass is the first to
collapse to `glass.bare` (tint, no blur).

### 12.4 Tier degradation

| Tier | Blur | Glow | Gradients | Particles | Motion |
|---|---|---|---|---|---|
| `precise` (default desktop) | full budget | full | aurora allowed | ≤ 12 | full grammar |
| `efficient` (reduced-motion or low-power) | `glass.bare` everywhere (tint only) | static ring, no halo animation | static gradients only | 0 | opacity-only ≤ 75ms |
| `minimal` | tint only | ring only | flat colors | 0 | none |

Tier is decided once per session by `useMotionTier` (Motion §3.4) plus
`prefers-reduced-transparency` (forces `efficient` blur) and
`prefers-reduced-data` (forces `minimal` gradients/particles). An effect may
never *detect* a tier and "compromise" — the tiers are closed sets.

---

## 13. The effect catalog — where each effect lives

Every effect named above, anchored to a Foundry component and a Gloss entry:

| Effect | Component | Gloss | Class | Tier floor |
|---|---|---|---|---|
| Card lift + shadow travel | G1 Card | H04 | C1 | efficient |
| Button press handshake | A1 Button | K03 | C1 | minimal (still works) |
| Glass app header | F? AppHeader | — | C2 | efficient (bare) |
| Glass float menus | D? Popover / C? Tooltip | O06 | C2 | efficient (bare) |
| Palette glass + backdrop | D11 CommandPalette | C13 | C2 | efficient (bare) |
| Modal dim + blur seam | D1 Modal | O01 | C2 | efficient (bare) |
| Drawer glass + slide | D2 Drawer | O03 | C2 | efficient (bare) |
| Scroll-catch band | E2 DataTable | — | C2 (bare) | efficient |
| Sidebar morph | G2 AppShell | P? nav | C1 | efficient |
| Wash on interactive rows | E2 DataTable / G1 Card | S-family | C1 | efficient |
| Aurora backdrop | — login, empty states | L? | C3 (×2 max) | efficient → static |
| Particles | — login | — | C1 | efficient → none |
| Specular edge | G1 Card floating, D11 | — | C3 (×1) | dark only |
| Under-glow reflection | D? Popover | — | C0 | dark only |
| Success pulse | C? Toast | N-family | C1 | efficient |
| PulseDot live halo | C? PulseDot | N? | C1 | efficient |
| Trail ghost on drag | E2 DataTable / Kanban | D02 | C1 | efficient |
| Sticky table glass | E2 DataTable | — | C2 (sm) | efficient (bare) |
| Spotlight + glow | — onboarding | O? | C2 + C1 | efficient |
| Empty-state skylight | G? EmptyState | — | C0 | minimal |

---

## 14. Governance

An effect ships when all of these are true:

1. **It answers a hierarchy question.** State the question in the PR
   description ("why is this surface above the canvas?") — if the answer is
   "because it looks nice," the effect is rejected.
2. **It is a token, not a hardcode.** Blur radius, tint %, glow opacity,
   shadow offset, aurora speed — every value exists in the CSS token layer
   (extending the existing `--blur-*`, `--shadow-*`, `--glow-*` namespaces).
   Zero raw values in components.
3. **It is classed and tiered.** The cost class is stamped; the tier
   degradation is implemented — not planned. `prefers-reduced-transparency`
   and `prefers-reduced-data` are honored, not noted.
4. **It is single-subject.** One effect per moment, per surface, per viewport
   (§9.2 law 4, Motion §4.5). Screenshots are reviewed for stacking: two
   glows, two blurs in the same layer, or one animation too many is a
   rejection.
5. **It passes the quiet test.** Viewed at 50% zoom, from 3 feet: the effect
   should be *felt*, not *seen*. If it draws the eye first, it's too loud.
6. **It is measured.** The frame budget (§12.2) is verified in the browser
   (performance panel) for any C2/C3 effect before merge. The blur budget
   (§12.3) is counted in review.
7. **It is documented in The Gloss.** No undocumented state — an effect without
   a Felt/Spec/Tier entry does not exist.

**The shutter rule (the single most important governance line):** every effect
in this document is controlled by exactly one global intensity knob — the
Motion tier. No component may add its own "subtlety slider."

---

## 15. Implementation map (ordered PRs)

1. **The token layer** — extend `index.css` with the `--glass-*`, `--specular-*`,
   `--wash-*`, `--aurora-*` namespaces mapping to existing `--blur-*`,
   `--shadow-*`, `--glow-*` tokens. Pure CSS, zero behavior change.
2. **The glass utilities** — `.glass-pane`, `.glass-float`, `.glass-focus`,
   `.glass-bare`, `.glass-frosted` classes (blur + tint + hairline as units),
   with `prefers-reduced-transparency` collapse built in.
3. **The wash** — the pointer-throttled hover wash on `G1 Card` interactive
   variant and `E2 DataTable` rows (one shared hook, 60ms throttle, keyboard
   arrival centers it).
4. **The float/spotlight shadows** — replace per-component shadows with the
   elevation-mapped tokens; add the dark-mode specular edge + under-glow to
   `glass.float` surfaces.
5. **The aurora + particles** — the login backdrop (static base + two C3 blobs
   + ≤ 12 C1 particles) with full tier degradation; the app's single rAF
   ticker.
6. **Retrofit the chrome** — app header, drawer, palette, modal dims to the
   glass utilities (they already use `backdrop-blur-sm` — the utility layer
   standardizes and adds the tint + hairline).
7. **The sidebar morph** — replace the current collapse with the §8.2 morph
   (FLIP + label fade at 40%).
8. **Audit gate** — walk every screen against §14; the blur budget counter and
   the quiet test are manual review steps in the PR template.

---

## 16. Acceptance criteria

- The app renders with **zero C4 effects** and at most **two C3 effects** in
  any viewport (normally the login aurora only).
- Every surface's depth is explainable by §1's three currencies; no surface
  uses more than it needs.
- Opening the command palette, a modal, a drawer, and a tooltip in sequence
  never exceeds the §12.3 blur budget.
- With `prefers-reduced-motion`, `prefers-reduced-transparency`, and
  `prefers-reduced-data` all set: the app is fully functional, fully legible,
  and every surface still states its hierarchy (tint + hairline survive).
- With the battery/low-power flag: the frame budget holds; the app does not
  drop below 60fps on the Ledger's 10k-row scroll with the header glass and
  the wash active.
- No screenshot in the product shows two surfaces competing for attention —
  the quiet test (§14.5) passes at review.
