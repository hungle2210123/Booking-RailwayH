#!/usr/bin/env python3
"""
Verify PostgreSQL-only deployment - No Google Sheets dependencies
"""
import os
import sys

def check_files():
    """Check that only PostgreSQL files exist"""
    print("🔍 Checking deployment files...")
    
    # Check main app file
    if os.path.exists('app.py'):
        with open('app.py', 'r') as f:
            content = f.read()
            if 'google' in content.lower() or 'gsheet' in content.lower():
                print("❌ app.py still contains Google Sheets references")
                return False
            else:
                print("✅ app.py is clean (PostgreSQL only)")
    
    # Check logic file
    if os.path.exists('core/logic.py'):
        with open('core/logic.py', 'r') as f:
            content = f.read()
            if 'Thành viên Genius' in content:
                print("❌ core/logic.py still contains 'Thành viên Genius' references")
                return False
            else:
                print("✅ core/logic.py is clean (PostgreSQL only)")
    
    # Check Procfile
    if os.path.exists('Procfile'):
        with open('Procfile', 'r') as f:
            content = f.read().strip()
            if 'gunicorn app:app' in content:
                print("✅ Procfile correctly configured for PostgreSQL app")
            else:
                print(f"❌ Procfile misconfigured: {content}")
                return False
    
    return True

def check_environment():
    """Check environment variables"""
    print("\n🔧 Checking environment setup...")
    
    required_vars = ['DATABASE_URL', 'USE_POSTGRESQL']
    optional_vars = ['GOOGLE_API_KEY', 'FLASK_SECRET_KEY']
    
    for var in required_vars:
        if os.getenv(var):
            print(f"✅ {var} is set")
        else:
            print(f"❌ {var} is missing (REQUIRED)")
            return False
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"✅ {var} is set")
        else:
            print(f"⚠️ {var} is missing (optional)")
    
    return True

def test_import():
    """Test importing the main app"""
    print("\n🧪 Testing app import...")
    
    try:
        from app import app, db
        print("✅ Successfully imported Flask app")
        
        # Test database models
        from core.models import Booking, Guest, MessageTemplate
        print("✅ Successfully imported PostgreSQL models")
        
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def main():
    """Main verification function"""
    print("🚀 PostgreSQL Deployment Verification")
    print("=" * 50)
    
    all_good = True
    
    all_good &= check_files()
    all_good &= check_environment()
    all_good &= test_import()
    
    print("\n" + "=" * 50)
    if all_good:
        print("✅ DEPLOYMENT READY - All checks passed!")
        print("🚀 Your PostgreSQL-only app should deploy successfully")
    else:
        print("❌ DEPLOYMENT ISSUES FOUND")
        print("🔧 Please fix the issues above before deploying")
    
    return 0 if all_good else 1

if __name__ == '__main__':
    sys.exit(main())