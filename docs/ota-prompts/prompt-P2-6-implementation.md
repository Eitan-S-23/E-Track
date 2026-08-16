# 任务：实现 OTA 看板任务卡 P2-6（升级态 RAM 峰值实测回填）

> 本文件是 P2-6 实现会话的提示词。由主会话（非实现方，Claude Opus 5）按
> `docs/ota-prompts/prompt-template-implementation.md` 撰写，落盘时间 2026-08-15。
> 实现会话直接读本文件开工，不需要用户复述背景。
>
> **状态：已冻结（2026-08-16）。**
> 冻结依据：Acceptance Governance 在 Ubuntu 上取得正式远端通过
> —— PR #3 / run `31948667013` / 候选提交 `68b929b`，「Run P2-6 spec probes」
> 步骤实际输出 harness 自检 **20/20** + 探针 **8/8 PASS**，
> 「Run governance regression tests」输出 `Ran 45 tests ... OK`（远端 0 跳过）。
> 远端工具链：`arm-none-eabi-gcc 13.3.1 20240614`（Arm GNU Toolchain 13.3.Rel1
> Build arm-13.24）+ 宿主 `gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1)`。
> 本文件自此为**只读判据源**：判据需要改动必须先在 `PLAN-OTA-EXEC.md` §9 变更
> 登记表登记，并重新走「整改 → 远端 CI 通过 → 再冻结」；**不得就地改判据继续
> 实现**。发现判据矛盾或不可实现 → 把 P2-6 置「阻塞」并停止（见 §0 规约）。
> 2026-08-16 按独立复核裁定整改：外置 guard 布局（§4.2 第 1/4/5 条）、
> 删除「峰值恰等 8192B 一律 HARNESS_FAIL」并改为 §4.8 的 measurement-validity
> 判据、AC5 定为 auxiliary（§4.1/§4.6/§7）、`P2_6_TEST_ENABLE` 不进 linker
> define（§4.3 第 4 项）、LVGL 改 `--wrap` 调用级计数（§4.5 第 2 项）、
> `required_peak` 改名 `arena_peak_observed` 并明确失败路径只是下界（§3.2/§3.3）、
> 新增 §4.9 构型边界（永久生产改动 vs 测试插桩 + 三份搜索清单 L1/L2/L3 + 迁移性论证）。

## 0. 你的身份与规约（先读，违反即作废）

你是 **P2-6 的实现会话**。本仓库 `AGENTS.md` 的「OTA 执行规约」对你强制生效：

1. **先读看板再动手**：`PLAN-OTA-EXEC.md` 是唯一任务与状态源。开工前把
   `PLAN-OTA-EXEC.md:545` 的 P2-6 状态改为「进行中」并写认领标识，
   **只改本文件 §1.1「本卡范围」列出的文件**。
2. **契约只读**：`PLAN-OTA.md`（§9 预算表）与 `docs/ota-binary-contracts.md`
   （§10 overlay 契约）冻结。发现矛盾或不可实现 → 把 P2-6 置「阻塞」+ 在看板
   §9 变更登记表（`PLAN-OTA-EXEC.md:637`）登记，然后停止。
   **禁止就地修改契约继续实现**。
3. **完成必须附证据**：命令 + 关键输出、产物路径 + 时间戳、SHA-256。长输出落盘
   `docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md`。
   **你不自验收** —— 验收由另一个非实现会话执行。
4. **research 落盘**：编码前的检索/分析结论写进上面那个证据文档，不许只留在对话里。
5. **不提交**：禁止 `git commit` / `push` / `merge`，由主会话收口。
6. **收尾**：结束前回写 P2-6 卡状态，并在看板 §10 会话日志（`PLAN-OTA-EXEC.md:643`）
   追加一行。
7. **绝对禁止** `git checkout -- <file>` / `git restore`：本 worktree 的未提交内容
   是唯一副本，覆盖即永久丢失。

全局准则：**一切输出、文档、注释、日志、提交信息用简体中文**（代码标识符除外）。

### 0.1 本卡的性质（先理解，否则会做错方向）

P2-6 **不是新造测量系统**，而是「**把已有的测量值接到生产路径 + 补上唯一缺失的
栈测量 + 回填两份文档**」。overlay 段、所有权状态机、workspace 数组、layout 宏、
链接器 ASSERT、**以及固定池峰值计量本身**都已在 P0-6/P2-2/P2-3 落地并通过验收。

三个必须闭合的数值，按缺口大小排序：

| 口径 | 现状 | 你要做的 |
|---|---|---|
| overlay 固定池峰值 ≤ `40960B` | **已实现且已实测**（`arena.peak` → `info.workspace_peak`），但只在 P2-3 自检 harness 里被读，生产路径丢弃 | 把生产路径的 `workspace_peak` 取出来并留证，并补两个诊断字段（§3.2） |
| OTA 调用栈 ≤ `8192B` | **完全没有实测手段**（GCC 侧 StackInfo 不可用，见 §4.1） | 按 §4.2 的**唯一指定方案**建立栈区与哨兵测量并实测 |
| 主 RAM 余量表 | P0-6 数字来自 **2026-07-26 的 legacy 产物**，已严重过期 | 用当前 GCC/AC5 产物重算并回填 |

还有一项**不是回填而是排除性证明**的判据（详见 §4.5）：OTA 关键窗口内
**主堆（`_sbrk`）与 LVGL 池均无新增分配**。这条决定了「栈 8192B + 池 40960B」
是不是完整预算 —— 若 OTA 期间偷偷从主堆或 LVGL 池借了内存，前两个数字再漂亮
也不构成 RAM 安全结论。

### 0.2 规范性摘要（本节是规范，其余章节是它的展开）

本文件很长，且大量篇幅是**为什么这样定**的实测论证。为免你把论证当要求、把要求
当建议，这里一次性把**规范性内容**列全。本节与后文冲突时以后文的详细条款为准，
但**分类归属**（required / auxiliary / stop condition）以本节为准。

**（一）required —— 缺一即本卡不算完成**

| 判据 | 内容 | 详见 |
| --- | --- | --- |
| C1 / C2 | full / patch 路径生产侧 `workspace_peak` ≤ `40960B` 实测 | §3.1 |
| C3 | OTA 栈峰值 ≤ `8192B`（判定用 `<=`），**且**按 §4.9-E 走完所选那**一条**闭环路线 | §4.7 / §4.9-E |
| C4 | guard 区 32B intact | §4.2 第 4 条 |
| C5 | OTA 窗口 `sbrk_call_count` 增量 = 0 | §4.5 第 1 项 |
| C6 | `lv_tlsf_malloc` / `lv_tlsf_realloc` 增量 = 0（`free` 见下「交叉核对项」） | §4.5 第 2 项 |
| C7 | 异常退出后 LiveMap 可重建 | §4.5 第 3 项 |
| C8 | GCC 主 RAM 高水位与余量（改动前后对比） | §4.6 第 2 项 |
| C10 / C11 | 宿主容量边界两点鉴别力（FULL / PATCH 各正负一例） | §3.3 |
| C12 | 清单 **L2** 生产零命中 **+ L3 两固件构型零命中** | §4.9-C |
| C13 | measurement-validity 八项 + 三类负例（**C3 / C4 的前置**） | §4.8 |
| C15 | 清单 **L1** 在 `P2_6_TEST_ENABLE=1` 构型全命中 | §4.9-C |
| C16 | 插桩→生产迁移性论证 **七项全给结论** | §4.9-D |

其余 required 事项：§4.2 七条方案全部落地（段名冻结 `.ota_stack` /
`.ota_stack_guard`，九条 ASSERT A1-A9 齐全并在真实 `ld.S` 上复验正例 +
A1/A2/A4/A5/A6 各一负例）、`PLAN-OTA.md` §9 与
`docs/ota-binary-contracts.md` §10 回填实测值、证据文档落盘、回写看板卡状态与 §10 日志。

**（二）auxiliary —— 取不到不阻断本卡，但不得伪装成 required 的替代**

| 项 | 定位 | 取不到时 |
| --- | --- | --- |
| C9（AC5 主 RAM 高水位 / `Program Size`） | 辅助工具链对照，AC5 不是 OTA 产物工具链 | 记 `NOT_OBSERVED`，**不得**记 FAIL / `EVIDENCE_GAP`，不得阻断本卡 |
| C14（`lv_mem_monitor` 池四字段进出差值） | 佐证项：只证净状态未变，**不排除**窗口内瞬态分配 | 不得用它替代 C6；C6 若降级必须记 `EVIDENCE_GAP` |
| `free` 计数 | C6 的交叉核对项，不占新内存故非门禁 | 非 0 必须定位释放点，否则记 `EVIDENCE_GAP` |
| 可选 `--wrap=lv_mem_*` 分层归因 | 归因用，有同 TU 盲区 | 不得单独充当 C6 判据 |

**（三）stop condition —— 落盘现象 → 停止 → 等裁决，不得自行决定**

七类（完整表述见 §6，此处只列触发面）：① 需改 §1.1 范围外文件；② 出现本文件未列
的失效模式；③ 同一验证项连续 3 次失败；④ 真机进入不可恢复状态；⑤ 实测触发四种
具体情形（overlay 已 acquire 仍容量不足且宿主已取到 `P_full > 40960B` / 栈峰值
`> 8192B` 或 guard 破损（以 C13 已通过为前提）/ `sbrk` 或 required 拦截层增量非零 /
结论是必须改契约数字）；⑥ 红线互相矛盾或与实测冲突；⑦ §4.2 七条方案任一经实测
不可实现。**停止不等于失败**，但私自扩范围等于本卡作废。

**（四）不是规范的部分（不要当要求执行，也不要照抄进你的证据文档）**

- 所有标注「撰写会话已实测」「探针实测」的段落是**给你的可复用结论与踩坑警告**，
  用途是省掉你重踩；它们不是判据。你仍须在真实构建/真实 `ld.S` 上复验，
  复验结果与探针冲突时**以你的实测为准并落盘说明**，不得沿用探针结论。
- 所有「历史裁定 / 已作废写法 / 为何推翻」的引用块是**防回退提醒**。它们存在的
  唯一目的是阻止你照抄早期版本。完整的过程研究在
  `docs/ota-exec-notes/P2-6-spec-stack-feasibility-2026-08-15.md`，
  探针本体与 fail-closed 基线在 `tests/ota/spec-probes/p2-6/`（含 `README.md`）。
- §2.2 的 P0-6 legacy 数字（2026-07-26）是历史对照，**不是**你的比较基线。

**（五）四条红线**（§5 全文，踩中即整卡作废重来）：① 契约门槛数字只读；
② 禁止在本会话改 `Tools/etu_pack.py` 做字典降档；③ `ota_package.c` / `ota_patch.c`
的六条计量语义不变量；④ 不得为保住 StackInfo 而关闭 `--gc-sections`。

## 1. 必读文件（按顺序）

1. `PLAN-OTA-EXEC.md` 的 **P2-6 卡**（`:544-548`，含目标与验收条目）
2. `PLAN-OTA.md` §9（`:216-224`）—— 冻结预算表，回填目标之一
3. `docs/ota-exec-notes/P0-6-ram-baseline-overlay.md`，重点 **§3 实测方法**
   （`:50-63`）与 **§5.5 Overlay 契约与后续验收**（`:199-213`，明确点名 P2-6
   要采「`StackInfo`、固定池高水位、异常退出后的 LiveMap 重建」三项）
4. `docs/ota-binary-contracts.md` §10（`:529` 附近为 `OTA_STACK_RESERVE` 定义处）
5. `AGENTS.md`：「J-Link 自动烧录与 RTT 闭环调试」+「J-Link 闭环防卡死清单」

### 1.1 本卡范围（只能改这些文件）

**允许修改**：

- `USER/App/Utils/OtaUpdate/OtaUpdate.cpp` / `.h`（把 `workspace_peak` 接出来）
- `USER/HAL/HAL_OTA_Package.cpp` / `.h`（若需要暴露栈/池/堆水位查询）
- `Libraries/OTA/ota_package.c` / `.h`、`Libraries/OTA/ota_patch.c` / `.h`
  —— **仅限**两处：①新增 §3.2 的两个诊断字段与其赋值（含 `arena_alloc` 内
  「容量检查之前」的观测量更新，方案 A）；②§3.3 冻结的那段被
  `OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE` 门控的宿主容量覆盖。
  两处都必须满足红线 3 的不变量清单。其余语义（校验顺序、`arena_alloc` 的对齐与
  `arena.peak` 记账时机、既有结果码、`:665` / `:1161` 的固定最小 workspace 前置
  检查、`arena.peak > arena.capacity` 门禁）一律不动。
- `cmake/linker/x-track-app-gcc.ld.S`（按 §4.2 建栈区 + 外置 guard 区、导出四个
  符号与两个 `STACK$$` 别名、加 §4.2 第 1 条的九条 ASSERT A1-A9）
- `MDK-ARM_F435/cmake-generated/cmake/gcc_runtime_compat.c`
  （**仅**把 `_sbrk` 上限改为 `__StackGuardStart`（**不是** `__StackLimit`，理由见
  §4.2 第 5 条），并加 §4.5 的 `sbrk_call_count` /
  `sbrk_peak` 计数；该文件是 git 跟踪的手写文件，不是生成物，见 §4.1 第 3 项）
- `MDK-ARM_F435/cmake-generated/cmake/sources/startup_at32f435_437_gcc.S`
  （**仅**在首次 C 调用前填充 8192B 栈区哨兵、并向**独立 guard 区**写 guard 魔数，
  见 §4.2 第 4 条；注意 guard 区在栈区之外，不是「栈底最低字」）
- `Libraries/StackInfo/StackInfo.c` / `.h`（补 GCC 分支与工具链护栏）
- `USER/HAL/HAL_Config.h` 的 `CONFIG_SHOW_STACK_INFO` / `CONFIG_SHOW_HEAP_INFO`
  （仅在需要打开既有查询路径时）
- `MDK-ARM_F435/cmake-generated/CMakeLists.txt` 的 **48-90 行既有 option 与两两
  互斥块**（新增 `P2_6_TEST_ENABLE` option 与四条互斥，见 §4.3 第 4 项）
  与 **505 行以后手写 OTA 块**（测试构型的 `target_compile_definitions`、
  §4.5 第 2 项的 `--wrap` 链接选项；**禁止**把 `P2_6_TEST_ENABLE` 追加进
  `OTA_TEST_LINKER_DEFINES`；**禁止重跑 `keil_uvprojx2cmake.py`**）
- `PLAN-OTA.md` §9 与 `docs/ota-binary-contracts.md` §10 的**实测回填**
  —— 注意：**只允许回填「实测值」，不允许改动任何门槛数字**（`40960B`、
  `8192B`、`16KB` 字典）。改门槛属于 §6 停止条件。
- `PLAN-OTA-EXEC.md`（P2-6 卡状态 + §10 会话日志；若发生降档则 §9 登记）
- `docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md`（新建）
- `tests/ota/` 下新增本卡回归脚本

**禁止修改**：`Libraries/OTA/ota_package.c` / `ota_patch.c` 中除 §3.2 诊断字段与
§3.3 宏门控容量覆盖以外的任何逻辑（尤其校验顺序、`arena_alloc` 的容量判据与
`arena.peak` 更新时机、`arena.peak > arena.capacity` 门禁、
`workspace_len < OTA_*_WORKSPACE_SIZE` 前置检查）；
`Tools/etu_pack.py`（只有触发 §6 停止条件并获裁决后才动）；
`Libraries/OTA/ota_layout.h` 的地址/长度宏。


## 2. 背景（标注实测 / 推断，不得混同）

### 2.1 冻结契约口径（来自 `PLAN-OTA.md` §9，只读）

- 主 RAM `0x20000000..0x20058000` = `352KiB` = **360448B**
- `RW_IRAM2` / overlay `0x20058000..0x20080000` = `160KiB` = **163840B**
- OTA 固定池上限 `OTA_POOL_CEILING` = **40960B**
  （= `OTA_OVERLAY_WORKSPACE_LENGTH 0xA000`，`Libraries/OTA/ota_layout.h`）
- 主 RAM OTA 调用栈保留 `OTA_STACK_RESERVE` = **8192B**
- 已知工作集 `35492B` + 对齐/护栏 `5468B` = `40960B`
- 字典固定 `lc=2,lp=0,pb=0` 的 **16KiB**

### 2.2 P0-6 基线（**2026-07-26 的 legacy 产物**，已过期，仅作历史对照）

| 工具链 | 主 RAM 高水位 | 余量 | 来源 |
|---|---|---|---|
| AC5 | `313528B / 360448B`（86.98%） | `46920B` | `docs/ota-exec-notes/P0-6-ram-baseline-overlay.md` §5.1 |
| GCC | `286232B / 360448B`（79.41%） | `74216B` | 同上 §5.2，取自 legacy `X-Track.elf/map`（2026-07-26 12:34） |

**注意**：P0-6 的 GCC 数字来自已废弃的 legacy 目标，**不是**当前
`X-Track-App-GCC`。直接引用会得出错误的「余量充足」结论。

### 2.3 当前产物实测（撰写会话 2026-08-15 实测，你必须自己重跑复核）

产物：`MDK-ARM_F435/cmake-generated/build-gcc-release/app-gcc/X-Track-App-GCC.{elf,map}`
（859836B / 2412710B，均 2026-08-15 00:16）；
`MDK-ARM_F435/Listings-App-AC5/X-Track-App-AC5.map`。

| 工具链 | 口径 | 实测 | 余量 |
|---|---|---|---|
| GCC | `_ebss` = `0x200550c0` → 静态 | **348352B**（96.64%） | 12096B 到 `_estack` |
| GCC | `._user_heap_stack` 末 `0x200562c0`（P0-6 口径高水位） | **352960B**（97.92%） | **7488B** |
| AC5 | `RW_IRAM1 Size=0x55d10` / `Max=0x57ff8` | **351504B**（97.52%） | **8936B** |

**与 P0-6 基线的差值（实测）**：GCC 余量 **−66728B**，AC5 余量 **−37984B**。
P1/P2 新增的静态占用已经把 P0-6 时的宽裕余量吃掉大半。

GCC 主 RAM 前五大消费者（实测，来自 map）：

| 符号 | 字节 | 归属 |
|---|---|---|
| `.bss.work_mem_int.1` | 131072 | lv_mem（LVGL 内建池，`LV_MEM_SIZE 128KiB`） |
| `lv_disp_buf`（两块，各 76800） | 153600 | `lv_port_disp.cpp` |
| `xtrack_img_line_cache` | 24624 | `lv_img_decoder.c` |
| `routePoints` | 9216 | `DP_Navigation` |
| `msc_struct` | 4184 | USB MSC |

**GCC 比 AC5 多占的一项已知差异**：`xtrack_img_line_cache` 在 AC5 上是
**动态分配到 LVGL 池**（`XTRACK_IMG_LINE_CACHE_DYNAMIC 1` 仅 `__CC_ARM`），
GCC 上是 **24624B 静态数组**。这条差异由 `tests/ota/test_ac5_ram_budget.py`
锁定，**不要试图为了腾余量把 GCC 也改成动态** —— 那会改动被治理 CI 断言的行为，
属于越卡（§6 停止条件 1）。

### 2.4 固定池峰值已有实测（P2-3 验收留证）

`workspace_peak=21832B / 40960B`（53.3%，余 19128B），来源
`docs/ota-exec-notes/P2-3-implementation-evidence-2026-07-31.md`。
该值是**差分（patch）路径**的自检 harness 观测。P2-6 要补的是**全量（full）
路径**以及**生产（非 harness）路径**的同类观测。

## 3. 需求 A：把固定池峰值接到生产路径并实测

### 3.1 生产路径取出 `workspace_peak`

**现状**：`USER/App/Utils/OtaUpdate/OtaUpdate.cpp:460-501` 的
`OtaUpdate` apply 分支已经拿到了完整的 `ota_package_info_t info` /
`ota_patch_info_t info`，但只读取了 `target_vcode`、`image_len`、
`image_sha256` 三个字段，**`info.workspace_peak` 被直接丢弃**。

导致：生产升级路径没有任何峰值观测点，P2-6 若不改这里，就只能拿 P2-3 的
自检 harness 数据充当「真实升级路径实测」，不满足 P0-6 §5.5 的要求。

**要求**：真实升级路径（SD 全量 + SD 差分）各产生一条可采集、可留证的峰值观测，
且数值满足 `workspace_peak ≤ 40960B`。

**改法（复用既有链，不要新造探针）**：

- 计量已存在，**禁止重写**：
  - `Libraries/OTA/ota_package.c:132-153` `arena_alloc` 内
    `if (arena->used > arena->peak) arena->peak = arena->used;`
  - `Libraries/OTA/ota_patch.c:196-198` 同构
  - `Libraries/OTA/ota_package.c:720` / `ota_patch.c:1225` 已有
    `if (state->arena.peak > state->arena.capacity)` → `*_ERR_WORKSPACE`
  - `Libraries/OTA/ota_package.c:740` / `ota_patch.c:1291`
    `info.workspace_peak = (uint32_t)(prefix + state->arena.peak);`
  - 字段声明：`ota_package.h:78` / `ota_patch.h:112`
- 已有的自检门禁与输出格式可参照（**不要照抄进生产路径的 `P2_3_` 前缀**）：
  - `USER/HAL/HAL_OTA_Package.cpp:1057` `info.workspace_peak > OTA_PATCH_WORKSPACE_SIZE`
    → `detail = 0x43`
  - `USER/HAL/HAL_OTA_Package.cpp:1071-1079` RTT 行含 `peak=%lu`
- 生产侧输出通道：`OtaUpdate.cpp` 现在**没有任何 RTT/日志调用**
  （只有两处 `snprintf` 写 `lastError`）。你需要自行选择上报方式并在证据文档里
  说明理由。可选路线：① 直接 `SEGGER_RTT_printf`；② 存到 `OtaUpdate`
  成员再由既有 RTT 命令回显；③ 复用 `HAL_OTA_Package.cpp` 已有的 RTT 输出点。

**硬约束**：上报通道**必须走 RTT**。`CONFIG_DEBUG_SERIAL` 固定为 `Serial5`
UART，`JLinkRTTLogger` 采不到；用 UART 会导致验收会话拿不到证据。
输出时机另见 §4.4（测量值先存内存、退出关键路径后再格式化输出，
否则 `SEGGER_RTT_printf` 自身的栈帧会污染栈峰值）。

### 3.2 超限时必须能量化「超出多少」（本卡新增能力）

**问题**：现有链路只能给出布尔结论。`arena.peak > arena.capacity` 触发时返回
`*_ERR_WORKSPACE`（`ota_package.c:720` / `ota_patch.c:1225`），
`info.workspace_peak` 此时**不会**被赋值（赋值点在 `:740` / `:1291` 的成功路径），
所以一旦超限，证据只能证明「失败了」，**无法回答「需要多少字节才够」**。
降档决策（字典 16KiB → 8KiB）需要的正是这个幅度。

**要求（严格按此范围，不要扩大）**：

1. 在 `ota_package_info_t` / `ota_patch_info_t` 各新增两个字段：
   - `arena_peak_observed`：本次解包/打补丁观测到的池峰值，**含 `prefix`**，
     与 `workspace_peak` 同口径（既有 `workspace_peak` 就是
     `prefix + state->arena.peak`，见 `ota_package.c:740` / `ota_patch.c:1291`）。
     **计算方式已按裁定冻结为下面的「方案 A」，不得自行改公式。**
   - `failed_request_size`：触发容量不足的那一次 `arena_alloc` 的**原始请求字节数**
     （即入参 `size`，未对齐；未发生失败时为 `0`）。
     **该字段只作独立报告，禁止与 `arena_peak_observed` 相加**（理由见下）。
2. 这两个字段在**成功与失败两条路径上都要有确定值**，且失败路径必须随
   `*_ERR_WORKSPACE` 一起返回给调用方，否则等于没做。
3. **只作诊断，不参与控制流**。
   - 判定是否超限仍由既有的 `arena.peak > arena.capacity`（`ota_package.c:720` /
     `ota_patch.c:1225`）与 `arena_alloc` 返回 `0` 引发的
     `LzmaDec_Allocate != SZ_OK`（`ota_package.c:717`）决定，不得改成读新字段。
   - **观测量必须是新成员，禁止改写 `arena.peak` 的更新时机。**
     `arena.peak` 只在容量检查通过后更新，因此恒有 `arena.peak <= arena.capacity`；
     把它挪到检查之前会让 `:720` 那条既有门禁从「恒不触发的防御断言」变成会真实
     触发的控制流分支 —— 那是改语义，撞红线 3。新增独立成员（例如
     `arena.peak_probe`）承载观测量。
4. 生产路径（§3.1）与自检 harness 都要能打印这两个值。

**方案 A：`arena_peak_observed` 的冻结算法（裁定结论，含推导，照抄即可）**

```c
/* arena_alloc 内，紧跟 aligned_size 计算之后、容量检查之前 */
aligned_size = align_up(size, ARENA_ALIGNMENT);
if (arena->used + aligned_size > arena->peak_probe)   /* 观测量：假设性高水位 */
{
    arena->peak_probe = arena->used + aligned_size;
}
if (aligned_size > arena->capacity - arena->used)     /* 既有门禁，位置不变 */
{
    arena->failed_request = size;                     /* 原始请求，未对齐 */
    return 0;
}
```

即：`arena_peak_observed = prefix + max(arena.used + aligned_request_size)`，
**在容量检查之前更新**，所以**失败的那一次请求本身已经计入观测峰值**。

- 成功路径：`arena_peak_observed == workspace_peak == prefix + arena.peak`，
  是**完整的实际需求峰值**。
- **失败路径：`arena_peak_observed` 是需求的下界（lower bound），写法固定为**

  ```text
  需求 >= arena_peak_observed
  ```

  仍是下界而非需求值，原因是那次失败之后**本应发生的后续分配根本没有执行**
  （`arena_alloc` 返回 `0` → `LzmaDec_Allocate` 返回 `SZ_ERROR_MEM` → 直接
  `goto cleanup`）。
- **禁止写成 `需求 >= arena_peak_observed + failed_request_size`。**
  这是重复计算，会把下界虚高一个 `failed_request_size`：
  ① 该字段在**容量检查之前**更新；② 失败请求的 `aligned_size` 已经进入
  `peak_probe`；③ 字段本身已含 `prefix`。三者叠加后再加一次原始请求，
  等于把同一块内存算两遍。
  `failed_request_size` 的唯一用途是**单独报告**「是哪一次请求撞墙的、要多少」，
  用于判断是字典缓冲还是 probs 数组不够 —— 它不是加数。
- **禁止把失败路径上的观测值当成完整需求写进报告或降档依据。**
  这正是本字段不叫 `required_peak` 的原因 —— 那个名字会诱导读者把下界读成需求值。
  要拿到完整需求峰值，必须按 §3.3 在**宿主**用足够大的容量成功跑一次。
- 若你的实现里两条路径共用同一字段名而语义不同，**必须在输出里带上成败标志**
  （例如同时打印结果码），否则读日志的人无法判断这个数是需求还是下界。

**语义精度要求（极易做错，写死在这里）**：

- 只有确认是「**成功 acquire overlay 之后**的容量不足」才允许据此判断字典预算。
- **overlay owner 冲突**（`OTA_OverlayAcquireLiveMap()` 失败、LiveMap 仍持有、
  所有权状态机拒绝）**不是内存超限**，绝不能计入 `arena_peak_observed` 语义，
  也不能在证据里写成「池不够」。这两类失败在报告里必须分开成两个不同现象。
- 若你无法区分这两类失败，说明上报字段设计不对，先改设计再测。

### 3.3 容量边界的鉴别力验证（宿主：先取完整需求，再做两点）

新增诊断字段若没有负例，等于没有鉴别力。**顺序不能颠倒**，FULL 与 PATCH 各做一组：

**第 0 步（先做，否则后两步的容量值无从确定）**：在宿主用**足够大的容量**
（就用正式的 `40960B`，成功即可）跑通一次，取得
**完整的 `arena_peak_observed`**。记为 `P_full`。
这一步的意义：只有成功路径上的观测值才是完整需求（§3.2 语义），
失败路径给不出 `P_full`。
第 0 步**必须同时打印 `prefix`**，否则下面的坐标换算无从做起。

**【坐标必须换算：`P_full` 含 `prefix`，`arena.capacity` 不含】**

两个量不在同一坐标系里，直接把 `P_full` 当容量写会整体偏移一个 `prefix`：

| 量 | 是否含 `prefix` | 出处 |
|---|---|---|
| `workspace_peak` / `arena_peak_observed` / `P_full` | **含** | `prefix + arena.peak`（`ota_package.c:740`） |
| `arena.capacity` | **不含** | `workspace_len - prefix`（`ota_package.c:695` / `ota_patch.c:1189`） |

所以边界两点的容量值必须写成 **`P_full - prefix`** 与 **`P_full - prefix - 1`**。

**【禁止用「缩短 `workspace_len`」实现这两点 —— 那是假负例】**

生产代码在进入 arena **之前**就有固定最小 workspace 前置拒绝：

```c
/* ota_package.c:665（ota_patch.c:1161 同构） */
if (workspace == 0 || workspace_len < OTA_PACKAGE_WORKSPACE_SIZE)
{ ... return OTA_PACKAGE_ERR_WORKSPACE; }
```

`OTA_PACKAGE_WORKSPACE_SIZE == OTA_PATCH_WORKSPACE_SIZE ==
OTA_OVERLAY_WORKSPACE_LENGTH == 40960B`。而 `P_full` 实测远小于该值
（P2-3 差分路径实测 `21832B`，§2.4）。若把 `workspace_len` 直接设成
`P_full` 或 `P_full - 1`，代码会在 `:665` 就返回 `*_ERR_WORKSPACE`，
**根本没进 arena**：
`arena_peak_observed` 与 `failed_request_size` 全为 `0`，
你测到的是「前置检查生效」而不是「arena 容量边界有鉴别力」。

现有 harness 的 `short_workspace` 开关
（`tests/ota/test_ota_package.c:249-251`，返回 `OTA_PACKAGE_WORKSPACE_SIZE - 1u`）
测的正是那条前置检查 —— 它是另一条判据的既有覆盖，
**不得复用它充当本节的容量边界负例**。

**【冻结的 test-only 注入方式（照此实现，不要自创）】**

1. `workspace_acquire` 返回的 `workspace_len` **保持 `40960B` 不变**，
   于是 `:665` / `:1161` 的前置检查正常通过，控制流真正进入 arena。
2. **仅在宿主 harness** 用 test-only 宏覆盖 `state->arena.capacity`，
   紧跟既有赋值之后：

   ```c
   state->arena.capacity = workspace_len - prefix;
   #if defined(OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE)
       /* 仅宿主边界用例编译；固件构型下本段不存在 */
       state->arena.capacity = ota_p2_6_host_arena_capacity(prefix);
   #endif
   ```

   宿主侧由 harness 提供 `ota_p2_6_host_arena_capacity()`，返回
   `P_full - prefix` 或 `P_full - prefix - 1`。
3. **不得改动 `:665` / `:1161` 的固定最小 workspace 检查**，也不得改
   `OTA_*_WORKSPACE_SIZE` 宏。
4. **fail-closed**：宏未定义时不得产生任何代码差异（不要写成运行期变量默认值）。
   该宏**只能**出现在宿主 harness 的编译命令行里，**禁止**进入
   `CMakeLists.txt` 的任何固件构型，并须并入 §4.9 C 项的清单 **L3**
   （B' 组：符号 `ota_p2_6_host_arena_capacity` 在两个固件目标中零命中；
   宏名 `OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE` 在两个固件构型的 CMake cache 与
   `compile_commands.json` 中零命中）。它**不进**正向命中清单 L1。
5. `Libraries/OTA/ota_package.c` / `ota_patch.c` 的**允许改动范围**因此从
   「仅 §3.2 诊断字段」扩为「§3.2 诊断字段 + 本节这段被宏门控的容量覆盖」，
   其余语义（校验顺序、`arena_alloc` 对齐与记账、既有结果码、
   `arena.peak > arena.capacity` 门禁）一律不动。

| 点 | 池容量设置 | 期望 |
|---|---|---|
| 正例 | `capacity = P_full - prefix` | 成功返回，`workspace_peak == arena_peak_observed == P_full` |
| 负例 | `capacity = P_full - prefix - 1` | 返回 `*_ERR_WORKSPACE`，且 `arena_peak_observed` 与 `failed_request_size` 均非零，并显式记录「该值是下界」 |

共四次运行（FULL/PATCH × 正/负），加上第 0 步两次，合计六次。

负例还必须证明**副作用没有发生**：candidate 分区既没有被 prepare（擦除），
也没有被 program（写入）。用现有宿主 harness 的 flash 桩计数或写入日志证明
（`tests/ota/test_ota_package.c` 已有 `candidate_prepares` /
`candidate_programs` 口径可复用），不要靠肉眼看结论。

负例还必须区分它与前置检查的失败**不是同一条**：`arena_peak_observed != 0`
即证明控制流确实进了 arena。若该值为 `0`，说明你又落回了前置拒绝路径，
本条判据判 `HARNESS_FAIL` 而不是 PASS。

**边界只在宿主做**。真机**只跑正式的 `40960B` 容量**，
**禁止**在设备上做逐字节扫描或反复破坏性容量试验（会反复擦写 candidate 分区，
且 halt/掉电时序有把 SD 卡打挂的既有风险，见 §8）。

**真机若真的出现 `*_ERR_WORKSPACE`**：只能得出「需求超过 `40960B`」这一个结论，
**不得**用那次失败读到的 `arena_peak_observed` 宣称已知完整超出幅度。
要给降档决策提供幅度，必须回到宿主用更大容量成功跑一次取 `P_full`。


## 4. 需求 B：建立可信的 OTA 调用栈水位测量

这是本卡**唯一真正缺失**的能力，也是最容易做错的部分。

### 4.1 依赖缺口（撰写会话已实测，不要重复踩）

**GCC 目标上 `Libraries/StackInfo` 双重不可用**：

1. **符号不存在**。`StackInfo.c:25-33` 依赖
   ```c
   #define CSTACK_BLOCK_NAME      STACK
   #define SECTION_START(_name_)  _name_##$$Base   /* 注意是双美元符 */
   #define SECTION_END(_name_)    _name_##$$Limit
   extern const int STACK$$Base;   /* 宏展开后的真实符号名 */
   extern const int STACK$$Limit;
   ```
   这是 **armlink 为 `AREA` 自动生成的符号约定**。GCC map 里栈相关符号只有
   `_estack = 0x20058000`、`_sstack = 0x20000000`、`_Min_Stack_Size = 0x1000`
   （`X-Track-App-GCC.map:11361-11364`），**没有 `STACK$$Base` / `STACK$$Limit`**。
2. **代码已被丢弃**。map 中 `StackInfo` 共 14 处命中，**全部落在
   `Discarded input sections`（第 334..10950 行）**；最终链接映射区只有第 10996 行
   一条 `LOAD ...Libraries/StackInfo/StackInfo.c.obj`（非段分配）。
   即 `--gc-sections` 已把四个函数全部丢弃。

**AC5 目标上情况不同**（成因与修法都不一样，不要混为一谈）：

- `STACK$$Base = 0x20054d10` / `STACK$$Limit = 0x20055d10` **确实存在**
  （`MDK-ARM_F435/Listings-App-AC5/X-Track-App-AC5.map:30326-30327`，双美元符）。
- 来源是 `MDK-ARM_F435/RTE/Device/-AT32F435RGT7/startup_at32f435_437.s:15-19`：
  `Stack_Size EQU 0x00001000` + `AREA STACK, NOINIT, READWRITE, ALIGN=3`
  + `Stack_Mem SPACE Stack_Size` + `__initial_sp`；armlink 自动生成 `$$Base/$$Limit`，
  再由 scatter 的 `.ANY (+RW +ZI)` 收进 `RW_IRAM1`。
- `MDK-ARM_F435/scatter/X-Track-App-AC5.sct` **没有** STACK 执行域，
  这是正常的，不是缺陷 —— 不要为此去改 scatter。
- 四个函数被 armlink 移除（map `:19579-19582` 的 `Removing stackinfo.o(...)`），
  因为 `USER/HAL/HAL_Config.h:218` `CONFIG_SHOW_STACK_INFO 0` 使唯一调用者
  `USER/HAL/HAL_Memory.cpp:49` 被条件编译掉。
- **AC5 侧不做栈峰值测量，也不做哨兵与 guard。** 本卡已裁定 AC5 为 auxiliary
  （§4.6 第 1 项），它只提供静态 RAM 高水位与 `Program Size` 对照（§9 C9）。
  这段 AC5 事实之所以仍然写在这里，是为了让你知道 `STACK$$Base/$$Limit` 的
  **命名与方向来源**（§4.2 第 2 条要在 GCC 侧复刻这套别名），**不是**要你去改
  AC5 侧的 startup 或打开 AC5 的 `CONFIG_SHOW_STACK_INFO`。
- 顺带记录一个**未验证的推断**，仅供他人立卡参考，本卡不做也不汇报：AC5 的
  `AREA STACK` 是 `NOINIT`，而 `StackInfo.h` 的 `STACK_INFO_BLANK 0x00000000`
  假设未用过的栈为 0；AT32 上电 SRAM 不保证为 0，热复位更不保证。所以「AC5 打开
  宏即可用」是乐观推断，**不得当成已验证结论写进任何报告**。
  `MDK-ARM_F435/RTE/Device/-AT32F435RGT7/startup_at32f435_437.s` 明确**不在本卡
  范围**（§1.1）；若你认为必须改它，走 §6 停止条件上报，不要私自扩范围。


**另外两个宏也都是 0**：`HAL_Config.h:218-219`
`CONFIG_SHOW_STACK_INFO 0` / `CONFIG_SHOW_HEAP_INFO 0`。
且 `Memory_ShowHeapInfo()` 用的是 **AC5 专有** `__heapstats((__heapprt)..., &size)`
（`HAL_Memory.cpp:18-45`），**GCC 上不存在该 API**。
`__heapstats` 在本卡**只列为辅助证据，不作 required 门禁** —— 除非你先证明它
确实提供**峰值**语义而不只是当前占用快照（ARM 文档未承诺峰值）。
堆侧的 required 判据改用 §4.5 指定的三组机器可读量。

### 4.2 GCC 侧栈测量：唯一指定方案（不要再另选路线）

以下七条是**已裁定的唯一方案**，不是候选清单。你的任务是实现并验证它，
而不是重新比较方案。若你认为某条不可实现，走 §6 停止条件上报，不要私自换路线。

> **本节已于 2026-08-16 经独立复核修订，并已完成最小链接正负例实测**：guard 由
> 「栈区内最低字」改为**栈区之外、紧邻 `__StackLimit` 低地址侧的独立 guard 区**。
> 原布局会让 `StackInfo` 扫描第一次比较即命中 guard，峰值恒为 8192B，判据静默
> 假通过（宿主已复现，见 §4.2 第 4 条）。修订后 `StackInfo` 扫描完整 8192B 栈区、
> 无需跳过任何字，`peak == 8192B` 变回**有效的零余量观测**而不是失效特征值。
> 涉及 `_sbrk` 上限、堆重叠 ASSERT、静态 RAM 余量三处口径一并改为以
> **guard 区起始地址**为界，不要再按 `__StackLimit` 算。
> 布局与九条 ASSERT 已在 `tests/ota/spec-probes/p2-6/guard_layout/` 完成正例 1 +
> 负例 9 的链接实测（第 1 条附实测符号值与踩坑）；你仍须在真实 `ld.S` 上复跑。

**1）在 `ld.S` 里把有效 RAM 显式切成「数据/堆区 + guard 区 + 顶部精确 8192B 栈区」。**

目标布局（地址自高到低，`__StackGuardStart` 为新增的堆/栈分界）：

    0x20058000  __StackTop = STACK$$Limit = _estack   ← 初始 SP
                  [ 8192B 可用栈区，全部填非零哨兵 ]   ← StackInfo 扫描范围
    0x20056000  __StackLimit = STACK$$Base            ← 栈能生长到的下界
                  [ guard 区，OTA_STACK_GUARD_SIZE ]  ← 填 guard 魔数，不在扫描范围
    0x20055FE0  __StackGuardStart                     ← _sbrk 上限 / 堆区硬边界
                  [ 数据段 + 最小堆 ]
    0x20000000

- 可用栈区必须是 `NOLOAD` 段，位于 `RAM` 顶部，**长度精确 `8192` 字节**
  （契约 `OTA_STACK_RESERVE`），不要写成 `_Min_Stack_Size` 之类可漂移的表达式。
  **段名冻结为 `.ota_stack`**（下面 A1/A3/A4/A6 与探针 `cases.json` 逐条引用该名）。
- guard 区是**另一个** `NOLOAD` 段，紧贴可用栈区下方，长度取 **32 字节**（8 个字），
  **段名冻结为 `.ota_stack_guard`**。
  不要把 guard 算进 8192B —— 8192B 是契约保留给**栈本身**的，guard 是额外的
  检测开销。guard 占用必须在 §4.6 第 2 项的余量回填里**单列一行如实说明**，
  不得混进「栈保留」数字里，也不得因此改动 `8192B` 契约值（§5 红线 1）。
- 导出四个符号：`__StackTop`（栈区高地址 = 初始 SP，应与现有 `_estack` 一致）、
  `__StackLimit`（可用栈区低地址）、`__StackGuardStart`（guard 区低地址 =
  数据/堆区的硬上界）、`__StackGuardEnd`（应等于 `__StackLimit`）。
- 保留 `_estack` / `_sstack` 现有定义不删，避免 startup 与既有代码失配。
- **符号必须由实际输出段派生，不得写成独立常量算术**（这是下面 ASSERT 有鉴别力的
  前提，见本条末尾的实测踩坑）：

      __StackLimit      = ADDR(.ota_stack);
      __StackTop        = ADDR(.ota_stack) + SIZEOF(.ota_stack);
      __StackGuardStart = ADDR(.ota_stack_guard);
      __StackGuardEnd   = ADDR(.ota_stack_guard) + SIZEOF(.ota_stack_guard);

- 追加 `ASSERT`，把布局约束全部变成链接期硬失败。**九条都要**，且
  **A1–A5 必须锚在段的实测 `ADDR`/`SIZEOF` 上，不能拿符号比符号**：

  | 编号 | 断言 | 拦住的错误 |
  |---|---|---|
  | A1 | `SIZEOF(.ota_stack) == OTA_STACK_RESERVE` | 栈区长度漂移 |
  | A2 | `SIZEOF(.ota_stack_guard) == OTA_STACK_GUARD_SIZE` | guard 长度漂移 |
  | A3 | `ADDR(.ota_stack) + SIZEOF(.ota_stack) == _estack` | 栈顶未对齐初始 SP |
  | A4 | `ADDR(.ota_stack_guard) + SIZEOF(.ota_stack_guard) == ADDR(.ota_stack)` | guard 与栈区之间有空洞 |
  | A5 | `ADDR(._user_heap_stack) + SIZEOF(._user_heap_stack) <= ADDR(.ota_stack_guard)` | 数据/堆段侵入 guard |
  | A6 | `__StackLimit == ADDR(.ota_stack)` | 符号与段脱钩 |
  | A7 | `__StackGuardStart == ADDR(.ota_stack_guard)` | 符号与段脱钩 |
  | A8 | `__StackGuardEnd == __StackLimit` | guard 上界与栈下界不一致 |
  | A9 | `__StackTop == _estack` | 栈顶符号与 startup 失配 |

  A5 是本方案的核心护栏 —— 没有它，越界只会在运行期表现为随机崩溃。
  A6–A9 防的是后续维护者把符号改回独立算术：那样 A1–A4 仍会通过，
  但符号已不再描述真实段布局。

- **【撰写会话已链接实测，正负例全过，可直接照用】**
  探针 `tests/ota/spec-probes/p2-6/guard_layout/`（`arm-none-eabi-gcc 13.3.1`，
  正例 1 + 负例 9 共 10 个用例；`python tests/ota/spec-probes/p2-6/guard_layout/run.py`
  按 `cases.json` 的期望判据 fail-closed 判定，rc=0 才算通过）。正例实测符号值：

      __StackTop        = 0x20058000   （= _estack = STACK$$Limit = 初始 SP）
      __StackLimit      = 0x20056000   （= STACK$$Base）
      __StackGuardStart = 0x20055fe0   （= _sbrk 上限）
      __StackGuardEnd   = 0x20056000   （== __StackLimit）

  九个负例分别是：栈区长度错（命中 A1）、guard 长度错（A2）、guard 与栈之间
  有空洞（A4）、guard 段地址错（A4）、栈段地址错（A3）、数据段侵入 guard（A5）、
  堆段侵入 guard（A5）、`__StackLimit` 与 `.ota_stack` 脱钩（**命中集合恰好只有
  A6**）、两层间接宏简化成一层（链接期未定义符号 `CSTACK_BLOCK_NAME$$Base`）。
  **你必须在真实 `ld.S` 上复跑正例 + 至少 A1/A2/A4/A5/A6 各一个负例，把 rc 与
  ASSERT 消息贴进证据文档**；沿用探针结论而不复跑不算验证。

- **【撰写会话已实测，A6 负例的构造方式必须照抄，否则做不出独立负例】**
  直接把 `__StackLimit` 改成脱钩算术会**连带**打死 A8（`__StackGuardEnd ==
  __StackLimit`）、进而牵连 A3/A9，命中集合里出现多条，无法证明 A6 自身有鉴别力。
  正确做法是**把 `__StackGuardEnd` 一并改成同一个脱钩值**（探针用
  `_estack - OTA_STACK_RESERVE - 64` = `0x20055FC0`），使 A8 仍然成立，
  A1–A5、A7、A9 逐条推演也都不受影响 —— 于是命中集合**恰好** `{A6}`。
  复跑时判据必须是「命中集合等于 `{A6}`」而不是「集合包含 A6」，
  否则 A6 靠别的条目连带失败也能算过。

- **【撰写会话踩坑，最易做出「假通过」的一处】段的实际填充长度必须与契约常量
  脱钩，否则负例恒不触发。** 探针第一版把段内 `. = <长度>;` 与 A1/A2 右值
  的 `OTA_STACK_RESERVE` / `OTA_STACK_GUARD_SIZE` 绑成同一个值：改「长度」时
  两边一起变，A1/A2 **恒成立**，七个负例里有两个静默通过。
  修法是让二者来自不同来源（探针用 `@@STACK_FILL@@` / `@@GUARD_FILL@@` 与
  `@@STACK_LEN@@` / `@@GUARD_LEN@@` 两组独立占位符）。
  在真实 `ld.S` 上对应的要求是：段内长度写字面值或独立变量，A1/A2 右值写契约
  常量宏，**不要为了「少一处硬编码」把两边合并成一个符号** —— 合并之后
  ASSERT 就只是在和自己比较。
- **【撰写会话已实测，锚点极易写错】不要用 `end` 作重叠 ASSERT 的左值。**
  `ld.S:296-299` 里 `end` 是 `PROVIDE(end = .)` 在 `._user_heap_stack`
  **段起始处**定义的，是堆区**起点**不是终点。写成
  `ASSERT(end <= __StackGuardStart, ...)` 时，堆区膨胀不会让 `end` 变大，
  ASSERT **恒成立、永不触发**（实测：把堆预留改成 `0x58000` 制造重叠，
  该 ASSERT 静默通过，最后只靠 ld 内置的 `overlaps section` 兜住，
  错误信息还指不出是栈冲突）。
  正确锚点用段结束地址，即上面 A5 的写法：
  `ASSERT(ADDR(._user_heap_stack) + SIZEOF(._user_heap_stack) <= __StackGuardStart, ...)`。
  实测该写法在正例 rc=0 不误报，负例明确报出自定义消息（当时验证用的右值是
  `__StackLimit`；换成 `__StackGuardStart` 只是把边界再下移 guard 长度，
  鉴别力不变，但你仍须在真实脚本上复跑正/负例各一次）。
- **【撰写会话已实测】段内不要做绝对地址算术。** 段体内的 `.` 是相对段起始的
  偏移，写 `. = __StackLimit + 8192 - <绝对符号>;` 会被当成巨大长度，
  实测报 `region RAM overflowed by 536871424 bytes`。用绝对地址定位段
  （`.ota_stack __StackLimit (NOLOAD) : { ... . = 8192; }`），段内只用相对长度。

**2）提供 `STACK$$Base` / `STACK$$Limit` 兼容别名（注意双美元符）。**

- 目的：让 `Libraries/StackInfo/StackInfo.c` 在 GCC 下能直接复用，不必分叉两套实现。
- 映射关系：`STACK$$Base = __StackLimit`、`STACK$$Limit = __StackTop`
  （armlink 的 `$$Base` 是低地址、`$$Limit` 是高地址，与 `__Stack*` 命名方向相反，
  **极易接反，接反会得到负数或巨大值**）。
- **【撰写会话已实测，两个工具链限制均不成立，可直接照用】**
  探针 `tests/ota/spec-probes/p2-6/guard_layout/`，工具链
  `arm-gnu-toolchain-13.3.rel1`：
  ① **GNU ld 脚本里直接写 `STACK$$Base = __StackLimit;` 即可，不需要引号。**
     实测链接 rc=0，`nm` 得 `20056000 A STACK$$Base` / `20058000 A STACK$$Limit`。
  ② **arm-none-eabi-gcc 默认接受含 `$` 的标识符**（`-fdollars-in-identifiers`
     默认开启）。`extern const int STACK$$Base;` 编译 rc=0，`nm` 得
     `U STACK$$Base`。显式加 `-fno-dollars-in-identifiers` 才报
     `pasting "..." and "$" does not give a valid preprocessing token` +
     `stray '$' in program` —— 确认本项目未使用该选项即可。
  ③ 端到端已验证：C 代码引用 + ld 定义别名 → 链接 rc=0，`_start` 反汇编内联出
     `.word 0x20058000` / `.word 0x20056000`，相减恰为 8192。
  **所以退路（`#if defined(__GNUC__) && !defined(__CC_ARM)` 直接引用
  `__StackLimit`/`__StackTop`）无需启用**；但你仍须在自己的构建里复跑一次
  `nm` 确认，并把输出贴进证据文档。若你的实测与此相反，按 §6 停止条件上报。
- **【撰写会话已实测，必须照做】两层间接宏不可省。**
  `StackInfo.c:25-34` 的 `CSTACK_BLOCK_START(_name_)` → `SECTION_START(_name_)`
  两层写法**不是冗余**：`##` 会抑制形参的宏展开，若只留一层直接写
  `SECTION_START(CSTACK_BLOCK_NAME)`，得到的符号是字面量
  `CSTACK_BLOCK_NAME$$Base` 而**不是** `STACK$$Base`（实测 `nm` 输出确认）。
  这种错误**编译不报错**，只在链接期表现为未定义符号；若你同时在 ld 里定义了
  同名错符号，就会静默得到错误的栈边界。**不要"简化"这两层宏。**
  探针负例 `neg9_one_layer_macro`（`tests/ota/spec-probes/p2-6/guard_layout/`）
  已把这条固化成可复跑判据：开 `-DP2_6_ONE_LAYER_MACRO` 后链接必须失败，
  错误文本必须出现未定义符号 `CSTACK_BLOCK_NAME$$Base` / `$$Limit`，
  且**不得**命中任何 A1–A9 —— 否则说明是别的原因失败，不能算证明。

**3）`._user_heap_stack` 不再重复预留 4KiB 栈，只保留最小堆。**

这一条是**必须做**的，不是可选优化。算术已核实（以 32 字节 guard 为例）：

| 量 | 当前值 | 说明 |
|---|---|---|
| `end`（`._user_heap_stack` 起点） | `0x200550c0` | GCC map 实测 |
| 现有预留 | `0x200` 堆 + `0x1000` 栈 = `0x1200` | `ld.S:300-301` |
| 现有末址 | `0x200562c0` | |
| 新栈区下界 `__StackLimit` | `0x20058000 - 0x2000 = 0x20056000` | 8192B 栈区 |
| guard 区起始 `__StackGuardStart` | `0x20056000 - 0x20 = 0x20055fe0` | 32B guard |
| **越界** | `0x200562c0 - 0x20055fe0 = 0x2e0 = 736B` | **必然重叠** |

即：**保留原 `. = . + _Min_Stack_Size` 的同时再开 8192B 栈区 + 32B guard，
比可用空间少 736B，链接必然被第 1 条的 ASSERT 打死。** 必须删掉
`._user_heap_stack` 里的栈预留行，只留 `. = . + _Min_Heap_Size`（`0x200`）。
改完末址 `0x200552c0`，距 `__StackGuardStart` 余 `0xd20 = 3360B`。

**余量回填口径（三个数都要写，不要只写一个）**：
- 改动后真实静态余量 = **3360B**（到 `__StackGuardStart`，即堆能合法生长的上界）
- guard 检测开销 = **32B**（单列，不计入 8192B 栈保留，也不计入静态余量）
- 契约栈保留 = **8192B**（不变，见 §5 红线 1）

上述 `3360B` / `736B` 是按 32 字节 guard 算出的；若你最终选了别的 guard 长度，
必须按实际长度重算并在证据文档里给出算式。**不要拿改动前的 7488B 交差**，
也不要把 guard 的 32B 混进「栈保留」或悄悄从 8192B 里扣。

**4）startup 在首次 C 调用前写非零哨兵（8192B 栈区）+ guard 魔数（独立 guard 区）。**

- 位置：`startup_at32f435_437_gcc.S` 的 `Reset_Handler`，
  **在 `bl extend_sram_512k` 之前**（`:157-159` 已实测：`ldr r0,=_estack` /
  `mov sp,r0` 之后紧接就 `bl extend_sram_512k`，那已经是第一个 C 调用，会用栈）。
  此刻 SP 刚设好、尚无任何栈帧，填满整个栈区是安全的。
- 填充范围 `__StackLimit .. __StackTop`（8192B），填**非零**哨兵常量。
  **不得依赖 NOINIT 段偶然为零**：GCC 的 `.Lfill_bss`（`:174-179`）只覆盖
  `_sbss.._ebss`，栈区不在其中；AC5 的 `AREA STACK, NOINIT` 同样不清零。
- **【撰写会话已核实】可访问性没问题，但原因要写对。**
  栈区 `0x20056000..0x20058000` 落在主 RAM（`0x20000000..0x20058000`，352K）内，
  而 `extend_sram_512k` 之前的基础配置已有 **384K**（到 `0x20060000`），
  故栈区在扩展前即可写；只有 overlay 区（`0x20058000..0x20080000`，需 512K）
  才依赖扩展。
  另外注意 `extend_sram_512k`（`MDK-ARM_F435/Platform/Core/at32f435_437_clock.c:122-139`）
  在 EOPB0 尚非 512K 时会**擦写用户系统数据并 `nvic_system_reset()`**，
  复位后重走 `Reset_Handler` —— 哨兵会被**再填一次**，这不影响正确性。
  该函数注释亦明确「此时 RW/ZI 尚未初始化，只允许使用局部变量」即它**会用栈**，
  这正是哨兵必须填在它之前的原因。
- guard/canary：填在**独立的 guard 区**（`__StackGuardStart .. __StackGuardEnd`，
  即 `__StackLimit` 之下的 32 字节），魔数与哨兵取**不同常量**，以便区分
  「用到了但没越界」和「已越界」。**guard 不在 `__StackLimit .. __StackTop`
  之内**，因此不占用契约的 8192B，也不进入 StackInfo 的扫描范围。
- 同步更新 `StackInfo.h` 的 `STACK_INFO_BLANK`，使其等于你选的哨兵值，
  否则扫描仍按 0 判断，全部数据无效。
- **StackInfo 扫描范围恰是 `STACK$$Base .. STACK$$Limit`（完整 8192B），
  `i` 从 0 起算，不跳过任何字。** 外置 guard 布局的全部意义就在这里：
  扫描区内每一个字在 startup 后都是哨兵值，第一个非哨兵字就是真实的最深水位。
- **【撰写会话宿主实测，说明为什么必须外置】** 若把 guard 写在栈区内最低字
  （`__StackLimit` 处，即 `i=0`），`StackInfo.c:52-61` 的「从 `i=0` 向上找第一个
  非 BLANK 字」会**第一次比较就命中 guard** → `usageSize = size` → 峰值**恒为
  8192B**；而门禁是「≤ 8192B」，于是判据**永远 PASS 且完全失去鉴别力**。
  宿主复现（`python tests/ota/spec-probes/p2-6/host_scan/run.py`，fail-closed）：
  实际用 1024B 时，无 guard 扫描得 `1024B`（正确，场景 S1），guard 写在栈区内
  得 `8192B`（失效，场景 S2）；另外场景 S4 证明 `BLANK` 常量若未与实际哨兵
  同步，同样恒返回满栈 `8192B`。
  这不是会报错的失败，是静默假通过。**外置 guard 后该冲突不复存在**，
  故不要再引入「扫描跳过 guard 字」这类偏移补偿 —— 偏移写错同样会静默出错。
- **guard 的能力边界（必须在证据文档里如实写明，不要夸大）**：guard 只能检出
  **跨越 guard 区的写入**。函数序言 `sub sp, #N` 一次跳过 32 字节再写中间位置时，
  guard 可能保持完整而越界已经发生。因此**越界的主判据是「峰值 ≤ 8192B」与
  链接期 ASSERT**，guard 是补充证据，不是唯一防线。
- **AC5 侧不做哨兵与 guard**（本卡已裁定 AC5 为 auxiliary，见 §4.6 第 1 项）。
  AC5 只提供静态 RAM 高水位 / `Program Size` 对照（§9 C9），
  **不产出 AC5 栈峰值，也不以 AC5 结果阻断本卡**。

**5）`_sbrk` 上限改成 `__StackGuardStart`（不是 `__StackLimit`）。**

现状（`gcc_runtime_compat.c:24-58` 实测）：
`limit = &_estack - &_Min_Stack_Size` = `0x20058000 - 0x1000 = 0x20057000`，
即**堆可以长进栈区 4096B，栈只被硬保证 4096B**，而契约要 8192B。

改成 `limit = (uintptr_t)&__StackGuardStart`。**注意不要写成 `__StackLimit`**：
guard 区在 `__StackLimit` 之下，若堆上限取 `__StackLimit`，堆就能合法地长进
guard 区并把魔数改掉，guard 判据随即失效（表现为「guard 破损」误报成栈越界）。
取 `__StackGuardStart` 后，堆上限、第 1 条的重叠 ASSERT（A5）、
运行期 guard 三者口径完全一致，都以 guard 区起始地址为界。

**6）栈段用 `KEEP`，StackInfo 靠真实调用保活，不动全局链接选项。**

- 第 1 条的栈区是 `NOLOAD` 段，用 `KEEP()` 防止被回收。
- `StackInfo` 的四个函数不靠 `KEEP` 保活，而是**真的被调用**
  （§4.4 的采集点会调用它们）。有真实调用链就不会被 `--gc-sections` 丢弃。
- **不需要也不允许**关闭或绕过 `--gc-sections`（见 §5 红线 4）。

**7）水位口径 = clean boot 到 OTA 结束的生命周期最大值（保守上界）。**

- 哨兵扫描给出的是「自上次填充以来的历史最深」，**不是** OTA 窗口独占值。
  本卡明确采用它作**保守上界**：若生命周期上界都 ≤ 8192B，OTA 窗口自然 ≤ 8192B。
- 必须同时记录**两个数**：OTA 入口处的基线水位、OTA 结束后的水位。
  差值只作参考（不是严格的 OTA 窗口值），但基线过高本身就是有价值的信号。
- **禁止在 OTA 入口重填活动栈**。那会覆盖当前正在使用的栈帧，直接崩。
  哨兵只在 startup 填一次。
- 产品门禁是**两条同时成立**：`峰值 ≤ 8192B` **且** `guard intact`。
  注意是 `≤`，**不是 `<`** —— 外置 guard 布局下 `峰值 == 8192B` 是**有效的
  零余量观测**（栈刚好用满可用区、一个字节都没越界、guard 完好），
  必须记 PASS 并在报告里显著标注「余量为 0」，不得改判 `HARNESS_FAIL`。
  guard 被破坏说明已越界，报 `PRODUCT_FAIL`（此时峰值数字本身不可信）。
- **但门禁本身不能自证有效**。峰值数字可信的前提（栈边界符号正确、
  `STACK_INFO_BLANK` 与哨兵一致、扫描确有鉴别力等）由 §4.8 的
  **独立 measurement-validity 判据**验证，与产品门禁分开评判、分开报告。
  两者的关系：measurement-validity 不通过 → 产品门禁的 PASS/FAIL **一律作废**，
  按 §4.8 的分类表判 `HARNESS_FAIL` 或 `EVIDENCE_GAP`，不得直接写产品结论。
- **StackInfo 扫描调用自身的栈开销必须量化**（本卡新增要求，不得省略）。
  `StackInfo_GetUsage()`（或你的采集函数）本身会压栈，它的栈帧也会踩掉哨兵，
  因此**测得峰值包含测量动作自己的开销**。你必须给出这个开销的字节数，
  并说明它是如何测得的（可行做法：在同一构型下比较「只调用一次采集」与
  「采集函数外再套一层同签名空壳后调用」两次的峰值差，或直接读采集函数的
  `sub sp, #N` 序言 + 其调用链最深路径，反汇编取值）。
  报告里必须写成两行：`测得峰值 = <A>B`、`其中测量开销 = <B>B`，
  并明确「产品门禁按 `<A>` 判定（保守，含测量开销）」。
  **不要把测量开销从峰值里减掉再报**，那会把保守上界变成乐观估计。

### 4.3 已核实的口径（防止重复走弯路）

1. **`cmake/linker/x-track-app-gcc.ld.S` 可以改，不违反规约。**
   核查结论：它是**手写维护的模板**、git 跟踪、位于仓库根 `cmake/linker/` 下，
   **不在** `MDK-ARM_F435/cmake-generated/` 内；`keil_uvprojx2cmake.py`
   全仓检索无任何 `ld.S` / linker 相关命中（该脚本本身未入库，见
   `docs/ota-exec-notes/P1-2-target-linker-decision-2026-07-26.md:46`）。
   它经 `MDK-ARM_F435/cmake-generated/CMakeLists.txt:33/35` 预处理生成到
   `${APP_OUTPUT_DIR}/x-track-app-gcc.ld`。
   相关行：`:5 _estack`、`:6 _sstack`、`:7 _Min_Heap_Size=0x200`、
   `:8 _Min_Stack_Size=0x1000`、`:228 .stack (NOLOAD)`、`:235 .heap (NOLOAD)`、
   `:242-261 OVERLAY ... > RW_IRAM2`、`:263-270` 四条 overlay ASSERT、
   `:296-301 ._user_heap_stack`。

2. **`.stack` / `.heap` 段当前是空的。** GCC map `:23861-23919` 显示
   `.stack 0x200550c0 0x0`、`.heap 0x200550c0 0x0` —— 没有任何输入段落进去。
   真正的栈空间来自 `._user_heap_stack` 里 `. = . + _Min_Stack_Size`
   预留的地址空洞，**不是一个有名字、可填充、可扫描的段**。
   §4.2 第 1/3 条正是要把这个空洞换成一个真正的、有符号、可填充、可扫描的栈区。
   **段名已冻结，不给你选择权**：新栈区段名必须是 `.ota_stack`，guard 段名必须是
   `.ota_stack_guard`。这两个名字被九条 ASSERT（A1-A9）与探针 `cases.json` 逐条
   引用，改名会让 ASSERT 全部失效或需要连带改判据。因此**不得**复用现存的空段
   `.stack`：那两个空段既不改名也不承担新职责，保留原样（若你确认它们完全无用，
   删除属于本卡范围之外的清理，不要在本卡顺手做）。

3. **`MDK-ARM_F435/cmake-generated/cmake/gcc_runtime_compat.c` 是 git 跟踪的
   手写文件，不是生成物。** `git ls-files MDK-ARM_F435/cmake-generated/cmake/`
   列出它；生成脚本无相关命中。所以它**可以改**，且已列入 §1.1 本卡范围 ——
   但授权范围仅限 §4.2 第 5 条（`_sbrk` 上限改 `__StackGuardStart`）与 §4.5
   第 1 项（`sbrk_call_count` / `sbrk_peak` 计数与读取接口）。
   该文件内其余内容不得改动。

4. **`P2_x_TEST_ENABLE` 是既有 harness 模式，照它办；但本卡的开关不进 linker
   define。**
   `MDK-ARM_F435/cmake-generated/CMakeLists.txt:48-90` 定义
   `option(P1_6_TEST_ENABLE / P2_1_ / P2_2_ / P2_3_ ... OFF)`，两两
   `message(FATAL_ERROR "... mutually exclusive")`，经 `:78-89` 的
   `OTA_TEST_LINKER_DEFINES` 以 `-DP2_x_TEST_ENABLE=1` 传给 `:97` / `:111` 的
   ld 预处理；`ld.S:13-20` 用 `#if defined(...)` 切出控制区。

   **本卡的三条硬约束（已裁定，不要自行改动）**：
   - `option(P2_6_TEST_ENABLE ...)` 与它同 `P1_6_`/`P2_1_`/`P2_2_`/`P2_3_` 的
     **四条两两互斥**必须写在 `48-90` 这段既有 option 区内（§1.1 已相应扩权），
     不要在文件别处另起一套开关。
   - **禁止把 `P2_6_TEST_ENABLE` 追加进 `OTA_TEST_LINKER_DEFINES`。**
     理由：栈区/guard 段布局、`__Stack*` 符号、`STACK$$*` 别名、九条 ASSERT
     全部是**永久生产改动**（§4.9），生产构型也必须成立，`ld.S` 里不需要、
     也不允许出现 `#if defined(P2_6_TEST_ENABLE)` 包裹这些内容。
     若 ld 预处理拿不到这个宏，正是预期结果。
   - `P2_6_TEST_ENABLE` 只通过 `target_compile_definitions` 作用于 C/C++ 侧的
     **测量与输出插桩**（RTT 打印、采集点、计数器）。构型边界见 §4.9。

5. **GCC startup 只清零 `.bss`，不清栈区。**
   `MDK-ARM_F435/cmake-generated/cmake/sources/startup_at32f435_437_gcc.S:157-184`：
   `ldr r0,=_estack; mov sp,r0` → `extend_sram_512k` → `SystemInit` →
   copy `.data` → `.Lfill_bss` 只覆盖 `_sbss.._ebss` → `:183 __libc_init_array`
   → `:184 bl main`。**栈区没有任何填充**。而 `Libraries/StackInfo/StackInfo.h` 的
   `STACK_INFO_BLANK ((uint32_t)0x00000000)` 假设「未用过的栈是 0」。
   AT32 上电 SRAM 内容不保证为 0，热复位更不保证 —— **直接照搬 StackInfo
   的扫描法在 GCC 上会给出无意义的数字**。

### 4.4 采集与输出时机（做错会污染被测量的对象）

1. **P2-6 自检构型开关名用 `P2_6_TEST_ENABLE`**，沿用 §4.3 第 4 项的既有模式，
   并补齐与全部既有构型（`P1_6_` / `P2_1_` / `P2_2_` / `P2_3_`）的两两互斥
   `FATAL_ERROR`。不要另起一套开关名。
2. **测量值先存内存，退出关键路径后再格式化输出。** `SEGGER_RTT_printf` 自身要
   分配栈帧、走 vsnprintf，在 OTA 关键窗口内调用它会把它自己的栈消耗算进峰值，
   使测得的数字偏大且不可复现。正确顺序：关键路径内只做「读值 → 存静态变量」，
   离开关键路径后再统一 RTT 打印。
3. **最终必须关闭 `P2_6_TEST_ENABLE`、fresh 重建生产固件，并证明测量标记不存在。**
   要求给出**五样东西**：① fresh configure + build 的完整命令与 rc；
   ② 生产 `.elf/.hex/.bin/.map` 的时间戳与 SHA-256；
   ③ **清单 L2 在生产产物中零命中** —— 搜索清单不是自由发挥，必须逐项照 §4.9 C 项
   的三份清单与介质分工执行，给出零命中的命令与输出；
   ④ **清单 L1 在 `P2_6_TEST_ENABLE=1` 构型上全部命中的正向证明**
   （否则零命中也可能只是搜索命令写错）；
   ⑤ **清单 L3 在两个固件构型上都零命中**（B' 组是宿主专属，不进 L1）。
   注意 ③④⑤ 是**三份不同的清单**，不是同一份清单跑三遍；宏名只在 CMake cache /
   `compile_commands.json` / 编译命令行里核对，不在 ELF/map 里搜（§4.9 C 项）。
   只说「已关闭宏」不算证明，只给零命中一组也不算完成。
4. 采集点调用 `StackInfo` 的四个函数即可（真实调用链同时满足 §4.2 第 6 条的保活）。

### 4.5 堆侧排除性证明：OTA 窗口无新增分配（required）

栈 8192B + 池 40960B 只有在「OTA 期间不从别处借内存」的前提下才是完整预算。
本卡必须给出三组机器可读证据，**不接受「代码里没看到 malloc」这类静态推理**。

**1）`_sbrk` 调用计数与峰值（主要判据）。**

在 `gcc_runtime_compat.c` 的 `_sbrk` 内新增两个静态量并提供读取接口：
- `sbrk_call_count`：每次进入 `_sbrk` 就自增（成功失败都算）。
- `sbrk_peak`：`current` 达到过的最大值（单调，不随负增量回落）。

判据：**OTA 核心 apply 窗口的 `sbrk_call_count` 增量必须为 0**。

**为什么不能只看 `current` 前后相等**：`_sbrk` 支持负增量
（`gcc_runtime_compat.c:44-53` 的 `decrease` 分支），所以「进出时 `current` 相同」
完全可能是「中途长上去又缩回来」，那段时间堆确实占用过 RAM，可能与栈相撞。
调用次数增量为 0 才能排除这种情况；`sbrk_peak` 用于给出历史最高水位。

**2）LVGL 池：调用级计数（required）+ 净状态对比（佐证）。**

**先看清一个陷阱**：`lv_mem_monitor()` 的四个字段**都不足以排除 OTA 窗口内的
瞬态分配**，撰写会话已逐行核实 `Simulator/LVGL.Simulator/lvgl/src/misc/lv_mem.c`：

- `max_used` 是文件级 static 单调量（`:58-59` 声明，`:155-162` 仅在 `lv_mem_alloc`
  成功路径更新）→ 一个启动阶段就达到的历史峰值，OTA 期间无论发生什么都不变。
- **`lv_mem_realloc()`（`:194-217`）根本不更新 `cur_used` / `max_used`**，
  它只调 `lv_tlsf_realloc` 就返回 → **realloc 引起的占用增长在四个字段里完全
  不可见**，`max_used` 也不会因此上升。
- `free_size` / `free_biggest_size` / `frag_pct`（`:246-269` 由
  `lv_tlsf_walk_pool` 现算）是**瞬时快照**：窗口内 alloc 后又 free、
  或原地 realloc 增长后再缩回，进出两次快照可以完全相同。

所以「四字段差值为 0」只能证明**净状态未变**，**不能**证明窗口内没有分配。

**required 判据 = 调用级计数增量为 0**，用 test-only 链接期打桩实现，
**不改 LVGL 源码**。

**【拦截层级已由撰写会话实测裁定：必须包 `lv_tlsf_*`，不是 `lv_mem_*`】**

探针 `tests/ota/spec-probes/p2-6/wrap_probe/`（`arm-none-eabi-gcc 13.3.1` + 宿主
`gcc 15.2.0`，四构型矩阵 mem/tlsf/both/prod，`python
tests/ota/spec-probes/p2-6/wrap_probe/run.py` rc=0 全通过）实测：

- 复刻 LVGL 两层结构（`lv_mem.c:134` 的 `lv_tlsf_malloc(tlsf, size)` 是跨翻译
  单元调用，`lv_tlsf.c:1098` 定义实现）后，模拟 `lv_mem_buf_get(48)` 这个
  **`lv_mem.c` 内部入口**：真实池**确实发生了 1 次分配**，而
  `--wrap=lv_mem_alloc` 的 wrapper 计数增量是 **0**。
  → 这是**静默假通过**：判据读到 0 会宣告「窗口内无分配」，而池已经被动过。
- 同一场景下 `--wrap=lv_tlsf_malloc` 的增量是 **1**，覆盖该盲区。
  `both` 构型同时观察两层，确认 `mem_a=0 && tlsf_a=1`。
- **盲区比「拦到但没重定向」更彻底**：反汇编（`arm_both.dis`）显示 `-O2` 下
  `lv_mem_buf_get` 与 `lv_mem_alloc` 都被尾调用折叠，指令直接
  `b.w __wrap_lv_tlsf_malloc` —— **上层调用点在链接前就已不存在**，
  `nm` / map 里也看不到任何痕迹。所以「没拦住」这件事**没有任何链接期迹象
  可供发现**，只能靠上面这种正负例对照测出来。

因此本卡指定：

- 仅在 `P2_6_TEST_ENABLE` 构型下给 App 目标加
  `-Wl,--wrap=lv_tlsf_malloc,--wrap=lv_tlsf_realloc,--wrap=lv_tlsf_free`
  （**这是 required 判据的拦截层**），在你自己的测试插桩文件里实现
  `__wrap_lv_tlsf_malloc` / `__wrap_lv_tlsf_realloc` / `__wrap_lv_tlsf_free`：
  各自自增计数器后**原样转发**到 `__real_lv_tlsf_*`，不得改变参数、返回值
  或调用顺序。
- 可以**额外**包一层 `--wrap=lv_mem_alloc/realloc/free` 作为分层归因
  （区分「LVGL 外部调用者」与「LVGL 内部入口」），但它**不能单独充当 required
  判据**。真实项目里 `lv_tlsf_*` 由 `lv_mem.c` 跨 TU 调用，`--wrap` 可拦；
  你必须用 map/`nm` 复核这一点仍然成立（若某次编译把 `lv_mem.c` 与 `lv_tlsf.c`
  合并为同一 TU 或启用了 LTO，则该层同样会失效 —— 见下面第 4 项）。
- 判据（**冻结口径，§9 C6 与本条完全一致，不得各写一套**）：
  - **门禁项**：OTA 核心 apply 窗口内 `lv_tlsf_malloc` 与 `lv_tlsf_realloc` 的
    调用计数增量**均为 0**。非 0 即 `PRODUCT_FAIL`（窗口内确实借了内存）。
  - **交叉核对项**：`free` 计数增量**必须实测并如实记录**，但它**不是**预算门禁
    —— `free` 不占新内存。然而 `free` 增量非 0 意味着 OTA 窗口内 LVGL 池确有活动，
    与 §4.5 第 3 项「窗口内 LVGL 自身未被驱动」的排除性论证直接冲突。因此：
    `free` 增量为 0 → 正常；非 0 → **必须定位到具体释放点**（哪个调用者、
    释放的是窗口前分配的哪块），说明它为何不影响峰值预算；给不出定位即本判据记
    `EVIDENCE_GAP`，**不得**以「free 不设门禁」为由静默放过。
- **`--wrap` 只允许出现在 `P2_6_TEST_ENABLE` 构型**。生产构型不得带该选项，
  并按 §4.4 第 3 项一并证明 `__wrap_lv_*` 与 `__real_lv_*` 符号在生产产物中
  零命中（它们属 §4.9 C 项清单 L1/L2 的**符号**类，核对介质是 `.elf` + `.map`；
  探针实测：生产构型 14 个测量符号全部消失，map 内也无 `__wrap_`/`__real_`）。
  这条不与红线 4 冲突：红线 4 禁的是关闭/绕过 `--gc-sections`，不是禁止
  test-only 打桩；但你**不得**借机改动任何其他全局链接选项。

**你必须复跑并留证的八项（探针已全部实测通过，写法可照用）**：

| # | 项 | 探针实测结论 |
|---|---|---|
| 1 | `__wrap_*` 进入最终 ELF 与 map | ARM 构型 14/14 符号命中、map 6/6 wrapper 命中 |
| 2 | `__real_*` 正确转发、无未解析残留 | `nm` 无 `U __real_*` |
| 3 | 参数/返回值/调用顺序不变 | 序列指纹四构型全等（`163`）、`last_size=48`、`ret_nonnull=1` |
| 4 | 正例增量为 0 | 三种插桩构型场景 A 全零 |
| 5 | 负例增量非零 | alloc/realloc/free 三路径各 +1 |
| 6 | wrapper 关闭后生产构型符号全消失 | 14 个符号全消失、map 无 `__wrap_`/`__real_` |
| 7 | `--gc-sections` 不误删 wrapper | 见第 1 项（须让每个 wrapper 都被真实引用） |
| 8 | 明确无 LTO | 命令行无 `-flto` |

第 3 项的做法比「计数相等」强得多，建议照用：在真实实现侧维护一个**调用序列
指纹**（例如 `seq = seq * 5 + opcode`，malloc/realloc/free 各一个 opcode）
与「最后一次请求大小 / 返回值是否非空」，然后要求**插桩构型与生产构型得到
完全相同的指纹**。计数相等只能说明次数没变，指纹相等才能说明顺序也没变。

**【探针踩坑，你会遇到同样两个】**

- **wrapper 定义集合必须与 `--wrap=` 集合严格一一对应。** 实测：定义了
  `__wrap_X` 却没在命令行传 `--wrap=X` 时，`__real_X` 是**未定义引用，链接
  直接失败**（fail-closed，不会静默降级）。所以两层 wrapper 要用两个独立宏
  分别门控（探针用 `P2_6_WRAP_MEM` / `P2_6_WRAP_TLSF`），不要一个宏包住六个。
- **未被引用的 wrapper 会被 `--gc-sections` 删掉，造成第 1 项假失败。**
  探针第一版只调 alloc 路径，`realloc`/`free` 四个符号全被删。你的鉴别力
  用例必须真实走到每一条被包的路径。

**佐证（仍然要做，但不是唯一依据）**：OTA 入口与出口各取一次
`lv_mem_monitor()` 快照，记录并比较 `free_size`、`free_biggest_size`、
`frag_pct`、`max_used` 四个字段。默认允许差值为 0；若实测存在非零差值，
必须解释来源并由验收合同显式接受，不得事后放宽。

**覆盖边界（必须原样写进证据文档，不得含糊）**：`--wrap` 只改变**跨目标文件**
的符号解析。包 `lv_tlsf_*` 之后，仍不能拦截 `lv_tlsf.c` **内部**对
`lv_tlsf_malloc/realloc/free` 的同 TU 直接调用。因此准确表述是
「**OTA 窗口内没有任何跨 TU 调用者向 LVGL 池申请或释放内存**」。
配合下面这条，才够支撑 required 判据：

- **必须另外证明 OTA 窗口内 LVGL 自身没有被驱动。** 即 `lv_task_handler` /
  `lv_timer_handler`、LVGL 定时器、以及任何异步回调在核心 apply 窗口内**未
  运行**（给出调用点与窗口关系的证据，例如窗口内主循环被阻塞、或 handler
  入口计数增量为 0）。**只给 `--wrap` 计数为 0 而不证明这一条，等于没有排除
  LVGL 内部活动。**

**若 `--wrap` 在本项目构建里被证明不可行**（例如 `lv_mem.c` 与 `lv_tlsf.c` 被
合并为同一 TU、启用了 LTO、或调用被内联消除 —— 你必须用 map/反汇编给出证据，
探针里的反汇编检查可直接照搬）：本判据**降级**为「LVGL 池净状态未变化」，
且必须在证据文档与矩阵里显式写明「**该判据不排除窗口内瞬态分配**」，
按 `EVIDENCE_GAP` 处理这一部分，**不得**表述为「已证明 OTA 窗口无 LVGL 分配」。

**3）AC5 `__heapstats`（辅助，非门禁）。**

可以采，但只作交叉参考。要把它升为 required，必须先证明它给的是峰值而非
当前快照（ARM 文档未承诺峰值语义）。未证明前，在证据文档里标注「辅助证据」。

### 4.6 仍需你自行判断并落盘的点

1. **AC5 的定位已裁定为 auxiliary，不是自选项，不要再做取舍判断。**
   依据：`AGENTS.md` 首段明确 AC5 只是本地硬件调试/工具链对照的辅助路径，
   **不得升为 OTA/CI 产物**；OTA 生产固件是 GCC。
   本卡对 AC5 的要求**仅限**：
   - 提供 AC5 静态 RAM 高水位与 `Program Size` 作为对照（§9 C9），
     因为它是 `PLAN-OTA.md` §9 预算表里余量更紧的一条（`8936B`）；
   - **不做**哨兵填充、**不做** guard、**不产出 AC5 栈峰值**；
   - `MDK-ARM_F435/RTE/Device/-AT32F435RGT7/startup_at32f435_437.s`
     **不在本卡范围内**（§1.1 未列出），不要去改它。
   相应地，**AC5 的任何结果都不构成本卡的阻断条件**；AC5 栈测量若将来确有需要，
   另立卡处理，不在 P2-6 内做。
2. **主 RAM 余量表的重算口径。** 明确你用 GCC 的哪个地址作高水位
   （`_ebss` 还是 `._user_heap_stack` 末）。P0-6 用的是后者
   （`docs/ota-exec-notes/P0-6-ram-baseline-overlay.md` 明写「GCC 则以
   `._user_heap_stack` 末地址作为静态保留高水位」），**回填必须与 P0-6 同口径**，
   否则两份数字不可比。注意 §4.2 第 3 条改完后 `._user_heap_stack` 不再含栈预留，
   新口径下「静态保留高水位」应改为 **guard 区起始 `__StackGuardStart`**
   （不是 `__StackLimit` —— guard 区也是被占用的 RAM，只是用途是检测而非栈），
   并在回填处写清口径变更与 guard 单列的 32B，不要让两代数字看起来像同一把尺子。
3. **`$$` 符号可行性已由撰写会话实测结论给出**（见 §4.2 第 2 条与
   `docs/ota-exec-notes/P2-6-spec-stack-feasibility-2026-08-15.md`）：
   ld 不需引号、gcc 默认接受、端到端链接通过，**默认不启用 `#if __GNUC__` 退路**。
   你需要做的是在自己的构建里**复跑一次 `nm` 与 map 确认**并贴出输出；
   只有当你的实测与该结论相反时，才改走退路并说明差异原因。

### 4.7 预算与判定口径（不要因为接近阈值就去动红线）

- **固定池**：`workspace_peak ≤ 40960B` 即通过。P2-3 已实测 `21832B`（53.3%），
  余量充裕，**正常情况不应触发降档**。
- **调用栈（产品门禁）**：**两条同时成立**才通过 —— 峰值 `≤ 8192B`
  **且** guard intact。门槛来源分类 = `protocol_contract`
  （`OTA_STACK_RESERVE`，`docs/ota-binary-contracts.md` §10），**不是**历史观测值。
  - 注意是 `≤` 而**不是** `<`：外置 guard 布局下 `峰值 == 8192B` 是**有效的
    零余量观测**，记 PASS 并在报告里显著标注「余量为 0」。
  - guard 破损 → `PRODUCT_FAIL`（峰值数字此时不可信）。
  - **产品门禁的结论只有在 §4.8 的 measurement-validity 判据通过后才成立。**
- **堆**：`sbrk_call_count` 在 OTA 核心 apply 窗口增量为 0；LVGL 侧
  `alloc`/`realloc` 调用计数增量为 0（§4.5 第 2 项，含降级条款）。
- **主 RAM 余量**：**没有门槛**，P2-6 只要求「回填实测值」。
  §2.3 显示余量已经很紧（GCC 改动前 `7488B`，按 §4.2 第 3 条改完约 `3360B`
  外加单列的 32B guard），这是**事实陈述，不是本卡的失败条件**。
  不要为了让数字好看去删 LVGL 缓冲、改 `LV_MEM_SIZE`、或把
  `xtrack_img_line_cache` 改成动态 —— 那些都在范围外且会踩治理 CI。
- **降档条件**：只有在**成功 acquire overlay 之后**发生容量不足
  （即 `*_ERR_WORKSPACE`），并且**已按 §3.3 在宿主用足够大的容量成功跑出完整的
  `arena_peak_observed`** 且该完整值 `> 40960B` 时，才允许提议把字典降 8KiB。
  **不得**仅凭真机一次失败时读到的 `arena_peak_observed` 判断超出幅度 ——
  失败路径上那个值只是**下界**（§3.2 语义）。
  **overlay owner 冲突不算超限**（§3.2 语义精度要求）。
  这**不是**你能自决的（见 §5 红线 2 与 §6 停止条件 5）。

### 4.8 measurement-validity 判据（与产品门禁分开评判，required）

产品门禁（`峰值 ≤ 8192B` + guard intact）**不能自证有效**：扫描边界接反、
`STACK_INFO_BLANK` 与哨兵不一致、栈段被挪位，都会产出一个「看起来通过」的数字。
因此本卡必须**另设一条独立判据**，逐项验证测量本身可信，
并**先于**产品门禁评判。

**必须验证的 8 项（缺一项即不通过）**：

1. 栈边界符号取值正确：`nm` / map 实测 `__StackLimit`、`__StackTop`、
   `__StackGuardStart`、`__StackGuardEnd` 四个地址，与 §4.2 第 1 条布局图一致。
2. `STACK$$Base` / `STACK$$Limit` **方向正确**：`STACK$$Base` 是低地址、
   `STACK$$Limit` 是高地址，相减恰为 `8192`（接反会得到负数或巨大值）。
3. **guard 区不在 StackInfo 扫描范围内**：给出扫描起止地址，证明它等于
   `[__StackLimit, __StackTop)`，且与 `[__StackGuardStart, __StackGuardEnd)`
   无交集。
4. 哨兵常量与 `STACK_INFO_BLANK` **一致**：给出两处定义的实际取值并逐字节比对。
5. **正例有鉴别力**：构造一个已知消耗约 `1024B` 的调用路径，扫描必须测得
   约 `1024B`（允许偏差就是第 7 项量化的测量开销，须在报告里对上账）。
6. **三类负例必须被拒绝**（各给一次实际运行的证据，不接受推理）：
   ① `STACK_INFO_BLANK` 故意写错（与哨兵不一致）→ 结果被识别为无效；
   ② 栈边界故意接反或指向错误地址 → 结果被识别为无效；
   ③ guard 被故意踩破 → 报 guard 破损。
   负例允许在**宿主**上做（`tests/ota/spec-probes/p2-6/host_scan/` 已有可复用
   骨架，S2/S4/S5 分别对应上面三类），不必在真机上制造越界。
7. **StackInfo 扫描调用自身的栈开销已量化**：按 §4.2 第 7 条给出字节数与测法。
8. 扫描区在 startup 后**确实被哨兵填满**：至少给出一次「填充后立即扫描」的
   观测，结果应为「已用 = 采集路径自身开销」量级，而不是 0 或 8192B。

**结果分类（6 条，严格按此判，不得混用）**：

| 观测情形 | 结果 |
|---|---|
| 已证明 scanner 逻辑错、栈边界错、或构型配置错 | `HARNESS_FAIL` |
| 无法判断「扫描失效」还是「真实满栈」（证据不足以区分） | `EVIDENCE_GAP` |
| 有效测量，峰值 `> 8192B` | `PRODUCT_FAIL` |
| guard 损坏（无论峰值多少） | `PRODUCT_FAIL` |
| 有效测量，峰值 `== 8192B`，外置 guard intact | `PASS`（报告标注**零余量**） |
| 有效测量，峰值 `< 8192B`，guard intact | `PASS` |

**注意**：第 2 行的 `EVIDENCE_GAP` 是原「峰值恰等 8192B 一律 HARNESS_FAIL」
规则的正确替代 —— 判据看的是**证据能否区分两种成因**，不是看数值是否等于某个
特征值。若 8 项验证全部通过，`8192B` 就是可信的零余量观测，不是失效特征值。

### 4.9 永久生产改动 vs 测试插桩：构型边界（冻结，不得挪动）

本卡的改动分两类，**边界写死在这里**。放错一边的后果：把永久改动做成 test-only
→ 生产固件仍然没有 8192B 硬保证；把测试插桩留进生产 → 生产固件带上 RTT 输出与
计数器，§4.4 第 3 项的清单 L2 零命中证明必然失败。

**A. 永久生产改动（两种构型都必须存在，不受任何 `P2_x_TEST_ENABLE` 影响）**

1. `ld.S`：8192B 可用栈区段、32B guard 区段、九条 ASSERT A1-A9（§4.2 第 1 条）。
2. `ld.S`：`__StackTop` / `__StackLimit` / `__StackGuardStart` / `__StackGuardEnd`
   四个符号，以及 `STACK$$Base` / `STACK$$Limit` 两个兼容别名。
3. `ld.S`：`._user_heap_stack` 删除栈预留（§4.2 第 3 条）。
4. `gcc_runtime_compat.c`：`_sbrk` 上限改 `__StackGuardStart`（§4.2 第 5 条）。
5. `startup_at32f435_437_gcc.S`：哨兵填充 + guard 魔数写入（§4.2 第 4 条）。
   **它是永久改动**：生产固件也必须有可信的栈边界与越界检测基础，
   且填充发生在首个 C 调用前，成本是一次约 2048 字的写循环，不进入 OTA 窗口。
6. `StackInfo.c` / `.h`：GCC 分支、工具链护栏、`STACK_INFO_BLANK` 取值。

**B. 仅测试构型（`P2_6_TEST_ENABLE=1` 才编入，生产构型必须零命中）**

1. 全部 RTT 输出（格式串、`SEGGER_RTT_printf` 调用点）。
2. 测量采集点（OTA 入口/出口调用 StackInfo、`lv_mem_monitor` 快照）。
3. `sbrk_call_count` / `sbrk_peak` 计数器与其读取接口。
4. `__wrap_lv_tlsf_malloc` / `__wrap_lv_tlsf_realloc` / `__wrap_lv_tlsf_free`
   （required 拦截层）以及可选的 `__wrap_lv_mem_*` 分层归因，
   及其 `-Wl,--wrap=...` 链接选项（§4.5 第 2 项）。
5. 所有 `P2_6_` 前缀的符号、宏与格式串。
6. §4.8 第 6 项的三类负例开关（若你用编译期开关实现）。

**B'. 宿主 harness 专属（两个固件构型都必须零命中，含 `P2_6_TEST_ENABLE=1`）**

§3.3 的容量覆盖宏 `OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE` 与函数
`ota_p2_6_host_arena_capacity`。它**只**出现在宿主 harness 的编译命令行里，
与 `P2_6_TEST_ENABLE` 无关，因此它属于「两侧都零命中」，
只进下面的清单 **L3**，**不进**正向命中清单 **L1**。
把它单列，免得你为了凑正向命中而误把它塞进固件构型。

**C. 三份互不混用的搜索清单（§4.4 第 3 项要求的证明，逐项给命令与输出）**

> **【本条已于 2026-08-16 按派单前置整改裁定重写（阻断 2）。原文只有「一份清单
> 跑正反两组」，与 B' 组「两个固件构型都零命中」直接矛盾 —— 任何合规实现必然
> 违反其中一条。不要照抄任何早期版本。】**

清单必须**拆成三份**，每份的项集合、构型和期望都不同：

| 清单 | 项集合 | 构型 | 期望 |
| --- | --- | --- | --- |
| **L1** | 仅 B 组测试插桩项 | `P2_6_TEST_ENABLE=1` | **全部命中**（正向证明） |
| **L2** | B 组 + B' 组（= L1 ∪ L3） | 生产（宏关闭，fresh 重建） | **全部零命中** |
| **L3** | 仅 B' 组宿主专属项 | **两个固件构型都要**（含 `P2_6_TEST_ENABLE=1`） | **全部零命中** |

集合关系必须成立：`L1 ∩ L3 = ∅`、`L2 = L1 ∪ L3`。把 B' 组项塞进 L1，正向证明
必然失败；把 B' 组项漏出 L2，生产零命中就漏检宿主专属符号。

**L1（同时是 L2 的前半）—— B 组项**：

- 符号前缀：`P2_6_`
- 包装符号：`__wrap_lv_tlsf_malloc`、`__wrap_lv_tlsf_realloc`、
  `__wrap_lv_tlsf_free`、`__real_lv_tlsf_malloc`、`__real_lv_tlsf_realloc`、
  `__real_lv_tlsf_free`，以及你实际启用的 `__wrap_lv_mem_*` / `__real_lv_mem_*`
  （**清单必须与你实际传的 `--wrap=` 集合一一对应** —— 见 §4.5 的 fail-closed 实测）
- 计数器符号：`sbrk_call_count`、`sbrk_peak`（及你实际采用的名字）
- 你新增的采集函数名（把实际函数名逐个列进证据文档，不要只写「我的采集函数」）
- 你新增的全部 RTT 格式串字面量（逐条列出实际字符串）
- 宏名：`P2_6_TEST_ENABLE`（**核对介质见下面「介质分工」，不在 ELF/map 里搜**）
- §4.8 第 6 项三类负例开关（若你用编译期开关实现，按其实际形态归入符号或宏）

**L3（同时是 L2 的后半）—— B' 组项**：

- 符号：`ota_p2_6_host_arena_capacity`
- 宏名：`OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE`（同样按宏的介质核对）

**介质分工（介质选错等于判据失效，必须照此执行）**：

| 项的形态 | 核对介质 | 工具 |
| --- | --- | --- |
| 符号 | `.elf` + `.map` | `arm-none-eabi-nm`、`arm-none-eabi-objdump -t`、map 文本搜索 |
| 字符串字面量 | `.elf` 的 `.rodata` | `strings`、`arm-none-eabi-objdump -s -j .rodata` |
| **预处理宏名** | **`CMakeCache.txt` + `compile_commands.json` + 构建日志的编译命令行** | 文本搜索 |

预处理宏名在编译期就被展开消掉，**不会**作为标识符进入目标文件（除非它恰好也是
某个导出符号名，或被 `#` 串化成字符串字面量）。所以：

- **不得**要求「宏名出现在 ELF/map」—— 该正向判据对任何合规实现都必然失败。
- **不得**把「ELF/map 里搜不到宏名」当成生产构型干净的证据 —— 那个零命中恒成立，
  零鉴别力。
- 宏的两个方向都在**构建输入侧**核对：生产构型的 `CMakeCache.txt` 与
  `compile_commands.json` 里**不得**出现 `P2_6_TEST_ENABLE=1` 与
  `OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE`；测试构型的 `compile_commands.json` 里
  **必须**出现 `-DP2_6_TEST_ENABLE=1`（或 CMake 生成的等价形式），且必须覆盖你
  实际插桩的**每个**翻译单元，不是只命中一处就算过。

**字符串字面量的一个例外处理**：若某条 RTT 格式串在测试构型 ELF 里也搜不到，
先查是不是被编译器合并/拆分（`-fmerge-constants`）或 `--gc-sections` 回收，
而不是直接判 FAIL。此时你有两条合规出路：给出该字面量确实被引用的反汇编证据，
或把它从 L1 移出并写明理由。**不得**默默改小 L1 使正向证明看起来通过。

**三组输出全部贴进证据文档**（L1 正向、L2 生产零命中、L3 两侧零命中），
缺任一组即 §9 的 C12 / C15 记 `EVIDENCE_GAP`。只给 L2 一组不算完成 —— 那排除不了
「搜索命令本身写错所以什么都搜不到」。

**D. 插桩固件的测量值凭什么迁移到生产固件（必须逐轮实测，不存在通用前提）**

产品门禁判的是**生产固件**的栈峰值，而测量只能在**插桩固件**上取得。

> **【本条已于 2026-08-16 按独立复核裁定重写。原文写的「B 类插桩只增加栈消耗，
> 故插桩峰值是生产峰值的上界」已被撰写会话实测推翻，不要照抄任何早期版本。】**

**为什么「插桩只会更大」不成立（实测反例）**：

`P2_6_TEST_ENABLE` 不只是「多一个调用」—— 它会改变内联决策、寄存器分配、
spill、父函数栈帧、尾调用、跨函数常量传播、代码布局和调用结构。这些变化
**可以让某个函数的栈帧变小**。探针 `tests/ota/spec-probes/p2-6/stack_usage/`
（`arm-none-eabi-gcc 13.3.1`，四层 OTA 调用链，`-fstack-usage`；反例由
`python tests/ota/spec-probes/p2-6/stack_usage/scan4.py` 冻结并 fail-closed 判定）
实测到的反例：

| 构型 | `ota_apply` 栈帧 | 链上求和 |
|---|---|---|
| 生产 | **992 B** | 992 B |
| 插桩（计数 + 采集点 `noinline`） | **520 B**（小 472 B） | 1000 B |
| 插桩（+ 96B 快照） | **520 B** | 1032 B |
| 插桩（+ 512B 快照） | **520 B** | **1448 B** |

机制：插桩使采集点所在函数不再被内联（`ota_stage_verify` / `ota_hash_block`
从「无独立条目」变为独立栈帧 280B / 648B），父函数因此**不再折叠**子函数的
局部缓冲，`ota_apply` 的栈帧反而缩小 472B —— 而**链上真实峰值同时变深**
（992B → 1448B）。若按原论证拿插桩构型的 `ota_apply` 当生产上界，会**低估
472B**。

**这不是人为构造的边缘情况**：P2-6 需要按函数归属栈帧，而被内联的函数在
`.su` 里**没有独立条目**，所以插桩构型抑制内联是常态需求，不是意外。
（作为对照，撰写会话另做了三轮否证尝试：单调用点链 21 配置（`scan.py`）、
多调用点链 18 配置（`scan2.py`）、体积膨胀型插桩 7 配置（`scan3.py`），
**均未触发反例** —— 说明单纯加大插桩体积或快照尺寸不足以发现该问题，
必须比较内联结构。别把「我扫了很多尺寸都没事」当成单调性成立的证据。）

**因此本卡要求（逐轮实测，缺一项即 `EVIDENCE_GAP`）**：

1. **两构型各自产出并保存静态栈使用数据**：生产构型与 `P2_6_TEST_ENABLE=1`
   构型分别带 `-fstack-usage` 编译，保存全部 `.su`（或等价数据）作为原始证据。
   实测确认本工具链 `.su` 的 qualifier 全为 `static`（无 `dynamic`/VLA），
   数值可直接求和；**但 `-O2` 下被内联的函数没有独立 `.su` 条目**，
   「按调用链逐函数查表求和」会漏算 —— 必须以**实际存在的条目**为准，
   并显式列出哪些链上函数已无独立条目。
2. **逐函数比较 OTA 活跃调用链上的每个函数**，而不是只比总量。对每个函数给出
   「生产 / 插桩 / 关系」三列，并**单独列出插桩更小或独立条目出现/消失的函数**
   —— 这些正是迁移性论证的风险点。
3. **比较两构型的内联与尾调用差异**：给出两构型反汇编中实际存在的函数体集合
   （`objdump -d` 的函数标签），列出仅在一侧存在的函数。探针的做法可照搬。
4. **证明采集点在核心 apply 窗口之外**（否则采集自身的栈帧会进入被测峰值）。
5. **证明 wrapper 未改动 OTA 路径**：`--wrap` 只转发、诊断字段不进控制流
   （红线 3）；给出 OTA 相关函数在两构型 map 中的存在性与地址差异说明。
6. **纳入中断栈预算**：`StackInfo` 观测的是主栈被改写深度，异常/中断在同一 MSP
   上再压栈帧。给出异常帧大小 × 允许嵌套层数的预算，并说明它与 8192B 的关系。
   异常帧大小**不是只看 `-mfloat-abi`**，必须逐项交代下面五个量，任一未交代即
   本项不成立：
   ① 基本帧 32B（xPSR/PC/LR/R12/R3-R0）；
   ② FPU 扩展帧 +72B（S0-S15 + FPSCR + 保留字）—— 只在**该异常发生时 FP 上下文
     已激活**才压，且 `FPCCR.LSPEN` 懒压栈会把实际压栈时机推迟到后续 FP 指令，
     **预算必须按最坏情况（已压）算**，不能因为"当前没跑 FP"就省掉；
   ③ 栈对齐调整字 +4B（`CCR.STKALIGN`，进入异常时 SP 不是 8 字节对齐则补一字）；
   ④ **ISR 自身的软件保存帧**（被调用者保存寄存器 + ISR 局部变量 + ISR 内的调用
     链）—— 用 ISR 的 `.su` 数据，不能只算硬件帧；
   ⑤ **NVIC 最大抢占嵌套层数**：按实际优先级分组（`AIRCR.PRIGROUP`）与各中断
     配置的抢占优先级列出可同时嵌套的最坏组合，不是笼统写「假设 2 层」。
   预算 = Σ（每层的 ①+②+③+④），层数取 ⑤ 的最坏值。
7. **共享 A 类布局**：两种构型的栈区/guard/符号/ASSERT 完全相同（A 类是永久
   改动），「8192B 这把尺子」在两边是同一把。给出两构型 map 中四个栈符号地址
   相同的实测对比。

**若上述比较显示插桩构型在 OTA 活跃链上存在「比生产更小」的函数栈帧，或两构型
内联结构不同且你无法论证最深路径不受影响，则不得把插桩测量值迁移为生产结论**
—— 按 `EVIDENCE_GAP` 记录，或改为直接测量生产固件（例如生产构型保留哨兵与
guard，仅用一次性外部手段读取水位）。**不要**用「插桩版测到多少就是多少」
含糊交差，也**不要**引用任何形式的「插桩恒为上界」作为前提。

### 4.9-E 最大 SP 上界的两条闭环路线（C3 唯一允许的两种取证方式）

> **【本节为 2026-08-16 定向复核裁定新增，取代早期任何「四选一」写法。】**
> 早期版本把「`-fstack-usage`」「调用链求和」「中断嵌套预算」「最低 MSP 探针」
> 并列成四个可替代项，这是错的：
> - `-fstack-usage` **只是逐函数数据源**，本身不构成任何上界；
> - 只有把它按**OTA 实际调用图的最大路径**求和，才得到**线程态**栈上界；
> - 中断/异常嵌套预算必须**叠加**到线程态上界之上，它不能单独替代调用链求和
>   （反过来也不行）；
> - 最低 MSP 探针只有在能证明**连续覆盖所有瞬态最低点**时才可替代静态闭环，
>   离散采样（定时器轮询、断点、事后读 SP）**不够**。

**你必须在下面两条路线里选一条，并把所选路线的每一项都做完。**
跨路线拼凑（例如「静态求和 + 一次离散 SP 采样」）**不算闭环**。

**路线 (a) 静态闭环** —— 全部三项缺一不可：

1. **生产构型**实际调用图的**最大路径** `.su` 求和。要求：
   - 调用图必须来自生产构型的实际产物（`objdump` 调用关系 / map / `.su` 条目），
     不是源码阅读推断；
   - 必须显式列出所选最大路径的每一层函数与其 `.su` 字节数；
   - `-O2` 下被内联的函数没有独立 `.su` 条目，**必须以实际存在的条目为准**并
     声明哪些逻辑层已被折叠进父帧（见 §4.9-D 第 1 项）。
2. **最坏中断/异常嵌套预算**，按 §4.9-D 第 6 项的五个量（基本帧 / FPU 扩展帧 /
   对齐字 / ISR 软件保存帧 / NVIC 最大抢占嵌套层数）逐项给出并求和。
3. **两者相加**与 8192B 比较，给出余量字节数。

**路线 (b) 运行期闭环** —— 必须满足下面任一条并给出该机制的正确性论证：

1. **连续最低 MSP 观测**：能证明观测机制在整个 OTA 窗口内不漏任何瞬态最低点
   （例如每次函数序言/中断入口都更新水位、或硬件持续比较），并给出该「不漏」
   性质的论证，不是「采样够密」这类定性说法；或
2. **边界故障机制**：越界必然产生可判定的硬故障或标志（例如 MPU 保护区、
   PSPLIM/MSPLIM 类栈限制寄存器、guard 页触发 fault），并给出「越界必触发、
   触发必被记录」的论证。
   注：本项目的 32B 魔数 guard **不满足**本条 —— 它只能检出跨越 guard 区的写入，
   `sub sp, #N` 跳过 32B 后 guard 可能完整而越界已发生（§4.2 guard 能力边界条）。
   guard 是补充证据，不能作为路线 (b) 的闭环机制。

**下列任一情形无法闭合时，C3 一律记 `EVIDENCE_GAP`，不得判 PASS**：

- **函数指针 / 间接调用**：OTA 路径上存在无法静态定界的间接调用目标；
- **递归**：调用图存在环且无法给出确定的最大深度；
- **动态栈**：`.su` 出现 `dynamic` qualifier（VLA / `alloca`）；
- **未知中断嵌套**：无法列出最坏抢占组合，或存在优先级配置在运行期被改动；
- 路线 (b) 无法论证「不漏瞬态最低点」或「越界必触发」。

以上任一情形下，把缺口写清（哪条路线、哪一项、为什么闭不上），
**不要**降级成「哨兵扫描 + 定性论证」交差。

## 5. 红线（踩中即整卡作废重来）

- **红线 1（契约只读）**：禁止修改 `PLAN-OTA.md` §9 与
  `docs/ota-binary-contracts.md` §10 里的**任何门槛数字**
  （`40960B`、`8192B`、`163840B`、`16KB` 字典、`35492B` 工作集、`5468B` 护栏）。
  你只能**追加/更新实测值**，且必须标明「P2-6 实测 / 2026-08-15 / 产物哈希」。
  违反后果：改门槛等于让本卡自证通过，验收链失去意义。
  正确通道：`AGENTS.md` OTA 规约 §2 + 看板 §9 登记，本卡不采用该路径。

- **红线 2（字典降档，极易踩）**：即使实测超 `40960B`，**也不准在本会话里改
  `Tools/etu_pack.py`**。理由：① 降档要 MCU 侧与制包端**同时**改，
  `Tools/etu_pack.py:186`（`dict_size: int = 1 << 14`）、`:191`（filter 字典）、
  `:380`（`--lzma-dict` default）三处加 CI 必须同步，漏一处就产生「制包 16KiB /
  解包 8KiB」的静默不兼容包；② 它改变已冻结的压缩参数，属契约变更。
  正确顺序：**落盘实测数字 → P2-6 置「阻塞」→ 看板 §9 登记 → 停止等裁决**。

- **红线 3（计量语义不变量）**：`Libraries/OTA/ota_package.c` / `ota_patch.c` 里，
  除 §3.2 明确授权的两个诊断字段及其赋值外，**不得改动任何既有行为**。
  具体不变量清单（逐条自检并在证据文档回答）：
  1. `arena_alloc` 的**返回值**与**对齐行为**不变；
  2. `arena` 的**清零行为**与**释放顺序**不变；
  3. `arena.peak` 的记账语义不变，`:720` / `:1225` 的
     `arena.peak > arena.capacity` 门禁表达式不变；
  4. **现有 `workspace_peak` 的语义必须保持不变**（仍是 `prefix + arena.peak`，
     仍只在成功路径赋值）—— 新字段是新增口径，不是对它的重定义；
  5. candidate 分区的 **prepare/program IO 时序**不变；
  6. **所有既有结果码不变**（不得新增/改写返回码，不得改变何时返回哪个码）。
  理由：P2-2/P2-3 的验收结论绑定在这套语义上，动它会让两张已完成卡的证据失效，
  且它正是 P2-6 要读的那个数。诊断字段**只被写、只被读出来打印**，
  不得进入任何判断分支。

- **红线 4（不要为省事关掉 gc-sections）**：GCC 侧若为了保住 StackInfo 而全局
  去掉 `--gc-sections`，会显著增大 App 体积（当前 text `597324B`，OTA 分区容量有限）
  并改变所有既有产物哈希，使 P2-1..P2-5 的构建证据全部失配。
  **本卡不需要动 gc-sections**：栈段用 `KEEP()` 精准保留，StackInfo 靠真实调用链
  保活（§4.2 第 6 条）。既不要关闭它，也不要用 `-Wl,--undefined` 之类的全局手段
  绕过它。

其他禁止项：不改 `Libraries/OTA/ota_layout.h` 的地址/长度宏；不改
`Simulator/LVGL.Simulator/lv_conf.h` 的 `LV_MEM_SIZE`（该文件被 F435 共编，
且 `tests/ota/test_ac5_ram_budget.py` 断言必须是 `128U * 1024U`）；
不把项目切到 AC6；不删 `Objects*` / `Listings*` / 生成的固件产物；
**禁止重跑 `keil_uvprojx2cmake.py`**（会冲掉 `CMakeLists.txt` 505 行以后全部
OTA 手写块并删掉 boot 目标）；`#include` 一律用正斜杠
（Linux GCC 不把 `\` 当路径分隔符，本机 Windows 编过不代表 CI 绿，
见 `AGENTS.md`「GCC / Linux CI 源码可移植防坑」）。

## 6. 停止条件（必须遵守，不得自行扩范围）

出现以下任一情况：**落盘现象 → 停止 → 等裁决**，不要自己决定怎么办。

1. 需要改 §1.1「本卡范围」之外的文件（`Tools/etu_pack.py`、`lv_conf.h`、
   `lv_img_decoder.c`、`ota_layout.h` 等）。
   注意 `gcc_runtime_compat.c` 与 `startup_at32f435_437_gcc.S` **已在范围内**，
   改它们不触发本条；但改动必须限定在 §4.2 第 4/5 条授权的内容。
2. 遇到本 prompt 未列出的失效模式（新的栈溢出、overlay 越界、
   OTA 中途 HardFault、LiveMap 重建失败等）。
3. 同一验证项连续 3 次失败。
4. 真机进入无法用 `AGENTS.md` 所述手段恢复的状态。
5. **实测触发以下任一**：
   - 成功 acquire overlay 之后仍容量不足（`*_ERR_WORKSPACE`），**且**已按 §3.3
     第 0 步在宿主用足够大容量成功取到完整 `P_full` 且 `P_full > 40960B`
     —— 这才是降档议题，**overlay owner 冲突不算**（§3.2）。
     **不得**仅凭真机失败时读到的 `arena_peak_observed` 就宣布降档：那个值只是
     需求的下界，不是完整需求（§3.2 字段语义）。
   - OTA 栈峰值 `> 8192B`，**或 guard 区被破坏**（后者即使峰值数字看着达标
     也必须停）。前提是 §4.8 的 measurement-validity 已通过；若未通过，
     这不是停止条件，而是 `HARNESS_FAIL` / `EVIDENCE_GAP`，按 §4.8 表分类后
     修 harness 重测。
   - `sbrk_call_count` 在 OTA 核心 apply 窗口出现非零增量，或
     required 拦截层 `__wrap_lv_tlsf_malloc` / `__wrap_lv_tlsf_realloc`
     的调用增量非零（§4.5 第 2 项）；
   - 你的结论是必须调整契约数字（`8192B` 栈区大小、`40960B` 池上限、
     `16KiB` 字典）。
6. 发现红线之间互相矛盾，或红线与实测冲突。
7. §4.2 七条方案中任一条经实测不可实现（例如 ld 拒绝 `$` 符号且
   `#if __GNUC__` 分支也走不通）。
   **不要私自换方案** —— 方案已裁定，替换方案属范围裁决。

   > **不要照抄早期版本里的「AC5 startup 属不可改生成物」这个例子** ——
   > 该例已于 2026-08-16 按裁定删除，因为它不成立也不相关：AC5 在本卡是
   > auxiliary（§4.1 / §4.6 / §7），只提供静态 RAM 高水位与 `Program Size`
   > 对照（§9 C9），§4.2 的栈区/guard/哨兵方案**只落在 GCC 侧**；
   > 涉及的两个文件
   > `MDK-ARM_F435/cmake-generated/cmake/sources/startup_at32f435_437_gcc.S`
   > 与 `MDK-ARM_F435/cmake-generated/cmake/gcc_runtime_compat.c`
   > **都是 git 跟踪的手写文件，不是生成物**，§1.1 已列入允许修改。
   > 拿「生成物不可改」当停止理由会得到错误的阻塞结论。

落盘格式：证据文档追加「停止记录：现象 / 已排除项 / 当前设备与代码状态 / 建议」。
**禁止**为绕过障碍而扩大改动范围，即使你判断那样做是对的 —— 范围裁决不属于
执行会话。

## 7. 构建验证（全部要留命令与关键输出）

GCC（OTA 官方产物，与 CI 一致；构建目录必须落在**项目内**，禁止写到 `D:\tmp`、
`%TEMP%`、兄弟仓库等项目外路径）：

    cmake -S MDK-ARM_F435/cmake-generated -B MDK-ARM_F435/cmake-generated/build-gcc-release \
      -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_OBJECT_PATH_MAX=1024
    cmake --build MDK-ARM_F435/cmake-generated/build-gcc-release \
      --target X_Track_App_GCC X_Track_Boot --parallel

（`SOURCE_DATE_EPOCH=1786320000`，与 `AGENTS.md` / CI 一致。）

AC5 辅助（**auxiliary，不构成阻断条件**；本卡只用它取静态 RAM 高水位与
`Program Size` 做对照，见 §4.6 第 1 项。**不产出 AC5 栈峰值**）：

    build_f435_and_simulator.bat --no-pause --ac5-only

若改了 `lv_conf.h` 之外的广泛头文件，AC5 侧改用
`MDK-ARM_F435\build_f435.ps1 -Target X-Track-App-AC5 -AutoStale`。
AC5 若因与本卡无关的既有原因编译失败，如实记录并继续 —— 不得因此把本卡置阻塞，
也不得为让 AC5 通过而去改 §1.1 范围外的 AC5 文件。
此时 §9 的 **C9 记 `NOT_OBSERVED`**（该判据 `required = false`，
category 为辅助工具链观测），**不得**记成 PRODUCT_FAIL / HARNESS_FAIL /
EVIDENCE_GAP —— 那会让一个非阻断的对照项反过来卡住本卡。

宿主回归（CI 同款，必须全绿；至少这几组）：

    python tests/ota/test_acceptance_bundle.py
    python tests/ota/test_ac5_ram_budget.py
    python tests/ota/test_f435_build_bootstrap.py
    python tests/ota/test_p2_5_build_provenance.py
    python tests/ota/test_ota_package.py
    python tests/ota/test_ota_patch.py
    python tests/ota/test_ota_update.py
    python tests/ota/test_ota_staging.py

若新增了 P2-6 自检构型，还要跑**与全部既有构型的两两互斥检查**
（照 P2-3 的做法：production + 本构型 configure 应 rc=0，任意两个同开应 rc=1
并命中对应 `FATAL_ERROR`）。另外必须给出**链接期 ASSERT 的负例**：
按 §4.2 第 1 条列出的**九类负例**逐个构造，确认九条 ASSERT A1-A9 真的让链接失败
且**命中的是对应那一条的自定义消息**（不是随便哪一条报错就算过），然后改回。
其中 A6 必须用「命中集合恰好等于 `{A6}`」判定（构造方式见 §4.2 A6 负例条）。
撰写会话已在 `tests/ota/spec-probes/p2-6/guard_layout/` 用最小 ld 跑通
「正例 1 + 负例 9」共 10 个用例，做法可直接照搬；注意其中「段的实际填充长度必须与
契约常量脱钩」那条踩坑，否则 A1/A2 恒成立、两个负例静默通过。

需报告产物时间戳、SHA-256、`arm-none-eabi-size` 输出与 AC5 `Program Size`；
有 warning 要明说「有警告、零错误」，不得把警告伪装成成功细节。
**必须同时报告改动前后的主 RAM 高水位对比**（你的改动本身也会占 RAM），
且按 §4.6 第 2 项说明口径是否发生变更。
**最终一次构建必须是关闭 `P2_6_TEST_ENABLE` 的 fresh 生产构建**，
并附 §4.9 C 项的**三组**证明（三份清单互不混用）：生产产物对 **L2 全部零命中**
（§9 C12）、`P2_6_TEST_ENABLE=1` 构型对 **L1 全部命中**（§9 C15）、
**L3 在两个固件构型上都零命中**（§9 C12 的一部分）。只给零命中一组
不算完成 —— 那无法排除「搜索命令写错所以什么都搜不到」。
宏名一律在 CMake cache / `compile_commands.json` / 编译命令行核对，不在 ELF/map 搜。
另外必须给出 §4.9-D 的插桩→生产迁移性论证 **全部七项**（§9 C16），
其中两构型 map 的四个栈边界符号地址必须实测一致；
最大 SP 上界另按 §4.9-E 走完所选那一条闭环路线（§9 C3）。

## 8. 真机自测（J-Link；正式验收由非实现会话重跑）

严格按 `AGENTS.md`「J-Link 自动烧录与 RTT 闭环调试」+「J-Link 闭环防卡死清单」。
RTT 地址必须从**本次烧录目标本次链接生成的 map** 取 `_SEGGER_RTT`：

- GCC 生产：`MDK-ARM_F435\cmake-generated\build-gcc-release\app-gcc\X-Track-App-GCC.map`
- AC5 辅助：`MDK-ARM_F435\Listings-App-AC5\X-Track-App-AC5.map`

顺序：严格符号行解析取地址 → `mem8 <RTT> 16` 验「SEGGER RTT」签名 →
读 down descriptor（`_SEGGER_RTT+0x60`，pBuffer 在 `+0x64`、WrOff 在 `+0x6C`，
16 字节环形缓冲需按 WrOff 取模续写）→ 启动**单个** `JLinkRTTLogger` 且带明确超时。
启动前先清残留：

    Stop-Process -Name JLinkRTTLogger -Force -ErrorAction SilentlyContinue

烧录参数：`-Device AT32F435RGT7 -If SWD -Speed 1000 -AutoConnect 1 -ExitOnError 1`
（**必须用全名 `AT32F435RGT7`**，缩写会弹 GUI 挂死；速度必须 1000kHz）。

任何来自旧 RTT 地址 / 残留 logger / 错误命令回显 / 与当前源码不匹配的日志一律
标记**污染**并重测，不得参与判定。

对照 P2-6 卡的验收条目自测：

1. **SD 全量升级（`OTA_SD_KIND_FULL`）真机跑通**，采到 `workspace_peak` 与
   `arena_peak_observed` 实测值，与 `40960B` 比较，留 RTT 原始日志。
   若该次运行失败，`arena_peak_observed` 只是下界，必须按 §3.2 语义如实标注。
2. **SD 差分升级（`OTA_SD_KIND_PATCH`）真机跑通**，同上。可与 P2-3 已有的
   `21832B` 对照，但**不能用 P2-3 的数字代替本卡生产路径观测**。
3. **OTA 调用栈峰值实测**（生命周期上界口径，§4.2 第 7 条），
   同时给出**OTA 入口基线水位**、**guard 区状态**与**扫描调用自身的栈开销**，
   与 `8192B` 按 `≤` 比较，说明测量方法与可信边界。峰值与 guard **两条都要过**，
   且必须先完成 §4.8 的 measurement-validity 八项验证 —— 该验证不通过时，
   峰值数字无论多少都不得当成结论（按 §4.8 表分类为 `HARNESS_FAIL` 或
   `EVIDENCE_GAP`）。峰值恰等 `8192B` 且 guard intact 时记通过，
   但必须在报告里显著标注「余量为 0」。
4. **堆无 spill 证明**（§4.5）：OTA 核心 apply 窗口的 `sbrk_call_count` 增量、
   `sbrk_peak`，以及 **LVGL `__wrap_lv_mem_alloc` / `__wrap_lv_mem_realloc` 的
   调用增量（required，须均为 0）**；LVGL 池四字段的入口/出口值只作佐证，
   单靠它不能证明窗口内没有分配（§4.5 第 2 项已给 `lv_mem.c` 逐行依据）。
5. **异常退出后 LiveMap 重建**（P0-6 §5.5 点名的第三项）：升级中途失败/取消后
   overlay 所有权释放、LiveMap 重新初始化、地图正常显示。
   所有权 API：`USER/HAL/HAL_OTA_Package.cpp:252` `OTA_OverlayAcquireLiveMap()`、
   `:257` `OTA_OverlayReleaseLiveMap()`、`:262` `OTA_OverlayIsOtaOwned()`
   （声明在 `USER/HAL/HAL_OTA_Package.h:10-12`）。
6. **改动后主 RAM 高水位重测**，回填 §2.3 表格的「P2-6 后」一列。
7. **真机只跑正式 `40960B` 容量**。容量边界的正/负例只在宿主做（§3.3），
   **禁止**在设备上做破坏性容量扫描。
8. 需用户物理配合的项：如实标注「待用户配合」，**不得以其他方式替代或声称通过**
   （例如需要拔卡拷贝 `.etu`、或需要电池供电脱机验证时）。

设备风险提示（`AGENTS.md` 已记录，不要当成代码 bug 去改代码）：

- 烧录会 halt MCU，可能把传输中的 SD 卡打成软复位救不回的挂死态。现象：
  `SD_IsReady=0`、LiveMap stat 的 `lineMiss/sdMs` 全 0、瓦片不显示。
  先从 map 查 `SD_IsReady` 地址用 `mem` 读值确认，恢复方式是**拔插 SD 卡或整机
  断电**，不是改代码。
- GPS 模拟器会随机游走出地图覆盖区且经 GPX 持久化（复位无效）。测 LiveMap 重建前
  必须执行 复位 → RTT 命令 `gpsreset` → `livemap` 三连，否则空白地图会被误判为
  重建失败。

## 9. 交付清单

- 证据文档 `docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md`：
  research 结论、逐条改动理由、§4.6 三个评估点与 §5 红线 3 六条不变量的
  **结论与数字**、全部构建/回归/真机命令与关键输出、产物路径 + 时间戳 + SHA-256、
  以及**你没做到的项**如实列出。
- **观测值按验收矩阵格式给**，便于验收会话机械核对而不必重新推理：
  每个验收项一行，写 `判据ID | 实测值(带单位) | 原始证据文件路径`。
  格式对齐 `docs/acceptance-contracts/template.evidence-matrix.json` 的
  `observed` / `evidence` 字段（布尔值、带单位数值或完整状态链）。
  本卡至少需要这几个判据行：
  ```
  P2-6-C1  | full 路径 workspace_peak=<N>B / 40960B         | <RTT 日志路径>
  P2-6-C2  | patch 路径 workspace_peak=<N>B / 40960B        | <RTT 日志路径>
  P2-6-C3  | OTA 栈峰值=<N>B / 8192B（判定用 <=；入口基线=<N>B） | <RTT 日志路径>
           | 注：必须附**独立的最大 SP 上界证据**，且只能走 §4.9-E 冻结的
           | **两条闭环路线之一**（(a) 静态闭环 或 (b) 运行期闭环），
           | 二者内部各项**不可互相替代**。理由：哨兵扫描测到的是「最深被
           | 改写字节」，`sub sp, #N` 一次跳过 32B guard 后可能只在新 SP 附近
           | 写入，8192B 扫描区底部未被连续改写；链接期 ASSERT 只证明静态段
           | 布局，不观察运行期 SP。**所选路线未整体闭合时 C3 记
           | `EVIDENCE_GAP`**，不得凭哨兵单一来源判 PASS，也不得用路线内
           | 单独一项冒充闭环
           | 注：判定是 <=，**不是** <。峰值恰等 8192B 且 guard intact 是
           | 有效的**零余量**观测，必须记 PASS 并在报告显著标注「余量为 0」，
           | 不得改判 HARNESS_FAIL。结果分类一律查 §4.8 六行表，
           | 且本判据的 PASS/FAIL 以 C13 通过为前提
  P2-6-C4  | guard 区 intact=<true|false>（区间 <起址>..<止址>, 32B） | <RTT 日志路径>
  P2-6-C5  | OTA 窗口 sbrk_call_count 增量=<N>（须为 0）     | <RTT 日志路径>
  P2-6-C6  | LVGL 池调用增量（`lv_tlsf_*` 层）:                | <RTT 日志路径>
           | malloc=<N> / realloc=<N>（**门禁：两项须均为 0**）/ free=<N>
           | 注：`free` 是**交叉核对项不是门禁项**（不占新内存）；但 free 非 0
           | 必须定位到具体释放点并说明不影响峰值预算，给不出定位记
           | `EVIDENCE_GAP`（口径与 §4.5 第 2 项完全一致，不得各写一套）
           | 注：required 拦截层是 `lv_tlsf_malloc/realloc/free`，**不是**
           | `lv_mem_*`（后者有同 TU 盲区，§4.5 实测）；须附 `__wrap_*` 已参与
           | 链接的证据（nm + map + 反汇编分支目标）+ 一个能读到非零增量的负例；
           | 还须附「OTA 窗口内 LVGL 自身未被驱动」的证明（§4.5）；
           | 覆盖边界写「经 `lv_tlsf_*` 的全部调用者」，
           | 不得写成「LVGL 池无任何活动」
  P2-6-C7  | 异常退出后 LiveMap 重建=<true|false>           | <截图/RTT 路径>
  P2-6-C8  | GCC 主 RAM 高水位=<N>B / 360448B, 余<N>B       | <map 摘录路径>
  P2-6-C9  | AC5 主 RAM 高水位=<N>B / 360448B, 余<N>B       | <map 摘录路径>
           | **required = false**；category = 辅助工具链观测
           | （auxiliary toolchain observation）。AC5 不是 OTA 产物工具链
           | （`AGENTS.md` 首段），本项只作对照。取不到时记 `NOT_OBSERVED`，
           | **不得**记 PRODUCT_FAIL / HARNESS_FAIL / EVIDENCE_GAP，
           | 也不得因此阻断本卡
  P2-6-C10 | 宿主边界 FULL: prefix=<N>B, P_full=<N>B;         | <宿主日志路径>
           | cap=P_full-prefix 成功 / cap=P_full-prefix-1 失败
  P2-6-C11 | 宿主边界 PATCH: prefix=<N>B, P_full=<N>B;        | <宿主日志路径>
           | cap=P_full-prefix 成功 / cap=P_full-prefix-1 失败
  P2-6-C12 | 生产固件测量标记零命中: L2 零命中=<true|false>,   | <搜索命令输出路径>
           | L3 两固件构型均零命中=<true|false>（§4.9-C 三份清单）
           | 注：宏名在 CMakeCache/compile_commands/编译命令行核对，
           | 符号与字符串才在 .elf/.map 核对。两项缺一即 `EVIDENCE_GAP`
  P2-6-C13 | measurement-validity: §4.8 八项全通过=<true|false>；| <验证输出路径>
           | 扫描调用自身栈开销=<N>B；三类负例均被拒=<true|false>
  P2-6-C14 | LVGL 池四字段进出差值=<free/biggest/frag/max>   | <RTT 日志路径>
           | 注：佐证项，只证明净状态未变，不排除窗口内瞬态分配
  P2-6-C15 | 测量标记正向命中: TEST_ENABLE=1 构型对 L1 全命中=<true|false> | <搜索命令输出路径>
           | 注：L1 **只含 B 组**测试插桩项，B' 组（L3）不进本清单；
           | 宏名 `P2_6_TEST_ENABLE` 的正向证明是 `compile_commands.json`
           | 覆盖**每个**插桩翻译单元，不是 ELF 里搜到宏名
  P2-6-C16 | 插桩->生产迁移性论证 §4.9-D 七项全通过=<true|false>；| <证据文档章节>
           | 两构型 map 四符号地址一致=<true|false>
           | 注：七项 = ① 两构型各自 `.su` 原始数据；② 逐函数比较并列出
           | 插桩更小/条目出现消失的函数；③ 内联与尾调用差异（反汇编函数体
           | 集合）；④ 采集点在 apply 窗口之外；⑤ wrapper 未改 OTA 路径；
           | ⑥ 中断栈预算（五个量，见 §4.9-D 第 6 项）；⑦ 共享 A 类布局。
           | **逐项给结论，缺一项即本判据 `EVIDENCE_GAP`**；不得写成
           | 「三点论证」或只报总量比较
  ```
  C10/C11 的「失败」一行必须同时含「candidate 未 prepare、未 program」的证明，
  且必须先按 §3.3 第 0 步取到完整 `P_full`；不得用失败路径读到的
  `arena_peak_observed`（那只是下界）当成 `P_full`。
  两点的容量值必须按 §3.3 换算成 `P_full - prefix` 坐标（`P_full` 含 `prefix`，
  `arena.capacity` 不含），且必须用 §3.3 冻结的 `arena.capacity` 覆盖方式实现
  —— **缩短 `workspace_len` 会撞 `:665` / `:1161` 前置拒绝，是假负例**。
  失败一行还必须报 `arena_peak_observed != 0` 以证明控制流确实进了 arena。
  C6 是 required 主判据（`--wrap` 调用级计数）；若 `--wrap` 被证明不可行而降级为
  C14 净状态判据，该项按 `EVIDENCE_GAP` 报，**不得**写成「已证明窗口无 LVGL 分配」。
  C13 不通过时，C3 与 C4 的 PASS/FAIL 一律作废，按 §4.8 表分类为
  `HARNESS_FAIL` 或 `EVIDENCE_GAP`。
  C12 与 C15 必须成对出现（一反一正），且必须用**不同的清单**：C12 判 L2（B∪B'）
  与 L3（B'，两固件构型），C15 判 L1（仅 B 组）。只有零命中没有正向命中，无法排除
  「搜索命令本身写错所以什么都搜不到」；反之用同一份清单同时要求「全部命中」与
  「两侧零命中」是自相矛盾的判据，任何合规实现都过不了 —— 见 §4.9 C 项的集合关系
  `L1 ∩ L3 = ∅`、`L2 = L1 ∪ L3`。
- **回填两处文档**（只填实测值，不动门槛）：
  `PLAN-OTA.md` §9 的 RAM 基线与升级态峰值预算条目、
  `docs/ota-binary-contracts.md` §10 对应处。回填必须与 P0-6 同口径（§4.6 第 2 项），
  并标注「P2-6 实测 / 日期 / 产物哈希」以区别于 P0-6 的 2026-07-26 legacy 数字。
- 回写 P2-6 卡状态（`PLAN-OTA-EXEC.md:545`）+ 看板 §10 追加一行会话日志。
  若触发降档条件，改为置「阻塞」+ §9 变更登记表登记。
- **不 commit**。改完停下，等非实现会话验收、主会话收口。
