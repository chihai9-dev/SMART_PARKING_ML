"""Trích xuất 10 đặc trưng HSV từ ảnh vùng biển số đã cắt."""
from __future__ import annotations
import cv2
import numpy as np

FEATURE_NAMES = [
    "white_ratio", "yellow_ratio", "blue_ratio", "red_ratio",
    "mean_hue", "mean_sat", "mean_val", "std_val",
    "dark_pixel_ratio", "bright_pixel_ratio",
]

def extract_plate_color_features(crop_bgr: np.ndarray) -> tuple[np.ndarray, dict[str, float]]:
    """Trả về vector 10 đặc trưng HSV và dictionary để hiển thị qua API."""
    if crop_bgr is None or not isinstance(crop_bgr, np.ndarray) or crop_bgr.size == 0:
        raise ValueError("Ảnh vùng biển số rỗng hoặc không hợp lệ.")
    if crop_bgr.ndim != 3 or crop_bgr.shape[2] != 3:
        raise ValueError("Ảnh đầu vào phải có 3 kênh màu BGR.")

    h, w = crop_bgr.shape[:2]
    my, mx = max(1, int(h * 0.10)), max(1, int(w * 0.10))
    inner = crop_bgr[my:h-my, mx:w-mx] if h > 20 and w > 20 else crop_bgr
    if inner.size == 0:
        inner = crop_bgr

    resized = cv2.resize(inner, (160, 64), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(resized, cv2.COLOR_BGR2HSV)
    h_ch, s_ch, v_ch = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    white = (s_ch <= 55) & (v_ch >= 135)
    yellow = (h_ch >= 14) & (h_ch <= 36) & (s_ch >= 65) & (v_ch >= 90)
    blue = (h_ch >= 95) & (h_ch <= 132) & (s_ch >= 65) & (v_ch >= 45)
    red = ((h_ch <= 10) | (h_ch >= 168)) & (s_ch >= 65) & (v_ch >= 45)
    dark = v_ch < 95
    bright = (s_ch <= 45) & (v_ch >= 180)

    values = {
        "white_ratio": round(float(np.mean(white)), 4),
        "yellow_ratio": round(float(np.mean(yellow)), 4),
        "blue_ratio": round(float(np.mean(blue)), 4),
        "red_ratio": round(float(np.mean(red)), 4),
        "mean_hue": round(float(np.mean(h_ch) / 179.0), 4),
        "mean_sat": round(float(np.mean(s_ch) / 255.0), 4),
        "mean_val": round(float(np.mean(v_ch) / 255.0), 4),
        "std_val": round(float(np.std(v_ch) / 255.0), 4),
        "dark_pixel_ratio": round(float(np.mean(dark)), 4),
        "bright_pixel_ratio": round(float(np.mean(bright)), 4),
    }
    vector = np.array([values[name] for name in FEATURE_NAMES], dtype=np.float32)
    return vector, values
