# P2-6-SD-R8 硬件链执行证据：FULL 闭环（Apply→Stage→复位→boot 消费）+ C1/C4/C5/C6/C14 FULL 侧 + C7（2026-08-31）

- 会话：R8 实现 agent（授权来源：本轮任务书"新增授权"——允许固件自身 OTA 路径执行
  Apply→Stage→复位→boot 消费，含随之发生的 QSPI candidate 槽写入与 EEPROM BCB 写入）
- 证据根：`.cache/p2-6-sd-r8-20260831-01-implementation/`（启动前写入预检确认原不存在，
  路径链无 reparse point，位于项目根内）
- 动作序列：S0 修正版 BCB 双块 preflight → S1 FULL 上传 → S2+S3 FULL Apply+Stage（含测量采集）
  → S4 复位观测 boot 消费链 → S5 C7（LiveMap 基线 / 升级发起失败 / 重建恢复）
- 本文档只报事实，不写"验收通过"；验收由非实现会话执行。

## 0. 执行环境

| 项 | 值 |
|---|---|
| 冻结测试 ELF | `.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf`，SHA-256 `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`（与 R5/R7 一致，未重建） |
| 板卡起始基线 | test v2.8.0（fw_header vcode=20800，image_len=600744），BCB=CONFIRMED(4) |
| FULL 资产 | `.cache/p2-6-sd-ota/assets/P2-6A-FULL-v2.8.1.etu`，282367 B，SHA-256 `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7`（输入侧复算一致） |
| 关键符号（本轮 nm 重取） | `HAL::HAL_Update()`=0x08040884、`HAL::EEPROM_ReadBufferSafe`=0x08040C50、`bcb_is_valid`=0x08012100、`bcb_arbiter`=0x08012138、`HAL::OTA_GetBcbHal()`=0x08040CC4、`bcb_app_hal`=0x0809CB0C、`HAL::OTA_GetBcbState()`=0x08040CCC、`_SEGGER_RTT`=0x20053E1C、`SD_IsReady`=0x20053214、`g_ota_overlay_owner`=0x20053FA0、`g_ota_overlay_workspace`=0x20058000、`PageManager::Push`=0x0803DB94、`PageManager::Pop`=0x0803D98C |
| J-Link | 板载 J-Link，`C:\Users\SU\SEGGER\JLink_V818`，SWD 1000 kHz，设备全名 `AT32F435RGT7` |

每个硬件会话沿用受控停点模式：`monitor halt` → `monitor WriteU32 0xE0042008 0x00001000`（WDT 暂停）
→ thbreak `HAL::HAL_Update()` 确定性停点 → 受控调用后校验 `$pc==0x08040884`。

## 1. S0：修正版 BCB 双块 preflight —— PASS

**R7 遗留缺陷的四处修正全部落实**：

1. 读前把 192 B 缓冲（0x20058000..0x200580BF）整段清零（48×u32 循环写 0），防止
   overlay 里的上传残留被误读为 EEPROM 内容；
2. `HAL::EEPROM_ReadBufferSafe` 返回 bool（1=成功），放行条件改为 `rc==1`，非 1 即
   `quit 84/85` 停止（R7 的 `if $ra == 0` 方向反了）；
3. **无条件**读 B 块并打印独立 `read_b_rc` 行（A/B 各自 rc 行）；
4. `bcb_arbiter` 传真实 `bcb_hal_t`：受控调用 `HAL::OTA_GetBcbHal()` 取回
   `$hal=0x0809cb0c` 并校验 == `bcb_app_hal` 符号地址后再传参（R7 传 NULL 返回 -1）。

命令：`python .cache/p2-6-sd-r8-20260831-01-implementation/tmp/run_s0.py`（复用
`p2_6_rtt_ota_driver.run_gdb_session`），脚本 `tmp/r8-s0-bcb.gdb`。退出码 0，
`transport_classification=PASS`。

GDB 标记（`logs/r8-s0-bcb-gdb.log`）：

```
P2_6_R8_S0 IDENTITY PASS magic=ETFW vcode=20800 image_len=600744
P2_6_R8_S0 STATE PASS sd=1 vtor=0x08010000 cfsr=0x00000000 owner=0
P2_6_R8_S0 bcb_state=4
P2_6_R8_S0 buffer_zeroed bytes=192
P2_6_R8_S0 read_a_rc=1
P2_6_R8_S0 read_b_rc=1        ← B 块本轮真实读取（R7 从未读到）
P2_6_R8_S0 valid_a=1
P2_6_R8_S0 valid_b=1           ← 真实 B 块合法（R7 的 valid_b=0 系残留误读）
P2_6_R8_S0 hal_ptr=0x0809cb0c  ← 真实 bcb_app_hal
P2_6_R8_S0 arbiter=1           ← BCB_ARBITER_A（R7 为 -1）
P2_6_R8_S0 dump_done bytes=192
```

**BCB 双块逐字段**（`logs/s0-bcb-raw.bin` 192B，SHA-256
`0E0A1449201BDCA028E91B1083C90464AD041A158E6D3FB820348A56A0E7C1F3`；
[0:64]=A、[64:128]=B、[128:192]=仲裁输出）：

| 字段 | BCB_A（活动块） | BCB_B |
|---|---|---|
| magic | `0x43425445`（"ETBC"） | `0x43425445`（"ETBC"） |
| state | 4（CONFIRMED） | 5（ROLLBACK） |
| copy_phase | 0 | 2（ROLLBACK 搬运） |
| seq | **752** | 751 |
| resume_block | 0 | 147 |
| cand_addr | 0x00001000 | 0x00001000 |
| cand_len | 600744 | 600744 |
| cand_crc32 | 0x53E81862 | 0x53E81862 |
| cand_vcode | 20801 | 20801 |
| cur_vcode | 20800 | 20800 |
| backup_len/crc32/vcode | 600744 / 0x53E81862 / 20800 | 同 A |
| crc32 复算（zlib off0..59 vs off60） | 0x7E8C74EA **一致** | 0x66CC6CC3 **一致** |

仲裁（真实 hal）：`arbiter=1`（A），A/B seq 差 `(int16)(752-751)=1>0` 取新者 A，与
`OTA_GetBcbState()=4` 一致。仲裁输出区字段与 A 块一致（仅 pad[12] 差异：deserialize
清零 vs 原始块 0xFF，属结构性差异非数据差异）。

**对 R7 结论的更正**：R7 报告的"BCB_B magic=f5ad8999 非法、CRC 不符"实为
`if $ra == 0` 缺陷导致 B 块从未被读、0x20058040 处是 overlay 残留垃圾；真实 B 块是
合法的 ROLLBACK 残留（seq=751、resume_block=147，R5 PATCH OTA 复位后 boot 回滚的
中间态写块）。**S0 结论不受影响**（R7 的 D1 四字段对照使用的是 A 块数据，仍然有效）。

## 2. S1：FULL 上传 1/1 —— PASS

命令（bash，`--mcu-path` 用 MSYS `//` 前缀防路径转换）：

```
python tests/ota/p2_6_rtt_sd_uploader.py \
  --input=.cache/p2-6-sd-ota/assets/P2-6A-FULL-v2.8.1.etu \
  --mcu-path=//P2-6A-FULL-v2.8.1-R8-20260831-01.etu \
  --output-prefix=p2-6-sd-r8-full-upload-hw-01 \
  --log-dir=.cache/p2-6-sd-r8-20260831-01-implementation/logs \
  --tmp-dir=.cache/p2-6-sd-r8-20260831-01-implementation/tmp \
  --timeout=600
```

| 判据 | 实测 |
|---|---|
| MCU 落盘路径 | `/P2-6A-FULL-v2.8.1-R8-20260831-01.etu`（R8 专用新路径，`target_absent probe_res=12`） |
| 上传字节数 | 282367 B（9 chunk：8×32768 + 20223），全部 `res=0` |
| 读回 SHA-256 | `readback.bin` 282367 B = `84D3F384…D2E7`，`readback_matches=true` |
| transport | PASS（gdb_exit=0、server 自然退出、端口清零、无 session_error） |
| PASS 标记 | `P2_6_SD_UPLOAD PASS bytes=282367 chunks=9` 恰 1 次 |

产物：`logs/p2-6-sd-r8-full-upload-hw-01-{result.json,gdb.log,jlink-server.log,rtt.raw.log}`、
`tmp/p2-6-sd-r8-full-upload-hw-01/`（upload.gdb、readback.bin、source-00*.bin×9）。
result.json SHA-256 `09CE8AB6ECA39A2FDD75DA5DA6A2D9A08712C241CD90EFF10CE6AD78311799E3`（72370 B）。

## 3. S2+S3：FULL Apply 测量采集 + 固件自动 Stage —— 全链闭合

命令（`MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1` 防路径转换；
`--prepare-only` 先行验证路径原样到达后正式执行）：

```
MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1 python tests/ota/p2_6_rtt_ota_driver.py \
  --kind FULL --package-path=/P2-6A-FULL-v2.8.1-R8-20260831-01.etu \
  --output-prefix=p2-6-sd-r8-full-ota-hw-01 \
  --log-dir=.cache/p2-6-sd-r8-20260831-01-implementation/logs \
  --tmp-dir=.cache/p2-6-sd-r8-20260831-01-implementation/tmp \
  --timeout=480
```

退出码 0。两段式 RTT 采集闭合（derive ELIGIBLE → logger 逐字节 → postcheck 仅 RdOff
变化 → `rtt_channel_binding_verified=true`），恰 1 条 FULL 测量记录。

### 3.1 导入流程标记（`logs/p2-6-sd-r8-full-ota-hw-01-gdb.log`）

```
P2_6_IDENTITY PASS label=before_ota_fw header_bytes=96        （v2.8.0 / vcode=20800）
P2_6_STATE PASS label=before_ota sd=1 vtor=0x08010000 cfsr=0x00000000 bcb=4 owner=0
P2_6_RTT_DRIVER push_ok=1 / page_ready state=3 / row_index=10
P2_6_RTT_DRIVER confirm mode=1 kind=FULL
P2_6_RTT_DRIVER import_started mode=2
P2_6_IDENTITY PASS label=after_ota_fw header_bytes=96
P2_6_STATE PASS label=after_ota sd=1 vtor=0x08010000 cfsr=0x00000000 bcb=1 owner=0
P2_6_RTT_DRIVER result mode=3
P2_6_RTT_DRIVER PASS kind=FULL page_state=3 mode=3
```

before BCB=4（CONFIRMED）→ after BCB=**1（STAGED）**、owner=0、sd/vtor/cfsr 全部正常。

### 3.2 C1/C4/C5/C6/C14 FULL 侧实测（RTT 测量行，`logs/p2-6-sd-r8-full-ota-hw-01-rtt-payload.raw.log`）

```
P2_6 kind=full result=0 workspace_peak=33016 arena_peak_observed=33016
  failed_request_size=0 stack_entry=3496 stack_peak=3496 stack_total=8192
  guard_entry=1 guard_exit=1 sbrk_delta=0 sbrk_peak=537221444
  tlsf_malloc_delta=0 tlsf_realloc_delta=0 tlsf_free_delta=0
  lv_free_entry=63616 lv_free_exit=63616
  lv_big_entry=59900 lv_big_exit=59900
  lv_frag_entry=6 lv_frag_exit=6
  lv_max_entry=64667 lv_max_exit=64667
```

| 判据 | 实测 | 门禁 | 判定口径（供验收会话核对） |
|---|---|---|---|
| **C1** workspace_peak | **33016 B** | ≤ 40960 B | 占 80.6%，余 7944 B |
| **C1** arena_peak_observed | 33016 B（=workspace_peak，成功路径） | — | 与 §4.7 一致 |
| **C4** guard | entry=1 / exit=1，32B guard intact | guard 破损即 PRODUCT_FAIL | intact |
| （顺带）stack_peak | 3496 B ≤ 8192 B | 栈门禁（C3 线） | 有效测量 |
| **C5** sbrk_delta | 0 | 增量必须为 0 | sbrk_peak=537221444（历史水位，0x2005_0000 量级堆顶） |
| **C6** tlsf_malloc_delta | 0 | 必须 0 | |
| **C6** tlsf_realloc_delta | 0 | 必须 0 | |
| **C6** tlsf_free_delta | 0（交叉核对项） | 非 0 须定位释放点 | 为 0，无需定位 |
| **C14** LVGL 池四字段 | free 63616→63616、biggest 59900→59900、frag 6→6、max_used 64667→64667 | 净状态不变（佐证） | 全部相等 |

### 3.3 S3：candidate ETSL 槽头已被固件 Stage 流程重写（修复 R5 越权擦除）

只读 GDB 会话（`tmp/r8-s3-candhdr.gdb`，`monitor ExcludeFlashCacheRange`×2 均被 J-Link
接受，`set may-write-memory off`）dump candidate 槽头扇区 [0x90000000, 0x90001000)。

`logs/s3-cand-slot-header.bin`（4096 B，SHA-256 `E83A86AE8E939941F2B955850ED84EFF52AC17050585E5507F79A44055F341B4`）
按契约 §4.1 ETSL 32B 解析：

| 字段 | off | 实测 | 交叉对照 |
|---|---|---|---|
| magic | 0 | `"ETSL"` | 合法 |
| slot_type | 4 | 1（OTA_SLOT_TYPE_CANDIDATE；byte=0x01 + pad 0xFF×3） | 合法 |
| payload_len | 8 | 600744 | = BCB cand_len = fw_header image_len |
| payload_crc32 | 12 | 0x53E81862 | = BCB cand_crc32 = R7 D2 复算值 |
| version_code | 16 | 20801 | = BCB cand_vcode |
| sha8 | 20 | `9db3c649b80e82c6` | = fw_header.image_sha256[:8]（R7 D3） |
| commit_marker | 28 | 0x434F4D54（"COMT"） | **已提交**（marker-last 完整走完） |

**R5 越权 `qspi_erase(0x0)` 抹掉的槽头已被本轮固件导入流程自动重写并提交**，未做任何
手工补写。staging 槽头扇区（0x90030000）dump 内容与 ETSL 布局不匹配（非本轮判据，
如实登记，不作判据使用）。

## 4. S4：复位观测 boot 消费链 —— 决定性闭合（D1/D2/D3 的最终回答）

复位：JLink Commander `r`→`g`（21:14:02，`logs/r8-s4-reset.log`）。

### 4.1 第一次观测（复位后约 110 s，`tmp/r8-s4-obs1.gdb` / `logs/r8-s4-obs1-*`）

| 项 | 实测 |
|---|---|
| App slot fw_header | magic=0x57465445（ETFW）、**vcode=20801**、image_len=600744 |
| 运行态 | pc=0x0802a870（App 区）、vtor=0x08010000、cfsr=0 |
| App 侧快照 | `g_ota_state_snapshot=4`（CONFIRMED）、`g_ota_confirm_done=1` |
| RTT | 签名有效（WrOff=284 RdOff=0，全部为复位后新输出） |

RTT 环内容（`logs/s4-obs1-rtt-ring.bin` 前 284 B）：

```
OTA: HANDOFF vtor=0x08010000 primask=0 basepri=0 faultmask=0 control=0 ...
Reset: NRST SW
QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled
OTA: TEST_BOOT confirmed vcode=20801
```

### 4.2 第二次观测（升级后 BCB 双块终态，`tmp/r8-s4-obs2.gdb`）

`logs/s4-obs2-bcb-raw.bin`（192 B，SHA-256 `B75390AF6D3AD0F80832C00D5DF1BFF654B06E1425EA865289FF73C42C15FD82`）：

| 字段 | BCB_A（活动块） | BCB_B |
|---|---|---|
| state | 4（**CONFIRMED**） | 3（**TEST_BOOT**） |
| seq | **904** | **903** |
| cur_vcode | **20801** | 20800 |
| cand_* / backup_* | 与升级前一致（cand_vcode=20801、crc=0x53E81862） | 同 |
| crc32 复算 | 一致 | 一致 |
| 读取 rc / valid / 仲裁 | read_a_rc=1 read_b_rc=1 valid_a=1 valid_b=1 arbiter=1（真实 hal） | |

### 4.3 boot 消费链结论

**boot 接受并消费了 candidate**。完整证据链：

1. 复位前（S2/S3 后）：BCB=STAGED、candidate ETSL 头已提交、payload/fw_header 三道
   否决数据在 R7 已证相等、BCB cand_* 四字段相等（S0 复核）；
2. 复位后：**App slot vcode 20800→20801**（boot 把 candidate 写入 App slot）；
3. EEPROM 留痕：seq 752→903（boot 写 TEST_BOOT 至 B 块）→904（App 确认写 CONFIRMED
   至 A 块，cur_vcode=20801）——STAGED→APPLYING→TEST_BOOT→CONFIRMED 状态迁移
   在双块上完整留痕；
4. RTT 行 `OTA: TEST_BOOT confirmed vcode=20801`（App 在 TEST_BOOT 态执行确认动作，
   非"already CONFIRMED"幂等路径）；
5. App 运行 v2.8.1，sd=1、vtor=0x08010000、cfsr=0、owner=0，无 WDT/HardFault。

**对 R5"复位后未升级"的最终定界**：boot/固件消费链本身无缺陷；R5 现象的根因即
R6 裁定所载——R5 自己越权 `qspi_erase(0x0)` 抹掉了 candidate ETSL 槽头扇区，使
boot 第一道否决（ETSL 头解析）必然触发。本轮固件自动重写槽头后，boot 一次消费成功。

## 5. S5：C7 —— 升级失败后 overlay 释放 / LiveMap 重新初始化 / 地图正常显示

RTT 下行命令通道在该 test 构型不可用（`CONFIG_RTT_DEBUG_CMD_ENABLE=0`，P2-5 交付态，
ELF 无 `RttDebugCmd_Poll` 符号）——**用 GDB 受控调用等效替代并如实登记**：
`gpsreset` ≡ 直写 `gpsSimulator.state`（`ResetToDefault` 被 -O2 内联无符号，
SimState 布局按头文件手算：baseLon@0/baseLat@8/baseAlt@16/curLon@24/curLat@32/curAlt@40/
course@48，DEFAULT=104.88393/26.56854/50.0）；`livemap` ≡ `PageManager::Push("Pages/LiveMap")`；
`back` ≡ `PageManager::Pop()`。

### 5.1 S5-A：LiveMap 正常基线

复位（21:27:52）→ 等 App 起来 → 会话 A2（`tmp/r8-s5-a-baseline2.gdb`）：
GPS 复位（写前后坐标打印：curLon 104.880541→104.883930）→ `push_ok=1`（LiveMap
进入前台）→ **`livemap_owner=1`（OTA_OverlayAcquireLiveMap 成功，LiveMap 持有 overlay）**。

RTT logger 32 s（`logs/s5-a-livemap-baseline.rtt.log`，4593 B）：**38 条统计行**，
`lineHit` 2-312/秒、`lineMiss` 0-42、`sdMs` 0-38、`refrMs` ~200 ms——地图正常显示基线。

**第一次 Push 尝试被产品 USB MSC gate 拒绝**（`push_ok=0`，会话 A `r8-s5-a-baseline.gdb`）：
`IsLiveMapBlockedByUsbMsc` = name 匹配 + `USB_IsMassStorageOnSD()`（MSC_USE_SD_CARD
编译期恒真）+ `USB_IsPlugged()`（当时 USB CONFIGURED）。这是真实产品 fail-closed
行为（USB MSC 期间 SD 独占、LiveMap 禁入），如实登记。A2 会话复测时
`usb_plugged_before=0`（Windows 侧已离开 CONFIGURED），并调用正规 API
`usbd_disconnect()`（0x08018E77，拉 D+ 软断开，模拟拔线语义）后 Push 成功。
两次会话之间 USB 状态由 CONFIGURED 变为非 CONFIGURED 的确切时点未追踪（如实登记）。

### 5.2 S5-B：升级发起失败（Inspect 版本关 fail-closed）

会话 `tmp/r8-s5-b-patchfail.gdb`：LiveMap 前台（`before owner=1 bcb=4`）→
`Push("Pages/FirmwareUpdate")` 成功（`push_ok=1`）→ `EnterPath("/")` → 行扫描找到
R5 PATCH 包（`row_index=4`）→ `SelectRow(4)` → **`confirm mode=0`：Inspect 阶段被
版本关拒绝**（`ota_sd.c:312`：`target_vcode(20801) <= current_vcode(20801)` →
`OTA_SD_ERR_VERSION`），升级未发起，mode 保持 BROWSER。

**"升级中途失败"的形态限制（如实登记）**：当前板卡 vcode=20801 与 SD 上**全部现存
冻结包**（R5 PATCH / R7 FULL / R8 FULL / P2-5 系列，target 均=20801）相同，
`ota_sd.c:312` 的 Inspect 版本关使任何包都无法进入 Begin/staging 写入/Apply 阶段；
"进入 WORKING 后失败"（例如 base mismatch 在 `ota_patch.c:337` 触发）需要
target>current 的包，现存资产中没有，制新包超出本轮授权。因此 C7 的"升级失败"以
"升级发起被产品版本关 fail-closed 拒绝"呈现。OTA 持有 overlay 的中途快照
（owner=PACKAGE）未能采样：S2 成功导入未插桩中途读（R8 任务书未要求），
S5-B 失败发生在 Inspect（先于 `ota_patch.c:1168` 的 workspace_acquire）。
拔 SD 卡物理注错（真实升级中途异常）需用户物理配合，未执行。

### 5.3 S5-C：失败后恢复链（overlay 释放 → 取消 → LiveMap 重建）

会话 `tmp/r8-s5-c-recover.gdb`：

```
P2_6_R8_S5C fail_state mode=0 owner=0   ← 升级发起失败后 owner=0（LiveMap 已释放 overlay）
P2_6_R8_S5C pop_ok=1                    ← 取消升级流程（Pop 返回）
P2_6_R8_S5C owner_mid=1                 ← Pop 恢复栈中的 LiveMap：重新 acquire（重新初始化）
P2_6_R8_S5C gps_reset_done curLon=104.883930 curLat=26.568540
P2_6_R8_S5C push_ok=0                   ← 多余的重复 Push 被产品 "multi push" 保护正确拒绝
```

恢复链证据：LiveMap 在栈中（S5-A2 Push）→ FirmwareUpdate 压栈时 LiveMap
onViewDidUnload 释放（`fail_state owner=0`，动画完成后的稳定终态）→ Pop 取消升级 →
LiveMap onViewWillAppear 重新初始化并 acquire overlay（`owner_mid=1`）。随后的重复
`Push("Pages/LiveMap")` 被 `FindPageInStack` 拒绝（产品防重入保护，顺带验证）。

RTT logger 32 s（`logs/s5-c-livemap-recover.rtt.log`，4571 B）：**41 条统计行**，
`lineHit` 8-311/秒、`lineMiss` 0-23、`refrMs` ~200 ms——与基线一致水平，
**LiveMap 重建后地图正常显示**。

## 6. 验收矩阵交付（判据ID | 实测值(带单位) | 原始证据文件路径）

证据根 = `.cache/p2-6-sd-r8-20260831-01-implementation/`，下表路径相对该根。

| 判据ID | 实测值 | 原始证据文件路径 |
|---|---|---|
| S0 BCB-A | ETBC / state=4(CONFIRMED) / seq=752 / cand_addr=0x1000 / cand_len=600744 B / cand_crc32=0x53E81862 / cand_vcode=20801 / 块内 CRC32 复算一致(0x7E8C74EA) | logs/s0-bcb-raw.bin + logs/r8-s0-bcb-gdb.log |
| S0 BCB-B | ETBC / state=5(ROLLBACK) / seq=751 / copy_phase=2 / resume_block=147 / cand_* 同 A / 块内 CRC32 复算一致(0x66CC6CC3)；read_a_rc=1 read_b_rc=1（双读成功） valid_a=1 valid_b=1 arbiter=1（真实 hal，A 活动） | logs/s0-bcb-raw.bin + logs/r8-s0-bcb-gdb.log |
| S1 FULL 上传 | 282367 B / 9 chunk / 读回 SHA-256=84D3F384…D2E7 与输入逐字节相同 / PASS 标记恰 1 次 | logs/p2-6-sd-r8-full-upload-hw-01-result.json |
| C1（FULL 侧）workspace_peak | 33016 B（≤40960 B，占 80.6%） | logs/p2-6-sd-r8-full-ota-hw-01-rtt-payload.raw.log + …-result.json |
| C1（FULL 侧）arena_peak_observed | 33016 B（=workspace_peak，成功路径） | 同上 |
| C4 guard | guard_entry=1 guard_exit=1（32B guard intact）；stack_peak=3496 B ≤ 8192 B | 同上 |
| C5 sbrk | sbrk_delta=0（apply 窗口零调用）；sbrk_peak=537221444 | 同上 |
| C6 tlsf | malloc_delta=0 realloc_delta=0（门禁）；free_delta=0（交叉核对） | 同上 |
| C14 LVGL 池四字段 | free 63616→63616 B、biggest 59900→59900 B、frag 6→6%、max_used 64667→64667 B（净状态不变） | 同上 |
| S3 candidate ETSL 头 | ETSL / type=1(CANDIDATE) / len=600744 / crc32=0x53E81862 / vcode=20801 / sha8=9db3c649b80e82c6 / marker=0x434F4D54 已提交（R5 越权擦除已由固件自动修复） | logs/s3-cand-slot-header.bin + logs/r8-s3-candhdr-gdb.log |
| S3 BCB | after_ota bcb=1(STAGED)、owner=0（driver 全门禁 PASS，rtt_channel_binding_verified=true） | logs/p2-6-sd-r8-full-ota-hw-01-result.json |
| S4 boot 接受 candidate | App slot fw_header vcode 20800→20801（复位后实读） | logs/r8-s4-obs1-gdb.log |
| S4 BCB 状态迁移 | STAGED(S2 后)→TEST_BOOT(B 块 seq=903 state=3)→CONFIRMED(A 块 seq=904 state=4 cur_vcode=20801)；双块 CRC 复算一致；arbiter=1 | logs/s4-obs2-bcb-raw.bin + logs/r8-s4-obs2-gdb.log |
| S4 复位后版本 | vcode=20801（v2.8.1）运行中；RTT 行 `OTA: TEST_BOOT confirmed vcode=20801`；sd=1 vtor=0x08010000 cfsr=0 owner=0 | logs/s4-obs1-rtt-ring.bin + logs/r8-s4-obs1-gdb.log |
| C7 overlay 释放 | 升级发起失败后 owner=0（LiveMap 已释放；fail_state mode=0 owner=0） | logs/r8-s5-c-recover-gdb.log |
| C7 LiveMap 重新初始化 | Pop 取消升级后 owner=1（LiveMap 重新 acquire；重复 Push 被产品防重入拒绝） | logs/r8-s5-c-recover-gdb.log |
| C7 地图正常显示 | 重建后 41 条统计行（32 s）：lineHit 8-311/秒、lineMiss 0-23、refrMs ~200 ms（与基线 38 条/lineHit 2-312 一致） | logs/s5-c-livemap-recover.rtt.log + logs/s5-a-livemap-baseline.rtt.log |

本轮产物总清单与逐文件 SHA-256：`result.json`（89 文件 / 2717848 B，
自身 SHA-256 `AA6D1259D790CDCEAD2FD5D7E01CE25B0D779A41B25B2B9DFC5BBD98B83B9BBE`）。

## 7. 没做到 / 如实登记项

1. **"升级中途失败"的形态降级**：以"升级发起被 Inspect 版本关（ota_sd.c:312）
   fail-closed 拒绝"呈现，未进入 Begin/staging/Apply（当前板卡 v2.8.1 与全部现存
   包 target=20801 相同；无 target>current 的包，制新包超授权）。
2. **OTA 持有 overlay 的中途快照（owner=PACKAGE）未采样**（S2 未插桩中途读；
   S5-B 失败先于 workspace_acquire）。
3. **拔 SD 卡物理注错**（真实升级中途异常）需用户物理配合，未执行。
4. **RTT 下行命令不可用**（test 构型 `CONFIG_RTT_DEBUG_CMD_ENABLE=0`）：gpsreset/
   livemap/back 均以 GDB 受控调用等效替代（GPS state 直写 / PageManager Push/Pop）。
5. **第一次 Push LiveMap 被 USB MSC gate 拒绝**（真实产品行为）；A2 会话时 USB 已
   自然离开 CONFIGURED（`usb_plugged_before=0`），另调 `usbd_disconnect()` 正规 API
   软断开（语义=模拟拔线）。USB 状态变化的确切时点未追踪。
6. **staging 槽头 dump（0x90030000）内容与 ETSL 布局不匹配**，未查明语义，不作判据。
7. S5-C 会话脚本的"Push LiveMap 应成功"期望错误（quit 127）：LiveMap 已被 Pop 恢复
   在前台，重复 Push 被产品正确拒绝；板上状态不受影响，恢复链观测已完成。
8. 空中残留观察：s5-a 基线日志中 1 行统计行被 RTT 环回绕截断（"updaLiveMap
   stat:…"，1024B 环形缓冲已知现象），其余 38 行完整。

## 8. 会话写入与边界自查

- 硬件动作：S0/S3/S4obs/S5 各 GDB 会话（halt + WDT 暂停 + 受控调用 + dump）；
  S1 一次 FULL 上传（写 SD 文件，授权路径）；S2+S3 一次 FULL OTA 导入（固件自身
  OTA 路径：写 staging、写 candidate 槽、自拷 backup、写 EEPROM BCB——本轮任务书
  新增授权范围）；S4 一次复位（r+g）+ S5 一次复位（r+g）；两次 RTT logger 采集
  （各 32 s，启动前清残留、单实例、带超时、事后确认无残留）。
- target 写清单：S0/S4obs2 的 192B overlay 缓冲（清零+BCB 读入+仲裁输出，任务书授权）；
  S5 的 gpsSimulator.state 直写（gpsreset 等效）；S5-A2 的 usbd_disconnect 受控调用
  （产品 API，软断开）；S1 的 SD 文件写与 S2+S3 的固件自身 OTA 写（QSPI/EEPROM，
  本轮新增授权）；S5-B 的 FirmwareUpdate 页面驱动（产品路径）。
- 项目外写入：仅 `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` mtime 副作用
  （driver 既授权范围，各 result.json 如实登记）。
- 生产源码、boot 源码、冻结契约、门槛数字（40960B/8192B/16KiB）、R5/R7 证据根：
  零改动。未做 GDB 手工写 QSPI、未手工改 BCB、未 qspi_erase、未改任何门槛数字。
- 配额：FULL 上传 R8 `1/1`（PASS）；FULL OTA（Apply→Stage）本轮新增授权下执行
  （成功）；复位×2；C7 失败导入 `1/1`（发起失败形态）。R7 的 FULL 上传补发记录
  保持不变。
- 未 commit/push；收口由主会话执行。
