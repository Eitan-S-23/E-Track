# P3-1 构建与验证证据（BLE 传输层）

- 日期：2026-09-02
- 作者：P3-1 实现 agent（Claude）
- 范围：`build_f435_and_simulator.bat --no-pause`（CMake configure + GCC `X_Track_App_GCC`/`X_Track_Boot` + MSBuild 模拟器）
- 前置：host 单元测试证据见 `P3-1-research-ble-transport.md` §7.3（session 105/105、frame 39/39、SD 层回归通过）

## 1. 构建命令与退出码

| 轮次 | 命令 | 退出码 | 说明 |
|---|---|---|---|
| 1（全量） | `./build_f435_and_simulator.bat --no-pause` | 0 | CMake configure + 全源编译 + 链接 + 模拟器 |
| 2（增量） | 同上 | 0 | 行尾规范化还原后重编 10 个 HAL.h 依赖者 + 重链接 |
| 3（空跑同步验证） | 同上 | 0 | `ninja: no work to do`，0 个编译步骤——证明产物与全部最终源同步 |

日志：`.claude/p3_1_build_log.txt`（全量）、`.claude/p3_1_build_log_final.txt`（增量）、`.claude/p3_1_build_log_sync.txt`（空跑，仅本地留存不入库）。

轮次 2/3 背景：Edit 工具曾把 `HAL_OTA_Package.cpp/.h`、`HAL.h` 的既有 LF 行尾规范化为 CRLF（1044+12+6 行伪变更），已用 Python 字节级脚本还原为 HEAD 行尾；`git diff` 最终仅含真实变更（HAL_OTA_Package.cpp 24 行、.h 8 行、HAL.h 3 行）。mtime 复核确认 `HAL_OTA_Package.cpp.obj`（00:20:07）与 `HAL_Bluetooth.cpp.obj`（00:19:50）均晚于其源还原时刻（00:19:09/10）——产物绑定最终源；轮次 3 空跑进一步证明 build 树无陈旧对象。

## 2. 警告/错误统计（显式申报）

- **全量构建（轮次 1）：637 行 warning，0 error。**
- **增量构建（轮次 2）：395 行 warning，0 error。**
- 本卡新源 `ota_ble_ring.c` / `ota_ble_frame.c` / `ota_ble_session.c`：**编译 0 warning 0 error**（host 测试构型 `-Wall -Wextra -Werror` 亦全绿）。
- `HAL_Bluetooth.cpp` / `HAL_OTA_Package.cpp`：编译自身 0 新增 warning；仅命中链接器 `2-byte wchar_t` 警告——该警告为**全仓库既有模式**（本轮 382 个对象命中，含 `Arduino.c`、`WString.cpp` 等纯既有文件，每对象一条）。
- `HAL.cpp` 3 条 `-Wwrite-strings`（82/85/88 行）为既有代码行（本卡仅在第 148 行区新增泵注册 4 行）。
- 其余 warning 均来自未触碰的既有源（PageFactory.h unused-parameter 22、MusicCode.h missing-field-initializers 系列等）。

## 3. arm-none-eabi-size 输出

```text
   text	   data	    bss	    dec	    hex	filename
 601432	    932	 561688	1164052	 11c314	X-Track-App-GCC.elf
  14720	      4	   9780	  24504	   5fb8	X-Track-Boot.elf
```

## 4. 产物清单（时间戳 / 大小 / SHA-256）

| 产物 | 时间戳 | 大小 | SHA-256 |
|---|---|---|---|
| `MDK-ARM_F435/cmake-generated/build-gcc-release/app-gcc/X-Track-App-GCC.elf` | 2026-09-02 00:21:39 | 867952 | `4a5f673ae775c7c72a481a44f32350a13635b168de5a954c5985e4ca74773a87` |
| `…/app-gcc/X-Track-App-GCC.hex` | 2026-09-02 00:21:39 | 1694382 | `cb6de4c884a96577cfff9dd3ee811652e01d46394e8e5ecd0a9e7191371fcef1` |
| `…/app-gcc/X-Track-App-GCC.bin` | 2026-09-02 00:21:39 | 602864 | `4c44622a7716197278a85a569ad2247cf1e0bc1816edd5c650b40b354f33e30d` |
| `…/app-gcc/X-Track-App-GCC.map` | 2026-09-02 00:21:39 | 2433909 | `057fce1c10997e8695bea43afa66fba8b738ec4adbf8010794f78bc7a50241d9` |
| `…/boot/X-Track-Boot.elf` | 2026-08-15 00:16:19 | 36860 | `d21713ca2c1efeac949f8ec0ffddacac439fed6bf26f9c65641bee24464fdabc` |
| `…/boot/X-Track-Boot.hex` | 2026-08-15 00:16:21 | 41485 | `ff3badef69be6d97fd66815b8df90efd962a708b559c8951d4b56380f8001f71` |
| `…/boot/X-Track-Boot.bin` | 2026-08-15 00:16:21 | 14724 | `5842ff3e19ba9e1eaaea10f27e825c7b6efc278b200531014b0dba61264f6594` |
| `…/boot/X-Track-Boot.map` | 2026-08-15 00:16:19 | 100450 | `14e7a8addd37dfe71744c11ab0db60d5c535fbe725fe3e950f82354f34a4fc93` |
| `Simulator/Output/Debug/x64/LVGL.Simulator.exe` | 2026-09-02 00:20:49 | 5864960 | `9952365787183701b753c3317d0b33a2f6c059d39b567dd2c020dd2b8af7300f` |

说明：**Boot 产物时间戳为 2026-08-15**——本卡未触碰任何 Boot 源，构建命令已请求 `X_Track_Boot` 目标，Ninja 判定无重编必要（同轮次 3 的 no-work 语义），故产物保持上次成功构建状态。Boot 不是本卡交付物，列于此处仅为构建矩阵完整性。

## 5. RAM 门槛红线验证（map 证据）

从 `X-Track-App-GCC.map` 核对（链接成功本身即表示全部链接断言通过）：

| 检查项 | 证据 | 结论 |
|---|---|---|
| `.ota_overlay` 尺寸断言 `SIZEOF == 0xA000` | map：`.ota_overlay 0x20058000 0xa000 load address 0x20080000` | ✅ 40960B（RX 环 4096 + staging receiver 4160 从此子分配，主 RAM 零占用） |
| BLE 会话控制块落位 | map：`.bss._ZL13s_ble_session 0x20053050 0x238`（HAL_Bluetooth.cpp.obj） | ✅ 568B ≤ 研究预算 650B，在 3360B 堆空洞内 |
| A5 主 RAM 封顶断言 | map：`ASSERT((ADDR(._user_heap_stack)+SIZEOF(._user_heap_stack)) <= ADDR(.ota_stack_guard), A5: …)` 链接通过 | ✅ 未破坏冻结 RAM 门槛（派工书停止条件 2 未触发） |
| OTA stack guard 断言 A2/A4 | map：`.ota_stack_guard 0x20055fe0 0x20`，紧邻 `.ota_stack` | ✅ |

## 6. CI 可移植性自检（反斜杠 include）

```text
rg "#include.*\\" Libraries USER MDK-ARM_F435/Platform
```

手写源命中仅 `Libraries/USB_MSC/msc_diskio.c.old`（`.old` 存档、不参与编译）与文档/非编译文件。**本卡全部新源（`Libraries/OTA/ota_ble_*.{c,h}`、HAL 接线改动）零反斜杠 include。** 工程接线后 GCC 构建（Windows 本机）与生成脚本再生 CMake 已绿；Linux CI 最终确认由验收轮负责。

## 7. 工程接线证据

- `MDK-ARM_F435/cmake-generated/CMakeLists.txt`：diff 仅 3 行新源（`ota_ble_ring.c` / `ota_ble_frame.c` / `ota_ble_session.c`，经 `keil_to_cmake.py` 再生，非手改）。
- `MDK-ARM_F435/proj.uvprojx`：diff 30 行（App-AC5 target OTA 组插入同 3 新源 + 头文件条目，字节级补丁锚定 `ota_p2_1_test.h`→`ota_keys.c` 顺序；Legacy target 未动）。
- 模拟器工程：本卡未接入新源（模拟器 `HAL/HAL_Bluetooth.cpp` 为独立拷贝，不含 BLE OTA 路径；`ota_sd.c` 等既有接入不受影响）。

## 8. 遗留说明

- 本卡不执行 git commit/push/merge（派工书 §6），交付工作区改动由主会话收口。
- AC5 构建未在本轮执行（派工书默认路径为 GCC；uvprojx 已接线，AC5 证据可在验收轮按需用 `build_f435.ps1 -Target X-Track-App-AC5 -BootstrapIfNeeded` 补充，新源已有同组 dep 模板可借用）。
- 真机 J-Link 闭环（烧录 + RTT 观测 BLE 会话）属 P3-3 联调范围，本卡以 host 单测 + 固件构建为验收面。
