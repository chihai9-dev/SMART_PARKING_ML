"""Unit test huấn luyện và dự đoán Random Forest."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.models.classification import (
    load_color_model,
    predict_plate_color,
    train_classification_model,
)

class TestModel(unittest.TestCase):
    def test_saved_color_model_loads(self):
        model = load_color_model()
        self.assertIsNotNone(model)
        self.assertEqual(set(model.classes_), {"White", "Yellow", "Blue", "Red"})

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
