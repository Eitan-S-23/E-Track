window.TraceDeltaActivity = function ({ api, mutate, text, escape, formatBytes, openTarget, openPanel, onJobs, canNotify = () => true,
  onError = () => {}, onRecovered = () => {} }) {
  const button = document.querySelector("#taskButton");
  const content = document.querySelector("#taskContent");
  const toast = document.querySelector("#taskToast");
  const active = job => !["ready", "failed"].includes(job.status);
  let actor = null, data = null, loading = false, error = "", timer = null, page = 0;
  let generation = 0, pushInfo = null, pushBusy = false, pushChecking = false, pushRevision = 0, pushError = "", toastTimer = null;
  let noticePage = 0, readRevision = 0, readBusy = false, readError = "", viewTimer = null, refreshAgain = false, workerUpdate = false;
  let readQueue = new Set(), pendingOpen = new URLSearchParams(location.search).get("tasks") === "1";
  let pendingNotices = [];
  try { pendingOpen ||= sessionStorage.getItem("trace-admin-open-tasks") === "1"; } catch { /* The URL still covers cold starts. */ }
  const readLocal = key => { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } };
  const saveLocal = (key,value) => { try { localStorage.setItem(key,JSON.stringify(value)); } catch { /* Server history still works without local storage. */ } };
  const key = suffix => `trace-admin-tasks:${actor}:${suffix}`;
  function supported() { return isSecureContext && "Notification" in window && "serviceWorker" in navigator && "PushManager" in window; }
  const keyBytes = value => Uint8Array.from(atob(value.replace(/-/g,"+").replace(/_/g,"/")+"="),c=>c.charCodeAt(0));
  function matchingKey(subscription, publicKey) {
    const existing = subscription.options?.applicationServerKey;
    if (!existing) return true;
    const expected = keyBytes(publicKey), actual = new Uint8Array(existing);
    return expected.length === actual.length && expected.every((byte,index)=>byte === actual[index]);
  }
  async function subscriptionId(subscription) {
    const digest = await crypto.subtle.digest("SHA-256",new TextEncoder().encode(subscription.endpoint));
    return [...new Uint8Array(digest)].map(byte=>byte.toString(16).padStart(2,"0")).join("");
  }
  async function reconcilePush(value, current, revision) {
    const unchanged = ()=>current === generation && revision === pushRevision && !pushBusy;
    if (!unchanged()) return;
    if (!supported() || Notification.permission !== "granted" || !value.pushPublicKey) { pushInfo = null; return; }
    pushChecking = true; render();
    try {
      const registration = await navigator.serviceWorker.getRegistration("/");
      if (!workerUpdate && registration?.active?.scriptURL === new URL("/admin-sw.js",location.origin).href) {
        workerUpdate = true;
        void registration.update().catch(()=>{});
      }
      const subscription = await registration?.pushManager.getSubscription();
      const id = subscription && matchingKey(subscription,value.pushPublicKey) ? await subscriptionId(subscription) : null;
      const registered = value.pushSubscriptions?.find(row=>row.id === id && row.expiresAt > Date.now()/1000);
      if (unchanged()) pushInfo = registered ? {id:registered.id,expiresAt:registered.expiresAt} : null;
      if (unchanged()) onRecovered("tasks-push-check");
    } catch (e) {
      if (unchanged()) {
        pushInfo = null;
        pushError = text("暂时无法核对浏览器订阅，未更改已有订阅。", "Unable to check the browser subscription. Existing subscriptions were not changed.") + " " + e.message;
        onError(new Error(pushError), "tasks-push-check");
      }
    } finally { if (unchanged()) { pushChecking = false; render(); } }
  }
  function phase(job) {
    return ({ dispatching: text("正在提交", "Submitting"), queued: text("等待构建状态", "Awaiting build status"),
      awaiting_approval: text("等待 GitHub 手动审批", "Awaiting GitHub reviewer approval"),
      ci_queued: text("GitHub 排队中", "Queued in GitHub"), ci_preparing: text("前置检查 / 准备构建", "Prechecks / preparing build"),
      ci_waiting: text("等待 GitHub 环境放行", "Waiting for GitHub environment"),
      ci_finished: text("GitHub 流程已结束，请核对结果", "GitHub run finished; reconcile the result"),
      ci_pending: text("正在查询构建记录", "Looking up the build run"), ci_unavailable: text("暂时无法读取构建状态", "Build status temporarily unavailable"),
      dispatch_unknown: text("提交结果未知，请核对", "Dispatch uncertain; reconcile"),
      building: text("构建与重建校验", "Building and reconstruction checks"), running: text("构建与重建校验", "Building and reconstruction checks"),
      uploading: text("上传差分文件", "Uploading delta"), verifying: text("等待校验登记", "Awaiting verification and registration"),
      ready: job.enabled ? text("已生成并启用", "Ready and enabled") : text("已生成，待启用", "Ready, not enabled"),
      failed: text("生成失败", "Build failed") })[job.phase ?? job.status] ?? job.status;
  }
  function elapsed(job) {
    if (!job.createdAt) return "";
    const end = active(job) ? Math.floor(Date.now()/1000) : job.updatedAt;
    const seconds = Math.max(0, (end ?? job.createdAt) - job.createdAt);
    return text("耗时 ", "Elapsed ") + (seconds < 60 ? `${seconds}s` : `${Math.floor(seconds/60)}m ${seconds%60}s`);
  }
  function progress(job) {
    const phases = ["queued", "building", "uploading", "verifying", "ready"];
    const phaseName = job.phase ?? (job.status === "running" ? "building" : job.status);
    const current = ["awaiting_approval", "ci_queued", "ci_preparing", "ci_waiting", "ci_pending"].includes(phaseName) ? "queued" : phaseName;
    const index = phases.indexOf(current);
    const labels = [text("排队", "Queue"),text("构建", "Build"),text("上传", "Upload"),text("登记", "Verify"),text("完成", "Ready")];
    if (phaseName === "awaiting_approval") labels[0] = text("待审批", "Approval");
    if (phaseName === "ci_preparing") labels[0] = text("前置检查", "Prechecks");
    return `<div class="task-progress" data-state="${escape(job.status)}" aria-label="${escape(phase(job))}">
      ${labels.map((label,i)=>`<span class="${index >= 0 && i < index ? "done" : i === index ? "current" : ""}" ${i === index ? 'aria-current="step"' : ""}><i></i>${escape(label)}</span>`).join("")}</div>
      <small class="task-time">${escape(elapsed(job))}${job.updatedAt ? ` · ${escape(text("更新于 ","Updated "))}${escape(new Date(job.updatedAt*1000).toLocaleTimeString())}` : ""}</small>`;
  }
  function notify(message) {
    clearTimeout(toastTimer);
    toast.querySelector("span").textContent = message;
    toast.hidden = false;
    toastTimer = setTimeout(()=>{ toast.hidden = true; },10000);
  }
  function resume() {
    announce();
    if (!pendingOpen || !actor || document.hidden) return;
    pendingOpen = false;
    if (openPanel() === false) { pendingOpen = true; return; }
    try { sessionStorage.removeItem("trace-admin-open-tasks"); } catch { /* No business state is stored here. */ }
    const url = new URL(location.href);
    if (url.searchParams.get("tasks") === "1") {
      url.searchParams.delete("tasks"); history.replaceState(history.state,"",url.href);
    }
  }
  function announce() {
    if (!actor || document.hidden || !canNotify()) return;
    const last = Number(readLocal(key("noticed")) ?? 0);
    const fresh = pendingNotices.filter(n=>n.unread && n.id > last);
    if (!fresh.length) return;
    const arrival = fresh.length === 1 && fresh[0].type === "candidate" ? fresh[0] : null;
    notify(arrival ? `${arrival.kind === "firmware" ? "MCU" : arrival.kind === "windows" ? "Windows App" : "Android App"} ${arrival.versionName} · ${text("新构建包已入库，待发布", "New candidate registered, not published")}`
      : text(`${fresh.length} 条新结果，可在任务与通知中查看。`, `${fresh.length} new results. Open Tasks and notifications to review.`));
    saveLocal(key("noticed"),Math.max(...fresh.map(n=>n.id)));
    pendingNotices = [];
  }
  function requestPanel() {
    pendingOpen = true;
    try { sessionStorage.setItem("trace-admin-open-tasks","1"); } catch { /* Keep the in-memory intent. */ }
    resume();
  }
  function scheduleVisibleRead() {
    clearTimeout(viewTimer);
    if (!actor || readBusy || readError || document.hidden || content.closest("[hidden], [inert]")) return;
    viewTimer = setTimeout(()=>{
      if (document.hidden || content.closest("[hidden], [inert]")) return;
      const root = document.querySelector("#taskScroll").getBoundingClientRect();
      const ids = [...content.querySelectorAll(".task-notification.unread")].filter(node=>{
        const rect = node.getBoundingClientRect();
        const width = Math.max(0,Math.min(rect.right,root.right,innerWidth)-Math.max(rect.left,root.left,0));
        const height = Math.max(0,Math.min(rect.bottom,root.bottom,innerHeight)-Math.max(rect.top,root.top,0));
        return rect.width > 0 && rect.height > 0 && width*height >= rect.width*rect.height*.75;
      }).map(node=>Number(node.dataset.notificationId));
      if (ids.length) void markRead(ids);
    },500);
  }
  async function markRead(ids = [], throughId = null) {
    for (const id of ids) if (data?.notifications.some(n=>n.id === id && n.unread)) readQueue.add(id);
    if (!actor || readBusy || (!readQueue.size && throughId === null)) return;
    const current = generation, batch = [...readQueue].slice(0,30);
    batch.forEach(id=>readQueue.delete(id));
    readBusy = true; readError = ""; render();
    let confirmed = false;
    try {
      const result = await mutate("/api/admin/delta/notifications/read",throughId === null ? {ids:batch} : {throughId});
      if (current !== generation) return;
      if (result.ok !== true || (throughId === null
        ? !Array.isArray(result.readIds) || !batch.every(id=>result.readIds.includes(id))
        : !Number.isSafeInteger(result.throughId) || result.throughId < throughId)) throw new Error(text("服务器未确认已读状态。", "The server did not confirm read status."));
      readRevision++; confirmed = true;
      onRecovered("tasks-read");
      let consumed = 0;
      data.notifications = data.notifications.map(n=>{
        if (!n.unread || !(throughId === null ? batch.includes(n.id) : n.id <= throughId)) return n;
        consumed++; return {...n,unread:0};
      });
      data.unreadCount = Math.max(0,data.unreadCount-consumed);
    } catch (e) {
      if (current === generation) {
        readError = text("已读状态保存失败，未读提示暂时保留。请刷新后重试。", "Read status could not be saved. Unread indicators are retained; refresh to retry.") + " " + e.message;
        onError(new Error(readError), "tasks-read");
        readQueue.clear();
      }
    } finally {
      if (current === generation) {
        readBusy = false; render();
        if (confirmed) { void refresh(); if (readQueue.size) void markRead(); }
      }
    }
  }
  function render() {
    const focused = content.contains(document.activeElement) ? document.activeElement : null;
    const focusAction = focused?.dataset.taskAction, focusTarget = focused?.dataset.taskTarget, focusNotice = focused?.dataset.notificationId;
    const jobs = data?.jobs ?? [], running = jobs.filter(active).length, unread = data?.unreadCount ?? 0;
    button.disabled = !actor;
    button.querySelector(".task-label").textContent = text("任务", "Tasks");
    button.setAttribute("aria-label", `${text("任务与通知", "Tasks and notifications")}: ${running} ${text("进行中", "active")}, ${unread} ${text("未读", "unread")}`);
    const badge = button.querySelector(".task-badge");
    badge.textContent = String(unread); badge.hidden = !unread;
    button.dataset.running = String(running > 0);
    button.title = button.getAttribute("aria-label");
    document.querySelector("#taskTitle").textContent = text("任务与通知", "Tasks and notifications");
    document.querySelector("#taskClose").setAttribute("aria-label",text("关闭任务", "Close tasks"));
    toast.querySelector("button").textContent = text("查看任务", "View tasks");
    const enabled = supported() && Notification.permission === "granted" && pushInfo?.expiresAt > Date.now()/1000;
    const pushText = !supported() ? text("此浏览器不支持后台系统提醒，结果仍保留在这里。", "This browser does not support background push. Results remain here.")
      : Notification.permission === "denied" ? text("浏览器已阻止通知，可在网站权限中允许；任务照常生成。", "Notifications are blocked in site settings. Builds are unaffected.")
      : pushChecking ? text("正在核对浏览器与服务器的推送订阅...", "Checking browser and server push subscriptions...")
      : enabled ? text("已开启提醒，浏览器与服务器订阅已核对。系统或浏览器限制仍可能阻止通知。", "Alerts enabled; browser and server subscriptions match. Browser or OS policies can still block notifications.")
      : Notification.permission === "granted" ? text("浏览器已允许通知，但尚未确认有效的推送订阅。请点击开启提醒。", "Browser permission is allowed, but no matching push subscription is confirmed. Select Enable alerts.")
      : text("开启系统提醒后，切到后台也可接收结果。首次需要允许浏览器通知。", "Enable system alerts for background results. Browser permission is required once.");
    page = Math.max(0,Math.min(page,Math.ceil(jobs.length/8)-1));
    const notifications = data?.notifications ?? [];
    noticePage = Math.max(0,Math.min(noticePage,Math.ceil(notifications.length/6)-1));
    content.innerHTML = `<section class="task-notification-settings"><div><strong>${escape(text("系统提醒", "System alerts"))}</strong><p>${escape(pushText)}</p>
      ${pushError ? `<p class="error" role="alert">${escape(pushError)}</p>` : ""}</div>
      <button type="button" class="secondary-button" data-task-action="${enabled ? "push-off" : "push-on"}" ${pushBusy || pushChecking || !supported() || !data?.pushPublicKey || (!enabled && Notification.permission === "denied") ? "disabled" : ""}>${escape(enabled ? text("关闭提醒", "Turn off") : text("开启提醒", "Enable alerts"))}</button></section>
      ${data && !data.pushPublicKey ? `<p class="firmware-hint">${escape(text("服务器推送尚未配置，站内通知仍可使用。", "Server push is not configured. In-app notifications still work."))}</p>` : ""}
      <div class="operations-buttons task-toolbar"><button type="button" class="secondary-button" data-task-action="refresh" ${loading ? "disabled" : ""}>${escape(text("刷新", "Refresh"))}</button>
      <button type="button" class="secondary-button" data-task-action="read" ${!unread || loading || readBusy ? "disabled" : ""}>${escape(text("全部标为已读", "Mark all read"))}</button><span>${running} ${escape(text("进行中", "active"))} · ${unread} ${escape(text("未读", "unread"))}</span></div>
      ${readError ? `<p class="error" role="alert">${escape(readError)}</p>` : ""}
      ${error ? `<p class="error" role="alert">${escape(error)} ${escape(text("上次状态已保留，恢复连接后重新读取，不会重发构建。", "Previous status retained; reconnecting only rereads, never redispatches builds."))}</p>` : ""}
      ${loading && !data ? `<p role="status">${escape(text("正在读取任务...", "Loading tasks..."))}</p>` : ""}
      <div class="task-notifications">${notifications.slice(noticePage*6,(noticePage+1)*6).map(n=>`<button type="button" class="task-notification ${n.unread ? "unread" : ""}" data-notification-id="${n.id}" data-task-type="${escape(n.type ?? "delta")}" data-task-kind="${escape(n.kind)}" data-task-target="${escape(n.targetReleaseId)}"><span>${escape(n.kind === "firmware" ? text("单片机", "MCU") : n.kind === "windows" ? "Windows App" : "Android App")} · ${n.type === "candidate" ? escape(n.versionName) : `${escape(n.baseVersionCode)} → ${escape(n.targetVersionCode)}`}</span><strong>${escape(n.type === "candidate" ? text("新构建包已入库，查看详情", "New candidate registered, open details") : n.status === "ready" ? text("差分包已生成", "Delta ready") : text("差分生成失败", "Delta failed"))}</strong><small>${escape(new Date(n.createdAt*1000).toLocaleString())}</small></button>`).join("")}</div>
      ${notifications.length > 6 ? `<nav class="release-pagination" aria-label="${escape(text("通知分页", "Notification pages"))}"><button type="button" data-task-action="notice-prev" ${noticePage === 0 ? "disabled" : ""}>${escape(text("上一页通知", "Previous notifications"))}</button><span>${noticePage+1} / ${Math.ceil(notifications.length/6)}</span><button type="button" data-task-action="notice-next" ${(noticePage+1)*6 >= notifications.length ? "disabled" : ""}>${escape(text("下一页通知", "Next notifications"))}</button></nav>` : ""}
      <h3 class="delta-jobs-title">${escape(text("我的差分任务", "My delta jobs"))}</h3>
      <p class="firmware-hint">${escape(text("App 与单片机共用任务记录；关闭弹窗不会取消任务。成功后仍需手动启用，不会自动发布渠道。", "App and MCU jobs share this history. Closing does not cancel. Verified deltas still need manual enabling; channels are never auto-published."))}</p>
      <div class="task-job-list">${jobs.slice(page*8,(page+1)*8).map(job=>`<article class="task-job" data-job-id="${escape(job.id)}"><div class="task-job-title"><strong>${escape(job.kind === "firmware" ? text("单片机", "MCU") : "App")} · ${escape(job.baseVersionCode)} → ${escape(job.targetVersionCode)}</strong><span>${escape(phase(job))}</span></div>${progress(job)}
        ${job.errorCode ? `<p class="error">${escape(job.errorCode)}</p>` : ""}<div class="task-job-footer"><span>${job.sizeBytes ? escape(formatBytes(job.sizeBytes)) : escape(text("进度按真实阶段显示，不估算百分比。", "Actual stages, not estimated percentages."))}</span>
        ${/^https:\/\/github\.com\/Eitan-S-23\/(?:E-Track|Trace)\/actions\/runs\/\d+$/.test(job.runUrl ?? "") ? `<a href="${escape(job.runUrl)}" target="_blank" rel="noopener noreferrer">${escape(job.phase === "awaiting_approval" ? text("前往 GitHub 审批", "Review in GitHub") : text("查看构建", "Open build"))}</a>` : ""}
        <button type="button" class="text-button" data-task-kind="${escape(job.kind)}" data-task-target="${escape(job.targetReleaseId)}">${escape(text("查看差分", "Open deltas"))}</button></div></article>`).join("") || `<p class="empty">${escape(text("还没有你的差分任务。", "No delta jobs submitted by this account yet."))}</p>`}</div>
      ${jobs.length > 8 ? `<nav class="release-pagination"><button type="button" data-task-action="prev" ${page === 0 ? "disabled" : ""}>${escape(text("上一页", "Previous"))}</button><span>${page+1} / ${Math.ceil(jobs.length/8)}</span><button type="button" data-task-action="next" ${(page+1)*8 >= jobs.length ? "disabled" : ""}>${escape(text("下一页", "Next"))}</button></nav>` : ""}`;
    if (focused && !content.closest("[hidden], [inert]")) {
      [...content.querySelectorAll("button")].find(node=>!node.disabled && (focusNotice ? node.dataset.notificationId === focusNotice : focusAction ? node.dataset.taskAction === focusAction
        : focusTarget && node.dataset.taskTarget === focusTarget && node.dataset.taskKind === focused.dataset.taskKind))?.focus({preventScroll:true});
    }
    scheduleVisibleRead();
  }
  function schedule() {
    clearTimeout(timer);
    if (!actor) return;
    timer = setTimeout(refresh, document.hidden ? 120000 : data?.jobs.some(active) ? 30000 : 60000);
  }
  async function refresh() {
    if (!actor) return;
    if (loading) { refreshAgain = true; return; }
    const current = generation, identity = actor, pushSnapshot = pushRevision, readSnapshot = readRevision;
    loading = true; render();
    try {
      const value = await api("/api/admin/delta/activity");
      if (current !== generation) return;
      if (readSnapshot !== readRevision) { refreshAgain = true; return; }
      if (value.actor && value.actor !== identity) {
        setActor(null); error = text("登录账号已变化，请刷新后台。", "Account changed. Refresh Admin."); render(); return;
      }
      if (value.ok !== true || value.actor !== identity || value.scope !== "own-jobs" || !Array.isArray(value.jobs) || !Array.isArray(value.notifications)) throw new Error(text("任务状态读取失败", "Invalid task response"));
      data = value; error = "";
      onRecovered("tasks-refresh");
      // A response started before a subscription change cannot undo its result.
      await reconcilePush(value,current,pushSnapshot);
      if (current !== generation) return;
      if (readSnapshot !== readRevision) { refreshAgain = true; return; }
      pendingNotices = value.notifications;
      const previouslyNoticed = Number(readLocal(key("noticed")) ?? 0);
      for (const notice of value.notifications) {
        if (notice.unread && notice.id > previouslyNoticed && notice.status === "failed" && notice.type !== "candidate") {
          onError(new Error(`${text("差分生成失败", "Delta build failed")}: ${notice.baseVersionCode} → ${notice.targetVersionCode}\n${notice.errorCode ?? "CI_BUILD_FAILED"}`),
            `delta-result:${notice.jobId}:${notice.attempt}`);
        }
      }
      announce();
      onJobs(value.jobs);
    } catch (e) { if (current === generation) { error = e.message; onError(e, "tasks-refresh"); } }
    finally {
      if (current === generation) {
        loading = false; render();
        if (refreshAgain) { refreshAgain = false; clearTimeout(timer); timer = setTimeout(refresh,0); }
        else schedule();
      }
    }
  }
  async function enablePush() {
    if (!supported() || !data?.pushPublicKey || pushBusy || pushChecking) return;
    const current = generation, publicKey = data.pushPublicKey;
    pushRevision++; pushBusy = true; pushError = ""; render();
    onRecovered("tasks-push");
    let stage = "permission";
    try {
      // Permission is requested only from the user's click, never from a poll.
      const permission = Notification.permission === "granted" ? "granted" : await Notification.requestPermission();
      if (current !== generation || permission !== "granted") return;
      stage = "worker";
      const registration = await navigator.serviceWorker.register("/admin-sw.js",{scope:"/",updateViaCache:"none"});
      await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();
      if (current !== generation) return;
      stage = "provider";
      if (subscription && !matchingKey(subscription,publicKey)) throw new Error(text(
        "浏览器保留了使用不同密钥的订阅。请在网站通知设置中取消旧授权后重新允许；已有订阅未被自动取消。",
        "The browser subscription uses a different key. Reset this site's notification permission, then allow it again. The existing subscription was not automatically removed."));
      subscription ??= await registration.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:keyBytes(publicKey)});
      if (current !== generation) return;
      stage = "server";
      const expectedId = await subscriptionId(subscription);
      if (current !== generation) return;
      const result = await mutate("/api/admin/delta/notifications/subscribe",{endpoint:subscription.endpoint,applicationServerKey:publicKey});
      if (current !== generation) return;
      if (result.ok !== true || result.id !== expectedId || !(result.expiresAt > Date.now()/1000)) throw new Error(text("后台未返回有效订阅确认。", "The server did not confirm a valid subscription."));
      pushInfo = {id:result.id,expiresAt:result.expiresAt};
    } catch (e) {
      if (current === generation) {
        const detail = String(e.message ?? e);
        pushError = /Registration failed.*push service error/i.test(detail)
          ? text("浏览器向推送服务注册失败，系统提醒尚未开启。请检查浏览器及网络；差分任务和站内结果不受影响。", "Browser registration with the push service failed. System alerts are not enabled. Check the browser and network; builds and in-app results are unaffected.") + " " + detail
          : (stage === "server" ? text("浏览器订阅已保留，但后台登记未成功；再次开启会复用订阅，不会重发构建。", "The browser subscription was preserved, but server registration failed. Enabling again reuses it and never restarts builds.")
            : text("系统提醒设置未完成，差分任务不受影响。", "System alert setup did not complete. Delta builds are unaffected.")) + " " + detail;
        onError(new Error(pushError), "tasks-push");
      }
    }
    finally { if (current === generation) { pushBusy = false; render(); } }
  }
  content.addEventListener("click", async event => {
    const target = event.target.closest("button");
    if (!target || target.disabled) return;
    if (target.dataset.taskTarget) {
      const current = generation;
      onRecovered("tasks-open");
      try {
        if (await openTarget(target.dataset.taskKind,target.dataset.taskTarget,target.dataset.taskType ?? "delta") !== false
          && current === generation && target.dataset.notificationId) void markRead([Number(target.dataset.notificationId)]);
      } catch (e) { if (current === generation) { error = e.message; onError(e, "tasks-open"); render(); } }
      return;
    }
    const action = target.dataset.taskAction;
    if (action === "push-on") { await enablePush(); return; }
    const current = generation;
    try {
      if (action === "refresh") { readError = ""; onRecovered("tasks-refresh"); onRecovered("tasks-read"); await refresh(); }
      if (action === "prev" || action === "next") { page += action === "prev" ? -1 : 1; render(); }
      if (action === "notice-prev" || action === "notice-next") { noticePage += action === "notice-prev" ? -1 : 1; render(); }
      if (action === "read") {
        await markRead([],Math.max(0,...(data?.notifications ?? []).map(n=>n.id)));
      }
      if (action === "push-off" && pushInfo && !pushBusy && !pushChecking) {
        pushRevision++; pushBusy = true; pushError = ""; render();
        await mutate("/api/admin/delta/notifications/unsubscribe",{id:pushInfo.id});
        if (current !== generation) return;
        pushInfo = null;
        const registration = await navigator.serviceWorker.getRegistration("/");
        await (await registration?.pushManager.getSubscription())?.unsubscribe();
      }
    } catch (e) { if (current === generation) {
      if (action === "push-off") pushError = e.message; else error = e.message;
      onError(e, action === "push-off" ? "tasks-push" : "tasks-action");
    } }
    finally { if (current === generation) { if (action === "push-off") pushBusy = false; render(); } }
  });
  toast.querySelector("button").addEventListener("click",()=>{ requestPanel(); toast.hidden = true; });
  document.querySelector("#taskScroll").addEventListener("scroll",scheduleVisibleRead,{passive:true});
  window.addEventListener("resize",scheduleVisibleRead);
  document.addEventListener("visibilitychange",()=>{ clearTimeout(viewTimer); if (!document.hidden) { resume(); refresh(); } else schedule(); });
  window.addEventListener("online",refresh);
  window.addEventListener("pageshow",()=>{ resume(); refresh(); });
  navigator.serviceWorker?.addEventListener("message",event=>{
    if (event.data?.type === "trace-delta-updated") refresh();
    if (event.data?.type === "trace-delta-open") {
      requestPanel();
      event.ports?.[0]?.postMessage({type:"trace-delta-open-accepted"});
      refresh();
    }
  });
  function setActor(value) {
    if (actor === value) { refresh(); return; }
    actor = value; generation++; data = null; loading = false; error = ""; page = 0; pushBusy = false; pushChecking = false; pushError = "";
    noticePage = 0; readRevision = 0; readBusy = false; readError = ""; readQueue = new Set(); refreshAgain = false; clearTimeout(viewTimer);
    clearTimeout(timer); clearTimeout(toastTimer); toast.hidden = true; pendingNotices = [];
    pushInfo = null;
    render(); if (actor) { refresh(); resume(); }
  }
  return { refresh, render, setActor, progress, phase, resume };
};
