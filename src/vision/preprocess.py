"""Tiền xử lý ảnh trước khi OCR biển số."""

from __future__ import annotations

from io import BytesIO
from typing import Union

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

from PIL import Image, ImageOps

ImageInput = Union[str, bytes, np.ndarray, Image.Image]


def load_image(source: ImageInput) -> np.ndarray:
    """Đọc ảnh từ đường dẫn, bytes, ndarray hoặc PIL.Image → BGR uint8."""
    if isinstance(source, np.ndarray):
        img = source
        if img.ndim == 2:
            if cv2 is not None:
                return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            return np.stack([img, img, img], axis=-1)
        if img.shape[2] == 4:
            return img[:, :, :3]
        return img

    if isinstance(source, Image.Image):
        pil = ImageOps.exif_transpose(source).convert("RGB")
        rgb = np.array(pil)
        return rgb[:, :, ::-1].copy()

    if isinstance(source, bytes):
        pil = ImageOps.exif_transpose(Image.open(BytesIO(source))).convert("RGB")
        rgb = np.array(pil)
        return rgb[:, :, ::-1].copy()

    if isinstance(source, str):
        if cv2 is not None:
            img = cv2.imread(source)
            if img is not None:
                return img
        pil = ImageOps.exif_transpose(Image.open(source)).convert("RGB")
        rgb = np.array(pil)
        return rgb[:, :, ::-1].copy()

    raise TypeError(f"Không đọc được ảnh từ kiểu {type(source)}")


def resize_max(image: np.ndarray, max_side: int = 1280) -> np.ndarray:
    """Giới hạn cạnh dài để OCR nhanh hơn."""
    h, w = image.shape[:2]
    longest = max(h, w)
    if longest <= max_side:
        return image
    scale = max_side / float(longest)
    new_w, new_h = int(w * scale), int(h * scale)
    if cv2 is not None:
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    pil = Image.fromarray(image[:, :, ::-1])
    pil = pil.resize((new_w, new_h), Image.Resampling.LANCZOS)
    return np.array(pil)[:, :, ::-1].copy()


def preprocess_for_ocr(image: np.ndarray) -> np.ndarray:
    """Tăng tương phản, khử nhiễu nhẹ, trả về ảnh BGR đã xử lý."""
    image = resize_max(image)
    if cv2 is None:
        return image

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bilateralFilter(gray, 7, 50, 50)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)


def image_to_jpeg_bytes(image: np.ndarray, quality: int = 85) -> bytes:
    rgb = image[:, :, ::-1] if image.ndim == 3 else image
    buf = BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def image_to_jpeg_base64(image: np.ndarray, quality: int = 85) -> str:
    import base64

    return base64.b64encode(image_to_jpeg_bytes(image, quality)).decode("ascii")
