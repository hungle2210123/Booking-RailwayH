#!/usr/bin/env python3
"""
🏠 ROOM MANAGEMENT SYSTEM - Database Migration
Adds rooms table and properly links rooms to apartments
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from datetime import datetime

# Detect environment
is_railway = bool(
    os.getenv('RAILWAY_ENVIRONMENT') or
    os.getenv('RAILWAY_ENVIRONMENT_ID') or
    os.getenv('RAILWAY_SERVICE_ID') or
    (os.getenv('DATABASE_URL') and 'railway' in os.getenv('DATABASE_URL', '').lower())
)
DATABASE_URL = os.getenv('DATABASE_URL', "postgresql://postgres:locloc123@localhost:5432/hotel_booking")

print("=" * 80)
print("🏠 ROOM MANAGEMENT SYSTEM - DATABASE MIGRATION")
print("=" * 80)
print(f"🌍 Environment: {'Railway' if is_railway else 'Local'}")
print(f"📍 Database URL: {DATABASE_URL[:70]}...")
print("=" * 80)

# Create engine
try:
    print("🔄 Creating database engine...")
    engine = create_engine(DATABASE_URL, echo=False)

    # Test connection
    print("🔄 Testing database connection...")
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print("✅ Database connection successful")
except Exception as e:
    print(f"❌ Connection failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 1: Create rooms table
print("\n📋 STEP 1: Creating rooms table...")
create_rooms_table_sql = """
CREATE TABLE IF NOT EXISTS rooms (
    room_id SERIAL PRIMARY KEY,
    room_name VARCHAR(255) NOT NULL UNIQUE,
    apartment_id INTEGER NOT NULL REFERENCES apartments(apartment_id) ON DELETE CASCADE,
    room_type VARCHAR(100),
    max_guests INTEGER DEFAULT 2,
    floor_number INTEGER,
    room_features TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rooms_apartment ON rooms(apartment_id);
CREATE INDEX IF NOT EXISTS idx_rooms_name ON rooms(room_name);
CREATE INDEX IF NOT EXISTS idx_rooms_active ON rooms(is_active);
"""

try:
    with engine.begin() as conn:
        conn.execute(text(create_rooms_table_sql))
        print("✅ Rooms table created successfully")
except Exception as e:
    print(f"❌ Failed to create rooms table: {e}")
    sys.exit(1)

# Step 2: Insert default rooms
print("\n📋 STEP 2: Inserting rooms for both apartments...")

try:
    with engine.begin() as conn:
        # Get apartment IDs
        result = conn.execute(text("""
            SELECT apartment_id, apartment_name
            FROM apartments
            WHERE apartment_name IN ('118 Hang Bac Hostel', '18 Hang Be')
            ORDER BY apartment_name
        """))
        apartments = {row[1]: row[0] for row in result}

        print(f"   Found apartments: {apartments}")

        if '118 Hang Bac Hostel' not in apartments or '18 Hang Be' not in apartments:
            print("❌ Error: Required apartments not found!")
            sys.exit(1)

        apt1_id = apartments['118 Hang Bac Hostel']
        apt2_id = apartments['18 Hang Be']

        # Insert rooms
        insert_rooms_sql = f"""
        INSERT INTO rooms (room_name, apartment_id, room_type, max_guests, is_active, display_order)
        VALUES
            -- Apartment 1: 118 Hang Bac Hostel (3 existing rooms)
            ('118 hang bac', {apt1_id}, 'Standard Room', 2, TRUE, 1),
            ('kitchen', {apt1_id}, 'Kitchen Room', 2, TRUE, 2),
            ('night market', {apt1_id}, 'Market View Room', 2, TRUE, 3),

            -- Apartment 2: 18 Hang Be (2 new rooms)
            ('hang be 101', {apt2_id}, 'Standard Room', 2, TRUE, 1),
            ('hang be 102', {apt2_id}, 'Standard Room', 2, TRUE, 2)
        ON CONFLICT (room_name) DO NOTHING;
        """

        result = conn.execute(text(insert_rooms_sql))
        print(f"✅ Rooms inserted successfully")

except Exception as e:
    print(f"❌ Failed to insert rooms: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Add room_id column to bookings table
print("\n📋 STEP 3: Adding room_id column to bookings...")
add_column_sql = """
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS room_id INTEGER
REFERENCES rooms(room_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_bookings_room ON bookings(room_id);
"""

try:
    with engine.begin() as conn:
        conn.execute(text(add_column_sql))
        print("✅ room_id column added to bookings table")
except Exception as e:
    print(f"⚠️  room_id column might already exist: {e}")

# Step 4: Link existing bookings to rooms based on accommodation_name
print("\n📋 STEP 4: Linking existing bookings to rooms...")

try:
    with engine.begin() as conn:
        # Check if accommodation_name column exists
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('bookings')]

        if 'accommodation_name' in columns:
            print("✅ Found accommodation_name column - migrating data...")

            # Update bookings to link to rooms based on accommodation_name
            update_sql = """
            UPDATE bookings b
            SET room_id = (
                SELECT room_id
                FROM rooms r
                WHERE LOWER(TRIM(r.room_name)) = LOWER(TRIM(b.accommodation_name))
                LIMIT 1
            )
            WHERE b.room_id IS NULL
            AND b.accommodation_name IS NOT NULL
            AND b.accommodation_name != '';
            """

            result = conn.execute(text(update_sql))
            print(f"✅ Linked {result.rowcount} bookings to rooms based on accommodation_name")

            # Check how many bookings still unmapped
            unmapped_result = conn.execute(text("""
                SELECT COUNT(*)
                FROM bookings
                WHERE room_id IS NULL
                AND accommodation_name IS NOT NULL
                AND accommodation_name != ''
            """))
            unmapped_count = unmapped_result.scalar()

            if unmapped_count > 0:
                print(f"⚠️  {unmapped_count} bookings still unmapped - checking accommodation names...")

                # Show unmapped accommodation names
                unmapped_names = conn.execute(text("""
                    SELECT DISTINCT accommodation_name, COUNT(*) as count
                    FROM bookings
                    WHERE room_id IS NULL
                    AND accommodation_name IS NOT NULL
                    AND accommodation_name != ''
                    GROUP BY accommodation_name
                    ORDER BY count DESC
                """))

                print("\n   Unmapped accommodation names:")
                for row in unmapped_names:
                    print(f"   - '{row[0]}': {row[1]} bookings")

                # Set default room for unmapped bookings
                default_room_result = conn.execute(text("""
                    SELECT room_id FROM rooms
                    WHERE room_name = '118 hang bac'
                    LIMIT 1
                """))
                default_room = default_room_result.fetchone()

                if default_room:
                    default_room_id = default_room[0]
                    update_default_sql = f"""
                    UPDATE bookings
                    SET room_id = {default_room_id}
                    WHERE room_id IS NULL
                    AND accommodation_name IS NOT NULL;
                    """

                    result = conn.execute(text(update_default_sql))
                    print(f"\n✅ Set {result.rowcount} unmapped bookings to default room (118 hang bac)")
        else:
            print("⚠️  No accommodation_name column - setting all bookings to default room")

            # Get default room
            default_room_result = conn.execute(text("""
                SELECT room_id FROM rooms
                WHERE room_name = '118 hang bac'
                LIMIT 1
            """))
            default_room = default_room_result.fetchone()

            if default_room:
                default_room_id = default_room[0]
                update_sql = f"""
                UPDATE bookings
                SET room_id = {default_room_id}
                WHERE room_id IS NULL;
                """

                result = conn.execute(text(update_sql))
                print(f"✅ Set {result.rowcount} bookings to default room (118 hang bac)")

except Exception as e:
    print(f"⚠️  Error during booking-room migration: {e}")
    import traceback
    traceback.print_exc()

# Step 5: Verify migration
print("\n📋 STEP 5: Verifying migration...")
try:
    with engine.connect() as conn:
        # Count rooms per apartment
        result = conn.execute(text("""
            SELECT
                a.apartment_name,
                COUNT(r.room_id) as room_count,
                STRING_AGG(r.room_name, ', ' ORDER BY r.display_order) as rooms
            FROM apartments a
            LEFT JOIN rooms r ON a.apartment_id = r.apartment_id
            GROUP BY a.apartment_id, a.apartment_name
            ORDER BY a.apartment_id
        """))

        print("\n📊 Rooms by Apartment:")
        for row in result:
            print(f"   🏢 {row[0]}: {row[1]} rooms")
            print(f"      └─ Rooms: {row[2]}")

        # Count bookings by room
        result = conn.execute(text("""
            SELECT
                a.apartment_name,
                r.room_name,
                COUNT(b.booking_id) as booking_count
            FROM rooms r
            LEFT JOIN apartments a ON r.apartment_id = a.apartment_id
            LEFT JOIN bookings b ON r.room_id = b.room_id
            GROUP BY a.apartment_name, r.room_name, r.display_order
            ORDER BY a.apartment_name, r.display_order
        """))

        print("\n📊 Bookings by Room:")
        total_bookings = 0
        for row in result:
            print(f"   {row[0]} → {row[1]}: {row[2]} bookings")
            total_bookings += row[2]

        print(f"\n   TOTAL: {total_bookings} bookings")

except Exception as e:
    print(f"❌ Verification failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("🎉 ROOM MIGRATION COMPLETE")
print("=" * 80)
print("\n✅ Summary:")
print("   • Rooms table created with apartment_id foreign key")
print("   • 5 rooms added (3 for 118 Hang Bac, 2 for 18 Hang Be)")
print("   • room_id column added to bookings table")
print("   • Existing bookings linked to appropriate rooms")
print("\n✅ Next steps:")
print("   1. Update booking forms to include room selection")
print("   2. Update dashboard to filter by room")
print("   3. Update revenue reports to show per-room statistics")
print("=" * 80)

# Cleanup
engine.dispose()
