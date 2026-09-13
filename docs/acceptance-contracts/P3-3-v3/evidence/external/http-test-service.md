# P3-3-v3 外部输入证据：EXT-HTTP-TEST-SERVICE（受控 v2 服务 + Quick Tunnel）

- 输入 ID: EXT-HTTP-TEST-SERVICE（category=environment）
- 核对会话: 独立验收会话（非实现会话，P3-3 冻结办理）
- 日期: 2026-09-13
- freeze_commit: `a178ecc1dca3929e1bca702fb11344f3c5bd2872`
- 部署执行依据: P3-3-EXEC-AUTH-20260913 第二节（Quick Tunnel 路线）

## 1. 冻结身份（服务实现）

`Tools/ota/p3-3-service/` 四件套（SERVICE_VERSION=2，runner 冻结依赖经
Validation profile required_paths 落地）：

- `service.py` SHA-256 `f71012de119811863d2274fd674a702c69a512f18ea73e3188be2233130ba009`
- `service_config.json` SHA-256 `2facafa60fb4c65944c55168d46a2fbf2b2de7ea05d46e47beffa850cc7ce39c`
- `selftest.py` SHA-256 `b96d4e2f05c84c3401c1dff14ee9c0f6e5dc7ee0a076e272180d2f4d4aa202b4`
- `tls_hostcheck.py` SHA-256 `f9202b6b47f50526e75710fd2b8048e87b24bb94ab07f82b88716a761821da6c`

## 2. D1 运行时部署实测（2026-09-13）

| 项 | 实测值 |
| --- | --- |
| Quick Tunnel 公网地址 | `https://feed-recipients-copper-ellis.trycloudflare.com` |
| cloudflared 进程 | PID 18940（`--no-autoupdate`，QUIC 注册边缘 sjc08） |
| 受控 v2 服务 | PID 15892，监听 `127.0.0.1:8443`（HTTP，TLS 由 CF 边缘终止） |
| 服务启动参数 | `--public-base-url` = 隧道地址，`--active-release toy-30201` |
| 启动双 fixture 字节级核验 | toy `fc4ae5a9…`/284,092B、real `0a2eb26a…`/284,112B 通过（失配拒绝） |
| 8h 窗口 | 2026-09-13T12:26Z 起算（至约 20:26Z），须覆盖至 D5 清理完成 |
| 暴露面 | 仅 latest/download 端点与两份绑定 ETU；无 CF 账号、不读旧 token、无 adb reverse |

## 3. D2 宿主端到端检查（14/14 ALL PASS）

- 脚本: `.cache/p3-3-v2-service/d2_hostcheck.py`（仅默认信任库，不加载任何测试 CA）
- 日志: `.cache/p3-3-v2-service/quicktunnel-hostcheck.log`
  （SHA-256 `6cea803724b6321fcded326757710e54edf8ae7dbd5293fc00bf639fceb04523`）
- 四项结果：
  1. latest 真机十参数 200 / schemaVersion=2 / versionCode=30201（toy）/
     `asset.downloadUrl` 同隧道 https 前缀 / asset 四元组一致 / 动态 token
     下载端点；
  2. 整包下载 200 / 284,092B / SHA-256
     `fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2` 全等；
  3. 证书链默认信任库校验通过（subject CN=trycloudflare.com，issuer
     Google Trust Services WE1，零测试 CA）；
  4. 负例 `/`、`/api/ci/jobs`、`/api/admin/`、
     `/api/public/firmware/latestx` 全 404。

## 4. 独立核对记录（本会话实测）

- `quicktunnel-hostcheck.log` 逐行实读：14/14 ALL PASS，头部隧道 URL、双 PID
  （18940/15892）、窗口起算 2026-09-13T12:26Z 与上表一致，尾部
  `D2_HOSTCHECK=PASS`。
- 日志 SHA-256 实算与登记值一致（`6cea8037…`）。

## 5. endpoint 注入绑定（进入受验 APK）

- 注入方式: build.yml dispatch 输入
  `firmware_latest_url=https://feed-recipients-copper-ellis.trycloudflare.com/api/public/firmware/latest`
- 注入时序合规: 先隧道取址 → D2 宿主端到端检查通过 → 唯一一次受验 APK
  构建（run 34757419111）→ APK 内 2 处 dex 字符串静态确认同 URL。
- 下载路径走 token 验签端点 `/api/public/firmware/download`，无静态直链。

## 6. 原始证据指针

- `.cache/p3-3-v2-service/quicktunnel-hostcheck.log`（D2 检查完整日志）
- `.cache/p3-3-v2-service/service.log`（D3 观测期日志，每请求一行含 requestId）
- `.cache/p3-3-cloudflared/tunnel.log`、`tunnel.pid`、`acquisition.txt`
- `docs/ota-exec-notes/P3-3-acceptance-apk-build-2026-09-13.md`（D1/D2/P2 统一留证）
- 服务方案与 16 项宿主自测: `docs/ota-exec-notes/P3-3-v2-service-plan-and-selftest-2026-09-13.md`

## 7. 边界与不证明范围（沿用合同 description）

- 本输入不证明 P4-2 通过（不实现 register/D1/admin 发布链）。
- 服务不放宽 App 校验、不注入 OtaService 状态；APK 走真实 Dio HTTP 请求。
- 地址改变或隧道退出即暂停相关阶段，不换地址、不追加 APK 构建；
  D4 toy→真包切换只重启本机服务，隧道进程与公网地址维持不变；
  D5 完整清理（按 PID 终止双进程 + 日志归档 + 无残留验证）为判据内动作。
