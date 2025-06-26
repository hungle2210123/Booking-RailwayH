# Railway Setup Guide for Hotel Booking System

## 🚂 Railway PostgreSQL Configuration

### Step 1: Create PostgreSQL Database
1. Go to Railway dashboard: https://railway.app/dashboard
2. Click "New Project" → "Database" → "PostgreSQL"
3. Wait for PostgreSQL to initialize

### Step 2: Connect Web Service to Database
1. Go to your Web Service → Variables tab
2. Add this exact variable:
   ```
   Name: DATABASE_URL
   Value: ${{Postgres.DATABASE_URL}}
   ```
3. Save variables (Railway will automatically redeploy)

### Step 3: Verify Connection
Your app logs should show:
```
✅ Database configured: postgresql://...
```

If you still see SQLite fallback, check:
- Database is created and running
- Variable name is exactly `DATABASE_URL`
- Value is exactly `${{Postgres.DATABASE_URL}}` (with double curly braces)

### Step 4: Import Data
Once PostgreSQL is connected, the app will automatically:
1. Create database tables
2. Import data from csvtest.xlsx
3. Show dashboard with all bookings

## 🔧 Troubleshooting

### Common Issues:
1. **Still using SQLite**: Environment variable not set correctly
2. **Database connection error**: PostgreSQL service not running
3. **Table errors**: Database needs initialization (restart app)

### Check Database Status:
- Railway dashboard → PostgreSQL service → Logs
- Web service logs should show database connection success

## 📱 App URLs:
- **Main App**: https://web-production-8f671.up.railway.app/
- **Health Check**: https://web-production-8f671.up.railway.app/health
- **Dashboard**: https://web-production-8f671.up.railway.app/dashboard