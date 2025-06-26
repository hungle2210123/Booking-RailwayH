#!/usr/bin/env python3
"""
Quick System Status Check
Can be run while Flask server is running
"""

import os
from pathlib import Path

def check_file_modifications():
    """Quick check of file modifications"""
    print("🔍 SYSTEM STATUS CHECK")
    print("=" * 50)
    
    files_to_check = [
        ("core/models.py", "collected_amount", "Database model updated"),
        ("app_postgresql.py", "collected_amount", "API endpoint updated"),
        ("templates/dashboard.html", "modalCollectedAmount", "Frontend modal updated"),
        ("templates/dashboard.html", "Số tiền đã thu", "Dashboard display updated"),
        ("core/logic_postgresql.py", "collected_amount", "Data loading updated"),
        ("add_collected_amount.sql", "ALTER TABLE", "Migration script created")
    ]
    
    status = []
    for file_path, search_str, description in files_to_check:
        full_path = Path(file_path)
        
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if search_str in content:
                    print(f"✅ {description}")
                    status.append(True)
                else:
                    print(f"❌ {description} - MISSING")
                    status.append(False)
            except Exception as e:
                print(f"❌ {description} - ERROR: {e}")
                status.append(False)
        else:
            print(f"❌ {description} - FILE NOT FOUND")
            status.append(False)
    
    success_rate = sum(status) / len(status) * 100
    print(f"\n📊 File Modifications: {success_rate:.0f}% complete")
    
    return all(status)

def check_database_migration_ready():
    """Check if migration script is ready"""
    print("\n🔍 DATABASE MIGRATION CHECK")
    print("=" * 50)
    
    migration_file = Path("add_collected_amount.sql")
    
    if migration_file.exists():
        print("✅ Migration script exists")
        
        with open(migration_file, 'r') as f:
            content = f.read()
        
        required_elements = [
            "ALTER TABLE bookings",
            "ADD COLUMN collected_amount",
            "DECIMAL(12, 2)",
            "DEFAULT 0.00",
            "NOT NULL"
        ]
        
        all_found = True
        for element in required_elements:
            if element in content:
                print(f"✅ Contains: {element}")
            else:
                print(f"❌ Missing: {element}")
                all_found = False
        
        return all_found
    else:
        print("❌ Migration script not found")
        return False

def show_next_steps():
    """Show next steps for user"""
    print("\n🚀 NEXT STEPS TO COMPLETE SETUP")
    print("=" * 50)
    
    print("1. 🗄️ Apply Database Migration:")
    print("   psql -d your_database_name -f add_collected_amount.sql")
    print("   (Replace 'your_database_name' with actual database name)")
    
    print("\n2. 🔄 Restart Flask Server:")
    print("   Ctrl+C to stop current server")
    print("   python app_postgresql.py")
    
    print("\n3. 🧪 Test Payment Collection:")
    print("   - Go to dashboard")
    print("   - Click 'Thu' button on any guest")
    print("   - Enter test amount (e.g., 123456)")
    print("   - Check server logs for: '💰 Setting collected_amount to: 123456'")
    print("   - Verify dashboard shows green collected amount")
    
    print("\n4. 📊 Verify in Database:")
    print("   - Open DBeaver or PostgreSQL client")
    print("   - Check bookings table for collected_amount column")
    print("   - Verify test payment was saved correctly")
    
    print("\n5. 🎯 Look for Success Indicators:")
    print("   - Green checkmark + amount in dashboard")
    print("   - Red remaining amount (if partially paid)")
    print("   - Updated payment status in modal")

def main():
    """Main status check"""
    print("🎯 COLLECTED AMOUNT TRACKING SYSTEM - STATUS CHECK")
    print("=" * 70)
    
    files_ok = check_file_modifications()
    migration_ok = check_database_migration_ready()
    
    print(f"\n📋 SYSTEM STATUS SUMMARY")
    print("=" * 50)
    
    if files_ok:
        print("✅ File modifications: COMPLETE")
    else:
        print("❌ File modifications: INCOMPLETE")
    
    if migration_ok:
        print("✅ Migration script: READY")
    else:
        print("❌ Migration script: NOT READY")
    
    if files_ok and migration_ok:
        print("\n🎉 SYSTEM READY FOR DEPLOYMENT!")
        print("All code changes complete - ready to apply database migration")
    else:
        print("\n⚠️ SYSTEM NOT READY")
        print("Some components need attention before deployment")
    
    show_next_steps()

if __name__ == "__main__":
    main()