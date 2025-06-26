#!/usr/bin/env python3
"""
Debug taxi and commission frontend issues
"""

import requests
import json

def test_taxi_payment_direct():
    """Test taxi payment directly via API"""
    print("🚕 TESTING TAXI PAYMENT DIRECTLY")
    print("=" * 50)
    
    # Test data that SHOULD work
    test_data = {
        "booking_id": "FLASK_TEST_001", 
        "collected_amount": 150000,  # 150,000 VND taxi fare
        "collector_name": "LOC LE",
        "payment_note": "Test taxi payment",
        "payment_type": "taxi",  # This is the key - frontend must send this
        "commission_amount": 75000,  # Also test commission
        "commission_type": "normal"
    }
    
    print("📤 Sending direct API request:")
    for key, value in test_data.items():
        print(f"   {key}: {value}")
    
    try:
        response = requests.post(
            "http://localhost:5000/api/collect_payment",
            headers={"Content-Type": "application/json"},
            json=test_data
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS: {result.get('message')}")
            return True
        else:
            print(f"❌ FAILED: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def check_database_after_update():
    """Check if taxi data was saved to database"""
    print("\n📊 CHECKING DATABASE STATUS")
    print("=" * 50)
    
    try:
        response = requests.get("http://localhost:5000/api/debug_booking/FLASK_TEST_001")
        
        if response.status_code == 200:
            data = response.json()
            booking_data = data.get('booking_data', {})
            
            print("📋 Current booking data:")
            print(f"   - taxi_amount: {booking_data.get('taxi_amount')}đ")
            print(f"   - commission: {booking_data.get('commission')}đ") 
            print(f"   - booking_notes: {booking_data.get('booking_notes')}")
            print(f"   - collector: {booking_data.get('collector')}")
            
            # Check if taxi was saved
            taxi_amount = booking_data.get('taxi_amount', 0)
            commission = booking_data.get('commission', 0)
            
            if taxi_amount == 150000:
                print("✅ TAXI: Correctly saved to database")
            else:
                print(f"❌ TAXI: Expected 150000, got {taxi_amount}")
                
            if commission == 75000:
                print("✅ COMMISSION: Correctly saved to database")
            else:
                print(f"❌ COMMISSION: Expected 75000, got {commission}")
                
            return taxi_amount == 150000 and commission == 75000
        else:
            print(f"❌ Cannot check database: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Database check error: {e}")
        return False

def main():
    print("🔧 TAXI & COMMISSION DEBUG TEST")
    print("=" * 60)
    print("This test will:")
    print("1. Send taxi payment directly to API (bypassing frontend)")
    print("2. Check if data was saved to PostgreSQL")
    print("3. Verify what the management table should show")
    print("=" * 60)
    
    # Test direct API
    api_success = test_taxi_payment_direct()
    if not api_success:
        print("\n💥 API test failed - backend issue")
        return False
    
    # Check database
    db_success = check_database_after_update()
    if not db_success:
        print("\n💥 Database check failed - data not saved")
        return False
    
    print("\n" + "=" * 60)
    print("🎉 SUCCESS! Backend and database are working correctly")
    print("=" * 60)
    print("\n🔍 FRONTEND DIAGNOSIS:")
    print("Since the backend works, the issue is in the frontend.")
    print("The frontend is not sending 'payment_type: taxi' correctly.")
    print("\n📋 Next steps:")
    print("1. Check browser console when submitting taxi payment")
    print("2. Look for these debug logs:")
    print("   - '🔍 [DEBUG] Taxi detection:'")
    print("   - '🚕 [DEBUG] TAXI MODE ACTIVATED!'")
    print("   - '📤 [DEBUG] Final request data being sent:'")
    print("3. The frontend should show 'payment_type: taxi' in the logs")
    print("4. If not, the taxi checkbox/amount detection is broken")
    
    print("\n🏪 MANAGEMENT TABLE DISPLAY:")
    print("Go to /bookings page and check FLASK_TEST_001:")
    print("- Taxi column should show: Badge with '150,000đ'")
    print("- Commission should show: '75,000đ'")
    print("- If showing dash (-), check load_booking_data() function")
    
    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)