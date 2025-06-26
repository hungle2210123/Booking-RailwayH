#!/usr/bin/env python3
"""
Detailed Excel file analyzer to understand expense data structure
"""
import zipfile
import xml.etree.ElementTree as ET

def analyze_expense_data(filepath):
    """
    Analyze the expense data structure from the Excel file
    """
    print("=== DETAILED EXPENSE DATA ANALYSIS ===")
    
    try:
        with zipfile.ZipFile(filepath, 'r') as xlsx_file:
            # First, get all shared strings (text values)
            shared_strings = []
            if 'xl/sharedStrings.xml' in xlsx_file.namelist():
                with xlsx_file.open('xl/sharedStrings.xml') as strings_file:
                    strings_xml = strings_file.read().decode('utf-8')
                    root = ET.fromstring(strings_xml)
                    for si in root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                        t = si.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                        if t is not None and t.text:
                            shared_strings.append(t.text)
            
            print(f"Total shared strings: {len(shared_strings)}")
            
            # Map header columns to their Vietnamese/English meanings
            print("\n=== COLUMN HEADERS (First 21 columns) ===")
            for i, header in enumerate(shared_strings[:21]):
                print(f"Column {chr(65+i)}: {header}")
            
            # Analyze sheets
            for sheet_num in range(1, 6):  # We have 5 sheets
                sheet_path = f'xl/worksheets/sheet{sheet_num}.xml'
                if sheet_path in xlsx_file.namelist():
                    print(f"\n=== ANALYZING SHEET {sheet_num} ===")
                    
                    with xlsx_file.open(sheet_path) as sheet_file:
                        sheet_xml = sheet_file.read().decode('utf-8')
                        root = ET.fromstring(sheet_xml)
                        
                        rows = root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
                        print(f"Rows in sheet {sheet_num}: {len(rows)}")
                        
                        if len(rows) > 1:  # Skip empty sheets
                            print(f"Sample data from first few rows:")
                            
                            for row_idx, row in enumerate(rows[:5]):  # First 5 rows
                                cells = row.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c')
                                row_data = []
                                
                                for cell in cells:
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
                                            value = value_elem.text
                                    else:
                                        value = 'empty'
                                    
                                    row_data.append(value)
                                
                                if row_data:  # Only show non-empty rows
                                    print(f"  Row {row_idx + 1}: {row_data[:10]}...")  # First 10 columns
            
            # Extract unique values that might be categories
            print(f"\n=== POTENTIAL EXPENSE CATEGORIES ===")
            
            # Look for category-like strings in shared strings
            categories = []
            expense_keywords = ['chi phí', 'expense', 'cost', 'fee', 'payment', 'tiền', 'thanh toán', 
                              'phí', 'giá', 'hóa đơn', 'bill', 'invoice', 'taxi', 'food', 'maintenance',
                              'repair', 'supplies', 'utilities', 'rent', 'insurance']
            
            for string in shared_strings:
                string_lower = string.lower()
                for keyword in expense_keywords:
                    if keyword in string_lower and len(string) < 50:  # Reasonable category length
                        categories.append(string)
                        break
            
            print("Potential expense categories found:")
            for cat in set(categories):  # Remove duplicates
                print(f"  - {cat}")
            
            # Look for date patterns
            print(f"\n=== DATE PATTERNS ===")
            date_patterns = []
            for string in shared_strings:
                if any(char.isdigit() for char in string) and ('/' in string or '-' in string):
                    if len(string) < 20:  # Reasonable date length
                        date_patterns.append(string)
            
            print("Potential date values:")
            for date in set(date_patterns[:10]):  # First 10 unique dates
                print(f"  - {date}")
            
            # Look for currency/amount patterns
            print(f"\n=== CURRENCY/AMOUNT PATTERNS ===")
            currency_patterns = []
            for string in shared_strings:
                if any(curr in string.lower() for curr in ['đ', 'vnd', '$', 'usd', 'eur', '₫']):
                    currency_patterns.append(string)
                elif string.replace(',', '').replace('.', '').isdigit() and len(string) > 3:
                    currency_patterns.append(string)
            
            print("Potential currency/amount values:")
            for curr in set(currency_patterns[:15]):  # First 15 unique amounts
                print(f"  - {curr}")
    
    except Exception as e:
        print(f"Error in detailed analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    analyze_expense_data("csvtest.xlsx")