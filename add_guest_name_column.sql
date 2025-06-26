-- Add guest_name column to bookings table for quick access
-- This avoids joins when we just need the guest name

-- Add the column
ALTER TABLE bookings ADD COLUMN guest_name VARCHAR(255);

-- Populate the column with existing data from guests table
UPDATE bookings 
SET guest_name = guests.full_name 
FROM guests 
WHERE bookings.guest_id = guests.guest_id;

-- Add index for performance
CREATE INDEX idx_bookings_guest_name ON bookings(guest_name);

-- Show result
SELECT COUNT(*) as total_bookings_with_guest_names FROM bookings WHERE guest_name IS NOT NULL;