# P3-3-v3 外部输入证据：EXT-TOY-BOOTABLE（可启动受控固件包 toy 3.2.1/30201）

- 输入 ID: EXT-TOY-BOOTABLE（category=fixture）
- 核对会话: 独立验收会话（非实现会话，P3-3 冻结办理）
- 日期: 2026-09-13
- freeze_commit: `a178ecc1dca3929e1bca702fb11344f3c5bd2872`
- 制包依据: 用户批准的离线准备路径（零真机/零云端/零代码改动），
  记录 `docs/ota-exec-notes/P3-3-offline-assets-2026-09-13.md`

## 1. 冻结身份四元组

| 项 | 值 |
| --- | --- |
| 目标版本 | 3.2.1（versionCode 30201） |
| pre-finalize BIN | SHA-256 `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f`（602,984B） |
| 最终镜像 raw | SHA-256 `43ee943a185f63d70284c7c5a9992d677a9bf8c518dacd2e63df8ec7e5809b55` |
| fw_header 双零摘要 | `a7ae03872dbeb62f1167f16701d57eee0666bab547d94ef08a5f2c603dd755d9` |
| ETU 包 | 规范名 `e-track-at32f435-v3.2.1-full.etu`，SHA-256 `fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2`（284,092B） |

## 2. 实物独立核对（本会话实测）

- 实物路径: `.cache/p3-3-assets/e-track-at32f435-v3.2.1-full.etu`
  （另有制包过程副本 `toy-3.2.1-30201-full.etu`，同哈希同字节）。
- sha256sum 实测（2026-09-13，独立验收会话）:
  - `e-track-at32f435-v3.2.1-full.etu` → `fc4ae5a9…d479a2`，284,092B ✓
  - `toy-3.2.1-30201-final.bin` → `43ee943a…09b55`（602,984B）✓
  - `toy-3.2.1-pre-finalize.bin` → `7328c1b1…2153f`（602,984B）✓
- 受控 v2 服务启动时对 fixture 做字节级核验（失配拒绝），实测通过
  （见 EXT-HTTP-TEST-SERVICE 证据 §2）。
- 版本占用检查: 30201 与 30202 无混用、无冲突。

## 3. 上板资格审定

- 独立准入复核 ADMISSION_PASS（`docs/ota-exec-notes/P3-3-admission-review-2026-09-13.md`，
  2026-09-13）覆盖资产资格审定。
- freeze_commit 源码树与制包基线 c89c58f 在 Production profile 范围的一致性
  已在准入复核中核对（不一致才需按资产方案 §2.3 重建重出四元组）。
- `tests/ota-vectors/` golden vectors 不具上板资格，未用于本输入。

## 4. 边界

- 离线制包完成不等于闭环通过：toy 闭环判据为 C-TOY-LOOP（独立执行）。
- ETU 因 AES nonce 随机不可从文档复现；实物 `.cache/p3-3-assets/` 为唯一
  持有处，丢失重打包须重新登记（不可回改本证据）。
