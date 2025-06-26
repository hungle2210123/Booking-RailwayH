# Application Configuration Guide - Step by Step

## 🎯 Configure Your Hotel Booking Application

Now that your PostgreSQL database is set up successfully, let's configure the application to connect to it.

## 📋 **Step 1: Setup Environment File**

### **1.1 Copy the Template**

**Windows Command Prompt:**
```cmd
copy .env_postgresql.template .env
```

**Windows PowerShell:**
```powershell
Copy-Item .env_postgresql.template .env
```

**Mac/Linux:**
```bash
cp .env_postgresql.template .env
```

**Manual Method:**
- Right-click `.env_postgresql.template`
- Select "Copy"
- Right-click in same folder → "Paste"
- Rename the copy to `.env` (remove the .template part)

### **1.2 Verify File Created**
You should now have a new file called `.env` in your project folder.

## 📝 **Step 2: Edit Environment Configuration**

### **2.1 Open .env File**
Open the `.env` file in any text editor:
- **Notepad** (Windows)
- **TextEdit** (Mac) 
- **VS Code, Sublime Text, etc.**

### **2.2 Configure Database Connection**

**Find this line:**
```env
DATABASE_URL=postgresql://username:password@host:port/database
```

**Replace with YOUR pgAdmin connection details:**
```env
DATABASE_URL=postgresql://postgres:your_actual_password@localhost:5432/hotel_booking
```

**Examples:**

If your PostgreSQL password is `mypassword123`:
```env
DATABASE_URL=postgresql://postgres:mypassword123@localhost:5432/hotel_booking
```

If your PostgreSQL password is `admin`:
```env
DATABASE_URL=postgresql://postgres:admin@localhost:5432/hotel_booking
```

### **2.3 Configure Flask Secret Key**

**Find this line:**
```env
FLASK_SECRET_KEY=your_secret_key_here
```

**Replace with a random secret key:**
```env
FLASK_SECRET_KEY=hotel_booking_secret_2024_change_this_in_production
```

**Or generate a secure one:**
```python
# Run this in Python to generate a secure key
import secrets
print(secrets.token_hex(32))
```

### **2.4 Optional: Configure Gemini AI (for image processing)**

**Find this line:**
```env
GOOGLE_API_KEY=your_gemini_api_key
```

**If you have a Gemini API key:**
```env
GOOGLE_API_KEY=AIzaSyD1234567890abcdefghijk
```

**If you don't have one (skip for now):**
```env
# GOOGLE_API_KEY=your_gemini_api_key
```

### **2.5 Complete .env File Example**

Your final `.env` file should look like this:
```env
# Flask Configuration
FLASK_SECRET_KEY=hotel_booking_secret_2024_change_this_in_production

# PostgreSQL Database (REQUIRED)
DATABASE_URL=postgresql://postgres:mypassword123@localhost:5432/hotel_booking

# Google AI API (Optional - only for Gemini image processing)
GOOGLE_API_KEY=AIzaSyD1234567890abcdefghijk

# Performance Settings
ENABLE_PERFORMANCE_LOGGING=true

# Production Settings
ENV=production
DEBUG=false
```

## 🔧 **Step 3: Install Python Dependencies**

### **3.1 Open Command Prompt/Terminal**
Navigate to your project folder:
```cmd
cd C:\Users\T14\Desktop\hotel_flask_app\hotel_flask_app_optimized
```

### **3.2 Install Dependencies**
```bash
pip install -r requirements_postgresql.txt
```

**Expected output:**
```
Collecting flask==2.3.3
Downloading flask-2.3.3...
Installing collected packages: flask, pandas, psycopg2-binary...
Successfully installed flask-2.3.3 pandas-2.0.3 psycopg2-binary-2.9.7 ...
```

**If you get permission errors on Windows:**
```cmd
pip install --user -r requirements_postgresql.txt
```

**If you get errors on Mac/Linux:**
```bash
pip3 install -r requirements_postgresql.txt
```

## 🧪 **Step 4: Test Application Connection**

### **4.1 Run Connection Test**
```bash
python test_postgresql_connection.py
```

### **4.2 Expected Successful Output**
```
🧪 PostgreSQL Database Test Suite
==================================================
🗄️ Database URL: localhost:5432/hotel_booking

🔬 Running Connection Test...
🔗 Testing PostgreSQL Connection...
✅ PostgreSQL connection successful!

🔬 Running CRUD Operations...
📝 Testing CRUD Operations...
📖 Testing READ operation...
✅ Found 3 existing bookings
➕ Testing CREATE operation...
✅ Created test booking: TEST_20241224_143052
✏️ Testing UPDATE operation...
✅ Updated booking: TEST_20241224_143052
🗑️ Testing DELETE operation...
✅ Deleted test booking: TEST_20241224_143052
✅ All CRUD operations successful!

🔬 Running Health Check...
🏥 Testing Health Check...
📊 Health Status: healthy
🗄️ Backend: postgresql
📈 Statistics:
   - Bookings: 3
   - Guests: 3
   - Expenses: 0
✅ Database health check passed!

🔬 Running Performance Test...
⚡ Testing Performance...
🚀 Query Performance:
   - Retrieved 3 bookings
   - Time: 45.2ms
✅ Performance test passed!

==================================================
📋 Test Results Summary:
   Connection Test: ✅ PASS
   CRUD Operations: ✅ PASS
   Health Check: ✅ PASS
   Performance Test: ✅ PASS

🎯 Overall: 4/4 tests passed
🎉 All tests passed! PostgreSQL setup is working correctly.

📖 Next steps:
   1. Connect with pgAdmin 4 or DBeaver
   2. Run: python app_postgresql.py
   3. Visit: http://localhost:5000
```

### **4.3 If Tests Fail**

**Common Error 1: Connection refused**
```
❌ Connection error: connection to server at "localhost" (127.0.0.1), port 5432 failed
```
**Solution:** PostgreSQL service not running
```cmd
# Windows
net start postgresql-x64-14

# Mac
brew services start postgresql

# Linux
sudo systemctl start postgresql
```

**Common Error 2: Authentication failed**
```
❌ Connection error: FATAL: password authentication failed for user "postgres"
```
**Solution:** Wrong password in .env file
- Check your PostgreSQL password
- Update DATABASE_URL in .env file

**Common Error 3: Database does not exist**
```
❌ Connection error: FATAL: database "hotel_booking" does not exist
```
**Solution:** Create database in pgAdmin first
- Open pgAdmin 4
- Right-click server → Create → Database → Name: hotel_booking

## 🚀 **Step 5: Run Your Hotel Booking Application**

### **5.1 Start the Application**
```bash
python app_postgresql.py
```

### **5.2 Expected Startup Output**
```
✅ PostgreSQL Database Service initialized
✅ Database tables created/verified
✅ PostgreSQL Database Service initialized successfully
 * Running on all addresses (0.0.0.0)
 * Running on http://127.0.0.1:5000
 * Running on http://[::1]:5000
Press CTRL+C to quit
```

### **5.3 Access Web Interface**
Open your web browser and go to:
```
http://localhost:5000
```

**You should see:**
- ✅ Hotel booking dashboard
- ✅ Sample data loaded (3 bookings)
- ✅ Revenue statistics
- ✅ All features working

## 🎯 **Step 6: Verify Everything Works**

### **6.1 Test Dashboard**
- Navigate to http://localhost:5000
- Should show dashboard with sample bookings
- Revenue totals should display

### **6.2 Test Bookings Page**
- Click "Bookings" in navigation
- Should show 3 sample bookings:
  - DEMO001 - Nguyễn Văn A
  - DEMO002 - Trần Thị B  
  - DEMO003 - John Smith

### **6.3 Test Database Health**
Visit: http://localhost:5000/api/database/health

Should return:
```json
{
  "status": "healthy",
  "backend": "postgresql",
  "connection": "success",
  "stats": {
    "bookings": 3,
    "guests": 3,
    "expenses": 0
  }
}
```

## 🛠️ **Troubleshooting**

### **Issue 1: Import Error**
```
ModuleNotFoundError: No module named 'flask'
```
**Solution:**
```bash
pip install -r requirements_postgresql.txt
```

### **Issue 2: Environment File Not Found**
```
FileNotFoundError: .env file not found
```
**Solution:**
```bash
copy .env_postgresql.template .env
```

### **Issue 3: Database Connection Error**
**Check your .env file:**
- Correct password
- Correct database name (hotel_booking)
- PostgreSQL service running

### **Issue 4: Port Already in Use**
```
Address already in use: Port 5000
```
**Solution:**
- Stop other applications using port 5000
- Or change port: `python app_postgresql.py` will use PORT environment variable

## 🎉 **Success Checklist**

When everything is working correctly:

- ✅ `.env` file created and configured
- ✅ Dependencies installed successfully
- ✅ Connection test passes (4/4 tests)
- ✅ Application starts without errors
- ✅ Web interface loads at http://localhost:5000
- ✅ Sample data visible in dashboard
- ✅ All features functional
- ✅ **100% PostgreSQL, 0% Google Sheets**

## 📞 **Need Help?**

If you encounter issues:

1. **Run diagnostics:**
   ```bash
   python check_postgresql_status.py
   ```

2. **Check connection test:**
   ```bash
   python test_postgresql_connection.py
   ```

3. **Verify database in pgAdmin:**
   - Connect to your database
   - Verify hotel_booking database exists
   - Check that tables have data

4. **Check application logs for specific error messages**

Your hotel booking system is now running on **pure PostgreSQL** with **zero Google Sheets dependencies**! 🎊