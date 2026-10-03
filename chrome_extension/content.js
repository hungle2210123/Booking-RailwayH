// "Gửi về Hotel Pro" — runs on admin.booking.com pages.
// Reads ONLY what is already on the screen when you click the button; it never clicks,
// navigates or loads anything on Booking.com by itself.
(function () {
  if (window.__hotelProInjected) return;
  window.__hotelProInjected = true;

  const host = document.createElement('div');
  host.id = 'hotel-pro-ext';
  host.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:2147483647;';
  const root = host.attachShadow({ mode: 'open' });   // own styles, untouched by the extranet's CSS
  document.documentElement.appendChild(host);

  root.innerHTML = `
    <style>
      * { box-sizing: border-box; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
      .fab { border: 0; border-radius: 999px; padding: 12px 18px; font-size: 14px; font-weight: 800; cursor: pointer;
             background: #0f172a; color: #fff; box-shadow: 0 6px 20px rgba(0,0,0,.3); }
      .fab:hover { background: #1e293b; }
      .panel { position: fixed; right: 18px; bottom: 74px; width: 400px; max-height: calc(100vh - 100px); overflow: auto;
               background: #fff; color: #0f172a; border-radius: 16px; box-shadow: 0 12px 40px rgba(0,0,0,.35); padding: 16px; display: none; }
      .panel.open { display: block; }
      h3 { margin: 0 0 4px; font-size: 16px; }
      .badge { display: inline-block; font-size: 11px; font-weight: 800; padding: 2px 8px; border-radius: 999px; margin-left: 6px; vertical-align: 2px; }
      .badge.new { background: #dbeafe; color: #1d4ed8; } .badge.old { background: #dcfce7; color: #166534; }
      .hint { font-size: 12px; color: #64748b; margin: 0 0 10px; }
      .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
      .f { display: flex; flex-direction: column; gap: 3px; }
      .f.full { grid-column: 1 / -1; }
      label { font-size: 11px; font-weight: 800; color: #475569; }
      input { padding: 7px 9px; border: 1.5px solid #cbd5e1; border-radius: 8px; font-size: 13px; width: 100%; }
      input.missing { border-color: #ef4444; background: #fef2f2; }
      input.changed { border-color: #f59e0b; background: #fffbeb; }
      .was { font-size: 11px; color: #b45309; }
      .chk { display: flex; align-items: center; gap: 8px; font-size: 13px; margin-top: 10px; }
      .chk input { width: auto; }
      .row { display: flex; gap: 8px; margin-top: 14px; }
      .row button { flex: 1; border: 0; border-radius: 10px; padding: 10px; font-weight: 800; cursor: pointer; font-size: 14px; }
      .save { background: #16a34a; color: #fff; } .save:disabled { opacity: .5; cursor: wait; }
      .close { background: #e2e8f0; color: #0f172a; }
      .msg { margin-top: 10px; font-size: 13px; font-weight: 700; }
      .msg.ok { color: #15803d; } .msg.err { color: #b91c1c; }
      .msg a { color: #1d4ed8; }
      .paid { margin-top: 8px; font-size: 12px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 6px 8px; color: #166534; }
    </style>
    <div class="panel" id="panel"></div>
    <button class="fab" id="fab" type="button">📥 Gửi về Hotel Pro</button>`;

  const $ = sel => root.querySelector(sel);
  const panel = $('#panel');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const api = (path, body) => chrome.runtime.sendMessage({ type: 'api', path, body });
  const fmt = n => n ? new Intl.NumberFormat('vi-VN').format(Math.round(n)) : '';

  // ── Read what is on screen ─────────────────────────────────────
  function capture() {
    const textOf = el => (el?.innerText || el?.textContent || '').replace(/\s+/g, ' ').trim();
    const pairs = [];
    document.querySelectorAll('dt').forEach(dt => {
      const dd = dt.nextElementSibling;
      if (dd && dd.tagName === 'DD') pairs.push([textOf(dt), textOf(dd)]);
    });
    document.querySelectorAll('tr').forEach(tr => {
      const cells = tr.querySelectorAll('th, td');
      if (cells.length === 2) pairs.push([textOf(cells[0]), textOf(cells[1])]);
    });
    document.querySelectorAll('[class*="label" i]').forEach(lbl => {
      const val = lbl.nextElementSibling;
      const l = textOf(lbl);
      if (val && l && l.length < 40) pairs.push([l, textOf(val)]);
    });
    const heading = textOf(document.querySelector('h1')) || textOf(document.querySelector('h2'));
    return {
      url: location.href,
      title: document.title,
      heading,
      text: (document.body.innerText || '').slice(0, 60000),
      pairs: pairs.filter(p => p[0] && p[1]).slice(0, 400),
      tel: [...document.querySelectorAll('a[href^="tel:"]')].map(a => decodeURIComponent(a.getAttribute('href').slice(4))),
      mailto: [...document.querySelectorAll('a[href^="mailto:"]')].map(a => decodeURIComponent(a.getAttribute('href').slice(7).split('?')[0])),
    };
  }

  // ── Panel ──────────────────────────────────────────────────────
  const FIELDS = [
    ['booking_id', 'Mã đặt phòng', 'text', false],
    ['guest_name', 'Tên khách', 'text', false],
    ['checkin_date', 'Nhận phòng', 'date', false],
    ['checkout_date', 'Trả phòng', 'date', false],
    ['listing', 'Loại phòng (tên chỗ nghỉ)', 'text', true],
    ['room_amount', 'Tổng giá (đ)', 'text', false],
    ['commission', 'Hoa hồng (đ)', 'text', false],
    ['phone', 'Số điện thoại', 'text', false],
    ['nationality', 'Quốc gia', 'text', false],
    ['email', 'Email', 'text', true],
  ];

  function show(result) {
    const p = result.parsed, ex = result.existing;
    const val = k => (k === 'room_amount' || k === 'commission') ? fmt(p[k]) : (p[k] ?? '');
    const old = k => {
      if (!ex) return null;
      const map = { checkin_date: ex.checkin_date, checkout_date: ex.checkout_date, guest_name: ex.guest_name,
                    room_amount: ex.room_amount, commission: ex.commission, listing: ex.listing, phone: ex.phone, email: ex.email };
      return map[k];
    };
    const differs = k => {
      const o = old(k), n = p[k];
      if (o === null || o === undefined || o === '' || n === null || n === undefined || n === '') return false;
      if (k === 'room_amount' || k === 'commission') return Math.abs(Number(o) - Number(n)) >= 1;
      return String(o).trim() !== String(n).trim();
    };
    const missing = new Set(p.missing || []);
    panel.innerHTML = `
      <h3>${esc(p.guest_name || 'Đặt phòng')}${ex ? '<span class="badge old">Đã có trên web</span>' : '<span class="badge new">Booking mới</span>'}</h3>
      <p class="hint">Kiểm tra / sửa thông tin rồi bấm Lưu. Ô <b style="color:#b91c1c">đỏ</b> = chưa đọc được, ô <b style="color:#b45309">vàng</b> = khác với trên web.</p>
      <div class="grid">
        ${FIELDS.map(([k, label, type, full]) => `
          <div class="f ${full ? 'full' : ''}">
            <label for="f_${k}">${label}</label>
            <input id="f_${k}" type="${type}" value="${esc(val(k))}" ${k === 'listing' ? 'list="hp_listings"' : ''}
                   class="${missing.has(k) ? 'missing' : differs(k) ? 'changed' : ''}">
            ${differs(k) ? `<span class="was">Trên web: ${esc(k === 'room_amount' || k === 'commission' ? fmt(old(k)) : old(k))}</span>` : ''}
          </div>`).join('')}
      </div>
      <datalist id="hp_listings">${(result.listings || []).map(l => `<option value="${esc(l)}">`).join('')}</datalist>
      <label class="chk"><input type="checkbox" id="f_cancelled" ${p.status === 'cancelled' ? 'checked' : ''}> Booking này đã HỦY trên Booking.com</label>
      ${ex && (ex.collector || ex.collected_amount) ? `<div class="paid">💰 Đã thu ${fmt(ex.collected_amount)}đ (${esc(ex.collector)}) — tiền đã thu, căn đã xếp, xác nhận đến trên web sẽ giữ nguyên.</div>` : ''}
      ${(p.notes || []).map(n => `<p class="msg err">${esc(n)}</p>`).join('')}
      <div class="row">
        <button class="close" id="b_close" type="button">Đóng</button>
        <button class="save" id="b_save" type="button">💾 Lưu vào web</button>
      </div>
      <div class="msg" id="msg"></div>`;
    panel.classList.add('open');
    $('#b_close').onclick = () => panel.classList.remove('open');
    $('#b_save').onclick = save;
  }

  async function save() {
    const v = k => ($('#f_' + k)?.value || '').trim();
    const body = {
      booking_id: v('booking_id'), guest_name: v('guest_name'),
      checkin_date: v('checkin_date'), checkout_date: v('checkout_date'),
      listing: v('listing'), room_amount: v('room_amount').replace(/\D/g, ''),
      commission: v('commission').replace(/\D/g, ''), phone: v('phone'),
      nationality: v('nationality'), email: v('email'),
      cancelled: $('#f_cancelled').checked,
    };
    const btn = $('#b_save'), msg = $('#msg');
    btn.disabled = true; msg.className = 'msg'; msg.textContent = 'Đang lưu...';
    const r = await api('/api/ext/booking/save', body);
    btn.disabled = false;
    if (r?.success) {
      msg.className = 'msg ok';
      const link = r.checkin_date ? ` · <a href="${esc(r._server)}/calendar_details/${esc(r.checkin_date)}" target="_blank">Mở lịch ngày ${esc(r.checkin_date.split('-').reverse().slice(0, 2).join('/'))}</a>` : '';
      msg.innerHTML = '✅ ' + esc(r.message) + link;
    } else {
      msg.className = 'msg err';
      msg.textContent = '❌ ' + (r?.error || 'Lỗi không rõ');
    }
  }

  $('#fab').addEventListener('click', async () => {
    const fab = $('#fab');
    fab.textContent = '⏳ Đang đọc...';
    const r = await api('/api/ext/booking/parse', capture());
    fab.textContent = '📥 Gửi về Hotel Pro';
    if (!r?.success) {
      panel.innerHTML = `<p class="msg err">❌ ${esc(r?.error || 'Lỗi không rõ')}</p>
        <p class="hint">Kiểm tra địa chỉ web trong biểu tượng tiện ích (góc trên trình duyệt).</p>
        <div class="row"><button class="close" id="b_close" type="button">Đóng</button></div>`;
      panel.classList.add('open');
      $('#b_close').onclick = () => panel.classList.remove('open');
      return;
    }
    show(r);
  });
})();
