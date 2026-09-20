"""Unit test nhận diện / chuẩn hóa biển số, loại xe, phạt quá giờ."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.parking.penalty import compute_penalty
from src.parking.tickets import TicketStore
from src.vision.generate_plate_images import render_plate_image
from src.vision.plate_detect import find_plate_regions
from src.vision.plate_ocr import _assemble_from_items, is_valid_vn_plate, normalize_plate, plates_match
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


class TestPenalty(unittest.TestCase):
    def test_within_grace(self):
        result = compute_penalty(predicted_minutes=240, actual_minutes=250)
        self.assertFalse(result["is_overtime"])
        self.assertEqual(result["penalty_vnd"], 0)

    def test_overtime_tier(self):
        result = compute_penalty(predicted_minutes=240, actual_minutes=300)
        self.assertTrue(result["is_overtime"])
        self.assertGreater(result["penalty_vnd"], 0)


class TestTickets(unittest.TestCase):
    def test_open_and_mismatch_on_close(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            store = TicketStore(Path(tmp) / "t.db")
            opened = store.open_ticket({
                "student_id": "SV0001",
                "plate": "59B112345",
                "vehicle_type": "Motorbike",
                "entry_time": "2026-09-20 07:00:00",
                "predicted_behavior": "Full_Day",
                "duration_minutes": 240,
                "recommended_zone": "Khu B/C (Đỗ lâu)",
                "estimated_exit": "11:00 - 20/09/2026",
            })
            self.assertEqual(opened["status"], "open")
            found = store.find_open_by_plate("59B112345")
            self.assertIsNotNone(found)
            closed = store.close_ticket(opened["id"], {
                "exit_time": "2026-09-20 12:00:00",
                "exit_plate": "30A11111",
                "exit_vehicle_type": "Car",
                "plate_match": False,
                "vehicle_match": False,
                "overtime_minutes": 60,
                "penalty_vnd": 15000,
                "status": "alert",
                "alert_message": "Sai biển và loại xe",
            })
            self.assertEqual(closed["status"], "alert")
            self.assertEqual(closed["exit_plate"], "30A11111")


class TestAssembleAndDetect(unittest.TestCase):
    def test_two_line_motorbike_plate(self):
        plate, _ = _assemble_from_items([("59-B1", 0.9), ("123.45", 0.8)])
        self.assertEqual(plate, "59B112345")
        self.assertTrue(is_valid_vn_plate(plate))

    def test_find_region_on_synthetic_plate(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = render_plate_image("51A12345", "Car", Path(tmp) / "p.png")
            img = load_image(str(path))
            regions = find_plate_regions(img)
            self.assertGreaterEqual(len(regions), 1)
            self.assertIn("crop", regions[0])

    def test_render_and_preprocess(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            path = render_plate_image("59B112345", "Motorbike", Path(tmp) / "p.png")
            img = load_image(str(path))
            self.assertEqual(img.ndim, 3)
            prepared = preprocess_for_ocr(img)
            self.assertEqual(prepared.ndim, 3)


if __name__ == "__main__":
    unittest.main()
