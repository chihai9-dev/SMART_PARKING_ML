"""Unit test cho các hàm xử lý dữ liệu."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.clean_data import clean_parking_data
from src.data.generate_data import generate_smart_parking_data


class TestData(unittest.TestCase):
    def test_generate_includes_license_plate(self):
        df = generate_smart_parking_data(num_records=30, seed=1)
        self.assertIn("license_plate", df.columns)
        self.assertTrue(df["license_plate"].str.len().gt(0).all())

    def test_clean_normalizes_plate(self):
        df = generate_smart_parking_data(num_records=20, seed=2)
        df.loc[0, "license_plate"] = "59-B1 123.45"
        cleaned = clean_parking_data(df)
        self.assertEqual(cleaned.loc[0, "license_plate"], "59B112345")
        self.assertTrue((cleaned["duration_minutes"] >= 1).all())


if __name__ == "__main__":
    unittest.main()
