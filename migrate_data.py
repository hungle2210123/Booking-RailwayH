#!/usr/bin/env python3
"""
Migrate data from Local PostgreSQL to Railway PostgreSQL
"""

import os
import psycopg2
import pandas as pd
from datetime import datetime
import json

# Database connections
LOCAL_DB_URL = "postgresql://postgres:locloc123@localhost:5432/hotel_booking"
RAILWAY_DB_URL = "postgresql://postgres:VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi@postgres.railway.internal:5432/railway"

def export_local_data():
    """Export all data from local PostgreSQL"""
    print("🔍 Connecting to LOCAL PostgreSQL...")
    
    try:
        local_conn = psycopg2.connect(LOCAL_DB_URL)
        local_cursor = local_conn.cursor()
        
        # Get all tables
        local_cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE';
        """)
        
        tables = [row[0] for row in local_cursor.fetchall()]
        print(f"📋 Found tables: {tables}")
        
        exported_data = {}
        
        for table in tables:
            print(f"📦 Exporting table: {table}")
            
            # Get all data from table
            local_cursor.execute(f"SELECT * FROM {table};")
            rows = local_cursor.fetchall()
            
            # Get column names
            local_cursor.execute(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' 
                ORDER BY ordinal_position;
            """)
            columns = [row[0] for row in local_cursor.fetchall()]
            
            # Convert to list of dictionaries
            table_data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    value = row[i]
                    # Convert datetime objects to strings
                    if isinstance(value, datetime):
                        value = value.isoformat()
                    elif value is None:
                        value = None
                    else:
                        value = str(value)
                    row_dict[col] = value
                table_data.append(row_dict)
            
            exported_data[table] = {
                'columns': columns,
                'data': table_data,
                'count': len(table_data)
            }
            
            print(f"   ✅ Exported {len(table_data)} rows from {table}")
        
        local_cursor.close()
        local_conn.close()
        
        # Save to JSON file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = f"local_data_export_{timestamp}.json"
        
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(exported_data, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ Export completed successfully!")
        print(f"📁 File: {export_file}")
        print(f"📊 Total tables: {len(exported_data)}")
        
        # Show summary
        for table, info in exported_data.items():
            print(f"   - {table}: {info['count']} rows")
        
        return export_file
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return None

def import_to_railway(export_file):
    """Import data to Railway PostgreSQL"""
    print(f"\n🚀 Importing data to Railway PostgreSQL...")
    
    try:
        # Load exported data
        with open(export_file, 'r', encoding='utf-8') as f:
            exported_data = json.load(f)
        
        # Connect to Railway
        railway_conn = psycopg2.connect(RAILWAY_DB_URL)
        railway_cursor = railway_conn.cursor()
        
        for table_name, table_info in exported_data.items():
            print(f"📦 Importing table: {table_name}")
            
            columns = table_info['columns']
            data = table_info['data']
            
            if not data:
                print(f"   ⚠️ No data to import for {table_name}")
                continue
            
            # Clear existing data
            railway_cursor.execute(f"DELETE FROM {table_name};")
            print(f"   🗑️ Cleared existing data from {table_name}")
            
            # Insert new data
            for row_dict in data:
                # Create INSERT statement
                placeholders = ', '.join(['%s'] * len(columns))
                columns_str = ', '.join(columns)
                
                sql = f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"
                
                # Prepare values
                values = []
                for col in columns:
                    value = row_dict.get(col)
                    if value == 'None' or value == '':
                        value = None
                    values.append(value)
                
                try:
                    railway_cursor.execute(sql, values)
                except Exception as e:
                    print(f"   ⚠️ Error inserting row: {e}")
                    continue
            
            # Commit table changes
            railway_conn.commit()
            print(f"   ✅ Imported {len(data)} rows to {table_name}")
        
        railway_cursor.close()
        railway_conn.close()
        
        print(f"\n🎉 Import completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def verify_migration():
    """Verify data was migrated correctly"""
    print(f"\n🔍 Verifying migration...")
    
    try:
        # Check Railway database
        railway_conn = psycopg2.connect(RAILWAY_DB_URL)
        railway_cursor = railway_conn.cursor()
        
        # Check main tables
        tables_to_check = ['bookings', 'accommodations', 'monthly_reports']
        
        for table in tables_to_check:
            try:
                railway_cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = railway_cursor.fetchone()[0]
                print(f"   📊 {table}: {count} rows")
                
                if table == 'bookings' and count > 0:
                    # Show sample booking
                    railway_cursor.execute(f"SELECT guest_name, room_amount FROM {table} LIMIT 1;")
                    sample = railway_cursor.fetchone()
                    if sample:
                        print(f"      📋 Sample: {sample[0]} - {sample[1]}đ")
                        
            except Exception as e:
                print(f"   ❌ Error checking {table}: {e}")
        
        railway_cursor.close()
        railway_conn.close()
        
        return True
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    print("🏨 Hotel Booking System - Data Migration Tool")
    print("=" * 60)
    print("📊 LOCAL → RAILWAY PostgreSQL Migration")
    print("=" * 60)
    
    # Step 1: Export from local
    export_file = export_local_data()
    
    if not export_file:
        print("❌ Export failed. Cannot proceed with import.")
        exit(1)
    
    # Step 2: Import to Railway
    success = import_to_railway(export_file)
    
    if not success:
        print("❌ Import failed.")
        exit(1)
    
    # Step 3: Verify migration
    verify_migration()
    
    print("\n🎉 DATA MIGRATION COMPLETED!")
    print("🚀 Your Railway app should now have all your local data")
    print("🔗 Check your Railway app URL to verify the migration")