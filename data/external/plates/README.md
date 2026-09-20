# Ảnh biển số mẫu (synthetic)

Dùng để thử pipeline OCR và demo cổng vào/ra khi chưa có camera thật.

Sinh lại ảnh:

```bash
python src/vision/generate_plate_images.py
```

File PNG được đặt trong thư mục này. Trên trang `/parking` có thể upload một file để gọi `/api/scan-plate`.
