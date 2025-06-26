#!/usr/bin/env python3
"""
Simple PostgreSQL Connection Test
No Unicode characters - Windows compatible
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Load environment variables
load_dotenv(BASE_DIR / ".env")

def test_connection():
    """Test basic PostgreSQL connection"""
    print("=== PostgreSQL Connection Test ===")
    
    # Check environment variables
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not found in environment")
        return False
    
    print(f"DATABASE_URL configured: {database_url.split('@')[-1] if '@' in database_url else 'Invalid URL'}")
    
    try:
        # Test psycopg2 connection
        import psycopg2
        from urllib.parse import urlparse
        
        # Parse database URL
        parsed = urlparse(database_url)
        
        # Connect to PostgreSQL
        print("Testing psycopg2 connection...")
        conn = psycopg2.connect(
            host=parsed.hostname,
            port=parsed.port or 5432,
            database=parsed.path[1:] if parsed.path else '',
            user=parsed.username,
            password=parsed.password
        )
        
        # Test query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"SUCCESS: Connected to PostgreSQL")
        print(f"Version: {version[0][:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: Connection failed - {str(e)}")
        return False

def test_sqlalchemy_connection():
    """Test SQLAlchemy connection"""
    print("\n=== SQLAlchemy Connection Test ===")
    
    try:
        from sqlalchemy import create_engine, text
        
        database_url = os.getenv('DATABASE_URL')
        engine = create_engine(database_url)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test_value"))
            test_value = result.fetchone()
            print(f"SUCCESS: SQLAlchemy connection working")
            print(f"Test query result: {test_value[0]}")
            
        return True
        
    except Exception as e:
        print(f"ERROR: SQLAlchemy connection failed - {str(e)}")
        return False

def test_flask_app_setup():
    """Test Flask app initialization"""
    print("\n=== Flask App Setup Test ===")
    
    try:
        from flask import Flask
        from core.database_service_postgresql import init_database_service, get_database_service
        
        # Create Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database service
        with app.app_context():
            init_database_service(app)
            db_service = get_database_service()
            
            # Test health check
            health = db_service.get_health_status()
            print(f"SUCCESS: Flask app initialized")
            print(f"Health status: {health.get('status', 'Unknown')}")
            
        return True
        
    except Exception as e:
        print(f"ERROR: Flask app setup failed - {str(e)}")
        return False

def main():
    """Run all connection tests"""
    print("Starting PostgreSQL Migration Verification Tests\n")
    
    tests = [
        ("Basic Connection", test_connection),
        ("SQLAlchemy Connection", test_sqlalchemy_connection),
        ("Flask App Setup", test_flask_app_setup),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Running: {test_name}")
        print('='*50)
        success = test_func()
        results.append((test_name, success))
    
    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print('='*50)
    
    passed = 0
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("SUCCESS: All PostgreSQL tests passed!")
        return True
    else:
        print("ERROR: Some tests failed. Check configuration.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)