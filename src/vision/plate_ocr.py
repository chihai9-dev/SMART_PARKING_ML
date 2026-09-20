"""Nhận diện và chuẩn hóa biển số xe Việt Nam."""

from __future__ import annotations

import re
from typing import Any, Optional

import numpy as np

from src.vision.plate_detect import annotate_plate, find_plate_regions
from src.vision.preprocess import (
    ImageInput,
    image_to_jpeg_base64,
    load_image,
    preprocess_for_ocr,
    resize_max,
)

# 51A12345, 51AB12345, 59B112345, cho phép OCR nhầm O/0
_PLATE_RE = re.compile(r"^\d{2}[A-Z]{1,3}\d{4,6}$")


_OCR_DIGIT_FIX = {"O": "0", "D": "0", "Q": "0", "I": "1", "L": "1", "Z": "2", "S": "5"}


def normalize_plate(raw: Optional[str]) -> str:
    """Bỏ dấu chấm, gạch, khoảng trắng; viết hoa; sửa nhầm OCR ở vị trí số."""
    if raw is None:
        return ""
    text = re.sub(r"[^A-Z0-9]", "", str(raw).upper())
    if not text:
        return ""
    chars = list(text)
    for i, ch in enumerate(chars):
        # Mã tỉnh (2 số đầu) và phần số đuôi (từ ký tự thứ 4).
        if i < 2 or i >= 4:
            chars[i] = _OCR_DIGIT_FIX.get(ch, ch)
        elif i == 3 and ch in _OCR_DIGIT_FIX and len(chars) >= 9:
            chars[i] = _OCR_DIGIT_FIX[ch]
    return "".join(chars)


def is_valid_vn_plate(plate: str) -> bool:
    """Kiểm tra biển đã chuẩn hóa có dạng biển VN thông dụng."""
    return bool(_PLATE_RE.match(normalize_plate(plate)))


def plates_match(entry_plate: str, exit_plate: str) -> bool:
    """Hai biển khớp sau khi chuẩn hóa."""
    a, b = normalize_plate(entry_plate), normalize_plate(exit_plate)
    if not a or not b:
        return False
    return a == b


def _pick_best_ocr_text(items: list[tuple[str, float]]) -> tuple[str, float]:
    """Ưu tiên chuỗi giống biển số, sau đó theo độ tin cậy."""
    scored: list[tuple[float, str, float]] = []
    for text, conf in items:
        plate = normalize_plate(text)
        bonus = 2.0 if is_valid_vn_plate(plate) else (0.5 if plate else -1.0)
        scored.append((bonus + conf, plate or normalize_plate(text), conf))
    if not scored:
        return "", 0.0
    scored.sort(reverse=True)
    return scored[0][1], float(scored[0][2])


def _assemble_from_items(items: list[tuple[str, float]]) -> tuple[str, float]:
    """Gộp nhiều dòng OCR (biển xe máy 2 hàng) thành một biển."""
    if not items:
        return "", 0.0
    joined = normalize_plate("".join(text for text, _ in items))
    best, conf = _pick_best_ocr_text(items)
    if is_valid_vn_plate(joined) and (not is_valid_vn_plate(best) or len(joined) >= len(best)):
        avg = sum(c for _, c in items) / max(len(items), 1)
        return joined, float(avg)
    if is_valid_vn_plate(best):
        return best, conf
    return joined or best, conf


class PlateRecognizer:
    """Tìm vùng biển trong ảnh, rồi OCR (RapidOCR → EasyOCR → Tesseract)."""

    def __init__(self) -> None:
        self._rapid = None
        self._rapid_failed = False
        self._easyocr_reader = None
        self._easyocr_failed = False

    def _rapidocr(self):
        if self._rapid_failed:
            return None
        if self._rapid is not None:
            return self._rapid
        try:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError:
                from rapidocr import RapidOCR
            self._rapid = RapidOCR()
            return self._rapid
        except Exception as e:
            import traceback
            print("=== LỖI KHỞI TẠO RAPIDOCR ===")
            print(f"Lỗi: {e}")
            traceback.print_exc()
            print("=============================")
            self._rapid_failed = True
            return None

    def _easyocr(self):
        if self._easyocr_failed:
            return None
        if self._easyocr_reader is not None:
            return self._easyocr_reader
        try:
            import easyocr

            self._easyocr_reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            return self._easyocr_reader
        except Exception:
            self._easyocr_failed = True
            return None

    def _ocr_image(self, image_bgr: np.ndarray) -> tuple[list[tuple[str, float]], str]:
        prepared = preprocess_for_ocr(image_bgr)
        rgb = prepared[:, :, ::-1]

        rapid = self._rapidocr()
        if rapid is not None:
            output = rapid(rgb)
            items: list[tuple[str, float]] = []
            if hasattr(output, "txts") and output.txts:
                scores = list(getattr(output, "scores", []) or [])
                for i, txt in enumerate(output.txts):
                    score = float(scores[i]) if i < len(scores) else 0.0
                    items.append((str(txt), score))
            else:
                rows = output[0] if isinstance(output, tuple) else output
                if rows:
                    for row in rows:
                        if row is None:
                            continue
                        if isinstance(row, dict):
                            items.append((str(row.get("txt") or row.get("text") or ""), float(row.get("score") or 0)))
                        elif len(row) >= 3:
                            items.append((str(row[1]), float(row[2])))
            return items, "rapidocr"

        reader = self._easyocr()
        if reader is not None:
            results = reader.readtext(rgb)
            items = [(str(text), float(conf)) for _, text, conf in results]
            return items, "easyocr"

        tess = _try_tesseract(prepared)
        if tess is not None:
            plate, conf, raw = tess
            return [(raw, conf)], "tesseract"

        return [], "none"

    def recognize(self, source: ImageInput) -> dict[str, Any]:
        image = resize_max(load_image(source), 1600)
        regions = find_plate_regions(image)
        engine = "none"
        best: dict[str, Any] | None = None

        for region in regions:
            items, engine = self._ocr_image(region["crop"])
            plate, conf = _assemble_from_items(items)
            candidate = {
                "plate": plate,
                "raw_candidates": items,
                "confidence": conf,
                "engine": engine,
                "valid": is_valid_vn_plate(plate),
                "bbox": region["bbox"],
                "region_score": region["score"],
            }
            if best is None:
                best = candidate
            else:
                best_key = (int(best["valid"]), best["confidence"], best.get("region_score", 0))
                new_key = (int(candidate["valid"]), candidate["confidence"], candidate["region_score"])
                if new_key > best_key:
                    best = candidate
            if candidate["valid"] and conf >= 0.35:
                break

        if best is None:
            best = {
                "plate": "",
                "raw_candidates": [],
                "confidence": 0.0,
                "engine": engine,
                "valid": False,
                "bbox": [0, 0, image.shape[1], image.shape[0]],
            }

        if engine == "none" and not best["plate"]:
            best["message"] = "Chưa cài engine OCR. Chạy: pip install rapidocr-onnxruntime"

        bbox = best.get("bbox") or [0, 0, image.shape[1], image.shape[0]]
        x, y, bw, bh = bbox
        crop = image[y:y + bh, x:x + bw]
        if crop.size == 0:
            crop = image
        annotated = annotate_plate(image, bbox, best.get("plate") or "")
        best["crop_jpeg_b64"] = image_to_jpeg_base64(crop)
        best["annotated_jpeg_b64"] = image_to_jpeg_base64(annotated)
        return best


_DEFAULT_RECOGNIZER: Optional[PlateRecognizer] = None


def get_recognizer() -> PlateRecognizer:
    global _DEFAULT_RECOGNIZER
    if _DEFAULT_RECOGNIZER is None:
        _DEFAULT_RECOGNIZER = PlateRecognizer()
    return _DEFAULT_RECOGNIZER


def recognize_plate(source: ImageInput) -> dict[str, Any]:
    """Nhận diện biển số từ ảnh (đường dẫn, bytes hoặc ndarray)."""
    return get_recognizer().recognize(source)


def _try_tesseract(image_bgr: np.ndarray) -> Optional[tuple[str, float, str]]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None
    rgb = image_bgr[:, :, ::-1]
    pil = Image.fromarray(rgb)
    raw = pytesseract.image_to_string(
        pil,
        config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.",
    )
    plate = normalize_plate(raw)
    conf = 0.7 if is_valid_vn_plate(plate) else 0.3 if plate else 0.0
    return plate, conf, raw.strip()
