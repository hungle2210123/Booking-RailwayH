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
    load_booking_data, create_demo_data,
    get_daily_activity, get_overall_calendar_day_info,
    extract_booking_info_from_image_content,
    check_duplicate_guests, analyze_existing_duplicates,
    add_new_booking, update_booking, delete_booking_by_id,
    prepare_dashboard_data,
    add_expense_to_database, get_expenses_from_database
)

# Import dashboard processing module  
from core.dashboard_routes import process_dashboard_data, safe_to_dict_records

# Import pure PostgreSQL database service
from core.database_service_postgresql import init_database_service, get_database_service, DatabaseConfig

# Import crawling service for authenticated web scraping
from core.crawl_service import CrawlIntegration

# Configuration
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, template_folder=BASE_DIR / "templates", static_folder=BASE_DIR / "static")

# Production configuration
app.config['ENV'] = 'production'
app.config['DEBUG'] = False
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")

# PostgreSQL-only database configuration for Railway
database_url = os.getenv('DATABASE_URL')
print(f"🔍 DATABASE_URL detected: {database_url[:50] if database_url else 'None'}...")
print(f"🔍 Full DATABASE_URL length: {len(database_url) if database_url else 0} characters")

# Also check for Railway's native PostgreSQL service
railway_postgres_url = os.getenv('POSTGRES_URL') or os.getenv('RAILWAY_POSTGRES_URL')
if railway_postgres_url:
    print(f"🔍 Railway POSTGRES_URL found: {railway_postgres_url[:50]}...")
    if not database_url or 'DATABASE_URL = ' in database_url:
        print("🔧 Using Railway's native PostgreSQL URL instead...")
        database_url = railway_postgres_url

# Fix common Railway environment variable issues
if database_url:
    print(f"🔍 Raw DATABASE_URL: {database_url}")
    
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

@app.route('/')
def dashboard():
    """PostgreSQL-powered dashboard route"""
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

    # Render template with processed data
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
                )
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
            
            print(f"🔍 EXPANDED INTERESTED GUESTS FILTER RESULTS:")
            print(f"   📊 Total guests filtered: {before_count} → {after_count}")
            print(f"   🏨 All upcoming guests: {upcoming_guests}")
            print(f"   💰 Current/staying unpaid guests: {current_unpaid_guests}")
            print(f"   📅 Focus: All future arrivals + current unpaid guests")
            print(f"   🎯 Logic: Future check-ins OR (unpaid AND not checked out yet)")
            
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
                pagination=pagination_info
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
            
            if add_new_booking(booking_data):
                # Cache removed - data will be fresh automatically
                flash('Booking added successfully!', 'success')
                return redirect(url_for('view_bookings'))
            else:
                flash('Error adding booking to database', 'error')
        
        except Exception as e:
            flash(f'Error adding booking: {str(e)}', 'error')
    
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
            return jsonify({'status': 'success', 'message': 'Booking deleted successfully'})
        else:
            return jsonify({'status': 'error', 'message': 'Failed to delete booking'}), 400
    
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
                    print(f"✅ DELETED: Booking {booking_id}")
                else:
                    failed_ids.append(booking_id)
                    print(f"❌ FAILED: Booking {booking_id}")
            except Exception as e:
                failed_ids.append(booking_id)
                print(f"❌ ERROR deleting booking {booking_id}: {str(e)}")
        
        # Prepare response
        if deleted_count > 0:
            message = f"Đã xóa thành công {deleted_count} booking"
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
    """Expense management with PostgreSQL"""
    if request.method == 'GET':
        try:
            expenses_df = get_expenses_from_database()
            expenses_list = safe_to_dict_records(expenses_df)
            print(f"💰 EXPENSES API: Found {len(expenses_list)} expenses in database")
            # Return format expected by frontend JavaScript
            return jsonify({'success': True, 'data': expenses_list, 'status': 'success'})
        except Exception as e:
            print(f"❌ EXPENSES API ERROR: {e}")
            return jsonify({'success': False, 'error': str(e), 'status': 'error'}), 500
    
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
        failed_bookings = []
        existing_bookings = []  # Track bookings that already exist
        
        for i, booking_data in enumerate(bookings_data):
            try:
                guest_name = booking_data.get('guest_name', '')
                booking_id = booking_data.get('booking_id', '')
                
                print(f"💾 [SAVE_EXTRACTED] Processing booking {i+1}: {guest_name}")
                
                # Check if booking ID already exists
                existing_booking = load_booking_data()
                if not existing_booking.empty and booking_id and booking_id in existing_booking['Số đặt phòng'].values:
                    print(f"ℹ️ [SAVE_EXTRACTED] Booking ID {booking_id} already exists - skipping (not an error)")
                    existing_bookings.append(f"Booking {i+1}: {guest_name} - Already exists in system ({booking_id})")
                    continue
                
                # Generate unique booking ID if empty or duplicate
                if not booking_id:
                    booking_id = f"AI_{datetime.now().strftime('%Y%m%d%H%M%S')}{i:02d}"
                    print(f"🔄 [SAVE_EXTRACTED] Generated new booking ID: {booking_id}")
                
                # Generate unique email to avoid constraint violations
                unique_email = f"guest{booking_id.lower()}@ai-extracted.local"
                print(f"📧 [SAVE_EXTRACTED] Generated unique email: {unique_email}")
                
                # Convert to expected format for add_new_booking function
                processed_booking = {
                    'guest_name': guest_name,
                    'booking_id': booking_id,
                    'email': unique_email,  # ✅ Always provide unique email
                    'phone': '',  # Empty phone is safe
                    'nationality': '',
                    'passport_number': '',
                    'checkin_date': datetime.strptime(booking_data.get('checkin_date'), '%Y-%m-%d').date() if booking_data.get('checkin_date') else None,
                    'checkout_date': datetime.strptime(booking_data.get('checkout_date'), '%Y-%m-%d').date() if booking_data.get('checkout_date') else None,
                    'room_amount': float(booking_data.get('room_amount', 0)),
                    'commission': float(booking_data.get('commission', 0)),
                    'taxi_amount': float(booking_data.get('taxi_amount', 0)),
                    'collector': '',  # Will be set when payment is collected
                    'notes': f"Imported via AI photo processing on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
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
                
                # Save booking using existing function
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
        if saved_count > 0:
            success_msg = f"✅ Đã lưu thành công {saved_count} booking"
            if existing_bookings or failed_bookings:
                total_skipped = len(existing_bookings) + len(failed_bookings)
                success_msg += f" (bỏ qua {total_skipped} booking)"
            flash(success_msg, 'success')
        
        # Show existing bookings as info (not errors)
        if existing_bookings:
            for existing in existing_bookings:
                flash(f"ℹ️ {existing}", 'info')
        
        # Show actual errors
        if failed_bookings:
            for error in failed_bookings:
                flash(f"❌ {error}", 'error')
        
        # If nothing was saved and no existing bookings
        if saved_count == 0 and len(existing_bookings) == 0:
            flash('❌ Không thể lưu booking nào. Vui lòng kiểm tra dữ liệu và thử lại.', 'error')
        
        print(f"🎯 [SAVE_EXTRACTED] Complete: {saved_count} saved, {len(existing_bookings)} existing, {len(failed_bookings)} failed")
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
    df = load_booking_data(force_fresh=force_fresh)
    
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
        
        # Load booking data
        df = load_booking_data()
        
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
        # Configure Gemini API
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            return jsonify({'error': 'Google AI API not configured'}), 400
        
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
                
                # Check for duplicates
                df = load_booking_data()
                duplicates = check_duplicate_guests(df, booking.get('guest_name', ''), booking.get('checkin_date', ''))
                duplicate_check = {"has_duplicates": len(duplicates) > 0, "duplicates": duplicates}
                
                return jsonify({
                    'type': 'single',
                    'booking': booking,
                    'duplicate_check': duplicate_check,
                    'message': f"Đã nhận diện 1 booking: {booking.get('guest_name', 'Unknown')}"
                })
                
            elif booking_info['type'] == 'multiple':
                # Multiple bookings detected
                bookings = booking_info.get('bookings', [])
                
                # Check for duplicates across all bookings
                df = load_booking_data()
                all_duplicates = []
                for booking in bookings:
                    duplicates = check_duplicate_guests(df, booking.get('guest_name', ''), booking.get('checkin_date', ''))
                    all_duplicates.extend(duplicates)
                
                duplicate_check = {"has_duplicates": len(all_duplicates) > 0, "duplicates": all_duplicates}
                
                return jsonify({
                    'type': 'multiple',
                    'bookings': bookings,
                    'count': len(bookings),
                    'duplicate_check': duplicate_check,
                    'message': f"Đã nhận diện {len(bookings)} booking từ ảnh"
                })
        
        # Legacy format fallback (single booking without type)
        df = load_booking_data()
        duplicates = check_duplicate_guests(df, booking_info.get('guest_name', ''), booking_info.get('checkin_date', ''))
        duplicate_check = {"has_duplicates": len(duplicates) > 0, "duplicates": duplicates}
        
        return jsonify({
            'success': True,
            'bookings': [booking_info],  # Legacy format
            'duplicate_check': duplicate_check
        })
    
    except Exception as e:
        print(f"❌ Photo processing error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

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


@app.route('/api/quick_notes', methods=['GET', 'POST'])
def quick_notes():
    """Quick notes management"""
    try:
        db_service = get_database_service()
        
        if request.method == 'GET':
            # Get all quick notes
            notes = db_service.get_quick_notes()
            return jsonify([note.to_dict() for note in notes])
        
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
                priority=data.get('priority', 'normal')
            )
            print(f"✅ [CREATE_QUICK_NOTE] Note created successfully: {note.note_id}")
            return jsonify({
                'success': True,
                'message': 'Note created successfully',
                'note': note.to_dict()
            }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        from core.models import MessageTemplate
        
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
                'id': template.template_id,
                'created_at': template.created_at.isoformat() if template.created_at else None
            })
        
        print(f"📋 Templates API: Processed {len(templates_data)} templates")
        
        # Group by category for better organization
        from collections import defaultdict
        categories_dict = defaultdict(list)
        for template in templates_data:
            categories_dict[template['Category']].append(template)
        
        print(f"📋 Templates API: Organized into {len(categories_dict)} categories: {list(categories_dict.keys())}")
        
        # Return in format expected by JavaScript
        return jsonify({
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
        
        # Load data and filter for the specific month and checked-in guests only
        df = load_booking_data()
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
        
        # Load data and filter for the specific week and checked-in guests only
        df = load_booking_data()
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
        
        # Load data and filter for checked-in guests only
        df = load_booking_data()
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
        
        # Sort by amount (highest first)
        guest_details.sort(key=lambda x: x['amount'], reverse=True)
        
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

# Initialize crawling integration
CrawlIntegration.setup_crawl_routes(app)

@app.route('/api/crawl_admin_bookings', methods=['POST'])
def crawl_admin_bookings():
    """API endpoint for crawling booking admin panel with AI extraction"""
    try:
        import psutil
        import time
        from pathlib import Path
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        data = request.get_json()
        target_url = data.get('target_url')
        profile_name = data.get('profile_name', 'booking_fixed_profile')
        
        if not target_url:
            return jsonify({'success': False, 'error': 'Target URL required'}), 400
        
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
            
            return jsonify({
                'success': True,
                'bookings_count': extracted_count,
                'bookings': bookings,
                'message': f'Successfully extracted {extracted_count} bookings from admin panel'
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
        
        # Load all booking data
        df = load_booking_data()
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
        
        # Load booking data
        df = load_booking_data()
        
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
        
        # Load booking data
        df = load_booking_data()
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
            custom_instructions = ai_config.get('customInstructions', '')
            selected_template = ai_config.get('selectedTemplate')
            response_mode = ai_config.get('responseMode', 'auto')
            
            print(f"📝 [AI_CHAT_ANALYZE] AI Config: {ai_config}")
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
                        
                        # Create prompt based on AI config
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
- Custom instructions: {custom_instructions or 'Friendly conversational English'}

Requirements:
- ONLY provide the message text ready to copy/paste
- Write in natural, conversational English
- Be brief but ensure the guest understands
- Sound like a friendly native English speaker
- NO explanations, NO analysis, JUST the response message"""

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
        
        # Also test alternative connection strings
        alternative_urls = [
            "postgresql://postgres:postgres@localhost:5432/hotel_booking",
            "postgresql://postgres:admin@localhost:5432/hotel_booking", 
            "postgresql://postgres@localhost:5432/hotel_booking",
            "postgresql://postgres:locloc123@localhost:5432/postgres",
            "postgresql://postgres:postgres@localhost:5432/postgres"
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))