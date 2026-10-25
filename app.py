import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import json
from functools import lru_cache
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import calendar
import base64
import time
import io
import re
# Optional Google Generative AI import
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    GEMINI_AVAILABLE = False
    print("⚠️ Google Generative AI not available - using Python OCR")

OPENROUTER_AVAILABLE = False
OpenAI = None

# Python OCR imports
try:
    import cv2
    import numpy as np
    import pytesseract
    from PIL import Image, ImageEnhance, ImageFilter
    import re
    
    # Auto-configure Tesseract path for Windows
    if os.name == 'nt':  # Windows
        import platform
        common_tesseract_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            r"C:\Users\%USERNAME%\AppData\Local\Tesseract-OCR\tesseract.exe"
        ]
        
        for path in common_tesseract_paths:
            expanded_path = os.path.expandvars(path)
            if os.path.exists(expanded_path):
                pytesseract.pytesseract.tesseract_cmd = expanded_path
                print(f"✅ Auto-configured Tesseract at: {expanded_path}")
                break
    
    PYTHON_OCR_AVAILABLE = True
    print("✅ Python OCR (Tesseract + OpenCV) available")
except ImportError as e:
    PYTHON_OCR_AVAILABLE = False
    print(f"⚠️ Python OCR not available: {e}")
    print("   Install with: pip install opencv-python pytesseract pillow")

from io import BytesIO
from sqlalchemy import text

# --- PostgreSQL-Only Configuration ---
# Import pure PostgreSQL business logic modules
from core.logic_postgresql import (
    load_booking_data, load_booking_data_for_calculations, create_demo_data,
    get_daily_activity, get_overall_calendar_day_info,
    extract_booking_info_from_image_content,
    check_duplicate_guests, analyze_existing_duplicates,
    add_new_booking, update_booking, delete_booking_by_id, cancel_booking_by_id,
    prepare_dashboard_data,
    add_expense_to_database, get_expenses_from_database
)

# Import AI duplicate detector (optional for Railway deployment)
try:
    from core.ai_duplicate_detector import ai_duplicate_detector
    print("✅ AI duplicate detector loaded")
except ImportError:
    print("⚠️ AI duplicate detector not available - using fallback")
    ai_duplicate_detector = None

# Import dashboard processing module  
from core.dashboard_routes import process_dashboard_data, safe_to_dict_records

# Import pure PostgreSQL database service
from core.database_service_postgresql import init_database_service, get_database_service, DatabaseConfig

# Import crawling service for authenticated web scraping
from core.crawl_service import CrawlIntegration

# Import sync API blueprints (optional - removed during cleanup)
# from railway_sync_api import sync_bp
# from sync_api_routes import sync_api_bp

# Import auto sync service
from core.auto_sync_service import auto_sync_service

# Import production booking extractor
PRODUCTION_EXTRACTOR_AVAILABLE = False
extract_booking_from_image_flask = None

try:
    import sys
    import os
    
    # Add current directory to path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
    
    from production_booking_extractor import extract_booking_from_image_flask
    PRODUCTION_EXTRACTOR_AVAILABLE = True
    print("✅ Production booking extractor loaded successfully")
except ImportError as e:
    print(f"⚠️ Production booking extractor import failed: {e}")
    PRODUCTION_EXTRACTOR_AVAILABLE = False
except Exception as e:
    print(f"❌ Production booking extractor error: {e}")
    PRODUCTION_EXTRACTOR_AVAILABLE = False

# Import optimized crawling and performance monitoring
from core.performance_dashboard import performance_bp

# Import caching configuration
from core.cache_config import init_cache, clear_booking_cache

# Import backup and export functionality
from backup_routes import register_backup_routes

# Learning mode removed for simplicity

# Import test dashboard blueprint (optional - for development/testing only)
try:
    from core.test_dashboard_route import test_dashboard_bp
    test_dashboard_available = True
except ImportError:
    print("ℹ️  Test dashboard module not available (expected in production)")
    test_dashboard_available = False

# Configuration
BASE_DIR = Path(__file__).resolve().parent

# Smart environment file loading
# Railway auto-detection: Load .env.railway if in Railway environment
is_railway = bool(os.getenv('RAILWAY_ENVIRONMENT_ID') or os.getenv('RAILWAY_PROJECT_ID') or os.getenv('RAILWAY_SERVICE_ID'))

if is_railway:
    # Railway environment detected - use Railway-specific config
    railway_env_path = BASE_DIR / ".env.railway"
    if railway_env_path.exists():
        load_dotenv(railway_env_path)
        print(f"🚂 Railway environment detected - loaded: {railway_env_path}")
    else:
        load_dotenv(BASE_DIR / ".env")  # Fallback to .env
        print(f"⚠️ Railway detected but .env.railway not found - using .env fallback")
else:
    # Local environment - use standard .env file
    load_dotenv(BASE_DIR / ".env")
    print(f"🏠 Local environment - loaded: {BASE_DIR / '.env'}")

app = Flask(__name__, template_folder=BASE_DIR / "templates", static_folder=BASE_DIR / "static")

# Register sync blueprints (commented out - modules removed during cleanup)
# app.register_blueprint(sync_bp)
# app.register_blueprint(sync_api_bp)

# Learning mode blueprint removed

# Register test dashboard blueprint (only if available)
if test_dashboard_available:
    app.register_blueprint(test_dashboard_bp)
    print("✅ Test dashboard blueprint registered")
else:
    print("ℹ️  Test dashboard blueprint skipped (not available in production)")

# Register performance monitoring blueprint
app.register_blueprint(performance_bp)

# Register backup and export routes
register_backup_routes(app)
print("✅ Backup and export routes registered")

# Production configuration with temporary debug for auto sync
railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
app.config['ENV'] = 'production'
app.config['DEBUG'] = railway_env  # Enable debug on Railway to troubleshoot auto sync menu
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")

# ⚡ PERFORMANCE: Initialize caching system
cache = init_cache(app)
print("✅ Flask-Caching initialized with 30s TTL")

# ==============================================================================
# CACHE CONTROL FOR TEMPLATES
# ==============================================================================

# Debug pages that print connection settings are closed to the public (Oct 25: /debug/env showed the first 50 characters
# of DATABASE_URL — the password — to anyone). Open them only by setting DEBUG_ROUTES=1 on the server for a moment.
_SECRET_DEBUG_PATHS = ('/debug/env', '/debug/local_postgres', '/debug/db-config')


@app.before_request
def _close_secret_debug_pages():
    if request.path.rstrip('/') in _SECRET_DEBUG_PATHS and os.getenv('DEBUG_ROUTES') != '1':
        return 'Not found', 404


@app.after_request
def add_header(response):
    """
    Add cache control headers to prevent browser caching of HTML templates.
    This ensures users always see the latest version after deployment.
    Static files (CSS, JS, images) can still be cached via /static route.
    """
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    elif request.path.startswith('/static/') and request.args.get('v') and response.status_code == 200:
        # asset() URLs carry the file's version, so the phone can keep them without asking again
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return response


@app.template_global()
def asset(filename):
    """url_for('static') + ?v=<file mtime>: cached for good, and a new deploy changes the URL."""
    try:
        v = int(os.path.getmtime(os.path.join(app.static_folder, filename)))
    except OSError:
        v = 0
    return url_for('static', filename=filename, v=v)


@app.template_global()
def page_version(template, *scripts):
    """Newest mtime of a page's template + its scripts. A page that refreshes itself in place reloads fully when
    this changes (a new deploy), so new buttons never arrive without the code behind them."""
    paths = [os.path.join(app.root_path, app.template_folder, template)] + [os.path.join(app.static_folder, s) for s in scripts]
    v = 0
    for p in paths:
        try:
            v = max(v, int(os.path.getmtime(p)))
        except OSError:
            pass
    return v

# ==============================================================================
# HELPER FUNCTIONS
# ==============================================================================

def safe_parse_vietnamese_number(value, default=0.0):
    """Safely parse Vietnamese-formatted numbers like '400,000' or '400.000'"""
    if not value:
        return default
    
    # If it's already a number, return it
    if isinstance(value, (int, float)):
        return float(value)
    
    # Convert to string and clean it
    str_value = str(value).strip()
    if not str_value:
        return default
    
    try:
        # Remove common Vietnamese thousand separators
        cleaned = str_value.replace(',', '').replace('.', '').replace(' ', '')
        
        # Handle VND suffix
        cleaned = cleaned.replace('VND', '').replace('đ', '').replace('₫', '').strip()
        
        # If there are still non-numeric characters, try to extract numbers
        import re
        numbers_only = re.sub(r'[^\d]', '', cleaned)
        
        if numbers_only:
            return float(numbers_only)
        else:
            print(f"⚠️ [NUMBER_PARSE] Could not parse number from '{value}', using default {default}")
            return default
            
    except (ValueError, TypeError) as e:
        print(f"⚠️ [NUMBER_PARSE] Error parsing '{value}': {e}, using default {default}")
        return default

# ========================================
# SMART DATABASE CONFIGURATION
# ========================================

# Get database source preference
database_source = os.getenv('DATABASE_SOURCE', 'auto').lower()
local_db_url = os.getenv('LOCAL_DATABASE_URL')
railway_db_url = os.getenv('RAILWAY_DATABASE_URL')
explicit_db_url = os.getenv('DATABASE_URL')

print(f"🎯 DATABASE_SOURCE setting: {database_source}")
print(f"🔍 Local DB available: {'✅' if local_db_url else '❌'}")
print(f"🔍 Railway DB available: {'✅' if railway_db_url else '❌'}")
print(f"🔍 Explicit DATABASE_URL: {'✅' if explicit_db_url else '❌'}")

# Smart database selection logic
database_url = None

if database_source == 'local':
    if local_db_url:
        database_url = local_db_url
        print(f"🏠 Using LOCAL PostgreSQL: {database_url[:50]}...")
    else:
        print(f"❌ LOCAL database requested but LOCAL_DATABASE_URL not set")
        
elif database_source == 'railway':
    if railway_db_url:
        database_url = railway_db_url
        print(f"🚂 Using RAILWAY PostgreSQL: {database_url[:50]}...")
    else:
        print(f"❌ RAILWAY database requested but RAILWAY_DATABASE_URL not set")
        
elif database_source == 'auto':
    # Smart Auto-detect: Prefer Railway for data completeness, fallback to local
    is_railway_deployed = bool(os.getenv('RAILWAY_ENVIRONMENT_ID') or os.getenv('RAILWAY_PROJECT_ID') or os.getenv('RAILWAY_SERVICE_ID'))

    # CRITICAL FIX: Railway provides multiple DATABASE_URL variants
    # Priority: PUBLIC_URL (for free/hobby without Private Networking) > internal URL
    railway_public_url = os.getenv('DATABASE_PUBLIC_URL') or os.getenv('POSTGRES_PUBLIC_URL')
    railway_private_url = os.getenv('DATABASE_PRIVATE_URL') or os.getenv('POSTGRES_PRIVATE_URL')
    railway_generic_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')

    print(f"🔍 Railway deployment detected: {'✅' if is_railway_deployed else '❌'}")
    print(f"🔍 Railway Public URL: {'✅' if railway_public_url else '❌'}")
    print(f"🔍 Railway Private URL: {'✅' if railway_private_url else '❌'}")
    print(f"🔍 Railway Generic URL: {'✅' if railway_generic_url else '❌'}")

    # Priority: Railway public URL > configured Railway URL > generic URL > local DB
    if is_railway_deployed:
        # When deployed to Railway, prefer public URL (works without Private Networking)
        if railway_public_url:
            database_url = railway_public_url
            print(f"🚂 AUTO: Railway production (PUBLIC) - Using public PostgreSQL: {database_url[:50]}...")
        elif railway_generic_url and 'railway.internal' not in railway_generic_url:
            # Use generic URL if it's NOT the internal networking URL
            database_url = railway_generic_url
            print(f"🚂 AUTO: Railway production - Using PostgreSQL: {database_url[:50]}...")
        elif railway_private_url:
            # Fallback to private URL (requires Private Networking enabled)
            database_url = railway_private_url
            print(f"⚠️ AUTO: Using PRIVATE URL (requires Private Networking): {database_url[:50]}...")
        elif railway_generic_url:
            # Last resort - use whatever DATABASE_URL is set
            database_url = railway_generic_url
            print(f"⚠️ AUTO: Using generic DATABASE_URL (may need Private Networking): {database_url[:50]}...")
        else:
            print(f"❌ AUTO: Railway deployed but no DATABASE_URL found!")
    elif railway_db_url:
        # Development with explicit Railway URL
        database_url = railway_db_url
        print(f"🧪 AUTO: Development with Railway data - Using Railway DB: {database_url[:50]}...")
    elif local_db_url:
        # Local development
        database_url = local_db_url
        print(f"🏠 AUTO: Local development - Using local PostgreSQL: {database_url[:50]}...")
    else:
        print(f"❌ AUTO: No database URL found - Check your environment variables")
        
else:
    print(f"❌ Invalid DATABASE_SOURCE: {database_source}. Use 'local', 'railway', or 'auto'")

if database_url:
    print(f"✅ Selected database: {database_url[:50]}...")
    print(f"📏 Database URL length: {len(database_url)} characters")
else:
    print(f"🚨 No database configured!")

# Fix common Railway environment variable issues
if database_url:
    print(f"🔍 Raw DATABASE_URL: {database_url}")

    # Remove line breaks and normalize whitespace - CRITICAL FIX
    database_url = ' '.join(database_url.split())
    print(f"🔧 After line break removal: {database_url[:50]}...")

    # Remove "DATABASE_URL=" or "DATABASE_URL = " or "DATABASE_URL =" prefix if it exists
    if database_url.startswith('DATABASE_URL'):
        print("🔧 Fixing DATABASE_URL prefix issue...")
        # Handle all variations: "DATABASE_URL=", "DATABASE_URL = ", "DATABASE_URL ="
        if database_url.startswith('DATABASE_URL = '):
            database_url = database_url.replace('DATABASE_URL = ', '', 1)
        elif database_url.startswith('DATABASE_URL ='):
            database_url = database_url.replace('DATABASE_URL =', '', 1)
        elif database_url.startswith('DATABASE_URL='):
            database_url = database_url.replace('DATABASE_URL=', '', 1)
        print(f"🔧 After prefix removal: {database_url[:50]}...")

    # Remove any quotes that might be added
    original_url = database_url
    database_url = database_url.strip('\'"')
    if original_url != database_url:
        print(f"🔧 Removed quotes: {database_url[:50]}...")

    # Railway internal networking URL - will work if Private Networking is enabled
    # If not enabled, Railway will show proper error messages
    if 'postgres.railway.internal' in database_url or 'railway.internal' in database_url:
        print("✅ Using Railway internal networking URL")
        print(f"   Database URL: {database_url[:60]}...")
        print("   Note: Requires Private Networking enabled in Railway")

    # Final validation
    if database_url:
        print(f"🔧 Final cleaned URL: {database_url[:50]}...")
        print(f"🔧 Final URL length: {len(database_url)} characters")
    else:
        print("❌ URL became empty after cleaning!")

# Debug: Check if URL is being truncated
if database_url and len(database_url) < 90:  # Expected length is ~92 characters
    print(f"⚠️ WARNING: DATABASE_URL appears truncated (expected ~92 chars, got {len(database_url)})")
    print(f"⚠️ Current URL: {database_url}")
    print("⚠️ Expected format: postgresql://postgres:<password>@mainline.proxy.rlwy.net:36647/railway")

# Railway PostgreSQL connection validation
if not database_url or database_url == 'None' or len(database_url.strip()) == 0:
    print("🚨 POSTGRESQL NOT CONFIGURED!")
    print("   📍 Current environment variables:")
    for key in sorted(os.environ.keys()):
        if 'DATABASE' in key or 'POSTGRES' in key:
            print(f"      {key}: {os.environ[key][:30]}...")
    print("")
    print("🔧 FALLBACK: Using SQLite to prevent crash...")
    database_url = "sqlite:///fallback.db"
elif database_url.startswith('postgresql://'):
    print("✅ POSTGRESQL DETECTED!")
    try:
        # Extract host from URL for display
        if '@' in database_url:
            host_part = database_url.split('@')[1].split('/')[0] if '/' in database_url.split('@')[1] else database_url.split('@')[1]
            print(f"   🏗️ Database host: {host_part}")
        print("   🚀 Application will use PostgreSQL database")
        
        # Basic validation - just check it's a proper postgresql:// URL
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        
        # Only check essential components for PostgreSQL
        if parsed.scheme == 'postgresql' and parsed.netloc and parsed.hostname:
            print(f"   ✅ Database: {parsed.path.lstrip('/') or 'default'}")
            print(f"   ✅ Host: {parsed.hostname}:{parsed.port or 5432}")
            
            # Convert to SQLAlchemy-compatible URL for better compatibility
            if not database_url.startswith('postgresql+psycopg2://'):
                database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://')
                print(f"   🔧 Using SQLAlchemy driver: postgresql+psycopg2://")
        else:
            raise ValueError(f"Invalid PostgreSQL URL - missing required components")
        
    except Exception as url_error:
        print(f"⚠️ POSTGRESQL URL VALIDATION FAILED: {url_error}")
        print(f"   URL: {database_url[:50]}...")
        print("   🔧 USING FALLBACK SQLite...")
        database_url = "sqlite:///fallback.db"
else:
    print(f"⚠️ UNEXPECTED DATABASE_URL FORMAT: {database_url[:50]}...")
    print("   Expected: postgresql://user:pass@host:port/dbname")
    print("   🔧 USING FALLBACK SQLite...")
    database_url = "sqlite:///fallback.db"

try:
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # CRITICAL: Enhanced connection settings for Railway PostgreSQL stability
    # Addresses SSL SYSCALL EOF errors with proper keepalive and SSL configuration
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_size': 10,              # Connection pool size
        'pool_recycle': 3600,         # Recycle connections after 1 hour (prevents stale connections)
        'pool_pre_ping': True,        # Test connections before using them (critical for detecting dead connections)
        'pool_timeout': 30,           # Wait up to 30s for connection from pool
        'max_overflow': 5,            # Allow 5 extra connections beyond pool_size during high load
        'connect_args': {
            'connect_timeout': 10,    # 10 second connection timeout
            'options': '-c statement_timeout=30000',  # 30 second query timeout
            'sslmode': 'require',     # ENFORCE SSL for Railway (changed from 'prefer')
            'keepalives': 1,          # Enable TCP keepalives
            'keepalives_idle': 30,    # Start keepalive probes after 30s of idle
            'keepalives_interval': 10, # Send keepalive probe every 10s
            'keepalives_count': 5     # Drop connection after 5 failed probes
        }
    }

    print(f"✅ Database configured: {database_url[:30]}...")
    print(f"✅ Connection timeout: 10s | Query timeout: 30s")

    # NOTE: Removed connection test - it was causing unnecessary SQLite fallback
    # The app will naturally connect when needed, and show proper errors if it fails
    # This matches the working configuration from commit 691bf70

except Exception as e:
    print(f"❌ Database configuration error: {e}")
    print("🔧 Using SQLite fallback...")
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///fallback.db"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize PostgreSQL database service (non-blocking for Railway healthchecks)
try:
    init_database_service(app)
    print("✅ Database service initialized successfully")
except Exception as db_init_error:
    print(f"⚠️ Database service initialization delayed: {db_init_error}")
    print("   App will continue - database will connect on first request")

@app.context_processor
def inject_pandas():
    return dict(pd=pd)

# Custom Jinja2 filters for date formatting
@app.template_filter('safe_date_format')
def safe_date_format(date_value, format_string='%d/%m/%y'):
    """Safely format date values, handling None, NaT, and string values"""
    try:
        if date_value is None:
            return 'N/A'
        
        if isinstance(date_value, str):
            if date_value.lower() in ['nat', 'none', 'null', '', 'n/a']:
                return 'N/A'
            try:
                date_value = pd.to_datetime(date_value)
            except:
                return date_value
        
        if pd.isna(date_value):
            return 'N/A'
            
        if hasattr(date_value, 'strftime'):
            return date_value.strftime(format_string)
        
        return str(date_value)
        
    except Exception as e:
        print(f"Error formatting date {date_value}: {e}")
        return 'Error'

@app.template_filter('safe_day_name')
def safe_day_name(date_value):
    """Safely get day name from date value"""
    try:
        if date_value is None or pd.isna(date_value):
            return ''
        
        if isinstance(date_value, str):
            if date_value.lower() in ['nat', 'none', 'null', '', 'n/a']:
                return ''
            try:
                date_value = pd.to_datetime(date_value)
            except:
                return ''
        
        if hasattr(date_value, 'strftime'):
            return date_value.strftime('%A')
        
        return ''
        
    except Exception as e:
        print(f"Error getting day name for {date_value}: {e}")
        return ''

@app.template_filter('is_valid_date')
def is_valid_date(date_value):
    """Check if date value is valid"""
    try:
        if date_value is None:
            return False
        
        if isinstance(date_value, str):
            if date_value.lower() in ['nat', 'none', 'null', '', 'n/a']:
                return False
            try:
                pd.to_datetime(date_value)
                return True
            except:
                return False
        
        if pd.isna(date_value):
            return False
            
        return hasattr(date_value, 'strftime')
        
    except:
        return False

# Environment configuration (PostgreSQL only)
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Only for Gemini AI
TOTAL_HOTEL_CAPACITY = 6  # Total: 6 rooms (118 Hang Bac: 4 rooms, 18 Hang Be: 2 rooms)

# Initialize Google Gemini AI (for image processing only)
if GOOGLE_API_KEY and genai:
    genai.configure(api_key=GOOGLE_API_KEY)

# --- PostgreSQL Data Loading Function ---
def load_data(force_fresh: bool = False):
    """Load booking data from PostgreSQL only"""
    if force_fresh:
        print("🔄 Loading booking data from PostgreSQL with FRESH connection...")
    else:
        print("Loading booking data from PostgreSQL...")
    try:
        # Load data directly from PostgreSQL
        df = load_booking_data(force_fresh=force_fresh)
        
        if df.empty:
            print("No booking data found, creating demo data...")
            create_demo_data()
            df = load_booking_data(force_fresh=force_fresh)
        
        print(f"✅ Loaded {len(df)} bookings from PostgreSQL")
        return df, len(df)
        
    except Exception as e:
        print(f"Error loading data from PostgreSQL: {e}")
        # Return empty DataFrame if error
        return pd.DataFrame(), 0

# --- MAIN ROUTES ---


# ── The rest of the app lives in app_parts/ (Oct 25: one 19,000-line file cost Claude too much context) ──────────
# Each part is executed IN THIS MODULE'S NAMESPACE, in file-name order — exactly as if its text were still here, so
# routes, endpoint names and helpers are unchanged. Find a route / function in docs/CODEMAP.md.
for _part in sorted((BASE_DIR / 'app_parts').glob('p[0-9][0-9]_*.py')):
    exec(compile(_part.read_text(encoding='utf-8'), str(_part), 'exec'), globals())


if __name__ == '__main__':
    # For local development only
    port = os.environ.get('PORT')
    if port and port.isdigit():
        app.run(host='0.0.0.0', port=int(port))
    else:
        app.run(host='0.0.0.0', port=5000)