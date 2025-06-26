# 🔧 COLLECTED AMOUNT TRACKING - DEBUG CHEAT SHEET

## 🚀 Quick Start Commands

```bash
# 1. Apply database migration
psql -d your_database_name -f add_collected_amount.sql

# 2. Restart Flask server  
python app_postgresql.py

# 3. Check system status
python3 check_system_status.py
```

## 🔍 Debug Points to Monitor

### Server Logs (Critical)
```
🚀 [COLLECT_PAYMENT] API CALLED - Starting payment collection
💰 Setting collected_amount to: 123456
✅ VERIFICATION - collected_amount: 123456.00
```

### Database Verification
```sql
-- Check if column exists
SELECT column_name FROM information_schema.columns 
WHERE table_name = 'bookings' AND column_name = 'collected_amount';

-- Check data
SELECT booking_id, room_amount, collected_amount 
FROM bookings WHERE booking_id = 'FLASK_TEST_001';
```

### Frontend Indicators
- ✅ Green checkmark with collected amount
- ❌ Red warning with remaining amount  
- 🎯 Modal shows breakdown: Original | Collected | Remaining

## 🐛 Common Issues & Fixes

### Issue: "Column doesn't exist"
**Fix:** Run migration script
```bash
psql -d database_name -f add_collected_amount.sql
```

### Issue: "Collected amount not saving"
**Check:** API logs for `💰 Setting collected_amount to:`
**Fix:** Restart Flask server after code changes

### Issue: "Dashboard not showing green amounts"
**Check:** Template variables `{{ collected }}` and `{{ remaining }}`
**Fix:** Clear browser cache (Ctrl+Shift+Del)

### Issue: "Modal not showing payment breakdown"
**Check:** JavaScript console for errors
**Fix:** Verify `modalCollectedAmount` element exists

## 📊 Test Scenarios

### Test 1: New Payment
1. Click "Thu" button
2. Enter 123456
3. **Expect:** Green "123,456đ" with checkmark
4. **Database:** `collected_amount = 123456.00`

### Test 2: Partial Payment
1. Booking amount: 500,000đ
2. Collect: 300,000đ
3. **Expect:** Green "300,000đ" + Red "Còn: 200,000đ"

### Test 3: Full Payment
1. Booking amount: 500,000đ
2. Collect: 500,000đ  
3. **Expect:** Green "500,000đ" + "Đã thanh toán"

## 🎯 Success Indicators

### Backend Success
```
[COLLECT_PAYMENT] 💰 Setting collected_amount to: 123456
[UPDATE_BOOKING] ✅ VERIFICATION - collected_amount: 123456.00
```

### Frontend Success
- Dashboard shows green collected amount
- Modal displays payment breakdown
- No JavaScript errors in console

### Database Success
```sql
bookings.collected_amount = 123456.00  -- Your input saved!
bookings.room_amount = 500000.00       -- Original preserved
```

## 📁 Key Files & Line Numbers

| File | Line | Purpose |
|------|------|---------|
| `app_postgresql.py` | 819 | API saves collected_amount |
| `core/logic_postgresql.py` | 94 | Query includes collected data |
| `core/logic_postgresql.py` | 282 | Database update logic |
| `templates/dashboard.html` | 543 | UI payment status display |
| `templates/dashboard.html` | 1115 | Modal JavaScript function |
| `core/models.py` | 76 | Database column definition |

## 🔄 Quick Reset (If Needed)

```bash
# Reset collected amounts to 0
UPDATE bookings SET collected_amount = 0.00;

# Reset to match room amounts  
UPDATE bookings SET collected_amount = room_amount;
```

---
**💡 Pro Tip:** Watch server logs in real-time during testing to see exactly what's happening!