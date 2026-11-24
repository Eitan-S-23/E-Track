(function () {
  'use strict';
  window.TraceAccounts = function ({ element, detailElement, api, mutate, session, text, escape: esc, confirm, onError, onRecovered, onSuccess, onDetailVisibility, onSearchChange }) {
    let epoch = 0, ticket = 0, actor = '', busy = false, notice = '', pendingSearch = false;
    const lists = Object.fromEntries(['accounts','terminals','devices'].map(key =>
      [key, { data: { users: [], rows: [], total: 0 }, page: 1, query: '' }]));
    const list = () => lists[view] ?? lists.accounts;
    let settings = null, draft = null, detail = null, detailVisible = false, returnId = null;
    let view = 'accounts', detailTab = 'devices';
    const owner = () => session()?.role === 'owner';
    const dirty = () => draft && settings && JSON.stringify(draft) !== JSON.stringify(settings);
    const stamp = n => n ? new Date(n).toLocaleString() : '-';
    const label = (cn, en) => esc(text(cn, en));
    const firmware = n => Number.isInteger(n) ? `${Math.floor(n / 10000)}.${Math.floor(n / 100) % 100}.${n % 100}` : '-';
    const sessionState = s => s === 'valid' ? label('登录有效（非在线）','Valid sign-in (not online)')
      : s === 'revoked' ? label('已撤销','Revoked') : label('已过期','Expired');
    const count = value => Number.isInteger(value) && value >= 0 ? String(value) : '-';
    function quotaDetails() {
      const line = (component, title, quota) => `<p data-check-component="${component}"><strong>${title}</strong> ·
        ${label('自动剩余','Automatic remaining')}: ${count(quota?.automatic?.remaining)} / ${count(quota?.automatic?.limit)} ·
        ${label('手动剩余','Manual remaining')}: ${count(quota?.manual?.remaining)} / ${count(quota?.manual?.limit)}</p>`;
      const components = detail.quota?.components;
      return components?.app && components?.firmware
        ? line('app', label('APP','App'), components.app) + line('firmware', label('主控固件','MCU firmware'), components.firmware)
        : line('legacy', label('检查更新（旧版共用）','Update checks (legacy shared)'), detail.quota);
    }
    function detailBody(disabled) {
      if (detailTab === 'terminals') return (detail.terminals ?? []).map(t => `<div class="feedback-item"><strong>${esc(t.model || text('型号未知','Unknown model'))}</strong>
          <code>${esc(t.installationId)}</code><span>${esc(t.platform)} · ${esc(t.osVersion || '-')} · APP ${esc(t.versionName || '-')} (${Number(t.versionCode)})</span>
          <small>${label('最近活动','Last activity')}: ${esc(stamp(t.lastSeenAt))}</small>
          ${(detail.observations ?? []).filter(o => o.installationId === t.installationId).map(o => `<button class="secondary-button" data-detail-tab="devices">${label('曾连接码表','Observed device')}: ${esc(o.uid)} · ${esc(firmware(o.firmwareVersion))} · ${esc(stamp(o.observedAt))}</button>`).join('')}</div>`).join('');
      if (detailTab === 'sessions') return (detail.sessions ?? []).map(s => `<div class="feedback-item"><strong>${esc(s.model || text('型号未知','Unknown model'))}</strong>
          <span>${esc(s.versionName || '-')} · ${sessionState(s.state)}</span><small>${label('登录时间','Signed in')}: ${esc(stamp(s.createdAt))}</small>
          <small>${label('最近活动','Last activity')}: ${esc(stamp(s.lastSeenAt))}</small>
          <button class="secondary-button" data-revoke-session="${esc(s.id)}" ${disabled || s.state !== 'valid' ? 'disabled' : ''}>${label('退出该终端','Sign out this session')}</button></div>`).join('');
      if (detailTab === 'logins') return `<ol>${(detail.logins ?? []).map(l => `<li>${esc(stamp(l.occurred_at))} ${esc(l.app_version || text('版本未知','Unknown version'))}</li>`).join('')}</ol>`;
      if (detailTab === 'audit') return `<ol>${(detail.audit ?? []).map(a => `<li>${esc(stamp(a.occurredAt))} · ${esc(a.action)} ${esc(a.uid || '')}</li>`).join('')}</ol>`;
      return detail.devices.map(d => `<div class="feedback-item"><strong>${esc(d.name)}</strong><code style="overflow-wrap:anywhere">${esc(d.uid)}</code>
        <span>${esc(d.model)} · HW ${Number(d.hardware_revision)} · FW ${esc(firmware(d.firmware_version))}</span>
        <small>${label('绑定时间','Bound')}: ${esc(stamp(d.bound_at))}</small><small>${label('最近上报（非在线）','Last report (not online)')}: ${esc(stamp(d.last_seen_at))}</small>
        ${(detail.observations ?? []).filter(o => o.uid === d.uid).map(o => `<button class="secondary-button" data-detail-tab="terminals">${label('关联终端','Related terminal')}: ${esc(o.installationId)} · ${esc(stamp(o.observedAt))}</button>`).join('')}
        <button class="secondary-button" data-unbind="${esc(d.uid)}" ${disabled}>${label('解绑','Unbind')}</button></div>`).join('') || `<p>${label('无绑定设备','No bound devices')}</p>`;
    }
    function render() {
      const { data, page } = list();
      const disabled = busy || !owner() ? 'disabled' : '';
      const independent = Number.isInteger(draft?.firmware_automatic_daily_limit) && Number.isInteger(draft?.firmware_manual_daily_limit);
      const limitFields = [
        ['automatic_daily_limit',independent ? 'APP 自动每日上限' : '自动每日上限',independent ? 'App automatic daily limit' : 'Automatic daily limit'],
        ['manual_daily_limit',independent ? 'APP 手动每日上限' : '手动每日上限',independent ? 'App manual daily limit' : 'Manual daily limit'],
        ...(independent ? [['firmware_automatic_daily_limit','固件自动每日上限','Firmware automatic daily limit'],
          ['firmware_manual_daily_limit','固件手动每日上限','Firmware manual daily limit']] : []),
      ];
      element.innerHTML = `<div class="panel-head"><div><h2>${label('账号管理', 'Accounts')}</h2>
        </div>
        <button id="accountReload" class="secondary-button" ${busy ? 'disabled' : ''}>${label('刷新', 'Refresh')}</button></div>
        <p role="status">${busy ? label('正在读取或保存，请稍候','Loading or saving, please wait') : ''}</p>
        <div class="operations-buttons" role="group" aria-label="${label('账号关联视图','Account relation views')}">
          ${[['accounts','账号','Accounts'],['terminals','APP 终端','App terminals'],['devices','绑定码表','Bound devices'],['settings','账号设置','Account settings']].map(([key,cn,en]) =>
            `<button class="secondary-button" data-account-view="${key}" aria-pressed="${view === key}" ${busy ? 'disabled' : ''}>${label(cn,en)}</button>`).join('')}</div>
        ${view === 'accounts' ? `<div class="operations-buttons account-stats"><span>${label('有效账号', 'Accounts')}: ${data.stats ? Number(data.stats.registered?.total ?? 0) : '-'}</span>
          <span>${label('今日登录用户', 'Users signed in today')}: ${data.stats ? Number(data.stats.today?.users ?? 0) : '-'}</span>
          <span>${label('今日登录次数', 'Sign-ins today')}: ${data.stats ? Number(data.stats.today?.logins ?? 0) : '-'}</span></div>` : ''}
        ${view === 'settings' && draft ? `<form id="accountSettings">
          <fieldset class="account-settings-group"><legend>${label('登录与注册','Sign-in and registration')}</legend>
            ${[['registration_enabled','开放注册','Registration'],['password_registration_enabled','允许密码注册','Password registration'],
              ['email_verification_enabled','注册验证邮箱','Verify registration email']].map(([key,cn,en]) =>
              `<label class="account-setting">${label(cn,en)}<input type="checkbox" name="${key}" ${draft[key] ? 'checked' : ''} ${disabled}></label>`).join('')}
          </fieldset><fieldset class="account-settings-group"><legend>${label('检查更新额度','Update check limits')}</legend>
            ${limitFields.map(([key,cn,en]) =>
              `<label class="account-setting">${label(cn,en)} <input type="number" name="${key}" min="0" max="1000" value="${Number(draft[key])}" ${disabled}></label>`).join('')}
          </fieldset><p class="firmware-hint">${draft.emailDeliveryAvailable === true
            ? label('邮件已配置', 'Email configured') : label('邮件未配置', 'Email not configured')}</p>
            <button class="save-button" ${disabled}>${label('保存设置', 'Save settings')}</button></form>` : ''}
        ${view === 'accounts' ? `<div class="table-scroll account-list"><table class="inventory-table"><thead><tr><th>${label('用户', 'User')}</th><th>${label('状态', 'State')}</th>
          <th>${label('终端 / 码表','Terminals / devices')}</th><th>${label('最近登录', 'Last sign-in')}</th><th></th></tr></thead><tbody>
          ${data.users.map(u => `<tr><td>${esc(u.username)}<br><small>${esc(u.email || '')}</small></td><td>${esc(u.state)}</td>
            <td><button class="secondary-button" data-user="${esc(u.id)}" data-open-detail-tab="terminals">${Number(u.terminalCount ?? 0)}</button> /
              <button class="secondary-button" data-user="${esc(u.id)}" data-open-detail-tab="devices">${Number(u.deviceCount ?? 0)}</button></td>
            <td>${esc(stamp(u.lastLoginAt))}</td><td><button class="secondary-button" data-user="${esc(u.id)}" aria-haspopup="dialog">${label('详情', 'Details')}</button></td></tr>`).join('') ||
            `<tr><td colspan="5">${label('没有匹配账号', 'No matching accounts')}</td></tr>`}</tbody></table></div>` : view === 'settings' ? '' :
          `<div class="table-scroll account-list"><table class="inventory-table"><thead><tr>
            <th>${label('账号','Account')}</th><th>${label('设备','Device')}</th><th>${label('版本','Version')}</th><th>${label('最近上报','Last report')}</th></tr></thead><tbody>
          ${(data.rows ?? []).map(r => `<tr><td><button class="secondary-button" data-user="${esc(r.accountId)}" data-open-detail-tab="${view}">${esc(r.username)}</button></td>
            <td>${esc(r.model || r.name || '-')}<br><code>${esc(r.uid || r.installationId)}</code></td>
            <td>${esc(r.uid ? firmware(r.firmwareVersion) : `${r.versionName || '-'} (${r.versionCode}) · ${r.osVersion || '-'}`)}</td>
            <td>${esc(stamp(r.lastSeenAt))}</td></tr>`).join('') || `<tr><td colspan="4">${label('没有匹配记录','No matching records')}</td></tr>`}</tbody></table></div>`}
        ${view !== 'settings' ? `<div class="operations-buttons"><button class="secondary-button" id="accountPrev" ${busy || page <= 1 ? 'disabled' : ''}>${label('上一页', 'Previous')}</button>
          <span>${page} / ${Math.max(1, Math.ceil(data.total / 30))}</span><button class="secondary-button" id="accountNext" ${busy || page * 30 >= data.total ? 'disabled' : ''}>${label('下一页', 'Next')}</button></div>` : ''}`;
      if (detailElement) detailElement.innerHTML = detail ? `<section class="feedback-detail"><div class="panel-head"><h3>${esc(detail.account.username)}</h3></div>
          ${quotaDetails()}
          <div class="operations-buttons"><button class="secondary-button" data-action="state" ${disabled}>${detail.account.state === 'active' ? label('停用账号','Disable account') : label('启用账号','Enable account')}</button>
            <button class="secondary-button" data-action="revoke-sessions" ${disabled}>${label('撤销全部登录', 'Revoke all sessions')}</button></div>
          <div class="operations-buttons" role="group" aria-label="${label('账号详情','Account details')}">
            ${[['devices','绑定码表','Devices'],['terminals','APP 终端','Terminals'],['sessions','登录会话','Sessions'],['logins','登录记录','Sign-ins'],['audit','操作记录','Actions']].map(([key,cn,en]) =>
              `<button class="secondary-button" data-detail-tab="${key}" aria-pressed="${detailTab === key}">${label(cn,en)}</button>`).join('')}</div>
          <div id="accountDetailBody" class="account-detail-list">${detailBody(disabled)}</div></section>` : '';
    }
    function syncDetail() {
      const visible = Boolean(detail);
      if (visible !== detailVisible) { detailVisible = visible; onDetailVisibility?.(visible); }
    }
    function closeDetail() { detail = null; render(); syncDetail(); }
    async function mayDiscard() {
      return !dirty() || await confirm({ title: text('放弃未保存设置？','Discard unsaved settings?'),
        message: text('已保存设置不受影响。','Saved settings will not change.'), confirmLabel: text('放弃','Discard'), tone: 'warning' });
    }
    async function run(action) {
      if (busy || !actor) return;
      const current = epoch, request = ++ticket;
      onRecovered?.('accounts');
      busy = true; notice = '';
      let failure;
      try { render(); await action(() => current === epoch && request === ticket); }
      catch (error) { if (current === epoch && request === ticket) { notice = error.message; failure = error; } }
      finally { if (current === epoch && request === ticket) {
        busy = false;
        try { render(); syncDetail(); } catch (error) { failure ??= error; }
      } }
      if (current !== epoch || request !== ticket) return;
      if (failure) onError?.(failure, 'accounts');
      else { onRecovered?.('accounts'); if (notice) onSuccess?.(notice); }
      if (pendingSearch) { pendingSearch = false; void load(); }
    }
    async function load() {
      if (!await mayDiscard()) return;
      const requestedView = view, requestedList = list(), page = requestedList.page, query = requestedList.query;
      await run(async current => {
        const result = requestedView === 'settings' ? null : await api('/api/admin/accounts' +
          (requestedView === 'accounts' ? '' : '/' + requestedView) + '?page=' + page + '&q=' + encodeURIComponent(query));
        if (result && !Array.isArray(result[requestedView === 'accounts' ? 'users' : 'rows'])) {
          throw Error(text('账号列表响应无效，请重新读取','Invalid account list response; reload the list'));
        }
        const config = requestedView === 'settings' ? await api('/api/admin/accounts/settings') : null;
        if (current() && view === requestedView) {
          if (result) requestedList.data = result;
          if (config) { settings = config; draft = { ...config }; }
        }
      });
    }
    async function open(id) {
      await run(async current => {
        const result = await api('/api/admin/accounts/' + encodeURIComponent(id));
        if (current()) { detail = result; returnId = id; }
      });
    }
    element.addEventListener('input', event => {
      const name = event.target.name;
      if (draft && ['registration_enabled','password_registration_enabled','email_verification_enabled',
        'automatic_daily_limit','manual_daily_limit','firmware_automatic_daily_limit','firmware_manual_daily_limit'].includes(name)) {
        draft[name] = event.target.type === 'checkbox' ? Number(event.target.checked) : Number(event.target.value);
      }
    });
    element.addEventListener('submit', event => {
      if (event.target.id !== 'accountSettings') return;
      event.preventDefault(); if (!owner() || busy || !draft) return;
      const payload = { ...draft };
      void run(async current => {
        const result = await mutate('/api/admin/accounts/settings', payload);
        if (current()) { settings = result.settings; draft = { ...settings }; notice = text('账号设置已保存','Account settings saved'); }
      });
    });
    async function clicked(event) {
      const button = event.target instanceof Element ? event.target.closest('button') : null;
      if (!button || busy) return;
      if (button.dataset.accountView) {
        if (!await mayDiscard()) return;
        if (!['accounts','terminals','devices','settings'].includes(button.dataset.accountView)) return;
        view = button.dataset.accountView; detail = null; syncDetail(); draft = settings ? { ...settings } : null;
        onSearchChange?.(view === 'settings' ? '' : list().query); return void load();
      }
      if (button.dataset.detailTab) { detailTab = button.dataset.detailTab; render();
        detailElement?.querySelector(`[data-detail-tab="${detailTab}"]`)?.focus({ preventScroll: true }); return; }
      if (button.id === 'accountReload') return void load();
      if (button.id === 'accountPrev' || button.id === 'accountNext') {
        if (!await mayDiscard()) return;
        list().page += button.id === 'accountNext' ? 1 : -1; draft = settings ? { ...settings } : null;
        return void load();
      }
      if (button.dataset.user) { detailTab = button.dataset.openDetailTab || 'devices'; return void open(button.dataset.user); }
      const action = button.dataset.unbind ? 'unbind' : button.dataset.revokeSession ? 'revoke-session' : button.dataset.action;
      if (!action || !detail || !owner()) return;
      const id = detail.account.id, currentEpoch = epoch;
      const payload = action === 'state' ? { state: detail.account.state === 'active' ? 'disabled' : 'active' }
        : action === 'unbind' ? { uid: button.dataset.unbind } : action === 'revoke-session' ? { sessionId: button.dataset.revokeSession } : {};
      if (!await confirm({ title: text('确认账号操作？','Confirm account action?'),
        message: detail.account.username + ' · ' + button.textContent, confirmLabel: text('确认','Confirm'), tone: 'warning' }) || currentEpoch !== epoch) return;
      await run(async current => {
        await mutate('/api/admin/accounts/' + id + '/' + action, payload);
        if (!current()) return;
        let result;
        try { result = await api('/api/admin/accounts/' + id); }
        catch (_) { throw Error(text('操作已完成，但详情刷新失败。请刷新查看，不要重复提交。', 'Action completed, but detail refresh failed. Refresh the page; do not repeat the action.')); }
        if (current()) { detail = result; notice = text('操作完成','Action completed'); }
      });
    }
    element.addEventListener('click', clicked);
    detailElement?.addEventListener('click', clicked);
    return { render, load, dirty, closeDetail,
      returnFocus() { return returnId ? element.querySelector(`[data-user="${CSS.escape(returnId)}"]`) : null; },
      async showRelations(kind, value = '') {
        if (busy || !['terminals','devices'].includes(kind) || !await mayDiscard()) return;
        view = kind; list().query = value.slice(0,64); list().page = 1; detail = null; syncDetail(); draft = settings ? { ...settings } : null;
        onSearchChange?.(list().query);
        await load();
      },
      search(value) {
        if (view === 'settings') return;
        list().query = value.slice(0,64); list().page = 1;
        // Search stays editable while a list loads; retain only its latest intent.
        if (busy) pendingSearch = true; else void load();
      },
      setSession(value) {
        const identity = value?.actor ? value.actor + ':' + value.role : '';
        if (identity !== actor) {
          actor = identity; epoch++; ticket++; busy = false; pendingSearch = false; view = 'accounts'; detailTab = 'devices';
          for (const item of Object.values(lists)) { item.data = { users: [], rows: [], total: 0 }; item.page = 1; item.query = ''; }
          settings = draft = detail = returnId = null; notice = ''; render(); syncDetail();
        }
        if (actor && !element.closest('[hidden]')) void load();
      }
    };
  };
})();
