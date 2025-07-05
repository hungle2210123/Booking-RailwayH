#!/usr/bin/env python3
"""
🚂 Automatic Railway Migration Script
Syncs local database to Railway automatically

Usage: python auto_migration.py
"""

import psycopg2
import sys
from datetime import datetime
import os

# Database configurations
LOCAL_DB = {
    "host": "localhost",
    "port": "5432",
    "database": "hotel_booking",
    "user": "postgres",
    "password": "postgres"  # Update if different
}

RAILWAY_DB = {
    "host": "mainline.proxy.rlwy.net", 
    "port": "36647",
    "database": "railway",
    "user": "postgres",
    "password": "VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi"
}

def connect_database(db_config, db_name):
    """Connect to database"""
    try:
        conn = psycopg2.connect(
            host=db_config["host"],
            port=db_config["port"],
            database=db_config["database"],
            user=db_config["user"],
            password=db_config["password"]
        )
        print(f"✅ Connected to {db_name} database")
        return conn
    except Exception as e:
        print(f"❌ Failed to connect to {db_name}: {e}")
        return None

def get_local_data(local_conn):
    """Extract all data from local database"""
    print("📤 Exporting data from local database...")
    
    try:
        with local_conn.cursor() as cur:
            # Get bookings data
            cur.execute("""
                SELECT booking_id, guest_id, checkin_date, checkout_date, 
                       room_amount, commission, taxi_amount, collector, 
                       booking_status, booking_notes, created_at, updated_at, 
                       collected_amount, guest_name, arrival_confirmed, 
                       arrival_confirmed_at
                FROM bookings 
                ORDER BY created_at
            """)
            bookings = cur.fetchall()
            
            # Get message templates
            cur.execute("SELECT * FROM message_templates ORDER BY template_id")
            templates = cur.fetchall()
            
            # Get expenses
            cur.execute("SELECT * FROM expenses ORDER BY expense_id")
            expenses = cur.fetchall()
            
            print(f"📊 Found {len(bookings)} bookings, {len(templates)} templates, {len(expenses)} expenses")
            return {
                'bookings': bookings,
                'templates': templates, 
                'expenses': expenses
            }
            
    except Exception as e:
        print(f"❌ Error extracting local data: {e}")
        return None

def clear_railway_database(railway_conn):
    """Clear and recreate Railway database structure"""
    print("🧹 Clearing Railway database...")
    
    try:
        with railway_conn.cursor() as cur:
            # Drop everything
            cur.execute("DROP SCHEMA public CASCADE")
            cur.execute("CREATE SCHEMA public")
            cur.execute("GRANT ALL ON SCHEMA public TO postgres")
            cur.execute("GRANT ALL ON SCHEMA public TO public")
            
            # Recreate tables
            print("🏗️ Recreating table structure...")
            
            # Bookings table
            cur.execute("""
                CREATE TABLE public.bookings (
                    booking_id character varying(50) NOT NULL PRIMARY KEY,
                    guest_id integer NOT NULL,
                    checkin_date date NOT NULL,
                    checkout_date date NOT NULL,
                    room_amount numeric DEFAULT 0,
                    commission numeric DEFAULT 0,
                    taxi_amount numeric DEFAULT 0,
                    collector character varying(255),
                    booking_status character varying(50) DEFAULT 'confirmed',
                    booking_notes text,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    collected_amount numeric NOT NULL DEFAULT 0.00,
                    guest_name text,
                    arrival_confirmed boolean NOT NULL DEFAULT false,
                    arrival_confirmed_at timestamp without time zone
                )
            """)
            
            # Message templates table
            cur.execute("""
                CREATE TABLE public.message_templates (
                    template_id SERIAL PRIMARY KEY,
                    template_name character varying(255) NOT NULL,
                    category character varying(100),
                    template_content text,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Expenses table
            cur.execute("""
                CREATE TABLE public.expenses (
                    expense_id SERIAL PRIMARY KEY,
                    description text,
                    amount numeric(12,2),
                    expense_date date,
                    category_id integer,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Other supporting tables
            cur.execute("""
                CREATE TABLE public.expense_categories (
                    category_id SERIAL PRIMARY KEY,
                    category_name character varying(255) NOT NULL,
                    description text,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE public.guests (
                    guest_id SERIAL PRIMARY KEY,
                    guest_name character varying(255),
                    email character varying(255),
                    phone character varying(255),
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE public.quick_notes (
                    note_id SERIAL PRIMARY KEY,
                    content text,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
                    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE public.arrival_times (
                    arrival_id SERIAL PRIMARY KEY,
                    booking_id character varying(255),
                    estimated_arrival timestamp,
                    actual_arrival timestamp,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute("""
                CREATE TABLE public.cancellation_actions (
                    action_id SERIAL PRIMARY KEY,
                    booking_id character varying(255),
                    action_type character varying(100),
                    action_date timestamp,
                    notes text,
                    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
        railway_conn.commit()
        print("✅ Railway database cleared and recreated")
        return True
        
    except Exception as e:
        print(f"❌ Error clearing Railway database: {e}")
        railway_conn.rollback()
        return False

def import_data_to_railway(railway_conn, data):
    """Import all data to Railway database"""
    print("📥 Importing data to Railway...")
    
    try:
        with railway_conn.cursor() as cur:
            # Import bookings
            print(f"📋 Importing {len(data['bookings'])} bookings...")
            for booking in data['bookings']:
                cur.execute("""
                    INSERT INTO public.bookings 
                    (booking_id, guest_id, checkin_date, checkout_date, room_amount, 
                     commission, taxi_amount, collector, booking_status, booking_notes, 
                     created_at, updated_at, collected_amount, guest_name, 
                     arrival_confirmed, arrival_confirmed_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, booking)
            
            # Import message templates
            if data['templates']:
                print(f"📝 Importing {len(data['templates'])} message templates...")
                for template in data['templates']:
                    # Skip template_id (auto-generated)
                    cur.execute("""
                        INSERT INTO public.message_templates 
                        (template_name, category, template_content, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s)
                    """, template[1:])  # Skip first column (template_id)
            
            # Import expenses
            if data['expenses']:
                print(f"💰 Importing {len(data['expenses'])} expenses...")
                for expense in data['expenses']:
                    # Skip expense_id (auto-generated)
                    cur.execute("""
                        INSERT INTO public.expenses 
                        (description, amount, expense_date, category_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, expense[1:])  # Skip first column (expense_id)
        
        railway_conn.commit()
        print("✅ All data imported successfully")
        return True
        
    except Exception as e:
        print(f"❌ Error importing data: {e}")
        railway_conn.rollback()
        return False

def verify_migration(local_conn, railway_conn):
    """Verify migration was successful"""
    print("🔍 Verifying migration...")
    
    try:
        # Check local counts
        with local_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bookings")
            local_bookings = cur.fetchone()[0]
            cur.execute("SELECT SUM(room_amount), SUM(commission) FROM bookings")
            local_totals = cur.fetchone()
        
        # Check Railway counts
        with railway_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM bookings")
            railway_bookings = cur.fetchone()[0]
            cur.execute("SELECT SUM(room_amount), SUM(commission) FROM bookings")
            railway_totals = cur.fetchone()
        
        print(f"\n📊 MIGRATION VERIFICATION:")
        print(f"   Local bookings: {local_bookings}")
        print(f"   Railway bookings: {railway_bookings}")
        print(f"   Local revenue: {local_totals[0]:,.2f}")
        print(f"   Railway revenue: {railway_totals[0]:,.2f}")
        print(f"   Local commission: {local_totals[1]:,.2f}")
        print(f"   Railway commission: {railway_totals[1]:,.2f}")
        
        if local_bookings == railway_bookings and local_totals == railway_totals:
            print("✅ MIGRATION SUCCESSFUL - All data matches!")
            return True
        else:
            print("❌ MIGRATION FAILED - Data mismatch!")
            return False
            
    except Exception as e:
        print(f"❌ Error verifying migration: {e}")
        return False

def main():
    """Main migration process"""
    print("🚂 AUTOMATIC RAILWAY MIGRATION")
    print("=" * 50)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Connect to databases
    print("🔌 Connecting to databases...")
    local_conn = connect_database(LOCAL_DB, "LOCAL")
    railway_conn = connect_database(RAILWAY_DB, "RAILWAY")
    
    if not local_conn or not railway_conn:
        print("❌ Database connection failed - stopping migration")
        sys.exit(1)
    
    try:
        # Step 2: Extract local data
        data = get_local_data(local_conn)
        if not data:
            print("❌ Failed to extract local data")
            sys.exit(1)
        
        # Step 3: Clear and recreate Railway
        if not clear_railway_database(railway_conn):
            print("❌ Failed to clear Railway database")
            sys.exit(1)
        
        # Step 4: Import data
        if not import_data_to_railway(railway_conn, data):
            print("❌ Failed to import data")
            sys.exit(1)
        
        # Step 5: Verify migration
        if verify_migration(local_conn, railway_conn):
            print(f"\n🎉 MIGRATION COMPLETED SUCCESSFULLY!")
            print(f"   {len(data['bookings'])} bookings migrated")
            print(f"   {len(data['templates'])} templates migrated")
            print(f"   {len(data['expenses'])} expenses migrated")
        else:
            print(f"\n❌ MIGRATION COMPLETED WITH ERRORS!")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
        
    finally:
        # Close connections
        if local_conn:
            local_conn.close()
        if railway_conn:
            railway_conn.close()
        
        print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 50)

if __name__ == "__main__":
    main()