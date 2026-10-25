# Hotel Pro — homestay booking & guest-messaging app (Flask + PostgreSQL on Railway)

Owner: Vietnamese homestay owner (4 apartments in Hanoi Old Quarter), works mostly from an **iPhone**, not a developer.
Answer in Vietnamese, plain words. Repo hungle2210123/Booking-RailwayH, branch `main`, live at
https://web-production-8f671.up.railway.app — **push straight to main** ("git push luôn"); Railway deploys in ~3 min.

## Find code fast (read this first — keeps context small)
- **`docs/CODEMAP.md`** = every route / function / page-script with `file:line`. `grep` it first, then read only that range.
  Regenerate after adding / moving code: `python tools/codemap.py` (commit it).
- Python: `app.py` (≈600 lines: imports, config, DB setup, shared helpers) then **`app_parts/pNN_*.py`**, executed in order
  INSIDE app.py's namespace (one shared global namespace — same as one big file; endpoint names unchanged).
  New code goes in the part of its feature. A new part file must keep the `pNN_` prefix (load order) — Dockerfile copies `app_parts/`.
  p01 health, cancellations, auto-sync, debug · p02 page shells, dashboard API, **Chrome extension** import/save, photo import ·
  p03 **/messages**, phone, AI reply, screenshots, journey, Thu tiền, /tin-nhanh · p04 /bookings, add/edit, expenses ·
  p05 **calendar** month + calendar_details, vacancy, placement · p06 mobile payment, booking API, image/text extraction ·
  p07 /ai_assistant page, homestay, quick notes, arrival times · p08 collect payment, history, imports, check-in status ·
  p09 message templates API + images · p10 apartments/rooms · p11 analytics · p12 sync/crawl/duplicates · p13 translate,
  railway misc · p14 electricity.
- `core/`: `journey.py` (messaging steps), `revenue.py` (ALL revenue numbers), `occupancy.py` (vacancy), `booking_page_parser.py`
  (extension + screenshot parsing), `models.py`, `two_bedroom.py`. Front-end: `templates/*.html` (big, inline JS),
  `static/js/journey.js` (send sheet), `static/js/booking_card.js`, `chrome_extension/` (content.js, background.js).
- Feature notes (read only the one you need): **`docs/messages.md`** (journey, Zalo/VN, Thu tiền, /messages page, photo
  import, Tin nhanh, Mẫu Câu) · **`docs/extension.md`** (partner bookings, AI reply, screenshots, cancellations, multi-room,
  phone) · **`docs/calendar_revenue.md`** (vacancy, calm colours, sync, per-apartment view, 2PN, dashboard/revenue, rooms) ·
  `docs/history.md` (pre-Oct-2026 notes). Full old CLAUDE.md (local only, git-ignored): `BACKUP_BEFORE_CLEANUP/CLAUDE_full_2026-10-25.md`.
  When a feature changes, update its docs/*.md section (not this file) — keep this file short.

## Verify before pushing
- Smoke test: `python tools/smoke.py` (24 main pages / APIs on the real DB, prints ALL OK).
- Test on real data with throwaway rows (booking ids like `9990001234`, template `ZZ TEST …`) and delete them after.
- Jinja templates are cached: restart the preview server (`.claude/launch.json` "flask-app") after template edits.
- UI changes: check at 375px (owner's iPhone) with the browser preview. Never leave test data or temp files in `static/`.
- Writing Python edit scripts: put them in the scratchpad and run them (heredocs with quotes break in this shell).

## Data facts
- PostgreSQL on Railway (production, used for local testing too — `DATABASE_SOURCE=auto`):
  the URL is `RAILWAY_DATABASE_URL` in the local `.env` (git-ignored — never commit or paste it; Railway's own `DATABASE_URL`
  is set in its Variables). The old password was in git history → owner should rotate it (Railway security notice Oct 22).
- Apartments: 1 = 118 Hang Bac Hostel · 2 = 18 Hang Be · 506 = 25 Hoi Vu · 877 = 19 Tho Nhuom. Placement = `bookings.actual_apartment`
  (apartment id as text) — the only reliable apartment link; listing names / `room_id` are NOT (room_id 1 is a placeholder).
- Booking state: `booking_status` (cancelled/deleted = gone) + `checkin_status` ('confirmed' / 'cancelling' = Báo hủy / 'no_show').
  Money: `room_amount`, `collected_amount`, `collector` (LOC LE / THAO LE), `taxi_amount`. Commission is no longer used anywhere.
- Pictures for guests are stored IN THE DB (`template_images.image_data`, `booking_screenshots`) — Railway's disk is wiped on deploy.
- Revenue: one rule set in `core/revenue.py` (`build_overview`, `day_figures`) used by dashboard, month calendar and day page.

## Hard rules (owner decisions + safety)
- Never log in to Booking.com or type the owner's passwords. The extension is **read-only on Booking**: never auto-click
  "Hiển thị số điện thoại", never call Booking APIs, never scrape. It only TYPES into Booking's chat box; the owner presses Gửi.
- No bulk WhatsApp sending from a personal account. Partner-company phone numbers (tail `035640799`) are never a guest's phone.
- The owner creates / rotates API keys and passwords themselves (Gemini key is `GOOGLE_API_KEY` on Railway). Never paste secrets into chat.
- Cancelled on Booking → `checkin_status='cancelling'` (Báo hủy, undoable), never hide a booking for good.
- UI: calm colours (black/grey/white; red = act now, amber = soon, green = done), phone-first, Vietnamese labels, few big buttons.
- Owner likes always-on automation (no on/off toggles) and wants work pushed directly; explain results simply in Vietnamese.
- Deployment: Dockerfile build (`python3 -u run.py` → gunicorn `app:app`); it COPYs app.py, run.py, core/, app_parts/, templates/,
  static/ … — a new top-level file/folder must be added to the Dockerfile or it never reaches Railway.
