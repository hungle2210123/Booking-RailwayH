# 🚕 Live Taxi Payment Debug Guide

## 🎯 Purpose
This guide will help you debug why taxi payments are not showing in the database.

## 🔧 Enhanced Debugging Features Added

### 1. **Enhanced API Logging**
The `/api/collect_payment` endpoint now has detailed logging that shows:
- All received parameters
- Whether `payment_type` is set to 'taxi'
- The exact `update_data` being sent to database

### 2. **Database Update Verification**
The `update_booking` function now:
- Logs before and after taxi_amount values
- Re-queries the database after commit to verify the update
- Shows the actual database values after saving

### 3. **Debug Endpoint**
New endpoint: `/api/debug_booking/<booking_id>`
- Shows raw database values
- Compares with query results
- Helps identify data discrepancies

## 🧪 Step-by-Step Testing Process

### Step 1: Test Taxi Payment Collection
1. **Go to Dashboard** → Find an uncollected guest
2. **Click "Thu" button** → Collection modal opens
3. **Check "Có taxi" checkbox** → Taxi amount field appears
4. **Enter taxi amount** (e.g., 200000)
5. **Select collector** (LOC LE or THAO LE)
6. **Click "Xác nhận"**

### Step 2: Check Server Logs
**Look for these log messages:**
```
🚀 [COLLECT_PAYMENT] API CALLED - Starting payment collection
🔍 [COLLECT_PAYMENT] Raw request data: {...}
[COLLECT_PAYMENT] 🎯 EXTRACTED VALUES:
[COLLECT_PAYMENT]   - payment_type: 'taxi' ⭐ CRITICAL ⭐
[COLLECT_PAYMENT] 🚕 TAXI PAYMENT: taxi_amount = 200000.0
[UPDATE_BOOKING] 🚕 TAXI UPDATE:
[UPDATE_BOOKING]   - OLD taxi_amount: 0
[UPDATE_BOOKING]   - NEW taxi_amount: 200000.0
[UPDATE_BOOKING] ✅ VERIFICATION - Booking after commit:
[UPDATE_BOOKING]   - taxi_amount: 200000.0
```

### Step 3: Verify Database State
**Option A: Use Debug Endpoint**
- Visit: `http://your-app-url/api/debug_booking/BOOKING_ID`
- Check the JSON response for `taxi_amount`

**Option B: Check in DBeaver/pgAdmin**
```sql
SELECT booking_id, taxi_amount, commission, booking_notes, updated_at 
FROM bookings 
WHERE booking_id = 'YOUR_BOOKING_ID';
```

### Step 4: Check Template Display
1. **Go to Bookings page** (`/bookings`)
2. **Find your booking** in the table
3. **Look at the 🚕 Taxi column**
4. **Should show**: `Badge: 200,000đ` (not `-`)

## 🔍 Troubleshooting Scenarios

### Scenario A: Frontend Issue
**Symptoms:** Server logs show `payment_type: 'room'` instead of `'taxi'`
**Solution:** JavaScript issue - taxi checkbox not working
**Fix:** Check browser console for errors

### Scenario B: Backend Processing Issue  
**Symptoms:** Server logs show `payment_type: 'taxi'` but no taxi_amount update
**Solution:** Logic error in payment processing
**Fix:** Check the if/else logic in collect_payment function

### Scenario C: Database Update Issue
**Symptoms:** Logs show taxi_amount update but verification shows old value
**Solution:** Database transaction not committing
**Fix:** Check database connection and transaction handling

### Scenario D: Query Issue
**Symptoms:** Database shows taxi_amount but bookings page shows `-`
**Solution:** SQL query or template issue
**Fix:** Check `load_booking_data()` function and template logic

### Scenario E: Cache Issue
**Symptoms:** Everything looks correct but display doesn't update
**Solution:** Data cache not clearing
**Fix:** Hard refresh browser (Ctrl+F5) or restart app

## 🚨 Common Issues & Quick Fixes

### Issue 1: "Có taxi" checkbox doesn't show amount field
```javascript
// Check in browser console:
document.getElementById('hasTaxi').addEventListener('change', function() {
    console.log('Taxi checkbox changed:', this.checked);
});
```

### Issue 2: Frontend sends wrong payment_type
```javascript
// Add this debug in dashboard.html collectPayment() function:
console.log('Payment type being sent:', paymentType);
console.log('Has taxi checked:', document.getElementById('hasTaxi').checked);
```

### Issue 3: Database shows update but template shows dash
```sql
-- Check if data exists:
SELECT taxi_amount, 
       CASE WHEN taxi_amount > 0 THEN 'Should show badge' ELSE 'Shows dash' END as display_status
FROM bookings 
WHERE booking_id = 'YOUR_BOOKING_ID';
```

## 📋 Test Checklist

When testing taxi payment collection, verify each step:

- [ ] **Frontend**: Taxi checkbox works (shows/hides amount field)
- [ ] **Frontend**: Amount field accepts numeric input  
- [ ] **Frontend**: Sends `payment_type: 'taxi'` in API request
- [ ] **Backend**: Receives `payment_type: 'taxi'` in logs
- [ ] **Backend**: Creates `update_data` with `taxi_amount`
- [ ] **Backend**: Calls `update_booking()` function
- [ ] **Database**: `taxi_amount` field updated in `bookings` table
- [ ] **Query**: `load_booking_data()` returns correct taxi value
- [ ] **Template**: Bookings page shows taxi amount badge
- [ ] **DBeaver**: Can see updated data in database browser

## 🎯 Expected Success Flow

```
1. User checks "Có taxi" → Amount field appears ✅
2. User enters 200000 → JavaScript validates ✅  
3. User clicks save → API called with payment_type:'taxi' ✅
4. Backend processes → update_data contains taxi_amount:200000 ✅
5. Database updates → bookings.taxi_amount = 200000 ✅
6. Verification → Re-query confirms update ✅
7. Cache clears → Fresh data loaded ✅
8. Page reloads → Template shows "Badge: 200,000đ" ✅
9. DBeaver check → Can see taxi_amount = 200000 ✅
```

## 💡 Debugging Tips

1. **Always check server logs first** - they show the exact flow
2. **Use the debug endpoint** - it shows raw database vs query data  
3. **Check browser console** - for JavaScript errors
4. **Test with small amounts** - easier to track (e.g., 1000đ)
5. **Use different browsers** - to rule out caching issues

## 🔧 Quick Test Commands

**Test the debug endpoint:**
```bash
curl http://localhost:5000/api/debug_booking/FLASK_TEST_001
```

**Test payment collection:**
```bash
curl -X POST http://localhost:5000/api/collect_payment \
  -H "Content-Type: application/json" \
  -d '{
    "booking_id": "FLASK_TEST_001",
    "collected_amount": 200000,
    "collector_name": "LOC LE", 
    "payment_type": "taxi",
    "commission_amount": 0,
    "commission_type": "none"
  }'
```

---

**With these enhancements, you should be able to identify exactly where the taxi payment process is failing and fix it accordingly!** 🚕✅