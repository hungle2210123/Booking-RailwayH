"""
Hotel Booking System - Pure PostgreSQL Database Service
100% PostgreSQL - No Google Sheets dependencies
"""

import os
import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date
from flask import current_app
from contextlib import contextmanager
import pandas as pd
from sqlalchemy import text

# Import models only
from .models import db, Guest, Booking, QuickNote, Expense, MessageTemplate, ArrivalTime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =====================================================
# CONFIGURATION - POSTGRESQL ONLY
# =====================================================

class DatabaseConfig:
    """PostgreSQL-only database configuration"""
    
    # PostgreSQL is the only backend
    USE_POSTGRESQL = True
    USE_HYBRID_MODE = False
    FALLBACK_TO_SHEETS = False
    
    # Performance monitoring
    ENABLE_PERFORMANCE_LOGGING = os.getenv('ENABLE_PERFORMANCE_LOGGING', 'true').lower() == 'true'
    
    # PostgreSQL connection settings
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    @classmethod
    def get_primary_backend(cls):
        """Get the primary database backend"""
        return 'postgresql'
    
    @classmethod
    def get_fallback_backend(cls):
        """No fallback - PostgreSQL only"""
        return None
    
    @classmethod
    def get_use_postgresql(cls):
        """Always use PostgreSQL"""
        return True

# =====================================================
# PERFORMANCE MONITORING
# =====================================================

class PerformanceTimer:
    """Context manager for measuring performance"""
    
    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        duration = (self.end_time - self.start_time) * 1000  # Convert to milliseconds
        
        if DatabaseConfig.ENABLE_PERFORMANCE_LOGGING:
            logger.info(f"PERFORMANCE: {self.operation_name} (PostgreSQL) - {duration:.1f}ms")
        
        return False

# =====================================================
# EXCEPTION HANDLING
# =====================================================

class DatabaseError(Exception):
    """Base exception for database operations"""
    pass

class PostgreSQLError(DatabaseError):
    """PostgreSQL specific error"""
    pass

# =====================================================
# PURE POSTGRESQL DATABASE SERVICE
# =====================================================

class PostgreSQLDatabaseService:
    """
    Pure PostgreSQL database service
    All operations go directly to PostgreSQL
    """
    
    def __init__(self):
        self.backend_name = "PostgreSQL"
        logger.info("PostgreSQL Database Service initialized")
    
    def get_connection(self):
        """Get PostgreSQL database connection"""
        return db.engine.connect()
    
    def test_connection(self) -> Dict[str, Any]:
        """Test PostgreSQL connection"""
        try:
            with PerformanceTimer("Connection Test"):
                with self.get_connection() as conn:
                    result = conn.execute(text("SELECT 1 as test")).fetchone()
                    
            return {
                'status': 'success',
                'backend': 'postgresql',
                'message': 'PostgreSQL connection successful',
                'test_result': result[0] if result else None
            }
            
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            return {
                'status': 'error',
                'backend': 'postgresql', 
                'message': f'PostgreSQL connection failed: {str(e)}'
            }
    
    def get_all_bookings(self) -> List[Dict[str, Any]]:
        """Get all bookings from PostgreSQL"""
        try:
            with PerformanceTimer("Get All Bookings"):
                query = text("""
                    SELECT 
                        b.booking_id,
                        g.full_name as guest_name,
                        g.email,
                        g.phone,
                        b.checkin_date,
                        b.checkout_date,
                        b.room_amount,
                        b.commission,
                        b.taxi_amount,
                        b.collector,
                        b.booking_status,
                        b.booking_notes,
                        b.created_at,
                        b.updated_at,
                        CASE WHEN b.taxi_amount > 0 THEN true ELSE false END as has_taxi
                    FROM bookings b
                    JOIN guests g ON b.guest_id = g.guest_id
                    WHERE b.booking_status != 'deleted'
                    ORDER BY b.checkin_date DESC
                """)
                
                with self.get_connection() as conn:
                    result = conn.execute(query)
                    bookings = [dict(row._mapping) for row in result]
                
                logger.info(f"Retrieved {len(bookings)} bookings from PostgreSQL")
                return bookings
                
        except Exception as e:
            logger.error(f"Error getting bookings: {e}")
            raise PostgreSQLError(f"Failed to get bookings: {str(e)}")
    
    def create_booking(self, booking_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create new booking in PostgreSQL"""
        try:
            with PerformanceTimer("Create Booking"):
                # Check if guest exists
                guest = db.session.query(Guest).filter_by(
                    full_name=booking_data.get('guest_name', ''),
                    email=booking_data.get('email', '')
                ).first()
                
                if not guest:
                    # Create new guest
                    guest = Guest(
                        full_name=booking_data.get('guest_name', ''),
                        email=booking_data.get('email', ''),
                        phone=booking_data.get('phone', ''),
                        nationality=booking_data.get('nationality', ''),
                        passport_number=booking_data.get('passport_number', '')
                    )
                    db.session.add(guest)
                    db.session.flush()
                
                # Create new booking
                booking = Booking(
                    booking_id=booking_data.get('booking_id', ''),
                    guest_id=guest.guest_id,
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
                
                logger.info(f"Created booking: {booking_data.get('booking_id')}")
                
                return {
                    'status': 'success',
                    'booking_id': booking.booking_id,
                    'message': 'Booking created successfully'
                }
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating booking: {e}")
            raise PostgreSQLError(f"Failed to create booking: {str(e)}")
    
    def update_booking(self, booking_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update booking in PostgreSQL"""
        try:
            with PerformanceTimer("Update Booking"):
                booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
                
                if not booking:
                    return {
                        'status': 'error',
                        'message': f'Booking {booking_id} not found'
                    }
                
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
                for field, value in update_data.items():
                    if hasattr(booking, field):
                        setattr(booking, field, value)
                
                # Map common field names
                field_mapping = {
                    'checkin_date': 'checkin_date',
                    'checkout_date': 'checkout_date', 
                    'room_amount': 'room_amount',
                    'commission': 'commission',
                    'taxi_amount': 'taxi_amount',
                    'collector': 'collector',
                    'notes': 'booking_notes',
                    'status': 'booking_status'
                }
                
                for old_field, new_field in field_mapping.items():
                    if old_field in update_data:
                        setattr(booking, new_field, update_data[old_field])
                
                db.session.commit()
                
                logger.info(f"Updated booking: {booking_id}")
                
                return {
                    'status': 'success',
                    'booking_id': booking_id,
                    'message': 'Booking updated successfully'
                }
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating booking: {e}")
            raise PostgreSQLError(f"Failed to update booking: {str(e)}")
    
    def delete_booking(self, booking_id: str) -> Dict[str, Any]:
        """Delete booking from PostgreSQL (soft delete)"""
        try:
            with PerformanceTimer("Delete Booking"):
                booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
                
                if not booking:
                    return {
                        'status': 'error', 
                        'message': f'Booking {booking_id} not found'
                    }
                
                # Soft delete
                booking.booking_status = 'deleted'
                db.session.commit()
                
                logger.info(f"Deleted booking: {booking_id}")
                
                return {
                    'status': 'success',
                    'booking_id': booking_id,
                    'message': 'Booking deleted successfully'
                }
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting booking: {e}")
            raise PostgreSQLError(f"Failed to delete booking: {str(e)}")
    
    def get_expenses(self) -> List[Dict[str, Any]]:
        """Get all expenses from PostgreSQL"""
        try:
            with PerformanceTimer("Get Expenses"):
                query = text("""
                    SELECT 
                        expense_id,
                        expense_date,
                        amount,
                        description,
                        category,
                        collector,
                        created_at
                    FROM expenses
                    ORDER BY expense_date DESC
                """)
                
                with self.get_connection() as conn:
                    result = conn.execute(query)
                    expenses = [dict(row._mapping) for row in result]
                
                return expenses
                
        except Exception as e:
            logger.error(f"Error getting expenses: {e}")
            raise PostgreSQLError(f"Failed to get expenses: {str(e)}")
    
    def create_expense(self, expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create expense in PostgreSQL"""
        try:
            with PerformanceTimer("Create Expense"):
                expense = Expense(
                    expense_date=expense_data.get('date'),
                    amount=expense_data.get('amount', 0),
                    description=expense_data.get('description', ''),
                    category=expense_data.get('category', 'general'),
                    collector=expense_data.get('collector', '')
                )
                
                db.session.add(expense)
                db.session.commit()
                
                return {
                    'status': 'success',
                    'expense_id': expense.expense_id,
                    'message': 'Expense created successfully'
                }
                
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating expense: {e}")
            raise PostgreSQLError(f"Failed to create expense: {str(e)}")
    
    # =====================================================
    # QUICK NOTES METHODS
    # =====================================================
    
    def get_quick_notes(self) -> List[QuickNote]:
        """Get all quick notes"""
        try:
            return db.session.query(QuickNote).filter_by(is_completed=False).order_by(QuickNote.created_at.desc()).all()
        except Exception as e:
            logger.error(f"Error getting quick notes: {e}")
            return []
    
    def get_quick_note(self, note_id: int) -> Optional[QuickNote]:
        """Get specific quick note by ID"""
        try:
            return db.session.query(QuickNote).filter_by(note_id=note_id).first()
        except Exception as e:
            logger.error(f"Error getting quick note {note_id}: {e}")
            return None
    
    def create_quick_note(self, note_type: str, content: str, guest_name: str = None, 
                         booking_id: str = None, priority: str = 'normal') -> QuickNote:
        """Create new quick note"""
        try:
            logger.info(f"Creating quick note: type={note_type}, content={content[:50]}...")
            note = QuickNote(
                note_type=note_type,
                note_content=content,  # Use correct column name
                created_by=guest_name  # Map guest_name to created_by
            )
            db.session.add(note)
            db.session.commit()
            logger.info(f"Successfully created quick note {note.note_id}")
            return note
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating quick note: {e}")
            raise PostgreSQLError(f"Failed to create quick note: {str(e)}")
    
    def update_quick_note(self, note_id: int, data: Dict[str, Any]) -> Optional[QuickNote]:
        """Update quick note with proper field mapping"""
        try:
            note = db.session.query(QuickNote).filter_by(note_id=note_id).first()
            if not note:
                return None
            
            # Map frontend fields to database fields
            field_mapping = {
                'type': 'note_type',
                'content': 'note_content', 
                'guest_name': 'created_by',
                'completed': 'is_completed'
            }
            
            for key, value in data.items():
                # Use mapped field name if available, otherwise use direct field name
                db_field = field_mapping.get(key, key)
                if hasattr(note, db_field):
                    setattr(note, db_field, value)
                    logger.info(f"Updated {db_field} = {value}")
            
            db.session.commit()
            logger.info(f"Successfully updated quick note {note_id}")
            return note
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating quick note {note_id}: {e}")
            raise PostgreSQLError(f"Failed to update quick note: {str(e)}")
    
    def delete_quick_note(self, note_id: int) -> bool:
        """Delete quick note"""
        try:
            logger.info(f"Attempting to delete quick note {note_id}")
            note = db.session.query(QuickNote).filter_by(note_id=note_id).first()
            if not note:
                logger.warning(f"Quick note {note_id} not found")
                return False
            
            logger.info(f"Deleting quick note {note_id}: {note.note_content[:50]}...")
            db.session.delete(note)
            db.session.commit()
            logger.info(f"Successfully deleted quick note {note_id}")
            return True
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting quick note {note_id}: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    # =====================================================
    # ARRIVAL TIMES METHODS
    # =====================================================
    
    def get_arrival_times(self) -> List[ArrivalTime]:
        """Get all arrival times"""
        try:
            return db.session.query(ArrivalTime).all()
        except Exception as e:
            logger.error(f"Error getting arrival times: {e}")
            return []
    
    def upsert_arrival_time(self, booking_id: str, estimated_arrival: str = None, 
                           notes: str = None) -> ArrivalTime:
        """Create or update arrival time"""
        try:
            arrival_time = db.session.query(ArrivalTime).filter_by(booking_id=booking_id).first()
            
            if not arrival_time:
                arrival_time = ArrivalTime(booking_id=booking_id)
                db.session.add(arrival_time)
            
            if estimated_arrival:
                from datetime import datetime
                arrival_time.arrival_time = datetime.strptime(estimated_arrival, '%H:%M').time()  # Use correct column name
            
            if notes:
                arrival_time.notes = notes  # Use correct column name
            
            db.session.commit()
            return arrival_time
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error upserting arrival time: {e}")
            raise PostgreSQLError(f"Failed to upsert arrival time: {str(e)}")
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get PostgreSQL health status"""
        try:
            connection_test = self.test_connection()
            
            # Get database stats
            with self.get_connection() as conn:
                booking_count = conn.execute(text("SELECT COUNT(*) FROM bookings WHERE booking_status != 'deleted'")).scalar()
                guest_count = conn.execute(text("SELECT COUNT(*) FROM guests")).scalar()
                expense_count = conn.execute(text("SELECT COUNT(*) FROM expenses")).scalar()
            
            return {
                'status': 'healthy',
                'backend': 'postgresql',
                'connection': connection_test['status'],
                'stats': {
                    'bookings': booking_count,
                    'guests': guest_count,
                    'expenses': expense_count
                },
                'features': {
                    'crud_operations': True,
                    'performance_monitoring': True,
                    'data_integrity': True
                }
            }
            
        except Exception as e:
            return {
                'status': 'unhealthy',
                'backend': 'postgresql',
                'error': str(e)
            }

# =====================================================
# SERVICE INSTANCE AND HELPER FUNCTIONS
# =====================================================

# Global service instance
_database_service = None

def init_database_service(app):
    """Initialize the PostgreSQL database service"""
    global _database_service
    
    # Initialize SQLAlchemy with the app
    db.init_app(app)
    
    # Create database service
    _database_service = PostgreSQLDatabaseService()
    
    # Create tables if they don't exist
    with app.app_context():
        try:
            db.create_all()
            logger.info("Database tables created/verified")
        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
    
    logger.info("PostgreSQL Database Service initialized successfully")

def get_database_service() -> PostgreSQLDatabaseService:
    """Get the database service instance"""
    global _database_service
    
    if _database_service is None:
        raise RuntimeError("Database service not initialized. Call init_database_service() first.")
    
    return _database_service

# =====================================================
# COMPATIBILITY FUNCTIONS
# =====================================================

def get_use_postgresql() -> bool:
    """Always return True - PostgreSQL only"""
    return True

def get_primary_backend() -> str:
    """Always return postgresql"""
    return 'postgresql'

print("Pure PostgreSQL Database Service loaded successfully")