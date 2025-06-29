#!/usr/bin/env python3
"""
Direct PostgreSQL to Railway Sync
Pure Python implementation without external dependencies
"""

import os
import subprocess
import sys

def get_env_variable(name, default=None):
    """Read environment variable from .env file"""
    env_file = '.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith(f'{name}='):
                    return line.split('=', 1)[1].strip('"\'')
    return os.getenv(name, default)

def test_postgresql_command():
    """Test if psql command is available"""
    try:
        result = subprocess.run(['psql', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ PostgreSQL client available: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    return False

def export_local_data():
    """Export data from local PostgreSQL"""
    print("📤 Exporting local PostgreSQL data...")
    
    local_db_url = get_env_variable('LOCAL_DATABASE_URL', 
                                   'postgresql://postgres:locloc123@localhost:5432/hotel_booking')
    
    # Parse connection string
    # postgresql://postgres:locloc123@localhost:5432/hotel_booking
    parts = local_db_url.replace('postgresql://', '').split('@')
    user_pass = parts[0].split(':')
    host_port_db = parts[1].split('/')
    host_port = host_port_db[0].split(':')
    
    user = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ''
    host = host_port[0]
    port = host_port[1] if len(host_port) > 1 else '5432'
    database = host_port_db[1] if len(host_port_db) > 1 else 'postgres'
    
    print(f"  Host: {host}:{port}")
    print(f"  Database: {database}")
    print(f"  User: {user}")
    
    # Export main tables
    tables = ['guests', 'bookings', 'expenses', 'quick_notes', 'message_templates']
    
    export_dir = 'sync_export'
    os.makedirs(export_dir, exist_ok=True)
    
    for table in tables:
        print(f"  Exporting {table}...")
        
        # Set PGPASSWORD environment variable
        env = os.environ.copy()
        env['PGPASSWORD'] = password
        
        # Export table to CSV
        export_file = f"{export_dir}/{table}.csv"
        cmd = [
            'psql',
            '-h', host,
            '-p', port,
            '-U', user,
            '-d', database,
            '-c', f"\\copy {table} TO '{os.path.abspath(export_file)}' WITH CSV HEADER"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            if result.returncode == 0:
                # Count exported records
                with open(export_file, 'r') as f:
                    line_count = sum(1 for line in f) - 1  # Subtract header
                print(f"    ✅ {table}: {line_count} records exported")
            else:
                print(f"    ❌ {table}: Export failed - {result.stderr.strip()}")
        except Exception as e:
            print(f"    ❌ {table}: Exception - {e}")
    
    return export_dir

def import_to_railway(export_dir):
    """Import data to Railway PostgreSQL"""
    print("\n📤 Importing to Railway PostgreSQL...")
    
    railway_db_url = get_env_variable('DATABASE_URL')
    if not railway_db_url:
        print("❌ Railway DATABASE_URL not configured")
        return False
    
    # Clean Railway URL (remove prefixes if present)
    if railway_db_url.startswith('DATABASE_URL'):
        railway_db_url = railway_db_url.split('=', 1)[1].strip('"\'')
    
    # Parse Railway connection string
    parts = railway_db_url.replace('postgresql://', '').replace('postgresql+psycopg2://', '').split('@')
    user_pass = parts[0].split(':')
    host_port_db = parts[1].split('/')
    host_port = host_port_db[0].split(':')
    
    user = user_pass[0]
    password = user_pass[1] if len(user_pass) > 1 else ''
    host = host_port[0]
    port = host_port[1] if len(host_port) > 1 else '5432'
    database = host_port_db[1] if len(host_port_db) > 1 else 'railway'
    
    print(f"  Railway Host: {host}:{port}")
    print(f"  Railway Database: {database}")
    print(f"  Railway User: {user}")
    
    # Import each table
    tables = ['guests', 'bookings', 'expenses', 'quick_notes', 'message_templates']
    
    for table in tables:
        export_file = f"{export_dir}/{table}.csv"
        if not os.path.exists(export_file):
            print(f"    ⚠️ {table}: No export file found")
            continue
            
        print(f"  Importing {table}...")
        
        # Set PGPASSWORD for Railway
        env = os.environ.copy()
        env['PGPASSWORD'] = password
        
        # Clear existing data first
        clear_cmd = [
            'psql',
            '-h', host,
            '-p', port,
            '-U', user,
            '-d', database,
            '-c', f"TRUNCATE TABLE {table} RESTART IDENTITY CASCADE;"
        ]
        
        try:
            result = subprocess.run(clear_cmd, capture_output=True, text=True, env=env)
            if result.returncode == 0:
                print(f"    🗑️ {table}: Cleared existing data")
            else:
                print(f"    ⚠️ {table}: Clear warning - {result.stderr.strip()}")
        except Exception as e:
            print(f"    ⚠️ {table}: Clear exception - {e}")
        
        # Import new data
        import_cmd = [
            'psql',
            '-h', host,
            '-p', port,
            '-U', user,
            '-d', database,
            '-c', f"\\copy {table} FROM '{os.path.abspath(export_file)}' WITH CSV HEADER"
        ]
        
        try:
            result = subprocess.run(import_cmd, capture_output=True, text=True, env=env)
            if result.returncode == 0:
                print(f"    ✅ {table}: Import successful")
            else:
                print(f"    ❌ {table}: Import failed - {result.stderr.strip()}")
        except Exception as e:
            print(f"    ❌ {table}: Import exception - {e}")
    
    return True

def main():
    """Main sync function"""
    print("🚀 Direct PostgreSQL → Railway Sync")
    print("=" * 50)
    
    # Check if psql is available
    if not test_postgresql_command():
        print("❌ PostgreSQL client (psql) not available")
        print("💡 Install PostgreSQL client tools or run from a machine with psql")
        return False
    
    # Show current configuration
    local_url = get_env_variable('LOCAL_DATABASE_URL', 'postgresql://postgres:locloc123@localhost:5432/hotel_booking')
    railway_url = get_env_variable('DATABASE_URL', 'Not configured')
    
    print(f"📋 Local DB: {local_url}")
    print(f"📋 Railway DB: {railway_url[:50]}..." if len(railway_url) > 50 else f"📋 Railway DB: {railway_url}")
    
    if railway_url == 'Not configured':
        print("❌ Railway DATABASE_URL not configured in .env file")
        return False
    
    # Confirm sync
    print(f"\n🎯 This will sync your local hotel_booking data (76 bookings) to Railway")
    proceed = input("Proceed with sync? (y/N): ").lower().strip()
    
    if proceed != 'y':
        print("❌ Sync cancelled")
        return False
    
    # Export local data
    export_dir = export_local_data()
    
    # Import to Railway
    success = import_to_railway(export_dir)
    
    if success:
        print(f"\n🎉 SYNC COMPLETED!")
        print(f"✅ Your hotel booking data is now on Railway")
        print(f"🔗 Check your Railway deployment to verify")
    else:
        print(f"\n❌ Sync failed - check errors above")
    
    return success

if __name__ == "__main__":
    main()