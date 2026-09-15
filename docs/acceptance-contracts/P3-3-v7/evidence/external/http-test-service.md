# P3-3-v7 外部输入证据：EXT-HTTP-TEST-SERVICE（受控 v2 测试服务 + Quick Tunnel r5）

- 输入 ID: EXT-HTTP-TEST-SERVICE（category=environment）
- 编制: 实现会话（P3-3-IMPL-20260907，DRAFT）；冻结核对: 待非实现会话
- 日期: 2026-09-15
- freeze_commit: `0fb167cf4c44a6e4741e5a42fcd4945cf29f7780`（v6/v7 共用——v7 为纯合同勘误轮，零实现/服务变化）
- 服务实现: `Tools/ota/p3-3-service/` 四件套（service.py / service_config.json /
  selftest.py / tls_hostcheck.py，SERVICE_VERSION=2；冻结依赖经 Validation
  profile required_paths 落地）。方案与 16 项宿主自测 + tls_hostcheck 宿主
  HTTPS 全链记录见 `docs/ota-exec-notes/P3-3-v2-service-plan-and-selftest-2026-09-13.md`
  （第五轮修订）。

## 1. v6 轮部署实例（本合同绑定的执行事实，r6 实机验证）

- r5 Quick Tunnel：域名
  `https://quality-lap-aggregate-comment.trycloudflare.com`，cloudflared
  PID 3868，隧道日志 `.cache/p3-3-cloudflared/tunnel-r5-20260914.log`；
  隧道指向 `http://127.0.0.1:8443`，Cloudflare 边缘终止 TLS。
- v6 服务实例：python PID 17520，2026-09-14 23:42:39 起，监听
  127.0.0.1:8443（`--public-base-url=r5 隧道地址`，
  `--active-release real-30203`，脱离 harness 托管），请求日志
  `.cache/p3-3-v2-service/service-v6-20260914.log`。
- 启动横幅（`service-v6-restart.stdout`）三 fixture fail-closed 字节级
  核验通过：real-30202 `284573:0c8ae468…`、real-30203
  `284608:a543f952…`、toy-30201 `284540:0219899d…`。
- endpoint 注入：第六轮受验 APK（run 34864052541）构建时
  firmware_latest_url=r5 隧道 latest 地址，构建日志
  DISPATCH_FIRMWARE_LATEST_URL 留证。
- 观测期请求时间线（service-v6-20260914.log）：23:43:06/23:43:19
  latest（30202）→ 23:43:23 download 284,608B（首次下载，未形成完整
  传输闭环）→ 23:59:30/00:00:11 latest（30202+ab0585f7 真实起点）→
  00:00:15 download 284,608B → BLE 传输 → 00:06:05/00:06:08/00:07:22
  三次 latest 自报 30203+3a282768 全等 → no_update 自洽。
- D 清理（2026-09-15）：隧道 3868 与服务 17520 均按 PID 核验命令行
  身份后终止；cloudflared 进程零残留、8443 端口零监听。验收复核依据
  =已落盘日志与 probe 产物，不依赖活端点。

## 2. 历史实例归属（保留，不与本合同指纹混用）

- r4 Quick Tunnel（`describing-substance-databases-past.trycloudflare.com`，
  2026-09-14 04:22:26 起）+ v5 服务实例（PID 22316，2026-09-14 20:21:05
  起，`--active-release toy-30201`）服务 v5 轮 toy/真包闭环与第五轮 APK
  注入（v5 合同事实）；请求日志
  `.cache/p3-3-v2-service/service-v5-20260914.log` 与
  `service-v5-r20260914-real.log` 留档。
- v6 合同 EXT-HTTP-TEST-SERVICE 的 fingerprint 曾遗留 r4/v5 实例身份
  （v6 独立验收报告 G02），v7 起本输入指纹只绑 r5+v6 实例；r4/v5 身份
  仅在本节作历史记录。

## 3. 边界与不证明范围（沿 v5/v6 口径不变）

- 明确不证明 P4-2 通过（不实现 register/D1/admin 发布链）。
- 服务不放宽 App 校验、不注入 OtaService 状态；APK 走真实 Dio HTTP
  请求。
- 不用 CF 账号、不读任何 token；本轮服务与隧道均已终止，v7 验收为
  纯离线复核，不重新拉起。
