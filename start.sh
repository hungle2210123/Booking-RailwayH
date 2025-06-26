#!/usr/bin/env bash
# Render start script for hotel booking system

echo "🚀 Starting Hotel Booking System..."
echo "Environment: $FLASK_ENV"
echo "Port: $PORT"

# Start the application
exec gunicorn app_simple:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120