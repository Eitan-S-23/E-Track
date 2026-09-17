# P3-4 解析器整改（P34-P01..P34-P07、P34-PR2-01..PR2-05、P34-PR3-01/PR3-02）— 实现与开发自测记录

- 日期：2026-09-17
- 分支：`dev/flutter/p3-4-link-stats`
- 工作树：`D:\github\my\E-Track\.cache\worktrees\p3-4-link-stats`
- 被整改基线：`0441f7862eaa65d201b49814dbd556ec98e8515a`（tree
  `ea6bd78250c17a0311b992f1527b192bc29af65f`），原交付提交 `9518361`、
  `ada2f15`、`0441f78`
- 本批范围：三批合并交付，均为 `Tools/ota/p3-4-link-stats/` 内的解析器与自测：
  1. **第一批**（预审阻断项，7 类）：`docs/ota-exec-notes/P3-4-wiring-impl-2026-09-16.md`
     §10 登记的 P34-P01 ~ P34-P07；
  2. **第二批**（复审阻断项，5 类）：`docs/ota-exec-notes/P3-4-parser-rereview-2026-09-17.md`
     §Findings 登记的 P34-PR2-01 ~ P34-PR2-05；
  3. **第三批**（准入复核阻断项，2 类）：非实现会话的准入复核报告
     `.cache/p3-4-parser-review-pr2-followup-20260917/review.md` 登记的
     P34-PR3-01（样本数值域仍漏检）与 P34-PR3-02（包 SHA 格式校验可绕过）；
     该轮明确 **PR2-01/03/05 可关闭，PR2-02/04 尚需补修**，本批一并补修。
- 复审依据（**只读输入**）：`docs/ota-exec-notes/P3-4-parser-rereview-2026-09-17.md`
  （13,621 B，SHA-256
  `09725ff3978eda243c74c0c8671f3025c108337bbef19dfcd8d73b3b3263b244`），
  由非实现会话出具；本会话未改其字节、未改被验代码、未执行 CI、未提交推送。
- 准入复核依据（**只读输入**，位于本工作树内、属复核会话资产）：
  `.cache/p3-4-parser-review-pr2-followup-20260917/review.md`
  （10,889 B，SHA-256
  `7f13a9299aefcc8f49adedafe1e80a005941fdd3ae6b4e595127ce426e374397`；其余文件哈希见
  §1.3）。本会话未重跑其 runner、未覆盖其任何文件（该目录内 `cli/`、`probes/`、
  `tmp/` 与全部 JSON 均为只读引用）。
- 不重开 P3-4 实验卡；不改 Flutter/MCU 产品实现、线协议、冻结契约、profile
  定义、workflow 与历史冻结包。
- 本轮结论定位：**实现 + 开发自测结果**。正式验收仍为 **NOT_RUN**（P3-4 尚无
  已审批冻结合同与矩阵），本记录不构成独立验收 PASS，也不构成 P3-4 完成声明。

---

## 0. 整改前的影响分析（先分析再批量修复）

### 0.1 第一批复现路径与既有事实

预审证据目录 `.cache/p3-4-parser-review-20260917/`（主工作树，**只读**）给出：

- `adversarial-results.json`：19 个合成探针，2 通过 / 17 暴露问题；
- `mutation-audit.json`：25 条鉴别力配对中 22 条为 `AssertionError`，3 条为
  运行期异常（`_clock_segments` 置空导致 `len(None)`；`parse_sample` 置空导致
  `samples[0]` 的 `IndexError` ×2）；
- `capture-audit.json`：Windows 整份捕获中，行 307–976 的观测块有 9 个实例段、
  摘要只声明 8 个 ACK，却把缓冲区里的 210 个 ACK 合并进全报告（266 ACK / 64 段）。

### 0.2 第一批七个问题在代码中的确切位置与影响面

| 发现 ID | 位置 | 影响面 |
| --- | --- | --- |
| P34-P01 实验参数混组 | `aggregate()` 只按 `label` 归并；`devices` 只收集不分组 | 设备/MTU/写模式/波特率/超时/重试/包/sender 任一变化都会被合成同一个 P99 |
| P34-P02 污染块仍被合并 | `aggregate()` 用 `check_group_only(group)` 重跑**宽松模式**，丢掉解析期 fatal 与严格模式结论；只按 `outcome=='ok'` 过滤 | 真实 Windows 块（9 段 / 210 vs 8）整块进入合并 |
| P34-P03 只按行数核对 | `_observed_counts()` 只做 `len(...)` 计数，无偏移集合 | 复制一个 ACK 的 `off` 可顶替另一个缺失段；删除首发 `off` 零检出 |
| P34-P04 空捕获/null 摘要绕过 | `parse_log()` 中 `summary is not None and not isinstance(...)` 短路；空文件无任何检出 | `--device-capture` 下空文件 exit 0；`OTA_LINK_STATS null` 清空缓冲区且无 BAD_JSON |
| P34-P05 字段/类型/范围核对不全 | `_check_structure()` 用 `schema in frozenset`（`{}` 触发 `TypeError`）；`_check_counters()` 用 `value < declared`（`"1"` 触发 `TypeError`）；`_check_quantiles()` 只核 ACK 分位数与 `elapsedUs`；`strictFieldsComplete` 只看计数键 | 非法类型直接 traceback，`--json` 无结构化结论；阶段指标与 `getInfo.totalUs` 篡改不可见；删 `writeMode`/`mtuSource` 仍 `strictFieldsComplete=true`；`elapsed=0` 的成功传输仍可合并 |
| P34-P06 合法早到 ACK 被误判 | `_clock_segments()` 把 `ack_early_invalid` 当普通时间戳 | 发射端合法输出序 `ack_early(10) → durable(11) → ack_early_invalid(10) → segment_first_send(20)` 被报 `CLOCK_NONMONOTONIC` |
| P34-P07 鉴别力把异常当断言失败 | `selftest.test_negative_cases_discriminate_on_check_removal()` 的 `except Exception` | 3/25 配对靠运行期异常"通过"，不证明任何判据有鉴别力 |

### 0.3 依赖面的实测核对（不是推测）

在改造前先用现有解析器探明真实捕获的形状，作为新语义的输入：

1. **真实捕获的身份签名**（`aggregate` 现无此概念）：Windows 8 个 `ok` 块与
   Ubuntu 7 个 `ok` 块均为 `(device=AA:BB, mtuChunkBytes=247, mtuRequested=247,
   mtuSource=缺, writeMode=缺)`；另有 1 个 `fail` 块为 `mtuChunkBytes=20`。
2. **污染块（Windows 行 307–976）**：9 个实例段，每段内部 `segment_first_send`
   的 `off` 唯一；第 8 段内 `off=0`/`off=256` **重复首发**（`off=0` 在行 885 与
   941 各出现一次）。发射端 `ota_link_stats.dart:253` 用
   `if (_sentOffsets.add(offsetBytes))` 保证**同一实例内首发偏移唯一**，因此段内
   重复首发即为"同段内存在多个实例"的确证，而非解析器误报。
3. **阶段指标可重算性**：对真实捕获中 `calls` 与样本数精确相等的块，
   `gattWrites/discovers/platformWrites` 的 `minUs/p50Us/p95Us/maxUs` 与
   `getInfo.totalUs` 全部与样本重算一致 → 新增这些核对**不会**在真实捕获上
   产生误报。
4. **旧发射端缺字段全集**：真实日志（含夹具切片）缺
   `bind.writeMode`、`bind.mtuSource`、`transfer.ackEarlyInvalid`、
   `transfer.ackEarlyUnsent`、`getInfo.failures`、`discovers.errors`、
   `platformWrites.errors`（+ 可选元数据 `attempt`/`attempts`/`failure`/
   `attemptEndUs`）。因此 `writeMode`/`mtuSource` 必须纳入"必需字段"判定，
   `strictFieldsComplete` 才能反映真实核对范围。

### 0.4 第一批修复设计（与冻结语义的对应关系）

- **P34-P01**：新增侧车输入 `--group <json>`，声明实验身份
  （device / mtuChunkBytes / mtuRequested / writeMode / baud / timeoutMs /
  maxRetries / packageSha256 / packageBytes / senderCommit / firmwareCommit /
  captureMethod / appState）与 `inputs[]`（路径 + SHA-256）。`--log` 可重复。
  未声明身份时合并结果标 `eligibleForThreshold=false`，理由
  `GROUP_IDENTITY_NOT_DECLARED`；观测签名冲突时按签名拆分为独立输入组并报
  `GROUP_IDENTITY_CONFLICT`(warn)，不产出跨组混合统计；声明与观测不符报
  `GROUP_IDENTITY_MISMATCH`(fatal)；日志未被侧车绑定报 `INPUT_UNBOUND`(fatal)；
  SHA 不符报 `INPUT_SHA_MISMATCH`(fatal)。行格式保持冻结，未新增/修改任何
  日志字段。
- **P34-P02**：`check_group()` 把结论写回 `group.findings`，`aggregate()` 一律
  复用该结论，不再重跑宽松模式。区分三层：
  `attributable`（无 fatal、无 `STRAGGLER`、单实例段、偏移集合自洽）→
  `clean`（另需 `outcome=='ok'` 且 `ackSamples=='complete'`）→
  `threshold`（另需身份已声明且一致）。不合格轮次进入 `excluded[]`，保留
  行号与理由；只有 `attributable` 的块样本才允许进入任何数值池。
- **P34-P03**：新增逐实例段的偏移集合核对——`SEGMENT_OFFSET_MISSING`(fatal)、
  `DUPLICATE_SEGMENT_OFFSET` / `DUPLICATE_ACK_OFFSET` / `ORPHAN_RETRANSMIT` /
  `ACK_WITHOUT_SEGMENT`（`--device-capture` 下 fatal，默认 warn + 取消洁净资格）。
  合法形状保留：重传不产生新唯一段与新 ACK 样本；多段共用一个 ACK 不报错；
  新实例 resume 返回、本实例未发送的前缀（`ack_early`）不被制造成样本，也不
  被当成普通缺失段。
- **P34-P04**：`parse_log()` 不再用 `summary is not None` 短路；顶层非对象/null
  摘要报 `BAD_JSON`(fatal) 并把该块按"非合法收口"记录（严格模式下再报
  `SUMMARY_MISSING` fatal），样本仍归属该块、不被静默清空；完全无观测输入报
  `NO_OBSERVATIONS`(fatal)。**零观测在两种模式下都是致命**：默认模式可以容忍
  未收口/多实例这类形状问题，但"没测到东西"不是口径松紧问题，而是被测量对象
  缺失，任何模式都不得让只看退出码的调用方把空捕获判绿（实测见 §3）。
- **P34-P05**：新增声明式类型/范围表 `FIELD_TYPE_INVALID`(fatal)，全部比较路径
  先做类型判定，杜绝 traceback；`strictFieldsComplete` 改为"必需字段（计数键 +
  绑定身份键）无缺失且 runs>0"；新增阶段分位数重算（gatt/discover/platform）与
  `getInfo.totalUs` 重算 `PHASE_TOTAL_MISMATCH`(fatal)；成功传输
  `elapsedUs<=0` 报 `ELAPSED_NOT_POSITIVE`(fatal)，但**不**禁止单次操作零微秒
  耗时（`gatt_write us=0` 合法）；`bool` 不当作整数；缺字段只降 `strictFieldsComplete`
  而不阻止诊断合并（供旧版本兼容），但不得据此声称契约完整。
- **P34-P06**：`ack_early_invalid` 不参与实例单调时钟，但必须关联到**同段内
  未被消费**的同 `off`、同 `us` 的 `ack_early`；关联失败报
  `EARLY_ACK_UNLINKED`(fatal)。真实时钟回退（`CLOCK_NONMONOTONIC`）、
  多实例污染（`MULTI_INSTANCE`）、无关联旧时间重放三类负例全部保留。
- **P34-P07**：鉴别力配对改为显式变异表，每个变异声明"变异点 + 类型保持方式"，
  运行期先验证变异后目标函数仍满足返回类型契约（`_clock_segments` 返回 list、
  `parse_sample` 返回 `Sample|None`），再要求负例抛出**恰为 `AssertionError`**
  的异常，并记录"变异点 / 期望检出码 / 实际异常类型 / 恢复后再跑结果"。

### 0.5 第二批（复审）五类阻断问题与整改前实测复现值

第一批交付后由非实现会话复审，仍不放行，登记 5 类问题（逐字复现值取自
`docs/ota-exec-notes/P3-4-parser-rereview-2026-09-17.md` §Findings）：

| 发现 ID | 复审原始描述 | 整改前实测复现值 | 定位 |
| --- | --- | --- | --- |
| **P34-PR2-01** 资格门禁错误放行 | 附带侧车后，空捕获、解析失败或仅 partial 的数据仍显示 `eligibleForThreshold=true`，即使 runs/ACK 均为 0 | 空捕获 + 合法侧车：`runs=0`/`ackLatency.count=0`，但 `eligibleForThreshold=true`、`ineligibleReasons` 为空 | `link_stats.py:1423`（门槛资格判据） |
| **P34-PR2-02** 空身份被视为齐备 | 包 SHA、提交、采集方式等为空字符串，参数为 0，仍可获得门槛资格 | 侧车身份字段全填 `""`/`0`：13 项字段"类型合法且存在"，`_kind_ok` 全过，门槛资格成立 | `link_stats.py:1208`（身份校验） |
| **P34-PR2-03** 同一日志可重复计数 | 同一路径传入两次，runs 从 1 变 2、ACK 从 8 变 16；不同目录的同名日志还会丢失来源区分 | `--log X --log X`：`runs=2`、ACK 样本 8→16（同一份捕获被当成两轮）；两份不同目录同名日志的 `sourceId` 均为 `tests.log`，无法指回唯一捕获 | `link_stats.py:1463`（输入装载） |
| **P34-PR2-04** 字段和数值校验仍不完整 | 删除 `elapsedUs` 后零传输时长可绕过检查；负偏移、零段长度、负阶段时间也均零发现通过 | 删 `transfer.elapsedUs`：零致命（`_check_transfer_timing` 只在三键齐备时判定）；`off=-128`：零致命；`len=0`：零致命；`phases.bind[0]=-1`：零致命 | `link_stats.py:1006`（样本取值域/时序核对） |
| **P34-PR2-05** 新证据缺少行尾保护 | 按当前 Git 检出规则，侧车由 719 变为 743 字节，清单和日志的 SHA 也变化；`git add -f` 不能解决此问题 | 该目录在 `core.autocrlf=true` 下未钉 `-text`：LF 文件检出变 CRLF、混合 EOL 文件多出字节，已记录哈希与新检出字节不符 | `.gitattributes`（证据目录行尾属性） |

### 0.6 第二批修复设计

- **P34-PR2-01**：门槛资格不再只看身份。`_qualification_reasons()` 的判据改为
  **四者同时成立**才返回空理由清单：①身份已声明且无冲突/不符；②身份绑定类致命项
  为空（`IDENTITY_BLOCKING_CODES`）；③有可归属的洁净轮（`runs>0`，否则
  `NO_ELIGIBLE_RUNS`）且有确认样本（`ackLatency.count>0`，否则 `NO_ACK_SAMPLES`）；
  ④**本轮全部检出**中无致命项（`aggregate(..., capture_findings=...)` 把整轮
  fatal 透传给资格判定，逐条记 `FATAL:<CODE>`）。理由逐条列出而非折叠成布尔，
  便于调用方直接定位是哪一项不成立；`runs=0` 时合并统计里没有一条样本可供比较，
  `eligibleForThreshold=true` 属伪结论，必须为假。
- **P34-PR2-02**：新增身份**语义域**表 `GROUP_IDENTITY_DOMAINS`（与
  `GROUP_IDENTITY_FIELDS` 一一对应，模块级 `AssertionError` fail-closed），
  类型合法不再等于"已声明"：`text` 域要求非空、非纯空白且不是
  `IDENTITY_PLACEHOLDERS`（unknown/none/null/n/a/na/tbd/?）占位符；`positive`
  域要求正整数（baud/timeoutMs/MTU/包长，0 不是可工作配置）；`nonneg` 域允许 0
  （`maxRetries=0` 是明确的"不重试"策略，属合法声明）；`hex64` 域要求 64 位
  十六进制包 SHA-256。违反者报 `GROUP_IDENTITY_INVALID`(fatal) 并取回 `None`
  身份 → 同时失去门槛资格。
- **P34-PR2-03**：`main()` 装载输入时按**内容摘要**去重：同一 sha256 的第二次
  及以后引用只登记元数据、不再解析，`duplicateOf` 指向首个 `sourceId`，并报
  `DUPLICATE_INPUT`(fatal)；`sourceId` 改为 `'%s#%s' % (basename, sha256[:12])`，
  不同目录下的同名日志因此各自可追溯；侧车绑定与身份校验只消费去重后的
  `unique_meta`。`--json` 新增顶层 `inputs[]`（path/name/sourceId/sha256/bytes/
  duplicateOf），合并统计的 `runs` 与样本数不再被重复引用成倍放大。
- **P34-PR2-04**：三处补齐数值域与完备性：①`_check_transfer_timing()` 先判三键
  是否存在，任一缺失即 `TIMING_INCOMPLETE`(fatal) 并返回——`startUs/endAckUs/
  elapsedUs` 自 schema 1 起由 `toJson` 恒定输出，删呈现字段不得绕过时长核对；
  ②`_sample_off()` 对 `off<0` 报 `SEGMENT_OFFSET_INVALID`(fatal)、对
  `segment_first_send` 的 `len<=0` 报 `SEGMENT_LENGTH_INVALID`(fatal)
  （`len` 仅该 kind 必需，`segment_retransmit` 只核对 `off`）；
  ③`phases.<name>` 列表中的负值报 `PHASE_NEGATIVE`(fatal)——阶段是块内相对时间，
  不可能为负。三者的检出码都在 `--json` 中结构化输出，且使门槛资格为假。
- **P34-PR2-05**：`.gitattributes` 追加证据包整目录 `-text`
  （`/docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17/** -text`）与两个
  单文件条目，按仓库既有 "只增不改" 维护规则新增，不动任何既有行、不改动任何
  文件的当前字节，只让 blob 与新检出字节跟工作树逐字节相同（审计见 §5）。

### 0.7 第三批（准入复核）两项缺陷与整改前实测复现值

第二批交付后由非实现会话做准入复核，结论为**不放行**：PR2-01/03/05 可关闭，
PR2-02/04 尚需补修，另登记 2 项新缺陷。逐字复现值取自该轮复核报告
`.cache/p3-4-parser-review-pr2-followup-20260917/review.md`（只读输入）：

| 发现 ID | 复核原始描述 | 整改前实测复现值 | 定位（整改前） |
| --- | --- | --- | --- |
| **P34-PR3-01** 样本数值域仍漏检 | 非末条 durable 的负值/缺失/非整数偏移，重传段零/负长度，以及 GATT 负字节数，共 **6 个反例仍返回零发现、`eligibleForThreshold=true`** | 6 个反例逐个注入后 `findings=[]`、`eligibleForThreshold=true`、退出码 0 | `link_stats.py:736`（复核点名的行号，位于 `_sum_bytes()` 的累加初始化处，即三处成因之③所在的函数）；另两处见下段 |
| **P34-PR3-02** 包 SHA 格式校验可绕过 | 64 位十六进制后追加 `\n`，实际 **65 字符**仍获门槛资格；原因是正则 `$` 可匹配末尾换行之前 | `packageSha256='A'*64+'\n'`：`GROUP_IDENTITY_INVALID` 未触发、门槛可用为真 | `link_stats.py:599`（`_HEX64_RE` 用 `$` 而非 `\Z`） |

**PR3-01 的成因（不是"少写一条判据"，而是校验范围不完整）**：①`_observed_counts`
只在循环结束后用**末条** durable 的 `off` 作为 `durableFinalOff`，中间样本的
`off` 从不取值域核对——删掉或改坏非末条 `off` 不会改变末值，于是零发现；
②`_sample_off(sample, findings)` 的 `len` 校验分支只被 `segment_first_send`
调用方使用，重传样本走同一函数却未要求长度，`len=0/-1` 直接进入
`retransmitFrames`/`segmentSendTotal` 计数池；③字节计数累加只把"缺失/非整数"
当畸形，负值被静默累加，使 `gattWriteBytes`/`platformWriteBytes` 的相等判定
失去意义。

**PR3-02 的成因**：Python 正则的 `$`（无 `re.MULTILINE`）在字符串末尾**或末尾
换行之前**成立，因此 `^[0-9a-fA-F]{64}$` 接受了 65 个字符（64 位十六进制 + LF）。
`_int`/`_TOKEN_RE` 同样使用 `$`，但它们的输入来自逐行切分后的 token（不含换行），
外部不可达；`packageSha256` 来自 JSON 侧车，**是唯一外部可达的路径**——这也是
本批只补 `\A…\Z` 全串锚定而不改其它正则行为的原因。

### 0.8 第三批修复设计

- **P34-PR3-01（三处收口）**：①`_observed_counts` 改为**逐条** durable 调用
  `_sample_off()`，任一条缺 `off`/非整数/为负即 `durable_usable=False`
  （并抑制由"末值不可信"派生的误导性 `COUNT_MISMATCH`），末值 `durableFinalOff`
  只在整串合法时给出——"合法末条"不再能把非法中间样本洗白；②`_sample_off`
  新增 `require_len` 形参，`segment_first_send` **与** `segment_retransmit`
  两个调用方都传 `True`（发射端两类样本都携带 `len`，见 `ota_link_stats.dart`
  的 `toJson`），`len` 缺失报 `SEGMENT_OFFSET_MISSING`、`len<=0` 报
  `SEGMENT_LENGTH_INVALID`；③`_sum_bytes()` 增加 `bytes<0` →
  `BYTE_COUNT_INVALID`(fatal)，GATT 与 platform **两个调用方共用同一函数**，
  域校验不偏袒任何一侧。合法形状原样保留：durable 的 `off=0`（resume 起点）、
  正长度重传、两类写入的非负字节和、多段共用确认、合法早到 ACK。
- **P34-PR3-02**：三个词法正则（`_TOKEN_RE`/`_INT_RE`/`_HEX64_RE`）改用
  `\A…\Z` **全串锚定**，`packageSha256` 必须是恰好 64 位十六进制；不新增字段、
  不放宽取值、不改黄金输出。合法对照原样保留：大写摘要合法、`maxRetries=0`
  仍是合法声明（`nonneg` 域，本批未动）。
- 两处修复都只改"校验范围"，不改任何合法输入的判定结果：§3.3 中既有 15 条 CLI
  用例的输出在整改后**逐字节未变**（§5.2 对照）。

### 0.9 明确不做的事

- 不修改冻结行格式、冻结契约文档、profile 定义、workflow、历史冻结包；
- 不修改发射端 `ota_link_stats.dart`（两批都只读其语义做交叉核对，**没有**为了
  迁就解析器改发射端）；
- 不重跑主工作树 `.cache/p3-4-parser-review-20260917/` 的旧 runner，不覆盖其任何
  文件；不触碰复审会话的 `.cache/p3-4-parser-rereview-20260917/` 与
  `docs/ota-exec-notes/P3-4-parser-rereview-2026-09-17.md`；
- 不新增真机采集（无设备操作、无 AT、无 J-Link、无烧录、无安装、无发布）；
- 不启动 APK/EXE/固件构建，不触发任何 workflow，不改 CI 定时重跑。

---

## 1. 改动文件与依赖范围（实测）

### 1.1 改动清单

| 路径 | 状态 | 字节 | SHA-256 |
| --- | --- | --- | --- |
| `Tools/ota/p3-4-link-stats/link_stats.py` | 已修改（未提交） | 84,728 | `0cf95913612c688c6414b2becddcacffebc5b5aa92641eb989a299737b6b82c7` |
| `Tools/ota/p3-4-link-stats/selftest.py` | 已修改（未提交） | 164,081 | `fb1ec6f23644189a1ce17a512d47cd5d70bdbd20c261b767be7075637832b3dc` |
| `.gitattributes` | 已修改（未提交，+10 行；第三批**未再新增**条目） | 15,217 | `d1d982d9df418f9e9c37ccbefa1f6edd8abda055310e5225742fd01c0716eff6` |
| `docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17.md` | 新增（未跟踪） | 本文件 | 不记录自身哈希（自指），由交付说明给出 |
| `docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17/` | 新增证据目录（未跟踪） | 35 件（清单 34 条 + 清单自身） | 逐件哈希见 §3.4 |

`git diff --numstat` 实测：`.gitattributes` 10/0、`link_stats.py` 1230/162、
`selftest.py` 2509/233；合计 **3749 插入 / 395 删除**（相对基线 `0441f78`，
三批累计）。第三批没有再新增任何 `.gitattributes` 条目——第二批量身定做的
整目录 `-text` 已覆盖第三批新增的全部文件（见 §5.1 审计）。

### 1.2 `.gitattributes` 行尾保护（本批新增，含一条需主会话裁决的条目）

新增 10 行，全部为追加，未改动任何既有行：

```text
+/docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17/** -text
+/docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17.md -text
+/docs/ota-exec-notes/P3-4-parser-rereview-2026-09-17.md -text
```

（前三行为属性行，另 7 行为解释该约定的中文注释，含"与上面
`/docs/acceptance-contracts/**` 同一约定""不改动任何文件的当前字节"两条。）

其中 **`P3-4-parser-rereview-2026-09-17.md` 一行属复审会话的文件**，本批一并
钉住是因为它连同本记录构成"复审 → 整改"的成对证据，且同为字节绑定的新文本
文件；**若主会话认为不应为他人产物设置属性，可直接删除该单行**——删除它不影响
本批任何已记录哈希（本批证据目录与本文档的两条属性保持不变即可）。

### 1.3 明确未改动的被验/冻结资产与只读复核资产

- `Tools/ota/p3-4-link-stats/fixtures/round6-ubuntu-head.log`：
  `d482f9ed386a064146992585fdf93ab2738f1b785c2bdc2e910e0d81c37bf645`，41,982 B，
  274 行，`git status` 无改动（真实切片的字节不因新解析行为变化）；
- `Tools/ota/p3-4-link-stats/fixtures/PROVENANCE.md`：无改动；
- `.gitattributes` 第 84–87 行既有 4 条 `-text` 条目：无改动；
- 复审报告 `docs/ota-exec-notes/P3-4-parser-rereview-2026-09-17.md`：
  `09725ff3978eda243c74c0c8671f3025c108337bbef19dfcd8d73b3b3263b244`（13,621 B），
  只读引用，未改字节。
- 准入复核资产 `.cache/p3-4-parser-review-pr2-followup-20260917/`（复核会话所有，
  **只读**）：`review.md` 10,889 B /
  `7f13a9299aefcc8f49adedafe1e80a005941fdd3ae6b4e595127ce426e374397`、
  `review.py` 27,207 B /
  `d25af1e0c2b8fd59f8529ba0ffea36afc04596d09bdc7df525060a6276e39b1e`、
  `final-audit.json` 2,916 B /
  `6c2126d952064edd2806fe5b3aee565c21a31d0e438b80f329d1d87e37b6836c`、
  `numeric-neighbors.json` 38,268 B /
  `39b30e9787d34b796504386fa48dba8c4750f598c9ce81f78f840dff44904399`、
  `identity-neighbors.json` 30,575 B /
  `b9706fd0bb399cdaa8aaf77edfb77ba2d3ad9c9037520c63b69e2ba13252b424`。
  本会话只读引用（用于逐条复现 6 个反例），未在其目录内新建、覆盖或删除任何文件，
  也未重跑其 `review.py`（其输出路径为独占名，重跑会覆盖复核结论）。

### 1.4 边界

依赖面只有 `link_stats.py`、`selftest.py` 两个 Python 文件与一条属性新增；未改
Flutter/MCU 产品实现、线协议、冻结契约、`Tools/provenance/manifest_profiles.json`、
workflow、历史冻结包与发射端 `ota_link_stats.dart`。`docs/ota-exec-notes/` 不属于
任何 profile，本目录产物不改变 Validation 组的失效判定。

---

## 2. 整改矩阵

**第一批（P34-P01..P34-P07）**

| 发现 ID | 原因（证据） | 修复 | 正例 | 负例 | 鉴别力证据 | 尚未覆盖 |
| --- | --- | --- | --- | --- | --- | --- |
| **P34-P01** 参数混组 | `aggregate()` 只按 `label` 归并，`devices` 只收集不分组 | 新增侧车 `--group`（13 项身份 + `inputs[]` 路径/SHA）；按观测签名拆分输入组；`GROUP_IDENTITY_*` / `INPUT_UNBOUND` / `INPUT_SHA_MISMATCH`；`eligibleForThreshold` 只在身份已声明且一致时为真 | `P01 侧车：身份声明齐备 → 门槛可用`、`P01 身份：拆分后各组保留自身统计`、`P01 身份：单签名结论须带观测身份`（10 条 P01 用例） | `P01 侧车：身份与观测不符/日志未绑定/SHA 不符/字段不全 → 致命`、`P01 身份：未声明身份不得标为门槛可用` | **变异对 `_qualification_reasons`(5)**（PR2 批新增，见下）与 CLI `fixture-identity-ok` 门槛可用=True 对 `fixture-json`=False 对 `identity-sha-bad`/`identity-incomplete`=致命 exit 1 | 侧车路径只在夹具与真实捕获上验证，四份真实捕获均无侧车 |
| **P34-P02** 污染块仍被合并 | `aggregate()` 用 `check_group_only()` 重跑宽松模式，丢掉解析期 fatal 与严格结论 | `check_group()` 结论写回 `group.findings`，`aggregate()` 一律复用；三层 `attributable → clean → threshold`；不合格轮次进 `excluded[]` 保留行号与理由 | `P02 归属：解析期致命项归属所在块`、`P02 洁净：诊断池与洁净池分离`、`P02 真实污染块被排除且留痕`（真实捕获行 307–976） | `P02 洁净：partial 覆盖不得合并`、`P02 洁净：拖尾轮次不得合并`、`P02 留痕：非 ok 终态记入排除而非致命` | **变异对 `_classify`(3 条)**：置为恒 `(True,True)` 后 3 条负例全部以 `AssertionError` 打红、正例 `test_strict_contract_block_has_no_findings` 仍绿 | — |
| **P34-P03** 只按行数核对 | `_observed_counts()` 只有 `len(...)`，无偏移集合 | 逐实例段偏移集合核对：`SEGMENT_OFFSET_MISSING`(fatal)、`DUPLICATE_SEGMENT_OFFSET`/`DUPLICATE_ACK_OFFSET`/`ORPHAN_RETRANSMIT`/`ACK_WITHOUT_SEGMENT`（严格 fatal、默认 warn + 取消洁净资格） | `P03 合法：重传不新增唯一段与 ACK 样本`、`P03 合法：多段共用一个确认`、`P03 合法：resume 前缀不被误报为缺失段` | `P03 偏移：重复确认/首发缺 off/孤儿重传/无段确认`（4 条） | **变异对 `_check_offset_sets`(4 条)**：全部 `AssertionError`，恢复后通过 | — |
| **P34-P04** 空捕获/null 摘要绕过 | `summary is not None` 短路；空文件零检出 | `parse_log()` 顶层非对象/null 摘要报 `BAD_JSON`(fatal) 且不清空样本；完全无观测报 `NO_OBSERVATIONS`(fatal，**两种模式都致命**) | `P04 收口：破损摘要不丢弃样本`、`P04 收口：未收口统计按 label 归属` | `P04 空捕获：空文件/纯噪声不是成功`、`P04 收口：null 摘要/非对象摘要不是合法收口`、`P04 收口：非法收口块不得进入合并`（6 条） | **PR2 批补齐变异对**：`_qualification_reasons`(5) 中的 `test_empty_capture_with_sidecar_is_not_threshold_eligible` 即"删判据即红"证明；CLI `empty-capture` 与 `pr2-empty-capture-sidecar` 均 exit 1 + `FATAL:NO_OBSERVATIONS` | `NO_OBSERVATIONS` 自身的检出函数不在变异表内（其资格后果已配对） |
| **P34-P05** 字段/类型/范围核对不全 | `schema in frozenset`、`value < declared` 直接 `TypeError`；分位数只核 ACK；`strictFieldsComplete` 只看计数键 | 声明式类型/范围表 `FIELD_TYPE_INVALID`(fatal)；阶段分位数重算与 `getInfo.totalUs` 重算 `PHASE_TOTAL_MISMATCH`(fatal)；成功传输 `elapsedUs<=0` 报 `ELAPSED_NOT_POSITIVE`(fatal) 而单次操作零微秒合法；`bool` 不当整数；`strictFieldsComplete` 改含绑定身份键 | `P05 类型：布尔不冒充整数`、`P05 范围：单次操作零微秒合法`、`P05 完整性：字段齐全时为真`、`P05 完整性：旧版缺字段仍可诊断合并` | `P05 范围：成功传输零时长非法且不合并`、`P05 类型：非法类型给结构化结论（无 traceback）`、`P05 重算：阶段分位数/getInfo.totalUs 篡改被检出`、`P05 完整性：缺绑定字段降完整性` | **变异对 19 条**：`_check_counters`(6)、`_check_quantiles`(4)、`_check_structure`(3)、`_check_derived`(3)、`_check_required_present`(2)、`_check_integrity`(1) | — |
| **P34-P06** 合法早到 ACK 被误判 | `_clock_segments()` 把 `ack_early_invalid` 当普通时间戳 | 该 kind 不参与实例单调时钟，但必须关联同段内未被消费的同 `off`/同 `us` 的 `ack_early`，关联失败报 `EARLY_ACK_UNLINKED`(fatal) | `P06 早到 ACK：发射端合法输出序不报时钟回退`、`P06 早到 ACK：仅该 kind 除外于单调时钟` | `P06 早到 ACK：无关联旧时间重放致命`、`偏移不匹配致命`、`跨实例挪用被检出`、`真实时钟回退仍报警`（4 条） | **变异对 `_check_early_links`(3) + `_check_clock`(2) + `_clock_segments`(1)**，全部 `AssertionError` | 形状按发射端 `ota_link_stats.dart` 的**源码语义构造**，不是 Dart 实机执行或设备测量 |
| **P34-P07** 异常被当作鉴别力 | `except Exception` 把运行期异常也算"负例通过"（原 3/25） | 显式变异表：每个变异声明变异点与类型保持方式，先验返回类型契约（`NoneType` / `list` / `Sample\|None` / `tuple2bool`），再要求负例抛出**恰为 `AssertionError`**，并记录"变异点 / 期望检出码 / 实际异常 / 恢复后再跑" | 每个变异对附带正例（共 10 个不同正例名），恢复后正例仍绿 | 64 条负例槽位全部以 `AssertionError` 命中，**运行期异常 0 条**（原 3 条已消除） | 变异表静态审计：每条期望检出码必须出现在该用例源码前 2000 字符内，且条目数被断言锁死（61 条期望条目） | 变异条目 23 个 / 去重目标 22 个 / 负例槽位 64 个；不覆盖 PR2-03 的输入装载路径与 PR3 的词法正则可达性（见 §7） |

**第二批（P34-PR2-01..P34-PR2-05）**

| 发现 ID | 原因（复审原始复现值） | 修复 | 正例 | 负例 | 鉴别力证据 | 尚未覆盖 |
| --- | --- | --- | --- | --- | --- | --- |
| **P34-PR2-01** 资格门禁错误放行 | 门槛资格只看身份声明；`runs=0`/ACK=0 时仍 `eligibleForThreshold=true`、理由清单为空 | `_qualification_reasons()` 四条件 AND：身份声明且无冲突/不符 ∧ 身份绑定类致命项为空 ∧ `runs>0` 且 `ackLatency.count>0`（`NO_ELIGIBLE_RUNS`/`NO_ACK_SAMPLES`）∧ **整轮**无致命项（`aggregate(capture_findings=...)` 逐条记 `FATAL:<CODE>`） | `P01 资格（PR2-01）：本轮有致命项不得放行`、`P01 侧车：身份声明齐备 → 门槛可用`（`fixture-identity-ok` 门槛可用=True，反向证明该门禁不是恒假） | `P01 资格（PR2-01）：空捕获+侧车不得放行`、`仅 partial 不得放行`、`分析失败不得放行`；CLI `pr2-empty-capture-sidecar`：exit 1、`runs=0`、`ackLatency.count=0`、门槛=False、理由 `['NO_ELIGIBLE_RUNS','FATAL:NO_OBSERVATIONS']` | **变异对 `_qualification_reasons`(5)**：`test_empty_capture_with_sidecar_is_not_threshold_eligible`、`test_partial_round_without_clean_run_is_not_threshold_eligible`、`test_fatal_round_elsewhere_still_blocks_threshold_eligibility`、`test_merge_without_declared_identity_is_not_threshold_eligible`、`test_sidecar_identity_mismatch_is_fatal`——判据删除后全部以 `AssertionError` 打红 | "分析失败"分支由 `INTERNAL_ERROR` 兜底路径给出门槛=False，走的是同一资格函数，但无独立变异对 |
| **P34-PR2-02** 空身份被视为齐备 | 身份字段存在 + 类型合法即视为"已声明"，`""`/`0` 全过 | 新增 `GROUP_IDENTITY_DOMAINS` 语义域表（与字段表一一对应，模块级 fail-closed）：text 非空非空白非占位符、positive 正整数、nonneg 允许 0、hex64 64 位十六进制；违反报 `GROUP_IDENTITY_INVALID`(fatal) | `P01 侧车（PR2-02）：零重试是合法声明`（`maxRetries=0` 仍可门槛可用）、`pr2-empty-identity` 的 `runs=2`/ACK=16 证明样本未受影响 | `P01 侧车（PR2-02）：空/空白字段不构成声明`、`占位符不构成声明`、`零参数不构成声明`；CLI `pr2-empty-identity`：exit 1、fatal `GROUP_IDENTITY_INVALID`、门槛=False | **变异对 `_identity_domain_problem`(3)**：`test_sidecar_blank_identity_values_are_not_declared`、`test_sidecar_placeholder_identity_is_not_declared`、`test_sidecar_zero_parameters_are_not_declared`；正例 `test_sidecar_zero_retries_is_a_legal_declaration` | 语义域表本身的"漏字段"由模块级 `AssertionError` 保证，不由变异对保证 |
| **P34-PR2-03** 同一日志可重复计数 | 输入按路径装载、无去重；`sourceId` 只有 basename | 按 sha256 去重（重复只登记不解析）+ `duplicateOf` 指向首个 `sourceId` + `DUPLICATE_INPUT`(fatal)；`sourceId='%s#%s' % (basename, sha[:12])`；`--json` 增顶层 `inputs[]` | `CLI（PR2-03）：同名不同目录保留来源标识`（`pr2-same-basename`：2 条输入同名、sourceId 互异、无 `duplicateOf`）；`CLI：--log 可重复` | `CLI（PR2-03）：重复输入去重且如实报告`（`pr2-duplicate-input`：`runs=2`（非 4）、`inputs[1].duplicateOf == inputs[0].sourceId`、fatal `DUPLICATE_INPUT`、门槛=False） | **无变异对**：该修复在 `main()` 装载层，变异表只覆盖解析/判定函数；等价证明是 §3.3 的两条 CLI 断言（`runs` 不成倍、来源可追溯） | 两条 CLI 用例都只覆盖"重复/同名"两种形态；编码不同的等价文本未纳入（字节不同即视为不同输入，属既定语义） |
| **P34-PR2-04** 字段和数值校验仍不完整 | 删 `elapsedUs`/负偏移/零段长/负阶段时间四类注入在整改前**零发现通过** | ①`_check_transfer_timing()` 三键任一缺失即 `TIMING_INCOMPLETE`(fatal) 并返回；②`_sample_off()` 对 `off<0` 报 `SEGMENT_OFFSET_INVALID`、`segment_first_send` 的 `len<=0` 报 `SEGMENT_LENGTH_INVALID`(fatal)；③`phases` 负值报 `PHASE_NEGATIVE`(fatal) | `P05 时序（PR2-04）：非成功终态允许 null`、`P05 范围：单次操作零微秒合法`、`P03 合法：重传不新增唯一段与 ACK 样本`（不误伤合法形状） | `P05 时序（PR2-04）：缺 elapsedUs 致命`、`缺 startUs/endAckUs 致命`、`成功传输时序为 null 致命`、`负段偏移致命`、`零段长致命`、`负阶段时间致命`（7 条）；CLI `pr2-numeric-tamper`：exit 1，fatal 集合含 `{SEGMENT_OFFSET_INVALID, SEGMENT_LENGTH_INVALID, TIMING_INCOMPLETE, PHASE_NEGATIVE, INTERNAL_INCONSISTENT}`，门槛=False | **变异对 10 条**：`_sample_off`(3)（负偏移 / 零段长 / 缺首发 off）、`_check_transfer_timing`(5)（缺字段 / 类型 / 成功为 null / 零时长 / 篡改）、`_check_quantiles` 中的 2 条（`test_phase_quantile_tamper_is_detected`、`test_getinfo_total_tamper_is_detected`）；第三批把 `_sample_off` 从 3 条扩到 **6 条**（新增重传零长度 / 负长度 / 缺长度） | `PHASE_NEGATIVE` 无独立变异对（`_check_derived` 的 3 对覆盖重传派生量、`PHASE_REVERSED`、bind 阶段时长）；其端到端后果由 `pr2-numeric-tamper` 的 CLI 致命码断言覆盖 |
| **P34-PR2-05** 新证据缺少行尾保护 | 证据目录未钉 `-text`，`core.autocrlf=true` 下新检出字节与工作树不符（侧车 719→743 B，清单与日志 SHA 变化）；`git add -f` 不能解决 | `.gitattributes` 追加整目录 `-text` + 两处单文件 `-text`（只增不改），目录内全部文件新检出字节 == 工作树字节 | §5.1 审计：第二批 30 个目标、第三批扩到 **39 个目标**（证据目录 35 件 + `link_stats.py` + `selftest.py` + `.gitattributes` + 本文档），两轮 `新检出字节 != 工作树字节` 的文件数均为 **0**，目标属性均为 `text: unset` | 反证：审计脚本对"未钉 `-text` 且含 CRLF"的构造目标会报 `unstable`（脚本保留该分支，本轮目标集内无命中即通过） | 审计脚本用隔离 `GIT_INDEX_FILE`/`GIT_OBJECT_DIRECTORY`/`GIT_ALTERNATE_OBJECT_DIRECTORIES` 跑真实 clean/smudge 过滤器后逐字节比对，不依赖 `git check-attr` 的声明 | 该属性只保护本证据目录与两份记录；仓库其他未钉 `-text` 的新增文本文件不在本批范围 |

**第三批（P34-PR3-01、P34-PR3-02）**

| 发现 ID | 原因（复核原始复现值） | 修复 | 正例 | 负例 | 鉴别力证据 | 尚未覆盖 |
| --- | --- | --- | --- | --- | --- | --- |
| **P34-PR3-01** 样本数值域仍漏检 | ①`_observed_counts` 只用**末条** durable 的 `off` 作为 `durableFinalOff`，中间样本从不取值域；②`_sample_off` 的 `len` 分支只被 `segment_first_send` 传入，重传样本免检；③`_sum_bytes` 只报"缺失/非整数"，负值被静默累加 → 6 个反例零发现且 `eligibleForThreshold=true` | ①durable **逐条**过 `_sample_off()`，任一条非法即 `durable_usable=False` 且末值置空（并抑制由不可信末值派生的误导性 `COUNT_MISMATCH`）；②`_sample_off(..., require_len=True)` 同时用于首发与重传（`len` 缺失 → `SEGMENT_OFFSET_MISSING`，`len<=0` → `SEGMENT_LENGTH_INVALID`）；③`_sum_bytes` 对 `bytes<0` 报 `BYTE_COUNT_INVALID`(fatal)，GATT 与 platform 同一函数 | `P05 正例（PR3-01）：合法重传保持洁净与门槛资格`、`durable 零偏移是合法 resume 起点`、`两类写入的合法字节和被正确累加`；探针同时给出 `重传 len=128（对照）`、`platform bytes=100（对照）` 与基线块本身三个零致命对照 | 逐条注入的 6 个反例各命中**恰好一个**码（探针 §逐步打印），合并进一份日志后 CLI `pr3-numeric-tamper`：exit 1、fatal 集合**恰等于** `{SEGMENT_OFFSET_INVALID, SEGMENT_OFFSET_MISSING, SEGMENT_LENGTH_INVALID, BYTE_COUNT_INVALID}`、8 处反例逐条点名、`runs=0`、门槛 False | 变异对新增 `_observed_counts`(3)（负/缺/非整数非末条偏移）、`_sample_off`(+3 重传槽位，共 6)、`_sum_bytes`(2)（GATT 与 platform 各一），全部 `AssertionError` 命中且恢复后正例仍绿 | ①非法 `off` 的文本形态（`off=bad`、`off=1.5`）统一归到"缺偏移"同一码，无独立检出码；②`platform_write` 负值与 GATT 负值共用 `BYTE_COUNT_INVALID`，不按写入方分码（调用方信息在 `detail` 中） |
| **P34-PR3-02** 包 SHA 格式校验可绕过 | `_HEX64_RE` 用 `^…$` 锚定，而 Python 的 `$`（无 `re.MULTILINE`）在末尾换行之前也成立 → `'A'*64 + '\n'`（解码后 **65 字符**）仍被当作合法包 SHA，取得门槛资格 | 三个词法正则（`_TOKEN_RE`/`_INT_RE`/`_HEX64_RE`）改用 `\A…\Z` **全串锚定**；`packageSha256` 必须是恰好 64 位十六进制。不改字段、不放宽取值、不改任何黄金输出 | `P01 正例（PR3-02）：合法大写摘要 + 零重试仍构成声明`；CLI `pr3-package-sha-uppercase-ok`：exit 0、无致命、`runs=2`、门槛 **True**、`declared.packageSha256 == 'ABCDEF0123456789'*4`、`declared.maxRetries == 0`（大写合法与零重试合法的双向对照） | `P01 侧车（PR3-02）：包 SHA 尾随换行不构成声明`、`P05 范围（PR3-02）：词法正则必须整串锚定`；CLI `pr3-package-sha-trailing-lf`：exit 1、fatal 集合**恰为** `{GROUP_IDENTITY_INVALID}`、`detail` 点名 `packageSha256` 并如实报"65"字符、`identity.declared=None`、门槛 False；探针另给 `A*64+'\r\n'` 与 `G*64`（非十六进制）两个反例 | 变异对 `_HEX64_RE`(2)（`test_sidecar_package_sha_trailing_newline_is_not_declared`、`test_lexical_regexes_reject_trailing_newline`）与 `_INT_RE`(1)；两者都把锚定改回 `$` 后以 `AssertionError` 打红，恢复后正例仍绿 | `_TOKEN_RE` 的 `$`→`\Z` 改动**没有**配套变异对与断言：其值类 `[^=]*` 会吸收行内换行字符，而它的输入来自逐行切分（token 内不可能含换行），外部不可达；强行设对会得到"改回 `$` 仍然通过"的零鉴别力条目，故按 §7 第 2 条如实标注为未覆盖 |

---

## 3. 实测命令、退出码与产物

工作目录一律为 `D:\github\my\E-Track\.cache\worktrees\p3-4-link-stats`。

### 3.1 开发自测（主证据）

```text
python -X utf8 -S -B Tools/ota/p3-4-link-stats/selftest.py
```

- 退出码：`0`（stderr 0 字节）
- 计数：**PASS 124 / FAIL 0 / SKIP 0 / ERROR 0**（整改前 92 项；第一批后 110 项；
  第三批新增 14 项）
- 原始输出：`docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17/selftest-full-2026-09-17.log`
  （28,460 B，SHA-256 `0454b47f4f0054462a78723a7351432057913c1b90f5fe14543eee0764d63b43`，
  末行 `EXIT=0`，共 254 行；末行前为 `---- selftest 总计 124 项，失败 0 项 ----`）
- 新增（PR2 相关）用例：

  | 编号 | 用例 | 覆盖 |
  | --- | --- | --- |
  | 15–18 | `P01 侧车（PR2-02）：空/空白字段、占位符、零参数不构成声明`、`零重试是合法声明` | PR2-02 |
  | 20–23 | `P01 资格（PR2-01）：空捕获+侧车、本轮有致命项、仅 partial、分析失败均不得放行` | PR2-01 |
  | 52–59 | `P05 时序（PR2-04）：缺 elapsedUs/缺 startUs/endAckUs/成功传输为 null 致命`、`非成功终态允许 null`、`负段偏移/零段长/负阶段时间致命`、`非整数阶段边界给结构化结论` | PR2-04 |
  | 103–104 | `CLI（PR2-03）：重复输入去重且如实报告`、`同名不同目录保留来源标识` | PR2-03 |
  | 107 | `鉴别力：保持类型的变异下负例必须失败（P34-P07）` | 鉴别力总数由 38 升至 53 |

- 第三批新增（PR3 相关）用例：

  | 编号 | 用例 | 覆盖 |
  | --- | --- | --- |
  | 19 | `P01 侧车（PR3-02）：包 SHA 尾随换行不构成声明` | PR3-02 反例 |
  | 20 | `P01 正例（PR3-02）：合法大写摘要 + 零重试仍构成声明` | PR3-02 正例（大写合法 + `maxRetries=0` 合法） |
  | 21 | `P05 范围（PR3-02）：词法正则必须整串锚定` | PR3-02 词法层（`\A…\Z` 对 `_int`/`_HEX64_RE` 的行为，并保留合法取值不被误杀） |
  | 63–65 | `P05 范围（PR3-01）：非末条 durable 负偏移/缺偏移/偏移非整数致命` | PR3-01 ① |
  | 66–68 | `P05 范围（PR3-01）：重传零长度/负长度/缺长度致命` | PR3-01 ② |
  | 69–70 | `P05 范围（PR3-01）：GATT 负字节数致命`、`platform 负字节数致命` | PR3-01 ③（两个调用方各一条） |
  | 71–73 | `P05 正例（PR3-01）：合法重传保持洁净与门槛资格`、`durable 零偏移是合法 resume 起点`、`两类写入的合法字节和被正确累加` | PR3-01 的"不误伤合法形状"三条对照 |

  用例 21 在整改中曾出现过一次**我自己的期望写错**（把 `_TOKEN_RE` 也当作必须
  拒绝换行的正则），红在 `selftest.py:926`；实测确认其值类 `[^=]*` 会吸收换行、
  而输入来自逐行切分、外部不可达后，删除该断言与对应变异对并保留合法对照——
  §7 第 2 条如实登记这一未覆盖面，不通过改断言凑绿。

- 追溯说明：整改前的 92 项归档（20,860 B / 21,317 B 两版）与第二轮的 110 项
  归档（25,457 B）已从证据目录移出到工作树内 `.cache/p34-dev/superseded/`
  （gitignored），只作为旧→新对照材料，**不是**本轮结论依据；本轮结论只引用
  上表 28,460 B 的归档。

### 3.2 鉴别力配对（P34-P07）

从 `selftest.py` 的 `DISCRIMINATION` 变异表静态计数：**23 个变异条目 / 22 个去重
目标 / 64 条负例槽位 / 61 条期望条目 / 10 个不同正例**，运行期异常 **0** 条
（原 3 条已消除）。槽位按目标归并：

| 目标函数 | 负例槽位 |
| --- | --- |
| `_check_counters` | 6 |
| `_sample_off`（第二批 3 + 第三批 3） | 6 |
| `_check_transfer_timing` | 5 |
| `_qualification_reasons` | 5 |
| `_check_offset_sets` | 4 |
| `_check_quantiles` | 4 |
| `_check_derived` | 3 |
| `_check_early_links` | 3 |
| `_check_structure` | 3 |
| `_classify` | 3 |
| `_identity_domain_problem` | 3 |
| `_observed_counts`（第三批新增） | 3 |
| `_HEX64_RE`（第三批新增） | 2 |
| `_check_clock` | 2 |
| `_check_labels` | 2 |
| `_check_required_present` | 2 |
| `_sum_bytes`（第三批新增） | 2 |
| `parse_sample` | 2 |
| `_INT_RE`（第三批新增） | 1 |
| `_check_attempts` | 1 |
| `_check_integrity` | 1 |
| `_clock_segments` | 1 |
| **合计** | **64** |

判定规则（`test_negative_cases_discriminate_on_check_removal`）：先验证变异后目标
函数仍满足返回类型契约（`NoneType` / `list` / `Sample|None` / 返回二元组），再要求
负例抛出**恰为 `AssertionError`**；运行期其它异常记为失败并打印类型。变异表条目数
被 `assert len(declared) == 61` 锁死（每条都要有对应期望检出码文本，且必须出现在
该用例源码前 2000 字符内），第三批为 5 个目标的新增槽位新增 9 条期望条目，并
改写 1 条既有期望文本（`test_lexical_regexes_reject_trailing_newline`）。
日志第 185 行给出本轮结论，逐条"变异点 / 期望检出码 / 实际异常 / 恢复后再跑"在
用例内逐项打印（`恢复=通过`）。第三批新增 **11 个槽位 / 5 个目标**（`_sample_off`
+3、`_observed_counts` +3、`_sum_bytes` +2、`_HEX64_RE` +2、`_INT_RE` +1，
53 → 64），对应日志第 174–184 行的期望检出码依次为 `SEGMENT_OFFSET_INVALID`×1、
`SEGMENT_OFFSET_MISSING`×3、`SEGMENT_LENGTH_INVALID`×2、`BYTE_COUNT_INVALID`×2、
`GROUP_IDENTITY_INVALID`×3（合计 11）。每条负例都配了**必须仍然通过的正例**，
例如 `_observed_counts` → `test_durable_zero_offsets_are_legal_resume_marks`、
`_sample_off` → `test_legal_retransmit_keeps_block_clean`、
`_sum_bytes` → `test_legal_write_byte_sums_over_both_writers_are_accepted`、
`_HEX64_RE` → `test_sidecar_uppercase_package_sha_and_zero_retries_are_legal`，
即"把合法形状连同畸形一起打死"会被正例当场判红。

### 3.3 CLI 证据矩阵（18 条，全部实测）

| 用例 | 退出码 | runs | ACK 样本 | 唯一段 | P99 | 门槛可用 | 关键结论 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `fixture-json` | 0 | 2 | 16 | 16 | 580 | False | warn `FIELD_ABSENT`；理由 `GROUP_IDENTITY_NOT_DECLARED` |
| `fixture-identity-ok` | 0 | 2 | 16 | 16 | 580 | **True** | 理由清单为空（门禁的正例，证明其非恒假） |
| `identity-sha-bad` | 1 | 2 | 16 | 16 | 580 | False | fatal `INPUT_SHA_MISMATCH` + `INPUT_UNBOUND` |
| `identity-incomplete` | 1 | 2 | 16 | 16 | 580 | False | fatal `GROUP_IDENTITY_INCOMPLETE` |
| `empty-capture`（0 B） | 1 | 0 | 0 | 0 | null | False | fatal `NO_OBSERVATIONS` |
| `missing-file` | 2 | — | — | — | — | — | stderr `读取失败: [Errno 2]` |
| `real-win-polluted` | 0 | 6 | 48 | 48 | 1328 | False | warn `DUPLICATE_SEGMENT_OFFSET`/`DUPLICATE_ACK_OFFSET`/`MULTI_INSTANCE`/`STRAGGLER`/`FIELD_ABSENT` |
| `real-ubuntu-loose` | 0 | 6 | 48 | 48 | 1184 | False | warn `SUMMARY_MISSING` + `STRAGGLER` |
| `real-ubuntu-strict` | 1 | 6 | 48 | 48 | 1184 | False | **fatal `SUMMARY_MISSING`** |
| `fixture-plain` | 0 | — | — | — | — | — | 人读输出（字节与整改前一致） |
| `pr2-empty-capture-sidecar` | 1 | 0 | 0 | 0 | null | False | 空捕获 + **合法侧车**：理由 `['NO_ELIGIBLE_RUNS','FATAL:NO_OBSERVATIONS']`（PR2-01 反例） |
| `pr2-empty-identity` | 1 | 2 | 16 | 16 | 580 | False | 身份全空/零：fatal `GROUP_IDENTITY_INVALID`（PR2-02 反例），样本数不受影响 |
| `pr2-duplicate-input` | 1 | 2 | 16 | 16 | 580 | False | 同一文件传两次：`inputs[1].duplicateOf == inputs[0].sourceId`，fatal `DUPLICATE_INPUT`（PR2-03 反例） |
| `pr2-same-basename` | 0 | 0 | 0 | 0 | null | False | 两份不同目录的同名捕获：2 条输入同名、sourceId 互异、无 `duplicateOf`；两捕获签名不同 → `GROUP_IDENTITY_CONFLICT` 拆组、不产出跨组混合统计 |
| `pr2-numeric-tamper` | 1 | 0 | 0 | 0 | null | False | 四类注入全检出：fatal `{SEGMENT_OFFSET_INVALID, SEGMENT_LENGTH_INVALID, PHASE_NEGATIVE, TIMING_INCOMPLETE, INTERNAL_INCONSISTENT}`（PR2-04 反例） |
| `pr3-numeric-tamper` | 1 | 0 | 0 | 0 | null | False | **PR3-01 反例**：fatal 集合**恰等于** `{SEGMENT_OFFSET_INVALID, SEGMENT_OFFSET_MISSING, SEGMENT_LENGTH_INVALID, BYTE_COUNT_INVALID}`，8 处反例逐条点名（3 durable + 3 重传 + 2 字节计数），行号为 185/218/181/234/268/265/266/267 |
| `pr3-package-sha-trailing-lf` | 1 | 2 | 16 | 16 | 580 | False | **PR3-02 反例**：64 位十六进制 + LF（解码 65 字符）→ 恰 1 条 fatal `GROUP_IDENTITY_INVALID`，`detail` 点名 `packageSha256` 并如实报 65；`identity.declared=None`；样本数仍为 2/16（身份非法不清空观测） |
| `pr3-package-sha-uppercase-ok` | 0 | 2 | 16 | 16 | 580 | **True** | **PR3-02 正例**：合法大写摘要 + `maxRetries=0`；无致命、理由清单为空、`declared.packageSha256 == 'ABCDEF0123456789'*4`、`declared.maxRetries == 0` |

命令原文与逐条退出码冻结在 `cli-index.txt`（每行 `<exit> <name> :: <完整命令>`，
18 行），对应输出为 `cli-<name>.out`。退出码序列：
`0/0/1/1/1/2/0/0/1/0/1/1/1/0/1/1/1/0`。

复现校验：矩阵运行时逐条重跑并与已存 `.out` 做**逐字节**比对，命中差异的用例
打印 `重生成(旧=<sha16>)` 后据实重写（PR2 批次使 8 条 JSON 用例的结论必然变化，
旧字节由 `.cache/p34-dev/old-manifest.txt` 保留，对照见 §5.2），并断言
`cli-index.txt` 既有行**逐字节未变**后才追加新命令。第三批实测：**前 15 条用例
的 `.out` 全部报 `字节一致`**（无一条重生成），`cli-index.txt` 既有 15 行逐字节
未变、仅追加 3 行 —— 即两处修复没有为了放行畸形输入而改变任何既有结论。生成器
与反例输入一并入库：`build_pr2_inputs.py`、`build_pr3_inputs.py`（均为确定性、
`'xb'` 写、拒绝覆盖内容不同的既有文件，重复运行打印"已存在且字节一致"），
逐条反例探针为 `probe_pr3_counterexamples.py`（stdout 固化为
`pr3-counterexample-probe.txt`）。

### 3.4 证据目录清单（35 件，逐件按工作树字节）

目录：`docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17/`

| 文件 | 字节 | SHA-256 |
| --- | --- | --- |
| `build_pr2_inputs.py` | 6,738 | `c23010f7405d4660f2a3a06e64a84f6939332a870f22742af2344501718290f6` |
| `build_pr3_inputs.py` | 6,116 | `827b9f56be678cd89473a47012a651e8d66abbd152111ca2b3eac68e2f672036` |
| `cli-empty-capture.out` | 1,525 | `5062472fbd6e7853d37da399ab98c1eca197603283701b3b9d04ee780cdc3ee3` |
| `cli-fixture-identity-ok.out` | 8,472 | `1abb28965aee3fb7d7785a48ca2b4d98a56e2ccfdcfa8eee6d66a1689cb2ae8f` |
| `cli-fixture-json.out` | 7,950 | `d68fb7aeb18e2e359011f11cdae8696c17d92e52a7a435f45e7fd071e2d4df2f` |
| `cli-fixture-plain.out` | 6,093 | `89beab3bf2aaddd87945457c651aac87fd7771d79690b18323b7e0b34ce31d93` |
| `cli-identity-incomplete.out` | 8,286 | `4ee55e861ef9cf98071d45c0a6a5de3c5f4c4a49ffc43735d5f7ac376699caf7` |
| `cli-identity-sha-bad.out` | 9,019 | `685c15658d0acf471b56d00b0078338b7c8073c0b17b9745fd349531b7b81c1d` |
| `cli-index.txt` | 3,890 | `0c40595789d32fbc4c0ac7522bedb5995f0c1dc400b99c4098604c7d339819f5` |
| `cli-missing-file.out` | 128 | `ff5d5fb38b0f13e5848642345ed24bf9a9f01be3b5f74a431498302f4ce86885` |
| `cli-pr2-duplicate-input.out` | 8,767 | `2334f9368b6bde640b0d96a4c08c65d61328dcba5e0dcb5cb791ccd88d1642cb` |
| `cli-pr2-empty-capture-sidecar.out` | 2,053 | `f5b84bbe57f0e1048def9983d7805312e366c264514e6d46c79350e0d826b3e2` |
| `cli-pr2-empty-identity.out` | 10,367 | `6389b6f9705b138507a888f7c58d7a06993e94434498de748a019b67e078d7f6` |
| `cli-pr2-numeric-tamper.out` | 9,460 | `7de07b65ea95ff7c5cd15777af83052de1dd057beabfb9de44d4058bba93aca5` |
| `cli-pr2-same-basename.out` | 60,396 | `64a2f7b0505b82dfd62a7b4ed7c1e112d56273e135d2f2ed11905d6989c1fbb8` |
| `cli-pr3-numeric-tamper.out` | 10,964 | `bf5ea67e4647bcf5e5af49567d0125955a3bb568f7c88b84e9a533c50b404c65` |
| `cli-pr3-package-sha-trailing-lf.out` | 8,264 | `f876bd2ae178f9f95e2e0afd808a3ae8a47ce2747dfe6cd07a2a5eb8faf3548b` |
| `cli-pr3-package-sha-uppercase-ok.out` | 8,500 | `3c018e24b25d81bed13f7b52063f6f137105bdd6160e1e6d4a49129793607010` |
| `cli-real-ubuntu-loose.out` | 6,884 | `a1e2577c0998a6b368ed3d95d750a7f7cb20ee7a58f9797c2071a51f75479aaa` |
| `cli-real-ubuntu-strict.out` | 6,910 | `79a53afb21dd3c4f1b36c2bc86c68e3ab2766f731a3ec3bec97ccdb207563edc` |
| `cli-real-win-polluted.out` | 53,354 | `7a4efab01b5786b7b6fc057857ec63ec875bbc72c71156c1ff82f54b52657715` |
| `empty-capture.log` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `pr2-numeric-tamper.log` | 42,204 | `c27656d82e504d95a729fcd84b13b4220a8985ace59e853cec0743aad145f2d0` |
| `pr3-counterexample-probe.txt` | 3,942 | `cf25efa06c94165bfda6c846a9772008db2f32569f53120f1aaa87779009c59b` |
| `pr3-numeric-tamper.log` | 42,335 | `04642073966478afc76ac289ff26dc61785db8ba569bc6e4fadc1341f3c58dac` |
| `probe_pr3_counterexamples.py` | 4,747 | `3360192af9551a68e33f2bfe1e0585e9d7aacb5ef6faf63634214f8b3af96edd` |
| `selftest-full-2026-09-17.log` | 28,460 | `0454b47f4f0054462a78723a7351432057913c1b90f5fe14543eee0764d63b43` |
| `sidecar-empty-capture.json` | 720 | `dde75ab891a7c1cfd73d3e3d73192ffc4c28c8f3ea036eeaffcce2a6caa3f9c1` |
| `sidecar-empty-identity.json` | 510 | `122fa52c2e5ad305b223daf7423a601c742601b40d397602a65bf63170431609` |
| `sidecar-incomplete.json` | 663 | `7e6f097378bf822749240c678cec79169bc8a4783c8d21bc0c9fbba63231de7c` |
| `sidecar-ok.json` | 719 | `9a38bc5dd278f5467641155b767cf018908d3c2a73f49c3c336b48d94aa43c32` |
| `sidecar-package-sha-trailing-lf.json` | 737 | `878b5ee59386e803c0e378442de3c3dbf7341cd477b6894ad64c8571c86e136c` |
| `sidecar-package-sha-uppercase.json` | 733 | `f29b2b797c491263d78685d5d1e9b61312b1c2722ac93537af0cd4528e885afe` |
| `sidecar-sha-mismatch.json` | 719 | `3060a72ec817d4c5a2591f1595e6bacbc36cda782e4f6c3e66929fcd3ddd0c1c` |
| `SHA256SUMS-parser-remediation.txt`（清单本身） | 4,043 | `530267db86518f7362c8b6ea851df3f8d237d38aae838ba4f96694e3ffc156e5` |

清单沿用 `docs/ota-exec-notes/{real,toy}-loop-r7-evidence/SHA256SUMS-*.txt` 的既有
格式（`<文件名>: <字节>B sha256=<哈希>`），逐件覆盖上表除清单自身外的 34 个文件。
清单由 `.cache/p34-dev/make_manifest.py` 按工作树字节生成（目录内容变化即整表
重建，不做增量追加），生成输出固化在 `.cache/p34-dev/pr3-manifest.log`。

### 3.5 入库注意（供主会话）

- 证据目录中 4 个 `.log` 文件（`selftest-full-2026-09-17.log`、`pr2-numeric-tamper.log`、
  `pr3-numeric-tamper.log`、`empty-capture.log`）命中 `.gitignore:13` 的 `*.log`，
  `git status` 默认看不到，提交需 `git add -f`。仓库既有先例一致：
  `docs/ota-exec-notes/real-loop-r7-evidence/*.log`
  与 `toy-loop-r7-evidence/*.log` 同为忽略规则下已跟踪的原始日志。本会话不改
  `.gitignore`（不在整改范围内），也不改文件扩展名——`empty-capture.log` 的路径被
  `cli-pr2-empty-capture-sidecar.out` 的 `inputs[].path` 与 `cli-index.txt` 引用，
  改名会连带作废已冻结的 CLI 证据；`pr3-numeric-tamper.log` 同理被
  `cli-pr3-numeric-tamper.out` 与 `cli-index.txt` 引用。
- **不受忽略规则影响的新增件**：`pr3-counterexample-probe.txt` 扩展名是 `.txt`，
  `git add` 无需 `-f` 即可入库（逐字节清单仍由 §3.4 覆盖）。
- 本批新增的 `.gitattributes` 条目已使这些文件的 blob 与工作树逐字节相同，
  `git add -f` 后不会再出现"检出即变字节"的问题（§5.1 审计）。

---

## 4. 真实 CI 捕获的重新解释

四份真实捕获均在**只读**路径
`D:/github/my/E-Track/.cache/ci-<run>/{ubuntu,windows}/<runid>/logs/tests.log`
上解析，未复制、未修改。判定口径：`attributable` 的块才进数值池；`clean` 才进
"合格统计"；`threshold` 才标门槛可用。

### 4.1 污染识别（>1 实例段的块）

| 捕获 | 污染块标签 / 行范围 | 样本 | 实例段 | 确认样本 | 摘要声明确认 | 首发 / 重传 |
| --- | --- | --- | --- | --- | --- | --- |
| `ci-35034258547/ubuntu` | `upgrade` 行 787..（未收口） | 434 | 9 | 203 | None（无摘要） | 203 / 2 |
| `ci-35034258547/windows` | `upgrade` 行 307..976 | 454 | 9 | 210 | 8 | 210 / 2 |
| `ci-35094204310/ubuntu` | `upgrade` 行 813..（未收口） | 85 | 9 | 13 | None（无摘要） | 15 / 1 |
| `ci-35094204310/windows` | `upgrade` 行 240..450 | 114 | 9 | 21 | 8 | 22 / 1 |

Windows 行 307–976 的判定依据是发射端语义而非解析器口味：`ota_link_stats.dart:253`
用 `_sentOffsets.add(offsetBytes)` 保证**同一实例内首发偏移唯一**，该块内
`off=0`/`off=256` 重复首发（如 `off=0` 在行 885 与 941 各一次）→ 段内存在多实例，
"9 段 / 210 确认样本 vs 摘要 8" 即该形态的直接后果，不是解析器误报。

### 4.2 排除理由（不合格轮次）

排除项逐条带行号与理由，形如 `排除 <run>/<host> 行 a..b 检出=[...] 理由=[...]`，
逐条落盘于自测日志第 164–224 行（52 条）。理由取值实测为：

- `"OUTCOME:'fail'"` —— 非 ok 终态；
- `"ACK_SAMPLES:'partial:missing=N'"` —— 覆盖不全（N∈{1,8}）；
- `"SAMPLE_POPULATION_NOT_ATTRIBUTABLE:STRAGGLER"` —— 摘要后拖尾样本；
- `'NOT_SINGLE_INSTANCE'` 与 `'OFFSET_SET_INCONSISTENT:…'` —— 多实例/偏移集合违例
  （仅命中污染块本身，即 Windows 行 307–976）。

整份捕获读数与排除计数：

| 捕获 | 块 | 样本 | 解析期致命 | 告警分布 | runs | excluded | 未收口 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ci-35034258547/ubuntu` | 27 | 801 | 0 | `FIELD_ABSENT` 182、`STRAGGLER` 12、`SUMMARY_MISSING` 1 | 6 | 13 | 1 块 / 434 样本 |
| `ci-35034258547/windows` | 27 | 821 | 0 | `FIELD_ABSENT` 189、`STRAGGLER` 24、`DUPLICATE_SEGMENT_OFFSET` 2、`DUPLICATE_ACK_OFFSET` 2、`MULTI_INSTANCE` 1 | 6 | 14 | 0 |
| `ci-35094204310/ubuntu` | 43 | 443 | 0 | `STRAGGLER` 12、`SUMMARY_MISSING` 1 | 6 | 12 | 1 块 / 85 样本 |
| `ci-35094204310/windows` | 43 | 448 | 0 | `STRAGGLER` 29、`SUMMARY_MISSING` 1、`MULTI_INSTANCE` 1 | 5 | 13 | 1 块 / 6 样本 |

四份捕获解析期**致命 0 条**——但"0 致命"不等于"可合并"，这正是 P34-P02 的核心：
污染块以**排除**而非致命的方式离开数值池，其排除留痕可被独立复核。

### 4.3 合法合并范围（整改后的洁净池）

| 捕获 | runs | 确认样本 | 唯一段 | 唯一重传 | P99 | 字段完整 | 门槛可用 | 零样本块 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ci-35034258547/ubuntu` | 6 | 48 | 48 | 0 | 900 | False | False | 0 |
| `ci-35034258547/windows` | 6 | 48 | 48 | 0 | 1328 | False | False | 0 |
| `ci-35094204310/ubuntu` | 6 | 48 | 48 | 0 | 1184 | True | False | 8 |
| `ci-35094204310/windows` | 5 | 40 | 40 | 0 | 1020 | True | False | 8 |

- **字段完整**在第五轮捕获为 False：该轮发射端尚无 `bind.writeMode`/`bind.mtuSource`
  等绑定字段，`strictFieldsComplete` 如实反映"契约完整"而非"能跑"（§0.3 第 4 条）。
- **门槛可用全为 False**：四份捕获都未附侧车身份，按 P34-P01 记
  `GROUP_IDENTITY_NOT_DECLARED`。该结果符合设计——真实捕获不得在缺少实验身份声
  明时被标为可直接用于性能门槛；PR2-01 的门禁只在此之上加了"有样本、无整轮致命"
  两条，不改变真实捕获的既有结论（四份捕获 runs>0、致命 0，故新增两条不触发）。
- **零样本块 8**：第六轮两份捕获各有 8 个只含 `probe` 标签、无样本行的合法结构块；
  它们不计入污染（`_clock_segments([])` 返回 0 段），也不进任何数值池。

### 4.4 与整改前的差异（整改效果的直接读数）

`ci-35034258547/windows`（P02 的证据来源）：

| 指标 | 整改前 | 整改后 |
| --- | --- | --- |
| runs | 8 | 6 |
| 合并 ACK 样本 | 266 | 48 |
| 唯一段 | 64 | 48 |
| 污染块处置 | 整块进入合并 | 行 307–976 排除并留痕（理由 `NOT_SINGLE_INSTANCE`、`OFFSET_SET_INCONSISTENT:DUPLICATE_*`） |

整改前被合并的 266 个 ACK 里有 210 个来自 9 实例段的污染块；整改后洁净池只剩
6 轮 × 8 个已确认样本。P99 的绝对值在两种口径下不同（不受污染口径 vs 受污染口径），
本记录不复述旧 P99，以免把污染口径的数字当成基线。

### 4.5 第三批（PR3）后重读：四份捕获读数未变

PR3 改的是**样本数值域**与**包 SHA 域**，真实捕获中不含这两类缺陷，故四份捕获
应逐字节稳定。本轮重跑自测时对四份捕获重读，读数与 §4.1–§4.4 完全一致（原始
日志：`selftest-full-2026-09-17.log` 第 188–251 行）：

| 捕获 | 块 | 样本 | 致命 | runs | 确认样本 | 唯一段 | P99 | 门槛可用 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `ci-35034258547/ubuntu` | 27 | 801 | 0 | 6 | 48 | 48 | 900 | False |
| `ci-35034258547/windows` | 27 | 821 | 0 | 6 | 48 | 48 | 1328 | False |
| `ci-35094204310/ubuntu` | 43 | 443 | 0 | 6 | 48 | 48 | 1184 | False |
| `ci-35094204310/windows` | 43 | 448 | 0 | 5 | 40 | 40 | 1020 | False |

误导风险点：新增的 `BYTE_COUNT_INVALID` 致命码若作用于 GATT/platform 字节计数，
理论上可能让真实捕获新增致命项。实测四份捕获致命仍为 **0**，即真实捕获的
`kind=gatt_write`/`kind=platform_write` 样本字节数全为非负整数——**没有把真实
数据打红**，也没有因此改变任何一轮的洁净池。

---

## 5. 字节身份与新检出

### 5.1 审计方法与结果

`git ls-files --eol` 对解析器目录仍为：

```text
i/lf  w/lf  attr/-text   Tools/ota/p3-4-link-stats/fixtures/PROVENANCE.md
i/lf  w/lf  attr/-text   Tools/ota/p3-4-link-stats/fixtures/round6-ubuntu-head.log
i/lf  w/lf  attr/-text   Tools/ota/p3-4-link-stats/link_stats.py
i/lf  w/lf  attr/-text   Tools/ota/p3-4-link-stats/selftest.py
```

对本批新增证据的审计不依赖属性声明，而是**跑真实的 clean/smudge 过滤器**：
在隔离的 `GIT_INDEX_FILE` + `GIT_OBJECT_DIRECTORY` + `GIT_ALTERNATE_OBJECT_DIRECTORIES`
下 `git add -f` → `git cat-file -p :<path>`（blob 字节）→
`git checkout-index -f -a --prefix=<包内临时目录>/`（新检出字节），
与工作树字节三者逐字节比对，并用 `git check-attr -a` 记录属性。

```text
目标数=39（证据目录 35 件 + link_stats.py + selftest.py + .gitattributes + 本记录）
新检出字节 != 工作树字节（真实缺陷）的文件数=0
工作树/blob/新检出 三者不等的文件数=0
```

即：P34-PR2-05 的缺陷（`719 → 743 B` 那类检出即变字节）在 PR3 新增文件上同样不
出现，且**每一个**目标（不只 4 个 `.log`）都通过了字节身份审计。
审计用的包内临时目录在比对完成后已删除，工作树内无残留。

复核方式：在最终字节上重跑同一脚本，`EXIT=0`、39 行 `OK`、`0` 个 `DIFF`/`UNSTABLE`；
原始输出固化在 `.cache/p34-dev/pr3-byte-audit.log`（gitignored 开发产物，
不属于证据包；证据包里与字节身份相关的只有证据文件本身与上表哈希）。

### 5.2 旧包 → 新包字节对照

`cli-*.out`、`cli-index.txt`、`selftest-full-*.log` 因 PR2 批次行为变化而据实
重放，旧字节保存在 `.cache/p34-dev/old-manifest.txt`（上一修订清单副本，
gitignored）。逐条对照（旧 → 新，前缀为 SHA-256 前 16 位）：

| 文件 | 旧字节 / 旧前缀 | 新字节 / 新前缀 | 变化原因 |
| --- | --- | --- | --- |
| `cli-fixture-plain.out` | 6,093 / `89beab3bf2aaddd8` | 6,093 / `89beab3bf2aaddd8` | **未变**（人读输出，本批未改其格式与取值） |
| `cli-missing-file.out` | 128 / `ff5d5fb38b0f13e5` | 128 / `ff5d5fb38b0f13e5` | **未变**（读取失败路径） |
| `sidecar-ok.json` | 719 / `9a38bc5dd278f546` | 719 / `9a38bc5dd278f546` | **未变**（冻结输入） |
| `sidecar-sha-mismatch.json` | 719 / `3060a72ec817d4c5` | 719 / `3060a72ec817d4c5` | **未变**（冻结输入） |
| `sidecar-incomplete.json` | 663 / `7e6f097378bf8227` | 663 / `7e6f097378bf8227` | **未变**（冻结输入） |
| `empty-capture.log` | 0 / `e3b0c44298fc1c14` | 0 / `e3b0c44298fc1c14` | **未变**（冻结输入） |
| `cli-fixture-json.out` | 7,878 / `b85ec74eebd01881` | 7,950 / `d68fb7aeb18e2e35` | 顶层新增 `inputs[]` 来源元数据 |
| `cli-fixture-identity-ok.out` | 8,400 / `9952cfdb2594f203` | 8,472 / `1abb28965aee3fb7` | 同上 |
| `cli-identity-sha-bad.out` | 8,934 / `eaa8459d4bc37818` | 9,019 / `685c15658d0acf47` | 同上 + 门槛理由 |
| `cli-identity-incomplete.out` | 8,214 / `389ba60d4edc4ddf` | 8,286 / `4ee55e861ef9cf98` | 同上 |
| `cli-empty-capture.out` | 1,413 / `60a4dc0678eefa02` | 1,525 / `5062472fbd6e7853` | 同上 + `NO_ELIGIBLE_RUNS` 理由 |
| `cli-real-win-polluted.out` | 53,113 / `e22160cbf4e1e2b0` | 53,354 / `7a4efab01b5786b7` | 同上 |
| `cli-real-ubuntu-loose.out` | 6,669 / `149a45d2f6b998bf` | 6,884 / `a1e2577c0998a6b3` | 同上 |
| `cli-real-ubuntu-strict.out` | 6,670 / `e4b2a1acc526204b` | 6,910 / `79a53afb21dd3c4f` | 同上 |
| `cli-index.txt` | 1,965 / `12ca19de37eb2599` | 3,185 / `89bb996814d868fc` | 追加 5 条 PR2 命令（既有 10 行逐字节未变） |
| `selftest-full-2026-09-17.log` | 21,317 / `509001ae5c693d1f` | 25,457 / `20f6313efd29c24f` | 用例 92 → 110，配对 38 → 53 |
| 新增（9 件） | — | `build_pr2_inputs.py`、`pr2-numeric-tamper.log`、`sidecar-empty-{capture,identity}.json`、`cli-pr2-*.out` ×5 | PR2 证据 |
| 移出（1 件） | 20,860 / `fb8a24f362575afe` | 移至 `.cache/p34-dev/superseded/` | 上一修订的旧自测归档，不属本轮结论 |

上表为 **PR2 轮**的旧 → 新对照，已固化为上一修订的结论，本轮不重述其判断。
**PR3 轮**（本批）的字节对照如下，判据是"既有证据不得被改写"：

| 文件 | 本轮结果 | 依据 |
| --- | --- | --- |
| 15 个既有 `cli-*.out` | **逐字节未变**（全部 `字节一致`，0 个 `重生成`） | `.cache/p34-dev/pr3-cli-matrix.log` 的逐条 `字节一致` 行 |
| `cli-index.txt` | 3,185 / `89bb996814d868fc` → 3,890 / `0c40595789d32fbc` | 追加 3 条 PR3 命令；脚本对同名既有行做**全等比较**，15 行逐字节未变（`cli-index.txt 新增行` ×3，无"既有行被改动"失败） |
| `selftest-full-2026-09-17.log` | 25,457 / `20f6313efd29c24f` → 28,460 / `0454b47f4f005446` | 用例 110 → 124，配对 53/18 目标 → 64/22 目标，期望条目 61 |
| 新增（9 件） | — | `build_pr3_inputs.py`、`probe_pr3_counterexamples.py`、`pr3-counterexample-probe.txt`、`pr3-numeric-tamper.log`、`sidecar-package-sha-{trailing-lf,uppercase}.json`、`cli-pr3-*.out` ×3 | PR3 证据 |
| 移出（2 件） | 56,711 / `(上一修订报告)` 与 3,039 / `326cfd711e04bc73` | 移至 `.cache/p34-dev/superseded/` | 上一修订的报告与清单副本，已被本轮修订取代 |

**关键点**：本轮对 15 个既有 CLI 输出**一个字节都没改**。这正是复审要求
"Do not change golden outputs to accept these malformed inputs" 的直接证据——
新增的六类反例是在**新用例**里判红，不是在旧输出里把期望值改宽。

真实切片身份（P34-P02 与 P04 共用的输入，未变）：

```text
来源 SHA-256 = 1cc73fa22e4cb692b685a5fb582380de189a84faa0f6d11927219068dc8406e6 (179,715 B)
夹具 SHA-256 = d482f9ed386a064146992585fdf93ab2738f1b785c2bdc2e910e0d81c37bf645 (41,982 B, 274 行)
夹具 == 来源前 41982 字节 : True
末行 = OTA_LINK_STATS {"schema":1,"label":"probe","device":"AA:BB",…
```

即夹具仍是真实捕获的**逐字节前缀**，末行是完整摘要（块边界完整）；与
`PROVENANCE.md` 登记值逐项一致。

---

## 6. 写入边界审计

- **主工作树评审证据目录 `.cache/p3-4-parser-review-20260917/`（只读输入）**：
  未重跑其 runner、未覆盖其任何文件；本会话仍未触碰。
- **主工作树复审证据目录 `.cache/p3-4-parser-rereview-20260917/`（只读输入）**：
  同上，未触碰。
- **主工作树本轮准入复核目录 `.cache/p3-4-parser-review-pr2-followup-20260917/`
  （只读输入）**：`review.md`（10,889 B，sha256 `7f13a9299aefcc8f…`）与同目录
  `review.py`、`final-audit.json`、`numeric-neighbors.json`、`identity-neighbors.json`
  仅被读取用于定位两个缺陷与复现粒度（哈希见 §1.3），**未重跑、未覆盖、未新增
  同名文件**；本轮的反例复现一律写入本工作树的新目录
  `docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17/`，不写入评审目录。
- **复审会话资产**：`docs/ota-exec-notes/P3-4-parser-rereview-2026-09-17.md`
  （13,621 B）与 `.cache/p3-4-parser-rereview-20260917/` 只读引用，未改字节
  （哈希见 §1.2/§1.3）。
- **主工作树 `git status --short --branch`**：与开工快照逐条一致（仅
  `PLAN-OTA-EXEC.md`、`app/bluetooth_flutter_Trace/**` 的既有改动与既有未跟踪
  文件，无新增条目）；本会话未向主工作树写入任何文件。
- **本会话全部写入落在 p3-4 worktree 内**：
  `Tools/ota/p3-4-link-stats/{link_stats.py,selftest.py}`、
  `docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17{,.md}`、
  `.gitattributes`（+10 行）、以及 gitignored 的 `.cache/p34-dev/`（探针脚本、
  中间日志与 `superseded/` 旧归档）。
- **临时文件**：selftest 自带的 `leftover_temp_files()` 用例断言解析器目录无
  `_tmp_*` 残留；CLI 生成器用 `'xb'` 写入并拒绝覆盖既有内容；PR3 反例探针
  同样在 `finally` 中回收侧车临时文件（`pr3-counterexample-probe.txt` 末行实测
  输出 `leftover_temp_files()` 为空）；字节审计的隔离索引与临时检出目录已删除。
- **`git status` 可见性**：证据目录 35 件中 4 个 `.log` 被 `.gitignore` 遮蔽
  （需 `git add -f`，见 §3.5）；其余 31 件按常规则可见。
- 未产生项目外写入；未做真机操作与远端操作。

---

## 7. 未覆盖项与诚实声明

1. **P34-PR2-03 无变异对**。输入去重与来源标识在 `main()` 装载层，变异表只覆盖
   解析/判定函数；该修复的证明是两条 CLI 断言（`runs` 不成倍、来源可追溯），
   矩阵中已如实标注。
2. **`PHASE_NEGATIVE` 无独立变异对**。其同函数 `_check_derived` 的另 3 条配对（重传派生量、`PHASE_REVERSED`、bind 阶段时长）不覆盖负阶段时间分支，`PHASE_NEGATIVE` 本身只有用例 + CLI 端到端致命码断言。
3. **P34-P06 是源码语义构造**。早到 ACK、resume、重传、多实例的形状按发射端
   `ota_link_stats.dart` 的输出序在自测内构造，**不是** Dart 实机执行结果，
   也不是设备测量。
4. **无侧车下的门槛判定**：四份真实捕获都没有 `--group`，因此真实
   `eligibleForThreshold` 全为 False 是"缺声明"的结果，不能读成"性能不达标"。
5. **`ineligibleReasons` 措辞不精确（未修）**：侧车在场但字段非法/不全时，理由
   清单会同时出现 `GROUP_IDENTITY_NOT_DECLARED` 与
   `GROUP_IDENTITY_INVALID`/`GROUP_IDENTITY_INCOMPLETE`（后者已足够定位）。
   这是"身份函数返回 None → 与未声明同路径"的措辞后果，不影响退出码、致命性与
   门槛判定，属外观问题，不在两批阻断范围内。
6. **本机 SKIP = 0**：四份真实捕获在本机齐备，故"可选：整份真实捕获"与 P02 的
   真实污染块用例实际执行并 PASS。**若在无捕获环境运行，这些用例会 SKIP；
   SKIP 不得计入 PASS**（`selftest.py` 对缺捕获一律走 SKIP 分支而非断言通过）。
7. **本记录不是独立验收**。不构成 P3-4 完成声明，不构成独立验收 PASS；
   正式验收仍为 **NOT_RUN**（尚无已审批冻结合同与矩阵）。复审是否放行由非实现
   会话判定，本记录只提交"已按三批阻断项（P34-P01..P07、P34-PR2-01..PR2-05、
   P34-PR3-01/PR3-02）整改并附开发自测证据"。
8. **未执行**：真机/AT/J-Link/烧录/安装/OTA/发布部署/远端产物删除，APK、EXE 与
   固件构建，任何 workflow 触发，任何 CI 定时重跑变更。
9. `PLAN-OTA-EXEC.md` 与主工作树的实现记录本会话**只读**，需回写的文本见 §8，
   由主会话串行落盘。
10. **`_TOKEN_RE` 无变异对（PR3 新增声明）**。PR3-02 的整改把 `\A…\Z` 用于
    `_INT_RE` 与 `_HEX64_RE`（两者都有配对：`test_lexical_regexes_reject_trailing_newline`
    同时期望"数字解析必须整串匹配"与"hex64 域必须整串匹配"，两条负例各自打红）。
   `_TOKEN_RE` 未加配对，理由是它**不构成外部可达的换行路径**：其值类 `[^=]*`
   在语法上能吞 `\n`，但该正则的输入来自按行切分后的单行文本，行内不可能含
   `\n`；若强行给它加"必须拒绝尾随换行"的负例，得到的是一条**不可达**断言——
   上一轮我正是照抄了这个错误期望，导致自测两次假红（`selftest.py:926`），
   最终以删除该断言与配对了结。故此处只保留可被外部输入触发的两条。
11. **`main()` 装载层仍无变异对**（承接第 1 条）。PR3 的两处修复（`_sum_bytes`
    域校验、`_observed_counts` 全量遍历、`_sample_off` 的 `require_len`）全部
    位于**解析/判定层**，因而都有类型保持的变异对（共 **11 对 / 5 个目标**，
    见 §3.2）；装载层的输入去重/来源标识继续只由 CLI 断言覆盖，与第 1 条同因，
    不重复声明。
12. **平台写入侧只验"负值"域**。`platform_write` 与 `gatt_write` 共用
    `_sum_bytes`，本轮对两侧都加了同域变异对（`test_gatt_negative_bytes_is_fatal`
    与 `test_platform_negative_bytes_is_fatal`），反例探针另给了"净零"组合
    （`bytes=-5` 与 `bytes=+5` 并存）证明**逐条校验而非按合计**。该函数的另外
    两个子域（`bytes` 缺失、非整数）走既有 `MALFORMED_SAMPLE`(fatal) 分支，
    不是本轮改动，因此**没有**配套的 PR3 变异对——这是本条登记的真实未覆盖点：
    新域有对、旧域只有既有用例，二者不同源。

---

## 8. 供主会话串行回写的文本

### 8.1 追加到实现记录 `docs/ota-exec-notes/P3-4-wiring-impl-2026-09-16.md`

```markdown

## 11. 解析器整改（P34-P01..P34-P07、P34-PR2-01..PR2-05、P34-PR3-01/PR3-02）实现与开发自测（2026-09-17）

- 分支/工作树：`dev/flutter/p3-4-link-stats` /
  `D:\github\my\E-Track\.cache\worktrees\p3-4-link-stats`，基线 `0441f78`
- 改动：`Tools/ota/p3-4-link-stats/link_stats.py`
  `0cf95913612c688c6414b2becddcacffebc5b5aa92641eb989a299737b6b82c7`（84,728 B）；
  `Tools/ota/p3-4-link-stats/selftest.py`
  `fb1ec6f23644189a1ce17a512d47cd5d70bdbd20c261b767be7075637832b3dc`（164,081 B）；
  `.gitattributes` `d1d982d9…`（+10 行，证据包整目录 `-text` 行尾保护，只增不改）；
  合计 3749 插入 / 395 删除。
- 自测：`python -X utf8 -S -B Tools/ota/p3-4-link-stats/selftest.py`
  → exit 0，**124 项全通过**、FAIL 0 / SKIP 0 / ERROR 0；鉴别力 **64 条负例槽位 /
  23 条目 / 22 个变异目标 / 61 条期望条目 / 10 个正例**，运行期异常 0；
  CLI 矩阵 **18 条**全部按预期退出码与字段断言通过。
- 第一批（P34-P01..P07）：资格门禁、身份语义域、输入去重与来源标识、时序字段
  完备性与数值域、鉴别力配对、证据包字节身份。
- 第二批（复审 5 类 P34-PR2-01..05）：资格门禁改为"身份声明 ∧ 有合格洁净轮且
  ACK 样本>0 ∧ 整轮无致命"；身份空串/占位符/零参数不构成声明；输入按 sha256
  去重且 `sourceId` 带内容摘要；时序三键缺失、负偏移、零段长、负阶段时间全部
  致命化；证据包整目录钉 `-text`。
- 第三批（本轮准入复核 P34-PR3-01/PR3-02）：`_observed_counts` 改为遍历**每一条**
  durable（不再只看末条），`_sample_off` 增 `require_len` 分支，`_sum_bytes` 对
  GATT 与 platform **两个调用方**共用同一负值域校验，新增致命码 `BYTE_COUNT_INVALID`；
  三个词法正则 `_TOKEN_RE`/`_INT_RE`/`_HEX64_RE` 一律改用 `\A…\Z` 整串锚定
  （`$` 可匹配末尾换行之前，导致 64 位十六进制 + `\n` 的 65 字符包 SHA 曾被放行）。
  六类反例经 `probe_pr3_counterexamples.py` 逐条隔离复现（每条恰命中一个致命码），
  合并后经真实 CLI 得到退出码 1、致命集合恰为
  `{SEGMENT_OFFSET_INVALID, SEGMENT_OFFSET_MISSING, SEGMENT_LENGTH_INVALID,
  BYTE_COUNT_INVALID}`、8 处反例逐条点名、`runs=0`、门槛不可用；合法对照
  （大写摘要 + `maxRetries=0`、合法重传、durable 零偏移 resume 起点、两类写入的
  合法字节和）全部保持门槛可用。**15 个既有 CLI 输出本轮一个字节未改**。
- 真实捕获重新解释：四份捕获解析期致命仍为 0，污染块（9 实例段）以**排除**并留痕
  的方式离开数值池；`ci-35034258547/windows` 为 6 runs / 48 确认样本 / 48 唯一段；
  四份捕获因无侧车身份，门槛可用仍为 False（第三批后重读，四份读数逐项未变）。
- 详表、CLI 矩阵、逐件 SHA-256 与字节对照见
  `docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17.md` 与同目录证据包（35 件，
  清单 `SHA256SUMS-parser-remediation.txt` 4,043 B / `530267db…`）。
- **定位：实现认领 + 开发自测；不构成独立验收 PASS，正式验收仍为 NOT_RUN。**
```

### 8.2 看板 `PLAN-OTA-EXEC.md` P3-4 卡

- 状态保持 **进行中**（不得置"完成"）；认领标识不变。
- §9 变更登记表无需新增行（未改冻结契约、未改线协议、未改 profile）。
- §10 会话日志追加一行：

```text
2026-09-17 | P3-4 | 解析器整改第三批（准入复核 P34-PR3-01/PR3-02）实现完成并本地自测通过：124/124，鉴别力 64 槽位/23 条目/22 目标/61 期望条目，CLI 18 条（既有 15 条输出逐字节未变）；证据 docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17(.md 及 /，35 件)；正式验收仍 NOT_RUN，待非实现会话复审判定 | 工作树 .cache/worktrees/p3-4-link-stats
```
