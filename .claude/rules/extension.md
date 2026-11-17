---
paths:
  - "chrome_extension/**"
  - "app_parts/p02_*.py"
  - "core/booking_page_parser.py"
---
# Chrome extension + Booking.com data — read docs/extension.md for the full notes
- The extension is READ-ONLY on Booking: auto-clicks "Hiển thị số điện thoại" ONLY once per opened booking (owner decision 17/11/2026, popup switch, also during ▶ runs incl. 7:00 since 1.23, not partner bookings), never call Booking APIs,
  never send messages. ONE exception (owner, 17/11/2026, accepts the account risk): "▶ Mở từng khách" (content.js end)
  opens the guests of the visible list one by one at human speed after the owner presses it, saves each, returns.
  Also by itself at 7:00 daily (background.js alarm opens admin.booking.com, uses the owner's open session, never logs in). It only reads the page the owner opened and TYPES into Booking's chat box; the owner presses Gửi.
- The extension never logs in to Booking or handles the owner's passwords. Re-login after a logout = separate Tampermonkey script
  `tools/tu-dong-dang-nhap/` (login pages only); keep the extension and that script apart.
- Group overview (several properties, ext 1.25): `groupProps` / `groupStep` in content.js chain the properties with arrivals;
  `guestLinks` returns nothing there (8-digit property IDs look like booking numbers).
- Cancelled on Booking → `checkin_status='cancelling'` (Báo hủy, undoable), never `booking_status='cancelled'`.
- Several rooms in one reservation → one booking per room: `<id>`, `<id>-2`, … (`_ext_save_rooms`, page order); rate-plan lines
  ("Standard Rate … Genius 15%") are never rooms (`_is_rate_line`).
- Partner bookings: the page phone (tail 035640799) is the partner's — never store it as the guest's.
- Bump `chrome_extension/manifest.json` version on every extension change; the owner reloads it in chrome://extensions
  (also on a second laptop by copying the folder).
- After changes: `python -m pytest tests/test_parsers.py tests/test_flows.py`.
