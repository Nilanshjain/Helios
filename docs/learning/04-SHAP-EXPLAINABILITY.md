# 04 - SHAP Explainability for Anomaly Detection

**Goal**: Learn how to explain WHY an anomaly was detected using SHAP values.

**Time**: 2-3 hours (reading + hands-on)

**Prerequisites**: Understanding of Isolation Forest, feature extraction

---

## 🤔 The Explainability Problem

### Current Situation (Black Box):
```
Anomaly Detected!
Service: api-gateway
Score: -0.92
Severity: HIGH
```

**Engineer's Questions**:
- ❓ WHY was this detected?
- ❓ Which metric(s) triggered it?
- ❓ Is it CPU? Latency? Error rate?
- ❓ How do I fix it?

**Current Answer**: 🤷 "The ML model says so"

### With Explainability (Glass Box):
```
Anomaly Detected!
Service: api-gateway
Score: -0.92
Severity: HIGH

TOP CONTRIBUTING FACTORS:
1. error_rate: 15.2% (baseline: 2.1%) → +12.4% impact 🔴
2. cpu_usage: 92% (baseline: 45%) → +8.7% impact 🔴
3. p99_latency: 850ms (baseline: 120ms) → +6.3% impact 🟡
4. db_connection_pool: 98% (baseline: 60%) → +4.1% impact 🟡
5. memory_usage: 48% (baseline: 50%) → -0.2% impact ✅

DIAGNOSIS: High error rate likely caused by CPU exhaustion
and database connection pool saturation.

RECOMMENDED ACTION: Scale up instances or investigate
sudden traffic spike.
```

**Now the engineer knows**:
- ✅ Error rate is the main problem
- ✅ CPU and DB connections are also stressed
- ✅ Memory is fine
- ✅ Clear action: scale or investigate traffic

---

## 🎯 What is SHAP?

**SHAP** = **SH**apley **A**dditive Ex**P**lanations

### Simple Definition:
SHAP tells you **how much each feature contributed** to a specific prediction.

### Analogy: Team Contribution

Imagine a basketball team wins by 20 points. Who contributed most?

```
Player A: +12 points (star player!)
Player B: +8 points (second scorer)
Player C: +2 points (some help)
Player D: 0 points (neutral)
Player E: -2 points (turnovers hurt the team)
```

**Total**: 12 + 8 + 2 + 0 + (-2) = 20 points ✅

SHAP does the same for ML models:

```
Anomaly Score: -0.92 (very anomalous!)

error_rate:     -0.45 (pushed score down = more anomalous!)
cpu_usage:      -0.28 (also pushed down)
p99_latency:    -0.15 (some contribution)
memory_usage:   +0.02 (pushed up slightly = less anomalous)
...other features

Total: -0.45 - 0.28 - 0.15 + 0.02 + ... = -0.92 ✅
```

---

## 🧮 How SHAP Works (Simplified)

SHAP is based on **game theory** (Shapley values from economics).

### The Question:
"If I remove this feature, how much does the prediction change?"

### The Process:

1. **Baseline prediction** (all features average):
   - With all features at average values → score = -0.1 (normal)

2. **Add feature #1 (error_rate = 15.2%)**:
   - New prediction → score = -0.55
   - SHAP value = -0.55 - (-0.1) = **-0.45**

3. **Add feature #2 (cpu_usage = 92%)**:
   - New prediction → score = -0.83
   - SHAP value = -0.83 - (-0.55) = **-0.28**

4. **Repeat for all features**...

(Actual implementation is more complex - averages over all orderings)

### Key Property: **Additivity**
```
Baseline + SHAP₁ + SHAP₂ + ... + SHAPₙ = Final Prediction
```

---

## 📊 Visualizing SHAP Values

### 1. **Waterfall Chart** (Most Useful!)

Shows how each feature pushes prediction from baseline to final value:

```
  Prediction
      │
 0.0  ├─────────────────────── Baseline (average)
      │
-0.2  │
      │
-0.4  │   ↓ error_rate (-0.45)
      │   ███████████████████████
-0.6  │                         ↓ cpu_usage (-0.28)
      │                         ████████████
-0.8  │                                     ↓ p99_latency (-0.15)
      │                                     ██████
-0.9  ├─────────────────────────────────── Final: -0.92 🚨
```

**Reading**: Error rate has the biggest downward push (most anomalous).

### 2. **Force Plot** (Alternative View)

```
            Features pushing TOWARD anomaly (red)
                        ↓
    ┌─────────────────────────────────────────────┐
-0.1│ error_rate  cpu_usage  p99_latency          │
    │ (-0.45)     (-0.28)    (-0.15)         →  -0.92
    │              memory_usage  event_count      │
    │              (+0.02)       (+0.01)          │
    └─────────────────────────────────────────────┘
                        ↑
            Features pushing AWAY from anomaly (blue)
```

### 3. **Feature Importance Bar Chart**

```
error_rate      ████████████████████████████ 0.45
cpu_usage       ██████████████████ 0.28
p99_latency     ████████ 0.15
db_connections  █████ 0.08
cache_hit_rate  ██ 0.04
memory_usage    █ 0.02
...
```

---

## 🛠️ Using SHAP with Isolation Forest

### Installation
```bash
pip install shap
```

### Code Example

```python
import shap
import numpy as np
from sklearn.ensemble import IsolationForest

# 1. Train Isolation Forest (you already have this)
model = IsolationForest(contamination=0.05, random_state=42)
model.fit(X_train)  # X_train shape: (1000, 25) - 1000 windows, 25 features

# 2. Create SHAP explainer (TreeExplainer for tree-based models)
explainer = shap.TreeExplainer(
    model,
    X_train,  # Background dataset (for baseline calculation)
    model_output='raw'  # Use raw anomaly scores
)

# 3. Explain a specific prediction
current_window_features = np.array([[
    150,      # event_count
    0.152,    # error_rate (15.2%!)
    45,       # p50_latency
    350,      # p95_latency
    850,      # p99_latency (high!)
    120,      # latency_std
    14,       # hour_of_day (2pm)
    7.8,      # p95_p50_ratio
    2.4,      # p99_p95_ratio
    22.8,     # error_count
    5.01,     # log_event_count
    5.02,     # log_error_rate
    92,       # cpu_usage (very high!)
    78,       # memory_usage
    98,       # db_connection_pool (saturated!)
    # ... other 25 features
]])

# 4. Calculate SHAP values
shap_values = explainer(current_window_features)

# 5. Get SHAP values for this prediction
shap_array = shap_values.values[0]  # Array of 25 numbers

# 6. Get feature names
feature_names = [
    'event_count', 'error_rate', 'p50_latency', 'p95_latency',
    'p99_latency', 'latency_std', 'hour_of_day', 'p95_p50_ratio',
    'p99_p95_ratio', 'error_count', 'log_event_count', 'log_error_rate',
    'cpu_usage', 'memory_usage', 'db_connection_pool',
    # ...
]

# 7. Create importance ranking
importance = list(zip(feature_names, np.abs(shap_array)))
importance.sort(key=lambda x: x[1], reverse=True)

print("Top 5 Contributing Features:")
for i, (feature, shap_value) in enumerate(importance[:5], 1):
    actual_value = current_window_features[0][feature_names.index(feature)]
    print(f"{i}. {feature}: {actual_value:.2f} → SHAP: {shap_value:.3f}")
```

**Output**:
```
Top 5 Contributing Features:
1. error_rate: 0.15 → SHAP: 0.452
2. cpu_usage: 92.00 → SHAP: 0.283
3. p99_latency: 850.00 → SHAP: 0.154
4. db_connection_pool: 98.00 → SHAP: 0.087
5. cache_hit_rate: 0.25 → SHAP: 0.042
```

---

## 📈 Visualizing SHAP (Interactive)

```python
import matplotlib.pyplot as plt

# Waterfall plot (most informative!)
shap.waterfall_plot(shap_values[0])
plt.savefig('shap_waterfall.png')

# Force plot (horizontal view)
shap.force_plot(
    explainer.expected_value,
    shap_values.values[0],
    current_window_features[0],
    feature_names=feature_names,
    matplotlib=True
)
plt.savefig('shap_force.png')

# Bar chart (feature importance)
shap.bar_plot(shap_values[0], feature_names=feature_names)
plt.savefig('shap_bar.png')
```

---

## 🎯 Integrating SHAP into Helios

### Step 1: Add SHAP to Detection Pipeline

**File**: `services/detection/app/ml/explainability.py` (NEW)

```python
"""Explainable anomaly detection using SHAP"""

import shap
import numpy as np
from typing import Dict, List

class ExplainableAnomalyDetector:
    """Wraps anomaly detector with SHAP explainability"""

    def __init__(self, detector):
        self.detector = detector
        self.explainer = None

    def create_explainer(self, X_train: np.ndarray):
        """Create SHAP explainer after training"""
        self.explainer = shap.TreeExplainer(
            self.detector.model,
            X_train,
            model_output='raw'
        )

    def explain(self, features: np.ndarray) -> Dict:
        """Generate explanation for prediction"""

        # Calculate SHAP values
        shap_values = self.explainer(features)

        # Get feature names
        feature_names = self.detector.feature_extractor.get_feature_names()

        # Get SHAP array
        shap_array = shap_values.values[0]

        # Rank by absolute importance
        importance = [
            {
                'feature': name,
                'shap_value': float(shap_array[i]),
                'actual_value': float(features[0][i]),
                'importance': abs(float(shap_array[i]))
            }
            for i, name in enumerate(feature_names)
        ]

        importance.sort(key=lambda x: x['importance'], reverse=True)

        return {
            'top_features': importance[:5],  # Top 5 contributors
            'all_shap_values': shap_array.tolist(),
            'baseline': float(shap_values.base_values[0]),
            'prediction': float(shap_values.base_values[0] + sum(shap_array))
        }
```

### Step 2: Include SHAP in Anomaly Alerts

**File**: `services/detection/app/consumers/detection_consumer.py:211`

```python
def _handle_anomaly(self, service, result, events):
    """When anomaly detected, include SHAP explanation"""

    # Get SHAP explanation
    explanation = self.explainer.explain(result['features_array'])

    alert = {
        'id': f"anomaly_{service}_{int(time.time())}",
        'timestamp': datetime.now().isoformat(),
        'service': service,
        'severity': result['severity'],
        'score': result['score'],
        'features': dict(zip(result['feature_names'], result['features'])),

        # NEW: Add SHAP explanation
        'explanation': {
            'top_contributing_features': explanation['top_features'],
            'shap_values': explanation['all_shap_values']
        }
    }

    # Store + publish as before
    self._store_anomaly(alert)
    self._publish_alert(alert)
```

### Step 3: Enhanced Reports with SHAP

**File**: `services/reporting/app/generators/prompts.py:60`

```python
def build_incident_report_prompt(context: ReportContext) -> str:
    anomaly = context.anomaly

    # Extract SHAP explanation
    top_features = anomaly['explanation']['top_contributing_features']

    # Format for Claude
    shap_analysis = _format_shap_features(top_features)

    prompt = f"""...

## ML Model Explanation (SHAP Analysis)

The anomaly detection model identified these key factors:

{shap_analysis}

**Interpretation**: The model flagged this incident primarily due to
{top_features[0]['feature']} being significantly elevated, combined with
{top_features[1]['feature']} also showing abnormal values.

## Your Task
Using the SHAP analysis above, focus your root cause investigation on:
1. Why {top_features[0]['feature']} spiked
2. Correlation with {top_features[1]['feature']}
...
"""

def _format_shap_features(features: List[Dict]) -> str:
    """Format SHAP features for Claude"""
    lines = []

    for i, feat in enumerate(features, 1):
        name = feat['feature']
        value = feat['actual_value']
        shap = feat['shap_value']
        impact = "↑ INCREASED anomaly" if shap < 0 else "↓ decreased anomaly"

        lines.append(
            f"{i}. **{name}**: {value:.2f} "
            f"(SHAP impact: {shap:.3f} {impact})"
        )

    return "\n".join(lines)
```

**Result**: Claude now knows WHICH metrics caused the anomaly and can provide targeted recommendations!

---

## 🎨 Building Explainability UI (Day 11)

### Simple HTML + Chart.js Version

**File**: `services/ui/index.html`

```html
<!DOCTYPE html>
<html>
<head>
    <title>Anomaly Explainability</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <h1>Latest Anomaly Explanation</h1>

    <div id="anomaly-info">
        <p><strong>Service</strong>: <span id="service">api-gateway</span></p>
        <p><strong>Score</strong>: <span id="score">-0.92</span></p>
        <p><strong>Time</strong>: <span id="time">2025-10-29 14:32</span></p>
    </div>

    <h2>Top Contributing Features (SHAP Values)</h2>
    <canvas id="shapChart" width="400" height="200"></canvas>

    <h2>Feature Values vs. Baseline</h2>
    <table id="featureTable">
        <tr>
            <th>Feature</th>
            <th>Actual</th>
            <th>Baseline</th>
            <th>Deviation</th>
            <th>SHAP Impact</th>
        </tr>
    </table>

    <script>
        // Fetch latest anomaly from API
        fetch('/api/v1/anomalies/latest')
            .then(r => r.json())
            .then(data => {
                // Update info
                document.getElementById('service').textContent = data.service;
                document.getElementById('score').textContent = data.score.toFixed(3);
                document.getElementById('time').textContent = data.timestamp;

                // Get top 5 features from SHAP
                const topFeatures = data.explanation.top_contributing_features;

                // Create bar chart
                new Chart(document.getElementById('shapChart'), {
                    type: 'bar',
                    data: {
                        labels: topFeatures.map(f => f.feature),
                        datasets: [{
                            label: 'SHAP Importance',
                            data: topFeatures.map(f => Math.abs(f.shap_value)),
                            backgroundColor: topFeatures.map(f =>
                                f.shap_value < -0.1 ? 'rgba(255, 99, 132, 0.6)' : 'rgba(75, 192, 192, 0.6)'
                            )
                        }]
                    },
                    options: {
                        scales: { y: { beginAtZero: true } },
                        plugins: {
                            title: { display: true, text: 'Feature Contribution to Anomaly' }
                        }
                    }
                });

                // Populate table
                const table = document.getElementById('featureTable');
                topFeatures.forEach(f => {
                    const row = table.insertRow();
                    row.insertCell(0).textContent = f.feature;
                    row.insertCell(1).textContent = f.actual_value.toFixed(2);
                    row.insertCell(2).textContent = '2.1'; // TODO: Get from baseline
                    row.insertCell(3).textContent = '+' + (f.actual_value - 2.1).toFixed(1);
                    row.insertCell(4).textContent = f.shap_value.toFixed(3);
                });
            });
    </script>
</body>
</html>
```

**Result**: Simple but professional UI showing SHAP explanations!

---

## 📚 Understanding SHAP Values

### Interpretation Guide

| SHAP Value | Meaning | Action |
|------------|---------|--------|
| **Large negative** (< -0.2) | Strong contributor to anomaly | **Investigate this metric!** |
| **Small negative** (-0.2 to -0.05) | Moderate contributor | Monitor, may be secondary issue |
| **Near zero** (-0.05 to +0.05) | Minimal impact | Likely not relevant |
| **Positive** (> +0.05) | Pushes toward normal | This metric is actually fine |

### Example Analysis

```
SHAP Results:
  error_rate: -0.45      🔴 PRIMARY ISSUE
  cpu_usage: -0.28       🟠 SECONDARY ISSUE
  p99_latency: -0.15     🟡 CONTRIBUTING FACTOR
  memory_usage: +0.02    ✅ NORMAL (ignore)
  event_count: +0.01     ✅ NORMAL (ignore)
```

**Diagnosis**: Error rate spike is the main problem, likely caused by high CPU. Fix CPU → likely fixes errors.

---

## 🎯 Benefits for Resume

Adding SHAP gives you:

1. **Explainable AI** - Hot topic in ML engineering
2. **Production-ready thinking** - Engineers need to debug, not just detect
3. **Advanced ML** - Beyond basic model usage
4. **User experience** - Actionable insights, not black boxes
5. **Interview talking point** - "I integrated SHAP to explain WHY anomalies were detected, which reduced mean time to diagnosis by providing engineers with feature importance rankings instead of just anomaly scores."

---

## 📖 Recommended Resources

### Official SHAP Documentation:
- **GitHub**: https://github.com/slundberg/shap
- **TreeExplainer**: https://shap.readthedocs.io/en/latest/generated/shap.TreeExplainer.html
- **Examples**: https://shap.readthedocs.io/en/latest/example_notebooks/

### Video Tutorials:
- "SHAP Values Explained" by StatQuest (15 min): https://www.youtube.com/watch?v=VB12vP-F0FE
- "Interpretable ML with SHAP" by DataCamp (20 min)

### Papers (Optional):
- "A Unified Approach to Interpreting Model Predictions" (Lundberg & Lee, 2017)

---

## 🧪 Hands-On Exercise

Before Day 8, try this:

```python
import shap
import numpy as np
from sklearn.ensemble import IsolationForest

# 1. Create toy dataset (10 normal points + 1 anomaly)
X_normal = np.random.randn(10, 3) * 0.5  # 3 features, small variance
X_anomaly = np.array([[5, 0, 0]])  # Feature 0 is extreme!

X = np.vstack([X_normal, X_anomaly])

# 2. Train Isolation Forest
model = IsolationForest(contamination=0.1, random_state=42)
model.fit(X)

# 3. Predict (should detect anomaly)
scores = model.decision_function(X)
print("Anomaly scores:", scores)
print("Last point (anomaly):", scores[-1])

# 4. Create SHAP explainer
explainer = shap.TreeExplainer(model, X)

# 5. Explain anomaly
shap_values = explainer(X_anomaly)

# 6. Print SHAP values
print("\nSHAP values for anomaly:")
for i, val in enumerate(shap_values.values[0]):
    print(f"Feature {i}: {val:.3f}")

print("\nInterpretation:")
print(f"Feature 0 (value={X_anomaly[0][0]:.1f}) has SHAP={shap_values.values[0][0]:.3f}")
print("This is the main reason for anomaly detection!")
```

**Expected Output**:
```
Anomaly scores: [-0.15 -0.12 ... -0.89]
Last point (anomaly): -0.89

SHAP values for anomaly:
Feature 0: -0.72
Feature 1: -0.05
Feature 2: -0.03

Interpretation:
Feature 0 (value=5.0) has SHAP=-0.72
This is the main reason for anomaly detection!
```

---

## ✅ Understanding Checklist

Before Day 8, you should know:

- [ ] What is explainability and why it matters
- [ ] What SHAP values represent
- [ ] How to create TreeExplainer for Isolation Forest
- [ ] How to calculate SHAP values for a prediction
- [ ] How to interpret SHAP values (negative = anomalous)
- [ ] How to rank features by importance
- [ ] How to visualize SHAP (waterfall, bar charts)
- [ ] How to include SHAP in anomaly alerts

---

## ➡️ Next Steps

1. ✅ Complete hands-on exercise above
2. ➡️ Read `05-ENSEMBLE-METHODS.md` (combining IF + Prophet)
3. ➡️ Read `06-FEATURE-ENGINEERING.md` (25 features)
4. ➡️ Start `implementation/DAY-08-SHAP.md` when ready

---

*SHAP transforms your anomaly detector from a black box ("trust me, it's anomalous") to an explainable system ("here's exactly why it's anomalous and what to fix"). This is the difference between a demo project and a production system!*
