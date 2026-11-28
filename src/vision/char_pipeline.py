"""Pipeline tự xây: YOLOv8n cắt ký tự → HOG + SVM phân loại → Ghép biển số VN."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import joblib
import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

from src.features.char_hog import CHAR_IMAGE_SIZE, extract_char_hog_features
from src.vision.preprocess import image_to_jpeg_base64

ROOT = Path(__file__).resolve().parents[2]
CHAR_YOLO_ONNX_PATH = ROOT / "models" / "vision" / "char_detect.onnx"
CHAR_SVM_MODEL_PATH = ROOT / "models" / "classification" / "char_svm_model.joblib"

VN_DIGITS = set("0123456789")
VN_LETTERS = set("ABCDEFGHKLMNPRSTUVXYZ")


@dataclass
class CharDetection:
    bbox: list[int]  # [x, y, w, h] trong tọa độ ảnh biển số
    cx: float
    cy: float
    w: float
    h: float
    det_conf: float
    crop: np.ndarray


def _compute_iou(box_a: Sequence[int], box_b: Sequence[int]) -> float:
    ax, ay, aw, ah = box_a
    bx, by, bw, bh = box_b
    x0 = max(ax, bx)
    y0 = max(ay, by)
    x1 = min(ax + aw, bx + bw)
    y1 = min(ay + ah, by + bh)
    inter = max(0, x1 - x0) * max(0, y1 - y0)
    if inter <= 0:
        return 0.0
    union = aw * ah + bw * bh - inter
    return float(inter / max(union, 1))


def deduplicate_char_boxes(
    detections: list[CharDetection],
    iou_thresh: float = 0.45,
) -> list[CharDetection]:
    """Khử box ký tự trùng nhau, giữ box có độ tin cậy cao hơn."""
    ordered = sorted(detections, key=lambda d: d.det_conf, reverse=True)
    kept: list[CharDetection] = []
    for det in ordered:
        is_dup = False
        for existing in kept:
            if _compute_iou(det.bbox, existing.bbox) >= iou_thresh:
                is_dup = True
                break
            # Kiểm tra thêm khoảng cách tâm quá gần (cùng 1 ký tự nhưng box lệch nhẹ)
            dx = abs(det.cx - existing.cx)
            dy = abs(det.cy - existing.cy)
            min_w = min(det.w, existing.w)
            min_h = min(det.h, existing.h)
            if dx < 0.35 * min_w and dy < 0.35 * min_h:
                is_dup = True
                break
        if not is_dup:
            kept.append(det)
    return kept


def sort_characters_vn_plate(
    detections: list[CharDetection],
) -> tuple[list[CharDetection], int]:
    """Sắp xếp danh sách box ký tự theo đúng thứ tự đọc biển số VN (1 dòng hoặc 2 dòng).

    Thuật toán:
    - Nếu chênh lệch trục y giữa các tâm ký tự nhỏ hơn 0.65 * median(h) → biển 1 dòng,
      sắp xếp trực tiếp theo tọa độ cx tăng dần.
    - Nếu lớn hơn → chạy K-Means 1D (k=2) trên tọa độ cy để tách chuẩn hàng trên và
      hàng dưới (chịu được biển bị nghiêng nhẹ), sau đó sắp xếp từng hàng theo cx tăng dần.
    """
    if len(detections) <= 1:
        return list(detections), 1 if detections else 0

    heights = np.array([d.h for d in detections], dtype=np.float32)
    median_h = float(np.median(heights)) if heights.size else 1.0
    ys = np.array([d.cy for d in detections], dtype=np.float32)
    y_span = float(np.max(ys) - np.min(ys))

    if y_span < 0.65 * median_h or len(detections) < 4:
        return sorted(detections, key=lambda d: d.cx), 1

    # K-Means 1D (k=2) đơn giản, xác định (deterministic) khởi tạo bằng min và max cy
    c_top = float(np.min(ys))
    c_bot = float(np.max(ys))
    for _ in range(15):
        assign_top = np.abs(ys - c_top) <= np.abs(ys - c_bot)
        if not np.any(assign_top) or np.all(assign_top):
            break
        new_top = float(np.mean(ys[assign_top]))
        new_bot = float(np.mean(ys[~assign_top]))
        if abs(new_top - c_top) < 1e-3 and abs(new_bot - c_bot) < 1e-3:
            c_top, c_bot = new_top, new_bot
            break
        c_top, c_bot = new_top, new_bot

    if c_top > c_bot:
        c_top, c_bot = c_bot, c_top

    # Chỉ coi là 2 dòng nếu khoảng cách 2 tâm hàng đủ lớn
    if (c_bot - c_top) < 0.65 * median_h:
        return sorted(detections, key=lambda d: d.cx), 1

    top_row: list[CharDetection] = []
    bottom_row: list[CharDetection] = []
    for det in detections:
        if abs(det.cy - c_top) <= abs(det.cy - c_bot):
            top_row.append(det)
        else:
            bottom_row.append(det)

    # Tránh tách nhầm khi một hàng chỉ có 1 ký tự nhiễu
    if len(top_row) < 2 or len(bottom_row) < 2:
        return sorted(detections, key=lambda d: d.cx), 1

    top_row.sort(key=lambda d: d.cx)
    bottom_row.sort(key=lambda d: d.cx)
    return top_row + bottom_row, 2


def _allowed_charset_for_position(pos: int, total_len: int) -> Optional[set[str]]:
    """Trả về tập ký tự hợp lệ theo quy tắc vị trí biển số Việt Nam.

    - Vị trí 0, 1: Mã tỉnh/thành (luôn là chữ số 0-9).
    - Vị trí 2: Seri chữ (luôn là chữ cái A-Z).
    - 4 ký tự cuối (khi tổng độ dài >= 7): Dãy số đăng ký (luôn là chữ số 0-9).
    - Vị trí 3 (khi tổng độ dài 8 hoặc 9): Có thể là chữ (51LD12345) hoặc số (59B112345).
    """
    if total_len < 6:
        return None
    if pos in (0, 1):
        return VN_DIGITS
    if pos == 2:
        return VN_LETTERS
    if total_len >= 7 and pos >= total_len - 4:
        return VN_DIGITS
    return None


def decode_plate_with_constraints(
    prob_matrix: np.ndarray,
    classes: Sequence[str],
) -> tuple[str, float, list[dict[str, Any]]]:
    """Constrained Decoding: chọn ký tự có xác suất cao nhất thỏa luật vị trí biển VN."""
    class_list = [str(c).upper() for c in classes]
    total = len(prob_matrix)
    chosen_chars: list[str] = []
    char_details: list[dict[str, Any]] = []

    for idx in range(total):
        probs = np.asarray(prob_matrix[idx], dtype=np.float64)
        raw_best_idx = int(np.argmax(probs))
        raw_char = class_list[raw_best_idx]
        raw_conf = float(probs[raw_best_idx])

        allowed = _allowed_charset_for_position(idx, total)
        final_char = raw_char
        final_conf = raw_conf
        constrained = False

        if allowed is not None and raw_char not in allowed:
            candidate_indices = [
                i for i, ch in enumerate(class_list) if ch in allowed
            ]
            if candidate_indices:
                best_allowed_idx = max(candidate_indices, key=lambda i: probs[i])
                final_char = class_list[best_allowed_idx]
                final_conf = float(probs[best_allowed_idx])
                constrained = True

        chosen_chars.append(final_char)
        char_details.append({
            "position": idx,
            "char": final_char,
            "confidence": round(final_conf, 4),
            "raw_char": raw_char,
            "raw_confidence": round(raw_conf, 4),
            "constrained": constrained,
        })

    plate = "".join(chosen_chars)
    mean_conf = (
        float(np.mean([d["confidence"] for d in char_details]))
        if char_details
        else 0.0
    )
    return plate, round(mean_conf, 4), char_details


class CustomCharALPR:
    """Pipeline nhận diện biển số tự xây: YOLOv8n (cắt ký tự) + HOG & SVM (đọc ký tự)."""

    def __init__(
        self,
        yolo_onnx_path: Path = CHAR_YOLO_ONNX_PATH,
        svm_model_path: Path = CHAR_SVM_MODEL_PATH,
        input_size: int = 320,
    ) -> None:
        self.yolo_onnx_path = Path(yolo_onnx_path)
        self.svm_model_path = Path(svm_model_path)
        self.input_size = input_size
        self._yolo_session = None
        self._yolo_input_name = "images"
        self._svm_model = None
        self._loaded = False

    def _ensure_loaded(self) -> bool:
        if self._loaded:
            return self._yolo_session is not None and self._svm_model is not None
        self._loaded = True

        if not self.yolo_onnx_path.exists() or not self.svm_model_path.exists():
            return False

        try:
            import onnxruntime as ort

            self._yolo_session = ort.InferenceSession(
                str(self.yolo_onnx_path),
                providers=["CPUExecutionProvider"],
            )
            inp = self._yolo_session.get_inputs()[0]
            self._yolo_input_name = inp.name
            if len(inp.shape) == 4 and isinstance(inp.shape[2], int) and inp.shape[2] > 0:
                self.input_size = int(inp.shape[2])
            self._svm_model = joblib.load(self.svm_model_path)
            return True
        except Exception:
            self._yolo_session = None
            self._svm_model = None
            return False

    @property
    def is_available(self) -> bool:
        return self._ensure_loaded()

    def detect_characters(
        self,
        plate_bgr: np.ndarray,
        conf_thresh: float = 0.25,
        iou_thresh: float = 0.45,
        pad_ratio: float = 0.06,
    ) -> list[CharDetection]:
        """Chạy YOLOv8n ONNX trên ảnh biển số để cắt thành từng ảnh ký tự nhỏ."""
        if not self._ensure_loaded() or cv2 is None or plate_bgr is None or plate_bgr.size == 0:
            return []

        h, w = plate_bgr.shape[:2]
        imgsz = self.input_size
        scale = float(imgsz) / max(h, w)
        nh, nw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))
        resized = cv2.resize(plate_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((imgsz, imgsz, 3), dtype=np.uint8)
        canvas[:nh, :nw] = resized

        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 255.0, (imgsz, imgsz), swapRB=True)
        outputs = self._yolo_session.run(None, {self._yolo_input_name: blob})[0]

        # Hỗ trợ cả output [1, 4+nc, N] (chuẩn Ultralytics) và [1, N, 4+nc]
        raw = outputs[0]
        preds = raw.T if raw.shape[0] < raw.shape[1] else raw

        boxes: list[list[int]] = []
        scores: list[float] = []
        for row in preds:
            # 1 class: row[4]; đa class: max(row[4:])
            conf = float(np.max(row[4:])) if len(row) > 5 else float(row[4])
            if conf < conf_thresh:
                continue
            xc, yc, bw, bh = row[:4]
            x0 = max(0, int((xc - bw / 2.0) / scale))
            y0 = max(0, int((yc - bh / 2.0) / scale))
            box_w = min(w - x0, int(bw / scale))
            box_h = min(h - y0, int(bh / scale))
            # Lọc nhiễu quá nhỏ (ốc vít, dấu chấm)
            if box_w < max(4, int(w * 0.02)) or box_h < max(8, int(h * 0.12)):
                continue
            boxes.append([x0, y0, box_w, box_h])
            scores.append(conf)

        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(boxes, scores, conf_thresh, iou_thresh)
        detections: list[CharDetection] = []
        for idx_raw in indices:
            idx = int(idx_raw)
            bx, by, bw, bh = boxes[idx]
            pad_x = max(1, int(round(bw * pad_ratio)))
            pad_y = max(1, int(round(bh * pad_ratio)))
            x0 = max(0, bx - pad_x)
            y0 = max(0, by - pad_y)
            x1 = min(w, bx + bw + pad_x)
            y1 = min(h, by + bh + pad_y)
            crop = plate_bgr[y0:y1, x0:x1]
            if crop.size == 0:
                continue
            detections.append(
                CharDetection(
                    bbox=[int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
                    cx=bx + bw / 2.0,
                    cy=by + bh / 2.0,
                    w=float(bw),
                    h=float(bh),
                    det_conf=float(scores[idx]),
                    crop=crop,
                )
            )

        return deduplicate_char_boxes(detections, iou_thresh=iou_thresh)

    def recognize_plate_crop(
        self,
        plate_bgr: np.ndarray,
        include_char_crops_b64: bool = False,
    ) -> dict[str, Any]:
        """Nhận diện đầy đủ từ ảnh crop biển số → chuỗi biển số + chi tiết từng ký tự."""
        detections = self.detect_characters(plate_bgr)
        if not detections:
            return {
                "plate": "",
                "confidence": 0.0,
                "line_count": 0,
                "characters": [],
                "engine": "custom_yolo_hog_svm",
            }

        ordered, line_count = sort_characters_vn_plate(detections)
        features = np.vstack([
            extract_char_hog_features(det.crop, size=CHAR_IMAGE_SIZE)
            for det in ordered
        ])

        if hasattr(self._svm_model, "predict_proba"):
            probs = self._svm_model.predict_proba(features)
            classes = list(self._svm_model.classes_)
            plate, mean_conf, details = decode_plate_with_constraints(probs, classes)
        else:
            preds = self._svm_model.predict(features)
            plate = "".join(str(p).upper() for p in preds)
            mean_conf = float(np.mean([d.det_conf for d in ordered]))
            details = [
                {
                    "position": i,
                    "char": str(p).upper(),
                    "confidence": round(float(ordered[i].det_conf), 4),
                    "raw_char": str(p).upper(),
                    "raw_confidence": round(float(ordered[i].det_conf), 4),
                    "constrained": False,
                }
                for i, p in enumerate(preds)
            ]

        for det, item in zip(ordered, details):
            item["bbox"] = det.bbox
            item["det_confidence"] = round(det.det_conf, 4)
            if include_char_crops_b64:
                item["crop_jpeg_b64"] = image_to_jpeg_base64(det.crop)

        return {
            "plate": plate,
            "confidence": mean_conf,
            "line_count": line_count,
            "characters": details,
            "engine": "custom_yolo_hog_svm",
        }


_DEFAULT_CUSTOM_ALPR: Optional[CustomCharALPR] = None


def get_custom_char_alpr() -> CustomCharALPR:
    global _DEFAULT_CUSTOM_ALPR
    if _DEFAULT_CUSTOM_ALPR is None:
        _DEFAULT_CUSTOM_ALPR = CustomCharALPR()
    return _DEFAULT_CUSTOM_ALPR
