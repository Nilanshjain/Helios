# Rule-Based Baseline vs Isolation Forest (v2)

*Generated 2026-05-27T08:47:43+00:00*

## Rule

`flag if (error_rate > 0.050) OR (p95_latency > 2.0*baseline_p95)`

- `baseline_p95` (median across training windows) = **290.6 ms**

- Latency threshold = 581.2 ms


## Side-by-side metrics

| Metric | Rule-based baseline | Isolation Forest (v2) |
|---|---:|---:|
| Precision | 1.000 | 1.000 |
| Recall | 0.800 | 0.842 |
| **F1** | **0.889** | **0.914** |
| Specificity | 1.000 | 1.000 |
| FPR | 0.000 | 0.000 |
| MCC | 0.853 | 0.887 |
| Balanced Accuracy | 0.900 | 0.921 |
| PR-AUC | (binary rule, n/a) | 0.980 |
| ROC-AUC | (binary rule, n/a) | 0.987 |

## Confusion matrices

**Rule-based:** TP=32  FP=0  TN=80  FN=8

**IF (v2):** TP=16  FP=0  TN=42  FN=3

## Interpretation

- **IF roughly matches the rule.** F1 delta = +0.025. The IF still buys you a continuous score (useful for severity / triage) and PR-AUC = 0.980, but the headline F1 isn't a strong selling point.

- Note: the rule is intentionally simple. A tuned version (per-service rolling baselines, exponentially-weighted thresholds, hysteresis) could close more of the gap.