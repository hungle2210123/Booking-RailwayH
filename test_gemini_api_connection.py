#!/usr/bin/env python3
"""
Test Gemini API connectivity and configuration
"""

import os
from dotenv import load_dotenv
import google.generativeai as genai

def test_gemini_api():
    """Test Gemini API connection"""
    print("🔍 Testing Gemini API Connection...")
    
    # Load environment variables
    load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        print("❌ ERROR: GOOGLE_API_KEY not found in environment variables")
        return False
    
    print(f"✅ API Key found: {api_key[:10]}...{api_key[-4:]}")
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Test with a simple prompt
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("Say 'Hello from Gemini API test'")
        
        print("✅ Gemini API Response:")
        print(f"   📝 {response.text}")
        return True
        
    except Exception as e:
        print(f"❌ Gemini API Error: {str(e)}")
        return False

def test_analyze_duplicates_function():
    """Test the analyze_existing_duplicates function"""
    print("\n🔍 Testing Duplicate Analysis Function...")
    
    try:
        # Import the function
        import sys
        sys.path.append('/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized')
        from core.logic_postgresql import analyze_existing_duplicates
        
        # Create sample data
        import pandas as pd
        sample_data = pd.DataFrame([
            {'Số đặt phòng': 'TEST001', 'Tên người đặt': 'John Doe', 'Tổng thanh toán': 100000},
            {'Số đặt phòng': 'TEST002', 'Tên người đặt': 'Jane Smith', 'Tổng thanh toán': 200000},
            {'Số đặt phòng': 'TEST003', 'Tên người đặt': 'John Doe', 'Tổng thanh toán': 100000},  # Potential duplicate
        ])
        
        result = analyze_existing_duplicates(sample_data)
        print("✅ Duplicate Analysis Function Working:")
        print(f"   📊 Total groups: {result.get('total_groups', 0)}")
        print(f"   🔍 Total duplicates: {result.get('total_duplicates', 0)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Duplicate Analysis Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("🤖 Gemini AI & Duplicate Analysis Test")
    print("=" * 50)
    
    # Test Gemini API
    gemini_works = test_gemini_api()
    
    # Test duplicate analysis function
    analysis_works = test_analyze_duplicates_function()
    
    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY:")
    print(f"   🤖 Gemini API: {'✅ Working' if gemini_works else '❌ Failed'}")
    print(f"   🔍 Duplicate Analysis: {'✅ Working' if analysis_works else '❌ Failed'}")
    
    if gemini_works and analysis_works:
        print("\n🎉 All systems working! AI Filter Duplicates should work.")
    else:
        print("\n⚠️ Issues detected. Please check the errors above.")