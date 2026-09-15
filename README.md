# Smart Parking ML

Dự án Machine Learning cho hệ thống bãi đỗ xe thông minh (Smart Parking System).

## Cấu trúc thư mục

- `data/` — dữ liệu thô, đã xử lý, và dữ liệu ngoài
- `notebooks/` — các notebook Jupyter cho từng giai đoạn (thu thập, làm sạch, EDA, mô hình hóa...)
- `src/` — mã nguồn Python (thu thập dữ liệu, feature engineering, huấn luyện mô hình, đánh giá)
- `models/` — các mô hình đã huấn luyện (pickle)
- `outputs/` — biểu đồ và kết quả xuất ra
- `app/` — ứng dụng web (Flask) demo hệ thống
- `database/` — cơ sở dữ liệu SQLite
- `docs/` — báo cáo, slide thuyết trình, sơ đồ, tài liệu tham khảo
- `tests/` — unit test

## Cài đặt

```bash
pip install -r requirements.txt
```

## Chạy ứng dụng

```bash
python app/app.py
```
