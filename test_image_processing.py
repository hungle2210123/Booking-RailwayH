#!/usr/bin/env python3
"""
Test Image Processing API Fix
Verify that the image processing endpoint can handle base64 data
"""

import requests
import json
import base64
from pathlib import Path

def create_test_base64_image():
    """Create a simple test image in base64 format"""
    # Create a minimal 1x1 pixel PNG in base64
    # This is a valid PNG header for testing
    test_png_bytes = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,  # 1x1 pixel
        0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53,  # RGB color
        0xDE, 0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x08, 0x99, 0x01, 0x01, 0x00, 0x00, 0x00,  # Minimal data
        0x00, 0x00, 0x37, 0x6E, 0xF9, 0x24, 0x00, 0x00,  # CRC
        0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42,  # IEND chunk
        0x60, 0x82
    ])
    
    return base64.b64encode(test_png_bytes).decode('utf-8')

def test_image_processing_api():
    """Test the image processing API with base64 data"""
    print("🧪 TESTING IMAGE PROCESSING API")
    print("=" * 50)
    
    # Create test image data
    test_base64 = create_test_base64_image()
    print(f"📷 Created test image, base64 length: {len(test_base64)}")
    
    # Test data with base64 image
    test_payload = {
        "image_b64": f"data:image/png;base64,{test_base64}"
    }
    
    print(f"📤 Sending test data to API...")
    
    try:
        response = requests.post(
            'http://127.0.0.1:5000/api/process_pasted_image',
            headers={'Content-Type': 'application/json'},
            data=json.dumps(test_payload),
            timeout=30
        )
        
        print(f"📬 API Response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success! Response: {result}")
            return True
        else:
            try:
                error_data = response.json()
                print(f"❌ API Error: {error_data}")
            except:
                print(f"❌ HTTP Error: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask server")
        print("   Make sure server is running: python app_postgresql.py")
        return False
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def test_without_base64():
    """Test API without image data to verify error handling"""
    print("\n🧪 TESTING ERROR HANDLING (No Image)")
    print("=" * 50)
    
    try:
        response = requests.post(
            'http://127.0.0.1:5000/api/process_pasted_image',
            headers={'Content-Type': 'application/json'},
            data=json.dumps({}),
            timeout=10
        )
        
        print(f"📬 API Response: {response.status_code}")
        
        if response.status_code == 400:
            result = response.json()
            if 'No image provided' in result.get('error', ''):
                print("✅ Error handling works correctly")
                return True
            else:
                print(f"❌ Unexpected error message: {result}")
                return False
        else:
            print(f"❌ Expected 400 error, got: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def test_gemini_api_connectivity():
    """Test if Gemini API is accessible"""
    print("\n🧪 TESTING GEMINI API CONNECTIVITY")
    print("=" * 50)
    
    try:
        response = requests.get(
            'http://127.0.0.1:5000/api/test_gemini',
            timeout=10
        )
        
        print(f"📬 API Response: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Gemini API test result: {result}")
            return True
        else:
            try:
                error_data = response.json()
                print(f"❌ Gemini API Error: {error_data}")
            except:
                print(f"❌ HTTP Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 IMAGE PROCESSING API TESTING SUITE")
    print("=" * 70)
    
    tests = [
        ("Gemini API Connectivity", test_gemini_api_connectivity),
        ("Image Processing with Base64", test_image_processing_api),
        ("Error Handling (No Image)", test_without_base64)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n📋 TEST RESULTS SUMMARY")
    print("=" * 70)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("\n🎉 ALL TESTS PASSED!")
        print("The image processing API should now work correctly.")
    else:
        print("\n⚠️ SOME TESTS FAILED")
        print("Check the Flask server logs for more details.")

if __name__ == "__main__":
    main()