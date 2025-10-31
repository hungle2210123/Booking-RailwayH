#!/bin/bash
# Railway Startup Script - Run migrations then start app

echo "🚀 Railway Startup Script"
echo "========================="

# Check if apartments table exists
echo "📋 Checking if apartments table exists..."
python3 -c "
from sqlalchemy import create_engine, inspect
import os

database_url = os.getenv('DATABASE_URL', '')
if database_url:
    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if 'apartments' not in tables:
        print('⚠️  Apartments table not found - migration needed')
        exit(1)
    else:
        print('✅ Apartments table already exists')
        exit(0)
else:
    print('⚠️  DATABASE_URL not set')
    exit(1)
" 2>/dev/null

MIGRATION_NEEDED=$?

# Run migration if needed
if [ $MIGRATION_NEEDED -eq 1 ]; then
    echo "🔄 Running apartment migration..."
    python3 migrate_add_apartments.py

    if [ $? -eq 0 ]; then
        echo "✅ Migration completed successfully"
    else
        echo "⚠️  Migration failed or already run - continuing anyway"
    fi
else
    echo "✅ Migration not needed - apartments table exists"
fi

echo "🚀 Starting application..."
python3 run.py
