#!/usr/bin/env python3
"""
Read Excel file to understand template categorization structure
"""
import pandas as pd
import json

def read_excel_templates():
    try:
        # Read the Excel file
        file_path = "/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized/csvtest (1).xlsx"
        
        # Try to read all sheets
        excel_file = pd.ExcelFile(file_path)
        print(f"📊 Excel file sheets: {excel_file.sheet_names}")
        
        # Read each sheet
        for sheet_name in excel_file.sheet_names:
            print(f"\n📋 Reading sheet: {sheet_name}")
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            
            print(f"Columns: {list(df.columns)}")
            print(f"Shape: {df.shape}")
            print("First 10 rows:")
            print(df.head(10).to_string())
            print("\n" + "="*80)
        
    except Exception as e:
        print(f"Error reading Excel file: {e}")

if __name__ == "__main__":
    read_excel_templates()