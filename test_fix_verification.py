#\!/usr/bin/env python3
# Quick test to verify the collector chart vs details fix
import requests

def test_collector_fix():
    print("🔧 Testing Collector Chart vs Details Fix...")
    print("=" * 50)
    
    # Test collector details API
    print("\n2. Testing LOC LE collector details...")
    try:
        response = requests.post("http://localhost:5000/api/collector_guest_details", 
                               json={
                                   "collector": "LOC LE",
                                   "start_date": "2025-06-01",
                                   "end_date": "2025-06-30"
                               })
        
        if response.status_code == 200:
            data = response.json()
            if data["success"]:
                detail_amount = data["total_amount"]
                detail_count = data["count"]
                print(f"✅ Details API: LOC LE = {detail_amount:,.0f}đ ({detail_count} guests)")
                print("📊 Check server console for matching amounts!")
            else:
                print(f"❌ Details API error: {data.get('message')}")
        else:
            print(f"❌ Details API HTTP error: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Details API exception: {e}")

if __name__ == "__main__":
    test_collector_fix()
