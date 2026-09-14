# P3-3-v5 外部输入证据：EXT-TOY-BOOTABLE（可启动受控固件包 toy 3.2.1/30201，v5 重制）

- 输入 ID: EXT-TOY-BOOTABLE（category=fixture）
- 编制: 实现会话（P3-3-IMPL-20260907，DRAFT）；冻结核对: 待非实现会话
- 日期: 2026-09-14
- freeze_commit: `6415226b8c30abcffa2b9bab52f0db717f8f7cb9`
- 重制依据: 修复轮整体授权（用户 2026-09-14 批准的链路：O2 缺陷修复
  `1894f9d` → 重建 → finalize 烧板 → BCB 恢复 r2 → 重制包 → v5 冻结 →
  O 序列重跑），记录 `docs/ota-exec-notes/P3-3-offline-assets-v5-rebuild-2026-09-14.md`

## 1. 为什么必须重制（v4→v5 资产变更根因）

- v4 轮 toy/真包源 = `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f`
  （602,984B，O2 缺陷版 3.2.0，未含 `session_handle_end` 的 BCB STAGED
  提交+复位）。O2 实测 PRODUCT_FAIL 已证明该版本固件升级闭环断裂。
- v4 合同 EXT-TOY 描述的基线规则在本轮触发：freeze_commit 源码树相对
  v3 制包基线出现 Production profile 内固件提交（`1894f9d`），按资产方案
  §2.3 必须重建重出四元组。若 O2 重跑仍下载旧 toy，升级后接收端固件
  退回缺陷代码，O3 必然复现 REBOOT_RECONNECT_FAILED。
- **v5 源镜像** = `1894f9d` 的 GCC 构建原件
  `.cache/bg/app-gcc/X-Track-App-GCC.bin`（603,764B，SHA-256
  `4b16048f5970c9cef924690a62031e232cd1d2fb8c1b8af85c18993cfdf830ec`），
  与板上 3.2.0-fixed finalize 镜像（`d7cc4194…a38e488`）仅差 0x400-0x45F
  头区、与板上 S5 快照身份（`24fc02ea…`）闭合——即当前板上运行本体的
  同一构建产物（provenance 链见重制记录 §1）。

## 2. 冻结身份四元组（v5）

| 项 | 值 |
| --- | --- |
| 目标版本 | 3.2.1（versionCode 30201） |
| pre-finalize BIN | SHA-256 `4b16048f5970c9cef924690a62031e232cd1d2fb8c1b8af85c18993cfdf830ec`（603,764B） |
| 最终镜像 raw | SHA-256 `aeafc96e77d372aea1e893a979f2368ba9176c4999a61090ceb2956cd4085298`（603,764B） |
| fw_header 双零摘要 | `9d7a3cdca4f8612908a13c538796cddcb9bb0e27c8b3d06ae21769dcbe123371` |
| ETU 包 | 规范名 `e-track-at32f435-v3.2.1-full.etu`，SHA-256 `0219899dd993f61f2c75eaec7002bc9c24e0fc629a60e87046e74266d55410c5`（284,540B） |

ETU 外层属性：target_vcode=30201、flags=0x000b、key_id=1（开发密钥，
与固件 `ota_keys.c` key_id=1 一致）、nonce
`4d3bfb84015032a9af2610930ef3782f`；fw_header crc32（头前 92B）
`0x138BA318`；finalize 参数 `--ver-name 3.2.1 --build-ts 1789387723
--hw-rev 1 --layout-id 1 --min-boot 1`（与原轮同款口径）。

## 3. 实物独立核对（v5 轮实测，供冻结会话复核）

- 实物路径: `.cache/p3-3-assets-v5/e-track-at32f435-v3.2.1-full.etu`
  （另有制包过程副本 `toy-3.2.1-30201-full.etu`，同哈希同字节）。
- 离线验证 `verify_v5.py` 判据 A-I 全 PASS（rc=0，报告
  `.cache/p3-3-assets-v5/verify_v5_report.txt`）：pre-finalize 副本与 bg
  构建原件逐字节相等；finalize 差异仅 0x400..0x45F（78B）本体零差异；
  头字段独立解码（magic=ETFW/header_ver=1/vcode=30201/build_ts=1789387723/
  image_len=603764）全过；双零摘要独立复算相等；header_crc32 独立复算
  相等；`etu_unpack.py --verify-fw-header` OK；candidate 与 finalize 镜像
  逐字节一致；规范名副本与原始产物逐字节一致；升级检查模拟 30201>30200 ✔。
- 补充判据（v5 新增）：**与板上 3.2.0-fixed 本体逐字节同源**——差异 41
  字节全部位于 0x408..0x45F 头身份字段，功能本体零差异，排除「升级后
  本体回退」风险。
- 受控 v2 服务启动时对 fixture 字节级核验（失配拒绝）实测通过
  （见 EXT-HTTP-TEST-SERVICE 证据 §2）；公网签名下载探针
  `v5-download-probe.etu`（284,540B，SHA `0219899d…`）与实物逐字节全等。
- 版本占用检查: 30201 与 30202 无混用、无冲突；板上 30200 → toy 30201 →
  真包 30202 同源升级链三环。

## 4. 上板资格

- 资产方案与准入框架沿用 v3 独立准入复核 ADMISSION_PASS
  （`docs/ota-exec-notes/P3-3-admission-review-2026-09-13.md`）；本轮
  按同一方案 §2.3 基线规则从修复版源重建，制包工具身份
  （`Tools/etu_pack.py` blob `8a413ed3…`、`Tools/etu_unpack.py` blob
  `86409ec3…`）与原轮登记一致、零改动。
- `tests/ota-vectors/` golden vectors 不具上板资格，未用于本输入。

## 5. 边界

- 离线制包完成不等于闭环通过：toy 闭环判据为 C-TOY-LOOP（独立执行）。
- ETU 因 AES nonce 随机不可从文档复现；实物 `.cache/p3-3-assets-v5/`
  为唯一持有处，丢失重打包须重新登记（不可回改本证据；最终镜像 raw SHA
  可由 pre-finalize 源+参数确定性复现，ETU SHA 不可）。
- v4 旧资产 `.cache/p3-3-assets/` 8 文件原样保全（v4 冻结包证据完整性
  所需），已不再被服务引用。
