# Guest Double-Counting Fix Summary

## Problem Description
The revenue calendar was double-counting guests who checked in on a specific date. Users reported:
> "The system reports that the number of guests checking in is 3, but the guests staying are still 3 guests checking in and in summary, it still reports that these 3 guests are added twice. If the guest checks in, don't show that they are staying anymore. Only show it once."

## Root Cause Analysis

### Location of Issue
**File:** `/core/logic_postgresql.py`  
**Function:** `get_daily_activity()` (lines 382-390)

### The Problem
The logic for determining "staying" guests was including guests who checked in on the same day:

```python
# BEFORE FIX (problematic logic)
staying = df[
    (df_checkin.dt.date <= target_date) &  # <= includes check-in day
    (df_checkout.dt.date > target_date) &
    (df['Tình trạng'] == 'OK')
]
```

This caused guests to appear in BOTH:
1. `arrivals` list (guests checking in today)
2. `staying` list (guests staying tonight)

### Template Impact
In `/templates/calendar_details.html` line 33:
```html
{% set all_bookings = check_in + staying_over + check_out %}
```

And line 812 in calendar_details route:
```python
'guest_count': len(check_in) + len(check_out) + len(staying_over)
```

This resulted in guests checking in being counted twice in the total.

## Solution Implemented

### Code Fix
**File:** `/core/logic_postgresql.py` (lines 387-388)

```python
# AFTER FIX (corrected logic)
staying = df[
    (df_checkin.dt.date < target_date) &   # CHANGED: < excludes check-in day
    (df_checkout.dt.date > target_date) &
    (df['Tình trạng'] == 'OK')
]
```

### Logic Explanation
- **Check-in guests:** Only appear in `arrivals` list
- **Staying guests:** Only guests who checked in on PREVIOUS days
- **Check-out guests:** Only appear in `departures` list
- **No double counting:** Each guest appears in exactly one category per day

## Test Scenarios

### Scenario Example (Date: 2025-06-26)
- **Guest A:** Check-in 2025-06-26, Check-out 2025-06-28
  - **Before fix:** Appears in both arrivals AND staying (double count)
  - **After fix:** Appears ONLY in arrivals ✅
- **Guest B:** Check-in 2025-06-25, Check-out 2025-06-27  
  - **Before fix:** Appears ONLY in staying ✅
  - **After fix:** Appears ONLY in staying ✅
- **Guest C:** Check-in 2025-06-24, Check-out 2025-06-26
  - **Before fix:** Appears ONLY in departures ✅
  - **After fix:** Appears ONLY in departures ✅

### Expected Results After Fix
- **Arrivals:** 1 guest (Guest A)
- **Staying:** 1 guest (Guest B)  
- **Departures:** 1 guest (Guest C)
- **Total:** 3 guests (no double counting)

## Files Modified

1. **`/core/logic_postgresql.py`**
   - Modified `get_daily_activity()` function
   - Changed condition from `<=` to `<` for staying guests
   - Added explanatory comments

## Verification Steps

1. **Calendar Details Page:** Check that guest counts match actual unique guests
2. **Summary Totals:** Verify "Tổng khách" shows correct count (not doubled)
3. **Commission Overview:** Confirm percentage calculations are accurate
4. **Individual Lists:** Ensure guests appear in only one category per day

## Impact on Other Functions

- **Revenue Calculations:** Unaffected (uses separate `active_on_date` logic)
- **Dashboard Routes:** Unaffected (`get_daily_revenue_by_stay` uses correct logic)
- **Calendar View:** Unaffected (uses different calculation methods)

## Files NOT Affected

- `/core/dashboard_routes.py` - Uses correct per-night distribution logic
- `/templates/calendar.html` - Uses different revenue calculation
- Revenue calculation functions - Use `active_on_date` logic correctly

## Status: ✅ FIXED

The double-counting issue has been resolved. Guests checking in on a specific date will now appear only in the arrivals list and will not be duplicated in the staying list.