"""Bộ phân loại biển số xe Việt Nam đa tiêu chí (License Plate Classification).

Phân loại biển số theo:
1. Địa phương đăng ký (Tỉnh / Thành phố / Khu vực Bắc - Trung - Nam).
2. Nhóm phương tiện & Đối tượng cấp biển (Xe máy cá nhân, Ô tô con, Ô tô kinh doanh vận tải, Cơ quan nhà nước, Quân đội, Ngoại giao).
3. Màu sắc biển số (Biển trắng dân sự, Biển vàng kinh doanh, Biển xanh công quyền, Biển đỏ quân đội).
4. Định dạng bố cục biển (Biển 1 dòng chữ nhật dài vs Biển 2 dòng vuông).
5. Đặc điểm phong thủy (Ngũ quý, Tứ quý, Sảnh tiến, Thần tài, Lộc phát...).
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np

# Bảng tra cứu mã 63 tỉnh thành Việt Nam + Cơ quan TW (Thông tư 24/2023/TT-BCA)
PROVINCE_MAP: Dict[str, Tuple[str, str]] = {
    "11": ("Cao Bằng", "Miền Bắc"),
    "12": ("Lạng Sơn", "Miền Bắc"),
    "14": ("Quảng Ninh", "Miền Bắc"),
    "15": ("Hải Phòng", "Miền Bắc"),
    "16": ("Hải Phòng", "Miền Bắc"),
    "17": ("Thái Bình", "Miền Bắc"),
    "18": ("Nam Định", "Miền Bắc"),
    "19": ("Phú Thọ", "Miền Bắc"),
    "20": ("Thái Nguyên", "Miền Bắc"),
    "21": ("Yên Bái", "Miền Bắc"),
    "22": ("Tuyên Quang", "Miền Bắc"),
    "23": ("Hà Giang", "Miền Bắc"),
    "24": ("Lào Cai", "Miền Bắc"),
    "25": ("Lai Châu", "Miền Bắc"),
    "26": ("Sơn La", "Miền Bắc"),
    "27": ("Điện Biên", "Miền Bắc"),
    "28": ("Hòa Bình", "Miền Bắc"),
    "29": ("Hà Nội", "Miền Bắc"),
    "30": ("Hà Nội", "Miền Bắc"),
    "31": ("Hà Nội", "Miền Bắc"),
    "32": ("Hà Nội", "Miền Bắc"),
    "33": ("Hà Nội", "Miền Bắc"),
    "40": ("Hà Nội", "Miền Bắc"),
    "34": ("Hải Dương", "Miền Bắc"),
    "35": ("Ninh Bình", "Miền Bắc"),
    "36": ("Thanh Hóa", "Miền Trung"),
    "37": ("Nghệ An", "Miền Trung"),
    "38": ("Hà Tĩnh", "Miền Trung"),
    "43": ("Đà Nẵng", "Miền Trung"),
    "47": ("Đắk Lắk", "Tây Nguyên"),
    "48": ("Đắk Nông", "Tây Nguyên"),
    "49": ("Lâm Đồng", "Tây Nguyên"),
    "50": ("TP. Hồ Chí Minh", "Miền Nam"),
    "51": ("TP. Hồ Chí Minh", "Miền Nam"),
    "52": ("TP. Hồ Chí Minh", "Miền Nam"),
    "53": ("TP. Hồ Chí Minh", "Miền Nam"),
    "54": ("TP. Hồ Chí Minh", "Miền Nam"),
    "55": ("TP. Hồ Chí Minh", "Miền Nam"),
    "56": ("TP. Hồ Chí Minh", "Miền Nam"),
    "57": ("TP. Hồ Chí Minh", "Miền Nam"),
    "58": ("TP. Hồ Chí Minh", "Miền Nam"),
    "59": ("TP. Hồ Chí Minh", "Miền Nam"),
    "60": ("Đồng Nai", "Miền Nam"),
    "61": ("Bình Dương", "Miền Nam"),
    "62": ("Long An", "Miền Nam"),
    "63": ("Tiền Giang", "Miền Nam"),
    "64": ("Vĩnh Long", "Miền Nam"),
    "65": ("Cần Thơ", "Miền Nam"),
    "66": ("Đồng Tháp", "Miền Nam"),
    "67": ("An Giang", "Miền Nam"),
    "68": ("Kiên Giang", "Miền Nam"),
    "69": ("Cà Mau", "Miền Nam"),
    "70": ("Tây Ninh", "Miền Nam"),
    "71": ("Bến Tre", "Miền Nam"),
    "72": ("Bà Rịa - Vũng Tàu", "Miền Nam"),
    "73": ("Quảng Bình", "Miền Trung"),
    "74": ("Quảng Trị", "Miền Trung"),
    "75": ("Thừa Thiên Huế", "Miền Trung"),
    "76": ("Quảng Ngãi", "Miền Trung"),
    "77": ("Bình Định", "Miền Trung"),
    "78": ("Phú Yên", "Miền Trung"),
    "79": ("Khánh Hòa", "Miền Trung"),
    "80": ("Cục CSGT / Cơ quan Trung ương", "Toàn quốc"),
    "81": ("Gia Lai", "Tây Nguyên"),
    "82": ("Kon Tum", "Tây Nguyên"),
    "83": ("Sóc Trăng", "Miền Nam"),
    "84": ("Trà Vinh", "Miền Nam"),
    "85": ("Ninh Thuận", "Miền Trung"),
    "86": ("Bình Thuận", "Miền Trung"),
    "88": ("Vĩnh Phúc", "Miền Bắc"),
    "89": ("Hưng Yên", "Miền Bắc"),
    "90": ("Hà Nam", "Miền Bắc"),
    "92": ("Quảng Nam", "Miền Trung"),
    "93": ("Bình Phước", "Miền Nam"),
    "94": ("Bạc Liêu", "Miền Nam"),
    "95": ("Hậu Giang", "Miền Nam"),
    "97": ("Bắc Kạn", "Miền Bắc"),
    "98": ("Bắc Giang", "Miền Bắc"),
    "99": ("Bắc Ninh", "Miền Bắc"),
}

# Ký hiệu viết tắt quân đội (Biển đỏ)
MILITARY_PREFIXES: Dict[str, str] = {
    "QP": "Bộ Quốc phòng",
    "TC": "Tổng cục Chính trị",
    "TH": "Tổng cục Hậu cần",
    "TK": "Tổng cục CN Quốc phòng",
    "TT": "Tổng cục Kỹ thuật",
    "TM": "Bộ Tổng Tham mưu",
    "QA": "Quân chủng PK - KQ",
    "QC": "Quân chủng Hải quân",
    "QB": "Bộ Tư lệnh Bộ đội Biên phòng",
    "QD": "Quân đoàn",
    "QH": "Học viện Quốc phòng",
    "VT": "Tập đoàn Viettel",
}


def detect_plate_color(crop_img: Optional[np.ndarray]) -> Tuple[str, str]:
    """Phân loại màu sắc của biển số dựa trên không gian màu HSV."""
    if crop_img is None or crop_img.size == 0:
        return "Trắng", "Biển dân sự tiêu chuẩn (Nền trắng, chữ đen)"

    try:
        hsv = cv2.cvtColor(crop_img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)

        # Bỏ qua viền ngoài (cắt 15% viền để lấy vùng nền trung tâm)
        h_crop = int(crop_img.shape[0] * 0.15)
        w_crop = int(crop_img.shape[1] * 0.15)
        if h_crop > 0 and w_crop > 0:
            h_roi = h[h_crop:-h_crop, w_crop:-w_crop]
            s_roi = s[h_crop:-h_crop, w_crop:-w_crop]
            v_roi = v[h_crop:-h_crop, w_crop:-w_crop]
        else:
            h_roi, s_roi, v_roi = h, s, v

        # Biển đỏ
        red_mask1 = cv2.inRange(hsv, (0, 70, 50), (10, 255, 255))
        red_mask2 = cv2.inRange(hsv, (170, 70, 50), (180, 255, 255))
        red_ratio = (np.count_nonzero(red_mask1) + np.count_nonzero(red_mask2)) / (crop_img.shape[0] * crop_img.shape[1])
        if red_ratio > 0.35:
            return "Đỏ", "Biển quân sự (Nền đỏ, chữ trắng)"

        # Biển xanh dương
        blue_mask = cv2.inRange(hsv, (95, 60, 50), (135, 255, 255))
        blue_ratio = np.count_nonzero(blue_mask) / (crop_img.shape[0] * crop_img.shape[1])
        if blue_ratio > 0.35:
            return "Xanh", "Biển cơ quan nhà nước / Công quyền (Nền xanh, chữ trắng)"

        # Biển vàng
        yellow_mask = cv2.inRange(hsv, (15, 60, 60), (38, 255, 255))
        yellow_ratio = np.count_nonzero(yellow_mask) / (crop_img.shape[0] * crop_img.shape[1])
        if yellow_ratio > 0.30:
            return "Vàng", "Biển kinh doanh vận tải (Nền vàng, chữ đen)"

        # Biển trắng (Độ bão hòa thấp, độ sáng cao)
        return "Trắng", "Biển dân sự tiêu chuẩn (Nền trắng, chữ đen)"
    except Exception:
        return "Trắng", "Biển dân sự tiêu chuẩn (Nền trắng, chữ đen)"


def check_lucky_plate(digits: str) -> str:
    """Phân loại biển số đẹp / phong thủy."""
    if not digits or len(digits) < 4:
        return "Tiêu chuẩn"

    # Ngũ quý (5 số giống nhau liên tiếp)
    if len(digits) == 5 and len(set(digits)) == 1:
        return f"Ngũ quý {digits[0]} (Siêu phẩm độc bản)"

    # Tứ quý
    if len(digits) >= 4:
        last4 = digits[-4:]
        if len(set(last4)) == 1:
            return f"Tứ quý {last4[0]} (Đại cát phát tài)"

    # Tam hoa (3 số cuối giống nhau)
    if len(digits) >= 3:
        last3 = digits[-3:]
        if len(set(last3)) == 1:
            return f"Tam hoa {last3[0]}"

    # Sảnh tiến (dãy số tiến đều: 1234, 2345, 6789, 234.56...)
    is_step = True
    for i in range(len(digits) - 1):
        if int(digits[i + 1]) != int(digits[i]) + 1:
            is_step = False
            break
    if is_step and len(digits) >= 4:
        return "Sảnh tiến (Thăng quan tiến chức)"

    # Lộc phát (đuôi 68, 86, 6868, 8686)
    if digits.endswith("68") or digits.endswith("86"):
        return "Lộc phát (68 / 86)"

    # Thần tài (đuôi 39 hoặc 79)
    if digits.endswith("39") or digits.endswith("79"):
        return "Thần tài (39 / 79)"

    # Cặp số gánh / đảo (ví dụ: 1221, 2332)
    if len(digits) == 4 and digits[0] == digits[3] and digits[1] == digits[2]:
        return "Số gánh đối xứng"

    return "Tiêu chuẩn"


def classify_license_plate(
    plate: str,
    crop_img: Optional[np.ndarray] = None,
    bbox: Optional[list] = None,
) -> Dict[str, Any]:
    """Phân loại biển số xe đa tiêu chí toàn diện."""
    clean_plate = re.sub(r"[^A-Z0-9]", "", (plate or "").upper())

    if not clean_plate:
        return {
            "valid": False,
            "plate": plate,
            "province_code": "",
            "province_name": "Chưa xác định",
            "region": "Chưa xác định",
            "vehicle_category": "Chưa xác định",
            "series": "",
            "color_name": "Chưa xác định",
            "color_desc": "",
            "layout": "Chưa xác định",
            "lucky_tag": "Tiêu chuẩn",
            "classification_summary": "Không nhận diện được biển số",
        }

    # 1. Kiểm tra biển Quân đội (bắt đầu bằng 2 chữ cái quân chủng)
    first2 = clean_plate[:2]
    if first2 in MILITARY_PREFIXES:
        color_name, color_desc = ("Đỏ", "Biển quân đội (Nền đỏ, chữ trắng)")
        return {
            "valid": True,
            "plate": clean_plate,
            "province_code": first2,
            "province_name": f"Quân đội nhân dân Việt Nam ({MILITARY_PREFIXES[first2]})",
            "region": "Toàn quốc",
            "vehicle_category": "Phương tiện Quân sự / Quốc phòng",
            "series": first2,
            "color_name": color_name,
            "color_desc": color_desc,
            "layout": "Biển quân sự",
            "lucky_tag": "Đặc chủng",
            "classification_summary": f"Quân đội · {MILITARY_PREFIXES[first2]} · Biển đỏ",
        }

    # 2. Phân loại theo Tỉnh / Thành phố
    province_code = clean_plate[:2]
    province_info = PROVINCE_MAP.get(province_code, ("Chưa rõ địa phương", "Toàn quốc"))
    province_name, region = province_info

    # 3. Phân tích Series và Nhóm phương tiện
    remaining = clean_plate[2:]
    
    # TH1: Ô tô có 1 hoặc 2 chữ cái + 4 hoặc 5 số (VD: 30A-88888, 51F-12345, 51LD-1234)
    # TH2: Xe máy có 1 chữ cái + 1 số + 4 hoặc 5 số (VD: 59-S2 12345, 29-B1 56789)
    match_car_single = re.match(r"^([A-Z])([0-9]{4,5})$", remaining)
    match_car_double = re.match(r"^([A-Z]{2})([0-9]{4,5})$", remaining)
    match_moto = re.match(r"^([A-Z][0-9])([0-9]{4,5})$", remaining)

    vehicle_category = "Phương tiện cơ giới"
    series = ""
    digits = ""
    layout = "Biển 1 dòng chữ nhật (520x110mm)"

    if match_car_single:
        # Ô tô dân sự biển 1 chữ cái (30A, 51F, 43C...)
        series = match_car_single.group(1)
        digits = match_car_single.group(2)
        if series in ("A", "F", "K", "G"):
            vehicle_category = "Ô tô con / Xe du lịch"
        elif series == "B":
            vehicle_category = "Ô tô khách / Xe chở người"
        elif series in ("C", "H"):
            vehicle_category = "Ô tô tải / Xe chuyên dùng"
        elif series == "D":
            vehicle_category = "Ô tô bán tải (Van / Pickup)"
        elif series == "E":
            vehicle_category = "Ô tô dịch vụ / Vận tải"
        else:
            vehicle_category = f"Ô tô con (Seri {series})"
        layout = "Biển ô tô 1 dòng dài (520x110mm)"
    elif match_car_double:
        # Ô tô liên doanh, xe cơ quan (LD, DA, NN, NG, CV)
        series = match_car_double.group(1)
        digits = match_car_double.group(2)
        if series == "LD":
            vehicle_category = "Ô tô doanh nghiệp Liên doanh"
        elif series in ("NN", "NG", "QT", "CV"):
            vehicle_category = "Ô tô Ngoại giao / Quốc tế"
        else:
            vehicle_category = f"Ô tô chuyên dụng (Seri {series})"
        layout = "Biển ô tô 1 dòng dài (520x110mm)"
    elif match_moto:
        # Xe máy (59-S2, 29-B1...)
        series = match_moto.group(1)
        digits = match_moto.group(2)
        vehicle_category = "Xe mô tô / Xe máy"
        layout = "Biển xe máy 2 dòng vuông (330x165mm)"
    else:
        # Fallback
        letters = re.findall(r"[A-Z]+", remaining)
        num_parts = re.findall(r"\d+", remaining)
        series = "".join(letters)
        digits = "".join(num_parts)
        if len(series) == 1:
            vehicle_category = "Ô tô con / Xe cơ giới"
            layout = "Biển ô tô 1 dòng dài"
        else:
            vehicle_category = "Xe mô tô / Xe máy"
            layout = "Biển xe máy 2 dòng vuông"

    # 4. Phân loại màu sắc
    color_name, color_desc = detect_plate_color(crop_img)

    # Nếu mã tỉnh là 80 thì là cơ quan Trung ương
    if province_code == "80":
        vehicle_category = "Cơ quan Nhà nước / Trung ương"
        if color_name == "Trắng":
            color_name = "Xanh"
            color_desc = "Biển cơ quan nhà nước (Nền xanh, chữ trắng)"

    # Nếu phát hiện nền vàng thì phân loại xe kinh doanh vận tải
    if color_name == "Vàng":
        vehicle_category = f"{vehicle_category} (Kinh doanh vận tải)"

    # 5. Phân loại biển đẹp phong thủy
    lucky_tag = check_lucky_plate(digits)

    # Tóm tắt phân loại ngắn gọn
    summary = f"{province_name} · {vehicle_category} · Biển {color_name}"
    if lucky_tag != "Tiêu chuẩn":
        summary += f" · {lucky_tag}"

    return {
        "valid": True,
        "plate": clean_plate,
        "province_code": province_code,
        "province_name": province_name,
        "region": region,
        "vehicle_category": vehicle_category,
        "series": series,
        "color_name": color_name,
        "color_desc": color_desc,
        "layout": layout,
        "digits": digits,
        "lucky_tag": lucky_tag,
        "classification_summary": summary,
    }
