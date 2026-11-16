/* One gesture owner for every sheet. Native content scrolling keeps priority. */
window.TraceSheetGestures = function ({ sheet, scroll, backdrop, canClose, close,
  headerSelector = ".quick-sheet-header, .quick-sheet-handle", centered = true, verticalCentered = false }) {
  let gesture = null;
  let suppressClickUntil = 0;
  const controls = "button, a, input, textarea, select, label, summary, [contenteditable], [data-no-sheet-drag]";
  function reset() {
    gesture = null;
    sheet.classList.remove("sheet-dragging");
    sheet.style.removeProperty("transform");
    backdrop?.style.removeProperty("opacity");
  }
  function available() { return !sheet.hidden && !sheet.inert && canClose(); }
  function begin(x, y, target, pointerId = null) {
    reset();
    if (!available() || !(target instanceof Element) || target.closest(controls)) return;
    const header = Boolean(target.closest(headerSelector));
    if (!header && (!scroll.contains(target) || scroll.scrollTop > 0)) return;
    // Nested scroll regions and text editors must never hand a swipe to the sheet.
    for (let node = target; !header && node && node !== scroll; node = node.parentElement) {
      if (node.scrollHeight > node.clientHeight + 1 && /auto|scroll/.test(getComputedStyle(node).overflowY)) return;
    }
    gesture = { x, y, lastPosition: 0, lastTime: performance.now(), velocity: 0, distance: 0, active: false, header, axis: null, pointerId };
  }
  function move(x, y, event) {
    const g = gesture;
    if (!g) return;
    if (!available()) { reset(); return; }
    const dx = x - g.x, dy = y - g.y;
    if (!g.active) {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      if (g.header && Math.abs(dx) > Math.abs(dy) * 1.3) g.axis = "x";
      else if (dy > 0 && dy > Math.abs(dx) * 1.3) g.axis = "y";
      else { reset(); return; }
      if (!event.cancelable) { reset(); return; }
      g.active = true;
      sheet.classList.add("sheet-dragging");
    }
    if (event.cancelable) event.preventDefault();
    const now = performance.now();
    const position = g.axis === "x" ? Math.abs(dx) : Math.max(0, dy);
    g.velocity = (position - g.lastPosition) / Math.max(1, now - g.lastTime);
    g.lastPosition = position; g.lastTime = now; g.distance = position;
    const origin = centered ? "-50%" : "0px";
    const originY = verticalCentered ? "-50%" : "0px";
    sheet.style.transform = g.axis === "x" ? `translate(calc(${origin} + ${dx}px), ${originY})`
      : `translate(${origin}, calc(${originY} + ${position}px))`;
    if (backdrop) backdrop.style.opacity = String(Math.max(.35, 1 - g.distance / Math.max(1, sheet.clientHeight)));
  }
  function end(cancelled = false) {
    const g = gesture;
    if (!g) return;
    if (g.active) suppressClickUntil = performance.now() + 400;
    const threshold = Math.min(140, Math.max(80, (g.axis === "x" ? sheet.clientWidth : sheet.clientHeight) * .25));
    const dismiss = !cancelled && g.active && available() && (g.distance >= threshold ||
      (g.distance >= 50 && g.velocity >= .7 && performance.now() - g.lastTime < 100));
    reset();
    if (dismiss) close();
  }
  sheet.addEventListener("touchstart", event => {
    if (event.touches.length !== 1) { end(true); return; }
    const point = event.touches[0];
    begin(point.clientX, point.clientY, event.target);
  }, { passive: true });
  sheet.addEventListener("touchmove", event => {
    if (event.touches.length !== 1) { end(true); return; }
    const point = event.touches[0];
    move(point.clientX, point.clientY, event);
  }, { passive: false });
  sheet.addEventListener("touchend", () => end());
  sheet.addEventListener("touchcancel", () => end(true));
  sheet.addEventListener("pointerdown", event => {
    if (event.pointerType === "touch" || event.button !== 0 || !event.target.closest(headerSelector)) return;
    begin(event.clientX, event.clientY, event.target, event.pointerId);
    if (gesture) sheet.setPointerCapture(event.pointerId);
  });
  sheet.addEventListener("pointermove", event => {
    if (gesture?.pointerId === event.pointerId) move(event.clientX, event.clientY, event);
  });
  sheet.addEventListener("pointerup", event => { if (gesture?.pointerId === event.pointerId) end(); });
  sheet.addEventListener("pointercancel", event => { if (gesture?.pointerId === event.pointerId) end(true); });
  sheet.addEventListener("lostpointercapture", () => { if (gesture?.pointerId !== null) end(true); });
  sheet.addEventListener("click", event => {
    if (performance.now() < suppressClickUntil) { event.preventDefault(); event.stopImmediatePropagation(); }
  }, true);
  new MutationObserver(() => { if (sheet.hidden || sheet.inert) reset(); })
    .observe(sheet, { attributes: true, attributeFilter: ["hidden", "inert"] });
  return { reset };
};
