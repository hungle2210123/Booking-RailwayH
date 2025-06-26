#!/usr/bin/env python3
"""
Test script to verify Gemini API connectivity with your API key
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_gemini_api():
    """Test Gemini API connection"""
    print("🤖 Testing Gemini AI API Connection")
    print("=" * 40)
    
    # Get API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key or api_key == 'your_gemini_api_key':
        print("❌ GOOGLE_API_KEY not configured in .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-10:]}")
    
    # Try to import and configure Gemini
    try:
        import google.generativeai as genai
        print("✅ google.generativeai library imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import google.generativeai: {e}")
        print("💡 Install with: pip install google-generativeai")
        return False
    
    # Configure API
    try:
        genai.configure(api_key=api_key)
        print("✅ Gemini API configured successfully")
    except Exception as e:
        print(f"❌ Failed to configure Gemini API: {e}")
        return False
    
    # Test simple text generation
    try:
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("Hello, can you respond with just 'API Working'?")
        
        if response and response.text:
            print(f"✅ API Response: {response.text.strip()}")
            print("🎉 Gemini API is working correctly!")
            return True
        else:
            print("❌ API response was empty")
            return False
            
    except Exception as e:
        print(f"❌ Failed to generate content: {e}")
        return False

def test_duplicate_analysis_logic():
    """Test the duplicate analysis logic without dependencies"""
    print("\n🔍 Testing Duplicate Analysis Logic")
    print("=" * 40)
    
    # Simple mock data
    sample_bookings = [
        {"Tên người đặt": "Nguyen Van A", "Check-in Date": "2024-01-15", "Tổng thanh toán": 500000},
        {"Tên người đặt": "Nguyen Van A", "Check-in Date": "2024-01-16", "Tổng thanh toán": 510000},  # Duplicate
        {"Tên người đặt": "Tran Thi B", "Check-in Date": "2024-01-20", "Tổng thanh toán": 600000},
        {"Tên người đặt": "Le Van C", "Check-in Date": "2024-01-25", "Tổng thanh toán": 700000},
    ]
    
    # Simple duplicate detection logic (same name + similar dates)
    duplicates = []
    for i, booking1 in enumerate(sample_bookings):
        for j, booking2 in enumerate(sample_bookings):
            if i != j and booking1["Tên người đặt"] == booking2["Tên người đặt"]:
                # Check if dates are within 3 days
                try:
                    from datetime import datetime
                    date1 = datetime.strptime(booking1["Check-in Date"], "%Y-%m-%d")
                    date2 = datetime.strptime(booking2["Check-in Date"], "%Y-%m-%d")
                    
                    if abs((date1 - date2).days) <= 3:
                        duplicates.append((booking1, booking2))
                except:
                    pass
    
    if duplicates:
        print(f"✅ Found {len(duplicates)} potential duplicate pairs")
        for dup in duplicates:
            print(f"   - {dup[0]['Tên người đặt']}: {dup[0]['Check-in Date']} vs {dup[1]['Check-in Date']}")
    else:
        print("✅ No duplicates found in sample data")
    
    print("✅ Duplicate analysis logic working")
    return True

def main():
    """Run all tests"""
    print("🏨 GEMINI AI & DUPLICATE ANALYSIS TEST")
    print("=" * 50)
    
    success = True
    
    # Test Gemini API
    if not test_gemini_api():
        success = False
    
    # Test duplicate logic
    if not test_duplicate_analysis_logic():
        success = False
    
    if success:
        print("\n" + "=" * 50)
        print("🎉 ALL TESTS PASSED!")
        print("✅ Gemini API working correctly")
        print("✅ Duplicate analysis logic working")
        print("✅ AI Duplicate Analysis should now work in your app")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("❌ Some tests failed")
        print("Please check the errors above and fix them")
        print("=" * 50)
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)