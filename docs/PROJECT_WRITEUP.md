# Helios — Real-time anomaly detection with SHAP-grounded LLM reports

> A deep dive into what was built, what was deliberately *not* built, and
> the engineering reasoning behind every interesting choice. This doc is
> the long form of the README — about a 15-minute read. The TL;DR table
> at the end is the elevator pitch.

## The problem

Microservices generate huge volumes of operational telemetry, and 99.9%
of it is uninteresting. Reading every log line is impossible; threshold
alerts ("page me when P99 > 500ms") miss novel failures and fire too
often on known-good traffic shifts. The interesting questions are:

1. Which one-minute window in this service looks *unusual* relative to
   the past few weeks?
2. *Why* does it look unusual — what specifically pushed our score down?
3. *What should the oncall engineer do about it?*

Helios answers all three for a single service at a time, in real time:

- **(1) Detection** — A scikit-learn `IsolationForest` scores every
  one-minute window of events per service. Twelve hand-engineered
  features (latency percentiles, error rates, log-scaled volumes, ratios)
  go in; a single anomaly score comes out. Threshold is derived from a
  validation-set F1 sweep, not hand-picked.
- **(2) Explanation** — Every anomaly is run through SHAP
  (`TreeExplainer`) to attribute the score back to its top three
  features. The attributions ride along inside the Kafka alert, get
  stored in the `anomalies` table's JSONB column, surface in Grafana,
  and are injected into the LLM prompt that generates the report.
- **(3) Action** — An LLM (Gemini 1.5 Flash by default, Claude as a
  configurable alternative) consumes the alert + SHAP context + recent
  service events, and produces a Pydantic-typed `IncidentReport`:
  executive summary, root-cause hypothesis (constrained to reference at
  least one SHAP feature by name), tiered recommended actions,
  monitoring follow-up. Rendered to markdown and PDF.

The whole pipeline is event-driven, Kafka in the middle. Detection and
reporting run as independent consumers; either can scale out or be
restarted without coordinating.

## Architecture in one diagram

```
events POST                  topic: events                    topic: anomaly-alerts
  ┌──────────────┐  ─────►  ┌────────────────────┐  ─────►  ┌────────────────────┐
  │ Ingestion    │  produce │ Detection consumer │ produce  │ Reporting consumer │
  │ (Go, FastAPI)│          │ (Python)           │          │ (Python)           │
  └──────────────┘          │                    │          │                    │
        │                   │ - 12-feature pipe  │          │ - Gemini  ┐        │
        ▼                   │ - IsolationForest  │          │ - Claude  │── Pydantic
  ┌──────────────┐          │ - SHAP TreeExpl.   │          │ - Mock    ┘  IncidentReport
  │ Storage      │ ◄──────  │ - Drift metrics    │          │ - PDF render        │
  │ writer (Go)  │          └────────────────────┘          └────────────────────┘
  └─────┬────────┘                                                    │
        ▼                                                              ▼
  ┌──────────────┐  ◄────────────────  Prometheus  ◄────────  Grafana
  │ TimescaleDB  │                       │                      │
  │ (hypertables)│                       └──── alerts ───── AlertManager
  └──────────────┘
```

13 containers total. Local bring-up is one command (`python scripts/demo.py`),
which runs `docker compose up -d --wait`, seeds 7 days of historical
data, launches a background anomaly generator, and opens Grafana.

## Why Isolation Forest

For tabular operational metrics with no labeled anomalies and frequent
non-stationarity, the practical short-list is:

- **Statistical thresholds (Z-score, IQR)** — fast, no training, but
  brittle to seasonality and miss multivariate patterns ("normal
  latency but normal *only* if traffic is also low").
- **Isolation Forest** — unsupervised, robust to mixed scales, fast to
  train (CPU-only, <30s on the full synthetic dataset), explainable
  via SHAP `TreeExplainer`.
- **Autoencoders / LSTMs** — captures temporal structure but needs GPU
  for training, much more data, and SHAP doesn't apply cleanly.
- **Prophet** — strong on seasonal univariate time series; awkward for
  multivariate operational data and requires per-stream tuning.

For a single-developer project that needs to *work*, *explain itself*,
and *fit on a free-tier ARM VM*, Isolation Forest is the right pick.
Prophet was scaffolded earlier in the project's history and deliberately
deleted — three pages of imports, zero production calls. See Phase 1 in
the commit history.

## Feature engineering — 12 features by design

The features are deliberately hand-engineered, not learned, so the SHAP
attributions are interpretable to a human SRE:

| Feature | Why it's useful |
|---|---|
| `event_count` | Volume — anomalies often appear as spikes or drops |
| `error_rate` | Fraction of ERROR/CRITICAL events |
| `p50/p95/p99_latency_ms` | Latency distribution shape |
| `latency_std` | Tail behaviour |
| `hour_of_day` | Captures business-hours vs nights/weekends seasonality |
| `p95_p50_ratio`, `p99_p95_ratio` | Distribution skew — catches "median fine, tail blown up" |
| `error_count`, `log_event_count`, `log_error_rate` | Log-scaled and absolute counterparts so the IF sees both magnitudes and ratios |

The same pipeline runs in training, evaluation, and live inference
(`services/detection/app/ml/feature_engineering.py`). Drift between
those three would silently destroy precision — having one extractor
keeps them honest.

## Evaluation — where most "ML projects" fall apart

The project originally evaluated on synthetic data the same script
generated. That's not evaluation; that's saying "I memorised the answer
key." Phase 2 replaces it with held-out splits of two public labeled
benchmarks:

- **NAB (Numenta Anomaly Benchmark, *Neurocomputing* 2017)** — 58
  univariate real-world streams: AWS CloudWatch metrics, ad-exchange
  traffic, Twitter mention rates, road traffic. The most-cited
  streaming anomaly benchmark.
- **SMD (Server Machine Dataset, OmniAnomaly KDD 2019)** — 28 real
  server machines × 38 metrics each, per-timestep human-labeled
  anomalies. Closer to actual production observability data.

Adapter: each raw value is treated as one event's "latency", windowed,
and run through the same 12-feature pipeline. Per-stream z-score
normalisation handles the wild scale differences between NAB streams
(CPU% 0–100 vs Twitter mentions 0–50,000). `error_rate` becomes a
two-sided "fraction of |z| > 1.96" proxy — catches up-spikes and
drops.

### Results

| Dataset | F1 | Precision | Recall | FPR | PR-AUC | ROC-AUC | Threshold |
|---|---|---|---|---|---|---|---|
| **NAB** | 0.326 | 0.338 | 0.314 | 0.063 | 0.276 | 0.635 | +0.10 |
| **SMD** | 0.327 | 0.274 | 0.405 | 0.052 | 0.369 | 0.810 | +0.06 |

Streams (NAB) / machines (SMD) are split 60/20/20 by identity into
train / validation / test. **Held-out test streams are never seen
during training or threshold selection.** Threshold per dataset is the
F1-maximising value over a sweep from −1.0 to +0.5 on the validation
set.

### How to read these numbers honestly

- **F1 around 0.33 on NAB** is competitive with published Isolation
  Forest baselines. State-of-the-art on NAB (Numenta's HTM Java
  implementation) scores in the 0.40s after years of tuning; deep
  models like OmniAnomaly score 0.45–0.50 on NAB. Generic Isolation
  Forest *without* dataset-specific tuning typically lands 0.25–0.35.
- **ROC-AUC 0.81 on SMD** is the more telling number. SMD anomalies
  have clearer multivariate signal; the model picks up substantial
  separability without ever being trained on the dataset.
- **Both PR-AUCs > 0** means we're meaningfully above random; NAB's
  anomaly class is very imbalanced (~4% positive), so PR-AUC of 0.28
  is a 7× lift over chance.
- **FPRs around 0.05** are the operationally relevant numbers — at the
  chosen threshold, the model fires false alarms on 5–6% of normal
  windows. For a system processing one window per service per minute,
  that's the difference between an SRE who trusts the alerts and one
  who doesn't.

The model card (`models/evaluation/model_card.md`) is Google-style:
intended use, training data, evaluation data, per-dataset metrics,
ethical considerations, and an explicit limitations section. The
production threshold in the detection service is loaded from
`models/evaluation/results.json` at startup so eval drives production —
not the other way around.

## SHAP — the per-anomaly explanation

`TreeExplainer` on the trained `IsolationForest`, fed a 100-row scaled
training sample as the background distribution. The explainer is built
lazily on the first anomaly and cached. Per-anomaly attribution cost is
in the low single-digit milliseconds; `helios_shap_inference_seconds`
makes that visible in Grafana.

Each alert carries the top three features by `|SHAP|`, each tagged
`toward_anomaly` (negative SHAP — pulls the IsolationForest score lower)
or `toward_normal` (positive SHAP). Those attributions flow through:

1. The Kafka `anomaly-alerts` payload (downstream consumers see them).
2. The TimescaleDB `anomalies.features` JSONB column (Grafana queries
   them).
3. The LLM prompt (the report's root-cause hypothesis is *constrained*
   to reference at least one SHAP feature by name).
4. A Grafana panel on the master dashboard, "Recent Anomalies — Top
   SHAP Feature".

So when a recruiter reads a sample report and sees `"the dominant SHAP
contributor is p99_latency_ms (SHAP −1.44) ... the latency-tail
signature without a corresponding increase in event_count is the
classic fingerprint of a downstream dependency slowing down"`, that's
the model attributing its own decision in a way the LLM was forced to
ground in the actual feature math, not in generic SRE boilerplate.

## LLM layer — provider-portable structured output

Both Gemini and Claude target the same Pydantic `IncidentReport` schema
(`services/reporting/app/generators/structured_output.py`):

```
IncidentReport
├── incident_id, service, detected_at, severity, confidence
├── executive_summary       (oncall-pager-sized overview)
├── root_cause_hypothesis   (must reference a SHAP feature by name)
├── contributing_features[] (auto-populated from the detection alert)
├── recommended_actions[]   (immediate / short_term / long_term)
└── monitoring_checks[]
```

- Gemini uses the SDK's native `response_schema=IncidentReport`
  constraint, guaranteeing the response parses back into the schema.
- Claude is prompted to emit JSON-only and parsed defensively (strips
  ``` fences if present, falls back to free-text wrapping on bad JSON).

Both providers track tokens used and cost (in USD) per report. Both are
selectable via `REPORT_GENERATOR_MODE=gemini|claude|mock`. Mock is a
first-class option — when no API key is set, the system renders a
templated report from the same Pydantic shape, so the demo never
silently fails.

The markdown rendering is identical regardless of which provider ran —
`IncidentReport.to_markdown()` is the single source of truth. A saved
report from Gemini and a saved report from Claude are byte-identical in
structure; only the prose content differs.

## MLOps observability — three layers of drift

`docs/MLOPS.md` covers this in operational depth. The short version:

1. **Score-distribution monitoring (live)** —
   `helios_model_prediction_score` is a Prometheus histogram updated
   every time the consumer scores a window. The model-health dashboard
   renders it as a heatmap and overlays the 1h vs 24h median. The
   **PredictionScoreShift** alert fires on >50% median divergence —
   the cheapest, earliest drift signal.

2. **Per-feature PSI (scheduled)** — `scripts/drift_check.py` computes
   Population Stability Index per feature against the training
   distribution. Quantile bins from the reference, two-sided cutoffs
   (PSI < 0.10 ok / 0.10–0.25 minor / > 0.25 major). Outputs JSON +
   PNG per-run plus a stable `latest/` pointer. Exit code 1 on major
   drift — slots into cron / CI. Smoke-tested across `--simulate
   none|minor|moderate|severe`; latency features show PSI 2–4 on
   moderate, 5–12 on severe.

3. **Model freshness (load-time)** —
   `helios_model_prediction_age_days` is a gauge set from the
   training timestamp in `model_config.json`. The **StaleModel** alert
   fires at 30 days. Fail-loud safety net for the "everything looks
   healthy but the model is six months old" case.

The model-health dashboard (`config/grafana/dashboards/helios-model-health.json`)
gives all three a single pane: lifecycle stats, score-distribution
heatmap, per-feature PSI bar gauge, live feature quantiles, SHAP
top-feature frequency, and the recent-anomalies SHAP context table.

## Things deliberately not built

- **Custom React frontend.** Started, scaffolded, found that the
  hook files it depended on didn't exist. Two paths: spend two weeks
  completing it, or accept that Grafana is a better UI for an MLOps
  story. Picked the second; deleted the React code. Engineering decisions
  on a portfolio project should optimise for honest signal, not surface
  area.
- **Prophet / ensemble detectors.** Scaffolded earlier in the project's
  life as files that imported each other but were never called by the
  live consumer. Same call: delete rather than complete. The model card
  reflects only what runs.
- **Kubernetes + Terraform.** The repo previously had a `.github/workflows/deploy.yml`
  targeting EKS, with no actual manifests. That's exactly the kind of
  CV-padding a senior reviewer immediately spots. Replaced with a real
  `ci.yml` that lints, tests, and builds; deploy story is
  `docker compose` on Oracle Cloud Always Free, documented in
  `docs/DEPLOY.md`.
- **Concept drift via feedback labels.** Helios has no ground-truth
  labels for production anomalies (no oncall feedback loop yet), so the
  drift monitoring is purely *data* drift. The way to add it is a small
  UI on top of the `anomalies.is_resolved` column; documented as an open
  improvement in MLOPS.md but not built.
- **Per-service PSI.** Today PSI is computed globally; a sudden shift
  in one service can be masked by stability in the rest. Adding a
  `{feature, service}` label to `helios_feature_psi` is half a day's
  work; documented but not built.

## Limitations a hiring manager should know

I'd rather these be in writing than discovered in an interview:

- **Single-instance.** The system runs as a single instance on a
  laptop and has not been benchmarked at scale. Horizontal scaling would require Kafka
  partition tuning, sticky-consumer assignment, and a careful look at
  the per-service window state in `DetectionConsumer` (currently
  in-memory deques — wouldn't survive a restart).
- **Synthetic training data, public benchmark evaluation.** The model
  deployed in the demo was trained on `SyntheticDataGenerator` output.
  Public-benchmark evaluation gives us defensible *generalisation*
  numbers, but real production deployment would want a retraining pass
  on actual ingest traffic before being trusted.
- **No feedback loop.** Oncall engineers can't tell the system "this
  was a false positive" today. That's the highest-leverage next
  improvement and the natural Phase 8.
- **LLM cost has no hard cap.** Token tracking is in place, but there's
  no daily-budget kill switch. The Gemini free tier (1500 req/day)
  provides an effective ceiling for the demo; a production deployment
  would add an explicit budget cap.

## Stack and scale

| Layer | Choice | Why |
|---|---|---|
| Ingestion | Go 1.21 + Chi router | Goroutine concurrency; non-blocking Kafka producer; per-request latency exported to Prometheus |
| Message broker | Kafka 3.6 + Zookeeper | 10 partitions, snappy compression, two consumer groups |
| Storage | TimescaleDB (PostgreSQL 15) | Hypertables, continuous aggregates, JSONB for SHAP |
| ML runtime | Python 3.11 + scikit-learn 1.3.2 | CPU-only inference; SHAP TreeExplainer integrates cleanly |
| Reporting | Python 3.11 + Pydantic 2.5 | Structured output via google-generativeai (Gemini) + anthropic (Claude) |
| Monitoring | Prometheus 2.47 + Grafana 10.2 | Two dashboards (master + model-health), AlertManager |
| Orchestration | Docker Compose v2 | 13 services, ARM64-compatible, single-command bring-up |
| Deployment | Oracle Cloud Always Free, ARM Ampere | 4 OCPU / 24 GB RAM forever-free; Caddy auto-HTTPS |
| Experiments | MLflow (local file backend) | `mlruns/` browsable in-repo, 6 logged runs |
| CI | GitHub Actions | ruff + pytest + compose-build smoke + drift_check |

## What this project optimised for, in priority order

1. **Honest, reproducible numbers.** Anyone can clone, run
   `python scripts/evaluate.py --dataset both`, and reproduce the
   exact F1/PR-AUC quoted in the README — same seed, same splits.
2. **Code that runs on first read.** Every file in the repo is either
   actively imported or has an explicit role in the demo. Half-finished
   work was deleted, not commented out.
3. **MLOps signal over ML-research signal.** The project isn't trying
   to beat NAB's state of the art (it doesn't). It's trying to
   demonstrate that the candidate can deploy, observe, and operate ML
   in production — features the audit cited as the biggest gap when
   I started.
4. **Free to demo.** Public URL on Oracle Always Free, Gemini free
   tier, no recurring costs ever.

## Reading order (if you have 15 minutes)

1. README — the headline numbers and quickstart.
2. `models/evaluation/model_card.md` — Google-style model card.
3. `docs/sample-incident-report.md` — what the LLM actually produces.
4. `docs/MLOPS.md` — operational decisions, retraining playbook.
5. `scripts/evaluate.py` — the centerpiece script.
6. `services/detection/app/ml/anomaly_detector.py` — the `explain()`
   method is the new bit.
7. `services/reporting/app/generators/structured_output.py` — the
   schema both LLMs target.
8. `docs/DEPLOY.md` — the deployment story end-to-end.

## TL;DR (the one paragraph)

Helios is a real-time anomaly-detection platform: events flow in via
Kafka, a 12-feature Isolation Forest scores one-minute service windows,
SHAP attributes each anomaly's score to its top three features, and a
provider-portable LLM layer (Gemini default, Claude alternative) emits
a Pydantic-typed incident report with a root-cause hypothesis that's
explicitly grounded in the SHAP features. Evaluated on two public
labeled benchmarks (F1 0.326 on NAB, 0.327 on SMD; ROC-AUC 0.81 on
SMD), monitored with three independent drift signals (score
distribution, per-feature PSI, model freshness), deployed publicly on
Oracle Always Free at $0/month. The full repo is 13 containers, one
command to bring up.
