-- Add collected_amount column to bookings table
-- This column tracks the actual money collected from customers

-- Check if column exists, if not add it
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'bookings' 
        AND column_name = 'collected_amount'
    ) THEN
        ALTER TABLE bookings 
        ADD COLUMN collected_amount DECIMAL(12, 2) DEFAULT 0.00 NOT NULL;
        
        -- Update existing bookings to set collected_amount = room_amount initially
        UPDATE bookings 
        SET collected_amount = room_amount 
        WHERE collected_amount = 0.00;
        
        RAISE NOTICE 'Added collected_amount column and updated existing data';
    ELSE
        RAISE NOTICE 'collected_amount column already exists';
    END IF;
END $$;