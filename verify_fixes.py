#!/usr/bin/env python3
"""
Verify All Payment Collection Fixes
Quick check that all issues have been resolved
"""

import os
from pathlib import Path

def check_external_js_updated():
    """Check if external JS file has been updated"""
    print("🔍 CHECKING EXTERNAL JS FILE")
    print("=" * 50)
    
    js_file = Path("static/js/dashboard.js")
    if not js_file.exists():
        print("❌ External JS file not found")
        return False
    
    with open(js_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("function openCollectModal(bookingId, guestName, totalAmount, commission = 0, roomFee = 0, taxiFee = 0, collectedAmount = 0)", "Updated function signature"),
        ("modalOriginalAmount", "Modal original amount element"),
        ("modalCollectedAmount", "Modal collected amount element"),
        ("modalRemainingAmount", "Modal remaining amount element"),
        ("console.error('[CollectModal]", "Error logging for debugging")
    ]
    
    all_found = True
    for check_str, description in checks:
        if check_str in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - MISSING")
            all_found = False
    
    return all_found

def check_template_fixes():
    """Check if template has the correct fixes"""
    print("\n🔍 CHECKING TEMPLATE FIXES")
    print("=" * 50)
    
    template_file = Path("templates/dashboard.html")
    if not template_file.exists():
        print("❌ Template file not found")
        return False
    
    with open(template_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("has_valid_collector = collector in ['LOC LE', 'THAO LE']", "Valid collector check"),
        ("total_amount = room_fee + taxi_fee", "Correct total calculation"),
        ("modalOriginalAmount", "New modal structure"),
        ("// DISABLED: This function has been moved to /static/js/dashboard.js", "Duplicate function disabled"),
        ("Chưa có người thu", "No collector warning message")
    ]
    
    all_found = True
    for check_str, description in checks:
        if check_str in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - MISSING")
            all_found = False
    
    return all_found

def check_api_fixes():
    """Check if API has collector validation"""
    print("\n🔍 CHECKING API FIXES")
    print("=" * 50)
    
    api_file = Path("app_postgresql.py")
    if not api_file.exists():
        print("❌ API file not found")
        return False
    
    with open(api_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("valid_collectors = ['LOC LE', 'THAO LE']", "Valid collector list"),
        ("if collector_name not in valid_collectors:", "Collector validation"),
        ("update_data['collected_amount'] = float(collected_amount)", "Collected amount saving"),
        ("✅ Valid collector confirmed", "Collector confirmation logging")
    ]
    
    all_found = True
    for check_str, description in checks:
        if check_str in content:
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - MISSING")
            all_found = False
    
    return all_found

def check_database_migration():
    """Check if database migration files exist"""
    print("\n🔍 CHECKING DATABASE MIGRATION")
    print("=" * 50)
    
    migration_files = [
        ("add_collected_amount.sql", "Main migration script"),
        ("reset_collected_amounts.sql", "Reset script for incorrect data")
    ]
    
    all_found = True
    for filename, description in migration_files:
        file_path = Path(filename)
        if file_path.exists():
            print(f"✅ {description}")
        else:
            print(f"❌ {description} - MISSING")
            all_found = False
    
    return all_found

def show_next_steps(all_passed):
    """Show what user needs to do next"""
    print("\n🚀 NEXT STEPS")
    print("=" * 50)
    
    if all_passed:
        print("🎉 ALL FIXES VERIFIED - Ready to test!")
        print()
        print("1. 🔄 RESTART Flask Server:")
        print("   - Stop current server (Ctrl+C)")
        print("   - python app_postgresql.py")
        print()
        print("2. 🧹 CLEAR Browser Cache:")
        print("   - Press Ctrl+Shift+Del")
        print("   - Clear cached images and files")
        print("   - Refresh dashboard (F5)")
        print()
        print("3. 🧪 TEST Collection Button:")
        print("   - Click 'Thu' button on any guest")
        print("   - Should open modal without JavaScript errors")
        print("   - Modal should show payment breakdown")
        print("   - Only LOC LE/THAO LE can collect payments")
        print()
        print("4. 🔍 VERIFY Results:")
        print("   - Dashboard shows red amounts for uncollected")
        print("   - Green amounts only appear after valid collection")
        print("   - Total amounts include room + taxi fees")
        print()
        print("5. 📊 Optional Database Migration:")
        print("   - psql -d database -f add_collected_amount.sql")
        print("   - psql -d database -f reset_collected_amounts.sql")
    else:
        print("⚠️ SOME FIXES MISSING - Review the failed checks above")
        print()
        print("Common issues:")
        print("- External JS file not updated properly")
        print("- Template changes not saved")
        print("- API validation missing")
        print()
        print("Try:")
        print("1. Re-run the fixes from the previous messages")
        print("2. Ensure all files are saved")
        print("3. Run this script again to verify")

def main():
    """Run all verification checks"""
    print("🔧 PAYMENT COLLECTION FIXES - VERIFICATION")
    print("=" * 70)
    
    checks = [
        ("External JS File", check_external_js_updated),
        ("Template Fixes", check_template_fixes),
        ("API Fixes", check_api_fixes),
        ("Database Migration", check_database_migration)
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name} failed with error: {e}")
            results.append((check_name, False))
    
    # Summary
    print("\n📋 VERIFICATION SUMMARY")
    print("=" * 70)
    
    passed = 0
    for check_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {check_name}")
        if result:
            passed += 1
    
    all_passed = passed == len(results)
    print(f"\n🎯 Overall Result: {passed}/{len(results)} checks passed")
    
    show_next_steps(all_passed)

if __name__ == "__main__":
    main()