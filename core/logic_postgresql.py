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
import time
from typing import Dict, List, Optional, Tuple, Any
import json
import calendar
from io import BytesIO
from sqlalchemy import text
from flask import current_app

# ⚡ ULTRA PERFORMANCE: Global cache for booking data
_booking_data_cache = None
_cache_timestamp = 0

def clear_booking_cache():
    """Clear the global booking data cache - call after any data modification"""
    global _booking_data_cache, _cache_timestamp
    _booking_data_cache = None
    _cache_timestamp = 0
    print("🔄 Cache cleared - next request will reload fresh data")

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

def execute_query(query: str, params: dict = None, force_fresh: bool = False, allow_fallback: bool = False) -> pd.DataFrame:
    """Execute SQL query and return DataFrame - SQLAlchemy 2.0 compatible"""
    try:
        if force_fresh:
            print("🔄 EXECUTE_QUERY: Using fresh database connection")
            # Force a new connection by disposing the pool
            from .models import db
            db.engine.dispose()

        from .models import db
        # SQLAlchemy 2.0 style: use connection.execute() then convert to DataFrame
        with db.engine.connect() as conn:
            if params:
                query_result = conn.execute(text(query), params)
            else:
                query_result = conn.execute(text(query))

            # Fetch all rows and column names
            rows = query_result.fetchall()
            if query_result.returns_rows and rows:
                # Get column names from the result
                columns = list(query_result.keys())
                # Convert to DataFrame
                result = pd.DataFrame(rows, columns=columns)
            else:
                result = pd.DataFrame()

            if force_fresh:
                print(f"🔄 EXECUTE_QUERY: Fresh query returned {len(result)} rows")
            return result
    except Exception as e:
        print(f"Database query error: {e}")
        import traceback
        traceback.print_exc()
        # If allow_fallback is True, re-raise the error so calling code can handle it
        if allow_fallback:
            raise e
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

def load_booking_data_for_calculations(force_fresh: bool = False) -> pd.DataFrame:
    """Load booking data EXCLUDING cancelled bookings - for calculations and analytics"""
    df = load_booking_data(force_fresh=force_fresh)
    if df.empty:
        return df
    
    # Filter out cancelled bookings for all calculations and features
    if 'Tình trạng' in df.columns:
        initial_count = len(df)
        df = df[df['Tình trạng'] != 'Đã hủy']
        filtered_count = initial_count - len(df)
        if filtered_count > 0:
            print(f"🔍 [CALCULATIONS] Excluded {filtered_count} cancelled bookings from calculations")
    
    return df

def load_booking_data(force_fresh: bool = False) -> pd.DataFrame:
    """Load all booking data from PostgreSQL with caching"""
    # ⚡ ULTRA PERFORMANCE: Use global cache if not force_fresh
    global _booking_data_cache, _cache_timestamp
    cache_ttl = 30  # 30 seconds

    if not force_fresh and _booking_data_cache is not None:
        if time.time() - _cache_timestamp < cache_ttl:
            return _booking_data_cache.copy()

    if force_fresh:
        print("🔄 FORCE FRESH: Loading data with fresh database connection")
    
    # Smart query that works with or without guests table
    query = """
    SELECT
        b.booking_id as "Số đặt phòng",
        COALESCE(g.full_name, b.guest_name) as "Tên người đặt",
        COALESCE(b.accommodation_name, '118 Hang Bac Hostel') as "Tên chỗ nghỉ",
        b.checkin_date as "Check-in Date",
        b.checkout_date as "Check-out Date",
        b.room_amount as "Tổng thanh toán",
        COALESCE(b.collected_amount, 0) as "Số tiền đã thu",
        b.commission as "Hoa hồng",
        b.taxi_amount as "Taxi",
        b.collector as "Người thu tiền",
        COALESCE(b.commission_status, 'pending') as "Trạng thái hoa hồng",
        CASE
            WHEN b.booking_status IN ('cancelled', 'đã hủy', 'deleted') THEN 'Đã hủy'
            WHEN b.booking_status = 'pending' THEN 'Chờ xử lý'
            ELSE 'OK'
        END as "Tình trạng",
        b.booking_notes as "Ghi chú thanh toán",
        'VND' as "Tiền tệ",
        'Hà Nội' as "Vị trí",
        'Không' as "Thành viên Genius",
        CASE WHEN b.taxi_amount > 0 THEN true ELSE false END as "Có taxi",
        CASE WHEN b.taxi_amount > 0 THEN false ELSE true END as "Không có taxi",
        b.apartment_id,
        b.room_id,
        b.created_at,
        b.updated_at
    FROM bookings b
    LEFT JOIN guests g ON b.guest_id = g.guest_id
    -- Exclude deleted bookings from all queries
    WHERE (b.booking_status != 'deleted' OR b.booking_status IS NULL)
    ORDER BY b.checkin_date DESC NULLS LAST
    """
    
    # Try the full query first (works for local with guests table)
    try:
        df = execute_query(query, force_fresh=force_fresh, allow_fallback=True)
        if not df.empty:
            result = process_booking_dataframe(df)
            # ⚡ ULTRA PERFORMANCE: Store in cache (global already declared at function start)
            _booking_data_cache = result.copy()
            _cache_timestamp = time.time()
            return result
        else:
            print("⚠️ Full query returned empty result, trying fallback...")
    except Exception as e:
        print(f"⚠️ Full query failed (likely missing guests table): {e}")
        print("🔄 Switching to Railway-compatible fallback query...")
    
    # Fallback query without guests table (works for Railway)
    fallback_query = """
    SELECT 
        b.booking_id as "Số đặt phòng",
        b.guest_name as "Tên người đặt", 
        COALESCE(b.accommodation_name, '118 Hang Bac Hostel') as "Tên chỗ nghỉ",
        b.checkin_date as "Check-in Date",
        b.checkout_date as "Check-out Date",
        b.room_amount as "Tổng thanh toán",
        COALESCE(b.collected_amount, 0) as "Số tiền đã thu",
        b.commission as "Hoa hồng",
        b.taxi_amount as "Taxi",
        b.collector as "Người thu tiền",
        COALESCE(b.commission_status, 'pending') as "Trạng thái hoa hồng",
        CASE
            WHEN b.booking_status IN ('cancelled', 'đã hủy', 'deleted') THEN 'Đã hủy'
            WHEN b.booking_status = 'pending' THEN 'Chờ xử lý'
            ELSE 'OK'
        END as "Tình trạng",
        b.booking_notes as "Ghi chú thanh toán",
        'VND' as "Tiền tệ",
        'Hà Nội' as "Vị trí",
        'Không' as "Thành viên Genius",
        CASE WHEN b.taxi_amount > 0 THEN true ELSE false END as "Có taxi",
        CASE WHEN b.taxi_amount > 0 THEN false ELSE true END as "Không có taxi",
        b.apartment_id,
        b.created_at,
        b.updated_at
    FROM bookings b
    -- Exclude deleted bookings from all queries
    WHERE (b.booking_status != 'deleted' OR b.booking_status IS NULL)
    ORDER BY b.checkin_date DESC NULLS LAST
    """
    
    print("🔄 Using fallback query without guests table...")
    df = execute_query(fallback_query, force_fresh=force_fresh)

    if df.empty:
        return pd.DataFrame()

    result = process_booking_dataframe(df)

    # ⚡ ULTRA PERFORMANCE: Store in cache (global already declared at function start)
    _booking_data_cache = result.copy()
    _cache_timestamp = time.time()

    return result

def process_booking_dataframe(df):
    """Process the booking dataframe with proper data types"""
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
    
    # Ensure required text fields are not null to prevent frontend errors
    text_columns = ['Tên người đặt', 'Số đặt phòng', 'Tình trạng', 'Người thu tiền']
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].fillna('N/A').astype(str)
    
    # Ensure Tình trạng has valid values only
    if 'Tình trạng' in df.columns:
        df['Tình trạng'] = df['Tình trạng'].apply(lambda x: x if x in ['OK', 'Đã hủy', 'Chờ xử lý'] else 'OK')
    
    print(f"✅ Loaded {len(df)} bookings from PostgreSQL")
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
        
        # Commit to get auto-assigned guest_ids (let PostgreSQL handle ID assignment)
        db.session.commit()
        
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

def _fix_guest_sequence() -> bool:
    """Fix PostgreSQL guest_id sequence to prevent duplicate key violations"""
    try:
        print("🔧 [FIX_SEQUENCE] Fixing PostgreSQL guest_id sequence...")
        
        from .models import db, Guest
        from sqlalchemy import text
        
        with db.engine.connect() as conn:
            # Get the maximum guest_id currently in the table
            result = conn.execute(text("SELECT COALESCE(MAX(guest_id), 0) FROM guests"))
            max_guest_id = result.scalar()
            
            # Set the sequence to the next available value
            next_value = max_guest_id + 1
            conn.execute(text(f"SELECT setval('guests_guest_id_seq', {next_value})"))
            conn.commit()
            
            print(f"✅ [FIX_SEQUENCE] Guest sequence fixed! Next guest_id will be: {next_value}")
            return True
            
    except Exception as e:
        print(f"❌ [FIX_SEQUENCE] Failed to fix guest sequence: {e}")
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
        
        # Check for email conflicts with different guests
        if email:
            existing_email_guest = db.session.query(Guest).filter_by(email=email).first()
            if existing_email_guest and existing_email_guest.full_name != booking_data.get('guest_name', ''):
                # Email exists for different guest - set email to None to avoid conflict
                print(f"⚠️ [ADD_NEW_BOOKING] Email conflict detected for {booking_data.get('guest_name', '')}, setting to None")
                email = None
        
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
            # Commit to get auto-assigned guest_id (let PostgreSQL handle ID assignment)
            db.session.commit()
            print(f"✅ [ADD_NEW_BOOKING] New guest created: ID {guest.guest_id}")
        else:
            print(f"✅ [ADD_NEW_BOOKING] Existing guest found: ID {guest.guest_id}")
        
        # Generate unique booking ID if not provided
        booking_id = booking_data.get('booking_id', '').strip()
        if not booking_id:
            booking_id = f"PHOTO_{uuid.uuid4().hex[:8].upper()}"
            print(f"🔍 [ADD_NEW_BOOKING] Generated booking ID: {booking_id}")
        
        # Check for booking ID conflicts
        existing_booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        if existing_booking:
            # Generate new unique booking_id
            original_id = booking_id
            booking_id = f"PHOTO_{uuid.uuid4().hex[:8].upper()}"
            print(f"⚠️ [ADD_NEW_BOOKING] Booking ID conflict ({original_id}), generated new: {booking_id}")
        
        # 🔧 MAP ROOM NAME TO ROOM_ID for apartment filtering
        accommodation_name = booking_data.get('accommodation_name', '118 Hang Bac Hostel')
        room_id = None

        from .models import Room
        room_name_lower = accommodation_name.lower().strip()
        print(f"[ADD_NEW_BOOKING] 🏠 Mapping room name to room_id: {room_name_lower}")

        # Try exact match first
        room = db.session.query(Room).filter(
            db.func.lower(Room.room_name) == room_name_lower,
            Room.is_active == True
        ).first()

        # If no exact match, try partial match
        if not room:
            room = db.session.query(Room).filter(
                db.func.lower(Room.room_name).contains(room_name_lower) |
                db.func.lower(db.text(f"'{room_name_lower}'")).contains(db.func.lower(Room.room_name)),
                Room.is_active == True
            ).first()

        if room:
            room_id = room.room_id
            print(f"[ADD_NEW_BOOKING] ✅ Mapped to room_id: {room.room_id} ({room.room_name}, apartment_id: {room.apartment_id})")
        else:
            print(f"[ADD_NEW_BOOKING] ⚠️ WARNING: Could not find room_id for '{accommodation_name}', defaulting to room 1")
            room_id = 1  # Default to first room (118 hang bac)

        # Create new booking
        booking = Booking(
            booking_id=booking_id,
            guest_id=guest.guest_id,
            guest_name=booking_data.get('guest_name', ''),  # Denormalized for quick access
            accommodation_name=accommodation_name,  # Room type/property
            room_id=room_id,  # 🔧 SET ROOM_ID for apartment filtering
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
        error_str = str(e)
        
        # Enhanced error handling with specific constraint identification
        if "duplicate key value violates unique constraint" in error_str:
            if "guests_pkey" in error_str:
                print(f"🔧 [ADD_NEW_BOOKING] Guest ID sequence issue detected, attempting fix...")
                if _fix_guest_sequence():
                    print(f"✅ [ADD_NEW_BOOKING] Sequence fixed, retrying booking creation...")
                    return add_new_booking(booking_data)  # Retry once
            elif "guests_email_key" in error_str:
                print(f"❌ [ADD_NEW_BOOKING] Email unique constraint violation for: {booking_data.get('guest_name', 'Unknown')}")
                print(f"   Email causing conflict: {booking_data.get('email', 'No email')}")
            elif "bookings_pkey" in error_str:
                print(f"❌ [ADD_NEW_BOOKING] Booking ID conflict for: {booking_data.get('booking_id', 'No ID')}")
            else:
                print(f"❌ [ADD_NEW_BOOKING] Unknown unique constraint violation: {error_str}")
        
        print(f"❌ [ADD_NEW_BOOKING] Error adding booking for {booking_data.get('guest_name', 'Unknown')}: {e}")
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
        if 'commission_status' in update_data:
            old_status = booking.commission_status or 'pending'
            new_status = update_data['commission_status']
            booking.commission_status = new_status
            print(f"[UPDATE_BOOKING] 📊 COMMISSION STATUS UPDATE:")
            print(f"[UPDATE_BOOKING]   - OLD status: {old_status}")
            print(f"[UPDATE_BOOKING]   - NEW status: {new_status}")
            print(f"[UPDATE_BOOKING]   - After assignment: {booking.commission_status}")
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
        if 'checkin_status' in update_data:
            booking.checkin_status = update_data['checkin_status'] or None  # '' → NULL
        if 'accommodation_name' in update_data:
            booking.accommodation_name = update_data['accommodation_name']

            # 🔧 MAP ROOM NAME TO ROOM_ID for apartment filtering
            room_name_lower = update_data['accommodation_name'].lower().strip()
            print(f"[UPDATE_BOOKING] 🏠 Mapping room name to room_id: {room_name_lower}")

            from .models import Room
            # Try exact match first
            room = db.session.query(Room).filter(
                db.func.lower(Room.room_name) == room_name_lower,
                Room.is_active == True
            ).first()

            # If no exact match, try partial match
            if not room:
                room = db.session.query(Room).filter(
                    db.func.lower(Room.room_name).contains(room_name_lower) |
                    db.func.lower(db.text(f"'{room_name_lower}'")).contains(db.func.lower(Room.room_name)),
                    Room.is_active == True
                ).first()

            if room:
                booking.room_id = room.room_id
                print(f"[UPDATE_BOOKING] ✅ Mapped to room_id: {room.room_id} ({room.room_name}, apartment_id: {room.apartment_id})")
            else:
                print(f"[UPDATE_BOOKING] ⚠️ WARNING: Could not find room_id for '{update_data['accommodation_name']}'")

        # Commit changes - simple and fast
        db.session.commit()

        print(f"[UPDATE_BOOKING] ✅ Successfully updated booking: {booking_id}")
        print(f"[UPDATE_BOOKING]   - commission: {booking.commission}")
        print(f"[UPDATE_BOOKING]   - commission_status: {booking.commission_status}")
        print(f"[UPDATE_BOOKING]   - taxi_amount: {booking.taxi_amount}")
        print(f"[UPDATE_BOOKING]   - collected_amount: {booking.collected_amount}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error updating booking: {e}")
        return False

def cancel_booking_by_id(booking_id: str) -> bool:
    """Cancel booking in PostgreSQL (soft cancel - preserves data)"""
    from .models import db, Booking
    
    try:
        booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        if not booking:
            print(f"Booking {booking_id} not found")
            return False
        
        # Soft cancel - mark as cancelled (preserves all data)
        booking.booking_status = 'cancelled'
        db.session.commit()
        print(f"Cancelled booking: {booking_id}")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"Error cancelling booking: {e}")
        return False

def soft_delete_booking_by_id(booking_id: str) -> bool:
    """Soft delete - mark as cancelled but preserve all data"""
    print(f"🔄 [SOFT_DELETE] Marking booking as cancelled (preserving data): {booking_id}")
    return cancel_booking_by_id(booking_id)

def delete_booking_by_id(booking_id: str) -> bool:
    """Permanently delete booking and all associated data from PostgreSQL"""
    from .models import db, Booking, Guest
    
    try:
        print(f"🗑️ [DELETE] Permanently deleting booking: {booking_id}")
        
        # Find the booking
        booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        if not booking:
            print(f"❌ [DELETE] Booking {booking_id} not found")
            return False
        
        guest_id = booking.guest_id
        guest_name = booking.guest_name
        
        # Delete the booking record permanently
        db.session.delete(booking)
        print(f"🗑️ [DELETE] Removed booking record: {booking_id}")
        
        # Check if the guest has any other bookings
        other_bookings = db.session.query(Booking).filter_by(guest_id=guest_id).count()
        
        if other_bookings == 0:
            # Delete the guest record if no other bookings exist
            guest = db.session.query(Guest).filter_by(guest_id=guest_id).first()
            if guest:
                db.session.delete(guest)
                print(f"🗑️ [DELETE] Removed guest record: {guest_name} (ID: {guest_id})")
        else:
            print(f"ℹ️ [DELETE] Guest {guest_name} has {other_bookings} other bookings, keeping guest record")
        
        # Commit all changes
        db.session.commit()
        print(f"✅ [DELETE] Successfully deleted booking {booking_id} and associated data")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ [DELETE] Error deleting booking {booking_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

# ==============================================================================
# DATA ANALYSIS FUNCTIONS
# ==============================================================================

def get_room_symbol_by_name(room_name: str) -> str:
    """Get room symbol based on room name (calendar view helper) - SIMPLIFIED 3-SYMBOL SYSTEM"""
    if not room_name:
        return '●'

    room_lower = room_name.lower()

    # 18 Hang Be (Green apartment) - Individual room numbers
    if 'hang be' in room_lower or 'hàng bè' in room_lower:
        if '101' in room_lower:
            return '①'  # Circled 1 for Room 101
        elif '102' in room_lower:
            return '②'  # Circled 2 for Room 102
        return '①'  # Default to Room 101 if unclear

    # 118 Hang Bac (Blue apartment) - ALL rooms use ONE symbol
    if 'hang bac' in room_lower or 'hàng bạc' in room_lower or 'hang bạc' in room_lower:
        return '●'  # Circle for ALL Hang Bac rooms (Standard, Kitchen, Night Market)

    return '●'  # Default circle

def _make_apt_abbr(name: str) -> str:
    """Short abbreviation: skip numbers, use only first 2 significant words.
    e.g. '118 Hang Bac Hostel' → 'HBac', '18 Hang Be' → 'HBe', '25 Hoi Vu' → 'HVu'"""
    words = [w for w in name.split() if not w.isdigit()][:2]
    if not words:
        return name[:5]
    if len(words) == 1:
        return words[0][:4].capitalize()
    return words[0][0].upper() + words[1][:3].capitalize()


def _booking_matches_apartment(acc_name, apt_name_lower, room_names_lower):
    """Return True if accommodation name matches this apartment or any of its rooms."""
    acc_l = str(acc_name or '').lower().strip()
    if not acc_l:
        return False
    if apt_name_lower in acc_l or acc_l in apt_name_lower:
        return True
    # Only use room-name substring match when the room name is long enough to be unambiguous
    return any((len(rn) >= 4 and rn in acc_l) or (len(acc_l) >= 4 and acc_l in rn)
               for rn in room_names_lower)


def _assign_booking_to_apt(acc_name: str, apt_id_col, apartments_list: list):
    """Assign a booking to exactly ONE apartment.

    Priority:
      1. First apartment whose name/rooms match the accommodation name (Tên chỗ nghỉ)
      2. apartment_id column value as fallback when name gives no match
    Returns the matched apartment id (int) or None.
    """
    acc_l = str(acc_name or '').lower().strip()
    if acc_l:
        for apt in apartments_list:
            room_names_lower = [r['name_lower'] for r in apt.get('rooms', [])]
            if _booking_matches_apartment(acc_l, apt['name_lower'], room_names_lower):
                return apt['id']
    # Fallback: trust the stored apartment_id column
    try:
        if apt_id_col is not None and not (isinstance(apt_id_col, float) and apt_id_col != apt_id_col):
            return int(apt_id_col)
    except (TypeError, ValueError):
        pass
    return None


def get_daily_activity(df: pd.DataFrame, target_date: datetime.date, apartments_list=None) -> Dict[str, Any]:
    """Get daily activity — fully dynamic apartment support.

    apartments_list: pre-loaded list of dicts with keys:
        id, name, name_lower, capacity, rooms=[{name, name_lower}]
    When provided, arrivals_by_apt / departures_by_apt are populated per apartment ID.
    """
    _empty = {
        'arrivals': [], 'departures': [], 'staying': [],
        'arrivals_by_apt': {}, 'departures_by_apt': {},
        'arrivals_symbols': {}, 'departures_symbols': {},
        'one_night_count': 0,
    }
    if df.empty:
        return _empty

    # ── Date filters ────────────────────────────────────────────────────────────
    arrivals = pd.DataFrame()
    departures = pd.DataFrame()
    staying = pd.DataFrame()

    if 'Check-in Date' in df.columns:
        df_checkin = pd.to_datetime(df['Check-in Date'])
        arrivals = df[(df_checkin.dt.date == target_date) & (df['Tình trạng'] != 'Đã hủy')]

    if 'Check-out Date' in df.columns:
        df_checkout = pd.to_datetime(df['Check-out Date'])
        departures = df[(df_checkout.dt.date == target_date) & (df['Tình trạng'] != 'Đã hủy')]

    if all(col in df.columns for col in ['Check-in Date', 'Check-out Date', 'Tình trạng']):
        df_checkin = pd.to_datetime(df['Check-in Date'])
        df_checkout = pd.to_datetime(df['Check-out Date'])
        staying = df[
            (df_checkin.dt.date < target_date) &
            (df_checkout.dt.date > target_date) &
            (df['Tình trạng'] != 'Đã hủy')
        ]

    # ── Per-apartment counts — exclusive assignment (each booking → ONE apt) ────
    arrivals_by_apt   = {apt['id']: 0 for apt in (apartments_list or [])}
    departures_by_apt = {apt['id']: 0 for apt in (apartments_list or [])}

    if apartments_list:
        def _apt_id_col_val(df_slice, idx):
            if 'apartment_id' in df_slice.columns:
                v = df_slice.at[idx, 'apartment_id']
                return None if pd.isna(v) else v
            return None

        # arrivals: assign each booking to exactly one apartment
        if not arrivals.empty:
            acc_col = arrivals['Tên chỗ nghỉ'] if 'Tên chỗ nghỉ' in arrivals.columns \
                      else pd.Series('', index=arrivals.index)
            apt_id_col = arrivals['apartment_id'] if 'apartment_id' in arrivals.columns \
                         else pd.Series(None, index=arrivals.index)
            for acc, aid in zip(acc_col, apt_id_col):
                assigned = _assign_booking_to_apt(acc, aid, apartments_list)
                if assigned is not None and assigned in arrivals_by_apt:
                    arrivals_by_apt[assigned] += 1

        # departures: same exclusive logic
        if not departures.empty:
            acc_col = departures['Tên chỗ nghỉ'] if 'Tên chỗ nghỉ' in departures.columns \
                      else pd.Series('', index=departures.index)
            apt_id_col = departures['apartment_id'] if 'apartment_id' in departures.columns \
                         else pd.Series(None, index=departures.index)
            for acc, aid in zip(acc_col, apt_id_col):
                assigned = _assign_booking_to_apt(acc, aid, apartments_list)
                if assigned is not None and assigned in departures_by_apt:
                    departures_by_apt[assigned] += 1

    # ── One-night stays ─────────────────────────────────────────────────────────
    one_night_count = 0
    for _, booking in arrivals.iterrows():
        checkin = pd.to_datetime(booking.get('Check-in Date'))
        checkout = pd.to_datetime(booking.get('Check-out Date'))
        if checkin and checkout and (checkout - checkin).days == 1:
            one_night_count += 1

    return {
        'arrivals': arrivals.to_dict('records') if not arrivals.empty else [],
        'departures': departures.to_dict('records') if not departures.empty else [],
        'staying': staying.to_dict('records') if not staying.empty else [],
        'arrivals_by_apt': arrivals_by_apt,
        'departures_by_apt': departures_by_apt,
        # Legacy keys kept for any existing callers
        'arrivals_symbols': {},
        'departures_symbols': {},
        'one_night_count': one_night_count,
    }

def get_overall_calendar_day_info(df: pd.DataFrame, target_date: str,
                                   total_capacity: int = 6,
                                   apartments_list=None) -> Dict[str, Any]:
    """Get comprehensive calendar day info — fully dynamic apartment support.

    apartments_list: pre-loaded list of dicts with keys:
        id, name, name_lower, capacity, rooms=[{name, name_lower}]
    When provided, avoids all per-call DB queries (big performance win).
    Returns apartments_status list for dynamic template rendering.
    """
    _empty_activity = {
        'arrivals': [], 'departures': [], 'staying': [],
        'arrivals_by_apt': {}, 'departures_by_apt': {},
        'arrivals_symbols': {}, 'departures_symbols': {},
        'one_night_count': 0,
    }

    def _empty_result(cap=total_capacity):
        return {
            'occupied_units': 0, 'available_units': cap,
            'status_text': "Trồng", 'status_color': 'empty',
            'arrivals_count': 0, 'departures_count': 0, 'staying_count': 0,
            'daily_revenue': 0, 'commission_total': 0, 'revenue_minus_commission': 0,
            'activity': _empty_activity,
            'apartments_status': [],
            'apt1_occupied': 0, 'apt1_available': 4,
            'apt2_occupied': 0, 'apt2_available': 2,
        }

    try:
        target_date_obj = pd.to_datetime(target_date).date()

        if df is None or df.empty or total_capacity == 0:
            return _empty_result()

        df_local = df.copy()
        if 'Check-in Date' in df_local.columns:
            df_local['Check-in Date'] = pd.to_datetime(df_local['Check-in Date']).dt.date
        if 'Check-out Date' in df_local.columns:
            df_local['Check-out Date'] = pd.to_datetime(df_local['Check-out Date']).dt.date

        # Active bookings on this date
        active_on_date = df_local[
            df_local['Check-in Date'].notna() &
            df_local['Check-out Date'].notna() &
            (df_local['Check-in Date'] <= target_date_obj) &
            (df_local['Check-out Date'] > target_date_obj) &
            (df_local['Tình trạng'] != 'Đã hủy')
        ]

        occupied_units = len(active_on_date)
        available_units = max(0, total_capacity - occupied_units)

        # Per-apartment occupancy
        apartments_status = []
        apt1_occupied = 0
        apt1_available = total_capacity
        apt2_occupied = 0
        apt2_available = 0

        try:
            if apartments_list:
                # Fast path — pre-loaded data, zero extra DB queries
                for apt in apartments_list:
                    apt_id = apt['id']
                    apt_name_lower = apt['name_lower']
                    room_names_lower = [r['name_lower'] for r in apt.get('rooms', [])]
                    apt_capacity = apt['capacity']

                    if not active_on_date.empty:
                        def _match(acc, _anl=apt_name_lower, _rnl=room_names_lower):
                            return _booking_matches_apartment(acc, _anl, _rnl)

                        if 'apartment_id' in active_on_date.columns:
                            id_mask = active_on_date['apartment_id'] == apt_id
                        else:
                            id_mask = pd.Series(False, index=active_on_date.index)

                        name_mask = active_on_date['Tên chỗ nghỉ'].apply(_match)
                        apt_occ = int((id_mask | name_mask).sum())
                    else:
                        apt_occ = 0

                    apt_avail = max(0, apt_capacity - apt_occ)
                    apartments_status.append({
                        'id':       apt_id,
                        'name':     apt['name'],
                        'abbr':     apt.get('abbr') or _make_apt_abbr(apt['name']),
                        'occupied': apt_occ,
                        'capacity': apt_capacity,
                        'available': apt_avail,
                    })
                    if apt_id == 1:
                        apt1_occupied, apt1_available = apt_occ, apt_avail
                    elif apt_id == 2:
                        apt2_occupied, apt2_available = apt_occ, apt_avail

            else:
                # Slow path — query DB (fallback when no pre-loaded list)
                from core.models import Apartment, Room, db
                apts_q = db.session.query(
                    Apartment.apartment_id, Apartment.apartment_name
                ).filter(Apartment.is_active == True).order_by(Apartment.apartment_id).all()

                for apt_row in apts_q:
                    apt_id = apt_row.apartment_id
                    rooms_q = db.session.query(Room.room_name).filter(
                        Room.apartment_id == apt_id, Room.is_active == True).all()
                    room_names_lower = [r.room_name.lower() for r in rooms_q]
                    apt_capacity = len(rooms_q)
                    apt_name_lower = apt_row.apartment_name.lower()

                    if not active_on_date.empty:
                        def _match(acc, _anl=apt_name_lower, _rnl=room_names_lower):
                            return _booking_matches_apartment(acc, _anl, _rnl)

                        if 'apartment_id' in active_on_date.columns:
                            id_mask = active_on_date['apartment_id'] == apt_id
                        else:
                            id_mask = pd.Series(False, index=active_on_date.index)

                        name_mask = active_on_date['Tên chỗ nghỉ'].apply(_match)
                        apt_occ = int((id_mask | name_mask).sum())
                    else:
                        apt_occ = 0

                    apt_avail = max(0, apt_capacity - apt_occ)
                    apartments_status.append({
                        'id':       apt_id,
                        'name':     apt_row.apartment_name,
                        'abbr':     _make_apt_abbr(apt_row.apartment_name),
                        'occupied': apt_occ,
                        'capacity': apt_capacity,
                        'available': apt_avail,
                    })
                    if apt_id == 1:
                        apt1_occupied, apt1_available = apt_occ, apt_avail
                    elif apt_id == 2:
                        apt2_occupied, apt2_available = apt_occ, apt_avail

        except Exception as e:
            print(f"⚠️ Error building apartments_status: {e}")

        # FIX: Recalculate available_units from room-level data.
        # occupied_units = len(active_on_date) counts ALL guest bookings (can exceed room count
        # in a hostel).  Using max(0, room_capacity - booking_count) clips to 0 even when rooms
        # are still physically available, causing false "Hết phòng".
        # Instead, derive availability from the per-apartment matched counts.
        if apartments_status:
            available_units = sum(a['available'] for a in apartments_status)

        # Activity (pass apartments_list for per-apartment counts)
        activity = get_daily_activity(df_local, target_date_obj, apartments_list=apartments_list)
        arrivals_count = len(activity['arrivals'])
        departures_count = len(activity['departures'])
        staying_count = len(activity['staying'])

        # Revenue — per-night distribution
        daily_revenue = 0
        commission_total = 0
        for _, booking in active_on_date.iterrows():
            try:
                nights = (booking['Check-out Date'] - booking['Check-in Date']).days or 1
                daily_revenue += float(booking.get('Tổng thanh toán', 0) or 0) / nights
                commission_total += float(booking.get('Hoa hồng', 0) or 0) / nights
            except (ValueError, TypeError):
                continue

        # Status
        if occupied_units == 0:
            status_text, status_color = "Trống", "empty"
        elif available_units == 0:
            status_text, status_color = "Hết phòng", "full"
        else:
            status_text, status_color = f"{available_units}/{total_capacity} trống", "occupied"

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
            'activity': activity,
            'apartments_status': apartments_status,
            # Legacy keys
            'apt1_occupied': apt1_occupied, 'apt1_available': apt1_available,
            'apt2_occupied': apt2_occupied, 'apt2_available': apt2_available,
        }

    except Exception as e:
        print(f"Error getting calendar day info: {e}")
        return {
            'occupied_units': 0, 'available_units': total_capacity,
            'status_text': "Lỗi", 'status_color': 'empty', 'error': str(e),
            'arrivals_count': 0, 'departures_count': 0, 'staying_count': 0,
            'daily_revenue': 0, 'commission_total': 0, 'revenue_minus_commission': 0,
            'activity': _empty_activity,
            'apartments_status': [],
            'apt1_occupied': 0, 'apt1_available': 4,
            'apt2_occupied': 0, 'apt2_available': 2,
        }


def prepare_dashboard_data(df: pd.DataFrame, start_date: datetime, end_date: datetime, 
                          sort_by: str, sort_order: str) -> Dict[str, Any]:
    """Prepare dashboard data from PostgreSQL using optimized SQL queries"""
    
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # Optimized query for selected period metrics
    query_selected = """
    SELECT
        COALESCE(SUM(room_amount), 0) as total_revenue,
        COUNT(booking_id) as total_guests
    FROM bookings
    WHERE checkin_date BETWEEN :start_date AND :end_date
      AND booking_status != 'cancelled';
    """
    selected_metrics_df = execute_query(query_selected, {"start_date": start_date_str, "end_date": end_date_str})

    # Convert numeric columns to proper dtypes (Railway DB may return strings)
    if not selected_metrics_df.empty:
        selected_metrics_df['total_revenue'] = pd.to_numeric(selected_metrics_df['total_revenue'], errors='coerce').fillna(0)
        selected_metrics_df['total_guests'] = pd.to_numeric(selected_metrics_df['total_guests'], errors='coerce').fillna(0)
    selected_metrics = selected_metrics_df.iloc[0]

    # Optimized query for monthly revenue (all time) - Database compatible
    # Try PostgreSQL first, fallback to SQLite if needed
    try:
        query_monthly = """
        SELECT
            to_char(checkin_date, 'YYYY-MM') as "Tháng",
            SUM(room_amount) as "Tổng thanh toán"
        FROM bookings
        WHERE booking_status != 'cancelled'
        GROUP BY 1
        ORDER BY 1;
        """
        monthly_revenue = execute_query(query_monthly)
        print(f"💰 [MONTHLY_REVENUE] PostgreSQL query returned {len(monthly_revenue)} rows")
        if not monthly_revenue.empty:
            # Convert numeric columns to proper dtypes (Railway DB may return strings)
            monthly_revenue['Tổng thanh toán'] = pd.to_numeric(monthly_revenue['Tổng thanh toán'], errors='coerce').fillna(0)
            print(f"💰 [MONTHLY_REVENUE] Sample data: {monthly_revenue.head(3).to_dict('records')}")
        else:
            print("💰 [MONTHLY_REVENUE] No data returned from PostgreSQL query")
    except Exception as e:
        print(f"⚠️ [MONTHLY_REVENUE] PostgreSQL query failed, trying SQLite: {e}")
        query_monthly = """
        SELECT
            strftime('%Y-%m', checkin_date) as "Tháng",
            SUM(room_amount) as "Tổng thanh toán"
        FROM bookings
        WHERE booking_status != 'cancelled'
        GROUP BY 1
        ORDER BY 1;
        """
        monthly_revenue = execute_query(query_monthly)
        print(f"💰 [MONTHLY_REVENUE] SQLite query returned {len(monthly_revenue)} rows")
        if not monthly_revenue.empty:
            # Convert numeric columns to proper dtypes (Railway DB may return strings)
            monthly_revenue['Tổng thanh toán'] = pd.to_numeric(monthly_revenue['Tổng thanh toán'], errors='coerce').fillna(0)
            print(f"💰 [MONTHLY_REVENUE] Sample data: {monthly_revenue.head(3).to_dict('records')}")
        else:
            print("💰 [MONTHLY_REVENUE] No data returned from SQLite query")

    # Optimized query for collector revenue (selected period)
    query_collector = """
    SELECT
        collector as "Người thu tiền",
        SUM(room_amount) as "Tổng thanh toán",
        COUNT(booking_id) as "Số đặt phòng",
        SUM(commission) as "Hoa hồng"
    FROM bookings
    WHERE checkin_date BETWEEN :start_date AND :end_date
      AND booking_status != 'cancelled'
      AND collector IN ('LOC LE', 'THAO LE')
    GROUP BY 1;
    """
    collector_revenue = execute_query(query_collector, {"start_date": start_date_str, "end_date": end_date_str})

    if not collector_revenue.empty:
        # Convert numeric columns to proper dtypes (Railway DB may return strings)
        collector_revenue['Tổng thanh toán'] = pd.to_numeric(collector_revenue['Tổng thanh toán'], errors='coerce').fillna(0)
        collector_revenue['Số đặt phòng'] = pd.to_numeric(collector_revenue['Số đặt phòng'], errors='coerce').fillna(0)
        collector_revenue['Hoa hồng'] = pd.to_numeric(collector_revenue['Hoa hồng'], errors='coerce').fillna(0)

        total_collected = collector_revenue['Tổng thanh toán'].sum()
        collector_revenue['Tỷ lệ %'] = (collector_revenue['Tổng thanh toán'] / total_collected * 100).round(1) if total_collected > 0 else 0

    return {
        'total_revenue_selected': selected_metrics['total_revenue'],
        'total_guests_selected': selected_metrics['total_guests'],
        'monthly_revenue_all_time': monthly_revenue,
        'collector_revenue_selected': collector_revenue,
        'genius_stats': pd.DataFrame(),
        'monthly_guests_all_time': pd.DataFrame(),
        'weekly_guests_all_time': pd.DataFrame(),
        'monthly_collected_revenue': pd.DataFrame()
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
    if df.empty:
        return {'duplicate_groups': [], 'total_duplicates': 0, 'total_groups': 0}

    try:
        # Check required columns
        required_columns = ['Tên người đặt', 'Check-in Date']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            return {'duplicate_groups': [], 'total_duplicates': 0, 'total_groups': 0}

        # Ensure dates are properly formatted
        df_work = df.copy()
        try:
            df_work['Check-in Date'] = pd.to_datetime(df_work['Check-in Date'])
        except Exception as date_error:
            return {'duplicate_groups': [], 'total_duplicates': 0, 'total_groups': 0}

        # Filter out null values and cancelled bookings
        df_clean = df_work.dropna(subset=['Tên người đặt', 'Check-in Date'])

        # Exclude cancelled bookings from duplicate detection
        if 'Tình trạng' in df_clean.columns:
            df_clean = df_clean[df_clean['Tình trạng'] != 'Đã hủy']

        unique_guests = df_clean['Tên người đặt'].unique()
        duplicate_groups = []

        # Performance optimization: limit processing time
        import time
        start_time = time.time()
        max_processing_time = 30  # 30 seconds timeout

        for name in unique_guests:
            # Check timeout
            if time.time() - start_time > max_processing_time:
                break
            
            guest_bookings = df_clean[df_clean['Tên người đặt'] == name].sort_values('Check-in Date')
            
            if len(guest_bookings) > 1:
                # Optimization: limit to reasonable number of bookings per guest
                if len(guest_bookings) > 20:
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
                        continue

        total_time = time.time() - start_time

        return {
            'duplicate_groups': duplicate_groups,
            'total_duplicates': len(duplicate_groups),
            'total_groups': len(duplicate_groups),
            'processing_time': total_time,
            'processed_guests': len(unique_guests),
            'total_guests': len(unique_guests)
        }

    except Exception as e:
        return {'duplicate_groups': [], 'total_duplicates': 0, 'total_groups': 0, 'error': str(e)}

# ==============================================================================
# EXPENSE MANAGEMENT
# ==============================================================================

def add_expense_to_database(expense_data: Dict) -> int:
    """Add expense to PostgreSQL and return expense_id"""
    from .models import db, Expense
    from sqlalchemy.exc import IntegrityError
    
    try:
        # CRITICAL FIX: Check and fix sequence if needed
        try:
            # Check if we have a sequence collision issue
            max_id_result = db.session.execute(db.text('SELECT COALESCE(MAX(expense_id), 0) FROM expenses')).scalar()
            current_seq_result = db.session.execute(db.text('SELECT last_value FROM expenses_expense_id_seq')).scalar()
            
            print(f"🔍 [EXPENSE_FIX] Max expense_id in table: {max_id_result}")
            print(f"🔍 [EXPENSE_FIX] Current sequence value: {current_seq_result}")
            
            # Fix sequence if it's behind the actual data
            if max_id_result >= current_seq_result:
                new_seq_value = max_id_result + 1
                db.session.execute(db.text(f'SELECT setval(\'expenses_expense_id_seq\', {new_seq_value})'))
                db.session.commit()
                print(f"✅ [EXPENSE_FIX] Reset sequence to {new_seq_value}")
                
        except Exception as seq_error:
            print(f"⚠️ [EXPENSE_FIX] Sequence check failed: {seq_error}")
            # Continue anyway - the insert might still work
        
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
        print(f"✅ [EXPENSE_SUCCESS] Added expense ID {expense_id}: {expense_data.get('description')}")
        return expense_id
        
    except IntegrityError as integrity_error:
        db.session.rollback()
        print(f"❌ [EXPENSE_INTEGRITY] Integrity error: {integrity_error}")
        
        # Try to fix sequence and retry once
        try:
            print("🔄 [EXPENSE_RETRY] Attempting to fix sequence and retry...")
            max_id_result = db.session.execute(db.text('SELECT COALESCE(MAX(expense_id), 0) FROM expenses')).scalar()
            new_seq_value = max_id_result + 1
            db.session.execute(db.text(f'SELECT setval(\'expenses_expense_id_seq\', {new_seq_value})'))
            db.session.commit()
            
            # Retry the insert
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
            print(f"✅ [EXPENSE_RETRY_SUCCESS] Added expense ID {expense_id} after sequence fix")
            return expense_id
            
        except Exception as retry_error:
            db.session.rollback()
            print(f"❌ [EXPENSE_RETRY_FAILED] Retry failed: {retry_error}")
            return None
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ [EXPENSE_ERROR] Error adding expense: {e}")
        return None

def get_expenses_from_database() -> pd.DataFrame:
    """Get all expenses from PostgreSQL with English field names for API compatibility

    Railway DB Schema: expense_id, expense_date, amount, description, category (VARCHAR), collector (VARCHAR), created_at
    """
    query = """
    SELECT
        expense_id,
        expense_date as "date",
        amount,
        description,
        category,
        collector,
        created_at
    FROM expenses
    ORDER BY expense_date DESC
    """

    result = execute_query(query)
    print(f"💰 EXPENSES QUERY: Found {len(result)} expenses in database")
    print(f"💰 EXPENSES COLUMNS: {list(result.columns) if not result.empty else 'NO DATA'}")
    if not result.empty:
        # Convert numeric columns to proper dtypes (Railway DB may return strings)
        result['amount'] = pd.to_numeric(result['amount'], errors='coerce').fillna(0)
        print(f"💰 FIRST EXPENSE: {result.iloc[0].to_dict()}")
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

def extract_booking_with_openrouter(image_data: bytes, openrouter_keys: list, room_type: str = '118 Hang Bac Hostel') -> Dict:
    """Extract booking information using OpenRouter APIs with multiple models"""
    import requests
    import json
    import base64
    
    # Convert image to base64
    try:
        image_base64 = base64.b64encode(image_data).decode('utf-8')
    except Exception as e:
        return {'error': f'Image encoding failed: {str(e)}'}
    
    # Booking extraction system prompt
    system_prompt = f"""You are an expert at extracting booking information from screenshots of booking confirmation emails, hotel booking platforms, or reservation confirmments.

Extract the following information from the image:

1. Guest Name (Full name, including first and last names)
2. Check-in Date (format: YYYY-MM-DD)
3. Check-out Date (format: YYYY-MM-DD)
4. Room Amount/Total Price (number only, no currency symbols)
5. Accommodation Name (hotel/hostel name, default to "{room_type}" if not visible)
6. Booking Platform (e.g., Booking.com, Airbnb, Agoda, etc.)
7. Number of Guests (adults + children)
8. Room Type (if specified)

CRITICAL REQUIREMENTS:
- Return ONLY valid JSON
- Use exact field names as shown below
- Convert all dates to YYYY-MM-DD format
- Extract numbers only for amounts (remove currency symbols like $, €, đ, VNĐ)
- If information is not clearly visible, use null
- Guest name should be complete (first + last name)

JSON Format:
{{
    "guest_name": "Full Name",
    "checkin_date": "YYYY-MM-DD",
    "checkout_date": "YYYY-MM-DD", 
    "room_amount": number_only,
    "accommodation_name": "{room_type}",
    "booking_platform": "platform_name",
    "guest_count": number,
    "room_type": "room_description_if_available",
    "extraction_confidence": "high/medium/low",
    "model": "openrouter_model_name"
}}

Examples:
- "John Smith" → "guest_name": "John Smith"
- "Dec 25, 2024" → "checkin_date": "2024-12-25"
- "$150.00" → "room_amount": 150
- "2 adults" → "guest_count": 2"""

    # Free models to try with OpenRouter
    free_models = [
        ('qwen/qwen3-coder:free', 'Qwen3_Coder_Free'),
        ('mistralai/mistral-7b-instruct:free', 'Mistral_7B_Free'),
        ('nousresearch/hermes-3-llama-3.1-405b:free', 'Hermes_405B_Free'),
        ('meta-llama/llama-3.1-8b-instruct:free', 'Llama3_8B_Free')
    ]
    
    # Try each OpenRouter API key with different models
    for key_name, api_key in openrouter_keys:
        for model_name, model_display in free_models:
            print(f"🤖 [BOOKING_OPENROUTER] Trying {key_name} with {model_display}")
            
            try:
                response = requests.post(
                    url="https://openrouter.ai/api/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:5000",
                        "X-Title": "Booking Extraction",
                    },
                    data=json.dumps({
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": [
                                {"type": "text", "text": "Extract booking information from this image:"},
                                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                            ]}
                        ],
                        "max_tokens": 500
                    }),
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content = result['choices'][0]['message']['content']
                    print(f"✅ [BOOKING_OPENROUTER] {model_display} - Response received")
                    
                    # Parse JSON response
                    import re
                    json_match = re.search(r'\{.*\}', content, re.DOTALL)
                    if json_match:
                        try:
                            data = json.loads(json_match.group())
                            data['model'] = model_display
                            data['extraction_method'] = f'openrouter_{model_display.lower()}'
                            
                            # Validate required fields
                            if data.get('guest_name') and data.get('checkin_date'):
                                print(f"🎯 [BOOKING_OPENROUTER] SUCCESS - Guest: {data.get('guest_name')}, Check-in: {data.get('checkin_date')}")
                                return {'success': True, **data}
                            else:
                                print(f"⚠️ [BOOKING_OPENROUTER] {model_display} - Missing required fields")
                        except json.JSONDecodeError:
                            print(f"⚠️ [BOOKING_OPENROUTER] {model_display} - JSON parsing failed")
                    else:
                        print(f"⚠️ [BOOKING_OPENROUTER] {model_display} - No JSON found in response")
                        
                else:
                    print(f"❌ [BOOKING_OPENROUTER] {model_display} - API error: {response.status_code}")
                    if response.status_code == 401:
                        print(f"   Invalid API key: {key_name}")
                        break  # Don't try other models with invalid key
                    
            except Exception as e:
                print(f"❌ [BOOKING_OPENROUTER] {model_display} - Exception: {str(e)[:100]}")
    
    return {'error': 'All OpenRouter models failed for booking extraction'}

def extract_booking_info_from_image_content_multi_api(image_data: bytes, room_type: str = '118 Hang Bac Hostel') -> Dict:
    """Extract booking information from image using Multiple Gemini APIs with auto-switching"""
    if not genai:
        return {'error': 'Gemini AI not available'}
    
    import os
    
    # Get all available Gemini API keys
    gemini_keys = []
    for i in range(1, 6):
        key_name = f'GEMINI_API_KEY_{i}' if i > 1 else 'GEMINI_API_KEY'
        key = os.getenv(key_name)
        if key and key.strip():
            gemini_keys.append((key_name, key))
    
    if not gemini_keys:
        return {'error': 'No Gemini API keys found in environment'}
    
    print(f"🔑 [MULTI_BOOKING_AI] Found {len(gemini_keys)} Gemini API keys")
    
    # Try each Gemini API key
    for key_name, api_key in gemini_keys:
        try:
            print(f"🔑 [BOOKING_AI] Trying {key_name} (length: {len(api_key)})")
            genai.configure(api_key=api_key)
            
            print(f"🤖 [BOOKING_AI] Creating model: gemini-1.5-flash")
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Convert image for Gemini
            if not Image:
                print(f"❌ PIL not available for image processing")
                return {'error': 'PIL not available for image processing on railway'}
            
            print(f"🖼️ [BOOKING_AI] Processing image data (size: {len(image_data)} bytes)")
            image = Image.open(BytesIO(image_data))
            print(f"🖼️ [BOOKING_AI] Image opened successfully: {image.format} {image.size}")
            
            prompt = """You are a booking data extraction AI. Extract ALL bookings from this image and classify the room type for EACH booking.

🏠 ROOM CLASSIFICATION RULES (Apply to EACH booking individually):

Step 1: Find the "Tên chỗ nghỉ" (property name) column for EACH booking row
Step 2: Match the property name to ONE of these rooms:

Room 1: "hang be 101"
  ✅ Property name contains: "Kitchen & Washing Machine" OR "1 BR" OR "Old Quarter - Kitchen" (single bedroom)
  ❌ Does NOT contain: "2 BR"

Room 2: "hang be 102"
  ✅ Property name contains: "2 BR" OR "Free Laundry - Kitchen" OR "2 bedroom"

Room 3: "118 Hang Bac Hostel" (DEFAULT)
  ✅ Property name contains: "Night market" OR "Kitchen & Balcony" OR any other name
  ✅ Use this as DEFAULT if property name doesn't match Room 1 or Room 2

⚠️ CRITICAL: Different bookings will have DIFFERENT property names → DIFFERENT room classifications!

📋 EXAMPLE OUTPUT (Study this carefully):

{
    "type": "multiple",
    "count": 3,
    "bookings": [
        {
            "guest_name": "John Smith",
            "booking_id": "1234567890",
            "checkin_date": "2025-11-03",
            "checkout_date": "2025-11-05",
            "room_amount": 1097820,
            "commission": 164673,
            "room_name": "hang be 101",
            "property_name_raw": "The Heart of Old Quarter - Kitchen & Washing Machine",
            "nights": 2
        },
        {
            "guest_name": "Jane Doe",
            "booking_id": "0987654321",
            "checkin_date": "2025-11-04",
            "checkout_date": "2025-11-06",
            "room_amount": 1409895,
            "commission": 211484,
            "room_name": "hang be 102",
            "property_name_raw": "The Heart Of Old Quarter 2 BR - Free Laundry - Kitchen",
            "nights": 2
        },
        {
            "guest_name": "Bob Wilson",
            "booking_id": "5555555555",
            "checkin_date": "2025-11-05",
            "checkout_date": "2025-11-07",
            "room_amount": 950000,
            "commission": 142500,
            "room_name": "118 Hang Bac Hostel",
            "property_name_raw": "Home in Old Quarter - Night market",
            "nights": 2
        }
    ]
}

📝 EXTRACTION STEPS FOR EACH BOOKING:
1. Extract: guest_name, booking_id, checkin_date (YYYY-MM-DD), checkout_date (YYYY-MM-DD)
2. Extract: room_amount (pure number, no commas), commission (pure number, 0 if not shown)
3. Extract: property_name_raw (EXACT text from "Tên chỗ nghỉ" column)
4. Classify: Apply room classification rules to property_name_raw → set room_name
5. Calculate: nights = days between checkout and checkin

🎯 REQUIRED JSON FIELDS (for each booking):
- guest_name (string)
- booking_id (string)
- checkin_date (YYYY-MM-DD format)
- checkout_date (YYYY-MM-DD format)
- room_amount (integer, no commas)
- commission (integer, no commas, use 0 if not shown)
- room_name (MUST be one of: "hang be 101", "hang be 102", "118 Hang Bac Hostel")
- property_name_raw (exact property name from image)
- nights (integer)

⚠️ VALIDATION CHECKLIST:
✓ Each booking has different room_name based on its property_name_raw
✓ room_name is EXACTLY one of: "hang be 101", "hang be 102", "118 Hang Bac Hostel"
✓ Numbers have NO commas (1097820 not 1,097,820)
✓ Dates use YYYY-MM-DD format
✓ JSON is valid (no trailing commas, proper quotes)

Return ONLY the JSON. No explanations, no markdown, no code blocks."""
            
            print(f"🤖 [BOOKING_AI] Sending image to {key_name} with room type: {room_type}")
            response = model.generate_content([prompt, image])
            
            # Check if response generation was successful
            if not response:
                print(f"⚠️ [BOOKING_AI] {key_name} returned no response object, trying next API")
                continue
            
            print(f"✅ [BOOKING_AI] {key_name} response received, checking content...")
            
            # Parse JSON from response with better error handling
            import json
            # Check if response.text exists and is not None
            if not hasattr(response, 'text') or response.text is None:
                print(f"⚠️ [BOOKING_AI] {key_name} response.text is None, trying next API")
                continue
            
            # Clean the response text - sometimes Gemini adds extra text
            response_text = response.text.strip()
            print(f"🤖 [BOOKING_AI] {key_name} response: {response_text[:200]}...")
            
            # Check if response text is empty
            if not response_text:
                print(f"⚠️ [BOOKING_AI] {key_name} response text is empty, trying next API")
                continue
            
            # Try to find JSON in the response
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_text = response_text[json_start:json_end]
                print(f"📝 [BOOKING_AI] {key_name} extracted JSON: {json_text[:100]}...")
                try:
                    result = json.loads(json_text)
                    print(f"✅ [BOOKING_AI] SUCCESS with {key_name}!")

                    # 🔍 DEBUG: Log room classification for each booking
                    if 'booking' in result:
                        bookings = [result['booking']]
                    elif 'bookings' in result:
                        bookings = result['bookings']
                    else:
                        bookings = []

                    print(f"🏠 [ROOM_DEBUG] AI returned {len(bookings)} booking(s):")
                    for i, booking in enumerate(bookings):
                        guest_name = booking.get('guest_name', 'N/A')
                        room_name = booking.get('room_name', 'NOT SET')
                        property_raw = booking.get('property_name_raw', 'NOT EXTRACTED')
                        print(f"  [{i+1}] {guest_name}: room_name='{room_name}' | property_name_raw='{property_raw}'")

                    return result
                except json.JSONDecodeError as json_error:
                    print(f"⚠️ [BOOKING_AI] {key_name} JSON decode error: {json_error}, trying next API")
                    continue
            else:
                print(f"⚠️ [BOOKING_AI] {key_name} no valid JSON found, trying next API")
                continue
                
        except Exception as e:
            error_str = str(e)
            if '429' in error_str or 'quota' in error_str.lower():
                print(f"🔄 [BOOKING_AI] {key_name} quota exceeded, trying next API...")
            else:
                print(f"❌ [BOOKING_AI] {key_name} error: {error_str[:100]}, trying next API...")
            continue
    
    # If all Gemini APIs failed, try OpenRouter as fallback
    print(f"🔄 [BOOKING_AI] All {len(gemini_keys)} Gemini APIs exhausted, trying OpenRouter...")
    
    # Get all available OpenRouter API keys
    openrouter_keys = []
    for i in range(1, 6):
        key_name = f'OPENROUTER_API_KEY_{i}' if i > 1 else 'OPENROUTER_API_KEY'
        key = os.getenv(key_name)
        if key and key.strip():
            openrouter_keys.append((key_name, key))
    
    print(f"🔑 [BOOKING_OPENROUTER] Found {len(openrouter_keys)} OpenRouter API keys")
    
    if openrouter_keys:
        # Try OpenRouter booking extraction
        openrouter_result = extract_booking_with_openrouter(image_data, openrouter_keys, room_type)
        if openrouter_result.get('success'):
            return openrouter_result
    
    # All APIs failed
    total_apis = len(gemini_keys) + len(openrouter_keys)
    print(f"❌ [BOOKING_AI] All {total_apis} APIs exhausted ({len(gemini_keys)} Gemini + {len(openrouter_keys)} OpenRouter)")
    return {'error': f'All {total_apis} APIs exhausted - booking extraction failed'}

def extract_booking_info_from_image_content(image_data: bytes, google_api_key: str, room_type: str = '118 Hang Bac Hostel') -> Dict:
    """
    Backward compatibility wrapper - now uses multi-API system
    The google_api_key parameter is ignored as we use multiple keys from environment
    """
    print("🔄 [BOOKING_AI] Using multi-API system (backward compatibility)")
    return extract_booking_info_from_image_content_multi_api(image_data, room_type)

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