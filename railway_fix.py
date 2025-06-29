#!/usr/bin/env python3
"""
Railway Deployment Fix
Handles database setup and data sync for Railway deployment
"""

import os
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def fix_railway_deployment():
    """Fix all Railway deployment issues"""
    print("🚀 Railway Deployment Fix Tool")
    print("=" * 50)
    
    try:
        # Import required modules
        from core.database_service_postgresql import get_database_service
        from core.models import db, Booking, Guest, Expense
        from flask import Flask
        from dotenv import load_dotenv
        
        # Load environment variables
        load_dotenv()
        
        # Create Flask app for database context
        app = Flask(__name__)
        
        # Get database URL
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found in environment")
            return False
            
        print(f"📋 Database URL: {database_url[:50]}...")
        
        # Configure database
        app.config['SQLALCHEMY_DATABASE_URI'] = database_url
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database
        db.init_app(app)
        
        with app.app_context():
            print("🔄 Creating database tables...")
            
            # Create all tables
            db.create_all()
            print("✅ Database tables created successfully")
            
            # Check existing data
            booking_count = Booking.query.count()
            guest_count = Guest.query.count()
            
            print(f"📊 Current data in Railway:")
            print(f"   - Bookings: {booking_count}")
            print(f"   - Guests: {guest_count}")
            
            if booking_count == 0:
                print("⚠️ No bookings found in Railway database")
                print("💡 Use the dashboard sync button to import your data")
            else:
                print("✅ Data found in Railway database")
                
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def check_environment_variables():
    """Check Railway environment variables"""
    print("\n🔍 Checking Environment Variables")
    print("=" * 50)
    
    required_vars = [
        'DATABASE_URL',
        'FLASK_SECRET_KEY',
        'GOOGLE_API_KEY'
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {value[:20]}...")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️ Missing variables: {', '.join(missing_vars)}")
        print("💡 Set these in Railway Dashboard → Variables")
        return False
    
    print("✅ All required environment variables are set")
    return True

def create_sample_data():
    """Create sample data if database is empty"""
    print("\n🎯 Creating Sample Data")
    print("=" * 50)
    
    try:
        from core.database_service_postgresql import get_database_service
        
        db_service = get_database_service()
        
        # Create a sample booking
        sample_guest = {
            'full_name': 'Railway Test Guest',
            'email': 'test@railway.app',
            'phone': '+84123456789'
        }
        
        sample_booking = {
            'booking_id': 'RAILWAY_TEST_001',
            'checkin_date': '2025-06-29',
            'checkout_date': '2025-06-30',
            'room_amount': 500000,
            'commission': 50000,
            'guest_name': 'Railway Test Guest'
        }
        
        # Check if test data already exists
        existing_booking = db_service.get_booking_by_id('RAILWAY_TEST_001')
        
        if not existing_booking:
            print("📝 Creating test booking...")
            # Add guest first
            guest_id = db_service.add_guest(sample_guest)
            sample_booking['guest_id'] = guest_id
            
            # Add booking
            booking_id = db_service.add_booking(sample_booking)
            
            print(f"✅ Created test booking: {booking_id}")
            print("🎯 Railway deployment is working!")
        else:
            print("ℹ️ Test data already exists")
            
        return True
        
    except Exception as e:
        print(f"❌ Error creating sample data: {e}")
        return False

def main():
    """Main fix function"""
    print("🔧 Railway Deployment Complete Fix")
    print("=" * 60)
    
    # Step 1: Check environment variables
    env_ok = check_environment_variables()
    
    if not env_ok:
        print("\n❌ Environment variables not properly configured")
        print("🔧 SOLUTION:")
        print("1. Go to Railway Dashboard → Your Project → Variables")
        print("2. Set: DATABASE_URL=${{Postgres.DATABASE_URL}}")
        print("3. Set: FLASK_SECRET_KEY=hotel_booking_secret_2024_railway_production")
        print("4. Set: GOOGLE_API_KEY=AIzaSyCcVHV8mdeee1cjZ4D0te5XlyrJAyQxGR4")
        return False
    
    # Step 2: Fix database
    db_ok = fix_railway_deployment()
    
    if not db_ok:
        print("\n❌ Database setup failed")
        return False
    
    # Step 3: Create sample data
    sample_ok = create_sample_data()
    
    print("\n🎉 RAILWAY FIX COMPLETED!")
    print("=" * 50)
    
    if db_ok and sample_ok:
        print("✅ Database connection working")
        print("✅ Tables created successfully")
        print("✅ Sample data added")
        print("🔗 Your Railway app should now work!")
        print("\n💡 NEXT STEPS:")
        print("1. Visit your Railway app URL")
        print("2. Use 'Sync Data' button to import your 76 bookings")
        print("3. Verify all data displays correctly")
    
    return True

if __name__ == "__main__":
    main()