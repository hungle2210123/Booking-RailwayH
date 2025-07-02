#!/usr/bin/env python3
"""
Database migration script for Railway auto-deployment
This runs automatically when Railway deploys from Git
"""

import os
import sys

def run_migration():
    """Run database migration on Railway deployment"""
    
    # Get Railway database URL from environment
    database_url = os.getenv('DATABASE_URL') or os.getenv('RAILWAY_POSTGRES_URL')
    
    if not database_url:
        print("❌ No database URL found in environment")
        return False
    
    print(f"🚂 Running Railway migration...")
    
    try:
        import psycopg2
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Create table if not exists
        create_sql = """
        CREATE TABLE IF NOT EXISTS cancellation_actions (
            action_id SERIAL PRIMARY KEY,
            booking_id VARCHAR(50) NOT NULL,
            guest_name VARCHAR(255) NOT NULL,
            cancellation_type VARCHAR(50) NOT NULL,
            action_status VARCHAR(50) NOT NULL DEFAULT 'pending',
            confirmed_by VARCHAR(100),
            confirmation_date TIMESTAMP,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_cancellation_booking_id ON cancellation_actions(booking_id);
        CREATE INDEX IF NOT EXISTS idx_cancellation_status ON cancellation_actions(action_status);
        
        -- Fix any existing NULL values
        UPDATE cancellation_actions 
        SET action_status = 'pending' 
        WHERE action_status IS NULL;
        
        -- Insert demo data for testing
        INSERT INTO cancellation_actions 
        (booking_id, guest_name, cancellation_type, action_status, notes) 
        VALUES 
        ('RW001', 'Le Thuong Railway', 'le_thuong', 'pending', '🚨 Railway auto-deploy - Le Thuong'),
        ('RW002', 'Private Guest Railway', 'zero_commission', 'pending', '💼 Railway auto-deploy - Private booking'),
        ('RW003', 'Cancelled Guest Railway', 'cancelled', 'pending', '❌ Railway auto-deploy - Cancelled guest'),
        ('RW004', 'Confirmed Guest Railway', 'le_thuong', 'confirmed', '✅ Railway auto-deploy - Already confirmed')
        ON CONFLICT (booking_id) DO NOTHING;
        """
        
        cursor.execute(create_sql)
        conn.commit()
        
        # Verify migration
        cursor.execute("SELECT COUNT(*) FROM cancellation_actions")
        count = cursor.fetchone()[0]
        
        print(f"✅ Railway migration completed successfully - {count} records")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    if success:
        print("🎉 Database migration completed!")
    else:
        print("❌ Migration failed - check logs")
        sys.exit(1)