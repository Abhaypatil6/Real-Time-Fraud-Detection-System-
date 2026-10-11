"""
Feature engineering and preprocessing for fraud detection.
Handles scaling, encoding, and feature selection for ML models.
"""
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
import joblib
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.config import model_config

FEATURE_COLUMNS = [
    "amount",
    "hour_of_day",
    "day_of_week",
    "is_weekend",
    "is_night",
    "is_high_risk_country",
    "is_high_risk_category",
    "distance_from_home_km",
    "velocity_1h",
    "velocity_24h",
    "failed_attempts_24h",
    "card_present",
    "is_international",
    "amount_vs_avg_ratio",
]

CATEGORICAL_COLUMNS = ["merchant_category", "country"]
TARGET_COLUMN = "is_fraud"


class FraudPreprocessor:
    """
    Preprocessing pipeline for fraud detection:
    - Label-encodes categorical columns
    - Standard-scales numerical features
    - Provides transform() for inference on single transactions
    """

    def __init__(self):
        self.scaler = StandardScaler()
        self.label_encoders: dict[str, LabelEncoder] = {}
        self.feature_columns = FEATURE_COLUMNS
        self._fitted = False

    # ------------------------------------------------------------------
    # Training helpers
    # ------------------------------------------------------------------
    def fit_transform(self, df: pd.DataFrame):
        """Fit on training data and return (X_train, X_test, y_train, y_test)."""
        df = df.copy()
        df = self._encode_categoricals(df, fit=True)
        df = self._add_engineered_features(df)

        X = df[self.feature_columns].values
        y = df[TARGET_COLUMN].values

        X_scaled = self.scaler.fit_transform(X)
        self._fitted = True

        return train_test_split(
            X_scaled, y,
            test_size=model_config.test_size,
            random_state=model_config.random_state,
            stratify=y,
        )

    def _encode_categoricals(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        for col in CATEGORICAL_COLUMNS:
            if col not in df.columns:
                continue
            if fit:
                le = LabelEncoder()
                df[col + "_enc"] = le.fit_transform(df[col].astype(str))
                self.label_encoders[col] = le
            else:
                le = self.label_encoders.get(col)
                if le is None:
                    df[col + "_enc"] = 0
                else:
                    # Handle unseen labels
                    known = set(le.classes_)
                    df[col + "_enc"] = df[col].astype(str).apply(
                        lambda v: le.transform([v])[0] if v in known else 0
                    )
        return df

    def _add_engineered_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add derived features to the feature set."""
        # Log-scale amount (heavy right skew)
        df["log_amount"] = np.log1p(df["amount"])
        df["velocity_ratio"] = df["velocity_1h"] / (df["velocity_24h"] + 1)
        df["risk_score_raw"] = (
            df["is_high_risk_country"] * 2
            + df["is_high_risk_category"] * 2
            + df["is_night"]
            + df["is_international"]
            + df["failed_attempts_24h"] * 0.5
        )
        # Extend feature columns with engineered ones
        extra = ["log_amount", "velocity_ratio", "risk_score_raw"]
        for col in extra:
            if col not in self.feature_columns:
                self.feature_columns.append(col)
        return df

    # ------------------------------------------------------------------
    # Inference helpers
    # ------------------------------------------------------------------
    def transform_single(self, transaction: dict) -> np.ndarray:
        """Transform a single raw transaction dict for model inference."""
        if not self._fitted:
            raise RuntimeError("Preprocessor not fitted. Call fit_transform() first.")
        df = pd.DataFrame([transaction])
        df = self._encode_categoricals(df, fit=False)
        df = self._add_engineered_features(df)

        # Fill missing features with 0
        for col in self.feature_columns:
            if col not in df.columns:
                df[col] = 0

        X = df[self.feature_columns].values
        return self.scaler.transform(X)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save(self, path: str = None):
        path = path or model_config.scaler_path
        os.makedirs(os.path.dirname(path), exist_ok=True)
        joblib.dump(self, path)
        print(f"[Preprocessor] Saved to {path}")

    @staticmethod
    def load(path: str = None) -> "FraudPreprocessor":
        path = path or model_config.scaler_path
        preprocessor = joblib.load(path)
        print(f"[Preprocessor] Loaded from {path}")
        return preprocessor
