#!/usr/bin/env bash
# Render start script for hotel booking system

echo "🚀 Starting Full Hotel Booking System..."
echo "Environment: $FLASK_ENV"
echo "Port: $PORT"

# Start the FULL application (not simple)
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120