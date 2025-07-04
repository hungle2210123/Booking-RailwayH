#!/usr/bin/env python3
"""
Export local PostgreSQL data to SQL file for Render import
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

try:
    import psycopg2
    import json
except ImportError:
    print("❌ Missing required packages. Install with:")
    print("pip install psycopg2-binary python-dotenv")
    sys.exit(1)

def export_local_data():
    """Export local PostgreSQL data to SQL file"""
    
    # Get local database URL
    local_db_url = os.getenv('LOCAL_DATABASE_URL')
    if not local_db_url:
        print("❌ LOCAL_DATABASE_URL not found in .env file")
        return False
    
    print(f"🔗 Connecting to local database...")
    print(f"📊 Database: {local_db_url[:50]}...")
    
    try:
        # Connect to local PostgreSQL
        conn = psycopg2.connect(local_db_url)
        cursor = conn.cursor()
        
        # Export filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_file = f"local_data_export_{timestamp}.sql"
        
        print(f"📁 Exporting to: {export_file}")
        
        with open(export_file, 'w', encoding='utf-8') as f:
            # Write header
            f.write("-- Hotel Booking System Data Export\n")
            f.write(f"-- Exported: {datetime.now()}\n")
            f.write(f"-- Source: Local PostgreSQL\n\n")
            
            # Get all table names
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE';
            """)
            
            tables = cursor.fetchall()
            print(f"📋 Found {len(tables)} tables")
            
            for (table_name,) in tables:
                print(f"📦 Exporting table: {table_name}")
                
                # Get table structure
                cursor.execute(f"""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}' 
                    ORDER BY ordinal_position;
                """)
                
                columns = cursor.fetchall()
                
                # Get table data
                cursor.execute(f"SELECT * FROM {table_name};")
                rows = cursor.fetchall()
                
                if rows:
                    f.write(f"\n-- Table: {table_name} ({len(rows)} rows)\n")
                    
                    # Create column list for INSERT
                    column_names = [col[0] for col in columns]
                    columns_str = ', '.join(column_names)
                    
                    # Write INSERT statements
                    for row in rows:
                        # Format values for SQL
                        formatted_values = []
                        for i, value in enumerate(row):
                            if value is None:
                                formatted_values.append('NULL')
                            elif isinstance(value, str):
                                # Escape quotes
                                escaped_value = value.replace("'", "''")
                                formatted_values.append(f"'{escaped_value}'")
                            elif isinstance(value, datetime):
                                formatted_values.append(f"'{value}'")
                            else:
                                formatted_values.append(str(value))
                        
                        values_str = ', '.join(formatted_values)
                        f.write(f"INSERT INTO {table_name} ({columns_str}) VALUES ({values_str});\n")
                
                else:
                    f.write(f"\n-- Table: {table_name} (empty)\n")
        
        cursor.close()
        conn.close()
        
        print(f"✅ Export completed successfully!")
        print(f"📁 File: {export_file}")
        print(f"📊 File size: {os.path.getsize(export_file)} bytes")
        
        return export_file
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        return False

def export_to_json():
    """Export to JSON format as backup"""
    local_db_url = os.getenv('LOCAL_DATABASE_URL')
    if not local_db_url:
        return False
        
    try:
        conn = psycopg2.connect(local_db_url)
        cursor = conn.cursor()
        
        # Export bookings to JSON
        cursor.execute("SELECT * FROM bookings;")
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        
        bookings_data = []
        for row in rows:
            booking = dict(zip(columns, row))
            # Convert datetime objects to strings
            for key, value in booking.items():
                if isinstance(value, datetime):
                    booking[key] = value.isoformat()
            bookings_data.append(booking)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_file = f"bookings_backup_{timestamp}.json"
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(bookings_data, f, indent=2, ensure_ascii=False)
        
        cursor.close()
        conn.close()
        
        print(f"✅ JSON backup created: {json_file}")
        print(f"📊 Exported {len(bookings_data)} bookings")
        
        return json_file
        
    except Exception as e:
        print(f"❌ JSON export failed: {e}")
        return False

if __name__ == "__main__":
    print("🏨 Hotel Booking System - Data Export Tool")
    print("=" * 50)
    
    # Export to SQL
    sql_file = export_local_data()
    
    # Export to JSON as backup
    json_file = export_to_json()
    
    if sql_file:
        print("\n📋 Next Steps:")
        print("1. Complete Render deployment setup")
        print("2. Get Render PostgreSQL connection string")
        print(f"3. Import {sql_file} to Render database")
        print("4. Verify data in Render deployment")
    else:
        print("\n❌ Export failed. Check your local PostgreSQL connection.")