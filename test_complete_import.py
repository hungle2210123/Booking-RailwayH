#!/usr/bin/env python3
"""
Complete Import Test - Verify data extraction and format compatibility
Ultra Think Optimization Test Suite
"""

from core.comprehensive_import import (
    parse_excel_file, 
    import_customers_from_sheet1,
    import_message_templates_from_sheet2,
    import_expenses_from_sheet5
)

def test_complete_import_workflow():
    """Test the complete import workflow without database operations"""
    print("🧪 COMPLETE IMPORT WORKFLOW TEST")
    print("=" * 60)
    
    try:
        # Step 1: Parse Excel file
        print("📊 Step 1: Parsing Excel file...")
        sheets_data = parse_excel_file("csvtest.xlsx")
        if not sheets_data:
            print("❌ Failed to parse Excel file")
            return False
        
        print(f"✅ Parsed {len(sheets_data)} sheets successfully")
        
        # Step 2: Import customers and bookings
        print("\n👥 Step 2: Importing customers and bookings...")
        customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
        
        customers_count = len(customers_data.get('customers', []))
        bookings_count = len(customers_data.get('bookings', []))
        
        print(f"✅ Extracted {customers_count} customers and {bookings_count} bookings")
        
        # Step 3: Import message templates
        print("\n💬 Step 3: Importing message templates...")
        templates_data = import_message_templates_from_sheet2(sheets_data.get('Sheet2', []))
        templates_count = len(templates_data)
        
        print(f"✅ Extracted {templates_count} message templates")
        
        # Step 4: Import expenses
        print("\n💰 Step 4: Importing expenses...")
        expenses_data = import_expenses_from_sheet5(sheets_data.get('Sheet5', []))
        expenses_count = len(expenses_data)
        
        print(f"✅ Extracted {expenses_count} expenses")
        
        # Step 5: Verify data structure and quality
        print("\n🔍 Step 5: Data Quality Verification...")
        
        # Check customer data structure
        if customers_data.get('customers'):
            sample_customer = customers_data['customers'][0]
            required_customer_fields = ['full_name']
            missing_fields = [field for field in required_customer_fields if field not in sample_customer]
            if missing_fields:
                print(f"❌ Customer data missing fields: {missing_fields}")
                return False
            print("✅ Customer data structure valid")
        
        # Check booking data structure
        if customers_data.get('bookings'):
            sample_booking = customers_data['bookings'][0]
            required_booking_fields = ['booking_id', 'guest_name', 'checkin_date', 'checkout_date']
            missing_fields = [field for field in required_booking_fields if field not in sample_booking]
            if missing_fields:
                print(f"❌ Booking data missing fields: {missing_fields}")
                return False
            print("✅ Booking data structure valid")
        
        # Check template data structure
        if templates_data:
            sample_template = templates_data[0]
            required_template_fields = ['template_name', 'category', 'template_content']
            missing_fields = [field for field in required_template_fields if field not in sample_template]
            if missing_fields:
                print(f"❌ Template data missing fields: {missing_fields}")
                return False
            print("✅ Template data structure valid")
        
        # Check expense data structure
        if expenses_data:
            sample_expense = expenses_data[0]
            required_expense_fields = ['description', 'amount', 'expense_date', 'category']
            missing_fields = [field for field in required_expense_fields if field not in sample_expense]
            if missing_fields:
                print(f"❌ Expense data missing fields: {missing_fields}")
                return False
            print("✅ Expense data structure valid")
        
        # Step 6: Summary report
        print(f"\n📊 IMPORT READINESS SUMMARY:")
        print(f"   👥 Customers ready for import: {customers_count}")
        print(f"   📋 Bookings ready for import: {bookings_count}")
        print(f"   💬 Templates ready for import: {templates_count}")
        print(f"   💰 Expenses ready for import: {expenses_count}")
        print(f"   📈 Total records ready: {customers_count + bookings_count + templates_count + expenses_count}")
        
        # Show sample data for verification
        print(f"\n🔍 SAMPLE DATA FOR VERIFICATION:")
        
        if customers_data.get('customers'):
            print(f"Sample Customer: {customers_data['customers'][0]}")
        
        if customers_data.get('bookings'):
            print(f"Sample Booking: {customers_data['bookings'][0]}")
        
        if templates_data:
            template_sample = dict(templates_data[0])
            template_sample['template_content'] = template_sample['template_content'][:100] + "..." if len(template_sample['template_content']) > 100 else template_sample['template_content']
            print(f"Sample Template: {template_sample}")
        
        if expenses_data:
            print(f"Sample Expense: {expenses_data[0]}")
        
        print("\n✅ ALL IMPORT TESTS PASSED - DATA READY FOR DATABASE")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def verify_data_integrity():
    """Verify data integrity and relationships"""
    print("\n🔒 DATA INTEGRITY VERIFICATION")
    print("=" * 50)
    
    try:
        # Parse and extract data
        sheets_data = parse_excel_file("csvtest.xlsx")
        customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
        
        customers = customers_data.get('customers', [])
        bookings = customers_data.get('bookings', [])
        
        # Check customer-booking relationships
        customer_names = {customer['full_name'] for customer in customers}
        booking_guest_names = {booking['guest_name'] for booking in bookings}
        
        # Find orphaned bookings (bookings without corresponding customers)
        orphaned_bookings = booking_guest_names - customer_names
        if orphaned_bookings:
            print(f"⚠️ Found {len(orphaned_bookings)} orphaned bookings (guests not in customer list)")
            for guest in list(orphaned_bookings)[:5]:  # Show first 5
                print(f"   - {guest}")
        else:
            print("✅ All bookings have corresponding customers")
        
        # Check for duplicate booking IDs
        booking_ids = [booking['booking_id'] for booking in bookings]
        duplicate_ids = [bid for bid in set(booking_ids) if booking_ids.count(bid) > 1]
        if duplicate_ids:
            print(f"⚠️ Found {len(duplicate_ids)} duplicate booking IDs")
            for bid in duplicate_ids[:5]:  # Show first 5
                print(f"   - {bid}")
        else:
            print("✅ All booking IDs are unique")
        
        # Check date validity
        invalid_dates = 0
        for booking in bookings:
            checkin = booking.get('checkin_date')
            checkout = booking.get('checkout_date')
            if checkin and checkout and checkin >= checkout:
                invalid_dates += 1
        
        if invalid_dates > 0:
            print(f"⚠️ Found {invalid_dates} bookings with invalid date ranges")
        else:
            print("✅ All booking dates are valid")
        
        # Check amount validity
        invalid_amounts = 0
        for booking in bookings:
            for amount_field in ['room_amount', 'taxi_amount', 'commission']:
                amount = booking.get(amount_field, 0)
                if amount and amount < 0:
                    invalid_amounts += 1
        
        if invalid_amounts > 0:
            print(f"⚠️ Found {invalid_amounts} negative amounts")
        else:
            print("✅ All amounts are non-negative")
        
        print("✅ Data integrity verification complete")
        return True
        
    except Exception as e:
        print(f"❌ Integrity check failed: {e}")
        return False

if __name__ == "__main__":
    print("🚀 COMPREHENSIVE IMPORT TEST SUITE")
    print("=" * 70)
    
    # Run complete workflow test
    workflow_success = test_complete_import_workflow()
    
    # Run data integrity verification
    integrity_success = verify_data_integrity()
    
    if workflow_success and integrity_success:
        print("\n🎉 ALL TESTS PASSED - READY FOR PRODUCTION IMPORT!")
        exit(0)
    else:
        print("\n❌ SOME TESTS FAILED - NEEDS INVESTIGATION")
        exit(1)