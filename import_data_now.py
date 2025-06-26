#!/usr/bin/env python3
"""
Direct Database Import - Immediate Solution
Ultra optimized to work with existing Flask setup
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def import_data_directly():
    """
    Import data directly using the existing Flask application
    """
    print("🚀 STARTING DIRECT IMPORT")
    print("=" * 50)
    
    try:
        # Import Flask and create app with same config as your running app
        from flask import Flask
        from dotenv import load_dotenv
        
        # Load environment
        load_dotenv(project_root / ".env")
        
        # Create Flask app with same configuration
        app = Flask(__name__, 
                   template_folder=project_root / "templates", 
                   static_folder=project_root / "static")
        
        # Production configuration (same as your running app)
        app.config['ENV'] = 'production'
        app.config['DEBUG'] = False
        app.secret_key = os.getenv("FLASK_SECRET_KEY", "a_default_secret_key_for_development")
        app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Initialize database with app
        from core.models import db
        db.init_app(app)
        
        print("✅ Flask app initialized")
        
        # Import data processing modules
        from core.comprehensive_import import (
            parse_excel_file, 
            import_customers_from_sheet1,
            import_message_templates_from_sheet2,
            import_expenses_from_sheet5
        )
        
        print("✅ Import modules loaded")
        
        # Check if Excel file exists
        excel_file_path = project_root / "csvtest.xlsx"
        if not excel_file_path.exists():
            print(f"❌ Excel file not found: {excel_file_path}")
            return False
        
        print(f"✅ Excel file found: {excel_file_path}")
        
        # Step 1: Parse Excel file
        print("\n📊 PARSING EXCEL FILE...")
        sheets_data = parse_excel_file(str(excel_file_path))
        if not sheets_data:
            print("❌ Failed to parse Excel file")
            return False
        
        print(f"✅ Parsed {len(sheets_data)} sheets")
        
        # Step 2: Extract data
        print("\n📋 EXTRACTING DATA...")
        customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
        templates_data = import_message_templates_from_sheet2(sheets_data.get('Sheet2', []))
        expenses_data = import_expenses_from_sheet5(sheets_data.get('Sheet5', []))
        
        customers_count = len(customers_data.get('customers', []))
        bookings_count = len(customers_data.get('bookings', []))
        templates_count = len(templates_data)
        expenses_count = len(expenses_data)
        
        print(f"✅ Extracted:")
        print(f"   👥 {customers_count} customers")
        print(f"   📋 {bookings_count} bookings")
        print(f"   💬 {templates_count} templates")
        print(f"   💰 {expenses_count} expenses")
        
        # Step 3: Import to database within Flask context
        print("\n💾 IMPORTING TO DATABASE...")
        
        with app.app_context():
            from core.models import Guest, Booking, MessageTemplate, Expense
            
            import_stats = {
                'customers_new': 0,
                'customers_updated': 0,
                'bookings_new': 0, 
                'bookings_updated': 0,
                'templates_new': 0,
                'templates_updated': 0,
                'expenses_new': 0,
                'expenses_skipped': 0,
                'errors': []
            }
            
            # Import customers first
            print("👥 Importing customers...")
            guest_mapping = {}
            
            for customer in customers_data.get('customers', []):
                try:
                    existing_guest = Guest.query.filter_by(full_name=customer['full_name']).first()
                    
                    if not existing_guest:
                        new_guest = Guest(
                            full_name=customer['full_name'],
                            email=customer.get('email'),
                            phone=customer.get('phone'),
                            nationality=customer.get('nationality'),
                            passport_number=customer.get('passport_number')
                        )
                        db.session.add(new_guest)
                        db.session.flush()
                        guest_mapping[customer['full_name']] = new_guest.guest_id
                        import_stats['customers_new'] += 1
                        print(f"   ✅ New: {customer['full_name']}")
                    else:
                        guest_mapping[customer['full_name']] = existing_guest.guest_id
                        import_stats['customers_updated'] += 1
                        print(f"   📝 Exists: {customer['full_name']}")
                        
                except Exception as e:
                    error = f"Customer {customer.get('full_name', 'Unknown')}: {e}"
                    import_stats['errors'].append(error)
                    print(f"   ❌ {error}")
            
            db.session.commit()
            print(f"✅ Customers committed: {import_stats['customers_new']} new, {import_stats['customers_updated']} existing")
            
            # Import bookings
            print("📋 Importing bookings...")
            
            for booking in customers_data.get('bookings', []):
                try:
                    guest_id = guest_mapping.get(booking['guest_name'])
                    if not guest_id:
                        error = f"Booking {booking['booking_id']}: Guest '{booking['guest_name']}' not found"
                        import_stats['errors'].append(error)
                        print(f"   ❌ {error}")
                        continue
                    
                    existing_booking = Booking.query.filter_by(booking_id=booking['booking_id']).first()
                    
                    if not existing_booking:
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
                        import_stats['bookings_new'] += 1
                        print(f"   ✅ New: {booking['booking_id']} - {booking['guest_name']}")
                    else:
                        # Update existing booking
                        existing_booking.room_amount = booking['room_amount'] or 0.0
                        existing_booking.taxi_amount = booking['taxi_amount'] or 0.0
                        existing_booking.commission = booking['commission'] or 0.0
                        existing_booking.collector = booking.get('collector')
                        existing_booking.booking_status = booking.get('booking_status', 'confirmed')
                        existing_booking.booking_notes = booking.get('booking_notes')
                        import_stats['bookings_updated'] += 1
                        print(f"   📝 Updated: {booking['booking_id']} - {booking['guest_name']}")
                        
                except Exception as e:
                    error = f"Booking {booking.get('booking_id', 'Unknown')}: {e}"
                    import_stats['errors'].append(error)
                    print(f"   ❌ {error}")
            
            db.session.commit()
            print(f"✅ Bookings committed: {import_stats['bookings_new']} new, {import_stats['bookings_updated']} updated")
            
            # Import templates
            print("💬 Importing message templates...")
            
            for template in templates_data:
                try:
                    template_name = template['template_name']
                    if len(template_name) > 255:
                        template_name = template_name[:250] + "..."
                    
                    existing_template = MessageTemplate.query.filter_by(template_name=template_name).first()
                    
                    if not existing_template:
                        new_template = MessageTemplate(
                            template_name=template_name,
                            category=template['category'][:100] if template['category'] else 'general',
                            template_content=template['template_content']
                        )
                        db.session.add(new_template)
                        import_stats['templates_new'] += 1
                        print(f"   ✅ New: {template_name[:50]}...")
                    else:
                        existing_template.template_content = template['template_content']
                        existing_template.category = template['category'][:100] if template['category'] else 'general'
                        import_stats['templates_updated'] += 1
                        print(f"   📝 Updated: {template_name[:50]}...")
                        
                except Exception as e:
                    error = f"Template {template.get('template_name', 'Unknown')[:30]}: {e}"
                    import_stats['errors'].append(error)
                    print(f"   ❌ {error}")
            
            db.session.commit()
            print(f"✅ Templates committed: {import_stats['templates_new']} new, {import_stats['templates_updated']} updated")
            
            # Import expenses
            print("💰 Importing expenses...")
            
            for expense in expenses_data:
                try:
                    existing_expense = Expense.query.filter_by(
                        description=expense['description'],
                        amount=expense['amount'],
                        expense_date=expense['expense_date']
                    ).first()
                    
                    if not existing_expense:
                        new_expense = Expense(
                            description=expense['description'],
                            amount=expense['amount'],
                            expense_date=expense['expense_date'],
                            category=expense['category'],
                            collector=expense['collector']
                        )
                        db.session.add(new_expense)
                        import_stats['expenses_new'] += 1
                        print(f"   ✅ New: {expense['description'][:30]}... - {expense['amount']:,.0f}đ")
                    else:
                        import_stats['expenses_skipped'] += 1
                        print(f"   ⏭️ Skipped: {expense['description'][:30]}... - {expense['amount']:,.0f}đ")
                        
                except Exception as e:
                    error = f"Expense {expense.get('description', 'Unknown')[:30]}: {e}"
                    import_stats['errors'].append(error)
                    print(f"   ❌ {error}")
            
            db.session.commit()
            print(f"✅ Expenses committed: {import_stats['expenses_new']} new, {import_stats['expenses_skipped']} skipped")
            
            # Final summary
            total_success = (
                import_stats['customers_new'] + import_stats['customers_updated'] +
                import_stats['bookings_new'] + import_stats['bookings_updated'] +
                import_stats['templates_new'] + import_stats['templates_updated'] +
                import_stats['expenses_new']
            )
            
            print(f"\n🎉 IMPORT COMPLETED SUCCESSFULLY!")
            print(f"📊 FINAL SUMMARY:")
            print(f"   👥 Customers: {import_stats['customers_new']} new, {import_stats['customers_updated']} existing")
            print(f"   📋 Bookings: {import_stats['bookings_new']} new, {import_stats['bookings_updated']} updated")
            print(f"   💬 Templates: {import_stats['templates_new']} new, {import_stats['templates_updated']} updated")
            print(f"   💰 Expenses: {import_stats['expenses_new']} new, {import_stats['expenses_skipped']} skipped")
            print(f"   📈 Total Success: {total_success}")
            print(f"   ❌ Total Errors: {len(import_stats['errors'])}")
            
            if import_stats['errors']:
                print(f"\n⚠️ ERRORS:")
                for error in import_stats['errors'][:5]:  # Show first 5
                    print(f"   - {error}")
                if len(import_stats['errors']) > 5:
                    print(f"   ... and {len(import_stats['errors']) - 5} more errors")
            
            # Verify data was imported
            final_counts = {
                'customers': Guest.query.count(),
                'bookings': Booking.query.count(),
                'templates': MessageTemplate.query.count(),
                'expenses': Expense.query.count()
            }
            
            print(f"\n✅ DATABASE VERIFICATION:")
            print(f"   👥 Total customers in database: {final_counts['customers']}")
            print(f"   📋 Total bookings in database: {final_counts['bookings']}")
            print(f"   💬 Total templates in database: {final_counts['templates']}")
            print(f"   💰 Total expenses in database: {final_counts['expenses']}")
            
            return total_success > 0
        
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 DIRECT DATABASE IMPORT - IMMEDIATE SOLUTION")
    print("=" * 70)
    
    success = import_data_directly()
    
    if success:
        print("\n🎉 SUCCESS! Your CSV data has been imported to PostgreSQL!")
        print("📍 Next steps:")
        print("   1. Refresh your Flask app browser page")
        print("   2. Check Dashboard for updated statistics")
        print("   3. Go to 'Quản lý Đặt phòng' to see imported bookings")
        print("   4. Visit 'Chi Phí Tháng' to see imported expenses")
        print("   5. Check 'Quản Lý Dữ Liệu' for data management")
    else:
        print("\n❌ Import failed. Check error messages above.")
    
    input("\nPress Enter to exit...")