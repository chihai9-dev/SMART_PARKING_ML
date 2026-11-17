# SmartParking - ALPR

SmartParking tập trung vào hai chức năng chính: **nhận diện ký tự biển số xe tự động (ALPR)** và **phân loại màu nền biển số**. Dự án không thực hiện phân loại phương tiện thành xe máy hoặc ô tô.

## 1. Chức năng

- Quét biển số trực tiếp bằng webcam hoặc tải ảnh lên.
- Phát hiện vùng biển số bằng YOLOv8 và đọc ký tự bằng RapidOCR.
- Phân loại màu nền biển số bằng Random Forest trên 10 đặc trưng HSV: trắng, vàng, xanh và đỏ.
- Hiển thị kết quả nhận diện, độ tin cậy và ảnh biển số được cắt.
- Lưu, tra cứu, lọc và xóa lịch sử nhận diện trong SQL Server.
- Swagger UI để kiểm tra .NET Web API.

## 2. Kiến trúc

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS | Camera, tải ảnh, kết quả và lịch sử |
| AI Service | Python, Flask, OpenCV, YOLOv8, RapidOCR, Random Forest | Phát hiện vùng biển số, đọc ký tự và phân loại màu nền |
| Backend | .NET 10, Dapper, Swagger | API quản lý lượt nhận diện |
| Database | Microsoft SQL Server | Lưu lịch sử nhận diện trong bảng PlateScans |

Luồng xử lý: React lấy ảnh từ camera hoặc file; Python phát hiện vùng biển số, nhận dạng ký tự và phân loại màu nền từ ảnh biển số đã cắt; .NET API nhận thông tin lượt quét; Dapper ghi lịch sử vào SQL Server.

## 3. Chuẩn bị môi trường

Cần cài Python, .NET 10 SDK, Node.js/npm và SQL Server.

### Python

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### SQL Server

Mở `database/init_smartparking_sqlserver.sql` trong SSMS và chạy để tạo database SmartParking cùng bảng PlateScans.

Nếu database đã được tạo từ phiên bản cũ, chạy thêm một lần file `database/migrations/20261117_remove_vehicle_type.sql` để xóa cột VehicleType không còn sử dụng.

## 4. Huấn luyện mô hình phân loại màu biển số

Đặt ảnh biển số đã gán nhãn vào các thư mục:

- `data/labeled_plates/White/`
- `data/labeled_plates/Yellow/`
- `data/labeled_plates/Blue/`
- `data/labeled_plates/Red/`

Sau đó chạy:

```powershell
python train_plate_color.py
```

Mô hình được lưu tại `models/classification/best_classification_model.pkl`. Kết quả đánh giá và biểu đồ được lưu trong thư mục `outputs/`. Nếu có ảnh thật đã gán nhãn, ảnh thật được tách thành tập holdout riêng và chỉ dùng tập đó để báo cáo chất lượng; ảnh tổng hợp chỉ được dùng để huấn luyện. Nếu chưa có ảnh thật, metadata ghi rõ kết quả chỉ là đánh giá trên dữ liệu tổng hợp và không đại diện cho hiệu năng camera.

Lưu ý: nếu chưa có ảnh thật đã gán nhãn, chương trình có thể tạo dữ liệu tổng hợp để kiểm tra pipeline. Kết quả đánh giá trên dữ liệu tổng hợp không đại diện cho độ chính xác khi chạy camera thực tế.

## 5. Chạy hệ thống

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

## 6. API chính

| Dịch vụ | Endpoint | Mục đích |
|---|---|---|
| Python | POST /api/preview-plate | Nhận diện thử frame camera, không ghi database |
| Python | POST /api/scan-plate | Nhận diện biển số, phân loại màu và gửi lượt quét sang .NET |
| Python | POST /api/classify-plate-color | Phân loại màu từ ảnh vùng biển số |
| Python | GET /api/model-info | Xem metadata mô hình phân loại màu |
| Python | GET /scan-image/{filename} | Xem ảnh nhận diện đã lưu |
| .NET | GET /api/PlateScans | Lấy lịch sử nhận diện |
| .NET | GET /api/PlateScans/stats | Lấy thống kê lượt nhận diện |
| .NET | POST /api/PlateScans | Lưu lượt nhận diện |
| .NET | DELETE /api/PlateScans/{id} | Xóa lượt nhận diện |

## 7. Kiểm tra

1. Chạy đủ Python, .NET Backend và React Frontend.
2. Mở frontend và cấp quyền dùng webcam.
3. Kiểm tra tab Quét Camera.
4. Thử chọn một ảnh ở tab Tải ảnh nhận diện.
5. Kiểm tra kết quả biển số và màu nền được trả về.
6. Mở Nhật ký nhận diện để kiểm tra dữ liệu đã lưu.
7. Mở Swagger UI để kiểm tra các endpoint PlateScans.
