# SDMAS Desktop App — Complete Redesign Specification

**Product Design · v3 · *"Corridor"***
**Status:** Redesign in full · **Companion:** `docs/DESIGN_SYSTEM_V3.md` (tokens, components, motion, a11y) · **Screens, part 2:** `docs/APP_REDESIGN_V3_SCREENS.md`

> This is a from-scratch redesign of the SDMAS desktop application. The current UI is treated as a feature inventory, not a starting point. Every screen is specified against the v3 design system, built to feel like a native premium desktop application — not a web dashboard.

---

## Part 0 — The native desktop stance

SDMAS is a data-heavy operational tool used for hours a day by people who are not "app people" — administrators, principals, accountants, teachers. The redesign's job: make it feel like a tool *built for this computer*, with the calm authority of a bank, the density of a ledger, and the polish of a first-party OS app.

### 0.1 Seven decisions that define the redesign

| # | Decision | What it replaces |
|---|---|---|
| D1 | **The window is a workspace, not a webpage.** Full-height shell: toolbar, sidebar, canvas, status bar. No page chrome, no giant centered cards. | "Dashboard page" with max-width 1400px floating content |
| D2 | **Master–detail is the default pattern.** Lists and their details live in split views. Nothing navigates away to see details. | List pages → separate detail pages |
| D3 | **Command is the primary navigation.** ⌘K palette, per-screen shortcuts, `/` quick search. The mouse is optional for experts. | Clicking through menus |
| D4 | **Create/edit is a sheet, not a page.** Every form opens as a macOS-style sheet attached to the toolbar or as a panel from context. | Full-page forms |
| D5 | **Inspector, not tab maze.** 360 views (student, teacher, class) are split panes: master list | detail | inspector. | Deep tab hierarchies |
| D6 | **Density is a setting, not a default.** Ledgers default compact; people screens default comfortable. User can override globally. | One-size-fits-all spacing |
| D7 | **Status is a language.** The status bar, toolbar badges, and status chips speak sync/health/attention consistently. | Scattered alerts |

### 0.2 Native patterns we borrow (as patterns, not code)

Sheets (Mac), split views (Finder/Xcode), inspector (macOS), unified toolbar (macOS), command palette (Linear), multi-select contextual actions (Finder), spring-based window interactions (iOS), status bar (Mac apps), focus-follows-keyboard (everything good).

### 0.3 What never appears again

- Centered floating "hero" dashboards with marketing-style greeting copy.
- 8-tile "Quick Navigation" icon grids.
- Page-level modal dialogs for edits (now sheets/panels).
- Separate detail routes for master–detail content (now split views).
- Scattered `rounded-2xl` shadows on everything (now the elevation ladder).

---

## Part 1 — New information architecture

### 1.1 Workspaces

The sidebar organizes the product into **workspaces** (groups), each with a distinct purpose, icon set, and density default.

| Workspace | Contains | Default density |
|---|---|---|
| **Today** | Command center (home), timeline, risk center | Comfortable |
| **People** | Students, teachers, users & roles, admissions | Comfortable |
| **Academics** | Years/terms, classes, sections, subjects, assignments, enrollment, class 360 | Comfortable |
| **Attendance** | Daily, section, student attendance, records, intelligence | Compact |
| **Finance** | Fees, school finance, receipts, reconciliation, receipt lookup | Compact |
| **Insights** | Analytics, reports, report builder, report cards | Comfortable |
| **Operations** | Batch operations, rollover, exports | Compact |
| **Communicate** | Composer, templates, sent, approvals, notifications | Comfortable |
| **Settings** | Profile, appearance, security, audit log | Comfortable |

### 1.2 Old route → new pattern map (abridged)

| Today | Redesign |
|---|---|
| `/dashboard`, `/command-center`, `/risk`, `/timeline` | **Today** workspace; command center becomes the home screen (role-aware); timeline becomes a drawer from the toolbar clock icon; risk becomes a Today sub-view |
| `/students`, `/teachers`, `/users` | **People** workspace; master–detail split views |
| `/students/:id/student-360` | Split view: students list \| student detail \| inspector (360) |
| `/academic/*` | **Academics** workspace, left column navigates years→terms→classes→sections |
| `/attendance/*` | **Attendance** workspace; daily recording is the hero flow |
| `/fees/*`, `/school-finance/*` | **Finance** workspace; ledgers |
| `/analytics`, `/reports/*`, `/report-builder/*`, `/report-cards`, `/risk` | **Insights** workspace |
| `/operations/*` | **Operations** workspace |
| `/communications/*`, `/workflow/*`, `/notifications` | **Communicate** workspace |
| `/parent/*` (portal) | Separate portal shell (simpler chrome, larger type) |
| `/profile`, `/users`, audit | **Settings** workspace |

---

## Part 2 — Shell & global systems

These screens are shared by every other screen. They are specified once and referenced by the catalog.

### S.1 The App Window (shell)

- **Purpose:** The persistent container that makes SDMAS feel like one application, not a set of pages.
- **Layout (desktop ≥1280):** Column 1 = sidebar (256px, collapsible to 68px); Column 2 = content canvas (fluid, min 640px); optional Column 3 = inspector (340px, contextual). Toolbar (56px) spans columns 2–3. Status bar (28px) spans the full window.
- **Visual hierarchy:** Sidebar (navy ink) is the darkest surface; canvas is the lightest; toolbar is frosted blur over the canvas with a hairline bottom edge; status bar is canvas-minus-one with hairlines.
- **Navigation:** Toolbar back/forward (historical within window), sidebar, ⌘K, workspace shortcuts.
- **Animations:** Workspace switch = 260ms crossfade + 8px rise (direction-aware: pushing deeper moves right). Inspector slides in 260ms from right with parallax (inspector 16px / content 8px).
- **Spacing:** Canvas padding 32px (desktop), 24px (tablet); toolbar 56px; gaps on the 8px grid.
- **Component positioning:** Toolbar: [back/forward] [workspace title + term chip] ⋯ [global search] [notification bell] [sync state] [user menu]. Sidebar bottom: user card + collapse. Status bar left: campus + term; right: network/sync, theme, shortcut hint.
- **Empty states:** The shell itself never empties; when a workspace has no content, the canvas shows the workspace's first-run empty state (T.8).
- **Hover:** Toolbar buttons get a 40px ghost-wash hit area; sidebar items brighten text + icon 10%.
- **Loading:** First paint shows a window-shaped skeleton (toolbar bar, sidebar blocks, content grid) — the shell's own ghost.
- **Keyboard shortcuts:** `⌘1..⌘9` switch workspaces · `⌘[` / `⌘]` back/forward · `⌘K` palette · `⌘B` toggle sidebar · `⌘,` settings.
- **Micro-interactions:** Bell settles with a soft spring on new notifications; sync state cycles with a subtle pulse while syncing; window gains a 1px focus ring distinction when the browser window is focused.
- **Transition animations:** Workspace crossfade (260ms, `ease.enter`); sidebar expand/collapse animates width via transform (180ms, `ease.standard`); status bar content fades on change (120ms).

### S.2 Unified Toolbar

- **Purpose:** The app's command surface — search, notification, sync, user — constant across screens.
- **Layout:** 56px tall, `blur.md` (12px) frosted over canvas with hairline bottom. Left cluster: back/forward chevrons, then the current screen title (h4, semibold) + a "context chip" (term/year/campus) that opens a popover.
- **Visual hierarchy:** Title left = place; actions right = power. Primary in-screen action lives in the *screen's* toolbar row, not here (keeps this bar global).
- **Navigation:** Search field center-left (⌘K / ⌘⇧K), bell, sync, avatar menu on the right.
- **Animations:** Title crossfades on screen change (120ms); search field expands from 240px to full-width on focus (spring-gentle).
- **Spacing:** 56px height; internal gaps 8px; right cluster gap 4px; search field height 36px.
- **Component positioning:** Search field is the visual anchor (fixed width 320px at rest). Bell badge (accent dot, 8px) on the bell glyph. User menu = avatar circle (28px) + chevron.
- **Empty states:** n/a (chrome).
- **Hover:** Ghost-wash (40px) on icon buttons; search field border lifts.
- **Loading:** n/a.
- **Keyboard shortcuts:** `⌘⇧K` global search · `⌘K` palette · `⌘⇧M` notifications · `⌘⇧S` sync now.
- **Micro-interactions:** Sync icon rotates 360° during sync; bell does a 2-spring settle when unread count changes; avatar shows an accent ring while a campus switch is in flight.
- **Transition animations:** Frost opacity ramps up 260ms after scroll begins; title swap 120ms crossfade.

### S.3 Sidebar (workspace navigator)

- **Purpose:** Workspace and section navigation; the map of the app.
- **Layout:** 256px (68px collapsed). Logo row (56px) → workspace groups with micro uppercase labels → user card pinned bottom. Active item = accent-tint wash + 3px left rail (grows in 120ms).
- **Visual hierarchy:** Workspaces (icon+label, 13px medium) above sections (11px, indented). Badge counts (accent pill) on Today/approvals/notifications items only.
- **Navigation:** Groups collapse/expand; workspace items navigate; the Today workspace header carries a "New…" quick-create menu.
- **Animations:** Width animates via transform 180ms; group expand chevron rotates; active rail animates height from 0.
- **Spacing:** Group label: 8px below, 4px above, 12px horizontal; items: 36px rows, 8px gap, 10px horizontal padding; badges right-aligned.
- **Component positioning:** Logo top-left; workspace items fill; user card bottom (avatar 32px, name, campus chip, role badge); collapse chevron in the logo row.
- **Empty states:** Workspaces with no items show a single "No sections yet" 11px muted row (rare; e.g. empty admissions).
- **Hover:** Item bg `nav-bg-hover` (white 6%); icon scales 110% with a 120ms spring; chevron brightens.
- **Loading:** While roles/workspaces load, skeleton rows mirror real items (no layout shift).
- **Keyboard shortcuts:** `⌘1..⌘9` workspaces · `↑↓`+`Enter` navigate · `⌘B` collapse.
- **Micro-interactions:** Badge count pops (`badge-pop` 120ms spring) when it changes; collapse animates labels to icons with tooltips (120ms delay).
- **Transition animations:** Section swap crossfade 260ms; collapse 180ms; badge pop 120ms spring.

### S.4 Command Palette

- **Purpose:** The fastest path to anything: screens, records, actions, recent items.
- **Layout:** Centered card 640px, `blur.lg` + `surface.overlay` + elevation.command; search field top (36px), grouped results below (max 6 visible per group), footer hint row (mono keycaps).
- **Visual hierarchy:** Query echoes in the field; groups labeled micro-uppercase; results = icon (16px) + label + right-aligned context (route/description); "Recent" section on empty query.
- **Navigation:** Type = live filter (150ms debounce); `↑↓` move, `Enter` run, `Esc` close, `Tab` jump groups; typeahead highlights the matched substring in accent.
- **Animations:** Card rises 8px + fades in 260ms; results stagger in 24ms each (fade + 2px rise); empty-query recent list fades in after 120ms.
- **Spacing:** Card padding 16px; result rows 36px; group gaps 12px; footer 8px above card bottom edge.
- **Component positioning:** Footer: left "↑↓ navigate · ↵ open · esc close", right workspace hint. Recently-opened items before everything when query is empty.
- **Empty states:** "No results for 'xyz'" + two fallback rows: "Search all records ⌘⇧K" and "Open in…". Never a blank card.
- **Hover:** Result row washes; right-context appears (or brightens).
- **Loading:** If a search source is slow, a 36px shimmer row + spinner row appears; results stream in as they arrive.
- **Keyboard shortcuts:** `⌘K` open · typeahead always on · `⌘1..9` jump to group · `⌘,` settings entry row.
- **Micro-interactions:** Selection row indents 4px; matched substring stays accent while row is hovered; palette keeps last query on accidental close (restores on reopen).
- **Transition animations:** Open 260ms rise+fade; close 120ms fade-out-scale; row changes 60ms.

### S.5 Global Search

- **Purpose:** Record-level search across all entities (students, teachers, classes, receipts, applications…), backend-powered.
- **Layout:** Full-window overlay (dim 45%) with a centered search sheet (720px): query field, category filter chips (All/Students/Teachers/Classes/Fees), grouped results (People / Academic / Finance / Admissions), live keyboard navigation.
- **Visual hierarchy:** Query field dominates; category chips secondary; results grouped by entity with per-result metadata (class, campus, status chip).
- **Navigation:** Results are keyboard-navigable; Enter opens the record in its master–detail view (deep-linking into the split view with the record selected).
- **Animations:** Sheet fades+rises 260ms; chips slide in from left 24ms stagger; result groups fade on query change 120ms.
- **Spacing:** Sheet 720px wide, 16px padding; rows 44px; chips 8px gaps; result groups 16px apart.
- **Component positioning:** Chips under the field; results below; "press ⌘⏎ to open in new window" hint bottom-right (future native windowing).
- **Empty states:** No matches → illustration + "Nothing found for 'x'" + suggestion to try a name or ID; plus "Search across reports" link.
- **Hover:** Result rows wash; status chips stay readable; category chips lift border.
- **Loading:** Skeletons mirror real result shapes (avatar circle + two text lines) while the query debounce resolves; a thin progress hairline under the field for slow backends.
- **Keyboard shortcuts:** `⌘⇧K` open · `↑↓` + `Enter` · `⌘1..4` jump categories · `Esc` close (restores focus).
- **Micro-interactions:** Debounce spinner (12px) in the field while waiting; result count text ("24 results") counts up.
- **Transition animations:** Open 260ms; close 120ms; query swap 120ms crossfade.

### S.6 Notification Center

- **Purpose:** All persistent notifications, approvals, and activity in one place.
- **Layout:** Drawer from the right edge (480px), `blur.lg` header with segmented control (All / Approvals / Mentions), grouped list by date ("Today", "Yesterday", "This week"), item = status glyph + title + context line + relative time + inline action.
- **Visual hierarchy:** Unread items carry an accent dot + tint wash; approval items carry an action row (Approve/Reject) with danger/accent buttons; time is muted mono.
- **Navigation:** From the toolbar bell; drawer keeps focus; deep-links navigate and close the drawer.
- **Animations:** Drawer slides 260ms + parallax (page 8px); unread dot pops on arrival; grouping headers stick with blur.
- **Spacing:** 480px drawer; items 16px padding, 8px gaps; headers 24px above/8px below.
- **Component positioning:** Actions right-aligned in approval items; "Mark all read" ghost button pinned under the segmented control.
- **Empty states:** "You're all caught up" — success-glow dot + subtle illustration + "Enable more event types" settings link.
- **Hover:** Item washes; inline action buttons reveal (always visible on touch); time brightens.
- **Loading:** Skeleton mirrors items (dot + two lines) for 260ms; drawer opens instantly with skeletons inside — never blocks on a spinner.
- **Keyboard shortcuts:** `⌘⇧M` open · `↑↓`+`Enter` open item · `A`/`R` approve/reject on focused approval · `Esc` close.
- **Micro-interactions:** Bell settle on new; unread count animates; approvals fly a check/X draw on the item before removal (240ms, then item collapses).
- **Transition animations:** Slide-in 260ms; item removal collapse 200ms; group reflow stagger 24ms.

### S.7 Status Bar

- **Purpose:** Ambient truth: campus, term, sync health, network, and a hint that shortcuts exist.
- **Layout:** 28px full-width strip under the canvas: left = campus name + term/year chip; right = sync state ("Synced 12:04" / spinning "Syncing…"), theme toggle, "⌘K" hint.
- **Visual hierarchy:** Muted by design (11px, `text.tertiary`); sync state gets a live pulse dot (accent) while syncing; errors flip to danger dot + tooltip.
- **Navigation:** Campus chip opens the campus/org switcher popover; sync opens a small status popover (last sync, pending ops, "Sync now").
- **Animations:** Status text fades on change 120ms; sync dot pulses 2s loop only while syncing; error flashes once.
- **Spacing:** 28px height; left/right padding 12px; gap between items 16px.
- **Component positioning:** Left cluster (campus, term) | spacer | right cluster (sync, theme, hint). Nothing else.
- **Empty states:** n/a.
- **Hover:** Chips get a ghost wash; sync popover trigger shows "last sync 12:04".
- **Loading:** Sync state replaces with shimmer text while first sync resolves.
- **Keyboard shortcuts:** n/a (informational).
- **Micro-interactions:** Clicking campus opens switcher; theme toggle springs (sun→moon morph 260ms).
- **Transition animations:** Fade 120ms on any state change.

### S.8 Sheets, Panels & Popovers (native form containers)

- **Purpose:** Create/edit forms, contextual details, and quick actions without leaving the working surface.
- **Layout:** **Sheets** (create/edit): 560px card sliding down from the toolbar (macOS sheet metaphor), dim behind. **Panels**: right inspector column (340px) for contextual detail. **Popovers**: anchored cards (tooltips, campus switcher, user menu, quick-create).
- **Visual hierarchy:** Sheet = title bar (h4 + close) + form body (4px-gap field grid) + footer (secondary left, primary right). Panel = compact detail + inline actions.
- **Navigation:** Sheets trap focus; Esc cancels; Enter submits primary. Panels are dismissible via ✕; popovers close on outside click.
- **Animations:** Sheet slides down + fades 260ms spring; panel slides in 260ms parallax; popover scales 0.98→1 + fades 160ms.
- **Spacing:** Sheet 560px, padding 24px; fields 8px apart (4px in compact mode); footer 16px above bottom edge; panel 16px padding.
- **Component positioning:** Primary action bottom-right of sheet footer, full-width on short sheets; destructive always ghost-danger, left of primary.
- **Empty states:** Sheets show the field skeleton (3 shimmer rows) while drafts load.
- **Hover:** Footer buttons standard; sheet drag handle (future resizable sheets) brightens.
- **Loading:** Save button shows spinner + "Saving…" without layout shift; sheet body skeleton on draft load.
- **Keyboard shortcuts:** `Esc` cancel · `⌘↵` submit · `Tab`/`⇧Tab` through fields · `⌘↑/↓` prev/next field on some forms.
- **Micro-interactions:** Field validation errors shake the field (400ms) once + focus the first invalid; saved sheets close with a check-draw on the row they affected.
- **Transition animations:** Sheet enter 260ms slide-down+spring; exit 120ms fade; panel enter/exit 260ms.

---

## Part 3 — Screen family templates

Every screen in the catalog (Part 4) is built from one of these templates. The catalog entries specify what *differs* and what *matters* per screen; these templates specify the common anatomy, states, and behavior.

### T.1 Workspace / List screen

- **Anatomy:** Toolbar row (title + context chip + primary action) → filter bar (search field, filter chips, sort, density toggle) → list (virtualized, sticky header, row actions) → footer (count + pagination).
- **States:** Loading = list skeleton (rows mirror real data). Empty = T.8. Error = banner + retry. Selected rows = accent tint. Hover = row wash + revealed actions.
- **Motion:** Rows enter staggered 24ms; filter changes crossfade 120ms; pagination slides rows 160ms.
- **Keyboard:** `/` focuses search · `↑↓`+`Enter` open in detail pane · `Space` multi-select · `E` export · `N` new.

### T.2 Master–Detail split

- **Anatomy:** Left pane = T.1 list (min 320px, resizable). Right pane = detail (title, metadata, sections as vertical stack, primary action pinned under toolbar row). Selection state = accent rail on the selected row.
- **Navigation:** Selecting a row updates the detail pane in place — **no route change**; deep links restore selection. `Esc` returns focus to the list.
- **Motion:** Detail pane content crossfades 160ms on selection change; a subtle 4px rise. Inspector (if present) slides from the right.
- **States:** Loading detail = pane skeleton; missing record = error state with back-to-list action.

### T.3 360 Profile (People)

- **Anatomy:** Three columns: **master list** (people) | **profile** (header card with avatar, identity, status chips, key facts grid; body sections: overview / academics / fees / attendance / activity as accordions) | **inspector** (right, context-sensitive: quick actions, recent activity, contact, documents, notes).
- **Motion:** Column 3 slides in only when a record has depth (e.g., 360 loaded); profile sections expand with height-free transform animation.
- **Shortcuts:** `⌘↑/↓` prev/next person · `⌘P` print · `⌘E` edit profile.

### T.4 Ledger (Finance/Operations)

- **Anatomy:** Filter bar (period, status, campus, search) → dense table (compact density default, tabular numerals, sticky header with blur, sticky action column) → totals footer row (tabbed: sum/avg/count) → pagination.
- **States:** Row status = chip + icon + text (never color alone). Balance columns right-aligned; IDs in mono.
- **Motion:** Cell value changes pulse (fade-through-50%); rows reorder slide 160ms; totals count up 400ms.
- **Shortcuts:** `T` totals toggle · `E` export · `F` filter focus · `⌘F` find-in-page.

### T.5 Form Sheet

- **Anatomy:** Title bar + sectioned field grid (2-col desktop, 1-col narrow) + footer. Fields: label above (micro uppercase optional), hint, inline validation.
- **Motion:** Fields reveal section-by-section 24ms stagger on open; invalid field shake 400ms.
- **States:** Saving = footer spinner; success = sheet closes + toast; duplicate detection = inline error on the field with suggestion row.

### T.6 Builder Canvas (Report Builder / Report Cards)

- **Anatomy:** Full-bleed canvas (no card), left **palette/fields** rail (drag sources), center **canvas** (drop targets, live preview), right **inspector** (property panel). Snap grid 8px, selection = accent ring.
- **Motion:** Drag ghost follows cursor with spring; drop animates element into place 200ms; property changes live-render with 120ms transition.
- **Shortcuts:** `⌘Z/⇧⌘Z` undo/redo · `⌘D` duplicate · `⌫` delete · arrows nudge · `⌘↵` run preview.

### T.7 Portal (Parent/Student)

- **Anatomy:** Simplified shell: slim top bar (back, title, bell) + single column content (max 900px) + bottom action bar. Larger type (body 16px), generous touch targets (44px).
- **Motion:** Content slides between portal sections 260ms; pull-to-refresh on mobile.
- **States:** Every financial/attendance figure renders as a friendly card, not a raw ledger.

### T.8 Empty / First-run states

- **Anatomy:** Full-pane: duotone illustration (original line art) → h3 title → one-line body → single primary action → optional 3-step "how it works" row.
- **Motion:** Elements rise in 24ms stagger; illustration draws once (200ms per element).
- **Rules:** Never "No data." Always: what this screen is, why it's empty, and the exact next step. First-run adds a dismissible onboarding card above.

---

## Part 4 — Screen catalog (1 of 2)

> Screens F–M continue in `docs/APP_REDESIGN_V3_SCREENS.md`. Field keys: **P** purpose · **L** layout · **VH** visual hierarchy · **N** navigation · **A** animations · **S** spacing · **CP** component positioning · **E** empty state · **H** hover · **LD** loading · **K** keyboard · **MI** micro-interactions · **T** transitions.

---

### A. Entry

#### A.1 Login
- **P:** Identity gate for all roles; sets the tone of the product in one screen.
- **L:** Two-pane window (desktop): left = Dawn gradient canvas (`brand.950→600`) with the product line "A school run at the quality of a bank" + ambient animated grid (10% opacity); right = centered form column (420px): logo squircle, "Sign in to SDMAS", username, password, "Sign in" primary, "Forgot password?" ghost. Campus chip only after auth (never pre-auth).
- **VH:** Form column dominates; brand canvas is quiet theater. One primary action. Error banner sits above the field.
- **N:** Enter submits; `Tab` field order; forgot-password → sheet from the right; no other navigation.
- **A:** Canvas grid drifts slowly (60s loop, 10% opacity — ambient only); form enters with 24ms stagger; logo draws once.
- **S:** Form 420px, padding 32px; field gap 8px; section gap 16px; canvas column full-bleed.
- **CP:** Logo → greeting → fields → primary → secondary. Error banner directly above the form, not in the footer.
- **E:** n/a (auth failure = error state): banner + field shake + "Reset password" escape.
- **H:** Primary lifts elevation + glow; ghost brightens; password reveal icon brightens.
- **LD:** Sign-in button → spinner + "Signing in…"; no layout shift; on success the whole window crossfades to the shell 300ms.
- **K:** `Enter` submit · `Tab`/`⇧Tab` fields · `Esc` clears focus · `⌘L` focus username.
- **MI:** Caps-lock warning glyph appears in the password field; failed login shakes the submit button once (400ms) and rings the field pair; the form tilts 0.5° on very wrong credentials (dismissive, then resets).
- **T:** Entry: form rise 8px stagger 260ms; exit to shell: 300ms fade + 16px rise with a hairline "window open" feel.

#### A.2 Workspace / Campus picker (post-login, multi-campus only)
- **P:** Choose the campus (tenant) to work in; the tenancy boundary made visible.
- **L:** Centered sheet (560px): list of campuses as cards (squircle glyph, name, role chips, last-visited badge), "Create campus" ghost at the bottom for platform admins.
- **VH:** Current campus card gets an accent ring + check; others flat.
- **N:** Cards are the list; Enter picks; Esc goes to profile.
- **A:** Cards rise 24ms stagger; ring draws 200ms.
- **S:** 560px sheet, 16px padding, card rows 64px, 8px gaps.
- **CP:** Picked card first (pinned), others alphabetical; footer = create + manage.
- **E:** No campuses → platform setup empty state (T.8) with "Create your first campus".
- **H:** Card lifts 4px + border brightens; role chips stay muted.
- **LD:** Card skeletons ×3 with shimmer.
- **K:** `↑↓`+`Enter` · `⌘N` create.
- **MI:** Campus switch plays a full-shell 260ms crossfade with the status bar updating "Campus: X".
- **T:** Sheet 260ms rise+fade; selection → shell 300ms crossfade.

---

### B. Today (workspace)

#### B.1 Command Center (home, role-aware)
- **P:** The morning screen: what needs attention today, one glance, zero clicks.
- **L:** Toolbar row (title "Today" + term chip + primary "Record attendance"). Body, 12-col grid: row 1 = 4 KPI tiles (attendance %, fees collected, dues, applications pending — each: label, animated count, sparkline, delta chip); row 2 = left 8-col "Attention queue" (severity-sorted items: low attendance, unpaid fees, expiring approvals — each opens its workspace with the record pre-selected), right 4-col "Today's rhythm" (classes today, pending approvals, scheduled payments); row 3 = activity strip (last 10 timeline events, compact).
- **VH:** KPI numbers (display, bold, tabular) are the loudest; attention items carry severity dots (danger/warning/info); everything else quiet.
- **N:** Every tile/queue item deep-links into its workspace split view. Workspace icons switch via sidebar. No internal tabs — the grid *is* the navigation.
- **A:** KPI numbers count up 500ms; tiles stagger 24ms; attention queue re-sorts with a 160ms slide when data refreshes (auto-refresh 5min, silent).
- **S:** Canvas 32px padding; grid gap 24px; tile padding 16px; queue item rows 48px.
- **CP:** Primary action pinned top-right of the toolbar row; severity order danger→info; live pulse dot on the attendance KPI while today's recording is in progress.
- **E:** First-run: T.8 "Your school hasn't recorded anything yet" + three steps (Add students → Set fee structure → Record attendance) with per-step deep links. Empty-but-onboarded: KPI tiles show dashes, queue shows "All clear" success card.
- **H:** Tiles lift 2px + border brightens; queue items wash + chevron slides 4px; KPI sparklines reveal on hover.
- **LD:** Window-shaped skeleton: 4 KPI tiles (with number-shaped shimmer), queue rows ×5, activity rows ×6 — mirrors the real grid.
- **K:** `N` record attendance · `R` risk center · `T` timeline · `⌘↵` open first queue item · `1-4` jump KPI tiles' workspaces.
- **MI:** Live attendance dot pulses while recording is in progress; delta chips pop on change; queue items flash once on arrival of new severity (with sound off).
- **T:** Tiles stagger in 24ms; KPI counts 500ms; queue reflow 160ms; refresh crossfade 120ms (never a full-screen spinner).

#### B.2 Timeline
- **P:** The operational activity feed — who did what, when, across the campus.
- **L:** Drawer or full workspace? Full workspace: toolbar row (filter chips: entity type / actor / date range) + two-column feed (left: date-stamped event cards with actor avatar, action verb, entity link, time; right 300px: "Today by the numbers" + people who acted most). Enter via toolbar clock icon or Today.
- **VH:** Events grouped by day; actor emphasized, verb muted, entity accented. Live badge when new events arrive.
- **N:** Events deep-link; "New events" floating pill at top of the feed when live updates arrive (click to reveal).
- **A:** New events drop in with 24ms stagger + accent flash; filter changes crossfade 120ms; live pill bounces once.
- **S:** Feed max-width 720px center-left; card padding 16px; date headers sticky with blur; gap 8px.
- **CP:** Filters above feed; right rail fixed 300px; live pill floats above the first unread event.
- **E:** Empty day → "Quiet day" with success glow + "What counts as an event" explainer.
- **H:** Event cards wash; deep-links accent; avatar rings on hover.
- **LD:** Feed skeleton (avatar circles + text lines ×8) mirrors events.
- **K:** `J/K` next/prev event · `F` filter focus · `L` live toggle.
- **MI:** New-event pill counts up; actor avatars stack with overlap rings.
- **T:** Stagger 24ms; crossfade 120ms; live reveal 200ms slide-down.

#### B.3 Risk Center
- **P:** Deterministic risk findings (attendance, finance, academic rules) — the campus's "check engine light."
- **L:** Toolbar row (severity filter chips: critical/warning/info; rule filter) + findings table (T.4 ledger style: finding, rule, affected entity, severity, first seen, status) + detail panel (right, 380px): rule explanation, affected records, "Resolve" action. Critical findings pin to top with danger rail.
- **VH:** Severity drives everything: critical = danger rail + dot; then warning; then info. Resolved = muted with strikethrough-free check.
- **N:** Findings open records in their workspaces; resolve opens a confirm sheet; "ignore" moves to a muted list.
- **A:** New critical finding animates the toolbar bell + flashes the row 2×; table resort slides 160ms; detail panel slides 260ms.
- **S:** Ledger density (36px rows); detail panel 380px; filter chips 8px gaps.
- **CP:** Severity chips left; "Export findings" ghost right; resolve button in the detail panel footer (danger or accent depending on rule).
- **E:** Zero findings → full-pane success state: "No findings — every rule is passing" with success glow + last-audit time + "Re-run audit" ghost.
- **H:** Rows wash; critical rows show a subtle red glow edge on hover; detail links accent.
- **LD:** Table skeleton; if rules are still computing, a thin progress hairline under the toolbar row.
- **K:** `F` filter · `↵` open finding · `X` resolve focused · `E` export.
- **MI:** Severity counts in chips count up; resolve flies a check-draw on the row; "re-run audit" spins then pulses success.
- **T:** Table slide 160ms; panel 260ms; success state 300ms fade-in.

---

### C. People (workspace)

#### C.1 Students (master–detail split)
- **P:** Find, view, and manage any student without leaving context.
- **L:** T.2 split: left list (search, filters: class/section/status, columns name+ID+class+attendance chip), right detail pane (header card: avatar, name, ID mono, status chips, class/section; sections accordion: Overview, Academics, Fees, Attendance, Documents, Notes). Optional inspector column for 360 depth.
- **VH:** List = scan; detail = read; the selected row's accent rail links them.
- **N:** Selection changes the pane in place; row Enter opens detail pane; `⌘E` opens edit sheet; `⌘O` opens 360 inspector.
- **A:** Pane crossfade 160ms + 4px rise; inspector slides 260ms; avatar loads with a soft scale-in.
- **S:** List min 320px/resizable; detail padding 24px; header card 16px; accordion gaps 8px.
- **CP:** Primary "Add student" in the toolbar row; row actions (edit/360/export) revealed on hover.
- **E:** No students → T.8: "Welcome to your first class" + Add student + Batch enroll + Import.
- **H:** Row wash + ID brightens; avatar ring; accordion headers brighten; reveal-actions slide in.
- **LD:** List skeleton + detail pane skeleton (avatar circle + lines) simultaneously — the split renders as one ghost.
- **K:** `/` search · `↑↓`+`Enter` · `Space` select · `N` add · `⌘E` edit · `⌘O` 360 · `E` export.
- **MI:** Attendance chip in the list pulses on today's live updates; avatar initials shimmer once on first load.
- **T:** Pane 160ms; inspector 260ms; selection rail draws 120ms.

#### C.2 Student Detail (profile pane — part of C.1, expanded alone on narrow windows)
- **P:** Full record view for one student.
- **L:** Header card (avatar 64px, name, ID mono, status chips, quick actions) → metadata grid (contact, guardians, transport) → section accordions (Academics: class/section/roll; Fees: due/paid/outstanding with mini-bars; Attendance: month grid heatmap; Documents; Notes; Timeline of activity).
- **VH:** Identity at top; money and attendance get the loudest numeric treatment.
- **N:** Accordions keep everything one pane; each section's "Open in…" deep-links to the workspace tool.
- **A:** Accordions expand with height-transform 200ms; heatmap cells fill left→right 160ms stagger.
- **S:** 24px padding; metadata 2-col grid, 8px gaps; sections 24px apart.
- **CP:** Edit (⌘E) top-right of header; primary financial action ("Record payment") in the Fees section header, not global.
- **E:** A section with no data collapses to a quiet "Not recorded yet" row with a link.
- **H:** Accordion headers wash; heatmap cells brighten; quick-action icons lift.
- **LD:** Pane skeleton mirrors header + accordion titles.
- **K:** `⌘E` edit · `⌘P` print profile · `⌘F` find · `Space` open first accordion.
- **MI:** Heatmap cells pop on hover with the date tooltip; fee bars count up.
- **T:** Accordion 200ms; pane 160ms.

#### C.3 Student 360 (inspector)
- **P:** The longitudinal story: attendance trend, fee health, academic pulse, activity — the "why" behind the record.
- **L:** T.3 inspector column (340px) + optionally full-width mode: four mini-panels stacked: Academic (grades/score bars), Attendance (6-month trend sparkline + status breakdown), Finance (dues vs paid area chart + status), Activity (compact feed). Each panel's header has "Open in Insights".
- **VH:** Trend lines are the loudest; current status chips at top; everything reads top-to-bottom.
- **N:** Panels deep-link to analytics; the inspector follows the selected student as you arrow through the list.
- **A:** Panels reveal 24ms stagger; charts draw 500ms; status chips pop on change.
- **S:** 340px; panels 16px padding, 12px gaps.
- **CP:** Status header fixed; charts stacked; footer "Export 360 PDF".
- **E:** No data yet → each panel shows its own quiet empty line, not a wall of "—".
- **H:** Chart hover crosshair + series emphasis; panels lift 2px.
- **LD:** Panel skeletons mirror chart shapes.
- **K:** `⌘↑/↓` prev/next student · `⌘P` export · `1-4` jump panels.
- **MI:** Live attendance today highlights the current day on the heatmap with a pulse dot.
- **T:** Panels 24ms stagger; charts 500ms; inspector 260ms.

#### C.4 Teachers (master–detail split)
- **P:** Find and manage teaching staff.
- **L:** T.2 split: list (search, filter by subject/status, columns name, employee ID mono, subjects, load chip) + detail (header card + accordions: Assignments, Classes, Subjects, Leave, Documents). 360 inspector follows selection.
- **VH/N/A/S/CP/E/H/LD/K/MI/T:** Mirror C.1/C.2/C.3 with teacher-specific accents: load chip (classes/week) color-coded amber above threshold; "Assign class" primary; empty state = "Invite your first teacher". Shortcut deltas: `⌘T` timetable; `⌘A` assign class.

#### C.5 Users & Roles (admin)
- **P:** Account lifecycle and permission administration.
- **L:** T.4 ledger: users table (name, username, role chips, campus, status, last active) + detail panel (right): role checkboxes (permission matrix), reset password, deactivate. Filter: role / status / campus.
- **VH:** Role chips use the role color language; inactive rows muted; platform admins carry a badge.
- **N:** Select row → panel; "Invite user" primary in toolbar row (sheet); permission matrix edits inside the panel.
- **A:** Role change flies the permission diff (added/removed rows pulse); row reflow 160ms.
- **S:** 36px rows; panel 380px.
- **CP:** Danger zone (deactivate/delete) bottom of the panel, ghost-danger, confirm sheet required.
- **E:** No users → "Invite your first teammate".
- **H:** Row wash; permission rows brighten on hover; role chips lift.
- **LD:** Table skeleton + panel skeleton.
- **K:** `N` invite · `⌘E` edit · `⌫` with confirm = deactivate · `F` filter.
- **MI:** Last-active relative time ticks down subtly; deactivation greys the row 200ms.
- **T:** Row reflow 160ms; panel 260ms.

---

### D. Academics (workspace)

#### D.1 Academic Calendar (years & terms)
- **P:** The skeleton of the school year: years, terms, session dates.
- **L:** Workspace left rail: year tree (2025-26 → Term 1, Term 2) as a collapsible list; main pane: term timeline card (start/end dates, duration bar, status chip) + "configure" sheet from toolbar row.
- **VH:** Current term carries accent ring + "active" chip; past terms muted; future dashed.
- **N:** Year node expands; selecting a term drives the Academics workspace context chip (status bar + toolbar).
- **A:** Tree expand 160ms; timeline bar grows 300ms on load.
- **S:** Tree 240px; timeline card 24px padding; gaps 16px.
- **CP:** "New academic year" primary; "Roll over year" ghost (deep-links Operations rollover).
- **E:** No years → T.8: "Set up your first academic year" 2-step (Create year → Add terms).
- **H:** Year nodes wash; term cards lift; status chips stay.
- **LD:** Tree skeleton + card skeleton.
- **K:** `N` new year · `→/←` expand/collapse · `⌘↵` open active term.
- **MI:** Active-term chip pulses softly during term; date countdown ("42 days left") in the chip.
- **T:** Tree 160ms; card 200ms.

#### D.2 Classes
- **P:** Manage class groups and their composition.
- **L:** T.1 list (classes as cards or table: name, section, teacher, size, capacity bar) + expand → class detail (T.2) with tabs: Overview / Roster / Schedule / Assignments.
- **VH:** Capacity bars color-code (green <80%, amber 80–95%, red >95%).
- **N:** Selecting a class opens detail pane; "Open Class 360" promotes to three-pane.
- **A:** Capacity bars fill 400ms; roster rows stagger 24ms.
- **S:** Cards 16px padding; roster 40px rows.
- **CP:** "New class" primary; per-class overflow menu (edit/roster/export).
- **E:** Empty → T.8 "Create your first class" with class-from-template option.
- **H:** Card lift; capacity bar tooltip on hover; roster rows wash.
- **LD:** Card grid skeleton mirrors card count.
- **K:** `N` new · `↑↓`+`↵` open · `⌘R` roster.
- **MI:** Enrollments update the capacity bar with a 400ms fill animation.
- **T:** Cards 24ms stagger; pane 160ms.

#### D.3 Class 360
- **P:** One class, everything: composition, attendance health, performance, teacher load.
- **L:** T.3: master list (classes) | profile (class header, roster heatmap by attendance, subject score bars, teacher card) | inspector (schedule, notes, risk flags).
- **VH:** Attendance heatmap is the centerpiece; subject bars secondary.
- **N:** Roster names deep-link to Students; teacher card to Teachers.
- **A:** Heatmap fills per-day 24ms stagger; bars 400ms.
- **S:** 340px inspector; 16px paddings.
- **CP:** "Record attendance" primary in profile header; "Export roster" ghost.
- **E:** No roster → T.8 "Add students to this class".
- **H:** Heatmap cells brighten; roster rows wash.
- **LD:** Panel skeletons mirror chart shapes.
- **K:** `⌘R` record · `⌘E` export · `⌘S` schedule.
- **MI:** Today's column pulses if not yet recorded.
- **T:** Panels 24ms stagger; charts 500ms.

#### D.4 Sections, D.5 Subjects, D.6 Teacher Assignments, D.7 Enrollment
- **P:** Structural building blocks: section management, subject catalog, teacher→class/subject mapping, enrollment (add/remove students from classes).
- **L:** D.4/D.5 = T.1 lists with side detail (Sections: name, class, strength, class teacher; Subjects: name, code, classes count, teacher count). D.6 = assignment matrix (teachers × classes/subjects with load chips; drag to assign). D.7 = enrollment ledger (student, from class, to class, date, status) with bulk enrollment sheet.
- **VH:** Matrices emphasize the diagonal (assigned cells accent-tinted); ledgers right-align numerals.
- **N:** All four are reached from the Academics workspace rail; each has its own T.1 toolbar row.
- **A:** Matrix cells fade in 120ms stagger; drag ghost springs.
- **S:** 8px matrix cell gaps; ledger 36px rows.
- **CP:** "Assign" primary in D.6; "Enroll students" primary in D.7 (sheet with search-multi-select).
- **E:** D.4/D.5/D.6 empty = T.8 "Structure your school"; D.7 empty = "Enroll your first student".
- **H:** Matrix cells wash; assignment cells show a check-draw on drop; ledger rows standard.
- **LD:** Matrix/ledger skeletons mirror shapes.
- **K:** D.6 `⌘A` assign · D.7 `N` enroll · all: `F` filter.
- **MI:** Drag-assign drops with a 200ms settle + row pulse; enrollment changes update Class 360 capacity bars live.
- **T:** 120ms fades; 200ms drops.

---

### E. Attendance (workspace)

#### E.1 Record Attendance (daily — the hero flow)
- **P:** Mark a whole class present/absent in under 30 seconds, twice a day.
- **L:** Toolbar row (date stepper ← today →, class/section selector, period chip, status bar shows class size + progress) → roster grid: student rows (avatar, name, ID) each with a 4-option segmented control (Present / Absent / Late / Excused) — default Present, click cycles or drops a menu; bottom bar: "Save & next class" primary + summary counts (P/A/L/E chips counting live).
- **VH:** The roster is the only thing; counts bottom-right are live feedback; unmarked rows carry a subtle "not saved" dot.
- **N:** Date stepper walks backward/forward; class selector jumps; Save advances to next scheduled class (suggestion row under the button).
- **A:** Rows stagger in 24ms; segmented control fills with 160ms; save button check-draw 300ms; counts count up.
- **S:** Rows 44px; segmented 32px; grid gap 4px; bottom bar 64px.
- **CP:** Segmented controls right-aligned per row; summary left of save; "mark all present" ghost at the toolbar row.
- **E:** No classes today → "No classes scheduled" + schedule link; no roster → link to enrollment.
- **H:** Row wash; segmented options hover-lift; avatar ring on focus.
- **LD:** Roster skeleton mirrors student rows; the segmented controls render as placeholders.
- **K:** `→/←` move between students · `1/2/3/4` set status · `Space` toggle Present/Absent · `⌘↵` save & next · `⌘Z` undo last mark.
- **MI:** Undo toast after each save ("Saved — 32 present, 2 absent. ⌘Z to undo"); unmarked dot turns to check; a stray double-click on a row opens the record detail.
- **T:** Rows 24ms; save 300ms check; next-class suggestion slides up 200ms.

#### E.2 Section & Student Attendance
- **P:** Attendance from a section's perspective (whole section, day view) and one student's record (detail).
- **L:** E.2-section: T.4 table (students × date columns with status dots, compact); E.2-student: T.2 detail (month heatmap, status breakdown, exceptions list).
- **VH:** Dots encode status (P green / A red / L amber / E blue) with text tooltips; week columns shaded.
- **N:** Date range selector drives columns; student rows open the student detail pane.
- **A:** Dots pop on edit; heatmap fills 24ms stagger.
- **S:** 32px rows; dot cells centered; heatmap cells 14px.
- **CP:** "Edit day" sheet from toolbar; "Export" ghost.
- **E:** No records → T.8 "Start with today's attendance".
- **H:** Dots scale 120% on hover; column headers brighten.
- **LD:** Dot-grid skeleton mirrors the matrix.
- **K:** `←→` move days · `Space` toggle focused cell · `⌘E` edit day.
- **MI:** Cell edits flash the dot; bulk-fill a column by dragging (mouse) with a live preview tint.
- **T:** Dots 120ms; grid crossfade 120ms.

#### E.3 Attendance Records (ledger)
- **P:** Searchable, filterable history — audit-grade.
- **L:** T.4 ledger: date, class/section, student, status chip, recorded by, time; filters: date range, class, status, recorded-by; export + drill-down to record detail sheet.
- **VH:** Status chips lead; date column in mono.
- **N:** Row → record detail sheet (who/when, status history for that student-day).
- **A:** Filter crossfade 120ms; export progress hairline.
- **S:** 36px rows; sticky header.
- **CP:** Export right; filters left; record detail as sheet (T.5).
- **E:** No records in range → quiet empty + "adjust filters" ghost.
- **H:** Row wash; status chip micro-lift.
- **LD:** Ledger skeleton.
- **K:** `F` filter · `E` export · `↵` open record.
- **MI:** Export button shows row count ("Export 1,240 rows").
- **T:** 120ms crossfades.

#### E.4 Attendance Intelligence
- **P:** Find the patterns before they become problems: chronic absence, period-level trends, thresholds.
- **L:** Split: left rail = views (Overview / Period analysis / Corrections / Thresholds); main = each view's content. Overview: trend line (6 months) + status breakdown + "students below threshold" list. Period analysis: period × class heatmap. Corrections: discrepancy ledger (auto-detected anomalies) with "confirm/correct" actions. Thresholds: rule list (risk engine config) with toggle + limit steppers.
- **VH:** Anomalies are danger-flagged; threshold breaches call attention via the bell.
- **N:** Rail switches views; anomalies deep-link to student detail.
- **A:** Charts draw 500ms; correction approval flies a check.
- **S:** Rail 200px; charts 16px padding.
- **CP:** "Re-run analysis" ghost; threshold edits save inline with a 120ms flash.
- **E:** No anomalies → success glow "No patterns flagged".
- **H:** Chart series emphasis; anomaly rows wash.
- **LD:** Chart skeletons; analysis progress hairline.
- **K:** `1-4` views · `⌘R` re-run · `↵` open anomaly.
- **MI:** Threshold breach animates a one-time bell pulse; corrections count up.
- **T:** Views crossfade 160ms; charts 500ms.
