#!/usr/bin/env python3
"""
🏢 APARTMENT QUICK ADD HELPER
================================
Interactive script to add a new apartment with rooms
NO CODE CHANGES NEEDED - 100% database-driven
"""

import os
import sys
from app import app
from core.models import db, Apartment, Room

def add_new_apartment():
    """Interactive apartment creation"""

    print("=" * 60)
    print("🏢 ADD NEW APARTMENT - INTERACTIVE MODE")
    print("=" * 60)
    print()

    # Get apartment details
    apt_name = input("📍 Apartment name (e.g., '42 Hang Gai'): ").strip()
    if not apt_name:
        print("❌ Apartment name is required!")
        return

    apt_address = input("🏠 Full address (optional, press Enter to skip): ").strip()
    owner_name = input("👤 Owner name (optional, press Enter to skip): ").strip()

    print()
    print("=" * 60)
    print("🛏️  ROOM CONFIGURATION")
    print("=" * 60)
    print()

    # Get room details
    print("You're adding: 3x 1-bedroom + 1x 2-bedroom = 4 rooms")
    print()

    # Ask for room names
    rooms_data = []

    print("Enter names for the 3 one-bedroom apartments:")
    for i in range(3):
        room_name = input(f"  1BR #{i+1} name (e.g., '{apt_name} - 10{i+1}'): ").strip()
        if not room_name:
            room_name = f"{apt_name} - 10{i+1}"
        rooms_data.append({
            'name': room_name,
            'type': '1-Bedroom',
            'max_guests': 2,
            'order': i + 1,
            'features': 'One bedroom, kitchen, bathroom'
        })

    print()
    room_name = input(f"  2BR name (e.g., '{apt_name} - 201'): ").strip()
    if not room_name:
        room_name = f"{apt_name} - 201"
    rooms_data.append({
        'name': room_name,
        'type': '2-Bedroom',
        'max_guests': 4,
        'order': 4,
        'features': 'Two bedrooms, kitchen, bathroom, living room'
    })

    print()
    print("=" * 60)
    print("📋 SUMMARY")
    print("=" * 60)
    print(f"Apartment: {apt_name}")
    print(f"Address: {apt_address or 'N/A'}")
    print(f"Owner: {owner_name or 'N/A'}")
    print(f"Total rooms: 4 (3x 1BR + 1x 2BR)")
    print()
    print("Rooms:")
    for i, room in enumerate(rooms_data, 1):
        print(f"  {i}. {room['name']} - {room['type']} (max {room['max_guests']} guests)")
    print()

    confirm = input("✅ Confirm and create? (yes/no): ").strip().lower()
    if confirm not in ['yes', 'y']:
        print("❌ Cancelled by user")
        return

    # Create apartment and rooms
    try:
        with app.app_context():
            # Create apartment
            new_apartment = Apartment(
                apartment_name=apt_name,
                apartment_address=apt_address or None,
                total_rooms=4,
                max_guests_per_room=2,
                apartment_type='Mixed (3x 1BR + 1x 2BR)',
                is_active=True,
                owner_name=owner_name or None,
                property_notes='3 one-bedroom units + 1 two-bedroom unit'
            )
            db.session.add(new_apartment)
            db.session.flush()  # Get the apartment_id

            print(f"\n✅ Apartment created with ID: {new_apartment.apartment_id}")

            # Create rooms
            for room_data in rooms_data:
                new_room = Room(
                    room_name=room_data['name'],
                    apartment_id=new_apartment.apartment_id,
                    room_type=room_data['type'],
                    max_guests=room_data['max_guests'],
                    is_active=True,
                    display_order=room_data['order'],
                    room_features=room_data['features']
                )
                db.session.add(new_room)
                print(f"✅ Room created: {room_data['name']}")

            db.session.commit()

            print()
            print("=" * 60)
            print("🎉 SUCCESS!")
            print("=" * 60)
            print(f"Apartment '{apt_name}' has been added successfully!")
            print(f"Apartment ID: {new_apartment.apartment_id}")
            print(f"Total rooms created: 4")
            print()
            print("🔄 No code changes needed - the calendar will automatically")
            print("   show the new apartment once the admin interface is ready!")
            print("=" * 60)

    except Exception as e:
        db.session.rollback()
        print(f"\n❌ ERROR: {str(e)}")
        print("Please check the error and try again.")
        return

if __name__ == '__main__':
    add_new_apartment()
