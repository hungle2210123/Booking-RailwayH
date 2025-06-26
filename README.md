# 🏨 Hotel Booking Management System - PostgreSQL Edition

## 🎯 **Production-Ready Flask Application**
**100% PostgreSQL** | **Google Sheets Removed** | **AI-Powered** | **Commission Analytics**

---

## 🚀 **Quick Start**

### **1. Clone Repository**
```bash
git clone https://github.com/locle27/Booking-PostgreSQL.git
cd Booking-PostgreSQL
```

### **2. Install Dependencies**
```bash
pip install -r requirements_production.txt
```

### **3. Configure Environment**
```bash
cp .env.production .env
# Edit .env with your PostgreSQL credentials
```

### **4. Setup Database**
```bash
# Create PostgreSQL database
# Update DATABASE_URL in .env
python app_postgresql.py  # Creates tables automatically
```

### **5. Import Templates**
```bash
# Visit: http://localhost:8080/api/templates/import_json
# Or use the AI Assistant interface
```

---

## ⚙️ **Environment Configuration**

### **Required Variables**
```env
# Flask Settings
FLASK_ENV="production"
FLASK_SECRET_KEY="your_unique_secret_key"
PORT="8080"

# Database (REQUIRED)
DATABASE_URL="postgresql://username:password@host:port/database"
USE_POSTGRESQL="true"

# AI Integration
GOOGLE_API_KEY="your_gemini_api_key"
```

### **Removed Variables (No Longer Needed)**
- ❌ `DEFAULT_SHEET_ID` - Google Sheets removed
- ❌ `GCP_CREDENTIALS_JSON` - Google Sheets removed  
- ❌ `MESSAGE_TEMPLATE_WORKSHEET` - Templates in PostgreSQL
- ❌ `WORKSHEET_NAME` - Bookings in PostgreSQL

---

## 🏗️ **Architecture**

### **Core Components**
```
hotel_flask_app_optimized/
├── app_postgresql.py          # Main Flask application (62 routes)
├── core/
│   ├── models.py             # SQLAlchemy database models
│   ├── logic_postgresql.py   # Business logic layer
│   ├── database_service_postgresql.py  # Database service
│   └── dashboard_routes.py   # Analytics & dashboard
├── templates/                # Jinja2 HTML templates
├── static/                   # CSS, JS, images
└── config/                   # Configuration files
```

### **Database Schema**
- **bookings** - Core booking data with commission tracking
- **guests** - Customer information
- **message_templates** - AI Assistant templates (96+ templates)
- **expenses** - Financial tracking
- **quick_notes** - Task management
- **arrival_times** - Guest arrival coordination

---

## 🎯 **Key Features**

### **✅ Advanced Commission Analytics**
- Real-time commission tracking with visual indicators
- Multi-level prioritization (Red: >150k, Yellow: normal, Green: no commission)
- Per-night revenue distribution for accurate calendar view
- Smart duplicate detection and prevention

### **✅ Payment Collection System**
- Actual vs. booking amount tracking
- Collected amount validation with proper collectors
- Visual payment status indicators (Green: paid, Red: pending)
- Comprehensive payment breakdown in modals

### **✅ AI-Powered Features**
- Gemini AI integration for booking screenshot analysis
- Automated booking information extraction
- Intelligent duplicate detection
- 96+ categorized message templates

### **✅ Professional Dashboard**
- Real-time analytics with commission insights
- Revenue calendar with per-night pricing
- Guest categorization (checking in, staying, departing)
- Advanced filtering and search capabilities

---

## 🔧 **Deployment**

### **Local Development**
```bash
python app_postgresql.py
# Access: http://localhost:8080
```

### **Production Deployment (Koyeb/Heroku)**
```bash
# Set environment variables in your hosting platform
# Ensure PostgreSQL database is configured
# Deploy using requirements_production.txt
```

### **Database Migration**
```bash
# The app creates tables automatically on first run
# For existing data, use the import utilities in /core/
```

---

## 📊 **System Status**

### **✅ Completed Features**
- [x] 100% PostgreSQL migration (Google Sheets removed)
- [x] Advanced commission analytics system
- [x] Payment collection tracking
- [x] AI booking screenshot analysis
- [x] Per-night revenue distribution
- [x] Message template management (96+ templates)
- [x] Real-time dashboard analytics
- [x] Production-ready architecture

### **🎯 Recent Achievements**
- **Template Fix**: AI Assistant now displays proper template titles
- **Commission Analytics**: Multi-level prioritization with visual indicators
- **Payment Tracking**: Actual money collection vs. booking amounts
- **Revenue Calendar**: Accurate per-night pricing distribution
- **Database Optimization**: Pure PostgreSQL with optimized queries

---

## 🛠️ **Troubleshooting**

### **Common Issues**

**1. Database Connection Error**
```bash
# Check DATABASE_URL format
# Ensure PostgreSQL server is running
# Verify credentials and database exists
```

**2. Template Loading Issues**
```bash
# Import templates: POST /api/templates/import_json
# Check message_templates table in PostgreSQL
# Verify JSON file: config/message_templates.json
```

**3. Commission Analytics Not Showing**
```bash
# Check booking data has commission values
# Verify per-night calculation logic
# Refresh dashboard cache
```

---

## 📝 **API Endpoints**

### **Core Routes**
- `GET /` - Main dashboard
- `GET /bookings` - Booking management
- `GET /calendar` - Revenue calendar
- `GET /ai-assistant` - AI template interface

### **API Routes**
- `GET/POST /api/templates` - Template management
- `POST /api/collect_payment` - Payment collection
- `POST /api/add_booking` - Create booking
- `GET /api/dashboard_data` - Dashboard analytics

---

## 📞 **Support**

- **Repository**: https://github.com/locle27/Booking-PostgreSQL
- **Owner**: locle27
- **Branch**: main (clean PostgreSQL setup)
- **Documentation**: Complete technical docs in PROJECT_DOCUMENTATION.md

---

**🎉 Ready for production deployment with PostgreSQL database!**