"""
Hotel Booking System - Pure PostgreSQL Business Logic
All Google Sheets functionality removed - PostgreSQL only
"""

import pandas as pd
import numpy as np
import datetime
import re
import csv
import os
from typing import Dict, List, Optional, Tuple, Any
import json
import calendar
from io import BytesIO
from sqlalchemy import text
from flask import current_app

# Import only necessary libraries
try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import plotly.express as px
    import plotly.io as p_json
    import plotly
except ImportError:
    px = None
    p_json = None
    plotly = None

# ==============================================================================
# POSTGRESQL DATA ACCESS LAYER
# ==============================================================================

def get_db_connection():
    """Get database connection from Flask app context"""
    from .models import db
    return db.engine.connect()

def execute_query(query: str, params: dict = None, force_fresh: bool = False) -> pd.DataFrame:
    """Execute SQL query and return DataFrame"""
    try:
        if force_fresh:
            print("🔄 EXECUTE_QUERY: Using fresh database connection")
            # Force a new connection by disposing the pool
            from .models import db
            db.engine.dispose()
        
        with get_db_connection() as conn:
            result = pd.read_sql(text(query), conn, params=params or {})
            if force_fresh:
                print(f"🔄 EXECUTE_QUERY: Fresh query returned {len(result)} rows")
            return result
    except Exception as e:
        print(f"Database query error: {e}")
        return pd.DataFrame()

def execute_insert_update_delete(query: str, params: dict = None) -> bool:
    """Execute INSERT, UPDATE, or DELETE query"""
    try:
        with get_db_connection() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return True
    except Exception as e:
        print(f"Database operation error: {e}")
        return False

# ==============================================================================
# CORE DATA FUNCTIONS - POSTGRESQL ONLY
# ==============================================================================

def load_booking_data(force_fresh: bool = False) -> pd.DataFrame:
    """Load all booking data from PostgreSQL"""
    if force_fresh:
        print("🔄 FORCE FRESH: Loading data with fresh database connection")
    
    query = """
    SELECT 
        b.booking_id as "Số đặt phòng",
        g.full_name as "Tên người đặt", 
        '118 Hang Bac Hostel' as "Tên chỗ nghỉ",
        b.checkin_date as "Check-in Date",
        b.checkout_date as "Check-out Date",
        b.room_amount as "Tổng thanh toán",
        COALESCE(b.collected_amount, 0) as "Số tiền đã thu",
        b.commission as "Hoa hồng",
        b.taxi_amount as "Taxi",
        b.collector as "Người thu tiền",
        CASE 
            WHEN b.booking_status IN ('confirmed', 'ok', 'mới') THEN 'OK'
            WHEN b.booking_status IN ('cancelled', 'đã hủy') THEN 'Đã hủy'
            WHEN b.booking_status = 'pending' THEN 'Chờ xử lý'
            ELSE b.booking_status
        END as "Tình trạng",
        b.booking_notes as "Ghi chú thanh toán",
        'VND' as "Tiền tệ",
        'Hà Nội' as "Vị trí",
        'Không' as "Thành viên Genius",
        CASE WHEN b.taxi_amount > 0 THEN true ELSE false END as "Có taxi",
        CASE WHEN b.taxi_amount > 0 THEN false ELSE true END as "Không có taxi",
        b.created_at,
        b.updated_at
    FROM bookings b
    JOIN guests g ON b.guest_id = g.guest_id
    -- Exclude deleted bookings from all queries
    WHERE b.booking_status != 'deleted'
    ORDER BY b.checkin_date DESC
    """
    
    df = execute_query(query, force_fresh=force_fresh)
    
    if df.empty:
        return pd.DataFrame()
    
    # Data type conversions
    date_columns = ['Check-in Date', 'Check-out Date']
    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Numeric columns
    numeric_columns = ['Tổng thanh toán', 'Số tiền đã thu', 'Hoa hồng', 'Taxi']
    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    print(f"Loaded {len(df)} bookings from PostgreSQL")
    return df

def create_demo_data():
    """Create demo data in PostgreSQL (if needed for testing)"""
    from .models import db, Guest, Booking
    from datetime import datetime, timedelta
    
    try:
        # Check if demo data already exists
        existing_count = db.session.query(Booking).count()
        if existing_count > 0:
            print(f"Demo data already exists: {existing_count} bookings")
            return True
        
        # Create demo guests
        demo_guests = [
            Guest(full_name="Nguyễn Văn A", email="nguyenvana@email.com", phone="0123456789"),
            Guest(full_name="Trần Thị B", email="tranthib@email.com", phone="0987654321"),
            Guest(full_name="Lê Minh C", email="leminhc@email.com", phone="0369741852")
        ]
        
        for guest in demo_guests:
            db.session.add(guest)
        
        db.session.flush()  # Get guest IDs
        
        # Create demo bookings
        today = datetime.now().date()
        demo_bookings = [
            Booking(
                booking_id="DEMO001",
                guest_id=demo_guests[0].guest_id,
                checkin_date=today + timedelta(days=1),
                checkout_date=today + timedelta(days=3),
                room_amount=500000,
                commission=50000,
                taxi_amount=0,
                collector="Admin",
                booking_status="confirmed",
                booking_notes="Demo booking 1"
            ),
            Booking(
                booking_id="DEMO002", 
                guest_id=demo_guests[1].guest_id,
                checkin_date=today + timedelta(days=5),
                checkout_date=today + timedelta(days=7),
                room_amount=600000,
                commission=60000,
                taxi_amount=200000,
                collector="Admin",
                booking_status="confirmed",
                booking_notes="Demo booking 2"
            )
        ]
        
        for booking in demo_bookings:
            db.session.add(booking)
        
        db.session.commit()
        print("Demo data created successfully")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error creating demo data: {e}")
        return False

def add_new_booking(booking_data: Dict) -> bool:
    """Add new booking to PostgreSQL"""
    from .models import db, Guest, Booking
    import uuid
    
    try:
        print(f"🔍 [ADD_NEW_BOOKING] Processing: {booking_data.get('guest_name', 'Unknown')}")
        
        # Handle empty email - convert to None to avoid unique constraint issues
        email = booking_data.get('email', '').strip()
        if not email or len(email) == 0:
            email = None
            print(f"🔍 [ADD_NEW_BOOKING] Empty email converted to None")
        
        # Check if guest exists (only by name if no email)
        if email:
            guest = db.session.query(Guest).filter_by(
                full_name=booking_data.get('guest_name', ''),
                email=email
            ).first()
        else:
            # If no email, just check by name for potential match
            guest = db.session.query(Guest).filter_by(
                full_name=booking_data.get('guest_name', '')
            ).filter(Guest.email.is_(None)).first()
        
        if not guest:
            print(f"🔍 [ADD_NEW_BOOKING] Creating new guest")
            # Create new guest
            guest = Guest(
                full_name=booking_data.get('guest_name', ''),
                email=email,  # Will be None if empty
                phone=booking_data.get('phone', ''),
                nationality=booking_data.get('nationality', ''),
                passport_number=booking_data.get('passport_number', '')
            )
            db.session.add(guest)
            db.session.flush()
            print(f"✅ [ADD_NEW_BOOKING] New guest created: ID {guest.guest_id}")
        else:
            print(f"✅ [ADD_NEW_BOOKING] Existing guest found: ID {guest.guest_id}")
        
        # Generate unique booking ID if not provided
        booking_id = booking_data.get('booking_id', '').strip()
        if not booking_id:
            booking_id = f"PHOTO_{uuid.uuid4().hex[:8].upper()}"
            print(f"🔍 [ADD_NEW_BOOKING] Generated booking ID: {booking_id}")
        
        # Create new booking
        booking = Booking(
            booking_id=booking_id,
            guest_id=guest.guest_id,
            guest_name=booking_data.get('guest_name', ''),  # Denormalized for quick access
            checkin_date=booking_data.get('checkin_date'),
            checkout_date=booking_data.get('checkout_date'),
            room_amount=booking_data.get('room_amount', 0),
            commission=booking_data.get('commission', 0),
            taxi_amount=booking_data.get('taxi_amount', 0),
            collector=booking_data.get('collector', ''),
            booking_status='confirmed',
            booking_notes=booking_data.get('notes', '')
        )
        
        db.session.add(booking)
        db.session.commit()
        print(f"✅ [ADD_NEW_BOOKING] Successfully added booking: {booking_id}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ [ADD_NEW_BOOKING] Error adding booking: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_booking(booking_id: str, update_data: Dict) -> bool:
    """Update existing booking in PostgreSQL"""
    from .models import db, Booking, Guest
    
    try:
        print(f"[UPDATE_BOOKING] Updating booking {booking_id} with data: {update_data}")
        booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        if not booking:
            print(f"Booking {booking_id} not found")
            return False
        
        # Update guest info if provided
        if any(key in update_data for key in ['guest_name', 'email', 'phone']):
            guest = booking.guest
            if 'guest_name' in update_data:
                guest.full_name = update_data['guest_name']
            if 'email' in update_data:
                guest.email = update_data['email'] 
            if 'phone' in update_data:
                guest.phone = update_data['phone']
        
        # Update booking info
        if 'checkin_date' in update_data:
            booking.checkin_date = update_data['checkin_date']
        if 'checkout_date' in update_data:
            booking.checkout_date = update_data['checkout_date']
        if 'room_amount' in update_data:
            booking.room_amount = update_data['room_amount']
        if 'commission' in update_data:
            old_commission = booking.commission or 0
            new_commission = update_data['commission']
            booking.commission = new_commission
            print(f"[UPDATE_BOOKING] 💰 COMMISSION UPDATE:")
            print(f"[UPDATE_BOOKING]   - OLD commission: {old_commission}")
            print(f"[UPDATE_BOOKING]   - NEW commission: {new_commission}")
            print(f"[UPDATE_BOOKING]   - Type: {type(new_commission)}")
            print(f"[UPDATE_BOOKING]   - After assignment: {booking.commission}")
        if 'collected_amount' in update_data:
            old_collected_amount = booking.collected_amount or 0
            new_collected_amount = update_data['collected_amount']
            booking.collected_amount = new_collected_amount
            print(f"[UPDATE_BOOKING] 💰 COLLECTED AMOUNT UPDATE:")
            print(f"[UPDATE_BOOKING]   - OLD collected_amount: {old_collected_amount}")
            print(f"[UPDATE_BOOKING]   - NEW collected_amount: {new_collected_amount}")
            print(f"[UPDATE_BOOKING]   - Type: {type(new_collected_amount)}")
        if 'taxi_amount' in update_data:
            old_taxi_amount = booking.taxi_amount
            new_taxi_amount = update_data['taxi_amount']
            booking.taxi_amount = new_taxi_amount
            print(f"[UPDATE_BOOKING] 🚕 TAXI UPDATE:")
            print(f"[UPDATE_BOOKING]   - OLD taxi_amount: {old_taxi_amount}")
            print(f"[UPDATE_BOOKING]   - NEW taxi_amount: {new_taxi_amount}")
            print(f"[UPDATE_BOOKING]   - Type: {type(new_taxi_amount)}")
            print(f"[UPDATE_BOOKING]   - After assignment: {booking.taxi_amount}")
        if 'collector' in update_data:
            booking.collector = update_data['collector']
        if 'notes' in update_data:
            booking.booking_notes = update_data['notes']
        if 'booking_notes' in update_data:
            booking.booking_notes = update_data['booking_notes']
        if 'status' in update_data:
            booking.booking_status = update_data['status']
        
        # CRITICAL: Flush and refresh to ensure changes are visible to other connections
        db.session.flush()
        db.session.refresh(booking)
        db.session.commit()
        
        # Force clear any potential connection-level caching
        db.session.close()
        
        # NUCLEAR OPTION: Dispose entire connection pool to force fresh connections
        db.engine.dispose()
        print(f"[UPDATE_BOOKING] 💥 NUCLEAR: Disposed entire connection pool for fresh data")
        
        # VERIFICATION: Re-query the booking to verify the update was saved
        verification_booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        if verification_booking:
            print(f"[UPDATE_BOOKING] ✅ VERIFICATION - Booking after commit:")
            print(f"[UPDATE_BOOKING]   - taxi_amount: {verification_booking.taxi_amount}")
            print(f"[UPDATE_BOOKING]   - commission: {verification_booking.commission}")
            print(f"[UPDATE_BOOKING]   - collected_amount: {verification_booking.collected_amount}")
            print(f"[UPDATE_BOOKING]   - booking_notes: {verification_booking.booking_notes}")
        else:
            print(f"[UPDATE_BOOKING] ❌ VERIFICATION FAILED - Could not re-query booking {booking_id}")
        
        print(f"[UPDATE_BOOKING] ✅ Successfully updated booking: {booking_id}")
        print(f"[UPDATE_BOOKING] 🔄 Database session flushed and closed to ensure visibility")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating booking: {e}")
        return False

def delete_booking_by_id(booking_id: str) -> bool:
    """Delete booking from PostgreSQL"""
    from .models import db, Booking
    
    try:
        booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        if not booking:
            print(f"Booking {booking_id} not found")
            return False
        
        # Soft delete - mark as deleted
        booking.booking_status = 'deleted'
        db.session.commit()
        print(f"Deleted booking: {booking_id}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting booking: {e}")
        return False

# ==============================================================================
# DATA ANALYSIS FUNCTIONS
# ==============================================================================

def get_daily_activity(df: pd.DataFrame, target_date: datetime.date) -> Dict[str, Any]:
    """Get daily activity for a specific date"""
    if df.empty:
        return {'arrivals': [], 'departures': [], 'staying': []}
    
    # Filter by date - ensure dates are properly converted
    arrivals = pd.DataFrame()
    departures = pd.DataFrame()
    staying = pd.DataFrame()
    
    if 'Check-in Date' in df.columns:
        df_checkin = pd.to_datetime(df['Check-in Date'])
        arrivals = df[df_checkin.dt.date == target_date]
    
    if 'Check-out Date' in df.columns:
        df_checkout = pd.to_datetime(df['Check-out Date'])
        departures = df[df_checkout.dt.date == target_date]
    
    # Guests staying (checked in BEFORE date, checking out after date)
    # FIXED: Exclude guests checking in on the same day to prevent double counting
    if all(col in df.columns for col in ['Check-in Date', 'Check-out Date', 'Tình trạng']):
        df_checkin = pd.to_datetime(df['Check-in Date'])
        df_checkout = pd.to_datetime(df['Check-out Date'])
        staying = df[
            (df_checkin.dt.date < target_date) &  # CHANGED: < instead of <= to exclude check-in day
            (df_checkout.dt.date > target_date) &
            (df['Tình trạng'] == 'OK')
        ]
    
    return {
        'arrivals': arrivals.to_dict('records') if not arrivals.empty else [],
        'departures': departures.to_dict('records') if not departures.empty else [],
        'staying': staying.to_dict('records') if not staying.empty else []
    }

def get_overall_calendar_day_info(df: pd.DataFrame, target_date: str, total_capacity: int = 4) -> Dict[str, Any]:
    """Get comprehensive calendar day information matching original function"""
    try:
        target_date_obj = pd.to_datetime(target_date).date()
        
        if df is None or df.empty or total_capacity == 0:
            return {
                'occupied_units': 0, 
                'available_units': total_capacity,
                'status_text': "Trống", 
                'status_color': 'empty',
                'arrivals_count': 0,
                'departures_count': 0,
                'staying_count': 0,
                'daily_revenue': 0,
                'commission_total': 0,
                'revenue_minus_commission': 0
            }

        df_local = df.copy()
        
        # Convert datetime columns to date objects for comparison
        if 'Check-in Date' in df_local.columns:
            df_local['Check-in Date'] = pd.to_datetime(df_local['Check-in Date']).dt.date
        if 'Check-out Date' in df_local.columns:
            df_local['Check-out Date'] = pd.to_datetime(df_local['Check-out Date']).dt.date
        
        # Find active bookings on this date
        active_on_date = df_local[
            (df_local['Check-in Date'].notna()) &
            (df_local['Check-out Date'].notna()) &
            (df_local['Check-in Date'] <= target_date_obj) & 
            (df_local['Check-out Date'] > target_date_obj) &
            (df_local['Tình trạng'] != 'Đã hủy')
        ]
        
        occupied_units = len(active_on_date)
        available_units = max(0, total_capacity - occupied_units)
        
        # Calculate activity counts
        activity = get_daily_activity(df_local, target_date_obj)
        arrivals_count = len(activity['arrivals'])
        departures_count = len(activity['departures'])
        staying_count = len(activity['staying'])
        
        # Calculate revenue for the day - OPTIMIZED PER-NIGHT DISTRIBUTION
        daily_revenue = 0
        commission_total = 0
        
        # Get all bookings active on this date (staying guests)
        for _, booking in active_on_date.iterrows():
            try:
                checkin_date = booking['Check-in Date']
                checkout_date = booking['Check-out Date']
                total_amount = float(booking.get('Tổng thanh toán', 0))
                commission_amount = float(booking.get('Hoa hồng', 0))
                
                # Calculate number of nights for this booking
                nights = (checkout_date - checkin_date).days
                if nights <= 0:
                    nights = 1  # Minimum 1 night
                
                # Distribute revenue across all nights of stay
                daily_rate_total = total_amount / nights
                daily_commission = commission_amount / nights
                
                # Add to this day's revenue
                daily_revenue += daily_rate_total
                commission_total += daily_commission
                
            except (ValueError, TypeError) as e:
                # Skip invalid booking data
                continue
        
        # Determine status text and color based on capacity
        if occupied_units == 0:
            status_text = "Trống"
            status_color = "empty"
        elif available_units == 0:
            status_text = "Hết phòng"
            status_color = "full"
        else:
            status_text = f"{available_units}/{total_capacity} trống"
            status_color = "occupied"
        
        return {
            'occupied_units': occupied_units,
            'available_units': available_units,
            'status_text': status_text,
            'status_color': status_color,
            'arrivals_count': arrivals_count,
            'departures_count': departures_count,
            'staying_count': staying_count,
            'daily_revenue': daily_revenue,
            'commission_total': commission_total,
            'revenue_minus_commission': daily_revenue - commission_total,
            'activity': activity
        }
        
    except Exception as e:
        print(f"Error getting calendar day info: {e}")
        return {
            'occupied_units': 0, 
            'available_units': total_capacity,
            'status_text': "Lỗi", 
            'status_color': 'empty',
            'error': str(e)
        }

def prepare_dashboard_data(df: pd.DataFrame, start_date: datetime, end_date: datetime, 
                          sort_by: str, sort_order: str) -> Dict[str, Any]:
    """Prepare dashboard data from PostgreSQL"""
    if df.empty:
        return {
            'total_revenue_selected': 0,
            'total_guests_selected': 0,
            'monthly_revenue_all_time': pd.DataFrame(),
            'collector_revenue_selected': pd.DataFrame(),
            'genius_stats': pd.DataFrame(),
            'monthly_guests_all_time': pd.DataFrame(),
            'weekly_guests_all_time': pd.DataFrame(),
            'monthly_collected_revenue': pd.DataFrame()
        }
    
    # Filter data by date range for metrics but not for ALL-TIME chart
    # ✅ CRITICAL: Use date-only comparison for consistency with details API
    start_date_only = start_date.date()
    end_date_only = end_date.date()
    mask = (df['Check-in Date'].dt.date >= start_date_only) & (df['Check-in Date'].dt.date <= end_date_only)
    filtered_df = df[mask]
    
    print(f"🔍 [CHART_LOGIC] Step 1 - Period filter: {len(df)} → {len(filtered_df)} guests")
    print(f"🔍 [CHART_LOGIC] Date range (date only): {start_date_only} to {end_date_only}")
    
    # Calculate totals for selected period
    total_revenue = filtered_df['Tổng thanh toán'].sum() if 'Tổng thanh toán' in filtered_df.columns else 0
    total_guests = len(filtered_df)
    
    # ✅ Monthly revenue analysis - USE ALL DATA for chart (including May and all months)
    print(f"🔍 [PREPARE_DASHBOARD] Creating monthly revenue chart with ALL {len(df)} bookings")
    if not df.empty and 'Check-in Date' in df.columns:
        # Use full df instead of filtered_df to show ALL months
        monthly_revenue = df.groupby(
            df['Check-in Date'].dt.to_period('M')
        )['Tổng thanh toán'].sum().reset_index()
        monthly_revenue['Tháng'] = monthly_revenue['Check-in Date'].astype(str)
        monthly_revenue = monthly_revenue[['Tháng', 'Tổng thanh toán']]
        print(f"📊 [PREPARE_DASHBOARD] Created monthly revenue chart with {len(monthly_revenue)} months: {monthly_revenue['Tháng'].tolist()}")
    else:
        monthly_revenue = pd.DataFrame(columns=['Tháng', 'Tổng thanh toán'])
    
    # ✅ CRITICAL FIX: Use FILTERED period data to match date filter selection
    if 'Người thu tiền' in filtered_df.columns:
        # Only include valid collectors with actual collected amounts
        valid_collectors = ['LOC LE', 'THAO LE']
        
        print(f"💰 [COLLECTOR_VALIDATION] Using FILTERED period data: {start_date.date()} to {end_date.date()}")
        print(f"🔍 [CHART_LOGIC] Step 1 - Period filter result: {len(filtered_df)} guests")
        
        # ✅ CRITICAL FIX: Apply same checked-in filter as monthly revenue
        from datetime import date
        today = date.today()
        checked_in_mask = filtered_df['Check-in Date'].dt.date <= today
        period_checked_in = filtered_df[checked_in_mask].copy()
        
        print(f"🔍 [CHART_LOGIC] Step 2 - Checked-in filter: {len(filtered_df)} → {len(period_checked_in)} guests")
        print(f"💰 [COLLECTOR_VALIDATION] Period checked-in only: {len(period_checked_in)} (excluded {len(filtered_df) - len(period_checked_in)} future)")
        
        # Now apply collector validation to period checked-in guests only
        valid_collector_df = period_checked_in[
            (period_checked_in['Người thu tiền'].isin(valid_collectors)) & 
            (period_checked_in['Tổng thanh toán'] > 0)
        ].copy()
        
        print(f"💰 [COLLECTOR_VALIDATION] Valid collector records: {len(valid_collector_df)}")
        
        # ✅ ENHANCED DEBUG: Show all collectors in FILTERED PERIOD checked-in data
        if 'Người thu tiền' in period_checked_in.columns:
            debug_collector_counts = period_checked_in['Người thu tiền'].value_counts(dropna=False)
            debug_collector_revenue = period_checked_in.groupby('Người thu tiền', dropna=False)['Tổng thanh toán'].sum()
            
            print(f"🔍 [COLLECTOR_CHART_DEBUG] All collectors in FILTERED PERIOD checked-in data:")
            for collector, count in debug_collector_counts.items():
                revenue = debug_collector_revenue.get(collector, 0)
                is_valid = collector in valid_collectors
                print(f"🔍   '{collector}': {count} guests, {revenue:,.0f}đ {'✅' if is_valid else '❌'}")
                
            # Specific LOC LE tracking
            loc_le_count = debug_collector_counts.get('LOC LE', 0)
            loc_le_revenue = debug_collector_revenue.get('LOC LE', 0)
            print(f"🎯 [CHART_LOC_LE] Final: {loc_le_count} guests, {loc_le_revenue:,.0f}đ")
        
        if not valid_collector_df.empty:
            # Group by collector and calculate detailed stats
            collector_revenue = valid_collector_df.groupby('Người thu tiền').agg({
                'Tổng thanh toán': 'sum',
                'Số đặt phòng': 'count',  # Count bookings
                'Hoa hồng': 'sum'  # Sum commission if available
            }).reset_index()
            
            # Add percentage calculation
            total_collected = collector_revenue['Tổng thanh toán'].sum()
            collector_revenue['Tỷ lệ %'] = (collector_revenue['Tổng thanh toán'] / total_collected * 100).round(1)
            
            # Add validation info
            print(f"💰 [COLLECTOR_CHART_TOTAL] Total collected by valid collectors: {total_collected:,.0f}đ")
            for _, row in collector_revenue.iterrows():
                collector_name = row['Người thu tiền']
                amount = row['Tổng thanh toán']
                count = row['Số đặt phòng']
                percentage = row['Tỷ lệ %']
                print(f"💰 [COLLECTOR_DETAIL] {collector_name}: {amount:,.0f}đ ({count} bookings, {percentage}%)")
        else:
            print(f"💰 [COLLECTOR_WARNING] No valid collections found for period")
            collector_revenue = pd.DataFrame(columns=['Người thu tiền', 'Tổng thanh toán', 'Số đặt phòng', 'Hoa hồng', 'Tỷ lệ %'])
    else:
        collector_revenue = pd.DataFrame(columns=['Người thu tiền', 'Tổng thanh toán', 'Số đặt phòng', 'Hoa hồng', 'Tỷ lệ %'])
    
    return {
        'total_revenue_selected': total_revenue,
        'total_guests_selected': total_guests,
        'monthly_revenue_all_time': monthly_revenue,
        'collector_revenue_selected': collector_revenue,
        'genius_stats': pd.DataFrame(),  # Placeholder
        'monthly_guests_all_time': pd.DataFrame(),  # Placeholder
        'weekly_guests_all_time': pd.DataFrame(),  # Placeholder
        'monthly_collected_revenue': pd.DataFrame()  # Placeholder
    }

# ==============================================================================
# DUPLICATE DETECTION
# ==============================================================================

def check_duplicate_guests(df: pd.DataFrame, guest_name: str, checkin_date: str) -> List[Dict]:
    """Check for duplicate guests in PostgreSQL data"""
    if df.empty:
        return []
    
    try:
        checkin_dt = pd.to_datetime(checkin_date)
        date_range_start = checkin_dt - pd.Timedelta(days=3)
        date_range_end = checkin_dt + pd.Timedelta(days=3)
        
        # Find potential duplicates
        mask = (
            (df['Tên người đặt'].str.lower().str.contains(guest_name.lower(), na=False)) &
            (df['Check-in Date'] >= date_range_start) &
            (df['Check-in Date'] <= date_range_end)
        )
        
        duplicates = df[mask]
        return duplicates.to_dict('records') if not duplicates.empty else []
        
    except Exception as e:
        print(f"Error checking duplicates: {e}")
        return []

def analyze_existing_duplicates(df: pd.DataFrame) -> Dict[str, List]:
    """Analyze existing duplicates in the dataset with performance optimizations"""
    print("🤖 [DUPLICATE_ANALYSIS] Starting analysis...")
    
    if df.empty:
        print("🤖 [DUPLICATE_ANALYSIS] DataFrame is empty")
        return {'duplicate_groups': [], 'total_duplicates': 0, 'total_groups': 0}
    
    try:
        # Check required columns
        required_columns = ['Tên người đặt', 'Check-in Date']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"🤖 [DUPLICATE_ANALYSIS] Missing columns: {missing_columns}")
            print(f"🤖 [DUPLICATE_ANALYSIS] Available columns: {list(df.columns)}")
            return {'duplicate_groups': [], 'total_duplicates': 0, 'total_groups': 0}
        
        # Ensure dates are properly formatted
        df_work = df.copy()
        try:
            df_work['Check-in Date'] = pd.to_datetime(df_work['Check-in Date'])
        except Exception as date_error:
            print(f"🤖 [DUPLICATE_ANALYSIS] Date conversion error: {date_error}")
            return {'duplicate_groups': [], 'total_duplicates': 0, 'total_groups': 0}
        
        # Filter out null values
        df_clean = df_work.dropna(subset=['Tên người đặt', 'Check-in Date'])
        
        unique_guests = df_clean['Tên người đặt'].unique()
        print(f"🤖 [DUPLICATE_ANALYSIS] Processing {len(unique_guests)} unique guests from {len(df_clean)} bookings")
        
        # DEBUG: Show first few guest names and their booking counts
        guest_counts = df_clean['Tên người đặt'].value_counts()
        multi_booking_guests = guest_counts[guest_counts > 1]
        print(f"🤖 [DUPLICATE_ANALYSIS] Guests with multiple bookings: {len(multi_booking_guests)}")
        if len(multi_booking_guests) > 0:
            print(f"🤖 [DUPLICATE_ANALYSIS] Top guests with multiple bookings:")
            for name, count in multi_booking_guests.head(5).items():
                print(f"   - {name}: {count} bookings")
        
        duplicate_groups = []
        processed_count = 0
        
        # Performance optimization: limit processing time
        import time
        start_time = time.time()
        max_processing_time = 30  # 30 seconds timeout
        
        for name in unique_guests:
            # Check timeout
            if time.time() - start_time > max_processing_time:
                print(f"🤖 [DUPLICATE_ANALYSIS] Timeout reached after {max_processing_time}s, stopping analysis")
                break
            
            processed_count += 1
            if processed_count % 50 == 0:  # Progress every 50 guests
                print(f"🤖 [DUPLICATE_ANALYSIS] Progress: {processed_count}/{len(unique_guests)} guests")
            
            guest_bookings = df_clean[df_clean['Tên người đặt'] == name].sort_values('Check-in Date')
            
            if len(guest_bookings) > 1:
                # Optimization: limit to reasonable number of bookings per guest
                if len(guest_bookings) > 20:
                    print(f"🤖 [DUPLICATE_ANALYSIS] Guest '{name}' has {len(guest_bookings)} bookings, limiting to most recent 20")
                    guest_bookings = guest_bookings.tail(20)
                
                # Check if any bookings are within 3 days of each other
                for i in range(len(guest_bookings) - 1):
                    try:
                        current = guest_bookings.iloc[i]
                        next_booking = guest_bookings.iloc[i + 1]
                        
                        # Safe date difference calculation
                        current_date = current['Check-in Date']
                        next_date = next_booking['Check-in Date']
                        
                        if pd.isna(current_date) or pd.isna(next_date):
                            continue
                        
                        date_diff = (next_date - current_date).days
                        
                        if abs(date_diff) <= 3:
                            # DEBUG: Log found duplicate
                            print(f"🤖 [DUPLICATE_FOUND] Guest: {name}, Date diff: {date_diff} days")
                            print(f"   Booking 1: {current.get('Số đặt phòng', 'N/A')} on {current_date.date()}")
                            print(f"   Booking 2: {next_booking.get('Số đặt phòng', 'N/A')} on {next_date.date()}")
                            
                            # Limit dictionary conversion to avoid memory issues
                            current_dict = {
                                'Số đặt phòng': current.get('Số đặt phòng', 'N/A'),
                                'guest_name': current.get('Tên người đặt', 'N/A'),
                                'check_in': str(current_date.date()) if not pd.isna(current_date) else 'N/A',
                                'amount': current.get('Tổng thanh toán', 0)
                            }
                            next_dict = {
                                'Số đặt phòng': next_booking.get('Số đặt phòng', 'N/A'),
                                'guest_name': next_booking.get('Tên người đặt', 'N/A'),
                                'check_in': str(next_date.date()) if not pd.isna(next_date) else 'N/A',
                                'amount': next_booking.get('Tổng thanh toán', 0)
                            }
                            
                            duplicate_groups.append({
                                'guest_name': name,
                                'bookings': [current_dict, next_dict],
                                'date_difference_days': date_diff
                            })
                            
                    except Exception as booking_error:
                        print(f"🤖 [DUPLICATE_ANALYSIS] Error processing booking for {name}: {booking_error}")
                        continue
        
        total_time = time.time() - start_time
        print(f"🤖 [DUPLICATE_ANALYSIS] Analysis completed in {total_time:.2f}s")
        print(f"🤖 [DUPLICATE_ANALYSIS] Found {len(duplicate_groups)} duplicate groups")
        
        return {
            'duplicate_groups': duplicate_groups,
            'total_duplicates': len(duplicate_groups),
            'total_groups': len(duplicate_groups),  # Add this for template compatibility
            'processing_time': total_time,
            'processed_guests': processed_count,
            'total_guests': len(unique_guests)
        }
        
    except Exception as e:
        print(f"🤖 [DUPLICATE_ANALYSIS] Error analyzing duplicates: {e}")
        import traceback
        traceback.print_exc()
        return {'duplicate_groups': [], 'total_duplicates': 0, 'total_groups': 0, 'error': str(e)}

# ==============================================================================
# EXPENSE MANAGEMENT
# ==============================================================================

def add_expense_to_database(expense_data: Dict) -> int:
    """Add expense to PostgreSQL and return expense_id"""
    from .models import db, Expense
    
    try:
        expense = Expense(
            expense_date=expense_data.get('date'),
            amount=expense_data.get('amount', 0),
            description=expense_data.get('description', ''),
            category=expense_data.get('category', 'general'),
            collector=expense_data.get('collector', '')
        )
        
        db.session.add(expense)
        db.session.commit()
        
        expense_id = expense.expense_id
        print(f"✅ Added expense ID {expense_id}: {expense_data.get('description')}")
        return expense_id  # Return the expense_id instead of True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error adding expense: {e}")
        return None  # Return None instead of False

def get_expenses_from_database() -> pd.DataFrame:
    """Get all expenses from PostgreSQL with English field names for API compatibility"""
    query = """
    SELECT 
        expense_id,
        expense_date as "date",
        amount as "amount",
        description as "description", 
        category as "category",
        collector as "collector",
        created_at
    FROM expenses
    ORDER BY expense_date DESC
    """
    
    result = execute_query(query)
    print(f"💰 EXPENSES QUERY: Found {len(result)} expenses in database")
    return result

# ==============================================================================
# PLACEHOLDER FUNCTIONS (for compatibility)
# ==============================================================================

# These functions are kept for compatibility but will return empty results
def import_from_gsheet(*args, **kwargs) -> pd.DataFrame:
    """Placeholder - Google Sheets removed"""
    print("⚠️ Google Sheets functionality removed - using PostgreSQL only")
    return load_booking_data()

def append_multiple_bookings_to_sheet(*args, **kwargs) -> bool:
    """Placeholder - Google Sheets removed"""
    print("⚠️ Google Sheets functionality removed - use PostgreSQL functions")
    return False

def update_row_in_gsheet(*args, **kwargs) -> bool:
    """Placeholder - Google Sheets removed"""
    print("⚠️ Google Sheets functionality removed - use PostgreSQL functions")
    return False

def delete_row_in_gsheet(*args, **kwargs) -> bool:
    """Placeholder - Google Sheets removed"""
    print("⚠️ Google Sheets functionality removed - use PostgreSQL functions")
    return False

def delete_multiple_rows_in_gsheet(*args, **kwargs) -> bool:
    """Placeholder - Google Sheets removed"""
    print("⚠️ Google Sheets functionality removed - use PostgreSQL functions")
    return False

def export_data_to_new_sheet(*args, **kwargs) -> bool:
    """Placeholder - Google Sheets removed"""
    print("⚠️ Google Sheets functionality removed")
    return False

def import_message_templates_from_gsheet(*args, **kwargs) -> List:
    """Placeholder - Google Sheets removed"""
    print("⚠️ Google Sheets functionality removed")
    return []

def export_message_templates_to_gsheet(*args, **kwargs) -> bool:
    """Placeholder - Google Sheets removed"""
    print("⚠️ Google Sheets functionality removed")
    return False

# Aliases for compatibility
add_expense_to_sheet = add_expense_to_database
get_expenses_from_sheet = get_expenses_from_database

# ==============================================================================
# IMAGE PROCESSING (Gemini AI)
# ==============================================================================

def extract_booking_info_from_image_content(image_data: bytes, google_api_key: str) -> Dict:
    """Extract booking information from image using Gemini AI"""
    if not genai or not google_api_key:
        return {'error': 'Gemini AI not available'}
    
    try:
        genai.configure(api_key=google_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-05-20')
        
        # Convert image for Gemini
        image = Image.open(BytesIO(image_data)) if Image else None
        if not image:
            return {'error': 'PIL not available for image processing'}
        
        prompt = """
        Extract ALL booking information from this image. If there are multiple bookings/guests, extract all of them.
        Return as JSON in this exact format:
        
        For SINGLE booking:
        {
            "type": "single",
            "booking": {
                "guest_name": "full name",
                "booking_id": "booking ID", 
                "checkin_date": "YYYY-MM-DD",
                "checkout_date": "YYYY-MM-DD",
                "room_amount": number,
                "commission": number,
                "email": "email if available",
                "phone": "phone if available"
            }
        }
        
        For MULTIPLE bookings:
        {
            "type": "multiple",
            "count": number_of_bookings,
            "bookings": [
                {
                    "guest_name": "full name 1",
                    "booking_id": "booking ID 1", 
                    "checkin_date": "YYYY-MM-DD",
                    "checkout_date": "YYYY-MM-DD",
                    "room_amount": number,
                    "commission": number,
                    "email": "email if available",
                    "phone": "phone if available"
                },
                {
                    "guest_name": "full name 2",
                    "booking_id": "booking ID 2",
                    "checkin_date": "YYYY-MM-DD", 
                    "checkout_date": "YYYY-MM-DD",
                    "room_amount": number,
                    "commission": number,
                    "email": "email if available",
                    "phone": "phone if available"
                }
            ]
        }
        
        Important: Look carefully for multiple guest names, booking IDs, or booking entries in the image. 
        If you see multiple bookings, return type "multiple" with all bookings in the array.
        If you see only one booking, return type "single" with the booking object.
        """
        
        response = model.generate_content([prompt, image])
        
        # Parse JSON from response with better error handling
        import json
        try:
            # Clean the response text - sometimes Gemini adds extra text
            response_text = response.text.strip()
            print(f"🤖 Gemini response text: {response_text[:200]}...")
            
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                print(f"📝 Extracted JSON: {json_text}")
                result = json.loads(json_text)
                return result
            else:
                print(f"❌ No valid JSON found in response")
                return {'error': 'No valid JSON found in AI response', 'raw_response': response_text}
                
        except json.JSONDecodeError as json_error:
            print(f"❌ JSON decode error: {json_error}")
            return {
                'error': f'Invalid JSON from AI: {str(json_error)}',
                'raw_response': response.text[:500]  # First 500 chars for debugging
            }
        
    except Exception as e:
        print(f"Error extracting booking info: {e}")
        return {'error': str(e)}

# ==============================================================================
# MARKET INTELLIGENCE PLACEHOLDER
# ==============================================================================

def scrape_booking_apartments(*args, **kwargs) -> List:
    """Placeholder for market intelligence"""
    print("⚠️ Market intelligence functionality requires separate implementation")
    return []

def format_apartments_display(*args, **kwargs) -> str:
    """Placeholder for market intelligence"""
    return "Market intelligence data not available"

print("PostgreSQL-only logic module loaded successfully")