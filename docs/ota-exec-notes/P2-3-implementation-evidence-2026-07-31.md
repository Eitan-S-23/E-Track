# P2-3 bspatch 流式集成实现证据（2026-07-31）

> 实现会话：Claude（原实现）+ Codex（独立验收整改接管）。
> 实现会话当时状态：**进行中，整改完成，待独立验收**。实现、宿主回归、构建
> 证据齐备；**本实现会话未自验收、未置「完成」、未 commit/push**，且当时按
> 会话禁令未运行 J-Link/RTT。后续独立非实现会话已完成真机抽验并判定通过，详见
> `P2-3-acceptance-2026-07-31.md`。

## 1. 基线与范围

```text
origin/main = 14d5476 (docs(ota): accept merge 52d0c33 conflict resolution)
仓库根工作树 = 保持干净且仍在 14d5476（未改动）
实现 checkout = D:\github\my\E-Track\.cache\p2-3-20260731（git clone --local 自仓库根）
```

本卡只实现差分 `.etu` 路径（`flags=0x0007`）。不写 ETSL commit marker、不改任何
BCB 副本、不进 STAGED（属 P2-5）。未修改 `PLAN-OTA.md`、
`docs/ota-binary-contracts.md`（冻结契约），未修改 vendor
`bsdiff_lzma_AES128-main/` 任何文件，未改动 P1-6 / P2-1 / P2-2 的实现与证据。

编码前研究与设计冻结于
`docs/ota-exec-notes/P2-3-bspatch-research-2026-07-31.md`（规约 §4）。

## 2. 变更清单

```text
新增  Libraries/OTA/ota_patch.h                 差分链对外 API
新增  Libraries/OTA/ota_patch.c                 差分链实现（可移植 C，callback I/O）
新增  Libraries/OTA/ota_p2_3_test.h             evidence harness 控制区布局
新增  tests/ota/test_ota_patch.c                宿主测试（167 checks）
新增  tests/ota/test_ota_patch.py               宿主测试编译/运行入口
新增  tests/ota-vectors/p2-3-vendor-oldpos.etu  vendor 多控制组/oldpos-only 回归包
新增  tests/ota-vectors/p2-3-vendor-oldpos-new.bin  对应目标镜像
新增  tests/ota-vectors/p2-3-invalid-control.etu    [0,0,0] 非进展拒绝回归包
改动  USER/HAL/HAL_OTA_Package.{h,cpp}          base_read(XIP) + OTA_PatchApplyStaging + P2-3 harness
改动  USER/HAL/HAL.cpp                          P2-3 harness 调用点 + 两条互斥 #error
改动  MDK-ARM_F435/cmake-generated/CMakeLists.txt  P2_3_TEST_ENABLE 开关块 + ota_patch.c 入编
改动  MDK-ARM_F435/proj.uvprojx                 ota_patch.{c,h} / ota_p2_3_test.h 入 Keil 工程
改动  cmake/linker/x-track-app-gcc.ld.S         .p2_3_control 0x800 evidence 区
改动  .github/workflows/firmware-build.yml      追加 python3 tests/ota/test_ota_patch.py
改动  PLAN-OTA-EXEC.md                          P2-3 卡认领与状态回写
```

## 3. vendor RAM-only 假设的处理（vendor 零改动）

研究阶段逐行读完 vendor 后确认 RAM-only 假设共 **4 处**，比卡片列出的 3 处多一处，
且第 1 处位于 vendor **核心**而非 user 层 —— 这决定了「绕过而非改造」的集成方式：

| # | 位置 | 假设 | 本卡处理 |
|---|---|---|---|
| 1 | `bspatch/bspatch.c:49-98` | 形参 `uint8_t *new`，第 72/78/89 行直接 `new+newpos` 读写，**从不调用 `stream->write`** → new 必须整块在 RAM | 不调用 `bspatch()`。在 `ota_patch.c` 实现同语义分块驱动 |
| 2 | `user/interface.c:262` | `bspatch_patch(..., uint8_t *patch_data, uint32_t patch_size, ...)` 整包在 RAM | 不调用 |
| 3 | `user/interface.c:281` | `vfopen(patch_data, patch_size)` 整个 patch 当内存数组 | 不用 vFile，patch 走 4KiB QSPI 滑窗 |
| 4 | `lzma/lzma_decompress.c:207` | `inBuf = vfgetpos(pf,...)` 把整压缩流裸指针交给 LzmaDec | 不用 `lzma_decompress_read()`，直接 `LzmaDec_DecodeToBuf` + 滑窗 |
| 5 | `user/interface.c:85` | `chunked_bspatch` 内 `bs_malloc(buffer_size)` 走主堆 | 1KiB 缓冲取自 40KiB 固定 arena，无主堆 |

**vendor 目录零改动**，因此对 bsdiff 制包侧零影响。只复用两个纯算法文件
（`lzma/LzmaDec.c`、`AES128_CTR/aes_core.c`），二者已由 P2-2 入库使用。
`interface.c` / `vFile.c` / `lzma_decompress.c` / `bspatch.c` 一行不引用、不编译。

复审报告修正 2 的三条集成约束逐条落实：

- **old = XIP 指针直读**：`USER/HAL/HAL_OTA_Package.cpp` 的 `base_read()` 从
  `OTA_APP_ORIGIN`(0x08010000) 直接 memcpy 当前块到 1KiB 缓冲，不复制整镜像。
- **patch 输入 = QSPI staging 流式 reader**：`stream_append()` 4KiB 密文滑窗，
  原地 AES-CTR 解密，替代 vFile 的 RAM-only 假设。
- **new 输出 = 1KiB 块写 QSPI candidate**：复用 P0-5 安全 API
  （`qspi_erase`/`qspi_data_write` + XIP 恢复），写后立即回读比对。
- 未照抄 README 的 `malloc(old_size)`：峰值与 `ph_osize`/`ph_nsize` 完全无关。

## 4. 校验顺序（契约 §2.4 ①-⑩ + §2.3 注，未重排未省略）

```text
外层  ① magic/header_len/header_crc32 → ② flags==0x0007 → ③ alg_id/key_id
      → ④ hw_rev → ⑤ layout_id → ⑥ min_boot_ver → ⑦ target_vcode>cur_vcode
      → ⑧ base_vcode==cur_vcode 且 base_sha8==当前镜像 SHA-256 前 8B
      → ⑨ 包长/payload_len 上限 → ⑩ payload_crc32（覆盖加密后 payload）
内层  1. ph_hcrc（off0..3 置零重算，BE）
      2. ph_psize == payload_len-40
      3. 首遍只解压不合成：实际长度 == ph_original_size，且流正常终止
      4. ph_osize/ph_ocrc 对基版（XIP 流式 CRC，二重兜底）
      —— 以上全部在 candidate_prepare 之前 ——
      重绕 AES/LZMA，第二遍执行流式 bspatch
      5. ph_nsize/ph_ncrc 对 candidate（QSPI 回读流式 CRC）
```

首遍和第二遍复用同一次 `LzmaDec_Allocate`，只重置 AES-CTR 输入位置与
`LzmaDec_Init` 状态，不增加第二份字典/概率表。首遍失败时 `base_read_count==0` 且
`candidate_prepare/program==0`，实际恢复冻结的 `1 → 2 → 3 → 4 → 5` 顺序。

`base_sha8` 语义经 toy 向量实测确认 = 基版**整文件** SHA-256 前 8B
（`toy-old.bin` file_sha256 `3081fa0afc5bb2f3…` == 外层头 `base_sha8`），
不是 fw_header 的双零法 `image_sha256`。

一个实测坑：bsdiff 控制字是 **sign-magnitude 编码**（bit63 符号位 + 低 63 位绝对
值），不是补码。toy-patch 的 `ctrl[2]` 原始字节是
`0f00000000000080`：vendor `offtin`/sign-magnitude 解码为 **-15**，若按 little-endian
`int64_t` 补码误读才是 **-9223372036854775793**。实现逐字节按 vendor `offtin`
公式还原。

## 5. 宿主测试与逐字节一致性证明

```text
命令：python tests/ota/test_ota_patch.py   （cwd = .cache/p2-3-20260731）
结果：167/167 checks passed
      P2_3_VECTOR_PREFLIGHT=PASS vendor_controls=11 oldpos_only=9
      invalid_control=[0,0,0]
```

关键断言（正常链）：

```text
toy-patch returns success                                     PASS
toy-patch output matches toy-new byte-for-byte                PASS
toy-patch outer metadata matches expected.json                PASS
toy-patch inner header fields match expected.json             PASS
toy-patch fw_header double-zero SHA matches expected          PASS
toy-patch writes bounded 1KiB chunks                          PASS
toy-patch workspace stays within fixed 40KiB arena            PASS
toy-patch workspace is acquired, wiped, and released once     PASS
toy-patch reads base image in bounded blocks, never whole     PASS
vendor multi-control patch returns success                    PASS
vendor multi-control output matches expected byte-for-byte    PASS
decoded_length rejection precedes base validation             PASS
candidate fw_header mismatch returns fw_header                PASS
candidate version mismatch returns image_metadata             PASS
all-zero non-progress control returns patch_control            PASS
```

新增 vendor 回归由仓库未修改
`bsdiff_lzma_AES128-main/bsdiff/build/bin/bsdiff.exe` 生成。解密解压后控制流固定为：

```text
[1500,333,2560]
[0,0,-256] x 9
[2263,0,-179]
```

公开 `ota_patch_apply()` 返回成功，6 次写入均不超过 1KiB，candidate 与
`p2-3-vendor-oldpos-new.bin` 4096B 逐字节一致。静态回归资产：

```text
p2-3-vendor-oldpos-new.bin 4096B sha256 d37e66ef5fe96b1961a504e3c0610ebec962c27cc93ac7f4955d05986b575034
p2-3-vendor-oldpos.etu      448B sha256 bcb6ed305ee73d546f4c533c0cdda8f3495538b88e4f3c5a947d7ea3277d4a27
p2-3-invalid-control.etu    137B sha256 6e481859a9ff5508a2dabb1b349f0a0acf6f0330a3d7895fec01f5f190ed3e5d
```

逐字节一致性的判定方式：夹具 candidate 以 `0xA5` 预填，`candidate_prepare` 后置
`0xFF`，`candidate_program` 模拟 NOR 语义（只能 1→0，未擦写覆盖即失败），
合成结束后 `memcmp(fixture.candidate, toy-new.bin, 4096) == 0` 且
`prepared_len == 4096`。同时内层实测值与 `expected.json` 对齐：

```text
payload_len=149  payload_crc32=0x59B94A78  target_vcode=20800  base_vcode=20700
ph_psize=109  ph_osize=4096  ph_ocrc=0x37562FA9  ph_ncrc=0x46C4F6E1
ph_original_size=4120 (=24B 控制 + 4096B diff)  image_len=4096
image_sha256=5b508eea3c3604ef42b5895d44b1df540a21e910bd00b184ff31ab80f0c824df
```

注：`expected.json` 的 `payload_crc32` 字段存的是 **LE 字节串** `784ab959`，
对应 u32 `0x59B94A78`；而 `ph_ocrc`/`ph_ncrc` 是 BE 存储故字节串与 u32 同形。
首轮测试因把 LE 串当 u32 用而失败 1 项，已按向量实测值修正。

拒绝分支覆盖（每条均断言 BCB 逐字节不变；prepare 前的分支另断言
prepare/program 计数为 0）：

- 外层：magic、header_len、header CRC、误用全量 flags(0x000B)、alg_id、key_id、
  hw_rev、layout_id、min_boot_ver、target_vcode 等于/低于当前（降级）、
  base_vcode 不等/为 0、base_sha8 不符/全零、设备身份不符、
  payload_len 与包长不符、payload_len 无 patch 流、payload CRC、
  外层头读失败、payload 读失败。
- 内层：ph_hcrc、ph_psize、pad 非零、LZMA lc 非冻结值、字典 <4KiB/>16KiB、
  ph_nsize 容不下 fw_header/超 candidate 容量、
  ph_original_size 低于 nsize+控制/控制字节非 24 对齐/长于实际流、
  ph_osize 不符/为 0、ph_ocrc 不符、**基版被改 1 字节被 ph_ocrc 兜住**、
  基版读失败、ph_ncrc 不符。
- 流与 flash：LZMA 流损坏、prepare 失败、program 失败、回读不符、回读失败。
- 最终镜像：共享 Boot fw_header 校验失败、有效 fw_header 与外层 target_vcode
  元数据不一致。
- workspace：acquire 失败（不启动 LZMA/bspatch，契约 §531）、short workspace
  被拒且已清零释放。
- 参数：null io、null device、缺 base_read 回调、package_len 过小/过大。
- 控制流：公开 API 命中 `PATCH_CONTROL` 的 `[0,0,0]`、patch 流截断、LZMA 流过短。

## 6. 堆峰值实测（≤ P0-6 预算）

**实测值，非估算**（由 `ota_patch_info_t.workspace_peak` 导出，测试打印）：

```text
[info] workspace_peak=21832 bytes, ceiling=40960 bytes
[info] work buffer=1024, stream buffer=1024, input window=4096
```

即 **21832 B / 40960 B，占 53.3%，余量 19128 B**。契约 §520 逐项对账：

| 契约 §520 分配项 | 预算 | 本卡实现 |
|---|---:|---|
| bspatch 差分/extra 写缓冲 | 1024 | `work[1024]`（**本卡启用的新增项**） |
| LZMA 解压输出缓冲 | 1024 | `stream[1024]`（承载 bsdiff 指令流） |
| 单个 staging 活跃窗口 | 4096 | `input[4096]`，密文原地解密不双倍 |
| `CLzmaDec` + 概率表 + 字典 | 100+10112+16384 | arena 内 LzmaDec_Allocate（toy 实测字典 4096，上限按 16384 预算） |
| AES ctx + counter + keystream | 192 | `AES_ctx` + `counter[16]` + `keystream[16]` |
| hash/CRC 与 allocator 开销 | 2048 | `verify[1024]` 归入此项 |

峰值与 `ph_osize`(4096)/`ph_nsize`(4096) 无关 —— 这是「不 malloc(old_size)」的
实质。若换 603 KB 真实镜像，`work`/`stream`/`input`/LZMA 状态尺寸不变，峰值仅随
props 中的字典尺寸变化（上限 16 KiB 已在预算内）。

真机峰值回填属 P2-6（`OTA_P2_3_OFF_WORKSPACE_PEAK` 已在 harness 控制区预留）。

## 7. 宿主回归（全部实跑，零回退）

| 测试 | 命令 | 结果 |
|---|---|---|
| fw_header vectors | `python tests/boot/test_fw_header_vectors.py` | `P1_1_FW_HEADER_VECTORS=PASS cases=16` → **16/16** |
| Boot Ymodem / ETSL | `python tests/boot/test_boot_protocols.py` | `19 checks, 0 failure(s)` / `P1_1_BOOT_PROTOCOLS=PASS` → **19/19** |
| BCB | `gcc -Wall -Wextra -Werror -ILibraries/EEPROM -ILibraries tests/bcb/test_bcb_arbiter.c Libraries/EEPROM/eeprom_bcb.c` 后运行 | `0 failure(s)`，PASS 行计数 **27/27** |
| Boot state machine | `python tests/boot/test_boot_state_machine.py` | `P1_3_STATE_MACHINE=PASS checks=96 failures=0` → **96/96** |
| P1-6 control protocol | `python tests/boot/test_p1_6_protocol.py` | `P1_6_PROTOCOL=PASS checks=21 failures=0` → **21/21** |
| OTA golden vectors | `python tests/ota-vectors/test_vectors.py` | `Ran 9 tests ... OK` → **9/9** |
| P2-1 staging | `python tests/ota/test_ota_staging.py` | `P2_1_STAGING=PASS checks=48 failures=0` → **48/48** |
| P2-2 package | `python tests/ota/test_ota_package.py` | `P2_2_PACKAGE=PASS checks=102` → **102/102** |
| **P2-3 patch（新增）** | `python tests/ota/test_ota_patch.py` | **167/167 checks passed**；vendor 11 组/oldpos-only 9 组 preflight PASS |

八项既有回归全部命中卡上冻结的期望计数，零回退。

补充运行 `python tests/boot/test_prepare_bootstrap_app.py` 的默认环境路径时失败：
测试优先启动 Windows PowerShell 5.1，其子进程内 `Get-FileHash` 不可解析，抛出
`CommandNotFoundException,Copy-P1PreservedArtifact`。不改无关测试，改用本机
PowerShell 7（临时 PATH 仅暴露 `pwsh`，并设 `PYTHONUTF8=1`）重跑同一命令：
`P1_5_PREPARE_TOOL=PASS checks=42 powershell_checks=8`。该补充项不在 P2-3
冻结验收矩阵，两个结果均作为环境说明保留。

## 8. 构建证据

环境说明：最终整改构建使用 `Unix Makefiles` 和短路径，避免 Windows 长对象路径
问题。生产构型目录为 `D:/p2-3-gcc-prod-final`，evidence 构型目录为
`D:/etfwe3`；两者 `CMAKE_BUILD_TYPE=Release`，源码目录均指向本实现 checkout。

### 8.1 生产构型（fresh GCC Release，P2-3 harness OFF）

```powershell
cmake -S MDK-ARM_F435/cmake-generated -B D:/p2-3-gcc-prod-final -G "Unix Makefiles" `
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024 -DP2_3_TEST_ENABLE=OFF
cmake --build D:/p2-3-gcc-prod-final --target X_Track_Boot X_Track_App_GCC --parallel 4
```

Boot：

```text
Memory region     Used Size  Region Size  %age Used
       FLASH:      14236 B        64 KB     21.72%
         RAM:       9784 B       352 KB      2.71%
   text  data   bss    dec   hex  filename
   14232     4  9780  24016  5dd0  D:/p2-3-gcc-prod-final/boot/X-Track-Boot.elf

X-Track-Boot.bin  14236 bytes  2026-07-31 21:18:56 +08:00
SHA-256 5656466564891B54666325DA4545F3F819BA38F50660AB4772809B5647135AB5
```

- **Boot < 64 KiB**：14236 < 65536 ✓（21.72%）
- **三个 LOAD 段无 RWX**（`arm-none-eabi-readelf -lW`）：

```text
Type   Offset   VirtAddr   PhysAddr   FileSiz MemSiz  Flg
EXIDX  0x004790 0x08003790 0x08003790 0x00008 0x00008 R
LOAD   0x001000 0x08000000 0x08000000 0x03798 0x03798 R E
LOAD   0x005000 0x20000000 0x08003798 0x00004 0x01438 RW
LOAD   0x000438 0x20001438 0x0800379c 0x00000 0x01200 RW
```

三个 LOAD 分别为 `R E` / `RW` / `RW`，无一为 RWX ✓

App：

```text
X-Track-App-GCC.bin  563148 bytes  2026-07-31 21:22:10 +08:00
SHA-256 3FB7058A2A45848678C600755C3577EF0BFF298B89C4AF188FC7BE1B4B15750E
```

App 镜像含 `__DATE__`/`__TIME__`（`USER/App/Version.h:76`），按构造**不可复现**，
此哈希仅用于本轮定位，不作可复现声明。Boot 不含时间戳，哈希可复现。

overlay 互斥布局（`readelf -SW`，同址而非顺序摆放）：

```text
[14] .sram_ext     NOBITS  20058000  028000  WA
[15] .ota_overlay  NOBITS  20058000  00a000  WA
```

**warning 与 error 的如实陈述**：App 构建**有 warning、零 error**。warning 全部
为仓库既有类别 —— `PageFactory.h` unused parameter ×21、`MusicCode.h` missing
field initializer、`pgmspace.h`/`DateStrings.cpp` strict-aliasing、
`SPI.h` unused variable、SdFat packed-member、newlib
`_write/_read/_kill/_getpid is not implemented`、link 期 2-byte/4-byte wchar_t。
App ELF 另保留仓库既有首个 `RWE` LOAD 段，链接器会报告
`has a LOAD segment with RWX permissions`；本卡未修改该既有布局。Boot 的三个
LOAD 段仍为 `R E` / `RW` / `RW`，无 RWX。
逐条核对：**`ota_patch.c` 与 `ota_p2_3_test.h` 未产生任何新增编译告警**，
`ota_patch.c` 与 `HAL_OTA_Package.cpp` 仅各出现一条既有类别的 wchar_t 链接告警
（该类告警每个目标文件都有）。

### 8.2 Evidence 构型（P2_3_TEST_ENABLE=ON）

```powershell
cmake -S MDK-ARM_F435/cmake-generated -B D:/etfwe3 -G "Unix Makefiles" `
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024 -DP2_3_TEST_ENABLE=ON
cmake --build D:/etfwe3 --target X_Track_App_GCC --parallel 4
```

```text
[100%] Built target X_Track_App_GCC     BUILD_RC=0，零 error
X-Track-App-GCC.bin  579008 bytes  2026-07-31 21:28:55 +08:00
SHA-256 8ACFB1FC305ED92D66C48D86066F1B8425C2EE820F3500FCA55F2E2C7D8097EB

[12] .p2_3_control  NOBITS  20057800  000800  WA     ← RAM 尾部 - 0x800
[15] .sram_ext      NOBITS  20058000  028000  WA
[16] .ota_overlay   NOBITS  20058000  00a000  WA

__p2_3_control_start__ = 20057800    __p2_3_control_end__ = 20058000
HAL_OTA_PatchEvidenceReady = 08043350
HAL_OTA_PatchEvidenceDone  = 08043354
HAL::OTA_PatchEvidenceRun  = 08043368
```

生产构型中 `.p2_3_control` 段计数为 **0**，无任何 evidence 符号。
`.ota_overlay` 四条断言与 P1-6 `0x200` / P2-1 `0x80` / P2-2 `0x800` 三段区
均未改动，仅新增 `#elif defined(P2_3_TEST_ENABLE)` 分支。
Evidence 构型同样有仓库既有 warning（包括 App ELF 首个 `RWE` LOAD 段），但
error 数为 0。关闭 harness 的生产 App 仍有同一既有 RWE 段；P2-3 只新增
evidence-only `.p2_3_control`，未改变该段权限。无 RWX 的 `R E` / `RW` / `RW`
结论仅适用于 Boot。

### 8.3 harness 配置矩阵（最终整改复跑）

```text
cmake -S MDK-ARM_F435/cmake-generated -B D:/p23-final-cfg-20260731-prod
  -G Ninja -DCMAKE_BUILD_TYPE=Release
  -> rc=0, Configuring done / Generating done

cmake -S MDK-ARM_F435/cmake-generated -B D:/p23-final-cfg-20260731-p23
  -G Ninja -DCMAKE_BUILD_TYPE=Release -DP2_3_TEST_ENABLE=ON
  -> rc=0, Configuring done / Generating done

cmake -S MDK-ARM_F435/cmake-generated -B D:/p23-final-cfg-20260731-p16p23
  -G Ninja -DCMAKE_BUILD_TYPE=Release -DP1_6_TEST_ENABLE=ON -DP2_3_TEST_ENABLE=ON
  -> rc=1
  P1-6 and P2-3 evidence harnesses are mutually exclusive
cmake -S MDK-ARM_F435/cmake-generated -B D:/p23-final-cfg-20260731-p21p23
  -G Ninja -DCMAKE_BUILD_TYPE=Release -DP2_1_TEST_ENABLE=ON -DP2_3_TEST_ENABLE=ON
  -> rc=1
  P2-1 and P2-3 evidence harnesses are mutually exclusive
cmake -S MDK-ARM_F435/cmake-generated -B D:/p23-final-cfg-20260731-p22p23
  -G Ninja -DCMAKE_BUILD_TYPE=Release -DP2_2_TEST_ENABLE=ON -DP2_3_TEST_ENABLE=ON
  -> rc=1
  P2-2 and P2-3 evidence harnesses are mutually exclusive
```

生产与 P2-3 单开配置成功，新增 3 条两两互斥断言均在 configure 阶段按预期
`FATAL_ERROR`；`USER/HAL/HAL.cpp` 另有两条 `#error` 兜底。

### 8.4 AC5 App 构建

```powershell
# 新增源的 dep/lnp 元数据已生成；最终编译、链接、fromelf 全部走命令行脚本
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command `
  "& 'MDK-ARM_F435\build_f435.ps1' -Target 'X-Track-App-AC5' -AutoStale"
```

先用 `UV4.exe -b ... -t X-Track-App-AC5` 让 Keil 刷新新增源的 dep/lnp；随后
`build_f435.ps1` 复用 `Objects-App-AC5/proj_X-Track-App-AC5.dep` 与
`X-Track-App-AC5.lnp` 中的精确命令完成最终链接与 `fromelf`，无需打开 uVision
界面参与后续编译：

```text
[AutoStale] stale sources (incl header deps): 109
[OK] target X-Track-App-AC5 build complete (armlink/fromelf exit code 0)
Program Size: Code=265448 RO-data=288536 RW-data=1296 ZI-data=495380
".\Objects-App-AC5\X-Track-App-AC5.axf" - 0 Error(s), 0 Warning(s).
Track-App-AC5.bin 554784 bytes 2026-07-31T22:05:13+08:00
SHA-256 E6B8CBD7BB1CF30B232D2CE4C240947FA4C2998E58200E2D8182525B53C95BC8
```

`proj_X-Track-App-AC5.dep` 包含 `ota_patch.c` 编译条目，lnp 包含
`.\objects-app-ac5\ota_patch.o`，证明新源已进入 AC5 App 最终链接。

### 8.5 可移植性自检

按 `AGENTS.md`「GCC / Linux CI 源码可移植防坑」，新增/改动手写源的
`#include` 全部为正斜杠，`Libraries/OTA` 下反斜杠 include 命中数为 **0**。
新增文件均为纯 C（`.c`）或头文件，不涉及 Keil `--cpp11` group option 陷阱。

### 8.6 整改续行最终复核（2026-07-31 21:18-21:36 +08:00）

在未再修改源码的前提下，对当前工作树重跑关键命令，确认后台构建和产物刷新未
改变结论：

```powershell
python tests/ota/test_ota_patch.py
cmake --build D:/p2-3-gcc-prod-final --target X_Track_Boot X_Track_App_GCC --parallel 4
cmake --build D:/etfwe3 --target X_Track_App_GCC --parallel 4
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command `
  "& 'MDK-ARM_F435\build_f435.ps1' -Target 'X-Track-App-AC5' -AutoStale"
```

- P2-3 宿主：`167/167 checks passed`，vendor preflight 仍为
  `vendor_controls=11 oldpos_only=9 invalid_control=[0,0,0]`。
- 既有宿主回归再次命中冻结计数：fw_header `16/16`、Boot 协议 `19/19`、
  BCB `27/27`、状态机 `96/96`、P1-6 `21/21`、golden `9/9`、P2-1
  `48/48`、P2-2 `102/102`；PowerShell 7 补充项为 `42/42`。
- GCC production 增量复核 rc=0：Boot `14236B`，SHA-256
  `5656466564891B54666325DA4545F3F819BA38F50660AB4772809B5647135AB5`；App
  `563148B`，当前产物 SHA-256
  `3FB7058A2A45848678C600755C3577EF0BFF298B89C4AF188FC7BE1B4B15750E`。
- GCC evidence 增量复核 rc=0：App `579008B`，当前产物 SHA-256
  `8ACFB1FC305ED92D66C48D86066F1B8425C2EE820F3500FCA55F2E2C7D8097EB`；
  `.p2_3_control @ 0x20057800 / 0x800`，三个 evidence 函数地址仍为
  `0x08043350` / `0x08043354` / `0x08043368`。生产构型仍无
  `.p2_3_control`，Boot 三个 LOAD 仍为 `R E` / `RW` / `RW`。
- AC5 命令行复核 rc=0：`[AutoStale] stale sources (incl header deps): 109`，
  armlink/fromelf 成功，
  `Program Size: Code=265448 RO-data=288536 RW-data=1296 ZI-data=495380`，
  build log 为 `0 Error(s), 0 Warning(s)`；`Track-App-AC5.bin` 为 `554784B`，
  当前 SHA-256
  `E6B8CBD7BB1CF30B232D2CE4C240947FA4C2998E58200E2D8182525B53C95BC8`。
- 随后的同命令终检再次返回
  `[AutoStale] stale sources (incl header deps): 0`，armlink/fromelf 仍为 rc=0，
  Program Size、bin 长度与 SHA-256 均保持上述值；说明 dep/lnp 当前已无陈旧源。
- 五种最终 configure 复核：production/P2-3 单开为 `rc=0/0`；
  P1-6/P2-3、P2-1/P2-3、P2-2/P2-3 为 `rc=1/1/1`，均命中对应
  `mutually exclusive` 文本。

### 8.7 最终命令复核（2026-07-31 22:05 +08:00）

未修改源码的最终工作树上再次执行：

```powershell
python tests/ota/test_ota_patch.py
python tests/boot/test_fw_header_vectors.py
python tests/boot/test_boot_protocols.py
gcc -std=c99 -Wall -Wextra -Werror -O2 -ILibraries/EEPROM `
  tests/bcb/test_bcb_arbiter.c Libraries/EEPROM/eeprom_bcb.c `
  -o .cache/p2-3-bcb-test.exe
.cache/p2-3-bcb-test.exe
python tests/boot/test_boot_state_machine.py
python tests/boot/test_p1_6_protocol.py
python tests/boot/test_prepare_bootstrap_app.py  # PowerShell 7 + PYTHONUTF8=1
python tests/ota-vectors/test_vectors.py
python tests/ota/test_ota_staging.py
python tests/ota/test_ota_package.py
cmake --build D:/p2-3-gcc-prod-final --target X_Track_Boot X_Track_App_GCC --parallel 4
cmake --build D:/etfwe3 --target X_Track_App_GCC --parallel 4
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command `
  "& 'MDK-ARM_F435\\build_f435.ps1' -Target 'X-Track-App-AC5' -AutoStale"
git diff --check
```

结果：P2-3 `167/167`；既有宿主 `16/19/27/96/21/9/48/102`；PowerShell 7
补充项 `42/42`；GCC production Boot/App `14236B/563148B`，哈希分别为
`5656466564891B54666325DA4545F3F819BA38F50660AB4772809B5647135AB5` /
`3FB7058A2A45848678C600755C3577EF0BFF298B89C4AF188FC7BE1B4B15750E`；
evidence App `579008B`，哈希为
`8ACFB1FC305ED92D66C48D86066F1B8425C2EE820F3500FCA55F2E2C7D8097EB`，
`.p2_3_control` 仍为 `0x20057800/0x800`；AC5 `AutoStale=0`、armlink/fromelf
rc=0、`0 Error(s), 0 Warning(s)`、`Program Size: Code=265448 RO-data=288536
RW-data=1296 ZI-data=495380`、bin `554784B`、哈希为
`E6B8CBD7BB1CF30B232D2CE4C240947FA4C2998E58200E2D8182525B53C95BC8`；
五构型 configure 结果仍为 `0/0/1/1/1`，三条非法组合均命中对应
`mutually exclusive` 错误；`git diff --check` 无输出。

GCC App 与 AC5 App 含构建时间信息，重复链接可改变二进制哈希；§8.1/§8.2/§8.4
与本节均记录对应命令最后一次成功重建时的当前产物哈希，不将 App 哈希视为可复现
身份值。Boot 镜像不含构建时间信息，哈希保持稳定。

## 9. 待办与技术债

1. **实现会话未执行真机取证，独立验收已补抽验**：实现会话当时禁跑
   J-Link/RTT；后续独立会话使用 `P2_3_TEST_ENABLE` success 路径完成真机抽验，
   4096B candidate 与期望 SHA-256 完全一致，workspace 峰值 21784B，BCB 前后
   逐字节一致，并恢复生产 Boot/App 到 `CONFIRMED v20800`。坏包与降级分支继续由
   公开 API 宿主矩阵覆盖，符合「PC 仿真+真机抽验」验收选项。
2. **三个流式原语暂存两份**（AES-CTR 流 / arena / 4KiB 滑窗，`ota_package.c` 与
   `ota_patch.c` 各一份）。原因：P2-2 已独立验收收口，其真机 r3 证据绑定当时
   `ota_package.c` 字节，提取共享会使已验收证据与源码脱节，而本卡禁跑板卡命令且
   「不动 P2-2 既有实现」为红线。两份代码刻意保持逐字段同构，建议 P2-5/P2-6
   （届时两卡本就需改动并重新取证）一并提取 `Libraries/OTA/ota_stream.{c,h}`。
   详见 research 文档 §7.2。
3. **补充测试的默认环境差异**：`test_prepare_bootstrap_app.py` 在 Windows
   PowerShell 5.1 路径下因 `Get-FileHash` 模块解析失败；同一测试切换到本机
   PowerShell 7 后已通过 `42/42`。不修改该无关测试。

## 10. 验收状态

独立非实现会话已于 2026-07-31 完成整改验收并判定 **通过**；P2-3 已在执行看板
置为 **完成**，P2 进度更新为 `3/6`。实现会话未自验收，验收会话也未
commit/push/merge；完整判据、真机日志与设备恢复审计见
`P2-3-acceptance-2026-07-31.md`。
