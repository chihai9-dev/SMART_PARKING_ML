"""Tìm vùng biển số trong ảnh (xe + nền), không chỉ ảnh crop sẵn."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

from src.vision.preprocess import resize_max

_yolo_session = None
_yolo_loaded = False


def _get_yolo_session():
    """Tải ONNX session cho mô hình YOLOv8 phát hiện biển số."""
    global _yolo_session, _yolo_loaded
    if _yolo_loaded:
        return _yolo_session
    _yolo_loaded = True
    try:
        import onnxruntime as ort
        model_path = Path(__file__).resolve().parents[2] / "models" / "vision" / "best.onnx"
        if model_path.exists():
            _yolo_session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    except Exception:
        _yolo_session = None
    return _yolo_session


def _detect_yolo_plates(image: np.ndarray, conf_thresh: float = 0.35) -> list[dict[str, Any]]:
    """Dùng mô hình YOLO ONNX để định vị biển số nhanh và chính xác."""
    session = _get_yolo_session()
    if session is None or cv2 is None:
        return []
    try:
        h, w = image.shape[:2]
        scale = 640.0 / max(h, w)
        nh, nw = int(h * scale), int(w * scale)
        resized = cv2.resize(image, (nw, nh))
        canvas = np.zeros((640, 640, 3), dtype=np.uint8)
        canvas[:nh, :nw] = resized

        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 255.0, (640, 640), swapRB=True)
        outputs = session.run(None, {"images": blob})[0]
        preds = outputs[0].T  # shape [8400, 5]

        boxes, scores = [], []
        for row in preds:
            conf = float(row[4])
            if conf >= conf_thresh:
                xc, yc, bw, bh = row[:4]
                x0 = max(0, int((xc - bw / 2.0) / scale))
                y0 = max(0, int((yc - bh / 2.0) / scale))
                bw = min(w - x0, int(bw / scale))
                bh = min(h - y0, int(bh / scale))
                if bw > 15 and bh > 15:
                    boxes.append([x0, y0, bw, bh])
                    scores.append(conf)

        if not boxes:
            return []

        indices = cv2.dnn.NMSBoxes(boxes, scores, conf_thresh, 0.45)
        candidates = []
        for i in indices:
            idx = int(i)
            bx, by, bw, bh = boxes[idx]
            # Mở rộng biên nhẹ (padding 5%) để tránh cắt sát mép chữ biển số
            pad_x = int(bw * 0.05)
            pad_y = int(bh * 0.05)
            x0 = max(0, bx - pad_x)
            y0 = max(0, by - pad_y)
            x1 = min(w, bx + bw + pad_x)
            y1 = min(h, by + bh + pad_y)
            crop = image[y0:y1, x0:x1]
            if crop.size > 0:
                candidates.append({
                    "bbox": [x0, y0, x1 - x0, y1 - y0],
                    "crop": crop,
                    "score": float(scores[idx]) + 2.0,  # Ưu tiên cao hơn thuật toán contour
                })
        return candidates
    except Exception:
        return []


def _score_box(w: int, h: int, img_area: int) -> float:
    if h <= 0 or w <= 0:
        return 0.0
    ratio = w / float(h)
    area = w * h
    area_ratio = area / max(img_area, 1)
    
    # Kích thước biển số: 
    # Ô tô (1 dòng) ratio ~ 4.7
    # Xe máy (2 dòng) ratio ~ 1.3 - 1.4
    if 1.15 <= ratio <= 6.0 and 0.003 <= area_ratio <= 0.35:
        ideal = 2.2 if ratio < 2.4 else 4.2
        
        # ĐIỂM TỈ LỆ (Càng gần hình dáng biển số càng tốt)
        ratio_score = 1.0 - min(abs(ratio - ideal) / 4.0, 1.0)
        
        # ĐIỂM DIỆN TÍCH (Tăng mạnh trọng số: Biển càng to thì điểm càng cao)
        # Hệ số cũ là * 4, giờ tăng lên * 10 để ưu tiên biển gần camera
        area_score = min(area_ratio * 10, 1.0) 
        
        return ratio_score + area_score
    return 0.0


def find_plate_regions(image: np.ndarray, max_candidates: int = 5) -> list[dict[str, Any]]:
    """Trả về các vùng nghi là biển số, điểm cao trước."""
    if cv2 is None:
        h, w = image.shape[:2]
        return [{"bbox": [0, 0, w, h], "crop": image, "score": 0.1}]

    # 0) Ưu tiên sử dụng mô hình YOLO ONNX
    yolo_candidates = _detect_yolo_plates(image)
    if yolo_candidates:
        h, w = image.shape[:2]
        full = {"bbox": [0, 0, w, h], "crop": image, "score": 0.02}
        yolo_candidates.sort(key=lambda c: c["score"], reverse=True)
        results = yolo_candidates[:max(1, max_candidates - 1)]
        results.append(full)
        return results

    image = resize_max(image, 1600)
    h, w = image.shape[:2]
    img_area = h * w
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 11, 60, 60)

    candidates: list[dict[str, Any]] = []
    seen: set[tuple[int, int, int, int]] = set()

    def add_rect(x: int, y: int, bw: int, bh: int, extra: float = 0.0) -> None:
        pad_x, pad_y = int(bw * 0.06), int(bh * 0.12)
        x0 = max(0, x - pad_x)
        y0 = max(0, y - pad_y)
        x1 = min(w, x + bw + pad_x)
        y1 = min(h, y + bh + pad_y)
        key = (x0 // 8, y0 // 8, x1 // 8, y1 // 8)
        if key in seen:
            return
        score = _score_box(x1 - x0, y1 - y0, img_area) + extra
        if score <= 0:
            return
        seen.add(key)
        crop = image[y0:y1, x0:x1]
        if crop.size == 0:
            return
        candidates.append({
            "bbox": [int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
            "crop": crop,
            "score": float(score),
        })

    # 1) Cạnh + hình chữ nhật
    edges = cv2.Canny(gray, 60, 180)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 5))
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        add_rect(x, y, bw, bh)

    # 2) Vùng sáng (biển trắng / vàng)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    white = cv2.inRange(hsv, (0, 0, 140), (180, 80, 255))
    yellow = cv2.inRange(hsv, (15, 40, 80), (40, 255, 255))
    mask = cv2.bitwise_or(white, yellow)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5)))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        add_rect(x, y, bw, bh, extra=0.15)

    # 3) Black-hat: chữ tối trên nền sáng
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)
    _, thresh = cv2.threshold(blackhat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = cv2.dilate(thresh, kernel, iterations=1)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in contours:
        x, y, bw, bh = cv2.boundingRect(cnt)
        add_rect(x, y, bw, bh, extra=0.1)

    candidates.sort(key=lambda c: c["score"], reverse=True)
    if not candidates:
        candidates.append({"bbox": [0, 0, w, h], "crop": image, "score": 0.05})
    # Luôn giữ toàn ảnh ở cuối như phương án dự phòng. Trường hợp webcam
    # có biển số lớn nhưng các contour không rõ, OCR vẫn còn cơ hội đọc được.
    full = {"bbox": [0, 0, w, h], "crop": image, "score": 0.02}
    candidates = sorted(candidates, key=lambda c: c["score"], reverse=True)
    normal = candidates[:max(1, max_candidates - 1)]
    normal.append(full)
    return normal


def annotate_plate(image: np.ndarray, bbox: list[int], label: str = "") -> np.ndarray:
    """Vẽ khung vùng biển lên ảnh gốc."""
    out = image.copy()
    if cv2 is None:
        return out
    x, y, bw, bh = bbox
    cv2.rectangle(out, (x, y), (x + bw, y + bh), (0, 200, 80), 3)
    if label:
        cv2.putText(out, label, (x, max(20, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 200, 80), 2)
    return out
