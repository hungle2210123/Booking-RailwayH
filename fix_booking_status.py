#!/usr/bin/env python3
"""
Fix Booking Status Script
Fixes all booking statuses that are incorrectly set to cancelled
"""

import sys
import os

# Add the project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import app
from core.models import db, Booking

def fix_booking_statuses():
    """Fix all booking statuses to 'confirmed' unless they should be cancelled"""
    
    with app.app_context():
        try:
            # Count total bookings
            total_bookings = db.session.query(Booking).count()
            print(f"📊 Total bookings in database: {total_bookings}")
            
            # Check current status distribution
            status_counts = db.session.query(
                Booking.booking_status, 
                db.func.count(Booking.booking_status)
            ).group_by(Booking.booking_status).all()
            
            print("\n🔍 Current booking status distribution:")
            for status, count in status_counts:
                print(f"   {status}: {count} bookings")
            
            # Update all bookings that don't have explicit cancelled status
            # Set them to 'confirmed' (which maps to 'OK' in the UI)
            affected_bookings = db.session.query(Booking).filter(
                ~Booking.booking_status.in_(['deleted', 'cancelled'])
            ).all()
            
            print(f"\n🔧 Updating {len(affected_bookings)} bookings to 'confirmed' status...")
            
            # Update bookings in batches
            batch_size = 100
            updated_count = 0
            
            for i in range(0, len(affected_bookings), batch_size):
                batch = affected_bookings[i:i + batch_size]
                
                for booking in batch:
                    booking.booking_status = 'confirmed'
                    updated_count += 1
                
                # Commit batch
                db.session.commit()
                print(f"   ✅ Updated batch {i//batch_size + 1}: {min(i + batch_size, len(affected_bookings))} / {len(affected_bookings)}")
            
            print(f"\n✅ Successfully updated {updated_count} booking statuses to 'confirmed'")
            
            # Verify the changes
            print("\n🔍 New booking status distribution:")
            new_status_counts = db.session.query(
                Booking.booking_status, 
                db.func.count(Booking.booking_status)
            ).group_by(Booking.booking_status).all()
            
            for status, count in new_status_counts:
                print(f"   {status}: {count} bookings")
            
            return True
            
        except Exception as e:
            print(f"❌ Error fixing booking statuses: {e}")
            db.session.rollback()
            return False

if __name__ == "__main__":
    print("🚀 Starting booking status fix...")
    success = fix_booking_statuses()
    
    if success:
        print("\n🎉 Booking status fix completed successfully!")
        print("\n💡 Next steps:")
        print("   1. Restart your Flask application")
        print("   2. Refresh the dashboard page")
        print("   3. Check that [CANCELLED] statuses are no longer showing incorrectly")
    else:
        print("\n❌ Booking status fix failed. Please check the error messages above.")
    
    sys.exit(0 if success else 1)