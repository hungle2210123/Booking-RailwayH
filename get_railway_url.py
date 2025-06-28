#!/usr/bin/env python3
"""
Helper script to check Railway database connection
Run this with your Railway URL to verify it works
"""

import psycopg2
import sys

def test_railway_connection():
    print("🔍 Railway Database Connection Tester")
    print("=" * 40)
    
    railway_url = input("Enter your Railway PostgreSQL URL: ").strip()
    
    if not railway_url:
        print("❌ No URL provided")
        return
    
    if "localhost" in railway_url:
        print("⚠️  WARNING: This looks like a local URL, not Railway!")
        print("   Railway URLs should contain 'railway.app'")
        proceed = input("Continue anyway? (y/n): ").lower()
        if proceed != 'y':
            return
    
    try:
        print("🔌 Testing connection to Railway...")
        conn = psycopg2.connect(railway_url)
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]
        print(f"✅ Connection successful!")
        print(f"📊 PostgreSQL Version: {version}")
        
        # Check existing tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = cursor.fetchall()
        print(f"\n📋 Existing tables in Railway database:")
        
        if tables:
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                count = cursor.fetchone()[0]
                print(f"   - {table[0]}: {count} records")
        else:
            print("   No tables found (empty database)")
        
        cursor.close()
        conn.close()
        
        print(f"\n🎯 This Railway database is ready for sync!")
        
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Check Railway dashboard for correct DATABASE_URL")
        print("2. Ensure PostgreSQL service is running on Railway")
        print("3. Verify the URL format: postgresql://user:pass@host:port/db")

if __name__ == "__main__":
    test_railway_connection()