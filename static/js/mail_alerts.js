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
    close: () => { open = false; window.__maMails = null; box().innerHTML = ''; },
    seen: async (id) => { const j = await post(id ? { id } : { all: true }); if (j.success) { list = j.alerts; drawBar(); if (list.length) drawList(); else MailAlerts.close(); } },
    bot: async (action, id) => {       // 🤖 the separate Zalo bot for booking alerts
      const body = { action, id };
      if (action === 'token') body.token = ((document.getElementById('maTok') || {}).value || '').replace(/\s+/g, '');
      if (action === 'off' && !confirm('Bỏ bot đặt phòng? Tin báo sẽ quay về bot dọn phòng.')) return;
      let j = {}; try { j = await (await fetch('/api/moi/mail_bot', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })).json(); } catch (e) {}
      if (!j.success) return alert('Chưa được: ' + (j.error || 'lỗi mạng'));
      if (action === 'test') alert('Đã gửi tin thử ✅ xem trong Zalo');
      MailAlerts.setup();
    },
    // 📧 every booking mail of the last 14 days — time booked + booking number (owner, Nov 12)
    list: async (kind) => {
      open = false; window.__maKind = kind === undefined ? (window.__maKind === undefined ? 'last' : window.__maKind) : kind;
      const k = window.__maKind;
      if (!window.__maMails) box().innerHTML = sheet(head('BOOKING.COM · GMAIL', 'Thư đặt phòng') + '<div style="padding:24px 0;text-align:center;color:#64748B;font-weight:700">Đang tải…</div>');
      if (kind === undefined || !window.__maMails) { try { const j = await (await fetch('/api/moi/mail_list', { cache: 'no-store' })).json(); if (j.success) { window.__maMails = j.mails; window.__maLast = j.last; } } catch (e) {} }
      const all = window.__maMails || [], ms = all.filter((m) => !k || m.kind === k);
      const chip = (v, label) => `<button onclick="MailAlerts.list('${v}')" style="min-height:40px;padding:0 12px;border-radius:12px;font-size:13px;font-weight:800;border:1.5px solid ${k === v ? '#0E1525' : '#E2E5EB'};background:${k === v ? '#0E1525' : '#fff'};color:${k === v ? '#fff' : '#0E1525'}">${label} · ${all.filter((m) => !v || m.kind === v).length}</button>`;
      const COL = { last: '#B45309', new: '#0E1525', cancel: '#B91C1C', change: '#475569', msg: '#1D4ED8' };
      let h = head('BOOKING.COM · GMAIL · CHỈ HÔM NAY', 'Thư Booking hôm đó')
        + `<div style="display:flex;gap:6px;flex-wrap:wrap;margin-top:12px">${chip('last', '⚡ Phút chót')}${chip('', 'Tất cả')}${chip('new', 'Đặt mới')}${chip('cancel', 'Hủy')}${chip('msg', '💬 Tin khách')}</div>`
        + `<div style="margin-top:8px;font-size:12.5px;color:#64748B">${window.__maLast ? 'Gmail tự kiểm tra mỗi phút · thư gần nhất nhận lúc ' + esc(window.__maLast.at) : 'Chưa nhận được thư nào từ Gmail — bấm ⚙ Cài đặt ở dưới.'}</div>`;
      if (!ms.length) h += '<div style="padding:26px 0;text-align:center;color:#64748B;font-weight:700">Không có thư nào.</div>';
      let g = '';
      ms.forEach((m) => {
        if (m.group !== g) { g = m.group; h += `<div style="margin:14px 2px 2px;font-size:12px;font-weight:800;color:#64748B;text-transform:uppercase;letter-spacing:.04em">${esc(g)}</div>`; }
        h += `<div style="margin-top:6px;border:1.5px solid #E7E9EE;border-radius:14px;padding:10px 12px;background:${m.kind === 'cancel' ? '#FEF2F2' : '#fff'}">
          <div style="display:flex;align-items:center;gap:8px"><b style="font-size:20px;font-variant-numeric:tabular-nums">${esc(m.time)}</b><span style="font-size:11.5px;font-weight:800;color:#fff;background:${COL[m.kind]};border-radius:999px;padding:3px 8px">${esc(m.label)}</span><span style="flex:1"></span><span style="font-size:12px;font-weight:800;color:${m.in_app ? '#15803D' : '#94A3B8'}">${m.in_app ? '✓ đã vào app' : 'chưa vào app'}</span></div>
          ${m.kind === 'msg' ? `<div style="margin-top:6px;font-size:15px;font-weight:800">👤 ${esc(m.guest)}${m.stay ? ` <span style="font-size:12.5px;font-weight:700;color:#64748B">· ${esc(m.stay)}</span>` : ''}</div><div style="margin-top:4px;background:#EFF6FF;border-radius:10px;padding:8px 10px;font-size:14px;line-height:1.45;overflow-wrap:anywhere">${esc(m.text)}</div>` : ''}
          <div style="display:flex;align-items:center;gap:8px;margin-top:6px"><span style="flex:1;font-size:15px;font-weight:800;font-variant-numeric:tabular-nums">Mã ${esc(m.booking_id || '—')}</span>${m.booking_id ? `<button onclick="MailAlerts.copyId('${esc(m.booking_id)}')" style="min-height:34px;padding:0 10px;border-radius:10px;border:1.5px solid #E2E5EB;background:#fff;font-size:12.5px;font-weight:800;color:#0E1525">Copy mã</button>` : ''}</div>
          <div style="font-size:13px;color:#475569;margin-top:4px;overflow-wrap:anywhere">${esc([m.place, m.arrive ? 'khách đến ' + m.arrive : ''].filter(Boolean).join(' · '))}${m.prop ? '<br>' + esc(m.prop) : ''}</div></div>`;
      });
      h += `<div style="display:flex;gap:8px;margin-top:14px">${btn('↻ Tải lại', 'MailAlerts.list()', true)}${btn('Mở Booking', `window.open('${BOOKING}','_blank')`)}${btn('⚙ Cài đặt', 'MailAlerts.setup()')}</div>`;
      box().innerHTML = sheet(h);
    },
    copyId: async (id) => {
      try { await navigator.clipboard.writeText(id); } catch (e) { const a = document.createElement('textarea'); a.value = id; document.body.appendChild(a); a.select(); document.execCommand('copy'); a.remove(); }
      const el = document.createElement('div'); el.textContent = 'Đã copy mã ' + id;
      el.style.cssText = 'position:fixed;left:50%;bottom:90px;transform:translateX(-50%);z-index:99999;background:#0E1525;color:#fff;padding:10px 16px;border-radius:999px;font:800 13.5px/1 inherit';
      document.body.appendChild(el); setTimeout(() => el.remove(), 1600);
    },
    setup: async () => {
      open = false;
      if (!document.getElementById('maOv') || !document.getElementById('maOv').innerHTML) box().innerHTML = sheet(head('CÀI 1 LẦN', 'Gmail Booking → app') + '<div style="padding:24px 0;text-align:center;color:#64748B;font-weight:700">Đang tải…</div>');
      let j = {}; try { j = await (await fetch('/api/moi/mail_setup', { cache: 'no-store' })).json(); } catch (e) {}
      if (!j.success) return;
      window.__maScript = j.script;
      const card = (inner) => `<div style="margin-top:14px;border:1.5px solid #E7E9EE;border-radius:14px;padding:12px">${inner}</div>`;
      const botBox = card(`<div style="font-size:15px;font-weight:800">🤖 Bot Zalo riêng để báo đặt phòng</div>` + (!j.bot2
        ? `<div style="font-size:13px;color:#475569;line-height:1.5;margin-top:4px">Hiện tin báo đang đi chung bot dọn phòng. Muốn tách riêng: mở <b>Zalo Bot Creator</b> → <b>tạo bot mới</b> (vd "Đặt phòng") → <b>Thiết lập chung</b> → copy <b>Bot Token</b> → dán vào đây.</div>
           <textarea id="maTok" rows="2" autocomplete="off" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="Dán Bot Token của bot MỚI" style="width:100%;box-sizing:border-box;margin-top:8px;padding:10px 12px;border:1.5px solid #CBD5E1;border-radius:12px;font-size:16px;resize:none"></textarea>
           <div style="display:flex;margin-top:8px">${btn('Lưu & kết nối bot', "MailAlerts.bot('token')", true)}</div>`
        : `<div style="font-size:13.5px;font-weight:700;color:#15803D;margin-top:4px">✓ Đã kết nối${j.bot2_name ? ' — ' + esc(j.bot2_name) : ''}</div>`
          + (j.bot2_chats.length
            ? `<div style="font-size:13px;color:#475569;margin-top:6px">Người nhận tin báo:</div>` + j.bot2_chats.map((c) => `<div style="display:flex;align-items:center;gap:8px;margin-top:6px"><b style="flex:1;font-size:14px">${esc(c.name)}</b><button onclick="MailAlerts.bot('remove','${esc(c.id)}')" style="min-height:34px;padding:0 10px;border-radius:10px;border:1.5px solid #E2E5EB;background:#fff;font-size:12.5px;font-weight:800;color:#B91C1C">Bỏ</button></div>`).join('')
              + `<div style="display:flex;gap:8px;margin-top:10px">${btn('Gửi tin thử', "MailAlerts.bot('test')", true)}${btn('Bỏ bot này', "MailAlerts.bot('off')")}</div>`
            : `<div style="margin-top:8px;border-radius:12px;padding:10px 12px;font-size:13.5px;font-weight:700;background:#FEF3C7;color:#92400E;line-height:1.5">Còn 1 bước: mở Zalo, tìm bot mới và <b>nhắn cho nó 1 tin bất kỳ</b> (vd "alo") để bot biết gửi cho ai. Rồi bấm Tải lại.</div>
               <div style="display:flex;gap:8px;margin-top:10px">${btn('↻ Tải lại', 'MailAlerts.setup()', true)}${btn('Bỏ bot này', "MailAlerts.bot('off')")}</div>`)));
      const step = (n, t) => `<div style="display:flex;gap:10px;margin-top:10px"><b style="flex:none;width:26px;height:26px;border-radius:50%;background:#0E1525;color:#fff;font-size:13px;display:flex;align-items:center;justify-content:center">${n}</b><div style="flex:1;font-size:14px;line-height:1.5">${t}</div></div>`;
      box().innerHTML = sheet(head('CÀI 1 LẦN · NÊN LÀM TRÊN MÁY TÍNH', 'Gmail Booking → app')
        + `<div style="margin-top:12px;border-radius:12px;padding:10px 12px;font-size:13.5px;font-weight:700;background:${j.last ? '#F0FDF4' : '#FEF3C7'};color:${j.last ? '#15803D' : '#92400E'}">${j.last ? '✓ Đang chạy — thư gần nhất nhận lúc ' + esc(j.last.at) : 'Chưa nhận được thư nào — làm 5 bước dưới đây.'}</div>`
        + (j.zalo || (j.bot2 && j.bot2_chats.length) ? '' : '<div style="margin-top:8px;border-radius:12px;padding:10px 12px;font-size:13px;font-weight:700;background:#FEF2F2;color:#B91C1C">Bot Zalo chưa có ai là "Chủ" đang bật → sẽ không có thông báo trên điện thoại (app vẫn hiện).</div>')
        + step(1, 'Mở <b>script.google.com</b> bằng đúng tài khoản Gmail đang nhận thư Booking → <b>Dự án mới</b>.')
        + step(2, 'Xóa hết chữ có sẵn, bấm nút dưới để copy rồi <b>dán</b> vào.<div style="display:flex;margin-top:8px">' + btn('📋 Copy đoạn script', 'MailAlerts.copy()', true) + '</div>')
        + step(3, 'Bấm 💾 <b>Lưu</b>. Ở ô chọn hàm phía trên chọn <b>caiDat</b> rồi bấm <b>▶ Chạy</b>.')
        + step(4, 'Google hỏi quyền: <b>Xem lại quyền</b> → chọn tài khoản → <b>Nâng cao</b> → <b>Đi tới dự án (không an toàn)</b> → <b>Cho phép</b>. (Google báo vậy vì script do chính bạn tạo, chưa qua kiểm duyệt.)')
        + step(5, 'Xong. Từ giờ mỗi phút script tự xem thư mới của Booking và báo lên app + Zalo. Mở lại bảng này để thấy dòng xanh "Đang chạy".')
        + botBox
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
