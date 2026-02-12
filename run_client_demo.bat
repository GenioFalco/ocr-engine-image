@echo off
if not exist "venv" (
    echo [ERROR] Virtual environment not found. Please run 'setup_local.bat' first.
    pause
    exit /b 1
)

echo [INFO] Running Client Demo Script...
call venv\Scripts\activate.bat
python client_demo.py
pause
