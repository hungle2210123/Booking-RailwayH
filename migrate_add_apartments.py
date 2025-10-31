#!/usr/bin/env python3
"""
🏢 APARTMENT MANAGEMENT SYSTEM - Database Migration
Adds apartments table and links existing bookings to apartments
"""

import os
import sys
from sqlalchemy import create_engine, text
from datetime import datetime

# Detect environment and use appropriate database
# Railway detection: Check for DATABASE_URL containing railway.internal or Railway environment variables
is_railway = bool(
    os.getenv('RAILWAY_ENVIRONMENT') or
    os.getenv('RAILWAY_ENVIRONMENT_ID') or
    os.getenv('RAILWAY_SERVICE_ID') or
    (os.getenv('DATABASE_URL') and 'railway' in os.getenv('DATABASE_URL', '').lower())
)
DATABASE_URL = os.getenv('DATABASE_URL', "postgresql://postgres:locloc123@localhost:5432/hotel_booking")

print("=" * 80)
print("🏢 APARTMENT MANAGEMENT SYSTEM - DATABASE MIGRATION")
print("=" * 80)
print(f"🌍 Environment: {'Railway' if is_railway else 'Local'}")
print(f"📍 Railway Detection Methods:")
print(f"   - RAILWAY_ENVIRONMENT: {bool(os.getenv('RAILWAY_ENVIRONMENT'))}")
print(f"   - RAILWAY_ENVIRONMENT_ID: {bool(os.getenv('RAILWAY_ENVIRONMENT_ID'))}")
print(f"   - RAILWAY_SERVICE_ID: {bool(os.getenv('RAILWAY_SERVICE_ID'))}")
print(f"   - DATABASE_URL contains 'railway': {bool(os.getenv('DATABASE_URL') and 'railway' in os.getenv('DATABASE_URL', '').lower())}")
print(f"📍 Database URL: {DATABASE_URL[:70]}...")
print(f"📍 Database URL length: {len(DATABASE_URL)}")
print("=" * 80)

# Create engine with better error handling
try:
    print("🔄 Creating database engine...")
    engine = create_engine(DATABASE_URL, echo=False)
    print("✅ Engine created")

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

# Step 0: Create guests table if it doesn't exist
print("\n📋 STEP 0: Creating guests table if needed...")

try:
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if 'guests' not in tables:
        print("   Creating guests table from scratch...")
        create_guests_table_sql = """
        CREATE TABLE guests (
            guest_id SERIAL PRIMARY KEY,
            full_name VARCHAR(255) NOT NULL,
            email VARCHAR(255) UNIQUE,
            phone VARCHAR(50),
            nationality VARCHAR(100),
            passport_number VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX idx_guests_name ON guests(full_name);
        CREATE INDEX idx_guests_email ON guests(email);
        CREATE INDEX idx_guests_phone ON guests(phone);
        """

        with engine.begin() as conn:
            conn.execute(text(create_guests_table_sql))
        print("✅ Guests table created successfully")
    else:
        print("✅ Guests table already exists - skipping creation")

except Exception as e:
    print(f"⚠️  Guests table check/creation: {e}")
    print("   Continuing anyway - guests features may be limited")

# Step 1: Create apartments table
print("\n📋 STEP 1: Creating apartments table...")
create_apartments_table_sql = """
CREATE TABLE IF NOT EXISTS apartments (
    apartment_id SERIAL PRIMARY KEY,
    apartment_name VARCHAR(255) NOT NULL UNIQUE,
    apartment_address TEXT,
    total_rooms INTEGER NOT NULL DEFAULT 1,
    max_guests_per_room INTEGER DEFAULT 2,
    apartment_type VARCHAR(100),
    floor_number INTEGER,
    building_name VARCHAR(255),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    owner_name VARCHAR(255),
    owner_phone VARCHAR(50),
    property_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_apartments_name ON apartments(apartment_name);
CREATE INDEX IF NOT EXISTS idx_apartments_active ON apartments(is_active);
"""

try:
    with engine.begin() as conn:
        conn.execute(text(create_apartments_table_sql))
        print("✅ Apartments table created successfully")
except Exception as e:
    print(f"❌ Failed to create apartments table: {e}")
    sys.exit(1)

# Step 2: Insert default apartments
print("\n📋 STEP 2: Inserting default apartments...")
insert_apartments_sql = """
INSERT INTO apartments (apartment_name, apartment_address, total_rooms, apartment_type, is_active, building_name)
VALUES
    ('118 Hang Bac Hostel', '118 Hàng Bạc, Hoàn Kiếm, Hà Nội', 4, 'Hostel', TRUE, '118 Hàng Bạc'),
    ('18 Hang Be', '18 Hàng Bè, Hoàn Kiếm, Hà Nội', 2, 'Apartment', TRUE, '18 Hàng Bè')
ON CONFLICT (apartment_name) DO NOTHING;
"""

try:
    with engine.begin() as conn:
        result = conn.execute(text(insert_apartments_sql))
        print(f"✅ Default apartments inserted (or already exist)")
except Exception as e:
    print(f"❌ Failed to insert apartments: {e}")
    sys.exit(1)

# Step 3: Add apartment_id column to bookings table
print("\n📋 STEP 3: Adding apartment_id column to bookings...")
add_column_sql = """
ALTER TABLE bookings
ADD COLUMN IF NOT EXISTS apartment_id INTEGER
REFERENCES apartments(apartment_id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_bookings_apartment ON bookings(apartment_id);
"""

try:
    with engine.begin() as conn:
        conn.execute(text(add_column_sql))
        print("✅ apartment_id column added to bookings table")
except Exception as e:
    print(f"⚠️  apartment_id column might already exist: {e}")

# Step 4: Link existing bookings to apartments (based on accommodation_name if it exists)
print("\n📋 STEP 4: Linking existing bookings to apartments...")

# First, check if accommodation_name column exists
try:
    with engine.begin() as conn:
        # Check for accommodation_name column
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'bookings' AND column_name = 'accommodation_name';
        """))
        has_accommodation_name = result.fetchone() is not None

        if has_accommodation_name:
            print("✅ Found accommodation_name column - migrating data...")

            # Update bookings to link to apartments based on accommodation_name
            update_sql = """
            UPDATE bookings b
            SET apartment_id = (
                SELECT apartment_id
                FROM apartments a
                WHERE a.apartment_name = b.accommodation_name
                LIMIT 1
            )
            WHERE b.apartment_id IS NULL
            AND b.accommodation_name IS NOT NULL;
            """

            result = conn.execute(text(update_sql))
            print(f"✅ Linked {result.rowcount} bookings to apartments based on accommodation_name")
        else:
            print("⚠️  No accommodation_name column found - will set default apartment")

            # Get the first apartment ID (118 Hang Bac Hostel)
            result = conn.execute(text("SELECT apartment_id FROM apartments WHERE apartment_name = '118 Hang Bac Hostel' LIMIT 1"))
            default_apartment = result.fetchone()

            if default_apartment:
                default_id = default_apartment[0]

                # Set all bookings without apartment_id to default apartment
                update_sql = f"""
                UPDATE bookings
                SET apartment_id = {default_id}
                WHERE apartment_id IS NULL;
                """

                result = conn.execute(text(update_sql))
                print(f"✅ Set {result.rowcount} bookings to default apartment (118 Hang Bac Hostel)")
            else:
                print("❌ Default apartment not found!")

except Exception as e:
    print(f"⚠️  Error during booking migration: {e}")

# Step 4.5: Create guest records from bookings if needed
print("\n📋 STEP 4.5: Creating guest records from bookings...")
try:
    # Check if guests table exists and has correct schema
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    if 'guests' not in tables:
        print("⚠️  Guests table doesn't exist - skipping guest record creation")
    else:
        # Check if full_name column exists
        columns = [col['name'] for col in inspector.get_columns('guests')]
        if 'full_name' not in columns:
            print(f"⚠️  Guests table has wrong schema (columns: {columns}) - skipping")
        else:
            with engine.begin() as conn:
                # Check if bookings have guest_name but no guest_id
                create_guests_sql = """
                INSERT INTO guests (full_name, created_at)
                SELECT DISTINCT
                    COALESCE(guest_name, 'Unknown Guest') as full_name,
                    CURRENT_TIMESTAMP
                FROM bookings
                WHERE guest_name IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM guests WHERE guests.full_name = bookings.guest_name
                )
                ON CONFLICT DO NOTHING;
                """

                # First create guests
                result = conn.execute(text(create_guests_sql))
                print(f"✅ Created {result.rowcount} guest records from bookings")

                # Then link bookings to guests
                link_guests_sql = """
                UPDATE bookings b
                SET guest_id = (
                    SELECT guest_id
                    FROM guests g
                    WHERE g.full_name = b.guest_name
                    LIMIT 1
                )
                WHERE b.guest_id IS NULL
                AND b.guest_name IS NOT NULL;
                """

                result = conn.execute(text(link_guests_sql))
                print(f"✅ Linked {result.rowcount} bookings to guest records")

except Exception as e:
    print(f"⚠️  Error creating guest records: {e}")
    # Continue anyway - not critical

# Step 5: Verify migration
print("\n📋 STEP 5: Verifying migration...")
try:
    with engine.connect() as conn:
        # Count apartments
        result = conn.execute(text("SELECT COUNT(*) FROM apartments"))
        apartment_count = result.scalar()
        print(f"✅ Total apartments: {apartment_count}")

        # Show apartments
        result = conn.execute(text("SELECT apartment_id, apartment_name, total_rooms, is_active FROM apartments ORDER BY apartment_id"))
        apartments = result.fetchall()
        print("\n📊 Apartments:")
        for apt in apartments:
            status = "🟢 Active" if apt[3] else "🔴 Inactive"
            print(f"   {apt[0]}. {apt[1]} ({apt[2]} rooms) - {status}")

        # Count bookings by apartment
        result = conn.execute(text("""
            SELECT
                COALESCE(a.apartment_name, 'Unassigned') as apartment,
                COUNT(*) as booking_count
            FROM bookings b
            LEFT JOIN apartments a ON b.apartment_id = a.apartment_id
            GROUP BY a.apartment_name
            ORDER BY booking_count DESC
        """))
        booking_counts = result.fetchall()

        print("\n📊 Bookings by Apartment:")
        total_bookings = 0
        for row in booking_counts:
            print(f"   {row[0]}: {row[1]} bookings")
            total_bookings += row[1]
        print(f"\n   TOTAL: {total_bookings} bookings")

except Exception as e:
    print(f"❌ Verification failed: {e}")

print("\n" + "=" * 80)
print("🎉 MIGRATION COMPLETE")
print("=" * 80)
print("\n✅ Next steps:")
print("1. Run this migration on Railway PostgreSQL:")
print("   RAILWAY_DATABASE_URL='postgresql://...' python3 migrate_add_apartments.py")
print("2. Test apartment management in dashboard")
print("3. Assign bookings to specific apartments")
print("=" * 80)

# Cleanup
engine.dispose()
