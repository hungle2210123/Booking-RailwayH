# p08_collect_history_import — collect payment, commission status, guest amounts, booking history, Excel/JSON import, check-in status sync
# Part of app.py (lines 9613-11163 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/api/collect_payment', methods=['POST'])
def collect_payment():
    """API endpoint để thu tiền từ khách hàng - PostgreSQL version"""
    try:
        print("🚀 [COLLECT_PAYMENT] API CALLED - Starting payment collection")
        data = request.get_json()
        print(f"🔍 [COLLECT_PAYMENT] Raw request data: {data}")
        
        if not data:
            return jsonify({'success': False, 'message': 'Không có dữ liệu'}), 400
        
        booking_id = data.get('booking_id')
        collected_amount = data.get('collected_amount')
        collector_name = data.get('collector_name')
        payment_note = data.get('payment_note', '')
        payment_type = data.get('payment_type', 'room')  # 'room' hoặc 'taxi'
        taxi_amount = data.get('taxi_amount')  # ADDED: Taxi amount for database update
        commission_amount = data.get('commission_amount', 0)
        commission_type = data.get('commission_type', 'normal')  # 'normal' hoặc 'none'
        commission_status = data.get('commission_status', 'pending')  # NEW: 'pending', 'confirmed', 'cancelled'
        
        print(f"[COLLECT_PAYMENT] 🎯 EXTRACTED VALUES:")
        print(f"[COLLECT_PAYMENT]   - booking_id: '{booking_id}'")
        print(f"[COLLECT_PAYMENT]   - collected_amount: {collected_amount} ({type(collected_amount)})")
        print(f"[COLLECT_PAYMENT]   - collector_name: '{collector_name}'")
        print(f"[COLLECT_PAYMENT]   - payment_note: '{payment_note}'")
        print(f"[COLLECT_PAYMENT]   - payment_type: '{payment_type}' ⭐ CRITICAL ⭐")
        print(f"[COLLECT_PAYMENT]   - taxi_amount: {taxi_amount} 🚕 NEW")
        print(f"[COLLECT_PAYMENT]   - commission_amount: {commission_amount}")
        print(f"[COLLECT_PAYMENT]   - commission_type: '{commission_type}'")
        print(f"[COLLECT_PAYMENT]   - commission_status: '{commission_status}' 🆕 NEW")
        
        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Thiếu mã đặt phòng'}), 400
            
        if not collector_name:
            return jsonify({'success': False, 'message': 'Thiếu tên người thu tiền'}), 400
        
        # CRITICAL: Only allow valid collectors (except for system cancellations)
        valid_collectors = ['LOC LE', 'THAO LE', 'SYSTEM']
        if collector_name not in valid_collectors:
            return jsonify({'success': False, 'message': f'Người thu tiền không hợp lệ. Chỉ chấp nhận: {", ".join(valid_collectors)}'}), 400

        # Allow 0 collected_amount for cancellation requests (when collector is SYSTEM)
        if collector_name != 'SYSTEM':
            if not collected_amount or collected_amount <= 0:
                return jsonify({'success': False, 'message': 'Số tiền thu không hợp lệ'}), 400
        
        # Prepare update data for PostgreSQL
        update_data = {}
        
        # Update commission based on commission type - FIXED LOGIC
        if commission_type == 'none':
            update_data['commission'] = 0
            print("[COLLECT_PAYMENT] Setting commission to 0 (no commission)")
        elif 'commission_amount' in data and commission_amount is not None:  # only when the caller sent one (the calendar's Thu tiền does not)
            update_data['commission'] = float(commission_amount)
            print(f"[COLLECT_PAYMENT] Setting commission to {commission_amount}")
        else:
            print(f"[COLLECT_PAYMENT] ⚠️ No commission update - amount is None")
        
        # ALWAYS update collector AND collected_amount for both taxi and room payments
        update_data['collector'] = collector_name

        # 💰 CUMULATIVE: Add new payment to existing collected_amount (don't overwrite)
        from core.models import Booking as _BookingModel
        existing_booking = _BookingModel.query.get(booking_id)
        existing_collected = float(existing_booking.collected_amount or 0) if existing_booking else 0
        _room = float(existing_booking.room_amount or 0) if existing_booking else 0
        if (payment_type != 'taxi' and collector_name != 'SYSTEM' and _room > 0 and existing_collected >= _room - 1000
                and abs(float(collected_amount or 0) - _room) <= 1000 and not data.get('allow_duplicate')):
            # the same full amount again on a booking already paid = a double tap (Philippe / Chiara were counted twice)
            return jsonify({'success': False, 'duplicate': True,
                            'message': f'⚠️ Khách này đã thu đủ {existing_collected:,.0f}đ — không ghi thêm lần nữa (tránh thu trùng). '
                                       f'Cần sửa số tiền thì dùng Sửa booking.'}), 409
        total_collected = existing_collected + float(collected_amount)
        update_data['collected_amount'] = total_collected
        print(f"[COLLECT_PAYMENT] 💰 Cumulative collected: {existing_collected} + {collected_amount} = {total_collected}")
        print(f"[COLLECT_PAYMENT] ✅ Valid collector confirmed: {collector_name}")

        # 🆕 UPDATE commission_status based on commission decision
        valid_commission_statuses = ['pending', 'confirmed', 'cancelled']
        if 'commission_status' in data and commission_status in valid_commission_statuses:
            update_data['commission_status'] = commission_status
            print(f"[COLLECT_PAYMENT] 🆕 Setting commission_status to: {commission_status}")
        else:
            print(f"[COLLECT_PAYMENT] ⚠️ Invalid commission_status '{commission_status}', keeping as 'pending'")
        
        # 🚕 ALWAYS UPDATE TAXI AMOUNT if provided (regardless of payment type)
        if taxi_amount is not None and taxi_amount >= 0:
            update_data['taxi_amount'] = float(taxi_amount)
            print(f"[COLLECT_PAYMENT] 🚕 Setting taxi_amount in DB to: {taxi_amount}")
        
        # 📝 CREATE APPROPRIATE NOTES based on payment type
        if payment_type == 'taxi':
            # Primary taxi payment
            if payment_note:
                update_data['booking_notes'] = f"Thu taxi {collected_amount:,.0f}đ (taxi: {taxi_amount:,.0f}đ) - {payment_note}"
            else:
                update_data['booking_notes'] = f"Thu taxi {collected_amount:,.0f}đ (taxi fee: {taxi_amount:,.0f}đ)"
            print(f"[COLLECT_PAYMENT] ✅ Taxi payment - collected: {collected_amount}, taxi_amount: {taxi_amount}, collector: {collector_name}")
        else:
            # Room payment (but may include taxi amount update)
            taxi_note = f" (taxi: {taxi_amount:,.0f}đ)" if taxi_amount and taxi_amount > 0 else ""
            if payment_note:
                update_data['booking_notes'] = f"Thu {collected_amount:,.0f}đ{taxi_note} - {payment_note}"
            else:
                update_data['booking_notes'] = f"Thu {collected_amount:,.0f}đ{taxi_note}"
            print(f"[COLLECT_PAYMENT] ✅ Room payment - collected: {collected_amount}, taxi_amount: {taxi_amount}, collector: {collector_name}")
        
        print(f"[COLLECT_PAYMENT] 📊 Final update_data: {update_data}")

        # Update booking using the update_booking function
        record_booking_history(booking_id, update_data, changed_by='collect_payment')
        success = update_booking(booking_id, update_data)
        
        if success:
            print(f"[COLLECT_PAYMENT] Successfully updated booking {booking_id}")
            
            # Cache removed - data will be fresh automatically
            
            commission_msg = ""
            if commission_type == 'none':
                commission_msg = " (Không có hoa hồng)"
            elif commission_amount and commission_amount > 0:
                commission_msg = f" (Hoa hồng: {commission_amount:,.0f}đ)"
            
            # Create detailed success message with all updates
            updates = []
            updates.append(f"Thu: {collected_amount:,.0f}đ")
            if commission_amount is not None and commission_amount >= 0:
                updates.append(f"Hoa hồng: {commission_amount:,.0f}đ")
            if taxi_amount is not None and taxi_amount >= 0:
                updates.append(f"Taxi: {taxi_amount:,.0f}đ")
            
            update_summary = ", ".join(updates)
            
            if payment_type == 'taxi':
                return jsonify({
                    'success': True,
                    'message': f'✅ Thu taxi thành công! {update_summary}',
                    'commission_status': commission_status,  # 🆕 For instant UX feedback
                    'refresh_bookings': True,  # 🔄 Signal to refresh booking management
                    'updated_data': {
                        'collected_amount': collected_amount,
                        'commission_amount': commission_amount,
                        'taxi_amount': taxi_amount,
                        'booking_id': booking_id
                    }
                })
            else:
                return jsonify({
                    'success': True,
                    'message': f'✅ Thu tiền thành công! {update_summary}',
                    'commission_status': commission_status,
                    'new_collected': total_collected,  # Cumulative total collected
                    'refresh_bookings': True,
                    'updated_data': {
                        'collected_amount': total_collected,
                        'commission_amount': commission_amount,
                        'taxi_amount': taxi_amount,
                        'booking_id': booking_id,
                        'commission_status': commission_status
                    }
                })
        else:
            print(f"[COLLECT_PAYMENT] Failed to update booking {booking_id}")
            return jsonify({
                'success': False,
                'message': f'Lỗi cập nhật booking {booking_id}. Vui lòng thử lại.'
            }), 500

    except Exception as e:
        print(f"❌ [COLLECT_PAYMENT] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Lỗi hệ thống: {str(e)}'}), 500

@app.route('/api/update_commission_status', methods=['POST'])
def update_commission_status():
    """API endpoint to update commission status (pending/confirmed/cancelled)"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'success': False, 'message': 'Không có dữ liệu'}), 400

        booking_id = data.get('booking_id')
        commission_status = data.get('commission_status')

        print(f"[UPDATE_COMMISSION] Received request:")
        print(f"  - booking_id: {booking_id}")
        print(f"  - commission_status: {commission_status}")

        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Thiếu mã đặt phòng'}), 400

        if commission_status not in ['pending', 'confirmed', 'cancelled']:
            return jsonify({'success': False, 'message': 'Trạng thái hoa hồng không hợp lệ'}), 400

        # Update database using existing update_booking function
        update_data = {
            'commission_status': commission_status
        }

        # ⚠️ CRITICAL: When cancelling commission, set commission amount to 0
        if commission_status == 'cancelled':
            update_data['commission'] = 0
            print(f"[UPDATE_COMMISSION] ⚠️ Setting commission to 0 (cancelled)")

        record_booking_history(booking_id, update_data, changed_by='commission_update')
        success = update_booking(booking_id, update_data)

        if success:
            status_text = {
                'pending': 'Chờ quyết định',
                'confirmed': 'Đã xác nhận',
                'cancelled': 'Đã hủy'
            }[commission_status]

            print(f"[UPDATE_COMMISSION] ✅ Successfully updated to: {status_text}")

            return jsonify({
                'success': True,
                'message': f'Đã cập nhật trạng thái hoa hồng: {status_text}',
                'commission_status': commission_status
            })
        else:
            print(f"[UPDATE_COMMISSION] ❌ Failed to update booking {booking_id}")
            return jsonify({
                'success': False,
                'message': 'Không thể cập nhật trạng thái hoa hồng'
            }), 500

    except Exception as e:
        print(f"❌ [UPDATE_COMMISSION] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Lỗi hệ thống: {str(e)}'}), 500

@app.route('/api/confirm_no_cancellation', methods=['POST'])
def confirm_no_cancellation():
    """
    🆕 NEW ENDPOINT: Confirm that commission will NOT be cancelled.

    This endpoint allows marking a booking's commission_status as 'confirmed',
    indicating that the commission will be kept (not cancelled).

    Used when:
    - User collects payment and confirms commission should stay
    - User wants to finalize commission decision without immediate payment

    Request JSON:
    {
        "booking_id": "BK12345",
        "confirmed_by": "LOC LE" or "THAO LE"
    }

    Response:
    {
        "success": true,
        "message": "✅ Đã xác nhận giữ hoa hồng"
    }
    """
    try:
        data = request.get_json()
        print(f"🔍 [CONFIRM_NO_CANCELLATION] Request data: {data}")

        if not data:
            return jsonify({'success': False, 'message': 'Không có dữ liệu'}), 400

        booking_id = data.get('booking_id')
        confirmed_by = data.get('confirmed_by')

        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Thiếu mã đặt phòng'}), 400

        if not confirmed_by:
            return jsonify({'success': False, 'message': 'Thiếu thông tin người xác nhận'}), 400

        # Only allow valid collectors to confirm
        valid_confirmers = ['LOC LE', 'THAO LE']
        if confirmed_by not in valid_confirmers:
            return jsonify({'success': False, 'message': f'Người xác nhận không hợp lệ. Chỉ chấp nhận: {", ".join(valid_confirmers)}'}), 400

        # Update commission_status to 'confirmed'
        update_data = {
            'commission_status': 'confirmed'
        }

        print(f"[CONFIRM_NO_CANCELLATION] Setting commission_status='confirmed' for booking {booking_id}")

        record_booking_history(booking_id, update_data, changed_by='commission_update')
        success = update_booking(booking_id, update_data)

        if success:
            print(f"[CONFIRM_NO_CANCELLATION] Successfully confirmed commission for booking {booking_id}")
            return jsonify({
                'success': True,
                'message': '✅ Đã xác nhận giữ hoa hồng',
                'refresh_bookings': True
            })
        else:
            print(f"[CONFIRM_NO_CANCELLATION] Failed to update booking {booking_id}")
            return jsonify({
                'success': False,
                'message': f'Lỗi cập nhật booking {booking_id}. Vui lòng thử lại.'
            }), 500

    except Exception as e:
        print(f"[COLLECT_PAYMENT] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False, 
            'message': f'Lỗi server: {str(e)}'
        }), 500

@app.route('/api/update_guest_amounts', methods=['POST'])
def update_guest_amounts():
    """Update room and taxi amounts for a booking"""
    try:
        data = request.get_json()
        print(f"[UPDATE_GUEST_AMOUNTS] Received data: {data}")
        
        booking_id = data.get('booking_id')
        room_amount = data.get('room_amount')
        taxi_amount = data.get('taxi_amount')
        commission_amount = data.get('commission_amount')
        commission_type = data.get('commission_type', 'normal')
        edit_note = data.get('edit_note', '')
        accommodation_name = data.get('accommodation_name')
        rooms_occupied = data.get('rooms_occupied')

        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Missing booking ID'}), 400

        # Prepare update data
        update_data = {}

        if room_amount is not None:
            update_data['room_amount'] = float(room_amount)
            print(f"[UPDATE_GUEST_AMOUNTS] Setting room_amount to {room_amount}")

        if taxi_amount is not None:
            update_data['taxi_amount'] = float(taxi_amount)
            print(f"[UPDATE_GUEST_AMOUNTS] Setting taxi_amount to {taxi_amount}")

        if accommodation_name is not None:
            update_data['accommodation_name'] = accommodation_name
            print(f"[UPDATE_GUEST_AMOUNTS] Setting accommodation_name to {accommodation_name}")

        if rooms_occupied is not None:
            update_data['rooms_occupied'] = int(rooms_occupied)
            print(f"[UPDATE_GUEST_AMOUNTS] Setting rooms_occupied to {rooms_occupied}")
            
        # Handle commission updates
        if commission_amount is not None:
            if commission_type == 'none':
                update_data['commission'] = 0
                print(f"[UPDATE_GUEST_AMOUNTS] Setting commission to 0 (no commission)")
            else:
                update_data['commission'] = float(commission_amount)
                print(f"[UPDATE_GUEST_AMOUNTS] Setting commission to {commission_amount}")
        else:
            print(f"[UPDATE_GUEST_AMOUNTS] Commission not modified - keeping existing value")
            
        if edit_note:
            update_data['booking_notes'] = edit_note
            print(f"[UPDATE_GUEST_AMOUNTS] Setting notes to: {edit_note}")
        
        print(f"[UPDATE_GUEST_AMOUNTS] Final update_data: {update_data}")

        # Update the booking using core logic
        record_booking_history(booking_id, update_data, changed_by='edit_amounts')
        success = update_booking(booking_id, update_data)
        
        if success:
            print(f"[UPDATE_GUEST_AMOUNTS] Successfully updated {booking_id}")
            return jsonify({
                'success': True,
                'message': f'Successfully updated amounts for {booking_id}'
            })
        else:
            print(f"[UPDATE_GUEST_AMOUNTS] Failed to update {booking_id}")
            return jsonify({
                'success': False,
                'message': f'Failed to update booking {booking_id}'
            }), 500
            
    except Exception as e:
        print(f"[UPDATE_GUEST_AMOUNTS] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

def record_booking_history(booking_id, update_data, changed_by='system'):
    """Record field-level changes to a booking into booking_history table."""
    try:
        from core.models import db, Booking, BookingHistory
        from decimal import Decimal
        import sqlalchemy

        # Auto-create table if not exists (safety for Railway first deploy)
        try:
            BookingHistory.__table__.create(db.engine, checkfirst=True)
        except Exception:
            pass

        booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        if not booking:
            return

        field_labels = {
            'guest_name': 'Tên khách',
            'accommodation_name': 'Phòng',
            'rooms_occupied': 'Số phòng',
            'checkin_date': 'Ngày check-in',
            'checkout_date': 'Ngày check-out',
            'room_amount': 'Tiền phòng',
            'taxi_amount': 'Tiền taxi',
            'commission': 'Hoa hồng',
            'collected_amount': 'Số tiền đã thu',
            'collector': 'Người thu tiền',
            'commission_status': 'Trạng thái hoa hồng',
            'booking_status': 'Trạng thái booking',
            'booking_notes': 'Ghi chú',
            'notes': 'Ghi chú',        # alias used in edit_booking form
            'room_type': 'Phòng',      # alias used in quick_update
            'status': 'Trạng thái booking',  # alias used in edit_booking form
        }
        # Fields that don't exist on Booking model → map to correct attribute
        field_alias = {
            'notes': 'booking_notes',
            'room_type': 'accommodation_name',
            'status': 'booking_status',
        }

        def normalize(val):
            """Convert to float-rounded string for numeric comparison."""
            if val is None:
                return ''
            if isinstance(val, Decimal):
                return str(round(float(val), 2))
            if isinstance(val, float):
                return str(round(val, 2))
            return str(val).strip()

        added = 0
        for field, new_val in update_data.items():
            db_field = field_alias.get(field, field)
            old_val = getattr(booking, db_field, None)

            old_str = normalize(old_val)
            new_str = normalize(new_val)

            if old_str == new_str:
                continue

            label = field_labels.get(field, field)
            entry = BookingHistory(
                booking_id=booking_id,
                field_name=label,
                old_value=old_str,
                new_value=new_str,
                change_description=f"{label}: [{old_str}] → [{new_str}]",
                changed_by=changed_by,
            )
            db.session.add(entry)
            added += 1

        if added:
            db.session.commit()
            print(f"[HISTORY] Recorded {added} change(s) for {booking_id} by {changed_by}")
    except Exception as e:
        print(f"[HISTORY] Failed to record history for {booking_id}: {e}")
        import traceback
        traceback.print_exc()
        try:
            db.session.rollback()
        except Exception:
            pass


@app.route('/api/history/all', methods=['GET'])
def get_all_history():
    """Get all booking history across all bookings, newest first."""
    try:
        from core.models import db, BookingHistory, Booking
        limit = min(int(request.args.get('limit', 200)), 500)

        entries = (db.session.query(BookingHistory)
                   .order_by(BookingHistory.created_at.desc())
                   .limit(limit)
                   .all())

        # Build a quick lookup for guest names
        booking_ids = list({e.booking_id for e in entries})
        bookings = db.session.query(Booking.booking_id, Booking.guest_name).filter(
            Booking.booking_id.in_(booking_ids)
        ).all()
        name_map = {b.booking_id: b.guest_name for b in bookings}

        result = []
        for e in entries:
            d = e.to_dict()
            d['guest_name'] = name_map.get(e.booking_id, '')
            result.append(d)

        return jsonify({'success': True, 'history': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/booking/<booking_id>/history', methods=['GET'])
def get_booking_history(booking_id):
    """Get edit history for a booking."""
    try:
        from core.models import db, BookingHistory
        entries = (db.session.query(BookingHistory)
                   .filter_by(booking_id=booking_id)
                   .order_by(BookingHistory.created_at.desc())
                   .all())
        return jsonify({'success': True, 'history': [e.to_dict() for e in entries]})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/booking_history/<int:history_id>', methods=['DELETE'])
def delete_booking_history(history_id):
    """Delete a history entry — requires password 001022."""
    try:
        from core.models import db, BookingHistory
        data = request.get_json() or {}
        if data.get('password') != '001022':
            return jsonify({'success': False, 'message': 'Mật khẩu không đúng'}), 403

        entry = db.session.query(BookingHistory).filter_by(history_id=history_id).first()
        if not entry:
            return jsonify({'success': False, 'message': 'Không tìm thấy bản ghi'}), 404

        db.session.delete(entry)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Đã xóa bản ghi lịch sử'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/update_booking_comprehensive', methods=['POST'])
def update_booking_comprehensive():
    """Comprehensive update for booking - all editable fields"""
    try:
        data = request.get_json()
        print(f"[UPDATE_BOOKING_COMPREHENSIVE] Received data: {data}")

        booking_id = data.get('booking_id')

        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Missing booking ID'}), 400

        # Prepare update data
        update_data = {}

        # Guest name
        if 'guest_name' in data and data['guest_name']:
            update_data['guest_name'] = data['guest_name'].strip()
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating guest_name to: {update_data['guest_name']}")

        # Accommodation
        if 'accommodation_name' in data:
            update_data['accommodation_name'] = data['accommodation_name']
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating accommodation_name to: {update_data['accommodation_name']}")

        # Rooms occupied
        if 'rooms_occupied' in data:
            update_data['rooms_occupied'] = int(data['rooms_occupied'])
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating rooms_occupied to: {update_data['rooms_occupied']}")

        # Check-in date
        if 'checkin_date' in data and data['checkin_date']:
            from datetime import datetime
            try:
                checkin_date = datetime.strptime(data['checkin_date'], '%Y-%m-%d').date()
                update_data['checkin_date'] = checkin_date
                print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating checkin_date to: {checkin_date}")
            except ValueError as e:
                return jsonify({'success': False, 'message': f'Invalid check-in date format: {str(e)}'}), 400

        # Check-out date
        if 'checkout_date' in data and data['checkout_date']:
            from datetime import datetime
            try:
                checkout_date = datetime.strptime(data['checkout_date'], '%Y-%m-%d').date()
                update_data['checkout_date'] = checkout_date
                print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating checkout_date to: {checkout_date}")
            except ValueError as e:
                return jsonify({'success': False, 'message': f'Invalid check-out date format: {str(e)}'}), 400

        # Financial data
        if 'room_amount' in data:
            update_data['room_amount'] = float(data['room_amount'])
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating room_amount to: {update_data['room_amount']}")

        if 'taxi_amount' in data:
            update_data['taxi_amount'] = float(data['taxi_amount'])
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating taxi_amount to: {update_data['taxi_amount']}")

        if 'commission_amount' in data:
            update_data['commission'] = float(data['commission_amount'])
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating commission to: {update_data['commission']}")

        # Notes
        if 'edit_note' in data and data['edit_note']:
            update_data['booking_notes'] = data['edit_note'].strip()
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Updating notes to: {update_data['booking_notes']}")

        # Validate dates if both provided
        if 'checkin_date' in update_data and 'checkout_date' in update_data:
            if update_data['checkout_date'] <= update_data['checkin_date']:
                return jsonify({'success': False, 'message': 'Check-out date must be after check-in date'}), 400

        print(f"[UPDATE_BOOKING_COMPREHENSIVE] Final update_data: {update_data}")

        # Update the booking using core logic
        record_booking_history(booking_id, update_data, changed_by='edit_form')
        success = update_booking(booking_id, update_data)

        if success:
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Successfully updated {booking_id}")
            return jsonify({
                'success': True,
                'message': f'Successfully updated booking {booking_id}'
            })
        else:
            print(f"[UPDATE_BOOKING_COMPREHENSIVE] Failed to update {booking_id}")
            return jsonify({
                'success': False,
                'message': f'Failed to update booking {booking_id}'
            }), 500

    except Exception as e:
        print(f"[UPDATE_BOOKING_COMPREHENSIVE] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Server error: {str(e)}'
        }), 500

@app.route('/api/update_collected_amount', methods=['POST'])
def update_collected_amount():
    """Update only the collected amount for a booking - ADMIN ONLY"""
    try:
        data = request.get_json()
        print(f"[UPDATE_COLLECTED] 💰 Received data: {data}")
        
        booking_id = data.get('booking_id')
        collected_amount = data.get('collected_amount', 0)
        collector_name = data.get('collector_name', '').strip()
        note = data.get('note', '').strip()
        
        # Validate input
        if not booking_id:
            return jsonify({'success': False, 'message': 'Thiếu mã đặt phòng'}), 400
        
        if collected_amount < 0:
            return jsonify({'success': False, 'message': 'Số tiền không thể âm'}), 400
            
        # CRITICAL: Validate collector
        valid_collectors = ['LOC LE', 'THAO LE']
        if not collector_name:
            return jsonify({'success': False, 'message': 'Vui lòng chọn người thu tiền'}), 400
            
        if collector_name not in valid_collectors:
            return jsonify({'success': False, 'message': f'Người thu tiền không hợp lệ. Chỉ chấp nhận: {", ".join(valid_collectors)}'}), 400
            
        print(f"[UPDATE_COLLECTED] ✅ Valid collector confirmed: {collector_name}")
        
        # 🔒 SECURITY: This is an admin function - should be restricted
        # For now, we'll log it but allow it to proceed
        print(f"[UPDATE_COLLECTED] ⚠️ ADMIN ACTION: Updating collected_amount for {booking_id}")
        
        # Prepare update data - collected_amount, collector, commission_status, and notes
        update_data = {
            'collected_amount': float(collected_amount),
            'collector': collector_name,
            'commission_status': 'pending'  # 🆕 Set to pending - user must decide later
        }
        
        # Add note if provided
        if note:
            update_data['booking_notes'] = f"Thu tiền: {collected_amount:,.0f}đ bởi {collector_name} - {note}"
        else:
            update_data['booking_notes'] = f"Thu tiền: {collected_amount:,.0f}đ bởi {collector_name}"
        
        print(f"[UPDATE_COLLECTED] 📊 Update data: {update_data}")

        # Update the booking using core logic
        record_booking_history(booking_id, update_data, changed_by='collect_payment')
        success = update_booking(booking_id, update_data)
        
        if success:
            print(f"[UPDATE_COLLECTED] ✅ Successfully updated collected_amount for {booking_id}")

            # Fetch updated booking data to return to frontend
            from core.models import db, Booking
            booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()

            response_data = {
                'success': True,
                'message': f'Đã cập nhật số tiền đã thu: {collected_amount:,.0f}đ',
                'booking_id': booking_id,
                'collected_amount': collected_amount,
                'commission_status': 'pending'
            }

            # Add additional booking data for frontend UI update
            if booking:
                response_data.update({
                    'commission': float(booking.commission) if booking.commission else 0,
                    'room_name': booking.accommodation_name or '',
                    'checkin_date': booking.checkin_date.strftime('%Y-%m-%d') if booking.checkin_date else '',
                    'checkout_date': booking.checkout_date.strftime('%Y-%m-%d') if booking.checkout_date else '',
                    'guest_name': booking.guest.full_name if booking.guest else ''
                })

            print(f"[UPDATE_COLLECTED] 📤 Returning enhanced data: {response_data}")
            return jsonify(response_data)
        else:
            print(f"[UPDATE_COLLECTED] ❌ Failed to update {booking_id}")
            return jsonify({
                'success': False,
                'message': f'Không thể cập nhật booking {booking_id}'
            }), 500
            
    except Exception as e:
        print(f"[UPDATE_COLLECTED] 🚨 Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Lỗi server: {str(e)}'
        }), 500

@app.route('/api/debug_booking/<booking_id>', methods=['GET'])
def debug_booking_data(booking_id):
    """Debug endpoint to check booking data in database"""
    try:
        print(f"🔍 [DEBUG_BOOKING] Checking booking: {booking_id}")
        
        # Check in PostgreSQL database directly
        from core.models import db, Booking, Guest
        booking = db.session.query(Booking).filter_by(booking_id=booking_id).first()
        
        if not booking:
            return jsonify({
                'success': False,
                'message': f'Booking {booking_id} not found in database'
            }), 404
        
        # Get guest info
        guest = booking.guest
        
        booking_data = {
            'booking_id': booking.booking_id,
            'guest_name': guest.full_name if guest else 'N/A',
            'room_amount': float(booking.room_amount) if booking.room_amount else 0,
            'taxi_amount': float(booking.taxi_amount) if booking.taxi_amount else 0,
            'commission': float(booking.commission) if booking.commission else 0,
            'collector': booking.collector,
            'booking_notes': booking.booking_notes,
            'booking_status': booking.booking_status,
            'created_at': booking.created_at.isoformat() if booking.created_at else None,
            'updated_at': booking.updated_at.isoformat() if booking.updated_at else None
        }
        
        print(f"[DEBUG_BOOKING] Database values:")
        for key, value in booking_data.items():
            print(f"[DEBUG_BOOKING]   - {key}: {value} ({type(value)})")
        
        # Also check what load_booking_data returns for this booking
        df = load_booking_data()
        if not df.empty:
            booking_row = df[df['Số đặt phòng'] == booking_id]
            if not booking_row.empty:
                row_data = booking_row.iloc[0].to_dict()
                print(f"[DEBUG_BOOKING] load_booking_data result:")
                print(f"[DEBUG_BOOKING]   - Taxi: {row_data.get('Taxi', 'N/A')} ({type(row_data.get('Taxi'))})")
                print(f"[DEBUG_BOOKING]   - Hoa hồng: {row_data.get('Hoa hồng', 'N/A')}")
                print(f"[DEBUG_BOOKING]   - Ghi chú thanh toán: {row_data.get('Ghi chú thanh toán', 'N/A')}")
        
        return jsonify({
            'success': True,
            'booking_data': booking_data,
            'query_data': row_data if 'row_data' in locals() else None
        })
        
    except Exception as e:
        print(f"[DEBUG_BOOKING] Error: {e}")
        return jsonify({
            'success': False,
            'message': f'Error debugging booking: {str(e)}'
        }), 500


@app.route('/api/import_excel_expenses', methods=['POST'])
def import_excel_expenses():
    """Import expenses from Excel file"""
    try:
        import pandas as pd
        from datetime import datetime, date
        import os
        
        # Use relative path since csvtest.xlsx is in the same directory as app_postgresql.py
        excel_file_path = os.path.join(os.path.dirname(__file__), "csvtest.xlsx")
        
        if not os.path.exists(excel_file_path):
            return jsonify({'success': False, 'message': 'Excel file not found'}), 400
        
        # Smart categorization function
        def categorize_expense(description):
            description_lower = description.lower() if description else ""
            
            categories = {
                'room_supplies': ['xịt phòng', 'chậu ngâm', 'đồ dùng phòng', 'vệ sinh', 'làm sạch', 'khăn', 'ga giường', 'toilet'],
                'food_beverage': ['ăn', 'thức ăn', 'nước', 'coffee', 'cafe', 'beer', 'bia', 'đồ uống', 'ăn vặt', 'nướng', 'cơm'],
                'maintenance': ['sửa chữa', 'bảo trì', 'thay thế', 'lắp đặt', 'điện', 'nước', 'máy lạnh', 'wifi'],
                'transportation': ['taxi', 'xe', 'di chuyển', 'đi lại', 'xăng', 'grab', 'giao hàng'],
                'marketing': ['quảng cáo', 'booking', 'commission', 'hoa hồng', 'platform', 'website'],
                'utilities': ['điện', 'nước', 'internet', 'wifi', 'gas', 'garbage', 'rác'],
                'office_supplies': ['văn phòng', 'giấy', 'bút', 'máy in', 'mực in', 'stapler'],
                'guest_service': ['dịch vụ khách', 'đón tiễn', 'hỗ trợ khách', 'amenity'],
                'miscellaneous': ['khác', 'other', 'misc']
            }
            
            for category, keywords in categories.items():
                for keyword in keywords:
                    if keyword in description_lower:
                        return category
            
            return 'miscellaneous'
        
        # Read Excel data
        excel_data = pd.read_excel(excel_file_path, sheet_name=None)
        expenses = []
        
        # Process Sheet5 (Expense Tracking)
        if 'Sheet5' in excel_data:
            sheet5 = excel_data['Sheet5']
            
            for index, row in sheet5.iterrows():
                try:
                    amount = None
                    description = ""
                    expense_date = datetime.now().date()
                    
                    # Extract data from row
                    for col in sheet5.columns:
                        value = row[col]
                        if pd.notna(value):
                            if isinstance(value, (int, float)) and value > 0:
                                amount = float(value)
                            elif isinstance(value, str) and len(value) > 3:
                                description = str(value)
                            elif isinstance(value, (datetime, date)):
                                expense_date = value if isinstance(value, date) else value.date()
                    
                    if amount and amount > 0 and description:
                        category = categorize_expense(description)
                        
                        expense_data = {
                            'description': description,
                            'amount': amount,
                            'date': expense_date,
                            'category': category,
                            'collector': 'IMPORTED'
                        }
                        
                        if add_expense_to_database(expense_data):
                            expenses.append(expense_data)
                
                except Exception as e:
                    print(f"Error processing expense row {index}: {e}")
        
        # Process Sheet1 for commission and taxi expenses
        if 'Sheet1' in excel_data:
            sheet1 = excel_data['Sheet1']
            
            for index, row in sheet1.iterrows():
                try:
                    commission = row.get('Hoa hồng', 0) if 'Hoa hồng' in row else 0
                    taxi = row.get('Taxi', 0) if 'Taxi' in row else 0
                    guest_name = row.get('Tên người đặt', 'Unknown Guest') if 'Tên người đặt' in row else 'Unknown Guest'
                    booking_id = row.get('Số đặt phòng', f'BOOKING_{index}') if 'Số đặt phòng' in row else f'BOOKING_{index}'
                    
                    expense_date = datetime.now().date()
                    if 'Check-in Date' in row and pd.notna(row['Check-in Date']):
                        try:
                            expense_date = pd.to_datetime(row['Check-in Date']).date()
                        except:
                            pass
                    
                    # Add commission as marketing expense
                    if commission and commission > 0:
                        expense_data = {
                            'description': f'Hoa hồng booking {booking_id} - {guest_name}',
                            'amount': float(commission),
                            'date': expense_date,
                            'category': 'marketing',
                            'collector': 'IMPORTED'
                        }
                        
                        if add_expense_to_database(expense_data):
                            expenses.append(expense_data)
                    
                    # Add taxi as transportation expense
                    if taxi and taxi > 0:
                        expense_data = {
                            'description': f'Taxi cho khách {guest_name} - {booking_id}',
                            'amount': float(taxi),
                            'date': expense_date,
                            'category': 'transportation',
                            'collector': 'IMPORTED'
                        }
                        
                        if add_expense_to_database(expense_data):
                            expenses.append(expense_data)
                
                except Exception as e:
                    print(f"Error processing booking row {index}: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Successfully imported {len(expenses)} expenses',
            'imported_count': len(expenses)
        })
        
    except Exception as e:
        print(f"Error importing Excel expenses: {e}")
        return jsonify({
            'success': False,
            'message': f'Import failed: {str(e)}'
        }), 500

@app.route('/api/comprehensive_import', methods=['POST'])
def comprehensive_import():
    """
    Comprehensive import of all data: customers, costs, and message templates
    Ultra Think Optimization with complete validation and Flask context
    """
    try:
        print("🚀 COMPREHENSIVE IMPORT API CALLED")
        
        # Import the comprehensive import module
        from core.comprehensive_import import (
            parse_excel_file, 
            import_customers_from_sheet1,
            import_message_templates_from_sheet2,
            import_expenses_from_sheet5
        )
        from core.database_import import comprehensive_database_import
        
        # Use relative path since csvtest.xlsx is in the same directory as app_postgresql.py
        excel_file_path = os.path.join(os.path.dirname(__file__), "csvtest.xlsx")
        
        if not os.path.exists(excel_file_path):
            return jsonify({
                'success': False,
                'message': f'Excel file not found: {excel_file_path}. Please upload csvtest.xlsx to the server.'
            }), 400
        
        # Step 1: Parse Excel file
        print("📊 Parsing Excel file...")
        sheets_data = parse_excel_file(excel_file_path)
        if not sheets_data:
            return jsonify({
                'success': False,
                'message': 'Failed to parse Excel file'
            }), 400
        
        # Step 2: Import customers and bookings from Sheet 1
        print("👥 Importing customers and bookings...")
        customers_data = import_customers_from_sheet1(sheets_data.get('Sheet1', []))
        
        # Step 3: Import message templates from Sheet 2
        print("💬 Importing message templates...")
        templates_data = import_message_templates_from_sheet2(sheets_data.get('Sheet2', []))
        
        # Step 4: Import expenses from Sheet 5
        print("💰 Importing expenses...")
        expenses_data = import_expenses_from_sheet5(sheets_data.get('Sheet5', []))
        
        # Step 5: Save to database using Flask context-aware function
        print("💾 Saving to database with Flask context...")
        
        # Use current Flask app context directly
        with app.app_context():
            from core.models import db, Guest, Booking, MessageTemplate, Expense
            
            results = {
                'customers': {'imported': 0, 'updated': 0, 'errors': []},
                'bookings': {'imported': 0, 'updated': 0, 'errors': []},
                'templates': {'imported': 0, 'updated': 0, 'errors': []},
                'expenses': {'imported': 0, 'skipped': 0, 'errors': []},
                'total_success': 0,
                'total_errors': 0
            }
            
            # Import customers first
            guest_mapping = {}
            if customers_data.get('customers'):
                for customer in customers_data['customers']:
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
                            results['customers']['imported'] += 1
                        else:
                            guest_mapping[customer['full_name']] = existing_guest.guest_id
                            results['customers']['updated'] += 1
                            
                    except Exception as e:
                        results['customers']['errors'].append(f"Customer {customer.get('full_name', 'Unknown')}: {str(e)}")
                
                db.session.commit()
            
            # Import bookings
            if customers_data.get('bookings'):
                for booking in customers_data['bookings']:
                    try:
                        guest_id = guest_mapping.get(booking['guest_name'])
                        if not guest_id:
                            results['bookings']['errors'].append(f"Booking {booking['booking_id']}: Guest not found")
                            continue
                        
                        # Skip bookings with null checkin/checkout dates (incomplete bookings)
                        if not booking.get('checkin_date') or not booking.get('checkout_date'):
                            results['bookings']['errors'].append(f"Booking {booking['booking_id']}: Skipped - missing checkin/checkout dates (incomplete booking)")
                            continue
                        
                        existing_booking = Booking.query.filter_by(booking_id=booking['booking_id']).first()
                        
                        if not existing_booking:
                            new_booking = Booking(
                                booking_id=booking['booking_id'],
                                guest_id=guest_id,
                                guest_name=booking['guest_name'],  # Add guest_name for quick access
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
                            results['bookings']['imported'] += 1
                        else:
                            existing_booking.guest_name = booking['guest_name']  # Update guest_name
                            existing_booking.room_amount = booking['room_amount'] or 0.0
                            existing_booking.taxi_amount = booking['taxi_amount'] or 0.0
                            existing_booking.commission = booking['commission'] or 0.0
                            existing_booking.collector = booking.get('collector')
                            existing_booking.booking_status = booking.get('booking_status', 'confirmed')
                            existing_booking.booking_notes = booking.get('booking_notes')
                            results['bookings']['updated'] += 1
                            
                    except Exception as e:
                        db.session.rollback()  # Rollback failed booking
                        results['bookings']['errors'].append(f"Booking {booking.get('booking_id', 'Unknown')}: {str(e)}")
                
                try:
                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    print(f"❌ Error committing bookings: {e}")
                    raise
            
            # Import templates
            if templates_data:
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
                            results['templates']['imported'] += 1
                        else:
                            existing_template.template_content = template['template_content']
                            existing_template.category = template['category'][:100] if template['category'] else 'general'
                            results['templates']['updated'] += 1
                            
                    except Exception as e:
                        results['templates']['errors'].append(f"Template {template.get('template_name', 'Unknown')[:30]}: {str(e)}")
                
                db.session.commit()
            
            # Import expenses
            if expenses_data:
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
                            results['expenses']['imported'] += 1
                        else:
                            results['expenses']['skipped'] += 1
                            
                    except Exception as e:
                        results['expenses']['errors'].append(f"Expense {expense.get('description', 'Unknown')[:30]}: {str(e)}")
                
                db.session.commit()
            
            # Calculate totals
            results['total_success'] = (
                results['customers']['imported'] + results['customers']['updated'] +
                results['bookings']['imported'] + results['bookings']['updated'] +
                results['templates']['imported'] + results['templates']['updated'] +
                results['expenses']['imported']
            )
            
            results['total_errors'] = (
                len(results['customers']['errors']) +
                len(results['bookings']['errors']) +
                len(results['templates']['errors']) +
                len(results['expenses']['errors'])
            )
        
        # Prepare detailed summary
        summary = {
            'customers_imported': results['customers']['imported'] + results['customers']['updated'],
            'bookings_imported': results['bookings']['imported'] + results['bookings']['updated'],
            'templates_imported': results['templates']['imported'] + results['templates']['updated'],
            'expenses_imported': results['expenses']['imported'],
            'total_imported': results['total_success'],
            'total_errors': results['total_errors'],
            'errors': []
        }
        
        # Collect all errors
        for category_data in [results['customers'], results['bookings'], results['templates'], results['expenses']]:
            summary['errors'].extend(category_data.get('errors', []))
        
        return jsonify({
            'success': True,
            'message': f'Comprehensive import completed successfully! Total: {summary["total_imported"]} records',
            'summary': summary
        })
        
    except Exception as e:
        # Rollback the session on error
        try:
            db.session.rollback()
        except:
            pass
        print(f"❌ Comprehensive import error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Import failed: {str(e)}'
        }), 500

@app.route('/api/import_status', methods=['GET'])
def import_status():
    """
    Get current database status after import
    """
    try:
        from core.models import Guest, Booking, MessageTemplate, Expense
        
        status = {
            'customers_count': Guest.query.count(),
            'bookings_count': Booking.query.count(),
            'templates_count': MessageTemplate.query.count(),
            'expenses_count': Expense.query.count(),
            'last_updated': datetime.now().isoformat()
        }
        
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Status check failed: {str(e)}'
        }), 500

@app.route('/api/import_bookings_json', methods=['POST'])
def import_bookings_json():
    """
    Import bookings directly from JSON data
    Expects JSON format: {"bookings": [{"guest_name": "...", "checkin_date": "...", ...}]}
    """
    try:
        from core.models import db, Booking
        from datetime import datetime

        # Get JSON data from request
        data = request.get_json()

        if not data or 'bookings' not in data:
            return jsonify({
                'success': False,
                'error': 'Invalid JSON format. Expected {"bookings": [...]}'
            }), 400

        bookings_data = data['bookings']
        print(f"📋 Received {len(bookings_data)} bookings to import")

        results = {
            'imported': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }

        for booking_data in bookings_data:
            try:
                booking_id = booking_data.get('booking_id')
                if not booking_id:
                    results['errors'].append('Missing booking_id')
                    continue

                # Check if booking already exists
                existing_booking = Booking.query.filter_by(booking_id=booking_id).first()

                # Parse dates
                checkin_date = None
                checkout_date = None

                if booking_data.get('checkin_date'):
                    try:
                        checkin_date = datetime.strptime(booking_data['checkin_date'], '%Y-%m-%d').date()
                    except:
                        results['errors'].append(f"Booking {booking_id}: Invalid checkin_date format")
                        continue

                if booking_data.get('checkout_date'):
                    try:
                        checkout_date = datetime.strptime(booking_data['checkout_date'], '%Y-%m-%d').date()
                    except:
                        results['errors'].append(f"Booking {booking_id}: Invalid checkout_date format")
                        continue

                if not checkin_date or not checkout_date:
                    results['errors'].append(f"Booking {booking_id}: Missing dates")
                    continue

                if existing_booking:
                    # Update existing booking
                    existing_booking.guest_name = booking_data.get('guest_name', existing_booking.guest_name)
                    existing_booking.checkin_date = checkin_date
                    existing_booking.checkout_date = checkout_date
                    existing_booking.room_type = booking_data.get('room_type', existing_booking.room_type)
                    existing_booking.room_amount = float(booking_data.get('room_amount', 0))
                    existing_booking.commission = float(booking_data.get('commission', 0))
                    existing_booking.booking_status = booking_data.get('status', 'confirmed')
                    existing_booking.currency = booking_data.get('currency', 'VND')
                    existing_booking.updated_at = datetime.now()

                    results['updated'] += 1
                    print(f"✅ Updated booking {booking_id} for {booking_data.get('guest_name')}")
                else:
                    # Create new booking
                    new_booking = Booking(
                        booking_id=booking_id,
                        guest_name=booking_data.get('guest_name', 'Unknown'),
                        checkin_date=checkin_date,
                        checkout_date=checkout_date,
                        room_type=booking_data.get('room_type', 'Standard'),
                        room_amount=float(booking_data.get('room_amount', 0)),
                        commission=float(booking_data.get('commission', 0)),
                        booking_status=booking_data.get('status', 'confirmed'),
                        currency=booking_data.get('currency', 'VND'),
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )

                    db.session.add(new_booking)
                    results['imported'] += 1
                    print(f"✅ Created booking {booking_id} for {booking_data.get('guest_name')}")

            except Exception as e:
                results['errors'].append(f"Booking {booking_data.get('booking_id', 'Unknown')}: {str(e)}")
                print(f"❌ Error importing booking: {e}")

        # Commit all changes
        try:
            db.session.commit()
            print(f"💾 Committed {results['imported']} new + {results['updated']} updated bookings")
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': f'Database commit failed: {str(e)}'
            }), 500

        return jsonify({
            'success': True,
            'message': f"Imported {results['imported']} new, updated {results['updated']} bookings",
            'results': results
        })

    except Exception as e:
        print(f"❌ JSON import error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _ensure_checkin_status_column():
    """Create checkin_status column if it doesn't exist yet.
    Safe to call every request (ALTER TABLE ... IF NOT EXISTS is idempotent).
    Called at the top of every checkin-status endpoint so the column is
    guaranteed before any DML or SELECT that references it."""
    try:
        from core.models import db as _cs_db
        _cs_db.session.execute(
            text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS checkin_status VARCHAR(20)")
        )
        _cs_db.session.commit()
    except Exception:
        try:
            from core.models import db as _cs_db
            _cs_db.session.rollback()
        except Exception:
            pass


@app.route('/api/set_checkin_status', methods=['POST'])
def set_checkin_status():
    """Save daily check-in arrival status for a booking to PostgreSQL.
    Called from both mobile and desktop whenever staff marks a guest
    confirmed / cancelling / not-contacted. Shared across all devices."""
    try:
        _ensure_checkin_status_column()  # always runs first — guarantees column exists
        data = request.get_json()
        booking_id = data.get('booking_id', '').strip()
        status = data.get('status')  # 'confirmed' | 'cancelling' | None/''
        if not booking_id:
            return jsonify({'success': False, 'error': 'Missing booking_id'}), 400
        # Normalise: empty string → NULL (= "not contacted")
        if status == '':
            status = None
        if status not in (None, 'confirmed', 'cancelling'):
            return jsonify({'success': False, 'error': f'Invalid status: {status}'}), 400
        from core.models import db
        # Only update checkin_status — NOT booking_status.
        # This keeps the booking visible in today's check-in view even after a
        # page refresh (so staff can review/undo throughout the day).
        # The booking is excluded from the "staying" section for all FUTURE days
        # by filtering on checkin_status='cancelling' in calendar/mobile views.
        db.session.execute(
            text("UPDATE bookings SET checkin_status = :s WHERE booking_id = :bid"),
            {'s': status, 'bid': booking_id}
        )
        if status == 'confirmed':      # the guest was reached → no "📵 không liên lạc được" any more
            try:
                db.session.execute(text("DELETE FROM journey_log WHERE booking_id = :bid AND step = 'unreachable'"),
                                   {'bid': booking_id})
            except Exception:
                pass
        db.session.commit()
        return jsonify({'success': True, 'booking_id': booking_id, 'status': status})
    except Exception as e:
        try:
            from core.models import db
            db.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get_checkin_statuses')
def get_checkin_statuses():
    """Return {booking_id: status} for a list of booking IDs.
    Used by desktop calendar_details to sync statuses from DB on page load."""
    try:
        _ensure_checkin_status_column()  # always runs first — guarantees column exists
        bids = request.args.getlist('bids[]')
        if not bids:
            return jsonify({'success': True, 'statuses': {}})
        from core.models import db
        rows = db.session.execute(
            text("""SELECT booking_id, checkin_status FROM bookings
                    WHERE booking_id = ANY(:bids) AND checkin_status IS NOT NULL"""),
            {'bids': bids}
        ).fetchall()
        statuses = {r[0]: r[1] for r in rows}
        # what /messages knows: last message sent / "📵 không liên lạc được" (shown on the calendar's status bar)
        contact = {}
        try:
            from core import journey as J
            for bid, done in J.sent_status(db.session, bids).items():
                last = J.last_contact(done)
                contact[bid] = {'last': last, 'unreach': J.unreachable_at(done, statuses.get(bid) == 'confirmed')}
        except Exception as _ce:
            print(f"[checkin_statuses] contact info failed: {_ce}")
        apts = {r[0]: (r[1] or '') for r in db.session.execute(
            text("SELECT booking_id, actual_apartment FROM bookings WHERE booking_id = ANY(:bids)"), {'bids': bids}).fetchall()}
        return jsonify({'success': True, 'statuses': statuses, 'contact': contact, 'apts': apts})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'statuses': {}})


# ============================================================================
# API ENDPOINTS FOR AI ASSISTANT TEMPLATES
# ============================================================================

