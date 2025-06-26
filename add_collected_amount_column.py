#!/usr/bin/env python3
"""
Add collected_amount column to bookings table
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

from core.models import db
from core.database_service_postgresql import get_database_service
from sqlalchemy import text
from app_postgresql import app

def add_collected_amount_column():
    """Add collected_amount column to bookings table"""
    
    with app.app_context():
        try:
            # Check if column already exists
            check_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'bookings' 
            AND column_name = 'collected_amount'
            """
            
            result = db.session.execute(text(check_query)).fetchone()
            
            if result:
                print("✅ collected_amount column already exists!")
                return True
            
            # Add the column
            add_column_query = """
            ALTER TABLE bookings 
            ADD COLUMN collected_amount DECIMAL(12, 2) DEFAULT 0.00 NOT NULL
            """
            
            db.session.execute(text(add_column_query))
            db.session.commit()
            
            print("✅ Successfully added collected_amount column to bookings table!")
            
            # Verify the column was added
            verify_result = db.session.execute(text(check_query)).fetchone()
            if verify_result:
                print("✅ Column verified - migration successful!")
                
                # Show current table structure
                columns_query = """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'bookings'
                ORDER BY ordinal_position
                """
                
                columns = db.session.execute(text(columns_query)).fetchall()
                print("\n📋 Current bookings table structure:")
                for col in columns:
                    print(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
                
                return True
            else:
                print("❌ Failed to verify column addition")
                return False
                
        except Exception as e:
            print(f"❌ Error adding column: {e}")
            db.session.rollback()
            return False

def update_existing_bookings():
    """Update existing bookings to set collected_amount = room_amount initially"""
    
    with app.app_context():
        try:
            # Set collected_amount to room_amount for existing bookings
            update_query = """
            UPDATE bookings 
            SET collected_amount = room_amount 
            WHERE collected_amount = 0.00 AND room_amount > 0
            """
            
            result = db.session.execute(text(update_query))
            db.session.commit()
            
            rows_updated = result.rowcount
            print(f"✅ Updated {rows_updated} existing bookings with collected_amount = room_amount")
            
            return True
            
        except Exception as e:
            print(f"❌ Error updating existing bookings: {e}")
            db.session.rollback()
            return False

def main():
    """Main migration function"""
    
    print("🔄 ADDING COLLECTED_AMOUNT COLUMN TO BOOKINGS TABLE")
    print("=" * 60)
    
    # Step 1: Add the column
    if add_collected_amount_column():
        print("\n🔄 Step 1: Column added successfully")
        
        # Step 2: Update existing bookings
        if update_existing_bookings():
            print("🔄 Step 2: Existing data updated successfully")
            
            print("\n✅ MIGRATION COMPLETE!")
            print("\n🎯 NEXT STEPS:")
            print("1. Restart your Flask server")
            print("2. Test the collect payment functionality")
            print("3. collected_amount will now track actual money collected")
            print("4. room_amount remains the original booking amount")
            
            return True
        else:
            print("❌ Step 2 failed")
            return False
    else:
        print("❌ Step 1 failed")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)