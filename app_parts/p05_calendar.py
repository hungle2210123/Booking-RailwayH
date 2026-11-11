


@app.route('/api/set_actual_apartment', methods=['POST'])
def set_actual_apartment():
    """Save which actual apartment a guest is assigned to."""
    try:
        from core.models import db as _sadb
        data       = request.get_json()
        booking_id = data.get('booking_id', '').strip()
        apt_value  = data.get('actual_apartment', '').strip()   # '' = clear
        if not booking_id:
            return jsonify({'success': False, 'message': 'Missing booking_id'}), 400

        _moi_ensure()     # bookings.room_no (/moi): a room number belongs to the apartment, so it goes when that changes
        if apt_value:
            _sadb.session.execute(
                text("UPDATE bookings SET room_no = CASE WHEN actual_apartment = :apt THEN room_no END, "
                     "actual_apartment = :apt WHERE booking_id = :bid"),
                {'apt': apt_value, 'bid': booking_id}
            )
        else:
            _sadb.session.execute(
                text("UPDATE bookings SET actual_apartment = NULL, room_no = NULL WHERE booking_id = :bid"),
                {'bid': booking_id}
            )
        _sadb.session.commit()

        # Record to activity history
        try:
            from core.models import BookingHistory as _SABH
            _vn = datetime.utcnow() + timedelta(hours=7)
            _h = _SABH(booking_id=booking_id, field_name='Căn hộ thực tế',
                       old_value=None, new_value=apt_value or '(xóa)',
                       change_description=f"Phân loại căn hộ: {apt_value or 'Xóa'} lúc {_vn.strftime('%H:%M %d/%m/%Y')}",
                       changed_by='set_apartment')
            _sadb.session.add(_h); _sadb.session.commit()
        except Exception:
            pass

        return jsonify({'success': True, 'booking_id': booking_id, 'actual_apartment': apt_value})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


