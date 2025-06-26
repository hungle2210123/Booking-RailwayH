#!/usr/bin/env python3
"""
Test Flask Application Routes and Features
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# Load environment variables
load_dotenv(BASE_DIR / ".env")

def test_flask_app_startup():
    """Test Flask application startup"""
    print("=== Flask Application Startup Test ===")
    
    try:
        import app_postgresql
        from flask import Flask
        
        # Create a test client
        app = app_postgresql.app
        app.config['TESTING'] = True
        client = app.test_client()
        
        print("Flask app created successfully")
        return True, client
        
    except Exception as e:
        print(f"ERROR: Flask app startup failed - {str(e)}")
        return False, None

def test_dashboard_route(client):
    """Test dashboard route"""
    print("\n=== Dashboard Route Test ===")
    
    try:
        with client.application.app_context():
            response = client.get('/')
            
            print(f"Dashboard response status: {response.status_code}")
            
            if response.status_code == 200:
                print("Dashboard loaded successfully")
                return True
            else:
                print(f"Dashboard failed with status: {response.status_code}")
                return False
        
    except Exception as e:
        print(f"ERROR: Dashboard test failed - {str(e)}")
        return False

def test_bookings_route(client):
    """Test bookings route"""
    print("\n=== Bookings Route Test ===")
    
    try:
        with client.application.app_context():
            response = client.get('/bookings')
            
            print(f"Bookings response status: {response.status_code}")
            
            if response.status_code == 200:
                print("Bookings page loaded successfully")
                return True
            else:
                print(f"Bookings failed with status: {response.status_code}")
                return False
        
    except Exception as e:
        print(f"ERROR: Bookings test failed - {str(e)}")
        return False

def test_calendar_route(client):
    """Test calendar route"""
    print("\n=== Calendar Route Test ===")
    
    try:
        with client.application.app_context():
            response = client.get('/calendar/')
            
            print(f"Calendar response status: {response.status_code}")
            
            if response.status_code == 200:
                print("Calendar loaded successfully")
                return True
            else:
                print(f"Calendar failed with status: {response.status_code}")
                return False
        
    except Exception as e:
        print(f"ERROR: Calendar test failed - {str(e)}")
        return False

def test_api_endpoints(client):
    """Test API endpoints"""
    print("\n=== API Endpoints Test ===")
    
    try:
        with client.application.app_context():
            # Test database health endpoint
            response = client.get('/api/database/health')
            print(f"Database health status: {response.status_code}")
            
            if response.status_code == 200:
                health_data = json.loads(response.data)
                print(f"Database status: {health_data.get('status', 'unknown')}")
            
            # Test database connection endpoint
            response = client.get('/api/database/test_connection')
            print(f"Database connection status: {response.status_code}")
            
            # Test expenses API
            response = client.get('/api/expenses')
            print(f"Expenses API status: {response.status_code}")
            
            return response.status_code == 200
        
    except Exception as e:
        print(f"ERROR: API endpoints test failed - {str(e)}")
        return False

def test_booking_operations(client):
    """Test booking operations through routes"""
    print("\n=== Booking Operations Test ===")
    
    try:
        with client.application.app_context():
            # Test add booking page
            response = client.get('/bookings/add')
            print(f"Add booking page status: {response.status_code}")
            
            if response.status_code != 200:
                print("Add booking page failed")
                return False
            
            # Test adding a booking via POST
            import time
            today = date.today()
            unique_id = f'FLASK_TEST_{int(time.time())}'
            booking_data = {
                'booking_id': unique_id,
                'guest_name': 'Flask Test User',
                'email': 'flask_test@example.com',
                'phone': '+1234567890',
                'checkin_date': today.strftime('%Y-%m-%d'),
                'checkout_date': (today + timedelta(days=2)).strftime('%Y-%m-%d'),
                'room_amount': '500000',
                'commission': '50000',
                'taxi_amount': '0',
                'collector': 'Test Collector',
                'notes': 'Flask test booking'
            }
            
            response = client.post('/bookings/add', data=booking_data, follow_redirects=True)
            print(f"Add booking POST status: {response.status_code}")
            
            if response.status_code == 200:
                print("Booking added successfully")
                return True
            else:
                print("Booking addition failed")
                return False
        
    except Exception as e:
        print(f"ERROR: Booking operations test failed - {str(e)}")
        return False

def main():
    """Run all Flask app tests"""
    print("Starting Flask Application Test Suite\n")
    
    # Test app startup
    success, client = test_flask_app_startup()
    if not success:
        print("Flask app startup failed - cannot continue tests")
        return False
    
    tests = [
        ("Dashboard Route", lambda: test_dashboard_route(client)),
        ("Bookings Route", lambda: test_bookings_route(client)),
        ("Calendar Route", lambda: test_calendar_route(client)),
        ("API Endpoints", lambda: test_api_endpoints(client)),
        ("Booking Operations", lambda: test_booking_operations(client)),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        success = test_func()
        results.append((test_name, success))
    
    # Summary
    print(f"\n{'='*60}")
    print("FLASK APPLICATION TEST SUMMARY")
    print('='*60)
    
    passed = 0
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        print(f"{test_name}: {status}")
        if success:
            passed += 1
    
    print(f"\nPassed: {passed}/{len(results)} tests")
    
    if passed == len(results):
        print("SUCCESS: All Flask application tests passed!")
        return True
    else:
        print("ERROR: Some Flask application tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)