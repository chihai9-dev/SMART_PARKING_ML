# Camera nhận diện biển số trong Web ALPR

## Luồng hoạt động

1. React Web xin quyền truy cập webcam qua getUserMedia().
2. React gửi frame định kỳ đến Python Flask bằng POST /api/preview-plate.
3. Python xử lý vùng biển số và OCR, sau đó trả JSON để React hiển thị.
4. Khi cùng một biển số hợp lệ ổn định qua 3 frame, React gửi ảnh đến POST /api/scan-plate.
5. Flask xử lý ảnh và gọi .NET POST /api/PlateScans.
6. .NET dùng Dapper lưu kết quả vào SQL Server, bảng PlateScans.

## Hai chế độ nhận ảnh

- Camera trực tiếp: quét frame, hiển thị kết quả tạm thời, sau đó lưu lượt quét khi biển số ổn định.
- Tải ảnh: người dùng chọn ảnh JPG, PNG hoặc WEBP; Python nhận diện và lưu kết quả.

## Chạy

Khởi động Python AI Service, .NET Backend và React Frontend theo README.md.
Mở giao diện React tại http://localhost:5173 và cấp quyền camera cho trình duyệt.

Preview camera không ghi database ở từng frame. Chỉ lượt quét được chốt mới được lưu vào bảng PlateScans.
