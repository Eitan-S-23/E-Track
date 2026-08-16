# P2-6 栈测量方案设计可行性验证（Spec 侧，2026-08-15）

> 执行者：P2-6 提示词撰写会话（非实现会话，非验收会话）。
> 依据：审查裁定 Q2「验证深度 = B2(i)，只做设计可行性验证，不由 Spec 方做真机 OTA 峰值」。
> 范围：GCC map 布局、无重叠 ASSERT、符号导出、`_sbrk` 边界、startup 哨兵循环反汇编、
> StackInfo 宿主模式测试。**不含真机 OTA 栈峰值实测**（属实现会话 Luna 的 P2-6-C3）。
> 探针目录：`tests/ota/spec-probes/p2-6/`（受 Validation profile 管理，已入库；
> 生成物落 `.cache/p2-6-spec-probe-run/`，不入库）。第一轮内置 guard 版探针留在
> `.cache/p2-6-spec-probe/`，结论已被取代，故意不迁移，理由见该目录 README。
> 工具链：`arm-gnu-toolchain-13.3.rel1-ming`，`arm-none-eabi-gcc 13.3.1 20240614`。

本文件是 research 落盘（`AGENTS.md` OTA 规约第 4 条），不是验收证据。
所有结论均为**宿主/链接期**验证，目的是在派单前排除方案不可实现的风险，
并把「必须实测确认」的未知项换成确定答案，减少实现会话返工。

---

## 1. 结论摘要

| # | 验证项 | 结论 | 对提示词的影响 |
|---|---|---|---|
| 1 | ld 脚本定义 `STACK$$Base` 是否需引号 | **不需要**，直接赋值即可 | 取消「必须实测」，给出确定答案 |
| 2 | gcc 是否接受含 `$` 的标识符 | **默认接受**（`-fdollars-in-identifiers` 默认开） | 同上；退路默认不启用 |
| 3 | C 引用 + ld 定义端到端链接 | **通过**，反汇编内联出正确地址 | 同上 |
| 4 | 两层间接宏能否省 | **不能**，省掉得到错误符号名且编译不报错 | **新增红线级提醒** |
| 5 | 长度/重叠 ASSERT 鉴别力 | 有效，但 `end` 锚点写法**恒不触发** | **新增锚点纠正条款** |
| 6 | 段内绝对地址算术 | 会爆 `overflowed by 536871424 bytes` | 新增写法提醒 |
| 7 | `_sbrk` 新旧上限差值 | 旧上限高 **4096B**，堆可侵入栈区 | 量化必要性证明 |
| 8 | 哨兵填充循环是否消耗栈 | 不消耗（只用 r0/r1/r2，无 push/bl） | 反汇编证据 |
| 9 | 栈区在 SRAM 扩展前可访问性 | 可访问（栈区在 352K 内，基础配置 384K） | 把「请自己复核」换成确定结论 |
| 10 | **guard 置于栈区内时与 StackInfo 扫描算法冲突** | **冲突，会静默假通过** | **改为「外置 guard 区」布局** |

第 4、5、10 项是本轮发现的**新增设计缺陷**，裁定原文与整改前的提示词均未覆盖。
其中第 10 项后果最严重：会让 P2-6-C3 判据**永远 PASS 且完全失去鉴别力**。

> **2026-08-16 修订（独立复核裁定）**：第 10 项的**修法**已被推翻并替换。
> 本文件原提出的两条修正（① 扫描起点跳过 guard 字；② 峰值恰等 8192B 一律先判
> `HARNESS_FAIL`）均不采用 —— ① 引入易写错的偏移补偿，② 混淆了「扫描失效」与
> 「真实满栈」两种成因。**现行方案是把 guard 移到 8192B 栈区之外**，详见
> `docs/ota-prompts/prompt-P2-6-implementation.md` §4.2 第 1/4/5 条与 §4.8。
> 本节下方 §6 已按该裁定改写；缺陷本身的成立性与宿主复现数据不变。

---

## 2. `$$` 符号可行性（裁定标为「必须实测」的最高风险项）

### 2.1 gcc 侧

`extern const int STACK$$Base;` + 取址相减，`arm-none-eabi-gcc -c -O2` **rc=0**。
`nm` 输出：

```text
00000000 T probe_stack_total
         U STACK$$Base
         U STACK$$Limit
```

显式加 `-fno-dollars-in-identifiers` 才失败，确认这就是控制该行为的选项：

```text
error: pasting "CSTACK_BLOCK_NAME" and "$" does not give a valid preprocessing token
error: stray '$' in program
```

本项目未使用该选项，故默认可用。

### 2.2 两层间接宏不可省（新发现）

`StackInfo.c:25-34` 用了两层：`CSTACK_BLOCK_START(_name_)` → `SECTION_START(_name_)`。
这**不是冗余**。`##` 会抑制形参的宏展开：

| 写法 | 实际生成的符号（`nm` 实测） |
|---|---|
| 一层：`SECTION_START(CSTACK_BLOCK_NAME)` | `U CSTACK_BLOCK_NAME$$Base` ← **错** |
| 两层：`CSTACK_BLOCK_START(CSTACK_BLOCK_NAME)` | `U STACK$$Base` ← 正确 |

一层写法**编译 rc=0 不报错**，只在链接期表现为未定义符号；若同时在 ld 里
定义了同名错符号，会静默得到错误的栈边界。AC5 map `:30326-30327` 里是
`STACK$$Base`，也证明两层间接确实生效。

### 2.3 ld 侧与端到端

ld 脚本内直接写（无引号）：

```ld
STACK$$Base  = __StackLimit;
STACK$$Limit = __StackTop;
```

链接 rc=0，`nm probe2.elf`：

```text
20056000 B __StackLimit
20058000 B __StackTop
20056000 A STACK$$Base
20058000 A STACK$$Limit
```

端到端反汇编（`ENTRY(_start)` 保住引用，避免 `--gc-sections` 把引用一起丢掉
而产生假通过）：

```text
20000000 <_start>:
   ldr r3, [pc, #8]    @ -> .word 0x20058000
   ldr r1, [pc, #12]   @ -> .word 0x20056000
   subs r3, r3, r1     @ = 8192
```

**注**：首次尝试时 `--gc-sections` 丢弃了 `_start`，段表里没有 `.text`，
符号虽然「解析成功」但引用已不存在——这种情况不能算验证通过。加 `ENTRY` 后重测。

---

## 3. 段布局与 ASSERT

### 3.1 正例布局

```text
Idx Name          Size      VMA       LMA
  0 .text         00000018  20000000  20000000
  1 .bss          00000004  20000018  20000018
  2 ._user_heap   00000204  2000001c  2000001c
  3 .ota_stack    00002000  20056000  20056000
```

`.ota_stack` size = `0x2000` = 8192B 精确，VMA 落在 `__StackLimit`，NOLOAD 生效。

### 3.2 段内绝对地址算术会爆

段体内 `.` 是相对段起始的偏移。写
`. = __StackLimit + OTA_STACK_RESERVE - __stack_area_start;` 得到：

```text
section `.ota_stack' will not fit in region `RAM'
region `RAM' overflowed by 536871424 bytes
```

`536871424` ≈ `0x20000200`，正是把绝对地址当成了长度。
正确写法用绝对地址定位段，段内只用相对长度：

```ld
.ota_stack __StackLimit (NOLOAD) : { KEEP(*(.ota_stack)) . = OTA_STACK_RESERVE; } > RAM
```

### 3.3 ASSERT 鉴别力（含锚点纠正）

| 负例 | 结果 |
|---|---|
| 栈区长度改 4096 | `ld: OTA stack area must be exactly 8192 bytes`，rc=1 ✓ |
| 堆预留改 `0x58000` | 见下 |

堆膨胀负例暴露锚点错误：`ASSERT(end <= __StackLimit, ...)` **没有触发**。
原因是 `ld.S:296-299` 中 `end` 由 `PROVIDE(end = .)` 定义在
`._user_heap_stack` **段起始处**，是堆区起点不是终点，堆膨胀不会让它变大。
当时只靠 ld 内置检查兜住，错误信息还指不出是栈冲突：

```text
ld: section .ota_stack VMA [20056000,20057fff] overlaps section ._user_heap VMA [2000001c,2005801f]
```

改用段结束地址作锚点后，正例 rc=0 不误报，负例明确报出自定义消息：

```ld
ASSERT(ADDR(._user_heap) + SIZEOF(._user_heap) <= __StackLimit, "Data/heap region overlaps the OTA stack area")
```

```text
ld: Data/heap region overlaps the OTA stack area
```

---

## 4. `_sbrk` 上限：量化必要性

`gcc_runtime_compat.c:32` 现为 `limit = &_estack - &_Min_Stack_Size`。
反汇编确认两种口径各自算出的立即数：

| 口径 | 表达式 | 实测值 |
|---|---|---|
| 旧 | `&_estack - &_Min_Stack_Size` | `0x20057000` |
| 新（本轮实测口径） | `&__StackLimit` | `0x20056000` |

差值 **4096B**。即不改上限时，堆可以合法长进 8192B 栈区的**下半部**，
契约要求的 8192B 里只有 4096B 被硬保证。这是裁定第 3 条的精确必要性证明。

> **2026-08-16 修订**：现行方案的 `_sbrk` 上限取 **`__StackGuardStart`**
> （`0x20056000 - 0x20 = 0x20055fe0`），不是 `__StackLimit` —— 否则堆能合法长进
> guard 区并改掉魔数，guard 判据失效。相对旧上限的差值变为
> `0x20057000 - 0x20055fe0 = 0x1020 = 4128B`（4096B 栈 + 32B guard）。
> 本节的必要性论证不受影响，只是边界再下移一个 guard 长度。

---

## 5. startup 哨兵填充

### 5.1 循环反汇编（确认不消耗栈）

```text
   ldr r0, =__StackLimit      @ 0x20056000
   ldr r1, =__StackTop        @ 0x20058000
   mov.w r2, #0xa5a5a5a5
.Lfill: cmp r0, r1
        bcs .Ldone
        str.w r2, [r0], #4
        b .Lfill
.Ldone: ldr r0, =__StackLimit
        ldr r2, =0x5aa55aa5   @ guard
        str r2, [r0]
        bl probe_c_entry      @ 第一个 C 调用，在此之后
```

只用 r0/r1/r2，无 `push`/`bl`，填充期间不产生栈帧，故填满整个栈区安全。
`bl` 之后才开始压栈（会覆盖顶部哨兵），这正是「已使用」的正常语义。

> **2026-08-16 修订**：探针里 guard 写在 `__StackLimit`（栈区内最低字），
> 这正是 §6 缺陷的成因。现行方案 guard 目标地址改为 `__StackGuardStart`
> （栈区之外的独立 guard 区）。本节结论（填充循环不消耗栈、必须在首个 C 调用前）
> 与地址选择无关，仍然成立。

### 5.2 可访问性与 `extend_sram_512k`

```text
主 RAM   : 0x20000000..0x20058000  (360448B = 352K)
overlay  : 0x20058000..0x20080000  (163840B = 160K)  合计 512K
384K 边界: 0x20060000
8192B 栈区: 0x20056000..0x20058000   栈区顶 <= 384K 边界 → True
```

栈区完全落在 352K 主 RAM 内，而扩展前基础配置已有 384K，
故 `extend_sram_512k` 之前即可写；只有 overlay 区依赖 512K 扩展。

`extend_sram_512k`（`MDK-ARM_F435/Platform/Core/at32f435_437_clock.c:122-139`）
两点补充事实：
- EOPB0 尚非 512K 时会擦写用户系统数据并 `nvic_system_reset()`，复位后重走
  `Reset_Handler` → 哨兵被**再填一次**，不影响正确性。
- 其注释明确「此时 RW/ZI 尚未初始化，只允许使用局部变量」→ 它**会用栈**，
  这就是哨兵必须填在它之前的原因。

---

## 6. StackInfo 宿主测试：guard 与扫描算法冲突（最严重发现）

`StackInfo.c:52-61` 的扫描是「从 `i=0`（栈底最低地址）向上找第一个非 BLANK 字，
取 `usageSize = size - i`」。裁定第 5 条要求在 `__StackLimit` 写 guard，
而 `__StackLimit` 正是 `i=0`，且 guard 按定义非 BLANK。

宿主复现（`tests/ota/spec-probes/p2-6/host_scan/`，`gcc -O2 -Wall -Wextra`；
判定已 fail-closed 化，跑 `python tests/ota/spec-probes/p2-6/host_scan/run.py`）：

| 场景 | 构型 | 实际用量 | 扫描结果 | 判定 |
|---|---|---|---|---|
| 1 | 非零哨兵，无 guard | 1024B | `1024B` | ✓ 基准正确 |
| 2 | 非零哨兵 + 栈底 guard | 1024B | **`8192B`** | ✗ **失效** |
| 3 | 同场景 2，扫描跳过 guard 字 | 1024B | `1024B` | ✓ 有效但**已弃用** |
| 4 | 填非零哨兵但 `BLANK` 仍为 0 | 1024B | **`8192B`** | ✗ 失效 |
| 5 | guard 被踩破（模拟溢出） | 满栈 | guard `0xDEADBEEF`，intact=false | ✓ 可检出 |

**危险性**：场景 2/4 的失效值恒为栈区总长 `8192B`，而门禁是「峰值 ≤ 8192B」，
`8192 ≤ 8192` 成立 → 判据**永远 PASS**。这不是会报错的失败，是**静默假通过**，
P2-6-C3 会完全失去鉴别力。

### 6.1 修法（2026-08-16 独立复核裁定，替换本文件原结论）

本文件初版给出的两条修正**已被推翻，不再采用**：

| 原结论（作废） | 作废理由 |
|---|---|
| ① 扫描起点跳过 guard 区（`i` 从 guard 字数起算） | 引入偏移补偿，偏移写错同样静默出错；场景 3 虽实测有效，但把正确性押在一个易错常量上 |
| ② 峰值恰等 8192B 一律先判 `HARNESS_FAIL` | 混淆「扫描失效」与「真实满栈」两种成因；且会把合法的零余量观测误判为 harness 故障 |

**现行方案：guard 移出栈区。** 布局为
`[数据/堆区] → __StackGuardStart → [32B guard 区] → __StackGuardEnd == __StackLimit
→ [8192B 可用栈区] → __StackTop`。要点：

- `STACK$$Base = __StackLimit`、`STACK$$Limit = __StackTop`，扫描范围恰是完整
  8192B 栈区，`i` 从 0 起算、**不跳过任何字** → 场景 2 的冲突不复存在。
- `_sbrk` 上限、堆重叠 ASSERT、静态 RAM 余量口径全部改用 `__StackGuardStart`
  （取 `__StackLimit` 会让堆合法长进 guard 区并改掉魔数）。
- 该布局下 `峰值 == 8192B` 且 guard intact 是**有效的零余量观测**，记 PASS 并
  标注「余量为 0」，**不是** `HARNESS_FAIL`。
- 取代原 ② 的是**独立的 measurement-validity 判据**（八项验证 + 六行结果分类表），
  判的是「证据能否区分扫描失效与真实满栈」，而不是数值是否等于某个特征值。
- guard 的能力边界也一并写明：它只能检出**跨越 guard 区的写入**，
  `sub sp, #N` 一次跳过 32 字节时 guard 可能完整而越界已发生；
  故越界主判据是「峰值 ≤ 8192B」与链接期 ASSERT，guard 是补充证据。

落地位置：`docs/ota-prompts/prompt-P2-6-implementation.md` §4.2 第 1/4/5 条、
§4.7、§4.8（measurement-validity）、§4.9（构型边界）、§9（C3/C4/C13）。

场景 4 对应的「同步 `STACK_INFO_BLANK`」整改前提示词已覆盖；
场景 2 的冲突为本轮新发现，整改前未覆盖。

---

## 7. 本轮未验证的项（明确边界，不得当成已验证）

- **真机 OTA 栈峰值**：按裁定不由 Spec 方做，属 Luna 的 P2-6-C3。
- **真实 `ld.S` 改造后的完整链接**：本轮用的是最小化复刻脚本，未改动
  `cmake/linker/x-track-app-gcc.ld.S` 本体，也未跑 `X_Track_App_GCC` 全量构建。
  真实脚本还含 overlay、四条 overlay ASSERT、`P2_x_TEST_ENABLE` 条件区，
  Luna 必须在真实脚本上复验。
  **外置 guard 区段与九条 ASSERT 已于 2026-08-16 完成最小链接正负例**（见 §8.1，
  第三轮裁定整改 ①②），原「五条 ASSERT 未链接验证」的表述已作废；但那仍是复刻
  脚本，真实脚本上的链接结果不得据此推定。
- **AC5 侧哨兵**：**已不在本卡范围**。AC5 经复核裁定为 auxiliary，只提供静态
  RAM 高水位与 `Program Size` 对照，不产出 AC5 栈峰值；
  `MDK-ARM_F435/RTE/Device/-AT32F435RGT7/startup_at32f435_437.s` 明确不改。
  故本轮未验证、也无需验证其等效改动。
- **`sbrk_call_count` / `sbrk_peak` 的实际接线**：只做了上限差值的数值验证，
  未实现计数器。
- **LVGL `--wrap` 的可行性**：已于 2026-08-16 完成最小验证（见 §8.2，第三轮
  裁定整改 ⑤），原「完全未验证」的表述已作废。实测结论把 required 拦截层从
  `lv_mem_*` 改为 `lv_tlsf_*`：`-O2` 下 `lv_mem_buf_get` 对同 TU 的
  `lv_mem_alloc` 调用被尾调用折叠，**链接前就不存在可拦截的调用点**，
  比「拦到但未重定向」更彻底。**仍未验证**的是真实构建上的等价性：真实
  `lv_mem.c` 的内部入口集合、`--gc-sections` 在真实链接脚本下的行为，
  以及 OTA 窗口内 LVGL task handler / timer / 异步回调是否真的未被驱动。
  Luna 必须在真实构建上复验并写明覆盖边界；不可行则按提示词 §4.5 第 2 项走
  `EVIDENCE_GAP`，不得宣告「已证明 OTA 窗口无 LVGL 分配」。
- **StackInfo 扫描调用自身的栈开销**：未量化。提示词 §4.2 第 7 条与 §4.8 第 7 项
  要求 Luna 实测并单列，本轮没有给出任何数字。
- **最大 SP 上界的两条闭环路线均未闭合**：Spec 侧只验证了 `-fstack-usage`
  **数据源可用性**（`.su` 能产出、qualifier 全 `static`，见 §8.3）。逐函数 `.su`
  本身**不构成任何上界**：
  - **静态闭环**（提示词 §4.9-E 路线 a）仍缺两块 —— 生产构型**实际调用图最大路径**
    的 `.su` 求和，以及**最坏中断/异常嵌套预算**（含 FP 上下文是否激活、FPCCR
    懒压栈、8 字节对齐字、ISR 软件保存帧、NVIC 最大抢占嵌套）。
  - **运行期闭环**（路线 b）**尚未实现**：需要能证明连续覆盖所有瞬态最低 SP 的
    观测机制或边界故障机制，离散采样不算。
  Luna 必须**完整选择其中一条**并把该路线的每一项做完；跨路线拼凑（例如
  「静态求和 + 一次离散 SP 采样」）不算闭环，否则按提示词 §9 C3 记 `EVIDENCE_GAP`。
  （2026-08-16 定向复核已作废本文早前的「四选一」表述：那四项不是并列替代关系。）
- 探针已迁入 `tests/ota/spec-probes/p2-6/`（受 Validation profile 管理）；
  本文件的命令与输出摘录为过程留痕，正式证据由 `run_all.py` 日志按 SHA-256 绑定。

---

## 8. 第三轮独立复核整改的实测证据（2026-08-16）

第三轮裁定给出 10 项最低整改清单。本节记录其中需要实证的六项的观测结果。
凡与 §7 早前「未验证」标注冲突处，§7 已就地改写，以本节为准。

### 8.1 外置 guard 最小链接正负例（整改 ①②）

探针 `tests/ota/spec-probes/p2-6/guard_layout/`：`layout.ld.tmpl` 定义 `.ota_stack`
与 `.ota_stack_guard` 两个输出段，四个符号全部由段的 `ADDR()`/`SIZEOF()` 派生，
九条 ASSERT A1-A9 各带自定义消息。

正例链接通过，符号落位与 §3 一致：

```text
[PASS] pos  rc=0  __StackLimit=0x20056000  __StackTop=0x20058000
              __StackGuardStart=0x20055fe0  __StackGuardEnd=0x20056000
              STACK$$Base=0x20056000  STACK$$Limit=0x20058000
```

七类负例全部让链接失败，且命中的是对应那一条的自定义消息：

| 负例 | 构造 | 命中 |
| --- | --- | --- |
| neg1_stack_len | 栈段长度错 | A1, A3, A9 |
| neg2_guard_len | guard 段长度错 | A2, A4, A8 |
| neg3_gap | guard 与栈之间留空洞 | A4, A8 |
| neg4_guard_addr | guard 段地址错 | A4, A8 |
| neg5_stack_addr | 栈段地址错 | A3, A4, A8, A9 |
| neg6_heap_into_guard | 数据/堆段侵入 guard | A5 |
| neg7_symbol_decoupled | 符号与段脱钩（改独立算术） | A7 |

**2026-08-16 补测（派单前置整改阻断 3 与两层宏判据）**：负例扩到九类，
`cases.json` 的判定分支由两种扩为三种（`assert_contains` / `assert_exact` /
`undefined_symbols`）。

| 负例 | 构造 | 判定方式 | 命中 |
| --- | --- | --- | --- |
| neg8_stacklimit_decoupled | `__StackLimit` 与 `.ota_stack` 脱钩，**同时**把 `__StackGuardEnd` 改成同一脱钩值 `_estack - OTA_STACK_RESERVE - 64`（`0x20055FC0`）使 A8 仍成立 | `assert_exact` | **恰好 `['A6']`** |
| neg9_one_layer_macro | 开 `-DP2_6_ONE_LAYER_MACRO`，两层间接宏简化成一层 | `undefined_symbols` + 不得命中任何 A1-A9 | 未定义符号 `CSTACK_BLOCK_NAME$$Base` / `$$Limit` |

neg8 是**原「A6 无独立负例」缺口的闭合**。关键在于不能只改 `__StackLimit`：
直接改会**连带**打死 A8（`__StackGuardEnd == __StackLimit`）以及经由
`__StackTop` 的 A3/A9，命中集合变成一堆条目，无法证明 A6 自身有鉴别力。
把 `__StackGuardEnd` 一并改成同一脱钩值后 A8 恢复成立，命中集合才收缩到 `{A6}`。
因此判据必须是**「命中集合恰好等于 `{A6}`」**（`assert_exact`），
写成「集合包含 A6」时 A6 靠别的条目连带失败也能算过，等于没有鉴别力。

neg9 把 §2.2 的两层宏结论从「编译期观测」升级为**链接期 fail-closed 判据**：
一层写法编译 rc=0 不报错，只在链接期表现为未定义符号；判据同时要求
**不得命中任何 ASSERT**，防止用别的失败冒充。

上述两条已写进提示词 §4.2 第 1 条（含「A6 负例的构造方式必须照抄」条款）、
§4.9-C 与 §7 的复验清单（正例 1 + 负例 9 共 10 个用例，
真实 `ld.S` 复验必须覆盖 A1/A2/A4/A5/**A6**）。

另外，段的实际填充长度必须与契约常量脱钩才能构造 neg1/neg2：若用同一个常量同时
决定填充和 ASSERT 阈值，改常量会让两边同步移动，负例恒不触发。

### 8.2 ARM GCC `--wrap` 最小验证（整改 ⑤）

探针 `tests/ota/spec-probes/p2-6/wrap_probe/`：宿主组验行为，ARM 组验链接。
裁定要求的 8 项全部通过：

```text
插桩构型 ELF 符号命中: 14/14
__real_* 未解析残留: 无
map 中 wrapper 命中: 6/6
生产构型残留测量符号: 无（14 个全部消失）
生产构型 map 残留 __wrap_/__real_: 无
命令行 LTO 选项: 无（未启用 LTO）
调用序列指纹(各构型应一致): {'mem': (163, 96), 'tlsf': (163, 96),
                             'both': (163, 96), 'prod': (163, 96)}
tlsf 转发保真: last_tlsf_size=48 ret_nonnull=1
```

**决定 required 拦截层的核心观测**：模拟 LVGL 内部入口 `lv_mem_buf_get`
（与 `lv_mem_alloc` 同一 TU）触发真实池分配 1 次时——

```text
[核心结论] lv_mem 层拦截增量=0（盲区），lv_tlsf 层拦截增量=1（覆盖）
lv_mem_buf_get  分支目标 -> ['__wrap_lv_tlsf_malloc']
lv_mem_alloc    分支目标 -> ['__wrap_lv_tlsf_malloc']
上层调用点是否被内联/尾调用消除: True（--wrap=lv_mem_alloc 无可拦截的调用点）
```

盲区成因比「符号解析不跨 TU」更彻底：`-O2` 把 `lv_mem_buf_get` 里对
`lv_mem_alloc` 的调用尾调用折叠掉了，链接期连调用点都不存在，nm/map 里也看不到
痕迹。故 required 改为 `--wrap=lv_tlsf_malloc/realloc/free`。

**fail-closed 副产物**：定义了 `__wrap_X` 却不在命令行传 `--wrap=X` 时，
`__real_X` 是未定义引用，链接直接失败。因此 wrapper 定义集合与 `--wrap=` 集合
必须一一对应——这条已写进提示词 §4.5 与 §4.9 C 组清单。

### 8.3 `-fstack-usage` 与插桩非单调性反例（整改 ③ 部分 + ④）

探针 `tests/ota/spec-probes/p2-6/stack_usage/`。`arm-none-eabi-gcc 13.3.1` 产出
`.su`，qualifier 全为 `static`（无 dynamic/VLA），故静态求和路径可用。

**但 `-O2` 下被内联的函数没有独立 `.su` 条目**，逐函数查表求和会漏算——生产构型
链上只剩 `ota_apply` 一条 992B 记录，其余三层全部内联。

裁定阻断 2 的决定性反例（`scan4.py`，采集点加 `__attribute__((noinline))`）：

```text
插桩构型                        ota_apply      链上求和  逐函数关系
仅计数                               992       992  无变化
计数+采集点 noinline                   520      1000  ota_apply:992→520 变小
计数+noinline+96B快照                 520      1032  ota_apply:992→520 变小
计数+noinline+512B快照                520      1448  ota_apply:992→520 变小
出现「插桩后 ota_apply 栈帧 < 生产」的构型: 3/4（各小 472 B，同时链上求和更深）
```

父帧变小的同时链上真实峰值变深：`ota_stage_verify` 与 `ota_hash_block`
从「已内联无独立条目」变为独立 280B / 200-648B。因此**不能**用插桩构型的逐函数
栈帧当生产构型的上界。

**方法学结论（防止实现者误判单调性成立）**：四轮否证尝试——`scan.py` 21 配置
（3 插桩位置 × 7 快照尺寸）0 反例、`scan2.py` 18 配置多调用点链 0 反例、
`scan3.py` 7 配置体积膨胀型插桩（BULK=1..64）0 反例，只有 `scan4.py` 4 配置
抑制采集点内联时命中 3 反例。**单纯加大插桩体积或快照尺寸不足以触发非单调；
触发条件是插桩改变了内联结构。** 而 P2-6 恰好需要按函数归属栈帧、被内联函数
没有独立条目，所以插桩抑制内联是常态而非人为构造。

### 8.4 arena 坐标系与失败下界（整改 ⑥⑦）

读 `Libraries/OTA/ota_package.c` 与 `ota_patch.c` 确认的坐标系：

| 量 | 是否含 prefix | 出处 |
| --- | --- | --- |
| `arena.capacity` | **不含** | `ota_package.c:695` / `ota_patch.c:1189` |
| `info.workspace_peak` | **含** | `ota_package.c:740` / `ota_patch.c:1291` |
| `P_full`（P2-3 冻结值） | **含** | 契约 |

两条据此定下的规范（已写回提示词 §3.2 / §3.3）：

1. **失败下界不能相加**。`arena_peak_observed` 在容量检查**之前**更新，
   失败请求的 `aligned_size` 已经进入该字段，且字段本身含 prefix，
   故失败路径只能推出 `需求 >= arena_peak_observed`；写成
   `+ failed_request_size` 是重复计算。
2. **`arena.peak` 的更新时机不可动**。现状是检查通过后才更新，因此恒有
   `arena.peak <= arena.capacity`，`ota_package.c:720` / `ota_patch.c:1225`
   的 `arena.peak > arena.capacity` 是恒不触发的防御断言。把更新挪到检查之前
   会让那条门禁变成真实触发的控制流分支——那是改语义。观测量必须是新成员。

**假负例风险（实测确认）**：`ota_package.c:665` / `ota_patch.c:1161` 有
`workspace_len < OTA_*_WORKSPACE_SIZE`（40960B）前置拒绝，而 P2-3 实测
`P_full = 21832B` 远小于该值。所以「把 `workspace_len` 缩短到 `P_full`」会在进入
arena 之前就被拒，测到的是前置检查而非容量边界鉴别力。
`tests/ota/test_ota_package.c:249-251` 已有的 `short_workspace` 开关测的正是那条
前置检查，**不得复用它充当容量边界负例**。冻结的注入方式改为：保持
`workspace_len = 40960B`，仅在宿主 harness 用
`OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE` 覆盖 `arena.capacity` 为
`P_full - prefix` 与 `P_full - prefix - 1`，并要求负例报
`arena_peak_observed != 0` 以证明控制流确实进了 arena。

### 8.5 防回迁测试改全仓枚举（整改 ⑨）

裁定指出旧口径（扫 `.claude` 全树 + 仓库顶层 + `docs/` 顶层）漏掉任意嵌套位置。
实测把 `prompt-P9-7-bspatch.md` 放进 `notes/deep/` 时旧口径零命中，而
`git ls-files -co --exclude-standard -z -- "*.md"` 命中。

改后口径与实测数据：全仓 258 个 `.md`，路径深度 1-8 层；`.codex-worktree-*`
被 `.gitignore:66` 排除（0 命中）；**嵌套 git 仓库内的 `.md` 不被枚举**
（实测 `git init` 过的探针目录 0 命中，这也解释了为什么 `test_acceptance_bundle.py`
自己的 `.acceptance-repo-fixture-*` 不会污染断言）；仓库顶层散落的 `.md` 会被
枚举（实测 1 命中）。`-z` 是必需的：仓库含中文文件名，默认 quotepath 会转义路径。

`tests/ota/test_acceptance_bundle.py` 的 `GovernancePromptScopeTests` 现在有
`enumerate_repo_markdown()`（枚举失败即抛错，fail-closed）与
`find_stray_dispatch_prompts()`，并新增
`test_repo_wide_enumeration_reaches_nested_dirs`：在仓库内建深层临时目录放一个
派单式命名探针，断言它被枚举到且被判为 stray，用完即删。该探针目录**不能**加进
`.gitignore`——一旦被忽略，`git ls-files -co` 就看不见它，鉴别力断言随即失效。

本轮（第三轮整改）全量执行结果：39 个测试通过（1 项因缺依赖跳过），0 stray。
定向复核第二轮又新增 6 项 CI 接线回归，当前总数见 §9.2。

### 8.6 本轮仍未闭合的整改项

- 整改 ③ 只验证了 `-fstack-usage` 的**数据源可用性**，两条闭环路线（静态：生产
  调用图最大路径求和 + 最坏中断预算；运行期：连续最低 SP 观测）都未闭合，
  缺口已转为 §9 C3 的 `EVIDENCE_GAP` 条款（详见 §7 对应条目与提示词 §4.9-E）。
- 整改 ⑩（`docs/ota-prompts/prompt-p2-3-bspatch.md` 移动与
  `.claude/fix_plan_p2_6.js` 删除的用户授权）属流程项，不在本文件留痕范围。

---

## 9. 定向复核第二轮整改的实测证据（2026-08-16）

### 9.1 探针汇总器的 ENV_BLOCKED 误分类（阻断 1）

复核复现的缺陷：把某个探针的 runner 路径改成不存在的脚本后，Python 因「文件
不存在」返回 2，旧 `run_all.py` 只凭 `rc == 2` 判定，输出
`[ENV_BLOCKED] missing_runner` 并以 `rc=2` 收场。那实际是 harness 故障；混合出现
「真实失败 + 工具链缺失」时，旧逻辑还会用 `rc=2` 掩盖失败。

修复后的三条不变量：

| 项 | 冻结口径 |
| --- | --- |
| `ENV_BLOCKED` 判定 | 退出码 == 2 **且**输出含 `_probe_env` 签发的行首标记 `[ENV_BLOCKED] P2_6_PROBE_ENV_BLOCKED `；只认行首，不做子串包含 |
| 其余非零退出 | 脚本缺失、语法错误、解释器启动错误、断言失败、被信号杀死的负退出码一律 `HARNESS_FAIL` |
| 汇总优先级 | 有 `HARNESS_FAIL` → 1；否则有 `ENV_BLOCKED` → 2；全通过 → 0；**空序列 → 1** |

标记的签发（`require_tools()`）与识别（`is_env_blocked_output()`）同源在
`_probe_env.py`，防止调用方硬编码字符串后漂移。

**为什么不能用退出码反推故障类型**（Python 3.13.12 本机实测，2026-08-16 定向复核
第二轮补测）：`2` 并不专属"环境缺工具链"，而语法错误也不落在 `2` 上 ——

| 故障 | 实测退出码 |
| --- | --- |
| 脚本文件不存在（`python missing.py`） | 2 |
| 非法解释器参数（`python --bogus-option`） | 2 |
| 语法错误 | 1 |
| 未捕获异常（含 `AssertionError`） | 1 |
| `sys.exit(n)` | 原样透传 `n` |

即"非零退出码 → 故障类型"没有可靠映射，唯一可靠区分手段就是上表第一条的标记行。
本文早前把"语法错误"也写成返回 2 的表述已按实测更正。

`selftest/classification_selftest.py` 把裁定要求的四个负例冻结为可执行断言
（另加正例，共 20 项判据：`classify` 8 + `aggregate` 6 + 端到端 5 + 条目数门禁 1），
并由 `run_all.py` 作为**前置门禁**运行——自检不过即 `rc=1` 且不输出任何 Spec 结论。

| 编号 | 负例 | 期望标记 | 期望整体退出码 |
| --- | --- | --- | --- |
| N1 | 探针脚本缺失（假脚本故意不入库） | `HARNESS_FAIL` | 1 |
| N2 | 伪 `rc=2`（退出码 2 + 旧格式输出，无规范化标记） | `HARNESS_FAIL` | 1 |
| N3 | 真实环境阻塞 + harness 失败混合 | 两者并存 | 1（失败优先） |
| N4 | 纯环境阻塞（走真实 `require_tools()`） | `ENV_BLOCKED` | 2 |
| P1 | 全部通过（缺它则「恒判失败」也能过） | `PASS` | 0 |

**鉴别力用变异测试证明，不只看跑绿**：

```text
M1 classify 换回只看退出码的旧实现        -> 自检 8 处 FAIL（N2 复现为 rc=2/标记 ENV_BLOCKED）
M2 aggregate 改成环境阻塞优先             -> 自检 8 处 FAIL（含 aggregate([])=0、N3 得 rc=2）
M3 识别端标记前缀改成 DRIFTED_MARKER      -> 自检 6 处 FAIL（N3/N4 的真 ENV_BLOCKED 被判 harness 失败）
```

真实环境阻塞路径端到端验证（证明标记确由 `require_tools()` 签发而非测试桩）。
命令必须**先取到 Python 绝对路径再清空 PATH**，否则 shell 连 `python` 本身都找不到：

```text
PY=$(python -c "import sys; print(sys.executable)")
PATH="/nonexistent-dir-for-env-blocked-test" "$PY" tests/ota/spec-probes/p2-6/run_all.py
-> PY=C:\Users\SU\AppData\Local\Programs\Python\Python313\python.exe
-> 8 个探针全 ENV_BLOCKED（通过 0/8），整体 rc=2，逐项日志中出现
   [ENV_BLOCKED] P2_6_PROBE_ENV_BLOCKED 工具链缺失: gcc
-> 汇总行：存在 ENV_BLOCKED 且无 HARNESS_FAIL：工具链缺失，按验收合同不得记 PASS。
```

自检子进程用 `sys.executable` 启动，因此清空的 PATH 会被继承；N4 用的
`p2-6-tool-that-must-not-exist` 在任何 PATH 下都缺失，故自检仍先通过，再由正式
探针取得真实 `ENV_BLOCKED`。

恢复基线后完整执行：自检 20/20 + 探针 **8/8 PASS**，`rc=0`。

### 9.2 探针接入远端 CI（阻断 2）

此前 8 组探针只在本机跑过：`acceptance-governance.yml` 既不监听
`tests/ota/spec-probes/**`，执行步骤里也没有 `run_all.py`；`firmware-build.yml`
同样不监听。后果是「远端治理变绿」不能证明探针通过，且单独改探针不触发任何
workflow。

接线选择 **Acceptance Governance** 而非固件工作流：探针只需 `arm-none-eabi-gcc/nm/
objdump` 与宿主 `gcc`，不需要完整 App+Boot 构建；挂到固件工作流会让每次改探针都
跑一次全量构建。工具链固定 `13.3.Rel1`，与 `firmware-build.yml` 同版本——探针里的
栈帧字节数、`.su` 数值、内联折叠结论都绑定到具体版本。

`tests/ota/test_acceptance_bundle.py` 新增 `SpecProbeCiWiringTests`（6 项），
锁定路径过滤两处、工具链 action 与版本、执行命令、安装步骤先于探针步骤、
探针文件受 Validation profile 枚举、探针条目数与 `EXPECTED_PROBE_COUNT` 双向一致。
最后一项针对的是运行期门禁的盲区：**同时**把 `PROBES` 删到 1 项并把冻结值改成 1，
`run_all.py` 自己的门禁依然通过，CI 会以「1/1 通过」变绿。

七个变异全部被检出（每次只改一处、跑完即按字节恢复并核对 SHA-256）：

```text
M1 删掉 pull_request 侧路径过滤（只留 1 处）      -> FAIL
M2 工具链版本换成 14.2.Rel1                      -> FAIL
M3 工具链换成浮动 latest                         -> FAIL
M4 删掉探针执行命令                              -> FAIL
M5 工具链安装步骤挪到探针之后                    -> FAIL
M6 PROBES 删到 1 项且同步下调冻结值              -> FAIL
M7 某个探针路径改成不存在的脚本                  -> FAIL
```

`tests/ota/test_acceptance_bundle.py` 全量：**45 个测试通过**（1 项因缺依赖跳过），
0 stray。

**远端首轮的跨平台风险（必须预先声明）**：本轮全部探针数值基线在 Windows +
MinGW 宿主 gcc 15.2.0 上取得，`wrap_probe` 的 `real_pool_seq=(163,96)`、`scan4` 的
`ota_apply` 992B→520B 等精确数值要到 Ubuntu runner 首跑才能确认。同为 13.3.Rel1
时 ARM 侧代码生成应一致，但**若远端首轮红，处置口径是「工具链或构型已变 →
重新裁定基线」，不是把探针判为坏掉、也不是把 Spec 结论作废**。

### 9.3 「四选一」口径修正（高优先项）

本文 §7 早前写的「最大 SP 上界证据（四选一）」与提示词 §4.9-E 冻结的「两条完整
闭环路线」冲突，已按裁定改写（见 §7 对应条目）。口径以提示词 §4.9-E 为准：
`-fstack-usage` 只是逐函数数据源，跨路线拼凑不算闭环。
