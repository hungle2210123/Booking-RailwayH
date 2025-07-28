#!/usr/bin/env python3
"""
Database Migration: Add accommodation_name column to bookings table
This script adds the accommodation_name field to support room type selection
"""

import os
import sys
from pathlib import Path
from sqlalchemy import text
from dotenv import load_dotenv

# Add current directory to path to import our modules
current_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(current_dir))

# Load environment variables
load_dotenv(current_dir / ".env")

def run_migration():
    """Add accommodation_name column to bookings table"""
    try:
        # Import database connection
        from core.database_service_postgresql import get_database_service
        from core.models import db
        
        print("🔄 Starting accommodation_name column migration...")
        
        # Initialize database service
        db_service = get_database_service()
        if not db_service:
            print("❌ Failed to get database service")
            return False
        
        with db.engine.connect() as conn:
            # Check if column already exists
            check_column_query = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'bookings' 
            AND column_name = 'accommodation_name'
            """
            result = conn.execute(text(check_column_query))
            if result.fetchone():
                print("✅ accommodation_name column already exists, skipping migration")
                return True
            
            # Add the accommodation_name column
            add_column_query = """
            ALTER TABLE bookings 
            ADD COLUMN accommodation_name VARCHAR(255) DEFAULT '118 Hang Bac Hostel';
            """
            
            conn.execute(text(add_column_query))
            conn.commit()
            print("✅ accommodation_name column added successfully")
            
            # Create index for better performance
            create_index_query = """
            CREATE INDEX IF NOT EXISTS idx_bookings_accommodation_name 
            ON bookings(accommodation_name);
            """
            
            conn.execute(text(create_index_query))
            conn.commit()
            print("✅ Index created for accommodation_name column")
            
            # Update existing bookings to have default accommodation name
            update_existing_query = """
            UPDATE bookings 
            SET accommodation_name = '118 Hang Bac Hostel' 
            WHERE accommodation_name IS NULL;
            """
            
            result = conn.execute(text(update_existing_query))
            conn.commit()
            updated_count = result.rowcount
            print(f"✅ Updated {updated_count} existing bookings with default accommodation name")
            
        print("🎉 Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Import Flask app to initialize database
    from app import app
    
    with app.app_context():
        success = run_migration()
        if not success:
            sys.exit(1)
        print("✅ All done! Room type selection should now work properly.")