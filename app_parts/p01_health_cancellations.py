# p01_health_cancellations — health, cancellations centre, OK status, auto-sync, debug routes
# Part of app.py (lines 612-1426 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/health')
def healthcheck():
    """Railway healthcheck endpoint - returns 200 OK without database access"""
    return jsonify({
        'status': 'healthy',
        'service': 'hotel-booking-system',
        'version': '2.0',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/debug/db-config')
def debug_db_config():
    """Debug endpoint to show database configuration (for troubleshooting only)"""
    import os

    # Get all database-related environment variables
    db_vars = {}
    for key in os.environ.keys():
        if any(keyword in key.upper() for keyword in ['DATABASE', 'POSTGRES', 'DB_', 'RAILWAY']):
            value = os.environ[key]
            # Mask password for security
            if 'URL' in key.upper() or 'PASSWORD' in key.upper():
                if '@' in value:
                    # Show everything except password
                    parts = value.split('@')
                    if '://' in parts[0]:
                        protocol_user = parts[0].split('://')
                        if ':' in protocol_user[1]:
                            user = protocol_user[1].split(':')[0]
                            masked = f"{protocol_user[0]}://{user}:***MASKED***@{parts[1]}"
                        else:
                            masked = value
                    else:
                        masked = value
                else:
                    masked = '***MASKED***'
            else:
                masked = value
            db_vars[key] = masked

    # Get current app configuration
    current_db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'NOT SET')
    if current_db_uri and current_db_uri != 'NOT SET':
        if '@' in current_db_uri:
            parts = current_db_uri.split('@')
            if '://' in parts[0]:
                protocol_user = parts[0].split('://')
                if ':' in protocol_user[1]:
                    user = protocol_user[1].split(':')[0]
                    current_db_uri = f"{protocol_user[0]}://{user}:***MASKED***@{parts[1]}"

    return jsonify({
        'environment_variables': db_vars,
        'current_sqlalchemy_uri': current_db_uri,
        'railway_detected': bool(os.getenv('RAILWAY_ENVIRONMENT_ID') or os.getenv('RAILWAY_PROJECT_ID')),
        'database_source_setting': os.getenv('DATABASE_SOURCE', 'auto')
    }), 200


@app.route('/api/cancellation_notifications')
def api_cancellation_notifications():
    """API endpoint for cancellation notifications"""
    try:
        from core.cancellation_notifications import get_cancellation_notifications
        notifications = get_cancellation_notifications()
        return jsonify({
            'success': True,
            'notifications': notifications,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_CANCELLATION_NOTIFICATIONS] Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'notifications': {'summary': {'total_alerts': 0}}
        }), 500

@app.route('/api/urgent_alerts')
def api_urgent_alerts():
    """API endpoint for urgent cancellation alerts only"""
    try:
        from core.cancellation_notifications import get_urgent_cancellation_alerts
        urgent_alerts = get_urgent_cancellation_alerts()
        return jsonify({
            'success': True,
            'urgent_alerts': urgent_alerts,
            'count': len(urgent_alerts),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_URGENT_ALERTS] Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e),
            'urgent_alerts': []
        }), 500

@app.route('/api/debug_cancellations')
def api_debug_cancellations():
    """Debug endpoint to check cancellation data"""
    try:
        from core.cancellation_notifications import debug_guest_data, get_cancellation_notifications
        from core.models import db, CancellationAction
        
        # Check cancellation_actions table directly
        all_actions = CancellationAction.query.all()
        confirmed_actions = CancellationAction.query.filter_by(action_status='confirmed').all()
        pending_actions = CancellationAction.query.filter_by(action_status='pending').all()
        
        debug_info = debug_guest_data()
        notifications = get_cancellation_notifications()
        
        return jsonify({
            'success': True,
            'debug_info': debug_info,
            'cancellation_actions_table': {
                'total_actions': len(all_actions),
                'confirmed_actions': len(confirmed_actions),
                'pending_actions': len(pending_actions),
                'confirmed_details': [{'booking_id': a.booking_id, 'guest_name': a.guest_name, 'status': a.action_status, 'confirmation_date': a.confirmation_date} for a in confirmed_actions],
                'pending_details': [{'booking_id': a.booking_id, 'guest_name': a.guest_name, 'status': a.action_status} for a in pending_actions[:5]]
            },
            'notifications_summary': notifications['summary'],
            'notifications_detailed': {
                'le_thuong_alerts': len(notifications['specific_guest_alerts']),
                'zero_commission_alerts': len(notifications['zero_commission_alerts']),
                'cancelled_alerts': len(notifications['cancellation_status_alerts'])
            },
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_DEBUG_CANCELLATIONS] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/confirmed_cancellations')
def api_confirmed_cancellations():
    """View history of confirmed cancellation actions - uses debug_database approach"""
    try:
        # Get ALL actions using the EXACT same approach as debug_database (which works)
        from core.models import db, CancellationAction
        
        # Use the exact same query as debug_database endpoint
        all_actions = CancellationAction.query.all()
        
        print(f"✅ [API_CONFIRMED_CANCELLATIONS] Got {len(all_actions)} total actions from database")
        
        # Filter to only confirmed/ok actions (client-side filtering like debug_database does)
        confirmed_list = []
        for action in all_actions:
            if action.action_status in ['confirmed', 'ok']:
                confirmed_list.append({
                    'action_id': action.action_id,
                    'booking_id': action.booking_id,
                    'guest_name': action.guest_name,
                    'cancellation_type': action.cancellation_type,
                    'action_status': action.action_status,
                    'confirmed_by': action.confirmed_by,
                    'confirmation_date': action.confirmation_date.isoformat() if action.confirmation_date else None,
                    'notes': action.notes,
                    'created_at': action.created_at.isoformat() if action.created_at else None
                })
        
        # Sort by confirmation_date descending
        confirmed_list.sort(key=lambda x: x['confirmation_date'] or '1900-01-01', reverse=True)
        
        # Limit to 20 most recent
        confirmed_list = confirmed_list[:20]
        
        print(f"✅ [API_CONFIRMED_CANCELLATIONS] Filtered to {len(confirmed_list)} confirmed actions")
        
        return jsonify({
            'success': True,
            'total_confirmed': len(confirmed_list),
            'confirmed_cancellations': confirmed_list,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_CONFIRMED_CANCELLATIONS] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/canceled_customers_management')
def api_canceled_customers_management():
    """Get ALL canceled customers for re-classification management"""
    try:
        from core.cancellation_notifications import get_all_canceled_customers_for_management
        customers = get_all_canceled_customers_for_management()
        
        # Categorize customers based on real action status
        categorized = {
            'needs_classification': [c for c in customers if c['needs_action']],
            'pending_review': [c for c in customers if c['action_status'] == 'pending'],
            'confirmed': [c for c in customers if c['action_status'] in ['confirmed', 'ok']],
            'all_customers': customers
        }
        
        # Debug categorization
        print(f"🔍 [CATEGORIZATION_DEBUG] Total customers: {len(customers)}")
        print(f"🔍 [CATEGORIZATION_DEBUG] Needs classification: {len(categorized['needs_classification'])}")
        print(f"🔍 [CATEGORIZATION_DEBUG] Pending review: {len(categorized['pending_review'])}")
        print(f"🔍 [CATEGORIZATION_DEBUG] Confirmed: {len(categorized['confirmed'])}")
        
        # Debug sample of each category
        if categorized['needs_classification']:
            sample = categorized['needs_classification'][0]
            print(f"🔍 [NEEDS_ACTION_SAMPLE] {sample['guest_name']} ({sample['booking_id']}): action_status='{sample['action_status']}', needs_action={sample['needs_action']}")
        
        if categorized['confirmed']:
            sample = categorized['confirmed'][0]
            print(f"🔍 [CONFIRMED_SAMPLE] {sample['guest_name']} ({sample['booking_id']}): action_status='{sample['action_status']}', needs_action={sample['needs_action']}")
        
        return jsonify({
            'success': True,
            'total_customers': len(customers),
            'categories': {
                'needs_classification': len(categorized['needs_classification']),
                'pending_review': len(categorized['pending_review']),
                'confirmed': len(categorized['confirmed'])
            },
            'all_customers': customers,
            'needs_classification': categorized['needs_classification'],
            'pending_review': categorized['pending_review'],
            'confirmed': categorized['confirmed'],
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        print(f"❌ [API_CANCELED_CUSTOMERS] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/debug_confirmed_cancellations')
def api_debug_confirmed_cancellations():
    """Debug endpoint specifically for confirmed cancellations"""
    try:
        from core.logic_postgresql import execute_query
        
        # Test simple count query
        count_query = "SELECT COUNT(*) as total FROM cancellation_actions"
        count_result = execute_query(count_query)
        total_actions = count_result.iloc[0]['total'] if not count_result.empty else 0
        
        # Test confirmed/ok query
        confirmed_query = "SELECT COUNT(*) as confirmed_count FROM cancellation_actions WHERE action_status IN ('confirmed', 'ok')"
        confirmed_result = execute_query(confirmed_query)
        confirmed_count = confirmed_result.iloc[0]['confirmed_count'] if not confirmed_result.empty else 0
        
        # Get actual confirmed records
        records_query = """
        SELECT action_id, booking_id, guest_name, action_status, confirmation_date 
        FROM cancellation_actions 
        WHERE action_status IN ('confirmed', 'ok') 
        ORDER BY confirmation_date DESC 
        LIMIT 5
        """
        records_result = execute_query(records_query)
        sample_records = records_result.to_dict('records') if not records_result.empty else []
        
        return jsonify({
            'success': True,
            'total_actions': total_actions,
            'confirmed_count': confirmed_count,
            'sample_confirmed_records': sample_records,
            'debug_info': 'This endpoint tests confirmed cancellations functionality',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'debug_info': 'Error testing confirmed cancellations functionality',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/edit_cancellation', methods=['POST'])
def api_edit_cancellation():
    """Edit existing cancellation action (change status, notes, etc.)"""
    try:
        print(f"🔄 [API_EDIT_CANCELLATION] Request received")
        data = request.get_json()
        print(f"🔍 [API_EDIT_CANCELLATION] Request data: {data}")
        
        action_id = data.get('action_id')
        booking_id = data.get('booking_id')
        new_status = data.get('action_status')  # 'confirmed', 'pending', 'cancelled'
        new_notes = data.get('notes')
        
        print(f"📋 [API_EDIT_CANCELLATION] Params: action_id={action_id}, booking_id={booking_id}, new_status={new_status}")
        
        from core.models import db, CancellationAction
        
        # Find the cancellation action to edit
        action = None
        if action_id and action_id != 'undefined': # Check for 'undefined' string from JS
            try:
                action = CancellationAction.query.get(int(action_id))
            except ValueError:
                print(f"⚠️ [API_EDIT_CANCELLATION] Invalid action_id format: {action_id}")
                action = None
        
        if not action and booking_id:
            action = CancellationAction.query.filter_by(booking_id=booking_id).first()
            print(f"🔍 [API_EDIT_CANCELLATION] Found by booking_id: {action is not None}")
        
        if not action:
            print(f"❌ [API_EDIT_CANCELLATION] No action found for booking_id={booking_id}")
            # If no cancellation action exists and we're trying to set to pending,
            # this means we want to "undo" a confirmation that was already removed
            if new_status == 'pending':
                print(f"✅ [API_EDIT_CANCELLATION] Already undone - returning success")
                return jsonify({
                    'success': True,
                    'message': 'Cancellation already undone - alert will be removed',
                    'action': 'already_undone',
                    'booking_id': booking_id
                })
            else:
                print(f"❌ [API_EDIT_CANCELLATION] Action not found")
                return jsonify({
                    'success': False,
                    'error': f'Cancellation action not found for booking {booking_id}'
                }), 404
        
        # Update fields if provided
        old_status = action.action_status
        print(f"📝 [API_EDIT_CANCELLATION] Current status: {old_status} → {new_status}")
        
        if new_status and new_status != old_status:
            action.action_status = new_status
            if new_status == 'confirmed':
                action.confirmed_by = 'System User'
                action.confirmation_date = datetime.now()
                print(f"✅ [API_EDIT_CANCELLATION] Set to confirmed")
            elif new_status == 'pending':
                action.confirmed_by = None
                action.confirmation_date = None
                print(f"⏳ [API_EDIT_CANCELLATION] Set to pending (undo)")
        
        if new_notes:
            action.notes = new_notes
        
        action.updated_at = datetime.now()
        
        db.session.commit()
        print(f"💾 [API_EDIT_CANCELLATION] Database updated successfully")
        
        print(f"✏️ [EDIT_CANCELLATION] {action.booking_id}: {old_status} → {action.action_status}")
        
        return jsonify({
            'success': True,
            'message': f'Updated cancellation for {action.guest_name} (Status: {old_status} → {action.action_status})',
            'action_id': action.action_id,
            'booking_id': action.booking_id,
            'old_status': old_status,
            'new_status': action.action_status,
            'guest_name': action.guest_name,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_EDIT_CANCELLATION] Error: {e}")
        import traceback
        print(f"❌ [API_EDIT_CANCELLATION] Traceback: {traceback.format_exc()}")
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/delete_cancellation', methods=['POST'])
def api_delete_cancellation():
    """Delete a cancellation action completely"""
    try:
        data = request.get_json()
        action_id = data.get('action_id')
        booking_id = data.get('booking_id')
        
        from core.models import db, CancellationAction
        
        # Find the cancellation action to delete
        if action_id:
            action = CancellationAction.query.get(action_id)
        elif booking_id:
            action = CancellationAction.query.filter_by(booking_id=booking_id).first()
        else:
            return jsonify({
                'success': False,
                'error': 'Must provide either action_id or booking_id'
            }), 400
        
        if not action:
            return jsonify({
                'success': False,
                'error': 'Cancellation action not found'
            }), 404
        
        guest_name = action.guest_name
        booking_id = action.booking_id
        
        db.session.delete(action)
        db.session.commit()
        
        print(f"🗑️ [DELETE_CANCELLATION] Deleted action for {booking_id} - {guest_name}")
        
        return jsonify({
            'success': True,
            'message': f'Deleted cancellation action for {guest_name}',
            'booking_id': booking_id,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_DELETE_CANCELLATION] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/delete_cancellation', methods=['POST'])
def api_delete_cancellation_by_booking():
    """Delete cancellation record by booking_id"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')

        if not booking_id:
            return jsonify({
                'success': False,
                'error': 'Missing booking_id'
            }), 400

        from core.models import db, CancellationAction

        # Find all cancellation records for this booking
        actions = CancellationAction.query.filter_by(booking_id=booking_id).all()

        if not actions:
            return jsonify({
                'success': False,
                'error': 'No cancellation records found'
            }), 404

        # Delete all records
        for action in actions:
            db.session.delete(action)

        db.session.commit()

        # Force cache refresh
        db.engine.dispose()

        return jsonify({
            'success': True,
            'message': f'Deleted {len(actions)} cancellation record(s)',
            'deleted_count': len(actions)
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting cancellation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/confirm_cancellation', methods=['POST'])
def api_confirm_cancellation():
    """Confirm cancellation action and save to database"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        guest_name = data.get('guest_name')
        cancellation_type = data.get('cancellation_type')
        confirmed_by = 'System User'  # You can enhance this with actual user tracking
        
        if not all([booking_id, guest_name, cancellation_type]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Import model
        from core.models import db, CancellationAction
        
        # Check if already confirmed - prevent duplicate confirmations
        existing = CancellationAction.query.filter_by(
            booking_id=booking_id,
            action_status='confirmed'
        ).first()
        
        if existing:
            # Already confirmed - return success without duplicating
            print(f"ℹ️ [ALREADY_CONFIRMED] Booking {booking_id} already confirmed")
            return jsonify({
                'success': True,
                'message': f'Cancellation already confirmed for {guest_name}',
                'action': 'already_confirmed',
                'action_id': existing.action_id
            })
        
        # Also check for ANY existing action (pending/confirmed) and update it
        any_existing = CancellationAction.query.filter_by(booking_id=booking_id).first()
        
        if any_existing:
            # Update existing action to confirmed
            any_existing.action_status = 'confirmed'
            any_existing.confirmed_by = confirmed_by
            any_existing.confirmation_date = datetime.now()
            any_existing.notes = f'Updated to confirmed status for {cancellation_type} guest'
            
            try:
                db.session.commit()
                print(f"🔄 [UPDATE_CONFIRMATION] Updated existing action {any_existing.action_id} to confirmed")
                
                # Force cache refresh by disposing the connection pool
                db.engine.dispose()
                
                return jsonify({
                    'success': True,
                    'message': f'Cancellation confirmed for {guest_name}',
                    'action': 'updated',
                    'action_id': any_existing.action_id,
                    'refresh_required': True
                })
            except Exception as commit_error:
                db.session.rollback()
                print(f"❌ [COMMIT_ERROR] Failed to commit update: {commit_error}")
                return jsonify({
                    'success': False,
                    'error': f'Database commit failed: {str(commit_error)}'
                }), 500
        
        # Create new cancellation action record
        cancellation_action = CancellationAction(
            booking_id=booking_id,
            guest_name=guest_name,
            cancellation_type=cancellation_type,
            action_status='confirmed',
            confirmed_by=confirmed_by,
            confirmation_date=datetime.now(),
            notes=f'Confirmed cancellation on booking app for {cancellation_type} guest'
        )
        
        db.session.add(cancellation_action)
        
        try:
            db.session.commit()
            print(f"✅ [CONFIRM_CANCELLATION] Booking {booking_id} - {guest_name} - {cancellation_type}")
            
            # Force cache refresh by disposing the connection pool
            db.engine.dispose()
            
            return jsonify({
                'success': True,
                'message': f'Cancellation confirmed for {guest_name}',
                'action_id': cancellation_action.action_id,
                'timestamp': datetime.now().isoformat(),
                'refresh_required': True
            })
        except Exception as commit_error:
            db.session.rollback()
            print(f"❌ [COMMIT_ERROR] Failed to commit new action: {commit_error}")
            return jsonify({
                'success': False,
                'error': f'Database commit failed: {str(commit_error)}'
            }), 500
        
    except Exception as e:
        print(f"❌ [API_CONFIRM_CANCELLATION] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/undo_cancellation', methods=['POST'])
def api_undo_cancellation():
    """Undo cancellation confirmation and allow alert to show again"""
    try:
        data = request.get_json()
        action_id = data.get('action_id')
        booking_id = data.get('booking_id')
        guest_name = data.get('guest_name')
        
        if not action_id and not booking_id:
            return jsonify({
                'success': False,
                'error': 'Either action_id or booking_id is required'
            }), 400
        
        # Import model
        from core.models import db, CancellationAction
        
        # Find and delete the cancellation action record
        if action_id:
            cancellation_action = CancellationAction.query.filter_by(action_id=action_id).first()
        else:
            cancellation_action = CancellationAction.query.filter_by(
                booking_id=booking_id,
                action_status='confirmed'
            ).first()
        
        if not cancellation_action:
            return jsonify({
                'success': False,
                'error': 'Cancellation action not found'
            }), 404
        
        # Store info before deletion
        stored_booking_id = cancellation_action.booking_id
        stored_guest_name = cancellation_action.guest_name
        stored_type = cancellation_action.cancellation_type
        
        # Delete the cancellation action record
        db.session.delete(cancellation_action)
        db.session.commit()
        
        print(f"🗑️ [UNDO_CANCELLATION] Deleted action for {stored_guest_name} - {stored_booking_id}")
        print(f"🔄 [UNDO_CANCELLATION] Alert will show again on next page load")
        
        return jsonify({
            'success': True,
            'message': f'Confirmation undone for {stored_guest_name}. Alert will appear on next page load.',
            'booking_id': stored_booking_id,
            'guest_name': stored_guest_name,
            'cancellation_type': stored_type,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_UNDO_CANCELLATION] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/set_ok_status', methods=['POST'])
def api_set_ok_status():
    """Set OK status for a guest (meaning no more cancellation issues)"""
    try:
        data = request.get_json()
        booking_id = data.get('booking_id')
        guest_name = data.get('guest_name')
        cancellation_type = data.get('cancellation_type', 'ok_status')
        confirmed_by = 'System User'  # You can enhance this with actual user tracking
        
        if not all([booking_id, guest_name]):
            return jsonify({
                'success': False,
                'error': 'Missing required fields: booking_id and guest_name'
            }), 400
        
        # Import models
        from core.models import db, CancellationAction, Booking
        
        # CRITICAL: Update booking status to restore full functionality
        booking = Booking.query.filter_by(booking_id=booking_id).first()
        if not booking:
            return jsonify({
                'success': False,
                'error': f'Booking {booking_id} not found'
            }), 404
            
        # Restore booking to confirmed status (enables all features)
        old_status = booking.booking_status
        booking.booking_status = 'confirmed'
        booking.booking_notes = f"{booking.booking_notes or ''} [OK Status: Restored from {old_status}]".strip()
        
        print(f"🔄 [RESTORE_BOOKING] {booking_id} status: {old_status} → confirmed")
        
        # Check if there's already an action for this booking - update it instead of creating new
        existing = CancellationAction.query.filter_by(
            booking_id=booking_id,
            guest_name=guest_name
        ).first()
        
        if existing:
            # Update existing action to OK status
            existing.cancellation_type = 'ok_status'
            existing.action_status = 'ok'
            existing.confirmed_by = confirmed_by
            existing.confirmation_date = datetime.now()
            existing.notes = f'Guest marked as OK - booking restored to full functionality'
            db.session.commit()
            
            print(f"🔄 [UPDATE_OK_STATUS] Updated existing action {existing.action_id} to OK status")
            return jsonify({
                'success': True,
                'message': f'{guest_name} restored to full functionality - booking status: {old_status} → confirmed',
                'action': 'updated',
                'action_id': existing.action_id,
                'booking_status_change': f'{old_status} → confirmed'
            })
        
        # Create new OK status record
        ok_action = CancellationAction(
            booking_id=booking_id,
            guest_name=guest_name,
            cancellation_type='ok_status',
            action_status='ok',
            confirmed_by=confirmed_by,
            confirmation_date=datetime.now(),
            notes=f'Guest marked as OK - booking restored to full functionality from {old_status}'
        )
        
        db.session.add(ok_action)
        db.session.commit()
        
        print(f"✅ [SET_OK_STATUS] Booking {booking_id} - {guest_name} - restored to full functionality")
        
        return jsonify({
            'success': True,
            'message': f'{guest_name} restored to full functionality - booking status: {old_status} → confirmed',
            'action_id': ok_action.action_id,
            'booking_status_change': f'{old_status} → confirmed',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        print(f"❌ [API_SET_OK_STATUS] Error: {e}")
        import traceback
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500



