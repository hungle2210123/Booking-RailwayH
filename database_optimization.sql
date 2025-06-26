-- Professional Database Optimization for Hotel Booking System
-- Execute these commands to optimize search and filter performance

-- 1. COMPOSITE INDEXES FOR SEARCH PERFORMANCE
-- Optimizes guest name + booking ID searches
CREATE INDEX IF NOT EXISTS idx_bookings_search_composite 
ON bookings (guest_id, booking_status, checkin_date DESC);

-- Optimizes date range filtering (most common filter)
CREATE INDEX IF NOT EXISTS idx_bookings_date_range 
ON bookings (checkin_date, checkout_date) 
WHERE booking_status != 'cancelled';

-- Optimizes payment status filtering
CREATE INDEX IF NOT EXISTS idx_bookings_payment_status 
ON bookings (collector, collected_amount, commission);

-- 2. SEARCH-SPECIFIC INDEXES
-- Full-text search optimization for guest names
CREATE INDEX IF NOT EXISTS idx_guests_fulltext_search 
ON guests USING gin(to_tsvector('english', full_name || ' ' || COALESCE(email, '') || ' ' || COALESCE(phone, '')));

-- Booking ID search optimization
CREATE INDEX IF NOT EXISTS idx_bookings_id_search 
ON bookings USING gin(to_tsvector('english', booking_id));

-- 3. FILTER PERFORMANCE INDEXES
-- Status + date combination (very common)
CREATE INDEX IF NOT EXISTS idx_bookings_status_date 
ON bookings (booking_status, checkin_date DESC) 
WHERE booking_status IN ('confirmed', 'pending');

-- Commission analysis optimization
CREATE INDEX IF NOT EXISTS idx_bookings_commission_analysis 
ON bookings (commission DESC, checkin_date) 
WHERE commission > 0;

-- Payment collection optimization
CREATE INDEX IF NOT EXISTS idx_bookings_collection_status 
ON bookings (collected_amount, room_amount, checkin_date) 
WHERE collected_amount < room_amount;

-- 4. PARTIAL INDEXES FOR ACTIVE DATA
-- Only index active/future bookings for faster interested guests filter
CREATE INDEX IF NOT EXISTS idx_bookings_active_guests 
ON bookings (checkout_date, collected_amount, collector) 
WHERE checkout_date >= CURRENT_DATE OR collected_amount = 0;

-- 5. PERFORMANCE STATISTICS UPDATE
-- Update table statistics for query optimizer
ANALYZE bookings;
ANALYZE guests;

-- 6. QUERY PERFORMANCE VERIFICATION
-- Check index usage (run after creating indexes)
EXPLAIN (ANALYZE, BUFFERS) 
SELECT b.booking_id, g.full_name, b.checkin_date, b.collected_amount
FROM bookings b 
JOIN guests g ON b.guest_id = g.guest_id 
WHERE g.full_name ILIKE '%nguyen%' 
AND b.checkin_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY b.checkin_date DESC;

-- 7. INDEX MONITORING QUERIES
-- Monitor index effectiveness
SELECT 
    schemaname, 
    tablename, 
    indexname, 
    idx_scan as index_scans,
    idx_tup_read as tuples_read,
    idx_tup_fetch as tuples_fetched
FROM pg_stat_user_indexes 
WHERE schemaname = 'public' 
ORDER BY idx_scan DESC;