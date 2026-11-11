/* 🔧 Đổi định dạng proxy (owner, Nov 11): paste a line like
 *     curl -v -x http://USER:PASS@HOST:PORT -L https://…        (or just http://USER:PASS@HOST:PORT)
 * → HOST:PORT:USER:PASS   (one per line; several lines at once work).
 * Runs ONLY in the browser: nothing is sent to the server and nothing is stored — these are passwords.
 * Used by /moi and /may-tinh: ProxyTool.open(). ProxyTool.convert(text) is the pure function (tested with node). */
(function (root) {
  const one = (line) => {
    line = String(line || '').trim();
    if (!line) return null;
    // USER:PASS@HOST:PORT, with or without http:// / socks5:// in front (the proxy part of a curl command)
    let m = line.match(/(?:[a-z][a-z0-9+.-]*:\/\/)?([^\s:@\/'"]+):([^\s'"]+)@([A-Za-z0-9.-]+):(\d{2,5})(?![\w.-])/i);
    if (m) return m[3] + ':' + m[4] + ':' + m[1] + ':' + m[2];
    // already HOST:PORT:USER:PASS → keep
    m = line.match(/^([A-Za-z0-9.-]+):(\d{2,5}):([^\s:]+):(\S+)$/);
    if (m) return line;
    // proxy without a password: -x http://HOST:PORT
    m = line.match(/(?:-x|--proxy)\s+['"]?(?:[a-z][a-z0-9+.-]*:\/\/)?([A-Za-z0-9.-]+):(\d{2,5})/i);
    if (m) return m[1] + ':' + m[2];
    return null;
  };
  const convert = (text) => {
    const out = [], bad = [];
    String(text || '').split(/\r?\n/).forEach((l) => {
      l = l.replace(/^\s*\$\s*/, '').trim();          // a copied "$ curl …" prompt
      if (!l) return;
      const r = one(l);
      if (r) { if (!out.includes(r)) out.push(r); } else bad.push(l);
    });
    return { out, bad };
  };

  const open = () => {
    if (!root.document) return;
    const old = document.getElementById('pxOv'); if (old) old.remove();
    const ov = document.createElement('div');
    ov.id = 'pxOv';
    ov.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(14,21,37,.45);display:flex;align-items:flex-end;justify-content:center';
    ov.innerHTML = `<div role="dialog" aria-modal="true" style="background:#fff;width:100%;max-width:560px;max-height:92vh;overflow:auto;border-radius:20px 20px 0 0;padding:16px 16px calc(16px + env(safe-area-inset-bottom));font-family:inherit;color:#0E1525">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px"><div style="flex:1"><div style="font-size:11.5px;font-weight:800;letter-spacing:1px;color:#64748B">CÔNG CỤ</div><div style="font-size:20px;font-weight:800">Đổi định dạng proxy</div></div>
        <button id="pxX" aria-label="Đóng" style="width:38px;height:38px;border-radius:50%;border:0;background:#F1F5F9;font-size:18px;font-weight:800">✕</button></div>
      <div style="font-size:13px;color:#64748B;margin-bottom:6px">Dán dòng <b>curl … -x http://tên:mậtkhẩu@máychủ:cổng …</b> (dán nhiều dòng cũng được)</div>
      <textarea id="pxIn" rows="4" autocapitalize="off" autocorrect="off" spellcheck="false" placeholder="curl -v -x http://user:pass@host:12321 -L https://…" style="width:100%;box-sizing:border-box;border:1.5px solid #DDE1E8;border-radius:12px;padding:10px;font:13px/1.4 ui-monospace,Menlo,Consolas,monospace"></textarea>
      <div style="display:flex;gap:8px;margin:8px 0 12px"><button id="pxPaste" style="flex:1;min-height:44px;border-radius:12px;border:1.5px solid #DDE1E8;background:#fff;font-weight:800;font-size:14px">📋 Dán</button>
        <button id="pxClear" style="min-height:44px;border-radius:12px;border:1.5px solid #DDE1E8;background:#fff;font-weight:800;font-size:14px;padding:0 16px">Xóa</button></div>
      <div style="font-size:13px;color:#64748B;margin-bottom:6px">Kết quả — <b>máychủ:cổng:tên:mậtkhẩu</b></div>
      <textarea id="pxOut" rows="3" readonly style="width:100%;box-sizing:border-box;border:1.5px solid #DDE1E8;border-radius:12px;padding:10px;background:#F8FAFC;font:13px/1.4 ui-monospace,Menlo,Consolas,monospace"></textarea>
      <div id="pxMsg" style="font-size:12.5px;font-weight:700;min-height:18px;margin:6px 0"></div>
      <button id="pxCopy" style="width:100%;min-height:48px;border-radius:12px;border:0;background:#0E1525;color:#fff;font-weight:800;font-size:15px">Copy kết quả</button>
      <div style="font-size:11.5px;color:#94A3B8;margin-top:10px">🔒 Đổi ngay trên máy này — không gửi lên máy chủ, không lưu lại.</div></div>`;
    document.body.appendChild(ov);
    const $ = (id) => ov.querySelector('#' + id), inp = $('pxIn'), outp = $('pxOut'), msg = $('pxMsg');
    const run = () => {
      const r = convert(inp.value);
      outp.value = r.out.join('\n');
      outp.rows = Math.max(3, Math.min(r.out.length + 1, 10));
      msg.style.color = r.bad.length ? '#B45309' : '#15803D';
      msg.textContent = !inp.value.trim() ? '' : r.bad.length ? `⚠ ${r.bad.length} dòng không đọc được (cần dạng tên:mậtkhẩu@máychủ:cổng)` : `✓ ${r.out.length} proxy`;
    };
    const close = () => ov.remove();
    inp.addEventListener('input', run);
    $('pxX').onclick = close;
    ov.addEventListener('click', (e) => { if (e.target === ov) close(); });
    $('pxClear').onclick = () => { inp.value = ''; run(); inp.focus(); };
    $('pxPaste').onclick = async () => {
      try { inp.value = await navigator.clipboard.readText(); run(); }
      catch (e) { inp.focus(); msg.style.color = '#B45309'; msg.textContent = 'Chạm giữ vào ô trên → Dán'; }
    };
    $('pxCopy').onclick = () => {
      if (!outp.value) { msg.style.color = '#B45309'; msg.textContent = 'Chưa có kết quả — dán dòng proxy vào ô trên'; return; }
      let ok = false;
      try { outp.removeAttribute('readonly'); outp.select(); outp.setSelectionRange(0, outp.value.length); ok = document.execCommand('copy'); outp.setAttribute('readonly', ''); } catch (e) {}
      if (!ok && navigator.clipboard) navigator.clipboard.writeText(outp.value).catch(() => {});
      msg.style.color = '#15803D'; msg.textContent = '✓ Đã copy';
    };
    setTimeout(() => inp.focus(), 50);
  };

  root.ProxyTool = { convert, open };
  if (typeof module !== 'undefined' && module.exports) module.exports = root.ProxyTool;
})(typeof window !== 'undefined' ? window : globalThis);
