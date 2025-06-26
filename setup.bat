@echo off
echo ========================================
echo Hotel Booking System - Setup Script
echo PostgreSQL Edition
echo ========================================

echo.
echo 1. Copying environment template...
copy .env.production .env
if %errorlevel% neq 0 (
    echo ERROR: Failed to copy .env.production
    pause
    exit /b 1
)

echo.
echo 2. Environment file created successfully!
echo Please edit .env file with your PostgreSQL credentials:
echo    - DATABASE_URL: Your PostgreSQL connection string
echo    - FLASK_SECRET_KEY: Change to a unique secret key
echo    - GOOGLE_API_KEY: Your Gemini AI API key (optional)

echo.
echo 3. Installing Python dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Edit .env file with your database credentials
echo 2. Ensure PostgreSQL database is running
echo 3. Run: python app.py
echo 4. Access: http://localhost:8080
echo.
pause