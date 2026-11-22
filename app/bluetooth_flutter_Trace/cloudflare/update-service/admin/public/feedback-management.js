(function () {
  "use strict";
  window.TraceFeedbackInbox = function ({ element, api, mutate, session, text, escape: esc, confirm, onError, onRecovered, onSuccess }) {
    const states = ["pending", "processing", "resolved", "declined"];
    let actor = "", epoch = 0, listTicket = 0, detailTicket = 0, timer = 0;
    let rows = [], nextCursor = null, filter = "all", query = "", selected = null, history = [];
    let draft = null, loading = false, saving = false, detailLoading = false, notice = "";
    const editAllowed = () => ["owner", "publisher"].includes(session()?.role);
    const label = value => ({ all: text("\u5168\u90e8", "All"), pending: text("\u5f85\u5904\u7406", "Pending"),
      processing: text("\u5904\u7406\u4e2d", "Processing"), resolved: text("\u5df2\u89e3\u51b3", "Resolved"),
      declined: text("\u4e0d\u91c7\u7eb3", "Declined") })[value] || value;
    const dirty = () => Boolean(selected && draft && (draft.status !== selected.status || draft.note !== selected.note));
    const stamp = value => Number.isFinite(Number(value)) ? new Date(Number(value) * 1000).toLocaleString() : "-";
    const options = values => values.map(value => `<option value="${value}">${esc(label(value))}</option>`).join("");

    function render() {
      const focus = document.activeElement;
      const focusedId = element.contains(focus) ? focus.id : null;
      const selection = focusedId === "feedbackNote" ? [focus.selectionStart, focus.selectionEnd] : null;
      element.innerHTML = `<div class="panel-head"><div><h2>${esc(text("\u7528\u6237\u53cd\u9988", "User feedback"))}</h2>
        <p>${esc(text("\u67e5\u770b\u53cd\u9988\u5e76\u8bb0\u5f55\u5904\u7406\u7ed3\u679c\u3002\u6b63\u6587\u4fdd\u7559 90 \u5929\u3002", "Review feedback and record its outcome. Message content is retained for 90 days."))}</p></div>
        <button type="button" class="secondary-button" id="feedbackReload" ${loading ? "disabled" : ""}>${esc(text("\u5237\u65b0\u5217\u8868", "Refresh list"))}</button></div>
        <div class="operations-buttons"><label for="feedbackFilter">${esc(text("\u5904\u7406\u72b6\u6001", "Status"))}</label>
          <select id="feedbackFilter">${options(["all", ...states])}</select></div>
        <p class="firmware-hint" id="feedbackNotice" role="status">${esc(loading ? text("正在读取", "Loading") : detailLoading ? text("正在读取详情", "Loading detail") : saving ? text("正在保存", "Saving") : '')}</p>
        <div class="feedback-layout"><div><div id="feedbackList">${rows.map(item => `<button type="button" class="feedback-item ${selected?.id === item.id ? "active" : ""}" data-feedback-id="${Number(item.id)}">
          <span class="tag">${esc(label(item.status))}</span><span class="feedback-meta">${esc(item.platform)} / ${esc(item.versionName)} / ${esc(stamp(item.receivedAt))}</span>
          <span class="feedback-body">${esc(String(item.body).slice(0, 180))}</span></button>`).join("") || `<p class="empty">${esc(loading ? text("\u6b63\u5728\u8bfb\u53d6", "Loading") : text("\u6ca1\u6709\u5339\u914d\u7684\u53cd\u9988", "No matching feedback"))}</p>`}</div>
          <button type="button" class="secondary-button" id="feedbackMore" ${nextCursor == null ? "hidden" : ""} ${loading ? "disabled" : ""}>${esc(text("\u52a0\u8f7d\u66f4\u591a", "Load more"))}</button></div>
          <section id="feedbackDetail" class="feedback-detail" tabindex="-1" ${selected ? "" : "hidden"}>
          ${selected ? `<div class="panel-head"><h3>${esc(text("\u53cd\u9988", "Feedback"))} #${Number(selected.id)}</h3>
            <button type="button" class="secondary-button" id="feedbackDetailReload" ${saving ? "disabled" : ""}>${esc(text("\u91cd\u65b0\u8bfb\u53d6", "Reload detail"))}</button></div>
            <p class="feedback-meta">${esc(text("\u63d0\u4ea4\u65f6\u95f4", "Received"))}: ${esc(stamp(selected.receivedAt))}</p>
            <p class="feedback-body" id="feedbackBody">${esc(selected.body)}</p>
            <label for="feedbackState">${esc(text("\u5904\u7406\u72b6\u6001", "Status"))}</label>
            <select id="feedbackState" ${!editAllowed() || saving ? "disabled" : ""}>${options(states)}</select>
            <label for="feedbackNote">${esc(text("\u5904\u7406\u5907\u6ce8", "Processing notes"))}</label>
            <textarea id="feedbackNote" rows="5" maxlength="2000" ${!editAllowed() || saving ? "disabled" : ""}></textarea>
            <p class="firmware-hint" id="feedbackDraftState">${esc(dirty() ? text("\u6709\u672a\u4fdd\u5b58\u7684\u4fee\u6539", "Unsaved changes") : "")}</p>
            <button type="button" class="save-button" id="feedbackSave" ${!editAllowed() || saving ? "disabled" : ""}>${esc(saving ? text("\u6b63\u5728\u4fdd\u5b58", "Saving") : text("\u4fdd\u5b58\u5904\u7406\u7ed3\u679c", "Save outcome"))}</button>
            <h4>${esc(text("\u5904\u7406\u8bb0\u5f55", "History"))}</h4><ol class="feedback-history">${history.map(item => `<li><span>${esc(stamp(item.createdAt))} / ${esc(item.actor)} / ${esc(label(item.status))}</span><p>${esc(item.note)}</p></li>`).join("")}</ol>` : ""}
          </section></div>`;
      element.querySelector("#feedbackFilter").value = filter;
      if (selected) {
        element.querySelector("#feedbackState").value = draft.status;
        element.querySelector("#feedbackNote").value = draft.note;
        if (detailLoading) for (const id of ["feedbackState", "feedbackNote", "feedbackSave"]) element.querySelector("#" + id).disabled = true;
      }
      if (focusedId && !element.hidden) {
        const restored = element.querySelector("#" + focusedId);
        restored?.focus({ preventScroll: true });
        if (selection && restored) restored.setSelectionRange(...selection);
      }
    }

    async function load(append = false) {
      if (!session()?.actor) return;
      clearTimeout(timer);
      const ticket = ++listTicket, generation = epoch;
      loading = true; notice = ""; render();
      const search = new URLSearchParams({ status: filter, q: query });
      if (append && nextCursor != null) search.set("before", String(nextCursor));
      try {
        const value = await api("/api/admin/feedback?" + search);
        if (ticket !== listTicket || generation !== epoch) return;
        if (!Array.isArray(value.feedback)) throw Error(text("\u53cd\u9988\u54cd\u5e94\u683c\u5f0f\u65e0\u6548", "Invalid feedback response"));
        rows = append ? [...rows, ...value.feedback.filter(item => !rows.some(row => row.id === item.id))] : value.feedback;
        nextCursor = value.nextCursor ?? null;
        onRecovered?.('feedback-list');
      } catch (error) {
        if (ticket === listTicket && generation === epoch) { notice = error.message; onError?.(error, 'feedback-list'); }
      } finally {
        if (ticket === listTicket && generation === epoch) { loading = false; render(); }
      }
    }

    async function mayDiscard() {
      return !dirty() || await confirm({ tone: "warning", title: text("\u653e\u5f03\u672a\u4fdd\u5b58\u7684\u5907\u6ce8\uff1f", "Discard unsaved notes?"),
        message: text("\u5df2\u4fdd\u5b58\u7684\u5904\u7406\u8bb0\u5f55\u4e0d\u53d7\u5f71\u54cd\u3002", "Saved history is unaffected."),
        confirmLabel: text("\u653e\u5f03\u4fee\u6539", "Discard") });
    }
    async function open(id) {
      if (saving || detailLoading) return;
      const generation = epoch;
      if (!await mayDiscard() || generation !== epoch) return;
      const ticket = ++detailTicket;
      detailLoading = true;
      notice = text("\u6b63\u5728\u8bfb\u53d6\u8be6\u60c5", "Loading detail"); render();
      try {
        const value = await api("/api/admin/feedback/" + id);
        if (ticket !== detailTicket || generation !== epoch) return;
        if (value.feedback?.id !== id || !Number.isInteger(value.feedback.revision)) throw Error(text("\u53cd\u9988\u54cd\u5e94\u683c\u5f0f\u65e0\u6548", "Invalid feedback response"));
        selected = value.feedback; history = value.history || [];
        draft = { status: selected.status, note: selected.note }; notice = ""; render();
        onRecovered?.('feedback-detail');
        if (!element.hidden && element.closest("[data-admin-view]")?.hidden !== true) {
          const detail = element.querySelector("#feedbackDetail");
          detail.scrollIntoView({ block: "nearest" });
          detail.focus({ preventScroll: true });
        }
      } catch (error) { if (ticket === detailTicket && generation === epoch) { notice = error.message; onError?.(error, 'feedback-detail'); } }
      finally { if (ticket === detailTicket && generation === epoch) { detailLoading = false; render(); } }
    }

    async function save() {
      if (!selected || !editAllowed() || saving || detailLoading) return;
      const generation = epoch, id = selected.id, revision = selected.revision;
      onRecovered?.('feedback-save');
      const payload = { status: draft.status, note: draft.note, revision };
      saving = true; notice = ""; render();
      try {
        const value = await mutate("/api/admin/feedback/" + id, payload);
        if (generation !== epoch) return;
        if (value.feedback?.id !== id || value.feedback.revision <= revision) throw Error(text("\u672a\u6536\u5230\u6709\u6548\u4fdd\u5b58\u786e\u8ba4", "Missing save acknowledgement"));
        selected = value.feedback; history = value.history || [];
        draft = { status: selected.status, note: selected.note };
        rows = rows.map(item => item.id === id ? selected : item)
          .filter(item => filter === "all" || item.status === filter);
        notice = text("\u5904\u7406\u7ed3\u679c\u5df2\u4fdd\u5b58", "Outcome saved");
        onRecovered?.('feedback-save');
        onSuccess?.(notice);
      } catch (error) {
        if (generation === epoch) {
          notice = error.code === "CAS_CONFLICT"
          ? text("\u53cd\u9988\u5df2\u88ab\u5176\u4ed6\u64cd\u4f5c\u4fee\u6539\u3002\u5f53\u524d\u5907\u6ce8\u5df2\u4fdd\u7559\uff0c\u8bf7\u91cd\u65b0\u8bfb\u53d6\u540e\u6838\u5bf9\u3002", "Feedback changed elsewhere. Your notes are retained; reload and reconcile.")
          : text("\u672a\u786e\u8ba4\u4fdd\u5b58\u6210\u529f\uff0c\u5907\u6ce8\u5df2\u4fdd\u7559\u3002\u8bf7\u5148\u91cd\u65b0\u8bfb\u53d6\u72b6\u6001\u518d\u91cd\u8bd5\u3002", "Save was not confirmed. Notes are retained; reload state before retrying.") + " " + error.message;
          onError?.(notice, 'feedback-save');
        }
      } finally { if (generation === epoch) { saving = false; render(); } }
    }

    element.addEventListener("click", event => {
      const item = event.target.closest("[data-feedback-id]");
      if (item) { void open(Number(item.dataset.feedbackId)); return; }
      const id = event.target.closest("button")?.id;
      if (id === "feedbackReload") void load();
      if (id === "feedbackMore") void load(true);
      if (id === "feedbackDetailReload" && selected) void open(selected.id);
      if (id === "feedbackSave") void save();
    });
    element.addEventListener("change", event => {
      if (event.target.id === "feedbackFilter") { filter = event.target.value; void load(); }
      if (event.target.id === "feedbackState" && draft) { draft.status = event.target.value; render(); }
    });
    element.addEventListener("input", event => {
      if (event.target.id === "feedbackNote" && draft) {
        draft.note = event.target.value;
        element.querySelector("#feedbackDraftState").textContent = dirty() ? text("\u6709\u672a\u4fdd\u5b58\u7684\u4fee\u6539", "Unsaved changes") : "";
      }
    });
    return {
      render, load, dirty,
      search(value) { query = value.slice(0, 120); listTicket++; clearTimeout(timer); timer = setTimeout(() => void load(), 300); },
      setSession(value) {
        const identity = value?.actor ? value.actor + ":" + value.role : "";
        if (identity === actor) { if (!element.hidden) void load(); return; }
        actor = identity; epoch++; listTicket++; detailTicket++; clearTimeout(timer);
        rows = []; selected = null; draft = null; history = []; nextCursor = null;
        loading = false; saving = false; detailLoading = false; notice = ""; render();
        if (actor && !element.hidden) void load();
      },
    };
  };
})();
