#!/usr/bin/env python3
"""
Simple data export using built-in modules
"""

import os
import sys
import json
from datetime import datetime

# Simple environment variable reader
def load_env_file():
    """Load .env file manually"""
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key] = value
    except FileNotFoundError:
        print("❌ .env file not found")
    return env_vars

def test_connection():
    """Test if we can connect to local database"""
    env_vars = load_env_file()
    local_db_url = env_vars.get('LOCAL_DATABASE_URL')
    
    print(f"🔍 Checking local database connection...")
    print(f"📊 LOCAL_DATABASE_URL: {local_db_url[:50] if local_db_url else 'Not found'}...")
    
    if not local_db_url:
        print("❌ LOCAL_DATABASE_URL not found in .env")
        return False
    
    try:
        import psycopg2
        conn = psycopg2.connect(local_db_url)
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT COUNT(*) FROM bookings;")
        count = cursor.fetchone()[0]
        print(f"✅ Connection successful! Found {count} bookings")
        
        # Show sample data
        cursor.execute("SELECT guest_name, room_amount FROM bookings LIMIT 3;")
        samples = cursor.fetchall()
        
        print("📋 Sample bookings:")
        for guest_name, room_amount in samples:
            print(f"   - {guest_name}: {room_amount}đ")
        
        cursor.close()
        conn.close()
        return True
        
    except ImportError:
        print("❌ psycopg2 not available. Install with: pip install psycopg2-binary")
        return False
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    print("🏨 Hotel Booking System - Connection Test")
    print("=" * 50)
    
    success = test_connection()
    
    if success:
        print("\n✅ Your local database is accessible!")
        print("📋 Next: Install psycopg2-binary to export data")
        print("Command: pip install psycopg2-binary python-dotenv")
    else:
        print("\n❌ Cannot access local database")
        print("🔧 Troubleshooting:")
        print("1. Make sure PostgreSQL is running locally")
        print("2. Check .env file has correct LOCAL_DATABASE_URL")
        print("3. Install required packages: pip install psycopg2-binary")