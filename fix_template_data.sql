-- Fix template_name column data in PostgreSQL
-- This script corrects the mapping: Label → template_name, Message → template_content

BEGIN;

-- Clear existing templates first
DELETE FROM message_templates;

-- Insert templates with CORRECT field mapping

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (1, 'DON PHONG - DEFAULT', 'DON PHONG', 'Youre welcome! Please feel free to relax and get some breakfast.
Well get your room ready and clean for you, and Ill let you know as soon as possible when its all set', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (2, 'Standard Welcome', 'WELCOME', 'Welcome!
Thanks for your reservation. We look forward to seeing you soon', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (3, 'Arrival Time Request', 'WELCOME', 'Hello Alejandro,
Ive received your reservation for 118 Hang Bac.
Could you please let me know your approximate arrival time for today?', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (4, 'Arrival Information DEFAULT', 'ARRIVAL', 'When you arrive at 118 Hang Bac, please text me  I will guide you to your room.', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (5, 'EARLY CHECK IN - DEFAULT', 'EARLY CHECK IN', 'Hello, Im so sorry, but the room isnt available right now.
Youre welcome to leave your luggage here and use the Wi-Fi.', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (6, 'Ill check again around 12', 'EARLY CHECK IN', '00 AM and let you know as soon as possible when its all set', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (7, 'Check-in Instructions DEFAULT', 'CHECK IN', 'When you arrive at 118 Hang Bac Street, you will see a souvenir shop at the front.
Please walk into the shop about 10 meters, and you will find a staircase on your right-hand side.
Go up the stairs, then look for your room number.
The door will be unlocked, and the key will be inside the room.', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (8, 'Feedback Message DEFAULT', 'FEED BACK', 'We hope you had a wonderful stay!
Wed love to hear about your experience – feel free to leave us a review on Booking.com', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (9, 'PARK - DEFAULT', 'PARK', 'Please park your motorbike across the street, but make sure not to block their right-side door.', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (10, 'LAUNDRY - DEFAULT', 'LAUNDRY', 'you''re welcome to use the washer and dryer on the 3rd floor for free.
We would appreciate it if you could use them for larger loads when possible. Thank you!', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (11, 'Airport Pickup - Pillar 14', 'TAXI', 'Once you have landed and are outside the terminal, please go to Pillar 14. It will be easier for my driver to find you there. Thank you!', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (12, 'Driver Booking Confirmation', 'TAXI', 'Okay, your driver is booked. I''ll send the driver''s info very soon. When you arrive, please try to connect to airport WiFi; the driver will contact you on WhatsApp
Could I get your flight number so my driver can check the arrival time and gate to pick you up?', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (13, 'Taxi Service Offer', 'TAXI', 'Have you arranged transportation from the airport yet? I have a driver who offers cheap taxi rates. Would you like me to book it for you? If you''d like to confirm the booking, kindly let me know
It''s only 280,000 VND. That''s cheaper than usual because I have my own driver readily available at the airport . You''re welcome to check normal prices and compare. Please feel free to message me if you need anything, and I''ll arrange a driver for you right at the airport', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (14, 'NOT BOOKING - DEFAULT', 'NOT BOOKING', 'Regarding payment, I can offer you a 150,000 VND (approx. $5.80 USD) discount if you''re comfortable paying me directly in cash for the room, rather than through the booking platform.
This is just an option, of course – no pressure at all! Please let me know if you''re interested .', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (15, 'HET PHONG - 2', 'HET PHONG', 'We sincerely apologize for this inconvenience. Due to an unforeseen and critical issue, namely an electrical leak, the room you booked is unfortunately no longer available. For your safety, we must address this immediately. Therefore, we unfortunately need to cancel your booking. We sincerely apologize for this situation and seek your understanding for this necessary cancellation.

Thank you for your understanding. We hope to have the pleasure of welcoming you on your next visit. Have a pleasant evening', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (16, 'bye bye', 'FEED BACK', 'We hope you had a wonderful stay!

For your next trip, if you need a room, please feel free to contact us directly. As a thank you for being a valued guest, we''d be happy to offer you a 10% discount on your next booking when you reserve directly with us. We look forward to welcoming you again next time

If you need a taxi to the airport, please don''t hesitate to let me know. I can arrange one for you at a special discounted rate that our guests often appreciate.', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (17, 'NOT BOOKING - 2', 'NOT BOOKING', 'Regarding payment, I can offer you a 150,000 VND (approx. $5.80 USD) discount if you''re comfortable paying me directly in cash for the room, rather than through the booking platform.This is just an option, of course – no pressure at all! Please let me know if you''re interested .If you agree to this, I will then cancel your reservation on the booking app.', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (18, 'Apology with Discounts', 'FEED BACK', 'As a gesture of our sincere apology, we''d like to make two separate offers. First, we''d like to offer you a 10% discount for your next booking with us. Second, when you are leaving Hanoi, we can also arrange an airport taxi for you for the special price of just 250,000 VND. Please contact us in advance if you wish to use these offers.', NOW(), NOW());

INSERT INTO message_templates (template_id, template_name, category, template_content, created_at, updated_at)
VALUES (19, 'HET PHONG - 4', 'HET PHONG', 'Jack, I am so incredibly sorry, but we have an emergency.
We''ve just discovered a serious electrical problem in your room. For your safety, we absolutely cannot let you check in.

This means we must unfortunately cancel your booking. I am so sorry for this terrible timing.', NOW(), NOW());

-- Reset sequence to continue from last ID
SELECT setval('message_templates_template_id_seq', (SELECT MAX(template_id) FROM message_templates));

COMMIT;

-- Verify the fix
SELECT template_id, template_name, category, 
       CASE WHEN LENGTH(template_content) > 50 
            THEN SUBSTRING(template_content, 1, 50) || '...' 
            ELSE template_content 
       END as content_preview
FROM message_templates 
ORDER BY category, template_name 
LIMIT 20;
