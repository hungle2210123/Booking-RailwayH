#!/usr/bin/env python3
"""
Migration Script: Add Accommodation Support
Adds accommodation_name and rooms_occupied columns to bookings table
Supports multiple hotels: 118 Hang Bac (4 rooms) + 18 Hang Be (2 rooms) = 6 total rooms
"""

import psycopg2
from psycopg2 import sql
import os

# Database configurations
DATABASES = {
    'local': {
        'host': 'localhost',
        'port': 5432,
        'database': 'hotel_booking',
        'user': 'postgres',
        'password': 'locloc123'
    },
    'railway': {
        'host': 'mainline.proxy.rlwy.net',
        'port': 36647,
        'database': 'railway',
        'user': 'postgres',
        'password': 'VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi'
    }
}

def run_migration(db_config, db_name):
    """Run the accommodation migration on specified database"""
    print(f"\n{'='*60}")
    print(f"🏨 ACCOMMODATION MIGRATION - {db_name.upper()}")
    print(f"{'='*60}")

    try:
        # Connect to database
        conn = psycopg2.connect(**db_config)
        conn.autocommit = False
        cursor = conn.cursor()

        print(f"✅ Connected to {db_name} database")

        # 1. Add accommodation_name column
        print("\n📋 Step 1: Adding accommodation_name column...")
        try:
            cursor.execute("""
                ALTER TABLE bookings
                ADD COLUMN IF NOT EXISTS accommodation_name VARCHAR(255)
                DEFAULT '118 Hang Bac Hostel';
            """)
            print("✅ accommodation_name column added")
        except Exception as e:
            print(f"⚠️  accommodation_name column may already exist: {e}")

        # 2. Add rooms_occupied column (for multi-room bookings)
        print("\n📋 Step 2: Adding rooms_occupied column...")
        try:
            cursor.execute("""
                ALTER TABLE bookings
                ADD COLUMN IF NOT EXISTS rooms_occupied INTEGER
                DEFAULT 1
                CHECK (rooms_occupied >= 1 AND rooms_occupied <= 6);
            """)
            print("✅ rooms_occupied column added")
        except Exception as e:
            print(f"⚠️  rooms_occupied column may already exist: {e}")

        # 3. Create index on accommodation_name for faster queries
        print("\n📋 Step 3: Creating index on accommodation_name...")
        try:
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_bookings_accommodation
                ON bookings(accommodation_name);
            """)
            print("✅ Index created on accommodation_name")
        except Exception as e:
            print(f"⚠️  Index may already exist: {e}")

        # 4. Update existing bookings to have default accommodation
        print("\n📋 Step 4: Updating existing bookings...")
        cursor.execute("""
            UPDATE bookings
            SET accommodation_name = '118 Hang Bac Hostel',
                rooms_occupied = 1
            WHERE accommodation_name IS NULL OR accommodation_name = '';
        """)
        updated_count = cursor.rowcount
        print(f"✅ Updated {updated_count} existing bookings")

        # 5. Verify migration
        print("\n📋 Step 5: Verifying migration...")
        cursor.execute("""
            SELECT
                COUNT(*) as total_bookings,
                COUNT(DISTINCT accommodation_name) as distinct_hotels,
                SUM(rooms_occupied) as total_rooms_occupied
            FROM bookings
            WHERE booking_status NOT IN ('deleted', 'cancelled', 'đã hủy');
        """)
        stats = cursor.fetchone()
        print(f"✅ Migration verified:")
        print(f"   - Total active bookings: {stats[0]}")
        print(f"   - Distinct hotels: {stats[1]}")
        print(f"   - Total rooms occupied: {stats[2]}")

        # 6. Show accommodation breakdown
        print("\n📊 Accommodation breakdown:")
        cursor.execute("""
            SELECT
                accommodation_name,
                COUNT(*) as booking_count,
                SUM(rooms_occupied) as total_rooms
            FROM bookings
            WHERE booking_status NOT IN ('deleted', 'cancelled', 'đã hủy')
                AND checkin_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY accommodation_name
            ORDER BY booking_count DESC;
        """)
        accommodations = cursor.fetchall()
        for acc in accommodations:
            print(f"   - {acc[0]}: {acc[1]} bookings ({acc[2]} rooms)")

        # Commit transaction
        conn.commit()
        print(f"\n{'='*60}")
        print(f"✅ MIGRATION COMPLETED SUCCESSFULLY - {db_name.upper()}")
        print(f"{'='*60}\n")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"\n❌ ERROR during {db_name} migration: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

def main():
    """Main migration execution"""
    print("\n🏨 HOTEL ACCOMMODATION MIGRATION")
    print("=" * 60)
    print("Adding support for multiple hotels:")
    print("  • 118 Hang Bac Hostel (4 rooms) - Original")
    print("  • 18 Hang Be Apartment (2 rooms) - NEW")
    print("  • Total capacity: 6 rooms")
    print("=" * 60)

    # Determine which database to migrate
    db_source = os.getenv('DATABASE_SOURCE', 'auto')

    if db_source == 'auto':
        # Try Railway first, fallback to local
        print("\n🔍 Auto-detection mode - trying Railway first...")
        success = run_migration(DATABASES['railway'], 'railway')
        if not success:
            print("\n🔄 Railway failed, trying local...")
            success = run_migration(DATABASES['local'], 'local')
    elif db_source == 'railway':
        success = run_migration(DATABASES['railway'], 'railway')
    else:
        success = run_migration(DATABASES['local'], 'local')

    if success:
        print("\n" + "="*60)
        print("✅ ALL MIGRATIONS COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("\nNext steps:")
        print("1. Update booking forms to include accommodation selector")
        print("2. Update calendar views to show 6 rooms capacity")
        print("3. Add hotel filter to dashboard and reports")
        print("="*60 + "\n")
    else:
        print("\n" + "="*60)
        print("❌ MIGRATION FAILED - Please check errors above")
        print("="*60 + "\n")
        exit(1)

if __name__ == "__main__":
    main()
