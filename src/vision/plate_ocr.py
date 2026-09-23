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
_OCR_LETTER_FIX = {"0": "O", "1": "I", "2": "Z", "5": "S", "8": "B"}


def normalize_plate(raw: Optional[str]) -> str:
    """Chuẩn hóa biển số Việt Nam và sửa một số lỗi OCR thường gặp.

    OCR camera hay nhầm O/0, I/1, S/5... Vì phần đầu biển có thể là chữ
    còn phần đuôi chủ yếu là số, hàm xử lý từng vùng thay vì đổi toàn chuỗi.
    """
    if raw is None:
        return ""
    text = re.sub(r"[^A-Z0-9]", "", str(raw).upper())
    if not text:
        return ""

    chars = list(text)

    # Hai ký tự đầu luôn là mã tỉnh/thành dạng số.
    for i in range(min(2, len(chars))):
        chars[i] = _OCR_DIGIT_FIX.get(chars[i], chars[i])

    if len(chars) <= 2:
        return "".join(chars)

    # Phần sau mã tỉnh: tìm chuỗi số ở cuối, thường dài 4-6 ký tự.
    # Các ký tự ngay trước phần số được coi là seri chữ và sửa 0/1/... -> O/I/...
    tail_len = 0
    for ch in reversed(chars):
        if ch.isdigit():
            tail_len += 1
        else:
            break
    tail_len = min(tail_len, 6)
    prefix_end = len(chars) - tail_len if tail_len >= 4 else min(len(chars), 5)

    for i in range(2, prefix_end):
        if chars[i].isdigit():
            chars[i] = _OCR_LETTER_FIX.get(chars[i], chars[i])

    # Phần số cuối: sửa ký tự OCR bị đọc thành chữ.
    digit_start = max(prefix_end, 2)
    for i in range(digit_start, len(chars)):
        chars[i] = _OCR_DIGIT_FIX.get(chars[i], chars[i])

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
                from rapidocr import RapidOCR
            except ImportError:
                from rapidocr_onnxruntime import RapidOCR
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
            try:
                output = rapid(rgb)
                items: list[tuple[str, float]] = []
                # RapidOCR versions return either an object with txts/scores
                # or a tuple/list containing [box, text, score] rows.
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
                if items:
                    return items, "rapidocr"
            except Exception as exc:
                print(f"RapidOCR frame error: {exc}")

        reader = self._easyocr()
        if reader is not None:
            try:
                results = reader.readtext(rgb)
                items = [(str(text), float(conf)) for _, text, conf in results]
                if items:
                    return items, "easyocr"
            except Exception as exc:
                print(f"EasyOCR frame error: {exc}")

        # Tesseract fallback: thử vài kiểu tiền xử lý/PSM để tăng khả năng đọc
        # biển bị nhỏ, lệch sáng hoặc có hai dòng.
        best_items: list[tuple[str, float]] = []
        variants: list[np.ndarray] = [prepared]
        try:
            import cv2
            gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
            gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray)
            _, otsu = cv2.threshold(clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            adaptive = cv2.adaptiveThreshold(clahe, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7)
            variants.extend([cv2.cvtColor(otsu, cv2.COLOR_GRAY2BGR), cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR)])
        except Exception:
            pass

        for variant in variants:
            for psm in (7, 6, 11):
                result = _try_tesseract(variant, psm=psm)
                if result is None:
                    continue
                plate, conf, raw = result
                if not raw:
                    continue
                score = (2.0 if is_valid_vn_plate(plate) else 0.0) + conf + min(len(plate), 10) / 100.0
                current_score = (2.0 if any(is_valid_vn_plate(normalize_plate(t)) for t, _ in best_items) else 0.0) + (best_items[0][1] if best_items else 0.0)
                if not best_items or score > current_score:
                    best_items = [(raw, conf)]
        return best_items, "tesseract" if best_items else "none"

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
            best["message"] = "Chưa cài engine OCR. Chạy: python -m pip install rapidocr onnxruntime"

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


def _try_tesseract(image_bgr: np.ndarray, psm: int = 7) -> Optional[tuple[str, float, str]]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None
    rgb = image_bgr[:, :, ::-1]
    pil = Image.fromarray(rgb)
    raw = pytesseract.image_to_string(
        pil,
        config=f"--psm {psm} -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.",
    )
    plate = normalize_plate(raw)
    conf = 0.7 if is_valid_vn_plate(plate) else 0.3 if plate else 0.0
    return plate, conf, raw.strip()
