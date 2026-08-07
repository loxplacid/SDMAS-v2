# SDMAS - Relationship Intelligence System

This document describes the **intended** relationship-intelligence layer for
SDMAS v2 — the automatic detection of duplicates, fraud, attendance/fee
anomalies, cheating/bullying clusters, teacher favoritism, social clusters,
hidden relationships, and graph-based recommendations.

It inherits the deterministic design philosophy established by
`domains/risk` (see `risk/rules.py`, `risk/evaluator.py`) and reuses two
existing foundations rather than reinventing them:

- **`docs/GRAPH_LAYER.md`** — the campus-scoped entity graph (networkx,
  PageRank, community detection, derived `FRIEND_OF` edges).
- **`domains/risk`** — the deterministic rule engine, findings lifecycle
  (open → acknowledged → resolved) and severity banding.

Status: **design spec with a working core.** Five detectors are implemented
and tested end-to-end; the rest are spec-only roadmap items. Not yet wired
into the API.

Implementation status:

| Piece | State |
|---|---|
| Entity graph + similarity + stats primitives (`intelligence/graph.py`, `similarity.py`, `stats.py`) | Implemented |
| Seeded IsolationForest + DBSCAN + label-propagation + PageRank wrappers (`clustering.py`, `isolation.py`) | Implemented |
| Evidence scoring + findings (risk-shaped) (`scoring.py`) | Implemented |
| Detector registry + metadata (`rules.py`, `detectors/`) | Implemented |
| Detector: duplicate students (blocking + similarity) | Implemented |
| Detector: attendance anomaly (robust z-score + isolation-forest consensus) | Implemented |
| Detector: cheating cluster (DBSCAN/hamming over answer sheets) | Implemented |
| Detector: teacher favoritism (rule engine with ability control) | Implemented |
| Detector: social cluster (label propagation + PageRank centrality) | Implemented |
| Detection pipeline: orchestration, dedupe, noise floor, report (`pipeline.py`) | Implemented |
| Detectors: duplicate parents, fee anomaly, fraud, bullying cluster, hidden relationships, recommendations | Spec only |
| Scheduling (cron), human review queue, visualization feeds, tenancy guards, API router, outbox ingestion | Spec only |

## 1. Purpose & scope

The system answers the question *"which records, people and groups deserve a
human's attention?"* across eleven detection types:

| # | Detection | Category | What it looks for |
|---|---|---|---|
| 1 | Duplicate students | duplicate | two student records that are the same person |
| 2 | Duplicate parents | duplicate | guardian records that are the same person across families |
| 3 | Fraud | integrity | ghost students, fabricated documents, payment diversion |
| 4 | Attendance anomalies | anomaly | students deviating from their cohort's attendance pattern |
| 5 | Fee anomalies | anomaly | unusual payment amount/timing/reversal patterns |
| 6 | Cheating clusters | cluster | answer sheets with statistically implausible agreement |
| 7 | Bullying clusters | cluster | repeated directed-harassment signals forming a directed cluster |
| 8 | Teacher favoritism | integrity | persistently inflated marks beyond the ability control |
| 9 | Social clusters | social | co-attendance / co-enrolment communities |
| 10 | Hidden relationships | social | unstated links inferred from shared contact/bank/address signals |
| 11 | Recommendations | social | co-enrolment affinity + centrality-ranked peer matches (opt-in) |

The output is always a **finding** — an explainable, evidence-scored review
signal for a human queue. Nothing in this layer ever auto-acts, auto-flags a
student publicly, or reaches a family directly.

## 2. Non-negotiables

1. **No accusations — only review signals.** Every detector output lands in
   the human review lifecycle. A cheating-cluster finding says *"these answer
   sheets agree implausibly; please look"*, never *"student X cheated"*.
2. **Deterministic where possible.** Similarity scoring, robust statistics,
   DBSCAN and label propagation are pure functions. The one *learned*
   component — IsolationForest — is made deterministic by a pinned
   `random_state` and single-threaded execution, so identical input produces
   identical output on any machine (see §5.2).
3. **The risk domain owns severity and lifecycle.** Findings reuse
   `severity_from_score` banding and are shaped for the existing
   `risk_findings` open → acknowledged → resolved flow. Integration adds a
   row, not a new paradigm.
4. **False positives are designed out, not tuned away.** Each detector has at
   least one structural guard (consensus, ability control, threshold, noise
   floor) that reduces noise before any human sees a queue.
5. **Tenancy is preserved.** Graphs, findings and queues are campus-scoped the
   same default-deny way as `multi_tenant`. Cross-campus leakage through
   graph traversal is structurally impossible (per `GRAPH_LAYER.md`).
6. **Evidence is inspectable.** Every finding decomposes into named, weighted,
   0-1 normalised evidence items with human-readable detail — the paper trail
   for review and for audit.

---

## 3. Core objects

New package: `apps/api/app/intelligence/`.

```
intelligence/
  graph.py          EntityGraph — campus-scoped networkx projection
  similarity.py     normalize_* / jaro / jaro_winkler / token_jaccard /
                    name_similarity / record_similarity
  stats.py          mean / std / mad / modified_z_score / z_score (robust)
  scoring.py        Evidence, Finding, EvidenceScorer (risk-shaped)
  config.py         DetectorConfig, IntelligenceConfig (thresholds as data)
  rules.py          DetectorDefinition registry + catalog (all 11 types)
  clustering.py     dbscan_clusters, label_propagation_communities,
                    pagerank_rankings, student_community_graph
  isolation.py      isolation_anomaly_scores (seeded, normalised 0-1)
  pipeline.py       DetectionPipeline, PipelineReport
  detectors/        base.py (Detector ABC) + one module per detector
```

### 3.1 Entity graph

A `networkx.MultiDiGraph` bound to one `campus_id`. Nodes are
`(label, entity_id)` — the existing primary key, never a second identity
space (mirrors `GRAPH_LAYER.md`). Edges are typed and weighted, e.g.
`parent_of`, `teaches`, `co_attendance`, `student_id` links inside grade
records.

The pipeline caller builds the graph from persisted records (integration
phases ingest from the graph layer's outbox projection — §9). Detectors read
only this graph; they are pure functions of it.

### 3.2 Findings & evidence

```python
Evidence(metric_id, value, weight, detail)   # value is 0-1 normalised
Finding(rule_code, category, entity_type, entity_id,
        score, severity, reason, recommended_action,
        evidence=(...), status="open")
```

`EvidenceScorer` computes `100 × Σ(weight·value) / Σ(weight)`, clamps to
0-100, banded via the risk domain's `severity_from_score`, and emits
**nothing** below a per-detector `min_score` — the first false-positive
reduction. `Finding.status` is `open` by default; the lifecycle (acknowledge
→ resolve, with reviewer notes) belongs to `domains/risk` in integration.

### 3.3 Configuration

All thresholds and weights are **data, not code**: an `IntelligenceConfig`
seeds defaults per detector (mirroring `risk_rule_configs`) and supports
validated per-detector overrides via `merged(...)` (unknown detector or key
raises). The isolation-forest seed lives here, so a campus can pin or change
reproducibility policy.

---

## 4. Detection pipeline

```
campus records ──► EntityGraph (scoped projection)
                        │
   ┌────────────────────┴─────────────────────┐
   │  DetectionPipeline (stable detector order) │
   └────────────────────┬─────────────────────┘
     per-detector: evidence must clear min_score
     dedupe: one finding per (rule, entity) — strongest wins
     noise floor: global score floor trims weak tails
                        │
                 PipelineReport (counts + sorted findings)
                        │
              human review queue (risk_findings lifecycle)
```

`DetectionPipeline.run(graph)`:

1. **Discovery** — instantiate every *enabled* detector from the registry
   (`DETECTORS`); config toggles map 1:1 to catalog ids.
2. **Detection** — run detectors in stable id order; each returns sorted
   findings with evidence.
3. **False-positive reduction** — three layers: per-detector `min_score`,
   dedupe per `(rule_code, entity_id, group_id)` keeping the strongest
   (a `group_id` keeps distinct events distinct — cheating cluster in exam
   101 vs 102, duplicate pair with partner A vs B), and a global noise floor
   (a safety net below the per-detector minimums, so it only bites when a
   campus configures an aggressive detector).
4. **Report** — `PipelineReport` with counts by category/severity, enabled
   detector list, and the deterministic finding order
   (score desc, rule, entity).

---

## 5. Algorithms

### 5.1 Similarity scoring (entity resolution)

- **Normalisation** — NFKD accent-stripping, lowercasing, punctuation
  collapse for names; digits-only for phones; lower/strip for emails.
- **Jaro-Winkler** — typo tolerance; **token Jaccard** — word-order
  robustness; `name_similarity` takes the best of both.
- **`record_similarity`** — weighted combination over identity-bearing fields
  (name 0.4, guardian 0.2, DOB exact 0.2, address 0.2); missing fields are
  skipped, never zeroed.

### 5.2 Anomaly detection

- **Statistical signal** — robust *modified z-score* (median + MAD) per
  feature column; immune to the outliers it is hunting. `|z| > 3.5` is the
  conventional flag.
- **Model signal** — seeded IsolationForest (`random_state` from config,
  `n_jobs=1`), whose raw scores are min-max normalised to 0-1 "anomaly
  strength".
- **Consensus** — a finding requires *both* signals to agree. That agreement
  is the layer's primary false-positive reduction for anomalies.

### 5.3 Clustering & graph algorithms

- **DBSCAN** (sklearn) with `metric="hamming"` over per-exam answer vectors:
  clusters answer sheets whose answers agree on nearly every position —
  including, crucially, the *wrong* answers, the statistical signature of
  copying. Deterministic (no randomness). Noise points are dropped.
- **Label propagation** — networkx's deterministic greedy
  `label_propagation_communities` (explicitly *not* the random-tie-breaking
  `asyn_lpa` variant).
- **PageRank** — networkx, weighted, deterministic; identifies the most
  central members of a detected community.

### 5.4 Rule engine (favoritism, fraud, hidden relationships)

Rules are pure functions over persisted data evaluated at a point in time —
the same contract as `domains/risk`. Favoritism is the implemented showcase:

1. per exam: class average % (reference distribution);
2. per (teacher, student): average % gap vs that reference;
3. per student: ability proxy = average % in subjects *not* taught by the
   teacher under review.

Fires only when the gap is **persistent** (≥ `min_exams`), **large**
(≥ `gap_threshold`), and the student is **not** a high performer elsewhere
(ability < `ability_floor`) — the ability control separates genuine high
performers from inflated marks.

---

## 6. Evidence scoring & human review

- **Score** — weighted 0-100 (see §3.2); every finding ships its full
  evidence list so a reviewer sees *why* before opening records.
- **Review queue** — findings integrate with the risk domain's lifecycle:
  open → acknowledged → resolved, reviewer notes appended, status
  transitions permission-gated and audited.
- **Feedback loop (spec)** — resolved-as-false-positive findings feed a
  suppression list per (rule, entity, feature signature) so recurring noise
  does not re-queue; escalation thresholds tune detector thresholds per
  campus via `IntelligenceConfig.merged`.

## 7. False-positive reduction (summary)

| Layer | Where | Effect |
|---|---|---|
| Blocking before pair scoring | duplicates | O(n·block) pairs instead of O(n²); only plausible pairs scored |
| Similarity threshold | duplicates | pairs below threshold never become evidence |
| `min_score` gate | every detector | weak evidence emits no finding |
| Statistical + model consensus | attendance anomaly | both signals must agree |
| Ability control | favoritism | high performers elsewhere are not flagged |
| Agreement threshold + min cluster size | cheating / social | only tight, large clusters fire |
| Dedupe per (rule, entity, group) | pipeline | strongest finding wins; distinct events stay distinct |
| Global noise floor | pipeline | weak tails trimmed |

## 8. Scheduling

- **Frequency classes** — cheap detectors (rules, duplicates over new rows)
  run nightly; graph-derived detectors (social clusters, cheating per exam,
  hidden relationships) run after the graph layer's derived-edge projection;
  the isolation-forest pass is capped at nightly for cost.
- **Delivery (spec)** — the worker process picks up a scheduled
  `IntelligenceJob` (mirroring the simulation worker pattern), runs the
  pipeline for each changed campus, and writes findings through the risk
  lifecycle; the API stays responsive.

## 9. Visualization (spec)

Read-only feeds the frontend renders — the client renders only, never
re-figures numbers:

- `GET …/intelligence/{campus}/findings?severity=&category=&status=`
- `GET …/intelligence/{campus}/finding/{id}` — evidence list, entity
  records, review actions.
- `GET …/intelligence/{campus}/graph/neighborhood?node={label}:{id}&depth=2`
  — force-graph JSON for a finding's context (reuses the graph layer's
  visualization exporters: graphml/dot/json).
- Cluster cards render community membership + PageRank centrality directly.

## 10. Performance

- **Pure detectors over a scoped projection** — no live-table scans; the
  graph is built once per campus per run from batched SQL.
- **Blocking** keeps duplicate pair counts linear-ish in practice.
- **Seeded + single-worker IsolationForest** — deterministic and
  CPU-bounded; contamination caps the model pass.
- **Result reuse** — findings for unchanged input are idempotent; the
  scheduling layer can skip a campus whose records are byte-identical
  (snapshot hash), mirroring the simulation engine's approach.
- **Caching (spec)** — plan/result keys in Redis keyed by
  `(campus, detector_set, record_version)`.

## 11. Architecture

```
Web / Mobile ─► /api/v1/intelligence/* (tenancy-guarded, audit)
                     │
        ┌────────────┴──────────────────────────┐
   Pipeline Service                    IntelligenceJob (worker, cron)
        │                                         │
   DetectionPipeline ──► detectors ──► EvidenceScorer
        │                 │
   EntityGraph (networkx, campus-scoped) ◄── graph layer projection / outbox
        │                 │
        │            algorithms: DBSCAN · IsolationForest (seeded) ·
        │            label propagation · PageRank · robust z-score
        ▼
   risk_findings lifecycle (open → acknowledged → resolved, audited)
```

New runtime deps: `networkx` and `scikit-learn` (both already in
`pyproject.toml`; sklearn is worker-process only).

## 12. Roadmap

**Phase 1 – working core (shipped)**
- Entity graph + similarity + stats primitives; seeded IsolationForest,
  DBSCAN, label propagation, PageRank wrappers.
- Evidence scoring + risk-shaped findings; detector registry + catalog.
- Five detectors: duplicate students, attendance anomaly, cheating cluster,
  teacher favoritism, social cluster.
- Detection pipeline with dedupe + noise floor; deterministic test suite.

**Phase 2 – remaining detectors + review loop**
- Duplicate parents, fee anomaly, hidden relationships (blocking/similarity
  extensions), fraud rule set, bullying cluster (directed signals).
- Human review queue integration with `domains/risk` + suppression list.
- Config admin (per-campus threshold overrides).

**Phase 3 – operations**
- Scheduled `IntelligenceJob` worker; per-campus incremental runs keyed on
  record version.
- Graph-layer outbox ingestion (reuse the projection from `GRAPH_LAYER.md`);
  tenancy + audit suites.
- Visualization feeds (finding detail, graph neighborhood, cluster cards).

**Phase 4 – recommendations & scale**
- Opt-in graph-based recommendations (co-enrolment affinity + PageRank).
- Redis result caching; larger-campus batching.

## 13. Testing (determinism guarantee)

Implemented now (`tests/test_intelligence/`):

- **Similarity** — normalisation, Jaro/Jaro-Winkler, token Jaccard,
  weighted `record_similarity` (missing fields skipped, not zeroed).
- **Stats** — MAD / modified z-score robustness (outlier flagged, normal
  point not), zero-spread guard.
- **Algorithms** — DBSCAN/hamming separates tight groups and drops noise;
  isolation scores are seeded (run-twice equality) and normalised 0-1.
- **Detectors** — duplicates find the same-person pair and skip unrelated
  records; attendance flags only the true low-attendance outliers (never the
  majority); cheating cluster fires on implausible answer agreement;
  favoritism fires only with the ability control satisfied; social cluster
  finds the dense community.
- **Pipeline** — runs all enabled detectors, dedupes per (rule, entity),
  sorts by score, counts categories; deterministic across runs; config
  disables detectors; unknown-detector overrides rejected.

Spec only (phases 2–4):

- **Tenancy suite** — `test_intelligence/test_tenancy.py` proving
  cross-campus graph/finding isolation (mirror the multi-tenant security
  suite).
- **No-AI audit** — a lint-style test asserting no detector imports an
  unseeded/stochastic component; the only learned component is the pinned
  IsolationForest.
- **Suppression list tests** — resolved false positives do not re-queue.

## Related docs

- [`GRAPH_LAYER.md`](GRAPH_LAYER.md) — the entity graph this layer reads.
- [`SIMULATION_ENGINE.md`](SIMULATION_ENGINE.md) — sibling deterministic
  engine; shares the worker/caching patterns.
- `apps/api/app/domains/risk/` — severity banding, rules style, findings
  lifecycle reused here.
- [`ARCHITECTURE.md`](ARCHITECTURE.md), [`TENANCY.md`](TENANCY.md)
