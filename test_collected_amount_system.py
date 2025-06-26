#!/usr/bin/env python3
"""
Test Script for Collected Amount Tracking System
Debug and verify the complete implementation
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent))

def test_database_migration():
    """Test if collected_amount column exists"""
    print("🔍 TESTING DATABASE MIGRATION")
    print("=" * 50)
    
    try:
        from sqlalchemy import create_engine, text
        
        # Get database URL from environment or use default
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            print("❌ DATABASE_URL not found in environment")
            return False
        
        engine = create_engine(database_url)
        
        # Check if column exists
        query = """
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'bookings' 
        AND column_name = 'collected_amount'
        """
        
        with engine.connect() as conn:
            result = conn.execute(text(query)).fetchone()
            
            if result:
                print("✅ collected_amount column EXISTS!")
                print(f"   - Type: {result[1]}")
                print(f"   - Nullable: {result[2]}")
                print(f"   - Default: {result[3]}")
                return True
            else:
                print("❌ collected_amount column NOT FOUND")
                print("   Need to run migration: psql -d database -f add_collected_amount.sql")
                return False
                
    except Exception as e:
        print(f"❌ Database connection error: {e}")
        return False

def test_booking_data_structure():
    """Test if booking data includes collected amount"""
    print("\n🔍 TESTING BOOKING DATA STRUCTURE")
    print("=" * 50)
    
    try:
        from app_postgresql import app
        from core.logic_postgresql import load_booking_data
        
        with app.app_context():
            df = load_booking_data()
            
            if df.empty:
                print("⚠️ No booking data found")
                return False
            
            # Check if collected amount column exists in data
            if 'Số tiền đã thu' in df.columns:
                print("✅ 'Số tiền đã thu' column found in booking data!")
                print(f"   - Total bookings: {len(df)}")
                
                # Show sample data
                for i, row in df.head(3).iterrows():
                    booking_id = row.get('Số đặt phòng', 'N/A')
                    original = row.get('Tổng thanh toán', 0)
                    collected = row.get('Số tiền đã thu', 0)
                    print(f"   - {booking_id}: Original={original:,.0f}đ, Collected={collected:,.0f}đ")
                
                return True
            else:
                print("❌ 'Số tiền đã thu' column NOT FOUND in booking data")
                print(f"   Available columns: {list(df.columns)}")
                return False
                
    except Exception as e:
        print(f"❌ Data loading error: {e}")
        return False

def test_api_endpoint():
    """Test collect_payment API functionality"""
    print("\n🔍 TESTING API ENDPOINT")
    print("=" * 50)
    
    try:
        import requests
        import json
        
        # Test data
        test_data = {
            "booking_id": "FLASK_TEST_001",
            "collected_amount": 123456,
            "collector_name": "TEST_USER",
            "payment_note": "Test payment collection",
            "payment_type": "room",
            "commission_amount": 0,
            "commission_type": "none"
        }
        
        # Make API call
        response = requests.post(
            'http://127.0.0.1:5000/api/collect_payment',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(test_data),
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ API endpoint working correctly!")
                print(f"   - Response: {result.get('message', 'Success')}")
                return True
            else:
                print("❌ API returned error:")
                print(f"   - Message: {result.get('message', 'Unknown error')}")
                return False
        else:
            print(f"❌ API returned status code: {response.status_code}")
            print(f"   - Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("⚠️ Flask server not running - start with: python app_postgresql.py")
        return False
    except Exception as e:
        print(f"❌ API test error: {e}")
        return False

def test_frontend_integration():
    """Test frontend file modifications"""
    print("\n🔍 TESTING FRONTEND INTEGRATION")
    print("=" * 50)
    
    try:
        dashboard_path = Path("templates/dashboard.html")
        
        if not dashboard_path.exists():
            print("❌ dashboard.html not found")
            return False
        
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for critical modifications
        checks = [
            ("modalOriginalAmount", "Original amount modal field"),
            ("modalCollectedAmount", "Collected amount modal field"), 
            ("modalRemainingAmount", "Remaining amount modal field"),
            ("Số tiền đã thu", "Collected amount template variable"),
            ("collectedAmount", "JavaScript collected amount parameter")
        ]
        
        all_found = True
        for check_str, description in checks:
            if check_str in content:
                print(f"✅ {description} - FOUND")
            else:
                print(f"❌ {description} - NOT FOUND")
                all_found = False
        
        return all_found
        
    except Exception as e:
        print(f"❌ Frontend test error: {e}")
        return False

def run_comprehensive_test():
    """Run all tests and provide summary"""
    print("🧪 COLLECTED AMOUNT TRACKING SYSTEM - COMPREHENSIVE TEST")
    print("=" * 70)
    
    tests = [
        ("Database Migration", test_database_migration),
        ("Booking Data Structure", test_booking_data_structure),
        ("API Endpoint", test_api_endpoint),
        ("Frontend Integration", test_frontend_integration)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📋 TEST SUMMARY")
    print("=" * 70)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall Result: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED - System ready for production!")
        print("\n🚀 Next Steps:")
        print("1. Test payment collection in browser")
        print("2. Verify dashboard shows correct payment status")
        print("3. Check PostgreSQL data with DBeaver")
    else:
        print("\n⚠️ Some tests failed - review the issues above")
        print("\n🔧 Common fixes:")
        print("1. Run database migration: psql -d database -f add_collected_amount.sql")
        print("2. Restart Flask server: python app_postgresql.py")
        print("3. Clear browser cache and reload dashboard")

if __name__ == "__main__":
    run_comprehensive_test()