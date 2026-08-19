# SDMAS v2 — Design System

> **Version:** 4.0
> **Date:** August 19, 2026
> **Status:** Authoritative reference for all UI work

---

## 1. Design Principles

### 1.1 Core Identity

SDMAS is an **institutional operating system**. It is not a collection of CRUD pages. Every pixel must communicate:

- **CONTROL** — The user is in command of their institution
- **TRUST** — Data is accurate, actions are deliberate
- **PRECISION** — Every element has a purpose
- **INTELLIGENCE** — The system surfaces what matters
- **SCALE** — Built for thousands of records and dozens of concurrent users

### 1.2 Design Values

| Value | Meaning | Anti-Pattern |
|-------|---------|--------------|
| **Dense** | Information density > whitespace | Giant cards with 3 lines of text |
| **Calm** | Neutral surfaces, restrained color | Rainbow gradients, glowing borders |
| **Deliberate** | Every element earns its space | Decorative blobs, animated backgrounds |
| **Consistent** | Same pattern = same appearance | 5 different card styles across pages |
| **Fast** | Sub-100ms interactions feel instant | Heavy animations that delay response |
| **Honest** | Real data, real states, real errors | Fake dashboards, mock data |

### 1.3 What We Are NOT

- ❌ Not a design portfolio piece
- ❌ Not a consumer app
- ❌ Not an "AI dashboard" with glowing orbs
- ❌ Not a template with rainbow gradient cards
- ❌ Not a SPA that hides behind animations

### 1.4 What We ARE

- ✅ A serious $1M+ enterprise tool
- ✅ An institutional command platform
- ✅ A data-dense operational interface
- ✅ A tool school administrators use daily
- ✅ A system that earns trust through consistency

---

## 2. Color System

### 2.1 Brand Colors

| Token | Value | Usage |
|-------|-------|-------|
| `--color-brand-navy` | `#080c24` | Sidebar background, primary dark |
| `--color-brand-navy-light` | `#11163a` | Sidebar hover, dark surfaces |
| `--color-brand-navy-mid` | `#1a2052` | Dark mode surface |
| `--color-brand-accent` | `#4f7aff` | Primary actions, links, focus rings |
| `--color-brand-accent-hover` | `#3b64e6` | Accent hover state |
| `--color-brand-accent-subtle` | `rgba(79, 122, 255, 0.08)` | Accent backgrounds (light) |
| `--color-brand-accent-ring` | `rgba(79, 122, 255, 0.35)` | Focus rings |

**Rule:** The accent color appears on **one element per visual region** — the primary action, the active nav item, the selected filter. Never paint entire sections in accent.

### 2.2 Semantic Colors

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--color-success` | `#0f973d` | `#0f973d` | Positive states, confirmations |
| `--color-success-light` | `#e9f9ee` | `#052e16` | Success backgrounds |
| `--color-success-dark` | `#06722d` | `#0f973d` | Success hover |
| `--color-warning` | `#d97706` | `#d97706` | Caution, attention needed |
| `--color-warning-light` | `#fef6e6` | `#341a00` | Warning backgrounds |
| `--color-warning-dark` | `#b45309` | `#d97706` | Warning hover |
| `--color-danger` | `#dc2626` | `#dc2626` | Errors, destructive actions |
| `--color-danger-light` | `#fae8e8` | `#2d0909` | Danger backgrounds |
| `--color-danger-dark` | `#b91c1c` | `#dc2626` | Danger hover |
| `--color-info` | `#0284c7` | `#0284c7` | Informational, neutral-positive |
| `--color-info-light` | `#e0f2fe` | `#0c334e` | Info backgrounds |
| `--color-info-dark` | `#0369a1` | `#0284c7` | Info hover |

**Rule:** Semantic colors are for **status and feedback only**. Never use them for decorative purposes. A success badge is green. A success gradient hero is not.

### 2.3 Surface System

| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--color-bg` | `#f5f5f7` | `#080c24` | Page background |
| `--color-bg-warm` | `#f8f7f4` | `#0a0f2a` | Alternate page background |
| `--color-surface` | `#ffffff` | `#11163a` | Cards, panels, modals |
| `--color-surface-hover` | `#f0f0f3` | `#181e4a` | Hover states on surfaces |
| `--color-surface-elevated` | `#ffffff` | `#1a2052` | Elevated surfaces (dropdowns) |
| `--color-surface-overlay` | `rgba(0,0,0,0.45)` | `rgba(0,0,0,0.60)` | Modal overlays |

**Rule:** Surfaces have **subtle elevation hierarchy**. Background < Surface < Elevated. Never use gradients to differentiate surfaces — use shadow and border.

### 2.4 Border System

| Token | Value | Usage |
|-------|-------|-------|
| `--color-border` | `#e3e4e9` / `#1e2456` | Default borders |
| `--color-border-light` | `#eef0f4` / `#181e45` | Subtle dividers |
| `--color-border-hover` | `#c8cad2` / `#2a3270` | Border on hover |
| `--color-divider` | `#e8eaef` / `#1e2456` | Section dividers |

**Rule:** Borders are **1px solid**. No 2px borders except on very rare emphasis cases. No dashed borders in the main UI.

### 2.5 Text System

| Token | Value | Usage |
|-------|-------|-------|
| `--color-text-primary` | `#0b0e1a` / `#e4e6ef` | Headings, primary content |
| `--color-text-secondary` | `#464b61` / `#9ea3bf` | Body text, descriptions |
| `--color-text-tertiary` | `#868da6` / `#636b90` | Labels, timestamps |
| `--color-text-muted` | `#aeb4c9` / `#434a6e` | Placeholders, hints |
| `--color-text-inverse` | `#ffffff` / `#080c24` | Text on colored backgrounds |

**Rule:** Text hierarchy must be **clear at a glance**. Primary for content, secondary for descriptions, tertiary for metadata. Never use more than 3 text levels in a single component.

---

## 3. Typography

### 3.1 Font Stack

```css
--font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
--font-mono: 'JetBrains Mono', 'SF Mono', 'Fira Code', monospace;
```

**Rule:** Inter only. No other serif or display fonts. Monospace for code, IDs, and numeric data only.

### 3.2 Type Scale

| Token | Size | Usage |
|-------|------|-------|
| `--text-caption` | 11px | Timestamps, fine print |
| `--text-xs` | 12px | Badges, compact labels |
| `--text-sm` | 13px | Table cells, secondary text |
| `--text-base` | 14px | Body text, form inputs (base size) |
| `--text-md` | 15px | Emphasized body text |
| `--text-lg` | 16px | Section headings |
| `--text-xl` | 18px | Card titles |
| `--text-2xl` | 22px | Page titles |
| `--text-3xl` | 26px | Major page titles (rare) |

**Rule:** The base font size is **14px**. Body text is `--text-base`. Page titles are `--text-2xl` (22px). **Never use `--text-4xl` or larger** in production UI — that's for marketing pages only.

### 3.3 Font Weights

| Token | Value | Usage |
|-------|-------|-------|
| `--font-normal` | 400 | Body text |
| `--font-medium` | 500 | Labels, emphasized text |
| `--font-semibold` | 600 | Headings, buttons |
| `--font-bold` | 650 | Page titles only |

**Rule:** Body text is `font-normal` (400). Labels and buttons are `font-medium` (500). Headings are `font-semibold` (600). Only page titles use `font-bold`.

### 3.4 Line Heights

| Token | Value | Usage |
|-------|-------|-------|
| `--leading-tight` | 1.2 | Headings |
| `--leading-snug` | 1.35 | Compact text |
| `--leading-normal` | 1.5 | Standard |
| `--leading-relaxed` | 1.65 | Body text (default) |

---

## 4. Spacing

### 4.1 Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--space-1` | 4px | Tight gaps (icon to text) |
| `--space-1.5` | 6px | Form field gaps |
| `--space-2` | 8px | Compact element gaps |
| `--space-3` | 12px | Standard element gaps |
| `--space-4` | 16px | Section internal padding |
| `--space-5` | 20px | Card padding |
| `--space-6` | 24px | Section gaps |
| `--space-8` | 32px | Major section gaps |
| `--space-10` | 40px | Page section spacing |
| `--space-12` | 48px | Page-level spacing |

### 4.2 Spacing Rules

| Context | Spacing |
|---------|---------|
| Icon to label | `--space-2` (8px) |
| Label to input | `--space-1.5` (6px) |
| Form fields | `--space-4` (16px) vertical |
| Card internal padding | `--space-5` (20px) |
| Between cards | `--space-4` to `--space-6` (16-24px) |
| Page sections | `--space-8` (32px) |
| Page margin | `--space-6` to `--space-8` (24-32px) |

---

## 5. Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 6px | Badges, small elements |
| `--radius-md` | 8px | Buttons, inputs |
| `--radius-lg` | 10px | Cards, dialogs |
| `--radius-xl` | 12px | Modals, large cards |
| `--radius-2xl` | 16px | Feature cards (rare) |
| `--radius-full` | 9999px | Pills, avatars |

**Rule:** The standard radius is **10px** (`--radius-lg`). Inputs and buttons use **8px** (`--radius-md`). Cards use **10px**. Modals use **12px**. **Never use `--radius-2xl` (16px) or larger** on cards — it looks consumer, not enterprise.

### 5.1 Radius by Component

| Component | Radius |
|-----------|--------|
| Button | `--radius-md` (8px) via `rounded-[10px]` |
| Input / Select | `--radius-lg` (10px) via `rounded-[10px]` |
| Badge | `--radius-full` (pill) |
| Card | `--radius-xl` (12px) via `rounded-xl` |
| Modal | `--radius-xl` (12px) via `rounded-2xl` |
| Dropdown | `--radius-lg` (10px) |
| Table row | 0 (no radius) |
| Avatar | `--radius-full` (circle) |
| Toast | `--radius-lg` (10px) |
| Tooltip | `--radius-sm` (6px) |

---

## 6. Elevation (Shadows)

| Token | Usage |
|-------|-------|
| `--shadow-xs` | Subtle border effect (1px ring) |
| `--shadow-sm` | Default card shadow |
| `--shadow-md` | Hover state, elevated panels |
| `--shadow-lg` | Dropdowns, popovers |
| `--shadow-xl` | Modals, drawers |
| `--shadow-2xl` | Command palette |

**Rule:** Shadows are **subtle and warm**. Every shadow includes a 1px border ring for definition. Never use colored shadows (no `shadow-blue-500/20`). Never use `shadow-2xl` on cards — only on the highest-elevation surfaces.

### 6.1 Elevation Ladder

| Level | Shadow | Usage |
|-------|--------|-------|
| 0 | None | Page background |
| 1 | `shadow-xs` | Default cards |
| 2 | `shadow-sm` | Cards at rest |
| 3 | `shadow-md` | Hover state, elevated cards |
| 4 | `shadow-lg` | Dropdowns, popovers |
| 5 | `shadow-xl` | Modals, drawers |
| 6 | `shadow-2xl` | Command palette, toast stack |

---

## 7. Component Specifications

### 7.1 Buttons

| Variant | Background | Text | Border | Hover |
|---------|-----------|------|--------|-------|
| **primary** | `--color-brand-accent` | White | None | `--color-brand-accent-hover` |
| **secondary** | `--color-surface` | `--color-text-primary` | `--color-border` | `--color-surface-hover` |
| **danger** | `--color-danger` | White | None | `--color-danger-dark` |
| **ghost** | Transparent | `--color-text-secondary` | None | `--color-surface-hover` |
| **outline** | Transparent | `--color-text-primary` | `--color-border` | Accent border + text |

| Size | Padding | Font | Height |
|------|---------|------|--------|
| `xs` | 4px 10px | 11px | ~28px |
| `sm` | 6px 12px | 12px | ~32px |
| `md` | 8px 16px | 14px | ~38px |
| `lg` | 10px 24px | 15px | ~42px |

**Rules:**
- One primary button per visual region
- Destructive actions use `danger` variant, not a red-styled primary
- Loading state replaces icon with spinner, keeps text
- `disabled` state: 45% opacity, no pointer events
- Active state: `scale(0.97)` with spring easing

### 7.2 Inputs

| Property | Value |
|----------|-------|
| Border | 1px solid `--color-border` |
| Radius | 10px (`rounded-[10px]`) |
| Padding | 10px 14px (vertical 10px, horizontal 14px) |
| Font | 14px, `--color-text-primary` |
| Placeholder | `--color-text-muted` |
| Focus | 2px accent border + 2px accent ring |
| Error | 2px danger border + 2px danger ring |
| Disabled | `--color-surface-hover` background, 50% opacity |

**Rules:**
- Always include a label (or aria-label)
- Error messages appear below the input with `animate-slide-down`
- Hint text appears below when no error
- Labels are `text-sm font-medium`

### 7.3 Select

Same styling as Input with:
- Custom chevron icon (not native)
- `appearance-none`
- Same focus/error/disabled states

### 7.4 Badges

| Variant | Background | Text | Dot Color |
|---------|-----------|------|-----------|
| success | `--color-success-light` | `--color-success-dark` | `--color-success` |
| warning | `--color-warning-light` | `--color-warning-dark` | `--color-warning` |
| danger | `--color-danger-light` | `--color-danger-dark` | `--color-danger` |
| info | `--color-info-light` | `--color-info-dark` | `--color-info` |
| neutral | `--color-surface-hover` | `--color-text-secondary` | `--color-text-muted` |
| primary | `--color-brand-accent-subtle` | `--color-brand-accent` | `--color-brand-accent` |

| Size | Padding | Font |
|------|---------|------|
| `sm` | 2px 6px | 10px |
| `md` | 4px 8px | 12px |

**Rules:**
- Always pill-shaped (`rounded-full`)
- Dot variant adds a 6px colored circle before text
- Use for status indicators only, not decorative labels
- Max 2 words in a badge

### 7.5 Cards

| Property | Value |
|----------|-------|
| Background | `--color-surface` |
| Border | 1px solid `--color-border` |
| Shadow | `shadow-xs` (default), `shadow-sm` (hover) |
| Radius | 12px (`rounded-xl`) |
| Padding | 20px (`p-5`) |

**Rules:**
- Cards are **white surfaces with subtle borders**, not colored containers
- **No gradient backgrounds on cards** — ever
- **No rainbow icon circles** on cards
- Clickable cards: hover lifts 1px + shadow-sm + accent border tint
- Card titles: `text-base font-semibold`
- Card subtitles: `text-sm text-tertiary`

### 7.6 Tables

| Property | Value |
|----------|-------|
| Header | `--color-bg` background, sticky |
| Header text | 12px, uppercase, `--color-text-tertiary`, semibold |
| Cell padding | 14px vertical (comfortable), 10px (compact), 6px (dense) |
| Cell text | 14px, `--color-text-primary` |
| Row divider | 1px `--color-divider` |
| Row hover | `--color-brand-accent-subtle` |
| Selected row | `--color-brand-accent-subtle` + 3px left accent border |
| Zebra | Every other row gets `--color-bg` at 40% opacity |

**Rules:**
- Tables are the **primary data display** in enterprise apps
- Use the DataTable component, never raw HTML tables
- Server-side pagination for 100+ records
- Client-side filtering for <1000 records
- Sticky headers always
- Keyboard navigation (↑/↓ rows, Enter to activate, Space to select)

### 7.7 Modals

| Property | Value |
|----------|-------|
| Overlay | `--color-surface-overlay` + `backdrop-blur(2px)` |
| Container | `--color-surface`, `rounded-2xl`, `shadow-xl` |
| Max width | sm: 448px, md: 512px, lg: 672px, xl: 896px |
| Max height | 85vh |
| Header | Border bottom, padding 28px |
| Body | Padding 24px |
| Footer | Border top, `--color-bg` background, padding 24px |

**Rules:**
- Focus trapped inside modal
- Escape key closes
- Click outside closes
- Previous focus restored on close
- Title is required
- Footer contains action buttons (right-aligned)

### 7.8 Drawers

| Property | Value |
|----------|-------|
| Width | sm: 320px, md: 480px, lg: 640px |
| Side | right (default), left (mobile nav) |
| Overlay | Same as modal |
| Animation | Slide in from side |

### 7.9 Dropdowns

| Property | Value |
|----------|-------|
| Background | `--color-surface-elevated` |
| Border | 1px solid `--color-border` |
| Shadow | `shadow-lg` |
| Radius | 10px |
| Item padding | 8px 12px |
| Item font | 14px |
| Hover | `--color-surface-hover` |
| Divider | 1px `--color-divider` |

### 7.10 Tabs

| Variant | Style |
|---------|-------|
| **underline** | Bottom border, active has accent bottom line |
| **pills** | Contained in `--color-surface-hover` background, active has white bg + shadow |

**Rules:**
- Underline for page-level navigation
- Pills for within-card filtering
- Keyboard: Arrow keys navigate, Home/End jump

### 7.11 Tooltips

| Property | Value |
|----------|-------|
| Background | `--color-brand-navy` |
| Text | White |
| Radius | 6px |
| Padding | 6px 10px |
| Font | 12px |
| Max width | 250px |
| Arrow | 6px triangle |

### 7.12 Pagination

| Property | Value |
|----------|-------|
| Position | Bottom of table, spanning full width |
| Left | "X – Y of Z" with page size selector |
| Right | Page number buttons |
| Active page | Primary button |
| Inactive page | Secondary button |

### 7.13 Page Header

| Property | Value |
|----------|-------|
| Eyebrow | 12px, uppercase, semibold, accent color |
| Title | 22px (`--text-2xl`), bold, primary text |
| Subtitle | 14px, muted text |
| Actions | Right-aligned, flex row |
| Bottom margin | 20px (compact) or 32px (default) |

**Rules:**
- Every page has a PageHeader
- Eyebrow is the section context (e.g., "Academics", "Fees")
- Title is the page name
- Subtitle is a count or brief description

### 7.14 Skeleton Loaders

| Property | Value |
|----------|-------|
| Color | `--color-border-light` |
| Animation | Pulse opacity 0.4 → 0.8, 1.6s |
| Shape | Rectangles matching content shape |
| Border | `rounded-lg` |

**Rules:**
- Every page must have a skeleton state
- Skeletons should approximate the layout of real content
- Never show a blank page while loading
- Never show a spinner where a skeleton would be better

### 7.15 Empty States

| Property | Value |
|----------|-------|
| Icon | 56px circle, `--color-bg` background, `--color-text-tertiary` icon |
| Title | 16px, semibold, primary text |
| Description | 14px, tertiary text, max-width 400px |
| Action | Primary button below |

**Rules:**
- Every list/table page must have an empty state
- Empty state title should be specific ("No students yet" not "No data found")
- Empty state description should explain what to do
- Empty state action should be the primary creation action

### 7.16 Error States

| Property | Value |
|----------|-------|
| Icon | 56px circle, `--color-danger-light` background, danger icon |
| Message | 14px, semibold, danger text |
| Retry | Primary button (danger variant) |

**Rules:**
- Every data-fetching page must have an error state
- Error message should be the API error detail
- Retry button should re-execute the failed request
- Never show "Something went wrong" without the actual error

### 7.17 Toast Notifications

| Property | Value |
|----------|-------|
| Position | Bottom-right |
| Width | 360px |
| Radius | 10px |
| Shadow | `shadow-xl` |
| Duration | 4s (success), 6s (error), 5s (info) |
| Stacking | Stack upward with 8px gap |

| Type | Left border | Icon |
|------|------------|------|
| success | 3px green | Checkmark |
| error | 3px red | X mark |
| info | 3px blue | Info circle |

### 7.18 Confirm Dialogs

**Never use `window.confirm()`.** Always use the `ConfirmDialog` component.

| Property | Value |
|----------|-------|
| Width | 448px |
| Title | 16px, semibold |
| Message | 14px, secondary text |
| Confirm | Primary or danger button |
| Cancel | Outline button |

---

## 8. Layout System

### 8.1 Application Shell

```
┌─────────┬──────────────────────────────────┐
│         │  Header (60px)                    │
│ Sidebar ├──────────────────────────────────┤
│ (256px) │  Main Content                     │
│         │  (scrollable)                     │
│         │                                   │
│         │  Max-width: 1400px, centered      │
│         │  Padding: 24-32px                 │
└─────────┴──────────────────────────────────┘
```

| Property | Value |
|----------|-------|
| Sidebar width | 256px (expanded), 68px (collapsed) |
| Header height | 60px |
| Main content max-width | 1400px |
| Main content padding | 24px (mobile) → 32px (desktop) |
| Sidebar background | `--color-brand-navy` |

### 8.2 Page Layout Patterns

**List Page:**
```
PageHeader
├── Toolbar (filters, actions)
├── DataTable (with filter rail if filterable)
└── Pagination
```

**Detail Page:**
```
PageHeader
├── Info Grid (2-3 columns)
├── Related Data (tabs or sections)
└── Actions
```

**Dashboard Page:**
```
PageHeader
├── KPI Row (4-6 compact metric blocks)
├── Primary Content (table or chart, 2/3 width)
└── Secondary Content (1/3 width sidebar)
```

**Hub Page (section landing):**
```
PageHeader
├── Quick Stats Row (4 compact metrics)
├── Recent Items Table (5-10 rows)
└── Quick Actions (2-3 buttons)
```

### 8.3 Grid System

| Breakpoint | Columns | Gutter | Margin |
|------------|---------|--------|--------|
| Mobile (<640px) | 1 | 16px | 16px |
| Tablet (640-1024px) | 2 | 16px | 24px |
| Desktop (1024-1440px) | 12 | — | 32px |
| Wide (>1440px) | 12 | — | Auto (max 1400px) |

**Common column spans:**
- Full width: `col-span-12`
- 2/3 + 1/3: `col-span-8` + `col-span-4`
- 1/2 + 1/2: `col-span-6` + `col-span-6`
- 1/3 + 1/3 + 1/3: `col-span-4` × 3
- 1/4 × 4: `col-span-3` × 4

---

## 9. Spacing & Density Rules

### 9.1 Information Density

Enterprise UIs are **dense**. Every pixel must carry information.

| Density Level | Cell Padding | Font Size | Usage |
|---------------|-------------|-----------|-------|
| Comfortable | 14px | 14px | Default tables, forms |
| Compact | 10px | 13px | Data-heavy tables |
| Dense | 6px | 12px | Admin overview tables |

### 9.2 Page Density

| Element | Max Height |
|---------|-----------|
| KPI card | 80px |
| Table row | 48px (comfortable) |
| Form field | 40px |
| Button | 38px (md) |
| Header | 60px |
| Sidebar item | 36px |

### 9.3 Whitespace Rules

- **Never** add empty space just to "fill" a page
- **Never** use `py-16` or larger on non-hero sections
- **Never** center content vertically in a full viewport unless it's a login page
- **Always** use the minimum spacing that provides clear visual separation
- **Prefer** tighter layouts that show more data over spacious layouts with less

---

## 10. Motion System

### 10.1 Duration Scale

| Token | Value | Usage |
|-------|-------|-------|
| `--motion-instant` | 75ms | Color changes, opacity |
| `--motion-fast` | 120ms | Hover states, small transitions |
| `--motion-base` | 180ms | Standard transitions |
| `--motion-slow` | 260ms | Page transitions, drawers |
| `--motion-slower` | 380ms | Modal entrance |
| `--motion-slowest` | 500ms | Complex animations (rare) |

### 10.2 Easing Curves

| Token | Value | Usage |
|-------|-------|-------|
| `--ease-standard` | `cubic-bezier(0.4, 0, 0.2, 1)` | Default |
| `--ease-decelerate` | `cubic-bezier(0, 0, 0.2, 1)` | Entering elements |
| `--ease-accelerate` | `cubic-bezier(0.4, 0, 1, 1)` | Exiting elements |
| `--ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Buttons, playful |
| `--ease-spring-gentle` | `cubic-bezier(0.25, 1.3, 0.5, 1)` | Scale animations |

### 10.3 Animation Rules

1. **Duration cap:** No animation longer than 380ms in production UI
2. **Transform only:** Prefer `transform` and `opacity` over layout properties
3. **One direction:** Enter from bottom-right, exit to bottom-right
4. **Stagger max:** 20ms stagger between items, max 300ms total
5. **Reduced motion:** All animations must have `motion-safe:` prefix or respect `prefers-reduced-motion`
6. **No looping:** Except skeleton pulse and notification pulse
7. **No bounce:** Spring easing is subtle (0.34, 1.56), not bouncy

### 10.4 When to Animate

| Animate | Don't Animate |
|---------|---------------|
| Page transitions | Background colors |
| Modal/drawer open/close | Text content |
| List item enter/exit | Layout shifts |
| Hover state changes | Loading spinners (use skeleton) |
| Skeleton shimmer | Progress bars (use percentage text) |
| Button press feedback | Error messages |
| Focus ring appearance | Data updates |

---

## 11. Iconography

### 11.1 Icon System

- **Style:** Outline (stroke-based), 1.5px stroke width
- **Size:** 16px (inline), 20px (nav), 24px (feature)
- **Color:** Inherits from parent (`currentColor`)
- **Library:** Heroicons-style SVG paths (already in use)

### 11.2 Icon Sizes

| Context | Size | Stroke |
|---------|------|--------|
| Inline with text | 16px | 1.5px |
| Button icon | 16px | 2px |
| Nav item | 20px | 1.5px |
| Empty state | 24px | 1.5px |
| Feature icon | 24px | 1.5px |

### 11.3 Icon Rules

- Icons never stand alone without text (except nav items with tooltips)
- Icon color always matches adjacent text color
- Icons in buttons are 16px, aligned center
- No colored icon backgrounds (no `bg-blue-100 p-2 rounded-lg` around icons)
- Icons are decorative, never functional on their own

---

## 12. Navigation Design

### 12.1 Sidebar Sections (Admin)

```
OVERVIEW
├── Command Center
├── Action Center
├── Risk Center
├── Data Quality
├── Work Queue
└── Timeline

PEOPLE
├── Students
├── Teachers
├── Admissions
└── Leave

ACADEMICS
├── Classes
├── Sections
├── Subjects
├── Enrollments
└── Terms

ATTENDANCE
├── Records
├── Daily
└── Intelligence

FINANCE
├── Fee Types
├── Fee Structures
├── Payments
└── School Finance

COMMUNICATIONS
├── Compose
├── Templates
└── Sent

REPORTING
├── Reports Hub
├── Report Cards
├── Report Builder
└── Analytics

SYSTEM
├── Users
├── Audit Logs
├── Approvals
├── Data Migration
├── Operations
└── Notifications
```

### 12.2 Sidebar Rules

- **Sections are role-filtered:** Each role sees only its relevant sections
- **Section labels** are 9px, uppercase, semibold, 30% opacity
- **Active item** has accent left bar (3px) + accent background
- **Hover** has 6% white overlay
- **Icons** are 20px, stroke-based
- **Labels** are 13px, medium weight
- **Collapsed mode:** Icons only, tooltip on hover
- **Sections with >6 items** get a divider after the 6th

---

## 13. Data Display Patterns

### 13.1 KPI Metrics

```
┌──────────────────┐
│ ACTIVE STUDENTS   │  ← 11px, uppercase, tertiary
│ 1,247             │  ← 22px, bold, primary
│ +3.2% this month  │  ← 12px, tertiary (optional trend)
└──────────────────┘
```

**Rules:**
- KPI cards are **compact** — max 80px height
- Label is uppercase, 11px, tertiary
- Value is 22px, bold, primary
- Trend is 12px, colored (green up, red down)
- No icons in KPI cards (the number IS the content)
- No gradients, no colored backgrounds
- Border: 1px solid `--color-border`
- Background: `--color-surface`

### 13.2 Tables

**Rules:**
- Header: uppercase, 12px, semibold, tertiary
- Cells: 14px, primary text
- Numeric cells: right-aligned, tabular-nums
- Date cells: 13px, secondary text
- Status cells: Badge component
- Action cells: Ghost buttons, right-aligned
- Empty rows: show empty state, not blank space

### 13.3 Charts

- Use Recharts with SDMAS color tokens
- No decorative chart elements (no 3D, no excessive gridlines)
- Chart backgrounds: transparent
- Axis text: 12px, tertiary
- Legend: 13px, secondary
- Tooltip: standard tooltip component

### 13.4 Timelines / Activity Feeds

- Each item: icon (left) + content (center) + timestamp (right)
- Icons colored by event type
- Timestamp: 12px, tertiary, relative time
- Max 10 items visible, "View more" link below

---

## 14. Form Patterns

### 14.1 Form Layout

```
Label (14px, medium, primary)
Input (14px, border, 10px radius)
Error/Hint (12px, below input)
```

**Vertical spacing between fields:** 16px
**Label to input spacing:** 6px
**Error to next field spacing:** 16px (error pushes content down)

### 14.2 Form Rules

- Labels are **always visible** (never placeholder-only)
- Required fields: asterisk after label (`First Name *`)
- Inline validation: on blur, not on every keystroke
- Submit button: primary variant, right-aligned in footer
- Cancel button: outline variant, left of submit
- Server errors: displayed as Alert component at top of form
- Loading state: button shows spinner, form fields disabled

### 14.3 Confirmation Patterns

| Action | Confirmation |
|--------|-------------|
| Create | No confirmation (optimistic) |
| Update | No confirmation (optimistic) |
| Deactivate | ConfirmDialog with danger variant |
| Delete | ConfirmDialog with danger variant |
| Bulk delete | ConfirmDialog with count in message |
| Destructive bulk | ConfirmDialog with typed confirmation |

**Never use `window.confirm()`.**

---

## 15. Responsive Behavior

### 15.1 Breakpoints

| Name | Width | Behavior |
|------|-------|----------|
| Mobile | <640px | Single column, stacked layout |
| Tablet | 640-1024px | 2-column grid, collapsible sidebar |
| Desktop | >1024px | Full layout, persistent sidebar |

### 15.2 Responsive Rules

| Element | Mobile | Tablet | Desktop |
|---------|--------|--------|---------|
| Sidebar | Drawer (left) | Drawer | Persistent |
| Header | Hamburger + search icon | Full | Full |
| Tables | Card layout or scroll | Scroll | Full |
| Forms | Full width | 2-column | 2-3 column |
| KPIs | 2-column grid | 3-column | 6-column |
| Charts | Full width | Full width | 2/3 width |
| Modals | Full width, full height | Centered | Centered |
| Page padding | 16px | 24px | 32px |

### 15.3 Mobile Table Strategy

Tables on mobile should:
1. **Hide non-essential columns** (use `hideOnMobile: true`)
2. **Show key columns** (name, status, actions)
3. **Allow horizontal scroll** for remaining columns
4. **Never** render a completely different mobile layout unless the table has >10 columns

---

## 16. Accessibility

### 16.1 Requirements

- **Focus visible:** 2px accent outline, 2px offset
- **Keyboard navigation:** All interactive elements reachable via Tab
- **ARIA labels:** All icon-only buttons must have aria-label
- **Semantic HTML:** `<nav>`, `<main>`, `<header>`, `<table>`, `<form>`
- **Color contrast:** WCAG 2.2 AA (4.5:1 for text, 3:1 for large text)
- **Reduced motion:** All animations respect `prefers-reduced-motion`
- **Screen reader:** Live regions for toasts, loading states announced

### 16.2 Focus Management

- Page load: focus moves to main content
- Modal open: focus moves to modal, trapped inside
- Modal close: focus returns to trigger element
- Route change: focus moves to new page heading
- Error: focus moves to error message

---

## 17. What NOT To Do

### 17.1 Visual Anti-Patterns

| Anti-Pattern | Why |
|-------------|-----|
| Gradient hero sections | Looks like a marketing page, not a tool |
| Rainbow gradient icon circles | "AI dashboard" aesthetic |
| Glassmorphism / backdrop-blur | Consumer app feel |
| Glow effects / colored shadows | Distracting, not enterprise |
| Animated gradient backgrounds | Performance cost, visual noise |
| Floating decorative elements | No functional purpose |
| Large rounded cards (16px+) | Consumer app feel |
| Excessive whitespace | Wastes screen real estate |
| Giant headings (32px+) | Marketing page, not tool |
| Animated page transitions >200ms | Slows interaction |

### 17.2 Component Anti-Patterns

| Anti-Pattern | Why |
|-------------|-----|
| `window.confirm()` | Browser dialog, not enterprise |
| `console.log()` in production | Debug noise |
| Spinner where skeleton would work | Worse perceived performance |
| Empty page while loading | Broken UX |
| "Something went wrong" with no detail | Unhelpful error |
| Cards that are just navigation links | Hub pages should show data |
| Tables without loading states | Confusing |
| Forms without validation | Broken UX |

### 17.3 Code Anti-Patterns

| Anti-Pattern | Why |
|-------------|-----|
| Two animation libraries (animejs + motion) | Bundle bloat |
| `window.location.href` instead of `navigate()` | Full page reload |
| Hardcoded data in components | Not real |
| `any` types everywhere | Type safety |
| Inline styles for layout | Use Tailwind |

---

## 18. Token Reference (CSS Custom Properties)

All tokens are defined in `index.css` and consumed via Tailwind arbitrary values:

```css
/* Usage in Tailwind */
className="bg-[var(--color-surface)]"
className="text-[var(--color-text-primary)]"
className="border-[var(--color-border)]"
className="rounded-[10px]"
className="shadow-[var(--shadow-sm)]"
className="transition-all duration-[var(--motion-fast)]"
```

---

## 19. Implementation Checklist

For every page redesign, verify:

- [ ] PageHeader with eyebrow, title, subtitle
- [ ] Loading state (skeleton, not spinner)
- [ ] Error state (with retry)
- [ ] Empty state (with action)
- [ ] Responsive layout (mobile → desktop)
- [ ] Keyboard navigation
- [ ] ARIA labels on icon buttons
- [ ] Real API data (no mock/fake)
- [ ] ConfirmDialog for destructive actions
- [ ] No gradients on cards or backgrounds
- [ ] Consistent spacing (16px between sections)
- [ ] Consistent typography (14px base)
- [ ] Consistent border radius (10px default)
- [ ] Focus-visible states
- [ ] Reduced motion support
