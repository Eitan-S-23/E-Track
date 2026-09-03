# P3-2 执行证据：实现物与 host 测试验证

日期：2026-09-03 ｜ 记录人：P3-2 实现 agent
设计依据：`docs/ota-prompts/prompt-P3-2-implementation.md`（冻结派工书）、
`docs/ota-exec-notes/P3-2-identity-research.md`（编码前研究）。

## 1. 实现物清单

| 文件 | 状态 | 内容 |
|---|---|---|
| `Libraries/OTA/ota_device_info.h` | 新增 | 设备身份链接口：`ota_device_info_t` 值对象、`ota_device_identity_t` 快照状态（诊断字段）、`ota_device_result_t` 错误码、`ota_device_identity_get()` |
| `Libraries/OTA/ota_device_info.c` | 新增 | 实现：fw_header 完整校验（含向量）→ 全镜像 raw SHA-256（256B 块增量）→ 字段填充（fw_header 实值 + `BOOT_VERSION` + 冻结 model）→ 每次调用 BCB 仲裁（ERROR fail closed）。纯只读 |
| `USER/HAL/HAL_Bluetooth.cpp` | 修改 | 占位身份链替换为 `s_ble_identity` 快照 + `ble_current_image_read`（内部 Flash 镜像读）；`ble_env_info_provider` / `ble_env_get_device` 同源取数（get_device 的 `base_image_sha8` = raw SHA 前 8B，.etu 比较域） |
| `MDK-ARM_F435/cmake-generated/CMakeLists.txt` | 修改 | `APP_PROJECT_SOURCES` 列表追加 `Libraries/OTA/ota_device_info.c` |
| `MDK-ARM_F435/proj.uvprojx` | 修改 | OTA 组追加 `ota_device_info.c`（FileType 1）/ `.h`（FileType 5） |
| `tests/ota/test_ota_device_info.c` | 新增 | host 单元测试（T1-T8，见 §3） |
| `tests/ota/test_ota_device_info.py` | 新增 | 编译运行器（链接真实源，gcc/MSVC 双路径） |

未修改：`boot/**`、`Libraries/OTA/ota_ble_*`（P3-1 资产）、
`USER/App/Utils/OtaUpdate/OtaUpdate.cpp`（P2 已收口资产，等价行为，
迁移建议见 research 笔记 §7）、冻结契约文档。

## 2. 关键实现决策（与 research 笔记 §4/§5 一致）

- **摘要域**：`info.image_sha256` = 全镜像 `[0, image_len)` 原始字节
  SHA-256（raw 域）；fw_header.image_sha256 双零域仅用于 header 校验，
  两域不互换。`ble_env_get_device` 的 `base_image_sha8` 取 raw 前 8B
  （.etu `base_sha8` 比较域，OTA-XC-IMAGE-IDENTITY）。
- **字段权威**：model = 冻结常量 `"E-Track\0"`；hw_rev / layout_id /
  cur_vcode = 校验通过的 fw_header 实值；boot_ver = `BOOT_VERSION`
  编译期常量（fw_header 只存 min_boot_ver 下界）。
- **BCB 语义**：仲裁 A/B/NONE 均放行（身份权威在 fw_header，§3.2
  「镜像真伪始终以 fw_header SHA 为准」；BCB.cur_vcode stale 以
  fw_header 为准）；仅仲裁 ERROR（EEPROM IO 失败）fail closed。
- **快照**：fw_header 校验 + raw SHA（约百毫秒级）结果缓存于
  `s_ble_identity`；运行期 App 无法改写自身 Flash，重启 RAM 清零
  天然失效；BCB 仲裁每次调用重跑（轻量 EEPROM 读 128B）。
- **fail closed**：任一步失败返回负错误码且 `*out` 不写入（部分
  有效不得生成 INFO）；无 0.0.0 / 全零 SHA / 编译期版本回落。

## 3. host 测试执行证据

命令（仓库根 `D:\github\my\E-Track`）：

```
python tests/ota/test_ota_device_info.py
```

输出：

```
P3_2_OTA_DEVICE_INFO checks=114 failures=0
P3_2_OTA_DEVICE_INFO_ALL=PASS
```

退出码 0。链接真实源：`Libraries/OTA/ota_device_info.c` +
`boot/src/boot_fw_header.c` + `boot/src/boot_crc32.c` +
`boot/src/boot_sha256.c` + `Libraries/EEPROM/eeprom_bcb.c`，
编译 `gcc -std=c99 -Wall -Wextra -Werror -O2`（本机 gcc，0 警告）。

### 3.1 用例覆盖（114 断言）

| 组 | 断言数 | 覆盖 |
|---|---|---|
| ANCHOR | 44（22 次锚定 × 2） | golden 实文件原始字节与 `tests/ota-vectors/expected.json` 逐字节锚定（file_sha256 + fw_header.image_sha256 两域分别锚定），证明与 CI/Tools 同 fixture |
| T1 | 12 | 正例全字段：model 精确 8B `"E-Track\0"`、hw=1、layout=1、boot=`BOOT_VERSION`、vcode=20700、image_sha256 == 独立重算 raw SHA |
| T7 | 6 | 摘要域分离：expected.json 两域互异；设备输出 raw ≠ fixture 头内双零域；两域前 8B 互异；raw 前 8B == `.etu base_sha8` 期望（`3081fa0afc5bb2f3`，expected.json toy-patch.etu） |
| T2 | 24（8 负例 × 3） | fw_header 负例 fail closed + 诊断码 + `*out` 不写：magic / header_crc / image_sha 字段翻转 / payload 篡改 / image_len 超上界 / image_len 过小 / 向量 MSP / 向量 reset |
| T3 | 4 | 读 IO：header 读失败、payload 读失败（validate 阶段 `BOOT_FW_ERR_READ`）、raw SHA 阶段读失败（读预算=18 恰放行 validate 的 1+16+1 次读）→ `OTA_DEVICE_ERR_IMAGE_READ` |
| T4 | 9 | BCB：仅 A / B 回绕更新 / 仅 B / 双块无效 NONE 照常放行 / cur_vcode stale 以 fw_header 为准 / 每次调用重仲裁（bcb_result 刷新 A→NONE） |
| T5 | 3 | EEPROM 读失败 → `OTA_DEVICE_ERR_BCB_IO` fail closed，`*out` 不写 |
| T6 | 5 | NULL 参数负例（state/out/reader/read/bcb_hal） |
| T8 | 10 | 快照：首调 34 次镜像读（validate 18 + raw 16）；二调零额外读、输出一致；全程 EEPROM 零写；快照重置 + 换 toy-new.bin → vcode=20800、新 raw SHA |

### 3.2 golden fixture 装配约定（重要）

`tests/ota-vectors/toy-old.bin` 是 .etu/ETSL 打包向量文件，向量表
（前 8B）为占位填充字节（MSP=0xDDDCDFDE 等），不能过
`boot_fw_header_validate` 的向量检查。测试流程：

1. 加载实文件后先锚定**原始字节**：raw SHA == expected.json
   `file_sha256`、头内存储 sha == expected.json
   `fw_header.image_sha256`（与 CI/Tools 同 fixture 的逐字节证明）；
2. 再**装配合法向量表**（MSP=0x2007F000、reset=0x08010001，与
   `test_ota_backup.c` 的 build_valid_image 同款）并按双零法 refit
   头部，使镜像语义与生产固件一致；
3. 期望 raw SHA 对**装配后镜像**独立重算（`boot_sha256` 直接计算，
   与被测实现独立路径）。

两层断言合起来同时满足派工书判据「与 CI/Tools 同 fixture 逐字节
一致」与「32B 摘要与独立 host 计算逐字节一致」。

### 3.3 调试记录（第 1、2 次验证失败）

- 第 1 轮失败（31 断言红）：golden 向量表占位字节过不了向量检查
  （根因见 §3.2），改为锚定+装配两段式后通过。
- 第 2 轮失败（1 断言红）：`HDR_SHA_NEW` 数组手抄 expected.json 时
  `89` 误写为 `8a`。修正后 114/114 全绿；随后用脚本把 C 文件中全部
  5 个期望数组与 expected.json 程序级核对（`ALL_MATCH`），排除同类
  抄写错误。

### 3.4 期望数组程序级核对

命令（核对 C 源内期望数组与 expected.json）：

```
python - <<EOF  # 见会话记录；从 expected.json 读取并逐字节比对
```

输出：

```
RAW_SHA_OLD: OK (len=32)
HDR_SHA_OLD: OK (len=32)
RAW_SHA_NEW: OK (len=32)
HDR_SHA_NEW: OK (len=32)
BASE_SHA8_OLD: OK (len=8)
ALL_MATCH
```

## 4. 真机取证方案（已完成，证据见 §7）

请求帧（GET_INFO，session=0 seq=0）：
`A5 5A 00 00 00 00 00 00 10 0E`（CRC16-CCITT-FALSE=0x0E10 小端，
覆盖 cmd..payload 六字节零）。

取证路径：GCC 生产固件 finalize 后烧录，J-Link GDB 逐字节 inferior call
`ota_ble_session_feed_idle(&s_ble_session, 0, 0, <byte>)`（走生产
全路径 demux→session→provider→fw_header 校验→raw SHA→BCB 仲裁→
`session_send_info`），读 `s_ble_session.tx_frame[0..59]` 得真实
INFO 帧（60B = 8 头 + 50 payload + 2 CRC），host 解码逐字段断言 +
同固件 dump App 区独立计算 raw SHA 比对。证据见 §7。

## 5. 构建证据（GCC 生产路径 + 模拟器）

命令（仓库根）：

```
./build_f435_and_simulator.bat --no-pause
```

结果：exit code 0。CMake configure 成功，`X_Track_App_GCC` 103 步全部
编译链接成功，`X_Track_Boot` 目标 up-to-date（Boot 源未变，产物保持
2026-08-15 时间戳未重链），MSBuild 模拟器构建成功。

产物（`MDK-ARM_F435/cmake-generated/build-gcc-release/`）：

| 产物 | 时间戳 | 大小 | SHA-256 前 16B |
|---|---|---|---|
| app-gcc/X-Track-App-GCC.elf | 2026-09-03 02:37:00 | 872076 B | 0d645338529659ad |
| app-gcc/X-Track-App-GCC.hex | 2026-09-03 02:37:02 | 1694726 B | 98703397c1b5cb21 |
| app-gcc/X-Track-App-GCC.bin | 2026-09-03 02:37:02 | 602984 B | 7328c1b15feff721 |
| app-gcc/X-Track-App-GCC.map | 2026-09-03 02:37:00 | 2434214 B | 323297e54d2839ed |
| boot/X-Track-Boot.elf | 2026-08-15 00:16:19（未重链） | 36860 B | d21713ca2c1efeac |
| boot/X-Track-Boot.bin | 2026-08-15 00:16:21（未重链） | 14724 B | 5842ff3e19ba9e1e |
| Simulator/Output/Debug/x64/LVGL.Simulator.exe | 2026-09-03 02:37:29 | — | — |

`arm-none-eabi-size`：

```
   text	   data	    bss	    dec	    hex	filename
 601544	    940	 561688	1164172	 11c38c	app-gcc/X-Track-App-GCC.elf
  14720	      4	   9780	  24504	   5fb8	boot/X-Track-Boot.elf
```

FLASH 602984 B / 960 KB = 61.34%。

警告情况：**0 错误，519 条警告全部为仓库既有基线**——链接期
`uses 2-byte wchar_t yet ...` 口径警告覆盖全仓库全部对象（含未修改
的 Bluetooth.cpp、SdFat 等），编译警告集中在 ArduinoAPI/Adafruit 等
未修改库（`-Wunused-parameter`、`-Wrestrict` 等）。本卡新增/修改的
`ota_device_info.c`（[97/103] 编译成功）与 `HAL_Bluetooth.cpp` 仅
出现在上述全对象共有 wchar_t 链接警告中，**无任何编译警告**。

## 6. 静态生产符号检查（GCC App ELF）

`arm-none-eabi-nm` 结果：

```
20053008 b _ZL14s_ble_identity              ← 快照状态（BSS）
080408d8 t _ZL21ble_env_info_providerP14ota_ble_info_t
0804095c t _ZL18ble_env_get_deviceP15ota_sd_device_t
08048868 T ota_device_identity_get          ← 身份链实现（text）
```

- 测试符号泄漏检查：仅命中 `bot_scsi_test_unit`（USB MSC 生产
  SCSI 命令）与 `lv_obj_hit_test`（LVGL 生产 API），**无测试符号**。
- `k_ota_device_model` 数组被 -O2 内联进 memcpy（符号不保留），
  字符串 `"E-Track"` 落 .rodata 偏移 0x493ca（`arm-none-eabi-strings`
  确认）。

## 7. 真机取证证据（GCC 生产固件 + J-Link GDB）

### 7.1 取证固件准备（finalize 直刷镜像）

直刷 bin 在 APP+0x400 处是 0xFF 擦除态（无 fw_header），身份链按合同
fail closed。用 `Tools/etu_pack.py finalize` 回填 fw_header 生成取证镜像：

```
python Tools/etu_pack.py finalize \
  --app MDK-ARM_F435/cmake-generated/build-gcc-release/app-gcc/X-Track-App-GCC.bin \
  --out .cache/p3-2-realdevice/X-Track-App-GCC-p32.bin \
  --ver-name 3.2.0 --build-ts 1788375368 --hw-rev 1 --layout-id 1 --min-boot 1
```

镜像属性（finalize 输出 + host 独立重算核对，全部 match）：image_len=602984、
header_version=1、version_name="3.2.0"（vcode=30200）、build_ts=1788375368、
hw_rev=1、layout_id=1、min_boot_ver=1、
raw SHA-256=`4512de0878c146a93b55f65aa86acab4eedcf7f7082ead97ad73c24884671b4b`、
fw_header 双零摘要域 SHA-256 前 8B=`d97534841302c16d`（与 raw 域互异）、
header_crc32=0x8f431170（覆盖头前 92B 重算一致）；与源 bin 仅
0x400..0x45F（fw_header 96B）内 78 字节差异，其余逐字节相同。

烧录（`loadbin 0x08010000` + `verifybin`，AGENTS.md 先例命令；
CommandFile 用 Python 写，bash printf 会吃转义损坏路径）：

```
JLink.exe -Device AT32F435RGT7 -If SWD -Speed 1000 -AutoConnect 1 \
  -ExitOnError 1 -CommandFile flash-app-gcc.jlink   # O.K. verifybin
```

板上运行验证（JLink mem 读 + RTT）：向量表 MSP=0x2007F000、
reset=0x08010001；APP+0x404 处 ETFW magic、vcode=30200（0x75F8）、
build_ts=1788375368；`_SEGGER_RTT=0x20053630` 处读得
`53 45 47 47 45 52 20 52 54 54`（SEGGER RTT 签名）。固件正常
运行（LiveMap/Dialplate 正常起，RTT 统计行输出）。

### 7.2 取证链路（JLinkGDBServerCL inferior call，P2-6 先例）

GCC Release 构建无 DWARF（仅符号表），GDB call 用绝对地址强转：

```
JLinkGDBServerCL.exe -select USB -device AT32F435RGT7 -if SWD -speed 1000 \
  -port 24361 -swoport 24362 -telnetport 24364 -rtttelnetport 24363 -nogui -singlerun
arm-none-eabi-gdb -batch -x p3_2_capture.gdb   # file ELF + target remote 127.0.0.1:24361
```

符号（`arm-none-eabi-nm`，GCC ELF）：`ota_ble_session_feed_idle=0x08049b48`、
`s_ble_session=0x20053058`、`s_ble_identity=0x20053008`。
`s_ble_session` 布局（sizeof=568，对齐 8）：env 函数指针表 @0-39（send
@4）、tx_frame（142B 数组）在偏移 **421**（421+142=563，尾部 pad 5B）。

逐字节喂入 R3 请求帧 `A5 5A 00 00 00 00 00 00 10 0E`：

```
call ((void (*)(void*, void*, void*, unsigned char))0x08049b49) \
  ((void*)0x20053058, (void*)0, (void*)0, 0xA5)   # …×10 字节
dump binary memory info_frame.bin 0x200531FD 0x20053239   # tx_frame 60B
```

### 7.3 R3 轮直接观测（活固件，核心链路成立）

R3 attach 时固件活着（PC=0x08053550 in memset，固件 init 运行中）。
逐字节喂入 seq=0 GET_INFO 帧后 `P3_2_FEED_DONE`，tx_frame 出现合法
INFO 帧——设备身份链（demux→session→identity provider→fw_header 校验
→raw SHA→BCB 仲裁→encode）在生产固件上完整走通。该轮 dump 偏移
用了错误的 426（晚 5B），随后 R4 以正确偏移 421 复取。

### 7.4 R4 轮 dump 与逐字段断言（22/22 PASS）

产物（`.cache/p3-2-realdevice/`，2026-09-03）：

| 产物 | 时间戳 | 大小 | SHA-256 |
|---|---|---|---|
| X-Track-App-GCC-p32.bin（finalize 镜像） | 03:02:09 | 602984 B | `4512de08…1b4b` |
| app_dump.bin（板上 App 区 dump） | 03:05:23 | 602984 B | `4512de08…1b4b` |
| info_frame.bin（tx_frame 60B） | 03:14:28 | 60 B | `08131be3…b4c0f` |
| feed_before.bin | 03:14:28 | 60 B | `08131be3…b4c0f` |
| identity.bin（s_ble_identity 60B） | 03:14:28 | 60 B | `ffde6504…de0c5` |
| sess_full.bin（整结构 568B） | 03:14:28 | 568 B | `47495da7…0db642` |

评估命令与结果（断言集按 R3/R4 数据设计）：

```
python .cache/p3-2-realdevice/p3_2_r4_evidence_eval.py
```

```
== INFO 帧结构 ==            7/7 PASS
  60B / A5 5A / cmd=0x80 / session=0 / seq=0 / len=50 /
  CRC16-CCITT-FALSE calc=1B4F wire=1B4F（cmd..payload 自洽）
== INFO payload（设备身份链各字段）==  8/8 PASS
  model="E-Track\0" / hw_rev=1 / layout_id=1 / boot_ver=1 /
  cur_vcode=30200 / image_sha256=4512de08…1b4b / proto_ver=1 /
  max_window_segs=32
== App 区镜像与 INFO 摘要互证 ==     2/2 PASS
  板上 App 区 dump == finalize 镜像（602984B 逐字节）；
  App 区独立 raw SHA-256 == INFO.image_sha256（三方一致：
  finalize 镜像 == 板上 dump == INFO 帧内 32B 摘要）
== s_ble_identity 快照 ==           6/6 PASS
  valid=1 / model / cur_vcode=30200 / image_sha256 与 INFO 一致 /
  fw_header_result=BOOT_FW_OK(0) / bcb_result=BCB_ARBITER_A(1) 放行
== 整结构兜底 ==                    2/2 PASS
  s_ble_session 整结构 568B；INFO 帧位于偏移 421（tx_frame 字段）
P3_2_R3R4_EVIDENCE=PASS
```

完成判据覆盖：真机 INFO 的 hw/layout/boot/vcode 逐项正确且可追溯到
finalize 权威值；32B 摘要与独立 host 计算**逐字节一致**（三方）；
vcode=30200 ↔ version_name="3.2.0" 映射正确（major*10000+minor*100+patch）。

### 7.5 证据链说明与限制（如实记录）

- **新旧帧区分**：R3/R4 帧 seq=0，与更早 seq=0 帧无法用 seq 区分。
  支持「帧为 R3 轮喂入产生」的证据是过程性直接观测：R3 attach 时固件
  活（PC 在 memset）、R3 喂帧后 tx_frame 由空变为 INFO 帧、R4 dump 与
  R3 内容一致（同一帧）；R4 轮固件已死（attach PC=Reset_Handler，
  喂帧不产生新帧，before==after，符合预期），帧内容为 R3 产生的
  RAM 残留。
- **环境故障与停止重试**：R3 成功后固件 crash（PC=cm_backtrace_fault）。
  根因定位为 GDB inferior call 的副作用：`session_send_info` 末尾
  `env.send`→`ble_env_send`（`BT_SERIAL.write` UART 逐字节写）在
  GDB 环境执行后，detach 恢复运行的固件 fault。诊断轮（逐字节喂+
  观察 demux.state 0→1→2→0 完整推进、bcb_result 不刷新）证明死
  固件上帧在 CRC/dispatch 层被静默丢弃，非身份链缺陷。
- **后续取证环境阻塞**：R8-R10 三轮尝试复位固件补充 seq=0x1234
  取证（铁证设计：请求帧 `A5 5A 00 00 34 12 00 00 0B C5`，CRC=0xC50B）
  均失败于环境级故障——J-Link 复位命令（`r` 与 `RSetType 0`）挂死、
  杀挂死进程后 J-Link USB 链路死亡（GDB server 卡在
  `Connecting to J-Link...`）、PnP 软复位两次无效。物理恢复（拔插
  J-Link / 整机断电）超出 agent 自动化能力，按派工书「连续三次验证
  失败即停止」纪律停止重试。
- **R10 补证方案（已就绪待环境恢复）**：`.cache/p3-2-realdevice/
  p3_2_r10_capture.py` 已实现——喂帧前把 `env.send`（结构偏移 4）指向
  固件内 2 字节 `bx lr` 桩（`__retarget_lock_init_recursive=0x080537A8`，
  objdump 验证），encode 照常填充 tx_frame 而 UART 副作用彻底消除，
  取证后恢复原指针（`ble_env_send=0x08040BF8`）；请求改 seq=0x1234，
  decode 断言含「before 无帧头（复位后 init 清零）+ seq 回显 0x1234」
  新旧帧铁证。前置条件：物理恢复 J-Link 链路后执行该脚本。

### 7.6 AC5 构建证据（辅助路径，2026-09-03 02:44）

命令（bootstrap 全量重建，`proj.uvprojx` 变更后走
`UV4 -b` 再 `build_f435.ps1` 常规链）：

```
./MDK-ARM_F435/build_f435.ps1 -Target X-Track-App-AC5 -BootstrapIfNeeded
```

结果：`0 Error(s), 0 Warning(s)`。

```
Program Size: Code=305484 RO-data=289388 RW-data=1340 ZI-data=532896
```

产物（`MDK-ARM_F435/`，2026-09-03 02:44:49-50）：

| 产物 | SHA-256 前 16B |
|---|---|
| Objects-App-AC5/X-Track-App-AC5.axf | `83ac7ce5566a57f4` |
| Objects-App-AC5/X-Track-App-AC5.hex | `671e74e68232f6d5` |
| Track-App-AC5.bin | `15c9c380e5e166e8` |

AC5 镜像仅作工具链对照，不参与 OTA/CI 验收（AGENTS.md 规定）。
