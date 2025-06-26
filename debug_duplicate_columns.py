#!/usr/bin/env python3
"""
Debug script to check DataFrame column names and data types
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from core.logic_postgresql import load_booking_data
import pandas as pd

def debug_dataframe_structure():
    """Debug the DataFrame structure returned by load_booking_data"""
    print("🔍 Debugging DataFrame structure for duplicate analysis...")
    
    try:
        # Load the data just like the API does
        df = load_booking_data()
        
        print(f"📊 DataFrame Shape: {df.shape}")
        print(f"📋 DataFrame Columns: {list(df.columns)}")
        print(f"📈 Data Types:")
        for col, dtype in df.dtypes.items():
            print(f"  - {col}: {dtype}")
        
        # Check for the specific columns used in analyze_existing_duplicates
        required_columns = ['Tên người đặt', 'Check-in Date']
        print(f"\n🎯 Checking required columns for duplicate analysis:")
        for col in required_columns:
            if col in df.columns:
                print(f"  ✅ {col}: Found")
                # Check data samples
                if not df[col].empty:
                    print(f"    📝 Sample values: {df[col].dropna().head(3).tolist()}")
                    print(f"    🔢 Non-null count: {df[col].notna().sum()}/{len(df)}")
                else:
                    print(f"    ⚠️  Column is empty")
            else:
                print(f"  ❌ {col}: Missing")
        
        # Check for guest names to see if there are any duplicates
        if 'Tên người đặt' in df.columns:
            guest_names = df['Tên người đặt'].dropna()
            unique_names = guest_names.unique()
            print(f"\n👥 Guest name analysis:")
            print(f"  - Total bookings: {len(guest_names)}")
            print(f"  - Unique guests: {len(unique_names)}")
            print(f"  - Potential duplicates: {len(guest_names) - len(unique_names)}")
            
            # Show guests with multiple bookings
            name_counts = guest_names.value_counts()
            multiple_bookings = name_counts[name_counts > 1]
            if not multiple_bookings.empty:
                print(f"  📋 Guests with multiple bookings:")
                for name, count in multiple_bookings.head(5).items():
                    print(f"    - {name}: {count} bookings")
            else:
                print(f"  ℹ️  No guests with multiple bookings found")
        
        # Check Check-in Date format
        if 'Check-in Date' in df.columns:
            checkin_dates = df['Check-in Date'].dropna()
            print(f"\n📅 Check-in Date analysis:")
            print(f"  - Non-null dates: {len(checkin_dates)}")
            if not checkin_dates.empty:
                print(f"  - Sample dates: {checkin_dates.head(3).tolist()}")
                print(f"  - Date type: {type(checkin_dates.iloc[0])}")
                
                # Try to convert dates if they're strings
                try:
                    pd_dates = pd.to_datetime(checkin_dates)
                    print(f"  ✅ Dates can be converted to datetime")
                    print(f"  - Date range: {pd_dates.min()} to {pd_dates.max()}")
                except Exception as e:
                    print(f"  ❌ Date conversion error: {e}")
        
        return df
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    debug_dataframe_structure()