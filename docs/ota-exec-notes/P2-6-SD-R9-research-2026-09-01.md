# P2-6-SD-R9 派工前 research：C7 补测（20802 制包 + Apply 中途失败注入）（2026-09-01）

- 会话：R9 实现 agent（授权来源：`.cache/_r9.txt` 派工书，实现会话不自验收）
- 证据根：`.cache/p2-6-sd-r9-20260901-01-implementation/`（启动前写入预检确认原不存在，
  路径链 `D:\github\my\E-Track` → `.cache` → 新根均无 reparse point，全部位于项目根内）
- 本文按看板 §0 规则 7 在编码/制包前落盘检索与分析结论。

## 1. 为什么 R8 拿不到 C7、R9 怎么补

- 板卡现态：test v2.8.1 / vcode=20801 / BCB=CONFIRMED(4)（R8 证据 §4）。
- SD 上全部现存冻结包（R5 PATCH / R7 FULL / R8 FULL / P2-5 系列）`target_vcode`
  均=20801，`ota_sd.c:312` 的 Inspect 版本关 `target_vcode <= current_vcode →
  OTA_SD_ERR_VERSION` fail-closed 拒绝，进不到 Begin/Apply。
- R9 路线：离线制 2.8.2（vcode=20802 > 20801）包绕过版本关；BAD 包把失败点
  推到 Apply 内部（acquire 之后），取得 C7 的三段观测。

## 2. 决定性陷阱确认（ota_package.c 源码核对）

`Libraries/OTA/ota_package.c`（本轮逐行核对，与派工书描述一致）：

```text
ota_package_apply_full 流程（行号为当前源码）：
  parse_outer_header     :662
  validate_payload_crc   :667   ← 先校验外层 payload CRC32（off36）
  workspace_acquire      :672   ← 之后 overlay owner 才变 PACKAGE(2)
  arena 初始化           :690 前后
  LzmaDec_Allocate       :728
  candidate_prepare      :739   ← QSPI 擦 candidate 槽
  decode_candidate       :744   ← LZMA 解码（BAD 包失败点）
  validate_candidate_image :757
  cleanup（任何失败路径）: secure_zero + workspace_release → owner 回 0
```

- 直接翻 payload 字节而不修 off36 → `validate_payload_crc` 在 acquire 前返回
  `OTA_PACKAGE_ERR_PAYLOAD_CRC(-15)`，owner 永远不会变 PACKAGE。
- BAD 派生配方（派工书指定）：`b[64 + (len(b)-64)//2] ^= 0x01` 翻 payload 中位
  1 字节，再修 off36（payload_crc32=crc32(b[64:])）与 off60（header_crc32=
  crc32(b[0:60])），使外层 CRC 自洽 → 失败点推到 `decode_candidate` 的
  LZMA 解码（预期 `LZMA_DATA(-20)` 类失败，错误码 ≠ PAYLOAD_CRC）。
- 宿主正例：`tests/ota/test_ota_package.c` 的 "damaged LZMA stream" 用例即该
  形态（外层 CRC 修好、LZMA 流损坏 → LZMA_DATA，且 candidate 操作已发生），
  证明该失败点在 acquire 之后成立。

## 3. 宿主离线闸门设计（S1 第 5 步）

- 仿 `tests/ota/test_p2_6_capacity_package.c` 构型：`#define main
  p2_2_package_original_main` + `#include "test_ota_package.c"` + 自定义 main，
  源文件放证据根（不改仓库 tests/）。
- 编译命令同 `tests/ota/test_ota_package.py`：`gcc -std=c99 -Wall -Wextra
  -Werror -O2`，includes `Libraries` / `boot/include` /
  `bsdiff_lzma_AES128-main/bspatch/lzma` / `bsdiff_lzma_AES128-main/bspatch/AES128_CTR`，
  源=测试文件 + `Libraries/OTA/ota_package.c` + `Libraries/OTA/ota_keys.c` +
  `boot/src/boot_crc32.c boot_sha256.c boot_fw_header.c` + `LzmaDec.c` +
  `aes_core.c`，另加 `-I tests/ota`（容纳 fixture include）。
- device 构型：`current_vcode=20801`（对齐板卡现态），hw/layout/boot 与
  `default_device()` 一致。
- GOOD 断言：result=0。
- BAD 断言：result≠0 且 ≠PAYLOAD_CRC；`workspace_peak≠0` 或 arena 已初始化
  （HAL_OTA_Package.cpp 失败路径测量行 `workspace_peak=0` 而
  `arena_peak_observed≠0`——宿主构型以 arena 初始化为 acquire 证据）；
  acquire/release 计数各 1（cleanup 释放）。
- 两个结论均落盘到证据根 logs/。

## 4. 硬件会话采集 owner==PACKAGE(2) 的确定性方案

- Apply 在 FirmwareUpdate 的 workTimer（12ms LVGL timer）回调内同步执行，
  期间 `HAL::HAL_Update()` 不运行 → 停在 HAL_Update 的轮询读不到 owner=2。
- 方案：thbreak 设在 `LzmaDec_Allocate` 入口（workspace_acquire 之后、解码
  之前，owner 必已=2）。该符号在 App 侧为 `LzmaDec_Allocate`（lzma 源编进
  App），本轮 nm 重取地址。
- 备选：`ota_package_apply_full` 内 workspace_acquire 调用后的下一条语句地址
  （反汇编定位），两者取一即可；优先 LzmaDec_Allocate（符号唯一、语义清晰）。
- 其余符号（HAL_Update / g_ota_overlay_owner / OTA_GetBcbState / Push / Pop /
  FirmwareUpdate vptr / EnterPath / SelectRow / StartImport / FinishImport /
  strcmp / gpsSimulator / SD_IsReady / _SEGGER_RTT / vcode 读点 0x08010408）
  全部本轮 nm 重取，不沿用 R8 值。
- 页面状态机（R8 已实测沿用）：mode 页偏移 0x34e4；rows 在 +0x146c + i*312
  +4（path 字符串）；MODE_BROWSER=0 → SelectRow(Inspect) → MODE_CONFIRM=1 →
  StartImport(Begin) → MODE_WORKING=2 → 失败 FinishImport(false) →
  MODE_RESULT=3。
- Apply 窗口期 WDT 暂停已由 `monitor WriteU32 0xE0042008 0x00001000` 提供
  （每次 halt 后立即执行，R19 验证）。

## 5. uploader 双门禁适配（wrapper monkey-patch，零仓库改动）

`tests/ota/p2_6_rtt_sd_uploader.py` 有两道硬门禁会阻断本轮上传：

1. `validate_frozen_asset`（:511 附近）只认 R5 PATCH / R8 FULL 两个冻结资产
   SHA-256；新制 BAD-2.8.2.etu 会被拒。
2. `driver.load_frozen_device_header` 把设备镜像哈希冻结为 v2.8.0
   （`FROZEN_V280_IMAGE_SHA256`），GDB 脚本逐字比对运行中 fw_header；板卡现
   v2.8.1 必不匹配。

适配方案：在证据根写 wrapper 脚本 `import tests/ota/p2_6_rtt_sd_uploader`，
运行时 monkey-patch：
- `validate_frozen_asset` → 对 BAD-2.8.2.etu 返回 `("FULL-R9-BAD-2.8.2", sha)`，
  语义=本轮新资产登记（仍对未知输入 fail-closed）；
- 设备头校验 → 改为读哈希校验过的 v2.8.1 finalized bin
  （`.cache/p2-6-sd-ota/assets/` 冻结资产，SHA-256
  `A2D3083B25EE32813EFF6CC1BD0CF77CE235FD03BF79947C08B8A3C815D58E00`，
  与 R8 升级后板卡运行的 App slot 镜像一致），逐字比对保持 fail-closed。

理由：仓库上传器及其单测属冻结测试基建（R6 裁定白名单之外的修改需新裁定）；
wrapper 只在证据根内、运行时注入，不触碰仓库文件，行为保持 fail-closed。
该项将在证据文档 §7 如实登记（等效替代 + 理由）。

## 6. 资产与工具链状态核对（本轮实测）

- 源镜像 `.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.bin`：同源 ELF
  SHA-256 实测 `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`
  （与 R5/R7/R8 冻结记录一致）。
- `build_ts` 固定值沿用 `1786320000`（`.cache/p2-6-sd-ota/assets/asset-summary.json`，
  与 R8 全量包一致）；lzma_dict 默认 16384（不传 `--lzma-dict`，红线 2）。
- v2.8.1 finalized bin SHA-256 = `A2D3083B...D58E00`（上节引用）。

## 7. 风险与停止条件

- BCB 全程必须 CONFIRMED(4)、vcode 保持 20801；一旦 STAGED/APPLYING 立即停止
  原样上报（说明 BAD 包被接受进 staging——理论上外层 CRC 自洽+版本关放行后
  Begin/staging 传输可能成功，失败点在 Apply 的解码段，故 staging 传输成功是
  预期内，但 BCB 状态只允许在 Apply 成功 Stage 后才变 STAGED；Apply 失败必须
  保持 CONFIRMED）。复核：BCB 写入仅发生在 `OTA_PackageApplyStaging` 成功后的
  staging 提交路径；Apply 失败 → `InvalidateCandidate()`，不写 BCB。
- 离线闸门不过 → 不碰硬件。
- 产品行为观测 1/1 限额；产品前失败可当场修重试。
- 红线全清单见派工书；未 commit/push。
