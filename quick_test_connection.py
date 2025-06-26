#!/usr/bin/env python3
"""
Quick PostgreSQL Connection Test
Test basic connection before full setup
"""

import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_basic_connection():
    """Test basic PostgreSQL connection"""
    
    # Get connection details from .env
    database_url = os.getenv('DATABASE_URL')
    print(f"🔗 Testing connection with: {database_url}")
    
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    try:
        # Test connection to default postgres database first
        postgres_url = database_url.replace('/hotel_booking', '/postgres')
        print(f"🧪 Testing default database: {postgres_url}")
        
        conn = psycopg2.connect(postgres_url)
        cursor = conn.cursor()
        
        # Test basic query
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Connected successfully!")
        print(f"📊 PostgreSQL version: {version}")
        
        # Check if hotel_booking database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'hotel_booking';")
        db_exists = cursor.fetchone()
        
        if db_exists:
            print("✅ hotel_booking database exists")
            
            # Test connection to hotel_booking database
            conn.close()
            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name;
            """)
            tables = cursor.fetchall()
            
            if tables:
                print(f"✅ Found {len(tables)} tables in hotel_booking database:")
                for table in tables:
                    print(f"   - {table[0]}")
            else:
                print("⚠️ hotel_booking database exists but has no tables")
                print("💡 You need to run the database_init.sql script in pgAdmin")
                
        else:
            print("❌ hotel_booking database does not exist")
            print("💡 Create it in pgAdmin 4:")
            print("   1. Right-click server → Create → Database")
            print("   2. Name: hotel_booking")
            print("   3. Then run database_init.sql script")
        
        conn.close()
        return True
        
    except psycopg2.OperationalError as e:
        print(f"❌ Connection failed: {e}")
        
        if "password authentication failed" in str(e):
            print("💡 Solution: Check your password in .env file")
        elif "could not connect to server" in str(e):
            print("💡 Solution: Make sure PostgreSQL service is running")
        elif "database" in str(e) and "does not exist" in str(e):
            print("💡 Solution: Create the database first")
            
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == '__main__':
    print("🧪 Quick PostgreSQL Connection Test")
    print("=" * 40)
    
    success = test_basic_connection()
    
    if success:
        print("\n🎉 Basic connection works!")
        print("📖 Next steps:")
        print("   1. Make sure hotel_booking database exists")
        print("   2. Run database_init.sql in pgAdmin")
        print("   3. Run: python test_postgresql_connection.py")
    else:
        print("\n❌ Connection failed. Check the error messages above.")