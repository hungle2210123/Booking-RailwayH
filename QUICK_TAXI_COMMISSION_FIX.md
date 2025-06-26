# 🚕💰 Quick Taxi & Commission Fix Tool

## 🎯 **IMMEDIATE SOLUTION**

Since the frontend is broken, use this **direct PostgreSQL update tool** to manually save taxi and commission amounts.

## 🚀 **How to Use**

### **Step 1: Run the Tool**
```bash
cd /mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized
python manual_taxi_commission_update.py
```

### **Step 2: Interactive Menu**
```
📋 Available commands:
1. show - Show all current bookings
2. update - Update taxi/commission for a booking  
3. verify - Verify a booking's current values
4. exit - Exit the tool
```

## 🧪 **Example Usage**

### **Show Current Bookings**
```
Enter command (1-4): 1

📋 CURRENT BOOKINGS:
================================================================================
ID              Guest                Room       Commission    Taxi       Collector      
--------------------------------------------------------------------------------
FLASK_TEST_001  Flask Test User      500,000        50,000       0       LOC LE         
DEMO001         Nguyễn Văn A         500,000        50,000       0       Admin          
```

### **Update Taxi & Commission**
```
Enter command (1-4): 2

Enter booking ID to update: FLASK_TEST_001

Updating FLASK_TEST_001:
Enter taxi amount (or press Enter to skip): 200000
Enter commission amount (or press Enter to skip): 75000
Enter notes (or press Enter to skip): Manual update - taxi and commission

🔍 CONFIRM UPDATE for FLASK_TEST_001:
   - Set taxi to: 200,000đ
   - Set commission to: 75,000đ
   - Set notes to: Manual update - taxi and commission

Proceed with update? (y/n): y

🔧 Executing update for FLASK_TEST_001:
   - Taxi amount: 200,000đ
   - Commission: 75,000đ
   - Notes: Manual update - taxi and commission

✅ Successfully updated FLASK_TEST_001

✅ VERIFICATION for FLASK_TEST_001:
   - Commission: 75,000đ
   - Taxi amount: 200,000đ
   - Notes: Manual update - taxi and commission
   - Updated: 2025-06-25 02:15:23
```

## 🔍 **Verify in Management Table**

After updating with the tool:

1. **Go to http://localhost:5000/bookings**
2. **Find your booking** (e.g., FLASK_TEST_001)
3. **Check the columns:**
   - **🚕 Taxi:** Should show `Badge: 200,000đ`
   - **💰 Commission:** Should show `75,000đ`

## 🎯 **Quick Commands**

### **Show All Bookings**
```bash
python manual_taxi_commission_update.py show
```

### **Update FLASK_TEST_001 with Taxi**
```python
# In interactive mode:
# 1. Run tool
# 2. Type: 2 (update)
# 3. Enter: FLASK_TEST_001
# 4. Enter taxi: 200000
# 5. Enter commission: 75000
# 6. Confirm: y
```

## 💾 **Database Verification**

The tool directly updates PostgreSQL:
```sql
UPDATE bookings 
SET taxi_amount = 200000, 
    commission = 75000, 
    booking_notes = 'Manual update - taxi and commission',
    updated_at = CURRENT_TIMESTAMP
WHERE booking_id = 'FLASK_TEST_001';
```

## ✅ **Expected Results**

After using the tool:

1. **✅ Database Updated** - Taxi and commission saved to PostgreSQL
2. **✅ Management Table Shows Data** - Bookings page displays correct amounts
3. **✅ Backend Logs Accurate** - Server shows updated values
4. **✅ Reports Include Data** - All analytics include taxi/commission

## 🔧 **Troubleshooting**

### **If Tool Doesn't Work**
```bash
# Check environment
ls .env
cat .env | grep DATABASE_URL

# Test database connection
python test_postgresql_connection.py
```

### **If Updates Don't Show in Table**
```bash
# Force refresh the bookings page
Ctrl + F5

# Check database directly
python debug_crud_test.py
```

---

**This tool bypasses the broken frontend completely and directly updates PostgreSQL!** 🎉

Use this while we fix the frontend taxi detection issue.