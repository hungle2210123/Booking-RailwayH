#!/usr/bin/env python3
"""
Debug CRUD Operations Test
Find exactly what's failing in CRUD operations
"""

import os
import sys
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def debug_crud_operations():
    """Debug CRUD operations step by step"""
    print("🔬 Debugging CRUD Operations...")
    
    try:
        from core.database_service_postgresql import get_database_service
        from core.models import db
        from flask import Flask
        
        # Create test Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            print("✅ Flask app context created")
            
            # Initialize database
            try:
                db.init_app(app)
                print("✅ Database initialized")
            except Exception as e:
                print(f"❌ Database init failed: {e}")
                return False
            
            # Get database service
            try:
                db_service = get_database_service()
                print("✅ Database service obtained")
            except Exception as e:
                print(f"❌ Database service failed: {e}")
                print("💡 Try: from core.database_service_postgresql import init_database_service")
                print("💡 Then: init_database_service(app)")
                
                # Try to initialize service
                try:
                    from core.database_service_postgresql import init_database_service
                    init_database_service(app)
                    db_service = get_database_service()
                    print("✅ Database service initialized and obtained")
                except Exception as e2:
                    print(f"❌ Service initialization failed: {e2}")
                    return False
            
            # Test 1: Read existing data
            print("\n📖 Testing READ operation...")
            try:
                bookings = db_service.get_all_bookings()
                print(f"✅ READ successful - Found {len(bookings)} bookings")
                
                if bookings:
                    sample_booking = bookings[0]
                    print(f"   Sample booking: {sample_booking.get('booking_id', 'No ID')} - {sample_booking.get('guest_name', 'No name')}")
                
            except Exception as e:
                print(f"❌ READ failed: {e}")
                print(f"   Error type: {type(e).__name__}")
                
                # Check if tables exist
                try:
                    with db.engine.connect() as conn:
                        result = conn.execute(db.text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))
                        tables = [row[0] for row in result]
                        print(f"   Available tables: {tables}")
                except Exception as e2:
                    print(f"   Cannot check tables: {e2}")
                
                return False
            
            # Test 2: Create new booking
            print("\n➕ Testing CREATE operation...")
            test_booking_id = f'TEST_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            test_booking = {
                'booking_id': test_booking_id,
                'guest_name': 'Debug Test Guest',
                'email': f'debug_{datetime.now().strftime("%Y%m%d_%H%M%S")}@test.com',
                'phone': '0999999999',
                'checkin_date': date.today() + timedelta(days=1),
                'checkout_date': date.today() + timedelta(days=3),
                'room_amount': 500000,
                'commission': 50000,
                'taxi_amount': 0,
                'collector': 'Debug System',
                'notes': 'Debug test booking - will be deleted'
            }
            
            try:
                create_result = db_service.create_booking(test_booking)
                if create_result['status'] == 'success':
                    print(f"✅ CREATE successful - Created booking: {test_booking_id}")
                else:
                    print(f"❌ CREATE failed: {create_result['message']}")
                    return False
            except Exception as e:
                print(f"❌ CREATE exception: {e}")
                print(f"   Error type: {type(e).__name__}")
                
                # Check if it's a database constraint issue
                if "foreign key" in str(e).lower():
                    print("   💡 Issue: Foreign key constraint - guest creation problem")
                elif "unique" in str(e).lower():
                    print("   💡 Issue: Unique constraint violation")
                elif "not null" in str(e).lower():
                    print("   💡 Issue: Required field missing")
                
                return False
            
            # Test 3: Update booking
            print("\n✏️ Testing UPDATE operation...")
            update_data = {
                'room_amount': 600000,
                'notes': 'Updated by debug test'
            }
            
            try:
                update_result = db_service.update_booking(test_booking_id, update_data)
                if update_result['status'] == 'success':
                    print(f"✅ UPDATE successful - Updated booking: {test_booking_id}")
                else:
                    print(f"❌ UPDATE failed: {update_result['message']}")
                    return False
            except Exception as e:
                print(f"❌ UPDATE exception: {e}")
                return False
            
            # Test 4: Delete booking
            print("\n🗑️ Testing DELETE operation...")
            try:
                delete_result = db_service.delete_booking(test_booking_id)
                if delete_result['status'] == 'success':
                    print(f"✅ DELETE successful - Deleted booking: {test_booking_id}")
                else:
                    print(f"❌ DELETE failed: {delete_result['message']}")
                    return False
            except Exception as e:
                print(f"❌ DELETE exception: {e}")
                return False
            
            print("\n🎉 All CRUD operations successful!")
            return True
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("💡 Check that all required modules are installed:")
        print("   pip install -r requirements_postgresql.txt")
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print(f"   Error type: {type(e).__name__}")
        return False

def check_database_tables():
    """Check if all required tables exist"""
    print("\n🔍 Checking Database Tables...")
    
    try:
        import psycopg2
        database_url = os.getenv('DATABASE_URL')
        
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Check for required tables
        required_tables = ['guests', 'bookings', 'expenses', 'quick_notes', 'message_templates', 'arrival_times']
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]
        
        print(f"📊 Found {len(existing_tables)} tables:")
        for table in existing_tables:
            print(f"   ✅ {table}")
        
        missing_tables = [table for table in required_tables if table not in existing_tables]
        if missing_tables:
            print(f"❌ Missing tables: {missing_tables}")
            print("💡 Run database_init.sql script in pgAdmin 4")
            return False
        
        # Check sample data
        cursor.execute("SELECT COUNT(*) FROM guests;")
        guest_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM bookings;")
        booking_count = cursor.fetchone()[0]
        
        print(f"📈 Data counts:")
        print(f"   Guests: {guest_count}")
        print(f"   Bookings: {booking_count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Table check failed: {e}")
        return False

def main():
    """Main debug function"""
    print("🐛 CRUD Operations Debug Tool")
    print("=" * 40)
    
    # Check environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in .env file")
        return False
    
    print(f"🗄️ Database: {database_url.split('@')[-1] if '@' in database_url else 'Invalid URL'}")
    
    # Check tables first
    tables_ok = check_database_tables()
    
    if not tables_ok:
        print("\n❌ Database tables issue detected")
        print("💡 Fix the tables first, then retry CRUD test")
        return False
    
    # Run CRUD debug
    crud_ok = debug_crud_operations()
    
    if crud_ok:
        print("\n🎉 CRUD operations working correctly!")
        print("💡 The original test should now pass")
    else:
        print("\n❌ CRUD operations failed")
        print("💡 Check the error messages above for solutions")
    
    return crud_ok

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)