# P3-3 受验 APK 构建与身份实测（P2）+ Quick Tunnel 部署信息（D1/D2）—— 2026-09-13

> 执行依据：用户集中执行授权 `P3-3-EXEC-AUTH-20260913` 第二/四节 +
> 独立准入复核 ADMISSION_PASS。注入时序按第二节：先隧道取址 → 宿主端到端
> 检查（D2）通过 → 注入唯一一次受验 APK 构建 → 地址绑定进合同。

## 1. D1 隧道与受控服务（运行时状态）

| 项 | 值 |
| --- | --- |
| Quick Tunnel 公网地址 | `https://feed-recipients-copper-ellis.trycloudflare.com` |
| cloudflared 进程 | PID **18940**（后台任务 btmb2dqv6，`--no-autoupdate`，QUIC 已注册边缘 sjc08） |
| 隧道日志/收敛 | `.cache/p3-3-cloudflared/tunnel.log`、pidfile `tunnel.pid`；HOME/USERPROFILE 已覆盖收敛至 `.cache/p3-3-cloudflared/home/`（启动前/后均确认用户目录无 `~/.cloudflared` 写入） |
| cloudflared 获取登记 | 版本 2026.9.1（built 2026-09-10），54,976,432B，SHA-256 `2837888cc0f5d58f15b6dc478376de90b4d3ba5241c7947455d1e0a0df429712`，`.cache/p3-3-cloudflared/acquisition.txt` |
| 受控 v2 服务 | PID **15892**，监听 `127.0.0.1:8443`（HTTP，TLS 由 CF 边缘终止），`--public-base-url` = 隧道地址，`--active-release toy-30201`；启动时双 fixture 字节级核验通过（toy `fc4ae5a9…`/284092、real `0a2eb26a…`/284112）；日志 `.cache/p3-3-v2-service/service.log`（D3 持续采集，每请求一行含 requestId） |
| 8h 窗口 | **2026-09-13T12:26Z 起算（至约 20:26Z）**，须覆盖至 D5 清理完成；地址改变或隧道退出即暂停相关阶段，不换地址、不追加 APK 构建 |
| 暴露面 | 仅 latest/download 端点与两份绑定 ETU；无 CF 账号、不读旧 token、无 adb reverse |

## 2. D2 宿主端到端检查（14/14 ALL PASS）

- 脚本：`.cache/p3-3-v2-service/d2_hostcheck.py`（参数=隧道 URL；仅默认信任库，不加载任何测试 CA）。
- 证据：`.cache/p3-3-v2-service/quicktunnel-hostcheck.log`。
- 四项：
  1. latest 真机十参数（appId=trace, deviceModel=e-track-at32f435, channel=stable,
     currentVersionCode=30200, currentImageSha=64×0, hardwareRevision=1,
     layoutId=1, bootVersion=1, protocolVersion=1, appVersionCode=86）→ 200 /
     schemaVersion=2 / versionCode=30201 / `asset.downloadUrl` 同隧道 https
     前缀 / asset 四元组一致 / 动态 token 下载端点；
  2. 整包下载 200 / 284,092B / SHA-256 `fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2` 全等；
  3. 证书链默认信任库校验通过（subject CN=trycloudflare.com ← issuer
     Google Trust Services WE1，零测试 CA）；
  4. 负例 `/`、`/api/ci/jobs`、`/api/admin/`、`/api/public/firmware/latestx`
     全 404，不放大暴露。

## 3. P2 受验 APK 构建（唯一一笔 build-only 额度，已消耗）

- 派发（D2 全过后）：`gh workflow run build.yml --ref dev/flutter/apk/p3-3-admission
  -f publish_release=false -f replace_existing_release=false
  -f firmware_latest_url=https://feed-recipients-copper-ellis.trycloudflare.com/api/public/firmware/latest
  -f release_application_id_suffix=.p33acceptance`
- **Run 34757419111**（Build APK and EXE Release，2026-09-13T12:33:33Z 派发）：
  Build Android APK / Build Windows EXE 均 **success**；Deploy GitHub Pages 与
  Create GitHub Release 均 **skipped**（publish_release=false /
  replace_existing_release=false 生效，Pages/Release 未执行）。

## 4. 受验 APK 身份三元组（全部本机实测）

| 项 | 实测值 | 方法 |
| --- | --- | --- |
| 文件 | `.cache/p3-3-apk/ble-monitor-android.apk`，46,682,632B | `gh run download 34757419111 -n android-apk` |
| SHA-256 | `c85ee96e9e41c3ac4e174bbb506719a9b9fc00ca3d598bbaaeddae83b1963427` | sha256sum |
| 包名 | **`com.wen.gaia.gaia.p33acceptance`**（versionCode=86 / versionName=1.0.60） | aapt dump badging（注入成功，非 ENV_BLOCKED） |
| 签名 | v2 scheme `Verifies`（v1/v3/v4 false，1 signer）；Signer DN `C=US, O=Android, CN=Android Debug`；**证书 SHA-256 `c1c89084cfbeb4268bf71225ad1124dcaf466088eb6fb6b09eb4d069e21942ae`**（SHA-1 `23feeb3f…db16b5`，MD5 `f827dd91…49bb5e`） | apksigner verify --print-certs（官方 build-tools r35，见 §6） |
| endpoint 注入 | APK 内 2 处 `https://feed-recipients-copper-ellis.trycloudflare.com/api/public/firmware/latest`（dex 字符串静态确认） | grep -a 二进制扫描 |

注：证书指纹为本次产物实测（不同 CI run 的 debug 签名不能假定相同，O1 双侧
比对以本值为受验侧基准）。既有安装 `com.wen.gaia.gaia` 侧指纹在 O1 时经
dumpsys→pull→apksigner 实测。

## 5. 工具链（本机实测所用，均为只读使用或 worktree 内收敛）

- adb：`D:/install/leidian/LDPlayer4/adb.exe`（1.0.41 / 34.0.4，支持 Android 13 真机）。
- aapt：`D:/install/leidian/LDPlayer4/aapt.exe`。
- apksigner：官方 build-tools r35 组件，下载 zip（59,878,107B，SHA-256
  `5753c679a1b90bcf6fbc9945a2ce39dfb9e74f1df0831a1e1866ae5b594326f0`，
  `dl.google.com/android/repository/build-tools_r35_windows.zip`）解压至
  worktree `.cache/p3-3-apk/tools/android-15/`（apksigner.bat + lib），
  未全局安装；JAVA_HOME 用本机既有 `D:/install/jdk17`。
- keytool -jarfile 不可用原因：本 APK 仅 v2 签名（v1 JAR 签名 false），
  keytool/jarsigner 只认 v1，故取官方 apksigner。

## 6. 前置链状态（O1 开始前）

- P1 受控服务+隧道+D2 检查：**完成**（本文 §1/§2）。
- P2 受验 APK 身份：**完成**（本文 §3/§4）。
- P0 BCB 恢复：**完成**（`P3-3-recovery-execution-2026-09-13.md`，§5 完成判据四条全满足）。
- P3 合同冻结+NOT_RUN 前检：待非实现会话办理（本文件与恢复执行留证提供
  冻结回填所需的全部实测值：隧道地址/PID/窗口/hostcheck 日志路径、APK
  三元组与证书指纹、恢复终态）。
