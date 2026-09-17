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
  ——**自带归属**，不再进入任何数值池（`discovers.calls` 等计数保持封存时刻的值）。
- 摘要新增 `'retired': {'reason': <r>, 'us': <n>}`；未封存实例该字段为 `null`。
- 调用点：`ota_service.dart:1759`，仅在「本轮未获判定」（`outcome == null`）时封存，
  原因三分：`outer-timeout`（外层预算放弃）、`cancelled`（取消代次变化）、
  `no-verdict`（其余无结论）。取得结论的轮次（completed / identityChanged / timedOut）
  不封存——该路径上所有 await 都已返回、平台调用无在飞工作，观测流自然排空。

**被放弃的工作留痕，不静默删样本**：封存**之前**已产生的合法样本原样保留在流里，
该轮摘要以 `retired` + `attempts[].outcome='abandoned'` 记明其状态；封存**之后**的
观测一条不丢，只是换成带 `attempt=` 的 LATE 行。实现中不存在「删除观测以改善
统计」的分支。

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
| 同上 | 封存：迟到观测走 `OTA_LINK_LATE`，样本流停止且不入数值池（DA03） | 原始行前缀、行序、`discovers.calls` 不增长 |
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

执行记录（提交 SHA、run URL、逐作业结论）见 §9。

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

| 编号 | 目的 | 提交 | run URL | 结论 |
|---|---|---|---|---|
| R1 | checks-only 对照（source-bound 全量 analyze + test） | 待回填 | 待回填 | 待回填 |
| R2 | 同提交 source-bound Android debug APK | 待回填 | 待回填 | 待回填 |
| R3 | 外部变异反证（期望红） | 待回填 | 待回填 | 待回填 |

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
