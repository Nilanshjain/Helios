# 02 - ML Fundamentals: Isolation Forest Deep Dive

**Reading Time**: 2-3 hours
**Prerequisites**: Basic understanding of decision trees
**Goal**: Deeply understand how Isolation Forest works and why it's perfect for anomaly detection

---

## What is Anomaly Detection?

### Definition
**Anomaly Detection** is the task of identifying unusual patterns that don't conform to expected behavior. In observability, this means detecting system behaviors that indicate potential issues.

### Types of Learning

#### Supervised Learning
- Requires **labeled data** (examples marked as "normal" or "anomaly")
- Example: Email spam detection (emails labeled spam/not spam)
- **Problem for us**: We don't have labeled production anomalies
- **Problem**: Anomalies are rare, creating class imbalance

#### Unsupervised Learning
- Works with **unlabeled data** (just raw observations)
- Learns what "normal" looks like, flags deviations
- Example: Fraud detection (learns normal transaction patterns)
- **Perfect for us**: We have tons of event data but no labels

### Why Unsupervised for Helios?

```
Production Reality:
- 99% of events are normal operations
- 1% are anomalies (errors, slowdowns, outages)
- No one has manually labeled millions of events
- Anomalies change over time (new failure modes)

Solution: Isolation Forest
- Learns from unlabeled data
- Assumes anomalies are "rare and different"
- No manual labeling required
```

---

## How Isolation Forest Works

### The Core Insight: Isolation

**Key Idea**: Anomalies are **easier to isolate** than normal points.

#### The Purple Elephant Analogy

Imagine you're at a zoo with 1000 gray elephants and 1 purple elephant.

**Finding the purple elephant**:
- Ask 1 question: "Is it purple?" → Found in 1 step
- Isolated quickly because it's different

**Finding a specific gray elephant**:
- Need many questions: "Is it in section A?" "Is it eating?" "Is it near the water?"
- Takes many steps because they're all similar

**Isolation Forest does this with data points!**

### Decision Trees for Isolation

#### Normal Decision Tree (Classification)
```
Goal: Separate classes accurately
Example: Is this email spam?
├─ Contains "free money"?
│  ├─ Yes → Spam
│  └─ No → More questions...
```

#### Isolation Tree (Anomaly Detection)
```
Goal: Isolate points quickly
Example: Is this event anomalous?
├─ Latency > 500ms?
│  ├─ Yes (Isolated!) → 1 split
│  └─ No
│     ├─ Error rate > 10%?
│     │  ├─ Yes (Isolated!) → 2 splits
│     │  └─ No → More splits needed...
```

### Training Process

#### Step 1: Build Multiple Random Trees

```python
# Pseudocode for one isolation tree
def build_isolation_tree(data, height=0, max_height=10):
    if height >= max_height or len(data) <= 1:
        return Leaf(size=len(data))

    # Pick random feature
    feature = random.choice(features)

    # Pick random split value between min and max
    min_val = data[feature].min()
    max_val = data[feature].max()
    split = random.uniform(min_val, max_val)

    # Split data
    left = data[data[feature] < split]
    right = data[data[feature] >= split]

    return Node(
        feature=feature,
        split=split,
        left=build_isolation_tree(left, height+1),
        right=build_isolation_tree(right, height+1)
    )
```

**Key Points**:
- Random feature selection (not optimized like decision trees)
- Random split point (not optimized for purity)
- Stop at max height or single point
- Build 100-200 trees (default: 100)

#### Step 2: No Class Labels Needed!

```python
# Training data (NO labels!)
training_data = [
    {"latency": 50, "error_rate": 0.02},   # Normal
    {"latency": 45, "error_rate": 0.01},   # Normal
    {"latency": 500, "error_rate": 0.15},  # Anomaly (but unlabeled!)
    {"latency": 48, "error_rate": 0.02},   # Normal
    ...
]

# Train (no labels passed!)
model = IsolationForest(n_estimators=100)
model.fit(training_data)  # Just learns structure
```

### Inference Process

#### Step 1: Count Splits to Isolate

For a new data point, pass it through each tree and count how many splits until it reaches a leaf.

```
Example Point: {latency: 600, error_rate: 0.20}

Tree 1: latency > 500? YES → Leaf (depth=1)
Tree 2: error_rate > 0.15? YES → Leaf (depth=1)
Tree 3: latency > 450? YES → error_rate > 0.18? YES → Leaf (depth=2)
...
Tree 100: latency > 550? YES → Leaf (depth=1)

Average depth: 1.2 splits
```

```
Normal Point: {latency: 50, error_rate: 0.02}

Tree 1: latency > 500? NO → error_rate > 0.05? NO → ... → Leaf (depth=8)
Tree 2: latency > 200? NO → error_rate > 0.03? NO → ... → Leaf (depth=7)
...
Tree 100: latency > 100? NO → ... → Leaf (depth=9)

Average depth: 8.1 splits
```

#### Step 2: Convert to Anomaly Score

**Formula**:
```
score = 2^(-average_depth / c(n))

where c(n) = average depth of unsuccessful search in BST
           ≈ 2*ln(n-1) + 0.5772 (Euler's constant)
           (n = number of training samples)
```

**Interpretation**:
- Score close to **1**: Anomaly (isolated quickly, shallow depth)
- Score close to **0**: Normal (many splits needed, deep depth)
- Score close to **0.5**: Edge case (ambiguous)

**Scikit-learn Convention**:
- Uses **negative** scores: `-1` to `+1`
- **Negative** (< -0.5): Anomaly
- **Positive** (> 0): Normal


---

## Why Isolation Forest?

### Comparison with Other Algorithms

| Algorithm | Training Speed | Inference Speed | No Labels? | High Dimensions? | Interpretability |
|-----------|---------------|-----------------|-----------|------------------|------------------|
| **Isolation Forest** | ⚡ Fast | ⚡ Fast | ✅ Yes | ✅ Yes | 🟡 Medium |
| One-Class SVM | 🐌 Slow | ⚡ Fast | ✅ Yes | ❌ No | ❌ Low |
| Local Outlier Factor | 🐌 Slow | 🐌 Slow | ✅ Yes | 🟡 OK | 🟡 Medium |
| Autoencoder | 🐌 Very Slow | ⚡ Fast | ✅ Yes | ✅ Yes | ❌ Very Low |
| DBSCAN | ⚡ Fast | ⚡ Fast | ✅ Yes | ❌ No | ✅ High |

### Why Isolation Forest for Helios?

✅ **Speed**: Sub-10ms inference (real-time requirement)
✅ **Scalability**: Handles 25+ features easily
✅ **No Labels**: Works with raw event data
✅ **Production Proven**: Used by AWS, DataDog, Dynatrace
✅ **Easy to Tune**: Only 2 main parameters

---

## Feature Normalization with StandardScaler

### The Problem

```python
# Raw features (different scales!)
event = {
    "event_count": 1000,        # Range: 0 - 10,000
    "error_rate": 0.05,         # Range: 0 - 1
    "p99_latency_ms": 150,      # Range: 0 - 5,000
    "cpu_usage": 0.45,          # Range: 0 - 1
}
```

**Issue**: Isolation Forest picks split points randomly. Features with larger ranges dominate.

- "event_count" gets split at 5000
- "error_rate" gets split at 0.5
- If event_count is 1001 vs 999, barely moves in tree
- If error_rate is 0.06 vs 0.04, barely moves in tree
- **But** these are equally important signals!

### The Solution: StandardScaler

**Formula**:
```
scaled_value = (value - mean) / standard_deviation
```

**Effect**:
- All features centered at 0
- All features have standard deviation of 1
- Now all features contribute equally

```python
# Before scaling
{event_count: 1000, error_rate: 0.05, p99_latency: 150}

# After scaling (example)
{event_count: 0.2, error_rate: -0.5, p99_latency: 1.3}
```

### Code Pattern

```python
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

# Always scale first!
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)

# Then train
model = IsolationForest()
model.fit(X_scaled)

# When predicting, scale new data with SAME scaler
new_data_scaled = scaler.transform(new_data)
predictions = model.predict(new_data_scaled)
```

**Critical**: Use the **same scaler** for training and inference!

---

## Key Parameters

### `contamination`

**Definition**: Expected proportion of anomalies in training data

```python
IsolationForest(contamination=0.05)  # Expect 5% anomalies
```

**Impact**:
- Sets the threshold for anomaly score
- `contamination=0.05` → scores below ~-0.4 are anomalies
- `contamination=0.1` → scores below ~-0.2 are anomalies

**How to Choose**:
- Production systems: 1-5% (most data is normal)
- If unsure: Start with `0.05` (5%)
- Can tune based on evaluation metrics

**In Helios**: We use `0.05` (5% contamination)

### `n_estimators`

**Definition**: Number of trees in the forest

```python
IsolationForest(n_estimators=100)  # Build 100 trees
```

**Impact**:
- More trees → more stable predictions
- More trees → slower training/inference
- Diminishing returns after 100-200

**How to Choose**:
- Start with 100 (sklearn default)
- Increase if predictions are unstable
- 200-300 for production systems

**In Helios**: We use `100` trees

### `max_samples`

**Definition**: Number of samples to use when building each tree

```python
IsolationForest(max_samples=256)  # Each tree sees 256 samples
```

**Impact**:
- Smaller → faster training
- Smaller → more diversity between trees
- Default: `min(256, n_samples)`

**In Helios**: We use default (`256` or fewer)

---

## Hands-On Exercise

### Generate Toy Dataset

```python
import numpy as np
from sklearn.ensemble import IsolationForest
import matplotlib.pyplot as plt

# Generate normal data (clustered)
normal = np.random.randn(200, 2) * 0.5 + [0, 0]

# Generate anomalies (scattered far away)
anomalies = np.random.uniform(-4, 4, (10, 2))

# Combine
X = np.vstack([normal, anomalies])
```

### Train Model

```python
# Train Isolation Forest
model = IsolationForest(contamination=0.05, random_state=42)
model.fit(X)

# Predict
predictions = model.predict(X)  # -1 = anomaly, 1 = normal
scores = model.score_samples(X)  # Continuous scores
```

### Visualize

```python
plt.figure(figsize=(10, 6))

# Plot normal points
plt.scatter(X[predictions == 1, 0], X[predictions == 1, 1],
            c='blue', label='Normal', alpha=0.5)

# Plot anomalies
plt.scatter(X[predictions == -1, 0], X[predictions == -1, 1],
            c='red', label='Anomaly', s=100, marker='x')

plt.legend()
plt.title('Isolation Forest Results')
plt.show()
```

---

## Common Pitfalls

### 1. Forgetting to Scale Features

```python
# ❌ WRONG
model.fit(raw_data)

# ✅ CORRECT
scaler = StandardScaler()
scaled_data = scaler.fit_transform(raw_data)
model.fit(scaled_data)
```

### 2. Contamination Too High

```python
# ❌ WRONG (if only 2% are actually anomalies)
model = IsolationForest(contamination=0.2)  # 20%!

# Result: Many real anomalies classified as normal
```

### 3. Training on Anomalous Data

```python
# ❌ WRONG
training_data = production_events_during_outage  # Mostly errors!
model.fit(training_data)

# Result: Model learns errors are "normal"
```

**Solution**: Train on known-good data or use synthetic data

### 4. Different Scalers for Train/Test

```python
# ❌ WRONG
X_train_scaled = StandardScaler().fit_transform(X_train)
X_test_scaled = StandardScaler().fit_transform(X_test)  # NEW scaler!

# ✅ CORRECT
scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)  # SAME scaler
```

---

## How Helios Uses Isolation Forest

### Current Implementation

**File**: `services/detection/app/ml/anomaly_detector.py`

```python
class AnomalyDetector:
    def __init__(self, contamination=0.05):
        self.scaler = StandardScaler()
        self.model = IsolationForest(
            contamination=contamination,
            n_estimators=100,
            max_samples=256,
            random_state=42
        )

    def train(self, training_data):
        # Extract 12 features
        features = feature_extractor.extract(training_data)

        # Scale
        features_scaled = self.scaler.fit_transform(features)

        # Train
        self.model.fit(features_scaled)

    def predict(self, events):
        # Extract features from new events
        features = feature_extractor.extract(events)

        # Scale with SAME scaler
        features_scaled = self.scaler.transform(features)

        # Predict
        score = self.model.score_samples(features_scaled)[0]
        is_anomaly = score < -0.4  # Threshold

        return {
            "is_anomaly": is_anomaly,
            "score": score,
            ...
        }
```

### Enhancement Plan (Days 4-5)

You'll extend this to:
1. **25 features** instead of 12 (Day 3)
2. **Ensemble** with Prophet forecasting (Day 4-5)
3. **SHAP explainability** (Day 8)

---

## Self-Quiz

Test your understanding:

1. **Why is Isolation Forest unsupervised?**
   <details>
   <summary>Answer</summary>
   It doesn't require labeled data (no "anomaly" or "normal" labels). It learns patterns from the data structure itself.
   </details>

2. **What does a low anomaly score mean?**
   <details>
   <summary>Answer</summary>
   The point was isolated quickly (few splits), indicating it's different from most data → likely an anomaly.
   </details>

3. **Why do we need StandardScaler?**
   <details>
   <summary>Answer</summary>
   Features have different scales (e.g., event_count: 0-10k vs error_rate: 0-1). Without scaling, large-scale features dominate. Scaling ensures all features contribute equally.
   </details>

4. **What happens if contamination is too low?**
   <details>
   <summary>Answer</summary>
   The threshold is too strict → many real anomalies are missed (low recall).
   </details>

5. **What happens if you train on mostly anomalous data?**
   <details>
   <summary>Answer</summary>
   The model learns anomalies are "normal" → fails to detect future anomalies.
   </details>

---

## Checklist

Before moving to Day 2, ensure you can:

- [ ] Explain Isolation Forest in your own words (pretend you're teaching a friend)
- [ ] Draw a simple isolation tree on paper
- [ ] Understand why anomalies have shorter paths
- [ ] Explain what StandardScaler does and why it's needed
- [ ] Choose appropriate `contamination` value
- [ ] Avoid the 4 common pitfalls listed above
- [ ] Read and understand Helios's `anomaly_detector.py` code

---

## Next Steps

**Tomorrow (Day 2)**: You'll build a **RealisticDataGenerator** that creates 30 days of synthetic events with realistic correlations. You'll use your Isolation Forest knowledge to generate data that:
- Has normal patterns (clustered in feature space)
- Has rare anomalies (isolated in feature space)
- Tests your model's detection ability
