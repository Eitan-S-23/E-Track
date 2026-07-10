(() => {
  'use strict';

  const PAGE_URL = 'https://eitan-s-23.github.io/Trace/';
  const APP_SCHEME_URL = 'trace://speedometer';
  const APP_PACKAGE_NAME = 'com.wen.gaia.gaia';
  const ANDROID_APK_URL =
    'https://github.com/Eitan-S-23/Trace/releases/latest/download/ble-monitor-android.apk';
  const WINDOWS_DOWNLOAD_URL =
    'https://github.com/Eitan-S-23/Trace/releases/latest/download/ble-monitor-windows.zip';

  const userAgent = navigator.userAgent || '';
  const params = new URLSearchParams(window.location.search);
  const isWeChat = /MicroMessenger/i.test(userAgent);
  const isInAppBrowser =
    isWeChat ||
    /QQ\/|Weibo|AlipayClient|DingTalk|Lark|Feishu|Bytedance|Toutiao|Aweme|Instagram|FBAN|FBAV|Line\//i.test(
      userAgent,
    );
  const isAndroid = /Android/i.test(userAgent);
  const isIos =
    /iPhone|iPad|iPod/i.test(userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

  const openButton = document.getElementById('openAppButton');
  const copyButton = document.getElementById('copyLinkButton');
  const status = document.getElementById('openStatus');
  const wechatGuide = document.getElementById('wechatGuide');

  function fallbackPageUrl() {
    const url = new URL(PAGE_URL);
    url.searchParams.set('fallback', '1');
    return url.toString();
  }

  function androidIntentUrl() {
    return `intent://speedometer#Intent;scheme=trace;package=${APP_PACKAGE_NAME};S.browser_fallback_url=${encodeURIComponent(
      fallbackPageUrl(),
    )};end`;
  }

  function setMode(mode) {
    document.body.dataset.mode = mode;
    wechatGuide.hidden = mode !== 'in-app';
  }

  function setStatus(message, tone = 'normal') {
    status.textContent = message;
    status.classList.toggle('is-warning', tone === 'warning');
  }

  function wireDownloads() {
    for (const id of ['downloadAndroid', 'downloadAndroidBottom']) {
      const link = document.getElementById(id);
      if (link) link.href = ANDROID_APK_URL;
    }

    const windowsLink = document.getElementById('downloadWindows');
    if (windowsLink) windowsLink.href = WINDOWS_DOWNLOAD_URL;
  }

  function bindOpenTracking(startedAt) {
    let appLikelyOpened = false;

    const cleanup = () => {
      document.removeEventListener('visibilitychange', onVisibilityChange);
      window.removeEventListener('pagehide', onPageHide);
    };

    const onVisibilityChange = () => {
      if (document.hidden) {
        appLikelyOpened = true;
        cleanup();
      }
    };

    const onPageHide = () => {
      appLikelyOpened = true;
      cleanup();
    };

    document.addEventListener('visibilitychange', onVisibilityChange);
    window.addEventListener('pagehide', onPageHide);

    window.setTimeout(() => {
      cleanup();
      if (!appLikelyOpened && Date.now() - startedAt < 3200) {
        setMode('browser');
        setStatus('如果没有跳转，可能尚未安装 App，或浏览器拦截了自动唤起。', 'warning');
      }
    }, 2200);
  }

  function navigateToApp(targetUrl) {
    if (isIos) {
      const iframe = document.createElement('iframe');
      iframe.hidden = true;
      iframe.src = APP_SCHEME_URL;
      document.body.appendChild(iframe);
      window.setTimeout(() => iframe.remove(), 1200);
    }

    window.location.href = targetUrl;
  }

  function openApp(source) {
    if (isInAppBrowser) {
      setMode('in-app');
      setStatus('请先在右上角菜单中选择“在浏览器打开”。', 'warning');
      return;
    }

    setMode('browser');
    setStatus(source === 'auto' ? '正在打开骑行软件...' : '正在请求系统打开骑行软件...');
    bindOpenTracking(Date.now());

    const targetUrl = isAndroid ? androidIntentUrl() : APP_SCHEME_URL;
    navigateToApp(targetUrl);
  }

  async function copyPageLink() {
    try {
      await navigator.clipboard.writeText(PAGE_URL);
      setStatus('页面链接已复制，可以粘贴到浏览器或聊天窗口。');
    } catch (_) {
      const input = document.createElement('textarea');
      input.value = PAGE_URL;
      input.setAttribute('readonly', '');
      input.style.position = 'fixed';
      input.style.opacity = '0';
      document.body.appendChild(input);
      input.select();
      document.execCommand('copy');
      input.remove();
      setStatus('页面链接已复制，可以粘贴到浏览器或聊天窗口。');
    }
  }

  function boot() {
    wireDownloads();

    openButton.addEventListener('click', () => openApp('manual'));
    copyButton.addEventListener('click', copyPageLink);

    if (isInAppBrowser) {
      setMode('in-app');
      setStatus('请先在右上角菜单中选择“在浏览器打开”。', 'warning');
      return;
    }

    if (params.get('fallback') === '1') {
      setMode('browser');
      setStatus('没有检测到已安装的骑行软件，可以先下载 Android APK。', 'warning');
      return;
    }

    if (!isAndroid && !isIos) {
      setMode('browser');
      return;
    }

    openApp('auto');
  }

  boot();
})();
