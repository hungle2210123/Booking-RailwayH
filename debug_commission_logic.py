#!/usr/bin/env python3
"""
Debug Commission Logic in Collect Payment API
"""

def test_commission_logic():
    """Test the exact commission logic from the API"""
    
    print("🔍 TESTING COMMISSION LOGIC FROM API")
    print("=" * 50)
    
    # Test cases that match real usage
    test_cases = [
        {
            'name': 'Normal commission (50000)',
            'commission_amount': 50000,
            'commission_type': 'normal'
        },
        {
            'name': 'Zero commission with normal type',
            'commission_amount': 0,
            'commission_type': 'normal'
        },
        {
            'name': 'None commission with normal type',
            'commission_amount': None,
            'commission_type': 'normal'
        },
        {
            'name': 'No commission type none',
            'commission_amount': 0,
            'commission_type': 'none'
        },
        {
            'name': 'Commission 75000 with normal',
            'commission_amount': 75000,
            'commission_type': 'normal'
        }
    ]
    
    for test in test_cases:
        print(f"\n🧪 Test: {test['name']}")
        print(f"   Input: commission_amount={test['commission_amount']}, commission_type='{test['commission_type']}'")
        
        # Simulate the exact API logic
        update_data = {}
        commission_amount = test['commission_amount']
        commission_type = test['commission_type']
        
        # EXACT LOGIC FROM API (lines 805-810)
        if commission_type == 'none':
            update_data['commission'] = 0
            print("   → Setting commission to 0 (no commission)")
        elif commission_amount is not None and commission_amount > 0:
            update_data['commission'] = float(commission_amount)
            print(f"   → Setting commission to {commission_amount}")
        else:
            print("   → ❌ NO COMMISSION UPDATE! (Logic gap)")
        
        print(f"   Result: update_data = {update_data}")
        
        # Check if commission would be saved
        if 'commission' in update_data:
            print(f"   ✅ COMMISSION SAVED: {update_data['commission']}")
        else:
            print(f"   ❌ COMMISSION NOT SAVED!")

def test_frontend_data():
    """Test what frontend actually sends"""
    
    print("\n🔍 TESTING FRONTEND DATA SCENARIOS")
    print("=" * 50)
    
    # Scenarios from your testing
    scenarios = [
        {
            'name': 'User enters 75000 commission',
            'request_data': {
                'commission_amount': 75000,
                'commission_type': 'normal'
            }
        },
        {
            'name': 'User checks "no commission"',
            'request_data': {
                'commission_amount': 0,
                'commission_type': 'none'
            }
        },
        {
            'name': 'User enters 0 but leaves normal type',
            'request_data': {
                'commission_amount': 0,
                'commission_type': 'normal'
            }
        },
        {
            'name': 'Frontend sends null commission',
            'request_data': {
                'commission_amount': None,
                'commission_type': 'normal'
            }
        }
    ]
    
    for scenario in scenarios:
        print(f"\n🎯 Scenario: {scenario['name']}")
        data = scenario['request_data']
        
        commission_amount = data['commission_amount'] 
        commission_type = data['commission_type']
        
        print(f"   Frontend sends: commission_amount={commission_amount}, commission_type='{commission_type}'")
        
        # Apply API logic
        update_data = {}
        
        if commission_type == 'none':
            update_data['commission'] = 0
            result = "✅ SAVED as 0"
        elif commission_amount is not None and commission_amount > 0:
            update_data['commission'] = float(commission_amount)
            result = f"✅ SAVED as {commission_amount}"
        else:
            result = "❌ NOT SAVED (falls through logic)"
        
        print(f"   API Result: {result}")

def identify_fix():
    """Identify the exact fix needed"""
    
    print("\n🔧 COMMISSION LOGIC FIX NEEDED")
    print("=" * 50)
    
    print("❌ CURRENT BROKEN LOGIC:")
    print("""
    if commission_type == 'none':
        update_data['commission'] = 0
    elif commission_amount is not None and commission_amount > 0:  # ← BUG HERE!
        update_data['commission'] = float(commission_amount)
    # ELSE: Nothing happens - commission not saved!
    """)
    
    print("✅ FIXED LOGIC SHOULD BE:")
    print("""
    if commission_type == 'none':
        update_data['commission'] = 0
    elif commission_amount is not None:  # ← REMOVE > 0 check
        update_data['commission'] = float(commission_amount)
    """)
    
    print("\n🎯 THE ISSUE:")
    print("- API only saves commission if amount > 0")
    print("- If user enters 0 commission with 'normal' type, it's ignored")
    print("- If frontend sends null/undefined, it's ignored") 
    print("- This creates inconsistent behavior")
    
    print("\n💡 THE FIX:")
    print("- Remove the '> 0' condition")
    print("- Allow commission_amount = 0 to be saved")
    print("- Only skip if commission_amount is None/undefined")

def main():
    """Run all debug tests"""
    test_commission_logic()
    test_frontend_data()
    identify_fix()
    
    print("\n" + "=" * 60)
    print("🚨 CONCLUSION: Commission logic has a gap!")
    print("The API doesn't save commission when amount = 0 with type = 'normal'")
    print("This explains why your commission entries aren't being saved!")
    print("=" * 60)

if __name__ == "__main__":
    main()