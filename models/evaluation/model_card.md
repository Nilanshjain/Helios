# Helios Anomaly Detector — Model Card

*Generated 2026-05-19T10:04:06+00:00*

## Model details

- **Architecture:** scikit-learn `IsolationForest` with `StandardScaler`.
- **Feature pipeline:** 12 features, identical to `services/detection/app/ml/feature_engineering.py`: event_count, error_rate, p50_latency_ms, p95_latency_ms, p99_latency_ms, latency_std, hour_of_day, p95_p50_ratio, p99_p95_ratio, error_count, log_event_count, log_error_rate.
- **Threshold:** chosen per dataset by sweeping decision-function thresholds on the validation split and picking the value that maximises F1.

## Intended use

Detect anomalous windows in operational telemetry (event counts, error rates, latency percentiles) for the Helios observability platform. Out of scope: fraud detection, security intrusion detection, root-cause inference (SHAP feature attribution is provided separately by `app/ml/explainability.py`).

## Evaluation data

Two public, labeled benchmarks:
- **NAB** (Numenta Anomaly Benchmark, Neurocomputing 2017): 58 univariate real-world streams (AWS CloudWatch, ad exchange, Twitter mentions, traffic).
- **SMD** (Server Machine Dataset, OmniAnomaly KDD 2019): 28 server machines × 38 metrics × per-timestep labels.

**Adapter:** raw values were mapped into Helios's 12-feature window schema by treating each value as one event's `latency_ms`. `error_rate` was proxied by the fraction of values exceeding the 95th-percentile cutoff of the training streams (computed once, applied to val and test — no label leakage). For SMD's multivariate streams, all (timestep, metric) values in a window were pooled before percentile computation.
**Splits:** streams (NAB) / machines (SMD) shuffled with seed and split 60% train / 20% validation / 20% test. Held-out test streams are never seen during training or threshold selection.

## Performance

| Dataset | F1 | Precision | Recall | FPR | PR-AUC | ROC-AUC | Threshold | Test windows |
|---------|------|-----------|--------|------|--------|---------|-----------|--------------|
| NAB | 0.326 | 0.338 | 0.314 | 0.063 | 0.276 | 0.635 | +0.10 | 2404 |
| SMD | 0.327 | 0.274 | 0.405 | 0.052 | 0.369 | 0.810 | +0.06 | 6021 |

## Limitations

- Public benchmark performance is a proxy for production behaviour. NAB streams are mostly single-metric system telemetry; SMD is multivariate but its anomaly labels are inherently noisy (human-labeled by SREs). Production Helios sees 12-feature windows over real Kafka event streams — performance there may differ.
- The `error_rate` adapter is a self-supervised proxy (values above 95th percentile of training). On true Helios traffic this feature is computed from `level=ERROR|CRITICAL` event ratios, which is a different signal.
- Isolation Forest is unsupervised: the chosen threshold reflects a validation-set operating point. Production should re-derive the threshold from its own labeled incidents (see `docs/MLOPS.md` for the retraining process).

## Reproducibility

```bash
python scripts/evaluate.py --dataset both
```

Artifacts: `models/evaluation/results.json`, per-dataset PR/ROC/confusion PNGs, MLflow experiments under `mlruns/`. The chosen production threshold is loaded from `results.json` at service startup (see `services/detection/app/core/config.py`).
