#!/usr/bin/env python3
"""
Enhanced Railway startup script with comprehensive error diagnostics
"""
import os
import subprocess
import sys

def test_imports():
    """Test all critical imports before starting gunicorn"""
    print("=" * 60)
    print("🔍 TESTING CRITICAL IMPORTS")
    print("=" * 60)

    critical_imports = [
        ('flask', 'Flask'),
        ('flask_caching', 'Flask-Caching'),
        ('sqlalchemy', 'SQLAlchemy'),
        ('psycopg2', 'PostgreSQL Driver'),
        ('gunicorn', 'Gunicorn'),
        ('pandas', 'Pandas'),
        ('plotly', 'Plotly'),
        ('google.generativeai', 'Google Gemini AI'),
    ]

    all_passed = True
    for module_name, display_name in critical_imports:
        try:
            __import__(module_name)
            print(f"✅ {display_name}: OK")
        except ImportError as e:
            print(f"❌ {display_name}: FAILED - {e}")
            all_passed = False

    print("=" * 60)
    return all_passed

def test_app_import():
    """Test if app.py can be imported"""
    print("\n🔍 TESTING APP IMPORT")
    print("=" * 60)
    try:
        # Try to import the Flask app
        from app import app
        print(f"✅ app.py imported successfully")
        print(f"✅ Flask app name: {app.name}")
        return True
    except Exception as e:
        print(f"❌ FAILED TO IMPORT APP: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_environment():
    """Check critical environment variables"""
    print("\n🔍 ENVIRONMENT VARIABLES")
    print("=" * 60)

    env_vars = [
        'PORT',
        'DATABASE_URL',
        'DATABASE_SOURCE',
        'RAILWAY_DB_HOST',
        'RAILWAY_DB_NAME',
    ]

    for var in env_vars:
        value = os.environ.get(var)
        if value:
            # Mask passwords in output
            if 'PASSWORD' in var or 'URL' in var:
                masked = value[:20] + '...' if len(value) > 20 else value
                print(f"✅ {var}: {masked}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"⚠️  {var}: NOT SET")

    print("=" * 60)

def main():
    print("\n" + "=" * 60)
    print("🚀 RAILWAY STARTUP DIAGNOSTICS")
    print("=" * 60)

    # Step 1: Check environment
    check_environment()

    # Step 2: Test imports
    if not test_imports():
        print("\n❌ CRITICAL: Import tests failed!")
        print("Cannot start application with missing dependencies")
        sys.exit(1)

    # Step 3: Test app import
    if not test_app_import():
        print("\n❌ CRITICAL: Cannot import Flask app!")
        print("Check app.py for syntax errors or import issues")
        sys.exit(1)

    # Step 4: Get and validate PORT
    port = os.environ.get('PORT', '5000')
    try:
        port_int = int(port)
        if not (1 <= port_int <= 65535):
            print(f"⚠️ Invalid port {port}, using 5000")
            port = '5000'
    except (ValueError, TypeError):
        print(f"⚠️ Non-numeric port '{port}', using 5000")
        port = '5000'

    print(f"\n✅ ALL CHECKS PASSED - Starting gunicorn on 0.0.0.0:{port}")
    print("=" * 60)

    # Step 5: Start gunicorn optimized for Railway Hobby (8 vCPU, 8GB RAM)
    # Formula: workers = (2 x CPU cores) + 1 = (2 x 8) + 1 = 17 workers
    # But we'll use 4 workers to leave headroom for database connections
    cmd = [
        'gunicorn',
        'app:app',
        '--bind', f'0.0.0.0:{port}',
        '--workers', '4',  # Increased from 2 to 4 for Hobby plan (8 vCPU)
        '--worker-class', 'sync',
        '--timeout', '120',  # Reduced from 300 to 120 (Hobby has better performance)
        '--graceful-timeout', '120',
        '--keep-alive', '5',
        '--max-requests', '1000',  # Restart workers after 1000 requests to prevent memory leaks
        '--max-requests-jitter', '100',  # Add randomness to prevent all workers restarting at once
        '--access-logfile', '-',
        '--error-logfile', '-',
        '--log-level', 'info',  # Changed from debug to info (less verbose)
        '--preload',  # Preload app to catch errors early
    ]

    print(f"📝 Command: {' '.join(cmd)}\n")
    os.execvp('gunicorn', cmd)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ STARTUP FAILED WITH EXCEPTION:")
        import traceback
        traceback.print_exc()
        sys.exit(1)
