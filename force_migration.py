#!/usr/bin/env python3
"""
FORCE MIGRATION - Run all migrations in sequence
This script ensures migrations run even if detection fails
"""

import os
import sys
import subprocess

print("=" * 80)
print("🚀 FORCE MIGRATION - Running All Database Updates")
print("=" * 80)

# Check if we have DATABASE_URL
database_url = os.environ.get('DATABASE_URL')
if not database_url:
    print("⚠️  No DATABASE_URL - using local database")
    database_url = "postgresql://postgres:locloc123@localhost:5432/hotel_booking"

print(f"📍 Database: {database_url[:50]}...")

# Migration 1: Apartments
print("\n" + "=" * 80)
print("📋 MIGRATION 1: Apartments + Guests Tables")
print("=" * 80)
try:
    result = subprocess.run(
        [sys.executable, 'migrate_add_apartments.py'],
        capture_output=True,
        text=True,
        timeout=120
    )
    print(result.stdout)
    if result.returncode != 0:
        print("⚠️  Apartment migration had issues:")
        print(result.stderr)
except Exception as e:
    print(f"⚠️  Apartment migration error: {e}")

# Migration 2: Rooms
print("\n" + "=" * 80)
print("📋 MIGRATION 2: Rooms Table")
print("=" * 80)
try:
    result = subprocess.run(
        [sys.executable, 'migrate_add_rooms.py'],
        capture_output=True,
        text=True,
        timeout=120
    )
    print(result.stdout)
    if result.returncode != 0:
        print("⚠️  Room migration had issues:")
        print(result.stderr)
except Exception as e:
    print(f"⚠️  Room migration error: {e}")

# Verification
print("\n" + "=" * 80)
print("🔍 VERIFICATION")
print("=" * 80)

try:
    from sqlalchemy import create_engine, inspect, text

    engine = create_engine(database_url)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    print(f"✅ Total tables: {len(tables)}")
    print(f"   Apartments exists: {'apartments' in tables}")
    print(f"   Rooms exists: {'rooms' in tables}")
    print(f"   Guests exists: {'guests' in tables}")

    # Check bookings columns
    if 'bookings' in tables:
        columns = [col['name'] for col in inspector.get_columns('bookings')]
        print(f"\n📊 Bookings table columns:")
        print(f"   apartment_id: {'apartment_id' in columns}")
        print(f"   room_id: {'room_id' in columns}")

    # Count rooms
    if 'rooms' in tables:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM rooms"))
            room_count = result.scalar()
            print(f"\n🏠 Total rooms: {room_count}")

            result = conn.execute(text("SELECT room_name FROM rooms ORDER BY apartment_id, display_order"))
            rooms = result.fetchall()
            print(f"\n   Rooms:")
            for room in rooms:
                print(f"   - {room[0]}")

    engine.dispose()
    print("\n✅ MIGRATION VERIFICATION COMPLETE")

except Exception as e:
    print(f"❌ Verification failed: {e}")
    import traceback
    traceback.print_exc()

print("=" * 80)
print("🎉 FORCE MIGRATION COMPLETE")
print("=" * 80)
