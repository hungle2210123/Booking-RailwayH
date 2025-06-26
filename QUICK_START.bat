@echo off
echo ============================================
echo Hotel Booking System - PostgreSQL Quick Start
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://python.org
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo Step 1: Creating environment file...
    copy ".env_postgresql.template" ".env"
    echo.
    echo IMPORTANT: Edit .env file with your PostgreSQL credentials!
    echo DATABASE_URL=postgresql://postgres:your_password@localhost:5432/hotel_booking
    echo.
    pause
)

REM Install dependencies
echo Step 2: Installing Python dependencies...
pip install -r requirements_postgresql.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    pause
    exit /b 1
)

echo.
echo Step 3: Testing database connection...
python test_postgresql_connection.py
if errorlevel 1 (
    echo.
    echo ERROR: Database connection failed!
    echo Please check:
    echo 1. PostgreSQL is running
    echo 2. Database 'hotel_booking' exists
    echo 3. Credentials in .env file are correct
    echo.
    echo Setup Guide: Open PGADMIN_SETUP_GUIDE.md
    pause
    exit /b 1
)

echo.
echo ============================================
echo SUCCESS! Database connection works!
echo ============================================
echo.
echo Starting Hotel Booking System...
echo Web interface will be available at: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start the application
python app_postgresql.py