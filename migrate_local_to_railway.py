#!/usr/bin/env python3
"""
CRITICAL DATA RECOVERY SCRIPT
Migrate all booking data from local PostgreSQL to Railway PostgreSQL

This script will:
1. Connect to local PostgreSQL (112 bookings)
2. Connect to Railway PostgreSQL (once service is added)
3. Copy ALL tables and data to Railway
4. Verify data integrity
"""

import os
import sys
from sqlalchemy import create_engine, text, MetaData, Table
from sqlalchemy.orm import sessionmaker
import pandas as pd

# Local PostgreSQL (source - has your 112 bookings)
LOCAL_DB = "postgresql://postgres:locloc123@localhost:5432/hotel_booking"

# Railway PostgreSQL (destination - will be provided after you add the service)
# You need to update this with the actual Railway DATABASE_URL after adding PostgreSQL service
# Default to the internal URL if available
RAILWAY_DB = os.getenv('RAILWAY_DATABASE_URL') or os.getenv('DATABASE_URL') or input("Enter Railway DATABASE_URL (from Railway dashboard): ")

# Note: If you're running this FROM Railway, use postgres.railway.internal
# If you're running this FROM your local machine, you'll need the public URL
print(f"\n🔍 Railway Database URL type:")
if 'railway.internal' in RAILWAY_DB:
    print("   ⚠️  INTERNAL URL detected - This script must run FROM Railway container!")
    print("   ❌ Cannot connect to postgres.railway.internal from your local machine")
    print("\n💡 You have two options:")
    print("   1. Get the PUBLIC database URL from Railway dashboard (recommended)")
    print("   2. Run this script as a Railway deployment job")
    response = input("\n   Continue anyway? (yes/no): ")
    if response.lower() != 'yes':
        print("❌ Migration cancelled - Please get the public DATABASE_URL")
        sys.exit(0)

print("=" * 80)
print("🚨 CRITICAL DATA MIGRATION: Local → Railway")
print("=" * 80)
print(f"📍 Source (Local):  {LOCAL_DB}")
print(f"📍 Target (Railway): {RAILWAY_DB[:50]}...")
print("=" * 80)

# Create engines
print("\n🔌 Connecting to databases...")
try:
    local_engine = create_engine(LOCAL_DB)
    railway_engine = create_engine(RAILWAY_DB)
    print("✅ Connected to both databases")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    sys.exit(1)

# Test connections
print("\n🔍 Testing connections...")
try:
    with local_engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM bookings"))
        local_count = result.scalar()
        print(f"✅ Local database: {local_count} bookings found")

    with railway_engine.connect() as conn:
        # Create tables if they don't exist
        conn.execute(text("SELECT 1"))
        print(f"✅ Railway database: Connected successfully")
except Exception as e:
    print(f"❌ Connection test failed: {e}")
    sys.exit(1)

# Get list of all tables from local database
print("\n📋 Discovering tables...")
metadata = MetaData()
metadata.reflect(bind=local_engine)
tables = list(metadata.tables.keys())
print(f"✅ Found {len(tables)} tables: {', '.join(tables)}")

# Confirm migration
print("\n" + "=" * 80)
print("⚠️  WARNING: This will copy ALL data to Railway database")
print(f"   Tables to migrate: {', '.join(tables)}")
print(f"   Estimated bookings: {local_count}")
print("=" * 80)
response = input("\n🚨 Proceed with migration? (yes/no): ")

if response.lower() != 'yes':
    print("❌ Migration cancelled")
    sys.exit(0)

# Migrate each table
print("\n🚀 Starting migration...\n")
migration_summary = {}

for table_name in tables:
    try:
        print(f"📦 Migrating table: {table_name}")

        # Read all data from local table
        df = pd.read_sql_table(table_name, local_engine)
        row_count = len(df)

        if row_count == 0:
            print(f"   ⚠️  Table is empty, skipping")
            migration_summary[table_name] = {'status': 'skipped', 'rows': 0}
            continue

        # Write data to Railway table
        df.to_sql(table_name, railway_engine, if_exists='replace', index=False)

        # Verify migration
        verify_df = pd.read_sql_table(table_name, railway_engine)
        verify_count = len(verify_df)

        if verify_count == row_count:
            print(f"   ✅ Successfully migrated {row_count} rows")
            migration_summary[table_name] = {'status': 'success', 'rows': row_count}
        else:
            print(f"   ⚠️  Row count mismatch: {row_count} → {verify_count}")
            migration_summary[table_name] = {'status': 'partial', 'rows': verify_count}

    except Exception as e:
        print(f"   ❌ Migration failed: {e}")
        migration_summary[table_name] = {'status': 'failed', 'rows': 0, 'error': str(e)}

# Final verification
print("\n" + "=" * 80)
print("📊 MIGRATION SUMMARY")
print("=" * 80)

total_success = 0
total_failed = 0
total_rows = 0

for table, result in migration_summary.items():
    status_icon = "✅" if result['status'] == 'success' else "⚠️" if result['status'] == 'partial' else "❌"
    print(f"{status_icon} {table}: {result['rows']} rows ({result['status']})")

    if result['status'] == 'success':
        total_success += 1
        total_rows += result['rows']
    else:
        total_failed += 1

print("=" * 80)
print(f"✅ Successful: {total_success} tables, {total_rows} total rows")
print(f"❌ Failed: {total_failed} tables")
print("=" * 80)

# Final booking count verification
try:
    with railway_engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM bookings"))
        railway_count = result.scalar()
        print(f"\n🎯 FINAL VERIFICATION:")
        print(f"   Local bookings:   {local_count}")
        print(f"   Railway bookings: {railway_count}")

        if railway_count == local_count:
            print(f"   ✅ PERFECT MATCH - All {railway_count} bookings migrated successfully!")
        else:
            print(f"   ⚠️  MISMATCH - Expected {local_count}, got {railway_count}")
except Exception as e:
    print(f"❌ Final verification failed: {e}")

print("\n" + "=" * 80)
print("🎉 MIGRATION COMPLETE")
print("=" * 80)
print("\nNext steps:")
print("1. Verify data in Railway dashboard: https://web-production-8f671.up.railway.app/")
print("2. Check booking count matches your expectations")
print("3. Test creating/editing/deleting bookings")
print("=" * 80)

# Cleanup
local_engine.dispose()
railway_engine.dispose()
