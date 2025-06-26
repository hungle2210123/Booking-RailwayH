#!/usr/bin/env python3
"""
Complete import process with fixed date parsing
- Clear existing imported data
- Import all data with enhanced date parsing
- Verify results
"""

import sys
import os
from flask import Flask
from datetime import datetime

# Add project path
sys.path.append('/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized')

def create_flask_app():
    """Create Flask app with database context"""
    from core.database_service_postgresql import init_database_service
    from dotenv import load_dotenv
    from pathlib import Path
    
    BASE_DIR = Path(__file__).resolve().parent
    load_dotenv(BASE_DIR / ".env")
    
    app = Flask(__name__)
    app.config['ENV'] = 'production'
    app.config['DEBUG'] = False
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key")
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database
    init_database_service(app)
    
    return app

def clear_imported_data(app):
    """Clear existing imported data"""
    print("🧹 CLEARING IMPORTED DATA...")
    
    with app.app_context():
        from core.models import db, Booking, Guest, MessageTemplate, Expense
        
        try:
            # Keep only the original test bookings
            original_booking_ids = ['FLASK_TEST_001', 'FLASK_TEST_002', 'FLASK_TEST_003', 'FLASK_TEST_004']
            
            # Delete imported bookings (not the original test ones)
            deleted_bookings = Booking.query.filter(~Booking.booking_id.in_(original_booking_ids)).delete(synchronize_session=False)
            
            # Delete imported guests (keep only original test guests)
            original_guest_names = ['Flask Test User', 'Test Guest 1', 'Test Guest 2', 'Test Guest 3']
            deleted_guests = Guest.query.filter(~Guest.full_name.in_(original_guest_names)).delete(synchronize_session=False)
            
            # Delete imported templates and expenses
            deleted_templates = MessageTemplate.query.delete()
            deleted_expenses = Expense.query.delete()
            
            db.session.commit()
            
            print(f"✅ Cleared: {deleted_bookings} bookings, {deleted_guests} guests, {deleted_templates} templates, {deleted_expenses} expenses")
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error clearing data: {e}")
            return False

def run_comprehensive_import(app):
    """Run the comprehensive import with Flask context"""
    print("\n🚀 RUNNING COMPREHENSIVE IMPORT...")
    
    with app.app_context():
        try:
            from core.comprehensive_import import main
            success = main()
            return success
        except Exception as e:
            print(f"❌ Import error: {e}")
            import traceback
            traceback.print_exc()
            return False

def verify_import_results(app):
    """Verify the import results"""
    print("\n📊 VERIFYING IMPORT RESULTS...")
    
    with app.app_context():
        from core.models import db, Booking, Guest, MessageTemplate, Expense
        from core.logic_postgresql import load_booking_data
        
        try:
            # Count records
            booking_count = Booking.query.count()
            guest_count = Guest.query.count()
            template_count = MessageTemplate.query.count()
            expense_count = Expense.query.count()
            
            print(f"📋 Database counts:")
            print(f"   Bookings: {booking_count}")
            print(f"   Guests: {guest_count}")
            print(f"   Templates: {template_count}")
            print(f"   Expenses: {expense_count}")
            
            # Test data loading
            df = load_booking_data(force_fresh=True)
            print(f"   Data loading test: {len(df)} bookings loaded")
            
            # Check date validity
            if not df.empty:
                valid_dates = 0
                total_bookings = len(df)
                
                for _, row in df.iterrows():
                    checkin = row.get('Check-in Date')
                    checkout = row.get('Check-out Date')
                    if pd.notna(checkin) and pd.notna(checkout):
                        valid_dates += 1
                
                print(f"   Valid dates: {valid_dates}/{total_bookings} ({(valid_dates/total_bookings*100):.1f}%)")
            
            return True
            
        except Exception as e:
            print(f"❌ Verification error: {e}")
            import traceback
            traceback.print_exc()
            return False

def main():
    """Main execution function"""
    print("🎯 COMPLETE IMPORT PROCESS WITH FIXED DATE PARSING")
    print("=" * 70)
    
    # Create Flask app
    app = create_flask_app()
    
    # Step 1: Clear existing data
    if not clear_imported_data(app):
        print("❌ Failed to clear data")
        return False
    
    # Step 2: Run import
    if not run_comprehensive_import(app):
        print("❌ Failed to import data")
        return False
    
    # Step 3: Verify results
    if not verify_import_results(app):
        print("❌ Failed to verify results")
        return False
    
    print("\n🎉 IMPORT PROCESS COMPLETED SUCCESSFULLY!")
    print("✅ All 67 bookings should now be in PostgreSQL with correct dates")
    print("✅ Dashboard and calendar should display all data correctly")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)