"""
2-bedroom (2 PN) booking flag.

Bookings aren't tied to a physical room (room_id is often a placeholder), so the flag
lives on the booking:
  - bookings.two_bedroom = TRUE / FALSE  -> set by staff (manual override)
  - bookings.two_bedroom = NULL          -> auto-detected from the listing name
    ("2 PN Hàng Bè", "Căn hộ 2 phòng ngủ ...", "Two-Bedroom Apartment", "101 - 2 PN")

"2 Giường" listings count too (owner, Oct 25: they are priced like the 2-bedroom units and
must be watched the same way) — but "Giường đôi" / "Giường cỡ King" (one bed) do not.
"""
import re
import unicodedata

_TWO_BR_PATTERNS = [
    r'\b2\s*-?\s*pn\b',          # "2 PN", "2PN", "2-PN"
    r'\b2\s*phong\s*ngu\b',      # "2 phòng ngủ"
    r'\b2\s*ngu\b',              # "2 ngủ"
    r'\btwo[\s-]*bedroom',       # "Two-Bedroom", "two bedroom"
    r'\b2[\s-]*bedroom',         # "2-Bedroom", "2 bedroom"
    r'\b2\s*giuong\b',           # "2 Giường 18 Hàng Bè", "2 Giường Hội Vũ"
    r'\btwo[\s-]*beds?\b',       # "Two Beds"
    r'\b2[\s-]*beds\b',          # "2 beds"
]
_TWO_BR_RE = re.compile('|'.join(_TWO_BR_PATTERNS))


def _fold(text):
    text = unicodedata.normalize('NFD', str(text or ''))
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    return text.replace('đ', 'd').replace('Đ', 'D').lower()


def listing_is_two_bedroom(listing_name):
    return bool(_TWO_BR_RE.search(_fold(listing_name)))


def is_two_bedroom(listing_name, manual_flag=None):
    """Manual flag wins; otherwise detect from the listing name."""
    if manual_flag is not None:
        return bool(manual_flag)
    return listing_is_two_bedroom(listing_name)


def ensure_column(session, text):
    """Add bookings.two_bedroom if missing (safe to call on every request)."""
    try:
        session.execute(text("ALTER TABLE bookings ADD COLUMN IF NOT EXISTS two_bedroom BOOLEAN DEFAULT NULL"))
        session.commit()
    except Exception:
        session.rollback()


def load_manual_flags(session, text, booking_ids):
    """{booking_id: True/False} for bookings where staff set the flag by hand."""
    booking_ids = [b for b in booking_ids if b]
    if not booking_ids:
        return {}
    ensure_column(session, text)
    rows = session.execute(text(
        "SELECT booking_id, two_bedroom FROM bookings "
        "WHERE booking_id = ANY(:bids) AND two_bedroom IS NOT NULL"
    ), {'bids': list(booking_ids)}).fetchall()
    return {r[0]: bool(r[1]) for r in rows}


def watch_days(session, text, start, days, today, apartments=None):
    """2PN arrivals / check-outs / guests staying for each day in [start, start + days).

    Used by the Phòng trống board so 2-bedroom turnovers further ahead are visible.
    Skips cancelled / Báo hủy / no-show bookings and unconfirmed guests more than 2 days
    past arrival (same rules as the calendar_details 2PN panel).
    `apartments`: {apartment_id: {'abbr': ...}} to label placed guests.
    """
    from datetime import timedelta
    ensure_column(session, text)
    end = start + timedelta(days=days)
    rows = session.execute(text("""
        SELECT booking_id, guest_name, checkin_date, checkout_date, accommodation_name,
               actual_apartment, checkin_status, two_bedroom
        FROM bookings
        WHERE checkin_date <= :end AND checkout_date >= :start
          AND COALESCE(booking_status, '') NOT IN ('cancelled', 'deleted')
          AND COALESCE(checkin_status, '') NOT IN ('cancelling', 'no_show')
        ORDER BY checkin_date, guest_name
    """), {'start': start, 'end': end}).fetchall()

    guests = []
    for bid, name, ci, co, listing, apt, status, flag in rows:
        if not ci or not co or not is_two_bedroom(listing, flag):
            continue
        if status != 'confirmed' and ci < today - timedelta(days=2):
            continue
        apt_id = str(apt or '').strip()
        abbr = ''
        if apt_id and apartments:
            info = apartments.get(int(apt_id)) if apt_id.isdigit() else None
            abbr = info['abbr'] if info else ''
        guests.append({
            'booking_id': bid, 'name': name or bid, 'checkin': ci, 'checkout': co,
            'nights': max((co - ci).days, 1), 'apt': abbr, 'placed': bool(abbr),
            'confirmed': status == 'confirmed',
        })

    def _short(g):
        return {k: g[k] for k in ('booking_id', 'name', 'nights', 'apt', 'placed', 'confirmed')}

    out = []
    for i in range(days):
        d = start + timedelta(days=i)
        arrive = [_short(g) for g in guests if g['checkin'] == d]
        leave = [_short(g) for g in guests if g['checkout'] == d]
        stay = [_short(g) for g in guests if g['checkin'] < d < g['checkout']]
        out.append({'date': d.strftime('%Y-%m-%d'), 'in': arrive, 'out': leave, 'stay': stay})
    return out
