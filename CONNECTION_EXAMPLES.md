# Database Connection Examples

## 🔗 Connection String Examples

### **Local PostgreSQL**
```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/hotel_booking
```

### **Cloud PostgreSQL Services**

**Koyeb PostgreSQL:**
```env
DATABASE_URL=postgresql://koyeb-adm:npg_...@ep-little-haze-a2133rvc.eu-central-1.pg.koyeb.app:5432/koyebdb
```

**Railway PostgreSQL:**
```env
DATABASE_URL=postgresql://postgres:pass@containers-us-west-1.railway.app:7432/railway
```

**Heroku PostgreSQL:**
```env
DATABASE_URL=postgresql://user:pass@ec2-host.compute-1.amazonaws.com:5432/dbname
```

**AWS RDS PostgreSQL:**
```env
DATABASE_URL=postgresql://username:password@mydb.123456789012.us-east-1.rds.amazonaws.com:5432/hotel_booking
```

**Google Cloud SQL:**
```env
DATABASE_URL=postgresql://postgres:password@34.123.45.67:5432/hotel_booking
```

## 🛠️ pgAdmin 4 Connection Settings

### **Local Connection**
```
Host: localhost
Port: 5432
Database: hotel_booking
Username: postgres
Password: [your password]
```

### **Cloud Connection**
```
Host: [your cloud host]
Port: [your port, usually 5432]
Database: [your database name]
Username: [your username]
Password: [your password]
SSL Mode: Require (for cloud)
```

## 🧪 Testing Your Connection

### **Method 1: Using our test script**
```bash
python test_postgresql_connection.py
```

### **Method 2: Using psql command line**
```bash
psql "postgresql://postgres:password@localhost:5432/hotel_booking"
```

### **Method 3: Using Python directly**
```python
import psycopg2
conn = psycopg2.connect("postgresql://postgres:password@localhost:5432/hotel_booking")
print("Connection successful!")
conn.close()
```

## 🔍 Finding Your Connection Details

### **Default PostgreSQL Installation**
- Host: `localhost`
- Port: `5432`
- Username: `postgres`
- Password: [What you set during installation]
- Database: [Create `hotel_booking`]

### **In pgAdmin 4**
1. Right-click your server
2. Properties → Connection tab
3. Copy the connection details

### **Environment Variables**
Common PostgreSQL environment variables:
```bash
PGHOST=localhost
PGPORT=5432
PGDATABASE=hotel_booking
PGUSER=postgres
PGPASSWORD=your_password
```

## ⚡ Quick Connection Test

Run this in pgAdmin Query Tool:
```sql
SELECT version();
SELECT current_database();
SELECT current_user;
```

Should return:
- PostgreSQL version information
- Current database name
- Current username