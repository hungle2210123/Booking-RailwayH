---
paths:
  - "app_parts/p03_*.py"
  - "templates/messages.html"
  - "templates/quick.html"
  - "templates/journey_settings.html"
  - "static/js/journey.js"
  - "core/journey.py"
---
# Guest messaging (/messages, journey, Thu tiền, Tin nhanh) — read docs/messages.md for the full notes
- Owner uses this on an iPhone: big buttons, Vietnamese labels, calm colours (red = act now, amber = soon, green = done).
- Buttons inside `#live` call `window.MsgAct.*(this)` via onclick (iPhone Safari ignores delegated listeners on button text);
  `#live` is re-fetched every 30 s and swapped in place — new UI inside it must survive re-rendering (state in localStorage / DB).
- Opening WhatsApp / Zalo / SMS is NOT "sent": only the ✅ Đã gửi answer logs a journey step (`askSent`).
- Text and pictures are shared SEPARATELY (WhatsApp drops one when both go together); a share must run inside the tap
  (pictures prefetched as Files).
- Zalo cannot be pre-filled: copy synchronously (`copyNow`) before leaving the page.
- Grouping = by APARTMENT (`by_apt`, `.atabs`, floating 🏠 `#aptfab`), value order (price, nights) inside; default view = today
  (`days` only read with `pick=1`).
- Never bulk-send WhatsApp. Partner phone tail 035640799 is never a guest's number.
- After changes: `python -m pytest tests/test_flows.py tests/test_pages.py`.
