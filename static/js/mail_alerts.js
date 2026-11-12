/* 📧 Booking.com mail alerts (owner, Nov 12): "🆕 có đặt phòng mới" on /moi and /may-tinh — a bar at the top, tap = list.
 * Data: /api/moi/mail_alerts (filled by the owner's Gmail script → /api/mail-hook, app_parts/p17_mail.py).
 * MailAlerts.setup() = the one-time setup sheet (copy the script into Google Apps Script). Self-contained, no page code needed. */
(function () {
  let list = [], bar = null, open = false;
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const BOOKING = 'https://admin.booking.com/';
  const post = async (body) => { try { return await (await fetch('/api/moi/mail_alerts', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json(); } catch (e) { return {}; } };
  const sheet = (inner) => `<div style="position:fixed;inset:0;z-index:99990;background:rgba(14,21,37,.55);display:flex;align-items:flex-end;justify-content:center" onclick="if(event.target===this)MailAlerts.close()">
    <div style="background:#fff;color:#0E1525;width:100%;max-width:560px;max-height:88vh;overflow:auto;border-radius:22px 22px 0 0;padding:16px 16px calc(18px + env(safe-area-inset-bottom));font-family:inherit">${inner}</div></div>`;
  const head = (kick, title) => `<div style="display:flex;align-items:center;gap:10px"><div style="flex:1"><div style="font-size:11px;font-weight:800;letter-spacing:.08em;color:#64748B">${kick}</div><div style="font-size:20px;font-weight:800">${title}</div></div>
    <button onclick="MailAlerts.close()" aria-label="Đóng" style="width:40px;height:40px;border-radius:12px;border:1.5px solid #E2E5EB;background:#fff;font-size:18px;font-weight:800;color:#0E1525">✕</button></div>`;
  const btn = (label, act, dark) => `<button onclick="${act}" style="flex:1;min-height:44px;border-radius:12px;font-size:14px;font-weight:800;border:1.5px solid ${dark ? '#0E1525' : '#E2E5EB'};background:${dark ? '#0E1525' : '#fff'};color:${dark ? '#fff' : '#0E1525'}">${label}</button>`;
  function box() { let el = document.getElementById('maOv'); if (!el) { el = document.createElement('div'); el.id = 'maOv'; document.body.appendChild(el); } return el; }

  function drawBar() {
    if (!list.length) { if (bar) { bar.remove(); bar = null; } return; }
    if (!bar) {
      bar = document.createElement('button'); bar.id = 'maBar';
      bar.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);top:calc(8px + env(safe-area-inset-top));z-index:99980;max-width:calc(100vw - 24px);' +
        'border:0;border-radius:999px;padding:11px 16px;color:#fff;font:800 14px/1.1 inherit;box-shadow:0 8px 24px rgba(0,0,0,.35);white-space:nowrap;overflow:hidden;text-overflow:ellipsis';
      bar.onclick = () => MailAlerts.open();
      document.body.appendChild(bar);
    }
    const bad = list.filter((a) => a.bad).length, fresh = list.length - bad;
    bar.style.background = '#DC2626';
    bar.textContent = [fresh ? `🆕 ${fresh} đặt phòng mới` : '', bad ? `❌ ${bad} báo hủy` : ''].filter(Boolean).join(' · ') + ' ›';
  }
  function drawList() {
    if (!open) return;
    box().innerHTML = sheet(head('BOOKING.COM · THƯ MỚI', 'Đặt phòng vừa báo') + (list.length ? list.map((a) => `
      <div style="margin-top:10px;border:1.5px solid ${a.bad ? '#FECACA' : '#E7E9EE'};background:${a.bad ? '#FEF2F2' : '#F7F8FA'};border-radius:14px;padding:10px 12px">
        <div style="display:flex;gap:8px;align-items:baseline"><b style="flex:1;font-size:14.5px;color:${a.bad ? '#B91C1C' : '#0E1525'}">${esc(a.title)}</b><span style="font-size:12px;font-weight:700;color:#64748B">${esc(a.at)}</span></div>
        ${a.lines.map((l) => `<div style="font-size:13.5px;margin-top:3px;color:#334155;overflow-wrap:anywhere">${esc(l)}</div>`).join('')}
        <div style="display:flex;gap:8px;margin-top:10px">${btn('Mở Booking', `window.open('${BOOKING}','_blank')`, true)}${btn('✓ Đã xem', `MailAlerts.seen(${a.id})`)}</div></div>`).join('')
      + (list.length > 1 ? `<div style="display:flex;margin-top:12px">${btn('✓ Đã xem tất cả', 'MailAlerts.seen(0)')}</div>` : '')
      : '<div style="padding:26px 0;text-align:center;color:#64748B;font-weight:700">Không còn thư nào chưa xem ✅</div>'));
  }
  async function load() {
    if (document.hidden) return;
    try { const j = await (await fetch('/api/moi/mail_alerts', { cache: 'no-store' })).json(); if (j.success) { list = j.alerts; drawBar(); drawList(); } } catch (e) {}
  }
  window.MailAlerts = {
    open: () => { open = true; drawList(); },
    close: () => { open = false; box().innerHTML = ''; },
    seen: async (id) => { const j = await post(id ? { id } : { all: true }); if (j.success) { list = j.alerts; drawBar(); if (list.length) drawList(); else MailAlerts.close(); } },
    setup: async () => {
      open = false;
      box().innerHTML = sheet(head('CÀI 1 LẦN', 'Gmail Booking → app') + '<div style="padding:24px 0;text-align:center;color:#64748B;font-weight:700">Đang tải…</div>');
      let j = {}; try { j = await (await fetch('/api/moi/mail_setup', { cache: 'no-store' })).json(); } catch (e) {}
      if (!j.success) return;
      window.__maScript = j.script;
      const step = (n, t) => `<div style="display:flex;gap:10px;margin-top:10px"><b style="flex:none;width:26px;height:26px;border-radius:50%;background:#0E1525;color:#fff;font-size:13px;display:flex;align-items:center;justify-content:center">${n}</b><div style="flex:1;font-size:14px;line-height:1.5">${t}</div></div>`;
      box().innerHTML = sheet(head('CÀI 1 LẦN · NÊN LÀM TRÊN MÁY TÍNH', 'Gmail Booking → app')
        + `<div style="margin-top:12px;border-radius:12px;padding:10px 12px;font-size:13.5px;font-weight:700;background:${j.last ? '#F0FDF4' : '#FEF3C7'};color:${j.last ? '#15803D' : '#92400E'}">${j.last ? '✓ Đang chạy — thư gần nhất nhận lúc ' + esc(j.last.at) : 'Chưa nhận được thư nào — làm 5 bước dưới đây.'}</div>`
        + (j.zalo ? '' : '<div style="margin-top:8px;border-radius:12px;padding:10px 12px;font-size:13px;font-weight:700;background:#FEF2F2;color:#B91C1C">Bot Zalo chưa có ai là "Chủ" đang bật → sẽ không có thông báo trên điện thoại (app vẫn hiện).</div>')
        + step(1, 'Mở <b>script.google.com</b> bằng đúng tài khoản Gmail đang nhận thư Booking → <b>Dự án mới</b>.')
        + step(2, 'Xóa hết chữ có sẵn, bấm nút dưới để copy rồi <b>dán</b> vào.<div style="display:flex;margin-top:8px">' + btn('📋 Copy đoạn script', 'MailAlerts.copy()', true) + '</div>')
        + step(3, 'Bấm 💾 <b>Lưu</b>. Ở ô chọn hàm phía trên chọn <b>caiDat</b> rồi bấm <b>▶ Chạy</b>.')
        + step(4, 'Google hỏi quyền: <b>Xem lại quyền</b> → chọn tài khoản → <b>Nâng cao</b> → <b>Đi tới dự án (không an toàn)</b> → <b>Cho phép</b>. (Google báo vậy vì script do chính bạn tạo, chưa qua kiểm duyệt.)')
        + step(5, 'Xong. Từ giờ mỗi phút script tự xem thư mới của Booking và báo lên app + Zalo. Mở lại bảng này để thấy dòng xanh "Đang chạy".')
        + '<div style="margin-top:12px;font-size:12.5px;color:#64748B;line-height:1.5">Script chỉ đọc thư gửi từ booking.com, chạy trong Gmail của bạn; không ai nhận mật khẩu. Đoạn script có địa chỉ riêng của app — đừng gửi cho người khác.</div>');
    },
    copy: async () => {
      const t = window.__maScript || '';
      try { await navigator.clipboard.writeText(t); } catch (e) { const a = document.createElement('textarea'); a.value = t; document.body.appendChild(a); a.select(); document.execCommand('copy'); a.remove(); }
      alert('Đã copy ✅ — dán vào script.google.com');
    },
  };
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
  setInterval(load, 45000);
  setTimeout(load, 1200);
})();
