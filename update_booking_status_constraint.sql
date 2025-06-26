-- Update booking status constraint to allow Vietnamese status values
-- This fixes the import error for CSV data with Vietnamese status

-- Drop the existing constraint
ALTER TABLE bookings DROP CONSTRAINT IF EXISTS chk_valid_status;

-- Add new constraint with Vietnamese values
ALTER TABLE bookings ADD CONSTRAINT chk_valid_status 
CHECK (booking_status IN ('confirmed', 'cancelled', 'deleted', 'pending', 'mới', 'đã hủy', 'đã xóa', 'chờ xử lý'));

-- Show current bookings count
SELECT COUNT(*) as total_bookings FROM bookings;