"""
SHAP-based Explainability for Anomaly Detection

Provides feature importance explanations for why anomalies were detected.
Uses SHAP (SHapley Additive exPlanations) to compute:
- Feature contributions to anomaly score
- Top positive/negative contributing features
- Visualization data for waterfall/bar charts
"""

import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from app.core.logging import get_logger

logger = get_logger(__name__)

# Try to import SHAP
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    logger.warning("shap_not_installed", message="SHAP not available. Install with: pip install shap")


class ShapExplainer:
    """
    SHAP-based explainer for Isolation Forest models.

    Provides human-readable explanations for anomaly detections.
    """

    def __init__(self):
        """Initialize SHAP explainer"""
        if not SHAP_AVAILABLE:
            raise ImportError("SHAP is not installed. Install with: pip install shap")

        self.explainer: Optional[shap.Explainer] = None
        self.feature_names: List[str] = []
        self.background_data: Optional[np.ndarray] = None

        logger.info("shap_explainer_initialized")

    def fit(
        self,
        model: Any,
        background_data: np.ndarray,
        feature_names: List[str]
    ) -> None:
        """
        Fit SHAP explainer on model and background data.

        Args:
            model: Trained sklearn model (IsolationForest)
            background_data: Sample of training data for baseline
            feature_names: Names of features
        """
        logger.info("fitting_shap_explainer", num_features=len(feature_names))

        self.feature_names = feature_names
        self.background_data = background_data

        # Use a sample of background data (SHAP can be slow)
        if len(background_data) > 100:
            sample_indices = np.random.choice(len(background_data), 100, replace=False)
            background_sample = background_data[sample_indices]
        else:
            background_sample = background_data

        # Create explainer
        # For IsolationForest, we use TreeExplainer
        try:
            self.explainer = shap.TreeExplainer(
                model,
                background_sample,
                feature_names=feature_names
            )
            logger.info("shap_explainer_fitted")
        except Exception as e:
            logger.error("shap_explainer_fit_failed", error=str(e))
            # Fallback to KernelExplainer (slower but more general)
            logger.info("using_kernel_explainer_fallback")
            self.explainer = shap.KernelExplainer(
                model.score_samples,
                background_sample
            )

    def explain(self, features: np.ndarray) -> Dict[str, Any]:
        """
        Explain a single prediction.

        Args:
            features: Feature vector [1, n_features]

        Returns:
            Dict with SHAP values and interpretation
        """
        if self.explainer is None:
            raise RuntimeError("Explainer not fitted. Call fit() first.")

        # Get SHAP values
        shap_values = self.explainer.shap_values(features)

        # Handle different SHAP output formats
        if isinstance(shap_values, list):
            shap_values = shap_values[0]

        if len(shap_values.shape) > 1:
            shap_values = shap_values[0]

        # Get top contributing features
        top_positive, top_negative = self._get_top_contributors(shap_values)

        # Build explanation
        explanation = {
            "shap_values": shap_values.tolist(),
            "feature_names": self.feature_names,
            "base_value": self.explainer.expected_value if hasattr(self.explainer, 'expected_value') else 0.0,
            "top_positive_contributors": top_positive,
            "top_negative_contributors": top_negative,
            "feature_importance": self._rank_features(shap_values),
        }

        return explanation

    def _get_top_contributors(
        self,
        shap_values: np.ndarray,
        top_n: int = 5
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Get top positive and negative contributing features.

        Args:
            shap_values: SHAP values for all features
            top_n: Number of top features to return

        Returns:
            (top_positive, top_negative) lists of dicts
        """
        # Pair features with SHAP values
        feature_contributions = [
            {
                "feature": self.feature_names[i],
                "shap_value": float(shap_values[i]),
                "abs_value": abs(shap_values[i])
            }
            for i in range(len(shap_values))
        ]

        # Sort by SHAP value
        positive = sorted(
            [f for f in feature_contributions if f["shap_value"] > 0],
            key=lambda x: x["shap_value"],
            reverse=True
        )[:top_n]

        negative = sorted(
            [f for f in feature_contributions if f["shap_value"] < 0],
            key=lambda x: x["shap_value"]
        )[:top_n]

        return positive, negative

    def _rank_features(self, shap_values: np.ndarray) -> List[Dict[str, Any]]:
        """
        Rank features by absolute SHAP value.

        Args:
            shap_values: SHAP values

        Returns:
            List of features ranked by importance
        """
        ranked = [
            {
                "feature": self.feature_names[i],
                "shap_value": float(shap_values[i]),
                "abs_shap_value": abs(shap_values[i]),
                "rank": 0  # Will be set below
            }
            for i in range(len(shap_values))
        ]

        # Sort by absolute value
        ranked.sort(key=lambda x: x["abs_shap_value"], reverse=True)

        # Assign ranks
        for rank, item in enumerate(ranked, 1):
            item["rank"] = rank

        return ranked

    def generate_explanation_text(self, explanation: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation text.

        Args:
            explanation: Output from explain()

        Returns:
            Human-readable explanation
        """
        lines = ["Anomaly Detection Explanation:", ""]

        # Top contributors pushing toward anomaly (negative SHAP)
        if explanation["top_negative_contributors"]:
            lines.append("Top factors indicating ANOMALY:")
            for contrib in explanation["top_negative_contributors"]:
                lines.append(f"  - {contrib['feature']}: {contrib['shap_value']:.4f}")
            lines.append("")

        # Top contributors pushing toward normal (positive SHAP)
        if explanation["top_positive_contributors"]:
            lines.append("Top factors indicating NORMAL:")
            for contrib in explanation["top_positive_contributors"]:
                lines.append(f"  - {contrib['feature']}: +{contrib['shap_value']:.4f}")
            lines.append("")

        # Overall summary
        neg_sum = sum(c["shap_value"] for c in explanation["top_negative_contributors"])
        pos_sum = sum(c["shap_value"] for c in explanation["top_positive_contributors"])

        lines.append(f"Net SHAP impact: {neg_sum + pos_sum:.4f}")
        lines.append(f"  Anomaly factors: {neg_sum:.4f}")
        lines.append(f"  Normal factors:  +{pos_sum:.4f}")

        return "\n".join(lines)

    def prepare_visualization_data(
        self,
        explanation: Dict[str, Any],
        actual_features: np.ndarray
    ) -> Dict[str, Any]:
        """
        Prepare data for frontend visualization (waterfall/bar charts).

        Args:
            explanation: Output from explain()
            actual_features: Actual feature values

        Returns:
            Dict with chart-ready data
        """
        # Get top 10 most important features
        top_features = explanation["feature_importance"][:10]

        # Build chart data
        chart_data = {
            "type": "waterfall",
            "features": [],
            "shap_values": [],
            "feature_values": [],
            "base_value": explanation["base_value"],
        }

        for item in top_features:
            feature_idx = self.feature_names.index(item["feature"])
            chart_data["features"].append(item["feature"])
            chart_data["shap_values"].append(item["shap_value"])
            chart_data["feature_values"].append(float(actual_features[0][feature_idx]))

        return chart_data


def add_shap_to_prediction(
    ensemble_detector: Any,
    events: List[Dict[str, Any]],
    prediction: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Add SHAP explanation to existing prediction.

    Args:
        ensemble_detector: Trained ensemble detector
        events: Event window
        prediction: Original prediction dict

    Returns:
        Enhanced prediction with SHAP values
    """
    if not SHAP_AVAILABLE:
        logger.warning("shap_not_available_skipping")
        return prediction

    try:
        # Extract features
        features = np.array(prediction["features"]).reshape(1, -1)

        # Create explainer
        explainer = ShapExplainer()

        # Fit on model (using small background sample)
        # In practice, you'd cache the fitted explainer
        background = ensemble_detector.scaler.transform(
            np.random.randn(50, len(prediction["features"]))  # Random background
        )

        explainer.fit(
            ensemble_detector.isolation_forest,
            background,
            prediction["feature_names"]
        )

        # Get explanation
        explanation = explainer.explain(features)

        # Add to prediction
        prediction["shap_explanation"] = explanation
        prediction["explanation_text"] = explainer.generate_explanation_text(explanation)
        prediction["visualization_data"] = explainer.prepare_visualization_data(explanation, features)

        logger.info("shap_explanation_added")

    except Exception as e:
        logger.error("shap_explanation_failed", error=str(e))
        prediction["shap_explanation"] = None
        prediction["explanation_text"] = "Explanation generation failed"

    return prediction


if __name__ == "__main__":
    """Test SHAP explainability"""

    print("Testing ShapExplainer...")
    print("=" * 60)

    if not SHAP_AVAILABLE:
        print("❌ SHAP not installed. Install with: pip install shap")
        exit(1)

    # Create synthetic data
    print("\n1. Creating synthetic model and data...")
    from sklearn.ensemble import IsolationForest

    np.random.seed(42)
    X_train = np.random.randn(100, 10)  # 100 samples, 10 features
    X_test = np.random.randn(1, 10)  # 1 test sample

    feature_names = [f"feature_{i}" for i in range(10)]

    # Train model
    model = IsolationForest(contamination=0.1, random_state=42)
    model.fit(X_train)

    # Predict
    score = model.score_samples(X_test)[0]
    is_anomaly = score < -0.5

    print(f"  Model score: {score:.3f}")
    print(f"  Is anomaly: {is_anomaly}")

    # Explain with SHAP
    print("\n2. Generating SHAP explanation...")
    explainer = ShapExplainer()
    explainer.fit(model, X_train, feature_names)

    explanation = explainer.explain(X_test)

    print("\n3. Explanation Results:")
    print("=" * 60)
    print(explainer.generate_explanation_text(explanation))

    print("\n4. Feature Importance Ranking:")
    print("=" * 60)
    for item in explanation["feature_importance"][:5]:
        print(f"  {item['rank']}. {item['feature']:15s}: {item['shap_value']:+.4f} (|{item['abs_shap_value']:.4f}|)")

    print("\n5. Visualization Data:")
    print("=" * 60)
    viz_data = explainer.prepare_visualization_data(explanation, X_test)
    print(f"  Type: {viz_data['type']}")
    print(f"  Features: {viz_data['features'][:3]}...")
    print(f"  SHAP values: {viz_data['shap_values'][:3]}...")

    print(f"\n{'=' * 60}")
    print("✓ SHAP explainability test complete!")
