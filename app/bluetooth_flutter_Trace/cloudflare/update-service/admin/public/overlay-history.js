/* Same-document history lets browser/Android Back dismiss the top layer first. */
window.TraceOverlayHistory = function ({ layers, dismiss, canDismiss }) {
  const key = "traceAdminOverlay";
  const scope = crypto.randomUUID();
  let depth = 0, travelling = false, queued = false;
  const original = history.state?.[key] ? history.state[key].original : history.state;
  function marker() { return history.state?.[key]; }
  function sync() {
    if (queued) return;
    queued = true;
    queueMicrotask(() => {
      queued = false;
      if (travelling) return;
      const count = layers().length;
      if (count < depth) {
        travelling = true;
        history.go(count - depth);
      } else {
        while (depth < count) {
          depth++;
          history.pushState({ [key]: { scope, depth, original } }, "", location.href);
        }
      }
    });
  }
  window.addEventListener("popstate", () => {
    const value = marker();
    depth = value?.scope === scope ? value.depth : 0;
    if (travelling) { travelling = false; sync(); return; }
    let open = layers();
    while (open.length > depth && canDismiss(open.at(-1))) {
      dismiss(open.at(-1));
      const remaining = layers();
      if (remaining.length >= open.length) break;
      open = remaining;
    }
    // Forward into a consumed layer never replays a dialog or a business action.
    if (!open.length && value) { history.replaceState(value.original, "", location.href); depth = 0; }
    sync();
  });
  const previous = marker();
  if (previous && Number.isInteger(previous.depth) && previous.depth > 0 && previous.depth <= 8) {
    travelling = true;
    history.go(-previous.depth);
  }
  return { sync };
};
