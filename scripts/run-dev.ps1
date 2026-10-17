# Quick Start Script for Local Explorer AI Development
Write-Host "Khởi động Local Explorer AI Môi trường Phát triển..." -ForegroundColor Cyan

# 1. Start containers
Write-Host "1. Khởi động DB PostGIS & Redis..." -ForegroundColor Green
docker compose up -d db redis

# 2. Instructions
Write-Host "Mở terminal riêng chạy Backend (apps/api):" -ForegroundColor Yellow
Write-Host "  cd apps/api; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000 --no-access-log --ws-max-size 65536"
Write-Host "Mở terminal riêng chạy Frontend (apps/web):" -ForegroundColor Yellow
Write-Host "  cd apps/web; npm run dev"
