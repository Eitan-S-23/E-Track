# P3-3-v4 外部输入证据（沿用 v3 核对记录）：EXT-REAL-ETU（真实固件 OTA 包 3.2.2/30202）

- 输入 ID: EXT-REAL-ETU（category=fixture）
- 核对会话: 独立验收会话（非实现会话，P3-3 冻结办理）
- 日期: 2026-09-13
- freeze_commit: `a178ecc1dca3929e1bca702fb11344f3c5bd2872`
- 制包依据: 用户裁定——与 toy 同一合格生产镜像（7328c1b1…）经
  finalize 3.2.2 + pack-full 30202 独立封包，两镜像仅 fw_header 版本身份
  字段（0x408..0x45F）差异、功能本体逐字节相同；不同包分别绑定身份、
  不混用。记录 `docs/ota-exec-notes/P3-3-offline-assets-2026-09-13.md`

## 1. 冻结身份四元组

| 项 | 值 |
| --- | --- |
| 目标版本 | 3.2.2（versionCode 30202） |
| pre-finalize BIN | SHA-256 `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f`（602,984B，与 toy 同一镜像） |
| 最终镜像 raw | SHA-256 `c958221392fade8b40520df2d7fd4278632d64bcdd8261b0ac7536c6468a7f39` |
| fw_header 双零摘要 | `85d19304bcc8f40be99e544705f4100c7b9d2702882773f32a46226c1be9d327` |
| ETU 包 | 规范名 `e-track-at32f435-v3.2.2-full.etu`，SHA-256 `0a2eb26a481d8c462b5316a67a151c8241de354d00797fa22f11e77056538ce5`（284,112B） |

## 2. 实物独立核对（本会话实测）

- 实物路径: `.cache/p3-3-assets/e-track-at32f435-v3.2.2-full.etu`
  （另有制包过程副本 `real-3.2.2-30202-full.etu`，同哈希同字节）。
- sha256sum 实测（2026-09-13，独立验收会话）:
  - `e-track-at32f435-v3.2.2-full.etu` → `0a2eb26a…38ce5`，284,112B ✓
  - `real-3.2.2-30202-final.bin` → `c9582213…a7f39`（602,984B）✓
  - `real-3.2.2-pre-finalize.bin` → `7328c1b1…2153f`（与 toy pre-finalize
    同哈希，印证「同一合格生产镜像」）✓
- 受控 v2 服务启动时对 fixture 做字节级核验（失配拒绝），实测通过
  （见 EXT-HTTP-TEST-SERVICE 证据 §2）。
- 版本占用检查: 30202 与 30201 无混用、无冲突。

## 3. 上板资格审定

- 独立准入复核 ADMISSION_PASS（`docs/ota-exec-notes/P3-3-admission-review-2026-09-13.md`）
  覆盖资产资格审定；真包仅在 C-TOY-LOOP PASS 后经受控服务 D4 切换激活
  （只停服务 → `--active-release real-30202` 重启，隧道进程与公网地址不变）。

## 4. 边界

- 闭环判据为 C-REAL-LOOP（独立执行）；终点 versionCode 30202 与完整 raw
  SHA-256 `c9582213…` 独立比对，不得由 toy 结果代替。
- ETU 因 AES nonce 随机不可从文档复现；实物 `.cache/p3-3-assets/` 为唯一
  持有处，丢失重打包须重新登记（不可回改本证据）。

## v4 冻结复核（2026-09-14）

- 资产实物 sha256sum 复核：ETU `0a2eb26a…`/284,112B 全等，四元组与 v3 冻结值不变。
- 编制：实现会话（DRAFT）；冻结核对待非实现会话。
