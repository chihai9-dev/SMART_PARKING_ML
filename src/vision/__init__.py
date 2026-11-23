"""Phát hiện, nhận diện ký tự và phân loại màu nền biển số."""

from src.vision.plate_ocr import (
    PlateRecognizer,
    is_valid_vn_plate,
    normalize_plate,
    plates_match,
    recognize_plate,
)

__all__ = [
    "PlateRecognizer",
    "normalize_plate",
    "plates_match",
    "is_valid_vn_plate",
    "recognize_plate",
]
