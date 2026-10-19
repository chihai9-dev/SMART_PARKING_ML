from flask import Flask, redirect, request, jsonify, send_from_directory

from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import base64
import json
import os
import ssl
import sys
import threading
import time

import pandas as pd
import joblib


# ============================================================
# PATH
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# ============================================================
# EXISTING ML / OCR / PARKING MODULES
# ============================================================

from src.parking.penalty import compute_penalty
from src.vision.plate_ocr import (
    is_valid_vn_plate,
    normalize_plate,
    plates_match,
    recognize_plate,
)
from src.vision.vehicle_type import (
    canonicalize_vehicle_type,
    infer_vehicle_type,
    vehicle_types_match,
)


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024


# ============================================================
# LOCAL IMAGE DIRECTORIES
# ============================================================

SCAN_DIR = Path(ROOT_DIR) / "data" / "processed" / "scans"
TICKET_IMAGE_DIR = Path(ROOT_DIR) / "data" / "processed" / "ticket_images"

SCAN_DIR.mkdir(parents=True, exist_ok=True)
TICKET_IMAGE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# .NET BACKEND CONFIGURATION
# ============================================================

# Backend hiện tại của bạn chạy tại:
# http://localhost:5049
#
# Nếu sau này backend chạy port khác:
#
# PowerShell:
# $env:SMARTPARKING_API_URL="http://localhost:PORT"
#
SMARTPARKING_API_URL = os.getenv(
    "SMARTPARKING_API_URL",
    "http://localhost:5049",
).rstrip("/")

SMARTPARKING_USERNAME = os.getenv(
    "SMARTPARKING_USERNAME",
    "admin",
)

SMARTPARKING_PASSWORD = os.getenv(
    "SMARTPARKING_PASSWORD",
    "123456",
)


class BackendApiError(Exception):
    def __init__(self, status_code, message, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.body = body


_backend_token = None
_backend_token_expires_at = 0.0
_backend_token_lock = threading.Lock()


def _backend_ssl_context():
    """
    Cho phép Flask Python gọi .NET HTTPS development certificate
    nếu backend bị redirect từ HTTP sang HTTPS.

    Chỉ phục vụ môi trường local/dev.
    """
    if SMARTPARKING_API_URL.startswith("https://localhost"):
        return ssl._create_unverified_context()

    if SMARTPARKING_API_URL.startswith("https://127.0.0.1"):
        return ssl._create_unverified_context()

    return None


def _http_json_request(
    method,
    url,
    payload=None,
    token=None,
):
    """
    Gửi HTTP request JSON tới .NET Backend.
    Không phụ thuộc requests để tránh phải cài thêm package.
    """

    headers = {
        "Accept": "application/json",
    }

    body = None

    if payload is not None:
        body = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = Request(
        url,
        data=body,
        headers=headers,
        method=method.upper(),
    )

    try:
        context = _backend_ssl_context()

        if context is not None:
            response = urlopen(
                req,
                timeout=20,
                context=context,
            )
        else:
            response = urlopen(
                req,
                timeout=20,
            )

        raw = response.read().decode("utf-8")

        if not raw:
            return {}

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {
                "raw": raw,
            }

    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")

        try:
            body_data = json.loads(raw)
        except json.JSONDecodeError:
            body_data = {
                "message": raw,
            }

        message = (
            body_data.get("message")
            or body_data.get("title")
            or f"Backend trả HTTP {exc.code}."
        )

        raise BackendApiError(
            exc.code,
            message,
            body_data,
        )

    except URLError as exc:
        raise BackendApiError(
            0,
            (
                "Không thể kết nối SmartParking Backend. "
                f"Địa chỉ hiện tại: {SMARTPARKING_API_URL}. "
                f"Chi tiết: {exc.reason}"
            ),
        )

    except Exception as exc:
        raise BackendApiError(
            0,
            f"Lỗi gọi SmartParking Backend: {exc}",
        )


def _clear_backend_token():
    global _backend_token
    global _backend_token_expires_at

    with _backend_token_lock:
        _backend_token = None
        _backend_token_expires_at = 0.0


def _backend_login():
    """
    Đăng nhập vào .NET Backend để lấy JWT.
    """

    global _backend_token
    global _backend_token_expires_at

    payload = {
        "username": SMARTPARKING_USERNAME,
        "password": SMARTPARKING_PASSWORD,
    }

    data = _http_json_request(
        "POST",
        f"{SMARTPARKING_API_URL}/api/Auth/login",
        payload,
        None,
    )

    token = data.get("token")

    if not token:
        raise BackendApiError(
            500,
            "Backend login không trả về JWT token.",
            data,
        )

    expires_in_minutes = int(
        data.get("expiresInMinutes", 60)
    )

    with _backend_token_lock:
        _backend_token = token

        # Trừ 30 giây để tránh token vừa hết hạn giữa request.
        _backend_token_expires_at = (
            time.time()
            + max(30, expires_in_minutes * 60 - 30)
        )

    return token


def _get_backend_token():
    global _backend_token
    global _backend_token_expires_at

    with _backend_token_lock:
        if (
            _backend_token
            and time.time() < _backend_token_expires_at
        ):
            return _backend_token

    return _backend_login()


def _backend_request(
    method,
    path,
    payload=None,
):
    """
    Gọi API .NET có JWT.

    Nếu JWT hết hạn hoặc Backend trả 401:
    - xóa token
    - login lại
    - request lại 1 lần
    """

    url = f"{SMARTPARKING_API_URL}{path}"

    for attempt in range(2):
        token = _get_backend_token()

        try:
            return _http_json_request(
                method,
                url,
                payload,
                token,
            )

        except BackendApiError as exc:

            if (
                exc.status_code == 401
                and attempt == 0
            ):
                _clear_backend_token()
                continue

            raise


# ============================================================
# BACKEND TICKET HELPERS
# ============================================================

def _backend_get_all_tickets():
    return _backend_request(
        "GET",
        "/api/Tickets",
    )


def _backend_get_ticket(ticket_id):
    try:
        return _backend_request(
            "GET",
            f"/api/Tickets/{int(ticket_id)}",
        )
    except BackendApiError as exc:
        if exc.status_code == 404:
            return None

        raise


def _backend_get_open_by_plate(plate):
    plate = normalize_plate(plate)

    if not plate:
        return None

    encoded_plate = quote(
        plate,
        safe="",
    )

    try:
        return _backend_request(
            "GET",
            f"/api/Tickets/open/{encoded_plate}",
        )

    except BackendApiError as exc:
        if exc.status_code == 404:
            return None

        raise


def _backend_create_entry(
    plate,
    vehicle_type,
    entry_time,
    entry_image_path=None,
    plate_image_path=None,
):
    payload = {
        "plate": plate,
        "vehicleType": vehicle_type or "Motorbike",
        "entryTime": entry_time,
        "entryImagePath": entry_image_path,
        "plateImagePath": plate_image_path,
    }

    return _backend_request(
        "POST",
        "/api/Tickets/entry",
        payload,
    )


def _backend_close_exit(
    ticket_id,
    exit_image_path,
    penalty_amount,
    status,
):
    payload = {
        "exitImagePath": exit_image_path,
        "penaltyAmount": float(
            penalty_amount or 0
        ),
        "status": int(status),
    }

    return _backend_request(
        "POST",
        f"/api/Tickets/{int(ticket_id)}/exit",
        payload,
    )


# ============================================================
# BACKEND TICKET NORMALIZATION
# ============================================================

def _format_backend_datetime(value):
    if not value:
        return None

    try:
        return pd.to_datetime(value).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except Exception:
        return str(value)


def _status_code_from_backend(value):
    try:
        return int(value)
    except Exception:
        if str(value).lower() == "open":
            return 1

        if str(value).lower() == "closed":
            return 2

        if str(value).lower() == "alert":
            return 3

        return 1


def _status_name(status_code):
    mapping = {
        1: "open",
        2: "closed",
        3: "alert",
    }

    return mapping.get(
        int(status_code),
        "open",
    )


def _normalize_backend_ticket(ticket):
    if not isinstance(ticket, dict):
        return None

    ticket_id = ticket.get(
        "ticketId",
        ticket.get("TicketId"),
    )

    ticket_code = ticket.get(
        "ticketCode",
        ticket.get("TicketCode", ""),
    )

    plate = ticket.get(
        "plate",
        ticket.get("Plate", ""),
    )

    vehicle_type = ticket.get(
        "vehicleType",
        ticket.get("VehicleType", "Motorbike"),
    )

    entry_time_raw = ticket.get(
        "entryTime",
        ticket.get("EntryTime"),
    )

    entry_image_path = ticket.get(
        "entryImagePath",
        ticket.get("EntryImagePath"),
    )

    plate_image_path = ticket.get(
        "plateImagePath",
        ticket.get("PlateImagePath"),
    )

    exit_time_raw = ticket.get(
        "exitTime",
        ticket.get("ExitTime"),
    )

    exit_image_path = ticket.get(
        "exitImagePath",
        ticket.get("ExitImagePath"),
    )

    status_value = ticket.get(
        "status",
        ticket.get("Status", 1),
    )

    # .NET enum trả về số: 1 = Open, 2 = Closed, 3 = Alert
    try:
        status_code = int(status_value)
    except (TypeError, ValueError):
        status_text = str(status_value).strip().lower()

        if status_text in {"open", "đang gửi"}:
            status_code = 1
        elif status_text in {"closed", "đã trả xe"}:
            status_code = 2
        elif status_text == "alert":
            status_code = 3
        else:
            status_code = 1

    if status_code == 1:
        status_text = "open"
    elif status_code == 2:
        status_text = "closed"
    elif status_code == 3:
        status_text = "alert"
    else:
        status_text = "open"

    penalty_amount = ticket.get(
        "penaltyAmount",
        ticket.get("PenaltyAmount", 0),
    )

    created_at_raw = ticket.get(
        "createdAt",
        ticket.get("CreatedAt"),
    )

    return {
        "id": ticket_id,
        "ticket_id": ticket_id,

        "ticket_code": ticket_code or "",

        "plate": plate or "",

        "vehicle_type": vehicle_type or "Motorbike",

        "entry_time": _format_backend_datetime(
            entry_time_raw
        ),

        "entry_image_path": (
            entry_image_path or ""
        ),

        "plate_image_path": (
            plate_image_path or ""
        ),

        "exit_time": _format_backend_datetime(
            exit_time_raw
        ),

        "exit_image_path": (
            exit_image_path or ""
        ),

        "status": status_text,

        "status_code": status_code,

        "penalty_amount": penalty_amount or 0,

        "created_at": _format_backend_datetime(
            created_at_raw
        ),
    }


# ============================================================
# ML MODELS
# ============================================================

MODEL_DIR = os.path.join(
    ROOT_DIR,
    "models",
)

clf_model = None
reg_model = None
demand_model = None

_models_error = None


try:
    clf_model = joblib.load(
        os.path.join(
            MODEL_DIR,
            "classification",
            "best_classification_model.pkl",
        )
    )

    reg_model = joblib.load(
        os.path.join(
            MODEL_DIR,
            "regression",
            "best_regression_model.pkl",
        )
    )

    demand_model = joblib.load(
        os.path.join(
            MODEL_DIR,
            "demand",
            "best_demand_model.pkl",
        )
    )

except Exception as exc:
    _models_error = str(exc)


# ============================================================
# PREDICTION
# ============================================================

def _parse_entry_time(entry_time_str):
    if entry_time_str:
        return pd.to_datetime(
            entry_time_str
        )

    return pd.Timestamp(
        datetime.now()
    )


def _recommend_zone(
    predicted_behavior,
    raw_predicted_minutes,
):
    if predicted_behavior == "Early_Return":
        return (
            min(
                raw_predicted_minutes,
                210,
            ),
            "Khu A (Ra vào nhanh)",
        )

    if predicted_behavior == "Full_Day":
        return (
            max(
                raw_predicted_minutes,
                240,
            ),
            "Khu B/C (Đỗ lâu)",
        )

    if predicted_behavior == "Overnight":
        return (
            max(
                raw_predicted_minutes,
                720,
            ),
            "Khu D (An ninh qua đêm)",
        )

    return (
        raw_predicted_minutes,
        "Khu D (Dài ngày)",
    )


def run_prediction(payload):
    if (
        clf_model is None
        or reg_model is None
        or demand_model is None
    ):
        entry_time = _parse_entry_time(
            payload.get("entry_time")
        )

        est_min = 240

        return {
            "status": "success",
            "student_id": payload.get(
                "student_id",
                "Unknown",
            ),
            "current_demand": None,
            "behavior": "Full_Day",
            "duration_minutes": est_min,
            "estimated_exit": (
                entry_time
                + pd.Timedelta(
                    minutes=est_min
                )
            ).strftime(
                "%H:%M - %d/%m/%Y"
            ),
            "recommended_zone": "Khu B/C (Đỗ lâu)",
            "model_warning": (
                "Chưa load được mô hình ML: "
                f"{_models_error}"
            ),
        }

    student_id = payload.get(
        "student_id",
        "Unknown",
    )

    vehicle = payload.get(
        "vehicle",
        "Motorbike",
    )

    usual_zone = payload.get(
        "usual_zone",
        "Zone_A",
    )

    rolling_avg = float(
        payload.get(
            "rolling_avg",
            200,
        )
    )

    hist_overnight = int(
        payload.get(
            "hist_overnight",
            0,
        )
    )

    entry_time = _parse_entry_time(
        payload.get("entry_time")
    )

    demand_features = pd.DataFrame(
        [
            {
                "hour": entry_time.hour,
                "day_of_week": entry_time.weekday(),
                "is_weekend": (
                    1
                    if entry_time.weekday() >= 5
                    else 0
                ),
                "is_morning": (
                    1
                    if entry_time.hour < 12
                    else 0
                ),
                "is_exam_week": 0,
            }
        ]
    )[
        demand_model.feature_names_in_
    ]

    current_demand = int(
        demand_model.predict(
            demand_features
        )[0]
    )

    clf_features = pd.DataFrame(
        [
            {
                "entry_hour": entry_time.hour,
                "entry_minute": entry_time.minute,
                "day_of_week_num": entry_time.weekday(),
                "is_weekend": (
                    1
                    if entry_time.weekday() >= 5
                    else 0
                ),
                "is_morning": (
                    1
                    if entry_time.hour < 12
                    else 0
                ),
                "rolling_avg_duration": rolling_avg,
                "historical_overnight_count": hist_overnight,
                "vehicle_type_Motorbike": (
                    1
                    if vehicle == "Motorbike"
                    else 0
                ),
                "usual_zone_Zone_B": (
                    1
                    if usual_zone == "Zone_B"
                    else 0
                ),
                "usual_zone_Zone_C": (
                    1
                    if usual_zone == "Zone_C"
                    else 0
                ),
                "usual_zone_Zone_D": (
                    1
                    if usual_zone == "Zone_D"
                    else 0
                ),
                "is_exam_week": 0,
            }
        ]
    )[
        clf_model.feature_names_in_
    ]

    predicted_behavior = clf_model.predict(
        clf_features
    )[0]

    raw_predicted_minutes = (
        reg_model.predict(
            clf_features
        )[0]
    )

    est_min, zone_rec = _recommend_zone(
        predicted_behavior,
        raw_predicted_minutes,
    )

    estimated_exit = (
        entry_time
        + pd.Timedelta(
            minutes=est_min
        )
    )

    return {
        "status": "success",
        "student_id": student_id,
        "current_demand": current_demand,
        "behavior": predicted_behavior,
        "duration_minutes": int(est_min),
        "estimated_exit": estimated_exit.strftime(
            "%H:%M - %d/%m/%Y"
        ),
        "recommended_zone": zone_rec,
    }


def _prediction_for_existing_ticket(
    ticket,
):
    """
    SQL Server hiện lưu thông tin vé cơ bản.
    Prediction không nằm trong bảng Tickets hiện tại.

    Vì vậy khi xe ra, tái tạo prediction từ:
    - thời gian vào
    - loại xe
    - cùng các tham số mặc định của automatic gate

    Điều này giữ penalty hoạt động mà không cần SQLite.
    """

    entry_time = ticket.get(
        "entry_time"
    )

    vehicle = (
        ticket.get("vehicle_type")
        or "Motorbike"
    )

    return run_prediction(
        {
            "student_id": "AUTO_GATE",
            "entry_time": entry_time,
            "vehicle": vehicle,
            "usual_zone": "Zone_A",
            "rolling_avg": 260,
            "hist_overnight": 0,
        }
    )


# ============================================================
# REQUEST HELPERS
# ============================================================

def _decode_base64_image(value):
    """Giải mã ảnh base64/data URL từ camera web."""
    if not value:
        return None

    try:
        text = str(value).strip()
        if "," in text and text.lower().startswith("data:"):
            text = text.split(",", 1)[1]

        return base64.b64decode(text, validate=True)
    except Exception:
        return None


def _read_upload():
    """Đọc ảnh từ multipart hoặc JSON/base64 để gate tự động không phụ thuộc kiểu request."""
    file = request.files.get("image")

    if file and file.filename:
        data = file.read()
        if data:
            return data

    body = request.json if request.is_json else {}
    body = body if isinstance(body, dict) else {}

    for key in (
        "image_base64",
        "imageBase64",
        "frame_base64",
        "frameBase64",
        "image",
        "frame",
    ):
        data = _decode_base64_image(body.get(key))
        if data:
            return data

    return None


def _typed_plate():
    if request.is_json and request.json:
        return request.json.get(
            "plate"
        ) or ""

    return request.form.get(
        "plate"
    ) or ""


def _save_ticket_images(
    image_bytes: bytes,
    ocr: dict,
    prefix: str,
):
    """
    Lưu ảnh toàn cảnh và ảnh crop biển số.
    SQL Server chỉ lưu path.
    """

    TICKET_IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    image_name = (
        f"{stamp}_{prefix}.jpg"
    )

    image_path = (
        TICKET_IMAGE_DIR
        / image_name
    )

    image_path.write_bytes(
        image_bytes
    )

    plate_name = ""

    crop_b64 = (
        ocr.get("crop_jpeg_b64")
        if isinstance(ocr, dict)
        else None
    )

    if crop_b64:
        plate_name = (
            f"{stamp}_{prefix}_plate.jpg"
        )

        (
            TICKET_IMAGE_DIR
            / plate_name
        ).write_bytes(
            base64.b64decode(
                crop_b64
            )
        )

    return (
        image_name,
        plate_name,
    )


def _plate_from_request(
    image_bytes,
):
    typed = normalize_plate(
        _typed_plate()    )

    ocr = None

    if image_bytes:
        ocr = recognize_plate(
            image_bytes
        )

        plate = (
            ocr.get("plate")
            or typed
        )

    else:
        plate = typed

    return (
        plate,
        ocr,
    )


def _backend_error_response(
    exc,
):
    status_code = exc.status_code

    if (
        status_code < 400
        or status_code > 599
    ):
        status_code = 503

    return jsonify(
        {
            "status": "error",
            "message": exc.message,
            "backend": SMARTPARKING_API_URL,
        }
    ), status_code


# ============================================================
# LOCAL SCAN HISTORY
# ============================================================

_scan_history = []


def _save_scan_record(record):
    _scan_history.insert(
        0,
        record,
    )

    if len(_scan_history) > 100:
        del _scan_history[100:]


# ============================================================
# PAGE ROUTES
# ============================================================
# Flask chỉ còn là dịch vụ API/OCR. Giao diện chính được chạy bằng React.
# Các đường dẫn trang cũ chuyển về React để không dùng lại template HTML.

@app.route("/")
@app.route("/dashboard")
@app.route("/parking")
@app.route("/history")
def legacy_page_redirect():
    return redirect("http://localhost:5173/", code=302)

# ============================================================
# PREDICTION API
# ============================================================

@app.route(
    "/api/predict",
    methods=["POST"],
)
def predict():
    try:
        data = request.json or {}

        return jsonify(
            run_prediction(data)
        )

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


# ============================================================
# OCR SCAN
# ============================================================

@app.route(
    "/api/scan-plate",
    methods=["POST"],
)
def scan_plate():
    try:
        uploaded = request.files.get(
            "image"
        )

        if (
            not uploaded
            or not uploaded.filename
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": (
                        "Hãy chọn 1 file ảnh "
                        "có biển số xe."
                    ),
                }
            ), 400

        image_bytes = uploaded.read()

        filename = uploaded.filename

        ocr = recognize_plate(
            image_bytes
        )

        vehicle = infer_vehicle_type(
            source=image_bytes,
            plate=ocr.get("plate"),
        )

        SCAN_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        stamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        safe = "".join(
            ch
            if ch.isalnum()
            or ch in ".-_"
            else "_"
            for ch in filename
        )[:80]

        image_path = (
            SCAN_DIR
            / f"{stamp}_{safe}"
        )

        image_path.write_bytes(
            image_bytes
        )

        crop_path = ""

        if ocr.get(
            "crop_jpeg_b64"
        ):
            crop_file = (
                SCAN_DIR
                / f"{stamp}_crop.jpg"
            )

            crop_file.write_bytes(
                base64.b64decode(
                    ocr[
                        "crop_jpeg_b64"
                    ]
                )
            )

            crop_path = str(
                crop_file
            )

        record = {
            "id": stamp,
            "plate": (
                ocr.get("plate")
                or ""
            ),
            "valid": ocr.get(
                "valid"
            ),
            "confidence": ocr.get(
                "confidence"
            ),
            "engine": ocr.get(
                "engine"
            ),
            "source_filename": filename,
            "image_path": str(
                image_path
            ),
            "crop_path": crop_path,
            "vehicle_type": vehicle.get(
                "vehicle_type"
            ),
            "extra": {
                "bbox": ocr.get(
                    "bbox"
                ),
                "raw_candidates": ocr.get(
                    "raw_candidates"
                ),
                "message": ocr.get(
                    "message"
                ),
            },
        }

        _save_scan_record(
            record
        )

        # Lưu tự động vào .NET Backend SQL Server
        try:
            detected_plate = ocr.get("plate")
            if detected_plate:
                _backend_request(
                    "POST",
                    "/api/PlateScans",
                    payload={
                        "plate": detected_plate,
                        "vehicleType": vehicle.get("vehicle_type") or "Motorbike",
                        "confidence": float(ocr.get("confidence") or 1.0),
                        "imagePath": f"/scan-image/{image_path.name}",
                        "cropImagePath": f"/scan-image/{Path(crop_path).name}" if crop_path else None,
                        "note": ocr.get("engine") or "YOLOv8 + RapidOCR",
                    },
                )
        except Exception as be_exc:
            print(f"[Warning] Khong the day scan sang .NET Backend: {be_exc}")

        return jsonify(
            {
                "status": "success",
                "plate": ocr.get(
                    "plate"
                ),
                "valid": ocr.get(
                    "valid"
                ),
                "confidence": ocr.get(
                    "confidence"
                ),
                "engine": ocr.get(
                    "engine"
                ),
                "message": ocr.get(
                    "message"
                ),
                "vehicle_type": vehicle.get(
                    "vehicle_type"
                ),
                "vehicle_source": vehicle.get(
                    "source"
                ),
                "raw_candidates": ocr.get(
                    "raw_candidates",
                    [],
                ),
                "bbox": ocr.get(
                    "bbox"
                ),
                "crop_jpeg_b64": ocr.get(
                    "crop_jpeg_b64"
                ),
                "annotated_jpeg_b64": ocr.get(
                    "annotated_jpeg_b64"
                ),
                "saved": record,
                "image_path": str(
                    image_path
                ),
                "crop_path": crop_path,
            }
        )

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


# ============================================================
# TICKET IMAGE
# ============================================================

@app.route(
    "/ticket-image/<path:filename>"
)
def ticket_image(filename):
    """Phục vụ ảnh vé từ path lưu trong SQL Server."""
    try:
        relative = str(filename).replace("\\", "/").lstrip("/")
        prefix = "ticket_images/"
        if relative.lower().startswith(prefix):
            relative = relative[len(prefix):]

        safe_name = Path(relative).name
        if not safe_name:
            return jsonify(
                {
                    "status": "error",
                    "message": "Tên ảnh không hợp lệ.",
                }
            ), 400

        image_path = TICKET_IMAGE_DIR / safe_name

        if not image_path.is_file():
            return jsonify(
                {
                    "status": "error",
                    "message": "Không tìm thấy ảnh vé.",
                    "filename": safe_name,
                }
            ), 404

        return send_from_directory(
            TICKET_IMAGE_DIR,
            safe_name,
        )
    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


@app.route("/scan-image/<path:filename>")
def get_scan_image(filename):
    safe_name = os.path.basename(filename)
    return send_from_directory(SCAN_DIR, safe_name)


# ============================================================
# OCR PREVIEW
# ============================================================

@app.route(
    "/api/preview-plate",
    methods=["POST"],
)
def preview_plate():
    """
    OCR preview cho camera tự động.

    Không tạo vé.
    Không ghi SQL Server.
    """

    try:
        uploaded = request.files.get(
            "image"
        )

        if (
            not uploaded
            or not uploaded.filename
        ):
            return jsonify(
                {
                    "status": "error",
                    "message": (
                        "Không có ảnh camera."
                    ),
                }
            ), 400

        image_bytes = uploaded.read()

        ocr = recognize_plate(
            image_bytes
        )

        plate = normalize_plate(
            ocr.get("plate")
            or ""
        )

        vehicle = infer_vehicle_type(
            source=image_bytes,
            plate=plate,
        )

        return jsonify(
            {
                "status": "success",
                "plate": plate,
                "valid": bool(
                    ocr.get("valid")
                ),
                "confidence": ocr.get(
                    "confidence",
                    0,
                ),
                "engine": ocr.get(
                    "engine",
                    "none",
                ),
                "message": ocr.get(
                    "message",
                    "",
                ),
                "vehicle_type": vehicle.get(
                    "vehicle_type"
                ),
                "bbox": ocr.get(
                    "bbox"
                ),
                "annotated_jpeg_b64": ocr.get(
                    "annotated_jpeg_b64"
                ),
                "crop_jpeg_b64": ocr.get(
                    "crop_jpeg_b64"
                ),
            }
        )

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


# ============================================================
# AUTOMATIC GATE EVENT
# ============================================================

@app.route(
    "/api/gate-event",
    methods=["POST"],
)
def gate_event():
    """
    Tự động nhận diện biển số.

    ENTRY:
        Camera/OCR
        -> .NET POST /api/Tickets/entry
        -> SQL Server

    EXIT:
        Camera/OCR
        -> .NET GET /api/Tickets/open/{plate}
        -> tính penalty bằng ML/Python
        -> .NET POST /api/Tickets/{id}/exit
        -> SQL Server
    """

    try:
        body = (
            request.json
            if request.is_json
            else {}
        ) or {}

        mode = (
            request.form.get("mode")
            or body.get("mode")
            or "entry"
        ).strip().lower()

        if mode not in {
            "entry",
            "exit",
        }:
            return jsonify(
                {
                    "status": "error",
                    "message": (
                        "mode phải là "
                        "entry hoặc exit."
                    ),
                }
            ), 400

        image_bytes = _read_upload()

        if not image_bytes:
            return jsonify(
                {
                    "status": "error",
                    "message": (
                        "Không có ảnh từ camera. "
                        "Gửi multipart field 'image' "
                        "hoặc JSON/base64 image."
                    ),
                }
            ), 400

        ocr = recognize_plate(
            image_bytes
        )

        # ----------------------------------------------------
        # CAMERA PREVIEW FALLBACK
        # ----------------------------------------------------

        plate_hint = normalize_plate(
            request.form.get(
                "plate_hint"
            )
            or body.get(
                "plate_hint",
                "",
            )
        )

        preview_crop_b64 = (
            request.form.get(
                "preview_crop_jpeg_b64"
            )
            or body.get(
                "preview_crop_jpeg_b64",
                "",
            )
        )

        preview_conf = float(
            request.form.get(
                "preview_confidence"
            )
            or body.get(
                "preview_confidence",
                0,
            )
            or 0
        )

        preview_valid = (
            is_valid_vn_plate(
                plate_hint
            )
        )

        if (
            preview_valid
            and (
                not ocr.get("valid")
                or normalize_plate(
                    ocr.get("plate")
                    or ""
                )
                == plate_hint
            )
        ):
            ocr["plate"] = plate_hint
            ocr["valid"] = True

            ocr["confidence"] = max(
                float(
                    ocr.get(
                        "confidence"
                    )
                    or 0
                ),
                preview_conf,
            )

            ocr["message"] = (
                ocr.get("message")
                or (
                    "Biển số đã ổn định "
                    "qua camera."
                )
            )

            if preview_crop_b64:
                ocr[
                    "crop_jpeg_b64"
                ] = preview_crop_b64

        # ----------------------------------------------------
        # NORMALIZE PLATE
        # ----------------------------------------------------

        plate = normalize_plate(
            ocr.get("plate")
            or plate_hint
        )

        if (
            not plate
            or not ocr.get("valid")
        ):
            return jsonify(
                {
                    "status": "error",
                    "event": "ignored",
                    "message": (
                        ocr.get("message")
                        or (
                            "Chưa nhận diện "
                            "được biển số hợp lệ."
                        )
                    ),
                    "plate": plate,
                    "confidence": ocr.get(
                        "confidence",
                        0,
                    ),
                    "engine": ocr.get(
                        "engine",
                        "none",
                    ),
                    "ocr": ocr,
                }
            ), 422

        # ----------------------------------------------------
        # VEHICLE
        # ----------------------------------------------------

        vehicle_info = infer_vehicle_type(
            source=image_bytes,
            plate=plate,
        )

        vehicle = (
            canonicalize_vehicle_type(
                vehicle_info.get(
                    "vehicle_type"
                )
            )
            or "Motorbike"
        )

        # ====================================================
        # ENTRY
        # ====================================================

        if mode == "entry":

            # Kiểm tra xe đã có vé mở trong SQL Server chưa.
            existing = (
                _backend_get_open_by_plate(
                    plate
                )
            )

            if existing:
                ticket = (
                    _normalize_backend_ticket(
                        existing
                    )
                )

                return jsonify(
                    {
                        "status": "success",
                        "event": "duplicate",
                        "message": (
                            f"Xe {plate} "
                            "đang có vé mở."
                        ),
                        "plate": plate,
                        "ticket": ticket,
                        "ocr": ocr,
                        "vehicle": vehicle_info,
                    }
                )

            # ------------------------------------------------
            # ML PREDICTION
            # ------------------------------------------------

            entry_time = datetime.now().isoformat(timespec="seconds")

            prediction = run_prediction(
                {
                    "student_id": "AUTO_GATE",
                    "entry_time": entry_time,
                    "vehicle": vehicle,
                    "usual_zone": "Zone_A",
                    "rolling_avg": 260,
                    "hist_overnight": 0,
                }
            )

            # ------------------------------------------------
            # SAVE IMAGE
            # ------------------------------------------------

            (
                image_name,
                plate_image_name,
            ) = _save_ticket_images(
                image_bytes,
                ocr,
                "entry",
            )

            # ------------------------------------------------
            # SEND TO .NET BACKEND
            # ------------------------------------------------

            try:
                backend_ticket = (
                    _backend_create_entry(
                        plate=plate,
                        vehicle_type=vehicle,
                        entry_time=entry_time,
                        entry_image_path=image_name,
                        plate_image_path=plate_image_name,
                    )
                )

            except BackendApiError as exc:

                # Race condition:
                # nếu request khác vừa tạo vé,
                # lấy vé mở hiện tại.
                if exc.status_code == 409:

                    existing = (
                        _backend_get_open_by_plate(
                            plate
                        )
                    )

                    if existing:
                        ticket = (
                            _normalize_backend_ticket(
                                existing
                            )
                        )

                        return jsonify(
                            {
                                "status": "success",
                                "event": "duplicate",
                                "message": (
                                    f"Xe {plate} "
                                    "đang có vé mở."
                                ),
                                "plate": plate,
                                "ticket": ticket,
                                "ocr": ocr,
                                "vehicle": vehicle_info,
                            }
                        )

                raise

            ticket = (
                _normalize_backend_ticket(
                    backend_ticket
                )
            )

            return jsonify(
                {
                    "status": "success",
                    "event": "created",
                    "message": (
                        f"Đã tự động tạo vé "
                        f"cho xe {plate}."
                    ),
                    "plate": plate,
                    "ticket": ticket,
                    "prediction": prediction,
                    "ocr": ocr,
                    "vehicle": vehicle_info,
                }
            )

        # ====================================================
        # EXIT
        # ====================================================

        open_backend_ticket = (
            _backend_get_open_by_plate(
                plate
            )
        )

        if open_backend_ticket is None:
            return jsonify(
                {
                    "status": "success",
                    "event": "not_found",
                    "message": (
                        "Không tìm thấy vé "
                        f"đang gửi cho biển {plate}."
                    ),
                    "plate": plate,
                    "ocr": ocr,
                    "vehicle": vehicle_info,
                }
            )

        open_ticket = (
            _normalize_backend_ticket(
                open_backend_ticket
            )
        )

        exit_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        exit_vehicle = vehicle

        # ----------------------------------------------------
        # RECREATE ML PREDICTION
        # ----------------------------------------------------

        prediction = (
            _prediction_for_existing_ticket(
                open_ticket
            )
        )

        predicted_minutes = int(
            prediction.get(
                "duration_minutes",
                240,
            )
            or 240
        )

        # ----------------------------------------------------
        # PENALTY
        # ----------------------------------------------------

        penalty = compute_penalty(
            predicted_minutes=predicted_minutes,
            entry_time=open_ticket.get(
                "entry_time"
            ),
            exit_time=exit_time,
        )

        # ----------------------------------------------------
        # VALIDATE PLATE / VEHICLE
        # ----------------------------------------------------

        plate_ok = plates_match(
            open_ticket.get("plate"),
            plate,
        )

        vehicle_ok = (
            vehicle_types_match(
                open_ticket.get(
                    "vehicle_type"
                ),
                exit_vehicle,
            )
        )

        alerts = []

        if not plate_ok:
            alerts.append(
                "Biển số lúc ra "
                "không khớp lúc vào."
            )

        if not vehicle_ok:
            alerts.append(
                "Loại xe lúc ra "
                "không khớp lúc vào."
            )

        if penalty["is_overtime"]:
            alerts.append(
                "Gửi quá giờ "
                f"{penalty['overtime_minutes']} phút."
            )

        # ----------------------------------------------------
        # SAVE EXIT IMAGE
        # ----------------------------------------------------

        (
            exit_image_name,
            exit_plate_image_name,
        ) = _save_ticket_images(
            image_bytes,
            ocr,
            "exit",
        )

        status_name = (
            "closed"
            if plate_ok and vehicle_ok
            else "alert"
        )

        status_code = (
            2
            if status_name == "closed"
            else 3
        )

        # ----------------------------------------------------
        # CLOSE TICKET IN .NET / SQL SERVER
        # ----------------------------------------------------

        closed_backend_ticket = (
            _backend_close_exit(
                ticket_id=open_ticket[
                    "ticket_id"
                ],
                exit_image_path=exit_image_name,
                penalty_amount=penalty[
                    "penalty_vnd"
                ],
                status=status_code,
            )
        )

        closed = (
            _normalize_backend_ticket(
                closed_backend_ticket
            )
        )

        # Các thông tin này chưa có column trong
        # bảng Tickets hiện tại nên giữ trong response.
        closed[
            "exit_plate"
        ] = plate

        closed[
            "exit_vehicle_type"
        ] = exit_vehicle

        closed[
            "exit_plate_image_path"
        ] = exit_plate_image_name

        closed[
            "plate_match"
        ] = plate_ok

        closed[
            "vehicle_match"
        ] = vehicle_ok

        closed[
            "overtime_minutes"
        ] = penalty[
            "overtime_minutes"
        ]

        closed[
            "alert_message"
        ] = " ".join(alerts)

        return jsonify(
            {
                "status": "success",
                "event": (
                    "closed"
                    if status_name == "closed"
                    else "alert"
                ),
                "message": (
                    (
                        "Đã tự động cập nhật vé "
                        f"{closed.get('ticket_code')} "
                        "thành đã trả xe."
                    )
                    if status_name == "closed"
                    else (
                        "Vé được đóng "
                        "nhưng có cảnh báo."
                    )
                ),
                "plate": plate,
                "ticket": closed,
                "prediction": prediction,
                "penalty": penalty,
                "plate_match": plate_ok,
                "vehicle_match": vehicle_ok,
                "alerts": alerts,
                "ocr": ocr,
                "vehicle": vehicle_info,
            }
        )

    except BackendApiError as exc:
        return _backend_error_response(
            exc
        )

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


# ============================================================
# SCANS
# ============================================================

@app.route("/api/scans")
def list_scans():
    return jsonify(
        {
            "status": "success",
            "scans": _scan_history,
        }
    )

# ============================================================
# MANUAL CHECK-IN
# ============================================================

@app.route(
    "/api/checkin",
    methods=["POST"],
)
def checkin():
    try:
        image_bytes = _read_upload()

        body = (
            request.form.to_dict()
            if request.form
            else (
                request.json or {}
            )
        )

        plate, ocr = _plate_from_request(
            image_bytes
        )

        if not plate:
            return jsonify(
                {
                    "status": "error",
                    "message": (
                        "Không đọc được "
                        "biển số. Chụp lại "
                        "hoặc nhập tay."
                    ),
                    "ocr": ocr,
                }
            ), 400

        # ----------------------------------------------------
        # CHECK DUPLICATE
        # ----------------------------------------------------

        existing = (
            _backend_get_open_by_plate(
                plate
            )
        )

        if existing:
            return jsonify(
                {
                    "status": "error",
                    "message": (
                        f"Xe {plate} "
                        "đang có vé gửi."
                    ),
                    "ticket": (
                        _normalize_backend_ticket(
                            existing
                        )
                    ),
                    "ocr": ocr,
                }
            ), 409

        # ----------------------------------------------------
        # VEHICLE
        # ----------------------------------------------------

        declared = (
            body.get("vehicle")
            or body.get("vehicle_type")
        )

        vehicle_info = infer_vehicle_type(
            source=image_bytes,
            plate=plate,
            declared=declared,
        )

        vehicle = (
            canonicalize_vehicle_type(
                vehicle_info[
                    "vehicle_type"
                ]
            )
            or "Motorbike"
        )

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        entry_time = (
            body.get("entry_time")
            or datetime.now().isoformat(timespec="seconds")
        )

        payload = {
            "student_id": body.get(
                "student_id",
                "Unknown",
            ),
            "entry_time": entry_time,
            "vehicle": vehicle,
            "usual_zone": body.get(
                "usual_zone",
                "Zone_A",
            ),
            "rolling_avg": body.get(
                "rolling_avg",
                200,
            ),
            "hist_overnight": body.get(
                "hist_overnight",
                0,
            ),
        }

        prediction = run_prediction(
            payload
        )

        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        image_name = None
        plate_image_name = None

        if image_bytes:
            (
                image_name,
                plate_image_name,
            ) = _save_ticket_images(
                image_bytes,
                ocr or {},
                "entry",
            )

        # ----------------------------------------------------
        # CREATE SQL SERVER TICKET
        # ----------------------------------------------------

        backend_ticket = (
            _backend_create_entry(
                plate=plate,
                vehicle_type=vehicle,
                entry_time=entry_time,
                entry_image_path=image_name,
                plate_image_path=plate_image_name,
            )
        )

        ticket = (
            _normalize_backend_ticket(
                backend_ticket
            )
        )

        return jsonify(
            {
                "status": "success",
                "ticket": ticket,
                "prediction": prediction,
                "ocr": ocr,
                "vehicle": vehicle_info,
            }
        )

    except BackendApiError as exc:
        return _backend_error_response(
            exc
        )

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


# ============================================================
# MANUAL CHECK-OUT
# ============================================================

@app.route(
    "/api/checkout",
    methods=["POST"],
)
def checkout():
    try:
        image_bytes = _read_upload()

        body = (
            request.form.to_dict()
            if request.form
            else (
                request.json or {}
            )
        )

        exit_plate, ocr = _plate_from_request(
            image_bytes
        )

        ticket_id = body.get(
            "ticket_id"
        )

        open_ticket = None

        # ----------------------------------------------------
        # FIND BY TICKET ID
        # ----------------------------------------------------

        if ticket_id:
            backend_ticket = (
                _backend_get_ticket(
                    int(ticket_id)
                )
            )

            if backend_ticket:
                normalized = (
                    _normalize_backend_ticket(
                        backend_ticket
                    )
                )

                if normalized.get(
                    "status_code"
                ) == 1:
                    open_ticket = normalized

        # ----------------------------------------------------
        # FIND BY PLATE
        # ----------------------------------------------------

        if open_ticket is None:

            lookup = normalize_plate(
                body.get(
                    "lookup_plate"
                )
                or body.get(
                    "entry_plate"
                )
                or ""
            )

            if lookup:
                backend_ticket = (
                    _backend_get_open_by_plate(
                        lookup
                    )
                )

                if backend_ticket:
                    open_ticket = (
                        _normalize_backend_ticket(
                            backend_ticket
                        )
                    )

        # ----------------------------------------------------
        # FIND BY EXIT OCR
        # ----------------------------------------------------

        if (
            open_ticket is None
            and exit_plate
        ):
            backend_ticket = (
                _backend_get_open_by_plate(
                    exit_plate
                )
            )

            if backend_ticket:
                open_ticket = (
                    _normalize_backend_ticket(
                        backend_ticket
                    )
                )

        if open_ticket is None:
            return jsonify(
                {
                    "status": "error",
                    "message": (
                        "Không tìm thấy vé "
                        "đang mở. Kiểm tra "
                        "biển số lúc vào."
                    ),
                    "ocr": ocr,
                }
            ), 404

        # ----------------------------------------------------
        # VEHICLE
        # ----------------------------------------------------

        declared = (
            body.get("vehicle")
            or body.get(
                "vehicle_type"
            )
        )

        vehicle_info = infer_vehicle_type(
            source=image_bytes,
            plate=exit_plate,
            declared=declared,
        )

        exit_vehicle = (
            vehicle_info.get(
                "vehicle_type"
            )
            or open_ticket.get(
                "vehicle_type"
            )
        )

        # ----------------------------------------------------
        # EXIT TIME
        # ----------------------------------------------------

        exit_time = (
            body.get("exit_time")
            or datetime.now().isoformat(timespec="seconds")
        )

        # Nếu không OCR được biển lúc ra,
        # dùng biển lúc vào để không đánh dấu mismatch
        # trong trường hợp checkout thủ công.
        comparison_plate = (
            exit_plate
            or open_ticket.get(
                "plate"
            )
            or ""
        )

        # ----------------------------------------------------
        # PREDICTION
        # ----------------------------------------------------

        prediction = (
            _prediction_for_existing_ticket(
                open_ticket
            )
        )

        predicted_minutes = int(
            prediction.get(
                "duration_minutes",
                240,
            )
            or 240
        )

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        plate_ok = plates_match(
            open_ticket.get("plate"),
            comparison_plate,
        )

        vehicle_ok = (
            vehicle_types_match(
                open_ticket.get(
                    "vehicle_type"
                ),
                exit_vehicle,
            )
        )

        # ----------------------------------------------------
        # PENALTY
        # ----------------------------------------------------

        penalty = compute_penalty(
            predicted_minutes=predicted_minutes,
            entry_time=open_ticket.get(
                "entry_time"
            ),
            exit_time=exit_time,
        )

        alerts = []

        if not plate_ok:
            alerts.append(
                "Biển số lúc ra "
                "không khớp lúc vào."
            )

        if not vehicle_ok:
            alerts.append(
                "Loại xe lúc ra "
                "không khớp lúc vào."
            )

        if penalty["is_overtime"]:
            alerts.append(
                "Gửi quá giờ "
                f"{penalty['overtime_minutes']} phút."
            )

        status_name = (
            "closed"
            if plate_ok and vehicle_ok
            else "alert"
        )

        status_code = (
            2
            if status_name == "closed"
            else 3
        )

        # ----------------------------------------------------
        # SAVE EXIT IMAGE
        # ----------------------------------------------------

        exit_image_name = None
        exit_plate_image_name = ""

        if image_bytes:
            (
                exit_image_name,
                exit_plate_image_name,
            ) = _save_ticket_images(
                image_bytes,
                ocr or {},
                "exit",
            )

        # ----------------------------------------------------
        # CLOSE SQL SERVER TICKET
        # ----------------------------------------------------

        backend_closed = (
            _backend_close_exit(
                ticket_id=open_ticket[
                    "ticket_id"
                ],
                exit_image_path=exit_image_name,
                penalty_amount=penalty[
                    "penalty_vnd"
                ],
                status=status_code,
            )
        )

        closed = (
            _normalize_backend_ticket(
                backend_closed
            )
        )

        closed[
            "exit_plate"
        ] = comparison_plate

        closed[
            "exit_vehicle_type"
        ] = exit_vehicle

        closed[
            "exit_plate_image_path"
        ] = exit_plate_image_name

        closed[
            "plate_match"
        ] = plate_ok

        closed[
            "vehicle_match"
        ] = vehicle_ok

        closed[
            "overtime_minutes"
        ] = penalty[
            "overtime_minutes"
        ]

        closed[
            "alert_message"
        ] = " ".join(alerts)

        return jsonify(
            {
                "status": "success",
                "allowed": (
                    plate_ok
                    and vehicle_ok
                ),
                "ticket": closed,
                "prediction": prediction,
                "penalty": penalty,
                "plate_match": plate_ok,
                "vehicle_match": vehicle_ok,
                "alerts": alerts,
                "ocr": ocr,
                "vehicle": vehicle_info,
            }
        )

    except BackendApiError as exc:
        return _backend_error_response(
            exc
        )

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


# ============================================================
# TICKET LIST
# ============================================================

@app.route("/api/tickets")
def list_tickets():
    try:
        requested_status = (
            request.args.get(
                "status"
            )
        )

        backend_data = (
            _backend_get_all_tickets()
        )

        raw_tickets = (
            backend_data
            if isinstance(
                backend_data,
                list,
            )
            else []
        )

        tickets = [
            _normalize_backend_ticket(
                item
            )
            for item in raw_tickets
        ]

        if requested_status:
            requested = (
                requested_status
                .strip()
                .lower()
            )

            status_map = {
                "1": "open",
                "2": "closed",
                "3": "alert",
            }

            requested = status_map.get(
                requested,
                requested,
            )

            tickets = [
                ticket
                for ticket in tickets
                if ticket.get(
                    "status"
                )
                == requested
            ]

        return jsonify(
            {
                "status": "success",
                "tickets": tickets,
            }
        )

    except BackendApiError as exc:
        return _backend_error_response(
            exc
        )

    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": str(exc),
            }
        ), 500


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    print(
        "=================================================="
    )
    print(
        " SmartParking Python"
    )
    print(
        " Camera + OCR + ML + .NET Backend"
    )
    print(
        "=================================================="
    )
    print(
        f"Backend: {SMARTPARKING_API_URL}"
    )
    print(
        "Python: http://127.0.0.1:5000"
    )
    print(
        "=================================================="
    )

    app.run(
        debug=True,
        port=5000,
    )
