#!/usr/bin/env python3
"""
Test CRUD Operations for PostgreSQL Migration
"""

import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Load environment variables
load_dotenv(BASE_DIR / ".env")

def test_database_initialization():
    """Test database initialization and table creation"""
    print("=== Database Initialization Test ===")
    
    try:
        from flask import Flask
        from core.database_service_postgresql import init_database_service, get_database_service
        from core.models import create_all_tables, get_db_stats
        
        # Create Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database service
        with app.app_context():
            init_database_service(app)
            
            # Explicitly create tables
            create_all_tables(app)
            
            # Get database stats
            stats = get_db_stats(app)
            print(f"Database stats: {stats}")
            
        return True
        
    except Exception as e:
        print(f"ERROR: Database initialization failed - {str(e)}")
        return False

def test_guest_operations():
    """Test guest CRUD operations"""
    print("\n=== Guest CRUD Operations Test ===")
    
    try:
        from flask import Flask
        from core.database_service_postgresql import init_database_service, get_database_service
        from core.models import db, Guest
        
        # Create Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            init_database_service(app)
            
            # Check if test guest already exists
            existing_guest = db.session.query(Guest).filter_by(email="test@example.com").first()
            if existing_guest:
                # Delete existing test guest
                db.session.delete(existing_guest)
                db.session.commit()
            
            # Create test guest
            test_guest = Guest(
                full_name="Test User",
                email="test@example.com",
                phone="+1234567890",
                nationality="Test Country"
            )
            
            db.session.add(test_guest)
            db.session.commit()
            print(f"Created guest: {test_guest.full_name}")
            
            # Read guest
            found_guest = db.session.query(Guest).filter_by(email="test@example.com").first()
            if found_guest:
                print(f"Read guest: {found_guest.full_name}")
            else:
                raise Exception("Guest not found after creation")
            
            # Update guest
            found_guest.full_name = "Updated Test User"
            db.session.commit()
            print(f"Updated guest: {found_guest.full_name}")
            
            # Delete guest
            db.session.delete(found_guest)
            db.session.commit()
            print("Deleted test guest")
            
        return True
        
    except Exception as e:
        print(f"ERROR: Guest CRUD failed - {str(e)}")
        return False

def test_booking_operations():
    """Test booking CRUD operations"""
    print("\n=== Booking CRUD Operations Test ===")
    
    try:
        from flask import Flask
        from core.database_service_postgresql import init_database_service, get_database_service
        from core.models import db, Guest, Booking
        
        # Create Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            init_database_service(app)
            
            # Create test guest first
            test_guest = Guest(
                full_name="Booking Test User",
                email="booking_test@example.com",
                phone="+1234567890"
            )
            db.session.add(test_guest)
            db.session.flush()  # Get guest ID
            
            # Create test booking
            today = date.today()
            test_booking = Booking(
                booking_id="TEST001",
                guest_id=test_guest.guest_id,
                checkin_date=today,
                checkout_date=today + timedelta(days=2),
                room_amount=500000,
                commission=50000,
                taxi_amount=0,
                collector="Test Collector",
                booking_status="confirmed"
            )
            
            db.session.add(test_booking)
            db.session.commit()
            print(f"Created booking: {test_booking.booking_id}")
            
            # Read booking
            found_booking = db.session.query(Booking).filter_by(booking_id="TEST001").first()
            if found_booking:
                print(f"Read booking: {found_booking.booking_id}")
                print(f"Guest name: {found_booking.guest.full_name}")
            else:
                raise Exception("Booking not found after creation")
            
            # Update booking
            found_booking.room_amount = 600000
            db.session.commit()
            print(f"Updated booking amount: {found_booking.room_amount}")
            
            # Test soft delete
            found_booking.booking_status = 'deleted'
            db.session.commit()
            print("Soft deleted booking")
            
            # Cleanup
            db.session.delete(found_booking)
            db.session.delete(test_guest)
            db.session.commit()
            print("Cleaned up test data")
            
        return True
        
    except Exception as e:
        print(f"ERROR: Booking CRUD failed - {str(e)}")
        return False

def test_business_logic():
    """Test business logic functions"""
    print("\n=== Business Logic Test ===")
    
    try:
        from flask import Flask
        from core.database_service_postgresql import init_database_service
        from core.logic_postgresql import load_booking_data, create_demo_data
        
        # Create Flask app
        app = Flask(__name__)
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        with app.app_context():
            init_database_service(app)
            
            # Test creating demo data
            print("Creating demo data...")
            success = create_demo_data()
            if success:
                print("Demo data created successfully")
            
            # Test loading booking data
            print("Loading booking data...")
            df = load_booking_data()
            print(f"Loaded {len(df)} bookings")
            
            if not df.empty:
                # Convert column names to ASCII for display
                column_names = []
                for col in df.columns:
                    try:
                        column_names.append(col.encode('ascii', 'replace').decode('ascii'))
                    except:
                        column_names.append(col)
                print("Sample columns:", column_names)
                print("First booking available")
            
        return True
        
    except Exception as e:
        print(f"ERROR: Business logic test failed - {str(e)}")
        return False

def main():
    """Run all CRUD tests"""
    print("Starting CRUD Operations Test Suite\n")
    
    tests = [
        ("Database Initialization", test_database_initialization),
        ("Guest CRUD Operations", test_guest_operations),
        ("Booking CRUD Operations", test_booking_operations),
        ("Business Logic Functions", test_business_logic),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        success = test_func()
        results.append((test_name, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("CRUD OPERATIONS TEST SUMMARY")
    print('='*60)
    
    passed = 0
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("SUCCESS: All CRUD operations working correctly!")
        return True
    else:
        print("ERROR: Some CRUD operations failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)