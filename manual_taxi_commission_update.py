#!/usr/bin/env python3
"""
Manual Taxi & Commission Update Tool
Directly updates PostgreSQL database bypassing broken frontend
"""

import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_database_connection():
    """Get PostgreSQL database connection"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return None
    
    try:
        engine = create_engine(database_url)
        return engine
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return None

def show_current_bookings():
    """Show current bookings with taxi and commission info"""
    engine = get_database_connection()
    if not engine:
        return
    
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    b.booking_id,
                    g.full_name as guest_name,
                    b.room_amount,
                    b.commission,
                    b.taxi_amount,
                    b.collector,
                    b.booking_notes
                FROM bookings b
                JOIN guests g ON b.guest_id = g.guest_id
                WHERE b.booking_status != 'deleted'
                ORDER BY b.checkin_date DESC
            """)
            
            result = conn.execute(query)
            bookings = result.fetchall()
            
            if not bookings:
                print("📋 No bookings found")
                return
            
            print("\n📋 CURRENT BOOKINGS:")
            print("=" * 80)
            print(f"{'ID':<15} {'Guest':<20} {'Room':<10} {'Commission':<12} {'Taxi':<10} {'Collector':<15}")
            print("-" * 80)
            
            for booking in bookings:
                print(f"{booking.booking_id:<15} {booking.guest_name:<20} "
                      f"{booking.room_amount:>9,.0f} {booking.commission:>11,.0f} "
                      f"{booking.taxi_amount:>9,.0f} {booking.collector or 'N/A':<15}")
            
            return bookings
            
    except Exception as e:
        print(f"❌ Error fetching bookings: {e}")
        return None

def update_taxi_commission(booking_id, taxi_amount=None, commission_amount=None, notes=None):
    """Update taxi and/or commission for a booking"""
    engine = get_database_connection()
    if not engine:
        return False
    
    try:
        with engine.connect() as conn:
            # Build update query dynamically
            updates = []
            params = {'booking_id': booking_id}
            
            if taxi_amount is not None:
                updates.append("taxi_amount = :taxi_amount")
                params['taxi_amount'] = float(taxi_amount)
            
            if commission_amount is not None:
                updates.append("commission = :commission")
                params['commission'] = float(commission_amount)
            
            if notes:
                updates.append("booking_notes = :notes")
                params['notes'] = notes
            
            if not updates:
                print("❌ No updates specified")
                return False
            
            # Add timestamp update
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            query = text(f"""
                UPDATE bookings 
                SET {', '.join(updates)}
                WHERE booking_id = :booking_id
            """)
            
            print(f"🔧 Executing update for {booking_id}:")
            if taxi_amount is not None:
                print(f"   - Taxi amount: {taxi_amount:,.0f}đ")
            if commission_amount is not None:
                print(f"   - Commission: {commission_amount:,.0f}đ")
            if notes:
                print(f"   - Notes: {notes}")
            
            result = conn.execute(query, params)
            conn.commit()
            
            if result.rowcount > 0:
                print(f"✅ Successfully updated {booking_id}")
                return True
            else:
                print(f"❌ No booking found with ID: {booking_id}")
                return False
                
    except Exception as e:
        print(f"❌ Update failed: {e}")
        return False

def verify_update(booking_id):
    """Verify the update was successful"""
    engine = get_database_connection()
    if not engine:
        return
    
    try:
        with engine.connect() as conn:
            query = text("""
                SELECT 
                    booking_id,
                    commission,
                    taxi_amount,
                    booking_notes,
                    updated_at
                FROM bookings
                WHERE booking_id = :booking_id
            """)
            
            result = conn.execute(query, {'booking_id': booking_id})
            booking = result.fetchone()
            
            if booking:
                print(f"\n✅ VERIFICATION for {booking_id}:")
                print(f"   - Commission: {booking.commission:,.0f}đ")
                print(f"   - Taxi amount: {booking.taxi_amount:,.0f}đ")
                print(f"   - Notes: {booking.booking_notes or 'None'}")
                print(f"   - Updated: {booking.updated_at}")
            else:
                print(f"❌ Booking {booking_id} not found")
                
    except Exception as e:
        print(f"❌ Verification failed: {e}")

def interactive_mode():
    """Interactive mode for updating bookings"""
    print("\n🚕💰 MANUAL TAXI & COMMISSION UPDATE TOOL")
    print("=" * 50)
    print("This tool directly updates PostgreSQL database")
    print("=" * 50)
    
    while True:
        print("\n📋 Available commands:")
        print("1. show - Show all current bookings")
        print("2. update - Update taxi/commission for a booking")
        print("3. verify - Verify a booking's current values")
        print("4. exit - Exit the tool")
        
        choice = input("\nEnter command (1-4): ").strip().lower()
        
        if choice in ['1', 'show']:
            show_current_bookings()
            
        elif choice in ['2', 'update']:
            bookings = show_current_bookings()
            if not bookings:
                continue
                
            booking_id = input("\nEnter booking ID to update: ").strip().upper()
            
            # Validate booking exists
            if not any(b.booking_id == booking_id for b in bookings):
                print(f"❌ Booking ID '{booking_id}' not found")
                continue
            
            print(f"\nUpdating {booking_id}:")
            
            # Get taxi amount
            taxi_input = input("Enter taxi amount (or press Enter to skip): ").strip()
            taxi_amount = None
            if taxi_input:
                try:
                    taxi_amount = float(taxi_input.replace(',', ''))
                except ValueError:
                    print("❌ Invalid taxi amount")
                    continue
            
            # Get commission amount
            commission_input = input("Enter commission amount (or press Enter to skip): ").strip()
            commission_amount = None
            if commission_input:
                try:
                    commission_amount = float(commission_input.replace(',', ''))
                except ValueError:
                    print("❌ Invalid commission amount")
                    continue
            
            # Get notes
            notes_input = input("Enter notes (or press Enter to skip): ").strip()
            notes = notes_input if notes_input else None
            
            if taxi_amount is None and commission_amount is None and notes is None:
                print("❌ No updates specified")
                continue
            
            # Confirm update
            print(f"\n🔍 CONFIRM UPDATE for {booking_id}:")
            if taxi_amount is not None:
                print(f"   - Set taxi to: {taxi_amount:,.0f}đ")
            if commission_amount is not None:
                print(f"   - Set commission to: {commission_amount:,.0f}đ")
            if notes:
                print(f"   - Set notes to: {notes}")
            
            confirm = input("\nProceed with update? (y/n): ").strip().lower()
            if confirm == 'y':
                if update_taxi_commission(booking_id, taxi_amount, commission_amount, notes):
                    verify_update(booking_id)
            else:
                print("❌ Update cancelled")
                
        elif choice in ['3', 'verify']:
            booking_id = input("Enter booking ID to verify: ").strip().upper()
            verify_update(booking_id)
            
        elif choice in ['4', 'exit', 'quit']:
            print("👋 Goodbye!")
            break
            
        else:
            print("❌ Invalid command")

def quick_update_examples():
    """Show quick update examples for common scenarios"""
    print("\n🚀 QUICK UPDATE EXAMPLES:")
    print("=" * 40)
    
    examples = [
        {
            'name': 'Add taxi fare to FLASK_TEST_001',
            'booking_id': 'FLASK_TEST_001',
            'taxi_amount': 200000,
            'notes': 'Added taxi fare manually'
        },
        {
            'name': 'Update commission for DEMO001',
            'booking_id': 'DEMO001', 
            'commission_amount': 75000,
            'notes': 'Updated commission manually'
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['name']}")
        print(f"   Command: update_taxi_commission('{example['booking_id']}', ")
        if 'taxi_amount' in example:
            print(f"            taxi_amount={example['taxi_amount']},")
        if 'commission_amount' in example:
            print(f"            commission_amount={example['commission_amount']},")
        print(f"            notes='{example['notes']}')")

def main():
    """Main function"""
    if len(sys.argv) > 1:
        # Command line mode
        if sys.argv[1] == 'show':
            show_current_bookings()
        elif sys.argv[1] == 'examples':
            quick_update_examples()
        else:
            print("Usage: python manual_taxi_commission_update.py [show|examples]")
    else:
        # Interactive mode
        interactive_mode()

if __name__ == "__main__":
    main()