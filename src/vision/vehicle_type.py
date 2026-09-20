"""Suy ra loại xe (xe máy / ô tô) từ biển số hoặc ảnh."""

from __future__ import annotations

from typing import Any, Optional

from src.vision.plate_ocr import normalize_plate
from src.vision.preprocess import ImageInput, load_image

_CANON = {
    "motorbike": "Motorbike",
    "xe máy": "Motorbike",
    "xe may": "Motorbike",
    "bike": "Motorbike",
    "motorcycle": "Motorbike",
    "car": "Car",
    "ô tô": "Car",
    "o to": "Car",
    "oto": "Car",
    "automobile": "Car",
}


def canonicalize_vehicle_type(raw: Optional[str]) -> str:
    if not raw:
        return ""
    key = str(raw).strip().lower()
    return _CANON.get(key, str(raw).strip().title())


def infer_vehicle_type_from_plate(plate: str) -> str:
    """Xe máy VN thường có series chữ+số (59B1…); ô tô series chỉ chữ (51A…)."""
    p = normalize_plate(plate)
    if len(p) >= 9 and p[2].isalpha() and p[3].isdigit():
        return "Motorbike"
    if p:
        return "Car"
    return ""


def infer_vehicle_type(
    source: Optional[ImageInput] = None,
    plate: Optional[str] = None,
    declared: Optional[str] = None,
) -> dict[str, Any]:
    """
    Ưu tiên loại xe người dùng chọn; nếu không có thì suy từ biển;
    ảnh dùng heuristic kích thước (ô tô khung hình thường rộng hơn) khi chưa có model CNN.
    """
    if declared:
        vtype = canonicalize_vehicle_type(declared)
        return {"vehicle_type": vtype, "source": "declared", "confidence": 1.0}

    if plate:
        vtype = infer_vehicle_type_from_plate(plate)
        if vtype:
            return {"vehicle_type": vtype, "source": "plate_pattern", "confidence": 0.8}

    if source is not None:
        image = load_image(source)
        h, w = image.shape[:2]
        ratio = w / max(h, 1)
        vtype = "Car" if ratio > 1.45 else "Motorbike"
        return {
            "vehicle_type": vtype,
            "source": "image_aspect",
            "confidence": 0.4,
            "aspect_ratio": round(ratio, 3),
        }

    return {"vehicle_type": "", "source": "unknown", "confidence": 0.0}


def vehicle_types_match(entry_type: str, exit_type: str) -> bool:
    a = canonicalize_vehicle_type(entry_type)
    b = canonicalize_vehicle_type(exit_type)
    if not a or not b:
        return False
    return a == b
