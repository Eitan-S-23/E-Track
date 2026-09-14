# P3-3-v7 外部输入证据：EXT-REAL-ETU（真实固件 OTA 包 3.2.3/30203，v6 制包）

- 输入 ID: EXT-REAL-ETU（category=fixture）
- 编制: 实现会话（P3-3-IMPL-20260907，DRAFT）；冻结核对: 待非实现会话
- 日期: 2026-09-15
- freeze_commit: `0fb167cf4c44a6e4741e5a42fcd4945cf29f7780`（v6/v7 共用——v7 为纯合同勘误轮，零实现/固件/资产变化）
- 制包依据: 源镜像=`1894f9d` 修复版 GCC 构建原件（pre-finalize `4b16048f…`，
  603,764B，即板上 3.2.0-fixed 本体，与 toy/30202 真包同源），
  `etu_pack.py finalize 3.2.3 + pack-full 30203`；制包与四元组记录见
  `docs/ota-exec-notes/P3-3-r6-verification-execution-2026-09-14.md` §2/§3
- v6 轮本包已完成 30202→30203 实机闭环（r6），当前设备即运行本包目标镜像

## 1. 冻结身份四元组（v6 制包，本合同唯一绑定目标）

| 项 | 值 |
| --- | --- |
| 目标版本 | 3.2.3（versionCode 30203） |
| pre-finalize BIN | SHA-256 `4b16048f5970c9cef924690a62031e232cd1d2fb8c1b8af85c18993cfdf830ec`（603,764B，与 toy/30202 真包同一源镜像） |
| 最终镜像 raw | SHA-256 `3a2827683cbd2b557dd5d441927d1a490b3b28fe11f8d7a4b4b5c86a594144a3`（603,764B） |
| fw_header 双零摘要 | `1a60579440c6feb79fa52f488dfcc0d6ff893eda36533d32ff08e4685094bd28` |
| ETU 包 | 规范名 `e-track-at32f435-v3.2.3-full.etu`，SHA-256 `a543f952dcd1b0f57770669e253b29e9a93b7ffb94263bc7bdc3b1bdf4ef1915`（284,608B） |

升级链归属：与 30200/30201/30202 各环仅 fw_header 版本身份字段
（0x408..0x45F，41 字节）差异，功能本体逐字节同源——同源升级链
30200→30201→30202→30203 第 4 环。

## 2. 实物独立核对（v6 轮实测，供验收会话复核）

- 实物路径: `.cache/p3-3-assets-v6/e-track-at32f435-v3.2.3-full.etu`
  （admission worktree 内唯一持有处；ETU 因 AES nonce 随机不可从文档
  复现，丢失重打包须重新登记）。
- 离线验证 `verify_v6.py` 判据 A-G+I 全 PASS
  （报告 `.cache/p3-3-assets-v6/verify_v6_report.txt`：头字段/双零摘要/
  header_crc32 独立复算、`etu_unpack --verify-fw-header` OK、candidate
  与规范名副本逐字节比对、升级检查模拟 30203>30202、与 v5 真包 41 字节
  同源差异判据）。
- v6 轮独立验收会话已复算实物（2026-09-15，P3-3-v6-acceptance 报告
  §4.1）：ETU 284,608B `a543f952…`、目标镜像 603,764B `3a282768…`，
  与本四元组全等。
- r6 实机闭环（服务端日志证据）：`.cache/p3-3-v2-service/service-v6-20260914.log`
  ——00:00:15 download 284,608B（本 ETU）→ BLE 传输 → 设备重启 →
  00:06:05.449 / 00:06:08.608 / 00:07:22.431 三次 latest 设备自报
  currentVersionCode=30203 + currentImageSha=`3a282768…4144a3` 与本
  四元组第 2/4 行全等 → 200 no_update（114B）自洽。

## 3. 历史版本归属（保留，不与本合同指纹混用）

- v5 真包 3.2.2/30202（镜像 raw `ab0585f7…`、ETU `0c8ae468…`、
  284,573B）实物 `.cache/p3-3-assets-v5/` 原样保留作历史轮证据；
  30202 闭环已在 v5 轮 O4 完成。
- v6 合同 EXT-REAL-ETU 的 fingerprint 曾遗留 v5 的 30202 四元组（v6
  独立验收报告 G02），v7 起本输入指纹只绑 30203；30202 身份仅在本节
  作历史记录。
