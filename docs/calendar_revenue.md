# Calendar, apartments, vacancy, dashboard & revenue

Detail notes moved out of CLAUDE.md (Oct 25) — read when working on this area. Find code with docs/CODEMAP.md.

### **🏠 Vacancy = placement-based (`core/occupancy.py`)**
Vacancy board (`/api/vacancy_preview`) + "Tình trạng căn hộ" bar (`/api/apartment_daily_summary`) only count a
booking against an apartment once it is placed there (`bookings.actual_apartment`). From its arrival day on it must
also be `checkin_status='confirmed'`. Everything else is returned as `pending` ("⏳ chờ") — never guessed from
listing name / room_id (listing names are sold across apartments; TN bookings carry Hội Vũ room_ids).
`over` = placed guests beyond the apartment's active room count → "VƯỢT" warning.
`/api/apartment_placement_check` warns before placing a guest into a full apartment.

### **🎨 Calm colours (owner, Oct 2026) — /messages + calendar_details**
Colour only for what needs attention: red = act now (⚡ Chưa thu, 🔴 Chưa nhắn, Báo hủy, VƯỢT), amber = soon / to do
(Trả hôm nay / ngày mai, chưa xếp căn, chưa có số, ⭐ VIP), green = done (small: Xác nhận đến, 💬 Đã nhắn); the
apartment colour only on the card's left edge + its name chip. Everything else black / grey / white. Calendar: one
override layer `<style id="calm-colours">` at the end of calendar_details.html (`body …` + !important); /messages: the
"Calm colours" block at the end of its <style>. /messages cards show "💰 total · N đêm · price/đêm".

### **🔄 /messages ⇄ calendar_details sync (arrival status)**
The server is the only source: calendar_details no longer pushes this browser's localStorage statuses to the DB on
load (old "STEP 0" brought back statuses cleared on another device / "Hoàn tác"). `cdSyncFromDB()` applies the DB
status (also a cleared one) on load, every 30 s and when the tab is shown again; a status tapped here is not
overwritten for 10 s (`window._cdRecent`). `/api/get_checkin_statuses` also returns `contact` (journey_log): the
calendar's "📞 Chưa liên hệ" button shows "💬 Đã nhắn · step · time" or "📵 Không liên lạc được · time".
With no arrival status that button is a toggle (`cdToggleContacted`): "📞 Chưa liên hệ" ⇄ "✅ Đã liên hệ · time" = the same
manual mark as /messages (journey_log 'contacted', label '✋ Đã liên hệ'); with confirmed / cancelling it still clears the
status (old behaviour). A guest already messaged from /messages just gets a toast.
Placements sync too: `/api/get_checkin_statuses` returns `apts` (actual_apartment) for every card on the page; the sync
moves a card placed / moved on /messages or another device (`cdApplyAptUI` = the picker's look, shared with `setApt`,
then data-apt + the per-apartment board/groups).
/messages shows "🙋 Khách đã xác nhận đến" for checkin_status 'confirmed' (counts as contacted). Owner reversed this
(Oct 15): every card has a ✅ Xác nhận đến chip (`MsgAct.confirm`, toggles to "🙋 Đã xác nhận · bỏ") = the calendar's
status via `/api/set_checkin_status` ('confirmed' / ''), so the calendar, vacancy board and apartment tiles follow.

### **🏠 Per-apartment view on calendar_details (`#aptOverview`)**
Above the 3 columns: one tile per apartment (colour = `apartments_list[i].color`, same as the apartment picker) with
🛬 Đến / 🏨 Đang ở / 🧳 Trả counted from the cards (`data-apt` = actual_apartment; 'cancelling' cards skipped), plus
tonight's free rooms from `/api/vacancy_preview` (same numbers as the Phòng trống board) and "⏳ N chờ xác nhận";
a "⏳ Chưa xếp căn" tile. Tap a tile = show only that apartment's cards (`.apt-filtered-out`). Cards get the apartment
colour (8px left edge, light tint, coloured watermark; unplaced = grey dashed edge); payment strip on top and the 2PN
purple edge are untouched. Updates on placement (`setApt` sets `data-apt`) and on status changes (MutationObserver).
Each column (Đến / Đang ở / Trả) is grouped by apartment (apartments' order, unplaced last) with a header
"🏠 name · N" (`.apt-group-h`); `cdSortByApt(id)` runs after the old sorts (groupSection: confirmed → none →
cancelling; staying: soonest checkout) so their order is kept inside each apartment group.
Guests marked 📵 on /messages are dimmed (`.cd-unreach`: opacity .42 + grey, full on hover/tap) and go last in their
apartment group; on /messages the 📵 group cards are dimmed the same way.
A 📵 mark only holds while nothing newer happened (`J.unreachable_at`): not once the guest is confirmed (✅ Xác nhận
đến also deletes the mark in `set_checkin_status`), not when a message was sent after it; confirmed cards are never dimmed.

### **🛏️ 2-bedroom bookings (`core/two_bedroom.py`)**
`bookings.two_bedroom` BOOLEAN: NULL = auto-detect from listing ("2 PN", "2 phòng ngủ", "Two-Bedroom", and since Oct 25
also "2 Giường" — owner: priced like 2PN, watch the same; "Giường đôi / cỡ King" are not), TRUE/FALSE = manual
(`/api/set_two_bedroom`). Shown as 🛏️ 2PN toggle on cards, a check-out watch panel in calendar_details (next 3 days)
and "🛏️ N trả 2PN" badges in the month calendar.
Phòng trống board (`/api/vacancy_preview` → `two_br_days` from `core.two_bedroom.watch_days`, 14 days; per day card
`two_br` = counts): purple "🛏️ 2PN: N trả · N đến (N đang ở)" line on each day card (calendar_details sidebar + month
calendar board) and, under the cards, the purple "🛏️ PHÒNG 2 NGỦ — 14 NGÀY TỚI" list: each day with a 2PN check-out
or arrival, names + nights + apartment (red "chưa xếp căn" when not placed); tap = that day's page.

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
Oct 18: commission is no longer tracked ANYWHERE — hidden on calendar_details (card "HH" badge, "Sau trừ hoa hồng",
breakdown columns, edit field), the month calendar, /bookings (column + modals) and edit_booking; the column and old
values stay in the DB and forms keep the stored value. /api/collect_payment no longer resets commission to 0 when the
caller sends none (the calendar's Thu tiền never sent it).
Revenue = money collected for the ROOM: `collected − taxi_amount` (`room_paid`); a paid booking whose room money differs
from the room price by > 1,000đ is flagged on the dashboard day list ("⚠️ giá phòng X/đêm"). Double "Thu tiền" is
refused: /api/collect_payment (409 `duplicate`, unless `allow_duplicate`) and /api/pay/collect (unless `force`, sent
by the sheet after its over-total confirm) when the booking is already paid and the same full amount comes again.
ONE day figure everywhere (owner, Oct 23: same day showed 12.5M dashboard / 14.2M month calendar / 16.4M day page):
`core.revenue.day_figures(bookings, dates)` (dashboard rules: per night, paid → room money, Báo hủy / no-show out,
unconfirmed arrivals = pending, future = expected, guests leaving that day NOT counted) now feeds the month calendar cell
(+ "⏳ +Xđ · N chờ xác nhận" line) and the calendar_details headline / breakdown / `rev_pn` (per-night data-rev for the
page's JS recalculation; `stay_co_rev` = total minus confirmed arrivals). Old `get_daily_revenue_by_stay` only as fallback.
5 bookings counted exactly twice (Philippe 19.19M → 9.59M, Chiara Gelmi, Jorge Nava, Hong Tran, AIR8n) were corrected
(booking_history 'fix_double_collect', backup BACKUP_BEFORE_CLEANUP/double_collected_fix_2026-10-18.json).

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

