#!/bin/bash

# Railway Startup Script for Hotel Booking System
echo "🚂 Starting Hotel Booking System on Railway..."

# Check if DATABASE_URL is set
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL not set. Please configure PostgreSQL in Railway dashboard."
    echo "   1. Go to Railway dashboard"
    echo "   2. Create PostgreSQL database"
    echo "   3. Add environment variable: DATABASE_URL = \${{Postgres.DATABASE_URL}}"
    exit 1
fi

echo "✅ DATABASE_URL configured: ${DATABASE_URL:0:30}..."

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
python -c "
import os
import time
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

database_url = os.getenv('DATABASE_URL')
if database_url:
    engine = create_engine(database_url)
    for i in range(30):  # Try for 30 seconds
        try:
            engine.execute('SELECT 1')
            print('✅ PostgreSQL is ready!')
            break
        except OperationalError:
            print(f'⏳ Waiting for PostgreSQL... ({i+1}/30)')
            time.sleep(1)
    else:
        print('❌ PostgreSQL not ready after 30 seconds')
        exit(1)
"

# Start the application
echo "🚀 Starting Flask application..."
exec gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --timeout 120 --access-logfile - --error-logfile -