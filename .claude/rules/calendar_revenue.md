---
paths:
  - "app_parts/p05_*.py"
  - "app_parts/p11_*.py"
  - "core/revenue.py"
  - "core/occupancy.py"
  - "core/two_bedroom.py"
  - "templates/calendar.html"
  - "templates/calendar_details.html"
  - "templates/dashboard.html"
---
# Calendar, vacancy, dashboard & revenue — read docs/calendar_revenue.md for the full notes
- ONE revenue rule set: `core/revenue.py` (`classify`, `night_kind`, `build_overview`, `day_figures`). Dashboard, month calendar
  cell and calendar_details headline must show the same number per day — never add another calculation.
  Per night (value ÷ nights); paid → room money (`collected − taxi_amount`); Báo hủy / no-show out; unconfirmed arrivals =
  "⏳ chờ" (pending, not counted); future = expected; guests leaving that day are NOT counted.
- Apartment = `bookings.actual_apartment` (id as text) only — never guess from listing name or room_id (room_id 1 = placeholder).
  Ids: 1 = 118 Hang Bac · 2 = 18 Hang Be · 506 = 25 Hoi Vu · 877 = 19 Tho Nhuom.
- Vacancy counts a booking only once placed (and confirmed from its arrival day).
- calendar_details reads arrival statuses from the DB (`cdSyncFromDB`), never pushes localStorage to the DB.
- Commission is not tracked anywhere any more.
- After changes: `python -m pytest tests/test_revenue.py tests/test_pages.py`.
