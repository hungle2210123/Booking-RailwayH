#!/usr/bin/env python3
"""
Comprehensive Data Import System - Ultra Think Optimization
Import customers, costs, and message templates from Excel with complete validation
"""

import zipfile
import xml.etree.ElementTree as ET
import os
import sys
from datetime import datetime, date
import re
from typing import Dict, List, Any, Optional, Union

# Add the project root to Python path
sys.path.append('/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized')

def parse_excel_file(filepath: str) -> Dict[str, List[List[Any]]]:
    """
    Parse Excel file using native XML parsing (no pandas dependency)
    Returns organized data by sheet
    """
    print("🔍 PARSING EXCEL FILE")
    print("=" * 50)
    
    try:
        with zipfile.ZipFile(filepath, 'r') as xlsx_file:
            # Get shared strings (text values)
            shared_strings = []
            if 'xl/sharedStrings.xml' in xlsx_file.namelist():
                with xlsx_file.open('xl/sharedStrings.xml') as strings_file:
                    strings_xml = strings_file.read().decode('utf-8')
                    root = ET.fromstring(strings_xml)
                    for si in root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                        t = si.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                        if t is not None and t.text:
                            shared_strings.append(t.text)
                        else:
                            shared_strings.append('')
            
            print(f"✅ Found {len(shared_strings)} shared strings")
            
            # Parse each sheet
            sheets_data = {}
            for sheet_num in range(1, 6):  # Sheets 1-5
                sheet_path = f'xl/worksheets/sheet{sheet_num}.xml'
                if sheet_path in xlsx_file.namelist():
                    print(f"📋 Processing Sheet {sheet_num}")
                    
                    with xlsx_file.open(sheet_path) as sheet_file:
                        sheet_xml = sheet_file.read().decode('utf-8')
                        root = ET.fromstring(sheet_xml)
                        
                        # Extract row data
                        rows_data = []
                        rows = root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
                        
                        for row in rows:
                            row_data = []
                            cells = row.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c')
                            
                            # Build complete row with proper column mapping
                            max_col = 0
                            cell_map = {}
                            
                            for cell in cells:
                                # Get column reference (A1, B1, etc.)
                                ref = cell.get('r', '')
                                if ref:
                                    # Extract column letter and convert to number
                                    col_letters = ''.join(c for c in ref if c.isalpha())
                                    col_num = 0
                                    for c in col_letters:
                                        col_num = col_num * 26 + (ord(c.upper()) - ord('A') + 1)
                                    col_num -= 1  # Convert to 0-based
                                    
                                    max_col = max(max_col, col_num)
                                    
                                    # Get cell value
                                    cell_type = cell.get('t', 'number')
                                    value_elem = cell.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                                    
                                    if value_elem is not None:
                                        if cell_type == 's':  # String reference
                                            try:
                                                string_index = int(value_elem.text)
                                                if string_index < len(shared_strings):
                                                    value = shared_strings[string_index]
                                                else:
                                                    value = f"String_Index_{string_index}"
                                            except (ValueError, IndexError):
                                                value = value_elem.text
                                        else:
                                            # Try to parse as number
                                            try:
                                                value = float(value_elem.text)
                                                # If it's a whole number, convert to int
                                                if value.is_integer():
                                                    value = int(value)
                                            except ValueError:
                                                value = value_elem.text
                                    else:
                                        value = None
                                    
                                    cell_map[col_num] = value
                            
                            # Build complete row array
                            if cell_map:  # Only add non-empty rows
                                row_array = []
                                for i in range(max_col + 1):
                                    row_array.append(cell_map.get(i, None))
                                rows_data.append(row_array)
                        
                        sheets_data[f'Sheet{sheet_num}'] = rows_data
                        print(f"   ✅ {len(rows_data)} rows extracted")
            
            return sheets_data
            
    except Exception as e:
        print(f"❌ Error parsing Excel file: {e}")
        import traceback
        traceback.print_exc()
        return {}

def clean_and_validate_data(data: Any, data_type: str = 'string') -> Any:
    """
    Clean and validate data based on expected type
    """
    if data is None:
        if data_type == 'decimal':
            return 0.0
        return None
    
    if data == '':
        if data_type == 'decimal':
            return 0.0
        return None
    
    try:
        if data_type == 'string':
            return str(data).strip() if data else None
        elif data_type == 'email':
            email = str(data).strip().lower() if data else None
            if email and '@' in email and '.' in email:
                return email
            return None
        elif data_type == 'phone':
            phone = str(data).strip() if data else None
            if phone:
                # Remove common phone formatting
                import re  # Ensure re is available
                phone = re.sub(r'[^\d+]', '', phone)
                return phone if len(phone) >= 8 else None
            return None
        elif data_type == 'decimal':
            if isinstance(data, (int, float)):
                return float(data)
            elif isinstance(data, str):
                data = data.strip()
                if not data or data.lower() in ['', 'nan', 'none', 'null', 'n/a']:
                    return 0.0
                # Remove currency symbols and commas, keep dots and digits
                import re  # Ensure re is available in local scope
                cleaned = re.sub(r'[^0-9.-]', '', data)
                if cleaned and cleaned not in ['', '.', '-']:
                    try:
                        return float(cleaned)
                    except ValueError:
                        return 0.0
                return 0.0
            return 0.0
        elif data_type == 'date':
            if isinstance(data, (int, float)):
                # Handle Excel serial number dates (days since 1900-01-01)
                try:
                    if data > 0 and data < 100000:  # Reasonable range for Excel dates
                        # Excel serial date epoch is 1900-01-01, but Excel incorrectly treats 1900 as a leap year
                        from datetime import timedelta
                        excel_epoch = datetime(1899, 12, 30)  # Adjusted for Excel's leap year bug
                        parsed_date = excel_epoch + timedelta(days=data)
                        print(f"✅ Excel serial date parsed: {data} -> {parsed_date.date()}")
                        return parsed_date.date()
                except Exception as e:
                    print(f"❌ Error parsing Excel date {data}: {e}")
                    return None
            elif isinstance(data, str):
                data = data.strip()
                if not data or data.lower() in ['', 'nan', 'none', 'null', 'n/a']:
                    return None
                    
                # Vietnamese date pattern first
                if 'ngày' in data and 'tháng' in data and 'năm' in data:
                    # Parse Vietnamese format: "ngày 30 tháng 5 năm 2025"
                    try:
                        import re  # Ensure re is available
                        match = re.search(r'ngày (\d+) tháng (\d+) năm (\d+)', data)
                        if match:
                            day, month, year = match.groups()
                            parsed = datetime(int(year), int(month), int(day))
                            print(f"✅ Vietnamese date parsed: '{data}' -> {parsed.date()}")
                            return parsed.date()
                    except Exception as e:
                        print(f"❌ Error parsing Vietnamese date '{data}': {e}")
                
                # Comprehensive date format list for CSV data
                date_formats = [
                    '%Y-%m-%d',           # 2025-05-30 (primary format)
                    '%Y-%m-%d %H:%M:%S',  # 2025-05-30 10:30:00
                    '%d/%m/%Y',           # 30/05/2025
                    '%m/%d/%Y',           # 05/30/2025
                    '%d-%m-%Y',           # 30-05-2025
                    '%Y/%m/%d',           # 2025/05/30
                    '%d %b %Y',           # 30 May 2025
                    '%d %B %Y',           # 30 May 2025
                    '%b %d, %Y',          # May 30, 2025
                    '%B %d, %Y',          # May 30, 2025
                    '%d tháng %m, %Y',    # 30 tháng 5, 2025
                    '%d tháng %m %Y'      # 30 tháng 5 2025
                ]
                
                for fmt in date_formats:
                    try:
                        parsed = datetime.strptime(data, fmt)
                        print(f"✅ Date parsed: '{data}' -> {parsed.date()} using format {fmt}")
                        return parsed.date()
                    except ValueError:
                        continue
                        
                # Try parsing with pandas as fallback
                try:
                    import pandas as pd
                    parsed = pd.to_datetime(data, errors='raise')
                    print(f"✅ Date parsed with pandas: '{data}' -> {parsed.date()}")
                    return parsed.date()
                except:
                    pass
                    
                print(f"⚠️ Could not parse date: '{data}'")
                return None
            elif isinstance(data, datetime):
                return data.date()
            elif isinstance(data, date):
                return data
            return None
        elif data_type == 'datetime':
            if isinstance(data, str):
                # Try various datetime formats
                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y']:
                    try:
                        return datetime.strptime(data, fmt)
                    except ValueError:
                        continue
            elif isinstance(data, datetime):
                return data
            return None
        elif data_type == 'boolean':
            if isinstance(data, bool):
                return data
            elif isinstance(data, str):
                return data.lower() in ['true', '1', 'yes', 'y', 'ok', 'completed']
            elif isinstance(data, (int, float)):
                return bool(data)
            return False
    
    except Exception as e:
        print(f"❌ EXCEPTION in clean_and_validate_data: {e} for data={repr(data)}, type={data_type}")
        import traceback
        traceback.print_exc()
        return None
    
    return data

def import_customers_from_sheet1(sheet_data: List[List[Any]]) -> List[Dict[str, Any]]:
    """
    Import customer/booking data from Sheet 1
    Ultra optimized with complete validation
    """
    print("\n👥 IMPORTING CUSTOMERS & BOOKINGS")
    print("=" * 50)
    
    if not sheet_data or len(sheet_data) < 2:
        print("❌ No customer data found in Sheet 1")
        return []
    
    # Expected columns based on analysis
    headers = sheet_data[0] if sheet_data else []
    customers = []
    bookings = []
    
    # Column mapping (prioritize exact column names for dates)
    col_map = {}
    for i, header in enumerate(headers):
        if header:
            header = str(header).strip()
            if 'Số đặt phòng' in header:
                col_map['booking_id'] = i
            elif 'Tên người đặt' in header:
                col_map['guest_name'] = i
            elif 'Tên chỗ nghỉ' in header:
                col_map['property_name'] = i
            elif header == 'Check-in Date':  # EXACT match for primary date columns
                col_map['checkin_date'] = i
                print(f"🎯 Found Check-in Date at column {i}")
            elif header == 'Check-out Date':  # EXACT match for primary date columns  
                col_map['checkout_date'] = i
                print(f"🎯 Found Check-out Date at column {i}")
            elif 'Tổng thanh toán' in header:
                col_map['room_amount'] = i  # Map Excel "Total Payment" to PostgreSQL room_amount
                print(f"🎯 Found Tổng thanh toán (Total Payment) at column {i} -> room_amount")
            elif 'Giá mỗi đêm' in header:
                col_map['per_night_rate'] = i  # Keep per-night rate separate for reference
            elif 'Hoa hồng' in header:
                col_map['commission'] = i
            elif 'Taxi' in header:
                col_map['taxi_amount'] = i
            elif 'Người thu tiền' in header:
                col_map['collector'] = i
            elif 'Tình trạng' in header:
                col_map['status'] = i
            elif 'Ghi chú' in header:
                col_map['notes'] = i
    
    # Fallback for date columns if exact matches not found
    if 'checkin_date' not in col_map:
        for i, header in enumerate(headers):
            if header and any(keyword in str(header).lower() for keyword in ['checkin', 'check-in', 'ngày đến', 'check in']):
                col_map['checkin_date'] = i
                print(f"🔄 Fallback: Found checkin date at column {i}")
                break
    
    if 'checkout_date' not in col_map:
        for i, header in enumerate(headers):
            if header and any(keyword in str(header).lower() for keyword in ['checkout', 'check-out', 'ngày đi', 'check out']):
                col_map['checkout_date'] = i  
                print(f"🔄 Fallback: Found checkout date at column {i}")
                break
    
    print(f"📊 Column mapping found: {col_map}")
    print(f"📊 Available headers: {headers}")
    
    # Check if we found date columns
    if 'checkin_date' not in col_map:
        print("⚠️ WARNING: checkin_date column not found!")
    if 'checkout_date' not in col_map:
        print("⚠️ WARNING: checkout_date column not found!")
    
    # Process data rows
    unique_guests = {}  # Track unique guests
    processed_bookings = []
    
    for row_idx, row in enumerate(sheet_data[1:], 1):  # Skip header
        if not row or not any(row):  # Skip empty rows
            continue
        
        try:
            # Extract data with validation
            booking_id = clean_and_validate_data(
                row[col_map.get('booking_id', 0)] if col_map.get('booking_id', 0) < len(row) else None,
                'string'
            )
            
            guest_name = clean_and_validate_data(
                row[col_map.get('guest_name', 1)] if col_map.get('guest_name', 1) < len(row) else None,
                'string'
            )
            
            if not booking_id or not guest_name:
                print(f"⚠️ Row {row_idx}: Missing booking ID or guest name - skipping")
                continue
            
            # Extract other fields
            checkin_date = clean_and_validate_data(
                row[col_map.get('checkin_date', 3)] if col_map.get('checkin_date', 3) < len(row) else None,
                'date'
            )
            
            checkout_date = clean_and_validate_data(
                row[col_map.get('checkout_date', 4)] if col_map.get('checkout_date', 4) < len(row) else None,
                'date'
            )
            
            room_amount = clean_and_validate_data(
                row[col_map.get('room_amount', 8)] if col_map.get('room_amount', 8) < len(row) else None,
                'decimal'
            ) or 0.0
            
            commission = clean_and_validate_data(
                row[col_map.get('commission', 15)] if col_map.get('commission', 15) < len(row) else None,
                'decimal'
            ) or 0.0
            
            taxi_amount = clean_and_validate_data(
                row[col_map.get('taxi_amount', 20)] if col_map.get('taxi_amount', 20) < len(row) else None,
                'decimal'
            ) or 0.0
            
            collector = clean_and_validate_data(
                row[col_map.get('collector', 19)] if col_map.get('collector', 19) < len(row) else None,
                'string'
            )
            
            status = clean_and_validate_data(
                row[col_map.get('status', 6)] if col_map.get('status', 6) < len(row) else None,
                'string'
            ) or 'confirmed'
            
            notes = clean_and_validate_data(
                row[col_map.get('notes', 18)] if col_map.get('notes', 18) < len(row) else None,
                'string'
            )
            # Handle 'nan' values
            if notes and str(notes).lower() in ['nan', 'none', 'null']:
                notes = None
            
            # Create guest record if not exists
            guest_key = guest_name.lower().strip()
            if guest_key not in unique_guests:
                unique_guests[guest_key] = {
                    'full_name': guest_name,
                    'email': None,  # Not available in this sheet
                    'phone': None,  # Not available in this sheet
                    'nationality': None,
                    'passport_number': None
                }
            
            # Create booking record
            booking_data = {
                'booking_id': booking_id,
                'guest_name': guest_name,
                'checkin_date': checkin_date,
                'checkout_date': checkout_date,
                'room_amount': room_amount,
                'taxi_amount': taxi_amount,
                'commission': commission,
                'collected_amount': 0.0,  # Will be updated from payment data
                'collector': collector,
                'booking_status': status if status else 'confirmed',
                'booking_notes': notes
            }
            
            processed_bookings.append(booking_data)
            print(f"✅ Row {row_idx}: {guest_name} - {booking_id}")
            
        except Exception as e:
            print(f"❌ Row {row_idx}: Error processing - {e}")
            continue
    
    customers = list(unique_guests.values())
    
    print(f"📊 IMPORT SUMMARY:")
    print(f"   👥 Customers: {len(customers)}")
    print(f"   📋 Bookings: {len(processed_bookings)}")
    
    return {
        'customers': customers,
        'bookings': processed_bookings
    }

def import_message_templates_from_sheet2(sheet_data: List[List[Any]]) -> List[Dict[str, Any]]:
    """
    Import message templates from Sheet 2
    """
    print("\n💬 IMPORTING MESSAGE TEMPLATES")
    print("=" * 50)
    
    if not sheet_data or len(sheet_data) < 2:
        print("❌ No template data found in Sheet 2")
        return []
    
    templates = []
    headers = sheet_data[0] if sheet_data else []
    
    # Column mapping for templates
    col_map = {}
    for i, header in enumerate(headers):
        if header:
            header = str(header).strip().lower()
            if 'label' in header:
                col_map['name'] = i
            elif 'message' in header:
                col_map['content'] = i
            elif any(cat in header for cat in ['don phong', 'welcome', 'arrival', 'check']):
                col_map['category'] = i
    
    # Process template rows
    for row_idx, row in enumerate(sheet_data[1:], 1):  # Skip header
        if not row or not any(row):
            continue
        
        try:
            template_name = clean_and_validate_data(
                row[col_map.get('name', 0)] if col_map.get('name', 0) < len(row) else None,
                'string'
            )
            
            template_content = clean_and_validate_data(
                row[col_map.get('content', 1)] if col_map.get('content', 1) < len(row) else None,
                'string'
            )
            
            category = clean_and_validate_data(
                row[col_map.get('category', 2)] if col_map.get('category', 2) < len(row) else None,
                'string'
            ) or 'general'
            
            if not template_name or not template_content:
                print(f"⚠️ Row {row_idx}: Missing template name or content - skipping")
                continue
            
            # Clean up template name
            template_name = template_name.strip()
            if template_name.isdigit() or template_name == 'DEFAULT':
                template_name = f"Template_{row_idx}_{category}"
            
            template_data = {
                'template_name': template_name,
                'category': category.lower().replace(' ', '_'),
                'template_content': template_content
            }
            
            templates.append(template_data)
            print(f"✅ Template: {template_name} [{category}]")
            
        except Exception as e:
            print(f"❌ Row {row_idx}: Error processing template - {e}")
            continue
    
    print(f"📊 Imported {len(templates)} message templates")
    return templates

def import_expenses_from_sheet5(sheet_data: List[List[Any]]) -> List[Dict[str, Any]]:
    """
    Import expense data from Sheet 5
    """
    print("\n💰 IMPORTING EXPENSES")
    print("=" * 50)
    
    if not sheet_data or len(sheet_data) < 2:
        print("❌ No expense data found in Sheet 5")
        return []
    
    expenses = []
    headers = sheet_data[0] if sheet_data else []
    
    # Smart categorization function
    def categorize_expense(description):
        if not description:
            return 'miscellaneous'
        
        description_lower = description.lower()
        
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
        
        for category, keywords in categories.items():
            for keyword in keywords:
                if keyword in description_lower:
                    return category
        
        return 'miscellaneous'
    
    # Process expense rows
    for row_idx, row in enumerate(sheet_data[1:], 1):  # Skip header
        if not row or not any(row):
            continue
        
        try:
            # Extract data from row (flexible approach since sheet structure may vary)
            description = None
            amount = None
            expense_date = None
            
            for cell in row:
                if cell is None:
                    continue
                
                # Try to identify description (string, length > 3)
                if isinstance(cell, str) and len(cell) > 3 and not description:
                    if not any(keyword in cell.lower() for keyword in ['amount', 'created', 'date']):
                        description = cell
                
                # Try to identify amount (number > 0)
                elif isinstance(cell, (int, float)) and cell > 0 and not amount:
                    amount = float(cell)
                
                # Try to identify date
                elif isinstance(cell, str) and '-' in cell and not expense_date:
                    try:
                        # Try to parse as date
                        for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S']:
                            try:
                                parsed = datetime.strptime(cell.split()[0], fmt)
                                expense_date = parsed.date()
                                break
                            except ValueError:
                                continue
                    except:
                        pass
            
            if not description or not amount or amount <= 0:
                print(f"⚠️ Row {row_idx}: Missing description or invalid amount - skipping")
                continue
            
            if not expense_date:
                expense_date = datetime.now().date()
            
            category = categorize_expense(description)
            
            expense_data = {
                'description': description,
                'amount': amount,
                'expense_date': expense_date,
                'category': category,
                'collector': 'IMPORTED'
            }
            
            expenses.append(expense_data)
            print(f"✅ Expense: {description[:30]}... - {amount:,.0f}đ [{category}]")
            
        except Exception as e:
            print(f"❌ Row {row_idx}: Error processing expense - {e}")
            continue
    
    print(f"📊 Imported {len(expenses)} expenses")
    return expenses

def save_to_database(customers_data: List[Dict], templates_data: List[Dict], expenses_data: List[Dict]) -> Dict[str, Any]:
    """
    Save all imported data to PostgreSQL database using Flask-aware database module
    """
    print("\n💾 SAVING TO DATABASE WITH FLASK CONTEXT")
    print("=" * 50)
    
    try:
        from core.database_import import comprehensive_database_import
        
        # Use the Flask-aware database import function
        results = comprehensive_database_import(customers_data, templates_data, expenses_data)
        
        if 'error' in results:
            return results
        
        # Convert results to expected format for compatibility
        legacy_results = {
            'customers': results['customers'].get('imported', 0) + results['customers'].get('updated', 0),
            'bookings': results['bookings'].get('imported', 0) + results['bookings'].get('updated', 0),
            'templates': results['templates'].get('imported', 0) + results['templates'].get('updated', 0),
            'expenses': results['expenses'].get('imported', 0),
            'errors': []
        }
        
        # Collect all errors
        for category, data in results.items():
            if isinstance(data, dict) and data.get('errors'):
                legacy_results['errors'].extend(data['errors'])
        
        return legacy_results
        
    except Exception as e:
        print(f"❌ Database import error: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e)}

def main():
    """
    Main execution function - Ultra Think Optimization
    """
    print("🚀 COMPREHENSIVE DATA IMPORT - ULTRA THINK OPTIMIZATION")
    print("=" * 70)
    
    excel_file_path = "/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized/csvtest.xlsx"
    
    if not os.path.exists(excel_file_path):
        print(f"❌ Excel file not found: {excel_file_path}")
        return False
    
    # Step 1: Parse Excel file
    sheets_data = parse_excel_file(excel_file_path)
    if not sheets_data:
        print("❌ Failed to parse Excel file")
        return False
    
    # Step 2: Import customers and bookings from Sheet 1
    customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
    
    # Step 3: Import message templates from Sheet 2
    templates_data = import_message_templates_from_sheet2(sheets_data.get('Sheet2', []))
    
    # Step 4: Import expenses from Sheet 5
    expenses_data = import_expenses_from_sheet5(sheets_data.get('Sheet5', []))
    
    # Step 5: Save to database
    results = save_to_database(customers_data, templates_data, expenses_data)
    
    print("\n✅ COMPREHENSIVE IMPORT COMPLETE")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)