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
      .tag.cx { display: inline-block; font-size: 10px; font-weight: 800; background: #dc2626; color: #fff; border-radius: 6px; padding: 0 6px; margin-left: 4px; }
      .paid { margin-top: 8px; font-size: 12px; background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 6px 8px; color: #166534; }
    </style>
    <div class="panel" id="panel"></div>
    <button class="fab" id="fab" type="button">📥 Gửi về Hotel Pro</button>`;

  const $ = sel => root.querySelector(sel);
  const panel = $('#panel');
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const api = (path, body) => chrome.runtime.sendMessage({ type: 'api', path, body });
  const fmt = n => n ? new Intl.NumberFormat('vi-VN').format(Math.round(n)) : '';

  // ── Reservation LIST page ("Đặt phòng" table) ───────────────────
  const fold = t => String(t || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .replace(/đ/g, 'd').replace(/Đ/g, 'D').toLowerCase().replace(/\s+/g, ' ').trim();
  const LIST_KEYS = ['ma so dat phong', 'ma dat phong', 'booking number', 'reservation number'];
  const BID_RE = /^\s*\d{8,12}\s*$/;
  const cellText = el => (el?.innerText || el?.textContent || '').trim();
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
      .filter(el => el.children.length === 0 && BID_RE.test(cellText(el)));
    // A list shows several booking numbers; a single one is a reservation detail page
    if (new Set(leaves.map(cellText)).size < 2) return null;
    // Row = the ancestor just below the container shared with the next booking number
    const rowOf = leaf => {
      if (leaves.length === 1) return leaf.closest('tr, [role="row"], li') || leaf.parentElement?.parentElement;
      const other = leaves.find(l => l !== leaf);
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
      .find(el => el.children.length <= 2 && isHeaderText(cellText(el)));
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
      .filter(el => el.children.length === 0 && BID_RE.test(cellText(el))));
    const path = el => { const p = []; for (let e = el; e && p.length < 8; e = e.parentElement) p.push(e.tagName.toLowerCase() + (e.getAttribute('role') ? `[role=${e.getAttribute('role')}]` : '') + (e.className && typeof e.className === 'string' ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '')); return p.join(' < '); };
    const hdr = docs.flatMap(doc => [...doc.querySelectorAll('*')]).find(el => el.children.length <= 2 && isHeaderText(cellText(el)));
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

  $('#fab').addEventListener('click', async () => {
    const fab = $('#fab');
    fab.textContent = '⏳ Đang đọc...';
    const listPage = captureList();
    const r = await api('/api/ext/booking/parse', listPage || capture());
    fab.textContent = '📥 Gửi về Hotel Pro';
    if (!r?.success && listPage) {
      // Not a list after all → try it as a single reservation page
      const single = await api('/api/ext/booking/parse', capture());
      if (single?.success && single.mode === 'single' && single.parsed.booking_id) { show(single); return; }
      const diag = JSON.stringify({ ...diagnostics(), how: listPage.how, headers: listPage.headers,
                                    cellsPerRow: listPage.rows.slice(0, 5).map(x => x.length) }, null, 1);
      panel.innerHTML = `<p class="msg err">❌ ${esc(r?.error || 'Lỗi không rõ')}</p>
        <pre style="font-size:10px;max-height:160px;overflow:auto;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:6px;white-space:pre-wrap">${esc(diag)}</pre>
        <div class="row"><button class="close" id="b_close" type="button">Đóng</button>
          <button class="save" id="b_copy" type="button">📋 Sao chép chẩn đoán</button></div>`;
      panel.classList.add('open');
      $('#b_close').onclick = () => panel.classList.remove('open');
      $('#b_copy').onclick = () => navigator.clipboard.writeText(diag).then(() => { $('#b_copy').textContent = '✅ Đã sao chép'; });
      return;
    }
    if (!r?.success) {
      panel.innerHTML = `<p class="msg err">❌ ${esc(r?.error || 'Lỗi không rõ')}</p>
        <p class="hint">Kiểm tra địa chỉ web trong biểu tượng tiện ích (góc trên trình duyệt).</p>
        <div class="row"><button class="close" id="b_close" type="button">Đóng</button></div>`;
      panel.classList.add('open');
      $('#b_close').onclick = () => panel.classList.remove('open');
      return;
    }
    if (r.mode === 'list') { showList(r); return; }
    if (!r.parsed.booking_id) {
      const diag = JSON.stringify(diagnostics(), null, 1);
      panel.innerHTML = `<p class="msg err">Không thấy đặt phòng trên trang này.</p>
        <p class="hint">Mở trang <b>Đặt phòng</b> (danh sách) hoặc một đặt phòng cụ thể rồi bấm lại.
          Nếu đang ở đúng trang mà vẫn lỗi: bấm <b>Sao chép chẩn đoán</b> và gửi cho người hỗ trợ
          (chỉ có cấu trúc trang, không có tên hay thông tin khách).</p>
        <pre style="font-size:10px;max-height:160px;overflow:auto;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:6px;white-space:pre-wrap">${esc(diag)}</pre>
        <div class="row"><button class="close" id="b_close" type="button">Đóng</button>
          <button class="save" id="b_copy" type="button">📋 Sao chép chẩn đoán</button></div>`;
      panel.classList.add('open');
      $('#b_close').onclick = () => panel.classList.remove('open');
      $('#b_copy').onclick = async () => {
        try { await navigator.clipboard.writeText(diag); $('#b_copy').textContent = '✅ Đã sao chép'; }
        catch (e) { $('#b_copy').textContent = 'Không sao chép được — chụp màn hình giúp'; }
      };
      return;
    }
    show(r);
  });
})();
