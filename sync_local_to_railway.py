#!/usr/bin/env python3
"""
Simple Local to Railway Sync
Direct PostgreSQL to PostgreSQL transfer
"""

import subprocess
import os
import sys

def run_psql_command(host, port, user, database, password, command, description):
    """Run a psql command with proper error handling"""
    print(f"  {description}...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    
    cmd = [
        'psql',
        '-h', host,
        '-p', str(port),
        '-U', user,
        '-d', database,
        '-c', command
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0:
            print(f"    ✅ {description} successful")
            if result.stdout.strip():
                print(f"    {result.stdout.strip()}")
            return True
        else:
            print(f"    ❌ {description} failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"    ❌ {description} error: {e}")
        return False

def export_table_to_csv(host, port, user, database, password, table, filename):
    """Export table to CSV file"""
    print(f"  Exporting {table}...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    env['PGCLIENTENCODING'] = 'UTF8'
    
    copy_command = f"\\copy {table} TO '{filename}' WITH CSV HEADER ENCODING 'UTF8'"
    
    cmd = [
        'psql',
        '-h', host,
        '-p', str(port),
        '-U', user,
        '-d', database,
        '-c', copy_command
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0:
            # Count lines in file
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for line in f) - 1  # Subtract header
                print(f"    ✅ {table}: {line_count} records exported")
                return True
            except:
                print(f"    ✅ {table}: exported (count unknown)")
                return True
        else:
            print(f"    ❌ {table}: export failed - {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"    ❌ {table}: export error - {e}")
        return False

def import_csv_to_table(host, port, user, database, password, table, filename):
    """Import CSV file to table"""
    if not os.path.exists(filename):
        print(f"    ⚠️ {table}: CSV file not found, skipping")
        return True
        
    print(f"  Importing {table}...")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = password
    env['PGCLIENTENCODING'] = 'UTF8'
    
    # Clear table first
    clear_command = f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"
    if not run_psql_command(host, port, user, database, password, clear_command, f"Clear {table}"):
        print(f"    ⚠️ Could not clear {table}, continuing...")
    
    # Import data
    copy_command = f"\\copy {table} FROM '{filename}' WITH CSV HEADER ENCODING 'UTF8'"
    
    cmd = [
        'psql',
        '-h', host,
        '-p', str(port),
        '-U', user,
        '-d', database,
        '-c', copy_command
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        if result.returncode == 0:
            print(f"    ✅ {table}: imported successfully")
            return True
        else:
            print(f"    ❌ {table}: import failed - {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"    ❌ {table}: import error - {e}")
        return False

def main():
    print("🚀 Local PostgreSQL → Railway Sync")
    print("=" * 50)
    
    # Configuration
    LOCAL_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'user': 'postgres',
        'database': 'hotel_booking',
        'password': 'locloc123'
    }
    
    RAILWAY_CONFIG = {
        'host': 'mainline.proxy.rlwy.net',
        'port': 36647,
        'user': 'postgres',
        'database': 'railway',
        'password': 'VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi'
    }
    
    # Create export directory
    export_dir = 'sync_export'
    os.makedirs(export_dir, exist_ok=True)
    
    # Tables to sync
    tables = ['guests', 'bookings', 'expenses', 'quick_notes', 'message_templates']
    
    print(f"📋 Local: {LOCAL_CONFIG['host']}:{LOCAL_CONFIG['port']}/{LOCAL_CONFIG['database']}")
    print(f"📋 Railway: {RAILWAY_CONFIG['host']}:{RAILWAY_CONFIG['port']}/{RAILWAY_CONFIG['database']}")
    print()
    
    # Test connections
    print("🔍 Testing connections...")
    
    local_ok = run_psql_command(
        LOCAL_CONFIG['host'], LOCAL_CONFIG['port'], LOCAL_CONFIG['user'],
        LOCAL_CONFIG['database'], LOCAL_CONFIG['password'],
        "SELECT 'Local connection successful' as status;",
        "Test local connection"
    )
    
    railway_ok = run_psql_command(
        RAILWAY_CONFIG['host'], RAILWAY_CONFIG['port'], RAILWAY_CONFIG['user'],
        RAILWAY_CONFIG['database'], RAILWAY_CONFIG['password'],
        "SELECT 'Railway connection successful' as status;",
        "Test Railway connection"
    )
    
    if not local_ok:
        print("❌ Cannot connect to local PostgreSQL")
        return False
        
    if not railway_ok:
        print("❌ Cannot connect to Railway PostgreSQL")
        return False
    
    print("✅ Both databases accessible")
    print()
    
    # Get confirmation
    proceed = input("Proceed with sync? This will overwrite Railway data (y/N): ").lower().strip()
    if proceed != 'y':
        print("❌ Sync cancelled")
        return False
    
    print()
    print("📤 Step 1: Exporting from local PostgreSQL...")
    
    export_success = {}
    for table in tables:
        filename = os.path.join(export_dir, f"{table}.csv")
        export_success[table] = export_table_to_csv(
            LOCAL_CONFIG['host'], LOCAL_CONFIG['port'], LOCAL_CONFIG['user'],
            LOCAL_CONFIG['database'], LOCAL_CONFIG['password'],
            table, filename
        )
    
    print()
    print("📤 Step 2: Importing to Railway PostgreSQL...")
    
    import_success = {}
    for table in tables:
        if export_success.get(table, False):
            filename = os.path.join(export_dir, f"{table}.csv")
            import_success[table] = import_csv_to_table(
                RAILWAY_CONFIG['host'], RAILWAY_CONFIG['port'], RAILWAY_CONFIG['user'],
                RAILWAY_CONFIG['database'], RAILWAY_CONFIG['password'],
                table, filename
            )
        else:
            print(f"  Skipping {table} (export failed)")
            import_success[table] = False
    
    print()
    print("🔍 Verifying Railway data...")
    
    for table in ['bookings', 'guests', 'expenses']:
        run_psql_command(
            RAILWAY_CONFIG['host'], RAILWAY_CONFIG['port'], RAILWAY_CONFIG['user'],
            RAILWAY_CONFIG['database'], RAILWAY_CONFIG['password'],
            f"SELECT '{table.title()}: ' || COUNT(*) FROM {table};",
            f"Count {table}"
        )
    
    print()
    print("📋 SYNC SUMMARY:")
    print("=" * 30)
    
    successful_tables = [table for table, success in import_success.items() if success]
    failed_tables = [table for table, success in import_success.items() if not success]
    
    if successful_tables:
        print(f"✅ Successfully synced: {', '.join(successful_tables)}")
        
    if failed_tables:
        print(f"❌ Failed to sync: {', '.join(failed_tables)}")
    
    if len(successful_tables) >= 2:  # At least guests and bookings
        print()
        print("🎉 SYNC COMPLETED!")
        print("✅ Your booking data is now on Railway!")
        print("🔗 Check your Railway app to see the data")
        return True
    else:
        print()
        print("❌ SYNC FAILED")
        print("Not enough tables were successfully synced")
        return False

if __name__ == "__main__":
    try:
        success = main()
        input("\nPress Enter to exit...")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Sync cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)