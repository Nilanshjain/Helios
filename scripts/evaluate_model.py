#!/usr/bin/env python3
"""
Helios ML Model Evaluation Script

Evaluates trained Isolation Forest model on test data and generates
comprehensive performance reports including:
- Precision, Recall, F1 scores
- Confusion matrix
- ROC curve and AUC
- Precision-Recall curve
- Feature importance analysis
"""

import argparse
import json
import numpy as np
import pandas as pd
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.metrics import (
    classification_report, confusion_matrix, precision_recall_fscore_support,
    roc_curve, auc, precision_recall_curve, average_precision_score
)
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# Import data generator from training script
import sys
sys.path.append(str(Path(__file__).parent))
from train_model import SyntheticDataGenerator


class ModelEvaluator:
    """Evaluate trained anomaly detection model"""

    def __init__(self, model_path, scaler_path):
        """Load trained model and scaler"""
        print(f"Loading model from {model_path}")
        self.model = joblib.load(model_path)

        print(f"Loading scaler from {scaler_path}")
        self.scaler = joblib.load(scaler_path)

    def prepare_features(self, df):
        """Engineer features (same as training)"""
        features = df[[
            'event_count',
            'error_rate',
            'p50_latency_ms',
            'p95_latency_ms',
            'p99_latency_ms',
            'latency_std',
            'hour_of_day'
        ]].copy()

        # Additional engineered features
        features['p95_p50_ratio'] = features['p95_latency_ms'] / (features['p50_latency_ms'] + 1)
        features['p99_p95_ratio'] = features['p99_latency_ms'] / (features['p95_latency_ms'] + 1)
        features['error_count'] = features['event_count'] * features['error_rate']

        # Log transforms
        features['log_event_count'] = np.log1p(features['event_count'])
        features['log_error_rate'] = np.log1p(features['error_rate'] * 1000)

        return features

    def predict(self, X):
        """Make predictions"""
        X_scaled = self.scaler.transform(X)
        predictions = self.model.predict(X_scaled)
        scores = self.model.score_samples(X_scaled)

        # Convert -1 (anomaly) to 1, and 1 (normal) to 0
        y_pred = np.where(predictions == -1, 1, 0)

        # Normalize scores to [0, 1] range for probability-like interpretation
        scores_norm = (scores - scores.min()) / (scores.max() - scores.min())

        return y_pred, scores_norm

    def evaluate(self, X, y_true, output_dir):
        """Comprehensive model evaluation"""
        print("\n" + "="*70)
        print("MODEL EVALUATION")
        print("="*70)

        # Make predictions
        print("\nMaking predictions on test data...")
        y_pred, scores = self.predict(X)

        # Basic metrics
        metrics = self._calculate_metrics(y_true, y_pred)

        # Generate visualizations
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        self._plot_confusion_matrix(y_true, y_pred, output_path)
        self._plot_roc_curve(y_true, scores, output_path)
        self._plot_precision_recall_curve(y_true, scores, output_path)
        self._plot_score_distribution(y_true, scores, output_path)
        self._plot_feature_importance(X, output_path)

        return metrics, y_pred, scores

    def _calculate_metrics(self, y_true, y_pred):
        """Calculate comprehensive performance metrics"""
        print("\nCalculating performance metrics...")

        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

        print("\nConfusion Matrix:")
        print(f"  True Negatives:  {tn:7d}")
        print(f"  False Positives: {fp:7d}")
        print(f"  False Negatives: {fn:7d}")
        print(f"  True Positives:  {tp:7d}")

        # Calculate metrics
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average='binary', zero_division=0
        )
        accuracy = (tp + tn) / (tp + tn + fp + fn)
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0

        print("\nPerformance Metrics:")
        print(f"  Accuracy:            {accuracy*100:6.2f}%")
        print(f"  Precision:           {precision*100:6.2f}%   {'✓' if precision >= 0.95 else '✗'} (target: ≥95.0%)")
        print(f"  Recall (Sensitivity):{recall*100:6.2f}%   {'✓' if recall >= 0.85 else '✗'} (target: ≥85.0%)")
        print(f"  Specificity:         {specificity*100:6.2f}%")
        print(f"  F1 Score:            {f1*100:6.2f}%")
        print(f"  False Positive Rate: {fpr*100:6.2f}%   {'✓' if fpr <= 0.15 else '✗'} (target: ≤15.0%)")
        print(f"  False Negative Rate: {fnr*100:6.2f}%")

        print("\nDetailed Classification Report:")
        print(classification_report(y_true, y_pred, target_names=['Normal', 'Anomaly']))

        return {
            'accuracy': float(accuracy),
            'precision': float(precision),
            'recall': float(recall),
            'specificity': float(specificity),
            'f1_score': float(f1),
            'false_positive_rate': float(fpr),
            'false_negative_rate': float(fnr),
            'confusion_matrix': {
                'true_negatives': int(tn),
                'false_positives': int(fp),
                'false_negatives': int(fn),
                'true_positives': int(tp)
            }
        }

    def _plot_confusion_matrix(self, y_true, y_pred, output_dir):
        """Plot and save confusion matrix"""
        print("  Generating confusion matrix plot...")

        cm = confusion_matrix(y_true, y_pred)
        plt.figure(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', cbar=True,
                    xticklabels=['Normal', 'Anomaly'],
                    yticklabels=['Normal', 'Anomaly'])
        plt.title('Confusion Matrix', fontsize=14, fontweight='bold')
        plt.ylabel('True Label')
        plt.xlabel('Predicted Label')
        plt.tight_layout()

        output_file = output_dir / 'confusion_matrix.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    Saved to: {output_file}")

    def _plot_roc_curve(self, y_true, scores, output_dir):
        """Plot ROC curve"""
        print("  Generating ROC curve...")

        fpr, tpr, thresholds = roc_curve(y_true, scores)
        roc_auc = auc(fpr, tpr)

        plt.figure(figsize=(8, 6))
        plt.plot(fpr, tpr, color='darkorange', lw=2,
                 label=f'ROC curve (AUC = {roc_auc:.3f})')
        plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--', label='Random Classifier')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate (Recall)')
        plt.title('Receiver Operating Characteristic (ROC) Curve', fontsize=14, fontweight='bold')
        plt.legend(loc='lower right')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        output_file = output_dir / 'roc_curve.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    Saved to: {output_file}")
        print(f"    AUC Score: {roc_auc:.4f}")

    def _plot_precision_recall_curve(self, y_true, scores, output_dir):
        """Plot Precision-Recall curve"""
        print("  Generating Precision-Recall curve...")

        precision, recall, thresholds = precision_recall_curve(y_true, scores)
        avg_precision = average_precision_score(y_true, scores)

        plt.figure(figsize=(8, 6))
        plt.plot(recall, precision, color='darkorange', lw=2,
                 label=f'PR curve (AP = {avg_precision:.3f})')
        plt.axhline(y=0.95, color='red', linestyle='--', lw=1, label='Target Precision (95%)')
        plt.xlim([0.0, 1.0])
        plt.ylim([0.0, 1.05])
        plt.xlabel('Recall')
        plt.ylabel('Precision')
        plt.title('Precision-Recall Curve', fontsize=14, fontweight='bold')
        plt.legend(loc='lower left')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        output_file = output_dir / 'precision_recall_curve.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    Saved to: {output_file}")
        print(f"    Average Precision: {avg_precision:.4f}")

    def _plot_score_distribution(self, y_true, scores, output_dir):
        """Plot anomaly score distribution"""
        print("  Generating score distribution plot...")

        plt.figure(figsize=(10, 6))

        # Separate scores by true label
        normal_scores = scores[y_true == 0]
        anomaly_scores = scores[y_true == 1]

        plt.hist(normal_scores, bins=50, alpha=0.6, label='Normal', color='blue', edgecolor='black')
        plt.hist(anomaly_scores, bins=50, alpha=0.6, label='Anomaly', color='red', edgecolor='black')

        plt.xlabel('Anomaly Score')
        plt.ylabel('Frequency')
        plt.title('Anomaly Score Distribution', fontsize=14, fontweight='bold')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        output_file = output_dir / 'score_distribution.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    Saved to: {output_file}")

    def _plot_feature_importance(self, X, output_dir):
        """Analyze feature importance through permutation"""
        print("  Analyzing feature importance...")

        # Use simple variance-based importance as proxy
        feature_variance = X.var().sort_values(ascending=False)

        plt.figure(figsize=(10, 8))
        feature_variance.plot(kind='barh', color='steelblue', edgecolor='black')
        plt.xlabel('Variance')
        plt.ylabel('Feature')
        plt.title('Feature Variance (Proxy for Importance)', fontsize=14, fontweight='bold')
        plt.grid(True, alpha=0.3, axis='x')
        plt.tight_layout()

        output_file = output_dir / 'feature_importance.png'
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"    Saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Evaluate Helios anomaly detection model')
    parser.add_argument('--model', type=str, default='models/isolation_forest.pkl',
                        help='Path to trained model file')
    parser.add_argument('--scaler', type=str, default='models/scaler.pkl',
                        help='Path to scaler file')
    parser.add_argument('--test-days', type=int, default=3,
                        help='Days of test data to generate (default: 3)')
    parser.add_argument('--test-data', type=str, default=None,
                        help='Path to existing test data CSV (optional)')
    parser.add_argument('--output-dir', type=str, default='evaluation_results',
                        help='Output directory for results')
    parser.add_argument('--save-predictions', action='store_true',
                        help='Save predictions to CSV')
    args = parser.parse_args()

    print("="*70)
    print("HELIOS ML MODEL EVALUATION")
    print("="*70)

    # Check if model files exist
    model_path = Path(args.model)
    scaler_path = Path(args.scaler)

    if not model_path.exists():
        print(f"\nERROR: Model file not found: {model_path}")
        print("Please train a model first using train_model.py")
        return 1

    if not scaler_path.exists():
        print(f"\nERROR: Scaler file not found: {scaler_path}")
        print("Please train a model first using train_model.py")
        return 1

    # Load test data
    if args.test_data:
        print(f"\nLoading test data from {args.test_data}")
        df = pd.read_csv(args.test_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    else:
        print(f"\nGenerating {args.test_days} days of test data...")
        generator = SyntheticDataGenerator(days=args.test_days, random_state=123)  # Different seed
        df = generator.generate()

    print(f"  Test samples: {len(df)}")
    print(f"  Normal: {(df['is_anomaly'] == 0).sum()}")
    print(f"  Anomalous: {(df['is_anomaly'] == 1).sum()}")

    # Load evaluator
    evaluator = ModelEvaluator(model_path, scaler_path)

    # Prepare features
    X = evaluator.prepare_features(df)
    y_true = df['is_anomaly'].astype(int)

    # Evaluate
    metrics, y_pred, scores = evaluator.evaluate(X, y_true, args.output_dir)

    # Save results
    output_path = Path(args.output_dir)
    results_file = output_path / 'evaluation_metrics.json'

    evaluation_results = {
        'evaluation_date': datetime.now().isoformat(),
        'model_file': str(model_path),
        'test_samples': len(df),
        'test_days': args.test_days,
        'metrics': metrics
    }

    print(f"\nSaving evaluation results to {results_file}")
    with open(results_file, 'w') as f:
        json.dump(evaluation_results, f, indent=2)

    # Save predictions if requested
    if args.save_predictions:
        predictions_file = output_path / 'predictions.csv'
        print(f"Saving predictions to {predictions_file}")

        predictions_df = pd.DataFrame({
            'timestamp': df['timestamp'],
            'true_label': y_true,
            'predicted_label': y_pred,
            'anomaly_score': scores,
            'correct': y_true == y_pred
        })
        predictions_df.to_csv(predictions_file, index=False)

    print("\n" + "="*70)
    print("EVALUATION COMPLETE!")
    print("="*70)
    print(f"\nResults saved to: {output_path}/")
    print(f"  - evaluation_metrics.json")
    print(f"  - confusion_matrix.png")
    print(f"  - roc_curve.png")
    print(f"  - precision_recall_curve.png")
    print(f"  - score_distribution.png")
    print(f"  - feature_importance.png")

    if args.save_predictions:
        print(f"  - predictions.csv")

    # Check if targets met
    precision = metrics['precision']
    recall = metrics['recall']
    fpr = metrics['false_positive_rate']

    targets_met = precision >= 0.95 and recall >= 0.85 and fpr <= 0.15

    if targets_met:
        print("\n✓ All target metrics achieved on test data!")
    else:
        print("\n⚠ Some target metrics not met on test data:")
        if precision < 0.95:
            print(f"  - Precision: {precision*100:.2f}% < 95.0%")
        if recall < 0.85:
            print(f"  - Recall: {recall*100:.2f}% < 85.0%")
        if fpr > 0.15:
            print(f"  - FPR: {fpr*100:.2f}% > 15.0%")

    return 0 if targets_met else 1


if __name__ == '__main__':
    exit(main())
