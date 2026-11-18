import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.alpr_benchmark import (
    _bbox_from_row,
    _read_manifest,
    character_error_rate,
    intersection_over_union,
)


class TestAlprBenchmark(unittest.TestCase):
    def test_exact_plate_has_zero_character_error(self):
        self.assertEqual(character_error_rate("59-B1 123.45", "59B112345"), 0.0)

    def test_character_error_is_normalized_by_expected_length(self):
        self.assertAlmostEqual(character_error_rate("51A12345", "51A12346"), 0.125)

    def test_bbox_iou(self):
        self.assertEqual(intersection_over_union([0, 0, 10, 10], [0, 0, 10, 10]), 1.0)
        self.assertEqual(intersection_over_union([0, 0, 10, 10], [20, 20, 5, 5]), 0.0)
        self.assertEqual(intersection_over_union([0, 0, 10, 10], None), 0.0)

    def test_blank_bbox_is_optional(self):
        row = pd.Series({"bbox_x": "", "bbox_y": "", "bbox_width": "", "bbox_height": ""})
        self.assertIsNone(_bbox_from_row(row))

    def test_benchmark_rejects_synthetic_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            pd.DataFrame([{
                "image_path": "plate.png",
                "plate_true": "51A12345",
                "source": "synthetic",
            }]).to_csv(path, index=False)
            with self.assertRaisesRegex(ValueError, "real images only"):
                _read_manifest(path)


if __name__ == "__main__":
    unittest.main()
