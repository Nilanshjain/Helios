# 03 - Prophet Forecasting for Anomaly Detection

**Goal**: Learn time-series forecasting with Facebook Prophet and how to use it for anomaly detection.

**Time**: 3-4 hours (reading + hands-on)

**Prerequisites**: Understanding of current Isolation Forest implementation

---

## 📚 What is Time-Series Forecasting?

**Simple Definition**: Predicting future values based on historical patterns.

**Example**:
```
Historical error_rate data (last 30 days):
Monday 9am:    2.1%, 2.3%, 2.0%, 2.2% → Predict next Monday 9am: ~2.15%
Monday 3pm:    5.1%, 5.3%, 4.9%, 5.2% → Predict next Monday 3pm: ~5.1%
Saturday 9am:  0.8%, 0.9%, 0.7%, 0.8% → Predict next Saturday: ~0.8%
```

**Key Insight**: Normal behavior has **patterns** - traffic is higher at 3pm than 9am, lower on weekends, etc.

---

## 🎯 Why Use Forecasting for Anomaly Detection?

### Current Approach (Isolation Forest Only):
- Looks at features in isolation
- No understanding of "what's normal **right now**"
- Fixed threshold (-0.7) for all times

**Problem Example**:
```
5% error rate at 3pm Monday → Normal (peak traffic, some errors expected)
5% error rate at 3am Sunday → ANOMALY! (should be ~0.5% at that time)
```

Isolation Forest sees both as similar feature values, might miss the 3am anomaly.

### With Forecasting:
- Learn "normal" varies by time of day/week
- Detect deviations from **expected** behavior
- Adaptive thresholds based on predictions

**Solution**:
```
3pm Monday:
  Predicted: 5.1% ± 0.8%
  Actual: 5.0%
  Status: ✅ Normal (within confidence band)

3am Sunday:
  Predicted: 0.6% ± 0.2%
  Actual: 5.0%
  Status: 🚨 ANOMALY (6x above prediction!)
```

---

## 🔮 What is Prophet?

**Prophet** is a time-series forecasting library by Facebook (Meta) designed for business metrics.

### Why Prophet for This Project?

| Feature | Why It Matters |
|---------|----------------|
| **Automatic seasonality** | Learns weekly/daily patterns without manual config |
| **Robust to missing data** | Works even if some time windows have no events |
| **Confidence intervals** | Provides prediction bands (upper/lower bounds) |
| **Fast** | Fits models quickly (seconds, not minutes) |
| **Easy API** | Simpler than ARIMA or LSTM for this use case |
| **Industry-proven** | Used at Facebook, Uber, Airbnb for anomaly detection |

### Prophet vs. Alternatives

| Method | Pros | Cons | When to Use |
|--------|------|------|-------------|
| **Prophet** | Auto-seasonality, fast, easy | Less accurate for very noisy data | Business metrics (error rates, latency) ✅ |
| **ARIMA** | Statistical rigor | Manual tuning required | When you need statistical tests |
| **LSTM** | Captures complex patterns | Slow training, needs lots of data | Long sequences, complex patterns |
| **Statistical Bands** | Simple, fast | No seasonality awareness | Quick baseline only |

**For Helios**: Prophet is ideal - we have seasonal patterns (daily/weekly traffic) and need fast, automatic forecasting.

---

## 🧮 How Prophet Works (Simplified)

Prophet models time-series as:

```
y(t) = trend(t) + seasonality(t) + holidays(t) + error(t)
```

### 1. **Trend**: Long-term growth/decline
```
Error rate trending up over weeks (gradual degradation)
OR
Error rate stable (mature service)
```

### 2. **Seasonality**: Repeating patterns
```
Weekly: Monday-Friday high traffic, weekends low
Daily: 9am-5pm peak, 1am-6am low
```

### 3. **Holidays**: Special events (we'll skip for now)

### 4. **Error**: Random noise

### Example Breakdown:

**Observed Data** (error_rate %):
```
Mon 9am: 2.0%
Mon 3pm: 5.0%
Sat 9am: 0.8%
Sat 3pm: 1.2%
```

**Prophet Decomposition**:
```
Value = Trend + Daily + Weekly + Noise

Mon 9am: 2.0% = 1.5% + 0.3% + 0.1% + 0.1%
               (stable) (morning) (weekday) (random)

Mon 3pm: 5.0% = 1.5% + 3.2% + 0.1% + 0.2%
               (stable) (afternoon peak!) (weekday) (random)

Sat 9am: 0.8% = 1.5% + 0.3% + (-1.1%) + 0.1%
               (stable) (morning) (weekend lower!) (random)
```

**Forecast** for next Monday 3pm:
```
Predicted: 1.5% + 3.2% + 0.1% = 4.8%
Confidence: 4.0% to 5.6% (80% interval)
```

If actual is **7.2%** → **ANOMALY** (outside confidence band!)

---

## 📦 Prophet Quick Start

### Installation
```bash
pip install prophet
```

### Basic Usage (5 Lines of Code!)

```python
from prophet import Prophet
import pandas as pd

# 1. Prepare data (requires 'ds' and 'y' columns)
df = pd.DataFrame({
    'ds': ['2025-10-01', '2025-10-02', '2025-10-03', ...],  # Dates
    'y': [2.1, 2.3, 5.1, 0.8, ...]  # Values (error_rate)
})

# 2. Create model
model = Prophet(
    daily_seasonality=True,   # Learn daily patterns
    weekly_seasonality=True,  # Learn weekly patterns
    yearly_seasonality=False  # Skip (not enough data)
)

# 3. Train
model.fit(df)

# 4. Make predictions
future = model.make_future_dataframe(periods=24, freq='H')  # Next 24 hours
forecast = model.predict(future)

# 5. Get prediction with confidence intervals
print(forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail())
```

**Output**:
```
            ds      yhat  yhat_lower  yhat_upper
2025-10-29 15:00  4.8      4.0         5.6
2025-10-29 16:00  5.2      4.3         6.1
...
```

---

## 🎯 Using Prophet for Anomaly Detection

### Strategy: Forecast + Confidence Bands

**Algorithm**:
```python
def is_anomalous(actual_value, forecast):
    """Check if actual value is outside confidence interval"""

    predicted = forecast['yhat']
    lower_bound = forecast['yhat_lower']
    upper_bound = forecast['yhat_upper']

    # Anomaly if outside 80% confidence interval
    if actual_value > upper_bound or actual_value < lower_bound:
        return True, "Outside confidence band"
    else:
        return False, "Within normal range"
```

**Example**:
```python
# Historical error_rate for api-gateway
historical_data = fetch_last_30_days('api-gateway', 'error_rate')

# Train Prophet
model = Prophet()
model.fit(historical_data)

# Predict for current 5-min window
forecast = model.predict(pd.DataFrame({'ds': [datetime.now()]}))

# Current window has 8.2% error rate
actual_error_rate = 8.2

# Check
if actual_error_rate > forecast['yhat_upper'].values[0]:
    print("🚨 ANOMALY: Error rate above expected range!")
    print(f"Expected: {forecast['yhat'].values[0]:.1f}%")
    print(f"Upper bound: {forecast['yhat_upper'].values[0]:.1f}%")
    print(f"Actual: {actual_error_rate:.1f}%")
```

---

## 🔧 Prophet for Multiple Metrics

For Helios, we'll forecast **3 key metrics** per service:

1. **error_rate** (%)
2. **p99_latency_ms** (milliseconds)
3. **cpu_usage** (%) - new feature!

### Multi-Metric Detector

```python
class ProphetAnomalyDetector:
    def __init__(self):
        self.models = {}  # Store models per metric

    def train(self, service: str, historical_data: pd.DataFrame):
        """Train Prophet models for error_rate, p99_latency, cpu_usage"""

        for metric in ['error_rate', 'p99_latency_ms', 'cpu_usage']:
            # Prepare data for this metric
            df = pd.DataFrame({
                'ds': historical_data['timestamp'],
                'y': historical_data[metric]
            })

            # Train Prophet
            model = Prophet(
                daily_seasonality=True,
                weekly_seasonality=True,
                changepoint_prior_scale=0.05  # Flexibility for trend changes
            )
            model.fit(df)

            # Store trained model
            self.models[f"{service}_{metric}"] = model

    def predict(self, service: str, current_window: Dict) -> Dict:
        """Check if current metrics are anomalous"""

        anomalies = {}

        for metric in ['error_rate', 'p99_latency_ms', 'cpu_usage']:
            # Get current value
            actual = current_window[metric]

            # Get forecast
            model = self.models[f"{service}_{metric}"]
            forecast = model.predict(pd.DataFrame({'ds': [datetime.now()]}))

            predicted = forecast['yhat'].values[0]
            upper = forecast['yhat_upper'].values[0]
            lower = forecast['yhat_lower'].values[0]

            # Check if anomalous
            is_anomaly = actual > upper or actual < lower
            deviation = abs(actual - predicted) / (predicted + 1) * 100

            anomalies[metric] = {
                'is_anomaly': is_anomaly,
                'actual': actual,
                'predicted': predicted,
                'upper_bound': upper,
                'lower_bound': lower,
                'deviation_percent': deviation
            }

        # Overall anomaly if 2+ metrics anomalous
        anomaly_count = sum(1 for m in anomalies.values() if m['is_anomaly'])

        return {
            'is_anomaly': anomaly_count >= 2,
            'anomaly_count': anomaly_count,
            'metric_details': anomalies
        }
```

---

## 📊 Visualizing Prophet Forecasts

Prophet provides built-in plotting:

```python
# Plot forecast
fig = model.plot(forecast)
plt.title('Error Rate Forecast with Confidence Intervals')
plt.xlabel('Date')
plt.ylabel('Error Rate (%)')
plt.savefig('prophet_forecast.png')
```

**Output** (conceptual):
```
    Error Rate (%)
    |
  8 |                                 🔴 <- Actual (anomaly!)
    |                              ─────── Upper bound
  6 |                          ╱╲╱    ╲╱╲
    |                         ╱  ╲  ╱    ╲
  4 |      Forecast ─────────           ╲─────
    |                   ╲╱  ╲╱    ╲╱
  2 |            ─────── Lower bound
    |
  0 |_____________________________________________
       Mon  Tue  Wed  Thu  Fri  Sat  Sun
```

---

## 🆚 Prophet vs. Isolation Forest

| Aspect | Isolation Forest | Prophet Forecasting |
|--------|------------------|---------------------|
| **Type** | Outlier detection | Time-series forecasting |
| **Input** | Feature vector (12-25 numbers) | Historical time-series (1000+ points) |
| **Training** | Learn distribution of normal features | Learn trend + seasonality |
| **Detection** | "Is this feature vector unusual?" | "Is this value unexpected for this time?" |
| **Strengths** | Multi-dimensional, fast inference | Time-aware, seasonality |
| **Weaknesses** | No time awareness | Single metric at a time |
| **Best For** | General outliers, multi-feature | Metrics with temporal patterns |

### Why Use BOTH (Ensemble)?

**Scenario 1**: Deployment at 2am
```
Prophet: ✅ "2am has low traffic, but this is normal deployment window"
IF: 🚨 "High error rate detected!" (sees 10% errors)
Ensemble: 🚨 ANOMALY (IF caught it, Prophet might miss if deployments are regular)
```

**Scenario 2**: Gradual degradation
```
Prophet: 🚨 "Error rate trending up over 3 days, now outside normal band"
IF: ✅ "Current features within normal range" (change is slow)
Ensemble: 🚨 ANOMALY (Prophet caught the trend)
```

**Scenario 3**: Both agree
```
Prophet: 🚨 "Way above expected for Monday 3pm"
IF: 🚨 "Feature vector is outlier"
Ensemble: 🚨🚨 HIGH CONFIDENCE ANOMALY (both algorithms agree!)
```

---

## 🛠️ Practical Implementation Plan (Day 4)

### Step 1: Generate Historical Data
```python
# Need 30 days of 5-min windows for training
# 30 days * 24 hours * 12 windows/hour = 8,640 windows

generator = RealisticDataGenerator(days=30)
windows = generator.generate()

# Extract metrics per window
historical = []
for window in windows:
    features = extract_features(window)
    historical.append({
        'timestamp': window[0]['time'],
        'error_rate': features[1],  # Feature #2
        'p99_latency_ms': features[4],  # Feature #5
        'cpu_usage': features[13]  # New feature!
    })

df = pd.DataFrame(historical)
```

### Step 2: Train Prophet Models
```python
prophet_detector = ProphetAnomalyDetector()
prophet_detector.train('api-gateway', df)
```

### Step 3: Use in Detection Pipeline
```python
# In detection_consumer.py
def _run_detection(self, service):
    events = list(self.windows[service])

    # 1. Isolation Forest detection
    if_result = self.isolation_forest.predict(events)

    # 2. Prophet detection (NEW!)
    current_features = extract_features(events)
    prophet_result = self.prophet_detector.predict(service, current_features)

    # 3. Ensemble voting (NEW!)
    if if_result['is_anomaly'] and prophet_result['is_anomaly']:
        confidence = 0.95  # Both agree!
    elif if_result['is_anomaly'] or prophet_result['is_anomaly']:
        confidence = 0.70  # One detected
    else:
        confidence = 0.10  # Neither detected

    is_anomaly = confidence > 0.5

    return {
        'is_anomaly': is_anomaly,
        'confidence': confidence,
        'if_score': if_result['score'],
        'prophet_anomaly_count': prophet_result['anomaly_count'],
        'prophet_details': prophet_result['metric_details']
    }
```

---

## 📚 Recommended Resources

### Official Documentation:
- **Prophet Quick Start**: https://facebook.github.io/prophet/docs/quick_start.html (30 min read)
- **Seasonality**: https://facebook.github.io/prophet/docs/seasonality,_holiday_effects,_and_regressors.html

### Video Tutorials:
- "Facebook Prophet Tutorial" by ritvikmath (20 min): https://www.youtube.com/watch?v=95-HMzxsghY
- "Time Series Forecasting with Prophet" by Data School (15 min)

### Papers (Optional Deep Dive):
- "Forecasting at Scale" (Prophet paper): https://peerj.com/preprints/3190.pdf

---

## 🧪 Hands-On Exercise

Try this before Day 4:

```python
import pandas as pd
import numpy as np
from prophet import Prophet
import matplotlib.pyplot as plt

# Generate synthetic error_rate data with daily pattern
dates = pd.date_range('2025-10-01', periods=30*24, freq='H')
error_rates = []

for i, date in enumerate(dates):
    hour = date.hour

    # Daily pattern: higher during business hours
    base = 2.0
    daily = 3.0 if 9 <= hour <= 17 else 0.0
    noise = np.random.normal(0, 0.5)

    error_rate = base + daily + noise
    error_rates.append(max(0, error_rate))  # Can't be negative

# Create DataFrame
df = pd.DataFrame({'ds': dates, 'y': error_rates})

# Train Prophet
model = Prophet(daily_seasonality=True, weekly_seasonality=False)
model.fit(df)

# Forecast next 24 hours
future = model.make_future_dataframe(periods=24, freq='H')
forecast = model.predict(future)

# Plot
fig = model.plot(forecast)
plt.title('Error Rate Forecast')
plt.savefig('prophet_test.png')
print("Plot saved to prophet_test.png")

# Check an anomaly
test_time = pd.DataFrame({'ds': [dates[-1] + pd.Timedelta(hours=14)]})  # 2pm
test_forecast = model.predict(test_time)

actual_anomaly = 15.0  # Simulated high error rate
predicted = test_forecast['yhat'].values[0]
upper = test_forecast['yhat_upper'].values[0]

print(f"\nAnomaly Test:")
print(f"Predicted: {predicted:.1f}%")
print(f"Upper bound: {upper:.1f}%")
print(f"Actual: {actual_anomaly:.1f}%")

if actual_anomaly > upper:
    print("🚨 ANOMALY DETECTED!")
else:
    print("✅ Normal")
```

**Expected Output**:
```
Anomaly Test:
Predicted: 5.2%
Upper bound: 7.8%
Actual: 15.0%
🚨 ANOMALY DETECTED!
```

---

## ✅ Understanding Checklist

Before Day 4, you should know:

- [ ] What is time-series forecasting?
- [ ] Why Prophet is better than static thresholds
- [ ] What are trend and seasonality?
- [ ] How confidence intervals work
- [ ] How to detect anomalies with Prophet
- [ ] Why combine Prophet + Isolation Forest?
- [ ] How to train Prophet on historical data
- [ ] How to forecast and check current values

---

## ➡️ Next Steps

1. ✅ Complete hands-on exercise above
2. ➡️ Read `04-SHAP-EXPLAINABILITY.md` (learn explainable AI)
3. ➡️ Read `05-ENSEMBLE-METHODS.md` (combining algorithms)
4. ➡️ Start `implementation/DAY-04-PROPHET.md` when ready

---

*Prophet makes time-series anomaly detection significantly better by understanding "what's normal RIGHT NOW" instead of a fixed threshold. This is how DataDog and AWS CloudWatch work!*
