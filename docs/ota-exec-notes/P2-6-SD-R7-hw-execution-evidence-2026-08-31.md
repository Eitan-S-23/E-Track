# P2-6-SD-R7 硬件链执行证据：FULL 上传补发 + D1/D2/D3 只读判别（2026-08-31）

- 会话：R7 实现 agent（授权来源：`P2-6-BR-20260830-SD-R6-01` §2.2 / §2.3 / §3.3）
- 证据根：`.cache/p2-6-sd-r7-20260831-01-implementation/`（全新目录，启动前已确认不存在）
- 动作序列：S1 FULL 上传补发 `1/1` → S2 D1 读 BCB 双块 → S3 D2 全量读回 candidate payload
  → S4 D3 读 fw_header。四步按任务书顺序执行，全部完成，无失败停机点。
- 本文档只报事实，不写"验收通过"；验收由非实现会话执行。

## 0. 执行环境

| 项 | 值 |
|---|---|
| 冻结测试 ELF | `.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf`，SHA-256 `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`（与 R5 轮一致，未重建） |
| 板卡基准镜像 | `X-Track-App-GCC-p2-6a-test-v2.8.0.finalized.bin`，SHA-256 `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5` |
| FULL 资产 | `.cache/p2-6-sd-ota/assets/P2-6A-FULL-v2.8.1.etu`，282367 B，SHA-256 `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7` |
| 离线前置 | `python tests/ota/test_p2_6_rtt_sd_uploader.py` → `Ran 10 tests ... OK`（硬件启动前） |
| J-Link | 板载 J-Link，`C:\Users\SU\SEGGER\JLink_V818`，SWD 1000 kHz，设备全名 `AT32F435RGT7` |

## 1. S1：FULL 上传补发 1/1 —— PASS

**命令**（bash；`--mcu-path` 用 MSYS 双斜杠 `//` 防路径转换，harness 收到单斜杠 `/`）：

```
python tests/ota/p2_6_rtt_sd_uploader.py \
  --input=.cache/p2-6-sd-ota/assets/P2-6A-FULL-v2.8.1.etu \
  --mcu-path=//P2-6A-FULL-v2.8.1-R7-20260831-01.etu \
  --output-prefix=p2-6-sd-r7-full-upload-hw-01 \
  --log-dir=.cache/p2-6-sd-r7-20260831-01-implementation/logs \
  --tmp-dir=.cache/p2-6-sd-r7-20260831-01-implementation/tmp \
  --timeout=600
```

**退出码 0**。关键实测（result.json + gdb.log）：

| 判据 | 实测 |
|---|---|
| MCU 落盘路径 | `/P2-6A-FULL-v2.8.1-R7-20260831-01.etu`（R5 用的是 `-R5-` 名，目标不存在，`target_absent probe_res=12`） |
| 上传字节数 | 282367 B（9 chunk：8×32768 + 20223） |
| 读回 SHA-256 | `readback.bin` 282367 B = `84D3F384…D2E7`，`readback_matches=true`，逐 chunk MI 读回 828 块全对齐 |
| transport | `PASS`（gdb_exit=0、server 自然退出、端口清零、无 session_error） |
| PASS 标记 | `P2_6_SD_UPLOAD PASS bytes=282367 chunks=9` 恰 1 次 |
| 运行态 | before/after 均 `sd=1 vtor=0x08010000 cfsr=0 owner=0`，`bcb=4`（CONFIRMED，boot 回滚后契约态） |

产物：`logs/p2-6-sd-r7-full-upload-hw-01-{result.json,gdb.log,jlink-server.log,rtt.raw.log}`、
`tmp/p2-6-sd-r7-full-upload-hw-01/{upload.gdb,mcu-path.bin,readback.bin,source-00*.bin×9}`。

- result.json SHA-256 `F51CC45B8E5521F655DE4E5ACEDF4A870B2621F6EDD507ED2C2EB86499380864`（72370 B）
- gdb.log SHA-256 `1667132C44ACEA84BC88115FC6C007ECF294480BE0E734E14BC8A63FCB666993`（621930 B）
- upload.gdb SHA-256 `17210F85E3E036067CED76B5FE24434184AAC9FD055CA3CC0E471519A16C273C`

R5 那次 FAIL（GDB 41，harness 前置缺陷）保持已消耗记录不抹除；本轮为 §3.3 授权的补发 `1/1`。

## 2. S2：D1 读 BCB 双块 —— PASS（四字段全部命中期望）

**方法**：GDB 会话（`target remote` → `monitor halt` → 紧跟 `monitor WriteU32 0xE0042008 0x00001000` →
thbreak `HAL::HAL_Update()` 0x08040884 确定性停点），受控调用
`HAL::EEPROM_ReadBufferSafe(reg, buf, len)`（0x08040C51）两次，把 EEPROM BCB-A(0x00)/BCB_B(0x40)
各 64 B 读入 OTA overlay 缓冲 0x20058000/0x20058040 —— **该缓冲是本轮唯一 target RAM 写**；
随后 `dump binary memory` 192 B 落盘。另调用 `bcb_is_valid()`（0x08012101）对双块做合法性判定。

命令：`python .cache/p2-6-sd-r7-20260831-01-implementation/tmp/run_d1.py`（复用
`p2_6_rtt_ota_driver.run_gdb_session` 启动 JLinkGDBServerCL + arm-none-eabi-gdb -batch），
脚本 `tmp/r7-d1-bcb.gdb`。退出码 0，`transport_classification=PASS`。

GDB 标记（`logs/r7-d1-bcb-gdb.log`）：

```
P2_6_R7_D1 stop_verified pc=0x08040884
P2_6_R7_D1 read_a_rc=1
P2_6_R7_D1 valid_a=1
P2_6_R7_D1 valid_b=0
P2_6_R7_D1 arbiter=-1
P2_6_R7_D1 dump_done
```

原始 dump：`logs/d1-bcb-raw.bin`（192 B，SHA-256 `628E05D4480A50892EB888C26BAF8A131F50B3C7DA4D3E0A7EFACE98583A1A4C`；
[0:64]=BCB_A、[64:128]=BCB_B、[128:192]=仲裁输出区）。

**BCB_A 逐字段解析**（`bcb_t` 小端，`Libraries/EEPROM/eeprom_bcb.h:53-72`）：

| 字段 | off | 实测值 | 期望值（R5 candidate ETSL 头） | 判定 |
|---|---|---|---|---|
| magic | 0 | `0x43425445`（"ETBC"） | — | 合法 |
| schema_ver | 4 | 1 | — | 合法 |
| state | 5 | 4（CONFIRMED） | — | boot 回滚后契约态 |
| seq | 8 | 752 | — | — |
| **cand_addr** | 12 | **0x00001000** | 0x00001000 | **相等** |
| **cand_len** | 16 | **600744**（0x92AA8） | 600744 | **相等** |
| **cand_crc32** | 20 | **0x53E81862** | 0x53E81862 | **相等** |
| **cand_vcode** | 24 | **20801**（0x5141） | 20801 | **相等** |
| cur_vcode | 28 | 20800（0x5140） | — | v2.8.0 |
| backup_len/crc32/vcode | 32/36/40 | 600744 / 0x53E81862 / 20800 | — | — |
| crc32（存） | 60 | 0x7E8C74EA | 复算 zlib.crc32(off0..59) = 0x7E8C74EA | **一致** |

**BCB_B**：magic=`f5ad8999`（非 ETBC）、CRC 复算不符 → 非法块；按契约 §3.2 单合法取 A，
与 `OTA_GetBcbState()`=4 一致。

**D1 结论**：BCB `cand_*` 四字段与 candidate ETSL 头**全部相等**，**未命中**
`boot_state_machine.c:207-214` 的 BCB 否决点。

登记一处 harness 瑕疵（不影响数据）：脚本里 `bcb_arbiter` 受控调用误传 NULL hal 指针，返回
`-1`（BCB_ARBITER_ERROR）——该次调用只读且失败返回，无副作用；仲裁结论已由 `bcb_is_valid`
双块判定（A 合法/B 非法）覆盖。A 块 64 B 数据来自独立受控调用读回 + CRC 复算一致，可信。

## 3. S3：D2 全量读回 candidate payload —— PASS（CRC32/SHA-256 双双命中）

**方法**：按 R19 已证明的分块 dump 模式（`monitor halt` → `monitor WriteU32 0xE0042008 0x00001000`
→ `monitor ExcludeFlashCacheRange 0x90001000,0x00092AA8` → `set may-write-memory off` /
`set may-call-functions off` → `set remote memory-read-packet-size 256 fixed`），对 XIP 窗口
`[0x90001000, 0x90001000+600744)` = `[0x90001000, 0x90093AA8)` 以 4 KB 块 `dump binary memory`
147 块（末块 2728 B），全程单次 halt、WDT 已暂停。

命令：`python .cache/p2-6-sd-r7-20260831-01-implementation/tmp/run_d2.py`，脚本
`tmp/r7-d2-cand.gdb`。退出码 0，`transport_classification=PASS`。

GDB 标记：`attached_stopped`、147 条 `DUMP_EXPECTED`、`DUMP_ALL_DONE chunks=147`。

产物：`logs/d2-chunk-000.bin … d2-chunk-146.bin`（147 块，总 600744 B，逐块字节数全对）。

**复算结果**（宿主拼接 147 块后）：

| 判据 | 实测 | 期望 | 判定 |
|---|---|---|---|
| 总字节数 | 600744 | 600744 | 相等 |
| CRC32（zlib） | `0x53E81862` | `0x53E81862`（candidate ETSL 头 crc） | **相等** |
| SHA-256 | `A2D3083B25EE32813EFF6CC1BD0CF77CE235FD03BF79947C08B8A3C815D58E00` | `A2D3083B…D58E00`（权威 v2.8.1 镜像） | **相等** |

拼接镜像落盘：`logs/d2-candidate-payload-full.bin`（600744 B，SHA-256 同上）。
**即：candidate 槽 payload 区完整保有权威 v2.8.1 镜像，boot 的全量 CRC 校验在数据上本就会通过。**

## 4. S4：D3 读 fw_header —— PASS（三字段全部命中期望）

fw_header 位于 candidate payload 偏移 0x400（外部 flash 0x90001400），已包含在
`d2-chunk-000.bin` 内：`[0x400, 0x400+96)`。提取落盘 `logs/d3-fw-header.bin`
（96 B，SHA-256 `B528761F65753BE578FF2F16317F8812F069CA9311102C7DD542B51F051A4339`），
与权威镜像 `X-Track-App-GCC-p2-6a-test-v2.8.1.finalized.bin` 自身 [0x400,0x460) **逐字节一致**。

按 `boot/src/boot_fw_header.c` 的 `FW_*_OFF` 契约偏移解析：

| 字段 | off | 实测 | 期望 | 判定 |
|---|---|---|---|---|
| magic | 0 | "ETFW" | — | 合法 |
| header_version | 4 | 1 | — | 合法 |
| **image_len** | 36 | **600744** | 600744 | **相等** |
| **version_code** | 8 | **20801**（0x5141） | 20801 | **相等** |
| **image_sha256[:8]** | 40 | **9db3c649** | 0x9DB3C649（ETSL sha8） | **相等** |
| version_name | 12 | "2.8.1" | — | 一致 |
| image_sha256 全 32 B | 40 | `9db3c649b80e82c6…5e067` | 权威镜像 header 同字段 | 一致 |

## 5. D1/D2/D3 对照总表

| 判别 | 否决点（boot_state_machine.c） | 实测 | 结论 |
|---|---|---|---|
| D1 BCB cand_* 四字段 | :207-214 | 四字段全部与 ETSL 头相等 | **不触发** |
| D2 payload 全量 CRC32 | :165-189 链 | CRC32=0x53E81862 且 SHA-256=权威镜像 | **不触发** |
| D3 fw_header 校验 | :195-201 | len/vcode/sha8 全等，且 header==权威镜像 | **不触发** |

boot 的 STAGED 分支三道否决（ETSL 头解析 → payload 全量 CRC32 → fw_header + BCB cand_* 对照）
中，本轮可测的后两道在当前板卡数据上**均不会触发**；ETSL 头扇区已被 R5 实验 5 销毁
（R6 裁定书 §2.3 已登记），该第一道否决当前必然触发，属已知板卡状态，不是本轮新结论。

## 6. 会话写入与边界自查

- 硬件动作：S1 一次 FULL 上传 GDB 会话（写 SD 文件，授权路径）；D1/D2 各一次只读 GDB 会话
  （halt + WDT 暂停 + 受控读调用 + dump）。无复位、无烧录、无 apply、无 BCB 写、无 QSPI 写/擦。
- target 写：仅 D1 的 RAM 缓冲 0x20058000..0x200580BF（128 B BCB 双块 + 仲裁输出区，任务书授权）；
  S1 的 SD 文件写属 uploader 授权路径。
- 产物全部位于 `D:\github\my\E-Track\.cache\p2-6-sd-r7-20260831-01-implementation\`；
  项目外仅 `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` mtime 副作用（driver 既授权范围，
  result.json `outside_repo_writes` 如实登记）。
- 生产源码、boot 源码、冻结契约、R5/R14/R15 证据根、P2-6 正式状态：零改动。
- 配额：FULL 上传补发 `1/1` 本轮消耗（PASS）；R5 原 FAIL 记录保留。未动 FULL OTA / 异常退出 /
  LiveMap 配额。
- 未 commit/push；收口由主会话执行。

## 7. 中断与重试登记（如实）

- S1 首两次启动失败于宿主参数层：bash 直接传 `--mcu-path /P2-6A-…` 时 MSYS 把参数转换为
  Windows 路径（`D:/…` 前缀），被 harness 路径校验拒绝，`P2_6_RTT_SD_UPLOAD=FAIL MCU path must
  be absolute...`。两次均**未启动硬件**（uploader 在 validate_mcu_path 即退出，无 J-Link 会话）。
  改用 MSYS 惯例 `//` 前缀（`--mcu-path=//P2-6A-…`）后正常。此为宿主调用环境适配，非 harness
  或产品缺陷。
- D2 首次 GDB 会话失败（gdb_exit=1，`Bad format string, non-terminated '"'`）：生成器把 `\n`
  写成了真实换行截断 printf 格式串。已 halt + WDT 暂停但**未执行任何 dump**（0 块写出），无
  target 写、无读数据。修正转义后同脚本重跑成功。该次失败会话日志已删除重写（残留仅日志文件，
  无数据产物）；此处如实登记共两次 D2 会话启动。
- D1 的 `bcb_arbiter` NULL-hal 调用瑕疵见 §2。
