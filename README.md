# SmartParking - ALPR

SmartParking hiện tập trung vào chức năng **nhận diện biển số xe tự động (ALPR)**. Hệ thống nhận ảnh từ camera trực tiếp hoặc file ảnh, đọc biển số và lưu lịch sử nhận diện vào SQL Server.

## 1. Chức năng

- Quét biển số trực tiếp bằng webcam.
- Tải ảnh lên để nhận diện biển số.
- Hiển thị kết quả nhận diện, độ tin cậy và ảnh biển số được cắt.
- Lưu lịch sử nhận diện vào SQL Server, bảng PlateScans.
- Tra cứu, lọc và xóa lượt nhận diện.
- Swagger UI để kiểm tra .NET Web API.

Hệ thống không còn chức năng tạo vé, check-in/check-out, trả xe, tính phí/phạt, lịch sử vé hoặc đăng nhập/JWT.

## 2. Kiến trúc

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS | Camera, tải ảnh, kết quả và lịch sử |
| AI Service | Python, Flask, mã nhận diện trong src/vision | Phát hiện vùng biển số và đọc ký tự |
| Backend | .NET 10, Dapper, Swagger | API quản lý lượt nhận diện |
| Database | Microsoft SQL Server | Lưu dữ liệu trong bảng PlateScans |

Luồng xử lý: React lấy ảnh từ camera hoặc file; Python xử lý OCR; .NET API nhận dữ liệu JSON; Dapper ghi kết quả vào SQL Server.

## 3. Chuẩn bị môi trường

Cần cài Python, .NET 10 SDK, Node.js/npm và SQL Server.

### Python

Mở PowerShell tại thư mục gốc dự án và chạy:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### SQL Server

Mở database/init_smartparking_sqlserver.sql trong SSMS và chạy để tạo database SmartParking cùng bảng PlateScans.

File SQL có lệnh xóa bảng dbo.Tickets cũ nếu bảng vẫn còn. Lệnh này sẽ xóa dữ liệu vé cũ trong bảng đó. Nó không xóa bảng PlateScans.

Kiểm tra chuỗi kết nối trong Backend/src/Smartparking.Api/appsettings.json. Giá trị hiện tại dùng SQL Server instance localhost\SQLEXPRESS04. Hãy đổi tên instance nếu máy bạn dùng tên khác.

## 4. Chạy hệ thống

Mở ba cửa sổ PowerShell tại thư mục gốc dự án.

**Terminal 1 - Python AI Service**

```powershell
.\venv\Scripts\Activate.ps1
python app/app.py
```

Python API chạy tại http://127.0.0.1:5000.

**Terminal 2 - .NET Backend**

```powershell
dotnet run --project Backend/src/Smartparking.Api
```

Swagger UI: http://localhost:5049/swagger.

**Terminal 3 - React Frontend**

```powershell
cd frontend
npm install
npm run dev
```

Mở địa chỉ Vite hiển thị trong terminal, mặc định thường là http://localhost:5173.

Có thể dùng run_alpr_system.bat hoặc run_alpr_system.ps1 để mở cả ba thành phần sau khi đã cài dependencies và tạo thư mục venv.

## 5. API chính

| Dịch vụ | Endpoint | Mục đích |
|---|---|---|
| Python | POST /api/preview-plate | Nhận diện thử frame camera, không ghi database |
| Python | POST /api/scan-plate | Nhận diện ảnh và gửi kết quả sang .NET để lưu |
| Python | GET /scan-image/{filename} | Xem ảnh nhận diện đã lưu |
| .NET | GET /api/PlateScans | Lấy lịch sử nhận diện |
| .NET | GET /api/PlateScans/stats | Lấy thống kê |
| .NET | POST /api/PlateScans | Lưu lượt nhận diện |
| .NET | DELETE /api/PlateScans/{id} | Xóa lượt nhận diện |

## 6. Kiểm tra

1. Chạy đủ Python, .NET Backend và React Frontend.
2. Mở http://localhost:5173 và cấp quyền dùng webcam.
3. Kiểm tra tab Quét Camera.
4. Thử chọn một ảnh ở tab Tải ảnh nhận diện.
5. Mở Nhật ký nhận diện để kiểm tra dữ liệu đã lưu.
6. Mở Swagger UI để kiểm tra các endpoint PlateScans.
