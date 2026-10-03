"""
Revenue rules for the dashboard — ONE definition used everywhere on it.

Revenue is recognised PER NIGHT STAYED: a booking's value is split evenly over its
nights, so a day's revenue = the nights sold that day, and a month's revenue = the sum
of its days (the daily calendar always adds up to the month total).

Excluded entirely (not revenue):
  - booking_status 'cancelled' / 'deleted'
  - checkin_status 'cancelling' (guest cancelled) / 'no_show'

Every other booking gets one status (applied to each of its nights):
  paid      – money collected (collector LOC LE / THAO LE or collected_amount > 0);
              value = what was actually collected
  due       – guest confirmed arrived, nothing collected yet          → "Chưa thu"
  expected  – check-in in the future, or arrival day reached (≤ 2 days ago) but not
              confirmed yet                                           → "Dự kiến"
  review    – arrival day passed > 2 days ago, never confirmed, never paid
              → probably a no-show; NOT counted (handled on the calendar page)

Commission counts unless commission_status = 'cancelled' (commission waived).
Room capacity per day = active rooms that existed that day (rooms from the initial
database setup count from the start).
"""
import calendar as _cal
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta

VALID_COLLECTORS = ('LOC LE', 'THAO LE')
GRACE_DAYS = 2          # same grace period as the calendar's no-show rule

STATUS_LABELS = {'paid': 'Đã thu', 'due': 'Chưa thu', 'expected': 'Dự kiến', 'review': 'Cần kiểm tra'}
WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN']


def vn_today():
    return (datetime.utcnow() + timedelta(hours=7)).date()


def _f(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def load_bookings(session, text):
    rows = session.execute(text("""
        SELECT booking_id, guest_name, checkin_date, checkout_date,
               room_amount, collected_amount, commission, commission_status,
               collector, booking_status, checkin_status, arrival_confirmed,
               actual_apartment, accommodation_name
        FROM bookings
        WHERE checkin_date IS NOT NULL
    """)).fetchall()
    keys = ('booking_id', 'guest_name', 'checkin_date', 'checkout_date',
            'room_amount', 'collected_amount', 'commission', 'commission_status',
            'collector', 'booking_status', 'checkin_status', 'arrival_confirmed',
            'actual_apartment', 'accommodation_name')
    return [dict(zip(keys, r)) for r in rows]


def load_rooms(session, text):
    """Active rooms of active apartments with the date they start counting."""
    rows = session.execute(text("""
        SELECT r.room_id, r.apartment_id, r.created_at::date
        FROM rooms r JOIN apartments a ON a.apartment_id = r.apartment_id
        WHERE r.is_active = true AND a.is_active = true
    """)).fetchall()
    first = min((r[2] for r in rows if r[2]), default=None)
    # Rooms created when the database was first set up existed before that date too
    return [{'apartment_id': r[1], 'since': None if (r[2] is None or r[2] == first) else r[2]} for r in rows]


def classify(b, today):
    """Enriched dict for a booking, or None if it is excluded."""
    if (b.get('booking_status') or '').strip().lower() in ('cancelled', 'deleted'):
        return None
    if b.get('checkin_status') in ('cancelling', 'no_show'):
        return None

    ci = b['checkin_date']
    co = b.get('checkout_date') or ci
    nights = max((co - ci).days, 1)
    room = _f(b.get('room_amount'))
    collected = _f(b.get('collected_amount'))
    collector = (b.get('collector') or '').strip().upper()
    valid_collector = collector in VALID_COLLECTORS
    paid = valid_collector or collected > 0
    confirmed = b.get('checkin_status') == 'confirmed' or bool(b.get('arrival_confirmed'))

    if paid:
        value = collected if collected > 0 else room
        status = 'paid'
    else:
        value = room
        if ci > today:
            status = 'expected'
        elif confirmed:
            status = 'due'
        elif ci >= today - timedelta(days=GRACE_DAYS):
            status = 'expected'
        else:
            status = 'review'

    commission = 0.0 if (b.get('commission_status') or '').lower() == 'cancelled' else _f(b.get('commission'))
    return {
        'booking_id': b['booking_id'],
        'name': b.get('guest_name') or b['booking_id'],
        'checkin': ci, 'checkout': co, 'nights': nights,
        'listing': b.get('accommodation_name') or '',
        'apartment_id': str(b.get('actual_apartment') or '').strip(),
        'value': value,
        'per_night': value / nights,
        'commission_per_night': commission / nights,
        'collector': collector if paid else '',
        'status': status,
    }


def _nights_of(x):
    """Dates whose night this booking occupies (a same-day booking counts on check-in day)."""
    return [x['checkin'] + timedelta(days=i) for i in range(x['nights'])]


def _month_key(d):
    return d.strftime('%Y-%m')


def month_shift(month, delta):
    y, m = map(int, month.split('-'))
    m += delta
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f'{y:04d}-{m:02d}'


def _zero():
    return {'revenue': 0.0, 'collected': 0.0, 'due': 0.0, 'expected': 0.0,
            'commission': 0.0, 'room_nights': 0, 'capacity': 0, 'arrivals': 0, 'departures': 0}


def _add_night(t, x):
    t['revenue'] += x['per_night']
    t['commission'] += x['commission_per_night']
    t['room_nights'] += 1
    key = {'paid': 'collected', 'due': 'due', 'expected': 'expected'}[x['status']]
    t[key] += x['per_night']


def _ratios(t):
    t['net'] = t['revenue'] - t['commission']
    t['adr'] = round(t['revenue'] / t['room_nights']) if t['room_nights'] else 0      # giá TB / đêm phòng
    # More nights sold than rooms on record = the room list didn't cover that period
    # (older units were never entered) → occupancy/RevPAR unknown rather than >100%.
    t['capacity_known'] = bool(t['capacity']) and t['room_nights'] <= t['capacity']
    t['occupancy'] = round(t['room_nights'] / t['capacity'] * 100, 1) if t['capacity_known'] else None
    t['revpar'] = round(t['revenue'] / t['capacity']) if t['capacity_known'] else None
    t['collect_rate'] = round(t['collected'] / t['revenue'] * 100, 1) if t['revenue'] else 0.0
    return t


def build_overview(bookings, rooms, month, apartments, expenses_by_month=None, today=None, months_back=12):
    """Everything the dashboard shows for `month` (YYYY-MM).

    rooms: from load_rooms(); apartments: [{id, name, color}];
    expenses_by_month: {YYYY-MM: {'total', 'work'}}.
    """
    today = today or vn_today()
    expenses_by_month = expenses_by_month or {}
    apt_names = {str(a['id']): a['name'] for a in apartments}
    items = [x for x in (classify(b, today) for b in bookings) if x]
    counted = [x for x in items if x['status'] != 'review']

    def capacity_on(d, apartment_id=None):
        return sum(1 for r in rooms
                   if (r['since'] is None or r['since'] <= d)
                   and (apartment_id is None or str(r['apartment_id']) == apartment_id))

    # ── Per-night aggregation ─────────────────────────────────────────
    by_day = defaultdict(_zero)
    by_month = defaultdict(_zero)
    collectors_month = defaultdict(lambda: defaultdict(float))
    for x in counted:
        for d in _nights_of(x):
            _add_night(by_day[d], x)
            _add_night(by_month[_month_key(d)], x)
            if x['status'] == 'paid':
                collectors_month[_month_key(d)][x['collector'] or 'Khác'] += x['per_night']
        by_day[x['checkin']]['arrivals'] += 1
        by_day[x['checkout']]['departures'] += 1

    def month_days(m):
        y, mm = map(int, m.split('-'))
        first = datetime(y, mm, 1).date()
        return [first + timedelta(days=i) for i in range(_cal.monthrange(y, mm)[1])]

    def month_totals(m):
        t = dict(by_month[m]) if m in by_month else _zero()
        t['capacity'] = sum(capacity_on(d) for d in month_days(m))
        return _ratios(t)

    # ── 12-month series ending at the selected month ─────────────────
    series = []
    for i in range(months_back - 1, -1, -1):
        m = month_shift(month, -i)
        t = month_totals(m)
        c = collectors_month.get(m, {})
        series.append({'month': m, 'revenue': t['revenue'], 'collected': t['collected'], 'due': t['due'],
                       'expected': t['expected'], 'net': t['net'], 'occupancy': t['occupancy'],
                       'adr': t['adr'], 'room_nights': t['room_nights'],
                       'loc': c.get('LOC LE', 0.0), 'thao': c.get('THAO LE', 0.0)})

    # ── Selected month KPIs ──────────────────────────────────────────
    k = month_totals(month)
    prev = month_totals(month_shift(month, -1))
    k['prev_revenue'] = prev['revenue']
    k['prev_occupancy'] = prev['occupancy']
    k['change_pct'] = round((k['revenue'] - prev['revenue']) / prev['revenue'] * 100, 1) if prev['revenue'] else None
    exp = expenses_by_month.get(month)
    k['expenses'] = exp['total'] if exp else None
    k['expenses_work'] = exp['work'] if exp else None
    k['profit'] = k['net'] - exp['work'] if exp else None
    review_month = [x for x in items if x['status'] == 'review' and _month_key(x['checkin']) == month]
    k['review_count'] = len(review_month)
    k['review_value'] = sum(x['value'] for x in review_month)

    # ── Daily calendar for the month ─────────────────────────────────
    days_list = month_days(month)
    night_rows = defaultdict(list)       # date -> bookings staying that night
    for x in counted:
        for d in _nights_of(x):
            if _month_key(d) == month:
                night_rows[d].append(x)
    days = []
    for d in days_list:
        t = dict(by_day[d]) if d in by_day else _zero()
        t['capacity'] = capacity_on(d)
        _ratios(t)
        days.append({
            'date': d.isoformat(), 'weekday': WEEKDAYS[d.weekday()], 'is_weekend': d.weekday() >= 5,
            'revenue': t['revenue'], 'collected': t['collected'], 'due': t['due'], 'expected': t['expected'],
            'room_nights': t['room_nights'], 'capacity': t['capacity'], 'occupancy': t['occupancy'],
            'adr': t['adr'], 'arrivals': t['arrivals'], 'departures': t['departures'],
            'guests': sorted(({
                'booking_id': x['booking_id'], 'name': x['name'],
                'apartment': apt_names.get(x['apartment_id'], ''), 'listing': x['listing'],
                'per_night': x['per_night'], 'status': x['status'], 'status_label': STATUS_LABELS[x['status']],
                'checkin': x['checkin'].isoformat(), 'checkout': x['checkout'].isoformat(), 'nights': x['nights'],
                'is_arrival': x['checkin'] == d, 'is_last_night': x['checkout'] == d + timedelta(days=1),
            } for x in night_rows.get(d, [])), key=lambda g: (g['apartment'] or 'zz', g['name'])),
        })

    # Day statistics — for a month still in progress only the days up to today count,
    # otherwise future (still empty) days would drag averages down and look "empty"
    elapsed = [x for x in days if x['date'] <= today.isoformat()] or days
    best = max(days, key=lambda x: x['revenue']) if days else None
    weekday_rev = [x['revenue'] for x in elapsed if not x['is_weekend']]
    weekend_rev = [x['revenue'] for x in elapsed if x['is_weekend']]
    stats = {
        'best_day': {'date': best['date'], 'revenue': best['revenue']} if best and best['revenue'] else None,
        'avg_day': round(sum(x['revenue'] for x in elapsed) / len(elapsed)) if elapsed else 0,
        'avg_weekday': round(sum(weekday_rev) / len(weekday_rev)) if weekday_rev else 0,
        'avg_weekend': round(sum(weekend_rev) / len(weekend_rev)) if weekend_rev else 0,
        'empty_days': sum(1 for x in elapsed if x['capacity'] and x['room_nights'] == 0),
        'full_days': sum(1 for x in elapsed if x['capacity'] and x['room_nights'] >= x['capacity']),
        'days_counted': len(elapsed),
        'days_in_month': len(days),
    }

    # ── Collectors & apartments for the month ────────────────────────
    total_paid = sum(collectors_month.get(month, {}).values())
    collectors = [{'name': n, 'amount': a, 'share': round(a / total_paid * 100, 1) if total_paid else 0}
                  for n, a in sorted(collectors_month.get(month, {}).items(), key=lambda kv: -kv[1])]

    apt = OrderedDict((str(a['id']), {'id': str(a['id']), 'name': a['name'], 'color': a.get('color', '#64748b'),
                                      'revenue': 0.0, 'collected': 0.0, 'room_nights': 0, 'capacity': 0})
                      for a in apartments)
    apt['__none__'] = {'id': '', 'name': 'Chưa xếp căn', 'color': '#94a3b8',
                       'revenue': 0.0, 'collected': 0.0, 'room_nights': 0, 'capacity': 0}
    for d, staying in night_rows.items():
        for x in staying:
            a = apt.get(x['apartment_id']) or apt['__none__']
            a['revenue'] += x['per_night']
            a['room_nights'] += 1
            if x['status'] == 'paid':
                a['collected'] += x['per_night']
    for key, a in apt.items():
        if key != '__none__':
            a['capacity'] = sum(capacity_on(d, key) for d in days_list)
        known = a['capacity'] and a['room_nights'] <= a['capacity']
        a['occupancy'] = round(a['room_nights'] / a['capacity'] * 100, 1) if known else None
        a['adr'] = round(a['revenue'] / a['room_nights']) if a['room_nights'] else 0
    apartments_out = [a for a in apt.values() if a['room_nights'] or a['capacity']]

    months_available = sorted({_month_key(d) for d in by_day.keys()}, reverse=True)
    return {
        'month': month, 'today': today.isoformat(),
        'kpis': k, 'stats': stats, 'series': series, 'days': days,
        'collectors': collectors, 'apartments': apartments_out,
        'months_available': months_available,
    }
