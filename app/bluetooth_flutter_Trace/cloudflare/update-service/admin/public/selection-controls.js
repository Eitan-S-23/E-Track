window.TraceSelectionControls = function ({ active, count, locked = false, allowed = true,
  attribute, actions = {}, text, escape, label }) {
  if (!allowed) return "";
  const names = { enter: "enter", exit: "exit", select: "select-page", remove: "delete", ...actions };
  const icon = (action, name, caption, disabled = locked) => `<button type="button" class="icon-button"
    data-${attribute}="${escape(action)}" aria-label="${escape(caption)}" title="${escape(caption)}" ${disabled ? "disabled" : ""}>
    <svg class="ui-icon" aria-hidden="true"><use href="#${name}"></use></svg></button>`;
  if (!active) return icon(names.enter, "i-trash", label);
  return icon(names.exit, "i-close", text("\u9000\u51fa\u5220\u9664\u6a21\u5f0f", "Exit deletion mode"))
    + `<button type="button" class="secondary-button" data-${attribute}="${escape(names.select)}" ${locked ? "disabled" : ""}>
      ${escape(text("\u9009\u62e9/\u53d6\u6d88\u9009\u62e9\u5f53\u524d\u9875", "Select / clear current page"))}</button>
      <span class="selection-count" role="status">${escape(text("\u5df2\u9009 ", "Selected: "))}${count}</span>`
    + icon(names.remove, "i-trash", text("\u5220\u9664\u6240\u9009", "Delete selected") + ` (${count})`, locked || !count);
};
