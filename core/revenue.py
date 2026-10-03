"""
Revenue / collection rules for the dashboard — ONE definition used everywhere on it.

A booking belongs to the month of its check-in date (whole booking, not split per night).

Excluded entirely (not revenue):
  - booking_status 'cancelled' / 'deleted'
  - checkin_status 'cancelling' (guest cancelled) / 'no_show'

Every other booking gets one status:
  paid      – money collected (collector LOC LE / THAO LE or collected_amount > 0);
              revenue = what was actually collected
  short     – collected, but less than the booking value (discount or partial payment);
              revenue = what was collected, the gap is listed for checking
  due       – guest confirmed arrived, nothing collected yet          → "Chưa thu"
  arriving  – arrival day reached (≤ 2 days ago), not confirmed yet   → expected revenue
  upcoming  – check-in in the future                                  → expected revenue
  review    – arrival day passed > 2 days ago, never confirmed, never paid
              → probably a no-show; NOT counted, listed under "Cần kiểm tra"

Commission counts unless commission_status = 'cancelled' (commission waived).
"""
from collections import OrderedDict, defaultdict
from datetime import date, datetime, timedelta

VALID_COLLECTORS = ('LOC LE', 'THAO LE')
GRACE_DAYS = 2          # same grace period as the calendar's no-show rule
SHORT_TOLERANCE = 1000  # đ — rounding differences are not "thu thiếu"

STATUS_LABELS = {
    'paid': 'Đã thu',
    'short': 'Thu thiếu',
    'due': 'Chưa thu',
    'arriving': 'Chờ xác nhận đến',
    'upcoming': 'Sắp đến',
    'review': 'Cần kiểm tra',
}
COUNTED = ('paid', 'short', 'due', 'arriving', 'upcoming')


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


def classify(b, today):
    """Return an enriched dict for a counted/review booking, or None if excluded."""
    if (b.get('booking_status') or '').strip().lower() in ('cancelled', 'deleted'):
        return None
    if b.get('checkin_status') in ('cancelling', 'no_show'):
        return None

    ci, co = b['checkin_date'], b.get('checkout_date') or b['checkin_date']
    room = _f(b.get('room_amount'))
    collected = _f(b.get('collected_amount'))
    collector = (b.get('collector') or '').strip().upper()
    is_valid_collector = collector in VALID_COLLECTORS
    paid = is_valid_collector or collected > 0
    paid_amount = collected if collected > 0 else (room if is_valid_collector else 0.0)
    confirmed = b.get('checkin_status') == 'confirmed' or bool(b.get('arrival_confirmed'))

    gap = 0.0
    if paid:
        revenue = paid_amount
        gap = room - paid_amount if room - paid_amount > SHORT_TOLERANCE else 0.0
        status = 'short' if gap else 'paid'
    else:
        revenue = room
        if ci > today:
            status = 'upcoming'
        elif confirmed:
            status = 'due'
        elif ci >= today - timedelta(days=GRACE_DAYS):
            status = 'arriving'
        else:
            status = 'review'

    commission = _f(b.get('commission'))
    if (b.get('commission_status') or '').lower() == 'cancelled':
        commission = 0.0

    return {
        'booking_id': b['booking_id'],
        'name': b.get('guest_name') or b['booking_id'],
        'checkin': ci,
        'checkout': co,
        'nights': max((co - ci).days, 1),
        'month': ci.strftime('%Y-%m'),
        'listing': b.get('accommodation_name') or '',
        'apartment_id': str(b.get('actual_apartment') or '').strip(),
        'room_amount': room,
        'paid_amount': paid_amount,
        'collector': collector if paid else '',
        'revenue': revenue,
        'gap': gap,
        'commission': commission if status != 'review' else 0.0,
        'raw_commission': _f(b.get('commission')),
        'commission_status': b.get('commission_status') or 'pending',
        'status': status,
        'status_label': STATUS_LABELS[status],
        'confirmed': confirmed,
    }


def _empty_totals():
    return {k: 0.0 for k in ('revenue', 'collected', 'due', 'expected', 'review', 'gap',
                             'commission', 'nights')} | {
        'bookings': 0, 'paid_count': 0, 'due_count': 0, 'expected_count': 0,
        'review_count': 0, 'short_count': 0}


def _add(t, x):
    if x['status'] == 'review':
        t['review'] += x['room_amount']
        t['review_count'] += 1
        return
    t['revenue'] += x['revenue']
    t['commission'] += x['commission']
    t['nights'] += x['nights']
    t['bookings'] += 1
    if x['status'] in ('paid', 'short'):
        t['collected'] += x['paid_amount']
        t['paid_count'] += 1
        if x['status'] == 'short':
            t['gap'] += x['gap']
            t['short_count'] += 1
    elif x['status'] == 'due':
        t['due'] += x['revenue']
        t['due_count'] += 1
    else:  # arriving / upcoming
        t['expected'] += x['revenue']
        t['expected_count'] += 1


def _finish(t):
    t['net'] = t['revenue'] - t['commission']
    t['collect_rate'] = round(t['collected'] / t['revenue'] * 100, 1) if t['revenue'] else 0.0
    t['avg_per_night'] = round(t['revenue'] / t['nights']) if t['nights'] else 0
    return t


def month_shift(month, delta):
    y, m = map(int, month.split('-'))
    m += delta
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f'{y:04d}-{m:02d}'


def _row(x, apt_names):
    return {
        'booking_id': x['booking_id'], 'name': x['name'],
        'checkin': x['checkin'].isoformat(), 'checkout': x['checkout'].isoformat(),
        'nights': x['nights'], 'listing': x['listing'],
        'apartment': apt_names.get(x['apartment_id'], ''),
        'room_amount': x['room_amount'], 'paid_amount': x['paid_amount'],
        'revenue': x['revenue'], 'gap': x['gap'], 'commission': x['raw_commission'],
        'commission_status': x['commission_status'],
        'collector': x['collector'], 'status': x['status'], 'status_label': x['status_label'],
    }


def build_overview(bookings, month, apartments, expenses_by_month=None, today=None, months_back=12):
    """Everything the dashboard shows for `month` (YYYY-MM).

    apartments: list of {id, name, color}; expenses_by_month: {YYYY-MM: {'total', 'work'}}.
    """
    today = today or vn_today()
    apt_names = {str(a['id']): a['name'] for a in apartments}
    items = [x for x in (classify(b, today) for b in bookings) if x]

    by_month = defaultdict(_empty_totals)
    collectors_by_month = defaultdict(lambda: defaultdict(float))
    for x in items:
        _add(by_month[x['month']], x)
        if x['status'] in ('paid', 'short'):
            collectors_by_month[x['month']][x['collector'] or 'Khác'] += x['paid_amount']

    expenses_by_month = expenses_by_month or {}

    # 12-month series ending at the selected month
    series = []
    for i in range(months_back - 1, -1, -1):
        m = month_shift(month, -i)
        t = _finish(dict(by_month[m])) if m in by_month else _finish(_empty_totals())
        c = collectors_by_month.get(m, {})
        series.append({
            'month': m, 'revenue': t['revenue'], 'collected': t['collected'], 'due': t['due'],
            'expected': t['expected'], 'commission': t['commission'], 'net': t['net'],
            'bookings': t['bookings'],
            'loc': c.get('LOC LE', 0.0), 'thao': c.get('THAO LE', 0.0), 'other': c.get('Khác', 0.0),
        })

    kpis = _finish(dict(by_month[month])) if month in by_month else _finish(_empty_totals())
    prev = by_month.get(month_shift(month, -1))
    prev_rev = prev['revenue'] if prev else 0.0
    kpis['prev_revenue'] = prev_rev
    kpis['change_pct'] = round((kpis['revenue'] - prev_rev) / prev_rev * 100, 1) if prev_rev else None
    exp = expenses_by_month.get(month)
    kpis['expenses'] = exp['total'] if exp else None
    kpis['expenses_work'] = exp['work'] if exp else None
    kpis['profit'] = kpis['net'] - exp['work'] if exp else None

    month_items = [x for x in items if x['month'] == month]

    # Collectors this month
    coll = defaultdict(lambda: {'amount': 0.0, 'count': 0})
    for x in month_items:
        if x['status'] in ('paid', 'short'):
            k = x['collector'] or 'Khác'
            coll[k]['amount'] += x['paid_amount']
            coll[k]['count'] += 1
    collectors = [{'name': k, **v} for k, v in sorted(coll.items(), key=lambda kv: -kv[1]['amount'])]

    # Apartments this month (by placement)
    apt = OrderedDict((str(a['id']), {'id': str(a['id']), 'name': a['name'], 'color': a.get('color', '#64748b'),
                                      'revenue': 0.0, 'collected': 0.0, 'count': 0, 'nights': 0})
                      for a in apartments)
    apt['__none__'] = {'id': '', 'name': 'Chưa xếp căn', 'color': '#94a3b8',
                       'revenue': 0.0, 'collected': 0.0, 'count': 0, 'nights': 0}
    for x in month_items:
        if x['status'] == 'review':
            continue
        a = apt.get(x['apartment_id']) or apt['__none__']
        a['revenue'] += x['revenue']
        a['count'] += 1
        a['nights'] += x['nights']
        if x['status'] in ('paid', 'short'):
            a['collected'] += x['paid_amount']
    apartments_out = [a for a in apt.values() if a['count'] or a['id']]

    def rows(status, newest_first):
        return sorted((_row(x, apt_names) for x in items if x['status'] == status),
                      key=lambda r: r['checkin'], reverse=newest_first)

    lists = {
        'month': sorted((_row(x, apt_names) for x in month_items), key=lambda r: (r['checkin'], r['name'])),
        # Across ALL months: debts oldest first so nothing slips through; checks newest first
        'due_all': rows('due', newest_first=False),
        'review_all': rows('review', newest_first=True),
        'short_all': rows('short', newest_first=True),
    }

    totals_all = {
        'due': sum(r['revenue'] for r in lists['due_all']),
        'due_count': len(lists['due_all']),
        'review': sum(r['room_amount'] for r in lists['review_all']),
        'review_count': len(lists['review_all']),
        'gap': sum(r['gap'] for r in lists['short_all']),
        'short_count': len(lists['short_all']),
    }

    months_available = sorted(by_month.keys(), reverse=True)
    return {
        'month': month,
        'today': today.isoformat(),
        'kpis': kpis,
        'series': series,
        'collectors': collectors,
        'apartments': apartments_out,
        'lists': lists,
        'totals_all': totals_all,
        'months_available': months_available,
    }
