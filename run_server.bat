@echo off
if not exist "venv" (
    echo [ERROR] Virtual environment not found. Please run 'setup_local.bat' first.
    pause
    exit /b 1
)

echo [INFO] Starting OCR Engine Server...
echo API Docs will be available at: http://127.0.0.1:8000/docs
call venv\Scripts\activate.bat
set DATABASE_URL=sqlite:///./sql_app.db
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
