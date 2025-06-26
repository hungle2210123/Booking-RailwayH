#!/usr/bin/env python3
"""
Debug script to test the analyze_existing_duplicates function directly
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from core.logic_postgresql import load_booking_data, analyze_existing_duplicates
import pandas as pd
import time

def test_analyze_function():
    """Test the analyze_existing_duplicates function step by step"""
    print("🧪 Testing analyze_existing_duplicates function...")
    
    try:
        # Step 1: Load data
        print("📊 Step 1: Loading data...")
        start_time = time.time()
        df = load_booking_data()
        load_time = time.time() - start_time
        print(f"  ✅ Data loaded in {load_time:.2f} seconds")
        print(f"  📈 DataFrame shape: {df.shape}")
        
        if df.empty:
            print("  ⚠️  DataFrame is empty, cannot test duplicate analysis")
            return
        
        # Step 2: Check required columns
        print("\n🔍 Step 2: Checking required columns...")
        required_cols = ['Tên người đặt', 'Check-in Date']
        for col in required_cols:
            if col in df.columns:
                print(f"  ✅ {col}: Found")
            else:
                print(f"  ❌ {col}: Missing")
                print(f"  📋 Available columns: {list(df.columns)}")
                return
        
        # Step 3: Test analyze function
        print("\n⚙️  Step 3: Running analyze_existing_duplicates...")
        start_time = time.time()
        
        # Call the function with debug prints
        result = analyze_existing_duplicates_with_debug(df)
        
        analysis_time = time.time() - start_time
        print(f"  ✅ Analysis completed in {analysis_time:.2f} seconds")
        
        # Step 4: Show results
        print(f"\n📊 Step 4: Analysis Results:")
        print(f"  - Total duplicate groups: {result.get('total_duplicates', 0)}")
        print(f"  - Groups found: {len(result.get('duplicate_groups', []))}")
        
        if result.get('duplicate_groups'):
            print(f"  📝 Sample duplicate groups:")
            for i, group in enumerate(result['duplicate_groups'][:3]):
                print(f"    Group {i+1}: {group.get('guest_name', 'N/A')} - {group.get('date_difference_days', 'N/A')} days apart")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in test: {e}")
        import traceback
        traceback.print_exc()

def analyze_existing_duplicates_with_debug(df: pd.DataFrame):
    """Debug version of analyze_existing_duplicates with extra logging"""
    print("    🔍 Starting duplicate analysis...")
    
    if df.empty:
        print("    ⚠️  DataFrame is empty")
        return {'duplicate_groups': [], 'total_duplicates': 0}
    
    try:
        # Check unique guests
        unique_guests = df['Tên người đặt'].unique()
        print(f"    👥 Found {len(unique_guests)} unique guests")
        
        duplicate_groups = []
        
        for i, name in enumerate(unique_guests):
            if i % 10 == 0:  # Progress update every 10 guests
                print(f"    🔄 Processing guest {i+1}/{len(unique_guests)}: {name}")
            
            guest_bookings = df[df['Tên người đặt'] == name].sort_values('Check-in Date')
            
            if len(guest_bookings) > 1:
                print(f"    🔍 Guest '{name}' has {len(guest_bookings)} bookings")
                
                # Check if any bookings are within 3 days of each other
                for j in range(len(guest_bookings) - 1):
                    current = guest_bookings.iloc[j]
                    next_booking = guest_bookings.iloc[j + 1]
                    
                    try:
                        # Convert dates to datetime if needed
                        current_date = pd.to_datetime(current['Check-in Date'])
                        next_date = pd.to_datetime(next_booking['Check-in Date'])
                        
                        date_diff = (next_date - current_date).days
                        
                        if abs(date_diff) <= 3:
                            print(f"      🎯 Duplicate found: {date_diff} days apart")
                            duplicate_groups.append({
                                'guest_name': name,
                                'bookings': [current.to_dict(), next_booking.to_dict()],
                                'date_difference_days': date_diff
                            })
                    except Exception as date_error:
                        print(f"      ❌ Date processing error for {name}: {date_error}")
        
        print(f"    ✅ Analysis complete: Found {len(duplicate_groups)} duplicate groups")
        
        return {
            'duplicate_groups': duplicate_groups,
            'total_duplicates': len(duplicate_groups)
        }
        
    except Exception as e:
        print(f"    ❌ Error analyzing duplicates: {e}")
        import traceback
        traceback.print_exc()
        return {'duplicate_groups': [], 'total_duplicates': 0}

if __name__ == "__main__":
    test_analyze_function()