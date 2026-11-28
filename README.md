# SmartParking — Nhận diện biển số xe (ALPR)

SmartParking là ứng dụng nhận diện ký tự biển số xe Việt Nam và phân loại màu nền biển số. Phạm vi phân loại màu hiện tại chỉ gồm **trắng** và **vàng**; biển xanh/đỏ được đánh dấu ngoài phạm vi thay vì gán nhầm sang một trong hai lớp.

## Chức năng chính

- Nhận diện từ ảnh tải lên hoặc webcam.
- Tìm vùng biển số, đọc và chuẩn hóa ký tự, kiểm tra định dạng biển số Việt Nam thông dụng.
- Phân loại nền biển trắng/vàng bằng Random Forest (RF) và K-Nearest Neighbors (KNN), đồng thời hiển thị kết quả để đối chiếu.
- Lưu và tra cứu lịch sử lượt nhận diện, ảnh biển số đã cắt và màu dự đoán trong SQL Server.
- Xem thống kê, xuất nhật ký CSV và kiểm tra API qua Swagger.

## Công nghệ

| Thành phần | Công nghệ | Nhiệm vụ |
|---|---|---|
| Giao diện | React 19, TypeScript, Vite, Tailwind CSS | Tải ảnh, webcam, kết quả, thống kê và nhật ký |
| Dịch vụ AI | Python, Flask, OpenCV, ONNX Runtime | Nhận ảnh, phát hiện biển số, OCR và phân loại màu |
| Phát hiện biển số | YOLOv8 ONNX (`models/vision/best.onnx`) | Đề xuất vùng biển số; bộ dò contour/heuristic là phương án dự phòng |
| OCR | RapidOCR; EasyOCR và Tesseract là phương án dự phòng khi được cài đặt | Đọc ký tự từ vùng biển số |
| Phân loại màu | scikit-learn, Random Forest, KNN, đặc trưng HSV | Dự đoán trắng/vàng từ ảnh biển số đã cắt |
| API nghiệp vụ | ASP.NET Core 10, Dapper, Swagger | Quản lý và truy vấn lượt nhận diện |
| Cơ sở dữ liệu | Microsoft SQL Server | Lưu bảng `PlateScans` |

## Kiến trúc và luồng hoạt động

```text
Trình duyệt (React)
  ├─ Ảnh tải lên hoặc khung hình webcam
  ▼
Vite proxy ──► Python Flask AI (cổng 5000)
                 1. Kiểm tra ảnh (tối đa 8 MB), giải mã bằng OpenCV
                 2. YOLOv8 tìm biển; dùng bộ dò dự phòng nếu cần
                 3. OCR nhiều biến thể ảnh → chuẩn hóa và kiểm tra biển số
                 4. Cắt ảnh biển → trích 10 đặc trưng HSV → RF và KNN
                 5. Trả ký tự, độ tin cậy, ảnh cắt/đánh dấu, màu và so sánh
                         │
                         └─ Kết quả hợp lệ ─► .NET Web API (cổng 5049)
                                                │ Dapper
                                                ▼
                                         SQL Server / PlateScans
```

### Chi tiết xử lý ảnh

1. **Nhận ảnh:** React gửi ảnh tải lên hoặc khung hình webcam dưới dạng multipart đến Flask thông qua Vite proxy. Webcam gửi các khung hình để xem trước; khi cùng biển số ổn định qua ba khung hình liên tiếp, giao diện gửi lượt quét để lưu.
2. **Kiểm tra và giải mã:** Flask yêu cầu ảnh hợp lệ, giới hạn kích thước tải lên 8 MB, sau đó giải mã thành ảnh BGR bằng OpenCV.
3. **Phát hiện biển:** Bộ nhận diện ưu tiên YOLOv8 ONNX. Nếu mô hình không sẵn sàng hoặc không tìm thấy vùng phù hợp, hệ thống sử dụng các phương pháp contour/heuristic và phương án dự phòng trên ảnh đầu vào.
4. **Đọc ký tự:** OCR chạy trên vùng biển và các biến thể tiền xử lý ảnh. RapidOCR được ưu tiên; EasyOCR/Tesseract chỉ dùng nếu môi trường có cài đặt. Văn bản được chuẩn hóa, hiệu chỉnh một số nhầm lẫn ký tự-số thường gặp và kiểm tra định dạng biển số Việt Nam. Kết quả OCR là dự đoán, cần kiểm tra lại nếu ảnh mờ hoặc biển bị che.
5. **Phân loại màu:** Hệ thống cắt vùng biển, loại viền, chuẩn hóa kích thước và trích 10 đặc trưng HSV. RF là kết quả chính; KNN được chạy để đối chiếu. Màu xanh/đỏ nổi trội được báo ngoài phạm vi. Độ tin cậy mô hình là xác suất dự đoán, không phải độ chính xác của toàn bộ hệ thống.
6. **Hiển thị và lưu:** Flask trả kết quả, ảnh gốc/ảnh cắt và báo cáo so sánh mô hình. Khi lưu lượt quét, dịch vụ AI gọi .NET API; API dùng Dapper ghi vào `PlateScans`. Giao diện tải nhật ký/thống kê từ .NET. Việc nhận diện thành công không đồng nghĩa chắc chắn lưu thành công; trường `database_saved` thể hiện riêng trạng thái lưu.

## Dữ liệu và mô hình màu

Ảnh gán nhãn có trong `data/labeled_plates/White/` và `data/labeled_plates/Yellow/`. Dataset nguồn là [Roboflow Universe — license-plate-color v4](https://universe.roboflow.com/nguyenluanai/license-plate-color), giấy phép được ghi là CC BY 4.0. Chỉ giữ nhãn `bien_trang` và `bien_vang`; ảnh xanh/không rõ bị loại. Có tổng cộng 1,502 ảnh gốc theo các split nguồn. Thông tin nguồn và ghi công nằm tại [`data/labeled_plates/README.md`](data/labeled_plates/README.md).

Huấn luyện lại từ thư mục gốc:

```powershell
python train_plate_color.py
```

Script huấn luyện RF và KNN, lưu model/metadata trong `models/classification/` và kết quả trong `outputs/results/`. KNN chuẩn hóa đặc trưng bằng `StandardScaler` và dùng 5 láng giềng. Dữ liệu giả lập nếu được dùng thì chỉ bổ sung cho huấn luyện, không được xem là bằng chứng hiệu năng ảnh camera thực. Khi có ảnh thật được giữ riêng, báo cáo đánh giá trên ảnh thật; nếu chỉ có dữ liệu tổng hợp, báo cáo ghi rõ điều đó.

Các báo cáo gồm Accuracy, Precision/Recall/Macro-F1, ma trận nhầm lẫn, độ trễ phân loại và đánh giá lặp theo nhóm biển số. Những lần chia lặp sử dụng cùng một dataset, có thể có tập kiểm thử chồng lấp và chỉ là thống kê mô tả. Độ trễ chỉ đo bước phân loại màu trên crop; không bao gồm phát hiện biển, OCR hoặc trích xuất đặc trưng, vì vậy không phải thời gian xử lý toàn ảnh.

Kết quả hiện có trong `outputs/results/algorithm_comparison.json` dựa trên tập ảnh thật giữ riêng: RF và KNN cùng Accuracy 99.66% trong lần đánh giá đơn; 10 lần group holdout cho RF Macro-F1 trung bình 99.796% (SD 0.310 điểm phần trăm), KNN 99.660% (SD 0.218 điểm phần trăm). KNN có thời gian phân loại trung bình thấp hơn trong benchmark đã lưu. Đây là kết quả trên dataset hiện tại, không bảo đảm hiệu năng với camera hoặc phiên chụp độc lập khác. Huấn luyện lại khi dịch vụ Python đang chạy thì cần khởi động lại dịch vụ để nạp model mới.

## Yêu cầu

- Windows 10/11 (các lệnh bên dưới dùng PowerShell).
- Python 3.10 trở lên, pip.
- Node.js 20.19+ (hoặc 22.12+) và npm.
- .NET 10 SDK.
- Microsoft SQL Server (LocalDB, Express hoặc máy chủ SQL có thể truy cập) và SQL Server Management Studio (SSMS) để khởi tạo database thuận tiện.

## Cài đặt lần đầu

Thực hiện tại thư mục gốc repository.

### 1. Cài thư viện Python

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu PowerShell chặn kích hoạt môi trường ảo, có thể chạy lệnh này trong cửa sổ PowerShell hiện tại rồi kích hoạt lại:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 2. Cài Frontend

```powershell
cd frontend
npm install
cd ..
```

### 3. Tạo database

Trong SSMS, kết nối đến SQL Server của bạn, mở và chạy `database/init_smartparking_sqlserver.sql`. Script tạo database `SmartParking`, bảng `dbo.PlateScans` và các cột màu cần thiết.

Backend mặc định kết nối `localhost\SQLEXPRESS` bằng Windows Authentication. Nếu cấu hình SQL Server của bạn khác, sửa connection string `DefaultConnection` trong `Backend/src/Smartparking.Api/appsettings.json`, hoặc ghi đè bằng biến môi trường .NET `ConnectionStrings__DefaultConnection`. Không đưa mật khẩu hoặc thông tin nhạy cảm vào Git.

Với database cũ chưa có cột màu, chạy `database/migrations/20261118_add_plate_color.sql`. Chỉ với database cũ có cột không còn dùng `VehicleType`, có thể chạy thêm `database/migrations/20261117_remove_vehicle_type.sql`. Không cần chạy migration này cho database mới.

### 4. Cấu hình Backend (nếu cần)

Python mặc định gọi Backend tại `http://127.0.0.1:5049`. Muốn dùng địa chỉ khác, đặt biến môi trường `SMARTPARKING_API_URL` trước khi chạy Python service, ví dụ:

```powershell
$env:SMARTPARKING_API_URL = "http://127.0.0.1:5049"
```

## Chạy ứng dụng

Mở **ba cửa sổ PowerShell** tại thư mục gốc repository và để cả ba dịch vụ chạy.

**Cửa sổ 1 — Python AI Service**

```powershell
.\venv\Scripts\Activate.ps1
python app\app.py
```

AI API mặc định chạy tại `http://127.0.0.1:5000`.

**Cửa sổ 2 — .NET Backend**

```powershell
dotnet run --project Backend\src\Smartparking.Api
```

Backend HTTP chạy tại `http://localhost:5049`; Swagger UI tại `http://localhost:5049/swagger`.
Trong Swagger UI, chọn **SmartParking Python AI Service** ở danh sách tài liệu để thử các endpoint Flask. Python service phải đang chạy ở cổng 5000. Swagger tải tài liệu và chuyển tiếp request Python qua Backend cùng origin, nên cũng hoạt động khi mở Swagger qua HTTPS mà không bị trình duyệt chặn mixed content/CORS.

**Cửa sổ 3 — Frontend**

```powershell
cd frontend
npm run dev
```

Mở địa chỉ Vite được in ra trong terminal, thường là `http://localhost:5173`. Trong giao diện, chọn **Tải ảnh nhận diện** để tải ảnh JPG/PNG/WEBP, hoặc chọn **Quét camera** và cấp quyền webcam. Kết quả lịch sử xuất hiện khi SQL Server và .NET Backend đã kết nối.

## API tham khảo

| Dịch vụ | Endpoint | Mô tả |
|---|---|---|
| Python | `POST /api/preview-plate` | Nhận diện thử khung hình webcam, không lưu lượt quét |
| Python | `POST /api/scan-plate` | Nhận diện ảnh, phân loại màu và thử gửi lượt quét tới Backend |
| Python | `POST /api/classify-plate-color` | Phân loại màu từ ảnh crop biển số |
| Python | `GET /api/model-info` | Xem metadata mô hình màu |
| Python | `GET /api/scans` | Lấy lịch sử scan tạm trong bộ nhớ của dịch vụ |
| Python | `GET /scan-image/{filename}` | Phục vụ ảnh scan đã lưu |
| .NET | `GET /api/PlateScans?search=...` | Lấy/tìm kiếm lịch sử |
| .NET | `GET /api/PlateScans/stats` | Lấy thống kê |
| .NET | `GET /api/PlateScans/{id}` | Lấy một lượt quét |
| .NET | `POST /api/PlateScans` | Tạo lượt quét |
| .NET | `DELETE /api/PlateScans/{id}` | Xóa lượt quét |

Frontend dùng Vite proxy: `/python-api/*` chuyển tới Flask và `/backend-api/*` chuyển tới .NET. Có thể gọi trực tiếp các URL trên cổng 5000 và 5049 khi kiểm thử dịch vụ riêng.
Flask cung cấp OpenAPI tại `http://localhost:5000/openapi.json`; Backend chuyển tài liệu này qua `/python-api/openapi.json` và chuyển tiếp các lệnh **Try it out** tới Flask. Khi chạy bằng Docker Compose, địa chỉ nội bộ Python được cấu hình là `http://python-api:5000`; khi chạy PowerShell trên máy Windows, Backend mặc định dùng `http://127.0.0.1:5000`.

## Kiểm thử và kiểm tra chất lượng

Từ thư mục gốc:

```powershell
python -m pytest
```

Build và lint giao diện:

```powershell
cd frontend
npm run build
npm run lint
```

Build Backend:

```powershell
dotnet build Backend\SmartParking.slnx
```

Để kiểm tra thủ công toàn hệ thống: khởi chạy đủ ba dịch vụ, tải một ảnh biển số rõ nét, kiểm tra ký tự/màu/ảnh crop, rồi mở nhật ký và xác nhận bản ghi trong SQL Server. Thử riêng webcam, ảnh không hợp lệ và tình huống Backend/database chưa chạy.

## Giới hạn và xử lý sự cố

- Kết quả phụ thuộc chất lượng ảnh, góc chụp, ánh sáng, độ phân giải và khả năng mô hình phát hiện/OCR; luôn xác nhận biển số trước khi dùng nghiệp vụ.
- Bộ phân loại màu chỉ hỗ trợ nền trắng/vàng; nhãn ngoài phạm vi hoặc ảnh crop kém có thể không phân loại được chính xác.
- Mô hình màu không thay thế đánh giá toàn luồng ALPR. Các metric màu không đo độ chính xác phát hiện biển/OCR.
- Frontend, Flask, Backend và SQL Server đều cần chạy để có đầy đủ trải nghiệm; nếu chỉ chạy Flask, kết quả nhận diện có thể có nhưng nhật ký database không cập nhật.
- Nếu không lưu được, kiểm tra SQL Server đang chạy, database/bảng đã khởi tạo và connection string; Swagger giúp kiểm tra riêng kết nối Backend.
- Nếu không có webcam hoặc trình duyệt không cấp quyền camera, vẫn có thể kiểm thử qua tải ảnh.

## Tài liệu khác

- [`docs/ML_LIFECYCLE.md`](docs/ML_LIFECYCLE.md): tổ chức dữ liệu, huấn luyện/đánh giá và vòng đời mô hình.
- [`data/labeled_plates/README.md`](data/labeled_plates/README.md): nguồn ảnh, nhãn và ghi công dataset.
