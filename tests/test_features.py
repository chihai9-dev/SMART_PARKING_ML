"""Unit test trích xuất 10 đặc trưng HSV."""
import sys
import unittest
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.features.feature_engineering import FEATURE_NAMES, extract_plate_color_features

class TestFeatures(unittest.TestCase):
    def test_extract_10_hsv_features(self):
        image = np.full((64, 160, 3), (50, 210, 240), dtype=np.uint8)
        vector, values = extract_plate_color_features(image)
        self.assertEqual(len(vector), len(FEATURE_NAMES))
        self.assertEqual(len(FEATURE_NAMES), 10)
        self.assertGreater(values["yellow_ratio"], 0.8)

    def test_empty_image_raises(self):
        with self.assertRaises(ValueError):
            extract_plate_color_features(np.array([]))

if __name__ == "__main__":
    unittest.main()
