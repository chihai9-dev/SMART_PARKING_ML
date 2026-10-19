@echo off
setlocal
cd /d "%~dp0"

echo ======================================================================
echo    KHOI DONG HE THONG NHAN DIEN BIEN SO XE - ALPR SYSTEM
echo ======================================================================
echo.

echo [1/3] Khoi chay Python AI Service (Port 5000)...
start "ALPR - Python AI (Port 5000)" cmd /k "cd /d "%~dp0" && .\venv\Scripts\python.exe app\app.py"

timeout /t 3 /nobreak > nul

echo [2/3] Khoi chay Backend Web API (Port 5049)...
start "ALPR - Backend API (Port 5049)" cmd /k "cd /d "%~dp0" && dotnet run --project Backend\src\Smartparking.Api"

timeout /t 3 /nobreak > nul

echo [3/3] Khoi chay React Frontend (Port 5173)...
start "ALPR - Frontend (Port 5173)" cmd /k "cd /d "%~dp0\frontend" && npm run dev"

echo.
echo ======================================================================
echo    He thong ALPR dang duoc khoi chay:
echo    - Frontend Web:   http://localhost:5173
echo    - Backend API:    http://localhost:5049/swagger
echo    - Python AI API:  http://127.0.0.1:5000
echo ======================================================================
echo.
pause
