window.TraceTaskControls = {
  buttons(job, { text, escape, locked = false, allowed = true }) {
    if (["ready", "failed", "cancelled"].includes(job.status)) return "";
    const bound = /^https:\/\/github\.com\/Eitan-S-23\/(?:E-Track|Trace)\/actions\/runs\/\d+$/.test(job.runUrl ?? "");
    const unavailable = locked || !allowed || job.cancelling || !bound;
    const reason = !allowed ? text("需要发布者权限", "Publisher access required")
      : job.cancelling ? text("正在确认取消结果", "Waiting for confirmed cancellation")
      : !bound ? text("尚未关联准确的构建记录，暂不能安全取消", "No uniquely bound run yet; cancellation is unavailable")
      : text("操作处理中", "Operation in progress");
    return [
      ["cancel", "i-block", text("取消当前任务", "Cancel this task")],
      ["cancel-restart", "i-refresh", text("取消当前任务后，按原参数重新运行", "Cancel this task, then restart with the original inputs")]
    ].map(([action,icon,label]) => `<button type="button" class="icon-button task-control" data-task-control="${action}"
      data-control-job="${escape(job.id)}" aria-label="${escape(label)}" aria-disabled="${unavailable}"
      data-tooltip="${escape(unavailable ? `${label}: ${reason}` : label)}">
      <svg class="ui-icon" aria-hidden="true"><use href="#${icon}"></use></svg></button>`).join("");
  }
};

// Long-press explains the action; it must not fall through to a synthesized click.
(() => {
  let press = null, timer = null, suppressClick = false;
  const clear = () => { clearTimeout(timer); timer = null; press?.node.classList.remove("tooltip-visible"); press = null; };
  document.addEventListener("pointerdown", event => {
    clear(); suppressClick = false;
    const node = event.target.closest?.("[data-task-control]");
    if (!node || event.pointerType === "mouse" || !event.isPrimary) return;
    press = { node, x:event.clientX, y:event.clientY };
    timer = setTimeout(() => { if (press) { suppressClick = true; press.node.classList.add("tooltip-visible"); } },500);
  },true);
  document.addEventListener("pointermove", event => {
    if (press && (Math.abs(event.clientX-press.x)>8 || Math.abs(event.clientY-press.y)>8)) clear();
  },true);
  document.addEventListener("pointerup", () => { clearTimeout(timer); if (!suppressClick) clear(); },true);
  document.addEventListener("pointercancel", () => { clear(); suppressClick = false; },true);
  document.addEventListener("contextmenu", event => {
    if (event.target.closest?.("[data-task-control]")) event.preventDefault();
  });
  document.addEventListener("click", event => {
    if (suppressClick) { event.preventDefault(); event.stopImmediatePropagation(); suppressClick = false; clear(); return; }
    if (event.target.closest?.('[data-task-control][aria-disabled="true"]')) {
      event.preventDefault(); event.stopImmediatePropagation();
    }
  },true);
})();
