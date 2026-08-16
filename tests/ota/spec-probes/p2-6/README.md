# P2-6 Spec 探针（栈守护 / 内存拦截 / 栈用量）

本目录是 P2-6（OTA 栈与堆护栏）**规范可行性探针**的受治理副本。原始探针位于
`.cache/p2-6-spec-probe/`，被 `.gitignore` 的 `/.cache/` 排除，导致干净 worktree
中验收会话拿不到证据、三类 manifest 也无法绑定原始判据。按派单前置整改裁定
（阻断 4），可复现的**源文件、runner、期望判据**迁入此处；`.o`/`.su`/`.elf`/
`.map`/`.exe` 等二进制生成物不入库。

本路径受 `Tools/provenance/manifest_profiles.json` 的 **Validation** profile 覆盖
（其 `root_patterns` 已含 `tests/`），因此**无需修改该 JSON**。

## 运行方式

仓库根执行：

```
python tests/ota/spec-probes/p2-6/run_all.py
```

- 退出码优先级**固定**（不可调换）：`1` = 至少一个探针 harness 失败（结论已失效
  或 harness 本身故障）；`2` = 没有 harness 失败且至少一个探针**真实**工具链缺失
  （`ENV_BLOCKED`，按验收合同不得记 PASS）；`0` = 全部与记录结论一致。
  混合出现"真实失败 + 工具链缺失"时**必须**返回 1：先返回 2 会让调用方按
  "补装工具链后重跑"处理，真实失败被环境噪声掩盖。
- `ENV_BLOCKED` **不看裸退出码**。判定要求退出码 == 2 **且**输出含
  `_probe_env.require_tools()` 签发的规范化标记行
  （`[ENV_BLOCKED] P2_6_PROBE_ENV_BLOCKED `）。理由：`python 不存在的脚本.py`
  与非法解释器参数也让 Python 返回 2（3.13.12 实测），只看退出码会把 harness
  故障误报成"工具链缺失"（2026-08-16 定向复核阻断 1 的实测负例）；语法错误等
  故障返回 1、`sys.exit(n)` 透传任意码，非零退出码与"缺工具链"没有可靠映射。
  标记的签发与识别（`is_env_blocked_output()`）都在 `_probe_env.py`，避免调用方
  硬编码字符串而漂移。
- 全部生成物落在 `.cache/p2-6-spec-probe-run/`（不受 Git 跟踪），每个探针另有
  一份 `<name>.log`。**正式运行日志必须按 SHA-256 绑定进证据包。**
- 单独运行某个探针：`python tests/ota/spec-probes/p2-6/<子目录>/run.py`。
- 单独运行 harness 自检：
  `python tests/ota/spec-probes/p2-6/selftest/classification_selftest.py`。

工具链要求（缺任一即 `ENV_BLOCKED`）：`gcc`（宿主）、`arm-none-eabi-gcc`、
`arm-none-eabi-nm`、`arm-none-eabi-objdump`。本轮实测版本：
Arm GNU Toolchain 13.3.Rel1（`arm-none-eabi-gcc 13.3.1`）、宿主 MinGW gcc 15.2.0。

## 全部探针 fail-closed

每个 runner 都把**记录结论冻结成期望值**并按退出码判定，不靠人工看输出：

| 探针 | 冻结基线 |
| --- | --- |
| `selftest`（前置门禁） | 20 项：`classify` 8 + `aggregate` 6 + 端到端 5 + 条目数门禁 1 |
| `guard_layout` | 10 个用例判定全中（含 `neg8` 命中集合恰为 `['A6']`） |
| `wrap_probe` | 14 项 ELF 判据 + 6 项 map 判据；四构型 `real_pool_seq=(163,96)` |
| `stack_usage/run.py` | `EXPECT_VIOLATION=False`（本构型无反例）、比较 3 种插桩构型 |
| `stack_usage/scan.py` | 21 配置、`EXPECT_NEG=0` |
| `stack_usage/scan2.py` | 18 配置、`EXPECT_NEG=0` |
| `stack_usage/scan3.py` | 7 配置、`EXPECT_NEG=0` |
| `stack_usage/scan4.py` | 3/4 构型出反例、`ota_apply` 992→520B、链上求和必须更深 |
| `host_scan` | `S1=1024`、`S2=8192`、`S3=1024`、`S4=8192`、`S5_guard_intact=0` |

结论翻转不是"探针坏了"，而是**工具链或构型已变，对应提示词判据必须重新裁定**，
不得静默沿用旧结论。

## `selftest/` —— harness 自身的 fail-closed 门禁

`run_all.py` 在跑正式探针**之前**先运行 `selftest/classification_selftest.py`；
自检不通过即整体 `rc=1` 且**不输出任何 Spec 结论** —— harness 不可信时
"8/8 通过"没有证据价值。

四个负例来自 2026-08-16 定向复核阻断 1（把 runner 路径改成不存在的脚本后，
旧汇总器输出 `[ENV_BLOCKED] missing_runner` 并以 `rc=2` 收场）：

| 编号 | 负例 | 期望标记 | 期望整体退出码 |
| --- | --- | --- | --- |
| N1 | 探针脚本缺失（`fake_missing_probe_does_not_exist.py` 故意不入库） | `HARNESS_FAIL` | 1 |
| N2 | 伪 `rc=2`（`fake_spoofed_env.py`：退出码 2 + 旧格式输出，无标记） | `HARNESS_FAIL` | 1 |
| N3 | 真实环境阻塞 + harness 失败混合 | 两者并存 | 1（失败优先） |
| N4 | 纯环境阻塞（`fake_env_blocked.py` 走真实 `require_tools()`） | `ENV_BLOCKED` | 2 |
| P1 | 全部通过（正例基线，缺它则"恒判失败"也能过） | `PASS` | 0 |

另有 `classify()` 8 项、`aggregate()` 6 项纯函数判据与 1 项条目数门禁
（`PROBES` 被删到 1 项时必须 `rc=1` 且不执行任何探针）。

`fake_env_blocked.py` **不硬编码标记**，直接调用生产路径的 `require_tools()`：
签发与识别始终同源，标记漂移会立即让 N3/N4 失败。已实测三种变异各自被检出：
只看退出码的旧 `classify`（8 处失败）、环境阻塞优先的 `aggregate`（8 处失败）、
识别端标记漂移（6 处失败）。

## 各探针用途与期望结论

### `guard_layout/` —— 九条链接期 ASSERT 的鉴别力

外置 guard 布局：

```
__StackTop   = 0x20058000  (= _estack = STACK$$Limit)
             ↓ 8192B 栈区 (.ota_stack)
__StackLimit = 0x20056000  (= STACK$$Base = __StackGuardEnd)
             ↓ 32B guard  (.ota_stack_guard)
__StackGuardStart = 0x20055FE0  (_sbrk 上限)
```

- `layout.ld.tmpl`：参数化链接脚本模板（`@@KEY@@` 占位符），含九条 ASSERT。
- `cases.json`：schema `p2-6-guard-layout-cases-v1`，**判据外置**，runner 不内嵌
  期望值。10 个用例 = 1 正例 + 9 负例。
- `probe_main.c`：extern 四个栈符号 + 两层间接宏引用 armlink 兼容别名
  （`STACK$$Base` / `STACK$$Limit`，**双美元**），并以 `P2_6_ONE_LAYER_MACRO`
  开关构造一层宏负例。

九条 ASSERT（全部锚在段的 `ADDR`/`SIZEOF` 上，不锚在裸符号算术上）：

| 编号 | 断言内容 |
| --- | --- |
| A1 | `SIZEOF(.ota_stack) == OTA_STACK_RESERVE` |
| A2 | `SIZEOF(.ota_stack_guard) == 32` |
| A3 | 栈段末尾 `== _estack` |
| A4 | guard 紧邻栈区，无空洞 |
| A5 | `._user_heap_stack` 末不侵入 guard |
| A6 | `__StackLimit == ADDR(.ota_stack)` |
| A7 | `__StackGuardStart == ADDR(.ota_stack_guard)` |
| A8 | `__StackGuardEnd == __StackLimit` |
| A9 | `__StackTop == _estack` |

两个关键负例：

- **`neg8_stacklimit_decoupled`（A6 独立负例，阻断 3）**：直接把 `__StackLimit`
  与 `.ota_stack` 脱钩会连带打死 A8/A3/A9，无法证明 A6 自身有鉴别力。做法是
  把 `__StackGuardEnd` 一并改成同一脱钩值 `_estack - OTA_STACK_RESERVE - 64`，
  使 A8 仍成立。判据用 `assert_exact`，要求命中集合**恰好** `['A6']`。
  实测通过。
- **`neg9_one_layer_macro`（两层宏必要性）**：`SECTION_START(_name_)` 展开为
  `_name_##$$Base`，`##` 抑制形参展开。若简化成一层宏，得到的是字面量
  `CSTACK_BLOCK_NAME$$Base` —— **编译期不报错**，只在链接期表现为未定义符号。
  判据要求错误文本含 `CSTACK_BLOCK_NAME$$Base` / `$$Limit`，且**不得**命中任何
  ASSERT（避免用别的失败冒充）。

三类判定分支：`assert_exact`（命中集合 == 期望）、`assert_contains`（期望 ⊆ 命中）、
`undefined_symbols`（未定义符号 + 无 ASSERT 命中）。

### `wrap_probe/` —— `--wrap` 拦截层选型

- `--wrap` 只改**跨目标文件**的符号解析。`-O2` 下 `lv_mem_buf_get` 对同一 TU 内
  `lv_mem_alloc` 的调用被尾调用折叠，链接前已无可拦截调用点。
- 结论：**required 拦截层是 `lv_tlsf_malloc` / `lv_tlsf_realloc` / `lv_tlsf_free`**，
  不是上层 `lv_mem_*`。
- fail-closed 语义：定义了 `__wrap_X` 却不传 `--wrap=X` → `__real_X` 未定义引用
  → 链接失败。这是设计要求，不是缺陷。
- 实测：四构型 `real_pool_seq=(163,96)`；`lv_mem_buf_get` 分支目标为
  `['__wrap_lv_tlsf_malloc']`；上层调用点确实被内联消除。

### `stack_usage/` —— `-fstack-usage` 与插桩单调性

- `run.py`：`-fstack-usage` 产出可用性（qualifier 全 `static`，无 `dynamic`/VLA）
  + 调用链求和 + 三种插桩构型的逐函数比较。**本构型无反例**。
- `scan.py` / `scan2.py` / `scan3.py`：分别扫描插桩位置×快照大小（21）、多调用点
  构型（18）、插桩体积（7 档 BULK）。**全部 0 反例。**
- **`scan4.py` 是 C16 判据的唯一实证反例来源**：给采集点加 `noinline` 后
  `ota_apply` 栈帧 **992B → 520B（小 472B）**，而链上求和 **992B → 1000/1032/1448B
  （更深）**，4 个构型中 3 个触发。
- 因此 C16 必须要求**两构型各自出 `.su` 并逐函数比较**，不能拿插桩峰值当生产峰值
  上界。父帧变小往往伴随链上真实峰值变深。
- 另一个必须写进判据的事实：`-O2` 下被内联的函数**没有独立 `.su` 条目**，
  "逐函数查表求和"会漏算，必须以实际存在的函数为准。

### `host_scan/` —— StackInfo 扫描算法与栈底 guard 的相互作用

照抄 `StackInfo.c:43-69` 的扫描算法，参数化 `BLANK` 与起扫下标：

| 场景 | 期望 | 机制 |
| --- | --- | --- |
| S1 | 1024 | 基准：非零哨兵 + 无 guard，扫描准确 |
| S2 | 8192 | guard 落在 `i=0`，扫描立即命中 → **恒返回满栈（失效）** |
| S3 | 1024 | 排除 guard 字后读数恢复 → **仅证明 S2 的成因**；`skip_words` 偏移修法已作废 |
| S4 | 8192 | `BLANK` 未与哨兵常量同步 → `i=0` 即命中 → **恒返回满栈（失效）** |
| S5 | `intact=0` | guard 字被完全覆盖 → 溢出可检出（外置 guard 的兜底手段） |

C 侧只输出纯 ASCII 键值行，判定全在 `run.py` 的 `EXPECT` 字典；编译告警
（`-Wall -Wextra` 下 stderr 非空）也计入失败。

**本探针支撑的判据是「guard 必须外置」，不是「给扫描加偏移」。** S2/S4 的失效值
恒为栈区总长 `8192B`，而门禁是「峰值 ≤ 8192B」，`8192 ≤ 8192` 成立 → C3 会**静默
假通过**。现行方案据此把 guard 移到 8192B 栈区之外，扫描 `i` 从 0 起算、不跳过
任何字（见 `docs/ota-exec-notes/P2-6-spec-stack-feasibility-2026-08-15.md` §6.1
的作废表）。S3 只是成因对照实验，**不得**被引用为推荐修法。

## 不迁移的第一轮探针（结论已被取代）

`.cache/p2-6-spec-probe/` 顶层还有一批**第一轮内置 guard 版**探针，**故意不迁移**：

- `probe.ld` / `fixed.ld` / `fixed_neg.ld` / `neg1.ld` / `neg2.ld` / `sbrk.ld`：
  内置 guard 布局，仅 3 条 ASSERT，已被 `guard_layout/layout.ld.tmpl` 的九条
  ASSERT 完全取代。同时迁移会在仓库里留下两套互相矛盾的布局脚本。
- `probe_sbrk.c` / `probe.c` / `probe_macro.c` / `probe_two_layer.c`：能力已并入
  `guard_layout/probe_main.c` + `neg9_one_layer_macro`。

如需追溯第一轮过程结论，见 `docs/ota-exec-notes/P2-6-spec-stack-feasibility-2026-08-15.md`。

## 与验收证据包的关系

- **入库**：本目录全部源文件、runner、`cases.json`（受 Validation profile 覆盖）。
- **不入库**：`.cache/p2-6-spec-probe-run/` 下的一切二进制、`.su`、`.map`、`.elf`。
- **必须绑定进证据包**：`run_all.py` 的完整输出与各探针 `<name>.log` 的 SHA-256。
  仅有 "探针通过" 的口头结论不构成证据。
