// "Gửi về Hotel Pro" — runs on admin.booking.com pages.
// Reads what is on the screen when you click a button. The ONE exception (owner, 17/11/2026):
// "▶ Mở từng khách" opens the guests of the visible list one by one after the owner presses it.
// Owner decision 17/11/2026: on ONE opened booking it clicks "Hiển thị số điện thoại" once (switch in the
// popup, default on) — also on each guest of "▶ Mở từng khách" / the 7:00 run (1.23), never on partner bookings. Never calls Booking APIs.
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
      .lg { margin-bottom: 10px; }
      .lt { font-size: 12px; font-weight: 800; color: #334155; margin: 8px 0 4px; }
      .lt span { color: #94a3b8; }
      .li { display: flex; gap: 8px; align-items: flex-start; padding: 7px 8px; border: 1px solid #e2e8f0; border-radius: 10px; margin-bottom: 5px; cursor: pointer; }
      .li input { width: auto; margin-top: 3px; }
      .li.cx { background: #fef2f2; border-color: #fecaca; }
      .lm { flex: 1; min-width: 0; display: flex; flex-direction: column; font-size: 13px; }
      .ls { font-size: 11px; color: #64748b; }
      .lc { font-size: 11px; color: #b45309; font-weight: 700; }
      .lp { font-size: 12px; font-weight: 800; white-space: nowrap; }
      .tag { align-self: flex-start; width: fit-content; }
      .tag.mr { display: inline-block; font-size: 10px; font-weight: 800; background: #f59e0b; color: #fff; border-radius: 6px; padding: 0 6px; margin-left: 4px; }
      .tag.nl { display: inline-block; font-size: 10px; font-weight: 800; background: #2563eb; color: #fff; border-radius: 6px; padding: 0 6px; margin-left: 4px; }
      .tag.cx { display: inline-block; font-size: 10px; font-weight: 800; background: #dc2626; color: #fff; border-radius: 6px; padding: 0 6px; margin-left: 4px; }
      .paid { margin-top: 8px; font-size: 12px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 6px 8px; color: #166534; }
      .toast { position: absolute; right: 0; bottom: 56px; width: 300px; max-width: calc(100vw - 36px); background: #0f172a; color: #fff; font-size: 13px; line-height: 1.4; border-radius: 12px; padding: 10px 12px; box-shadow: 0 8px 24px rgba(0,0,0,.25); }
      .toast { cursor: pointer; }
      /* a panel is open → the toast goes to the top of the screen so it never covers the panel's buttons */
      .panel.open ~ #toast { position: fixed; top: 18px; bottom: auto; right: 18px; }
      .toast.ok { background: #166534; } .toast.warn { background: #b45309; } .toast.partner { background: #6d28d9; }
      .fab2 { background: #16a34a; margin-right: 8px; } .fab2:hover { background: #15803d; }
      .fab3 { background: #4f46e5; margin-right: 8px; } .fab3:hover { background: #4338ca; }
      .ai-ta { width: 100%; min-height: 110px; font: 13px/1.45 system-ui, sans-serif; padding: 8px 10px; border: 1.5px solid #cbd5e1;
               border-radius: 10px; resize: vertical; }
      .ai-ta.vi { min-height: 64px; }
      .ai-vi { font-size: 12px; color: #475569; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 7px 9px;
               margin-top: 6px; white-space: pre-wrap; }
      .ai-sec { font-size: 12px; font-weight: 800; color: #334155; margin: 12px 0 5px; }
      .ai-row { display: flex; gap: 6px; margin-top: 6px; }
      .ai-row button { flex: 1; border: 1.5px solid #cbd5e1; background: #fff; border-radius: 10px; padding: 8px; font-weight: 800;
                       font-size: 13px; cursor: pointer; color: #0f172a; }
      .ai-row button.rec { background: #dc2626; border-color: #dc2626; color: #fff; }
      .ai-row button:disabled { opacity: .5; cursor: wait; }
      .tpl { display: block; width: 100%; text-align: left; border: 1.5px solid #e2e8f0; background: #fff; border-radius: 10px;
             padding: 8px 10px; margin-bottom: 6px; font-size: 13px; font-weight: 700; cursor: pointer; color: #0f172a; }
      .tpl.on { border-color: #16a34a; background: #f0fdf4; }
      .pv { white-space: pre-wrap; font-size: 12px; line-height: 1.45; background: #f8fafc; border: 1px solid #e2e8f0;
            border-radius: 10px; padding: 8px 10px; max-height: 220px; overflow: auto; margin: 4px 0 0; }
      .ptag { display: inline-block; font-size: 11px; font-weight: 800; background: #ede9fe; color: #6d28d9; border-radius: 999px; padding: 2px 8px; }
    </style>
    <div class="panel" id="panel"></div>
    <button class="fab fab3" id="ai" type="button" style="display:none">🤖 Trả lời AI</button><button class="fab fab2" id="fill" type="button" style="display:none">💬 Điền tin</button><button class="fab" id="fab" type="button">📥 Gửi về Hotel Pro</button>`;

  const $ = sel => root.querySelector(sel);
  const panel = $('#panel');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const RELOAD_MSG = 'Tiện ích vừa được cập nhật — bấm F5 tải lại trang Booking rồi bấm lại nút.';
  const api = async (path, body) => {
    // After the extension is reloaded, scripts left in already-open tabs lose their connection
    if (!chrome.runtime?.id) return { success: false, error: RELOAD_MSG };
    try {
      return await Promise.race([
        chrome.runtime.sendMessage({ type: 'api', path, body }),
        new Promise((_, rej) => setTimeout(() => rej(new Error(
          'Web Hotel Pro không trả lời sau 40 giây — kiểm tra mạng hoặc địa chỉ web trong cài đặt tiện ích.')), 40000)),
      ]);
    } catch (e) {
      return { success: false, error: /context invalidated/i.test(e.message) ? RELOAD_MSG : e.message };
    }
  };
  const fmt = n => n ? new Intl.NumberFormat('vi-VN').format(Math.round(n)) : '';

  // ── Reservation LIST page ("Đặt phòng" table) ───────────────────
  const fold = t => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().replace(/\s+/g, ' ').trim();
  const LIST_KEYS = ['ma so dat phong', 'ma dat phong', 'booking number', 'reservation number'];
  const BID_RE = /^\s*\d{8,12}\s*$/;
  const cellText = el => (el?.innerText || el?.textContent || '').trim();
  const rawText = el => (el?.textContent || '').trim();
  const isHeaderText = t => { const f = fold(t); return f.length < 60 && LIST_KEYS.some(k => f.includes(k)); };
  const cellObj = c => ({ text: cellText(c), link: cellText(c.querySelector('a, [role="link"]')) });

  // The page itself plus any same-origin frames (the table may live inside an iframe)
  function allDocs() {
    const out = [document];
    for (let i = 0; i < out.length; i++) {
      out[i].querySelectorAll('iframe, frame').forEach(f => {
        try { if (f.contentDocument && !out.includes(f.contentDocument)) out.push(f.contentDocument); } catch (e) { /* other origin */ }
      });
    }
    return out;
  }

  // A row's "cells": its direct children, skipping single-child wrapper layers
  function cellsOf(row) {
    let el = row;
    while (el.children.length === 1) el = el.children[0];
    return [...el.children];
  }

  // Strategy 1 — a real <table>. Rows may use <th> for the first column, so use row.cells.
  function fromTable(doc) {
    for (const t of doc.querySelectorAll('table')) {
      const trs = [...t.rows];
      // A list header has many columns; a 2-column "label | value" table is a detail page
      const hi = trs.findIndex(r => r.cells.length >= 5 && [...r.cells].some(c => isHeaderText(cellText(c))));
      if (hi < 0) continue;
      const headers = [...trs[hi].cells].map(c => cellText(c).replace(/\s+/g, ' '));
      const rows = trs.slice(hi + 1)
        .filter(r => [...r.cells].some(c => /\d{8,12}/.test(cellText(c))))
        .map(r => [...r.cells].map(cellObj));
      if (rows.length) return { headers, rows, how: 'table' };
    }
    return null;
  }

  // Strategy 2 — any layout (div grids, ARIA): start from the booking-number cells.
  function fromBookingNumbers(doc) {
    const leaves = [...doc.querySelectorAll('a, [role="link"], span, div, td, th')]
      .filter(el => el.children.length === 0 && BID_RE.test(rawText(el)));
    // A list shows several booking numbers; a single one is a reservation detail page
    if (new Set(leaves.map(rawText)).size < 2) return null;
    // Row = the ancestor just below the container shared with a booking number of ANOTHER row
    // (the same number can appear twice in one row, e.g. a link and a hidden copy)
    const rowOf = leaf => {
      const other = leaves.find(l => rawText(l) !== rawText(leaf));
      let el = leaf;
      while (el.parentElement && !el.parentElement.contains(other)) el = el.parentElement;
      return el;
    };
    const rowEls = [...new Set(leaves.map(rowOf))].filter(Boolean);
    const rows = rowEls.map(r => cellsOf(r).map(cellObj)).filter(c => c.length >= 4);
    if (rows.length < 2) return null;
    // Header row: the element holding the "Mã số đặt phòng" title, at the same level as the rows
    let headers = [];
    const hLeaf = [...doc.querySelectorAll('th, [role="columnheader"], div, span, button')]
      .find(el => el.children.length <= 2 && rawText(el).length < 80 && isHeaderText(rawText(el)));
    if (hLeaf) {
      let el = hLeaf;
      while (el.parentElement && cellsOf(el.parentElement).length < rows[0].length - 1) el = el.parentElement;
      const hr = el.parentElement;
      if (hr) headers = cellsOf(hr).map(c => cellText(c).replace(/\s+/g, ' '));
    }
    return { headers, rows, how: 'numbers' };
  }

  function captureList() {
    for (const doc of allDocs()) {
      const found = fromTable(doc) || fromBookingNumbers(doc);
      if (found) return { mode: 'list', url: location.href, ...found };
    }
    return null;
  }

  // What the page looks like, WITHOUT guest data — for fixing the reader if it still fails
  function diagnostics() {
    const docs = allDocs();
    const frames = document.querySelectorAll('iframe, frame').length;
    const d = docs[docs.length - 1];
    const leaves = docs.flatMap(doc => [...doc.querySelectorAll('a, span, div, td, th')]
      .filter(el => el.children.length === 0 && BID_RE.test(rawText(el))));
    const path = el => { const p = []; for (let e = el; e && p.length < 8; e = e.parentElement) p.push(e.tagName.toLowerCase() + (e.getAttribute('role') ? `[role=${e.getAttribute('role')}]` : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '')); return p.join(' < '); };
    const hdr = docs.flatMap(doc => [...doc.querySelectorAll('th, [role="columnheader"], div, span, button')])
      .find(el => el.children.length <= 2 && rawText(el).length < 80 && isHeaderText(rawText(el)));
    return {
      page: location.pathname, frames, sameOriginDocs: docs.length,
      tables: docs.reduce((n, doc) => n + doc.querySelectorAll('table').length, 0),
      roleRows: docs.reduce((n, doc) => n + doc.querySelectorAll('[role="row"]').length, 0),
      bookingNumberCells: leaves.length,
      bookingNumberPath: leaves[0] ? path(leaves[0]) : null,
      headerFound: !!hdr, headerPath: hdr ? path(hdr) : null,
      shadowHosts: [...d.querySelectorAll('*')].filter(e => e.shadowRoot).length,
    };
  }
  const safeDiagnostics = extra => {
    try { return { ...diagnostics(), ...extra }; } catch (e) { return { diagnosticsError: e.message, ...extra }; }
  };

  // ── Read what is on screen ─────────────────────────────────────
  const safeDecode = v => { try { return decodeURIComponent(v); } catch (e) { return v; } };
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
      tel: [...document.querySelectorAll('a[href^="tel:"]')].map(a => safeDecode(a.getAttribute('href').slice(4))),
      mailto: [...document.querySelectorAll('a[href^="mailto:"]')].map(a => safeDecode(a.getAttribute('href').slice(7).split('?')[0])),
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

  let shownRooms = [];
  function show(result) {
    const p = result.parsed, ex = result.existing;
    shownRooms = p.rooms || [];
    const val = k => (k === 'room_amount' || k === 'commission') ? fmt(p[k])
      : (p[k] ?? ((k === 'phone' || k === 'email') && ex && ex[k] ? ex[k] : ''));
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
    const missing = new Set((p.missing || []).filter(k => !((k === 'phone' || k === 'email') && ex && ex[k])));
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
      ${shownRooms.length > 1 ? `<div class="paid" style="background:#eff6ff;border-color:#bfdbfe;color:#1e3a8a">
        🛏️ <b>Khách đặt ${shownRooms.length} phòng</b> → lưu thành ${shownRooms.length} đặt phòng riêng trên web
        (mỗi phòng tên, giá, ngày riêng; phòng bị hủy → <b>Báo hủy</b>):
        ${shownRooms.map((r, i) => `<div style="margin-top:4px">#${i + 1} ${esc(r.title)} · ${fmt(r.price)}đ
          ${r.cancelled ? '<span class="tag cx">Hủy bởi khách</span>' : ''}</div>`).join('')}
        <div style="margin-top:4px;opacity:.75">Mã trên web: ${esc(p.booking_id || '')}${shownRooms.slice(1).map((_, i) => ', ' + esc(p.booking_id || '') + '-' + (i + 2)).join('')}</div></div>` : ''}
      <datalist id="hp_listings">${(result.listings || []).map(l => `<option value="${esc(l)}">`).join('')}</datalist>
      <label class="chk"><input type="checkbox" id="f_cancelled" ${p.status === 'cancelled' ? 'checked' : ''}> Khách đã HỦY trên Booking.com → <b>Báo hủy</b> trên lịch (không xoá, hoàn tác được)</label>
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
    panel.querySelectorAll('.grid input').forEach(i => i.addEventListener('input', () => i.classList.remove('missing')));
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
      rooms: shownRooms.length > 1 ? shownRooms : undefined,
    };
    const btn = $('#b_save'), msg = $('#msg');
    btn.disabled = true; msg.className = 'msg'; msg.textContent = 'Đang lưu...';
    const r = await api('/api/ext/booking/save', body);
    btn.disabled = false;
    if (r?.success) {
      msg.className = 'msg ok';
      const link = r.checkin_date ? ` · <a href="${esc(r._server)}/calendar_details/${esc(r.checkin_date)}" target="_blank">Mở lịch ngày ${esc(r.checkin_date.split('-').reverse().slice(0, 2).join('/'))}</a>` : '';
      const saved = body.phone ? ` · 📞 SĐT trên web: <b>${esc(body.phone)}</b>` : '';
      msg.innerHTML = '✅ ' + esc(r.action === 'unchanged' ? 'Đã lưu — trên web đã đúng như vậy' : r.message) + saved + link;
    } else {
      msg.className = 'msg err';
      msg.textContent = '❌ ' + (r?.error || 'Lỗi không rõ');
    }
  }

  // ── List panel ─────────────────────────────────────────────────
  const GROUPS = [
    ['new', '🆕 Booking mới', true],
    ['changed', '✏️ Có thay đổi', true],
    ['same', '✔ Không đổi', false],
    ['skip_cancelled', '— Đã hủy, chưa có trên web (bỏ qua)', false],
  ];
  const ddmm = iso => iso ? iso.split('-').reverse().slice(0, 2).join('/') : '?';

  function showList(result) {
    const items = result.items || [];
    const rowHtml = (it, i, checked) => `
      <label class="li ${it.status === 'cancelled' ? 'cx' : ''}">
        <input type="checkbox" data-i="${i}" ${checked ? 'checked' : ''} ${it.action === 'same' || it.action === 'skip_cancelled' ? 'disabled' : ''}>
        <span class="lm">
          <b>${esc(it.guest_name || it.existing_name || '?')}</b>
          ${it.status === 'cancelled' ? '<span class="tag cx">Đã hủy</span>' : ''}
          ${it.rooms > 1 ? `<span class="tag mr">⚠️ ${it.rooms} phòng</span>` : ''}
          ${it.new_listing && it.status !== 'cancelled' ? '<span class="tag nl">🆕 loại phòng mới</span>' : ''}
          <span class="ls">${ddmm(it.checkin_date)} → ${ddmm(it.checkout_date)} · ${esc(it.listing || '')} · #${esc(it.booking_id)}</span>
          ${it.changes && it.changes.length ? `<span class="lc">${esc(it.changes.join(' · '))}</span>` : ''}
        </span>
        <span class="lp">${it.room_amount ? fmt(it.room_amount) : ''}</span>
      </label>`;
    const groups = GROUPS.map(([key, title, on]) => {
      const list = items.map((it, i) => [it, i]).filter(([it]) => it.action === key);
      if (!list.length) return '';
      return `<div class="lg"><div class="lt">${title} <span>(${list.length})</span></div>
        ${list.map(([it, i]) => rowHtml(it, i, on)).join('')}</div>`;
    }).join('');
    const toSave = items.filter(it => it.action === 'new' || it.action === 'changed').length;
    panel.innerHTML = `
      <h3>📋 ${items.length} booking trong bảng</h3>
      <p class="hint">Tích các booking muốn lưu. Booking <b>Đã hủy</b> trên Booking sẽ được đánh dấu hủy trên web.
        Số điện thoại không có ở trang này — mở từng đặt phòng để lấy.</p>
      ${groups || '<p class="hint">Không đọc được dòng nào.</p>'}
      <div class="row">
        <button class="close" id="b_close" type="button">Đóng</button>
        <button class="save" id="b_save" type="button" ${toSave ? '' : 'disabled'}>💾 Lưu ${toSave} booking</button>
      </div>
      <div class="msg" id="msg"></div>`;
    panel.classList.add('open');
    $('#b_close').onclick = () => panel.classList.remove('open');
    const btn = $('#b_save');
    const recount = () => {
      const n = root.querySelectorAll('.li input:checked:not(:disabled)').length;
      btn.textContent = `💾 Lưu ${n} booking`; btn.disabled = !n;
    };
    root.querySelectorAll('.li input').forEach(c => c.addEventListener('change', recount));
    btn.onclick = async () => {
      const chosen = [...root.querySelectorAll('.li input:checked:not(:disabled)')].map(c => {
        const it = items[+c.dataset.i];
        return { ...it, cancelled: it.status === 'cancelled' };
      });
      const msg = $('#msg');
      btn.disabled = true; msg.className = 'msg'; msg.textContent = `Đang lưu ${chosen.length} booking...`;
      const r = await api('/api/ext/booking/save_many', { items: chosen });
      btn.disabled = false;
      if (!r?.success) { msg.className = 'msg err'; msg.textContent = '❌ ' + (r?.error || 'Lỗi không rõ'); return; }
      const s = r.summary, errs = r.results.filter(x => !x.success);
      msg.className = errs.length ? 'msg err' : 'msg ok';
      msg.innerHTML = `✅ Thêm ${s.created} · Cập nhật ${s.updated} · Không đổi ${s.unchanged}`
        + (errs.length ? `<br>❌ Lỗi ${errs.length}: ${errs.map(e => esc((e.booking_id || '') + ' — ' + e.error)).join('<br>')}` : '');
    };
  }

  // One panel for every kind of failure: message, what to do, and page structure (no guest data)
  function showProblem(message, hint, diag) {
    const text = diag ? JSON.stringify(diag, null, 1) : '';
    panel.innerHTML = `<p class="msg err">❌ ${esc(message)}</p>
      ${hint ? `<p class="hint">${hint}</p>` : ''}
      ${text ? `<pre style="font-size:10px;max-height:160px;overflow:auto;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:6px;white-space:pre-wrap">${esc(text)}</pre>` : ''}
      <div class="row"><button class="close" id="b_close" type="button">Đóng</button>
        ${text ? '<button class="save" id="b_copy" type="button">📋 Sao chép chẩn đoán</button>' : ''}</div>`;
    panel.classList.add('open');
    $('#b_close').onclick = () => panel.classList.remove('open');
    if (text) $('#b_copy').onclick = async () => {
      try { await navigator.clipboard.writeText(text); $('#b_copy').textContent = '✅ Đã sao chép'; }
      catch (e) { $('#b_copy').textContent = 'Không sao chép được — chụp màn hình giúp'; }
    };
  }
  const DIAG_HINT = 'Bấm <b>Sao chép chẩn đoán</b> và gửi cho người hỗ trợ (chỉ có cấu trúc trang, không có tên hay thông tin khách).';
  const paint = () => new Promise(r => requestAnimationFrame(() => setTimeout(r, 0)));  // let the button text show

  let busy = false;
  $('#fab').addEventListener('click', async () => {
    if (busy) return;
    busy = true;
    const fab = $('#fab');
    const t = { start: performance.now() };
    const ms = since => Math.round(performance.now() - since);
    let stage = 'đọc trang';
    let listPage = null;
    try {
      fab.textContent = '⏳ Đang đọc trang...';
      await paint();
      try { listPage = captureList(); } catch (e) { t.listError = e.message; }
      t.readMs = ms(t.start);

      stage = 'gửi về web';
      fab.textContent = listPage ? `⏳ Đang gửi ${listPage.rows.length} dòng...` : '⏳ Đang gửi về web...';
      await paint();
      const t1 = performance.now();
      let r = await api('/api/ext/booking/parse', listPage || capture());
      t.serverMs = ms(t1);

      if (!r?.success && listPage) {
        // Not a list after all → try it as a single reservation page
        const single = await api('/api/ext/booking/parse', capture());
        if (single?.success && single.mode === 'single' && single.parsed.booking_id) { show(single); return; }
        showProblem(r?.error || 'Lỗi không rõ', DIAG_HINT, safeDiagnostics({
          how: listPage.how, headers: listPage.headers,
          cellsPerRow: listPage.rows.slice(0, 5).map(x => x.length), timing: t }));
        return;
      }
      if (!r?.success) {
        showProblem(r?.error || 'Lỗi không rõ',
          'Kiểm tra địa chỉ web trong biểu tượng tiện ích (góc trên trình duyệt).');
        return;
      }
      if (r.mode === 'list') { showList(r); return; }
      if (!r.parsed.booking_id) {
        showProblem('Không thấy đặt phòng trên trang này.',
          'Mở trang <b>Đặt phòng</b> (danh sách) hoặc một đặt phòng cụ thể rồi bấm lại. Nếu đang ở đúng trang mà vẫn lỗi: ' + DIAG_HINT,
          safeDiagnostics({ timing: t }));
        return;
      }
      show(r);
    } catch (e) {
      showProblem(`Lỗi khi ${stage}: ${e.message}`, DIAG_HINT,
        safeDiagnostics({ stage, error: String(e && e.stack || e).slice(0, 400), timing: t }));
    } finally {
      busy = false;
      fab.textContent = '📥 Gửi về Hotel Pro';
    }
  });

  // ── Số điện thoại hiện ra trên trang đặt phòng → tự lưu về web ──────
  // Chỉ ĐỌC trang: chính bạn bấm nút "Hiển thị số điện thoại" của Booking, tiện ích đọc số đó rồi lưu.
  // Chủ nhà quyết định 17/11/2026: tiện ích tự bấm nút đó 1 lần trên trang 1 khách (xem autoReveal bên dưới);
  // bấm cả khi đang "▶ Mở từng khách" (1.23), không bấm đặt phòng qua đối tác.
  // Not inside a longer run of digits — a booking number like 5091703794 must not yield "091703794"
  // …and never across a line break (the address line under the phone starts with digits too)
  const PHONE_FIND = /(?<![\d+])(?:\+|00|0)\d[\d \t ().\-]{6,18}\d(?!\d)/g;
  const digitsOf = s => String(s || '').replace(/\D/g, '');
  const digitsOk = s => { const n = digitsOf(s).length; return n >= 8 && n <= 15; };
  const EMAILS_RE = /[^\s@]+@[^\s@]+\.[a-z]{2,}/gi;
  const REVEAL_WORDS = ['hien thi so dien thoai', 'xem so dien thoai', 'show phone', 'display phone', 'reveal phone'];
  const isRevealEl = el => !!el && rawText(el).length < 60 && REVEAL_WORDS.some(w => fold(rawText(el)).includes(w));
  let revealSpot = null;
  function phonesIn(el) {
    const out = [];
    el.querySelectorAll('a[href^="tel:"]').forEach(a => { const v = safeDecode(a.getAttribute('href').slice(4)).trim(); if (digitsOk(v)) out.push(v); });
    ((el.innerText || '').match(PHONE_FIND) || []).forEach(m => { if (digitsOk(m)) out.push(m.trim()); });
    return out;
  }
  // Số của khách chỉ lấy trong khung thông tin khách (cạnh email @guest.booking.com hoặc nút hiện số),
  // để không nhầm sang số khác trên trang (vd số của chỗ nghỉ).
  function phoneNear(el) {
    for (let a = el, lvl = 0; a && lvl < 6; a = a.parentElement, lvl++) {
      if (((a.innerText || '').match(EMAILS_RE) || []).length > 1 && lvl > 0) break;
      const hits = phonesIn(a).filter(p => digitsOf(p) !== digitsOf(rawText(el)));
      if (hits.length) return hits[0];
    }
    return null;
  }
  function guestPhone() {
    const mail = [...document.querySelectorAll('a, span, div, p')].find(el => el.children.length === 0 && /@guest\.booking\.com/i.test(rawText(el)));
    const near = mail && phoneNear(mail);
    if (near) return near;
    if (revealSpot && document.contains(revealSpot)) { const hits = phonesIn(revealSpot); if (hits.length) return hits[0]; }
    return null;
  }
  let toastTimer;
  function toast(html, kind, ms = 7000) {
    let el = $('#toast');
    if (!el) { el = document.createElement('div'); el.id = 'toast'; root.appendChild(el); }
    el.className = 'toast ' + (kind || '');
    el.innerHTML = html + ' <span style="opacity:.6">· bấm để tắt</span>';
    el.onclick = () => { clearTimeout(toastTimer); el.remove(); };
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.remove(), ms);
  }
  // "Đối tác Booking.com" box: booked through a partner company. The number shown is the partner's
  // (same local number for everyone, only the country code changes) → never saved as the guest's.
  const PARTNER_WORDS = ['cong ty hop tac voi booking.com', 'partner company of booking.com',
                         'company that partners with booking.com', 'through a booking.com partner'];
  const isPartnerBooking = () => { const t = fold(document.body.innerText || ''); return PARTNER_WORDS.some(w => t.includes(w)); };

  const phoneDone = new Set();
  let phoneSaved = { bid: '', at: 0 }, shotSavedFor = '';   // ▶ Mở từng khách moves on as soon as both are done
  let phoneBusy = false;
  async function checkPhone() {
    if (phoneBusy || busy || !chrome.runtime?.id) return;
    const partner = isPartnerBooking();
    const ph = guestPhone();
    if (!ph && !partner) return;
    const key = location.href.split('#')[0] + '|' + (partner ? 'partner' : digitsOf(ph));
    if (phoneDone.has(key)) { if (ph && revealedNow()) shotAfterReveal(); return; }
    phoneBusy = true;
    try {
      phoneDone.add(key);
      const r = await api('/api/ext/booking/phone', { ...capture(), phone: ph || '', partner });
      if (!r?.success) { phoneDone.delete(key); return; }
      phoneSaved = { bid: resId(), at: Date.now() };
      if (r.status === 'partner') toast(`🤝 <b>${esc(r.guest_name)}</b> đặt qua <b>đối tác Booking</b> — số trên trang là của đối tác nên <b>không lưu</b>. Bấm <b>💬 Điền tin</b> để xin số Zalo/WhatsApp trong khung chat.`, 'partner');
      else if (r.status === 'partner_not_on_web') toast(`🤝 Đặt qua <b>đối tác Booking</b> — số trên trang là của đối tác, không phải của khách. Chưa tự thêm được booking${r.error ? ' (' + esc(r.error) + ')' : ''}: bấm 📥 để thêm.`, 'partner');
      else if (r.status === 'created') toast(`📥 Đã tự thêm booking <b>${esc(r.guest_name)}</b> vào web + lưu SĐT <b>${esc(r.phone)}</b>`, 'ok');
      else if (r.status === 'saved') toast(`📞 Đã lưu SĐT <b>${esc(r.phone)}</b> cho <b>${esc(r.guest_name)}</b>`, 'ok');
      else if (r.status === 'same') toast(`📞 SĐT của <b>${esc(r.guest_name)}</b> đã có trên web`);
      else if (r.status === 'duplicate') toast(`⚠️ Số <b>${esc(r.phone)}</b> đang là của khách <b>${esc(r.other_name)}</b> — chưa lưu, kiểm tra lại`, 'warn');
      else if (r.status === 'not_on_web') toast(`📞 Thấy SĐT nhưng chưa tự thêm được booking #${esc(r.booking_id)}${r.error ? ' (' + esc(r.error) + ')' : ''} — bấm 📥 để thêm`, 'warn');
      // 📸 the Booking picture is taken only right after YOU clicked "Hiển thị số điện thoại" and the number shows
      //    (owner, Oct 2026: never on page open / tab switch — those pictures came out wrong)
      if (ph && revealedNow() && ['saved', 'created', 'same', 'partner', 'duplicate'].includes(r.status)) shotAfterReveal();
    } finally { phoneBusy = false; }
  }

  // ⚡ Auto-capture of the reservation box (always on — owner decision), only right after the owner clicked
  //   Booking's "Hiển thị số điện thoại" on this page and the number showed — never on page open or tab switch.
  const autoShotDone = new Set();
  let lastPhoneToast = '';
  let revealAt = 0;
  const revealedNow = () => Date.now() - revealAt < 20000;
  function autoShot(kind) {
    const bid = resId();
    if (!bid || !chrome.runtime?.id) return Promise.resolve(null);
    const key = bid + '|' + kind;
    if (autoShotDone.has(key)) return Promise.resolve(null);
    autoShotDone.add(key);
    lastPhoneToast = kind === 'phone' ? ($('#toast')?.innerHTML || '') : '';
    // 1.48 (owner Nov 22: "cần giữ hiển thị màn hình Chrome thì mới chụp được"): the real screen capture only works for
    // the tab ON the screen → a tab behind, a minimized window, a locked PC draw the box from the page instead
    // (domshot.js); the screen capture failing for any reason (not 'busy') → the same.
    // 1.49: background.js now takes a REAL picture of a tab not on the screen too (Chrome draws it: DevTools protocol);
    // the drawing from the page is only the last resort
    return chrome.runtime.sendMessage({ type: 'auto-shot' }).catch(() => null).then(r => {
      if (r?.success || r?.error === 'busy') return r;
      return domAutoShot();
    }).then(r => {
      if (r?.success) return r;
      autoShotDone.delete(key);                      // allow another try
      if (r?.error === 'busy') setTimeout(() => autoShot(kind), 2500);   // another capture was running
      return r;
    }).catch(() => { autoShotDone.delete(key); return null; });
  }
  async function domAutoShot() {
    if (!window.hpDomShot) return { success: false, error: 'domshot.js chưa nạp' };
    let prep;
    try { prep = prepareShot(true); } catch (e) { cancelShot(); return { success: false, error: e.message }; }
    if (!prep?.ok) return { success: false, error: prep?.error };
    return (await finishShot(null)) ? { success: true, dom: true } : { success: false, error: 'Không vẽ được khung đặt phòng' };
  }
  function shotAfterReveal() {
    const bid = resId();
    if (!bid || autoShotDone.has(bid + '|phone')) return;
    let tries = 0;
    const go = async () => {
      // 1.48: a tab not on the screen is drawn from the page (domshot.js) — only a different booking stops it
      if (resId() !== bid) return;
      const r = await autoShot('phone');
      if (r?.success) shotSavedFor = bid;
      if (r && !r.success && r.reason !== 'off' && /khung/i.test(r.error || '') && ++tries < 2) setTimeout(go, 3000);
    };
    setTimeout(go, 1000);                            // the number has just appeared: let the page settle
  }
  // Chỉ phản ứng khi bạn bấm đúng nút "Hiển thị số điện thoại"; số hiện ra sau đó một chút.
  document.addEventListener('click', e => {
    if (host.contains(e.target)) return;
    const el = e.target.closest ? e.target.closest('button, a, [role="button"], span') : null;
    if (!isRevealEl(el)) return;
    revealAt = Date.now();
    revealSpot = el.parentElement?.parentElement || el.parentElement;
    [600, 1500, 3000, 6000].forEach(ms => setTimeout(checkPhone, ms));
  }, true);
  // Nếu số đã hiện sẵn khi mở trang (hoặc là đặt phòng qua đối tác): chỉ lưu số, KHÔNG chụp ảnh.
  // 1.52 (owner Nov 22, Sanka Silva 6437146610): an OLD booking arriving today shows the number with NO
  // "Hiển thị số điện thoại" button; the page (a run's unfocused window) was drawn after the 2.5 s / 6 s reads → the
  // number was never read. Now: read every 1.5 s for 40 s after a reservation opens, until the number is saved.
  let phoneWatchT = null;
  function phoneWatch() {
    clearInterval(phoneWatchT);
    const bid = resId(), t0 = Date.now();
    if (!bid) { [2500, 6000].forEach(ms => setTimeout(checkPhone, ms)); return; }
    phoneWatchT = setInterval(() => {
      if (resId() !== bid || phoneSaved.bid === bid || Date.now() - t0 > 40000 || !chrome.runtime?.id) { clearInterval(phoneWatchT); return; }
      checkPhone();
    }, 1500);
  }
  setTimeout(phoneWatch, 0);                         // after the whole script ran (resId is declared further down)

  // ── Tự bấm "Hiển thị số điện thoại" (chủ nhà quyết định 17/11/2026, chấp nhận rủi ro tài khoản) ──
  // 1 lần cho mỗi res_id, chờ 1–2 giây ngẫu nhiên; el.click() kích hoạt listener ở trên → checkPhone + ảnh.
  // Bấm cả khi đang chạy "▶ Mở từng khách" (kể cả lần tự chạy 7:00 — runStep chờ lưu số), không bấm đặt phòng qua đối tác.
  // Tắt được trong popup tiện ích (hpAutoReveal, mặc định bật).
  const revealClicked = new Set();
  let revealTimer = null;
  let autoRevealOn = false;
  // true = a click is scheduled (▶ Mở từng khách then waits for the number to be saved)
  function autoRevealTry() {
    const bid = resId();
    if (!autoRevealOn || !bid || revealClicked.has(bid)) return false;
    if (revealTimer) return true;
    if (isPartnerBooking()) return false;
    const el = [...document.querySelectorAll('button, a, [role="button"]')].find(b => !host.contains(b) && b.offsetParent !== null && isRevealEl(b));
    if (!el) return false;
    revealTimer = setTimeout(() => {
      revealTimer = null;
      if (resId() !== bid || revealClicked.has(bid) || isPartnerBooking() || !el.isConnected) return;
      revealClicked.add(bid);
      el.click();
    }, 1000 + Math.random() * 1000);
    return true;
  }
  chrome.storage.sync.get({ hpAutoReveal: true }).then(({ hpAutoReveal }) => {
    if (!hpAutoReveal) return;
    autoRevealOn = true;
    let pend = null;
    new MutationObserver(() => { if (!pend) pend = setTimeout(() => { pend = null; autoRevealTry(); }, 400); })
      .observe(document.body, { childList: true, subtree: true });
    autoRevealTry();
  }).catch(() => {});

  // ── 💬 Điền tin: put a ready message into Booking's own "Trò chuyện với khách" box ──────
  // Only types into the box on the page you are looking at; YOU read it and press Booking's Gửi.
  const resId = () => { try { const q = new URL(location.href).searchParams; return q.get('res_id') || q.get('reservation_id') || ''; } catch (e) { return ''; } };
  function chatBox() {
    const cands = [...document.querySelectorAll('textarea, [contenteditable="true"], [role="textbox"]')]
      .filter(el => !host.contains(el) && el.offsetParent !== null);
    const hint = el => fold([el.getAttribute('placeholder'), el.getAttribute('aria-label'), el.getAttribute('data-placeholder')].join(' '));
    return cands.find(el => /soan tin nhan|tin nhan|message|reply|tra loi/.test(hint(el))) || cands[cands.length - 1] || null;
  }
  function putInChat(box, text) {
    box.focus();
    if (box.tagName === 'TEXTAREA' || box.tagName === 'INPUT') {
      const proto = box.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto, 'value').set.call(box, text);   // so the page's framework sees it
      box.dispatchEvent(new Event('input', { bubbles: true }));
      box.dispatchEvent(new Event('change', { bubbles: true }));
    } else {
      document.execCommand('selectAll', false, null);
      document.execCommand('insertText', false, text);
    }
    box.scrollIntoView({ block: 'center', behavior: 'smooth' });
  }
  // Booking names often end with the country code ("Lucas de Kok nl") — not part of a greeting
  const cleanName = n => String(n || '').replace(/\s+[a-z]{2}$/, '').trim();
  const fillTokens = (t, g) => t
    .replace(/\{ten\}/g, cleanName(g.ten) || 'bạn').replace(/\{nhan\}/g, g.nhan || '')
    .replace(/\{tra\}/g, g.tra || '').replace(/\{phong\}/g, g.phong ? ' (' + g.phong + ')' : '');

  const fillBtn = $('#fill');
  let shownResId = null;
  const refreshFillBtn = () => {
    fillBtn.style.display = resId() ? '' : 'none';
    if (resId() !== shownResId) {                // another reservation opened (also without a reload)
      if (shownResId !== null) phoneWatch();
      shownResId = resId();
    }
  };
  refreshFillBtn();
  setInterval(refreshFillBtn, 2000);              // the extranet can switch pages without reloading
  fillBtn.addEventListener('click', async () => {
    fillBtn.textContent = '⏳ ...';
    const r = await api('/api/ext/auto_messages', { ...capture(), partner: isPartnerBooking() });
    fillBtn.textContent = '💬 Điền tin';
    if (!r?.success) { showProblem(r?.error || 'Lỗi không rõ', 'Kiểm tra địa chỉ web trong biểu tượng tiện ích (góc trên trình duyệt).'); return; }
    let cur = r.templates.find(t => t.id === r.default_id) || r.templates[0];
    const draw = () => {
      const text = fillTokens(cur.content, r.guest || {});
      panel.innerHTML = `<h3>💬 Điền tin vào khung chat Booking</h3>
        ${r.partner ? '<p><span class="ptag">🤝 Khách đặt qua đối tác — xin số Zalo/WhatsApp</span></p>' : ''}
        <p class="hint">Chọn mẫu → <b>Điền vào khung chat</b> → đọc lại rồi tự bấm <b>Gửi</b> của Booking. Tiện ích không tự gửi.
          Sửa mẫu ở web: menu 💬 Nhắn Khách.<br>📸 Ảnh đặt phòng để gửi khách: <b>chuột phải → Chụp ảnh đặt phòng</b> (hoặc Alt+Shift+S).</p>
        ${r.templates.map(t => `<button type="button" class="tpl ${t === cur ? 'on' : ''}" data-id="${esc(t.id)}">${esc(t.name)}</button>`).join('')}
        <pre class="pv">${esc(text)}</pre>
        <div class="row"><button class="close" id="b_close" type="button">Đóng</button>
          <button class="save" id="b_put" type="button">✍️ Điền vào khung chat</button></div>
        <div class="msg" id="msg"></div>`;
      panel.classList.add('open');
      $('#b_close').onclick = () => panel.classList.remove('open');
      root.querySelectorAll('.tpl').forEach(b => {
        b.onclick = () => { cur = r.templates.find(t => String(t.id) === b.dataset.id) || cur; draw(); };
      });
      $('#b_put').onclick = () => {
        const box = chatBox();
        if (!box) {
          const m = $('#msg'); m.className = 'msg err';
          m.textContent = '❌ Không thấy khung "Soạn tin nhắn" — mở phần "Trò chuyện với khách" trên trang rồi bấm lại.';
          return;
        }
        putInChat(box, text);
        panel.classList.remove('open');
        toast('✍️ Đã điền tin vào khung chat — đọc lại rồi bấm <b>Gửi</b> của Booking', 'ok');
      };
    };
    draw();
  });

  // ── 🤖 Trả lời AI: a reply for the conversation open on the screen ────────────────────
  // Reads ONLY the conversation already shown on this page (the column around Booking's message box) and the
  // booking number on it; the web adds what it knows about the guest and asks the AI. 🎤 = speak Vietnamese
  // (Chrome's speech recognition), the AI writes it as an English message. The text is only TYPED into Booking's
  // box — you read it and press Booking's own Gửi. Nothing is ever sent by the extension.
  const aiBtn = $('#ai');
  setInterval(() => { aiBtn.style.display = chatBox() ? '' : 'none'; }, 2000);
  function chatThread() {
    const box = chatBox();
    if (!box) return '';
    let el = box, best = null;
    while ((el = el.parentElement) && el !== document.body) {
      if (el.getBoundingClientRect().width > window.innerWidth * 0.75) break;   // stop before the whole page
      if ((el.innerText || '').length > 120) best = el;
    }
    return ((best || box.parentElement)?.innerText || '').slice(-6000);
  }
  function pageBookingNumber() {
    if (resId()) return resId();
    const t = fold(document.body.innerText || '');
    const m = t.match(/(?:so dat phong|ma dat phong|booking number|reservation number)[^0-9]{0,40}(\d{8,12})/);
    return m ? m[1] : '';
  }
  let aiState = { en: '', vi: '', note: '' };
  async function aiAsk(mode, viText) {
    const busy = root.querySelectorAll('#ai_again, #ai_tr, #ai_put');
    busy.forEach(b => { b.disabled = true; });
    const m = $('#ai_msg'); if (m) { m.className = 'msg'; m.textContent = mode === 'translate' ? '⏳ Đang viết thành tiếng Anh…' : '⏳ AI đang đọc tin nhắn…'; }
    const r = await api('/api/ext/ai_reply', { mode, vi: viText || '', thread: chatThread(), booking_id: pageBookingNumber() });
    busy.forEach(b => { b.disabled = false; });
    if (!r?.success) { if (m) { m.className = 'msg err'; m.textContent = '❌ ' + (r?.error || 'Lỗi không rõ'); } return; }
    aiState = { en: r.en, vi: r.vi, note: r.known ? `Khách có trên web (mã ${r.booking_id}) — AI dùng ngày, căn, địa chỉ của khách.`
                                               : 'Chưa thấy đặt phòng này trên web — AI chỉ dựa vào tin nhắn.' };
    drawAi();
  }
  function drawAi(keepVi) {
    const viDraft = keepVi ?? ($('#ai_vi')?.value || '');
    panel.innerHTML = `<h3>🤖 Trả lời khách bằng AI</h3>
      <p class="hint">AI đọc cuộc trò chuyện đang mở → gợi ý câu trả lời. Không ổn thì <b>🎤 nói</b> hoặc gõ ý của bạn bằng tiếng Việt
        → AI viết thành tiếng Anh. Bấm <b>Điền vào khung chat</b>, đọc lại rồi tự bấm <b>Gửi</b> của Booking.</p>
      <div class="ai-sec">✉️ Tin sẽ gửi (sửa được)</div>
      <textarea class="ai-ta" id="ai_en" placeholder="⏳ …">${esc(aiState.en)}</textarea>
      ${aiState.vi ? `<div class="ai-vi">🇻🇳 ${esc(aiState.vi)}</div>` : ''}
      ${aiState.note ? `<p class="hint" style="margin:6px 0 0">${esc(aiState.note)}</p>` : ''}
      <div class="ai-sec">🗣️ Ý của bạn (tiếng Việt)</div>
      <textarea class="ai-ta vi" id="ai_vi" placeholder="Ví dụ: ok bạn, 2h chiều tới là có phòng, tới nơi nhắn WhatsApp cho mình">${esc(viDraft)}</textarea>
      <div class="ai-row"><button type="button" id="ai_mic">🎤 Nói</button><button type="button" id="ai_tr">🇬🇧 Viết thành tiếng Anh</button></div>
      <div class="row"><button class="close" id="b_close" type="button">Đóng</button>
        <button class="close" id="ai_again" type="button">🔄 Gợi ý lại</button>
        <button class="save" id="ai_put" type="button">✍️ Điền vào khung chat</button></div>
      <div class="msg" id="ai_msg"></div>`;
    panel.classList.add('open');
    $('#b_close').onclick = () => { stopMic(); panel.classList.remove('open'); };
    $('#ai_again').onclick = () => aiAsk('suggest');
    $('#ai_tr').onclick = () => {
      const v = $('#ai_vi').value.trim();
      if (!v) { const m = $('#ai_msg'); m.className = 'msg err'; m.textContent = 'Nói hoặc gõ ý của bạn trước đã'; return; }
      stopMic(); aiAsk('translate', v);
    };
    $('#ai_put').onclick = () => {
      const text = $('#ai_en').value.trim(), box = chatBox(), m = $('#ai_msg');
      if (!text) { m.className = 'msg err'; m.textContent = 'Chưa có tin để điền'; return; }
      if (!box) { m.className = 'msg err'; m.textContent = '❌ Không thấy khung "Soạn tin nhắn" trên trang'; return; }
      stopMic(); putInChat(box, text); panel.classList.remove('open');
      toast('✍️ Đã điền tin vào khung chat — đọc lại rồi bấm <b>Gửi</b> của Booking', 'ok');
    };
    $('#ai_mic').onclick = toggleMic;
  }
  // 🎤 Chrome's own speech recognition (Vietnamese). Chrome asks once for the microphone.
  let rec = null;
  function stopMic() { if (rec) { try { rec.stop(); } catch (e) {} rec = null; } }
  function toggleMic() {
    const btn = $('#ai_mic');
    if (rec) { stopMic(); btn.classList.remove('rec'); btn.textContent = '🎤 Nói'; return; }
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { const m = $('#ai_msg'); m.className = 'msg err'; m.textContent = 'Trình duyệt này không nhận giọng nói — hãy gõ'; return; }
    const ta = $('#ai_vi'), before = ta.value.trim();
    rec = new SR(); rec.lang = 'vi-VN'; rec.continuous = true; rec.interimResults = true;
    rec.onresult = e => {
      let said = '';
      for (let i = 0; i < e.results.length; i++) said += e.results[i][0].transcript;
      ta.value = (before ? before + ' ' : '') + said.trim();
    };
    rec.onerror = e => {
      const m = $('#ai_msg');
      if (m && e.error !== 'no-speech' && e.error !== 'aborted') {
        m.className = 'msg err';
        m.textContent = e.error === 'not-allowed' ? '🎤 Chưa cho phép micro — bấm biểu tượng ổ khoá cạnh địa chỉ trang → Micro → Cho phép'
                                                  : '🎤 Lỗi micro: ' + e.error;
      }
    };
    rec.onend = () => { rec = null; const b = $('#ai_mic'); if (b) { b.classList.remove('rec'); b.textContent = '🎤 Nói'; } };
    rec.start();
    btn.classList.add('rec'); btn.textContent = '⏹ Dừng nói';
  }
  aiBtn.addEventListener('click', () => {
    aiState = { en: '', vi: '', note: '' };
    drawAi('');
    aiAsk('suggest');
  });

  // ── 📸 Screenshot of the reservation box ─────────────────────────────────────────────
  // Started from the toolbar icon, right-click menu or Alt+Shift+S (Chrome only allows a capture
  // right after you invoke the extension). Saves 2 versions: full (owner) + guest (internal parts covered).
  const MASK_LABELS = ['khoan co tinh hoa hong', 'hoa hong uoc tinh', 'ma iata', 'ghi chu (chi danh cho noi bo)',
                       'commissionable amount', 'commission', 'iata', 'internal note'];
  const R = el => el.getBoundingClientRect();
  const box = r => ({ left: r.left, top: r.top, right: r.right, bottom: r.bottom, width: r.right - r.left, height: r.bottom - r.top });
  const union = (a, b) => box({ left: Math.min(a.left, b.left), top: Math.min(a.top, b.top),
                                right: Math.max(a.right, b.right), bottom: Math.max(a.bottom, b.bottom) });
  const grow = (a, p) => box({ left: a.left - p, top: a.top - p, right: a.right + p, bottom: a.bottom + p });
  let pendingShot = null;

  function prepareShot(auto) {
    if (pendingShot) return { ok: false, error: 'busy' };
    const bid = resId();
    if (!bid) return { ok: false, error: 'Mở trang chi tiết của một đặt phòng rồi chụp lại' };
    const visibleLeaves = () => [...document.querySelectorAll('body *')]
      .filter(el => el.children.length === 0 && !host.contains(el) && el.getClientRects().length);
    const ft = el => fold(rawText(el));
    let leaves = visibleLeaves();
    const idLeaf = leaves.find(el => /^(ma so dat phong|booking number|reservation number)/.test(ft(el)));
    if (!idLeaf) return { ok: false, error: 'Không thấy khung thông tin đặt phòng trên trang này' };
    // The info box: smallest ancestor holding the check-in and the total, plus its own padding/border
    let card = idLeaf;
    while (card.parentElement && card.parentElement !== document.body) {
      const t = fold(card.innerText || '');
      if (/(nhan phong|check-in)/.test(t) && /(tong tien|total)/.test(t)) break;
      card = card.parentElement;
    }
    for (let p = card.parentElement; p && p !== document.body; p = p.parentElement) {
      const a = R(card), b = R(p);
      if (b.width <= a.width + 60 && b.height <= a.height + 80) card = p; else break;
    }
    // Put it near the top of the screen (instantly, so positions are final)
    const backTo = window.scrollY;
    window.scrollTo({ top: Math.max(0, R(card).top + window.scrollY - 70), behavior: 'instant' });
    leaves = visibleLeaves();
    const cardR = box(R(card));
    let area = cardR;
    const head = leaves.find(el => /^(chi tiet dat phong|reservation details|booking details)$/.test(ft(el)));
    if (head && R(head).bottom <= cardR.top + 2 && cardR.top - R(head).bottom < 140) area = union(area, R(head));
    // The room block under it ("Studio … VND 1.007.760" + dates)
    const price = leaves.find(el => /^vnd\s?[\d.,]+$/.test(ft(el)) && R(el).top > cardR.bottom - 5 && R(el).top < cardR.bottom + 420);
    if (price) {
      // climb to the whole room box: stop below the container that also holds the info box
      let blk = price;
      while (blk.parentElement && !blk.parentElement.contains(card) && R(blk.parentElement).height <= 450) blk = blk.parentElement;
      area = R(blk).height <= 450 ? union(area, R(blk))
        : union(area, { left: cardR.left, right: cardR.right, top: cardR.bottom, bottom: R(price).bottom + 70 });
    }
    area = grow(area, 10);
    if (head && R(head).top - 4 > area.top) area = box({ ...area, top: R(head).top - 4 });   // not the link line above the title
    // What the guest must not see: commission, IATA, internal notes, Booking's notices, partner box
    const masks = [];
    leaves.forEach(el => {
      const t = ft(el), r = R(el);
      if (r.bottom < area.top || r.top > area.bottom) return;
      if (MASK_LABELS.some(w => t.startsWith(w))) {
        const val = leaves.find(v => v !== el && R(v).top >= r.bottom - 3 && R(v).top - r.bottom < 40 &&
                                     R(v).left < r.right && R(v).right > r.left);
        masks.push(grow(val ? union(r, R(val)) : box(r), 3));
      } else if (/ban het|sold out/.test(t)) {
        // the notice row includes its ⓘ icon: climb while the text stays the same (icons add no text)
        // (start from the paragraph: the matched leaf is often the "…phòng đã bán hết" link at its end)
        let row = el.parentElement || el;
        const own = fold(row.innerText || row.textContent || '');
        while (row.parentElement && fold(row.parentElement.innerText || '') === own) row = row.parentElement;
        masks.push(grow(box(R(row)), 4));
      } else if (t === 'doi tac booking.com' || t === 'booking.com partner') {
        let blk = el;
        while (blk.parentElement && !/(cong ty hop tac|partner company|partners with)/.test(fold(blk.innerText || ''))) blk = blk.parentElement;
        if (R(blk).height < 260) masks.push(grow(box(R(blk)), 3));
      }
    });
    // Floating tooltips / popovers over the box (e.g. the mouse now rests on "Thanh toán của khách" after
    // the scroll) must not be in the picture: hide them for the capture only.
    const overlaps = r => r.right > area.left && r.left < area.right && r.bottom > area.top && r.top < area.bottom;
    const floating = [...document.querySelectorAll('[role="tooltip"], [class*="tooltip" i], [class*="popover" i]')]
      .filter(el => !host.contains(el) && !el.contains(card) && el.getClientRects().length &&
                    ['absolute', 'fixed'].includes(getComputedStyle(el).position) && overlaps(R(el)));
    floating.forEach(el => { el.dataset.hpVis = el.style.visibility; el.style.visibility = 'hidden'; });
    host.style.visibility = 'hidden';            // our own buttons must not appear in the picture
    setTimeout(() => { host.style.visibility = ''; restoreFloating(floating); }, 6000);   // never leave things hidden
    panel.classList.remove('open');
    pendingShot = { bid, area, masks, floating, auto: !!auto, backTo, vw: window.innerWidth, vh: window.innerHeight, cut: area.bottom > window.innerHeight };
    return { ok: true };
  }

  async function finishShot(dataUrl, method) {
    const p = pendingShot;
    pendingShot = null;
    try {
      if (!p) throw new Error('Hết thời gian — chụp lại nhé');
      let src, s, a, ox = 0, oy = 0;
      if (dataUrl) {
        src = await new Promise((res, rej) => {     // (img.decode() can stall in a background tab)
          const i = new Image();
          i.onload = () => res(i);
          i.onerror = () => rej(new Error('Ảnh chụp bị lỗi'));
          i.src = dataUrl;
        });
        s = src.width / p.vw;
        a = { left: Math.max(0, p.area.left), top: Math.max(0, p.area.top),
              right: Math.min(p.vw, p.area.right), bottom: Math.min(p.vh, p.area.bottom) };
      } else {
        // 1.48: no screen picture → draw the box from the page (positions are those of prepareShot: draw BEFORE
        // the page scrolls back). Not limited to the screen: a long box is never cut.
        src = await window.hpDomShot(p.area, host);
        s = src.width / p.area.width; a = p.area; ox = p.area.left; oy = p.area.top; p.cut = false;
      }
      restoreFloating(p.floating);
      window.scrollTo({ top: p.backTo, behavior: 'instant' });     // picture taken — page back where you were
      const make = masked => {
        const c = document.createElement('canvas');
        c.width = Math.round((a.right - a.left) * s);
        c.height = Math.round((a.bottom - a.top) * s);
        const x = c.getContext('2d');
        x.drawImage(src, (a.left - ox) * s, (a.top - oy) * s, c.width, c.height, 0, 0, c.width, c.height);
        if (masked) {
          x.fillStyle = '#ffffff';
          p.masks.forEach(m => x.fillRect((m.left - a.left) * s, (m.top - a.top) * s, m.width * s, m.height * s));
        }
        return c.toDataURL('image/jpeg', 0.9);
      };
      const full = make(false), guest = make(true);
      host.style.visibility = '';
      if (!p.auto) toast('📸 Đang lưu ảnh lên web…');
      const r = await api('/api/ext/booking/screenshot', { booking_id: p.bid, full, guest, method: dataUrl ? (method || 'screen') : 'dom' });
      if (!r?.success) throw new Error(r?.error || 'Lỗi không rõ');
      try { sessionStorage.setItem(shotStampKey(p.bid), String(Date.now())); } catch (e) {}
      if (p.auto) {
        if (lastPhoneToast) toast(lastPhoneToast + '<br>📸 Đã lưu luôn <b>ảnh đặt phòng</b> (bản gửi khách đã che hoa hồng)', 'ok');
        else toast('📸 Đã lưu ảnh đặt phòng', 'ok', 2500);
        return true;
      }
      $('#toast')?.remove();
      panel.innerHTML = `<h3>📸 Đã lưu ảnh đặt phòng #${esc(r.booking_id)}</h3>
        <p class="hint">Đây là bản <b>gửi khách</b> (đã che hoa hồng, IATA, ghi chú nội bộ). Bản đầy đủ cũng đã lưu để quản lý.
          ${r.on_web ? 'Trên điện thoại: <b>💬 Nhắn Khách</b> hoặc trang lịch → <b>📷 Ảnh</b> → Gửi.'
                     : '⚠️ Đặt phòng này chưa có trên web — bấm 📥 để thêm.'}
          ${p.cut ? '<br>⚠️ Khung dài hơn màn hình nên phần dưới bị cắt — thu nhỏ trang (Ctrl và phím −) rồi chụp lại.' : ''}</p>
        <img src="${guest}" alt="" style="width:100%;border-radius:10px;border:1px solid #e2e8f0">
        <div class="row"><button class="close" id="b_close" type="button">Đóng</button></div>`;
      panel.classList.add('open');
      $('#b_close').onclick = () => panel.classList.remove('open');
      return true;
    } catch (e) {
      host.style.visibility = '';
      if (p) { restoreFloating(p.floating); window.scrollTo({ top: p.backTo, behavior: 'instant' }); }
      toast('❌ Chụp ảnh: ' + esc(e.message), 'warn');
      return false;
    }
  }
  function cancelShot() {           // capture refused / failed: buttons back, page back
    host.style.visibility = '';
    if (pendingShot) {
      restoreFloating(pendingShot.floating);
      window.scrollTo({ top: pendingShot.backTo, behavior: 'instant' });
      pendingShot = null;
    }
  }
  function restoreFloating(list) {
    (list || []).forEach(el => {
      if (!('hpVis' in el.dataset)) return;
      el.style.visibility = el.dataset.hpVis;
      delete el.dataset.hpVis;
    });
  }

  chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
    if (msg?.type === 'shot-prepare') {
      try { reply(prepareShot(msg.auto)); } catch (e) { cancelShot(); reply({ ok: false, error: e.message }); }
    } else if (msg?.type === 'shot-image') {
      finishShot(msg.dataUrl, msg.method);
    } else if (msg?.type === 'shot-error') {
      cancelShot();
      toast((msg.auto ? '📸 Không tự chụp được ảnh: ' : '📸 ') + esc(msg.error), 'warn');
    }
    return false;
  });

  // ── ▶ Mở từng khách: owner decision 17/11/2026 ("tôi không sợ mất tài khoản") ──────────────
  // Only when the owner presses ▶: opens each guest of the visible list (e.g. "Khách đến") one by one at
  // human speed, saves the booking facts to the web, then the next one, then back to the list.
  // On each guest it also clicks "Hiển thị số điện thoại" (autoRevealTry, 1.23) and waits until the number is saved.
  const RUN_KEY = 'hp_run_queue';
  const runGet = () => { try { return JSON.parse(sessionStorage.getItem(RUN_KEY) || 'null'); } catch (e) { return null; } };
  const runSet = q => { try { q ? sessionStorage.setItem(RUN_KEY, JSON.stringify(q)) : sessionStorage.removeItem(RUN_KEY); } catch (e) {} };
  const wait = ms => new Promise(r => setTimeout(r, ms));
  const humanPause = () => wait(1000 + Math.random() * 1500);

  // Guest links of the list on screen: links whose text is a booking number, visible, one per number
  // Only what is really on screen: the other tabs ("Khách đi", "Lưu trú qua đêm") stay in the page, just hidden
  // (owner 17/11/2026: 3 guests showed, ▶ said 5).
  const hiddenTab = a => {
    if (a.checkVisibility && !a.checkVisibility({ opacityProperty: true, visibilityProperty: true, contentVisibilityAuto: true })) return true;
    const r = a.getBoundingClientRect();
    if (!r.width || !r.height) return true;
    for (let p = a.parentElement; p; p = p.parentElement) {
      if (p.hidden || p.getAttribute('aria-hidden') === 'true' || p.inert) return true;
      if (p.getAttribute('role') === 'tabpanel') return false;
    }
    return false;
  };
  // The list a guest link belongs to (the open tab's panel / list). Owner 17/11/2026: the button said 3 but
  // the confirm listed 5 (2 from "Khách đi") → only guests of the SAME list as the first one are taken.
  const listOf = a => a.closest('[role="tabpanel"], ul, ol, table, [role="list"], [role="table"], [role="grid"]') || a.ownerDocument.body;
  function guestLinks() {
    if (groupTable()) return [];                   // group overview: 8-digit property IDs are not guests
    const arr = arrivalsToday();                   // a property's home: only "Khách đến · Hôm nay" (1.27)
    if (arr) return arr.items;
    const seen = new Set(), out = [];
    let list = null;
    for (const doc of allDocs()) {
      doc.querySelectorAll('a[href]').forEach(a => {
        const n = rawText(a);
        if (!BID_RE.test(n) || a.offsetParent === null || host.contains(a) || hiddenTab(a)) return;
        const l = listOf(a);
        if (!list) list = l; else if (l !== list) return;
        if (seen.has(n.trim())) return;
        seen.add(n.trim());
        out.push({ bid: n.trim(), url: a.href });
      });
    }
    return out;
  }

  // ── 🏢 Trang tổng quan nhiều chỗ nghỉ (ext 1.25, owner 17/11/2026) ─────────────────────────────
  // Sau khi đăng nhập Booking đưa về bảng "Chỗ nghỉ | … | Đến trong 48 giờ tới …". Lấy các căn có số khách đến > 0
  // (đọc không ra cột đó → lấy mọi căn), mở lần lượt trang chủ từng căn → "▶ Mở từng khách" trên danh sách
  // "Khách đến" của căn đó → xong thì sang căn kế tiếp → cuối cùng quay về trang tổng quan, báo tổng kết.
  // Hàng đợi căn: sessionStorage 'hp_group_queue' {props, i, back, ok, total, bad, auto}; props[i].started = đã chạy.
  const GROUP_KEY = 'hp_group_queue';
  // the overview of ALL the account's properties ("Tổng quan hôm nay" + table). background.js opens it at 7:00.
  const GROUP_URL = 'https://admin.booking.com/hotel/hoteladmin/groups/home/index.html';
  // 1.31: name of this profile's Booking account (popup), put in the Zalo messages
  const hpAccount = async () => { try { return (await chrome.storage.local.get('hpAccount')).hpAccount || ''; } catch (e) { return ''; } };
  const groupGet = () => { try { return JSON.parse(sessionStorage.getItem(GROUP_KEY) || 'null'); } catch (e) { return null; } };
  const groupSet = g => { try { g ? sessionStorage.setItem(GROUP_KEY, JSON.stringify(g)) : sessionStorage.removeItem(GROUP_KEY); } catch (e) {} };
  const gCells = row => [...row.querySelectorAll(':scope > th, :scope > td, :scope > [role="cell"], :scope > [role="columnheader"], :scope > [role="rowheader"], :scope > [role="gridcell"]')];
  // The overview table = the one whose header has "Đến trong 48 giờ" (or "arrivals in the next 48").
  function groupTable() {
    if (resId()) return null;
    for (const doc of allDocs()) {
      for (const h of doc.querySelectorAll('th, [role="columnheader"]')) {
        const t = fold(rawText(h));
        if (/den trong 48|arriv\w* .*48|check-?ins? .*48/.test(t) && !host.contains(h)) {
          const tbl = h.closest('table, [role="table"], [role="grid"]');
          if (tbl) return { tbl, head: h };
        }
      }
    }
    return null;
  }
  function groupProps() {
    const g = groupTable();
    if (!g) return null;
    const headRow = g.head.closest('tr, [role="row"]');
    const col = headRow ? gCells(headRow).indexOf(g.head) : -1;
    const out = [], seen = new Set();
    // 1.34 (owner 17/11/2026, 19 Thọ Nhuộm overview "đơ"): the header and the rows can be two separate tables (sticky
    // header + scrolling body) → look for the rows in the smallest box around the header table that has a row
    // starting with a property ID.
    const hasIdRow = el => [...el.querySelectorAll('tr, [role="row"]')].some(r => r !== headRow &&
      /^\s*\d{5,10}\b/.test(rawText(gCells(r)[0] || r)));
    let box = g.tbl;
    for (let k = 0; k < 6 && box.parentElement && !hasIdRow(box); k++) box = box.parentElement;
    box.querySelectorAll('tr, [role="row"]').forEach(row => {
      if (row === headRow) return;
      const cells = gCells(row);
      if (cells.length < 2) return;
      const id = (rawText(cells[0]).match(/\b\d{5,10}\b/) || [])[0];
      if (!id || seen.has(id)) return;
      seen.add(id);
      const name = (cells[1].innerText || rawText(cells[1])).split('\n')[0].trim() || id;
      // Arrivals count: the text in this row that sits UNDER the "Đến trong 48 giờ tới" header (by position on the
      // page — 1.27: reading by cell index gave nothing on the real page, so every property was visited)
      let n = numUnder(row, g.head);
      if (n < 0 && col >= 0 && cells[col]) { const m = rawText(cells[col]).match(/^\s*(\d+)\s*$/); if (m) n = +m[1]; }
      const closed = /dong \/ khong the dat|khong the dat phong|closed|not bookable/.test(fold(rawText(row)));
      const links = [...row.querySelectorAll('a[href]')].filter(a => !host.contains(a));
      const a = links.find(x => new RegExp('hotel_id=' + id + '\\b').test(x.href)) ||
        links.find(x => /hotel_id=/.test(x.href) && !/reservation|message|review|inbox|status/i.test(x.href));
      let url = a ? a.href : '';
      if (!url) {
        const ses = new URL(location.href).searchParams.get('ses');
        url = `https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/home.html?hotel_id=${id}&lang=vi` + (ses ? '&ses=' + encodeURIComponent(ses) : '');
      }
      out.push({ id, name, n, closed, url });
    });
    return out;
  }
  // The number shown in `row` straight below `head` (overlapping its left–right span). -1 = none.
  function numUnder(row, head) {
    const h = head.getBoundingClientRect();
    if (!h.width) return -1;
    for (const el of row.querySelectorAll('*')) {
      if (el.children.length) continue;               // leaf elements only (the "2" in its blue circle)
      const t = rawText(el);
      if (!/^\d{1,3}$/.test(t)) continue;
      const r = el.getBoundingClientRect();
      if (!r.width) continue;
      const cx = (r.left + r.right) / 2;
      if (cx >= h.left - 4 && cx <= h.right + 4) return +t;
    }
    return -1;
  }
  // Visit: count > 0. Count 0 → skip. Count unreadable → visit unless the property is closed
  // (its home page then checks "Khách đến · Hôm nay" itself and leaves at once when it is 0).
  const groupPick = props => props.filter(p => p.n > 0 || (p.n < 0 && !p.closed));

  // ── "Đặt phòng · Hôm nay · Khách đến N" box on a property's home page (1.27) ──────────────────────
  // Only TODAY's arrivals: the guest links inside the "Khách đến" tab's panel. Owner 17/11/2026: the run opened a
  // guest arriving 21/10 (a link from another box of the page) and visited properties with "Khách đến 0".
  // null = the box is not on the page (yet); { n, items } otherwise (n = the tab's badge number, -1 unknown).
  function arrivalsToday() {
    for (const doc of allDocs()) {
      const tab = [...doc.querySelectorAll('[role="tab"], button, a, li')].find(el =>
        !host.contains(el) && el.offsetParent !== null && /^khach den\s*\d*$|^arrivals?\s*\d*$/.test(fold(rawText(el)).replace(/\s+/g, ' ').trim()));
      if (!tab) continue;
      const m = rawText(tab).match(/(\d+)\s*$/);
      const n = m ? +m[1] : -1;
      // the tab's own panel, else the box around the tab bar (the "Đặt phòng" card)
      let panel = null;
      const pid = tab.getAttribute('aria-controls') || tab.querySelector('[aria-controls]')?.getAttribute('aria-controls');
      if (pid) panel = doc.getElementById(pid);
      if (!panel) {
        const bar = tab.closest('[role="tablist"], ul, nav') || tab.parentElement;
        for (let a = bar; a && a !== doc.body; a = a.parentElement) {
          if (/xem tat ca dat phong|view all reservations|khong co khach den/.test(fold(rawText(a))) || a.querySelector('table, [role="table"], [role="tabpanel"]')) { panel = a; break; }
        }
      }
      if (!panel) return { n, items: [] };
      const seen = new Set(), items = [];
      panel.querySelectorAll('a[href]').forEach(a => {
        const b = rawText(a).trim();
        if (!BID_RE.test(b) || a.offsetParent === null || hiddenTab(a) || seen.has(b)) return;
        seen.add(b); items.push({ bid: b, url: a.href });
      });
      // a selected-but-other tab (Khách đi…) would show its own list: only trust links while "Khách đến" is selected
      if (tab.getAttribute('aria-selected') === 'false') return { n, items: [] };
      return { n, items };
    }
    return null;
  }
  // "Vào: A (2), B (1) · Bỏ qua: C (0), D (đóng)" — what was read from the overview, shown before leaving it
  const groupSummary = all => {
    const go = groupPick(all), skip = all.filter(p => !go.includes(p));
    const lab = p => `${esc(p.name)} (${p.n >= 0 ? p.n : '?'}${p.closed ? ', đóng' : ''})`;
    return `Vào: ${go.map(lab).join(', ') || '—'}` + (skip.length ? `<br>Bỏ qua: ${skip.map(lab).join(', ')}` : '');
  };
  async function startGroup(props, auto, all) {
    groupSet({ props, i: 0, back: location.href, ok: 0, total: 0, bad: [], auto: !!auto });
    toast(`🏢 Đến trong 48 giờ — ${groupSummary(all || props)}`, 'ok', 6000);
    // 1.30: the Zalo booking bot tells the owner the PC is running and which properties (owner, Nov 17)
    if (auto) {
      morningGo();
      const lab = p => p.name + (p.n > 0 ? ` (${p.n})` : '');
      const skip = (all || props).filter(p => !props.includes(p)).map(p => lab(p) + (p.closed ? ' đóng' : ''));
      api('/api/ext/morning', { stage: 'start', go: props.map(lab), skip, account: await hpAccount() }).catch(() => {});
    }
    await wait(4000);                               // let the owner see what was picked
    const g = groupGet();
    if (g && g.i === 0 && !runGet()) location.href = props[0].url;
  }
  async function stopGroup(note) {
    const g = groupGet();
    if (!g) return;
    groupSet(null);
    try { sessionStorage.setItem('hp_group_done', JSON.stringify({ note, ok: g.ok, total: g.total, bad: g.bad, n: g.props.length })); } catch (e) {}
    if (g.auto) {                                   // 1.30: "✅ Xong: đã lưu x/y" on Zalo (wait ≤ 4 s before leaving the page)
      await Promise.race([api('/api/ext/morning', { stage: 'done', ok: g.ok, total: g.total, bad: g.bad.slice(0, 10), account: await hpAccount(),
        note: /^⚠️/.test(note || '') ? note : /dừng/.test(note || '') ? 'Đã bị dừng giữa chừng.' : '' }).catch(() => {}), wait(4000)]);
    }
    location.href = g.back;
  }
  function showGroupDone() {
    let d = null;
    try { d = JSON.parse(sessionStorage.getItem('hp_group_done') || 'null'); sessionStorage.removeItem('hp_group_done'); } catch (e) {}
    if (!d) return;
    toast(`🏢 ${esc(d.note || '✅ Xong.')} Đã xem ${d.n} căn · lưu <b>${d.ok}/${d.total}</b> khách về Hotel Pro.` +
      (d.bad.length ? `<br>Chưa lưu được: ${d.bad.map(b => `${esc(b.bid)} (${esc(b.why)})`).join(', ')}` : ''),
      d.bad.length ? 'warn' : 'ok', 30000);
  }
  // On a property's home page while the group queue is active: run its "Khách đến" list, or move on.
  // 1.38: today's morning run really began (background.js retries the morning until this is set)
  const morningGo = () => chrome.storage.local.set({ hpMorningGo: new Date().toLocaleDateString('sv') }).catch(() => {});
  async function groupStep() {
    const g = groupGet();
    if (!g || runGet() || resId()) return;
    chrome.storage.local.set({ hpRunBusy: Date.now() }).catch(() => {});
    if (g.auto) morningGo();
    const p = g.props[g.i];
    if (!p) { stopGroup('✅ Xong.'); return; }
    if (p.started) {                                // its guests are done (finishRun brought us back here)
      g.i += 1; groupSet(g);
      await wait(2500);                             // let the "Đã lưu x/y" toast be seen
      if (!groupGet()) return;
      if (g.i >= g.props.length) stopGroup('✅ Xong.'); else location.href = g.props[g.i].url;
      return;
    }
    toast(`🏢 Căn ${g.i + 1}/${g.props.length}: <b>${esc(p.name)}</b> — đang xem khách đến hôm nay…`, 'ok', 5000);
    for (let t = 0; t < 14 && groupGet(); t++) {    // the home page draws the "Khách đến" box after loading
      const a = arrivalsToday();
      if (a && a.items.length) {
        p.started = true; groupSet(g);
        startRun(a.items);
        return;
      }
      if (a && a.n === 0 && t >= 1) break;          // "Khách đến 0" (seen twice) → next property at once
      await wait(1500);
    }
    if (!groupGet()) return;
    p.started = true; groupSet(g);                  // no guest link on this page → next property
    groupStep();
  }

  const runBtn = document.createElement('button');
  runBtn.className = 'fab fab2'; runBtn.type = 'button'; runBtn.style.display = 'none';
  root.insertBefore(runBtn, $('#ai'));
  function refreshRunBtn() {
    const q = runGet();
    if (q) { runBtn.textContent = `⏹ Dừng (${Math.min(q.i + 1, q.items.length)}/${q.items.length})`; runBtn.style.display = ''; return; }
    const g = groupGet();
    if (g) { runBtn.textContent = `⏹ Dừng (căn ${Math.min(g.i + 1, g.props.length)}/${g.props.length})`; runBtn.style.display = ''; return; }
    if (resId()) { runBtn.style.display = 'none'; return; }
    const gp = groupProps();
    if (gp) {
      const k = groupPick(gp).length;
      runBtn.textContent = `▶ Các căn có khách đến (${k})`;
      runBtn.style.display = k ? '' : 'none';
      return;
    }
    const n = guestLinks().length;
    runBtn.textContent = `▶ Mở từng khách (${n})`;
    runBtn.style.display = n ? '' : 'none';
  }
  setInterval(refreshRunBtn, 2000);

  // ── 💬 Hỏi thăm khách (owner, Nov 19 2026): its OWN button, separate from 📥 Gửi về Hotel Pro ──
  // On a reservations list ("Mã số đặt phòng" table): one click = save guests the web does not have yet, send the
  // booking numbers of this table (not cancelled) → /moi Nhắn khách › Đã trả phòng shows only these guests. Reads the page only.
  const askBtn = document.createElement('button');
  askBtn.className = 'fab'; askBtn.type = 'button'; askBtn.style.cssText = 'display:none;background:#7c3aed;margin-right:8px';
  root.insertBefore(askBtn, $('#ai'));
  let askBusy = false;
  const askRows = () => { try { const l = captureList(); return l && (l.headers.some(isHeaderText) || l.rows.length >= 2) ? l : null; } catch (e) { return null; } };
  setInterval(() => {
    if (askBusy) return;
    const l = !runGet() && !groupGet() && !resId() && guestLinks().length ? askRows() : null;
    askBtn.style.display = l ? '' : 'none';
    if (l) askBtn.textContent = `💬 Hỏi thăm khách (${l.rows.length})`;
  }, 2000);
  askBtn.addEventListener('click', async () => {
    if (askBusy) return; askBusy = true;
    try {
      askBtn.textContent = '⏳ Đang đọc bảng...';
      const l = askRows(); if (!l) { toast('❌ Không đọc được bảng đặt phòng trên trang này.', 'warn'); return; }
      const r = await api('/api/ext/booking/parse', l);
      if (!r?.success || r.mode !== 'list') { toast('❌ ' + esc(r?.error || 'Không đọc được bảng'), 'warn'); return; }
      const items = (r.items || []).filter(it => it.status !== 'cancelled' && it.action !== 'skip_cancelled' && it.booking_id);
      if (!items.length) { toast('Không có khách nào (tất cả đã hủy).', 'warn'); return; }
      // 1.46 (owner Nov 21: "Hỏi thăm chỉ để nhắn tin thôi, đâu phải lấy thông tin đặt phòng"): this button ONLY sends
      // the booking numbers. It never saves / changes a booking (1.4x saved new + changed rows → it overwrote prices,
      // dates and room names of ~40 guests and added old guests without picture/phone). Saving = 📥 Gửi về Hotel Pro.
      askBtn.textContent = '⏳ Đang gửi danh sách...';
      const o = await api('/api/ext/out_list', { ids: [...new Set(items.map(it => String(it.booking_id).split('-')[0]))] });
      if (!o?.success) { toast('❌ ' + esc(o?.error || 'Lỗi không rõ'), 'warn'); return; }
      // owner, Nov 19: on the PC it only SAVES the list — the owner sends the messages later from the phone
      toast(`✅ Đã gửi ${o.n} khách sang <b>Nhắn khách › Đã trả phòng</b> — mở trên điện thoại để nhắn.` +
        (o.found < o.n ? `<br>${o.n - o.found} khách chưa có trên web (không hiện trong danh sách nhắn).` : ''), 'ok', 10000);
    } finally { askBusy = false; askBtn.textContent = '💬 Hỏi thăm khách'; }
  });
  // ── 📅 Lấy cả tháng (1.55, owner Nov 25: "lấy khách ở phần Đặt phòng … Nhận phòng, từ ngày hiện tại đến cuối tháng,
  // tình trạng OK, lấy toàn bộ") ── reads Booking's reservation LIST, every page ("Tiếp theo"), and sends the rows to
  // /api/ext/month_sync, which ADDS only the guests the web does not have (never changes existing ones). Reads the page
  // only: no reservation opened, no phone revealed. Its own button (one button = one job) + once a day by itself.
  const isResList = () => /search_reservations/.test(location.pathname);
  function nextPageBtn() {
    for (const doc of allDocs()) {
      const el = [...doc.querySelectorAll('button, a, [role="button"]')].find(b => /^(tiếp theo|next)\b/i.test(rawText(b).trim()));
      if (el) {
        const off = el.disabled || el.getAttribute('aria-disabled') === 'true' || /disabled/i.test(String(el.className || ''))
          || el.closest('[aria-disabled="true"], [disabled], [class*="disabled" i]');
        return off ? null : el;
      }
    }
    return null;
  }
  const firstBid = l => { try { return (JSON.stringify(l.rows[0] || '').match(/\d{9,11}/) || [''])[0]; } catch (e) { return ''; } };
  async function readAllPages(waitS) {
    const pages = [];
    let cap = null;
    for (let t = 0; t < waitS && !(cap = askRows()); t++) await wait(1000);
    if (!cap) return { pages, complete: false };
    while (cap && pages.length < 15) {
      pages.push(cap);
      const nx = nextPageBtn();
      if (!nx) return { pages, complete: true };
      const was = firstBid(cap);
      nx.click();
      let moved = null;
      for (let t = 0; t < 20 && !moved; t++) { await wait(800); const c = askRows(); if (c && firstBid(c) && firstBid(c) !== was) moved = c; }
      if (!moved) return { pages, complete: false };
      await wait(700);
      cap = askRows() || moved;
    }
    return { pages, complete: false };
  }
  const monthUrl = (hid, ses, job) => 'https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/search_reservations.html'
    + `?upcoming_reservations=1&source=nav&hotel_id=${hid}&lang=vi&ses=${encodeURIComponent(ses)}`
    + `&date_type=arrival&date_from=${job.from}&date_to=${job.to}&reservation_status=ok`;
  const monthToast = r => `✅ Đọc ${r.rows} khách OK · <b>thêm mới ${r.created.length}</b> vào lịch · ${r.had} khách đã có (giữ nguyên)`
    + (r.created.length ? '<br>' + r.created.slice(0, 8).map(x => esc(x.name) + ' · ' + esc(String(x.ci).slice(8, 10) + '/' + String(x.ci).slice(5, 7))).join('<br>') : '')
    + (r.gone?.length ? `<br>⚠️ ${r.gone.length} khách trong app không còn OK trên Booking: ` + r.gone.slice(0, 5).map(x => esc(x.name)).join(', ') : '');
  const monBtn = document.createElement('button');
  monBtn.className = 'fab'; monBtn.type = 'button'; monBtn.style.cssText = 'display:none;background:#0f766e;margin-right:8px';
  root.insertBefore(monBtn, askBtn);
  let monBusy = false;
  setInterval(() => {
    if (monBusy) return;
    const show = isResList() && !runGet() && !groupGet() && !!askRows();
    monBtn.style.display = show ? '' : 'none';
    if (show) monBtn.textContent = '📅 Lưu cả danh sách vào lịch';
  }, 2000);
  monBtn.addEventListener('click', async () => {
    if (monBusy) return; monBusy = true;
    try {
      monBtn.textContent = '⏳ Đang đọc từng trang...';
      const { pages, complete } = await readAllPages(5);
      if (!pages.length) { toast('❌ Không đọc được bảng đặt phòng trên trang này.', 'warn'); return; }
      const q = new URL(location.href).searchParams, arr = q.get('date_type') === 'arrival';
      monBtn.textContent = `⏳ Đang lưu ${pages.length} trang...`;
      const r = await api('/api/ext/month_sync', { pages, account: await hpAccount(), complete: complete && arr,
        date_from: arr ? q.get('date_from') || '' : '', date_to: arr ? q.get('date_to') || '' : '' });
      if (!r?.success) { toast('❌ ' + esc(r?.error || 'Lỗi không rõ'), 'warn'); return; }
      toast(monthToast(r) + (complete ? '' : '<br>(chưa đọc hết các trang — bấm lại)'), r.gone?.length ? 'warn' : 'ok', 15000);
    } finally { monBusy = false; monBtn.textContent = '📅 Lưu cả danh sách vào lịch'; }
  });
  async function monthJob() {
    if (!chrome.runtime?.id) return;
    let job = null;
    try { job = await chrome.runtime.sendMessage({ type: 'month-job' }); } catch (e) {}
    if (!job || !job.hotels?.length) return;
    await wait(2500);
    // owner Nov 25: "đang lấy lịch của những căn hộ đã đóng cửa rồi" → first stop = the group overview: keep only the
    // properties that are NOT "Đóng / Không thể đặt phòng" (an account with one property has no overview → kept as is)
    if (!job.checked) {
      const ses0 = new URL(location.href).searchParams.get('ses') || '';
      let went = ''; try { went = sessionStorage.getItem('hp_month_grp') || ''; } catch (e) {}
      if (!/\/groups\//.test(location.pathname) && went !== job.day) {     // once: go to the overview (one property = no overview)
        try { sessionStorage.setItem('hp_month_grp', job.day); } catch (e) {}
        location.href = 'https://admin.booking.com/hotel/hoteladmin/groups/home/index.html' + (ses0 ? '?ses=' + encodeURIComponent(ses0) : '');
        return;
      }
      let gp = null;
      for (let t = 0; t < 12 && !(gp = groupProps()); t++) await wait(1000);
      try { job = await chrome.runtime.sendMessage({ type: 'month-hotels', open: gp ? gp.filter(p => !p.closed).map(p => p.id) : null,
        closed: gp ? gp.filter(p => p.closed).map(p => p.id) : [] }); } catch (e) { return; }
      if (!job) return;
      if (!job.hotels.length) { finishMonth(job); return; }
    }
    const u = new URL(location.href), ses = u.searchParams.get('ses') || '';
    const hid = job.hotels[job.i];
    if (!hid) { finishMonth(job); return; }
    if (!isResList() || u.searchParams.get('hotel_id') !== hid || u.searchParams.get('date_from') !== job.from) {
      if (ses) location.href = monthUrl(hid, ses, job);      // no session yet = sign-in page: Tampermonkey signs in first
      return;
    }
    toast(`📅 Đang lấy khách hôm nay + ngày mai · chỗ nghỉ ${job.i + 1}/${job.hotels.length} · ${esc(job.from)} → ${esc(job.to)}`, 'ok', 5000);
    const { pages, complete } = await readAllPages(20);
    let r = null;
    try { r = await api('/api/ext/month_sync', { pages, date_from: job.from, date_to: job.to, account: await hpAccount(), complete }); } catch (e) {}
    let nx = null;
    try { nx = await chrome.runtime.sendMessage({ type: 'month-step', created: r?.created || [], gone: r?.gone || [], rows: r?.rows || 0 }); } catch (e) {}
    if (nx && nx.hotels[nx.i]) { await wait(1500 + Math.random() * 1500); location.href = monthUrl(nx.hotels[nx.i], ses, nx); return; }
    finishMonth(nx || job);
  }
  async function finishMonth(job) {
    await Promise.race([api('/api/ext/month_report', { account: await hpAccount(), created: job.created || [], gone: job.gone || [],
      rows: job.rows || 0, date_from: job.from, date_to: job.to }).catch(() => {}), wait(8000)]);
    chrome.runtime.sendMessage({ type: 'month-done' }).catch(() => {});
  }
  function startRun(items) {
    runSet({ items, i: 0, back: location.href, log: [] });
    location.href = items[0].url;
  }
  runBtn.addEventListener('click', () => {
    if (runGet() || groupGet()) {
      if (groupGet()) { runSet(null); stopGroup('⏹ Đã dừng.'); } else finishRun('⏹ Đã dừng.');
      return;
    }
    const gp = groupProps();
    if (gp) {
      const pick = groupPick(gp);
      if (!pick.length) return;
      if (!confirm(`Mở lần lượt ${pick.length} căn có khách đến, ở mỗi căn mở từng khách, bấm "Hiển thị số điện thoại" và lưu về Hotel Pro?\n\n` +
        pick.map(p => `• ${p.name}` + (p.n > 0 ? ` (${p.n})` : '')).join('\n'))) return;
      startGroup(pick, false, gp);
      return;
    }
    const items = guestLinks();
    if (!items.length) return;
    if (!confirm(`Tự mở lần lượt ${items.length} khách trên danh sách này, bấm "Hiển thị số điện thoại" và lưu về Hotel Pro?\n\nMã đặt phòng: ${items.map(x => x.bid).join(', ')}`)) return;
    startRun(items);
  });

  function finishRun(note) {
    const q = runGet();
    runSet(null);
    if (!q) return;
    const ok = q.log.filter(l => l.ok).length;
    const bad = q.log.filter(l => !l.ok);
    const g = groupGet();
    if (g) { g.ok += ok; g.total += q.items.length; g.bad.push(...bad); groupSet(g); }
    try { sessionStorage.setItem('hp_run_done', JSON.stringify({ note, ok, total: q.items.length, bad })); } catch (e) {}
    try {
      if (sessionStorage.getItem('hp_fetch')) sessionStorage.setItem('hp_fetch_result',
        JSON.stringify({ ok: q.log.filter(l => l.ok).map(l => l.bid), bad, note }));
    } catch (e) {}
    if (location.href !== q.back) location.href = q.back; else { showRunDone(); fetchJob(); }
  }
  function showRunDone() {
    let d = null;
    try { d = JSON.parse(sessionStorage.getItem('hp_run_done') || 'null'); sessionStorage.removeItem('hp_run_done'); } catch (e) {}
    if (!d) return;
    toast(`${esc(d.note || '✅ Xong.')} Đã lưu <b>${d.ok}/${d.total}</b> khách về Hotel Pro.` +
      (d.bad.length ? `<br>Chưa lưu được: ${d.bad.map(b => `${esc(b.bid)} (${esc(b.why)})`).join(', ')}` : ''),
      d.bad.length ? 'warn' : 'ok', 20000);
  }

  // the guest's address with the session of THIS page (after a new sign-in the old `ses` is no longer valid)
  function withSes(url) {
    try {
      const ses = new URL(location.href).searchParams.get('ses'), u = new URL(url);
      if (ses) u.searchParams.set('ses', ses);
      return u.href;
    } catch (e) { return url; }
  }
  async function logoutLoop() {
    const q = runGet();
    let r = null;
    try { r = await chrome.runtime.sendMessage({ type: 'logout-loop' }); } catch (e) {}
    const note = r?.reset
      ? '⚠️ Booking tự đăng xuất mỗi lần mở chi tiết khách → máy đã tự xóa TOÀN BỘ cookie + dữ liệu web của hồ sơ Chrome này, đăng nhập lại và chạy lại (Booking có thể hỏi mã SMS qua Zalo).'
      : r?.paused
        ? '⛔ Booking vẫn tự đăng xuất mỗi lần mở chi tiết khách (đã tự xóa toàn bộ dữ liệu mà không hết) → máy TẠM DỪNG tự mở khách 6 tiếng. Thử tay: chrome://settings/clearBrowserData → Mọi lúc → xóa → đăng nhập lại.'
        : '⚠️ Booking tự đăng xuất mỗi lần mở chi tiết khách (hôm nay đã tự sửa 1 lần). Cần anh: chrome://settings/clearBrowserData → Mọi lúc → xóa → đăng nhập lại.';
    if (q) q.items.slice(q.i).forEach(x => q.log.push({ bid: x.bid, ok: false, why: 'Booking đăng xuất' }));
    const g = groupGet();
    if (g && q) {
      g.ok += q.log.filter(l => l.ok).length; g.total += q.items.length; g.bad.push(...q.log.filter(l => !l.ok)); groupSet(g);
      runSet(null); stopGroup(note);
    } else if (q) { runSet(q); finishRun(note); }
  }
  // 📥 1.36 Khách đặt trong ngày (owner 18/11/2026): background.js opened this tab for the new guests of today that the
  // server got from Booking's mails → open each reservation (same run as "▶ Mở từng khách": save + phone), then one
  // Zalo line and the tab closes.
  async function fetchJob() {
    if (!chrome.runtime?.id) return;
    let job = null;
    try { job = await chrome.runtime.sendMessage({ type: 'fetch-job' }); } catch (e) {}
    if (!job || !job.items?.length) return;
    let res = null;
    try { res = JSON.parse(sessionStorage.getItem('hp_fetch_result') || 'null'); } catch (e) {}
    if (res) {
      try { sessionStorage.removeItem('hp_fetch_result'); } catch (e) {}
      await Promise.race([api('/api/ext/pending', { action: 'report', ok: res.ok, bad: res.bad, note: res.note, account: await hpAccount() })
        .catch(() => {}), wait(8000)]);
      chrome.runtime.sendMessage({ type: 'fetch-done' }).catch(() => {});
      return;
    }
    try { if (sessionStorage.getItem('hp_fetch')) return; } catch (e) {}
    await wait(2500);                                // the overview after the sign-in redirects carries `ses`
    if (runGet() || resId()) return;
    const ses = new URL(location.href).searchParams.get('ses') || '';
    const items = job.items.map(x => ({ bid: x.bid,
      url: `https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/booking.html?hotel_id=${x.hotel_id}&lang=vi` +
        (ses ? '&ses=' + encodeURIComponent(ses) : '') + `&res_id=${x.bid}&source=homepage` }));
    try { sessionStorage.setItem('hp_fetch', '1'); } catch (e) {}
    toast(`📥 Khách mới đặt hôm nay: ${items.map(i => esc(i.bid)).join(', ')} — đang mở…`, 'ok', 5000);
    await wait(1500);
    startRun(items);
  }
  // 📩 1.58 Hỏi WhatsApp từ điện thoại (owner, Nov 27): background.js opened this tab for ONE guest the owner tapped on
  // /moi → open that reservation, type the 'Xin số …' message into Booking's chat box, press Booking's Gửi, check the
  // box emptied, report /api/ext/chat_done (→ Zalo) and the tab closes. Only the message box itself (placeholder /
  // label says message) is used — never another text field of the page.
  function chatBoxStrict() {
    const cands = [...document.querySelectorAll('textarea, [contenteditable="true"], [role="textbox"]')]
      .filter(el => !host.contains(el) && el.offsetParent !== null);
    const hint = el => fold([el.getAttribute('placeholder'), el.getAttribute('aria-label'), el.getAttribute('data-placeholder'),
      el.getAttribute('name'), el.id].join(' '));
    return cands.find(el => /soan tin nhan|tin nhan|message|reply|tra loi/.test(hint(el)) && !/ghi chu|note|remark/.test(hint(el))) || null;
  }
  function chatOpenSection() {
    const els = [...document.querySelectorAll('button, a, [role="button"], [role="tab"]')].filter(el => !host.contains(el) && el.offsetParent !== null);
    const el = els.find(e => /tro chuyen voi khach|nhan tin cho khach|gui tin nhan cho khach|message guest|message the guest/.test(fold(e.textContent + ' ' + (e.getAttribute('aria-label') || ''))));
    if (el) el.click();
    return !!el;
  }
  function chatSendBtn(box) {
    const ok = el => !host.contains(el) && el.offsetParent !== null && !el.disabled && el.getAttribute('aria-disabled') !== 'true';
    const isSend = el => /^(gui|send)$|gui tin nhan|^gui tin|send message/.test(fold((el.textContent || '').trim() + ' ' + (el.getAttribute('aria-label') || '')).trim());
    if (box.form) { const b = [...box.form.querySelectorAll('button')].find(b => ok(b) && (isSend(b) || b.type === 'submit')); if (b) return b; }
    let p = box.parentElement;
    for (let i = 0; i < 8 && p; i++, p = p.parentElement) {
      const b = [...p.querySelectorAll('button, [role="button"]')].find(b => ok(b) && isSend(b));
      if (b) return b;
    }
    return null;
  }
  async function chatJob() {
    if (!chrome.runtime?.id) return;
    let job = null;
    try { job = await chrome.runtime.sendMessage({ type: 'chat-job' }); } catch (e) {}
    if (!job) return;
    const key = 'hp_chat_' + job.job;
    try { if (sessionStorage.getItem(key + '_busy')) return; } catch (e) {}
    const done = async (ok, why, extra = {}) => {
      await Promise.race([api('/api/ext/chat_done', { job: job.job, ok, why, ...extra }).catch(() => {}), wait(8000)]);
      try { sessionStorage.removeItem(key); sessionStorage.removeItem(key + '_busy'); } catch (e) {}
      toast(ok ? '✅ Đã nhắn hỏi WhatsApp' : '⚠️ Chưa nhắn được: ' + esc(why), ok ? 'ok' : 'err', 4000);
      chrome.runtime.sendMessage({ type: 'chat-done' }).catch(() => {});
    };
    if (resId() !== String(job.bid)) {
      let n = 0;
      try { n = +(sessionStorage.getItem(key) || 0); } catch (e) {}
      if (n >= 3) return done(false, 'Booking không mở được đặt phòng này');
      await wait(2500);                              // the overview after the sign-in redirects carries `ses`
      if (resId() === String(job.bid)) return chatJob();
      const ses = new URL(location.href).searchParams.get('ses') || '';
      try { sessionStorage.setItem(key, String(n + 1)); } catch (e) {}
      location.href = `https://admin.booking.com/hotel/hoteladmin/extranet_ng/manage/booking.html?hotel_id=${job.hotel_id}&lang=vi` +
        (ses ? '&ses=' + encodeURIComponent(ses) : '') + `&res_id=${job.bid}&source=homepage`;
      return;
    }
    try { sessionStorage.setItem(key + '_busy', '1'); } catch (e) {}
    toast('📩 Lệnh từ điện thoại: nhắn hỏi WhatsApp cho ' + esc(job.guest || job.bid) + '…', 'ok', 8000);
    let box = null;
    for (let i = 0; i < 40 && !box; i++) {          // the reservation page draws its parts after loading
      box = chatBoxStrict();
      if (!box && (i === 10 || i === 25)) chatOpenSection();
      if (!box) await wait(1000);
    }
    if (!box) return done(false, 'không thấy khung "Soạn tin nhắn" trên trang đặt phòng', { final: true });
    putInChat(box, job.text);
    await wait(2000);                                // Booking enables its Gửi after the text is in
    const btn = chatSendBtn(box);
    if (!btn) return done(false, 'đã điền tin nhưng không thấy nút Gửi — mở Booking bấm Gửi giúp', { final: true });
    btn.click();
    let sent = false;
    for (let i = 0; i < 15 && !sent; i++) {          // sent = Booking emptied its message box
      await wait(1000);
      const b = box.isConnected ? box : chatBoxStrict();
      const v = b ? String(b.value !== undefined ? b.value : b.textContent || '') : '';
      sent = !v.trim();
    }
    return done(sent, sent ? '' : 'đã bấm Gửi nhưng tin vẫn nằm trong khung — mở Booking xem giúp', { clicked: true });
  }

  // the properties of THIS Booking account (a new guest is only opened in the profile whose account has it)
  function learnHotels() {
    if (!chrome.runtime?.id || /403/.test(location.pathname)) return;
    const ids = new Set();
    const h = new URL(location.href).searchParams.get('hotel_id');
    if (h && /^\d{5,10}$/.test(h) && !/[?&]has_access=0/.test(location.href)) ids.add(h);
    const gp = groupProps() || [];
    gp.forEach(p => p.id && ids.add(p.id));
    // full = the group overview lists ALL properties of the signed-in account → it REPLACES the list (1.44: the owner
    // swapped the Booking accounts of two profiles, Nov 19 — old properties must not stay)
    if (ids.size) chrome.runtime.sendMessage({ type: 'hotels', ids: [...ids], full: gp.length > 0 }).catch(() => {});
  }
  setTimeout(learnHotels, 8000);

  async function runStep() {
    const q = runGet();
    if (!q) return;
    chrome.storage.local.set({ hpRunBusy: Date.now() }).catch(() => {});   // 1.29: no self-reload in the middle of a run
    const it = q.items[q.i];
    if (!it) { finishRun('✅ Xong.'); return; }
    refreshRunBtn();
    // 1.36 (owner 18/11/2026): Booking can sign out when a reservation opens (its security check; this profile's
    // cookies went bad on Nov 18 — EVERY reservation → ?logout=1). The Tampermonkey script signs in again and we land
    // here on the overview / a home page instead of the guest → try that guest once more with the NEW session; the
    // same guest twice → skip it; 3 times in this run → stop, and background.js clears Booking's cookies + runs again.
    if (!resId()) {
      await wait(2500);
      const q1 = runGet();
      if (!q1 || resId()) return;
      const cur = q1.items[q1.i];
      cur.bounce = (cur.bounce || 0) + 1; q1.bounce = (q1.bounce || 0) + 1;
      if (q1.bounce >= 3) { runSet(q1); logoutLoop(); return; }
      if (cur.bounce >= 2) { q1.log.push({ bid: cur.bid, ok: false, why: 'Booking đăng xuất khi mở khách này' }); q1.i += 1; }
      runSet(q1);
      const nx = q1.items[q1.i];
      if (!nx) { finishRun('✅ Xong.'); return; }
      toast('🔑 Booking vừa đăng xuất rồi đăng nhập lại — mở lại khách…', 'warn', 5000);
      location.href = withSes(nx.url);
      return;
    }
    let ok = false, why = 'không đọc được trang';
    // wait for the reservation to show (the extranet draws the page after loading)
    for (let t = 0; t < 20 && !(document.body.innerText || '').includes(it.bid); t++) await wait(750);
    await wait(800);
    if (!runGet()) return;                         // stopped meanwhile
    try {
      let r = await api('/api/ext/booking/parse', capture());
      // 1.45 (owner Nov 20: a guest who booked 2 min earlier → "Thiếu: ngày nhận, ngày trả, giá, loại phòng"): the number
      // shows before the rest of the page is drawn → read again every 1.5 s (≤ 15 s) until the dates are there
      for (let t = 0; t < 10 && runGet() && !(r?.parsed?.checkin_date && r?.parsed?.checkout_date); t++) {
        await wait(1500);
        r = await api('/api/ext/booking/parse', capture());
      }
      const p = r?.parsed;
      if (r?.success && r.mode === 'single' && p?.booking_id) {
        const rooms = (p.rooms || []).length > 1 ? p.rooms : undefined;
        const s = await api('/api/ext/booking/save', {
          booking_id: p.booking_id, guest_name: p.guest_name || '', checkin_date: p.checkin_date || '',
          checkout_date: p.checkout_date || '', listing: p.listing || '',
          room_amount: String(p.room_amount || '').replace(/\D/g, ''), commission: String(p.commission || '').replace(/\D/g, ''),
          phone: '', nationality: p.nationality || '', email: p.email || '',   // phone only via checkPhone (partner rule)
          cancelled: p.status === 'cancelled', rooms,
        });
        ok = !!s?.success; why = s?.error || '';
        if (ok) toast(`📥 ${q.i + 1}/${q.items.length} · Đã lưu <b>${esc(p.guest_name || it.bid)}</b>`, 'ok', 4000);
        checkPhone();
        // 👁 click "Hiển thị số điện thoại" too (owner 17/11/2026: fully automatic), then give checkPhone
        //    (0.6–6 s after the click) + the picture time before going to the next guest
        let scheduled = false;
        for (let t = 0; t < 8 && !scheduled && runGet(); t++) { scheduled = autoRevealTry(); if (!scheduled) await wait(750); }
        // move on as soon as the number + picture are saved (owner 17/11/2026: "phải đợi rất lâu");
        // picture not possible (tab not in front…) → 4 s after the number; at most 12 s in all
        if (scheduled) {
          const bid = resId(), t0 = Date.now();
          while (Date.now() - t0 < 12000 && runGet()) {
            if (shotSavedFor === bid) break;
            if (phoneSaved.bid === bid && Date.now() - phoneSaved.at > 4000) break;
            await wait(300);
          }
        }
        // 1.52: no button (number already on the page: old booking arriving today) → wait up to 10 s for it to be read
        if (!scheduled) {
          const bid = resId(), t0 = Date.now();
          while (Date.now() - t0 < 10000 && runGet() && resId() === bid && phoneSaved.bid !== bid && !isPartnerBooking()) {
            checkPhone(); await wait(1000);
          }
        }
        // 1.48: no picture yet (the number did not show, or the capture failed) → draw it from the page now
        if (runGet() && resId() === p.booking_id && shotSavedFor !== p.booking_id) {
          const r2 = await Promise.race([autoShot('run'), wait(10000)]);
          if (r2?.success) shotSavedFor = p.booking_id;
        }
      } else why = r?.error || 'không thấy mã đặt phòng';
    } catch (e) { why = e.message; }
    const q2 = runGet();
    if (!q2) return;
    q2.log.push({ bid: it.bid, ok, why });
    q2.i += 1;
    runSet(q2);
    await humanPause();
    if (!runGet()) return;
    if (q2.i >= q2.items.length) finishRun('✅ Xong.');
    else location.href = q2.items[q2.i].url;
  }

  // ⏰ 7:00 every morning background.js opens Booking's home page → start on its own (no question asked)
  async function autoMorning() {
    if (!chrome.runtime?.id || runGet() || resId()) return;
    const { hpAutoRunUntil } = await chrome.storage.local.get('hpAutoRunUntil');
    if (!hpAutoRunUntil || Date.now() > hpAutoRunUntil) return;
    // 1.34: being on the overview counts as "tried" → a property home reached later never bounces back (was a loop)
    if (/\/groups\//.test(location.pathname)) { try { sessionStorage.setItem('hp_tried_group', '1'); } catch (e) {} }
    for (let t = 0; t < 40; t++) {                 // the home page draws the "Khách đến" list after loading
      let gp = groupProps();                       // several properties (owner's account) → overview table
      if (gp && gp.length) {
        await wait(2500);                          // the counts can arrive after the rows → read again when settled
        gp = groupProps() || gp;
        // ONE property (owner, Nov 17: 19 Thọ Nhuộm) → straight to its own home page, which checks "Khách đến · Hôm
        // nay" itself (the overview's 48-hour count is not needed); hpAutoRunUntil stays set for that page
        if (gp.length === 1) {
          try { sessionStorage.setItem('hp_prop_name', gp[0].name); } catch (e) {}
          location.href = gp[0].url;
          return;
        }
        await chrome.storage.local.remove('hpAutoRunUntil');
        const pick = groupPick(gp);
        if (!pick.length) {
          toast('🏢 Hôm nay không căn nào có khách đến.<br>' + groupSummary(gp), 'ok', 20000);
          morningGo();
          api('/api/ext/morning', { stage: 'start', note: 'Hôm nay không căn nào có khách đến — không phải làm gì.', account: await hpAccount() }).catch(() => {});
          return;
        }
        startGroup(pick, true, gp);
        return;
      }
      const a = arrivalsToday();                   // one property's home: only "Khách đến · Hôm nay"
      if (a) {
        // 1.33 (owner 17/11/2026): admin.booking.com/ opens the LAST property's home, not the overview of all
        // properties → go to the group overview once; an account with one property comes back here (redirect).
        let tried = null;
        try { tried = sessionStorage.getItem('hp_tried_group'); sessionStorage.setItem('hp_tried_group', '1'); } catch (e) {}
        if (!tried) { location.href = GROUP_URL; return; }
      }
      if (a && (a.items.length || (a.n === 0 && t >= 2))) {
        await chrome.storage.local.remove('hpAutoRunUntil');
        const hid = new URL(location.href).searchParams.get('hotel_id') || '';
        let name = '';
        try { name = sessionStorage.getItem('hp_prop_name') || ''; } catch (e) {}
        name = (name || rawText(document.querySelector('h1, h2')) || '').split('\n')[0].trim().slice(0, 60) || ('căn ' + hid);
        if (!a.items.length) {
          toast('Hôm nay không có khách đến.', 'ok', 15000);
          morningGo();
          api('/api/ext/morning', { stage: 'start', note: `${name}: hôm nay không có khách đến — không phải làm gì.`, account: await hpAccount() }).catch(() => {});
          return;
        }
        startGroup([{ id: hid, name, n: a.items.length, url: location.href }], true);   // same path: Zalo start / done
        return;
      }
      // the overview could not be read (error page / unknown layout) → the normal home page, once (never back here)
      if (t === 14 && /\/groups\//.test(location.pathname)) { location.href = 'https://admin.booking.com/'; return; }
      await wait(1500);
    }
  }
  // background.js: the owner has just signed in after the bot's "Booking đã đăng xuất" → start now
  chrome.runtime.onMessage.addListener(m => { if (m?.type === 'hp-morning-start') setTimeout(autoMorning, 1500); return false; });
  // 1.47 (owner Nov 21: Krizza Ceniza saved twice at the same instant, no picture): a tab Booking opens FROM a run
  // tab gets a COPY of its sessionStorage → it ran the same run too (double save; a tab behind cannot take the
  // picture). Each tab remembers its own id; a tab holding another tab's id is a copy → drop the copied run state.
  (async () => {
    let me = null;
    try { me = (await chrome.runtime.sendMessage({ type: 'tab-id' }))?.id ?? null; } catch (e) {}
    try {
      const owner = sessionStorage.getItem('hp_tab');
      if (me != null && owner && owner !== String(me)) {
        [RUN_KEY, GROUP_KEY, 'hp_fetch', 'hp_fetch_result', 'hp_run_done'].forEach(k => sessionStorage.removeItem(k));
      }
      if (me != null) sessionStorage.setItem('hp_tab', String(me));
    } catch (e) {}
    startTab();
  })();
  function startTab() {
  if (runGet()) setTimeout(runStep, 1500);
  else if (groupGet()) { setTimeout(showRunDone, 1500); setTimeout(groupStep, 3000); }
  else { setTimeout(showRunDone, 1500); setTimeout(showGroupDone, 1500); setTimeout(autoMorning, 3000); setTimeout(fetchJob, 2000); setTimeout(monthJob, 2500); setTimeout(chatJob, 2000); }
  }
})();
