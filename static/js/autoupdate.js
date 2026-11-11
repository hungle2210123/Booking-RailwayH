/* Auto-update for the home-screen apps (/moi, /may-tinh, /tin-nhanh): a new deploy reloads the page by itself.
 * Asks /api/version when the app comes back to the front, on focus, and every minute.
 *  · nothing open → reload at once
 *  · a sheet / dialog is open or the owner is typing → never reload under their hands: show a small bar
 *    "Có bản mới — chạm để cập nhật" and reload as soon as the sheet closes (checked every 3 s).
 * Owner, Nov 11: "sao không tự động cập nhật trên icon iPhone" — the old check waited silently while a sheet was open
 * (exactly when they opened the sheet to look for the new button) and Tin nhanh had no check at all.
 * window.__BUILD = the build the page was rendered with (set by the template); if missing, the first answer is used. */
(function () {
  let build = window.__BUILD || null, busy = false, bar = null, waiting = false;
  const OPEN = '.ov, .jr-ov, #modal .modal, #drawer.open, #pxOv, input:focus, textarea:focus, select:focus';
  const reload = () => { try { sessionStorage.setItem('au_reloaded', String(Date.now())); } catch (e) {} location.reload(); };
  function showBar() {
    if (bar) return;
    bar = document.createElement('button');
    bar.id = 'auBar';
    bar.textContent = '🔄 Có bản mới — chạm để cập nhật';
    bar.style.cssText = 'position:fixed;left:50%;transform:translateX(-50%);top:calc(8px + env(safe-area-inset-top));z-index:99999;' +
      'border:0;border-radius:999px;padding:10px 16px;background:#0E1525;color:#fff;font:800 13.5px/1 inherit;' +
      'box-shadow:0 8px 24px rgba(0,0,0,.35);white-space:nowrap';
    bar.onclick = reload;
    document.body.appendChild(bar);
  }
  async function check() {
    if (busy || document.hidden) return; busy = true;
    try {
      const j = await (await fetch('/api/version', { cache: 'no-store' })).json();
      if (!j.build) return;
      if (!build) { build = j.build; return; }
      if (j.build !== build) {
        if (!document.querySelector(OPEN)) return reload();
        showBar();
        if (!waiting) { waiting = true; const t = setInterval(() => { if (!document.querySelector(OPEN)) { clearInterval(t); reload(); } }, 3000); }
      }
    } catch (e) {} finally { busy = false; }
  }
  document.addEventListener('visibilitychange', () => { if (!document.hidden) setTimeout(check, 600); });
  window.addEventListener('pageshow', () => setTimeout(check, 600));       // iPhone brings a frozen page back
  window.addEventListener('focus', () => setTimeout(check, 600));
  setInterval(check, 60000);
  setTimeout(check, 1500);
})();
