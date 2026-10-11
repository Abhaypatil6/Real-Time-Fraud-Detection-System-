"""
Model evaluation utilities — precision, recall, F1, AUC-ROC, confusion matrix.
"""
import numpy as np
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    average_precision_score,
    precision_recall_curve,
    f1_score,
    precision_score,
    recall_score,
)


def evaluate_model(y_true: np.ndarray, y_proba: np.ndarray, threshold: float = 0.45) -> dict:
    """
    Compute comprehensive fraud detection metrics.

    Args:
        y_true:    Ground-truth labels (0/1)
        y_proba:   Fraud probability scores from the model
        threshold: Decision threshold for binary classification

    Returns:
        dict with all key metrics
    """
    y_pred = (y_proba >= threshold).astype(int)

    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    roc_auc = roc_auc_score(y_true, y_proba)
    avg_precision = average_precision_score(y_true, y_proba)
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0

    # False-positive reduction vs. naive model (baseline = all predictions positive)
    baseline_fp = int(y_true.sum())  # baseline: flag everything as fraud
    fp_reduction_pct = round((1 - fp / max(baseline_fp, 1)) * 100, 1)

    return {
        "threshold": threshold,
        "total_transactions": int(len(y_true)),
        "total_fraud": int(y_true.sum()),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "true_negatives": int(tn),
        "false_negatives": int(fn),
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1_score": round(float(f1), 4),
        "roc_auc": round(float(roc_auc), 4),
        "avg_precision_score": round(float(avg_precision), 4),
        "false_positive_rate": round(float(fpr), 4),
        "false_negative_rate": round(float(fnr), 4),
        "specificity": round(float(specificity), 4),
        "fp_reduction_vs_baseline_pct": fp_reduction_pct,
    }


def print_metrics(metrics: dict):
    """Pretty-print evaluation metrics."""
    sep = "-" * 50
    print("\n" + sep)
    print("  MODEL EVALUATION RESULTS")
    print(sep)
    print(f"  Transactions tested : {metrics['total_transactions']:,}")
    print(f"  True fraud cases    : {metrics['total_fraud']:,}")
    print(f"  Threshold           : {metrics['threshold']}")
    print(sep)
    print(f"  True  Positives     : {metrics['true_positives']:,}")
    print(f"  False Positives     : {metrics['false_positives']:,}")
    print(f"  True  Negatives     : {metrics['true_negatives']:,}")
    print(f"  False Negatives     : {metrics['false_negatives']:,}")
    print(sep)
    print(f"  Precision           : {metrics['precision']:.4f}")
    print(f"  Recall              : {metrics['recall']:.4f}")
    print(f"  F1 Score            : {metrics['f1_score']:.4f}")
    print(f"  ROC-AUC             : {metrics['roc_auc']:.4f}")
    print(f"  Avg Precision (AP)  : {metrics['avg_precision_score']:.4f}")
    print(f"  Specificity         : {metrics['specificity']:.4f}")
    print(f"  False Positive Rate : {metrics['false_positive_rate']:.4f}")
    print(f"  False Negative Rate : {metrics['false_negative_rate']:.4f}")
    print(sep)
    print(f"  FP Reduction vs Base: {metrics['fp_reduction_vs_baseline_pct']}%")
    print(sep + "\n")
