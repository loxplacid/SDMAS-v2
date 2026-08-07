# SDMAS Analytics System — v3 Specification

**Codename:** *The Watchtower*
**Status:** Draft for review · **Owner:** Product Design · **Version:** 3.0.0
**Scope:** apps/web (desktop-first) · **Companion docs:** `docs/DESIGN_SYSTEM_V3.md` (the *Corridor* — tokens, palette, typography) and `docs/MOTION_SYSTEM_V3.md` (the *Compass* — choreography). This document is the normative expansion of the Corridor's §12.9 *Graphs* and the *Insights* workspace.

> A school run at the quality of a bank watches three numbers a day, and can get to the third decimal in under four keystrokes. The Watchtower is the view from the top of the school — dense enough to scan, calm enough to think in.

---

## 0. Thesis — the three jobs of the analytics layer

Analytics in SDMAS has exactly three jobs, in order:

1. **Watch** — the school's vital signs at a glance: attendance today, fees this week, alerts now. The morning scan takes eight seconds.
2. **Investigate** — from a blinking number to the underlying rows in ≤3 interactions. No number is ever a dead end.
3. **Decide** — compare, forecast, and commit: is this class worse than last term, and is the fee campaign going to hit target?

Everything that does not serve one of these three is decoration. Concretely rejected: gradient hero charts, 3D/bevel effects, chart junk (excessive gridlines, dual-unnecessary axis), charts that exist to fill a card, and any animation that outlives its data's usefulness.

**The posture is Bloomberg Terminal meets Apple:** the *information density and at-a-glance scanning* of a terminal, with the *hierarchy, restraint, and spatial continuity* of an Apple product. Terminal density decides what we show; Apple restraint decides what we hide.

---

## 1. Sources & extraction — principles only, nothing copied

| Source | What it demonstrates | Principle extracted | Translation into SDMAS |
|---|---|---|---|
| **Bloomberg Terminal** | Everything fits; nothing scrolls; every screen is a grid of panels with a live readout | **Density as respect** — the monitor shows more because it treats the user's attention as scarce | Full-width chart rooms; the *sparkgrid*; window presets 1D/1W/1M/1Y; live readouts in every chart header |
| **Bloomberg Terminal** | Function codes (`WEI`, `TOP`) and a command line summon any surface instantly | **The command line** — keyboard as the fastest pointer | Analytics command bar (`/attendance`, `STU:101`), function-style deep links, saved views |
| **Bloomberg Terminal** | Amber = caution, red = alarm, green = good; instant response; the market never waits | **Status semantics + the fast clock** — color means *state*, not decoration; updates feel live | The status language (§4.3); SSE live floor (§7); feedback outruns transition |
| **Apple (HIG)** | Hierarchy of information; remove chrome; spatial continuity; direct manipulation | **Hierarchy & restraint** — one hierarchy per screen; the data is the interface | The readout-as-header pattern; empty states instead of empty frames; chart chrome hidden until hover |
| **Apple (HIG)** | Dark mode is first-class, not a skin | **Themes as native states** | Every chart token has a light and dark value; the terminal rooms run dark by default |
| **Linear / Figma** | Fast, precise chart interactions; keyboard-first power | **The fast clock** | Hover ≤120ms, brush ~60ms, all interactions transform+opacity only |

The output below is original. Values reference the Corridor's tokens and the Compass's move specs wherever they exist.

---

## 2. The chart room (the frame around every chart)

Every chart lives in a **chart room**: a full-width card with a fixed anatomy, so scanning many charts takes no re-learning.

```
┌────────────────────────────────────────────────────────────────────┐
│  Attendance % · Class 7A          [1D][1W][1M][1Y] ◈ [⋮] [⛶] [⥁]  │  ← header row
│  94.2%  ▲2.1 vs last week         · Present  Absent  Late  Excused  │  ← live readout + series legend
├────────────────────────────────────────────────────────────────────┤
│  (plot area — gridline, crosshair on hover, range brush on demand)  │
├────────────────────────────────────────────────────────────────────┤
│  last updated 09:42 · source: live              [Export] [Compare]  │  ← footer row
└────────────────────────────────────────────────────────────────────┘
```

**Header row** (always visible):
- Title: `h4` weight 600, tabular numerals, left. Unit embedded when ambiguous ("Attendance %", "₹ / term").
- **Window presets** — `1D 1W 1M 1Y` as underline tabs (Corridor §12.8). Default `1M`; `1D` is a time-of-day view for live metrics. Preset switch is a *condensation* move (fast crossfade, §6.4 filter rule) — never a slide.
- Right cluster: **Compare** (⊕), **Fullscreen** (⛶), **export** (⋮ menu: PNG / CSV / PDF, share).

**Readout row** — the single most important pattern in the system:
- The **current value** is a large tabular numeral (`text-xl`, weight 700) followed by a **delta chip** (▲2.1 vs last week, green/amber/red per §4.3). On hover, the readout live-replaces with **the value at the cursor** and the delta becomes "vs previous period".
- The **series legend** sits right of the readout: 8px color swatches + name, all *clickable to toggle series* (§6), hover-dimming enabled.

**Footer row** (dense, `caption`):
- Left: provenance — "last updated 09:42 · source: live / report cache". For cached charts, a refresh affordance; for live charts, a pulsing sync dot (§7).
- Right: contextual actions — Export, and *"View underlying rows"* on any chart that has them.

**Rules:**
- Every number in a chart room is `tabular-nums`. No exceptions.
- A chart room is **not** a card — it has no box shadow at rest, only hairlines (Corridor §12.4 rule). Cards are for decisions; rooms are for reading.
- Chart rooms never nest more than one level.

---

## 3. The chart grammar (shared by every chart)

### 3.1 Axes & gridlines
- **Horizontal gridlines only**, `ink.200` at 1px, solid for the zero/axis line and dashed at 40% for midlines. **No vertical gridlines** (Corridor §12.9).
- **Y-axis:** linear default; log toggle available for skewed distributions (fee amounts, long-tail). Tick labels `caption` (12px), muted, right-aligned, tabular.
- **X-axis (time):** no tick labels below `1W` granularity where the sparkline carries the story; show `dd MMM` or `MMM` rotated 0°, every-nth label, never overlapping. Weekends appear as lighter column bands on school-day charts (never as gaps that imply "no data").
- **Axis titles only when the unit is not obvious** (§12.9). A chart that needs both an axis title and a legend and a footnote is two charts.

### 3.2 Scales & units
- Percentages: always `94.2%`, never `94.20`, never a 0–100 axis that clips the band (auto-pad ±5%).
- Currency: currency code in the header, never repeated per tick; thousands separators; `₹1.2L`/`$12.4k` compaction only in sparkgrid cells, never on axes.
- Dates: ISO-free, locale-aware. "Mon 12 Aug", not "2026-08-12".
- **Zero rule:** a zero baseline is drawn solid and emphasized on all bar charts; the axis never starts above zero on a bar/area chart unless the deltas are the story (then a `∿` marker indicates a truncated axis).

### 3.3 Series
- Categorical palette §3.4 of the Corridor; **max 6 series**; the 7th+ series aggregates into "Other" with a tooltip breakdown.
- **Semantic status colors are reserved for status** (§4.3) — a status breakdown chart may use green/amber/red, but a categorical trend chart must not (a finance series is never "red = bad" by palette accident).
- Area fills: 20% gradient tints of the stroke, fading to transparent (Corridor §12.9).
- The **primary series** in any room is the one the title names; it gets `strokeWidth 2.25`, others `1.5`, and it draws first (it is the subject).

### 3.4 Typography in charts
| Role | Token | Notes |
|---|---|---|
| Readout value | `text-xl` w700, tabular, −0.01em | The single largest number in the room |
| Header title | `text-base` w600 | |
| Axis/tick labels | `caption` (12px), muted | |
| Legend/footnote | `caption`, tertiary | |
| KPI numerals | `text-2xl` w700 tabular (Corridor §5) | KPI rooms |

---

## 4. Color as language

### 4.1 The palette is already built
Reuse Corridor §3.4 (`dv.*` categorical, Okabe-Ito-inspired, 6 series max, both themes). Charts must stop hardcoding Tailwind hexes (`#22c55e`, `#ef4444`…) — those are the v2 look this system replaces. All chart colors flow from `dv.*` tokens with dark-mode pairs.

### 4.2 Tints & states
- Selection/hover emphasis: `brand` tint at 8–12% for hovered bars/cells, `brand` stroke for the crosshair.
- Dimmed series at 40% opacity on hover-focus (Corridor §12.9).
- Threshold bands (e.g., the 90% attendance line, the overdue-30d band) render as a 1px `brand`/`amber` rule with a caption label — never as a filled region unless the region is the point of the chart.

### 4.3 The status language (the amber/red/green semantics)
Inherited from the Corridor and applied *consistently across every chart, chip, cell, and delta*:
- **Green = good / healthy / on track.** Never used to decorate — it states health.
- **Amber = caution / near threshold / at risk.** The default attention color; amber is the loudest color in the system because it appears most often.
- **Red = alarm / breach / off track.** Reserved for actual breaches (below the threshold, overdue beyond grace, failed goal).
- **Grey = neutral / no data / not applicable.**

Delta chips: ▲/▼/→ with green/red/grey per *whether the movement is good for the goal*, not per direction — rising overdue fees is red, rising collections is green. Each chip's direction must be paired with text ("▲2.1 vs last week"); never color-only (a11y, Corridor §10).

---

## 5. Chart type catalog — every chart, redesigned

Each entry: when to use it, the anatomy, its motion, its interactions. All motion references the Compass (draw-in = `Draw`, D1; KPI count-up = `slower`→`slowest`, `ease.enter`, tabular, ≤500ms).

### 5.1 Time-series line/area — *the spine*
The most common chart: attendance %, collections, enrollment, any number over time.
- **Anatomy:** 1–4 series, area fill only on the primary, horizontal gridlines, time axis, range brush reserved (appears on hover at the bottom edge, `fast`).
- **Motion:** lines **draw left→right** 500ms `slowest` with `ease.enter` (Compass §6.4 — only on first load of the room, never on window change; window change is a 160ms crossfade). Points fade in after the draw. When data updates live, the **new point draws in place** — the line never redraws.
- **Interactions:** hover crosshair with readout replacement (§6.1); click a data point → detail surface (daily row, term summary); wheel/brush zoom (§6.3).
- **Empty:** the room shows the empty state (§13.2 pattern) — never an empty plot frame.

### 5.2 Composed bar + line — *finance's workhorse*
Collections vs dues, enrollments vs targets: bars for one measure, a line for the other, twin scales only when the units truly differ (and then the secondary axis is drawn on the right with its own gridline *only* on its scale).
- **Motion:** bars **grow from baseline** (`Draw`, 300–380ms, staggered 20ms per group — never more than 12 bars animated); the line draws over after.
- **Interactions:** hover highlights the bar *and* the point; clicking a bar drills into the period's transaction list.

### 5.3 Stacked bars & stacked area — *composition over time*
Attendance status composition (present/absent/late/excused per week), fee status (paid/partial/waived/overdue).
- **Anatomy:** one bar per period, segments ordered consistently (healthy first), total at top (`tabular`). Stacked area only for the primary composition; two stacked areas never overlap.
- **Motion:** segments grow bottom-up in their visual order, 20ms stagger, total ≤500ms.
- **Interactions:** hover reads the segment + % of bar; click a segment → filtered underlying rows.

### 5.4 Calendar heatmap — *the pattern finder*
Daily values across a term (attendance %, fee collections, incidents) — GitHub-style but denser and Apple-calmer.
- **Anatomy:** 7 rows (Mon–Sun) × weeks, cells `12–16px` squircle (`radius.squircle` token), value encoded by **intensity of a single hue** (never rainbow): brand for neutral volume, amber→red when the metric is a health metric and low is bad (attendance), green→red when both directions matter (fees: green collected, red overdue).
- **Legend:** a 4-step intensity strip (0 / low / med / high) — never a continuous rainbow bar.
- **Motion:** cells fill with a 120ms `fast` wash in reading order (capped 150ms stagger — Compass §4.3); a live cell pulses once on arrival (§7).
- **Interactions:** hover shows day + value + delta in the readout; click a day → that day's rows; drag-select a week → the week as a new time window.

### 5.5 Matrix heatmap — *class × period*
The Bloomberg-style monitor of the school: rows = classes (or teachers), columns = weeks (or subjects), cell = the metric, sorted so the worst row is on top.
- **Anatomy:** row header = class name + its 1M trend sparkline + current value; cell colors per §4.3 status semantics; column headers = weeks.
- **Motion:** cells reveal column-by-column, 20ms stagger, ≤150ms; row sorting is a **FLIP** (Compass §6.4).
- **Interactions:** hover row highlights the whole row (readout shows class summary); click row → class drill-down; click cell → the specific period+class detail. Sort by value / worst-first / alpha via column-header clicks.

### 5.6 Donut with goal arc — *goal tracking*
The goal-tracking primitive: "collections vs the ₹40L target".
- **Anatomy:** donut for composition (optional), with a **goal arc** — a `brand` arc from the goal point around the ring, and the value needle reading the % of goal. Center: the big number (`text-2xl` tabular) + "of ₹40L goal".
- **Status:** the arc and center number take green/amber/red per **distance to goal with time left** (on track / at risk / off track — §8).
- **Motion:** the arc **draws** 500ms; the needle settles with a spring (small object, Compass §3.4); the center number **counts up** ≤500ms.
- **Interactions:** hover shows exact values (current, goal, gap, days left, required daily pace); click → the goal's underlying ledger.

### 5.7 Bullet chart — *target vs actual vs bad*
The densest single-measure chart (Stephen Few's bullet): one bar = actual, a tick = target, a faint band = the "bad zone".
- Use for: fee recovery %, attendance targets, teacher workload targets, parent-communication response rates.
- **Anatomy:** a single horizontal bar (max 120px in a KPI room), target tick, bad-zone band, value label.
- **Motion:** bar draws `fast` (120ms) — the bullet is a *state*, not a spectacle.
- **Interactions:** hover → target vs actual vs gap readout; click → history sparkline.

### 5.8 Funnel — *enrollment & workflow journeys*
Applications → verified → admitted → enrolled → active; or workflow stages.
- **Anatomy:** centered horizontal bands, width ∝ count, labels inside with counts, conversion % between bands (`caption`, tabular).
- **Motion:** bands expand left→right 500ms with 20ms stagger.
- **Interactions:** hover highlights the band + conversion; click a band → that stage's records.

### 5.9 Quadrant scatter — *the two-variable lens*
Attendance vs grades; risk score vs recency; workload vs class size.
- **Anatomy:** two semantic axes (good is top-right by default), quadrant tints at 4% opacity, points = students/teachers/classes, sized by a third variable (optional).
- **Motion:** points **fade in** with 20ms stagger (never fly in); quadrant labels fade in after.
- **Interactions:** hover highlights the point + a callout with its identity and values; click → that entity's 360; brush-select a region → filtered list in a side sheet.

### 5.10 Distribution histogram — *grades, fee buckets, ages*
Grade distribution, fee-amount distribution, wait-times.
- **Anatomy:** equal-width bins, count on Y, the mean and median as tick marks (`brand`/`grey`), threshold lines per §4.2.
- **Motion:** bars grow from baseline, 20ms stagger ≤150ms.
- **Interactions:** hover reads bin range + count + %; click a bin → the students/records in it.

### 5.11 Sparkgrid — *the terminal monitor*
The Bloomberg-ism: a dense table where every row carries a sparkline. This is the **at-a-glance** surface — "all 40 classes, attendance, 1M trend, delta" in one screen.
- **Anatomy:** `density.compact` table (36px rows) with a `1.5px`-stroke, 40px-tall sparkline column, value column (tabular), delta chip column, status chip column. No column without a purpose; no vertical borders.
- **Motion:** rows enter `fast` with 20ms stagger; sparklines draw 500ms on first render only; re-sorting FLIPs (§6.4).
- **Interactions:** sort any column; hover row → row wash + readout; click row → detail room. This surface is keyboard-first: arrow keys move rows, `Enter` drills.

### 5.12 Activity timeline — *what happened, when*
The operational feed as a chart: attendance recorded, fees collected, alerts fired, jobs completed.
- **Anatomy:** a time axis with event glyphs; events are status-colored; a density band (histogram of event volume) above the axis; critical events get a label, others collapse to the tooltip.
- **Motion:** new events **slide in from the right** (`Slide E, D2`) as they arrive live; the band re-draws without redrawing older glyphs.
- **Interactions:** hover an event → its card (actor, action, timestamp); click → the audit detail; drag along the axis → time window scrub.

### 5.13 Heat band (mini heatmap) — *the 24-hour floor*
For live metrics: attendance marking flow through the school day, server load, collection activity.
- **Anatomy:** 24 columns (hours) × one row per stream, cell intensity per §4.1.
- **Motion:** the current hour's cell pulses on arrival; the band scrolls left on the hour.

---

## 6. The interaction model

### 6.1 Hover (the universal readout)
- Hover activates **within 120ms** (`fast`), never with a delay.
- A **crosshair** (1px `ink.300` vertical) aligns with the data point; the header **readout swaps to the hovered value** live (the room's headline becomes "Fri 12 Aug · 96.1% ▲1.4").
- The hovered series stays full; others **dim to 40%** (Compass §6.4). On the heatmap, the whole row highlights.
- Tooltips are **floating cards** (`radius.surface`, elevation floating, tabular numerals, series swatches, hairlines) per Corridor §12.9 — but the readout-in-header pattern means most charts never need a tooltip at all. If the header readout already answers the question, the tooltip stays hidden.

### 6.2 Click & drill-down (the investigate rule)
- **Every visible element is clickable** — a point, a bar, a cell, a row, an event glyph. No dead geometry.
- Click = **drill one level**: point → the period's breakdown; bar → the period's rows; matrix cell → class+period detail; sparkgrid row → the detail room.
- **Shift+click** = open the underlying **rows directly** (the ledger truth).
- Drill-down is `Slide E, D2` for the surface that appears (never a full page hop unless the user asks); back is the reverse.
- **Three clicks max** to reach raw rows from any chart. This is a hard rule.

### 6.3 Zoom (the time lens)
- **Range brush**: appears as a thin strip at the plot's bottom edge on hover (`fast` fade); drag to select a window; the chart re-axes to it (`Slide E`, 160ms crossfade).
- **Wheel zoom**: `⌥`+scroll zooms around the cursor (terminal habit); `⌥`+scroll resets. Trackpad pinch works where the browser supports it.
- **Keyboard**: `[` `]` step the window out/in; `0` resets. **Double-click the plot resets the zoom.**
- Zoom is transform-composited: the plot area scales/translates, axes re-render only on commit.

### 6.4 Comparison mode (the decide rule)
- **Compare (⊕)** toggles a second series layer: same measure, different window, entity, or scenario (this term vs last term; Class 7A vs 7B; actual vs forecast).
- The compared series renders **dashed**, in a second categorical hue, with a **delta readout** in the header ("94.2% vs 91.8% last term · ▲2.4").
- Comparison never adds a second Y-axis unless units differ (then §5.2's rule applies).
- **Entering/leaving comparison is a crossfade, never a replot.**

### 6.5 Fullscreen mode (the terminal room)
- **⛶** expands the room to the whole canvas (true fullscreen via the Fullscreen API on desktop; a "terminal room" overlay otherwise — the shell chrome fades out `fast`).
- In fullscreen, density steps to **compact**, the footer's provenance stays, and the room shows **up to 4 synchronized rooms** when the user adds them (watchlist mode: pick charts from any dashboard into one monitor — the multi-monitor Bloomberg pattern made personal).
- Escape exits fullscreen; the focus returns to the ⛶ button.

### 6.6 Window presets & provenance
- `1D 1W 1M 1Y` tabs are *state*, saved with the view (§9). Changing a window keeps the zoom/compare state where sensible.
- Every surface shows its **source** (live vs report cache) and **last updated** time — a terminal trusts nothing without provenance.

---

## 7. Live metrics — the live floor

Some numbers are alive: attendance being marked right now, collections arriving today, jobs running.

- **Transport:** the existing SSE endpoints (`/api/notifications/events` pattern) extended to analytics topics. The live floor is **push-first, poll-fallback** — if the stream drops, the room marks "stale" (`amber` provenance) and polls at 30s, then reconnects.
- **Live rooms:** the Command Center's pulse strip (§8.1), the "Today" readouts, the activity timeline, the 24h heat band. Everything else is report-cache — liveness is a property of the data, not a styling choice.
- **Arrival behavior (the pulse):** a live-updated number **pulses once** (Compass §7 — one Pulse per moment, ≤300ms scale bounce on the value only, not the whole room). A row/cell that changes value gets a one-shot **status wash** fading out over 180ms (Compass §6.4). If three numbers change in the same second, one Pulse on the loudest and still washes on the rest — never choreographed chaos.
- **Connection state:** a 6px sync dot in the footer — `brand` breathing gently (1.6s, the legal loop) while connected, `amber` solid when stale, `grey` when the room is offline/report-only. The dot is the *only* loop in a live room.
- **"Since midnight" counters:** the Command Center's live KPI numerals (marked present today, collected today) count up as they arrive; they never redraw the whole floor.

---

## 8. Goal tracking

A goal is a number with a deadline and an owner. The Watchtower tracks them as first-class objects.

- **Anatomy:** a goal strip (KPI room variant): bullet chart (§5.7) or goal-arc donut (§5.6), the goal's name, owner, deadline, and a **pace line**: current progress, required daily/weekly pace to hit target, and the **forecast line** (where current pace lands).
- **Status machine (the amber/red/green semantics):**
  - **On track (green)** — forecast ≥ target.
  - **At risk (amber)** — forecast within a configurable band below target (default 10%); still recoverable at 1.25× pace.
  - **Off track (red)** — forecast below target even at 1.5× pace, or deadline passed with a gap.
- **Forecast:** linear projection from the current slope with a stated confidence band ("±4% at this pace") — never a promise without a number.
- **Typical goals:** fee collection % by term end, attendance % per class, low-attendance students below threshold, enrollment to capacity, workflow completion.
- **Motion:** the arc/bar draws 500ms on load; the status chip settles `fast`; on a live update, the status **re-evaluates and the chip swaps** — the chip swap is the moment's one subject.
- **Interactions:** click a goal → its room (trend, pace, contributors, the ledger); every goal has a "review" action that opens the decision surface (approve, adjust, escalate).

---

## 9. Dashboards — every dashboard, redesigned

Layout rules first: every dashboard is a **grid of rooms** on a full-width canvas (the `1400px` page cap does not apply to analytics rooms — the terminal uses the whole window). Dashboards use `density.comfortable` by default, `compact` in fullscreen or at the user's setting. Filters are a **command bar** pinned under the page header, not a card above the charts.

### 9.1 Command Center — the morning watchtower
The Bloomberg-meets-Apple flagship. Redesigned from the current KPI-tile page into a live floor:
- **Row 0 (pulse strip):** 6 live KPI numerals (students present today, attendance % now, collected today, overdue today, alerts open, jobs running) — tabular, count-up on load, pulse on live change, each with a 40px sparkline.
- **Row 1 (the watch grid):** attendance matrix heatmap (§5.5 — classes × weeks, worst-first) in the primary column (3fr), the 24h heat band + live activity timeline (1fr) beside it.
- **Row 2:** goal strips (§8) for active term goals; the low-attendance list collapses into the matrix drill-down.
- **Command bar:** `⌘K` from anywhere; the bar accepts `/attendance`, entity names, and function codes (§10).
- **Motion budget:** the floor loads as a single `Fade` (no per-room heroics); KPIs count up; charts draw once; everything after is live pulses. Total first-paint of data ≤ 500ms after fetch.

### 9.2 Analytics Hub — the navigator
Redesigns the current gradient-card page: a **1D terminal grid** — one row per analytics domain (Attendance, Financial, Student, Academic, Teacher, Predictive) with its own sparkline, status chips (amber count), and a "quick view" strip of its top 3 rooms. No marketing tiles, no gradients (§0). Domain rows are keyboard-navigable.

### 9.3 Attendance Analytics
- **Command bar:** academic year → class → section → granularity (the current cascade, kept — it is correct), plus a **threshold slider** for the alert band.
- **Rooms:** KPI strip (records, present, absent, late, attendance % — the % gets the goal arc vs the class target); **attendance trend** (line+area, §5.1) with a threshold rule at the alert band; **status distribution** (donut, §5.6 without the goal arc); **class comparison** (the matrix heatmap, §5.5, replacing the flat bar chart — this is the scan surface); **term attendance** (sparkgrid, §5.11, replacing the plain table); **low-attendance alert** (kept as a split-card with amber rail, deep-linking to each student's 360).
- **Drill path:** matrix cell → class+week detail → the day's rows → student 360. ≤3 clicks (§6.2).

### 9.4 Financial Analytics
- **Rooms:** KPI strip (collected this term, outstanding, overdue, recovery %, collection goal arc); **collections vs dues** (composed bar+line §5.2 — this is the spine); **overdue aging** (distribution histogram §5.10 with the 30/60/90 rules as threshold lines); **payment-method mix** (donut); **class-wise recovery** (bullet grid §5.7, one bullet per class); **fee-type performance** (sparkgrid).
- **Comparison:** this term vs last term is one click (§6.4) — the composed chart overlays the previous term dashed.
- **Drill path:** bar → that month's transactions (ledger); aging bin → the specific overdue dues; bullet → that class's recovery ledger.

### 9.5 Student Analytics
- **Rooms:** enrollment trend (line+area §5.1); cohort composition (stacked bar §5.3 — grades, sections); demographics (distribution §5.10); **attendance × grades quadrant** (§5.9 — the intervention lens); retention/survival (line, first-year dropout). 
- **Drill path:** quadrant point → that student's 360 (inspector follows arrow keys — the App Redesign T.3 pattern); a brushed quadrant region → a side sheet of those students with a bulk-action bar.

### 9.6 Teacher Analytics
- **Rooms:** workload vs class size quadrant (§5.9); **teacher attendance** (calendar heatmap §5.4); class performance by teacher (matrix heatmap — rows = teachers); subject pass-rate distribution (§5.10); teacher 360 panels embed the same rooms at their own scale.
- **Drill path:** matrix row → teacher's class list → class detail.

### 9.7 Academic Analytics
- **Rooms:** subject performance (sparkgrid: subject, avg grade, pass %, trend); grade distribution (§5.10) with mean/median ticks; **academic structure** (funnel §5.8 — classes → sections → students); timetable utilization (24h heat band §5.13, rooms vs hours).

### 9.8 Predictive Analytics (Risk + forecast)
- **Rooms:** **risk quadrant** (§5.9 — risk score × recency, the existing Risk Center findings feed the points); **forecast lines** (attendance %, fee completion — actual solid + forecast dashed with confidence band, the Compass's §6.3 "draw" on the forecast segment only); **predicted low-attendance funnel** (§5.8 — who will breach the threshold at the current pace); the alert queue keeps its severity-sorted list.
- **Posture:** every forecast is paired with its confidence and its *basis* ("based on 30-day pace"). A predictive chart without a "why" is rejected.

### 9.9 Portal-facing analytics (student & parent)
Deliberately **not** the terminal: single-column rooms, 16px type, 44px targets, friendly summaries — the App Redesign L-series rules. A student sees their own attendance trend, fee status, and goals (e.g., attendance to next report card). The same chart types render at 1.5× comfort with no terminal features.

---

## 10. The terminal layer

Power features that make the Watchtower feel like an instrument, not a website.

- **Analytics command bar** (`/` from anywhere, `⌘K` second tab): summon a room, a domain, an entity. Examples: `/attendance`, `/fees class:7A`, `STU:1042`, `TCH:31`, `7A` (a class), `94%` (a threshold search).
- **Function codes** (the terminal's `WEI`): each room has a 2–4 letter code shown in its footer — `ATT-TRND`, `FIN-COLL`, `RISK-MTX` — usable in the command bar and shareable as deep links (`/analytics/finance?view=FIN-COLL&w=1Y&c=1`).
- **Saved views:** a view = domain + filters + windows + comparison + fullscreen layout + sort. Saved in the nav persistence store (the `useNavPersistence` pattern), shareable as links. `⌘S` saves the current room state.
- **Keyboard map (analytics):**
  - `[` `]` — window out/in · `0` — reset zoom
  - `↑↓←→` — move hover/selection in grids, matrices, and sparkgrids
  - `Enter` — drill into the selected element · `⇧Enter` — open underlying rows
  - `C` — toggle comparison · `⛶` (`F`) — fullscreen · `E` — export menu
  - `Esc` — close surface / reset · `?` — analytics shortcuts sheet (reuse the existing dialog)
- **Watchlist:** in fullscreen, `+` adds the current room to the personal monitor (§6.5) — the multi-monitor Bloomberg grid as a saved, personal dashboard.

---

## 11. Motion & states (extending the Compass)

| Surface | Move (Compass spec) | Notes |
|---|---|---|
| Room first render | `Fade, D2, I1` | Rooms never parade; the floor is one fade |
| Chart draw-in | `Draw` (lines L→R, bars from baseline), 500ms `slowest`, `ease.enter` | First render only; window changes are 160ms crossfades |
| KPI count-up | `slower`→`slowest`, `ease.enter`, tabular, ≤500ms | The legal ceiling |
| Live value arrival | one `Pulse` (§7) | One pulse per moment, never the whole room |
| Changed cell/row | status wash, 180ms one-shot | The changed thing pulses, not the row |
| Drill surface | `Slide E, D2`, `slow` | Back is the reverse |
| Matrix row re-sort | FLIP, `slow` | Compass §6.4 |
| Fullscreen enter/exit | chrome fades `fast`; rooms crossfade 160ms | The OS owns the window physics |
| Comparison toggle | crossfade 160ms | Never a replot |
| Skeleton (rooms) | mirrors the room's shape, `fast` fade in, 1.6s shimmer loop | Corridor §6.11 |
| Empty / error | Corridor §13.2 / §13.3 states in the room | Never an empty frame |

**Performance contract:** charts animate transform/opacity and `d` path data only; ≤8 concurrent animated elements; the crosshair and range brush are their own layer; live rooms cap at 30fps of *updates*, not rerenders — the SSE handler writes to the readout, it does not re-render the chart for every tick.

---

## 12. Density

- **Comfortable** (default): rooms breathe; gridlines at `ink.200`; readout `text-xl`.
- **Compact** (fullscreen, or user setting): 8px denser padding, `caption` axis labels, readout `text-lg`, sparkgrid row height 36px, matrix cells 12px.
- Density is a **user setting** with a per-room override; it animates via transform (`base`, 180ms — the Corridor's §16 rule), never as an emergency mode.

---

## 13. Accessibility

- **The chart is never the only signal.** Every room has a screen-reader summary in its header (`aria-label`: "Attendance percentage, 94.2%, up 2.1 from last week") and **the data is always available as rows** — "View underlying rows" doubles as the accessible data table.
- **Charts ship with a data table** (visually hidden or expandable) — the a11y floor is a table, not an image.
- Color is never the sole encoder: series carry dash/pattern variants where meaningful; status always pairs with a glyph (▲/◆/⦿) and text (§4.3).
- Keyboard parity for every interaction: hover → focus (arrow keys move a focus crosshair), click → Enter, zoom → `[`/`]`, comparison → `C`, fullscreen → `F`.
- Motion is fully tiered: the Compass's `efficient` tier keeps crossfades and washes, `minimal` removes all chart animation (draw-in, pulse, count-up → instant). Chart draw-in must never block reading — the data is visible at first paint, the draw is an enhancement.
- `prefers-reduced-transparency` removes the backdrop blur on fullscreen overlays and the wash pulses.

---

## 14. Implementation map

**Chart engine:** Recharts v3 (already installed). Build a **`components/charts/`** layer — thin, typed wrappers that encode this spec so charts are never authored ad hoc:

| New file | Encodes |
|---|---|
| `charts/ChartRoom.tsx` | the frame (§2): header, readout, window presets, compare/fullscreen/export, footer provenance |
| `charts/ChartAxes.tsx` | gridlines, axis ticks, typography, scale rules (§3) |
| `charts/ChartColors.ts` | `dv.*` token map + status language (§4) |
| `charts/TimeSeries.tsx` · `ComposedChart.tsx` · `StackedBars.tsx` | §5.1–5.3 |
| `charts/CalendarHeatmap.tsx` · `MatrixHeatmap.tsx` · `HeatBand.tsx` | §5.4, §5.5, §5.13 |
| `charts/GoalArc.tsx` · `BulletChart.tsx` | §5.6, §5.7 (goal tracking §8) |
| `charts/Funnel.tsx` · `Quadrant.tsx` · `Distribution.tsx` | §5.8–5.10 |
| `charts/Sparkgrid.tsx` | §5.11 (dense monitor table) |
| `charts/ActivityTimeline.tsx` | §5.12 |
| `charts/useChartZoom.ts` · `useLiveFloor.ts` | range brush/zoom (§6.3), SSE live floor (§7) |
| `charts/AnalyticsCommandBar.tsx` | §10 command bar + function codes |

**Replace, in order (each is an independent PR):**
1. `components/analytics/*` — the five existing charts (attendance trend/status/comparison, collection trend, student distribution) become thin compositions of the new layer; hardcoded hexes die here.
2. `components/analytics/kpi-card.tsx` → the KPI room with sparkline + delta chip + count-up (Corridor §12.4 `kpi` card).
3. `pages/analytics/*` — attendance, academic, finance, students pages migrate room-by-room.
4. `pages/school-finance/dashboard.tsx` and `pages/command-center/command-center.tsx` — the two flagship floors (§9.1, §9.4).
5. `pages/analytics/analytics-hub.tsx` → the terminal navigator (§9.2).
6. Live floor (SSE) behind a feature flag; predictive rooms behind the existing Risk Center data.

**Sequencing:** ChartRoom + ChartAxes + ChartColors first (the grammar), then the five §5.1–5.3 primitives, then the heatmaps and goal tracking, then the dashboards. The command bar and watchlist are last — they are power features that depend on everything else being solid.

---

## 15. Acceptance criteria

- Any number on any dashboard is reachable from raw rows in ≤3 clicks or ≤6 keystrokes.
- The morning scan (Command Center) conveys the school's state in 8 seconds without reading a single label twice.
- Zero hardcoded chart colors remain in `components/analytics` and `pages/*`.
- All chart motion respects the Compass tiers; no chart animates on every window change or live tick.
- Every chart room has an accessible summary and a data-table fallback.
- The 1M window renders 40+ class rows in the matrix heatmap at a stable 60fps on a mid-range laptop.

---

*The Watchtower is the view from the top of the school. It watches, it investigates, it decides — and it never gets in the way of the data it is showing.*
