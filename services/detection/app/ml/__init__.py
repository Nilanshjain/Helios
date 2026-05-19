"""Machine learning components for anomaly detection.

Import submodules directly to avoid loading heavy deps (shap) at package import time:
    from app.ml.anomaly_detector import AnomalyDetector
    from app.ml.feature_engineering import FeatureExtractor
    from app.ml.explainability import ShapExplainer, SHAP_AVAILABLE
"""
