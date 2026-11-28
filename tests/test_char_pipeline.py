"""Kiểm thử pipeline cắt ký tự YOLO + HOG & SVM + ghép biển số VN."""

from __future__ import annotations

import numpy as np

from src.features.char_hog import CHAR_IMAGE_SIZE, extract_char_hog_features, preprocess_char_crop
from src.vision.char_pipeline import (
    CharDetection,
    decode_plate_with_constraints,
    deduplicate_char_boxes,
    sort_characters_vn_plate,
)


def _dummy_det(cx: float, cy: float, w: float = 20.0, h: float = 40.0, conf: float = 0.9) -> CharDetection:
    x = int(cx - w / 2)
    y = int(cy - h / 2)
    crop = np.full((int(h), int(w), 3), 220, dtype=np.uint8)
    return CharDetection(bbox=[x, y, int(w), int(h)], cx=cx, cy=cy, w=w, h=h, det_conf=conf, crop=crop)


def test_hog_preserves_shape_and_returns_324_dims():
    # Ký tự mảnh như số '1' (12x44) vẫn được pad vuông và trả đúng 324 đặc trưng HOG
    thin_char = np.full((44, 12, 3), 240, dtype=np.uint8)
    thin_char[6:38, 4:8] = 20
    norm = preprocess_char_crop(thin_char, size=CHAR_IMAGE_SIZE)
    assert norm.shape == (32, 32)
    feat = extract_char_hog_features(thin_char, size=CHAR_IMAGE_SIZE)
    assert feat.shape == (324,)
    assert np.isfinite(feat).all()


def test_sort_single_line_plate():
    # Biển ô tô 1 dòng (8 ký tự), đầu vào bị xáo trộn thứ tự
    xs = [30, 60, 90, 125, 155, 185, 215, 245]
    dets = [_dummy_det(x, 50 + (i % 2) * 2) for i, x in enumerate(xs)]
    shuffled = [dets[5], dets[0], dets[7], dets[2], dets[4], dets[1], dets[6], dets[3]]

    ordered, line_count = sort_characters_vn_plate(shuffled)
    assert line_count == 1
    assert [d.cx for d in ordered] == xs


def test_sort_two_line_tilted_vn_plate():
    # Biển xe máy 2 dòng hơi nghiêng: hàng trên 4 ký tự, hàng dưới 5 ký tự
    top = [_dummy_det(40, 32), _dummy_det(70, 35), _dummy_det(105, 38), _dummy_det(135, 41)]
    bot = [_dummy_det(25, 88), _dummy_det(55, 91), _dummy_det(85, 94), _dummy_det(115, 97), _dummy_det(145, 100)]
    mixed = [bot[2], top[3], bot[0], top[1], bot[4], top[0], bot[1], top[2], bot[3]]

    ordered, line_count = sort_characters_vn_plate(mixed)
    assert line_count == 2
    assert [d.cx for d in ordered] == [40, 70, 105, 135, 25, 55, 85, 115, 145]


def test_deduplicate_overlapping_char_boxes():
    d1 = _dummy_det(50, 50, 22, 40, conf=0.92)
    d2 = _dummy_det(52, 51, 22, 40, conf=0.71)  # trùng d1
    d3 = _dummy_det(90, 50, 22, 40, conf=0.88)
    kept = deduplicate_char_boxes([d2, d3, d1])
    assert len(kept) == 2
    assert {round(d.det_conf, 2) for d in kept} == {0.92, 0.88}


def test_constrained_decoding_fixes_province_and_series():
    classes = ["0", "1", "2", "3", "4", "5", "8", "9", "B", "F"]
    idx = {c: i for i, c in enumerate(classes)}

    # Chuỗi thực tế: 59F12345 (8 ký tự)
    # Cố tình cho vị trí 0 nhầm 'B' (0.55) > '5' (0.40) và vị trí 2 nhầm '8' (0.52) > 'F' (0.45)
    probs = np.full((8, len(classes)), 0.001, dtype=np.float64)
    probs[0, idx["B"]] = 0.55
    probs[0, idx["5"]] = 0.40
    probs[1, idx["9"]] = 0.90
    probs[2, idx["8"]] = 0.52
    probs[2, idx["F"]] = 0.45
    probs[3, idx["1"]] = 0.88
    probs[4, idx["2"]] = 0.91
    probs[5, idx["3"]] = 0.89
    probs[6, idx["4"]] = 0.92
    probs[7, idx["5"]] = 0.93

    plate, conf, details = decode_plate_with_constraints(probs, classes)
    assert plate == "59F12345"
    assert conf > 0.7
    assert details[0]["constrained"] is True
    assert details[0]["raw_char"] == "B"
    assert details[2]["constrained"] is True
    assert details[2]["raw_char"] == "8"
