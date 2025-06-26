#!/bin/bash
echo "========================================"
echo "Hotel Booking System - Setup Script"
echo "PostgreSQL Edition"
echo "========================================"

echo ""
echo "1. Copying environment template..."
cp .env.production .env
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to copy .env.production"
    exit 1
fi

echo ""
echo "2. Environment file created successfully!"
echo "Please edit .env file with your PostgreSQL credentials:"
echo "   - DATABASE_URL: Your PostgreSQL connection string"
echo "   - FLASK_SECRET_KEY: Change to a unique secret key"
echo "   - GOOGLE_API_KEY: Your Gemini AI API key (optional)"

echo ""
echo "3. Installing Python dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

echo ""
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your database credentials"
echo "2. Ensure PostgreSQL database is running"
echo "3. Run: python app.py"
echo "4. Access: http://localhost:8080"
echo ""