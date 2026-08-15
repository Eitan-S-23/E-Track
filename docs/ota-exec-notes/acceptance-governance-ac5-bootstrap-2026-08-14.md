# 验收治理、GCC 默认构建与 AC5 自举整改记录

## 1. 范围

本次不重新打开 P2-5 产品卡，也不修改 OTA 状态机、升级协议或已验收行为。整改分为
三个部分：

1. 验收执行治理：冻结验收合同、拆分任务状态与单轮结果、建立证据失效矩阵、限制
   无条件全量复验，并规定紧凑证据包。
2. 构建角色纠正：默认生产链恢复为 GCC OTA App + GCC Boot + 模拟器；AC5 仅保留为
   本地硬件调试、工具链对照和兼容验证的辅助构建。
3. AC5 基础设施：保留干净 worktree 自举能力，但消除仅因工程文件时间戳变化而重复
   启动 UV4 的浪费；AC5 RAM 规避不得改变 GCC 正式固件的 heap/BSS 语义。

## 2. 已确认根因

- P2-5 原始验收只要求真机 OTA 状态链，后续执行中加入时序、视觉、宿主回归和模拟器
  生命周期，且标准 prompt 未版本化进入 `main`。
- 单一 provenance manifest 同时包含生产源码、测试和工具，导致 harness 变化也使总哈希
  改变，无法计算最小复验集。
- Keil `dep/lnp` 被 Git 忽略，原 AC5 脚本在干净 worktree 中无法自举；已有 uVision
  进程时还存在单实例异步返回风险。
- 前一轮为解决上述 AC5 问题，误把 `X-Track-App-AC5` 提升为默认一键入口，与
  `P1-2-target-linker-decision-2026-07-26.md` 的冻结结论冲突：
  `X-Track-App-GCC` 才是 OTA/CI 唯一正式 App 产物，GitHub Actions 同时构建
  `X_Track_App_GCC` 和 `X_Track_Boot`。
- 前一轮还把共享 LiveMap 行缓存对所有 MCU 构建改成 LVGL heap 动态分配。该改动虽关闭
  AC5 `RW_IRAM1` 链接阻断，却无必要地改变了 GCC 正式固件的既有运行时语义。
- AC5 自举最初只比较 `proj.uvprojx` 与 `dep/lnp` 时间戳。工程内容未变化、仅 mtime 被
  checkout 或工具刷新时，也会触发数分钟 UV4 全量构建。
- CMake 工程无条件执行 `set(CMAKE_OBJECT_PATH_MAX 140)`，覆盖调用方传入的 1024，本地
  长路径默认构建因此仍报告对象路径风险。

## 3. 设计决定

### 3.1 验收合同与结果

- 每轮独立验收必须引用 `docs/acceptance-contracts/` 下已冻结、已审批、带版本号的 JSON
  合同；`.claude` prompt 只能作为辅助说明，不能成为唯一标准。
- 任务状态仍为 `待办/进行中/阻塞/完成`。单轮验收结果独立使用 `PASS`、
  `PRODUCT_FAIL`、`HARNESS_FAIL`、`EVIDENCE_GAP`、`ENV_BLOCKED`。
- 产品失败通常使任务保持 `进行中`；只有契约矛盾、不可实现或必需外部依赖缺失才使用
  `阻塞`。
- 性能门禁必须来自产品 SLA、协议契约或明确安全比例，禁止将历史测量值加极小余量后
  反向冻结为门槛。

### 3.2 证据失效与复用

- 输入分为 `Production`、`Validation`、`Governance` 三类 manifest，并额外记录 fixture、
  硬件状态和外部产物哈希。
- 生产源码或构建配置变化只失效相关构建及下游证据；测试、fixture 或 harness 变化只
  失效由它们产生的证据；合同变化先重映射矩阵，只补跑新增或失配条件。
- harness 必须 fail-closed，禁止常量 PASS。PASS/FAIL 都必须绑定原始证据路径；修
  harness 不得自动触发无关产品回归。
- 收口只保留合同、矩阵、命令清单、分类 manifest、产物哈希、决定性原始日志和视觉
  证据哈希，不归档数 GB 构建目录或重复源码副本。

### 3.3 默认 GCC 与显式 AC5

- `build_f435_and_simulator.bat --no-pause` 默认执行 Release/Ninja CMake configure，构建
  `X_Track_App_GCC`、`X_Track_Boot`，再构建模拟器。配置固定
  `SOURCE_DATE_EPOCH=1786320000`，与 CI 对齐。
- `--with-ac5` 在 GCC 后附加 `X-Track-App-AC5`；`--ac5-only` 只构建 AC5，不运行 GCC
  或模拟器。
- `--legacy` 只选择旧布局 AC5 目标，必须与 `--with-ac5` 或 `--ac5-only` 配合；旧布局
  产物禁止参与 OTA 验收。
- 可控临时目录和编译缓存统一重定向到仓库内 `.cache`。CMake 工程仅在调用方未指定时
  使用 140 的兼容默认值，不再覆盖命令行的 1024。

### 3.4 AC5 自举与去重

- `build_f435.ps1 -BootstrapIfNeeded` 在 `dep/lnp` 缺失、为空或工程内容变化时运行一次
  `UV4.exe -b`；已有 UV4 进程时 fail-fast，超时后终止进程树。
- 首次兼容旧元数据时仍以 mtime 判断；元数据确认有效后，在目标 `Objects-*` 目录写入
  `proj_<target>.uvprojx.sha256`。哈希先统一 CRLF/LF，后续内容相同则忽略时间戳及纯
  换行抖动。
- UV4 完成后必须校验可解析的 build summary、`0 Error(s)`、非空 `dep/lnp` 和有效工程
  哈希绑定，再进入现有 `AutoStale -> armlink -> fromelf` 流程。
- UV4 对被追踪 `RTE_Components.h` 产生的尾随空格会自动清理，但实际 RTE 组件变化保留。

### 3.5 行缓存工具链隔离

- `__CC_ARM` 下继续从 128 KiB LVGL 池按需分配 24,624B 行缓存，页面卸载时释放；分配
  失败只 warning 一次并降级为无缓存读取。
- GCC 正式固件恢复静态行缓存，不调用 release，不改变历史 heap 生命周期和性能语义。
- 模拟器保持其既有非 `ARDUINO` 路径，不引入 AC5 RAM workaround。

## 4. 验收方法

1. 运行 acceptance bundle、provenance、构建模式和 AC5 RAM 分支专项测试。
2. 执行默认批处理，确认只有 `[GCC]`、`[SIM]`，不存在 `[AC5]` 或 `[BOOTSTRAP]`。
3. 执行 `--ac5-only`，确认不存在 GCC/MSBuild 阶段；首次必要自举后再次执行必须
   `[BOOTSTRAP]=0`。
4. 对 GCC App/Boot 和 AC5 产物独立读取 size、map、时间戳和 SHA-256，不以批处理最终
   `[OK]` 作为唯一通过依据。
5. 最终执行 Python/PowerShell/XML/JSON 解析、模板校验器、`git diff --check`、进程和
   项目外写入审计。

## 5. 实施结果

### 5.1 验收治理

- 新增 `docs/acceptance-execution-contract.md`、版本化合同/矩阵模板和
  `Tools/acceptance/validate_bundle.py`，落实冻结合同、五类单轮结果、失效矩阵、
  fail-closed harness 与紧凑证据包。
- `source_manifest.ps1` 保留 Legacy 模式并增加 `Production`、`Validation`、
  `Governance` profile。当前合同由矩阵 `contract_sha256` 单独绑定，避免 Governance
  manifest 自引用。
- 校验器重新读取分类 manifest 与原始证据并核对 SHA-256；路径越界、缺文件、哈希不符
  或常量式汇总均不得宣告 PASS。

### 5.2 默认 GCC 生产链

最终命令为：

```text
cmd.exe /d /c build_f435_and_simulator.bat --no-pause
```

退出码 0、耗时 332.640 秒；阶段只有 `[GCC]`、`[SIM]` 和 `[OK]`，
`[AC5]/[BOOTSTRAP]` 行数为 0。构建输出统计为 583 条 warning 行、0 条 error 行；warning
均为既有 GCC/MSVC 编译告警，未伪装为“无警告”。CMake 对象路径风险行数为 0，最终
cache 确认 `CMAKE_OBJECT_PATH_MAX=1024`，调用方值未再被工程覆盖。

`arm-none-eabi-size`：

```text
text=597324 data=932 bss=556912 dec=1155168  X-Track-App-GCC.elf
text=14720  data=4   bss=9780   dec=24504    X-Track-Boot.elf
```

App 的标准 `size` BSS 包含 linker overlay，不能直接当作同时驻留 RAM。按最终 map 的主
RAM 段计算为 348,352 / 360,448B，剩余 12,096B；静态行缓存已回到 GCC 正式固件且仍在
契约内。

| 产物 | 大小 | 时间戳 | SHA-256 |
|---|---:|---|---|
| `X-Track-App-GCC.elf` | 859,836 | 2026-08-15 00:16:22.654 | `E6257710EE7BF183E3DD659A22599993DF837CAAB244103D8D5AE809FF55DC42` |
| `X-Track-App-GCC.hex` | 1,682,838 | 2026-08-15 00:16:22.806 | `FC3F3247CD38EB7F3E4D1AB50D7EB030E3DCD20EE6ACFB10099FA823055CCDFF` |
| `X-Track-App-GCC.bin` | 598,756 | 2026-08-15 00:16:22.871 | `7483766934E5B5BBFFC480B7268DFA4D8C83244AB5A1F7ACDEB811F6796C16BC` |
| `X-Track-App-GCC.map` | 2,412,710 | 2026-08-15 00:16:22.660 | `468861712A43EDE09BB6942AB542FEA00872EDF235D3D49DAB9A2F1416D7C243` |
| `X-Track-Boot.elf` | 36,860 | 2026-08-15 00:16:19.679 | `D21713CA2C1EFEAC949F8EC0FFDDACAC439FED6BF26F9C65641BEE24464FDABC` |
| `X-Track-Boot.hex` | 41,485 | 2026-08-15 00:16:21.265 | `FF3BADEF69BE6D97FD66815B8DF90EFD962A708B559C8951D4B56380F8001F71` |
| `X-Track-Boot.bin` | 14,724 | 2026-08-15 00:16:21.546 | `5842FF3E19BA9E1EAAEA10F27E825C7B6EFC278B200531014B0DBA61264F6594` |
| `X-Track-Boot.map` | 100,450 | 2026-08-15 00:16:19.682 | `14E7A8ADDD37DFE71744C11AB0DB60D5C535FBE725FE3E950F82354F34A4FC93` |
| `LVGL.Simulator.exe` | 5,864,960 | 2026-08-14 23:42:39.959 | `FEC135DC6E11B71DA6DC2E799A602FAFCC3D9A83E0437BE32CEC18FE3405BC30` |

### 5.3 AC5 自举、去重与 RAM

干净副本首次 AC5 自举的既有有效证据为 468.719 秒，UV4 `0 error / 0 warning`，证明
`dep/lnp` 缺失时可从项目内自举。该证据只证明 AC5 辅助链，不再作为默认构建证据。

本轮在引入工程哈希前执行 `--ac5-only`，因 `proj.uvprojx` mtime 晚于元数据而再次启动
UV4，耗时 377.2 秒；工程实际内容未改变，证明纯 mtime 规则仍会浪费时间。加入目标级
SHA-256 stamp 后再次执行：

```text
[AC5] Building auxiliary target X-Track-App-AC5...
[AutoStale] stale sources (incl header deps): 0
[LINK] armlink --via Objects-App-AC5\X-Track-App-AC5.lnp
[OK] target X-Track-App-AC5 build complete (armlink/fromelf exit code 0)
Program Size: Code=301084 RO-data=289372 RW-data=1332 ZI-data=532248
```

第二次退出码 0、耗时 33.2 秒、`[BOOTSTRAP]` 行数为 0，且未运行 GCC 或模拟器。AC5
map 中 `RW_IRAM1` 继续为 351,504 / 360,440 字节，剩余 8,936 字节。动态缓存只存在于
`__CC_ARM` 分支；GCC 已恢复静态缓存。

### 5.4 校验与清理

- 专项测试 `31 passed in 27.35s`，覆盖 acceptance bundle fail-closed、分类 manifest、
  GCC/AC5 构建模式、CMake 路径上限、AC5 内容哈希门控和工具链隔离的行缓存策略。
- Python AST、PowerShell parser、`proj.uvprojx` XML 和两份 JSON 模板均解析通过；模板
  以 `--allow-draft` 运行校验器得到
  `VALIDATION=PASS contract=TASK-v1 round=YYYYMMDD-HHMMSS overall=NOT_RUN`。
- UV4 自举曾给被追踪的 `RTE_Components.h` 增加三处尾随空格；已仅清理本轮生成噪声，
  文件恢复与 index 一致，最终 `git diff --check` 通过。
- 删除本轮 pytest cache 的 4,095B 文件；`.cache` 内只保留批处理约定的空目录骨架，
  后续构建可按需重建。未运行 J-Link/RTT、未改 SD 卡、未写项目外路径，且无残留
  `UV4`、`LVGL.Simulator` 或 `JLinkRTTLogger` 进程。

## 6. 独立审查后的第二轮整改（2026-08-15）

首轮整改经独立审查后确认方向正确，但存在五项不能用于正式验收的结构性缺口：命令和
产物未做实物闭环、最小复验仍依赖人工解释、Production manifest 漏实际 GCC CMake
入口、新测试未进入 CI，以及 AC5 默认目标和 RTT map 指令冲突。本轮已完成以下纠正：

1. 合同和矩阵升级为 v2。合同强制包含 Production、Validation、Governance 三类
   manifest，并冻结精确命令、允许退出码、产物包内路径和判据对输入/命令/产物的依赖。
2. 判据矩阵新增实际观测值、`EXECUTED/REUSED` 和复用来源。PASS 的观测值必须由校验器
   与布尔、数值或状态链 gate 直接比较。
3. 校验器现在拒绝空命令/空产物 PASS、未批准退出码、命令替换、无输出证据、产物路径
   越界、产物替换、缺文件、大小不符和 SHA-256 不符。非零退出码只有在合同明确批准时
   才合法，避免误伤故障注入负例。
4. 新增前后轮自动比较：三类 manifest、external input、判据、命令、产物定义或上一轮
   结果变化都会生成明确 rerun reason，并输出最小 `rerun_criteria`、`required_commands`
   和 `required_artifacts`。矩阵使用 `REUSED` 时，最终校验会重新计算失效集并核对上一轮
   观测值、证据、命令和产物。
5. Production manifest 已纳入
   `MDK-ARM_F435/cmake-generated/CMakeLists.txt`。生产 CI workflow 只进入 Production；
   新增轻量 `acceptance-governance.yml` 进入 Validation，避免纯 Spec/校验器修改触发完整
   GCC 构建。
6. `build_f435.ps1` 默认目标改为 `X-Track-App-AC5`；所有窄命令均显式写目标，烧录
   App-AC5 后 RTT 地址改从 `Listings-App-AC5/X-Track-App-AC5.map` 读取。

专项回归扩展到 40 项，覆盖审查中构造的 `exit_code=1`、`../../missing.bin`、空命令、
空产物、命令/产物替换、缺失实物、manifest 漏项、自动 rerun plan 和 CI 接线。该轮只改
验收工具、Spec、CI 和 AC5 辅助入口默认值，没有改变 GCC CMake 生产配置或固件源码，
因此不重复执行完整 GCC/AC5 构建；使用解析、静态测试和端到端临时证据包验证即可。

## 7. 独立审查后的第三轮整改（2026-08-15）

第二轮整改再次复审后发现：复验仍错误绑定包含绝对 `RepoRoot` 和全局 `HEAD` 的 JSON
文件哈希；manifest 结构可伪造；Ubuntu 路径守卫使用固定反斜杠；跨任务/同版本合同可复用；
performance 判据可借 `frozen_requirement` 绕过；`PRODUCT_FAIL` 可缺命令和产物；纯治理测试
仍会匹配完整固件 workflow。本轮完成以下收紧：

1. 正式输入 manifest 升级为 `etrack-input-manifest-v2`。合同分别记录 JSON 完整性哈希
   `manifest_json_sha256` 和稳定文件集合 `manifest_sha256`；复验只比较后者。
2. 合同绑定的 `source-manifest.json` 不再包含绝对根目录、`HEAD`、mtime 或生成时间。
   `RepoRoot`/`Head` 仅保留在不参与失效判定的 `summary.json`。两套不同目录、不同提交号且
   文件 mtime 不同的夹具已生成逐字节相同的 txt/JSON manifest。
3. 校验器现在复核 manifest schema、字段集合、FileCount、排序、重复路径、逐项长度/哈希、
   profile 必需入口、内部 `ManifestSHA256` 和配套 `source-manifest.txt`。空/伪造/漏项
   manifest 均 fail-closed。
4. 证据复用只允许完全相同的冻结合同，或同一 `task_id`、版本加一且
   `parent_contract_sha256` 精确绑定上一合同的直接后继。跨任务、同版本篡改、跳版和错误
   父合同均拒绝生成 rerun plan。
5. performance 判据只能使用 `product_sla`、`safety_ratio` 或 `protocol_contract`。实际执行
   的 PASS/FAIL 必须有命令 provenance；产品/harness FAIL 还必须绑定真实产物。
6. `worktree_guard.ps1` 改用平台目录分隔符和平台正确的大小写比较；Ubuntu `pwsh` 由轻量
   governance workflow 覆盖。firmware workflow 改为只监听产品 OTA 测试 glob，不再因
   `test_acceptance_bundle.py` 等纯治理测试变化触发完整 GCC 构建。

治理专项最终为 `51/51`：acceptance `26/26`、AC5 RAM `3/3`、构建治理 `14/14`、provenance
`8/8`。本轮未改变 GCC CMake、固件源码或 AC5 工程输入，不重复运行 GCC/AC5/模拟器。

## 8. 独立审查后的第四轮整改（2026-08-15）

第三轮复审继续发现五项 fail-closed 缺口：manifest 仍只验证自洽、Production 漏掉真实
RTE 编译输入、相同矩阵可循环自复用、rerun plan 未成为必需且带哈希的证据，以及输出
守卫未拒绝最终文件 symlink。本轮完成以下整改：

1. 新增 `Tools/provenance/manifest_profiles.json` 作为生成器与校验器唯一共享的 profile
   定义。Production 纳入 GCC 实际使用的 RGT7 设备目录与 `RTE/_X-Track`，但排除 AC5
   专用 `_X-Track-App-AC5` 和旧 CGU7 输入；Validation 纳入 profile 配置自身，避免
   PowerShell 与 Python 白名单再次漂移，同时不扩大无关失效范围。
2. 最终校验强制传入 `--repo-root`，历史复用强制再传 `--previous-repo-root`。校验器在指定
   Git worktree 中重新执行同一 profile 枚举，逐项读取真实路径、长度和 SHA-256，与包内
   manifest 做精确集合比较；内部自洽但伪造的记录不能通过。
3. 当前矩阵使用 `REUSED` 时，必须绑定上一矩阵文件 SHA-256、包内 rerun plan 路径及该
   文件 SHA-256。最终校验会重新计算计划并比较完整 JSON 内容，缺失、替换或人工改写均
   fail-closed。
4. 当前/上一矩阵文件哈希和 `round_id` 必须不同；上一判据只有自身为 `EXECUTED PASS`
   时才可复用。相同矩阵自指和链式 `REUSED` 均被拒绝，消除无需真实执行证据的循环自证。
5. `Assert-WorktreeFileOutput` 现在检查最终已存在文件的 reparse/link 状态；manifest txt、
   JSON、summary 和源码复制目标均在写入前调用文件守卫。

本轮同时保留第三轮解决的时间抖动问题：复验只比较稳定 `ManifestSHA256`，该指纹不包含
mtime、绝对 worktree、全局 `HEAD`、生成时间或保存目录。只改时间戳、换等内容 worktree
或提交无关 profile 文件不会触发产品判据复验；真实相对路径、长度或内容变化仍会失效。

验收校验器负例扩展到 31 项并已通过，覆盖伪造 manifest、RTE 漏项、自矩阵/同轮次复用、
缺失计划、错误计划哈希和合法单跳复用。完整治理回归共执行 57 项：acceptance 31、AC5
RAM 3、构建治理 14、provenance 9；本机 56 项通过，唯一跳过项是 Windows 当前权限无法
创建 symlink，Ubuntu CI 保留并执行该负例。本轮只修改验收治理、测试和规范；仅运行
可复现时间宏的单文件 GCC 探针，不运行完整 GCC 固件、AC5、模拟器或真机流程。

## 9. 独立审查后的第五轮整改与最终验收（2026-08-15）

第四轮复审后仍发现三项跨平台和归属缺口：PowerShell 使用普通 `git ls-files` 文本输出，
导致 Git 引号转义的中文路径被跳过；rerun plan 写入只检查最终文件，没有拒绝已有父目录
symlink/junction；两个合同模板虽然被 CI 和测试直接读取，却未归属任何 manifest。本轮完成：

1. PowerShell 生成器改为读取 `git ls-files -z` 原始 stdout 字节，按 NUL 分隔并严格 UTF-8
   解码；路径按 UTF-8 字节序排序。Windows PowerShell 5.1 与 `pwsh 7.6` 均和 Python
   校验器对真实 worktree 逐记录一致。
2. rerun plan 输出在创建父目录前逐级检查完整父链，创建后、实际写入前再次检查；最终文件
   或任一父目录为 symlink、junction 或 reparse point 时均 fail-closed。另增不依赖本机
   symlink 权限的父链遍历单元测试，避免本地跳过形成假阳性。
3. `template.contract.json` 与 `template.evidence-matrix.json` 精确加入 Validation profile
   的 `top_files` 和 `required_paths`，但不包含整个活动合同目录，避免合同自引用和跨任务
   无关失效。

最终本地治理测试共 59 项：57 项通过，2 项按预期因 Windows 当前权限无法创建真实
symlink 而跳过；Ubuntu CI 会执行这两个物理负例。Validation manifest 共 78 条，包含
8 条中文路径和两个合同模板。PowerShell 5.1、`pwsh 7.6` 与 Python 重建的文件集合和稳定
SHA-256 相同；PowerShell、Python、JSON、YAML、XML 解析及 `git diff --check` 均通过。

严格按新结果分类，提交前治理整改结果为 `EVIDENCE_GAP`，唯一缺口是远端 Ubuntu 尚未
产生两个真实 symlink 负例的执行证据。提交后远端 governance CI 全绿即可转为正式
`PASS`；该证据缺口不涉及产品代码，无需重新运行 GCC、AC5、模拟器或真机验收。

## 10. 结论

P2-5 产品卡保持完成；流程审计和构建基础设施整改不重新打开产品验收。默认正式构建已
恢复为 GCC App + Boot，AC5 只在明确请求时运行。AC5 仍可从干净 worktree 自举，但普通
增量运行由工程内容哈希门控，不再因 mtime 抖动无条件支付数分钟 UV4 成本。AC5 RAM
workaround 也被限制在 AC5 编译器分支，不再改变 GCC 生产固件的运行时语义。正式验收
必须使用 v2 合同和矩阵；首轮 v1 模板与“已自动化最小复验”的旧表述由本节取代。
