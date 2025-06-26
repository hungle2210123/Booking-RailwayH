#!/bin/bash

echo "============================================"
echo "Hotel Booking System - PostgreSQL Quick Start"
echo "============================================"
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "ERROR: Python is not installed"
        echo "Please install Python from https://python.org"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

echo "Using Python: $PYTHON_CMD"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Step 1: Creating environment file..."
    cp ".env_postgresql.template" ".env"
    echo
    echo "IMPORTANT: Edit .env file with your PostgreSQL credentials!"
    echo "DATABASE_URL=postgresql://postgres:your_password@localhost:5432/hotel_booking"
    echo
    read -p "Press Enter to continue after editing .env file..."
fi

# Install dependencies
echo "Step 2: Installing Python dependencies..."
$PYTHON_CMD -m pip install -r requirements_postgresql.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo
echo "Step 3: Testing database connection..."
$PYTHON_CMD test_postgresql_connection.py
if [ $? -ne 0 ]; then
    echo
    echo "ERROR: Database connection failed!"
    echo "Please check:"
    echo "1. PostgreSQL is running"
    echo "2. Database 'hotel_booking' exists"
    echo "3. Credentials in .env file are correct"
    echo
    echo "Setup Guide: Open PGADMIN_SETUP_GUIDE.md"
    exit 1
fi

echo
echo "============================================"
echo "SUCCESS! Database connection works!"
echo "============================================"
echo
echo "Starting Hotel Booking System..."
echo "Web interface will be available at: http://localhost:5000"
echo
echo "Press Ctrl+C to stop the server"
echo

# Start the application
$PYTHON_CMD app_postgresql.py