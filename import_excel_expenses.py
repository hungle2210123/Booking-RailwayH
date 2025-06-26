#!/usr/bin/env python3
"""
Import Excel Data to Enhanced Expense Management System
Ultra Think Optimization - Complete data import and categorization
"""

import pandas as pd
import os
import sys
from pathlib import Path
from datetime import datetime, date
import re

def read_excel_data(file_path):
    """Read and analyze Excel data"""
    print("🔍 READING EXCEL DATA")
    print("=" * 50)
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return None
    
    try:
        # Read all sheets
        excel_data = pd.read_excel(file_path, sheet_name=None)
        print(f"✅ Found {len(excel_data)} sheets in Excel file")
        
        for sheet_name, df in excel_data.items():
            print(f"📋 Sheet '{sheet_name}': {len(df)} rows, {len(df.columns)} columns")
        
        return excel_data
    
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        return None

def categorize_expense(description):
    """Smart categorization of expenses based on description"""
    description_lower = description.lower() if description else ""
    
    # Define categories with Vietnamese keywords
    categories = {
        'room_supplies': ['xịt phòng', 'chậu ngâm', 'đồ dùng phòng', 'vệ sinh', 'làm sạch', 'khăn', 'ga giường', 'toilet'],
        'food_beverage': ['ăn', 'thức ăn', 'nước', 'coffee', 'cafe', 'beer', 'bia', 'đồ uống', 'ăn vặt', 'nướng', 'cơm'],
        'maintenance': ['sửa chữa', 'bảo trì', 'thay thế', 'lắp đặt', 'điện', 'nước', 'máy lạnh', 'wifi'],
        'transportation': ['taxi', 'xe', 'di chuyển', 'đi lại', 'xăng', 'grab', 'giao hàng'],
        'marketing': ['quảng cáo', 'booking', 'commission', 'hoa hồng', 'platform', 'website'],
        'utilities': ['điện', 'nước', 'internet', 'wifi', 'gas', 'garbage', 'rác'],
        'office_supplies': ['văn phòng', 'giấy', 'bút', 'máy in', 'mực in', 'stapler'],
        'guest_service': ['dịch vụ khách', 'đón tiễn', 'hỗ trợ khách', 'amenity'],
        'miscellaneous': ['khác', 'other', 'misc']
    }
    
    # Check each category
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in description_lower:
                return category
    
    return 'miscellaneous'  # Default category

def extract_expense_data(excel_data):
    """Extract and process expense data from all relevant sheets"""
    print("\n💰 EXTRACTING EXPENSE DATA")
    print("=" * 50)
    
    expenses = []
    
    # Process Sheet 5 (Expense Tracking) - Most relevant
    if 'Sheet5' in excel_data:
        sheet5 = excel_data['Sheet5']
        print(f"📊 Processing Sheet5 (Expense Tracking): {len(sheet5)} rows")
        
        for index, row in sheet5.iterrows():
            try:
                # Extract amount (assuming it's in a column with numeric values)
                amount = None
                description = ""
                expense_date = datetime.now().date()
                
                # Try to find amount and description in the row
                for col in sheet5.columns:
                    value = row[col]
                    if pd.notna(value):
                        if isinstance(value, (int, float)) and value > 0:
                            amount = float(value)
                        elif isinstance(value, str) and len(value) > 3:
                            description = str(value)
                        elif isinstance(value, (datetime, date)):
                            expense_date = value if isinstance(value, date) else value.date()
                
                if amount and amount > 0 and description:
                    category = categorize_expense(description)
                    
                    expenses.append({
                        'description': description,
                        'amount': amount,
                        'date': expense_date,
                        'category': category,
                        'collector': 'IMPORTED',
                        'source_sheet': 'Sheet5',
                        'source_row': index + 1
                    })
                    
                    print(f"✅ Extracted: {description[:30]}... - {amount:,.0f}đ [{category}]")
            
            except Exception as e:
                print(f"⚠️ Error processing row {index + 1}: {e}")
    
    # Process Sheet 1 (Booking Data) for commission and taxi expenses
    if 'Sheet1' in excel_data:
        sheet1 = excel_data['Sheet1']
        print(f"📊 Processing Sheet1 (Booking Data): {len(sheet1)} rows")
        
        for index, row in sheet1.iterrows():
            try:
                # Extract commission as expense
                commission = row.get('Hoa hồng', 0) if 'Hoa hồng' in row else 0
                taxi = row.get('Taxi', 0) if 'Taxi' in row else 0
                guest_name = row.get('Tên người đặt', 'Unknown Guest') if 'Tên người đặt' in row else 'Unknown Guest'
                booking_id = row.get('Số đặt phòng', f'BOOKING_{index}') if 'Số đặt phòng' in row else f'BOOKING_{index}'
                
                # Extract dates
                expense_date = datetime.now().date()
                if 'Check-in Date' in row and pd.notna(row['Check-in Date']):
                    try:
                        expense_date = pd.to_datetime(row['Check-in Date']).date()
                    except:
                        pass
                
                # Add commission as marketing expense
                if commission and commission > 0:
                    expenses.append({
                        'description': f'Hoa hồng booking {booking_id} - {guest_name}',
                        'amount': float(commission),
                        'date': expense_date,
                        'category': 'marketing',
                        'collector': 'IMPORTED',
                        'source_sheet': 'Sheet1',
                        'source_row': index + 1
                    })
                    print(f"✅ Commission: {guest_name} - {commission:,.0f}đ")
                
                # Add taxi as transportation expense
                if taxi and taxi > 0:
                    expenses.append({
                        'description': f'Taxi cho khách {guest_name} - {booking_id}',
                        'amount': float(taxi),
                        'date': expense_date,
                        'category': 'transportation',
                        'collector': 'IMPORTED',
                        'source_sheet': 'Sheet1',
                        'source_row': index + 1
                    })
                    print(f"✅ Taxi: {guest_name} - {taxi:,.0f}đ")
            
            except Exception as e:
                print(f"⚠️ Error processing booking row {index + 1}: {e}")
    
    print(f"\n📊 TOTAL EXTRACTED: {len(expenses)} expense entries")
    return expenses

def import_to_database(expenses):
    """Import expenses to PostgreSQL database"""
    print("\n💾 IMPORTING TO DATABASE")
    print("=" * 50)
    
    # Add the project root to Python path
    sys.path.append('/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized')
    
    try:
        from core.logic_postgresql import add_expense_to_database
        
        imported_count = 0
        failed_count = 0
        
        for expense in expenses:
            try:
                if add_expense_to_database(expense):
                    imported_count += 1
                    print(f"✅ Imported: {expense['description'][:40]}...")
                else:
                    failed_count += 1
                    print(f"❌ Failed: {expense['description'][:40]}...")
            
            except Exception as e:
                failed_count += 1
                print(f"❌ Error importing expense: {e}")
        
        print(f"\n📊 IMPORT RESULTS:")
        print(f"✅ Successfully imported: {imported_count}")
        print(f"❌ Failed to import: {failed_count}")
        print(f"📈 Success rate: {(imported_count / len(expenses) * 100):.1f}%")
        
        return imported_count > 0
    
    except ImportError as e:
        print(f"❌ Cannot import database functions: {e}")
        print("Make sure you're running this from the Flask app directory")
        return False

def generate_category_summary(expenses):
    """Generate summary by category"""
    print("\n📊 EXPENSE CATEGORY SUMMARY")
    print("=" * 50)
    
    category_stats = {}
    
    for expense in expenses:
        category = expense['category']
        if category not in category_stats:
            category_stats[category] = {'count': 0, 'total_amount': 0}
        
        category_stats[category]['count'] += 1
        category_stats[category]['total_amount'] += expense['amount']
    
    # Sort by total amount descending
    sorted_categories = sorted(category_stats.items(), 
                             key=lambda x: x[1]['total_amount'], 
                             reverse=True)
    
    total_amount = sum(stats['total_amount'] for stats in category_stats.values())
    total_count = sum(stats['count'] for stats in category_stats.values())
    
    print(f"{'Category':<20} {'Count':<8} {'Amount (VND)':<15} {'%':<8}")
    print("-" * 55)
    
    for category, stats in sorted_categories:
        percentage = (stats['total_amount'] / total_amount * 100) if total_amount > 0 else 0
        print(f"{category:<20} {stats['count']:<8} {stats['total_amount']:>13,.0f} {percentage:>6.1f}%")
    
    print("-" * 55)
    print(f"{'TOTAL':<20} {total_count:<8} {total_amount:>13,.0f} {'100.0%':>8}")

def create_sample_data_file():
    """Create a sample CSV file with the imported data structure"""
    print("\n📁 CREATING SAMPLE DATA FILE")
    print("=" * 50)
    
    sample_data = [
        {
            'description': 'Mua 2 chai xịt phòng',
            'amount': 100000,
            'date': '2025-06-20',
            'category': 'room_supplies',
            'collector': 'LOC LE'
        },
        {
            'description': 'Ăn trưa nhân viên',
            'amount': 150000,
            'date': '2025-06-20',
            'category': 'food_beverage',
            'collector': 'THAO LE'
        },
        {
            'description': 'Sửa chữa điện lạnh phòng 101',
            'amount': 300000,
            'date': '2025-06-19',
            'category': 'maintenance',
            'collector': 'LOC LE'
        },
        {
            'description': 'Taxi đón khách sân bay',
            'amount': 250000,
            'date': '2025-06-19',
            'category': 'transportation',
            'collector': 'THAO LE'
        },
        {
            'description': 'Hoa hồng booking Booking.com',
            'amount': 75000,
            'date': '2025-06-18',
            'category': 'marketing',
            'collector': 'LOC LE'
        }
    ]
    
    df = pd.DataFrame(sample_data)
    output_file = 'imported_expenses_sample.csv'
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"✅ Sample data saved to: {output_file}")

def main():
    """Main execution function"""
    print("🚀 EXCEL TO EXPENSE IMPORT - ULTRA THINK OPTIMIZATION")
    print("=" * 70)
    
    excel_file_path = "/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized/csvtest.xlsx"
    
    # Step 1: Read Excel data
    excel_data = read_excel_data(excel_file_path)
    if not excel_data:
        print("❌ Cannot proceed without Excel data")
        return False
    
    # Step 2: Extract expense data
    expenses = extract_expense_data(excel_data)
    if not expenses:
        print("❌ No expense data found to import")
        return False
    
    # Step 3: Generate summary
    generate_category_summary(expenses)
    
    # Step 4: Create sample file
    create_sample_data_file()
    
    # Step 5: Ask user for import confirmation
    print(f"\n🤔 IMPORT CONFIRMATION")
    print("=" * 50)
    print(f"Found {len(expenses)} expense entries ready to import.")
    print("Categories found:", set(exp['category'] for exp in expenses))
    
    # For automated import (uncomment the line below to enable database import)
    # import_success = import_to_database(expenses)
    print("\n✅ ANALYSIS COMPLETE")
    print("To import to database, uncomment the import_to_database() call in main()")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)