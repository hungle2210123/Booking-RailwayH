#!/usr/bin/env python3
"""
Fix template data via API call - for when you can run the Flask app
"""
import requests
import json
import time

def fix_templates_via_api():
    """Fix templates by calling the Flask API endpoint"""
    
    # Flask app URL (adjust if needed)
    base_url = "http://localhost:5000"
    
    try:
        print("🔄 Attempting to fix templates via API...")
        
        # Call the template import API endpoint
        response = requests.post(f"{base_url}/api/templates/import_json")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Templates fixed successfully via API!")
                print(f"📊 {result.get('imported_count', 0)} templates imported")
                print(f"📂 Categories: {', '.join(result.get('categories', []))}")
                return True
            else:
                print(f"❌ API call failed: {result.get('error', 'Unknown error')}")
                return False
        else:
            print(f"❌ HTTP Error {response.status_code}: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Flask server. Make sure it's running on localhost:5000")
        print("   Start server with: python app_postgresql.py")
        return False
    except Exception as e:
        print(f"❌ Error fixing templates: {e}")
        return False

def check_templates_status():
    """Check current template status via API"""
    base_url = "http://localhost:5000"
    
    try:
        response = requests.get(f"{base_url}/api/templates")
        
        if response.status_code == 200:
            result = response.json()
            templates = result.get('data', [])
            
            print(f"📋 Current templates in database: {len(templates)}")
            print("\n🔍 Sample templates (showing Label field):")
            for i, template in enumerate(templates[:5]):
                label = template.get('Label', 'N/A')
                category = template.get('Category', 'N/A')
                print(f"  {i+1}. {category} - {label}")
            
            return True
        else:
            print(f"❌ Cannot check templates: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Error checking templates: {e}")
        return False

if __name__ == "__main__":
    print("🔧 Template Data Fix Tool")
    print("=" * 50)
    
    # First check current status
    print("1️⃣ Checking current template status...")
    check_templates_status()
    
    print("\n2️⃣ Attempting to fix template data...")
    if fix_templates_via_api():
        print("\n3️⃣ Verifying fix...")
        time.sleep(1)
        check_templates_status()
        print("\n✅ Template fix completed! Check your AI Assistant now.")
    else:
        print("\n❌ Fix failed. Try the manual SQL approach instead.")
        print("   Run: psql -d your_database_name -f fix_template_data.sql")