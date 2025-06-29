#!/usr/bin/env python3
"""
Simple Railway Sync - Use Flask app environment
This script uses your existing Flask app to sync data to Railway
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import from your existing Flask app
from app import app
from core.models import db, Booking, QuickNote, Expense, MessageTemplate
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import pandas as pd

# Load environment variables
load_dotenv()

def sync_to_railway():
    """Sync data from current database to Railway"""
    print("🚀 Simple Railway Sync")
    print("=" * 40)
    
    # Get Railway database URL
    railway_url = os.getenv('RAILWAY_DATABASE_URL')
    if not railway_url:
        print("❌ RAILWAY_DATABASE_URL not found in .env file")
        return False
    
    print(f"🔍 Railway URL: {railway_url[:50]}...")
    
    try:
        # Test Railway connection
        print("🔌 Testing Railway connection...")
        railway_engine = create_engine(railway_url)
        
        with railway_engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ Railway connection successful!")
            print(f"📊 PostgreSQL Version: {version[:100]}...")
        
        # Use Flask app context to access current database
        with app.app_context():
            print("📦 Connecting to current database...")
            
            # Test current database connection
            try:
                current_count = db.session.execute(text("SELECT COUNT(*) FROM bookings")).fetchone()[0]
                print(f"📋 Current database has {current_count} bookings")
            except Exception as e:
                print(f"❌ Current database connection failed: {e}")
                return False
            
            # Create Railway tables using SQLAlchemy
            print("🏗️ Creating Railway database schema...")
            
            # Connect SQLAlchemy to Railway
            railway_db_config = app.config['SQLALCHEMY_DATABASE_URI']
            app.config['SQLALCHEMY_DATABASE_URI'] = railway_url
            
            # Reinitialize database with Railway URL
            db.init_app(app)
            
            with app.app_context():
                # Create all tables on Railway
                db.create_all()
                print("✅ Railway schema created successfully!")
                
                # Restore original database URL for reading data
                app.config['SQLALCHEMY_DATABASE_URI'] = railway_db_config
                db.init_app(app)
                
                # Now read data from current database and write to Railway
                print("📦 Starting data transfer...")
                
                transfer_results = {}
                
                # Transfer Bookings
                print("📤 Transferring bookings...")
                bookings = Booking.query.all()
                print(f"   Found {len(bookings)} bookings to transfer")
                
                if bookings:
                    # Switch to Railway database
                    app.config['SQLALCHEMY_DATABASE_URI'] = railway_url
                    db.init_app(app)
                    
                    # Clear existing data
                    with app.app_context():
                        db.session.execute(text("TRUNCATE TABLE bookings RESTART IDENTITY CASCADE"))
                        db.session.commit()
                        
                        # Transfer each booking
                        for booking in bookings:
                            new_booking = Booking(
                                guest_name=booking.guest_name,
                                booking_reference=booking.booking_reference,
                                checkin_date=booking.checkin_date,
                                checkout_date=booking.checkout_date,
                                room_amount=booking.room_amount or 0,
                                taxi_amount=booking.taxi_amount or 0,
                                commission=booking.commission or 0,
                                collected_amount=booking.collected_amount or 0,
                                email=booking.email,
                                phone=booking.phone,
                                payment_collector=booking.payment_collector,
                                notes=booking.notes,
                                status=booking.status or 'active',
                                arrival_confirmed=booking.arrival_confirmed or False,
                                arrival_confirmed_at=booking.arrival_confirmed_at
                            )
                            db.session.add(new_booking)
                        
                        db.session.commit()
                        
                        # Verify transfer
                        transferred_count = db.session.execute(text("SELECT COUNT(*) FROM bookings")).fetchone()[0]
                        transfer_results['bookings'] = {
                            'source': len(bookings),
                            'transferred': transferred_count,
                            'success': transferred_count > 0
                        }
                        print(f"   ✅ Transferred {transferred_count} bookings")
                    
                    # Restore original database
                    app.config['SQLALCHEMY_DATABASE_URI'] = railway_db_config
                    db.init_app(app)
                
                # Transfer Quick Notes
                print("📤 Transferring quick notes...")
                with app.app_context():
                    notes = QuickNote.query.all()
                    print(f"   Found {len(notes)} notes to transfer")
                    
                    if notes:
                        # Switch to Railway
                        app.config['SQLALCHEMY_DATABASE_URI'] = railway_url
                        db.init_app(app)
                        
                        with app.app_context():
                            db.session.execute(text("TRUNCATE TABLE quick_notes RESTART IDENTITY CASCADE"))
                            db.session.commit()
                            
                            for note in notes:
                                new_note = QuickNote(
                                    note_type=note.note_type,
                                    content=note.content,
                                    guest_name=note.guest_name,
                                    booking_id=note.booking_id
                                )
                                db.session.add(new_note)
                            
                            db.session.commit()
                            transferred_count = db.session.execute(text("SELECT COUNT(*) FROM quick_notes")).fetchone()[0]
                            transfer_results['quick_notes'] = {
                                'source': len(notes),
                                'transferred': transferred_count,
                                'success': transferred_count > 0
                            }
                            print(f"   ✅ Transferred {transferred_count} notes")
                        
                        # Restore original database
                        app.config['SQLALCHEMY_DATABASE_URI'] = railway_db_config
                        db.init_app(app)
                
                # Transfer Expenses
                print("📤 Transferring expenses...")
                with app.app_context():
                    expenses = Expense.query.all()
                    print(f"   Found {len(expenses)} expenses to transfer")
                    
                    if expenses:
                        # Switch to Railway
                        app.config['SQLALCHEMY_DATABASE_URI'] = railway_url
                        db.init_app(app)
                        
                        with app.app_context():
                            db.session.execute(text("TRUNCATE TABLE expenses RESTART IDENTITY CASCADE"))
                            db.session.commit()
                            
                            for expense in expenses:
                                new_expense = Expense(
                                    description=expense.description,
                                    amount=expense.amount,
                                    category=expense.category,
                                    expense_date=expense.expense_date
                                )
                                db.session.add(new_expense)
                            
                            db.session.commit()
                            transferred_count = db.session.execute(text("SELECT COUNT(*) FROM expenses")).fetchone()[0]
                            transfer_results['expenses'] = {
                                'source': len(expenses),
                                'transferred': transferred_count,
                                'success': transferred_count > 0
                            }
                            print(f"   ✅ Transferred {transferred_count} expenses")
                        
                        # Restore original database
                        app.config['SQLALCHEMY_DATABASE_URI'] = railway_db_config
                        db.init_app(app)
                
                # Transfer Message Templates
                print("📤 Transferring message templates...")
                with app.app_context():
                    templates = MessageTemplate.query.all()
                    print(f"   Found {len(templates)} templates to transfer")
                    
                    if templates:
                        # Switch to Railway
                        app.config['SQLALCHEMY_DATABASE_URI'] = railway_url
                        db.init_app(app)
                        
                        with app.app_context():
                            db.session.execute(text("TRUNCATE TABLE message_templates RESTART IDENTITY CASCADE"))
                            db.session.commit()
                            
                            for template in templates:
                                new_template = MessageTemplate(
                                    template_name=template.template_name,
                                    category=template.category,
                                    template_content=template.template_content
                                )
                                db.session.add(new_template)
                            
                            db.session.commit()
                            transferred_count = db.session.execute(text("SELECT COUNT(*) FROM message_templates")).fetchone()[0]
                            transfer_results['message_templates'] = {
                                'source': len(templates),
                                'transferred': transferred_count,
                                'success': transferred_count > 0
                            }
                            print(f"   ✅ Transferred {transferred_count} templates")
                        
                        # Restore original database
                        app.config['SQLALCHEMY_DATABASE_URI'] = railway_db_config
                        db.init_app(app)
                
                # Final verification
                print("")
                print("🎉 SYNC COMPLETED!")
                print("📊 Transfer Summary:")
                total_transferred = 0
                all_success = True
                
                for table, result in transfer_results.items():
                    status = "✅" if result['success'] else "❌"
                    print(f"   {status} {table}: {result['transferred']}/{result['source']} records")
                    total_transferred += result['transferred']
                    if not result['success']:
                        all_success = False
                
                print(f"")
                print(f"📈 Total records transferred: {total_transferred}")
                print(f"🎯 Overall success: {'Yes' if all_success else 'No'}")
                
                if all_success:
                    print("")
                    print("🚀 Next steps:")
                    print("1. Update your Railway app environment variables")
                    print("2. Set DATABASE_URL to your Railway PostgreSQL URL")
                    print("3. Deploy your Railway app")
                    print("4. Your app will now use Railway PostgreSQL!")
                
                return all_success
        
    except Exception as e:
        print(f"❌ Sync failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = sync_to_railway()
    if success:
        print("\n✅ Sync completed successfully!")
    else:
        print("\n❌ Sync failed. Check the errors above.")