#!/usr/bin/env python3
"""
Test the complete taxi fare workflow
"""

import sys
import os
import requests
import json

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_current_booking_data():
    """Check current booking data before taxi collection"""
    print("🔍 Step 1: Check Current Booking Data")
    print("=" * 40)
    
    booking_id = "FLASK_TEST_001"
    
    try:
        # Use the debug endpoint to check current data
        response = requests.get(f"http://localhost:5000/api/debug_booking/{booking_id}")
        
        if response.status_code == 200:
            data = response.json()
            booking_data = data.get('booking_data', {})
            
            print(f"📋 Current booking data for {booking_id}:")
            print(f"   - Guest: {booking_data.get('guest_name')}")
            print(f"   - Room amount: {booking_data.get('room_amount')}đ")
            print(f"   - Taxi amount: {booking_data.get('taxi_amount')}đ ⭐")
            print(f"   - Commission: {booking_data.get('commission')}đ")
            print(f"   - Collector: {booking_data.get('collector')}")
            print(f"   - Notes: {booking_data.get('booking_notes')}")
            
            if booking_data.get('taxi_amount', 0) == 0:
                print("✅ Confirmed: No taxi fare initially (as expected)")
            else:
                print(f"⚠️  Unexpected: Taxi amount already exists: {booking_data.get('taxi_amount')}")
                
            return booking_data
        else:
            print(f"❌ Failed to get booking data: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"❌ Error checking booking data: {e}")
        return None

def test_taxi_collection_api():
    """Test taxi collection API directly"""
    print("\n🚕 Step 2: Test Taxi Collection API")
    print("=" * 40)
    
    # This simulates what the frontend SHOULD send
    request_data = {
        "booking_id": "FLASK_TEST_001",
        "collected_amount": 123111,  # The taxi amount you entered
        "collector_name": "LOC LE",
        "payment_note": "Thu tiền taxi",
        "payment_type": "taxi",  # This is critical!
        "commission_amount": 0,
        "commission_type": "none"
    }
    
    print("📤 Sending taxi collection request:")
    for key, value in request_data.items():
        print(f"   {key}: {value}")
    
    try:
        response = requests.post(
            "http://localhost:5000/api/collect_payment",
            headers={"Content-Type": "application/json"},
            json=request_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ API Response: {result.get('message')}")
            return True
        else:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False

def test_after_collection_data():
    """Check booking data after taxi collection"""
    print("\n📊 Step 3: Verify Data After Collection")
    print("=" * 40)
    
    booking_id = "FLASK_TEST_001"
    
    try:
        response = requests.get(f"http://localhost:5000/api/debug_booking/{booking_id}")
        
        if response.status_code == 200:
            data = response.json()
            booking_data = data.get('booking_data', {})
            
            print(f"📋 Booking data after taxi collection:")
            print(f"   - Taxi amount: {booking_data.get('taxi_amount')}đ")
            print(f"   - Booking notes: {booking_data.get('booking_notes')}")
            print(f"   - Updated at: {booking_data.get('updated_at')}")
            
            expected_taxi = 123111
            actual_taxi = booking_data.get('taxi_amount', 0)
            
            if actual_taxi == expected_taxi:
                print(f"✅ SUCCESS: Taxi amount correctly updated to {actual_taxi}đ")
                return True
            else:
                print(f"❌ FAILED: Expected {expected_taxi}đ, got {actual_taxi}đ")
                return False
        else:
            print(f"❌ Failed to verify data: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Verification error: {e}")
        return False

def test_bookings_page_display():
    """Test how the data appears on bookings page"""
    print("\n📋 Step 4: Check Bookings Page Display")
    print("=" * 40)
    
    print("💡 To verify the bookings page display:")
    print("1. Go to http://localhost:5000/bookings")
    print("2. Find booking FLASK_TEST_001")
    print("3. Look at the 🚕 Taxi column")
    print("4. Should show: Badge with '123,111đ'")
    print("5. Should NOT show: Dash (-)")
    
    return True

def main():
    """Run complete taxi workflow test"""
    print("🚕 COMPLETE TAXI FARE WORKFLOW TEST")
    print("=" * 50)
    print("Testing: Add taxi fare during payment collection")
    print("=" * 50)
    
    try:
        # Step 1: Check initial state
        initial_data = test_current_booking_data()
        if not initial_data:
            print("❌ Cannot proceed - failed to get initial data")
            return False
        
        # Step 2: Test API collection
        api_success = test_taxi_collection_api()
        if not api_success:
            print("❌ Cannot proceed - API collection failed")
            return False
        
        # Step 3: Verify update
        verification_success = test_after_collection_data()
        if not verification_success:
            print("❌ Verification failed - data not updated")
            return False
        
        # Step 4: Guide for manual verification
        test_bookings_page_display()
        
        print("\n" + "=" * 50)
        print("🎉 TAXI WORKFLOW TEST COMPLETE!")
        print("✅ Taxi fare successfully added during collection")
        print("✅ Database updated with taxi amount")
        print("✅ Ready for bookings page verification")
        print("=" * 50)
        
        print("\n🔧 Expected workflow:")
        print("1. Initial: taxi_amount = 0")
        print("2. Collect: Add 123,111đ taxi fare")
        print("3. Result: taxi_amount = 123111, displayed in table")
        
        print("\n📋 Next steps:")
        print("1. Check bookings page for taxi display")
        print("2. Verify in DBeaver: SELECT taxi_amount FROM bookings WHERE booking_id='FLASK_TEST_001'")
        print("3. If still showing dash (-), there's a template display issue")
        
        return True
        
    except Exception as e:
        print(f"\n💥 TEST ERROR: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)