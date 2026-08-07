# SDMAS Desktop App — Screen Catalog (2 of 2)

**Part 2 of the redesign specification.** Part 1 (`docs/APP_REDESIGN_V3.md`) defines the stance, architecture, shell (S.1–S.8), and family templates (T.1–T.8). This catalog continues from screen **F. Admissions** through the portals. Field keys: **P** purpose · **L** layout · **VH** visual hierarchy · **N** navigation · **A** animations · **S** spacing · **CP** component positioning · **E** empty state · **H** hover · **LD** loading · **K** keyboard · **MI** micro-interactions · **T** transitions.

---

## F. Admissions (People workspace)

### F.1 Applications (list)
- **P:** Track the admission pipeline from inquiry to enrollment.
- **L:** T.4-style pipeline board: three columns (New / Reviewed / Enrolled) as kanban cards (applicant avatar, name, program, applied date, priority chip) + list view toggle. Filters: program, status, date.
- **VH:** Priority chips (accent=high) and status columns create the pipeline at a glance; card count per column is the header.
- **N:** Cards drag between columns (with status change confirm for Enrolled); clicking opens the application detail pane.
- **A:** Card drag ghost springs; column counts count up; moving a card reflows the column 200ms.
- **S:** Kanban gap 16px; cards 12px padding, 8px gaps; columns min 280px.
- **CP:** "New inquiry" primary in toolbar row; per-card overflow (view, reassign, archive).
- **E:** No applications → T.8 "Start your first admission cycle" + "New inquiry" + "Import applicants".
- **H:** Cards lift 2px + border brighten; priority chip stays; drop targets glow when a card is dragged over them.
- **LD:** Column skeletons mirror card shapes.
- **K:** `1-3` jump columns · `N` new inquiry · `↵` open · `⌘⇧→` move to next column.
- **MI:** Moving to Enrolled triggers an enrollment sheet suggestion; archived cards fade and collapse 200ms.
- **T:** Reflow 200ms; open 160ms; count 200ms.

### F.2 Application Detail
- **P:** The full applicant dossier and decision record.
- **L:** T.2 detail pane: header card (avatar, name, program, status chip, priority) → metadata grid (contact, guardian, school, documents) → timeline (inquiry → review → decision steps with actor+time) → decision bar (Approve / Reject / Hold) pinned under the toolbar row.
- **VH:** Decision bar is the loudest element (danger on Reject, accent on Approve); timeline quiet.
- **N:** Approve opens the enrollment sheet (student record creation, class assignment); Reject requires a reason (sheet, 1 required field).
- **A:** Timeline steps draw 24ms stagger; decision bar slides in 200ms once the dossier loads.
- **S:** 24px padding; decision bar 64px; timeline rows 40px.
- **CP:** Approve right, Reject danger-left of it, Hold ghost; document list opens the documents viewer.
- **E:** No documents → "No documents attached" with upload link (documents validation per v3).
- **H:** Timeline rows wash; decision buttons lift; document rows brighten.
- **LD:** Pane skeleton mirrors header + timeline.
- **K:** `⌘↵` approve · `⌘⌫` reject (with confirm) · `⌘D` documents · `⌘T` timeline.
- **MI:** Approve flies a check-draw and the card slides to Enrolled in the background; Reject red-flashes the card.
- **T:** Pane 160ms; timeline 24ms stagger; decision 200ms.

### F.3 New Inquiry (sheet)
- **P:** Fast capture of a walk-in inquiry.
- **L:** T.5 sheet (560px): applicant name, program select, guardian contact, source, notes; footer: "Save inquiry" primary + "Save & admit" secondary.
- **VH:** Three fields + notes; everything else chrome.
- **N:** Sheet from toolbar "New inquiry"; Esc cancels; Save lands on F.1 with the new card highlighted.
- **A:** Sheet 260ms; fields 24ms stagger; card highlight pulse 600ms.
- **S:** 560px; fields 8px gaps.
- **CP:** Notes textarea full-width last; footer actions right.
- **E:** n/a.
- **H:** Standard input hover.
- **LD:** Field skeletons while draft loads (rare).
- **K:** `⌘↵` save · `Esc` cancel.
- **MI:** Duplicate-name detection suggests "Existing applicant found" merge row.
- **T:** Sheet 260ms; highlight 600ms pulse.

---

## G. Finance (workspace)

### G.1 Fee Dashboard
- **P:** The money posture of the campus at a glance: collected, outstanding, overdue, pipeline.
- **L:** Row 1: four KPI tiles (Collected, Outstanding, Overdue, Collection rate % — each with sparkline + delta). Row 2: 8-col collection trend area chart (period stepper) + 4-col status breakdown (donut). Row 3: top-10 outstanding students table (T.4 compact) with "Record payment" per row.
- **VH:** Currency numerals (display, tabular, right-aligned) dominate; overdue tile carries danger treatment; donut status colors match v3 status palette.
- **N:** KPI tiles deep-link to the relevant ledger (G.2/G.3); table rows open the student fee pane.
- **A:** Counts count up 500ms; chart draws 500ms; top-10 rows stagger 24ms.
- **S:** Grid gap 24px; tiles 16px padding; chart 16px padding.
- **CP:** "Record payment" primary in toolbar row (opens receipt sheet); period stepper beside the chart header.
- **E:** No financial data → T.8 "Set up your fee structure" 2-step (Fee types → Structures) + "Record first payment".
- **H:** Tiles lift; chart series emphasize; table rows wash.
- **LD:** Window skeleton: 4 tiles + chart block + 10 rows.
- **K:** `N` record payment · `1-4` jump tiles · `F` filter.
- **MI:** Overdue total ticks red pulse when it increases; payment recorded elsewhere updates the tiles with a count-up + glow.
- **T:** Tiles 24ms; counts 500ms; chart 500ms.

### G.2 Fee Types & Structures
- **P:** Define the catalog of fees and their term-level pricing.
- **L:** Split: left list (fee types: name, code mono, status, #structures), right detail (structure grid: term × amount with inline edit, due dates, waivers). "New fee type" primary.
- **VH:** Amount columns right-aligned; active types bold, archived muted.
- **N:** Type selection drives the structure pane; editing is inline (commit 200ms flash).
- **A:** Structure cells fade on save; inline steppers spring.
- **S:** 36px ledger rows; inline cells 8px gaps.
- **CP:** Add structure row ghost under grid; archive in type overflow.
- **E:** No types → T.8 "Create your first fee type" (name, code, category).
- **H:** Cells hover-wash; amount cells show a pencil ghost.
- **LD:** Split skeletons.
- **K:** `N` new · `↵` open · `⌘S` save inline · `A` add row.
- **MI:** Inline save shows a brief green check in the cell; archived types grey out with a 200ms fade.
- **T:** Save flash 200ms; split crossfade 160ms.

### G.3 Fee Dues, Payments & Student Fees (ledgers)
- **P:** The operational ledgers: who owes what (dues), what was paid (payments), and one student's full fee story.
- **L:** Three T.4 ledgers under one Finance rail: **Dues** (student, structure, term, amount, paid, balance, due date, status chip), **Payments** (receipt # mono, student, date, amount, method, recorded by, status), **Student Fees** (T.2 split — select student → balance card + payment history + structure breakdown).
- **VH:** Balances right-aligned; overdue rows carry danger rail; status chips everywhere.
- **N:** Dues/payments rows open the receipt sheet (view/void); Student Fees selects via master list.
- **A:** Balance cells pulse on change; voids animate a strike-through + grey 300ms.
- **S:** 32–36px rows; totals footer pinned.
- **CP:** "Record payment" primary (opens G.6 receipt sheet); "Export" ghost; totals footer (sum/avg/count).
- **E:** Empty dues → "No dues — structure not assigned yet" + link; empty payments → "Record your first payment".
- **H:** Row wash; receipt # brightens; voided rows muted permanently.
- **LD:** Ledger skeletons with totals footer shimmer.
- **K:** `N` payment · `V` void focused (confirm) · `E` export · `F` filter.
- **MI:** Balance pulsing 50%→100% opacity once on live update; receipt lookup inline from any row (⌘⇧R).
- **T:** Cell pulse 120ms; ledger crossfade 120ms.

### G.4 School Finance (broader)
- **P:** The accountant's full picture: schedules, outstanding balances, receipts, reconciliation, transactions.
- **L:** Workspace rail: Dashboard / Schedules / Outstanding / Receipts / Reconciliation / Transactions / Reports. **Schedules**: structure calendar (due dates per term, auto-generate dues). **Outstanding**: aged receivables table (0-30 / 31-60 / 61+ buckets as columns with subtotals). **Receipts**: receipt register (T.4). **Reconciliation**: two-pane side-by-side (system ledger vs bank statement import) with match/unmatch controls; unmatched rows amber. **Transactions**: full GL-style ledger with category filters.
- **VH:** Aged buckets columnar — the eye reads aging instantly; unmatched reconciliation rows are the loudest anomaly.
- **N:** Rail switches tools; rows deep-link to student fee panes or receipt sheets.
- **A:** Aging table reflows 160ms; reconciliation match flies a check and greys both rows 200ms.
- **S:** Ledger rows 36px; reconciliation panes min 400px each.
- **CP:** Reconciliation: "Import statement" primary; "Auto-match" ghost; unmatched counter chip in the rail.
- **E:** No statements → reconciliation shows "Import your first statement" + template download.
- **H:** Ledger row wash; match controls lift; buckets header count-up.
- **LD:** Skeleton per tool; import progress hairline.
- **K:** `1-7` tools · `M` match focused pair · `E` export · `F` filter.
- **MI:** Auto-match suggests with a 400ms amber→green settle; totals tick after every match.
- **T:** Tool crossfade 160ms; match 200ms.

### G.5 Receipt Lookup
- **P:** Find any payment by receipt number, student, or amount — instantly.
- **L:** Search-first single screen: big receipt search field (mono placeholder "e.g. RCP-2026-0042") + result card (receipt facsimile: header, student, items, totals, method, recorded-by) + "print/email/void" actions. Recent lookups listed below.
- **VH:** The receipt facsimile is designed like an actual receipt — type hierarchy that prints identically.
- **N:** Enter searches; result card is the screen; actions right.
- **A:** Result card rises 200ms; receipt lines stagger 24ms.
- **S:** Max-width 720px; receipt padding 32px (print-like).
- **CP:** Search dominates; recent lookups ghost list under it.
- **E:** No match → "No receipt found" + suggestions (typo? student lookup?).
- **H:** Recent rows wash; actions lift.
- **LD:** Receipt-shaped skeleton (lines of text widths).
- **K:** `/` focus search · `↵` search · `⌘P` print · `⌘E` email.
- **MI:** Search-as-you-type prefixes match in mono with accent; last-5 lookups persist per campus.
- **T:** Result 200ms; search swap 120ms.

---

## H. Insights (workspace)

### H.1 Analytics Hub
- **P:** Choose the lens: academic, attendance, finance, student analytics — one hub, no dead-end.
- **L:** Hub grid of four large entry cards (accent duotone glyphs, title, one-line description, sample sparkline); below: "Recent reports" list. Each card is a workspace-switch.
- **VH:** Cards equal; the "most relevant" (per role) is subtly pinned first with a small badge.
- **N:** Cards navigate to H.2–H.5; recent reports deep-link.
- **A:** Cards stagger 24ms; sparklines draw 400ms.
- **S:** Grid gap 24px; cards 24px padding.
- **CP:** Hub is single-purpose; no primary action (role-aware default pinned card is the affordance).
- **E:** n/a (hub never empties).
- **H:** Card lift 4px + border accent; glyph brightens.
- **LD:** Card skeletons with sparkline shimmer.
- **K:** `1-4` lenses · `↵` open.
- **MI:** Sample sparkline on the pinned card animates on hover.
- **T:** Stagger 24ms; open 260ms.

### H.2–H.5 Analytics (Academic / Attendance / Finance / Student)
- **P:** Deep single-domain analytics. H.2 academic: score distribution, subject performance, term trends. H.3 attendance: trend, status breakdown, class comparison, period heatmap. H.4 finance: collection trend, category split, aging. H.5 student: distribution by class/section, top/bottom performers, flags.
- **L:** Shared analytics scaffold: filter bar (term/year, class/section, date range — sticky under toolbar) → hero metric row (3 KPIs) → main chart (large, left 8-col) + side panel (4-col: secondary chart + top-5 list) → drill-down table (T.4, clickable rows).
- **VH:** One hero chart per screen; everything else secondary. v3 chart language (§12.9): horizontal-only gridlines, ≤6 series, draw-in, tabular tooltips.
- **N:** Chart series click → drill table; table rows → records; filter changes re-render with crossfade.
- **A:** Charts draw 500ms; filters crossfade 120ms; KPIs count up.
- **S:** 16px paddings; hero chart min 420px tall; side panel 4-col.
- **CP:** Export (PDF/Excel) ghost right of filter bar; drill table below fold-1.
- **E:** No data for filters → chart area shows "No data for this selection" with reset-filters ghost — never an empty frame.
- **H:** Series emphasis + crosshair; table rows wash.
- **LD:** Chart skeletons mirror shapes; filter hairline progress.
- **K:** `E` export · `F` filter · `R` reset · `1` hero toggle.
- **MI:** Tooltip values in tabular mono; drill rows open with a 120ms pulse.
- **T:** Charts 500ms; filter 120ms; drill 160ms.

### H.6 Reports Hub & H.7–H.9 Report Screens (Attendance / Fee Collection / Outstanding)
- **P:** One page per report class, each a T.4 ledger + export center: run, preview, export, schedule.
- **L:** Hub: recent reports + templates list. Report screen: filter bar (period, class, status) → preview table (live) → export panel (right 300px: format PDF/Excel, columns, orientation, "Export" + "Schedule monthly").
- **VH:** Preview leads; export panel is secondary but always visible; totals footer.
- **N:** Templates open their report screen; exports toast with progress hairline + download.
- **A:** Preview rows stagger 24ms; export progress 120ms; scheduled badge pops.
- **S:** Preview 36px rows; export panel 300px.
- **CP:** "Export" primary in export panel; "Run" ghost beside filters.
- **E:** No data → quiet empty + "adjust period".
- **H:** Rows wash; export format cards lift.
- **LD:** Preview skeleton + export panel skeleton.
- **K:** `⌘↵` run · `⌘E` export · `S` schedule.
- **MI:** Export button counts rows; completion toast has "Reveal in Files" (native download).
- **T:** Rows 24ms; run crossfade 120ms.

### H.10 Report Builder
- **P:** Compose custom reports: pick fields, filter, preview, save, schedule.
- **L:** T.6 builder canvas: left palette (entity fields, draggable), center canvas (column drop zones, live preview table, 8px snap), right inspector (field settings: label, width, format, sort; report settings: title, filter rules). Top row: Save / Run preview / Export.
- **VH:** Canvas is king; palette muted; inspector contextual to selection (accent ring on selected column).
- **N:** Drag from palette to canvas; columns reorder by drag; inspector edits selection; saved reports → H.6 hub.
- **A:** Drag ghost springs; drop settles 200ms; preview re-renders 120ms; columns reorder slide 160ms.
- **S:** Rail 240px; inspector 300px; canvas min 480px.
- **CP:** Run preview primary in top row; Save ghost; "New from template" ghost.
- **E:** Empty canvas → drop-zone illustration "Drag fields here" + "Start from a template" row.
- **H:** Palette items lift on drag; drop zones glow on hover-over; column headers wash.
- **LD:** Canvas shows preview skeleton while running; palette never blocks.
- **K:** `⌘Z/⇧⌘Z` · `⌘D` duplicate column · `⌫` remove · arrows nudge · `⌘↵` preview · `⌘S` save.
- **MI:** Unsaved-changes dot in the toolbar; column count chip ("12 columns"); drag reorder shows live insertion indicator.
- **T:** Drop 200ms; preview 120ms; inspector slide 160ms.

### H.11 Report Cards
- **P:** Student report cards: design the template, generate per-class, preview, print.
- **L:** T.6 canvas with A4-paper metaphor: page frame (8.5×11 ratio, hairline), header/grade-table/subject-grid zones as drop targets, inspector for layout (margins, show/hide sections). Toolbar: class selector, "Generate for class", "Print batch".
- **VH:** The paper is the hero (white, shadows only via print-style hairline); canvas chrome recedes.
- **N:** Class selector drives generation; per-student preview via a page stepper.
- **A:** Pages flip with a 120ms slide; generation progress hairline + count.
- **S:** Paper canvas centered; margins per inspector (default 48px).
- **CP:** Generate primary; print batch ghost; template library ghost.
- **E:** No students in class → "Nothing to generate" + enroll link.
- **H:** Drop targets glow; zone selection ring.
- **LD:** Page skeleton mirrors layout while generating.
- **K:** `⌘↵` generate · `⌘P` print · `←→` page stepper.
- **MI:** Print batch queues with a progress toast ("12/48 printed").
- **T:** Page flip 120ms; generation 160ms.

### H.12 Risk Center *(moved under Insights; see B.3 for full spec — here: role framing)*
- **P:** Risk as insight, not alarm — same spec as B.3, framed as the Insights workspace's "attention" screen.
- **L/N/A/S/CP/E/H/LD/K/MI/T:** Identical to B.3. Reached from Insights rail; Today's queue deep-links here with the finding pre-selected.

---

## I. Operations (workspace)

### I.1 Operations Hub
- **P:** The single door to batch work: enrollments, fee dues, rollover, exports.
- **L:** Hub grid of operation cards (Batch enroll, Generate fee dues, Roll over year, Export data) each with icon, title, description, last-run info, and "Run" ghost. Below: "Recent runs" list with status chips (complete / failed / partial).
- **VH:** Destructive/irreversible ops (Rollover) carry a danger chevron and require a confirm sheet; reversible ops accent.
- **N:** Cards open their wizard; recent runs deep-link to results.
- **A:** Cards stagger 24ms; run status pops on completion.
- **S:** Grid gap 24px; cards 16px padding.
- **CP:** No single primary — each card is its own entry; "History" ghost top-right.
- **E:** No runs yet → "No operations run yet" + first-run hint.
- **H:** Cards lift; danger cards tint red edge on hover.
- **LD:** Card skeletons.
- **K:** `1-6` ops · `↵` run · `R` recent runs.
- **MI:** Last-run relative time; failed runs count-up on the badge.
- **T:** Stagger 24ms; status pop 200ms.

### I.2 Batch Enroll / I.3 Generate Fee Dues (wizards)
- **P:** Bulk operations with a safe, reviewable flow: source → preview → run → results.
- **L:** Four-step wizard in a 720px sheet: **1 Source** (file drop / search-multi-select / class-based), **2 Map** (column mapping for files, live preview of first 5 rows), **3 Review** (full preview table with per-row validation chips: valid/warning/error + reasons), **4 Run** (progress + result summary: imported count, failures table with download-errors).
- **VH:** Step indicator (1-4) top; preview is the loudest; validation errors danger-coded; the "Run" primary appears only on step 4.
- **N:** Steps gated (Next disabled until valid); back always safe; Esc cancels with confirm if work in progress.
- **A:** Step transitions slide 160ms (direction-aware); validation chips pop; progress bar hairline.
- **S:** 720px; step content 16px padding; preview 36px rows.
- **CP:** Footer: Back ghost left, Next/Run primary right; step indicator top center.
- **E:** Bad file → upload dropzone error state with the specific parse error + "download template" link.
- **H:** Preview rows wash; chips micro-lift; dropzone highlights on drag-over.
- **LD:** Preview skeleton during parse; per-row validation streams in.
- **K:** `⌘↵` next/run · `⌘←` back · `Esc` cancel.
- **MI:** Valid rows tick green as validation resolves; error rows shake once + focus; final summary counts count up.
- **T:** Step slide 160ms; chips 120ms.

### I.4 Rollover (year-end)
- **P:** Safe, reversible-until-committed year transition: archive → carry → verify.
- **L:** Full workspace (not a sheet — this deserves the room): checklist wizard: 1 Pre-flight (required checks: dues settled?, attendance archived?, reports exported? — each with status chip), 2 Carry-forward selections (which structures/balances/rosters roll into the new year), 3 Review (what will change — side-by-side old vs new), 4 Commit (type confirmation phrase, then progress).
- **VH:** Checklist states (pending / passed / blocked) drive the flow; the Commit step is visually dangerous (red confirmation field).
- **N:** Blocked checks must resolve (deep-link); Commit disables until phrase typed.
- **A:** Checklist items tick with draw; progress hairline; old-vs-new diff rows slide.
- **S:** 56px rows; diff grid 8px gaps; max-width 900px.
- **CP:** "Begin rollover" primary only when all checks pass; "Export archive first" ghost.
- **E:** n/a (structured flow).
- **H:** Checklist rows wash; diff rows brighten.
- **LD:** Pre-flight scans show progress per check.
- **K:** `⌘↵` next · `1-4` steps · `Esc` back (confirm).
- **MI:** Phrase confirmation field unlocks the commit with a spring; post-commit shows a full success state with archive download.
- **T:** Step 160ms; commit success 300ms.

### I.5 Exports (Attendance / Payments / Students)
- **P:** Get data out, cleanly, for the formats people actually need.
- **L:** T.1 list of export jobs (type, format, filters used, requested by, status, download) + "New export" sheet (pick type → format PDF/Excel/CSV → columns → filters → run). Running jobs live in the status bar too.
- **VH:** Job status chips (running hairline / complete / failed); completed jobs are the focus.
- **N:** New export opens sheet; completed rows download in place; failure rows offer "view error".
- **A:** Completion row pops + toast; progress hairline.
- **S:** 40px rows; sheet 560px.
- **CP:** "New export" primary; filters preview (row count) in the sheet.
- **E:** No jobs → T.8 "Export your first report" + quick links to common exports.
- **H:** Rows wash; download lifts.
- **LD:** Running rows show inline progress bar.
- **K:** `N` new · `↵` download · `F` filter.
- **MI:** Row count estimates stream in ("≈ 1,240 rows"); big jobs warn before run.
- **T:** Completion pop 200ms.

---

## J. Communicate (workspace)

### J.1 Composer
- **P:** Send announcements/messages to parents, students, staff — once, to the right people.
- **L:** Two-pane: left recipient builder (segments: whole class, custom list, role filter — with live count and expandable preview), right message canvas (subject, rich text, template picker, send-time). Footer: "Send now" primary + "Schedule" ghost.
- **VH:** Recipient count is the headline number (display, tabular); message canvas fills.
- **N:** Segments combine visually (chips); send/schedule from footer; delivery report opens J.3.
- **A:** Recipient count counts up; chips pop; canvas fields stagger 24ms.
- **S:** Panes 8px gap; chips 8px; canvas padding 24px.
- **CP:** Template picker above canvas; delivery channels (email/SMS/in-app) as toggles beside the footer.
- **E:** No recipients → builder empty state "Pick a class or role to start".
- **H:** Segment rows wash; channels lift; chips dismiss on hover.
- **LD:** Contact list skeleton while resolving segments.
- **K:** `⌘↵` send · `⌘⇧↵` schedule · `⌘T` template · `⌘D` draft.
- **MI:** Sending shows a fly animation (paper plane) then a delivery toast; unsent edits warn on leave.
- **T:** Stagger 24ms; send 200ms.

### J.2 Templates & J.3 Sent
- **P:** Reusable message skeletons; delivery tracking.
- **L:** J.2: template list (T.1) + preview pane + "New template" sheet (variable insertion `{{student_name}}` autocomplete). J.3: sent ledger (T.4): message, audience count, channels, sent time, opened/delivered/failed chips + drill-down detail sheet (per-recipient status).
- **VH:** Failed deliveries are danger-flagged; opened-rate small progress bar per message.
- **N:** Templates → "Use" opens J.1 pre-filled; Sent rows → detail sheet → "Resend to failed".
- **A:** Template preview crossfade 120ms; delivery chips pop.
- **S:** 36-40px rows; preview 320px pane.
- **CP:** "New template" primary; "Resend failed" ghost in detail.
- **E:** No templates → T.8 "Create your first template"; no sent → "Your messages will appear here".
- **H:** Row wash; chips lift.
- **LD:** List + preview skeletons.
- **K:** `N` new · `↵` open · `R` resend.
- **MI:** Opened-rate bars fill 400ms; failure rows pulse once.
- **T:** 120ms crossfades.

### J.4 Approvals (workflow inbox)
- **P:** The approval queue: leave, workflow steps, and permission requests — decided in place.
- **L:** T.1 list of approval cards (title, requester avatar, type, submitted time, priority chip) + right detail pane (request context, history, decision bar: Approve accent / Reject danger / Comment ghost). Filters: type / priority / "assigned to me".
- **VH:** Priority drives ordering; the decision bar is the loudest element in the pane.
- **N:** Keyboard-first decisions; deep-links to the underlying record (leave request, workflow step).
- **A:** Approval card flies check/X and collapses 200ms; queue reflows; counts update.
- **S:** Cards 16px padding; pane 380px; decision bar 64px.
- **CP:** Approve right, Reject danger-left, Comment ghost; batch actions bar appears on multi-select.
- **E:** Empty inbox → success state "All caught up" + bell link.
- **H:** Cards wash; decision buttons lift; requester avatar rings.
- **LD:** Card skeletons.
- **K:** `A` approve · `R` reject (reason sheet if required) · `C` comment · `J/K` next/prev · `1-3` priority filter.
- **MI:** Decisions animate the card out and update counts live; reject with reason shakes the card once.
- **T:** Card 200ms; queue reflow 160ms.

### J.5 Notifications (full page)
- **P:** The complete notification history (the drawer S.6 is the surface; this is the archive).
- **L:** Same anatomy as S.6 but full-pane: filters (type/date/read) + grouped list + "mark all read" + per-item settings ("stop these" → preferences sheet).
- **VH/N/A/S/CP/E/H/LD/K/MI/T:** Inherits S.6, plus: prefs sheet with per-event-type toggles; archive groups by month; shortcut `⌘M` mark-all.

---

## K. Settings (workspace)

### K.1 Profile
- **P:** Personal account: identity, security, appearance, notifications preferences.
- **L:** Left rail (Profile / Security / Appearance / Notifications) + content pane. Profile: avatar + display name + contact. Security: change password (current required), sessions list (revoke). Appearance: theme (light/dark/system) with live preview tiles, density mode, reduced-motion override. Notifications: per-event-type preference table with toggles.
- **VH:** Settings are quiet chrome; destructive items (revoke session, delete account) ghost-danger at pane bottom.
- **N:** Rail switches panes; changes save inline with 120ms flash.
- **A:** Panes crossfade 120ms; toggles spring; theme preview tiles swap live.
- **S:** Pane 720px max; rows 40px.
- **CP:** Danger zone pinned bottom of each relevant pane; "Sign out everywhere" in Security.
- **E:** No sessions → "No active sessions".
- **H:** Rows wash; toggles lift.
- **LD:** Pane skeletons.
- **K:** `1-4` panes · `⌘S` save · `⌘,` open settings from anywhere.
- **MI:** Theme preview tiles show a real sample card; density change animates the pane immediately.
- **T:** Pane 120ms; theme swap 300ms.

### K.2 Audit Log
- **P:** Tamper-evident record of who did what, when — for admins and compliance.
- **L:** T.4 ledger: timestamp (mono), actor, action verb, resource type, resource, campus, IP, outcome chip; filters: actor/type/date/outcome; detail sheet per row (full payload). "Export" with signed-hash note.
- **VH:** Outcome (success/denied) leads; sensitive actions (delete, role change) carry a subtle danger tint.
- **N:** Filters drive; rows open detail sheets; "related events" link chains.
- **A:** Filter crossfade 120ms; export hairline.
- **S:** 32px rows; mono columns right-aligned.
- **CP:** Export right; filters left; detail sheet (T.5).
- **E:** No events in range → quiet empty + "adjust filters".
- **H:** Row wash; payload mono brightens.
- **LD:** Ledger skeleton.
- **K:** `F` filter · `E` export · `↵` detail.
- **MI:** Denied outcomes flash amber once on arrival (live tail).
- **T:** 120ms crossfades.

### K.3 Leave (list / detail / request)
- **P:** Staff leave: request, approve, and track.
- **L:** List (T.1: requester, type, dates, balance, status chip) + detail pane (dates, reason, balance before/after, history, decision bar for approvers). "New leave" sheet (T.5: type, dates, reason, balance preview).
- **VH:** Balance column tabular; status chips lead; approvals get the decision bar language.
- **N:** Requests deep-link to the employee; decisions update balance chips live.
- **A:** Decision flies check/X 200ms; balance chip counts.
- **S:** 40px rows; sheet 560px.
- **CP:** "New leave" primary for staff; decision bar for approvers.
- **E:** No requests → "No leave requests" + link to policy.
- **H:** Rows wash; chips lift.
- **LD:** Skeletons.
- **K:** `N` new · `A/R` approve/reject · `↵` open.
- **MI:** Balance preview updates as dates are picked (net-working-days estimate).
- **T:** Decision 200ms.

---

## L. Portals (parent & student)

> Portal philosophy (T.7): a calm, read-first surface — not a miniature admin app. Larger type, 44px touch targets, one thing per screen, offline-friendly (PWA), and every figure rendered as a friendly card.

### L.1 Parent Dashboard
- **P:** A parent's morning: each child's day at a glance.
- **L:** Top bar (back, title, bell) → child cards (avatar, name, class, today's attendance status chip, latest announcement) stacked; below: "Fees due soon" summary strip + quick links (attendance, fees, results).
- **VH:** Children are the hero; status chips second; everything single-column, max 900px.
- **N:** Child card → per-child portal (L.2–L.8); fee strip → fee screen.
- **A:** Cards stagger 24ms; status chips pop on refresh.
- **S:** Card gap 12px; padding 20px; type 16px.
- **CP:** Bottom action bar: primary context action (e.g., "View today's attendance").
- **E:** No linked children → "Link your child" + code-entry sheet.
- **H:** Cards lift 2px; chips stay.
- **LD:** Child-card skeletons with status-chip shimmer.
- **K:** `1-9` jump children · `↵` open · `R` refresh.
- **MI:** Today's attendance chip pulses while unread; pull-to-refresh.
- **T:** Stagger 24ms; open slide 260ms.

### L.2–L.8 Parent Screens (Children / Fees / Attendance / Academic / Communication / Documents / Announcements)
- **P:** Per-domain reads for a selected child. L.2 children manager (which children are linked), L.3 fees (balance card, installments, pay link → payment sheet), L.4 attendance (month heatmap + exceptions), L.5 academic (results cards by term), L.6 communication (reply thread from the school), L.7 documents (report cards/downloads), L.8 announcements (feed).
- **L:** Shared portal scaffold: back-to-child chip, title, single-column cards. Fees/attendance/academic render as friendly summary cards with expandable detail — **never raw tables** at portal density.
- **VH:** The single most important number (balance / attendance % / latest result) is the card's headline.
- **N:** Child chip switches child in place; bottom bar has the one primary action per screen (Pay now / Reply / Download).
- **A:** Card swap crossfade 160ms; numbers count up; heatmap fills 24ms stagger.
- **S:** Cards 20px padding, 12px gaps; max 900px.
- **CP:** Primary in bottom bar (thumb-reach); secondary actions ghost.
- **E:** Each domain has a friendly empty ("No results yet this term", "No announcements").
- **H:** Cards lift; expandable rows wash.
- **LD:** Card skeletons; images (documents) lazy-load with shimmer.
- **K:** `↵` open card · `⌘P` print · back via `Esc`.
- **MI:** "Pay now" opens a lightweight payment sheet with a success glow on completion.
- **T:** Swap 160ms; expand 200ms.

### L.9 Student Dashboard
- **P:** A student's day: timetable now, attendance today, latest results, announcements.
- **L:** Hero card: "Next up" (today's next class with time + room, live) → today's attendance status chip → result highlight → announcements feed. Bottom bar: "View timetable".
- **VH:** "Next up" is the only loud thing; everything else is calm cards.
- **N:** Cards deep-link to L.10–L.15; bottom bar primary.
- **A:** Hero updates with a 200ms flip when the period changes; cards stagger.
- **S:** 900px max; hero 24px padding.
- **CP:** Bottom bar: "View timetable" primary.
- **E:** No timetable → "No classes scheduled today".
- **H:** Cards lift.
- **LD:** Hero skeleton with clock shimmer.
- **K:** `↵` open · `T` timetable.
- **MI:** Period change plays a soft clock-flip; attendance chip pulses if today unmarked.
- **T:** Flip 200ms; stagger 24ms.

### L.10–L.15 Student Screens (Attendance / Subjects / Results / Assignments / Timetable / Documents / Announcements)
- **P:** Per-domain student reads: attendance (month heatmap + status), subjects (subject cards with teacher + scores), results (term result cards), assignments (due list with due-soon danger chips + submission status), timetable (week grid with today highlighted and current class pulsing), documents (downloads), announcements.
- **L:** Shared scaffold (L.2–L.8): back chip, title, single column, friendly cards, primary in bottom bar. Timetable is the one "dense" exception: a 7-col week grid with today's column accented.
- **VH:** Due dates and today's classes are the loudest signals.
- **N:** Cards open expandable detail; bottom bar primary.
- **A:** Heatmap fill stagger; timetable row pulse on current class; due chips pop.
- **S:** Cards 20px padding, 12px gaps.
- **CP:** Bottom bar per-screen primary (View subjects / Open result / Mark done).
- **E:** Friendly empties per domain.
- **H:** Card lift; timetable cell brighten.
- **LD:** Card skeletons; result documents lazy shimmer.
- **K:** `↵` open · `←→` timetable days.
- **MI:** Assignments count-down ticks; completing an assignment flies a check.
- **T:** Swap 160ms; expand 200ms.

---

## M. Cross-cutting reference

### M.1 Global keyboard map (consolidated)
| Keys | Action |
|---|---|
| `⌘1..⌘9` | Switch workspace |
| `⌘K` | Command palette |
| `⌘⇧K` | Global search |
| `⌘⇧M` | Notification center |
| `⌘[` / `⌘]` | Back / forward |
| `⌘B` | Toggle sidebar |
| `⌘,` | Settings |
| `⌘⇧S` | Sync now |
| `?` | Shortcuts help (in-app) |
| `/` | Focus current screen's search/filter |
| `N` | New (context: sheet for that screen) |
| `E` | Export (screens with export) |
| `F` | Focus filters |
| `Esc` | Close sheet/popover/drawer, return to list |

### M.2 Density & type defaults by screen family
| Family | Row height | Type | Used by |
|---|---|---|---|
| Ledger | 36px (compact) | body-sm, tabular | Finance, attendance records, audit, risk |
| List | 44px | body | People, academic, reports |
| People profile | 48px | body | Student/teacher detail accordions |
| Portal | 56px+ | body 16px | Parent/student |
| Builder canvas | n/a | body | Report builder/report cards |

### M.3 The three global loading contracts
1. **First paint:** window-shaped shell skeleton (S.1).
2. **Screen data:** layout-mirroring skeleton per screen (never a centered spinner).
3. **Long operations:** 2px progress hairline under the toolbar + status bar sync state + cancellable where safe.

### M.4 Empty-state registry (every screen's empty is specified in its entry; the language is fixed)
- **T.8** = orientation (title, body, one action, optional steps).
- **Quiet empty** = small muted row + link (for sections within an otherwise populated screen).
- **Success empty** = "all clear / all caught up / no findings" with success glow (command center, risk, approvals, notifications).

### M.5 Error-state contract
Field (shake + message) → banner (inline, retry) → full-page (illustration, correlation ID, retry, safe path). Partial failures always show success-with-errors summaries and a downloadable error list. Offline = global banner + queued writes.

### M.6 Do / Don't (redesign-specific)
**Do:** master–detail over route-hopping · sheets over pages · skeletons over spinners · keyboard over mouse · compact ledgers, comfortable people · status as chip+icon+text · one primary per screen.
**Don't:** marketing heroes on work screens · icon-grid navigation · modal-on-modal · reveal-only-on-hover actions · raw tables in portals · animated anything longer than 500ms · hiding destructive actions.

### M.7 Rollout (implementation waves)
1. **Shell** (S.1–S.8) + workspace IA — replaces the current `app-layout`/`sidebar`/`header`.
2. **People + Today** — the two most-used workspaces; proves the master–detail and inspector patterns.
3. **Finance + Attendance** — proves the ledger and hero-flow (record attendance) patterns.
4. **Insights + Operations + Communicate** — builder canvas, wizards, approvals.
5. **Portals + Settings** — the calm, read-first shells.
Each wave is independently shippable; the shell wave is the only hard prerequisite.

---

*End of catalog. Part 1: `docs/APP_REDESIGN_V3.md`. Design system: `docs/DESIGN_SYSTEM_V3.md`.*
