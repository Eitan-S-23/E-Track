# P2-6 升级态 RAM 峰值实测回填：实现证据

> 本文档是 P2-6 实现会话的过程证据与最终候选证据容器。当前会话不执行
> git commit/push/merge，不创建 `docs/acceptance-contracts/P2-6-v1.contract.json`，
> 不修改 P3/P4 或执行 Cloudflare 配置/部署。正式独立验收由非实现会话执行。

## 1. 会话与工作区基线

- 日期：2026-08-19
- 项目根：`D:\github\my\E-Track`
- 实现分支：`p2-6-implementation-20260819`（由 `main` 创建）
- 开工前 `HEAD`：`99173123cae8c487b86efa8a4eecbbe73b1bb512`
- 开工前 `origin/main`：`99173123cae8c487b86efa8a4eecbbe73b1bb512`
- 开工前工作区：仅有用户指定的 6 个无关未跟踪文件；这些文件必须保留且不参与本卡推断。
- 认领：`PLAN-OTA-EXEC.md` 的 P2-6 已改为“进行中”，认领标识为
  `Codex(P2-6 implementation agent) / 2026-08-19`。P3/P4 卡未改动。
- 写入预检：项目根、`.git`、源码目录、文档目录、构建目录、`.cache` 及其计划
  子目录均解析为 `D:\github\my\E-Track` 内的普通目录/文件；预检未发现
  reparse point、junction 或 symlink。
- 项目内临时/缓存边界：
  - `TEMP`/`TMP`/`TMPDIR`：`D:\github\my\E-Track\.cache\p2-6-test-tmp`
  - `PIP_CACHE_DIR`：`D:\github\my\E-Track\.cache\p2-6-tool-cache`
  - `CCACHE_DIR`：`D:\github\my\E-Track\.cache\p2-6-tool-cache\ccache`
  - `PYTHONPYCACHEPREFIX`：`D:\github\my\E-Track\.cache\p2-6-pycache`
  - 构建/探针日志：项目内 `.cache\p2-6-build-logs`、`.cache\p2-6-spec-probe-run`

## 2. 规范源读取记录

开工前已完整读取以下冻结输入（不是以摘要替代）：

1. `AGENTS.md`
2. `PLAN-OTA-EXEC.md` 的 P2-6 卡、§9 变更登记、§10 会话日志规则
3. `docs/ota-prompts/prompt-P2-6-implementation.md` 全文（已冻结，只读）
4. `PLAN-OTA.md` §9
5. `docs/ota-exec-notes/P0-6-ram-baseline-overlay.md` 全文
6. `docs/ota-exec-notes/P2-6-spec-stack-feasibility-2026-08-15.md` 全文
7. `docs/ota-binary-contracts.md` §10
8. `tests/ota/spec-probes/p2-6/README.md` 及其全部受治理源文件、runner、期望判据

`docs/acceptance-contracts/P2-6-v1.contract.json` 当前不存在，符合派单入口的
预定流程；本实现会话不创建或冻结该合同。

## 3. 编码前检索与现状

### 3.1 生产路径

- `USER/App/Utils/OtaUpdate/OtaUpdate.cpp` 的 `Session::Apply()` 已调用
  `HAL::OTA_PackageApplyStaging()` / `HAL::OTA_PatchApplyStaging()`，但成功路径
  只保存 `target_vcode`、`image_len`、`image_sha256`，丢弃 `workspace_peak`。
- 现有 `workspace_peak` 由 `arena.peak` 计算，P2-6 只允许把它接到 RTT 生产观测，
  不得重写其更新时机、结果码、校验顺序或 candidate I/O 时序。

### 3.2 诊断字段缺口

- `ota_package_info_t` 与 `ota_patch_info_t` 当前只有 `workspace_peak`，尚无
  `arena_peak_observed` / `failed_request_size`。
- 冻结方案 A 要求在 `arena_alloc` 的对齐计算后、既有容量检查前更新独立观测量；
  失败请求记录原始 `size`，不得与观测量相加。既有 `arena.peak` 仍只在容量检查
  通过后更新。
- 宿主容量边界必须保持 `workspace_len == 40960B`，只在宏
  `OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE` 下覆盖 `arena.capacity`，避免误测
  固定最小 workspace 前置拒绝。

### 3.3 GCC 栈与堆边界

- `cmake/linker/x-track-app-gcc.ld.S` 当前在 `._user_heap_stack` 中保留
  `_Min_Heap_Size + _Min_Stack_Size`，没有可扫描的 `.ota_stack` 或独立 guard 段。
- 目标布局冻结为：`._user_heap_stack` → 32B `.ota_stack_guard` → 8192B
  `.ota_stack` → `_estack`；四个 `__Stack*` 符号从实际段 `ADDR/SIZEOF` 派生，
  并加入 A1-A9 九条 ASSERT。现有 `.stack`/`.heap` 空段不承担新职责。
- `gcc_runtime_compat.c` 当前 `_sbrk` 上限为 `_estack - _Min_Stack_Size`；必须
  改为 `__StackGuardStart`，并新增 test-only `sbrk_call_count`/`sbrk_peak` 读取。
- startup `Reset_Handler` 当前在首次 C 调用前没有栈填充；必须在
  `extend_sram_512k` 前用无栈帧循环填充 8192B 哨兵，并写独立 32B guard 魔数。
- `StackInfo.c` 已有两层 `##` 宏，必须保留；`StackInfo.h` 的
  `STACK_INFO_BLANK` 必须与 startup 哨兵一致。AC5 不做哨兵/guard/栈峰值，只作
  静态 RAM 与 `Program Size` auxiliary 对照。

### 3.4 构型与测量边界

- 新增 `P2_6_TEST_ENABLE` 仅通过 C/C++ `target_compile_definitions` 进入测试
  插桩；不得加入 `OTA_TEST_LINKER_DEFINES`，永久 linker 栈布局必须在生产构型存在。
- required LVGL 计数拦截层固定为 `lv_tlsf_malloc/realloc/free` 的 `--wrap`；
  `lv_mem_*` 只可作分层归因。wrapper 必须原样转发，生产构型不得留下 wrapper、
  计数器、采集函数或 RTT 字符串。
- 生产输出必须在离开 OTA 核心 apply 窗口后再格式化 RTT，避免输出函数自身栈帧
  污染被测峰值；采集值在窗口内只写入静态/持久状态。
- 测量标记清单分为 L1（测试构型正向全命中）、L2（生产全零命中）和 L3（宿主
  容量覆盖项在两个固件构型全零命中），宏名只在 CMake cache/compile commands/
  编译命令行核对。

## 4. 设计选择（编码前冻结对齐）

1. 生产 RTT 观测：在 `Session::Apply()` 成功/失败返回前只保存本次 full/patch
   观测到的诊断快照；在 `Apply()` 返回后由同一生产路径的非关键窗口函数输出，
   保留结果码以区分成功完整峰值与失败下界，并通过 `SEGGER_RTT_printf` 输出。
2. 诊断字段：按提示词方案 A 实现两个 info 字段及成功/失败确定值；字段只读/打印，
   不参与控制流。
3. 栈上界路线：选择 §4.9-E 路线 (a) 静态闭环。运行期连续最低 MSP 观测/硬件
   边界机制在当前允许文件范围内没有既有实现；因此将用生产构型实际反汇编/调用
   图、两构型 `.su`、最坏异常预算和共享段地址完成静态闭环。若函数指针、递归、
   dynamic 栈或未知抢占嵌套导致闭环不能成立，按冻结规则记 `EVIDENCE_GAP`，不拼凑
   哨兵数字。
4. LVGL required 判据：实现 TLSF 三层 wrapper 与正/负例；`free` 只作交叉核对，
   非零必须定位释放点。另采 `lv_mem_monitor` 四字段作 C14 佐证，不以其替代 C6。
5. 真实负例：链接器九条 ASSERT 先在真实 `ld.S` 上跑正例及 A1/A2/A4/A5/A6
   独立负例；宿主 FULL/PATCH 容量边界用已成功的 `P_full` 反推两点，并证明
   candidate prepare/program 计数为零。

## 5. 实施顺序与验证计划

1. 先修改允许范围内的结构体/arena 诊断字段与生产观测保存链。
2. 再落地 GCC `.ota_stack`/`.ota_stack_guard`、startup 哨兵、StackInfo 和
   `_sbrk` test-only 计数。
3. 增加 CMake P2-6 互斥选项、测试编译定义、TLSF wrapper 链接选项；保持生产
   构型无测试插桩。
4. 新增/更新 `tests/ota/` 宿主回归、构型互斥、容量边界、ASSERT 正负例和 L1/L2/L3
   符号扫描；所有生成物只写项目内 `.cache`。
5. 运行受治理 Spec 探针和提示词列出的宿主测试，随后 GCC Release App/Boot；AC5
   仅尝试 auxiliary，失败记 `NOT_OBSERVED`，不修改范围外文件。
6. 如环境允许，按 AGENTS.md 流程完成单一 J-Link/RTT 闭环；任何不可恢复设备状态
   或冻结停止条件均立即落盘并停止。
7. 最终关闭 `P2_6_TEST_ENABLE` 做 fresh 生产构建，生成产物时间戳/SHA-256、size、
   map、warning/error 统计和 C1-C16 观测矩阵。

## 6. 红线与停止条件复核

- 不改 `40960B`、`8192B`、`163840B`、16KiB 字典、35492B 工作集、5468B 护栏。
- 不改 `Tools/etu_pack.py`、`ota_layout.h`、`lv_conf.h`、`lv_img_decoder.c`，不关
  `--gc-sections`，不重跑 `keil_uvprojx2cmake.py`。
- 不修改 P3/P4，不部署 Cloudflare，不删除/移动用户列出的无关未跟踪文件，不删除
  Objects/Listings/既有构建产物。
- 若需范围外文件、遇到未列失效模式、同一验证连续三次失败、真机不可恢复、有效
  栈峰值超过 8192B/guard 损坏、overlay 完整需求超过 40960B、sbrk/TLSF required
  增量非零、或契约不可实现：追加“停止记录”，将 P2-6 置“阻塞”，在看板 §9 登记
  并停止，不自行换方案或放宽门槛。

## 7. 当前状态

本文件创建于生产源码修改之前；截至本记录，除 P2-6 看板认领行外尚未修改生产
实现文件。下一步开始按 §1.1 逐项实施，并在每个关键验证后追加原始命令、退出码、
观测值、产物路径和 SHA-256。

## 8. 实现候选

### 8.1 固定池诊断与生产路径

- `ota_package_info_t` / `ota_patch_info_t` 新增 `arena_peak_observed` 与
  `failed_request_size`。`arena_alloc` 在对齐后、既有容量检查前更新独立
  `peak_probe`；失败请求记录原始未对齐 `size`。
- `workspace_peak` 仍为成功路径上的 `prefix + arena.peak`；失败路径只回传新增
  诊断字段，`arena_peak_observed` 明确是需求下界，未与 `failed_request_size` 相加。
- 宿主边界测试只通过 `OTA_P2_6_HOST_ARENA_CAPACITY_OVERRIDE` 覆盖
  `arena.capacity`，传入的 `workspace_len` 始终保持正式 `40960B`，没有绕过固定最小
  workspace 前置检查。
- `OtaUpdate::Session::Apply()` 仍走真实 full/patch staging apply 链。测试构型在核心
  apply 返回后才调用 RTT 报告函数；最终生产构型关闭 `P2_6_TEST_ENABLE`，不含报告、
  计数器或 wrapper。

冻结提示词红线 3 的六条不变量复核：

| 不变量 | 结论 | 证据 |
|---|---|---|
| `arena_alloc` 返回值与对齐行为 | 未改；仍按 `ARENA_ALIGNMENT` 对齐，容量失败返回 `0` | `Libraries/OTA/ota_package.c`、`ota_patch.c` diff；既有 package/patch 回归 |
| arena 清零与释放顺序 | 未改；仍为入口 `secure_zero`，出口 `secure_zero` 后 `workspace_release` | package/patch 回归日志 |
| `arena.peak` 与既有门禁 | 未改；`arena.peak` 仍只在成功分配后更新，`arena.peak > arena.capacity` 表达式保留 | package/patch diff 与容量负例 |
| `workspace_peak` 语义 | 未改；成功路径仍为 `prefix + arena.peak`，失败路径为 `0` | `.cache/p2-6-runlogs/test_p2_6_capacity.log` |
| candidate prepare/program 时序 | 未改；容量负例均在 candidate 副作用前退出 | FULL/PATCH 负例 `candidate_prepares=0`、`candidate_programs=0` |
| 既有结果码 | 未新增或改写；既有回归全部通过 | `test_ota_package.py`、`test_ota_patch.py`、`test_ota_update.py`、`test_ota_staging.py` |

### 8.2 GCC 栈区、guard 与堆边界

永久生产布局已落地：

| 项 | 生产 map 实测 |
|---|---:|
| `__StackGuardStart` | `0x20055FE0` |
| `__StackGuardEnd` | `0x20056000` |
| `__StackLimit` / `STACK$$Base` | `0x20056000` |
| `__StackTop` / `STACK$$Limit` / `_estack` | `0x20058000` |
| `.ota_stack_guard` | `32B` |
| `.ota_stack` | `8192B` |
| `._user_heap_stack` | `0x200550C0..0x200552C0`，`512B` |

`_sbrk` 上限改为 `__StackGuardStart`。startup 在首个 C 调用之前把
`[__StackLimit,__StackTop)` 填成 `0xA5A5A5A5`，把独立 guard 填成
`0x5A5A5A5A`；`STACK_INFO_BLANK` / `STACK_INFO_GUARD` 与之逐值一致。

真实 `ld.S` 复验：正例通过；A1/A2/A4/A5/A6 负例均链接失败并命中相应自定义
ASSERT，A6 命中集合恰为 `{A6}`。受治理 Spec 探针另覆盖 A1-A9 的完整 1 正例 +
9 负例和一层宏负例。原始日志：

- `.cache/p2-6-runlogs/test_p2_6_link_asserts.log`
- `.cache/p2-6-spec-probe-run/guard_layout.log`
- 汇总 `.cache/p2-6-runlogs/spec-probes.log`，SHA-256
  `10611B04424CF1175F953F88C6501F832B116BF64D958CA7A8A0B2C4A4B57092`

### 8.3 测试插桩边界

- `P2_6_TEST_ENABLE` 只进入 App 的 C/C++ 编译定义，不进入
  `OTA_TEST_LINKER_DEFINES`；与 P1-6/P2-1/P2-2/P2-3 四个构型逐对互斥。
- required wrapper 固定为 `lv_tlsf_malloc/realloc/free`，反汇编确认每个 wrapper
  原样调用真实 TLSF 函数。`malloc`/`realloc` 是门禁，`free` 仅交叉核对。
- L1 测试构型正向命中、L2 fresh 生产构型零命中、L3 宿主专属宏/符号在两个固件
  构型均零命中。宏在 `CMakeCache.txt` / `compile_commands.json` 核对，符号和
  字符串在 ELF/map/反汇编核对。
- 原始输出：`.cache/p2-6-runlogs/test_p2_6_configuration.log`、
  `.cache/p2-6-runlogs/test_p2_6_symbols.log`、`.cache/p2-6-symbol-scan/`。

## 9. 宿主与 Spec 验证

所有命令都在 `D:\github\my\E-Track` 执行，`TEMP`、`TMP`、`TMPDIR`、工具缓存和
Python bytecode 均定向到项目内 `.cache`。汇总退出码见
`.cache/p2-6-runlogs/all-tests-summary.tsv`，SHA-256
`CC3B04469F0FF448D0E6416C34AF236F6FEA9E426B018DBDEA6CFE2CDCF19CAD`。

| 验证 | 通过 | 失败 | 跳过 | 原始日志 |
|---|---:|---:|---:|---|
| P2-6 Spec harness 自检 | 20 | 0 | 0 | `.cache/p2-6-runlogs/spec-probes.log` |
| P2-6 受治理探针 | 8 | 0 | 0 | 同上及 `.cache/p2-6-spec-probe-run/*.log` |
| `test_acceptance_bundle.py` | 64 | 0 | 1 | `.cache/p2-6-runlogs/test_acceptance_bundle.log` |
| `test_ac5_ram_budget.py` | 3 | 0 | 0 | `.cache/p2-6-runlogs/test_ac5_ram_budget.log` |
| `test_f435_build_bootstrap.py` | 14 | 0 | 0 | `.cache/p2-6-runlogs/test_f435_build_bootstrap.log` |
| `test_p2_5_build_provenance.py` | 10 | 0 | 1 | `.cache/p2-6-runlogs/test_p2_5_build_provenance.log` |
| `test_ota_package.py` | 102 | 0 | 0 | `.cache/p2-6-runlogs/test_ota_package.log` |
| `test_ota_patch.py` | 167 | 0 | 0 | `.cache/p2-6-runlogs/test_ota_patch.log` |
| `test_ota_update.py` | 7 | 0 | 0 | `.cache/p2-6-runlogs/test_ota_update.log` |
| `test_ota_staging.py` | 48 | 0 | 0 | `.cache/p2-6-runlogs/test_ota_staging.log` |
| backup + confirm-health | 132 | 0 | 0 | `.cache/p2-6-runlogs/test_ota_backup.log` |
| OTA SD core + adapters | 34 | 0 | 0 | `.cache/p2-6-runlogs/test_ota_sd.log` |
| GCC reproducibility | 1 | 0 | 0 | `.cache/p2-6-runlogs/test_ota_gcc_reproducibility.log` |
| SDIO command timeout functions | 9 | 0 | 0 | `.cache/p2-6-runlogs/test_sdio_command_timeouts.log` |
| P2-6 FULL/PATCH capacity scenarios | 6 | 0 | 0 | `.cache/p2-6-runlogs/test_p2_6_capacity.log` |
| P2-6 configuration cases | 7 | 0 | 0 | `.cache/p2-6-runlogs/test_p2_6_configuration.log` |
| 真实 `ld.S` 正例 + 指定负例 | 6 | 0 | 0 | `.cache/p2-6-runlogs/test_p2_6_link_asserts.log` |
| P2-6 L1/L2/L3 符号测试 | 6 | 0 | 0 | `.cache/p2-6-runlogs/test_p2_6_symbols.log` |

## 10. FULL/PATCH 宿主容量边界

原始日志 `.cache/p2-6-runlogs/test_p2_6_capacity.log`，SHA-256
`B44D41AF598D1C0D1A063CCF9F274EA4E43DD1F24E27496C27DD8609E0A7665B`。

| 路径 | `prefix` | 完整需求 `P_full` | 成功容量 | 失败容量 | 失败请求 | 失败副作用 |
|---|---:|---:|---:|---:|---:|---|
| FULL | `6576B` | `33072B` | `26496B` | `26495B` | `16384B` | prepare/program=`0/0` |
| PATCH | `7640B` | `21848B` | `14208B` | `14207B` | `4096B` | prepare/program=`0/0` |

两条成功路径均满足 `workspace_peak == arena_peak_observed == P_full <= 40960B`。
两条失败路径的 `workspace_peak=0`，`arena_peak_observed=P_full` 只作为该 fixture 下的
下界/鉴别力输出；一般失败路径仍不得把该字段解释成完整需求。没有触发字典降档或
冻结门槛修改条件。

## 11. 构建、产物与 RAM

### 11.1 GCC fresh 生产构建

最终构型：Ninja、Release、`SOURCE_DATE_EPOCH=1786320000`、
`CMAKE_OBJECT_PATH_MAX=1024`、`P2_6_TEST_ENABLE=OFF`。构建根：
`.cache/p2-6-cmake-prod-final-r2`。App 与 Boot 均构建成功。

- App size：`text=597660`、`data=932`、`bss=561040`、`dec=1159632`
- Boot size：`text=14720`、`data=4`、`bss=9780`、`dec=24504`
- warning：原始 `634` 行、去重 `578` 行，其中 linker 类 `380` 行；error=`0`
- 构建日志：`.cache/p2-6-runlogs/prod-r2-build.log`，SHA-256
  `9E0A4A28A86DEE6F5EB93ED38683D20DE4AD372F2433769167FBAEEEF3B4511D`
- size 日志：`.cache/p2-6-runlogs/prod-r2-size.log`，SHA-256
  `E82925693D5F2B5135451DAD42210FCC7E788656558647C1A0DC12C00A3C387A`

| 产物 | 时间戳 | SHA-256 |
|---|---|---|
| `app-gcc/X-Track-App-GCC.elf` | `2026-08-19T05:54:40.3818316+08:00` | `A86709C22B3C829128C3A9D31592A5FEAEAFD224D9871DF051DB5B64BBBB0487` |
| `app-gcc/X-Track-App-GCC.hex` | `2026-08-19T05:54:40.4774924+08:00` | `BBE8FF598F806106BFF96596071CCEFCCD07EE81E11F1F7749AC7CF4BE749E4B` |
| `app-gcc/X-Track-App-GCC.bin` | `2026-08-19T05:54:40.5269822+08:00` | `36D5C208077F08E487954D8EB9AD383827306C4F692E29545724317BE7C6CE3D` |
| `app-gcc/X-Track-App-GCC.map` | `2026-08-19T05:54:40.3857384+08:00` | `20794BC973A732CBEFBFF313B28EBA60B9D0190DAD522D504A855697091C4BA` |
| `boot/X-Track-Boot.elf` | `2026-08-19T05:54:36.3771106+08:00` | `D21713CA2C1EFEAC949F8EC0FFDDACAC439FED6BF26F9C65641BEE24464FDABC` |
| `boot/X-Track-Boot.hex` | `2026-08-19T05:54:36.5083405+08:00` | `FF3BADEF69BE6D97FD66815B8DF90EFD962A708B559C8951D4B56380F8001F71` |
| `boot/X-Track-Boot.bin` | `2026-08-19T05:54:36.6427458+08:00` | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F659` |
| `boot/X-Track-Boot.map` | `2026-08-19T05:54:36.3790632+08:00` | `14E7A8ADDD37DFE71744C11AB0DB60D5C535FBE725FE3E950F82354F34A4FC93` |

### 11.2 GCC 主 RAM 口径

P2-6 前当前产物的旧口径高水位为 `0x200562C0 = 352960B`，其中
`._user_heap_stack` 同时包含 512B 堆和 4096B 栈空洞。P2-6 后按冻结提示词改用
guard 起址作为静态保留边界：

- guard 边界高水位：`0x20055FE0 = 352224B / 360448B`
- 从该边界到 RAM 顶部：`8224B = 32B guard + 8192B 契约栈`，不是通用空闲堆
- 数据/最小堆末端：`0x200552C0 = 348864B`
- 可合法增长到 guard 的真实 heap headroom：`0xD20 = 3360B`
- 与旧高水位数值差：`352224 - 352960 = -736B`；因口径和布局同时变化，不能解释
  成“多出 736B 通用 RAM”

### 11.3 AC5 auxiliary

AC5 构建成功，warning=`0`、error=`0`：

- `Program Size: Code=301276 RO-data=289372 RW-data=1332 ZI-data=532248`
- `RW_IRAM1` 高水位 `0x55D10 = 351504B`
- armlink `Max=0x57FF8 = 360440B`，可用余量 `8936B`；若只按物理 352KiB
  `360448B` 计算则差 `8944B`，二者相差 armlink 顶部保留的 `8B`
- 构建日志 `.cache/p2-6-build-logs/ac5.log`，SHA-256
  `30923504D31AD5F9B5F64E38D0B0E7A3B846750FE585DC0DE39C210454F7E7F6`

| 产物 | 时间戳 | SHA-256 |
|---|---|---|
| `Objects-App-AC5/X-Track-App-AC5.axf` | `2026-08-19T04:36:45.5941451+08:00` | `05EDCD26B655B86E9BC47042D3E2C5E22B580B699158B123DDBFCC608925B85B` |
| `Objects-App-AC5/X-Track-App-AC5.hex` | `2026-08-19T04:36:49.8443575+08:00` | `B0BB240BCFB59CEFB0DA435194EFB5B582DCC5954078265C4D81B1E290761BA7` |
| `Track-App-AC5.bin` | `2026-08-19T04:36:49.9562106+08:00` | `3BB159C7DEDBC671EEAC27D954FA38CEF6AB4C5EA1341952705731F0706C65D3` |
| `Listings-App-AC5/X-Track-App-AC5.map` | `2026-08-19T04:36:46.1429850+08:00` | `0DC825F0402F03B91124A50E60C7FF18E9C6A81392521ABD7D8D2EBAD1C8C935` |

AC5 只作辅助静态对照，没有作为 OTA/CI 产物，也没有生成 AC5 栈峰值结论。

## 12. measurement-validity、C3 与迁移性

### 12.1 C13 八项验证

| 项 | 状态 | 观测/边界 |
|---|---|---|
| 1. 四个栈边界符号 | PASS | 生产 map/nm 为 `0x20055FE0/0x20056000/0x20056000/0x20058000` |
| 2. `STACK$$` 方向与长度 | PASS | Base=`0x20056000`，Limit=`0x20058000`，差 `8192B` |
| 3. guard 不在扫描区 | PASS | 扫描 `[0x20056000,0x20058000)`；guard `[0x20055FE0,0x20056000)`，无交集 |
| 4. 哨兵与 `STACK_INFO_BLANK` | PASS | startup 与头文件均为 `0xA5A5A5A5`；guard 独立为 `0x5A5A5A5A` |
| 5. 约 1024B 正例 | PASS | host scan S1 实测 `1024B` |
| 6. 三类负例 | PASS | S4 拒绝 BLANK 错配；S2 识别错误扫描范围包含 guard；S5 检出 guard 被写成 `0xDEADBEEF` |
| 7. 扫描自身开销 | EVIDENCE_GAP | `.su` 显示 scanner 直接帧 `0B`、entry/end 采集函数帧 `16B/8B`，但未取得同构型受控运行差分，不能只用 `.su` 代替冻结测法 |
| 8. startup 填充后立即扫描 | NOT_OBSERVED | J-Link 未连接，未取得启动后立即扫描观测 |

因此 C13 未全通过，分类为 `EVIDENCE_GAP`；C3/C4 的任何产品 PASS/FAIL 结论均不得
成立。host scan 原始日志：`.cache/p2-6-spec-probe-run/host_scan.log`。

### 12.2 C3 最大 SP 上界路线

选择冻结 §4.9-E 路线 (a) 静态闭环，但未闭合：

- 生产与测试各保存 `381` 个 `.su` 文件；生产 `4061` 条、测试 `4071` 条，qualifier
  全为 `static`，`dynamic=0`。
- 核心帧：`ota_package_apply_full=584B`、`ota_patch_apply=712B`、
  `HAL::OTA_PackageApplyStaging=64B`、`HAL::OTA_PatchApplyStaging=80B`；两构型一致。
- 生产调用图仍有无法仅凭当前反汇编闭合的间接边：full 根下 6 个间接调用函数，
  patch 根下 7 个，涉及 `ota_*_apply` 的 I/O 回调、`stream_append`、LZMA allocator/free、
  header reader 与 candidate write。
- 最坏中断/异常嵌套预算未能按基本帧、FPU 扩展帧、对齐字、ISR 软件保存帧和实际
  NVIC 抢占组合五项闭合。

原始证据：`.cache/p2-6-evidence/prod-callgraph.txt`，SHA-256
`060A780B8F015147AC4E75D2982C7883262D02199F6275328E631773CA648C59`；
生产 `.su` manifest SHA-256
`2acc3a5c0154966eaf843966ad2cd679ad87ac05bd1022cb2b2a1dd1cdbf3761`。

结论：C3=`EVIDENCE_GAP`。未把静态局部数据与哨兵扫描拼成闭环，也未声称取得
`<=8192B` 的产品结论。

### 12.3 C16 七项迁移性论证

| 项 | 状态 | 结论 |
|---|---|---|
| 1. 两构型 `.su` | PASS | 各 `381` 文件，均无 dynamic qualifier |
| 2. 逐函数比较 | PASS | 12 个差异条目；核心 full/patch/HAL apply 帧一致；`Session::Apply` 为 `112/120B`，`_sbrk` 为 `8/16B`，其余为 test-only |
| 3. 内联/尾调用函数体集合 | PASS | 生产标签 `2719`、测试 `2737`；生产独有 `0`，测试独有 18，均为测量/TLSF monitor 相关函数 |
| 4. 采集点在核心窗口外 | PASS | begin 在调用核心 apply 前，end 在其返回后；RTT 格式化在 `Session::Apply` 收到结果后 |
| 5. wrapper/诊断不改 OTA 控制流 | PASS | wrapper 只转发到真实 TLSF；诊断字段未进入判断；既有 OTA 回归全绿 |
| 6. 中断栈预算 | EVIDENCE_GAP | 未按实际 NVIC 最坏抢占组合闭合五项预算 |
| 7. 共享 A 类布局 | PASS | 两构型四个 `__Stack*` 地址、8192B 栈、32B guard 与 A1-A9 相同 |

C16 整体为 `EVIDENCE_GAP`，不能据此把插桩固件的未来真机数值直接迁移成生产结论。
生产/测试反汇编 SHA-256 分别为
`88D9507D79380D3CCF7C63F964EBBCBE48CA2400D3AD4AAC2D755A275691BEF6` 与
`CD7B7406D3D9BB7ED9CF198720477CDF4F5EEA187963283B4C420A515567AA6E`。

## 13. 真机、升级资产与生产恢复

### 13.1 测试构型、升级资产与有限真机观测

测试构型来自 `.cache/p2-6-cmake-test-final-r2`，其 `CMakeCache.txt` 明确
`P2_6_TEST_ENABLE=ON`，App map 的 `_SEGGER_RTT=0x20053E1C`。最初两次连接确实
出现 `Failed to initialized DAP`，原始日志仍保留在
`.cache/p2-6-runlogs/jlink-flash-test-20260819.log`；后续按 `AT32F435RGT7`、SWD、
1000kHz 重试后 DAP 初始化成功，旧结论“未烧录”不再成立。

为执行 SD FULL/PATCH 路径，使用冻结工具生成了同源测试基线、目标和两种 `.etu`：

| 资产 | 字节 | 时间戳 | SHA-256 |
|---|---:|---|---|
| `X-Track-App-GCC-test-v2.8.0.finalized.bin` | 600656 | `2026-08-19T13:20:55.6451563+08:00` | `8394730F258AE614DFED0C42931FF45D75DF620CD2C5B49BA4E2CD86E4AC75E6` |
| `X-Track-App-GCC-test-v2.8.1.finalized.bin` | 600656 | `2026-08-19T13:07:24.7408118+08:00` | `12C0BECB6233CD10756B464865E0C9FA4909B21876DCF661EDBC41493EFA8223` |
| `P2-6-FULL-v2.8.1.etu` | 282328 | `2026-08-19T13:20:56.4381849+08:00` | `AC39E95BB020A2C118FD120046700EFD3C5825E85421604DB8E5A3BA4A04F212` |
| `P2-6-PATCH-v2.8.0-to-v2.8.1.etu` | 305 | `2026-08-19T13:20:58.4228144+08:00` | `A5D30FD7B23F9B9C3008DB19269096A1AEB482FB795A7D29B4F8917C819FB302` |

FULL 与 PATCH 解包结果均为 600656B，SHA-256 都等于目标 `v2.8.1` 的
`12C0...8223`，逐字节比较均为 `True`。资产汇总日志
`.cache/p2-6-hardware-20260819/package-assets-summary.log` 的 SHA-256 为
`9D909DFA9A171A99E964CD17098F7CE29C9AC26322DE2BC9AE84BAC3B43C9B5C`；
round-trip 结论日志 `.cache/p2-6-hardware-20260819/roundtrip-summary.log` 的
SHA-256 为 `97716AB4C91167D61765D98AA4BD29135B806C806A1C966B4E01B04D635B5F97`。

J-Link 已把测试 `v2.8.1` App 以 `loadbin ..., 0x08010000` 写入并完成
`Verify successful`。烧录日志
`.cache/p2-6-hardware-20260819/flash-finalized-v2.8.1.log` 的 SHA-256 为
`B6006324AC29847F80161F4587902A2EB758D1EB918D006A8FBE94E243EE9A9B`。
复位后在 `0x20053E1C` 读到完整 `SEGGER RTT` 签名，App 向量首字为
`0x20058000`，`0x08010400` 为 `ETFW`、vcode `20801`、版本名 `2.8.1`；原始探测日志
`.cache/p2-6-hardware-20260819/post-flash-signature.log` 的 SHA-256 为
`B02CB0DE404E8FE90E6D32256E9B3478FC3063F9CDC203186BD58B12B356662F`。
随后也烧录并验证了测试基线 `v2.8.0`，供 PATCH 起点使用。

但是 Windows 枚举仅有固定盘 `C:`、`D:` 和 CD-ROM `F:`，不存在
`DriveType=2` 的可写移动盘或 SD 盘符。证据
`.cache/p2-6-hardware-20260819/removable-volume-audit.log` 的 SHA-256 为
`AF1FD9C302ED6AAA143A225AA177244E3A1573DCA544377A1229115C84520034`。
因此两份 `.etu` 无法写入设备物理 SD 卡，真实 SD OTA apply 窗口从未启动；测试固件
启动 RTT 只包含 `HANDOFF`、QSPI 和 BCB 启动信息，不含任何 P2-6 OTA 窗口计量行。
这意味着成功烧录、签名和资产 round-trip 不能替代 C1-C7/C14 的生产路径观测。

### 13.2 fresh 生产构型恢复

收尾前重新使用 `.cache/p2-6-cmake-prod-final-r2` 的 fresh 生产 App，
`CMakeCache.txt` 明确 `P2_6_TEST_ENABLE=OFF`。最终 finalized App 为：

- 路径：`.cache/p2-6-hardware-20260819/X-Track-App-GCC-production-v2.8.0.finalized.bin`
- 字节：`599092`
- 时间戳：`2026-08-19T13:58:34.6163465+08:00`
- SHA-256：`C601312045E4B78B2F25795CF81FA6C4153DB0BBED1F89541DEB080CF13C7F48`

该 App 仅写入 `0x08010000`，现有 Boot 保留；`verifybin` 成功。烧录日志
`.cache/p2-6-hardware-20260819/flash-production-v2.8.0.log` 的 SHA-256 为
`FBC59933F0E72272E008B1F542B7B14EE9E7F59B6F6DC271EDBBC94BC8C77CC8`。
生产 map 对应 RTT 地址为 `0x20053E14`，复位后签名、App 向量、`ETFW`、vcode
`20800` 和版本名 `2.8.0` 均正确；探测日志
`.cache/p2-6-hardware-20260819/production-signature.log` 的 SHA-256 为
`FFA912FD8EFCD0202479F420D596CBA456308A955CE345A3A4AE83A8A3C6C0E6`。

最终生产 RTT 原始日志为
`.cache/p2-6-hardware-20260819/rtt-production-v2.8.0.log`，286B，SHA-256
`A266CBF3756F12F49D8D5B63037298E62E7AD928AD960B4D1FE33AC15BB81FB8`；内容包含
`OTA: HANDOFF vtor=0x08010000`、`QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled`、
`OTA: BCB already CONFIRMED vcode=20800`，不含 WDT/HardFault。设备最终处于 fresh
生产构型运行状态，收尾检查无残留 `JLinkRTTLogger` 或其他 `JLink*` 进程。

## 14. P2-6-C1 至 C16 观测矩阵

格式：`判据ID | observed | evidence path`。

```text
P2-6-C1  | NOT_OBSERVED；FULL 资产已生成并 round-trip，但无可写 SD 介质，生产 apply 窗口未启动；宿主 33072B 仅属 C10 | .cache/p2-6-hardware-20260819/package-assets-summary.log；.cache/p2-6-hardware-20260819/removable-volume-audit.log
P2-6-C2  | NOT_OBSERVED；PATCH 资产已生成并 round-trip，但无可写 SD 介质，生产 apply 窗口未启动；宿主 21848B 仅属 C11 | .cache/p2-6-hardware-20260819/package-assets-summary.log；.cache/p2-6-hardware-20260819/removable-volume-audit.log
P2-6-C3  | EVIDENCE_GAP；未取得 OTA 窗口峰值，静态路线仍有未闭合间接边与中断预算 | .cache/p2-6-evidence/prod-callgraph.txt
P2-6-C4  | NOT_OBSERVED；测试固件已烧录且启动，但没有 OTA 窗口 guard 观测，且 C13 前置未全通过 | .cache/p2-6-hardware-20260819/rtt-startup-v2.8.1.log；.cache/p2-6-hardware-20260819/removable-volume-audit.log
P2-6-C5  | NOT_OBSERVED；真实 OTA 核心窗口未启动，sbrk_call_count 增量未取得 | .cache/p2-6-hardware-20260819/removable-volume-audit.log
P2-6-C6  | NOT_OBSERVED；真实 OTA 核心窗口未启动，required TLSF malloc/realloc 与 free 交叉核对增量均未取得 | .cache/p2-6-hardware-20260819/removable-volume-audit.log
P2-6-C7  | NOT_OBSERVED；未执行真实 OTA 异常退出，overlay release/LiveMap 重建未观测 | .cache/p2-6-hardware-20260819/removable-volume-audit.log
P2-6-C8  | GCC guard 边界高水位=352224B/360448B；顶部8224B=32B guard+8192B stack；heap headroom=3360B；旧口径352960B，数值差-736B | .cache/p2-6-cmake-prod-final-r2/app-gcc/X-Track-App-GCC.map
P2-6-C9  | AC5 auxiliary：高水位=351504B；armlink Max=360440B，余8936B；Program Size Code=301276 RO=289372 RW=1332 ZI=532248 | MDK-ARM_F435/Listings-App-AC5/X-Track-App-AC5.map
P2-6-C10 | FULL：prefix=6576B，P_full=33072B；cap=26496B 成功，26495B 失败；failed_request=16384B；负例 candidate prepare/program=0/0 | .cache/p2-6-runlogs/test_p2_6_capacity-r2.log
P2-6-C11 | PATCH：prefix=7640B，P_full=21848B；cap=14208B 成功，14207B 失败；failed_request=4096B；负例 candidate prepare/program=0/0 | .cache/p2-6-runlogs/test_p2_6_capacity-r2.log
P2-6-C12 | L2 生产零命中=true；L3 在 production/test 两构型零命中=true | .cache/p2-6-runlogs/test_p2_6_symbols-r2.log
P2-6-C13 | EVIDENCE_GAP；八项中1-6通过，7缺同构型受控运行差分，8虽已启动测试固件但无“startup 后立即扫描”观测；三类宿主负例均被识别 | .cache/p2-6-spec-probe-run/host_scan.log；.cache/p2-6-hardware-20260819/rtt-startup-v2.8.1.log
P2-6-C14 | NOT_OBSERVED；真实 OTA 窗口未启动，lv_mem_monitor 四字段进出差值未取得 | .cache/p2-6-hardware-20260819/removable-volume-audit.log
P2-6-C15 | TEST_ENABLE=1 对 L1 全命中=true，宏覆盖全部插桩 TU | .cache/p2-6-runlogs/test_p2_6_symbols-r2.log
P2-6-C16 | EVIDENCE_GAP；七项中1-5、7有结论，第6中断预算未闭合；两构型四符号一致=true | docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md
```

## 15. 剩余缺口、状态与文件系统审计

未完成项：C1/C2 的 SD FULL/PATCH 生产路径峰值；C3 的静态或运行期完整闭环；
C4-C7/C14 的真实升级窗口观测；C13 第 7 项受控扫描差分和第 8 项 startup 后立即扫描；
C16 中断预算；异常退出后 overlay 释放与 LiveMap 重建。J-Link 已恢复可用，当前实际
阻断是系统没有可写移动盘/SD 盘符。继续这些观测需要用户提供可由本机写入的物理 SD
介质或完成等价的物理介质配合；禁止改走非 SD 生产路径或伪造数字。

收尾重跑汇总位于 `.cache/p2-6-runlogs/p2-6-r2-host-summary.tsv`，SHA-256
`D0978259CF78556EB29138D71727FEBB5BF3C14DA6B3EA866E0D36318021EE2D`。结果为：
Spec harness `20/20`、受治理探针 `8/8`、acceptance bundle `64 pass / 0 fail /
1 skip`、AC5 budget `3/3`、bootstrap `14/14`、provenance `10 pass / 0 fail /
1 skip`、package `102/102`、patch `167/167`、update `7/7`、staging `48/48`、
capacity `6/6`、configuration `7/7`、链接 ASSERT `6/6`、生产符号扫描 `6/6`。
原始 `*-r2.log` 均在同目录；汇总脚本早先的 PowerShell `if` 表达式错误只影响空汇总
文件，不影响各测试进程退出码或原始日志，现已按原始日志重新生成汇总。

P2-6 的上述“进行中/未触发停止条件”结论已被本文件 §16 的续会话记录取代。续会话
对同一栈闭环验证连续执行三次且均失败，已命中冻结提示词的机械停止条件；当前卡状态
为“阻塞”，不得由实现会话继续修正或发起第四次验证。

本会话主动选择的源码、文档、构建、日志、缓存、测试与证据输出均位于
`D:\github\my\E-Track` 内。后续 J-Link 调用已把 `APPDATA`、`LOCALAPPDATA`、
`TEMP`、`TMP` 定向到项目内 `.cache/p2-6-jlink-*`；但较早的 J-Link 调用在覆盖生效前
自动触碰了项目外 `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`。最终该文件
长度 `986B`，时间 `2026-08-19T14:00:19.8732596+08:00`，SHA-256
`F29B1C7215E4B38F1F782AF36A45D0D213A2EE7E0EF0287D04C98A1982933832`；内容哈希与
早期检查相同，仅时间发生变化。该文件未被本会话修改、恢复、移动或清理；针对
`C:\Users\SU\AppData\Roaming\SEGGER` 的收尾审计未发现其他本轮新增文件。

用户列出的六个无关未跟踪文件保持原路径和未跟踪状态，未修改、删除、移动或提交。
未创建 `docs/acceptance-contracts/P2-6-v1.contract.json`，未执行 commit/push/merge/
rebase/stash，未触碰 P3/P4 或 Cloudflare。

## 16. 续会话静态栈闭环停止记录（2026-08-19）

### 16.1 fresh 栈数据构型

续会话先完成两个项目内 fresh Release/Ninja 构型，均使用
`SOURCE_DATE_EPOCH=1786320000`、`CMAKE_OBJECT_PATH_MAX=1024`、C/C++
`-fstack-usage`：

| 构型 | `P2_6_TEST_ENABLE` | App ELF/BIN | Boot ELF/BIN |
|---|---|---|---|
| `.cache/p2-6-cmake-prod-stack-final` | `OFF` | `864320B / 599092B`；ELF SHA-256 `A86709C22B3C829128C3A9D31592A5FEAEAFD224D9871DF051DB5B64BBBB0487`；BIN SHA-256 `36D5C208077F08E487954D8EB9AD383827306C4F692E29545724317BE7C6CE3D` | `36860B / 14724B`；ELF SHA-256 `D21713CA2C1EFEAC949F8EC0FFDDACAC439FED6BF26F9C65641BEE24464FDABC`；BIN SHA-256 `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| `.cache/p2-6-cmake-test-stack-final` | `ON` | `866296B / 600656B`；ELF SHA-256 `A4987711DB240417E24D527B319F2B4B16BDACCD268EEA79907C39D2B4C175A0`；BIN SHA-256 `FBF83E202E36118E5C79C12898BC583CCE56EAA88E931536311D5D7240B0288D` | 与生产构型 Boot 相同 |

两个 Ninja 子进程都生成了完整 App/Boot 产物后退出；生产目录追加检查输出
`ninja: no work to do.`。宿主调用工具在 120 秒处超时，导致两份 Tee 构建日志只保存
到中段，不能把其中的局部 warning 计数当作完整构建 warning 总数。配置日志分别为
`.cache/p2-6-build-logs/configure-prod-stack-final.log` 和
`.cache/p2-6-build-logs/configure-test-stack-final.log`；构建日志分别为
`.cache/p2-6-build-logs/build-prod-stack-final.log` 和
`.cache/p2-6-build-logs/build-test-stack-final.log`。

### 16.2 同一验证项连续三次失败

验证项均为 `python -B tests/ota/test_p2_6_stack_closure.py`，三次均在
`setUpClass` 的证据解析阶段失败，尚未形成 C3/C13/C16 产品结论：

| 次数 | 现象 | 原始日志 | SHA-256 |
|---:|---|---|---|
| 1 | `function_key()` 处理 objdump 的 `(anonymous namespace)::...` 符号时对空列表取 `[-1]`，抛出 `IndexError` | `.cache/p2-6-build-logs/stack-closure-run-1.log` | `91B602A3E6C43DA551A3D9589520B27AF90E1130EB2AAEE32085C0AE289B4D64` |
| 2 | 修正匿名命名空间解析后，脚本用错误对象后缀 `Libraries/OTA/LzmaDec.c.obj` 查找 `LzmaDec_Allocate`，而真实 map 对象来自 `bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c.obj`，抛出 `AnalysisError` | `.cache/p2-6-build-logs/stack-closure-run-2.log` | `EADED7B10FCF5D2F761F0778A74948ED231210849DF72A1B75B92C78D5013613` |
| 3 | 修正真实 LZMA 对象后，优化克隆 `LzmaDec_AllocateProbs2.isra.0` 未与 `.su` 基函数条目闭合，脚本按“项目函数缺少 `.su`”抛出 `AnalysisError` | `.cache/p2-6-build-logs/stack-closure-run-3.log` | `2A9A62E91FEB2DAEA7C7F56226AD5FA025DC1381D2AD9D92537DD08D70A2EEC7` |

三次失败均属于新验证 harness 的真实 ELF/map/`.su` 关联问题，不等价于“实测栈峰值
超过 `8192B`”，也不允许据此把 C3/C13/C16 判为产品失败；它们继续保持
`EVIDENCE_GAP`。但是冻结停止条件明确规定“同一验证项连续失败三次”后必须落盘、
置卡为“阻塞”并停止，未为 harness 解析错误提供例外，因此实现会话没有执行第四次。

### 16.3 停止点与设备状态

- 尚未烧录本轮 test-only fresh App，未执行 startup 即时扫描，也未生成
  `.cache/p2-6-gdb/startup-stack-scan-summary.log`。
- 设备仍保持 §13.2 已验证的 `P2_6_TEST_ENABLE=OFF` production `v2.8.0`，本轮没有
  改写设备 Flash。
- 未触发 `>8192B`、guard 损坏、workspace `>40960B`、sbrk/LVGL required 分配
  非零或冻结门槛修改等产品停止条件；本次唯一触发面是验证项连续三次失败。
- 后续动作必须由非实现协调会话按冻结治理裁定；当前实现 agent 不自行重置失败计数、
  换验证路线、放宽判据或继续验收。

## 17. P2-6 阻塞裁定与受控恢复授权（2026-08-19）

### 17.1 裁定

**结果：`AUTHORIZED_RESUME`。** 本记录由非实现、非独立验收的 P2-6 阻塞裁定会话
形成；本会话不实现 P3/P4、不配置或部署 Cloudflare、不执行第四次验证，也不创建
`docs/acceptance-contracts/P2-6-v1.contract.json`。

实现会话正确履行了冻结要求：同一验证项
`tests/ota/test_p2_6_stack_closure.py` 已连续失败三次，且三次均发生在
`setUpClass` 的证据解析阶段；实现 agent 没有重新解释失败、重置计数或执行第四次，
而是落盘停止记录并将卡置为“阻塞”。因此，“三次失败后停止”条件**确实发生**，旧轮次
已按规则终止；本裁定不是对旧轮次的回溯豁免。

### 17.2 裁定依据

1. 第一次失败是 `function_key()` 对 objdump 的
   `(anonymous namespace)::...` 名称产生空键并取 `[-1]`；这是符号规范化健壮性缺陷。
2. 第二次失败是 harness 使用 `Libraries/OTA/LzmaDec.c.obj` 过滤函数，而真实
   map/对象路径为 `bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c.obj`；这是对象
   归属过滤缺陷。
3. 第三次失败是 ELF 中的 `LzmaDec_AllocateProbs2.isra.0` 未与真实 `.su` 中的
   `LzmaDec_AllocateProbs2.isra` 条目建立关联；这是优化克隆后缀映射缺陷。
4. 三份原始日志均显示 `setUpClass` 异常、`Ran 0 tests`，没有进入 C3/C13/C16
   产品断言；现有证据没有 `>8192B` 栈峰值、guard 损坏、`>40960B` workspace、
   required `sbrk`/TLSF 分配非零或必须修改冻结数字的结论。
5. 静态闭环仍可按冻结 §4.9-E 路线 (a) 继续：生产 ELF 实际调用图最大路径的
   `.su` 求和，加上最坏中断/异常嵌套预算。修复仅需位于 §1.1 已允许的
   `tests/ota/` 证据/回归代码；不需要改变路线、判据、`8192B`/`40960B`/`16KiB`
   数字、产品语义或任何冻结合同。

### 17.3 新验证轮次边界

- 旧轮次的三次失败计数保留为历史事实，不得由实现 agent 自行重置或与新轮次混算。
- 仅授权**一个**新的、受控的实现验证轮次；同一验证项最多执行 **三次**。
- 第一次正式执行前，必须先完成一次不运行验证项的只读/静态修正审查，并一次性
  处理以下三类已知问题：
  - 匿名命名空间与空键：规范化必须对空前缀/无可提取 token fail-closed，不能再
    对空列表索引；保留 C++ 运算符、模板和 clone 后缀的可审计键规则。
  - LZMA 归属：从当前真实 map 的对象名/源路径解析并选择对象，不能写死错误的
    `Libraries/OTA/LzmaDec.c.obj` 后缀；对象选择不唯一或找不到时必须明确失败。
  - 优化克隆与 `.su`：对 `.isra.0`、`.constprop.0`、`.part.0` 等 ELF 标签与
    `.su` 基函数条目建立明确映射（例如去除 GCC 克隆实例号后再按同源 source/object
    约束匹配）；映射不唯一、跨源或无基函数时必须 fail-closed，并在报告中列出映射。
- 上述修正只能改冻结 §1.1 允许的测试/证据代码；不得修改生产源码、冻结提示词、
  冻结门槛、静态闭环路线、二进制合同或创建验收合同。
- 新轮次每次执行都必须保存原始日志和 SHA-256；若再次命中同一验证项三次，立即
  停止并重新请求非实现协调裁定，不得第四次执行或自行换路线。

### 17.4 可直接交给实现 agent 的恢复提示词

```text
你是 E-Track 的 P2-6 实现 agent。非实现阻塞裁定已给出 AUTHORIZED_RESUME，现只
授权一个新的、受控的静态栈闭环实现验证轮次。

先完整阅读 AGENTS.md、PLAN-OTA-EXEC.md 的 P2-6 卡/§9/§10、冻结提示词
docs/ota-prompts/prompt-P2-6-implementation.md 的 §0.2/§1.1/§4.9-D/E/§6，以及
docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md 的 §12-§17。

旧轮次事实不可改写：tests/ota/test_p2_6_stack_closure.py 已连续失败三次，旧轮次
已按冻结规则终止。不得重跑旧轮次、不得把旧失败改判为产品 FAIL、不得把旧计数清零
后冒充同一轮继续。新轮次对同一验证项最多正式执行三次；每次保存原始日志和 SHA-256，
第三次仍失败必须立即停止并等待新的非实现协调裁定，禁止第四次。

第一次正式执行前，先只读检查真实 ELF/map/.su，并一次性修正三类已知 harness
关联问题。这个静态准备阶段不得运行 test_p2_6_stack_closure.py：

1. 匿名命名空间/空键：function_key 或等价规范化逻辑不得对空列表取索引；无可提取
   token 时 fail-closed；保留 operator、模板和 GCC clone 后缀的可审计键规则。
2. LZMA 对象归属：从当前真实 map 的对象名或源路径解析 LZMA 函数对象，不得写死
   Libraries/OTA/LzmaDec.c.obj。当前产物真实对象为
   bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c.obj；找不到或不唯一时明确失败并
   列出候选。
3. 优化克隆/.su 关联：将 ELF 的 .isra.0/.constprop.0/.part.0 等实例与同源 .su
   基函数条目建立明确映射。当前决定性例子是 ELF 的
   LzmaDec_AllocateProbs2.isra.0 对应 .su 的 LzmaDec_AllocateProbs2.isra。
   必须同时约束 source/object；映射不唯一、跨源或缺条目时 fail-closed，并在输出
   报告中列出所有实际采用的克隆映射。

修正范围仅限冻结 §1.1 已允许的 tests/ota P2-6 测试/证据代码，以及
PLAN-OTA-EXEC.md 和实现证据文档的状态/日志回填。不得修改生产源码、冻结提示词、
冻结数字（8192B 栈、40960B 池、16KiB 字典）、C3 的 §4.9-E 静态闭环路线、产品
语义或二进制合同；不得创建 docs/acceptance-contracts/P2-6-v1.contract.json；不得
执行 P3/P4、Cloudflare、独立验收、commit、push、merge、rebase 或 stash。

静态准备完成并在证据文档列出三类处理结论后，才可开始新轮次第一次正式执行。可按
AGENTS.md 在项目内准备该验证项所需的既有 P2-6 运行态证据，但不得借准备动作改变产品
实现或冻结路线。若 harness 通过解析阶段，继续按冻结路线验证生产 ELF 调用图最大路径
.su 求和与最坏中断/异常预算；解析通过不等于产品 PASS，C3/C13/C16 必须按原判据
分别给出实际证据、PRODUCT_FAIL、HARNESS_FAIL 或 EVIDENCE_GAP。

所有主动输出、日志、缓存和临时文件必须位于 D:\github\my\E-Track 内。结束前回写
P2-6 状态、实现证据和 PLAN-OTA-EXEC.md §10，并报告是否发生任何项目外写入。
```

### 17.5 文件与边界审计

本裁定只修改了 `PLAN-OTA-EXEC.md` 与本证据文档；用户列出的六个无关未跟踪文件
保持原样，未创建验收合同，未执行提交或远端操作。除实现会话先前已记录的
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 时间变化外，本裁定没有发现或
产生新的项目外写入；该既有项目外路径未被本裁定修改、恢复、移动或清理。

## 18. AUTHORIZED_RESUME 新轮次静态准备（2026-08-19）

### 18.1 轮次边界

本节承接 §17 的非实现裁定，只执行新轮次第一次正式验证之前的静态准备。旧轮次
三次失败和 §16 停止结论保持原样；没有重跑旧日志、没有把旧失败改判为产品失败。
截至本节落盘，新的受控轮次对
`tests/ota/test_p2_6_stack_closure.py` 的正式执行次数仍为 **0/3**。

本阶段只修改 `tests/ota/test_p2_6_stack_closure.py` 的证据关联逻辑，没有修改生产
源码、冻结提示词、`8192B`/`40960B`/`16KiB` 数字、§4.9-E 静态闭合路线或二进制
合同。

### 18.2 三类已知关联问题的处理结论

1. **匿名命名空间/空键**：新增可审计 `FunctionIdentity`。将 objdump 的
   `(anonymous namespace)::` 与 `.su` 的 `{anonymous}::` 归一；从最后一个顶层
   参数列表反向提取 callable，保留模板内容和 `operator=`、`operator new`、
   `operator()` 等运算符名称；`.isra`/`.constprop`/`.part` 的 family 与实例后缀
   单独保留。空字符串、括号不平衡、`)`、`cpp)` 或无有效 callable 均不再索引空
   列表，而是 fail-closed。全表扫描时无关异常 `.su` 条目进入
   `invalid_su_identities` 审计；若实际闭合路径需要该条目，`frame()` 明确失败。
2. **LZMA 对象归属**：删除 LZMA 对象路径常量。每个当前真实构型均从 map 中
   `LzmaDec_Allocate` 与 `LzmaDec_FreeProbs` 的对象候选求唯一共同对象，再以该对象
   选择 `LzmaDec_AllocateProbs2`；找不到或不唯一时错误中列出逐函数候选与共同集合。
   当前 production ELF 的唯一对象为
   `CMakeFiles/X_Track_App_GCC.dir/D_/github/my/E-Track/bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c.obj`。
3. **优化 clone 与 `.su`**：每个 `.su` 文件先由其相对构建路径精确还原 `.obj`，
   再用 `compile_commands.json` 将对象绑定到编译源。ELF clone 只在同一 map 对象、
   同一编译源和同一 callable key 中关联；优先要求 clone family 精确一致，缺少带号
   实例时只允许唯一基条目，映射不唯一、跨对象、跨编译源或缺条目均 fail-closed。
   所有实际采用映射将写入 `stack-closure.json` 的 `clone_mappings`，包含 ELF
   地址/函数/clone、map 对象、编译源、`.su` 文件/对象/源/行号/函数/字节数。

决定性关联已经静态核实：ELF
`0x0804B06E LzmaDec_AllocateProbs2.isra.0` 与上述 map 对象一致，对应同对象 `.su`
的 `LzmaDec.c:1335 LzmaDec_AllocateProbs2.isra`，静态帧 `16B`、qualifier=`static`。

### 18.3 静态审计证据

没有加载测试模块、没有启动 unittest。仅执行 AST 语法检查和独立只读解析真实
ELF/map/`compile_commands.json`/`.su`，原始日志：

- 路径：`.cache/p2-6-build-logs/stack-closure-static-prep.log`
- 大小：`4131B`，`27` 行
- SHA-256：`5CF97000C297C2A115FDF6D63224F1DA9B2CAFE97B4BEC31DC278072C8B3300A`

关键结果：`AST_PARSE=PASS`；解析 `2755` 个 ELF 函数符号和 `8298` 个 map 输入范围；
LZMA 两个锚点各只有一个候选且共同对象唯一；LZMA clone 的对象、编译源和 `.su`
条目一致；production `.su` 全表识别出 `21` 个真实异常 identity 并单独审计；匿名
命名空间、`operator=`、`operator()`、模板 clone 和空 identity 五类独立样例均通过；
末行 `STATIC_PREPARATION_AUDIT=PASS`。

### 18.4 正式执行前剩余准备

startup 后立即扫描证据仍未生成，路径
`.cache/p2-6-gdb/startup-stack-scan-summary.log` 仍缺失；设备仍保持 §13.2 已验证的
production v2.8.0。本轮下一步是使用既有 test-only fresh App 在项目内完成受控
startup 即时扫描并生成冻结格式摘要，之后才允许执行新轮次第 1 次正式验证。

## 19. AUTHORIZED_RESUME 新轮次停止与生产恢复（2026-08-20）

### 19.1 轮次边界与静态准备

§16 的旧轮次三次失败保持原样，不与本轮计数混算。§18.4 是执行前快照；本节
记录其后的事实：startup 立即扫描已在 test-only 构型完成，摘要为
`observed=80 guard=1 helper_static=72 stack_total=8192`，文件为
`.cache/p2-6-gdb/startup-stack-scan-summary.log`，SHA-256
`DE36B3085AC5DF36927147505B2D1677813CC15C80C58E4D803CB88D5F8EC9EF`。

静态准备只修改冻结 §1.1 允许的 `tests/ota/test_p2_6_stack_closure.py`，并通过
AST 解析；三类已知关联问题的处理结论仍为：匿名命名空间/空键 fail-closed、LZMA
对象从真实 map 唯一解析、ELF clone 与同对象同源 `.su` 条目明确关联。静态准备原始
日志 `.cache/p2-6-build-logs/stack-closure-static-prep.log` 的 SHA-256 为
`5CF97000C297C2A115FDF6D63224F1DA9B2CAFE97B4BEC31DC278072C8B3300A`。

### 19.2 正式执行 3/3 与分类

本轮同一验证项正式执行次数为 **3/3**，三次均在产品断言前退出，均分类为
`HARNESS_FAIL`，不得据此判定产品门槛失败：

| 次数 | 现象 | 原始日志 | SHA-256 |
|---:|---|---|---|
| 1 | `class_init_handler` 的 USB MSC 对象归属未解析唯一 | `.cache/p2-6-build-logs/stack-closure-resume-run-1.log` | `0FC89E52B914EEEBBD64F9C7A9C103F58CB5BE8032559AD772FA4030C2AE4B49` |
| 2 | `ButtonEvent::EventMonitor` 与 `TonePlayer::Update` 的间接调用点未闭合 | `.cache/p2-6-build-logs/stack-closure-resume-run-2.log` | `0E6150CFCBE3162764E26E731F47AEF827E6C1634B8A367F1A038730A7C4702D` |
| 3 | test ELF 中 `P2_6_StartupStackScanProbe` 未能按对象唯一解析，`Ran 0 tests` | `.cache/p2-6-build-logs/stack-closure-resume-run-3.log` | `F560A7CFE99CA88E0F7A7B51F20B6C854EAD80FF3B3FCEF9DC8DF0857B830240` |

第三次仍失败后立即停止；没有第四次执行、没有重置计数、没有修改生产源码或冻结
数字。第三次的 PowerShell 启动包装首次被宿主策略拒绝，但 Python 未启动且未生成
日志，不计入正式执行；随后同一正式命令成功运行并生成上表日志。

### 19.3 静态递归环与 C3/C13/C16

在正式执行收尾前的独立静态审计中，生产 ELF 的启用 IRQ67（priority 1，handler
`OTGFS1_IRQHandler`）发现无界调用图环：

`sdio_command_data_send -> sd_init -> speed_change -> sd_switch -> sdio_command_data_send`

环节点及 `.su` 静态帧为 `40B/40B/72B/40B`，均来自同一
`Platform/Core/at32_sdio.c` 对象；完整节点、地址、边来源和 IRQ 启用证据见
`.cache/p2-6-build-logs/stack-closure-recursion-audit.log`，SHA-256
`D17CB67A3CED7AC439761EAED188E03EEBFCDF03AC09D95A6410E98B288DBF21`。
静态最终汇总为
`.cache/p2-6-build-logs/stack-closure-resume-run-3-static-final.log`（SHA-256
`14EABA973C697EBAD9AFC2FE5B729A8591C24190DF74C13318D914EEBA6DC67B`）及同名
`.json`（SHA-256 `8F2EF41C7912AA3D4A79A1D8F44D1F2FFBC53F4DC02880F4714392792B37D2D6`）。
该汇总显示 production/test FULL/PATCH 核心路径分别 `1592B/1720B`，resolver
`PASS`，但 IRQ67 为 `EVIDENCE_GAP`；因此 C3、C13、C16 均为
`EVIDENCE_GAP`，没有伪造 IRQ67 最大路径或有效 8192B 预算，也未将递归环改判为
`PRODUCT_FAIL`。正式第三次因 test ELF helper 解析失败，不能把静态汇总提升为产品
PASS。

### 19.4 生产恢复与边界审计

使用项目内缓存的 production v2.8.0 BIN（长度 `599092B`，烧录地址 `0x08010000`）
完成回刷和验证：

- BIN：`.cache/p2-6-hardware-20260819/X-Track-App-GCC-production-v2.8.0.finalized.bin`
- BIN SHA-256：`C601312045E4B78B2F25795CF81FA6C4153DB0BBED1F89541DEB080CF13C7F48`
- 恢复日志：`.cache/p2-6-hardware-20260819/restore-production-v2.8.0-20260820.log`
- 恢复日志 SHA-256：`1CF426303A1C476ED17B7254AA8D507220600F46E4F5946E1871F3F2174F035D`
- J-Link 输出：`Verify successful`，随后 reset/run 完成。

本轮主动选择的日志、缓存、临时目录和证据均位于项目根
`D:\github\my\E-Track` 内。项目外历史文件
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`（986B，SHA-256
`F29B1C7215E4B38F1F782AF36A45D0D213A2EE7E0EF0287D04C98A1982933832`）未被本轮修改、
恢复、移动或清理；收尾检查未发现新的项目外文件写入。J-Link 恢复时将
`USERPROFILE` 指向项目根，Windows 辅助进程因此在项目内短暂生成未跟踪
`D:\github\my\E-Track\AppData` profile 影子目录；收尾审计确认该目录创建于本轮、
无 reparse point 且严格位于项目根后已完整删除，最终工作区不再含该目录。用户列出的
六个无关未跟踪文件仍保持原路径和状态；未创建
`docs/acceptance-contracts/P2-6-v1.contract.json`，未执行
commit/push/merge/rebase/stash/独立验收，未触碰 P3/P4 或 Cloudflare。

### 19.5 当前状态

P2-6 按冻结停止条件置为 **阻塞**，等待新的非实现协调裁定。现有数字和产品语义
均保持冻结：workspace `40960B`、OTA 栈 `8192B`、字典 `16KiB`；本轮没有足够证据
宣告 C3/C13/C16 产品通过，也没有证据宣告产品超门槛。

## 20. P2-6A 前置整改闭合（2026-08-20）

### 20.1 授权与边界

用户在 P2-6 已因新受控轮次 `3/3` 耗尽而阻塞后，明确授权本会话执行独立的
P2-6A 前置整改：处理 SDIO 无界递归环，并把 stack harness 的静态解析/聚合能力
收敛到正式执行前可一次性审计的状态。本节不重开 P2-6 正式轮次，不重置 §19 的
`3/3`，也不构成独立验收。

本节没有运行 `tests/ota/test_p2_6_stack_closure.py`，没有第四次或新的正式执行；
没有修改冻结提示词、`8192B`/`40960B`/`16KiB` 数字、§4.9-E 静态闭环路线、
二进制合同或产品门槛。

### 20.2 整改内容

1. `MDK-ARM_F435/Platform/Core/at32_sdio.c`：删除
   `sdio_command_data_send()` 三个数据超时分支中的直接 `sd_init()`，新增
   `sdio_transfer_recover_timeout()`。恢复只在 `sd_block_read`、
   `sd_mult_blocks_read`、`sd_block_write`、`sd_mult_blocks_write`、
   `mmc_stream_read`、`mmc_stream_write` 六个外层传输边界各出现一次；初始化内部的
   `sd_switch()` 仍直接调用底层传输。因此原环
   `sdio_command_data_send -> sd_init -> speed_change -> sd_switch ->
   sdio_command_data_send` 被结构性切断，且同步 CMD12 路线未改变。
2. `MDK-ARM_F435/cmake-generated/CMakeLists.txt`：生产与
   `P2_6_TEST_ENABLE=1` 两种 App 构型均以 `-fstack-usage` 编译并各自产出 `.su`；
   `P2_6_TEST_ENABLE` 仍只控制 C/C++ 测量插桩、TLSF wrapper 和
   `P2_6_StartupStackScanProbe` 的 test-only 链接保活，没有进入
   `OTA_TEST_LINKER_DEFINES`。
3. `tests/ota/test_p2_6_stack_closure.py`：静态图补齐
   `lv_tlsf_walk_pool -> lv_mem_walker` 的唯一回调解析，并依据真实 TLSF 遍历不变量
   排除 `block_next -> __assert_func` 的不可达断言边；冻结的
   `lv_timer_handler -> onWorkTimer` 回调边被计入已解析集合。正式 unittest 未执行。
4. 新增 `tests/ota/p2_6_stack_preflight.py`，只导入解析器并聚合真实 ELF/map/`.su`、
   compile commands、对象归属、clone 映射、间接调用、调用图循环和构型边界；报告
   固定输出 `formal_test_executed=false`。新增
   `tests/ota/test_sdio_recovery_bounded.py` 锁定恢复边界、raw 调用数、两构型 `.su`
   选项和 test-only 探针保活边界。

### 20.3 构建与静态回归

全部可控输出均定向到项目内 `.cache/p2-6a-*`。production 构型重新配置后对
`X_Track_App_GCC X_Track_Boot` 执行单线程顺序构建，返回 `0`；test 构型重新配置后
相同目标明确返回 `ninja: no work to do.`。构型与产物为：

| 构型 | `.su` | App ELF/BIN | Boot ELF/BIN |
|---|---:|---|---|
| `.cache/p2-6a-cmake-prod-stack` (`P2_6_TEST_ENABLE=OFF`) | `379` 文件 / `4059` 条；`-fstack-usage=true`、test macro=false、LTO=false | `864320B / 599140B`；ELF SHA-256 `8890935D508A446D4AB3B1988A636A03A2289F2E57A3311AB97017BA87EC87AC`；BIN SHA-256 `1E7908CA8E9D7E59A21B2F97AFBB3D9416D7206184F6D2978B885357F588CC54` | `36860B / 14724B`；ELF SHA-256 `D21713CA2C1EFEAC949F8EC0FFDDACAC439FED6BF26F9C65641BEE24464FDABC`；BIN SHA-256 `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| `.cache/p2-6a-cmake-test-stack` (`P2_6_TEST_ENABLE=ON`) | `379` 文件 / `4070` 条；`-fstack-usage=true`、test macro=true、LTO=false | `866372B / 600744B`；ELF SHA-256 `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`；BIN SHA-256 `6078D6009003A75185C2C970FB39F157639824E79A97F8A218A8EBD324439E35` | 与 production Boot 尺寸一致 |

生产构建日志 `.cache/p2-6a-build-logs/prod-build.log` SHA-256 为
`80C9F43BDE4C97D0352BC5D89E1CB8CC176FEEFFCDB61371CA1B70E4725B78F2`；按日志文本
统计 `warning:` token 为 `634`、`error:` token 为 `0`。告警主要为仓库既有的
unused/sign/packed/strict-aliasing、2-byte/4-byte `wchar_t` 混用和 RWX LOAD segment，
未被隐藏为零告警。test 增量构建日志 SHA-256 为
`71AA391EC7D7E291B419A7F40FBA91919E14AC2394AB4E8B66ED126E267D70F6`。

允许执行的静态回归结果：

- `python tests/ota/test_sdio_command_timeouts.py`：
  `SDIO_COMMAND_TIMEOUTS=PASS functions=9`。原始日志
  `.cache/p2-6a-build-logs/sdio-command-timeouts.log`，SHA-256
  `B739E25985378C7B0627C7002AA441EFC37836BB61F01EA60CFBA913B235FCBC`。
- `python tests/ota/test_sdio_recovery_bounded.py`：
  `SDIO_RECOVERY_BOUNDED=PASS outer_transfers=6 raw_calls=8`。原始日志
  `.cache/p2-6a-build-logs/sdio-recovery-bounded.log`，SHA-256
  `7D9FFEA1E7FBEA8C173A075B43114389AB97DAC8A488A3B555D133D98F891CDB`。
- `py_compile`：`test_p2_6_stack_closure.py`、`p2_6_stack_preflight.py`、
  `test_sdio_recovery_bounded.py` 全部通过。

### 20.4 独立 preflight 结果

执行的是独立静态入口，而不是正式 unittest：

`python tests/ota/p2_6_stack_preflight.py --prod-build
.cache/p2-6a-cmake-prod-stack --test-build .cache/p2-6a-cmake-test-stack
--output .cache/p2-6a-stack-preflight`

结果为 `P2_6_STACK_PREFLIGHT=PASS`、`issues=0`、`notes=24`、
`formal_test_executed=false`。报告路径
`.cache/p2-6a-stack-preflight/report.json`，SHA-256
`B9D4E34510B45926F613004895F0CF9C7B62A4A9D225F164720FB049B2296667`；原始控制台日志
`.cache/p2-6a-build-logs/stack-preflight.log`，SHA-256
`9B544AEF112BF1CA5F50BEF79443881EED161A22F4F21869131D3F4E95F28008`。

决定性静态结论：

- production FULL/PATCH、SysTick 和运行态 NVIC 日志中全部启用 IRQ 均无未解析间接
  调用、帧映射错误或可达调用图环；IRQ67 `OTGFS1_IRQHandler` 的闭合范围为
  `161` 个可达函数。
- production/test 的 LZMA 唯一对象均解析为
  `bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c.obj`；USB MSC class 对象唯一。
- test ELF 的 `P2_6_StartupStackScanProbe` 位于 `0x08043804`，唯一归属
  `USER/HAL/HAL_OTA_Package.cpp.obj`；该探针及 `p2_6_measure_begin/end` 三个测量根
  均静态闭合。
- production/test 构型边界符合冻结要求：两者均有 `.su`，production 无 test macro，
  test 有 `P2_6_TEST_ENABLE=1`，两者均无 LTO。

### 20.5 状态裁定

在本节形成时，P2-6A 前置整改完成，但该结果不能追溯改写 §19 的第三次
`HARNESS_FAIL`，不能把正式计数从 `3/3` 清零，也不能由实现会话自行授权新的正式
执行。随后由本证据文档 §21 记录的同一非实现阻塞裁定会话完成复核并另行授权
`P2-6-R3`；本节的历史结论不限制 §21 的新裁定。

本节未创建 `docs/acceptance-contracts/P2-6-v1.contract.json`，未执行独立验收、
烧录、P3/P4、Cloudflare、commit、push、merge、rebase 或 stash。

## 21. P2-6-R3 非实现阻塞裁定（2026-08-20）

### 21.1 裁定结果

**AUTHORIZED_RESUME**。

本节由非实现阻塞裁定 agent 在同一会话中完成，不是把任务转交给另一个裁定会话。
P2-6 从“阻塞”恢复为“进行中”；旧轮次的三次失败仍是不可变历史，新授权轮次编号
为 `P2-6-R3`，不与旧轮次混算。

### 21.2 依据与边界审查

同时满足授权条件：

1. 旧轮次三次均在 `setUpClass`/证据解析阶段失败，三份日志均为 `Ran 0 tests`，
   没有进入 C3/C13/C16 产品断言；已知原因分别为解析键、LZMA 对象归属、优化
   clone 与 `.su` 关联缺陷。
2. 没有 `>8192B` 栈峰值、guard 损坏、`>40960B` workspace、required `sbrk`/
   TLSF 增量非零或必须改变冻结数字的证据。
3. P2-6A 已在用户明确授权的独立前置整改中闭合生产 IRQ67 的无界 SDIO 递归环，
   并使生产/test 两构型的真实 ELF/map/`.su`/间接调用聚合 preflight 收敛为
   `issues=0`。这项已完成的生产修正是新轮次的冻结输入；本授权不允许新轮次再
   修改生产源码。
4. P2-6A 没有改变静态闭环路线、`8192B`/`40960B`/`16KiB` 数字、产品语义、冻结
   提示词或二进制合同。新轮次只验证当前候选，不以额外修正来绕过停止条件。

### 21.3 新轮次硬边界

- 新轮次只允许同一验证项 `tests/ota/test_p2_6_stack_closure.py` 最多执行三次；
  第一次正式执行前只读核对 §20 的 preflight 报告、哈希和构型路径，不再重复旧的
  三类解析修正。
- 第一次正式执行成功并取得完整产品证据后立即停止，不为“凑满三次”重复执行。
- 任一次出现真实产品门槛失败、guard 损坏、栈峰值超 `8192B`、workspace 超
  `40960B`、required 分配增量非零，立即停止并按冻结分类记录，不得用 harness
  修补掩盖产品结果。
- 任一次出现新的未定界递归、未知间接调用、跨对象/跨源映射或其他冻结提示词未
  列失效模式，立即停止并重新请求非实现裁定；不得删边、假设有限深度或拼凑
  静态/运行期证据。
- 允许的修正仅限 `tests/ota/` 的直接证据/解析代码和本看板/证据文档的回填；不得
  修改生产源码、冻结提示词、冻结门槛、静态路线、二进制合同，不得创建验收合同。
- 每次正式执行必须把完整原始输出和 SHA-256 写入项目内 `.cache/p2-6r3-*`；
  任何启动正式验证进程均计为一次执行（即使 `Ran 0 tests`）；总执行数达到 `3/3`
  时无条件停止并等待新的非实现裁定，禁止第四次。
- 本轮不是独立验收，不得派独立验收 agent，不得执行 P3/P4 或 Cloudflare，不得
  commit、push、merge、rebase 或 stash。

### 21.4 可直接交给 P2-6 实现 agent 的恢复提示词

以下提示词是本裁定的完整执行边界：

    你是 E-Track 项目的 P2-6 实现 agent。非实现阻塞裁定已在同一会话给出
    AUTHORIZED_RESUME，现授权新的受控正式验证轮次 `P2-6-R3`。

    先只读阅读 AGENTS.md、PLAN-OTA-EXEC.md 的 P2-6 卡/§9/§10、
    docs/ota-prompts/prompt-P2-6-implementation.md 的 §0.2/§1.1/§4.9-D/E/§6，
    以及本证据文档 §12-§21。旧轮次事实不可改写：旧
    tests/ota/test_p2_6_stack_closure.py 已连续失败三次并按规则终止；不得重跑旧
    日志、不得把旧失败改判为产品 FAIL、不得把旧 `3/3` 清零后冒充新轮次。

    新轮次边界：同一验证项最多正式执行三次；任何启动正式验证进程均计数，即使
    `Ran 0 tests`。第一次正式执行前只做只读/静态核对，
    不运行正式验证项；核对以下固定输入：
    - production build: .cache/p2-6a-cmake-prod-stack
    - test build: .cache/p2-6a-cmake-test-stack
    - preflight report: .cache/p2-6a-stack-preflight/report.json
    - preflight SHA-256: B9D4E34510B45926F613004895F0CF9C7B62A4A9D225F164720FB049B2296667
    - report 必须显示 issue_count=0、formal_test_executed=false；两构型必须各有
      `.su`，生产构型不得有 `P2_6_TEST_ENABLE=1`，测试构型必须有该宏，且不得有
      `-flto`。

    P2-6A 的生产 SDIO 修正和静态解析修正已经冻结为本轮输入。不得再修改
    MDK-ARM_F435/Platform/Core/at32_sdio.c、生产 linker/CMake 语义、冻结提示词、
    8192B/40960B/16KiB 数字、§4.9-E 路线、产品语义或二进制合同。不得创建
    docs/acceptance-contracts/P2-6-v1.contract.json。

    完成只读核对后，按冻结提示词执行同一验证项：
    tests/ota/test_p2_6_stack_closure.py
    显式把 P2_6_PROD_STACK_BUILD 和 P2_6_TEST_STACK_BUILD 指向上述两个 build，
    并把所有 stdout/stderr、临时文件和运行日志定向到
    D:\github\my\E-Track\.cache\p2-6r3-build-logs（不得使用系统 TEMP 或项目外
    输出）。每次执行前记录轮次序号；每次执行后保存原始日志并计算 SHA-256。

    分类与停止：
    - 若首次完整通过并得到产品证据，立即停止，不重复执行；按冻结判据分别记录
      C3/C13/C16 和其余 C 项，解析通过不等于产品 PASS。
    - 若在产品断言前发生可定界 HARNESS_FAIL，可在 `tests/ota/` 内做一次直接、最小、
      可审计的证据解析修正后继续计数；不得修改生产源码或冻结输入。修正前记录
      原始日志、原因和 diff；修正无法定界时立即停止并请求裁定。
    - 若出现 PRODUCT_FAIL、guard 损坏、超门槛、未知递归/间接调用、跨源映射或
      新失效模式，立即停止，不得以重跑掩盖。
    - 第三次正式执行无论结果如何立即停止；禁止第四次、禁止自行换路线或重置计数。

    本轮不是独立验收。不得派验收 agent，不得执行 P3/P4、Cloudflare、commit、push、
    merge、rebase 或 stash。结束前回写 PLAN-OTA-EXEC.md §9/§10 和本证据文档，明确
    P2-6 当前状态、每次日志 SHA-256、C3/C13/C16 分类，以及是否发生项目外写入。

### 21.5 裁定后的状态与审计

P2-6 当前状态为**进行中**，新轮次上限为 `3`；旧轮次 `3/3` 保留为历史，不计入
`P2-6-R3`。本裁定没有运行正式 stack-closure 测试，没有第四次执行，没有独立验收，
没有创建验收合同，没有远端操作。

本裁定只追加/更新 `PLAN-OTA-EXEC.md` 与本证据文档。六个历史未跟踪文件保持原样；
本裁定主动选择的写入目标均在 `D:\github\my\E-Track` 内，未发现新的项目外写入。

## 22. P2-6-R3 正式静态闭环验证（2026-08-20）

### 22.1 写入预检与冻结输入核对

本轮活动项目根经 `git rev-parse --show-toplevel` 规范化为
`D:\github\my\E-Track`，分支为 `p2-6-implementation-20260819`，HEAD 与
`origin/main` 均为 `99173123cae8c487b86efa8a4eecbbe73b1bb512`。获准输出目录和
回填文件逐项转换为绝对路径后均位于项目根内，现存父链未发现 reparse point；
`TEMP`、`TMP`、`TMPDIR`、Python cache 和测试临时目录均覆盖到项目内 `.cache`。

第一次正式执行前的只读核对全部通过：

- production build：`.cache/p2-6a-cmake-prod-stack`
- test build：`.cache/p2-6a-cmake-test-stack`
- preflight：`.cache/p2-6a-stack-preflight/report.json`
- preflight SHA-256：
  `B9D4E34510B45926F613004895F0CF9C7B62A4A9D225F164720FB049B2296667`
- `issue_count=0`、`formal_test_executed=false`、`notes=24`
- production/test 均有 `379` 个 `.su` 文件；production test macro=`OFF`，test=`ON`
- 两构型均无 `-flto`
- LZMA 对象归属为
  `bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c.obj`
- `LzmaDec_AllocateProbs2.isra.0` 唯一映射到同对象、同编译源的
  `LzmaDec_AllocateProbs2.isra` `.su` 条目，静态帧 `16B`
- startup 摘要严格为
  `P2_6_STARTUP_SCAN observed=80 guard=1 helper_static=72 stack_total=8192`

### 22.2 R3 第一次正式执行

正式 Python 进程已启动，因此 P2-6-R3 计数为 `1/3`。显式输入为：

- `P2_6_PROD_STACK_BUILD=.cache/p2-6a-cmake-prod-stack`
- `P2_6_TEST_STACK_BUILD=.cache/p2-6a-cmake-test-stack`
- `P2_6_NVIC_LOG=.cache/p2-6-jlink-gdb/nvic-runtime-production.log`
- `P2_6_STARTUP_SCAN_LOG=.cache/p2-6-gdb/startup-stack-scan-summary.log`

执行结果为 `Ran 7 tests`、`6 PASS / 1 FAIL / 0 SKIP`、exit=`1`。唯一失败：

`test_measurement_call_overhead_is_quantified` 在
`tests/ota/test_p2_6_stack_closure.py:1432` 断言期望 `16`、实际 `40`。

证据文件：

| 文件 | SHA-256 |
|---|---|
| `.cache/p2-6r3-build-logs/run-1.log` | `92ABB7981AC667EDC5EE8C59C492A20526F898DDE63BA721E3867602E62DFD3A` |
| `.cache/p2-6r3-build-logs/stack-closure-run-1.json` | `E3527347C1191E96509D170DF2DD172AA66E9C73BE3E420921BF2F8BBEF37DBF` |
| `.cache/p2-6r3-build-logs/run-1.meta.txt` | `199B0153C7507A0BE85CE599C8FAFF00F282882B9370D6C0164627F0363E9107` |

归档 JSON 已生成完整静态结果：FULL/PATCH 线程峰值分别为 `1904B/2048B`；
运行态 NVIC 最坏中断/异常预算为 `768B`；静态总上界为
`2048 + 768 = 2816B <= 8192B`，余量 `5376B`。中断证据缺口为空，未出现未知
递归、未知间接调用、跨对象/跨源 clone 映射或 guard 损坏。

### 22.3 失败分类与停止决定

归档 JSON 中 `40B` 的路径是完整测量函数的最深静态路径：begin=`32B`，end=`40B`；
决定性 end 路径为
`p2_6_measure_end(8B) -> lv_mem_monitor(8B) -> lv_tlsf_walk_pool(16B) ->
block_next(8B)`。startup 独立探针为 `72B`，运行观测为 `80B`，guard=`1`。

冻结提示词要求扫描调用自身开销必须被量化，但没有把 `16B` 冻结为协议门槛。
因此 `40 != 16` 是测试内部把完整测量函数路径与历史精确观测强绑定造成的有限、
可审计 `HARNESS_FAIL`，不是 `>8192B`、guard 损坏或其他 `PRODUCT_FAIL`。同时，本次
已经完成全部 7 个 unittest 并写出完整产品静态结果；P2-6-R3 规则要求此时立即停止，
而测试修正规则只授权产品断言前的有限解析失败。因此本轮没有修改
`tests/ota/test_p2_6_stack_closure.py`，没有启动 R3 第 2/3 次，也没有用重跑掩盖
exit=`1`。

冻结分类如下：

| 判据 | 分类 | 依据 |
|---|---|---|
| P2-6-C3 | `EVIDENCE_GAP` | 静态数值 `2816B/8192B` 本身达标且 guard 无损坏证据，但 C13 前置未由正式 runner 干净通过，故不得直接形成产品 PASS |
| P2-6-C13 | `HARNESS_FAIL` | 测量开销已量化为完整函数路径 `40B`，但 harness 的非契约精确 `16B` 断言失败 |
| P2-6-C16 | `PASS` | production/test `.su`、对象与 clone 映射、调用图、实际 NVIC 中断预算和共享布局均闭合，无迁移性证据缺口 |

其他 C 项沿用既有证据矩阵：C1/C2、C4-C7、C14 仍为 `NOT_OBSERVED`；C8-C12、
C15 的既有静态/宿主结果不变。本轮没有真实 SD FULL/PATCH OTA 窗口，因此不能把
静态栈闭环替代 workspace、sbrk、TLSF、异常退出和 LiveMap 恢复真机证据。

### 22.4 状态、边界与文件系统审计

P2-6 保持 **进行中**，没有标记完成，也没有因产品超限置阻塞。P2-6-R3 在 `1/3`
即按“完整结果后停止”结束；未执行第 2、3 或第 4 次正式验证。未修改生产源码、
冻结提示词、冻结数字、静态路线、二进制合同或
`docs/acceptance-contracts/P2-6-v1.contract.json`；未执行独立验收、P3/P4、
Cloudflare、commit、push、merge、rebase 或 stash。

本轮主动输出仅位于项目内 `.cache/p2-6r3-build-logs`、
`.cache/p2-6-stack-closure`、`.cache/p2-6-test-tmp`、`.cache/p2-6-pycache`，以及本证据
文档和 `PLAN-OTA-EXEC.md`。六个指定历史未跟踪文件未修改、删除、移动或提交。
最终审计未发现本轮主动选择的项目外写入。

## 23. P2-6-R3-1 非实现阻塞裁定（2026-08-20）

### 23.1 裁定结果

**`AUTHORIZED_RESUME`。** 本裁定不新开 R4，不重置 P2-6-R3 计数，也不授权继续
修改生产实现。R3-1 保持为已经发生的正式第 `1/3` 次执行；仅授权一次测试侧口径
修正和一次正式 R3-2。即使名义上尚余第三次，本裁定也明确禁止自动执行 R3-3。

实现 agent 在 R3-1 后停止是正确的：该次已经实际运行全部 7 个 unittest 并产生完整
静态报告，符合 §21.3 的“取得完整结果后立即停止”边界。当前恢复授权来自新的
非实现裁定，不是实现会话自行忽略停止点。

### 23.2 `40B != 16B` 的准确性质

R3-1 的唯一失败不是产品门槛失败，而是 harness 把两个不同语义的量混为一谈：

1. 冻结提示词 §4.2 要求量化的是 `StackInfo_GetMaxUsageSize()` 执行时，扫描动作本身
   给哨兵观测增加的栈开销。允许的静态方法是读取采集函数的 `sub sp, #N` 序言，
   加上到扫描器的实际调用链最深路径；提示词没有冻结 `16B` 或 `40B` 这个精确数字。
2. 当前 harness 的 `measurement_overhead` 却取
   `maximum_path(p2_6_measure_begin/end)` 的整体最大值。R3-1 报告的 begin=`32B`、
   end=`40B` 来自测量包装函数的所有后续工作；决定性 `40B` 路径是
   `p2_6_measure_end -> lv_mem_monitor -> lv_tlsf_walk_pool -> block_next`。
3. 生产候选源码先在 `p2_6_measure_end()` 开头调用
   `StackInfo_GetMaxUsageSize()` 并保存 `exit_stack_peak`，之后才调用
   `p2_6_measure_mem()/lv_mem_monitor()`。因此后续 `40B` 路径不会反向污染已经保存的
   该次栈峰值，不能把它命名成“扫描调用自身开销”。
4. 当前 test `.su` 显示 `p2_6_measure_begin=16B`、`p2_6_measure_end=8B`、
   `StackInfo_GetMaxUsageSize=0B`。这说明真实扫描点的候选静态增量分别为 `16B/8B`，
   最大候选为 `16B`；但修正后的 harness 必须从真实反汇编/调用点和 `.su` 动态导出，
   不能继续把 `16` 当作不可解释的固定合同值。

所以允许修正的不是机械地把 `assertEqual(..., 16)` 改成 `40`，也不是删除 C13
判据，而是把“扫描点开销”和“整个测量包装函数静态上界”拆成两个可审计量。

### 23.3 唯一允许的修正与执行边界

- 生产源码、P2-6A 产物、CMake/linker/startup、冻结提示词、`8192B`/`40960B`/
  `16KiB`、§4.9-E 静态路线和二进制合同全部保持只读。
- 只允许修改 `tests/ota/test_p2_6_stack_closure.py`，以及回填
  `PLAN-OTA-EXEC.md` 和本证据文档。若必须触及其他文件，立即停止并改判
  `KEEP_BLOCKED`。
- harness 必须分别输出：
  - `stack_scan_overhead`：begin/end 在执行 `StackInfo_GetMaxUsageSize()` 的具体调用点
    上，到扫描器实际调用链的静态增量上界、逐层路径和最大值；
  - `measurement_wrapper_upper_bound`：begin/end 整体函数图的静态最大路径，保留
    R3-1 已观察到的 `32B/40B` 类信息供扰动审计。
- `stack_scan_overhead` 必须依据真实指令顺序定位采样调用点；若同一函数内目标调用
  不唯一、调用点无法归属、存在未知间接边或 `.su` 映射不唯一，必须 fail-closed，
  不得取整个函数最大路径代替。
- 正向断言至少要求扫描点路径可唯一闭合、开销 `>0` 且 `<256B`、扫描点上界不大于
  对应包装函数整体上界，并把实际字节数和路径写进 JSON。禁止再次写死
  `==16` 或 `==40`；startup helper 的 `72B/80B` 独立判据保持不变。
- 正式执行前只允许 AST/语法检查和对当前冻结 ELF/map/`.su` 的只读静态审计；必须
  在证据中先写明两个量的派生路径和预期结果。不得重建、烧录或操作 J-Link。
- 随后只允许启动一次正式 R3-2；进程一旦启动，计数变为 `2/3`。若 7 项完整干净
  通过，立即停止并按报告更新 C3/C13/C16；不得为了重复确认再运行。
- 若 R3-2 有任何失败、错误、跳过、新解析模式、结果不唯一，或修正证明需要改变
  生产/冻结输入，立即将 P2-6 置为“阻塞”，记录 `KEEP_BLOCKED`，禁止 R3-3、R4、
  自动续轮或换验证路线。
- 即使 R3-2 静态闭环通过，C1/C2、C4-C7、C14 仍需真实 SD OTA 窗口证据；在这些
  required 证据补齐前不得创建验收合同或进入独立验收。

### 23.4 可直接交给 P2-6 实现 agent 的恢复提示词

    你是 E-Track 项目的 P2-6 实现 agent。非实现裁定针对 R3-1 的
    `40B != 16B` 给出 `AUTHORIZED_RESUME`，但这是同一 P2-6-R3 内的一次窄授权，
    不是 R4，也不重置计数。R3-1 已正式发生，当前计数固定为 `1/3`。

    先完整只读阅读 AGENTS.md、PLAN-OTA-EXEC.md 的 P2-6 卡/§9/§10、冻结提示词
    docs/ota-prompts/prompt-P2-6-implementation.md 的 §0.2/§1.1/§4.2/§4.8/
    §4.9-D/E/§6，以及实现证据 §20-§23。保留 R3-1 原始日志和哈希：
    .cache/p2-6r3-build-logs/run-1.log
    SHA-256 92ABB7981AC667EDC5EE8C59C492A20526F898DDE63BA721E3867602E62DFD3A
    .cache/p2-6r3-build-logs/stack-closure-run-1.json
    SHA-256 E3527347C1191E96509D170DF2DD172AA66E9C73BE3E420921BF2F8BBEF37DBF

    本次只能修正 tests/ota/test_p2_6_stack_closure.py 的测量开销口径。不得修改任何
    生产源码、P2-6A build、CMake/linker/startup、冻结提示词、8192B/40960B/16KiB
    数字、§4.9-E 路线、产品语义或二进制合同。不得机械把常量 16 改成 40，也不得
    删除、跳过或弱化 C13 测试。

    修正目标是把两个量明确分开：

    1. stack_scan_overhead：只计算 p2_6_measure_begin/end 执行
       StackInfo_GetMaxUsageSize() 的具体采样调用点上，采集包装帧加扫描器实际调用链
       的静态增量。必须依据真实反汇编中的指令顺序定位调用点，并用同对象/同源 .su
       闭合逐层帧；当前候选数据应能解释 begin=16B、end=8B、最大=16B，但这些值必须
       动态导出，不能硬编码。
    2. measurement_wrapper_upper_bound：继续报告 begin/end 整个包装函数调用图的
       静态最大路径；R3-1 的候选是 32B/40B。这个量用于说明测量包装代码的整体扰动，
       不能冒充已经保存的 stack_peak 的扫描开销。

    JSON 必须分别保存两个量的 bytes、begin/end 和完整路径。若采样调用点不唯一、
    指令顺序无法确定、调用链存在未知间接边、对象或 .su 映射不唯一，立即停止并回报
    `KEEP_BLOCKED`，不得猜测。测试正向门禁要求扫描点路径唯一闭合、开销 >0 且
    <256B、扫描点上界不大于对应包装函数整体上界；禁止写死 ==16 或 ==40。
    startup helper 的 72B/80B 判据保持不变。

    任何写入前先按 AGENTS.md 完成项目内写入预检。所有输出只能位于
    D:\github\my\E-Track 内。正式执行前只做 AST/语法检查和对冻结 ELF/map/.su 的
    只读静态审计，并先在证据文档记录实际派生的两组路径；不得重建、烧录或运行
    J-Link。

    然后最多启动一次正式 R3-2，显式继续使用：
    P2_6_PROD_STACK_BUILD=.cache/p2-6a-cmake-prod-stack
    P2_6_TEST_STACK_BUILD=.cache/p2-6a-cmake-test-stack
    P2_6_NVIC_LOG=.cache/p2-6-jlink-gdb/nvic-runtime-production.log
    P2_6_STARTUP_SCAN_LOG=.cache/p2-6-gdb/startup-stack-scan-summary.log
    原始日志和 JSON 归档到项目内 .cache/p2-6r3-build-logs，并计算 SHA-256。

    R3-2 进程一旦启动，计数即为 2/3。若 7 项完整干净通过，立即停止并回填
    C3/C13/C16，不得重复执行。若出现任何 FAIL/ERROR/SKIP、新失效模式、结果不唯一
    或需要修改生产/冻结输入，立即把 P2-6 置为“阻塞”，记录 KEEP_BLOCKED；禁止
    R3-3、R4、自动续轮或换路线。

    即使静态闭环通过，C1/C2、C4-C7、C14 仍缺真实 SD OTA 窗口证据。本轮不得创建
    docs/acceptance-contracts/P2-6-v1.contract.json，不得进入独立验收，不得执行
    P3/P4、Cloudflare、commit、push、merge、rebase 或 stash。结束前回写看板 §9/
    §10 和实现证据，并报告项目外写入审计结果。

### 23.5 状态与文件系统审计

P2-6 保持 **进行中**；R3 计数保持 `1/3`，但授权上限已被本裁定收紧为仅一次
R3-2。此次裁定没有运行测试、构建、烧录、J-Link 或独立验收，没有修改测试或生产
源码，没有创建验收合同，也没有执行 Git 远端操作。

本裁定只修改 `PLAN-OTA-EXEC.md` 与本证据文档。写入前确认唯一活动根为
`D:\github\my\E-Track`；两个目标均为项目内既有文件，并沿用 §22.1 已完成的父链
reparse-point 审计。六个历史未跟踪文件保持原样；未发现本裁定产生项目外写入。

## 24. P2-6-R3-2 测量口径修正与正式执行前静态闭环（2026-08-20）

### 24.1 修正范围、备份与可审计 diff

本窄授权只修改了 `tests/ota/test_p2_6_stack_closure.py` 的测量开销解析和门禁。
生产源码、P2-6A 构建输入、CMake/linker/startup、冻结提示词、冻结数字、产品语义、
二进制合同和验收合同均未修改。修正前文件备份为
`.cache/p2-6r3-build-logs/r3-2-pre-fix-test_p2_6_stack_closure.py`，其 SHA-256 为
`92480BDA4033FCDF06FCDD629D843252125C12F62E13ACC8A027EFAC678AD396`。无索引
修正 diff 保存在 `.cache/p2-6r3-build-logs/r3-2-harness.diff`，长度 `9787` 字节，
SHA-256 为 `7885574E73FE3B441340A774088EBD3CF95C6DF7AFC6F3B6A74F601215E1EF75`。
AST 解析检查通过；正式测试进程在本节写入完成前尚未启动。

### 24.2 采样调用点的真实指令顺序与扫描点上界

修正后的 harness 在 production ELF 的反汇编中枚举包装函数内所有直接 `bl`/`blx`，
按指令地址保留调用顺序，并要求 `StackInfo_GetMaxUsageSize` 目标恰好出现一次。
当前冻结产物得到以下唯一调用点：

| 包装函数 | 唯一采样指令 | 调用序列中位置 | 包装帧 | 扫描器最大闭合帧 | 动态扫描点上界 |
|---|---|---:|---:|---:|---:|
| `p2_6_measure_begin` | `0x08043450: bl 0x08013E2C <StackInfo_GetMaxUsageSize>` | 第 3 个直接调用 | `16B` | `0B` | `16B` |
| `p2_6_measure_end` | `0x080436FE: bl 0x08013E2C <StackInfo_GetMaxUsageSize>` | 第 1 个直接调用 | `8B` | `0B` | `8B` |

两处扫描器调用均唯一，目标地址可归属，调用链无未知间接边或递归；扫描器自身的
`.su` 帧为 `0B`。每一层均通过同对象、同编译源和对应 `.su` 条目闭合：

- begin：`p2_6_measure_begin(16B)` → `StackInfo_GetMaxUsageSize(0B)`，总计 `16B`。
- end：`p2_6_measure_end(8B)` → `StackInfo_GetMaxUsageSize(0B)`，总计 `8B`。

因此动态导出的 `stack_scan_overhead` 为 `max(16B, 8B) = 16B`，不是代码中写死的
常量；JSON 将保存 begin/end 字节数、采样指令及完整 `.su` 审计路径。

### 24.3 整个测量包装函数上界（独立于扫描点）

同一调用图另行计算 `maximum_path`，不把扫描点之后的工作归入扫描开销：

- begin：`p2_6_measure_begin(16B)` 以 tail edge 进入
  `lv_mem_monitor(8B) -> lv_tlsf_walk_pool(16B) -> block_next(8B)`；按 tail-call
  记账为 `max(16B, 8B + 16B + 8B) = 32B`。
- end：`p2_6_measure_end(8B)` → `lv_mem_monitor(8B)` → `lv_tlsf_walk_pool(16B)` →
  `block_next(8B)`，总计 `40B`。

动态导出的 `measurement_wrapper_upper_bound` 为 `max(32B, 40B) = 40B`。该量仅用于
审计完整包装代码的扰动上界；扫描点上界均大于零、低于 `256B`，且分别不超过对应
包装函数上界。startup helper 的独立判据仍保持 `helper_static=72`、
`observed=80`、`stack_total=8192`、`guard=1`。

### 24.4 R3-2 正式执行边界

上述静态审计和证据写入完成后，才允许启动唯一一次 R3-2（计数从 `1/3` 变为 `2/3`）。
正式进程使用冻结的 production/test build 和项目内 TEMP/TMP/Python cache；原始日志、
JSON、退出码和 SHA-256 将归档到 `.cache/p2-6r3-build-logs`。若 7 项完整为
`7 PASS / 0 FAIL / 0 ERROR / 0 SKIP`，立即停止并回填 C3/C13/C16；任何其他结果、
新失效模式、结果不唯一或需要扩大修改范围都按裁定记 `KEEP_BLOCKED`，将 P2-6 置为
“阻塞”，禁止 R3-3、R4 或更换路线。

### 24.5 R3-2 唯一正式执行结果

静态准备和 §24.1-§24.4 的证据写入完成后，正式 Python 进程于
`2026-08-20T03:40:06.4244195Z` 启动，因此 P2-6-R3 计数固定为 `2/3`。本次显式使用：

- `P2_6_PROD_STACK_BUILD=.cache/p2-6a-cmake-prod-stack`
- `P2_6_TEST_STACK_BUILD=.cache/p2-6a-cmake-test-stack`
- `P2_6_NVIC_LOG=.cache/p2-6-jlink-gdb/nvic-runtime-production.log`
- `P2_6_STARTUP_SCAN_LOG=.cache/p2-6-gdb/startup-stack-scan-summary.log`
- `TEMP`、`TMP`、`TMPDIR`、`PYTHONPYCACHEPREFIX` 全部覆盖到项目内 `.cache`

进程于 `2026-08-20T03:40:38.0566154Z` 结束，exit=`0`。原始日志严格为
`Ran 7 tests in 30.469s`、`OK`，即 `7 PASS / 0 FAIL / 0 ERROR / 0 SKIP`；日志中
warning=`0`、error=`0`。按授权取得完整干净结果后立即停止，没有执行 R3-3。

| 证据 | SHA-256 |
|---|---|
| `.cache/p2-6r3-build-logs/run-2.log` | `7E28EC832328E4465AE31E46AEEEE14EFF0B4CDF7AABB4B2528045BC2186B59F` |
| `.cache/p2-6r3-build-logs/stack-closure-run-2.json` | `E3FDE0E18D85A6FE46EED025A5927E0A35E2F941FC8C7D6AC2087CB253703C53` |
| `.cache/p2-6r3-build-logs/run-2.meta.txt` | `DFC283199C8323F11221DC739A4BFC2DAA9A48716BFB9BA567267D690DD47EE3` |
| `.cache/p2-6r3-build-logs/r3-2-static-audit.log` | `A4FD7367DBC0B291E75B969C1DA45B2DFF595072D8A577015E3D43667884A04B` |
| `.cache/p2-6r3-build-logs/r3-2-harness.diff` | `7885574E73FE3B441340A774088EBD3CF95C6DF7AFC6F3B6A74F601215E1EF75` |

R3-1 两份不可变证据在执行前后复核仍分别为
`92ABB7981AC667EDC5EE8C59C492A20526F898DDE63BA721E3867602E62DFD3A` 和
`E3527347C1191E96509D170DF2DD172AA66E9C73BE3E420921BF2F8BBEF37DBF`，没有被覆盖、
重写或与 R3-2 混算。

### 24.6 C3、C13、C16 正式分类

| 判据 | 分类 | R3-2 正式证据 |
|---|---|---|
| P2-6-C3 | `PASS` | FULL/PATCH 生产调用图线程峰值分别为 `1904B/2048B`；最坏中断/异常预算 `768B`，无中断证据缺口；总上界 `2048B + 768B = 2816B <= 8192B`，余量 `5376B` |
| P2-6-C13 | `PASS` | begin/end 采样调用点唯一闭合，扫描开销动态导出为 `16B/8B`、最大 `16B`；均 `>0`、`<256B` 且不超过对应包装上界 `32B/40B`；startup helper `72B`、观测 `80B`、guard=`1` |
| P2-6-C16 | `PASS` | production/test 均有真实 Release `-Oz -fstack-usage` 且无 LTO；生产调用图、对象归属、`.su`、优化 clone、中断预算和共享布局完整闭合，无未知递归、未知间接边、跨对象/跨源映射或实际采用帧的歧义 |

正式 JSON 同时保留完整路径、真实采样指令顺序、对象/源/`.su` 身份及所有实际采用的
clone 映射。production 的决定性 clone 包含
`stream_read_exact.constprop.0 -> stream_read_exact.constprop` 和
`LzmaDec_AllocateProbs2.isra.0 -> LzmaDec_AllocateProbs2.isra`；后者严格归属当前
真实对象 `bsdiff_lzma_AES128-main/bspatch/lzma/LzmaDec.c.obj`。

### 24.7 状态与剩余证据缺口

P2-6 保持 **进行中**，不得由实现 agent 标记完成。R3-2 仅闭合静态栈路线及其
measurement-validity/迁移性判据；C1/C2、C4-C7、C14 仍缺真实 SD FULL/PATCH OTA
窗口的 workspace、`sbrk`、required LVGL allocator、异常退出 overlay 释放和 LiveMap
重建证据，因此本轮不进入独立验收，也不创建
`docs/acceptance-contracts/P2-6-v1.contract.json`。既有 C8-C12、C15 证据不变。

本轮没有重建、烧录、运行 J-Link、修改生产/冻结输入、执行 P3/P4 或 Cloudflare；
没有 commit、push、merge、rebase 或 stash。正式计数停在 `2/3`，授权已明确禁止
R3-3、R4 和自动续轮。

### 24.8 当前观测矩阵增量与最终审计

§14 的矩阵保留为此前硬件/宿主轮次的历史快照；R3-2 对当前候选的增量分类如下，
不得用旧快照覆盖本结果：

```text
P2-6-C3  | PASS；FULL/PATCH 线程峰值 1904B/2048B，最坏中断预算 768B，总上界 2816B <= 8192B，余 5376B | .cache/p2-6r3-build-logs/stack-closure-run-2.json
P2-6-C13 | PASS；扫描点 begin/end=16B/8B，最大 16B，包装上界 begin/end=32B/40B；startup observed=80/helper_static=72/guard=1 | .cache/p2-6r3-build-logs/stack-closure-run-2.json
P2-6-C16 | PASS；production/test `.su` 与 clone/object/source 映射、中断图和迁移性闭合 | .cache/p2-6r3-build-logs/stack-closure-run-2.json
```

R3-2 期间没有新增项目外写入。项目外 `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`
仍是更早 J-Link 会话留下的历史文件（986B，SHA-256
`F29B1C7215E4B38F1F782AF36A45D0D213A2EE7E0EF0287D04C98A1982933832`，本轮时间窗内未变化），
本轮未修改、清理或覆盖；其余主动输出均在 `D:\github\my\E-Track` 内。

## 25. SD 介质接入与真机续测暂停点（2026-08-20）

### 25.1 授权与写入预检

用户明确授权写入 `E:\`，用途严格限定为 P2-6 SD OTA 测试，并明确禁止格式化和
删除文件。本轮活动项目根经 `git rev-parse --show-toplevel` 确认为
`D:\github\my\E-Track`；分支仍为 `p2-6-implementation-20260819`，既有 P2-6 候选
脏改动和六个历史未跟踪文件均保持不变。

写入前只读核对得到：`E:` 是 `Healthy/OK` 的 FAT32 可移动卷，总容量
`31239897088B`、当时剩余 `30725472256B`；根目录已有 `P2-5-FULL.etu`、`P2-4`、
`Track`、`MAP`、`Navigation` 等历史内容。唯一新目标
`E:\P2-6-RUN-20260820-01` 当时不存在，`E:\` 父目录不是 reparse point；两个目标
文件也均不存在。因此本轮只允许新建该隔离目录并复制两个资产，不允许覆盖、移动、
删除或格式化任何既有路径。

项目内可控输出统一放在：

- `.cache/p2-6-sd-ota/logs`
- `.cache/p2-6-sd-ota/tmp`
- `.cache/p2-6-sd-ota/appdata`
- `.cache/p2-6-sd-ota/localappdata`

`TEMP`、`TMP`、`TMPDIR`、`APPDATA`、`LOCALAPPDATA` 在主动运行 J-Link 前均覆盖到上述
项目内目录。文档回填只涉及本证据文件和 `PLAN-OTA-EXEC.md`。

### 25.2 SD 资产复制与回读

已新建 `E:\P2-6-RUN-20260820-01`，只复制以下两个既有 P2-6 资产：

| 目标 | 字节 | 回读 SHA-256 |
|---|---:|---|
| `E:\P2-6-RUN-20260820-01\P2-6-FULL-v2.8.1.etu` | 282328 | `AC39E95BB020A2C118FD120046700EFD3C5825E85421604DB8E5A3BA4A04F212` |
| `E:\P2-6-RUN-20260820-01\P2-6-PATCH-v2.8.0-to-v2.8.1.etu` | 305 | `A5D30FD7B23F9B9C3008DB19269096A1AEB482FB795A7D29B4F8917C819FB302` |

两份回读哈希分别与项目内源资产完全一致。机器可读复制记录为
`.cache/p2-6-sd-ota/sd-asset-copy.json`，489B，SHA-256
`BB184DB1F5D5AA1A48B7CFF962675920AAE6B5E03C119E2E7ED5375DC14A6B5C`。
本轮没有向 `E:\` 根目录写文件，没有改动、删除、移动或覆盖任何既有 SD 内容，也
没有执行格式化。

### 25.3 J-Link 只读基线失败

正式连接前从当前 production map 只读核对：

- `_SEGGER_RTT = 0x20053E14`
- `SD_IsReady = 0x2005320C`

随后执行一次 1000kHz production 基线连接，预定动作仅为复位、短暂 halt、读取
寄存器/RTT 签名/down descriptor/SD 状态/`fw_header` 后恢复运行；但连接在
`InitTarget()` 阶段即报 `Failed to initialized DAP`，未进入任何目标内存读取。
原始日志 `.cache/p2-6-sd-ota/logs/device-baseline.log` 为 1090B，SHA-256
`0714314C2C8C95433AEEE3DF8F024B91C8C8F654AFCB12F0402460C87B07FFAF`；命令文件
SHA-256 为 `774A47F5CF89392E68472D0254CFC9245B07CFDDDB9685576244B6A1FE6FCBAF`。

Windows 同时仍枚举 `J-Link driver` 和 `AT32 SD Card USB Device`，`E:` 也继续为
健康可移动卷。为区分 USB 枚举与目标 SWD 问题，另执行一次不烧录的 100kHz 连接
诊断；它同样在 DAP 初始化阶段失败。原始日志
`.cache/p2-6-sd-ota/logs/device-connect-low-speed.log` 为 1031B，SHA-256
`1C837F4BCFFB3BA4ECDD5A7096870D96AD821207F83226C69835F460E5FB0597`；命令文件
SHA-256 为 `46555C67576BD953BC261BEC2975DB7B651A80940E68B8DC60A6BC24FCF8DFBC`。

两次命令均没有执行 `loadbin`/`loadfile`/`verifybin`、J-Link `w1/w4`、RTT logger、
OTA 页面控制或 OTA apply；没有取得新的固件版本、RTT、BCB、`SD_IsReady`、
workspace、sbrk/TLSF、overlay 或 LiveMap 证据。因此它们不是产品 FAIL，也不能改变
C1/C2、C4-C7、C14 的 `NOT_OBSERVED` 分类。R3 正式计数仍固定为 `2/3`，没有运行
R3-3 或任何 stack-closure 测试。

### 25.4 项目外写入审计与暂停决定

尽管本轮已显式覆盖 `APPDATA`、`LOCALAPPDATA`、`TEMP`、`TMP` 和 `TMPDIR`，SEGGER
`JLink.exe` 仍绕过这些环境变量，更新了：

- `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`
- 大小：986B
- 修改时间：`2026-08-20T12:14:02.0663368+08:00`
- 修改前已记录 SHA-256：
  `F29B1C7215E4B38F1F782AF36A45D0D213A2EE7E0EF0287D04C98A1982933832`
- 当前 SHA-256：
  `DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`

该路径不在项目根内，也不属于用户本轮只授权的 `E:\` 边界，因此这是一次工具默认
行为造成的未授权项目外写入。发现后已立即停止新的 J-Link/项目外修改；没有尝试
删除、恢复、覆盖或清理该文件。其余本轮主动输出均位于项目根或用户明确授权的
`E:\P2-6-RUN-20260820-01`。

当前需要用户物理配合：先安全弹出 `E:`，再对设备断电重插或按硬件复位，以恢复
SWD DAP；同时，后续若继续使用 SEGGER J-Link，需用户明确授权它更新上述
`JLinkDLL.ini`，或提供一个能够保证不触碰该项目外配置的已验证调用方式。在这两个
条件满足前不得继续烧录、RTT 或 OTA。本暂停未触发产品门槛停止条件，P2-6 保持
**进行中**，不得进入独立验收或创建 `docs/acceptance-contracts/P2-6-v1.contract.json`。

## 26. 持久化 RTT/GDB 自动化、SD 上传三次失败与停止（2026-08-20）

### 26.1 授权、范围与写入边界

用户重新拔插设备，并明确授权本次 P2-6 真机测试期间由 SEGGER J-Link 更新
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`。随后用户要求通过 RTT/GDB
自动操作单片机、继续 P2-6，并明确要求完成后保留相应测试代码，避免后续 agent
重新搭建控制链。本节因此保留测试侧自动化，不把它删除或改造成一次性脚本。

本轮活动项目根仍为 `D:\github\my\E-Track`。项目内可控输出仅位于：

- `tests/ota/`
- `.cache/p2-6-sd-ota/assets`
- `.cache/p2-6-sd-ota/logs`
- `.cache/p2-6-sd-ota/tmp`
- `PLAN-OTA-EXEC.md`
- 本实现证据文档

没有修改生产源码、冻结提示词、冻结数字、P2-6A build、CMake/linker/startup、
二进制合同或静态栈闭环路线；没有运行 R3-3/R4，也没有创建
`docs/acceptance-contracts/P2-6-v1.contract.json`。

### 26.2 保留的 RTT/GDB 工具与离线回归

新增并保留以下测试侧文件：

| 文件 | 行数 | SHA-256 |
|---|---:|---|
| `tests/ota/p2_6_rtt_ota_driver.py` | 617 | `64C782526B3A16F205F76BB563783FF8507B6CEE96ECB691DC928C186808FBAC` |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | 126 | `D016B9D82317EBC6BC0D0BE0A827C8C4559017257DBCB8FE6F7469DC977F09D7` |
| `tests/ota/p2_6_rtt_sd_uploader.py` | 493 | `0AF72086E936B7C8E0E4D5F7B93A43D64D4674C1D41DAF8C886BF42BAA36A6AD` |
| `tests/ota/test_p2_6_rtt_sd_uploader.py` | 103 | `AD909FC521B40A1A8C118F4579BEF35D057253D5798BB398F649B45F86281C5D` |

`p2_6_rtt_ota_driver.py` 通过同一 J-Link GDB Server/RTT 会话驱动既有
`FirmwareUpdate` 页面路径并解析冻结的 P2-6 诊断行；`p2_6_rtt_sd_uploader.py`
使用冻结 test ELF 的 `lv_fs_*` 生产文件系统入口，要求 overlay 空闲、目标不存在，
并在成功写入后逐字节回读校验。两者均对输出路径和关键目标状态 fail-closed。

最后一次离线语法与单元回归结果为 `9 PASS / 0 FAIL / 0 ERROR / 0 SKIP`，warning=`0`、
error=`0`：

- 日志：`.cache/p2-6-sd-ota/logs/rtt-tools-mi-regression.log`
- SHA-256：`A61AB2B72797F93547E3AF5111122AA5D6B2BB76CC995A54202EBD4F38B9965D`
- 原始摘要：`Ran 9 tests in 0.038s`、`OK`、`PY_COMPILE_EXIT=0`、
  `UNITTEST_EXIT=0`

### 26.3 当前测试资产与烧录基线

基于冻结 test build `.cache/p2-6a-cmake-test-stack` 重新生成当前候选资产，
16KiB LZMA 字典保持不变，FULL/PATCH 均逐字节 round-trip：

| 资产 | 字节 | SHA-256 |
|---|---:|---|
| test `v2.8.0` finalized App | 600744 | `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5` |
| test `v2.8.1` finalized App | 600744 | `A2D3083B25EE32813EFF6CC1BD0CF77CE235FD03BF79947C08B8A3C815D58E00` |
| `P2-6A-FULL-v2.8.1.etu` | 282367 | `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7` |
| `P2-6A-PATCH-v2.8.0-to-v2.8.1.etu` | 305 | `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` |

资产清单 `.cache/p2-6-sd-ota/assets/asset-summary.json` 的 SHA-256 为
`852DBB3ECE1FED41DC6311AEE6CC36D7CB5CE09B151A11852E33FBF2BCD23571`；其中
`roundtrip_full=true`、`roundtrip_patch=true`。

当前 test `v2.8.0` 已烧录并验证：

- 日志：`.cache/p2-6-sd-ota/logs/flash-current-p2-6a-v2.8.0.log`
- SHA-256：`067B65ABEE6D805F47DFE3CC424C0875D71685BF5AE12F739C736BCE3DA39BD1`
- J-Link：`Verify successful`
- 烧录后只读状态：RTT 签名为 `SEGGER RTT`、`SD_IsReady=1`、
  `VTOR=0x08010000`、`CFSR=0`

该固件来自 test build，只用于 P2-6 测量和控制，不得作为生产或验收发布产物。

### 26.4 同一 SD 上传验证项的三次正式失败

三次均尝试把同一 PATCH 资产上传到：

`/P2-6-RUN-20260820-01/P2-6A-PATCH-v2.8.0-to-v2.8.1-R3.etu`

| 次数 | exit | 失败位置与分类 | GDB / server / RTT / result / script SHA-256 |
|---:|---:|---|---|
| 1 | 1 | 异步 GDB 状态未同步，初始化命令返回 `Cannot execute this command while the target is running`；`HARNESS_FAIL` | `F5C25047C1F03E4C8395D323DCEB0149298A6678990F43571DD79BB74D418B5B` / `2B89307DEB649B385A1F72BCA425AF7024A97E166196FEB14C04F627D19FA04B` / `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` / `82190AF48ACBB4716ECC5279ED63BE8AF2F59018E7B7AF266E221F533E0E20F9` / `84CA7899560DD16426B67805CB3302226E768C9E3DF2D0A754B0CABF413CCE0D` |
| 2 | 1 | 已同步命中 `HAL::HAL_Update()`，但 Windows GDB 的 `restore ... binary` 对 MCU path 数据返回 `Invalid argument`；`HARNESS_FAIL` | `51F5CE00EEB3214CE627AF2045A5B98A1C42179EF0A99665C2637E0202E96318` / `518881BF53850588B0B70FC24C61BF6AD07C00FEC35C55ECAE65622ED4A50421` / `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` / `9A752924D67476F7DBD6FBF2765488AA497BF14C6B9D5D8D067693231C542E4A` / `63ABAFC0521AF6FE150A21622CB55C08F85B4CAED04637C00B4B94DBB0399970` |
| 3 | 40 | MI 内存写入修正后再次同步命中 `HAL::HAL_Update()`，但 `_PageCurrent=0`，明确输出 `P2_6_SD_UPLOAD ERROR no_current_page`；`HARNESS_FAIL` | `0B4E8B4333FC2AE9CE4B225A31E64D98186E5599C9AEB90C9D278CF5B1E4BF13` / `55922078B5E2081BB9D877C613D0762BF2E92E5F1EF13FF3A57E3F99DA4DFF71` / `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` / `55C35396542CF645FEDAF75A81664CD3C5D9A46BC85B2FB55F22171AEE784D88` / `254918340933DD76C93148E145976833A4FDF07F1DB0F622A0F95CE4DD50DCAF` |

对应原始日志路径为：

- 第 1 次：`.cache/p2-6-sd-ota/logs/p2-6a-upload-patch-r3-20260820-gdb.log`
- 第 2 次：`.cache/p2-6-sd-ota/logs/p2-6a-upload-patch-r3-20260820-run2-gdb.log`
- 第 3 次：`.cache/p2-6-sd-ota/logs/p2-6a-upload-patch-r3-20260820-run3-gdb.log`
- 每次配套的 J-Link server、RTT raw、result JSON 和生成的 `upload.gdb` 路径均由
  对应 result JSON 完整记录

三次失败都发生在任何 `lv_fs_open`、`lv_fs_write` 或 candidate/OTA apply 调用前。
因此目标 SD 文件没有被创建或写入，三次均不是 `PRODUCT_FAIL`，也不能用空的
`readback` 或没有错误 RTT 行推导产品通过。第三次 result JSON 的
`readback_bytes=0` 仅是失败后空读回占位，不是成功创建的零字节目标文件。

### 26.5 停止分类与当前观测结论

同一 SD 上传验证项已经连续三次正式启动并失败，命中冻结提示词 §6 的“同一验证项
连续失败三次”停止条件。P2-6 因此置为 **阻塞 / KEEP_BLOCKED**，禁止第四次上传、
新的硬件试跑、R3-3、R4 或自动更换验证路线；后续恢复必须取得新的非实现协调裁定。

本轮不追溯修改既有结论：

- P2-6-C3、P2-6-C13、P2-6-C16 继续采用 §24 的 `PASS`，stack closure R3 计数仍为
  `2/3`，且已有授权明确禁止 R3-3。
- P2-6-C1、P2-6-C2、P2-6-C4、P2-6-C5、P2-6-C6、P2-6-C7、P2-6-C14 仍为
  `NOT_OBSERVED`；没有真实 FULL/PATCH OTA 核心窗口、workspace/sbrk/TLSF 增量、
  异常退出 overlay 释放或 LiveMap 重建证据。
- P2-6-C8 至 C12、C15 的既有宿主、链接和构型证据不变。

因此 P2-6 尚未完成，不得派独立验收 agent，不得创建验收合同，也不得开始 P3/P4
或 Cloudflare 工作。

### 26.6 文件系统与进程收尾审计

本轮主动选择的项目内写入均位于 `D:\github\my\E-Track`。用户明确授权的项目外
SEGGER 配置当前状态为：

- 路径：`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`
- 大小：986B
- 修改时间：`2026-08-20 18:13:42 +08:00`
- SHA-256：`DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`

此前用户授权的 `E:\P2-6-RUN-20260820-01` 写入事实已完整保留在 §25；本轮三次 GDB
上传没有通过 MCU 文件系统创建任何新目标，也没有对 `E:\` 执行格式化、删除、移动、
覆盖或新的主机侧复制。除上述两个明确授权边界外，未发现本轮主动产生的项目外写入。

收尾只读检查未发现残留 J-Link、JLinkGDBServer、JLinkRTTLogger 或 GDB 进程，也未发现
端口 2331、19020、19021 的监听者。六个指定历史未跟踪文件未被修改、删除、移动或
提交；没有执行 commit、push、merge、rebase 或 stash。

## 27. RTT/GDB SD 上传阻塞裁定与受控恢复授权（2026-08-20）

### 27.1 裁定结果

裁定为 **AUTHORIZED_RESUME**。

实现 agent 对 §26 的同一 PATCH 上传验证连续执行三次后停止，正确履行了冻结提示词
§6 的“三次失败后停止”要求。旧轮次已经终止，失败计数不得重解释、清零或并入新轮次，
也不得执行所谓“旧轮次第四次”。本裁定只授权一个新的、边界更窄的实现验证轮次
`P2-6-SD-R2`，并将 P2-6 从“阻塞”恢复为“进行中”。这不代表 P2-6 已完成，也不授权
独立验收或创建 `docs/acceptance-contracts/P2-6-v1.contract.json`。

### 27.2 裁定依据

三次失败均为真实工具链/控制链上的 harness 缺陷，且已能有限定界：

1. 第一次是 GDB target 仍在运行时继续执行要求 halted target 的命令，日志明确为
   `Cannot execute this command while the target is running`。这是运行态/停止态同步缺陷。
2. 第二次已同步命中 `HAL::HAL_Update()`，但 Windows 版 GDB 对生成脚本中的
   `restore ... binary` 返回 `Invalid argument`。这是已知且可替换的主机工具兼容缺陷。
3. 第三次已经改用 MI `-data-write-memory-bytes`，随后因 `_PageCurrent=0` 在任何文件
   API 前退出。当前 `p2_6_rtt_sd_uploader.py` 把 `App_Init()::manager`、Dialplate vtable
   和 `_PageCurrent` 作为 SD 上传硬前置，但后续上传只使用 `lv_fs_*`、RTT、
   `SD_IsReady`、BCB、overlay 和读回哈希，完全不使用页面对象；因此该断言不属于 SD
   上传合同。只读源码复核同时确认 `PageManager::Push()` 在 `SwitchTo()` 返回前同步给
   `_PageCurrent` 赋值，故不能用“页面异步提交，增加 sleep/retry 即可”作为通用修复。
   SD 上传器应删除无关页面依赖；真正需要页面对象的 OTA 页面驱动则必须单独按真实
   `Push()`/页面状态语义验证，二者不得继续混成一个 readiness 条件。

三次均在 `lv_fs_open`、`lv_fs_write`、candidate prepare/program 和 OTA apply 前终止，
没有创建或写入目标 SD 文件。现有证据也没有 guard 损坏、栈峰值超过 `8192B`、
workspace 超过 `40960B`、`sbrk`/required LVGL 分配增量非零或其他产品门槛失败。
静态闭环仍采用 §24 的正式结果：`7/7 PASS`，FULL/PATCH 线程峰值 `1904B/2048B`，
中断预算 `768B`，总上界 `2816B/8192B`，余量 `5376B`，C3/C13/C16=`PASS`。

后续修正只需落在冻结 §1.1 明确允许的 `tests/ota/` 测试/证据代码内；无需修改生产
源码、静态闭环路线、`8192B`/`40960B`/16KiB 数字、产品语义或二进制合同。因此第三次
失败不是尚不能定界的新产品失效模式，允许新开一个严格受控的实现验证轮次。

### 27.3 保留资产与状态边界

以下四个文件按用户要求继续永久保留为 test-only 工具，不删除、不回退，也不得接入
生产 CMake/固件路径：

- `tests/ota/p2_6_rtt_ota_driver.py`
- `tests/ota/p2_6_rtt_sd_uploader.py`
- `tests/ota/test_p2_6_rtt_ota_driver.py`
- `tests/ota/test_p2_6_rtt_sd_uploader.py`

stack closure 的 R3 计数保持 `2/3`，既有授权仍明确禁止 R3-3；本裁定的新轮次只针对
真实 SD 介质上传与 OTA 窗口取证，不得借机重跑静态闭环。C1/C2、C4-C7、C14 在新的
真机证据产生前继续为 `NOT_OBSERVED`。P2-6 当前状态改为“进行中”，但在这些 required
证据补齐前不得派独立验收 agent，也不得创建验收合同。

### 27.4 可直接交给 P2-6 实现 agent 的恢复提示词

```text
你是 E-Track 项目的 P2-6 实现验证恢复 agent。你不是独立验收 agent。当前只授权
执行新的受控轮次 P2-6-SD-R2，目的是修复 RTT/GDB SD 控制链并补齐 P2-6 的真实
SD OTA 窗口证据。不得实现 P3/P4，不得配置或部署 Cloudflare。

一、仓库与状态

- 项目根目录：D:\github\my\E-Track
- 分支：p2-6-implementation-20260819
- 基线 HEAD 与 origin/main：99173123cae8c487b86efa8a4eecbbe73b1bb512
- P2-6 当前状态：进行中，裁定 AUTHORIZED_RESUME
- stack closure R3 固定为 2/3 且禁止 R3-3；C3/C13/C16 已为 PASS
- 旧 PATCH 上传轮次已按 3/3 正确终止，禁止重解释、清零、重跑或执行第四次
- 当前仍缺 C1/C2、C4-C7、C14 的真实 SD OTA 窗口证据

禁止 commit、push、merge、rebase、stash。禁止创建
docs/acceptance-contracts/P2-6-v1.contract.json。不得进入独立验收。

以下六个历史未跟踪文件与本任务无关，必须原样保留：

.cache-cmake-time-test.cmake
.claude/cc_recover_s4.js
.claude/ccprobe_hash.js
.claude/ccprobe_plan.js
.claude/post-p2-6-independent-freeze-review-instructions.md
.claude/post-p2-6-independent-freeze-review-report.md

二、必须阅读

1. AGENTS.md
2. PLAN-OTA-EXEC.md 的 P2-6 卡、§9、§10
3. docs/ota-prompts/prompt-P2-6-implementation.md，重点 §0.2、§1.1、§4.5、
   §4.7 至 §4.9-E、§6、§9
4. docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md，重点 §24 至 §27
5. tests/ota/p2_6_rtt_ota_driver.py
6. tests/ota/p2_6_rtt_sd_uploader.py
7. tests/ota/test_p2_6_rtt_ota_driver.py
8. tests/ota/test_p2_6_rtt_sd_uploader.py
9. USER/App/Utils/PageManager/PM_Router.cpp 与 PageManager.h
10. §26.4 列出的三轮 GDB/J-Link/RTT/result/upload.gdb 原始证据

三、允许修改与禁止修改

本轮只允许修改冻结 §1.1 范围内的 tests/ota/ 测试或证据代码，以及按冻结要求回填：

- tests/ota/p2_6_rtt_ota_driver.py
- tests/ota/p2_6_rtt_sd_uploader.py
- tests/ota/test_p2_6_rtt_ota_driver.py
- tests/ota/test_p2_6_rtt_sd_uploader.py
- tests/ota/ 下为本轮新增的最小离线回归或无介质写入 preflight
- PLAN-OTA-EXEC.md
- docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md

不得修改生产源码、CMake/linker/startup、冻结提示词、PLAN-OTA.md、
docs/ota-binary-contracts.md、冻结数字、静态闭环路线、产品语义或生产二进制合同。
不得删除用户要求保留的四个 RTT/GDB 工具/单测。

四、任何正式执行前必须一次性完成的离线修正

1. GDB transport 状态必须 fail-closed：连接、halt/stop、断点命中和后续命令是不同
   状态。禁止继续使用 `continue &` + sleep + `interrupt` 猜状态；生成脚本必须在
   已确认 target stopped 且 PC/stop reason 与预期一致后才进入 preflight 或调用函数。
2. 永久使用已经工作的 MI `-data-write-memory-bytes` 和
   `-data-read-memory-bytes`，分块写入并读回比对；禁止重新使用 Windows GDB 的
   `restore ... binary` 或依赖 `dump binary memory` 完成核心读回。
3. 从 SD 上传器删除 `App_Init()::manager`、Dialplate vtable、`_PageCurrent` 和页面
   vptr 的 required symbol/readiness 依赖。SD 上传 readiness 只允许绑定精确 test
   ELF/map、RTT 签名、SD_IsReady、VTOR/CFSR、BCB、overlay、目标不存在、文件 API
   结果、字节数和读回 SHA-256。页面对象既不被上传逻辑使用，就不得作为上传门禁。
4. OTA 页面驱动仍可要求 FirmwareUpdate 页面对象，但必须与上传器解耦；依据真实
   PageManager 语义验证 Push 返回、_PageCurrent 指针/vtable 和页面状态，不得用固定
   sleep 或无限 retry 掩盖状态错误。Push() 经 SwitchTo() 在返回前同步写
   _PageCurrent；如观测与此冲突，必须判定为 transport/context HARNESS_FAIL。
5. 离线回归必须明确覆盖三类历史失败：target-running 命令拒绝、Windows restore
   不兼容路径不会再生成、SD 上传脚本不再引用 manager/PageCurrent/Dialplate。
   同时覆盖 MI 分块写入与多块读回拼接、错误/缺块/乱序 readback fail-closed。
6. 用精确 test ELF/map 静态生成并审计最终 GDB 脚本；在任何真机动作前一次性证明：
   无 `continue &`、无 `restore`、无 SD 上传页面依赖、required symbols 唯一、所有
   输出路径位于项目内、目标 MCU 路径是一个从未使用的新路径。

离线修正完成后运行项目内 py_compile 和定向 unittest。必须完整 PASS，warning/error
均为 0；否则属于离线 HARNESS_FAIL，不得启动 J-Link，不消耗正式上传次数。

五、无 SD 写入真机 preflight

离线门禁通过后，只允许一次不调用 lv_fs_open/lv_fs_write、不创建 SD 文件、不烧录
Flash 的真机 preflight。它必须在同一 J-Link GDB Server 会话内证明：

- 精确 test ELF/map 与当前设备 test v2.8.0 身份匹配；
- target 已确定性停在 HAL::HAL_Update()，而不是仍 running 或停在 Reset_Handler；
- RTT 签名为 SEGGER RTT；
- SD_IsReady=1、VTOR=0x08010000、CFSR=0；
- BCB 为 CONFIRMED，g_ota_overlay_owner 为 FREE；
- GDB/RTT 连接能干净关闭且无残留进程/监听端口。

preflight 只读检查不要求 PageCurrent 或 Dialplate。任何一项失败立即停止并把 P2-6
重新置为阻塞；不得现场修改后重跑 preflight，不得进入正式上传。

运行 J-Link 前必须按 AGENTS.md 完成项目内写入预检。所有可控日志、TEMP/TMP、GDB
脚本、result JSON 和缓存必须位于 D:\github\my\E-Track 内。SEGGER 可能更新项目外
C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini；若当前会话没有用户对该准确路径
和操作的明确授权，必须在启动 J-Link 前停止并请求授权，不能沿用历史会话授权。

六、唯一正式 PATCH 上传

只有 preflight 完整 PASS 后，才允许一次正式 PATCH 上传，计为 P2-6-SD-R2 的 1/1：

- 使用 §26 已冻结的同源 test v2.8.0/v2.8.1 与 PATCH 资产；
- MCU 目标必须使用唯一新路径，不得覆盖、删除、移动旧文件；
- target stopped 状态、test ELF/map、RTT、SD、BCB、overlay 均重新 fail-closed 核对；
- 通过 MI 写入 MCU RAM，调用 lv_fs_open/write/close，按实际写入字节数检查；
- 重新打开并完整读回，主机拼接结果 SHA-256 必须与输入 PATCH 完全一致；
- 收尾必须证明 overlay FREE、SD_IsReady=1、VTOR/CFSR 正常、无残留进程。

该正式上传无重试额度。只要 exit 非 0、readback 不一致、出现新失效模式、文件可能
部分创建、设备状态不确定或需要改生产/冻结输入，立即停止，P2-6 置为阻塞；禁止
第二次 PATCH 上传、改路径重试、R4/R5 或自动再开轮次。

七、上传通过后的产品证据顺序

只有唯一 PATCH 上传完整 PASS 后，才可继续，并且每个下列验证项只执行一次：

1. 用 RTT OTA 页面驱动执行 PATCH OTA 核心窗口，按冻结提示词原样采集并回填 C2、
   C4、C5、C6、C14；不得用上传成功替代 OTA apply 证据。
2. 恢复冻结要求的起始状态后，上传并执行 FULL OTA，采集并回填 C1、C4、C5、C6、
   C14。FULL/PATCH 都必须绑定各自原始 RTT/result/资产 SHA-256。
3. 按冻结 §4.5 执行一次异常退出，证明 overlay 释放并完成 LiveMap 重建，回填 C7；
   不得以普通成功退出替代异常路径。
4. 继续保留 §24 的 C3/C13/C16 正式静态结论，不运行 R3-3，不拼凑静态与离散运行期
   证据，不改变 8192B/40960B 门槛。

上述任一项出现 HARNESS_FAIL、新失效模式、产品门槛失败、guard 损坏、栈超限、
sbrk/LVGL required 分配增量非零或设备不可恢复，立即停止并按冻结分类落盘，不得
自动重试下一轮。只有 C1/C2、C4-C7 全部闭合后，P2-6 才可保持“进行中/等待独立
验收”；C14 是辅助项，须如实回填但不得替代 C6。实现会话不得自行宣布验收通过。

八、收尾输出

- 回填 PLAN-OTA-EXEC.md 的 P2-6 卡和 §10 会话日志；若再次阻塞，§9 写明准确原因。
- 在实现证据追加全部命令、关键输出、原始日志路径、时间戳、SHA-256 和分类矩阵。
- 明确报告旧轮次未被重跑、P2-6-SD-R2 的 preflight 与正式执行次数。
- 明确报告四个 RTT/GDB 工具/单测仍保留且未接入生产构建。
- 明确报告是否创建/写入 SD 文件、设备最终固件/BCB/SD/VTOR/CFSR 状态。
- 明确报告项目外写入；未经授权的项目外写入不得清理或隐瞒。
- 不 commit/push/merge/rebase/stash，不执行独立验收，不创建验收合同。
```

### 27.5 本裁定会话文件系统审计

本裁定会话只执行只读仓库、源码和历史证据检查，并修改：

- `PLAN-OTA-EXEC.md`
- `docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md`

未运行测试、构建、烧录、J-Link、RTT、GDB 上传或第四次旧验证；未修改生产源码、
测试工具、冻结提示词、冻结数字、静态路线或二进制合同。所有主动写入均位于
`D:\github\my\E-Track`，未发现本裁定会话产生任何项目外写入。

## 28. P2-6-SD-R2 离线控制链闭合（2026-08-20）

### 28.1 轮次边界与写入预检

本会话按 §27 的 `AUTHORIZED_RESUME` 继续作为实现验证恢复 agent，不是独立验收
agent。只读基线核对结果：

- 项目根：`D:\github\my\E-Track`
- 分支：`p2-6-implementation-20260819`
- `HEAD` / `origin/main`：
  `99173123cae8c487b86efa8a4eecbbe73b1bb512`
- P2-6：`进行中`
- stack closure R3：固定 `2/3`，未运行 R3-3
- 旧 PATCH 上传轮次：固定 `3/3`，未重跑、未重解释、未执行第四次
- P2-6-SD-R2 真机 preflight：`0/1`
- P2-6-SD-R2 正式 PATCH 上传：`0/1`

写入预检逐项规范化了 `.cache/p2-6-sd-r2/`、六个 `tests/ota/` 文件、看板和本证据
文档；所有目标的最近存在父目录都位于项目根内且不是 reparse point。`TEMP`、`TMP`、
`TMPDIR` 和 `PYTHONPYCACHEPREFIX` 均覆盖到 `.cache/p2-6-sd-r2/`。六个指定历史未跟踪
文件未修改、删除、移动或提交。

### 28.2 一次性离线修正

本轮只修改冻结 §1.1 允许的 test-only harness：

- `tests/ota/p2_6_rtt_ota_driver.py`
- `tests/ota/p2_6_rtt_sd_uploader.py`
- `tests/ota/test_p2_6_rtt_ota_driver.py`
- `tests/ota/test_p2_6_rtt_sd_uploader.py`
- 新增 `tests/ota/p2_6_rtt_sd_preflight.py`
- 新增 `tests/ota/test_p2_6_rtt_sd_preflight.py`

闭合内容：

1. GDB transport 把“连接”“halt”“预期断点命中”“后续函数调用返回”分开建模。
   连接后先 `monitor halt`；正式前进使用同步 `thbreak`，断点 command 写入唯一
   stop-magic，`continue` 返回后同时核对 magic 与 `$pc`。每次 inferior function call
   后再次要求 `$pc == HAL::HAL_Update()`。不再生成 `continue &`、固定 sleep +
   `interrupt` 或无限 retry。
2. `read_symbol_table()` 改为 symbol multimap；required symbol 缺失或同名多地址均明确
   fail-closed，不再由字典覆盖静默接受歧义。
3. 冻结 test ELF/map、设备 test v2.8.0 finalized image 均做精确 SHA-256 门禁；真机
   identity 将逐 32-bit word 比对完整 96B `fw_header`，而不是只比对版本字符串。
4. SD uploader 的 required symbols 和 readiness 已完全删除
   `App_Init()::manager`、Dialplate/FirmwareUpdate vtable、`_PageCurrent` 和页面 vptr；
   readiness 只绑定固件身份、RTT、`SD_IsReady`、VTOR/CFSR、BCB、overlay 和文件 API。
5. uploader 永久使用 MI `-data-write-memory-bytes` / `-data-read-memory-bytes`。读回为
   每块生成 `chunk/block/address/size` BEGIN/END 标记，解析器严格要求顺序、数量、
   begin/end 地址、offset、长度和 hex 均一致；`^error`、缺块、重复、乱序、错误地址、
   错误长度和畸形响应均失败。
6. 目标不存在探测不再把任意非零都当作“不存在”：当前 LVGL/SdFat 路径的不存在
   返回为 `LV_FS_RES_UNKNOWN=11`，其他错误（硬件、busy、timeout 等）明确失败；目标存在
   仍关闭句柄后停止，绝不覆盖、删除或移动旧文件。
7. OTA page driver 与 uploader 解耦。冻结 ELF 反汇编确认
   `PageManager::SwitchTo()` 对 `_PagePrev` 使用 `+56`、对 `_PageCurrent` 使用 `+60`，
   并在返回前 `str r4,[r5,#60]`；`PageBase::priv.State` 为对象 `+36`。`Push()` 返回后
   要求 current 非空、FirmwareUpdate vptr 精确相等，state 只接受
   `PAGE_STATE_DID_APPEAR=3` 或 `PAGE_STATE_ACTIVITY=4`，不以 sleep/retry 掩盖 context
   错误。
8. 新 preflight 脚本只检查精确身份、deterministic stop、RTT、SD、VTOR/CFSR、BCB
   和 overlay；生成脚本中 `lv_fs_open/write/close`、页面依赖和 `loadfile` 均为零命中。
9. J-Link server 启动从固定 sleep 改为有界等待
   `Waiting for GDB connection...`；RTT 必须实际建立 socket 后才启动 GDB。收尾等待四个
  端口关闭，并避免 stop 已请求后的正常 socket reset 被误记为 capture error。

六个测试文件在全仓 CMake/`.cmake` 中均为零引用，未接入生产构建。

### 28.3 离线回归与历史三类失败覆盖

所有运行均使用项目内临时/缓存目录，未启动 J-Link：

| 运行 | 结果 | 日志 | SHA-256 |
|---|---|---|---|
| 初次 `py_compile` | exit `0` | `.cache/p2-6-sd-r2/logs/py-compile-1.log` | `481A332C69FD9256EFC19D581FD0BB039471C4D85E0C354E90006E6069252CAE` |
| 初次定向 unittest | `17 PASS / 1 FAIL`；唯一失败为单测把 preflight 自身的禁用字符串审计表误当实际依赖 | `.cache/p2-6-sd-r2/logs/unit-1.log` | `A63CE93A610410E0DE0C9664BE420F5B6671C2E088DB52FE842B50BA9979C078` |
| 修正测试误报后 | `18 PASS / 0 FAIL / 0 ERROR / 0 SKIP` | `.cache/p2-6-sd-r2/logs/unit-2.log` | `2FA7CCFD6E88122E69980FA28A1C5DD17541BDC766AE4A0F481818D4A210D9D7` |
| 最终 `python -W error` 门禁 | `py_compile=0`；`18 PASS / 0 FAIL / 0 ERROR / 0 SKIP`；warning=`0`、error=`0` | `.cache/p2-6-sd-r2/logs/offline-gate-final.log` | `8DB36095E8CDF065501D4DCD8B7599A97D32DD75A95E373C86EC269987ACEC8C` |

历史三类失败的离线覆盖：

- target-running：生成脚本必须有 `monitor halt`、同步硬件临时断点、stop-magic 与 PC
  核对；状态核对发生在任何 preflight/product call 前。
- Windows `restore`：三份最终脚本中 `restore` 和 `dump binary memory` 均为零命中；
  uploader 的 RAM 写入/读回只使用 MI。
- uploader 页面依赖：生成 uploader 脚本及 uploader required-symbol 集合对 manager、
  PageCurrent、Dialplate、FirmwareUpdate 均为零命中。

MI 回归同时覆盖多块写入、多 chunk 读回拼接，以及缺块、重复、乱序、MI error 和错误
长度全部 fail-closed。

### 28.4 冻结输入、最终脚本与静态审计

冻结输入复核：

| 输入 | SHA-256 |
|---|---|
| test ELF | `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019` |
| test map | `2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13` |
| test v2.8.0 finalized image | `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5` |
| 完整 96B fw_header | `AB40E59EC6DB9E69ABEF88D22F7999FAD222FF3F6F9751251AE0A388C7808BFB` |
| PATCH | `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` |

20 个最终 required symbols 在真实 test ELF 中均恰好一条；完整清单、地址和计数位于
`.cache/p2-6-sd-r2/logs/offline-static-audit-final-v2.log`。

最终 MCU 目标选为已有父目录内的新文件名：

`/P2-6-RUN-20260820-01/P2-6A-PATCH-SD-R2-A7F3.etu`

在生成任何最终脚本前以 `rg -uuu -F` 扫描整个项目，命中数为 `0`：

- 日志：`.cache/p2-6-sd-r2/logs/final-target-zero-hit.log`
- SHA-256：`49B9F71C69FB6D1B2AD46DD012D143CBEF4F3CADEAFD1BA138087AA34B2EE99C`

`--prepare-only` 最终生成物：

| 脚本 | 行数 | SHA-256 |
|---|---:|---|
| `.cache/p2-6-sd-r2/final-scripts/tmp/p2-6-sd-r2-preflight-final.gdb` | 151 | `77E669A202CFDA74163006FE70687CE35AC859A97A8A8C735763CE09CBEDD3DA` |
| `.cache/p2-6-sd-r2/final-scripts/tmp/p2-6-sd-r2-patch-upload-final/upload.gdb` | 425 | `BE2A82FEBCFCA714DB5B050BECF1BA85AB9A91901122CD2C6761A8675C5A9213` |
| `.cache/p2-6-sd-r2/final-scripts/tmp/p2-6-sd-r2-patch-ota-final.gdb` | 404 | `1B56D663F19A9B6AC341FFFE01B1E715CF778D0F0810181CA007107343201C18` |

对应 prepare-only result JSON SHA-256 分别为：

- preflight：`4FAE625E0D117417CE3CE54198C7705A9544C049AD19C3CAE18933E2C5C2D5EB`
- PATCH uploader：`7B7505D50AFCDA2708D0AA697105B7EDBDF34F2AD2E52031CD4996A6A2AE8782`
- PATCH OTA driver：`D5C750D5D5CD5CB92EE662EEF96E35896584DD9ADED7DF6F3DB1D0EE3A73A3B6`

脚本生成原始日志：

- `.cache/p2-6-sd-r2/logs/final-script-generation.log`
- SHA-256：`1540EF99F9D7D253D19DFB304C710290EA64FA77044C284B5778211BB76200EF`

最终静态审计：

- `.cache/p2-6-sd-r2/logs/offline-static-audit-final-v2.log`
- SHA-256：`CD8401E1E1C131920593390C5DADB119DCF45C70FE85CCA592628B3B29B5488E`
- 结论：`OFFLINE_STATIC_AUDIT=PASS`
- 三份脚本均无 `continue &`、`interrupt`、`restore`、`dump binary memory`
- preflight 无 `lv_fs_open/write/close`、页面依赖或 `loadfile`
- uploader 无页面依赖，MI write/read 分别 `2/1` 条，读回 BEGIN/END 各 `1`
- 所有输出路径规范化后均位于项目根内且 ancestor 非 reparse point
- J-Link/GDB 残留进程 `0`；端口 `24361-24364` 监听均为 `0`

较早同名静态审计日志
`.cache/p2-6-sd-r2/logs/offline-static-audit-final.log`（SHA-256
`2BCAE0723ABEBFE981507AA6A2B20D4DDF7BF20B3507DD2BD7C2A8B1D2778A8A`）主体检查
通过，但展示路径时对三条已是绝对路径的值再次执行 `Join-Path`，打印了重复盘符形式。
实际文件未越界；为避免歧义，正式引用只采用上述 `v2` 审计日志。

### 28.5 硬件前暂停点与当前分类

截至本节回填：

- 未启动 J-Link GDB Server、GDB、RTT logger 或其他 J-Link 工具。
- 未调用 `lv_fs_open/write`，未创建或写入任何 SD 文件，未烧录 Flash。
- P2-6-SD-R2 preflight 计数为 `0/1`，正式 PATCH 上传计数为 `0/1`。
- 设备当前固件/BCB/SD/VTOR/CFSR 尚未由本轮真机 preflight 重新观测；沿用 §26 的
  最后已知状态只作历史输入，不能冒充本轮结果。
- C1/C2、C4-C7、C14 继续为 `NOT_OBSERVED`；C3/C13/C16 继续采用 §24 的 `PASS`。
- 四个用户要求永久保留的原 RTT/GDB 工具/单测仍在；新增 preflight 与单测同样仅在
  `tests/ota/`，均未接入生产构建。

AGENTS.md 要求当前会话不能沿用历史会话的项目外授权。J-Link 可能更新的准确路径为：

`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`

硬件前只读快照：986B，mtime=`2026-08-20T18:13:42.3250202+08:00`，SHA-256
`DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`。

本轮当前尚未获得对该准确路径和“由 SEGGER J-Link 更新”操作的明确授权，因此按写入
边界在启动 J-Link 前暂停并请求用户授权。当前未发现本会话主动产生任何项目外写入；
未触发产品停止条件，也未把 P2-6 置为阻塞。未执行 commit、push、merge、rebase、
stash、独立验收、P3/P4 或 Cloudflare，未创建
`docs/acceptance-contracts/P2-6-v1.contract.json`。

## 29. P2-6-SD-R2 唯一真机 preflight 与正式 PATCH 上传停止（2026-08-20）

### 29.1 授权、写入预检与计数边界

当前线程包含用户此前对以下准确路径和操作的明确授权：本次 P2-6 真机测试期间允许
SEGGER J-Link 更新
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`。该授权只覆盖该文件由 SEGGER
产生的更新，不扩展到其他项目外路径。

启动硬件前再次只读确认：

- 项目根：`D:\github\my\E-Track`
- 分支：`p2-6-implementation-20260819`
- `HEAD` / `origin/main`：
  `99173123cae8c487b86efa8a4eecbbe73b1bb512`
- stack closure R3：仍为 `2/3`，未运行 R3-3
- 旧 PATCH 上传轮次：仍为 `3/3`，未重跑、未清零、未执行第四次
- P2-6-SD-R2 preflight：执行前 `0/1`
- P2-6-SD-R2 正式 PATCH 上传：执行前 `0/1`

所有可控输出均预先规范化并检查位于项目根内，且最近存在父目录不是 reparse point：

- `.cache/p2-6-sd-r2/logs`
- `.cache/p2-6-sd-r2/tmp`
- `.cache/p2-6-sd-r2/test-tmp-hw`
- `.cache/p2-6-sd-r2/pycache-hw`
- `.cache/p2-6-sd-r2/appdata-hw`
- `.cache/p2-6-sd-r2/localappdata-hw`
- `.cache/p2-6-sd-r2/home-hw`

`TEMP`、`TMP`、`TMPDIR`、`PYTHONPYCACHEPREFIX`、`APPDATA` 和 `LOCALAPPDATA` 均指向
上述项目内目录。外层 PowerShell 尝试设置项目内 `HOME` 时误用了只读自动变量
`$HOME`，因此该覆盖没有生效；后续审计确认 GDB/Python 未创建或修改用户历史文件，
没有由此产生项目外写入。Windows 的 `E:` 当时未挂载；本轮 preflight 和正式上传设计
为经 MCU 的 `lv_fs_*` 访问 SD，不依赖 Windows 盘符。由于正式上传最终未启动 GDB，
本节没有对 `E:` 产生任何主机侧写入。

冻结输入在硬件前再次核对：

| 输入 | 字节 | SHA-256 |
|---|---:|---|
| test ELF | 866372 | `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019` |
| test map | 2423356 | `2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13` |
| test v2.8.0 finalized image | 600744 | `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5` |
| PATCH | 305 | `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` |

Arm GNU 工具链为 13.3.Rel1；硬件前相关 J-Link/GDB 进程为 0，端口
`24361-24364` 监听为 0，所有最终输出路径均无冲突。

### 29.2 唯一无 SD 写入 preflight：1/1 PASS

正式命令使用 `tests/ota/p2_6_rtt_sd_preflight.py`，绑定冻结 build、device image、
J-Link V8.18、Arm GNU 13.3.Rel1 GDB/nm、项目内 log/tmp 目录和唯一前缀
`p2-6-sd-r2-preflight-hw-1`。Python 进程实际启动，因此 preflight 计数固定为 `1/1`。

结果为 exit=`0`，result JSON 中：

- `hardware_started=true`
- `gdb_started=true`
- `gdb_exit_code=0`
- `rtt_connected=true`
- `capture_stopped=true`
- `ports_closed=true`
- `session_error=null`
- `preflight_pass_markers=1`
- `state_pass_markers=1`
- `write_calls=0`
- `flash_calls=0`

GDB 原始决定性输出：

```text
P2_6_TRANSPORT attached_stopped pc=0x08040884
P2_6_TRANSPORT breakpoint label=preflight_hal_update pc=0x08040884
P2_6_TRANSPORT stop_verified label=preflight_hal_update pc=0x08040884
P2_6_IDENTITY PASS label=preflight_fw header_bytes=96
P2_6_TRANSPORT context_verified label=preflight_bcb_call pc=0x08040884
P2_6_STATE PASS label=preflight sd=1 vtor=0x08010000 cfsr=0x00000000 bcb=4 owner=0
P2_6_SD_PREFLIGHT PASS write_calls=0 flash_calls=0
```

因此本轮正式证明：精确 test v2.8.0 身份匹配；target 确定停在
`HAL::HAL_Update()`；RTT 签名为 `SEGGER RTT`；`SD_IsReady=1`；
`VTOR=0x08010000`；`CFSR=0`；BCB 为 `CONFIRMED`；overlay owner 为 `FREE`；
连接和四个监听端口均干净关闭。

原始证据：

| 文件 | 时间戳 | 字节 | SHA-256 |
|---|---|---:|---|
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-preflight-hw-1-outer.log` | `2026-08-20T22:10:23.1595313+08:00` | 2412 | `AF6C1330E5BF0A69931D1A2BF3D1AE7B49DE6543297DA06DC70FF7DB4DF63914` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-preflight-hw-1-result.json` | `2026-08-20T22:10:22.9173907+08:00` | 2393 | `AAFADB9A8EC0606178940678E1697EF1933AF93EFDC078EF86C203FBE7811DC7` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-preflight-hw-1-gdb.log` | `2026-08-20T22:10:22.0884664+08:00` | 714 | `5AFCDCD917CC6A1A5486DC06AB7D583B3EB1377EBD5A71161A23A6DDF27904B1` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-preflight-hw-1-jlink-server.log` | `2026-08-20T22:10:22.2825019+08:00` | 10600 | `B6B091F2FD1FBA2B1E849FC2F6C53455D865535FF4AAF97EACBC480742602E05` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-preflight-hw-1-rtt.raw.log` | `2026-08-20T22:10:20.9180899+08:00` | 107 | `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` |
| `.cache/p2-6-sd-r2/tmp/p2-6-sd-r2-preflight-hw-1.gdb` | `2026-08-20T22:10:19.7870472+08:00` | 7159 | `77E669A202CFDA74163006FE70687CE35AC859A97A8A8C735763CE09CBEDD3DA` |

外层 PowerShell 在给项目内 home 目录赋值时误用了大小写不敏感的只读自动变量
`$HOME`，因此控制台额外出现一次 `Cannot overwrite variable HOME`。该赋值是非终止
错误，正式 Python preflight 仍按上表 exit=`0` 并完成全部断言；外层日志记录
`OUTER_EXIT_CODE=0`。随后只读审计确认它没有创建 GDB/Python 用户历史文件，除已授权的
SEGGER 配置外未产生额外项目外写入。该包装错误不重跑、不改写 preflight 计数。

### 29.3 唯一正式 PATCH 上传：1/1 KEEP_BLOCKED

preflight 完整 PASS 后，按授权只启动一次正式上传：

- 输入：`.cache/p2-6-sd-ota/assets/P2-6A-PATCH-v2.8.0-to-v2.8.1.etu`
- 输入字节：`305`
- 输入 SHA-256：
  `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B`
- 唯一 MCU 目标：
  `/P2-6-RUN-20260820-01/P2-6A-PATCH-SD-R2-A7F3.etu`
- 前缀：`p2-6-sd-r2-patch-upload-hw-1`

Python 上传进程实际启动，因此 P2-6-SD-R2 正式 PATCH 上传计数固定为 `1/1`。它以
exit=`1` 结束，错误为：

```text
P2_6_RTT_SD_UPLOAD=FAIL GDB/RTT session failed: DriverError: J-Link GDB server readiness timeout after 45.0s
```

result JSON 和 server 日志给出精确边界：

- `server_started=true`
- `server_pid=18492`
- `server_exit_code=1`
- `gdb_started=false`
- `gdb_exit_code=null`
- `rtt_connected=false`
- `capture_stopped=true`
- `ports_closed=true`
- `session_error="DriverError: J-Link GDB server readiness timeout after 45.0s"`
- server 日志最后停在 `Connecting to J-Link...`
- GDB 日志未创建
- RTT 日志未创建
- readback 未创建，`readback_bytes/readback_sha256=null`

因为 GDB 从未启动，生成脚本中的 `target remote`、状态门禁和全部 `lv_fs_*` 调用均未被
执行。本次没有调用 `lv_fs_open`、`lv_fs_write`、`lv_fs_close`，没有创建或写入上述
MCU SD 目标文件，也没有烧录 Flash。`readback_matches=false` 只是未运行 GDB 后的空结果
字段，不能分类为产品读回失败或 PRODUCT_FAIL。

原始证据：

| 文件 | 时间戳 | 字节 | SHA-256 |
|---|---|---:|---|
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-patch-upload-hw-1-outer.log` | `2026-08-20T22:13:20.7758034+08:00` | 129 | `5F5F1F1552020E005E8996FF2F33C748A044FB311891C9E7BA358866220BC528` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-patch-upload-hw-1-result.json` | `2026-08-20T22:13:20.6004671+08:00` | 3019 | `AD0B472634994464CC07B5746D539E627794FE69128BC3D5E9E290DF135B1904` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-patch-upload-hw-1-jlink-server.log` | `2026-08-20T22:12:35.0546775+08:00` | 1124 | `0FD29570C3C0D033E5C1AB739C3DE79C1E4A29940C55A9D21F3B62A5C8E0477D` |
| `.cache/p2-6-sd-r2/tmp/p2-6-sd-r2-patch-upload-hw-1/upload.gdb` | `2026-08-20T22:12:34.2628089+08:00` | 22067 | `BE2A82FEBCFCA714DB5B050BECF1BA85AB9A91901122CD2C6761A8675C5A9213` |
| `.cache/p2-6-sd-r2/tmp/p2-6-sd-r2-patch-upload-hw-1/mcu-path.bin` | `2026-08-20T22:12:34.2589047+08:00` | 49 | `514D1F627180BAF57FA3114389CD6A28B149C6BC3D2E89904A064EAA4911C2AD` |
| `.cache/p2-6-sd-r2/tmp/p2-6-sd-r2-patch-upload-hw-1/source-000.bin` | `2026-08-20T22:12:34.2569499+08:00` | 305 | `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` |

这是 preflight 后出现的新 transport/HARNESS 失效，且正式上传额度已经消耗。按本轮
明确规则，只要正式上传 exit 非 0 即立即停止并置 P2-6 为阻塞；因此没有第二次 PATCH
上传、没有改目标路径重试、没有 PATCH OTA、FULL 上传/OTA、异常退出或 LiveMap 恢复
验证，也没有自动开启 R4/R5。

### 29.4 C 项分类、设备状态与文件系统审计

本轮增量分类：

| C 项 | 结论 | 本轮依据 |
|---|---|---|
| C1 | `NOT_OBSERVED` | FULL 上传/OTA 未启动 |
| C2 | `NOT_OBSERVED` | PATCH 资产未上传，PATCH OTA 未启动 |
| C3 | `PASS` | 沿用 §24 正式静态闭环，不运行 R3-3 |
| C4 | `NOT_OBSERVED` | 无真实 OTA 核心窗口 workspace 记录 |
| C5 | `NOT_OBSERVED` | 无真实 OTA 核心窗口 sbrk 记录 |
| C6 | `NOT_OBSERVED` | 无真实 OTA 核心窗口 required TLSF 记录 |
| C7 | `NOT_OBSERVED` | 异常退出和 LiveMap 重建未启动 |
| C13 | `PASS` | 沿用 §24 measurement-validity 正式结论 |
| C14 | `NOT_OBSERVED` | 无真实 OTA 核心窗口 auxiliary LVGL 池观测 |
| C16 | `PASS` | 沿用 §24 七项迁移性/静态结论 |

C8-C12、C15 的既有宿主、链接和构型证据不变。本轮没有形成 workspace 超过 `40960B`、
栈超过 `8192B`、guard 损坏、sbrk/LVGL required 分配增量非零或其他产品门槛失败证据。

设备最后可信的完整状态来自 29.2 preflight：test v2.8.0 身份、BCB `CONFIRMED`、
`SD_IsReady=1`、`VTOR=0x08010000`、`CFSR=0`、overlay `FREE`。正式上传阶段未能连接
J-Link 且 GDB 未启动，故没有后续目标命令、文件 API 或 Flash 操作；同时也没有新的
上传后设备读数，不能把 preflight 状态冒充为上传后重新观测值。

收尾审计：

- P2-6 状态改为 **阻塞 / KEEP_BLOCKED**，等待新的非实现协调裁定。
- preflight 固定 `1/1 PASS`；正式 PATCH 上传固定 `1/1 KEEP_BLOCKED`。
- 旧 PATCH 上传仍为 `3/3`，stack closure R3 仍为 `2/3`；均未重跑。
- 没有创建或写入本轮 MCU SD 目标文件，没有主机侧 `E:` 写入，没有烧录 Flash。
- J-Link/GDB/RTT 残留进程为 0，端口 `24361-24364` 监听为 0。
- 已授权项目外文件 `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 在 preflight
  时 mtime 更新为 `2026-08-20T22:10:20.7725912+08:00`，大小仍为 986B，SHA-256 仍为
  `DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`；正式上传没有再次
  改变它。未发现其他本会话主动项目外写入。
- 四个用户要求保留的 RTT/GDB 工具/单测仍原样保留；新增 preflight 与单测也保留，
  且这些文件在生产 CMake/固件构型中仍为零引用。
- 六个指定历史未跟踪文件未修改、删除、移动或提交。
- 未执行 commit、push、merge、rebase、stash、独立验收、P3/P4 或 Cloudflare，未创建
  `docs/acceptance-contracts/P2-6-v1.contract.json`。

## 30. P2-6-SD-R2 非实现阻塞裁定（2026-08-20）

### 30.1 裁定编号、日期与角色边界

- 裁定编号：`P2-6-BR-20260820-SD-R2-01`
- 裁定日期：`2026-08-20`
- 裁定结果：**`KEEP_BLOCKED`**

本节由 P2-6 非实现协调/阻塞裁定 agent 完成，不是当前实现 agent，也不是独立验收
agent。本次只读审查 P2-6-SD-R2 的停止证据，并仅回填
`PLAN-OTA-EXEC.md` 与本实现证据文档。未运行 J-Link、GDB、RTT、烧录、SD 写入、测试、
构建或任何真机命令；未重跑旧 PATCH `3/3`、未执行 SD-R2 第二次上传、未运行
stack closure R3-3，也未创建验收合同。

### 30.2 审查输入与 SHA-256

下表中的看板与实现证据哈希是本裁定写入前的只读输入哈希；裁定回填后文件哈希会按
预期变化。

| 文件 | SHA-256 |
|---|---|
| `AGENTS.md` | `B0F548E3B0F9ECFD73CB315AA30F2C731AE4FE04DF13DDAD413CA19FA5EB4EAE` |
| `PLAN-OTA-EXEC.md`（裁定前） | `FA9702749E7357CD1C3AE40E436B37BD8051174E5934A404AAC860BB29124FF3` |
| `docs/ota-prompts/prompt-P2-6-implementation.md` | `2394F76F7FEBE4B3A6F9B8C332C5CC9263FFF53F782F6CF672FDCF1EB60F218F` |
| 本实现证据文档（裁定前） | `629983F362411F6523A1BFCB08FA6E21789CF3CD5E3B6CD751C777F053BAE985` |
| `docs/acceptance-execution-contract.md` | `598C2A2BEC4E9CEC1E00591A5A537972024449CB896192D5066A6822452D5F52` |
| `tests/ota/p2_6_rtt_ota_driver.py` | `BD79AC5F23B9FCA638B0A482BB32B3139D83BD111FE7952FB813F644E45A74EF` |
| `tests/ota/p2_6_rtt_sd_uploader.py` | `36C4ABFF5829BDB9495CAFE16CD5D524EFE1691D4820CE714C37C1B6439F08A0` |
| `tests/ota/p2_6_rtt_sd_preflight.py` | `59524394DB2C8EC0D25927F92CBBE18F855CAE625EB905F28DE871C0A093D29D` |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | `79CBB52F033AF11B181F9D3D6076278F8963F5AF1AC90D3AB204793DCB26E524` |
| `tests/ota/test_p2_6_rtt_sd_uploader.py` | `80FB8797E77A632BF4BDD4EE39F335BABF77A456E4020B8BC0D5989C5F851F90` |
| `tests/ota/test_p2_6_rtt_sd_preflight.py` | `F447625AF5C580939316555C334FCE291AFA6F372DF9F57BF3EEA9A9AABEE1DC` |

P2-6-SD-R2 当前轮次证据：

| 证据 | SHA-256 |
|---|---|
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-preflight-hw-1-result.json` | `AAFADB9A8EC0606178940678E1697EF1933AF93EFDC078EF86C203FBE7811DC7` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-preflight-hw-1-gdb.log` | `5AFCDCD917CC6A1A5486DC06AB7D583B3EB1377EBD5A71161A23A6DDF27904B1` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-preflight-hw-1-jlink-server.log` | `B6B091F2FD1FBA2B1E849FC2F6C53455D865535FF4AAF97EACBC480742602E05` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-patch-upload-hw-1-result.json` | `AD0B472634994464CC07B5746D539E627794FE69128BC3D5E9E290DF135B1904` |
| `.cache/p2-6-sd-r2/logs/p2-6-sd-r2-patch-upload-hw-1-jlink-server.log` | `0FD29570C3C0D033E5C1AB739C3DE79C1E4A29940C55A9D21F3B62A5C8E0477D` |
| `.cache/p2-6-sd-r2/tmp/p2-6-sd-r2-patch-upload-hw-1/upload.gdb` | `BE2A82FEBCFCA714DB5B050BECF1BA85AB9A91901122CD2C6761A8675C5A9213` |
| 冻结 PATCH（305B） | `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` |

§26.4 旧 PATCH `3/3` 的 result/GDB/server/RTT/script 原始证据也已逐项复核，哈希与
§26.4 一致：

| 旧次数 | result | GDB | server | RTT | script |
|---:|---|---|---|---|---|
| 1 | `82190AF48ACBB4716ECC5279ED63BE8AF2F59018E7B7AF266E221F533E0E20F9` | `F5C25047C1F03E4C8395D323DCEB0149298A6678990F43571DD79BB74D418B5B` | `2B89307DEB649B385A1F72BCA425AF7024A97E166196FEB14C04F627D19FA04B` | `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` | `84CA7899560DD16426B67805CB3302226E768C9E3DF2D0A754B0CABF413CCE0D` |
| 2 | `9A752924D67476F7DBD6FBF2765488AA497BF14C6B9D5D8D067693231C542E4A` | `51F5CE00EEB3214CE627AF2045A5B98A1C42179EF0A99665C2637E0202E96318` | `518881BF53850588B0B70FC24C61BF6AD07C00FEC35C55ECAE65622ED4A50421` | `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` | `63ABAFC0521AF6FE150A21622CB55C08F85B4CAED04637C00B4B94DBB0399970` |
| 3 | `55C35396542CF645FEDAF75A81664CD3C5D9A46BC85B2FB55F22171AEE784D88` | `0B4E8B4333FC2AE9CE4B225A31E64D98186E5599C9AEB90C9D278CF5B1E4BF13` | `55922078B5E2081BB9D877C613D0762BF2E92E5F1EF13FF3A57E3F99DA4DFF71` | `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` | `254918340933DD76C93148E145976833A4FDF07F1DB0F622A0F95CE4DD50DCAF` |

### 30.3 失败分类与证据边界

P2-6-SD-R2 的正式 PATCH 上传分类为：

**`ENV_BLOCKED / TRANSPORT_NOT_READY`**。

这不是 `PRODUCT_FAIL`。J-Link GDB Server 进程虽然已启动，但日志只到
`Connecting to J-Link...`，45 秒内没有出现 `Waiting for GDB connection...`；因此
`gdb_started=false`、`rtt_connected=false`、`gdb_exit_code=null`。上传脚本没有执行，
`target remote`、固件身份/状态门禁、`lv_fs_open/write/close`、完整读回和 Flash 操作均
未发生。`readback_matches=false` 只是未创建 readback 后的默认结果字段，不能作为产品
读回失败。

本次也不应继续笼统分类为 `HARNESS_FAIL`。`run_gdb_session()` 在 server readiness
标记出现前不启动 RTT 或 GDB，超时后终止并等待 server、关闭日志流并确认四个监听端口
关闭；这些门禁在本次正确 fail-closed。当前没有证据证明 runner、探针或生成脚本不可信。
按 `docs/acceptance-execution-contract.md` §2，当前环境或外部设备无法执行必需步骤应记
`ENV_BLOCKED`。

但 `ENV_BLOCKED` 也不能被解释成“可能只是连接问题，所以再试一次”。同一
`JLinkGDBServerCL.exe` 命令在 `22:10` 的 preflight 完整成功，约两分钟后在正式上传却
无法越过 `Connecting to J-Link...`。现有单测只覆盖端口唯一性、脚本内容、符号、MI
读回和页面解耦，没有覆盖：

- server readiness timeout 的生命周期与分类；
- 一次成功 attach/detach 后的第二次连续 server acquisition；
- `ports_closed=true` 之外的进程退出、USB handle、probe 枚举和 DAP 可重入状态；
- 连续会话时新旧 PID、日志和 transport 状态完全隔离。

因此当前证据只能把失败定界到“产品路径之前的 J-Link transport readiness”，不能把
根因进一步定界为可由哪一处 `tests/ota/` 修改可靠消除。没有证据支持通过延长 45 秒、
直接重启、固定 sleep、自动 retry、改端口或换目标路径来恢复。

### 30.4 C1-C16 分类矩阵增量

| C 项 | 当前分类 | 本裁定增量 |
|---|---|---|
| C1 | `NOT_OBSERVED` | FULL 上传/OTA 未启动 |
| C2 | `NOT_OBSERVED` | PATCH 未写入 SD，PATCH OTA 未启动 |
| C3 | `PASS` | 沿用 §24 静态闭环；不运行 R3-3 |
| C4 | `NOT_OBSERVED` | 无真实 OTA 窗口 guard 观测 |
| C5 | `NOT_OBSERVED` | 无真实 OTA 窗口 sbrk 增量 |
| C6 | `NOT_OBSERVED` | 无真实 OTA 窗口 required TLSF 增量 |
| C7 | `NOT_OBSERVED` | 异常退出与 LiveMap 重建未启动 |
| C8 | `OBSERVED`（既有结论不变） | 本轮无新 GCC 主 RAM 证据 |
| C9 | `OBSERVED / auxiliary`（既有结论不变） | 本轮无新 AC5 证据 |
| C10 | `PASS`（既有结论不变） | 宿主 FULL 容量边界不受影响 |
| C11 | `PASS`（既有结论不变） | 宿主 PATCH 容量边界不受影响 |
| C12 | `PASS`（既有结论不变） | 生产零命中构型证据不受影响 |
| C13 | `PASS` | 沿用 §24 measurement-validity 正式结论 |
| C14 | `NOT_OBSERVED` | 无真实 OTA 窗口 auxiliary LVGL 池观测 |
| C15 | `PASS`（既有结论不变） | TEST_ENABLE 正向命中证据不受影响 |
| C16 | `PASS` | 沿用 §24 七项迁移性/静态闭环结论 |

本次没有形成 workspace 超过 `40960B`、栈超过 `8192B`、guard 损坏、sbrk/LVGL
required 分配增量非零或其他产品门槛失败证据。

### 30.5 P2-6 状态与新轮次裁定

P2-6 必须继续保持 **阻塞 / `KEEP_BLOCKED`**。本裁定不授权：

- `P2-6-SD-R3` 或任何其他新正式验证轮次；
- P2-6-SD-R2 第二次正式 PATCH 上传；
- 重启 J-Link、GDB、RTT 或执行 transport 诊断；
- 修改 `tests/ota/` harness；
- PATCH OTA、FULL 上传/OTA、异常退出、LiveMap 重建或独立验收。

准确原因不是产品超限，而是当前无法在不执行新硬件诊断的情况下给出非盲重试边界。
如果此时授权新轮次，唯一实际动作仍是再次运行同一 J-Link acquisition，不能证明它与
SD-R2 的失败条件有任何实质区别。

解除本次 `KEEP_BLOCKED` 前，需要用户或规范维护会话另行处理以下事项；这些事项**不是
本裁定的执行授权**：

1. 明确授权一个独立于 P2-6 正式证据轮次的 transport-only 整改/资格验证范围，并
   重新处理 J-Link 可能更新 `JLinkDLL.ini` 的准确项目外写入授权。
2. 在 `tests/ota/` 内建立可鉴别的离线生命周期门禁，至少覆盖 readiness timeout、ready
   前绝不启动 RTT/GDB、server 终止并 wait/close、连续两次 acquisition 状态隔离、以及
   `ENV_BLOCKED` 与 `HARNESS_FAIL` 的分类；全部离线门禁必须干净通过。
3. 经单独授权后，只执行无 SD/Flash 的只读 transport 资格验证，证明一次成功
   attach/detach 后能够再次取得 J-Link/server/target readiness，并绑定两个独立 PID、
   完整 server 日志和收尾状态；若仍失败，必须捕获足以区分 probe/USB/DAP 与 runner
   生命周期的原始证据，而不是继续重试。
4. 上述证据闭合后，再由新的非实现协调裁定决定是否创建 `P2-6-SD-R3`。即使未来
   授权，旧 PATCH `3/3`、SD-R2 preflight `1/1 PASS` 和正式上传 `1/1` 都不得清零、
   重解释或合并计数。

### 30.6 文件系统与禁止事项审计

本裁定会话主动修改的文件仅为：

- `PLAN-OTA-EXEC.md`
- `docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md`

两者均位于 `D:\github\my\E-Track` 内，文件及父目录均不是 reparse point。本裁定没有
产生项目外写入。只读复核的既有授权文件
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 仍为 986B，mtime
`2026-08-20T22:10:20.7725912+08:00`，SHA-256
`DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`；本裁定未恢复、
删除、覆盖、清理或修改它。

没有执行硬件动作，没有重跑旧轮次，没有创建或写入 SD 目标文件，没有烧录 Flash，
没有修改生产源码、测试脚本、冻结提示词、冻结数字、静态闭环路线、二进制合同或
`PLAN-OTA.md`；没有执行 P3/P4、Cloudflare、独立验收、commit、push、merge、rebase
或 stash，也没有创建 `docs/acceptance-contracts/P2-6-v1.contract.json`。

## 31. P2-6-TR-R1 transport-only 整改、资格验证与阻塞裁定（2026-08-21）

### 31.1 裁定编号、角色与授权边界

- 裁定编号：`P2-6-BR-20260821-TR-R1-01`
- 裁定日期：`2026-08-21`
- 裁定结果：**`KEEP_BLOCKED`**
- 资格轮次：`P2-6-TR-R1`，一次执行内最多两个连续只读 attach/detach session；首个
  session 失败即停止，不重试。

本节由 P2-6 非实现协调/阻塞裁定 agent 完成。用户明确授权 transport-only harness
整改、项目内离线生命周期测试，以及不调用 SD/Flash 写入的 J-Link/GDB/RTT 资格验证；
同时授权 SEGGER 在本次 P2-6 真机资格期间仅更新
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`。本轮没有授权 PATCH/FULL 上传、OTA、
烧录、stack closure、独立验收、验收合同或 Git 远端操作。

旧计数全部保持原样：旧 PATCH 上传 `3/3`，P2-6-SD-R2 preflight `1/1 PASS`，
P2-6-SD-R2 正式上传 `1/1` 非零，stack closure R3 `2/3` 且禁止 R3-3。`P2-6-TR-R1`
独立于这些轮次，不清零、不重解释也不合并计数。

### 31.2 transport-only 整改与离线门禁

本轮只修改或新增以下 test-only 文件：

- `tests/ota/p2_6_rtt_ota_driver.py`
- `tests/ota/test_p2_6_rtt_ota_driver.py`
- `tests/ota/p2_6_rtt_transport_qualifier.py`
- `tests/ota/test_p2_6_rtt_transport_qualifier.py`

整改后的 `run_gdb_session()` 不再在 GDB 返回后立即 terminate J-Link server。它先给
`-singlerun` server 一个 10 秒有界自然退出窗口，仅在超时后才按已记录 PID 执行
terminate，仍不退出时才 kill；结果显式记录 server readiness、PID、readiness 延迟、
自然退出、terminate/kill、退出码、收尾耗时、RTT/GDB 启动状态、端口关闭和 transport
分类。GDB 以 `-nx` 启动，`HOME`、`USERPROFILE`、`TEMP/TMP/TMPDIR` 和 pycache 均重定向
到项目内资格临时目录。

新增 qualifier 将一次正式资格执行固定为最多两个连续且相互独立的 server/GDB/RTT
session。每个 GDB 脚本只做 `target remote`、`monitor halt`、冻结 v2.8.0 fw_header 比较、
RTT 签名、`SD_IsReady`、VTOR、CFSR 和 overlay owner 只读检查，随后 detach/quit；禁止
`lv_fs_*`、`loadfile/loadbin/verifybin`、`restore`、Flash、`continue`、目标函数调用和目标
内存写入。第一 session 不完整通过时，第二 session 永不启动。

离线结果：

- `py_compile`：exit `0`。
- 定向 unittest：`27 PASS / 0 FAIL / 0 ERROR / 0 SKIP`，`Ran 27 tests in 1.208s`。
- 冻结输入静态门禁：ELF
  `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`，map
  `2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13`，test v2.8.0
  image `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5`，全部与冻结记录
  一致。
- session 1/2 GDB 脚本均为 122 行，SHA-256 分别为
  `B17C4F2C9CF8546C19FFEF82E25C84BFEAEBB49676C897B3EE925F396A63C5A1`、
  `AC2A7F1066B95953C45541C3540CFCAEF699F131DF480D5E049B0EAF46C0B2D5`；静态禁止项零命中。

最终 test-only 文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| `tests/ota/p2_6_rtt_ota_driver.py` | `46206A97FC17095FB94B8FDBE081A4D5F74477E19AA14FD7DEE72414AB8F257D` |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | `CA9D421CCDD50421F65FE3569C2302D3F3529838E8B8FC16307FFB95FF8DFE95` |
| `tests/ota/p2_6_rtt_transport_qualifier.py` | `8A95B12C9A066A5B07D346252C6AEA1C9FA3585E7C57F150456704943951D896` |
| `tests/ota/test_p2_6_rtt_transport_qualifier.py` | `56B205E2C50A5699F4BFABE0180D455314AAB3783A20B419E37DD15C5268AF82` |

### 31.3 启动前工具路径错误不计入资格 session

第一次调用 qualifier 时显式 GDB/NM 路径把目录 `13.3.rel1-ming` 误写为
`13.3.rel1.ming`。资格器在 `arm-none-eabi-gdb/nm is unavailable` 前置检查处 exit `1`；
J-Link server、GDB、RTT 均未启动，结果文件和 session 日志均未创建，因此
`P2-6-TR-R1` 硬件 session 计数仍为 `0/2`。该启动前失败未被重解释为资格通过，也没有
触发任何产品或设备动作。随后只读确认正确工具路径后，才启动下述唯一正式资格执行。

### 31.4 唯一正式资格执行结果

资格 result：

- `.cache/p2-6-transport-r1/logs/p2-6-tr-r1-hw-1-result.json`
- SHA-256：`321ADDECD57D2E7CB9E68C712EAEA3D5C1D80E8240F23AC28D1593BA313218E5`

session 1 server 日志：

- `.cache/p2-6-transport-r1/logs/p2-6-tr-r1-hw-1-session-1-jlink-server.log`
- SHA-256：`0FD29570C3C0D033E5C1AB739C3DE79C1E4A29940C55A9D21F3B62A5C8E0477D`

关键事实：

- `server_started=true`，PID `348`。
- 45 秒内没有出现 `Waiting for GDB connection...`，server 日志再次停在
  `Connecting to J-Link...`。
- `server_ready=false`，`gdb_started=false`，`rtt_connected=false`，
  `gdb_exit_code=null`。
- GDB 日志和 RTT 日志均未创建，所有资格 marker 计数均为 `0`。
- readiness 失败后先等待 10 秒自然退出；server 未自然退出，随后才执行 terminate，
  `server_exit_code=1`、`server_process_exited=true`、`ports_closed=true`，无残留进程或端口。
- session 1 分类为 `TRANSPORT_NOT_READY`，资格执行结果为 `qualification_pass=false`。
- 按首失败即停规则，session 2 没有启动；没有 retry、第三次 acquisition、上传或 OTA。
- 资格停止后执行的 Windows PnP 只读枚举显示唯一 J-Link 匹配设备当前存在且状态为
  `OK`：class=`USB`、friendly name=`J-Link driver`、instance ID=
  `USB\VID_1366&PID_0101\000000123456`。该枚举未启动 J-Link、GDB 或 target acquisition，
  不消耗资格次数。

### 31.5 失败分类、产品边界与 C1-C16 增量

本次正式资格失败分类为：

**`ENV_BLOCKED / TRANSPORT_NOT_READY`**。

它不是 `HARNESS_FAIL`：离线生命周期门禁已覆盖 readiness 前不得启动 RTT/GDB、自然退出
优先、强制收尾兜底、连续独立 PID 和首失败即停；本次 runner 按设计 fail-closed，原始
server 日志也与 SD-R2 的 readiness 失败逐字节同哈希。它也不是 `PRODUCT_FAIL`：GDB 未
连接 target，冻结固件身份和状态检查未执行，且没有任何 `lv_fs_*`、SD 文件、目标内存
写入、Flash 或 OTA 行为。PnP 又确认 USB 设备已经枚举且状态 `OK`，因此不能把失败简单
归因于“USB 完全未插”；当前证据将根因边界收紧为 runner 之外或低于 runner 的已枚举
J-Link probe 取得/USB handle/firmware readiness，而不是 P2-6 产品实现。

| C 项 | 当前分类 | 本轮增量 |
|---|---|---|
| C1 | `NOT_OBSERVED` | FULL 上传/OTA 未启动 |
| C2 | `NOT_OBSERVED` | PATCH 上传/OTA 未启动 |
| C3 | `PASS` | 沿用 §24，未运行 R3-3 |
| C4-C7 | `NOT_OBSERVED` | 无真实 SD OTA 窗口 |
| C8-C12 | 既有结论不变 | transport 资格未产生新产品证据 |
| C13 | `PASS` | 沿用 §24 measurement-validity 结论 |
| C14 | `NOT_OBSERVED` | 无真实 OTA 窗口 LVGL 池观测 |
| C15 | `PASS` | 既有 TEST_ENABLE 证据不变 |
| C16 | `PASS` | 沿用 §24 静态闭环结论 |

没有 workspace 超过 `40960B`、栈超过 `8192B`、guard 损坏、sbrk/TLSF 增量、SD 写入
或其他产品门槛失败证据。

### 31.6 状态与后续裁定

P2-6 继续保持 **阻塞 / `KEEP_BLOCKED`**。本轮不授权：

- `P2-6-SD-R3` 或其他上传/OTA 轮次；
- `P2-6-TR-R1` session 2、retry 或新的 acquisition；
- 旧 PATCH `3/3`、SD-R2 `1/1` 或 stack R3-3 的任何重跑；
- 独立验收或验收合同。

准确原因是：transport-only 整改已闭合可控 server 生命周期缺口，但唯一资格执行仍在
J-Link USB/probe acquisition readiness 前失败，未取得一次成功 attach/detach，更无法证明
连续第二次 acquisition 可重入。此时直接授权 SD-R3 仍然只是把产品验证暴露给同一个未
通过资格的 transport，不构成受控验证边界。

解除阻塞需要用户或设备/环境维护会话先恢复并只读证明 J-Link probe 能稳定完成至少一次
acquisition；之后必须由新的非实现协调裁定决定是否允许一个新的 transport qualification
ID。不得在本轮内通过拔插、重启、延长 timeout、换端口或自动 retry 继续尝试。

### 31.7 文件系统与禁止事项审计

本轮主动项目内输出位于：

- 上述四个 `tests/ota/` test-only 文件；
- `PLAN-OTA-EXEC.md` 与本实现证据文档；
- `.cache/p2-6-transport-r1/` 下的 pycache、测试临时文件、离线日志、资格脚本和原始证据。

项目外审计文件
`.cache/p2-6-transport-r1/logs/qualification-external-write-audit-r1.json` 的 SHA-256 为
`17A6BA02F54F1FB950376A3A4B3E0AE517F25F291D0E14A0E10B48D7A6E5B6F9`。SEGGER 目录前后
快照完全一致：授权的 `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 仍为 986B，
mtime `2026-08-20T14:10:20.7725912Z`，SHA-256
`DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`；本轮没有实际改变
该文件，也未发现其他项目外写入。未恢复、删除、覆盖或清理任何项目外文件。

没有运行 PATCH/FULL 上传、OTA、烧录、SD 写入、stack closure 或独立验收；没有重跑旧
轮次，没有创建 `docs/acceptance-contracts/P2-6-v1.contract.json`，没有修改生产源码、
冻结提示词、冻结数字、静态闭环路线、二进制合同或 `PLAN-OTA.md`；没有执行 P3/P4、
Cloudflare、commit、push、merge、rebase 或 stash。六个历史未跟踪文件保持原样。

## 32. P2-6-TR-R2 transport recovery 独立审计与 P2-6-SD-R3 授权裁定（2026-08-23）

### 32.1 角色、范围与冻结事实

本节由 P2-6 非实现协调/阻塞裁定 agent 完成。只审计最新 transport-only
只读双 session 证据，不执行 SD 上传、OTA、Flash/SD 写入、烧录、J-Link/GDB/RTT
硬件操作、stack closure、独立验收或 Git 远端操作。只允许回填本证据文档和
PLAN-OTA-EXEC.md。

冻结事实全部保持不变：stack closure R3=2/3，禁止 R3-3，C3/C13/C16 沿用 PASS；
最初 PATCH=3/3，禁止第四次；SD-R2 preflight=1/1 PASS；SD-R2 正式 PATCH=1/1
ENV_BLOCKED/TRANSPORT_NOT_READY，禁止重跑；C1/C2、C4-C7、C14 仍无真实 SD OTA
窗口证据；不创建 docs/acceptance-contracts/P2-6-v1.contract.json，不独立验收，
不 commit/push/merge/rebase/stash。

### 32.2 哈希复算

以下 SHA-256 均由本会话独立 Get-FileHash 复算并与用户冻结值/JSON 内值匹配：

| 证据 | SHA-256 |
|---|---|
| AGENTS.md | B0F548E3B0F9ECFD73CB315AA30F2C731AE4FE04DF13DDAD413CA19FA5EB4EAE |
| PLAN-OTA-EXEC.md（写入前） | 6E1367ACBB3039E26728B6E1F00CF1A6ECB169086B4594ABD84318A4E22FA8EA |
| docs/ota-prompts/prompt-P2-6-implementation.md | 2394F76F7FEBE4B3A6F9B8C332C5CC9263FFF53F782F6CF672FDCF1EB60F218F |
| 本证据文档（写入前） | 80A5647302E3117BCC79DF5F07C569FB9E4E804DCBE87889CA8A05662F7035E8 |
| tests/ota/p2_6_rtt_transport_qualifier.py | 8A95B12C9A066A5B07D346252C6AEA1C9FA3585E7C57F150456704943951D896 |
| tests/ota/p2_6_rtt_ota_driver.py | 46206A97FC17095FB94B8FDBE081A4D5F74477E19AA14FD7DEE72414AB8F257D |
| tests/ota/test_p2_6_rtt_transport_qualifier.py | 56B205E2C50A5699F4BFABE0180D455314AAB3783A20B419E37DD15C5268AF82 |
| result JSON | C166055F467AD60F7C527DEA53EB635404315AB51247F2F4010A3C101B35929F |
| test ELF | 35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019 |
| test map | 2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13 |
| test v2.8.0 image | AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5 |
| session 1 GDB script | B17C4F2C9CF8546C19FFEF82E25C84BFEAEBB49676C897B3EE925F396A63C5A1 |
| session 2 GDB script | AC2A7F1066B95953C45541C3540CFCAEF699F131DF480D5E049B0EAF46C0B2D5 |
| session 1 GDB log | 7A4092C1AF06675E537B8FB15466197CF8C7A58CF540C7A0156D87041AAA31E6 |
| session 1 server log | 9059BF7B8A7EB3507192981E57935EDC6F170D8B6851C12310B936E0642F031B |
| session 1 RTT log | D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0 |
| session 2 GDB log | 7D5611AD2B8690CC2EBBD2EFBFBF4F5A4C9C8010BB86362D9D24333802560A25 |
| session 2 server log | 9774DE46621BD456D1F9007AF40D4CBBEA7999069E863F711A88E795650C7001 |
| session 2 RTT log | D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0 |
| fw_header 96B at image offset 0x400 | AB40E59EC6DB9E69ABEF88D22F7999FAD222FF3F6F9751251AE0A388C7808BFB |
| SEGGER JLinkDLL.ini | DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0 |

### 32.3 日志与 session 语义

result schema 为 p2-6-rtt-transport-qualification-v1，sessions_attempted=2，
qualification_pass=true。session 1 使用独立 PID 21728、readiness 1.752 秒；
session 2 使用独立 PID 19976、readiness 0.306 秒。两轮都满足：
server_ready=true、gdb_started=true、gdb_exit_code=0、rtt_connected=true、
server_process_exited=true、server_natural_exit=true、server_terminate_sent=false、
server_kill_sent=false、capture_stopped=true、ports_closed=true、session_error=null、
transport_classification=PASS。

每份 GDB 日志各唯一出现 attached_stopped、固件头 IDENTITY PASS、STATE_PASS 和
最终 PASS marker，并以对应 session 编号标记。日志实际读取和验证的状态为：
固件头 96B 身份匹配；RTT 签名为 SEGGER RTT；SD_IsReady=1；
VTOR=0x08010000；CFSR=0；overlay owner=0；detach 成功。每份 server 日志均包含
J-Link is connected、Connected to target、Halting core、Waiting for GDB connection、
GDB client connected、Target halted、GDB closed TCP/IP connection 和 Shutting down。
两份 server 日志 socket 编号不同，哈希不同，不是同一日志重复引用。

### 32.4 只读脚本与收尾审计

两份脚本均 122 行。逐行检查确认只有 target remote、monitor halt、只读比较/读取、
detach、quit；file 只加载 ELF 符号。没有 Flash、SD API、lv_fs_open/write/close、
loadfile、loadbin、verifybin、restore、dump binary memory、continue、continue &、
interrupt、monitor reset/go/load、GDB call/函数调用、set 星号或其他目标内存写入。
脚本中的 set $name 只是 GDB convenience variable 赋值，右侧为目标只读表达式，
不写目标内存。

qualifier 首 session 通过后才启动第二个 session；没有 retry、第三次 acquisition 或
上传/OTA。当前 PID 21728 和 19976 均不存在；资格端口 24361、24362、24363、24364
LISTENING_COUNT=0；没有残留 J-LinkGDBServerCL、arm-none-eabi-gdb 或
JLinkRTTLogger 进程。SEGGER 配置当前为 986B、SHA-256
DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0；用户报告的本轮
前后 mtime/哈希快照不变。本裁定只读复核该外部文件，没有修改、恢复、删除、覆盖或
清理它，也没有发现其他项目外写入。

### 32.5 qualification_id 定性与 §30.5 裁定

JSON qualification_id=P2-6-TR-R1 来自 qualifier 源码硬编码旧 ID。冻结规范没有
要求该字段必须递增，也没有把字段值作为资格 PASS 门禁；本轮使用新的输出根
p2-6-transport-r2-20260823-01、新前缀 p2-6-tr-r2-20260823-01、独立日期时间、
两个不同 PID、独立日志和完整 SHA-256，足以与历史 TR-R1 唯一区分。因此将本 JSON
定性为新的 transport recovery qualification 证据，同时记录 legacy metadata defect。
禁止修改、覆盖、重命名或静默重标原始 JSON，禁止修改 qualifier harness；后续轮次
如仍产生 legacy 字段，只能如实记录，不得把它当作旧轮次重跑。

§30.5 的 readiness 生命周期、连续 acquisition、独立 PID/日志/收尾和外部配置审计
条件均已满足。裁定为 AUTHORIZED_RESUME，授权一个新的 P2-6-SD-R3 实现验证轮次。
Transport PASS 只解除 transport 阻塞，不改变产品结论，也不代表 P2-6 完成。当前
C1/C2、C4-C7、C14=NOT_OBSERVED；C3/C13/C16 沿用 PASS；其余既有 C 项不变。

### 32.6 P2-6-SD-R3 派单边界（完整提示词的冻结内容）

后续实现 agent 必须严格遵守以下全部条款：

1. 开始前必须阅读 AGENTS.md、PLAN-OTA-EXEC.md 的 P2-6 卡/§9/§10、冻结实现提示词
   §0.2/§1.1/§4.5/§4.7-§4.9-E/§6/§9、实现证据 §29-§32，以及现有
   tests/ota 的 transport/OTA/preflight 工具和对应单测；不得以旧日志、旧 map、旧
   RTT 地址或旧设备状态替代本轮输入。
2. 项目根 D:\github\my\E-Track，分支 p2-6-implementation-20260819，HEAD 和
   origin/main 均为 99173123cae8c487b86efa8a4eecbbe73b1bb512；本轮只做
   P2-6-SD-R3，不做 P3/P4/Cloudflare。
3. 旧 PATCH 3/3、SD-R2 preflight 1/1 PASS、SD-R2 正式上传 1/1
   ENV_BLOCKED/TRANSPORT_NOT_READY、stack R3 2/3 均冻结，不清零、不重跑、不重解释；
   C3/C13/C16 沿用 PASS，不运行 R3-3。
4. R3 开始前重新执行一次无 SD 写入 preflight。预检必须证明精确 test ELF/map/
   image、RTT、SD_IsReady=1、VTOR=0x08010000、CFSR=0、BCB CONFIRMED、overlay
   FREE、target stopped、GDB/RTT 收尾、无进程/端口残留；禁止 lv_fs_open/write/close、
   SD 文件创建、Flash 写入。首失败即停，禁止现场修后重跑。
5. 只允许一次 PATCH 上传，计为 R3 PATCH upload 1/1。输入、项目内日志根和 MCU/SD
   目标路径都必须是新的唯一实体；不得覆盖、删除、移动任何旧文件或旧路径。
6. 上传必须按现有 MI 分块协议执行，检查实际字节数；上传后完整读回，拼接结果
   SHA-256 必须逐字节等于输入 PATCH SHA-256。exit 非零、部分写入可能、缺块/
   乱序/重复/越界、SHA 不匹配或状态不确定立即停止，禁止第二次上传或改路径重试。
7. PATCH 上传完整 PASS 后，各只允许一次：PATCH OTA 核心窗口（C2/C4/C5/C6/C14）；
   FULL 上传与 FULL OTA（C1/C4/C5/C6/C14）；异常退出（C7）；LiveMap 恢复取证。
   不得以上传成功替代 OTA apply 或异常路径证据。
8. 任一新失效模式、HARNESS_FAIL、PRODUCT_FAIL、设备不可恢复、workspace 超过
   40960B、有效栈峰值超过 8192B、guard 损坏、sbrk 增量非零、required
   lv_tlsf_malloc/realloc 增量非零、free 非零且无法定位、C13 前置不通过或任何
   证据/收尾不确定，立即停止并等待新裁定，禁止自动重试。
9. 启动 J-Link 或写入项目外 SD/移动介质前，必须重新取得用户对准确外部路径、具体
   操作和副作用的明确授权；不得沿用历史授权。所有可控输出先做项目内写入预检。
10. 不得修改生产源码、冻结提示词、PLAN-OTA.md、二进制合同、冻结数字、静态路线、
   生产语义、当前 transport result JSON 或 qualifier legacy 字段；需要扩大范围先停。
11. 不得独立验收、创建验收合同、commit、push、merge、rebase 或 stash。C1/C2、
    C4-C7 全部闭合前只能回填“进行中/等待独立验收”，不能宣布完成。

### 32.7 文件系统审计结论

本裁定主动选择的写入目标只有 D:\github\my\E-Track\PLAN-OTA-EXEC.md 和
D:\github\my\E-Track\docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md。
两者及父目录均已规范化、位于活动 Git 根内且不是 reparse point。原始 cache、测试工具、
生产源码和项目外 SEGGER 文件未被修改。本裁定未执行任何硬件或 OTA 动作。

---

## 33. P2-6-SD-R3 静态前置闭合与 preflight 判据冲突停止（2026-08-23）

### 33.1 轮次身份与固定计数

本轮编号 `P2-6-SD-R3`，依据非实现裁定 `P2-6-BR-20260823-TR-R2-01=AUTHORIZED_RESUME`
（§32）派单。执行会话为实现验证会话，不做独立验收。

- 项目根 `D:\github\my\E-Track`，分支 `p2-6-implementation-20260819`
- `git rev-parse HEAD` = `origin/main` = `99173123cae8c487b86efa8a4eecbbe73b1bb512`
- 本轮输出唯一新根 `.cache/p2-6-sd-r3-20260823-01/`（受 `.gitignore:104:/.cache/` 忽略）

以下历史计数在本轮内**未清零、未重跑、未重解释、未合并**：

| 计数项 | 冻结值 | 本轮动作 |
| --- | --- | --- |
| stack closure R3 | `2/3`（禁止 R3-3） | 未执行 `tests/ota/test_p2_6_stack_closure.py` |
| C3 / C13 / C16 | 正式 `PASS` | 沿用，未重测、未与运行期采样拼接 |
| 最初 PATCH 上传 | `3/3`（禁止第四次） | 未执行 |
| P2-6-SD-R2 preflight | `1/1 PASS` | 未重跑 |
| P2-6-SD-R2 正式 PATCH 上传 | `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY` | 未重跑、未改路径重试 |
| P2-6-SD-R3 硬件 preflight | `0/1` | **未消耗**（见 §33.8 停止决定） |
| P2-6-SD-R3 PATCH 上传 | `0/1` | 未执行 |

### 33.2 项目内写入预检（AGENTS.md 非项目目录写入边界）

只读预检结论：

- 路径链 `D:\` → `D:\github` → `D:\github\my` → `D:\github\my\E-Track` → `.cache`
  逐级 `reparse=False`，无 symlink / junction / mount point。
- 新根规范化后相对路径 `.cache\p2-6-sd-r3-20260823-01`，`INSIDE_ROOT=True`，
  执行前**不存在**；最近已存在父目录 `.cache` 存在且非 reparse point。
- `.cache` 下 63 个既有目录全部枚举，新根与任一既有证据根/构建根无命名冲突。

### 33.3 冻结输入重绑定（本轮实测，不沿用旧记录）

| 输入 | 路径 | 字节数 | SHA-256 | 与 harness 冻结常量 |
| --- | --- | --- | --- | --- |
| test ELF | `.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.elf` | 866372 | `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019` | `FROZEN_TEST_ELF_SHA256` 匹配 |
| test map | `.cache/p2-6a-cmake-test-stack/app-gcc/X-Track-App-GCC.map` | 2423356 | `2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13` | `FROZEN_TEST_MAP_SHA256` 匹配 |
| 设备 image v2.8.0 | `.cache/p2-6-sd-ota/assets/X-Track-App-GCC-p2-6a-test-v2.8.0.finalized.bin` | 600744 | `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5` | `FROZEN_V280_IMAGE_SHA256` 匹配 |
| PATCH 输入 | `.cache/p2-6-sd-ota/assets/P2-6A-PATCH-v2.8.0-to-v2.8.1.etu` | 305 | `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` | `FROZEN_PATCH_SHA256` 匹配 |
| FULL 输入 | `.cache/p2-6-sd-ota/assets/P2-6A-FULL-v2.8.1.etu` | 282367 | `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7` | `FROZEN_FULL_SHA256` 匹配 |

设备固件头 SHA-256 `AB40E59EC6DB9E69ABEF88D22F7999FAD222FF3F6F9751251AE0A388C7808BFB`（96B）。

### 33.4 required 符号从本轮 test ELF 重绑定

`arm-none-eabi-nm -C --defined-only`（Arm GNU Toolchain 13.3.Rel1，nm 2.42）实测，
14 个 required 符号**全部唯一**（`count=1`），未沿用生产 map 的旧 RTT/SD 地址：

`App_Init()::manager=0x200504F8`、`vtable for Page::FirmwareUpdate=0x0809CB3C`、
`PageManager::Push=0x0803DB94`、`FirmwareUpdate::EnterPath=0x08045618`、
`SelectRow=0x08045710`、`StartImport=0x080457A8`、`FinishImport=0x08045074`、
`HAL::OTA_GetBcbState()=0x08040CCC`、`HAL::HAL_Update()=0x08040884`、
`strcmp=0x08052DB6`、`SD_IsReady=0x20053214`、`_SEGGER_RTT=0x20053E1C`、
`g_ota_overlay_owner=0x20053FA0`、`g_ota_overlay_workspace=0x20058000`。

`g_ota_overlay_workspace` 与 `ota_layout.h` 的 `OTA_OVERLAY_ORIGIN=0x20058000` 一致。
注意本轮 test 构型 `_SEGGER_RTT=0x20053E1C` / `SD_IsReady=0x20053214`，与 §25 生产 map
记录的 `0x20053E14` / `0x2005320C` 不同，**旧地址在本轮一律不可用**。

### 33.5 旧证据零改动基线

执行任何动作前先对五个既有根建立紧凑 manifest，落盘 `.cache/p2-6-sd-r3-20260823-01/baseline/`：

| 根 | 文件数 | 总字节 | manifest SHA-256 |
| --- | --- | --- | --- |
| `p2-6-sd-r2` | 182 | 3695741 | `812CDE88197E1692A526DDF2D4EF5DAD038BBA79708B9F769ABC599AD2F55902` |
| `p2-6-transport-r1` | 140 | 3430939 | `780287DACE26E81A9EF92FC6654E2B2AD48AE4BE6D8F7ECC4B27AC4B883F4CD7` |
| `p2-6-transport-r2-20260823-01` | 59 | 1274850 | `6665973EA2E7F838D6B8A2E83A102926A73A527814A173B4DFFFB07E4D340CF7` |
| `p2-6-sd-ota` | 171 | 5298361 | `B585C9F988F5D848171115C782660F0B7C407700997924646211F6E94BF35975` |
| `p2-6a-cmake-test-stack` | 813 | 18431456 | `400D9A3530EF899CE194D95CD14486F91DC7587747704D97AA1E3E5DF673E50D` |

三个 harness 单测在 `dir=` 硬编码处会于 `.cache/p2-6-sd-r2/tmp` 下创建
`TemporaryDirectory`（随机唯一名、退出自删）。修改测试即等于改 harness，为禁止项，
因此改为**跑完后逐根复算 manifest 证明零改动**：五个根 `files 不变 / manifest SAME`，
`ALL_OLD_EVIDENCE_UNCHANGED=True`。

manifest 口径（供独立复算）：逐行 `<仓库相对路径>|<字节数>|<大写 SHA-256>`，
路径用正斜杠、按路径升序，行间 `
`；落盘 `.manifest.txt` 末尾带一个换行，
而上表 `manifest SHA-256` 取**不含末尾换行**的表体哈希。
收尾复算同时校验两层：重建表体与落盘 `.manifest.txt` 逐字节相同
（`bytes_match=True`，即 1365 个文件的路径/大小/SHA-256 全部复现），
且表体哈希与上表一致（`manifest_match=True`）。

### 33.6 harness 离线回归

`python -m unittest -v` 对四个模块逐一执行，日志
`.cache/p2-6-sd-r3-20260823-01/offline/harness-unittests.log`：

| 模块 | 结果 |
| --- | --- |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | `Ran 13 tests ... OK` |
| `tests/ota/test_p2_6_rtt_sd_uploader.py` | `Ran 7 tests ... OK` |
| `tests/ota/test_p2_6_rtt_sd_preflight.py` | `Ran 3 tests ... OK` |
| `tests/ota/test_p2_6_rtt_transport_qualifier.py` | `Ran 4 tests ... OK` |

合计 `27 PASS / 0 FAIL / 0 ERROR / 0 SKIP`，warning=0、error=0。含真实硬约束：
`test_page_offsets_match_frozen_elf_disassembly`（objdump 反汇编断言页偏移）、
`test_preflight_required_symbols_are_unique_in_frozen_elf`（nm 实测
`HAL_UPDATE=0x08040884`、`OVERLAY_WORKSPACE=0x20058000`）。

### 33.7 无硬件 preflight 脚本静态审计（第四节禁止清单）

使用 `--prepare-only`（`hardware_started=false`，不启动 J-Link、不消耗唯一一次硬件
preflight）生成脚本并逐项审计。审计剔除 `printf` 字面量后只看可执行语义行，避免把
断言文本（如 `flash_calls=0`）误判为操作。

- 脚本 `.cache/p2-6-sd-r3-20260823-01/offline/tmp/p2-6-sd-r3-preflight-static.gdb`
- 151 行 / 7159B / SHA-256 `77E669A202CFDA74163006FE70687CE35AC859A97A8A8C735763CE09CBEDD3DA`
- 与 §29 中 SD-R2 已取得 `1/1 PASS` 的 `p2-6-sd-r2-preflight-final.gdb`
  **逐字节相同**（同 7159B、同 SHA-256）——生成确定，harness 与输入均无漂移

| 禁止项 | 结果 | 命中 |
| --- | --- | --- |
| Flash 操作 | CLEAN | — |
| `loadfile` / `loadbin` | CLEAN | — |
| `verifybin` | CLEAN | — |
| `restore` | CLEAN | — |
| `dump binary memory` | CLEAN | — |
| SD 文件 API `lv_fs_*` | CLEAN | — |
| 目标内存写入 `set *` | CLEAN | — |
| `continue &` | CLEAN | — |
| `interrupt` | CLEAN | — |
| `reset` / `go` | CLEAN | — |
| **`continue`** | **PRESENT** | 第 16 行，裸 `continue` |
| **函数调用** | **PRESENT** | 第 137 行 `set $bcb_preflight = ((unsigned char (*)(void))0x08040ccd)()` |

「不写 SD、不写 Flash、不写目标内存」这一实质目标成立
（`no_sd_write_objective_met=true`），但派单第四节清单中的 `continue` 与
「函数调用」两项确实命中。审计 JSON:
`.cache/p2-6-sd-r3-20260823-01/offline/logs/p2-6-sd-r3-preflight-static-audit.json`。

### 33.8 两处命中的技术定性与停止决定

两处命中都不是本轮引入，也不是缺陷，而是**冻结 harness 的必要设计**：

1. 第 16 行 `continue` 来自 `p2_6_rtt_ota_driver.py:314 deterministic_stop_lines()`。
   它先 `thbreak *0x08040884`（`HAL::HAL_Update()` 入口）并挂 `commands` 写入
   magic `0x50326201`，`continue` 之后立即双重校验 `magic` 与 `$pc`，任一不符即
   `quit 70`，随后 `delete breakpoints`。这是**受控前进到唯一确定停点**，不是自由
   运行；它正是 §28 为消除 SD-R2「异步 GDB 状态」`HARNESS_FAIL` 而引入的机制。
2. 第 137 行 inferior call 来自 `p2_6_rtt_ota_driver.py:426 runtime_state_lines()`。
   BCB 状态无法由纯内存读取得，必须调用 `HAL::OTA_GetBcbState()`（thumb 位 `|1`）；
   调用后紧接 `assert_stopped_at_lines()` 校验 `$pc` 仍为 `0x08040884`，
   上下文丢失即 `quit 71`。

派单第四节清单与冻结 harness 语义存在**判据错配**：看板 §565 记载的 SD-R2 preflight
冻结判据只禁止 `continue &`、`interrupt`、`restore`、`dump binary memory`（本轮全部
CLEAN）；而「无 `continue`、无函数调用」是看板 §568 / §577 中 **transport qualifier**
122 行只读脚本的判据（`p2_6_rtt_transport_qualifier.py:100 audit_read_only_script()`
的 forbidden 元组确实含 `continue` 与 `call `）。该清单被套用到 151 行 preflight 上，
而 preflight 在设计上必须包含这两者。冻结实现提示词
`docs/ota-prompts/prompt-P2-6-implementation.md` 全文检索 `continue|inferior|函数调用`
只命中第 1507 行 PowerShell 的 `-ErrorAction SilentlyContinue`，不存在该禁令。

本会话对此**无处置权**：

- 判定「受控 `continue` 可放行」= 重解释冻结判据 —— 派单第三节禁止；
- 删除 `continue` / inferior call = 改变 harness 语义 —— 派单第三节禁止，且会推翻
  §28 的控制链闭合与 §29 已 PASS 的 preflight 语义；
- 忽略命中继续硬件 preflight = 违反第四节「静态确认」前置。

因此按派单第三节「若必须改变 harness 语义、扩大文件范围或改变冻结判据，立即停止并
交新的非实现裁定」与第七节「立即停止 + 保存原始证据 + 等新的非实现裁定，禁止自动
重试」执行**停止**。

本轮结果分类：`EVIDENCE_GAP`（判据冲突，未取得任何新产品证据）。
**不是** `PRODUCT_FAIL`：未执行任何产品路径，无门槛失败、guard 损坏或栈峰值证据。
**不是** `HARNESS_FAIL`：离线回归 `27/27`，生成脚本与已 PASS 版本逐字节相同。
**不是** `ENV_BLOCKED`：未启动硬件，J-Link 可用性本轮未被测试。

### 33.9 本轮未执行的动作

- 未启动 J-Link、未启动 `JLinkGDBServerCL.exe`、未连接 SWD、未 halt/attach 目标。
- 硬件 preflight `0/1` 未消耗；PATCH 上传 `0/1` 未执行。
- 未调用 `lv_fs_open` / `lv_fs_write` / `lv_fs_close`，**未创建或写入任何 SD 文件**，
  未写 Flash，未写目标内存，未 reset/go。
- 未执行 PATCH OTA、FULL 上传/OTA、异常退出或 LiveMap 恢复取证；
  C1/C2、C4-C7、C14 仍为 `NOT_OBSERVED`。
- 未运行 stack closure（R3 保持 `2/3`），C3/C13/C16 沿用正式 `PASS`。
- 未创建 `docs/acceptance-contracts/P2-6-v1.contract.json`，未独立验收。
- 未执行 `git commit` / `push` / `merge` / `rebase` / `stash`；工作树 tracked 改动
  与本轮开始时一致。
- 未修改生产源码、CMake、linker、startup、冻结提示词、`PLAN-OTA.md`、
  `docs/ota-binary-contracts.md`、冻结数字、transport result JSON 或 qualifier
  的 legacy `qualification_id`。
- 未修改 `tests/ota/` 下任何 harness 或单测。

### 33.10 设备状态与外部写入审计

- 设备状态本轮**未观测也未改变**：无 attach、无 halt、无内存/Flash 写入。最后一次
  已知状态仍为 §32 记录的 transport R2 收尾态（`SD_IsReady=1`、`VTOR=0x08010000`、
  `CFSR=0`、overlay owner=`0`、BCB `CONFIRMED`），本轮不引用该状态作为新证据。
- **项目外写入：0 条**。`outside_repo_writes=[]`（prepare-only 结果 JSON 实测）。
  `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 本轮未读取、未写入、未触碰。
  历史 `E:\` 与 SEGGER 授权本轮一律未沿用。
- 残留进程与端口：本轮未启动 J-Link server、GDB 或 RTT logger，故无残留进程；
  `24361`-`24364` 本轮未被本会话监听。
- 本轮主动写入仅两类，全部位于活动 Git 根内：
  `.cache/p2-6-sd-r3-20260823-01/**`（新建唯一根）与本文件 + `PLAN-OTA-EXEC.md` 回填。
  五个既有证据根经 manifest 复算证明零改动。

### 33.11 待新的非实现裁定处理的问题

需由非实现协调/规范维护会话裁定，本会话不得自行选择：

1. `P2-6-SD-R3` preflight 的静态禁止清单以哪一份为准 —— 看板 §565 的 SD-R2
   preflight 冻结判据，还是 §568 的 transport qualifier 只读判据。
2. 若维持「preflight 不得含 `continue` 与函数调用」，则需裁定如何在不改 §28 控制链
   闭合语义、不推翻 §29 已 PASS preflight 的前提下取得等价的确定停点与 BCB 读取。
3. 裁定后重新派单时应明确 `P2-6-SD-R3` 硬件 preflight 计数仍为 `0/1`（本轮未消耗）。

### 33.12 会话结束写入审计（实测）

收尾脚本 `.cache/p2-6-sd-r3-20260823-01/writeback/final_audit.py`，
日志 `.cache/p2-6-sd-r3-20260823-01/writeback/final-audit.log`：

- 五个旧证据根全部 `SAME`，`manifest_match=True` 且 `bytes_match=True`，
  `ALL_OLD_EVIDENCE_UNCHANGED=True`（1365 个文件零改动）。
- `hardware_started=false`、`outside_repo_writes=[]`。
- `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 仍为 986B /
  SHA-256 `DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`，
  `mtime_ns=1787351959293072100`（与 §32 记录一致，本轮未读取也未写入）。
- 端口 `24361` / `24362` / `24363` / `24364` 全部 `closed`；
  `JLinkGDBServerCL.exe`、`JLinkRTTLogger.exe`、`JLink.exe`、
  `arm-none-eabi-gdb.exe` 均无进程。
- `HEAD` = `origin/main` = `99173123cae8c487b86efa8a4eecbbe73b1bb512`，
  分支 `p2-6-implementation-20260819`，未执行任何 Git 远端操作。
- 本轮回填后：`PLAN-OTA-EXEC.md` 302595B、`crlf=679` 保持不变、LF 行 873→875；
  本文件保持纯 LF（`crlf=0`）。两份文档均通过**反向重建校验**——移除本轮新增行
  并还原状态行后，SHA-256 分别精确回到编辑前的
  `1A8213B147A05931669733FDCA060D603D90830BAF690FB97655E84D3D58D323` 与
  `CC4A6D66009C637B1EC3178760AD4663033FD0FBD4DA3D68FFA9149853486DA3`，
  证明除三处预期新增外零附带改动（混合 EOL 文件未产生伪变更行）。

## 34. P2-6-SD-R3 preflight 判据独立裁定与恢复授权（2026-08-23）

### 34.1 裁定结果与角色边界

- 裁定编号：`P2-6-BR-20260823-SD-R3-01`
- 裁定结果：**`AUTHORIZED_RESUME`**
- 本轮停止分类：`EVIDENCE_GAP`（派单判据适用域冲突）

本节由 P2-6 非实现协调/阻塞裁定 agent 完成，只审计 §33 的静态证据、冻结
preflight 语义和此前 transport recovery 证据。没有执行 J-Link/GDB/RTT、烧录、
Flash/SD 写入、上传、OTA、stack closure、构建、独立验收或 Git 远端操作。

实现会话在硬件启动前停止是正确的；停止不消耗硬件 preflight 次数，也不构成
`PRODUCT_FAIL`、`HARNESS_FAIL` 或 `ENV_BLOCKED`。本裁定只纠正派单清单的适用域，
不修改冻结实现提示词、harness、生产源码、冻结数字、静态路线或二进制合同。

### 34.2 独立复算与证据实体

本裁定独立复算得到：

| 证据 | 字节数 | SHA-256 |
|---|---:|---|
| R3 preflight 脚本 | 7159 | `77E669A202CFDA74163006FE70687CE35AC859A97A8A8C735763CE09CBEDD3DA` |
| R3 prepare-only result | 1821 | `EE4C17255D09AB2E5BA5CA8D9F1F8D82A5FC435F1F6900B5283DBAB297B6AA63` |
| R3 静态审计 JSON | 2046 | `7B02A7C1841E4930011BAC4F654C8473A0490EBDBCAFC75ACBC9AE7A8A416B8E` |
| R3 harness unittest 日志 | 5170 | `5EB6E6D0904E2D078952041B8ED74C35749C99AD251AFE7039894F8C4CDA9E63` |
| test ELF | 866372 | `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019` |
| test map | 2423356 | `2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13` |
| test v2.8.0 image | 600744 | `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5` |
| PATCH | 305 | `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` |
| FULL | 282367 | `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7` |

R3 preflight 与 §28.4/§29 已取得 `1/1 PASS` 的
`.cache/p2-6-sd-r2/final-scripts/tmp/p2-6-sd-r2-preflight-final.gdb` 均为
151 行、7159B、同一 SHA-256，逐字节比较为 `True`。离线回归为
`27 PASS / 0 FAIL / 0 ERROR / 0 SKIP`。五个旧证据根的 1365 个文件
manifest 和总字节均匹配，旧证据未被改写。

§32 的 transport recovery 原始 result 仍为
`C166055F467AD60F7C527DEA53EB635404315AB51247F2F4010A3C101B35929F`；
两个独立 PID `21728` / `19976` 的 GDB 日志各唯一出现 identity/state/PASS
marker，server 日志均完成 readiness、target halt、GDB detach 和自然退出，且
`terminate=false`、`kill=false`。因此 §30.5 transport 阻塞仍保持已闭合。
result 内 `qualification_id=P2-6-TR-R1` 继续定性为已记录的 test-only legacy
metadata defect；新根、前缀、PID、日志和哈希足以唯一区分 transport R2。不得修改、
覆盖或静默重标原始 JSON。

### 34.3 判据适用域与两项命中定性

冻结证据链的优先关系如下：

1. §28.2 明确规定 SD preflight 的确定停点使用同步 `thbreak`、stop-magic、
   `continue` 返回后的 magic/PC 双校验；并规定 inferior function call 后必须再次
   校验 `$pc == HAL::HAL_Update()`。
2. §28.4、§29 和看板 §565 对 SD preflight 的静态禁令是
   `continue &`、`interrupt`、`restore`、`dump binary memory`，以及 SD 文件 API、
   页面依赖、Flash/目标写入和 `loadfile` 等。本轮这些项目全部 CLEAN。
3. 看板 §568/§577 和 `p2_6_rtt_transport_qualifier.py:audit_read_only_script()`
   的“无任何 `continue`、无函数调用”只约束 122 行 transport-only qualifier。
   qualifier 不读取 BCB，也不前进到 `HAL::HAL_Update()`，不能替代 151 行 SD
   preflight 的控制链。

因此两项命中均为**允许且必需的既有 SD preflight 语义**：

- 第 16 行 `continue` 只允许与同一脚本中的唯一 `thbreak *0x08040884`、
  stop-magic `0x50326201`、返回后的 magic/PC 双校验和 `delete breakpoints`
  组成一个不可拆分的同步确定停点；不得扩展为自由运行、异步继续或其他停点。
- 第 137 行只允许调用既有 `HAL::OTA_GetBcbState()`（Thumb 地址
  `0x08040ccd`），并必须立即执行 `preflight_bcb_call` 的
  `$pc=0x08040884` 上下文校验；不得增加其他 inferior call。

这不是放宽 transport qualifier，也不是更改 harness。此前派单把 qualifier 的额外
禁令套用到 SD preflight，属于派单派生清单过约束；该两项清单要求自本裁定起对
P2-6-SD-R3 preflight 不再适用。

### 34.4 当前状态与固定计数

- P2-6：**进行中 / 等待独立验收**，不是完成。
- P2-6-SD-R3 硬件 preflight：`0/1`，本轮 prepare-only 不消耗次数。
- P2-6-SD-R3 PATCH 上传：`0/1`。
- 最初 PATCH 上传：固定 `3/3`，禁止第四次或重解释。
- P2-6-SD-R2 preflight：固定 `1/1 PASS`，禁止重跑。
- P2-6-SD-R2 正式 PATCH 上传：固定 `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY`，禁止重跑。
- stack closure R3：固定 `2/3`，禁止 R3-3。
- C3/C13/C16 沿用正式 `PASS`。
- C1/C2、C4-C7、C14 仍为 `NOT_OBSERVED`，本裁定没有产生任何产品观测。

### 34.5 可直接派给实现 agent 的完整 P2-6-SD-R3 提示词

你是 E-Track 项目的 P2-6-SD-R3 实现验证 agent。你只执行本提示词明确授权的
preflight、SD 上传、OTA 与取证，不做独立验收，不修改生产实现或冻结规范。

一、开始前必读

1. `AGENTS.md`。
2. `PLAN-OTA-EXEC.md` 的 P2-6 卡、§9、§10。
3. `docs/ota-prompts/prompt-P2-6-implementation.md`，重点 §0.2、§1.1、
   §4.5、§4.7 至 §4.9-E、§6、§9。
4. `docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md`
   的 §28 至 §34，尤其 §28.2、§29、§30.5、§32、§33、§34.3。
5. `tests/ota/p2_6_rtt_ota_driver.py`、`tests/ota/p2_6_rtt_sd_uploader.py`、
   `tests/ota/p2_6_rtt_sd_preflight.py`、`tests/ota/p2_6_rtt_transport_qualifier.py`
   及对应单测。

二、项目与冻结输入

1. 项目根：`D:\github\my\E-Track`。
2. 分支：`p2-6-implementation-20260819`。
3. HEAD / origin/main：`99173123cae8c487b86efa8a4eecbbe73b1bb512`。
4. 新项目内证据根固定为
   `D:\github\my\E-Track\.cache\p2-6-sd-r3-20260823-02\`。开始前确认该根
   不存在、规范化后位于项目根内、路径链无 reparse point；只允许新建，不得覆盖、
   删除、移动或复用 `p2-6-sd-r3-20260823-01` 或任何旧证据。
5. 必须重新复算并匹配：ELF
   `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`；
   map `2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13`；
   test v2.8.0 image
   `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5`；
   PATCH `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B`；
   FULL `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7`。
6. 所有 required symbols 必须从本轮 test ELF 重取且唯一；不得沿用旧 map、旧 RTT
   地址、旧 SD 地址或旧设备状态。

三、不可改写的历史事实

1. 最初 PATCH 上传 `3/3`，禁止第四次、清零、重跑或重解释。
2. SD-R2 preflight `1/1 PASS`，禁止重跑。
3. SD-R2 正式 PATCH 上传 `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY`，禁止重跑。
4. stack closure R3 `2/3`，禁止 R3-3；C3/C13/C16 沿用正式 `PASS`。
5. SD-R3 硬件 preflight 仍为 `0/1`；PATCH 上传仍为 `0/1`。
6. C1/C2、C4-C7、C14 仍为 `NOT_OBSERVED`，不得引用历史状态冒充本轮证据。

四、SD preflight 判据澄清

1. 使用现有 `p2_6_rtt_sd_preflight.py` 与现有 driver 语义，不得修改 harness。
2. 允许且仅允许一个同步受控 `continue`：必须由
   `deterministic_stop_lines()` 生成，与唯一 `thbreak HAL::HAL_Update()`、
   stop-magic、返回后的 magic/PC 双校验和删除断点完整绑定。
3. 允许且仅允许一个 BCB inferior call：现有
   `HAL::OTA_GetBcbState()` 调用；调用后必须立即校验 PC 仍在
   `HAL::HAL_Update()`。不得增加、替换或移动其他函数调用。
4. 继续严格禁止：`continue &`、`interrupt`、`restore`、`dump binary memory`、
   `loadfile`、`loadbin`、`verifybin`、`set *` 或其他目标内存写入、Flash 操作、
   `lv_fs_open/write/close`、SD 文件创建或写入、页面对象依赖、`reset`、`go`、自由运行
   和无限/自动重试。
5. 可先执行一次 `--prepare-only` 静态生成；它不计入硬件 preflight。脚本必须与
   上述语义一致，任何额外 `continue`、额外 inferior call 或任一禁止项命中立即
   停止，不得现场修改 harness。

五、用户授权与项目外边界

1. 启动任何 J-Link/GDB/RTT 进程前，必须重新向用户说明并取得本轮对准确路径
   `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 可能由 SEGGER 更新的明确授权；
   不得沿用任何历史授权。
2. 写入 MCU 上的 SD/移动介质前，必须先向用户取得本轮准确的外部目标路径、写入
   操作和副作用的明确授权。用户授权后，PATCH 和 FULL 各使用一个新的、唯一的
   目标文件路径；路径必须由用户当轮明确给出并经项目外写入预检确认，不能由历史
   记录推断。不得复用任何历史 `E:\`、`/P2-6-RUN-20260820-01/` 或其他旧目标，
   不得改名、换路径或在未重新裁定时另建替代路径。
3. 授权前只允许项目内静态准备。若用户未授权，停止并报告 `WAITING_AUTHORIZATION`；
   不得启动硬件或改换路径。
4. 不得覆盖、删除、移动、重命名或清理 SD 上任何既有文件。目标存在、状态不确定或
   不存在探测返回非冻结的“确实不存在”状态时立即停止。

六、唯一硬件 preflight

1. 只允许一次无 SD 写入硬件 preflight，计数从 `0/1` 变为 `1/1`；首失败即停，
   不得现场修复后重跑。
2. 必须同时取得且各唯一命中：精确 96B 固件身份、确定停点、RTT 签名、
   `SD_IsReady=1`、`VTOR=0x08010000`、`CFSR=0`、BCB `CONFIRMED`、overlay owner
   `FREE`、最终 PASS。
3. 必须记录 server readiness、PID、GDB/RTT 启动、退出码、自然/强制收尾、端口状态；
   GDB detach 后 server 应自然退出。任何 terminate/kill、残留进程、监听端口或收尾
   不确定均视为首失败并停止。
4. preflight 不得调用任何 SD 文件 API，不得写 Flash/SD/目标内存，不得 reset/go。

七、唯一 PATCH 上传

1. 只有硬件 preflight 完整 PASS 后，才允许一次 PATCH 上传，计数 `0/1 -> 1/1`；
   输入、项目内日志和 MCU/SD 目标必须绑定本提示词的唯一实体。
2. 使用现有 MI 分块写入/严格读回协议。必须验证每块顺序、地址、长度、BEGIN/END
   标记和 MI 返回；任何缺块、重复、乱序、越界、部分写入可能或状态不确定立即停止。
3. 上传后必须完整读回并拼接全部字节，独立 SHA-256 必须等于
   `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B`。
4. 任一非 PASS 后禁止第二次上传、换路径、覆盖、删除或自动重试。

八、PATCH 通过后的单次取证顺序

1. PATCH OTA 只允许一次，补 C2/C4/C5/C6/C14 的真实窗口证据。
2. FULL 上传只允许一次；完整读回 SHA-256 必须等于
   `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7`。
3. FULL OTA 只允许一次，补 C1/C4/C5/C6/C14 的真实窗口证据。
4. 异常退出只允许一次，随后 LiveMap 恢复取证只允许一次，补 C7。
5. 每个阶段只有前一阶段完整 PASS 才可进入下一阶段；不得以上传成功替代 OTA apply，
   不得用 PATCH 结果替代 FULL，也不得用历史状态替代本轮观察。
6. C3/C13/C16 只沿用既有正式 PASS；不得运行 stack R3-3。

九、产品门禁与立即停止条件

出现任一情况立即保存原始证据、停止全部后续动作并等待新的非实现裁定，禁止自动重试：

1. 任一新失效模式、`HARNESS_FAIL`、`PRODUCT_FAIL`、`ENV_BLOCKED`、transport 非 PASS、
   设备/文件状态不确定或设备不可恢复。
2. `workspace_peak > 40960B`。
3. 有效栈峰值 `> 8192B`，或 guard 损坏。
4. OTA 核心窗口 `sbrk_call_count` 增量非零。
5. required `lv_tlsf_malloc` / `lv_tlsf_realloc` 增量非零；`free` 非零且无法定位。
6. C13 前置失效、BCB/VTOR/CFSR/overlay/身份不符合预期、读回哈希不匹配。
7. 任何进程/端口/外部配置收尾无法证明，或需要修改 harness、生产源码、冻结判据、
   冻结数字、静态路线、二进制合同、目标路径或操作次数。

十、禁止事项与回填

1. 不得修改生产源码、CMake、linker、startup、`tests/ota` harness/单测、冻结实现提示词、
   `PLAN-OTA.md`、`docs/ota-binary-contracts.md`、transport 原始 JSON 或 legacy
   `qualification_id`。
2. 不得独立验收、创建 `docs/acceptance-contracts/P2-6-v1.contract.json`，不得宣布
   P2-6 完成。
3. 不得 commit、push、merge、rebase、stash，不做 P3/P4/Cloudflare。
4. 只允许向新的项目内证据根、`PLAN-OTA-EXEC.md` 和本证据文档回填；任何项目外写入
   必须严格限于用户当轮明确批准的准确路径和操作。
5. 最终报告必须逐项给出计数、命令/退出码、原始日志与 SHA-256、设备状态、C 项分类、
   进程/端口收尾、项目内外写入清单，以及所有未取得的证据。即使全部执行成功，
   P2-6 也只能保持“进行中 / 等待独立验收”。

### 34.6 文件系统与项目外审计

本裁定会话主动修改的文件仅为：

- `D:\github\my\E-Track\PLAN-OTA-EXEC.md`
- `D:\github\my\E-Track\docs\ota-exec-notes\P2-6-implementation-evidence-2026-08-15.md`

两者和父目录均已规范化到活动 Git 根内，且不是 reparse point。原始
`.cache/p2-6-sd-r3-20260823-01/**`、transport 证据、测试工具和生产源码均未修改。

项目外只读审计的
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 当前仍为 986B，SHA-256
`DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`，mtime
`2026-08-22T06:39:19.2930721+08:00`；本裁定未修改、覆盖、恢复、删除或清理它。
本裁定没有产生项目外写入。当前未发现 J-Link/GDB/RTT 进程，端口 `24361` 至
`24364` 无 LISTENING。

## 35. P2-6-SD-R3 第二轮硬件执行与 uploader 常量差一停止（2026-08-23）

本节记录 `P2-6-SD-R3` 第二次派单（证据根后缀 `-02`）的完整执行。与第一轮
（§33，分类 `EVIDENCE_GAP`，未启动硬件）不同：本轮派单重写了 preflight 静态判据，
明确允许受控 `continue` 与唯一 `HAL::OTA_GetBcbState()` 调用，静态阻断因此解除，
硬件真实启动。本轮结论是 **`HARNESS_FAIL`**，根因在 uploader 的 LVGL 常量差一。

唯一新证据根：`.cache/p2-6-sd-r3-20260823-02/`。收尾审计时刻快照为 38 文件 /
406633B / manifest `8F1890913ACA3EACA033C3B9FA478133C15173EEEA16FE24C1860771D8D3FB11`；
包含回填期产物的最终清单以 `baseline/round-02-evidence.manifest.txt` 为准，
口径说明见 §35.10。

### 35.1 项目内静态前置（全绿）

- 写入预检：`D:\` → 仓库上级 → 仓库根 → `.cache` → 新根，路径链均存在且无
  reparse point；新根 `INSIDE_ROOT=True`、由本轮创建、此前不存在。
- 派单五个哈希**全部匹配**，且与 harness `FROZEN_*` 常量一致：

| 输入 | 字节 | SHA-256 | 匹配派单 |
| --- | --- | --- | --- |
| test ELF `X-Track-App-GCC.elf` | 866372 | `35BB2AB7...5076D019` | 是 |
| test map `X-Track-App-GCC.map` | 2423356 | `2446B401...A45D0C13` | 是 |
| device image v2.8.0 finalized | 600744 | `AB38A4E7...E569A5E5` | 是 |
| `P2-6A-PATCH-v2.8.0-to-v2.8.1.etu` | 305 | `2B0ACCAE...F37C9D2B` | 是 |
| `P2-6A-FULL-v2.8.1.etu` | 282367 | `84D3F384...C96DD2E7` | 是 |

- 6 个 required 符号从**本轮 test ELF** 重取且全部唯一，未沿用生产 map 旧地址：
  `HAL::OTA_GetBcbState()=0x08040CCC`、`HAL::HAL_Update()=0x08040884`、
  `SD_IsReady=0x20053214`、`_SEGGER_RTT=0x20053E1C`、
  `g_ota_overlay_owner=0x20053FA0`、`g_ota_overlay_workspace=0x20058000`
  （后者与 `OTA_OVERLAY_ORIGIN` 一致）。
- harness 离线回归 `27 PASS / 0 FAIL / 0 ERROR`；`tests/ota` 四个 harness 文件
  在本轮开始与结束时 SHA-256 完全一致（`harness_sha256_identical_to_round_start=True`）。
- 6 个旧证据根（含 R3-01 根）经 manifest 复算 `ALL_OLD_EVIDENCE_UNCHANGED=True`，
  共 1381 文件零改动。

### 35.2 preflight 静态审计（按本轮新判据 PASS）

`--prepare-only`（`hardware_started=false`，不消耗硬件次数）生成的脚本
151 行 / 7159B / SHA-256 `77E669A202CFDA74163006FE70687CE35AC859A97A8A8C735763CE09CBEDD3DA`，
与 SD-R2 已 `1/1 PASS` 的 `p2-6-sd-r2-preflight-final.gdb` **逐字节相同**。

- 12 项禁止全部 `CLEAN`：`continue &`、`interrupt`、`restore`、
  `dump binary memory`、`loadfile/loadbin`、`verifybin`、Flash 操作、
  `lv_fs_*` 文件 API、`set *` 与其他目标内存写入、`reset/go` 及自由运行、
  页面依赖、自动重试。
- 允许项 1（唯一同步 `continue`）**绑定成立**：第 16 行 `continue` 唯一，
  绑定第 10 行唯一 `thbreak *0x08040884`、第 13 行 stop-magic 置位
  `0x50326201`、第 17 行返回后 magic 校验、第 21 行 PC 校验
  `$pc != 0x08040884 → quit 70`、第 25 行 `delete breakpoints`。
- 允许项 2（唯一 BCB 调用）**绑定成立**：第 137 行
  `set $bcb_preflight = ((unsigned char (*)(void))0x08040ccd)()`，
  thumb 地址与符号 `0x08040CCC` 对应；第 139 行（两行内）复校
  `$p2_6_checked_pc != 0x08040884`。脚本内无其他函数调用表达式。
- `monitor halt` 恰 1 次且位于 `thbreak` 之前，是脚本内唯一 `monitor` 命令
  （`halt_bound=True`）。
- `no_sd_write_objective_met=true`，`static_audit_pass=true`。

审计器自身的一处修正需如实记录：v1 版本把 `monitor halt` 归入 `reset_or_go`
从而给出 `static_audit_pass=false`。这是本会话审计正则的分类错误，不是被审计脚本
的缺陷——`halt` 停住目标，是 attach 后取得确定停点的前提，与 `reset/go/自由运行`
语义相反。v1 报告原样保留为 `logs/preflight-static-audit-v1.json`
（3150B / `B9A3429171EF1C58...`）未被覆盖，v2 增加 `audit_version=2` 与 `v1_note`
说明修正理由。两版审计的**被审计脚本逐字节相同**，未修改 harness。

### 35.3 两项外部授权

- `AUTH-1-SEGGER-INI`：用户当轮授权 SEGGER 工具可改写
  `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`。授权前状态
  986B / `DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0` /
  `mtime_ns=1787351959293072100`。未沿用历史授权。
- `AUTH-2-SD-TARGET-PATH`：用户当轮选定采用建议目录
  `/P2-6-SD-R3-20260823-02/`（PATCH 与 FULL 各一个新文件），并确认容量足够、
  直接执行。明确避开 `E:\`、`/P2-6-RUN-20260820-01/`、
  `/P2-6-SD-R2-20260820-A7F3/`。操作限于创建两个新文件，不覆盖、不删除、不移动
  任何既有 SD 文件。

授权落盘于 `logs/authorization-granted.json`；授权前的等待状态与请求内容落盘于
`logs/authorization-request.json`（`hardware_started=false`、两项计数均 `0/1`）。

### 35.4 硬件 preflight：消耗 `1/1`，PASS

原始日志 `logs/p2-6-sd-r3-02-preflight-hw-gdb.log`（701B）：

```text
P2_6_TRANSPORT attached_stopped pc=0x08043216
P2_6_TRANSPORT breakpoint label=preflight_hal_update pc=0x08040884
P2_6_TRANSPORT stop_verified label=preflight_hal_update pc=0x08040884
P2_6_IDENTITY PASS label=preflight_fw header_bytes=96
P2_6_TRANSPORT context_verified label=preflight_bcb_call pc=0x08040884
P2_6_STATE PASS label=preflight sd=1 vtor=0x08010000 cfsr=0x00000000 bcb=4 owner=0
P2_6_SD_PREFLIGHT PASS write_calls=0 flash_calls=0
```

派单要求的全部必需项均**唯一取得**：96B 固件身份、确定停点
`pc=0x08040884`、RTT 签名（`rtt_connected=true`）、`SD_IsReady=1`、
`VTOR=0x08010000`、`CFSR=0`、BCB `CONFIRMED`(=4)、overlay owner `FREE`(=0)、
以及 `SD_PREFLIGHT PASS`。result JSON：`write_calls=0`、`flash_calls=0`、
`preflight_pass_markers=1`、`state_pass_markers=1`、`gdb_exit_code=0`。
生命周期：`server_pid` 记录、`server_ready_seconds=0.435`、
`server_natural_exit=true`、`server_kill_sent=false`、`ports_closed=true`、
`session_error=null`。未调用 `lv_fs_*`，未写 Flash/SD/目标内存，未 `reset/go`。

### 35.5 唯一 PATCH 上传：消耗 `1/1`，失败于写入前的只读探测

首次尝试被 Git Bash 的 MSYS 路径转换拦在 `validate_mcu_path()`：`/P2-6-…`
被改写成 Windows 路径，`startswith("/")` 不成立，`exit=1`。该次**未启动硬件、
未写 result JSON、未创建任何文件**，不消耗上传次数。改用
`MSYS2_ARG_CONV_EXCL='*' MSYS_NO_PATHCONV=1`，并先用
`python -c "print(repr(sys.argv[1]))"` 验证路径原样到达后才正式执行。

正式执行原始日志 `logs/p2-6-sd-r3-02-patch-upload-gdb.log`（767B）：

```text
P2_6_TRANSPORT attached_stopped pc=0x08043216
P2_6_TRANSPORT breakpoint label=upload_hal_update pc=0x08040884
P2_6_TRANSPORT stop_verified label=upload_hal_update pc=0x08040884
P2_6_IDENTITY PASS label=before_upload_fw header_bytes=96
P2_6_TRANSPORT context_verified label=before_upload_bcb_call pc=0x08040884
P2_6_STATE PASS label=before_upload sd=1 vtor=0x08010000 cfsr=0x00000000 bcb=4 owner=0
^done
P2_6_TRANSPORT context_verified label=probe_open_return pc=0x08040884
P2_6_SD_UPLOAD ERROR target_probe_unexpected res=12 expected_unknown=11
```

`gdb_exit_code=44`。失败点位于 uploader 写入协议**之前**的只读存在性探测
（`LV_FS_MODE_RD`），写模式 `LV_FS_MODE_WR|LV_FS_MODE_RD` 的 open 从未执行，
因此 SD 卡上**未创建、未覆盖、未删除任何文件**：`readback=null`、
`readback_bytes=null`、`readback_sha256=null`、`readback_matches=false`、
`readback_blocks=[]`、`readback_parse_error="MI readback event count mismatch: 0 != 3"`。
上传前设备状态与 preflight 完全一致且正常。

### 35.6 根因：uploader LVGL 常量差一（只读源码三段互证）

| 环节 | 文件 | 事实 |
| --- | --- | --- |
| 枚举真值 | `Simulator/LVGL.Simulator/lvgl/src/misc/lv_fs.h` | `LV_FS_RES_INV_PARAM=11`、`LV_FS_RES_UNKNOWN=12` |
| NULL 映射 | `Simulator/LVGL.Simulator/lvgl/src/misc/lv_fs.c` | `lv_fs_open()`：`if(file_d == NULL \|\| file_d == (void *)(-1)) return LV_FS_RES_UNKNOWN;` |
| 驱动返回 | `USER/lv_port/lv_port_fs_sdfat.cpp` | `fs_open()`：`SdFile::open()` 失败即 `file_p = NULL`，把「文件不存在／父目录不存在／FS 错误」折叠为同一个 NULL |
| harness 常量 | `tests/ota/p2_6_rtt_sd_uploader.py` | `LV_FS_RES_UNKNOWN = 11` ← **差一**，11 实为 `INV_PARAM` |

`single_lvgl_tree_compiled_by_firmware=true`：仓库内 `lv_fs.h` 的三份副本
（主树与两个 `.codex-worktree-*`）SHA-256 相同，且 GCC CMake 工程编译的正是
`Simulator/LVGL.Simulator/lvgl/src/misc/lv_fs.c`，不存在「设备用了另一份枚举」
的可能。

因此设备返回 `res=12` = `LV_FS_RES_UNKNOWN`，**正是 harness 本意要期望的
「目标文件不存在」**；harness 却拿 11 去比，必然判为 `target_probe_unexpected`。
`device_satisfied_intended_semantic=true`。

顺带确定：由于 SdFat 侧把所有失败折叠为 NULL，`res=12` 不携带目录信息，
**无法**用它区分「文件不存在」与「父目录 `/P2-6-SD-R3-20260823-02/` 不存在」。
下一节的穷尽性证明说明这个区分对本次失败并不重要。

### 35.7 穷尽性证明：当前常量下 uploader 无可达成功路径

probe 分支只有两个出口：

- 目标存在 → `res=0` → `printf target_exists` → `quit 43`
- 目标不存在 → `res=12` → 不等于 11 → `printf target_probe_unexpected` → `quit 44`

`any_reachable_success_path=false`。即：只要 `LV_FS_RES_UNKNOWN=11` 这个常量
存在，该 uploader 在**任何路径、任何 SD 卡、任何设备**上都无法创建新文件。
本次失败与所选目标路径**无关**，换目录不会改变结果，因此不属于「授权路径选错」，
也不能用换路径重试来绕过（派单同时禁止换路径重试）。

同时查证历史计数口径：`.cache/p2-6-sd-ota/logs/` 中所谓「旧 PATCH `3/3`」的三次
运行实为**全部失败**——`gdb_exit_code=40`、`readback_bytes=0`、
`readback_sha256=E3B0C442...`（空输入哈希）、`readback_matches=false`、
`capture_error=[WinError 10054]`，三份 gdb 日志均只有
`P2_6_SD_UPLOAD ERROR no_current_page`，且三次都用 `/P2-6-RUN-20260820-01/`。
也就是说 probe 分支历史上**从未被真机触达**，本轮是首次执行到该分支，
`LV_FS_RES_UNKNOWN=11` 此前从未被真实设备验证过。

### 35.8 分类与停止

本轮分类 **`HARNESS_FAIL`**：

- 不是 `PRODUCT_FAIL`：生产行为完全符合 LVGL 契约（`fs_open` 对不存在的目标返回
  NULL，`lv_fs_open` 把 NULL 映射为 `LV_FS_RES_UNKNOWN`）；上传前设备状态
  `sd=1 vtor=0x08010000 cfsr=0x00000000 bcb=4 owner=0` 全部正常。
- 不是 `ENV_BLOCKED`：J-Link、GDB server、RTT 与目标全部可达；同轮硬件 preflight
  已 `1/1 PASS`，上传会话也成功 attach、取得确定停点并校验固件身份。
- 不是 `EVIDENCE_GAP`：判据已在真机执行，得到确定性、可复现、有原始日志的负结果。

修正该常量必须修改 `tests/ota` harness，属派单明确禁止项，同时命中派单「需要修改
harness…立即停止」条款，故停止并未执行：未重试上传、未换路径、未改 harness、
未改生产源码、未改冻结判据/数字/路线/合同；未执行 PATCH OTA、FULL 上传、
FULL OTA、异常退出注错与 LiveMap 恢复取证（前置未通过）。

计数更新：硬件 preflight `1/1`（PASS）、PATCH 上传 `1/1`（FAIL）。
SD-R2 preflight `1/1`、SD-R2 正式上传 `1/1`、stack closure R3 `2/3` 均未重跑，
未运行 R3-3。C1/C2、C4-C7、C14 仍 `NOT_OBSERVED`；C3/C13/C16 沿用正式 `PASS`。

### 35.9 待非实现裁定的问题

1. 是否授权修正 `tests/ota/p2_6_rtt_sd_uploader.py` 的
   `LV_FS_RES_UNKNOWN = 11` → `12`。这是 test-only 常量，不触及生产源码，
   但仍属 harness 修改，需要显式授权与新轮次编号。
2. 修正后 probe 语义是否仍需收紧：由于 SdFat 把所有 open 失败折叠为 NULL，
   `res=12` 无法区分「文件不存在」与「父目录不存在」。若要求上传前确认父目录
   存在，需要额外的 `lv_fs_dir_open` 探测，那会引入新的目标调用，属判据变更。
3. 历史「旧 PATCH `3/3`」的计数口径需更正：该三次为全部失败，不构成任何
   `PASS` 证据，不应被后续轮次当作已冻结的成功记录复用。

### 35.10 会话结束写入审计

审计脚本 `.cache/p2-6-sd-r3-20260823-02/writeback/final_audit.py`，
日志 `writeback/final-audit.log`：

- 6 个旧证据根全部 `SAME`，`manifest_match=True` 且 `table_match=True`，
  `ALL_OLD_EVIDENCE_UNCHANGED=True`（1381 文件零改动）。
- `tests/ota` 四个 harness 文件 SHA-256 与本轮开始时完全一致；git 状态行未变。
- 项目外写入 1 条且在授权范围内：
  `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 仍为 986B、SHA-256
  仍为 `DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`
  （`bytes_changed=False`、`sha256_changed=False`），仅 `mtime_ns` 由
  `1787351959293072100` 变为 `1787503518048561900`（SEGGER 打开连接时更新）。
  除此之外无任何项目外写入。
- 端口 `24361`/`24362`/`24363`/`24364` 全部 `closed`；
  `JLinkGDBServerCL.exe`、`JLinkRTTLogger.exe`、`JLink.exe`、
  `arm-none-eabi-gdb.exe` 均无残留进程。
- `HEAD` = `origin/main` = `99173123cae8c487b86efa8a4eecbbe73b1bb512`，
  分支 `p2-6-implementation-20260819`，未执行任何 Git 提交/推送/合并/rebase/stash。
- 审计器自身修正一处并保留原件：v1 用 LF 字节串与磁盘 manifest 直接比较，
  而 `static_prepare.py` 的 `write_text()` 在 Windows 上把分隔符翻成 CRLF，
  导致 6 根全部误报 `bytes_match=False`（`manifest_sha256`、`file_count`、
  `total_bytes` 当时已全部匹配）。v2 改为按行尾归一化后比较表体。
  v1 日志原样保留为 `writeback/final-audit-v1.log`，未覆盖。
- 本轮回填：`PLAN-OTA-EXEC.md` 305430B → 314431B，`crlf=679` 保持不变、
  LF 行 877→879；本文件保持纯 LF。看板改动通过**反向重建校验**——移除两处
  新增行并还原状态行后，SHA-256 精确回到编辑前的
  `BA0777BA560B1E788DDE11060B0A5E29E5129FE83939B8E56BF0C5C7BCC26BEB`，
  证明除三处预期改动外零附带改动（混合 EOL 文件未产生伪变更行）。
  实现证据文档（本文件）为**纯追加**：追加前 196164B /
  `964EE92728CBCE869340029F7A2FB7CCDD01F2F05F993E5577F6A294D1095043`，
  §35 首次落盘后 210740B /
  `72420BB7BEDEB7D5E1A3D686D207033763A128CD81434C52030449DB21D0C77D`，
  随后在本节与 §35 引言处做了两处自洽性修正（把证据根清单区分为审计时刻快照与
  最终清单、补记本条追加指纹与表格转义说明），最终字节数与 SHA-256 记录于
  `.cache/p2-6-sd-r3-20260823-02/writeback/evidence-doc-final-fingerprint.json`
  （文件无法自含其哈希，故另存）。全程保持纯 LF（`crlf=0`）。该文件目前在 Git 中
  是未跟踪状态（`??`），因此 `git diff` 为空，追加安全性由
  `new.startswith(raw)` 字节前缀断言保证，而非依赖 diff 输出。
- 本节表格中 `lv_fs_open()` 那一行含两个转义竖线 `\|`，用于表示 C 的 `||`
  运算符；转义后按 Markdown 渲染仍是 3 列，与表头一致（已逐行校验列数）。
- 证据根最终清单以落盘文件为准：
  `.cache/p2-6-sd-r3-20260823-02/baseline/round-02-evidence.manifest.txt`
  （逐行 `<仓库相对posix路径>|<字节数>|<大写SHA-256>`，路径升序，manifest 自身
  不计入），配套 `writeback/final-fingerprint.log` 记录该清单的文件数、总字节与
  manifest SHA-256。此处**不内联具体数字**：回填期每写入一个脚本或日志都会改变
  计数，内联值必然自我失效。§35 引言的 38 文件 / 406633B 是收尾审计执行时刻的
  快照，与最终清单的差值即回填期产物（`evidence_writeback.py`、
  `post_append_check.py`、`record_final_fingerprint.py` 及其日志与指纹 JSON），
   不是既有证据发生变动。

## 36. P2-6-SD-R3-02 非实现常量审计与受控恢复裁定（2026-08-24）

### 36.1 角色、范围与唯一裁定

- 裁定编号：`P2-6-BR-20260824-SD-R3-02-01`
- 角色：P2-6 非实现 transport/阻塞裁定 agent；不是实现 agent，也不是独立验收 agent。
- 本会话只读复核仓库、源码、R3-02 原始日志和历史 manifest，并只允许回填本证据文档、
  `PLAN-OTA-EXEC.md` 以及新的审计快照目录
  `.cache/p2-6-sd-r3-20260824-03-adjudication/`。
- 未启动 J-Link/GDB/RTT/JLinkRTTLogger，未执行 OTA、烧录、Flash/SD 写入、stack closure、
  独立验收或 Git 远端操作。
- 唯一裁定：**`P2-6-BR-20260824-SD-R3-02-01 = AUTHORIZED_RESUME`**。

该裁定只授权一个新的 `P2-6-SD-R3-03` 实现验证轮次，不代表 P2-6 完成。当前状态继续为
`进行中 / 等待独立验收`；C1/C2、C4-C7、C14 仍为 `NOT_OBSERVED`，C3/C13/C16 沿用既有
正式 `PASS`，stack closure R3 固定 `2/3` 且禁止 R3-3。

### 36.2 冻结输入和独立复算哈希

| 输入 | 字节 | SHA-256 |
|---|---:|---|
| test ELF `X-Track-App-GCC.elf` | 866372 | `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019` |
| test map `X-Track-App-GCC.map` | 2423356 | `2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13` |
| test v2.8.0 image | 600744 | `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5` |
| PATCH | 305 | `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` |
| FULL | 282367 | `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7` |
| `lv_fs.h`（主树及两个 `.codex-worktree-*` 副本） | 8610 | `99C9F881BA90F59D91CA9A2833006AC1BF68E090CDD3056400126615CA32BBAC` |
| `lv_fs.c` 主树 | 14550 | `D7DA26624CD32A536EE52E47DCF5F110E92C76A67834DB75EE095B28145CA043` |

四个 harness 当前哈希也逐项复算，并与 R3-02 `logs/static-prepare-report.json` 一致：

| harness | SHA-256 |
|---|---|
| `tests/ota/p2_6_rtt_sd_uploader.py` | `36C4ABFF5829BDB9495CAFE16CD5D524EFE1691D4820CE714C37C1B6439F08A0` |
| `tests/ota/p2_6_rtt_sd_preflight.py` | `59524394DB2C8EC0D25927F92CBBE18F855CAE625EB905F28DE871C0A093D29D` |
| `tests/ota/p2_6_rtt_ota_driver.py` | `46206A97FC17095FB94B8FDBE081A4D5F74477E19AA14FD7DEE72414AB8F257D` |
| `tests/ota/p2_6_rtt_transport_qualifier.py` | `8A95B12C9A066A5B07D346252C6AEA1C9FA3585E7C57F150456704943951D896` |

### 36.3 根因逐项独立复核

1. `Simulator/LVGL.Simulator/lvgl/src/misc/lv_fs.h:35-47` 的隐式枚举为
   `LV_FS_RES_OK=0`、`...OUT_OF_MEM=10`、`LV_FS_RES_INV_PARAM=11`、
   `LV_FS_RES_UNKNOWN=12`；模式位为 `LV_FS_MODE_WR=0x01`、`LV_FS_MODE_RD=0x02`。
2. `MDK-ARM_F435/cmake-generated/CMakeLists.txt:352` 明确编译主树
   `Simulator/LVGL.Simulator/lvgl/src/misc/lv_fs.c`。主树与两个 worktree 副本的 `lv_fs.h`
   内容哈希相同，未发现第二套被固件使用的枚举源；因此根因不属于 source-tree mismatch。
3. `lv_fs_open()`（`lv_fs.c:57-89`）在 `open_cb` 返回 `NULL` 或 `(void *)(-1)` 时返回
   `LV_FS_RES_UNKNOWN`，数值为 12。
4. `USER/lv_port/lv_port_fs_sdfat.cpp:108-138` 中，模式 2 选择 `O_RDONLY`，模式 3
   选择 `O_RDWR | O_CREAT`；`SdFile::open()` 失败后删除对象并返回 `NULL`。文件不存在、
   父目录不存在和其他 SdFat open 错误在该适配层折叠为同一个 `NULL`，因此 `res=12` 不带
   目录级别诊断。
5. `p2_6_rtt_sd_uploader.py:311-324` 的 probe 只有两条出口：`res==0` 关闭句柄并
   `quit 43`；`res != LV_FS_RES_UNKNOWN` 则 `quit 44`；模式 3 open 位于其后。当前
   harness 常量为 11 时，真实设备对目标不存在返回 12，必然走 `quit 44`，没有任何可达
   成功上传路径。失败发生在写模式 open 之前，所以没有创建、覆盖、删除或移动 SD 文件。

这证明 R3-02 是确定的 harness 失败，而非产品行为失败或环境不可达。

### 36.4 四个 harness 的全量固件常量审计

审计范围包括 `LV_FS_RES_*`、LVGL 模式/seek 位、BCB 状态码、overlay owner、VTOR/SCB
地址、页面 ABI 偏移/stride、magic、退出码含义、冻结容量和状态 marker。逐项对照真实头文件、
冻结 ELF/map 反汇编、生成脚本和既有单测后，唯一固件侧不一致如下：

| 文件 | 常量/文本 | 当前 | 真实/应为 | 处置 |
|---|---|---:|---:|---|
| `tests/ota/p2_6_rtt_sd_uploader.py:36` | `LV_FS_RES_UNKNOWN` | 11 | 12 | **授权修正** |
| `tests/ota/p2_6_rtt_sd_uploader.py:319` | 诊断 `expected_unknown=11` | 11 | 12（或动态插值授权常量） | **授权同步修正** |

其余已核对固件侧常量对账如下：

| harness | 对账项目 | 真实来源/值 | 结论 |
|---|---|---|---|
| `p2_6_rtt_sd_uploader.py` | `OK=0`、`WR_RD=3`、`RD=2`、`SEEK_SET=0`、`SEEK_END=2`、`LV_FS_FILE_SIZE=12` | `lv_fs.h` 模式/seek 位；`lv_fs_file_t` 三个 4B 指针字段 = 12B | 一致 |
| `p2_6_rtt_sd_preflight.py` | HAL update stop magic、BCB `CONFIRMED=4`、overlay FREE=0、VTOR/CFSR addresses | driver + `eeprom_bcb.h` + `HAL_OTA_Package.cpp` + SCB contract | 一致 |
| `p2_6_rtt_ota_driver.py` | page offsets/stride/mode 0..3、BCB `STAGED=1/CONFIRMED=4`、VTOR `0x08010000`、workspace/stack gates | frozen ELF `SwitchTo`/`FirmwareUpdate` disassembly + `FirmwareUpdate.h` + `eeprom_bcb.h` + prompt | 一致 |
| `p2_6_rtt_transport_qualifier.py` | session count=2、transport marker/exit codes、read-only token set | qualifier source and §30.5 transport contract | 一致；`qualification_id` 仅 legacy metadata |

没有发现 `p2_6_rtt_sd_preflight.py`、`p2_6_rtt_ota_driver.py` 或
`p2_6_rtt_transport_qualifier.py` 的第二个阻断性固件常量差异。driver 的 `BCB_STATE_STAGED=1`、
`BCB_STATE_CONFIRMED=4`、`OTA_OVERLAY_FREE=0`、`EXPECTED_VTOR=0x08010000`，FirmwareUpdate
模式 0/1/2/3、页面 state 3/4、行区 `0x146C`、stride 312、path offset 4，LVGL 模式/seek 位，
以及 transport 状态 marker 均与真实源码/冻结 ELF 绑定。退出码是 host 协议内部值，不是固件
枚举，保持原样。不得扩大修改面，不得把 host 默认日志根改成“修复”。

### 36.5 历史计数和 manifest 时序问题

旧 PATCH 所谓 `3/3` 的三份 result 均失败：前两次 `gdb_exit_code=1`，第三次
`gdb_exit_code=40`、日志仅 `no_current_page`、`readback_bytes=0`、空输入 SHA
`E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`。因此应在看板和本节
定性为“**三次失败，上传额度耗尽**”，但不得清零、重解释、重跑或开放第四次；原始 JSON、GDB、
server、RTT 和脚本保持不变。

R3-02 `baseline/round-02-evidence.manifest.txt` 另有一个回填时序缺陷：manifest 记录
`writeback/post-append-check.log` 为 `0B/E3B0...`，而该审计日志在 manifest 生成后追加为
`1622B/FB6FA4B520DD161886452D9ACBD54FE80EDEC3188577722D2D209B36F9351C89`。六个旧证据根
逐文件复算均为零缺失、零不匹配，R3-02 原始硬件 result/GDB/server/RTT 日志也均未被改写，
四个 harness 哈希与起始记录一致。因此这是**当前根的审计回填自描述时序缺陷**，不是旧证据
污染，不足以推翻 `HARNESS_FAIL`；但 R3-03 必须在所有回填完成后再生成最终 manifest，生成后
禁止继续追加任何文件。

### 36.6 Q1-Q8 明确裁定

- **Q1 分类**：`HARNESS_FAIL`。不是 `PRODUCT_FAIL`（固件按 LVGL 契约返回 UNKNOWN，且
  preflight/上传前状态 `sd=1/vtor=0x08010000/cfsr=0/bcb=4/owner=0` 正常）；不是
  `ENV_BLOCKED`（同轮 server readiness、GDB、RTT、target 均可达）；不是 `EVIDENCE_GAP`
  （真实 probe 已执行并有确定原始日志）。
- **Q2 授权范围**：仅授权 `p2_6_rtt_sd_uploader.py` 的 `LV_FS_RES_UNKNOWN 11 -> 12`
  和同一错误诊断文本 `expected_unknown=11 -> 12`（可改为从该常量动态生成）。不授权任何
  生产源码、CMake/linker/startup、冻结 prompt/数字、二进制合同或原始 JSON 修改。
- **Q3 其他差异**：未发现第二处固件常量差异；其余三 harness 原样保留。允许新增/更新
  test-only 回归断言锁定 UNKNOWN=12，但不得扩展目标调用协议或改退出码语义。
- **Q4 父目录探测**：不新增 `lv_fs_dir_open`。这会改变冻结调用协议，且 SdFat 适配仍把多类
  错误折叠；R3-03 只接受用户当轮明确授权的唯一新 MCU 路径，probe 返回非 12 即停，不能
  把旧 `res=12` 追溯声称为“父目录已存在”。目标路径的父目录必须在启动硬件前由用户明确
  确认为已存在；无法确认时停止，不新增目录探测，也不消耗上传额度。
- **Q5 preflight 复用**：不复用 R3-02 的硬件状态。R3-03 必须重新做一次只读状态复核，
  计为新的 `0/1 -> 1/1` R3-03 preflight；R3-02 的 `1/1 PASS` 仍冻结、不重跑、不覆盖。
- **Q6 配额**：R3-03 各一次：硬件 preflight、PATCH 上传、PATCH OTA、FULL 上传、FULL OTA、
  异常退出注错、LiveMap 恢复取证。任一首失败、状态不确定或收尾不确定立即停止，禁止重试、
  换路径或自动恢复。
- **Q7 历史口径**：由本非实现裁定会话回填看板 §9/§10 和本节，写明“三次失败、额度耗尽”；
  原始历史证据不改，后续实现 agent 不得把它们当 PASS。
- **Q8 取证绑定**：单次 PATCH OTA 绑定 C2/C4/C5/C6/C14；单次 FULL OTA 绑定
  C1/C4/C5/C6/C14；单次异常退出加单次 LiveMap 恢复绑定 C7。上传读回只是 OTA 前置，不能
  替代 OTA apply；C3/C13/C16 沿用 PASS，不运行 R3-3。

### 36.7 §30.5 transport 复核及 metadata 定性

独立 transport recovery 根 `.cache/p2-6-transport-r2-20260823-01/` 的 result SHA-256 为
`C166055F467AD60F7C527DEA53EB635404315AB51247F2F4010A3C101B35929F`。两个 session PID
分别为 `21728`、`19976`，server readiness 为 `1.752s`、`0.306s`；两者均
`server_ready=true/gdb_started=true/gdb_exit_code=0/rtt_connected=true`，固件头、RTT、state/PASS
marker 各唯一命中，detach 后 server 自然退出，无 terminate/kill，端口关闭。两份资格 GDB
脚本只有 target remote、monitor halt、只读内存比较、detach/quit；无 Flash/SD/目标内存写入、
`loadfile/loadbin/restore`、`continue`、函数调用、`reset/go`。SEGGER 配置当前仍 986B、
SHA-256 `DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`，本会话只读。

JSON 的 `qualification_id` 仍为源码硬编码的 legacy `P2-6-TR-R1`。冻结规范未要求该字段
递增，唯一路径/前缀、时间、双 PID、日志和哈希足以区分本轮；定性为“新的 transport recovery
qualification 证据 + test-only legacy metadata defect”，不得修改、覆盖或静默重标原始 JSON。
因此 §30.5 readiness/acquisition/收尾/外部审计条件已满足，transport 阻塞闭合，但不改变
任何产品 C 项或 P2-6 完成状态。

### 36.8 可直接派发的 P2-6-SD-R3-03 实现 agent 提示词

```text
你是 E-Track 项目的 P2-6-SD-R3-03 实现验证 agent，不是独立验收 agent。只执行本提示词
明确授权的 test-only harness 修正、无 SD 写入 preflight、一次 PATCH/FULL 上传与一次 OTA
取证链；不得独立验收或宣布 P2-6 完成。

固定仓库与历史计数：
- 根 D:\github\my\E-Track；分支 p2-6-implementation-20260819；HEAD/origin/main
  99173123cae8c487b86efa8a4eecbbe73b1bb512。
- 旧 PATCH 3/3（实际三次均失败、额度耗尽）、SD-R2 preflight 1/1 PASS、SD-R2 正式上传
  1/1 ENV_BLOCKED/TRANSPORT_NOT_READY、stack closure R3 2/3 均冻结，不清零、不重跑、
  不重解释；禁止 R3-3；C3/C13/C16 沿用 PASS。
- C1/C2、C4-C7、C14 只能用本轮新真实证据，当前仍 NOT_OBSERVED。
- 冻结输入必须重新复算：ELF
  `35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`；map
  `2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13`；test image
  `AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5`；PATCH
  `2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B`；FULL
  `84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7`。不得替换。
- 使用唯一新的项目内证据根，例如 `.cache/p2-6-sd-r3-20260824-03-implementation/`；
  先验证路径链在仓库内且无 reparse point，不得复用/覆盖任何旧根。

唯一授权的 harness 修改（只允许这两处）：
1. `tests/ota/p2_6_rtt_sd_uploader.py`：`LV_FS_RES_UNKNOWN = 11` 改为 `12`。
2. 同一 probe 诊断文本 `expected_unknown=11` 改为 `expected_unknown=12`，或动态引用
   该常量。保留所有分支、LV_FS 模式位、地址偏移、MI 分块协议、退出码和读回逻辑。
   不得增加 `lv_fs_dir_open`，不得修改另外三个 harness。
改前/改后分别记录四个 harness SHA-256。先运行 py_compile 和现有定向 unittest；要求
全部 PASS、warning=0、error=0。不得修改生产源码、CMake/linker/startup、冻结提示词、
PLAN-OTA.md、二进制合同、transport 原始 JSON 或 legacy qualification_id。

硬件授权与项目外边界：
- 启动 J-Link/GDB/RTT 前重新取得用户对准确 `C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`
  路径及 SEGGER 可能改写它的本轮明确授权，不得沿用历史授权。
- 写 MCU SD 前重新取得用户对准确 MCU 路径、具体创建操作和副作用的本轮明确授权；只能
  使用一个新 PATCH 路径和一个新 FULL 路径，不覆盖、删除、移动任何旧文件，不换路径重试；
  两个路径的父目录必须是用户当轮明确确认已存在的目录。
- 所有脚本、日志、result、manifest、临时文件优先写新项目内证据根；manifest 必须在全部
  回填完成后生成，生成后不得再追加文件。

硬件配额和顺序（每项恰一次）：
1. preflight 使用冻结的 SD-preflight 语义：允许且仅允许一个由
   `deterministic_stop_lines()` 生成的同步 `continue`，并绑定唯一 `thbreak`、stop-magic、
   返回后的 magic/PC 双校验和断点删除；允许且仅允许一个
   `HAL::OTA_GetBcbState()` inferior call，调用后立即复校 PC 仍在 `HAL::HAL_Update()`。
   严禁 `continue &`、`interrupt`、`restore`、`dump binary memory`、`loadfile/loadbin/verifybin`、
   `set *` 或其他目标内存写入、Flash/SD/file API、页面依赖、`reset/go`、自由运行和自动重试。
2. 重新执行一次无 SD/Flash 写入 preflight，计 R3-03 preflight 0/1 -> 1/1。必须唯一取得
   96B 固件身份、确定停点、RTT 签名、SD_IsReady=1、VTOR=0x08010000、CFSR=0、BCB
   CONFIRMED、overlay FREE、write_calls=0、flash_calls=0、GDB exit=0；记录 readiness、
   PID、GDB/RTT 启停、自然/强制收尾、端口和残留进程。首失败即停。
3. 仅在 preflight 完整 PASS 后执行一次 PATCH 上传（0/1 -> 1/1）。只读目标 probe 必须
   返回 LV_FS_RES_UNKNOWN=12；随后使用既有 MI 分块写入和严格 BEGIN/END 读回协议。完整
   读回 SHA-256 必须等于 2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B。
   任一非 PASS、部分写入可能、状态不确定、缺块/乱序/越界或哈希不匹配立即停，禁止重试。
4. PATCH 上传完整 PASS 后，依次各执行一次 PATCH OTA、FULL 上传、FULL OTA、异常退出注错、
   LiveMap 恢复。FULL 读回 SHA-256 必须等于
   84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7。后一步只能在前一步
   完整 PASS 后开始。
5. 证据绑定：PATCH OTA -> C2/C4/C5/C6/C14；FULL OTA -> C1/C4/C5/C6/C14；异常退出+
   LiveMap 恢复 -> C7。不得用上传成功替代 OTA apply 或异常路径。

立即停止条件（保存原始证据后等待新非实现裁定，禁止自动重试）：
- 任一新失效模式、HARNESS_FAIL、PRODUCT_FAIL、ENV_BLOCKED、transport 非 PASS、设备/文件
  状态不确定、设备不可恢复、进程/端口/SEGGER 收尾不确定。
- workspace_peak > 40960B；有效 stack_peak > 8192B；guard 损坏；OTA 窗口 sbrk 增量非零；
  required lv_tlsf_malloc/realloc 增量非零；free 非零且无法定位；C13 前置失败。
- BCB/VTOR/CFSR/overlay/身份异常、读回不完整或 SHA 不匹配。
- 需要改生产代码、冻结数字/判据/静态路线、二进制合同、目标路径、操作次数，或超出上述
  两个 uploader 字面量的 harness 改动。

禁止事项与收尾：
- 不得修改原始 `.cache` 证据根、原始 transport JSON、生产源码、冻结文件；不得创建
  docs/acceptance-contracts/P2-6-v1.contract.json；不得独立验收或宣布完成；不得
  commit/push/merge/rebase/stash。
- 即使所有允许步骤 PASS，P2-6 仍只能回填“进行中/等待独立验收”；明确列出未观察 C 项、
  每个计数、原始日志/脚本/result SHA-256、设备状态、项目内外写入和收尾结果。
```

### 36.9 文件系统和项目外审计

本裁定会话主动写入的项目内路径只有：

- `.cache/p2-6-sd-r3-20260824-03-adjudication/independent-audit.md`
- `.cache/p2-6-sd-r3-20260824-03-adjudication/update_plan_bytes.py`
- `.cache/p2-6-sd-r3-20260824-03-adjudication/final-audit.md`
- `docs/ota-exec-notes/P2-6-implementation-evidence-2026-08-15.md`
- `PLAN-OTA-EXEC.md`

三者及父目录均规范化位于 `D:\github\my\E-Track` 内，均非 reparse point。未修改测试工具、
生产源码、冻结提示词、二进制合同、原始 `.cache` 证据或 transport JSON。项目外
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 只读核对为 986B、SHA-256
`DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`；本会话未写入、恢复、
删除或清理它。当前无 J-Link/GDB/RTT 残留进程，端口 24361-24364 无 LISTENING。

## 37. P2-6-SD-R3-03 preflight ENV_BLOCKED 独立裁定（2026-08-25）

### 37.1 唯一裁定

本轮非实现独立裁定编号为 `P2-6-BR-20260825-SD-R3-03-01`，结论为
**`KEEP_BLOCKED`**。R3-03 preflight 已消耗唯一配额并以
`ENV_BLOCKED / TRANSPORT_NOT_READY` 结束；不得重跑该 preflight，不得执行 PATCH/FULL
上传、OTA、异常退出或 LiveMap 恢复，也不得把本轮计数清零、改路径重试或并入旧轮次。

这不是 `PRODUCT_FAIL`：J-Link Server 在目标连接阶段失败，GDB/RTT 和任何产品路径均未
启动。也不是 `HARNESS_FAIL`：冻结脚本与允许的 test-only uploader 修正已通过离线回归，
失败发生在脚本执行之前。不是 `EVIDENCE_GAP`：本轮 transport 失败由完整的 Server 原始
日志、result JSON、退出码、PID 和收尾状态确定记录。

### 37.2 输入、哈希与结果复算

本轮证据根为 `.cache/p2-6-sd-r3-20260824-03-implementation/`。独立复算结果如下：

| 文件 | SHA-256 |
|---|---|
| `preflight/logs/p2-6-sd-r3-03-preflight-result.json` | `F7CF346AAD09F44CEB7CC70EAC5B235DDEC490A775B63357DAE7828C9C1CAEDE` |
| `preflight/logs/p2-6-sd-r3-03-preflight-jlink-server.log` | `DF192F1F956C51C1DB21EFAF9EB36E4C425E51F27BCA8998F05DCECF9213CAE9` |
| `preflight/tmp/p2-6-sd-r3-03-preflight.gdb` | `77E669A202CFDA74163006FE70687CE35AC859A97A8A8C735763CE09CBEDD3DA` |
| `preflight/console.log` | `5D6769B9C33BD83CC0A7FD27C848ED665C4D227FB8ACED69CECEA67A0A3C32D2` |
| `targeted-unittest.log` | `FA641EB07ACB5BB6F0641BF9E9D2928F24F94318E01928266A8A7B1EF68E64AE` |

冻结 ELF/map/test image/PATCH/FULL 的 SHA-256 分别仍为
`35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`、
`2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13`、
`AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5`、
`2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B` 和
`84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7`，均与冻结输入记录
一致。

四个 harness 的改前/改后记录为：uploader
`36C4ABFF5829BDB9495CAFE16CD5D524EFE1691D4820CE714C37C1B6439F08A0` ->
`88253A46C11A69B12D55ABACF1B13CF005B4722798EE6E7B85D0DFDBE46FDB61`；
`p2_6_rtt_sd_preflight.py`=`59524394DB2C8EC0D25927F92CBBE18F855CAE625EB905F28DE871C0A093D29D`、
`p2_6_rtt_ota_driver.py`=`46206A97FC17095FB94B8FDBE081A4D5F74477E19AA14FD7DEE72414AB8F257D`、
`p2_6_rtt_transport_qualifier.py`=`8A95B12C9A066A5B07D346252C6AEA1C9FA3585E7C57F150456704943951D896`
均未变。定向回归 `27/27 PASS`，无失败和错误。

### 37.3 Transport 失败边界

Server 日志完整走到：J-Link connected、target voltage `3.30 V`、`Connecting to target...`，
随后报告 `ERROR: Could not connect to target.` 并关闭。result JSON 的关键字段为：

- `server_started=true`，独立 PID `10964`；
- `server_ready=false`，`server_ready_seconds=null`，`server_exit_code=4294967293`；
- `server_process_exited=true`、`server_natural_exit=true`，未发送 terminate/kill；
- `gdb_started=false`、`gdb_exit_code=null`、`rtt_connected=false`；
- `ports_closed=true`，无残留进程或监听端口；
- GDB/RTT 日志未生成，故没有新的固件头、停点、RTT 签名、`SD_IsReady`、VTOR、CFSR、
  BCB 或 overlay 观测。

`hardware_started=true` 只表示 Server 进程已启动，不表示目标已 attach。JSON 中的
`write_calls=0` 和 `flash_calls=0` 是未进入 GDB 前的零值摘要，不能改写成设备状态 PASS；
但由于 GDB/RTT 从未启动，本轮确实没有执行目标内存、Flash、SD 或产品 OTA 写入，两个授权
MCU 文件均未创建。

preflight GDB 脚本 SHA-256 与生成记录一致，静态内容仍只有冻结 SD-preflight 所需的一个同步
`continue`、一个 BCB inferior call 和只读检查；无 `continue &`、`interrupt`、`restore`、
`loadfile/loadbin/verifybin`、`set *`、Flash/SD/file API 或 `reset/go`。因此失败点属于
transport acquisition，而不是本轮脚本判据。

### 37.4 §30.5 与后续边界

本轮**不满足 §30.5 的 readiness/acquisition 条件**，不能解除当前阻塞。此前独立 transport
recovery 双 session 的 `AUTHORIZED_RESUME` 证据仍按原始记录有效，但不能用历史成功覆盖本轮
新的 target acquisition 失败。

R3-03 计数冻结为：preflight `1/1 ENV_BLOCKED/TRANSPORT_NOT_READY`；PATCH 上传、PATCH
OTA、FULL 上传、FULL OTA、异常退出注错、LiveMap 恢复均 `0/1`。旧 PATCH `3/3`、SD-R2
preflight `1/1 PASS`、SD-R2 正式上传 `1/1 ENV_BLOCKED/TRANSPORT_NOT_READY` 和 stack
closure R3 `2/3` 均不变；C3/C13/C16 沿用 `PASS`，C1/C2、C4-C7、C14 仍为
`NOT_OBSERVED`。P2-6 仍为“进行中 / 等待独立验收”。

解除阻塞的最小边界不是再次盲跑 R3-03，而是由新的非实现裁定单独授权一次 transport-only
只读资格/整改会话：新证据根、重新核对 J-Link acquisition、不得写 Flash/SD/目标内存，且
至少取得两个独立 PID 的 readiness、attach、GDB/RTT 启动和自然收尾证据。若再次失败，必须
保留能区分 probe/USB/DAP 与 runner 生命周期的原始日志；在新的裁定前不得重跑 R3-03 或
消费任何后续 PATCH/OTA 配额。实现 agent 不得自行修 harness、换 MCU 路径或把 preflight
失败解释成产品失败。

### 37.5 文件系统与项目外审计

本轮项目内只产生并保留上述新证据根内容；未创建两个 MCU 文件，未修改原始证据根、原始
transport JSON、生产源码、冻结提示词或二进制合同，未创建验收合同，未执行 Git 远端操作。
项目外唯一报告写入为用户当轮授权的
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini`；独立只读核对为 `986B`，SHA-256
仍为 `DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`，本裁定会话未对其
写入、恢复、删除或清理。

## 38. P2-6 transport recovery candidate 独立裁定与 SD-R4 授权（2026-08-25）

### 38.1 唯一裁定与证据边界

本轮非实现独立裁定编号为 `P2-6-BR-20260825-TR-R3-01`，结论为
**`AUTHORIZED_RESUME`**。该裁定只允许创建一个新的正式 SD 验证轮次
`P2-6-SD-R4-01`；它**不**重跑、清零或改判 `P2-6-SD-R3-03`。R3-03 preflight
的 `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY` 仍是冻结历史事实，R3-03 后续配额不得
继续消费。

候选证据根为 `.cache/p2-6-transport-r3-20250825-01/`，manifest SHA-256 为
`F2E05A1C8ADEF51C3688299F74BA5170050A1902FD72C066F105CEAB22524DE4`。manifest 列出的
14 个文件经独立逐项复算，文件数、字节数和 SHA-256 全部匹配，实际文件数也是 14，且
manifest 之后没有追加文件。result JSON SHA-256 为
`D599FA47467267BE1B5E0B1ABA21931C8EFD98EDCB681627BF1B1E1E8FC03FBD`。

证据中的 `audit_id`、根目录和输出前缀使用了 `20250825`，而实际日期为 2026-08-25；
原始 JSON 的 `qualification_id=P2-6-TR-R1` 仍是 qualifier 源码硬编码值。这两项均定性为
**test-only legacy metadata defect**，不修改、覆盖或静默重标原始 JSON。唯一根、前缀、
result/manifest 哈希、两组 PID 和完整日志足以区分本轮实体，不构成证据身份阻断。
manifest 的 `generated_at=2026-08-25T13:12:07+08:00` 未随最终文件在 13:15 的重生成同步
更新，是一项自描述时间元数据缺陷；当前 manifest mtime 晚于全部 14 个被列文件，外部提供的
manifest SHA-256 精确匹配，且 14 个条目逐文件复算全部一致，因此不构成原始硬件证据污染。

### 38.2 两个 session 的独立复核

两次 session 使用冻结 `AT32F435RGT7 / SWD / 1000 kHz`，PID 分别为 `3564`、`2284`，
且彼此不同。每次均满足：Server readiness 唯一命中；目标连接成功；GDB/RTT 启动且退出码
为 0；固件 96B identity、RTT 签名、state 和 PASS marker 各唯一一次；Server 自然退出，
无 terminate/kill；端口 `24361-24364` 关闭；无残留进程。

关键日志 SHA-256：

| 文件 | SHA-256 |
|---|---|
| session 1 GDB | `8A9517FB2EB0E9C9618415ABEDA69E014FE6EA890E29EDD6DF247B1A30B8E342` |
| session 1 Server | `1B19F91BCB247B1974C45BF658C939871ACBA17F56DBE22D858C6B132082D870` |
| session 1 RTT | `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` |
| session 2 GDB | `7D5611AD2B8690CC2EBBD2EFBFBF4F5A4C9C8010BB86362D9D24333802560A25` |
| session 2 Server | `2C8FE818FAB32ABAFAC55EAAA8F78773DC342E22838BB708E1DD6C7ABE33E73D` |
| session 2 RTT | `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` |

两份 122 行 GDB 脚本各只有一次 `target remote`、一次允许的 `monitor halt`、只读内存检查、
`detach` 和 `quit`；静态审计及独立语义扫描均为零命中：无 `continue`、函数调用、`set *`、
`reset/go`、`loadfile/loadbin/restore`、Flash/SD/file API 或 RTT 下行写入。没有 Flash、SD、
目标内存、OTA 或产品路径操作。

### 38.3 §30.5 闭合与当前状态

本轮满足 §30.5 所需的 readiness、两次独立 acquisition、attach/detach、完整日志、自然
收尾和外部审计条件，因此 transport 阻塞已闭合。`JLinkDLL.ini` 前后均为 986B、SHA-256
`DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`，只有 mtime 变化，且
该路径属于用户本轮明确授权的 SEGGER 副作用范围。

正式计数冻结如下：

| 项目 | 当前计数 | 处置 |
|---|---:|---|
| 最初 PATCH 上传 | `3/3` | 冻结，禁止第四次 |
| SD-R2 preflight | `1/1 PASS` | 冻结，禁止重跑 |
| SD-R2 正式 PATCH 上传 | `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY` | 冻结，禁止重跑 |
| stack closure R3 | `2/3` | 冻结，禁止 R3-3 |
| SD-R3-03 preflight | `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY` | 冻结，禁止重跑 |
| SD-R4-01 preflight | `0/1` | 新轮次唯一一次 |
| SD-R4-01 PATCH/FULL/OTA/异常/LiveMap | 各 `0/1` | 依序执行，首失败即停 |

C3/C13/C16 沿用正式 `PASS`；C1/C2、C4-C7、C14 仍为 `NOT_OBSERVED`。P2-6 仍是
“进行中 / 等待独立验收”，本裁定不创建验收合同、不宣布完成。

### 38.4 可直接派给 SD-R4-01 实现 agent 的完整提示词

```text
你是 E-Track 项目的 P2-6-SD-R4-01 实现验证 agent，不是独立验收 agent。
只执行本提示词明确授权的 test-only harness 状态确认、一次无 SD 写入 preflight、一次
PATCH/FULL 上传和后续单次 OTA/异常/LiveMap 取证。不得独立验收或宣布 P2-6 完成。

固定仓库与不可改写计数：
- 根 D:\github\my\E-Track；分支 p2-6-implementation-20260819；
  HEAD/origin/main=99173123cae8c487b86efa8a4eecbbe73b1bb512。
- 最初 PATCH 3/3（三次失败，禁止第四次）；SD-R2 preflight 1/1 PASS；SD-R2 正式上传
  1/1 ENV_BLOCKED/TRANSPORT_NOT_READY；stack closure R3=2/3，禁止 R3-3。
- P2-6-SD-R3-03 preflight 已为 1/1 ENV_BLOCKED/TRANSPORT_NOT_READY，禁止重跑、清零、
  换路径或解释为产品失败；R3-03 PATCH/FULL/OTA/异常/LiveMap 均未执行且不得继续消费。
- C3/C13/C16 沿用 PASS；C1/C2、C4-C7、C14 只能用本轮新真实证据，当前仍 NOT_OBSERVED。

冻结输入（执行前逐项复算，不得替换）：
- ELF 35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019
- map 2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13
- test image AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5
- PATCH 2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B
- FULL 84D3F38420A9521FEEC1251CCE13A76F83F862935C2846A30D09DE1EC96DD2E7

证据根与 harness：
- 只能使用新的项目内根，例如
  D:\github\my\E-Track\.cache\p2-6-sd-r4-20260825-01-implementation\；
  先验证根及完整路径链位于仓库内且无 reparse point，不得复用任何旧根或候选
  transport 根 `.cache\p2-6-transport-r3-20250825-01\`。
- 当前唯一已授权的 harness 变化是 uploader 的 UNKNOWN=12 及同步诊断文本；不得再改
  tests/ota、生产源码、CMake/linker、冻结 prompt、PLAN-OTA.md、二进制合同或原始 JSON。
- 改动前后记录四个 harness SHA-256；运行 py_compile 与现有 27 项定向回归，必须全 PASS、
  warning=0、error=0。若 harness 有任何未授权变化，立即停止。

本轮外部授权必须重新取得：
- 启动 J-Link/GDB/RTT 前，用户必须重新授权准确的
  C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini 路径及其可能的 SEGGER mtime/内容副作用。
- 写 MCU SD 前，用户必须在本轮明确确认准确 PATCH 路径、准确 FULL 路径、创建/写入操作
  和副作用。此前 R3-03 的路径授权不延续到 R4。
- 仅可使用用户确认的两个新路径；实现 agent 不得自行选择并视为授权。用户未授权时停止。
- 获授权后只读检查父目录存在、路径链无 reparse point、目标文件不存在；父目录不存在、
  是 reparse point 或目标已存在时立即停止，不创建目录、不换路径、不消耗硬件配额。

建议路径（仅候选，不是授权）：
- PATCH `/P2-6A-PATCH-v2.8.0-to-v2.8.1-R4-20260825-01.etu`
- FULL  `/P2-6A-FULL-v2.8.1-R4-20260825-01.etu`

上述候选的父目录均为 SD 根 `/`，不要求创建新目录。仍须在硬件启动前由用户对这两个准确
文件路径、各创建并写入一次及可预见副作用作本轮明确授权；候选文本本身不构成授权。

硬件顺序与配额（每项恰一次）：
1. 新建唯一证据根并完成静态审计；无硬件动作不消耗配额。
2. 重新执行一次 SD-preflight 只读硬件预检，R4 preflight=0/1 -> 1/1。必须取得唯一
   96B 固件身份、确定停点、RTT 签名、SD_IsReady=1、VTOR=0x08010000、CFSR=0、BCB
   CONFIRMED、overlay FREE、write_calls=0、flash_calls=0、GDB exit=0，并记录 readiness、
   PID、GDB/RTT 启停、自然/强制收尾、端口和残留进程。
   SD-preflight 的冻结语义允许受控同步 continue 和唯一 BCB 读取调用；不要把 transport
   qualifier 的“无 continue/无函数调用”规则错套到这里。仍禁止 continue &、interrupt、
   restore、dump binary memory、loadfile/loadbin/verifybin、set *、reset/go、自由运行、
   Flash/SD/file API 和任何目标写入。首失败即停。
3. 仅 preflight 完整 PASS 后执行一次 PATCH 上传，PATCH=0/1 -> 1/1。只读 probe 必须为
   LV_FS_RES_UNKNOWN=12；使用现有 MI 分块协议，完整读回 SHA-256 必须等于冻结 PATCH。
   任一非 PASS、部分写入可能、缺块/乱序/越界、状态不确定或哈希不匹配立即停止，禁止重试。
4. PATCH 上传 PASS 后依序各执行一次：PATCH OTA、FULL 上传、FULL OTA、异常退出注错、
   LiveMap 恢复。FULL 读回 SHA-256 必须等于冻结 FULL；后一步只能在前一步完整 PASS 后开始。
5. 证据绑定：PATCH OTA -> C2/C4/C5/C6/C14；FULL OTA -> C1/C4/C5/C6/C14；异常退出与
   LiveMap 恢复 -> C7。上传成功不能替代 OTA apply 或异常路径证据。

任一以下情况立即停止，保存原始证据并等待新的非实现裁定：
- 任一 ENV_BLOCKED、TRANSPORT_NOT_READY、HARNESS_FAIL、PRODUCT_FAIL、身份/state/BCB/
  VTOR/CFSR/overlay 异常或任何状态不确定；
- readiness/GDB/RTT 未满足、marker 缺失/重复、terminate/kill、残留进程、监听端口或
  SEGGER 收尾不确定；
- 任何新 harness/生产源码/冻结数字或判据改动请求；
- workspace_peak>40960B、有效 stack_peak>8192B、guard 损坏、sbrk/TLSF required 增量非零、
  读回不完整或 SHA-256 不匹配；
- 需要重试、换路径、创建目录、覆盖/删除/移动旧文件，或超出本提示词配额。

收尾与禁止项：
- manifest 必须在全部回填完成后最后生成，生成后不得追加文件；逐文件记录 SHA-256。
- 不修改 R3-03、SD-R2、旧 PATCH 或 stack R3 证据；不修改候选 transport JSON/manifest。
- 不创建 docs/acceptance-contracts/P2-6-v1.contract.json，不独立验收，不 commit/push/
  merge/rebase/stash，不执行 P3/P4/Cloudflare。
- 即使全部步骤 PASS，也只回填 P2-6“进行中/等待独立验收”，并列出所有计数、C 项状态、
  设备观测、项目内外写入和收尾结果。
```

### 38.5 文件系统与项目外审计

本裁定会话只读复核 `.cache/p2-6-transport-r3-20250825-01/`，未启动硬件、未修改原始
transport 证据、未创建 MCU 文件、未修改生产源码或 harness、未创建验收合同，未执行 Git
远端操作。项目外 `JLinkDLL.ini` 仅按已授权范围复核，内容和大小未变。

## 39. P2-6-SD-R4-01 PATCH OTA 独立阻塞裁定（2026-08-25）

### 39.1 裁定

唯一裁定编号：`P2-6-BR-20260825-SD-R4-01-01`。

裁定结果：`KEEP_BLOCKED`。R4-01 PATCH OTA 的最终分类为 `HARNESS_FAIL`，不是
`PRODUCT_FAIL`、`ENV_BLOCKED` 或普通 `EVIDENCE_GAP`。本裁定不授权重跑 R4 PATCH OTA，
不授权开始 FULL 上传/FULL OTA、异常退出注错或 LiveMap 恢复取证，也不把 P2-6 改判为完成。

### 39.2 证据复核

实现证据根：`.cache/p2-6-sd-r4-20260825-01-implementation/`。独立复核的关键文件如下：

| 证据 | SHA-256 |
|---|---|
| preflight result | `52C830CC971379C1F01C1B33FB264C7B5D3656485A5831C262F911B9209CA827` |
| PATCH upload result | `9B5C8BEBA0020CD6F3D94DE294152FD74BA3F80C4AB160CFF457BB0E6851A65C` |
| PATCH OTA result | `2481C60D7E9B8E0337DAFE72840F591462A049996BC365535B584AF724AE71D2` |
| PATCH OTA GDB log | `15C78F3CD71795EDDCF54D7BD84191E4FFAA33E5AD162CC4F0DD762C523A1CFF` |
| PATCH OTA Server log | `BD908883C4557E7AE7DB366F00F85EEA6A92B413E7B9079C38FEA490E6CA9AE4` |
| PATCH OTA RTT log | `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` |
| failure audit | `07A4DF9E616564A9A1275300E8960BA790B177702F031DB929499EB90ACF8E0B` |
| closeout inventory | `CFB8B0BDBC553A29A46A7553E19671A9664427BEFCD858DFDA817C0B7D1098FD` |

closeout inventory 使用 `path|bytes|sha` 格式；243 个条目逐项复算为 `bad=0`。R4 preflight
和 PATCH 上传均为 `1/1 PASS`。PATCH OTA 的 GDB 日志中，下列 identity/state/result/PASS
marker 各唯一命中：

```text
P2_6_RTT_DRIVER import_started mode=2
P2_6_TRANSPORT stop_verified label=finish_import_entry pc=0x08045074
P2_6_IDENTITY PASS label=after_ota_fw header_bytes=96
P2_6_STATE PASS label=after_ota sd=1 vtor=0x08010000 cfsr=0x00000000 bcb=1 owner=0
P2_6_RTT_DRIVER result mode=3
P2_6_RTT_DRIVER PASS kind=PATCH page_state=3 mode=3
```

因此产品路径已确定到达结果态：`BCB=STAGED`、页面 mode=`3`、`SD_IsReady=1`、
`VTOR=0x08010000`、`CFSR=0`、overlay owner=`0`。Server/GDB 会话正常启动并以 exit 0
收尾，端口关闭且无残留进程，所以不能分类为产品失败或 transport 环境阻塞。

### 39.3 RTT 证据缺口与 HARNESS_FAIL 根因

PATCH OTA RTT 原始文件仅 107B，只包含 SEGGER/J-Link banner：

```text
SEGGER J-Link V8.18 - Real time terminal output
SEGGER J-Link V7.0, SN=-1
Process: JLinkGDBServerCL.exe
```

该 107B 文件与既有多轮 GDB-server RTT 文件逐字节相同；它不包含固件上行 payload，故
`rtt_connected=true` 只能证明 Telnet socket 建立，不能证明 `_SEGGER_RTT` Up channel 已绑定、
目标记录已到达或完整行已排空。

`tests/ota/p2_6_rtt_ota_driver.py` 的 `RttCapture.run()` 在 `socket.create_connection()` 成功后
即置连接成功；`run_gdb_session()` 又把该状态直接写为 `rtt_connected=true`。GDB 退出后，
`finally` 立即置 stop 并 join capture，没有 payload-ready 判据、当前 `_SEGGER_RTT` Up-channel
绑定证明、完整记录等待或有界 drain。现有离线测试只覆盖 socket 可连接，没有覆盖 banner-only、
延迟、截断或重复 payload。

冻结 ELF 的反汇编同时证明目标报告路径不是 no-op：`HAL::OTA_PatchApplyStaging`
(`0x08043944`) 返回后，`OtaUpdate::Session::Apply()+0xAC` 在 `0x08045F5C` 调用 apply，随后在
`0x08045F64` 调用 `HAL::OTA_P2_6_ReportPatchApply` (`0x08043A2C`)；报告公共路径
`p2_6_report_common` (`0x080434A0`) 调用 `SEGGER_RTT_printf` (`0x0804301C`)，且
`p2_6_measure_end()` 将 valid 置 1。`CONFIG_DEBUG_RTT_ENABLE=1`，RTT Up buffer 为 1024B、
模式为 `SEGGER_RTT_MODE_NO_BLOCK_TRIM`。由于 harness 未取得 payload，且 printf 返回值没有
被保存，缺失的测量数值不能从当前证据重建。

因此这是 host capture harness 把“TCP 已连接”误当成“RTT payload 已就绪”的确定性缺陷，
应分类为 `HARNESS_FAIL`。GDB 已证明的产品状态可以保留，但不能用它替代 C1/C2、C4-C7、
C14 所需的完整 RTT 数值记录。

### 39.4 计数、设备状态与 C 项冻结

| 项目 | 冻结状态 |
|---|---|
| 最初 PATCH 上传 | `3/3`，冻结，禁止第四次 |
| SD-R2 preflight | `1/1 PASS`，冻结 |
| SD-R2 正式 PATCH 上传 | `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY`，冻结 |
| stack closure R3 | `2/3`，冻结，禁止 R3-3 |
| R3-03 preflight | `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY`，冻结 |
| R4-01 preflight | `1/1 PASS`，冻结 |
| R4-01 PATCH 上传 | `1/1 PASS`，冻结 |
| R4-01 PATCH OTA | `1/1 HARNESS_FAIL`，冻结且禁止重跑 |
| R4-01 FULL 上传/FULL OTA/异常/LiveMap | 各 `0/1`，未授权启动 |

设备最后一次真实观测为 `BCB=STAGED`。在新的非实现裁定明确设备恢复边界前，禁止 reset、
BCB 操作、再次 PATCH OTA 或借其他步骤改变该状态。C3/C13/C16 沿用正式 `PASS`；C1/C2、
C4-C7、C14 继续为 `NOT_OBSERVED`。P2-6 保持“进行中 / 等待独立验收”，不得创建
`docs/acceptance-contracts/P2-6-v1.contract.json`。

### 39.5 最小下一步边界

下一步必须先派一个新的非实现 RTT capture-repair 裁定 agent，不得直接派实现 agent 接触
硬件。该裁定只允许离线审计，并决定是否授权 test-only 修改以下两个文件：

- `tests/ota/p2_6_rtt_ota_driver.py`
- `tests/ota/test_p2_6_rtt_ota_driver.py`

最小整改目标必须同时满足：

1. 明确区分 TCP socket connected 与 RTT payload ready；banner-only 不得记 PASS。
2. 绑定并验证当前冻结 ELF 的 `_SEGGER_RTT` Up-channel 数据来源，而不是仅连接 GDB Server
   暴露的 Telnet 端口。
3. GDB 产品路径结束后执行有界 drain；必须取得恰好一条完整目标记录，缺失、截断、重复或
   超时均 fail-closed。
4. 离线测试新增 banner-only、延迟 payload、截断 payload、重复 payload 四类负例及正常完整
   payload 正例。
5. 先完成离线整改、回归和独立复核；本裁定不授权任何新硬件轮次、SD 写入、OTA、reset、
   BCB 操作或项目外写入。
6. R4 PATCH OTA `1/1 HARNESS_FAIL` 永不清零、永不重跑。后续如需恢复设备或补证，必须由新
   非实现裁定基于 `BCB=STAGED` 明确给出新的轮次编号、恢复顺序和逐项配额。

### 39.6 文件系统与项目外审计

本独立裁定仅只读复核 R4 项目内证据并回填本文件与 `PLAN-OTA-EXEC.md`；未启动 J-Link、
GDB、RTT 或 OTA，未写 Flash/SD/目标内存，未修改生产源码、harness、冻结契约或 `.cache`
原始证据，未执行 commit/push/merge/rebase/stash。项目外
`C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini` 当前为 986B，SHA-256
`DF0194C43C748503D967FF574987C2EB4C0FF1940B58953565205C904909D9B0`；本裁定未对其写入。
端口 `24361-24364` 无监听，未发现 J-Link/GDB/RTT 残留进程。

## 40. P2-6-BR-20260825-RTT-CAPTURE-01 独立 RTT 采集修复裁定（2026-08-25）

### 40.1 审计范围与唯一裁定

本轮只读审计 R4 PATCH OTA 的 RTT 采集证据、冻结 ELF/map 的产品报告路径和
`tests/ota/p2_6_rtt_ota_driver.py` 及其对应单测；未启动 J-Link、JLinkGDBServerCL、
GDB、RTT logger，未连接或 halt 目标，未执行 reset/go/continue、Flash/SD/OTA/BCB 或
目标内存写入，未修改生产源码、冻结提示词、冻结契约、`tests/ota/` harness 或原始
`.cache` 证据，未创建验收合同，未执行 Git 操作。

唯一裁定：**`KEEP_BLOCKED`**。本轮不授权离线 test-only 修复，不生成实现 agent 提示词，
不授权任何 R4 PATCH OTA 重跑、FULL/异常退出/LiveMap 或其他硬件动作。R4 PATCH OTA
`1/1 HARNESS_FAIL` 继续冻结，P2-6 仍为“进行中 / 等待独立验收”。

### 40.2 独立 hash 复算

R4 证据根为
`.cache/p2-6-sd-r4-20260825-01-implementation/`。固定文件逐项复算结果如下，均与
先前冻结值一致，故未发现原始证据被修改：

| 文件 | bytes | SHA-256 |
|---|---:|---|
| `patch-ota/hw-01/logs/p2-6-sd-r4-01-patch-ota-hw-01-result.json` | 3588 | `2481C60D7E9B8E0337DAFE72840F591462A049996BC365535B584AF724AE71D2` |
| `patch-ota/hw-01/logs/p2-6-sd-r4-01-patch-ota-hw-01-gdb.log` | 1874 | `15C78F3CD71795EDDCF54D7BD84191E4FFAA33E5AD162CC4F0DD762C523A1CFF` |
| `patch-ota/hw-01/logs/p2-6-sd-r4-01-patch-ota-hw-01-jlink-server.log` | 50922 | `BD908883C4557E7AE7DB366F00F85EEA6A92B413E7B9079C38FEA490E6CA9AE4` |
| `patch-ota/hw-01/logs/p2-6-sd-r4-01-patch-ota-hw-01-rtt.raw.log` | 107 | `D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0` |
| `patch-ota/hw-01/failure-audit.json` | 2044 | `07A4DF9E616564A9A1275300E8960BA790B177702F031DB929499EB90ACF8E0B` |
| `closeout-file-sha256.txt` | 49814 | `CFB8B0BDBC553A29A46A7553E19671A9664427BEFCD858DFDA817C0B7D1098FD` |

`closeout-file-sha256.txt` 有 243 条 `path|bytes|sha` 记录。逐项按项目根解析并复算：
`bad=0`、`outside=0`、`missing=0`、`size_mismatch=0`、`hash_mismatch=0`、
`duplicate=0`、`reparse=0`。

当前两个 harness 也与固定输入一致：

| 文件 | 当前 SHA-256 | 修复后 SHA-256 |
|---|---|---|
| `tests/ota/p2_6_rtt_ota_driver.py` | `46206A97FC17095FB94B8FDBE081A4D5F74477E19AA14FD7DEE72414AB8F257D` | `N/A（本轮未授权、未修改）` |
| `tests/ota/test_p2_6_rtt_ota_driver.py` | `CA9D421CCDD50421F65FE3569C2302D3F3529838E8B8FC16307FFB95FF8DFE95` | `N/A（本轮未授权、未修改）` |

R4 result 的冻结静态输入字段仍为 ELF
`35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019`、map
`2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13` 和 test image
`AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5`；本轮未替换或重新
生成这些输入。

### 40.3 当前 RTT/GDB 状态机缺陷

逐行复核 `RttCapture.run()` 与 `run_gdb_session()` 得到以下状态语义：

| 状态 | 当前实现 | 独立审计结论 |
|---|---|---|
| `server_ready` | readiness marker 等待 | 有独立状态，R4 为 true |
| `rtt_socket_connected` | `socket.create_connection()` 成功后写 `socket_connected` | 只证明 TCP 建连，不是 payload |
| `rtt_payload_ready` | 不存在 | 缺失；banner-only 也会继续 |
| `gdb_started` / `gdb_exit_code` | GDB 启动及退出码有字段 | 退出码为 0 不能替代 RTT payload |
| `rtt_drain_complete` | 不存在 | GDB 结束后立即 `stop.set()`，没有有界 drain |
| `rtt_payload_complete` | 不存在 | 没有完整记录或 EOF/超时语义 |
| `rtt_record_count` | result 没有字段 | `measurements=[]` 仍可分类 PASS |
| `rtt_channel_binding_verified` | result 没有字段 | 未证明采集字节来自当前 ELF 的 Up channel |

`RttCapture.run()` 在 socket 建立后立即 `connected.set()`；异常路径也会调用
`connected.set()`，因此 `capture.connected.wait()` 无法区分“连接失败后异常通知”和有效
payload。`run_gdb_session()` 随后把该事件直接映射为 `rtt_connected=true`，GDB 返回后在
`finally` 立即停止 capture。`classify_transport_session()` 只检查 `rtt_connected`、GDB
退出和收尾字段，不检查 payload、记录数或 channel binding。

R4 result 明确记录 `rtt_connected=true`、`transport_classification="PASS"`，但同时记录
`measurements=[]`、`classifications=[]`；这正是当前状态机把“socket connected”误报为 RTT
成功的实证。

### 40.4 parser 与 mock 单测误报审计

`MEASUREMENT_RE` 和 `parse_measurements()` 的离线行为如下：

| 输入 | parser 记录数 | 当前 session 风险 |
|---|---:|---|
| 只有 SEGGER/J-Link banner | 0 | 仍可能因 socket connected 分类 `PASS` |
| banner 后延迟到达一条完整记录 | 1（若完整字节最终交给 parser） | 当前 GDB 结束即 stop，可能在记录到达前截断 |
| 被截断的记录 | 0 | 没有 fail-closed payload 门禁 |
| 两条相同完整记录 | 2 | 没有恰好一条记录门禁 |
| 一条完整记录加普通噪声 | 1 | parser 能忽略噪声，但 session 未验证 channel 来源 |
| socket 提前关闭且无记录 | 0 | EOF 不等于 payload fail；connected 仍可能为 true |
| GDB 非零退出但 RTT 有记录 | parser 可得到记录 | 分类先返回 `GDB_FAIL`，不得产生产品 PASS |

现有 `FakeCapture` 单测在没有任何 payload 的情况下只设置
`socket_connected=True` 和 `connected` event；`test_session_waits_for_ready_before_rtt_or_gdb_and_closes_naturally`
以及双 session 测试仍断言 transport `PASS`。因此当前 mock 明确允许“零 payload PASS”，属于
测试覆盖缺陷，而不是有效的 RTT 正例。现有单测没有 banner-only、延迟完整 payload、截断、
重复、socket 错误/提前关闭和“GDB 非零但 RTT 有记录”的 fail-closed fixture。

### 40.5 产品报告路径与 RTT channel binding

冻结 ELF/map 的静态路径仍为：

`HAL::OTA_PatchApplyStaging (0x08043944)` -> `HAL::OTA_P2_6_ReportPatchApply (0x08043A2C)`
-> `p2_6_report_common (0x080434A0)` -> `SEGGER_RTT_printf(0) (0x0804301C)`；
`p2_6_measure_end()` 将 measurement valid 置 1，`CONFIG_DEBUG_RTT_ENABLE=1`。当前
`_SEGGER_RTT=0x20053E1C`，Up buffer 为 `_acUpBuffer=0x20053A1C`、大小 1024B，模式为
`SEGGER_RTT_MODE_NO_BLOCK_TRIM`。

这只能证明固件具备报告路径，不能证明 R4 主机捕获了该路径产生的字节。Server 使用
`-rtttelnetport`，但 R4 result 只有 TCP 连接状态；没有只读 GDB memory snapshot 来核对
当前目标 `_SEGGER_RTT` 控制块的 `pBuffer/Size/WrOff/RdOff`，也没有把这些指针/偏移与
采集文件中的记录建立 provenance 关联。107B RTT 文件只有 banner，因而不能由 regex 命中、
GDB marker 或 socket 建连推断 Up-channel 绑定。

可审计方案选择为“当前 server RTT 通道 + 只读 GDB memory snapshot 绑定”：未来必须在
不写目标的前提下读取当前 `_SEGGER_RTT`、Up channel 0 描述符及环形缓冲偏移，并将采集到
的完整记录与该快照关联。该绑定证明需要真实目标状态，本轮禁止硬件，故无法闭合；这项
不可离线消除的缺口是 `KEEP_BLOCKED` 的决定性原因。

### 40.6 后续修复门槛与独立复核要求

本轮没有授权修改；若后续新的非实现裁定另行授权离线 test-only 修复，至少必须满足以下
不变量，且不得改变产品阈值、固件语义、OTA 配额、BCB 状态或历史轮次身份：

1. socket connected 永远不等于 payload ready；payload-ready 必须由一条完整、可解析且
   已建立 channel binding 的目标记录触发。
2. banner-only、截断、缺失、socket 错误/提前关闭、超时和 channel 未证实必须 fail-closed。
3. GDB 结束后执行有界 drain；必须得到恰好一条与 `--kind` 对应的完整 `P2_6` 记录，重复
   记录也失败；普通噪声可存在但不得改变记录计数。
4. GDB 非零、Server 非自然收尾、terminate/kill、端口残留或 capture 未停止立即失败；
   RTT 有记录不能覆盖 GDB 失败。
5. 离线 fixture 至少覆盖 banner-only、延迟完整 payload、截断 payload、重复 payload、
   完整 payload 加 banner/噪声且恰好一条、socket 错误/提前关闭、GDB 非零退出。

若未来获得授权，修复前后必须分别记录两个 harness SHA-256；离线回归必须逐项显示上述
fixture 的预期分类并 fail-closed。实现 agent 完成后，必须由第二个独立非实现 agent 在不改
文件的前提下重新复算修复后 hash、检查 diff 仅限这两个 test-only 文件、重跑全部 fixture，
并单独确认 channel-binding 方案仍要求真实只读目标证据。第二次独立复核通过前不得授权任何
硬件动作；本轮不产生“修复后 hash”，因为修复未授权、文件未修改。

### 40.7 计数、状态与文件系统边界

R4 PATCH OTA `1/1 HARNESS_FAIL` 保持冻结且禁止重跑；FULL 上传/FULL OTA/异常退出/
LiveMap 均为 `0/1`、未授权。旧 PATCH `3/3`、SD-R2 preflight `1/1 PASS`、SD-R2 正式
上传 `1/1 ENV_BLOCKED / TRANSPORT_NOT_READY`、stack closure R3 `2/3`、R3-03 preflight
`1/1 ENV_BLOCKED / TRANSPORT_NOT_READY` 均不清零、不重跑、不重解释。C3/C13/C16 继续为
`PASS`；C1/C2、C4-C7、C14 继续为 `NOT_OBSERVED`；P2-6 不改判完成，不创建
`docs/acceptance-contracts/P2-6-v1.contract.json`。

本轮主动写入仅限本文件和 `PLAN-OTA-EXEC.md`，两者均位于项目根内且所在路径链无 reparse
point。未写入项目外路径；项目外 `JLinkDLL.ini` 未被本轮触碰。
