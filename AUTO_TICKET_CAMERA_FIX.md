# Auto Ticket + Camera Plate Recognition

## Luồng mới

1. Mở trang `/` bằng Chrome/Edge.
2. Camera tự khởi động nếu trình duyệt đã cấp quyền; có thể bấm `Bật camera` nếu chưa bật.
3. Hệ thống tự lấy frame từ webcam mỗi khoảng 1,2 giây.
4. Backend tìm vùng nghi là biển số, crop vùng biển số và chạy OCR.
5. Cùng một biển số phải được nhận diện ổn định 3 frame liên tiếp mới chốt sự kiện.
6. Khi chốt:
   - Cổng vào: tạo vé điện tử mới.
   - Cổng ra: tìm vé `open` theo biển số và cập nhật thành `closed` nếu khớp.
7. Vé lưu vào `database/parking.db`.
8. Ảnh toàn cảnh và ảnh crop biển số được lưu trong `data/processed/ticket_images/`.

## Dữ liệu chính trong bảng `tickets`

- `ticket_code`: mã vé tự sinh, ví dụ `SP-20260921-000001`
- `plate`: mã biển số
- `entry_time`: thời gian vào
- `entry_image_path`: ảnh toàn cảnh lúc vào
- `plate_image_path`: ảnh crop biển số
- `status`: `open` = đang gửi, `closed` = đã trả xe
- `exit_time`, `exit_image_path`, `exit_plate_image_path`: dữ liệu lúc ra

## Các phần đã sửa

- Camera tự khởi động và tự quét frame.
- Chống tạo vé trùng bằng cách kiểm tra vé `open` cùng biển số.
- Tăng ổn định nhận diện từ 2 lên 3 frame.
- Kết quả OCR/crop của frame preview ổn định được truyền sang bước tạo vé để tránh frame cuối bị rung làm OCR thất bại.
- Bộ tìm vùng biển số giữ thêm phương án OCR toàn ảnh khi contour biển số không rõ.
- OCR fallback có thêm nhiều kiểu tiền xử lý và PSM cho Tesseract.
- Chuẩn hóa biển số có xử lý một số lỗi nhầm O/0, I/1, S/5 ở đúng vùng ký tự.
- Bổ sung `pytesseract` vào `requirements.txt` làm fallback OCR.

## Chạy project

```bash
python -m pip install -r requirements.txt
python app/app.py
```

Mở:

```text
http://127.0.0.1:5000
```

Nếu camera không mở, cấp quyền Camera cho Chrome/Edge và bảo đảm webcam không đang bị ứng dụng khác sử dụng.
