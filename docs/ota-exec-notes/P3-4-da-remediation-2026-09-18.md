# P3-4 发送端 DA01–DA03 整改与整卡交付记录

日期：2026-09-18（Asia/Shanghai）
实现方：Claude Code（实现会话，非验收方）
独占验证 worktree：`D:\github\my\E-Track\.cache\worktrees\p3-4-link-stats`
分支：`dev/flutter/p3-4-link-stats`
被整改基线：`b6b2164159e4131610bb53efec45378f7ce6c35e`（tree
`3ac58d261c29f30cea53b8f172e07e5872f02b96`，即 2026-09-17 准入复核所审 HEAD）
整改依据：`docs/ota-exec-notes/P3-4-device-admission-2026-09-17.md`、
`docs/ota-exec-notes/P3-4-device-prerequisites-2026-09-18.md` §5 清单

本文件是**实现侧交付记录**。它不构成验收结论，也不改写任何冻结包；`P3-4-parser-v1`
的既有 PASS 与本轮无关，整卡设备/性能验收仍为 `NOT_RUN`。

本轮**未**执行：设备连接、AT 命令、J-Link 挂载/烧录、APK 安装/清数据、OTA 传输、
release/deploy、远端产物删除。发送端源码与测试**仅**写入上述 worktree。

---

## 1. 交付物总览

| 类别 | 文件 | 增/删行 |
|---|---|---|
| 发送端源码 | `app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart` | +56 / −12 |
| 发送端源码 | `app/bluetooth_flutter_Trace/lib/ota/ota_link_stats.dart` | +91 / −10 |
| 发送端源码 | `app/bluetooth_flutter_Trace/lib/services/ota_service.dart` | +31 / −4 |
| 运行期测试 | `test/ota/ota_link_stats_test.dart` | +96 / −3 |
| 运行期测试 | `test/ota/ota_ble_transport_test.dart` | +221 / −3 |
| 运行期测试 | `test/ota/ota_service_upgrade_test.dart` | +73 / −3 |
| 运行期测试（新增） | `test/ota/ota_probe_late_attribution_test.dart` | 新增 516 行 |
| 开发自测入口（移植） | `.github/workflows/flutter-dev-checks.yml`、`Tools/flutter/dev_checks.py`、`tests/ota/test_flutter_dev_checks.py`、`.github/workflows/build.yml` | 与 main `2d81a4b` 逐 blob 一致 |

开发自测入口移植说明见 §8；它只移植**受审的 checks-only 工作流与诊断输入**，
不搬运 CI-ARTIFACT-01 治理特性（`manifest_profiles.json` 的 artifact 条目、
`artifact-maintenance*`）。

---

## 2. P34-DA01：被采信 ACK 的到达时刻归因

### 2.1 原始缺陷

原有实现把「ACK 到达时刻」取在调用方 `await` 返回**之后**：ACK 身份（seq/durable/
状态）已被正确校验，但时刻已经包含了写结算、帧解析与校验自身的开销。复现形状是
「同一被采信 ACK 的时刻随调用处后续工作漂移」，而不是身份误判。

### 2.2 修复后的口径

`lib/ota/ota_ble_transport.dart`：

- `_dispatchFrame`（:773）在**单个同步块**内一次性取钟 `final arrivalUs = stats?.nowUs();`
  （:794），并把同一值传给该次分发的每个等待者 `w.offer(f, atUs: arrivalUs)`（:796）。
  一次分发只取一次钟，同一帧的所有等待者看到同一时刻。
- `_FrameWaiterBase.arrivalUs`（字段 :1822，赋值 :1770）只在**首个匹配且未完成**的
  等待者上打戳；重复/迟到的同 seq 帧不覆盖。
- BEGIN：`final beginAckArrivalUs = beginAck.arrivalUs;`（:351）→
  `recordBeginAckArrival(arrivalUs: beginAckArrivalUs)`（:380）。
- END：`final endAckArrivalUs = waiter.arrivalUs;`（:603）；为 `null` 时抛
  `OtaTransportException('END ACK 到达时刻缺失（非分发路径完成）', code: 'ACK_MALFORMED')`，
  **不再回退到事后时钟**；否则 `stats?.recordEndAckArrival(atUs: endAckArrivalUs)`（:614）。
- 续传 BEGIN（resume）：`arrivalUs: waiter.arrivalUs`（:947）。

`lib/ota/ota_link_stats.dart`：`recordEndAckArrival({required int atUs})` 只采信传入值；
`recordResumeConfirm` 的 `[arrivalUs]` 语义同步改为「该有效 ACK 帧**到达分发点**的同源
时刻」，并写明调用方不得在 `await` 返回后另取时钟。

**未改动**：DATA 段延迟路径（样本在 `view.onAck(f)` 内采集，本就位于分发同步块内，
与本次同一时钟域）；transport 的成功/超时/取消/协议判定规则一律不变。

### 2.3 起点/终点口径映射声明（替代原「冻结边界」措辞）

评审要求：「`_writeFrame` 与其测试把『含写队列的 API 调用』描述为冻结边界，而
TUNING 权威文本说的是 BEGIN 传输起点。给出精确可观测映射与队列行为；源注释不能
改写契约。」

权威文本（`docs/ota-cross-system-contracts.md:1064`，`OTA-XC-BLE-TUNING`）：

> 计时使用单调高精度时钟，从 BEGIN 首字节开始发送到成功 END ACK 完整到达，包含正常
> ACK 等待和重传，不包含 latest 或 HTTP 下载。

Dart 侧映射（已写入 `ota_link_stats.dart::recordTransferStart`、
`ota_ble_transport.dart::_writeFrame` 与对应测试注释）：

| 契约量 | Dart 可观测代理 | 偏差方向 |
|---|---|---|
| BEGIN **首字节开始发送** | 首个 BEGIN 帧进入 `_writeFrame` 的时刻（在 `_writeFrameChecked` 写结算、`_writeSerial` 串行队列排队、帧分片与平台写回调**之前**） | 代理早于真实起点 ⇒ 测得时长**偏长** |
| END ACK **完整到达** | END 类帧到达 `_dispatchFrame` 的时刻（解码后、await 续体之前） | 同样不晚于真实到达 ⇒ 偏长 |

队列行为：起点登记是幂等的，只有本 transfer 的首个 BEGIN 帧生效；**串行队列排队
等待被计入传输时长**（这是代理偏长的来源之一，也是保守方向本身）。transfer 之外的
帧（GET_INFO 探针、后台身份复核）不构成传输起点。

因此 `effectiveThroughputKiBps = referencePackageBytes / 1024 / elapsedSeconds`
在 Dart 侧是契约口径的**保守上界**（时长只多不少、吞吐只低不高），不存在「美化
吞吐」的方向性风险。

残余（必须随结果一起报告，不得省略）：该上界与契约真值之差**无法在 Dart 侧直接
量化**——UART 首字节上线时刻对 Dart 不可见。差额可在分析时用帧级样本序列估计：
样本行分别携带每帧写调用时刻与该确认到达时刻，写调用与 ACK 到达之间的空档即为
排队/平台写开销的量级；重传轮次会放大该差额。任何把 `elapsedSeconds` 当作精确
契约值使用的结论，都必须同时给出这一残余量级。

源注释只描述代理映射，不改写契约文本；完整声明以本节为准。

---

## 3. P34-DA02：失败元数据先于终结摘要封存

原始缺陷：`emitSummary()` 是幂等封存（只有首次生效），而它在 `!ack.isOk` 分支**之前**
执行，导致非 OK END 路径的 `fail(stage, reason)` 永远进不了已发布的 JSON，摘要里
`failure` 域停在空值。

修复（`lib/services/ota_service.dart`）：

- 传输返回后先判两个**立即失败分支**：`fail('cancelled', 'generation-changed')`（:955）
  与 `fail('transfer', 'mcu-ack-0x<status>')`（:967），之后才 `linkStats.emitSummary()`
  （:972）。
- `finally`（:1180）仍无条件幂等收尾：所有早退、取消、异常与成功路径都恰好产出一份
  `OTA_LINK_STATS`，且 `recordTransferOutcome(ok: false)` 兜底不伪装成功传输。
- 探针轮次的 `attemptStats.emitSummary()`（:1773）与其后的 `roundStats.emitSummary()`
  （:1776/:1790）保持「先记结论、后封存」的同一顺序。
- 返回语义不变：整轮以 `false` 返回，**不抛异常**。

---

## 4. P34-DA03：放弃尝试的观测流封存与迟到归因

原始缺陷：外层 `.timeout` 只放弃等待，**不取消**在飞的平台发现/绑定调用。它们稍后
恢复时仍会在已定格实例上产生样本行，落到**下一轮**尝试的摘要块内 → 解析器按块内
计数核对判为 `STRAGGLER`（归属不明），下一轮的合法观测被降级，本轮的迟到观测又
无从归属。

修复：

- `OtaLinkStats.retire({required String reason})`：幂等封存，输出
  `OTA_LINK_RETIRE label=<l> attempt=<n> reason=<r> us=<n>`，置 `_retiredReason/_retiredUs`。
- 封存后该实例的一切观测改走 `OTA_LINK_LATE label=<l> attempt=<n> kind=<k> us=<n> [extra]`
  ——**自带归属**，并且不再进入任何数值池与计数（`discovers.calls` 等保持封存时刻的值，
  见 4.1 的实现缺口与封存闸门）。
- 摘要新增 `'retired': {'reason': <r>, 'us': <n>}`；未封存实例该字段为 `null`。
- 调用点：`ota_service.dart:1759`，仅在「本轮未获判定」（`outcome == null`）时封存，
  原因三分：`outer-timeout`（外层预算放弃）、`cancelled`（取消代次变化）、
  `no-verdict`（其余无结论）。取得结论的轮次（completed / identityChanged / timedOut）
  不封存——该路径上所有 await 都已返回、平台调用无在飞工作，观测流自然排空。

**被放弃的工作留痕，不静默删样本**：封存**之前**已产生的合法样本原样保留在流里，
该轮摘要以 `retired` + `attempts[].outcome='abandoned'` 记明其状态；封存**之后**的
观测一条不丢，只是换成带 `attempt=` 的 LATE 行。实现中不存在「删除观测以改善
统计」的分支。

### 4.1 封存闸门：CI 红运行后的一次性静态复查发现的实现缺口

首轮开发自测（run 35257955951，见 §9）为红。在按 §7.3 集中审查该轮失败集时发现
首版实现只改了**行的前缀**，没有改**数值入账**：`_emitSample` 在封存后改走
`OTA_LINK_LATE`，但各 `record*` 方法仍无条件 `add()` 到样本列表、累加字节与
错误计数。后果是封存轮次的数值池被迟到观测悄悄改写——那份摘要早已发射且不可重发，
迟到数值既不进任何摘要、又会被下游误读成该轮（已放弃）的合法统计。该缺口同时与
本轮新增的 DA03 断言（`s1['discovers']['calls'] == 0`）直接矛盾，属实现与声明不符。

修复（`lib/ota/ota_link_stats.dart`）：新增单一入账闸门
`bool _startObservation(String kind, int us, {String extra})`——未封存返回 `true`；
已封存则只写一条 LATE 行并返回 `false`，调用方立即返回、不改动任何统计字段。
闸门覆盖全部样本/计数入口共 8 处：`recordGetInfo`、`recordSegmentSendEnd`、
`recordAckConfirm`（逐段按封存时冻结的 `_firstSendEndUs` 判 `ack_early`/`ack_latency`，
不写确认集合与早到暂存）、`recordAckClass`、`recordDurableAdvance`、`recordGattWrite`、
`recordDiscover`、`recordPlatformWrite`。未封存路径的行文与数值逐字不变。

边界（写进代码注释，避免二次歧义）：封存封的是**观测流**，不封**轮次账目**——
`recordAttemptOutcome`、`phaseEnd`、`recordFailure`、`emitSummary` 与
`recordTransferStart`/`recordCharsDiscovery`/`recordMtu`/`recordSubscribe` 仍照常登记，
它们只服务本实例自己的那份摘要，不跨轮次串扰；否则被放弃轮次会失去
`attempts[].outcome=abandoned`。

新增确定性断言（`test/ota/ota_link_stats_test.dart`，同一 `debugPrint` 捕获）：
封存前 8 个入口各一次建立基线 → 封存 → 同一批入口各再来一次，断言
`bind`/`getInfo`/`transfer`/`gattWrites`/`discovers`/`platformWrites` 六个域**逐字不变**、
恰好新增 8 条自带 `label`/`attempt` 的 LATE 行、且样本行计数不再增长。

---

## 5. 日志/解析器契约影响声明

| 行前缀 | 新增/既有 | 字段 | 解析器 v1 行为 |
|---|---|---|---|
| `OTA_LINK_SAMPLE` | 既有 | `label kind us [extra]` | 解析；未封存实例唯一形态 |
| `OTA_LINK_LATE` | **新增** | `label attempt kind us [extra]` | **忽略**（前缀不符，不进任何池） |
| `OTA_LINK_RETIRE` | **新增** | `label attempt reason us` | **忽略** |
| `OTA_LINK_STATS` | 既有 | 规范 JSON 单行（新增 `retired` 字段） | 解析；新字段是**增加**，未删除/改名任何既有字段 |

- 只有 SAMPLE/LATE 携带 `attempt=`；RETIRE 在轮次外壳实例上 `attempt=-`。
- `P3-4-parser-v1` 的冻结证据、证据包与该轮核验器**未改动一字节**；本轮不重跑
  parser-v1，也不主张其结论因此变化。
- 是否需要把 LATE/RETIRE 纳入统计口径、以及是否触发最小重跑，属于**验收方**的
  依赖与 rerun-plan 判定，实现侧不自行扩围、不预填结论。

---

## 6. 确定性运行期测试清单

| 文件 | 用例 | 断言的可观测对象 |
|---|---|---|
| `test/ota/ota_link_stats_test.dart` | 终点取传入的到达时刻，不回退调用处时钟（DA01） | 传入 `atUs` 与调用处时钟分离时，字段与样本取传入值 |
| 同上 | 封存：迟到观测走 `OTA_LINK_LATE`，样本流停止且不入数值池（DA03） | 原始行前缀、行序、`discovers.calls` 不增长；封存**前**已产生的合法样本原样保留 |
| 同上 | 封存闸门覆盖全部样本与计数入口：迟到观测只留 LATE 行，数值池不变（DA03，4.1 的回归） | `bind`/`getInfo`/`transfer`/`gattWrites`/`discovers`/`platformWrites` 六域封存前后逐字相等；恰新增 8 条 LATE；样本行数不再增长 |
| 同上 | 未封存实例不产出 RETIRE/LATE 行，`retired` 字段为空（对照） | 反向对照，证明上条不是「怎么写都过」 |
| `test/ota/ota_ble_transport_test.dart` | 传输起点在首个 BEGIN 帧写调用时刻登记（保守代理，含排队等待）（P34-R03） | BEGIN 写永不返回时起点仍已登记 |
| 同上 | END 终点取被采信 ACK 的到达时刻：写结算后时钟再推进也不改判 | 时刻与身份同源，不随后续工作漂移 |
| 同上 | 未采信的 END 类帧到达不登记终点：伪造 ACK_END 只按无关应答处理 | 终点不被无关帧污染 |
| 同上 | resume BEGIN 前缀样本终点取该 BEGIN ACK 的到达时刻（P34-DA01） | 续传路径同一规则 |
| `test/ota/ota_service_upgrade_test.dart` | 非 OK END：失败元数据先于终结摘要封存，且整轮只有一份摘要（P34-DA02） | 注入非 OK END 后，**已发射 JSON** 的 `failure.stage='transfer'`、`reason='mcu-ack-0x10'`，且 `OTA_LINK_STATS` 恰一行 |
| `test/ota/ota_probe_late_attribution_test.dart` | 假适配器挂起第 1 轮发现：封存 → 第 2 轮完成 → 放行，迟到观测显式归因 | 原始流：1×RETIRE、1×LATE(带 attempt)、1×SAMPLE、块序 |
| 同上 | 挂起点在平台调用入口之上（双宿主）：迟到发现同样显式归因 | 同一契约在 Ubuntu 宿主也可执行 |
| 同上 | 正对照：不封存同一交错会产生越块样本行（本文件鉴别力的凭据） | 去掉封存后必出现越块的、无 attempt 绑定的 SAMPLE 行 |

**真实外壳 + 假适配器**（R07 要求的替换）：`ota_probe_late_attribution_test.dart`
用**真实 `BluetoothService`**（`findExactOtaCharacteristicsByAddress` →
`discoverServicesByAddress` → `recordDiscover`）装配可注入的假适配器
（`adapterForTest`）或只挂起入口的替身外壳（内部仍委托真实
`super.discoverServicesByAddress`）。

平台覆盖（显式声明，不用「任意平台都过」的断言掩盖未覆盖分支）：

- 用例 1 的挂起点在假适配器**内部**，而 `discoverServicesByAddress` 只在
  `Platform.isWindows` 下走可注入的 `_adapter` 分支：非 Windows 宿主**显式 skip**
  并写明原因，由 `flutter-dev-checks.yml` 的 windows 作业执行。
- 用例 2/3 的挂起点在平台调用入口**之上**，双宿主都执行。
- 断言对象是**原始样本/摘要流**（`debugPrint` 行），不是对象字段：行前缀、行序、
  摘要块内容与数值池三处都必须成立。

---

## 7. R07 变异反证（执行期）

评审原文要求：「Real BluetoothService plus fake-adapter tests replace the former
fake-only proof. The comment claiming removal discrimination is not an executed
mutation record; supply a bounded countercheck with the development batch.」

一次运行期反证由两部分构成：

1. **包内正对照**（随测试一起提交，永久可复跑）：上表最后一条用例在**同一交错**下
   不调用 `retire()`，证明未封存时确实产生越块、无归属的 SAMPLE 行——即被断言的那
   几行正是修复前后的差别所在。
2. **外部变异**（有界，隔离分支）：在 `dev/flutter/**` 的临时分支上删除真实外壳的
   `stats?.recordDiscover(...)` 上报点（`lib/services/bluetooth_service.dart`），
   期望新用例变红。变异体**不合并、不发布**，只作为「这些用例确实观测真实外壳上报
   路径」的凭据。

**执行记录（2026-09-18，开发自测，非验收）**：

- 基线：`b437cea`——R1c 两宿主 `analyze` + `tests` 全绿、`failed: 0`（§9.2），
  即变异体的父提交本身已验证。
- 变异体：`caaf01b`（隔离分支 `dev/flutter/p3-4-r07-mutation`，父提交 `b437cea`）：
  `lib/services/bluetooth_service.dart` **仅 -2 行**（两个成功路径上报点），其余字节
  与基线逐字一致。**不合并、不发布、不进入交付链**。
- 结果（run 35262020804，逐作业见 §9.4）：Windows 步骤 6 **失败**，381 passed /
  **5 failed**（3 个探针/正对应用例 + 2 个真实外壳用例）⇒ 判别力成立；Linux
  步骤 6 成功、0 failed ⇒ 该路径在 Linux 不可达，本变异的判别力**宿主受限**（原因
  与后续补强方向见 §9.4）。
- 变异分支保留在远端（`origin/dev/flutter/p3-4-r07-mutation`）供复核；实现侧不将其
  合并回 `dev/flutter/p3-4-link-stats`。

---

## 8. 开发自测入口移植

本分支原先缺失 main 上受审的 checks-only 输入，无法产出可绑定的开发自测证据。按
评审要求（「必须使用受审的 checks-only 工作流/诊断输入，并绑定新提交、SDK 与原始
输出；不得为了拿到新 runner 而静默合并无关的 main 或 P3-8 产品改动」），本轮从
`main` `2d81a4b` 逐 blob 移植且**仅**移植：

| 文件 | blob |
|---|---|
| `.github/workflows/flutter-dev-checks.yml` | `66016dcfdc1e6046a391efdd82a4c489b9f20fb9` |
| `Tools/flutter/dev_checks.py` | `a2e48019399978dea1ee5b452dbdde119cda5ac6` |
| `tests/ota/test_flutter_dev_checks.py` | `d5687470dc835eb015c8a881f525e62a3d53137a` |
| `.github/workflows/build.yml` | 仅增加两处 `retention-days: 14`（与 main 一致） |

未移植 `Tools/provenance/manifest_profiles.json` 的 artifact 条目与
`artifact-maintenance*`：它们属于独立的 CI-ARTIFACT-01 治理特性，其中 profile 条目
会引用本分支不存在的 workflow。

移植后的宿主回归本地执行结果：

- `python -X utf8 -S -B -m pytest tests/ota/test_flutter_dev_checks.py`：先出现 1 项
  失败（`build.yml` 的 APK 上传步骤缺 `retention-days: 14`），补齐后 **62/62 OK**。
- 另有 1 项在本机失败但**非产品缺陷**：`git hash-object --no-filters --stdin-paths`
  在 worktree 内对 `…generated_plugins.cmake` 报 `Filename too long`（实测绝对路径
  262 字符 > MAX_PATH）。加 `-c core.longpaths=true` 后通过。这是本机长路径限制
  （worktree 深度所致），CI runner 工作区短，不受影响；记录为环境局限，不改产品代码。

---

## 9. CI 证据（开发自测，非验收）

> **证据与工作树的对应关系**：下列 R1c/R2/R3 的**被测提交是 `b437cea`**（source-bound：
> runner 自报的 `commit` 字段与本地 `git rev-parse HEAD` 逐字一致）。本文件所在的
> 文档提交在该提交**之后**，只增加本记录、不触碰任何源码字节；
> `git diff --stat b437cea..e906556 -- app/` 为空，被测源码树逐字节不变，故上表结论继续
> 适用于当前分支顶端。
>
> **该文档提交的 push（run 35263914189）没有产生任何 CI 证据**：两个作业均在
> `started_at 2026-09-17T19:16:38Z → completed_at 19:16:40Z`（约 2 秒）内失败，
> `steps` 数为 0，作业日志取回为 `BlobNotFound`。注解原文：
> `The job was not started because recent account payments have failed or your spending
> limit needs to be increased.`（详见 §12 的账号计费阻断）。因此该 run **既不是**
> 本文档早先预估的「配额导致的红」，也**不进入**任何证据链；上表 R1c/R2/R3 的结论
> 来自它们各自已完成的实际运行，不受此影响。

| 编号 | 目的 | 提交 | run URL | 结论 |
|---|---|---|---|---|
| R1 | checks-only 对照（source-bound 全量 analyze + test） | `e2f6560` | run 35257955951 | **红（失败，未通过）**：23 项测试失败 + 1 项 analyzer info，根因见下 |
| R1b | 同目标复测（修 R1 三项缺陷后，checks-only） | `59e7641` | run 35260571963 | **红（失败，未通过）**：analyze 转绿，剩 1 项测试失败（封存用例断言过强，测试缺陷），另有上传配额环境阻断；见 R1b 段 |
| R1c | 修 R1b 单项失败后复测（checks-only） | `b437cea` | run 35261398648 | **开发自测全绿**：两宿主 analyze + tests 均 0 失败；整轮结论红，**唯一**原因是日志上传配额（环境阻断），非产品缺陷；见 9.2 |
| R2 | 同提交 source-bound Android debug APK | `b437cea` | run 35261942487 | **构建/校验全绿**（`apk_build`/`apk_verify`/`apk_collect` PASS，`apk_result: PASS`）；APK 产物**未发布**（同一配额阻断）；见 9.3 |
| R3 | 外部变异反证（期望红，隔离分支 `dev/flutter/p3-4-r07-mutation`） | `caaf01b`（父 `b437cea`） | run 35262020804 | **已红**：Windows 检出 5 项失败，Linux 未检出（路径不可达，见 §7 / 9.4） |

### 9.1 R1b（`59e7641`，run 35260571963）：红，1 项测试失败 + 上传配额环境阻断

SDK 身份（两作业一致，取自 `sdk_version`）：Flutter `3.47.4` stable，
frameworkRevision `9584c6713b324636289d067944a46fd6b49df14b`，Dart SDK `3.13.3`，
engine `06a2e2a110089dff50fe635cffd2a61e1b24fbcd`；scope `all`（`FLUTTER_DEV_TEST_SCOPE=all`），
`FLUTTER_DEV_BUILD_APK=false`，`TRACE_DEV_APP_ID_SUFFIX` 与 device-observation 输入均为空。

| 作业 | 作业 id | sdk_checkout / sdk_version / dependencies | analyze | tests |
|---|---|---|---|---|
| Linux (ubuntu-latest) | 105334953653 | PASS / PASS / PASS | PASS（15.4s，`No issues found!`） | **FAIL**：377 passed / 8 skipped / **1 failed** |
| Windows (windows-2022) | 105334953334 | PASS / PASS / PASS | PASS | **FAIL**：385 passed / 0 skipped / **1 failed** |

两侧 `development_result: FAIL`、`apk_result: NOT_REQUESTED`、`diagnostics_complete: true`；
Linux 的 8 项 skip 即 §6 声明的 Windows-only 用例（在 Windows 作业里实际执行并通过，
385 = 377 + 8）。

唯一失败用例（两作业同名）：
`test/ota/ota_link_stats_test.dart` → `P34-DA01 到达时刻 / P34-DA03 观测流封存` →
`封存：迟到观测走 OTA_LINK_LATE，样本流停止且不入数值池（DA03）`。

根因：**测试断言过强，不是实现缺陷**。该用例在封存**之前**先做了一次合法
`recordDiscover`，那会产生一条 SAMPLE 行；而断言写成「封存后 SAMPLE 行集合为空」，
把这条**应当保留**的合法样本也一并否掉了——与 DA03「保留有效样本、不得为改善统计而
静默删除」的要求相反。修法：封存前记下样本基线，封存后断言样本数**不变**，并断言
最后一条 SAMPLE 行早于 RETIRE 行（即封存后新增的行只能是自带 `label`/`attempt` 的
LATE）。封存闸门（§4.1）本身无缺陷：同一轮新增的闸门用例、探针用例与正对照全部通过。

**对 R1 根因覆盖面的更正**：R1 的失败清单被日志采集截断（“… and 19 more”），当时把
失败全集推定为由三项根因覆盖；R1b 证明该推定**不完整**——本项是第 4 类缺陷，三项修复
并未覆盖它。R1 的「23 项」仍只作修复范围依据，不作为已验证事实。

**环境阻断（如实记录，不记为成功）**：两个作业的 `Upload development logs
(not acceptance evidence)` 步骤均失败——
`Failed to CreateArtifact: Artifact storage quota has been hit. Unable to upload any
new artifacts.`（账号产物存储配额耗尽）。因此本轮**没有任何产物包可下载**，上表逐条
观测全部取自作业原始 stdout（`gh run view --repo Eitan-S-23/E-Track --job <id> --log`），
并已落盘为本地日志副本（`.cache/tmp-p34/r1b-linux.log` / `r1b-win.log`，位于独占
worktree 内）。上传失败按环境阻断记录，**不**因 `diagnostics_complete: true` 或步骤名
含 PASS 而改写为成功。

### 9.2 R1c（`b437cea`，run 35261398648）：两宿主开发自测全绿，整轮红仅因上传配额

SDK 身份与 R1b 一致（Flutter `3.47.4` stable / Dart `3.13.3` / engine
`06a2e2a110089dff50fe635cffd2a61e1b24fbcd`），scope `all`，
`FLUTTER_DEV_BUILD_APK=false`。

| 作业 | 作业 id | analyze | tests | development_result |
|---|---|---|---|---|
| Linux (ubuntu-latest) | 105337741447 | PASS（`exit=0`） | **PASS**：378 passed / 8 skipped / **0 failed** | PASS |
| Windows (windows-2022) | 105337741654 | PASS（`exit=0`） | **PASS**：386 passed / 0 skipped / **0 failed** | PASS |

- 这是本批**开发自测通过**的直接证据：`analyze: PASS (exit=0)`、`tests: PASS (exit=0)`，
  两宿主 `failed: 0`；`commit` 字段为 `b437cea2b940ea0fd94aaa5b67d635f9e59df333`，
  与本地 `git rev-parse HEAD` 逐字一致（source-bound）。
- 整轮 `conclusion: failure`，但失败步骤**只有** `Upload development logs
  (not acceptance evidence)`：`Failed to CreateArtifact: Artifact storage quota has
  been hit.`（步骤 7）。步骤 6 `Analyze, test and optionally build a debug APK`
  两宿主均成功，未出现在失败步骤列表中。
- 按评审「Keep upload failure strict」：上传失败保持严格、不降级为
  `continue-on-error`，因此整轮结论仍为红；该红是**环境阻断**（账号产物存储配额
  耗尽），不是产品缺陷，也**不得**据此写成「绿运行」。
- 因产物包不可下载，本轮全部观测取自作业原始 stdout（job 105337741447 /
  105337741654），已落盘为独占 worktree 内
  `.cache/tmp-p34/r1c-105337741447.log`、`.cache/tmp-p34/r1c-105337741654.log`。

### 9.3 R2（`b437cea`，run 35261942487）：source-bound debug APK 构建与校验全绿，产物未发布

| 作业 | 作业 id | analyze | tests | APK |
|---|---|---|---|---|
| Linux (ubuntu-latest) | 105339577804 | PASS | PASS：378 / 8 / 0 | `apk_prepare`/`apk_java`/`apk_sdk`/`apk_wrapper`/`apk_build`/`apk_verify`/`apk_collect` 全 PASS；`apk_result: PASS` |
| Windows (windows-2022) | 105339578099 | PASS | PASS：386 / 0 / 0 | `apk_result: NOT_REQUESTED`（APK 仅在 Linux 构建） |

APK 身份（runner 自报 `DEV_LOG[apk_collect]` 单行 JSON，取自作业原始 stdout）：

```text
{"artifact_kind":"development-debug-apk","formal_acceptance":"NOT_RUN",
 "commit":"b437cea2b940ea0fd94aaa5b67d635f9e59df333",
 "sha256":"a909676dc6731a45196985f6ddb6459e726f0be07e2a46e5898bb412b797cf1e",
 "bytes":131563134,"file":"trace-dev-debug.apk","release_signing":false,
 "application_id":"com.wen.gaia.gaia"}
```

- 该 JSON 自带 `formal_acceptance: NOT_RUN` 与 `release_signing: false`：这是**开发
  自测用 debug APK**，不是发布产物，也不构成独立验收。
- **产物未发布**：`Upload debug APK (not a release)` 步骤被跳过（前序
  `Upload development logs` 因配额失败）。因此本轮**没有可下载的 APK**，只有
  runner 记录的哈希与字节数；「构建通过」不能被读成「产物已归档」。
- 未安装、未清数据、未做任何设备侧操作。

### 9.4 R3（变异体 `caaf01b`，父提交 `b437cea`，run 35262020804）：期望红，Windows 检出 5 项

| 宿主 | 作业 id | tests | 步骤 6 | 结论 |
|---|---|---|---|---|
| Windows (windows-2022) | 105339840169 | 381 passed / 0 skipped / **5 failed** | **失败** | **检出变异** |
| Linux (ubuntu-latest) | 105339840397 | 378 passed / 8 skipped / 0 failed | 成功 | 未检出（路径不可达，见下） |

Windows 失败用例（5/5）：

1. `ota_link_stats_shell_test.dart` → `discoverServicesByAddress 外壳：成功与失败尝试都计入 calls/errors`
2. `ota_link_stats_shell_test.dart` → `findExact 外壳：发现计时/成败/写模式 + stats 透传到内部服务发现`
3. `ota_probe_late_attribution_test.dart` → `假适配器挂起第 1 轮发现：封存 → 第 2 轮完成 → 放行，迟到观测显式归因`
4. `ota_probe_late_attribution_test.dart` → `挂起点在平台调用入口之上（双宿主）：迟到发现同样显式归因`
5. `ota_probe_late_attribution_test.dart` → `正对照：不封存同一交错会产生越块样本行（本文件鉴别力的凭据）`

**Linux 未检出的原因（如实记录，不掩饰）**：被删的两个上报点位于
`discoverServicesByAddress` 的**成功分支**内，其中可注入假适配器的那一支由
`Platform.isWindows` 门控（§6 已声明该平台覆盖边界）；Linux 上该函数只会走
「未找到设备 → 抛 `UnsupportedError`」，即 **catch 分支**——而 catch 分支的
`recordDiscover(error: true)` **故意不在本轮变异范围内**（有界变异只删成功路径两行，
见 §7）。因此该变异体在当前用例集下的鉴别力是**宿主受限**的：Windows 直接判定，
Linux 无判别力。这既不能被读成「两宿主都验证过」，也不表示变异无效；若要在 Linux
侧取得同等判别力，需要补一个能触达成功路径的注入点（属新任务，不在本卡范围）。

R1 失败根因（同一批次内一次修完，按执行合同 §7.3 集中处理，不逐错重开）：

1. **END OK 去向错误的 fail-closed**（`lib/ota/ota_ble_transport.dart`）：终点归因在
   `waiter.arrivalUs == null` 时无条件抛 `ACK_MALFORMED`，而**未绑定观测**（`stats == null`）
   的构造根本不带到达戳——测试文件里 91 处 `OtaBleTransport(` 仅 13 处传 `stats:`，
   于是所有未绑定的成功传输全部失败。改为只在**绑定观测却拿不到到达戳**时 fail closed
   （那是真异常），未绑定时传输语义与插桩前逐字一致。
2. **analyzer `await_only_futures`**（`test/ota/ota_probe_late_attribution_test.dart`）：
   `await holdEntered;` 对 `Future<void> Function()` 取 await 是无效 await，strict analyze
   判 info → 步骤失败。改为 `await holdEntered();`。
3. **续传用例闸门超时**（`test/ota/ota_ble_transport_test.dart`）：`_pumpUntil` 用零延迟
   让出（无真实时间）轮询，而「ABORT + BEGIN 续传」需要真实重传超时才会到达同步点。
   为 `_pumpUntil` 增加显式 `tick`（默认 `Duration.zero` 保持原语义），该用例改传
   `tick: 5ms`、并对齐既有已通过兄弟用例的参数（`retries: 1`、`ackTimeout: 200ms`、
   `ackDelay: 1ms`）。超时仍以 `fail(reason)` 报红，不会挂死。

R1 的 23 项失败中，日志采集流（`DEV_LOG[tests]`）把失败清单截断为 4 条 + “… and 19 more”，
故失败全集由四条可见用例名、逐文件通过计数与上述 `stats` 绑定统计共同推定；该推定不
写作「已验证」，只作为修复范围依据。

回填时同时记录：被测提交 SHA、SDK 身份（Flutter/Dart 版本）、实际 scope、逐作业
结论、原始日志与产物清单。**上传配额失败一律记为环境阻断，不记为成功**；产物缺失
不得用「步骤 PASS」代替。

---

## 10. 参考包（1 MiB 完整合法 `.etu`）：技术可行性与裁定请求

### 10.1 要求原文

`OTA-XC-BLE-TUNING`（`docs/ota-cross-system-contracts.md:1055`）：

> `referencePackageBytes=1048576`，表示 BLE 实际传输的完整合法 `.etu` `total_len`，
> 不是解包后的 `image_len`。

同一节 :1044 同时规定：「包大小指完整合法 `.etu`，**不能追加无意义填充**绕过解析或
把小 toy 结果冒充参考包成绩」。即：**既不能补零凑数，也不能用小包冒充**。

### 10.2 实测结论：在冻结规格下不可达

编码链（`Tools/etu_pack.py`，`cmd_pack_full` :295-317）：

```text
plaintext = lzma_alone_encode(app, dict_size=args.lzma_dict)   # 默认 16KB 字典
payload   = aes_ctr_xcrypt(key, nonce, plaintext, encrypt=True) # CTR 流密码，长度不变
etu       = hdr(64B) + payload
约束      len(app) <= MAX_IMAGE_LEN = 0xF0000 = 983040
```

本机以仓库自身的 `lzma_alone_encode` 实测（脚本 `.cache/tmp-p34/measure_lzma_ceiling.py`，
纯内存、不生成任何 `.etu`；因本机缺 `pycryptodome`，加载打包器时仅把
`from Crypto.*` 两行替换为桩，其余源码原样执行）：

```text
MAX_IMAGE_LEN=983040  ETU_HEADER_LEN=64  REQUIRED_TOTAL=1048576
零膨胀下界: 64 + 983040 = 983104 (缺口 65472 字节)
若要凑满 1 MiB，编码链必须膨胀 6.66%

sha256-keystream   payload=  996500 total=  996564 ratio=1.013692 缺口=52012
random-seeded      payload=  996414 total=  996478 ratio=1.013605 缺口=52098
0xff-fill          payload=     209 total=     273 ratio=0.000213 缺口=1048303

实测最大 total=996564，距 1048576 缺口 52012 字节
```

即：**即使取 960 KiB 上限的、完全不可压缩的镜像，容器总长也只到 ≈996.6 KiB，仍差
52,012 字节（≈50.8 KiB）**。要凑满 1 MiB，编码链必须膨胀 **6.66%**，而实测不可压缩
输入的最坏膨胀只有 **1.37%**——相差约 5 倍，且真实 GCC App 镜像是可压缩的（真实全量
包实测 281,051–281,291 字节），只会更小。

补充事实：

- `Tools/etu_pack.py` 的 CLI **没有目标大小/填充选项**（argparse :366-390；源码核对
  `--pad` / `target-size` 均不存在），`check_limits`（:267）只有上限、没有下限，因此
  「合法但偏小」是被允许的，问题只在「凑不到 1 MiB」。
- 差集分析：`image_len` 上限 983,040 与候选/备份净容量 0xFF000 = 1,044,480 之间有
  61,440 字节余量，但把镜像放到 1,034,384 字节（按实测 1.0137 膨胀比反推才可能凑到
  1 MiB）会突破 960 KiB 镜像上限，且编码后逼近分区净容量——这已是**分区/布局级**改动。
- 1,048,576 这个数字在契约中另有一处来源：`XC-RELEASE-REHEARSAL-GOLDEN` 的
  canonical 资产向量（full `1048576` / patch `524288` / recovery `1048584`，:1302），
  那是发布流水线的合成 rehearsal 夹具值，与打包链可达长度无关。
- patch 类型的容器上限是 1.5 MiB，尺寸封顶本身不排除某个病态 patch 达到 1 MiB；但
  要求文本是「**完整**合法 `.etu`」，且 patch 是 Δ、需要已核定的基线镜像，不是同一
  语义。实现侧不主张用 patch 替代参考包。
- 本机 Python 缺 `pycryptodome`（`Tools/etu_pack.py` 直接 `raise`），因此**本机当前
  无法制备任何 .etu**；安装第三方依赖属于新的环境变更，未在未授权情况下执行。

### 10.3 请用户裁定（实现侧不自行改契约）

`PLAN-OTA.md` 与 `docs/ota-binary-contracts.md` 是冻结契约，发现不可实现应登记并停止
而非就地修改。实现侧据此提出三个候选，请用户选择其一：

1. **把 `referencePackageBytes` 改为「随参考包冻结的真实 `total_len`」**（推荐）。
   门槛公式 `effectiveThroughputKiBps = referencePackageBytes / 1024 / elapsedSeconds`
   不变，只把常量换成实测值——例如先交付一个真实、已校验、有上板资格的包，其
   `total_len` 即为参考值；或写成「≤1048576 的完整合法 `.etu`，取该包实测长度」。
   需升版本重新审批该条。
2. **在契约中显式定义合法填充**并说明 boot/解析器如何接受（当前 :1044 明确禁止
   「无意义填充」，需同步改写）。风险最高：填充会牵动 CRC/身份字段与解析口径，
   并可能被误读为「凑数通过」。
3. **调整镜像上限/分区布局**（把 0xF0000 抬到 ≈1,034,384 以上并重算净容量）。属于
   布局级变更，影响的验收面远大于 P3-4 本身。

在裁定之前，整卡性能验收的参考包前置项保持**未满足**，实现侧不以补零、不以待测
小包替代，也不把 toy 结果写成参考包成绩。

---

## 11. MCU 波特率测量 / AT 控制与恢复方案（有界提案）

依据：`Doc/ble.pdf`（XY-MBO35A V0.0.5，2025-09-10，670,885 B，SHA-256
`35f71dae4c4a3f7c8d050f678397781be5c7ccfe53fdb64306c0a6b460e8a21a`，
复核方已核对该文件）与现场源码。

### 11.1 现状与硬约束

- `USER/HAL/HAL_Bluetooth.cpp:332` `BT_SERIAL.begin(115200)`；`:377` 的
  `BT_SetName()` 是**只发不等**的 `AT+NAME=XTrace\r\n`，不做应答解析；`:405` 的
  `X-Trace\r\n` 周期保活会在 OTA 会话进行中被抑制。
- `USER/HAL/HAL_Config.h:92` `CONFIG_BT_SERIAL Serial`、`:93` `CONFIG_BT_USE_TRANSPARENT 0`
  ⇒ AT 与 OTA 数据共用同一路 UART，**没有主机旁路通道**；手册也明确 FFF2 是把数据
  透传给 MCU，**不得把 AT 文本写进 OTA BLE 通道并假定它配置了模块**。
- 手册声明的 `AT+UART?` / `AT+UART=NUM`（5=115200 … 8=921600）是**声明**，不是实测；
  且其查询表只列 0–5、设置表列 0–8，改动生效时刻与 OK 应答速率**未在文档中定义**。
- 手册要求主机在 `+READY\r\n` 之后才发命令或数据（PDF p9）。

**推论（决定了方案形状）**：改模块波特率必须**两端同时**改。只从主机侧发 AT 会把
MCU 与模块拆到不同速率，MCU 再也无法与模块通信——这不是可回退的单边操作，而是
**必须用新固件才能恢复的固件参数实验**。

### 11.2 有界提案（实验专用，不改生产协议）

1. **先基线，后调参**：在**当前 115200** 下先完成参考包基线测量（含发现、GATT 写、
   ACK 等待、durable 推进的分段数据）。无基线不进入改速。测量前按既有防坑清单执行
   `复位 → gpsreset → livemap` 式三连（语义对应到本链路即：复位设备、确认 OTA 会话
   空闲、确认身份版本）。
2. **实验固件**：为每个候选速率（230400 / 460800 / 921600）各构建一个**实验构建**，
   把 `BT_SERIAL.begin(<rate>)` 与该速率的模块配置动作绑定；改动**不进入生产构建**，
   以编译期开关隔离，不新增生产后门、不改协议、不改引脚/流控。
3. **模块配置与回读**：在 MCU 侧按手册发 `AT+UART=<n>\r\n`，按 `+READY\r\n` 或
   `AT+UART?\r\n` **回读实测**确认生效（不采信文档对生效时刻的沉默）；同时记录
   「设置命令的 OK 用旧速率还是新速率」这一实测事实。每次改速前绑定模块版本
   （`AT+VER?`）与 MAC（`AT+MAC?`），OTA 会话必须空闲。
4. **恢复链（必须预先具备，而不是出事后再想）**：模块速率存于其 NVM，MCU 固件回滚
   并不能让两者重新对齐。因此：
   - 为每个候选速率**预置一份同速率恢复构建**（能与模块对话的最小构建）；
   - 恢复顺序：烧同速率恢复构建 → 发 `AT+UART=5` → `AT+REBOOT=1` → `AT+UART?` 回读
     确认 115200 → 烧回基线生产固件；
   - **`AT+RESET=1` 工厂复位不作为默认恢复动作**（它改变无关配置，且不恢复被改 MAC，
     不是完整身份还原）；不得用复位 MAC/UUID 去猜修。
   - 模块与 MCU 速率失配时的兜底是 J-Link 烧录（沿用本仓库既有 J-Link 流程），
     全程不经 OTA 通道。
5. **单变量与配额**：同一轮只变 baud，MTU / timeout / retry / 前后台状态 / 包 SHA 与
   长度 / 设备 全部冻结；不同参数组合另立输入组，不拼接不同组的最好结果。每轮记录
   已用/剩余设备观测配额，超配额即停，不盲重试。
6. **门槛与结论**：`OTA-XC-BLE-TUNING` 的 P95 ≤120s、单轮 ≤150s、≥9 KiB/s、重传率
   ≤1%、30/30 连续成功、4h soak、重连恢复 10/10 均由验收方按合同判定；实现侧只提供
   观测与原始数据，不预告提速倍数、不承诺任何倍率。
7. **硬件流控**：RTS/CTS 引脚保持接地，任何构型都不得启用 UART 硬件流控。

该提案是**操作单草案**，需要验收方在其硬件合同里写死地址/命令/超时/恢复/配额后才
执行；本轮未执行任何 AT、未连接设备。

---

## 12. 未做与不做的事

- 未连接手机/MCU、未发任何 AT、未 J-Link 挂载或烧录、未安装 APK、未清数据、未执行
  OTA 传输、未做 release/deploy、未删除任何远端产物。
- 未修改 `PLAN-OTA.md`、`docs/ota-binary-contracts.md`、`docs/ota-cross-system-contracts.md`
  等冻结契约；§10 只提裁定请求。
- **CI 产物发布被环境阻断（记为未完成，不记为成功）**：本轮三个 run（R1c/R2/R3）
  的 `Upload development logs` 步骤全部因**账号产物存储配额耗尽**失败
  （`Failed to CreateArtifact: Artifact storage quota has been hit`），APK 上传
  步骤随之被跳过；因此**没有可下载的日志或 APK 产物**，全部证据取自 runner 原始
  stdout（本地落盘副本见 §9）。实现侧未清理、未删除任何既有远端产物，也未绕过
  或弱化该失败（`continue-on-error` 一律未使用）。
- **账号计费阻断（更硬的阻断，2026-09-17T19:16Z 起观测）**：除上述配额问题外，账号
  已进入「近期付款失败 / 需提高支出上限」状态，**任何新的作业都不会启动**。实测样本：
  run 35263914189（文档提交 `e906556`）两作业 `steps` 数 0、约 2 秒即失败，注解为
  `The job was not started because recent account payments have failed or your spending
  limit needs to be increased.`；作业日志 `BlobNotFound`。这意味着**在本项恢复前，
  实现侧无法再取得任何新的 CI 证据**（既非产品缺陷、也非 harness 缺陷，属
  `ENV_BLOCKED`）。该阻断不影响 §9 表中 R1c/R2/R3 已完成运行的有效性。
- 未改动 `P3-4-parser-v1` 的任何冻结证据、证据包或其核验器。
- 未修改主 worktree 的看板/记录/评审证据目录（`.cache/p3-4-parser-review-20260917/`、
  `.cache/p3-4-parser-rereview-20260917/`、`.cache/p3-4-parser-pr2-followup-20260917/`
  一律只读）。
- 本文件只写在独占验证 worktree 内；需要主会话回写的内容见 §13。

## 13. 主会话回写清单

1. `PLAN-OTA-EXEC.md`：P3-4 卡登记本轮整改（DA01–DA03 + 测试 + 参考包可行性），
   状态保持「进行中」；整卡设备验收仍 `NOT_RUN`，不得置「完成」。
2. 看板 §9 变更登记表：登记「`referencePackageBytes=1048576` 在冻结规格下不可达」
   的实测结论与 §10.3 的三选一裁定请求（**登记请求，不就地改契约**）。
3. 待用户裁定后再决定是否升版本、改合同条目与冻结流程。
4. 开发自测证据（§9）：R1c 两宿主 `analyze` + `tests` 全绿（`b437cea`）、R2 debug
   APK 构建/校验全绿但**产物未发布**、R3 变异反证在 Windows 检出 5 项（Linux 无
   判别力）。三个 run 的整轮结论均为红，原因**只有**账号产物存储配额耗尽这一环境
   阻断（上传步骤失败、APK 上传被跳过）。看板登记时须同时写明：本轮**无产物包可
   下载**，证据取自带 job id 的原始 stdout；P3-4 仍**不得**据此置「完成」。
5. 远端新增隔离分支 `dev/flutter/p3-4-r07-mutation`（变异体 `caaf01b`）：仅供复核的
   反证材料，**不得合并、不得发布**；如需清理该分支，请先明示再由主会话处理。
6. **账号计费阻断需主会话知悉并转达用户**：自 run 35263914189（2026-09-17T19:16Z）
   起新作业一概不启动（注解为付款失败/支出上限；`steps` 0，日志 `BlobNotFound`）。
   在本项恢复前，实现侧**无法**再产生任何新的开发自测证据，请勿把后续 dispatch 的
   快速红误读为实现侧回归；这属于环境阻断，需用户侧处理 Billing 后才能继续。
