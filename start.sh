#!/usr/bin/env bash
# Railway start script for hotel booking system

echo "🚀 Starting Railway Hotel Booking System..."
echo "Environment: $FLASK_ENV"
echo "Port: $PORT"
echo "Python version: $(python --version)"
echo "Pip version: $(pip --version)"

# Check if gunicorn is installed
if command -v gunicorn &> /dev/null; then
    echo "✅ Gunicorn found in PATH"
    exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
elif python -m gunicorn --version &> /dev/null; then
    echo "✅ Gunicorn found via python -m"
    exec python -m gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
else
    echo "❌ Gunicorn not found, attempting installation..."
    # Try installation with fallback for managed environments
    if [[ -n "$RAILWAY_ENVIRONMENT_ID" ]] || [[ -n "$NIX_PATH" ]]; then
        echo "🔧 Managed environment detected - trying direct install"
        pip install gunicorn==21.2.0 || echo "⚠️ Install failed, trying Python module approach"
    else
        pip install gunicorn==21.2.0
    fi
    echo "✅ Starting server with Python module..."
    exec python -m gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120
fi