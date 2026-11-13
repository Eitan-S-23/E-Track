window.TraceResourceUsage = function ({ element, api, text, escape, formatBytes, onResize = () => {} }) {
  let actor = null, generation = 0, data = null, busy = false, error = "";
  const groups = {workers:"Workers",pages:"Pages Functions",d1:"D1",durableObjects:"Durable Objects / SQLite",r2:"R2"};
  const labels = {
    workerRequests:["请求","Requests"],workerCpu:["CPU 总时间","Total CPU"],pagesRequests:["后台请求","Admin requests"],
    pagesCpuP50:["后台 CPU P50","Admin CPU P50"],pagesCpuP99:["后台 CPU P99","Admin CPU P99"],
    publicPagesRequests:["公开更新 API 请求","Public update API requests"],publicPagesCpuP50:["公开 API CPU P50","Public API CPU P50"],
    publicPagesCpuP99:["公开 API CPU P99","Public API CPU P99"],
    d1Read:["读取行","Rows read"],d1Write:["写入行","Rows written"],d1Storage:["存储采样","Storage sample"],
    doRequests:["请求","Requests"],doDuration:["运行时长","Duration"],doRead:["SQLite 读取行","SQLite rows read"],
    doWrite:["SQLite 写入行","SQLite rows written"],doStorage:["SQLite 存储采样","SQLite storage sample"],
    r2ClassA:["Class A 操作（月内）","Class A operations (month to date)"],r2ClassB:["Class B 操作（月内）","Class B operations (month to date)"],
    r2Storage:["标准存储采样","Standard storage sample"],r2IaStorage:["低频存储采样","Infrequent Access storage sample"]
  };
  const statuses = {ok:["已测量","Measured"],stale:["旧数据","Stale"],not_configured:["未接入","Not connected"],
    permission_denied:["无读取权限","Read permission denied"],unavailable:["暂不可用","Unavailable"],
    no_samples:["无采样数据","No samples"],refreshing:["正在更新","Refreshing"]};
  const date = value => Number.isFinite(value) ? new Date(value*1000).toLocaleString() : text("未知","Unknown");
  const amount = metric => metric.used === null || !Number.isFinite(metric.used) ? text("未知","Unknown")
    : metric.unit === "bytes" ? formatBytes(metric.used) : `${metric.used.toLocaleString(undefined,{maximumFractionDigits:3})} ${metric.unit}`;
  const status = value => text(...(statuses[value] ?? statuses.unavailable));
  function render() {
    const opened = new Set([...element.querySelectorAll("details[open]")].map(node=>node.dataset.usageGroup));
    element.innerHTML = `<section class="provider-usage" aria-label="${escape(text("服务商用量","Provider usage"))}">
      <div class="usage-heading"><h3>${escape(text("服务商用量","Provider usage"))}</h3><button type="button" class="text-button" data-usage-refresh ${busy || !actor ? "disabled" : ""}>${escape(busy ? text("读取中","Loading") : text("刷新","Refresh"))}</button></div>
      <p class="usage-note">${escape(text("仅统计配置的项目资源，不是整个账户余额。套餐、额度及剩余：未知。","Configured project resources only, not account-wide remaining usage. Plan, allowance and remaining: unknown."))}</p>
      ${error ? `<p class="error" role="alert">${escape(error)} ${escape(text("保留上次结果，不按零计算。","Previous results retained, never treated as zero."))}</p>` : ""}
      ${!data ? `<p role="status">${escape(busy ? text("正在读取服务商统计…","Loading provider metrics...") : text("打开面板后读取。","Loaded when this panel opens."))}</p>` : `
      <p class="usage-note">${escape(text("查询时间：","Checked: "))}${escape(date(data.checkedAt))}<br>${escape(text("下次可更新：","Next refresh: "))}${escape(date(data.nextRefreshAt))}</p>
      ${Object.entries(groups).map(([group,label])=>`<details class="usage-group" data-usage-group="${group}" ${opened.has(group) || (!element.querySelector("details") && group === "workers") ? "open" : ""}>
        <summary>${label}</summary>${data.metrics.filter(metric=>metric.group === group && labels[metric.key]).map(metric=>`<div class="usage-metric" data-usage-key="${escape(metric.key)}" data-state="${escape(error ? "stale" : metric.state)}">
          <div><span>${escape(text(...labels[metric.key]))}</span><strong>${escape(amount(metric))}</strong></div>
          <small>${escape(status(error ? "stale" : metric.state))}${metric.reason && metric.reason !== metric.state ? ` · ${escape(status(metric.reason))}` : ""} · ${escape(text("额度 / 剩余：未知","Allowance / remaining: unknown"))}</small>
          <small>${escape(text("范围：","Scope: "))}${escape(metric.scope)}</small>
          <small>${escape(text("统计窗口：","Window: "))}${escape(date(metric.periodStart))} → ${escape(date(metric.periodEnd))}</small>
          <small>${escape(text("最近成功查询：","Last successful query: "))}${escape(date(metric.lastSuccessAt))}${metric.sampledAt !== null ? `<br>${escape(text("采样时间：","Sampled: "))}${escape(date(metric.sampledAt))}` : ""}</small>
          ${metric.periodRolloverAt ? `<small>${escape(text("统计窗口切换：","Window rolls over: "))}${escape(date(metric.periodRolloverAt))}</small>` : ""}
        </div>`).join("")}</details>`).join("")}
      <p class="usage-note">${escape(text("数据可能延迟或抽样；排除最近 5 分钟。R2 操作按自然月统计，不是账单；存储为采样值，不是 GB·月。Pages CPU 为单次调用分位数，不是总 CPU。账户额度的重置时间未知。","Analytics may be delayed or sampled; the last five minutes are excluded. R2 operations use calendar months, not billing periods; storage is a sample, not GB-month. Pages CPU shows invocation percentiles, not total CPU. Account quota reset time is unknown."))}</p>
      <section class="usage-separate"><h4>GitHub Actions</h4><p>${escape(text("尚未接入 GitHub 账单用量，与 Cloudflare 分开计算。","GitHub billing usage is not connected and is separate from Cloudflare."))}</p></section>
      <section class="usage-separate"><h4>${escape(text("版本上报保护限制","Reporting safeguards"))}</h4><p>${escape(text(`App ${data.safeguards?.clientReportsPerUtcDay ?? "?"} 次/UTC 日；后台 ${data.safeguards?.backendReportsPerUtcDay ?? "?"} 次/UTC 日。这不是服务商额度，也不能换算为 D1 写入次数。`, `App ${data.safeguards?.clientReportsPerUtcDay ?? "?"}/UTC day; backend ${data.safeguards?.backendReportsPerUtcDay ?? "?"}/UTC day. These are not provider quotas or D1 write counts.`))}</p></section>`}
    </section>`;
    element.querySelectorAll("details").forEach(node=>node.addEventListener("toggle",onResize));
    onResize();
  }
  async function load() {
    if (!actor || busy) return;
    const current = generation;
    busy = true; error = ""; render();
    try {
      const value = await api("/api/admin/resource-usage");
      if (current !== generation) return;
      if (value.ok !== true || !Array.isArray(value.metrics)) throw new Error(text("用量响应无效。","Invalid usage response."));
      data = value;
    } catch (e) { if (current === generation) error = e.message; }
    finally { if (current === generation) { busy = false; render(); } }
  }
  element.addEventListener("click",event=>{ if (event.target.closest("[data-usage-refresh]")) void load(); });
  return {load,render,setActor(value) {
    if (value === actor) return;
    actor = value; generation++; data = null; error = ""; busy = false; render();
  }};
};
