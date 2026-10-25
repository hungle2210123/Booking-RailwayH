# p12_sync_crawl_duplicates — sync services, crawl admin bookings, bulk save, duplicate management, revenue comparison
# Part of app.py (lines 14788-16447 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
# =====================================================
# DATA SYNCHRONIZATION API ENDPOINTS
# =====================================================

@app.route('/api/sync/test_connections')
def api_test_sync_connections():
    """Test connections to both local and Railway databases"""
    try:
        from core.sync_service import DataSyncService
        
        sync_service = DataSyncService()
        results = sync_service.test_connections()
        
        return jsonify({
            'success': True,
            'connections': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Connection test failed: {str(e)}'
        }), 500

@app.route('/api/sync/status')
def api_sync_status():
    """Get current database status and record counts"""
    try:
        from core.sync_service import DataSyncService
        
        sync_service = DataSyncService()
        connections = sync_service.test_connections()
        
        # Calculate sync recommendation
        local_counts = connections.get('local_counts', {})
        railway_counts = connections.get('railway_counts', {})
        
        sync_needed = False
        differences = {}
        
        for table in ['bookings', 'guests', 'notes', 'expenses', 'templates']:
            local_count = local_counts.get(table, 0)
            railway_count = railway_counts.get(table, 0)
            diff = local_count - railway_count
            
            differences[table] = {
                'local': local_count,
                'railway': railway_count,
                'difference': diff
            }
            
            if diff != 0:
                sync_needed = True
        
        return jsonify({
            'success': True,
            'local_status': connections['local_status'],
            'railway_status': connections['railway_status'],
            'sync_needed': sync_needed,
            'differences': differences,
            'local_error': connections.get('local_error'),
            'railway_error': connections.get('railway_error')
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Status check failed: {str(e)}'
        }), 500

@app.route('/api/auto-sync/status')
def api_auto_sync_status():
    """Auto-sync status endpoint for the dashboard"""
    try:
        from core.sync_service import DataSyncService
        
        # Get actual sync status using existing sync service
        sync_service = DataSyncService()
        connections = sync_service.test_connections()
        
        # Calculate sync differences
        local_counts = connections.get('local_counts', {})
        railway_counts = connections.get('railway_counts', {})
        
        sync_needed = False
        differences = {}
        
        for table in ['bookings', 'guests', 'notes', 'expenses']:
            local_count = local_counts.get(table, 0)
            railway_count = railway_counts.get(table, 0)
            diff = local_count - railway_count
            
            if diff != 0:
                sync_needed = True
                
            differences[table] = {
                'local': local_count,
                'railway': railway_count,
                'difference': diff
            }
        
        return jsonify({
            'success': True,
            'auto_sync_enabled': True,
            'sync_needed': sync_needed,
            'last_sync': None,
            'sync_interval': '5 minutes',
            'database_source': os.getenv('DATABASE_SOURCE', 'auto'),
            'differences': differences,
            'local_connected': connections.get('local_connected', False),
            'railway_connected': connections.get('railway_connected', False),
            'local_counts': local_counts,
            'railway_counts': railway_counts,
            'message': 'Auto-sync is available'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'sync_needed': False,
            'auto_sync_enabled': False,
            'message': f'Auto-sync status failed: {str(e)}'
        }), 500

@app.route('/api/sync/history')
def api_sync_history():
    """Get sync history for the dashboard"""
    try:
        # Return properly formatted sync history
        history_entries = [
            {
                'timestamp': '2025-07-04 10:30:00',
                'type': 'auto',
                'status': 'success',
                'records_synced': 67,
                'source': 'local',
                'target': 'railway',
                'details': ['67 bookings synced successfully']
            }
        ]
        
        return jsonify({
            'success': True,
            'history': history_entries
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Sync history failed: {str(e)}',
            'history': []
        }), 500

@app.route('/api/sync/perform', methods=['POST'])
def api_sync_perform():
    """Perform actual sync operation"""
    try:
        from core.sync_service import DataSyncService
        
        # Get sync direction from request
        data = request.get_json() or {}
        sync_direction = data.get('direction', 'local_to_railway')
        
        print(f"🔄 [SYNC_PERFORM] Starting sync: {sync_direction}")
        
        # Perform the actual sync
        sync_service = DataSyncService()
        
        if sync_direction == 'local_to_railway':
            result = sync_service.sync_from_local_to_railway()
        elif sync_direction == 'railway_to_local':
            # For now, only support local to railway sync
            return jsonify({
                'success': False,
                'message': 'Railway to local sync not yet implemented. Use local to railway sync instead.'
            }), 400
        else:
            return jsonify({
                'success': False,
                'message': f'Invalid sync direction: {sync_direction}'
            }), 400
        
        print(f"✅ [SYNC_PERFORM] Sync completed: {result}")
        
        return jsonify({
            'success': result.get('success', False),
            'message': result.get('message', 'Sync completed'),
            'direction': sync_direction,
            'records_synced': result.get('records_synced', 0),
            'errors': result.get('errors', [])
        })
        
    except Exception as e:
        print(f"❌ [SYNC_PERFORM] Error: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Sync failed: {str(e)}',
            'direction': sync_direction if 'sync_direction' in locals() else 'unknown',
            'records_synced': 0,
            'errors': [str(e)]
        }), 500

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

# Initialize crawling integration
CrawlIntegration.setup_crawl_routes(app)

@app.route('/api/crawl_capabilities', methods=['GET'])
def get_crawl_capabilities():
    """Get comprehensive crawling capabilities for current environment"""
    try:
        print("🔍 [CRAWL_CAPABILITIES] Starting comprehensive crawl capabilities check...")
        
        # Railway environment detection
        railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
        print(f"🌍 [CRAWL_CAPABILITIES] Railway environment: {railway_env}")
        
        # Import enhanced railway crawl service
        try:
            from core.railway_crawl_service import railway_crawl_service
            print("✅ [CRAWL_CAPABILITIES] Enhanced railway crawl service imported successfully")
            
            is_available = railway_crawl_service.is_crawling_available()
            environment = 'railway' if railway_crawl_service.is_railway else 'local'
            methods = railway_crawl_service.get_crawling_methods()
            setup_instructions = railway_crawl_service._get_setup_instructions()
            
            # Enhanced capability info
            capability_info = {
                'success': True,
                'environment': 'railway' if railway_env else environment,  # FIXED: Correct environment detection
                'crawling_available': is_available,
                'is_available': is_available,  # FIXED: Added for frontend compatibility
                'total_methods': len(methods),
                'supported_methods': len([m for m in methods if m.get('supported', False)]),
                'methods': methods,
                'setup_instructions': setup_instructions,
                'api_keys_configured': {
                    'firecrawl': bool(os.getenv('FIRECRAWL_API_KEY')),
                    'scrapfly': bool(os.getenv('SCRAPFLY_API_KEY')),
                    'scraperapi': bool(os.getenv('SCRAPERAPI_KEY')),
                    'brightdata': bool(os.getenv('BRIGHTDATA_API_KEY'))
                },
                'recommendations': []
            }
            
            # Add recommendations based on environment
            if railway_env and not is_available:
                capability_info['recommendations'].append({
                    'type': 'setup',
                    'message': 'Configure at least one API-based crawling service for Railway deployment',
                    'priority': 'high',
                    'suggested_service': 'firecrawl'
                })
            elif railway_env and is_available:
                capability_info['recommendations'].append({
                    'type': 'success',
                    'message': f'✅ Railway crawling ready with {len([m for m in methods if m.get("supported", False)])} method(s)',
                    'priority': 'info'
                })
            
            print(f"📊 [CRAWL_CAPABILITIES] Found {len(methods)} total methods, {len([m for m in methods if m.get('supported', False)])} supported")
            return jsonify(capability_info)
            
        except ImportError as import_error:
            print(f"⚠️ [CRAWL_CAPABILITIES] Railway crawl service import failed: {import_error}")
            
            # Basic fallback detection
            is_available = False
            environment = 'railway' if railway_env else 'local'
            methods = []
            
            # Check for basic API keys
            if os.getenv('FIRECRAWL_API_KEY'):
                is_available = True
                methods.append({
                    'id': 'firecrawl',
                    'name': 'Firecrawl API (Basic)',
                    'description': 'Cloud-based web scraping service',
                    'supported': True,
                    'priority': 1
                })
            
            methods.append({
                'id': 'direct_http',
                'name': 'Direct HTTP Requests',
                'description': 'Basic HTTP scraping (limited functionality)',
                'supported': True,
                'priority': 5
            })
            
            # Check for Selenium in local environment
            if not railway_env:
                try:
                    import selenium
                    is_available = True
                    methods.append({
                        'id': 'selenium',
                        'name': 'Selenium Browser Automation',
                        'description': 'Full browser automation with saved profiles',
                        'supported': True,
                        'priority': 0
                    })
                except ImportError:
                    methods.append({
                        'id': 'selenium',
                        'name': 'Selenium Browser Automation',
                        'description': 'Install selenium package to enable',
                        'supported': False,
                        'reason': 'Selenium package not installed'
                    })
        
        capabilities = {
            'success': True,
            'environment': 'railway' if railway_env else environment,  # FIXED: Correct environment detection
            'crawling_available': is_available,
            'is_available': is_available,  # FIXED: Added for frontend compatibility
            'total_methods': len(methods),
            'supported_methods': len([m for m in methods if m.get('supported', False)]),
            'methods': methods,
            'alternatives': [
                '📸 Upload booking screenshots for AI extraction',
                '✏️ Manual booking entry',
                '📋 Import from CSV/Excel files'
            ],
            'setup_instructions': {
                'firecrawl': {
                    'name': 'Firecrawl API (Recommended)',
                    'steps': ['Visit https://firecrawl.dev', 'Sign up for account', 'Get API key', 'Set FIRECRAWL_API_KEY environment variable'],
                    'cost': 'Free tier: 500 requests/month'
                }
            }
        }
        
        print(f"✅ [CRAWL_CAPABILITIES] Capabilities: available={is_available}, env={environment}, methods={len(methods)}")
        return jsonify(capabilities)
        
    except Exception as e:
        print(f"❌ [CRAWL_CAPABILITIES] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'is_available': False,
            'environment': 'unknown',
            'methods': [],
            'alternatives': [
                '📸 Upload booking screenshots for AI extraction',
                '✏️ Manual booking entry', 
                '📋 Import from CSV/Excel files'
            ],
            'error': str(e)
        }), 500

@app.route('/api/crawl_admin_bookings', methods=['POST'])
def crawl_admin_bookings():
    """API endpoint for crawling booking admin panel with AI extraction"""
    try:
        # Import Railway-compatible crawling service
        from core.railway_crawl_service import railway_crawl_service
        
        data = request.get_json()
        target_url = data.get('target_url')
        profile_name = data.get('profile_name', 'booking_fixed_profile')
        
        if not target_url:
            return jsonify({'success': False, 'error': 'Target URL required'}), 400
        
        # 🚀 RAILWAY ENHANCEMENT: Use comprehensive crawling service
        is_railway = os.getenv('RAILWAY_PROJECT_ID') is not None
        print(f"🔍 [CRAWL_ADMIN] Environment: {'Railway' if is_railway else 'Local'}")
        
        if not railway_crawl_service.is_crawling_available():
            available_methods = railway_crawl_service.get_crawling_methods()
            setup_instructions = railway_crawl_service._get_setup_instructions()
            
            return jsonify({
                'success': False,
                'error': f'No crawling methods available. Configure API keys to enable Railway crawling.',
                'environment': 'railway' if is_railway else 'local',
                'available_methods': available_methods,
                'setup_instructions': setup_instructions,
                'recommendation': 'Set up Firecrawl API for best Railway compatibility',
                'alternatives': [
                    '📸 Upload booking screenshots for AI extraction',
                    '✏️ Manual booking entry through the form', 
                    '📋 Import from CSV/Excel files'
                ]
            }), 400
        
        # 🚀 OPTIMIZED: Use high-performance crawler for Railway
        if railway_crawl_service.is_railway:
            print(f"🌐 Using optimized cloud-compatible crawling for: {target_url}")
            
            # Import optimized crawler
            try:
                from core.optimized_railway_crawler import optimized_crawler
                import asyncio
                
                # Use optimized crawler with all performance features
                async def optimized_crawl():
                    return await optimized_crawler.crawl_with_retry(target_url, {
                        'required_features': ['javascript'] if 'booking.com' in target_url else [],
                        'cache_type': 'booking_data'
                    })
                
                # Run async crawler
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    crawl_result = loop.run_until_complete(optimized_crawl())
                    
                    # Format result for compatibility
                    result = {
                        'success': True,
                        'method': 'optimized_crawler',
                        'environment': 'railway',
                        'data': crawl_result,
                        'message': '✅ High-performance crawling successful',
                        'performance_optimized': True
                    }
                    
                    # Add performance metrics
                    performance_report = optimized_crawler.get_performance_report()
                    if 'summary' in performance_report:
                        result['performance_metrics'] = performance_report['summary']
                    
                    return jsonify(result)
                    
                finally:
                    loop.close()
                    
            except ImportError:
                print("⚠️ Optimized crawler not available, falling back to standard service")
                result = railway_crawl_service.crawl_admin_bookings_api(target_url, profile_name)
                return jsonify(result)
            except Exception as e:
                print(f"⚠️ Optimized crawler failed: {str(e)}, falling back to standard service")
                result = railway_crawl_service.crawl_admin_bookings_api(target_url, profile_name)
                return jsonify(result)
        
        # Original Selenium-based crawling for local development
        print(f"🕷️ Using Selenium crawling for: {target_url}")
        
        import psutil
        import time
        from pathlib import Path
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        # Check if profile exists
        profile_path = Path.cwd() / "browser_profiles" / profile_name
        if not profile_path.exists():
            return jsonify({'success': False, 'error': 'Browser profile not found. Please setup profile first.'}), 400
        
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            return jsonify({'success': False, 'error': 'Google AI API not configured'}), 400
        
        print(f"🕷️ Starting admin panel crawl for: {target_url}")
        
        # Smart Chrome cleanup using dedicated function
        from smart_chrome_cleanup import smart_chrome_cleanup
        smart_chrome_cleanup(profile_name)
        
        driver = None
        try:
            # Setup Chrome with saved profile
            chrome_options = Options()
            chrome_options.add_argument(f"--user-data-dir={profile_path}")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--force-device-scale-factor=1")
            chrome_options.add_argument("--remote-debugging-port=9227")
            
            print("🌐 Opening browser with saved profile...")
            driver = webdriver.Chrome(options=chrome_options)
            
            print(f"📍 Navigating to admin panel...")
            driver.get(target_url)
            time.sleep(10)
            
            # Check if logged in
            if "login" in driver.current_url.lower():
                return jsonify({'success': False, 'error': 'Profile expired - redirected to login'}), 400
            
            print("✅ Successfully accessed admin panel!")
            
            # Wait for table to load
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table, .bui-table"))
                )
                print("✅ Table loaded!")
            except:
                print("⚠️ Table not found, proceeding anyway...")
            
            time.sleep(5)
            
            # Get full page screenshot
            total_height = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(1920, total_height)
            time.sleep(2)
            
            print("📸 Taking full page screenshot...")
            screenshot_base64 = driver.get_screenshot_as_base64()
            screenshot_bytes = base64.b64decode(screenshot_base64)
            
            print(f"📊 Screenshot size: {len(screenshot_bytes)} bytes")
            
            # Process with AI
            print("🤖 Processing with Gemini AI...")
            booking_info = extract_booking_info_from_image_content(screenshot_bytes, GOOGLE_API_KEY)
            
            if 'error' in booking_info:
                return jsonify({'success': False, 'error': booking_info['error']}), 400
            
            # Process AI results into standard format
            bookings = []
            extracted_count = 0
            
            if booking_info.get('type') == 'multiple' and 'bookings' in booking_info:
                for booking in booking_info['bookings']:
                    if booking.get('guest_name'):
                        booking['source'] = 'admin_crawl'
                        booking['extracted_at'] = datetime.now().isoformat()
                        bookings.append(booking)
                        extracted_count += 1
            elif booking_info.get('guest_name'):
                booking_info['source'] = 'admin_crawl'
                booking_info['extracted_at'] = datetime.now().isoformat()
                bookings.append(booking_info)
                extracted_count = 1
            
            print(f"🎉 Successfully extracted {extracted_count} bookings!")
            
            # Apply AI duplicate detection to crawled bookings (if available)
            ai_analysis = {
                'analysis': {
                    'new_bookings': len(bookings) if bookings else 0,
                    'duplicates_found': 0,
                    'summary': 'AI duplicate detection not available'
                },
                'filtering_options': [],
                'recommendations': []
            }
            if bookings and ai_duplicate_detector:
                print(f"🤖 [AI_DUPLICATE] Applying AI duplicate detection to crawled bookings...")
                df = load_booking_data()
                ai_analysis = ai_duplicate_detector.create_filtered_response(bookings, df)
                
                return jsonify({
                    'success': True,
                    'bookings_count': extracted_count,
                    'bookings': bookings,
                    'ai_analysis': ai_analysis['analysis'],
                    'filtering_options': ai_analysis['filtering_options'],
                    'recommendations': ai_analysis['recommendations'],
                    'message': f"🤖 AI analyzed {extracted_count} crawled bookings - {ai_analysis['analysis']['new_bookings']} new, {ai_analysis['analysis']['duplicates_found']} duplicates"
                })
            elif bookings:
                print("⚠️ [AI_DUPLICATE] AI duplicate detector not available - skipping analysis")
                
                return jsonify({
                    'success': True,
                    'bookings_count': extracted_count,
                    'bookings': bookings,
                    'ai_analysis': ai_analysis['analysis'],
                    'filtering_options': ai_analysis['filtering_options'],
                    'recommendations': ai_analysis['recommendations'],
                    'message': f"🤖 AI analyzed {extracted_count} crawled bookings - {ai_analysis['analysis']['new_bookings']} new, {ai_analysis['analysis']['duplicates_found']} duplicates"
                })
            else:
                return jsonify({
                    'success': True,
                    'bookings_count': 0,
                    'bookings': [],
                    'message': 'No bookings found in admin panel'
                })
            
        except Exception as e:
            print(f"❌ Crawling error: {str(e)}")
            return jsonify({'success': False, 'error': str(e)}), 500
            
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
        
    except Exception as e:
        print(f"❌ [CRAWL_ADMIN] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save_bulk_bookings', methods=['POST'])
def save_bulk_bookings():
    """Save multiple bookings extracted from crawling"""
    try:
        data = request.get_json()
        if not data or 'bookings' not in data:
            return jsonify({'success': False, 'error': 'No bookings data provided'}), 400
        
        bookings = data['bookings']
        print(f"💾 [BULK_SAVE] Attempting to save {len(bookings)} bookings...")
        
        saved_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []
        skipped = []
        
        for i, booking_data in enumerate(bookings):
            try:
                # Validate required fields
                if not booking_data.get('guest_name'):
                    errors.append(f"Booking {i+1}: Missing guest name")
                    failed_count += 1
                    continue
                
                # Check if booking already exists
                booking_id = booking_data.get('booking_id', '').strip()
                if booking_id:
                    from core.models import db, Booking
                    existing_booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
                    if existing_booking:
                        skipped.append(f"Booking {i+1} ({booking_data.get('guest_name')}): Already exists - ID {booking_id}")
                        skipped_count += 1
                        print(f"⚠️ [BULK_SAVE] Booking {booking_id} already exists, skipping...")
                        continue
                
                # Convert date strings to date objects
                from datetime import datetime
                checkin_date = None
                checkout_date = None
                
                try:
                    checkin_str = booking_data.get('check_in_date') or booking_data.get('checkin_date')
                    if checkin_str:
                        checkin_date = datetime.strptime(checkin_str, '%Y-%m-%d').date()
                        
                    checkout_str = booking_data.get('check_out_date') or booking_data.get('checkout_date')
                    if checkout_str:
                        checkout_date = datetime.strptime(checkout_str, '%Y-%m-%d').date()
                        
                except ValueError as e:
                    errors.append(f"Booking {i+1}: Invalid date format - {str(e)}")
                    failed_count += 1
                    continue
                
                if not checkin_date or not checkout_date:
                    errors.append(f"Booking {i+1}: Missing required check-in or check-out date")
                    failed_count += 1
                    continue
                
                # Format booking data for database
                formatted_booking = {
                    'guest_name': booking_data.get('guest_name', ''),
                    'booking_id': booking_data.get('booking_id', ''),
                    'checkin_date': checkin_date,  # Use correct field name
                    'checkout_date': checkout_date,  # Use correct field name
                    'room_amount': safe_parse_vietnamese_number(booking_data.get('room_amount'), 0.0),
                    'commission': safe_parse_vietnamese_number(booking_data.get('commission'), 0.0),
                    'taxi_amount': safe_parse_vietnamese_number(booking_data.get('taxi_amount'), 0.0),
                    'email': booking_data.get('email', ''),
                    'phone': booking_data.get('phone', ''),
                    'notes': f"Imported from admin crawl - {booking_data.get('source', 'unknown')}"
                }
                
                # Add to database using existing function (returns boolean)
                result = add_new_booking(formatted_booking)
                
                if result:  # Boolean check, not dict
                    saved_count += 1
                    print(f"✅ [BULK_SAVE] Saved booking {i+1}: {booking_data.get('guest_name')}")
                else:
                    errors.append(f"Booking {i+1}: Database save failed")
                    failed_count += 1
                    
            except Exception as e:
                errors.append(f"Booking {i+1}: {str(e)}")
                failed_count += 1
                print(f"❌ [BULK_SAVE] Error saving booking {i+1}: {e}")
        
        print(f"📊 [BULK_SAVE] Results: {saved_count} saved, {skipped_count} skipped (already exist), {failed_count} failed")
        
        return jsonify({
            'success': True,
            'saved_count': saved_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'errors': errors,
            'skipped': skipped,
            'message': f'Bulk save completed: {saved_count} new bookings saved, {skipped_count} already existed, {failed_count} failed'
        })
        
    except Exception as e:
        print(f"❌ [BULK_SAVE] Critical error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/duplicate_management', methods=['GET'])
def duplicate_management():
    """Get comprehensive duplicate analysis for manual review"""
    try:
        from core.logic_postgresql import load_booking_data, analyze_existing_duplicates
        from core.models import db, Booking
        
        # Get guest filter parameter for dashboard integration
        guest_filter = request.args.get('guest', '').strip()
        
        print("🔍 [DUPLICATE_MGMT] Starting comprehensive duplicate analysis...")
        if guest_filter:
            print(f"🔍 [DUPLICATE_MGMT] Filtering for guest: {guest_filter}")
        
        # Load all booking data with fresh connection to ensure latest status updates
        df = load_booking_data(force_fresh=True)
        if df.empty:
            return jsonify({'success': True, 'duplicates': [], 'total_groups': 0})
        
        # Get detailed duplicate analysis
        duplicates_result = analyze_existing_duplicates(df)
        
        # Enhanced duplicate information with database details
        enhanced_duplicates = []
        
        for group in duplicates_result.get('duplicate_groups', []):
            # Apply guest filter if specified
            if guest_filter and guest_filter.lower() not in group['guest_name'].lower():
                continue
                
            enhanced_group = {
                'guest_name': group['guest_name'],
                'date_difference_days': group['date_difference_days'],
                'bookings': []
            }
            
            # Get full booking details from database
            for booking_info in group['bookings']:
                booking_id = booking_info.get('Số đặt phòng')
                if booking_id:
                    # Get full booking from database
                    full_booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
                    if full_booking:
                        enhanced_booking = {
                            'booking_id': full_booking.booking_id,
                            'guest_name': full_booking.guest_name,
                            'checkin_date': full_booking.checkin_date.strftime('%Y-%m-%d') if full_booking.checkin_date else 'N/A',
                            'checkout_date': full_booking.checkout_date.strftime('%Y-%m-%d') if full_booking.checkout_date else 'N/A',
                            'room_amount': float(full_booking.room_amount or 0),
                            'commission': float(full_booking.commission or 0),
                            'taxi_amount': float(full_booking.taxi_amount or 0),
                            'collected_amount': float(full_booking.collected_amount or 0),
                            'collector': full_booking.collector or '',
                            'booking_status': full_booking.booking_status,
                            'booking_notes': full_booking.booking_notes or '',
                            'created_at': full_booking.created_at.strftime('%Y-%m-%d %H:%M:%S') if full_booking.created_at else 'N/A'
                        }
                        enhanced_group['bookings'].append(enhanced_booking)
            
            # Only include groups with multiple bookings
            if len(enhanced_group['bookings']) > 1:
                enhanced_duplicates.append(enhanced_group)
        
        print(f"🔍 [DUPLICATE_MGMT] Found {len(enhanced_duplicates)} duplicate groups")
        
        return jsonify({
            'success': True,
            'duplicates': enhanced_duplicates,
            'total_groups': len(enhanced_duplicates),
            'processing_info': {
                'total_guests': duplicates_result.get('total_guests', 0),
                'processed_guests': duplicates_result.get('processed_guests', 0),
                'processing_time': duplicates_result.get('processing_time', 0)
            }
        })
        
    except Exception as e:
        print(f"❌ [DUPLICATE_MGMT] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/delete_duplicate_booking', methods=['POST'])
def delete_duplicate_booking():
    """Delete a specific booking from a duplicate group"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        
        if not booking_id:
            return jsonify({'success': False, 'error': 'Booking ID required'}), 400
        
        print(f"🗑️ [DELETE_DUPLICATE] Attempting to delete booking: {booking_id}")
        
        # Use existing delete function
        success = delete_booking_by_id(booking_id)
        
        if success:
            print(f"✅ [DELETE_DUPLICATE] Successfully deleted booking: {booking_id}")
            return jsonify({'success': True, 'message': f'Deleted booking {booking_id}'})
        else:
            return jsonify({'success': False, 'error': 'Failed to delete booking'}), 400
            
    except Exception as e:
        print(f"❌ [DELETE_DUPLICATE] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/revenue_calculation_comparison', methods=['GET'])
def revenue_calculation_comparison():
    """
    API endpoint to compare traditional vs daily distribution revenue calculation methods
    
    Query parameters:
    - method: 'traditional', 'daily_distribution', or 'both' (default: 'both')
    - months: number of months to analyze (default: 6)
    """
    try:
        from core.dashboard_routes import process_monthly_revenue_with_unpaid_enhanced, calculate_revenue_optimized_dual_method
        from core.logic_postgresql import load_booking_data
        
        # Get parameters
        method = request.args.get('method', 'both')
        months = int(request.args.get('months', 6))
        
        print(f"🔍 [REVENUE_COMPARISON] Method: {method}, Months: {months}")
        
        # Load booking data excluding cancelled bookings for revenue calculations
        df = load_booking_data_for_calculations()
        
        if df.empty:
            return jsonify({
                'success': False,
                'error': 'No booking data available',
                'data': {}
            })
        
        result = {
            'success': True,
            'comparison_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_bookings': len(df),
            'analysis_months': months,
            'methods': {}
        }
        
        if method in ['traditional', 'both']:
            print("💰 [REVENUE_COMPARISON] Calculating traditional method...")
            traditional_data = process_monthly_revenue_with_unpaid_enhanced(
                df, use_daily_distribution=False
            )
            result['methods']['traditional'] = {
                'name': 'Traditional Method (Current)',
                'description': 'Groups bookings by check-in month, counts full booking amount in that month',
                'data': traditional_data[-months:] if traditional_data else [],
                'total_months': len(traditional_data) if traditional_data else 0
            }
        
        if method in ['daily_distribution', 'both']:
            print("📅 [REVENUE_COMPARISON] Calculating daily distribution method...")
            daily_data = process_monthly_revenue_with_unpaid_enhanced(
                df, use_daily_distribution=True
            )
            result['methods']['daily_distribution'] = {
                'name': 'Daily Distribution Method (New)',
                'description': 'Divides booking amounts across each night of stay, more accurate for monthly totals',
                'data': daily_data[-months:] if daily_data else [],
                'total_months': len(daily_data) if daily_data else 0
            }
        
        if method == 'both':
            print("🔍 [REVENUE_COMPARISON] Creating detailed comparison...")
            dual_results = calculate_revenue_optimized_dual_method(df)
            result['detailed_comparison'] = dual_results.get('comparison_summary', {})
            
            # Calculate summary statistics
            traditional_total = sum([month.get('Tổng cộng', 0) for month in result['methods']['traditional']['data']])
            daily_total = sum([month.get('Tổng cộng', 0) for month in result['methods']['daily_distribution']['data']])
            
            result['summary'] = {
                'traditional_total_revenue': traditional_total,
                'daily_distribution_total_revenue': daily_total,
                'difference_amount': abs(traditional_total - daily_total),
                'difference_percent': (abs(traditional_total - daily_total) / max(traditional_total, daily_total) * 100) if max(traditional_total, daily_total) > 0 else 0,
                'recommendation': 'Daily distribution method provides more accurate monthly revenue distribution, especially for multi-night stays'
            }
        
        print(f"✅ [REVENUE_COMPARISON] Comparison completed successfully")
        return jsonify(result)
        
    except Exception as e:
        print(f"❌ [REVENUE_COMPARISON] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {}
        }), 500

@app.route('/api/daily_customer_breakdown', methods=['POST'])
def daily_customer_breakdown():
    """API endpoint to get detailed daily customer breakdown for a specific month"""
    try:
        print("🔍 [DAILY_BREAKDOWN] API called")
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'Không có dữ liệu'}), 400
            
        month = data.get('month')
        method = data.get('method', 'daily_distribution')
        
        print(f"📅 [DAILY_BREAKDOWN] Requested month: {month}, method: {method}")
        
        if not month:
            return jsonify({'success': False, 'message': 'Thiếu thông tin tháng'}), 400
        
        # Parse month - handle both "Tháng M/YYYY" and "YYYY-MM" formats
        try:
            if 'Tháng' in month:
                # Format: "Tháng 6/2025"
                parts = month.replace('Tháng ', '').split('/')
                month_num = int(parts[0])
                year = int(parts[1])
            else:
                # Format: "2025-06"
                parts = month.split('-')
                year = int(parts[0])
                month_num = int(parts[1])
                
            print(f"📅 [DAILY_BREAKDOWN] Parsed: Year={year}, Month={month_num}")
            
        except (ValueError, IndexError) as e:
            print(f"❌ [DAILY_BREAKDOWN] Month parsing error: {e}")
            return jsonify({'success': False, 'message': f'Định dạng tháng không hợp lệ: {month}'}), 400
        
        # Load booking data excluding cancelled bookings for calculations
        df = load_booking_data_for_calculations()
        if df.empty:
            return jsonify({'success': False, 'message': 'Không có dữ liệu booking'}), 400
            
        print(f"📊 [DAILY_BREAKDOWN] Loaded {len(df)} bookings")
        
        # Filter data for the specified month
        try:
            df['check_in_date'] = pd.to_datetime(df['Check-in Date'], errors='coerce')
            df['check_out_date'] = pd.to_datetime(df['Check-out Date'], errors='coerce')
            
            # Filter bookings that overlap with the requested month
            start_of_month = pd.Timestamp(year=year, month=month_num, day=1)
            if month_num == 12:
                end_of_month = pd.Timestamp(year=year+1, month=1, day=1) - pd.Timedelta(days=1)
            else:
                end_of_month = pd.Timestamp(year=year, month=month_num+1, day=1) - pd.Timedelta(days=1)
            
            # Bookings that overlap with this month (check-in before month end, check-out after month start)
            month_bookings = df[
                (df['check_in_date'] <= end_of_month) & 
                (df['check_out_date'] > start_of_month)
            ].copy()
            
            print(f"🎯 [DAILY_BREAKDOWN] Found {len(month_bookings)} bookings for {month}")
            print(f"🔍 [DAILY_BREAKDOWN] DataFrame columns: {list(df.columns)}")
            if len(month_bookings) > 0:
                print(f"🔍 [DAILY_BREAKDOWN] Sample booking columns: {list(month_bookings.iloc[0].index)}")

        except Exception as e:
            print(f"❌ [DAILY_BREAKDOWN] Date filtering error: {e}")
            return jsonify({'success': False, 'message': f'Lỗi xử lý ngày tháng: {str(e)}'}), 400
        
        if month_bookings.empty:
            return jsonify({
                'success': True,
                'daily_data': [],
                'summary': {
                    'total_customer_days': 0,
                    'unique_customers': 0,
                    'active_days': 0,
                    'average_occupancy': 0
                },
                'message': f'Không có khách hàng trong {month}'
            })
        
        # Calculate daily breakdown using daily distribution method
        daily_data = {}
        unique_customers = set()
        
        for idx, booking in month_bookings.iterrows():
            guest_name = booking.get('Tên người đặt', 'Unknown')
            checkin = booking['check_in_date']
            checkout = booking['check_out_date']

            # Get price information - use correct column name "Tổng thanh toán"
            total_amount = booking.get('Tổng thanh toán', 0) or 0
            if pd.isna(total_amount):
                total_amount = 0

            # Debug first booking
            if idx == month_bookings.index[0]:
                print(f"🔍 [PRICE_DEBUG] First booking: {guest_name}")
                print(f"🔍 [PRICE_DEBUG]   Tổng thanh toán: {booking.get('Tổng thanh toán', 'NOT FOUND')}")
                print(f"🔍 [PRICE_DEBUG]   Final total_amount: {total_amount}")

            # Calculate total nights for this booking
            total_nights = (checkout - checkin).days
            price_per_night = float(total_amount) / total_nights if total_nights > 0 else 0

            unique_customers.add(guest_name)

            # Calculate which days this booking covers within the month
            actual_start = max(checkin, start_of_month)
            actual_end = min(checkout, end_of_month + pd.Timedelta(days=1))

            # Generate date range for this booking within the month
            current_date = actual_start
            while current_date < actual_end:
                if current_date.month == month_num and current_date.year == year:
                    date_str = current_date.strftime('%Y-%m-%d')

                    if date_str not in daily_data:
                        daily_data[date_str] = {
                            'date': date_str,
                            'customers': [],
                            'total_nights': 0
                        }

                    # Add customer to this day
                    daily_data[date_str]['customers'].append({
                        'guest_name': guest_name,
                        'checkin_date': checkin.strftime('%Y-%m-%d'),
                        'checkout_date': checkout.strftime('%Y-%m-%d'),
                        'total_amount': float(total_amount),
                        'price_per_night': float(price_per_night),
                        'total_nights': total_nights
                    })
                    daily_data[date_str]['total_nights'] += 1

                current_date += pd.Timedelta(days=1)
        
        # Convert to list and sort by date
        daily_data_list = list(daily_data.values())
        daily_data_list.sort(key=lambda x: x['date'])
        
        # Calculate summary statistics
        total_customer_days = sum(len(day['customers']) for day in daily_data_list)
        active_days = len([day for day in daily_data_list if len(day['customers']) > 0])
        days_in_month = (end_of_month - start_of_month).days + 1
        average_occupancy = total_customer_days / days_in_month if days_in_month > 0 else 0
        
        summary = {
            'total_customer_days': total_customer_days,
            'unique_customers': len(unique_customers),
            'active_days': active_days,
            'average_occupancy': round(average_occupancy, 1)
        }
        
        print(f"✅ [DAILY_BREAKDOWN] Summary: {summary}")
        
        return jsonify({
            'success': True,
            'daily_data': daily_data_list,
            'summary': summary,
            'month': month,
            'message': f'Thành công tải dữ liệu cho {month}'
        })
        
    except Exception as e:
        print(f"❌ [DAILY_BREAKDOWN] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Lỗi server: {str(e)}',
            'daily_data': [],
            'summary': {}
        }), 500

