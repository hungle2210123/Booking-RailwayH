#!/usr/bin/env python3
"""
Hotel Booking System - Production Startup Script
Ensures proper PostgreSQL initialization and database setup
"""
import os
import sys
from pathlib import Path

def setup_environment():
    """Setup environment variables for production"""
    # Set required environment variables if not present
    if not os.getenv('USE_POSTGRESQL'):
        os.environ['USE_POSTGRESQL'] = 'true'
    
    if not os.getenv('FLASK_ENV'):
        os.environ['FLASK_ENV'] = 'production'
    
    if not os.getenv('PORT'):
        os.environ['PORT'] = '8080'
    
    print(f"🔧 Environment Setup Complete")
    print(f"   USE_POSTGRESQL: {os.getenv('USE_POSTGRESQL')}")
    print(f"   FLASK_ENV: {os.getenv('FLASK_ENV')}")
    print(f"   PORT: {os.getenv('PORT')}")

def verify_database():
    """Verify database connection"""
    try:
        from app_postgresql import app, db
        with app.app_context():
            # Test database connection
            db.engine.execute('SELECT 1')
        print("✅ Database connection verified")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("💡 Make sure DATABASE_URL is set correctly in environment")
        return False

def create_tables():
    """Create database tables if they don't exist"""
    try:
        from app_postgresql import app, db
        with app.app_context():
            db.create_all()
        print("✅ Database tables ensured")
        return True
    except Exception as e:
        print(f"❌ Table creation failed: {e}")
        return False

def main():
    """Main startup function"""
    print("🚀 Hotel Booking System - PostgreSQL Edition")
    print("=" * 50)
    
    # Setup environment
    setup_environment()
    
    # Verify database
    if not verify_database():
        print("❌ Startup failed - database connection error")
        sys.exit(1)
    
    # Create tables
    if not create_tables():
        print("❌ Startup failed - table creation error")
        sys.exit(1)
    
    print("✅ Startup complete - launching Flask application...")
    
    # Import and run the Flask app
    from app_postgresql import app
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main()