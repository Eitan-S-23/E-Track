window.TraceTaskControls = {
  buttons(job, { text, escape, locked = false, allowed = true }) {
    if (!job.cancelling && ["ready", "failed", "cancelled", "deleting", "deleted"].includes(job.status)) return "";
    const bound = /^https:\/\/github\.com\/Eitan-S-23\/(?:E-Track|Trace)\/actions\/runs\/\d+$/.test(job.runUrl ?? "");
    const unavailable = locked || !allowed || job.cancelling;
    const reason = !allowed ? text("需要发布者权限", "Publisher access required")
      : job.cancelling ? text("正在确认取消结果", "Waiting for confirmed cancellation")
      : !bound ? text("点击后先查找对应构建，再执行操作", "Find the matching build before applying this action")
      : text("操作处理中", "Operation in progress");
    return [
      ["cancel", "i-block", text("取消当前任务", "Cancel this task")],
      ["cancel-restart", "i-refresh", text("取消当前任务后，按原参数重新运行", "Cancel this task, then restart with the original inputs")]
    ].map(([action,icon,label]) => `<button type="button" class="icon-button task-control" data-task-control="${action}"
      data-control-job="${escape(job.id)}" aria-label="${escape(label)}" aria-disabled="${unavailable}"
      data-tooltip="${escape(unavailable || !bound ? `${label}: ${reason}` : label)}">
      <svg class="ui-icon" aria-hidden="true"><use href="#${icon}"></use></svg></button>`).join("");
  }
};

// Follow the task identity across polling/read-state renders, not a detached button.
(() => {
  const selector = "[data-task-control]";
  const tooltip = document.createElement("div");
  tooltip.id = "taskControlTooltip";
  tooltip.className = "task-control-tooltip";
  tooltip.setAttribute("role", "tooltip");
  tooltip.hidden = true;
  document.body.append(tooltip);
  let press = null, timer = null, shown = null, suppressed = null;
  const identity = node => ({ host: node.closest("#taskContent, #deltaContent"),
    job: node.dataset.controlJob, action: node.dataset.taskControl, node });
  const matches = (node, value) => node && value && value.host?.contains(node)
    && node.dataset.controlJob === value.job && node.dataset.taskControl === value.action;
  const resolve = value => value?.host && !value.host.closest("[hidden], [inert]")
    ? [...value.host.querySelectorAll(selector)].find(node => matches(node, value)) : null;
  function detach(node) {
    node?.classList.remove("tooltip-visible");
    node?.removeAttribute("aria-describedby");
  }
  function hide() {
    detach(shown?.node); shown = null;
    if (!tooltip.hidden) tooltip.hidden = true;
  }
  function clear() { clearTimeout(timer); timer = null; press = null; hide(); }
  function position() {
    if (!shown) return;
    const node = resolve(shown);
    if (!node) { hide(); return; }
    const replaced = node !== shown.node;
    if (replaced) detach(shown.node);
    shown.node = node;
    node.classList.add("tooltip-visible");
    node.setAttribute("aria-describedby", tooltip.id);
    if (tooltip.textContent !== node.dataset.tooltip) tooltip.textContent = node.dataset.tooltip;
    if (tooltip.hidden) tooltip.hidden = false;
    const rect = node.getBoundingClientRect(), tip = tooltip.getBoundingClientRect();
    const viewport = window.visualViewport, left = viewport?.offsetLeft ?? 0, top = viewport?.offsetTop ?? 0;
    const width = viewport?.width ?? innerWidth, height = viewport?.height ?? innerHeight, margin = 12;
    tooltip.style.left = `${Math.max(left + margin, Math.min(rect.right - tip.width, left + width - tip.width - margin))}px`;
    const above = rect.top - tip.height - 8;
    tooltip.style.top = `${Math.max(top + margin, Math.min(above >= top + margin ? above : rect.bottom + 8, top + height - tip.height - margin))}px`;
  }
  function show(value, mode) { hide(); shown = {...value, mode}; position(); }
  function suppress(value) { suppressed = {...value, until:performance.now() + 1500}; }
  document.addEventListener("pointerdown", event => {
    clear(); suppressed = null;
    const node = event.target.closest?.(selector);
    if (!node || event.pointerType === "mouse" || !event.isPrimary) return;
    press = {...identity(node), pointerId:event.pointerId, x:event.clientX, y:event.clientY};
    timer = setTimeout(() => {
      if (resolve(press)) { suppress(press); show(press, "press"); }
    },500);
  },true);
  document.addEventListener("pointermove", event => {
    if (press && event.pointerId === press.pointerId && (Math.abs(event.clientX-press.x)>8 || Math.abs(event.clientY-press.y)>8)) {
      suppress(press); clear();
    }
  },true);
  document.addEventListener("pointerup", event => {
    if (!press || event.pointerId !== press.pointerId) return;
    clearTimeout(timer); timer = null;
    if (shown?.mode === "press") suppress(press); else hide();
    press = null;
  },true);
  document.addEventListener("pointercancel", event => {
    if (press && event.pointerId === press.pointerId) { suppress(press); clear(); }
  },true);
  document.addEventListener("pointerover", event => {
    const node = event.target.closest?.(selector);
    if (event.pointerType === "mouse" && node && !node.contains(event.relatedTarget)) show(identity(node), "hover");
  },true);
  document.addEventListener("pointerout", event => {
    if (shown?.mode === "hover" && !shown.node.contains(event.relatedTarget)) hide();
  },true);
  document.addEventListener("focusin", event => {
    const node = event.target.closest?.(selector);
    if (node?.matches(":focus-visible")) show(identity(node), "focus");
    else if (shown?.mode === "focus") hide();
  });
  document.addEventListener("focusout", event => {
    if (shown?.mode === "focus" && event.target.isConnected) hide();
  });
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && shown) { clear(); event.preventDefault(); event.stopImmediatePropagation(); }
    if (event.key === "Enter" || event.key === " ") suppressed = null;
  },true);
  document.addEventListener("contextmenu", event => {
    if (event.target.closest?.(selector)) event.preventDefault();
  });
  document.addEventListener("click", event => {
    const node = event.target.closest?.(selector);
    if (matches(node, suppressed) && performance.now() <= suppressed.until) {
      event.preventDefault(); event.stopImmediatePropagation(); suppressed = null; clear(); return;
    }
    if (node?.getAttribute("aria-disabled") === "true") {
      show(identity(node), "focus");
      event.preventDefault(); event.stopImmediatePropagation();
    }
  },true);
  document.addEventListener("scroll", () => { if (press) suppress(press); clear(); },true);
  document.addEventListener("visibilitychange", () => { if (document.hidden) clear(); });
  window.addEventListener("resize", position);
  window.visualViewport?.addEventListener("resize", position);
  window.visualViewport?.addEventListener("scroll", position);
  new MutationObserver(() => {
    if (press && !resolve(press)) { suppress(press); clear(); }
    if (shown) position();
  }).observe(document.body, {childList:true, subtree:true, attributes:true, attributeFilter:["hidden", "inert"]});
})();
