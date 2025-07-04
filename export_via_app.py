#!/usr/bin/env python3
"""
Export data using your existing Flask app infrastructure
"""

import sys
import os
import json
from datetime import datetime

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from core.models import db, Booking, Accommodation
    from flask import Flask
    import pandas as pd
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("🔧 Make sure you're in the right directory and have installed requirements")
    sys.exit(1)

def setup_app():
    """Setup Flask app with local database"""
    app = Flask(__name__)
    
    # Use local database configuration
    local_db_url = "postgresql://postgres:locloc123@localhost:5432/hotel_booking"
    app.config['SQLALCHEMY_DATABASE_URI'] = local_db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    db.init_app(app)
    return app

def export_to_csv():
    """Export bookings to CSV for easy import"""
    app = setup_app()
    
    with app.app_context():
        try:
            # Get all bookings
            bookings = Booking.query.all()
            print(f"📊 Found {len(bookings)} bookings to export")
            
            if not bookings:
                print("⚠️ No bookings found in local database")
                return False
            
            # Convert to list of dictionaries
            booking_data = []
            for booking in bookings:
                booking_dict = {
                    'booking_id': booking.booking_id,
                    'guest_name': booking.guest_name,
                    'email': booking.email or '',
                    'phone': booking.phone or '',
                    'checkin_date': booking.checkin_date,
                    'checkout_date': booking.checkout_date,
                    'room_amount': float(booking.room_amount or 0),
                    'taxi_amount': float(booking.taxi_amount or 0),
                    'commission': float(booking.commission or 0),
                    'collected_amount': float(booking.collected_amount or 0),
                    'collector': booking.collector or '',
                    'note': booking.note or '',
                    'status': booking.status or 'active',
                    'created_at': booking.created_at,
                    'updated_at': booking.updated_at
                }
                booking_data.append(booking_dict)
            
            # Create CSV file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_file = f"local_bookings_export_{timestamp}.csv"
            
            # Convert to DataFrame and save
            df = pd.DataFrame(booking_data)
            df.to_csv(csv_file, index=False, encoding='utf-8')
            
            print(f"✅ CSV export completed!")
            print(f"📁 File: {csv_file}")
            print(f"📊 Exported {len(booking_data)} bookings")
            
            # Show sample data
            print("\n📋 Sample exported data:")
            print(df[['guest_name', 'room_amount', 'checkin_date']].head(3).to_string())
            
            return csv_file
            
        except Exception as e:
            print(f"❌ Export failed: {e}")
            return False

def export_to_sql_insert():
    """Export as SQL INSERT statements"""
    app = setup_app()
    
    with app.app_context():
        try:
            bookings = Booking.query.all()
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            sql_file = f"local_bookings_insert_{timestamp}.sql"
            
            with open(sql_file, 'w', encoding='utf-8') as f:
                f.write("-- Hotel Booking System Data Export\n")
                f.write(f"-- Exported: {datetime.now()}\n")
                f.write(f"-- Total bookings: {len(bookings)}\n\n")
                
                for booking in bookings:
                    # Create INSERT statement
                    sql = f"""INSERT INTO bookings (
    booking_id, guest_name, email, phone, checkin_date, checkout_date,
    room_amount, taxi_amount, commission, collected_amount, collector, note, status
) VALUES (
    '{booking.booking_id or ""}',
    '{(booking.guest_name or "").replace("'", "''")}',
    '{booking.email or ""}',
    '{booking.phone or ""}',
    '{booking.checkin_date}',
    '{booking.checkout_date}',
    {booking.room_amount or 0},
    {booking.taxi_amount or 0},
    {booking.commission or 0},
    {booking.collected_amount or 0},
    '{booking.collector or ""}',
    '{(booking.note or "").replace("'", "''")}',
    '{booking.status or "active"}'
);

"""
                    f.write(sql)
            
            print(f"✅ SQL export completed!")
            print(f"📁 File: {sql_file}")
            print(f"📊 Exported {len(bookings)} INSERT statements")
            
            return sql_file
            
        except Exception as e:
            print(f"❌ SQL export failed: {e}")
            return False

if __name__ == "__main__":
    print("🏨 Hotel Booking System - Data Export")
    print("=" * 50)
    
    try:
        # Try CSV export first (easier to import)
        csv_file = export_to_csv()
        
        # Also create SQL export
        sql_file = export_to_sql_insert()
        
        if csv_file or sql_file:
            print("\n✅ Export completed successfully!")
            print("\n📋 Files created:")
            if csv_file:
                print(f"   📄 CSV: {csv_file}")
            if sql_file:
                print(f"   📄 SQL: {sql_file}")
            
            print("\n🚀 Next Steps:")
            print("1. Complete Render deployment setup")
            print("2. Use CSV file with your app's bulk import feature, OR")
            print("3. Execute SQL file directly in Render PostgreSQL")
            
        else:
            print("\n❌ Export failed")
            
    except Exception as e:
        print(f"❌ Export script failed: {e}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure you're in the hotel_flask_app_optimized directory")
        print("2. Ensure PostgreSQL is running locally")
        print("3. Check that your Flask app can connect to local database")