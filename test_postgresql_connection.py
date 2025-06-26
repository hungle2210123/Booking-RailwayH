#!/usr/bin/env python3
"""
PostgreSQL Connection Test Script
Test database connectivity and CRUD operations
"""

import os
import sys
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_database_connection():
    """Test basic PostgreSQL connection"""
    print("🔗 Testing PostgreSQL Connection...")
    
    try:
        from core.database_service_postgresql import get_database_service, init_database_service
        from core.models import db
        from flask import Flask
        
        # Create test Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database
        with app.app_context():
            init_database_service(app)
            db_service = get_database_service()
            
            # Test connection
            result = db_service.test_connection()
            
            if result['status'] == 'success':
                print("✅ PostgreSQL connection successful!")
                return True
            else:
                print(f"❌ Connection failed: {result['message']}")
                return False
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return False

def test_crud_operations():
    """Test Create, Read, Update, Delete operations"""
    print("\n📝 Testing CRUD Operations...")
    
    try:
        from core.database_service_postgresql import get_database_service
        from core.models import db
        from flask import Flask
        
        # Create test Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            db.init_app(app)
            db_service = get_database_service()
            
            # Test 1: Read all bookings
            print("📖 Testing READ operation...")
            bookings = db_service.get_all_bookings()
            print(f"✅ Found {len(bookings)} existing bookings")
            
            # Test 2: Create new booking
            print("➕ Testing CREATE operation...")
            test_booking = {
                'booking_id': f'TEST_{datetime.now().strftime("%Y%m%d_%H%M%S")}',
                'guest_name': 'Test Guest',
                'email': f'test_{datetime.now().strftime("%Y%m%d_%H%M%S")}@test.com',
                'phone': '0999999999',
                'checkin_date': date.today() + timedelta(days=1),
                'checkout_date': date.today() + timedelta(days=3),
                'room_amount': 500000,
                'commission': 50000,
                'taxi_amount': 0,
                'collector': 'Test System',
                'notes': 'Test booking - will be deleted'
            }
            
            create_result = db_service.create_booking(test_booking)
            if create_result['status'] == 'success':
                print(f"✅ Created test booking: {test_booking['booking_id']}")
                test_booking_id = test_booking['booking_id']
            else:
                print(f"❌ Create failed: {create_result['message']}")
                return False
            
            # Test 3: Update booking
            print("✏️ Testing UPDATE operation...")
            update_data = {
                'room_amount': 600000,
                'notes': 'Updated test booking'
            }
            
            update_result = db_service.update_booking(test_booking_id, update_data)
            if update_result['status'] == 'success':
                print(f"✅ Updated booking: {test_booking_id}")
            else:
                print(f"❌ Update failed: {update_result['message']}")
                return False
            
            # Test 4: Delete booking
            print("🗑️ Testing DELETE operation...")
            delete_result = db_service.delete_booking(test_booking_id)
            if delete_result['status'] == 'success':
                print(f"✅ Deleted test booking: {test_booking_id}")
            else:
                print(f"❌ Delete failed: {delete_result['message']}")
                return False
            
            print("✅ All CRUD operations successful!")
            return True
            
    except Exception as e:
        print(f"❌ CRUD test error: {e}")
        return False

def test_health_check():
    """Test database health status"""
    print("\n🏥 Testing Health Check...")
    
    try:
        from core.database_service_postgresql import get_database_service
        from flask import Flask
        
        # Create test Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            from core.database_service_postgresql import init_database_service
            init_database_service(app)
            db_service = get_database_service()
            
            health = db_service.get_health_status()
            
            print(f"📊 Health Status: {health['status']}")
            print(f"🗄️ Backend: {health['backend']}")
            
            if 'stats' in health:
                stats = health['stats']
                print(f"📈 Statistics:")
                print(f"   - Bookings: {stats.get('bookings', 'N/A')}")
                print(f"   - Guests: {stats.get('guests', 'N/A')}")
                print(f"   - Expenses: {stats.get('expenses', 'N/A')}")
            
            if health['status'] == 'healthy':
                print("✅ Database health check passed!")
                return True
            else:
                print(f"❌ Health check failed: {health.get('error', 'Unknown error')}")
                return False
                
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_performance():
    """Test database performance"""
    print("\n⚡ Testing Performance...")
    
    try:
        import time
        from core.database_service_postgresql import get_database_service, PerformanceTimer
        from flask import Flask
        
        # Create test Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            from core.database_service_postgresql import init_database_service
            init_database_service(app)
            db_service = get_database_service()
            
            # Test query performance
            start_time = time.time()
            bookings = db_service.get_all_bookings()
            end_time = time.time()
            
            duration_ms = (end_time - start_time) * 1000
            print(f"🚀 Query Performance:")
            print(f"   - Retrieved {len(bookings)} bookings")
            print(f"   - Time: {duration_ms:.1f}ms")
            
            if duration_ms < 500:  # Under 500ms is good
                print("✅ Performance test passed!")
                return True
            else:
                print("⚠️ Performance could be better (>500ms)")
                return True  # Still pass, just slower
                
    except Exception as e:
        print(f"❌ Performance test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 PostgreSQL Database Test Suite")
    print("=" * 50)
    
    # Check environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        print("📝 Please copy .env_postgresql.template to .env and configure your database")
        sys.exit(1)
    
    print(f"🗄️ Database URL: {database_url.split('@')[-1] if '@' in database_url else 'Invalid URL'}")
    
    # Run tests
    tests = [
        ("Connection Test", test_database_connection),
        ("CRUD Operations", test_crud_operations),
        ("Health Check", test_health_check),
        ("Performance Test", test_performance)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🔬 Running {test_name}...")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! PostgreSQL setup is working correctly.")
        print("\n📖 Next steps:")
        print("   1. Connect with pgAdmin 4 or DBeaver")
        print("   2. Run: python app_postgresql.py")
        print("   3. Visit: http://localhost:5000")
    else:
        print("⚠️ Some tests failed. Please check your PostgreSQL configuration.")
    
    return passed == len(tests)

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)