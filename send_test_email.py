"""
Gửi email thử nghiệm — Báo cáo phòng trống Hotel Pro
Chạy: python send_test_email.py
"""
import smtplib, os, sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta, date

# ── Load .env ────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # nếu chưa cài python-dotenv

SMTP_EMAIL     = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD  = os.getenv("SMTP_APP_PASSWORD", "")
NOTIFY_EMAILS  = os.getenv("NOTIFY_EMAILS", "ngotri.2210@gmail.com")

# ── Kiểm tra credentials ─────────────────────────────────────────────────────
if not SMTP_EMAIL or not SMTP_PASSWORD:
    print("❌ Chưa có SMTP_EMAIL hoặc SMTP_APP_PASSWORD trong .env")
    print()
    print("👉 Cách tạo Gmail App Password (1 phút):")
    print("   1. Vào: https://myaccount.google.com/apppasswords")
    print("   2. Đăng nhập tài khoản: ngotri.2210@gmail.com")
    print("   3. App name: gõ 'Hotel Pro' → nhấn Create")
    print("   4. Copy mã 16 ký tự (ví dụ: abcd efgh ijkl mnop)")
    print("   5. Dán vào .env: SMTP_APP_PASSWORD=abcdefghijklmnop")
    print("   6. Chạy lại: python send_test_email.py")
    print()
    print("⚠️  Lưu ý: Tài khoản phải bật 2-Step Verification trước")
    sys.exit(1)

# ── Room_id → apartment_id mapping (từ DB rooms table) ───────────────────────
ROOM_APT = {4:2, 5:2, 1244:506, 1245:506, 1246:506, 1247:506,
            1793:1, 2:1, 3:1}
# Keywords phân loại theo accommodation_name (fallback)
BE_KW = ['hang be','hàng bè','hàng be','hang bè','be 101','be 102','2 pn hàng','2 pn hang']
HV_KW = ['hoi vu','hội vũ','hội vu','hoi vũ','phong 2 giuong',
         'phòng 2 giường','giuong hoi','101 - 2 pn','25 hv','studio hoi']

def _classify_apt(actual_apt, room_id, acc_name):
    """Trả về apartment_id: 1=118HB, 2=18HB, 506=25HV"""
    # 1. actual_apartment (do user gán thủ công) — ưu tiên cao nhất
    if actual_apt and str(actual_apt).isdigit():
        return int(actual_apt)
    # 2. room_id rõ ràng (không phải room 1 — dùng làm default)
    if room_id and room_id in ROOM_APT:
        return ROOM_APT[room_id]
    # 3. accommodation_name matching
    n = (acc_name or '').lower()
    for k in BE_KW:
        if k in n: return 2
    for k in HV_KW:
        if k in n: return 506
    return 1  # default: 118 HB

# ── Lấy dữ liệu phòng trống THẬT từ DB ───────────────────────────────────────
def get_vacancy_data():
    """
    Dùng lại hàm get_overall_calendar_day_info() của app để đảm bảo
    kết quả khớp 100% với lịch trên Railway.
    """
    """
    Tính phòng trống chính xác dùng actual_apartment (ưu tiên) → room_id → acc_name.
    Khớp 100% với calendar trên Railway.
    """
    import psycopg2
    today   = date.today()
    vn_days = ["Chủ Nhật","Thứ Hai","Thứ Ba","Thứ Tư","Thứ Năm","Thứ Sáu","Thứ Bảy"]

    db_url = os.getenv("RAILWAY_DATABASE_URL") or os.getenv("LOCAL_DATABASE_URL")
    conn   = psycopg2.connect(db_url)
    cur    = conn.cursor()

    # Màu chấm theo thứ tự apt
    DOT_COLORS = ["#3949ab","#2e7d32","#6a1b9a","#e65100","#00838f","#c62828"]

    # Load apartments + rooms ĐỘNG từ DB — không hardcode
    cur.execute("""
        SELECT a.apartment_id, a.apartment_name,
               r.room_id, r.room_name
        FROM apartments a
        JOIN rooms r ON r.apartment_id=a.apartment_id AND r.is_active=true
        WHERE a.is_active=true
        ORDER BY a.apartment_id, r.room_id
    """)
    apt_rows = cur.fetchall()

    # Build APT_CFG động
    from collections import OrderedDict
    apt_map = OrderedDict()
    for apt_id, apt_name, room_id, room_name in apt_rows:
        if apt_id not in apt_map:
            idx = len(apt_map)
            apt_map[apt_id] = {
                "id"   : apt_id,
                "name" : apt_name,
                "dot"  : DOT_COLORS[idx % len(DOT_COLORS)],
                "rooms": [],  # list of {room_id, room_name}
            }
        apt_map[apt_id]["rooms"].append({"id": room_id, "name": room_name})

    APT_CFG  = list(apt_map.values())
    apt_by_id = apt_map
    # capacity đã có từ len(rooms) ở trên, không cần query lại

    days = []
    for i in range(4):
        d     = today + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")

        # Query tất cả bookings active ngày d, lấy cả actual_apartment
        cur.execute("""
            SELECT room_id, accommodation_name, actual_apartment
            FROM bookings
            WHERE checkin_date  <= %s
              AND checkout_date  > %s
              AND COALESCE(booking_status,'') NOT IN ('cancelled','deleted')
              AND COALESCE(checkin_status,'') != 'cancelling'
        """, (d_str, d_str))
        rows = cur.fetchall()

        # Đếm bookings theo apartment
        from collections import Counter
        apt_count = Counter()
        for room_id, acc, actual_apt in rows:
            apt_id = _classify_apt(actual_apt, room_id, acc)
            if apt_id in apt_by_id:
                apt_count[apt_id] += 1

        # Build apt_data dùng tên từ DB
        apt_data   = []
        total_free = 0
        for apt in APT_CFG:
            cap  = len(apt["rooms"])
            occ  = min(apt_count.get(apt["id"], 0), cap)
            free = cap - occ
            total_free += free
            apt_data.append({
                "name"      : apt["name"],   # tên đúng từ DB
                "dot"       : apt["dot"],
                "free"      : free,
                "total"     : cap,
                "rooms"     : apt["rooms"],  # danh sách loại phòng
                "free_rooms": free,          # số phòng còn trống
            })

        days.append({
            "date"      : d,
            "label"     : ["Hôm nay","Ngày mai","+2 ngày","+3 ngày"][i],
            "weekday"   : vn_days[(d.weekday() + 1) % 7],
            "total_free": total_free,
            "apts"      : apt_data,
        })

    cur.close(); conn.close()
    return days

# ── Build HTML email ──────────────────────────────────────────────────────────
def build_html(days, is_alert=False, alert_day=None):
    today_str = datetime.now().strftime("%d/%m/%Y")
    base_url  = "https://web-production-8f671.up.railway.app"
    THRESHOLD = int(os.getenv("ALERT_THRESHOLD", 3))

    if is_alert and alert_day:
        subject = f"⚡ [CẢNH BÁO] {alert_day['date'].strftime('%d/%m')} còn {alert_day['total_free']} phòng trống!"
        hero_bg = "#e65100"
        hero_title = f"⚡ {alert_day['total_free']} Phòng Trống {alert_day['label']}!"
        hero_sub = "Cảnh báo sớm · Nhắc lại lần 2 vào 20:00"
    else:
        subject = f"🏨 [{today_str}] Phòng trống 4 ngày tới — Hotel Pro"
        hero_bg = "#1e2a5e"
        hero_title = "Phòng Trống 4 Ngày Tới"
        hero_sub = f"Báo cáo tự động · {today_str} · 07:00"

    # Build day cards
    day_cards = ""
    for day in days:
        d      = day["date"]
        is_hot = day["total_free"] > THRESHOLD
        full   = day["total_free"] == 0

        if full:
            border = "#c62828"; bar_color = "#c62828"
            hd_bg  = "#fce4ec"; count_color = "#c62828"
            count_text = "Hết phòng"
        elif is_hot:
            border = "#43a047"; bar_color = "#2e7d32"
            hd_bg  = "#e8f5e9"; count_color = "#1b5e20"
            count_text = f"{day['total_free']} phòng trống"
        else:
            border = "#e0e0e0"; bar_color = "#3949ab"
            hd_bg  = "#f8f8f8"; count_color = "#2e7d32" if day['total_free'] > 0 else "#bbb"
            count_text = f"{day['total_free']} phòng trống" if day['total_free'] > 0 else "Hết phòng"

        hot_badge = (
            '<span style="background:#2e7d32;color:#fff;padding:2px 10px;'
            'border-radius:10px;font-size:11px;font-weight:700;margin-left:8px;">'
            '🔥 NHIỀU PHÒNG TRỐNG</span>'
        ) if is_hot else ""

        # Apt items — hiện tên căn hộ từ DB + từng loại phòng
        apt_items = ""
        for i, apt in enumerate(day["apts"]):
            sep = '<td style="width:1px;background:#eee;padding:0 10px;"></td>' if i > 0 else ""
            free = apt["free"]
            total = apt["total"]
            num_color = "#1b5e20" if is_hot and free > 0 else ("#bbb" if free == 0 else "#2e7d32")

            # Hiện từng loại phòng dưới tên căn hộ
            rooms_html = ""
            if apt.get("rooms"):
                # Chỉ hiện tên phòng, không biết phòng nào trống cụ thể nên hiện list
                room_names = [r["name"].title() for r in apt["rooms"]]
                rooms_html = '<div style="font-size:9px;color:#aaa;margin-top:3px;line-height:1.5;">'
                rooms_html += "<br>".join(room_names)
                rooms_html += '</div>'

            apt_items += f"""
            {sep}
            <td style="padding:8px 12px;text-align:center;vertical-align:top;">
              <div style="display:inline-block;width:8px;height:8px;border-radius:50%;
                          background:{apt['dot']};margin-bottom:3px;"></div>
              <div style="font-size:11px;font-weight:700;color:#333;">{apt['name']}</div>
              <div style="font-size:22px;font-weight:900;line-height:1.1;color:{num_color};">{free}</div>
              <div style="font-size:10px;color:#aaa;">/ {total} trống</div>
              {rooms_html}
            </td>"""

        link = f"{base_url}/calendar_details/{d.strftime('%Y-%m-%d')}"
        day_cards += f"""
        <a href="{link}" target="_blank" style="display:block;text-decoration:none;color:inherit;
           margin-bottom:8px;border:{'2px' if is_hot else '1.5px'} solid {border};
           border-radius:9px;overflow:hidden;border-left:4px solid {bar_color};">
          <div style="background:{hd_bg};padding:9px 14px;display:flex;
                      justify-content:space-between;align-items:center;">
            <div>
              <span style="font-size:13px;font-weight:700;color:#222;">
                {day['label']} — {day['weekday']}
              </span>{hot_badge}
              <div style="font-size:10px;color:#999;margin-top:2px;">
                {d.strftime('%d tháng %m, %Y')} &nbsp;·&nbsp; 🔗 nhấn để xem chi tiết
              </div>
            </div>
            <div style="font-size:13px;font-weight:700;color:{count_color};">
              {count_text}
            </div>
          </div>
          <div style="background:#{'fafafa' if not is_hot else 'f1f8f1'};padding:4px 0;">
            <table style="width:100%;border-collapse:collapse;">{apt_items}</table>
          </div>
          {'<div style="background:#fce4ec;padding:6px 14px;font-size:11px;color:#880e4f;text-align:center;">⚠️ Hết toàn bộ phòng — cân nhắc đóng nhận đặt phòng ngày này</div>' if full else ''}
        </a>"""

    html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:'Segoe UI',Arial,sans-serif;">
<div style="max-width:580px;margin:24px auto;">

  <!-- Hero -->
  <div style="background:{hero_bg};border-radius:10px 10px 0 0;padding:28px 32px 22px;text-align:center;">
    <div style="font-size:10px;color:rgba(255,255,255,.45);letter-spacing:3px;margin-bottom:8px;">HOTEL PRO</div>
    <div style="font-size:20px;font-weight:700;color:#fff;">{hero_title}</div>
    <div style="font-size:11px;color:rgba(255,255,255,.6);margin-top:5px;">{hero_sub}</div>
    <div style="display:inline-block;margin-top:12px;background:rgba(255,255,255,.12);
                color:rgba(255,255,255,.85);padding:4px 14px;border-radius:12px;
                font-size:11px;border:1px solid rgba(255,255,255,.2);">
      {today_str}
    </div>
  </div>

  <!-- Body -->
  <div style="background:#fff;padding:22px 24px 28px;border-radius:0 0 10px 10px;">
    <div style="font-size:11px;color:#ccc;margin-bottom:12px;">
      💡 Nhấn vào từng ngày để mở lịch chi tiết trên Railway
    </div>
    {day_cards}
    <div style="text-align:center;margin-top:20px;">
      <a href="{base_url}/calendar/" target="_blank"
         style="display:inline-block;background:#1e2a5e;color:#fff;
                padding:11px 28px;border-radius:7px;font-size:13px;
                font-weight:600;text-decoration:none;">
        Mở Lịch Đặt Phòng →
      </a>
    </div>
  </div>

  <!-- Footer -->
  <div style="background:#37474f;border-radius:8px;margin-top:10px;
              padding:14px 20px;text-align:center;">
    <p style="color:#78909c;font-size:11px;margin:0;line-height:1.8;">
      Gửi tự động lúc 07:00 mỗi ngày · Hotel Pro<br>
      <a href="{base_url}" style="color:#80cbc4;">Trang quản lý</a>
    </p>
  </div>
</div>
</body></html>"""
    return subject, html


# ── Gửi email ─────────────────────────────────────────────────────────────────
def send_email(to_list, subject, html_body):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Hotel Pro <{SMTP_EMAIL}>"
    msg["To"]      = ", ".join(to_list)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"📤 Đang kết nối smtp.gmail.com:587 ...")
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, to_list, msg.as_string())

    print(f"✅ Đã gửi thành công tới: {', '.join(to_list)}")


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    to_list   = [e.strip() for e in NOTIFY_EMAILS.split(",") if e.strip()]
    days      = get_vacancy_data()
    THRESHOLD = int(os.getenv("ALERT_THRESHOLD", 3))

    print("Hotel Pro - Gui email thu nghiem")
    print(f"   Tu : {SMTP_EMAIL}")
    print(f"   Den: {', '.join(to_list)}")
    print()

    # Email 1: Báo cáo ngày
    subject, html = build_html(days)
    print("Dang gui bao cao hang ngay...")
    send_email(to_list, subject, html)

    # Email 2: Cảnh báo sớm nếu có ngày >3 phòng trống
    alert_days = [d for d in days[1:] if d["total_free"] > THRESHOLD]
    if alert_days:
        print()
        print(f"Phat hien {len(alert_days)} ngay co >{THRESHOLD} phong trong - gui canh bao som...")
        for alert_day in alert_days:
            subject2, html2 = build_html(days, is_alert=True, alert_day=alert_day)
            send_email(to_list, subject2, html2)
    else:
        print(f"Khong co ngay nao >{THRESHOLD} phong trong.")

    print()
    print("Xong! Kiem tra hop thu cua ban.")
