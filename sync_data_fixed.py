#!/usr/bin/env python3
"""
Fixed Database Synchronization Script
Handles schema differences and data validation
"""

import psycopg2
import pandas as pd
from datetime import datetime

def create_missing_columns(conn):
    """Add missing columns to Railway database"""
    cursor = conn.cursor()
    
    try:
        # Add arrival_confirmed columns if missing
        cursor.execute("""
            ALTER TABLE bookings 
            ADD COLUMN IF NOT EXISTS arrival_confirmed BOOLEAN DEFAULT FALSE NOT NULL,
            ADD COLUMN IF NOT EXISTS arrival_confirmed_at TIMESTAMP NULL;
        """)
        
        # Add comment for documentation
        cursor.execute("""
            COMMENT ON COLUMN bookings.arrival_confirmed IS 'Guest arrival confirmation status';
            COMMENT ON COLUMN bookings.arrival_confirmed_at IS 'Timestamp when arrival was confirmed';
        """)
        
        conn.commit()
        print("✅ Added missing arrival_confirmed columns")
        
    except Exception as e:
        print(f"⚠️ Column addition warning: {e}")
        conn.rollback()
    
    cursor.close()

def clean_guest_data(df):
    """Clean guest data to handle email constraint"""
    # Fix empty emails
    df.loc[df['email'].isna() | (df['email'] == ''), 'email'] = None
    
    # Remove guests with invalid emails that would violate constraint
    invalid_emails = df[df['email'].notna() & ~df['email'].str.contains('@', na=False)]
    if not invalid_emails.empty:
        print(f"⚠️ Removing {len(invalid_emails)} guests with invalid emails")
        df = df[~df.index.isin(invalid_emails.index)]
    
    print(f"✅ Cleaned guest data: {len(df)} valid records")
    return df

def clean_booking_data(df, valid_guest_ids):
    """Clean booking data to ensure foreign key integrity"""
    # Only keep bookings for guests that were successfully imported
    initial_count = len(df)
    df = df[df['guest_id'].isin(valid_guest_ids)]
    final_count = len(df)
    
    if initial_count != final_count:
        print(f"⚠️ Removed {initial_count - final_count} bookings with missing guest references")
    
    print(f"✅ Cleaned booking data: {final_count} valid records")
    return df

def import_table_data_safe(conn, table_name, df, skip_columns=None):
    """Safely import table data with column filtering"""
    if df.empty:
        print(f"⚠️ No data to import for {table_name}")
        return False, []
    
    skip_columns = skip_columns or []
    
    try:
        cursor = conn.cursor()
        
        # Get existing columns in target table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND table_schema = 'public'
        """, (table_name,))
        
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        # Filter DataFrame to only include existing columns
        df_columns = [col for col in df.columns if col in existing_columns and col not in skip_columns]
        df_filtered = df[df_columns].copy()
        
        print(f"📋 Importing {len(df_filtered)} records to {table_name} with columns: {df_columns}")
        
        # Clear existing data
        cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
        
        # Insert new data
        imported_ids = []
        for _, row in df_filtered.iterrows():
            columns = ', '.join(row.index)
            placeholders = ', '.join(['%s'] * len(row))
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) RETURNING *"
            cursor.execute(query, tuple(row.values))
            result = cursor.fetchone()
            if result:
                # Get the primary key (first column)
                imported_ids.append(result[0])
        
        conn.commit()
        cursor.close()
        print(f"✅ Successfully imported {len(df_filtered)} records to {table_name}")
        return True, imported_ids
    except Exception as e:
        print(f"❌ Import failed for {table_name}: {e}")
        conn.rollback()
        if 'cursor' in locals():
            cursor.close()
        return False, []

def sync_databases_fixed():
    """Fixed synchronization with error handling"""
    print("🔄 Fixed Hotel Booking Database Synchronization")
    print("=" * 55)
    
    # Database URLs
    LOCAL_DB = input("Enter LOCAL database URL: ").strip()
    RAILWAY_DB = input("Enter RAILWAY database URL: ").strip()
    
    if not LOCAL_DB or not RAILWAY_DB:
        print("❌ Both database URLs are required")
        return
    
    # Connect to databases
    print("\n📡 Connecting to databases...")
    try:
        local_conn = psycopg2.connect(LOCAL_DB)
        railway_conn = psycopg2.connect(RAILWAY_DB)
        print("✅ Connected to both databases")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return
    
    # Create missing columns on Railway
    print("\n🔧 Updating Railway database schema...")
    create_missing_columns(railway_conn)
    
    print(f"\n📤 Exporting data from local database...")
    
    # Export guests
    guests_df = pd.read_sql_query("SELECT * FROM guests", local_conn)
    guests_df = clean_guest_data(guests_df)
    
    # Export bookings  
    bookings_df = pd.read_sql_query("SELECT * FROM bookings", local_conn)
    
    # Export other tables
    notes_df = pd.read_sql_query("SELECT * FROM quick_notes", local_conn)
    expenses_df = pd.read_sql_query("SELECT * FROM expenses", local_conn)
    expense_cats_df = pd.read_sql_query("SELECT * FROM expense_categories", local_conn)
    templates_df = pd.read_sql_query("SELECT * FROM message_templates", local_conn)
    arrivals_df = pd.read_sql_query("SELECT * FROM arrival_times", local_conn)
    
    print(f"\n📥 Importing data to Railway database...")
    
    # Import guests first
    success, imported_guest_ids = import_table_data_safe(railway_conn, 'guests', guests_df)
    
    if success:
        # Clean bookings based on successfully imported guests
        bookings_df = clean_booking_data(bookings_df, imported_guest_ids)
        
        # Import bookings
        success, imported_booking_ids = import_table_data_safe(railway_conn, 'bookings', bookings_df)
        
        if success:
            # Clean arrival_times based on successfully imported bookings
            arrivals_df = arrivals_df[arrivals_df['booking_id'].isin(imported_booking_ids)]
            import_table_data_safe(railway_conn, 'arrival_times', arrivals_df)
    
    # Import other tables (not dependent on foreign keys)
    import_table_data_safe(railway_conn, 'quick_notes', notes_df)
    import_table_data_safe(railway_conn, 'expenses', expenses_df)
    import_table_data_safe(railway_conn, 'expense_categories', expense_cats_df)
    import_table_data_safe(railway_conn, 'message_templates', templates_df)
    
    # Final verification
    print(f"\n🔍 Verifying synchronization...")
    cursor = railway_conn.cursor()
    
    cursor.execute("""
        SELECT 
            (SELECT COUNT(*) FROM bookings) as bookings_count,
            (SELECT COUNT(*) FROM guests) as guests_count,
            (SELECT COUNT(*) FROM quick_notes) as notes_count,
            (SELECT COUNT(*) FROM expenses) as expenses_count,
            (SELECT COUNT(*) FROM message_templates) as templates_count,
            (SELECT COUNT(*) FROM arrival_times) as arrivals_count
    """)
    
    result = cursor.fetchone()
    
    print("📊 Final Record Counts on Railway:")
    print(f"   Bookings: {result[0]}")
    print(f"   Guests: {result[1]}")
    print(f"   Quick Notes: {result[2]}")
    print(f"   Expenses: {result[3]}")
    print(f"   Templates: {result[4]}")
    print(f"   Arrival Times: {result[5]}")
    
    # Close connections
    local_conn.close()
    railway_conn.close()
    
    print("\n🎉 Fixed database synchronization completed!")
    print("💡 Your Railway database now has the updated schema and clean data")

if __name__ == "__main__":
    try:
        sync_databases_fixed()
    except KeyboardInterrupt:
        print("\n⏹️ Synchronization cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")