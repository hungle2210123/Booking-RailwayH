-- Reset collected amounts for bookings without valid collectors
-- This fixes the issue where "Paid" status was showing incorrectly

-- Reset collected_amount to 0 for bookings without valid collectors
UPDATE bookings 
SET collected_amount = 0.00 
WHERE (collector IS NULL OR collector NOT IN ('LOC LE', 'THAO LE'))
AND collected_amount > 0;

-- Show the results
SELECT 
    booking_id,
    room_amount,
    taxi_amount,
    collected_amount,
    collector,
    CASE 
        WHEN collector IN ('LOC LE', 'THAO LE') AND collected_amount > 0 THEN 'VALID PAYMENT'
        WHEN collected_amount > 0 THEN 'INVALID - NO COLLECTOR'
        ELSE 'NO PAYMENT YET'
    END as payment_status
FROM bookings 
WHERE booking_status != 'deleted'
ORDER BY booking_id;

-- Summary
SELECT 
    COUNT(*) as total_bookings,
    SUM(CASE WHEN collector IN ('LOC LE', 'THAO LE') AND collected_amount > 0 THEN 1 ELSE 0 END) as valid_payments,
    SUM(CASE WHEN collector NOT IN ('LOC LE', 'THAO LE') OR collector IS NULL THEN 1 ELSE 0 END) as no_collector,
    SUM(CASE WHEN collected_amount > 0 AND (collector NOT IN ('LOC LE', 'THAO LE') OR collector IS NULL) THEN 1 ELSE 0 END) as fixed_incorrect_payments
FROM bookings 
WHERE booking_status != 'deleted';