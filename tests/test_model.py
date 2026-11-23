"""Unit test huấn luyện và dự đoán Random Forest."""
import sys
import unittest
import hashlib
import json
import random
from pathlib import Path
from unittest.mock import patch
import numpy as np
from sklearn.tree import DecisionTreeClassifier
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.models.classification import (
    KNN_MODEL_PATH,
    load_knn_model,
    load_color_model,
    predict_plate_color,
    train_classification_model,
    train_knn_model,
    MODEL_PATH,
    _FALLBACK_PATH,
)
from src.models.tuning import tune_model
from src.features.feature_engineering import extract_plate_color_features
from train_plate_color import generate_synthetic_plate

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
        self.assertEqual(set(model.classes_), {"White", "Yellow"})

    def test_saved_knn_model_loads(self):
        model = load_knn_model()
        self.assertIsNotNone(model)
        self.assertEqual(set(model.classes_), {"White", "Yellow"})
        metadata_path = KNN_MODEL_PATH.with_name("model_metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        digest = hashlib.sha256(KNN_MODEL_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            metadata["comparison_model"]["model_sha256"], digest
        )

    def test_legacy_model_is_used_when_active_model_is_missing(self):
        with (
            patch("src.models.classification.MODEL_PATH", MODEL_PATH.with_name("missing.pkl")),
            patch("src.models.classification._FALLBACK_PATH", _FALLBACK_PATH),
        ):
            model = load_color_model()
        self.assertIsNone(model)

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

    def test_random_forest_and_knn_predict_the_same_crop(self):
        rng = random.Random(42)
        labels = ("White", "Yellow")
        samples = [
            (extract_plate_color_features(generate_synthetic_plate(label, rng))[0], label)
            for label in labels
            for _ in range(20)
        ]
        X = np.asarray([sample for sample, _ in samples])
        y = np.asarray([label for _, label in samples])
        forest = train_classification_model(X, y)
        knn = train_knn_model(X, y)
        image = np.full((64, 160, 3), (50, 210, 240), dtype=np.uint8)

        result = predict_plate_color(forest, image, comparison_model=knn)

        self.assertEqual(result["algorithm"], "RandomForestClassifier")
        self.assertEqual(result["color_code"], "Yellow")
        self.assertEqual(
            result["comparison"]["algorithm"], "KNeighborsClassifier"
        )
        self.assertEqual(result["comparison"]["color_code"], "Yellow")
        self.assertEqual(set(result["comparison"]["probabilities"]), set(labels))

    def test_blue_and_red_crops_are_reported_out_of_scope(self):
        rng = np.random.default_rng(42)
        centers = {
            "White": [0.8, 0, 0, 0, 0, 0.1, 0.9, 0.1, 0.1, 0.8],
            "Yellow": [0, 0.8, 0, 0, 0.15, 0.8, 0.8, 0.1, 0.1, 0],
        }
        X = np.vstack([
            rng.normal(center, 0.01, (20, 10))
            for center in centers.values()
        ])
        y = np.repeat(list(centers), 20)
        forest = train_classification_model(X, y)
        knn = train_knn_model(X, y)

        for plate_bgr in ((180, 50, 20), (20, 20, 190)):
            image = np.full((64, 160, 3), plate_bgr, dtype=np.uint8)
            result = predict_plate_color(forest, image, comparison_model=knn)
            self.assertEqual(result["color_code"], "Unknown")
            self.assertEqual(result["scope_status"], "unsupported_color")
            self.assertEqual(result["comparison"]["color_code"], "Unknown")


if __name__ == "__main__":
    unittest.main()
