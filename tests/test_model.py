"""Unit test huấn luyện và dự đoán Random Forest."""
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.models.classification import predict_plate_color, train_classification_model


class TestModel(unittest.TestCase):
    def test_train_and_predict_plate_color(self):
        rng = np.random.default_rng(42)
        white = rng.normal(
            [0.8, 0.0, 0.0, 0.0, 0.0, 0.1, 0.9, 0.1, 0.1, 0.8],
            0.02, (30, 10)
        )
        yellow = rng.normal(
            [0.0, 0.8, 0.0, 0.0, 0.15, 0.8, 0.8, 0.1, 0.1, 0.0],
            0.02, (30, 10)
        )
        X = np.vstack([white, yellow])
        y = np.array(["White"] * 30 + ["Yellow"] * 30)
        model = train_classification_model(X, y)

        yellow_image = np.full((64, 160, 3), (50, 210, 240), dtype=np.uint8)
        result = predict_plate_color(model, yellow_image)
        self.assertEqual(result["color_code"], "Yellow")
        self.assertEqual(result["algorithm"], "RandomForestClassifier")
        self.assertGreaterEqual(result["confidence"], 0.0)


if __name__ == "__main__":
    unittest.main()
