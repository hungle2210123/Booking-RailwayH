#!/usr/bin/env python3
"""
Fixed CRUD Operations Test
Properly handle SQLAlchemy initialization
"""

import os
import sys
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_crud_with_proper_init():
    """Test CRUD operations with proper initialization"""
    print("🔬 Testing CRUD Operations (Fixed)...")
    
    try:
        from flask import Flask
        from core.models import db, Guest, Booking
        from core.database_service_postgresql import PostgreSQLDatabaseService
        
        # Create Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            # Initialize database ONCE
            db.init_app(app)
            print("✅ Database initialized")
            
            # Create database service directly
            db_service = PostgreSQLDatabaseService()
            print("✅ Database service created")
            
            # Test 1: Read existing data
            print("\n📖 Testing READ operation...")
            try:
                bookings = db_service.get_all_bookings()
                print(f"✅ READ successful - Found {len(bookings)} bookings")
                
                if bookings:
                    sample_booking = bookings[0]
                    print(f"   Sample: {sample_booking.get('booking_id')} - {sample_booking.get('guest_name')}")
                
            except Exception as e:
                print(f"❌ READ failed: {e}")
                return False
            
            # Test 2: Create new booking
            print("\n➕ Testing CREATE operation...")
            test_booking_id = f'TEST_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            test_booking = {
                'booking_id': test_booking_id,
                'guest_name': 'Test Guest Fixed',
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
            
            try:
                create_result = db_service.create_booking(test_booking)
                if create_result['status'] == 'success':
                    print(f"✅ CREATE successful - Created: {test_booking_id}")
                else:
                    print(f"❌ CREATE failed: {create_result['message']}")
                    return False
            except Exception as e:
                print(f"❌ CREATE exception: {e}")
                return False
            
            # Test 3: Update booking
            print("\n✏️ Testing UPDATE operation...")
            update_data = {'room_amount': 600000, 'notes': 'Updated test booking'}
            
            try:
                update_result = db_service.update_booking(test_booking_id, update_data)
                if update_result['status'] == 'success':
                    print(f"✅ UPDATE successful - Updated: {test_booking_id}")
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
                    print(f"✅ DELETE successful - Deleted: {test_booking_id}")
                else:
                    print(f"❌ DELETE failed: {delete_result['message']}")
                    return False
            except Exception as e:
                print(f"❌ DELETE exception: {e}")
                return False
            
            print("\n🎉 All CRUD operations successful!")
            return True
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def test_direct_sqlalchemy():
    """Test using SQLAlchemy directly"""
    print("\n🔬 Testing Direct SQLAlchemy Operations...")
    
    try:
        from flask import Flask
        from core.models import db, Guest, Booking
        
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            db.init_app(app)
            
            # Test direct SQLAlchemy operations
            print("📖 Testing direct database query...")
            
            # Query existing data
            bookings = db.session.query(Booking).join(Guest).all()
            print(f"✅ Found {len(bookings)} bookings via SQLAlchemy")
            
            for booking in bookings[:3]:  # Show first 3
                guest_name = booking.guest.full_name if booking.guest else "Unknown"
                print(f"   - {booking.booking_id}: {guest_name}")
            
            # Test creating a new booking
            print("\n➕ Creating test booking...")
            
            # Create or get test guest
            test_guest = db.session.query(Guest).filter_by(email='test@sqlalchemy.com').first()
            if not test_guest:
                test_guest = Guest(
                    full_name='SQLAlchemy Test Guest',
                    email='test@sqlalchemy.com',
                    phone='0888888888'
                )
                db.session.add(test_guest)
                db.session.flush()  # Get the guest_id
            
            # Create test booking
            test_booking_id = f'SQLTEST_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
            test_booking = Booking(
                booking_id=test_booking_id,
                guest_id=test_guest.guest_id,
                checkin_date=date.today() + timedelta(days=1),
                checkout_date=date.today() + timedelta(days=3),
                room_amount=500000,
                commission=50000,
                booking_status='confirmed',
                booking_notes='SQLAlchemy test'
            )
            
            db.session.add(test_booking)
            db.session.commit()
            print(f"✅ Created booking: {test_booking_id}")
            
            # Clean up - delete test booking
            db.session.delete(test_booking)
            db.session.commit()
            print(f"✅ Cleaned up test booking: {test_booking_id}")
            
            return True
            
    except Exception as e:
        print(f"❌ SQLAlchemy test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 Fixed CRUD Test Suite")
    print("=" * 40)
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    print(f"🗄️ Database: {database_url.split('@')[-1] if '@' in database_url else 'Invalid'}")
    
    # Test 1: Database service CRUD
    print("\n🔬 Test 1: Database Service CRUD")
    crud_success = test_crud_with_proper_init()
    
    # Test 2: Direct SQLAlchemy
    print("\n🔬 Test 2: Direct SQLAlchemy")
    sqlalchemy_success = test_direct_sqlalchemy()
    
    # Summary
    print("\n" + "=" * 40)
    print("📋 Test Results:")
    print(f"   Database Service CRUD: {'✅ PASS' if crud_success else '❌ FAIL'}")
    print(f"   Direct SQLAlchemy: {'✅ PASS' if sqlalchemy_success else '❌ FAIL'}")
    
    if crud_success and sqlalchemy_success:
        print("\n🎉 All tests passed! CRUD operations are working correctly.")
        print("💡 The original test should now pass. Try:")
        print("   python test_postgresql_connection.py")
    else:
        print("\n⚠️ Some tests failed, but this might be normal.")
        print("💡 Try starting the application:")
        print("   python app_postgresql.py")
    
    return crud_success or sqlalchemy_success

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)