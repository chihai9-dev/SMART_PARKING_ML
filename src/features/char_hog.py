"""Tiền xử lý ảnh ký tự biển số và trích xuất đặc trưng HOG (thuần NumPy, đồng nhất giữa Colab & local)."""

from __future__ import annotations

from typing import Tuple

import numpy as np

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

CHAR_IMAGE_SIZE: Tuple[int, int] = (32, 32)
HOG_CELL_SIZE: int = 8
HOG_BLOCK_CELLS: int = 2
HOG_NBINS: int = 9


def preprocess_char_crop(
    crop: np.ndarray,
    size: Tuple[int, int] = CHAR_IMAGE_SIZE,
) -> np.ndarray:
    """Chuẩn hóa ảnh ký tự nhỏ về ảnh xám kích thước chuẩn mà không làm méo tỷ lệ.

    Các bước:
    1. Chuyển sang ảnh xám (grayscale).
    2. Cân bằng tương phản cục bộ nhẹ (CLAHE) để giảm ảnh hưởng bóng đổ/ánh sáng.
    3. Letterbox padding thành hình vuông (giữ nguyên tỷ lệ khung hình để số '1', chữ 'I'
       không bị kéo bè thành hình vuông).
    4. Resize về kích thước chuẩn (mặc định 32x32).
    """
    if crop is None or crop.size == 0:
        return np.zeros((size[1], size[0]), dtype=np.uint8)

    if crop.ndim == 3:
        if cv2 is not None and hasattr(cv2, "cvtColor"):
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        else:
            gray = np.mean(crop, axis=2).astype(np.uint8)
    else:
        gray = crop.astype(np.uint8, copy=True)

    if cv2 is not None and hasattr(cv2, "createCLAHE"):
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        gray = clahe.apply(gray)

    h, w = gray.shape[:2]
    if h == 0 or w == 0:
        return np.zeros((size[1], size[0]), dtype=np.uint8)

    # Dùng màu nền ước lượng từ viền ảnh để pad tự nhiên (hợp cả biển trắng lẫn vàng).
    border_pixels = np.concatenate([
        gray[0, :],
        gray[-1, :],
        gray[:, 0],
        gray[:, -1],
    ])
    pad_val = int(np.median(border_pixels)) if border_pixels.size else 255

    side = max(h, w)
    # Thêm khoảng đệm nhỏ (~12%) để nét ký tự không chạm sát biên ảnh HOG.
    canvas_side = max(side + max(2, int(round(side * 0.12))), 4)
    canvas = np.full((canvas_side, canvas_side), pad_val, dtype=np.uint8)
    y_off = (canvas_side - h) // 2
    x_off = (canvas_side - w) // 2
    canvas[y_off : y_off + h, x_off : x_off + w] = gray

    if cv2 is not None and hasattr(cv2, "resize"):
        interp = cv2.INTER_AREA if canvas_side > size[0] else cv2.INTER_CUBIC
        return cv2.resize(canvas, size, interpolation=interp)

    from PIL import Image

    pil = Image.fromarray(canvas).resize(size, Image.Resampling.BILINEAR)
    return np.asarray(pil, dtype=np.uint8)


def compute_hog_32x32(gray_img: np.ndarray) -> np.ndarray:
    """Tính vector đặc trưng HOG (9 bins, cell 8x8, block 2x2, chuẩn hóa L2-Hys → 324 chiều).

    Viết thuần NumPy để đảm bảo kết quả giống hệt nhau giữa mọi phiên bản OpenCV/Colab/Windows.
    """
    img = gray_img.astype(np.float32) / 255.0
    h, w = img.shape[:2]

    gx = np.zeros_like(img)
    gy = np.zeros_like(img)
    gx[:, 1:-1] = img[:, 2:] - img[:, :-2]
    gy[1:-1, :] = img[2:, :] - img[:-2, :]

    magnitude = np.hypot(gx, gy)
    orientation = (np.degrees(np.arctan2(gy, gx)) % 180.0)

    n_cells_y = h // HOG_CELL_SIZE
    n_cells_x = w // HOG_CELL_SIZE
    bin_width = 180.0 / HOG_NBINS

    cell_hist = np.zeros((n_cells_y, n_cells_x, HOG_NBINS), dtype=np.float32)
    for cy in range(n_cells_y):
        y0, y1 = cy * HOG_CELL_SIZE, (cy + 1) * HOG_CELL_SIZE
        for cx in range(n_cells_x):
            x0, x1 = cx * HOG_CELL_SIZE, (cx + 1) * HOG_CELL_SIZE
            mag_cell = magnitude[y0:y1, x0:x1].ravel()
            ang_cell = orientation[y0:y1, x0:x1].ravel()
            bin_f = ang_cell / bin_width
            b0 = np.floor(bin_f).astype(np.int32) % HOG_NBINS
            b1 = (b0 + 1) % HOG_NBINS
            w1 = bin_f - np.floor(bin_f)
            w0 = 1.0 - w1
            np.add.at(cell_hist[cy, cx], b0, mag_cell * w0)
            np.add.at(cell_hist[cy, cx], b1, mag_cell * w1)

    eps = 1e-5
    blocks = []
    for by in range(n_cells_y - HOG_BLOCK_CELLS + 1):
        for bx in range(n_cells_x - HOG_BLOCK_CELLS + 1):
            block = cell_hist[
                by : by + HOG_BLOCK_CELLS,
                bx : bx + HOG_BLOCK_CELLS,
                :,
            ].ravel()
            # L2-Hys normalization
            norm = np.sqrt(np.sum(block * block) + eps * eps)
            block = np.minimum(block / norm, 0.2)
            norm2 = np.sqrt(np.sum(block * block) + eps * eps)
            blocks.append(block / norm2)

    if not blocks:
        return np.zeros(324, dtype=np.float32)
    return np.concatenate(blocks).astype(np.float32)


def extract_char_hog_features(
    crop: np.ndarray,
    size: Tuple[int, int] = CHAR_IMAGE_SIZE,
) -> np.ndarray:
    """Trích xuất vector đặc trưng HOG 1D (324 chiều với ảnh 32x32) cho 1 ký tự."""
    normalized = preprocess_char_crop(crop, size=size)
    return compute_hog_32x32(normalized)
