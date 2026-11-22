"""Các chỉ số đánh giá mô hình phân loại."""
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    f1_score, precision_score, recall_score,
)

def evaluate_classification(y_true, y_pred, labels=None) -> dict:
    labels = list(labels) if labels is not None else sorted(set(y_true) | set(y_pred))
    per_class_report = classification_report(
        y_true,
        y_pred,
        labels=labels,
        output_dict=True,
        zero_division=0,
    )
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "precision_macro": round(float(precision_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 4),
        "recall_macro": round(float(recall_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 4),
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "per_class": {
            str(label): {
                "precision": round(float(per_class_report[str(label)]["precision"]), 4),
                "recall": round(float(per_class_report[str(label)]["recall"]), 4),
                "f1_score": round(float(per_class_report[str(label)]["f1-score"]), 4),
                "support": int(per_class_report[str(label)]["support"]),
            }
            for label in labels
        },
        "labels": labels,
        "report": classification_report(y_true, y_pred, labels=labels, zero_division=0),
    }
