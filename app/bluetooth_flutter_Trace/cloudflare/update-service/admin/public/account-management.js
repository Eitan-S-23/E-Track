(function () {
  'use strict';
  window.TraceAccounts = function ({ element, api, mutate, session, text, escape: esc, confirm }) {
    let epoch = 0, ticket = 0, actor = '', busy = false, notice = '', page = 1, query = '';
    let data = { users: [], total: 0 }, settings = null, draft = null, detail = null;
    const owner = () => session()?.role === 'owner';
    const dirty = () => draft && settings && JSON.stringify(draft) !== JSON.stringify(settings);
    const stamp = n => n ? new Date(n).toLocaleString() : '-';
    const label = (cn, en) => esc(text(cn, en));
    function render() {
      const disabled = busy || !owner() ? 'disabled' : '';
      element.innerHTML = `<div class="panel-head"><div><h2>${label('账号管理', 'Accounts')}</h2>
        <p>${label('账号、登录统计与绑定码表。统计按北京时间划分，非在线人数。', 'Accounts, login statistics and bound devices. Shanghai calendar day; not concurrent online users.')}</p></div>
        <button id="accountReload" class="secondary-button" ${busy ? 'disabled' : ''}>${label('刷新', 'Refresh')}</button></div>
        <p role="status">${esc(notice)}</p>
        <div class="operations-buttons"><span>${label('有效账号', 'Accounts')}: ${Number(data.stats?.registered?.total ?? 0)}</span>
          <span>${label('今日登录用户', 'Users signed in today')}: ${Number(data.stats?.today?.users ?? 0)}</span>
          <span>${label('今日登录次数', 'Sign-ins today')}: ${Number(data.stats?.today?.logins ?? 0)}</span></div>
        ${draft ? `<details><summary>${label('注册与检查额度设置', 'Registration and check limits')}</summary>
          <form id="accountSettings"><div class="operations-buttons">
            ${[['registration_enabled','开放注册','Registration'],['password_registration_enabled','允许密码注册','Password registration'],
              ['email_verification_enabled','注册验证邮箱','Verify registration email']].map(([key,cn,en]) =>
              `<label><input type="checkbox" name="${key}" ${draft[key] ? 'checked' : ''} ${disabled}> ${label(cn,en)}</label>`).join('')}
            ${[['automatic_daily_limit','自动每日上限','Automatic daily limit'],['manual_daily_limit','手动每日上限','Manual daily limit']].map(([key,cn,en]) =>
              `<label>${label(cn,en)} <input type="number" name="${key}" min="0" max="1000" value="${Number(draft[key])}" ${disabled}></label>`).join('')}
            <button class="save-button" ${disabled}>${label('保存设置', 'Save settings')}</button></div>
          <p>${label('邮箱验证需先配置邮件发送；关闭注册不会停用已有账号。', 'Configure email delivery before enabling verification. Closing registration does not disable existing accounts.')}</p></form></details>` : ''}
        <div class="table-scroll" style="max-width:100%;overflow-x:auto"><table><thead><tr><th>${label('用户', 'User')}</th><th>${label('状态', 'State')}</th>
          <th>${label('设备数', 'Devices')}</th><th>${label('最近登录', 'Last sign-in')}</th><th></th></tr></thead><tbody>
          ${data.users.map(u => `<tr><td>${esc(u.username)}<br><small>${esc(u.email || '')}</small></td><td>${esc(u.state)}</td>
            <td>${Number(u.deviceCount)}</td><td>${esc(stamp(u.lastLoginAt))}</td><td><button class="secondary-button" data-user="${esc(u.id)}">${label('详情', 'Details')}</button></td></tr>`).join('') ||
            `<tr><td colspan="5">${label('没有匹配账号', 'No matching accounts')}</td></tr>`}</tbody></table></div>
        <div class="operations-buttons"><button id="accountPrev" ${busy || page <= 1 ? 'disabled' : ''}>${label('上一页', 'Previous')}</button>
          <span>${page} / ${Math.max(1, Math.ceil(data.total / 30))}</span><button id="accountNext" ${busy || page * 30 >= data.total ? 'disabled' : ''}>${label('下一页', 'Next')}</button></div>
        ${detail ? `<section class="feedback-detail"><div class="panel-head"><h3>${esc(detail.account.username)}</h3>
          <button id="accountClose">${label('关闭详情', 'Close details')}</button></div>
          <p>${label('自动剩余', 'Automatic remaining')}: ${Number(detail.quota.automatic.remaining)} / ${Number(detail.quota.automatic.limit)} ·
            ${label('手动剩余', 'Manual remaining')}: ${Number(detail.quota.manual.remaining)} / ${Number(detail.quota.manual.limit)}</p>
          <div class="operations-buttons"><button data-action="state" ${disabled}>${detail.account.state === 'active' ? label('停用账号','Disable account') : label('启用账号','Enable account')}</button>
            <button data-action="revoke-sessions" ${disabled}>${label('撤销全部登录', 'Revoke all sessions')}</button></div>
          <h4>${label('绑定码表', 'Bound devices')}</h4>
          ${detail.devices.map(d => `<div class="feedback-item"><strong>${esc(d.name)}</strong><code style="overflow-wrap:anywhere">${esc(d.uid)}</code>
            <span>${esc(d.model)} · HW ${Number(d.hardware_revision)} · FW ${Number(d.firmware_version)}</span>
            <small>${label('绑定时间', 'Bound')}: ${esc(stamp(d.bound_at))}</small><button data-unbind="${esc(d.uid)}" ${disabled}>${label('解绑', 'Unbind')}</button></div>`).join('') || `<p>${label('无绑定设备', 'No bound devices')}</p>`}
          <h4>${label('最近 50 次登录（保留 90 天）', 'Last 50 sign-ins (90-day retention)')}</h4>
          <ol>${detail.logins.map(l => `<li>${esc(stamp(l.occurred_at))} ${esc(l.app_version || '')}</li>`).join('')}</ol></section>` : ''}`;
    }
    async function mayDiscard() {
      return !dirty() || await confirm({ title: text('放弃未保存设置？','Discard unsaved settings?'),
        message: text('已保存设置不受影响。','Saved settings will not change.'), confirmLabel: text('放弃','Discard'), tone: 'warning' });
    }
    async function run(action) {
      if (busy || !actor) return;
      const current = epoch, request = ++ticket;
      busy = true; notice = ''; render();
      try { await action(() => current === epoch && request === ticket); }
      catch (error) { if (current === epoch && request === ticket) notice = error.message; }
      finally { if (current === epoch && request === ticket) { busy = false; render(); } }
    }
    async function load() {
      if (!await mayDiscard()) return;
      await run(async current => {
        const result = await api('/api/admin/accounts?page=' + page + '&q=' + encodeURIComponent(query));
        const config = await api('/api/admin/accounts/settings');
        if (current()) { data = result; settings = config; draft = { ...config }; }
      });
    }
    async function open(id) {
      await run(async current => {
        const result = await api('/api/admin/accounts/' + encodeURIComponent(id));
        if (current()) detail = result;
      });
    }
    element.addEventListener('input', event => {
      const name = event.target.name;
      if (draft && ['registration_enabled','password_registration_enabled','email_verification_enabled','automatic_daily_limit','manual_daily_limit'].includes(name)) {
        draft[name] = event.target.type === 'checkbox' ? Number(event.target.checked) : Number(event.target.value);
      }
    });
    element.addEventListener('submit', event => {
      if (event.target.id !== 'accountSettings') return;
      event.preventDefault(); if (!owner() || busy || !draft) return;
      const payload = { ...draft };
      void run(async current => {
        const result = await mutate('/api/admin/accounts/settings', payload);
        if (current()) { settings = result.settings; draft = { ...settings }; notice = text('已保存','Saved'); }
      });
    });
    element.addEventListener('click', async event => {
      const button = event.target.closest('button');
      if (!button || busy) return;
      if (button.id === 'accountReload') return void load();
      if (button.id === 'accountPrev' || button.id === 'accountNext') {
        if (!await mayDiscard()) return;
        page += button.id === 'accountNext' ? 1 : -1; draft = settings ? { ...settings } : null;
        return void load();
      }
      if (button.id === 'accountClose') { detail = null; render(); return; }
      if (button.dataset.user) return void open(button.dataset.user);
      const action = button.dataset.unbind ? 'unbind' : button.dataset.action;
      if (!action || !detail || !owner()) return;
      const id = detail.account.id, currentEpoch = epoch;
      const payload = action === 'state' ? { state: detail.account.state === 'active' ? 'disabled' : 'active' }
        : action === 'unbind' ? { uid: button.dataset.unbind } : {};
      if (!await confirm({ title: text('确认账号操作？','Confirm account action?'),
        message: detail.account.username + ' · ' + button.textContent, confirmLabel: text('确认','Confirm'), tone: 'warning' }) || currentEpoch !== epoch) return;
      await run(async current => {
        await mutate('/api/admin/accounts/' + id + '/' + action, payload);
        const result = await api('/api/admin/accounts/' + id);
        if (current()) { detail = result; notice = text('操作完成','Action completed'); }
      });
    });
    return { render, load, dirty,
      search(value) { query = value.slice(0,64); page = 1; void load(); },
      setSession(value) {
        const identity = value?.actor ? value.actor + ':' + value.role : '';
        if (identity !== actor) {
          actor = identity; epoch++; ticket++; busy = false; page = 1; query = ''; data = { users: [], total: 0 };
          settings = draft = detail = null; notice = ''; render();
        }
        if (actor && !element.hidden) void load();
      }
    };
  };
})();
