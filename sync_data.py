#!/usr/bin/env python3
"""
Database Synchronization Script
Sync data between local PostgreSQL and Railway PostgreSQL
"""

import os
import sys
import psycopg2
import pandas as pd
from datetime import datetime

def get_connection(database_url):
    """Create PostgreSQL connection"""
    try:
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None

def export_table_data(conn, table_name):
    """Export table data to DataFrame"""
    try:
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        print(f"✅ Exported {len(df)} records from {table_name}")
        return df
    except Exception as e:
        print(f"❌ Export failed for {table_name}: {e}")
        return pd.DataFrame()

def import_table_data(conn, table_name, df):
    """Import DataFrame to table"""
    if df.empty:
        print(f"⚠️ No data to import for {table_name}")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Clear existing data
        cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
        
        # Insert new data
        for _, row in df.iterrows():
            columns = ', '.join(row.index)
            placeholders = ', '.join(['%s'] * len(row))
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            cursor.execute(query, tuple(row.values))
        
        conn.commit()
        cursor.close()
        print(f"✅ Imported {len(df)} records to {table_name}")
        return True
    except Exception as e:
        print(f"❌ Import failed for {table_name}: {e}")
        conn.rollback()
        return False

def sync_databases():
    """Main synchronization function"""
    print("🔄 Hotel Booking Database Synchronization")
    print("=" * 50)
    
    # Database URLs (update these)
    LOCAL_DB = "postgresql://username:password@localhost:5432/hotel_booking"
    RAILWAY_DB = "postgresql://username:password@host:port/database"
    
    print("📝 Please update the database URLs in this script:")
    print(f"   LOCAL_DB: {LOCAL_DB}")
    print(f"   RAILWAY_DB: {RAILWAY_DB}")
    
    # Get URLs from user input
    local_url = input("Enter LOCAL database URL (or press Enter to use default): ").strip()
    if local_url:
        LOCAL_DB = local_url
    
    railway_url = input("Enter RAILWAY database URL: ").strip()
    if not railway_url:
        print("❌ Railway database URL is required")
        return
    
    RAILWAY_DB = railway_url
    
    # Connect to databases
    print("\n📡 Connecting to databases...")
    local_conn = get_connection(LOCAL_DB)
    railway_conn = get_connection(RAILWAY_DB)
    
    if not local_conn or not railway_conn:
        print("❌ Database connection failed")
        return
    
    # Tables to sync (in dependency order)
    tables = [
        'guests',
        'bookings', 
        'quick_notes',
        'expenses',
        'expense_categories',
        'message_templates',
        'arrival_times'
    ]
    
    print(f"\n📤 Exporting data from local database...")
    exported_data = {}
    
    for table in tables:
        exported_data[table] = export_table_data(local_conn, table)
    
    print(f"\n📥 Importing data to Railway database...")
    
    for table in tables:
        if table in exported_data:
            import_table_data(railway_conn, table, exported_data[table])
    
    # Verify sync
    print(f"\n🔍 Verifying synchronization...")
    cursor = railway_conn.cursor()
    
    verification_query = """
    SELECT 
        (SELECT COUNT(*) FROM bookings) as bookings_count,
        (SELECT COUNT(*) FROM guests) as guests_count,
        (SELECT COUNT(*) FROM quick_notes) as notes_count,
        (SELECT COUNT(*) FROM expenses) as expenses_count,
        (SELECT COUNT(*) FROM message_templates) as templates_count
    """
    
    cursor.execute(verification_query)
    result = cursor.fetchone()
    
    print("📊 Final Record Counts:")
    print(f"   Bookings: {result[0]}")
    print(f"   Guests: {result[1]}")
    print(f"   Quick Notes: {result[2]}")
    print(f"   Expenses: {result[3]}")
    print(f"   Templates: {result[4]}")
    
    # Close connections
    local_conn.close()
    railway_conn.close()
    
    print("\n🎉 Database synchronization completed successfully!")
    print("💡 Update your .env file to use Railway database URL for consistency")

if __name__ == "__main__":
    try:
        sync_databases()
    except KeyboardInterrupt:
        print("\n⏹️ Synchronization cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")