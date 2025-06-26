#!/usr/bin/env python3
"""
Simple Database Status Check - No Dependencies
"""

import os
import sys
import subprocess
from pathlib import Path

def load_env_manually():
    """Load .env file manually without python-dotenv"""
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value

def check_database_connectivity():
    """Check database connectivity using basic tools"""
    print("🔍 DATABASE CONNECTIVITY CHECK")
    print("=" * 50)
    
    load_env_manually()
    
    database_url = os.environ.get('DATABASE_URL', 'NOT SET')
    
    if database_url == 'NOT SET':
        print("❌ DATABASE_URL not configured")
        return False
    
    # Parse database URL
    if database_url.startswith('postgresql://'):
        # Extract host and port
        parts = database_url.replace('postgresql://', '').split('@')
        if len(parts) >= 2:
            host_part = parts[1].split('/')[0]
            if ':' in host_part:
                host, port = host_part.split(':')
            else:
                host, port = host_part, '5432'
            
            print(f"🎯 Testing connection to: {host}:{port}")
            
            # Test network connectivity
            result = subprocess.run(['nc', '-z', host, port], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                print(f"✅ Network connection to {host}:{port} successful")
                return True
            else:
                print(f"❌ Cannot connect to {host}:{port}")
                print(f"   Error: {result.stderr}")
                return False
    
    print("❌ Invalid DATABASE_URL format")
    return False

def check_required_packages():
    """Check if required packages are available"""
    print("\n🔍 PACKAGE AVAILABILITY CHECK")
    print("=" * 50)
    
    required_packages = [
        'flask',
        'psycopg2',
        'sqlalchemy', 
        'flask_sqlalchemy',
        'pandas',
        'python-dotenv'
    ]
    
    available_packages = []
    missing_packages = []
    
    for package in required_packages:
        try:
            result = subprocess.run([sys.executable, '-c', f'import {package.replace("-", "_")}'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                available_packages.append(package)
                print(f"✅ {package}")
            else:
                missing_packages.append(package)
                print(f"❌ {package}")
        except Exception as e:
            missing_packages.append(package)
            print(f"❌ {package} - {str(e)}")
    
    print(f"\n📊 Summary: {len(available_packages)}/{len(required_packages)} packages available")
    
    if missing_packages:
        print(f"\n⚠️  Missing packages: {', '.join(missing_packages)}")
        return False
    
    return True

def check_app_files():
    """Check if critical application files exist"""
    print("\n🔍 APPLICATION FILES CHECK")
    print("=" * 50)
    
    critical_files = [
        'app.py',
        'core/models.py',
        'core/logic.py', 
        'core/database_service.py',
        'requirements.txt',
        '.env'
    ]
    
    all_exist = True
    
    for file_path in critical_files:
        if Path(file_path).exists():
            print(f"✅ {file_path}")
        else:
            print(f"❌ {file_path}")
            all_exist = False
    
    return all_exist

def provide_fix_instructions():
    """Provide instructions to fix common issues"""
    print("\n🔧 FIX INSTRUCTIONS")
    print("=" * 50)
    
    load_env_manually()
    database_url = os.environ.get('DATABASE_URL', 'NOT SET')
    
    print("1. INSTALL REQUIRED PACKAGES:")
    print("   Windows: python -m pip install -r requirements.txt")
    print("   Linux:   python3 -m pip install -r requirements.txt")
    
    print("\n2. DATABASE CONFIGURATION:")
    if 'localhost' in database_url:
        print("   ⚠️  You're using localhost PostgreSQL but it's not running")
        print("   Solution A: Start local PostgreSQL service")
        print("   Solution B: Use production database URL")
    elif 'render.com' in database_url:
        print("   ✅ Using production database URL")
    else:
        print("   ⚠️  Check DATABASE_URL in .env file")
    
    print(f"\n3. CURRENT DATABASE_URL: {database_url[:50]}...")
    
    print("\n4. NEXT STEPS:")
    print("   - Install packages: pip install -r requirements.txt")
    print("   - Test connection: python simple_connection_test.py")
    print("   - Run app: python app.py")

def main():
    """Main diagnostic function"""
    print("🏨 HOTEL BOOKING SYSTEM - DATABASE DIAGNOSTIC")
    print("=" * 60)
    
    # Run all checks
    connectivity_ok = check_database_connectivity()
    packages_ok = check_required_packages()
    files_ok = check_app_files()
    
    # Summary
    print(f"\n📋 DIAGNOSTIC SUMMARY")
    print("=" * 50)
    print(f"Database Connectivity: {'✅' if connectivity_ok else '❌'}")
    print(f"Required Packages: {'✅' if packages_ok else '❌'}")
    print(f"Application Files: {'✅' if files_ok else '❌'}")
    
    if connectivity_ok and packages_ok and files_ok:
        print(f"\n🎉 ALL CHECKS PASSED - Ready to run application!")
        print("   Run: python app.py")
        return True
    else:
        print(f"\n⚠️  ISSUES FOUND - See fix instructions below")
        provide_fix_instructions()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)