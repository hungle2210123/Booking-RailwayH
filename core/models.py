"""
Hotel Booking System - SQLAlchemy Models
Enterprise PostgreSQL Schema Implementation
"""

from datetime import datetime, date, time
from typing import Optional
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, Boolean, DECIMAL, Date, Time, DateTime
from sqlalchemy import ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property

db = SQLAlchemy()

# =====================================================
# GUESTS TABLE - Master guest information
# =====================================================
class Guest(db.Model):
    __tablename__ = 'guests'
    
    # Primary identification
    guest_id = Column(Integer, primary_key=True, autoincrement=True)
    full_name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), unique=True, index=True)
    phone = Column(String(50), index=True)
    nationality = Column(String(100))
    passport_number = Column(String(100))
    
    # Audit fields
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    bookings = relationship("Booking", back_populates="guest", cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint("email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'", name='email_format'),
    )
    
    def __repr__(self):
        return f"<Guest {self.guest_id}: {self.full_name}>"
    
    def to_dict(self):
        return {
            'guest_id': self.guest_id,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'nationality': self.nationality,
            'passport_number': self.passport_number,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# =====================================================
# BOOKINGS TABLE - Core booking information
# =====================================================
class Booking(db.Model):
    __tablename__ = 'bookings'
    
    # Primary identification
    booking_id = Column(String(50), primary_key=True)
    guest_id = Column(Integer, ForeignKey('guests.guest_id', ondelete='RESTRICT'), nullable=False, index=True)
    guest_name = Column(String(255), nullable=True, index=True)  # Denormalized guest name for quick access
    
    # Booking details
    checkin_date = Column(Date, nullable=False, index=True)
    checkout_date = Column(Date, nullable=False, index=True)
    
    # Financial information
    room_amount = Column(DECIMAL(12, 2), default=0.00, nullable=False)
    taxi_amount = Column(DECIMAL(12, 2), default=0.00, nullable=False)
    commission = Column(DECIMAL(12, 2), default=0.00, nullable=False)
    collected_amount = Column(DECIMAL(12, 2), default=0.00, nullable=False)  # Track actual money collected
    
    # Payment tracking
    collector = Column(String(255))
    
    # Booking status
    booking_status = Column(String(50), default='confirmed', index=True)
    
    
    # Notes and comments
    booking_notes = Column(Text)
    
    # Audit fields
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    guest = relationship("Guest", back_populates="bookings")
    arrival_time = relationship("ArrivalTime", back_populates="booking", uselist=False, cascade="all, delete-orphan")
    
    # Constraints
    __table_args__ = (
        CheckConstraint('checkout_date > checkin_date', name='chk_checkout_after_checkin'),
        CheckConstraint('room_amount >= 0 AND taxi_amount >= 0 AND commission >= 0 AND collected_amount >= 0', name='chk_positive_amounts'),
        CheckConstraint("booking_status IN ('confirmed', 'cancelled', 'deleted', 'pending', 'mới', 'đã hủy', 'đã xóa', 'chờ xử lý')", name='chk_valid_status'),
    )
    
    @hybrid_property
    def nights(self):
        """Calculate number of nights"""
        if self.checkin_date and self.checkout_date:
            return (self.checkout_date - self.checkin_date).days
        return 0
    
    @hybrid_property
    def total_amount(self):
        """Calculate total amount"""
        return (self.room_amount or 0) + (self.taxi_amount or 0)
    
    @hybrid_property
    def has_taxi(self):
        """Check if booking has taxi"""
        return (self.taxi_amount or 0) > 0
    
    def __repr__(self):
        return f"<Booking {self.booking_id}: {self.guest.full_name if self.guest else 'N/A'}>"
    
    def to_dict(self):
        return {
            'booking_id': self.booking_id,
            'guest_id': self.guest_id,
            'guest_name': self.guest.full_name if self.guest else None,
            'checkin_date': self.checkin_date.isoformat() if self.checkin_date else None,
            'checkout_date': self.checkout_date.isoformat() if self.checkout_date else None,
            'nights': self.nights,
            'room_amount': float(self.room_amount) if self.room_amount else 0.0,
            'taxi_amount': float(self.taxi_amount) if self.taxi_amount else 0.0,
            'commission': float(self.commission) if self.commission else 0.0,
            'collected_amount': float(self.collected_amount) if self.collected_amount else 0.0,
            'total_amount': float(self.total_amount),
            'collector': self.collector,
            'booking_status': self.booking_status,
            'has_taxi': self.has_taxi,
            'booking_notes': self.booking_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# =====================================================
# QUICK_NOTES TABLE - Enhanced note system
# =====================================================
class QuickNote(db.Model):
    __tablename__ = 'quick_notes'
    
    note_id = Column(Integer, primary_key=True)
    
    # Note categorization  
    note_type = Column(String(50), nullable=False, index=True)
    
    # Content (matches database_init.sql)
    note_content = Column(Text, nullable=False)
    
    # Status tracking (matches database_init.sql)
    is_completed = Column(Boolean, default=False, index=True)
    completed_at = Column(DateTime)
    
    # Audit fields (matches database_init.sql)
    created_at = Column(DateTime, default=func.current_timestamp())
    created_by = Column(String(255))
    
    # Constraints (matches database_init.sql)
    __table_args__ = (
        CheckConstraint("note_type IN ('Thu tiền', 'Hủy phòng', 'Taxi', 'general')", name='chk_note_type'),
    )
    
    def __repr__(self):
        return f"<QuickNote {self.note_id}: {self.note_type}>"
    
    def to_dict(self):
        return {
            'note_id': self.note_id,
            'note_type': self.note_type,
            'content': self.note_content,  # Map to expected frontend field name
            'completed': self.is_completed,  # Map to expected frontend field name
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }

# =====================================================
# EXPENSES TABLE - Financial tracking
# =====================================================
class Expense(db.Model):
    __tablename__ = 'expenses'
    
    expense_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Expense details
    description = Column(Text, nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    expense_date = Column(Date, nullable=False, index=True)
    category = Column(String(100), default='general', index=True)
    collector = Column(String(255))
    
    # Audit fields
    created_at = Column(DateTime, default=func.current_timestamp())
    
    # Constraints
    __table_args__ = (
        CheckConstraint('amount >= 0', name='chk_expense_amount'),
    )
    
    def __repr__(self):
        return f"<Expense {self.expense_id}: {self.description[:50]}>"
    
    def to_dict(self):
        return {
            'expense_id': self.expense_id,
            'description': self.description,
            'amount': float(self.amount),
            'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'category': self.category,
            'collector': self.collector,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

# =====================================================
# MESSAGE_TEMPLATES TABLE - Template management
# =====================================================
class MessageTemplate(db.Model):
    __tablename__ = 'message_templates'
    
    template_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Template identification
    template_name = Column(String(255), nullable=False, unique=True)
    category = Column(String(100), default='general')
    
    # Content
    template_content = Column(Text, nullable=False)
    
    
    # Audit fields
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    
    def __repr__(self):
        return f"<MessageTemplate {self.template_id}: {self.template_name}>"
    
    def to_dict(self):
        return {
            'template_id': self.template_id,
            'template_name': self.template_name,
            'category': self.category,
            'template_content': self.template_content,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# =====================================================
# ARRIVAL_TIMES TABLE - Guest arrival tracking
# =====================================================
class ArrivalTime(db.Model):
    __tablename__ = 'arrival_times'
    
    arrival_id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(String(50), ForeignKey('bookings.booking_id', ondelete='CASCADE'), nullable=False)
    
    # Time details (matches database_init.sql)
    arrival_time = Column(Time)
    arrival_date = Column(Date)
    
    # Notes (matches database_init.sql)
    notes = Column(Text)
    
    # Audit fields (matches database_init.sql)
    created_at = Column(DateTime, default=func.current_timestamp())
    updated_at = Column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # Relationships
    booking = relationship("Booking", back_populates="arrival_time")
    
    def __repr__(self):
        return f"<ArrivalTime {self.arrival_id}: {self.booking_id}>"
    
    def to_dict(self):
        return {
            'arrival_id': self.arrival_id,
            'booking_id': self.booking_id,
            'estimated_arrival': self.arrival_time.isoformat() if self.arrival_time else None,  # Map to expected frontend field
            'arrival_date': self.arrival_date.isoformat() if self.arrival_date else None,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

# =====================================================
# DATABASE UTILITY FUNCTIONS
# =====================================================

def init_db(app):
    """Initialize database with Flask app"""
    db.init_app(app)
    
def create_all_tables(app):
    """Create all tables"""
    with app.app_context():
        db.create_all()
        print("All PostgreSQL tables created successfully!")

def drop_all_tables(app):
    """Drop all tables (use with caution!)"""
    with app.app_context():
        db.drop_all()
        print("WARNING: All PostgreSQL tables dropped!")

def get_db_stats(app):
    """Get database statistics"""
    with app.app_context():
        stats = {}
        stats['guests'] = Guest.query.count()
        stats['bookings'] = Booking.query.filter(Booking.booking_status != 'deleted').count()
        stats['quick_notes'] = QuickNote.query.count()
        stats['expenses'] = Expense.query.count()
        stats['message_templates'] = MessageTemplate.query.count()
        stats['arrival_times'] = ArrivalTime.query.count()
        return stats

# =====================================================
# SAMPLE DATA FUNCTIONS
# =====================================================

def create_sample_data(app):
    """Create sample data for testing"""
    with app.app_context():
        # Clear existing data
        db.session.query(QuickNote).delete()
        db.session.query(ArrivalTime).delete()
        db.session.query(Booking).delete()
        db.session.query(Guest).delete()
        db.session.query(Expense).delete()
        db.session.query(MessageTemplate).delete()
        
        # Create sample guests
        guest1 = Guest(
            full_name="John Smith",
            email="john.smith@email.com",
            phone="+1234567890",
            nationality="USA"
        )
        guest2 = Guest(
            full_name="Alice Johnson", 
            email="alice.j@email.com",
            phone="+1987654321",
            nationality="Canada"
        )
        guest3 = Guest(
            full_name="Nguyen Van A",
            email="nguyenvana@email.com", 
            phone="+84123456789",
            nationality="Vietnam"
        )
        
        db.session.add_all([guest1, guest2, guest3])
        db.session.flush()  # Get IDs
        
        # Create sample bookings
        from datetime import date, timedelta
        today = date.today()
        
        booking1 = Booking(
            booking_id="BK2025001",
            guest_id=guest1.guest_id,
            checkin_date=today,
            checkout_date=today + timedelta(days=3),
            room_amount=350000,
            taxi_amount=50000,
            booking_status="confirmed"
        )
        
        booking2 = Booking(
            booking_id="BK2025002", 
            guest_id=guest2.guest_id,
            checkin_date=today + timedelta(days=1),
            checkout_date=today + timedelta(days=5),
            room_amount=400000,
            taxi_amount=0,
            booking_status="confirmed"
        )
        
        booking3 = Booking(
            booking_id="BK2025003",
            guest_id=guest3.guest_id, 
            checkin_date=today - timedelta(days=1),
            checkout_date=today + timedelta(days=2),
            room_amount=300000,
            taxi_amount=30000,
            booking_status="confirmed"
        )
        
        db.session.add_all([booking1, booking2, booking3])
        
        # Create sample quick notes
        note1 = QuickNote(
            note_type="Thu tiền",
            note_content="Thu tiền từ khách John Smith",
            created_by="John Smith"
        )
        
        note2 = QuickNote(
            note_type="Taxi", 
            note_content="Đặt taxi cho khách Alice Johnson",
            created_by="Alice Johnson"
        )
        
        db.session.add_all([note1, note2])
        
        # Create sample templates
        template1 = MessageTemplate(
            template_name="Welcome Message",
            category="check-in", 
            template_content="Welcome to our hotel! Thank you for your reservation."
        )
        
        template2 = MessageTemplate(
            template_name="Checkout Message",
            category="checkout",
            template_content="Thank you for staying with us! We hope you enjoyed your stay."
        )
        
        template3 = MessageTemplate(
            template_name="Taxi Arrangement",
            category="taxi",
            template_content="Your taxi to the airport has been arranged. The driver will contact you 30 minutes before pickup."
        )
        
        db.session.add_all([template1, template2, template3])
        
        # Commit all changes
        db.session.commit()
        print("Sample data created successfully!")
        
        return get_db_stats(app)