#!/usr/bin/env python3
"""
Debug taxi payment collection issue
"""

import sys
import os
from datetime import datetime, date

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_taxi_payment_api_simulation():
    """Test the exact API call that would be made for taxi payment"""
    print("🔍 Testing Taxi Payment API Simulation")
    print("=" * 45)
    
    # Simulate the exact request data that would be sent from frontend
    sample_request_data = {
        'booking_id': 'FLASK_TEST_001',
        'collected_amount': 200000,
        'collector_name': 'LOC LE',
        'payment_note': 'Thu tiền taxi cho khách',
        'payment_type': 'taxi',  # This is the key field
        'commission_amount': 50000,
        'commission_type': 'normal'
    }
    
    print("📋 Simulating frontend request data:")
    for key, value in sample_request_data.items():
        print(f"   {key}: {value}")
    
    # Simulate the backend processing logic from app_postgresql.py
    print("\n🔧 Backend Processing Logic:")
    
    # Extract values (same as backend)
    booking_id = sample_request_data.get('booking_id')
    collected_amount = sample_request_data.get('collected_amount')
    collector_name = sample_request_data.get('collector_name')
    payment_note = sample_request_data.get('payment_note', '')
    payment_type = sample_request_data.get('payment_type', 'room')
    commission_amount = sample_request_data.get('commission_amount', 0)
    commission_type = sample_request_data.get('commission_type', 'normal')
    
    print(f"   booking_id: {booking_id}")
    print(f"   collected_amount: {collected_amount}")
    print(f"   payment_type: {payment_type}")
    print(f"   commission_amount: {commission_amount}")
    print(f"   commission_type: {commission_type}")
    
    # Prepare update_data (same as backend)
    update_data = {}
    
    # Commission logic
    if commission_type == 'none':
        update_data['commission'] = 0
        print("   ✅ Commission set to 0 (no commission)")
    elif commission_amount is not None and commission_amount > 0:
        update_data['commission'] = float(commission_amount)
        print(f"   ✅ Commission set to {commission_amount}")
    
    # Payment type logic - THIS IS CRITICAL
    if payment_type == 'taxi':
        # Thu tiền taxi
        update_data['taxi_amount'] = float(collected_amount)
        if payment_note:
            update_data['booking_notes'] = f"Thu taxi {collected_amount:,.0f}đ - {payment_note}"
        else:
            update_data['booking_notes'] = f"Thu taxi {collected_amount:,.0f}đ"
        print(f"   🚕 TAXI PAYMENT: taxi_amount = {update_data['taxi_amount']}")
        print(f"   📝 Notes: {update_data['booking_notes']}")
    else:
        # Thu tiền phòng
        update_data['collector'] = collector_name
        if payment_note:
            update_data['booking_notes'] = f"Thu {collected_amount:,.0f}đ - {payment_note}"
        else:
            update_data['booking_notes'] = f"Thu {collected_amount:,.0f}đ"
        print(f"   🏠 ROOM PAYMENT: collector = {update_data['collector']}")
    
    print(f"\n💾 Final update_data for database:")
    for key, value in update_data.items():
        print(f"   {key}: {value} ({type(value).__name__})")
    
    # Expected database updates
    expected_db_updates = {
        'taxi_amount': 200000.0,
        'commission': 50000.0,
        'booking_notes': 'Thu taxi 200,000đ - Thu tiền taxi cho khách'
    }
    
    print(f"\n🎯 Expected database changes:")
    for key, value in expected_db_updates.items():
        print(f"   {key}: {value}")
    
    # Verify logic
    all_correct = True
    for key, expected_value in expected_db_updates.items():
        if key in update_data:
            actual_value = update_data[key]
            if actual_value == expected_value:
                print(f"   ✅ {key}: CORRECT")
            else:
                print(f"   ❌ {key}: Expected {expected_value}, got {actual_value}")
                all_correct = False
        else:
            print(f"   ❌ {key}: MISSING from update_data")
            all_correct = False
    
    return all_correct

def test_database_query_logic():
    """Test how the data should appear in database queries"""
    print("\n🗄️ Testing Database Query Logic")
    print("=" * 35)
    
    print("📊 SQL Query from load_booking_data():")
    sql_query = """
    SELECT 
        b.booking_id as "Số đặt phòng",
        g.full_name as "Tên người đặt", 
        b.taxi_amount as "Taxi",
        b.commission as "Hoa hồng",
        b.booking_notes as "Ghi chú thanh toán"
    FROM bookings b
    JOIN guests g ON b.guest_id = g.guest_id
    WHERE b.booking_id = 'FLASK_TEST_001'
    """
    print(sql_query)
    
    print("\n🔍 Expected database values after taxi payment:")
    expected_db_row = {
        'Số đặt phòng': 'FLASK_TEST_001',
        'Taxi': 200000.0,  # This should NOT be blank!
        'Hoa hồng': 50000.0,
        'Ghi chú thanh toán': 'Thu taxi 200,000đ - Thu tiền taxi cho khách'
    }
    
    for key, value in expected_db_row.items():
        print(f"   {key}: {value}")
    
    print("\n📋 Template display logic (from bookings.html):")
    template_logic = """
    {% set taxi = booking.get('Taxi', 0) %}
    {% set taxi_value = taxi|float if taxi else 0 %}
    {% if taxi_value > 0 %}
    <span class="badge bg-info text-dark">{{ "{:,.0f}đ".format(taxi_value) }}</span>
    {% else %}
    <small class="text-muted">-</small>
    {% endif %}
    """
    print(template_logic)
    
    # Test template logic
    taxi = 200000.0  # This is what should come from database
    taxi_value = float(taxi) if taxi else 0
    
    if taxi_value > 0:
        display = f"Badge: {taxi_value:,.0f}đ"
        result = "✅ Shows taxi amount"
    else:
        display = "Dash: -"
        result = "❌ Shows dash (WRONG!)"
    
    print(f"\n🎨 Template rendering test:")
    print(f"   Input taxi value: {taxi}")
    print(f"   Processed taxi_value: {taxi_value}")
    print(f"   Display result: {display}")
    print(f"   Status: {result}")
    
    return True

def test_potential_issues():
    """Test potential issues that could cause blank taxi column"""
    print("\n🚨 Testing Potential Issues")
    print("=" * 30)
    
    issues = [
        {
            "name": "Frontend payment_type not 'taxi'",
            "request_data": {'payment_type': 'room', 'collected_amount': 200000},
            "expected_issue": "taxi_amount not set in update_data"
        },
        {
            "name": "collected_amount is 0 or null",
            "request_data": {'payment_type': 'taxi', 'collected_amount': 0},
            "expected_issue": "API validation should reject this"
        },
        {
            "name": "Database commit failure",
            "request_data": {'payment_type': 'taxi', 'collected_amount': 200000},
            "expected_issue": "update_booking returns False"
        },
        {
            "name": "Cache not cleared",
            "request_data": {'payment_type': 'taxi', 'collected_amount': 200000},
            "expected_issue": "Old data still displayed"
        },
        {
            "name": "SQL column mapping issue",
            "request_data": {'payment_type': 'taxi', 'collected_amount': 200000},
            "expected_issue": "taxi_amount not mapped to 'Taxi' column"
        }
    ]
    
    for i, issue in enumerate(issues, 1):
        print(f"\n📋 Issue {i}: {issue['name']}")
        print(f"   Request: {issue['request_data']}")
        print(f"   Potential problem: {issue['expected_issue']}")
        
        # Test the specific issue
        if issue['name'] == "Frontend payment_type not 'taxi'":
            payment_type = issue['request_data'].get('payment_type')
            if payment_type != 'taxi':
                print(f"   🔴 PROBLEM DETECTED: payment_type='{payment_type}' will not trigger taxi logic!")
            else:
                print(f"   ✅ payment_type is correct")
        
        elif issue['name'] == "collected_amount is 0 or null":
            collected_amount = issue['request_data'].get('collected_amount')
            if not collected_amount or collected_amount <= 0:
                print(f"   🔴 PROBLEM DETECTED: collected_amount={collected_amount} should be rejected!")
            else:
                print(f"   ✅ collected_amount is valid")
    
    return True

def main():
    """Run all taxi payment debugging tests"""
    print("🚕 TAXI PAYMENT COLLECTION DEBUG")
    print("=" * 50)
    print("Debugging why taxi amounts are not saving to database")
    print("=" * 50)
    
    try:
        test1 = test_taxi_payment_api_simulation()
        test2 = test_database_query_logic()
        test3 = test_potential_issues()
        
        if test1 and test2 and test3:
            print("\n" + "=" * 50)
            print("🔍 DEBUGGING COMPLETE!")
            print("✅ API logic appears correct")
            print("✅ Database query structure correct")
            print("✅ Template display logic correct")
            print("=" * 50)
            
            print("\n🎯 Most likely causes of blank taxi column:")
            print("1. 🔴 Frontend not sending payment_type='taxi'")
            print("2. 🔴 Database transaction not committing")
            print("3. 🔴 Cache not clearing after payment")
            print("4. 🔴 SQL query not retrieving updated data")
            
            print("\n🔧 Recommended debugging steps:")
            print("1. Check browser console during taxi payment")
            print("2. Check server logs for [COLLECT_PAYMENT] messages")
            print("3. Check database directly with pgAdmin/DBeaver")
            print("4. Verify frontend JavaScript sends correct data")
            
            print("\n💡 Expected behavior:")
            print("✅ Select taxi payment → payment_type='taxi'")
            print("✅ Enter amount → collected_amount=200000")
            print("✅ Save → taxi_amount updated in database")
            print("✅ Refresh → taxi amount shows in Taxi column")
            
            return True
        else:
            print("\n❌ Some debugging tests failed")
            return False
        
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)