#!/bin/bash
set -e

echo "🚀 Railway Docker Entrypoint Starting..."
echo "Raw PORT value: '$PORT'"
echo "Environment variables:"
env | grep PORT || echo "No PORT environment variables found"

# Set default port if PORT is empty, null, or invalid
if [ -z "$PORT" ] || [ "$PORT" = "null" ] || [ "$PORT" = "" ]; then
    echo "⚠️ PORT is empty/null, setting to 5000"
    export PORT=5000
fi

# Validate PORT is numeric
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    echo "❌ PORT '$PORT' is not numeric, setting to 5000"
    export PORT=5000
fi

echo "✅ Using PORT: $PORT"
echo "Starting gunicorn on 0.0.0.0:$PORT"

# Start gunicorn with the validated PORT
exec python -m gunicorn app:app --bind "0.0.0.0:$PORT" --workers 1 --timeout 120