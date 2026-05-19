# Helios MLOps Operations Guide

This document describes how Helios monitors its anomaly-detection model in
production, detects data and concept drift, and decides when to retrain.
It is intentionally short and decision-focused: every section answers a
question an oncall engineer (or a hiring manager) might ask.

## Why this exists

Anomaly detection on operational telemetry has a known failure mode: the
underlying traffic shape changes (new features ship, new services come
online, holiday traffic, infrastructure migrations), and a model trained
on the old distribution slowly stops being useful. The model still emits
predictions — they just drift from being signal to being noise. The
hardest part of running ML in production is noticing that has happened
before users do.

Helios bakes three layers of observability into the runtime so this
failure mode is loud:

1. **Score-distribution monitoring** (cheap, immediate).
2. **Feature drift via PSI** (rigorous, scheduled).
3. **Model freshness** (trivial, fail-loud).

Each layer fires its own Prometheus alert. The alerts route into the same
Alertmanager pipeline as everything else (see
`config/prometheus/alertmanager.yml`).

## Layer 1 — Score-distribution monitoring (live)

Every time the detection consumer evaluates a window, it records the
IsolationForest decision-function score in a histogram:

```
helios_model_prediction_score   (histogram, seconds buckets)
```

The model-health Grafana dashboard
(`config/grafana/dashboards/helios-model-health.json`) renders this as a
heatmap and overlays the 1-hour median vs the 24-hour baseline. A
sustained median shift of >50% triggers the **PredictionScoreShift**
alert defined in `config/prometheus/alerts.yml`:

```promql
abs(
  histogram_quantile(0.5, rate(helios_model_prediction_score_bucket[1h]))
  - histogram_quantile(0.5, rate(helios_model_prediction_score_bucket[24h]))
)
/ abs(histogram_quantile(0.5, rate(helios_model_prediction_score_bucket[24h])) + 1e-9)
> 0.5
```

This is the earliest-warning channel: the score median moves before any
single feature drifts hard enough to trip the PSI threshold. It's also
the cheapest — no separate job, no extra data path.

## Layer 2 — Population Stability Index per feature (scheduled)

PSI is the industry-standard drift metric for tabular ML (originated in
credit-risk modelling; widely adopted in MLOps). For a feature with
quantile-bucket proportions `p_ref` (reference) and `p_cur` (current):

```
PSI = Σ (p_cur - p_ref) · ln(p_cur / p_ref)
```

Conventional cutoffs:

| PSI | Interpretation |
|---|---|
| < 0.10 | No significant change. |
| 0.10 – 0.25 | Minor change, monitor. |
| > 0.25 | Significant shift. Retrain candidate. |

Helios computes PSI with `scripts/drift_check.py`. The script accepts a
real production-features CSV (`--current`) or simulates drift for demos
(`--simulate minor|moderate|severe`). It writes:

```
models/drift/{timestamp}/psi.json         # full PSI report + bin proportions
models/drift/{timestamp}/psi_bars.png     # per-feature bar chart
models/drift/latest/                       # stable pointer for dashboards
```

Exit code is `1` when any feature's PSI exceeds 0.25, so the script
slots cleanly into a cron job or CI step.

**Wiring PSI into Prometheus.** The model-health dashboard reads
`helios_feature_psi{feature="..."}` from Prometheus. Two ways to populate
it:

- **Prometheus pushgateway** (recommended for production). Drift-check
  runs on a cron, pushes the per-feature values to the pushgateway, and
  Prometheus scrapes pushgateway. Add a pushgateway service to
  `docker-compose.yml` and have the script POST the metric. The alert
  rule **FeatureDriftMajor** in `alerts.yml` then fires automatically.
- **Node-exporter textfile collector** (lower-overhead alternative).
  Write a `helios_drift.prom` file under the collector's watched
  directory at the end of each run.

Both approaches are 20-line additions; the script is designed to make
either trivial to bolt on. The dashboard works as soon as the metric
appears.

**Why not push from inside the consumer?** Drift is a property of the
production *distribution*, not any single prediction. Computing it
inline would require accumulating per-feature samples in memory and
periodically dumping them — duplicating what Prometheus's
`helios_model_feature_value` summary already does, but in an ad-hoc
way. Running drift-check against either the summary or the raw events
table keeps the consumer's hot path simple.

## Layer 3 — Model freshness

The detection consumer reads `model_config.json` at startup and exposes:

```
helios_model_prediction_age_days   (gauge, days)
```

The **StaleModel** alert fires if the value exceeds 30 days. This is the
fail-loud safety net for the embarrassing case where everything else
looks healthy because the model has long since stopped reflecting
reality.

## How threshold is chosen (and changed)

The production anomaly threshold is **derived from validation**, not
hand-picked:

1. `scripts/evaluate.py` runs the full pipeline on NAB and SMD held-out
   splits, sweeps the IsolationForest decision-function threshold from
   −1.0 to +0.5, and picks the F1-maximising value per dataset.
2. The chosen threshold is written into `models/evaluation/results.json`.
3. The detection service's `Settings` class reads that file at startup
   (see `services/detection/app/core/config.py`); the `ANOMALY_THRESHOLD`
   env var still overrides if set explicitly.

Concretely: the current production threshold is the NAB-derived value
because NAB's univariate metric streams are the closer analogue to
Helios's per-service operational telemetry. SMD's threshold is logged
for comparison but isn't used by default.

To re-derive the threshold after a retraining or distribution change:

```bash
python scripts/evaluate.py --dataset both --contaminations 0.03 0.05 0.10
# Inspect models/evaluation/results.json, model_card.md, and the PR/ROC plots
# Restart the detection service — it picks up the new threshold on load.
```

## Retraining playbook

The decision tree when drift or freshness alerts fire:

1. **Confirm the signal**. Look at the model-health dashboard. Is the
   score heatmap visibly different from a week ago? Which features
   showed >0.25 PSI? Cross-reference the SHAP top-feature frequency
   panel — is one feature suddenly dominating?
2. **Identify the cause**. Drift is almost never the model's fault. It
   reflects something that changed upstream: a deployment, a new
   service, a traffic-source change. Talk to the team that owns the
   drifted feature before retraining.
3. **Decide: retrain, threshold-tweak, or accept**.
   - If the drift is benign (e.g., a new service was added and its
     traffic looks healthy), retrain on data that includes the new
     regime: `python scripts/train_model.py --grid-search`. Then re-run
     `scripts/evaluate.py` to re-derive the threshold.
   - If the drift reflects a real incident (e.g., a customer is being
     spammed and event_count is permanently 10× higher), don't retrain
     blindly — the model is correctly flagging the new world as anomalous.
     Fix the upstream issue, then re-evaluate.
   - If the drift is moderate (PSI 0.10–0.25) and the alert volume
     hasn't changed, accept and add a note. PSI is sensitive.
4. **Verify**. After retraining, the prediction-age gauge drops to 0
   and the PSI heatmap should turn green within a few drift-check runs.

## Metrics reference

| Metric | Type | Source | Why it exists |
|---|---|---|---|
| `helios_model_prediction_score` | histogram | detection consumer (per-window) | Score distribution; Layer 1 drift signal |
| `helios_model_feature_value{feature}` | summary | detection consumer (per-window) | Live per-feature distribution; input to Layer 2 |
| `helios_model_prediction_age_days` | gauge | detection consumer (load-time) | Model freshness; Layer 3 |
| `helios_feature_psi{feature}` | gauge | `scripts/drift_check.py` via pushgateway | Per-feature PSI; Layer 2 |
| `helios_shap_inference_seconds` | histogram | detection consumer (per-anomaly) | SHAP cost and "did we explain?" rate |
| `helios_anomalies_detected_total{service,severity}` | counter | detection consumer | Anomaly rate by service / severity |

## Files referenced

- `services/detection/app/consumers/detection_consumer.py` — emits all live ML metrics
- `services/detection/app/consumers/metrics.py` — Prometheus metric definitions
- `services/detection/app/core/config.py` — threshold loading from eval results
- `scripts/evaluate.py` — derives production threshold from validation F1 sweep
- `scripts/drift_check.py` — PSI report generator
- `scripts/train_model.py` — retraining entry point
- `config/prometheus/alerts.yml` — drift / freshness / score-shift alerts
- `config/grafana/dashboards/helios-model-health.json` — model-health dashboard
- `models/evaluation/model_card.md` — Google-style model card

## Open improvements

Documented for completeness, not currently implemented:

- **Drift slice analysis.** PSI on the global feature distribution can
  mask service-specific drift. A natural next step is per-service PSI
  (label `{feature, service}` instead of just `{feature}`).
- **Concept drift via prediction-error feedback.** Helios doesn't have
  ground-truth labels for production anomalies, so we can only do
  *data* drift today. A feedback loop (oncall marking false positives
  in a small UI, or pulling resolution flags from `anomalies.is_resolved`)
  would unlock concept-drift tracking.
- **Auto-retrain on alert.** Currently humans run `train_model.py`.
  Wiring the StaleModel alert into a GitHub Actions job that opens a
  retraining PR is a one-day project.
