# SmartParking - ALPR

SmartParking tập trung vào hai chức năng chính: **nhận diện ký tự biển số xe tự động (ALPR)** và **phân loại màu nền biển số**. Dự án không thực hiện phân loại phương tiện thành xe máy hoặc ô tô.

## 1. Chức năng

- Quét biển số trực tiếp bằng webcam hoặc tải ảnh lên.
- Phát hiện vùng biển số bằng YOLOv8 và đọc ký tự bằng RapidOCR.
- Phân loại biển số dân dụng màu trắng và vàng bằng Random Forest và KNN trên cùng 10 đặc trưng HSV. Biển xanh/đỏ ngoài phạm vi sẽ được trả về là không hỗ trợ.
- Hiển thị kết quả nhận diện, độ tin cậy và ảnh biển số được cắt.
- Lưu, tra cứu, lọc và xóa lịch sử nhận diện trong SQL Server.
- Swagger UI để kiểm tra .NET Web API.

## 2. Kiến trúc

| Thành phần | Công nghệ | Vai trò |
|---|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS | Camera, tải ảnh, kết quả và lịch sử |
| AI Service | Python, Flask, OpenCV, YOLOv8, RapidOCR, Random Forest, KNN | Phát hiện vùng biển số, đọc ký tự và phân loại màu nền |
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

Để cập nhật database hiện có cho lịch sử màu biển số, chạy `database/migrations/20261118_add_plate_color.sql`.

## 4. Huấn luyện mô hình phân loại màu biển số

Phạm vi đồ án là biển số màu trắng và vàng; không thu thập hoặc phân loại biển xanh/đỏ. Đặt ảnh biển số trắng/vàng đã gán nhãn vào các thư mục:

- `data/labeled_plates/White/`
- `data/labeled_plates/Yellow/`

Sau đó chạy:

```powershell
python train_plate_color.py
```

Hai mô hình được lưu tại `models/classification/plate_color_model.pkl` (Random Forest) và `models/classification/plate_color_knn_model.pkl` (KNN). KNN dùng StandardScaler được fit trên tập huấn luyện và 5 láng giềng gần nhất. Kết quả Accuracy, Precision macro, Recall macro, F1 macro, confusion matrix, confidence trung bình và độ trễ phân loại trên cùng tập kiểm thử được ghi vào `outputs/results/classification_results.csv` và `outputs/results/algorithm_comparison.json`. Khi bốn metric chất lượng bằng nhau, mô hình chỉ được chọn theo tốc độ nếu median latency nhanh hơn ít nhất 5%; confidence không dùng để quyết định mô hình thắng. Confidence hiện chưa được hiệu chuẩn, latency chỉ tính thời gian phân loại màu (không gồm phát hiện biển/OCR). Nếu có ảnh thật đã gán nhãn, ảnh thật được tách thành tập holdout riêng và chỉ dùng tập đó để so sánh; ảnh tổng hợp chỉ tham gia huấn luyện. Nếu chưa có ảnh thật, báo cáo ghi rõ chỉ đánh giá bằng ảnh tổng hợp và không đại diện cho hiệu năng camera. API trả kết quả Random Forest ở các trường hiện có và thêm dự đoán KNN trong `comparison`. Màn hình tải ảnh hiển thị hai bảng dự đoán cùng các metric, confidence, latency và confusion matrix. Ảnh có màu xanh/đỏ rõ rệt được đánh dấu ngoài phạm vi thay vì gán thành trắng/vàng.

Để so sánh độ biến động qua nhiều lần chia dữ liệu, mỗi lần chạy `train_plate_color.py` còn huấn luyện lại hai mô hình trên **10 lần group holdout**, mỗi lần giữ lại 20% nhóm biển số và giữ các ảnh cùng biển trong một nhóm. Trung bình và độ lệch chuẩn Accuracy, macro-F1 và latency được ghi ở `outputs/results/algorithm_comparison.json` và từng lượt ở `outputs/results/repeated_group_evaluation.csv`; giao diện cũng hiển thị bảng tóm tắt. Đây là các lần lặp trên cùng một dataset (các holdout có thể chồng lấp), nên dùng để mô tả độ ổn định chứ không phải các mẫu độc lập để khẳng định ý nghĩa thống kê hay hiệu năng camera.

Nếu huấn luyện lại trong khi Python AI Service đang chạy, hãy khởi động lại service để nạp các model artifact mới.

Lưu ý: nếu chưa có ảnh thật đã gán nhãn, chương trình có thể tạo dữ liệu tổng hợp để kiểm tra pipeline. Kết quả đánh giá trên dữ liệu tổng hợp không đại diện cho độ chính xác khi chạy camera thực tế.

Hướng dẫn tổ chức dữ liệu theo phiên chụp, chạy benchmark ALPR trên ảnh thật có nhãn, và các giới hạn đánh giá hiện tại nằm trong [docs/ML_LIFECYCLE.md](docs/ML_LIFECYCLE.md).

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
