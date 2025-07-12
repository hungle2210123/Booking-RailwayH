#!/usr/bin/env python3
"""
🏥 Railway Deployment Health Check
Verifies that the custom date picker functionality is working correctly on Railway
"""

import requests
import json
from datetime import datetime, timedelta

def check_railway_deployment(base_url=None):
    """
    Check if the Railway deployment is working correctly
    """
    if not base_url:
        print("📋 To use this script, provide your Railway URL:")
        print("   python3 railway_health_check.py https://your-app.railway.app")
        return False
    
    print("🏥 RAILWAY DEPLOYMENT HEALTH CHECK")
    print("=" * 60)
    print(f"🌐 Target URL: {base_url}")
    print()
    
    # Test 1: Dashboard accessibility
    print("🔍 Test 1: Dashboard Accessibility")
    try:
        response = requests.get(f"{base_url}/", timeout=10)
        if response.status_code == 200:
            print("   ✅ Dashboard loads successfully")
            
            # Check for custom date picker elements
            if 'setCollectorDateType' in response.text:
                print("   ✅ Custom date picker JavaScript found")
            else:
                print("   ⚠️ Custom date picker JavaScript not found in HTML")
                
            if 'collectorDateCustom' in response.text:
                print("   ✅ Custom date picker HTML elements found")
            else:
                print("   ⚠️ Custom date picker HTML elements not found")
                
        else:
            print(f"   ❌ Dashboard failed to load: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Dashboard access failed: {e}")
        return False
    
    # Test 2: Collector Chart API
    print("\n🔍 Test 2: Collector Chart API")
    try:
        # Test with custom date range
        test_data = {
            "start_date": "2025-06-01",
            "end_date": "2025-07-31"
        }
        
        response = requests.post(
            f"{base_url}/api/collector_chart_data",
            json=test_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print("   ✅ API endpoint accessible")
            
            if result.get('success'):
                print("   ✅ API returns success response")
                
                if 'chart_data' in result:
                    print("   ✅ Chart data structure present")
                else:
                    print("   ⚠️ Chart data structure missing")
                    
                if 'stats_data' in result:
                    print("   ✅ Stats data structure present")
                    stats_count = len(result.get('stats_data', []))
                    print(f"   📊 Found {stats_count} collector records")
                else:
                    print("   ⚠️ Stats data structure missing")
                    
            else:
                print(f"   ⚠️ API returned error: {result.get('message', 'Unknown error')}")
        else:
            print(f"   ❌ API failed: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ API test failed: {e}")
        return False
    
    # Test 3: Database connectivity
    print("\n🔍 Test 3: Database Connectivity")
    try:
        # Test a simple API that requires database
        response = requests.get(f"{base_url}/api/debug_database", timeout=10)
        if response.status_code == 200:
            print("   ✅ Database connection working")
        else:
            print(f"   ⚠️ Database test inconclusive: HTTP {response.status_code}")
    except Exception as e:
        print(f"   ⚠️ Database test failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎉 HEALTH CHECK COMPLETE!")
    print()
    print("💡 Next Steps:")
    print("   1. Open your Railway app in browser")
    print("   2. Navigate to 'Phân bổ theo Người thu (Chi tiết)' section")
    print("   3. Click 'Tùy chọn ngày' button")
    print("   4. Set custom dates and verify chart updates")
    print()
    print("🛠️ If issues found:")
    print("   - Check Railway deployment logs")
    print("   - Verify environment variables are set")
    print("   - Ensure PostgreSQL connection is working")
    
    return True

def main():
    import sys
    if len(sys.argv) > 1:
        base_url = sys.argv[1].rstrip('/')
        check_railway_deployment(base_url)
    else:
        check_railway_deployment()

if __name__ == "__main__":
    main()