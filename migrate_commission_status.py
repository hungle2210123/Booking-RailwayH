#!/usr/bin/env python3
"""
Migration script to add commission_status column to bookings table.

This migration adds a new column to track commission decision state:
- pending: Commission decision not yet made (default)
- confirmed: Commission kept (no cancellation)
- cancelled: Commission cancelled (set to 0)
"""

import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError

def get_database_url():
    """Get database URL from environment or default to local PostgreSQL."""
    # Check for Railway/Koyeb production database
    if 'DATABASE_URL' in os.environ:
        return os.environ['DATABASE_URL']

    # Check for local PostgreSQL
    if 'POSTGRES_URL' in os.environ:
        return os.environ['POSTGRES_URL']

    # Default to local PostgreSQL
    return "postgresql://postgres:locloc123@localhost:5432/hotel_booking"

def column_exists(engine, table_name, column_name):
    """Check if column exists in table."""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def migrate_commission_status():
    """Add commission_status column to bookings table."""

    print("🚀 Starting commission_status migration...")

    # Get database connection
    database_url = get_database_url()
    print(f"📦 Connecting to database: {database_url[:30]}...")

    try:
        engine = create_engine(database_url)

        with engine.begin() as conn:
            # Check if column already exists
            if column_exists(engine, 'bookings', 'commission_status'):
                print("✅ Column 'commission_status' already exists. Skipping migration.")
                return True

            print("📝 Adding commission_status column...")

            # Add the column with default value
            conn.execute(text("""
                ALTER TABLE bookings
                ADD COLUMN commission_status VARCHAR(50)
                DEFAULT 'pending'
                NOT NULL
            """))

            # Add check constraint
            print("🔒 Adding check constraint...")
            conn.execute(text("""
                ALTER TABLE bookings
                ADD CONSTRAINT chk_valid_commission_status
                CHECK (commission_status IN ('pending', 'confirmed', 'cancelled'))
            """))

            # Create index for performance
            print("⚡ Creating index...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_bookings_commission_status
                ON bookings(commission_status)
            """))

            # Migrate legacy data: Set commission_status based on existing data
            print("🔄 Migrating legacy data...")

            # If commission is 0 and collector is set, mark as 'cancelled'
            result = conn.execute(text("""
                UPDATE bookings
                SET commission_status = 'cancelled'
                WHERE commission = 0
                AND collector IS NOT NULL
                AND collector != ''
            """))
            print(f"   - Marked {result.rowcount} bookings as 'cancelled' (commission=0)")

            # If commission > 0 and collector is set, mark as 'confirmed'
            result = conn.execute(text("""
                UPDATE bookings
                SET commission_status = 'confirmed'
                WHERE commission > 0
                AND collector IS NOT NULL
                AND collector != ''
            """))
            print(f"   - Marked {result.rowcount} bookings as 'confirmed' (commission>0)")

            # All others remain 'pending' (default)
            result = conn.execute(text("""
                SELECT COUNT(*) as count
                FROM bookings
                WHERE commission_status = 'pending'
            """))
            pending_count = result.fetchone()[0]
            print(f"   - {pending_count} bookings remain 'pending'")

            print("✅ Migration completed successfully!")
            return True

    except SQLAlchemyError as e:
        print(f"❌ Migration failed: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    success = migrate_commission_status()
    sys.exit(0 if success else 1)
