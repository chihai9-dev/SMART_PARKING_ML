from io import BytesIO
import random
import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.app import _confidence_for_backend, app
from train_plate_color import generate_synthetic_plate


class TestBackendConfidence(unittest.TestCase):
    def test_preserves_zero_ocr_confidence(self):
        self.assertEqual(_confidence_for_backend({"confidence": 0.0}), 0.0)

    def test_uses_default_only_when_confidence_is_missing_or_none(self):
        self.assertEqual(_confidence_for_backend({}), 1.0)
        self.assertEqual(_confidence_for_backend({"confidence": None}), 1.0)

    def test_color_endpoint_classifies_uploaded_plate(self):
        image = generate_synthetic_plate("Yellow", random.Random(42))
        encoded, buffer = cv2.imencode(".jpg", image)
        self.assertTrue(encoded)

        response = app.test_client().post(
            "/api/classify-plate-color",
            data={"image": (BytesIO(buffer.tobytes()), "plate.jpg")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["color_code"], "Yellow")


if __name__ == "__main__":
    unittest.main()
