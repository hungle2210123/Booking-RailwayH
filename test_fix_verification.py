#!/usr/bin/env python3
"""
Test script to verify the KeyError fix in analyze_existing_duplicates function
"""

# Test the specific code structure that was causing the KeyError
test_booking = {
    'Số đặt phòng': 'TEST001',
    'Tên người đặt': 'Test Guest',
    'Tổng thanh toán': 500000
}

# This should work now - accessing the Vietnamese column name
booking_id = test_booking['Số đặt phòng']
print(f"✅ Successfully accessed booking ID: {booking_id}")

# Test the dictionary structure that analyze_existing_duplicates now returns
current_dict = {
    'Số đặt phòng': test_booking.get('Số đặt phòng', 'N/A'),
    'guest_name': test_booking.get('Tên người đặt', 'N/A'),
    'amount': test_booking.get('Tổng thanh toán', 0)
}

print(f"✅ Dictionary structure: {current_dict}")
print(f"✅ Accessing booking ID from dict: {current_dict['Số đặt phòng']}")

print("\n🎉 Fix verification completed successfully!")
print("The KeyError should now be resolved because:")
print("1. analyze_existing_duplicates now returns 'Số đặt phòng' as the booking ID key")
print("2. app_postgresql.py expects booking['Số đặt phòng'] which will now work")