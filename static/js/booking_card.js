// Booking-confirmation image. Drawn on the device (canvas), shown as a preview, then sent to
// WhatsApp / Zalo through the phone's share sheet — wa.me links can only carry text, not pictures.
// On a computer: copy the image (paste into WhatsApp Web) or download it.
// Used by /messages and calendar_details:  HotelCard.open(bookingId)
(function () {
  const W = 1080;
  const BLUE1 = '#1e3a8a', BLUE2 = '#2563eb', INK = '#0f172a', MUTED = '#64748b', LINE = '#e2e8f0', GREEN = '#16a34a';
  const FONT = '"Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif';
  const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

  // Booking names often end with the country code ("Lucas de Kok nl")
  const cleanName = n => String(n || '').replace(/\s+[a-z]{2}$/, '').trim();
  const money = n => new Intl.NumberFormat('en-US').format(Math.round(n || 0)) + ' VND';
  const dateParts = iso => {                      // "2026-10-04" → ["04 Oct 2026", "Sunday"]
    if (!iso) return ['—', ''];
    const [y, m, d] = iso.split('-').map(Number);
    return [`${String(d).padStart(2, '0')} ${MON[m - 1]} ${y}`, DAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]];
  };

  function roundRect(x, l, t, w, h, r) {
    x.beginPath();
    x.moveTo(l + r, t);
    x.arcTo(l + w, t, l + w, t + h, r); x.arcTo(l + w, t + h, l, t + h, r);
    x.arcTo(l, t + h, l, t, r); x.arcTo(l, t, l + w, t, r);
    x.closePath();
  }
  function wrap(x, text, maxW, maxLines) {
    const out = []; let cur = '';
    for (const w of String(text).split(/\s+/)) {
      const t = cur ? cur + ' ' + w : w;
      if (x.measureText(t).width > maxW && cur) { out.push(cur); cur = w; } else cur = t;
    }
    if (cur) out.push(cur);
    if (out.length > maxLines) {
      out.length = maxLines;
      let last = out[maxLines - 1];
      while (last && x.measureText(last + '…').width > maxW) last = last.slice(0, -1);
      out[maxLines - 1] = last + '…';
    }
    return out.length ? out : ['—'];
  }

  // One routine for both passes: first only measures (draw=false) to find the height, then draws.
  function paint(x, d, draw, H) {
    const L = 60, T = 60, CW = W - 120, PAD = 64;
    const text = (s, px, py, font, color, align) => {
      x.font = font; x.fillStyle = color; x.textAlign = align || 'left';
      if (draw) x.fillText(s, px, py);
      x.textAlign = 'left';
    };
    if (draw) {
      x.fillStyle = '#eef2f7'; x.fillRect(0, 0, W, H);
      x.save(); x.shadowColor = 'rgba(15,23,42,.18)'; x.shadowBlur = 40; x.shadowOffsetY = 12;
      roundRect(x, L, T, CW, H - 120, 44); x.fillStyle = '#fff'; x.fill(); x.restore();
      x.save(); roundRect(x, L, T, CW, H - 120, 44); x.clip();
      const g = x.createLinearGradient(L, T, L + CW, T + 300);
      g.addColorStop(0, BLUE1); g.addColorStop(1, BLUE2);
      x.fillStyle = g; x.fillRect(L, T, CW, 300); x.restore();
      // ✓ badge
      const bx = L + CW - 130, by = T + 150;
      x.beginPath(); x.arc(bx, by, 64, 0, Math.PI * 2); x.fillStyle = 'rgba(255,255,255,.18)'; x.fill();
      x.beginPath(); x.arc(bx, by, 48, 0, Math.PI * 2); x.fillStyle = '#22c55e'; x.fill();
      x.strokeStyle = '#fff'; x.lineWidth = 11; x.lineCap = 'round'; x.lineJoin = 'round';
      x.beginPath(); x.moveTo(bx - 21, by + 2); x.lineTo(bx - 5, by + 19); x.lineTo(bx + 23, by - 15); x.stroke();
    }
    text(d.brand || 'Hanoi Old Quarter', L + PAD, T + 118, `800 58px ${FONT}`, '#fff');
    if ('letterSpacing' in x) x.letterSpacing = '5px';
    text('BOOKING CONFIRMATION', L + PAD, T + 184, `700 30px ${FONT}`, 'rgba(255,255,255,.92)');
    if ('letterSpacing' in x) x.letterSpacing = '0px';
    text('Xác nhận đặt phòng', L + PAD, T + 232, `500 27px ${FONT}`, 'rgba(255,255,255,.75)');

    let y = T + 300 + 82;
    text('GUEST', L + PAD, y, `700 26px ${FONT}`, MUTED);
    y += 64;
    x.font = `800 60px ${FONT}`;
    for (const ln of wrap(x, cleanName(d.name) || '—', CW - 2 * PAD, 2)) { text(ln, L + PAD, y, `800 60px ${FONT}`, INK); y += 70; }
    text('Booking no.  ' + (d.booking_id || ''), L + PAD, y + 2, `600 29px ${FONT}`, MUTED);
    y += 52;

    // Check-in / check-out boxes
    const gap = 28, bw = (CW - 2 * PAD - gap) / 2, bh = 176;
    [['CHECK-IN', d.checkin], ['CHECK-OUT', d.checkout]].forEach(([label, iso], i) => {
      const bx = L + PAD + i * (bw + gap);
      if (draw) { roundRect(x, bx, y, bw, bh, 26); x.fillStyle = '#f1f5f9'; x.fill(); }
      const [day, weekday] = dateParts(iso);
      text(label, bx + 30, y + 52, `800 26px ${FONT}`, BLUE2);
      text(day, bx + 30, y + 113, `800 46px ${FONT}`, INK);
      text(weekday, bx + 30, y + 152, `600 28px ${FONT}`, MUTED);
    });
    y += bh + 62;

    // Detail rows (label left, value right, up to 2 lines)
    const rows = [];
    if (d.nights) rows.push(['Nights', `${d.nights} night${d.nights > 1 ? 's' : ''}`]);
    if (d.room) rows.push(['Room', d.room]);
    if (d.address) rows.push(['Address', d.address]);
    if (d.total) rows.push(['Total', money(d.total)]);
    if (d.paid) rows.push(['Payment', 'Paid ✓', GREEN]);
    rows.forEach(([label, value, color], i) => {
      text(label, L + PAD, y, `600 31px ${FONT}`, MUTED);
      x.font = `700 33px ${FONT}`;
      const vl = wrap(x, value, CW - 2 * PAD - 230, 2);
      vl.forEach((ln, k) => text(ln, L + CW - PAD, y + k * 42, `700 33px ${FONT}`, color || INK, 'right'));
      y += 42 * (vl.length - 1);
      if (i < rows.length - 1) {
        y += 30;
        if (draw) { x.strokeStyle = LINE; x.lineWidth = 2; x.beginPath(); x.moveTo(L + PAD, y); x.lineTo(L + CW - PAD, y); x.stroke(); }
        y += 60;
      }
    });

    y += 92;
    text('We look forward to welcoming you!', W / 2, y, `700 33px ${FONT}`, BLUE2, 'center');
    return y + 70 + 60;              // card bottom padding + outer margin
  }

  function draw(d) {
    const measure = document.createElement('canvas').getContext('2d');
    const H = Math.ceil(paint(measure, d, false));
    const c = document.createElement('canvas');
    c.width = W; c.height = H;
    paint(c.getContext('2d'), d, true, H);
    return c;
  }

  let cssDone = false;
  function ensureCss() {
    if (cssDone) return;
    cssDone = true;
    const s = document.createElement('style');
    s.textContent = `
      .hc-ov{position:fixed;inset:0;z-index:99999;background:rgba(15,23,42,.62);display:flex;align-items:center;justify-content:center;padding:14px;}
      .hc-box{background:#fff;border-radius:16px;max-width:440px;width:100%;max-height:94vh;overflow:auto;padding:12px;box-shadow:0 20px 50px rgba(0,0,0,.35);}
      .hc-head{display:flex;align-items:center;gap:8px;margin:0 0 8px;}
      .hc-title{flex:1;min-width:0;font-weight:800;font-size:.95rem;color:#0f172a;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
      .hc-x{border:none;background:#f1f5f9;color:#334155;width:34px;height:34px;border-radius:50%;font-size:1rem;font-weight:800;cursor:pointer;flex-shrink:0;}
      .hc-img{display:block;width:100%;height:auto;max-height:46vh;object-fit:contain;background:#f8fafc;border-radius:10px;border:1px solid #e2e8f0;}
      .hc-btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;}
      .hc-btns button,.hc-btns a{flex:1 1 40%;display:flex;align-items:center;justify-content:center;text-align:center;border:none;border-radius:12px;padding:13px 8px;font-weight:800;font-size:.95rem;cursor:pointer;text-decoration:none;font-family:inherit;}
      .hc-share{background:#16a34a;color:#fff;flex-basis:100% !important;font-size:1rem !important;}
      .hc-copy{background:#2563eb;color:#fff;} .hc-dl{background:#e0e7ff;color:#1e3a8a;}
      .hc-note{font-size:.78rem;color:#64748b;margin-top:8px;line-height:1.45;}
      .hc-note a{color:#2563eb;font-weight:700;}
      .hc-load{padding:30px 10px;text-align:center;font-weight:700;color:#334155;}`;
    document.head.appendChild(s);
  }

  const shotUrl = (bookingId, v) => `/api/booking_screenshot/${encodeURIComponent(bookingId)}?v=${v}&t=${Date.now()}`;

  // The picture sent to the guest: the Booking.com screenshot (guest version — commission and
  // internal notes covered) when the extension has taken one, otherwise the drawn card.
  async function getImage(bookingId) {
    const d = await fetch('/api/booking_card/' + encodeURIComponent(bookingId)).then(r => r.json());
    if (!d.success) throw new Error(d.error || 'Không lấy được dữ liệu');
    let blob = null;
    if (d.shot) {
      const res = await fetch(shotUrl(bookingId, 'guest'));
      if (res.ok) blob = await res.blob();
    }
    const isShot = !!blob;
    if (!blob) blob = await new Promise(res => draw(d).toBlob(res, 'image/png'));
    const fname = `booking-${d.booking_id}.${blob.type === 'image/jpeg' ? 'jpg' : 'png'}`;
    return { d, blob, isShot, fname, file: new File([blob], fname, { type: blob.type || 'image/png' }) };
  }

  // JPEG → PNG: Safari can only put PNG pictures on the clipboard
  function toPng(blob) {
    if (blob.type === 'image/png') return Promise.resolve(blob);
    return new Promise((res, rej) => {
      const u = URL.createObjectURL(blob), img = new Image();
      img.onload = () => {
        const c = document.createElement('canvas');
        c.width = img.naturalWidth; c.height = img.naturalHeight;
        c.getContext('2d').drawImage(img, 0, 0);
        URL.revokeObjectURL(u);
        c.toBlob(b => (b ? res(b) : rej(new Error('Không đổi được ảnh'))), 'image/png');
      };
      img.onerror = () => { URL.revokeObjectURL(u); rej(new Error('Ảnh bị lỗi')); };
      img.src = u;
    });
  }

  async function open(bookingId) {
    ensureCss();
    let url = null;
    const ov = document.createElement('div');
    ov.className = 'hc-ov';
    ov.innerHTML = '<div class="hc-box"><div class="hc-load">⏳ Đang tạo ảnh xác nhận…</div></div>';
    document.body.appendChild(ov);
    const close = () => { ov.remove(); if (url) URL.revokeObjectURL(url); };
    ov.addEventListener('click', e => { if (e.target === ov) close(); });
    const box = ov.querySelector('.hc-box');
    try {
      const { d, blob, isShot, fname, file } = await getImage(bookingId);   // always the latest picture
      url = URL.createObjectURL(blob);
      const canShare = !!(navigator.canShare && navigator.canShare({ files: [file] }));
      const canCopy = !!(navigator.clipboard && navigator.clipboard.write && window.ClipboardItem);
      const png = canCopy ? toPng(blob) : null;      // prepared now, so "Sao chép" works inside the tap
      if (png) png.catch(() => {});
      const name = cleanName(d.name).replace(/</g, '&lt;');
      box.innerHTML = `
        <div class="hc-head"><div class="hc-title">📷 Ảnh xác nhận · ${name}</div>
          <button type="button" class="hc-x" aria-label="Đóng">✕</button></div>
        <img class="hc-img" src="${url}" alt="Booking confirmation">
        <div class="hc-btns">
          ${canShare ? '<button type="button" class="hc-share">📤 Gửi ảnh (WhatsApp / Zalo…)</button>' : ''}
          ${canCopy ? '<button type="button" class="hc-copy">📋 Sao chép ảnh</button>' : ''}
          <a class="hc-dl" href="${url}" download="${fname}">⬇️ Tải ảnh</a>
        </div>
        <div class="hc-note">${canShare
          ? '<b>Gửi ảnh</b> → chọn WhatsApp hoặc Zalo → chọn khách → Gửi. Hoặc <b>Sao chép ảnh</b> rồi dán vào khung chat của khách.'
          : '<b>Sao chép ảnh</b> rồi dán (Ctrl+V) vào WhatsApp Web / Zalo, hoặc <b>Tải ảnh</b>.'}
          ${isShot
            ? '<br>📸 Ảnh chụp từ Booking — bản gửi khách (đã che hoa hồng, ghi chú nội bộ). <a href="#" class="hc-full">Xem bản đầy đủ</a>'
            : '<br>Ảnh tự tạo — chưa có ảnh chụp từ Booking. Mở đặt phòng này trên máy tính là tiện ích tự chụp.'}</div>`;
      box.querySelector('.hc-x').onclick = close;
      const fullLink = box.querySelector('.hc-full');
      if (fullLink) {
        let showingFull = false, fullUrl = null;
        fullLink.onclick = async e => {       // owner view only — sending always uses the guest version
          e.preventDefault();
          const imgEl = box.querySelector('.hc-img');
          if (!showingFull) {
            if (!fullUrl) { const r = await fetch(shotUrl(bookingId, 'full')); if (!r.ok) return; fullUrl = URL.createObjectURL(await r.blob()); }
            imgEl.src = fullUrl; fullLink.textContent = 'Xem bản gửi khách'; showingFull = true;
          } else {
            imgEl.src = url; fullLink.textContent = 'Xem bản đầy đủ'; showingFull = false;
          }
        };
      }
      const share = box.querySelector('.hc-share');
      if (share) share.onclick = async () => {
        try { await navigator.share({ files: [file] }); }
        catch (e) { if (e.name !== 'AbortError') box.querySelector('.hc-note').textContent = '❌ ' + e.message; }
      };
      const cp = box.querySelector('.hc-copy');
      if (cp) cp.onclick = async () => {
        try {
          await navigator.clipboard.write([new ClipboardItem({ 'image/png': png })]);
          cp.textContent = '✅ Đã sao chép — dán vào chat';
        } catch (e) { cp.textContent = 'Không sao chép được — dùng Tải ảnh'; }
      };
    } catch (e) {
      box.innerHTML = `<div class="hc-load">❌ ${String(e.message || e).replace(/</g, '&lt;')}</div>
        <div class="hc-btns"><button type="button" class="hc-close">Đóng</button></div>`;
      box.querySelector('.hc-close').onclick = close;
    }
  }

  window.HotelCard = { open, draw, quickShare: open };   // 📷 always shows the preview first
})();
