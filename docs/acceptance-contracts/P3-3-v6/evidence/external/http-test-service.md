# P3-3-v5 外部输入证据：EXT-HTTP-TEST-SERVICE（受控 v2 服务 + Quick Tunnel r4）

- 输入 ID: EXT-HTTP-TEST-SERVICE（category=environment）
- 编制: 实现会话（P3-3-IMPL-20260907，DRAFT）；冻结核对: 待非实现会话
- 日期: 2026-09-14
- freeze_commit: `6415226b8c30abcffa2b9bab52f0db717f8f7cb9`
- 部署执行依据: 修复轮整体授权（用户 2026-09-14 批准：O2 缺陷修复→重建→重制包→
  合同升 v5 重冻结→O 序列重跑）+ 服务路线用户裁定 B（Quick Tunnel 第四条）+
  v5 fixture 切换（同批授权「授权，此外你说的超授权问题也一并授权」）

## 1. 冻结身份（服务实现）

`Tools/ota/p3-3-service/` 四件套（SERVICE_VERSION=2；runner 冻结依赖经
Validation profile required_paths 落地，本节哈希仅为辅助说明，不替代 profile
冻结依赖）：

- `service.py` SHA-256 `f71012de119811863d2274fd674a702c69a512f18ea73e3188be2233130ba009`（与 v3/v4 冻结值一致，零改动）
- `service_config.json` SHA-256 `0f552033a1be50fa0e8ed1ec0b04b50422ff556ff63582fde7df7aa194a87749`（**v5 唯一变化**：两 release 的 targetImageSha256 与 asset 身份改绑 v5 重制包四元组，path 指向 `.cache/p3-3-assets-v5/`；随 freeze_commit 6415226 入库）
- `selftest.py` SHA-256 `b96d4e2f05c84c3401c1dff14ee9c0f6e5dc7ee0a076e272180d2f4d4aa202b4`（与 v3/v4 一致）
- `tls_hostcheck.py` SHA-256 `f9202b6b47f50526e75710fd2b8048e87b24bb94ab07f82b88716a761821da6c`（与 v3/v4 一致）

服务语义（latest v2 十参数/token 下载/激活时序等）与 v4 合同 description
所载完全一致，本轮零代码改动；fixture 身份由 v4 旧四元组
（toy `fc4ae5a9…`/real `0a2eb26a…`）整体切换为 v5 重制四元组
（toy `0219899d…`/real `0c8ae468…`，见 EXT-TOY-BOOTABLE/EXT-REAL-ETU）。

## 2. 运行史与当前部署（如实登记）

历史轮作废（沿用 v4 登记）：r1 `feed-recipients-copper-ellis`（2026-09-13
20:26Z 8h 窗口到期路径上死亡）、r2 `ideas-coastal-province-enrollment`
（2026-09-14 00:33 后无声死亡）、r3 `started-monitors-shower-cherry`
（v4 冻结绑定轮，2026-09-14 03:09-03:12 蜂窝链路瞬断杀进程，域名随进程
永久失效——v4 合同 EXT-HTTP/C-RELEASE-BUILD 事实基础失效即 v5 升版根因
之一）。三死亡轮日志归档 `tunnel-r1/r2/*.log`、`tunnel.log`、
`service-r1/r2*.log`，不参与任何判据。

当前部署（r4 轮，2026-09-14）：

| 项 | 实测值 |
| --- | --- |
| Quick Tunnel 公网地址 | `https://describing-substance-databases-past.trycloudflare.com` |
| cloudflared | 2026-09-14 04:22:26 起（tunnel log 20:22:26Z），Connector ID `78d40f42-e9bd-49fe-8610-cb561bc4710b`，QUIC 边缘 sjc，`--no-autoupdate --url http://127.0.0.1:8443`（shell `&` 形式，不受会话进程退出影响） |
| 隧道日志 | `.cache/p3-3-cloudflared/tunnel-r4-20260914.log`（SHA-256 `46afdffed289e5fe161873441952d06600f8d9bb7742db50e08f69fd84a8cfc2`）、`tunnel-r4.pid` |
| 受控 v2 服务（v5 实例） | python PID 22316，2026-09-14 20:21:05 起，监听 `127.0.0.1:8443`，`--public-base-url`=r4 隧道地址，`--active-release toy-30201`，完全脱离 harness 托管（`(python … &)` 形式） |
| 启动双 fixture 核验 | toy-30201 `e-track-at32f435-v3.2.1-full.etu` 284,540B `0219899dd993…`、real-30202 `e-track-at32f435-v3.2.2-full.etu` 284,573B `0c8ae468948d…` 通过（失配拒绝启动的 fail-closed 语义下即资产身份成立；`service-v5-restart.stdout` SHA-256 `8b03ddb9a787be49d64da494d5368198f09d362e438e9b7e8a40dc09f60e9ecb`） |
| 请求日志 | `.cache/p3-3-v2-service/service-v5-20260914.log`（SHA-256 `be1de1e327ac27d958ab59d911e17737ccd7a2e7ea9e8911d1a212b720b32b8e`） |

r4 服务轮换史（如实）：04:22:49 初启（托管形式，供旧 toy `fc4ae5a9…`，
其 O1/O2 请求日志完整保留 `service-r4-20260914.log`，SHA-256
`8edb901016cf2311ccf96ceab1ef4b2296f40c51a3edbe789c5da71191ee4d2c`；
16:5x 会话轮换时托管进程退出，属 HARNESS 类事件）→ 17:01:54 脱离托管
重启（PID 23040，仍旧 toy；`service-r4-restart.stdout` SHA-256
`bc84011ca92d04d31dda5bd628e83cd392dac35a3d2d1bbf5e6c03921ff4a5cd`）→
20:21:05 按 PID 精确核验停止旧实例后起 v5 实例（PID 22316，新 fixture）。
**隧道进程与公网地址全程未变**（r4 起活至本证据编制时存活）。

## 3. 宿主端到端检查（两层，如实分层登记）

- **r4 轮 D2：14/14 ALL PASS（2026-09-14 04:2x，当时 fixture=旧 toy
  `fc4ae5a9…`）**——latest 十参数 200/schemaVersion=2/versionCode=30201/
  downloadUrl 同域 https 前缀/fixture 哈希与大小一致/下载端点 200 且 SHA
  全等/证书链默认信任库校验（CN=trycloudflare.com，issuer Google Trust
  Services WE1）/根路径与 3 个未知端点 404。登记于主执行笔记 §13.2。
- **v5 fixture 切换后三层验证（2026-09-14 20:2x，新 toy `0219899d…`）**：
  ①本机 `/latest` 200，updateAvailable=true，versionName=3.2.1/
  versionCode=30201，targetImageSha256=`aeafc96e…`，asset
  `0219899d…`/284,540，签名 downloadUrl 指向 r4 隧道域名；
  ②公网隧道域名 `/latest` 200 同身份；③经其签名 downloadUrl 下载得
  284,540B，SHA-256 `0219899d…` 与本地实物逐字节全等（探针落盘
  `.cache/p3-3-v2-service/v5-download-probe.etu`）。登记于
  `P3-3-offline-assets-v5-rebuild-2026-09-14.md` §7。

O 序列重跑时的正式 D 判定由验收会话按合同执行并绑定原始日志。

## 4. endpoint 注入绑定（进入受验 APK）

- 注入方式: build.yml dispatch 输入
  `firmware_latest_url=https://describing-substance-databases-past.trycloudflare.com/api/public/firmware/latest`
- 注入时序合规: 先隧道取址 → r4 D2 宿主端到端检查通过（旧 fixture 时点，
  endpoint 与隧道身份即此轮确定）→ 受验 APK 构建（run 34781909023，
  2026-09-14 04:48:47 派发，dispatch 提交 `55b2d07`，用户 2026-09-14
  04:4x 逐轮授权第 5 笔构建额度）→ 用户装机并确认升级页元数据与冻结基准
  全等 → 16:53 真机 latest×3 200（O1 实测，含连接板卡后真实
  currentImageSha，证明 endpoint 在受验 APK 内真实生效）。
- 下载路径走 token 验签端点 `/api/public/firmware/download`，无静态直链。

## 5. 原始证据指针

- `.cache/p3-3-cloudflared/tunnel-r4-20260914.log` + `tunnel-r4.pid`
- `.cache/p3-3-v2-service/service-r4-20260914.log`（含 O1/O2 真机请求行）、
  `service-r4-restart.stdout`、`service-r4-20260914-part1.bak`
- `.cache/p3-3-v2-service/service-v5-20260914.log`、`service-v5-restart.stdout`、
  `v5-download-probe.etu`
- `docs/ota-exec-notes/P3-3-speedometer-real-ble-fix-2026-09-14.md` §12-§14
  （r3 死亡登记、r4 轮执行、第五轮 APK、O1/O2 实测）
- `docs/ota-exec-notes/P3-3-offline-assets-v5-rebuild-2026-09-14.md` §7（三层验证）
- 服务方案与 16 项宿主自测: `docs/ota-exec-notes/P3-3-v2-service-plan-and-selftest-2026-09-13.md`

## 6. 边界与不证明范围（沿用合同 description）

- 本输入不证明 P4-2 通过（不实现 register/D1/admin 发布链）。
- 服务不放宽 App 校验、不注入 OtaService 状态；APK 走真实 Dio HTTP 请求。
- 地址改变或隧道退出即暂停相关阶段，不换地址、不追加 APK 构建；
  D4 toy→真包切换只重启本机服务（`--active-release real-30202`），隧道
  进程与公网地址维持不变；D5 完整清理（按 PID 终止双进程 + 日志归档 +
  无残留验证）为判据内动作。
- v5 fixture 切换属宿主侧操作（零真机/零云端/零产品代码改动），授权链
  见本文件头。
