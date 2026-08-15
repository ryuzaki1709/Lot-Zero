# Lot Zero - Local Full Stack Launcher (FastAPI Backend + Vite Frontend)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$ApiDir = Join-Path $Root "apps\api"
$WebDir = Join-Path $Root "apps\web"
$PythonExe = Join-Path $ApiDir ".venv\Scripts\python.exe"
$NodeDir = "C:\Users\sujan reddy\AppData\Local\OpenAI\Codex\runtimes\cua_node\5b26acff135cec6b\bin"
$NpmCmd = Join-Path $NodeDir "npm.cmd"

$env:PATH = "$NodeDir;$env:PATH"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   LOT ZERO - Evidence-Backed Recall Incident Workspace   " -ForegroundColor Yellow
Write-Host "   Google All Things Agentic Hackathon · Devpost          " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "[1/2] Starting FastAPI Backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
Start-Process -FilePath $PythonExe -ArgumentList "-m uvicorn lot_zero.app:app --host 127.0.0.1 --port 8000" -WorkingDirectory $ApiDir

Start-Sleep -Seconds 2

Write-Host "[2/2] Starting Vite Frontend on http://localhost:5173..." -ForegroundColor Cyan
Start-Process -FilePath $NpmCmd -ArgumentList "run dev -- --host 127.0.0.1 --port 5173" -WorkingDirectory $WebDir

Start-Sleep -Seconds 3

Write-Host "Opening Incident War Room in your default browser..." -ForegroundColor Green
Start-Process "http://127.0.0.1:5173"

Write-Host "`nLot Zero is running! Press Ctrl+C in the launched windows when finished." -ForegroundColor Yellow
