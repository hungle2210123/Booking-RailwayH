---
paths:
  - "chrome_extension/**"
  - "app_parts/p02_*.py"
  - "core/booking_page_parser.py"
---
# Chrome extension + Booking.com data — read docs/extension.md for the full notes
- The extension is READ-ONLY on Booking: never auto-click "Hiển thị số điện thoại", never call Booking APIs, never scrape,
  never send messages. It only reads the page the owner opened and TYPES into Booking's chat box; the owner presses Gửi.
- Never log in to Booking or handle the owner's passwords.
- Cancelled on Booking → `checkin_status='cancelling'` (Báo hủy, undoable), never `booking_status='cancelled'`.
- Several rooms in one reservation → one booking per room: `<id>`, `<id>-2`, … (`_ext_save_rooms`, page order); rate-plan lines
  ("Standard Rate … Genius 15%") are never rooms (`_is_rate_line`).
- Partner bookings: the page phone (tail 035640799) is the partner's — never store it as the guest's.
- Bump `chrome_extension/manifest.json` version on every extension change; the owner reloads it in chrome://extensions
  (also on a second laptop by copying the folder).
- After changes: `python -m pytest tests/test_parsers.py tests/test_flows.py`.
