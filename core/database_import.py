#!/usr/bin/env python3
"""
Database Import Module - Flask Application Context Aware
Ultra Think Optimization for PostgreSQL Database Operations
"""

import os
import sys
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from flask import Flask

def create_app_context():
    """
    Create Flask application context for database operations
    """
    # Add the project root to Python path
    sys.path.append('/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized')
    
    from dotenv import load_dotenv
    from pathlib import Path
    
    BASE_DIR = Path('/mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized')
    load_dotenv(BASE_DIR / ".env")
    
    app = Flask(__name__, template_folder=BASE_DIR / "templates", static_folder=BASE_DIR / "static")
    
    # Production configuration
    app.config['ENV'] = 'production'
    app.config['DEBUG'] = False
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")
    
    # PostgreSQL database configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize database with app
    from core.models import db
    db.init_app(app)
    
    return app

def save_customers_to_database(customers_data: List[Dict[str, Any]], app_context) -> Dict[str, Any]:
    """
    Save customers to PostgreSQL database within Flask context
    """
    print("\n👥 SAVING CUSTOMERS TO DATABASE")
    print("=" * 50)
    
    with app_context.app_context():
        from core.models import db, Guest
        
        results = {'imported': 0, 'updated': 0, 'errors': []}
        guest_mapping = {}  # Map guest names to IDs
        
        try:
            for customer in customers_data:
                try:
                    # Check if guest already exists by name
                    existing_guest = Guest.query.filter_by(full_name=customer['full_name']).first()
                    
                    if not existing_guest:
                        # Create new guest
                        new_guest = Guest(
                            full_name=customer['full_name'],
                            email=customer.get('email'),
                            phone=customer.get('phone'),
                            nationality=customer.get('nationality'),
                            passport_number=customer.get('passport_number')
                        )
                        db.session.add(new_guest)
                        db.session.flush()  # Get ID without committing
                        guest_mapping[customer['full_name']] = new_guest.guest_id
                        results['imported'] += 1
                        print(f"✅ New customer: {customer['full_name']} (ID: {new_guest.guest_id})")
                    else:
                        # Update existing guest if needed
                        if customer.get('email') and not existing_guest.email:
                            existing_guest.email = customer['email']
                        if customer.get('phone') and not existing_guest.phone:
                            existing_guest.phone = customer['phone']
                        if customer.get('nationality') and not existing_guest.nationality:
                            existing_guest.nationality = customer['nationality']
                        if customer.get('passport_number') and not existing_guest.passport_number:
                            existing_guest.passport_number = customer['passport_number']
                        
                        guest_mapping[customer['full_name']] = existing_guest.guest_id
                        results['updated'] += 1
                        print(f"📝 Updated customer: {customer['full_name']} (ID: {existing_guest.guest_id})")
                        
                except Exception as e:
                    error_msg = f"Customer {customer.get('full_name', 'Unknown')}: {str(e)}"
                    results['errors'].append(error_msg)
                    print(f"❌ {error_msg}")
            
            # Commit all customer changes
            db.session.commit()
            print(f"✅ Customers committed: {results['imported']} new, {results['updated']} updated")
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Customer batch error: {str(e)}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        return results, guest_mapping

def save_bookings_to_database(bookings_data: List[Dict[str, Any]], guest_mapping: Dict[str, int], app_context) -> Dict[str, Any]:
    """
    Save bookings to PostgreSQL database within Flask context
    """
    print("\n📋 SAVING BOOKINGS TO DATABASE")
    print("=" * 50)
    
    with app_context.app_context():
        from core.models import db, Booking
        
        results = {'imported': 0, 'updated': 0, 'errors': []}
        
        try:
            for booking in bookings_data:
                try:
                    guest_id = guest_mapping.get(booking['guest_name'])
                    if not guest_id:
                        error_msg = f"Booking {booking['booking_id']}: Guest '{booking['guest_name']}' not found"
                        results['errors'].append(error_msg)
                        print(f"❌ {error_msg}")
                        continue
                    
                    # Check if booking already exists
                    existing_booking = Booking.query.filter_by(booking_id=booking['booking_id']).first()
                    
                    if not existing_booking:
                        # Create new booking
                        new_booking = Booking(
                            booking_id=booking['booking_id'],
                            guest_id=guest_id,
                            checkin_date=booking['checkin_date'],
                            checkout_date=booking['checkout_date'],
                            room_amount=booking['room_amount'] or 0.0,
                            taxi_amount=booking['taxi_amount'] or 0.0,
                            commission=booking['commission'] or 0.0,
                            collected_amount=booking['collected_amount'] or 0.0,
                            collector=booking.get('collector'),
                            booking_status=booking.get('booking_status', 'confirmed'),
                            booking_notes=booking.get('booking_notes')
                        )
                        db.session.add(new_booking)
                        results['imported'] += 1
                        print(f"✅ New booking: {booking['booking_id']} - {booking['guest_name']}")
                    else:
                        # Update existing booking
                        existing_booking.guest_id = guest_id
                        existing_booking.checkin_date = booking['checkin_date']
                        existing_booking.checkout_date = booking['checkout_date']
                        existing_booking.room_amount = booking['room_amount'] or 0.0
                        existing_booking.taxi_amount = booking['taxi_amount'] or 0.0
                        existing_booking.commission = booking['commission'] or 0.0
                        existing_booking.collected_amount = booking['collected_amount'] or 0.0
                        existing_booking.collector = booking.get('collector')
                        existing_booking.booking_status = booking.get('booking_status', 'confirmed')
                        existing_booking.booking_notes = booking.get('booking_notes')
                        existing_booking.updated_at = datetime.now()
                        
                        results['updated'] += 1
                        print(f"📝 Updated booking: {booking['booking_id']} - {booking['guest_name']}")
                        
                except Exception as e:
                    error_msg = f"Booking {booking.get('booking_id', 'Unknown')}: {str(e)}"
                    results['errors'].append(error_msg)
                    print(f"❌ {error_msg}")
            
            # Commit all booking changes
            db.session.commit()
            print(f"✅ Bookings committed: {results['imported']} new, {results['updated']} updated")
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Booking batch error: {str(e)}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        return results

def save_templates_to_database(templates_data: List[Dict[str, Any]], app_context) -> Dict[str, Any]:
    """
    Save message templates to PostgreSQL database within Flask context
    """
    print("\n💬 SAVING MESSAGE TEMPLATES TO DATABASE")
    print("=" * 50)
    
    with app_context.app_context():
        from core.models import db, MessageTemplate
        
        results = {'imported': 0, 'updated': 0, 'errors': []}
        
        try:
            for template in templates_data:
                try:
                    # Clean template name to avoid duplicates
                    template_name = template['template_name']
                    if len(template_name) > 255:
                        template_name = template_name[:250] + "..."
                    
                    # Check if template already exists
                    existing_template = MessageTemplate.query.filter_by(template_name=template_name).first()
                    
                    if not existing_template:
                        # Create new template
                        new_template = MessageTemplate(
                            template_name=template_name,
                            category=template['category'][:100] if template['category'] else 'general',  # Limit category length
                            template_content=template['template_content']
                        )
                        db.session.add(new_template)
                        results['imported'] += 1
                        print(f"✅ New template: {template_name[:50]}...")
                    else:
                        # Update existing template
                        existing_template.template_content = template['template_content']
                        existing_template.category = template['category'][:100] if template['category'] else 'general'
                        existing_template.updated_at = datetime.now()
                        results['updated'] += 1
                        print(f"📝 Updated template: {template_name[:50]}...")
                        
                except Exception as e:
                    error_msg = f"Template {template.get('template_name', 'Unknown')[:30]}: {str(e)}"
                    results['errors'].append(error_msg)
                    print(f"❌ {error_msg}")
            
            # Commit all template changes
            db.session.commit()
            print(f"✅ Templates committed: {results['imported']} new, {results['updated']} updated")
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Template batch error: {str(e)}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        return results

def save_expenses_to_database(expenses_data: List[Dict[str, Any]], app_context) -> Dict[str, Any]:
    """
    Save expenses to PostgreSQL database within Flask context
    """
    print("\n💰 SAVING EXPENSES TO DATABASE")
    print("=" * 50)
    
    with app_context.app_context():
        from core.models import db, Expense
        
        results = {'imported': 0, 'skipped': 0, 'errors': []}
        
        try:
            for expense in expenses_data:
                try:
                    # Check for duplicate expenses (same description, amount, and date)
                    existing_expense = Expense.query.filter_by(
                        description=expense['description'],
                        amount=expense['amount'],
                        expense_date=expense['expense_date']
                    ).first()
                    
                    if not existing_expense:
                        # Create new expense
                        new_expense = Expense(
                            description=expense['description'],
                            amount=expense['amount'],
                            expense_date=expense['expense_date'],
                            category=expense['category'],
                            collector=expense['collector']
                        )
                        db.session.add(new_expense)
                        results['imported'] += 1
                        print(f"✅ New expense: {expense['description'][:30]}... - {expense['amount']:,.0f}đ")
                    else:
                        results['skipped'] += 1
                        print(f"⏭️ Skipped duplicate: {expense['description'][:30]}... - {expense['amount']:,.0f}đ")
                        
                except Exception as e:
                    error_msg = f"Expense {expense.get('description', 'Unknown')[:30]}: {str(e)}"
                    results['errors'].append(error_msg)
                    print(f"❌ {error_msg}")
            
            # Commit all expense changes
            db.session.commit()
            print(f"✅ Expenses committed: {results['imported']} new, {results['skipped']} skipped")
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Expense batch error: {str(e)}"
            results['errors'].append(error_msg)
            print(f"❌ {error_msg}")
        
        return results

def comprehensive_database_import(customers_data: Dict[str, List], templates_data: List[Dict], expenses_data: List[Dict]) -> Dict[str, Any]:
    """
    Comprehensive database import with proper Flask context management
    Ultra Think Optimization
    """
    print("\n🚀 COMPREHENSIVE DATABASE IMPORT - ULTRA OPTIMIZED")
    print("=" * 70)
    
    try:
        # Create Flask application context
        print("🔧 Creating Flask application context...")
        app = create_app_context()
        
        # Initialize final results
        final_results = {
            'customers': {'imported': 0, 'updated': 0, 'errors': []},
            'bookings': {'imported': 0, 'updated': 0, 'errors': []},
            'templates': {'imported': 0, 'updated': 0, 'errors': []},
            'expenses': {'imported': 0, 'skipped': 0, 'errors': []},
            'total_success': 0,
            'total_errors': 0
        }
        
        # Step 1: Import customers
        if customers_data.get('customers'):
            customer_results, guest_mapping = save_customers_to_database(customers_data['customers'], app)
            final_results['customers'] = customer_results
        else:
            guest_mapping = {}
            print("⚠️ No customer data to import")
        
        # Step 2: Import bookings
        if customers_data.get('bookings'):
            booking_results = save_bookings_to_database(customers_data['bookings'], guest_mapping, app)
            final_results['bookings'] = booking_results
        else:
            print("⚠️ No booking data to import")
        
        # Step 3: Import message templates
        if templates_data:
            template_results = save_templates_to_database(templates_data, app)
            final_results['templates'] = template_results
        else:
            print("⚠️ No template data to import")
        
        # Step 4: Import expenses
        if expenses_data:
            expense_results = save_expenses_to_database(expenses_data, app)
            final_results['expenses'] = expense_results
        else:
            print("⚠️ No expense data to import")
        
        # Calculate totals
        final_results['total_success'] = (
            final_results['customers'].get('imported', 0) + 
            final_results['customers'].get('updated', 0) +
            final_results['bookings'].get('imported', 0) + 
            final_results['bookings'].get('updated', 0) +
            final_results['templates'].get('imported', 0) + 
            final_results['templates'].get('updated', 0) +
            final_results['expenses'].get('imported', 0)
        )
        
        final_results['total_errors'] = (
            len(final_results['customers'].get('errors', [])) +
            len(final_results['bookings'].get('errors', [])) +
            len(final_results['templates'].get('errors', [])) +
            len(final_results['expenses'].get('errors', []))
        )
        
        print(f"\n📊 FINAL IMPORT SUMMARY:")
        print(f"   👥 Customers: {final_results['customers'].get('imported', 0)} new, {final_results['customers'].get('updated', 0)} updated")
        print(f"   📋 Bookings: {final_results['bookings'].get('imported', 0)} new, {final_results['bookings'].get('updated', 0)} updated")
        print(f"   💬 Templates: {final_results['templates'].get('imported', 0)} new, {final_results['templates'].get('updated', 0)} updated")
        print(f"   💰 Expenses: {final_results['expenses'].get('imported', 0)} new, {final_results['expenses'].get('skipped', 0)} skipped")
        print(f"   📈 Total Success: {final_results['total_success']}")
        print(f"   ❌ Total Errors: {final_results['total_errors']}")
        
        if final_results['total_errors'] > 0:
            print(f"\n⚠️ ERRORS SUMMARY:")
            for category, results in final_results.items():
                if isinstance(results, dict) and results.get('errors'):
                    print(f"   {category}: {len(results['errors'])} errors")
                    for error in results['errors'][:3]:  # Show first 3 errors
                        print(f"     - {error}")
        
        return final_results
        
    except Exception as e:
        print(f"❌ CRITICAL IMPORT ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {'error': str(e), 'total_success': 0, 'total_errors': 1}

if __name__ == "__main__":
    # Test the database import functionality
    print("🧪 Testing database import functionality...")
    
    # Sample test data
    test_customers = {
        'customers': [
            {'full_name': 'Test Customer', 'email': 'test@example.com', 'phone': '123456789'}
        ],
        'bookings': []
    }
    test_templates = []
    test_expenses = []
    
    results = comprehensive_database_import(test_customers, test_templates, test_expenses)
    print(f"Test results: {results}")