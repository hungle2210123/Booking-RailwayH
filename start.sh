#!/usr/bin/env bash
# Railway start script for hotel booking system

echo "🚀 Starting Railway Hotel Booking System..."
echo "Environment: $FLASK_ENV"
echo "Port: $PORT"
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

# Check if gunicorn is installed
if command -v gunicorn &> /dev/null; then
    echo "✅ Gunicorn found"
    exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
elif python -m gunicorn --version &> /dev/null; then
    echo "✅ Gunicorn found via python -m"
    exec python -m gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
else
    echo "❌ Gunicorn not found, installing..."
    pip install gunicorn==21.2.0
    echo "✅ Gunicorn installed, starting server..."
    exec python -m gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
fi