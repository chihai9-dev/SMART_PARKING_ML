"""Random Forest phan loai mau nen bien so: White / Yellow / Blue / Red."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from src.features.feature_engineering import FEATURE_NAMES, extract_plate_color_features

ROOT_DIR = Path(__file__).resolve().parents[2]
# Dung model mau bien so da duoc train
MODEL_PATH = ROOT_DIR / "models" / "classification" / "plate_color_model.pkl"
# Fallback sang best_classification_model neu plate_color_model chua co
_FALLBACK_PATH = ROOT_DIR / "models" / "classification" / "best_classification_model.pkl"

LOGGER = logging.getLogger(__name__)

COLOR_LABELS_VI = {
    "White":  "Bien Trang (Dan su)",
    "Yellow": "Bien Vang (Kinh doanh van tai)",
    "Blue":   "Bien Xanh (Co quan Nha nuoc)",
    "Red":    "Bien Do (Quan doi)",
}


def train_classification_model(
    X_train, y_train, random_state: int = 42
) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=4,
        class_weight="balanced",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


def _is_valid_color_model(model) -> bool:
    """Kiem tra model co dung dinh dang phan loai mau bien so khong."""
    expected = {"White", "Yellow", "Blue", "Red"}
    actual = set(map(str, getattr(model, "classes_", [])))
    return (
        hasattr(model, "predict_proba")
        and actual == expected
        and getattr(model, "n_features_in_", None) == len(FEATURE_NAMES)
    )


def load_color_model(model_path: Path | str | None = None) -> RandomForestClassifier | None:
    """
    Tai model phan loai mau bien so.
    Thu tu uu tien: plate_color_model.pkl -> duong dan truyen vao -> fallback.
    """
    candidates = [MODEL_PATH]
    if model_path is not None:
        candidates.insert(0, Path(model_path))

    for path in candidates:
        if not path.is_file():
            continue
        try:
            model = joblib.load(path)
            if _is_valid_color_model(model):
                LOGGER.info("Loaded plate color model from %s", path)
                return model
            LOGGER.warning(
                "Model %s khong hop le (classes/features khong khop).", path
            )
        except (OSError, ValueError, EOFError, ImportError, KeyError) as exc:
            LOGGER.warning("Khong the tai model %s: %s", path, exc)

    return None


def predict_plate_color(
    model: Any = None,
    crop_bgr: np.ndarray | None = None,
) -> dict[str, Any]:
    """
    Du doan mau nen bien so tu anh crop BGR.
    Ho tro ca:
      - predict_plate_color(model, crop_bgr)
      - predict_plate_color(crop_bgr) (tu dong load model mac dinh)
    Tra ve dict voi cac key: color_code, color_label, confidence, probabilities.
    """
    if isinstance(model, np.ndarray) and crop_bgr is None:
        crop_bgr = model
        model = load_color_model()
    elif model is None:
        model = load_color_model()

    result: dict[str, Any] = {
        "color_code": "Unknown",
        "color_label": "Chua phan loai duoc mau bien so",
        "confidence": 0.0,
        "probabilities": {},
        "features": {},
        "feature_names": FEATURE_NAMES,
        "algorithm": "RandomForestClassifier",
    }

    try:
        vector, features = extract_plate_color_features(crop_bgr)
        result["features"] = features
    except (ValueError, TypeError) as exc:
        LOGGER.warning("Khong the trich xuat dac trung mau: %s", exc)
        return result

    if model is None:
        result["color_label"] = "Chua co mo hinh phan loai mau"
        return result

    try:
        probabilities = model.predict_proba([vector])[0]
        classes = list(model.classes_)
        best_idx = int(np.argmax(probabilities))
        code = str(classes[best_idx])
        confidence = round(float(probabilities[best_idx]), 4)

        result.update({
            "color_code": code,
            "color_label": COLOR_LABELS_VI.get(code, code),
            "confidence": confidence,
            "probabilities": {
                str(c): round(float(p), 4)
                for c, p in zip(classes, probabilities)
            },
        })
    except Exception as exc:
        LOGGER.warning("Loi khi du doan mau bien so: %s", exc)

    return result
