# P3-3-v5 外部输入证据：EXT-REAL-ETU（真实固件 OTA 包 3.2.2/30202，v5 重制）

- 输入 ID: EXT-REAL-ETU（category=fixture）
- 编制: 实现会话（P3-3-IMPL-20260907，DRAFT）；冻结核对: 待非实现会话
- 日期: 2026-09-14
- freeze_commit: `6415226b8c30abcffa2b9bab52f0db717f8f7cb9`
- 重制依据: 与 EXT-TOY-BOOTABLE 同批（修复轮整体授权；源镜像同为
  `1894f9d` 修复版 GCC 构建 `4b16048f…`，即板上 3.2.0-fixed 本体），
  记录 `docs/ota-exec-notes/P3-3-offline-assets-v5-rebuild-2026-09-14.md`

## 1. 冻结身份四元组（v5）

| 项 | 值 |
| --- | --- |
| 目标版本 | 3.2.2（versionCode 30202） |
| pre-finalize BIN | SHA-256 `4b16048f5970c9cef924690a62031e232cd1d2fb8c1b8af85c18993cfdf830ec`（603,764B，与 toy 同一源镜像，两份独立副本） |
| 最终镜像 raw | SHA-256 `ab0585f71b9a523863b582e8ed4cc47a279bf6e57c4a1038635593306746ab7e`（603,764B） |
| fw_header 双零摘要 | `c57eb4cbd5d903b67f443f60daf82d5463008fc9d5146fd89333a9d854773ff0` |
| ETU 包 | 规范名 `e-track-at32f435-v3.2.2-full.etu`，SHA-256 `0c8ae468948d8e85af0e8eaf3ec52e046f1b6a3cdba88f9bd8478790f0590f6f`（284,573B） |

ETU 外层属性：target_vcode=30202、flags=0x000b、key_id=1、nonce
`f2daa90ed2056608e0a0ef2b5e20330e`；fw_header crc32（头前 92B）
`0xACFD2124`；finalize 参数与 toy 同款（`--ver-name 3.2.2 --build-ts
1789387723 --hw-rev 1 --layout-id 1 --min-boot 1`）。

## 2. 实物独立核对（v5 轮实测，供冻结会话复核）

- 实物路径: `.cache/p3-3-assets-v5/e-track-at32f435-v3.2.2-full.etu`
  （另有制包过程副本 `real-3.2.2-30202-full.etu`，同哈希同字节）。
- 离线验证 `verify_v5.py` 判据 A-I 全 PASS（报告同目录
  `verify_v5_report.txt`）：头字段/双零摘要/header_crc32 独立复算、
  `etu_unpack.py --verify-fw-header`、candidate 逐字节比对、规范名副本
  比对、升级检查模拟 30202>30201 ✔ 全过。
- **toy 与真包两份最终镜像间仅 38 字节差异，全部位于 0x408..0x45F**
  （fw_header 版本身份字段）——与原轮同构：功能本体逐字节相同，版本
  身份是唯一区分，不同包分别绑定身份、不混用（用户裁定语义沿用）。
- 受控 v2 服务启动双 fixture 字节级核验（含 real-30202）实测通过
  （见 EXT-HTTP-TEST-SERVICE 证据 §2）。
- 版本占用检查: 30202 与 30201 无混用、无冲突。

## 3. 上板资格

- 同 EXT-TOY-BOOTABLE：资产方案/准入框架沿用 v3 ADMISSION_PASS，本轮按
  §2.3 基线规则从修复版源重建，制包工具身份与原轮一致、零改动。
- 真包仅在 C-TOY-LOOP PASS 后经受控服务 D4 切换激活（只停服务 →
  `--active-release real-30202` 重启，隧道进程与公网地址不变）。

## 4. 边界

- 闭环判据为 C-REAL-LOOP（独立执行）；终点 versionCode 30202 与完整 raw
  SHA-256 `ab0585f7…` 独立比对，不得由 toy 结果代替。
- ETU 因 AES nonce 随机不可从文档复现；实物 `.cache/p3-3-assets-v5/`
  为唯一持有处，丢失重打包须重新登记（不可回改本证据）。
