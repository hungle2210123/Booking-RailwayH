# pgAdmin 4 Connection Fix Guide

## 🚨 Error: "Host name must be valid hostname or IPv4 or IPv6 address"

This error occurs when pgAdmin 4 doesn't recognize your hostname format. Here are the solutions:

## 🔧 Solution 1: Use Correct Local Connection

### **For Local PostgreSQL (Most Common)**

In pgAdmin 4, when creating server connection:

**Connection Tab:**
```
Host name/address: localhost
Port: 5432
Maintenance database: postgres
Username: postgres
Password: [your PostgreSQL password]
```

**Alternative hosts to try:**
- `localhost`
- `127.0.0.1` (IPv4 loopback)
- `::1` (IPv6 loopback - if IPv6 enabled)

## 🔧 Solution 2: Check PostgreSQL Service

### **Windows:**
1. **Check if PostgreSQL is running:**
   ```cmd
   # Open Command Prompt as Administrator
   net start
   ```
   Look for PostgreSQL service (like `postgresql-x64-14`)

2. **Start PostgreSQL if not running:**
   ```cmd
   net start postgresql-x64-14
   ```
   (Replace with your PostgreSQL version)

3. **Or use Services:**
   - Press `Win + R`, type `services.msc`
   - Find PostgreSQL service
   - Right-click → Start

### **Mac:**
```bash
# Check if running
brew services list | grep postgresql

# Start if not running
brew services start postgresql
```

### **Linux:**
```bash
# Check status
sudo systemctl status postgresql

# Start if not running
sudo systemctl start postgresql
```

## 🔧 Solution 3: Find Correct Connection Details

### **Method 1: Check PostgreSQL Configuration**

**Windows:** Find `postgresql.conf` file (usually in):
```
C:\Program Files\PostgreSQL\[version]\data\postgresql.conf
```

**Mac/Linux:**
```bash
sudo find / -name postgresql.conf 2>/dev/null
```

Look for these lines:
```
listen_addresses = 'localhost'
port = 5432
```

### **Method 2: Check Running PostgreSQL**

**Windows:**
```cmd
netstat -an | findstr :5432
```

**Mac/Linux:**
```bash
netstat -an | grep :5432
```

Should show: `127.0.0.1:5432` or `0.0.0.0:5432`

## 🔧 Solution 4: Step-by-Step pgAdmin Connection

### **1. Open pgAdmin 4**
- Windows: Start Menu → pgAdmin 4
- Make sure it fully loads (may take a minute)

### **2. Register New Server**
- Right-click "Servers" in left panel
- Select "Register" → "Server"

### **3. General Tab**
```
Name: Local PostgreSQL
Server group: Servers
```

### **4. Connection Tab - Try These Options:**

**Option A (Recommended):**
```
Host name/address: localhost
Port: 5432
Maintenance database: postgres
Username: postgres
Password: [your password]
Save password: ✓
```

**Option B (If Option A fails):**
```
Host name/address: 127.0.0.1
Port: 5432
Maintenance database: postgres
Username: postgres
Password: [your password]
Save password: ✓
```

**Option C (IPv6):**
```
Host name/address: ::1
Port: 5432
Maintenance database: postgres
Username: postgres
Password: [your password]
Save password: ✓
```

### **5. Advanced Tab (Optional)**
```
DB restriction: postgres, hotel_booking
```

## 🔧 Solution 5: Alternative Connection Methods

### **Method 1: Use Default PostgreSQL User**

If you forgot the postgres password:

**Windows:**
1. Open Command Prompt as Administrator
2. Switch to postgres user:
   ```cmd
   runas /user:postgres cmd
   ```
3. Connect without password:
   ```cmd
   psql -U postgres
   ```

**Mac/Linux:**
```bash
sudo -u postgres psql
```

### **Method 2: Reset PostgreSQL Password**

**Windows:**
1. Stop PostgreSQL service
2. Edit `pg_hba.conf` file
3. Change authentication method to `trust`
4. Restart service
5. Connect and change password:
   ```sql
   ALTER USER postgres PASSWORD 'newpassword';
   ```

## 🔧 Solution 6: Cloud Database Connection

### **If Using Cloud PostgreSQL:**

**Koyeb Example:**
```
Host name/address: ep-little-haze-a2133rvc.eu-central-1.pg.koyeb.app
Port: 5432
Maintenance database: koyebdb
Username: koyeb-adm
Password: [your koyeb password]
SSL mode: Require
```

**Railway Example:**
```
Host name/address: containers-us-west-1.railway.app
Port: 7432
Maintenance database: railway
Username: postgres
Password: [your railway password]
SSL mode: Require
```

## 🧪 Test Your Connection

### **1. Command Line Test:**
```bash
# Test local connection
psql -h localhost -p 5432 -U postgres -d postgres

# Test with IP
psql -h 127.0.0.1 -p 5432 -U postgres -d postgres
```

### **2. Python Test:**
```python
import psycopg2

# Test different hosts
hosts = ['localhost', '127.0.0.1', '::1']

for host in hosts:
    try:
        conn = psycopg2.connect(
            host=host,
            port=5432,
            database='postgres',
            user='postgres',
            password='your_password'
        )
        print(f"✅ Connection successful with host: {host}")
        conn.close()
        break
    except Exception as e:
        print(f"❌ Failed with host {host}: {e}")
```

### **3. Use Our Test Script:**
```bash
python test_postgresql_connection.py
```

## 🔍 Common Issues & Solutions

### **Issue 1: "Connection refused"**
**Solution:** PostgreSQL service not running
```bash
# Start PostgreSQL service
# Windows: net start postgresql-x64-14
# Mac: brew services start postgresql
# Linux: sudo systemctl start postgresql
```

### **Issue 2: "Password authentication failed"**
**Solution:** Wrong password or user
- Try default user: `postgres`
- Reset password if needed
- Check if user exists

### **Issue 3: "Database does not exist"**
**Solution:** Use `postgres` as maintenance database first
- Connect to default `postgres` database
- Then create `hotel_booking` database

### **Issue 4: "Port 5432 not listening"**
**Solution:** PostgreSQL not configured to listen
- Check `postgresql.conf`
- Ensure `listen_addresses = 'localhost'`
- Restart PostgreSQL service

## 🎯 Working Connection Examples

### **Local Development:**
```
✅ localhost:5432
✅ 127.0.0.1:5432
✅ [computer-name]:5432
```

### **Cloud Services:**
```
✅ ep-xxx.eu-central-1.pg.koyeb.app:5432
✅ containers-us-west-1.railway.app:7432
✅ ec2-xxx.compute-1.amazonaws.com:5432
```

## 📞 Quick Fix Checklist

1. ✅ **PostgreSQL service running?**
2. ✅ **Using `localhost` or `127.0.0.1`?**
3. ✅ **Port 5432 correct?**
4. ✅ **Username `postgres` correct?**
5. ✅ **Password correct?**
6. ✅ **Maintenance database is `postgres`?**

After fixing the connection, you can proceed with creating the `hotel_booking` database and running the schema script!