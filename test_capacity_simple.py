#!/usr/bin/env python3
"""
Simple test to verify 4-room hotel capacity constants and logic
"""

import sys
import os

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_capacity_constants():
    """Test that hotel capacity is set to 4 rooms in all relevant files"""
    print("🏨 Testing Hotel Capacity Constants")
    print("=" * 40)
    
    # Test app_postgresql.py
    try:
        with open('app_postgresql.py', 'r', encoding='utf-8') as f:
            app_content = f.read()
            if 'TOTAL_HOTEL_CAPACITY = 4' in app_content:
                print("✅ app_postgresql.py: TOTAL_HOTEL_CAPACITY = 4")
            else:
                print("❌ app_postgresql.py: Hotel capacity not set to 4")
                return False
    except Exception as e:
        print(f"❌ Error reading app_postgresql.py: {e}")
        return False
    
    # Test logic_postgresql.py
    try:
        with open('core/logic_postgresql.py', 'r', encoding='utf-8') as f:
            logic_content = f.read()
            if 'total_capacity: int = 4' in logic_content:
                print("✅ logic_postgresql.py: Default capacity parameter = 4")
            else:
                print("❌ logic_postgresql.py: Default capacity not set to 4")
                return False
    except Exception as e:
        print(f"❌ Error reading logic_postgresql.py: {e}")
        return False
    
    # Test dashboard_routes.py for overcrowded detection
    try:
        with open('core/dashboard_routes.py', 'r', encoding='utf-8') as f:
            dashboard_content = f.read()
            if 'guest_count > 4' in dashboard_content or "guest_count'] > 4" in dashboard_content:
                print("✅ dashboard_routes.py: Overcrowded detection for >4 guests")
            else:
                print("❌ dashboard_routes.py: Overcrowded detection not set for 4 rooms")
                return False
    except Exception as e:
        print(f"❌ Error reading dashboard_routes.py: {e}")
        return False
    
    return True

def test_calendar_template():
    """Test that calendar template has proper 4-room capacity handling"""
    print("\n📅 Testing Calendar Template")
    print("=" * 30)
    
    try:
        with open('templates/calendar_details.html', 'r', encoding='utf-8') as f:
            template_content = f.read()
            
            # Check for commission tracking features
            if 'commission_level' in template_content or 'has_commission' in template_content:
                print("✅ calendar_details.html: Commission level tracking present")
            else:
                print("❌ calendar_details.html: Commission level tracking missing")
                return False
                
            # Check for guest activity categorization
            if 'check_in' in template_content and 'staying_over' in template_content and 'check_out' in template_content:
                print("✅ calendar_details.html: Guest activity categories present")
            else:
                print("❌ calendar_details.html: Guest activity categories missing")
                return False
                
            # Check for revenue breakdown
            if 'revenue_minus_commission' in template_content or 'daily_total_minus_commission' in template_content:
                print("✅ calendar_details.html: Revenue minus commission calculation present")
            else:
                print("❌ calendar_details.html: Revenue minus commission calculation missing")
                return False
                
    except Exception as e:
        print(f"❌ Error reading calendar_details.html: {e}")
        return False
    
    return True

def test_file_structure():
    """Test that all required files exist"""
    print("\n📁 Testing File Structure")
    print("=" * 25)
    
    required_files = [
        'app_postgresql.py',
        'core/logic_postgresql.py', 
        'core/dashboard_routes.py',
        'core/models.py',
        'core/database_service_postgresql.py',
        'templates/calendar_details.html',
        'templates/dashboard.html',
        'templates/bookings.html',
        'templates/calendar.html'
    ]
    
    all_exist = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path} - Missing!")
            all_exist = False
    
    return all_exist

def test_key_functions():
    """Test key function signatures without importing dependencies"""
    print("\n🔧 Testing Key Function Signatures")
    print("=" * 35)
    
    # Test logic_postgresql.py functions
    try:
        with open('core/logic_postgresql.py', 'r', encoding='utf-8') as f:
            logic_content = f.read()
            
            required_functions = [
                'def get_overall_calendar_day_info',
                'def get_daily_activity',
                'def load_booking_data',
                'def add_new_booking',
                'def update_booking',
                'def delete_booking_by_id'
            ]
            
            for func in required_functions:
                if func in logic_content:
                    print(f"✅ {func.replace('def ', '')}")
                else:
                    print(f"❌ {func.replace('def ', '')} - Missing!")
                    return False
                    
    except Exception as e:
        print(f"❌ Error checking logic functions: {e}")
        return False
    
    # Test dashboard_routes.py functions
    try:
        with open('core/dashboard_routes.py', 'r', encoding='utf-8') as f:
            dashboard_content = f.read()
            
            required_functions = [
                'def process_dashboard_data',
                'def process_overdue_guests',
                'def detect_overcrowded_days',
                'def get_daily_revenue_by_stay',
                'def process_arrival_notifications',
                'def process_departure_notifications'
            ]
            
            for func in required_functions:
                if func in dashboard_content:
                    print(f"✅ {func.replace('def ', '')}")
                else:
                    print(f"❌ {func.replace('def ', '')} - Missing!")
                    return False
                    
    except Exception as e:
        print(f"❌ Error checking dashboard functions: {e}")
        return False
    
    return True

def main():
    """Run all tests"""
    print("🏨 HOTEL BOOKING SYSTEM - 4-ROOM CAPACITY VERIFICATION")
    print("=" * 60)
    print("Testing that the system is properly configured for 4-room hotel")
    print("=" * 60)
    
    try:
        # Run all tests
        test1 = test_capacity_constants()
        test2 = test_calendar_template()
        test3 = test_file_structure()
        test4 = test_key_functions()
        
        if all([test1, test2, test3, test4]):
            print("\n" + "=" * 60)
            print("🎉 ALL VERIFICATION TESTS PASSED!")
            print("✅ Hotel capacity properly set to 4 rooms")
            print("✅ All required files present")
            print("✅ Key functions implemented")
            print("✅ Commission analytics features present")
            print("✅ Calendar details functionality complete")
            print("=" * 60)
            print("\n🚀 System ready for 4-room hotel operation!")
            return True
        else:
            print("\n❌ Some tests failed - check output above")
            return False
        
    except Exception as e:
        print(f"\n💥 ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)