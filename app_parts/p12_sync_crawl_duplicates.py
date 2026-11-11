# p12_sync_crawl_duplicates — sync services, crawl admin bookings, bulk save, duplicate management, revenue comparison
# Part of app.py (lines 14788-16447 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
# =====================================================
# DATA SYNCHRONIZATION API ENDPOINTS
# =====================================================


# =====================================================
# ===== OLD APARTMENT ENDPOINTS REMOVED (duplicates) - See lines 9102-9364 for new system =====
# # 🏢 APARTMENT MANAGEMENT API ENDPOINTS
# =====================================================

# @app.route('/api/apartments', methods=['GET'])
# def get_apartments():
#     """Get all apartments"""
#     try:
#         from core.models import Apartment
#         apartments = Apartment.query.filter_by(is_active=True).order_by(Apartment.apartment_name).all()

#         return jsonify({
#             'success': True,
#             'apartments': [apt.to_dict() for apt in apartments]
#         })
#     except Exception as e:
#         print(f"❌ [GET_APARTMENTS] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/apartments/<int:apartment_id>', methods=['GET'])
# def get_apartment_by_id(apartment_id):
#     """Get single apartment details - LEGACY ENDPOINT (duplicate removed)"""
#     try:
#         from core.models import Apartment
#         apartment = Apartment.query.get(apartment_id)

#         if not apartment:
#             return jsonify({
#                 'success': False,
#                 'error': 'Apartment not found'
#             }), 404

#         return jsonify({
#             'success': True,
#             'apartment': apartment.to_dict()
#         })
#     except Exception as e:
#         print(f"❌ [GET_APARTMENT] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/apartments', methods=['POST'])
# def create_apartment_legacy():
#     """Create new apartment"""
#     try:
#         from core.models import Apartment, db
#         data = request.get_json()

#         # Validate required fields
#         if not data.get('apartment_name'):
#             return jsonify({
#                 'success': False,
#                 'error': 'Apartment name is required'
#             }), 400

#         # Check if apartment already exists
#         existing = Apartment.query.filter_by(apartment_name=data['apartment_name']).first()
#         if existing:
#             return jsonify({
#                 'success': False,
#                 'error': 'Apartment with this name already exists'
#             }), 400

#         # Create new apartment
#         apartment = Apartment(
#             apartment_name=data['apartment_name'],
#             apartment_address=data.get('apartment_address'),
#             total_rooms=data.get('total_rooms', 1),
#             max_guests_per_room=data.get('max_guests_per_room', 2),
#             apartment_type=data.get('apartment_type'),
#             floor_number=data.get('floor_number'),
#             building_name=data.get('building_name'),
#             owner_name=data.get('owner_name'),
#             owner_phone=data.get('owner_phone'),
#             property_notes=data.get('property_notes'),
#             is_active=data.get('is_active', True)
#         )

#         db.session.add(apartment)
#         db.session.commit()

#         print(f"✅ [CREATE_APARTMENT] Created apartment: {apartment.apartment_name}")

#         return jsonify({
#             'success': True,
#             'apartment': apartment.to_dict(),
#             'message': f'Apartment "{apartment.apartment_name}" created successfully'
#         }), 201
#     except Exception as e:
#         print(f"❌ [CREATE_APARTMENT] Error: {str(e)}")
#         db.session.rollback()
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/apartments/<int:apartment_id>', methods=['PUT'])
# def update_apartment(apartment_id):
#     """Update apartment details"""
#     try:
#         from core.models import Apartment, db
#         apartment = Apartment.query.get(apartment_id)

#         if not apartment:
#             return jsonify({
#                 'success': False,
#                 'error': 'Apartment not found'
#             }), 404

#         data = request.get_json()

#         # Update fields
#         if 'apartment_name' in data:
#             # Check for duplicate name
#             existing = Apartment.query.filter(
#                 Apartment.apartment_name == data['apartment_name'],
#                 Apartment.apartment_id != apartment_id
#             ).first()
#             if existing:
#                 return jsonify({
#                     'success': False,
#                     'error': 'Apartment with this name already exists'
#                 }), 400
#             apartment.apartment_name = data['apartment_name']

#         if 'apartment_address' in data:
#             apartment.apartment_address = data['apartment_address']
#         if 'total_rooms' in data:
#             apartment.total_rooms = data['total_rooms']
#         if 'max_guests_per_room' in data:
#             apartment.max_guests_per_room = data['max_guests_per_room']
#         if 'apartment_type' in data:
#             apartment.apartment_type = data['apartment_type']
#         if 'floor_number' in data:
#             apartment.floor_number = data['floor_number']
#         if 'building_name' in data:
#             apartment.building_name = data['building_name']
#         if 'owner_name' in data:
#             apartment.owner_name = data['owner_name']
#         if 'owner_phone' in data:
#             apartment.owner_phone = data['owner_phone']
#         if 'property_notes' in data:
#             apartment.property_notes = data['property_notes']
#         if 'is_active' in data:
#             apartment.is_active = data['is_active']

#         db.session.commit()

#         print(f"✅ [UPDATE_APARTMENT] Updated apartment: {apartment.apartment_name}")

#         return jsonify({
#             'success': True,
#             'apartment': apartment.to_dict(),
#             'message': f'Apartment "{apartment.apartment_name}" updated successfully'
#         })
#     except Exception as e:
#         print(f"❌ [UPDATE_APARTMENT] Error: {str(e)}")
#         db.session.rollback()
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/apartments/<int:apartment_id>', methods=['DELETE'])
# def delete_apartment(apartment_id):
#     """Soft delete apartment (set is_active = False)"""
#     try:
#         from core.models import Apartment, Booking, db
#         apartment = Apartment.query.get(apartment_id)

#         if not apartment:
#             return jsonify({
#                 'success': False,
#                 'error': 'Apartment not found'
#             }), 404

#         # Check if apartment has bookings
#         booking_count = Booking.query.filter_by(apartment_id=apartment_id).count()

#         if booking_count > 0:
#             # Soft delete - just mark as inactive
#             apartment.is_active = False
#             db.session.commit()

#             print(f"✅ [DELETE_APARTMENT] Deactivated apartment: {apartment.apartment_name} ({booking_count} bookings)")

#             return jsonify({
#                 'success': True,
#                 'message': f'Apartment "{apartment.apartment_name}" deactivated (has {booking_count} bookings)'
#             })
#         else:
#             # Hard delete if no bookings
#             db.session.delete(apartment)
#             db.session.commit()

#             print(f"✅ [DELETE_APARTMENT] Deleted apartment: {apartment.apartment_name}")

#             return jsonify({
#                 'success': True,
#                 'message': f'Apartment "{apartment.apartment_name}" deleted successfully'
#             })
#     except Exception as e:
#         print(f"❌ [DELETE_APARTMENT] Error: {str(e)}")
#         db.session.rollback()
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/apartments/<int:apartment_id>/stats', methods=['GET'])
# def get_apartment_stats(apartment_id):
#     """Get apartment statistics"""
#     try:
#         from core.models import Apartment, Booking
#         from sqlalchemy import func
#         from datetime import datetime, date

#         apartment = Apartment.query.get(apartment_id)

#         if not apartment:
#             return jsonify({
#                 'success': False,
#                 'error': 'Apartment not found'
#             }), 404

#         # Get booking statistics
#         total_bookings = Booking.query.filter_by(apartment_id=apartment_id).count()

#         # Active bookings (currently checked in)
#         today = date.today()
#         active_bookings = Booking.query.filter(
#             Booking.apartment_id == apartment_id,
#             Booking.checkin_date <= today,
#             Booking.checkout_date > today,
#             Booking.booking_status.in_(['confirmed', 'mới'])
#         ).count()

#         # Upcoming bookings
#         upcoming_bookings = Booking.query.filter(
#             Booking.apartment_id == apartment_id,
#             Booking.checkin_date > today,
#             Booking.booking_status.in_(['confirmed', 'mới'])
#         ).count()

#         # Total revenue (all time)
#         revenue_result = db.session.query(
#             func.sum(Booking.room_amount).label('total_revenue')
#         ).filter(
#             Booking.apartment_id == apartment_id,
#             Booking.booking_status.in_(['confirmed', 'mới'])
#         ).first()

#         total_revenue = float(revenue_result.total_revenue or 0)

#         # Monthly revenue (current month)
#         current_month_start = date(today.year, today.month, 1)
#         monthly_revenue_result = db.session.query(
#             func.sum(Booking.room_amount).label('monthly_revenue')
#         ).filter(
#             Booking.apartment_id == apartment_id,
#             Booking.checkin_date >= current_month_start,
#             Booking.booking_status.in_(['confirmed', 'mới'])
#         ).first()

#         monthly_revenue = float(monthly_revenue_result.monthly_revenue or 0)

#         return jsonify({
#             'success': True,
#             'apartment': apartment.to_dict(),
#             'stats': {
#                 'total_bookings': total_bookings,
#                 'active_bookings': active_bookings,
#                 'upcoming_bookings': upcoming_bookings,
#                 'total_revenue': total_revenue,
#                 'monthly_revenue': monthly_revenue,
#                 'occupancy_rate': (active_bookings / apartment.total_rooms * 100) if apartment.total_rooms > 0 else 0
#             }
#         })
#     except Exception as e:
#         print(f"❌ [GET_APARTMENT_STATS] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# =====================================================
# ===== OLD ROOM ENDPOINTS REMOVED (duplicates) - See lines 9367-9534 for new system =====
# # ROOM MANAGEMENT APIs
# =====================================================

# @app.route('/api/rooms', methods=['GET'])
# def get_rooms():
#     """Get all active rooms, optionally filtered by apartment"""
#     try:
#         from core.models import Room, Apartment

#         apartment_id = request.args.get('apartment_id', type=int)

#         # Build query
#         query = Room.query.filter_by(is_active=True)

#         if apartment_id:
#             query = query.filter_by(apartment_id=apartment_id)

#         rooms = query.order_by(Room.apartment_id, Room.display_order).all()

#         return jsonify({
#             'success': True,
#             'rooms': [room.to_dict() for room in rooms]
#         })
#     except Exception as e:
#         print(f"❌ [GET_ROOMS] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/rooms/<int:room_id>', methods=['GET'])
# def get_room(room_id):
#     """Get specific room details"""
#     try:
#         from core.models import Room

#         room = Room.query.get(room_id)
#         if not room:
#             return jsonify({
#                 'success': False,
#                 'error': 'Room not found'
#             }), 404

#         return jsonify({
#             'success': True,
#             'room': room.to_dict()
#         })
#     except Exception as e:
#         print(f"❌ [GET_ROOM] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/rooms', methods=['POST'])
# def create_room():
#     """Create new room"""
#     try:
#         from core.models import Room, db

#         data = request.get_json()

#         # Validate required fields
#         if not data.get('room_name'):
#             return jsonify({
#                 'success': False,
#                 'error': 'Room name is required'
#             }), 400

#         if not data.get('apartment_id'):
#             return jsonify({
#                 'success': False,
#                 'error': 'Apartment ID is required'
#             }), 400

#         # Create room
#         room = Room(
#             room_name=data['room_name'],
#             apartment_id=data['apartment_id'],
#             room_type=data.get('room_type'),
#             max_guests=data.get('max_guests', 2),
#             floor_number=data.get('floor_number'),
#             room_features=data.get('room_features'),
#             is_active=data.get('is_active', True),
#             display_order=data.get('display_order', 0)
#         )

#         db.session.add(room)
#         db.session.commit()

#         return jsonify({
#             'success': True,
#             'room': room.to_dict()
#         }), 201

#     except Exception as e:
#         db.session.rollback()
#         print(f"❌ [CREATE_ROOM] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/rooms/<int:room_id>', methods=['PUT'])
# def update_room(room_id):
#     """Update existing room"""
#     try:
#         from core.models import Room, db

#         room = Room.query.get(room_id)
#         if not room:
#             return jsonify({
#                 'success': False,
#                 'error': 'Room not found'
#             }), 404

#         data = request.get_json()

#         # Update fields
#         if 'room_name' in data:
#             room.room_name = data['room_name']
#         if 'apartment_id' in data:
#             room.apartment_id = data['apartment_id']
#         if 'room_type' in data:
#             room.room_type = data['room_type']
#         if 'max_guests' in data:
#             room.max_guests = data['max_guests']
#         if 'floor_number' in data:
#             room.floor_number = data['floor_number']
#         if 'room_features' in data:
#             room.room_features = data['room_features']
#         if 'is_active' in data:
#             room.is_active = data['is_active']
#         if 'display_order' in data:
#             room.display_order = data['display_order']

#         db.session.commit()

#         return jsonify({
#             'success': True,
#             'room': room.to_dict()
#         })

#     except Exception as e:
#         db.session.rollback()
#         print(f"❌ [UPDATE_ROOM] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/rooms/<int:room_id>', methods=['DELETE'])
# def delete_room(room_id):
#     """Soft delete room (set is_active=False)"""
#     try:
#         from core.models import Room, Booking, db

#         room = Room.query.get(room_id)
#         if not room:
#             return jsonify({
#                 'success': False,
#                 'error': 'Room not found'
#             }), 404

#         # Check if room has active bookings
#         active_bookings = Booking.query.filter_by(room_id=room_id).filter(
#             Booking.booking_status.in_(['confirmed', 'mới', 'pending'])
#         ).count()

#         if active_bookings > 0:
#             return jsonify({
#                 'success': False,
#                 'error': f'Cannot delete room with {active_bookings} active bookings. Please cancel or move bookings first.'
#             }), 400

#         # Soft delete
#         room.is_active = False
#         db.session.commit()

#         return jsonify({
#             'success': True,
#             'message': 'Room deactivated successfully'
#         })

#     except Exception as e:
#         db.session.rollback()
#         print(f"❌ [DELETE_ROOM] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/rooms/<int:room_id>/stats', methods=['GET'])
# def get_room_stats(room_id):
#     """Get statistics for a specific room"""
#     try:
#         from core.models import Room, Booking, db
#         from datetime import date, timedelta
#         from sqlalchemy import func

#         room = Room.query.get(room_id)
#         if not room:
#             return jsonify({
#                 'success': False,
#                 'error': 'Room not found'
#             }), 404

#         today = date.today()
#         first_day_of_month = today.replace(day=1)

#         # Total bookings
#         total_bookings = Booking.query.filter_by(room_id=room_id).count()

#         # Active bookings (confirmed, not cancelled)
#         active_bookings = Booking.query.filter_by(room_id=room_id).filter(
#             Booking.booking_status.in_(['confirmed', 'mới'])
#         ).count()

#         # Upcoming bookings
#         upcoming_bookings = Booking.query.filter_by(room_id=room_id).filter(
#             Booking.checkin_date >= today,
#             Booking.booking_status.in_(['confirmed', 'mới'])
#         ).count()

#         # Total revenue (all time)
#         total_revenue = db.session.query(func.sum(Booking.room_amount)).filter(
#             Booking.room_id == room_id,
#             Booking.booking_status.in_(['confirmed', 'mới'])
#         ).scalar() or 0

#         # Monthly revenue
#         monthly_revenue = db.session.query(func.sum(Booking.room_amount)).filter(
#             Booking.room_id == room_id,
#             Booking.checkin_date >= first_day_of_month,
#             Booking.booking_status.in_(['confirmed', 'mới'])
#         ).scalar() or 0

#         return jsonify({
#             'success': True,
#             'room': room.to_dict(),
#             'stats': {
#                 'total_bookings': total_bookings,
#                 'active_bookings': active_bookings,
#                 'upcoming_bookings': upcoming_bookings,
#                 'total_revenue': float(total_revenue),
#                 'monthly_revenue': float(monthly_revenue)
#             }
#         })
#     except Exception as e:
#         print(f"❌ [GET_ROOM_STATS] Error: {str(e)}")
#         return jsonify({
#             'success': False,
#             'error': str(e)
#         }), 500

# @app.route('/api/expenses')
def api_expenses():
    """Get monthly expenses for dashboard"""
    try:
        from core.logic_postgresql import get_monthly_expenses
        
        # Get all expenses (not filtered by month)
        expenses = get_monthly_expenses(show_all=True)
        
        if expenses is None:
            expenses = []
        
        # Convert to proper format
        expense_list = []
        if isinstance(expenses, list):
            for expense in expenses:
                if isinstance(expense, dict):
                    expense_list.append({
                        'description': expense.get('description', 'Expense'),
                        'amount': float(expense.get('amount', 0)),
                        'date': expense.get('date'),
                        'expense_date': expense.get('expense_date'),
                        'created_at': expense.get('created_at')
                    })
        
        return jsonify({
            'success': True,
            'expenses': expense_list,
            'total_count': len(expense_list)
        })
        
    except Exception as e:
        print(f"❌ [EXPENSES_API] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Expenses API failed: {str(e)}',
            'expenses': []
        }), 500




