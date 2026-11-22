"""Random Forest phan loai mau nen bien so: White / Yellow / Blue / Red."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any
import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from src.features.feature_engineering import FEATURE_NAMES, extract_plate_color_features

ROOT_DIR = Path(__file__).resolve().parents[2]
# Model màu được huấn luyện và ghi metadata bởi train_plate_color.py.
MODEL_PATH = ROOT_DIR / "models" / "classification" / "plate_color_model.pkl"
KNN_MODEL_PATH = (
    ROOT_DIR / "models" / "classification" / "plate_color_knn_model.pkl"
)
_FALLBACK_PATH = ROOT_DIR / "models" / "classification" / "best_classification_model.pkl"

LOGGER = logging.getLogger(__name__)

COLOR_LABELS_VI = {
    "White": "Biển Trắng (Dân sự)",
    "Yellow": "Biển Vàng (Kinh doanh vận tải)",
    "Blue": "Biển Xanh (Cơ quan Nhà nước)",
    "Red": "Biển Đỏ (Quân đội)",
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


def train_knn_model(X_train, y_train) -> Pipeline:
    model = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "classifier",
                KNeighborsClassifier(n_neighbors=5, weights="distance"),
            ),
        ]
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


def load_knn_model(
    model_path: Path | str | None = None,
) -> Pipeline | None:
    path = Path(model_path) if model_path is not None else KNN_MODEL_PATH
    if not path.is_file():
        return None
    try:
        model = joblib.load(path)
    except (OSError, ValueError, EOFError, ImportError, KeyError) as exc:
        LOGGER.warning("Khong the tai KNN model %s: %s", path, exc)
        return None
    if (
        not isinstance(model, Pipeline)
        or not isinstance(model.named_steps.get("classifier"), KNeighborsClassifier)
        or not _is_valid_color_model(model)
    ):
        LOGGER.warning("KNN model %s khong hop le.", path)
        return None
    LOGGER.info("Loaded plate color KNN model from %s", path)
    return model


def load_color_model(model_path: Path | str | None = None) -> RandomForestClassifier | None:
    """
    Load the requested model, then the active model, then the legacy artifact.
    """
    candidates = []
    if model_path is not None:
        candidates.append(Path(model_path))
    candidates.extend((MODEL_PATH, _FALLBACK_PATH))

    candidates = list(dict.fromkeys(candidates))

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
    comparison_model: Pipeline | None = None,
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
        if comparison_model is not None:
            comparison_probabilities = comparison_model.predict_proba([vector])[0]
            comparison_classes = list(comparison_model.classes_)
            comparison_best_idx = int(np.argmax(comparison_probabilities))
            comparison_code = str(comparison_classes[comparison_best_idx])
            result["comparison"] = {
                "algorithm": "KNeighborsClassifier",
                "color_code": comparison_code,
                "color_label": COLOR_LABELS_VI.get(comparison_code, comparison_code),
                "confidence": round(
                    float(comparison_probabilities[comparison_best_idx]), 4
                ),
                "probabilities": {
                    str(color): round(float(probability), 4)
                    for color, probability in zip(
                        comparison_classes, comparison_probabilities
                    )
                },
            }
    except Exception as exc:
        LOGGER.warning("Loi khi du doan mau bien so: %s", exc)

    return result
