# P1-2 target 矩阵与受控 linker/scatter 源冻结决策

- 日期：2026-07-26
- 版本：**v3（2026-07-27，主会话二次复核收口；v1/v2 为历史修订）**
- 卡：P1-2 App 重定位双链接（本轮只做方案冻结，不写实现代码）
- 认领：Claude（方案冻结会话）
- 状态来源：`PLAN-OTA-EXEC.md`（P0 已完成 6/6，P1/P2 硬门槛已打开）
- 规范数值唯一权威来源：**`docs/ota-binary-contracts.md` §0.4/§10**（冻结，只读）；本文件与
  `Libraries/OTA/ota_layout.h` 均为其**实现侧**派生，不得取代或改写它
- 只读契约：`PLAN-OTA.md` v1.3.3、`docs/ota-binary-contracts.md` v1.1（本轮未修改，也不得修改）
- 前序研究：`docs/ota-exec-notes/P1-P2-layout-toolchain-issues-2026-07-26.md`
  （其 §0「P0 4/6、不可认领」为历史快照，本轮只沿用其技术分析，不沿用其门槛结论）

本轮不修改任何 linker/scatter/CMake/uvprojx/system/startup 实现文件，不执行 git 提交。
下面每一条都落到文件路径与 target 名称，供下一轮实现会话直接照抄。

### v3 收口摘要（主会话二次复核的五项修正）

| 审查意见 | 落点 | 结论 |
|---|---|---|
| 1. CI 闭锁语义自相矛盾 | §4.1.1、§5 A9c、§6 步 11 | job `if` 只保留 publish 条件，门闩移到首步；未就绪时明确硬失败，不再声称 skipped job 能输出错误 |
| 2. 实施步骤编号不一致 | §6 | 根副本只读反查与证据落盘合并为第 13 步；全文统一为 13 步 |
| 3. 验收编号不一致 | §5 | 完成门槛统一为 A1-A9d；A10 继续明确排除在 P1-2 之外 |
| 4. A9 命令未覆盖声明范围 | §5.1 | 16 个受控路径全部进入“新文件全文/既有文件新增行”检查，并补 layout/uvprojx/jlink/etu 结构化 allowlist 校验 |
| 5. `.noinit` 放置与 map 证据未冻结 | §3.1、§5 A6、§6 步 3/6/7 | 固定专用 `.ota_vtor_noinit`：GCC `NOLOAD`、AC5 `UNINIT`、保留/对齐/大小/map 证据明确，不落 overlay、不硬编码 RAM 地址 |

---

## 0. 本轮核实的仓库现状（决策依据，均为本会话实读）

| 事实 | 位置 | 对决策的影响 |
|---|---|---|
| GCC CI/VSCode 唯一使用的工程是 `MDK-ARM_F435/cmake-generated/` | `.github/workflows/firmware-build.yml:61`（`CMAKE_PROJECT_DIR`）、`.vscode/tasks.json:10-13` | 受控 App linker 必须被这棵树引用，其他副本一律不参与 |
| 该工程 linker 仍是旧布局 | `MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld:11` `FLASH ORIGIN=0x08000000, LENGTH=0x100000` | 现产物不可作 OTA App |
| 该 linker 无 `.fw_header`、无向量表尺寸断言 | 同文件 `SECTIONS` 仅 `.isr_vector > FLASH` | 契约 §1 落位缺失 |
| 仓库另有一份同名旧 linker 且 RAM 口径不同 | `cmake/generated_linker.ld:12` `RAM LENGTH=0x60000`（cmake-generated 版为 `0x58000`） | 漂移风险 4.10 已证实；必须明确"不参与构建" |
| 根 `CMakeLists.txt` 引用的是根 `cmake/generated_linker.ld` | `CMakeLists.txt:20` | 根工程不是 CI 入口，属历史副本 |
| CMake 目标名/产物名单一 | `cmake-generated/CMakeLists.txt:9,22-25`：`project("X-Track")`、`X-Track.elf/hex/bin/map`；CI 构建 `--target X_Track` | 必须 per-target 拆分产物名 |
| AC5 只有一个 Keil target，scatter 指向生成目录 | `MDK-ARM_F435/proj.uvprojx:10` `<TargetName>X-Track</TargetName>`、`:374` `<ScatterFile>.\Objects\X-Track.sct</ScatterFile>` | scatter 位于 `Objects/`（`.gitignore:22` 已忽略，`git ls-files` 未跟踪）→ 不可复现 |
| 该 scatter 实际是手工维护的 | `MDK-ARM_F435/Objects/X-Track.sct` 文件头中文注释明确"手动维护，勿勾选 Use Memory Layout from Target Dialog"，`umfTarg=0` | 内容有价值（RAMCODE/RW_IRAM2 语义），需迁出到受控路径而不是重写 |
| AC5 增量脚本硬编码单一 dep/lnp/输出 | `MDK-ARM_F435/build_f435.ps1:69-70`（`Objects\proj_X-Track.dep`、`Objects\X-Track.lnp`） | 新 target 必须参数化，否则会误编旧布局 |
| `VECT_TAB_OFFSET` 全局写死 0 | `MDK-ARM_F435/RTE/Device/-AT32F435RGT7/system_at32f435_437.c:38`，`:100` 写 `SCB->VTOR = FLASH_BASE \| VECT_TAB_OFFSET` | 不能全局硬改成 0x10000（boot/legacy 会错） |
| 该 system 文件被两条工具链共用 | uvprojx `:5019` RTE 实例；`cmake-generated/CMakeLists.txt:136` 直接引用同一路径 | 用编译期宏按 target 选择，是唯一不复制文件的做法 |
| 向量表段由 linker 定位，startup 无绝对地址 | `cmake/sources/startup_at32f435_437_gcc.S:15` `.section .isr_vector`；AC5 `startup_at32f435_437.s` `AREA RESET, DATA, READONLY` + scatter `*.o (RESET, +First)` | **startup 文件无需改动**，改 linker/scatter 即可完成重定位 |
| 现有 J-Link 脚本写死 0x08000000 | `MDK-ARM_F435/cmake-generated/.vscode/jlink_flash_bin.jlink`、`.vscode/tasks.json` 多处 `X-Track.bin 0x08000000` | 必须新增 per-target 烧录脚本，旧脚本留给 legacy |
| 转换脚本不在仓库内 | `git ls-files` 无 `keil_uvprojx2cmake.py`；仅 `.claude/prompt-keil2cmake-portable.md` 描述其行为 | 方案 1（纳管转换脚本）成本高、不可立即验证 |

---

## 1. 决策一：target 矩阵（冻结）

矩阵为**穷举**：本仓库不允许存在任何未进入下表的固件 target。

| 逻辑 target | 工具链 | 工程内 target 名 | Flash ORIGIN/LENGTH | VTOR | 用途 |
|---|---|---|---|---|---|
| X-Track-Boot | GCC | CMake target `X_Track_Boot` | `0x08000000` / `0x10000` | `0x08000000`（`VECT_TAB_OFFSET=0`） | boot 骨架（P1-1 消费本卡冻结的 layout 源） |
| X-Track-App-GCC | GCC | CMake target `X_Track_App_GCC` | `0x08010000` / `0xF0000` | `0x08010000`（`VECT_TAB_OFFSET=0x10000`） | **OTA/CI 唯一正式产物**（`PLAN-OTA.md` §7） |
| X-Track-App-AC5 | AC5 | Keil `<TargetName>X-Track-App-AC5</TargetName>` | `0x08010000` / `0xF0000` | `0x08010000` | 本地硬件调试与对照；地址/VTOR/fw_header/RAM overlay 语义与 App-GCC **完全相同** |
| X-Track-Legacy-AC5 | AC5 | Keil `<TargetName>X-Track</TargetName>`（物理名不改） | `0x08000000` / `0x100000` | `0x08000000` | 仅迁移过渡；**不得用于 OTA 验收** |
| **X-Track-Legacy-GCC** | **GCC** | **CMake target `X_Track`（现有，物理名不改）** | **`0x08000000` / `0x100000`（旧生成 linker）** | **`0x08000000`** | **兼容目标：仅服务 `.vscode/tasks.json` 本地 GCC 调试与迁移期对照；不得用于 OTA 构建、发布或验收** |

### 1.1a 第五个 target：`X_Track`（Legacy-GCC）的定性（本轮审查补入）

前一版矩阵漏列了现有 GCC CMake target `X_Track`——它在 `cmake-generated/CMakeLists.txt` 中真实存在、
仍引用旧布局 `cmake/generated_linker.ld`（`0x08000000`/`0x100000`），并被 `.vscode/tasks.json`
的 12 处构建/烧录项与 `firmware-build.yml:155` 直接使用。留一个"矩阵外的模糊 target"正是
前序研究 §4.10 所指的假绿来源，故本轮**二选一取"保留并定性为兼容目标"**：

- 逻辑名 `X-Track-Legacy-GCC`，物理 CMake target 名保持 `X_Track`（理由同 §1.1：改名会同时打断
  `.vscode/tasks.json` 12 处引用与 PRE-4 已绿的 CI 路径，收益仅是措辞）。
- 定性：**兼容/过渡目标**。允许本地 VSCode 构建与调试，禁止参与 OTA 产物、Release 资产、CF 注册
  与任何 P1/P2 验收；A9b 要求 CI 的构建目标从它切到 `X_Track_App_GCC`。
- 退役条件（不在 P1-2 完成）：待 `X_Track_App_GCC` + `X_Track_Boot` 通过 P1-4/P1-5 真机启动闭环、
  且 `.vscode/tasks.json` 迁移到新 target 后，由主会话与用户确认后移除 `X_Track` 及其
  `generated_linker.ld` 引用。P1-2 只负责定性与隔离，不负责删除。
- 文件头标注：下一轮在 `cmake-generated/CMakeLists.txt` 的 `X_Track` target 定义处加注释
  "Legacy-GCC 兼容目标，旧 0x08000000 布局，禁止用于 OTA"。

### 1.1 Legacy-AC5 物理 target 名保持 `X-Track` 的理由

`X-Track-Legacy-AC5` 是矩阵中的逻辑名。物理 Keil target 名保持 `X-Track` 不改，因为：
`build_f435.ps1:69-70` 以 target 名派生 `proj_X-Track.dep` / `X-Track.lnp`，`AGENTS.md` 全篇的
UV4/armcc/armlink fallback 命令、351 个既有 `.o`、`Listings/X-Track.map`、addr2line 流程都绑定该名。
改名会让整条本机 AC5 应急链路失效，收益仅是文档措辞。

代价是"逻辑名 ≠ 物理名"，因此本决策要求：`PLAN-OTA-EXEC.md`、本文件、以及下一轮新增的
bootstrap/烧录脚本一律写明映射 `X-Track-Legacy-AC5 == Keil target "X-Track"`、
`X-Track-Legacy-GCC == CMake target "X_Track"`（两个 legacy 逻辑名共用相似物理名，务必标全）。
产物隔离要求（第 4 节）由输出目录/文件名保证，与 target 名无关，因此
"禁止新旧 target 共用 `X-Track.*` 产物"仍然成立。

### 1.2 Boot 只做 GCC

`PLAN-OTA.md` §7 与 P1-1 卡均要求 boot 为 GCC。本卡只负责让 boot 能引用同一套 layout 常量与
linker 片段，不建 AC5 boot target。

---

## 2. 决策二：受控 linker/scatter 源（选方案 2，附单一数值源）

**采纳方案 2：新增版本控制的稳定 linker/scatter 源，由 CMake/Keil target 显式引用。**
不采纳方案 1（纳管转换脚本/模板）作为本轮主路径。

理由：
1. 转换脚本 `keil_uvprojx2cmake.py` 不在仓库内（`git ls-files` 无命中，仅 `.claude/prompt-keil2cmake-portable.md` 记录其行为），纳管它属于"先补一个不可验证的外部工具再做 P1-2"，会把 P1-2 阻塞在与 OTA 无关的工具迁移上。
2. 该脚本的定位是"从 uvprojx 内存区域生成 fallback linker"（`conversion-report.json` 亦如此标注）。OTA 布局不是 uvprojx 里的信息（boot/app 双区、`.fw_header`、overlay 断言都不来自 Keil 内存对话框），继续走"生成"路线会让契约受一个 GUI 字段摆布。
3. 方案 2 落地后，`cmake-generated/cmake/generated_linker.ld` 退化为"只服务 legacy/历史"的生成物，OTA 产物不再依赖任何生成物；这直接关闭前序研究 §4.4/§4.10 两个风险。

### 2.1 实现侧单一来源：`Libraries/OTA/ota_layout.h`

**权威层级（本轮审查修正术语）**：

| 层 | 文件 | 地位 |
|---|---|---|
| 规范数值唯一权威 | `docs/ota-binary-contracts.md` §0.4/§10 | **冻结契约**。`BOOT_ORIGIN`/`APP_ORIGIN`/`FW_HEADER_OFFSET`/overlay 边界等规范值的唯一定义点；改动只走看板 §9 回审 |
| 实现侧单一来源 | `Libraries/OTA/ota_layout.h` | 契约数值在 C/linker/scatter 侧的**唯一转录点**，供 linker/scatter/C/烧录脚本引用，避免各处重复写字面量 |

`ota_layout.h` **不定义、不取代、不修改**契约：它只是把契约 §0.4/§10 已冻结的数值转录成宏，
每个宏须在注释中标注其契约出处（如 `/* contracts §0.4 APP_ORIGIN */`）。
若两者出现不一致，以 `docs/ota-binary-contracts.md` 为准，并按看板 §0.4 置 `阻塞` 登记 §9，
禁止改契约去迁就实现。A9 的一致性检查方向同样是"头文件对齐契约"，而非反向。

新增纯 `#define` 头（ASCII，仅宏，不含 C 语句，可被 C/C++、armcc 的 scatter 预处理器、GCC 的
`-E` 链接脚本预处理同时包含）：

```
Libraries/OTA/ota_layout.h      # 新增：BOOT_ORIGIN/APP_ORIGIN/长度/FW_HEADER_OFFSET/overlay 边界
```

内容口径（数值只允许引用 `docs/ota-binary-contracts.md` §0.4/§10，不新增契约）：
`OTA_BOOT_ORIGIN=0x08000000`、`OTA_BOOT_LENGTH=0x10000`、`OTA_APP_ORIGIN=0x08010000`、
`OTA_APP_LENGTH=0xF0000`、`OTA_FW_HEADER_OFFSET=0x400`、`OTA_FW_HEADER_SIZE=96`、
`OTA_VECTOR_MAX=0x400`、`OTA_RAM_ORIGIN=0x20000000`、`OTA_RAM_LENGTH=0x58000`、
`OTA_OVERLAY_ORIGIN=0x20058000`、`OTA_OVERLAY_LENGTH=0x28000`。
`FW_HEADER_ADDR` 不定义（契约标为派生值，由 `ORIGIN+OFFSET` 得出）。

四方共享方式：
- GCC linker：`cmake/linker/x-track-app-gcc.ld.S`、`x-track-boot-gcc.ld.S` 用 `#include "ota_layout.h"`，构建时经 `arm-none-eabi-gcc -E -P -x assembler-with-cpp` 预处理成 `.ld`（STM32/Zephyr 通用做法）。
- AC5 scatter：`MDK-ARM_F435/scatter/X-Track-App-AC5.sct` 首行写 `#! armcc -E -I ../../Libraries/OTA` 并 `#include "ota_layout.h"`（armlink 官方支持的 scatter 预处理）。
- C/C++ 运行时（VTOR 自检、boot 解析、`.fw_header` 占位对象）直接 `#include "OTA/ota_layout.h"`。
- Python 侧（`Tools/etu_pack.py` 已冻结 `FW_HEADER_OFFSET=0x400`，本卡不改）→ 由验收矩阵第 5 节的一致性检查把两边对齐，而不是再写一份数字。

**红线（限定在受控文件集内）**：除 §5.1 明列的不可预处理格式精确 allowlist 外，本卡新增/修改的
OTA 地址/长度/偏移不得写裸字面量，一律引用 `ota_layout.h` 的宏。

这条红线**不是**全仓禁令。`0x400` 等数值在本仓库有大量与 OTA 无关的合法用途，实测：全仓
含 `0x400` 的文件 45 个，剔除 vendor/第三方后仍有 10 个属于合法命中，例如
`MDK-ARM_F435/RTE/Device/-AT32F435RGT7/at32f435_437_flash.c`（flash 页操作）、
`MDK-ARM_F435/Platform/Core/at32_sdio.h`、`MDK-ARM_F435/Platform/middlewares/usbd_class/hid_iap/hid_iap_class.h`、
`USER/App/Utils/lv_img_png/PNGdec/src/zutil.h`、以及 F403A 的 `system_at32f4xx.c`。
把这些纳入判定会让 A9 永远无法通过，属不可执行的验收项。A9 的精确口径见第 5 节。

### 2.2 受控源文件清单（下一轮新增，路径冻结）

```
Libraries/OTA/ota_layout.h                     # 数值单一来源（宏）
Libraries/OTA/fw_header_placeholder.c          # 96B .fw_header 占位对象（AC5+GCC 通吃）
Libraries/OTA/ota_vtor_check.c                 # App 启动前 VTOR 自检与取证标记
Libraries/OTA/ota_vtor_check.h                 # 自检接口与 map 可见标记声明
cmake/linker/x-track-app-gcc.ld.S              # App GCC 受控 linker 源（预处理前）
cmake/linker/x-track-boot-gcc.ld.S             # Boot GCC 受控 linker 源（P1-1 消费）
MDK-ARM_F435/scatter/X-Track-App-AC5.sct       # App AC5 受控 scatter 源（预处理式）
```

- `cmake/linker/` 为新目录；不复用根 `cmake/`（其 `generated_linker.ld` 是待退役副本）。
- `MDK-ARM_F435/scatter/` 为新目录；**不再**把 App scatter 放在 `MDK-ARM_F435/Objects/`（被 `.gitignore:22` 忽略、且 uVision 可重新生成）。
- Legacy 的 `MDK-ARM_F435/Objects/X-Track.sct` 保持原样不动（不迁移、不删除），避免影响本机 AC5 应急链路；它只服务 `X-Track-Legacy-AC5`。

### 2.3 明确禁止（写入验收）

- 禁止把 `MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld` 改成永久 App 源（下次转换会覆盖）。
- 禁止把 `MDK-ARM_F435/Objects/X-Track.sct` 改成 App 永久源（未跟踪、可被 uVision 重生成）。
- 禁止让根 `CMakeLists.txt` / 根 `cmake/generated_linker.ld` 参与 OTA 产物；它们 RAM 口径已漂移（`0x60000` vs `0x58000`）。
  **本卡不修改这两份历史副本**（审查意见 4：原步骤 13 要改它们，但看板 §范围未含，属范围矛盾，已删除该步骤）。
  改为**引用反查取证**：证明 CI 与 VSCode 均不引用它们，因此无需注释、无需删除也不会污染 OTA 产物：
  - `firmware-build.yml:61` 固定 `CMAKE_PROJECT_DIR: MDK-ARM_F435/cmake-generated`，CI 从不 configure 仓库根；
  - `.vscode/tasks.json` 全部 `-S ${workspaceFolder}/MDK-ARM_F435/cmake-generated`，本机构建亦不走根工程。
  是否最终删除属独立的仓库清理事项，留主会话与用户决定，不进 P1-2。

---

## 3. 决策三：VTOR / `VECT_TAB_OFFSET` 按 target 选择

`system_at32f435_437.c` 被 GCC 与 AC5 共用（`cmake-generated/CMakeLists.txt:136` 与 uvprojx RTE `:5019` 指向同一文件），因此不复制文件、不全局硬改，改为宏选择：

- 在 `system_at32f435_437.c:38` 处把 `#define VECT_TAB_OFFSET 0x0` 改为：
  当定义 `OTA_TARGET_APP` 时取 `ota_layout.h` 的 `(OTA_APP_ORIGIN - OTA_BOOT_ORIGIN)`（即 `0x10000`），否则保持 `0x0`。
- `OTA_TARGET_APP` 的注入点：CMake `X_Track_App_GCC` 的 `target_compile_definitions`；Keil `X-Track-App-AC5` target 的 `<Define>`（现有 `X-Track` target 的 `<Define>` 在 `proj.uvprojx:341`，保持不含该宏）。
- 结果：Boot=0、Legacy=0、App-GCC/App-AC5=0x10000，数值来自同一个头。
- App 启动自检：读 `SCB->VTOR` 与 `OTA_APP_ORIGIN` 比对，不一致即 fail-closed。位置与失败行为已冻结，见 §3.1。

**startup 文件不动**：GCC 的 `.isr_vector`（`cmake/sources/startup_at32f435_437_gcc.S:15`）与 AC5 的
`AREA RESET`＋scatter `*.o (RESET, +First)` 都由 linker 定位，改 ORIGIN 即自动落到 `0x08010000`。

### 3.1 VTOR 自检位置与失败行为（冻结）

**位置：`USER/main.cpp` 的 `main()` 内，`Core_Init()` 之前的第一条语句。**

本会话实读确认的调用链：`USER/main.cpp:102` `main()` → `Core_Init()`
（`MDK-ARM_F435/Platform/Core/mcu_core.c:26`）→ `system_clock_config()` →
`nvic_priority_group_config()` → `Delay_Init()`（`Platform/Core/delay.c:42`）→
`SysTick_Config(SYSTICK_LOAD_VALUE)` + `NVIC_SetPriority(SysTick_IRQn, ...)`。

即 `Core_Init()` 一旦返回，SysTick 已配置并使能中断。若此时 VTOR 仍指向错误的向量表
（boot 的 `0x08000000` 或未被 `SystemInit()` 正确改写的值），第一个 SysTick 中断就会取到
错误的处理函数地址，表现为立刻 HardFault 或静默跳进 boot 的 handler——错误将无法归因，
也来不及留下任何标记。因此自检必须早于 `Core_Init()`，这是本决策唯一允许的落点。

放弃 `USER/App/App.cpp` 与 `USER/HAL/HAL.cpp` 作为落点：两者都在 `setup()` 内（`main.cpp` 的
`Core_Init()` 之后）才被调用，已过 SysTick 使能点，不满足上述要求。

**失败行为（fail-closed，按顺序执行）：**

1. `__disable_irq()`——先阻止任何中断经错误向量表分发。
2. 写取证标记：`SEGGER_RTT_Init()` 在 `setup()` 内才执行（`main.cpp` 的 `setup()` 首行），
   自检点上 RTT **尚未初始化**，因此不能依赖 `SEGGER_RTT_printf` 留证。改为两级标记：
   - 一级（必留，不依赖任何初始化）：把实测 `SCB->VTOR` 与期望值 `OTA_APP_ORIGIN` 写入一对
     位于专用 `.ota_vtor_noinit` 段的全局变量（如 `g_ota_vtor_actual` / `g_ota_vtor_expected`），
     供 J-Link `mem32` 按 map 地址直接复读。这不是散落在普通 `.bss` 的变量：GCC linker
     必须以 `NOLOAD` 输出该段并用 `KEEP()` 收集输入段；AC5 scatter 必须以独立 `UNINIT`
     执行区显式选择该输入段，变量声明使用 AC5 可识别的 `zero_init`/`used` 语义且在自检代码中
     有真实写引用（不得给 scatter 生搬 GNU `KEEP()` 语法）。这样启动代码不会清零/复制它。
     段须 4 字节对齐、至少容纳两个 `uint32_t`，不得放入
     `.sram_ext` overlay；map 必须同时给出段地址/大小和两个符号地址。取证时只使用当前
     target 的 map 地址读取，不在源码或脚本中另写绝对 RAM 地址。这是复位后唯一稳定可取的
     证据，取证方式与 P0-5 的 `g_qspi_ota_disabled`/`g_qspi_jedec_id` 完全一致（AGENTS.md 已验证可行）。
   - 二级（尽力而为）：就地调用 `SEGGER_RTT_Init()` 后 `SEGGER_RTT_printf(0, ...)` 输出
     `OTA: VTOR mismatch actual=0x%08X expected=0x%08X`。此调用只写 RAM 控制块、不依赖时钟或
     外设，在 `Core_Init()` 之前可用；但因其早于正常初始化，**证据判定以一级标记为准**，
     RTT 行只作辅助。
3. 进入 `for(;;) __WFI();` 死循环，**不继续启动 App**。不复位、不喂狗、不跳 boot：
   继续跑会让错误 VTOR 下的中断随机破坏状态，自动复位会形成无日志的复位循环，
   两者都比停机更难诊断。停机后由 J-Link `halt`+`mem32` 取一级标记。

VTOR 匹配时自检无副作用、无输出，正常继续 `Core_Init()`。

A6 的运行时判定据此拆为两条：匹配路径在受控调试启动下读到 `SCB->VTOR == 0x08010000` 且
不进入死循环；失败路径需人为注错（临时把期望值改为错误值重编一次）验证确实停机且
一级标记可被 `mem32` 复读，取证后立即恢复。

---

## 4. 决策四：产物、dep/lnp、烧录脚本命名隔离（冻结）

### 4.1 GCC 侧

`cmake-generated/CMakeLists.txt` 现在把 `X-Track.elf/hex/bin/map` 硬编码为单一名（`:22-25`），CI 也按此名上传（`firmware-build.yml:164-182`）。冻结为：

| target | 输出目录 | elf/hex/bin | map |
|---|---|---|---|
| `X_Track_App_GCC` | `<build>/app-gcc/` | `X-Track-App-GCC.{elf,hex,bin}` | `X-Track-App-GCC.map` |
| `X_Track_Boot` | `<build>/boot/` | `X-Track-Boot.{elf,hex,bin}` | `X-Track-Boot.map` |
| 现有 `X_Track`（legacy GCC，旧布局） | `<build>/`（不变） | `X-Track.{elf,hex,bin}`（不变） | `X-Track.map`（不变） |

保留现有 `X_Track` 目标名与产物名不变，是为了让 `.vscode/tasks.json`（依赖 `X_Track`、`X-Track.elf`）
与 PRE-4 已绿的 CI 在切换期间不断裂；但 **OTA 正式产物从此只认 `X-Track-App-GCC.bin`**。

CI 切换（`firmware-build.yml`）：`--target X_Track` → `X_Track_App_GCC`，产物路径与
`sha256/bin_size` 计算、artifact 上传一并改到 `X-Track-App-GCC.bin/hex/elf/map`。这属于 P1-2
必须同轮完成的一步，否则 CI 会继续产出旧布局"看起来绿"的产物（前序研究 §4.10）。为此本轮把
`firmware-build.yml` 追加进 P1-2 的范围。**但正式发布链必须同轮上锁，见 §4.1.1。**

### 4.1.1 P1-2 阶段的正式发布保护（冻结）

审查意见 5 指出的风险成立：P1-2 完成后 `X-Track-App-GCC.bin` 是一个**不可独立启动**的镜像——
它的向量表在 `0x08010000`，而 Cortex-M4 复位从 `0x08000000` 取 MSP/PC。此时 boot（P1-1/P1-4）
与 bootstrap（P1-5）都还不存在，任何设备拿到这个包都会变砖。而现有 workflow 的
`workflow_dispatch(publish=true)` 会直接建 GitHub Release 并注册 CF 正式候选
（`firmware-build.yml:192` 的 job 条件 + `:223` Create Release + `:282` Register candidate）。

**P1-2 阶段如何阻止正式发布**：`register-cloudflare` job 的 `if` **保持**现有
`workflow_dispatch && publish == 'true'`，不得把 `vars.OTA_BOOT_CHAIN_READY` 并入该 `if`；否则变量
未设置时整个 job 会被 GitHub Actions 静默标成 skipped，job 内不可能再输出错误。改为在该 job
的第一步（checkout/download 之前）读取仓库变量 `vars.OTA_BOOT_CHAIN_READY`，仅当其精确等于
`true` 才继续；未就绪时打印 `::error` 说明"boot 链未完成，App 镜像不可独立启动，禁止正式发布"
并 `exit 1`。变量默认未配置即按空值/false 处理。

push/PR 路径本来就不进该 job（PRE-3 已验收），因此 P1-2 阶段的净效果是：构建与 artifact 正常；
`publish=false` 时该 job 按原语义跳过；`publish=true` 时 job 必须实际启动并在首步**明确硬失败**，
不能静默跳过。选择"首步门闩 + 硬失败"而不是删除 job，是为了保留 PRE-3/PRE-4 已验收的正式链
结构，避免 P4 再重建一遍。

**何时解锁**：`OTA_BOOT_CHAIN_READY=true` 由用户在 P1-5 真机 bootstrap 通过、且 P4-1 正式发布链
演练完成后配置（人工配合点，登记进看板 §1 人工点总览）。解锁前提是 boot 已能出厂预置或
bootstrap 手册已可执行——即设备侧存在能引导 `0x08010000` 的 boot。P1-2 本轮只上锁，不解锁。

**三类产物的语义（冻结，禁止混用）**：

| 产物 | 头部状态 | 语义 | 允许用途 |
|---|---|---|---|
| `X-Track-App-GCC.bin`（CI 构建直出） | `0x400` 处为 `0xFF` 占位 | **未 finalize**，无 `ETFW`/SHA/CRC | 仅 artifact 调试、A5 占位态取证；**禁止**发布、禁止入 .etu、禁止作恢复资产 |
| `X-Track-App-GCC.bin` 经 `etu_pack.py --finalize` | `0x400` 处为真实 96B 头 | **finalized**，`--verify-fw-header` 通过 | 唯一可入 `.etu`、可作 recovery 资产本体（P4-1 制包顺序①-⑥）的镜像 |
| `X-Track-App-GCC.hex` / `.elf` | 与构建直出同源，占位头 | 调试/烧录辅助 | 本机 J-Link 与调试；**禁止**作为正式恢复资产或 Release 交付的固件本体 |

因此 P4-1 的制包顺序不变：构建占位头 bin → `--finalize` → 组包。hex/elf 永远是占位头产物，
`fromelf`/`objcopy` 不会回写 finalize 结果，把占位头 hex 当恢复资产发布会得到一个
`magic != ETFW` 必被 boot 拒绝的镜像。A9b 的 CI 断言须包含"发布路径引用的 bin 已 finalize"。

### 4.2 AC5 侧

| target | Objects 目录 | 产物 | dep / lnp | map |
|---|---|---|---|---|
| `X-Track-App-AC5` | `MDK-ARM_F435\Objects-App-AC5\` | `X-Track-App-AC5.axf/.hex`、`Track-App-AC5.bin` | `proj_X-Track-App-AC5.dep` / `X-Track-App-AC5.lnp` | `Listings-App-AC5\X-Track-App-AC5.map` |
| `X-Track`（legacy） | `MDK-ARM_F435\Objects\`（不变） | `X-Track.axf/.hex`、`Track.bin`（不变） | `proj_X-Track.dep` / `X-Track.lnp`（不变） | `Listings\X-Track.map`（不变） |

`build_f435.ps1` 增加 `-Target` 参数（默认 `X-Track`，保持 AGENTS.md 现有命令零改动），
由它派生 dep/lnp/Objects/Listings 路径与 `fromelf` 输出名。这是本卡对该脚本的**唯一**改动方向；
不改其 dep/lnp 复用机制（AGENTS.md 红线：禁止手写编译/链接参数）。

### 4.3 烧录脚本

新增（不覆盖旧脚本）：

```
Tools/jlink/flash-boot.jlink            # boot @ OTA_BOOT_ORIGIN
Tools/jlink/flash-app-gcc.jlink         # App-GCC bin @ OTA_APP_ORIGIN
Tools/jlink/flash-app-ac5.jlink         # App-AC5 bin @ OTA_APP_ORIGIN
```

现有 `MDK-ARM_F435/cmake-generated/.vscode/jlink_flash_*.jlink` 与 `.vscode/tasks.json` 中写死
`X-Track.bin 0x08000000` 的项保留给 legacy，不改语义。`.jlink` 不支持宏，因此这三个脚本是
**烧录脚本域中唯一允许出现地址字面量的位置**，且必须在文件头注释里写明"数值来源 `Libraries/OTA/ota_layout.h`"，
并由第 5 节 A9 验收项做一致性检查。P1-5 的一次性 bootstrap 脚本在此基础上组合，不另立地址源。

---

## 5. 决策五：P1-2 扩展验收矩阵（冻结）

置 `完成` 前须逐项留证；A1-A9d 属 P1-2，A10 明确不属 P1-2。

| 编号 | 验收项 | 判定方式（命令/证据） |
|---|---|---|
| A1 | GCC App Flash `ORIGIN=0x08010000`、`LENGTH=0xF0000` | `X-Track-App-GCC.map` 的 memory 配置摘录；预处理后 `.ld` 的 `MEMORY` 块 |
| A2 | AC5 App 同址同长 | `X-Track-App-AC5.map` 的 `Load Region LR_IROM1 (Base: 0x08010000, Size ... Max: 0x000f0000)` 摘录 |
| A3 | `.isr_vector` 起于 `0x08010000` 且 `SIZEOF(.isr_vector) <= 0x400` | GCC：map 段表 + linker `ASSERT` 存在（人为超限时链接失败可复现）；AC5：向量表独占执行区上限 0x400，超限 armlink 报错 |
| A4 | `.fw_header` 落位 `0x08010400`、大小恰 96B | 两侧 map 段表；`arm-none-eabi-nm`/`fromelf` 符号地址 |
| A5 | raw bin 中 header 位于文件 offset `0x400` | 对 `X-Track-App-GCC.bin` 与 `Track-App-AC5.bin` 读 `0x400..0x45F`：占位态为 `0xFF` 填充；经 `Tools/etu_pack.py --finalize` 后 `0x400..0x403 == "ETFW"`、`--verify-fw-header` 通过（双零 SHA + header CRC32），且 `0x000..0x3FF` 向量区逐字节不变 |
| A6 | VTOR 口径：Boot/Legacy `VECT_TAB_OFFSET=0`（实际 VTOR=`0x08000000`），App `VECT_TAB_OFFSET=0x10000`（实际 VTOR=`0x08010000`） | 静态：预处理产物/编译期宏展开与实际 VTOR 对号；自检代码位于 `USER/main.cpp` 的 `Core_Init()` **之前**（§3.1 冻结落点），fail-closed 分支与 RTT-前取证标记均在；GCC map 显示 `.ota_vtor_noinit` 为 `NOLOAD`，AC5 map 显示对应执行区为 `UNINIT`，两侧均列出段地址/大小和两个标记符号。运行时：debugger 受控启动下读到 `SCB->VTOR=0x08010000`，失败路径注错后按当前 map 地址读取 `g_ota_vtor_actual`/`g_ota_vtor_expected`，确认停机且标记可复读 |
| A7 | GCC/AC5 RAM 与 `.sram_ext`/overlay 边界一致 | 两侧 map：主 RAM `0x20000000` 长 `0x58000`；overlay 区 `0x20058000` 长 `0x28000`；GCC `ASSERT(SIZEOF(overlay) <= 0x28000)` 存在；与契约 §10.1/§10.2 逐项对号 |
| A8 | 各 target 产物完全隔离 | 目录/文件清单 + 时间戳：构建 App 后 `Objects\X-Track.axf`、`<build>/X-Track.bin` 时间戳与哈希不变；App 产物不落 `X-Track.*` 名 |
| A9 | 无字面量漂移（**仅在受控文件集内判定**） | 见下方 A9 口径表：只 grep 本卡新增/修改的受控文件，宏名 + allowlist 判定；vendor/第三方/无关业务常量不纳入 |
| A9b | CI 只构建受控 App linker | `firmware-build.yml` 目标为 `X_Track_App_GCC`；干净 checkout run 绿并输出 `X-Track-App-GCC.bin` 的 size/sha256；构建后自动断言 A1/A3/A4/A5 静态项，失败即停止发布 |
| A9c | 正式发布闭锁（P1-2 阶段强制） | `register-cloudflare` 的 job `if` 只保留 `workflow_dispatch && publish == 'true'`；首步读取 `vars.OTA_BOOT_CHAIN_READY`，未精确为 `true` 时输出 `::error` 并硬失败，不得静默 skipped。P1-5 bootstrap 真机通过且 P4-1 演练绿后，才由 P4-1 置该变量 |
| A9d | 产物语义与 finalize 边界 | 构建直出的 `X-Track-App-GCC.bin` 为占位头；只有 `etu_pack.py --finalize` 后的 bin 可入 `.etu`/作 recovery 资产。hex/elf 永远是占位头，禁止作为正式恢复资产；CI 发布路径必须引用 finalized bin |
| A10 | **不属于 P1-2**：普通 J-Link `r`+`g` 启动 App | 明确排除。App 搬到 `0x08010000` 后复位仍从 `0x08000000` 取 MSP/PC，普通 reset/run 通过与否都不构成重定位验收。App 真实启动证据属 P1-4（boot 交接）与 P1-5（bootstrap）；P1-2 只允许 debugger 显式设置 MSP/VTOR/PC 的受限启动，且须在证据中标注为"受限调试启动，非正常启动链" |

其余不变的红线：AC5 与 GCC 允许不同的只有编译参数表达、scatter/LD 语法、代码尺寸、map 排版与调试信息；
地址、长度、向量偏移、fw_header 偏移/大小、RAM/overlay 边界、启动自检与交接契约必须相同。

### 5.1 A9 检查口径（修订：由"全仓禁止"改为"受控文件集 + allowlist"）

**修订原因（主会话审查意见 1，本轮实读复核）**：原口径"全仓 grep 禁止出现 `0x400`/`0xF0000`"不可执行。
`0x400` 在当前仓库有 45 个文件命中，剔除 vendor/第三方后仍有 10 个**合法且与 OTA 无关**的命中，例如
`MDK-ARM_F435/Platform/Core/at32_sdio.h`（SDIO 块长）、`RTE/Device/-AT32F435RGT7/at32f435_437_flash.c`
（flash 扇区常量）、`USER/App/Utils/lv_img_png/PNGdec/src/zutil.h`（zlib 缓冲）、
`MDK-ARM_F403A/**/system_at32f4xx.c`（F403A 另一工程）。这些不得纳入判定，否则 A9 永远不可能通过。

**受控文件集（A9 的唯一判定范围）**如下 16 个路径。新文件检查全文；既有文件
（CMake/uvprojx/system/build 脚本/main/workflow）只检查相对 `HEAD` 的新增或修改行，避免把
未由本卡触碰的 legacy 配置误判为新漂移。删除行不参与裸字面量判定，但须在正常 diff 审查中核对。

```
Libraries/OTA/ota_layout.h
Libraries/OTA/fw_header_placeholder.c
Libraries/OTA/ota_vtor_check.c
Libraries/OTA/ota_vtor_check.h
cmake/linker/x-track-app-gcc.ld.S
cmake/linker/x-track-boot-gcc.ld.S
MDK-ARM_F435/scatter/X-Track-App-AC5.sct
MDK-ARM_F435/cmake-generated/CMakeLists.txt        （仅本卡新增的 target 段）
MDK-ARM_F435/proj.uvprojx                          （仅本卡新增的 App-AC5 target 段）
MDK-ARM_F435/RTE/Device/-AT32F435RGT7/system_at32f435_437.c
MDK-ARM_F435/build_f435.ps1
USER/main.cpp                                      （VTOR 自检落点，见 §3.1）
.github/workflows/firmware-build.yml
Tools/jlink/flash-boot.jlink
Tools/jlink/flash-app-gcc.jlink
Tools/jlink/flash-app-ac5.jlink
```

**判定规则**：

| 检查 | 规则 |
|---|---|
| OTA 地址/长度字面量 | `0x08000000`、`0x08010000`/`0x0801_0000`、`0x10000`、`0xF0000`、`0x20000000`、`0x58000`、`0x20058000`、`0x28000` 在受控新增内容中一律使用 `OTA_*` 宏；只允许出现在下述精确 allowlist |
| `0x400` | 当语义为 fw_header 偏移或向量上限时，受控新增内容一律写 `OTA_FW_HEADER_OFFSET` / `OTA_VECTOR_MAX`；若既有文件新增了其它语义的 `0x400`，证据必须列出该行并说明语义，否则按违规处理 |
| allowlist（允许字面量，须带来源注释） | ① `Libraries/OTA/ota_layout.h`：实现侧唯一数值转录点，逐项对齐契约；② `MDK-ARM_F435/proj.uvprojx` 的新 `X-Track-App-AC5` target 中无法预处理的 IROM/TextAddress XML 字段，仅允许 App origin/length，须由 XML 查询与 `ota_layout.h` 对号；设备级 FlashDriver 全片范围属于现有芯片配置，不视为 OTA 布局重复定义；③ `Tools/jlink/*.jlink`：格式不支持宏，地址字面量须注明来源；④ `Tools/etu_pack.py`/`etu_unpack.py`：P0-2 已冻结，**不属于本卡写入范围**，只单独核对 `FW_HEADER_OFFSET=0x400`；⑤ `.md` 文档。`firmware-build.yml` 不豁免地址字面量，仅产物文件名不属于地址检查 |
| 不纳入判定 | `vendor/**`、`USER/App/Utils/**` 第三方库、`Simulator/**`、`MDK-ARM_F403A/**`、`bsdiff_lzma_AES128-main/**`、`MDK-ARM_F435/Platform/**`（除受控集列出者）、以及一切非本卡修改的业务常量 |

**可执行命令（证据须贴其原始输出）**：

```powershell
# 新文件查全文；既有文件只查相对 HEAD 的新增行。uvprojx/layout/jlink/etu 走下方结构化 allowlist 核对。
$newFiles = @(
  'Libraries/OTA/fw_header_placeholder.c',
  'Libraries/OTA/ota_vtor_check.c',
  'Libraries/OTA/ota_vtor_check.h',
  'cmake/linker/x-track-app-gcc.ld.S',
  'cmake/linker/x-track-boot-gcc.ld.S',
  'MDK-ARM_F435/scatter/X-Track-App-AC5.sct'
)
$trackedFiles = @(
  'MDK-ARM_F435/cmake-generated/CMakeLists.txt',
  'MDK-ARM_F435/RTE/Device/-AT32F435RGT7/system_at32f435_437.c',
  'MDK-ARM_F435/build_f435.ps1',
  'USER/main.cpp',
  '.github/workflows/firmware-build.yml'
)
$literalPattern = '(?i)\b(?:0x08000000|0x08010000|0x0801_0000|0x10000|0xF0000|0x20000000|0x58000|0x20058000|0x28000|0x400)\b'
$violations = @()
$presentNew = @($newFiles | Where-Object { Test-Path -LiteralPath $_ })
if ($presentNew.Count) {
  $violations += Select-String -LiteralPath $presentNew -Pattern $literalPattern
}
$current = ''
git diff --unified=0 HEAD -- $trackedFiles | ForEach-Object {
  if ($_ -match '^\+\+\+ b/(.+)$') { $current = $Matches[1]; return }
  if ($_ -match '^\+(?!\+\+\+)' -and $_ -match $literalPattern) {
    $violations += "$current`t$_"
  }
}
if ($violations.Count) { $violations; throw 'A9: controlled literals must use OTA_* macros' }

# ota_layout.h：所有实现侧数值定义逐项与冻结契约对号。
$expected = [ordered]@{
  OTA_BOOT_ORIGIN       = '0x08000000'; OTA_BOOT_LENGTH       = '0x10000'
  OTA_APP_ORIGIN        = '0x08010000'; OTA_APP_LENGTH        = '0xF0000'
  OTA_FW_HEADER_OFFSET  = '0x400';      OTA_FW_HEADER_SIZE     = '96'
  OTA_VECTOR_MAX        = '0x400';      OTA_RAM_ORIGIN         = '0x20000000'
  OTA_RAM_LENGTH        = '0x58000';    OTA_OVERLAY_ORIGIN     = '0x20058000'
  OTA_OVERLAY_LENGTH    = '0x28000'
}
$layout = Get-Content -LiteralPath 'Libraries/OTA/ota_layout.h' -Raw
foreach ($entry in $expected.GetEnumerator()) {
  $name = [regex]::Escape($entry.Key); $value = [regex]::Escape($entry.Value)
  if ($layout -notmatch "(?m)^\s*#define\s+$name\s+$value(?:[uUlL]*)\b") {
    throw "A9: ota_layout.h mismatch: $($entry.Key)=$($entry.Value)"
  }
}

# uvprojx：只校验无法引用 C 宏的 App-AC5 IROM/TextAddress 字段；scatter 仍是链接权威。
function HexValue([string]$value) { [Convert]::ToUInt32(($value -replace '^0x', ''), 16) }
[xml]$uv = Get-Content -LiteralPath 'MDK-ARM_F435/proj.uvprojx' -Raw
$app = @($uv.Project.Targets.Target) | Where-Object TargetName -eq 'X-Track-App-AC5'
if ($app.Count -ne 1) { throw 'A9: X-Track-App-AC5 target missing or duplicated' }
$mem = $app.TargetOption.TargetArmAds.ArmAdsMisc.OnChipMemories
$ld = $app.TargetOption.TargetArmAds.LDads
$cpu = [string]$app.TargetOption.TargetCommonOption.Cpu
if ($cpu -notmatch 'IROM\((0x[0-9A-Fa-f]+),(0x[0-9A-Fa-f]+)\)') {
  throw 'A9: uvprojx App-AC5 Cpu IROM fields missing'
}
$cpuOrigin = HexValue $Matches[1]; $cpuLength = HexValue $Matches[2]
if ($cpuOrigin -ne 0x08010000 -or $cpuLength -ne 0xF0000 -or
    (HexValue $mem.IROM.StartAddress) -ne 0x08010000 -or (HexValue $mem.IROM.Size) -ne 0xF0000 -or
    (HexValue $mem.OCR_RVCT4.StartAddress) -ne 0x08010000 -or (HexValue $mem.OCR_RVCT4.Size) -ne 0xF0000 -or
    (HexValue $ld.TextAddressRange) -ne 0x08010000) { throw 'A9: uvprojx App-AC5 IROM fields drifted' }

# jlink 与 P0-2 Python 常量是格式豁免，但仍须逐项一致。
$jlinkExpected = [ordered]@{
  'Tools/jlink/flash-boot.jlink'    = '0x08000000'
  'Tools/jlink/flash-app-gcc.jlink' = '0x08010000'
  'Tools/jlink/flash-app-ac5.jlink' = '0x08010000'
}
foreach ($entry in $jlinkExpected.GetEnumerator()) {
  $text = Get-Content -LiteralPath $entry.Key -Raw
  if ($text -notmatch [regex]::Escape($entry.Value) -or
      $text -notmatch 'Libraries/OTA/ota_layout\.h') { throw "A9: jlink mismatch: $($entry.Key)" }
}
foreach ($path in 'Tools/etu_pack.py','Tools/etu_unpack.py') {
  if (-not (Select-String -LiteralPath $path -Pattern '^FW_HEADER_OFFSET\s*=\s*0x400\b' -Quiet)) {
    throw "A9: frozen FW_HEADER_OFFSET drifted: $path"
  }
}
'A9_CONTROLLED_LITERAL_CHECK=PASS'
```

证据必须保留脚本原始输出与 `git diff --unified=0`；脚本通过只证明字面量未漂移，不能替代
对 `docs/ota-binary-contracts.md` §0.4/§10.1 的人工逐项复核。

---

## 6. 下一轮实施文件清单与顺序

按此顺序做，每步可独立编译验证；出现契约矛盾立即按看板 §0.4 置 `阻塞` 并登记 §9。

| 步 | 文件 | 动作 | 验证 |
|---|---|---|---|
| 1 | `Libraries/OTA/ota_layout.h` | 新增（纯宏，ASCII） | 被 C/C++ 与预处理器包含均无语法错误 |
| 2 | `Libraries/OTA/fw_header_placeholder.c` | 新增 96B `.fw_header` 占位（`0xFF` 填充，AC5/GCC 双语法） | 单独编译通过；`sizeof==96` 编译期断言 |
| 3 | `cmake/linker/x-track-app-gcc.ld.S` | 新增：App MEMORY/`.fw_header`@+0x400/向量 ASSERT/overlay ASSERT；RAM 与 overlay 沿用 `0x58000`+`0x28000`；加入 `.ota_vtor_noinit (NOLOAD)`、`KEEP`、对齐/大小断言 | 预处理产物人工核对；A6 map 段证据 |
| 4 | `MDK-ARM_F435/cmake-generated/CMakeLists.txt` | 加 `X_Track_App_GCC` target（含 `.ld.S` 预处理自定义命令、`OTA_TARGET_APP` 定义、per-target 产物名/目录）；保留现有 `X_Track` 不变 | `cmake --build ... --target X_Track_App_GCC` 成功 |
| 5 | `MDK-ARM_F435/RTE/Device/-AT32F435RGT7/system_at32f435_437.c` | `VECT_TAB_OFFSET` 改为按 `OTA_TARGET_APP` 选择（含 `ota_layout.h`） | Boot/Legacy 展开为 0、App 为 `0x10000` |
| 6 | `USER/main.cpp`（`main()` 内 `Core_Init()` **之前**，§3.1 冻结落点）+ `Libraries/OTA/ota_vtor_check.{c,h}` | 新增 VTOR 与 `OTA_APP_ORIGIN` 比对，按 §3.1 冻结的失败行为实现：`__disable_irq()` → 写一级标记 `g_ota_vtor_actual`/`g_ota_vtor_expected`（专用 `.ota_vtor_noinit` 输入段，供 `mem32` 按 map 复读）→ 二级 `SEGGER_RTT_Init()`+printf（辅助）→ `for(;;) __WFI()` 停机。**不自纠 VTOR、不复位、不喂狗**。仅 `OTA_TARGET_APP` 编译期生效 | 编译通过；A6 静态+运行时两条（匹配路径正常启动；注错路径停机且标记可 `mem32` 复读） |
| 7 | `MDK-ARM_F435/scatter/X-Track-App-AC5.sct` | 新增预处理式 scatter：向量执行区（≤0x400）+ `.fw_header` FIXED @ `+0x400` + 主 RO 区 + `RW_IRAM1 0x58000`（含既有 RAMCODE/`lv_tlsf.o`/`font_bahnschrift_13.o` 语义）+ 专用 `.ota_vtor_noinit` `UNINIT`/保留区 + `RW_IRAM2 UNINIT 0x28000` | armlink 通过，A2/A3/A4/A6/A7 |
| 8 | `MDK-ARM_F435/proj.uvprojx` | 新增 `X-Track-App-AC5` target：Objects/Listings 独立目录、OutputName、ScatterFile 指向第 7 步、`<Define>` 加 `OTA_TARGET_APP`、源列表加第 2 步文件；**页面组 `<GroupOption>`/`--cpp11` 按 AGENTS.md 整组拷贝**；现有 `X-Track` target 不改 | `UV4 -b -t X-Track-App-AC5` 生成新 dep/lnp；`0 Error(s) 0 Warning(s)` + `Program Size` |
| 9 | `MDK-ARM_F435/build_f435.ps1` | 加 `-Target`（默认 `X-Track`），派生 dep/lnp/Objects/Listings/输出名；保持 ASCII | 默认调用与 AGENTS.md 现有命令行为逐字节一致（legacy 产物哈希不变）；`-Target X-Track-App-AC5` 可增量编 |
| 10 | `cmake/linker/x-track-boot-gcc.ld.S` | 新增 boot 布局源（供 P1-1 消费；本卡只提供受控源与 `X_Track_Boot` target 骨架，不写 boot 业务代码） | configure 通过 |
| 11 | `.github/workflows/firmware-build.yml` | 目标改 `X_Track_App_GCC`、产物名改 `X-Track-App-GCC.*`、加 A1/A3/A4/A5 静态断言；`register-cloudflare` 保持 publish 条件并新增首步 `OTA_BOOT_CHAIN_READY` 硬失败门闩；发布路径只接受 finalized bin | 干净 checkout 普通构建绿（A9b）；`publish=true` 且门闩未开时明确失败（A9c）；产物语义检查通过（A9d） |
| 12 | `Tools/jlink/flash-boot.jlink`、`flash-app-gcc.jlink`、`flash-app-ac5.jlink` | 新增，带数值来源注释 | A9 一致性检查 |
| 13 | 根副本只读反查 + `docs/ota-exec-notes/P1-2-*.md` + 看板证据栏 | **不修改**根 `CMakeLists.txt` / 根 `cmake/generated_linker.ld`；证明 CI/VSCode 均不引用它们，并落盘 A1-A9d 的命令、map 摘录、哈希、时间戳与 CI 结果 | 根副本引用数=0 作为 A8 证据；随后交非实现会话验收 |

---

## 7. 本轮未做与不得做

- 未修改任何 linker、scatter、CMake、uvprojx、system/startup、`build_f435.ps1`、workflow 实现文件（仅本文件与 `PLAN-OTA-EXEC.md` 的 P1-2 卡有改动）。
- 未修改 `PLAN-OTA.md` 与 `docs/ota-binary-contracts.md`（冻结契约，只读；本文件不构成契约，只是实现侧决策）。
- 未执行 `git commit/push`，留主会话审查收口（OTA 规约 §5）。
- 未把 App 布局落到任何生成物或未跟踪文件上。
- 未以普通 J-Link reset/run 作为任何启动结论。

---

## 8. 修订记录

### v3（2026-07-27，主会话二次复核收口）

不改变五 target、受控源方案 2、VTOR 自检落点或发布解锁条件，只消除执行层歧义：

1. 发布门闩由 job `if` 移到 job 首步，确保 `publish=true` 且 boot 链未就绪时有明确失败日志。
2. 验收门槛统一为 A1-A9d，A10 仍是明确排除项；实施顺序统一为 13 步。
3. A9 改为覆盖全部 16 个受控路径，并对无法使用 C 宏的 uvprojx/jlink 与冻结 Python 常量单独校验。
4. VTOR 取证段固定为 `.ota_vtor_noinit`，双工具链分别采用 `NOLOAD`/`UNINIT` 并要求 map 证据。

### v2（2026-07-26，主会话方案审查整改）

审查结论「总体方向通过，暂不进入实现」，六条意见的整改落点：

| 审查意见 | 整改 | 落点 |
|---|---|---|
| 1. A9 检查口径不可执行（仅 `0x400` 就命中约 49 个文件） | 改为 16 个受控路径内判定：新文件查全文、既有文件只查本卡新增行；补齐全部地址/长度/`0x400` 模式，并对 `ota_layout.h`、uvprojx App target、jlink、P0-2 Python 常量做结构化 allowlist 校验 | §2.1 红线、§5 A9 行、新增 §5.1 |
| 2. 矩阵缺第五个模糊 target | 采纳「定义为兼容目标」而非移除：`X-Track-Legacy-GCC`（CMake `X_Track`）正式入矩阵，标注不得用于 OTA 与退役条件；矩阵由四行改五行 | §1 矩阵、§1.3 |
| 3. VTOR 自检位置与失败行为未冻结 | 冻结到 `USER/main.cpp` 的 `Core_Init()` **之前**；冻结 fail-closed 三步，并把一级标记收敛为专用 `.ota_vtor_noinit` 段：GCC=`NOLOAD`、AC5=`UNINIT`、两侧保留且 map 可核查，不落 overlay、不硬编码 RAM 地址 | §3 第 4 条、新增 §3.1、§5 A6 |
| 4. 步骤 13 与看板范围矛盾 | 删除原先“修改根副本”的动作；当前第 13 步只做根副本引用反查并与 A1-A9d 证据落盘合并，总实施步骤固定为 13 | §2.3 第 3 条、§6 步 13 |
| 5. CI 正式发布保护缺失 | 新增 §4.1.1：job `if` 保持 `workflow_dispatch && publish=true`，首步检查 `vars.OTA_BOOT_CHAIN_READY`，未就绪时明确硬失败而非静默 skipped；解锁条件绑定 P1-5 真机 bootstrap + P4-1 演练绿；同时冻结 finalized bin 与占位头 hex/elf 的语义差异 | 新增 §4.1.1、§5 A9c/A9d |
| 6. 术语：`ota_layout.h` 不能表述为取代契约 | 全文改为「实现侧单一来源」，明确 `docs/ota-binary-contracts.md` 仍是规范数值唯一权威；两者关系为「派生 + 一致性校验」，冲突时以契约为准并按 §0.4 阻塞 | §2.1 标题与首段、§7 |

审查意见之外，本轮另修正两处本文件自身的不准确表述（均为收紧，不改方向）：

1. 原 §3 把自检落点写成「`App.cpp` 或 `HAL.cpp`，实现轮定」——按意见 3 冻结后，该表述连同 §6 步 6 的「实现轮定」一并删除。
2. 原 §5 A9 行写「全仓 grep」，与意见 1 冲突，已整体重写。
