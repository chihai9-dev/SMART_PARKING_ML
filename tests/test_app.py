from io import BytesIO
import random
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        payload = response.get_json()
        self.assertEqual(payload["color_code"], "Yellow")
        self.assertEqual(
            payload["comparison"]["algorithm"], "KNeighborsClassifier"
        )

    def test_scan_persists_structured_color_and_zero_confidence(self):
        color = {
            "color_code": "Yellow",
            "color_label": "Biển Vàng",
            "confidence": 0.87,
        }
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch("app.app.SCAN_DIR", Path(tmp)),
                patch("app.app.recognize_plate", return_value={
                    "plate": "51A12345",
                    "valid": True,
                    "confidence": 0.0,
                    "engine": "test",
                    "bbox": [0, 0, 10, 10],
                }),
                patch("app.app._classify_crop_b64", return_value=color),
                patch("app.app._read_algorithm_comparison", return_value={
                    "evaluation_source": "real",
                    "algorithms": {
                        "RandomForestClassifier": {"metrics": {"accuracy": 0.9}},
                        "KNeighborsClassifier": {"metrics": {"accuracy": 0.85}},
                    },
                }),
                patch("app.app._backend_request", return_value={}) as backend_request,
            ):
                response = app.test_client().post(
                    "/api/scan-plate",
                    data={"image": (BytesIO(b"image-bytes"), "plate.jpg")},
                    content_type="multipart/form-data",
                )

        self.assertEqual(response.status_code, 200)
        payload = backend_request.call_args.kwargs["payload"]
        self.assertEqual(payload["confidence"], 0.0)
        self.assertEqual(payload["plateColorCode"], "Yellow")
        self.assertEqual(payload["plateColorLabel"], "Biển Vàng")
        self.assertEqual(payload["plateColorConfidence"], 0.87)
        response_payload = response.get_json()
        self.assertIn("RandomForestClassifier", response_payload["algorithm_comparison"]["algorithms"])
        self.assertIn("KNeighborsClassifier", response_payload["algorithm_comparison"]["algorithms"])


if __name__ == "__main__":
    unittest.main()
