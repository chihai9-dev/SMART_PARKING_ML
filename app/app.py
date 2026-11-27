from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import base64
import json
import cv2
import numpy as np
import os
import ssl
import sys

from flask import Flask, jsonify, redirect, request, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.openapi import OPENAPI_SPEC
from src.models.classification import (
    load_color_model,
    load_knn_model,
    predict_plate_color,
)
from src.vision.plate_ocr import normalize_plate, recognize_plate


app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
SWAGGER_CORS_ORIGINS = {
    "http://localhost:5049",
    "http://127.0.0.1:5049",
    "https://localhost:7298",
    "https://127.0.0.1:7298",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
}


@app.after_request
def add_swagger_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in SWAGGER_CORS_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Max-Age"] = "600"
        response.headers.add("Vary", "Origin")
    return response

SCAN_DIR = ROOT_DIR / "data" / "processed" / "scans"
SCAN_DIR.mkdir(parents=True, exist_ok=True)

COLOR_MODEL_META_PATH = ROOT_DIR / "models" / "classification" / "model_metadata.json"
ALGORITHM_COMPARISON_PATH = ROOT_DIR / "outputs" / "results" / "algorithm_comparison.json"
color_model = load_color_model()
knn_color_model = load_knn_model()

SMARTPARKING_API_URL = os.getenv(
    "SMARTPARKING_API_URL",
    "http://127.0.0.1:5049",
).rstrip("/")


class BackendApiError(Exception):
    def __init__(self, status_code: int, message: str, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.body = body


def _backend_ssl_context():
    if SMARTPARKING_API_URL.startswith(
        ("https://localhost", "https://127.0.0.1")
    ):
        return ssl._create_unverified_context()
    return None


def _http_json_request(method: str, url: str, payload=None):
    headers = {"Accept": "application/json"}
    body = None

    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(
        url,
        data=body,
        headers=headers,
        method=method.upper(),
    )

    try:
        context = _backend_ssl_context()
        if context is not None:
            response = urlopen(req, timeout=20, context=context)
        else:
            response = urlopen(req, timeout=20)

        with response:
            raw = response.read().decode("utf-8")

        if not raw:
            return {}

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}

    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body_data = json.loads(raw)
        except json.JSONDecodeError:
            body_data = {"message": raw}

        message = (
            body_data.get("message")
            or body_data.get("title")
            or "Backend trả HTTP {}.".format(exc.code)
        )
        raise BackendApiError(exc.code, message, body_data) from exc

    except URLError as exc:
        raise BackendApiError(
            0,
            (
                "Không thể kết nối SmartParking Backend. "
                "Địa chỉ hiện tại: {}. Chi tiết: {}".format(
                    SMARTPARKING_API_URL,
                    exc.reason,
                )
            ),
        ) from exc


def _backend_request(method: str, path: str, payload=None):
    return _http_json_request(
        method,
        "{}{}".format(SMARTPARKING_API_URL, path),
        payload,
    )


def _backend_error_response(exc: BackendApiError):
    status_code = exc.status_code
    if status_code < 400 or status_code > 599:
        status_code = 503

    return jsonify(
        {
            "status": "error",
            "message": exc.message,
            "backend": SMARTPARKING_API_URL,
        }
    ), status_code


def _confidence_for_backend(ocr: dict) -> float:
    confidence = ocr.get("confidence")
    return float(1.0 if confidence is None else confidence)


_scan_history = []


def _save_scan_record(record: dict):
    _scan_history.insert(0, record)
    if len(_scan_history) > 100:
        del _scan_history[100:]


def _classify_crop_b64(crop_b64: str | None) -> dict:
    if not crop_b64:
        return {}
    try:
        raw = base64.b64decode(crop_b64, validate=True)
        arr = np.frombuffer(raw, dtype=np.uint8)
        crop_bgr = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if crop_bgr is None:
            return {}
        return predict_plate_color(
            color_model,
            crop_bgr,
            comparison_model=knn_color_model,
        )
    except Exception as exc:
        print("[Warning] Không thể phân loại màu biển số: {}".format(exc))
        return {}


def _safe_upload_name(filename: str):
    name = Path(filename).name
    safe = "".join(
        char if char.isalnum() or char in ".-_" else "_"
        for char in name
    )
    return safe[:80] or "plate-image.jpg"


@app.route("/")
@app.route("/dashboard")
@app.route("/history")
def frontend_redirect():
    return redirect("http://localhost:5173/", code=302)


@app.route("/openapi.json")
def openapi_json():
    return jsonify(OPENAPI_SPEC)


@app.route("/api/model-info")
def model_info():
    if COLOR_MODEL_META_PATH.is_file():
        try:
            data = json.loads(COLOR_MODEL_META_PATH.read_text(encoding="utf-8"))
            return jsonify({"status": "success", "model": data})
        except (OSError, json.JSONDecodeError) as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500
    return jsonify({
        "status": "error",
        "message": "Chưa có metadata mô hình. Hãy chạy: python train_plate_color.py",
    }), 404


@app.route("/api/classify-plate-color", methods=["POST"])
def classify_plate_color_only():
    uploaded = request.files.get("image")
    if not uploaded or not uploaded.filename:
        return jsonify({"status": "error", "message": "Hãy gửi kèm file ảnh vùng biển số."}), 400
    image_bytes = uploaded.read()
    if not image_bytes:
        return jsonify({"status": "error", "message": "File ảnh không có dữ liệu."}), 400
    image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        return jsonify({"status": "error", "message": "Không giải mã được file ảnh."}), 400
    try:
        return jsonify({
            "status": "success",
            **predict_plate_color(
                color_model,
                image,
                comparison_model=knn_color_model,
            ),
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


def _read_algorithm_comparison():
    if not ALGORITHM_COMPARISON_PATH.is_file():
        return None
    try:
        return json.loads(
            ALGORITHM_COMPARISON_PATH.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        print("[Warning] Không đọc được báo cáo so sánh mô hình: {}".format(exc))
        return None


@app.route("/api/scan-plate", methods=["POST"])
def scan_plate():
    try:
        uploaded = request.files.get("image")
        if not uploaded or not uploaded.filename:
            return jsonify(
                {
                    "status": "error",
                    "message": "Hãy chọn một ảnh có biển số xe.",
                }
            ), 400

        image_bytes = uploaded.read()
        if not image_bytes:
            return jsonify(
                {
                    "status": "error",
                    "message": "File ảnh không có dữ liệu.",
                }
            ), 400

        ocr = recognize_plate(image_bytes)
        detected_plate = normalize_plate(ocr.get("plate") or "")
        plate_color = _classify_crop_b64(ocr.get("crop_jpeg_b64"))
        color_label = plate_color.get("color_label") or "Chưa phân loại màu biển số"

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe_filename = _safe_upload_name(uploaded.filename)
        image_path = SCAN_DIR / "{}_{}".format(stamp, safe_filename)
        image_path.write_bytes(image_bytes)

        crop_path = ""
        crop_base64 = ocr.get("crop_jpeg_b64")
        if crop_base64:
            crop_file = SCAN_DIR / "{}_crop.jpg".format(stamp)
            crop_file.write_bytes(base64.b64decode(crop_base64))
            crop_path = str(crop_file)

        record = {
            "id": stamp,
            "plate": detected_plate,
            "valid": ocr.get("valid"),
            "confidence": ocr.get("confidence"),
            "engine": ocr.get("engine"),
            "source_filename": uploaded.filename,
            "image_path": str(image_path),
            "crop_path": crop_path,
            "plate_color": plate_color,
            "extra": {
                "bbox": ocr.get("bbox"),
                "raw_candidates": ocr.get("raw_candidates"),
                "message": ocr.get("message"),
            },
        }
        _save_scan_record(record)

        database_saved = False
        database_message = None

        if detected_plate:
            try:
                _backend_request(
                    "POST",
                    "/api/PlateScans",
                    payload={
                        "plate": detected_plate,
                        "confidence": _confidence_for_backend(ocr),
                        "imagePath": "/scan-image/{}".format(image_path.name),
                        "cropImagePath": (
                            "/scan-image/{}".format(Path(crop_path).name)
                            if crop_path
                            else None
                        ),
                        "plateColorCode": (
                            plate_color.get("color_code")
                            if plate_color.get("color_code") != "Unknown"
                            else None
                        ),
                        "plateColorLabel": (
                            plate_color.get("color_label")
                            if plate_color.get("color_code") != "Unknown"
                            else None
                        ),
                        "plateColorConfidence": (
                            plate_color.get("confidence")
                            if plate_color.get("color_code") != "Unknown"
                            else None
                        ),
                        "note": "{} | {}".format(ocr.get("engine") or "Plate OCR", color_label),
                    },
                )
                database_saved = True
            except BackendApiError as exc:
                database_message = exc.message
                print(
                    "[Warning] Không thể lưu lượt nhận diện vào SQL Server: {}".format(
                        exc.message
                    )
                )

        return jsonify(
            {
                "status": "success",
                "plate": detected_plate or None,
                "valid": ocr.get("valid"),
                "confidence": ocr.get("confidence"),
                "engine": ocr.get("engine"),
                "message": ocr.get("message"),
                "plate_color": plate_color,
                "algorithm_comparison": _read_algorithm_comparison(),
                "raw_candidates": ocr.get("raw_candidates", []),
                "bbox": ocr.get("bbox"),
                "crop_jpeg_b64": ocr.get("crop_jpeg_b64"),
                "annotated_jpeg_b64": ocr.get("annotated_jpeg_b64"),
                "saved": record,
                "image_path": str(image_path),
                "crop_path": crop_path,
                "database_saved": database_saved,
                "database_message": database_message,
            }
        )

    except BackendApiError as exc:
        return _backend_error_response(exc)

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


@app.route("/scan-image/<path:filename>")
def get_scan_image(filename):
    safe_name = Path(filename).name
    if not safe_name:
        return jsonify(
            {
                "status": "error",
                "message": "Tên ảnh không hợp lệ.",
            }
        ), 400

    image_path = SCAN_DIR / safe_name
    if not image_path.is_file():
        return jsonify(
            {
                "status": "error",
                "message": "Không tìm thấy ảnh nhận diện.",
            }
        ), 404

    return send_from_directory(SCAN_DIR, safe_name)


@app.route("/api/preview-plate", methods=["POST"])
def preview_plate():
    try:
        uploaded = request.files.get("image")
        if not uploaded or not uploaded.filename:
            return jsonify(
                {
                    "status": "error",
                    "message": "Không có ảnh camera.",
                }
            ), 400

        image_bytes = uploaded.read()
        if not image_bytes:
            return jsonify(
                {
                    "status": "error",
                    "message": "Frame camera không có dữ liệu.",
                }
            ), 400

        ocr = recognize_plate(image_bytes)
        plate = normalize_plate(ocr.get("plate") or "")
        plate_color = _classify_crop_b64(ocr.get("crop_jpeg_b64"))

        return jsonify(
            {
                "status": "success",
                "plate": plate,
                "valid": bool(ocr.get("valid")),
                "confidence": ocr.get("confidence", 0),
                "engine": ocr.get("engine", "none"),
                "message": ocr.get("message", ""),
                "plate_color": plate_color,
                "bbox": ocr.get("bbox"),
                "annotated_jpeg_b64": ocr.get("annotated_jpeg_b64"),
                "crop_jpeg_b64": ocr.get("crop_jpeg_b64"),
            }
        )

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


@app.route("/api/scans")
def list_scans():
    return jsonify(
        {
            "status": "success",
            "scans": _scan_history,
        }
    )


if __name__ == "__main__":
    print("==================================================")
    print(" ALPR System - Nhận diện biển số & phân loại màu")
    print(" YOLO/OCR + RandomForest Color Classifier + .NET API")
    print("==================================================")
    print("Backend: {}".format(SMARTPARKING_API_URL))
    print("Python: http://127.0.0.1:5000")
    print("==================================================")
    app.run(debug=True, port=5000)
