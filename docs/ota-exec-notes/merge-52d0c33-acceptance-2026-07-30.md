# 合并提交 52d0c33 人工冲突解决独立验收

- 验收人: Claude（独立验收会话，非实现会话）
- 日期: 2026-07-30
- 被验收对象: `52d0c334f29c4975c16c55f9b7d8b74815bd6c05`（双父合并）
  - 父1 = `9a2f27f70bc4ebff26e5a335bce73ac681ab4890`（P1-6 侧）
  - 父2 = `2374519781460ce150b8ba44b4c246280939493a`（P2 收口侧）
  - 共同基线 = `bd9f4da0bee476d4ee2f4ba3f3e25b1e17b0d9ec`
- 验收 checkout: `.cache/acceptance-merge-52d0c33-20260730`（detached worktree）
- **结论: ACCEPT**

## 0. 本轮定位与纪律

本轮补的是规约 §3「实现者不自验收」的缺失签字：写这三个冲突解决的会话同时
也是跑组合验证的会话。验收范围严格限定为 5 个「与两个父提交都不同」的文件，
即两侧既有验收都未覆盖的新内容：

```text
MDK-ARM_F435/cmake-generated/CMakeLists.txt      （冲突解决）
cmake/linker/x-track-app-gcc.ld.S                （冲突解决）
cmake/linker/x-track-boot-gcc.ld.S               （冲突解决）
PLAN-OTA-EXEC.md                                 （状态对账）
docs/ota-exec-notes/P1-6-P2-integration-2026-07-30.md（集成记录）
```

不重新验收 P1-6、P2-1、P2-2 的实现本体，不推翻
`docs/ota-exec-notes/P2-1-P2-2-acceptance-2026-07-30.md`。本轮只读 + 跑验证：
未修改任何实现源码，未执行 `git commit/push/merge/rebase`，未运行 J-Link /
RTT / 任何板卡命令，未触碰 P1-6 物理断电点 03/05/07/15/16/17，
`PLAN-OTA.md` 与 `docs/ota-binary-contracts.md` 未修改。根工作树保持
`52d0c33` 且干净。

### 独立确认「5 文件」范围本身成立

```bash
git diff --name-status 9a2f27f 52d0c33   # 38 项
git diff --name-status 2374519 52d0c33   # 17 项
```

两个清单的交集恰为上述 5 个文件，与任务书一致，未发现第 6 个双向差异文件。

## 1. 核心判据：合并有没有丢掉任一侧的语义

### 1.1 方法

对三个冲突文件，先分别取 `base→父1`、`base→父2` 的完整 diff 建立「两侧各自
改了什么」的基准，再检查合并结果是否两侧都存活。对 linker 另加一道更强的
机器判据：用 `arm-none-eabi-gcc -E -P` 在同一组宏下分别预处理**父方原文**与
**合并结果**，逐字节 diff。

```bash
arm-none-eabi-gcc -E -P -x assembler-with-cpp -I <Libraries/OTA> \
  [-DP1_6_TEST_ENABLE=1 | -DP2_1_TEST_ENABLE=1 | -DP2_2_TEST_ENABLE=1] \
  <ld.S> -o <out.ld>
```

| 模式 | 文件 | 合并结果 vs 对应父方 |
|---|---|---|
| P1_6 | app | 差异（见 §1.2，已判定为有意且无损） |
| P1_6 | boot | **IDENTICAL** |
| P2_1 | app / boot | **IDENTICAL** / **IDENTICAL** |
| P2_2 | app / boot | **IDENTICAL** / **IDENTICAL** |
| default | app vs 父2 / boot vs 父2 | **IDENTICAL** / **IDENTICAL** |
| default | boot vs 父1 | **IDENTICAL** |

### 1.2 唯一一处非 IDENTICAL 的独立判定（无语义丢失）

`P1_6` 与 `default` 模式下，合并后的 App linker 采用了 P2 的
`OVERLAY … NOCROSSREFS { .sram_ext / .ota_overlay }` 结构，而父1 原文是旧的
扁平 `.sram_ext (NOLOAD)`。这不是「P1-6 的东西被覆盖」，理由是机器可查的：

```bash
git diff bd9f4da 9a2f27f -- cmake/linker/x-track-app-gcc.ld.S \
  | grep -E "^[+-].*(sram_ext|OVERLAY|ota_overlay)"
# → 无输出：P1-6 侧从未改动 sram_ext / overlay 区
```

即该区域是 P1-6 的**未修改继承内容**，P2 侧才是该区域的唯一修改者。合并取
P2 版本属于正确的「非冲突侧改动全取」，不存在被丢弃的 P1-6 语义。反向验证：

```bash
diff <(git show 2374519:cmake/linker/x-track-app-gcc.ld.S) \
     <(git show 52d0c33:cmake/linker/x-track-app-gcc.ld.S)
# → 27 行差异，全部为 P1_6 分支的新增；无 P2 内容被删改
```

即 **合并后的 App linker = 父2 版本 + P1-6 分支**，两侧语义都在。

### 1.3 三段 RAM 尾部 evidence control 区（0x200 / 0x80 / 0x800）

合并后 App linker 的 `MEMORY` 与 `SECTIONS` 均为三路
`#if P1_6 / #elif P2_2 / #elif P2_1 / #else` 链，三段都在且尺寸各自正确。
预处理产物实测（`0x20000000` / `0x58000` 为 `ota_layout.h` 契约值）：

```text
P1-6 : RAM = ORIGIN, LENGTH 0x58000-0x200 ; P1_6_CTRL LENGTH 0x200
       ASSERT(ADDR(.p1_6_control) == …-0x200) + ASSERT(SIZEOF == 0x200)
P2-1 : RAM = ORIGIN, LENGTH 0x58000-0x80  ; P2_1_CTRL LENGTH 0x80
       ASSERT(ADDR(.p2_1_control) == …-0x80)  + ASSERT(SIZEOF == 0x80)
P2-2 : RAM = ORIGIN, LENGTH 0x58000-0x800 ; P2_2_CTRL LENGTH 0x800
       ASSERT(ADDR(.p2_2_control) == …-0x800) + ASSERT(SIZEOF == 0x800)
```

三段的「主 RAM 与 control 相邻」「control 与 overlay 相邻」两条连续性
ASSERT 亦各自成对保留。判据 2 前半通过。

### 1.4 P2 的 `.ota_overlay` 地址与大小断言完整保留

四种模式的 App 预处理产物中，以下 4 条断言全部命中（4/4）：

```text
ASSERT(ADDR(.sram_ext)     == OTA_OVERLAY_ORIGIN,            "LiveMap overlay address drifted")
ASSERT(SIZEOF(.sram_ext)   <= LENGTH(RW_IRAM2),              "SRAM overlay exceeds the contracted region")
ASSERT(ADDR(.ota_overlay)  == OTA_OVERLAY_ORIGIN,            "OTA workspace address drifted")
ASSERT(SIZEOF(.ota_overlay)== OTA_OVERLAY_WORKSPACE_LENGTH,  "OTA workspace size drifted")
```

含 `NOCROSSREFS`、`__ota_overlay_start__/__ota_overlay_end__` 与
`KEEP(*(.ota_overlay*))`。判据 2 中段通过。

### 1.5 Boot linker：保留 P1-6 与 P2-1，P2-2 不给 Boot 加控制区

合并后 Boot linker 为两路 `#if P1_6 / #elif P2_1 / #else`，
`grep -n "P2_2"` 命中 **0**。预处理实测：

| 模式 | Boot control |
|---|---|
| default | 无（`RAM LENGTH = 0x58000` 完整） |
| P1-6 | `P1_6_CTRL` `0x200` + 两条 ASSERT |
| P2-1 | `P2_1_CTRL` `0x80` + 两条 ASSERT |
| P2-2 | **无**（`RAM LENGTH = 0x58000` 完整） |

判据 2 后半通过。

### 1.6 `APP_LINKER_DEFINES` → `OTA_TEST_LINKER_DEFINES` 改名无漏改

```bash
grep -rn "APP_LINKER_DEFINES\|P1_6_LINKER_DEFINES\|P2_LINKER_DEFINES" . \
  --include=*.txt --include=*.cmake --include=*.yml --include=*.ps1 --include=*.S
# → ZERO orphaned refs
```

新名全部使用点（CMakeLists 6 处 + 集成记录 1 处说明）：

```text
CMakeLists.txt:63  set(OTA_TEST_LINKER_DEFINES)
CMakeLists.txt:65/68/71  三个 list(APPEND …) 分别对应 P1_6 / P2_1 / P2_2
CMakeLists.txt:79  App  预处理命令 ${OTA_TEST_LINKER_DEFINES}
CMakeLists.txt:93  Boot 预处理命令 ${OTA_TEST_LINKER_DEFINES}
```

同一变量确实同时喂给 App 与 Boot 两条预处理命令，且三个开关都能进入该变量。
判据 3 通过。

### 1.7 CMakeLists 两侧非 linker 改动均存活

父1 侧：`boot_p1_6_test.c` 条件加入 `BOOT_PROJECT_SOURCES`(:531-533)、
`P1_6_TEST_ENABLE` 同时定义给 `X_Track_Boot` 与 `X_Track_App_GCC`(:684-686)。
父2 侧：`HAL_OTA_Staging.cpp`(:477)、`HAL_OTA_Package.cpp`(:496)、
`ota_keys.c`/`ota_package.c`/`ota_staging.c`(:498-500)、
`aes_core.c`/`LzmaDec.c`(:505-506) 入源列表，App 侧 include 目录三项，
`P2_1`/`P2_2` 各自的 `target_compile_definitions`(:688-692)。均在。

## 2. 宿主回归独立重跑（8/8 与集成记录一致）

命令与实测输出（在验收 checkout 内执行）：

```bash
python tests/boot/test_fw_header_vectors.py   # P1_1_FW_HEADER_VECTORS=PASS cases=16
python tests/boot/test_boot_protocols.py      # 19 checks, 0 failure(s) / P1_1_BOOT_PROTOCOLS=PASS
python tests/boot/test_boot_state_machine.py  # P1_3_STATE_MACHINE=PASS checks=96 failures=0
python tests/boot/test_p1_6_protocol.py       # P1_6_PROTOCOL=PASS checks=21 failures=0
python tests/ota-vectors/test_vectors.py      # Ran 9 tests … OK
python tests/ota/test_ota_staging.py          # P2_1_STAGING=PASS checks=48 failures=0
python tests/ota/test_ota_package.py          # P2_2_PACKAGE=PASS checks=102
gcc -Wall -Wextra -Werror -std=c99 -I Libraries/EEPROM -o test_bcb.exe \
    tests/bcb/test_bcb_arbiter.c Libraries/EEPROM/eeprom_bcb.c && ./test_bcb.exe
                                              # 27 checks, 0 FAIL
```

| 测试 | 声明 | 实测 |
|---|---|---|
| fw_header vectors | 16/16 | **16/16 PASS** |
| Ymodem / ETSL | 19/19 | **19/19 PASS** |
| BCB | 27/27 | **27 checks / 0 failure** |
| Boot state machine | 96/96 | **96/96 PASS** |
| P1-6 control protocol | 21/21 | **21/21 PASS** |
| OTA golden vectors | 9/9 | **9/9 OK** |
| P2-1 staging | 48/48 | **48/48 PASS** |
| P2-2 package | 102/102 | **102/102 PASS** |

BCB 宿主测试以 `-Wall -Wextra -Werror` 编译通过（零警告）。

## 3. CMake 四模式 configure 与三种非法双开

生成器按本机既有经验用 `Unix Makefiles`（Ninja 在本机首个 job 前挂起），
构建目录用短路径 `D:/w/*` 并带 `-DCMAKE_OBJECT_PATH_MAX=1024`。

```bash
cmake -S MDK-ARM_F435/cmake-generated -B D:/w/<mode> -G "Unix Makefiles" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024 [switches]
```

| 配置 | 期望 | 实测 rc |
|---|---|---|
| default | 成功 | **0** |
| `-DP1_6_TEST_ENABLE=ON` | 成功 | **0** |
| `-DP2_1_TEST_ENABLE=ON` | 成功 | **0** |
| `-DP2_2_TEST_ENABLE=ON` | 成功 | **0** |
| P1-6 + P2-1 | configure 阶段 FATAL | **1** `P1-6 and P2-1 evidence harnesses are mutually exclusive` |
| P1-6 + P2-2 | configure 阶段 FATAL | **1** `P1-6 and P2-2 evidence harnesses are mutually exclusive` |
| P2-1 + P2-2 | configure 阶段 FATAL | **1** `P2-1 and P2-2 evidence harnesses are mutually exclusive` |

三种非法组合都在 configure 阶段硬失败（`message(FATAL_ERROR)`，
CMakeLists:54-62），不是构建期才炸。

## 4. 四模式 linker 预处理产物对照表

由各模式构建目录的 `X_Track_App_GCC_linker_script` /
`X_Track_Boot_linker_script` 目标生成后实读：

| 模式 | App control | Boot control | App `.ota_overlay` |
|---|---|---|---|
| default | 无 | 无 | 有（5 处引用 + 4 断言） |
| P1-6 | `P1_6_CTRL` | `P1_6_CTRL` | 有 |
| P2-1 | `P2_1_CTRL` | `P2_1_CTRL` | 有 |
| P2-2 | `P2_2_CTRL` | **无** | 有 |

与集成记录 §2 声明的表格逐格一致。

## 5. fresh Release 组合构建与产物差异归因

### 5.1 实测产物

```bash
cmake --build D:/w/rel --target X_Track_App_GCC X_Track_Boot --parallel
```

```text
X-Track-Boot.bin    = 14236 bytes
  sha256 = 5656466564891b54666325da4545f3f819ba38f50660ab4772809b5647135ab5   ← 与声明逐位一致
X-Track-App-GCC.bin = 563228 bytes
  sha256 = ad4781a650d820d33ecf095a2a7c0c4d4face465bf3c819b6d828b1ae4e10147
```

`validate_boot_artifact.py` 独立重跑，与声明字面一致：

```text
P1_1_BOOT_ASSERTIONS=PASS bin=14236 vector=0x08000000/0x20c msp=0x20058000 reset=0x080028a1
```

Boot 三个 LOAD 段 `R E` / `RW` / `RW`，**无 RWX**；14236 B = 13.90 KiB < 64 KiB。
App 首个 LOAD 为 `RWE`、并保留 newlib/short-wchar 等既有 warning：
**有 warning（626 条）、零 error**，本轮不粉饰为成功细节。

### 5.2 App 声明 563252 vs 实测 563228：如实报告并已定性

集成记录声明的 App 为 `563252 B / 719f959c…`，本轮实测 `563228 B /
ad4781a6…`。**哈希对不上，如实报告**，并已独立定位为构建环境噪声、非冲突
解决引入的内容差异，依据三条：

1. **绝对路径被编进镜像**。App 内含 4 条 LVGL `__FILE__` 绝对路径（Boot 内
   `grep` 命中 0，故 Boot 可复现）。本验收 checkout 目录名
   `acceptance-merge-52d0c33-20260730` 为 33 字符；`563252-563228 = 24 = 4×6`，
   恰为 4 条路径各差 6 字符。
2. **在 +6 字符路径下重建，size 精确命中 563252**：
   ```text
   checkout .cache/acceptance-merge-52d0c33-20260730-plus6
   X-Track-App-GCC.bin = 563252 bytes   ← 与声明的 size 完全一致
   X-Track-Boot.bin    = 14236 bytes    sha256 = 5656466564891b…（不随路径变化）
   ```
3. **App 镜像内含 `__DATE__`/`__TIME__`**（`USER/App/Version.h:76`、
   `USER/HAL/HAL_FaultHandle.cpp:29,193`），故 App 的 sha256 **按构造不可
   复现**，两次不同时刻的构建必然不同哈希。这解释了为何 size 能对上而
   sha256 不能。Boot 无此依赖，因而 Boot 哈希逐位可复现。

结论：App 的 size 差异 100% 归因于构建路径长度，剩余哈希差异归因于
`__TIME__` 时间戳；两者都不指向合并内容缺陷。**Boot 作为无路径、无时间戳
依赖的产物，其 sha256 与声明逐位一致**，是本轮更强的证据。

### 5.3 与 P2-1/P2-2 验收记录 Boot 14228 / App 563188 的差异来源

按任务书要求逐项归因。先在**同长度路径**（40 字符）下重建两个父提交，消除
路径变量后同台比较：

| 提交 | Boot size | Boot sha256 |
|---|---|---|
| 基线 `bd9f4da` | **14208** | — |
| 父1 `9a2f27f`（P1-6） | **14216**（基线 +8） | c42b503a… |
| 父2 `2374519`（P2） | **14228**（基线 +20） | 50e651c6… |
| 合并 `52d0c33` | **14236** | 5656466564891b… |

**Boot 尺寸完全可加**：`14208 + 8 + 20 = 14236`。即合并 Boot 恰好等于基线
加上两侧各自的增量，两侧贡献都在、且没有第三方来源。

- P2 侧 +20 B 来自 `boot/src/boot_fw_header.c`(+33/-18) 与
  `boot/include/boot_fw_header.h`(+7)，属 P2-2 的 fw_header 复用改动。
- P1-6 侧 +8 B 来自 `boot/src/boot_state_machine.c`(+33/-3) 中一处
  **无条件**控制流改写：原 `if (erase(...) != 0 || program(...) != 0)` 的
  短路表达式被拆成独立 `if` 块以便插入 checkpoint。checkpoint 本身在
  `P1_6_TEST_ENABLE` 未定义时经
  `#define boot_p1_6_checkpoint(...) ((void)0)`（`boot/include/boot_p1_6_test.h`）
  完全消除，但拆分后的分支结构留在生产码里，产生这 8 B。这是 P1-6 侧代码
  本身的性质，**不是冲突解决引入的**——三个冲突文件都不含 Boot C 代码。

App 侧同样在同长度路径下比较：合并 `563228` **等于** 父2 `563228`，逐字节
diff 仅 93 B 差异、聚成 6 簇，全部落在
`__FILE__` 路径串与 `__TIME__` 时间戳上（实读簇内容：
`Jul 30 2026\n22:58:45` vs `Jul 30 2026\n23:46:16`、`23:00:02` vs `23:47:44`），
无一处落在代码或数据段。即 P1-6 对 App 的唯一源码改动
（`USER/HAL/HAL_EEPROM.cpp` 的 `p1_6_capture_confirmed_bcb`）确实被
`#if defined(P1_6_TEST_ENABLE)` 完整包裹，生产构建零占用。

最后在 P2 验收记录**原始 checkout** `.cache/checkout-B-P2-20260729` 内重建，
逐位复现该记录的两个数字：

```text
X-Track-Boot.bin    = 14228 bytes
  sha256 = 50e651c62e01c58e29f6c4ab4cdb3da849d2ba04c42733e506c322bb500d6e77  ← 与 P2 验收记录逐位一致
X-Track-App-GCC.bin = 563188 bytes                                          ← 与 P2 验收记录 size 一致
```

Boot 哈希与 P2-1/P2-2 验收记录完全相同，证明该记录的产物可复现、本轮比较
基准可靠。

**归因结论**：`14228 → 14236` 的 8 B 与 `563188 → 563228` 的 40 B 全部解释
完毕——8 B 来自 P1-6 侧 Boot 状态机的无条件分支拆分，40 B 来自 App 的
`__FILE__` 路径长度（P2 记录的 checkout 目录名比本轮短）。差异只来自 P1-6
侧改动与构建环境，**没有一个字节来自冲突解决的意外**。

## 6. 状态对账与红线复核

- 合并后 §1 总表：`P1 进行中 5/6`、`P2 进行中 2/6`，与集成记录声明一致。
- **P1-6 保持 `进行中`**（认领 Codex / 2026-07-29，14 AUTO 点通过、6 个物理
  断电点待用户配合）。父2 侧该卡为 `待办`，合并正确取用了父1 的权威状态。
- P2-1 / P2-2 均为 `完成`，证据栏指向既有验收记录，未被本轮改动。
- `git diff --name-only` 对 `PLAN-OTA.md` 与 `docs/ota-binary-contracts.md`
  在两个父方向上均为空 → **冻结契约未被合并触碰**。
- §9 变更登记表仍为 1 行（P1-5 那条），本轮未发现需要新登记的契约矛盾。
- 板面 `PLAN-OTA-EXEC.md` 相对父2 仅 `4 insertions / 3 deletions`，改动面
  局限于 P2 行与 P2-1/P2-2 两卡，无越界编辑。

## 7. 逐条判据结论

| # | 判据 | 结论 |
|---|---|---|
| 1 | 三个冲突文件三方比对，两侧改动都存活、无一侧被整段覆盖 | **通过**（§1.1-1.2、1.7；唯一非 IDENTICAL 处已证为 P1-6 未修改区，无语义丢失） |
| 2a | App 三段 control 区 0x200 / 0x80 / 0x800 都在 | **通过**（§1.3） |
| 2b | P2 `.ota_overlay` 地址与大小断言完整保留 | **通过**（§1.4，四模式 4/4） |
| 2c | Boot 保留 P1-6 `0x200` 与 P2-1 `0x80`，P2-2 不给 Boot 加控制区 | **通过**（§1.5，`P2_2` grep 命中 0） |
| 3 | 改名为 `OTA_TEST_LINKER_DEFINES` 后无引用点漏改，且同时喂 App/Boot | **通过**（§1.6，孤儿引用 0） |
| 4 | 宿主回归 8 项与声明一致 | **通过**（§2，16/19/27/96/21/9/48/102 全中） |
| 5 | 四模式 configure 成功 | **通过**（§3，rc 全 0） |
| 6 | 三种非法双开在 configure 阶段 FATAL_ERROR | **通过**（§3，rc 全 1 且报互斥） |
| 7 | 四模式 linker 预处理产物符合对照表 | **通过**（§4 逐格一致） |
| 8 | fresh Release 组合构建 + `validate_boot_artifact.py` | **通过**（§5.1；Boot size/sha256 与声明逐位一致，validator 字面一致） |
| 9 | Boot < 64 KiB 且三个 LOAD 均无 RWX | **通过**（§5.1，13.90 KiB / 无 RWX） |
| 10 | App 保留既有 warning 且如实声明 | **通过**（§5.1，有 warning 626 条、零 error，首个 LOAD `RWE` 为既有基线） |
| 11 | 声明哈希对不上须如实报告并归因 | **通过**（§5.2，已报告 App size/hash 差异并定性为路径长度 + `__TIME__`；Boot 哈希逐位一致） |
| 12 | 解释 14236/563252 与 P2 记录 14228/563188 的差异来源 | **通过**（§5.3，Boot 尺寸完全可加 14208+8+20=14236；差异只来自 P1-6 侧改动与构建环境，非冲突解决意外） |
| 13 | P1-6 保持 `进行中`、冻结契约未动 | **通过**（§6） |

## 8. 结论

**ACCEPT**。

人工冲突解决没有丢掉任何一侧的语义：三个冲突文件在四种模式下的 linker
预处理产物，除一处已证为「P1-6 未修改继承区」的有意取用外，与对应父方逐字节
相同；三段 control 区、`.ota_overlay` 断言、Boot 的 P2-2 缺席策略、以及
`OTA_TEST_LINKER_DEFINES` 改名后的全部引用点都正确。集成记录声明的 8 项宿主
回归、7 种 configure 结果、4 模式 linker 对照表均独立复现。

产物侧：Boot 的 size 与 sha256 与声明**逐位一致**，`validate_boot_artifact.py`
输出字面一致；App 的 size 差 24 B / 哈希不同已如实报告，并用 +6 字符路径重建
精确命中声明 size、加上镜像内 `__DATE__`/`__TIME__` 依赖两条证据定性为构建
环境噪声。与 P2 验收记录的 14228 / 563188 之差已完全归因：Boot 尺寸严格可加
（基线 14208 + P1-6 侧 8 + P2 侧 20 = 14236），8 B 属 P1-6 侧 Boot 状态机为插入
checkpoint 而做的无条件分支拆分，App 的 40 B 属路径长度差异——**没有字节来自
冲突解决的意外**。

遗留说明（不阻断本轮，供后续卡参考）：P1-6 侧那处无条件分支拆分会常驻生产
Boot 固件，虽经宿主 96/96 状态机回归覆盖且语义等价（短路 `||` 拆为顺序 `if`
不改变行为），但它属 P1-6 实现本体，最终判定应在 P1-6 卡自身的验收中收口，
本轮不代为放行。
