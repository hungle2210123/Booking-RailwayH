#\!/bin/bash
# Simple Railway start script
echo "🚀 Starting Railway Flask App..."
echo "PORT: $PORT"
exec gunicorn app:app --host 0.0.0.0 --port ${PORT:-8080}
