#!/usr/bin/env python3
"""
Simple Excel file analyzer without external dependencies
"""
import struct
import zipfile
import xml.etree.ElementTree as ET
import os

def analyze_xlsx_file(filepath):
    """
    Analyze XLSX file structure by reading the internal XML files
    """
    print("=== ANALYZING XLSX FILE ===")
    print(f"File: {filepath}")
    print(f"File size: {os.path.getsize(filepath)} bytes")
    print()
    
    try:
        with zipfile.ZipFile(filepath, 'r') as xlsx_file:
            # List all files in the XLSX archive
            print("=== XLSX INTERNAL FILES ===")
            for name in xlsx_file.namelist():
                print(f"  {name}")
            print()
            
            # Read the shared strings (contains text values)
            if 'xl/sharedStrings.xml' in xlsx_file.namelist():
                print("=== SHARED STRINGS (Text Values) ===")
                with xlsx_file.open('xl/sharedStrings.xml') as strings_file:
                    strings_xml = strings_file.read().decode('utf-8')
                    # Parse XML to extract text values
                    root = ET.fromstring(strings_xml)
                    strings = []
                    for si in root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si'):
                        t = si.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t')
                        if t is not None and t.text:
                            strings.append(t.text)
                    
                    print(f"Total text strings found: {len(strings)}")
                    print("Sample strings (first 20):")
                    for i, s in enumerate(strings[:20]):
                        print(f"  {i+1}: {s}")
                    print()
            
            # Read the main worksheet
            if 'xl/worksheets/sheet1.xml' in xlsx_file.namelist():
                print("=== WORKSHEET STRUCTURE ===")
                with xlsx_file.open('xl/worksheets/sheet1.xml') as sheet_file:
                    sheet_xml = sheet_file.read().decode('utf-8')
                    root = ET.fromstring(sheet_xml)
                    
                    # Count rows and cells
                    rows = root.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
                    print(f"Total rows found: {len(rows)}")
                    
                    if rows:
                        first_row = rows[0]
                        cells = first_row.findall('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}c')
                        print(f"Columns in first row: {len(cells)}")
                        
                        print("Cell references in first row:")
                        for cell in cells:
                            ref = cell.get('r', 'unknown')
                            cell_type = cell.get('t', 'number')
                            value_elem = cell.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v')
                            value = value_elem.text if value_elem is not None else 'empty'
                            print(f"  {ref}: {value} (type: {cell_type})")
            
    except Exception as e:
        print(f"Error analyzing XLSX file: {e}")
        return False
    
    return True

if __name__ == "__main__":
    analyze_xlsx_file("csvtest.xlsx")