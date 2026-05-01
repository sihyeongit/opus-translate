@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found: .venv\Scripts\python.exe
    echo Run the setup steps first, then try again.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m src.doctor
pause
