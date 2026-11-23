window.TraceResourceUsage = function ({ element, api, text, escape, formatBytes, onResize = () => {}, onError = () => {}, onRecovered = () => {} }) {
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
  const quotaLabels = {
    accountRequests:["账户请求（Workers + Pages）","Account requests (Workers + Pages)"],accountCpuLimit:["单次 CPU 上限","CPU limit per invocation"],
    accountD1Read:["账户读取行","Account rows read"],accountD1Write:["账户写入行","Account rows written"],accountD1Storage:["账户存储","Account storage"],
    accountDoRequests:["账户请求","Account requests"],accountDoDuration:["账户运行时长","Account duration"],
    accountDoRead:["账户 SQLite 读取行","Account SQLite rows read"],accountDoWrite:["账户 SQLite 写入行","Account SQLite rows written"],
    accountDoStorage:["账户 SQLite 存储","Account SQLite storage"],accountR2ClassA:["Standard Class A","Standard Class A"],
    accountR2ClassB:["Standard Class B","Standard Class B"],accountR2Storage:["Standard 存储累计估算","Standard accrued storage estimate"]
  };
  const reasons = {unknown_plan:["套餐未确认","Plan not established"],unknown_billing_period:["账期未确认","Billing period not established"],
    incomplete_coverage:["数据覆盖不完整","Incomplete data coverage"],unsupported_meter:["该计量暂无法完整查询","Complete metering is unavailable"],
    invalid_usage:["用量数据无效","Invalid usage data"],response_too_large:["响应超出安全上限","Response exceeds safety limit"],
    per_invocation:["这是单次调用限制，不是账户余额","Per-invocation limit, not an account balance"]};
  const statuses = {ok:["已测量","Measured"],stale:["旧数据","Stale"],not_configured:["未接入","Not connected"],
    permission_denied:["无读取权限","Read permission denied"],unavailable:["暂不可用","Unavailable"],
    no_samples:["无采样数据","No samples"],refreshing:["正在更新","Refreshing"]};
  const date = value => Number.isFinite(value) ? new Date(value*1000).toLocaleString() : text("未知","Unknown");
  const amount = (value, unit) => !Number.isFinite(value) || value < 0 ? text("未知","Unknown")
    : unit === "bytes" ? formatBytes(value) : `${value.toLocaleString(undefined,{maximumFractionDigits:value < 1 ? 6 : 3})} ${unit === "GB-month" ? text("GB·月","GB-month") : unit}`;
  const status = value => text(...(statuses[value] ?? statuses.unavailable));
  const reason = value => text(...(reasons[value] ?? statuses[value] ?? statuses.unavailable));
  function quotaRow(quota) {
    const state = error && quota.used !== null ? "stale" : quota.state;
    const invocation = quota.limitKind === "per_invocation";
    const percent = Number.isFinite(quota.used) && Number.isFinite(quota.allowance) && quota.allowance > 0 ? Math.min(100,quota.used/quota.allowance*100) : null;
    return `<div class="usage-metric usage-quota" data-quota-key="${escape(quota.key)}" data-state="${escape(state)}" data-limit-kind="${escape(quota.limitKind)}">
      <div><span>${escape(text(...quotaLabels[quota.key]))}</span><strong>${escape(amount(invocation ? quota.allowance : quota.used,quota.unit))}</strong></div>
      ${!invocation ? `<div class="usage-quota-balance"><span>${escape(text(quota.limitKind === "hard" ? "额度：" : "免费包含量：",quota.limitKind === "hard" ? "Limit: " : "Included: "))}${escape(amount(quota.allowance,quota.unit))}</span><span>${escape(text("预计剩余：","Estimated remaining: "))}<b data-quota-remaining>${escape(amount(quota.remaining,quota.unit))}</b></span></div>` : ""}
      ${percent !== null && !invocation ? `<div class="usage-quota-track" role="progressbar" aria-label="${escape(text(...quotaLabels[quota.key]))}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent.toFixed(2)}"><span style="width:${percent.toFixed(2)}%"></span></div>` : ""}
      ${Number.isFinite(quota.overage) && quota.overage > 0 ? `<small class="usage-overage">${escape(text("超出额度：","Above allowance: "))}${escape(amount(quota.overage,quota.unit))}${quota.limitKind === "included" ? ` · ${escape(text("超出免费包含量不代表服务停止","Exceeding included usage does not mean the service stops"))}` : ""}</small>` : ""}
      <small>${escape(status(state))} · ${escape(text("范围：整个 Cloudflare 账户（含其他项目）","Scope: entire Cloudflare account (including other projects)"))}</small>
      ${quota.planName ? `<small>${escape(text("套餐：","Plan: "))}${escape(quota.planName)}</small>` : ""}
      ${quota.reason ? `<small>${escape(reason(quota.reason))}</small>` : ""}
      ${!invocation ? `<small>${escape(text("统计窗口：","Window: "))}${escape(date(quota.periodStart))} → ${escape(date(quota.periodEnd))}</small>
      <small>${escape(quota.unit === "GB" && quota.quotaResetAt === null ? text("容量限制，无每日重置。","Storage capacity, no daily reset.") : text("额度重置：","Allowance resets: ")+date(quota.quotaResetAt))}</small>` : ""}
      <small>${escape(text("最近成功查询：","Last successful query: "))}${escape(date(quota.lastSuccessAt))}</small>
      ${quota.coverage ? `<small>${escape(text(`采样覆盖 ${quota.coverage.observedDays}/${quota.coverage.expectedDays} 天；每日峰值 ÷ ${quota.coverage.normalizationDays}。本日未完结，非账单。`,`Samples cover ${quota.coverage.observedDays}/${quota.coverage.expectedDays} days; daily peaks / ${quota.coverage.normalizationDays}. Current day is provisional, not an invoice.`))}</small>` : ""}
    </div>`;
  }
  function render() {
    const opened = new Set([...element.querySelectorAll("details[open]")].map(node=>node.dataset.usageGroup));
    element.innerHTML = `<section class="provider-usage" aria-label="${escape(text("服务商用量","Provider usage"))}">
      <div class="usage-heading"><h3>${escape(text("服务商用量","Provider usage"))}</h3><button type="button" class="text-button" data-usage-refresh ${busy || !actor ? "disabled" : ""}>${escape(busy ? text("读取中","Loading") : text("刷新","Refresh"))}</button></div>
      <p class="usage-note">${escape(text("账户额度与本项目用量分开统计。剩余根据已确认套餐和账户统计估算，不是账单余额。","Account allowances and project usage are separate. Remaining usage is estimated from established plans and account analytics, not an invoice balance."))}</p>
      ${error ? `<p class="error" role="alert">${escape(error)} ${escape(text("保留上次结果，不按零计算。","Previous results retained, never treated as zero."))}</p>` : ""}
      ${!data ? `<p role="status">${escape(busy ? text("正在读取服务商统计…","Loading provider metrics...") : text("打开面板后读取。","Loaded when this panel opens."))}</p>` : `
      <p class="usage-note">${escape(text("查询时间：","Checked: "))}${escape(date(data.checkedAt))}<br>${escape(text("下次可更新：","Next refresh: "))}${escape(date(data.nextRefreshAt))}</p>
      <div class="usage-plans">${(data.account?.plans ?? []).map(plan=>`<p><b>${escape(plan.product === "workers" ? "Workers / D1 / DO" : "R2")}</b> · ${escape(plan.name ?? text("套餐未知","Unknown plan"))} · ${escape(status(plan.state))}${plan.basis === "default_free" ? `<small>${escape(text("完整订阅查询未发现 Workers 付费套餐，适用默认 Free。","Complete subscription query has no Workers paid plan; default Free applies."))}</small>` : ""}${plan.periodStart !== null && plan.periodEnd !== null ? `<small>${escape(text("账期：","Billing period: "))}${escape(date(plan.periodStart))} → ${escape(date(plan.periodEnd))}</small>` : ""}${plan.reason ? `<small>${escape(reason(plan.reason))}</small>` : ""}</p>`).join("")}</div>
      ${!Array.isArray(data.account?.quotas) ? `<p class="usage-note">${escape(text("账户额度暂不可用；项目数据不能换算为剩余额度。","Account allowance is unavailable; project data cannot establish remaining usage."))}</p>` : ""}
      ${Object.entries(groups).map(([group,label])=>`<details class="usage-group" data-usage-group="${group}" ${opened.has(group) || (!element.querySelector("details") && group === "workers") ? "open" : ""}>
        <summary>${label}</summary>${data.account?.quotas?.some(quota=>quota.group === group && quotaLabels[quota.key]) ? `<h4 class="usage-subheading">${escape(text("账户额度","Account allowance"))}</h4>${data.account.quotas.filter(quota=>quota.group === group && quotaLabels[quota.key]).map(quotaRow).join("")}` : ""}
        ${data.metrics.some(metric=>metric.group === group && labels[metric.key]) ? `<h4 class="usage-subheading">${escape(text("本项目用量","Project usage"))}</h4>` : ""}
        ${data.metrics.filter(metric=>metric.group === group && labels[metric.key]).map(metric=>`<div class="usage-metric" data-usage-key="${escape(metric.key)}" data-state="${escape(error ? "stale" : metric.state)}">
          <div><span>${escape(text(...labels[metric.key]))}</span><strong>${escape(amount(metric.used,metric.unit))}</strong></div>
          <small>${escape(status(error ? "stale" : metric.state))}${metric.reason && metric.reason !== metric.state ? ` · ${escape(status(metric.reason))}` : ""} · ${escape(text("项目统计，不用于扣减账户额度","Project usage, not deducted from account allowance"))}</small>
          <small>${escape(text("范围：","Scope: "))}${escape(metric.scope)}</small>
          <small>${escape(text("统计窗口：","Window: "))}${escape(date(metric.periodStart))} → ${escape(date(metric.periodEnd))}</small>
          <small>${escape(text("最近成功查询：","Last successful query: "))}${escape(date(metric.lastSuccessAt))}${metric.sampledAt !== null ? `<br>${escape(text("采样时间：","Sampled: "))}${escape(date(metric.sampledAt))}` : ""}</small>
          ${metric.periodRolloverAt ? `<small>${escape(text("统计窗口切换：","Window rolls over: "))}${escape(date(metric.periodRolloverAt))}</small>` : ""}
        </div>`).join("")}${group === "r2" ? `<p class="usage-note">${escape(text("只有 Standard 适用免费包含量；Infrequent Access 没有免费额度。","Included free usage applies only to Standard; Infrequent Access has no free allowance."))}</p>` : ""}</details>`).join("")}
      <p class="usage-note">${escape(text("数据可能延迟或抽样；排除最近 5 分钟。免费日额度在 UTC 00:00 重置；按月包含量以查询到的账期为准，超出后可能继续计费。R2 GB·月按日峰值估算，不能用当前字节数直接扣减。项目 R2 操作仍按自然月、存储为最近采样。Pages CPU 为单次调用分位数。DO 请求统计包含实际 WebSocket 消息，付费账单另按 20:1 折算。","Analytics can be delayed or sampled; the last five minutes are excluded. Daily free limits reset at 00:00 UTC; monthly included usage follows the queried billing period and overages may be billed. R2 GB-month uses daily peak estimates, not current bytes. Project R2 operations still use calendar months and storage is the latest sample. Pages CPU is per-invocation. DO analytics count actual WebSocket messages; paid billing applies a 20:1 ratio."))}</p>
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
      if (value.metrics.some(metric=>!metric || typeof metric.key !== "string" || typeof metric.group !== "string" || typeof metric.unit !== "string")) {
        throw new Error(text("用量响应无效。","Invalid usage response."));
      }
      if (value.account !== undefined && (!Array.isArray(value.account?.plans) || !Array.isArray(value.account?.quotas) ||
          value.account.plans.some(plan=>!plan || typeof plan.product !== "string" || plan.name !== null && typeof plan.name !== "string") ||
          value.account.quotas.some(quota=>!quota || typeof quota.key !== "string" || typeof quota.group !== "string" || typeof quota.unit !== "string" ||
            [quota.used,quota.allowance,quota.remaining,quota.overage].some(amount=>amount !== null && (!Number.isFinite(amount) || amount < 0))))) {
        throw new Error(text("额度响应无效。","Invalid allowance response."));
      }
      data = value;
      onRecovered();
    } catch (e) { if (current === generation) { error = e.message; onError(e); } }
    finally { if (current === generation) { busy = false; render(); } }
  }
  element.addEventListener("click",event=>{ if (event.target.closest("[data-usage-refresh]")) void load(); });
  return {load,render,setActor(value) {
    if (value === actor) return;
    actor = value; generation++; data = null; error = ""; busy = false; render();
  }};
};
