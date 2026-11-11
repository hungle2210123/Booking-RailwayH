# p08_collect_history_import — collect payment, commission status, guest amounts, booking history, Excel/JSON import, check-in status sync
# Part of app.py (lines 9613-11163 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.


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


# ============================================================================
# API ENDPOINTS FOR AI ASSISTANT TEMPLATES
# ============================================================================

