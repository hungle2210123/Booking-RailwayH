# Hotel Booking Management System - Project Memory

## 🏨 Project Overview
**Name:** Hotel Booking Management System  
**Type:** Flask web application for hotel management  
**Owner:** hungle2210123  
**Repository:** https://github.com/hungle2210123/Booking-RailwayH  
**Branch:** main  
**Status:** ✅ Production Ready - PostgreSQL + Mobile Optimized + Custom Date Analytics

## 🏗️ System Architecture

### **Core Application Structure**
```
hotel_flask_app_optimized/
├── app.py (Main Flask App - 2,847 lines, 62 routes)
├── core/
│   ├── models.py (SQLAlchemy Models - 6 database tables)
│   ├── logic_postgresql.py (Business Logic)
│   ├── database_service_postgresql.py (Database Service)
│   └── dashboard_routes.py (Dashboard Analytics)
├── templates/ (Frontend Templates)
├── static/ (CSS, JS, Images)
```

### **Database Schema (PostgreSQL)**
- **bookings** - Core booking data (25+ columns, soft delete)
- **accommodations** - Hotel/property information
- **monthly_reports** - Financial analytics
- **audit_logs** - System change tracking
- **revenue_calendar** - Per-night revenue distribution
- **booking_images** - AI-processed screenshots

### **Database Connections**
**Smart Auto-Detection Configuration:**
- **DATABASE_SOURCE=auto** (recommended for seamless development and deployment)
- **Local Testing:** Uses Railway data for complete testing experience
- **Railway Deployment:** Automatically uses Railway production database
- **Priority:** Railway DB > Local DB (ensures data completeness)

**Local PostgreSQL (Development Fallback):**
```
Connection: postgresql://postgres:locloc123@localhost:5432/hotel_booking
Host: localhost
Port: 5432
Database: hotel_booking
Username: postgres
Password: locloc123
```

**Railway PostgreSQL (Production & Testing):**
```
Connection: postgresql://postgres:VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi@mainline.proxy.rlwy.net:36647/railway
Host: mainline.proxy.rlwy.net
Port: 36647
Database: railway
Username: postgres
Password: VmyAveAhkGVOFlSiVBWgyIEAUbKAXEPi
```

### **Data Flow**
```
User Request → app.py → core/logic_postgresql.py → core/models.py → PostgreSQL
                     ↓
Templates (Jinja2) ← Dashboard Processing ← core/dashboard_routes.py
```

## 🔧 AI Assistant System - Debug Guide

### **Critical Files & Functions**
**Primary File:** `/templates/ai_assistant.html` (1838+ lines)  
**Backend API:** `/app.py` (Lines 6934-7033, 4345-4578)

### **Common Issues & Solutions**

#### **JavaScript Syntax Errors**
**Issue:** "Unexpected end of input" in onclick handlers  
**Solution:** Use data attributes instead of complex inline strings
```javascript
// ❌ NEVER USE:
onclick="deleteTemplate('${templateId}', ${JSON.stringify(templateLabel)})"

// ✅ ALWAYS USE:
onclick="deleteTemplate('${templateId}')" data-template-name="${templateLabel}"
```

#### **Template Management Functions**
- `showAddTemplateModal()` - Opens add template dialog
- `addNewTemplate()` - Validates and saves templates
- `useTemplate(templateId)` - Copies template content
- `deleteTemplate(templateId)` - Deletes with confirmation
- `copyResponseContent(button)` - Copies AI response

#### **Database Sequence Fix**
**Issue:** PostgreSQL sequence out of sync  
**Solution:** Auto-repair endpoint `/api/templates/fix_sequence`

#### **Custom Instructions Fix**
**Issue:** Field name mismatch (snake_case vs camelCase)  
**Solution:** Handle both formats in backend
```python
custom_instructions = ai_config.get('custom_instructions', '') or ai_config.get('customInstructions', '')
```

### **Emergency Debugging Checklist**
1. **Templates Not Loading:** Check `/api/templates` returns `success: true`
2. **JavaScript Errors:** Look for unescaped quotes in template strings
3. **Delete Button Issues:** Verify `deleteTemplate()` function defined
4. **Database Sequence:** Run sequence fix endpoint
5. **Custom Instructions:** Check field name mapping

## 🎯 Latest Fixes & Features

### **Commission Analytics System**
- Real-time tracking with multi-level prioritization
- Red highlighting for high-commission guests (>150,000đ)
- Pulse animations and color-coding
- Advanced sorting: commission level → urgency → amount

### **Payment Collection System**
**Database Enhancement:**
```sql
ALTER TABLE bookings ADD COLUMN collected_amount DECIMAL(12, 2) DEFAULT 0.00 NOT NULL;
```

**Features:**
- Track actual money collected vs booking amount
- Visual payment status indicators (green/red)
- Enhanced modal with payment breakdown
- Collector validation (LOC LE/THAO LE only)

### **AI Image Processing**
- Gemini AI screenshot analysis
- JSON parsing with array/object detection
- Enhanced error handling for malformed responses
- Support for Vietnamese and international names

### **Excel/CSV Import System**
**Date Parsing:** 100% success rate with multiple formats
- YYYY-MM-DD format
- Excel serial numbers
- Vietnamese date patterns
- 12 different fallback formats

**Column Mapping:**
```python
# Excel "Tổng thanh toán" → PostgreSQL room_amount
elif 'Tổng thanh toán' in header:
    col_map['room_amount'] = i
```

### **Production Deployment**
**Platform:** Railway.app  
**Database:** PostgreSQL (Railway managed)  
**Performance:** Sub-100ms response times

#### **🚨 CRITICAL: Railway Free Plan Deployment Fix**
**Problem:** `Error: '$PORT' is not a valid port number`  
**Root Cause:** Docker shell expansion issues on Railway free plan

**✅ WORKING SOLUTION:**
1. **Disable Dockerfile:** Rename to `Dockerfile.disabled`
2. **Use Nixpacks Builder:** Set `builder = "nixpacks"` in `railway.toml`
3. **Python Runner Script:** Create `run.py` that reads PORT from `os.environ` directly
4. **Update Procfile:** Use `web: python run.py`

**Key Files:**
- `railway.toml` - Set Nixpacks builder, remove startCommand
- `Procfile` - Simple `web: python run.py` 
- `run.py` - Handles PORT validation without shell expansion
- `Dockerfile.disabled` - Keep as backup, don't use for deployment

**Why This Works:** Eliminates all shell variable expansion dependencies that cause PORT parsing errors on Railway's free plan.

## 🔧 Technical Guidelines

### **Tool Configuration**
**🔧 USE Standard Claude Code Tools for all operations**
- **File Reading:** Use `Read` tool with absolute paths
- **Code Search:** Use `Grep` tool with pattern matching  
- **File Search:** Use `Glob` tool with pattern matching
- **Directory Listing:** Use `LS` tool with absolute paths
- **File Editing:** Use `Edit` or `MultiEdit` tools
- **Terminal Operations:** Use `Bash` tool

**✅ Benefits of Standard Tools:**
- Reliable and always available
- Consistent behavior across sessions
- No external dependencies
- Proven performance with this codebase

### **Project Structure Reference**
**📁 Key Files and Locations:**
- **Core Files:** app.py (2,847 lines), dashboard.html, models.py, ai_assistant.html
- **Key Functions:** highlightUpcomingCheckins() ~line 10024, switchCancellationTab() ~line 10089
- **Database Schema:** bookings table with guest_name column (NOT separate guests table)
- **API Endpoints:** /api/canceled_customers_management, /api/confirmed_cancellations
- **CANCELLATION CENTER:** Always visible, lines 670-720 in dashboard.html

**🔍 Quick Navigation References:**
- **Dashboard Controls:** Lines 410-450 in dashboard.html
- **JavaScript Functions:** Lines 10024+ in dashboard.html
- **Database Models:** QuickNote ~line 150 in models.py
- **Cancellation Logic:** cancellation_notifications.py functions ~line 226
- **Database Connections:** Local and Railway PostgreSQL (see connection strings above)

### **Debug Logging Protocol**
**Rule:** Remove debug logs when user moves to new topics
- Keep essential error handling
- Remove temporary debug prints
- Maintain production-ready code

### **Development Commands**
```bash
# Local development
cd /mnt/c/Users/T14/Desktop/hotel_flask_app/hotel_flask_app_optimized
python3 app.py

# Railway deployment (after free plan fixes)
python run.py  # Test the Railway runner script locally

# Test AI processing
# - Upload booking screenshot
# - Verify JSON parsing
# - Check data extraction

# Test data import
# - Import Excel/CSV files
# - Verify PostgreSQL saves
# - Check dashboard display
```

## 📁 Quick Reference

### **Key File Locations**
- **Main App:** `/app.py`
- **Business Logic:** `/core/logic_postgresql.py`
- **Database Models:** `/core/models.py`
- **AI Assistant:** `/templates/ai_assistant.html`
- **Dashboard:** `/templates/dashboard.html`
- **Database:** PostgreSQL tables (bookings, accommodations, etc.)

### **API Endpoints**
- **Templates:** `/api/templates` (GET/POST/DELETE)
- **AI Analysis:** `/api/ai_analysis`
- **Payment Collection:** `/api/collect_payment`
- **Data Import:** `/api/import_data`
- **Booking Management:** Various CRUD endpoints

### **Database Operations**
- **Sequence Fix:** `/api/templates/fix_sequence`
- **Collected Amount:** `collected_amount` column
- **Revenue Calculation:** Per-night distribution
- **Commission Tracking:** Real-time analytics

## 🆕 **Latest Updates (October 2026)**

### **🧹 Repo cleanup (Oct 2026)**
Only what the Dockerfile copies is kept at the root (app.py, run.py, gunicorn.conf.py, backup_routes.py,
production_booking_extractor.py, force_migration.py, migrate_add_*.py, core/, templates/, static/) + chrome_extension/,
deploy config, CLAUDE.md, README, BACKUP_BEFORE_CLEANUP/, instance/ (local sqlite fallback). ~80 old tracked files were
removed (git history has them); ~130 local-only files were MOVED to `C:\Users\T14\Desktop\hotel_flask_app\_luu_tru_2026-10-04\`.
Rule for future cleanups: a file not in the Dockerfile COPY list never reaches Railway; check pages before/after.

### **🧭 Guest journey messaging (`core/journey.py`, `static/js/journey.js`, `/journey`)**
/messages (tabs 🛬 Sắp đến / 🏨 Đang ở) shows per guest a strip of steps 👋 welcome · 🕐 confirm · 🛂 passport ·
🧳 luggage (optional) · 🔑 checkin · 💳 payment · ⭐ thanks (+ ➕ any Mẫu Câu template). Each step sends a message_templates
row chosen per apartment in `journey_map(step, apartment_id 0=default, template_id)` (seeded from DEFAULT_MAP by template
name), filled with {ten}{nhan}{tra}{phong}{can}, plus the template's pictures. Per-apartment steps require the guest to be
placed (sheet offers the apartment picker → /api/set_actual_apartment). 'confirm' also attaches the Booking screenshot.
Sent steps: `journey_log`; next step = `recommended_step()` by dates. Pictures are stored IN THE DB
(`template_images.image_data/image_mime`, upload from `/journey`, served `/api/journey/image/<id>`; the old
`/api/templates/image/<file>` falls back to the DB) — files on Railway's disk are wiped at every deploy (2 old images lost).
Send = wa.me text (targets the number) or share sheet with pictures + text (text also copied). Calendar card chip 🧭 Nhắn.
🔑 checkin has `images_only`: when the apartment's check-in template has pictures, the sheet shows only the guide
picture(s) (📤 Gửi ảnh / Mở chat WhatsApp·Zalo / Sao chép ảnh) — no text; without a picture the text is used. All 4 apartments have their guide (template_images 9, 10, 11, 17).
Guest cards show only the journey steps not in `journey_prefs['buttons'].hidden` (owner: passport + thanks hidden →
👋 🕐 🧳 🔑 💳 + 🚫 Hủy khách). General messages live in the floating ⚡ Tin nhanh button (`Journey.quick()`, above 🔄):
pinned favorites first (template `{id}` or whole group `{cat}`: 🛂 Passport, 🔁 Change, ❌ Xin hủy, 🚕 Taxi, ⭐ Cảm ơn),
then every group; optional guest picker fills {ten} and gives that guest's WhatsApp/Zalo/SMS links; without a guest
`/api/journey/compose` fills {ten} = "there". The Mẫu Câu page (ai_assistant.html) has "📤 Gửi chữ + ảnh" →
`Journey.quick(templateId)` (share sheet with text + pictures). Pin/unpin with 📌 in the list or at /journey. Tapping the apartment chip on a /messages card opens the apartment picker.
/messages keeps itself up to date: `#live` is re-fetched every 30 s and when the page becomes visible again (never
while a sheet/zoom is open) and swapped in place; new cards get a green border + "🆕 N khách mới". Each card shows
🔴 Chưa nhắn / ✅ Đã nhắn (+ last step and VN time, `J.last_contact`); filter Tất cả / Chưa nhắn / Đã nhắn (localStorage,
delegated clicks — the bar is inside `#live`). Tapping 🔴 records the manual mark `journey_log.step='contacted'`
(`J.MANUAL_KEY`, messaged outside the app); tapping a hand mark removes it.
No per-step ✓ anywhere (owner: useless) — sending is still logged quietly in journey_log, only for that line.
🚫 Hủy khách chip on every card = calendar "Báo hủy" (`/api/set_checkin_status` 'cancelling'); the card leaves, toast
"Hoàn tác" restores the previous checkin_status (card carries it as data-cs).

### **💬 "Nhắn khách" page (`/messages`, `templates/messages.html`)**
Mobile-first page: upcoming arrivals (checkin_date in [today, today+days]) that have a phone, each with
WhatsApp / SMS / Zalo / Copy buttons + a pre-filled bilingual greeting (tokens `{ten}{nhan}{tra}{phong}`).
The greeting lives in `message_templates` with category `AUTO_MSG_CATEGORY = '0 · Nhắn tự động'` (default seeded
by `_auto_msg_templates()`; first template = default, also used by the WhatsApp/Zalo chips in calendar_details),
edited/saved from /messages via the existing `/api/templates` endpoints → shared by every device.
calendar_details has a compact phone mode (`body.cd-compact`, default < 768px, toggle in the sticky `.cd-toolbar`):
cards show a JS-built `.cd-sum` line, tap opens `.cd-open`. Guests without a phone listed separately. Links built in JS; `_msg_phone_links()` normalises
phone → wa (intl digits), sms (+intl), zalo (VN 0-form). Nav: "💬 Nhắn Khách". Workflow = capture + reveal phones on
PC, message from the phone. WhatsApp bulk-blast from a personal account is intentionally NOT built (ban risk).

### **📷 Booking from a phone screenshot (/messages "Thêm đặt phòng từ ảnh app Booking")**
For bookings made while the owner is away from the PC: screenshots of the Booking (Pulse) app are OCR'd ON THE PHONE
with tesseract.js (CDN, 'vie+eng', dark screenshots inverted first — no API key; the server has no Gemini key and the
old Gemini image routes don't work), text → `POST /api/booking_from_photo/parse` (`parse_pulse_text()` in
core/booking_page_parser.py: name = header line above the property name ("Cozy Studio Hanoi…"), never the bottom tab bar "Tin nhắn Khác"; first two "d tháng m yyyy" dates, room under
"N phòng", "Tổng giá tiền đặt phòng", booking number after "Mã số đặt phòng" or a lone 10-digit number not starting
with 0) → editable form (missing fields red) → `POST /api/booking_from_photo/save` = `_ext_save_one` (same rules as
the extension). The booking number is usually in a second screenshot; when missing, a booking already on the web with the
same dates + price (±1,000đ, exactly one) is taken (`matched`).
No booking number at all (the Pulse screen often has none) → saved with a provisional id `TAM-yymmdd-XXXX`
(`_provisional_id`). `_ext_save_one` (extension list/detail/phone, photo import) switches it to the real number when
a new real booking has the same dates and price ±1,000đ or same first two name words (`_provisional_match` →
`_rename_booking`: bookings PK + booking_history, booking_screenshots, cancellation_actions, journey_log,
revenue_calendar; arrival_times (FK, no cascade on update) is copied, deleted and re-inserted). Name cleanup drops
icon tokens OCR'd at both ends ("4 ZHI Li 0" → "ZHI Li").
The extension's list page and detail page also find the provisional booking (row shows "mã tạm … → <real>", a
reservation cancelled on Booking cancels it instead of being skipped as 'skip_cancelled').

### **🤝 Partner bookings (`bookings.via_partner`)**
Reservations with the "Đối tác Booking.com" box were made through a partner company: the phone on the page is the
partner's (`+<guest country> 203 5640 799` — same last 9 digits for every guest). Extension detects the box and posts
`partner: true` → server sets `via_partner = TRUE` and never stores that number (`_ensure_partner_column()`).
Server also rejects a phone whose last 9 digits (`_phone_tail`) are on another guest, or that is a slice of the
booking number. Calendar shows "🤝 Đối tác"; /messages lists them separately. Extension "💬 Điền tin" types a chosen
template into Booking's own chat box (`POST /api/ext/auto_messages`; partner → `AUTO_MSG_PARTNER_NAME`); the owner
presses Gửi — never auto-sent.

### **📸 Booking.com screenshot for guests (`booking_screenshots` table)**
Extension captures the reservation box + room block (`chrome.tabs.captureVisibleTab`; needs `activeTab`, so it is
started from the toolbar popup, the right-click menu or Alt+Shift+S — an in-page button cannot capture). Saves
`full_img` (owner) and `guest_img` (commission / IATA / internal note / Booking notices / partner box painted white)
via `POST /api/ext/booking/screenshot`; served by `GET /api/booking_screenshot/<bid>?v=guest|full`.
`static/js/booking_card.js` (`HotelCard.open`) shows the guest version and shares it via the phone share sheet
(wa.me cannot carry images); falls back to a drawn confirmation card when no screenshot exists.
Auto mode is ALWAYS ON (owner decision, Oct 2026): `<all_urls>` is a required host permission so the capture can run
without activeTab — after the phone is saved (`auto-shot` message → `shoot(tab, true)`); checks the tab is still
active, restores scroll. No on/off toggle in the popup (only a status line).
Captures ONLY once the guest phone is on the page (`shotWhenVisible`: just revealed → always; already known / partner →
once per 10 min per tab; waits until the tab is visible) — not on page open (owner, Oct 2026). If the booking is not
on the web yet, `/api/ext/booking/phone` adds it from the same page (`_create_from_page`, status `created`).
Guest image also covers the owner's bracket note in the room title; `_room_label()` strips it from messages
(`keep_note=True` only on owner screens). Sending on phones = 2 steps: text via wa.me/Zalo/SMS, then 📷 (`HotelCard.quickShare`) shares the prefetched
image (`HotelCard.prefetch` on step 1) — share must run inside the tap, so it is fetched ahead.
Room names shown to guests go through `_room_label()` / `looks_like_room()` (a Booking notice was once stored as a room).

### **📞 Chrome extension — phone handling**
`POST /api/ext/booking/phone`: when the owner clicks Booking's own "Hiển thị số điện thoại", the extension reads the
number ONLY from the guest block (next to `@guest.booking.com` / the reveal button) and saves it to the booking;
duplicate-guard rejects a number already on another guest. Extension is **read-only on Booking** — it never auto-clicks
the reveal, never calls Booking APIs, never scrapes (deliberate: Booking gates the phone behind a human click; automating
that is circumvention + account-ban risk, so it was removed). Extension also imports the reservation list/detail
(new/changed/cancelled, multi-room ⚠️, new-listing 🆕). Current ext version: see `chrome_extension/manifest.json`.

### **🏠 Vacancy = placement-based (`core/occupancy.py`)**
Vacancy board (`/api/vacancy_preview`) + "Tình trạng căn hộ" bar (`/api/apartment_daily_summary`) only count a
booking against an apartment once it is placed there (`bookings.actual_apartment`). From its arrival day on it must
also be `checkin_status='confirmed'`. Everything else is returned as `pending` ("⏳ chờ") — never guessed from
listing name / room_id (listing names are sold across apartments; TN bookings carry Hội Vũ room_ids).
`over` = placed guests beyond the apartment's active room count → "VƯỢT" warning.
`/api/apartment_placement_check` warns before placing a guest into a full apartment.

### **🛏️ 2-bedroom bookings (`core/two_bedroom.py`)**
`bookings.two_bedroom` BOOLEAN: NULL = auto-detect from listing ("2 PN", "2 phòng ngủ", "Two-Bedroom"; "2 Giường" is
NOT 2PN), TRUE/FALSE = manual (`/api/set_two_bedroom`). Shown as 🛏️ 2PN toggle on cards, a check-out watch panel in
calendar_details (next 3 days) and "🛏️ N trả 2PN" badges in the month calendar.

### **🗑️ Delete apartment**
`DELETE /api/apartments/<id>` (body `move_bookings_to`: id or null) + `/api/apartments/<id>/delete_check`.
`bookings.apartment_id` FK is RESTRICT → bookings are moved first; rooms cascade.

### **📊 Dashboard (`core/revenue.py` + `/api/dashboard/overview`)**
`/dashboard` is a thin page; every number comes from `build_overview()` with ONE rule set: revenue is recognised
PER NIGHT (booking value ÷ nights), so the daily calendar sums to the month total. Excludes cancelled/deleted/
`cancelling`/`no_show`; paid → actual collected amount; statuses paid / due / expected / review (review = > 2 days
past arrival, unconfirmed, unpaid → not counted). Stats: occupancy, ADR, RevPAR (capacity = active rooms that existed
that day; shown "—" when nights sold exceed rooms on record). No debt lists on the dashboard (calendar handles them).
Expense tools live at `/expenses` (`templates/expenses.html`).
Removed unauthenticated debug routes incl. `/api/clear_imported_data` (wiped all bookings).
Commission is intentionally NOT shown on the dashboard (owner decision: most direct-pay guests cancel on Booking).

### **📋 Message template categories**
Renamed to numbered guest-journey categories "1 · Chào đón…" → "11 · Cảm ơn…" (sorted numerically in the UI).
Old categories backed up in `BACKUP_BEFORE_CLEANUP/message_template_categories_2026-09-27.json`.

## 🆕 **Latest Updates (May–June 2026)**

### **🐛 Calendar Details Date-Type Bug Fix**
**Status:** ✅ FIXED (commit 37916fa)

**Problem:** Clicking any date in `/calendar/` showed:
> `Error loading calendar details: unsupported operand type(s) for -: 'Timestamp' and 'datetime.date'`

**Root Cause (2 places):**
1. `_daily_rev_for()` in `calendar_details` — `(co - ci).days` crashed when one date was `pd.Timestamp` and the other `datetime.date` (mixed sources: `_extra2` vs `df_local`)
2. Template `calendar_details.html` lines 1205, 1277, 1376, 1377, 1570 — same subtraction in Jinja

**Fix:** Added normalization step in `app.py:calendar_details()` that converts ALL date fields in `check_in`, `check_out`, `staying_over` dicts to `datetime.date` BEFORE any calculation or template rendering:
```python
def _normalize_dates(guest_list):
    for g in guest_list:
        for _f in ['Check-in Date', 'Check-out Date']:
            v = g.get(_f)
            if v is not None:
                try: g[_f] = pd.Timestamp(v).date() if pd.notna(v) else None
                except Exception: pass
_normalize_dates(check_in); _normalize_dates(check_out); _normalize_dates(staying_over)
```
Also wrapped revenue calc with `pd.Timestamp(co) - pd.Timestamp(ci)` as safety net.

---

### **💰 Per-Night Price Display in Calendar Details**
**Status:** ✅ PRODUCTION READY

**Added to all 3 sections** (Check-in, Đang Ở, Check-out) in `calendar_details.html`:
```html
{% if total_nights > 1 %}
<div class="detail-row" style="opacity:0.75;">
    <span style="font-size:0.75rem;">💰 Giá/đêm</span>
    <span style="color:#1976d2;">{{ "{:,.0f}".format(per_night_rate|int) }}đ/đêm</span>
</div>
{% endif %}
```

---

### **📧 Vacancy e-mails — REMOVED (Oct 2026)**
Owner dropped the "Phòng Trống" settings page, its e-mails (`send_test_email.py`) and the Mobile Check-in page
(`/mobile_checkin`). The vacancy board on the calendar (`/api/vacancy_preview`) stays.

**Quan trọng — `actual_apartment` column:**
- Được thêm auto vào bảng bookings: `ALTER TABLE bookings ADD COLUMN IF NOT EXISTS actual_apartment VARCHAR(100)`
- User gán qua `/api/set_actual_apartment` từ calendar details page
- Lưu dạng INTEGER (apartment_id): `1` = 118HB, `2` = 18HB, `506` = 25HV
- Đây là nguồn chính xác nhất cho room assignment

---

### **🗄️ Database — Room/Apartment Structure**
```
apartments:
  apt_id=1   → 118 Hang Bac Hostel  (4 rooms: ids 1,2,3,1793)
  apt_id=2   → 18 Hang Be           (2 rooms: ids 4,5)
  apt_id=506 → 25 Hoi Vu            (4 rooms: ids 1244-1247)

rooms:
  1=118 hang bac | 2=kitchen | 3=night market | 1793=ban cong  → apt1
  4=hang be 101  | 5=hang be 102                               → apt2
  1244=101-2PN   | 1245=102  | 1246=103 | 1247=104             → apt506

⚠️ QUAN TRỌNG: room_id=1 là DEFAULT PLACEHOLDER cho nhiều booking
   Không dùng room_id=1 để xác định apartment — dùng actual_apartment trước!
```

**accommodation_name inconsistency:** 30+ kiểu viết khác nhau trong DB
(ví dụ: "118 Hang Bac Hostel", "Ban Cong Hang Bac", "ban công", "Sofa Hàng Bạc"...)
→ Không dùng LIKE query trực tiếp — dùng `actual_apartment` (xem core/occupancy.py)

---

## 🆕 **Latest Updates (July 2025)**

### **🎯 Custom Date Picker for Collector Analytics**
**Status:** ✅ **PRODUCTION READY**

**Location:** Dashboard → "Phân bổ theo Người thu (Chi tiết)" section

**Features Added:**
- ✅ **Button-based interface** with 3 modes: Month, Custom, All-time
- ✅ **Custom date range selector** (e.g., June 15-31 selection)
- ✅ **Real-time chart updates** when dates are selected
- ✅ **Visual period indicators** showing current selection
- ✅ **Data validation** for LOC LE & THAO LE only

**Technical Implementation:**
- **Function:** `setCollectorDateType()` - Priority loaded in dashboard.html
- **API:** `/api/collector_chart_data` - Enhanced date range handling
- **Database:** PostgreSQL/SQLite compatibility with date filtering
- **UI:** Green alert box with prominent date inputs

**Usage Example:**
1. Click "📅 Tùy chọn ngày" button
2. Set custom dates (June 15 → June 31)
3. Chart automatically updates with filtered collector data

### **🗑️ Enhanced Delete Functionality**
**Status:** ✅ **PRODUCTION READY**

**1. Message Template Management**
- **Location:** AI Assistant → "Quản lý Mẫu Tin Nhắn" tab
- **Features:** Individual delete buttons with confirmation
- **API:** `DELETE /api/templates/<template_id>`
- **UX:** Toast notifications, smooth animations, loading states

**2. Individual Expense Deletion**
- **Location:** Dashboard → "Phân Loại Chi Phí: Cá Nhân & Công Việc" modal
- **Features:** Delete individual expenses (not bulk deletion)
- **API:** `DELETE /api/expenses/<expense_id>`
- **Safety:** Detailed confirmation with expense description and date
- **UX:** Immediate row removal, auto-refresh totals

### **📱 Mobile Responsiveness Overhaul**
**Status:** ✅ **PRODUCTION READY**

**Problem Solved:** Column overlap on Railway mobile deployment

**CSS Enhancements:**
- **Mobile Breakpoints:** 576px, 768px, 992px responsive design
- **Table Fixes:** Horizontal scroll, fixed column widths, touch scrolling
- **Classes Added:** `.booking-management-table`, `.compact-cancellation-table`
- **Features:** Scroll indicators, optimized fonts, stacked buttons

**Tables Enhanced:**
1. **Guest booking table** - No more column overlap
2. **Cancellation alerts table** - Touch-friendly scrolling
3. **Overdue guests table** - Proper mobile layout

### **🧹 Dashboard Controls Cleanup**
**Status:** ✅ **PRODUCTION READY**

**Removed Unused Tools:**
- ❌ Refresh Dashboard, Import CSV, Crawl Data
- ❌ Diagnostic tools (Check Data, Deep Check, Debug Import)
- ❌ Database management tools (Sync, Switch, Column management)

**Kept Essential Tools:**
- ✅ **Duplicates Management** with count indicator
- ✅ **All Bookings** navigation link

**Benefits:** Cleaner interface, better mobile experience, reduced maintenance

### **⚠️ Critical Production Notes**

**Database Configuration:**
- `DATABASE_SOURCE=auto` in railway.toml for automatic detection
- PostgreSQL/SQLite compatibility maintained for all queries
- Date parsing with comprehensive error handling

**Mobile Performance:**
- Tables now properly responsive on all devices
- Touch scrolling optimized for iOS/Android
- Railway mobile deployment tested and working

**Function Loading:**
- `setCollectorDateType` moved to priority load section
- All JavaScript functions globally accessible
- Enhanced error handling and debugging

**Testing Files Created:**
- `test_delete_functionality.js` - Delete function testing
- `mobile_responsive_test.html` - Mobile responsiveness testing
- `test_custom_dates_final.js` - Custom date picker testing

### **🚀 Deployment Status**
- **Last Deploy:** Commit 691bf70 - Enhanced custom date picker
- **Railway Status:** ✅ Production ready with mobile optimization
- **Database:** PostgreSQL with auto-detection working
- **Mobile:** ✅ Column overlap fixed, touch-friendly interface

---

**📊 System is fully optimized for production use with enhanced mobile experience and streamlined interface.**