@echo off
echo --- Industrial OCR Engine Local Setup ---

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.11+ and add to PATH.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create Virtual Environment
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
) else (
    echo [INFO] Virtual environment already exists.
)

:: Activate Venv and Install Requirements
echo [INFO] Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt

:: Check for .env file
if not exist ".env" (
    echo [INFO] Creating .env file from .env.example...
    copy .env.example .env
    echo [WARNING] Please edit .env file and add your GIGACHAT_CREDENTIALS!
)

echo.
echo [SUCCESS] Setup complete!
echo now run 'run_local.bat' to start the server.
pause
