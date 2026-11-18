"""Unit test huấn luyện và dự đoán Random Forest."""
import sys
import unittest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
from sklearn.tree import DecisionTreeClassifier
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.models.classification import (
    load_color_model,
    predict_plate_color,
    train_classification_model,
    MODEL_PATH,
    _FALLBACK_PATH,
)
from src.models.tuning import tune_model

class TestModel(unittest.TestCase):
    def test_tune_model_returns_fitted_best_estimator(self):
        X = np.array([[0.0], [0.1], [0.2], [1.0], [1.1], [1.2], [2.0], [2.1], [2.2]])
        y = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
        model = tune_model(
            DecisionTreeClassifier(random_state=42),
            {"max_depth": [1, 2, 3]},
            X,
            y,
            cv=3,
            n_jobs=1,
        )

        np.testing.assert_array_equal(model.predict(X), y)

    def test_saved_color_model_loads(self):
        model = load_color_model()
        self.assertIsNotNone(model)
        self.assertEqual(set(model.classes_), {"White", "Yellow", "Blue", "Red"})

    def test_legacy_model_is_used_when_active_model_is_missing(self):
        with (
            patch("src.models.classification.MODEL_PATH", MODEL_PATH.with_name("missing.pkl")),
            patch("src.models.classification._FALLBACK_PATH", _FALLBACK_PATH),
        ):
            model = load_color_model()
        self.assertIsNotNone(model)
        self.assertEqual(set(model.classes_), {"White", "Yellow", "Blue", "Red"})

    def test_metadata_hash_matches_active_model(self):
        metadata_path = MODEL_PATH.with_name("model_metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
        self.assertEqual(metadata["model_artifact"], MODEL_PATH.name)
        self.assertEqual(metadata["model_sha256"], digest)

    def test_invalid_model_file_is_ignored(self):
        model_path = Path(__file__).resolve().parents[1] / "models" / "classification" / "best_classification_model.pkl"
        with patch("src.models.classification.joblib.load", side_effect=KeyError("invalid pickle")):
            self.assertIsNone(load_color_model(model_path))

    def test_train_and_predict_plate_color(self):
        rng = np.random.default_rng(42)
        white = rng.normal([0.8,0,0,0,0,0.1,0.9,0.1,0.1,0.8], 0.02, (30,10))
        yellow = rng.normal([0,0.8,0,0,0.15,0.8,0.8,0.1,0.1,0], 0.02, (30,10))
        model = train_classification_model(
            np.vstack([white, yellow]), np.array(["White"]*30 + ["Yellow"]*30)
        )
        image = np.full((64,160,3), (50,210,240), dtype=np.uint8)
        result = predict_plate_color(model, image)
        self.assertEqual(result["color_code"], "Yellow")
        self.assertEqual(result["algorithm"], "RandomForestClassifier")

if __name__ == "__main__":
    unittest.main()
