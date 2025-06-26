#!/usr/bin/env python3
"""
Quick Import Solution - Uses requests to call the running Flask API
Works with your existing Flask app that's already running
"""

import requests
import json
import time
import sys
import os

def test_flask_connection():
    """Test if Flask app is running and accessible"""
    try:
        response = requests.get('http://127.0.0.1:5000/', timeout=5)
        return response.status_code == 200
    except:
        try:
            response = requests.get('http://localhost:5000/', timeout=5)
            return response.status_code == 200
        except:
            return False

def call_import_api():
    """Call the comprehensive import API"""
    print("🚀 CALLING IMPORT API ON RUNNING FLASK APP")
    print("=" * 60)
    
    # Try different URLs
    urls = [
        'http://127.0.0.1:5000/api/comprehensive_import',
        'http://localhost:5000/api/comprehensive_import',
        'http://192.168.0.102:5000/api/comprehensive_import'
    ]
    
    for url in urls:
        try:
            print(f"🔍 Trying: {url}")
            
            # Make the API call
            response = requests.post(
                url,
                headers={'Content-Type': 'application/json'},
                json={},
                timeout=300  # 5 minutes timeout for large imports
            )
            
            print(f"✅ Connected! Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('success'):
                    summary = result.get('summary', {})
                    
                    print(f"\n🎉 IMPORT SUCCESSFUL!")
                    print(f"📊 IMPORT SUMMARY:")
                    print(f"   👥 Customers imported: {summary.get('customers_imported', 0)}")
                    print(f"   📋 Bookings imported: {summary.get('bookings_imported', 0)}")
                    print(f"   💬 Templates imported: {summary.get('templates_imported', 0)}")
                    print(f"   💰 Expenses imported: {summary.get('expenses_imported', 0)}")
                    print(f"   📈 Total imported: {summary.get('total_imported', 0)}")
                    
                    if summary.get('errors'):
                        print(f"   ⚠️ Errors: {len(summary['errors'])}")
                        for error in summary['errors'][:3]:  # Show first 3
                            print(f"     - {error}")
                    
                    print(f"\n✅ {result.get('message', 'Import completed')}")
                    return True
                else:
                    print(f"❌ Import failed: {result.get('message', 'Unknown error')}")
                    return False
            else:
                print(f"❌ API call failed with status {response.status_code}")
                if response.text:
                    print(f"Response: {response.text}")
                
        except requests.exceptions.Timeout:
            print(f"⏰ Timeout waiting for import to complete")
            print("The import might still be running in the background...")
            return None
            
        except requests.exceptions.ConnectionError:
            print(f"❌ Cannot connect to {url}")
            continue
            
        except Exception as e:
            print(f"❌ Error calling {url}: {e}")
            continue
    
    return False

def check_flask_status():
    """Check if Flask app is running"""
    print("🔍 CHECKING FLASK APP STATUS")
    print("=" * 40)
    
    if test_flask_connection():
        print("✅ Flask app is running and accessible")
        return True
    else:
        print("❌ Flask app is not accessible")
        print("\n📝 TO FIX:")
        print("1. Make sure your Flask app is running:")
        print("   python app_postgresql.py")
        print("2. Check the console output for the correct URL")
        print("3. Verify PostgreSQL is running")
        return False

def check_import_status():
    """Check current database status"""
    try:
        urls = [
            'http://127.0.0.1:5000/api/import_status',
            'http://localhost:5000/api/import_status'
        ]
        
        for url in urls:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    status = response.json()
                    if status.get('success'):
                        data = status.get('status', {})
                        print(f"\n📊 CURRENT DATABASE STATUS:")
                        print(f"   👥 Customers: {data.get('customers_count', 0)}")
                        print(f"   📋 Bookings: {data.get('bookings_count', 0)}")
                        print(f"   💬 Templates: {data.get('templates_count', 0)}")
                        print(f"   💰 Expenses: {data.get('expenses_count', 0)}")
                        return True
                break
            except:
                continue
                
    except Exception as e:
        print(f"Could not check status: {e}")
    
    return False

def main():
    """Main function"""
    print("🚀 QUICK IMPORT SOLUTION")
    print("=" * 50)
    print("This script calls your running Flask app to import CSV data")
    print()
    
    # Step 1: Check if Flask is running
    if not check_flask_status():
        print("\n❌ Cannot proceed without running Flask app")
        return False
    
    # Step 2: Show current status
    print("\n📊 CURRENT STATUS:")
    check_import_status()
    
    # Step 3: Ask user confirmation
    print(f"\n🤔 READY TO IMPORT CSV DATA?")
    print("This will import all customers, bookings, templates, and expenses")
    print("from your csvtest.xlsx file into PostgreSQL database.")
    print()
    
    # For non-interactive mode, proceed automatically
    print("⏳ Starting import in 3 seconds...")
    time.sleep(3)
    
    # Step 4: Call import API
    result = call_import_api()
    
    if result:
        print(f"\n🎉 SUCCESS! Your data has been imported!")
        print(f"\n📍 NEXT STEPS:")
        print(f"1. Refresh your browser page")
        print(f"2. Go to Dashboard to see updated statistics")
        print(f"3. Check 'Quản lý Đặt phòng' for imported customers and bookings")
        print(f"4. Visit 'Chi Phí Tháng' for imported expenses")
        print(f"5. Check 'Quản Lý Dữ Liệu' for data management")
        
        # Show final status
        print(f"\n📊 UPDATED DATABASE STATUS:")
        check_import_status()
        
    elif result is None:
        print(f"\n⏰ Import may still be running...")
        print(f"Check your Flask app console for progress updates")
        
    else:
        print(f"\n❌ Import failed")
        print(f"Check your Flask app console for error details")
    
    return result

if __name__ == "__main__":
    try:
        success = main()
        if success:
            sys.exit(0)
        else:
            sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n⏹️ Import cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)