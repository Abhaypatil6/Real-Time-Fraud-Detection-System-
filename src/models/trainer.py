"""
Model training pipeline — generates data, fits ensemble, saves artifacts.
Run:  python -m src.models.trainer
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.data.generator import generate_dataset
from src.data.preprocessor import FraudPreprocessor
from src.models.ensemble_model import FraudEnsembleModel
from src.models.evaluator import evaluate_model, print_metrics


def train(n_samples: int = 50_000, fraud_ratio: float = 0.025):
    t0 = time.time()
    print("=" * 60)
    print("  FRAUD DETECTION PIPELINE - MODEL TRAINING")
    print("=" * 60)

    # 1. Generate dataset
    print("\n[1/4] Generating synthetic transaction dataset...")
    df = generate_dataset(n_samples=n_samples, fraud_ratio=fraud_ratio)

    # 2. Preprocess
    print("\n[2/4] Preprocessing features...")
    preprocessor = FraudPreprocessor()
    X_train, X_test, y_train, y_test = preprocessor.fit_transform(df)
    print(f"      Train: {X_train.shape} | Test: {X_test.shape}")
    print(f"      Features: {preprocessor.feature_columns}")

    # 3. Train ensemble
    print("\n[3/4] Training ensemble model (RF + GB)...")
    model = FraudEnsembleModel()
    model.fit(X_train, y_train)

    # 4. Evaluate
    print("\n[4/4] Evaluating on held-out test set...")
    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = evaluate_model(y_test, y_proba, model.threshold)
    print_metrics(metrics)

    # Save feature importance
    importance = model.get_feature_importance(preprocessor.feature_columns)
    os.makedirs("models", exist_ok=True)
    with open("models/feature_importance.json", "w") as f:
        json.dump(importance, f, indent=2)
    print("\n[Trainer] Saved feature_importance.json")

    # Save metrics
    with open("models/metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)
    print("[Trainer] Saved metrics.json")

    # Persist model & preprocessor
    model.save()
    preprocessor.save()

    elapsed = time.time() - t0
    print(f"\n[DONE] Training complete in {elapsed:.1f}s")
    print(f"   Model saved to: {os.path.abspath('models/ensemble_model.pkl')}")
    print("=" * 60)
    return model, preprocessor, metrics


if __name__ == "__main__":
    train()
