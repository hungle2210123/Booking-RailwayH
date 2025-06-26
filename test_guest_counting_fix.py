#!/usr/bin/env python3
"""
Test script to verify the guest counting double-counting fix
"""
import pandas as pd
from datetime import datetime, date
import sys
import os

# Add the parent directory to sys.path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.logic_postgresql import get_daily_activity, get_overall_calendar_day_info

def test_guest_counting_fix():
    """Test that guests checking in are not double-counted in staying list"""
    
    # Create test data with guests checking in today
    test_data = pd.DataFrame([
        {
            'Tên người đặt': 'Guest A',
            'Số đặt phòng': 'BK001',
            'Check-in Date': '2025-06-26',  # Today (checking in)
            'Check-out Date': '2025-06-28',  # Leaving in 2 days
            'Tình trạng': 'OK',
            'Tổng thanh toán': 500000,
            'Hoa hồng': 50000
        },
        {
            'Tên người đặt': 'Guest B',
            'Số đặt phòng': 'BK002',
            'Check-in Date': '2025-06-25',  # Yesterday (staying)
            'Check-out Date': '2025-06-27',  # Leaving tomorrow
            'Tình trạng': 'OK',
            'Tổng thanh toán': 400000,
            'Hoa hồng': 0
        },
        {
            'Tên người đặt': 'Guest C',
            'Số đặt phòng': 'BK003',
            'Check-in Date': '2025-06-24',  # 2 days ago (staying)
            'Check-out Date': '2025-06-26',  # Leaving today
            'Tình trạng': 'OK',
            'Tổng thanh toán': 300000,
            'Hoa hồng': 30000
        }
    ])
    
    # Convert dates
    test_data['Check-in Date'] = pd.to_datetime(test_data['Check-in Date'])
    test_data['Check-out Date'] = pd.to_datetime(test_data['Check-out Date'])
    
    # Test for today (2025-06-26)
    target_date = date(2025, 6, 26)
    
    print("=== GUEST COUNTING FIX TEST ===")
    print(f"Testing for date: {target_date}")
    print("\nTest Data:")
    for _, guest in test_data.iterrows():
        checkin = guest['Check-in Date'].date()
        checkout = guest['Check-out Date'].date()
        print(f"  {guest['Tên người đặt']}: {checkin} -> {checkout}")
    
    # Get daily activity
    activity = get_daily_activity(test_data, target_date)
    
    print(f"\n=== RESULTS ===")
    print(f"Check-ins today: {len(activity['arrivals'])}")
    for guest in activity['arrivals']:
        print(f"  - {guest['Tên người đặt']} (arriving)")
    
    print(f"\nStaying guests: {len(activity['staying'])}")
    for guest in activity['staying']:
        print(f"  - {guest['Tên người đặt']} (staying from previous days)")
    
    print(f"\nCheck-outs today: {len(activity['departures'])}")
    for guest in activity['departures']:
        print(f"  - {guest['Tên người đặt']} (departing)")
    
    # Check for double counting
    arrivals_names = [g['Tên người đặt'] for g in activity['arrivals']]
    staying_names = [g['Tên người đặt'] for g in activity['staying']]
    departures_names = [g['Tên người đặt'] for g in activity['departures']]
    
    # Check for overlaps
    arrivals_staying_overlap = set(arrivals_names) & set(staying_names)
    arrivals_departures_overlap = set(arrivals_names) & set(departures_names)
    staying_departures_overlap = set(staying_names) & set(departures_names)
    
    print(f"\n=== DOUBLE COUNTING CHECK ===")
    print(f"Arrivals & Staying overlap: {arrivals_staying_overlap}")
    print(f"Arrivals & Departures overlap: {arrivals_departures_overlap}")  
    print(f"Staying & Departures overlap: {staying_departures_overlap}")
    
    # Total unique guests
    all_guests = set(arrivals_names + staying_names + departures_names)
    total_count_method1 = len(activity['arrivals']) + len(activity['staying']) + len(activity['departures'])
    total_count_method2 = len(all_guests)
    
    print(f"\nTotal guest count (sum of lists): {total_count_method1}")
    print(f"Total unique guests: {total_count_method2}")
    
    # Test overall calendar info
    print(f"\n=== CALENDAR DAY INFO ===")
    day_info = get_overall_calendar_day_info(test_data, target_date.strftime('%Y-%m-%d'), 4)
    print(f"Occupied units: {day_info['occupied_units']}")
    print(f"Available units: {day_info['available_units']}")
    print(f"Arrivals count: {day_info['arrivals_count']}")
    print(f"Departures count: {day_info['departures_count']}")
    print(f"Staying count: {day_info['staying_count']}")
    
    # Verify the fix worked
    if len(arrivals_staying_overlap) == 0:
        print(f"\n✅ SUCCESS: No double counting detected!")
        print(f"✅ Guests checking in today appear only in arrivals list")
        print(f"✅ Guests staying from previous days appear only in staying list")
    else:
        print(f"\n❌ FAILED: Double counting still detected!")
        print(f"❌ Guests in both arrivals and staying: {arrivals_staying_overlap}")
    
    # Expected results:
    # - Guest A: Should be in arrivals only (checking in today)
    # - Guest B: Should be in staying only (checked in yesterday, staying tonight)
    # - Guest C: Should be in departures only (leaving today)
    # - Total unique guests: 3 (no double counting)
    # - Total counting method1: 3 (arrivals:1 + staying:1 + departures:1)
    
    print(f"\n=== EXPECTED vs ACTUAL ===")
    expected_arrivals = ["Guest A"]
    expected_staying = ["Guest B"] 
    expected_departures = ["Guest C"]
    
    print(f"Expected arrivals: {expected_arrivals}")
    print(f"Actual arrivals: {arrivals_names}")
    print(f"✅ Arrivals match: {arrivals_names == expected_arrivals}")
    
    print(f"Expected staying: {expected_staying}")
    print(f"Actual staying: {staying_names}")
    print(f"✅ Staying match: {staying_names == expected_staying}")
    
    print(f"Expected departures: {expected_departures}")
    print(f"Actual departures: {departures_names}")
    print(f"✅ Departures match: {departures_names == expected_departures}")

if __name__ == "__main__":
    test_guest_counting_fix()