"""Unit test cho nhan dien va chuan hoa bien so xe."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.vision.generate_plate_images import render_plate_image
from src.vision.plate_detect import find_plate_regions
from src.vision.plate_ocr import (
    _assemble_from_items,
    is_valid_vn_plate,
    normalize_plate,
    plates_match,
)
from src.vision.preprocess import load_image, preprocess_for_ocr
from src.vision.vehicle_type import infer_vehicle_type_from_plate, vehicle_types_match


class TestPlateNormalize(unittest.TestCase):
    def test_strips_separators(self):
        self.assertEqual(normalize_plate("59-B1 123.45"), "59B112345")
        self.assertEqual(normalize_plate("51A-123.45"), "51A12345")

    def test_ocr_digit_fix(self):
        self.assertEqual(normalize_plate("5O B112345")[:2], "50")

    def test_valid_vn_plate(self):
        self.assertTrue(is_valid_vn_plate("59B112345"))
        self.assertTrue(is_valid_vn_plate("51A12345"))
        self.assertFalse(is_valid_vn_plate("XYZ"))

    def test_plates_match(self):
        self.assertTrue(plates_match("59-B1 123.45", "59B112345"))
        self.assertFalse(plates_match("59B112345", "59B199999"))


class TestVehicleType(unittest.TestCase):
    def test_from_plate(self):
        self.assertEqual(infer_vehicle_type_from_plate("59B112345"), "Motorbike")
        self.assertEqual(infer_vehicle_type_from_plate("51A12345"), "Car")

    def test_types_match(self):
        self.assertTrue(vehicle_types_match("xe máy", "Motorbike"))
        self.assertFalse(vehicle_types_match("Motorbike", "Car"))


class TestAssembleAndDetect(unittest.TestCase):
    def test_two_line_motorbike_plate(self):
        plate, _ = _assemble_from_items([("59-B1", 0.9), ("123.45", 0.8)])
        self.assertEqual(plate, "59B112345")
        self.assertTrue(is_valid_vn_plate(plate))

    def test_find_region_on_synthetic_plate(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = render_plate_image("51A12345", "Car", Path(tmp) / "p.png")
            image = load_image(str(path))
            regions = find_plate_regions(image)
            self.assertGreaterEqual(len(regions), 1)
            self.assertIn("crop", regions[0])

    def test_render_and_preprocess(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = render_plate_image(
                "59B112345",
                "Motorbike",
                Path(tmp) / "p.png",
            )
            image = load_image(str(path))
            self.assertEqual(image.ndim, 3)
            prepared = preprocess_for_ocr(image)
            self.assertEqual(prepared.ndim, 3)


if __name__ == "__main__":
    unittest.main()
