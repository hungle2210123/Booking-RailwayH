-- Hotel Booking System - PostgreSQL Database Initialization Script
-- Run this script in pgAdmin 4 or DBeaver to create the database schema

-- Create database (run this as superuser)
-- CREATE DATABASE hotel_booking;

-- Connect to the hotel_booking database before running the rest

-- Enable UUID extension (optional, for better ID generation)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =====================================================
-- GUESTS TABLE - Master guest information
-- =====================================================
CREATE TABLE IF NOT EXISTS guests (
    guest_id SERIAL PRIMARY KEY,
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(50),
    nationality VARCHAR(100),
    passport_number VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_guests_email ON guests(email);
CREATE INDEX IF NOT EXISTS idx_guests_phone ON guests(phone);
CREATE INDEX IF NOT EXISTS idx_guests_name ON guests(full_name);

-- =====================================================
-- BOOKINGS TABLE - Main booking records
-- =====================================================
CREATE TABLE IF NOT EXISTS bookings (
    booking_id VARCHAR(50) PRIMARY KEY,
    guest_id INTEGER NOT NULL REFERENCES guests(guest_id) ON DELETE CASCADE,
    checkin_date DATE NOT NULL,
    checkout_date DATE NOT NULL,
    room_amount DECIMAL(12,2) DEFAULT 0,
    commission DECIMAL(12,2) DEFAULT 0,
    taxi_amount DECIMAL(12,2) DEFAULT 0,
    collector VARCHAR(255),
    booking_status VARCHAR(50) DEFAULT 'confirmed',
    booking_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_checkout_after_checkin CHECK (checkout_date > checkin_date),
    CONSTRAINT chk_positive_amounts CHECK (
        room_amount >= 0 AND 
        commission >= 0 AND 
        taxi_amount >= 0
    ),
    CONSTRAINT chk_valid_status CHECK (
        booking_status IN ('confirmed', 'cancelled', 'deleted', 'pending')
    )
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_bookings_guest_id ON bookings(guest_id);
CREATE INDEX IF NOT EXISTS idx_bookings_checkin_date ON bookings(checkin_date);
CREATE INDEX IF NOT EXISTS idx_bookings_checkout_date ON bookings(checkout_date);
CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings(booking_status);
CREATE INDEX IF NOT EXISTS idx_bookings_collector ON bookings(collector);

-- =====================================================
-- EXPENSES TABLE - Hotel expense tracking
-- =====================================================
CREATE TABLE IF NOT EXISTS expenses (
    expense_id SERIAL PRIMARY KEY,
    expense_date DATE NOT NULL,
    amount DECIMAL(12,2) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(100) DEFAULT 'general',
    collector VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_expense_amount CHECK (amount >= 0)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_expenses_category ON expenses(category);
CREATE INDEX IF NOT EXISTS idx_expenses_collector ON expenses(collector);

-- =====================================================
-- QUICK_NOTES TABLE - Dashboard quick notes
-- =====================================================
CREATE TABLE IF NOT EXISTS quick_notes (
    note_id SERIAL PRIMARY KEY,
    note_type VARCHAR(50) NOT NULL,
    note_content TEXT NOT NULL,
    is_completed BOOLEAN DEFAULT FALSE,
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Constraints
    CONSTRAINT chk_note_type CHECK (
        note_type IN ('Thu tiền', 'Hủy phòng', 'Taxi', 'general')
    )
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_quick_notes_type ON quick_notes(note_type);
CREATE INDEX IF NOT EXISTS idx_quick_notes_completed ON quick_notes(is_completed);

-- =====================================================
-- MESSAGE_TEMPLATES TABLE - Reusable message templates
-- =====================================================
CREATE TABLE IF NOT EXISTS message_templates (
    template_id SERIAL PRIMARY KEY,
    template_name VARCHAR(255) NOT NULL UNIQUE,
    template_content TEXT NOT NULL,
    category VARCHAR(100) DEFAULT 'general',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- ARRIVAL_TIMES TABLE - Guest arrival time tracking
-- =====================================================
CREATE TABLE IF NOT EXISTS arrival_times (
    arrival_id SERIAL PRIMARY KEY,
    booking_id VARCHAR(50) NOT NULL REFERENCES bookings(booking_id) ON DELETE CASCADE,
    arrival_time TIME,
    arrival_date DATE,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Unique constraint to prevent duplicate arrival times
    UNIQUE(booking_id, arrival_date)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_arrival_times_booking_id ON arrival_times(booking_id);
CREATE INDEX IF NOT EXISTS idx_arrival_times_date ON arrival_times(arrival_date);

-- =====================================================
-- UPDATE TRIGGERS - Automatically update updated_at timestamps
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic timestamp updates
DROP TRIGGER IF EXISTS update_guests_updated_at ON guests;
CREATE TRIGGER update_guests_updated_at 
    BEFORE UPDATE ON guests 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_bookings_updated_at ON bookings;
CREATE TRIGGER update_bookings_updated_at 
    BEFORE UPDATE ON bookings 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_message_templates_updated_at ON message_templates;
CREATE TRIGGER update_message_templates_updated_at 
    BEFORE UPDATE ON message_templates 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_arrival_times_updated_at ON arrival_times;
CREATE TRIGGER update_arrival_times_updated_at 
    BEFORE UPDATE ON arrival_times 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- SAMPLE DATA (Optional - for testing)
-- =====================================================

-- Insert sample guests
INSERT INTO guests (full_name, email, phone, nationality) VALUES 
('Nguyễn Văn A', 'nguyenvana@email.com', '0123456789', 'Vietnam'),
('Trần Thị B', 'tranthib@email.com', '0987654321', 'Vietnam'),
('John Smith', 'john.smith@email.com', '+1234567890', 'USA')
ON CONFLICT (email) DO NOTHING;

-- Insert sample bookings
INSERT INTO bookings (booking_id, guest_id, checkin_date, checkout_date, room_amount, commission, collector, booking_notes) VALUES 
('DEMO001', 1, CURRENT_DATE + INTERVAL '1 day', CURRENT_DATE + INTERVAL '3 days', 500000, 50000, 'Admin', 'Demo booking 1'),
('DEMO002', 2, CURRENT_DATE + INTERVAL '5 days', CURRENT_DATE + INTERVAL '7 days', 600000, 60000, 'Admin', 'Demo booking 2'),
('DEMO003', 3, CURRENT_DATE + INTERVAL '10 days', CURRENT_DATE + INTERVAL '12 days', 750000, 75000, 'Admin', 'Demo booking 3')
ON CONFLICT (booking_id) DO NOTHING;

-- Insert sample message templates
INSERT INTO message_templates (template_name, template_content, category) VALUES 
('Check-in Reminder', 'Xin chào! Đây là lời nhắc check-in cho ngày mai tại 118 Hang Bac Hostel.', 'check-in'),
('Payment Request', 'Xin chào! Vui lòng thanh toán tiền phòng cho booking của bạn.', 'payment'),
('Thank You', 'Cảm ơn bạn đã lưu trú tại 118 Hang Bac Hostel!', 'checkout')
ON CONFLICT (template_name) DO NOTHING;

-- =====================================================
-- USEFUL QUERIES FOR TESTING
-- =====================================================

-- Check table row counts
SELECT 
    'guests' as table_name, COUNT(*) as row_count FROM guests
UNION ALL
SELECT 
    'bookings' as table_name, COUNT(*) as row_count FROM bookings
UNION ALL
SELECT 
    'expenses' as table_name, COUNT(*) as row_count FROM expenses
UNION ALL
SELECT 
    'quick_notes' as table_name, COUNT(*) as row_count FROM quick_notes
UNION ALL
SELECT 
    'message_templates' as table_name, COUNT(*) as row_count FROM message_templates
UNION ALL
SELECT 
    'arrival_times' as table_name, COUNT(*) as row_count FROM arrival_times;

-- Test query: Get all bookings with guest information
SELECT 
    b.booking_id,
    g.full_name as guest_name,
    b.checkin_date,
    b.checkout_date,
    b.room_amount,
    b.commission,
    b.booking_status
FROM bookings b
JOIN guests g ON b.guest_id = g.guest_id
WHERE b.booking_status != 'deleted'
ORDER BY b.checkin_date;

-- Test query: Get revenue summary
SELECT 
    DATE_TRUNC('month', checkin_date) as month,
    COUNT(*) as booking_count,
    SUM(room_amount) as total_revenue,
    SUM(commission) as total_commission,
    SUM(room_amount - commission) as net_revenue
FROM bookings
WHERE booking_status = 'confirmed'
GROUP BY DATE_TRUNC('month', checkin_date)
ORDER BY month DESC;

COMMIT;