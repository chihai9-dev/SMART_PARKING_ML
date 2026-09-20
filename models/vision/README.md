# Mô hình thị giác (biển số)

Đặt trọng số detector/OCR tại đây khi nhóm train xong, ví dụ:

- `yolo_plate.pt` — phát hiện vùng biển
- `ocr_weights/` — backend EasyOCR / PaddleOCR

Code đọc ảnh nằm ở `src/vision/plate_ocr.py`. Ứng dụng Flask gọi qua `/api/scan-plate`, `/api/checkin`, `/api/checkout`.
