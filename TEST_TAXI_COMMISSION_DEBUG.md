# 🚕💰 Taxi & Commission Debug Guide

## 🎯 Enhanced Debugging Added

I've added **extensive debugging** to help identify exactly why taxi and commission data isn't saving.

## 🧪 Test Process

### Step 1: Clear Browser Cache
```
Ctrl + Shift + Del → Clear everything
```

### Step 2: Open Browser Console
```
F12 → Console tab
```

### Step 3: Test Taxi Payment

1. **Go to Dashboard** → Find an uncollected guest
2. **Click "Thu" button** → Modal opens
3. **Check "Có taxi" checkbox** → Should show taxi amount field
4. **Enter taxi amount** (e.g., 200000)
5. **Click submit**

### Step 4: Look for Debug Messages

**🚕 TAXI DETECTION:**
```
🔍 [TAXI] Amount element found: 200000 → 200000
🔍 [TAXI] Checkbox element found, checked: true
🔍 [TAXI] FINAL DETECTION RESULTS:
  - Raw amount input: 200000
  - Parsed amount value: 200000
  - Checkbox checked: true
  - Taxi mode active: true
  - Amount > 0: true

🚕 TAXI DETECTION:
- Checkbox: true
- Amount: 200000
- Mode: true
```

**🚕 PAYMENT TYPE DECISION:**
```
🚕 [DECISION] Determining payment type...
  - isTaxiMode: true
  - taxiAmountValue > 0: true
  - Condition check: isTaxiMode && taxiAmountValue > 0 = true
🚕 [DEBUG] TAXI MODE ACTIVATED!
🚕 [DEBUG] Set paymentType to: taxi
```

**📤 FINAL REQUEST:**
```
📤 [DEBUG] Final request data being sent:
{
  booking_id: "FLASK_TEST_001",
  collected_amount: 200000,
  payment_type: "taxi",  ← THIS IS CRITICAL!
  ...
}
```

### Step 5: Test Commission

1. **In the same modal** → Enter commission amount
2. **Make sure "Có hoa hồng" is selected**
3. **Enter amount** (e.g., 50000)
4. **Click submit**

**💰 COMMISSION DETECTION:**
```
💰 [COMMISSION] Has commission selected
  - Raw input value: 50000
  - Parsed commission: 50000

💰 COMMISSION DETECTED:
- Amount: 50000đ
- No commission: false
```

## 🔍 Troubleshooting

### Issue 1: Taxi Elements Not Found
```
❌ [TAXI] Amount element NOT FOUND!
❌ [TAXI] Checkbox element NOT FOUND!
```
**Solution:** Modal elements missing - refresh page

### Issue 2: Taxi Mode Not Activating
```
🔍 [TAXI] Checkbox element found, checked: false
  - Taxi mode active: false
```
**Solution:** Checkbox event listeners not working - check modal setup

### Issue 3: Wrong Payment Type Sent
```
🏠 [DEBUG] ROOM MODE (default)
🏠 [DEBUG] Set paymentType to: room
```
**Solution:** Taxi detection logic failing - check conditions

### Issue 4: Commission Not Detected
```
💰 [COMMISSION] No commission selected (commission = 0)
```
**Solution:** Commission checkbox or input field issue

## 📊 Expected Server Logs

**Correct Taxi Payment:**
```
[COLLECT_PAYMENT]   - payment_type: 'taxi' ⭐ CRITICAL ⭐
[COLLECT_PAYMENT] 🚕 TAXI PAYMENT: taxi_amount = 200000.0
[UPDATE_BOOKING] 🚕 TAXI UPDATE:
[UPDATE_BOOKING]   - OLD taxi_amount: 0
[UPDATE_BOOKING]   - NEW taxi_amount: 200000.0
```

**Correct Commission Update:**
```
[COLLECT_PAYMENT]   - commission_amount: 50000
[COLLECT_PAYMENT] Setting commission to 50000
[UPDATE_BOOKING]   - commission: 50000.00
```

## 🏪 Management Table Check

After successful payment, check `/bookings` page:

**Expected Display:**
- **Taxi Column:** Badge with "200,000đ" (not dash -)
- **Commission:** Should show in booking details
- **Notes:** Should show updated payment info

**If Still Showing Dash (-):**
- Data saved to PostgreSQL but display issue
- Check `load_booking_data()` function
- Check template rendering logic

## 🎯 Quick Fix Checklist

- [ ] Browser cache cleared
- [ ] Console shows taxi detection alerts
- [ ] Console shows "TAXI MODE ACTIVATED!"
- [ ] Request data shows `payment_type: "taxi"`
- [ ] Server logs show taxi update
- [ ] Database contains taxi amount
- [ ] Bookings page shows taxi badge

---

**With this enhanced debugging, we can pinpoint exactly where the taxi/commission detection is failing! 🔧**