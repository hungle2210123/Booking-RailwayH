"""
Room occupancy rules shared by the vacancy board, the apartment status bar and
the "is this apartment already full?" check.

Why placement-based: the listing name a guest booked on Booking.com does NOT tell
which physical apartment they end up in (e.g. "Ban Công Hàng Bạc" guests have been
placed in all five apartments), and bookings.room_id is often a placeholder or wrong.
So a booking only counts against an apartment once staff has placed it there
(bookings.actual_apartment). Everything else is reported as "pending" instead of
being guessed into some apartment.

Rules for one booking on one night:
  - checkin_status 'cancelling' / 'no_show'                      -> ignored
  - arrival day reached (check-in <= today) but not confirmed:
        more than NO_SHOW_GRACE_DAYS after check-in              -> ignored (no-show)
        otherwise                                                -> pending 'unconfirmed'
  - no actual_apartment (or an apartment that isn't active)      -> pending 'unassigned'
  - otherwise                                                    -> counts in that apartment
"""
from collections import OrderedDict
from datetime import datetime, timedelta, date as _date

# Same cutoff as calendar_details: unconfirmed for more than 2 days after check-in = no-show
NO_SHOW_GRACE_DAYS = 2
IGNORED_CHECKIN_STATUSES = ('cancelling', 'no_show')
INACTIVE_BOOKING_STATUSES = ('cancelled', 'deleted')

PENDING_REASON_LABELS = {
    'unconfirmed': 'chưa xác nhận đến',
    'unassigned': 'chưa xếp căn',
}


def vn_today():
    """Vietnam local date (server runs UTC)."""
    return (datetime.utcnow() + timedelta(hours=7)).date()


def apartment_abbr(name):
    """'118 Hang Bac Hostel' -> '118HB', '18 Hang Be' -> '18HB', '19  Tho Nhuom' -> '19TN'."""
    words = (name or '').split()
    if not words:
        return '?'
    if words[0].isdigit():
        rest = words[1:3]
        if len(rest) == 1 and rest[0].isupper():   # already an abbreviation, e.g. "19 TN"
            return words[0] + rest[0]
        initials = ''.join(w[0].upper() for w in rest if w and w[0].isalpha())
        return words[0] + initials
    return ''.join(w[0].upper() for w in words[:3] if w)


def parse_apartment_id(value):
    try:
        return int(str(value).strip()) if value not in (None, '') else None
    except (TypeError, ValueError):
        return None


def _as_date(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, _date):
        return value
    try:
        import pandas as pd
        return pd.Timestamp(value).date() if pd.notna(value) else None
    except Exception:
        return None


def guest_shown_on(view_date, checkin_date, checkin_status, today=None):
    """Should a staying / check-out guest appear when looking at `view_date`?

    - confirmed                                   -> yes
    - cancelling / no_show                        -> no
    - unconfirmed, more than the grace period past check-in -> no (no-show)
    - unconfirmed whose arrival day has come, viewed on a FUTURE date -> no:
      they haven't shown up yet, so tomorrow's list must not assume they did
      (they come back as soon as staff press "Xác nhận đến")
    - otherwise (today's view within the grace period, or not arrived yet) -> yes
    """
    today = today or vn_today()
    if checkin_status == 'confirmed':
        return True
    if checkin_status in IGNORED_CHECKIN_STATUSES:
        return False
    ci = _as_date(checkin_date)
    if ci is None:
        return True
    if ci < today - timedelta(days=NO_SHOW_GRACE_DAYS):
        return False
    if _as_date(view_date) > today and ci <= today:
        return False
    return True


def night_status(booking, night, today=None, active_apartment_ids=None):
    """Classify one booking for one night.

    booking: dict with checkin_date, checkout_date, checkin_status, actual_apartment
    Returns ('ignore', None) | ('pending', reason) | ('apt', apartment_id)
    """
    today = today or vn_today()
    ci = _as_date(booking.get('checkin_date'))
    co = _as_date(booking.get('checkout_date'))
    if not ci or not co or not (ci <= night < co):
        return ('ignore', None)

    status = booking.get('checkin_status')
    if status in IGNORED_CHECKIN_STATUSES:
        return ('ignore', None)

    if ci <= today and status != 'confirmed':
        if ci < today - timedelta(days=NO_SHOW_GRACE_DAYS):
            return ('ignore', None)
        return ('pending', 'unconfirmed')

    apt_id = parse_apartment_id(booking.get('actual_apartment'))
    if apt_id is None or (active_apartment_ids is not None and apt_id not in active_apartment_ids):
        return ('pending', 'unassigned')
    return ('apt', apt_id)


def load_apartments(session, text):
    """Active apartments (in id order) with their active room count as capacity."""
    rows = session.execute(text("""
        SELECT a.apartment_id, a.apartment_name, COUNT(r.room_id) AS rooms
        FROM apartments a
        LEFT JOIN rooms r ON r.apartment_id = a.apartment_id AND r.is_active = true
        WHERE a.is_active = true
        GROUP BY a.apartment_id, a.apartment_name
        ORDER BY a.apartment_id
    """)).fetchall()
    apartments = OrderedDict()
    for apt_id, name, rooms in rows:
        apartments[apt_id] = {
            'id': apt_id,
            'name': name,
            'abbr': apartment_abbr(name),
            'capacity': int(rooms or 0),
        }
    return apartments


def load_bookings(session, text, start, end):
    """Active bookings with at least one night in [start, end)."""
    rows = session.execute(text("""
        SELECT booking_id, guest_name, checkin_date, checkout_date,
               checkin_status, actual_apartment, accommodation_name
        FROM bookings
        WHERE checkin_date < :end AND checkout_date > :start
          AND COALESCE(booking_status, '') NOT IN ('cancelled', 'deleted')
    """), {'start': start, 'end': end}).fetchall()
    return [{
        'booking_id': r[0], 'guest_name': r[1] or r[0],
        'checkin_date': r[2], 'checkout_date': r[3],
        'checkin_status': r[4], 'actual_apartment': r[5],
        'accommodation_name': r[6] or '',
    } for r in rows]


def occupancy_for_night(bookings, apartments, night, today=None):
    """Per-apartment occupancy for one night plus the list of pending guests.

    free = rooms not taken by placed guests; over = placed guests beyond capacity.
    sellable = free - pending (negative means more guests than rooms).
    """
    today = today or vn_today()
    active_ids = set(apartments.keys())
    placed = {apt_id: [] for apt_id in apartments}
    pending = []
    for b in bookings:
        kind, value = night_status(b, night, today, active_ids)
        if kind == 'apt':
            placed[value].append(b['guest_name'])
        elif kind == 'pending':
            pending.append({
                'name': b['guest_name'],
                'booking_id': b['booking_id'],
                'reason': value,
                'reason_label': PENDING_REASON_LABELS[value],
                'listing': b.get('accommodation_name', ''),
            })

    apts_out = []
    total_free = 0
    over_count = 0
    for apt in apartments.values():
        guests = placed[apt['id']]
        occupied = len(guests)
        free = max(apt['capacity'] - occupied, 0)
        over = max(occupied - apt['capacity'], 0)
        total_free += free
        over_count += over
        apts_out.append({
            'id': apt['id'], 'name': apt['name'], 'abbr': apt['abbr'],
            'total': apt['capacity'], 'occupied': occupied,
            'free': free, 'over': over, 'guests': guests,
        })

    return {
        'apts': apts_out,
        'total_free': total_free,
        'pending': pending,
        'pending_count': len(pending),
        'sellable': total_free - len(pending),
        'over_count': over_count,
    }


def placement_conflicts(bookings, apartment, booking_id, checkin, checkout):
    """Nights in [checkin, checkout) where `apartment` would exceed its room count if
    `booking_id` were placed there. Counts every booking already placed in that
    apartment (confirmed or not) — this check is about not double-placing guests."""
    checkin, checkout = _as_date(checkin), _as_date(checkout)
    conflicts = []
    if not checkin or not checkout:
        return conflicts
    night = checkin
    while night < checkout:
        others = [
            b['guest_name'] for b in bookings
            if b['booking_id'] != booking_id
            and parse_apartment_id(b.get('actual_apartment')) == apartment['id']
            and b.get('checkin_status') not in IGNORED_CHECKIN_STATUSES
            and _as_date(b['checkin_date']) <= night < _as_date(b['checkout_date'])
        ]
        if len(others) + 1 > apartment['capacity']:
            conflicts.append({'night': night.isoformat(), 'placed': len(others), 'guests': others})
        night += timedelta(days=1)
    return conflicts
