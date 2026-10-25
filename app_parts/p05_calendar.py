# p05_calendar — vacancy preview, /calendar month, /calendar_details day page, placement, 2PN, apartment daily summary
# Part of app.py (lines 5448-6636 before the Oct 25 split). Runs inside app.py's namespace
# (see the loader at the end of app.py): every name defined in app.py and earlier parts is available here.
@app.route('/api/vacancy_preview')
def api_vacancy_preview():
    """Vacancy per apartment for the next few days (sidebar board + email preview widget).

    Only guests placed in an apartment (actual_apartment) count against it; guests whose
    arrival day has come but who aren't confirmed yet, or who aren't placed yet, are
    returned as `pending` — see core/occupancy.py for the rules.
    """
    try:
        from datetime import timedelta
        from core.models import db as _db
        from sqlalchemy import text as _text
        from core.occupancy import load_apartments, load_bookings, occupancy_for_night, vn_today

        vn_days = ["Chủ Nhật","Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy"]
        labels = ["Hôm nay","Ngày mai","+2 ngày","+3 ngày","+4 ngày","+5 ngày","+6 ngày"]
        DOT_COLORS = ["#3949ab","#2e7d32","#6a1b9a","#e65100","#00838f","#c62828"]

        apartments = load_apartments(_db.session, _text)
        today = vn_today()
        days_ahead = min(int(os.getenv('DAYS_AHEAD', 4)), len(labels))
        bookings = load_bookings(_db.session, _text, today, today + timedelta(days=days_ahead))

        days = []
        for i in range(days_ahead):
            d = today + timedelta(days=i)
            occ = occupancy_for_night(bookings, apartments, d, today)
            for idx, apt in enumerate(occ['apts']):
                apt['dot'] = DOT_COLORS[idx % len(DOT_COLORS)]
            days.append({
                'date'         : d.strftime('%Y-%m-%d'),
                'date_display' : d.strftime('%d tháng %m, %Y'),
                'label'        : labels[i],
                'weekday'      : vn_days[(d.weekday()+1)%7],
                'total_free'   : occ['total_free'],
                'apts'         : occ['apts'],
                'pending'      : occ['pending'],
                'pending_count': occ['pending_count'],
                'sellable'     : occ['sellable'],
                'over_count'   : occ['over_count'],
            })

        # 2-bedroom (2PN) arrivals / check-outs for the next 14 days — expensive units, watched closely
        two_br_days = []
        try:
            from core.two_bedroom import watch_days
            two_br_days = watch_days(_db.session, _text, today, 14, today, apartments)
            for i, w in enumerate(two_br_days):
                d = today + timedelta(days=i)
                w['weekday'] = vn_days[(d.weekday()+1)%7]
                w['label'] = labels[i] if i < len(labels) else d.strftime('%d/%m')
                w['date_short'] = d.strftime('%d/%m')
                if i < len(days):
                    days[i]['two_br'] = {'in': len(w['in']), 'out': len(w['out']), 'stay': len(w['stay'])}
        except Exception as _tbe:
            _db.session.rollback()
            print(f"[vacancy_preview] 2PN watch failed: {_tbe}")
        return jsonify({'success':True,'days':days,'two_br_days':two_br_days})
    except Exception as e:
        return jsonify({'success':False,'error':str(e),'days':[]})


@app.route('/calendar/')
@app.route('/calendar/<int:year>/<int:month>')
def calendar_view(year=None, month=None):
    """Calendar view with PostgreSQL data - supports apartment filtering"""
    if year is None or month is None:
        today = datetime.today()
        year, month = today.year, today.month

    # Get apartment filter from query parameter
    apartment_id = request.args.get('apartment_id', type=int)

    # Always force fresh data for calendar to fix revenue calculation issues
    force_fresh = True
    df = load_booking_data_for_calculations(force_fresh=force_fresh)

    # ── Pre-load ALL apartments + rooms ONCE (used for filtering AND per-day rendering) ──
    from core.models import Apartment as AptModel, Room as RoomModel

    def _make_apt_abbr(name: str) -> str:
        """Short abbreviation: skip numbers, use only first 2 significant words.
        e.g. '118 Hang Bac Hostel' → 'HBac', '18 Hang Be' → 'HBe', '25 Hoi Vu' → 'HVu'"""
        words = [w for w in name.split() if not w.isdigit()][:2]
        if not words:
            return name[:5]
        if len(words) == 1:
            return words[0][:4].capitalize()
        return words[0][0].upper() + words[1][:3].capitalize()

    all_apts = AptModel.query.filter_by(is_active=True).order_by(AptModel.apartment_id).all()
    apartments_list = []
    for apt in all_apts:
        rooms = RoomModel.query.filter_by(apartment_id=apt.apartment_id, is_active=True).all()
        apartments_list.append({
            'id':         apt.apartment_id,
            'name':       apt.apartment_name,
            'abbr':       _make_apt_abbr(apt.apartment_name),
            'name_lower': apt.apartment_name.lower(),
            'capacity':   len(rooms),
            'rooms':      [{'name': r.room_name, 'name_lower': r.room_name.lower()} for r in rooms],
        })

    # ── Filter by apartment (dual strategy: apartment_id col + name match) ──
    # Always derive capacity from the live DB room list, not the hardcoded constant
    display_capacity = sum(a['capacity'] for a in apartments_list) or TOTAL_HOTEL_CAPACITY
    display_apartments_list = apartments_list  # what the per-day function sees
    if apartment_id:
        apt_entry = next((a for a in apartments_list if a['id'] == apartment_id), None)
        if apt_entry:
            apt_name_lower   = apt_entry['name_lower']
            room_names_lower = [r['name_lower'] for r in apt_entry['rooms']]

            if 'apartment_id' in df.columns:
                id_mask = df['apartment_id'] == apartment_id
            else:
                id_mask = pd.Series(False, index=df.index)

            def _matches_apt(acc_name):
                if pd.isna(acc_name):
                    return False
                acc_l = str(acc_name).lower().strip()
                if apt_name_lower in acc_l or acc_l in apt_name_lower:
                    return True
                return any(rn in acc_l or acc_l in rn for rn in room_names_lower)

            name_mask = df['Tên chỗ nghỉ'].apply(_matches_apt)
            df = df[id_mask | name_mask]

            display_capacity = apt_entry['capacity'] if apt_entry['capacity'] > 0 else TOTAL_HOTEL_CAPACITY
            display_apartments_list = [apt_entry]   # only show selected apartment in cells
            print(f"📍 Calendar filtered to {apt_entry['name']} (id={apartment_id}): {len(df)} bookings, capacity={display_capacity}")
        else:
            print(f"⚠️ Apartment {apartment_id} not found, showing all data")

    # Generate calendar data in weeks format expected by template
    cal = calendar.monthrange(year, month)
    first_day, num_days = cal

    # Convert Python's weekday (Mon=0) to Sunday-based (Sun=0)
    first_day = (first_day + 1) % 7

    # Create calendar weeks structure
    calendar_data = []
    week = []

    # Add empty days for start of month
    for i in range(first_day):
        week.append((None, None, None))

    # Add actual days — pass apartments_list so each call skips DB queries
    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        day_info = get_overall_calendar_day_info(df, date_str, display_capacity,
                                                  apartments_list=display_apartments_list)

        week.append((date_obj, date_str, day_info))
        
        # Start new week on Sunday (weekday 6)
        if len(week) == 7:
            calendar_data.append(week)
            week = []
    
    # Add remaining empty days to complete last week
    while len(week) < 7:
        week.append((None, None, None))
    
    if week:
        calendar_data.append(week)
    
    # Generate revenue by date using optimized daily revenue calculation
    from core.dashboard_routes import get_daily_revenue_by_stay
    daily_revenue_data = get_daily_revenue_by_stay(df)

    print(f"🔍 [CALENDAR_DEBUG] Daily revenue data keys: {list(daily_revenue_data.keys())}")

    # Track high-value guests (>550,000đ/night) and price adjustments
    high_value_dates = {}  # {date: count of high-value guests}
#     price_adjustment_dates = {}  # {date: count of price adjustments}
    high_value_total_count = 0
    high_value_total_revenue = 0
#     price_adjustment_count = 0

    revenue_by_date = {}
    # Same numbers as the dashboard (core/revenue.py): confirmed / paid nights, Báo hủy and unconfirmed arrivals
    # left out (shown apart as "⏳ chờ"), future = booked forecast (owner, Oct 23: the cell said 14.2M, dashboard 12.5M).
    _rev_figs = None
    try:
        from core import revenue as _R
        from core.models import db as _rdb
        _rev_figs = _R.day_figures(_R.load_bookings(_rdb.session, text),
                                   [datetime(year, month, dd).date() for dd in range(1, num_days + 1)])
    except Exception as _e:
        print(f"[calendar] day_figures failed, old figures used: {_e}")
    for day in range(1, num_days + 1):
        date_str = f"{year}-{month:02d}-{day:02d}"
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

        if _rev_figs is not None:
            _fg = _rev_figs[date_obj]
            revenue_by_date[date_obj] = type('obj', (object,), {
                'daily_total': _fg['shown'], 'daily_total_minus_commission': _fg['shown'], 'total_commission': 0,
                'pending': _fg['pending'], 'pending_n': _fg['pending_n'],
            })()
        # Use optimized daily revenue data if available, fallback to calendar info
        elif date_obj in daily_revenue_data:
            revenue_info = daily_revenue_data[date_obj]
            print(f"🎯 [CALENDAR_DEBUG] {date_str}: Using optimized data - {revenue_info['daily_total']:,.0f}đ")
            revenue_by_date[date_obj] = type('obj', (object,), {
                'daily_total': revenue_info['daily_total'],
                'daily_total_minus_commission': revenue_info['daily_total_minus_commission'],
                'total_commission': revenue_info['total_commission']
            })()
        else:
            # Fallback to calendar info for dates without revenue data
            day_info = get_overall_calendar_day_info(df, date_str, display_capacity,
                                                      apartments_list=display_apartments_list)
            fallback_revenue = day_info.get('daily_revenue', 0)
            print(f"⚠️ [CALENDAR_DEBUG] {date_str}: Using fallback data - {fallback_revenue:,.0f}đ")
            revenue_by_date[date_obj] = type('obj', (object,), {
                'daily_total': fallback_revenue,
                'daily_total_minus_commission': day_info.get('revenue_minus_commission', 0),
                'total_commission': day_info.get('commission_total', 0)
            })()

        # Calculate high-value guests for this date (ONLY ON CHECK-IN DATE)
        checkin_bookings = df[
            (pd.to_datetime(df['Check-in Date']).dt.date == date_obj) &
            (df['Tình trạng'] != 'Đã hủy')
        ]

        high_value_count_today = 0

        for _, booking in checkin_bookings.iterrows():
            # Exclude room 102 (room_id = 5) from VIP indicator
            room_id = booking.get('room_id')
            if room_id == 5:
                continue  # Skip hang be 102 guests
            
            room_amount = booking.get('Tổng thanh toán', 0) or 0
            checkin = pd.to_datetime(booking.get('Check-in Date'))
            checkout = pd.to_datetime(booking.get('Check-out Date'))
            nights = (checkout - checkin).days if checkin and checkout else 1
            nights = max(nights, 1)  # Avoid division by zero

            per_night_rate = room_amount / nights

            # Check for high-value guest (>550k/night) - ONLY counted on check-in date
            # EXCLUDES hang be 102 (room_id = 5)
            if per_night_rate > 550000:
                high_value_count_today += 1
                high_value_total_count += 1
                high_value_total_revenue += per_night_rate

        if high_value_count_today > 0:
            high_value_dates[date_obj] = high_value_count_today

#         if price_adjust_count_today > 0:
#             price_adjustment_dates[date_obj] = price_adjust_count_today
    
    # ── Unpaid badge: count guests staying >1 day without payment per past date ──
    unpaid_by_date = {}
    _today_cal = datetime.today().date()
    _cancel_col = 'Tình trạng'
    _active_df = df[df[_cancel_col] != 'Đã hủy'] if _cancel_col in df.columns else df
    for _day in range(1, num_days + 1):
        _ds = f"{year}-{month:02d}-{_day:02d}"
        _do = datetime.strptime(_ds, "%Y-%m-%d").date()
        if _do > _today_cal:
            continue
        _cnt = 0
        for _, _row in _active_df.iterrows():
            try:
                _ci = pd.Timestamp(_row['Check-in Date']).date()
                _co = pd.Timestamp(_row['Check-out Date']).date()
                _collected = float(_row.get('Số tiền đã thu', 0) or 0)
                # Staying on this date AND checked in at least 1 day before AND not paid
                if _ci < _do <= _co and _collected == 0:
                    _cnt += 1
            except Exception:
                continue
        if _cnt > 0:
            unpaid_by_date[_ds] = _cnt

    # ── 2-bedroom check-outs per day (so the month view shows when 2PN units turn over) ──
    two_br_checkouts = {}
    try:
        from core.models import db as _tbdb
        from core.two_bedroom import is_two_bedroom, load_manual_flags
        _month_start = datetime(year, month, 1).date()
        _month_end = datetime(year + (month == 12), month % 12 + 1, 1).date()
        _co_dates = pd.to_datetime(_active_df['Check-out Date'], errors='coerce').dt.date
        _month_df = _active_df[(_co_dates >= _month_start) & (_co_dates < _month_end)]
        if 'checkin_status' in _month_df.columns:
            _month_df = _month_df[~_month_df['checkin_status'].isin(['cancelling', 'no_show'])]
        _manual = load_manual_flags(_tbdb.session, text, _month_df['Số đặt phòng'].astype(str).tolist())
        for _, _row in _month_df.iterrows():
            _bid = str(_row.get('Số đặt phòng', '') or '')
            if is_two_bedroom(_row.get('Tên chỗ nghỉ', ''), _manual.get(_bid)):
                _ds = pd.Timestamp(_row['Check-out Date']).strftime('%Y-%m-%d')
                two_br_checkouts.setdefault(_ds, []).append(str(_row.get('Tên người đặt', '') or _bid))
    except Exception as _tbe:
        print(f"[calendar_view] two-bedroom checkouts failed: {_tbe}")

    # Calculate previous and next month for navigation
    current_month = datetime(year, month, 1)

    if month == 1:
        prev_month = datetime(year - 1, 12, 1)
    else:
        prev_month = datetime(year, month - 1, 1)

    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)

    # Build dropdown data from the already-loaded apartments_list
    apartments_data = [{'apartment_id': a['id'], 'apartment_name': a['name']} for a in apartments_list]

    # Get current apartment info if filtered
    current_apartment = next((a for a in apartments_list if a['id'] == apartment_id), None) if apartment_id else None

    return render_template(
        'calendar.html',
        year=year,
        month=month,
        calendar_data=calendar_data,
        month_name=calendar.month_name[month],
        current_month=current_month,
        prev_month=prev_month,
        next_month=next_month,
        today=datetime.today().date(),
        revenue_by_date=revenue_by_date,
        high_value_dates=high_value_dates,
        high_value_total_count=high_value_total_count,
        high_value_total_revenue=high_value_total_revenue,
        apartments=apartments_data,          # For filter dropdown
        apartments_list=apartments_list,     # Full list for legend (dynamic)
        current_apartment_id=apartment_id,
        current_apartment=current_apartment,  # Current apartment object
        unpaid_by_date=unpaid_by_date,        # {date_str: count} unpaid guests staying >1 day
        two_br_checkouts=two_br_checkouts,    # {date_str: [guest names]} 2-bedroom check-outs
    )

@app.route('/debug_revenue')
def debug_revenue():
    """Debug route to test revenue calculations"""
    try:
        # Load fresh data
        df = load_booking_data_for_calculations(force_fresh=True)
        print(f"🔍 [DEBUG_ROUTE] Loaded {len(df)} bookings")
        
        # Test specific dates
        july_5_info = get_overall_calendar_day_info(df, "2025-07-05", TOTAL_HOTEL_CAPACITY)
        july_7_info = get_overall_calendar_day_info(df, "2025-07-07", TOTAL_HOTEL_CAPACITY)
        
        # Test optimized revenue function
        from core.dashboard_routes import get_daily_revenue_by_stay
        daily_revenue_data = get_daily_revenue_by_stay(df)
        
        july_5_optimized = daily_revenue_data.get(datetime(2025, 7, 5).date(), {})
        july_7_optimized = daily_revenue_data.get(datetime(2025, 7, 7).date(), {})
        
        result = f"""
        <h1>Revenue Debug Results</h1>
        <h2>July 5, 2025</h2>
        <p><strong>Calendar method:</strong> {july_5_info.get('daily_revenue', 0):,.0f}đ</p>
        <p><strong>Optimized method:</strong> {july_5_optimized.get('daily_total', 0):,.0f}đ</p>
        
        <h2>July 7, 2025</h2>
        <p><strong>Calendar method:</strong> {july_7_info.get('daily_revenue', 0):,.0f}đ</p>
        <p><strong>Optimized method:</strong> {july_7_optimized.get('daily_total', 0):,.0f}đ</p>
        
        <h2>Total Bookings</h2>
        <p><strong>Total bookings loaded:</strong> {len(df)}</p>
        <p><strong>Daily revenue data keys:</strong> {len(daily_revenue_data)}</p>
        """
        
        return result
        
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/calendar_details/<date_str>')
def calendar_details(date_str):
    """Calendar details view for specific date"""
    try:
        # Parse the date
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Load booking data excluding cancelled bookings for calendar calculations
        # ALWAYS use force_fresh=True to show latest updates immediately
        df = load_booking_data_for_calculations(force_fresh=True)

        # Get detailed day information — use live room count from DB
        from core.models import Apartment as _AptM, Room as _RoomM
        _total_rooms = _RoomM.query.join(_AptM).filter(
            _RoomM.is_active == True, _AptM.is_active == True
        ).count() or TOTAL_HOTEL_CAPACITY
        day_info = get_overall_calendar_day_info(df, date_str, _total_rooms)
        
        # Get activity data for the template
        activity = day_info.get('activity', {})
        check_in    = activity.get('arrivals', [])
        check_out   = activity.get('departures', [])
        staying_over = activity.get('staying', [])

        # ── Cancelling / no-show filter ──────────────────────────────────────
        # Railway server runs UTC; Vietnam is UTC+7.  Use VN local date so that
        # "has check-in day passed?" comparisons are correct even at midnight.
        _today_date = (datetime.utcnow() + timedelta(hours=7)).date()

        # Collect bids for ALL three sections — check_out guests are included so that
        # guests who reported cancellation on their check-in day and never actually
        # arrived are also filtered out of the check-out list.
        _ci_bids_only   = [b.get('Số đặt phòng','') for b in check_in     if b.get('Số đặt phòng')]
        _stay_bids_only = [b.get('Số đặt phòng','') for b in staying_over if b.get('Số đặt phòng')]
        _co_bids_only   = [b.get('Số đặt phòng','') for b in check_out    if b.get('Số đặt phòng')]
        _all_visible_bids = list(set(_ci_bids_only + _stay_bids_only + _co_bids_only))

        # Default: empty map (if DB query fails filter still runs; no-show logic kicks in)
        _all_status_map = {}
        try:
            from core.models import db as _cddb
            _ci_rows = _cddb.session.execute(
                text("""SELECT booking_id, checkin_status FROM bookings
                        WHERE checkin_status IS NOT NULL
                          AND (booking_id = ANY(:bids)
                               OR (DATE(checkin_date)=:d AND checkin_status='cancelling'))"""),
                {'bids': _all_visible_bids or ['__none__'], 'd': date_obj}
            ).fetchall()
            _all_status_map = {r[0]: r[1] for r in _ci_rows}
        except Exception as _qe:
            print(f"[calendar_details:{date_obj}] checkin_status query failed: {_qe}")

        _cancelling_all = {bid for bid, st in _all_status_map.items() if st == 'cancelling'}

        # TODAY: re-inject cancelling arrivals so staff can review/undo them.
        # PAST : strip cancelling bookings from check_in entirely.
        if date_obj == _today_date:
            _missing_ci = _cancelling_all - set(_ci_bids_only)
            if _missing_ci:
                try:
                    _df_full2 = load_booking_data(force_fresh=True)
                    _extra2 = _df_full2[
                        (_df_full2['Số đặt phòng'].isin(_missing_ci)) &
                        (_df_full2['Check-in Date'].apply(
                            lambda x: pd.Timestamp(x).date() == date_obj if pd.notna(x) else False))
                    ]
                    check_in = check_in + _extra2.to_dict('records')
                except Exception:
                    pass
        else:
            check_in = [b for b in check_in if b.get('Số đặt phòng','') not in _cancelling_all]

        # Filter staying_over — runs unconditionally (not inside a try/except).
        #   confirmed   → keep
        #   cancelling  → remove
        #   null/none   → remove once their check-in day has passed (no-show)
        #                 keep only if check-in is today (might still arrive)
        # NOTE: Do NOT filter by checkout_date <= today. When viewing a historical date
        # (e.g. Apr 16 viewed on Apr 19), guests who checked out Apr 17/18/19 WERE
        # legitimately staying on Apr 16 and must appear in the historical record.
        # Grace period: unconfirmed guests stay visible for 3 days after their check-in date
        # before being treated as no-shows.  (Previously: 1 day.)
        # Day 0 = check-in day, Day 1–2 = grace, Day 3+ = hidden.
        # Viewing a FUTURE date: guests whose arrival day has already come but who are
        # still unconfirmed are hidden too (they reappear once "Xác nhận đến" is pressed).
        # Rules live in core.occupancy.guest_shown_on.
        from core.occupancy import guest_shown_on

        def _guest_stays_over(g):
            bid = g.get('Số đặt phòng', '')
            return guest_shown_on(date_obj, g.get('Check-in Date'), _all_status_map.get(bid), _today_date)

        # Collect full data of hidden (unconfirmed/no-show) guests for the restore panel
        _hidden_guests = []
        _hidden_stay  = [g for g in staying_over if not _guest_stays_over(g)]
        _removed = [g.get('Tên người đặt','?') for g in _hidden_stay]
        staying_over = [g for g in staying_over if _guest_stays_over(g)]
        if _removed:
            print(f"[calendar_details:{date_obj}] Removed no-show/cancelled from staying: {_removed}")

        # Filter check_out: guests marked 'cancelling' never actually arrived, so they
        # cannot check out either.  Unconfirmed guests follow the same 3-day grace rule.
        def _guest_checks_out(g):
            bid = g.get('Số đặt phòng', '')
            return guest_shown_on(date_obj, g.get('Check-in Date'), _all_status_map.get(bid), _today_date)

        _hidden_co   = [g for g in check_out if not _guest_checks_out(g)]
        _co_removed = [g.get('Tên người đặt','?') for g in _hidden_co]
        check_out = [g for g in check_out if _guest_checks_out(g)]
        if _co_removed:
            print(f"[calendar_details:{date_obj}] Removed no-show/cancelled from checkout: {_co_removed}")

        # Build hidden_guests list (unconfirmed only — skip 'cancelling' which are true cancels)
        _seen_hidden = set()
        for _hg in (_hidden_stay + _hidden_co):
            _hbid = str(_hg.get('Số đặt phòng', '') or '')
            if not _hbid or _hbid in _seen_hidden:
                continue
            _hst = _all_status_map.get(_hbid, '')
            if _hst == 'cancelling':  # true cancellation — don't show in restore panel
                continue
            _seen_hidden.add(_hbid)
            try:
                _hci = pd.Timestamp(_hg.get('Check-in Date')).date() if pd.notna(_hg.get('Check-in Date')) else None
                _hco = pd.Timestamp(_hg.get('Check-out Date')).date() if pd.notna(_hg.get('Check-out Date')) else None
            except Exception:
                _hci = _hco = None
            _hidden_guests.append({
                'bid':   _hbid,
                'name':  _hg.get('Tên người đặt', 'N/A'),
                'room':  _hg.get('Tên chỗ nghỉ', ''),
                'ci':    _hci.strftime('%d/%m') if _hci else '',
                'co':    _hco.strftime('%d/%m') if _hco else '',
                'amount': float(_hg.get('Tổng thanh toán', 0) or 0),
                'section': 'Đang ở' if _hg in _hidden_stay else 'Check-out',
            })
        print(f"[calendar_details:{date_obj}] hidden_guests (restorable): {[g['name'] for g in _hidden_guests]}")

        # ── Normalize all date fields to datetime.date so template arithmetic works ──
        # Bookings can come from different sources (df_local with .date() OR _extra2 with
        # pd.Timestamp). Normalize here once so every downstream operation is safe.
        _DATE_FIELDS = ['Check-in Date', 'Check-out Date']
        def _normalize_dates(guest_list):
            for g in guest_list:
                for _f in _DATE_FIELDS:
                    v = g.get(_f)
                    if v is not None:
                        try:
                            g[_f] = pd.Timestamp(v).date() if pd.notna(v) else None
                        except Exception:
                            pass
        _normalize_dates(check_in)
        _normalize_dates(check_out)
        _normalize_dates(staying_over)

        # ── Revenue calculation — confirmed-only logic ───────────────────────
        # Rule:
        #   TODAY  → check-in guests MUST be 'confirmed' to count (NULL = didn't confirm = no-show)
        #   PAST   → same: NULL = user never confirmed = guest never arrived → don't count
        #   FUTURE → count all non-cancelling (expected revenue; confirmation hasn't happened yet)
        #   staying_over / check_out → already filtered above (NULL whose ci<today excluded)

        is_today_view        = (date_obj == _today_date)
        is_past_view         = (date_obj <  _today_date)
        is_past_or_today     = (date_obj <= _today_date)

        if is_past_or_today:
            # Past AND today: only confirmed arrivals count
            _revenue_checkins = [
                g for g in check_in
                if _all_status_map.get(g.get('Số đặt phòng', '')) == 'confirmed'
            ]
            _pending_checkins = [
                g for g in check_in
                if _all_status_map.get(g.get('Số đặt phòng', '')) != 'confirmed'
            ]
        else:
            # Future: count all (expected revenue)
            _revenue_checkins = check_in
            _pending_checkins = []

        revenue_guests  = _revenue_checkins + check_out + staying_over

        def _daily_rev_for(guest_list):
            """Return (total, commission, net) for a list of guest dicts."""
            rev = comm = 0.0
            for g in guest_list:
                try:
                    raw_total   = float(g.get('Tổng thanh toán', 0) or 0)
                    collected   = float(g.get('Số tiền đã thu',  0) or 0)
                    effective   = collected if collected > 0 else raw_total
                    commission  = float(g.get('Hoa hồng',        0) or 0)
                    ci = g['Check-in Date']
                    co = g['Check-out Date']
                    if pd.notna(ci) and pd.notna(co):
                        nights = max((pd.Timestamp(co) - pd.Timestamp(ci)).days, 1)
                        rev  += effective  / nights
                        comm += commission / nights
                except (ValueError, TypeError, AttributeError, KeyError):
                    continue
            return rev, comm, rev - comm

        confirmed_rev, confirmed_comm, confirmed_net = _daily_rev_for(revenue_guests)
        pending_rev,   _,              _             = _daily_rev_for(_pending_checkins)
        # Staying + checkout revenue (fixed regardless of check-in confirmation status)
        stay_co_rev, stay_co_comm, stay_co_net = _daily_rev_for(check_out + staying_over)

        # Build detailed breakdown (only revenue guests shown in breakdown table)
        detailed_bookings = []
        for guest in revenue_guests:
            try:
                raw_total  = float(guest.get('Tổng thanh toán', 0) or 0)
                collected  = float(guest.get('Số tiền đã thu',  0) or 0)
                effective  = collected if collected > 0 else raw_total
                commission_amount = float(guest.get('Hoa hồng', 0) or 0)
                ci = guest['Check-in Date']
                co = guest['Check-out Date']
                if pd.notna(ci) and pd.notna(co):
                    nights = max((pd.Timestamp(co) - pd.Timestamp(ci)).days, 1)
                    daily_amount = effective / nights
                    daily_comm   = commission_amount / nights
                    detailed_bookings.append(type('obj', (object,), {
                        'booking_id':  guest.get('Số đặt phòng', 'N/A'),
                        'guest_name':  guest.get('Tên người đặt', 'N/A'),
                        'daily_amount': daily_amount,
                        'daily_amount_minus_commission': daily_amount - daily_comm,
                        'commission_amount': commission_amount,
                        'total_amount': effective,
                        'nights': nights,
                    })())
            except (ValueError, TypeError, AttributeError, KeyError):
                continue

        # The headline / breakdown use the dashboard's numbers (core/revenue.py) so the day page, the month calendar
        # and the dashboard agree (owner, Oct 23). Guests leaving today are not counted (their last night was
        # yesterday); unconfirmed arrivals stay apart as "chờ xác nhận".
        rev_pn = {}
        try:
            from core import revenue as _R
            from core.models import db as _xdb_cd
            _fg = _R.day_figures(_R.load_bookings(_xdb_cd.session, text), [date_obj])[date_obj]
            confirmed_rev, confirmed_comm, confirmed_net = _fg['shown'], 0.0, _fg['shown']
            pending_rev = _fg['pending']
            rev_pn = {r['booking_id']: round(r['per_night']) for r in _fg['rows']}
            _live = [r for r in _fg['counted'] if r['is_arrival'] and r['confirmed']]   # added back by the page's JS
            stay_co_rev = confirmed_rev - sum(r['per_night'] for r in _live)
            stay_co_comm = 0.0
            _stay_co_n = len(_fg['counted']) - len(_live)
            _pending_checkins = [None] * _fg['pending_n']
            revenue_guests = _fg['counted']
            detailed_bookings = [type('obj', (object,), {
                'booking_id': r['booking_id'], 'guest_name': r['name'], 'daily_amount': r['per_night'],
                'daily_amount_minus_commission': r['per_night'], 'commission_amount': 0,
                'total_amount': r['value'], 'nights': r['nights']})() for r in _fg['counted']]
        except Exception as _e:
            print(f"[calendar_details] day_figures failed, old figures used: {_e}")
            _stay_co_n = len(check_out + staying_over)

        day_revenue_info = type('obj', (object,), {
            'daily_total':                  confirmed_rev,
            'daily_total_minus_commission': confirmed_net,
            'total_commission':             confirmed_comm,
            'guest_count':    len(revenue_guests),
            # Extra fields for template to show pending context
            'unconfirmed_count': len(_pending_checkins),
            'pending_revenue':   pending_rev,
            'is_today':          is_today_view,
            'bookings': detailed_bookings,
            # Staying + checkout revenue (fixed; used by client-side recalculation)
            'stay_co_rev':   stay_co_rev,
            'stay_co_comm':  stay_co_comm,
            'stay_co_count': _stay_co_n,
        })()
        
        # Build apartments_list for dynamic room badge colouring
        from core.models import Apartment as _AptM, Room as _RoomM
        def _make_abbr(name):
            words = [w for w in name.split() if not w.isdigit()][:2]
            if not words:
                return name[:5]
            return words[0][0].upper() + words[1][:3].capitalize() if len(words) >= 2 else words[0][:4].capitalize()

        _APT_COLORS  = ['#1976D2','#2E7D32','#7B1FA2','#E64A19','#00838F','#F57F17']
        _APT_EMOJIS  = ['🔵','🟢','🟣','🟠','🔵','🟡']
        _all_apts = _AptM.query.order_by(_AptM.apartment_id).all()
        apartments_list = []
        for _i, _apt in enumerate(_all_apts):
            _rooms = _RoomM.query.filter_by(apartment_id=_apt.apartment_id).all()
            apartments_list.append({
                'id':         _apt.apartment_id,
                'name':       _apt.apartment_name,
                'name_lower': _apt.apartment_name.lower(),
                'abbr':       _make_abbr(_apt.apartment_name),
                'color':      _APT_COLORS[_i % len(_APT_COLORS)],
                'emoji':      _APT_EMOJIS[_i % len(_APT_EMOJIS)],
                'rooms':      [{'name': r.room_name, 'name_lower': r.room_name.lower()} for r in _rooms],
                'active':     bool(getattr(_apt, 'is_active', True)),
                'capacity':   sum(1 for r in _rooms if getattr(r, 'is_active', True)),
            })

        # ── Load actual_apartment assignments from DB ──
        _apt_map = {}
        try:
            from core.models import db as _aptmdb
            # Auto-migrate: add actual_apartment column if not exists
            try:
                _aptmdb.session.execute(text(
                    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS actual_apartment VARCHAR(100) DEFAULT NULL"
                ))
                _aptmdb.session.commit()
            except Exception:
                _aptmdb.session.rollback()

            _all_day_bids = list(set(
                [b.get('Số đặt phòng','') for b in check_in + staying_over + check_out
                 if b.get('Số đặt phòng')]
            ))
            if _all_day_bids:
                _apt_rows = _aptmdb.session.execute(
                    text("SELECT booking_id, actual_apartment FROM bookings WHERE booking_id = ANY(:bids) AND actual_apartment IS NOT NULL"),
                    {'bids': _all_day_bids}
                ).fetchall()
                _apt_map = {r[0]: r[1] for r in _apt_rows}
        except Exception as _ae:
            print(f"[calendar_details] actual_apartment load failed: {_ae}")

        # ── Overdue unpaid: checked out in last 7 days, not yet collected ──
        overdue_unpaid = []
        try:
            _vn_today = (datetime.utcnow() + timedelta(hours=7)).date()
            _cutoff   = _vn_today - timedelta(days=7)
            _od_df    = load_booking_data(force_fresh=False)

            # Fetch checkin_status AND arrival_confirmed for no-show filtering
            _od_cs_map = {}
            _od_ac_map = {}  # arrival_confirmed map: booking_id -> bool
            try:
                from core.models import db as _oddb
                _od_rows = _oddb.session.execute(
                    text("SELECT booking_id, checkin_status, arrival_confirmed FROM bookings")
                ).fetchall()
                _od_cs_map = {r[0]: r[1] for r in _od_rows if r[1]}
                _od_ac_map = {r[0]: bool(r[2]) for r in _od_rows}
            except Exception:
                pass

            _no_show_cut = _vn_today - timedelta(days=2)

            for _, _row in _od_df.iterrows():
                try:
                    _co = _row.get('Check-out Date')
                    if not pd.notna(_co):
                        continue
                    _co_date = pd.Timestamp(_co).date()
                    # Only past checkouts within the 7-day window
                    if not (_cutoff <= _co_date < _vn_today):
                        continue

                    # Skip if already paid
                    _collector = str(_row.get('Người thu tiền', '') or '')
                    if 'LOC' in _collector or 'THAO' in _collector:
                        continue

                    # Skip if collected amount set
                    if float(_row.get('Số tiền đã thu', 0) or 0) > 0:
                        continue

                    # Skip cancelled/deleted
                    _bstatus = str(_row.get('Tình trạng', '') or '').lower()
                    if any(k in _bstatus for k in ['hủy', 'cancel', 'delet', 'xóa']):
                        continue

                    # Skip cancelling / no_show status
                    _bid = str(_row.get('Số đặt phòng', '') or '')
                    _cs  = str(_od_cs_map.get(_bid, '') or '')
                    if _cs in ('cancelling', 'no_show'):
                        continue

                    # 🚫 Skip no-shows: arrival was never confirmed = guest never actually arrived
                    _arrived = _od_ac_map.get(_bid, False)
                    if not _arrived:
                        continue  # No arrival confirmation → no-show, not a real unpaid checkout

                    _ci = _row.get('Check-in Date')
                    _ci_date = pd.Timestamp(_ci).date() if pd.notna(_ci) else _vn_today
                    _nights  = max((_co_date - _ci_date).days, 1)
                    _amount  = float(_row.get('Tổng thanh toán', 0) or 0)
                    _days_ago = (_vn_today - _co_date).days

                    overdue_unpaid.append({
                        'Tên người đặt': _row.get('Tên người đặt', 'N/A'),
                        'Tên chỗ nghỉ':  _row.get('Tên chỗ nghỉ', ''),
                        'Check-in Date': _ci,
                        'Check-out Date': _co,
                        'co_display': _co_date.strftime('%d/%m'),
                        'ci_display': _ci_date.strftime('%d/%m'),
                        'Tổng thanh toán': _amount,
                        'nights': _nights,
                        'days_ago': _days_ago,
                        'Số đặt phòng': _bid,
                    })
                except Exception:
                    continue

            # Sort: most recent checkout first (days_ago ascending)
            overdue_unpaid.sort(key=lambda x: x['days_ago'])
        except Exception as _oe:
            print(f"[calendar_details] overdue_unpaid load failed: {_oe}")

        # ── Guest phone numbers (filled by the Chrome extension / booking forms) ──
        phone_map = {}
        try:
            from core.models import db as _phdb

            def _dm(v):
                try:
                    return pd.Timestamp(v).strftime('%d/%m') if v is not None and pd.notna(v) else ''
                except Exception:
                    return ''
            # Name / dates / room per booking — fills the pre-written message on the WhatsApp/Zalo chips
            _ph_info = {}
            for _g in check_in + staying_over + check_out:
                _b = str(_g.get('Số đặt phòng', '') or '')
                if _b and _b not in _ph_info:
                    _ph_info[_b] = {'ten': str(_g.get('Tên người đặt', '') or '').strip(),
                                    'nhan': _dm(_g.get('Check-in Date')), 'tra': _dm(_g.get('Check-out Date')),
                                    'phong': _room_label(_g.get('Tên chỗ nghỉ'))}
            if _ph_info:
                _ensure_partner_column()
                _ensure_property_column()
                for _bid, _phone, _partner, _cho in _phdb.session.execute(text("""
                    SELECT b.booking_id, g.phone, b.via_partner, b.property_name FROM bookings b
                    LEFT JOIN guests g ON g.guest_id = b.guest_id
                    WHERE b.booking_id = ANY(:bids) AND (COALESCE(g.phone, '') <> '' OR b.via_partner)
                """), {'bids': list(_ph_info)}).fetchall():
                    if _bid in _ph_info:
                        _ph_info[_bid]['cho'] = _cho or ''
                    if _partner and not _real_guest_phone(_phone, True):    # partner's number / none of the guest's own
                        phone_map[_bid] = {'partner': True, **_ph_info.get(_bid, {})}
                        continue
                    _links = _msg_phone_links(_phone)
                    if _links:
                        _digits = re.sub(r'\D', '', _phone)
                        phone_map[_bid] = {'display': _phone, 'wa': _links['wa'], 'zalo': _links['zalo'],
                                           'tel': ('+' if _phone.strip().startswith('+') else '') + _digits,
                                           **_ph_info.get(_bid, {})}
        except Exception as _phe:
            print(f"[calendar_details] phone load failed: {_phe}")
        try:
            _amt = _auto_msg_templates()
            auto_msg = {'wa': _auto_msg_for(_amt, 'EN')['content'], 'zalo': _auto_msg_for(_amt, 'VI')['content']}
        except Exception as _ame:
            print(f"[calendar_details] auto message load failed: {_ame}")
            auto_msg = {'wa': AUTO_MSG_DEFAULT, 'zalo': AUTO_MSG_VI}

        # ── 2-bedroom (2 PN) bookings: flag per card + upcoming check-outs to watch ──
        two_br_map = {}
        two_br_upcoming = []
        try:
            from core.models import db as _tbdb
            from core.two_bedroom import is_two_bedroom, load_manual_flags, ensure_column as _tb_ensure
            _tb_ensure(_tbdb.session, text)

            _page_guests = check_in + staying_over + check_out
            _manual = load_manual_flags(_tbdb.session, text, [g.get('Số đặt phòng', '') for g in _page_guests])
            for g in _page_guests:
                _bid = str(g.get('Số đặt phòng', '') or '')
                if _bid:
                    two_br_map[_bid] = {
                        'on': is_two_bedroom(g.get('Tên chỗ nghỉ', ''), _manual.get(_bid)),
                        'manual': _manual.get(_bid),
                    }

            # Check-outs from the viewed date through the next 3 days
            _apt_names = {str(a['id']): a for a in apartments_list}
            _rows = _tbdb.session.execute(text("""
                SELECT booking_id, guest_name, checkin_date, checkout_date, accommodation_name,
                       actual_apartment, checkin_status, two_bedroom, collector
                FROM bookings
                WHERE checkout_date BETWEEN :d AND :d3
                  AND COALESCE(booking_status, '') NOT IN ('cancelled', 'deleted')
                  AND COALESCE(checkin_status, '') NOT IN ('cancelling', 'no_show')
                ORDER BY checkout_date, guest_name
            """), {'d': date_obj, 'd3': date_obj + timedelta(days=3)}).fetchall()
            for (_bid, _name, _ci, _co, _listing, _apt, _cst, _flag, _collector) in _rows:
                if not is_two_bedroom(_listing, _flag):
                    continue
                # Unconfirmed well past their arrival day = no-show, nothing to check out
                if _cst != 'confirmed' and _ci < _today_date - timedelta(days=2):
                    continue
                _apt_info = _apt_names.get(str(_apt or ''))
                two_br_upcoming.append({
                    'booking_id': _bid,
                    'name': _name or _bid,
                    'listing': _listing or '',
                    'checkin': _ci,
                    'checkout': _co,
                    'days_left': (_co - date_obj).days,
                    'nights': max((_co - _ci).days, 1),
                    'apartment': _apt_info['name'] if _apt_info else '',
                    'apt_color': _apt_info['color'] if _apt_info else '#94a3b8',
                    'confirmed': _cst == 'confirmed',
                    'paid': any(k in str(_collector or '') for k in ('LOC', 'THAO')),
                })
        except Exception as _tbe:
            print(f"[calendar_details] two-bedroom load failed: {_tbe}")

        return render_template(
            'calendar_details.html',
            date=date_obj,
            date_str=date_str,
            day_info=day_info,
            formatted_date=date_obj.strftime("%d/%m/%Y"),
            check_in=check_in,
            check_out=check_out,
            staying_over=staying_over,
            day_revenue_info=day_revenue_info, rev_pn=rev_pn,
            current_date=date_obj,
            pd=pd,
            timedelta=timedelta,
            apartments_list=apartments_list,
            apt_map=_apt_map,
            overdue_unpaid=overdue_unpaid,
            hidden_guests=_hidden_guests,
            two_br_map=two_br_map,
            two_br_upcoming=two_br_upcoming,
            phone_map=phone_map,
            auto_msg=auto_msg,
        )

    except Exception as e:
        flash(f'Error loading calendar details: {str(e)}', 'error')
        return redirect(url_for('calendar_view'))

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

        if apt_value:
            _sadb.session.execute(
                text("UPDATE bookings SET actual_apartment = :apt WHERE booking_id = :bid"),
                {'apt': apt_value, 'bid': booking_id}
            )
        else:
            _sadb.session.execute(
                text("UPDATE bookings SET actual_apartment = NULL WHERE booking_id = :bid"),
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


@app.route('/api/set_two_bedroom', methods=['POST'])
def set_two_bedroom():
    """Mark a booking as 2-bedroom (true), not 2-bedroom (false) or back to auto-detect (null)."""
    try:
        from core.models import db as _tbdb
        from core.two_bedroom import ensure_column, is_two_bedroom
        data = request.get_json() or {}
        booking_id = str(data.get('booking_id', '')).strip()
        value = data.get('value')
        if not booking_id:
            return jsonify({'success': False, 'message': 'Missing booking_id'}), 400
        if value not in (True, False, None):
            return jsonify({'success': False, 'message': 'value must be true, false or null'}), 400

        ensure_column(_tbdb.session, text)
        row = _tbdb.session.execute(
            text("UPDATE bookings SET two_bedroom = :v WHERE booking_id = :bid RETURNING accommodation_name"),
            {'v': value, 'bid': booking_id}
        ).fetchone()
        _tbdb.session.commit()
        if not row:
            return jsonify({'success': False, 'message': 'Không tìm thấy booking'}), 404
        return jsonify({'success': True, 'booking_id': booking_id, 'manual': value,
                        'on': is_two_bedroom(row[0], value)})
    except Exception as e:
        try:
            from core.models import db as _tbdb2; _tbdb2.session.rollback()
        except Exception:
            pass
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/apartment_placement_check', methods=['GET'])
def apartment_placement_check():
    """Before placing a guest: would the apartment exceed its room count on any night?
    ?booking_id=...&apartment_id=...  →  {conflicts: [{night, placed, guests}], capacity}"""
    try:
        from core.models import db as _pcdb
        from core.occupancy import load_apartments, load_bookings, placement_conflicts
        booking_id = (request.args.get('booking_id') or '').strip()
        apartment_id = request.args.get('apartment_id', type=int)
        if not booking_id or apartment_id is None:
            return jsonify({'success': False, 'message': 'Thiếu booking_id hoặc apartment_id'}), 400

        row = _pcdb.session.execute(
            text("SELECT checkin_date, checkout_date FROM bookings WHERE booking_id = :bid"),
            {'bid': booking_id}
        ).fetchone()
        if not row:
            return jsonify({'success': False, 'message': 'Không tìm thấy booking'}), 404

        apartments = load_apartments(_pcdb.session, text)
        apartment = apartments.get(apartment_id)
        if not apartment:
            return jsonify({'success': True, 'conflicts': [], 'capacity': None,
                            'inactive': True, 'message': 'Căn hộ đang tạm dừng'})

        bookings = load_bookings(_pcdb.session, text, row[0], row[1])
        conflicts = placement_conflicts(bookings, apartment, booking_id, row[0], row[1])
        return jsonify({'success': True, 'conflicts': conflicts,
                        'capacity': apartment['capacity'], 'apartment_name': apartment['name']})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/apartment_daily_summary', methods=['GET'])
def apartment_daily_summary():
    """
    Returns per-apartment occupancy for a given date.
    ?date=YYYY-MM-DD
    Uses EXACT same data pipeline + cancellation/no-show filters as calendar_details_view
    so that counts here always match what's visible in the 3-column card view.
    """
    try:
        from core.models import db as _adsdb, Apartment as _AdsApt, Room as _RoomM
        date_str = request.args.get('date', '')
        if not date_str:
            _vn = datetime.utcnow() + timedelta(hours=7)
            date_str = _vn.strftime('%Y-%m-%d')
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()

        # ── Step 1: Same data pipeline as calendar_details_view ──────────────
        df = load_booking_data_for_calculations(force_fresh=True)
        _total_rooms = _RoomM.query.join(_AdsApt).filter(
            _RoomM.is_active == True, _AdsApt.is_active == True
        ).count() or TOTAL_HOTEL_CAPACITY
        day_info = get_overall_calendar_day_info(df, date_str, _total_rooms)

        activity     = day_info.get('activity', {})
        check_in     = list(activity.get('arrivals',   []))
        check_out    = list(activity.get('departures', []))
        staying_over = list(activity.get('staying',    []))

        # ── Step 2: Same cancellation / no-show filter ────────────────────────
        _today_date = (datetime.utcnow() + timedelta(hours=7)).date()

        _ci_bids   = [b.get('Số đặt phòng', '') for b in check_in     if b.get('Số đặt phòng')]
        _stay_bids = [b.get('Số đặt phòng', '') for b in staying_over if b.get('Số đặt phòng')]
        _co_bids   = [b.get('Số đặt phòng', '') for b in check_out    if b.get('Số đặt phòng')]
        _all_visible_bids = list(set(_ci_bids + _stay_bids + _co_bids))

        _all_status_map = {}
        try:
            _st_rows = _adsdb.session.execute(
                text("""SELECT booking_id, checkin_status FROM bookings
                        WHERE checkin_status IS NOT NULL
                          AND (booking_id = ANY(:bids)
                               OR (DATE(checkin_date) = :d AND checkin_status = 'cancelling'))"""),
                {'bids': _all_visible_bids or ['__none__'], 'd': date_obj}
            ).fetchall()
            _all_status_map = {r[0]: r[1] for r in _st_rows}
        except Exception as _se:
            print(f"[apt_summary:{date_obj}] checkin_status query failed: {_se}")

        _cancelling_all = {bid for bid, st in _all_status_map.items() if st == 'cancelling'}

        # Filter check_in (past days: remove cancelling; today: keep all)
        if date_obj != _today_date:
            check_in = [b for b in check_in if b.get('Số đặt phòng', '') not in _cancelling_all]

        from core.occupancy import guest_shown_on

        def _stays_over(g):
            bid = g.get('Số đặt phòng', '')
            return guest_shown_on(date_obj, g.get('Check-in Date'), _all_status_map.get(bid), _today_date)

        _checks_out = _stays_over

        staying_over = [g for g in staying_over if _stays_over(g)]
        check_out    = [g for g in check_out    if _checks_out(g)]

        # ── Step 3: Load actual_apartment assignments from DB ─────────────────
        _all_day_bids = list(set(
            [b.get('Số đặt phòng', '') for b in check_in + staying_over + check_out
             if b.get('Số đặt phòng')]
        ))
        _apt_map = {}
        if _all_day_bids:
            try:
                _ap_rows = _adsdb.session.execute(
                    text("SELECT booking_id, actual_apartment FROM bookings "
                         "WHERE booking_id = ANY(:bids) AND actual_apartment IS NOT NULL"),
                    {'bids': _all_day_bids}
                ).fetchall()
                _apt_map = {r[0]: r[1] for r in _ap_rows}
            except Exception as _me:
                print(f"[apt_summary:{date_obj}] apt_map load failed: {_me}")

        # ── Step 4: Build apartment definitions (same order/colors as view) ───
        # Colors follow the full apartment list so they match the card selector buttons;
        # inactive apartments are only shown when someone is placed in them.
        from core.occupancy import night_status, parse_apartment_id, PENDING_REASON_LABELS, apartment_abbr
        _APT_COLORS = ['#1976D2', '#2E7D32', '#7B1FA2', '#E64A19', '#00838F', '#F57F17']
        _APT_EMOJIS = ['🔵', '🟢', '🟣', '🟠', '🔵', '🟡']
        all_apts = _AdsApt.query.order_by(_AdsApt.apartment_id).all()
        apt_defs = []
        for _i, _a in enumerate(all_apts):
            _cap = _RoomM.query.filter_by(apartment_id=_a.apartment_id, is_active=True).count()
            apt_defs.append({
                'id':        str(_a.apartment_id),
                'name':      _a.apartment_name,
                'abbr':      apartment_abbr(_a.apartment_name),
                'color':     _APT_COLORS[_i % len(_APT_COLORS)],
                'emoji':     _APT_EMOJIS[_i % len(_APT_EMOJIS)],
                'capacity':  _cap,
                'is_active': bool(_a.is_active),
            })
        _known_ids = {int(a['id']) for a in apt_defs}

        def _as_booking(g):
            bid = g.get('Số đặt phòng', '')
            return {
                'booking_id':       bid,
                'checkin_date':     g.get('Check-in Date'),
                'checkout_date':    g.get('Check-out Date'),
                'checkin_status':   _all_status_map.get(bid),
                'actual_apartment': _apt_map.get(bid),
            }

        # ── Step 5: Count per apartment — same rules as the vacancy board ─────
        # Staying + check-in guests occupy a room tonight only once they're placed in an
        # apartment (and, from their arrival day on, confirmed). The rest are "pending".
        staying_map  = {a['id']: [] for a in apt_defs}
        checkin_map  = {a['id']: [] for a in apt_defs}
        checkout_map = {a['id']: [] for a in apt_defs}
        pending = []

        for section, guests, target in (('staying', staying_over, staying_map),
                                         ('checkin', check_in, checkin_map)):
            for g in guests:
                bid  = g.get('Số đặt phòng', '')
                name = g.get('Tên người đặt', '') or bid
                kind, value = night_status(_as_booking(g), date_obj, _today_date, _known_ids)
                if kind == 'apt':
                    target[str(value)].append(name)
                elif kind == 'pending':
                    pending.append({'name': name, 'booking_id': bid, 'section': section,
                                    'reason': value, 'reason_label': PENDING_REASON_LABELS[value]})

        # Check-outs don't occupy tonight; show them under their placed apartment if any
        unset_checkout = []
        for g in check_out:
            bid  = g.get('Số đặt phòng', '')
            name = g.get('Tên người đặt', '') or bid
            apt_id = parse_apartment_id(_apt_map.get(bid))
            if apt_id in _known_ids:
                checkout_map[str(apt_id)].append(name)
            else:
                unset_checkout.append(name)

        result = []
        for a in apt_defs:
            aid = a['id']
            n_stay, n_in = len(staying_map[aid]), len(checkin_map[aid])
            occupied = n_stay + n_in
            if not a['is_active'] and not (occupied or checkout_map[aid]):
                continue
            result.append({
                **a,
                'staying':    staying_map[aid],
                'checkin':    checkin_map[aid],
                'checkout':   checkout_map[aid],
                'n_staying':  n_stay,
                'n_checkin':  n_in,
                'n_checkout': len(checkout_map[aid]),
                'occupied':   occupied,
                'free':       max(a['capacity'] - occupied, 0),
                'over':       max(occupied - a['capacity'], 0),
            })

        unset = [p['name'] for p in pending]
        return jsonify({
            'success':        True,
            'date':           date_str,
            'apartments':     result,
            'pending':        pending,
            'unset':          unset,
            'n_unset':        len(unset),
            'unset_checkout': unset_checkout,
            'over_count':     sum(a['over'] for a in result),
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500


