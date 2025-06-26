#!/usr/bin/env python3
"""
Test the decimal parsing function directly
"""

import re
from datetime import datetime, date

def clean_and_validate_data(data, data_type='string'):
    """
    Clean and validate data based on expected type
    """
    print(f"🔍 FUNCTION START: data={repr(data)}, type={data_type}")
    
    if data is None or data == '':
        print("→ Early return: None or empty")
        return None
    
    try:
        if data_type == 'decimal':
            print("→ Processing decimal type")
            if isinstance(data, (int, float)):
                result = float(data)
                print(f"→ int/float: returning {result}")
                return result
            elif isinstance(data, str):
                print("→ string processing...")
                data = data.strip()
                print(f"→ after strip: {repr(data)}")
                if not data or data.lower() in ['', 'nan', 'none', 'null', 'n/a']:
                    print("→ invalid string: returning 0.0")
                    return 0.0
                # Remove currency symbols and commas, keep dots and digits
                cleaned = re.sub(r'[^0-9.-]', '', data)
                print(f"→ after regex: {repr(cleaned)}")
                if cleaned and cleaned not in ['', '.', '-']:
                    try:
                        result = float(cleaned)
                        print(f"→ float conversion: SUCCESS {result}")
                        return result
                    except ValueError as e:
                        print(f"→ ValueError: {e}")
                        return 0.0
                print("→ cleaned value invalid: returning 0.0")
                return 0.0
            print("→ unknown type: returning 0.0")
            return 0.0
        else:
            print(f"→ non-decimal type: returning data")
            return data
    
    except Exception as e:
        print(f"→ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    print("→ END: returning data")
    return data

if __name__ == "__main__":
    print("🧪 TESTING DECIMAL PARSING")
    print("=" * 40)
    
    test_values = ['642200.0', '312000.0', '0.0', '', None]
    
    for value in test_values:
        print(f"\n🔍 Testing: {repr(value)}")
        result = clean_and_validate_data(value, 'decimal')
        print(f"✅ Result: {result}")
        print("-" * 30)