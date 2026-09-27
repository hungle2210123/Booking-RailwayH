"""
2-bedroom (2 PN) booking flag.

Bookings aren't tied to a physical room (room_id is often a placeholder), so the flag
lives on the booking:
  - bookings.two_bedroom = TRUE / FALSE  -> set by staff (manual override)
  - bookings.two_bedroom = NULL          -> auto-detected from the listing name
    ("2 PN Hàng Bè", "Căn hộ 2 phòng ngủ ...", "Two-Bedroom Apartment", "101 - 2 PN")

"2 Giường" (two beds) is NOT a 2-bedroom unit, so it is deliberately not matched.
"""
import re
import unicodedata

_TWO_BR_PATTERNS = [
    r'\b2\s*-?\s*pn\b',          # "2 PN", "2PN", "2-PN"
    r'\b2\s*phong\s*ngu\b',      # "2 phòng ngủ"
    r'\b2\s*ngu\b',              # "2 ngủ"
    r'\btwo[\s-]*bedroom',       # "Two-Bedroom", "two bedroom"
    r'\b2[\s-]*bedroom',         # "2-Bedroom", "2 bedroom"
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
