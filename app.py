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
from core.logic import (
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
from core.database_service import init_database_service, get_database_service, DatabaseConfig

# Configuration
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, template_folder=BASE_DIR / "templates", static_folder=BASE_DIR / "static")

# Production configuration
app.config['ENV'] = 'production'
app.config['DEBUG'] = False
app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")

# PostgreSQL-only database configuration
database_url = os.getenv('DATABASE_URL')
if not database_url or 'port' in database_url.replace('postgresql://', '').split('@')[0]:
    # Fallback for Railway if DATABASE_URL is not properly set
    print("⚠️ DATABASE_URL not properly configured. Please add PostgreSQL database in Railway.")
    print("   1. Go to Railway dashboard")
    print("   2. Click '+ New' → 'Database' → 'PostgreSQL'") 
    print("   3. Add environment variable: DATABASE_URL = ${{Postgres.DATABASE_URL}}")
    database_url = "postgresql://postgres:password@localhost:5432/hotel_booking"  # Fallback for testing

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
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
    dashboard_data = prepare_dashboard_data(df, start_date, end_date, sort_by, sort_order)

    # Process all dashboard data
    processed_data = process_dashboard_data(df, start_date, end_date, sort_by, sort_order, dashboard_data)

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
        
        # Auto duplicate filter
        duplicate_report = {'total_groups': 0, 'total_duplicates': 0, 'filtered_count': 0}
        if auto_filter:
            duplicates = analyze_existing_duplicates(filtered_df)
            duplicate_booking_ids = set()
            for group in duplicates['duplicate_groups']:
                for booking in group['bookings'][1:]:  # Keep first, mark others as duplicates
                    duplicate_booking_ids.add(booking['Số đặt phòng'])
            
            # Create duplicate report for template
            duplicate_report = {
                'total_groups': duplicates.get('total_groups', 0),
                'total_duplicates': duplicates.get('total_duplicates', 0),
                'filtered_count': len(duplicate_booking_ids)
            }
            
            filtered_df = filtered_df[~filtered_df['Số đặt phòng'].isin(duplicate_booking_ids)]
        
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
            
            update_data = {
                'guest_name': request.form.get('guest_name'),
                'checkin_date': datetime.strptime(checkin_date_str, '%Y-%m-%d').date(),
                'checkout_date': datetime.strptime(checkout_date_str, '%Y-%m-%d').date(),
                'room_amount': float(request.form.get('room_amount', 0)),
                'commission': float(request.form.get('commission', 0)),
                'taxi_amount': float(request.form.get('taxi_amount', 0)),
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
            
            if add_expense_to_database(expense_data):
                return jsonify({'success': True, 'status': 'success', 'message': 'Expense added successfully'})
            else:
                return jsonify({'success': False, 'status': 'error', 'message': 'Failed to add expense'}), 400
        
        except Exception as e:
            return jsonify({'success': False, 'status': 'error', 'message': str(e)}), 500

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

@app.route('/api/process_pasted_image', methods=['POST'])
def process_pasted_image():
    """Process image with Gemini AI (no Google Sheets)"""
    try:
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
        
        # Extract booking info using Gemini
        booking_info = extract_booking_info_from_image_content(
            image_data, 
            GOOGLE_API_KEY
        )
        
        # Check if extraction was successful
        if 'error' in booking_info:
            return jsonify(booking_info), 400
        
        # Wrap successful extraction in expected format for frontend
        print(f"✅ Booking info extracted successfully: {booking_info}")
        return jsonify({
            'success': True,
            'bookings': [booking_info]  # Frontend expects array format
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            note = db_service.create_quick_note(
                note_type=data.get('note_type', 'general'),
                content=data.get('content', ''),
                guest_name=data.get('guest_name'),
                booking_id=data.get('booking_id'),
                priority=data.get('priority', 'normal')
            )
            return jsonify(note.to_dict()), 201
    
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
            note = db_service.update_quick_note(note_id, data)
            if not note:
                return jsonify({'error': 'Note not found'}), 404
            return jsonify(note.to_dict())
        
        elif request.method == 'DELETE':
            if db_service.delete_quick_note(note_id):
                return jsonify({'message': 'Note deleted successfully'})
            else:
                return jsonify({'error': 'Note not found'}), 404
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
            arrival_time = db_service.upsert_arrival_time(
                booking_id=data.get('booking_id'),
                estimated_arrival=data.get('estimated_arrival'),
                notes=data.get('notes')
            )
            return jsonify(arrival_time.to_dict())
    
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
        # Basic validation
        if not data or 'name' not in data or 'content' not in data:
            return jsonify({'success': False, 'error': 'Name and content are required'}), 400
        
        # Create new template in database
        new_template = MessageTemplate(
            template_name=data['name'],
            category=data.get('category', 'General'),
            template_content=data['content']
        )
        
        # Save to database
        db.session.add(new_template)
        db.session.commit()
        
        print(f"📋 Templates API: Added new template '{data['name']}' with ID {new_template.template_id}")
        
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

@app.route('/api/templates/<template_id>', methods=['GET', 'DELETE'])
def handle_template(template_id):
    """Get or delete a specific template from PostgreSQL database"""
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))