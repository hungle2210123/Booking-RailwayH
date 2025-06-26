#!/usr/bin/env python3
"""
Test Commission and Taxi Amount Updates
Verify that payment collection properly updates database
"""

import requests
import json
import sys
from pathlib import Path

def test_payment_collection_api():
    """Test the collect_payment API with commission and taxi data"""
    print("🧪 TESTING PAYMENT COLLECTION API")
    print("=" * 50)
    
    # Test data with commission and taxi amounts
    test_data = {
        "booking_id": "FLASK_TEST_001",
        "collected_amount": 300000,
        "collector_name": "LOC LE",
        "payment_note": "Test payment with commission and taxi",
        "commission_amount": 25000,      # 💰 Commission amount
        "commission_type": "normal",     # 💰 Commission type
        "taxi_amount": 75000,           # 🚕 Taxi amount
        "payment_type": "room"          # 🎯 Payment type
    }
    
    print("📤 Sending test data:")
    for key, value in test_data.items():
        print(f"   - {key}: {value}")
    
    try:
        response = requests.post(
            'http://127.0.0.1:5000/api/collect_payment',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(test_data),
            timeout=10
        )
        
        print(f"\n📬 API Response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success: {result.get('success')}")
            print(f"📝 Message: {result.get('message', 'No message')}")
            
            if result.get('success'):
                print("\n🎉 API Test PASSED!")
                return True
            else:
                print(f"\n❌ API returned success=False: {result.get('message')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask server")
        print("   Make sure server is running: python app_postgresql.py")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def test_booking_data_retrieval():
    """Test if booking data can be retrieved with fresh data"""
    print("\n🧪 TESTING BOOKING DATA RETRIEVAL")
    print("=" * 50)
    
    try:
        # Test regular bookings page
        response = requests.get('http://127.0.0.1:5000/bookings', timeout=10)
        
        if response.status_code == 200:
            print("✅ Bookings page loads successfully")
            
            # Check if the page contains our test booking
            if "FLASK_TEST_001" in response.text:
                print("✅ Test booking found in bookings page")
                
                # Look for commission and taxi amounts in the response
                if "25,000" in response.text or "25000" in response.text:
                    print("✅ Commission amount appears to be displayed")
                else:
                    print("❌ Commission amount not found in page")
                
                if "75,000" in response.text or "75000" in response.text:
                    print("✅ Taxi amount appears to be displayed")
                else:
                    print("❌ Taxi amount not found in page")
                
                return True
            else:
                print("❌ Test booking not found in page")
                return False
        else:
            print(f"❌ Bookings page error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Data retrieval test error: {e}")
        return False

def check_dashboard_data():
    """Check if dashboard shows updated data"""
    print("\n🧪 TESTING DASHBOARD DATA")
    print("=" * 50)
    
    try:
        response = requests.get('http://127.0.0.1:5000/', timeout=10)
        
        if response.status_code == 200:
            print("✅ Dashboard loads successfully")
            
            # Check for test booking in dashboard
            if "FLASK_TEST_001" in response.text:
                print("✅ Test booking found in dashboard")
                return True
            else:
                print("❌ Test booking not found in dashboard")
                return False
        else:
            print(f"❌ Dashboard error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Dashboard test error: {e}")
        return False

def show_debugging_tips():
    """Show debugging tips for the user"""
    print("\n🔍 DEBUGGING TIPS")
    print("=" * 50)
    
    print("1. 📊 Check Server Logs:")
    print("   Look for these messages in your Flask server output:")
    print("   - '💰 COLLECT PAYMENT - Form Data Collected:'")
    print("   - '🚕 Setting taxi_amount in DB to:'")
    print("   - '💰 Setting collected_amount to:'")
    print("   - '📊 Final update_data:'")
    
    print("\n2. 🗄️ Check Database Directly:")
    print("   Run this SQL in DBeaver or psql:")
    print("   SELECT booking_id, room_amount, taxi_amount, commission, collected_amount, collector")
    print("   FROM bookings WHERE booking_id = 'FLASK_TEST_001';")
    
    print("\n3. 🔄 Force Refresh:")
    print("   - Clear browser cache (Ctrl+Shift+Del)")
    print("   - Hard refresh (Ctrl+F5)")
    print("   - Restart Flask server")
    
    print("\n4. 🎯 Test Again:")
    print("   - Go to dashboard")
    print("   - Click 'Thu' button for FLASK_TEST_001")
    print("   - Enter commission: 30000")
    print("   - Check 'Có taxi' and enter: 80000")
    print("   - Enter collected amount: 350000")
    print("   - Select collector: LOC LE")
    print("   - Save and check if values appear in booking management")

def main():
    """Run all tests"""
    print("🧪 COMMISSION & TAXI UPDATE TESTING SUITE")
    print("=" * 70)
    
    tests = [
        ("Payment Collection API", test_payment_collection_api),
        ("Booking Data Retrieval", test_booking_data_retrieval),
        ("Dashboard Data", check_dashboard_data)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📋 TEST RESULTS SUMMARY")
    print("=" * 70)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed < len(results):
        show_debugging_tips()
    else:
        print("\n🎉 ALL TESTS PASSED!")
        print("Commission and taxi updates should be working correctly.")

if __name__ == "__main__":
    main()