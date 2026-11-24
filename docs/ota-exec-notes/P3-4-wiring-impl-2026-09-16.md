# P3-4 链路观测接线实施记录（2026-09-16）

> 本文是 `P3-4-research-link-timing-2026-09-16.md` §9 验证入口的实施留痕：
> 接线 diff、五轮开发自测 CI、修复链与最终证据。设备实测、AT 改速、
> 正式验收均 NOT_RUN（待授权），本文不含任何未执行的测量结果。
>
> 输入基线：`9f67314`（main）；分支：`dev/flutter/p3-4-link-stats`
> （项目内独占 worktree `.cache/worktrees/p3-4-link-stats`，预授权范围）。

## 1. 提交链（五轮红->绿）

| 提交 | 内容 | CI run | 结论 |
|---|---|---|---|
| `b23ce5d` | feat: OtaLinkStats + 全链接线 + 22 项单元/接线测试 | 35029310741 | 红（analyze 11 错） |
| `1ba6460` | fix: 8 处条件级联可空调用 + `0b101` 二进制字面量 | 35030153403 | 红（6 测试失败） |
| `03b509d` | fix: emitSummary JSON 化、fake 零延迟 ACK 抢跑、acks 键位 | 35032091035 | 绿（双宿主） |
| `edf8f92` | test: 补 service 层接线断言 | 35033196516 | 红（mtuRequested=0） |
| `1256e2f` | fix: fake override 内对齐外壳 stats 上报语义 | 35034258547 | **绿（双宿主，最终）** |

最终绿：run
<https://github.com/Eitan-S-23/E-Track/actions/runs/35034258547>，
提交 `1256e2f7585f8358f2414f3ad8a4610580e62822`。

## 2. 接线内容（相对基线 9f67314 的 9 文件）

- `lib/ota/ota_link_stats.dart`（新增）：单绑定实例纯观测收集器。
  ACK 延迟样本按冻结定义（首发完整发送结束 → 首个有效确认到达）；
  nearest-rank P99（ceil(q*N) 不插值）；fail-closed 完整性
  `complete`/`partial:missing=N`；六类 ACK 分类计数；绑定阶段幂等；
  `OTA_LINK_SAMPLE` 流式行 + `OTA_LINK_STATS {json}` 幂等摘要
  （jsonEncode 规范单行 JSON）。
- `lib/ota/ota_ble_transport.dart`：发送循环 `recordSegmentSendEnd`
  （唯一段标识 = `blockStart + seg*128` 字节偏移）；onAck 确认集合快照
  （ACK 自身段 + durable 前移回收段 + bitmap 置位段）经
  `recordAckConfirm`；六类分类经 `recordAckClass`；durable 推进经
  `recordDurableAdvance`；`stats==null` 零行为差异。
- `lib/services/bluetooth_service.dart`：带计时外壳（requestOtaMtu/
  subscribeOtaNotifyByAddress/writeOtaCharacteristicByAddress 等）在
  stats 非 null 时 Stopwatch 计时并上报（MTU 协商结果、订阅、GATT 写
  时长/字节/错误、平台写、服务发现）。
- `lib/services/ota_service.dart`：upgrade（`phaseStart('bind')` →
  绑定 → `phaseEnd('bind')`，transfer 生命周期）与 probe 路径建独立
  stats 实例并 emitSummary；readDeviceInfo 高频路径有意不建 stats。
- 测试 4 文件：`ota_link_stats_test.dart`（22 项纯单元）、
  `ota_ble_transport_test.dart`（4 项接线 + `_McuSim` fake 扩展
  ackDelay/丢 ACK/重复 ACK）、`ota_service_upgrade_test.dart`（service
  接线断言：bind 字段/phase 成对/gattWrites 计数/probe 独立摘要）、
  `ota_service_session_test.dart`（签名同步）。

## 3. 五轮修复的技术结论（防复发）

1. **条件级联可空调用**：`cond ? null : Stopwatch()..start()` 解析为对
   整个条件表达式级联，接收者可空 → 必须写
   `cond ? null : (Stopwatch()..start())`（9 处，analyzer 报 11 错）。
2. **Dart 无二进制字面量**：`0b101` 解析为 `0` + 标识符 `b101`，用
   `0x05`。
3. **摘要必须 jsonEncode**：`Map.toString()` 键无引号，采集侧无法解析。
4. **fake 零延迟 ACK 抢跑（原结论已按预审 P34-R01 撤回）**：`ackDelay=0`
   的同步 fake 中，DATA ACK 的流监听微任务先于发送循环
   `recordSegmentSendEnd` 的 continuation 执行，确认到达时首发未登记 →
   样本系统性缺失，并影响后续段的确认回收。当时的处置是"测试 fake 用
   `ackDelay: 1ms` 还原真实时序、产品代码不改"，并据此写下"真机 ACK 至少
   一个连接间隔后到达，无此竞争"。**该结论不成立**：链路物理延迟不等于
   Dart 侧写完成通知必先执行，同一事件循环内"写完成 continuation"与
   "通知分发"的先后没有平台保证——零延迟确认是必须显式处理的观测场景，
   不是 fake 的伪影。整改见 §8（R01）：不再用延迟掩盖，改为把早到确认
   显式记为无效观测（`ackEarlyInvalid` 计数 + `ack_early_invalid` 流式行）
   并进入完整性缺口；1ms 延迟用例保留为正向接线用例，不再是该竞态的唯一
   处理方式。
5. **fake 覆写带计时外壳的旁路**：`_UpgradeFakeBle extends
   BluetoothService` 只能覆写公开外壳（私有方法库私有不可覆写），
   外壳内 stats 上报被整体旁路（mtuRequested=0）。修复：fake 的三个
   override 内对齐外壳语义手动上报（durationUs: 0；error 版在
   rethrow 前）。语义对齐已对照外壳源码逐字段核对
   （chunkBytes=协商返回值、ok=stream!=null、error+rethrow）。

## 4. 最终 CI 证据（run 35034258547）

- Ubuntu（artifact `flutter-dev-ubuntu-latest-35034258547-1`）：
  `development_result=PASS`、`scope=all`、analyze 零问题（12.7s）、
  tests `+348 ~7`（348 通过 7 skip，113.45s）、SDK stable、
  lockfile unchanged、toolchain_regen 3 文件已绑定恢复；OTA_LINK_
  观测行 828 条。
- Windows（artifact `flutter-dev-windows-2022-35034258547-1`）：
  `development_result=PASS`、analyze 零问题（16.5s）、tests `+355`
  （355 通过，113.59s）、OTA_LINK_ 观测行 849 条。
- 新增 service 接线测试 `P3-4 链路观测 service 接线：upgrade/probe
  摘要含绑定与传输字段` 双宿主均通过。
- `formal_acceptance=NOT_RUN`、`apk_requested=false`、
  `apk_result=NOT_REQUESTED`。**该 NOT_REQUESTED 只能解释为本次是
  checks-only 开发验证**：本批已修改 4 份产品 Dart 源码，它们本身就是
  APK/EXE 构建输入，原记录的"未改构建输入"表述不成立（预审 §7.4①）。
  未申请 App 构建不等于免除 App 构建门禁，正式构建需另按授权办理。
- 本地证据缓存：`.cache/ci-35034258547/`（双宿主 result.json 与
  logs/，小 artifact 直下避免整包 TLS 超时）。

## 5. 四类分离声明

| 类别 | 状态 |
|---|---|
| 源码编辑 | 完成：9 文件入 `dev/flutter/p3-4-link-stats`（最终 `1256e2f`） |
| 开发自测 | 完成：五轮 CI 链完整留痕，最终 run 35034258547 双宿主 PASS |
| APK/EXE 构建 | NOT_REQUESTED（**仅指本次是 checks-only 开发验证**；本批已改 4 份产品 Dart 源码即 APK/EXE 构建输入，"无构建输入变更"的表述按预审 §7.4① 撤回。未申请 ≠ 免除 App 构建门禁） |
| 独立验收 | NOT_RUN（由非实现会话按执行合同另行组织） |
| 设备实测（吞吐/AT） | NOT_RUN（操作单见 research §8，待授权） |

## 6. 待授权事项（不新增任何额度）

设备实验操作单（115200 基线测量 + 客户端热点分解，不含 AT 改速）已在
research §8 冻结草案；golden toy 与 1MiB 参考包的上板资格、MCU 侧 RTT
打点补强、连接参数实验纳入与否，均在授权裁定时一并决定。本批不执行
任何真机操作、烧录、AT 命令、安装卸载、发布部署或主干提交。

## 7. 非实现会话集中预审（Codex，2026-09-16）

### 7.1 阶段与结论

本节是执行合同 §7.3 的集中预审和正式验收准入核查，不是正式执行轮次。
上文 §1-§6 保留为原始交付记录；涉及完成程度、计时可信度和构建范围的
表述，以本节复核结论为准。

**本批暂不放行，P3-4 保持进行中，保留 Claude 的实现认领。**
开发自测双宿主 PASS 已独立核实，但仍有下表 7 项范围内阻断需要批量整改。
没有发现本批已审批冻结的 P3-4 版本化验收合同或 NOT_RUN 矩阵，未运行
`validate_bundle.py`，不生成虚构的 PRODUCT_FAIL/PASS 轮次或复用计划。
正式验收、APK/EXE 构建和设备实验不能由开发自测替代。

被审查对象：

- 基线 main：`9f67314700f2c796c66f56533b6db6166706353c`。
- 提交：`1256e2f7585f8358f2414f3ad8a4610580e62822`，分支
  `dev/flutter/p3-4-link-stats`。
- tree：`f95fc44353c6a6b34afff70fc7b470c06aa42fb6`；profile 配置 blob：
  `3769369d053aad028b67d7e2c17b5827b2b96f55`。这些是只读身份记录，
  不是合同冻结或审批。
- 项目内验证工作树 `.cache/worktrees/p3-4-link-stats` 的 Git 状态为空。
  相对 main 共 9 文件：4 份产品 Dart、4 份测试及 research 文档。
  主工作树对应 9 文件与该工作树的内容在 CRLF/LF 归一后全部一致；
  主工作树仍有原有脏文件，不可将其直接视为干净验收执行树。

### 7.2 已核实的开发证据

通过 GitHub CLI 的只读 API 核对 run 35034258547：workflow 为
`Flutter Development Checks`，event=`push`，attempt=1，head/ref 与上述
提交/分支一致，run 及 Ubuntu/Windows 两个任务均 `success`。
没有 dispatch、重跑 CI 或重新下载已有产物。

| 宿主 | analyze | 完整测试 | SDK | 原始 OTA_LINK_ 行 |
|---|---|---|---|---|
| Ubuntu | 零问题，退出码 0 | 348 通过、7 skip，退出码 0 | Flutter 3.47.4 / Dart 3.13.3 | 828 |
| Windows | 零问题，退出码 0 | 355 通过，退出码 0 | Flutter 3.47.4 / Dart 3.13.3 | 849 |

共同 Flutter revision：`9584c6713b324636289d067944a46fd6b49df14b`。
两份 result.json 均记录 `scope=all`、`development_result=PASS`、
`formal_acceptance=NOT_RUN`、`apk_requested=false` 和
`apk_result=NOT_REQUESTED`。锁文件未变；报告中的受控 toolchain_regen
及恢复记录保留，不把开发检查说成无输入改写的正式冻结执行。

本地原始 ZIP 与 GitHub API 返回的 artifact digest 完全相等：

| 本地 ZIP | GitHub artifact ID | 字节数 | SHA-256 |
|---|---|---|---|
| `.cache/ci-35034258547/ubuntu.zip` | 10422517128 | 34463 | `54fa9f7ac19ae9fd37e627dc891b41747762ef6939386e3077d38991cec53d7a` |
| `.cache/ci-35034258547/windows.zip` | 10422287862 | 34067 | `ddbbc6bcf3c7de653bf8f99cec02d7ae9377f26d92a64495f5e6b7b9e520b3c3` |

用只读 `zipfile` CRC 检查及逐成员字节比较，两个 ZIP 中共 12 份
result.json/log 与现有解压文件全部一致。不是只相信交付摘要或手写 PASS。
本轮 API 元数据保存在 `.cache/p3-4-review-20260916/` 的
`run-35034258547.json`、`artifacts-35034258547.json`。

### 7.3 集中问题清单

以下 `lib/`、`test/` 路径均相对 `app/bluetooth_flutter_Trace/`，行号基于
1256e2f。反例是源码控制流核查，不冒充本轮新执行的 Flutter 测试或真机结果。

| 发现 ID | 依据/判据 | 影响范围 | 处置 | 自测证据 |
|---|---|---|---|---|
| P34-R01 / P1 | `OTA-XC-BLE-TUNING` 首发完整结束到首个有效确认；`lib/ota/ota_ble_transport.dart:419`、`lib/ota/ota_link_stats.dart:188` | ACK 可在 `_sendSegment` 的 await continuation 前被分发。此时 `firstEnd == null` 直接丢掉确认；之后登记发送结束不会补样本，最后一段也没有后续 ACK 可补救。`test/ota/ota_ble_transport_test.dart:2268` 把 ACK 延迟 1ms 排除了这个顺序，未修产品观测。物理 ACK 有链路延迟不等于 Dart 的写完成通知必先执行。 | 保留真实发送边界与 ACK 到达时间，显式处理早到确认/迟到写完成；无法建立合法时序时明确记为无效观测，不将负时间截成 0 或以固定延迟掩盖问题。补零延迟及延迟写完成的确定性反例，撤回“真机无此竞争”的结论。 | 现有 4 项 transport 接线测试均指定 1ms ACK 延迟；新增反例 NOT_RUN。 |
| P34-R02 / P1 | 同条款允许 durable/bitmap 共同确认；`lib/ota/ota_ble_transport.dart:354`、`lib/ota/ota_link_stats.dart:198` | resume BEGIN 回 `durableOff=4096, bitmap=0` 时，只调用 current-block bitmap 确认与 durable 事件；此前已发送但未收到 DATA ACK 的 `[0,4096)` 段永远不生成样本。`recordBitmapConfirm` 在 bitmap=0 时直接返回，`recordDurableAdvance` 不补确认。 | 处理有效 BEGIN 的 durable 前缀和当前块 bitmap 的确认并集，仅为本实例确实发送过且未采样的段补首个有效确认，不给未发送的 resume 前缀制造样本；保存该有效 ACK 的真实到达时间。 | 现有 `test/ota/ota_ble_transport_test.dart:661` 的“全丢 ACK，journal 恢复后 END 成功”已在 CI 执行，但没有传 stats。为同一路径接入 stats 并断言完整性/样本数的测试 NOT_RUN。 |
| P34-R03 / P1 | 同条款计时到“成功 END ACK 完整到达”；`lib/ota/ota_ble_transport.dart:741` | `_dispatchFrame` 仅看 cmd 即覆盖 endAckUs，先于 waiter 的 session/seq 关联及 payload/status/durable 校验。合法 END 后同批分发的无关、重复或非法 END 可覆盖成功应答的时刻，outcome 仍可能为 ok。另 `:311` 在首个 BEGIN 实际排队/写入前记起点，可把首帧前等待混入。 | 到达时间与具体帧绑定；仅以本次请求最终采信的成功 END 帧提交终点，不采用“最后一个 END”。起点对齐已批准的 BEGIN 发送观测边界；不改变协议等待/重试语义。 | 新测试只验证覆盖式 setter，没有关联过滤、成功 END 后附加伪 END、首帧排队/暂停等计时反例；定向运行 NOT_RUN。 |
| P34-R04 / P2 | `OTA-XC-BLE-PERFORMANCE` 发现次数/耗时、实际 MTU/净荷与写入模式；`lib/services/bluetooth_service.dart:1680`、`lib/services/ota_service.dart:1840` | `findExactOtaCharacteristicsByAddress` 没有透传 stats，内部 `discoverServicesByAddress` 不计数；后台复核同样漏计。bind 阶段在严格发现之后才开始。所有日志/JSON 均无 writeMode/writeWithResponse。发现及平台写的异常尝试也只进入外层 GATT 错误，不进入相应阶段统计。无法据摘要还原实际调用次数或检查写模式是否混组。 | 把既有 OTA 严格发现、必要复核及失败尝试纳入明确的阶段/计数口径，记录实际绑定写模式；区分实际协商 MTU、净荷上限和未知/回退值。阶段包含关系须与 research 一致，不能将 findExact 总耗时直接冒充底层 discover 耗时。 | service 新测试只断言 found/MTU/subscribe/GATT 非零，没有写模式、发现精确次数或失败尝试断言；定向运行 NOT_RUN。 |
| P34-R05 / P2 | Spec 的完整摘要和日志缺失可检出；`lib/services/ota_service.dart:875`、`:900`、`:910` | 特征不存在、绑定返回 null、绑定期间取消、INFO 身份不一致等正常 `return false` 不经过 catch，也到不了 `:940` 的 emitSummary。即使已有发现/订阅观测，整轮也可能没有终结摘要。 | 收敛到幂等的统一观测收尾，覆盖早退、异常和取消；标明失败阶段/原因，未进入 transfer 不得伪装为成功传输。不要为了统计改取消或设备所有权语义。 | 成功 upgrade/probe 摘要测试不覆盖这些早退；失败/取消恰一摘要的测试 NOT_RUN。 |
| P34-R06 / P2 | `OTA-XC-BLE-PERFORMANCE` 重启重连/GET_INFO 独立报告、不同绑定不混组；`lib/services/ota_service.dart:1626`、`:1723` | 所有 probe attempt 共用一个 stats，但发现/MTU/订阅 setter 只保留首次。首轮 found=false、下一轮成功时，最终摘要仍 found=false；下一绑定的 MTU/订阅耗时也丢失。probe 没有 reconnect/bind 阶段起止，失败 GET_INFO 不计时；超时 attempt 的迟到回调仍可更新共享收集器。不能得到完整重连耗时或分清 attempt 的观测。 | 明确整段重连与各 attempt/连接绑定的统计归属，记录完整单调起止及失败耗时，隔离过期 attempt 与终结后的回调；不得把首次绑定字段与后续累计写入冒充同一绑定。 | 现有旧身份/超时/重试用例没有这些 stats 断言；多 attempt、首次发现失败、MTU 变化和迟到回调反例 NOT_RUN。 |
| P34-R07 / P2 | 执行合同 §7/§7.3：正反例须验证真实被测接线；`test/ota/ota_service_upgrade_test.dart:338`、`:2715`、`:2732`、`:2781` | 新 service 测试调用 `_UpgradeFakeBle` 的公开 override，并由 fake 自行 `recordMtu/recordSubscribe/recordGattWrite`。删除生产 BluetoothService 的对应记录点，该断言仍可通过；因此它只证明上层透传，不能证明测试注释所称“DATA 写经过计时外壳”。现有真实 BluetoothService + fake adapter 测试没有 stats 断言。 | 保留上层参数透传测试，另在观察点下方注入 fake adapter/平台响应，实际执行生产外壳和异常 rethrow；覆盖成功、异常、null stats，并用移除记录点的变异证明断言有鉴别力。不要求从外部覆写库私有方法。 | CI 通过的是 fake 上报路径；真实外壳计时/失败传播及变异反例 NOT_RUN。 |

### 7.4 交付表述更正与尚未覆盖项

1. §4/§5 的“无构建输入变更”不成立：本批修改了 4 份产品 Dart 源码，
   它们本身就是 APK/EXE 构建输入。原 run 的 NOT_REQUESTED 事实保留，
   但只能解释为本次是 checks-only 开发验证，不能解释为免除 App 构建门禁。
   正式构建需另按授权办理，不能为补此缺口擅自运行 build.yml 或推主干。
2. fake 内补上报是上层透传测试的合理适配，不是生产外壳覆盖证明；P34-R07
   要求补独立的真实外壳测试，不要求撤回 fake 修复或弱化已有断言。
3. §3 的“真机无此竞争”没有平台时序保证，不能作为取消早到 ACK 负例的依据。
   research §3.4 的“单样本值不受输出开销污染”也过于绝对：外层 GATT 计时
   包含内层 discover/platform_write 记录和日志开销。同一插桩版本不能自动
   证明优化前后不同调用次数下的观测者开销相等；设备实验需说明实际测量边界。
4. 日志解析器及日志缺失/混组/错误摘要/时钟域负例尚未交付。现有
   `ota_link_stats_test.dart:94` 只检查缺少确认时的内存状态，不会修改或解析
   摘要，因此不是摘要变异检出测试。可以按既定分批计划后续交付，但正式
   测量前必须补齐，不把本批已有单测标为这些判据的 PASS。
5. 包身份、1MiB 合法参考包、MCU UART/staging 分解、实际吞吐、AT 参数及
   设备上板资格均未在本轮实测，保持原操作单的待授权状态。P3-3-v9 及
   既有设备额度不变，不拿旧硬件结论替代 P3-4。

### 7.5 下一批验证范围

实现会话按 P34-R01 至 P34-R07 一次批量整改，沿上述既有 fake、adapter 和
恢复用例补针对性正反例；有输入变化后按 §7.3.2 在专用 dev/flutter/**
分支运行开发检查。保留当前五轮失败/修复链和最终绿 run，不抹去原始证据。
改动涉及 BluetoothService/OtaService/transport 共享调用者，稳定批次须有
Ubuntu/Windows 完整 App analyze/test；不因一个断言修复就重开正式验收。

正式验收应在已知阻断修复、自测稳定后审批版本化合同，使用受审组件依赖、
准确实现/runner/SDK 身份和 NOT_RUN 矩阵完成前检。开发报告不是可直接复用的
独立 EXECUTED PASS 锚点。本轮没有正式观测、硬件操作或重试额度消耗。

### 7.6 本轮操作与写入边界

- 执行了 Git 对象/diff/状态检查、源码集中复核、现有开发日志解析、GitHub
  只读元数据核对及 ZIP digest/CRC/成员字节核验；`git diff --check main
  1256e2f` 退出码 0。
- 本机 PATH 未发现 Flutter/Dart，未安装或调用本地 SDK，未新增运行
  Flutter 测试、APK/EXE 构建、正式验收、AT/J-Link/ADB/OTA 或发布部署。
- 没有提交、暂存、切分支、推送、合并、dispatch、修改凭据或远端。
  产品/测试、research、验证工作树及原有未跟踪资产保留。
- 主动输出仅为本节、看板回写以及
  `D:\github\my\E-Track\.cache\p3-4-review-20260916\` 内的只读查询入口与
  API 元数据；该目录及文档的规范化绝对路径/现有父链已在写入前核对。
  GitHub CLI 的临时/缓存/LOCALAPPDATA 输出定向项目内，关闭自动更新检查，
  原 GH 配置仅作为只读认证输入；未使用 PowerShell 或项目外临时输出。
- 最终审计：8 份产品/测试文件及 research 的原始 SHA-256 与本轮修改前
  一致，验证工作树仍 Git clean。GH 自动生成的
  `localappdata/GitHub CLI/device-id` 也位于上述项目内证据目录，未输出其
  内容；原项目外 GH config.yml/hosts.yml 未修改，未发现项目外主动输出。

## 8. 整改批实施记录（P34-R01..R07，2026-09-16）

本节由实现会话回写：承接 §7 集中预审的 7 项阻断（3×P1 + 4×P2），按预审
§7.5 一次批量整改并复验。§1-§6 保留原始交付记录，不被本节改写。

### 8.1 提交链与 CI 轮次（整改批）

| 提交 | 内容 | run | 双宿主结论 |
|---|---|---|---|
| `3fd464b` | R01-R07 批量整改（9 文件：4 产品 + 5 测试） | 35094204310（第六轮） | 红：tests 3 处 |
| `1772373` | 修第六轮暴露的三处（测试作用域 / transfer 终态 / 轮次序号） | 35095235370（第七轮） | 红：analyze 绿、tests 红 |
| `f5dc9fd` | 轮次汇总覆盖空转轮 + 绑定阶段包含发现 | 35097788256（第八轮） | 红：analyze 绿、tests 红 |
| `e783155` | END 非 OK 应答不得登记成功终点 | 35098277162（第九轮） | **步骤级双宿主 analyze/tests PASS**（整轮 run 因 artifact 上传失败，见 §8.4） |

第九轮：<https://github.com/Eitan-S-23/E-Track/actions/runs/35098277162>，
提交 `e783155395fcc9e66345c9d8c1862d97f375816f`，tree
`b5a45cc5a7c05d4659a1553ef9b6289deed1a0eb`，分支
`dev/flutter/p3-4-link-stats`。本地原始 job log：`.cache/ci-35098277162/`。

第五轮（`1256e2f`，run 35034258547）的绿 run 与 §1-§6 的原始证据保留不删，
作为整改前的基线；§7 预审的 7 项阻断即相对该基线成立。

### 8.2 逐项整改（对应 §7.3 的发现 ID）

- **R01（P1）早到 ACK 不再丢弃**：`lib/ota/ota_link_stats.dart` 增设早到确认
  暂挂表与 `ackEarlyInvalid` 计数。确认早于该段首发登记时，不再直接丢弃，而是
  记为**无效观测**（流式行 `kind=ack_early_invalid`）并计入完整性缺口
  （`partial:missing=N,early=M`）；首发登记随后到达时逐个消费暂挂项，**不得**
  反过来伪造「起点晚于终点」的样本。§3 第 4 条与 research §3.4 的「真机无此
  竞争」表述已撤回（改为正反例覆盖）。测试：单元组「P34 整改」；transport
  `T5 零延迟 ACK`（`ackDelay=0`，断言 `ackEarlyInvalid=32`、样本为空、
  完整性 `partial:missing=32,early=32`）。
- **R02（P1）续传 BEGIN 确认并集**：`ota_link_stats.dart` 新增
  `recordResumeConfirm(durableOff, bitmap, segmentSize, arrivalUs)`，按 durable
  前缀 ∪ 当前块 bitmap 的**并集**补记确认；只为本实例确实发送过且尚无样本的段
  补样本，未发送的 resume 前缀只暂挂为 `ackEarlyUnsent`（不造样本、也不算无效
  观测）。样本终点取该有效 ACK 的**真实到达时刻**（含丢 ACK 后的重发等待与
  ABORT + resume 全程）。transport 在有效 BEGIN ACK 处调用。测试：单元
  「resume BEGIN 确认并集」；transport `T6 整块 ACK 全丢 → ABORT + resume`、
  `T7 新实例续传`。
- **R03（P1）END 终点**：`lib/ota/ota_ble_transport.dart` 从帧分发层移除按 cmd
  覆盖的 `recordEndAckArrival()`，唯一调用点收在 `transfer()` 的 END **采信点**
  （waiter 精确关联 cmd+session+seq、status==OK、durable==total、尾块位图合法
  之后）；传输起点对齐 BEGIN 首帧**写调用**时刻（`_writeFrame` 内
  `_inTransfer` 分支），不再把首帧前排队等待混入。第九轮补：非 OK、非终态、
  无可续传预算的 END 应答（ERR_SHA / ERR_SEQ / ERR_STATE 余额耗尽）改为
  **非抛出早退**，不再落入成功块登记终点或置 `outcome=ok`；随后删除两处
  fail-closed 校验中已冗余的 `statusOk` 前置条件（早退已保证到达该处必为 OK）。
  测试：`T8 END 重放不覆盖终点`、`T9 END 错误状态`。
- **R04（P2）绑定/发现字段**：`lib/services/bluetooth_service.dart` 的严格发现
  `findExactOtaCharacteristicsByAddress` 与订阅/MTU/平台写外壳透传 stats，登记
  发现次数与成败、实际写模式（`writeMode`）、MTU 来源（`mtuSource`：真实协商值
  vs 回退值），失败尝试同样入账（`getInfo.failures` / `discovers.errors` /
  `platformWrites.errors`）。`lib/services/ota_service.dart` 的绑定阶段起点上移到
  严格发现**之前**（升级路径与 probe 路径同一包含关系，对齐 research §3.1
  「绑定 = 发现 + MTU + 订阅」）；发现失败时阶段不闭合，「已开始未完成」如实
  保留（`toJson` 对单元素阶段安全，`phaseUs` 为 null）。测试：单元「P34-R04
  失败往返」「MTU 来源与写模式可区分」；service 绑定字段与写模式断言。
- **R05（P2）早退摘要**：`ota_service.dart` 的 `fail(stage, reason)` 统一登记
  失败阶段与原因，`finally` 统一 `recordTransferOutcome(ok:false)` 并
  `emitSummary()`（幂等），使特征缺失、绑定返回 null、绑定期取消、身份不一致等
  **非异常早退**同样输出恰一份终结摘要；未进入传输者 `transfer.startUs/elapsedUs`
  为空，不伪装成功传输，取消与设备所有权语义未改。测试：service「早退摘要」
  （特征缺失 → `failure.stage=discover`、`outcome=fail`、`startUs=null`）。
- **R06（P2）probe 归属**：`ota_service.dart` 每轮探测独立
  `OtaLinkStats(attempt: n)`，轮内摘要在本轮结论时定格，迟到回调只落自己轮次；
  轮次外壳**逐轮无条件**汇总结论（含 `no_verdict`，否则空转轮次在整体摘要里
  消失），取消代次变化归一为 `cancelled`；`attempts[].n` 取
  `attempt ?? 记录序号`，避免同一份 JSON 里 `attempt=2` 配 `n=1` 的归属读错。
  测试：单元「probe 轮次」；service「probe 轮次归属」。
- **R07（P2）真实外壳测试**：新增 `test/ota/ota_link_stats_shell_test.dart`
  （361 行），用真实 `BluetoothService` + 注入 fake adapter/平台响应，实际执行
  生产计时外壳与异常 rethrow，覆盖成功、异常、`stats==null` 三态。既有
  `_UpgradeFakeBle` 透传测试保留（它只证明上层透传，不再充当外壳覆盖证据）。

### 8.3 第六轮三处红的根因（防复发）

1. 文件级 helper 看不到 `main()` 作用域内的局部助手 →
   `Method not found: 'shaOf'` / `'etuHeaderOf'`，transport 测试文件整体加载
   失败，该测试组当轮**未执行**；改为 helper 内就地自算 SHA-256 与前 64B 包
   前头。
2. R05 的 `transfer.outcome` 缺终态 → `finally` 补
   `recordTransferOutcome(ok:false)`。
3. R06 的单轮实例 `attempts[].n` 回落成实例内下标 → 改取
   `attempt ?? 记录序号`。

### 8.4 第九轮判定与证据边界（artifact 配额阻断）

第九轮 run 35098277162（`e783155`）双宿主**第 6 步「Analyze, test and
optionally build a debug APK」为 success**，该步骤日志尾部为：

```text
sdk_checkout: PASS (exit=0)
sdk_version: PASS (exit=0)
dependencies: PASS (exit=0)
analyze: PASS (exit=0)
tests: PASS (exit=0)
```

但该 run 的**整轮结论仍是 failure**：唯一失败步骤是第 7 步
「Upload development logs (not acceptance evidence)」，双宿主均报
`Failed to CreateArtifact: Artifact storage quota has been hit`。即**红的是
上传步骤，不是开发检查本身**。

代价与边界：`result.json` 与 `logs/*.log` 未上传，本轮的测试通过数、skip 数、
`OTA_LINK_` 观测行数、SDK 版本等**计数证据不可取回**，判定只能停在步骤级
（exit=0）。第八轮（`f5dc9fd`）同样 analyze 绿、tests 红，且失败详情同样不可
取回；第六、七轮的红是真实测试失败（第六轮细节见 §8.3）。

账号 artifact 用量（`gh api` 只读核对）：345 个 artifact，合计
4,548,046,614 B ≈ 4.24 GiB，其中 71 MiB 级 `flutter-dev-debug-apk-*` 占主体；
仓库为 private。GitHub 提示用量每 6-12 小时重算。**清理历史 artifact 属远端
破坏性操作，需用户明确授权，本次未执行任何删除。**

**重跑（attempt 2，2026-09-17）**：用户释放远端存储后（`gh api` 只读核对：
305 个 artifact / 1.43 GiB，`flutter-dev-debug-apk-*` 由 3.64 GiB 降至
0.84 GiB），对**同一 run、同一提交**触发环境恢复重跑
（`gh run rerun 35098277162`，attempt=2；分支 `dev/flutter/p3-4-link-stats`、
提交 `e783155` 均未改动，非新批次）。结果与 attempt 1 同形：双宿主第 6 步
`analyze: PASS (exit=0)` / `tests: PASS (exit=0)`，唯一失败步骤仍是上传，原始
报错为

```text
Failed to CreateArtifact: Artifact storage quota has been hit.
Unable to upload any new artifacts. Usage is recalculated every 6-12 hours.
```

（2026-09-16T23:03:51Z，Ubuntu job 第 7 步）。即：**释放存储不等于闸门立即
放行**——用量计数器按 6-12 小时重算，上传闸门读的是旧计数；这是环境时序，
不是产品缺陷，也不能把本轮当作新批次。本轮原始双宿主 job 日志归档于
`.cache/ci-35098277162-attempt2/`（Ubuntu 42,259 B / Windows 40,977 B，各自
SHA-256 与逐步结论见 `attempt2-summary.json`）。

本轮同时确认两条边界：(1) job 日志只含 harness 的**步骤级**结论与日志文件
路径，原始测试输出（通过数、`OTA_LINK_` 行数、SDK 版本）**只存在于 artifact
内**，故计数级证据仍须待闸门放行后取回，不能从 job 日志冒充；(2)
`.github/workflows/flutter-dev-checks.yml` 的上传步骤显式
`retention-days: 14`，与本节由 `expires_at` 反推的 14 天保留期一致。

第八轮红与第九轮绿之间只差一处提交：`f5dc9fd..e783155` 仅改
`lib/ota/ota_ble_transport.dart`（即 §8.2 R03 的 END 非 OK 早退），方向与定向
分析（反例 T9 的三条断言）一致；但因详情不可取回，**不能**据此断言第八轮的
失败项恰为 T9 三条，只能记录为「与定向分析一致」。

**重跑（attempt 3，2026-09-17）**：清理完成于本地 2026-09-17T02:17:28+08:00
（UTC 2026-09-16T18:17:28Z），重跑发起于 2026-09-17T07:15:27Z，间隔 **13 小时**，
已越过报错文本所称的 6-12 小时重算窗口。结果与 attempt 1/2 同形：

| 项 | 值 |
|---|---|
| run / attempt | 35098277162 / 3 |
| 分支 / 提交 | `dev/flutter/p3-4-link-stats` / `e783155`（未改动） |
| 双宿主第 6 步 | success（`sdk_checkout`/`sdk_version`/`dependencies`/`analyze`/`tests` 全 `PASS (exit=0)`） |
| 唯一失败步骤 | 第 7 步「Upload development logs (not acceptance evidence)」 |
| 报错原文 | `##[error]Failed to CreateArtifact: Artifact storage quota has been hit. Unable to upload any new artifacts. Usage is recalculated every 6-12 hours.`（Ubuntu 07:18:36.9184397Z；Windows 07:19:35.1436560Z） |
| 时间窗 | 07:15:27Z → 07:19:41Z（约 4 分钟） |
| 整轮结论 | failure（由上传步骤导致，非测试失败） |

**诊断更正**：attempt 2 把「清理后仍被拒」解释为 6-12 小时重算滞后（见上文）。
attempt 3 在越过该窗口之后**仍被拒**，故该解释不再成立。按 `gh api` 只读普查
（`.cache/p3-4-rerun-20260917/quota-census-20260917.json`），清理后残留的
**未过期**占用为 254 件 / 1,497,960,235 B ≈ 1.395 GiB，分解如下：

| 构成 | 件数 | 体量 | 可删除性 |
|---|---|---|---|
| 策略 pin 的 `flutter-dev-debug-apk-*` | 12 | 902,646,481 B (860.8 MiB) | **不可删**：命中 `artifact_maintenance_policy.json` 的 `pinned_artifacts`（到期 2026-09-23…09-29） |
| 非 pin 且仍落在维护工作流删除范围内 | 0 | 0 B | 已无可删项 |
| 非 pin 且范围外（分支前缀或命名前缀不匹配） | 242 | 595,313,754 B (567.7 MiB) | 不在 `dev/flutter/` + `flutter-dev-debug-apk-` 范围内；其中 25 件 >10 MB 共 544.5 MB（`android-apk`/`windows-exe`/`firmware-2.7`/`boot-2.7`，到期 2026-10-22 / 12-02 / 12-12…12-14） |

账号侧：同一普查覆盖 12 个私有仓库，**未过期占用全部集中在 E-Track**（其余仓库
产物均已过期、不计入）。额度数值需 `user` scope 才能读 billing，本会话 token
无该 scope（`gh api .../settings/billing/shared-storage` 返回 404 并要求
`gh auth refresh -s user`），故**只能给出上界**：额度 < 1.395 GiB。

由此三条结论：(1) 继续等待重算**不会**放行，attempt 2 的时序解释已被证伪；
(2) 要让闸门放行须把占用降到额度以下，而剩余体量只在 pin 集与维护工作流范围外
产物上——扩大删除范围属 AGENTS.md「不得为满足预算扩大删除范围」的禁区，取消
pin 会破坏 P3-3 的证据引用，二者都不应做；(3) 自然到期最早 2026-09-23
（1 件 71.68 MiB），pin 集整体要到 09-29 才清空。**计数级证据的缺口语义不变
（EVIDENCE_GAP），但其成因是残留地板高于账号额度，不是重算滞后。**

**不依赖 artifact 的计数通道（主线已有，本轮未启用）**：主线 `2d81a4b`
（feat(ci): bound artifact retention and preserve development diagnostics）
为 `Tools/flutter/dev_checks.py` 增加了 `log_diagnostics()`——它在**上传之前**从
完整 `tests.log` 逐行导出 `test_counts`（passed/skipped/failed）、`ota_link_lines`
（`OTA_LINK_` 行数）与 `sdk_identity`（framework/channel/dartSdk），以
`DEV_COMMAND {json}` 行打到**控制台**，末尾另输出 `DEVELOPMENT_RESULT`，即上传
失败也不影响计数可见性。该提交**不在被测 tree `e783155` 内**（`e783155` 携带的
`dev_checks.py` 早于它），所以本轮三份 job 日志中 `DEV_` 行数实测为 0。要让该
通道生效，需在 `dev/flutter/p3-4-link-stats` 上产生一个包含它的新提交（即同步
主线）后重跑；那会新建提交与新一轮 CI，**不属本次"不改被测 tree 的重跑"范围，
本轮未执行**，是否进行由用户决定。

本轮证据归档：`.cache/p3-4-rerun-20260917/`——`attempt3-job-105111622527.log`
（Windows，67,449 B）、`attempt3-job-105111622773.log`（Ubuntu，70,970 B）、
`attempt3-summary.json`（含两文件 SHA-256、逐步结论与报错原文）、
`quota-census-20260917.json`（上表普查）、`census.py`（只读普查脚本）。

### 8.5 四类分离声明（整改批后）

| 类别 | 状态 |
|---|---|
| 源码编辑 | 完成：整改批 4 个提交（`3fd464b` → `e783155`）落在 `dev/flutter/p3-4-link-stats` |
| 开发自测 | 第九轮**步骤级**双宿主 analyze/tests PASS；计数证据因 artifact 配额缺失（见 §8.4） |
| APK/EXE 构建 | NOT_REQUESTED（本批已改 4 份产品 Dart 源码，它们就是 APK/EXE 构建输入；未申请 ≠ 免除 App 构建门禁，正式构建需另按授权办理） |
| 独立验收 | NOT_RUN（由非实现会话按执行合同另行组织；开发报告不是可直接复用的 EXECUTED PASS 锚点） |
| 设备实测（吞吐/AT） | NOT_RUN（操作单见 research §8，待授权） |

### 8.6 未覆盖项与后续交付

1. **R04 后台复核路径未覆盖**：`resumeFromBackground` 的后台复核发现调用不计入
   bind 观测。该路径属 P3-8 后台执行域，且为它新增独立 label 会偏离 research
   §4.2 已冻结的日志格式，本批**不修**并如实声明，不作为 R04 已完成的一部分。
2. **日志解析器与负例已交付**（预审 §7.4④）：解析侧实现与四类负例（日志缺失、
   混组、错误摘要、时钟域错配）见 §9。§9 是在本批 CI 轮次之后补做的实现侧
   自测，**不改写 §8 的 CI 结论**，也不把 §9 的本地自测当作这些判据的独立
   验收 PASS。
3. **计数证据缺失**：第九轮 `result.json` 未上传，通过数与观测行数缺失。已按
   环境恢复路径对**同一提交**做了一次重跑（attempt 2，见 §8.4），双宿主
   analyze/tests 再次步骤级 PASS，但上传仍被滞后的用量计数器拒绝，计数证据
   仍未取回。剩余动作：待计数器重算（6-12 小时）后再重试同一 run；不得改动
   被测 tree，也不得把它当作新批次。
   **口径补充（2026-09-17 核对）**：`Tools/flutter/dev_checks.py` 自 `2d81a4b`
   起在 job 日志中输出每命令的 `NAME: STATUS (exit=N)` 行、`DEV_COMMAND {json}`
   （tests 命令含 `test_counts` 的 passed/skipped/failed 与 `ota_link_lines`）
   及 `DEVELOPMENT_RESULT {json}`；自该提交起的轮次，计数证据可从 job 日志
   取回，不再只能依赖 artifact。该改进对第九轮不生效——workflow 与 harness
   取自被运行的提交 `e783155`，早于 `2d81a4b`。
4. **零延迟微任务次序依赖**：transport 的零延迟 ACK 用例（T5）与实现语义自洽，
   但其「通知分发先于写完成续体」的前提不是 Dart 规范保证，当前依据是实测
   观察。若后续轮次该组出现反向结果，应由 fake 侧给出确定性时序，而不是放宽
   断言把该场景放回去。
5. **本批不新增任何设备、AT、烧录、安装卸载、发布部署或主干提交权限**；设备
   实验仍按 research §8 操作单等待授权。

## 9. 日志解析器与负例交付（预审 §7.4④ / research §10.5，2026-09-17）

本节交付 §8.6 第 2 条与 `P3-4-research-link-timing-2026-09-16.md` §10 第 5 条
所指的解析侧实现与负例。**本节是实现侧自测留痕，不是独立验收**；不含设备、
真机、AT 或任何新增测量结果。原 §8.6 第 2 条的"未交付"结论由本节取代，
§8.6 其余条目不变。

### 9.1 交付物与身份

路径相对项目内验证 worktree `.cache/worktrees/p3-4-link-stats/`（分支
`dev/flutter/p3-4-link-stats`）。

| 文件 | 体量 | SHA-256 |
|---|---|---|
| `Tools/ota/p3-4-link-stats/link_stats.py` | 730 行 | `f0d36022962868c005ecd0b7a3077758501674a2b3aee9f7c6100af09a447084` |
| `Tools/ota/p3-4-link-stats/selftest.py` | 972 行 | `e521a31ebb28c77f0a739cc7ddffd8fc4ce82d8cc55d2009854490a95e018b7d` |
| `Tools/ota/p3-4-link-stats/fixtures/round6-ubuntu-head.log` | 41,982 B / 274 行 | `d482f9ed386a064146992585fdf93ab2738f1b785c2bdc2e910e0d81c37bf645` |
| `Tools/ota/p3-4-link-stats/fixtures/PROVENANCE.md` | — | `d763559bf89ed3239a08a1804f4539a0b111ed610e0e5c9a752e9bdbcb3ad62a` |

夹具是第六轮 Ubuntu `tests.log` 第 1–274 行的**逐字节**切片（源 SHA-256
`1cc73fa2…`，179,715 B）；只允许"逐字节切片"与"selftest 运行时构造"两类
夹具的政策与覆盖/未覆盖形状见 `fixtures/PROVENANCE.md`。

复现命令（只读、仅标准库、无网络、无设备、不写仓库外路径）：

```bash
cd Tools/ota/p3-4-link-stats
python selftest.py                                          # 37 项，失败 0
python link_stats.py --log fixtures/round6-ubuntu-head.log   # exit 0（0 致命）
python link_stats.py --log <整份捕获> --device-capture --json # 严格块模型
```

CLI 退出码：`0` 无致命发现、`1` 存在致命发现、`2` 用法或读取错误。

### 9.2 判定模型：三处必须区分的形状

1. **分组与拖尾方向不对称。** 连续样本块由紧随其后的摘要收口，摘要描述
   "打印时刻的实例累计值"。缓冲区计数**大于**声明 → `STRAGGLER`(warn)
   （摘要后仍有该实例样本，第六轮真实日志中即每块摘要后的重连 INFO 写）；
   **小于**声明 → `COUNT_MISMATCH`(fatal)。方向不对称是为了不误报：摘要所属
   实例的样本必然全部落在它收口的块内，所以"观测少于声明"不会因块内混入
   其它实例而产生；反向则会，只能告警。
2. **两类缺失强度不同。** 摘要声明多于日志观测 = 丢行/截断（fatal，该块不
   参与合并）；样本之后没有摘要 = 没有可核对的声明（默认 warn，同样不参与
   合并，因为无 label/终态权威）。
3. **`--device-capture` 是单一严格开关。** 设备采集轮次按"每块恰一个实例
   且必须收口"判定：块内实例时钟回退 → `CLOCK_NONMONOTONIC`(fatal)，末尾
   未收口 → `SUMMARY_MISSING`(fatal)；默认模式把这两种形状分别记为
   `MULTI_INSTANCE`(warn) 与 `SUMMARY_MISSING`(warn)，以适配真实捕获（前序
   实例未收口）与测试 harness（传输级用例只断言样本行、不输出摘要）。

### 9.3 自测覆盖矩阵（37 项，全部 PASS）

- **正例控制（5 项）**：夹具逐字节身份与 SHA-256；真实切片 4 块单实例已收口
  （默认**与**严格模式都 0 致命，证明严格模式不是"一律打红"）；真实样本行 +
  由 selftest **独立重算**的当前契约摘要 → **零发现**（字段齐全时计数、分位数、
  完整性三层核对整体通过）；整改前切片缺字段逐项申报。
- **负例·日志缺失 / 未收口（2 项）**：删样本行 → `COUNT_MISMATCH`；
  删摘要 → 默认 warn / `--device-capture` fatal。
- **负例·混组（3 项）**：摘要 label 不符、块内样本 label 混用 → `MIXED_LABEL`；
  `attempts[].n` 回退 → `MIXED_ATTEMPT`；同 label 双实例落同一缓冲区 →
  `MULTI_INSTANCE`(warn) / 严格模式 `CLOCK_NONMONOTONIC`(fatal)。
- **负例·错误摘要（9 项）**：分位数、计数虚高、字节数、durable 末值越界、
  重传派生量、传输时长、完整性声明、阶段倒置、`bind.phaseUs` 不符 →
  `QUANTILE_MISMATCH` / `COUNT_MISMATCH` / `INTERNAL_INCONSISTENT` /
  `INTEGRITY_MISMATCH` / `PHASE_REVERSED`。
- **负例·时钟域与结构（7 项）**：`clock` 非冻结域 → `CLOCK_DOMAIN`；未知
  `schema` → `SCHEMA_UNKNOWN`；负 `us` → `CLOCK_NEGATIVE`；摘要 JSON 破损 →
  `BAD_JSON`；样本畸形 → `MALFORMED_SAMPLE`；未知 `kind` → `UNKNOWN_KIND`；
  缺必需对象 → `SCHEMA_MISSING`。
- **强度分级（2 项）**：字段缺失只告警（`FIELD_ABSENT`）、拖尾样本只告警
  （`STRAGGLER`）——两者都不得被判成致命。
- **口径与 CLI（5 项）**：nearest-rank 语义（`ceil(q*N)` 不插值、N=0 → null、
  N=1、整除边界）；分位数核对确实执行（非空转）；`--json` 结论形状；
  真实切片默认/严格模式退出码 0；合并统计只纳入 clean run。
- **鉴别力（1 项）**：见 §9.5。
- **整份真实捕获（1 项，外部证据不在场则 SKIP 并说明）**：见 §9.6。

### 9.4 自测跑出的解析器缺陷（本轮修正）

构造"摘要声明的 `durable.finalOff` 是更早的一条、其后仍有推进"时，本应告警
的形状被判成致命：`_check_counters` 用 `declared_final in [s.extra.get('off')
…]` 比较，左侧是 JSON 解析出的 `int`、右侧是样本 `extra` 里的**字符串**列表，
成员判断恒为假，于是落到 `COUNT_MISMATCH` 分支——正是文档声称要告警的
真实形状（摘要打印后同实例继续推进）被反向判红。已改为按整数比较
（`link_stats.py:479` 附近），并新增用例
`test_durable_final_off_behind_last_sample_is_warn` 固定该方向。

这条缺陷只在"正例控制 + 定向负例"同时存在时才会暴露：正例全绿掩盖不了它，
纯负例集也不会覆盖该方向。它不改变任何已冻结契约。

### 9.5 鉴别力证明（防"全红零鉴别力"）

自测内置 `test_negative_cases_discriminate_on_check_removal`：逐项把解析器的
核对函数临时置空，要求对应负例**确实失败**，随后恢复原函数。当前 10 个核对
函数、25 条配对全部具备鉴别力（置空 → 用例报错；恢复 → 全套 37 项全绿）。
若夹具字面量失配、核对被摘除或断言被写成恒真，本项会失败，而不是继续
显示全绿。

### 9.6 真实捕获上的运行（只读、非测量）

工具在**不入库**的整份 CI 捕获上运行，作为外部形状的正例控制（本轮只读
解析，未重跑 CI、未下载产物）：

| 宿主 | 观测块 | 样本 | 致命 | 告警构成 | 合并（label=upgrade） |
|---|---|---|---|---|---|
| Ubuntu | 27 | 801 | 0 | `FIELD_ABSENT` 130 + `STRAGGLER` 12 + `SUMMARY_MISSING` 1 | runs=7, excluded=12, 唯一段=56 |
| Windows | 27 | 821 | 0 | `FIELD_ABSENT` 135 + `STRAGGLER` 24 + `MULTI_INSTANCE` 1 | runs=8, excluded=12, 唯一段=64 |

两份捕获都来自整改前发射端 `1256e2f`（第六轮），故 130/135 条字段缺失是该
版本的**合法**缺失（5 个 R01/R04/R05 新增字段 × 各块），合并报告据此标注
`strictFieldsComplete=false`。告警全部有据可解释，无致命发现——这是"正常
输入不打红"的正例控制，**不是**对测量结果或发射端质量的判定。

### 9.7 边界与未覆盖项

- 本节全程只读：未执行设备、AT、J-Link、烧录、安装卸载、OTA、发布部署或
  主干提交；未重跑或 dispatch CI；未下载或删除任何产物；未修改输入日志。
- 该工具是**分析侧**工具：核对发射端日志的自洽性与缺行，不产生新测量，
  也不能替代独立验收。
- 未覆盖：真实设备采集轮次（`--device-capture` 目前只在合成与真实日志上
  自测）、1MiB 参考包的解析规模验证（§8 操作单待授权）、以及 MCU 侧 RTT
  行的对齐分析（需设备授权）。

### 9.8 本批提交与行尾保障（2026-09-17）

本批在独占开发分支 `dev/flutter/p3-4-link-stats` 落 3 个**本地** WIP 提交，
未推送、未合并、未发布：`9518361`（解析器与负例）、`ada2f15`（夹具行尾
白名单）、`0441f78`（夹具说明补记）。三份提交共用同一自测基线：提交前与
提交后各复跑一次 `python selftest.py`，均为 37 项全 PASS、失败 0（exit=0）。

交付过程中实测到一个**会静默毁掉字节身份**的环境坑，已加保障：

- 现象：`git add` 对该夹具告警「LF will be replaced by CRLF the next time
  Git touches it」。仓库 `core.autocrlf=true` 且该路径无 `-text` 条目，
  故 blob 是 LF、**新检出会变成 CRLF**；而本目录夹具的身份就是它的字节
  （`selftest.py` 直接对原文取 SHA-256，`fixture_lines()` 逐行解析），
  两者会同时失真——**本机当前工作副本是 LF 并不代表任何后续检出也是**。
- 处置：按 `.gitattributes` 既有约定（「实测满足工作树字节 == 索引 blob
  字节（纯 LF）」的路径标 `-text`，只增不改）为四个新文件补条目。
- 复检：`git ls-files --eol -- Tools/ota/p3-4-link-stats/` 四项均为
  `i/lf w/lf attr/-text`；`git checkout-index --prefix=<项目内临时目录>/`
  重新检出的夹具与解析器字节数与 SHA-256 与提交前一致（41,982 B /
  `d482f9ed…`、32,503 B / `f0d36022…`），CRLF 计数 0。临时目录用后即删。
- 说明：为满足验收合同「profile 内未跟踪文件不得成为 tree 外隐式输入」，
  夹具虽被仓库通用 `*.log` 规则命中，仍以 `git add -f` 纳入版本控制；
  其三处身份记录（PROVENANCE 表、`.gitattributes` 条目、`selftest.py`
  常量）必须同步更新，规则已写入 `fixtures/PROVENANCE.md`。

## 10. 解析器交付准入复核（Codex，2026-09-17）

### 10.1 范围与结论

**准入复核不通过：本批有 7 类范围内阻断问题，需集中整改。P3-4 保持进行中，
保留 Claude 的实现认领；不放行解析器用于正式测量判定，不宣告本批验收收口。**

本次按执行合同 §7.3 对用户交付的三个本地提交 `9518361`、`ada2f15`、
`0441f78` 进行非实现会话复核，差异基线为 `e783155`。范围是解析器、配套
selftest、夹具及行尾属性，并只读对照当前发射端事件语义；不是对全部 Flutter
整改、AT 实验或 P3-4 整卡的重新验收。§1-§9 原始记录保留，本节追加发现，
不回改原自测结果或历史冻结资产。

被审对象身份（仅身份记录，不冒充合同冻结）：

- worktree：`D:\github\my\E-Track\.cache\worktrees\p3-4-link-stats`；
  分支 `dev/flutter/p3-4-link-stats`。
- HEAD：`0441f7862eaa65d201b49814dbd556ec98e8515a`。
- tree：`ea6bd78250c17a0311b992f1527b192bc29af65f`。
- profile 配置 blob：`3769369d053aad028b67d7e2c17b5827b2b96f55`。

主树及交付 worktree 均未找到 P3-4 已审批冻结的版本化合同或 NOT_RUN 矩阵，
因此正式验收仍为 **NOT_RUN**，合同/矩阵准入存在 **EVIDENCE_GAP**。
本次没有运行 `validate_bundle.py`，没有虚构正式 HARNESS_FAIL/PASS 轮次、
冻结审批、EXECUTED PASS 锚点或 rerun plan。下述实跑是集中预审的宿主诊断，
不是未冻结合同下的正式观测。

### 10.2 已独立核实的交付事实

- 原 selftest 独立复跑一次：**37 项通过、0 失败，exit=0**；本机两份可选
  完整捕获均在场且确实执行，不是 SKIP。stdout 2,607 B，SHA-256
  `98018e0b023e2b5c47703800e9de7e3605c0c04237881d953651daf3c716bac5`；stderr 0 B。
- 四个文件的工作树字节与 HEAD blob 相等，SHA-256 与 §9.1 全部相符；
  `git ls-files --eol` 全部为 `i/lf w/lf attr/-text`。
- 真实夹具与原 Ubuntu 捕获第 1 至 274 行逐字节相等，源文件长度/SHA 与
  PROVENANCE 一致。另以 `git checkout-index` 独立新检出四个文件，SHA 与
  原工作树相同、CRLF 均为 0；本次临时检出随后只删除已核对的四文件及空父目录。
- 默认模式下两份完整捕获的块/样本/告警数可复现：Ubuntu 27/801、Windows
  27/821，均 0 致命。这只证明原 selftest 记录可复现，**不证明 clean-run
  合并合法**，其真实污染见 P34-P02。
- `git diff --check e783155 0441f78` 返回 2，只有
  `fixtures/PROVENANCE.md:56` 的 `new blank line at EOF`，列为非阻断格式建议，
  不据此扩大复验范围。

### 10.3 集中问题清单

下表 `link_stats.py`、`selftest.py` 均相对交付 worktree 的
`Tools/ota/p3-4-link-stats/`，行号绑定本节 HEAD。发现来自本轮新观测；不是
改写前轮结果。诊断夹具全部明确标记为合成输入，不冒充 CI、Dart 运行或设备数据。

| 发现 ID | 依据/判据 | 影响范围 | 处置 | 本轮复核证据 |
|---|---|---|---|---|
| P34-P01 / P1 | Spec 必需负例“不同参数混组”；`OTA-XC-BLE-PERFORMANCE` 同资产/设备/MTU/参数组；`link_stats.py:629` | `aggregate` 只按 label 分组，设备仅收集为一个列表，MTU/写模式不参与分组；也没有 baud/timeout/retry、包及发送器身份的绑定入口。同为 upgrade 的不同条件会生成一个合并 P99。原 label/attempt 负例不能代替参数混组负例。 | 绑定并核验真实实验输入组；可用受审侧车/外部输入保留现有行格式。身份缺失或冲突时只作诊断，不输出一个可用于门槛的混合统计。补不同 MTU、写模式、设备以及 baud/timeout/retry 的负例。 | `mixed_mtu`、`mixed_devices`、`mixed_write_modes` 三例均 exit=0、零发现、runs=2、ACK=4，未隔离或拒绝不同组。 |
| P34-P02 / P1 | `OTA-XC-BLE-TUNING` 只合并同组完整 clean run，不删除缺失样本美化 P99；`link_stats.py:646` | 合并重新调用宽松的 `check_group_only`，丢弃 analyse 的严格模式及解析期 fatal；只筛 outcome=ok，不筛 partial、MULTI_INSTANCE、STRAGGLER 的不确定归属。严格失败或缺样本的块仍被当 clean run，且混入样本全量参与 P99。 | 保留逐块解析/检查结论与模式；区分诊断统计和门槛统计，拒绝用缺失、污染或无法归属的观测证明成功。保留被排除轮次和缺口，不通过静默丢轮次美化结果。 | `partial_ack_population`：partial:missing=1 仍 runs=1/ACK=1；`mixed_instances_strict`：exit=1/CLOCK_NONMONOTONIC 但仍 runs=1/ACK=4；`parse_failure_report` 同样 fatal 后仍合并。**真实 Windows 原捕获第 307 至 976 行含 9 个实例段，摘要声明 8 个 ACK/8 个唯一段，却合并了 210 个 ACK**，导致整份报告 266 ACK/64 唯一段。 |
| P34-P03 / P1 | `OTA-XC-BLE-TUNING` 每个唯一 DATA 段恰一有效样本；Spec 日志缺行/错误摘要检出；`link_stats.py:332`、`:519` | 唯一段/ACK 完整性仅按行数核对，不验证 first-send/ACK 的 off 与 len，更不核对 offset 集合。重复同一偏移的 ACK 可顶替缺失段，计数仍相等而 ackSamples=complete。 | 按实例及唯一字节偏移校验发送、重发、确认集合与必需字段；重复/孤立 ACK、缺偏移、缺对应段及早到确认对应关系必须有显式检出。 | `duplicate_ack_offset` 把两个 ACK 的 off 都改成 0，仍 exit=0、零发现、ACK=2；`missing_segment_offset` 删除首发 off 同样零发现。 |
| P34-P04 / P1 | 执行合同 §7 缺日志/解析失败 fail-closed；`link_stats.py:263` | 空捕获在 --device-capture 下 exit=0；`OTA_LINK_STATS null` 被当成 summary=None 后清空缓冲，既不报 BAD_JSON，也绕过严格 SUMMARY_MISSING。整块原始样本失去合法收口仍显示无致命发现。 | 严格采集入口要求有效观测；JSON null/非对象/无效收口必须保留错误和块归属，不能消除未收口检出。诊断空输入与可验收输入需明确区分。 | `empty_capture` 与带 9 条样本的 `null_summary` 均严格模式 exit=0、零发现。 |
| P34-P05 / P2 | `OTA-XC-BLE-TUNING` elapsedSeconds<=0 无效；PERFORMANCE 阶段统计与完整字段；`link_stats.py:373`、`:490` | 检查只覆盖部分计数字段和 ACK 分位数。elapsed=0 被合并；错误 GATT/发现/平台写分位数及 GET_INFO totalUs 均未核对；删 writeMode/mtuSource 仍 strictFieldsComplete=true。部分错误 JSON 类型还直接 TypeError，--json 无结构化输出。 | 完整声明必需/可空/旧版本字段、类型与范围；对可由样本重算的阶段指标核对，成功传输时间须有效。旧版兼容只能显式申报缺项，不能把部分字段检查称为严格完整。 | `zero_elapsed`、`wrong_phase_metrics`、`missing_binding_fields` 均 exit=0、零发现且进入合并；`counter_wrong_type`/`schema_wrong_type` 返回 1 但仅 traceback、无 JSON。 |
| P34-P06 / P2 | 当前发射端 R01 真实事件语义；`link_stats.py:403`、`:420`；`ota_link_stats.dart:263`；`ota_ble_transport.dart:1587` | 把所有时间戳类样本的打印顺序视为时间非递减，但 ack_early_invalid 是首发登记时重放更早的确认到达时间。合法单实例可先输出 ack_early、durable，再输出旧时刻的 ack_early_invalid，严格模式误判时钟回退/多实例。旧发射端夹具没有此新增形状。 | 按事件时间与发射时间的区别验证时钟，核对早到记录关联；不能为避误报一律放松真实时钟错误。补当前发射端的单实例、早到确认与 durable 交错正例。 | 按当前源码顺序构造 `ack_early(10) -> durable(11) -> ack_early_invalid(10) -> first_send(20)`，得到严格 CLOCK_NONMONOTONIC/exit=1；本例是源码语义构造，不宣称已执行 Dart 或设备观测。 |
| P34-P07 / P2 | 执行合同 §7/§7.3 harness 鉴别力须命中所称判据；`selftest.py:883` | 置空检查后捕获任意 Exception 都计为鉴别力成功。其中 _clock_segments 返回 None 使 len(None) 抛 TypeError；parse_sample 返回 None 使构造夹具时 samples[0] 抛 IndexError。三例未到目标检出断言，不能据此声称 25 条目标断言全部有效。 | 使用类型保持的局部变异，确认正例仍能解析；区分预期断言失败与构造/运行异常，并绑定具体检出，异常不得计为有效反证。 | 逐对独立审计得到 25 配对中 22 个 AssertionError、3 个无关运行异常：1 个 TypeError + 2 个 IndexError。原 selftest 仍对其汇总 PASS。 |

P34-P05 的错误类型返回非零，未被记成成功；问题是未生成声明的结构化结论，
不要与其同项列出的“错误观测仍零发现并合并”混为一谈。P34-P06 的 partial
本身仍不能证明测量完整，要求修的是错误的时钟归因，而非放行缺样本。

### 10.4 执行记录与可复现证据

宿主：Windows，Python 3.13.12，均使用 `cmd.exe` 与 `-X utf8 -S -B`，没有
安装依赖或调用 Flutter SDK。执行目录显式限定在项目根或交付 worktree。
本地诊断材料位于 `.cache/p3-4-parser-review-20260917/`；不是新冻结 bundle，
其中未入库诊断入口不得直接充当后续正式合同的隐式 runner。

| 入口/材料 | 实际结果 |
|---|---|
| `baseline.py` / `baseline.json` / `delivered-selftest.stdout.log` | 原 37 项自测及身份核对，exit=0；stdout/stderr/实际命令与 SHA 均已绑定。 |
| `adversarial.py` / `adversarial-results.json` / `cases/` | 19 个独立诊断输入：合法正例及删样本对照 2 项满足预期，17 个输入暴露上表问题，runner exit=1；不是 17 个独立根因或 17 轮正式验收。每例保存输入、命令、退出码、原始 stdout/stderr 及 SHA。 |
| `mutation_audit.py` / `mutation-audit.json` | 25 配对定向审计，22 个断言失败、3 个运行异常，exit=1；只临时改内存函数引用，finally 恢复，未改被验源文件。 |
| `capture_audit.py` / `capture-audit.json` | 只读重新解释已有双宿主捕获，记录逐块纳入范围及源 SHA，exit=0 表示审计完成，不表示合并合法。 |
| `checkout_audit.py` / `checkout-audit.json` | 四文件新检出字节一致、CRLF=0，临时检出已清理，exit=0。 |
| `evidence-files.json` / `final-audit.json` | 本次输出索引、文件 SHA、文档原有正文/行尾保全及被验 worktree 最终身份检查。 |

复现示例：在项目根运行
`python -X utf8 -S -B .cache/worktrees/p3-4-link-stats/Tools/ota/p3-4-link-stats/link_stats.py --log .cache/p3-4-parser-review-20260917/cases/duplicate_ack_offset.log --device-capture --json`。
该例应被拒绝，而当前 exit=0/零发现。诊断 runner 为防覆盖证据采用独占输出名，
不要在已有证据目录上盲目重跑整个 runner。

### 10.5 后续范围与未覆盖项

1. 实现者按 P34-P01 至 P34-P07 集中修复，先做解析器局部正反例、当前发射端
   形状及类型保持的鉴别力自测；保留默认诊断兼容性与严格测量判定的边界，
   不为维持“整份捕获 0 致命”而接受污染数据。无需因 Python 修复重建固件、
   重采旧 CI 日志或消耗设备额度。
2. 已有 `Validation` profile 覆盖 `Tools/ota/` 内入口、selftest 和夹具；
   `Evidence` profile 不覆盖本目录，不得仅绑定 Evidence 规避 runner 依赖。
   正式验收准备时按真实命令声明组件/基础组，外部捕获绑定源 SHA；不要把主树
   `.cache` 下的可选捕获变成未声明输入。本轮未改 profile 或治理门槛。
3. 本批阻断消除、自测稳定、必要开发证据齐备后，再审批版本化合同、冻结
   实现/runner 并跑 NOT_RUN 矩阵前检。当前没有原始独立 EXECUTED PASS，
   不能将 §9 自测或本节诊断填成 REUSED PASS。
4. §8.6 的 R04 后台复核范围、Flutter 当前发射端计数证据、APK/EXE 构建和
   设备门禁不在本次三提交解析器复核中被置 PASS；本次未查询远端计数恢复，
   也未改动原 CI 定时/重跑计划。AT、J-Link、烧录、安装、OTA、发布部署均
   未执行；P3-3-v9 和旧设备额度不变。

### 10.6 写入边界与结束审计

唯一获准活动项目根为 `D:\github\my\E-Track`。全部主动写入均在本节、
看板的两条追加以及项目内 `.cache/p3-4-parser-review-20260917/`；原 selftest
另在交付 worktree 的工具目录创建并删除 `_tmp_ok.log`、`_tmp_bad.log`，执行前
已逐一确认不存在且全父链无 reparse point。运行前审查了脚本写入/删除路径，
所有诊断输出有项目边界及 reparse 守卫，TEMP/TMP/TMPDIR 均定向证据目录内。

未调用 PowerShell，未设置项目外缓存/临时/日志输出，未改认证配置；未提交、
暂存、推送、合并、dispatch、下载/删除远端产物或操作设备。四个被验文件、
原捕获与交付 HEAD 保持不变，交付 worktree 仍 clean。原有主树脏文件不覆盖；
看板原有正文及 726 个 CRLF 行尾保留，仅新增本轮记录。临时检出及 selftest
两临时文件已确认无残留，未发现项目外主动写入。详细路径与哈希见 final-audit。
