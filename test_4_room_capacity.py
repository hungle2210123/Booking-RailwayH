#!/usr/bin/env python3
"""
Test script to verify 4-room hotel capacity functionality
Tests the key functions to ensure they properly handle the hotel's 4-room limit
"""

import sys
import os
import pandas as pd
from datetime import datetime, timedelta, date

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import core logic functions
try:
    from core.logic_postgresql import get_overall_calendar_day_info, get_daily_activity
    from core.dashboard_routes import detect_overcrowded_days, process_arrival_notifications, process_departure_notifications
    print("✅ Successfully imported PostgreSQL logic modules")
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

def create_test_data():
    """Create test booking data to simulate various scenarios"""
    today = date.today()
    
    test_bookings = [
        # 4 guests checking in today (at capacity)
        {'Tên người đặt': 'Nguyen Van A', 'Số đặt phòng': 'TEST001', 'Check-in Date': today, 'Check-out Date': today + timedelta(days=2), 'Tổng thanh toán': 500000, 'Hoa hồng': 50000, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Tran Thi B', 'Số đặt phòng': 'TEST002', 'Check-in Date': today, 'Check-out Date': today + timedelta(days=2), 'Tổng thanh toán': 600000, 'Hoa hồng': 60000, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Le Van C', 'Số đặt phòng': 'TEST003', 'Check-in Date': today, 'Check-out Date': today + timedelta(days=2), 'Tổng thanh toán': 700000, 'Hoa hồng': 0, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Pham Thi D', 'Số đặt phòng': 'TEST004', 'Check-in Date': today, 'Check-out Date': today + timedelta(days=2), 'Tổng thanh toán': 800000, 'Hoa hồng': 200000, 'Tình trạng': 'OK'},
        
        # 6 guests trying to check in tomorrow (overcrowded!)
        {'Tên người đặt': 'Hoang Van E', 'Số đặt phòng': 'TEST005', 'Check-in Date': today + timedelta(days=1), 'Check-out Date': today + timedelta(days=3), 'Tổng thanh toán': 500000, 'Hoa hồng': 0, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Vu Thi F', 'Số đặt phòng': 'TEST006', 'Check-in Date': today + timedelta(days=1), 'Check-out Date': today + timedelta(days=3), 'Tổng thanh toán': 600000, 'Hoa hồng': 80000, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Do Van G', 'Số đặt phòng': 'TEST007', 'Check-in Date': today + timedelta(days=1), 'Check-out Date': today + timedelta(days=3), 'Tổng thanh toán': 700000, 'Hoa hồng': 0, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Bui Thi H', 'Số đặt phòng': 'TEST008', 'Check-in Date': today + timedelta(days=1), 'Check-out Date': today + timedelta(days=3), 'Tổng thanh toán': 800000, 'Hoa hồng': 160000, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Mai Van I', 'Số đặt phòng': 'TEST009', 'Check-in Date': today + timedelta(days=1), 'Check-out Date': today + timedelta(days=3), 'Tổng thanh toán': 900000, 'Hoa hồng': 180000, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Cao Thi J', 'Số đặt phòng': 'TEST010', 'Check-in Date': today + timedelta(days=1), 'Check-out Date': today + timedelta(days=3), 'Tổng thanh toán': 1000000, 'Hoa hồng': 200000, 'Tình trạng': 'OK'},
        
        # 2 guests checking out tomorrow
        {'Tên người đặt': 'Dao Van K', 'Số đặt phòng': 'TEST011', 'Check-in Date': today - timedelta(days=1), 'Check-out Date': today + timedelta(days=1), 'Tổng thanh toán': 500000, 'Hoa hồng': 0, 'Tình trạng': 'OK'},
        {'Tên người đặt': 'Ly Thi L', 'Số đặt phòng': 'TEST012', 'Check-in Date': today - timedelta(days=1), 'Check-out Date': today + timedelta(days=1), 'Tổng thanh toán': 600000, 'Hoa hồng': 70000, 'Tình trạng': 'OK'},
    ]
    
    df = pd.DataFrame(test_bookings)
    
    # Convert date columns
    df['Check-in Date'] = pd.to_datetime(df['Check-in Date'])
    df['Check-out Date'] = pd.to_datetime(df['Check-out Date'])
    
    return df

def test_calendar_day_info():
    """Test calendar day info function with 4-room capacity"""
    print("\n🏨 Testing Calendar Day Info (4-room capacity)")
    print("=" * 50)
    
    df = create_test_data()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    # Test today (should show 4/4 occupied - at capacity)
    today_info = get_overall_calendar_day_info(df, today.strftime('%Y-%m-%d'), total_capacity=4)
    print(f"📅 Today ({today.strftime('%Y-%m-%d')}):")
    print(f"   - Occupied units: {today_info['occupied_units']}/4")
    print(f"   - Available units: {today_info['available_units']}")
    print(f"   - Status: {today_info['status_text']} ({today_info['status_color']})")
    print(f"   - Arrivals: {today_info['arrivals_count']}")
    print(f"   - Daily revenue: {today_info['daily_revenue']:,.0f}đ")
    print(f"   - Commission total: {today_info['commission_total']:,.0f}đ")
    print(f"   - Revenue minus commission: {today_info['revenue_minus_commission']:,.0f}đ")
    
    # Test tomorrow (should show overcrowded)
    tomorrow_info = get_overall_calendar_day_info(df, tomorrow.strftime('%Y-%m-%d'), total_capacity=4)
    print(f"\n📅 Tomorrow ({tomorrow.strftime('%Y-%m-%d')}):")
    print(f"   - Occupied units: {tomorrow_info['occupied_units']}/4")
    print(f"   - Available units: {tomorrow_info['available_units']}")
    print(f"   - Status: {tomorrow_info['status_text']} ({tomorrow_info['status_color']})")
    print(f"   - Arrivals: {tomorrow_info['arrivals_count']}")
    print(f"   - Daily revenue: {tomorrow_info['daily_revenue']:,.0f}đ")
    
    # Verify capacity constraints
    assert today_info['occupied_units'] == 4, f"Expected 4 occupied units today, got {today_info['occupied_units']}"
    assert today_info['available_units'] == 0, f"Expected 0 available units today, got {today_info['available_units']}"
    assert tomorrow_info['arrivals_count'] == 6, f"Expected 6 arrivals tomorrow, got {tomorrow_info['arrivals_count']}"
    
    print("✅ Calendar day info test passed!")
    return True

def test_overcrowded_detection():
    """Test overcrowded day detection (>4 guests)"""
    print("\n🚨 Testing Overcrowded Day Detection")
    print("=" * 40)
    
    df = create_test_data()
    overcrowded_days = detect_overcrowded_days(df)
    
    print(f"Found {len(overcrowded_days)} overcrowded days:")
    for day in overcrowded_days:
        print(f"   📆 {day['date']}: {day['guest_count']} guests (>{4})")
        print(f"      Alert level: {day['alert_level']} ({day['alert_color']})")
        print(f"      Daily total: {day['daily_total']:,.0f}đ")
        print(f"      Days from today: {day['days_from_today']}")
    
    # Verify overcrowded detection
    assert len(overcrowded_days) > 0, "Should detect at least one overcrowded day"
    
    # Check that tomorrow is detected as overcrowded (6 guests > 4 rooms)
    tomorrow_found = False
    for day in overcrowded_days:
        if day['days_from_today'] == 1 and day['guest_count'] == 6:
            tomorrow_found = True
            break
    
    assert tomorrow_found, "Tomorrow should be detected as overcrowded with 6 guests"
    
    print("✅ Overcrowded detection test passed!")
    return True

def test_notification_priorities():
    """Test arrival/departure notifications with commission prioritization"""
    print("\n🔔 Testing Notification Priorities")
    print("=" * 35)
    
    df = create_test_data()
    
    # Test arrival notifications
    arrival_notifications = process_arrival_notifications(df)
    print(f"📥 Arrival notifications: {len(arrival_notifications)}")
    
    for i, notification in enumerate(arrival_notifications[:5]):  # Show first 5
        commission = notification.get('Hoa hồng', 0)
        commission_level = notification.get('commission_level', 'none')
        priority = notification.get('priority', 'normal')
        
        print(f"   {i+1}. {notification['guest_name']} ({notification['days_until']} days)")
        print(f"      Commission: {commission:,.0f}đ ({commission_level}) - Priority: {priority}")
    
    # Test departure notifications  
    departure_notifications = process_departure_notifications(df)
    print(f"\n📤 Departure notifications: {len(departure_notifications)}")
    
    for i, notification in enumerate(departure_notifications):
        commission = notification.get('Hoa hồng', 0)
        commission_level = notification.get('commission_level', 'none')
        
        print(f"   {i+1}. {notification['guest_name']} ({notification['days_until']} days)")
        print(f"      Commission: {commission:,.0f}đ ({commission_level})")
    
    # Verify high commission guests are prioritized
    if arrival_notifications:
        first_arrival = arrival_notifications[0]
        first_commission = first_arrival.get('Hoa hồng', 0)
        first_priority = first_arrival.get('priority', 'normal')
        
        print(f"\n🏆 Top priority arrival: {first_arrival['guest_name']}")
        print(f"   Commission: {first_commission:,.0f}đ")
        print(f"   Priority level: {first_priority}")
        
        # High commission guests (>150,000đ) should have critical/urgent priority
        high_commission_guests = [n for n in arrival_notifications if n.get('Hoa hồng', 0) > 150000]
        if high_commission_guests:
            for guest in high_commission_guests:
                assert guest['priority'] in ['critical', 'urgent'], f"High commission guest {guest['guest_name']} should have critical/urgent priority"
    
    print("✅ Notification priority test passed!")
    return True

def test_daily_activity():
    """Test daily activity tracking"""
    print("\n📊 Testing Daily Activity Tracking")
    print("=" * 35)
    
    df = create_test_data()
    today = date.today()
    tomorrow = today + timedelta(days=1)
    
    # Test today's activity
    today_activity = get_daily_activity(df, today)
    print(f"📅 Today's activity:")
    print(f"   - Arrivals: {len(today_activity['arrivals'])}")
    print(f"   - Departures: {len(today_activity['departures'])}")
    print(f"   - Staying: {len(today_activity['staying'])}")
    
    # Test tomorrow's activity
    tomorrow_activity = get_daily_activity(df, tomorrow)
    print(f"\n📅 Tomorrow's activity:")
    print(f"   - Arrivals: {len(tomorrow_activity['arrivals'])}")
    print(f"   - Departures: {len(tomorrow_activity['departures'])}")
    print(f"   - Staying: {len(tomorrow_activity['staying'])}")
    
    # Verify activity counts match expectations
    assert len(today_activity['arrivals']) == 4, f"Expected 4 arrivals today, got {len(today_activity['arrivals'])}"
    assert len(tomorrow_activity['arrivals']) == 6, f"Expected 6 arrivals tomorrow, got {len(tomorrow_activity['arrivals'])}"
    assert len(tomorrow_activity['departures']) == 2, f"Expected 2 departures tomorrow, got {len(tomorrow_activity['departures'])}"
    
    print("✅ Daily activity test passed!")
    return True

def main():
    """Run all tests"""
    print("🏨 HOTEL 4-ROOM CAPACITY TESTING")
    print("=" * 60)
    print("Testing PostgreSQL-optimized hotel booking system")
    print("Hotel capacity: 4 rooms maximum")
    print("=" * 60)
    
    try:
        # Run all tests
        test_calendar_day_info()
        test_overcrowded_detection()
        test_notification_priorities()
        test_daily_activity()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED!")
        print("✅ 4-room hotel capacity functionality working correctly")
        print("✅ Overcrowded day detection working")
        print("✅ Commission prioritization working")
        print("✅ Daily activity tracking working")
        print("=" * 60)
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)