#!/bin/bash
# Railway is hardcoded to look for this exact file
# So we'll give it exactly what it wants
echo "🚀 Docker Entrypoint Starting..."
echo "PORT: $PORT"
echo "All Environment Variables:"
env | grep -E "(PORT|DATABASE)" || echo "No relevant env vars found"

# Start gunicorn with correct syntax
exec gunicorn app:app --bind 0.0.0.0:${PORT:-8080} --workers 1 --timeout 120