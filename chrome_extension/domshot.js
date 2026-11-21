// 📸 Picture of a part of the page WITHOUT the screen (1.48, owner Nov 22: "cần giữ hiển thị màn hình Chrome thì mới
// chụp được"). chrome.tabs.captureVisibleTab only sees the tab that is ON the screen — a tab behind another one, a
// minimized window, a locked PC (7:00 run) gave no picture. This draws the box again from the page itself (layout
// positions, fonts, colours, borders, SVG icons) onto a canvas: works in any tab, visible or not.
// Used by content.js only when the real screen capture is not possible. Read-only: nothing on the page changes.
(function () {
  if (window.hpDomShot) return;
  const css = (el) => getComputedStyle(el);
  const alpha = (c) => { const m = /rgba?\(([^)]+)\)/.exec(c || ''); if (!m) return c && c !== 'transparent' ? 1 : 0;
    const p = m[1].split(/[ ,/]+/).filter(Boolean); return p.length > 3 ? parseFloat(p[3]) : 1; };
  const shown = (el) => { try { return el.checkVisibility ? el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) : true; } catch (e) { return true; } };
  const hits = (r, a) => r.width > 0 && r.height > 0 && r.right > a.left && r.left < a.right && r.bottom > a.top && r.top < a.bottom;
  const loadImg = (src) => new Promise((res) => { const i = new Image(); const t = setTimeout(() => res(null), 2500);
    i.onload = () => { clearTimeout(t); res(i); }; i.onerror = () => { clearTimeout(t); res(null); }; i.src = src; });
  const sameOrigin = (u) => { try { return /^(data|blob):/.test(u) || new URL(u, location.href).origin === location.origin; } catch (e) { return false; } };
  const radius = (cs) => Math.min(parseFloat(cs.borderTopLeftRadius) || 0, 40);

  function pathBox(x, r, rad) {
    x.beginPath();
    if (rad > 0 && x.roundRect) x.roundRect(r.left, r.top, r.width, r.height, Math.min(rad, r.width / 2, r.height / 2));
    else x.rect(r.left, r.top, r.width, r.height);
  }
  function paintBox(x, el, cs, r) {
    const rad = radius(cs);
    if (alpha(cs.backgroundColor) > 0) { x.fillStyle = cs.backgroundColor; pathBox(x, r, rad); x.fill(); }
    const side = (s) => ({ w: parseFloat(cs['border' + s + 'Width']) || 0, c: cs['border' + s + 'Color'], st: cs['border' + s + 'Style'] });
    const T = side('Top'), Rt = side('Right'), B = side('Bottom'), L = side('Left');
    const on = (b) => b.w > 0 && b.st !== 'none' && b.st !== 'hidden' && alpha(b.c) > 0;
    if ([T, Rt, B, L].every((b) => on(b) && b.w === T.w && b.c === T.c)) {
      x.strokeStyle = T.c; x.lineWidth = T.w;
      pathBox(x, { left: r.left + T.w / 2, top: r.top + T.w / 2, width: r.width - T.w, height: r.height - T.w }, rad); x.stroke();
      return;
    }
    if (on(T)) { x.fillStyle = T.c; x.fillRect(r.left, r.top, r.width, T.w); }
    if (on(B)) { x.fillStyle = B.c; x.fillRect(r.left, r.bottom - B.w, r.width, B.w); }
    if (on(L)) { x.fillStyle = L.c; x.fillRect(r.left, r.top, L.w, r.height); }
    if (on(Rt)) { x.fillStyle = Rt.c; x.fillRect(r.right - Rt.w, r.top, Rt.w, r.height); }
  }
  async function paintSvg(x, el, cs, r) {
    try {
      const c = el.cloneNode(true);
      c.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
      c.setAttribute('width', r.width); c.setAttribute('height', r.height);
      c.style.color = cs.color;
      if (!c.getAttribute('fill') && cs.fill && cs.fill !== 'none') c.setAttribute('fill', cs.fill);
      const img = await loadImg('data:image/svg+xml;charset=utf-8,' + encodeURIComponent(new XMLSerializer().serializeToString(c)));
      if (img) x.drawImage(img, r.left, r.top, r.width, r.height);
    } catch (e) {}
  }
  function caseOf(t, tt) {
    if (tt === 'uppercase') return t.toUpperCase();
    if (tt === 'lowercase') return t.toLowerCase();
    if (tt === 'capitalize') return t.replace(/(^|\s)(\S)/g, (m, a, b) => a + b.toUpperCase());
    return t;
  }
  function paintText(x, node, a) {
    const el = node.parentElement, cs = css(el);
    if (alpha(cs.color) === 0) return;
    x.font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    try { x.letterSpacing = cs.letterSpacing === 'normal' ? '0px' : cs.letterSpacing; } catch (e) {}
    x.fillStyle = cs.color; x.textBaseline = 'alphabetic';
    const rg = document.createRange(), s = node.data, re = /\S+/g;
    let m;
    while ((m = re.exec(s))) {
      rg.setStart(node, m.index); rg.setEnd(node, m.index + m[0].length);
      const rs = rg.getClientRects();
      if (!rs.length) continue;
      const r = rs[0];
      if (!hits(r, a)) continue;
      const word = caseOf(m[0], cs.textTransform);
      const mt = x.measureText(word);
      const asc = mt.fontBoundingBoxAscent || parseFloat(cs.fontSize) * 0.8, desc = mt.fontBoundingBoxDescent || parseFloat(cs.fontSize) * 0.2;
      const y = r.top + (r.height + asc - desc) / 2;
      if (rs.length > 1 || mt.width > r.width * 1.04) x.fillText(word, r.left, y, Math.max(r.width, 1)); else x.fillText(word, r.left, y);
    }
  }

  // area = {left, top, right, bottom, width, height} in viewport coordinates (getBoundingClientRect), skip = an element
  // never to draw (the extension's own buttons). Returns a canvas of the area at `scale`.
  window.hpDomShot = async function (area, skip, scale) {
    const s = scale || Math.max(2, window.devicePixelRatio || 1);
    const c = document.createElement('canvas');
    c.width = Math.round(area.width * s); c.height = Math.round(area.height * s);
    const x = c.getContext('2d');
    x.scale(s, s); x.translate(-area.left, -area.top);
    x.fillStyle = '#ffffff'; x.fillRect(area.left, area.top, area.width, area.height);
    const pageBg = css(document.body).backgroundColor;
    if (alpha(pageBg) > 0) { x.fillStyle = pageBg; x.fillRect(area.left, area.top, area.width, area.height); }
    const skipTree = new Set();        // fixed / sticky bars (site header…) and hidden parts are not part of the box
    const svgs = [], texts = [], hitEls = new WeakSet();
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let n = walk.currentNode;
    while (n) {
      if (n.nodeType === 3) {
        if (n.data.trim() && hitEls.has(n.parentElement)) texts.push(n);
        n = walk.nextNode(); continue;
      }
      const el = n;
      if (el !== document.body && (el === skip || (skip && skip.contains(el)) || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|HEAD)$/.test(el.tagName))) {
        n = walk.nextSibling() || nextUp(walk); continue;
      }
      const cs = css(el);
      if (cs.display === 'none' || ((cs.position === 'fixed' || cs.position === 'sticky') && el !== document.body)) {
        n = walk.nextSibling() || nextUp(walk); continue;
      }
      const r = el.getBoundingClientRect();
      if (el.tagName.toLowerCase() === 'svg') {
        if (hits(r, area) && shown(el)) svgs.push([el, cs, r]);
        n = walk.nextSibling() || nextUp(walk); continue;
      }
      if (hits(r, area) && shown(el)) {
        hitEls.add(el);
        paintBox(x, el, cs, r);
        if (el.tagName === 'IMG' && el.complete && sameOrigin(el.currentSrc || el.src)) { try { x.drawImage(el, r.left, r.top, r.width, r.height); } catch (e) {} }
      }
      n = walk.nextNode();
    }
    function nextUp(w) { let p; while ((p = w.parentNode())) { const sib = w.nextSibling(); if (sib) return sib; } return null; }
    for (const [el, cs, r] of svgs) await paintSvg(x, el, cs, r);
    for (const t of texts) { if (t.parentElement && shown(t.parentElement)) paintText(x, t, area); }
    return c;
  };
})();
