# P2-5 backup 自拷与 STAGED 提交 —— 研究设计（2026-08-02）

> 状态：实现会话 Claude / 2026-08-02 认领 P2-5 后落盘。本文为编码前研究结论，
> 只记录设计、复用点、边界与风险；不修改任何冻结契约（`PLAN-OTA.md`、
> `docs/ota-binary-contracts.md` 只读）。

## 1. 范围与边界

- 基线：`origin/main=614a3fc759768c4e00764e9b6e254574b93d89f0`（Merge PR #1:
  P2-4 SD firmware import flow）。worktree `E-Track-p2-5-20260801`，分支
  `p2-5-20260801`。
- 本卡片做 P2-5。**不重新实现/验收 P2-3/P2-4**；P2-4 已正式收口（`P2-4 完成`、
  P2 进度 `4/6`）。不实现 P2-6（RAM 峰值回填）、不实现 P3、不实现 P1-6
  断电矩阵；不修改既有 Boot 状态机（`boot/src/boot_state_machine.c` 只读）。
- 已冻结契约相关条款（引用不复制）：
  - `PLAN-OTA.md` §4 状态机末段：
    “当前版自拷 backup(读回 CRC)→BCB=STAGED→提示重启　/　[App] 自检过
    (HAL 全初始化+主循环 30s+IWDG 喂狗正常)→写 BCB=CONFIRMED”；
    “TEST_BOOT 期间 App 拒绝发起新 OTA”；“backup 槽锁定：STAGED→CONFIRMED
    期间不得重写 backup；下轮升级自拷仅在 CONFIRMED 态允许”。
  - `docs/ota-binary-contracts.md`：
    - §0.4 槽地址：`EXT_CANDIDATE=0x000000`、`EXT_BACKUP=0x100000`、
      `SLOT_HEADER_SIZE=0x1000`；`FW_HEADER_OFFSET=0x400`，
      `FW_HEADER_SIZE=96`。
    - §4.1 外部槽头 ETSL(32B, 小端)：`slot_type` 1=candidate 2=backup，
      `commit_marker=0x434F4D54`（擦除态 0xFFFFFFFF 未提交）。
    - §4.3 擦写序(marker-last)：槽头扇区先擦（marker 保持 0xFF）→ payload
      → 其余头字段写读回 → **commit_marker 最后单独写**（禁止复用旧 marker）。
    - §3.1 BCB：`cand_addr/cand_len/cand_crc32/cand_vcode/cur_vcode/
      backup_len/backup_crc32/backup_vcode`；`boot_try` 初 3；
      `state=1 STAGED`；`copy_phase/resume_block`。
    - §3.4：backup 槽锁定；STAGED→APPLYING 原子写 由 boot 完成（本卡不写）。
    - §5.7 状态码 `0x0E ERR_BUSY`：TEST_BOOT 期间拒绝新 OTA。
    - §1.1/§1.2 fw_header 96B + 校验依赖消解（SHA 双零法 / header_crc 前92B）。
    - §0.5 image_len≤0xF0000（candidate/backup 净 1MB-4KB≥960KB）。

## 2. 现状核对（实读代码，非猜测）

### 2.1 P2-4 落地边界（本卡上游）

- `OtaUpdate::Session`（`USER/App/Utils/OtaUpdate/OtaUpdate.cpp`）：
  `InitializeDevice()` 读当前内部 App fw_header 得 `current_vcode/image_len/
  base_image_sha8`；`Inspect()→Begin()→Step()→Apply()`。
  `Apply()` 调 `HAL::OTA_PackageApplyStaging`（full）或
  `HAL::OTA_PatchApplyStaging`（patch）→ **只合成并校验 candidate**，
  返回 `OTA_PACKAGE_OK/OTA_PATCH_OK` 即止。成功边界停在“CANDIDATE READY”，
  不写 BCB。
- `HAL::OTA_PackageApplyStaging`（`USER/HAL/HAL_OTA_Package.cpp`）：
  `candidate_prepare()` 把 candidate 槽头扇区+payload 区全部擦除；
  `candidate_program()` 用 `qspi_data_write` 把 payload 写在
  `EXT_CANDIDATE+SLOT_HEADER_SIZE` 之后（`+0x1000` 对齐）；`candidate_read()`
  走 XIP。**该路径不写 candidate 槽头 ETSL、不写 commit_marker** ——
  candidate 槽头（marker-last）写入属于本卡。
- `FirmwareUpdate` 页（`USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp`）：
  `FinishImport(true)` 显示 `TXT_READY("已就绪")` +
  `workDetailLabel="CANDIDATE READY"`，不提示重启 —— 本卡改为 STAGED 提交
  读回成功后才显示成功并提示重启。

### 2.2 boot 消费端（本卡产出必须被 boot 接受）

`boot/src/boot_state_machine.c`（只读，不可改）：

- `BCB_STATE_STAGED` → `validate_external_source(SOURCE_CANDIDATE)`：
  ① ETSL magic=ETSL + `commit_marker==0x434F4D54` + type==1 + pad==0xFF×3
  + `payload_len∈(0, OTA_APP_LENGTH]`（`boot_slot.c`）；② payload 全镜像
  **CRC32==slot.payload_crc32**；③ candidate `fw_header` 全项校验
  (`boot_fw_header_validate`)；④ `header.image_len==slot.payload_len &&
  header.version_code==slot.version_code &&
  header.image_sha256[:8]==slot.sha8`；⑤ 与 BCB 交叉核对
  `cand_addr==EXT_CANDIDATE+0x1000 && cand_len==slot.payload_len &&
  cand_crc32==slot.payload_crc32 && cand_vcode==slot.version_code`。
  校验不过 → 进 ROLLBACK（这就是“STAGED 提交错误会被 boot 打回”的兜底）。
- `BCB_STATE_ROLLBACK` → `validate_external_source(SOURCE_BACKUP)`：
  ETSL type==2 + `backup_len>0 && backup_len==slot.payload_len &&
  backup_crc32==slot.payload_crc32 && backup_vcode==slot.version_code`。
  因此 backup 槽头 ETSL 的 `payload_len/payload_crc32/vcode/sha8` 必须与
  BCB 的 `backup_*` 完全一致，且 `payload_len` = 升级前当前 App `image_len`。

结论：**candidate 槽头 ETSL 与 backup 槽头 ETSL 都必须由 App 按 §4.3
marker-last 写入，且字段与 BCB STAGED 记录逐项一致。**

### 2.3 可复用实现（禁止重造）

| 已有 | 位置 | 本卡用途 |
|---|---|---|
| `bcb_arbiter`/`bcb_commit`/`bcb_serialize`/`bcb_crc32` | `Libraries/EEPROM/eeprom_bcb.{c,h}` | BCB 仲裁+原子提交 |
| `bcb_hal_t` 注入二端口 | `HAL_EEPROM.cpp::bcb_app_hal` | App 侧 EEPROM |
| `boot_crc32`/`boot_sha256`/`boot_fw_header_validate[_ex]` | `boot/src/*.{c,h}` | 全镜像 CRC/SHA/fw_header 校验（App 已链接） |
| QSPI 安全 API `qspi_erase`/`qspi_data_write` + XIP 门 | `Libraries/W25Q128/qspi_cmd_en25qh128a.{h,cpp}` | backup 槽擦/写（生产区间策略已拒越界/自检区） |
| XIP 直读当前 App | `USER/App/Utils/OtaUpdate/OtaUpdate.cpp::CurrentImageRead` / `HAL_OTA_Package.cpp::base_read` | 自拷源 |
| `ota_confirm_test_boot` | `Libraries/OTA/ota_confirm.h` | CONFIRMED 原子提交+读回校验 |
| `HAL::OTA_ConfirmBoot` | `USER/HAL/HAL_EEPROM.cpp` | App 确认入口（本卡保持复用） |
| 主循环 `OTA_ConfirmUpdate` | `USER/main.cpp` | 确认门（本卡补健康条件） |
| boot 侧 ETSL 读（语义镜像） | `boot/src/boot_slot.c`（只读参考） | 本卡写端字段布局对号 |

### 2.4 需要注意的现状（真机事实）

- 当前板上生产 App 为 finalized v2.8.0(20800)（P2-4 收口回刷），boot 在板
  （STAGED→CONFIRMED 由 P1-3..P1-5 真机验证过）。
- `USER/App/Version.h` 编译常量是 `v2.7`(20700)，但权威版本在 fw_header；
  真机升级目标包必须由 `etu_pack.py --finalize` 产生 > 20800 的合法镜像。
- App 侧目前**不喂 WDT**：`boot_platform_watchdog_start()` 在 TEST_BOOT 用
  `reload=1561`/`DIV_256` 起动独立看门狗，但 `SystemInit/HAL` 均未使能 LICK
  （AT32 WDT 的时钟源），P1-3 能 30s 无喂狗确认成功即因 WDT 计数器实际未
  走。本卡“IWDG 正常”的判据论证见 §5.3。

## 3. 设计

### 3.1 新模块（纯 C、宿主可测）

**`Libraries/OTA/ota_slot_header.{c,h}`** —— ETSL 槽头的**写端**（boot 读端
不动）：

- `ota_slot_header_t`（与 `boot_slot_header_t` 字段同构）；`serialize()` 按
  §4.1 逐字段小端手填（禁 struct memcpy），`parse()` 供读回自检与宿主断言。
- `OTA_SLOT_MARKER_COMMIT 0x434F4D54u`、`OTA_SLOT_MARKER_ERASED 0xFFFFFFFFu`。

**`Libraries/OTA/ota_backup.{c,h}`** —— 核心提交事务：

```
typedef struct ota_backup_io_t {
    void *ctx;
    int (*app_read)(void *ctx, uint32_t offset, uint8_t *dst, uint32_t len);   // XIP 当前 App
    int (*flash_read)(void *ctx, uint32_t addr, uint8_t *dst, uint32_t len);
    int (*flash_erase_4k)(void *ctx, uint32_t addr);
    int (*flash_program)(void *ctx, uint32_t addr, const uint8_t *src, uint32_t len);
} ota_backup_io_t;

typedef struct ota_backup_info_t {
    uint32_t candidate_len; uint32_t candidate_crc32; uint32_t candidate_vcode;
    uint8_t  candidate_sha8[8];
    uint32_t backup_len;    uint32_t backup_crc32;    uint32_t backup_vcode;
    uint8_t  backup_sha8[8];
    uint32_t erase_count;   uint32_t program_count;   // 供宿主断言副作用
} ota_backup_info_t;

/* 返回 OTA_BACKUP_OK 或 OTA_BACKUP_ERR_*（见头文件）；失败保证：
 * 不提交 BCB=STAGED，活动 BCB 始终仍为 CONFIRMED。 */
ota_backup_result_t ota_backup_stage(const ota_backup_io_t *io,
                                     const bcb_hal_t *bcb_hal,
                                     ota_backup_info_t *out);
```

执行步骤（顺序即冻结契约）：

1. **fail-closed 仲裁**：`bcb_arbiter`。`BCB_ARBITER_ERROR`(I/O) →
   `ERR_EEPROM`；非 A/B → `ERR_EEPROM`；`state != CONFIRMED`
   （含 TEST_BOOT/STAGED/APPLYING/ROLLBACK）→ `ERR_STATE`。
   此步**任何 QSPI/EEPROM 零写入**（拒绝矩阵 §4.1）。
2. **读取并验证当前内部 App fw_header**（XIP，`app_read`）：`boot_fw_header_validate_ex`
   全项 + `image_len∈[0x400+96, OTA_APP_LENGTH]` + 槽界
   `EXT_BACKUP+0x1000+image_len ≤ EXT_BACKUP+0x100000`。得
   `backup_len/image_sha256/backup_vcode`。
3. **复核 candidate 全镜像**：XIP 读 candidate payload 逐块算
   `candidate_crc32`；读 candidate `fw_header` 全项校验；核对
   `header.image_len==candidate 读数 && header.vcode`；且
   `candidate_crc32` 与包目标 `target_vcode` 对应（candidate ETSL/BCB 用）。
   任一步失败 → `ERR_CANDIDATE_*`，零擦除零提交。
4. **擦 backup 槽头扇区**（`EXT_BACKUP`，marker 保持 0xFF）+ **擦 backup
   payload 区**（`EXT_BACKUP+0x1000 .. +0x1000+image_len` 按 4KB）→
   `flash_erase_4k` 失败 → `ERR_ERASE`。
5. **分块自拷**：固定 4KB 块缓冲（静态，非 malloc），`app_read` 源 →
   `flash_program`（`qspi_data_write` 安全 API），每块写后
   `flash_read` 逐字节比对；全程累计 CRC32。失败 → `ERR_WRITE/ERR_READBACK`。
6. **写 backup ETSL 头字段**（magic/type=2/pad/payload_len/crc/vcode/sha8）
   → 写后读回比对。失败 → `ERR_SLOT_HEADER`。
7. **写 backup `commit_marker`**（最后单独写）→ 读回比对。
8. **写 candidate ETSL 头字段** → 读回比对；**再单独写 candidate
   `commit_marker`** → 读回比对。
9. **复核双槽**：对 candidate、backup 各按 boot 判据（§2.2）复核：
   ETSL magic+marker+type+pad+长度 + payload CRC + fw_header 元数据一致性。
10. **原子提交 STAGED**：构造 `bcb_t{state=STAGED, tail_try 初3, copy_phase=0,
    resume=0, cand_addr=0x1000, cand_len, cand_crc32, cand_vcode,
    cur_vcode=当前版, backup_len, backup_crc32, backup_vcode}`，
    `bcb_commit(active, &next)`；随后 `bcb_arbiter` 读回，
    `state==STAGED && cand_* 与 backup_* 逐字段一致` → `OTA_BACKUP_OK`；
    否则 `ERR_COMMIT/ERR_VERIFY`（活动块可能已半写，二次仲裁兜底，
    状态仍非 CONFIRMED 时上层拒绝继续）。

`boot_try` 取值说明：boot 在 STAGED→APPLYING 原子写时自置 0，并在
APPLYING→TEST_BOOT 时自置 3；APP 提交 STAGED 时 §3.1 语义“初 3”，故写 3。
（已验证 boot 在 STAGED 分支不使用 boot_try，此值不影响 boot 行为。）

### 3.2 App 侧接线

- `HAL_OTA_Package.cpp`（或新增 `HAL_OTA_Backup.cpp`）暴露
  `HAL::OTA_BackupStage(bcb_hal_t*, ota_backup_info_t*)`：填充 `ota_backup_io_t`
  （`base_read` 风格 XIP 读 + QSPI 擦/写/读 + XIP 门），转发
  `ota_backup_stage`。复用 `g_ota_package_port` 计数或新增独立计数供取证。
- `OtaUpdate::Session` 新增 `ota_sd_result_t Stage()`：要求
  `transfer.phase==COMPLETE` 且已成功 `Apply()`；调
  `HAL::OTA_BackupStage`；返回 `OTA_SD_OK` 或映射失败。success 语义
  改为 **STAGED 读回成功**，原先的“CANDIDATE READY”不再代表整项成功。
- `FirmwareUpdate.cpp`：
  - `RunWorkStep()`：`applyPending → FinishImport(updater.Apply())` 改为
    `Apply()` 成功后进入 `STAGING BACKUP` 阶段（progress 96，detail
    "BACKUP + STAGED"），再 `Stage()`；`Stage()` 失败 → `FinishImport(false)`。
  - `FinishImport` 成功文案：`TXT_STAGED_READY`（“已就绪，请重启”，须查
    `font_cn_16.c.chars`）+ detail `"STAGED COMMIT OK"`，与“适合重启”语义。
  - 模拟器 `_WIN32`：`Stage()` 与 `Apply()` 一样短路成功（RAM 桩无真实
    QSPI/EEPROM），保证 UI 可截图；真实逻辑靠宿主测试 + 真机覆盖。
- 生产入口保持 `manager.Push("Pages/Startup")` 唯一；不引入
  `P2_5_TEST`/临时页面/自动 reset/harness。

### 3.3 App 确认门（TEST_BOOT→CONFIRMED）

新增 `Libraries/OTA/ota_confirm_health.{c,h}`（纯 C 健康门，宿主可测）：

```
typedef struct ota_confirm_health_t {
    uint32_t window_ms;    // 30_000
    uint32_t min_loops;    // 30
    uint32_t retry_ms;     // 1000
    uint32_t start_ms; bool start_valid;
    bool hal_ready; bool headers_verified;
    uint64_t loop_count; uint32_t feed_count; uint32_t last_attempt_ms;
} ;
void ota_confirm_health_init(h, now_ms);
void ota_confirm_health_mark_hal_ready(h);        // setup() 结尾调用
void ota_confirm_health_tick(h, now_ms, loop_ok); // 每圈 loop 调用
void ota_confirm_health_feed(h);                  // 每次喂狗计数
bool ota_confirm_health_due(h, now_ms, bool wdt_configured); // 全部条件满足
bool ota_confirm_health_retry_ok(h, now_ms);
```

- `USER/main.cpp` 编排（复用现有 `OTA_ConfirmUpdate` 骨架）：
  - `setup()` 结尾 `g_ota_hal_ready=true`；`main()` 里健康门窗口起点仍为
    setup 之后（现代码位置），并初始化健康模块。
  - `loop()`：每圈 `tick`；若处于 TEST_BOOT（启动仲裁缓存状态）则每次
    `HAL::OTA_WatchdogFeed()`（`wdt_counter_reload()`）并 `feed()`。
  - 确认时机：`due()`（30s + hal_ready + loop_count≥min + `wdt_configured`
    + feed_count>0）且 `retry_ok`（≥1s 间隔）→ `HAL::OTA_ConfirmBoot()`；
    失败继续保持 TEST_BOOT、按 1s 间隔重试（现有 `OTA_CONFIRM_RETRY_MS`）。
- `HAL::OTA_WatchdogFeed()`/`HAL::OTA_WatchdogIsConfigured()`：
  `HAL_EEPROM.cpp` 或新 HAL 文件。`IsConfigured` 读
  `WDT->div==WDT_CLK_DIV_256 && WDT->rld==1561`（boot 起动值）。
- 掩码结果映射：`ota_confirm_test_boot` 失败 rc 已含 `ERR_COMMIT/ERR_VERIFY`，
  直接复用；`CONFIRMED 已存`时幂等返回（`OTA_CONFIRM_ALREADY_CONFIRMED`）。

## 4. 拒绝矩阵与副作用保证

### 4.1 拒绝矩阵（宿主测试断言）

| 前置状态/故障 | ota_backup_stage 结果 | QSPI 擦除 | QSPI 写 | BCB 写 |
|---|---|---|---|---|
| BCB=TEST_BOOT/STAGED/APPLYING/ROLLBACK | ERR_STATE | 0 | 0 | 0 |
| BCB 双坏（NONE） | ERR_EEPROM | 0 | 0 | 0 |
| EEPROM I/O 失败 | ERR_EEPROM | 0 | 0 | 0 |
| 当前 App fw_header 无效/越界 | ERR_APP_HEADER | 0 | 0 | 0 |
| candidate 全镜像复核失败 | ERR_CANDIDATE_* | 0 | 0 | 0 |
| backup 擦除失败 | ERR_ERASE | 部分 | 0 | 0 |
| backup 写失败 | ERR_WRITE | 部分 | 部分 | 0 |
| backup 读回失败 | ERR_READBACK | 部分 | 部分 | 0 |
| backup 槽头写/读回失败 | ERR_SLOT_HEADER | 部分 | 部分 | 0 |
| candidate 槽头/marker 失败 | ERR_SLOT_HEADER | 部分 | 部分 | 0 |
| BCB commit 失败 | ERR_COMMIT | 部分 | 部分 | 0 |
| BCB readback 不一致 | ERR_VERIFY | 部分 | 部分 | 半写（无 STAGED） |

所有失败后：活动 BCB 保持 CONFIRMED（或半写块无 marker → 下一轮 CONFIRMED
升级会整槽重擦重写，符合 marker-last 语义）。

### 4.2 marker-last 调用序

`ota_backup_stage` 对 candidate 与 backup 均保证：槽头扇区擦除(marker 0xFF)
→ payload → 头字段 → **marker 单独最后写**。宿主测试用指令拦截记录顺序，
并验证半写 backup（差一步未写 marker）时 `flash_read` 端解析 ETSL 失败
（marker 仍 0xFF）→ 整槽无效 → 不产出 STAGED。

## 5. 风险与决策留痕

1. **WDT/LICK 微妙点**（§2.4）：AT32 WDT 时钟源 LICK 当前未使能，WDT 计数器
   实际不走。本卡**不修改系统时钟初始化**，避免给既有真机行为引入复位风暴；
   “IWDG 正常”按“boot 已按 reload1561/DIV_256 起动 WDT（寄存器可读）+ App
   每圈喂狗（feed 计数>0）+ WDT 未复位打断 30s 窗口”判据。若 LICK 未来使能，
   喂狗每圈执行即兜底。是否使能 LICK 列入 P5-2 注错矩阵评估。
2. **candidate 复核强度**：STAGED 前对 candidate 做“CRC + fw_header 全项 +
   元数据一致性”复核（等价 boot 判据，无骗过可能）；不重复拷入候选体。
3. **`boot_try=3` 取值**：STAGED 记录按契约“初 3”；boot 不依赖，后续自置。
4. **不触碰 Boot 状态机**：若在编码中发现必须改 `boot_state_machine.c` 或
   冻结契约才可实现 → 卡置阻塞 + §9 登记，停止。
5. **复用优先**：ETSL 写端在 App 侧新开 `ota_slot_header.c`，boot 读端
   `boot_slot.c` 保持零改动（避免 P1 回归）；两份代码只共享布局宏
   （`ota_layout.h`）。
6. **宿主测试夹具**：复用 `tests/ota-vectors/toy-new.bin`（4096B、合法
   finalized fw_header、vcode 20800）作为当前 App 与 candidate 样本；
   板级真实镜像用于真机。

## 6. 实施清单（参照，非契约）

1. `Libraries/OTA/ota_slot_header.{c,h}`、`ota_backup.{c,h}`、
   `ota_confirm_health.{c,h}` 新增。
2. `Libraries/EEPROM/`、`boot/` 零改动。
3. `USER/HAL/HAL_OTA_Package.cpp`（或新 HAL）接 `HAL::OTA_BackupStage` + WDT
   喂/检测。
4. `USER/App/Utils/OtaUpdate/OtaUpdate.{cpp,h}` 增 `Stage()`；
   `USER/App/Pages/FirmwareUpdate/FirmwareUpdate.cpp` 增 阶段与重启提示。
5. `USER/main.cpp` 健康门接线（不改 `ota_confirm.h`）。
6. 宿主测试 `tests/ota/test_ota_backup.c` + `test_ota_confirm_health.c`
   + Python 驱动；重跑全部既有回归。
7. 构建 GCC App/Boot、AC5 App、模拟器；模拟器真实 Startup 两次启动。
8. 真机 SD 升级闭环（STAGED→APPLYING→TEST_BOOT→CONFIRMED RTT 全程）；
   TEST_BOOT 窗口内发起 OTA 被拒无副作用；最终复查 BCB/内部 fw_header/
   backup 与升级前一致。

（本文件为研究记录，不含实现结论；实现后另行落盘证据文档。）