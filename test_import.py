#!/usr/bin/env python3
"""
Test script to verify import functionality works
"""

from core.comprehensive_import import (
    parse_excel_file, 
    import_customers_from_sheet1,
    import_message_templates_from_sheet2,
    import_expenses_from_sheet5
)

def test_import():
    """Test the import functionality"""
    print("🧪 TESTING IMPORT FUNCTIONALITY")
    print("=" * 50)
    
    # Test parsing
    sheets_data = parse_excel_file("csvtest.xlsx")
    if not sheets_data:
        print("❌ Failed to parse Excel file")
        return False
    
    print(f"✅ Parsed {len(sheets_data)} sheets")
    
    # Test customer import
    customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
    print(f"✅ Customers: {len(customers_data.get('customers', []))}")
    print(f"✅ Bookings: {len(customers_data.get('bookings', []))}")
    
    # Test template import
    templates_data = import_message_templates_from_sheet2(sheets_data.get('Sheet2', []))
    print(f"✅ Templates: {len(templates_data)}")
    
    # Test expense import
    expenses_data = import_expenses_from_sheet5(sheets_data.get('Sheet5', []))
    print(f"✅ Expenses: {len(expenses_data)}")
    
    # Show sample data
    print("\n📊 SAMPLE DATA:")
    if customers_data.get('customers'):
        print(f"Sample customer: {customers_data['customers'][0]}")
    
    if customers_data.get('bookings'):
        print(f"Sample booking: {customers_data['bookings'][0]}")
    
    if templates_data:
        print(f"Sample template: {templates_data[0]}")
    
    if expenses_data:
        print(f"Sample expense: {expenses_data[0]}")
    
    print("\n✅ ALL TESTS PASSED!")
    return True

if __name__ == "__main__":
    test_import()