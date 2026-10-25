# p10_apartments_rooms — apartments + rooms CRUD, migrate
# Part of app.py (lines 12226-12911 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
# ============================================================
# APARTMENT MANAGEMENT ROUTES - 100% Data-Driven System
# ============================================================

@app.route('/apartments')
def apartments_management():
    """Apartment management page - Add/Edit/Delete apartments without code changes"""
    return render_template('apartments.html')

@app.route('/api/apartments', methods=['GET'])
def get_apartments_list():
    """Get all apartments with statistics"""
    try:
        from core.models import Apartment, Room, db

        apartments = Apartment.query.order_by(Apartment.apartment_id).all()
        apartments_data = [apt.to_dict() for apt in apartments]

        # Calculate statistics
        total_apartments = len(apartments)
        active_apartments = len([apt for apt in apartments if apt.is_active])
        total_rooms = sum((apt.total_rooms or 0) for apt in apartments)
        max_capacity = sum((apt.max_guests_per_room or 0) * (apt.total_rooms or 0) for apt in apartments)

        return jsonify({
            'success': True,
            'apartments': apartments_data,
            'stats': {
                'total_apartments': total_apartments,
                'active_apartments': active_apartments,
                'total_rooms': total_rooms,
                'max_capacity': max_capacity
            }
        })
    except Exception as e:
        print(f"Error loading apartments: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/apartments/<int:apartment_id>', methods=['GET'])
def get_apartment_details(apartment_id):
    """Get single apartment details"""
    try:
        from core.models import Apartment, db

        apartment = Apartment.query.get(apartment_id)
        if not apartment:
            return jsonify({'success': False, 'error': 'Apartment not found'}), 404

        return jsonify({
            'success': True,
            'apartment': apartment.to_dict()
        })
    except Exception as e:
        print(f"Error loading apartment {apartment_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/apartments', methods=['POST'])
def create_new_apartment():
    """Create new apartment - NO CODE CHANGES NEEDED"""
    try:
        from core.models import Apartment, Room, db

        data = request.get_json()

        # Validate required fields
        if not data.get('apartment_name'):
            return jsonify({'success': False, 'error': 'Apartment name is required'}), 400

        # Create apartment
        new_apartment = Apartment(
            apartment_name=data['apartment_name'],
            apartment_address=data.get('apartment_address'),
            total_rooms=data.get('total_rooms', 1),
            max_guests_per_room=data.get('max_guests_per_room', 2),
            apartment_type=data.get('apartment_type'),
            is_active=True,
            owner_name=data.get('owner_name'),
            owner_phone=data.get('owner_phone'),
            property_notes=data.get('property_notes')
        )

        db.session.add(new_apartment)
        db.session.flush()  # Get the apartment_id

        # Auto-create rooms if requested
        if data.get('auto_create_rooms', True):
            total_rooms = data.get('total_rooms', 1)
            for i in range(total_rooms):
                room = Room(
                    room_name=f"{data['apartment_name']} - Room {i+1}",
                    apartment_id=new_apartment.apartment_id,
                    room_type=data.get('apartment_type', 'Standard'),
                    max_guests=data.get('max_guests_per_room', 2),
                    is_active=True,
                    display_order=i+1
                )
                db.session.add(room)

        db.session.commit()

        print(f"✅ Created apartment: {new_apartment.apartment_name} (ID: {new_apartment.apartment_id})")

        return jsonify({
            'success': True,
            'message': 'Apartment created successfully',
            'apartment': new_apartment.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error creating apartment: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/apartments/<int:apartment_id>', methods=['PUT'])
def update_apartment_info(apartment_id):
    """Update apartment details"""
    try:
        from core.models import Apartment, db

        apartment = Apartment.query.get(apartment_id)
        if not apartment:
            return jsonify({'success': False, 'error': 'Apartment not found'}), 404

        data = request.get_json()

        # Update fields
        if 'apartment_name' in data:
            apartment.apartment_name = data['apartment_name']
        if 'apartment_address' in data:
            apartment.apartment_address = data['apartment_address']
        if 'apartment_type' in data:
            apartment.apartment_type = data['apartment_type']
        if 'max_guests_per_room' in data:
            apartment.max_guests_per_room = data['max_guests_per_room']
        if 'owner_name' in data:
            apartment.owner_name = data['owner_name']
        if 'owner_phone' in data:
            apartment.owner_phone = data['owner_phone']
        if 'property_notes' in data:
            apartment.property_notes = data['property_notes']

        db.session.commit()

        print(f"✅ Updated apartment: {apartment.apartment_name} (ID: {apartment_id})")

        return jsonify({
            'success': True,
            'message': 'Apartment updated successfully',
            'apartment': apartment.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error updating apartment {apartment_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/apartments/<int:apartment_id>/toggle', methods=['POST'])
def toggle_apartment_status(apartment_id):
    """Toggle apartment active status"""
    try:
        from core.models import Apartment, db

        apartment = Apartment.query.get(apartment_id)
        if not apartment:
            return jsonify({'success': False, 'error': 'Apartment not found'}), 404

        # Toggle active status
        apartment.is_active = not apartment.is_active
        db.session.commit()

        status = 'activated' if apartment.is_active else 'deactivated'
        print(f"✅ {status.capitalize()} apartment: {apartment.apartment_name} (ID: {apartment_id})")

        return jsonify({
            'success': True,
            'message': f'Apartment {status} successfully',
            'is_active': apartment.is_active
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error toggling apartment {apartment_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

def _apartment_references(apartment_id):
    """How many bookings point at this apartment (placement, apartment_id, or one of its rooms)."""
    from core.models import db
    today = (datetime.utcnow() + timedelta(hours=7)).date()
    row = db.session.execute(text("""
        SELECT
          COUNT(*) FILTER (WHERE b.actual_apartment = :sid)                            AS placed,
          COUNT(*) FILTER (WHERE b.actual_apartment = :sid AND b.checkout_date > :today) AS placed_upcoming,
          COUNT(*) FILTER (WHERE b.apartment_id = :aid)                                AS linked,
          COUNT(*) FILTER (WHERE b.room_id IN (SELECT room_id FROM rooms WHERE apartment_id = :aid)) AS by_room
        FROM bookings b
    """), {'sid': str(apartment_id), 'aid': apartment_id, 'today': today}).fetchone()
    rooms = db.session.execute(text("SELECT COUNT(*) FROM rooms WHERE apartment_id = :aid"),
                               {'aid': apartment_id}).scalar()
    return {'placed': row[0], 'placed_upcoming': row[1], 'linked': row[2],
            'by_room': row[3], 'rooms': rooms}


@app.route('/api/apartments/<int:apartment_id>/delete_check', methods=['GET'])
def apartment_delete_check(apartment_id):
    """What deleting this apartment would affect — shown to the user before confirming."""
    try:
        from core.models import Apartment
        apartment = Apartment.query.get(apartment_id)
        if not apartment:
            return jsonify({'success': False, 'error': 'Không tìm thấy căn hộ'}), 404
        refs = _apartment_references(apartment_id)
        others = [{'id': a.apartment_id, 'name': a.apartment_name, 'is_active': a.is_active}
                  for a in Apartment.query.filter(Apartment.apartment_id != apartment_id)
                                          .order_by(Apartment.apartment_id).all()]
        return jsonify({'success': True, 'apartment': apartment.apartment_name,
                        'refs': refs, 'needs_move': bool(refs['placed'] or refs['linked']),
                        'other_apartments': others})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/apartments/<int:apartment_id>', methods=['DELETE'])
def delete_apartment_permanently(apartment_id):
    """Delete an apartment (e.g. one added by mistake).

    Bookings placed in it must go somewhere first: body {"move_bookings_to": <apartment_id>}
    moves them to another apartment, {"move_bookings_to": null} clears the placement.
    Its rooms are deleted with it (bookings.room_id pointing at them becomes NULL).
    """
    from core.models import Apartment, db
    try:
        apartment = Apartment.query.get(apartment_id)
        if not apartment:
            return jsonify({'success': False, 'error': 'Không tìm thấy căn hộ'}), 404

        data = request.get_json(silent=True) or {}
        refs = _apartment_references(apartment_id)
        needs_move = bool(refs['placed'] or refs['linked'])
        if needs_move and 'move_bookings_to' not in data:
            return jsonify({'success': False, 'needs_move': True, 'refs': refs,
                            'error': 'Căn hộ còn booking — chọn căn để chuyển booking sang trước khi xoá'}), 409

        target = data.get('move_bookings_to')
        if target is not None:
            try:
                target = int(target)
            except (TypeError, ValueError):
                return jsonify({'success': False, 'error': 'Căn chuyển tới không hợp lệ'}), 400
            if target == apartment_id or not Apartment.query.get(target):
                return jsonify({'success': False, 'error': 'Căn chuyển tới không hợp lệ'}), 400

        name = apartment.apartment_name
        if needs_move:
            db.session.execute(
                text("UPDATE bookings SET actual_apartment = :t WHERE actual_apartment = :sid"),
                {'t': str(target) if target is not None else None, 'sid': str(apartment_id)})
            db.session.execute(
                text("UPDATE bookings SET apartment_id = :t WHERE apartment_id = :aid"),
                {'t': target, 'aid': apartment_id})
        # rooms go with the apartment (FK ON DELETE CASCADE; bookings.room_id → SET NULL)
        db.session.execute(text("DELETE FROM rooms WHERE apartment_id = :aid"), {'aid': apartment_id})
        db.session.execute(text("DELETE FROM apartments WHERE apartment_id = :aid"), {'aid': apartment_id})
        db.session.commit()
        print(f"🗑️ Deleted apartment {name} (ID: {apartment_id}); bookings moved to {target}; refs={refs}")
        return jsonify({'success': True, 'message': f'Đã xoá căn hộ "{name}"',
                        'moved': refs['placed'] + refs['linked'] if needs_move else 0,
                        'moved_to': target, 'rooms_deleted': refs['rooms'],
                        'room_links_cleared': refs['by_room']})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting apartment {apartment_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/apartments/<int:apartment_id>/rooms', methods=['GET'])
def get_apartment_rooms(apartment_id):
    """Get all rooms for an apartment"""
    try:
        from core.models import Room, db

        rooms = Room.query.filter_by(apartment_id=apartment_id)\
                          .order_by(Room.display_order)\
                          .all()

        rooms_data = [room.to_dict() for room in rooms]

        return jsonify({
            'success': True,
            'rooms': rooms_data,
            'count': len(rooms_data)
        })

    except Exception as e:
        print(f"Error loading rooms for apartment {apartment_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/accommodation_options', methods=['GET'])
def get_accommodation_options():
    """Return ALL apartments + rooms for the booking edit dropdown.

    Strategy (two-pass):
    1. ALL rows from the apartments table (no is_active filter — avoids missing
       apartments whose flag may be wrong).
    2. Scan distinct accommodation_name values in bookings and surface any that
       aren't already covered by a formal apartment entry (e.g. legacy strings
       like '25 hoi vu' that exist only in booking records).

    Colour palette matches the calendar for visual consistency.
    """
    try:
        from core.models import Apartment as AptModel, Room as RoomModel, Booking, db
        from sqlalchemy import distinct as sa_distinct

        APT_COLORS = ['#1976D2', '#2E7D32', '#7B1FA2', '#E64A19', '#00838F', '#F57F17']

        # ── Pass 1: formal apartment table (ALL rows, no is_active filter) ──────
        apts = AptModel.query.order_by(AptModel.apartment_id).all()
        result = []
        covered_names_lower = set()          # track what we've already included

        for idx, apt in enumerate(apts):
            rooms = RoomModel.query.filter_by(
                apartment_id=apt.apartment_id
            ).order_by(RoomModel.display_order).all()
            result.append({
                'id':    apt.apartment_id,
                'name':  apt.apartment_name,
                'color': APT_COLORS[idx % len(APT_COLORS)],
                'rooms': [{'name': r.room_name} for r in rooms],
            })
            covered_names_lower.add(apt.apartment_name.lower().strip())
            # Also mark individual room names so we don't duplicate them
            for r in rooms:
                covered_names_lower.add(r.room_name.lower().strip())

        # ── Pass 2: legacy accommodation_name strings in bookings ────────────────
        # Group raw strings by their "parent" name (normalise case) and collect
        # unique room-level values seen within each parent group.
        legacy_rows = (
            db.session.query(sa_distinct(Booking.accommodation_name))
            .filter(
                Booking.accommodation_name.isnot(None),
                Booking.accommodation_name != '',
            )
            .order_by(Booking.accommodation_name)
            .all()
        )

        for (acc_name,) in legacy_rows:
            if not acc_name:
                continue
            acc_lower = acc_name.lower().strip()
            if acc_lower in covered_names_lower:
                continue  # already represented by a formal apartment or room
            # Surface as a standalone "apartment" with no sub-rooms
            idx_legacy = len(result)
            result.append({
                'id':    None,
                'name':  acc_name,
                'color': APT_COLORS[idx_legacy % len(APT_COLORS)],
                'rooms': [],
            })
            covered_names_lower.add(acc_lower)

        print(f"📋 accommodation_options: {len(result)} entries returned")
        return jsonify({'success': True, 'apartments': result})
    except Exception as e:
        print(f"Error loading accommodation options: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/apartments/<int:apartment_id>/stats', methods=['GET'])
def get_apartment_stats(apartment_id):
    """Get statistics for a specific apartment"""
    try:
        from core.models import Apartment, Booking, db
        from sqlalchemy import func
        from datetime import datetime, timedelta

        apartment = Apartment.query.get(apartment_id)
        if not apartment:
            return jsonify({'success': False, 'error': 'Apartment not found'}), 404

        # Get current month bookings for this apartment
        today = datetime.now().date()
        start_of_month = datetime(today.year, today.month, 1).date()
        if today.month == 12:
            end_of_month = datetime(today.year + 1, 1, 1).date()
        else:
            end_of_month = datetime(today.year, today.month + 1, 1).date()

        # Count active bookings
        active_bookings = Booking.query.filter(
            Booking.apartment_id == apartment_id,
            Booking.booking_status != 'deleted',
            Booking.checkin_date <= end_of_month,
            Booking.checkout_date >= start_of_month
        ).count()

        # Calculate revenue
        revenue_result = db.session.query(
            func.sum(Booking.room_amount)
        ).filter(
            Booking.apartment_id == apartment_id,
            Booking.booking_status != 'deleted',
            Booking.checkin_date >= start_of_month,
            Booking.checkin_date < end_of_month
        ).scalar()

        monthly_revenue = float(revenue_result) if revenue_result else 0.0

        return jsonify({
            'success': True,
            'stats': {
                'apartment_id': apartment_id,
                'apartment_name': apartment.apartment_name,
                'active_bookings': active_bookings,
                'monthly_revenue': monthly_revenue,
                'total_rooms': apartment.total_rooms,
                'max_capacity': (apartment.max_guests_per_room or 0) * (apartment.total_rooms or 0)
            }
        })

    except Exception as e:
        print(f"Error loading stats for apartment {apartment_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# ROOM MANAGEMENT ROUTES - Full CRUD for Web Interface
# ============================================================

@app.route('/api/rooms', methods=['POST'])
def create_room():
    """Create new room - Web manageable"""
    try:
        from core.models import Room, Apartment, db

        data = request.get_json()

        # Validate required fields
        if not data.get('room_name'):
            return jsonify({'success': False, 'error': 'Room name is required'}), 400
        if not data.get('apartment_id'):
            return jsonify({'success': False, 'error': 'Apartment ID is required'}), 400

        # Verify apartment exists
        apartment = Apartment.query.get(data['apartment_id'])
        if not apartment:
            return jsonify({'success': False, 'error': 'Apartment not found'}), 404

        # Get next display order
        max_order = db.session.query(db.func.max(Room.display_order))\
                              .filter_by(apartment_id=data['apartment_id'])\
                              .scalar() or 0

        # Create room
        new_room = Room(
            room_name=data['room_name'],
            apartment_id=data['apartment_id'],
            room_type=data.get('room_type', 'Standard'),
            max_guests=data.get('max_guests', 2),
            is_active=data.get('is_active', True),
            display_order=max_order + 1,
            room_features=data.get('room_features', '')
        )

        db.session.add(new_room)

        # Update apartment total_rooms count
        current_rooms_count = Room.query.filter_by(apartment_id=data['apartment_id']).count()
        apartment.total_rooms = current_rooms_count + 1

        db.session.commit()

        print(f"✅ Created room: {new_room.room_name} in apartment {apartment.apartment_name}")

        return jsonify({
            'success': True,
            'message': 'Room created successfully',
            'room': new_room.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error creating room: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<int:room_id>', methods=['PUT'])
def update_room(room_id):
    """Update room details - Web manageable"""
    try:
        from core.models import Room, db

        room = Room.query.get(room_id)
        if not room:
            return jsonify({'success': False, 'error': 'Room not found'}), 404

        data = request.get_json()

        # Update fields
        if 'room_name' in data:
            room.room_name = data['room_name']
        if 'room_type' in data:
            room.room_type = data['room_type']
        if 'max_guests' in data:
            room.max_guests = data['max_guests']
        if 'is_active' in data:
            room.is_active = data['is_active']
        if 'room_features' in data:
            room.room_features = data['room_features']
        if 'display_order' in data:
            room.display_order = data['display_order']

        db.session.commit()

        print(f"✅ Updated room: {room.room_name} (ID: {room_id})")

        return jsonify({
            'success': True,
            'message': 'Room updated successfully',
            'room': room.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error updating room {room_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<int:room_id>', methods=['DELETE'])
def delete_room(room_id):
    """Delete room - Web manageable"""
    try:
        from core.models import Room, Booking, Apartment, db

        room = Room.query.get(room_id)
        if not room:
            return jsonify({'success': False, 'error': 'Room not found'}), 404

        apartment_id = room.apartment_id
        room_name = room.room_name

        # Check if room has bookings
        booking_count = Booking.query.filter_by(room_id=room_id).count()

        if booking_count > 0:
            # Soft delete - mark as inactive
            room.is_active = False
            db.session.commit()

            print(f"⚠️ Deactivated room {room_name} ({booking_count} bookings exist)")

            return jsonify({
                'success': True,
                'message': f'Room "{room_name}" deactivated ({booking_count} bookings exist)',
                'soft_delete': True
            })
        else:
            # Hard delete if no bookings
            db.session.delete(room)

            # Update apartment total_rooms count
            apartment = Apartment.query.get(apartment_id)
            if apartment:
                remaining_rooms = Room.query.filter_by(apartment_id=apartment_id).count() - 1
                apartment.total_rooms = max(0, remaining_rooms)

            db.session.commit()

            print(f"✅ Deleted room: {room_name}")

            return jsonify({
                'success': True,
                'message': f'Room "{room_name}" deleted successfully',
                'soft_delete': False
            })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting room {room_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rooms/<int:room_id>', methods=['GET'])
def get_room_details(room_id):
    """Get single room details"""
    try:
        from core.models import Room

        room = Room.query.get(room_id)
        if not room:
            return jsonify({'success': False, 'error': 'Room not found'}), 404

        return jsonify({
            'success': True,
            'room': room.to_dict()
        })

    except Exception as e:
        print(f"Error loading room {room_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ============================================================
# END OF ROOM MANAGEMENT ROUTES
# ============================================================

# ============================================================
# END OF APARTMENT MANAGEMENT ROUTES
# ============================================================

@app.route('/migrate')
def migration_tool():
    """Serve the database migration tool page"""
    return send_from_directory('.', 'run_migration.html')

@app.route('/api/migrate_database', methods=['POST'])
def migrate_database():
    """Enhanced migration route for multi-image functionality"""
    try:
        from core.models import db
        from sqlalchemy import text
        
        migration_results = []
        
        # 1. Check and add image_path column to message_templates table
        check_column_sql = """
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'message_templates' 
        AND column_name = 'image_path';
        """
        
        result = db.session.execute(text(check_column_sql)).fetchone()
        
        if not result:
            # Add the missing column
            alter_sql = "ALTER TABLE message_templates ADD COLUMN image_path VARCHAR(500);"
            db.session.execute(text(alter_sql))
            migration_results.append("Added image_path column to message_templates")
        else:
            migration_results.append("image_path column already exists")
        
        # 2. Check and create template_images table
        check_table_sql = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name = 'template_images';
        """
        
        table_result = db.session.execute(text(check_table_sql)).fetchone()
        
        if not table_result:
            # Create template_images table
            create_table_sql = """
            CREATE TABLE template_images (
                image_id SERIAL PRIMARY KEY,
                template_id INTEGER NOT NULL,
                image_path VARCHAR(500) NOT NULL,
                image_filename VARCHAR(255) NOT NULL,
                image_order INTEGER DEFAULT 1,
                alt_text VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (template_id) REFERENCES message_templates(template_id) ON DELETE CASCADE
            );
            """
            db.session.execute(text(create_table_sql))
            migration_results.append("Created template_images table")
        else:
            migration_results.append("template_images table already exists")
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Database migration completed successfully',
            'results': migration_results
        })
            
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Migration failed: {str(e)}',
            'action': 'error'
        }), 500

