"""Nhận diện biển số và loại xe từ ảnh."""

from src.vision.plate_ocr import (
    PlateRecognizer,
    is_valid_vn_plate,
    normalize_plate,
    plates_match,
    recognize_plate,
)
from src.vision.vehicle_type import infer_vehicle_type, vehicle_types_match

__all__ = [
    "PlateRecognizer",
    "normalize_plate",
    "plates_match",
    "is_valid_vn_plate",
    "recognize_plate",
    "infer_vehicle_type",
    "vehicle_types_match",
]
