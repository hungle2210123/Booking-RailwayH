#!/usr/bin/env python3
"""
🔍 Railway Deployment Validator
Checks if your local changes are safe to deploy to Railway
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from colorama import init, Fore, Style

# Initialize colorama for colored output
try:
    init(autoreset=True)
except:
    # Fallback if colorama not available
    class Fore:
        GREEN = RED = YELLOW = CYAN = RESET = ""
    class Style:
        BRIGHT = RESET_ALL = ""

# Load environment variables
load_dotenv()

# Import sync service
try:
    from core.auto_sync_service import auto_sync_service
    from core.logic_postgresql import load_booking_data
    SYNC_AVAILABLE = True
except ImportError as e:
    SYNC_AVAILABLE = False
    print(f"⚠️  Warning: Could not import sync service: {e}")

def print_header(title):
    """Print formatted header"""
    print("\n" + "="*70)
    print(f"{Fore.CYAN}{Style.BRIGHT}  {title}")
    print("="*70 + Style.RESET_ALL)

def print_pass(message):
    """Print success message"""
    print(f"{Fore.GREEN}✅ {message}{Style.RESET_ALL}")

def print_fail(message):
    """Print error message"""
    print(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")

def print_warn(message):
    """Print warning message"""
    print(f"{Fore.YELLOW}⚠️  {message}{Style.RESET_ALL}")

def check_environment_config():
    """Check environment configuration"""
    print_header("1. Environment Configuration")

    issues = []

    # Check DATABASE_SOURCE
    db_source = os.getenv('DATABASE_SOURCE', 'auto')
    if db_source == 'local':
        print_pass(f"DATABASE_SOURCE=local (local-first development)")
    elif db_source == 'auto':
        print_warn("DATABASE_SOURCE=auto (will use Railway on deployment)")
    else:
        print_fail(f"DATABASE_SOURCE={db_source} (unexpected value)")
        issues.append("Unexpected DATABASE_SOURCE value")

    # Check database URLs
    local_url = os.getenv('LOCAL_DATABASE_URL')
    railway_url = os.getenv('RAILWAY_DATABASE_URL')

    if local_url:
        print_pass("LOCAL_DATABASE_URL configured")
    else:
        print_fail("LOCAL_DATABASE_URL not configured")
        issues.append("Missing LOCAL_DATABASE_URL")

    if railway_url:
        print_pass("RAILWAY_DATABASE_URL configured")
    else:
        print_fail("RAILWAY_DATABASE_URL not configured")
        issues.append("Missing RAILWAY_DATABASE_URL")

    # Check auto-sync settings
    auto_sync = os.getenv('AUTO_SYNC_ENABLED', 'false').lower() == 'true'
    if auto_sync:
        print_warn("Auto-sync ENABLED (will sync automatically)")
    else:
        print_pass("Auto-sync DISABLED (manual sync required)")

    return len(issues) == 0, issues

def check_database_connections():
    """Test database connections"""
    print_header("2. Database Connectivity")

    if not SYNC_AVAILABLE:
        print_fail("Sync service not available - skipping connectivity check")
        return False, ["Sync service unavailable"]

    issues = []

    # Test local database
    try:
        local_counts = auto_sync_service.get_table_counts(auto_sync_service.local_engine)
        total_local = sum(local_counts.values())
        print_pass(f"Local PostgreSQL connected ({total_local} total records)")
    except Exception as e:
        print_fail(f"Local PostgreSQL connection failed: {e}")
        issues.append("Local database connection failed")
        local_counts = {}

    # Test Railway database
    try:
        railway_counts = auto_sync_service.get_table_counts(auto_sync_service.railway_engine)
        total_railway = sum(railway_counts.values())
        print_pass(f"Railway PostgreSQL connected ({total_railway} total records)")
    except Exception as e:
        print_fail(f"Railway PostgreSQL connection failed: {e}")
        issues.append("Railway database connection failed")
        railway_counts = {}

    return len(issues) == 0, issues

def check_data_sync_status():
    """Check if data is synced"""
    print_header("3. Data Synchronization Status")

    if not SYNC_AVAILABLE:
        print_warn("Sync service not available - skipping sync check")
        return True, []

    issues = []

    try:
        status = auto_sync_service.analyze_sync_status(force_refresh=True)

        print(f"\n   Local records:   {status.local_count}")
        print(f"   Railway records: {status.railway_count}")

        if status.sync_needed:
            diff = abs(status.local_count - status.railway_count)
            print_fail(f"Databases OUT OF SYNC ({diff} record difference)")
            print(f"\n   Recommended action: {status.recommended_direction}")

            if status.differences:
                print(f"\n   Differences by table:")
                for table, diff_info in status.differences.items():
                    print(f"      {table:20} Local: {diff_info['local']:4d} | Railway: {diff_info['railway']:4d}")

            issues.append(f"Databases out of sync - run: python3 sync_manager.py {status.recommended_direction.replace('_', '-')}")
        else:
            print_pass("Databases are SYNCHRONIZED ✓")

    except Exception as e:
        print_fail(f"Could not check sync status: {e}")
        issues.append("Sync status check failed")

    return len(issues) == 0, issues

def check_code_quality():
    """Basic code quality checks"""
    print_header("4. Code Quality Checks")

    issues = []

    # Check if run.py exists and is configured for Railway
    if os.path.exists('run.py'):
        print_pass("run.py exists (Railway deployment script)")

        with open('run.py', 'r') as f:
            content = f.read()

            # Check for timeout configuration
            if '--timeout' in content:
                if '300' in content:
                    print_pass("Gunicorn timeout set to 300s")
                elif '120' in content:
                    print_warn("Gunicorn timeout is 120s (consider increasing to 300s)")
                else:
                    print_warn("Gunicorn timeout detected but value unclear")
            else:
                print_fail("No gunicorn timeout configured")
                issues.append("Missing gunicorn timeout in run.py")

            # Check for workers configuration
            if '--workers' in content:
                if "'2'" in content or '"2"' in content or ', 2' in content:
                    print_pass("Gunicorn configured with 2 workers")
                else:
                    print_warn("Gunicorn workers configuration unclear")
            else:
                print_fail("No gunicorn workers configured")
                issues.append("Missing gunicorn workers in run.py")
    else:
        print_fail("run.py missing")
        issues.append("Missing run.py for Railway deployment")

    # Check Procfile
    if os.path.exists('Procfile'):
        print_pass("Procfile exists")

        with open('Procfile', 'r') as f:
            content = f.read()
            if 'python run.py' in content or 'python3 run.py' in content:
                print_pass("Procfile uses run.py")
            else:
                print_warn("Procfile doesn't use run.py - check configuration")
    else:
        print_warn("Procfile missing (Railway will use default)")

    # Check requirements.txt
    if os.path.exists('requirements.txt'):
        print_pass("requirements.txt exists")

        with open('requirements.txt', 'r') as f:
            content = f.read()

            # Check for Flask-Caching
            if 'Flask-Caching' in content:
                print_pass("Flask-Caching installed (performance optimization)")
            else:
                print_warn("Flask-Caching not in requirements.txt")

            # Check for gunicorn
            if 'gunicorn' in content:
                print_pass("gunicorn installed")
            else:
                print_fail("gunicorn not in requirements.txt")
                issues.append("Missing gunicorn in requirements.txt")
    else:
        print_fail("requirements.txt missing")
        issues.append("Missing requirements.txt")

    return len(issues) == 0, issues

def check_git_status():
    """Check Git repository status"""
    print_header("5. Git Repository Status")

    issues = []

    # Check if git is initialized
    if not os.path.exists('.git'):
        print_fail("Not a Git repository")
        issues.append("Not a Git repository - run: git init")
        return False, issues

    import subprocess

    try:
        # Check for uncommitted changes
        result = subprocess.run(['git', 'status', '--porcelain'],
                              capture_output=True, text=True)

        if result.returncode != 0:
            print_fail("Could not check git status")
            issues.append("Git status check failed")
            return False, issues

        uncommitted = result.stdout.strip()

        if uncommitted:
            print_warn("Uncommitted changes detected:")
            for line in uncommitted.split('\n')[:5]:  # Show first 5
                print(f"      {line}")
            if len(uncommitted.split('\n')) > 5:
                print(f"      ... and {len(uncommitted.split('\n')) - 5} more")

            issues.append("Commit changes before deploying: git add . && git commit -m 'Your message'")
        else:
            print_pass("No uncommitted changes")

        # Check current branch
        result = subprocess.run(['git', 'branch', '--show-current'],
                              capture_output=True, text=True)

        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch == 'main' or branch == 'master':
                print_pass(f"On main branch ({branch})")
            else:
                print_warn(f"On branch '{branch}' (not main)")

    except Exception as e:
        print_fail(f"Git check failed: {e}")
        issues.append("Git check failed")

    return len(issues) == 0, issues

def run_validation():
    """Run all validation checks"""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}🚀 Railway Deployment Validation")
    print(f"   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(Style.RESET_ALL)

    all_issues = []

    # Run all checks
    checks = [
        ("Environment", check_environment_config),
        ("Connectivity", check_database_connections),
        ("Sync Status", check_data_sync_status),
        ("Code Quality", check_code_quality),
        ("Git Status", check_git_status),
    ]

    results = {}
    for name, check_func in checks:
        try:
            passed, issues = check_func()
            results[name] = passed
            all_issues.extend(issues)
        except Exception as e:
            print_fail(f"Check failed: {e}")
            results[name] = False
            all_issues.append(f"{name} check failed: {e}")

    # Summary
    print_header("Validation Summary")

    total_checks = len(results)
    passed_checks = sum(1 for p in results.values() if p)

    for name, passed in results.items():
        if passed:
            print_pass(f"{name:20} PASSED")
        else:
            print_fail(f"{name:20} FAILED")

    print()

    if passed_checks == total_checks:
        print(f"{Fore.GREEN}{Style.BRIGHT}✅ ALL CHECKS PASSED - READY TO DEPLOY!{Style.RESET_ALL}")
        print()
        print("Next steps:")
        print("   1. git push origin main")
        print("   2. Monitor Railway deployment logs")
        print("   3. Verify app is working: https://your-app.railway.app")
        return 0
    else:
        print(f"{Fore.RED}{Style.BRIGHT}❌ {len(all_issues)} ISSUES FOUND - FIX BEFORE DEPLOYING{Style.RESET_ALL}")
        print()
        print("Issues to fix:")
        for i, issue in enumerate(all_issues, 1):
            print(f"   {i}. {issue}")
        return 1

if __name__ == '__main__':
    try:
        sys.exit(run_validation())
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}❌ Validation cancelled{Style.RESET_ALL}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Fore.RED}❌ Validation failed: {e}{Style.RESET_ALL}")
        if '--debug' in sys.argv:
            raise
        sys.exit(1)
