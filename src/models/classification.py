"""Random Forest phân loại màu nền biển số: White / Yellow / Blue / Red."""
from __future__ import annotations
from pathlib import Path
from typing import Any
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from src.features.feature_engineering import FEATURE_NAMES, extract_plate_color_features

ROOT_DIR = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT_DIR / "models" / "classification" / "best_classification_model.pkl"
COLOR_LABELS_VI = {
    "White": "Biển Trắng (Dân sự)",
    "Yellow": "Biển Vàng (Kinh doanh vận tải)",
    "Blue": "Biển Xanh (Cơ quan Nhà nước)",
    "Red": "Biển Đỏ (Quân đội)",
}

def train_classification_model(X_train, y_train, random_state: int = 42) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=120, max_depth=12, min_samples_split=4,
        class_weight="balanced", random_state=random_state, n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model

def load_color_model(model_path: Path | str = MODEL_PATH) -> RandomForestClassifier | None:
    path = Path(model_path)
    if not path.is_file():
        return None
    try:
        model = joblib.load(path)
        expected = {"White", "Yellow", "Blue", "Red"}
        actual = set(map(str, getattr(model, "classes_", [])))
        if (not hasattr(model, "predict_proba") or actual != expected
                or getattr(model, "n_features_in_", None) != len(FEATURE_NAMES)):
            return None
        return model
    except (OSError, ValueError, EOFError, ImportError):
        return None

def predict_plate_color(model: RandomForestClassifier | None, crop_bgr: np.ndarray) -> dict[str, Any]:
    vector, features = extract_plate_color_features(crop_bgr)
    result = {
        "color_code": "Unknown",
        "color_label": "Chưa có mô hình phân loại màu",
        "confidence": 0.0,
        "probabilities": {},
        "features": features,
        "feature_names": FEATURE_NAMES,
        "algorithm": "RandomForestClassifier",
    }
    if model is None:
        return result
    probabilities = model.predict_proba([vector])[0]
    classes = list(model.classes_)
    best = int(np.argmax(probabilities))
    code = str(classes[best])
    result.update({
        "color_code": code,
        "color_label": COLOR_LABELS_VI.get(code, code),
        "confidence": round(float(probabilities[best]), 4),
        "probabilities": {str(c): round(float(p), 4) for c, p in zip(classes, probabilities)},
    })
    return result
