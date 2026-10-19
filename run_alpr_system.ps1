Set-Location -Path $PSScriptRoot

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "   KHOI DONG HE THONG NHAN DIEN BIEN SO XE (ALPR / ANPR SYSTEM)     " -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/3] Khoi chay Python AI Service (Port 5000)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k cd /d `"$PSScriptRoot`" && .\venv\Scripts\python.exe app\app.py"

Start-Sleep -Seconds 3

Write-Host "[2/3] Khoi chay .NET Backend API (Port 5049)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k cd /d `"$PSScriptRoot`" && dotnet run --project Backend\src\Smartparking.Api"

Start-Sleep -Seconds 3

Write-Host "[3/3] Khoi chay React Frontend (Port 5173)..." -ForegroundColor Yellow
Start-Process cmd -ArgumentList "/k cd /d `"$PSScriptRoot\frontend`" && npm run dev"

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Green
Write-Host " He thong ALPR dang chay:" -ForegroundColor Green
Write-Host " - Giao dien Web:   http://localhost:5173" -ForegroundColor White
Write-Host " - Backend Swagger: http://localhost:5049/swagger" -ForegroundColor White
Write-Host " - Python AI API:   http://127.0.0.1:5000" -ForegroundColor White
Write-Host "======================================================================" -ForegroundColor Green
