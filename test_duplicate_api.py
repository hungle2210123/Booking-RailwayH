#!/usr/bin/env python3
"""
Test script to debug the duplicate analysis API endpoint
"""

import requests
import json
import time

def test_analyze_duplicates_api():
    """Test the /api/analyze_duplicates endpoint"""
    print("🧪 Testing /api/analyze_duplicates API endpoint...")
    
    # Assuming the Flask app is running on localhost:5000
    api_url = "http://localhost:5000/api/analyze_duplicates"
    
    try:
        print(f"📡 Making request to: {api_url}")
        
        # Record start time
        start_time = time.time()
        
        # Make the API request with a reasonable timeout
        response = requests.get(api_url, timeout=30)
        
        # Record end time
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"⏱️  Request completed in {duration:.2f} seconds")
        print(f"📊 Response Status Code: {response.status_code}")
        print(f"📋 Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print("✅ API Response (JSON):")
                print(json.dumps(data, indent=2, default=str))
                
                # Check the structure
                if 'success' in data:
                    print(f"🔍 Success: {data['success']}")
                    if 'data' in data:
                        analysis_data = data['data']
                        print(f"📈 Total Groups: {analysis_data.get('total_duplicates', 'N/A')}")
                        print(f"📝 Groups Found: {len(analysis_data.get('duplicate_groups', []))}")
                    if 'message' in data:
                        print(f"💬 Message: {data['message']}")
                else:
                    print("⚠️  Unexpected response structure")
                    
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse JSON response: {e}")
                print(f"📄 Raw response: {response.text[:500]}...")
                
        else:
            print(f"❌ HTTP Error {response.status_code}")
            print(f"📄 Error response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("⏱️  Request timed out after 30 seconds")
        print("💡 This might indicate the function is hanging or taking too long")
        
    except requests.exceptions.ConnectionError:
        print("🔌 Connection error - is the Flask server running?")
        print("💡 Start the server with: python app_postgresql.py")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    test_analyze_duplicates_api()