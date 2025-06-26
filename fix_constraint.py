#!/usr/bin/env python3
"""
Fix database constraint to allow Vietnamese booking statuses
"""
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fix_booking_constraint():
    """Update booking status constraint"""
    try:
        # Get database URL from environment
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found in environment")
            return False
            
        print("🔧 Connecting to PostgreSQL database...")
        
        # Connect to database
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("🔧 Dropping old constraint...")
        # Drop existing constraint
        cur.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS chk_valid_status;")
        
        print("🔧 Adding new constraint with Vietnamese values...")
        # Add new constraint with Vietnamese values
        cur.execute("""
            ALTER TABLE bookings ADD CONSTRAINT chk_valid_status 
            CHECK (booking_status IN ('confirmed', 'cancelled', 'deleted', 'pending', 'mới', 'đã hủy', 'đã xóa', 'chờ xử lý'));
        """)
        
        # Commit changes
        conn.commit()
        
        print("✅ Database constraint updated successfully!")
        
        # Verify current bookings
        cur.execute("SELECT COUNT(*) FROM bookings;")
        count = cur.fetchone()[0]
        print(f"📊 Current bookings in database: {count}")
        
        cur.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Error updating constraint: {e}")
        return False

if __name__ == "__main__":
    success = fix_constraint()
    if success:
        print("\n🎉 Ready to import CSV data!")
        print("📍 Go back to your browser and click 'Nhập CSV' again")
    else:
        print("\n❌ Failed to update constraint")