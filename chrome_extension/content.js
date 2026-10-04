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
      .toast.ok { background: #166534; } .toast.warn { background: #b45309; } .toast.partner { background: #6d28d9; }
      .fab2 { background: #16a34a; margin-right: 8px; } .fab2:hover { background: #15803d; }
      .tpl { display: block; width: 100%; text-align: left; border: 1.5px solid #e2e8f0; background: #fff; border-radius: 10px;
             padding: 8px 10px; margin-bottom: 6px; font-size: 13px; font-weight: 700; cursor: pointer; color: #0f172a; }
      .tpl.on { border-color: #16a34a; background: #f0fdf4; }
      .pv { white-space: pre-wrap; font-size: 12px; line-height: 1.45; background: #f8fafc; border: 1px solid #e2e8f0;
            border-radius: 10px; padding: 8px 10px; max-height: 220px; overflow: auto; margin: 4px 0 0; }
      .ptag { display: inline-block; font-size: 11px; font-weight: 800; background: #ede9fe; color: #6d28d9; border-radius: 999px; padding: 2px 8px; }
    </style>
    <div class="panel" id="panel"></div>
    <button class="fab fab2" id="fill" type="button" style="display:none">💬 Điền tin</button><button class="fab" id="fab" type="button">📥 Gửi về Hotel Pro</button>`;

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
  // Không tự bấm, không tự mở trang, không moi số đang ẩn.
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
    el.innerHTML = html;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => el.remove(), ms);
  }
  // "Đối tác Booking.com" box: booked through a partner company. The number shown is the partner's
  // (same local number for everyone, only the country code changes) → never saved as the guest's.
  const PARTNER_WORDS = ['cong ty hop tac voi booking.com', 'partner company of booking.com',
                         'company that partners with booking.com', 'through a booking.com partner'];
  const isPartnerBooking = () => { const t = fold(document.body.innerText || ''); return PARTNER_WORDS.some(w => t.includes(w)); };

  const phoneDone = new Set();
  let phoneBusy = false;
  async function checkPhone() {
    if (phoneBusy || busy || !chrome.runtime?.id) return;
    const partner = isPartnerBooking();
    const ph = guestPhone();
    if (!ph && !partner) return;
    const key = location.href.split('#')[0] + '|' + (partner ? 'partner' : digitsOf(ph));
    if (phoneDone.has(key)) return;
    phoneBusy = true;
    try {
      phoneDone.add(key);
      const r = await api('/api/ext/booking/phone', { ...capture(), phone: ph || '', partner });
      if (!r?.success) { phoneDone.delete(key); return; }
      if (r.status === 'partner') toast(`🤝 <b>${esc(r.guest_name)}</b> đặt qua <b>đối tác Booking</b> — số trên trang là của đối tác nên <b>không lưu</b>. Bấm <b>💬 Điền tin</b> để xin số Zalo/WhatsApp trong khung chat.`, 'partner');
      else if (r.status === 'partner_not_on_web') toast(`🤝 Đặt qua <b>đối tác Booking</b> — số trên trang là của đối tác, không phải của khách. Chưa tự thêm được booking${r.error ? ' (' + esc(r.error) + ')' : ''}: bấm 📥 để thêm.`, 'partner');
      else if (r.status === 'created') toast(`📥 Đã tự thêm booking <b>${esc(r.guest_name)}</b> vào web + lưu SĐT <b>${esc(r.phone)}</b>`, 'ok');
      else if (r.status === 'saved') toast(`📞 Đã lưu SĐT <b>${esc(r.phone)}</b> cho <b>${esc(r.guest_name)}</b>`, 'ok');
      else if (r.status === 'same') toast(`📞 SĐT của <b>${esc(r.guest_name)}</b> đã có trên web`);
      else if (r.status === 'duplicate') toast(`⚠️ Số <b>${esc(r.phone)}</b> đang là của khách <b>${esc(r.other_name)}</b> — chưa lưu, kiểm tra lại`, 'warn');
      else if (r.status === 'not_on_web') toast(`📞 Thấy SĐT nhưng chưa tự thêm được booking #${esc(r.booking_id)}${r.error ? ' (' + esc(r.error) + ')' : ''} — bấm 📥 để thêm`, 'warn');
      // 📸 the Booking picture is taken only once the phone is on the page (owner decision, Oct 2026)
      if (['saved', 'created'].includes(r.status)) shotWhenVisible(true);          // just revealed → always a fresh picture
      else if (['same', 'partner'].includes(r.status)) shotWhenVisible(false);     // already known → not again within 10 min
    } finally { phoneBusy = false; }
  }

  // ⚡ Auto-capture of the reservation box (always on — owner decision), only once the guest's phone shows
  //   on the page (revealed now, already shown, or a partner booking) — not before.
  const autoShotDone = new Set();
  let lastPhoneToast = '';
  const SHOT_AGAIN_MS = 10 * 60 * 1000;
  const shotStampKey = bid => 'hp_shot_' + bid;
  function autoShot(kind) {
    const bid = resId();
    if (!bid || !chrome.runtime?.id) return Promise.resolve(null);
    const key = bid + '|' + kind;
    if (autoShotDone.has(key)) return Promise.resolve(null);
    autoShotDone.add(key);
    lastPhoneToast = kind === 'phone' ? ($('#toast')?.innerHTML || '') : '';
    return chrome.runtime.sendMessage({ type: 'auto-shot' }).then(r => {
      if (r?.success) return r;
      autoShotDone.delete(key);                      // allow another try
      if (r?.reason === 'off' && kind === 'phone') {
        let hinted = false;
        try { hinted = sessionStorage.getItem('hp_autoshot_hint') === '1'; sessionStorage.setItem('hp_autoshot_hint', '1'); } catch (e) {}
        if (!hinted) toast(lastPhoneToast + '<br><small>⚠️ Chưa tự chụp được ảnh đặt phòng: vào <b>chrome://extensions</b> bấm ↻ ở tiện ích Hotel Pro.</small>', 'warn');
      } else if (r?.error === 'busy') {
        setTimeout(() => autoShot(kind), 2500);       // another capture was running
      }
      return r;
    }).catch(() => { autoShotDone.delete(key); return null; });
  }
  function shotWhenVisible(fresh) {
    const bid = resId();
    if (!bid) return;
    if (!fresh) {
      let last = 0;
      try { last = +sessionStorage.getItem(shotStampKey(bid)) || 0; } catch (e) {}
      if (Date.now() - last < SHOT_AGAIN_MS) return;
    }
    let tries = 0;
    const go = async () => {
      if (document.hidden || resId() !== bid) return;
      const r = await autoShot('phone');
      if (r && !r.success && r.reason !== 'off' && /khung/i.test(r.error || '') && ++tries < 2) setTimeout(go, 4000);
    };
    if (!document.hidden) { setTimeout(go, 800); return; }
    // opened in a background tab → take it when you look at it
    document.addEventListener('visibilitychange', function once() {
      if (document.hidden) return;
      document.removeEventListener('visibilitychange', once);
      setTimeout(go, 1500);
    });
  }
  // Chỉ phản ứng khi bạn bấm đúng nút "Hiển thị số điện thoại"; số hiện ra sau đó một chút.
  document.addEventListener('click', e => {
    if (host.contains(e.target)) return;
    const el = e.target.closest ? e.target.closest('button, a, [role="button"], span') : null;
    if (!isRevealEl(el)) return;
    revealSpot = el.parentElement?.parentElement || el.parentElement;
    [600, 1500, 3000, 6000].forEach(ms => setTimeout(checkPhone, ms));
  }, true);
  // Nếu số đã hiện sẵn khi mở trang (hoặc là đặt phòng qua đối tác).
  [2500, 6000].forEach(ms => setTimeout(checkPhone, ms));

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
      if (shownResId !== null) [2500, 6000].forEach(ms => setTimeout(checkPhone, ms));
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
      } else if (r.top > cardR.bottom - 5 && !/vnd|\d{1,2}\s+thang|\d{4}/.test(t) && /\([^)]*\)\s*$/.test(rawText(el))) {
        // the room title in the room block: "(2 Giường 18 Hàng Bè)" is the owner's own note → cover just that part
        const node = [...el.childNodes].find(n => n.nodeType === 3 && n.textContent.includes('('));
        if (node) {
          const range = document.createRange();
          range.setStart(node, node.textContent.lastIndexOf('('));
          range.setEnd(node, node.textContent.length);
          [...range.getClientRects()].forEach(q => masks.push(grow(box(q), 2)));
        }
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

  async function finishShot(dataUrl) {
    const p = pendingShot;
    pendingShot = null;
    try {
      if (!p) throw new Error('Hết thời gian — chụp lại nhé');
      const img = await new Promise((res, rej) => {     // (img.decode() can stall in a background tab)
        const i = new Image();
        i.onload = () => res(i);
        i.onerror = () => rej(new Error('Ảnh chụp bị lỗi'));
        i.src = dataUrl;
      });
      restoreFloating(p.floating);
      window.scrollTo({ top: p.backTo, behavior: 'instant' });     // picture taken — page back where you were
      const s = img.width / p.vw;
      const a = { left: Math.max(0, p.area.left), top: Math.max(0, p.area.top),
                  right: Math.min(p.vw, p.area.right), bottom: Math.min(p.vh, p.area.bottom) };
      const make = masked => {
        const c = document.createElement('canvas');
        c.width = Math.round((a.right - a.left) * s);
        c.height = Math.round((a.bottom - a.top) * s);
        const x = c.getContext('2d');
        x.drawImage(img, a.left * s, a.top * s, c.width, c.height, 0, 0, c.width, c.height);
        if (masked) {
          x.fillStyle = '#ffffff';
          p.masks.forEach(m => x.fillRect((m.left - a.left) * s, (m.top - a.top) * s, m.width * s, m.height * s));
        }
        return c.toDataURL('image/jpeg', 0.9);
      };
      const full = make(false), guest = make(true);
      host.style.visibility = '';
      if (!p.auto) toast('📸 Đang lưu ảnh lên web…');
      const r = await api('/api/ext/booking/screenshot', { booking_id: p.bid, full, guest });
      if (!r?.success) throw new Error(r?.error || 'Lỗi không rõ');
      try { sessionStorage.setItem(shotStampKey(p.bid), String(Date.now())); } catch (e) {}
      if (p.auto) {
        if (lastPhoneToast) toast(lastPhoneToast + '<br>📸 Đã lưu luôn <b>ảnh đặt phòng</b> (bản gửi khách đã che hoa hồng)', 'ok');
        else toast('📸 Đã lưu ảnh đặt phòng', 'ok', 2500);
        return;
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
    } catch (e) {
      host.style.visibility = '';
      toast('❌ Chụp ảnh: ' + esc(e.message), 'warn');
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
      finishShot(msg.dataUrl);
    } else if (msg?.type === 'shot-error') {
      cancelShot();
      toast((msg.auto ? '📸 Không tự chụp được ảnh: ' : '📸 ') + esc(msg.error), 'warn');
    }
    return false;
  });
})();
