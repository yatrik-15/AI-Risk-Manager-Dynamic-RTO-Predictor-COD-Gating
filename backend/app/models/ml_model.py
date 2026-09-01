"""
CatBoost model loader and inference module.
Loads the model once at startup and provides fast predict_proba calls.
"""

import os
import json
import numpy as np
from catboost import CatBoostClassifier, Pool
from ..utils.feature_eng import ModelFeatures
import logging

logger = logging.getLogger(__name__)

# Paths relative to this file
ML_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ml", "model_artifacts")
ML_DIR = os.path.normpath(ML_DIR)


class RTOModel:
    """Singleton-style model wrapper. Load once, predict many."""

    def __init__(self):
        self.model = None
        self.feature_names = None
        self.cat_features = None
        self.cat_indices = None
        self.pincode_risk = None
        self._loaded = False

    def load(self):
        """Load model and supporting artifacts from disk."""
        model_path = os.path.join(ML_DIR, "rto_model.cbm")
        features_path = os.path.join(ML_DIR, "feature_names.json")
        pincode_path = os.path.join(ML_DIR, "pincode_risk.json")

        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at {model_path}. Run train.py first.")

        # Load CatBoost model
        self.model = CatBoostClassifier()
        self.model.load_model(model_path)

        # Load feature config
        with open(features_path, "r") as f:
            config = json.load(f)
        self.feature_names = config["features"]
        self.cat_features = config["cat_features"]
        self.cat_indices = config["cat_indices"]

        # Load pincode risk lookup
        with open(pincode_path, "r") as f:
            self.pincode_risk = json.load(f)

        self._loaded = True
        logger.info(f"[ML] Model loaded: {model_path} ({self.model.tree_count_} trees)")

    def predict(self, features: ModelFeatures) -> tuple[float, np.ndarray]:
        """
        Run inference on a single sample.

        Args:
            features: dict with keys matching self.feature_names

        Returns:
            (rto_probability, shap_values)
        """
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        # Build feature array in correct order
        feature_values = [features.get(name, 0) for name in self.feature_names]

        # Create Pool for prediction with categorical feature info
        pool = Pool(
            [feature_values],
            cat_features=self.cat_indices,
        )

        # Predict probability of RTO (class 1)
        proba = self.model.predict_proba(pool)[0]
        rto_prob = float(proba[1])
        rto_prob = max(0.0, min(rto_prob, 1.0))  # Clamp robustly

        # Get SHAP values using CatBoost's native implementation (fast C++)
        shap_values = self.model.get_feature_importance(
            pool,
            type="ShapValues",
        )[0]  # Shape: (n_features + 1,), last element is base value

        return rto_prob, shap_values[:-1]  # Exclude base value

    def get_top_risk_factors(self, shap_values: np.ndarray, top_k: int = 3) -> list[dict]:
        """
        Extract top-k features driving the risk score.

        Returns:
            List of dicts with 'feature', 'impact', 'direction'
        """
        # Sort by SHAP value descending (highest positive impact first)
        indices = np.argsort(shap_values)[::-1]

        factors = []
        for idx in indices:
            impact = float(shap_values[idx])
            if impact <= 0.001:  # Only consider positive impacts (increases risk)
                continue
            factors.append({
                "feature": self.feature_names[idx],
                "impact": round(impact, 4),
                "direction": "increases_risk",
            })
            if len(factors) == top_k:
                break

        return factors

    def get_pincode_risk_rate(self, pincode: str) -> float:
        """Get historical RTO rate for a pincode."""
        return self.pincode_risk.get(str(pincode), 0.2)  # Default 20% if unknown


# Global singleton
rto_model = RTOModel()
