from flask import Flask, render_template, request, jsonify
from datetime import datetime
import base64
import os
import sys

import pandas as pd
import joblib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from src.parking.penalty import compute_penalty
from src.parking.tickets import SCAN_DIR, TicketStore
from src.vision.plate_ocr import is_valid_vn_plate, normalize_plate, plates_match, recognize_plate
from src.vision.vehicle_type import canonicalize_vehicle_type, infer_vehicle_type, vehicle_types_match

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

MODEL_DIR = os.path.join(ROOT_DIR, "models")
clf_model = None
reg_model = None
demand_model = None
_models_error = None

try:
    clf_model = joblib.load(os.path.join(MODEL_DIR, "classification/best_classification_model.pkl"))
    reg_model = joblib.load(os.path.join(MODEL_DIR, "regression/best_regression_model.pkl"))
    demand_model = joblib.load(os.path.join(MODEL_DIR, "demand/best_demand_model.pkl"))
except Exception as exc:
    _models_error = str(exc)

ticket_store = TicketStore()


def _parse_entry_time(entry_time_str):
    if entry_time_str:
        return pd.to_datetime(entry_time_str)
    return pd.Timestamp(datetime.now())


def _recommend_zone(predicted_behavior, raw_predicted_minutes):
    if predicted_behavior == "Early_Return":
        return min(raw_predicted_minutes, 210), "Khu A (Ra vào nhanh)"
    if predicted_behavior == "Full_Day":
        return max(raw_predicted_minutes, 240), "Khu B/C (Đỗ lâu)"
    if predicted_behavior == "Overnight":
        return max(raw_predicted_minutes, 720), "Khu D (An ninh qua đêm)"
    return raw_predicted_minutes, "Khu D (Dài ngày)"


def run_prediction(payload):
    if clf_model is None or reg_model is None or demand_model is None:
        entry_time = _parse_entry_time(payload.get("entry_time"))
        est_min = 240
        return {
            "status": "success",
            "student_id": payload.get("student_id", "Unknown"),
            "current_demand": None,
            "behavior": "Full_Day",
            "duration_minutes": est_min,
            "estimated_exit": (entry_time + pd.Timedelta(minutes=est_min)).strftime("%H:%M - %d/%m/%Y"),
            "recommended_zone": "Khu B/C (Đỗ lâu)",
            "model_warning": f"Chưa load được mô hình ML: {_models_error}",
        }

    student_id = payload.get("student_id", "Unknown")
    vehicle = payload.get("vehicle", "Motorbike")
    usual_zone = payload.get("usual_zone", "Zone_A")
    rolling_avg = float(payload.get("rolling_avg", 200))
    hist_overnight = int(payload.get("hist_overnight", 0))
    entry_time = _parse_entry_time(payload.get("entry_time"))

    demand_features = pd.DataFrame([{
        "hour": entry_time.hour,
        "day_of_week": entry_time.weekday(),
        "is_weekend": 1 if entry_time.weekday() >= 5 else 0,
        "is_morning": 1 if entry_time.hour < 12 else 0,
        "is_exam_week": 0,
    }])[demand_model.feature_names_in_]
    current_demand = int(demand_model.predict(demand_features)[0])

    clf_features = pd.DataFrame([{
        "entry_hour": entry_time.hour,
        "entry_minute": entry_time.minute,
        "day_of_week_num": entry_time.weekday(),
        "is_weekend": 1 if entry_time.weekday() >= 5 else 0,
        "is_morning": 1 if entry_time.hour < 12 else 0,
        "rolling_avg_duration": rolling_avg,
        "historical_overnight_count": hist_overnight,
        "vehicle_type_Motorbike": 1 if vehicle == "Motorbike" else 0,
        "usual_zone_Zone_B": 1 if usual_zone == "Zone_B" else 0,
        "usual_zone_Zone_C": 1 if usual_zone == "Zone_C" else 0,
        "usual_zone_Zone_D": 1 if usual_zone == "Zone_D" else 0,
        "is_exam_week": 0,
    }])[clf_model.feature_names_in_]

    predicted_behavior = clf_model.predict(clf_features)[0]
    raw_predicted_minutes = reg_model.predict(clf_features)[0]
    est_min, zone_rec = _recommend_zone(predicted_behavior, raw_predicted_minutes)
    estimated_exit = entry_time + pd.Timedelta(minutes=est_min)

    return {
        "status": "success",
        "student_id": student_id,
        "current_demand": current_demand,
        "behavior": predicted_behavior,
        "duration_minutes": int(est_min),
        "estimated_exit": estimated_exit.strftime("%H:%M - %d/%m/%Y"),
        "recommended_zone": zone_rec,
    }


def _read_upload():
    file = request.files.get("image")
    if file and file.filename:
        return file.read()
    return None


def _typed_plate():
    if request.is_json and request.json:
        return request.json.get("plate") or ""
    return request.form.get("plate") or ""


def _plate_from_request(image_bytes):
    typed = normalize_plate(_typed_plate())
    ocr = None
    if image_bytes:
        ocr = recognize_plate(image_bytes)
        plate = ocr.get("plate") or typed
    else:
        plate = typed
    return plate, ocr


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/parking")
def parking():
    return render_template("parking.html")


@app.route("/history")
def history():
    return render_template("history.html")


@app.route("/api/predict", methods=["POST"])
def predict():
    try:
        data = request.json or {}
        return jsonify(run_prediction(data))
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})


@app.route("/api/scan-plate", methods=["POST"])
def scan_plate():
    try:
        uploaded = request.files.get("image")
        if not uploaded or not uploaded.filename:
            return jsonify({"status": "error", "message": "Hãy chọn 1 file ảnh có biển số xe."}), 400
        image_bytes = uploaded.read()
        filename = uploaded.filename
        ocr = recognize_plate(image_bytes)
        vehicle = infer_vehicle_type(source=image_bytes, plate=ocr.get("plate"))

        SCAN_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        safe = "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in filename)[:80]
        image_path = SCAN_DIR / f"{stamp}_{safe}"
        image_path.write_bytes(image_bytes)
        crop_path = ""
        if ocr.get("crop_jpeg_b64"):
            crop_file = SCAN_DIR / f"{stamp}_crop.jpg"
            crop_file.write_bytes(base64.b64decode(ocr["crop_jpeg_b64"]))
            crop_path = str(crop_file)

        record = ticket_store.save_plate_scan({
            "plate": ocr.get("plate") or "",
            "valid": ocr.get("valid"),
            "confidence": ocr.get("confidence"),
            "engine": ocr.get("engine"),
            "source_filename": filename,
            "image_path": str(image_path),
            "crop_path": crop_path,
            "vehicle_type": vehicle.get("vehicle_type"),
            "extra": {
                "bbox": ocr.get("bbox"),
                "raw_candidates": ocr.get("raw_candidates"),
                "message": ocr.get("message"),
            },
        })
        return jsonify({
            "status": "success",
            "plate": ocr.get("plate"),
            "valid": ocr.get("valid"),
            "confidence": ocr.get("confidence"),
            "engine": ocr.get("engine"),
            "message": ocr.get("message"),
            "vehicle_type": vehicle.get("vehicle_type"),
            "vehicle_source": vehicle.get("source"),
            "raw_candidates": ocr.get("raw_candidates", []),
            "bbox": ocr.get("bbox"),
            "crop_jpeg_b64": ocr.get("crop_jpeg_b64"),
            "annotated_jpeg_b64": ocr.get("annotated_jpeg_b64"),
            "saved": record,
            "image_path": str(image_path),
            "crop_path": crop_path,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/scans")
def list_scans():
    return jsonify({"status": "success", "scans": ticket_store.list_scans()})


@app.route("/api/checkin", methods=["POST"])
def checkin():
    try:
        image_bytes = _read_upload()
        body = request.form.to_dict() if request.form else (request.json or {})
        plate, ocr = _plate_from_request(image_bytes)
        if not plate:
            return jsonify({
                "status": "error",
                "message": "Không đọc được biển số. Chụp lại hoặc nhập tay.",
                "ocr": ocr,
            }), 400

        declared = body.get("vehicle") or body.get("vehicle_type")
        vehicle_info = infer_vehicle_type(source=image_bytes, plate=plate, declared=declared)
        vehicle = canonicalize_vehicle_type(vehicle_info["vehicle_type"]) or "Motorbike"

        payload = {
            "student_id": body.get("student_id", "Unknown"),
            "entry_time": body.get("entry_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "vehicle": vehicle,
            "usual_zone": body.get("usual_zone", "Zone_A"),
            "rolling_avg": body.get("rolling_avg", 200),
            "hist_overnight": body.get("hist_overnight", 0),
        }
        prediction = run_prediction(payload)
        ticket = ticket_store.open_ticket({
            "student_id": payload["student_id"],
            "plate": plate,
            "vehicle_type": vehicle,
            "entry_time": payload["entry_time"],
            "predicted_behavior": prediction.get("behavior"),
            "duration_minutes": prediction.get("duration_minutes"),
            "recommended_zone": prediction.get("recommended_zone"),
            "estimated_exit": prediction.get("estimated_exit"),
            "extra": {"ocr": ocr, "valid_plate": is_valid_vn_plate(plate)},
        })
        return jsonify({
            "status": "success",
            "ticket": ticket,
            "prediction": prediction,
            "ocr": ocr,
            "vehicle": vehicle_info,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/checkout", methods=["POST"])
def checkout():
    try:
        image_bytes = _read_upload()
        body = request.form.to_dict() if request.form else (request.json or {})
        exit_plate, ocr = _plate_from_request(image_bytes)
        ticket_id = body.get("ticket_id")
        open_ticket = None
        if ticket_id:
            open_ticket = ticket_store.get(int(ticket_id))
        if open_ticket is None:
            lookup = normalize_plate(body.get("lookup_plate") or body.get("entry_plate") or "")
            if lookup:
                open_ticket = ticket_store.find_open_by_plate(lookup)
        if open_ticket is None and exit_plate:
            open_ticket = ticket_store.find_open_by_plate(exit_plate)
        if open_ticket is None:
            return jsonify({
                "status": "error",
                "message": "Không tìm thấy vé đang mở. Kiểm tra biển số lúc vào.",
                "ocr": ocr,
            }), 404

        declared = body.get("vehicle") or body.get("vehicle_type")
        vehicle_info = infer_vehicle_type(source=image_bytes, plate=exit_plate, declared=declared)
        exit_vehicle = vehicle_info.get("vehicle_type") or open_ticket.get("vehicle_type")
        exit_time = body.get("exit_time") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        plate_ok = plates_match(open_ticket.get("plate"), exit_plate)
        vehicle_ok = vehicle_types_match(open_ticket.get("vehicle_type"), exit_vehicle)
        penalty = compute_penalty(
            predicted_minutes=int(open_ticket.get("duration_minutes") or 0),
            entry_time=open_ticket.get("entry_time"),
            exit_time=exit_time,
        )

        alerts = []
        if not plate_ok:
            alerts.append("Biển số lúc ra không khớp lúc vào.")
        if not vehicle_ok:
            alerts.append("Loại xe lúc ra không khớp lúc vào.")
        if penalty["is_overtime"]:
            alerts.append(f"Gửi quá giờ {penalty['overtime_minutes']} phút.")

        status = "alert" if (not plate_ok or not vehicle_ok) else "closed"
        closed = ticket_store.close_ticket(open_ticket["id"], {
            "exit_time": exit_time,
            "exit_plate": exit_plate,
            "exit_vehicle_type": exit_vehicle,
            "plate_match": plate_ok,
            "vehicle_match": vehicle_ok,
            "overtime_minutes": penalty["overtime_minutes"],
            "penalty_vnd": penalty["penalty_vnd"],
            "status": status,
            "alert_message": " ".join(alerts),
        })
        return jsonify({
            "status": "success",
            "allowed": plate_ok and vehicle_ok,
            "ticket": closed,
            "penalty": penalty,
            "plate_match": plate_ok,
            "vehicle_match": vehicle_ok,
            "alerts": alerts,
            "ocr": ocr,
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/tickets")
def list_tickets():
    status = request.args.get("status")
    return jsonify({"status": "success", "tickets": ticket_store.list_tickets(status=status)})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
