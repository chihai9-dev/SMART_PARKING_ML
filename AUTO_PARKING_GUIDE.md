# Smart Parking - Cổng tự động

Bản này chuyển camera từ kiểu **bấm chụp thủ công** sang kiểu **tự động nhận diện và tạo/cập nhật vé**.

## Luồng cổng vào

```text
Webcam trình duyệt
  -> tự chụp frame định kỳ
  -> OCR biển số
  -> cần 2 lần nhận diện giống nhau
  -> /api/gate-event (mode=entry)
  -> kiểm tra xe đã có vé mở chưa
  -> tạo ticket
  -> sinh mã vé SP-YYYYMMDD-xxxxxx
  -> lưu biển số + thời gian vào + ảnh toàn cảnh + ảnh crop biển số
  -> lưu SQLite
  -> trạng thái = open (Đang gửi)
```

## Luồng cổng ra

```text
Webcam trình duyệt
  -> tự chụp frame định kỳ
  -> OCR biển số
  -> cần 2 lần nhận diện giống nhau
  -> /api/gate-event (mode=exit)
  -> tìm ticket đang open theo biển số
  -> tính thời gian gửi / quá giờ
  -> lưu ảnh lúc ra
  -> cập nhật ticket
  -> trạng thái = closed (Đã trả xe) nếu khớp
```

## Database

Bảng `tickets` được mở rộng với:

- `ticket_code`: mã vé điện tử, ví dụ `SP-20260921-000001`
- `entry_image_path`: ảnh frame lúc xe vào
- `plate_image_path`: ảnh crop biển số lúc vào
- `exit_image_path`: ảnh frame lúc xe ra
- `exit_plate_image_path`: ảnh crop biển số lúc ra
- `status`: `open`, `closed`, hoặc `alert`

## Chạy

```powershell
python -m pip install -r requirements.txt
python app/app.py
```

Sau đó mở:

```text
http://127.0.0.1:5000
```

Chọn **CỔNG VÀO** hoặc **CỔNG RA**, bấm **Bật camera** một lần. Sau đó hệ thống tự quét.

Không cần chạy `camera_test.py` cho luồng hệ thống chính.
