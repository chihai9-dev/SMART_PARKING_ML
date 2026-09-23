# Camera nhận diện biển số trong Web Smart Parking

## Luồng hoạt động

```text
Chrome/Edge
   |
   | getUserMedia()
   v
Webcam máy tính
   |
   | Chụp 1 frame khi bấm nút
   v
JavaScript -> POST /api/scan-plate
   |
   v
Flask -> nhận ảnh
   |
   v
find_plate_regions()
   |
   v
RapidOCR / EasyOCR / Tesseract
   |
   v
normalize_plate()
   |
   v
SQLite + file scan + JSON kết quả
   |
   +--> điền biển số vào form VÀO/RA
```

## Chạy

```powershell
python -m pip install -r requirements.txt
python app/app.py
```

Mở trình duyệt tại:

```text
http://127.0.0.1:5000
```

Mở trang `/` bằng Chrome/Edge. Camera sẽ tự khởi động nếu trình duyệt đã cấp quyền; nếu chưa, bấm `Bật camera`. Khi một xe đứng ổn định trước camera, hệ thống tự nhận diện, tự cắt ảnh biển số, tự tạo mã vé và ghi vào SQLite.

Trang `/parking` là màn hình camera test độc lập trên web nhưng vẫn dùng chính API `/api/scan-plate`.

## Vì sao không OCR mọi frame?

Không chạy OCR liên tục trên từng frame vì OCR có thể nặng và làm trải nghiệm camera bị giật. Camera hiển thị video và tự gửi frame định kỳ; OCR chỉ chốt vé khi cùng một biển số hợp lệ xuất hiện ổn định qua nhiều frame.

## Quyền camera

Camera của trình duyệt cần được cấp quyền. `localhost` và `127.0.0.1` là các địa chỉ phù hợp để test cục bộ.
