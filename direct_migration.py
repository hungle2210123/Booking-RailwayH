#!/usr/bin/env python3
"""
Direct data migration from Local to Railway PostgreSQL
"""

import sys
import os

# Simple database connection without external dependencies
def migrate_data():
    """Transfer data directly from local to Railway"""
    
    # Database URLs
    LOCAL_DB = "postgresql://postgres:locloc123@localhost:5432/hotel_booking"
    
    # Railway internal URL (for when running from Railway app)
    RAILWAY_INTERNAL = "postgresql://postgres:VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi@postgres.railway.internal:5432/railway"
    
    # Railway external URL (for local access)
    RAILWAY_EXTERNAL = "postgresql://postgres:VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi@mainline.proxy.rlwy.net:36647/railway"
    
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        print("❌ psycopg2 not available. Install with: pip install psycopg2-binary")
        return False
    
    try:
        print("🔍 Connecting to LOCAL PostgreSQL...")
        local_conn = psycopg2.connect(LOCAL_DB)
        local_cursor = local_conn.cursor(cursor_factory=RealDictCursor)
        
        print("🔍 Connecting to RAILWAY PostgreSQL...")
        # Try external URL first (for local access)
        try:
            railway_conn = psycopg2.connect(RAILWAY_EXTERNAL)
        except:
            print("   Trying internal URL...")
            railway_conn = psycopg2.connect(RAILWAY_INTERNAL)
        
        railway_cursor = railway_conn.cursor()
        
        # Get tables to migrate
        local_cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)
        
        tables = [row['table_name'] for row in local_cursor.fetchall()]
        print(f"📋 Tables to migrate: {tables}")
        
        migrated_tables = {}
        
        for table in tables:
            print(f"\n📦 Migrating table: {table}")
            
            # Get all data from local table
            local_cursor.execute(f"SELECT * FROM {table};")
            rows = local_cursor.fetchall()
            
            if not rows:
                print(f"   ⚠️ No data in {table}")
                migrated_tables[table] = 0
                continue
            
            print(f"   📊 Found {len(rows)} rows in local {table}")
            
            # Clear Railway table first
            railway_cursor.execute(f"DELETE FROM {table};")
            print(f"   🗑️ Cleared Railway {table}")
            
            # Get column names
            columns = list(rows[0].keys())
            
            # Insert data to Railway
            success_count = 0
            for row in rows:
                try:
                    # Create INSERT statement
                    placeholders = ', '.join(['%s'] * len(columns))
                    columns_str = ', '.join(columns)
                    
                    sql = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"
                    values = [row[col] for col in columns]
                    
                    railway_cursor.execute(sql, values)
                    success_count += 1
                    
                except Exception as e:
                    print(f"      ⚠️ Error inserting row: {e}")
                    continue
            
            # Commit table changes
            railway_conn.commit()
            migrated_tables[table] = success_count
            print(f"   ✅ Successfully migrated {success_count}/{len(rows)} rows")
        
        # Summary
        print(f"\n🎉 MIGRATION COMPLETED!")
        print(f"📊 Migration Summary:")
        total_migrated = 0
        for table, count in migrated_tables.items():
            print(f"   - {table}: {count} rows")
            total_migrated += count
        
        print(f"\n📈 Total rows migrated: {total_migrated}")
        
        # Verify main bookings table
        railway_cursor.execute("SELECT COUNT(*) FROM bookings;")
        booking_count = railway_cursor.fetchone()[0]
        
        if booking_count > 0:
            railway_cursor.execute("SELECT guest_name, room_amount FROM bookings LIMIT 3;")
            samples = railway_cursor.fetchall()
            print(f"\n📋 Sample bookings in Railway:")
            for guest, amount in samples:
                print(f"   - {guest}: {amount}đ")
        
        local_cursor.close()
        local_conn.close()
        railway_cursor.close()
        railway_conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    print("🏨 Direct Database Migration Tool")
    print("=" * 50)
    print("📊 LOCAL → RAILWAY PostgreSQL Migration")
    print("=" * 50)
    
    success = migrate_data()
    
    if success:
        print("\n✅ SUCCESS: Your local data has been migrated to Railway!")
        print("🔗 Check your Railway app to verify the data")
        print("🎯 Next: Fix auto sync function to prevent data loss")
    else:
        print("\n❌ Migration failed. Check the error messages above.")