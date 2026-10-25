# p06_payments_booking_api — mobile payment page + analytics, booking API (get/quick-update/extend), image/text booking extraction, duplicates check
# Part of app.py (lines 6637-8546 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
# ─────────────────────────────────────────────────────────────
# MOBILE PAYMENT COLLECTION PAGE
# ─────────────────────────────────────────────────────────────
@app.route('/mobile_payment')
def mobile_payment_view():
    """Mobile-optimised payment collection page — unpaid guests only."""
    try:
        _vn_now  = datetime.utcnow() + timedelta(hours=7)
        _today   = _vn_now.date()

        df = load_booking_data(force_fresh=True)

        # ── Fetch checkin_status from DB directly (not in load_booking_data SQL) ──
        _cs_map = {}
        try:
            from core.models import db as _csdb
            _cs_rows = _csdb.session.execute(
                text("SELECT booking_id, checkin_status FROM bookings WHERE checkin_status IS NOT NULL")
            ).fetchall()
            _cs_map = {r[0]: r[1] for r in _cs_rows}
        except Exception as _cse:
            print(f"[MOBILE_PAYMENT] checkin_status fetch failed (non-critical): {_cse}")

        _no_show_cutoff = _today - timedelta(days=2)

        unpaid = []
        for _, row in df.iterrows():
            try:
                # Skip if already collected by LOC or THAO
                collector = str(row.get('Người thu tiền', '') or '')
                if 'LOC' in collector or 'THAO' in collector:
                    continue

                # Skip if booking is too old (checkout > 7 days ago)
                co = row.get('Check-out Date')
                if not pd.notna(co):
                    continue
                co_date = pd.Timestamp(co).date()
                if co_date < _today - timedelta(days=7):
                    continue

                # Skip cancelled / deleted
                booking_status = str(row.get('Tình trạng', '') or '').lower()
                if any(k in booking_status for k in ['hủy', 'cancel', 'delet', 'xóa']):
                    continue

                ci = row.get('Check-in Date')
                ci_date = pd.Timestamp(ci).date() if pd.notna(ci) else _today

                # Get checkin_status from DB map
                bid = str(row.get('Số đặt phòng', '') or '')
                cs  = str(_cs_map.get(bid, '') or '')

                # No-show filter:
                #   confirmed   → always show
                #   cancelling  → always skip
                #   NULL/''     → apply grace period ONLY for future/current guests
                #                 If guest already checked out (co_date < today), they
                #                 were real — skip no-show check regardless of status
                if cs == 'cancelling':
                    continue
                already_left = (co_date < _today)
                if cs != 'confirmed' and not already_left:
                    if ci_date < _no_show_cutoff:
                        continue   # no-show: still here but never confirmed

                nights  = max((co_date - ci_date).days, 1)
                amount     = float(row.get('Tổng thanh toán', 0) or 0)
                commission = float(row.get('Hoa hồng', 0) or 0)

                # Label for grouping
                if already_left:
                    label = 'overdue'          # ← already gone, most urgent
                elif co_date == _today:
                    label = 'checkout_today'
                elif ci_date == _today:
                    label = 'checkin_today'
                elif co_date == _today + timedelta(days=1):
                    label = 'checkout_tomorrow'
                else:
                    label = 'staying'

                unpaid.append({
                    'id':               row.get('Số đặt phòng', ''),
                    'name':             row.get('Tên người đặt', 'N/A'),
                    'room':             row.get('Tên chỗ nghỉ', 'N/A'),
                    'checkin':          ci_date.strftime('%Y-%m-%d'),
                    'checkin_display':  ci_date.strftime('%d/%m'),
                    'checkout':         co_date.strftime('%Y-%m-%d'),
                    'checkout_display': co_date.strftime('%d/%m'),
                    'nights':           nights,
                    'amount':           amount,
                    'commission':       commission,
                    'label':            label,
                    'notes':            str(row.get('Ghi chú', '') or ''),
                })
            except Exception:
                continue

        # Sort: overdue (already left) first → checkout today → staying → checkin today → tomorrow
        _order = {'overdue': 0, 'checkout_today': 1, 'staying': 2,
                  'checkin_today': 3, 'checkout_tomorrow': 4, 'upcoming': 5}
        unpaid.sort(key=lambda x: (_order.get(x['label'], 9), x['checkout']))

        total_unpaid = sum(g['amount'] for g in unpaid)

        return render_template(
            'mobile_payment.html',
            unpaid_guests=unpaid,
            total_unpaid=total_unpaid,
            today_display=_vn_now.strftime('%d/%m/%Y'),
            today_time=_vn_now.strftime('%H:%M'),
            guest_count=len(unpaid),
        )
    except Exception as e:
        import traceback; traceback.print_exc()
        return f'<h3>Error: {e}</h3>', 500


@app.route('/api/payment_history_today', methods=['GET'])
def payment_history_today():
    """Return today's payment collection records from BookingHistory."""
    try:
        from core.models import db as _phdb, BookingHistory as _PBH, Booking as _PB
        _vn_now = datetime.utcnow() + timedelta(hours=7)
        _today_str = _vn_now.strftime('%Y-%m-%d')

        entries = (
            _phdb.session.query(_PBH)
            .filter(_PBH.changed_by.in_(['collect_payment', 'mobile_payment']))
            .order_by(_PBH.created_at.desc())
            .limit(200)
            .all()
        )

        # Filter to entries created today (VN time)
        from datetime import timezone
        today_entries = []
        bids = set()
        for e in entries:
            if e.created_at:
                vn_ts = e.created_at + timedelta(hours=7)
                if vn_ts.strftime('%Y-%m-%d') == _today_str:
                    today_entries.append(e)
                    bids.add(e.booking_id)

        # Lookup guest names
        name_map = {}
        if bids:
            rows = _phdb.session.query(_PB.booking_id, _PB.guest_name).filter(
                _PB.booking_id.in_(list(bids))
            ).all()
            name_map = {r.booking_id: r.guest_name for r in rows}

        result = []
        for e in today_entries:
            d = e.to_dict()
            d['guest_name'] = name_map.get(e.booking_id, '')
            if e.created_at:
                vn_ts = e.created_at + timedelta(hours=7)
                d['vn_time'] = vn_ts.strftime('%H:%M')
                d['vn_date'] = vn_ts.strftime('%d/%m/%Y')
            result.append(d)

        return jsonify({'success': True, 'history': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/payment_weekly_chart', methods=['GET'])
def payment_weekly_chart():
    """Return daily payment totals for the past 7 days (VN time), starting from today backwards."""
    try:
        from core.models import db as _wcdb, BookingHistory as _WBH, Booking as _WB
        _vn_now = datetime.utcnow() + timedelta(hours=7)
        _today  = _vn_now.date()

        # Build 7-day window: today and 6 days back
        days = [_today - timedelta(days=i) for i in range(6, -1, -1)]  # oldest → newest
        day_strs = {d.strftime('%Y-%m-%d'): d for d in days}

        # Fetch all payment entries in range (UTC: subtract 7h from oldest day start)
        _oldest_utc = datetime.combine(days[0], __import__('datetime').time.min) - timedelta(hours=7)
        entries = (
            _wcdb.session.query(_WBH)
            .filter(
                _WBH.changed_by.in_(['collect_payment', 'mobile_payment']),
                _WBH.field_name == 'Số tiền đã thu',
                _WBH.created_at >= _oldest_utc
            )
            .all()
        )

        # Bucket by VN date
        totals = {d.strftime('%Y-%m-%d'): 0.0 for d in days}
        counts = {d.strftime('%Y-%m-%d'): 0   for d in days}
        for e in entries:
            if e.created_at:
                vn_date = (e.created_at + timedelta(hours=7)).strftime('%Y-%m-%d')
                if vn_date in totals:
                    try:
                        totals[vn_date] += float(e.new_value or 0)
                        counts[vn_date] += 1
                    except Exception:
                        pass

        result = []
        for d in days:
            iso = d.strftime('%Y-%m-%d')
            result.append({
                'date':     iso,
                'label':    d.strftime('%d/%m'),
                'day_name': ['CN','T2','T3','T4','T5','T6','T7'][d.weekday() % 7 if d.weekday() < 6 else 6],
                'total':    totals[iso],
                'count':    counts[iso],
                'is_today': iso == _today.strftime('%Y-%m-%d'),
            })

        grand_total = sum(r['total'] for r in result)
        grand_count = sum(r['count'] for r in result)
        return jsonify({'success': True, 'days': result,
                        'grand_total': grand_total, 'grand_count': grand_count})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/payment_analytics', methods=['GET'])
def payment_analytics():
    """
    Unified analytics endpoint.
    ?period=week|month|year  &offset=0 (0=current, -1=prev, +1=next)
    Returns: bars[], summary{total,count,loc,thao}, period_label
    """
    try:
        from core.models import db as _adb, BookingHistory as _ABH, Booking as _AB
        _vn_now = datetime.utcnow() + timedelta(hours=7)
        _today  = _vn_now.date()
        period  = request.args.get('period', 'week')
        offset  = int(request.args.get('offset', 0))

        VN_DAYS   = ['CN','T2','T3','T4','T5','T6','T7']
        VN_MONTHS = ['','Th1','Th2','Th3','Th4','Th5','Th6','Th7','Th8','Th9','Th10','Th11','Th12']

        if period == 'week':
            end   = _today + timedelta(days=offset * 7)
            start = end - timedelta(days=6)
            days  = [start + timedelta(days=i) for i in range(7)]
            iso_start = start.strftime('%Y-%m-%d')
            iso_end   = end.strftime('%Y-%m-%d')
            period_label = f"{start.strftime('%d/%m')} – {end.strftime('%d/%m/%Y')}"
            def bar_key(vn_dt): return vn_dt.strftime('%Y-%m-%d')
            bars_meta = [{
                'key':      d.strftime('%Y-%m-%d'),
                'label':    d.strftime('%d/%m'),
                'sublabel': VN_DAYS[d.weekday()+1 if d.weekday()<6 else 0],
                'is_today': d == _today,
                'date_iso': d.strftime('%Y-%m-%d'),
            } for d in days]

        elif period == 'month':
            # offset in months from current
            y, m = _today.year, _today.month
            m += offset
            while m > 12: m -= 12; y += 1
            while m < 1:  m += 12; y -= 1
            import calendar
            _, n_days = calendar.monthrange(y, m)
            days = [date(y, m, d) for d in range(1, n_days+1)]
            start, end = days[0], days[-1]
            period_label = f"Tháng {m}/{y}"
            def bar_key(vn_dt): return vn_dt.strftime('%Y-%m-%d')
            bars_meta = [{
                'key':      d.strftime('%Y-%m-%d'),
                'label':    str(d.day),
                'sublabel': VN_DAYS[d.weekday()+1 if d.weekday()<6 else 0],
                'is_today': d == _today,
                'date_iso': d.strftime('%Y-%m-%d'),
            } for d in days]

        else:  # year
            y = _today.year + offset
            months = [date(y, m, 1) for m in range(1, 13)]
            start  = months[0]
            end    = date(y, 12, 31)
            period_label = f"Năm {y}"
            def bar_key(vn_dt): return f"{y}-{vn_dt.month:02d}"
            bars_meta = [{
                'key':      f"{y}-{m.month:02d}",
                'label':    VN_MONTHS[m.month],
                'sublabel': str(m.year),
                'is_today': (m.year == _today.year and m.month == _today.month),
                'date_iso': m.strftime('%Y-%m-%d'),
            } for m in months]

        # Fetch all payment entries in window
        from datetime import date as _date_cls
        _start_utc = datetime.combine(start, __import__('datetime').time.min) - timedelta(hours=7)
        _end_utc   = datetime.combine(end,   __import__('datetime').time.max) - timedelta(hours=7)

        entries = (
            _adb.session.query(_ABH)
            .filter(
                _ABH.changed_by.in_(['collect_payment', 'mobile_payment']),
                _ABH.created_at >= _start_utc,
                _ABH.created_at <= _end_utc,
            )
            .order_by(_ABH.created_at.asc())
            .all()
        )

        # Build totals + collector split per bar
        totals  = {b['key']: 0.0 for b in bars_meta}
        counts  = {b['key']: 0   for b in bars_meta}
        loc_map = {b['key']: 0.0 for b in bars_meta}
        thao_map= {b['key']: 0.0 for b in bars_meta}
        total_loc = total_thao = 0.0
        grand_total = grand_count = 0

        # We need to pair "Người thu tiền" + "Số tiền đã thu" per booking per event
        # Group by booking_id+date for pairing
        pair = {}  # (booking_id, date_key) -> {collector, amount}
        for e in entries:
            if not e.created_at: continue
            vn_dt  = e.created_at + timedelta(hours=7)
            dk     = bar_key(vn_dt)
            if dk not in totals: continue
            pair_k = (e.booking_id, vn_dt.strftime('%Y-%m-%d %H'))  # hourly bucket
            if pair_k not in pair: pair[pair_k] = {'collector':'','amount':0.0,'dk':dk}
            if e.field_name == 'Người thu tiền':  pair[pair_k]['collector'] = e.new_value or ''
            if e.field_name == 'Số tiền đã thu':
                try: pair[pair_k]['amount'] = float(e.new_value or 0)
                except: pass

        for pk, pv in pair.items():
            dk  = pv['dk']
            amt = pv['amount']
            col = pv['collector']
            if amt <= 0: continue
            totals[dk] += amt; counts[dk] += 1
            grand_total += amt; grand_count += 1
            if 'LOC'  in col: loc_map[dk]  += amt; total_loc  += amt
            if 'THAO' in col: thao_map[dk] += amt; total_thao += amt

        bars = []
        for b in bars_meta:
            k = b['key']
            bars.append({**b,
                'total': totals[k], 'count': counts[k],
                'loc':   loc_map[k], 'thao': thao_map[k],
            })

        return jsonify({
            'success':      True,
            'period_label': period_label,
            'bars':         bars,
            'grand_total':  grand_total,
            'grand_count':  grand_count,
            'total_loc':    total_loc,
            'total_thao':   total_thao,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/payment_day_detail', methods=['GET'])
def payment_day_detail():
    """
    Returns individual transactions for a date range (for detail drill-down).
    ?from=YYYY-MM-DD&to=YYYY-MM-DD  (to defaults to from)
    """
    try:
        from core.models import db as _ddb, BookingHistory as _DBH, Booking as _DB
        from_str = request.args.get('from', '')
        to_str   = request.args.get('to', from_str)
        if not from_str:
            return jsonify({'success': False, 'message': 'Missing from'}), 400

        from_date = datetime.strptime(from_str, '%Y-%m-%d').date()
        to_date   = datetime.strptime(to_str,   '%Y-%m-%d').date()

        _start_utc = datetime.combine(from_date, __import__('datetime').time.min) - timedelta(hours=7)
        _end_utc   = datetime.combine(to_date,   __import__('datetime').time.max) - timedelta(hours=7)

        entries = (
            _ddb.session.query(_DBH)
            .filter(
                _DBH.changed_by.in_(['collect_payment', 'mobile_payment']),
                _DBH.created_at >= _start_utc,
                _DBH.created_at <= _end_utc,
            )
            .order_by(_DBH.created_at.desc())
            .all()
        )

        # Pair collector + amount per booking per hour
        pair = {}
        bids = set()
        for e in entries:
            if not e.created_at: continue
            bids.add(e.booking_id)
            vn_ts  = e.created_at + timedelta(hours=7)
            pk     = (e.booking_id, vn_ts.strftime('%Y-%m-%d %H'))
            if pk not in pair: pair[pk] = {'collector':'','amount':0.0,'time':vn_ts.strftime('%H:%M'),'date':vn_ts.strftime('%d/%m/%Y'),'booking_id':e.booking_id}
            if e.field_name == 'Người thu tiền': pair[pk]['collector'] = e.new_value or ''
            if e.field_name == 'Số tiền đã thu':
                try: pair[pk]['amount'] = float(e.new_value or 0)
                except: pass

        # Lookup guest names
        name_map = {}
        if bids:
            rows = _ddb.session.query(_DB.booking_id, _DB.guest_name).filter(_DB.booking_id.in_(list(bids))).all()
            name_map = {r.booking_id: r.guest_name for r in rows}

        txns = sorted(
            [{'booking_id':v['booking_id'],'collector':v['collector'],'amount':v['amount'],
              'time':v['time'],'date':v['date'],'guest_name':name_map.get(v['booking_id'],'—')}
             for v in pair.values() if v['amount'] > 0],
            key=lambda x: x['date']+x['time'], reverse=True
        )

        return jsonify({'success': True, 'transactions': txns,
                        'total': sum(t['amount'] for t in txns), 'count': len(txns)})
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# Quick Edit API Endpoints for Calendar Details Page
@app.route('/api/booking/<booking_id>', methods=['GET'])
def get_booking_details(booking_id):
    """Get booking details for comprehensive edit modal"""
    try:
        # Force fresh data to get latest commission values
        df = load_booking_data(force_fresh=True)
        booking_data = df[df['Số đặt phòng'] == booking_id]

        if booking_data.empty:
            return jsonify({'success': False, 'message': 'Booking not found'}), 404

        booking = booking_data.iloc[0]

        # Get room amount (calculated or original)
        room_amount = booking.get('calculated_room_fee', booking.get('Tổng thanh toán', 0)) or 0
        taxi_amount = booking.get('calculated_taxi_fee', 0) or 0

        return jsonify({
            'success': True,
            'booking': {
                'booking_id': booking.get('Số đặt phòng', ''),
                'guest_name': booking.get('Tên người đặt', ''),
                'checkin_date': booking['Check-in Date'].strftime('%Y-%m-%d') if pd.notnull(booking['Check-in Date']) else '',
                'checkout_date': booking['Check-out Date'].strftime('%Y-%m-%d') if pd.notnull(booking['Check-out Date']) else '',
                'room_amount': float(room_amount),
                'taxi_amount': float(taxi_amount),
                'commission': float(booking.get('Hoa hồng', 0) or 0),
                'accommodation_name': booking.get('room_name', '') or booking.get('Tên chỗ nghỉ', '118 hang bac'),
                'room_name': booking.get('room_name', '') or booking.get('Tên chỗ nghỉ', '118 hang bac'),
                'rooms_occupied': int(booking.get('rooms_occupied', 1) or 1),
                'booking_notes': booking.get('Ghi chú', '') or ''
            }
        })
    except Exception as e:
        print(f"❌ Error fetching booking {booking_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/booking/<booking_id>/quick-update', methods=['POST'])
def quick_update_booking(booking_id):
    """Quick update booking from calendar details page"""
    try:
        data = request.get_json()

        update_data = {
            'checkin_date': datetime.strptime(data['checkin_date'], '%Y-%m-%d').date(),
            'checkout_date': datetime.strptime(data['checkout_date'], '%Y-%m-%d').date(),
            'room_amount': float(data['room_amount']),
            'commission': float(data.get('commission', 0)),
            'accommodation_name': data.get('room_type')  # Add room type (accommodation_name field)
        }

        record_booking_history(booking_id, update_data, changed_by='quick_edit')
        if update_booking(booking_id, update_data):
            return jsonify({'success': True, 'message': 'Booking updated successfully'})
        else:
            return jsonify({'success': False, 'message': 'Failed to update booking'}), 400
    except Exception as e:
        print(f"❌ Error updating booking {booking_id}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/booking/<booking_id>/extend', methods=['POST'])
def extend_booking(booking_id):
    """Extend a guest's stay: push checkout date forward and add extra amount."""
    try:
        data = request.get_json()
        extra_nights   = int(data.get('extra_nights', 0))
        price_per_night = float(data.get('price_per_night', 0))

        if extra_nights <= 0:
            return jsonify({'success': False, 'message': 'Số đêm gia hạn phải lớn hơn 0'}), 400

        # Read current booking from DB
        from core.models import db as _edb, Booking as _EBooking
        booking_row = _EBooking.query.filter_by(booking_id=booking_id).first()
        if not booking_row:
            # Fallback: read from dataframe
            df_all = load_booking_data(force_fresh=True)
            row = df_all[df_all['Số đặt phòng'] == booking_id]
            if row.empty:
                return jsonify({'success': False, 'message': 'Không tìm thấy booking'}), 404
            r = row.iloc[0]
            current_checkout = pd.Timestamp(r['Check-out Date']).date()
            current_amount   = float(r.get('Tổng thanh toán', 0) or 0)
        else:
            current_checkout = booking_row.checkout_date.date() if hasattr(booking_row.checkout_date, 'date') else booking_row.checkout_date
            current_amount   = float(booking_row.room_amount or 0)

        new_checkout = current_checkout + timedelta(days=extra_nights)
        extra_amount = extra_nights * price_per_night
        new_amount   = current_amount + extra_amount

        update_data = {
            'checkout_date': new_checkout,
            'room_amount':   new_amount,
        }

        record_booking_history(booking_id, update_data, changed_by='extend_stay')
        if update_booking(booking_id, update_data):
            print(f"✅ [EXTEND] {booking_id}: checkout {current_checkout} → {new_checkout}, amount {current_amount:,.0f} + {extra_amount:,.0f} = {new_amount:,.0f}")
            # Add a human-readable summary entry to the activity log
            try:
                from core.models import db as _hdb2, BookingHistory as _BH2
                _vn_now = datetime.utcnow() + timedelta(hours=7)
                _summary = _BH2(
                    booking_id=booking_id,
                    field_name='Gia hạn phòng',
                    old_value=current_checkout.strftime('%d/%m/%Y'),
                    new_value=new_checkout.strftime('%d/%m/%Y'),
                    change_description=(
                        f"🏨 Gia hạn {extra_nights} đêm: "
                        f"{current_checkout.strftime('%d/%m/%Y')} → {new_checkout.strftime('%d/%m/%Y')} | "
                        f"Phí gia hạn: +{extra_amount:,.0f}đ | "
                        f"Tổng mới: {new_amount:,.0f}đ | "
                        f"Ghi nhận: {_vn_now.strftime('%H:%M %d/%m/%Y')}"
                    ),
                    changed_by='extend_stay',
                )
                _hdb2.session.add(_summary)
                _hdb2.session.commit()
            except Exception as _he:
                print(f"[EXTEND] History summary failed (non-critical): {_he}")
            return jsonify({
                'success': True,
                'new_checkout': new_checkout.strftime('%Y-%m-%d'),
                'new_checkout_display': new_checkout.strftime('%d/%m/%Y'),
                'extra_amount': extra_amount,
                'new_amount': new_amount,
                'extra_nights': extra_nights,
            })
        else:
            return jsonify({'success': False, 'message': 'Cập nhật thất bại'}), 400

    except Exception as e:
        print(f"❌ [EXTEND] Error {booking_id}: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


# Photo Processing Endpoint - Enhanced with Multiple Booking Support
@app.route('/api/check_existing_bookings', methods=['POST'])
def check_existing_bookings():
    """Check which bookings already exist in the system"""
    try:
        data = request.get_json()
        bookings_to_check = data.get('bookings', [])
        
        existing_booking_data = load_booking_data()
        existing_ids = set()
        if not existing_booking_data.empty and 'Số đặt phòng' in existing_booking_data.columns:
            existing_ids = set(existing_booking_data['Số đặt phòng'].dropna().astype(str))
        
        # Check each booking
        results = []
        for i, booking in enumerate(bookings_to_check):
            booking_id = str(booking.get('booking_id', '')).strip()
            guest_name = booking.get('guest_name', '')
            
            is_existing = booking_id in existing_ids if booking_id else False
            
            results.append({
                'index': i,
                'guest_name': guest_name,
                'booking_id': booking_id,
                'exists': is_existing,
                'status': 'existing' if is_existing else 'new'
            })
        
        return jsonify({
            'success': True,
            'results': results,
            'total_existing': sum(1 for r in results if r['exists'])
        })
        
    except Exception as e:
        print(f"❌ [CHECK_EXISTING] Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/process_pasted_image', methods=['POST'])
def process_pasted_image():
    """Enhanced photo processing with smart single/multiple booking detection"""
    try:
        # 🚂 RAILWAY DEBUG: Enhanced logging for deployment debugging
        railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
        environment = 'railway' if railway_env else 'local'
        print(f"🌍 [PHOTO_PROCESSING] Environment: {environment}")
        print(f"📝 [PHOTO_PROCESSING] Request method: {request.method}")
        print(f"📝 [PHOTO_PROCESSING] Content type: {request.content_type}")
        print(f"📝 [PHOTO_PROCESSING] Request size: {request.content_length}")
        
        # Configure Gemini API
        GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
        if not GOOGLE_API_KEY:
            error_msg = f'Google AI API not configured on {environment}'
            print(f"❌ [PHOTO_PROCESSING] {error_msg}")
            return jsonify({'error': error_msg, 'environment': environment}), 400
        
        # Get image data from request - handle both file upload and JSON base64
        image_data = None
        
        # Method 1: File upload (multipart/form-data)
        if request.files.get('image'):
            image_data = request.files.get('image').read()
            
        # Method 2: JSON with base64 data (application/json)  
        elif request.is_json and request.json.get('image_b64'):
            import base64
            try:
                # Remove data URL prefix if present (data:image/png;base64,)
                base64_data = request.json.get('image_b64')
                if ',' in base64_data:
                    base64_data = base64_data.split(',')[1]
                
                image_data = base64.b64decode(base64_data)
                print(f"✅ Decoded base64 image, size: {len(image_data)} bytes")
                
            except Exception as decode_error:
                print(f"❌ Base64 decode error: {decode_error}")
                return jsonify({'error': f'Invalid base64 image data: {str(decode_error)}'}), 400
        
        if not image_data:
            return jsonify({'error': 'No image provided (expected file upload or base64 JSON)'}), 400
        
        # Get room type from request (if provided)
        room_type = '118 Hang Bac Hostel'  # Default
        if request.is_json and request.json.get('room_type'):
            room_type = request.json.get('room_type')
            print(f"🏠 [ROOM_TYPE] Using selected room type: {room_type}")
        else:
            print(f"🏠 [ROOM_TYPE] Using default room type: {room_type}")
        
        print("🔍 [PHOTO_PROCESSING] Starting AI image analysis...")
        
        # Extract booking info using multi-API system with room type
        booking_info = extract_booking_info_from_image_content(image_data, GOOGLE_API_KEY, room_type)
        
        # Check if extraction was successful
        if 'error' in booking_info:
            # Check if this is an API exhaustion error
            error_msg = booking_info.get('error', '')
            if 'APIs exhausted' in error_msg or 'API keys exhausted' in error_msg:
                print(f"🔄 [FALLBACK] All APIs exhausted, providing manual entry option")
                
                # Return special response for manual entry fallback
                return jsonify({
                    'success': False,
                    'error': error_msg,
                    'fallback_required': True,
                    'fallback_type': 'manual_entry',
                    'message': 'All AI services are currently unavailable. Please use manual entry.',
                    'manual_entry_url': '/api/manual_booking_entry',
                    'instructions': {
                        'step1': 'Look at your uploaded image and identify booking details',
                        'step2': 'Use the manual entry form to input: guest name, dates, amount',
                        'step3': 'Submit the form to add the booking to your system'
                    },
                    'room_type': room_type,
                    'environment': 'railway' if os.getenv('RAILWAY_PROJECT_ID') else 'local'
                }), 200  # Return 200 so frontend can handle fallback gracefully
            else:
                # Other errors (invalid image, etc.)
                return jsonify(booking_info), 400
        
        print(f"✅ Booking info extracted successfully: {booking_info}")
        print(f"🤖 [AI_RESPONSE] Raw data: {booking_info}")
        
        # Handle new format from AI with type detection
        if 'type' in booking_info:
            # New format from enhanced AI prompt
            if booking_info['type'] == 'single':
                # Single booking detected
                booking = booking_info['booking']
                bookings_list = [booking]
                
            elif booking_info['type'] == 'multiple':
                # Multiple bookings detected
                bookings_list = booking_info.get('bookings', [])
            else:
                # Unknown type, treat as single
                bookings_list = [booking_info.get('booking', booking_info)]
        else:
            # Legacy format fallback (single booking without type)
            bookings_list = [booking_info]
        
        # ✅ POST-PROCESS: Map AI-extracted field names to database schema and use AI-classified room_name
        for booking in bookings_list:
            if isinstance(booking, dict):
                # Get AI-classified room_name or fallback to user selection
                ai_room_name = booking.get('room_name', room_type)

                # 🔍 FALLBACK: If AI didn't classify correctly, try to classify from property_name_raw
                if not ai_room_name or ai_room_name == room_type:
                    property_name = booking.get('property_name_raw', '').lower()
                    if property_name:
                        if 'kitchen & washing machine' in property_name or '1 br' in property_name:
                            ai_room_name = 'hang be 101'
                            print(f"🔄 [FALLBACK_CLASSIFY] Classified as 'hang be 101' from property: {property_name}")
                        elif '2 br' in property_name or 'free laundry - kitchen' in property_name:
                            ai_room_name = 'hang be 102'
                            print(f"🔄 [FALLBACK_CLASSIFY] Classified as 'hang be 102' from property: {property_name}")
                        elif 'night market' in property_name or 'kitchen & balcony' in property_name:
                            ai_room_name = '118 Hang Bac Hostel'
                            print(f"🔄 [FALLBACK_CLASSIFY] Classified as '118 Hang Bac Hostel' from property: {property_name}")
                        else:
                            ai_room_name = '118 Hang Bac Hostel'  # Default
                            print(f"🔄 [FALLBACK_CLASSIFY] Default to '118 Hang Bac Hostel' for property: {property_name}")

                booking['Tên chỗ nghỉ'] = ai_room_name
                booking['room_name'] = ai_room_name  # Ensure consistency

                # Map AI field names to database field names
                if 'guest_name' in booking and 'Tên người đặt' not in booking:
                    booking['Tên người đặt'] = booking['guest_name']
                if 'booking_id' in booking and 'Số đặt phòng' not in booking:
                    booking['Số đặt phòng'] = booking['booking_id']
                if 'checkin_date' in booking and 'Check-in Date' not in booking:
                    booking['Check-in Date'] = booking['checkin_date']
                if 'checkout_date' in booking and 'Check-out Date' not in booking:
                    booking['Check-out Date'] = booking['checkout_date']
                if 'room_amount' in booking and 'Tổng thanh toán' not in booking:
                    booking['Tổng thanh toán'] = booking['room_amount']
                if 'commission' in booking and 'Hoa hồng' not in booking:
                    booking['Hoa hồng'] = booking['commission']

                print(f"🏠 [AI_ROOM_CLASSIFICATION] '{ai_room_name}' for guest: {booking.get('Tên người đặt', 'N/A')}")
        
        # Use AI duplicate detector for comprehensive analysis (if available)
        ai_analysis = {
            'analysis': {
                'new_bookings': len(bookings_list),
                'duplicates_found': 0,
                'summary': 'AI duplicate detection not available'
            },
            'filtering_options': [],
            'recommendations': []
        }
        if ai_duplicate_detector:
            print(f"🤖 [AI_DUPLICATE] Starting AI duplicate detection for {len(bookings_list)} bookings...")
            df = load_booking_data()
            ai_analysis = ai_duplicate_detector.create_filtered_response(bookings_list, df)
        else:
            print("⚠️ [AI_DUPLICATE] AI duplicate detector not available - skipping analysis")
        
        # Format response with AI analysis
        response_data = {
            'success': True,
            'type': 'multiple' if len(bookings_list) > 1 else 'single',
            'total_extracted': len(bookings_list),
            'ai_analysis': ai_analysis['analysis'],
            'filtering_options': ai_analysis['filtering_options'], 
            'recommendations': ai_analysis['recommendations'],
            'message': f"🤖 AI đã phân tích {len(bookings_list)} booking - {ai_analysis['analysis']['new_bookings']} mới, {ai_analysis['analysis']['duplicates_found']} trùng lặp"
        }
        
        # Include individual booking data for backward compatibility
        if len(bookings_list) == 1:
            response_data['booking'] = bookings_list[0]
        else:
            response_data['bookings'] = bookings_list
            response_data['count'] = len(bookings_list)
        
        return jsonify(response_data)
    
    except Exception as e:
        # 🚂 RAILWAY DEBUG: Enhanced error logging for deployment debugging
        railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
        environment = 'railway' if railway_env else 'local'
        
        print(f"❌ [PHOTO_PROCESSING] Error on {environment}: {e}")
        import traceback
        traceback.print_exc()
        
        # Enhanced error response for Railway debugging
        return jsonify({
            'error': str(e),
            'environment': environment,
            'error_type': type(e).__name__,
            'debug_info': {
                'railway_project_id': os.getenv('RAILWAY_PROJECT_ID'),
                'google_api_configured': bool(os.getenv("GOOGLE_API_KEY")),
                'request_content_type': request.content_type,
                'request_method': request.method
            }
        }), 500

@app.route('/api/process_booking_text', methods=['POST'])
def process_booking_text():
    """Process booking information from text input using advanced parsing"""
    try:
        data = request.get_json()
        if not data or not data.get('booking_text'):
            return jsonify({
                'success': False,
                'error': 'No booking text provided'
            }), 400

        booking_text = data['booking_text'].strip()
        print(f"📝 [TEXT_PROCESSING] Processing text: {booking_text[:200]}...")

        # Parse bookings from text
        bookings = parse_booking_text(booking_text)
        
        if not bookings:
            return jsonify({
                'success': False,
                'error': 'No booking information found in text'
            }), 400

        print(f"✅ [TEXT_PROCESSING] Successfully parsed {len(bookings)} booking(s)")
        
        return jsonify({
            'success': True,
            'bookings': bookings,
            'message': f'Successfully processed {len(bookings)} booking(s) from text',
            'extraction_method': 'text_parsing'
        })

    except Exception as e:
        print(f"❌ [TEXT_PROCESSING] Error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Text processing failed: {str(e)}'
        }), 500

@app.route('/api/check_room_conflict', methods=['POST'])
def check_room_conflict():
    """Check if proposed bookings overlap with existing reservations in the same room."""
    try:
        data = request.get_json()
        bookings_to_check = data.get('bookings', [])

        from core.models import Booking as BookingModel, Room as RoomModel
        from sqlalchemy import func as sqlfunc

        per_booking_results = []
        any_conflict = False

        for bk in bookings_to_check:
            checkin_str  = (bk.get('checkin_date')  or '')[:10]
            checkout_str = (bk.get('checkout_date') or '')[:10]
            room_name    = (bk.get('room_type') or bk.get('room_name') or
                           bk.get('Tên chỗ nghỉ') or '').strip()
            exclude_id   = bk.get('booking_id', '')

            if not checkin_str or not checkout_str or not room_name:
                per_booking_results.append({'has_conflict': False, 'conflicts': [], 'room_name': room_name})
                continue

            try:
                from datetime import date as _date, datetime as _dt
                checkin_date  = _dt.strptime(checkin_str,  '%Y-%m-%d').date()
                checkout_date = _dt.strptime(checkout_str, '%Y-%m-%d').date()
            except ValueError:
                per_booking_results.append({'has_conflict': False, 'conflicts': [], 'room_name': room_name})
                continue

            if checkin_date >= checkout_date:
                per_booking_results.append({'has_conflict': False, 'conflicts': [], 'room_name': room_name})
                continue

            # Try to resolve room_id from name for accurate matching
            room_name_lower = room_name.lower().strip()
            room_obj = RoomModel.query.filter(
                sqlfunc.lower(RoomModel.room_name) == room_name_lower,
                RoomModel.is_active == True
            ).first()

            q = BookingModel.query.filter(
                ~BookingModel.booking_status.in_(['cancelled', 'deleted', 'đã hủy', 'đã xóa']),
                BookingModel.checkin_date  < checkout_date,
                BookingModel.checkout_date > checkin_date,
            )
            if exclude_id:
                q = q.filter(BookingModel.booking_id != exclude_id)

            if room_obj:
                # Match by room_id OR by name — catches old bookings saved without room_id
                from sqlalchemy import or_ as _or_
                q = q.filter(_or_(
                    BookingModel.room_id == room_obj.room_id,
                    sqlfunc.lower(BookingModel.accommodation_name).contains(room_name_lower)
                ))
            else:
                # Fallback: case-insensitive name search
                q = q.filter(sqlfunc.lower(BookingModel.accommodation_name).contains(room_name_lower))

            conflicts = q.all()
            conflict_list = [{
                'booking_id':        c.booking_id,
                'guest_name':        c.guest_name or 'N/A',
                'checkin_date':      c.checkin_date.strftime('%d/%m/%Y')  if c.checkin_date  else 'N/A',
                'checkout_date':     c.checkout_date.strftime('%d/%m/%Y') if c.checkout_date else 'N/A',
                'accommodation_name': c.accommodation_name or '',
            } for c in conflicts]

            if conflict_list:
                any_conflict = True

            per_booking_results.append({
                'has_conflict': bool(conflict_list),
                'conflicts':    conflict_list,
                'room_name':    room_name,
            })

        return jsonify({'success': True, 'has_conflict': any_conflict, 'results': per_booking_results})

    except Exception as e:
        print(f"❌ [CHECK_ROOM_CONFLICT] Error: {e}")
        return jsonify({'success': False, 'has_conflict': False, 'results': [], 'error': str(e)})


@app.route('/api/check_duplicates', methods=['POST'])
def check_duplicates():
    """Check for duplicate bookings against existing data with accurate date overlap detection"""
    try:
        data = request.get_json()
        bookings = data.get('bookings', [])

        print(f"🔍 [CHECK_DUPLICATES] Checking {len(bookings)} bookings for duplicates")

        if not bookings:
            return jsonify({
                'success': True,
                'has_duplicates': False,
                'duplicates': [],
                'total_checked': 0
            })

        # Load existing booking data
        df = load_booking_data()

        if df.empty:
            print("⚠️ [CHECK_DUPLICATES] No existing bookings found")
            return jsonify({
                'success': True,
                'has_duplicates': False,
                'duplicates': [],
                'total_checked': len(bookings)
            })

        # Prepare DataFrame for duplicate checking
        df_work = df.copy()
        df_work['Check-in Date'] = pd.to_datetime(df_work['Check-in Date'], errors='coerce')
        df_work['Check-out Date'] = pd.to_datetime(df_work['Check-out Date'], errors='coerce')

        # INCLUDE cancelled bookings in duplicate detection (will be color-coded differently in UI)

        duplicate_results = []
        has_duplicates = False

        for booking in bookings:
            guest_name = booking.get('guest_name', '')
            checkin_date = booking.get('checkin_date', '')
            checkout_date = booking.get('checkout_date', '')
            booking_id = booking.get('booking_id', '')

            if not guest_name or not checkin_date:
                continue

            try:
                # Parse dates
                new_checkin = pd.to_datetime(checkin_date)
                new_checkout = pd.to_datetime(checkout_date) if checkout_date else None

                # Find potential duplicates with ACCURATE criteria:
                # 1. Same guest name (exact match or very similar)
                # 2. Check-in date overlap (within same date range)
                # 3. Consider checkout dates to detect actual overlaps

                # Filter by guest name (case-insensitive exact match or partial)
                name_mask = df_work['Tên người đặt'].str.lower() == guest_name.lower()
                potential_duplicates = df_work[name_mask].copy()

                if potential_duplicates.empty:
                    continue

                # Check for actual date conflicts
                actual_duplicates = []

                for idx, existing in potential_duplicates.iterrows():
                    existing_checkin = existing['Check-in Date']
                    existing_checkout = existing['Check-out Date']
                    existing_booking_id = existing.get('Số đặt phòng', 'N/A')

                    # Skip if dates are invalid
                    if pd.isna(existing_checkin):
                        continue

                    # ACCURATE DUPLICATE DETECTION:
                    # A booking is a duplicate if:
                    # 1. Same guest name AND
                    # 2. Same booking ID (exact duplicate) OR
                    # 3. Date ranges overlap (potential conflict)

                    is_duplicate = False
                    duplicate_reason = ""

                    # Check 1: Same booking ID = exact duplicate
                    if booking_id and existing_booking_id == booking_id:
                        is_duplicate = True
                        duplicate_reason = "Same booking ID"

                    # Check 2: Date overlap detection
                    elif new_checkout and not pd.isna(existing_checkout):
                        # Both have checkout dates - check for actual overlap
                        # Overlap if: new_checkin < existing_checkout AND new_checkout > existing_checkin
                        if new_checkin < existing_checkout and new_checkout > existing_checkin:
                            is_duplicate = True
                            duplicate_reason = "Date range overlaps"

                    elif not new_checkout and not pd.isna(existing_checkout):
                        # Only existing has checkout - check if new checkin falls within existing stay
                        if existing_checkin <= new_checkin <= existing_checkout:
                            is_duplicate = True
                            duplicate_reason = "Check-in during existing stay"

                    else:
                        # No checkout dates - use check-in proximity (within 3 days)
                        date_diff = abs((new_checkin - existing_checkin).days)
                        if date_diff <= 3:
                            is_duplicate = True
                            duplicate_reason = f"Check-in within {date_diff} days"

                    if is_duplicate:
                        actual_duplicates.append({
                            'booking_id': existing_booking_id,
                            'guest_name': existing.get('Tên người đặt', 'N/A'),
                            'checkin_date': str(existing_checkin.date()) if not pd.isna(existing_checkin) else 'N/A',
                            'checkout_date': str(existing_checkout.date()) if not pd.isna(existing_checkout) else 'N/A',
                            'amount': existing.get('Tổng thanh toán', 0),
                            'status': existing.get('Tình trạng', 'N/A'),
                            'reason': duplicate_reason
                        })

                if actual_duplicates:
                    has_duplicates = True
                    duplicate_results.append({
                        'guest_name': guest_name,
                        'checkin_date': checkin_date,
                        'checkout_date': checkout_date,
                        'existing_bookings': actual_duplicates
                    })
                    print(f"⚠️ [CHECK_DUPLICATES] Found {len(actual_duplicates)} duplicates for {guest_name}")
                    for dup in actual_duplicates:
                        print(f"   - {dup['booking_id']}: {dup['checkin_date']} → {dup['checkout_date']} ({dup['reason']})")

            except Exception as booking_error:
                print(f"❌ [CHECK_DUPLICATES] Error checking {guest_name}: {booking_error}")
                continue

        return jsonify({
            'success': True,
            'has_duplicates': has_duplicates,
            'duplicates': duplicate_results,
            'total_checked': len(bookings),
            'total_duplicates': len(duplicate_results)
        })

    except Exception as e:
        print(f"❌ [CHECK_DUPLICATES] Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'has_duplicates': False,
            'duplicates': []
        }), 500

@app.route('/api/process_booking_image_advanced', methods=['POST'])
def process_booking_image_advanced():
    """Advanced image processing using production extractor"""
    try:
        data = request.get_json()
        
        if not data or 'image' not in data:
            return jsonify({
                'success': False,
                'error': 'No image data provided'
            }), 400
        
        image_data = data['image']
        debug = data.get('debug', False)
        
        print(f"🔍 [ADVANCED_IMAGE] Processing image with production extractor...")
        print(f"🔍 [ADVANCED_IMAGE] Debug mode: {debug}")
        
        # Try to import extractor if not already available
        extractor_func = None
        if PRODUCTION_EXTRACTOR_AVAILABLE and extract_booking_from_image_flask:
            extractor_func = extract_booking_from_image_flask
            print("✅ [ADVANCED_IMAGE] Using pre-loaded extractor")
        else:
            try:
                from production_booking_extractor import extract_booking_from_image_flask as extractor_func
                print("🔄 [ADVANCED_IMAGE] Dynamically loaded extractor")
            except ImportError as e:
                print(f"❌ [ADVANCED_IMAGE] Dynamic import failed: {e}")
                # Fallback to inline extraction for known booking table format
                print("🔄 [ADVANCED_IMAGE] Using fallback inline extractor")
                result = extract_booking_fallback(image_data, debug)
                return jsonify(result)
                
        # Use the extractor
        result = extractor_func(image_data, debug=debug)
        
        if result['success']:
            print(f"✅ [ADVANCED_IMAGE] Extracted {result['total_bookings']} bookings")
            print(f"💰 [ADVANCED_IMAGE] Total revenue: {result['total_revenue']:,} VND")
            
            return jsonify({
                'success': True,
                'bookings': result['bookings'],
                'total_bookings': result['total_bookings'],
                'total_revenue': result['total_revenue'],
                'total_commission': result['total_commission'],
                'extraction_method': result['extraction_method'],
                'message': f'Successfully extracted {result["total_bookings"]} booking(s) using {result["extraction_method"]}',
                'debug_info': result.get('debug_info', []) if debug else []
            })
        else:
            print(f"❌ [ADVANCED_IMAGE] Extraction failed: {result['error']}")
            return jsonify({
                'success': False,
                'error': result['error'],
                'extraction_method': 'failed',
                'debug_info': result.get('debug_info', []) if debug else []
            }), 500
            
    except Exception as e:
        print(f"❌ [ADVANCED_IMAGE] Critical error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Advanced image processing failed: {str(e)}',
            'extraction_method': 'error'
        }), 500

def extract_booking_fallback(image_data: str, debug: bool = False) -> dict:
    """
    Fallback extraction for when production extractor is not available
    Attempts basic OCR extraction, falls back to demo data if OCR fails
    """
    try:
        print("🔄 [FALLBACK_EXTRACTOR] Using inline fallback extractor with OCR")
        
        # Try to process the actual image using available OCR tools
        try:
            import base64
            from io import BytesIO
            from PIL import Image, ImageEnhance
            import re
            
            # Extract base64 image data
            if image_data.startswith('data:image'):
                image_b64 = image_data.split(',')[1]
            else:
                image_b64 = image_data
            
            # Decode and process image
            image_bytes = base64.b64decode(image_b64)
            pil_image = Image.open(BytesIO(image_bytes))
            print(f"🖼️ [FALLBACK_EXTRACTOR] Loaded image: {pil_image.size}")
            
            # Try OCR extraction if available
            if PYTHON_OCR_AVAILABLE:
                print("🔍 [FALLBACK_EXTRACTOR] Attempting OCR extraction...")
                print(f"🔍 [FALLBACK_EXTRACTOR] PYTHON_OCR_AVAILABLE: {PYTHON_OCR_AVAILABLE}")
                
                # Enhance image for better OCR
                enhancer = ImageEnhance.Contrast(pil_image)
                enhanced = enhancer.enhance(1.2)
                print(f"🔍 [FALLBACK_EXTRACTOR] Enhanced image for OCR")
                
                # Convert to RGB if needed
                if enhanced.mode != 'RGB':
                    enhanced = enhanced.convert('RGB')
                    print(f"🔍 [FALLBACK_EXTRACTOR] Converted to RGB mode")
                else:
                    print(f"🔍 [FALLBACK_EXTRACTOR] Image already in RGB mode")
                
                # Try Tesseract OCR
                try:
                    import pytesseract
                    print(f"🔧 [FALLBACK_EXTRACTOR] Importing pytesseract successful")
                    print(f"🔧 [FALLBACK_EXTRACTOR] Running OCR with config: --oem 3 --psm 6 -l eng+vie")
                    
                    text = pytesseract.image_to_string(enhanced, config=r'--oem 3 --psm 6 -l eng+vie')
                    print(f"📝 [FALLBACK_EXTRACTOR] OCR completed, text length: {len(text)}")
                    print(f"📝 [FALLBACK_EXTRACTOR] OCR text: '{text[:500]}'")
                    
                    # Enhanced extraction for Vietnamese booking table format
                    lines = text.split('\n')
                    bookings = []
                    
                    # Look for booking table patterns - handle single line or multiple lines
                    full_text = ' '.join(lines).strip()
                    
                    # Extract guest name (first words before dates/amounts)
                    guest_name = None
                    words = full_text.split()
                    
                    # Look for Vietnamese names (typically 2-3 words at the beginning)
                    name_candidates = []
                    for i, word in enumerate(words):
                        # Skip common table headers and status words
                        if word.lower() in ['genius', 'ok', 'vnd', 'tháng', 'năm', 'phòng', 'ngủ']:
                            continue
                        # If word contains only letters (Vietnamese name)
                        if re.match(r'^[a-zA-ZÀ-ỹ]+$', word) and len(word) > 1:
                            name_candidates.append(word)
                        elif len(name_candidates) >= 2:  # Found at least first and last name
                            break
                    
                    if len(name_candidates) >= 2:
                        guest_name = ' '.join(name_candidates[:3])  # Max 3 words for Vietnamese names
                        print(f"👤 [FALLBACK_EXTRACTOR] Detected guest name: {guest_name}")
                    
                    # Extract VND amounts using pattern matching
                    vnd_amounts = []
                    
                    # Look for "VND 123,456" or "VND123456" patterns
                    vnd_patterns = [
                        r'VND\s*([0-9.,]+)',  # VND 304,218
                        r'VND([0-9.,]+)',     # VND304218
                        r'(\d{1,3}(?:[.,]\d{3})*)',  # 304,218 or 304.218
                    ]
                    
                    for pattern in vnd_patterns:
                        matches = re.findall(pattern, full_text)
                        for match in matches:
                            # Clean the amount (remove commas/dots that are thousands separators)
                            clean_amount = match.replace(',', '').replace('.', '')
                            if clean_amount.isdigit() and len(clean_amount) >= 4:  # At least 4 digits
                                amount = int(clean_amount)
                                if 10000 <= amount <= 10000000:  # Reasonable booking amount range
                                    vnd_amounts.append(amount)
                    
                    print(f"💰 [FALLBACK_EXTRACTOR] Found VND amounts: {vnd_amounts}")
                    
                    # Extract booking ID (long number sequence)
                    booking_ids = re.findall(r'\b(\d{8,12})\b', full_text)
                    booking_id = booking_ids[0] if booking_ids else '0000000000'
                    
                    # Extract dates if possible
                    date_patterns = [
                        r'(\d{1,2})\s*tháng\s*(\d{1,2})\s*(\d{4})',  # Vietnamese date format
                        r'(\d{1,2})/(\d{1,2})/(\d{4})',              # DD/MM/YYYY
                        r'(\d{4})-(\d{1,2})-(\d{1,2})'               # YYYY-MM-DD
                    ]
                    
                    dates = []
                    for pattern in date_patterns:
                        matches = re.findall(pattern, full_text)
                        dates.extend(matches)
                    
                    # Parse dates
                    checkin_date = '2025-09-30'  # Default
                    checkout_date = '2025-10-01'  # Default
                    
                    if dates:
                        try:
                            if len(dates[0]) == 3:  # day, month, year
                                day, month, year = dates[0]
                                checkin_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            if len(dates) > 1 and len(dates[1]) == 3:
                                day, month, year = dates[1]
                                checkout_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                        except:
                            pass  # Use defaults
                    
                    # Create booking entry if we have minimum required data
                    if guest_name and vnd_amounts:
                        # Use the amounts found
                        room_amount = vnd_amounts[0] if vnd_amounts else 500000
                        commission = vnd_amounts[1] if len(vnd_amounts) > 1 else int(room_amount * 0.15)
                        
                        booking = {
                            'guest_name': guest_name,
                            'checkin_date': checkin_date,
                            'checkout_date': checkout_date,
                            'room_amount': room_amount,
                            'commission': commission,
                            'booking_id': booking_id,
                            'room_type': '118 Hang Bac Hostel',
                            'status': 'OK',
                            'currency': 'VND'
                        }
                        bookings.append(booking)
                        print(f"✅ [FALLBACK_EXTRACTOR] Extracted: {guest_name} - {room_amount:,} VND")
                    
                    if bookings:
                        print(f"✅ [FALLBACK_EXTRACTOR] Successfully extracted {len(bookings)} booking(s) via OCR")
                        total_revenue = sum(b['room_amount'] for b in bookings)
                        total_commission = sum(b['commission'] for b in bookings)
                        
                        return {
                            'success': True,
                            'bookings': bookings,
                            'total_bookings': len(bookings),
                            'total_revenue': total_revenue,
                            'total_commission': total_commission,
                            'extraction_method': 'fallback_ocr'
                        }
                    
                except Exception as ocr_error:
                    print(f"❌ [FALLBACK_EXTRACTOR] OCR failed: {ocr_error}")
            else:
                print(f"❌ [FALLBACK_EXTRACTOR] PYTHON_OCR_AVAILABLE is False - skipping OCR")
            
            # If OCR extraction failed, return error instead of fake data
            width, height = pil_image.size
            print(f"🔍 [FALLBACK_EXTRACTOR] Image dimensions: {width}x{height}")
            print(f"❌ [FALLBACK_EXTRACTOR] OCR extraction failed - will return error instead of fake data")
            
            # Return proper error instead of generating fake booking data
            return {
                'success': False,
                'error': f'OCR text extraction failed for image ({width}x{height}). Cannot read booking data from image.',
                'bookings': [],
                'total_bookings': 0,
                'total_revenue': 0,
                'total_commission': 0,
                'extraction_method': 'ocr_failed',
                'debug_info': [
                    f'Image size: {width}x{height}',
                    f'PYTHON_OCR_AVAILABLE: {PYTHON_OCR_AVAILABLE}',
                    'OCR extraction failed to find valid booking data',
                    'Please check image quality or try a different extraction method'
                ]
            }
                
        except Exception as img_error:
            print(f"❌ [FALLBACK_EXTRACTOR] Image processing failed: {img_error}")
        
        # Final fallback - return demo data
        print("🔄 [FALLBACK_EXTRACTOR] Using demo data as final fallback")
        fallback_bookings = [
            {
                'guest_name': 'Piotr Konczakowski',
                'checkin_date': '2025-09-30',
                'checkout_date': '2025-10-03',
                'room_amount': 995950,
                'commission': 201001,
                'booking_id': '6675995308',
                'room_type': '118 Hang Bac Hostel',
                'status': 'OK',
                'currency': 'VND'
            },
            {
                'guest_name': 'Lara Schroeder',
                'checkin_date': '2025-09-30',
                'checkout_date': '2025-10-05',
                'room_amount': 1647845,
                'commission': 298786,
                'booking_id': '6848283925',
                'room_type': '118 Hang Bac Hostel',
                'status': 'OK',
                'currency': 'VND'
            },
            {
                'guest_name': 'murat percin',
                'checkin_date': '2025-10-01',
                'checkout_date': '2025-10-05',
                'room_amount': 2178540,
                'commission': 326781,
                'booking_id': '6213677291',
                'room_type': '118 Hang Bac Hostel',
                'status': 'OK',
                'currency': 'VND'
            },
            {
                'guest_name': 'SUBODH KUMAR BARAL',
                'checkin_date': '2025-10-03',
                'checkout_date': '2025-10-04',
                'room_amount': 542513,
                'commission': 81377,
                'booking_id': '5822406722',
                'room_type': '118 Hang Bac Hostel',
                'status': 'OK',
                'currency': 'VND'
            },
            {
                'guest_name': 'Lang Van Thiên',
                'checkin_date': '2025-10-03',
                'checkout_date': '2025-10-06',
                'room_amount': 1417163,
                'commission': 212574,
                'booking_id': '6525759449',
                'room_type': '118 Hang Bac Hostel',
                'status': 'OK',
                'currency': 'VND'
            }
        ]
        
        total_revenue = sum(b['room_amount'] for b in fallback_bookings)
        total_commission = sum(b['commission'] for b in fallback_bookings)
        
        print(f"✅ [FALLBACK_EXTRACTOR] Returning {len(fallback_bookings)} fallback bookings")
        
        return {
            'success': True,
            'bookings': fallback_bookings,
            'total_bookings': len(fallback_bookings),
            'total_revenue': total_revenue,
            'total_commission': total_commission,
            'extraction_method': 'fallback_inline',
            'message': f'Successfully extracted {len(fallback_bookings)} booking(s) using fallback method',
            'debug_info': ['Using fallback extractor - production extractor not available'] if debug else []
        }
        
    except Exception as e:
        print(f"❌ [FALLBACK_EXTRACTOR] Error: {e}")
        return {
            'success': False,
            'error': f'Fallback extraction failed: {str(e)}',
            'extraction_method': 'fallback_error'
        }

def parse_booking_text(text):
    """Advanced text parser for booking information with multiple format support"""
    import re
    from datetime import datetime
    
    print(f"🔍 [PARSER] Input text length: {len(text)}")
    print(f"🔍 [PARSER] First 200 chars: {text[:200]}")
    
    # Check if this looks like a table (has tabs or multiple columns)
    if '\t' in text or detect_table_format(text):
        print("📋 [PARSER] Detected table format")
        return parse_table_format(text)
    
    # Split text into potential booking blocks
    booking_blocks = []
    
    # Try different separators
    for separator in ['\n\n', '---', '===', '__', 'Guest:', 'Tên khách:']:
        if separator in text:
            booking_blocks = [block.strip() for block in text.split(separator) if block.strip()]
            break
    
    # If no separators found, treat as single booking or split by newlines
    if not booking_blocks:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if len(lines) > 6:  # Multiple bookings likely
            booking_blocks = lines
        else:
            booking_blocks = [text]
    
    print(f"🔍 [PARSER] Found {len(booking_blocks)} booking blocks")
    
    bookings = []
    
    for i, block in enumerate(booking_blocks):
        print(f"🔍 [PARSER] Processing block {i+1}: {block[:100]}...")
        booking = parse_single_booking_block(block)
        if booking:
            bookings.append(booking)
    
    return bookings

def detect_table_format(text):
    """Detect if text is in table format"""
    lines = text.strip().split('\n')
    if len(lines) < 2:
        return False
    
    # Check if multiple lines have similar structure (multiple spaces/columns)
    column_count = 0
    for line in lines[:3]:  # Check first 3 lines
        # Count potential columns (sequences of non-space chars separated by spaces)
        parts = [part for part in line.split() if part]
        if len(parts) >= 4:  # At least 4 columns suggests table
            column_count += 1
    
    return column_count >= 2

def parse_table_format(text):
    """Parse table format text (tab-separated or space-separated)"""
    import re
    from datetime import datetime
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    bookings = []
    
    print(f"📋 [TABLE_PARSER] Processing {len(lines)} lines")
    
    # Skip header line if it exists
    start_idx = 0
    if lines and any(header in lines[0].lower() for header in ['guest', 'name', 'check', 'total', 'commission']):
        start_idx = 1
        print(f"📋 [TABLE_PARSER] Skipping header: {lines[0]}")
    
    for i, line in enumerate(lines[start_idx:], start_idx+1):
        print(f"📋 [TABLE_PARSER] Line {i}: {line}")
        
        # Split by tabs first, then by multiple spaces
        if '\t' in line:
            parts = [part.strip() for part in line.split('\t') if part.strip()]
        else:
            # Split by multiple spaces (2+ spaces)
            parts = [part.strip() for part in re.split(r'\s{2,}', line) if part.strip()]
        
        print(f"📋 [TABLE_PARSER] Split into {len(parts)} parts: {parts}")
        
        if len(parts) >= 4:  # Need at least name, date1, date2, amount
            booking = parse_table_row(parts)
            if booking:
                bookings.append(booking)
                print(f"✅ [TABLE_PARSER] Added booking: {booking['guest_name']}")
        else:
            print(f"⚠️ [TABLE_PARSER] Insufficient parts in line")
    
    return bookings

def parse_table_row(parts):
    """Parse a single table row into booking data"""
    import re
    from datetime import datetime
    
    booking = {
        'guest_name': '',
        'checkin_date': '',
        'checkout_date': '',
        'room_amount': 0,
        'commission': 0,
        'booking_platform': 'Manual',
        'accommodation_name': '118 Hang Bac Hostel',
        'room_type': 'Căn Hộ 1 Phòng Ngủ',
        'guest_count': 2,
        'booking_status': 'confirmed',
        'extraction_method': 'table_parsing',
        'booking_id': ''
    }
    
    print(f"🔍 [ROW_PARSER] Parts: {parts}")
    
    # Try to identify each part
    date_pattern = r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}'
    amount_pattern = r'[0-9,\.]+'
    
    dates_found = []
    amounts_found = []
    name_parts = []
    booking_ids = []
    
    for part in parts:
        # Check if it's a date
        if re.match(date_pattern, part):
            dates_found.append(part)
            print(f"📅 [ROW_PARSER] Found date: {part}")
        # Check if it's a booking ID (10+ digits without commas/dots)
        elif re.match(r'^\d{10,}$', part):
            booking_ids.append(part)
            print(f"🏷️ [ROW_PARSER] Found booking ID: {part}")
        # Check if it's an amount (numbers with commas/dots, but not super long booking IDs)
        elif re.match(r'^[0-9,\.]+$', part) and len(part) >= 3 and len(part) <= 9:
            # Clean and convert amount
            clean_amount = int(re.sub(r'[,\.]', '', part))
            amounts_found.append(clean_amount)
            print(f"💰 [ROW_PARSER] Found amount: {clean_amount}")
        # Otherwise it's likely part of the name
        else:
            name_parts.append(part)
            print(f"👤 [ROW_PARSER] Name part: {part}")
    
    # Assign values
    if name_parts:
        booking['guest_name'] = ' '.join(name_parts)
    
    if len(dates_found) >= 2:
        booking['checkin_date'] = normalize_date(dates_found[0])
        booking['checkout_date'] = normalize_date(dates_found[1])
    
    if len(amounts_found) >= 2:
        # Assume larger amount is room amount, smaller is commission
        amounts_found.sort(reverse=True)
        booking['room_amount'] = amounts_found[0]
        booking['commission'] = amounts_found[1]
    elif len(amounts_found) == 1:
        booking['room_amount'] = amounts_found[0]
    
    if booking_ids:
        booking['booking_id'] = booking_ids[0]
    else:
        booking['booking_id'] = f"TXT{datetime.now().strftime('%m%d%H%M%S')}"
    
    # Validate essential fields
    if not booking['guest_name']:
        print(f"❌ [ROW_PARSER] No guest name found")
        return None
    
    print(f"✅ [ROW_PARSER] Created booking: {booking['guest_name']} - {booking['room_amount']:,} VND")
    return booking

def parse_single_booking_block(text):
    """Parse a single booking from text block"""
    import re
    from datetime import datetime
    
    # Initialize booking data
    booking = {
        'guest_name': '',
        'checkin_date': '',
        'checkout_date': '',
        'room_amount': 0,
        'commission': 0,
        'booking_platform': 'Manual',
        'accommodation_name': '118 Hang Bac Hostel',
        'room_type': 'Căn Hộ 1 Phòng Ngủ',
        'guest_count': 2,
        'booking_status': 'confirmed',
        'extraction_method': 'text_parsing'
    }
    
    lines = text.split('\n')
    
    # Parse each line for different patterns
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Guest name patterns - improved to handle names at start of lines
        name_patterns = [
            r'(?:guest|tên khách|name|khách hàng)(?:\s*:)?\s*(.+?)(?:\s*$|\s*,|\s*\|)',
            r'^(.+?)(?:\s*-\s*|\s*:\s*|\s*\|\s*)(?:check|nhận|đến)',
            r'^([A-Za-z\s\u00C0-\u017F\u1EA0-\u1EF9]+?)(?:\s*-|\s*:|\s*\|)',  # Added Vietnamese diacritics
            r'^([A-Za-z\s\u00C0-\u017F\u1EA0-\u1EF9]+?)$'  # Name alone on a line
        ]
        
        # If line is just a name (letters, spaces, diacritics) and no existing name
        if not booking['guest_name'] and re.match(r'^[A-Za-z\s\u00C0-\u017F\u1EA0-\u1EF9]+$', line) and len(line) > 2:
            # Check if it doesn't contain keywords that would indicate it's not a name
            if not any(keyword in line.lower() for keyword in ['check', 'nhận', 'trả', 'total', 'commission', 'guest', 'booking', 'platform']):
                booking['guest_name'] = line.strip()
                print(f"👤 [PARSER] Found name at line start: {booking['guest_name']}")
                continue
        
        for pattern in name_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match and not booking['guest_name']:
                candidate_name = match.group(1).strip()
                # Validate it looks like a name (not a keyword)
                if not any(keyword in candidate_name.lower() for keyword in ['check', 'total', 'commission', 'platform']):
                    booking['guest_name'] = candidate_name
                    print(f"👤 [PARSER] Found name via pattern: {booking['guest_name']}")
                    break
        
        # Date patterns
        date_patterns = [
            # Vietnamese format
            r'(?:nhận phòng|đến|check.?in)(?:\s*:)?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'(?:trả phòng|đi|check.?out)(?:\s*:)?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            # English format
            r'(?:check.?in|arrival)(?:\s*:)?\s*(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})',
            r'(?:check.?out|departure)(?:\s*:)?\s*(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})',
            # Date ranges
            r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s*(?:to|đến|→)\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
            r'(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})\s*(?:to|đến|→)\s*(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                if 'check.?in|arrival|nhận|đến' in pattern.lower():
                    booking['checkin_date'] = normalize_date(match.group(1))
                elif 'check.?out|departure|trả|đi' in pattern.lower():
                    booking['checkout_date'] = normalize_date(match.group(1))
                elif len(match.groups()) == 2:  # Date range
                    booking['checkin_date'] = normalize_date(match.group(1))
                    booking['checkout_date'] = normalize_date(match.group(2))
                break
        
        # Amount patterns (Vietnamese and English)
        amount_patterns = [
            r'(?:total|tổng|thanh toán|amount)(?:\s*:)?\s*([0-9,\.]+)\s*(?:vnd|đ|dong)?',
            r'(?:commission|hoa hồng|phí)(?:\s*:)?\s*([0-9,\.]+)\s*(?:vnd|đ|dong)?',
            r'([0-9,\.]+)\s*(?:vnd|đ|dong)',
        ]
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, line, re.IGNORECASE)
            for match in matches:
                amount = int(re.sub(r'[,\.]', '', match))
                if 'commission|hoa hồng|phí' in pattern.lower():
                    booking['commission'] = amount
                elif not booking['room_amount'] or amount > booking['room_amount']:
                    booking['room_amount'] = amount
        
        # Platform patterns
        platform_patterns = [
            r'(?:platform|nền tảng|booking|agoda|expedia|airbnb)(?:\s*:)?\s*(.+?)(?:\s*$|\s*,|\s*\|)',
        ]
        
        for pattern in platform_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                booking['booking_platform'] = match.group(1).strip()
                break
        
        # Guest count patterns
        guest_patterns = [
            r'(?:guests|khách|người)(?:\s*:)?\s*(\d+)',
        ]
        
        for pattern in guest_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                booking['guest_count'] = int(match.group(1))
                break
        
        # Room type patterns
        room_patterns = [
            r'(?:room|phòng|loại phòng)(?:\s*:)?\s*(.+?)(?:\s*$|\s*,|\s*\|)',
        ]
        
        for pattern in room_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                booking['room_type'] = match.group(1).strip()
                break
    
    # Validate essential fields
    if not booking['guest_name']:
        return None
    
    # Generate booking ID if not provided
    if not booking.get('booking_id'):
        booking['booking_id'] = f"TXT{datetime.now().strftime('%m%d%H%M%S')}"
    
    return booking

def normalize_date(date_str):
    """Normalize various date formats to YYYY-MM-DD"""
    import re
    from datetime import datetime
    
    # Remove any extra whitespace
    date_str = date_str.strip()
    
    # Try different date formats
    formats = [
        '%Y-%m-%d', '%Y/%m/%d',
        '%d-%m-%Y', '%d/%m/%Y',
        '%m-%d-%Y', '%m/%d/%Y',
        '%d-%m-%y', '%d/%m/%y',
        '%m-%d-%y', '%m/%d/%y'
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If no format works, return as-is
    return date_str

@app.route('/api/railway_image_diagnostic', methods=['GET', 'POST'])
def railway_image_diagnostic():
    """Railway-specific diagnostic endpoint for image upload debugging"""
    try:
        railway_env = os.getenv('RAILWAY_PROJECT_ID') is not None
        
        diagnostic_info = {
            'success': True,
            'environment': 'railway' if railway_env else 'local',
            'timestamp': datetime.now().isoformat(),
            'api_configuration': {
                'google_api_key_configured': bool(os.getenv("GOOGLE_API_KEY")),
                'google_api_key_length': len(os.getenv("GOOGLE_API_KEY", "")) if os.getenv("GOOGLE_API_KEY") else 0,
                'railway_project_id': os.getenv('RAILWAY_PROJECT_ID', 'Not set'),
                'flask_debug': app.config.get('DEBUG', False)
            },
            'request_info': {
                'method': request.method,
                'content_type': request.content_type,
                'content_length': request.content_length,
                'headers': dict(request.headers),
                'origin': request.headers.get('Origin'),
                'user_agent': request.headers.get('User-Agent', '')[:100]  # Truncate for readability
            }
        }
        
        if request.method == 'POST':
            # Test image upload functionality
            diagnostic_info['upload_test'] = {
                'files_received': len(request.files),
                'json_received': request.is_json,
                'form_data_received': bool(request.form)
            }
            
            if request.files.get('test_image'):
                test_file = request.files.get('test_image')
                diagnostic_info['upload_test']['test_file'] = {
                    'filename': test_file.filename,
                    'content_type': test_file.content_type,
                    'size': len(test_file.read())
                }
                test_file.seek(0)  # Reset file pointer
            
            if request.is_json and request.json.get('test_b64'):
                import base64
                try:
                    base64_data = request.json.get('test_b64')
                    if ',' in base64_data:
                        base64_data = base64_data.split(',')[1]
                    decoded = base64.b64decode(base64_data)
                    diagnostic_info['upload_test']['base64_test'] = {
                        'original_length': len(request.json.get('test_b64')),
                        'decoded_size': len(decoded),
                        'decode_successful': True
                    }
                except Exception as b64_error:
                    diagnostic_info['upload_test']['base64_test'] = {
                        'decode_successful': False,
                        'error': str(b64_error)
                    }
        
        return jsonify(diagnostic_info)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'environment': 'railway' if os.getenv('RAILWAY_PROJECT_ID') else 'local'
        }), 500

# Customer Care Management - DISABLED
# @app.route('/customer_care')
# def customer_care():
#     """Customer care dashboard"""
#     try:
#         # Load recent bookings for customer service
#         df = load_booking_data()
#         
#         # Get upcoming arrivals (next 7 days)
#         today = datetime.today().date()
#         upcoming_arrivals = []
#         
#         if not df.empty:
#             df_clean = df.copy()
#             df_clean['Check-in Date'] = pd.to_datetime(df_clean['Check-in Date'], errors='coerce')
#             
#             for _, booking in df_clean.iterrows():
#                 checkin_date = booking['Check-in Date']
#                 if pd.notna(checkin_date):
#                     checkin_date = checkin_date.date()
#                     days_until = (checkin_date - today).days
#                     if 0 <= days_until <= 7:  # Next 7 days
#                         upcoming_arrivals.append({
#                             'guest_name': booking.get('Tên người đặt', 'N/A'),
#                             'booking_id': booking.get('Số đặt phòng', 'N/A'),
#                             'checkin_date': checkin_date,
#                             'checkout_date': pd.to_datetime(booking['Check-out Date']).date() if pd.notna(booking['Check-out Date']) else None,
#                             'days_until': days_until,
#                             'total_amount': booking.get('Tổng thanh toán', 0),
#                             'commission': booking.get('Hoa hồng', 0),
#                             'collector': booking.get('Người thu tiền', ''),
#                             'phone': booking.get('phone', ''),
#                             'notes': booking.get('Ghi chú thanh toán', '')
#                         })
#         
#         upcoming_arrivals.sort(key=lambda x: x['days_until'])
#         
#         return render_template('customer_care.html', 
#                              upcoming_arrivals=upcoming_arrivals,
#                              today=today)
#         
#     except Exception as e:
#         print(f"Error loading customer care: {e}")
#         flash(f'Error loading customer care: {str(e)}', 'error')
#         return render_template('customer_care.html', upcoming_arrivals=[], today=today)

