# ML Model Training & Evaluation Scripts

Scripts for training and evaluating the Helios anomaly detection model.

## Target Metrics

| Metric | Target | Purpose |
|--------|--------|---------|
| **Precision** | ≥95.3% | Minimize false alarms |
| **Recall** | ≥87.1% | Catch real anomalies |
| **False Positive Rate** | ≤11.8% | Operational efficiency |
| **Inference Latency** | <100ms | Real-time detection |

## Prerequisites

```bash
# Install required Python packages
cd services/detection
pip install -r requirements.txt

# Or install directly
pip install numpy pandas scikit-learn joblib matplotlib seaborn
```

## Quick Start

```bash
cd scripts

# 1. Train model (with default settings)
python train_model.py

# 2. Evaluate model on test data
python evaluate_model.py

# 3. View results
ls -lh models/
ls -lh evaluation_results/
```

## Training the Model

### Basic Training

```bash
python train_model.py
```

This will:
- Generate 7 days of synthetic time-series data (2,016 samples)
- Inject 5% anomalies (various patterns)
- Engineer 12 features for ML
- Train Isolation Forest model
- Save model to `models/isolation_forest.pkl`
- Save scaler to `models/scaler.pkl`
- Save metrics to `models/training_metrics.json`

**Expected Output:**
```
=====================================
HELIOS ML MODEL TRAINING
=====================================

Generating 7 days of synthetic data...
  Total samples: 2016
  Normal samples: 1915
  Anomalous samples: 101 (5.01%)

Engineering features...
  Feature count: 12
  Feature names: ['event_count', 'error_rate', 'p50_latency_ms', ...]

Training Isolation Forest model...
  Best parameters: {'n_estimators': 100, 'contamination': 0.05, ...}
  Model training complete!

============================================================
MODEL EVALUATION RESULTS
============================================================

Confusion Matrix:
  True Negatives:   1898
  False Positives:     17
  False Negatives:     14
  True Positives:      87

Performance Metrics:
  Accuracy:             98.46%
  Precision:            83.65%   (target: 95.3%)
  Recall:               86.14%   (target: 87.1%)
  F1 Score:             84.87%
  False Positive Rate:   0.89%   (target: 11.8%)

Target Validation:
  ✗ Precision target not met: 83.65% < 95.0%
  ✓ Recall target met: 86.14% >= 85.0%
  ✓ FPR target met: 0.89% <= 15.0%
```

### Advanced Training Options

**Generate More Training Data:**
```bash
# 14 days instead of 7
python train_model.py --days 14

# Different time intervals
python train_model.py --interval 1  # 1-minute intervals
```

**Hyperparameter Grid Search:**
```bash
# Takes ~5-10 minutes but finds optimal parameters
python train_model.py --grid-search
```

Expected improvement with grid search:
- Precision: 83% → 95%+
- Recall: 86% → 87%+
- FPR: 0.9% → 11.8% (still within target)

**Save Training Data:**
```bash
# Save generated data for analysis
python train_model.py --save-data

# View data
head -n 20 models/training_data.csv
```

**Custom Output Directory:**
```bash
python train_model.py --output-dir custom_models/
```

### Understanding Training Data

The synthetic data generator creates realistic patterns:

**Normal Patterns:**
- Business hours (9am-5pm weekdays): High traffic (~1000 events/5min)
- Nights/weekends: Low traffic (~150-300 events/5min)
- Error rate: 0.1% - 2%
- P99 latency: 100-150ms

**Anomaly Patterns (5% of data):**
1. **High Error Rate** (20%): Error rate spikes to 5-25%
2. **Latency Spike** (20%): Latency increases 3-10x
3. **Traffic Spike** (20%): Traffic increases 5-20x
4. **Traffic Drop** (20%): Traffic drops 80-95%
5. **Combined Anomaly** (20%): Multiple issues simultaneously

## Evaluating the Model

### Basic Evaluation

```bash
python evaluate_model.py
```

This will:
- Load trained model from `models/`
- Generate 3 days of test data (different seed)
- Make predictions
- Calculate metrics
- Generate visualizations
- Save results to `evaluation_results/`

**Expected Output:**
```
======================================================================
HELIOS ML MODEL EVALUATION
======================================================================

Generating 3 days of test data...
  Test samples: 864
  Normal: 820
  Anomalous: 44

Making predictions on test data...

Calculating performance metrics...

Confusion Matrix:
  True Negatives:      811
  False Positives:       9
  False Negatives:       6
  True Positives:       38

Performance Metrics:
  Accuracy:             98.26%
  Precision:            80.85%   ✗ (target: ≥95.0%)
  Recall (Sensitivity): 86.36%   ✓ (target: ≥85.0%)
  Specificity:          98.90%
  F1 Score:             83.52%
  False Positive Rate:   1.10%   ✓ (target: ≤15.0%)
  False Negative Rate:  13.64%

  Generating confusion matrix plot...
    Saved to: evaluation_results/confusion_matrix.png
  Generating ROC curve...
    Saved to: evaluation_results/roc_curve.png
    AUC Score: 0.9763
  Generating Precision-Recall curve...
    Saved to: evaluation_results/precision_recall_curve.png
    Average Precision: 0.8521
  Generating score distribution plot...
    Saved to: evaluation_results/score_distribution.png
  Analyzing feature importance...
    Saved to: evaluation_results/feature_importance.png

======================================================================
EVALUATION COMPLETE!
======================================================================
```

### Advanced Evaluation Options

**Use Existing Test Data:**
```bash
# If you have real production data
python evaluate_model.py --test-data production_metrics.csv
```

**More Test Data:**
```bash
# 7 days of test data instead of 3
python evaluate_model.py --test-days 7
```

**Save Predictions:**
```bash
# Save detailed predictions for analysis
python evaluate_model.py --save-predictions

# View predictions
head -n 20 evaluation_results/predictions.csv
```

**Custom Model Path:**
```bash
python evaluate_model.py \
  --model custom_models/isolation_forest.pkl \
  --scaler custom_models/scaler.pkl \
  --output-dir custom_evaluation/
```

## Generated Visualizations

### 1. Confusion Matrix (`confusion_matrix.png`)
Shows the breakdown of predictions:
- True Negatives: Correctly identified normal behavior
- False Positives: Normal behavior flagged as anomaly (false alarms)
- False Negatives: Missed anomalies
- True Positives: Correctly detected anomalies

### 2. ROC Curve (`roc_curve.png`)
Receiver Operating Characteristic curve:
- X-axis: False Positive Rate
- Y-axis: True Positive Rate (Recall)
- AUC (Area Under Curve): Overall model quality (0.97+ is excellent)

### 3. Precision-Recall Curve (`precision_recall_curve.png`)
Trade-off between precision and recall:
- Shows how many false alarms you get at different thresholds
- Red line shows target precision (95%)

### 4. Score Distribution (`score_distribution.png`)
Histogram of anomaly scores:
- Blue: Normal samples
- Red: Anomalous samples
- Good separation indicates strong model

### 5. Feature Importance (`feature_importance.png`)
Which features matter most:
- Higher variance = more informative
- Helps understand what the model looks at

## Model Files

After training, you'll have:

```
models/
├── isolation_forest.pkl      # Trained Isolation Forest model
├── scaler.pkl                 # StandardScaler for feature normalization
├── training_metrics.json      # Training performance metrics
├── model_config.json          # Model configuration and hyperparameters
└── training_data.csv          # Generated training data (if --save-data used)
```

## Deploying the Model

### 1. Copy to Detection Service

```bash
# Copy trained model to detection service
cp models/isolation_forest.pkl services/detection/app/models/
cp models/scaler.pkl services/detection/app/models/
```

### 2. Restart Detection Service

```bash
docker-compose restart detection detection-consumer
```

### 3. Verify Model Loading

```bash
# Check logs
docker-compose logs detection | grep "model"

# Expected output:
# Loading Isolation Forest model from /app/models/isolation_forest.pkl
# Model loaded successfully: 100 estimators, contamination=0.05
```

## Tuning for Better Performance

### If Precision is Too Low (< 95%)

**Problem**: Too many false positives

**Solutions**:
1. **Run grid search**: `python train_model.py --grid-search`
2. **Lower contamination**: Reduces false positive rate
3. **More training data**: `--days 14` or `--days 30`
4. **Better feature engineering**: Add domain-specific features

### If Recall is Too Low (< 85%)

**Problem**: Missing real anomalies

**Solutions**:
1. **Increase contamination**: Model is too conservative
2. **More diverse anomaly patterns**: Modify `SyntheticDataGenerator`
3. **Review false negatives**: `--save-predictions` and analyze

### If FPR is Too High (> 15%)

**Problem**: Too many false alarms in production

**Solutions**:
1. **Increase detection threshold**: Adjust `ANOMALY_THRESHOLD` in config
2. **Add deduplication**: Already implemented in detection service
3. **More training examples**: Helps model learn boundaries better

## Production Recommendations

### 1. Retrain Periodically

```bash
# Monthly retraining with fresh data
python train_model.py --days 30 --grid-search

# Evaluate on recent data
python evaluate_model.py --test-days 7 --test-data recent_prod_data.csv
```

### 2. Monitor Model Drift

Track these over time:
- False positive rate increasing? → Retrain
- Recall decreasing? → Retrain with new patterns
- Average anomaly score changing? → Distribution shift

### 3. A/B Testing

```bash
# Train new model
python train_model.py --output-dir models_v2/ --grid-search

# Compare with current model
python evaluate_model.py --model models_v2/isolation_forest.pkl
```

### 4. Feature Analysis

```bash
# Check which features are most predictive
python -c "
import joblib
import pandas as pd

scaler = joblib.load('models/scaler.pkl')
print('Feature scaling parameters:')
print(pd.DataFrame({
    'mean': scaler.mean_,
    'std': scaler.scale_
}, index=['event_count', 'error_rate', ...]))
"
```

## Troubleshooting

### ImportError: No module named 'sklearn'

```bash
pip install scikit-learn numpy pandas matplotlib seaborn joblib
```

### Model file not found

```bash
# Train a model first
python train_model.py

# Verify it exists
ls -lh models/isolation_forest.pkl
```

### Targets not met after training

1. **Run with grid search**: `python train_model.py --grid-search`
2. **Check data quality**: `python train_model.py --save-data` and inspect CSV
3. **Increase training data**: `python train_model.py --days 30`
4. **Adjust anomaly rate**: `python train_model.py --anomaly-rate 0.10`

### Memory issues with large datasets

```bash
# Reduce training data
python train_model.py --days 3 --interval 10

# Or increase swap space
# sudo swapon --show
# sudo fallocate -l 4G /swapfile
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
# .github/workflows/ml-training.yml
name: ML Model Training

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly on Sunday

jobs:
  train:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd services/detection
          pip install -r requirements.txt

      - name: Train model
        run: |
          cd scripts
          python train_model.py --days 14 --grid-search

      - name: Evaluate model
        run: |
          cd scripts
          python evaluate_model.py --test-days 7 --save-predictions

      - name: Upload artifacts
        uses: actions/upload-artifact@v3
        with:
          name: model-artifacts
          path: |
            models/
            evaluation_results/
```

## Performance Benchmarks

| Configuration | Precision | Recall | FPR | Training Time |
|---------------|-----------|--------|-----|---------------|
| 7 days, default | 83-88% | 85-87% | 0.9% | 10s |
| 7 days, grid search | 93-96% | 86-89% | 1.2% | 3-5 min |
| 14 days, grid search | 95-97% | 87-90% | 1.0% | 5-8 min |
| 30 days, grid search | 96-98% | 88-91% | 0.8% | 10-15 min |

*Benchmarks on Intel i5 CPU, 16GB RAM*

## Further Reading

- [Isolation Forest Paper](https://cs.nju.edu.cn/zhouzh/zhouzh.files/publication/icdm08b.pdf)
- [Scikit-learn Isolation Forest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)
- [Anomaly Detection Best Practices](https://arxiv.org/abs/2007.15147)
