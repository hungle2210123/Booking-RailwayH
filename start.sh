#!/usr/bin/env bash
# Railway start script for hotel booking system

echo "🚀 Starting Railway Hotel Booking System..."
echo "Environment: $FLASK_ENV"
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

# Set default port if not provided
if [ -z "$PORT" ]; then
    export PORT=5000
    echo "⚠️ PORT not set, defaulting to 5000"
fi

echo "Port: $PORT"

# Validate PORT is a number
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "❌ Invalid PORT: $PORT, defaulting to 5000"
    export PORT=5000
fi

# Check if gunicorn is installed and start server
if command -v gunicorn &> /dev/null; then
    echo "✅ Gunicorn found in PATH"
    exec gunicorn app:app --bind "0.0.0.0:$PORT" --workers 1 --timeout 120
elif python -m gunicorn --version &> /dev/null; then
    echo "✅ Gunicorn found via python -m"
    exec python -m gunicorn app:app --bind "0.0.0.0:$PORT" --workers 1 --timeout 120
else
    echo "❌ Gunicorn not found, attempting installation..."
    pip install gunicorn==21.2.0
    echo "✅ Starting server with Python module..."
    exec python -m gunicorn app:app --bind "0.0.0.0:$PORT" --workers 1 --timeout 120
fi