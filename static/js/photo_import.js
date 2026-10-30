// 📷 Photo tools for the new apps (/moi, /may-tinh) — the same reading and saving as /messages, in the new look, without
// leaving the page (owner, Oct 30: "bấm thêm khách từ ảnh là lại nhảy sang giao diện cũ").
//   PhotoImport.booking({apartments, onSaved})  screenshots of a Booking-app reservation → read on this device (OCR, no
//                                               upload) → fields to check (+ apartment) → /api/booking_from_photo/save
//   PhotoImport.phone({onSaved})                screenshots of the Booking-app chat → guest + number → /api/messages/phone
// Nothing is saved without the owner's tap.
(function () {
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const post = (u, b) => fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b) })
    .then((x) => x.json()).catch(() => null);
  const digits = (v) => String(v || '').replace(/\D/g, '');
  let worker = null, ov = null;

  function css() {
    if (document.getElementById('pi-css')) return;
    const s = document.createElement('style');
    s.id = 'pi-css';
    s.textContent = `
      .pi-ov{position:fixed;inset:0;z-index:99980;background:rgba(14,21,37,.48);display:flex;align-items:flex-end;justify-content:center;font-family:inherit}
      .pi{background:#fff;width:100%;max-width:600px;max-height:92vh;max-height:92dvh;overflow-y:auto;overscroll-behavior:contain;border-radius:24px 24px 0 0;
          padding:16px 20px calc(22px + env(safe-area-inset-bottom));color:#0E1525;box-shadow:0 -10px 40px rgba(14,21,37,.25)}
      @media(min-width:700px){.pi-ov{align-items:center}.pi{border-radius:20px}}
      .pi-top{display:flex;align-items:center;gap:10px}.pi-top div{flex:1;min-width:0}
      .pi-k{font-size:11px;font-weight:800;letter-spacing:1.2px;color:#64748B}.pi-t{font-size:20px;font-weight:800}
      .pi-x{width:42px;height:42px;border-radius:12px;border:1px solid #E2E5EB;background:#fff;font-size:18px;font-weight:800;color:#0E1525;cursor:pointer}
      .pi-steps{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin-top:12px}
      .pi-steps div{background:#F4F5F8;border-radius:12px;padding:8px 10px;font-size:12px;font-weight:600;color:#334155;line-height:1.35}
      .pi-steps b{display:block;font-size:11px;color:#64748B;letter-spacing:.5px}
      .pi-pick{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}
      .pi-pick label,.pi-pick button{min-height:52px;border-radius:14px;border:1.5px dashed #94A3B8;background:#fff;display:flex;align-items:center;justify-content:center;gap:8px;
          font-size:14px;font-weight:800;color:#0E1525;cursor:pointer;font-family:inherit}
      .pi-pick label.pri{border:none;background:#0E1525;color:#fff}
      .pi-thumbs{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.pi-thumbs img{width:64px;height:64px;object-fit:cover;border-radius:10px;border:1px solid #E2E5EB}
      .pi-status{margin-top:10px;font-size:13px;font-weight:700;color:#475569}.pi-status.err{color:#B91C1C}
      .pi-f{display:block;margin-top:10px}.pi-f span{display:block;font-size:12px;font-weight:700;color:#475569;margin-bottom:4px}
      .pi-f input,.pi-f select{width:100%;min-height:46px;border-radius:12px;border:1.5px solid #E2E5EB;padding:0 12px;font-size:16px;font-family:inherit;background:#fff;color:#0E1525;box-sizing:border-box}
      .pi-f input.miss{border-color:#F59E0B;background:#FFFBEB}
      .pi-2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
      .pi-note{margin-top:10px;border-radius:12px;padding:9px 12px;font-size:12.5px;line-height:1.5;background:#EFF6FF;color:#1E3A8A}
      .pi-note.warn{background:#FFFBEB;color:#92400E}
      .pi-save{width:100%;min-height:54px;border-radius:16px;border:none;background:#0E1525;color:#fff;font-size:15px;font-weight:800;margin-top:14px;cursor:pointer;font-family:inherit}
      .pi-save:disabled{opacity:.6}
      .pi-row{display:flex;gap:10px;align-items:flex-start;border:1px solid #E4E7ED;border-radius:14px;padding:10px;margin-top:10px}
      .pi-row img{width:56px;height:80px;object-fit:cover;border-radius:8px;flex-shrink:0}
      .pi-row .m{flex:1;min-width:0;display:flex;flex-direction:column;gap:3px}.pi-row b{font-size:14px}.pi-row small{font-size:12px;color:#475569}
      .pi-row input{min-height:42px;border-radius:10px;border:1.5px solid #E2E5EB;padding:0 10px;font-size:16px;font-family:inherit;margin-top:4px}
      .pi-row .ok{font-size:12.5px;font-weight:800;color:#15803D}.pi-row .er{font-size:12px;font-weight:700;color:#B91C1C}
      .pi-row button{min-height:40px;border-radius:10px;border:none;background:#0E1525;color:#fff;font-size:13px;font-weight:800;margin-top:4px;cursor:pointer;font-family:inherit}
      .pi-row button:disabled{opacity:.4}
      .pi-toast{position:fixed;left:50%;transform:translateX(-50%);bottom:calc(96px + env(safe-area-inset-bottom));z-index:99999;background:#0E1525;color:#fff;border-radius:14px;
          padding:12px 18px;font-size:13.5px;font-weight:700;box-shadow:0 10px 30px rgba(14,21,37,.3);max-width:90vw}`;
    document.head.appendChild(s);
  }
  const toast = (t) => { const el = document.createElement('div'); el.className = 'pi-toast'; el.setAttribute('role', 'status'); el.textContent = t;
    document.body.appendChild(el); setTimeout(() => el.remove(), 3500); };
  function sheet(kick, title, body) {
    css(); close();
    ov = document.createElement('div');
    ov.className = 'pi-ov';
    ov.innerHTML = `<div class="pi" role="dialog" aria-modal="true"><div class="pi-top"><div><div class="pi-k">${kick}</div><div class="pi-t">${title}</div></div>
      <button type="button" class="pi-x" aria-label="Đóng">✕</button></div>${body}</div>`;
    document.body.appendChild(ov);
    ov.addEventListener('click', (e) => { if (e.target === ov) close(); });
    ov.querySelector('.pi-x').onclick = close;
    return ov;
  }
  function close() { if (ov) ov.remove(); ov = null; }
  const status = (t, err) => { const el = ov && ov.querySelector('.pi-status'); if (el) { el.textContent = t; el.className = 'pi-status' + (err ? ' err' : ''); } };

  function loadTesseract() {
    if (window.Tesseract) return Promise.resolve();
    return new Promise((res, rej) => {
      const sc = document.createElement('script');
      sc.src = 'https://cdn.jsdelivr.net/npm/tesseract.js@5/dist/tesseract.min.js';
      sc.onload = res; sc.onerror = () => rej(new Error('không tải được bộ đọc chữ (kiểm tra mạng)'));
      document.head.appendChild(sc);
    });
  }
  async function getWorker() {
    status(window.Tesseract ? 'Đang đọc ảnh…' : 'Đang tải bộ đọc chữ (lần đầu ~10 giây)…');
    await loadTesseract();
    if (!worker) worker = await Tesseract.createWorker('vie+eng');
    return worker;
  }
  // dark-mode screenshots read best inverted to black text on white
  async function prepare(blob) {
    const url = URL.createObjectURL(blob), img = new Image();
    img.src = url; await img.decode();
    const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
    const x = c.getContext('2d'); x.drawImage(img, 0, 0);
    const d = x.getImageData(0, 0, c.width, c.height); let sum = 0, n = 0;
    for (let i = 0; i < d.data.length; i += 16) { sum += d.data[i] + d.data[i + 1] + d.data[i + 2]; n++; }
    if (sum / n / 3 < 110) {
      for (let i = 0; i < d.data.length; i += 4) { const g = 255 - (d.data[i] * .3 + d.data[i + 1] * .59 + d.data[i + 2] * .11); d.data[i] = d.data[i + 1] = d.data[i + 2] = g; }
      x.putImageData(d, 0, 0);
    }
    return { canvas: c, url };
  }
  const ocrLines = (d) => {
    if (d.lines && d.lines.length) return d.lines.map((l) => ({ text: l.text, bbox: l.bbox }));
    const out = []; (d.blocks || []).forEach((b) => (b.paragraphs || []).forEach((p) => (p.lines || []).forEach((l) => out.push({ text: l.text, bbox: l.bbox })))); return out;
  };
  async function fromClipboard() {
    try {
      const items = await navigator.clipboard.read(), files = [];
      for (const it of items) for (const t of it.types) if (t.startsWith('image/')) files.push(await it.getType(t));
      return files;
    } catch (e) { return null; }
  }
  document.addEventListener('paste', (e) => {                       // Ctrl+V on a computer
    if (!ov || !ov._onFiles) return;
    const files = [...((e.clipboardData && e.clipboardData.files) || [])].filter((f) => f.type.startsWith('image/'));
    if (files.length) { e.preventDefault(); ov._onFiles(files); }
  });

  // ═════ Thêm đặt phòng từ ảnh ═════
  const FIELDS = [['booking_id', 'Mã đặt phòng', 'text', 'numeric'], ['guest_name', 'Tên khách', 'text'],
                  ['checkin_date', 'Nhận phòng', 'date'], ['checkout_date', 'Trả phòng', 'date'],
                  ['listing', 'Loại phòng', 'text'], ['room_amount', 'Tổng tiền (đ)', 'text', 'numeric'],
                  ['property_name', 'Tên chỗ nghỉ (tin đăng)', 'text'], ['phone', 'Số điện thoại (nếu có)', 'tel']];
  const OPTIONAL = ['phone', 'booking_id', 'property_name'];
  function booking(opts) {
    opts = opts || {};
    let texts = [], shots = [], parsed = null, existing = null;
    const edited = new Set();
    const o = sheet('THÊM ĐẶT PHÒNG', 'Từ ảnh chụp app Booking', `
      <div class="pi-steps"><div><b>1 · CHỤP</b>Màn hình đặt phòng trong app Booking (có thể 2 ảnh, thấy cả mã đặt phòng)</div>
        <div><b>2 · CHỌN / DÁN</b>Ảnh được đọc ngay trên máy, không gửi đi đâu</div><div><b>3 · KIỂM TRA</b>Xem lại các ô rồi bấm Lưu</div></div>
      <div class="pi-note">📞 Có số điện thoại? Trong app bấm <b>Liên hệ</b> → chụp khung <b>"Gọi +84 …"</b> rồi thêm ảnh đó cùng lúc — web tự điền số.</div>
      <div class="pi-pick"><label class="pri">🖼 Chọn ảnh<input type="file" accept="image/*" multiple hidden></label><button type="button" class="paste">📋 Dán ảnh</button></div>
      <div class="pi-thumbs"></div><div class="pi-status"></div><div class="pi-form"></div>`);
    const add = async (files) => {
      if (!files || !files.length || !ov) return;
      try {
        const w = await getWorker();
        for (const f of files) {
          const { canvas, url } = await prepare(f);
          if (!ov) return;
          o.querySelector('.pi-thumbs').insertAdjacentHTML('beforeend', `<img src="${url}" alt="">`);
          status(`Đang đọc ảnh ${texts.length + 1}…`);
          const r = await w.recognize(canvas, {}, { text: true, blocks: true });
          texts.push(r.data.text); shots.push({ file: f, text: r.data.text, lines: ocrLines(r.data) });
        }
        const p = await post('/api/booking_from_photo/parse', { text: texts.join('\n'), texts });
        if (!ov) return;
        status(''); parsed = (p && p.parsed) || {}; existing = p && p.existing; form();
      } catch (e) { status('Không đọc được ảnh: ' + (e.message || e), true); }
    };
    o._onFiles = add;
    o.querySelector('input[type=file]').onchange = (e) => { add([...e.target.files]); e.target.value = ''; };
    o.querySelector('.paste').onclick = async () => { const f = await fromClipboard();
      if (f === null) status('Máy không cho dán trực tiếp — dùng "Chọn ảnh".', true); else if (!f.length) status('Không có ảnh trong bộ nhớ tạm — chụp màn hình, bấm Sao chép rồi dán lại.', true); else add(f); };

    function form() {
      const box = o.querySelector('.pi-form'), cur = {};
      box.querySelectorAll('[data-k]').forEach((i) => { cur[i.dataset.k] = i.value; });
      const p = parsed;
      const val = (k) => edited.has(k) ? cur[k] : (k === 'room_amount' ? (p[k] ? Math.round(p[k]).toLocaleString('vi-VN') : '') : (p[k] || ''));
      const inp = (f) => `<label class="pi-f"><span>${f[1]}</span><input data-k="${f[0]}" type="${f[2]}" ${f[3] ? `inputmode="${f[3]}"` : ''} value="${esc(val(f[0]))}"
        class="${val(f[0]) || OPTIONAL.includes(f[0]) ? '' : 'miss'}" ${f[0] === 'booking_id' ? 'placeholder="Không có cũng được — dùng mã tạm"' : ''}></label>`;
      const apts = opts.apartments || [];
      box.innerHTML = inp(FIELDS[1]) + `<div class="pi-2">${inp(FIELDS[2])}${inp(FIELDS[3])}</div>` + inp(FIELDS[4])
        + `<div class="pi-2">${inp(FIELDS[5])}${inp(FIELDS[7])}</div><div class="pi-2">${inp(FIELDS[0])}${apts.length ? `<label class="pi-f"><span>Xếp vào căn</span><select data-k="__apt"><option value="">Chưa xếp</option>${apts.map((a) => `<option value="${a.id}" ${String(cur.__apt || '') === String(a.id) ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}</select></label>` : ''}</div>`
        + inp(FIELDS[6])
        + (!val('booking_id') ? '<div class="pi-note">Không có <b>mã đặt phòng</b> cũng lưu được: web dùng <b>mã tạm</b>, khi mở booking này trên máy tính (tiện ích Chrome) sẽ tự đổi sang mã thật.</div>' : '')
        + (p.matched ? '<div class="pi-note">Ảnh không có mã đặt phòng — đã tìm thấy booking cùng ngày &amp; cùng giá trên web.</div>' : '')
        + (p.matched_name ? '<div class="pi-note">Ảnh gọi điện — đã tìm thấy booking của khách này; <b>Lưu</b> sẽ thêm số điện thoại.</div>' : '')
        + (p.phone ? `<div class="pi-note">📞 Đọc được số <b>${esc(p.phone)}</b> — kiểm tra lại cho đúng trước khi lưu.</div>` : '')
        + (existing ? `<div class="pi-note warn">Booking này <b>đã có trên web</b> (${esc(existing.guest_name)}) — Lưu sẽ cập nhật ngày / giá / phòng; tiền đã thu và căn đã xếp giữ nguyên.</div>` : '')
        + `<button type="button" class="pi-save">${existing ? 'Cập nhật đặt phòng' : 'Lưu khách vào web'}</button>`;
      box.querySelectorAll('[data-k]').forEach((i) => i.addEventListener('input', () => { edited.add(i.dataset.k); if (i.tagName === 'INPUT') i.classList.toggle('miss', !i.value && !OPTIONAL.includes(i.dataset.k)); }));
      box.querySelector('select[data-k]') && box.querySelector('select[data-k]').addEventListener('change', () => edited.add('__apt'));
      box.querySelector('.pi-save').onclick = save;
    }
    async function saveShot(bookingId) {          // the reservation screenshot = the booking picture (commission line covered for guests)
      const fold = (s) => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd');
      const pick = shots.map((s) => ({ s, t: fold(s.text) })).filter((x) => /nhan phong/.test(x.t) && /tra phong/.test(x.t) && !/goi\s*\+?\s*\d/.test(x.t))
        .sort((a, b) => /tong|gia tien/.test(b.t) - /tong|gia tien/.test(a.t))[0];
      if (!pick) return;
      const url = URL.createObjectURL(pick.s.file), img = new Image(); img.src = url; await img.decode();
      const k = Math.min(1, 1000 / img.naturalWidth);
      const draw = (mask) => { const c = document.createElement('canvas'); c.width = Math.round(img.naturalWidth * k); c.height = Math.round(img.naturalHeight * k);
        const x = c.getContext('2d'); x.drawImage(img, 0, 0, c.width, c.height);
        if (mask) pick.s.lines.filter((l) => /hoa hong|commission/.test(fold(l.text))).forEach((l) => { const b = l.bbox, px = x.getImageData(2, Math.max(0, Math.round(b.y0 * k)), 1, 1).data;
          x.fillStyle = `rgb(${px[0]},${px[1]},${px[2]})`; x.fillRect(0, b.y0 * k - 6, c.width, (b.y1 - b.y0) * k + 12); });
        return c.toDataURL('image/jpeg', 0.85); };
      await post('/api/booking_from_photo/shot', { booking_id: bookingId, full: draw(false), guest: draw(true) });
      URL.revokeObjectURL(url);
    }
    async function save() {
      const v = (k) => ((o.querySelector(`[data-k="${k}"]`) || {}).value || '').trim();
      const body = {}; FIELDS.forEach((f) => { body[f[0]] = v(f[0]); });
      body.room_amount = body.room_amount.replace(/\D/g, '');
      const missing = FIELDS.filter((f) => !OPTIONAL.includes(f[0]) && !body[f[0]]).map((f) => f[1]);
      if (missing.length) return status('Còn thiếu: ' + missing.join(', '), true);
      if (body.checkout_date <= body.checkin_date) return status('Ngày trả phải sau ngày nhận phòng', true);
      const btn = o.querySelector('.pi-save'), label = btn.textContent; btn.disabled = true; btn.textContent = 'Đang lưu…';
      const r = await post('/api/booking_from_photo/save', body);
      if (!r || !r.success) { btn.disabled = false; btn.textContent = label; return status((r && (r.error || r.message)) || 'Không lưu được', true); }
      if (r.booking_id) await saveShot(r.booking_id).catch(() => null);
      const apt = v('__apt');
      if (apt && r.booking_id) await post('/api/set_actual_apartment', { booking_id: r.booking_id, actual_apartment: apt });
      close();
      toast((r.action === 'created' ? 'Đã thêm ' : 'Đã cập nhật ') + body.guest_name);
      if (opts.onSaved) opts.onSaved(r);
    }
  }

  // ═════ Cập nhật số từ ảnh tin nhắn ═════
  function phone(opts) {
    opts = opts || {};
    let rows = [];
    const o = sheet('CẬP NHẬT SỐ ĐIỆN THOẠI', 'Từ ảnh chụp tin nhắn', `
      <div class="pi-steps"><div><b>1 · CHỤP</b>Cuộc trò chuyện trong app Booking (thấy tên khách, ngày ở và số)</div>
        <div><b>2 · CHỌN</b>Được chọn nhiều ảnh cùng lúc, đọc ngay trên máy</div><div><b>3 · LƯU</b>Web tự tìm khách và số — kiểm tra rồi bấm Lưu</div></div>
      <div class="pi-pick"><label class="pri">🖼 Chọn ảnh<input type="file" accept="image/*" multiple hidden></label><button type="button" class="paste">📋 Dán ảnh</button></div>
      <div class="pi-status"></div><div class="pi-list"></div>`);
    const read = async (files) => {
      if (!files || !files.length) return;
      try {
        const w = await getWorker(); let i = 0;
        for (const f of files) {
          if (!ov) return;
          status(`Đang đọc ảnh ${++i}/${files.length}…`);
          const { canvas, url } = await prepare(f);
          const r = await w.recognize(canvas);
          const p = await post('/api/phone_from_chat/parse', { text: r.data.text });
          rows.push({ url, p: (p && p.parsed) || {}, state: '' }); draw();
        }
        status('');
      } catch (e) { status('Không đọc được ảnh: ' + (e.message || e), true); }
    };
    o._onFiles = read;
    o.querySelector('input[type=file]').onchange = (e) => { read([...e.target.files]); e.target.value = ''; };
    o.querySelector('.paste').onclick = async () => { const f = await fromClipboard();
      if (f === null) status('Máy không cho dán trực tiếp — dùng "Chọn ảnh".', true); else if (!f.length) status('Không có ảnh trong bộ nhớ tạm.', true); else read(f); };
    function draw() {
      if (!ov) return;
      const ready = rows.filter((r) => r.p.booking_id && r.p.phone && r.state !== 'ok' && digits(r.p.current_phone) !== digits(r.p.phone));
      o.querySelector('.pi-list').innerHTML = rows.map((r, i) => { const p = r.p, same = p.current_phone && p.phone && digits(p.current_phone) === digits(p.phone);
        return `<div class="pi-row"><img src="${r.url}" alt=""><div class="m"><b>${esc(p.matched_name || p.guest_name || 'Không đọc được tên')}</b>
          <small>${p.booking_id ? `${esc(p.nhan)} → ${esc(p.tra)} · mã ${esc(p.booking_id)}` : '⚠️ Không tìm thấy khách này trên web'}</small>
          <small>${p.current_phone ? 'Số đang lưu: ' + esc(p.current_phone) : 'Chưa có số'}</small>
          <input type="tel" data-i="${i}" value="${esc(p.phone || '')}" placeholder="Không thấy số — gõ vào đây">
          ${(p.phones || []).length > 1 ? `<small>Các số trong ảnh: ${p.phones.map(esc).join(', ')}</small>` : ''}
          ${r.state === 'ok' ? '<div class="ok">✓ Đã lưu</div>' : same ? '<div class="ok">✓ Số này đã có trên web</div>' : `<button type="button" data-i="${i}" ${p.booking_id ? '' : 'disabled'}>Lưu số</button>`}
          ${r.state && r.state !== 'ok' ? `<div class="er">${esc(r.state)}</div>` : ''}</div></div>`; }).join('')
        + (ready.length > 1 ? `<button type="button" class="pi-save all">Lưu tất cả ${ready.length} số</button>` : '');
      o.querySelectorAll('.pi-row input').forEach((inp) => { inp.oninput = () => { rows[inp.dataset.i].p.phone = inp.value; }; });
      o.querySelectorAll('.pi-row button').forEach((b) => { b.onclick = () => save(+b.dataset.i).then(draw); });
      const all = o.querySelector('.pi-save.all'); if (all) all.onclick = async () => { for (const r of ready) await save(rows.indexOf(r)); draw(); };
    }
    async function save(i) {
      const r = rows[i]; if (!r.p.booking_id || !r.p.phone) return;
      let res = await post('/api/messages/phone', { booking_id: r.p.booking_id, phone: r.p.phone });
      if (res && res.status === 'duplicate' && confirm(`Số ${r.p.phone} đang là của khách "${res.other_name}". Vẫn lưu cho ${r.p.matched_name}?`))
        res = await post('/api/messages/phone', { booking_id: r.p.booking_id, phone: r.p.phone, force: true });
      r.state = res && res.success ? 'ok' : ((res && res.error) || 'Không lưu được');
      if (res && res.success && opts.onSaved) opts.onSaved(res);
    }
  }

  window.PhotoImport = { booking, phone, close };
})();
