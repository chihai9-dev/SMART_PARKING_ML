@echo off
chcp 65001 > nul
echo ======================================================================
echo    KHỞI ĐỘNG HỆ THỐNG NHẬN DIỆN BIỂN SỐ XE (ALPR / ANPR SYSTEM)
echo ======================================================================
echo.
echo [1/3] Đang khởi chạy Python AI Service (YOLOv8 + RapidOCR trên Port 5000)...
start "ALPR - Python AI Service (Port 5000)" cmd /k ".\venv\Scripts\python.exe app\app.py"

timeout /t 3 /nobreak > nul

echo [2/3] Đang khởi chạy .NET Web API (ASP.NET Core trên Port 5049)...
start "ALPR - .NET Backend API (Port 5049)" cmd /k "dotnet run --project Backend\src\Smartparking.Api"

timeout /t 3 /nobreak > nul

echo [3/3] Đang khởi chạy React Frontend (Vite trên Port 5173)...
start "ALPR - React Frontend (Port 5173)" cmd /k "cd frontend && npm run dev"

echo.
echo ======================================================================
echo Hệ thống đang chạy!
echo - Giao diện Web:   http://localhost:5173
echo - .NET Web API:    http://localhost:5049/swagger
echo - Python AI API:   http://127.0.0.1:5000
echo ======================================================================
echo.
pause
