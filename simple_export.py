#!/usr/bin/env python3
"""
Simple CSV export that doesn't require additional packages
"""

import os
import sys

def create_sql_dump():
    """Create SQL dump using pg_dump if available"""
    print("🔍 Attempting SQL dump...")
    
    # Try different pg_dump locations
    pg_dump_paths = [
        'pg_dump',
        '/usr/bin/pg_dump', 
        '/usr/local/bin/pg_dump',
        'C:\\Program Files\\PostgreSQL\\15\\bin\\pg_dump.exe',
        'C:\\Program Files\\PostgreSQL\\14\\bin\\pg_dump.exe',
        'C:\\Program Files\\PostgreSQL\\13\\bin\\pg_dump.exe',
    ]
    
    local_db = "postgresql://postgres:locloc123@localhost:5432/hotel_booking"
    
    for pg_dump in pg_dump_paths:
        try:
            import subprocess
            
            # Try to run pg_dump
            output_file = "local_data_dump.sql"
            cmd = [pg_dump, local_db, '-f', output_file]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ SQL dump created: {output_file}")
                return output_file
            else:
                print(f"❌ pg_dump failed: {result.stderr}")
                continue
                
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"❌ Error with {pg_dump}: {e}")
            continue
    
    print("❌ pg_dump not found or failed")
    return None

def manual_instructions():
    """Provide manual export instructions"""
    print("""
📋 MANUAL DATA EXPORT INSTRUCTIONS

Since automatic export requires packages not installed, here are manual options:

OPTION 1: Use pgAdmin (Recommended)
1. Open pgAdmin
2. Connect to local PostgreSQL (localhost:5432, user: postgres, password: locloc123)
3. Right-click hotel_booking database → Backup
4. Choose Custom format, save as hotel_booking_backup.backup
5. Use this file to restore to Railway

OPTION 2: Use psql command line
1. Open command prompt
2. Run: pg_dump -U postgres -h localhost -d hotel_booking > hotel_booking_dump.sql
3. Enter password: locloc123
4. Upload this SQL file to Railway

OPTION 3: Use Railway CLI (Easiest)
1. Install Railway CLI: npm install -g @railway/cli
2. Login: railway login
3. Connect to your project: railway link
4. Import data: railway run psql < hotel_booking_dump.sql

OPTION 4: Via Web Interface
1. Export your data via your local Flask app (http://localhost:5000)
2. Use any export feature in your booking system
3. Import via Railway Flask app bulk import

🎯 RAILWAY DATABASE CONNECTION:
postgresql://postgres:VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi@postgres.railway.internal:5432/railway
""")

if __name__ == "__main__":
    print("🏨 Simple Data Export Tool")
    print("=" * 40)
    
    # Try SQL dump first
    dump_file = create_sql_dump()
    
    if dump_file:
        print(f"\n✅ SUCCESS: {dump_file} created")
        print(f"📋 Next steps:")
        print(f"1. Upload this file to Railway using Railway CLI or pgAdmin")
        print(f"2. Restore to Railway PostgreSQL database")
        print(f"3. Verify data in your Railway app")
    else:
        print("\n⚠️ Automatic export failed")
        manual_instructions()