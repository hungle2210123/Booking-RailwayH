// Guest journey "send" sheet: one guest, one step (👋 🕐 🛂 🧳 🔑 💳 ⭐) at a time — the message for the
// guest's apartment (editable), its pictures, and the ways to send it. Used by /messages and calendar_details.
//   Journey.open(bookingId, stepKey, {pickApt})   stepKey '__more' = pick any Mẫu Câu template,
//                                                 'cat:<group>' = a pinned template group, pickApt = open the apartment list
// wa.me links carry text only, so a step with pictures is sent through the phone's share sheet
// (pictures + text together); the text is also copied, in case the app drops it.
(function () {
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let st = null;            // { bid, data, step, text, files, more: {template, text, images} }

  function css() {
    if (document.getElementById('jr-css')) return;
    const s = document.createElement('style');
    s.id = 'jr-css';
    s.textContent = `
      .jr-ov{position:fixed;inset:0;z-index:99990;background:rgba(15,23,42,.55);display:flex;align-items:flex-end;justify-content:center;}
      .jr{background:#fff;width:100%;max-width:560px;max-height:93vh;overflow:auto;border-radius:18px 18px 0 0;
          box-shadow:0 -10px 40px rgba(0,0,0,.3);padding:0 14px 16px;font-family:inherit;}
      @media(min-width:700px){.jr-ov{align-items:center}.jr{border-radius:18px}}
      .jr-h{position:sticky;top:0;background:#fff;padding:12px 0 8px;z-index:2;border-bottom:1px solid #f1f5f9;}
      .jr-top{display:flex;align-items:center;gap:8px;}
      .jr-name{flex:1;min-width:0;font-weight:800;font-size:1.02rem;color:#0f172a;overflow-wrap:anywhere;}
      .jr-name .jr-apt{display:table;margin:4px 0 0;}
      .jr-x{border:none;background:#f1f5f9;width:34px;height:34px;border-radius:50%;font-weight:800;cursor:pointer;flex-shrink:0;}
      .jr-meta{font-size:.78rem;color:#64748b;margin-top:2px;}
      .jr-apt{display:inline-block;font-size:.72rem;font-weight:800;border-radius:999px;padding:2px 9px;background:#e0f2fe;color:#075985;
          margin-left:6px;border:1px solid #7dd3fc;cursor:pointer;font-family:inherit;}
      .jr-pick button.cur{background:#f59e0b;color:#fff;}
      .jr-pick button.clear{border-color:#cbd5e1;color:#64748b;}
      .jr-edit{border:none;background:none;color:#2563eb;font-weight:800;font-size:.74rem;cursor:pointer;padding:0;font-family:inherit;}
      .jr-editbox{background:#fefce8;border:1px solid #fde68a;border-radius:12px;padding:9px;margin-top:8px;}
      .jr-editbox .jr-ta{min-height:200px;background:#fff;}
      .jr-save{background:#2563eb;} .jr-cancel{background:#94a3b8;}
      .jr-pick{margin-top:6px;padding:7px 8px;background:#fffbeb;border:1px solid #fde68a;border-radius:10px;font-size:.78rem;color:#92400e;}
      .jr-pick button{margin:4px 4px 0 0;border:1.5px solid #f59e0b;background:#fff;color:#92400e;font-weight:800;border-radius:9px;padding:5px 9px;cursor:pointer;font-family:inherit;font-size:.78rem;}
      .jr-steps{display:flex;gap:6px;overflow-x:auto;padding:8px 0 2px;scrollbar-width:none;}
      .jr-steps::-webkit-scrollbar{display:none}
      .jr-steps button{flex-shrink:0;border:1.5px solid #e2e8f0;background:#f8fafc;border-radius:999px;padding:5px 10px;
          font-size:.76rem;font-weight:700;color:#334155;cursor:pointer;font-family:inherit;white-space:nowrap;}
      .jr-steps button.on{background:#0f172a;color:#fff;border-color:#0f172a;}
      .jr-steps button.sent{border-color:#86efac;background:#dcfce7;color:#166534;}
      .jr-steps button.sent.on{background:#166534;color:#fff;border-color:#166534;}
      .jr-steps button.next{border-color:#2563eb;}
      .jr-tpl{font-size:.74rem;color:#64748b;margin:10px 0 4px;}
      .jr-tpl b{color:#334155;}
      .jr-ta{width:100%;min-height:150px;border:1.5px solid #e2e8f0;border-radius:12px;padding:9px;font-size:.9rem;line-height:1.45;
          font-family:inherit;resize:vertical;box-sizing:border-box;}
      .jr-imgs{display:flex;gap:7px;overflow-x:auto;margin-top:8px;}
      .jr-imgs img{height:96px;border-radius:9px;border:1px solid #e2e8f0;cursor:zoom-in;flex-shrink:0;background:#f8fafc;}
      .jr-noimg{font-size:.74rem;color:#94a3b8;margin-top:6px;}
      .jr-btns{display:grid;grid-template-columns:1fr 1fr;gap:7px;margin-top:11px;}
      .jr-btns a,.jr-btns button{display:flex;align-items:center;justify-content:center;gap:5px;border:none;border-radius:12px;
          padding:12px 6px;font-weight:800;font-size:.9rem;cursor:pointer;text-decoration:none;font-family:inherit;color:#fff;text-align:center;}
      .jr-btns .wide{grid-column:1/-1;font-size:1rem;}
      .jr-share{background:#16a34a;} .jr-wa{background:#25d366;} .jr-zalo{background:#0068ff;} .jr-sms{background:#2563eb;}
      .jr-copy{background:#475569;} .jr-imgonly{background:#7c3aed;}
      .jr-btns .off{opacity:.45;pointer-events:none;}
      .jr-sent{display:flex;align-items:center;gap:8px;margin-top:12px;font-size:.85rem;font-weight:700;color:#334155;}
      .jr-sent input{width:20px;height:20px;}
      .jr-note{font-size:.76rem;color:#64748b;margin-top:8px;line-height:1.45;}
      .jr-warn{font-size:.82rem;color:#92400e;background:#fffbeb;border:1px solid #fde68a;border-radius:10px;padding:9px 10px;margin-top:10px;}
      .jr-search{width:100%;border:1.5px solid #e2e8f0;border-radius:10px;padding:8px 10px;font-size:.9rem;margin-top:10px;box-sizing:border-box;font-family:inherit;}
      .jr-cat{font-size:.74rem;font-weight:800;color:#64748b;margin:10px 0 4px;}
      .jr-t{display:block;width:100%;text-align:left;border:1px solid #e2e8f0;background:#fff;border-radius:10px;padding:8px 10px;margin-bottom:5px;
          font-size:.84rem;font-weight:600;color:#0f172a;cursor:pointer;font-family:inherit;}
      .jr-t small{color:#7c3aed;font-weight:800;}
      .jr-row{display:flex;gap:5px;align-items:stretch;}
      .jr-row .jr-t{flex:1;min-width:0;}
      .jr-pin{flex-shrink:0;border:1px solid #e2e8f0;background:#fff;border-radius:10px;width:40px;margin-bottom:5px;cursor:pointer;font-size:.95rem;filter:grayscale(1);opacity:.5;}
      .jr-pin.on{filter:none;opacity:1;background:#fff7ed;border-color:#fdba74;}
      .jr-cath{display:flex;align-items:center;justify-content:space-between;gap:8px;}
      .jr-catpin{border:1px solid #e2e8f0;background:#fff;border-radius:999px;padding:3px 9px;font-size:.7rem;font-weight:800;color:#64748b;cursor:pointer;font-family:inherit;margin-top:6px;}
      .jr-catpin.on{background:#ffedd5;border-color:#fdba74;color:#9a3412;}
      .jr-hint{font-size:.74rem;color:#9a3412;background:#fff7ed;border-radius:9px;padding:6px 9px;margin-top:8px;}
      .jr-zoom{position:fixed;inset:0;z-index:99995;background:rgba(0,0,0,.88);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:14px;gap:10px;}
      .jr-zoom img{max-width:100%;max-height:78vh;border-radius:8px;}
      .jr-zoom div{display:flex;gap:8px;}
      .jr-zoom button,.jr-zoom a{border:none;border-radius:10px;padding:10px 14px;font-weight:800;cursor:pointer;font-family:inherit;text-decoration:none;color:#0f172a;background:#fff;font-size:.88rem;}
      .jr-toast{position:fixed;left:50%;bottom:22px;transform:translateX(-50%);background:#0f172a;color:#fff;font-size:.85rem;padding:9px 16px;
          border-radius:999px;z-index:99999;opacity:0;transition:opacity .2s;pointer-events:none;}
      .jr-toast.show{opacity:1;}`;
    document.head.appendChild(s);
  }

  function toast(msg) {
    let t = document.querySelector('.jr-toast');
    if (!t) { t = document.createElement('div'); t.className = 'jr-toast'; document.body.appendChild(t); }
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('show'), 2400);
  }
  function copyText(text) {
    const fallback = () => {
      const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta);
      ta.select(); try { document.execCommand('copy'); } catch (e) {} ta.remove();
    };
    try { return navigator.clipboard.writeText(text).catch(fallback); } catch (e) { fallback(); return Promise.resolve(); }
  }

  // ── open / load ──────────────────────────────────────────────────────────────
  const cache = new Map();          // bid → { p: promise of the guest data, at }
  function fetchGuest(bid) {
    const c = cache.get(bid);
    if (c && Date.now() - c.at < 20000) return c.p;
    const p = fetch('/api/journey/guest/' + encodeURIComponent(bid)).then(r => r.json());
    cache.set(bid, { p, at: Date.now() });
    p.catch(() => cache.delete(bid));
    return p;
  }
  // start loading while the finger is still on the chip (saves the network wait on tap)
  document.addEventListener('pointerdown', e => {
    const chip = e.target.closest && e.target.closest('.jchip[data-bid], .guest-journey[data-bid]');
    if (chip) fetchGuest(chip.dataset.bid);
  }, { passive: true });

  async function open(bid, step, opts) {
    css();
    close();
    const ov = document.createElement('div');
    ov.className = 'jr-ov';
    ov.innerHTML = '<div class="jr"><div style="padding:30px;text-align:center;font-weight:700;color:#334155">⏳ Đang tải…</div></div>';
    ov.addEventListener('click', e => { if (e.target === ov) close(); });
    document.body.appendChild(ov);
    try {
      const data = await fetchGuest(bid);
      if (!data.success) { cache.delete(bid); throw new Error(data.error || 'Lỗi tải dữ liệu'); }
      st = { bid, data, step: step || data.recommended || data.steps[0].key, ov, pickApt: !!(opts && opts.pickApt) };
      render();
    } catch (e) {
      ov.querySelector('.jr').innerHTML = `<div style="padding:24px;text-align:center;color:#b91c1c;font-weight:700">❌ ${esc(e.message)}</div>`;
    }
  }
  function close() {
    document.querySelectorAll('.jr-ov').forEach(o => o.remove());
    const reload = st && st.pinsChanged && document.querySelector('.jstrip');
    const had = !!st;
    st = null;
    if (reload) location.reload();
    else if (had && window.MsgLive) setTimeout(window.MsgLive.refresh, 700);   // ✅ Đã nhắn on the card
  }
  const curStep = () => st.data.steps.find(s => s.key === st.step);

  // ── render ───────────────────────────────────────────────────────────────────
  function render() {
    const b = st.data.booking;
    const box = st.ov.querySelector('.jr');
    const showPick = !b.apt || st.pickApt;
    const pick = !showPick ? '' : `<div class="jr-pick">${b.apt ? 'Đổi căn cho khách:' : '⚠️ Khách chưa xếp căn — chọn căn để gửi đúng địa chỉ & hướng dẫn:'}<br>
        ${b.apartments.map(a => `<button type="button" data-apt="${a.id}" class="${b.apt && b.apt.id === a.id ? 'cur' : ''}">${esc(a.name)}</button>`).join('')}
        ${b.apt ? '<button type="button" data-apt="" class="clear">✕ Bỏ xếp căn</button>' : ''}</div>`;
    box.innerHTML = `
      <div class="jr-h">
        <div class="jr-top"><div class="jr-name">${esc(b.name)}${b.apt ? `<button type="button" class="jr-apt" title="Đổi căn">🏠 ${esc(b.apt.name)} · ✏️ đổi căn</button>` : ''}</div>
          <button type="button" class="jr-x" aria-label="Đóng">✕</button></div>
        <div class="jr-meta">${esc(b.nhan)} → ${esc(b.tra)}${b.phong ? ' · ' + esc(b.phong) : ''}
          ${b.partner ? ' · 🤝 qua đối tác' : (b.phone ? ' · 📞 ' + esc(b.phone) : ' · chưa có số')}</div>
        ${pick}
        <div class="jr-steps"></div>
      </div>
      <div class="jr-body"></div>`;
    box.querySelector('.jr-x').onclick = close;
    drawTabs();
    box.querySelectorAll('.jr-pick button').forEach(btn => btn.onclick = () => setApartment(btn.dataset.apt));
    const aptBtn = box.querySelector('.jr-apt');
    if (aptBtn) aptBtn.onclick = () => { st.pickApt = !st.pickApt; render(); };
    const body = box.querySelector('.jr-body');
    if (st.step === '__more') renderMore(body);
    else if (st.step.startsWith('cat:')) renderMore(body, st.step.slice(4));
    else if (st.step.startsWith('fav:')) renderFav(body, (st.data.favorites || []).find(f => f.key === st.step));
    else renderStep(body, curStep());
  }

  // step tabs = steps the owner shows + pinned templates / groups + ➕
  function drawTabs() {
    const wrap = st.ov.querySelector('.jr-steps');
    const hidden = st.data.hidden || [];
    const tabs = st.data.steps.filter(s => !hidden.includes(s.key) || s.key === st.step).concat(st.data.favorites || []);
    wrap.innerHTML = tabs.map(s => `<button type="button" data-k="${esc(s.key)}"
        class="${s.key === st.step ? 'on' : ''} ${s.sent_at ? 'sent' : ''} ${s.key === st.data.recommended ? 'next' : ''}">
        ${s.emoji} ${esc(s.label)}${s.sent_at ? ' ✓' : ''}</button>`).join('')
      + `<button type="button" data-k="__more" class="${st.step === '__more' ? 'on' : ''}">➕ Tin khác</button>`;
    wrap.querySelectorAll('button').forEach(btn => btn.onclick = () => { st.step = btn.dataset.k; st.more = null; render(); });
    const on = wrap.querySelector('.on');
    if (on) on.scrollIntoView({ inline: 'center', block: 'nearest' });
  }

  function renderStep(body, s) {
    if (s.needs_apt) {
      body.innerHTML = `<div class="jr-warn">Bước <b>${s.emoji} ${esc(s.label)}</b> khác nhau theo căn — chọn căn của khách ở trên trước.</div>`;
      return;
    }
    if (!s.template) {
      body.innerHTML = `<div class="jr-warn">Chưa chọn mẫu tin cho bước này${st.data.booking.apt ? ' ở căn ' + esc(st.data.booking.apt.name) : ''}.
        Vào <a href="/journey">⚙️ Tin &amp; ảnh</a> để chọn.</div>`;
      return;
    }
    editor(body, s.template, s.text, s.images, s);
  }

  // The editable message + pictures + send buttons (a step, or a template picked in "Tin khác")
  function editor(body, template, text, images, step) {
    const b = st.data.booking, L = b.links;
    st.text = text; st.files = null;
    body.innerHTML = `
      <div class="jr-tpl">Mẫu: <b>${esc(template.name)}</b> · ô dưới sửa được cho lần gửi này (vd. số phòng) ·
        <button type="button" class="jr-edit">✏️ Sửa mẫu gốc</button></div>
      <textarea class="jr-ta">${esc(text)}</textarea>
      ${images.length ? `<div class="jr-imgs">${images.map(im => `<img alt="" data-url="${esc(im.url)}">`).join('')}</div>`
                      : '<div class="jr-noimg">Bước này chưa có ảnh — thêm ở ⚙️ Tin &amp; ảnh.</div>'}
      <div class="jr-btns"></div>
      ${step ? `<label class="jr-sent"><input type="checkbox" ${step.sent_at ? 'checked' : ''}> Đã gửi bước này</label>` : ''}
      <div class="jr-note"></div>`;
    const ta = body.querySelector('.jr-ta');
    ta.addEventListener('input', () => { st.text = ta.value; refreshLinks(); });
    body.querySelector('.jr-edit').onclick = () => editTemplate(body, template);
    body.querySelectorAll('.jr-imgs img').forEach(img => img.onclick = () => zoom(img.dataset.url));
    const btns = body.querySelector('.jr-btns');
    const note = body.querySelector('.jr-note');
    const shareOk = !!(navigator.canShare);
    const sent = () => step && markSent(step, true);

    if (images.length && shareOk) {
      btns.insertAdjacentHTML('beforeend', `<button type="button" class="jr-share wide off">⏳ Đang tải ${images.length} ảnh…</button>`);
    }
    if (L) {
      btns.insertAdjacentHTML('beforeend', `
        <a class="jr-wa ${images.length ? '' : 'wide'}" target="_blank" rel="noopener">🟢 WhatsApp${images.length ? ' (chữ)' : ''}</a>
        <a class="jr-zalo" target="_blank" rel="noopener">🔵 Zalo</a>
        <a class="jr-sms">💬 SMS</a>`);
    }
    btns.insertAdjacentHTML('beforeend', `<button type="button" class="jr-copy">📋 Chép tin</button>`);
    if (images.length && shareOk) btns.insertAdjacentHTML('beforeend', `<button type="button" class="jr-imgonly off">🖼 Chỉ gửi ảnh</button>`);

    function refreshLinks() {
      if (!L) return;
      const enc = encodeURIComponent(st.text);
      btns.querySelector('.jr-wa').href = `https://wa.me/${L.wa}?text=${enc}`;
      btns.querySelector('.jr-zalo').href = `https://zalo.me/${L.zalo}`;
      btns.querySelector('.jr-sms').href = `sms:${L.sms}?&body=${enc}`;
    }
    refreshLinks();
    if (L) {
      btns.querySelector('.jr-wa').addEventListener('click', sent);
      btns.querySelector('.jr-sms').addEventListener('click', sent);
      btns.querySelector('.jr-zalo').addEventListener('click', () => { copyText(st.text); toast('Đã chép tin — dán vào Zalo'); sent(); });
    }
    btns.querySelector('.jr-copy').onclick = () => { copyText(st.text); toast('Đã chép tin nhắn'); };

    note.innerHTML = b.partner
      ? '🤝 Khách đặt qua đối tác: chép tin rồi dán vào khung chat Booking (trên máy tính có nút 💬 Điền tin).'
      : (images.length && shareOk
          ? '<b>Gửi tin + ảnh</b> → chọn WhatsApp (hoặc Zalo) → chọn khách → Gửi. Lần đầu nhắn khách mới: bấm <b>WhatsApp (chữ)</b> trước để mở đúng chat, rồi gửi ảnh.'
          : (L ? 'Bấm <b>WhatsApp</b> → mở đúng chat của khách với tin soạn sẵn → Gửi.' : 'Khách chưa có số: chép tin để gửi qua kênh khác.'));

    // Pictures are downloaded once: shown as thumbnails and kept ready, so the share sheet can open
    // straight from the tap
    const thumbs = body.querySelectorAll('.jr-imgs img');
    if (images.length) {
      Promise.all(images.map((im, i) => fetch(im.url).then(r => r.ok ? r.blob() : null).then(bl => {
        if (!bl) return null;
        if (thumbs[i]) thumbs[i].src = URL.createObjectURL(bl);
        return new File([bl], `${(template.name || 'guide').replace(/[^\w-]+/g, '_').slice(0, 30)}-${i + 1}.${bl.type === 'image/png' ? 'png' : 'jpg'}`, { type: bl.type || 'image/jpeg' });
      }).catch(() => null)))
        .then(files => {
          if (!st || !shareOk) return;
          st.files = files.filter(Boolean);
          const share = btns.querySelector('.jr-share'), only = btns.querySelector('.jr-imgonly');
          if (!st.files.length || !navigator.canShare({ files: st.files })) {
            share.textContent = 'Máy này không gửi ảnh trực tiếp được'; return;
          }
          share.classList.remove('off'); only.classList.remove('off');
          share.textContent = `📤 Gửi tin + ${st.files.length} ảnh`;
          share.onclick = () => {
            copyText(st.text);                        // in case the app keeps only the pictures
            navigator.share({ files: st.files, text: st.text }).then(sent).catch(e => {
              if (e.name !== 'AbortError') note.textContent = '❌ ' + e.message;
            });
          };
          only.onclick = () => navigator.share({ files: st.files }).then(sent).catch(() => {});
        });
    }
    const cb = body.querySelector('.jr-sent input');
    if (cb) cb.onchange = () => markSent(step, cb.checked);
  }

  // A pinned template ("Check in trễ", "Nhắc để chìa"…): filled in for this guest, tracked like a step
  async function renderFav(body, fav) {
    if (!fav) { body.innerHTML = '<div class="jr-warn">Mẫu ghim này không còn — chỉnh ở ⚙️ Nút, tin &amp; ảnh.</div>'; return; }
    st.favCache = st.favCache || {};
    let c = st.favCache[fav.key];
    if (!c) {
      body.innerHTML = '<div style="padding:16px;color:#64748b">⏳ Đang tải…</div>';
      c = await fetch(`/api/journey/compose?booking_id=${encodeURIComponent(st.bid)}&template_id=${fav.id}`).then(x => x.json()).catch(() => null);
      if (!c || !c.success) { body.innerHTML = '<div class="jr-warn">Không tải được mẫu.</div>'; return; }
      st.favCache[fav.key] = c;
    }
    if (!st || st.step !== fav.key) return;
    editor(body, c.template, c.text, c.images, fav);
  }

  // Edit the template's own text (with {ten} {nhan} {tra} {phong} {can}) — saved for every guest
  async function editTemplate(body, template) {
    const r = await fetch('/api/templates/' + template.id).then(x => x.json()).catch(() => null);
    if (!r || !r.success) { toast('Không tải được mẫu'); return; }
    const box = document.createElement('div');
    box.className = 'jr-editbox';
    box.innerHTML = `<div class="jr-tpl" style="margin-top:0">✏️ Sửa mẫu gốc <b>${esc(template.name)}</b> — lưu là dùng cho <b>mọi khách</b>.
        Tự thay: {ten} tên · {nhan} ngày nhận · {tra} ngày trả · {phong} (phòng) · {can} tên căn</div>
      <textarea class="jr-ta">${esc(r.template.Message || '')}</textarea>
      <div class="jr-btns"><button type="button" class="jr-cancel">Huỷ</button><button type="button" class="jr-save">💾 Lưu mẫu</button></div>`;
    body.innerHTML = '';
    body.appendChild(box);
    box.querySelector('.jr-cancel').onclick = () => render();
    box.querySelector('.jr-save').onclick = async () => {
      const content = box.querySelector('.jr-ta').value.trim();
      if (!content) { toast('Mẫu không được để trống'); return; }
      const res = await fetch('/api/templates/' + template.id, { method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ Message: content }) }).then(x => x.json()).catch(() => null);
      if (!res || !res.success) { toast('❌ ' + ((res && res.error) || 'Không lưu được')); return; }
      toast('✅ Đã lưu mẫu');
      const bid = st.bid, keep = st.step;
      cache.delete(bid);
      if (st.favCache) delete st.favCache[keep];
      if (keep === '__more') {                   // refresh the picked template too
        const c = await fetch(`/api/journey/compose?booking_id=${encodeURIComponent(bid)}&template_id=${template.id}`).then(x => x.json());
        await open(bid, keep);
        if (st && c.success) { st.more = c; render(); }
      } else {
        await open(bid, keep);
      }
    };
  }

  // ── "➕ Tin khác": any template from Mẫu Câu ───────────────────────────────────
  async function renderMore(body, cat) {
    if (st.more) { editor(body, st.more.template, st.more.text, st.more.images, null); return; }
    body.innerHTML = '<div style="padding:16px;color:#64748b">⏳ Đang tải mẫu…</div>';
    if (!tplList) {
      const r = await fetch('/api/journey/templates').then(x => x.json()).catch(() => null);
      if (!r || !r.success) { body.innerHTML = '<div class="jr-warn">Không tải được danh sách mẫu.</div>'; return; }
      tplList = r.templates;
    }
    if (!st) return;
    const favs = () => (st.data.favorites || []);
    const pinnedT = id => favs().some(f => f.id === id);
    const pinnedC = c => favs().some(f => f.cat === c);
    const all = cat ? tplList.filter(t => (t.category || '') === cat) : tplList;
    const draw = q => {
      const f = s => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/đ/g, 'd');
      const list = all.filter(t => !q || f(t.name + ' ' + t.category).includes(f(q)));
      const groups = {};
      list.forEach(t => (groups[t.category || ''] = groups[t.category || ''] || []).push(t));
      return Object.keys(groups).sort((a, b) => a.localeCompare(b, 'vi', { numeric: true })).map(c =>
        (cat ? '' : `<div class="jr-cath"><div class="jr-cat">${esc(c || 'Khác')}</div>${c ? `<button type="button" class="jr-catpin ${pinnedC(c) ? 'on' : ''}"
            data-cat="${esc(c)}">📌 ${pinnedC(c) ? 'Đã ghim nhóm' : 'Ghim nhóm'}</button>` : ''}</div>`)
        + groups[c].map(t => `<div class="jr-row"><button type="button" class="jr-t" data-id="${t.id}">${esc(t.name)}${t.images ? ` <small>🖼${t.images}</small>` : ''}</button>
            <button type="button" class="jr-pin ${pinnedT(t.id) ? 'on' : ''}" data-pin="${t.id}" title="Ghim mẫu này thành nút trên thẻ khách">📌</button></div>`).join('')).join('')
        || '<div class="jr-noimg">Không có mẫu nào khớp.</div>';
    };
    body.innerHTML = (cat ? `<div class="jr-cath"><div class="jr-cat">${esc(cat)}</div>
          <button type="button" class="jr-catpin on" data-cat="${esc(cat)}">📌 Đã ghim nhóm</button></div>` : '')
      + `<input class="jr-search" placeholder="🔎 Tìm mẫu: check in trễ, taxi, giặt, chìa khoá…"><div class="jr-list">${draw('')}</div>`
      + (cat ? '' : '<div class="jr-hint">📌 = ghim thành nút trên thẻ khách (một mẫu, hoặc cả nhóm như CHANGE / Xin hủy). Bấm lại để bỏ ghim.</div>');
    const list = body.querySelector('.jr-list');
    const bind = () => {
      body.querySelectorAll('.jr-t').forEach(btn => btn.onclick = async () => {
        const c = await fetch(`/api/journey/compose?booking_id=${encodeURIComponent(st.bid)}&template_id=${btn.dataset.id}`).then(x => x.json());
        if (!c.success) { toast(c.error || 'Lỗi'); return; }
        st.more = c;
        editor(body, c.template, c.text, c.images, null);
      });
      body.querySelectorAll('.jr-pin').forEach(btn => btn.onclick = () => togglePin({ id: +btn.dataset.pin }, () => list.innerHTML = draw(q()) , bind));
      body.querySelectorAll('.jr-catpin').forEach(btn => btn.onclick = () => togglePin({ cat: btn.dataset.cat }, () => {
        if (cat) { st.step = '__more'; render(); } else list.innerHTML = draw(q());
      }, bind));
    };
    const q = () => body.querySelector('.jr-search').value;
    body.querySelector('.jr-search').addEventListener('input', () => { list.innerHTML = draw(q()); bind(); });
    bind();
  }
  let tplList = null;

  // a short button for a pinned group: "CHANGE" → 🔁 Change, "7 · Xin hủy & Giảm giá" → ❌ Xin hủy
  function catButton(cat) {
    if (/change/i.test(cat)) return { cat, emoji: '🔁', label: 'Change' };
    if (/sự cố/i.test(cat)) return { cat, emoji: '🛠️', label: 'Sự cố phòng' };
    if (/hủy/i.test(cat)) return { cat, emoji: '❌', label: 'Xin hủy' };
    return { cat, emoji: '📂', label: '' };
  }

  // 📌 pin / unpin a template ({id}) or a whole group ({cat}) as a button on every guest card
  async function togglePin(item, redraw, rebind) {
    const prefs = await fetch('/api/journey/prefs').then(x => x.json()).catch(() => null);
    if (!prefs || !prefs.success || !st) { toast('Không lưu được'); return; }
    const same = f => (item.id && f.id === item.id) || (item.cat && f.cat === item.cat);
    const had = prefs.prefs.favorites.some(same);
    const favorites = had ? prefs.prefs.favorites.filter(f => !same(f))
      : prefs.prefs.favorites.concat([item.cat ? catButton(item.cat) : { id: item.id }]);
    const r = await fetch('/api/journey/prefs', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hidden: prefs.prefs.hidden, favorites }) }).then(x => x.json()).catch(() => null);
    if (!r || !r.success || !st) { toast('Không lưu được'); return; }
    const old = {};
    (st.data.favorites || []).forEach(f => old[f.key] = f.sent_at);
    st.data.favorites = r.favorites.map(f => Object.assign(f, { sent_at: old[f.key] || null }));
    st.pinsChanged = true;
    cache.delete(st.bid);
    toast(had ? 'Đã bỏ ghim' : '📌 Đã ghim — nút hiện trên thẻ khách');
    drawTabs();
    redraw();
    rebind();
  }

  // ── actions ──────────────────────────────────────────────────────────────────
  async function markSent(step, sent) {
    if (!st || !step) return;
    const bid = st.bid;
    step.sent_at = sent ? new Date().toISOString() : null;
    cache.delete(bid);
    document.querySelectorAll(`.jchip[data-bid="${CSS.escape(bid)}"][data-step="${step.key}"]`)
      .forEach(chip => chip.classList.toggle('sent', sent));
    // save, then refresh which step is next (the ✓ above is already shown)
    await fetch('/api/journey/sent', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ booking_id: bid, step: step.key, sent }) }).catch(() => {});
    cache.delete(bid);
    const fresh = await fetchGuest(bid).catch(() => null);
    if (!fresh || !fresh.success) return;
    document.querySelectorAll(`.jchip[data-bid="${CSS.escape(bid)}"]`).forEach(chip => {
      const s = fresh.steps.find(x => x.key === chip.dataset.step) || (fresh.favorites || []).find(x => x.key === chip.dataset.step);
      chip.classList.toggle('sent', !!(s && s.sent_at));
      chip.classList.toggle('next', chip.dataset.step === fresh.recommended);
    });
    if (st && st.bid === bid) {
      st.data.recommended = fresh.recommended;
      fresh.steps.forEach(s => { const o = st.data.steps.find(x => x.key === s.key); if (o) o.sent_at = s.sent_at; });
      (fresh.favorites || []).forEach(f => { const o = (st.data.favorites || []).find(x => x.key === f.key); if (o) o.sent_at = f.sent_at; });
      st.ov.querySelectorAll('.jr-steps button').forEach(btn => {
        const s = st.data.steps.find(x => x.key === btn.dataset.k) || (st.data.favorites || []).find(x => x.key === btn.dataset.k);
        if (!s) return;
        btn.classList.toggle('sent', !!s.sent_at);
        btn.classList.toggle('next', s.key === fresh.recommended);
        btn.innerHTML = `${s.emoji} ${esc(s.label)}${s.sent_at ? ' ✓' : ''}`;
      });
    }
  }

  async function setApartment(aptId) {
    const bid = st.bid, step = st.step;
    const r = await fetch('/api/set_actual_apartment', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ booking_id: bid, actual_apartment: String(aptId || '') }) }).then(x => x.json()).catch(() => null);
    if (!r || r.success === false) { toast('Không lưu được căn'); return; }
    toast(aptId ? 'Đã xếp căn' : 'Đã bỏ xếp căn');
    cache.delete(bid);
    await open(bid, step);
    const apt = st && st.data.booking.apt;
    document.querySelectorAll(`.card[data-bid="${CSS.escape(bid)}"] .apt`).forEach(el => {
      el.textContent = apt ? apt.name : 'chưa xếp căn';
      el.classList.toggle('none', !apt);
    });
  }

  function zoom(url, fullUrl) {
    css();
    const z = document.createElement('div');
    z.className = 'jr-zoom';
    z.innerHTML = `<img src="${esc(url)}" alt=""><div><a href="${esc(url)}" download>⬇️ Tải ảnh</a>
      <button type="button" class="c">📋 Sao chép ảnh</button>
      ${fullUrl ? '<button type="button" class="f">Xem bản đầy đủ</button>' : ''}
      <button type="button" class="x">Đóng</button></div>`;
    z.addEventListener('click', e => { if (e.target === z) z.remove(); });
    z.querySelector('.x').onclick = () => z.remove();
    const f = z.querySelector('.f');
    if (f) f.onclick = () => {                     // owner check only — the guest gets the covered version
      const img = z.querySelector('img'), toFull = img.getAttribute('src') !== fullUrl;
      img.setAttribute('src', toFull ? fullUrl : url);
      f.textContent = toFull ? 'Xem bản gửi khách' : 'Xem bản đầy đủ';
    };
    const png = fetch(url).then(r => r.blob()).then(bl => bl.type === 'image/png' ? bl : new Promise((res, rej) => {
      const u = URL.createObjectURL(bl), im = new Image();
      im.onload = () => { const c = document.createElement('canvas'); c.width = im.naturalWidth; c.height = im.naturalHeight;
        c.getContext('2d').drawImage(im, 0, 0); URL.revokeObjectURL(u); c.toBlob(b => b ? res(b) : rej(), 'image/png'); };
      im.onerror = rej; im.src = u;
    }));
    png.catch(() => {});
    z.querySelector('.c').onclick = async e => {
      try { await navigator.clipboard.write([new ClipboardItem({ 'image/png': png })]); e.target.textContent = '✅ Đã chép'; }
      catch (err) { e.target.textContent = 'Không chép được'; }
    };
    document.body.appendChild(z);
  }

  window.Journey = { open, close, zoom };
})();
