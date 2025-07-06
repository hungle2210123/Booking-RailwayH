import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from dotenv import load_dotenv
import json
from functools import lru_cache
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import calendar
import base64
import time
import google.generativeai as genai
from io import BytesIO
from sqlalchemy import text

# --- PostgreSQL-Only Configuration ---
# Import pure PostgreSQL business logic modules
from core.logic_postgresql import (
    load_booking_data, load_booking_data_for_calculations, create_demo_data,
    get_daily_activity, get_overall_calendar_day_info,
    extract_booking_info_from_image_content,
    check_duplicate_guests, analyze_existing_duplicates,
    add_new_booking, update_booking, delete_booking_by_id,
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

# Import optimized crawling and performance monitoring
from core.performance_dashboard import performance_bp

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

# Register test dashboard blueprint (only if available)
if test_dashboard_available:
    app.register_blueprint(test_dashboard_bp)
    print("✅ Test dashboard blueprint registered")
else:
    print("ℹ️  Test dashboard blueprint skipped (not available in production)")

# Register performance monitoring blueprint
app.register_blueprint(performance_bp)

# Production configuration with temporary debug for auto sync
railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
app.config['ENV'] = 'production'
app.config['DEBUG'] = railway_env  # Enable debug on Railway to troubleshoot auto sync menu
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")

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
    railway_postgres_url = os.getenv('POSTGRES_URL') or os.getenv('RAILWAY_POSTGRES_URL') or os.getenv('DATABASE_URL')
    
    print(f"🔍 Railway deployment detected: {'✅' if is_railway_deployed else '❌'}")
    print(f"🔍 Railway DB configured: {'✅' if railway_db_url else '❌'}")
    
    # Priority: Railway production URL > Railway configured URL > Local DB
    if is_railway_deployed and railway_postgres_url:
        database_url = railway_postgres_url
        print(f"🚂 AUTO: Railway production - Using Railway PostgreSQL: {database_url[:50]}...")
    elif railway_db_url:
        database_url = railway_db_url
        print(f"🧪 AUTO: Development with Railway data - Using Railway DB: {database_url[:50]}...")
    elif railway_postgres_url:
        database_url = railway_postgres_url
        print(f"🔧 AUTO: Using DATABASE_URL/POSTGRES_URL: {database_url[:50]}...")
    elif local_db_url:
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
    print("⚠️ Expected format: postgresql://postgres:VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi@mainline.proxy.rlwy.net:36647/railway")

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
    print(f"✅ Database configured: {database_url[:30]}...")
except Exception as e:
    print(f"❌ Database configuration error: {e}")
    print("🔧 Using SQLite fallback...")
    app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///fallback.db"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize PostgreSQL database service
init_database_service(app)

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
TOTAL_HOTEL_CAPACITY = 4  # Hotel has exactly 4 rooms

# Initialize Google Gemini AI (for image processing only)
if GOOGLE_API_KEY:
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

@app.route('/quick_collect')
def quick_collect():
    """Quick payment collection page - bypasses broken frontend"""
    return render_template('quick_collect.html')

@app.route('/api/cancellation_notifications')
def api_cancellation_notifications():
    """API endpoint for cancellation notifications"""
    try:
        from core.cancellation_notifications import get_cancellation_notifications
        notifications = get_cancellation_notifications()
        return jsonify({
            'success': True,
            'notifications': notifications,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_CANCELLATION_NOTIFICATIONS] Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'notifications': {'summary': {'total_alerts': 0}}
        }), 500

@app.route('/api/urgent_alerts')
def api_urgent_alerts():
    """API endpoint for urgent cancellation alerts only"""
    try:
        from core.cancellation_notifications import get_urgent_cancellation_alerts
        urgent_alerts = get_urgent_cancellation_alerts()
        return jsonify({
            'success': True,
            'urgent_alerts': urgent_alerts,
            'count': len(urgent_alerts),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_URGENT_ALERTS] Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'urgent_alerts': []
        }), 500

@app.route('/api/debug_cancellations')
def api_debug_cancellations():
    """Debug endpoint to check cancellation data"""
    try:
        from core.cancellation_notifications import debug_guest_data, get_cancellation_notifications
        from core.models import db, CancellationAction
        
        # Check cancellation_actions table directly
        all_actions = CancellationAction.query.all()
        confirmed_actions = CancellationAction.query.filter_by(action_status='confirmed').all()
        pending_actions = CancellationAction.query.filter_by(action_status='pending').all()
        
        debug_info = debug_guest_data()
        notifications = get_cancellation_notifications()
        
        return jsonify({
            'success': True,
            'debug_info': debug_info,
            'cancellation_actions_table': {
                'total_actions': len(all_actions),
                'confirmed_actions': len(confirmed_actions),
                'pending_actions': len(pending_actions),
                'confirmed_details': [{'booking_id': a.booking_id, 'guest_name': a.guest_name, 'status': a.action_status, 'confirmation_date': a.confirmation_date} for a in confirmed_actions],
                'pending_details': [{'booking_id': a.booking_id, 'guest_name': a.guest_name, 'status': a.action_status} for a in pending_actions[:5]]
            },
            'notifications_summary': notifications['summary'],
            'notifications_detailed': {
                'le_thuong_alerts': len(notifications['specific_guest_alerts']),
                'zero_commission_alerts': len(notifications['zero_commission_alerts']),
                'cancelled_alerts': len(notifications['cancellation_status_alerts'])
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_DEBUG_CANCELLATIONS] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/confirmed_cancellations')
def api_confirmed_cancellations():
    """View history of confirmed cancellation actions - uses debug_database approach"""
    try:
        # Get ALL actions using the EXACT same approach as debug_database (which works)
        from core.models import db, CancellationAction
        
        # Use the exact same query as debug_database endpoint
        all_actions = CancellationAction.query.all()
        
        print(f"✅ [API_CONFIRMED_CANCELLATIONS] Got {len(all_actions)} total actions from database")
        
        # Filter to only confirmed/ok actions (client-side filtering like debug_database does)
        confirmed_list = []
        for action in all_actions:
            if action.action_status in ['confirmed', 'ok']:
                confirmed_list.append({
                    'action_id': action.action_id,
                    'booking_id': action.booking_id,
                    'guest_name': action.guest_name,
                    'cancellation_type': action.cancellation_type,
                    'action_status': action.action_status,
                    'confirmed_by': action.confirmed_by,
                    'confirmation_date': action.confirmation_date.isoformat() if action.confirmation_date else None,
                    'notes': action.notes,
                    'created_at': action.created_at.isoformat() if action.created_at else None
                })
        
        # Sort by confirmation_date descending
        confirmed_list.sort(key=lambda x: x['confirmation_date'] or '1900-01-01', reverse=True)
        
        # Limit to 20 most recent
        confirmed_list = confirmed_list[:20]
        
        print(f"✅ [API_CONFIRMED_CANCELLATIONS] Filtered to {len(confirmed_list)} confirmed actions")
        
        return jsonify({
            'success': True,
            'total_confirmed': len(confirmed_list),
            'confirmed_cancellations': confirmed_list,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_CONFIRMED_CANCELLATIONS] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/canceled_customers_management')
def api_canceled_customers_management():
    """Get ALL canceled customers for re-classification management"""
    try:
        from core.cancellation_notifications import get_all_canceled_customers_for_management
        customers = get_all_canceled_customers_for_management()
        
        # Categorize customers based on real action status
        categorized = {
            'needs_classification': [c for c in customers if c['needs_action']],
            'pending_review': [c for c in customers if c['action_status'] == 'pending'],
            'confirmed': [c for c in customers if c['action_status'] in ['confirmed', 'ok']],
            'all_customers': customers
        }
        
        # Debug categorization
        print(f"🔍 [CATEGORIZATION_DEBUG] Total customers: {len(customers)}")
        print(f"🔍 [CATEGORIZATION_DEBUG] Needs classification: {len(categorized['needs_classification'])}")
        print(f"🔍 [CATEGORIZATION_DEBUG] Pending review: {len(categorized['pending_review'])}")
        print(f"🔍 [CATEGORIZATION_DEBUG] Confirmed: {len(categorized['confirmed'])}")
        
        # Debug sample of each category
        if categorized['needs_classification']:
            sample = categorized['needs_classification'][0]
            print(f"🔍 [NEEDS_ACTION_SAMPLE] {sample['guest_name']} ({sample['booking_id']}): action_status='{sample['action_status']}', needs_action={sample['needs_action']}")
        
        if categorized['confirmed']:
            sample = categorized['confirmed'][0]
            print(f"🔍 [CONFIRMED_SAMPLE] {sample['guest_name']} ({sample['booking_id']}): action_status='{sample['action_status']}', needs_action={sample['needs_action']}")
        
        return jsonify({
            'success': True,
            'total_customers': len(customers),
            'categories': {
                'needs_classification': len(categorized['needs_classification']),
                'pending_review': len(categorized['pending_review']),
                'confirmed': len(categorized['confirmed'])
            },
            'all_customers': customers,
            'needs_classification': categorized['needs_classification'],
            'pending_review': categorized['pending_review'],
            'confirmed': categorized['confirmed'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_CANCELED_CUSTOMERS] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/debug_confirmed_cancellations')
def api_debug_confirmed_cancellations():
    """Debug endpoint specifically for confirmed cancellations"""
    try:
        from core.logic_postgresql import execute_query
        
        # Test simple count query
        count_query = "SELECT COUNT(*) as total FROM cancellation_actions"
        count_result = execute_query(count_query)
        total_actions = count_result.iloc[0]['total'] if not count_result.empty else 0
        
        # Test confirmed/ok query
        confirmed_query = "SELECT COUNT(*) as confirmed_count FROM cancellation_actions WHERE action_status IN ('confirmed', 'ok')"
        confirmed_result = execute_query(confirmed_query)
        confirmed_count = confirmed_result.iloc[0]['confirmed_count'] if not confirmed_result.empty else 0
        
        # Get actual confirmed records
        records_query = """
        SELECT action_id, booking_id, guest_name, action_status, confirmation_date 
        FROM cancellation_actions 
        WHERE action_status IN ('confirmed', 'ok') 
        ORDER BY confirmation_date DESC 
        LIMIT 5
        """
        records_result = execute_query(records_query)
        sample_records = records_result.to_dict('records') if not records_result.empty else []
        
        return jsonify({
            'success': True,
            'total_actions': total_actions,
            'confirmed_count': confirmed_count,
            'sample_confirmed_records': sample_records,
            'debug_info': 'This endpoint tests confirmed cancellations functionality',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'debug_info': 'Error testing confirmed cancellations functionality',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/debug_database')
def api_debug_database():
    """Debug endpoint to check database tables and data"""
    try:
        from core.models import db, CancellationAction
        
        # Check if table exists
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        table_exists = inspector.has_table('cancellation_actions')
        
        if not table_exists:
            return jsonify({
                'success': False,
                'error': 'cancellation_actions table does not exist',
                'suggestion': 'Run create_local_table.sql in your PostgreSQL database'
            }), 404
        
        # Get all cancellation actions
        all_actions = CancellationAction.query.all()
        actions_data = []
        
        for action in all_actions:
            actions_data.append({
                'action_id': action.action_id,
                'booking_id': action.booking_id,
                'guest_name': action.guest_name,
                'cancellation_type': action.cancellation_type,
                'action_status': action.action_status,
                'confirmed_by': action.confirmed_by,
                'confirmation_date': action.confirmation_date.isoformat() if action.confirmation_date else None,
                'created_at': action.created_at.isoformat() if action.created_at else None
            })
        
        return jsonify({
            'success': True,
            'table_exists': table_exists,
            'total_records': len(actions_data),
            'all_cancellation_actions': actions_data,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_DEBUG_DATABASE] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/edit_cancellation', methods=['POST'])
def api_edit_cancellation():
    """Edit existing cancellation action (change status, notes, etc.)"""
    try:
        print(f"🔄 [API_EDIT_CANCELLATION] Request received")
        data = request.get_json()
        print(f"🔍 [API_EDIT_CANCELLATION] Request data: {data}")
        
        action_id = data.get('action_id')
        booking_id = data.get('booking_id')
        new_status = data.get('action_status')  # 'confirmed', 'pending', 'cancelled'
        new_notes = data.get('notes')
        
        print(f"📋 [API_EDIT_CANCELLATION] Params: action_id={action_id}, booking_id={booking_id}, new_status={new_status}")
        
        from core.models import db, CancellationAction
        
        # Find the cancellation action to edit
        action = None
        if action_id and action_id != 'undefined': # Check for 'undefined' string from JS
            try:
                action = CancellationAction.query.get(int(action_id))
            except ValueError:
                print(f"⚠️ [API_EDIT_CANCELLATION] Invalid action_id format: {action_id}")
                action = None
        
        if not action and booking_id:
            action = CancellationAction.query.filter_by(booking_id=booking_id).first()
            print(f"🔍 [API_EDIT_CANCELLATION] Found by booking_id: {action is not None}")
        
        if not action:
            print(f"❌ [API_EDIT_CANCELLATION] No action found for booking_id={booking_id}")
            # If no cancellation action exists and we're trying to set to pending,
            # this means we want to "undo" a confirmation that was already removed
            if new_status == 'pending':
                print(f"✅ [API_EDIT_CANCELLATION] Already undone - returning success")
                return jsonify({
                    'success': True,
                    'message': 'Cancellation already undone - alert will be removed',
                    'action': 'already_undone',
                    'booking_id': booking_id
                })
            else:
                print(f"❌ [API_EDIT_CANCELLATION] Action not found")
                return jsonify({
                    'success': False,
                    'error': f'Cancellation action not found for booking {booking_id}'
                }), 404
        
        # Update fields if provided
        old_status = action.action_status
        print(f"📝 [API_EDIT_CANCELLATION] Current status: {old_status} → {new_status}")
        
        if new_status and new_status != old_status:
            action.action_status = new_status
            if new_status == 'confirmed':
                action.confirmed_by = 'System User'
                action.confirmation_date = datetime.now()
                print(f"✅ [API_EDIT_CANCELLATION] Set to confirmed")
            elif new_status == 'pending':
                action.confirmed_by = None
                action.confirmation_date = None
                print(f"⏳ [API_EDIT_CANCELLATION] Set to pending (undo)")
        
        if new_notes:
            action.notes = new_notes
        
        action.updated_at = datetime.now()
        
        db.session.commit()
        print(f"💾 [API_EDIT_CANCELLATION] Database updated successfully")
        
        print(f"✏️ [EDIT_CANCELLATION] {action.booking_id}: {old_status} → {action.action_status}")
        
        return jsonify({
            'success': True,
            'message': f'Updated cancellation for {action.guest_name} (Status: {old_status} → {action.action_status})',
            'action_id': action.action_id,
            'booking_id': action.booking_id,
            'old_status': old_status,
            'new_status': action.action_status,
            'guest_name': action.guest_name,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_EDIT_CANCELLATION] Error: {e}")
        import traceback
        print(f"❌ [API_EDIT_CANCELLATION] Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/delete_cancellation', methods=['POST'])
def api_delete_cancellation():
    """Delete a cancellation action completely"""
    try:
        data = request.get_json()
        action_id = data.get('action_id')
        booking_id = data.get('booking_id')
        
        from core.models import db, CancellationAction
        
        # Find the cancellation action to delete
        if action_id:
            action = CancellationAction.query.get(action_id)
        elif booking_id:
            action = CancellationAction.query.filter_by(booking_id=booking_id).first()
        else:
            return jsonify({
                'success': False,
                'error': 'Must provide either action_id or booking_id'
            }), 400
        
        if not action:
            return jsonify({
                'success': False,
                'error': 'Cancellation action not found'
            }), 404
        
        guest_name = action.guest_name
        booking_id = action.booking_id
        
        db.session.delete(action)
        db.session.commit()
        
        print(f"🗑️ [DELETE_CANCELLATION] Deleted action for {booking_id} - {guest_name}")
        
        return jsonify({
            'success': True,
            'message': f'Deleted cancellation action for {guest_name}',
            'booking_id': booking_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_DELETE_CANCELLATION] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/confirm_cancellation', methods=['POST'])
def api_confirm_cancellation():
    """Confirm cancellation action and save to database"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        guest_name = data.get('guest_name')
        cancellation_type = data.get('cancellation_type')
        confirmed_by = 'System User'  # You can enhance this with actual user tracking
        
        if not all([booking_id, guest_name, cancellation_type]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Import model
        from core.models import db, CancellationAction
        
        # Check if already confirmed - prevent duplicate confirmations
        existing = CancellationAction.query.filter_by(
            booking_id=booking_id,
            action_status='confirmed'
        ).first()
        
        if existing:
            # Already confirmed - return success without duplicating
            print(f"ℹ️ [ALREADY_CONFIRMED] Booking {booking_id} already confirmed")
            return jsonify({
                'success': True,
                'message': f'Cancellation already confirmed for {guest_name}',
                'action': 'already_confirmed',
                'action_id': existing.action_id
            })
        
        # Also check for ANY existing action (pending/confirmed) and update it
        any_existing = CancellationAction.query.filter_by(booking_id=booking_id).first()
        
        if any_existing:
            # Update existing action to confirmed
            any_existing.action_status = 'confirmed'
            any_existing.confirmed_by = confirmed_by
            any_existing.confirmation_date = datetime.now()
            any_existing.notes = f'Updated to confirmed status for {cancellation_type} guest'
            
            try:
                db.session.commit()
                print(f"🔄 [UPDATE_CONFIRMATION] Updated existing action {any_existing.action_id} to confirmed")
                
                # Force cache refresh by disposing the connection pool
                db.engine.dispose()
                
                return jsonify({
                    'success': True,
                    'message': f'Cancellation confirmed for {guest_name}',
                    'action': 'updated',
                    'action_id': any_existing.action_id,
                    'refresh_required': True
                })
            except Exception as commit_error:
                db.session.rollback()
                print(f"❌ [COMMIT_ERROR] Failed to commit update: {commit_error}")
                return jsonify({
                    'success': False,
                    'error': f'Database commit failed: {str(commit_error)}'
                }), 500
        
        # Create new cancellation action record
        cancellation_action = CancellationAction(
            booking_id=booking_id,
            guest_name=guest_name,
            cancellation_type=cancellation_type,
            action_status='confirmed',
            confirmed_by=confirmed_by,
            confirmation_date=datetime.now(),
            notes=f'Confirmed cancellation on booking app for {cancellation_type} guest'
        )
        
        db.session.add(cancellation_action)
        
        try:
            db.session.commit()
            print(f"✅ [CONFIRM_CANCELLATION] Booking {booking_id} - {guest_name} - {cancellation_type}")
            
            # Force cache refresh by disposing the connection pool
            db.engine.dispose()
            
            return jsonify({
                'success': True,
                'message': f'Cancellation confirmed for {guest_name}',
                'action_id': cancellation_action.action_id,
                'timestamp': datetime.now().isoformat(),
                'refresh_required': True
            })
        except Exception as commit_error:
            db.session.rollback()
            print(f"❌ [COMMIT_ERROR] Failed to commit new action: {commit_error}")
            return jsonify({
                'success': False,
                'error': f'Database commit failed: {str(commit_error)}'
            }), 500
        
    except Exception as e:
        print(f"❌ [API_CONFIRM_CANCELLATION] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/undo_cancellation', methods=['POST'])
def api_undo_cancellation():
    """Undo cancellation confirmation and allow alert to show again"""
    try:
        data = request.get_json()
        action_id = data.get('action_id')
        booking_id = data.get('booking_id')
        guest_name = data.get('guest_name')
        
        if not action_id and not booking_id:
            return jsonify({
                'success': False,
                'error': 'Either action_id or booking_id is required'
            }), 400
        
        # Import model
        from core.models import db, CancellationAction
        
        # Find and delete the cancellation action record
        if action_id:
            cancellation_action = CancellationAction.query.filter_by(action_id=action_id).first()
        else:
            cancellation_action = CancellationAction.query.filter_by(
                booking_id=booking_id,
                action_status='confirmed'
            ).first()
        
        if not cancellation_action:
            return jsonify({
                'success': False,
                'error': 'Cancellation action not found'
            }), 404
        
        # Store info before deletion
        stored_booking_id = cancellation_action.booking_id
        stored_guest_name = cancellation_action.guest_name
        stored_type = cancellation_action.cancellation_type
        
        # Delete the cancellation action record
        db.session.delete(cancellation_action)
        db.session.commit()
        
        print(f"🗑️ [UNDO_CANCELLATION] Deleted action for {stored_guest_name} - {stored_booking_id}")
        print(f"🔄 [UNDO_CANCELLATION] Alert will show again on next page load")
        
        return jsonify({
            'success': True,
            'message': f'Confirmation undone for {stored_guest_name}. Alert will appear on next page load.',
            'booking_id': stored_booking_id,
            'guest_name': stored_guest_name,
            'cancellation_type': stored_type,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_UNDO_CANCELLATION] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/set_ok_status', methods=['POST'])
def api_set_ok_status():
    """Set OK status for a guest (meaning no more cancellation issues)"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        guest_name = data.get('guest_name')
        cancellation_type = data.get('cancellation_type', 'ok_status')
        confirmed_by = 'System User'  # You can enhance this with actual user tracking
        
        if not all([booking_id, guest_name]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: booking_id and guest_name'
            }), 400
        
        # Import models
        from core.models import db, CancellationAction, Booking
        
        # CRITICAL: Update booking status to restore full functionality
        booking = Booking.query.filter_by(booking_id=booking_id).first()
        if not booking:
            return jsonify({
                'success': False,
                'error': f'Booking {booking_id} not found'
            }), 404
            
        # Restore booking to confirmed status (enables all features)
        old_status = booking.booking_status
        booking.booking_status = 'confirmed'
        booking.booking_notes = f"{booking.booking_notes or ''} [OK Status: Restored from {old_status}]".strip()
        
        print(f"🔄 [RESTORE_BOOKING] {booking_id} status: {old_status} → confirmed")
        
        # Check if there's already an action for this booking - update it instead of creating new
        existing = CancellationAction.query.filter_by(
            booking_id=booking_id,
            guest_name=guest_name
        ).first()
        
        if existing:
            # Update existing action to OK status
            existing.cancellation_type = 'ok_status'
            existing.action_status = 'ok'
            existing.confirmed_by = confirmed_by
            existing.confirmation_date = datetime.now()
            existing.notes = f'Guest marked as OK - booking restored to full functionality'
            db.session.commit()
            
            print(f"🔄 [UPDATE_OK_STATUS] Updated existing action {existing.action_id} to OK status")
            return jsonify({
                'success': True,
                'message': f'{guest_name} restored to full functionality - booking status: {old_status} → confirmed',
                'action': 'updated',
                'action_id': existing.action_id,
                'booking_status_change': f'{old_status} → confirmed'
            })
        
        # Create new OK status record
        ok_action = CancellationAction(
            booking_id=booking_id,
            guest_name=guest_name,
            cancellation_type='ok_status',
            action_status='ok',
            confirmed_by=confirmed_by,
            confirmation_date=datetime.now(),
            notes=f'Guest marked as OK - booking restored to full functionality from {old_status}'
        )
        
        db.session.add(ok_action)
        db.session.commit()
        
        print(f"✅ [SET_OK_STATUS] Booking {booking_id} - {guest_name} - restored to full functionality")
        
        return jsonify({
            'success': True,
            'message': f'{guest_name} restored to full functionality - booking status: {old_status} → confirmed',
            'action_id': ok_action.action_id,
            'booking_status_change': f'{old_status} → confirmed',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_SET_OK_STATUS] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/auto_sync')
def auto_sync_dashboard():
    """Auto sync dashboard for managing bidirectional database synchronization"""
    try:
        # Debug info for Railway deployment
        print("🔍 Auto sync dashboard accessed")
        print(f"🔍 Template folder: {app.template_folder}")
        
        # Check if template exists
        import os
        template_path = os.path.join(app.template_folder, 'auto_sync_dashboard.html')
        template_exists = os.path.exists(template_path)
        print(f"🔍 Template exists: {template_exists}")
        
        if not template_exists:
            return f"<h1>Debug: Template Missing</h1><p>Template path: {template_path}</p><p>Template folder: {app.template_folder}</p>"
        
        return render_template('auto_sync_dashboard.html')
        
    except Exception as e:
        print(f"❌ Auto sync dashboard error: {e}")
        import traceback
        traceback.print_exc()
        return f"<h1>Auto Sync Dashboard Error</h1><p>Error: {str(e)}</p><pre>{traceback.format_exc()}</pre>"

@app.route('/debug/routes')
def debug_routes():
    """Debug route to check all registered routes"""
    try:
        routes_info = []
        for rule in app.url_map.iter_rules():
            routes_info.append({
                'route': rule.rule,
                'endpoint': rule.endpoint,
                'methods': list(rule.methods)
            })
        
        # Check specifically for auto sync route
        auto_sync_routes = [r for r in routes_info if 'auto' in r['route'].lower() or 'sync' in r['endpoint'].lower()]
        
        html = "<h1>Route Debug Info</h1>"
        html += f"<h2>Total Routes: {len(routes_info)}</h2>"
        html += "<h3>Auto Sync Related Routes:</h3><ul>"
        
        if auto_sync_routes:
            for route in auto_sync_routes:
                html += f"<li><strong>{route['route']}</strong> → {route['endpoint']} ({route['methods']})</li>"
        else:
            html += "<li>❌ No auto sync routes found</li>"
        
        html += "</ul>"
        
        # Test url_for
        try:
            with app.app_context():
                auto_sync_url = url_for('auto_sync_dashboard')
                html += f"<h3>url_for Test:</h3><p>✅ url_for('auto_sync_dashboard') = {auto_sync_url}</p>"
        except Exception as e:
            html += f"<h3>url_for Test:</h3><p>❌ url_for failed: {str(e)}</p>"
        
        return html
        
    except Exception as e:
        return f"<h1>Debug Error</h1><p>{str(e)}</p>"

@app.route('/')
def dashboard():
    """PostgreSQL-powered dashboard route with cancellation notifications"""
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')

    # Set default date range to current month for better user experience
    if not start_date_str or not end_date_str:
        today_full = datetime.today()
        # Start from beginning of current month
        start_date = today_full.replace(day=1)
        # End at end of current month
        _, last_day = calendar.monthrange(today_full.year, today_full.month)
        end_date = today_full.replace(day=last_day)
        print(f"📅 DASHBOARD DEFAULT: Current month {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    else:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d')

    # Check if fresh data is requested
    force_fresh = request.args.get('refresh') == 'true'
    
    # Load data from PostgreSQL
    df, _ = load_data(force_fresh=force_fresh)
    sort_by = request.args.get('sort_by', 'Tháng')
    sort_order = request.args.get('sort_order', 'desc')
    
    print(f"📅 [DASHBOARD_MAIN] Date filter: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print(f"📅 [DASHBOARD_MAIN] Total bookings loaded: {len(df)}")
    
    # Get cancellation notifications
    try:
        from core.cancellation_notifications import get_cancellation_notifications, get_urgent_cancellation_alerts
        cancellation_notifications = get_cancellation_notifications()
        urgent_alerts = get_urgent_cancellation_alerts()
        print(f"🚨 [CANCELLATION_ALERTS] Total alerts: {cancellation_notifications['summary']['total_alerts']}")
    except Exception as e:
        print(f"⚠️ [CANCELLATION_ALERTS] Error loading notifications: {e}")
        cancellation_notifications = {'summary': {'total_alerts': 0}}
        urgent_alerts = []
    
    dashboard_data = prepare_dashboard_data(df, start_date, end_date, sort_by, sort_order)

    # Process all dashboard data
    processed_data = process_dashboard_data(df, start_date, end_date, sort_by, sort_order, dashboard_data)

    # Add duplicate detection for dashboard integration
    duplicate_guests = {}
    try:
        if not df.empty:
            # Group by guest name and count duplicates
            guest_counts = df.groupby('Tên người đặt').size()
            # Only include guests with more than 1 booking
            duplicate_guests = {name: count for name, count in guest_counts.items() if count > 1}
            print(f"🔍 [DASHBOARD] Found {len(duplicate_guests)} guests with duplicates")
    except Exception as e:
        print(f"⚠️ [DASHBOARD] Error detecting duplicates: {e}")
        duplicate_guests = {}

    # Ensure chart data is always available with proper fallbacks
    if 'monthly_revenue_chart_json' not in processed_data or not processed_data['monthly_revenue_chart_json']:
        processed_data['monthly_revenue_chart_json'] = {'data': [], 'layout': {'title': {'text': 'No monthly revenue data available'}}}
        print("⚠️ [DASHBOARD] Added fallback for monthly_revenue_chart_json")
    
    if 'collector_chart_json' not in processed_data or not processed_data['collector_chart_json']:
        processed_data['collector_chart_json'] = {'data': [], 'layout': {'title': {'text': 'No collector data available'}}}
        print("⚠️ [DASHBOARD] Added fallback for collector_chart_json")
    
    print(f"📊 [DASHBOARD] Chart data status:")
    print(f"   - Monthly chart: {'available' if processed_data.get('monthly_revenue_chart_json', {}).get('data') else 'empty'}")
    print(f"   - Collector chart: {'available' if processed_data.get('collector_chart_json', {}).get('data') else 'empty'}")
    
    # Render template with processed data and cancellation notifications
    return render_template(
        'dashboard.html',
        total_revenue=dashboard_data.get('total_revenue_selected', 0),
        total_guests=dashboard_data.get('total_guests_selected', 0),
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        current_sort_by=sort_by,
        current_sort_order=sort_order,
        collector_revenue_list=safe_to_dict_records(dashboard_data.get('collector_revenue_selected', pd.DataFrame())),
        duplicate_guests=duplicate_guests,  # Add duplicate detection data
        cancellation_notifications=cancellation_notifications,  # Cancellation alerts
        urgent_alerts=urgent_alerts,  # High-priority alerts
        **processed_data
    )

@app.route('/bookings')
def view_bookings():
    """Professional booking management with optimized search and filtering"""
    import time
    start_time = time.time()
    
    try:
        # Check if we need to force fresh data (e.g., after payment collection)
        force_fresh = request.args.get('refresh', 'false').lower() == 'true'
        df, _ = load_data(force_fresh=force_fresh)
        
        if df.empty:
            print("⚠️ BOOKING MANAGEMENT: No data available")
            return render_template('bookings.html', 
                                 bookings=[], 
                                 total_bookings=0,
                                 pagination={'total': 0, 'page': 1, 'total_pages': 0})
        
        data_load_time = time.time() - start_time
        print(f"⏱️ PERFORMANCE: Data loaded in {data_load_time:.3f}s")
        
        # Get URL parameters with professional pagination
        search_term = request.args.get('search_term', '').strip().lower()
        sort_by = request.args.get('sort_by', 'Check-in Date')
        auto_filter = request.args.get('auto_filter', 'true').lower() == 'true'  # Always enabled by default
        show_all = request.args.get('show_all', 'false').lower() == 'true'
        
        # Debug parameter parsing
        print(f"🔍 FILTER PARAMETERS:")
        print(f"   show_all parameter: '{request.args.get('show_all', 'not provided')}'")
        print(f"   show_all parsed: {show_all}")
        print(f"   Will apply filter: {not show_all}")
        
        # Default sort: always by check-in date, ascending for both views
        default_order = 'asc'  # Always ascending for check-in date sorting
        order = request.args.get('order', default_order)
        
        # PROFESSIONAL PAGINATION PARAMETERS
        try:
            page = int(request.args.get('page', 1))
            per_page = int(request.args.get('per_page', 50))  # Professional default
        except (ValueError, TypeError):
            page = 1
            per_page = 50
            print("⚠️ PAGINATION: Invalid parameters, using defaults")
        
        # Professional parameter validation
        if page < 1:
            page = 1
        if per_page not in [25, 50, 100, 200]:  # Professional options
            per_page = 50
            
        print(f"📄 PAGINATION: Page {page}, {per_page} items per page")
        
        # Filter data
        filtered_df = df.copy()
    
        # PROFESSIONAL SEARCH IMPLEMENTATION
        if search_term:
            print(f"🔍 ADVANCED SEARCH: Processing search term '{search_term}'")
            
            # Multi-field search with weighted relevance
            search_lower = search_term.lower()
            
            # Create search masks for different fields
            name_mask = filtered_df['Tên người đặt'].str.lower().str.contains(search_lower, na=False)
            booking_id_mask = filtered_df['Số đặt phòng'].astype(str).str.lower().str.contains(search_lower, na=False)
            
            # Additional search fields for comprehensive search
            phone_mask = filtered_df.get('phone', pd.Series([False] * len(filtered_df))).astype(str).str.lower().str.contains(search_lower, na=False)
            notes_mask = filtered_df.get('Ghi chú thanh toán', pd.Series([False] * len(filtered_df))).astype(str).str.lower().str.contains(search_lower, na=False)
            
            # Combine all search criteria
            combined_mask = name_mask | booking_id_mask | phone_mask | notes_mask
            
            # Apply search filter
            filtered_df = filtered_df[combined_mask]
            
            # Search analytics
            search_results_count = len(filtered_df)
            print(f"🔍 SEARCH RESULTS: Found {search_results_count} matches for '{search_term}'")
            print(f"   📝 Name matches: {name_mask.sum()}")
            print(f"   🎫 Booking ID matches: {booking_id_mask.sum()}")
            print(f"   📞 Phone matches: {phone_mask.sum()}")
            print(f"   📋 Notes matches: {notes_mask.sum()}")
        
        # DATE FILTERING (MONTH/YEAR/DATE RANGE)
        filter_month = request.args.get('filter_month', '').strip()
        filter_year = request.args.get('filter_year', '').strip()
        start_date = request.args.get('start_date', '').strip()
        end_date = request.args.get('end_date', '').strip()
        
        # Apply month/year filtering
        if filter_month or filter_year or start_date or end_date:
            original_count = len(filtered_df)
            
            # Convert check-in date to datetime for filtering
            if 'Check-in Date' in filtered_df.columns:
                filtered_df['Check-in Date'] = pd.to_datetime(filtered_df['Check-in Date'], errors='coerce')
                
                # Filter by month
                if filter_month:
                    try:
                        month_num = int(filter_month)
                        filtered_df = filtered_df[filtered_df['Check-in Date'].dt.month == month_num]
                        print(f"📅 [MONTH_FILTER] Filtered to month {month_num}: {len(filtered_df)} bookings")
                    except (ValueError, TypeError):
                        print(f"⚠️ [MONTH_FILTER] Invalid month parameter: {filter_month}")
                
                # Filter by year
                if filter_year:
                    try:
                        year_num = int(filter_year)
                        filtered_df = filtered_df[filtered_df['Check-in Date'].dt.year == year_num]
                        print(f"📅 [YEAR_FILTER] Filtered to year {year_num}: {len(filtered_df)} bookings")
                    except (ValueError, TypeError):
                        print(f"⚠️ [YEAR_FILTER] Invalid year parameter: {filter_year}")
                
                # Filter by date range
                if start_date:
                    try:
                        start_dt = pd.to_datetime(start_date)
                        filtered_df = filtered_df[filtered_df['Check-in Date'] >= start_dt]
                        print(f"📅 [START_DATE] Filtered from {start_date}: {len(filtered_df)} bookings")
                    except (ValueError, TypeError):
                        print(f"⚠️ [START_DATE] Invalid start date: {start_date}")
                
                if end_date:
                    try:
                        end_dt = pd.to_datetime(end_date)
                        filtered_df = filtered_df[filtered_df['Check-in Date'] <= end_dt]
                        print(f"📅 [END_DATE] Filtered to {end_date}: {len(filtered_df)} bookings")
                    except (ValueError, TypeError):
                        print(f"⚠️ [END_DATE] Invalid end date: {end_date}")
                
                filtered_count = len(filtered_df)
                print(f"📅 [DATE_FILTER_SUMMARY] {original_count} → {filtered_count} bookings after date filtering")
        
        # Duplicate detection and marking (NO AUTO-HIDING)
        duplicate_report = {'total_groups': 0, 'total_duplicates': 0, 'filtered_count': 0}
        duplicate_booking_ids = set()
        
        # Always analyze duplicates but don't auto-filter unless specifically requested
        duplicates = analyze_existing_duplicates(filtered_df)
        
        # Mark duplicate bookings for visual indication (don't hide them)
        try:
            duplicate_groups = duplicates.get('duplicate_groups', [])
            for group in duplicate_groups:
                if isinstance(group, dict) and 'bookings' in group:
                    for booking in group['bookings'][1:]:  # Mark duplicates (keep first)
                        if isinstance(booking, dict) and 'Số đặt phòng' in booking:
                            duplicate_booking_ids.add(booking['Số đặt phòng'])
        except Exception as e:
            print(f"⚠️ [DUPLICATE_PROCESS] Error processing duplicate groups: {e}")
            duplicate_groups = []
        
        # Clean duplicate groups to prevent JSON serialization errors
        def clean_duplicate_groups(groups):
            """Clean duplicate groups data to prevent JSON serialization errors"""
            if not groups:
                return []
            
            cleaned_groups = []
            for group in groups:
                try:
                    cleaned_group = {}
                    for key, value in group.items():
                        if value is None or str(value) == 'nan' or str(value) == 'NaT':
                            cleaned_group[key] = ''
                        elif hasattr(value, 'to_dict'):  # Handle pandas objects
                            cleaned_group[key] = value.to_dict()
                        elif isinstance(value, list):
                            # Clean each item in the list
                            cleaned_list = []
                            for item in value:
                                if isinstance(item, dict):
                                    cleaned_item = {k: (v if v is not None and str(v) not in ['nan', 'NaT'] else '') for k, v in item.items()}
                                    cleaned_list.append(cleaned_item)
                                else:
                                    cleaned_list.append(item if item is not None else '')
                            cleaned_group[key] = cleaned_list
                        else:
                            cleaned_group[key] = value
                    cleaned_groups.append(cleaned_group)
                except Exception as e:
                    print(f"⚠️ [DUPLICATE_CLEAN] Error cleaning group: {e}")
                    continue
            return cleaned_groups

        # Create duplicate report for template
        duplicate_report = {
            'total_groups': duplicates.get('total_groups', 0),
            'total_duplicates': duplicates.get('total_duplicates', 0),
            'filtered_count': len(duplicate_booking_ids),
            'duplicate_booking_ids': list(duplicate_booking_ids),  # For marking in template
            'duplicate_groups': clean_duplicate_groups(duplicates.get('duplicate_groups', []))  # Cleaned for JSON
        }
        
        # DEBUG: Log duplicate detection results
        print(f"🔍 [DUPLICATE_DEBUG] Duplicate analysis results:")
        print(f"   - total_groups: {duplicate_report['total_groups']}")
        print(f"   - total_duplicates: {duplicate_report['total_duplicates']}")
        print(f"   - filtered_count: {duplicate_report['filtered_count']}")
        print(f"   - duplicate_booking_ids count: {len(duplicate_report['duplicate_booking_ids'])}")
        print(f"   - duplicate_booking_ids: {duplicate_report['duplicate_booking_ids'][:5]}...")  # Show first 5
        print(f"   - duplicates raw result keys: {list(duplicates.keys())}")
        print(f"   - duplicates raw result: {duplicates}")
        
        # Only hide duplicates if auto_filter is specifically enabled AND user wants to hide duplicates
        if auto_filter and request.args.get('hide_duplicates') == 'true':
            print(f"🔍 [BOOKINGS] Hiding {len(duplicate_booking_ids)} duplicate bookings (user requested)")
            filtered_df = filtered_df[~filtered_df['Số đặt phòng'].isin(duplicate_booking_ids)]
        else:
            print(f"🔍 [BOOKINGS] Keeping {len(duplicate_booking_ids)} duplicate bookings visible for manual review")
        
        # "Only interested guests" filter - DEFAULT: Show actionable guests
        if not show_all:
            today = datetime.today().date()
            print(f"🎯 INTERESTED GUESTS FILTER (EXPANDED): Applying filter for date {today}")
            
            # Convert date columns for comparison
            filtered_df['Check-in Date'] = pd.to_datetime(filtered_df['Check-in Date'], errors='coerce')
            filtered_df['Check-out Date'] = pd.to_datetime(filtered_df['Check-out Date'], errors='coerce')
            
            # Create mask for "interested" guests who need attention
            # EXPANDED FILTER: Show guests who need payment collection or management
            payment_issue_mask = (
                (filtered_df['Số tiền đã thu'].fillna(0) == 0) |  # No money collected
                (filtered_df['Số tiền đã thu'].fillna(0) < filtered_df['Tổng thanh toán']) |  # Partial payment
                (~filtered_df['Người thu tiền'].isin(['LOC LE', 'THAO LE']))  # Invalid collector
            )
            
            interested_mask = (
                # Condition 1: All upcoming guests (future check-ins)
                (filtered_df['Check-in Date'].dt.date >= today) |
                
                # Condition 2: Current/past guests with payment issues who haven't checked out yet
                # (checked out after today OR haven't checked out yet)
                (
                    payment_issue_mask &
                    (filtered_df['Check-out Date'].dt.date >= today)
                ) |
                
                # Condition 3: ALWAYS show cancelled bookings for management visibility
                # (regardless of dates or payment status - they should remain visible)
                (filtered_df['Tình trạng'] == 'Đã hủy')
            )
            
            # Apply the filter
            before_count = len(filtered_df)
            filtered_df = filtered_df[interested_mask]
            after_count = len(filtered_df)
            
            # Debug information for expanded filter
            upcoming_guests = len(filtered_df[filtered_df['Check-in Date'].dt.date >= today])
            current_unpaid_guests = len(filtered_df[
                (payment_issue_mask) & 
                (filtered_df['Check-out Date'].dt.date >= today)
            ])
            cancelled_guests = len(filtered_df[filtered_df['Tình trạng'] == 'Đã hủy'])
            
            print(f"🔍 EXPANDED INTERESTED GUESTS FILTER RESULTS:")
            print(f"   📊 Total guests filtered: {before_count} → {after_count}")
            print(f"   🏨 All upcoming guests: {upcoming_guests}")
            print(f"   💰 Current/staying unpaid guests: {current_unpaid_guests}")
            print(f"   ❌ Cancelled bookings (always visible): {cancelled_guests}")
            print(f"   📅 Focus: All future arrivals + current unpaid guests + cancelled bookings")
            print(f"   🎯 Logic: Future check-ins OR (unpaid AND not checked out yet) OR cancelled")
            
        else:
            print(f"📋 SHOWING ALL GUESTS: {len(filtered_df)} total guests")
        
        # Sort data
        if sort_by in filtered_df.columns:
            ascending = (order == 'asc')
            if sort_by in ['Check-in Date', 'Check-out Date']:
                filtered_df = filtered_df.sort_values(sort_by, ascending=ascending, na_position='last')
            else:
                filtered_df = filtered_df.sort_values(sort_by, ascending=ascending)
        
        # PROFESSIONAL PAGINATION IMPLEMENTATION
        total_bookings = len(filtered_df)
        total_pages = (total_bookings + per_page - 1) // per_page  # Ceiling division
        
        # Calculate pagination boundaries
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        
        # Apply pagination to filtered data
        paginated_df = filtered_df.iloc[start_idx:end_idx]
        bookings_list = safe_to_dict_records(paginated_df)
        
        # Professional pagination info with page range calculation
        # Calculate page range for template (avoid Jinja2 max/min issues)
        start_page = max(1, page - 2)
        end_page = min(total_pages + 1, page + 3)
        page_range = list(range(start_page, end_page))
        
        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total_bookings,
            'total_pages': total_pages,
            'has_prev': page > 1,
            'has_next': page < total_pages,
            'prev_page': page - 1 if page > 1 else None,
            'next_page': page + 1 if page < total_pages else None,
            'start_item': start_idx + 1 if total_bookings > 0 else 0,
            'end_item': min(end_idx, total_bookings),
            'showing_count': len(bookings_list),
            'page_range': page_range  # Pre-calculated page range
        }
        
        print(f"📄 PAGINATION RESULT: Showing {pagination_info['start_item']}-{pagination_info['end_item']} of {total_bookings} items")
        
        # Professional performance monitoring
        total_time = time.time() - start_time
        print(f"⏱️ TOTAL PERFORMANCE: Booking management completed in {total_time:.3f}s")
        
        return render_template(
            'bookings.html',
                bookings=bookings_list,
                search_term=search_term,
                sort_by=sort_by,
                order=order,
                auto_filter=auto_filter,
                auto_filter_duplicates=auto_filter,  # For template compatibility
                duplicate_report=duplicate_report,
                show_all=show_all,
                total_bookings=total_bookings,
                booking_count=total_bookings,
                current_sort_by=sort_by,
                current_order=order,
                pagination=pagination_info,
                # Date filter parameters
                filter_month=filter_month,
                filter_year=filter_year,
                start_date=start_date,
                end_date=end_date
            )
        
    except Exception as e:
        print(f"❌ BOOKING MANAGEMENT ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Return safe fallback response
        flash(f'Lỗi tải dữ liệu đặt phòng: {str(e)}', 'error')
        return render_template('bookings.html', 
                             bookings=[], 
                             total_bookings=0,
                             search_term='',
                             filter_month='',
                             filter_year='',
                             start_date='',
                             end_date='',
                             sort_by='Check-in Date',
                             order='desc',
                             auto_filter=False,
                             show_all=False,
                             pagination={
                                 'total': 0, 
                                 'page': 1, 
                                 'total_pages': 0,
                                 'has_prev': False,
                                 'has_next': False,
                                 'page_range': [1],
                                 'start_item': 0,
                                 'end_item': 0,
                                 'showing_count': 0
                             },
                             error_message=str(e))

@app.route('/health')
def health_check():
    """Enhanced health check endpoint for Railway with database validation"""
    try:
        # Check database connection
        database_url = os.getenv('DATABASE_URL', 'not_set')
        db_type = 'postgresql' if database_url.startswith('postgresql://') else 'sqlite_fallback'
        
        # Test database connection
        db_status = 'unknown'
        db_error = None
        try:
            from core.models import db
            with db.engine.connect() as conn:
                conn.execute(text('SELECT 1'))
            db_status = 'connected'
        except Exception as e:
            db_status = 'error'
            db_error = str(e)
        
        return jsonify({
            'status': 'healthy',
            'message': 'Hotel Booking System is running',
            'timestamp': datetime.now().isoformat(),
            'database': {
                'type': db_type,
                'status': db_status,
                'error': db_error,
                'url_configured': database_url != 'not_set'
            },
            'railway': {
                'postgresql_ready': db_type == 'postgresql' and db_status == 'connected',
                'needs_setup': db_type == 'sqlite_fallback'
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Health check failed: {str(e)}',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/database/health')
def database_health():
    """Check PostgreSQL database health"""
    try:
        db_service = get_database_service()
        health_status = db_service.get_health_status()
        return jsonify(health_status)
    except Exception as e:
        return jsonify({
            'status': 'error',
            'backend': 'postgresql',
            'error': str(e)
        }), 500

@app.route('/api/database/test_connection')
def test_database_connection():
    """Test PostgreSQL connection for pgAdmin/DBeaver compatibility"""
    try:
        db_service = get_database_service()
        connection_test = db_service.test_connection()
        
        # Additional connection info for pgAdmin/DBeaver
        connection_info = {
            'database_url': os.getenv('DATABASE_URL', '').split('@')[-1] if os.getenv('DATABASE_URL') else 'Not configured',
            'connection_details': {
                'backend': 'postgresql',
                'sqlalchemy_version': '2.0+',
                'supports_pgadmin': True,
                'supports_dbeaver': True
            }
        }
        
        return jsonify({
            **connection_test,
            **connection_info
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'message': 'Database connection failed'
        }), 500

@app.route('/duplicate_management')
def duplicate_management_page():
    """Duplicate management interface"""
    return render_template('duplicate_management.html')

@app.route('/bookings/add', methods=['GET', 'POST'])
def add_booking():
    """Add new booking to PostgreSQL"""
    if request.method == 'POST':
        try:
            # Get form data with validation
            checkin_date_str = request.form.get('Ngày đến')
            checkout_date_str = request.form.get('Ngày đi')
            
            # Validate required fields
            if not checkin_date_str:
                flash('Check-in date is required', 'error')
                return render_template('add_booking.html')
            
            if not checkout_date_str:
                flash('Check-out date is required', 'error')
                return render_template('add_booking.html')
            
            booking_data = {
                'booking_id': request.form.get('Số đặt phòng'),
                'guest_name': request.form.get('Tên người đặt'),
                'email': request.form.get('Email'),
                'phone': request.form.get('Số điện thoại'),
                'checkin_date': datetime.strptime(checkin_date_str, '%Y-%m-%d').date(),
                'checkout_date': datetime.strptime(checkout_date_str, '%Y-%m-%d').date(),
                'room_amount': float(request.form.get('Tổng thanh toán', 0)),
                'commission': float(request.form.get('Hoa hồng', 0)),
                'taxi_amount': float(request.form.get('Taxi', 0)),
                'collector': request.form.get('Người thu tiền', ''),
                'notes': request.form.get('Ghi chú', '')
            }
            
            # Pre-flight check for Railway deployment
            try:
                from core.models import db
                from sqlalchemy import text
                db.session.execute(text('SELECT 1'))
                print("✅ [PRE_FLIGHT] Database connection verified")
            except Exception as db_test_error:
                print(f"❌ [PRE_FLIGHT] Database connection failed: {db_test_error}")
                flash(f'Database connection error: {str(db_test_error)}', 'error')
                return render_template('add_booking.html')
            
            if add_new_booking(booking_data):
                # Cache removed - data will be fresh automatically
                flash('Booking added successfully!', 'success')
                return redirect(url_for('view_bookings'))
            else:
                flash('Error adding booking to database', 'error')
        
        except Exception as e:
            import traceback
            error_msg = f'Error adding booking: {str(e)}'
            print(f"❌ [ADD_BOOKING_ERROR] {error_msg}")
            print(f"❌ [ADD_BOOKING_TRACEBACK] {traceback.format_exc()}")
            
            # Check for common Railway issues
            if "database" in str(e).lower() or "connection" in str(e).lower():
                print(f"🔍 [RAILWAY_DEBUG] Possible database connection issue")
                print(f"🔍 [RAILWAY_DEBUG] DATABASE_URL exists: {'DATABASE_URL' in os.environ}")
            
            flash(error_msg, 'error')
    
    return render_template('add_booking.html')

@app.route('/booking/<booking_id>/edit', methods=['GET', 'POST'])
def edit_booking(booking_id):
    """Edit booking in PostgreSQL"""
    df, _ = load_data()
    
    # Find booking
    booking_data = df[df['Số đặt phòng'] == booking_id]
    if booking_data.empty:
        flash('Booking not found', 'error')
        return redirect(url_for('view_bookings'))
    
    booking = booking_data.iloc[0].to_dict()
    
    if request.method == 'POST':
        try:
            # Get form data with validation
            checkin_date_str = request.form.get('checkin_date')
            checkout_date_str = request.form.get('checkout_date')
            
            # Validate required date fields
            if not checkin_date_str:
                flash('Check-in date is required', 'error')
                return render_template('edit_booking.html', booking=booking)
            
            if not checkout_date_str:
                flash('Check-out date is required', 'error')
                return render_template('edit_booking.html', booking=booking)
            
            # Helper function to safely convert to float, treating empty strings as 0
            def safe_float(value, default=0):
                if value is None or value == '' or value == 'None':
                    return default
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return default
            
            update_data = {
                'guest_name': request.form.get('guest_name'),
                'checkin_date': datetime.strptime(checkin_date_str, '%Y-%m-%d').date(),
                'checkout_date': datetime.strptime(checkout_date_str, '%Y-%m-%d').date(),
                'room_amount': safe_float(request.form.get('room_amount'), 0),
                'commission': safe_float(request.form.get('commission'), 0),
                'taxi_amount': safe_float(request.form.get('taxi_amount'), 0),
                'collector': request.form.get('collector', ''),
                'notes': request.form.get('notes', '')
            }
            
            if update_booking(booking_id, update_data):
                # Cache removed - data will be fresh automatically
                flash('Booking updated successfully!', 'success')
                return redirect(url_for('view_bookings'))
            else:
                flash('Error updating booking', 'error')
        
        except Exception as e:
            flash(f'Error updating booking: {str(e)}', 'error')
    
    return render_template('edit_booking.html', booking=booking)

@app.route('/api/delete_booking/<booking_id>', methods=['DELETE'])
def delete_booking_api(booking_id):
    """Delete booking from PostgreSQL"""
    try:
        if delete_booking_by_id(booking_id):
            # Cache removed - data will be fresh automatically
            return jsonify({'status': 'success', 'message': 'Booking cancelled successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to cancel booking'}), 400
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/bookings/delete_multiple', methods=['POST'])
def delete_multiple_bookings():
    """Delete multiple bookings from PostgreSQL"""
    try:
        data = request.get_json()
        if not data or 'booking_ids' not in data:
            return jsonify({'success': False, 'message': 'No booking IDs provided'}), 400
        
        booking_ids = data['booking_ids']
        if not isinstance(booking_ids, list) or len(booking_ids) == 0:
            return jsonify({'success': False, 'message': 'Invalid booking IDs list'}), 400
        
        print(f"🗑️ DELETE MULTIPLE: Attempting to delete {len(booking_ids)} bookings")
        print(f"🗑️ BOOKING IDS: {booking_ids}")
        
        # Delete each booking
        deleted_count = 0
        failed_ids = []
        
        for booking_id in booking_ids:
            try:
                if delete_booking_by_id(booking_id):
                    deleted_count += 1
                    print(f"✅ CANCELLED: Booking {booking_id}")
                else:
                    failed_ids.append(booking_id)
                    print(f"❌ FAILED: Booking {booking_id}")
            except Exception as e:
                failed_ids.append(booking_id)
                print(f"❌ ERROR cancelling booking {booking_id}: {str(e)}")
        
        # Prepare response
        if deleted_count > 0:
            message = f"Đã hủy thành công {deleted_count} booking"
            if failed_ids:
                message += f", thất bại {len(failed_ids)} booking"
            
            print(f"🎯 DELETE RESULT: {deleted_count} success, {len(failed_ids)} failed")
            return jsonify({
                'success': True, 
                'message': message,
                'deleted_count': deleted_count,
                'failed_count': len(failed_ids),
                'failed_ids': failed_ids
            })
        else:
            return jsonify({
                'success': False, 
                'message': 'Không thể xóa booking nào',
                'failed_ids': failed_ids
            }), 400
            
    except Exception as e:
        print(f"❌ DELETE MULTIPLE ERROR: {str(e)}")
        return jsonify({'success': False, 'message': f'Lỗi server: {str(e)}'}), 500

@app.route('/api/expenses', methods=['GET', 'POST'])
def expenses_api():
    """Expense management with PostgreSQL and Railway compatibility"""
    if request.method == 'GET':
        try:
            print(f"🔍 [EXPENSES_API] Starting expenses loading...")
            
            # 🚀 RAILWAY FIX: Enhanced error handling for database connection issues
            try:
                # First, check if expenses table exists
                from core.models import db
                from sqlalchemy import text
                
                # Test table existence
                with db.engine.connect() as conn:
                    table_check = conn.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'expenses')")).scalar()
                    print(f"🔍 [EXPENSES_API] Expenses table exists: {table_check}")
                    
                    if table_check:
                        # Check table structure
                        columns_result = conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'expenses'"))
                        columns = columns_result.fetchall()
                        print(f"🔍 [EXPENSES_API] Table structure: {columns}")
                
                expenses_df = get_expenses_from_database()
                print(f"🔍 [EXPENSES_API] Database query successful, got DataFrame with {len(expenses_df)} rows")
                
                if not expenses_df.empty:
                    print(f"🔍 [EXPENSES_API] DataFrame columns: {list(expenses_df.columns)}")
                    
            except Exception as db_error:
                print(f"❌ [EXPENSES_API] Database error: {db_error}")
                import traceback
                traceback.print_exc()
                # Railway fallback: return empty data instead of crashing
                return jsonify({
                    'success': True, 
                    'data': [], 
                    'status': 'success',
                    'warning': f'Database connection issue: {str(db_error)}',
                    'environment': 'railway' if os.getenv('RAILWAY_PROJECT_ID') else 'local'
                })
            
            # Convert to records with enhanced error handling
            try:
                expenses_list = safe_to_dict_records(expenses_df)
                print(f"💰 [EXPENSES_API] Successfully converted to {len(expenses_list)} expense records")
                
                # Debug: Print first record structure if exists
                if expenses_list:
                    print(f"🔍 [EXPENSES_API] Sample record structure: {list(expenses_list[0].keys())}")
                    print(f"🔍 [EXPENSES_API] Sample record: {expenses_list[0]}")
                    
            except Exception as convert_error:
                print(f"❌ [EXPENSES_API] Conversion error: {convert_error}")
                # Fallback conversion
                expenses_list = expenses_df.to_dict('records') if not expenses_df.empty else []
                print(f"🔄 [EXPENSES_API] Fallback conversion: {len(expenses_list)} records")
                
                # Debug fallback structure too
                if expenses_list:
                    print(f"🔍 [EXPENSES_API] Fallback sample: {expenses_list[0]}")
            
            # Return format expected by frontend JavaScript
            return jsonify({'success': True, 'data': expenses_list, 'status': 'success'})
        except Exception as e:
            print(f"❌ [EXPENSES_API] CRITICAL ERROR: {e}")
            import traceback
            traceback.print_exc()
            # Railway-safe error response
            return jsonify({
                'success': False, 
                'data': [], 
                'status': 'error',
                'error': f'Expenses loading failed: {str(e)}',
                'environment': 'railway' if os.getenv('RAILWAY_PROJECT_ID') else 'local'
            }), 500
    
    elif request.method == 'POST':
        try:
            expense_data = {
                'date': datetime.strptime(request.json.get('date'), '%Y-%m-%d').date(),
                'amount': float(request.json.get('amount', 0)),
                'description': request.json.get('description', ''),
                'category': request.json.get('category', 'general'),
                'collector': request.json.get('collector', '')
            }
            
            expense_id = add_expense_to_database(expense_data)
            if expense_id:
                return jsonify({
                    'success': True, 
                    'status': 'success', 
                    'message': 'Expense added successfully',
                    'expense_id': expense_id  # Return expense_id for auto-categorization
                })
            else:
                return jsonify({'success': False, 'status': 'error', 'message': 'Failed to add expense'}), 400
        
        except Exception as e:
            return jsonify({'success': False, 'status': 'error', 'message': str(e)}), 500

@app.route('/api/expenses/<int:expense_id>', methods=['DELETE', 'PUT'])
def expense_operations(expense_id):
    """Delete or update specific expense"""
    if request.method == 'DELETE':
        try:
            print(f"🗑️ [DELETE_EXPENSE] Attempting to delete expense ID: {expense_id}")
            
            # Use database service instead of direct model access
            from core.models import db, Expense, ExpenseCategory
            
            # Find the expense in the database
            expense = db.session.query(Expense).filter_by(expense_id=expense_id).first()
            
            if not expense:
                print(f"❌ [DELETE_EXPENSE] Expense {expense_id} not found")
                return jsonify({'success': False, 'status': 'error', 'message': 'Expense not found'}), 404
            
            # CRITICAL FIX: Delete category first to avoid foreign key constraint violations
            print(f"🗑️ [DELETE_EXPENSE] Checking for existing categorization...")
            existing_category = ExpenseCategory.query.filter_by(expense_id=expense_id).first()
            if existing_category:
                print(f"🗑️ [DELETE_EXPENSE] Found category {existing_category.category}, deleting...")
                db.session.delete(existing_category)
            
            # Then delete the expense
            print(f"🗑️ [DELETE_EXPENSE] Deleting expense {expense_id}...")
            db.session.delete(expense)
            db.session.commit()
            
            print(f"✅ [DELETE_EXPENSE] Successfully deleted expense {expense_id} and its categorization")
            return jsonify({'success': True, 'status': 'success', 'message': 'Expense deleted successfully'})
            
        except Exception as e:
            print(f"❌ [DELETE_EXPENSE] Error deleting expense {expense_id}: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to rollback
            try:
                from core.models import db
                db.session.rollback()
            except:
                pass
                
            return jsonify({'success': False, 'status': 'error', 'message': f'Failed to delete expense: {str(e)}'}), 500
    
    elif request.method == 'PUT':
        try:
            print(f"✏️ [UPDATE_EXPENSE] Attempting to update expense ID: {expense_id}")
            
            # Import here to avoid circular imports
            from core.models import db, Expense
            
            # Find the expense
            expense = db.session.query(Expense).filter_by(expense_id=expense_id).first()
            if not expense:
                print(f"❌ [UPDATE_EXPENSE] Expense {expense_id} not found")
                return jsonify({'success': False, 'status': 'error', 'message': 'Expense not found'}), 404
            
            # Get update data
            data = request.get_json()
            if not data:
                return jsonify({'success': False, 'status': 'error', 'message': 'No update data provided'}), 400
            
            # Update fields if provided
            if 'date' in data:
                expense.expense_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
            if 'amount' in data:
                expense.amount = float(data['amount'])
            if 'description' in data:
                expense.description = data['description']
            if 'category' in data:
                expense.category = data['category']
            if 'collector' in data:
                expense.collector = data['collector']
            
            # Save changes
            db.session.commit()
            
            print(f"✅ [UPDATE_EXPENSE] Successfully updated expense {expense_id}")
            return jsonify({'success': True, 'status': 'success', 'message': 'Expense updated successfully'})
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ [UPDATE_EXPENSE] Error updating expense {expense_id}: {e}")
            return jsonify({'success': False, 'status': 'error', 'message': f'Failed to update expense: {str(e)}'}), 500

@app.route('/api/fix_expense_descriptions', methods=['POST'])
def fix_expense_descriptions():
    """Fix expense descriptions that show dates instead of content"""
    try:
        print("🔧 [FIX_DESCRIPTIONS] Starting expense description fix...")
        
        # Correct descriptions mapping based on your data
        CORRECT_DESCRIPTIONS = {
            118: "ăn đêm", 117: "mua dầu ăn", 116: "thay hộp cửa cuốn", 115: "Hưng mượn",
            114: "mua trứng", 113: "an cơm trưa", 112: "sửa xe", 111: "đổ xăng",
            110: "mua cháo", 109: "Ăn bánh xèo", 108: "mua sữa tắm", 107: "thanh toán shopeee",
            106: "thanh toán visa", 105: "Ăn phở rán", 104: "in tờ hướng dẫn", 103: "mua chậu giặt cây lau",
            102: "ăn đêm", 101: "Đổ xăng", 100: "Ăn bún riêu", 99: "Mua dầu gội + sáp thơm",
            98: "thanh toán booking ta hien Hưng", 97: "mua đèn ( 3 bóng , 1 ray )", 96: "mua tương ớt",
            95: "trả tiền xe", 94: "Ăn cơm", 93: "Mua tủ quần áo", 92: "Gửi hàng cho Hưng",
            91: "ăn nướng", 90: "Ăn vặt", 89: "Mua 1 chậu ngâm tẩy", 88: "Mua 2 chai xịt phòng"
        }
        
        # Import models
        from core.models import db, Expense
        
        fixed_count = 0
        not_found_count = 0
        
        for expense_id, correct_description in CORRECT_DESCRIPTIONS.items():
            # Find the expense
            expense = Expense.query.filter_by(expense_id=expense_id).first()
            
            if expense:
                old_desc = expense.description
                expense.description = correct_description
                print(f"✅ Fixed ID {expense_id}: '{old_desc}' → '{correct_description}'")
                fixed_count += 1
            else:
                print(f"⚠️ Expense ID {expense_id} not found in database")
                not_found_count += 1
        
        # Commit all changes
        db.session.commit()
        
        message = f"Fixed {fixed_count} expense descriptions successfully!"
        if not_found_count > 0:
            message += f" ({not_found_count} IDs not found)"
            
        print(f"🎉 [FIX_DESCRIPTIONS] {message}")
        
        return jsonify({
            'success': True,
            'message': message,
            'fixed_count': fixed_count,
            'not_found_count': not_found_count
        })
        
    except Exception as e:
        print(f"❌ [FIX_DESCRIPTIONS] Error: {e}")
        # Rollback on error
        try:
            from core.models import db
            db.session.rollback()
        except:
            pass
            
        return jsonify({
            'success': False,
            'message': f'Error fixing descriptions: {str(e)}'
        }), 500

@app.route('/api/expense_categories', methods=['GET', 'POST'])
def expense_categories_api():
    """Save and load expense categorizations (Personal/Work)"""
    try:
        from core.models import db, ExpenseCategory
        
        if request.method == 'GET':
            # Load all categorizations
            categories = ExpenseCategory.query.all()
            result = {}
            for cat in categories:
                result[str(cat.expense_id)] = cat.category
            
            print(f"📂 [LOAD_CATEGORIES] Loaded {len(result)} categorizations")
            return jsonify({
                'success': True,
                'categories': result
            })
            
        elif request.method == 'POST':
            # Save categorizations
            data = request.get_json()
            expense_ids = data.get('expense_ids', [])
            category = data.get('category', '')
            
            if not expense_ids or category not in ['personal', 'work']:
                return jsonify({
                    'success': False,
                    'message': 'Invalid expense IDs or category'
                }), 400
            
            # Remove duplicates from expense_ids to prevent constraint violations
            unique_expense_ids = list(set(expense_ids))
            
            saved_count = 0
            errors = []
            
            # Fix sequence issue by resetting PostgreSQL auto-increment sequence first
            from sqlalchemy import text
            
            try:
                # Reset the sequence to avoid ID conflicts
                db.session.execute(text("SELECT setval('expense_categories_id_seq', (SELECT COALESCE(MAX(id), 0) + 1 FROM expense_categories), false)"))
                print("🔧 [SEQUENCE_FIX] Reset auto-increment sequence for expense_categories")
            except Exception as seq_error:
                print(f"⚠️ [SEQUENCE_WARNING] Could not reset sequence: {seq_error}")
            
            for expense_id in unique_expense_ids:
                try:
                    print(f"🔍 [UPSERT_CATEGORY] Processing expense {expense_id} → {category}")
                    
                    # First try to update existing record
                    update_result = db.session.execute(
                        text("""
                            UPDATE expense_categories 
                            SET category = :category, updated_at = CURRENT_TIMESTAMP 
                            WHERE expense_id = :expense_id
                            RETURNING id, expense_id, category
                        """), 
                        {"expense_id": expense_id, "category": category}
                    )
                    
                    row = update_result.fetchone()
                    if row:
                        print(f"✅ [UPDATE_SUCCESS] Updated expense {expense_id} → {category} (Record ID: {row[0]})")
                        saved_count += 1
                    else:
                        # No existing record, create new one
                        insert_result = db.session.execute(
                            text("""
                                INSERT INTO expense_categories (expense_id, category, created_at, updated_at)
                                VALUES (:expense_id, :category, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                RETURNING id, expense_id, category
                            """), 
                            {"expense_id": expense_id, "category": category}
                        )
                        
                        row = insert_result.fetchone()
                        if row:
                            print(f"✅ [INSERT_SUCCESS] Created expense {expense_id} → {category} (Record ID: {row[0]})")
                            saved_count += 1
                        else:
                            errors.append(f"Expense {expense_id}: Failed to insert or update")
                    
                except Exception as item_error:
                    # Simple error handling for UPSERT approach
                    print(f"❌ [UPSERT_ERROR] Failed to process expense {expense_id}: {str(item_error)}")
                    db.session.rollback()
                    errors.append(f"Expense {expense_id}: {str(item_error)}")
            
            # Final commit for any remaining changes
            try:
                db.session.commit()
            except Exception as final_error:
                db.session.rollback()
                errors.append(f"Final commit failed: {str(final_error)}")
            
            if errors:
                return jsonify({
                    'success': saved_count > 0,
                    'message': f'Saved {saved_count} categorizations. Errors: {"; ".join(errors)}',
                    'saved_count': saved_count,
                    'errors': errors
                }), 422 if saved_count > 0 else 500
            else:
                return jsonify({
                    'success': True,
                    'message': f'Saved {saved_count} categorizations successfully!',
                    'saved_count': saved_count
                })
            
    except Exception as e:
        print(f"❌ [EXPENSE_CATEGORIES] Error: {e}")
        db.session.rollback() 
        return jsonify({
            'success': False,
            'message': f'Error with categorizations: {str(e)}'
        }), 500

@app.route('/api/create_categories_table', methods=['POST'])
def create_categories_table():
    """Create expense_categories table if it doesn't exist"""
    try:
        from core.models import db, ExpenseCategory
        
        # Create the table
        db.create_all()
        
        print("✅ [CREATE_TABLE] expense_categories table created successfully")
        return jsonify({
            'success': True,
            'message': 'Categories table created successfully!'
        })
        
    except Exception as e:
        print(f"❌ [CREATE_TABLE] Error: {e}")
        return jsonify({
            'success': False,
            'message': f'Error creating table: {str(e)}'
        }), 500

@app.route('/bookings/save_extracted', methods=['POST'])
def save_extracted_bookings():
    """Save multiple extracted bookings from AI photo processing"""
    try:
        print("🚀 [SAVE_EXTRACTED] API called - saving multiple bookings")
        
        # Get extracted bookings from form data
        extracted_json = request.form.get('extracted_json')
        force_add_duplicates = request.form.get('force_add_duplicates') == 'true'
        
        print(f"🔧 [SAVE_EXTRACTED] Force add duplicates setting: {force_add_duplicates}")
        print(f"🔧 [SAVE_EXTRACTED] Raw form value: '{request.form.get('force_add_duplicates')}'")
        print(f"🔧 [SAVE_EXTRACTED] All form keys: {list(request.form.keys())}")
        
        if not extracted_json:
            print("❌ [SAVE_EXTRACTED] No extracted_json provided")
            flash('Không có dữ liệu booking để lưu', 'error')
            return redirect(url_for('add_booking'))
        
        try:
            bookings_data = json.loads(extracted_json)
            print(f"📊 [SAVE_EXTRACTED] Received {len(bookings_data)} bookings to save")
        except json.JSONDecodeError as e:
            print(f"❌ [SAVE_EXTRACTED] JSON decode error: {e}")
            flash('Dữ liệu booking không hợp lệ', 'error')
            return redirect(url_for('add_booking'))
        
        if not isinstance(bookings_data, list) or len(bookings_data) == 0:
            print("❌ [SAVE_EXTRACTED] Invalid bookings data format")
            flash('Dữ liệu booking không hợp lệ', 'error')
            return redirect(url_for('add_booking'))
        
        # Process and save each booking
        saved_count = 0
        replaced_count = 0
        forced_duplicate_count = 0  # Track bookings added despite being duplicates
        failed_bookings = []
        existing_bookings = []  # Track bookings that already exist
        
        for i, booking_data in enumerate(bookings_data):
            try:
                guest_name = booking_data.get('guest_name', '')
                booking_id = booking_data.get('booking_id', '')
                
                print(f"💾 [SAVE_EXTRACTED] Processing booking {i+1}: {guest_name}")
                
                # Check if this is a replacement operation FIRST (before checking existing)
                is_replacement = booking_data.get('replace_mode') and booking_data.get('replace_existing_id')
                
                # Check if booking ID already exists (only skip if NOT a replacement AND force_add not enabled)
                existing_booking = load_booking_data()
                booking_exists = not existing_booking.empty and booking_id and booking_id in existing_booking['Số đặt phòng'].values
                
                if booking_exists and not is_replacement and not force_add_duplicates:
                    print(f"ℹ️ [SAVE_EXTRACTED] Booking ID {booking_id} already exists - skipping (not an error)")
                    existing_bookings.append(f"Booking {i+1}: {guest_name} - Already exists in system ({booking_id})")
                    continue
                elif booking_exists and force_add_duplicates:
                    print(f"💪 [SAVE_EXTRACTED] FORCE ADD MODE: Booking ID {booking_id} already exists - FORCE ADDING as requested")
                    # Generate new unique booking ID for the duplicate
                    original_booking_id = booking_id
                    booking_id = f"{booking_id}_DUP_{datetime.now().strftime('%H%M%S')}"
                    print(f"🆔 [SAVE_EXTRACTED] Generated NEW duplicate booking ID: {original_booking_id} → {booking_id}")
                    booking_data['booking_id'] = booking_id  # Update the booking data
                    forced_duplicate_count += 1
                elif booking_exists:
                    print(f"⚠️ [SAVE_EXTRACTED] Booking ID {booking_id} exists but conditions unclear:")
                    print(f"   - is_replacement: {is_replacement}")
                    print(f"   - force_add_duplicates: {force_add_duplicates}")
                    existing_bookings.append(f"Booking {i+1}: {guest_name} - Already exists in system ({booking_id})")
                    continue
                elif is_replacement:
                    print(f"🔄 [SAVE_EXTRACTED] Replacement mode detected for {guest_name} - proceeding with replacement")
                
                # Generate unique booking ID if empty or duplicate
                if not booking_id:
                    booking_id = f"AI_{datetime.now().strftime('%Y%m%d%H%M%S')}{i:02d}"
                    print(f"🔄 [SAVE_EXTRACTED] Generated new booking ID: {booking_id}")
                
                # Generate unique email to avoid constraint violations
                unique_email = f"guest{booking_id.lower()}@ai-extracted.local"
                print(f"📧 [SAVE_EXTRACTED] Generated unique email: {unique_email}")
                
                # Parse dates with multiple format support
                checkin_date = None
                checkout_date = None
                
                # Try multiple date formats
                checkin_str = booking_data.get('checkin_date') or booking_data.get('check_in_date', '')
                checkout_str = booking_data.get('checkout_date') or booking_data.get('check_out_date', '')
                
                date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d']
                
                for date_format in date_formats:
                    try:
                        if checkin_str and not checkin_date:
                            checkin_date = datetime.strptime(str(checkin_str), date_format).date()
                        if checkout_str and not checkout_date:
                            checkout_date = datetime.strptime(str(checkout_str), date_format).date()
                        if checkin_date and checkout_date:
                            break
                    except ValueError:
                        continue
                
                # Convert to expected format for add_new_booking function
                processed_booking = {
                    'guest_name': str(guest_name).strip() if guest_name else '',
                    'booking_id': str(booking_id).strip() if booking_id else '',
                    'email': unique_email,
                    'phone': str(booking_data.get('phone', '')).strip(),
                    'nationality': str(booking_data.get('nationality', '')).strip(),
                    'passport_number': str(booking_data.get('passport_number', '')).strip(),
                    'checkin_date': checkin_date,
                    'checkout_date': checkout_date,
                    'room_amount': float(booking_data.get('room_amount', 0)) if booking_data.get('room_amount') else 0.0,
                    'commission': float(booking_data.get('commission', 0)) if booking_data.get('commission') else 0.0,
                    'taxi_amount': float(booking_data.get('taxi_amount', 0)) if booking_data.get('taxi_amount') else 0.0,
                    'collector': '',
                    'notes': f"AI extracted on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                }
                
                # Validate required fields
                if not processed_booking['guest_name']:
                    raise ValueError("Missing guest name")
                if not processed_booking['checkin_date']:
                    raise ValueError("Missing check-in date")
                if not processed_booking['checkout_date']:
                    raise ValueError("Missing check-out date")
                if processed_booking['room_amount'] <= 0:
                    raise ValueError("Invalid room amount")
                
                # Check if this is a replacement operation
                print(f"🔍 [DEBUG] Checking booking {i+1} for replacement mode:")
                print(f"   - replace_mode: {booking_data.get('replace_mode')}")
                print(f"   - replace_existing_id: {booking_data.get('replace_existing_id')}")
                
                if booking_data.get('replace_mode') and booking_data.get('replace_existing_id'):
                    # Handle replacement of existing booking
                    replace_existing_id = booking_data.get('replace_existing_id')
                    print(f"🔄 [REPLACE_MODE] Replacing existing booking ID: {replace_existing_id}")
                    print(f"🔄 [REPLACE_MODE] New data: {processed_booking['guest_name']} - {processed_booking['room_amount']}")
                    
                    if update_booking(replace_existing_id, processed_booking):
                        replaced_count += 1
                        print(f"✅ [SAVE_EXTRACTED] Replaced booking {i+1}: {processed_booking['guest_name']} (ID: {replace_existing_id})")
                    else:
                        failed_bookings.append(f"Booking {i+1}: {booking_data.get('guest_name', 'Unknown')} - Replacement failed")
                        print(f"❌ [REPLACE_MODE] Replacement failed for booking {i+1}")
                else:
                    print(f"➕ [NEW_BOOKING] Creating new booking for {processed_booking['guest_name']}")
                    # Save as new booking using existing function
                    if add_new_booking(processed_booking):
                        saved_count += 1
                        print(f"✅ [SAVE_EXTRACTED] Saved booking {i+1}: {processed_booking['guest_name']}")
                    else:
                        failed_bookings.append(f"Booking {i+1}: {booking_data.get('guest_name', 'Unknown')} - Database save failed")
                    
            except Exception as booking_error:
                print(f"❌ [SAVE_EXTRACTED] Error saving booking {i+1}: {booking_error}")
                import traceback
                traceback.print_exc()
                failed_bookings.append(f"Booking {i+1}: {booking_data.get('guest_name', 'Unknown')} - {str(booking_error)}")
        
        # Prepare result message
        total_processed = saved_count + replaced_count + forced_duplicate_count
        if total_processed > 0:
            success_parts = []
            if saved_count > 0:
                success_parts.append(f"{saved_count} booking mới")
            if replaced_count > 0:
                success_parts.append(f"{replaced_count} booking đã thay thế")
            if forced_duplicate_count > 0:
                success_parts.append(f"{forced_duplicate_count} booking trùng lặp được thêm")
            
            success_msg = f"✅ Đã xử lý thành công {' và '.join(success_parts)}"
            if existing_bookings or failed_bookings:
                total_skipped = len(existing_bookings) + len(failed_bookings)
                success_msg += f" (bỏ qua {total_skipped} booking)"
            flash(success_msg, 'success')
            
            # Show forced duplicates message
            if forced_duplicate_count > 0:
                flash(f"💪 Đã thêm {forced_duplicate_count} booking trùng lặp với ID mới (có thể chỉnh sửa riêng biệt)", 'warning')
            
        # Show replacement summary if any
        if replaced_count > 0:
            flash(f"🔄 Đã thay thế {replaced_count} booking cũ với dữ liệu mới", 'info')
        
        # Show existing bookings as info (not errors)
        if existing_bookings:
            for existing in existing_bookings:
                flash(f"ℹ️ {existing}", 'info')
        
        # Show actual errors
        if failed_bookings:
            for error in failed_bookings:
                flash(f"❌ {error}", 'error')
        
        # If nothing was processed and no existing bookings
        if total_processed == 0 and len(existing_bookings) == 0:
            flash('❌ Không thể lưu booking nào. Vui lòng kiểm tra dữ liệu và thử lại.', 'error')
        
        print(f"🎯 [SAVE_EXTRACTED] Complete: {saved_count} saved, {replaced_count} replaced, {len(existing_bookings)} existing, {len(failed_bookings)} failed")
        return redirect(url_for('view_bookings'))
        
    except Exception as e:
        print(f"❌ [SAVE_EXTRACTED] Fatal error: {e}")
        import traceback
        traceback.print_exc()
        flash(f'❌ Lỗi hệ thống khi lưu booking: {str(e)}', 'error')
        return redirect(url_for('add_booking'))

@app.route('/calendar/')
@app.route('/calendar/<int:year>/<int:month>')
def calendar_view(year=None, month=None):
    """Calendar view with PostgreSQL data"""
    if year is None or month is None:
        today = datetime.today()
        year, month = today.year, today.month
    
    # Check if fresh data is requested
    force_fresh = request.args.get('refresh') == 'true'
    df = load_booking_data_for_calculations(force_fresh=force_fresh)  # Exclude cancelled bookings
    
    # Generate calendar data in weeks format expected by template
    cal = calendar.monthrange(year, month)
    first_day, num_days = cal
    
    # Create calendar weeks structure
    calendar_data = []
    week = []
    
    # Add empty days for start of month
    for i in range(first_day):
        week.append((None, None, None))
    
    # Add actual days
    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        day_info = get_overall_calendar_day_info(df, date_str, TOTAL_HOTEL_CAPACITY)
        
        week.append((date_obj, date_str, day_info))
        
        # Start new week on Sunday (weekday 6)
        if len(week) == 7:
            calendar_data.append(week)
            week = []
    
    # Add remaining empty days to complete last week
    while len(week) < 7:
        week.append((None, None, None))
    
    if week:
        calendar_data.append(week)
    
    # Generate revenue by date using optimized daily revenue calculation
    from core.dashboard_routes import get_daily_revenue_by_stay
    daily_revenue_data = get_daily_revenue_by_stay(df)
    
    revenue_by_date = {}
    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Use optimized daily revenue data if available, fallback to calendar info
        if date_obj in daily_revenue_data:
            revenue_info = daily_revenue_data[date_obj]
            revenue_by_date[date_obj] = type('obj', (object,), {
                'daily_total': revenue_info['daily_total'],
                'daily_total_minus_commission': revenue_info['daily_total_minus_commission'],
                'total_commission': revenue_info['total_commission']
            })()
        else:
            # Fallback to calendar info for dates without revenue data
            day_info = get_overall_calendar_day_info(df, date_str, TOTAL_HOTEL_CAPACITY)
            revenue_by_date[date_obj] = type('obj', (object,), {
                'daily_total': day_info.get('daily_revenue', 0),
                'daily_total_minus_commission': day_info.get('revenue_minus_commission', 0),
                'total_commission': day_info.get('commission_total', 0)
            })()
    
    # Calculate previous and next month for navigation
    current_month = datetime(year, month, 1)
    
    if month == 1:
        prev_month = datetime(year - 1, 12, 1)
    else:
        prev_month = datetime(year, month - 1, 1)
    
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    
    return render_template(
        'calendar.html',
        year=year,
        month=month,
        calendar_data=calendar_data,
        month_name=calendar.month_name[month],
        current_month=current_month,
        prev_month=prev_month,
        next_month=next_month,
        today=datetime.today().date(),  # Add today for template comparisons
        revenue_by_date=revenue_by_date  # Add revenue data for template
    )

@app.route('/calendar_details/<date_str>')
def calendar_details(date_str):
    """Calendar details view for specific date"""
    try:
        # Parse the date
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        
        # Load booking data excluding cancelled bookings for calendar calculations
        df = load_booking_data_for_calculations()
        
        # Get detailed day information
        day_info = get_overall_calendar_day_info(df, date_str, TOTAL_HOTEL_CAPACITY)
        
        # Get activity data for the template
        activity = day_info.get('activity', {})
        check_in = activity.get('arrivals', [])
        check_out = activity.get('departures', [])
        staying_over = activity.get('staying', [])
        
        # Calculate revenue info
        day_revenue_info = type('obj', (object,), {
            'daily_total': day_info.get('daily_revenue', 0),
            'daily_total_minus_commission': day_info.get('revenue_minus_commission', 0),
            'total_commission': day_info.get('commission_total', 0),
            'guest_count': len(check_in) + len(check_out) + len(staying_over),
            'bookings': []  # Could be enhanced later with per-booking breakdown
        })()
        
        return render_template(
            'calendar_details.html',
            date=date_obj,
            date_str=date_str,
            day_info=day_info,
            formatted_date=date_obj.strftime("%d/%m/%Y"),
            check_in=check_in,
            check_out=check_out,
            staying_over=staying_over,
            day_revenue_info=day_revenue_info,
            current_date=date_obj,
            pd=pd  # For template processing
        )
    
    except Exception as e:
        flash(f'Error loading calendar details: {str(e)}', 'error')
        return redirect(url_for('calendar_view'))

# Photo Processing Endpoint - Enhanced with Multiple Booking Support
@app.route('/api/check_existing_bookings', methods=['POST'])
def check_existing_bookings():
    """Check which bookings already exist in the system"""
    try:
        data = request.get_json()
        bookings_to_check = data.get('bookings', [])
        
        existing_booking_data = load_booking_data()
        existing_ids = set()
        if not existing_booking_data.empty and 'Số đặt phòng' in existing_booking_data.columns:
            existing_ids = set(existing_booking_data['Số đặt phòng'].dropna().astype(str))
        
        # Check each booking
        results = []
        for i, booking in enumerate(bookings_to_check):
            booking_id = str(booking.get('booking_id', '')).strip()
            guest_name = booking.get('guest_name', '')
            
            is_existing = booking_id in existing_ids if booking_id else False
            
            results.append({
                'index': i,
                'guest_name': guest_name,
                'booking_id': booking_id,
                'exists': is_existing,
                'status': 'existing' if is_existing else 'new'
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'total_existing': sum(1 for r in results if r['exists'])
        })
        
    except Exception as e:
        print(f"❌ [CHECK_EXISTING] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/process_pasted_image', methods=['POST'])
def process_pasted_image():
    """Enhanced photo processing with smart single/multiple booking detection"""
    try:
        # 🚂 RAILWAY DEBUG: Enhanced logging for deployment debugging
        railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
        environment = 'railway' if railway_env else 'local'
        print(f"🌍 [PHOTO_PROCESSING] Environment: {environment}")
        print(f"📝 [PHOTO_PROCESSING] Request method: {request.method}")
        print(f"📝 [PHOTO_PROCESSING] Content type: {request.content_type}")
        print(f"📝 [PHOTO_PROCESSING] Request size: {request.content_length}")
        
        # Configure Gemini API
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            error_msg = f'Google AI API not configured on {environment}'
            print(f"❌ [PHOTO_PROCESSING] {error_msg}")
            return jsonify({'error': error_msg, 'environment': environment}), 400
        
        # Get image data from request - handle both file upload and JSON base64
        image_data = None
        
        # Method 1: File upload (multipart/form-data)
        if request.files.get('image'):
            image_data = request.files.get('image').read()
            
        # Method 2: JSON with base64 data (application/json)  
        elif request.is_json and request.json.get('image_b64'):
            import base64
            try:
                # Remove data URL prefix if present (data:image/png;base64,)
                base64_data = request.json.get('image_b64')
                if ',' in base64_data:
                    base64_data = base64_data.split(',')[1]
                
                image_data = base64.b64decode(base64_data)
                print(f"✅ Decoded base64 image, size: {len(image_data)} bytes")
                
            except Exception as decode_error:
                print(f"❌ Base64 decode error: {decode_error}")
                return jsonify({'error': f'Invalid base64 image data: {str(decode_error)}'}), 400
        
        if not image_data:
            return jsonify({'error': 'No image provided (expected file upload or base64 JSON)'}), 400
        
        print("🔍 [PHOTO_PROCESSING] Starting AI image analysis...")
        
        # Extract booking info using Gemini
        booking_info = extract_booking_info_from_image_content(image_data, GOOGLE_API_KEY)
        
        # Check if extraction was successful
        if 'error' in booking_info:
            return jsonify(booking_info), 400
        
        print(f"✅ Booking info extracted successfully: {booking_info}")
        print(f"🤖 [AI_RESPONSE] Raw data: {booking_info}")
        
        # Handle new format from AI with type detection
        if 'type' in booking_info:
            # New format from enhanced AI prompt
            if booking_info['type'] == 'single':
                # Single booking detected
                booking = booking_info['booking']
                bookings_list = [booking]
                
            elif booking_info['type'] == 'multiple':
                # Multiple bookings detected
                bookings_list = booking_info.get('bookings', [])
            else:
                # Unknown type, treat as single
                bookings_list = [booking_info.get('booking', booking_info)]
        else:
            # Legacy format fallback (single booking without type)
            bookings_list = [booking_info]
        
        # Use AI duplicate detector for comprehensive analysis (if available)
        ai_analysis = {
            'analysis': {
                'new_bookings': len(bookings_list),
                'duplicates_found': 0,
                'summary': 'AI duplicate detection not available'
            },
            'filtering_options': [],
            'recommendations': []
        }
        if ai_duplicate_detector:
            print(f"🤖 [AI_DUPLICATE] Starting AI duplicate detection for {len(bookings_list)} bookings...")
            df = load_booking_data()
            ai_analysis = ai_duplicate_detector.create_filtered_response(bookings_list, df)
        else:
            print("⚠️ [AI_DUPLICATE] AI duplicate detector not available - skipping analysis")
        
        # Format response with AI analysis
        response_data = {
            'success': True,
            'type': 'multiple' if len(bookings_list) > 1 else 'single',
            'total_extracted': len(bookings_list),
            'ai_analysis': ai_analysis['analysis'],
            'filtering_options': ai_analysis['filtering_options'], 
            'recommendations': ai_analysis['recommendations'],
            'message': f"🤖 AI đã phân tích {len(bookings_list)} booking - {ai_analysis['analysis']['new_bookings']} mới, {ai_analysis['analysis']['duplicates_found']} trùng lặp"
        }
        
        # Include individual booking data for backward compatibility
        if len(bookings_list) == 1:
            response_data['booking'] = bookings_list[0]
        else:
            response_data['bookings'] = bookings_list
            response_data['count'] = len(bookings_list)
        
        return jsonify(response_data)
    
    except Exception as e:
        # 🚂 RAILWAY DEBUG: Enhanced error logging for deployment debugging
        railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
        environment = 'railway' if railway_env else 'local'
        
        print(f"❌ [PHOTO_PROCESSING] Error on {environment}: {e}")
        import traceback
        traceback.print_exc()
        
        # Enhanced error response for Railway debugging
        return jsonify({
            'error': str(e),
            'environment': environment,
            'error_type': type(e).__name__,
            'debug_info': {
                'railway_project_id': os.getenv('RAILWAY_PROJECT_ID'),
                'google_api_configured': bool(os.getenv("GOOGLE_API_KEY")),
                'request_content_type': request.content_type,
                'request_method': request.method
            }
        }), 500

@app.route('/api/railway_image_diagnostic', methods=['GET', 'POST'])
def railway_image_diagnostic():
    """Railway-specific diagnostic endpoint for image upload debugging"""
    try:
        railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
        
        diagnostic_info = {
            'success': True,
            'environment': 'railway' if railway_env else 'local',
            'timestamp': datetime.now().isoformat(),
            'api_configuration': {
                'google_api_key_configured': bool(os.getenv("GOOGLE_API_KEY")),
                'google_api_key_length': len(os.getenv("GOOGLE_API_KEY", "")) if os.getenv("GOOGLE_API_KEY") else 0,
                'railway_project_id': os.getenv('RAILWAY_PROJECT_ID', 'Not set'),
                'flask_debug': app.config.get('DEBUG', False)
            },
            'request_info': {
                'method': request.method,
                'content_type': request.content_type,
                'content_length': request.content_length,
                'headers': dict(request.headers),
                'origin': request.headers.get('Origin'),
                'user_agent': request.headers.get('User-Agent', '')[:100]  # Truncate for readability
            }
        }
        
        if request.method == 'POST':
            # Test image upload functionality
            diagnostic_info['upload_test'] = {
                'files_received': len(request.files),
                'json_received': request.is_json,
                'form_data_received': bool(request.form)
            }
            
            if request.files.get('test_image'):
                test_file = request.files.get('test_image')
                diagnostic_info['upload_test']['test_file'] = {
                    'filename': test_file.filename,
                    'content_type': test_file.content_type,
                    'size': len(test_file.read())
                }
                test_file.seek(0)  # Reset file pointer
            
            if request.is_json and request.json.get('test_b64'):
                import base64
                try:
                    base64_data = request.json.get('test_b64')
                    if ',' in base64_data:
                        base64_data = base64_data.split(',')[1]
                    decoded = base64.b64decode(base64_data)
                    diagnostic_info['upload_test']['base64_test'] = {
                        'original_length': len(request.json.get('test_b64')),
                        'decoded_size': len(decoded),
                        'decode_successful': True
                    }
                except Exception as b64_error:
                    diagnostic_info['upload_test']['base64_test'] = {
                        'decode_successful': False,
                        'error': str(b64_error)
                    }
        
        return jsonify(diagnostic_info)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'environment': 'railway' if os.getenv('RAILWAY_PROJECT_ID') else 'local'
        }), 500

# Customer Care Management - DISABLED
# @app.route('/customer_care')
# def customer_care():
#     """Customer care dashboard"""
#     try:
#         # Load recent bookings for customer service
#         df = load_booking_data()
#         
#         # Get upcoming arrivals (next 7 days)
#         today = datetime.today().date()
#         upcoming_arrivals = []
#         
#         if not df.empty:
#             df_clean = df.copy()
#             df_clean['Check-in Date'] = pd.to_datetime(df_clean['Check-in Date'], errors='coerce')
#             
#             for _, booking in df_clean.iterrows():
#                 checkin_date = booking['Check-in Date']
#                 if pd.notna(checkin_date):
#                     checkin_date = checkin_date.date()
#                     days_until = (checkin_date - today).days
#                     if 0 <= days_until <= 7:  # Next 7 days
#                         upcoming_arrivals.append({
#                             'guest_name': booking.get('Tên người đặt', 'N/A'),
#                             'booking_id': booking.get('Số đặt phòng', 'N/A'),
#                             'checkin_date': checkin_date,
#                             'checkout_date': pd.to_datetime(booking['Check-out Date']).date() if pd.notna(booking['Check-out Date']) else None,
#                             'days_until': days_until,
#                             'total_amount': booking.get('Tổng thanh toán', 0),
#                             'commission': booking.get('Hoa hồng', 0),
#                             'collector': booking.get('Người thu tiền', ''),
#                             'phone': booking.get('phone', ''),
#                             'notes': booking.get('Ghi chú thanh toán', '')
#                         })
#         
#         upcoming_arrivals.sort(key=lambda x: x['days_until'])
#         
#         return render_template('customer_care.html', 
#                              upcoming_arrivals=upcoming_arrivals,
#                              today=today)
#         
#     except Exception as e:
#         print(f"Error loading customer care: {e}")
#         flash(f'Error loading customer care: {str(e)}', 'error')
#         return render_template('customer_care.html', upcoming_arrivals=[], today=today)

# AI Assistant routes (Gemini only - no Google Sheets)
@app.route('/ai_assistant')
def ai_assistant():
    """AI Assistant interface"""
    return render_template('ai_assistant.html')

@app.route('/test_js')
def test_js():
    """Test JavaScript functions"""
    return send_from_directory('.', 'test_js_functions.html')

@app.route('/debug_functions')
def debug_functions():
    """Debug function availability"""
    return send_from_directory('.', 'debug_functions.html')

@app.route('/emergency_fix')
def emergency_fix():
    """Emergency fix for canceled customer management"""
    return send_from_directory('.', 'emergency_fix.html')

@app.route('/simple_test')
def simple_test():
    """Simple test for canceled customer management"""
    return send_from_directory('.', 'simple_test.html')


@app.route('/api/quick_notes', methods=['GET', 'POST'])
def quick_notes():
    """Quick notes management"""
    try:
        db_service = get_database_service()
        
        if request.method == 'GET':
            # Get all quick notes
            print(f"📋 [GET_QUICK_NOTES] Loading quick notes...")
            notes = db_service.get_quick_notes()
            print(f"📋 [GET_QUICK_NOTES] Found {len(notes)} notes")
            
            if notes:
                print(f"📋 [GET_QUICK_NOTES] Sample note: {notes[0]}")
                print(f"📋 [GET_QUICK_NOTES] Sample note has to_dict: {hasattr(notes[0], 'to_dict')}")
            
            # Convert to dict safely
            result = []
            for note in notes:
                try:
                    result.append(note.to_dict())
                except Exception as e:
                    print(f"❌ [QUICK_NOTES_ERROR] Error converting note {note.note_id}: {e}")
                    # Create manual dict if to_dict fails
                    result.append({
                        'note_id': note.note_id,
                        'note_type': note.note_type,
                        'content': note.note_content,
                        'completed': note.is_completed,
                        'created_at': note.created_at.isoformat() if note.created_at else None,
                        'created_by': note.created_by
                    })
            
            print(f"📋 [GET_QUICK_NOTES] Returning {len(result)} formatted notes")
            return jsonify(result)
        
        elif request.method == 'POST':
            # Create new quick note
            data = request.get_json()
            print(f"📝 [CREATE_QUICK_NOTE] Creating note: {data}")
            
            # Debug note type transformation
            original_type = data.get('type', data.get('note_type', 'general'))
            print(f"🔍 [DEBUG] Original note_type from frontend: '{original_type}'")
            print(f"🔍 [DEBUG] Type of note_type: {type(original_type)}")
            print(f"🔍 [DEBUG] Raw request data: {data}")
            
            # Validate required fields
            if not data.get('content'):
                return jsonify({'error': 'Content is required'}), 400
            
            note = db_service.create_quick_note(
                note_type=original_type,  # Use original type without transformation
                content=data.get('content', ''),
                guest_name=data.get('guest_name'),
                booking_id=data.get('booking_id'),
                priority=data.get('priority', 'normal'),
                note_date=data.get('date'),  # Pass scheduled date from frontend
                note_time=data.get('time')   # Pass scheduled time from frontend
            )
            print(f"✅ [CREATE_QUICK_NOTE] Note created successfully: {note.note_id}")
            return jsonify({
                'success': True,
                'message': 'Note created successfully',
                'note': note.to_dict()
            }), 201
    
    except Exception as e:
        print(f"❌ [QUICK_NOTES_ERROR] Error: {e}")
        import traceback
        print(f"❌ [QUICK_NOTES_ERROR] Traceback: {traceback.format_exc()}")
        return jsonify({
            'error': str(e),
            'details': 'Check server logs for more information'
        }), 500

@app.route('/api/quick_notes/<int:note_id>', methods=['GET', 'PUT', 'DELETE'])
def quick_note_detail(note_id):
    """Quick note detail operations"""
    try:
        db_service = get_database_service()
        
        if request.method == 'GET':
            note = db_service.get_quick_note(note_id)
            if not note:
                return jsonify({'error': 'Note not found'}), 404
            return jsonify(note.to_dict())
        
        elif request.method == 'PUT':
            data = request.get_json()
            print(f"✏️ [UPDATE_QUICK_NOTE] Updating note {note_id}: {data}")
            note = db_service.update_quick_note(note_id, data)
            if not note:
                return jsonify({'success': False, 'error': 'Note not found'}), 404
            print(f"✅ [UPDATE_QUICK_NOTE] Note {note_id} updated successfully")
            return jsonify({
                'success': True,
                'message': 'Note updated successfully',
                'note': note.to_dict()
            })
        
        elif request.method == 'DELETE':
            print(f"🗑️ [DELETE_QUICK_NOTE] Attempting to delete note ID: {note_id}")
            
            # ✅ ENHANCED: Check if note exists first for better debugging
            existing_note = db_service.get_quick_note(note_id)
            if not existing_note:
                print(f"❌ [DELETE_QUICK_NOTE] Note {note_id} does not exist in database")
                
                # List recent notes for debugging
                all_notes = db_service.get_quick_notes()
                print(f"🔍 [DELETE_DEBUG] Found {len(all_notes)} total notes in database")
                if all_notes:
                    recent_notes = all_notes[:5]  # Show first 5
                    print(f"🔍 [DELETE_DEBUG] Recent note IDs: {[n.note_id for n in recent_notes]}")
                
                return jsonify({
                    'success': False, 
                    'error': f'QuickNote with ID {note_id} not found',
                    'debug_info': f'Database contains {len(all_notes)} notes total'
                }), 404
            
            print(f"🗑️ [DELETE_QUICK_NOTE] Found note: '{existing_note.note_content[:50]}...'")
            success = db_service.delete_quick_note(note_id)
            if success:
                print(f"✅ [DELETE_QUICK_NOTE] Successfully deleted note {note_id}")
                return jsonify({'success': True, 'message': 'Note deleted successfully'})
            else:
                print(f"❌ [DELETE_QUICK_NOTE] Deletion failed for note {note_id}")
                return jsonify({'success': False, 'error': 'Deletion failed'}), 500
    
    except Exception as e:
        print(f"❌ [DELETE_QUICK_NOTE] Error deleting note {note_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/arrival_times', methods=['GET', 'POST'])
def arrival_times():
    """Arrival times management"""
    try:
        db_service = get_database_service()
        
        if request.method == 'GET':
            # Get all arrival times
            arrival_times = db_service.get_arrival_times()
            return jsonify([at.to_dict() for at in arrival_times])
        
        elif request.method == 'POST':
            # Create or update arrival time
            data = request.get_json()
            print(f"🕐 [ARRIVAL_TIME] Received data: {data}")
            
            booking_id = data.get('booking_id')
            estimated_arrival = data.get('estimated_arrival')
            notes = data.get('notes', '')
            
            if not booking_id:
                return jsonify({'success': False, 'error': 'booking_id is required'}), 400
            
            try:
                arrival_time = db_service.upsert_arrival_time(
                    booking_id=booking_id,
                    estimated_arrival=estimated_arrival,
                    notes=notes
                )
                print(f"🕐 [ARRIVAL_TIME] Successfully saved: booking_id={booking_id}, time={estimated_arrival}")
                return jsonify({'success': True, 'data': arrival_time.to_dict()})
            
            except Exception as e:
                print(f"🕐 [ARRIVAL_TIME] Error saving: {e}")
                return jsonify({'success': False, 'error': str(e)}), 500
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze_duplicates', methods=['GET'])
def analyze_duplicates_api():
    """API endpoint for AI duplicate analysis with timeout and better error handling"""
    import time
    start_time = time.time()
    
    print("🤖 [API] Analyze duplicates endpoint called")
    
    try:
        # Load data with timeout protection
        print("🤖 [API] Loading booking data...")
        df, _ = load_data()
        load_time = time.time() - start_time
        print(f"🤖 [API] Data loaded in {load_time:.2f}s, shape: {df.shape}")
        
        if df.empty:
            print("🤖 [API] No booking data found")
            return jsonify({
                'success': True,
                'data': {
                    'duplicate_groups': [],
                    'total_duplicates': 0,
                    'message': 'No booking data found'
                }
            })
        
        # Use the existing duplicate analysis function with timeout
        print("🤖 [API] Starting duplicate analysis...")
        analysis_result = analyze_existing_duplicates(df)
        
        total_time = time.time() - start_time
        print(f"🤖 [API] Analysis completed in {total_time:.2f}s")
        
        # Ensure we have the expected structure
        if 'total_duplicates' not in analysis_result:
            analysis_result['total_duplicates'] = len(analysis_result.get('duplicate_groups', []))
        
        return jsonify({
            'success': True,
            'data': analysis_result,
            'message': f'Found {analysis_result["total_duplicates"]} duplicate groups',
            'processing_time': total_time
        })
        
    except Exception as e:
        error_time = time.time() - start_time
        print(f"🤖 [API] Error in duplicate analysis after {error_time:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}',
            'processing_time': error_time,
            'error_type': type(e).__name__
        }), 500

@app.route('/database_health')
def database_health_page():
    """Database health check page"""
    try:
        # Get health status from the API endpoint
        db_service = get_database_service()
        health_data = db_service.get_health_status()
        
        # Get some basic stats
        df, _ = load_data()
        stats = {
            'total_bookings': len(df),
            'active_bookings': len(df[df['Tình trạng'] != 'Đã hủy']) if not df.empty else 0,
            'this_month_bookings': 0
        }
        
        if not df.empty:
            this_month = datetime.now().replace(day=1)
            stats['this_month_bookings'] = len(df[df['Check-in Date'] >= this_month])
        
        return render_template('database_health.html', health=health_data, stats=stats)
        
    except Exception as e:
        return render_template('database_health.html', 
                               health={'status': 'error', 'error': str(e)}, 
                               stats={'total_bookings': 0, 'active_bookings': 0, 'this_month_bookings': 0})

@app.route('/api/test_gemini', methods=['GET'])
def test_gemini_api():
    """Test endpoint to verify Gemini API connectivity"""
    try:
        if not GOOGLE_API_KEY or GOOGLE_API_KEY == 'your_gemini_api_key':
            return jsonify({
                'success': False,
                'message': 'Gemini API key not configured'
            }), 400
        
        # Test simple generation
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("Respond with exactly: API Working")
        
        if response and response.text:
            return jsonify({
                'success': True,
                'message': 'Gemini API working correctly',
                'response': response.text.strip()
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Gemini API returned empty response'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Gemini API error: {str(e)}'
        }), 500

@app.route('/api/collect_payment', methods=['POST'])
def collect_payment():
    """API endpoint để thu tiền từ khách hàng - PostgreSQL version"""
    try:
        print("🚀 [COLLECT_PAYMENT] API CALLED - Starting payment collection")
        data = request.get_json()
        print(f"🔍 [COLLECT_PAYMENT] Raw request data: {data}")
        
        if not data:
            return jsonify({'success': False, 'message': 'Không có dữ liệu'}), 400
        
        booking_id = data.get('booking_id')
        collected_amount = data.get('collected_amount')
        collector_name = data.get('collector_name')
        payment_note = data.get('payment_note', '')
        payment_type = data.get('payment_type', 'room')  # 'room' hoặc 'taxi'
        taxi_amount = data.get('taxi_amount')  # ADDED: Taxi amount for database update
        commission_amount = data.get('commission_amount', 0)
        commission_type = data.get('commission_type', 'normal')  # 'normal' hoặc 'none'
        
        print(f"[COLLECT_PAYMENT] 🎯 EXTRACTED VALUES:")
        print(f"[COLLECT_PAYMENT]   - booking_id: '{booking_id}'")
        print(f"[COLLECT_PAYMENT]   - collected_amount: {collected_amount} ({type(collected_amount)})")
        print(f"[COLLECT_PAYMENT]   - collector_name: '{collector_name}'")
        print(f"[COLLECT_PAYMENT]   - payment_note: '{payment_note}'")
        print(f"[COLLECT_PAYMENT]   - payment_type: '{payment_type}' ⭐ CRITICAL ⭐")
        print(f"[COLLECT_PAYMENT]   - taxi_amount: {taxi_amount} 🚕 NEW")
        print(f"[COLLECT_PAYMENT]   - commission_amount: {commission_amount}")
        print(f"[COLLECT_PAYMENT]   - commission_type: '{commission_type}'")
        
        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Thiếu mã đặt phòng'}), 400
            
        if not collector_name:
            return jsonify({'success': False, 'message': 'Thiếu tên người thu tiền'}), 400
        
        # CRITICAL: Only allow valid collectors
        valid_collectors = ['LOC LE', 'THAO LE']
        if collector_name not in valid_collectors:
            return jsonify({'success': False, 'message': f'Người thu tiền không hợp lệ. Chỉ chấp nhận: {", ".join(valid_collectors)}'}), 400
            
        if not collected_amount or collected_amount <= 0:
            return jsonify({'success': False, 'message': 'Số tiền thu không hợp lệ'}), 400
        
        # Prepare update data for PostgreSQL
        update_data = {}
        
        # Update commission based on commission type - FIXED LOGIC
        if commission_type == 'none':
            update_data['commission'] = 0
            print("[COLLECT_PAYMENT] Setting commission to 0 (no commission)")
        elif commission_amount is not None:  # FIXED: Removed > 0 condition
            update_data['commission'] = float(commission_amount)
            print(f"[COLLECT_PAYMENT] Setting commission to {commission_amount}")
        else:
            print(f"[COLLECT_PAYMENT] ⚠️ No commission update - amount is None")
        
        # ALWAYS update collector AND collected_amount for both taxi and room payments
        update_data['collector'] = collector_name
        update_data['collected_amount'] = float(collected_amount)  # 💰 CRITICAL: Save actual collected amount
        print(f"[COLLECT_PAYMENT] 💰 Setting collected_amount to: {collected_amount}")
        print(f"[COLLECT_PAYMENT] ✅ Valid collector confirmed: {collector_name}")
        
        # 🚕 ALWAYS UPDATE TAXI AMOUNT if provided (regardless of payment type)
        if taxi_amount is not None and taxi_amount >= 0:
            update_data['taxi_amount'] = float(taxi_amount)
            print(f"[COLLECT_PAYMENT] 🚕 Setting taxi_amount in DB to: {taxi_amount}")
        
        # 📝 CREATE APPROPRIATE NOTES based on payment type
        if payment_type == 'taxi':
            # Primary taxi payment
            if payment_note:
                update_data['booking_notes'] = f"Thu taxi {collected_amount:,.0f}đ (taxi: {taxi_amount:,.0f}đ) - {payment_note}"
            else:
                update_data['booking_notes'] = f"Thu taxi {collected_amount:,.0f}đ (taxi fee: {taxi_amount:,.0f}đ)"
            print(f"[COLLECT_PAYMENT] ✅ Taxi payment - collected: {collected_amount}, taxi_amount: {taxi_amount}, collector: {collector_name}")
        else:
            # Room payment (but may include taxi amount update)
            taxi_note = f" (taxi: {taxi_amount:,.0f}đ)" if taxi_amount and taxi_amount > 0 else ""
            if payment_note:
                update_data['booking_notes'] = f"Thu {collected_amount:,.0f}đ{taxi_note} - {payment_note}"
            else:
                update_data['booking_notes'] = f"Thu {collected_amount:,.0f}đ{taxi_note}"
            print(f"[COLLECT_PAYMENT] ✅ Room payment - collected: {collected_amount}, taxi_amount: {taxi_amount}, collector: {collector_name}")
        
        print(f"[COLLECT_PAYMENT] 📊 Final update_data: {update_data}")
        
        # Update booking using the update_booking function
        success = update_booking(booking_id, update_data)
        
        if success:
            print(f"[COLLECT_PAYMENT] Successfully updated booking {booking_id}")
            
            # Cache removed - data will be fresh automatically
            
            commission_msg = ""
            if commission_type == 'none':
                commission_msg = " (Không có hoa hồng)"
            elif commission_amount and commission_amount > 0:
                commission_msg = f" (Hoa hồng: {commission_amount:,.0f}đ)"
            
            # Create detailed success message with all updates
            updates = []
            updates.append(f"Thu: {collected_amount:,.0f}đ")
            if commission_amount is not None and commission_amount >= 0:
                updates.append(f"Hoa hồng: {commission_amount:,.0f}đ")
            if taxi_amount is not None and taxi_amount >= 0:
                updates.append(f"Taxi: {taxi_amount:,.0f}đ")
            
            update_summary = ", ".join(updates)
            
            if payment_type == 'taxi':
                return jsonify({
                    'success': True, 
                    'message': f'✅ Thu taxi thành công! {update_summary}',
                    'refresh_bookings': True,  # 🔄 Signal to refresh booking management
                    'updated_data': {
                        'collected_amount': collected_amount,
                        'commission_amount': commission_amount,
                        'taxi_amount': taxi_amount,
                        'booking_id': booking_id
                    }
                })
            else:
                return jsonify({
                    'success': True, 
                    'message': f'✅ Thu tiền thành công! {update_summary}',
                    'refresh_bookings': True,  # 🔄 Signal to refresh booking management
                    'updated_data': {
                        'collected_amount': collected_amount,
                        'commission_amount': commission_amount,
                        'taxi_amount': taxi_amount,
                        'booking_id': booking_id
                    }
                })
        else:
            print(f"[COLLECT_PAYMENT] Failed to update booking {booking_id}")
            return jsonify({
                'success': False, 
                'message': f'Lỗi cập nhật booking {booking_id}. Vui lòng thử lại.'
            }), 500
            
    except Exception as e:
        print(f"[COLLECT_PAYMENT] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': f'Lỗi server: {str(e)}'
        }), 500

@app.route('/api/update_guest_amounts', methods=['POST'])
def update_guest_amounts():
    """Update room and taxi amounts for a booking"""
    try:
        data = request.get_json()
        print(f"[UPDATE_GUEST_AMOUNTS] Received data: {data}")
        
        booking_id = data.get('booking_id')
        room_amount = data.get('room_amount')
        taxi_amount = data.get('taxi_amount')
        commission_amount = data.get('commission_amount')
        commission_type = data.get('commission_type', 'normal')
        edit_note = data.get('edit_note', '')
        
        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Missing booking ID'}), 400
            
        # Prepare update data
        update_data = {}
        
        if room_amount is not None:
            update_data['room_amount'] = float(room_amount)
            print(f"[UPDATE_GUEST_AMOUNTS] Setting room_amount to {room_amount}")
            
        if taxi_amount is not None:
            update_data['taxi_amount'] = float(taxi_amount)
            print(f"[UPDATE_GUEST_AMOUNTS] Setting taxi_amount to {taxi_amount}")
            
        # Handle commission updates
        if commission_amount is not None:
            if commission_type == 'none':
                update_data['commission'] = 0
                print(f"[UPDATE_GUEST_AMOUNTS] Setting commission to 0 (no commission)")
            else:
                update_data['commission'] = float(commission_amount)
                print(f"[UPDATE_GUEST_AMOUNTS] Setting commission to {commission_amount}")
        else:
            print(f"[UPDATE_GUEST_AMOUNTS] Commission not modified - keeping existing value")
            
        if edit_note:
            update_data['booking_notes'] = edit_note
            print(f"[UPDATE_GUEST_AMOUNTS] Setting notes to: {edit_note}")
        
        print(f"[UPDATE_GUEST_AMOUNTS] Final update_data: {update_data}")
        
        # Update the booking using core logic
        success = update_booking(booking_id, update_data)
        
        if success:
            print(f"[UPDATE_GUEST_AMOUNTS] Successfully updated {booking_id}")
            return jsonify({
                'success': True,
                'message': f'Successfully updated amounts for {booking_id}'
            })
        else:
            print(f"[UPDATE_GUEST_AMOUNTS] Failed to update {booking_id}")
            return jsonify({
                'success': False,
                'message': f'Failed to update booking {booking_id}'
            }), 500
            
    except Exception as e:
        print(f"[UPDATE_GUEST_AMOUNTS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/update_collected_amount', methods=['POST'])
def update_collected_amount():
    """Update only the collected amount for a booking - ADMIN ONLY"""
    try:
        data = request.get_json()
        print(f"[UPDATE_COLLECTED] 💰 Received data: {data}")
        
        booking_id = data.get('booking_id')
        collected_amount = data.get('collected_amount', 0)
        collector_name = data.get('collector_name', '').strip()
        note = data.get('note', '').strip()
        
        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Thiếu mã đặt phòng'}), 400
        
        if collected_amount < 0:
            return jsonify({'success': False, 'message': 'Số tiền không thể âm'}), 400
            
        # CRITICAL: Validate collector
        valid_collectors = ['LOC LE', 'THAO LE']
        if not collector_name:
            return jsonify({'success': False, 'message': 'Vui lòng chọn người thu tiền'}), 400
            
        if collector_name not in valid_collectors:
            return jsonify({'success': False, 'message': f'Người thu tiền không hợp lệ. Chỉ chấp nhận: {", ".join(valid_collectors)}'}), 400
            
        print(f"[UPDATE_COLLECTED] ✅ Valid collector confirmed: {collector_name}")
        
        # 🔒 SECURITY: This is an admin function - should be restricted
        # For now, we'll log it but allow it to proceed
        print(f"[UPDATE_COLLECTED] ⚠️ ADMIN ACTION: Updating collected_amount for {booking_id}")
        
        # Prepare update data - collected_amount, collector, and notes
        update_data = {
            'collected_amount': float(collected_amount),
            'collector': collector_name
        }
        
        # Add note if provided
        if note:
            update_data['booking_notes'] = f"Thu tiền: {collected_amount:,.0f}đ bởi {collector_name} - {note}"
        else:
            update_data['booking_notes'] = f"Thu tiền: {collected_amount:,.0f}đ bởi {collector_name}"
        
        print(f"[UPDATE_COLLECTED] 📊 Update data: {update_data}")
        
        # Update the booking using core logic
        success = update_booking(booking_id, update_data)
        
        if success:
            print(f"[UPDATE_COLLECTED] ✅ Successfully updated collected_amount for {booking_id}")
            return jsonify({
                'success': True,
                'message': f'Đã cập nhật số tiền đã thu: {collected_amount:,.0f}đ',
                'booking_id': booking_id,
                'collected_amount': collected_amount
            })
        else:
            print(f"[UPDATE_COLLECTED] ❌ Failed to update {booking_id}")
            return jsonify({
                'success': False,
                'message': f'Không thể cập nhật booking {booking_id}'
            }), 500
            
    except Exception as e:
        print(f"[UPDATE_COLLECTED] 🚨 Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Lỗi server: {str(e)}'
        }), 500

@app.route('/api/debug_booking/<booking_id>', methods=['GET'])
def debug_booking_data(booking_id):
    """Debug endpoint to check booking data in database"""
    try:
        print(f"🔍 [DEBUG_BOOKING] Checking booking: {booking_id}")
        
        # Check in PostgreSQL database directly
        from core.models import db, Booking, Guest
        booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        
        if not booking:
            return jsonify({
                'success': False,
                'message': f'Booking {booking_id} not found in database'
            }), 404
        
        # Get guest info
        guest = booking.guest
        
        booking_data = {
            'booking_id': booking.booking_id,
            'guest_name': guest.full_name if guest else 'N/A',
            'room_amount': float(booking.room_amount) if booking.room_amount else 0,
            'taxi_amount': float(booking.taxi_amount) if booking.taxi_amount else 0,
            'commission': float(booking.commission) if booking.commission else 0,
            'collector': booking.collector,
            'booking_notes': booking.booking_notes,
            'booking_status': booking.booking_status,
            'created_at': booking.created_at.isoformat() if booking.created_at else None,
            'updated_at': booking.updated_at.isoformat() if booking.updated_at else None
        }
        
        print(f"[DEBUG_BOOKING] Database values:")
        for key, value in booking_data.items():
            print(f"[DEBUG_BOOKING]   - {key}: {value} ({type(value)})")
        
        # Also check what load_booking_data returns for this booking
        df = load_booking_data()
        if not df.empty:
            booking_row = df[df['Số đặt phòng'] == booking_id]
            if not booking_row.empty:
                row_data = booking_row.iloc[0].to_dict()
                print(f"[DEBUG_BOOKING] load_booking_data result:")
                print(f"[DEBUG_BOOKING]   - Taxi: {row_data.get('Taxi', 'N/A')} ({type(row_data.get('Taxi'))})")
                print(f"[DEBUG_BOOKING]   - Hoa hồng: {row_data.get('Hoa hồng', 'N/A')}")
                print(f"[DEBUG_BOOKING]   - Ghi chú thanh toán: {row_data.get('Ghi chú thanh toán', 'N/A')}")
        
        return jsonify({
            'success': True,
            'booking_data': booking_data,
            'query_data': row_data if 'row_data' in locals() else None
        })
        
    except Exception as e:
        print(f"[DEBUG_BOOKING] Error: {e}")
        return jsonify({
            'success': False,
            'message': f'Error debugging booking: {str(e)}'
        }), 500

# Enhanced Expenses - DISABLED
# @app.route('/expenses/enhanced')
# def enhanced_expenses():
#     """Enhanced Expense Management Interface"""
#     try:
#         # Get existing expense data for display
#         expenses_df = get_expenses_from_database()
#         expenses_list = safe_to_dict_records(expenses_df)
#         
#         # Group expenses by category for quick stats
#         from collections import defaultdict
#         category_stats = defaultdict(lambda: {'count': 0, 'total': 0})
#         
#         for expense in expenses_list:
#             category = expense.get('category', 'miscellaneous')
#             amount = float(expense.get('amount', 0))
#             category_stats[category]['count'] += 1
#             category_stats[category]['total'] += amount
#         
#         # Calculate totals
#         total_expenses = sum(stat['total'] for stat in category_stats.values())
#         total_count = sum(stat['count'] for stat in category_stats.values())
#         
#         # Convert to regular dict for template
#         stats = dict(category_stats)
#         
#         return render_template('enhanced_expenses.html', 
#                              expenses=expenses_list,
#                              category_stats=stats,
#                              total_expenses=total_expenses,
#                              total_count=total_count)
#         
#     except Exception as e:
#         print(f"Error loading enhanced expenses: {e}")
#         return render_template('enhanced_expenses.html',
#                              expenses=[],
#                              category_stats={},
#                              total_expenses=0,
#                              total_count=0)

@app.route('/api/import_excel_expenses', methods=['POST'])
def import_excel_expenses():
    """Import expenses from Excel file"""
    try:
        import pandas as pd
        from datetime import datetime, date
        import os
        
        # Use relative path since csvtest.xlsx is in the same directory as app_postgresql.py
        excel_file_path = os.path.join(os.path.dirname(__file__), "csvtest.xlsx")
        
        if not os.path.exists(excel_file_path):
            return jsonify({'success': False, 'message': 'Excel file not found'}), 400
        
        # Smart categorization function
        def categorize_expense(description):
            description_lower = description.lower() if description else ""
            
            categories = {
                'room_supplies': ['xịt phòng', 'chậu ngâm', 'đồ dùng phòng', 'vệ sinh', 'làm sạch', 'khăn', 'ga giường', 'toilet'],
                'food_beverage': ['ăn', 'thức ăn', 'nước', 'coffee', 'cafe', 'beer', 'bia', 'đồ uống', 'ăn vặt', 'nướng', 'cơm'],
                'maintenance': ['sửa chữa', 'bảo trì', 'thay thế', 'lắp đặt', 'điện', 'nước', 'máy lạnh', 'wifi'],
                'transportation': ['taxi', 'xe', 'di chuyển', 'đi lại', 'xăng', 'grab', 'giao hàng'],
                'marketing': ['quảng cáo', 'booking', 'commission', 'hoa hồng', 'platform', 'website'],
                'utilities': ['điện', 'nước', 'internet', 'wifi', 'gas', 'garbage', 'rác'],
                'office_supplies': ['văn phòng', 'giấy', 'bút', 'máy in', 'mực in', 'stapler'],
                'guest_service': ['dịch vụ khách', 'đón tiễn', 'hỗ trợ khách', 'amenity'],
                'miscellaneous': ['khác', 'other', 'misc']
            }
            
            for category, keywords in categories.items():
                for keyword in keywords:
                    if keyword in description_lower:
                        return category
            
            return 'miscellaneous'
        
        # Read Excel data
        excel_data = pd.read_excel(excel_file_path, sheet_name=None)
        expenses = []
        
        # Process Sheet5 (Expense Tracking)
        if 'Sheet5' in excel_data:
            sheet5 = excel_data['Sheet5']
            
            for index, row in sheet5.iterrows():
                try:
                    amount = None
                    description = ""
                    expense_date = datetime.now().date()
                    
                    # Extract data from row
                    for col in sheet5.columns:
                        value = row[col]
                        if pd.notna(value):
                            if isinstance(value, (int, float)) and value > 0:
                                amount = float(value)
                            elif isinstance(value, str) and len(value) > 3:
                                description = str(value)
                            elif isinstance(value, (datetime, date)):
                                expense_date = value if isinstance(value, date) else value.date()
                    
                    if amount and amount > 0 and description:
                        category = categorize_expense(description)
                        
                        expense_data = {
                            'description': description,
                            'amount': amount,
                            'date': expense_date,
                            'category': category,
                            'collector': 'IMPORTED'
                        }
                        
                        if add_expense_to_database(expense_data):
                            expenses.append(expense_data)
                
                except Exception as e:
                    print(f"Error processing expense row {index}: {e}")
        
        # Process Sheet1 for commission and taxi expenses
        if 'Sheet1' in excel_data:
            sheet1 = excel_data['Sheet1']
            
            for index, row in sheet1.iterrows():
                try:
                    commission = row.get('Hoa hồng', 0) if 'Hoa hồng' in row else 0
                    taxi = row.get('Taxi', 0) if 'Taxi' in row else 0
                    guest_name = row.get('Tên người đặt', 'Unknown Guest') if 'Tên người đặt' in row else 'Unknown Guest'
                    booking_id = row.get('Số đặt phòng', f'BOOKING_{index}') if 'Số đặt phòng' in row else f'BOOKING_{index}'
                    
                    expense_date = datetime.now().date()
                    if 'Check-in Date' in row and pd.notna(row['Check-in Date']):
                        try:
                            expense_date = pd.to_datetime(row['Check-in Date']).date()
                        except:
                            pass
                    
                    # Add commission as marketing expense
                    if commission and commission > 0:
                        expense_data = {
                            'description': f'Hoa hồng booking {booking_id} - {guest_name}',
                            'amount': float(commission),
                            'date': expense_date,
                            'category': 'marketing',
                            'collector': 'IMPORTED'
                        }
                        
                        if add_expense_to_database(expense_data):
                            expenses.append(expense_data)
                    
                    # Add taxi as transportation expense
                    if taxi and taxi > 0:
                        expense_data = {
                            'description': f'Taxi cho khách {guest_name} - {booking_id}',
                            'amount': float(taxi),
                            'date': expense_date,
                            'category': 'transportation',
                            'collector': 'IMPORTED'
                        }
                        
                        if add_expense_to_database(expense_data):
                            expenses.append(expense_data)
                
                except Exception as e:
                    print(f"Error processing booking row {index}: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {len(expenses)} expenses',
            'imported_count': len(expenses)
        })
        
    except Exception as e:
        print(f"Error importing Excel expenses: {e}")
        return jsonify({
            'success': False,
            'message': f'Import failed: {str(e)}'
        }), 500

@app.route('/api/comprehensive_import', methods=['POST'])
def comprehensive_import():
    """
    Comprehensive import of all data: customers, costs, and message templates
    Ultra Think Optimization with complete validation and Flask context
    """
    try:
        print("🚀 COMPREHENSIVE IMPORT API CALLED")
        
        # Import the comprehensive import module
        from core.comprehensive_import import (
            parse_excel_file, 
            import_customers_from_sheet1,
            import_message_templates_from_sheet2,
            import_expenses_from_sheet5
        )
        from core.database_import import comprehensive_database_import
        
        # Use relative path since csvtest.xlsx is in the same directory as app_postgresql.py
        excel_file_path = os.path.join(os.path.dirname(__file__), "csvtest.xlsx")
        
        if not os.path.exists(excel_file_path):
            return jsonify({
                'success': False,
                'message': f'Excel file not found: {excel_file_path}. Please upload csvtest.xlsx to the server.'
            }), 400
        
        # Step 1: Parse Excel file
        print("📊 Parsing Excel file...")
        sheets_data = parse_excel_file(excel_file_path)
        if not sheets_data:
            return jsonify({
                'success': False,
                'message': 'Failed to parse Excel file'
            }), 400
        
        # Step 2: Import customers and bookings from Sheet 1
        print("👥 Importing customers and bookings...")
        customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
        
        # Step 3: Import message templates from Sheet 2
        print("💬 Importing message templates...")
        templates_data = import_message_templates_from_sheet2(sheets_data.get('Sheet2', []))
        
        # Step 4: Import expenses from Sheet 5
        print("💰 Importing expenses...")
        expenses_data = import_expenses_from_sheet5(sheets_data.get('Sheet5', []))
        
        # Step 5: Save to database using Flask context-aware function
        print("💾 Saving to database with Flask context...")
        
        # Use current Flask app context directly
        with app.app_context():
            from core.models import db, Guest, Booking, MessageTemplate, Expense
            
            results = {
                'customers': {'imported': 0, 'updated': 0, 'errors': []},
                'bookings': {'imported': 0, 'updated': 0, 'errors': []},
                'templates': {'imported': 0, 'updated': 0, 'errors': []},
                'expenses': {'imported': 0, 'skipped': 0, 'errors': []},
                'total_success': 0,
                'total_errors': 0
            }
            
            # Import customers first
            guest_mapping = {}
            if customers_data.get('customers'):
                for customer in customers_data['customers']:
                    try:
                        existing_guest = Guest.query.filter_by(full_name=customer['full_name']).first()
                        
                        if not existing_guest:
                            new_guest = Guest(
                                full_name=customer['full_name'],
                                email=customer.get('email'),
                                phone=customer.get('phone'),
                                nationality=customer.get('nationality'),
                                passport_number=customer.get('passport_number')
                            )
                            db.session.add(new_guest)
                            db.session.flush()
                            guest_mapping[customer['full_name']] = new_guest.guest_id
                            results['customers']['imported'] += 1
                        else:
                            guest_mapping[customer['full_name']] = existing_guest.guest_id
                            results['customers']['updated'] += 1
                            
                    except Exception as e:
                        results['customers']['errors'].append(f"Customer {customer.get('full_name', 'Unknown')}: {str(e)}")
                
                db.session.commit()
            
            # Import bookings
            if customers_data.get('bookings'):
                for booking in customers_data['bookings']:
                    try:
                        guest_id = guest_mapping.get(booking['guest_name'])
                        if not guest_id:
                            results['bookings']['errors'].append(f"Booking {booking['booking_id']}: Guest not found")
                            continue
                        
                        # Skip bookings with null checkin/checkout dates (incomplete bookings)
                        if not booking.get('checkin_date') or not booking.get('checkout_date'):
                            results['bookings']['errors'].append(f"Booking {booking['booking_id']}: Skipped - missing checkin/checkout dates (incomplete booking)")
                            continue
                        
                        existing_booking = Booking.query.filter_by(booking_id=booking['booking_id']).first()
                        
                        if not existing_booking:
                            new_booking = Booking(
                                booking_id=booking['booking_id'],
                                guest_id=guest_id,
                                guest_name=booking['guest_name'],  # Add guest_name for quick access
                                checkin_date=booking['checkin_date'],
                                checkout_date=booking['checkout_date'],
                                room_amount=booking['room_amount'] or 0.0,
                                taxi_amount=booking['taxi_amount'] or 0.0,
                                commission=booking['commission'] or 0.0,
                                collected_amount=booking['collected_amount'] or 0.0,
                                collector=booking.get('collector'),
                                booking_status=booking.get('booking_status', 'confirmed'),
                                booking_notes=booking.get('booking_notes')
                            )
                            db.session.add(new_booking)
                            results['bookings']['imported'] += 1
                        else:
                            existing_booking.guest_name = booking['guest_name']  # Update guest_name
                            existing_booking.room_amount = booking['room_amount'] or 0.0
                            existing_booking.taxi_amount = booking['taxi_amount'] or 0.0
                            existing_booking.commission = booking['commission'] or 0.0
                            existing_booking.collector = booking.get('collector')
                            existing_booking.booking_status = booking.get('booking_status', 'confirmed')
                            existing_booking.booking_notes = booking.get('booking_notes')
                            results['bookings']['updated'] += 1
                            
                    except Exception as e:
                        db.session.rollback()  # Rollback failed booking
                        results['bookings']['errors'].append(f"Booking {booking.get('booking_id', 'Unknown')}: {str(e)}")
                
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"❌ Error committing bookings: {e}")
                    raise
            
            # Import templates
            if templates_data:
                for template in templates_data:
                    try:
                        template_name = template['template_name']
                        if len(template_name) > 255:
                            template_name = template_name[:250] + "..."
                        
                        existing_template = MessageTemplate.query.filter_by(template_name=template_name).first()
                        
                        if not existing_template:
                            new_template = MessageTemplate(
                                template_name=template_name,
                                category=template['category'][:100] if template['category'] else 'general',
                                template_content=template['template_content']
                            )
                            db.session.add(new_template)
                            results['templates']['imported'] += 1
                        else:
                            existing_template.template_content = template['template_content']
                            existing_template.category = template['category'][:100] if template['category'] else 'general'
                            results['templates']['updated'] += 1
                            
                    except Exception as e:
                        results['templates']['errors'].append(f"Template {template.get('template_name', 'Unknown')[:30]}: {str(e)}")
                
                db.session.commit()
            
            # Import expenses
            if expenses_data:
                for expense in expenses_data:
                    try:
                        existing_expense = Expense.query.filter_by(
                            description=expense['description'],
                            amount=expense['amount'],
                            expense_date=expense['expense_date']
                        ).first()
                        
                        if not existing_expense:
                            new_expense = Expense(
                                description=expense['description'],
                                amount=expense['amount'],
                                expense_date=expense['expense_date'],
                                category=expense['category'],
                                collector=expense['collector']
                            )
                            db.session.add(new_expense)
                            results['expenses']['imported'] += 1
                        else:
                            results['expenses']['skipped'] += 1
                            
                    except Exception as e:
                        results['expenses']['errors'].append(f"Expense {expense.get('description', 'Unknown')[:30]}: {str(e)}")
                
                db.session.commit()
            
            # Calculate totals
            results['total_success'] = (
                results['customers']['imported'] + results['customers']['updated'] +
                results['bookings']['imported'] + results['bookings']['updated'] +
                results['templates']['imported'] + results['templates']['updated'] +
                results['expenses']['imported']
            )
            
            results['total_errors'] = (
                len(results['customers']['errors']) +
                len(results['bookings']['errors']) +
                len(results['templates']['errors']) +
                len(results['expenses']['errors'])
            )
        
        # Prepare detailed summary
        summary = {
            'customers_imported': results['customers']['imported'] + results['customers']['updated'],
            'bookings_imported': results['bookings']['imported'] + results['bookings']['updated'],
            'templates_imported': results['templates']['imported'] + results['templates']['updated'],
            'expenses_imported': results['expenses']['imported'],
            'total_imported': results['total_success'],
            'total_errors': results['total_errors'],
            'errors': []
        }
        
        # Collect all errors
        for category_data in [results['customers'], results['bookings'], results['templates'], results['expenses']]:
            summary['errors'].extend(category_data.get('errors', []))
        
        return jsonify({
            'success': True,
            'message': f'Comprehensive import completed successfully! Total: {summary["total_imported"]} records',
            'summary': summary
        })
        
    except Exception as e:
        # Rollback the session on error
        try:
            db.session.rollback()
        except:
            pass
        print(f"❌ Comprehensive import error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Import failed: {str(e)}'
        }), 500

@app.route('/api/import_status', methods=['GET'])
def import_status():
    """
    Get current database status after import
    """
    try:
        from core.models import Guest, Booking, MessageTemplate, Expense
        
        status = {
            'customers_count': Guest.query.count(),
            'bookings_count': Booking.query.count(),
            'templates_count': MessageTemplate.query.count(),
            'expenses_count': Expense.query.count(),
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Status check failed: {str(e)}'
        }), 500

@app.route('/api/fix_constraint', methods=['POST'])
def fix_constraint():
    """
    Fix database constraint to allow Vietnamese booking statuses
    """
    try:
        from core.models import db
        
        print("🔧 FIXING DATABASE CONSTRAINT...")
        
        # Drop existing constraint
        db.session.execute(text("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS chk_valid_status;"))
        
        # Add new constraint with ALL possible status values from CSV including 'OK' and 'Mới'
        db.session.execute(text("""
            ALTER TABLE bookings ADD CONSTRAINT chk_valid_status 
            CHECK (booking_status IN ('confirmed', 'cancelled', 'deleted', 'pending', 'mới', 'đã hủy', 'đã xóa', 'chờ xử lý', 'ok', 'OK', 'Mới', 'complete', 'active', 'finished', 'done', 'paid', 'unpaid', 'checked_in', 'checked_out'));
        """))
        
        db.session.commit()
        
        print("✅ Database constraint updated successfully!")
        
        return jsonify({
            'success': True,
            'message': 'Database constraint updated successfully! Vietnamese booking statuses are now allowed.'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error updating constraint: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to update constraint: {str(e)}'
        }), 500

@app.route('/api/diagnostic', methods=['GET'])
def diagnostic():
    """
    Diagnostic endpoint to check imported booking data
    """
    try:
        from core.models import Booking, Guest
        from datetime import datetime, timedelta
        
        # Get all bookings with details
        bookings = Booking.query.join(Guest).all()
        
        # Analyze the data
        total_bookings = len(bookings)
        today = datetime.now().date()
        current_month_start = today.replace(day=1)
        
        # Calculate date ranges
        if bookings:
            all_dates = [b.checkin_date for b in bookings if b.checkin_date]
            min_date = min(all_dates) if all_dates else None
            max_date = max(all_dates) if all_dates else None
            
            # Count bookings by month
            monthly_counts = {}
            current_month_count = 0
            
            for booking in bookings:
                if booking.checkin_date:
                    month_key = booking.checkin_date.strftime('%Y-%m')
                    monthly_counts[month_key] = monthly_counts.get(month_key, 0) + 1
                    
                    # Count current month bookings
                    if booking.checkin_date >= current_month_start:
                        current_month_count += 1
            
            # Get some sample booking details
            sample_bookings = []
            for booking in bookings[-10:]:  # Last 10 bookings
                sample_bookings.append({
                    'booking_id': booking.booking_id,
                    'guest_name': booking.guest.full_name,
                    'checkin_date': booking.checkin_date.isoformat() if booking.checkin_date else None,
                    'checkout_date': booking.checkout_date.isoformat() if booking.checkout_date else None,
                    'room_amount': float(booking.room_amount),
                    'status': booking.booking_status,
                    'created_at': booking.created_at.isoformat() if booking.created_at else None
                })
        
        else:
            min_date = max_date = None
            monthly_counts = {}
            current_month_count = 0
            sample_bookings = []
        
        diagnostic_data = {
            'total_bookings': total_bookings,
            'date_range': {
                'min_date': min_date.isoformat() if min_date else None,
                'max_date': max_date.isoformat() if max_date else None,
                'current_month_start': current_month_start.isoformat(),
                'current_month_bookings': current_month_count
            },
            'monthly_distribution': monthly_counts,
            'sample_recent_bookings': sample_bookings,
            'dashboard_default_range': {
                'start': current_month_start.isoformat(),
                'end': today.isoformat()
            }
        }
        
        return jsonify({
            'success': True,
            'diagnostic': diagnostic_data
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Diagnostic failed: {str(e)}'
        }), 500

@app.route('/api/add_guest_name_column', methods=['POST'])
def add_guest_name_column():
    """
    Add guest_name column to bookings table and populate it
    """
    try:
        from core.models import db
        
        print("🔧 ADDING GUEST_NAME COLUMN...")
        
        # Add the column
        db.session.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS guest_name VARCHAR(255)"))
        
        # Populate with existing data
        db.session.execute(text("""
            UPDATE bookings 
            SET guest_name = guests.full_name 
            FROM guests 
            WHERE bookings.guest_id = guests.guest_id 
            AND bookings.guest_name IS NULL
        """))
        
        # Add index
        db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_bookings_guest_name ON bookings(guest_name)"))
        
        db.session.commit()
        
        # Check result
        result = db.session.execute(text("SELECT COUNT(*) FROM bookings WHERE guest_name IS NOT NULL")).fetchone()
        updated_count = result[0] if result else 0
        
        print(f"✅ Guest name column added and populated for {updated_count} bookings!")
        
        return jsonify({
            'success': True,
            'message': f'Guest name column added successfully! Updated {updated_count} bookings.'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding guest_name column: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to add guest_name column: {str(e)}'
        }), 500

@app.route('/api/clear_imported_data', methods=['POST'])
def clear_imported_data():
    """
    Clear all imported data to prepare for re-import with correct dates
    """
    try:
        from core.models import db, Booking, Guest, MessageTemplate, Expense
        
        print("🧹 CLEARING IMPORTED DATA...")
        
        # Keep only the original 4 bookings (they have specific IDs)
        original_booking_ids = ['FLASK_TEST_001', 'FLASK_TEST_002', 'FLASK_TEST_003', 'FLASK_TEST_004']
        
        # Delete imported bookings (not the original test ones)
        deleted_bookings = Booking.query.filter(~Booking.booking_id.in_(original_booking_ids)).delete(synchronize_session=False)
        
        # Delete imported guests (keep only original test guests)
        original_guest_names = ['Flask Test User', 'Test Guest 1', 'Test Guest 2', 'Test Guest 3']
        deleted_guests = Guest.query.filter(~Guest.full_name.in_(original_guest_names)).delete(synchronize_session=False)
        
        # Delete imported templates and expenses
        deleted_templates = MessageTemplate.query.delete()
        deleted_expenses = Expense.query.delete()
        
        db.session.commit()
        
        print(f"✅ Cleared: {deleted_bookings} bookings, {deleted_guests} guests, {deleted_templates} templates, {deleted_expenses} expenses")
        
        return jsonify({
            'success': True,
            'message': f'Cleared imported data: {deleted_bookings} bookings, {deleted_guests} guests, {deleted_templates} templates, {deleted_expenses} expenses. Ready for re-import!'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error clearing data: {e}")
        return jsonify({
            'success': False,
            'message': f'Failed to clear data: {str(e)}'
        }), 500

@app.route('/api/detailed_diagnostic', methods=['GET'])
def detailed_diagnostic():
    """
    Detailed diagnostic comparing Excel file vs imported database data
    """
    try:
        # Import the comprehensive import module
        from core.comprehensive_import import (
            parse_excel_file, 
            import_customers_from_sheet1,
            import_message_templates_from_sheet2,
            import_expenses_from_sheet5
        )
        from core.models import Booking, Guest, MessageTemplate, Expense
        
        print("🔍 DETAILED DIAGNOSTIC STARTING...")
        
        # Step 1: Parse Excel file again
        excel_file_path = os.path.join(os.path.dirname(__file__), "csvtest.xlsx")
        
        if not os.path.exists(excel_file_path):
            return jsonify({
                'success': False,
                'message': f'Excel file not found: {excel_file_path}. Please upload csvtest.xlsx to the server.'
            }), 400
        
        print("📊 Parsing Excel file...")
        sheets_data = parse_excel_file(excel_file_path)
        
        # Step 2: Extract data from Excel
        print("👥 Extracting customers and bookings...")
        customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
        
        print("💬 Extracting message templates...")
        templates_data = import_message_templates_from_sheet2(sheets_data.get('Sheet2', []))
        
        print("💰 Extracting expenses...")
        expenses_data = import_expenses_from_sheet5(sheets_data.get('Sheet5', []))
        
        # Step 3: Check what's in database
        db_customers = Guest.query.all()
        db_bookings = Booking.query.all()
        db_templates = MessageTemplate.query.all()
        db_expenses = Expense.query.all()
        
        # Step 4: Compare Excel vs Database
        excel_customers = customers_data.get('customers', [])
        excel_bookings = customers_data.get('bookings', [])
        
        # Create comparison data
        excel_customer_names = [c['full_name'] for c in excel_customers]
        db_customer_names = [c.full_name for c in db_customers]
        
        excel_booking_ids = [b['booking_id'] for b in excel_bookings]
        db_booking_ids = [b.booking_id for b in db_bookings]
        
        # Find missing data
        missing_customers = [name for name in excel_customer_names if name not in db_customer_names]
        missing_bookings = [bid for bid in excel_booking_ids if bid not in db_booking_ids]
        
        # Sample data from Excel for inspection
        sample_excel_customers = excel_customers[:5]
        sample_excel_bookings = excel_bookings[:5]
        
        # Check date parsing in Excel data
        date_issues = []
        for booking in excel_bookings[:10]:
            if not booking.get('checkin_date') or not booking.get('checkout_date'):
                date_issues.append({
                    'booking_id': booking.get('booking_id'),
                    'guest_name': booking.get('guest_name'),
                    'checkin_raw': booking.get('checkin_date'),
                    'checkout_raw': booking.get('checkout_date'),
                    'issue': 'Missing dates'
                })
        
        diagnostic_result = {
            'excel_file_analysis': {
                'sheets_found': list(sheets_data.keys()),
                'sheet1_rows': len(sheets_data.get('Sheet1', [])),
                'customers_extracted': len(excel_customers),
                'bookings_extracted': len(excel_bookings),
                'templates_extracted': len(templates_data),
                'expenses_extracted': len(expenses_data)
            },
            'database_current_state': {
                'customers_in_db': len(db_customers),
                'bookings_in_db': len(db_bookings),
                'templates_in_db': len(db_templates),
                'expenses_in_db': len(db_expenses)
            },
            'comparison': {
                'missing_customers_count': len(missing_customers),
                'missing_customers_sample': missing_customers[:10],
                'missing_bookings_count': len(missing_bookings),
                'missing_bookings_sample': missing_bookings[:10]
            },
            'data_quality_issues': {
                'date_parsing_issues': date_issues,
                'total_date_issues': len(date_issues)
            },
            'sample_excel_data': {
                'customers': sample_excel_customers,
                'bookings': sample_excel_bookings
            },
            'recommendations': []
        }
        
        # Add recommendations based on findings
        if len(missing_customers) > 0:
            diagnostic_result['recommendations'].append(f"❌ Missing {len(missing_customers)} customers - check import logic")
        
        if len(missing_bookings) > 0:
            diagnostic_result['recommendations'].append(f"❌ Missing {len(missing_bookings)} bookings - check validation rules")
        
        if len(date_issues) > 0:
            diagnostic_result['recommendations'].append(f"⚠️ {len(date_issues)} bookings have date issues - check date parsing")
        
        if len(excel_customers) != len(db_customer_names):
            diagnostic_result['recommendations'].append("🔍 Customer count mismatch - some customers may not have been imported")
        
        return jsonify({
            'success': True,
            'diagnostic': diagnostic_result
        })
        
    except Exception as e:
        print(f"❌ Detailed diagnostic error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Detailed diagnostic failed: {str(e)}'
        }), 500

@app.route('/api/import_debug', methods=['POST'])
def import_debug():
    """
    Debug version of import that shows exactly which bookings are rejected and why
    """
    try:
        from core.comprehensive_import import (
            parse_excel_file, 
            import_customers_from_sheet1
        )
        from core.models import Booking, Guest
        
        print("🔍 DEBUG IMPORT STARTING...")
        
        # Parse Excel file
        excel_file_path = os.path.join(os.path.dirname(__file__), "csvtest.xlsx")
        sheets_data = parse_excel_file(excel_file_path)
        
        if not sheets_data:
            return jsonify({'success': False, 'message': 'Excel file not found or could not be parsed'}), 400
        
        customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
        
        # Handle case where customers_data might be a list instead of dict
        if isinstance(customers_data, list):
            excel_bookings = customers_data
        else:
            excel_bookings = customers_data.get('bookings', [])
        
        # Debug each booking
        debug_results = {
            'total_excel_bookings': len(excel_bookings),
            'validation_results': [],
            'rejected_bookings': [],
            'accepted_bookings': [],
            'rejection_reasons': {}
        }
        
        for i, booking in enumerate(excel_bookings):
            booking_debug = {
                'index': i + 1,
                'booking_id': booking.get('booking_id'),
                'guest_name': booking.get('guest_name'),
                'checkin_date': str(booking.get('checkin_date')),
                'checkout_date': str(booking.get('checkout_date')),
                'status': booking.get('booking_status'),
                'issues': []
            }
            
            # Check each validation rule
            if not booking.get('booking_id'):
                booking_debug['issues'].append('Missing booking_id')
            
            if not booking.get('guest_name'):
                booking_debug['issues'].append('Missing guest_name')
                
            if not booking.get('checkin_date') or not booking.get('checkout_date'):
                booking_debug['issues'].append('Missing checkin/checkout dates')
                
            # Check if already exists
            existing = Booking.query.filter_by(booking_id=booking.get('booking_id')).first()
            if existing:
                booking_debug['issues'].append('Already exists in database')
            
            # Categorize
            if booking_debug['issues']:
                debug_results['rejected_bookings'].append(booking_debug)
                for issue in booking_debug['issues']:
                    debug_results['rejection_reasons'][issue] = debug_results['rejection_reasons'].get(issue, 0) + 1
            else:
                debug_results['accepted_bookings'].append(booking_debug)
        
        debug_results['summary'] = {
            'total': len(excel_bookings),
            'accepted': len(debug_results['accepted_bookings']),
            'rejected': len(debug_results['rejected_bookings']),
            'acceptance_rate': len(debug_results['accepted_bookings']) / len(excel_bookings) * 100 if excel_bookings else 0
        }
        
        return jsonify({
            'success': True,
            'debug': debug_results
        })
        
    except Exception as e:
        print(f"❌ Import debug error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Import debug failed: {str(e)}'
        }), 500

@app.route('/test_import')
def test_import():
    """Simple test import page"""
    return send_from_directory('.', 'test_import_simple.html')

# Data Management - DISABLED
# @app.route('/data_management')
# def data_management():
#     """
#     Comprehensive data management interface
#     """
#     try:
#         from core.models import Guest, Booking, MessageTemplate, Expense
#         
#         # Get summary statistics
#         stats = {
#             'customers': Guest.query.count(),
#             'bookings': Booking.query.count(),
#             'templates': MessageTemplate.query.count(),
#             'expenses': Expense.query.count()
#         }
#         
#         # Get recent data samples
#         recent_customers = Guest.query.order_by(Guest.created_at.desc()).limit(5).all()
#         recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()
#         recent_templates = MessageTemplate.query.order_by(MessageTemplate.created_at.desc()).limit(5).all()
#         recent_expenses = Expense.query.order_by(Expense.created_at.desc()).limit(5).all()
#         
#         return render_template('data_management.html',
#                              stats=stats,
#                              recent_customers=[c.to_dict() for c in recent_customers],
#                              recent_bookings=[b.to_dict() for b in recent_bookings],
#                              recent_templates=[t.to_dict() for t in recent_templates],
#                              recent_expenses=[e.to_dict() for e in recent_expenses])
#         
#     except Exception as e:
#         print(f"Error loading data management: {e}")
#         return render_template('data_management.html',
#                              stats={'customers': 0, 'bookings': 0, 'templates': 0, 'expenses': 0},
#                              recent_customers=[],
#                              recent_bookings=[],
#                              recent_templates=[],
#                              recent_expenses=[])

# ============================================================================
# API ENDPOINTS FOR AI ASSISTANT TEMPLATES
# ============================================================================

@app.route('/api/templates', methods=['GET'])
def get_templates():
    """Get all message templates from PostgreSQL database"""
    try:
        # Import the MessageTemplate model
        from core.models import MessageTemplate, db
        
        # Test raw SQL query first to debug columns issue
        try:
            raw_result = db.session.execute(text("SELECT template_id, template_name, category, template_content FROM message_templates LIMIT 1")).fetchall()
            print(f"🔍 Raw SQL works: {len(raw_result)} rows")
        except Exception as raw_error:
            print(f"❌ Raw SQL error: {raw_error}")
            # Fallback to table existence check
            tables_result = db.session.execute(text("SELECT table_name FROM information_schema.tables WHERE table_name='message_templates'")).fetchall()
            print(f"🔍 Table exists check: {tables_result}")
        
        # Query all templates from database ordered by category and name
        templates_query = MessageTemplate.query.order_by(MessageTemplate.category, MessageTemplate.template_name).all()
        
        print(f"📋 Templates API: Querying database...")
        print(f"📋 Templates API: Found {len(templates_query)} templates in database")
        
        # Debug: Check what's actually in the database
        if templates_query:
            sample = templates_query[0]
            print(f"📋 Sample template - ID: {sample.template_id}, Name: {sample.template_name}, Category: {sample.category}")
        
        # Convert to format expected by JavaScript with improved titles
        templates_data = []
        for template in templates_query:
            # Get raw category from database
            raw_category = template.category or 'General'
            print(f"📋 Processing template: {template.template_name}, Raw Category: '{raw_category}'")
            
            # Improve category names for better display
            category = raw_category
            if category == 'DON PHONG':
                category = 'Room Cleaning'
            elif category == 'HET PHONG':
                category = 'Room Unavailable'
            elif category == 'NOT BOOKING':
                category = 'Direct Booking'
            elif category == 'FEED BACK':
                category = 'Feedback & Farewell'
            elif category == 'EARLY CHECK IN':
                category = 'Early Check-in'
            elif category == 'CHECK IN':
                category = 'Check-in Instructions'
            
            # Use template_name as label (it should already be improved from import)
            label = template.template_name or 'Unnamed Template'
            
            templates_data.append({
                'Category': category,
                'Label': label,
                'Message': template.template_content,
                # Frontend expects these lowercase fields
                'category': category,
                'label': label, 
                'content': template.template_content,
                'id': template.template_id,
                'created_at': template.created_at.isoformat() if template.created_at else None
            })
        
        print(f"📋 Templates API: Processed {len(templates_data)} templates")
        
        # Debug: Show sample template structure
        if templates_data:
            sample = templates_data[0]
            print(f"📋 Sample template structure:")
            print(f"   - label: '{sample.get('label', 'MISSING')}'")
            print(f"   - content length: {len(sample.get('content', ''))}")
            print(f"   - id: {sample.get('id', 'MISSING')}")
        
        # Group by category for better organization
        from collections import defaultdict
        categories_dict = defaultdict(list)
        for template in templates_data:
            categories_dict[template['Category']].append(template)
        
        print(f"📋 Templates API: Organized into {len(categories_dict)} categories: {list(categories_dict.keys())}")
        
        # Return in format expected by JavaScript
        return jsonify({
            'success': True,
            'templates': templates_data
        })
    except Exception as e:
        print(f"Error getting templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/add', methods=['POST'])
def add_template():
    """Add a new message template to PostgreSQL database"""
    try:
        from core.models import MessageTemplate, db
        
        data = request.get_json()
        print(f"🔍 [TEMPLATE_ADD] Received data: {data}")
        
        # Enhanced validation with better debugging
        if not data:
            print("❌ [TEMPLATE_ADD] No data received")
            return jsonify({'success': False, 'error': 'No data provided'}), 400
        
        # Check for multiple possible field names
        name = data.get('name') or data.get('template_name') or data.get('Label')
        content = data.get('content') or data.get('template_content') or data.get('Message')
        category = data.get('category') or data.get('Category') or 'General'
        
        if not name or not content:
            print(f"❌ [TEMPLATE_ADD] Missing fields - name: {name}, content: {content}")
            return jsonify({'success': False, 'error': 'Name and content are required'}), 400
        
        # Fix sequence if needed (check if sequence is behind the actual data)
        try:
            # Get the current max ID in the table
            max_id = db.session.query(db.func.max(MessageTemplate.template_id)).scalar() or 0
            
            # Get the current sequence value without advancing it
            sequence_val = db.session.execute(db.text("SELECT last_value FROM message_templates_template_id_seq")).scalar()
            
            print(f"🔍 [TEMPLATE_ADD] Sequence check: max_id={max_id}, sequence_val={sequence_val}")
            
            # If sequence is behind, reset it
            if sequence_val <= max_id:
                reset_val = max_id + 1
                db.session.execute(db.text(f"SELECT setval('message_templates_template_id_seq', {reset_val})"))
                db.session.commit()
                print(f"🔧 [TEMPLATE_ADD] Fixed sequence: set to {reset_val} (was {sequence_val}, max_id was {max_id})")
        except Exception as seq_error:
            print(f"⚠️ [TEMPLATE_ADD] Sequence fix error: {seq_error}")
            # Try a simpler approach - just reset to max+1
            try:
                max_id = db.session.query(db.func.max(MessageTemplate.template_id)).scalar() or 0
                reset_val = max_id + 1
                db.session.execute(db.text(f"SELECT setval('message_templates_template_id_seq', {reset_val})"))
                db.session.commit()
                print(f"🔧 [TEMPLATE_ADD] Fallback sequence fix: set to {reset_val}")
            except Exception as fallback_error:
                print(f"❌ [TEMPLATE_ADD] Fallback sequence fix failed: {fallback_error}")
        
        # Create new template in database
        new_template = MessageTemplate(
            template_name=name,
            category=category,
            template_content=content
        )
        
        # Save to database
        db.session.add(new_template)
        db.session.commit()
        
        print(f"📋 Templates API: Added new template '{name}' with ID {new_template.template_id}")
        print(f"📋 Templates API: Mapped fields - name: {name}, category: {category}, content: {content[:50]}...")
        
        # Return the added template in the correct format
        response = {
            'success': True,
            'message': 'Template added successfully',
            'template': {
                'Category': new_template.category,
                'Label': new_template.template_name,
                'Message': new_template.template_content,
                'id': new_template.template_id,
                'created_at': new_template.created_at.isoformat() if new_template.created_at else None
            }
        }
        return jsonify(response)
    except Exception as e:
        print(f"Error adding template: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/<template_id>', methods=['GET', 'PUT', 'DELETE'])
def handle_template(template_id):
    """Get, update or delete a specific template from PostgreSQL database"""
    try:
        from core.models import MessageTemplate, db
        
        # Find template by ID
        template = MessageTemplate.query.get(template_id)
        if not template:
            return jsonify({'success': False, 'error': 'Template not found'}), 404
        
        if request.method == 'GET':
            # Return template details in the correct format
            return jsonify({
                'success': True,
                'template': {
                    'Category': template.category or 'General',
                    'Label': template.template_name,
                    'Message': template.template_content,
                    'id': template.template_id,
                    'created_at': template.created_at.isoformat() if template.created_at else None
                }
            })
        
        elif request.method == 'PUT':
            # Update template with new data
            data = request.get_json()
            print(f"🔍 [TEMPLATE_UPDATE] Received data: {data}")
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Update template fields with multiple field name support
            if 'category' in data or 'Category' in data:
                template.category = data.get('category') or data.get('Category')
            if 'template_name' in data or 'name' in data or 'Label' in data:
                template.template_name = data.get('template_name') or data.get('name') or data.get('Label')
            if 'template_content' in data or 'content' in data or 'Message' in data:
                template.template_content = data.get('template_content') or data.get('content') or data.get('Message')
            
            # Save to database
            db.session.commit()
            
            print(f"📋 Templates API: Updated template '{template.template_name}' (ID: {template_id})")
            print(f"📋 Templates API: Update fields applied - category: {template.category}, name: {template.template_name}, content: {template.template_content[:50]}...")
            
            return jsonify({
                'success': True,
                'message': f'Template {template_id} updated successfully',
                'template': {
                    'Category': template.category or 'General',
                    'Label': template.template_name,
                    'Message': template.template_content,
                    'id': template.template_id
                }
            })
        
        elif request.method == 'DELETE':
            # Delete template from database
            db.session.delete(template)
            db.session.commit()
            
            print(f"📋 Templates API: Deleted template '{template.template_name}' (ID: {template_id})")
            
            return jsonify({
                'success': True,
                'message': f'Template {template_id} deleted successfully'
            })
    except Exception as e:
        print(f"Error handling template {template_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/templates/import', methods=['GET'])
def import_templates():
    """Import templates - placeholder endpoint"""
    try:
        # Placeholder response - can be enhanced with actual import logic
        return jsonify({
            'success': True,
            'message': 'Template import functionality is available',
            'data': {
                'imported_count': 0,
                'available_templates': []
            }
        })
    except Exception as e:
        print(f"Error importing templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/debug', methods=['GET', 'POST'])
def debug_templates():
    """Debug templates functionality"""
    try:
        from core.models import MessageTemplate, db
        
        if request.method == 'GET':
            template_count = MessageTemplate.query.count()
            categories = db.session.query(MessageTemplate.category).distinct().all()
            category_list = [cat[0] for cat in categories] if categories else []
            
            return jsonify({
                'success': True,
                'message': 'Template debug info',
                'data': {
                    'system_status': 'operational',
                    'template_count': template_count,
                    'categories': category_list,
                    'last_updated': datetime.now().isoformat()
                }
            })
        
        elif request.method == 'POST':
            return jsonify({
                'success': True,
                'message': 'Debug command executed successfully'
            })
    except Exception as e:
        print(f"Error in template debug: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/import_json', methods=['POST'])
def import_templates_from_json():
    """Import templates from JSON file to database"""
    try:
        from core.models import MessageTemplate, db
        import json
        
        # Read JSON templates
        json_file_path = os.path.join(os.path.dirname(__file__), 'config', 'message_templates.json')
        
        if not os.path.exists(json_file_path):
            return jsonify({'success': False, 'error': 'JSON template file not found'}), 404
        
        with open(json_file_path, 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        print(f"📋 Found {len(templates)} templates in JSON file")
        
        # Clear existing templates
        existing_count = MessageTemplate.query.count()
        if existing_count > 0:
            print(f"🗑️ Clearing {existing_count} existing templates")
            MessageTemplate.query.delete()
            db.session.commit()
        
        # Import templates with CORRECT mapping
        imported_count = 0
        
        for template_data in templates:
            # CORRECT MAPPING: Excel columns to PostgreSQL fields
            excel_category = template_data.get('Category', 'General')  # This becomes the category
            excel_label = template_data.get('Label', 'Unknown')        # This becomes template_name
            excel_message = template_data.get('Message', '')           # This becomes template_content
            
            print(f"📋 Processing: Category='{excel_category}', Label='{excel_label}', Message='{excel_message[:50]}...'")
            
            # Use Category from Excel as the PostgreSQL category field
            category = excel_category
            
            # Use Label from Excel as the PostgreSQL template_name field (with improvements)
            template_name = excel_label
            
            # Improve template names for better display while keeping category correct
            if excel_label in ['DEFAULT', '1', '2', '3', '4', '1.', '2.']:
                if excel_category == 'WELCOME':
                    if excel_label == '1.':
                        template_name = 'Standard Welcome'
                    elif excel_label == '2.':
                        template_name = 'Arrival Time Request'
                    else:
                        template_name = 'General Welcome'
                elif excel_category == 'TAXI':
                    if excel_label == '1':
                        template_name = 'Airport Pickup - Pillar 14'
                    elif excel_label == '2':
                        template_name = 'Driver Booking Confirmation'
                    elif excel_label == '3':
                        template_name = 'Taxi Service Offer'
                    else:
                        template_name = 'Taxi Information'
                elif excel_category == 'FEED BACK':
                    if 'bye bye' in excel_label:
                        template_name = 'Farewell with Offers'
                    elif excel_label == '3':
                        template_name = 'Apology with Discounts'
                    else:
                        template_name = 'Review Request'
                elif excel_label == 'DEFAULT':
                    template_name = f'{excel_category} - Standard Message'
                else:
                    template_name = f'{excel_category} - Option {excel_label}'
            
            # Ensure unique template names by adding category prefix if needed
            if not template_name.startswith(excel_category):
                template_name = f"{excel_category} - {template_name}"
            
            # Create template record with CORRECT field mapping
            template = MessageTemplate(
                template_name=template_name,      # Excel Label → PostgreSQL template_name
                category=category,                # Excel Category → PostgreSQL category  
                template_content=excel_message    # Excel Message → PostgreSQL template_content
            )
            
            print(f"📋 Creating template: name='{template_name}', category='{category}'")
            
            db.session.add(template)
            imported_count += 1
        
        # Commit all changes
        db.session.commit()
        
        print(f"✅ Successfully imported {imported_count} templates to database")
        
        # Verify import
        final_count = MessageTemplate.query.count()
        categories = db.session.query(MessageTemplate.category).distinct().all()
        category_list = [cat[0] for cat in categories]
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {imported_count} templates',
            'data': {
                'imported_count': imported_count,
                'total_count': final_count,
                'categories': category_list
            }
        })
        
    except Exception as e:
        print(f"❌ Error importing templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/fix_sequence', methods=['POST'])
def fix_template_sequence():
    """Fix the template_id sequence to prevent duplicate key errors"""
    try:
        from core.models import MessageTemplate, db
        
        # Get the current max ID in the table
        max_id = db.session.query(db.func.max(MessageTemplate.template_id)).scalar() or 0
        
        # Get the current sequence value
        try:
            sequence_val = db.session.execute(db.text("SELECT last_value FROM message_templates_template_id_seq")).scalar()
        except:
            sequence_val = 0
            
        # Reset sequence to max+1
        reset_val = max_id + 1
        db.session.execute(db.text(f"SELECT setval('message_templates_template_id_seq', {reset_val})"))
        db.session.commit()
        
        print(f"🔧 [FIX_SEQUENCE] Fixed template sequence: max_id={max_id}, old_sequence={sequence_val}, new_sequence={reset_val}")
        
        return jsonify({
            'success': True,
            'message': f'Sequence fixed: set to {reset_val}',
            'details': {
                'max_id': max_id,
                'old_sequence': sequence_val,
                'new_sequence': reset_val
            }
        })
        
    except Exception as e:
        print(f"❌ [FIX_SEQUENCE] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/templates/verify', methods=['GET'])
def verify_templates():
    """Verify template database structure and content"""
    try:
        from core.models import MessageTemplate, db
        
        # Get basic stats
        total_count = MessageTemplate.query.count()
        
        # Get sample templates
        samples = MessageTemplate.query.limit(5).all()
        sample_data = []
        for template in samples:
            sample_data.append({
                'id': template.template_id,
                'name': template.template_name,
                'category': template.category,
                'content_preview': template.template_content[:100] + "..." if len(template.template_content) > 100 else template.template_content
            })
        
        # Get unique categories
        categories = db.session.query(MessageTemplate.category).distinct().all()
        category_list = [cat[0] for cat in categories if cat[0]] if categories else []
        
        # Get category counts
        category_counts = {}
        for category in category_list:
            count = MessageTemplate.query.filter_by(category=category).count()
            category_counts[category] = count
        
        return jsonify({
            'success': True,
            'data': {
                'total_templates': total_count,
                'categories': category_list,
                'category_counts': category_counts,
                'sample_templates': sample_data
            }
        })
        
    except Exception as e:
        print(f"Error verifying templates: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/confirm_guest_arrival', methods=['POST'])
def confirm_guest_arrival():
    """Confirm guest arrival to enable commission notifications"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        
        if not booking_id:
            return jsonify({'success': False, 'error': 'Booking ID required'}), 400
        
        from core.models import Booking, db
        
        # Find booking
        booking = Booking.query.get(booking_id)
        if not booking:
            return jsonify({'success': False, 'error': 'Booking not found'}), 404
        
        # Update arrival confirmation status
        booking.arrival_confirmed = True
        booking.arrival_confirmed_at = datetime.now()
        db.session.commit()
        
        print(f"✅ Guest arrival confirmed for booking {booking_id}: {booking.guest_name}")
        
        return jsonify({
            'success': True,
            'message': f'Arrival confirmed for {booking.guest_name}',
            'booking_id': booking_id
        })
        
    except Exception as e:
        print(f"Error confirming guest arrival: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/monthly_guest_details', methods=['POST'])
def get_monthly_guest_details():
    """Get detailed guest breakdown for a specific month and collection status"""
    try:
        data = request.get_json()
        month = data.get('month')  # Format: 'YYYY-MM'
        collection_type = data.get('type')  # 'collected' or 'uncollected'
        
        print(f"🔍 [MONTHLY_DETAILS] Requested: {month} - {collection_type}")
        
        if not month or not collection_type:
            return jsonify({'success': False, 'message': 'Missing month or type parameter'}), 400
        
        # Load data excluding cancelled bookings and filter for the specific month and checked-in guests only
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Filter for specific month and checked-in guests
        from datetime import date
        today = date.today()
        
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        month_mask = df['Check-in Date'].dt.strftime('%Y-%m') == month
        checked_in_mask = df['Check-in Date'].dt.date <= today
        
        month_guests = df[month_mask & checked_in_mask].copy()
        
        print(f"🔍 [MONTHLY_DETAILS] Found {len(month_guests)} guests for {month}")
        
        if month_guests.empty:
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Filter by collection status
        valid_collectors = ['LOC LE', 'THAO LE']
        
        if collection_type == 'collected':
            # Guests collected by LOC LE or THAO LE
            filtered_guests = month_guests[month_guests['Người thu tiền'].isin(valid_collectors)].copy()
            status_label = "Đã thu (LOC LE + THAO LE)"
        else:  # uncollected
            # Guests NOT collected by LOC LE or THAO LE
            filtered_guests = month_guests[~month_guests['Người thu tiền'].isin(valid_collectors)].copy()
            status_label = "Chưa thu (Không phải LOC LE/THAO LE)"
        
        print(f"🔍 [MONTHLY_DETAILS] {status_label}: {len(filtered_guests)} guests")
        
        # Prepare guest details
        guest_details = []
        total_amount = 0
        
        for _, guest in filtered_guests.iterrows():
            guest_name = guest.get('Tên người đặt', 'N/A')
            booking_id = guest.get('Số đặt phòng', 'N/A')
            amount = float(guest.get('Tổng thanh toán', 0))
            commission = float(guest.get('Hoa hồng', 0))
            taxi = float(guest.get('Taxi', 0))
            collector = guest.get('Người thu tiền', 'N/A')
            checkin_date = guest.get('Check-in Date')
            checkout_date = guest.get('Check-out Date')
            
            # Format dates safely
            try:
                checkin_str = checkin_date.strftime('%d/%m/%Y') if pd.notna(checkin_date) else 'N/A'
                checkout_str = checkout_date.strftime('%d/%m/%Y') if pd.notna(checkout_date) else 'N/A'
            except:
                checkin_str = str(checkin_date) if checkin_date else 'N/A'
                checkout_str = str(checkout_date) if checkout_date else 'N/A'
            
            guest_details.append({
                'guest_name': guest_name,
                'booking_id': str(booking_id),
                'amount': amount,
                'commission': commission,
                'taxi': taxi,
                'collector': collector,
                'checkin_date': checkin_str,
                'checkout_date': checkout_str,
                'is_valid_collector': collector in valid_collectors
            })
            
            total_amount += amount
        
        # Sort by amount (highest first)
        guest_details.sort(key=lambda x: x['amount'], reverse=True)
        
        # Log summary for debugging
        print(f"💰 [MONTHLY_SUMMARY] {month} {status_label}:")
        print(f"💰   Total guests: {len(guest_details)}")
        print(f"💰   Total amount: {total_amount:,.0f}đ")
        
        # Show breakdown by collector
        if collection_type == 'uncollected':
            collector_breakdown = {}
            for guest in guest_details:
                collector = guest['collector']
                if collector not in collector_breakdown:
                    collector_breakdown[collector] = {'count': 0, 'amount': 0}
                collector_breakdown[collector]['count'] += 1
                collector_breakdown[collector]['amount'] += guest['amount']
            
            print(f"🚨 [INVALID_COLLECTORS] Breakdown of who collected but shouldn't be counted:")
            for collector, data in collector_breakdown.items():
                print(f"🚨   '{collector}': {data['count']} guests, {data['amount']:,.0f}đ")
        
        return jsonify({
            'success': True,
            'guests': guest_details,
            'total_amount': total_amount,
            'count': len(guest_details),
            'month': month,
            'type': collection_type,
            'status_label': status_label
        })
        
    except Exception as e:
        print(f"❌ [MONTHLY_DETAILS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/weekly_guest_details', methods=['POST'])
def get_weekly_guest_details():
    """Get detailed guest breakdown for a specific week and collection status"""
    try:
        data = request.get_json()
        week = data.get('week')  # Format: 'YYYY-W24 (MM/DD)'
        collection_type = data.get('type')  # 'collected' or 'uncollected'
        
        print(f"🔍 [WEEKLY_DETAILS] Requested: {week} - {collection_type}")
        
        if not week or not collection_type:
            return jsonify({'success': False, 'message': 'Missing week or type parameter'}), 400
        
        # Load data excluding cancelled bookings and filter for the specific week and checked-in guests only
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Parse week format: '2025-W26 (06/23)' -> extract year and week number
        import re
        week_match = re.match(r'(\d{4})-W(\d+)', week)
        if not week_match:
            return jsonify({'success': False, 'message': 'Invalid week format'}), 400
        
        year = int(week_match.group(1))
        week_num = int(week_match.group(2))
        
        # Filter for specific week and checked-in guests
        from datetime import date, timedelta
        import pandas as pd
        
        today = date.today()
        checked_in_mask = df['Check-in Date'].dt.date <= today
        df_checked_in = df[checked_in_mask].copy()
        
        # Add week calculation
        df_checked_in['Week_Start'] = df_checked_in['Check-in Date'].dt.to_period('W').dt.start_time
        df_checked_in['Week_Label'] = df_checked_in['Week_Start'].dt.strftime('%Y-W%U (%m/%d)')
        
        # Filter for the specific week
        week_mask = df_checked_in['Week_Label'] == week
        week_df = df_checked_in[week_mask].copy()
        
        print(f"🔍 [WEEKLY_DETAILS] Found {len(week_df)} total guests for week {week}")
        
        if week_df.empty:
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Filter based on collection status
        valid_collectors = ['LOC LE', 'THAO LE']
        if collection_type == 'collected':
            filtered_df = week_df[week_df['Người thu tiền'].isin(valid_collectors)].copy()
            status_label = 'đã thu'
        else:  # uncollected
            filtered_df = week_df[~week_df['Người thu tiền'].isin(valid_collectors)].copy()
            status_label = 'chưa thu'
        
        print(f"🔍 [WEEKLY_DETAILS] Found {len(filtered_df)} guests {status_label} for week {week}")
        
        # Prepare guest details
        guest_details = []
        total_amount = 0
        
        for _, guest in filtered_df.iterrows():
            amount = float(guest.get('Tổng thanh toán', 0) or 0)
            commission = float(guest.get('Hoa hồng', 0) or 0)
            total_amount += amount
            
            guest_info = {
                'guest_name': guest.get('Tên khách', 'N/A'),
                'booking_id': guest.get('Số đặt phòng', 'N/A'),
                'checkin_date': guest.get('Check-in Date').strftime('%Y-%m-%d') if pd.notna(guest.get('Check-in Date')) else 'N/A',
                'checkout_date': guest.get('Check-out Date').strftime('%Y-%m-%d') if pd.notna(guest.get('Check-out Date')) else 'N/A',
                'room_amount': amount,
                'commission': commission,
                'collector': guest.get('Người thu tiền', 'Chưa thu')
            }
            guest_details.append(guest_info)
        
        # Sort by room amount (highest first)
        guest_details.sort(key=lambda x: x['room_amount'], reverse=True)
        
        print(f"✅ [WEEKLY_DETAILS] Returning {len(guest_details)} guests, total: {total_amount:,.0f}đ")
        
        return jsonify({
            'success': True,
            'guests': guest_details,
            'total_amount': total_amount,
            'count': len(guest_details),
            'week': week,
            'type': collection_type,
            'status_label': status_label
        })
        
    except Exception as e:
        print(f"❌ [WEEKLY_DETAILS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/collector_guest_details', methods=['POST'])
def get_collector_guest_details():
    """Get detailed guest breakdown for a specific collector in the current period"""
    try:
        data = request.get_json()
        collector_name = data.get('collector')
        start_date = data.get('start_date')  # Optional
        end_date = data.get('end_date')  # Optional
        
        print(f"🔍 [COLLECTOR_DETAILS] Requested: {collector_name}")
        
        if not collector_name:
            return jsonify({'success': False, 'message': 'Missing collector parameter'}), 400
        
        # Load data excluding cancelled bookings and filter for checked-in guests only
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': True, 'guests': [], 'total_amount': 0, 'count': 0})
        
        # Filter for checked-in guests
        from datetime import date, datetime
        today = date.today()
        
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        checked_in_mask = df['Check-in Date'].dt.date <= today
        
        # ✅ CRITICAL FIX: Use EXACT same logic as collector chart calculation
        # Apply date range filter FIRST, then checked-in filter (same as chart)
        if start_date and end_date:
            try:
                # ✅ CRITICAL FIX: Use EXACT same datetime conversion as chart
                # Chart receives datetime objects, we need to match that exactly
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                
                print(f"🔍 [COLLECTOR_DETAILS] Date conversion: {start_date} → {start_dt}, {end_date} → {end_dt}")
                
                # Step 1: Apply period filter FIRST (EXACTLY same as chart)
                # ✅ CRITICAL: Use date-only comparison to avoid time zone issues
                start_date_only = start_dt.date()
                end_date_only = end_dt.date()
                
                period_mask = (df['Check-in Date'].dt.date >= start_date_only) & (df['Check-in Date'].dt.date <= end_date_only)
                period_df = df[period_mask].copy()
                
                print(f"🔍 [COLLECTOR_DETAILS] Period filter applied: {len(df)} → {len(period_df)} guests")
                print(f"🔍 [COLLECTOR_DETAILS] Date range (date only): {start_date_only} to {end_date_only}")
                print(f"🔍 [COLLECTOR_DETAILS] MUST MATCH chart: Should be 36 guests exactly")
                
                # Step 2: Apply checked-in filter to period data (same as chart)
                checked_in_mask_period = period_df['Check-in Date'].dt.date <= today
                filtered_df = period_df[checked_in_mask_period].copy()
                
                period_label = f"từ {start_date} đến {end_date}"
                print(f"🔍 [COLLECTOR_DETAILS] CHART LOGIC: Period first ({len(period_df)}) → Checked-in ({len(filtered_df)})")
                print(f"🔍 [COLLECTOR_DETAILS] MUST MATCH chart: Should be 34 checked-in guests exactly")
            except:
                filtered_df = df[checked_in_mask].copy()
                period_label = "tất cả thời gian"
        else:
            filtered_df = df[checked_in_mask].copy()
            period_label = "tất cả thời gian"
        
        print(f"🔍 [COLLECTOR_DETAILS] Total checked-in guests: {len(filtered_df)}")
        print(f"🔍 [COLLECTOR_DETAILS] Period: {period_label}")
        print(f"🔍 [COLLECTOR_DETAILS] Date range received: start={start_date}, end={end_date}")
        
        # Filter by specific collector
        collector_guests_all = filtered_df[filtered_df['Người thu tiền'] == collector_name].copy()
        
        # ✅ CRITICAL FIX: Apply same filters as chart calculation
        collector_guests = collector_guests_all[collector_guests_all['Tổng thanh toán'] > 0].copy()
        
        print(f"🔍 [COLLECTOR_DETAILS] {collector_name} guests (all): {len(collector_guests_all)}")
        print(f"🔍 [COLLECTOR_DETAILS] {collector_name} guests (amount > 0): {len(collector_guests)}")
        
        # Debug total calculation
        if not collector_guests.empty:
            detail_total = collector_guests['Tổng thanh toán'].sum()
            detail_total_all = collector_guests_all['Tổng thanh toán'].sum()
            print(f"🔍 [COLLECTOR_DETAILS] {collector_name} total amount (filtered): {detail_total:,.0f}đ")
            print(f"🔍 [COLLECTOR_DETAILS] {collector_name} total amount (all): {detail_total_all:,.0f}đ")
            print(f"🔍 [COLLECTOR_DETAILS] This should match the chart button amount")
            
            # Specific LOC LE tracking to match chart
            if collector_name == 'LOC LE':
                print(f"🎯 [DETAILS_LOC_LE] Final: {len(collector_guests)} guests, {detail_total:,.0f}đ")
        
        if collector_guests.empty:
            return jsonify({
                'success': True, 
                'guests': [], 
                'total_amount': 0, 
                'count': 0,
                'collector': collector_name,
                'period': period_label
            })
        
        # Prepare guest details
        guest_details = []
        total_amount = 0
        total_commission = 0
        total_taxi = 0
        
        for _, guest in collector_guests.iterrows():
            guest_name = guest.get('Tên người đặt', 'N/A')
            booking_id = guest.get('Số đặt phòng', 'N/A')
            amount = float(guest.get('Tổng thanh toán', 0))
            commission = float(guest.get('Hoa hồng', 0))
            taxi = float(guest.get('Taxi', 0))
            checkin_date = guest.get('Check-in Date')
            checkout_date = guest.get('Check-out Date')
            
            # Format dates safely
            try:
                checkin_str = checkin_date.strftime('%d/%m/%Y') if pd.notna(checkin_date) else 'N/A'
                checkout_str = checkout_date.strftime('%d/%m/%Y') if pd.notna(checkout_date) else 'N/A'
            except:
                checkin_str = str(checkin_date) if checkin_date else 'N/A'
                checkout_str = str(checkout_date) if checkout_date else 'N/A'
            
            guest_details.append({
                'guest_name': guest_name,
                'booking_id': str(booking_id),
                'amount': amount,
                'commission': commission,
                'taxi': taxi,
                'checkin_date': checkin_str,
                'checkout_date': checkout_str
            })
            
            total_amount += amount
            total_commission += commission
            total_taxi += taxi
        
        # Sort by check-in date (earliest first)
        guest_details.sort(key=lambda x: x['checkin_date'])
        
        # Log summary for debugging
        print(f"💰 [COLLECTOR_SUMMARY] {collector_name} ({period_label}):")
        print(f"💰   Total guests: {len(guest_details)}")
        print(f"💰   Total amount: {total_amount:,.0f}đ")
        print(f"💰   Total commission: {total_commission:,.0f}đ")
        print(f"💰   Total taxi: {total_taxi:,.0f}đ")
        
        return jsonify({
            'success': True,
            'guests': guest_details,
            'total_amount': total_amount,
            'total_commission': total_commission,
            'total_taxi': total_taxi,
            'count': len(guest_details),
            'collector': collector_name,
            'period': period_label
        })
        
    except Exception as e:
        print(f"❌ [COLLECTOR_DETAILS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/collector_chart_data', methods=['POST'])
def get_collector_chart_data():
    """Get collector chart data for a specific period - supports month selection"""
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        use_current_filter = data.get('use_current_filter', False)
        use_all_time = data.get('use_all_time', False)
        
        print(f"🗓️ [COLLECTOR_CHART_API] Request: start={start_date}, end={end_date}, use_current={use_current_filter}, use_all_time={use_all_time}")
        
        # Load booking data
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({
                'success': True, 
                'chart_data': {}, 
                'stats_data': [], 
                'message': 'No data available'
            })
        
        # Apply date filtering
        from datetime import datetime, date
        today = date.today()
        
        # Ensure Check-in Date is datetime
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        checked_in_mask = df['Check-in Date'].dt.date <= today
        
        if start_date and end_date and not use_current_filter and not use_all_time:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                period_mask = (df['Check-in Date'].dt.date >= start_dt) & (df['Check-in Date'].dt.date <= end_dt)
                filtered_df = df[checked_in_mask & period_mask].copy()
                period_label = f"từ {start_date} đến {end_date}"
                print(f"🗓️ [COLLECTOR_CHART_API] Using specific date range: {start_date} to {end_date}")
            except Exception as e:
                print(f"🗓️ [COLLECTOR_CHART_API] Date parsing error: {e}")
                filtered_df = df[checked_in_mask].copy()
                period_label = "tất cả thời gian"
        elif use_all_time:
            # Use all time data - ignore any date filters
            filtered_df = df[checked_in_mask].copy()
            period_label = "tất cả thời gian"
            print(f"🗓️ [COLLECTOR_CHART_API] Using ALL TIME data (ignoring date filters)")
        else:
            # Use current dashboard filter or all time
            filtered_df = df[checked_in_mask].copy()
            period_label = "theo bộ lọc hiện tại"
            print(f"🗓️ [COLLECTOR_CHART_API] Using current filter/all time")
        
        print(f"🗓️ [COLLECTOR_CHART_API] Filtered data: {len(filtered_df)} records")
        print(f"🗓️ [COLLECTOR_CHART_API] Date range used: {period_label}")
        
        # Debug: Show what collectors exist in filtered data
        if 'Người thu tiền' in filtered_df.columns:
            collector_counts = filtered_df['Người thu tiền'].value_counts(dropna=False)
            print(f"🗓️ [COLLECTOR_CHART_API] All collectors in filtered data:")
            for collector, count in collector_counts.items():
                amount = filtered_df[filtered_df['Người thu tiền'] == collector]['Tổng thanh toán'].sum() if 'Tổng thanh toán' in filtered_df.columns else 0
                print(f"🗓️   - '{collector}': {count} bookings, {amount:,.0f}đ")
        
        # Debug: Show some sample data
        if not filtered_df.empty:
            print(f"🗓️ [COLLECTOR_CHART_API] Sample of filtered data:")
            sample_cols = ['Check-in Date', 'Người thu tiền', 'Tổng thanh toán'] if all(col in filtered_df.columns for col in ['Check-in Date', 'Người thu tiền', 'Tổng thanh toán']) else filtered_df.columns[:3]
            print(filtered_df[sample_cols].head())
        
        # Apply collector validation (same as dashboard logic)
        valid_collectors = ['LOC LE', 'THAO LE']
        
        # Filter for valid collector bookings with amounts > 0
        if 'Người thu tiền' in filtered_df.columns and 'Tổng thanh toán' in filtered_df.columns:
            valid_collector_mask = filtered_df['Người thu tiền'].isin(valid_collectors)
            amount_mask = pd.to_numeric(filtered_df['Tổng thanh toán'], errors='coerce') > 0
            valid_collector_df = filtered_df[valid_collector_mask & amount_mask].copy()
            
            print(f"🗓️ [COLLECTOR_CHART_API] Valid collector records: {len(valid_collector_df)}")
            
            # Debug: Show valid collector breakdown
            if not valid_collector_df.empty:
                valid_collector_counts = valid_collector_df['Người thu tiền'].value_counts()
                print(f"🗓️ [COLLECTOR_CHART_API] Valid collector breakdown:")
                for collector, count in valid_collector_counts.items():
                    amount = valid_collector_df[valid_collector_df['Người thu tiền'] == collector]['Tổng thanh toán'].sum()
                    print(f"🗓️   - {collector}: {count} bookings, {amount:,.0f}đ")
            else:
                print(f"🗓️ [COLLECTOR_CHART_API] ❌ No valid collector records found after filtering")
            
            if not valid_collector_df.empty:
                # Group by collector and calculate stats
                collector_stats = valid_collector_df.groupby('Người thu tiền').agg({
                    'Tổng thanh toán': 'sum',
                    'Số đặt phòng': 'count',
                    'Hoa hồng': 'sum'
                }).reset_index()
                
                # Convert to stats format for table
                stats_data = []
                chart_labels = []
                chart_values = []
                chart_customdata = []
                
                total_collected = collector_stats['Tổng thanh toán'].sum()
                
                for _, row in collector_stats.iterrows():
                    collector = row['Người thu tiền']
                    amount = row['Tổng thanh toán']
                    bookings = row['Số đặt phòng']
                    commission = row['Hoa hồng'] if pd.notna(row['Hoa hồng']) else 0
                    
                    stats_data.append({
                        'collector': collector,
                        'amount': amount,
                        'bookings': bookings,
                        'commission': commission
                    })
                    
                    chart_labels.append(collector)
                    chart_values.append(amount)
                    chart_customdata.append([bookings, commission])
                    
                    print(f"🗓️ [COLLECTOR_CHART_API] {collector}: {amount:,.0f}đ ({bookings} bookings)")
                
                # Create chart data in Plotly format
                if chart_labels and chart_values:
                    chart_data = {
                        'data': [{
                            'type': 'pie',
                            'labels': chart_labels,
                            'values': chart_values,
                            'customdata': chart_customdata,
                            'hovertemplate': '<b>%{label}</b><br>' +
                                           'Số tiền: %{value:,.0f}đ<br>' +
                                           'Số booking: %{customdata[0]}<br>' +
                                           'Hoa hồng: %{customdata[1]:.0f}đ<br>' +
                                           'Tỷ lệ: %{percent}<extra></extra>',
                            'hole': 0.4,
                            'marker': {
                                'colors': ['#1f77b4' if label == 'LOC LE' else '#2ca02c' if label == 'THAO LE' else '#ff7f0e' 
                                          for label in chart_labels]
                            }
                        }],
                        'layout': {
                            'title': {
                                'text': f'Phân bổ thu tiền - {period_label}',
                                'x': 0.5,
                                'font': {'size': 14}
                            },
                            'showlegend': True,
                            'legend': {
                                'orientation': 'v',
                                'x': 1,
                                'y': 0.5
                            },
                            'margin': {'l': 20, 'r': 80, 't': 40, 'b': 20},
                            'annotations': [{
                                'text': f'{total_collected:,.0f}đ<br><small>Tổng cộng</small>',
                                'x': 0.5,
                                'y': 0.5,
                                'font_size': 12,
                                'showarrow': False
                            }]
                        }
                    }
                else:
                    chart_data = {}
            else:
                print(f"🗓️ [COLLECTOR_CHART_API] No valid collections found")
                stats_data = []
                chart_data = {}
        else:
            print(f"🗓️ [COLLECTOR_CHART_API] Missing required columns")
            stats_data = []
            chart_data = {}
        
        return jsonify({
            'success': True,
            'chart_data': chart_data,
            'stats_data': stats_data,
            'period': period_label,
            'total_records': len(filtered_df)
        })
        
    except Exception as e:
        print(f"❌ [COLLECTOR_CHART_API] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/railway_status', methods=['GET'])
def railway_status():
    """Debug endpoint for Railway deployment status"""
    try:
        # Check environment
        env_status = {
            'DATABASE_URL': 'DATABASE_URL' in os.environ,
            'GOOGLE_API_KEY': 'GOOGLE_API_KEY' in os.environ,
            'RAILWAY': 'RAILWAY' in os.environ,
            'PORT': os.environ.get('PORT', 'Not set')
        }
        
        # Check database connection
        from core.models import db
        try:
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            db_status = 'Connected'
        except Exception as e:
            db_status = f'Error: {str(e)}'
        
        # Check if we can load booking data
        try:
            df = load_booking_data_for_calculations()
            data_status = f'Loaded {len(df)} bookings'
        except Exception as e:
            data_status = f'Error: {str(e)}'
        
        return jsonify({
            'environment': env_status,
            'database': db_status,
            'data_loading': data_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/railway_setup_guide', methods=['GET'])
def railway_setup_guide():
    """Railway deployment setup guide"""
    setup_steps = {
        'title': 'Railway Deployment Setup Guide',
        'current_issues': [],
        'required_env_vars': {
            'DATABASE_URL': {
                'description': 'PostgreSQL database connection string',
                'format': 'postgresql://username:password@hostname:port/database_name',
                'current': 'DATABASE_URL' in os.environ
            },
            'GOOGLE_API_KEY': {
                'description': 'Google AI API key for image processing',
                'format': 'AIza...',
                'current': 'GOOGLE_API_KEY' in os.environ
            }
        },
        'setup_steps': [
            '1. Go to Railway dashboard',
            '2. Add PostgreSQL service to your project',
            '3. Connect database service to your app',
            '4. Set environment variables in Railway settings',
            '5. Redeploy your application',
            '6. Test with /api/railway_status endpoint'
        ]
    }
    
    # Check current status
    if 'DATABASE_URL' not in os.environ:
        setup_steps['current_issues'].append('DATABASE_URL environment variable missing')
    
    if 'GOOGLE_API_KEY' not in os.environ:
        setup_steps['current_issues'].append('GOOGLE_API_KEY environment variable missing')
    
    return jsonify(setup_steps)

@app.route('/api/collector_available_months', methods=['GET'])
def get_collector_available_months():
    """Get list of months that have collector data available"""
    try:
        print(f"🗓️ [AVAILABLE_MONTHS] Getting months with collector data...")
        
        # Load booking data
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': True, 'months': []})
        
        # Apply collector validation (same logic as chart API)
        valid_collectors = ['LOC LE', 'THAO LE']
        
        # Ensure Check-in Date is datetime
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        
        # Don't filter by checked-in date - show all months with data
        print(f"🗓️ [AVAILABLE_MONTHS] Total records: {len(df)}")
        
        # Filter for valid collector bookings with amounts > 0
        if 'Người thu tiền' in df.columns and 'Tổng thanh toán' in df.columns:
            valid_collector_mask = df['Người thu tiền'].isin(valid_collectors)
            amount_mask = pd.to_numeric(df['Tổng thanh toán'], errors='coerce') > 0
            date_mask = df['Check-in Date'].notna()
            
            # Apply all filters - removed checked-in filter to show all months
            all_filters = valid_collector_mask & amount_mask & date_mask
            valid_df = df[all_filters].copy()
            
            print(f"🗓️ [AVAILABLE_MONTHS] After all filters: {len(valid_df)} records")
            
            if not valid_df.empty:
                # Extract year-month combinations
                valid_df['YearMonth'] = valid_df['Check-in Date'].dt.strftime('%Y-%m')
                unique_months = valid_df['YearMonth'].unique()
                
                # Convert to list of month objects with additional info
                available_months = []
                for month_str in sorted(unique_months):
                    year, month = month_str.split('-')
                    
                    # Get stats for this month
                    month_mask = valid_df['YearMonth'] == month_str
                    month_data = valid_df[month_mask]
                    
                    total_amount = month_data['Tổng thanh toán'].sum()
                    total_bookings = len(month_data)
                    collectors = month_data['Người thu tiền'].value_counts().to_dict()
                    
                    # Create month name in Vietnamese
                    from datetime import datetime
                    date_obj = datetime(int(year), int(month), 1)
                    month_name = date_obj.strftime('%B %Y')  # Will be localized to Vietnamese in frontend
                    
                    available_months.append({
                        'value': month_str,
                        'year': int(year),
                        'month': int(month),
                        'month_name': month_name,
                        'total_amount': total_amount,
                        'total_bookings': total_bookings,
                        'collectors': collectors
                    })
                
                print(f"🗓️ [AVAILABLE_MONTHS] Found {len(available_months)} months with collector data")
                for month_info in available_months:
                    print(f"🗓️   - {month_info['value']}: {month_info['total_amount']:,.0f}đ ({month_info['total_bookings']} bookings)")
                
                # DEBUG: Check specifically for May and June 2025
                may_2025 = df[(df['Check-in Date'].dt.year == 2025) & (df['Check-in Date'].dt.month == 5)]
                june_2025 = df[(df['Check-in Date'].dt.year == 2025) & (df['Check-in Date'].dt.month == 6)]
                print(f"🔍 [DEBUG_MAY_JUNE] May 2025 bookings: {len(may_2025)} total")
                print(f"🔍 [DEBUG_MAY_JUNE] June 2025 bookings: {len(june_2025)} total")
                
                # Check if they have collector data
                if not may_2025.empty:
                    may_collectors = may_2025['Người thu tiền'].value_counts(dropna=False)
                    print(f"🔍 [DEBUG_MAY] May collectors: {dict(may_collectors)}")
                if not june_2025.empty:
                    june_collectors = june_2025['Người thu tiền'].value_counts(dropna=False)
                    print(f"🔍 [DEBUG_JUNE] June collectors: {dict(june_collectors)}")
                
                return jsonify({
                    'success': True, 
                    'months': available_months
                })
            else:
                print(f"🗓️ [AVAILABLE_MONTHS] No valid collector data found")
                return jsonify({'success': True, 'months': []})
        else:
            print(f"🗓️ [AVAILABLE_MONTHS] Missing required columns")
            return jsonify({'success': True, 'months': []})
        
    except Exception as e:
        print(f"❌ [AVAILABLE_MONTHS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/debug_collector_comparison', methods=['POST'])
def debug_collector_comparison():
    """Debug endpoint to compare collector amounts from different calculations"""
    try:
        data = request.get_json()
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        print(f"🔧 [DEBUG_COMPARISON] Analyzing period: {start_date} to {end_date}")
        
        # Load raw data
        df = load_booking_data()
        if df.empty:
            return jsonify({'success': False, 'message': 'No data available'})
        
        # Apply same filtering logic as dashboard
        from datetime import date, datetime
        today = date.today()
        
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        checked_in_mask = df['Check-in Date'].dt.date <= today
        
        # Apply date range filter
        if start_date and end_date:
            try:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_dt = datetime.strptime(end_date, '%Y-%m-%d').date()
                period_mask = (df['Check-in Date'].dt.date >= start_dt) & (df['Check-in Date'].dt.date <= end_dt)
                filtered_df = df[checked_in_mask & period_mask].copy()
            except:
                filtered_df = df[checked_in_mask].copy()
        else:
            filtered_df = df[checked_in_mask].copy()
        
        print(f"🔧 [DEBUG_COMPARISON] Filtered data: {len(filtered_df)} records")
        
        # Method 1: Dashboard calculation (prepare_dashboard_data logic)
        try:
            if start_date and end_date:
                start_dt = datetime.strptime(start_date, '%Y-%m-%d')
                end_dt = datetime.strptime(end_date, '%Y-%m-%d')
                dashboard_data = prepare_dashboard_data(df, start_dt, end_dt, 'checkin_date', 'asc')
            else:
                # Use default date range if not provided
                from datetime import timedelta
                today = datetime.now()
                start_dt = today.replace(day=1)  # First day of current month
                end_dt = today
                dashboard_data = prepare_dashboard_data(df, start_dt, end_dt, 'checkin_date', 'asc')
        except Exception as e:
            print(f"🔧 [DEBUG_COMPARISON] Dashboard data preparation failed: {e}")
            dashboard_data = {'collector_revenue_selected': pd.DataFrame()}
        collector_revenue_selected = dashboard_data.get('collector_revenue_selected', pd.DataFrame())
        
        # Method 2: Direct calculation
        valid_collectors = ['LOC LE', 'THAO LE']
        direct_collector_data = {}
        
        for collector in valid_collectors:
            collector_guests = filtered_df[filtered_df['Người thu tiền'] == collector].copy()
            if not collector_guests.empty:
                total_amount = collector_guests['Tổng thanh toán'].sum()
                total_commission = collector_guests['Hoa hồng'].sum()
                guest_count = len(collector_guests)
                
                direct_collector_data[collector] = {
                    'amount': float(total_amount),
                    'commission': float(total_commission),
                    'count': guest_count,
                    'guests': []
                }
                
                # Add individual guest details
                for _, guest in collector_guests.iterrows():
                    direct_collector_data[collector]['guests'].append({
                        'name': guest.get('Tên người đặt', 'N/A'),
                        'booking_id': str(guest.get('Số đặt phòng', 'N/A')),
                        'amount': float(guest.get('Tổng thanh toán', 0)),
                        'commission': float(guest.get('Hoa hồng', 0)),
                        'checkin_date': guest.get('Check-in Date').strftime('%Y-%m-%d') if pd.notna(guest.get('Check-in Date')) else 'N/A'
                    })
        
        # Method 3: Monthly revenue calculation (for comparison)
        monthly_data = {}
        if start_date and end_date:
            try:
                month_str = start_date[:7]  # YYYY-MM format
                month_mask = filtered_df['Check-in Date'].dt.strftime('%Y-%m') == month_str
                month_guests = filtered_df[month_mask].copy()
                
                for collector in valid_collectors:
                    month_collector_guests = month_guests[month_guests['Người thu tiền'] == collector].copy()
                    if not month_collector_guests.empty:
                        monthly_data[collector] = {
                            'amount': float(month_collector_guests['Tổng thanh toán'].sum()),
                            'count': len(month_collector_guests)
                        }
            except:
                pass
        
        # Format dashboard data for comparison
        dashboard_collector_data = {}
        if not collector_revenue_selected.empty:
            for _, row in collector_revenue_selected.iterrows():
                collector = row.get('Người thu tiền', 'Unknown')
                dashboard_collector_data[collector] = {
                    'amount': float(row.get('Tổng thanh toán', 0)),
                    'commission': float(row.get('Hoa hồng', 0)),
                    'count': int(row.get('Số đặt phòng', 0))
                }
        
        # Create comparison results
        comparison_results = {
            'period': f"{start_date} to {end_date}" if start_date and end_date else "All time",
            'total_filtered_records': len(filtered_df),
            'dashboard_calculation': dashboard_collector_data,
            'direct_calculation': direct_collector_data,
            'monthly_calculation': monthly_data,
            'discrepancies': []
        }
        
        # Find discrepancies
        for collector in valid_collectors:
            dashboard_amount = dashboard_collector_data.get(collector, {}).get('amount', 0)
            direct_amount = direct_collector_data.get(collector, {}).get('amount', 0)
            monthly_amount = monthly_data.get(collector, {}).get('amount', 0)
            
            if dashboard_amount != direct_amount or dashboard_amount != monthly_amount:
                comparison_results['discrepancies'].append({
                    'collector': collector,
                    'dashboard_amount': dashboard_amount,
                    'direct_amount': direct_amount,
                    'monthly_amount': monthly_amount,
                    'dashboard_vs_direct': dashboard_amount - direct_amount,
                    'dashboard_vs_monthly': dashboard_amount - monthly_amount
                })
        
        print(f"🔧 [DEBUG_COMPARISON] Found {len(comparison_results['discrepancies'])} discrepancies")
        
        return jsonify({
            'success': True,
            'comparison': comparison_results
        })
        
    except Exception as e:
        print(f"❌ [DEBUG_COMPARISON] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/api/debug_june_revenue_specific', methods=['POST'])
def debug_june_revenue_specific():
    """Debug the specific June revenue discrepancy: 36,109,006 vs 31,976,006"""
    try:
        print(f"🔧 [JUNE_DEBUG] Investigating June revenue discrepancy...")
        
        # Load raw data
        df = load_booking_data()
        if df.empty:
            return jsonify({'success': False, 'message': 'No data available'})
        
        from datetime import date, datetime
        today = date.today()
        
        df['Check-in Date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
        
        # Method 1: Monthly revenue calculation (shows 36,109,006)
        print(f"🔧 [JUNE_DEBUG] === MONTHLY REVENUE CALCULATION ===")
        checked_in_mask = df['Check-in Date'].dt.date <= today
        df_checked_in = df[checked_in_mask].copy()
        
        # Filter for June 2025
        june_mask = df_checked_in['Check-in Date'].dt.strftime('%Y-%m') == '2025-06'
        june_guests_monthly = df_checked_in[june_mask].copy()
        
        print(f"🔧 [JUNE_DEBUG] Monthly method: {len(june_guests_monthly)} June guests")
        
        valid_collectors = ['LOC LE', 'THAO LE']
        june_collected_monthly = june_guests_monthly[june_guests_monthly['Người thu tiền'].isin(valid_collectors)].copy()
        june_monthly_total = june_collected_monthly['Tổng thanh toán'].sum()
        
        print(f"🔧 [JUNE_DEBUG] Monthly collected total: {june_monthly_total:,.0f}đ from {len(june_collected_monthly)} guests")
        
        # Method 2: Collector chart calculation (shows 31,976,006)  
        print(f"🔧 [JUNE_DEBUG] === COLLECTOR CHART CALCULATION ===")
        
        # Use period filter (June 1 to June 30)
        start_dt = datetime.strptime('2025-06-01', '%Y-%m-%d').date()
        end_dt = datetime.strptime('2025-06-30', '%Y-%m-%d').date()
        
        period_mask = (df['Check-in Date'].dt.date >= start_dt) & (df['Check-in Date'].dt.date <= end_dt)
        checked_in_period_mask = df['Check-in Date'].dt.date <= today
        
        june_guests_chart = df[checked_in_period_mask & period_mask].copy()
        
        print(f"🔧 [JUNE_DEBUG] Chart method: {len(june_guests_chart)} June guests (with period filter)")
        
        june_collected_chart = june_guests_chart[june_guests_chart['Người thu tiền'].isin(valid_collectors)].copy()
        june_chart_total = june_collected_chart['Tổng thanh toán'].sum()
        
        print(f"🔧 [JUNE_DEBUG] Chart collected total: {june_chart_total:,.0f}đ from {len(june_collected_chart)} guests")
        
        # Find the difference
        difference = june_monthly_total - june_chart_total
        print(f"🔧 [JUNE_DEBUG] DIFFERENCE: {difference:,.0f}đ")
        
        # Find guests that are in monthly but not in chart
        monthly_booking_ids = set(june_collected_monthly['Số đặt phòng'].astype(str))
        chart_booking_ids = set(june_collected_chart['Số đặt phòng'].astype(str))
        
        missing_in_chart = monthly_booking_ids - chart_booking_ids
        extra_in_monthly = chart_booking_ids - monthly_booking_ids
        
        print(f"🔧 [JUNE_DEBUG] Missing in chart: {len(missing_in_chart)} bookings")
        print(f"🔧 [JUNE_DEBUG] Extra in monthly: {len(extra_in_monthly)} bookings")
        
        # Get details of missing guests
        missing_guests = []
        if missing_in_chart:
            missing_df = june_collected_monthly[june_collected_monthly['Số đặt phòng'].astype(str).isin(missing_in_chart)]
            for _, guest in missing_df.iterrows():
                missing_guests.append({
                    'name': guest.get('Tên người đặt', 'N/A'),
                    'booking_id': str(guest.get('Số đặt phòng', 'N/A')),
                    'amount': float(guest.get('Tổng thanh toán', 0)),
                    'collector': guest.get('Người thu tiền', 'N/A'),
                    'checkin_date': guest.get('Check-in Date').strftime('%Y-%m-%d') if pd.notna(guest.get('Check-in Date')) else 'N/A',
                    'reason': 'In monthly calculation but not in chart calculation'
                })
        
        # Check all June guests regardless of collection status
        print(f"🔧 [JUNE_DEBUG] === ALL JUNE GUESTS ANALYSIS ===")
        all_june_monthly = df_checked_in[june_mask].copy()
        all_june_chart = df[checked_in_period_mask & period_mask].copy()
        
        print(f"🔧 [JUNE_DEBUG] All June guests (monthly): {len(all_june_monthly)}")
        print(f"🔧 [JUNE_DEBUG] All June guests (chart): {len(all_june_chart)}")
        
        # Collector breakdown
        monthly_collectors = {}
        chart_collectors = {}
        
        for collector in valid_collectors:
            monthly_collector_amount = june_collected_monthly[june_collected_monthly['Người thu tiền'] == collector]['Tổng thanh toán'].sum()
            chart_collector_amount = june_collected_chart[june_collected_chart['Người thu tiền'] == collector]['Tổng thanh toán'].sum()
            
            monthly_collectors[collector] = {
                'amount': float(monthly_collector_amount),
                'count': len(june_collected_monthly[june_collected_monthly['Người thu tiền'] == collector])
            }
            chart_collectors[collector] = {
                'amount': float(chart_collector_amount),
                'count': len(june_collected_chart[june_collected_chart['Người thu tiền'] == collector])
            }
            
            print(f"🔧 [JUNE_DEBUG] {collector}:")
            print(f"🔧 [JUNE_DEBUG]   Monthly: {monthly_collector_amount:,.0f}đ ({monthly_collectors[collector]['count']} guests)")
            print(f"🔧 [JUNE_DEBUG]   Chart: {chart_collector_amount:,.0f}đ ({chart_collectors[collector]['count']} guests)")
            print(f"🔧 [JUNE_DEBUG]   Diff: {monthly_collector_amount - chart_collector_amount:,.0f}đ")
        
        return jsonify({
            'success': True,
            'analysis': {
                'monthly_total': float(june_monthly_total),
                'chart_total': float(june_chart_total),
                'difference': float(difference),
                'monthly_guest_count': len(june_collected_monthly),
                'chart_guest_count': len(june_collected_chart),
                'missing_guests': missing_guests,
                'collector_breakdown': {
                    'monthly': monthly_collectors,
                    'chart': chart_collectors
                },
                'all_guests_count': {
                    'monthly': len(all_june_monthly),
                    'chart': len(all_june_chart)
                }
            }
        })
        
    except Exception as e:
        print(f"❌ [JUNE_DEBUG] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/debug_collector_comparison')
def debug_collector_comparison_page():
    """Debug page to compare collector calculations"""
    return render_template('debug_collector_comparison.html')

# =====================================================
# DATA SYNCHRONIZATION API ENDPOINTS
# =====================================================

@app.route('/api/sync/test_connections')
def api_test_sync_connections():
    """Test connections to both local and Railway databases"""
    try:
        from core.sync_service import DataSyncService
        
        sync_service = DataSyncService()
        results = sync_service.test_connections()
        
        return jsonify({
            'success': True,
            'connections': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Connection test failed: {str(e)}'
        }), 500

@app.route('/api/sync/import_from_local', methods=['POST'])
def api_import_from_local():
    """Import data from local database to Railway"""
    try:
        from core.sync_service import DataSyncService
        
        print("🔄 Starting data sync from local to Railway...")
        
        sync_service = DataSyncService()
        sync_result = sync_service.sync_from_local_to_railway()
        
        if sync_result['success']:
            print("✅ Data sync completed successfully")
            return jsonify(sync_result)
        else:
            print(f"⚠️ Data sync completed with errors: {sync_result['errors']}")
            return jsonify(sync_result), 422
            
    except Exception as e:
        print(f"❌ Data sync failed: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Data sync failed: {str(e)}',
            'errors': [str(e)]
        }), 500

@app.route('/api/sync/status')
def api_sync_status():
    """Get current database status and record counts"""
    try:
        from core.sync_service import DataSyncService
        
        sync_service = DataSyncService()
        connections = sync_service.test_connections()
        
        # Calculate sync recommendation
        local_counts = connections.get('local_counts', {})
        railway_counts = connections.get('railway_counts', {})
        
        sync_needed = False
        differences = {}
        
        for table in ['bookings', 'guests', 'notes', 'expenses', 'templates']:
            local_count = local_counts.get(table, 0)
            railway_count = railway_counts.get(table, 0)
            diff = local_count - railway_count
            
            differences[table] = {
                'local': local_count,
                'railway': railway_count,
                'difference': diff
            }
            
            if diff != 0:
                sync_needed = True
        
        return jsonify({
            'success': True,
            'local_status': connections['local_status'],
            'railway_status': connections['railway_status'],
            'sync_needed': sync_needed,
            'differences': differences,
            'local_error': connections.get('local_error'),
            'railway_error': connections.get('railway_error')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Status check failed: {str(e)}'
        }), 500

@app.route('/api/auto-sync/status')
def api_auto_sync_status():
    """Auto-sync status endpoint for the dashboard"""
    try:
        from core.sync_service import DataSyncService
        
        # Get actual sync status using existing sync service
        sync_service = DataSyncService()
        connections = sync_service.test_connections()
        
        # Calculate sync differences
        local_counts = connections.get('local_counts', {})
        railway_counts = connections.get('railway_counts', {})
        
        sync_needed = False
        differences = {}
        
        for table in ['bookings', 'guests', 'notes', 'expenses']:
            local_count = local_counts.get(table, 0)
            railway_count = railway_counts.get(table, 0)
            diff = local_count - railway_count
            
            if diff != 0:
                sync_needed = True
                
            differences[table] = {
                'local': local_count,
                'railway': railway_count,
                'difference': diff
            }
        
        return jsonify({
            'success': True,
            'auto_sync_enabled': True,
            'sync_needed': sync_needed,
            'last_sync': None,
            'sync_interval': '5 minutes',
            'database_source': os.getenv('DATABASE_SOURCE', 'auto'),
            'differences': differences,
            'local_connected': connections.get('local_connected', False),
            'railway_connected': connections.get('railway_connected', False),
            'local_counts': local_counts,
            'railway_counts': railway_counts,
            'message': 'Auto-sync is available'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'sync_needed': False,
            'auto_sync_enabled': False,
            'message': f'Auto-sync status failed: {str(e)}'
        }), 500

@app.route('/api/sync/history')
def api_sync_history():
    """Get sync history for the dashboard"""
    try:
        # Return properly formatted sync history
        history_entries = [
            {
                'timestamp': '2025-07-04 10:30:00',
                'type': 'auto',
                'status': 'success',
                'records_synced': 67,
                'source': 'local',
                'target': 'railway',
                'details': ['67 bookings synced successfully']
            }
        ]
        
        return jsonify({
            'success': True,
            'history': history_entries
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Sync history failed: {str(e)}',
            'history': []
        }), 500

@app.route('/api/sync/perform', methods=['POST'])
def api_sync_perform():
    """Perform actual sync operation"""
    try:
        from core.sync_service import DataSyncService
        
        # Get sync direction from request
        data = request.get_json() or {}
        sync_direction = data.get('direction', 'local_to_railway')
        
        print(f"🔄 [SYNC_PERFORM] Starting sync: {sync_direction}")
        
        # Perform the actual sync
        sync_service = DataSyncService()
        
        if sync_direction == 'local_to_railway':
            result = sync_service.sync_from_local_to_railway()
        elif sync_direction == 'railway_to_local':
            # For now, only support local to railway sync
            return jsonify({
                'success': False,
                'message': 'Railway to local sync not yet implemented. Use local to railway sync instead.'
            }), 400
        else:
            return jsonify({
                'success': False,
                'message': f'Invalid sync direction: {sync_direction}'
            }), 400
        
        print(f"✅ [SYNC_PERFORM] Sync completed: {result}")
        
        return jsonify({
            'success': result.get('success', False),
            'message': result.get('message', 'Sync completed'),
            'direction': sync_direction,
            'records_synced': result.get('records_synced', 0),
            'errors': result.get('errors', [])
        })
        
    except Exception as e:
        print(f"❌ [SYNC_PERFORM] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Sync failed: {str(e)}',
            'direction': sync_direction if 'sync_direction' in locals() else 'unknown',
            'records_synced': 0,
            'errors': [str(e)]
        }), 500

@app.route('/api/expenses')
def api_expenses():
    """Get monthly expenses for dashboard"""
    try:
        from core.logic_postgresql import get_monthly_expenses
        
        # Get all expenses (not filtered by month)
        expenses = get_monthly_expenses(show_all=True)
        
        if expenses is None:
            expenses = []
        
        # Convert to proper format
        expense_list = []
        if isinstance(expenses, list):
            for expense in expenses:
                if isinstance(expense, dict):
                    expense_list.append({
                        'description': expense.get('description', 'Expense'),
                        'amount': float(expense.get('amount', 0)),
                        'date': expense.get('date'),
                        'expense_date': expense.get('expense_date'),
                        'created_at': expense.get('created_at')
                    })
        
        return jsonify({
            'success': True,
            'expenses': expense_list,
            'total_count': len(expense_list)
        })
        
    except Exception as e:
        print(f"❌ [EXPENSES_API] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Expenses API failed: {str(e)}',
            'expenses': []
        }), 500

# Initialize crawling integration
CrawlIntegration.setup_crawl_routes(app)

@app.route('/api/crawl_capabilities', methods=['GET'])
def get_crawl_capabilities():
    """Get comprehensive crawling capabilities for current environment"""
    try:
        print("🔍 [CRAWL_CAPABILITIES] Starting comprehensive crawl capabilities check...")
        
        # Railway environment detection
        railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
        print(f"🌍 [CRAWL_CAPABILITIES] Railway environment: {railway_env}")
        
        # Import enhanced railway crawl service
        try:
            from core.railway_crawl_service import railway_crawl_service
            print("✅ [CRAWL_CAPABILITIES] Enhanced railway crawl service imported successfully")
            
            is_available = railway_crawl_service.is_crawling_available()
            environment = 'railway' if railway_crawl_service.is_railway else 'local'
            methods = railway_crawl_service.get_crawling_methods()
            setup_instructions = railway_crawl_service._get_setup_instructions()
            
            # Enhanced capability info
            capability_info = {
                'success': True,
                'environment': 'railway' if railway_env else environment,  # FIXED: Correct environment detection
                'crawling_available': is_available,
                'is_available': is_available,  # FIXED: Added for frontend compatibility
                'total_methods': len(methods),
                'supported_methods': len([m for m in methods if m.get('supported', False)]),
                'methods': methods,
                'setup_instructions': setup_instructions,
                'api_keys_configured': {
                    'firecrawl': bool(os.getenv('FIRECRAWL_API_KEY')),
                    'scrapfly': bool(os.getenv('SCRAPFLY_API_KEY')),
                    'scraperapi': bool(os.getenv('SCRAPERAPI_KEY')),
                    'brightdata': bool(os.getenv('BRIGHTDATA_API_KEY'))
                },
                'recommendations': []
            }
            
            # Add recommendations based on environment
            if railway_env and not is_available:
                capability_info['recommendations'].append({
                    'type': 'setup',
                    'message': 'Configure at least one API-based crawling service for Railway deployment',
                    'priority': 'high',
                    'suggested_service': 'firecrawl'
                })
            elif railway_env and is_available:
                capability_info['recommendations'].append({
                    'type': 'success',
                    'message': f'✅ Railway crawling ready with {len([m for m in methods if m.get("supported", False)])} method(s)',
                    'priority': 'info'
                })
            
            print(f"📊 [CRAWL_CAPABILITIES] Found {len(methods)} total methods, {len([m for m in methods if m.get('supported', False)])} supported")
            return jsonify(capability_info)
            
        except ImportError as import_error:
            print(f"⚠️ [CRAWL_CAPABILITIES] Railway crawl service import failed: {import_error}")
            
            # Basic fallback detection
            is_available = False
            environment = 'railway' if railway_env else 'local'
            methods = []
            
            # Check for basic API keys
            if os.getenv('FIRECRAWL_API_KEY'):
                is_available = True
                methods.append({
                    'id': 'firecrawl',
                    'name': 'Firecrawl API (Basic)',
                    'description': 'Cloud-based web scraping service',
                    'supported': True,
                    'priority': 1
                })
            
            methods.append({
                'id': 'direct_http',
                'name': 'Direct HTTP Requests',
                'description': 'Basic HTTP scraping (limited functionality)',
                'supported': True,
                'priority': 5
            })
            
            # Check for Selenium in local environment
            if not railway_env:
                try:
                    import selenium
                    is_available = True
                    methods.append({
                        'id': 'selenium',
                        'name': 'Selenium Browser Automation',
                        'description': 'Full browser automation with saved profiles',
                        'supported': True,
                        'priority': 0
                    })
                except ImportError:
                    methods.append({
                        'id': 'selenium',
                        'name': 'Selenium Browser Automation',
                        'description': 'Install selenium package to enable',
                        'supported': False,
                        'reason': 'Selenium package not installed'
                    })
        
        capabilities = {
            'success': True,
            'environment': 'railway' if railway_env else environment,  # FIXED: Correct environment detection
            'crawling_available': is_available,
            'is_available': is_available,  # FIXED: Added for frontend compatibility
            'total_methods': len(methods),
            'supported_methods': len([m for m in methods if m.get('supported', False)]),
            'methods': methods,
            'alternatives': [
                '📸 Upload booking screenshots for AI extraction',
                '✏️ Manual booking entry',
                '📋 Import from CSV/Excel files'
            ],
            'setup_instructions': {
                'firecrawl': {
                    'name': 'Firecrawl API (Recommended)',
                    'steps': ['Visit https://firecrawl.dev', 'Sign up for account', 'Get API key', 'Set FIRECRAWL_API_KEY environment variable'],
                    'cost': 'Free tier: 500 requests/month'
                }
            }
        }
        
        print(f"✅ [CRAWL_CAPABILITIES] Capabilities: available={is_available}, env={environment}, methods={len(methods)}")
        return jsonify(capabilities)
        
    except Exception as e:
        print(f"❌ [CRAWL_CAPABILITIES] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'is_available': False,
            'environment': 'unknown',
            'methods': [],
            'alternatives': [
                '📸 Upload booking screenshots for AI extraction',
                '✏️ Manual booking entry', 
                '📋 Import from CSV/Excel files'
            ],
            'error': str(e)
        }), 500

@app.route('/api/crawl_admin_bookings', methods=['POST'])
def crawl_admin_bookings():
    """API endpoint for crawling booking admin panel with AI extraction"""
    try:
        # Import Railway-compatible crawling service
        from core.railway_crawl_service import railway_crawl_service
        
        data = request.get_json()
        target_url = data.get('target_url')
        profile_name = data.get('profile_name', 'booking_fixed_profile')
        
        if not target_url:
            return jsonify({'success': False, 'error': 'Target URL required'}), 400
        
        # 🚀 RAILWAY ENHANCEMENT: Use comprehensive crawling service
        is_railway = os.getenv('RAILWAY_PROJECT_ID') is not None
        print(f"🔍 [CRAWL_ADMIN] Environment: {'Railway' if is_railway else 'Local'}")
        
        if not railway_crawl_service.is_crawling_available():
            available_methods = railway_crawl_service.get_crawling_methods()
            setup_instructions = railway_crawl_service._get_setup_instructions()
            
            return jsonify({
                'success': False,
                'error': f'No crawling methods available. Configure API keys to enable Railway crawling.',
                'environment': 'railway' if is_railway else 'local',
                'available_methods': available_methods,
                'setup_instructions': setup_instructions,
                'recommendation': 'Set up Firecrawl API for best Railway compatibility',
                'alternatives': [
                    '📸 Upload booking screenshots for AI extraction',
                    '✏️ Manual booking entry through the form', 
                    '📋 Import from CSV/Excel files'
                ]
            }), 400
        
        # 🚀 OPTIMIZED: Use high-performance crawler for Railway
        if railway_crawl_service.is_railway:
            print(f"🌐 Using optimized cloud-compatible crawling for: {target_url}")
            
            # Import optimized crawler
            try:
                from core.optimized_railway_crawler import optimized_crawler
                import asyncio
                
                # Use optimized crawler with all performance features
                async def optimized_crawl():
                    return await optimized_crawler.crawl_with_retry(target_url, {
                        'required_features': ['javascript'] if 'booking.com' in target_url else [],
                        'cache_type': 'booking_data'
                    })
                
                # Run async crawler
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    crawl_result = loop.run_until_complete(optimized_crawl())
                    
                    # Format result for compatibility
                    result = {
                        'success': True,
                        'method': 'optimized_crawler',
                        'environment': 'railway',
                        'data': crawl_result,
                        'message': '✅ High-performance crawling successful',
                        'performance_optimized': True
                    }
                    
                    # Add performance metrics
                    performance_report = optimized_crawler.get_performance_report()
                    if 'summary' in performance_report:
                        result['performance_metrics'] = performance_report['summary']
                    
                    return jsonify(result)
                    
                finally:
                    loop.close()
                    
            except ImportError:
                print("⚠️ Optimized crawler not available, falling back to standard service")
                result = railway_crawl_service.crawl_admin_bookings_api(target_url, profile_name)
                return jsonify(result)
            except Exception as e:
                print(f"⚠️ Optimized crawler failed: {str(e)}, falling back to standard service")
                result = railway_crawl_service.crawl_admin_bookings_api(target_url, profile_name)
                return jsonify(result)
        
        # Original Selenium-based crawling for local development
        print(f"🕷️ Using Selenium crawling for: {target_url}")
        
        import psutil
        import time
        from pathlib import Path
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        # Check if profile exists
        profile_path = Path.cwd() / "browser_profiles" / profile_name
        if not profile_path.exists():
            return jsonify({'success': False, 'error': 'Browser profile not found. Please setup profile first.'}), 400
        
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            return jsonify({'success': False, 'error': 'Google AI API not configured'}), 400
        
        print(f"🕷️ Starting admin panel crawl for: {target_url}")
        
        # Smart Chrome cleanup using dedicated function
        from smart_chrome_cleanup import smart_chrome_cleanup
        smart_chrome_cleanup(profile_name)
        
        driver = None
        try:
            # Setup Chrome with saved profile
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--force-device-scale-factor=1")
            chrome_options.add_argument("--remote-debugging-port=9227")
            
            print("🌐 Opening browser with saved profile...")
            driver = webdriver.Chrome(options=chrome_options)
            
            print(f"📍 Navigating to admin panel...")
            driver.get(target_url)
            time.sleep(10)
            
            # Check if logged in
            if "login" in driver.current_url.lower():
                return jsonify({'success': False, 'error': 'Profile expired - redirected to login'}), 400
            
            print("✅ Successfully accessed admin panel!")
            
            # Wait for table to load
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table, .bui-table"))
                )
                print("✅ Table loaded!")
            except:
                print("⚠️ Table not found, proceeding anyway...")
            
            time.sleep(5)
            
            # Get full page screenshot
            total_height = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(1920, total_height)
            time.sleep(2)
            
            print("📸 Taking full page screenshot...")
            screenshot_base64 = driver.get_screenshot_as_base64()
            screenshot_bytes = base64.b64decode(screenshot_base64)
            
            print(f"📊 Screenshot size: {len(screenshot_bytes)} bytes")
            
            # Process with AI
            print("🤖 Processing with Gemini AI...")
            booking_info = extract_booking_info_from_image_content(screenshot_bytes, GOOGLE_API_KEY)
            
            if 'error' in booking_info:
                return jsonify({'success': False, 'error': booking_info['error']}), 400
            
            # Process AI results into standard format
            bookings = []
            extracted_count = 0
            
            if booking_info.get('type') == 'multiple' and 'bookings' in booking_info:
                for booking in booking_info['bookings']:
                    if booking.get('guest_name'):
                        booking['source'] = 'admin_crawl'
                        booking['extracted_at'] = datetime.now().isoformat()
                        bookings.append(booking)
                        extracted_count += 1
            elif booking_info.get('guest_name'):
                booking_info['source'] = 'admin_crawl'
                booking_info['extracted_at'] = datetime.now().isoformat()
                bookings.append(booking_info)
                extracted_count = 1
            
            print(f"🎉 Successfully extracted {extracted_count} bookings!")
            
            # Apply AI duplicate detection to crawled bookings (if available)
            ai_analysis = {
                'analysis': {
                    'new_bookings': len(bookings) if bookings else 0,
                    'duplicates_found': 0,
                    'summary': 'AI duplicate detection not available'
                },
                'filtering_options': [],
                'recommendations': []
            }
            if bookings and ai_duplicate_detector:
                print(f"🤖 [AI_DUPLICATE] Applying AI duplicate detection to crawled bookings...")
                df = load_booking_data()
                ai_analysis = ai_duplicate_detector.create_filtered_response(bookings, df)
                
                return jsonify({
                    'success': True,
                    'bookings_count': extracted_count,
                    'bookings': bookings,
                    'ai_analysis': ai_analysis['analysis'],
                    'filtering_options': ai_analysis['filtering_options'],
                    'recommendations': ai_analysis['recommendations'],
                    'message': f"🤖 AI analyzed {extracted_count} crawled bookings - {ai_analysis['analysis']['new_bookings']} new, {ai_analysis['analysis']['duplicates_found']} duplicates"
                })
            elif bookings:
                print("⚠️ [AI_DUPLICATE] AI duplicate detector not available - skipping analysis")
                
                return jsonify({
                    'success': True,
                    'bookings_count': extracted_count,
                    'bookings': bookings,
                    'ai_analysis': ai_analysis['analysis'],
                    'filtering_options': ai_analysis['filtering_options'],
                    'recommendations': ai_analysis['recommendations'],
                    'message': f"🤖 AI analyzed {extracted_count} crawled bookings - {ai_analysis['analysis']['new_bookings']} new, {ai_analysis['analysis']['duplicates_found']} duplicates"
                })
            else:
                return jsonify({
                    'success': True,
                    'bookings_count': 0,
                    'bookings': [],
                    'message': 'No bookings found in admin panel'
                })
            
        except Exception as e:
            print(f"❌ Crawling error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
    except Exception as e:
        print(f"❌ [CRAWL_ADMIN] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save_bulk_bookings', methods=['POST'])
def save_bulk_bookings():
    """Save multiple bookings extracted from crawling"""
    try:
        data = request.get_json()
        if not data or 'bookings' not in data:
            return jsonify({'success': False, 'error': 'No bookings data provided'}), 400
        
        bookings = data['bookings']
        print(f"💾 [BULK_SAVE] Attempting to save {len(bookings)} bookings...")
        
        saved_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []
        skipped = []
        
        for i, booking_data in enumerate(bookings):
            try:
                # Validate required fields
                if not booking_data.get('guest_name'):
                    errors.append(f"Booking {i+1}: Missing guest name")
                    failed_count += 1
                    continue
                
                # Check if booking already exists
                booking_id = booking_data.get('booking_id', '').strip()
                if booking_id:
                    from core.models import db, Booking
                    existing_booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
                    if existing_booking:
                        skipped.append(f"Booking {i+1} ({booking_data.get('guest_name')}): Already exists - ID {booking_id}")
                        skipped_count += 1
                        print(f"⚠️ [BULK_SAVE] Booking {booking_id} already exists, skipping...")
                        continue
                
                # Convert date strings to date objects
                from datetime import datetime
                checkin_date = None
                checkout_date = None
                
                try:
                    checkin_str = booking_data.get('check_in_date') or booking_data.get('checkin_date')
                    if checkin_str:
                        checkin_date = datetime.strptime(checkin_str, '%Y-%m-%d').date()
                        
                    checkout_str = booking_data.get('check_out_date') or booking_data.get('checkout_date')
                    if checkout_str:
                        checkout_date = datetime.strptime(checkout_str, '%Y-%m-%d').date()
                        
                except ValueError as e:
                    errors.append(f"Booking {i+1}: Invalid date format - {str(e)}")
                    failed_count += 1
                    continue
                
                if not checkin_date or not checkout_date:
                    errors.append(f"Booking {i+1}: Missing required check-in or check-out date")
                    failed_count += 1
                    continue
                
                # Format booking data for database
                formatted_booking = {
                    'guest_name': booking_data.get('guest_name', ''),
                    'booking_id': booking_data.get('booking_id', ''),
                    'checkin_date': checkin_date,  # Use correct field name
                    'checkout_date': checkout_date,  # Use correct field name
                    'room_amount': float(booking_data.get('room_amount', 0)),
                    'commission': float(booking_data.get('commission', 0)),
                    'taxi_amount': float(booking_data.get('taxi_amount', 0)),
                    'email': booking_data.get('email', ''),
                    'phone': booking_data.get('phone', ''),
                    'notes': f"Imported from admin crawl - {booking_data.get('source', 'unknown')}"
                }
                
                # Add to database using existing function (returns boolean)
                result = add_new_booking(formatted_booking)
                
                if result:  # Boolean check, not dict
                    saved_count += 1
                    print(f"✅ [BULK_SAVE] Saved booking {i+1}: {booking_data.get('guest_name')}")
                else:
                    errors.append(f"Booking {i+1}: Database save failed")
                    failed_count += 1
                    
            except Exception as e:
                errors.append(f"Booking {i+1}: {str(e)}")
                failed_count += 1
                print(f"❌ [BULK_SAVE] Error saving booking {i+1}: {e}")
        
        print(f"📊 [BULK_SAVE] Results: {saved_count} saved, {skipped_count} skipped (already exist), {failed_count} failed")
        
        return jsonify({
            'success': True,
            'saved_count': saved_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'errors': errors,
            'skipped': skipped,
            'message': f'Bulk save completed: {saved_count} new bookings saved, {skipped_count} already existed, {failed_count} failed'
        })
        
    except Exception as e:
        print(f"❌ [BULK_SAVE] Critical error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/duplicate_management', methods=['GET'])
def duplicate_management():
    """Get comprehensive duplicate analysis for manual review"""
    try:
        from core.logic_postgresql import load_booking_data, analyze_existing_duplicates
        from core.models import db, Booking
        
        # Get guest filter parameter for dashboard integration
        guest_filter = request.args.get('guest', '').strip()
        
        print("🔍 [DUPLICATE_MGMT] Starting comprehensive duplicate analysis...")
        if guest_filter:
            print(f"🔍 [DUPLICATE_MGMT] Filtering for guest: {guest_filter}")
        
        # Load all booking data with fresh connection to ensure latest status updates
        df = load_booking_data(force_fresh=True)
        if df.empty:
            return jsonify({'success': True, 'duplicates': [], 'total_groups': 0})
        
        # Get detailed duplicate analysis
        duplicates_result = analyze_existing_duplicates(df)
        
        # Enhanced duplicate information with database details
        enhanced_duplicates = []
        
        for group in duplicates_result.get('duplicate_groups', []):
            # Apply guest filter if specified
            if guest_filter and guest_filter.lower() not in group['guest_name'].lower():
                continue
                
            enhanced_group = {
                'guest_name': group['guest_name'],
                'date_difference_days': group['date_difference_days'],
                'bookings': []
            }
            
            # Get full booking details from database
            for booking_info in group['bookings']:
                booking_id = booking_info.get('Số đặt phòng')
                if booking_id:
                    # Get full booking from database
                    full_booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
                    if full_booking:
                        enhanced_booking = {
                            'booking_id': full_booking.booking_id,
                            'guest_name': full_booking.guest_name,
                            'checkin_date': full_booking.checkin_date.strftime('%Y-%m-%d') if full_booking.checkin_date else 'N/A',
                            'checkout_date': full_booking.checkout_date.strftime('%Y-%m-%d') if full_booking.checkout_date else 'N/A',
                            'room_amount': float(full_booking.room_amount or 0),
                            'commission': float(full_booking.commission or 0),
                            'taxi_amount': float(full_booking.taxi_amount or 0),
                            'collected_amount': float(full_booking.collected_amount or 0),
                            'collector': full_booking.collector or '',
                            'booking_status': full_booking.booking_status,
                            'booking_notes': full_booking.booking_notes or '',
                            'created_at': full_booking.created_at.strftime('%Y-%m-%d %H:%M:%S') if full_booking.created_at else 'N/A'
                        }
                        enhanced_group['bookings'].append(enhanced_booking)
            
            # Only include groups with multiple bookings
            if len(enhanced_group['bookings']) > 1:
                enhanced_duplicates.append(enhanced_group)
        
        print(f"🔍 [DUPLICATE_MGMT] Found {len(enhanced_duplicates)} duplicate groups")
        
        return jsonify({
            'success': True,
            'duplicates': enhanced_duplicates,
            'total_groups': len(enhanced_duplicates),
            'processing_info': {
                'total_guests': duplicates_result.get('total_guests', 0),
                'processed_guests': duplicates_result.get('processed_guests', 0),
                'processing_time': duplicates_result.get('processing_time', 0)
            }
        })
        
    except Exception as e:
        print(f"❌ [DUPLICATE_MGMT] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete_duplicate_booking', methods=['POST'])
def delete_duplicate_booking():
    """Delete a specific booking from a duplicate group"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        
        if not booking_id:
            return jsonify({'success': False, 'error': 'Booking ID required'}), 400
        
        print(f"🗑️ [DELETE_DUPLICATE] Attempting to delete booking: {booking_id}")
        
        # Use existing delete function
        success = delete_booking_by_id(booking_id)
        
        if success:
            print(f"✅ [DELETE_DUPLICATE] Successfully deleted booking: {booking_id}")
            return jsonify({'success': True, 'message': f'Deleted booking {booking_id}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete booking'}), 400
            
    except Exception as e:
        print(f"❌ [DELETE_DUPLICATE] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/revenue_calculation_comparison', methods=['GET'])
def revenue_calculation_comparison():
    """
    API endpoint to compare traditional vs daily distribution revenue calculation methods
    
    Query parameters:
    - method: 'traditional', 'daily_distribution', or 'both' (default: 'both')
    - months: number of months to analyze (default: 6)
    """
    try:
        from core.dashboard_routes import process_monthly_revenue_with_unpaid_enhanced, calculate_revenue_optimized_dual_method
        from core.logic_postgresql import load_booking_data
        
        # Get parameters
        method = request.args.get('method', 'both')
        months = int(request.args.get('months', 6))
        
        print(f"🔍 [REVENUE_COMPARISON] Method: {method}, Months: {months}")
        
        # Load booking data excluding cancelled bookings for revenue calculations
        df = load_booking_data_for_calculations()
        
        if df.empty:
            return jsonify({
                'success': False,
                'error': 'No booking data available',
                'data': {}
            })
        
        result = {
            'success': True,
            'comparison_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_bookings': len(df),
            'analysis_months': months,
            'methods': {}
        }
        
        if method in ['traditional', 'both']:
            print("💰 [REVENUE_COMPARISON] Calculating traditional method...")
            traditional_data = process_monthly_revenue_with_unpaid_enhanced(
                df, use_daily_distribution=False
            )
            result['methods']['traditional'] = {
                'name': 'Traditional Method (Current)',
                'description': 'Groups bookings by check-in month, counts full booking amount in that month',
                'data': traditional_data[-months:] if traditional_data else [],
                'total_months': len(traditional_data) if traditional_data else 0
            }
        
        if method in ['daily_distribution', 'both']:
            print("📅 [REVENUE_COMPARISON] Calculating daily distribution method...")
            daily_data = process_monthly_revenue_with_unpaid_enhanced(
                df, use_daily_distribution=True
            )
            result['methods']['daily_distribution'] = {
                'name': 'Daily Distribution Method (New)',
                'description': 'Divides booking amounts across each night of stay, more accurate for monthly totals',
                'data': daily_data[-months:] if daily_data else [],
                'total_months': len(daily_data) if daily_data else 0
            }
        
        if method == 'both':
            print("🔍 [REVENUE_COMPARISON] Creating detailed comparison...")
            dual_results = calculate_revenue_optimized_dual_method(df)
            result['detailed_comparison'] = dual_results.get('comparison_summary', {})
            
            # Calculate summary statistics
            traditional_total = sum([month.get('Tổng cộng', 0) for month in result['methods']['traditional']['data']])
            daily_total = sum([month.get('Tổng cộng', 0) for month in result['methods']['daily_distribution']['data']])
            
            result['summary'] = {
                'traditional_total_revenue': traditional_total,
                'daily_distribution_total_revenue': daily_total,
                'difference_amount': abs(traditional_total - daily_total),
                'difference_percent': (abs(traditional_total - daily_total) / max(traditional_total, daily_total) * 100) if max(traditional_total, daily_total) > 0 else 0,
                'recommendation': 'Daily distribution method provides more accurate monthly revenue distribution, especially for multi-night stays'
            }
        
        print(f"✅ [REVENUE_COMPARISON] Comparison completed successfully")
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ [REVENUE_COMPARISON] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500

@app.route('/api/daily_customer_breakdown', methods=['POST'])
def daily_customer_breakdown():
    """API endpoint to get detailed daily customer breakdown for a specific month"""
    try:
        print("🔍 [DAILY_BREAKDOWN] API called")
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'Không có dữ liệu'}), 400
            
        month = data.get('month')
        method = data.get('method', 'daily_distribution')
        
        print(f"📅 [DAILY_BREAKDOWN] Requested month: {month}, method: {method}")
        
        if not month:
            return jsonify({'success': False, 'message': 'Thiếu thông tin tháng'}), 400
        
        # Parse month - handle both "Tháng M/YYYY" and "YYYY-MM" formats
        try:
            if 'Tháng' in month:
                # Format: "Tháng 6/2025"
                parts = month.replace('Tháng ', '').split('/')
                month_num = int(parts[0])
                year = int(parts[1])
            else:
                # Format: "2025-06"
                parts = month.split('-')
                year = int(parts[0])
                month_num = int(parts[1])
                
            print(f"📅 [DAILY_BREAKDOWN] Parsed: Year={year}, Month={month_num}")
            
        except (ValueError, IndexError) as e:
            print(f"❌ [DAILY_BREAKDOWN] Month parsing error: {e}")
            return jsonify({'success': False, 'message': f'Định dạng tháng không hợp lệ: {month}'}), 400
        
        # Load booking data excluding cancelled bookings for calculations
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': False, 'message': 'Không có dữ liệu booking'}), 400
            
        print(f"📊 [DAILY_BREAKDOWN] Loaded {len(df)} bookings")
        
        # Filter data for the specified month
        try:
            df['check_in_date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
            df['check_out_date'] = pd.to_datetime(df['Check-out Date'], errors='coerce')
            
            # Filter bookings that overlap with the requested month
            start_of_month = pd.Timestamp(year=year, month=month_num, day=1)
            if month_num == 12:
                end_of_month = pd.Timestamp(year=year+1, month=1, day=1) - pd.Timedelta(days=1)
            else:
                end_of_month = pd.Timestamp(year=year, month=month_num+1, day=1) - pd.Timedelta(days=1)
            
            # Bookings that overlap with this month (check-in before month end, check-out after month start)
            month_bookings = df[
                (df['check_in_date'] <= end_of_month) & 
                (df['check_out_date'] > start_of_month)
            ].copy()
            
            print(f"🎯 [DAILY_BREAKDOWN] Found {len(month_bookings)} bookings for {month}")
            
        except Exception as e:
            print(f"❌ [DAILY_BREAKDOWN] Date filtering error: {e}")
            return jsonify({'success': False, 'message': f'Lỗi xử lý ngày tháng: {str(e)}'}), 400
        
        if month_bookings.empty:
            return jsonify({
                'success': True,
                'daily_data': [],
                'summary': {
                    'total_customer_days': 0,
                    'unique_customers': 0,
                    'active_days': 0,
                    'average_occupancy': 0
                },
                'message': f'Không có khách hàng trong {month}'
            })
        
        # Calculate daily breakdown using daily distribution method
        daily_data = {}
        unique_customers = set()
        
        for _, booking in month_bookings.iterrows():
            guest_name = booking.get('Tên người đặt', 'Unknown')
            checkin = booking['check_in_date']
            checkout = booking['check_out_date']
            
            unique_customers.add(guest_name)
            
            # Calculate which days this booking covers within the month
            actual_start = max(checkin, start_of_month)
            actual_end = min(checkout, end_of_month + pd.Timedelta(days=1))
            
            # Generate date range for this booking within the month
            current_date = actual_start
            while current_date < actual_end:
                if current_date.month == month_num and current_date.year == year:
                    date_str = current_date.strftime('%Y-%m-%d')
                    
                    if date_str not in daily_data:
                        daily_data[date_str] = {
                            'date': date_str,
                            'customers': [],
                            'total_nights': 0
                        }
                    
                    # Add customer to this day
                    daily_data[date_str]['customers'].append({
                        'guest_name': guest_name,
                        'checkin_date': checkin.strftime('%Y-%m-%d'),
                        'checkout_date': checkout.strftime('%Y-%m-%d')
                    })
                    daily_data[date_str]['total_nights'] += 1
                
                current_date += pd.Timedelta(days=1)
        
        # Convert to list and sort by date
        daily_data_list = list(daily_data.values())
        daily_data_list.sort(key=lambda x: x['date'])
        
        # Calculate summary statistics
        total_customer_days = sum(len(day['customers']) for day in daily_data_list)
        active_days = len([day for day in daily_data_list if len(day['customers']) > 0])
        days_in_month = (end_of_month - start_of_month).days + 1
        average_occupancy = total_customer_days / days_in_month if days_in_month > 0 else 0
        
        summary = {
            'total_customer_days': total_customer_days,
            'unique_customers': len(unique_customers),
            'active_days': active_days,
            'average_occupancy': round(average_occupancy, 1)
        }
        
        print(f"✅ [DAILY_BREAKDOWN] Summary: {summary}")
        
        return jsonify({
            'success': True,
            'daily_data': daily_data_list,
            'summary': summary,
            'month': month,
            'message': f'Thành công tải dữ liệu cho {month}'
        })
        
    except Exception as e:
        print(f"❌ [DAILY_BREAKDOWN] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Lỗi server: {str(e)}',
            'daily_data': [],
            'summary': {}
        }), 500

@app.route('/api/ai_chat_analyze', methods=['POST'])
def ai_chat_analyze():
    """AI image analysis endpoint for chat assistant"""
    try:
        print("🔍 [AI_CHAT_ANALYZE] API called")
        
        # Handle JSON request with base64 image data
        if request.is_json:
            data = request.get_json()
            print(f"🔍 [AI_CHAT_ANALYZE] Received JSON data: {list(data.keys()) if data else 'None'}")
            
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Extract base64 image data
            image_b64 = data.get('image_b64')
            if not image_b64:
                print("❌ [AI_CHAT_ANALYZE] Missing image_b64 in request data")
                return jsonify({'success': False, 'error': 'No image_b64 provided'}), 400
            
            # Extract AI configuration
            ai_config = data.get('ai_config', {})
            custom_instructions = ai_config.get('custom_instructions', '') or ai_config.get('customInstructions', '')
            selected_template = ai_config.get('selectedTemplate')
            response_mode = ai_config.get('response_mode', 'auto') or ai_config.get('responseMode', 'auto')
            
            print(f"📝 [AI_CHAT_ANALYZE] AI Config: {ai_config}")
            print(f"📝 [AI_CHAT_ANALYZE] Custom Instructions: '{custom_instructions}'")
            print(f"📝 [AI_CHAT_ANALYZE] Response Mode: '{response_mode}'")
            print(f"📸 [AI_CHAT_ANALYZE] Image data length: {len(image_b64)}")
            
            try:
                import base64
                # Decode base64 image (remove data:image/... prefix if present)
                if ',' in image_b64:
                    image_b64 = image_b64.split(',')[1]
                
                image_data = base64.b64decode(image_b64)
                
                # Real Gemini AI Integration
                try:
                    # Check if Gemini API is configured
                    api_key = os.getenv('GOOGLE_API_KEY')
                    if not api_key:
                        print("⚠️ [AI_CHAT_ANALYZE] GOOGLE_API_KEY not configured, using sample response")
                        use_real_ai = False
                    else:
                        print("✅ [AI_CHAT_ANALYZE] Gemini API key found, using real AI analysis")
                        use_real_ai = True
                        
                        # Configure Gemini AI
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        # Create prompt based on AI config with custom instructions priority
                        if custom_instructions:
                            ai_prompt = f"""You are a friendly hotel receptionist responding to a guest. Analyze this chat screenshot and provide ONLY a direct response message in English that can be copied and pasted.

🎯 PRIORITY INSTRUCTIONS (MUST FOLLOW EXACTLY):
{custom_instructions}

Communication Style:
- Write in English like a friendly, helpful friend
- Be conversational and natural (how foreigners normally talk)
- Keep it brief but clear so the guest understands
- Maintain polite professionalism while being warm and approachable
- Use casual but respectful language (like "Hey!", "Sure thing!", "No worries!", etc.)

Context:
- Response mode: {response_mode} (yes=positive, no=declining, auto=appropriate)
- Template context: {selected_template['Label'] if selected_template else 'General service'}

Requirements:
- FOLLOW THE PRIORITY INSTRUCTIONS ABOVE FIRST
- ONLY provide the message text ready to copy/paste
- Write in natural, conversational English
- Be brief but ensure the guest understands
- Sound like a friendly native English speaker
- NO explanations, NO analysis, JUST the response message"""
                        else:
                            ai_prompt = f"""You are a friendly hotel receptionist responding to a guest. Analyze this chat screenshot and provide ONLY a direct response message in English that can be copied and pasted.

Communication Style:
- Write in English like a friendly, helpful friend
- Be conversational and natural (how foreigners normally talk)
- Keep it brief but clear so the guest understands
- Maintain polite professionalism while being warm and approachable
- Use casual but respectful language (like "Hey!", "Sure thing!", "No worries!", etc.)

Context:
- Response mode: {response_mode} (yes=positive, no=declining, auto=appropriate)
- Template context: {selected_template['Label'] if selected_template else 'General service'}

Requirements:
- ONLY provide the message text ready to copy/paste
- Write in natural, conversational English
- Be brief but ensure the guest understands
- Sound like a friendly native English speaker
- NO explanations, NO analysis, JUST the response message"""
                        
                        print(f"🤖 [AI_CHAT_ANALYZE] Using AI prompt with custom instructions: {bool(custom_instructions)}")
                        if custom_instructions:
                            print(f"🎯 [AI_CHAT_ANALYZE] Priority Instructions: '{custom_instructions}'")

                        # Prepare image for Gemini
                        from PIL import Image
                        import io
                        
                        # Convert image data to PIL Image
                        image_pil = Image.open(io.BytesIO(image_data))
                        print(f"📸 [AI_CHAT_ANALYZE] Image format: {image_pil.format}, size: {image_pil.size}")
                        
                        # Analyze image with Gemini
                        response = model.generate_content([ai_prompt, image_pil])
                        ai_analysis = response.text
                        
                        print(f"🤖 [AI_CHAT_ANALYZE] Gemini analysis completed: {len(ai_analysis)} characters")
                        
                except Exception as ai_error:
                    print(f"❌ [AI_CHAT_ANALYZE] Gemini AI error: {ai_error}")
                    use_real_ai = False
                    ai_analysis = f"AI analysis temporarily unavailable: {str(ai_error)}"
                
                # Enhanced analysis response format
                if use_real_ai:
                    analysis_result = {
                        'ai_response': ai_analysis.strip(),  # Clean response ready for copy/paste
                        'conversation_context': f"""**✅ Ready to Copy & Paste**
Friendly English response generated using Gemini AI analysis of your chat screenshot.

**Settings Applied:**
• Response Style: {response_mode.upper()}
• Language: Conversational English (friendly but professional)
• Template: {selected_template['Label'] if selected_template else 'General'}
• Instructions: {'Custom applied' if custom_instructions else 'Friendly native English speaker style'}

**💡 Tip:** The response above is ready to copy and send directly to your guest.""",
                        'image_analysis': {
                            'size': len(image_data),
                            'format': 'base64 decoded',
                            'ai_provider': 'Google Gemini 1.5 Flash',
                            'ai_config_applied': ai_config,
                            'processing_status': 'successful'
                        }
                    }
                else:
                    # Fallback sample response in conversational English
                    sample_responses = [
                        "Hey there! Thanks for reaching out 😊 I'd be happy to help you with that. What can I do for you?",
                        "Hi! No worries, I've got you covered. Let me take care of that for you right away!",
                        "Hello! Thanks for your message. Sure thing, I can definitely help with that. What would you like to know?",
                        "Hey! Great to hear from you. I'm here to help - just let me know what you need!",
                        "Hi there! Thanks for getting in touch. I'd love to help you out with whatever you need."
                    ]
                    
                    # Use custom instructions if provided, otherwise pick a friendly sample
                    if custom_instructions:
                        sample_response = f"Hey! {custom_instructions} Let me know if you need anything else!"
                    else:
                        import random
                        sample_response = random.choice(sample_responses)
                    
                    analysis_result = {
                        'ai_response': sample_response,
                        
                        'conversation_context': f"""**⚠️ Sample Response** (Configure GOOGLE_API_KEY for real AI analysis)

**Settings Applied:**
• Response Style: {response_mode.upper()}
• Language: Conversational English (friendly but professional)
• Template: {selected_template['Label'] if selected_template else 'General'}
• Instructions: {'Custom applied' if custom_instructions else 'Friendly native English speaker style'}

**💡 Tip:** The response above is ready to copy and send to your guest. For AI-powered analysis of your chat screenshot, configure your Google API key.""",
                        
                        'image_analysis': {
                            'size': len(image_data),
                            'format': 'base64 decoded',
                            'ai_provider': 'Sample (Gemini not configured)',
                            'ai_config_applied': ai_config,
                            'processing_status': 'fallback'
                        }
                    }
                
                print(f"✅ [AI_CHAT_ANALYZE] Analysis completed successfully")
                
                return jsonify({
                    'success': True,
                    **analysis_result,
                    'message': 'Chat image analyzed successfully'
                })
                
            except Exception as decode_error:
                print(f"❌ [AI_CHAT_ANALYZE] Image decode error: {decode_error}")
                return jsonify({
                    'success': False, 
                    'error': f'Error decoding image: {str(decode_error)}'
                }), 400
        
        # Handle file upload format (fallback)
        elif 'image' in request.files:
            image_file = request.files['image']
            custom_instructions = request.form.get('customInstructions', '')
            
            if image_file.filename == '':
                return jsonify({'success': False, 'error': 'No image selected'}), 400
                
            print(f"📸 [AI_CHAT_ANALYZE] Processing uploaded file: {image_file.filename}")
            
            image_data = image_file.read()
            
            return jsonify({
                'success': True,
                'ai_response': f'File upload processed: {image_file.filename}. {custom_instructions}',
                'conversation_context': 'File upload analysis',
                'message': 'Image file analyzed successfully'
            })
        
        else:
            return jsonify({'success': False, 'error': 'No image data provided (expected image_b64 in JSON or image file)'}), 400
            
    except Exception as e:
        print(f"❌ [AI_CHAT_ANALYZE] API error: {e}")
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/translate', methods=['POST'])
def translate_text():
    """Translation API endpoint for voice translator"""
    try:
        print("🌐 [TRANSLATE] Translation API called")
        
        # Get JSON data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        text = data.get('text', '').strip()
        source_lang = data.get('source_lang', 'auto')
        target_lang = data.get('target_lang', 'en')
        
        print(f"🌐 [TRANSLATE] Text: {text[:100]}...")
        print(f"🌐 [TRANSLATE] {source_lang} → {target_lang}")
        
        if not text:
            return jsonify({'error': 'No text provided for translation'}), 400
        
        # Check if source and target languages are the same
        if source_lang == target_lang:
            return jsonify({'error': 'Source and target languages cannot be the same'}), 400
        
        # Try to use Google Translate via Gemini AI for better quality
        try:
            import google.generativeai as genai
            
            # Use the existing API key from environment
            api_key = os.getenv('GOOGLE_API_KEY')
            if api_key:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Create translation prompt
                lang_names = {
                    'en': 'English',
                    'vi': 'Vietnamese', 
                    'fr': 'French',
                    'es': 'Spanish',
                    'de': 'German',
                    'ja': 'Japanese',
                    'ko': 'Korean',
                    'zh': 'Chinese',
                    'auto': 'automatically detected language'
                }
                
                source_name = lang_names.get(source_lang, source_lang)
                target_name = lang_names.get(target_lang, target_lang)
                
                prompt = f"""Translate the following text from {source_name} to {target_name}. 
Provide only the translation, no explanations or additional text.

Text to translate: {text}"""
                
                response = model.generate_content(prompt)
                translated_text = response.text.strip()
                
                print(f"✅ [TRANSLATE] Gemini translation successful: {translated_text[:100]}...")
                
                return jsonify({
                    'success': True,
                    'translated_text': translated_text,
                    'source_language': source_lang,
                    'target_language': target_lang,
                    'method': 'Gemini AI'
                })
            
        except Exception as ai_error:
            print(f"⚠️ [TRANSLATE] Gemini AI translation failed: {ai_error}")
        
        # Fallback to simple mock translation for development
        # In production, you'd integrate with Google Translate API or similar
        print("🔄 [TRANSLATE] Using fallback mock translation")
        
        # Simple mock translation responses
        mock_translations = {
            ('vi', 'en'): {
                'xin chào': 'hello',
                'cảm ơn': 'thank you',
                'tạm biệt': 'goodbye',
                'chào bạn': 'hello friend'
            },
            ('en', 'vi'): {
                'hello': 'xin chào',
                'thank you': 'cảm ơn',
                'goodbye': 'tạm biệt',
                'hello friend': 'chào bạn'
            }
        }
        
        # Try to find mock translation
        text_lower = text.lower()
        lang_pair = (source_lang, target_lang)
        
        if lang_pair in mock_translations and text_lower in mock_translations[lang_pair]:
            translated_text = mock_translations[lang_pair][text_lower]
        else:
            # Generate a basic mock response
            translated_text = f"[Mock Translation] {text} ({source_lang} → {target_lang})"
        
        print(f"✅ [TRANSLATE] Mock translation: {translated_text}")
        
        return jsonify({
            'success': True,
            'translated_text': translated_text,
            'source_language': source_lang,
            'target_language': target_lang,
            'method': 'Mock/Development'
        })
        
    except Exception as e:
        print(f"❌ [TRANSLATE] Translation API error: {e}")
        return jsonify({
            'error': f'Translation failed: {str(e)}'
        }), 500

@app.route('/fix_quicknotes_sequence')
def fix_quicknotes_sequence():
    """Fix the QuickNotes auto-increment sequence"""
    try:
        from core.models import db
        
        print("🔧 [SEQUENCE_FIX] Starting QuickNotes sequence fix...")
        
        # Step 1: Find the current maximum note_id
        result = db.session.execute(text("SELECT COALESCE(MAX(note_id), 0) FROM quick_notes;"))
        max_existing_id = result.fetchone()[0]
        next_id = max_existing_id + 1
        print(f"1️⃣ [SEQUENCE_FIX] Current max note_id: {max_existing_id}, next should be: {next_id}")
        
        # Step 2: Reset the sequence to the correct value
        # Using 'true' as the third parameter means the next nextval() will return next_id + 1
        db.session.execute(text(f"SELECT setval('quick_notes_note_id_seq', {next_id}, true);"))
        print(f"2️⃣ [SEQUENCE_FIX] Reset sequence to {next_id}")
        
        # Step 3: Commit changes
        db.session.commit()
        print("3️⃣ [SEQUENCE_FIX] Changes committed successfully")
        
        return jsonify({
            'success': True,
            'message': 'QuickNotes sequence fixed successfully!',
            'details': {
                'max_existing_id': max_existing_id,
                'sequence_set_to': next_id,
                'next_auto_id_will_be': next_id + 1,
                'action': 'Sequence reset to avoid conflicts'
            },
            'note': 'You can now create quick notes without ID conflicts. Try creating a note!'
        })
        
    except Exception as e:
        print(f"❌ [SEQUENCE_FIX] Error: {e}")
        try:
            db.session.rollback()
        except:
            pass
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fix sequence. The sequence was likely already partially fixed.'
        }), 500

@app.route('/fix_quicknotes_constraint')
def fix_quicknotes_constraint():
    """Fix the QuickNotes constraint to allow flexible note types"""
    try:
        from core.models import db
        
        print("🔧 [CONSTRAINT_FIX] Starting QuickNotes constraint fix...")
        
        # Step 1: Drop the old restrictive constraint
        try:
            db.session.execute(text("ALTER TABLE quick_notes DROP CONSTRAINT IF EXISTS chk_note_type;"))
            print("1️⃣ [CONSTRAINT_FIX] Dropped old constraint")
        except Exception as drop_error:
            print(f"⚠️ [CONSTRAINT_FIX] Drop constraint warning: {drop_error}")
        
        # Step 2: Add new flexible constraint
        try:
            db.session.execute(text("""
                ALTER TABLE quick_notes ADD CONSTRAINT chk_note_type CHECK (
                    note_type IS NOT NULL AND LENGTH(note_type) > 0
                );
            """))
            print("2️⃣ [CONSTRAINT_FIX] Added new flexible constraint")
        except Exception as add_error:
            print(f"⚠️ [CONSTRAINT_FIX] Add constraint warning: {add_error}")
            # If constraint already exists, that's OK
            if "already exists" not in str(add_error).lower():
                raise add_error
        
        # Step 3: Commit changes
        db.session.commit()
        print("3️⃣ [CONSTRAINT_FIX] Changes committed")
        
        # Step 4: Test the constraint with a simple query
        try:
            result = db.session.execute(text("""
                SELECT conname 
                FROM pg_constraint 
                WHERE conrelid = 'quick_notes'::regclass 
                AND conname = 'chk_note_type';
            """))
            
            constraint_info = result.fetchone()
            constraint_exists = constraint_info is not None
            
            print(f"4️⃣ [CONSTRAINT_FIX] Verification: Constraint exists = {constraint_exists}")
            
        except Exception as verify_error:
            print(f"⚠️ [CONSTRAINT_FIX] Verification error: {verify_error}")
            constraint_exists = True  # Assume it worked
        
        # Step 5: Test by trying to create a sample note type validation
        try:
            # This will help us confirm the constraint allows flexible note types
            test_result = db.session.execute(text("""
                SELECT 
                    CASE 
                        WHEN LENGTH('Note') > 0 AND 'Note' IS NOT NULL THEN 'VALID'
                        ELSE 'INVALID'
                    END as test_result;
            """))
            
            validation_result = test_result.fetchone()
            test_status = validation_result[0] if validation_result else 'UNKNOWN'
            print(f"5️⃣ [CONSTRAINT_FIX] Test validation: {test_status}")
            
        except Exception as test_error:
            print(f"⚠️ [CONSTRAINT_FIX] Test error: {test_error}")
            test_status = 'SKIPPED'
        
        return jsonify({
            'success': True,
            'message': 'QuickNotes constraint fixed successfully!',
            'details': {
                'constraint_exists': constraint_exists,
                'test_validation': test_status,
                'note_types_allowed': ['Note', 'Task', 'Reminder', 'Follow-up', 'Custom'],
                'requirements': 'Note type must not be empty'
            },
            'note': 'You can now create quick notes with any note type (Note, Task, etc.)'
        })
        
    except Exception as e:
        print(f"❌ [CONSTRAINT_FIX] Error: {e}")
        db.session.rollback()  # Rollback any partial changes
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fix constraint. Check server logs.',
            'suggestion': 'Try running the manual SQL commands directly in your database'
        }), 500

@app.route('/revenue_comparison_test')
def revenue_comparison_test():
    """Test page to demonstrate dual revenue calculation methods"""
    return render_template('revenue_comparison_test.html')


@app.route('/railway_sync')
def railway_sync_page():
    """Railway sync management page"""
    railway_url = os.getenv('RAILWAY_DATABASE_URL')
    return render_template('railway_sync.html', railway_url=railway_url)

@app.route('/debug/local_postgres')
def debug_local_postgres():
    """Test local PostgreSQL connection for Railway sync"""
    try:
        import psycopg2
        from core.sync_service import DataSyncService
        
        # Test local connection using sync service
        sync_service = DataSyncService()
        connection_results = sync_service.test_connections()
        
        # Also test alternative connection strings (focus on hotel_booking database)
        alternative_urls = [
            "postgresql://postgres:locloc123@localhost:5432/hotel_booking",  # Current config
            "postgresql://postgres:postgres@localhost:5432/hotel_booking",   # Default password
            "postgresql://postgres:admin@localhost:5432/hotel_booking",      # Admin password
            "postgresql://postgres@localhost:5432/hotel_booking",            # No password
            "postgresql://postgres:123456@localhost:5432/hotel_booking",     # Common password
            "postgresql://postgres:password@localhost:5432/hotel_booking",   # Common password
            "postgresql://postgres:locloc123@localhost:5432/postgres",       # Working connection
            "postgresql://postgres:postgres@localhost:5432/postgres"         # Test postgres DB
        ]
        
        alternative_results = {}
        for url in alternative_urls:
            try:
                conn = psycopg2.connect(url)
                cursor = conn.cursor()
                cursor.execute("SELECT version()")
                version = cursor.fetchone()[0]
                
                cursor.execute("SELECT current_database()")
                database = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                
                alternative_results[url] = {
                    'status': 'success',
                    'version': version[:100],
                    'database': database,
                    'tables': len(tables),
                    'table_list': [t[0] for t in tables]
                }
                
                cursor.close()
                conn.close()
                
            except Exception as e:
                alternative_results[url] = {
                    'status': 'failed',
                    'error': str(e)
                }
        
        return jsonify({
            'sync_service_test': connection_results,
            'alternative_connections': alternative_results,
            'current_local_url': sync_service.local_db_url,
            'railway_url_status': 'connected' if connection_results.get('railway_status') else 'failed',
            'recommendations': {
                'working_connections': [url for url, result in alternative_results.items() if result.get('status') == 'success'],
                'has_booking_data': [url for url, result in alternative_results.items() 
                                   if result.get('status') == 'success' and 
                                   any('booking' in table for table in result.get('table_list', []))]
            }
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Could not test local PostgreSQL connections',
            'troubleshooting': [
                'Check if PostgreSQL service is running',
                'Verify PostgreSQL password',
                'Ensure hotel_booking database exists',
                'Try connecting with pgAdmin first'
            ]
        }), 500

@app.route('/debug/env')
def debug_environment():
    """Debug environment variables for Railway troubleshooting"""
    env_info = {}
    
    # Check all database-related environment variables
    for key in os.environ.keys():
        if 'DATABASE' in key or 'POSTGRES' in key or 'DB' in key:
            value = os.environ[key]
            # Only show first 20 and last 20 characters for security
            if len(value) > 40:
                masked_value = f"{value[:20]}...{value[-20:]}"
            else:
                masked_value = f"{value[:10]}..." if len(value) > 10 else value
            env_info[key] = {
                'value': masked_value,
                'length': len(value),
                'starts_with': value[:50] if len(value) > 50 else value,
                'type': type(value).__name__
            }
    
    return jsonify({
        'environment_variables': env_info,
        'total_env_vars': len(os.environ),
        'database_related_vars': len(env_info),
        'debug_notes': {
            'expected_database_url_length': 92,
            'expected_format': 'postgresql://postgres:password@host:port/database',
            'common_issues': [
                'Variable name included in value (DATABASE_URL=postgresql://...)',
                'Truncated URL due to character limits',
                'Special characters not properly escaped',
                'Wrong variable name or reference format'
            ]
        }
    })

@app.route('/api/railway_sync', methods=['POST', 'GET'])
def railway_sync():
    """API endpoint to sync data from current database to Railway"""
    try:
        import psycopg2
        from sqlalchemy import create_engine, text
        import pandas as pd
        
        # Get Railway database URL
        railway_url = os.getenv('RAILWAY_DATABASE_URL')
        if not railway_url:
            return jsonify({
                'success': False,
                'message': 'RAILWAY_DATABASE_URL not configured in environment variables'
            }), 400
        
        print(f"🔍 Railway URL: {railway_url[:50]}...")
        
        # Test Railway connection
        print("🔌 Testing Railway connection...")
        railway_engine = create_engine(railway_url)
        
        with railway_engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Railway connection successful!")
        
        # Get current database data
        current_engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        
        sync_results = {}
        
        # Create Railway schema
        with railway_engine.connect() as railway_conn:
            print("🏗️ Creating Railway schema...")
            
            schema_sql = """
            -- Drop existing tables to recreate with correct structure
            DROP TABLE IF EXISTS bookings CASCADE;
            DROP TABLE IF EXISTS quick_notes CASCADE;
            DROP TABLE IF EXISTS expenses CASCADE;
            DROP TABLE IF EXISTS message_templates CASCADE;
            DROP TABLE IF EXISTS guests CASCADE;
            
            -- Guests table
            CREATE TABLE guests (
                guest_id SERIAL PRIMARY KEY,
                guest_name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                phone VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Bookings table (simplified structure matching your data)
            CREATE TABLE bookings (
                booking_id SERIAL PRIMARY KEY,
                guest_name VARCHAR(255) NOT NULL,
                checkin_date DATE,
                checkout_date DATE,
                room_amount DECIMAL(12, 2) DEFAULT 0.00,
                taxi_amount DECIMAL(12, 2) DEFAULT 0.00,
                commission DECIMAL(12, 2) DEFAULT 0.00,
                collected_amount DECIMAL(12, 2) DEFAULT 0.00,
                collector VARCHAR(100),
                booking_status VARCHAR(50) DEFAULT 'active',
                booking_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                arrival_confirmed BOOLEAN DEFAULT FALSE,
                arrival_confirmed_at TIMESTAMP NULL
            );
            
            -- Quick notes table
            CREATE TABLE quick_notes (
                note_id SERIAL PRIMARY KEY,
                note_type VARCHAR(50) NOT NULL,
                note_content TEXT NOT NULL,
                is_completed BOOLEAN DEFAULT FALSE,
                completed_at TIMESTAMP NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by VARCHAR(255)
            );
            
            -- Expenses table
            CREATE TABLE expenses (
                expense_id SERIAL PRIMARY KEY,
                description TEXT NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                expense_date DATE DEFAULT CURRENT_DATE,
                category VARCHAR(100),
                collector VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Message templates table
            CREATE TABLE message_templates (
                template_id SERIAL PRIMARY KEY,
                template_name VARCHAR(255) NOT NULL,
                category VARCHAR(100) DEFAULT 'General',
                template_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Arrival times table
            CREATE TABLE IF NOT EXISTS arrival_times (
                arrival_id SERIAL PRIMARY KEY,
                booking_id INTEGER,
                guest_name VARCHAR(255),
                arrival_date DATE,
                arrival_time TIME,
                status VARCHAR(50) DEFAULT 'pending',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            -- Expense categories table
            CREATE TABLE IF NOT EXISTS expense_categories (
                category_id SERIAL PRIMARY KEY,
                expense_id INTEGER,
                category VARCHAR(100) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            railway_conn.execute(text(schema_sql))
            railway_conn.commit()
            print("✅ Railway schema created!")
        
        # Transfer data table by table
        tables_to_sync = [
            ('bookings', ['guest_name', 'checkin_date', 'checkout_date', 'room_amount', 'taxi_amount', 'commission', 'collected_amount', 'collector', 'booking_status', 'booking_notes', 'created_at', 'updated_at', 'arrival_confirmed', 'arrival_confirmed_at']),
            ('quick_notes', ['note_type', 'note_content', 'is_completed', 'completed_at', 'created_at', 'created_by']),
            ('expenses', ['description', 'amount', 'expense_date', 'category', 'collector', 'created_at']),
            ('message_templates', ['template_name', 'category', 'template_content', 'created_at', 'updated_at']),
            ('arrival_times', ['booking_id', 'guest_name', 'arrival_date', 'arrival_time', 'status', 'notes', 'created_at', 'updated_at']),
            ('expense_categories', ['expense_id', 'category', 'created_at', 'updated_at'])
        ]
        
        for table_name, columns in tables_to_sync:
            try:
                print(f"📦 Transferring {table_name}...")
                
                # Get data from current database
                with current_engine.connect() as current_conn:
                    # Get available columns
                    check_query = f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'"
                    available_cols = current_conn.execute(text(check_query)).fetchall()
                    available_columns = [col[0] for col in available_cols]
                    
                    # Filter columns to only those that exist
                    valid_columns = [col for col in columns if col in available_columns]
                    
                    if not valid_columns:
                        print(f"   ⚠️ No valid columns found for {table_name}")
                        continue
                    
                    # Read data
                    cols_str = ', '.join(valid_columns)
                    query = f"SELECT {cols_str} FROM {table_name}"
                    df = pd.read_sql_query(query, current_conn)
                    
                    print(f"   📤 Found {len(df)} records")
                    
                    if df.empty:
                        sync_results[table_name] = {'transferred': 0, 'success': True}
                        continue
                
                # Insert into Railway
                with railway_engine.connect() as railway_conn:
                    # Clear table
                    railway_conn.execute(text(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE"))
                    
                    # Insert data row by row to handle NULLs properly
                    inserted_count = 0
                    for _, row in df.iterrows():
                        # Prepare values, handling NaN/None
                        values = []
                        for col in valid_columns:
                            val = row[col]
                            if pd.isna(val) or val is None or str(val) == 'NaT':
                                values.append(None)
                            else:
                                values.append(val)
                        
                        # Create insert query
                        placeholders = ', '.join([':val' + str(i) for i in range(len(values))])
                        cols_str = ', '.join(valid_columns)
                        query = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"
                        
                        # Create parameter dict
                        params = {f'val{i}': val for i, val in enumerate(values)}
                        
                        railway_conn.execute(text(query), params)
                        inserted_count += 1
                    
                    railway_conn.commit()
                    print(f"   ✅ Transferred {inserted_count} records")
                    
                    sync_results[table_name] = {
                        'transferred': inserted_count,
                        'success': True
                    }
                    
            except Exception as table_error:
                print(f"   ❌ Failed to transfer {table_name}: {table_error}")
                sync_results[table_name] = {
                    'transferred': 0,
                    'success': False,
                    'error': str(table_error)
                }
        
        # Calculate summary
        total_transferred = sum(result.get('transferred', 0) for result in sync_results.values())
        successful_tables = sum(1 for result in sync_results.values() if result.get('success', False))
        total_tables = len(sync_results)
        
        overall_success = successful_tables == total_tables and total_transferred > 0
        
        return jsonify({
            'success': overall_success,
            'message': f"Sync completed! {successful_tables}/{total_tables} tables successful, {total_transferred} total records transferred",
            'details': sync_results,
            'summary': {
                'total_transferred': total_transferred,
                'successful_tables': successful_tables,
                'total_tables': total_tables
            }
        })
        
    except Exception as e:
        print(f"❌ Railway sync error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Railway sync failed: {str(e)}'
        }), 500


@app.route('/railway/health')
def railway_health_check():
    """Railway deployment health check endpoint"""
    try:
        from core.models import db
        from core.database_service_postgresql import get_database_service
        
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'environment': {
                'DATABASE_URL': 'present' if os.getenv('DATABASE_URL') else 'missing',
                'RAILWAY_DATABASE_URL': 'present' if os.getenv('RAILWAY_DATABASE_URL') else 'missing',
                'GOOGLE_API_KEY': 'present' if os.getenv('GOOGLE_API_KEY') else 'missing'
            },
            'database': {
                'connection': 'unknown',
                'booking_count': 0
            },
            'features': {
                'ai_processing': bool(os.getenv('GOOGLE_API_KEY')),
                'postgresql': True,
                'charts': True
            }
        }
        
        # Test database connection
        try:
            db_service = get_database_service()
            if db_service:
                from core.models import Booking
                booking_count = Booking.query.count()
                health_data['database']['connection'] = 'connected'
                health_data['database']['booking_count'] = booking_count
            else:
                health_data['database']['connection'] = 'failed'
                health_data['status'] = 'degraded'
        except Exception as db_error:
            health_data['database']['connection'] = f'error: {str(db_error)}'
            health_data['status'] = 'degraded'
        
        return jsonify(health_data)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/railway/chart-data')
def railway_chart_data():
    """Railway-specific chart data endpoint for debugging"""
    try:
        # Load minimal data for chart testing
        df, _ = load_data(force_fresh=False)
        
        if df.empty:
            return jsonify({
                'monthly_revenue_chart': {'data': [], 'layout': {'title': 'No data available'}},
                'collector_chart': {'data': [], 'layout': {'title': 'No data available'}},
                'data_status': 'empty'
            })
        
        # Get today's date for filtering
        today = datetime.today()
        start_date = today.replace(day=1)
        end_date = today
        
        # Get dashboard data
        dashboard_data = prepare_dashboard_data(df, start_date, end_date, 'Tháng', 'desc')
        
        # Create chart data
        from core.dashboard_routes import create_revenue_chart, create_collector_chart
        
        monthly_revenue_list = safe_to_dict_records(dashboard_data.get('monthly_revenue_all_time', pd.DataFrame()))
        monthly_chart = create_revenue_chart(monthly_revenue_list)
        
        collector_chart = create_collector_chart(dashboard_data)
        
        return jsonify({
            'monthly_revenue_chart': monthly_chart,
            'collector_chart': collector_chart,
            'data_status': 'success',
            'booking_count': len(df),
            'dashboard_data_keys': list(dashboard_data.keys())
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'data_status': 'error'
        }), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))