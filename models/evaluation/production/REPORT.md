# Helios Production Model — Evaluation Report

*Generated 2026-05-27T08:47:05+00:00*  
*Timeline: data\chaos\timeline_20260527T071432Z.json*  
*Eval split: test*

## Dataset

- Total windows: **61**  (19 anomaly, 42 normal, anomaly rate = 31.1%)
- Chaos scenarios: **5**

## Threshold-dependent metrics

At deployed threshold = **+0.000**:

| Metric | Value | Grade |
|---|---:|:---:|
| Precision | 1.000 | GOOD |
| Recall | 0.842 | GOOD |
| F1 | 0.914 | GOOD |
| F2 (recall-weighted) | 0.870 | GOOD |
| Specificity (TNR) | 1.000 | GOOD |
| False Positive Rate | 0.000 | GOOD |
| MCC | 0.887 | GOOD |
| Balanced Accuracy | 0.921 | GOOD |

Confusion matrix: TP=16  FP=0  TN=42  FN=3

## Threshold-independent metrics

| Metric | Value | Grade | Note |
|---|---:|:---:|---|
| **PR-AUC** | 0.980 | GOOD | preferred for imbalanced data |
| **ROC-AUC** | 0.987 | GOOD | overall ranking quality |
| Best F1 (any threshold) | 0.914 @ +0.000 | GOOD | upper bound of F1 |
| Baseline (random) PR-AUC | 0.311 |  | model must exceed |

## Per-scenario-type recall

| Type | Recall | Grade |
|---|---:|:---:|
| cascading_timeout | 1.000 | GOOD |
| dependency_failure | 0.250 | POOR |
| latency_spike | nan | n/a |
| partial_outage | 1.000 | GOOD |

## Detection latency

- Median latency: **-33.0s** (-0.6 min) — GOOD
- P90 latency: **84.6s** (1.4 min)
- Scenarios caught: 3/5

## Operational metrics

- Clean-period false alarms: **0** in 42 normal windows = 0.00/hour
- Mean score during anomaly windows: -0.069
- Mean score during normal windows: +0.043
- Score separability (mean diff / pooled std): 3.27σ

## Verdict

- **WORKS WELL.** PR-AUC 0.980 significantly above random (0.311), F1 0.914, ROC-AUC 0.987.
- Low false-alarm rate (0.0/hour) — operationally clean.
- Fast detection: median latency -33s — alerts fire within 1-2 windows of incident onset.
- Reliably catches: cascading_timeout, partial_outage.
- Struggles with: dependency_failure (recall < 0.5). These chaos types don't perturb the feature distribution enough on this test split (most of that scenario falls in validation; only the tail edge lands in test).
- Strong class separation: anomaly scores are 3.3σ from normal — clear decision boundary.

## Plots

- `roc.png` — ROC curve
- `pr.png` — Precision-Recall curve
- `score_histogram.png` — Score distribution by class
- `per_scenario_recall.png` — Recall per chaos scenario type
- `detection_latency_cdf.png` — Detection latency CDF
