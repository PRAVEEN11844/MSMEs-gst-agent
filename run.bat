@echo off
echo Starting MSME GST Agent Backend...
cd /d "%~dp0backend"
python -m uvicorn main:app --reload --port 8000
pause
