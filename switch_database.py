#!/usr/bin/env python3
"""
Database Source Switcher
Easily switch between local and Railway database
"""

import os
import sys
from pathlib import Path

def switch_database_source(source):
    """Switch DATABASE_SOURCE in .env file"""
    env_file = Path('.env')
    
    if not env_file.exists():
        print("❌ .env file not found")
        return False
    
    # Read current .env content
    with open(env_file, 'r') as f:
        lines = f.readlines()
    
    # Update DATABASE_SOURCE line
    updated = False
    for i, line in enumerate(lines):
        if line.startswith('DATABASE_SOURCE='):
            lines[i] = f'DATABASE_SOURCE={source}\n'
            updated = True
            break
    
    if not updated:
        print("❌ DATABASE_SOURCE not found in .env file")
        return False
    
    # Write updated content
    with open(env_file, 'w') as f:
        f.writelines(lines)
    
    print(f"✅ Switched to {source.upper()} database")
    return True

def show_current_config():
    """Show current database configuration"""
    print("🔍 Current Database Configuration")
    print("=" * 40)
    
    source = os.getenv('DATABASE_SOURCE', 'auto')
    local_url = os.getenv('LOCAL_DATABASE_URL', 'Not set')
    railway_url = os.getenv('RAILWAY_DATABASE_URL', 'Not set')
    
    print(f"📋 DATABASE_SOURCE: {source}")
    print(f"🏠 Local: {local_url[:50]}...")
    print(f"🚂 Railway: {railway_url[:50]}...")
    
    # Show which database will be used
    if source == 'local':
        print(f"✅ Currently using: LOCAL PostgreSQL")
    elif source == 'railway':
        print(f"✅ Currently using: RAILWAY PostgreSQL")
    else:
        print(f"✅ Currently using: AUTO detection")

def main():
    """Main menu"""
    print("🔄 Database Source Switcher")
    print("=" * 50)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    # Show current config
    show_current_config()
    
    print()
    print("📋 Options:")
    print("1. Switch to LOCAL PostgreSQL (for development/testing)")
    print("2. Switch to RAILWAY PostgreSQL (for production)")
    print("3. Switch to AUTO detection")
    print("4. Show current configuration")
    print("5. Exit")
    
    choice = input("\nSelect option (1-5): ").strip()
    
    if choice == '1':
        if switch_database_source('local'):
            print("💡 Restart your Flask app to apply changes")
            print("📋 Use this for local development with your 76 bookings")
    elif choice == '2':
        if switch_database_source('railway'):
            print("💡 Restart your Flask app to apply changes")
            print("📋 Use this to connect to Railway production data")
    elif choice == '3':
        if switch_database_source('auto'):
            print("💡 Restart your Flask app to apply changes")
            print("📋 Auto-detection: Railway > Explicit > Local")
    elif choice == '4':
        show_current_config()
    elif choice == '5':
        print("👋 Goodbye!")
        return
    else:
        print("❌ Invalid choice")
    
    print()
    input("Press Enter to continue...")

if __name__ == "__main__":
    main()