@echo off
echo ========================================
echo Starting Musya Agent Backend Server
echo ========================================
echo.
echo Agent logs will show:
echo - CrewAI agent execution steps
echo - Tool calls and results
echo - Agent reasoning process
echo - Final responses
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

cd /d "%~dp0"
call .venv\Scripts\activate.bat
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
