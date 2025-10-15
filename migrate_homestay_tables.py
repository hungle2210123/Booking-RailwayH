#!/usr/bin/env python3
"""
Database Migration Script: Homestay Setup Tracker Tables
Creates three new tables: homestay_properties, setup_item_templates, purchase_records
"""

import os
import sys
from datetime import datetime
from flask import Flask
from core.models import db, HomestayProperty, SetupItemTemplate, PurchaseRecord

# Initialize Flask app
app = Flask(__name__)

# Database configuration - auto-detect
DATABASE_SOURCE = os.getenv('DATABASE_SOURCE', 'auto')

if DATABASE_SOURCE == 'auto':
    # Try Railway first, fallback to local
    railway_url = os.getenv('DATABASE_URL')
    if railway_url and railway_url.startswith('postgres://'):
        railway_url = railway_url.replace('postgres://', 'postgresql://', 1)
        app.config['SQLALCHEMY_DATABASE_URI'] = railway_url
        print("✅ Using Railway PostgreSQL database")
    else:
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:locloc123@localhost:5432/hotel_booking'
        print("✅ Using Local PostgreSQL database")
elif DATABASE_SOURCE == 'railway':
    railway_url = os.getenv('DATABASE_URL')
    if railway_url and railway_url.startswith('postgres://'):
        railway_url = railway_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = railway_url
    print("✅ Using Railway PostgreSQL database")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:locloc123@localhost:5432/hotel_booking'
    print("✅ Using Local PostgreSQL database")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# Initialize database
db.init_app(app)

def migrate_homestay_tables():
    """Create homestay setup tracker tables"""
    with app.app_context():
        try:
            print("\n" + "="*60)
            print("🏠 HOMESTAY SETUP TRACKER - DATABASE MIGRATION")
            print("="*60 + "\n")

            # Create tables
            print("📋 Creating new tables...")
            db.create_all()
            print("✅ Tables created successfully!")

            # Verify tables exist
            print("\n🔍 Verifying tables...")
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()

            required_tables = [
                'homestay_properties',
                'setup_item_templates',
                'purchase_records'
            ]

            for table in required_tables:
                if table in tables:
                    print(f"  ✅ {table} - EXISTS")
                else:
                    print(f"  ❌ {table} - MISSING")

            # Add sample data
            print("\n💡 Adding sample template items...")
            add_sample_templates()

            print("\n" + "="*60)
            print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
            print("="*60)

        except Exception as e:
            print(f"\n❌ Migration failed: {str(e)}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

def add_sample_templates():
    """Add sample setup item templates"""

    sample_templates = [
        # Furniture
        {'item_name': 'Giường đôi (1.6m x 2m)', 'item_category': 'Furniture', 'estimated_price': 3000000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Tủ quần áo', 'item_category': 'Furniture', 'estimated_price': 2000000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Bàn làm việc', 'item_category': 'Furniture', 'estimated_price': 1500000, 'priority': 'medium'},
        {'item_name': 'Ghế làm việc', 'item_category': 'Furniture', 'estimated_price': 800000, 'priority': 'medium'},
        {'item_name': 'Sofa 2 chỗ', 'item_category': 'Furniture', 'estimated_price': 4000000, 'priority': 'medium'},
        {'item_name': 'Bàn ăn + 4 ghế', 'item_category': 'Furniture', 'estimated_price': 2500000, 'priority': 'medium'},

        # Appliances
        {'item_name': 'Máy lạnh 1.5 HP', 'item_category': 'Appliances', 'estimated_price': 7000000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Máy giặt 8kg', 'item_category': 'Appliances', 'estimated_price': 5000000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Tủ lạnh 150L', 'item_category': 'Appliances', 'estimated_price': 4000000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Bếp điện từ đôi', 'item_category': 'Appliances', 'estimated_price': 1500000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Nồi cơm điện', 'item_category': 'Appliances', 'estimated_price': 500000, 'priority': 'medium'},
        {'item_name': 'Máy hút bụi', 'item_category': 'Appliances', 'estimated_price': 800000, 'priority': 'low'},

        # Bedding
        {'item_name': 'Nệm cao cấp 1.6m', 'item_category': 'Bedding', 'estimated_price': 2500000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Bộ chăn ga gối (4 món)', 'item_category': 'Bedding', 'estimated_price': 500000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Gối đầu (set 4 cái)', 'item_category': 'Bedding', 'estimated_price': 400000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Chăn đông', 'item_category': 'Bedding', 'estimated_price': 300000, 'priority': 'medium'},

        # Kitchen
        {'item_name': 'Bộ nồi chảo', 'item_category': 'Kitchen', 'estimated_price': 800000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Bộ dao thớt', 'item_category': 'Kitchen', 'estimated_price': 200000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Bộ đồ ăn (6 người)', 'item_category': 'Kitchen', 'estimated_price': 500000, 'priority': 'medium'},
        {'item_name': 'Ly cốc (set 12)', 'item_category': 'Kitchen', 'estimated_price': 200000, 'priority': 'medium'},
        {'item_name': 'Thùng rác phân loại', 'item_category': 'Kitchen', 'estimated_price': 300000, 'priority': 'medium'},

        # Bathroom
        {'item_name': 'Bình nóng lạnh 30L', 'item_category': 'Bathroom', 'estimated_price': 2000000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Gương nhà tắm', 'item_category': 'Bathroom', 'estimated_price': 300000, 'priority': 'medium'},
        {'item_name': 'Giá để đồ nhà tắm', 'item_category': 'Bathroom', 'estimated_price': 200000, 'priority': 'medium'},
        {'item_name': 'Rèm nhà tắm', 'item_category': 'Bathroom', 'estimated_price': 100000, 'priority': 'low'},

        # Electronics
        {'item_name': 'TV 43 inch Smart', 'item_category': 'Electronics', 'estimated_price': 6000000, 'priority': 'high'},
        {'item_name': 'Router WiFi', 'item_category': 'Electronics', 'estimated_price': 500000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Đèn LED trần', 'item_category': 'Electronics', 'estimated_price': 400000, 'priority': 'high', 'is_required': True},
        {'item_name': 'Quạt trần', 'item_category': 'Electronics', 'estimated_price': 1000000, 'priority': 'medium'},

        # Decor
        {'item_name': 'Rèm cửa chính', 'item_category': 'Decor', 'estimated_price': 800000, 'priority': 'medium'},
        {'item_name': 'Tranh treo tường (set 3)', 'item_category': 'Decor', 'estimated_price': 500000, 'priority': 'low'},
        {'item_name': 'Thảm trải sàn', 'item_category': 'Decor', 'estimated_price': 600000, 'priority': 'low'},
        {'item_name': 'Cây cảnh trang trí', 'item_category': 'Decor', 'estimated_price': 200000, 'priority': 'low'},
    ]

    # Check if templates already exist
    existing_count = SetupItemTemplate.query.count()
    if existing_count > 0:
        print(f"  ℹ️  {existing_count} templates already exist, skipping sample data")
        return

    # Add templates
    added_count = 0
    for template_data in sample_templates:
        template = SetupItemTemplate(**template_data)
        db.session.add(template)
        added_count += 1

    db.session.commit()
    print(f"  ✅ Added {added_count} sample item templates")

if __name__ == '__main__':
    migrate_homestay_tables()
