# Transfer Screening After Group16

## 2026-10-14 Candidate Acceptance And Main Delivery Complete

Current independent result: `P3-4-v15` candidate-stage PASS, not production
release or completion of the P3-5/P5 campaigns. Source is `fcbace8b`; verified
local evidence bundle is `15a025b9c2690e864456a32fb2820422846fb85b` (8838 exact
raw Git blob checks). The final plan reuses one original v14 EXECUTED PASS and
executes 16 required offline commands for the other three criteria.

See [the existing closeout record](P3-4-v13-offline-acceptance-2026-10-13.md#candidate-stage-closure)
for criteria, original evidence, timing limits, authority and the real freeze
index. A/B and P34-HOST-CLOSE-01 are CLOSED. No new device operation or OTA is
needed for this accepted candidate scope; v11 HARNESS_FAIL, v12 EVIDENCE_GAP,
v13 scoped PASS, v14 partial EVIDENCE_GAP and the physical total 3/3 remain.

The user subsequently authorized the concrete PR/CI/main delivery. App,
governance and firmware CI passed on `719737d`; PR #26 was merged as
`17147e4265336945576ec218c8541079d4d8bf6c`, preserving the original commit IDs.
Post-merge App CI also passed. Main is checked out in p34-final; the shared dirty
tree is preserved on `archive/p34-root-before-delivery-20261014`, not reset or
mixed into the published result. See the [delivered result](P3-4-v13-offline-acceptance-2026-10-13.md#delivered-result).
Do not request the same authority or repeat this completed candidate acceptance.
P3-5 retains real-backend 10/10; P5-1 retains final 30/30 and a real four-hour
campaign; P5-2 assesses physical-fault applicability. Trial5 remains deferred and
unresolved. Device pause and production-release restrictions remain. Earlier
dated statements below are history, not the current admission or delivery state.

## 2026-10-12 验收操作经验速查

按用户要求整理 [首阶段验收经验速查](P3-4-stage1-acceptance-lessons-2026-10-12.md)：
只复用已有处置经验，不新增门槛、检查轮次或工具。涵盖调用失联、两类 DNS 失败、手机真实
就绪、已完成清理和 DAP 间歇风险；旧清理描述以最新收据为准。仅文档变更，未执行规划、
测试或设备操作，未提交推送；P3-4 状态及原冻结合同/矩阵不变。

## 2026-10-11 P34-LIVE-01-R1 测试夹具整改已自测

本次仅修独立报告的唯一阻断：原两秒窗口混入 Python 启动，可能未进入阻塞点即结束。
改为有界等待真实读取子进程的标记/PID，再验证既有 owner 限时终止；Windows 保留进程
句柄从未结束到已结束的状态变化，不能只凭 launcher 退出判绿。产品 prepare 预算及
Network.start/phone_cell 门禁测试不改。定向 1 项和完整 52 项均通过，实际子进程回收已验证。
证据 `.cache/p34-dns-fixture-fix-20261011/`，详见 [R1 整改记录](P3-4-DNS-host-remediation-2026-10-11.md#p34-live-01-r1-bounded-fixture-startup-handshake)。
原独立 51/52 失败、旧绑定及实网原件保留；本批只有测试源码变化，宿主实现未改。
未提交、推送、建隧道、操作设备或清锁；仍待独立关闭 R1，不代表 P3-4 完成。

## 2026-10-11 P34-LIVE-01 修正后真实入口已验证

用户要求先证实问题已解决再交复核。本次仅宿主调用实际 Network.start，未改动已经过
52 项自测的源码：一个新隧道在 19.877 秒通过正常 HTTPS、元数据身份与原 1 MiB 全字节
校验，两个读取退出均为 0，20.164 秒内完成服务关闭。本次未遇 DNS 暂态，不冒称实网
重试复现；重试和原预算超时仍由前批针对性测试证明。原始连接重置诊断保留并在报告解释。
证据 `.cache/p34-dns-real-20261011/`，详见 [整改及实测记录](P3-4-DNS-host-remediation-2026-10-11.md)。
2444 份保护原件无变化；无手机、OTA、烧录、提交或推送。宿主缺口已修复并实测，正式
验收及 P3-4 仍未完成；不清锁、不改冻结合同或 round2，不另开隧道或追加设备测试。

## 2026-10-11 P34-LIVE-01 最小宿主整改自测完成

用户本轮明确允许修正 DNS 启动缺口，范围仍仅候选内宿主代码。Network.start 保持同一隧道，
按原 prepare 绝对截止等待实际 HTTPS/完整包可用；只有已识别 DNS 暂态允许重试。复用既有
Process 限制单次读取（getaddrinfo 不受 socket timeout 单独约束），保留所有请求原件，
超时/其他错误关闭自有服务，不启动手机。App、固件、UI、Boot、门槛和冻结合同均未改。

新增 11 项真实 Network.start/调用链宿主测试，连同既有 41 项共 52 项通过，exit=0、未超时；
使用原 1 MiB 包做字节检查，没有真实隧道、OTA、设备操作或 PRE/长测。代码未提交推送，
仅交原独立验收者复核本项，再由原冻结执行者处理有来源绑定的最小接续；不能套旧合同重放。
报告见 [DNS 启动整改](P3-4-DNS-host-remediation-2026-10-11.md)，证据在
`.cache/p34-dns-remediation-20261011/`。已封存 round2 ENV_BLOCKED、失败锁和历史原件保留，
资格 0/1、校准 0/12 不变；DNS 根因未唯一确定，自测不等于现场通过或 P3-4 完成。

## 2026-10-11 环境恢复优先与接续准入复查

用户明确优先不改代码，撤回“必须先修 Network.start”的前置结论，下方方向保留为此前建议。
09:00 UTC 一次原样入口主机检查仍报 DNS 11001，未到手机/OTA；原件在
`.cache/p34-env-reentry-20261011/`，单个自有隧道已关闭，1484 个保护原件未变。
仍不能以旧域名或 API 域名的解析成功放行新下载地址；网络实际准入和已封存 round2 的受控
接续均须满足，不删锁、改矩阵或重放成功项。资格 0/1、校准 0/12 不变。详见
[DNS 跟进的最新裁定](P3-4-DNS-host-followup-2026-10-11.md)。无产品/runner 修改或新设备动作。

## 2026-10-11 DNS/HTTPS 纯主机跟进

用户明确同意仅继续主机排查。两次原样 Network.start 在约 6 s 均因新域名 DNS 11001
提前失败；保留同一隧道有界等待后，分别在 12.458/16.723 s 观测到解析成功，22.471/29.023 s
完成真实 HTTPS metadata 和完整原 1 MiB 包校验。未换 DNS/代理、清缓存或操作设备，所有自有
服务均关闭。P34-LIVE-01 已有可重复的就绪窗口证据，最小方向是原 Network.start 的实际
同域可用性等待，不是重装/重烧设备；冻结 runner 未改，后续接线与合同接续由原维护者/冻结者负责。

另主动披露 P34-DNS-IO-01：系统 curl 检索官方文档时产生两项项目外 Cryptnet CRL 缓存，
已停止该调用并保留原位，未获授权不清理。准确路径、实测原件及最小 oracle 见
[DNS 主机跟进](P3-4-DNS-host-followup-2026-10-11.md)。旧 round2 ENV_BLOCKED 矩阵/失败锁/报告
均未改写；不据主机恢复宣称资格、校准或 P3-4 完成。

## 2026-10-11 v2 首阶段现场收口：ENV_BLOCKED

本次独立验收按 v2 完整谱系前检与 execution-order 执行，未重做 PRE 或旧 initial/base。
Q-APK、Q-MAINT、Q-BAUD、Q-PRODUCTION 四项实测通过；首次 Q-TRANSFER 在新 HTTPS 域名
DNS 解析处失败，尚未启动手机采集或 OTA。唯一 round2 矩阵收口为 6 PASS（含两项直接历史
REUSED）、1 environment FAIL、41 NOT_OBSERVED；完整前轮参数的最终校验通过，仅证明该
ENV_BLOCKED 矩阵有效。实际资格 OTA 0/1、校准 0/12，未执行恢复或后段长测。

唯一新阻断 P34-LIVE-01 的原件、有限 Network.start 就绪方向、宿主正反 oracle 和责任人见
[本轮独立现场报告](P3-4-v2-stage1-live-acceptance-2026-10-11.md)。同一域名稍后可解析，但不
据此重建 tunnel 或盲重放失败命令。所有服务/工具已关闭；失败锁保留，最后本轮真实回读为
原 production base/unchanged group16 Boot、确认/健康/存储合格。原冻结执行者须消费实际 v2
矩阵和剩余配额，处理后继与最小复验；不得继续已封存 live 轮次或猜定后段参数。

首次资格与四档校准尚未完成，P3-4 仍进行中。trial5 原因未知/专项暂停不变，原实现认领不变。
无产品修复、正式 runner 修改、提交/推送/主干写入；仅一次必要的当前会话 USB 实体连接 @，
已核回执并观测到连接，不对正常最终交接重复提醒。下方“可交执行”描述保留为此前历史状态。

## 2026-10-11 v2 首阶段验收交付已补齐

原复核/冻结会话已在零设备操作下补齐接续：`P3-4-v2` 已审批冻结，完整前轮谱系的
标准 NOT_RUN 前检通过；标准计划确认输入组未变，Q-INITIAL/Q-BASE 两项复用，其余
46 项待执行，不重刷 base 或重做整改测试。实际 live 内部门禁及复用正反例亦通过。
v1 的 ENV_BLOCKED 矩阵和失败原件保持原字节；旧宿主锁经父/子收据及二次 owner 检查
确认只有只读 USB 查询失败，原字节归档后解除，未改设备状态。

首阶段执行包现可交独立验收 agent。唯一结果矩阵在 `.acceptance-p3-4/round2/`；按冻结
命令顺序过滤标准计划，第一条为 Q-APK，不重跑旧 initial/base。手机实时连接仍在现场
准入时核对；校准后由原冻结方绑定最终参数，验收方再做正式后段，不把宿主准备当成
整卡通过。完整接手方法、矩阵生命周期、原件、锁处理和边界见
[v2 验收交接](P3-4-v2-acceptance-handoff-2026-10-11.md)。P3-4 仍进行中。

## 2026-10-11 本批复核收口与现场范围更正

本批 PRE-06 阶段预算已独立验证关闭，41 项受影响测试通过，真实合同与 NOT_RUN
前检已完成。详见 [独立报告](P3-4-independent-phase-budget-review-2026-10-11.md)。
本会话把此前现场推进指令延伸到了最新只要求复核/合同/前检的批次，已提前做 Q-INITIAL
检查及一次 Q-BASE 安装；此处披露范围控制问题，不作为本批整改所必需的动作。
Q-APK 停在首条 exact-serial 查询，手机未识别，未查询/安装 APK、未执行 OTA。
只读 USB 观察结束且私有 ADB 关闭；已不再要求用户为本批连接手机，不继续新增现场动作。

实际证据矩阵现为 ENV_BLOCKED：2 个已执行 PASS、1 个环境 FAIL、45 个未观测；其最终
实物校验通过并不等于整卡 PASS。第一次错误前检、正确 NOT_RUN 原矩阵、所有真实动作
及失败原件保留。板卡实际保留经完整回读/健康验证的 613952 B production base，Boot
仍是 group16；未恢复旧 App、未安装维护/restore、未改速。后续先按真实范围和准入接续，
不重开 trial5，不要求实现方重复长测，不把整卡置完成。

## 2026-10-11 独立阶段预算关闭与阶段一执行

原独立会话已复核 `530a57c5fa00c702fc4d654ed40c494e20a20b21` 的 PRE-06 阶段预算及
直接依赖，独立 live 41 项通过；没有重复已关闭服务/统计/profile/固件/APK 或长测。
证据：候选 `.cache/p34-independent-phase-budget-review-20261011/` 与
`.cache/p34-independent-phase-budget-20261011/`。PRE-01/07 源码和 PRE-05 关闭结论保留，
trial5 仍原因未知、用户裁定专项延期，不据此豁免新的完整性/恢复失败。

真实阶段一合同 `docs/acceptance-contracts/P3-4-v1.contract.json` 已由本非实现会话审批
冻结，SHA-256 `04dcfee7ebb18851879d2911065c40837bd3136c650c40c01228d99c6b80ebdf`。
原第一次矩阵哈希大小写错误及失败前检保留；只修矩阵后，标准 NOT_RUN 前检真实通过，
退出码 0，原件在 `.acceptance-p3-4/round1/precheck-corrected/`。合同未原地修改。

首次设备操作 `CMD-Q-INITIAL` 已完成：原始完整回读匹配旧 C30286-nt/623124 B 及固定
65536 B group16 Boot；同一启动确认 state=4，健康计数推进，fault/SDIO/存储 owner
检查通过。栈 guard 完整，本次读取 high-water=3148 B；实际 JEDEC=0xef4018、16 MiB。
现有 staging 属于旧包、committed_target=30286，不匹配本次参考包，预期 BEGIN durable=0。
只读证据在 `.acceptance-p3-4/round1/ops/cmd-q-initial/`；这不是新候选的传输/恢复资格。

以下在首次设备变更前登记，执行仍保持开放：

- 授权/owner：当前用户 P3-4 任务和设备政策；本 Codex 独立会话唯一串行操作者，原实现
  认领 Claude 不变。唯一写入根为本候选；不提交/推送/合并/发布，不动共享根索引。
- 对象：C30286、J-Link 123456、手机 10ADA4197U001CK/V2312A、BLE E3:49:E1:14:D6:CB；
  完整工具/固件/APK/ETU 身份由冻结合同及 `.cache/p34-live-inputs1/inputs.json` 绑定。
- 有限矩阵：标准 J-Link 安装 finalized base、核对或安装精确 APK、维护握手并回生产；
  一次不计性能的合法 1 MiB 资格 OTA 与普通 Boot 回滚；支持的四档各三次校准及对应回滚。
  48 条精确命令和阶段判据见冻结合同，不擅自跳前驱或替换失败笔。
- 恢复：既有 restore 固件、640 B READY/committed mailbox 和普通 Boot 路线，核对完整
  App/Boot、EEPROM 配置与擦除 journal；不做 target-to-base 的 App-only 降级。
  本阶段最终保留经验证的 base，整卡后段成功后保留 target。
- 时限：真实 live 命令显式 `--seconds 3390`，各阶段及失败取证/关闭余量按合同；普通
  J-Link 180 s、Boot/回读操作 300 s 不改，不挪用用户等待时间压缩正常终态。
- 原件：实际 argv、stdout/stderr、闭环收据和设备原始字节在同一 round1；新完整性/
  恢复失败或状态不明立即暂停受影响变更，不盲重试、不重放成功 OTA 补日志。
- 人工：只在路线就绪且确需原 UI/弹窗/物理动作时按当前会话通知规则请求，不自动点屏。
  SEGGER 自动历史目录已取只读基线，其既有外写授权不包含清理。

阶段一不允许宣布整卡完成。最终 baud/timeout 只按同组原始校准结果计算，再审批直接
后继合同；30/30、4h、10/10 等必选后段仍待执行，不能用阶段前检或自测替代。

## 2026-10-11 PRE-06 Phase Budget Repair Self-Tested

The four affected files are committed locally as
`530a57c5fa00c702fc4d654ed40c494e20a20b21`, tree
`6923db3a5a2eca406788420220d78c8ae69b06da`, on
`acceptance/p3-4-v2-20261009`. Profile blob is unchanged:
`c1fd80a844680ac760ee0e3b9b70b86f84d6b136`. This batch was not pushed and did not
trigger another PR firmware/APK build. It is not an independent PRE-06 closure.
Existing board/note edits and independent reports were not included in the commit.

- `phone_cell()` now switches from click wait to transfer observation on this
  capture's actual upgrade-start, and to terminal observation on MCU publication.
  App snapshot, ordinary Boot, full readback and archive each have their own
  budget. The actual J-Link 180 s and Boot/readback 300 s command limits are
  unchanged. Startup checks the remaining owner lifetime before inviting either
  query/download or transfer. The derived default lifetime is 3390 s; it is a
  sum of upper bounds, not a delay, measured duration or relaxed BLE criterion.
- `Phone.cmd()` passes the remaining phase allowance to the real command owner,
  rejects late results and never extends the private ADB lifetime. Failure
  retrieval has a separate reserve. Collector death observed at the same poll
  as App completion is no longer hidden by an early loop break.
- Existing selftest entry, host only: final **41 tests, OK**, command exit 0,
  no timeout, 30.501 s including the owned launcher. The original 25+110+170 s
  case completes at 305 s; 140+170 s completes at 310 s. Full 180 s App waiting,
  long Commander/Boot/readback/archive calls, exhausted preparation, all phase
  expiries, lost/error health, missing metrics, missed preboot capture, actual
  exit 7, App failure and cleanup failure have explicit control-flow coverage.
  These tests do not certify hardware performance or the physical capture window.
- The initial regression run against the old entry retained 36 tests / 11 failed
  assertions, including the independent timing counterexample. The final run
  also adds ADB deadline and terminal-evidence negatives. No failed log or old
  independent probe was rewritten to pass on the new code.

Evidence is candidate-local `.cache/p34-phase-budget-20261011/`: `red/`,
`green1/`, `final/`, `git/commit.json`, and `source-lock.json` (SHA-256
`694e7da1f6977c5b3789652f29166703659a34cb709f4596ad20f66b698dcde2`).
The final test log SHA-256 is
`d4aaa82eca845266e5a48dc5be2f468ecf4a616d50061fee7feccb635a7bdfc0`.
All 19 original assets were size/hash verified unchanged; their build source is
still `1c3f7f49`, not this host commit. The existing live input JSON is unchanged.
Parent v5 remains historical registration for the parent source, not a claim
that its old runner-byte records match this changed worktree.

Root's handoff is `D:/github/my/E-Track/.cache/P3-4-live-budget-handoff-2026-10-11.md`.
Only the original independent session's review of this finding/direct dependencies
is next. No service/statistics/profile/firmware/App campaign is reopened. Trial5
remains unknown/deferred; contract, first live qualification and formal matrix
remain NOT_RUN. No devices, remote CI, deployment or manual mention were used.

## 2026-10-11 PRE-06 Phase Budget Repair In Progress

Root is implementing only the remaining live-route finding against `352ad286`.
The independent 25+110+170 second counterexample is a host orchestration defect:
one 300-second timer includes user wait, transfer and the App's separate
180-second identity window. Helper-only tests missed the full `phone_cell()`
path. The repair uses observed upgrade-start and MCU terminal publication to
switch finite phase budgets, with startup admission for the remaining ADB
lifetime and separate snapshot/Boot/readback/archive/failure reserves. Command
timeouts must respect the active phone phase rather than outlive its owner.

Self-tests will exercise the real entry and filesystem/lock path with synthetic
device I/O and a controlled clock: long valid completion, exhausted preparation,
real phase expiry, collection/command errors and immutable failure retention.
No App/firmware/ETU/service changes, device operations, asset rebuilds or long
tests are needed. The original independent counterexample and all old evidence
remain unchanged. PRE-05 and PRE-01/07 closures and trial5's unknown/deferred
status remain; formal contract and live matrix are still NOT_RUN.

## 2026-10-11 PRE-05/06 现场接线独立复核

本批 `352ad286` 集中复核完成，正式准入未通过。PRE-05 的真实 1 MiB PATCH 服务整改已
验证关闭；PRE-06 的实际入口入库及 14 条传递依赖已绑定，但 `live.phone_cell()` 的
start-ready 后 300 s 硬窗口会混用点击等待、传输和 App 的独立 180 s 重启复核时间。
独立无设备反例：25+110+170 s 应在 305 s 完成，却在 300 s 关闭，finished/archive 未调用；
增大 --seconds 不能绕过硬上限。原宿主维护者只需修阶段预算与启动前余量准入，补实际
phone_cell 的时钟集成测试；不要改 App 窗口、放宽门槛或代做长测。

完整发现、最小方向、oracle 和责任人在
[独立报告](P3-4-independent-live-route-review-2026-10-11.md)。证据位于候选
`.cache/p34-independent-live-route-20261011/`：373 条来源/输入登记全部匹配，独立服务
6 tests 与现场入口 25 tests 通过，CI 原 ZIP/日志/exit 和五类离线绑定已直接核验，4 个
时序场景保存当前缺口。19 项原设备资产及其 `1c3f7f49` 构建归属不变，无需重建。

本会话未代写产品或正式 runner 修复。PRE-01/07 源码关闭、trial5 原因未知/专项延期及
trial6 续传分类均保留；合同未冻结，首次现场、30/30、4h、10/10 仍 NOT_RUN。
修正后只复核受影响项，再继续真实合同前检和唯一正式矩阵。没有设备/安装/OTA/AT/复位/
CI/提交推送/手动 @。当前 relay 实测无绑定，未自动送达 root；报告用于原 root 有限整改，
不是要求用户操作手机或重新全面准备。

## 2026-10-11 PRE-05/06 Live Route Remediation Delivered

The necessary ten source/test/CI files are committed and pushed at
`352ad286a26fc49255a132e00b93090527253747`, tree
`b1aabff9f2060fdaa4208a74e304514cfab5bf7e`, profile blob
`c1fd80a844680ac760ee0e3b9b70b86f84d6b136`. PR #26 remains draft and unmerged.
Existing operational note/board edits and independent reports were not staged.
This is implementation delivery for the original independent session, not a
declaration that PRE-05/06 are independently closed or that P3-4 is complete.

- PRE-05: the controlled service accepts the actual fixed 1 MiB PATCH, with exact
  raw base/version matching, canonical kind/name, outer ETU bounds/CRC and existing
  token v2/Range/full behavior. Real loopback HTTP retrieves identical original
  package bytes. Wrong base (including the same sha8 with a different full SHA),
  kind/name, size/hash/header and token are rejected. No P4-2 backend was added.
- PRE-06: `Tools/ota/p34-acceptance/live.py` and its three adapters provide the
  standard Commander/RTTLogger/private-ADB command route. They bind exact assets,
  ELF/map/accessors, tool companions and actual command arguments. They cover
  safe same-version installation, maintenance baud handshake/retention, guarded
  restore mailbox plus ordinary Boot rollback, fresh runtime/query/download,
  immutable per-process App captures and a single-host monotonic observer.
  Only an owned verified capture is archived and pruned. Uncertain operations
  keep their lock and raw output; a new directory does not authorize a replay.
- End-of-transfer stack/clock evidence is sampled after the real terminal metrics
  line, before the old App reboots. Header/VTOR/metric/tick/guard checks reject a
  missed window instead of substituting the new boot's stack. Initial BCB evidence
  is explicitly the current-boot confirmation snapshot, not a fabricated EEPROM
  dump. The physical disconnect is an operator action to be made exact in the
  frozen matrix; this entry never substitutes cancellation/global Bluetooth-off.
- Local service 6 and live-route 25 tests pass. The isolated real CLI and five
  retained image roles pass offline ELF/objcopy/map/ABI binding. Standard validator
  APIs check all 14 actual runner paths and the committed worktree with no errors;
  this API check has no approval or matrix and is NOT a formal NOT_RUN precheck.
- Governance CI `38067344494` passes; both original artifact ZIPs and their exact
  logs prove service 6/live 25 on Linux and Windows. Automatic PR firmware
  `38067344438` and APK/EXE `38067344483` also pass; registration/Release/Pages are
  skipped. No extra Flutter development push or debug-APK dispatch was requested.
  Automatically built CI binaries do not replace any selected device asset.

New source registration, relative to the shared root:
`.cache/p34-route-20261010/source-lock-v5.json`, SHA-256
`5f38ebc0d215f96adbfe6d0188248ee1e8d86424d36070e07a0501b6cc96bcdf`.
It supersedes, without changing, v4. All 19 selected assets are unchanged; their
source is still `1c3f7f49`, not the new host commit. Production/Firmware/Flutter
input objects are unchanged under the approved profile. The original selected
candidate/maintenance 641 warnings and restore 643 warnings, all zero errors,
remain recorded. No firmware/package/APK installation, OTA, reset, AT or SD action
was executed by this batch. Historical trial6 remains a resumed small transfer.

Original local evidence is in candidate `.cache/p34-route-tests4/service/`,
`.cache/p34-route-tests6/live/`, `.cache/p34-live-inputs1/offline3/` and
`.cache/p34-route-profile1/`; CI originals and receipts are in shared-root
`.cache/p34-route-20261010/ci/`. Earlier outputs are retained. In particular,
tests3 record a file-reader indentation regression and an incorrect clock-symbol
name; both were repaired and rechecked, not deleted or called hardware failures.

Next handoff: shared-root `.cache/P3-4-live-route-handoff-2026-10-11.md`.
The original independent session reviews only this batch and direct dependencies,
then freezes the actual P3-4-v1 contract/commands if admitted and executes the
first live qualification and single formal matrix. PRE-01/07 source closure and
trial5's unknown, deferred cause stay unchanged. Formal contract, first live
qualification, 30/30, 4h and 10/10 remain NOT_RUN. No manual mention or automatic
relay delivery is claimed; the current route has no bound independent target.

## 2026-10-10 PRE-05/06 Live Route Batch In Progress

The independent PRE-06 review closed the statistics/profile batch at `6942ae06`.
Its next-entry audit found two real missing links: the controlled service rejects
the selected PATCH, and the old device command chain lives outside the candidate
tree. Root is addressing only these links. Preserve all previous closure evidence,
trial5's deferred investigation and the unchanged 19 selected assets.

Use the existing single-asset service with strict full raw base matching, token
v2 and Range/TLS behavior; no P4-2 backend or PATCH-as-full workaround. Normalize
only the necessary standard Commander/RTTLogger/private-ADB operations, using the
existing host_io and process ownership primitives. The earlier cache observers
are read-only examples, not runnable dependencies or new Flash algorithms.
The bounded host oracle covers real loopback HTTP and negative device-adapter
fixtures; initial hardware qualification stays with the independent operator.
Outputs are under shared-root `.cache/p34-route-20261010/` and candidate-local
test directories. No phone/MCU operation, asset rebuild or long campaign is part
of this source remediation batch; formal admission remains pending.

## 2026-10-10 PRE-06 Independent Closure And Formal Route Gaps

Independent review of `6942ae068f6c57b1b42c679a2ebe039d5b9b0fef` closes the
review2 statistics and four exact profile exceptions. The original GET_INFO/5
discriminators now behave correctly without byte changes; 13 statistics tests
and the two new profile/Git-object mutation tests pass. All 171 directly
registered local files match; actual Production/Firmware/Flutter build inputs
and the 19 selected assets remain unchanged from `1c3f7f49`. Both complete CI
host logs match their archived ZIPs and execute the real service recovery test.
The recorder and RC3-07 failures remain preserved, not product fixes or hardware
evidence. PRE-01/07 source closure and trial5's unknown, deferred cause remain.

Continuing into the actual formal route exposed two remaining admission gaps:
PRE-05's specified `Tools/ota/p3-3-service/service.py` rejects the selected real
1 MiB PATCH because `Release._validate()` supports only full. PRE-06's historical
device/collection entries still require shared-root `Tools/ota/p34_session.py`
and consumed `.cache` adapters absent from the candidate commit. Do not relabel
the PATCH as full, replay old wrappers, or replace the available standard SEGGER
tools. Root must provide only the necessary accurate PATCH service and committed
standard-tool command/thin-adapter bindings, with bounded host positive/negative
tests. No duplicate implementation-side long campaign or unrelated rebuild is
requested. First live state/rollback qualification remains independent work.

Full findings, minimal directions, oracles and owners:
`docs/ota-exec-notes/P3-4-independent-pre06-review-2026-10-10.md`.
New evidence: candidate `.cache/p34-independent-pre06-20261010/`.
P3-4-v1 is still NOT_FROZEN; NOT_RUN precheck, first live qualification and the
single formal matrix have not run. No product edits, device operations, CI
dispatch, Git publication or manual mention occurred. Current-chat relay target
discovery returned no binding; no task was automatically delivered to root.

## 2026-10-10 PRE-06 Review2 Remediation Delivered

The finite review2 batch is implemented and self-tested at
`6942ae068f6c57b1b42c679a2ebe039d5b9b0fef`, tree
`67978f75d86c3b1522175b841aa881d90cf38230`, profile blob
`c1fd80a844680ac760ee0e3b9b70b86f84d6b136`. The acceptance branch and
`dev/flutter/p34-admission-20261010` both point there; PR #26 is still draft and
unmerged. This is implementation delivery for independent PRE-06 re-review,
not independent closure, formal admission or P3-4 completion.

- `acceptance_stats.py` accepts actual GET_INFO `0x00`/10-byte writes and rejects
  undefined `0x05`. A successful current capture requires successful GET_INFO,
  BEGIN and END writes, plus CAPS2 for v2; missing control/GATT accounting fails.
  The original independent synthetic probes now give the expected opposite
  results without editing their bytes. See `query-regression.json` below.
- Recovery consumes the service's exact `transfer` stage and
  `transport:DISCONNECTED` / `transport:DEVICE_LINK_CHANGED`, preserving the raw
  reason. Bare/substring reasons, cancellation, ABORT, wrong stage and ordinary
  success do not qualify. All ten recovery pairs must share one parameter/asset
  group; mixed baud, timeout, retry or asset groups cannot pass the total gate.
- The four omitted inputs now have exact top_files/required_paths exceptions:
  `p34-acceptance/build.py` in Validation, the three Gradle inputs in Production
  and Flutter. Generated build/cache files remain excluded. Standard profile
  enumeration and complete helper dependency binding have no errors; Git-object
  mutation tests use the normal rerun API and preserve unrelated consumers.
- The v2/schema10 transport test now performs real `getDeviceInfo()` before
  transfer/export/statistics. A separate actual service test records a native
  write disconnect after 4096 durable bytes and resumes an 8192-byte v1 fixture
  through two real snapshots and the statistics CLI. It counts one recovery,
  not a 1 MiB checkpoint or the ten-recovery gate. No runtime sender was changed.

Local original tests pass: statistics 13, bundle governance 116 and dependency
efficiency 33. Final CI runs pass: development 38047820907, governance
38047823595, firmware 38047823559 and PR APK/EXE 38047823551. Ubuntu has 722
passed / 16 skipped; Windows has 705 passed / 33 skipped; both report zero
failed tests and successful analyze. Original full tests.log files, exact new
test lines, SDK identities, raw CI ZIPs and job metadata are retained in shared
root `.cache/p34-pre06-20261010/ci-final/` and `ci-final-summary.json`.
The console excerpts were truncated; the full archived tests.log files were not.
APK/EXE build jobs succeeded; Release and Pages were skipped. No debug APK was
requested and none of these CI artifacts replaced the selected device assets.

Preserve the actual failure history: `4838dd13` first exposed a new test fixture
reusing a sealed one-upgrade OtaDiagnostics; `c9fb0291` corrected this with a fresh
recorder for resume. That revision passed the new tests but Linux hit an existing
RC3-07 fractional-millisecond deadline race (expected NO_DURABLE_PROGRESS, actual
TIMEOUT). `6942ae06` rounds positive timers up only inside that test's zone;
the failure-code and retry-count assertions remain. This is a test-clock repair,
not a claimed production timing fix. Original logs and scope are bound by
`fixture-failure.json` and `timer-test-scope.json`; earlier failures were not erased.

New source registration, relative to the shared root:
`.cache/p34-pre06-20261010/source-lock-v4.json`, SHA-256
`030559344ee3fdf80c5e5e2d1d2161c6136b84be36f02feb238d0f74eb732afb`.
It supersedes but does not overwrite v3. `identity-final.json` shows no actual
Production/Firmware/Flutter runtime or build-input change from `1c3f7f49` under
the corrected profile. All 19 selected assets still match their original hashes;
their source commit remains `1c3f7f49`, not the new statistics/test commit. Reuse
the existing 613952-byte raw/base/target/reference/restore set and diagnostic APK.
The original candidate/maintenance builds have 641 warnings, restore 643, all
zero errors; do not present them as warning-free or substitute CI firmware bytes.
The original trial6 remains resumed (first DATA 45056), not full-zero-start or
formal ACK-eligible evidence; current read-only output is `trial6-current.json`.

Next owner is the independent reviewer, using the new shared-root handoff
`.cache/P3-4-pre06-remediation-handoff-2026-10-10.md`. Recheck PRE-06 and its direct
dependencies, including the test-clock change; do not reopen source-closed
PRE-01/07 or trial5's deferred causal investigation without new evidence. If
admitted, continue the real P3-4-v1 contract/NOT_RUN precheck, first live
qualification and the single formal matrix from review2 section 4. These are
still NOT_RUN; do not demand a duplicate implementation-side long campaign.
No device, installation, OTA, reset, AT, merge, release or manual mention occurred.
The current chat has no bound cc-connect relay target, so automatic handoff was
not possible; the user must forward the handoff to the original independent
session. Normal final delivery uses only the bridge's completion notification.

## 2026-10-10 PRE-06 Review2 Remediation In Progress

Root is implementing the finite batch from
`P3-4-independent-remediation-review2-2026-10-10.md`: correct the GET_INFO wire
table, consume the service's actual transfer failure reason, require one recovery
parameter/asset group, and register the four specifically omitted build inputs.
Tests will exercise the real transport GET_INFO and service snapshot paths rather
than inventing another command/reason vocabulary. Add exact profile exceptions,
not a global build-output exclusion relaxation. PRE-01/07 stay independently
closed at source level; first live qualification and the formal matrix stay
NOT_RUN. Trial5's separate causal investigation remains deferred.

This batch does not change firmware or App runtime. Reuse the selected BIN,
reference/restore set and APK after proving runtime/build inputs unchanged; no
installation, extra OTA or debug-APK dispatch is planned. New root evidence is
`.cache/p34-pre06-20261010/`; preserve all earlier reports and source locks.

## 2026-10-10 Second Independent Remediation Review

Independent review of `1c3f7f49` is complete; formal admission is still blocked.
See [the second review](P3-4-independent-remediation-review2-2026-10-10.md) and
`.cache/p34-independent-review2-20261010/`. All 119 registered files match, and
909 actual GCC repository dependencies are covered. This session ran MCU metrics
5 tests / C core 14 checks, batch 9, formal statistics 10 and snapshot 31 tests.
Both CI host originals and APK/EXE job metadata were checked, not treated as
automatic closure. PRE-01's production observation implementation and PRE-07's
filtered-error chain have closure evidence; their first live qualification is
not a prefilled PASS. Trial5 remains cause-unknown with its separate work deferred.

Keep PRE-06 open for one bounded batch: the statistics table rejects the actual
GET_INFO command 0 and accepts undefined command 5; recovery counting misses the
service's `transport:DISCONNECTED` reason and allows mixed-parameter ten-pair
qualification. Independent synthetic probes preserve all these outcomes.
The frozen profile also excludes the actual `p34-acceptance/build.py` helper and
the three Android/plugin Gradle build files through its `build*` filter. Standard
validator API returns an unbound-runner error when the helper is declared honestly.
The report gives exact paths, smallest repairs, positive/negative oracles and owners.

Next owner: root and the original runner/profile maintainers, not another full
hardware preparation campaign. Submit the bounded fixes and affected tests; the
independent operator then continues P3-4-v1 freeze/NOT_RUN precheck and the one
live matrix. No duplicate implementation-side 30/30, 4h or 10/10 is requested.
No product/runner fix, device operation, formal freeze, Git publication or manual
mention was performed by this review. All formal hardware remains NOT_RUN;
original claim, earlier reports, failures and existing task edits are preserved.

## 2026-10-10 PRE-01/06/07 Implementation And CI Delivered

The three requested admission remediations are implemented and self-tested at
`1c3f7f49baa27c42452f7796839cea57ddd734b7`, tree
`765d607ace0ce3d4908e673b536a04f6631db3de`, profile-config blob
`a4355236f2d53235d0b144c3bceb70618f05a4da`. Both the acceptance branch and
`dev/flutter/p34-admission-20261010` point to that commit. PR #26 remains draft
and unmerged. This is delivery for independent re-review, not closure of the
reviewer's findings, a frozen contract, hardware qualification or P3-4 PASS.

- PRE-01: bounded 420-byte/schema-1 production MCU metrics cover payload/journal
  read/program/erase/verify, actual UART RX IRQ body and ACK TX. Experimental BLE,
  baud, install and RTT down controls remain OFF. Clock/overflow, acquisition/
  freeze, unknown initial state and first-error behavior are explicit. Reuse the
  standard RTT logger and matching map; nested inclusive costs are not additive
  savings. MCU decoder 5 tests, C core 14 checks and actual UART IRQ 202 checks pass.
- PRE-06: v1/v2 geometry and schema 10 are supported. The formal thin entry is
  `acceptance_stats.py` over the existing strict `observation_capture.py`.
  Actual BEGIN/control/DATA/durable accounting, nearest-rank P99, stable groups,
  failures/missing samples, unique-DATA retransmission denominator and recovery
  pairs are covered. Normal retries remain in the same business/latency pool.
  Batch/statistics tests are 9/10; strict snapshot tests are 31, all passing.
- PRE-07: bounded raw filtered ACK errors and sealed counts retain six distinct
  ownership classes, without changing credit/durable or active firstError.
  Matching/error prefixes reach the actual snapshot and strict reader. Real
  transport-to-snapshot-to-Python tests and a complete synthetic v2/schema-10
  transfer pass on both CI hosts; these are host oracles, not hardware results.

Final CI runs all passed: development push 38031160555, firmware 38031162380,
governance 38031162315, PR APK/EXE 38031162314 and diagnostic APK 38031649785.
Ubuntu reports 721 passed / 16 skipped; Windows 704 passed / 33 skipped.
The Android/Windows build jobs succeeded; Release/Pages were skipped. Original
CI logs, job metadata, dual-host reports and the new APK are retained at shared
root `.cache/p34-remediation-20261010/`, including `ci-final-summary.json` and
`final-archive/`. The initial f354 lint failure is preserved, not relabeled green.

The selected local App-only build is `.cache/p34-build3/`: raw BIN 613952 bytes,
SHA `7e556d3f9bc3d689a46648fd1c5e27cbe833a99fd2776ba1fb28bee983ebafa1`,
641 warnings / 0 errors. Ubuntu's actual candidate is 613964 bytes with a
different SHA; do not substitute it into the selected reference/restore set.
Fresh base/target/1 MiB inputs are in `.cache/p34-reference2/`; the real C decoder
passes byte equality and four rejection cases. Restore's 18 host checks pass;
its 613952-byte/CRC32 2889683253/base-SHA binding is rechecked. Finalized maintenance
and restore images are in `.cache/p34-maintenance-images2/`, built by
`p34-maintenance-build2` (641 warnings) and `p34-restore-build3` (643 warnings),
both zero errors. Boot was not rebuilt or modified. No image has been installed.

The new APK is 131722750 bytes, SHA
`858b6bd8811d3c2baaf758d0f99bb7e472192e693650018d00fd3cd3273ef68f`, from this exact
commit, with the expected p34probe application ID and fixed development signing
certificate. It is not the old 691aa3df APK. The compiled `.invalid` service URL
remains an explicit runtime-required placeholder, not a ready HTTPS service.

New artifact/source registration (all paths relative to the shared root):
`.cache/p34-remediation-20261010/source-lock-v3.json`, SHA
`4929eba892d46497d9475cfe2503696cf4bbae34f57c0c246dd47e5169ea01e3`.
It binds 19 assets and 82 development receipt/log files, the actual CI/APK reports
and README; it does not replace Git-object input groups or formal approval.
Candidate `.cache/p34-identity2/` confirms the 420-byte symbol and all 909 actual
repository GCC dependencies; 40 KiB overlay, 8192-byte stack and 32-byte guard
remain. The standard API check has no worktree/profile errors but is not a
FROZEN-contract/NOT_RUN precheck. The final CLI reinterpreted the unchanged trial6
original into shared-root `trial6-final.json/.log`: first DATA 45056, 1965 unique
segments, still resumed/small, fullZeroStart/reference/ackEligible all false.

Next owner: independent acceptance agent. Read the prior remediation report and
shared-root `.cache/P3-4-remediation-handoff-2026-10-10.md`, recheck this bounded
batch and affected inputs, then freeze actual commands and execute first live
qualification plus the single formal matrix. The implementation side did not
repeat 30/30, 4h or 10/10. All remain NOT_RUN; trial5 remains cause-unknown with its
separate investigation deferred. No device, manual mention, merge or deployment
occurred. Existing task-note edits and independent report were preserved; the
new closeout text is local operational history, not a claimed main integration.

## 2026-10-10 PRE-01/06/07 Implementation Batch

Owner: Codex root, continuing under the user's instruction to implement the
three remaining admission fixes. Original card claimant and independent review
remain unchanged. Worktree: `.cache/p34-final`, starting at `625e0a58`.

- PRE-01: the production image really has no MCU timing port. Reuse the existing
  staging IO wrappers and DWT clock, but not the experimental baud console.
  Add a bounded read-only production metrics snapshot, explicit clock/overflow
  validity and session boundary; qualify it on host and bind its final ELF/map.
- PRE-06: keep the strict snapshot reader. Extend the existing timing entry for
  v2/schema 10 and add formal run/group accounting over original snapshots.
  Validate real BEGIN state, wire bytes, durable ACK latency, failures and missing
  samples. Do not reinterpret a resumed/small run as a clean 1 MiB result.
- PRE-07: retain filtered ACK errors by bounded category with original fields,
  without changing matching, credit, durable state or first matching error.
  Exercise transport -> real App snapshot -> strict Python reader in CI.

This is one implementation/self-test batch, not a new acceptance round. No device
operations, trial5 causal investigation, sender redesign, UI change or historical
evidence rewrite. Firmware changes require fresh paired reference/restore assets;
old source locks and successful CI remain historical, not this batch's results.

## 2026-10-10 Independent Remediation Review

The independent review of candidate `625e0a58` is complete, but formal admission
is not passed. See [the consolidated report](P3-4-independent-remediation-review-2026-10-10.md)
and candidate `.cache/p34-independent-review-20261010/`. All 26 registered inputs
matched; all 907 in-repository GCC dependencies are covered by the frozen profile
definition. The current-candidate receiver matrix passed 327 checks across ten
modeled cases, its source-mutation negative fired, and the existing snapshot reader
passed 30 host tests. These are admission checks, not formal hardware PASS.

Keep the same PRE IDs. Remaining bounded work is PRE-01's actual production MCU
measurement route, PRE-06's v2/schema-10 statistics adapter, and PRE-07's retained
late-error evidence. Do not redo the whole campaign on the implementation side.
Trial5 remains unexplained and its separate causal investigation stays deferred.
No contract/commands were falsely frozen; live state/rollback qualification and
the single formal matrix remain NOT_RUN. No device, CI, Git publication or manual
mention was performed in this independent review; original claim and evidence stay.

## 2026-10-10 Final PR Checks Passed

Current source is `625e0a58d4f08e85d647b6e9d0521970312e69f6`, tree
`fa1a93d09e545ad67e9925a642f492c602edc44c`; profile-config blob remains
`a4355236f2d53235d0b144c3bceb70618f05a4da`. PR #26 stays draft and unmerged.
Final firmware CI 37983524994, governance CI 37983524840 and App build CI
37983524854 all passed. Android APK and Windows EXE tests/build/upload succeeded:
Ubuntu 713 passed / 16 skipped; Windows 696 passed / 33 skipped. Full original
logs and job/artifact metadata are archived in shared-root
`.cache/p34-integration1/delivery1/` as `*-final.*` and `ci-final-summary.json`.

The last failure was test-fixture placement, not an OTA/device failure:
ordinary App CI had system TEMP outside the worktree, so the strict snapshot
extractor correctly rejected that output. The fix moves this test's fixtures
under the App's `.dart_tool/ota-service-tests/`; it changes no runtime code and
does not weaken the guard. Both original failed jobs remain in `app-pr-failed.*`.
The existing validator confirms clean base profiles and no Flutter runtime
profile difference from the retained debug APK source, but this check is not
the still-required FROZEN-contract/NOT_RUN-matrix precheck.

Use `source-lock-v2.json`, SHA-256
`8a767931a0dcd947961f3863d460ceb4502df3a8e7ed02211f30d7d507908992`,
instead of the predecessor source register. The selected local firmware,
reference package, finalized maintenance images and debug APK are unchanged.
The temporary independent handoff has been updated to this final source and
these real CI outcomes. It still explicitly requires the independent operator
to freeze actual commands/contract and qualify the first live initial state;
formal hardware remains NOT_RUN. No new device operation or manual reminder.

## 2026-10-10 Published Candidate; Independent Admission Handoff

The scoped candidate is committed and pushed at
`38bd66eab3f20aec22844306e43c5ca210aad1e3`, tree
`90f68ab335a47e683f15700a164cd4df9f85e552`, profile-config blob
`a4355236f2d53235d0b144c3bceb70618f05a4da`, on
`acceptance/p3-4-v2-20261009`. Draft PR:
https://github.com/Eitan-S-23/E-Track/pull/26 . No merge, release or deployment.
The complete App tree matches the already-tested `691aa3df` development commit.

Firmware CI 37980146495 passed, including the actual P34_OTA_CANDIDATE build;
governance CI 37980146534 passed. Full original logs and the candidate artifact
are archived under the shared root `.cache/p34-integration1/delivery1/`.
The first failed runs remain preserved. Their two integration defects were an
old v1-only static command enumeration and a profile test missing the two real
production Tools headers. The current check preprocesses both configurations,
reuses the unchanged 47-check v1 oracle and checks the approved v2 supplement,
including nine mutation/negative tests. The profile target and portability
check also passed locally in the candidate's `.cache/p34-ci-fix1/`.

The selected local GCC raw App remains 612020 bytes with 641 warnings and zero
errors. The Ubuntu candidate build is 612024 bytes with a different SHA; do not
claim cross-host byte equality or replace the local base/PATCH/restore inputs
with that CI BIN. Both variants and original hashes are recorded. No new build,
package generation or hardware experiment was used to hide this distinction.
The maintenance/restore images now have valid headers, generated by the existing
finalizer without executable-body changes; they remain uninstalled and require
first live qualification. See candidate `.cache/p34-maintenance-images1/`.

Current artifact/source registration is shared-root
`.cache/p34-integration1/delivery1/source-lock.json`, SHA-256
`391d9f628fec9e66b57a7ac9184dfe2fb4e435cf962dad8cd36c7e4ce1a09f7e`.
This is an asset register, not a replacement profile manifest or FROZEN contract.
The independent handoff is shared-root
`.cache/P3-4-independent-acceptance-2026-10-10.md`. It fixes the same-package
three-run-per-supported-baud screening, separate P99 timeout selection, one
final 30/30 group, four-hour soak and ten reconnect recoveries. It explicitly
assigns first state/rollback qualification and final command/contract approval
to the independent operator; the implementer does not duplicate that campaign.

Remaining admission is real, not waived: bind the actually used collection and
baud commands/runners, approve the v3 contract with these real source objects,
and pass its NOT_RUN execution precheck before formal commands. Prefer the
standard J-Link/ADB and existing snapshot reader, not another general-purpose
controller. Necessary new runner code must be committed before freezing; first
hardware observations must not be required to pass in advance. P3-4 is still in
progress, with formal hardware and equivalent-state qualification NOT_RUN, not
formal READY/PASS. No manual @mention or device action occurred in this delivery.

## 2026-10-10 Acceptance Publication Authorized

The user's latest authorization covers the scoped candidate/dependency commits,
push to `acceptance/p3-4-v2-20261009`, a pending-review PR and the necessary CI.
It supersedes the earlier pending-permission entries below. No merge, release,
deployment or duplicate manual @mention is requested. Shared root HEAD/index
and unrelated edits remain untouched; integration uses `.cache/p34-final`.

The current candidate is the 612020-byte build in that worktree's
`.cache/p34-build1/result.json`, not the older 611892-byte preparation below.
Retained UART configuration preserves the same executable/package across the
four admitted rates. `.cache/p34-reference1/result.json` binds the legal exact
1 MiB C30286 -> C30287 pair; `.cache/p34-restore-test1/result.json` and
`.cache/p34-restore-build1/result.json` bind its 18-case rollback self-test and
App-only helper. Installation and equivalent-state qualification remain NOT_RUN.

App source `691aa3dff7691ec3763bc6a36fba74177e3dd004` adds only the required
230400/ACK-timeout configuration. Both development hosts and the requested APK
passed run 37971316004. Original logs and the uninstalled APK are archived under
the shared root `.cache/p34-integration1/flutter-config1/`. Existing successful
self-tests are retained, not repeated. The task PR additionally builds the
actual P34_OTA_CANDIDATE configuration; a default-build green result alone is
not candidate evidence. Formal hardware acceptance remains NOT_RUN.

## 2026-10-10 Notification Rule Correction

This turn is limited to the user's notification-rule correction. A manual real
@mention requires an already-authorized action outside chat, a continuing
execution, and no required chat reply. Authorization, choices, confirmation and
missing information requested in chat belong in the normal final reply and use
the bridge's automatic completion notification. Keeping another task or worker
running does not create an exception. Observe physical/device actions rather
than requiring an acknowledgement in chat.

Root AGENTS, the collaboration contract/index/PROJECT-06, the Flutter debugging
skill and its device-session reference, and the governance regression were
updated in the shared root and the owned `.cache/p34-final` worktree. Four
targeted tests passed in each tree; original logs are at
`.cache/p34-notification-rule-20261010/{root,candidate}.log` in the shared root.
No firmware/App change, build, CI request, device action or manual reminder was
performed for this correction. The earlier PR/CI permission reminder and its
receipt remain preserved as a mistaken notification, not a precedent. The
user's request to correct this rule does not authorize that pending PR/CI action.
P3-4 remains in progress; this is not a formal acceptance or mainline delivery.

## 2026-10-09 Acceptance-Only Direction

The user explicitly stopped further trial5 root-cause work and asked for only
the work required to hand P3-4 to acceptance. Keep the original failure as an
unresolved historical risk; do not classify it as operator error or repaired.
It no longer requires a separate causal investigation before candidate
preparation and submission. Any new failure in the formal plan is retained and
handled under the unchanged failure/credit/integrity rules, not erased by a
later success. No new receiver diagnostics, tuning or speculative fixes.

The remaining sequence is one reproducible candidate, legal 1 MiB/equivalent
initial-state inputs, then one independent formal campaign. The implementer does
not run another 30/30, four-hour and 10/10 campaign first. Ordinary Git publication
and formal freeze approval remain distinct from the existing Flutter WIP scope.

Candidate preparation uses the verified `fw-wait2` firmware source lineage,
not a wholesale overwrite of the dirty shared root. Under
`.cache/p34-acceptance1/`, retain its registered firmware inputs and overlay only
the already-tested stopped-ACK fix and HAL first-error/erase-policy integration.
Separate ACK clock/generation from the experiment collector so it can actually
build with the collector and baud console OFF; keep the measured memory budgets,
WAIT_RX, erase/QE/CRC/SHA choices, Boot and UI. The selected 921600 build is a
candidate setting, not a claim that the formal supported-rate selection passed.

The completed remediation self-tests are retained in `.cache/p34-remediation1/`:
receiver4 has 10 modeled cases/327 checks and a detected source-mutation negative
control; hal3 has four 187-check HAL runs and two 1536-check erase-ahead runs;
arm2 binds the final HAL target compile and unchanged pipeline/session unit
dependencies. These passed without compiler warnings, but are not hardware or
formal acceptance. Governance's two affected route/profile tests passed in
governance2 after the supplement rename and actual erase-header registration.
App commit `50efd3e95b5c7e9580c82cd7c6fa8f0639484a67` passed development run
37904382350 on both hosts; `flutter-artifacts1/result.json` binds all 20 original
artifact files (3974013 bytes), including the full, untruncated test logs. No APK
was requested or installed. None of these results closes trial5 or P3-4.

### Fixed Candidate Preparation Results

The fixed candidate built in `.cache/p34-acceptance1/fw2/`: 611892-byte raw
App, 0 errors and 641 warnings. The ELF/map and source receipt are bound by
`fw2/result.json`; this is not a Git freeze or an installed image. Boot was not
rebuilt or programmed. Experiment/installation profiles, AT console and RTT
down commands are OFF; functional ACK clock/generation, v2/WAIT_RX and the
measured memory/storage settings remain enabled. Do not use the old 336-byte
MCU profile collector against this image: that symbol is intentionally absent.

App `0133dbfb7fcc05cb0142bbae9e257fdc8ef5bea3`, branch
`dev/flutter/p34-fixed-candidate-20261009`, fixes the existing v2 defaults at
window 24 / DATA batch 12 and retains conservative v1 timeout fallback at
window 4 / single-frame writes. It is not another sender algorithm. Development
run [37941011805](https://github.com/Eitan-S-23/E-Track/actions/runs/37941011805)
passed both hosts: Windows 693 passed / 33 skipped, Ubuntu 710 passed / 16
skipped; both analyze steps passed. Flutter 3.47.7 / Dart 3.13.5. All 20 original
artifact files, including full test logs, are retained in
`.cache/p34-acceptance1/flutter-artifacts1/` (3949430 bytes). No APK requested,
installed or independently accepted.

Offline warning comparison retained all 641 warnings in each firmware build.
After normalizing only the old/new source-directory spelling in the warning
messages, their multisets have zero additions/removals. This does not declare
the existing warnings harmless or the build warning-free.

`assets1/result.json` proves one legal exact 1048576-byte PATCH package using the
same candidate executable, finalized as C30287 -> C30288. The real C decoder
matched every target byte and passed Boot/workspace guards; CRC, truncation,
same-version and wrong-base negatives were rejected before preparation. It is
not yet a qualified repeatable initial state and is NOT the installation input.

Initial-state check: `ota_confirm_test_boot` leaves an already-CONFIRMED BCB
unchanged, and Boot's CONFIRMED branch validates/jumps without rewriting
`cur_vcode`. Do not assume that directly programming C30287 updates a retained
C30286 BCB. Rebind only the candidate image headers/reference package to
C30286 -> C30287 under fresh `assets2/`, keeping `assets1/` immutable. This
avoids an installation-only OTA and an invented BCB edit. Live confirmation,
pending/staging state, exact current App/Boot and recovery still have to be
checked before using this route. New C30286 and historical C30286 are different
executables and must always be distinguished by full raw SHA-256.

`assets2/result.json` is now the selected prepared pair: base 611892 bytes,
SHA-256 `59add7d43a4fa836af5cfc69050af510a16aa6917f549cc645456cb08782f63f`;
target 611892 bytes,
SHA-256 `1f63a475cfc2f64e5590decd48c565ebd470012c02bdd1b21572856f9b07f418`;
reference package 1048576 bytes,
SHA-256 `71a14db796db5fba09af3885259b1d73cf77400711a36c94a955d0f3de813116`.
It passed the same real C decoder's byte-exact positive and four pre-prepare
negative cases, reusing the already-built decoder. No firmware rebuild or
device action was needed. Installation and repeatable-state qualification
remain NOT_RUN; the old currently installed C30286 cannot use this PATCH base.

For repeated same-package runs, the selected route is the existing verified-full-
backup plus inactive-BCB transaction and ordinary Boot rollback, as implemented
by `baud_restore.py` / the original restore helper, not App-only downgrading or
a new flasher. Its old 30209 -> 30208 / old-Boot identities are not usable here;
bind and qualify it for the actual candidate pair/group16 before repetitions.
`restore1/result.json` now binds that existing helper to C30287 -> C30286 and
the unchanged group16 Boot. The state-machine logic is unchanged; only image
identities, lengths/CRC/hashes, mailbox identity and source path were rebound.
All 18 real `bcb_commit` positive/negative cases passed, including inactive-slot
atomicity, sequence wrap, changed/pending state rejection and settings retention.
The 111284-byte helper built with 0 errors / 643 warnings, SHA-256
`3826faabce290185e56d959fa7ff424265fef074082017daec2df32b64d3a900`.
This is an App-only maintenance artifact, not the production candidate or a
new flasher. No recovery transaction or hardware qualification has occurred.

Source integration remains pending explicit ordinary Git authority. Root asked
once for candidate/necessary dependency commit and push to
`acceptance/p3-4-v2-20261009`, without main merge or release. The necessary
mid-task current-session real mention was acknowledged with exit 0 at
`.cache/p34-acceptance1/commit-notification1/receipt.json`. Do not resend it
merely because an unchanged request remains pending. Shared HEAD/index and the
original independent pre-review report still match the recorded bindings.

### Remaining Formal Admission

1. Integrate the selected candidate, exact App revision and the actually used
   runner/restore dependencies into a reachable dedicated commit after the
   pending Git authorization. Do not import all historical Tools/cache branches
   or touch the dirty shared checkout. Produce the real v3 freeze objects and
   NOT_RUN matrix, not placeholder IDs or a worktree-byte manifest.
2. Bind the formal sweep before freezing commands. The current fixed candidate
   uses compile-time `P34_OTA_UART_BAUD`; changing it produces a different base
   image and a PATCH base-hash mismatch. The 921600 fixture is not automatically
   one identical package for every compiled rate. Reuse the existing controlled
   runtime baud route, with its real command/source dependencies, or make only
   the UART configuration decoupling necessary to preserve a same-image/same-
   package comparison. Do not label per-rate package changes an identical-input
   sweep. No new baud/throughput claim or device tuning was made here.
3. The independent operator owns fresh current-state preflight, standard J-Link
   candidate installation and exact readback. One first legal reference transfer
   can supply the actual candidate backup and the targeted hardware observation;
   then qualify the rebound complete-state rollback before repeated same-package
   runs. This is not an extra installation-only OTA and must not be counted as an
   equivalent-state performance sample before equivalence is established.
4. Use one formal plan: fixed supported-rate screening, P99-derived timeout
   selection, then one final same-configuration 30/30 group, four-hour soak and
   10/10 recovery. The same original full-transfer observations supply throughput,
   P95, per-run time, retransmission and integrity criteria. Implementation does
   not duplicate this campaign. Exact finite cells, commands, deadlines, source
   dependencies and counter ownership must be in the approved contract before
   execution; this operational sequence is not a FROZEN contract.

P3-4 remains in progress. No formal contract, runtime initial-state qualification,
APK installation or independent formal campaign has been completed in this batch.
Trial5 stays a deferred historical risk, not a renewed causal-investigation gate.

## 2026-10-09 Approved Limited V2 Admission And Remediation

DECIDED, `OTA-DEC-015`: after the explanation of v2 and the four-step bounded
recommendation, the user replied "那你做吧". This authorizes retaining the existing
two-block/synchronous WAIT_RX route for remediation and future P3-4 acceptance.
It supersedes the pending-scope status below, not the original observations or
the earlier fact that an explanation request alone was not approval.

The [v2 supplement revision 1](../ota-ble-v2-contract.md) defines the prospective
protocol/compatibility target. The existing PRE-01 inventory below is now the
selected productionization direction, with its verification conditions intact.
Final source/configuration freeze, actual production rate/timeout selection and
product release remain pending. Old v1/P3-3-v9 and group16 Boot stay unchanged.

Research before implementation: the saved source confirms pending/in_start guards
in WAIT_RX, but the root copy is not equivalent; importing it blindly would lose
or conflate changes. Existing program-RX coverage uses only a 9000-byte fixture
and first-block callback. Extend the actual session/staging test route across
the original package's twelfth block and 13-block prefix, including IO/verify/
journal failure and safe source borrowing. The old failure's two mapped FF pages
remain evidence, not a unique root-cause diagnosis. The pipeline poll deadline
does not bound a blocked synchronous call. App status loss and profile dependency
gaps are addressed in the same batch, not by repeating a full stability campaign.

Execution is bound by the [remediation supplement](../ota-prompts/supplement-P3-4-remediation-2026-10-09.md).
First outputs are contained host regressions under `.cache/p34-remediation1/`.
No current hardware owner or device state has yet been inspected in this batch.
No formal campaign is running; trial5/PRE-03 remains open until its actual oracle
is satisfied. The 50 kB/s/Handler/QSPI-clock/startup-self-test branches stay paused
or cancelled. Ordinary Git publication and production release are not granted.

The next bounded source check reuses `fw-wait2/b/compile_commands.json` for the
three changed App translation units, redirects every output to a fresh local
directory and binds current-root headers explicitly. It is not a linked firmware
or proof of final production configuration. A direct staging diff also identifies
the measured 64 KiB erase-ahead policy absent from root; reconcile that existing
policy with first-error recording and its tests before calling root equivalent.
Do not import the other experimental source differences wholesale.

## 2026-10-09 Notification Clarification

DECIDED, user clarification: normal final replies already receive the bridge's
automatic @mention, including handoffs and final approval questions. A manual
real current-session @mention plus a checked receipt is required only for a
necessary user intervention while the current execution remains open, such as
reinserting an SD card. The project remaining unfinished is not such a trigger.
The normative rule is
[User Intervention Notifications](../agent-collaboration-contract.md#user-intervention-notifications),
with the cross-agent lesson in
[PROJECT-06](../agent-collaboration/project-workflow.md#project-06-only-manual-mentions-for-mid-task-blockers).

Root updated the local entry points, skill routes and governance regressions.
All seven selected host governance tests passed; original output is in
`.cache/p34-notification-policy1/tests.log` and `result.json`. The targeted
`git diff --check` passed with six LF/CRLF conversion warnings, not content
errors. No remote CI, commit/push, bridge test message or device operation was
performed. Historical notification receipts and the pre-review report remain
unchanged; the rule is not yet a published governance revision.

The user's v2 question is a request for explanation, not formal protocol/scope
approval. The two-block design uses two 4 KiB RAM receive buffers, not A/B
firmware partitions. The measured synchronous port with WAIT_RX overlaps only
part of receive and Flash waiting; accepted RAM bytes remain distinct from
readback-and-journal-confirmed durable progress. Trial5 remains unresolved and
the v2 admission, production freeze and formal acceptance gates below remain open.

## 2026-10-09 Root Response To Independent Pre-Review

Input: `.cache/P3-4-independent-pre-review-report-2026-10-09.md`, 51829 bytes,
SHA-256 `3325f74baa203b3c967c8e314158ed17ad42aade7fa5a7592e84232ee576f857`.
Root read the complete report and checked the actual `fw-wait2/configure.json`,
the relevant CMake/HAL coupling and installed App source at `ef47dabd`.
The independent report is preserved unchanged. This response is an operational
decision/proposal, NOT a frozen protocol supplement or formal acceptance result.

### P34-PRE-02: Technical Selection And Pending Scope Approval

DECIDED, root's recommended remediation candidate: retain the already-measured
negotiated v2/two-block pipeline with its synchronous port and WAIT_RX, together
with the installed App lineage and unchanged group16 Boot. Do not implement a new
native sender, raise the 50 kB/s goal, change QSPI frequency, restart self-tests,
or alter the upgrade UI. This choice does not close the trial5 reliability issue
or declare the current binary production-ready.

NEED_EVIDENCE / authorization boundary: experimental exploration permission is
not approval to amend the frozen P3-4/v1 contract. Request ONE explicit user
approval for a prospective versioned v2 protocol/compatibility supplement and
the corresponding P3-4 scope extension. Until that approval, do not edit the
normative frozen documents, claim v2 formally admitted, publish a new freeze,
or start dependent formal product observations. Existing v1/P3-3-v9 artifacts
and their historical completion remain immutable.

The proposed scope is limited to specifying existing behavior, not inventing
new throughput changes: CAPS2/nonce negotiation, commands 0x10..0x14, frame
lengths/CRC, 128-byte DATA, 24-segment physical in-flight cap, two 4096-byte
buffers, accepted versus verified durable progress, credit_end, ordered replay,
epoch/session/sequence validation, cancellation/DRAINING ownership and old-peer
compatibility. Preserve v1 behavior for old peers. A v2 failure or uncertain
write must not silently downgrade into v1. ACK/P99 accounting must retain the
first-complete-send to verified durable-confirmation meaning; accepted/GATT
completion does not become durable progress.

The original legal 1 MiB, >=9 KiB/s, P95 <=120 s, every run <=150 s, <=1% clean
DATA retransmission, 30/30, 4-hour soak and 10/10 recovery gates remain intact.
No Boot replacement, device experiment, commit/push, merge or release is granted
by this proposed scope decision. If v2 is not approved, root will separately
select a v1 candidate and stop using v2 results as its evidence; no automatic
App-only rollback, restoration or discarded failure evidence follows.

### P34-PRE-01: Candidate Switch Disposition

This is the proposed productionization inventory, not an applied configuration
or a final freeze. "Retain" means keep the measured behavior as the starting
candidate, subject to PRE-03 and targeted verification; it is not a reliability
waiver. A defect-driven change must be explicitly recorded with affected tests.

| Input / current setting | Root disposition for the candidate | Required closure before freeze |
| --- | --- | --- |
| P34_OTA_PIPELINE=1, P34_OTA_PIPELINE_SYNC=1, P34_OTA_PIPELINE_ACK_BIND=1, P34_OTA_PIPELINE_WAIT_RX=1 | Retain this existing combination conditional on v2 approval; no asynchronous-driver or continuous-sender rewrite. | Versioned compatibility decision, real source registration, PRE-03/07 failure cases, quiescent release and boundedness. |
| ACK UART transmit-complete plus 1 ms gap; timed ACK batch up to 2 ms with immediate control/error/durable flush | Preserve behavior; separate its functional clock and connection/session generation from the experiment logger. | Production build without experimental profile; FIFO/epoch/timeout/error tests and no weakened UART-completion semantics. |
| CONFIG_OTA_INSTALL_QE_REUSE=1, CONFIG_OTA_STAGING_QE_REUSE=1 | Retain the measured checked-restore behavior provisionally, not as proof that trial5 cannot involve it. | Explicit restore/IO/verify error classification and justified PRE-03 disposition. |
| CONFIG_OTA_INSTALL_BLOCK_ERASE=1, CONFIG_OTA_INSTALL_HALF_ERASE=1, CONFIG_OTA_STAGING_BLOCK_ERASE=1 | Retain existing erase policy; no new geometry/clock optimization. | Current range/ownership, failed-page recovery and actual reference-package tests. |
| OTA_PATCH_COALESCE_WRITES=1, CONFIG_OTA_APP_CRC32_NIBBLE=1; App boot_sha256.c -O2 override | Retain existing semantics/optimization as named build inputs, not untracked command-line accidents. | Exact shared-source identity, CRC/SHA/decoder positive/negative checks and Boot-target isolation. |
| CONFIG_OTA_UI_CADENCE=1, CONFIG_OTA_ACTIVE_PUMP=1 | Retain existing active-OTA scheduling while preserving the UI flow and foreground safety behavior. | Actual schedule/timeout dependency checks; do not infer runtime cadence from the nominal 20 ms macro alone. |
| P34_EARLY_FAULT_VECTORS=ON | Retain the reviewed protective Flash-vector/runtime-promotion behavior; do not simply disable it as "diagnostics". | Production-safe readiness dependencies, exact startup/linker registration and affected fault/stack checks; no Boot replacement. |
| P3_4_LINK_PROFILE=ON currently | Remove this all-in-one experiment switch from the final production configuration only after the functional dependencies below are split. | Build the actual production target with it OFF; no reliance on its baud console, clock setup, epoch definition or hidden heap overrides. |
| CONFIG_BT_BAUD_EXPERIMENT=1 currently; CONFIG_RTT_DEBUG_CMD_ENABLE=0 | Final production experiment/RTT command entry points OFF; retain RTT debug commands at 0. | Preserve a real product UART-rate/init path and session ownership; no arbitrary runtime AT console or transparent bridge. |
| CONFIG_OTA_BLE_PROFILE=1, CONFIG_OTA_INSTALL_PROFILE=1, CONFIG_OTA_INSTALL_COST=1 currently | Full experimental timing collectors OFF in the final production configuration; retain separately scoped, bounded read-only error/progress observation needed by the product and acceptance. | Error observation cannot control success/credit; final measurement uses the actual chosen build/config, not old diagnostic timings. |
| LV_MEM_SIZE=126976U, __p34_heap_min=4096 injected by profiling; 40 KiB overlay, 8192 B OTA stack and 32 B guard in measured layout | Preserve these measured memory budgets as explicit candidate constraints rather than silently reverting them when the profile is disabled. | Final map, all relevant allocator/linker inputs, WAIT_RX nested call/IRQ bound and required runtime watermarks; not a reopened unrelated RAM campaign. |
| App ef47dabd lineage; P34_OTA_PIPELINE true; dataBatchFrames=12; runtime requested window 28 but effective cap 24 | Preserve existing sender behavior, explicitly configure the negotiated cap/batch outside the experimental runtime loader; no Handler candidate/native batching. | Production/release-equivalent build and v1/v2/cancel/late-event tests, exact source and artifact binding. |
| App native per-write timing recorder and experimental runtime parameter/endpoint injection | Development-only, not hidden dependencies of the final product path; keep the normal OTA statistics and add PRE-07's bounded first-error details. | Explicit production defaults and capture inputs; no inference that disabling observation preserves measured performance. |
| Current UART retained/requested 921600; actual divisor 923076 | Record as the current screening state, NOT the selected final production rate. | The supported-rate comparison selects the highest qualifying combination; production init must then use that value, not accidentally fall back to 115200. |
| maxRetries=5; ackTimeout=2000 ms currently; 30-second no-durable budget | Keep maxRetries and no-progress rule; current timeout is only a starting input. | Final timeout follows the frozen clamp(3*P99,500,2000 ms) rule on the approved complete clean parameter group, not resumed trial6. |
| Current reconnect INFO 1000 ms / interval 500 ms / 12 attempts / link reuse; original UI | No new reconnect/UI tuning in this remediation. | Preserve target identity, generation invalidation and actual failure reporting. |
| Group16 Boot and QSPI frequency | Unchanged. | Identity binding and only directly affected shared-source checks; no cancelled clock/self-test route. |

Concrete coupling already confirmed in the saved measured source:

- `MDK-ARM_F435/cmake-generated/CMakeLists.txt:738` enables the baud console,
  BLE profile, LVGL pool override and separate heap minimum together.
- `USER/HAL/HAL_Bluetooth.cpp:45` declares `s_ble_epoch` only under the
  experiment flag, but the ACK batch uses it at line 989. Its functional
  generation cannot disappear with the console.
- `HAL_Bluetooth.cpp:229` has a compile error without the diagnostic DWT
  profile, and its ACK gap depends on the initialized clock. Remove the coupling,
  not the guard or necessary wait.
- `HAL_Bluetooth.cpp:845` otherwise initializes UART to 115200. Removing the
  experiment must not produce a silent mismatch with the retained module rate.
- The same flag suppresses legacy name/text output. Preserve the product's
  idle behavior while proving no AT/text interleaving during active binary OTA.
- `p34_early_fault.cpp` guards the transition to runtime vectors through real
  readiness checks. Preserve protection and examine those dependencies when
  removing the broad profile; do not bypass the check to make compilation pass.
- App `ota_service.dart` at ef47dabd lines 2236-2241 takes batch parameters from
  the experiment runtime and otherwise defaults to one frame. Those settings
  need an explicit product configuration, not an assumed identical sender.

### One Remediation Batch And The Next Owners

1. Root obtains the bounded v2 scope decision. If approved, prepare the
   prospective supplement and affected profile/contract changes for review;
   approval of direction is not a completed protocol freeze. Preserve exact
   v1 clauses/history and the original performance/integrity criteria.
2. The implementation owner receives PRE-01/03/06/07 together: integrate only
   the reviewed measured lineage, separate the above production dependencies,
   preserve numeric first-error ACK/context and receiver IO/restore/verify
   distinctions, and use the original package's first 13 blocks for the
   alternating-buffer/page-failure regression cases described by the reviewer.
   Do not call containment alone the repair of the unexplained trial5 failure.
3. The same batch supplies affected host/build checks, real dependency coverage
   for Android vendor sources, Tools/ota ACK headers and actual runners, plus
   bounded synchronous-IO and relevant WAIT_RX stack/ownership evidence. Do not
   substitute directory names or source-manifest counts for a reachable freeze.
4. Root then binds the legal 1 MiB asset and safe equivalent initial state,
   final configuration, source/runner commits and approved finite formal plan.
   Submit/push/freeze approvals remain separate. Do not require a duplicate
   implementation 30-run/soak campaign before independent formal observations.

Only this operational response and board state were edited here. PRE-01/02/03/
05/06/07 are not marked resolved, no code or normative contract was changed,
and no device, CI, build, commit or formal-test command was run. The first
external decision needed is the explicit v2 scope approval described above.

## 2026-10-09 Speed Work Paused; Independent Pre-Review Handoff

The user paused the additional 50 kB/s pursuit and requested an independent
pre-review handoff, NOT immediate formal acceptance. P3-4 remains in progress;
the original implementation ownership and formal gates are unchanged. Current
task prompt: `.cache/P3-4-independent-pre-review-2026-10-09.md`. It is a temporary
local handoff, not a frozen contract, published release or completed review.

Assess the measured WAIT_RX/v2 receiver and installed `ef47dabd` diagnostic APK
as inputs to selecting a stable candidate. Last verified board state is still
C30286 with unchanged group16 Boot; this preparation did not touch the phone or
MCU. The Handler candidate `a16eaf6a3b51c762a42aa34ef08cd16a6992d187` on
`dev/flutter/p34-main-dispatch-20261009` is excluded and uninstalled. Its earlier
development CI runs 37840858108/37842008780 are not device evidence; during this
handoff check its `download1/` and `apk1/apk.json` were absent. Do not restart its
download/CI or use its forward assets as the acceptance candidate.

Later discussion considered native batching and continuous credit-bounded
244-byte packing. No such sender was implemented or measured. The native trace's
1100 internal batch links contain 1.710096185 s of unhidden callback-dispatch
tail plus 2.585867346 s of disjoint inter-write gaps. Their 4.295963531 s sum is
an optimistic addressable interval under fixed surrounding waits and zero
replacement cost, not demonstrated savings or a physical throughput ceiling.
The 50 kB/s budget discussions are now deferred, not new formal criteria.

The pre-review must consolidate candidate/source integration and freeze gaps,
v2 eligibility against frozen protocol/window rules, the unresolved trial5
receiver verification failure, direct evidence reuse and remaining formal
observations. Do not make the implementation agent run 30/30 and the 4-hour soak
as an invented prerequisite for another full independent campaign. First real
formal observations can run once under the later approved frozen plan after
known blockers and admission prerequisites are addressed.

Only offline source/evidence inspection and a fresh review report are requested
now. No new product change, build, CI, commit/push, APK/firmware installation,
reset, OTA or formal matrix was performed for this handoff. Both QSPI detours
remain cancelled, the original UI flow remains unchanged, and older sections
below retain their historical decisions and failures rather than live commands.

## 2026-10-09 Native DATA Matched; One Callback-Scheduling Candidate

Owner: Codex root; P3-4 and the original implementation ownership remain in
progress. The explicit handoff is `.cache/P3-4-next-agent-2026-10-09.md`.
Use trial6's immutable snapshot and the installed APK source at
`ef47dabd51f129c64a0be0945265192d17f70c17`; the retained board is C30286 with
unchanged group16 Boot. No new device operation is part of this offline phase.

The existing QUERY-only correlator `.cache/p34-native1/query.py` cannot be
applied unchanged: the extracted log contains two `OTA_LINK_LATE` platform
writes inside pre-upgrade `DEVICE_LINK_CHANGED` ABORT intervals (log lines 29
and 51), in addition to 1320 ordinary platform samples. At the exact APK source,
`OtaLinkStats._startObservation/_emitSample` deliberately routes retired-instance
observations to LATE without changing that instance's frozen summary. Native
recording is capture-wide, not limited to unretired statistics instances.

The small adapter `.cache/p34-native-attribution1/analyze.py` now binds every
write. Original input/extraction SHA checks and the exact APK envelope verifier
pass. Native cumulative snapshot counts are 1, 2, 4, 6 and 1322; their common
prefixes are identical. The 1320 ordinary samples plus two LATE observations
match all 1322 native rows without exclusions. Native rows 3 and 5 both match
the encoded v1 ABORT (session 0, sequence 0), CRC32 1019771706, within the two
original prestart ABORT intervals. Their `query` labels identify retired stats
instances, not the wire command.

| Operation | Native rows | Native connection object | Count |
| --- | --- | --- | ---: |
| Pre-upgrade INFO queries | 1, 2, 4, 6 | 1 then 2 | 4 |
| Prestart ABORT | 3, 5 | 2 | 2 |
| Upgrade INFO, CAPS2, BEGIN2, END2 | 7, 8, 9, 1313 | 2 | 4 |
| Actual DATA2 GATT fragments | 10..1312 | 2 | 1303 |
| Post-END INFO probes | 1314..1322 | 3 | 9 |

The nine probes are nine writes on ONE new native GATT object, not nine new
connections or retransmitted DATA. Eight INFO attempts timed out; the ninth
returned the verified target identity. All native API/write callback statuses
are successful. Do not convert an unanswered INFO into a failed GATT write.

Every DATA fragment's length and CRC32 matches the exact package reconstructed
through the existing wire encoder. The CAPS fingerprint has a full-rank 32-bit
mapping for the sole unknown epoch; its inverse gives epoch 860533709. The
independent BEGIN, all DATA and END fingerprints verify it, with unique session
1. This is fingerprint correlation, not new HCI or radio capture. BEGIN sequence
0, DATA sequences 1..1965, END sequence 1966 and original segment/chunk completion
records agree. The resumed range remains 45056..296525: 251469 payload bytes,
1965 frames and 286839 wire bytes. There are no unmatched rows.

| DATA timing population | Total seconds | P50 ms | P95 ms | P99 ms |
| --- | ---: | ---: | ---: | ---: |
| App outer GATT call | 8.786622 | 5.231 | 15.738 | 23.248 |
| Nested App platform call | 8.570999 | 5.037 | 15.530 | 22.961 |
| GATT minus platform wrapper | 0.215623 | 0.148 | 0.260 | 0.406 |
| Native method entry to submit | 0.379268 | 0.280 | 0.414 | 0.541 |
| Native submit to API return | 2.483078 | 1.743 | 2.964 | 4.807 |
| Native submit to callback | 3.615905 | 2.403 | 5.224 | 7.743 |
| Native callback to main dispatch | 2.009790 | 0.387 | 5.154 | 14.168 |
| Native entry to both return/dispatch ready | 6.004964 | 3.306 | 10.551 | 17.766 |

API return and callback intervals overlap; 31 DATA callbacks precede API return.
Do NOT add those totals. Callback dispatch is stamped immediately before
`methodChannel.invokeMethod`, not at Dart delivery. Its interval includes callback
body work and main-thread queuing, whose individual costs are not recorded.
The platform-minus-native duration residual is 2.566035 seconds, not isolated
Flutter cost: it includes both bridge boundaries, locks/codecs and scheduling.
The native DATA span is 11.133972 seconds; its inter-write gaps total 5.129008
seconds. Of these, 1100 gaps inside already-reserved batches total 2.585867
seconds; 202 batch boundaries total 2.543141 seconds and include real credit/
durable waits. These gaps overlap the other accounting views and are not additive
with the platform residual. No uncalibrated absolute clocks were subtracted.

DECIDED: reject wrapper-only tuning as the significant next step (even eliminating
all 0.215623 seconds is only 1.89% of this 11.392060-second resumed transfer).
Do not remove platform callback backpressure or implement a native batch sender.
The latter would additionally need to preserve per-fragment dispatched/ACK
eligibility, cancellation, byte order and connection ownership; this report does
not justify that broader rewrite.

One bounded candidate will instead reuse a SINGLE main-looper Handler for all
plugin callback delivery, using `Handler.createAsync` on API 28+ and ordinary
Handler on older Android. The Android 13 `Handler.java` contract explicitly says
async messages bypass display synchronization barriers while keeping FIFO within
that handler. Moving ALL plugin callback types together avoids selectively
prioritizing write completions ahead of their peer BLE events. This changes
scheduling, not thread, API-result semantics, write concurrency, native callback
waiting, transport locks, UI flow, MTU, MCU credit or firmware.

The trace establishes a material candidate interval, NOT the presence/duration
of a synchronization barrier on this phone. The absolute upper bound from
eliminating the entire unhidden callback-dispatch tail is 1.997279 seconds
(17.53% of this resumed transfer), assuming everything else stays constant.
Real gain can be zero: callback body time, an already-running main-thread task,
radio backpressure and later credit waits remain. This candidate does not claim
the separate 2.585867 seconds between writes, a five-second saving or 50 kB/s.
Keep it only if bounded real measurements support a worthwhile net gain.

Development work uses `.cache/p34-main-dispatch1/src` from exact base `ef47dabd`,
then the already-authorized `dev/flutter/p34-main-dispatch-20261009` checks/APK
route. Tests exercise the actual Java factory with host queue doubles (API level,
single-handler FIFO, deferred execution, barrier eligibility and unchanged
dispatch guard), plus existing native/Flutter regressions. Host doubles do not
prove real Android barrier timing; APK compilation and device screening stay
separate. No local Flutter/Gradle build or device installation is involved yet.

For a real comparison, prepare legal forward inputs and equivalent zero-start
state first. Trial6 is not that baseline. Do not reuse its consumed outputs or
old package as a new installation. Keep all failed/successful originals; formal
1 MiB, repeat/soak/recovery and independent acceptance remain unfinished.

Offline self-tests: 10 test methods passed, including the 11 existing QUERY
checks and original-log negative cases (missing LATE, changed native prefix,
wrong identity, overflow/incomplete, wrong CRC/segment/connection, deficient epoch
mapping). Results are `.cache/p34-native-attribution1/tests1/{result.json,tests.log}`.
The source-bound analysis is `.cache/p34-native-attribution1/result1/result.json`;
all matched operations are in its sibling `operations.json`, SHA-256
`e671d545fbf3a97c45e5c1b701566694a7c88ddc9e4c32355dc8d6c830b23adf`.
Original evidence, UI, firmware, cancelled QSPI routes and shared index remain
unchanged. Source references: exact APK `NativeWriteTrace.java`, plugin lines
2490/2985 and `ota_pipeline_transport.dart` lines 262/310; Android 13 public source
`https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/os/Handler.java`.

## Native Timing Decision: Diagnostic Only, No New Speed Result

### Current Result: Normal J-Link Check And Resumed OTA Retest Passed

The requested single original-flow retest completed in `measure/trial6`.
The immutable App snapshot has one upgrade start/end, outcome `completed`,
9411 records, zero lost records, and SHA-256
`14069b7ce0c15d8c4858eb94f299657063c1d140bac46b3af4c7d0eca9f81850`.
Its actual BEGIN progress was 45056 bytes; the first DATA offset is 45056.
The remaining 251469 bytes reached the final durable offset 296525 with
1965 unique DATA frames, zero retransmissions, no error/malformed ACKs, and
complete ACK samples. Transfer BEGIN-to-END-ACK time is 11.392060 seconds;
the separate App reconnect phase is 17.772017 seconds. This is a resumed
functional retest, NOT a zero-start full-package throughput improvement.
The final native snapshot contains 1322 writes with zero overflow, incomplete,
API, callback or correlation errors. Two pre-upgrade link-change teardowns
occurred before the sole upgrade start, not as failed OTA invocations.

Read-only standard Commander verification in
`.cache/p34-native-data1/measure/postcheck/result.json` passes full C30286 App
(623124 bytes, SHA-256
`a2800b07b7de0311b91eebeaa3a9a6012542ae2306d693c14d067877470eac51`),
unchanged group16 Boot, confirmation, VTOR, SD readiness, no fault, advancing
execution and idle session. All trial6 owners and private USB services closed
normally. No firmware, clock, APK or sender parameter was changed for this run;
no further reset or programming occurred during postcheck. Both Feishu requests
used actual user mentions. The failed trial5 snapshot is preserved unchanged;
one exact older successful capture was copied and moved to the App's archive,
without deletion, through the existing archive worker to free its eighth slot.

Conclusion: normal startup and this resumed OTA both work. The earlier
twelfth-block verify failure did not recur, but its unique cause is still
unproven. Do not claim the firmware is fault-free, erase that failure evidence,
reactivate the cancelled diagnostics, or repeat the successful OTA for logs.
Current retained firmware is C30286 / 3.2.86-nt, not C30285. The route and
pre-retest state below are preserved for traceability.

The user rejected both the frequency-change detour and the subsequent QSPI
self-test detour. BOTH are cancelled, neither was installed. Do not build or
flash `.cache/p34-qspi-page1/f` or its diagnostic image. The self-test section
below is superseded history, not current work.

Standard SEGGER Commander loaded the original normal C30285 input from
`.cache/p34-waitrx1/assets1/target.bin`. It reported `Skipped. Contents already
match`, so this was a checked matching-image load with reset/run, not a new
physical erase/program. `.cache/p34-qspi-page1/direct-normal-verified1/result.json`
then verified the complete 623124-byte App, unchanged 65536-byte group16 Boot,
confirmation, VTOR, SD readiness, no fault, advancing execution and idle session.
App SHA-256: `3392efc8582b3745b8e3c85a32bdb4e36c08ac5e819110e005e664f5d429f75f`.
Normal startup does not prove the OTA receive/staging path is fault-free.

Latest user direction: retest OTA once through the original App flow. Owner is
Codex root; host write boundary remains `D:/github/my/E-Track`, with only the
existing SEGGER native-history exception. Reuse the installed `ef47dabd` native
timing APK and unchanged `assets1/full.etu` (296525 bytes, SHA-256
`6bc750062eeb9a536e9173ba2ce8d5cec1284873d8c4a2da3bf2e46bc9b802dc`).
Keep firmware, QSPI clock, Boot, sender settings, APK and UI flow unchanged.
Do not erase the persistent staging prefix: BEGIN may resume from 45056 bytes;
record the actual MCU progress and do not present a resumed run as zero-start
throughput. No further installation OTA, self-test, screenshot or UI automation.

Use the existing full phone/network lifecycle with fresh `measure/trial6`
evidence. Bind the original trial5 terminal failure explicitly, preserve its
snapshot, and reuse the existing exact-capture archive worker only if capacity
requires it; do not label the failure a completed OTA. Prepare collection and
post-upgrade full-image/Boot/confirmation verification before a real Feishu
mention requests Connect -> firmware -> Check -> Download -> Start BLE transfer.
Run one invocation, retain success or failure, close owned workers, and audit
outputs. No blind replay, new speed claim, commit, push or release is included.

### Superseded: Keep The Existing Clock; Direct J-Link Self-Test

The user rejected advancing the clock hypothesis without stronger causality.
QSPI frequency was NOT changed between the prior successful OTA and trial5;
the receiver executable is the same apart from its finalized identity header.
Two erased pages do not prove a clock root cause. The proposed DIV12 candidate
was never built successfully, programmed or measured; that route is stopped.
Its first host clock-fixture compilation failed before execution, and its
`tests1` receipt remains preserved. Do not resume the superseded clock plan below.

The current user-directed route is standard J-Link verification at the unchanged
DIV2/144MHz setting. Reuse the existing `Qspi_SelfTest` and restricted
`qspi_erase_selftest` / `qspi_data_write_selftest` APIs, with a bounded64-cycle
development run rotating over sixteen4KiB sectors. Only the permanently reserved
`0x7f0000..0x7fffff` self-test area is erased/programmed. The failed staging
package, filesystem, candidate/backup/recovery slots, Boot and EEPROM remain
untouched. A small volatile completion/count/first-error record supplements the
existing original RTT output; it does not replace the driver or retry failures.

Build a same-version diagnostic App from the exact receiver source, prove the
disabled build is byte-identical, and use the standard safe-idle J-Link route
for installation. Observe the original self-test result and actual QSPI clock,
then restore the exact retained C30285 image through the same route and verify
full App/Boot, SD readiness and running health. No phone operation or OTA is
needed for this cell. No main/tag push, release or acceptance claim is included.
A passing startup self-test excludes neither BLE-load/reentrancy problems nor
intermittent faults; report that boundary rather than claiming OTA is repaired.

### Failed Pages Confirmed; Conservative-Clock Diagnostic Candidate

`staging-prefix1/result.json` preserves two identical 53248-byte mapped reads,
bracketed by unchanged C30285/confirmed/idle/SD-ready/QSPI-XIP/EDMA-idle state.
The journal contains the original package SHA and the eleven-block durable
bitmap. Payload blocks 0..10 match exactly. Block11 contains two wholly erased
256-byte pages at within-block offsets0x500 and0x700: 511 bytes differ from the
original package and every differing byte reads0xff. These correspond to package
offsets0xb500/0xb700 and external Flash addresses0x30c500/0x30c700. This is evidence
of persistent mapped-data disagreement, not merely an App/collector error; it
does not alone distinguish chip timing, ignored commands, DMA, power or cache.

The first owner comparison incorrectly required equality of DHCSR S_SLEEP;
both original samples otherwise passed. `staging-state1/reconciled.json` reuses
those samples, checks the sole0x40000 difference and three owner/health negative
cases. No repeated sample was taken to repair the host assertion.

Source and current CTRL show DIV2 at288MHz AHB, nominal144MHz QSPI. The retained
Winbond W25Q128BV datasheet (`.cache/p34-erase/references/`) limits quad commands
to70MHz and other non03h commands to104MHz. JEDEC EF4018 does not establish the
exact suffix, so do not assert the board is BV or that this one failure proves
overclocking as the sole cause. DIV12/24MHz is the conservative diagnostic axis.
The driver also treats an EDMA error as transfer-done; this is a separate known
source risk, not an observed EDMA error in trial5. Do not silently fold that
behavioral change into a claimed single-factor clock result.

Finite next cell, owner Codex root, writable root unchanged: copy the exact
installed source without altering its frozen input, add opt-in DIV12 at the
existing QSPI initializer and a first-failure-only staging record (IO versus
byte mismatch, address/length/first differing byte). Disabled builds must
reproduce the retained executable; actual-source host cases must preserve
readback and durable gates and prove diagnostic/no-diagnostic behavior.
Reuse GCC and standard J-Link for candidate installation after full current
state checks. Keep Boot, EEPROM, BLE sender, baud/window/ACK policy and original
UI flow unchanged. One legal full successor transfer screens the changed clock
and collects existing App/native records plus the failure record if needed.
This is failure remediation, not a new speed or reliability acceptance claim.
No automatic replay if it fails without a discriminating new observation; never
repeat a successful transfer for missing host logs. Final retained state requires
full App/unchanged-Boot/confirmation/health verification.

### Recovery Verified; Preserve The Failed Prefix

After the user's recovery confirmation, the already-started standard Commander
read completed in `recovered-device1/result.json`: full retained C30285 App and
unchanged group16 Boot, confirmation, SD ready, idle session, no fault, and
advancing execution all PASS. No host reset/programming was issued. The current
volatile session is cleared; this does not erase or supersede the original
45056-byte durable-prefix failure evidence. C30286 is still not installed.

Next discriminating observation: use the existing Commander `savebin` primitives
to inspect the failed staging prefix, not another transfer. Bind fresh software
addresses to the exact installed map, qualify idle OTA/overlay and QSPI XIP/DMA
state, then read the journal and first twelve payload blocks twice, bracketed by
identity/owner/state reads. Compare against the retained original package.
This is a mapped-logical read, not an uncached-chip proof. No FIFO, register
write, halt, reset, erase, program, Boot/EEPROM change, or phone operation is part
of this probe. Stop dependent operations if qualification or repeatability fails.
The thin task-local adapter only composes the tested Commander entry; it does
not replace a debug protocol or Flash algorithm. Outputs remain project-local.

### Latest Result: Real Transfer Failed During Payload Verification

The original full lifecycle ran in `measure/trial5` without product-code changes
or another APK installation. PID27112, capture
`1791470681659748-6b319b3ac1f35fcbf637e008`, used the original 296525-byte package.
It performed one actual upgrade invocation, ending `not-completed` at 14:57Z on
2026-10-08. Unlike the earlier expired windows, this was a real transfer failure.
The original finished snapshot is retained under `cells/s04/finished/` even though
the success-only collector reports `full installation snapshot/input mismatch`.
That collector error is not the original OTA cause and must not prompt a replay.

App evidence: 416 DATA frames sent once, 45056 bytes durable, one error ACK,
`ACK_STATUS` / `v2 receiver stopped`, no END ACK, and 64 missing ACK samples.
All 280 upgrade platform writes returned successfully. The snapshot includes 288
native writes across queries and this failed transfer, without native overflow,
incomplete, API, callback or correlation errors. It is not a completed-throughput
sample and does not establish a new speed gain.

Standard Commander read-only evidence `failure-profile1/verified.json` binds the
same receiver header/VTOR and two identical frozen profile reads: run1, terminal
ABORT, total296525, 12 payload program/erase/verify calls, exactly one payload
verify error, and no overlay/UART drops, UART errors or profile parser errors.
This locates failure in verification of the twelfth 4 KiB payload block. The
verify callback covers both restore/read IO failure and byte mismatch; the
counter alone does not distinguish them or prove defective Flash hardware.
The numeric error ACK was not retained by the App summary. Do not infer a
specific hardware cause or promise that another transfer will succeed.

`failure-device1/result.json` confirms full unchanged C30285 App and group16 Boot,
confirmation, idle session, no fault and advancing execution. Its overall result
is FAILED because the matched-map `SD_IsReady` read is0. Staging remains incomplete
at45056 bytes. SD unready is a separate observation, not a demonstrated cause of
the payload verification error. No reset/programming/EEPROM write was issued.
All trial5 USB/network/coordinator owners closed without forced termination.

Before any next device mutation, reconcile this failed prefix and restore the
qualified device state. A native Feishu @request asks only for reinserting the
board's SD card while retaining J-Link power, not another OTA. After that action,
use the existing read-only Commander verification with a fresh output directory.
Do not change the original UI flow, weaken verification, roll back App-only across
BCB state, or count this failed short transfer as sustained native timing evidence.

### Current Direction: Restart The Unstarted App Flow

Latest user clarification: use the original working upgrade flow. Do not treat
the missed Start window or agent-induced recovery trouble as a product/UI bug;
do not add screenshot-driven UI checks or change the upgrade implementation.
The original `Followup` lifecycle is reused unchanged through the thin
`original-flow.py` launcher, with fresh evidence directory `measure/trial5`.
The failed `trial4` already stopped the old App, archived its zero-start capture
and retired its configuration. Its later host-only assertion incorrectly required
the remaining historical completed capture to be idle. Preserve that failure;
do not repeat its completed retirement. Original `Followup` already handles this
verified stopped/config-absent/completed-history state.

User decision on 2026-10-08: stop spending time preserving the stale App flow;
rebuild the test setup once. Preserve original failures, reuse the installed APK
and legal C30285->C30286 package, and do not reset/program the MCU or reinstall
the APK for this recovery. There is still no native DATA transfer or speed result.

`attach2` successfully reached the existing PID23560 and cached package, but the
App later reported `DEVICE_LINK_CHANGED` on foreground resume. Read-only
`link-change1/result.json` confirms zero upgrade starts/ends, a healthy capture
and unchanged package. `attach3` retained changing pre-Start queries: reconnect
restored successful INFO reads, with an intervening query timeout and repeated
foreground link-change terminals. Its final health still has zero starts/ends.
Both attachment owners reached their start deadlines and closed USB normally.
An existing package on disk and a live collector did NOT establish a usable UI
Start action. Root twice gave an unverified button instruction; do not repeat it.
The actual installed UI labels that action `开始 BLE 传输`, and its presence
depends on both service phase and retained in-memory firmware state. The only
successful screenshot showed the phone launcher, not the OTA page; the next
screen read was blocked by owner closure. No missing-button root cause is proven.

Prepared restart entry: `.cache/p34-native-data1/restart.py`, fresh output
`measure/trial4`. Reuse the existing full lifecycle, strict query capture,
retirement and unused-capture archival helpers. Recheck zero starts and the exact
old PID/config before stopping that App, preserve its records, retire its old
configuration, make one recorder slot, then start a fresh service/config/App flow.
Use the original package and actual new query/download admission, then inspect
the real page before asking for the correctly named action. Never relax the
link/identity/package checks or repeat a successful OTA to recover logs.

User communication decision: when a real human action is required, send a native
Feishu @mention, not only an ordinary progress message. The existing
`cc-connect send --stdin` route with `<at user_id="...">...</at>` was verified;
the installed bridge sends this as `MsgTypeText`. Reconnect, Start and page-view
requests have successful local send receipts under `notify-*.log`; delivery is
not proof the user acted. Use the current session/recipient, never @all. Clear
inherited `CC_LOG_FILE` and contain CLI temporary paths before invoking it.
Do not interpret the old USB-blocker/ready instructions below as current actions.

### Previous Blocker: Phone Not Visible Over USB

The third host window ended at 11:34:59Z without an observed upgrade start.
The final health still reports zero starts/ends, no loss/error. Its network,
coordinator and standard MCU sampler closed normally; the phone observer's exit1
records the user-start deadline, not a failed OTA. Preserve `measure/trial3` and
`measure/trace`; the latter has no terminal OTA profile because no transfer ran.
No new speed gain or C30286 installation has been measured.

Reassessment selected a cheaper continuation instead of rebuilding the service
and reconfiguring/relaunching the App again. The installed revision's
`OtaService.startOtaUpgrade` uses its already-verified local file, cached asset
identity, and a fresh pre-BEGIN GET_INFO; it does not require another HTTP
download/latest request at Start. `.cache/p34-native-data1/attach.py` reuses the
original PID/capture/config and pre-Start downloaded-byte admission. It only
attaches a fresh private USB reader and invokes the existing snapshot collector.
It never fabricates an admission/footer, starts an OTA, launches/reinstalls the
App, changes config or logging, or creates another network service. The original
App and JNI producers remain the diagnostic timing sources. No renewed MCU
payload/ACK profile is claimed; this is GATT attribution, not UART/staging or
reliability acceptance. The separate full target/Boot/health postcheck remains.

`attach-tests1.json` passed the actual two-native-query/original-config binding
and original downloaded-package admission checks. The first attachment owner
`attach1` then failed before any App command: original ADB receipts repeatedly
report `error: device '10ADA4197U001CK' not found`. Result is
`ATTACHMENT_INCOMPLETE`, detail `exact phone did not become online in the bounded
USB window`; its 45.2s owner exited1 without forced termination and private USB
closed normally. This is the current need for human intervention: restore the
phone's USB connection and unlock it. Do not touch J-Link power, use the expired
Start instruction, reinstall, or assume the old PID is still live.

After USB is ready, the prepared next entry is:
`python -I -S -B -X utf8 .cache/p34-native-data1/attach.py launch --out D:/github/my/E-Track/.cache/p34-native-data1/attach2`.
Check actual `ready.json` and the existing App/capture before asking for Start.
The helper permits a previously started/completed invocation only through the
original verified pre-Start admission and retrieves its original snapshot; it
does not replay it. A changed PID/config or unhealthy capture must be reconciled,
not bypassed. All original timeout/adapter/deadline/offline receipts are retained.
Latest known firmware remains C30285 with unchanged group16 Boot, and latest
public transfer result remains13.343180s. The diagnostic APK install/query result
is real; host preparation and fixes are not a new transport optimization.

### Previous Ready Window: Expired Without Start

The active native DATA cell is now `.cache/p34-native-data1/measure/trial3`,
launched through `followup.py`, not either failed prior host entry. Its App is
PID23560, capture `1791457787051921-ce226156aa511d98780f588b`. The exact
296525-byte C30285->C30286 package is downloaded and byte-admitted;
`cells/s04/status.json` reports `READY_FOR_FULL_INSTALL_START`. Its original
query capture contains two complete native write samples with no native errors,
incomplete rows or overflow. The latest observed health at 11:25Z still has
zero upgrade starts/ends and no loss/error. No new acceleration is claimed.

The standard Commander sampler is also live: `measure/trace/ready.json` at
11:18Z verifies its first sample against the C30285 header and App VTOR. It runs
under `measure/native-runtime`, through `live_trace3.py`, with the existing
1260s outer/1200s sampling bounds. It monitors `trial3`, not `trial2`. User was
asked to tap Start once for 3.2.86-nt and keep the App foreground, without
switching to chat. Do not issue another Start or restart these owners. Check
fresh owner/health records first; the finite windows may expire while idle.

After actual completion, retrieve and verify the original snapshot already
handled by the live phone owner; check its and the sampler's real closure.
Use `.cache/p34-native-data1/observe.py postcheck --arm measure` for the separate
read-only whole-target/unchanged-Boot/confirmation/health check, once no debugger
owner remains. `followup.py` exposes the corrected runtime-reader bindings and
`trigger("measure")` remains available through its imported trial module for
offline original-snapshot verification. Do not replay the logical DATA cell if
the OTA succeeded but any host/analysis step failed.

The second host entry `trial2` ended before App launch because inherited
`retire_initial` read a config that `settle1` had already archived. Its original
USB command receipt ends at a read-only stat reporting the absent config;
there is no launch receipt or new OTA. All its owners/USB closed. `followup.py`
now accepts absent config only with the exact successful retirement proof and
an absent App process; a present config still follows the original strict route.
`measure/check3/result.json` reruns the full reader/config checks, and the entry
also passed three retired-config guards (valid retired state, unexpected PID,
invalid retirement). Original helpers/checks/failures stay immutable. This
remaining small guard was preferred over replacing the existing installer,
transport, network or collection machinery. Native timing installation and host
repairs are preparation, not new measured speed improvements.

### Current Result: Installed And Query-Native Timing Verified

The read-only reconciliation on 2026-10-08 09:30Z found the exact new APK
`c9809a339d19d60f6e686ed99dd9329263c21ed2f66679cff76dd2e6417ea25a` installed,
with the original completed WAIT_RX snapshot, configuration and BLE permissions
unchanged. `reconcile1/result.json` is `INSTALLED_APK_AND_DATA_RECONCILED`; its
worker exited 0 and USB closed normally. The earlier install command still has
its original timeout receipt. No second installation was performed.

`observe-reconciled.py` reuses the unchanged query observation function, replacing
only the original install-receipt prerequisite with the source-bound successful
reconciliation. On 09:39Z the real App PID 22809, capture
`1791452360291806-c05f253189033023e14e1d80`, produced one fully matched 10-byte
INFO write: native method-to-submit 0.627396ms, submit-to-return 1.320886ms,
submit-to-callback 1.857865ms, callback-to-main-dispatch 0.266458ms. All native
error, incomplete and overflow counters are zero. The separate App platform
duration is 16.100ms; these different boundaries do not isolate Flutter overhead.
Original records and native result are in `observe1/read-002`, result is
`NATIVE_QUERY_TIMING_VERIFIED`; the 34.6s owner and USB closed normally. This is
query-only capability, not saturated DATA throughput or a new acceleration.

### Next Finite Cell: Prospective Native DATA Attribution

Preparation checkpoint: `.cache/p34-native-data1/assets1/result.json` verifies
the 296525-byte full ETU, SHA-256
`6bc750062eeb9a536e9173ba2ce8d5cec1284873d8c4a2da3bf2e46bc9b802dc`.
Existing native decoding is byte-identical and four rejection cases pass.
`current-device1/result.json` is a fresh read-only standard-Commander whole-App,
whole-Boot, confirmed/idle/SD/fault/running/advancing-health PASS. No reset or
programming was performed. The diagnostic APK remains the one installed above.

The first prepared host cell `measure/trial` failed before transfer observation
with `AttributeError: ... has no attribute 'same_device'`. Its launched App was
PID21585. Standalone new-envelope verification had passed, but that check missed
the existing runtime reader's extra identity/configuration helpers. This is a
host adapter mistake, not a BLE or firmware failure. The applicable existing
pattern was already present in `Tools/ota/p34_radio_followup.py:fixed_envelope`:
retain `Tools/ota/p34_observation.py` and extend only its tested prefix tuple.
Do not replace the whole runtime reader with the narrower build-time envelope.

`resume.py` applies that existing composition with the exact installed revision's
five native prefixes. `measure/check2/result.json` now tests the runtime API,
actual native-query records plus runtime configuration binding, wrong-config
rejection and the original full snapshot. Original `trial.py`, its first check,
failed cell and closed owners remain unchanged. `settle1/result.json` proves
zero upgrade starts, stopped App, verified non-deleting query/config archival,
preserved completed WAIT_RX snapshot and normal USB/worker closure. Therefore
there is still no new OTA result. The pending logical DATA cell reuses the SAME
package/APK through fresh `measure/trial2` outputs and a new bounded service;
this is host recovery, not a second measurement or another firmware install.

Owner: Codex root; writable root `D:/github/my/E-Track`, outputs under
`.cache/p34-native-data1`. Reuse the now-installed exact diagnostic APK and the
existing full-OTA phone/network, strict snapshot and standard Commander read-only
routes. No new APK/firmware build, custom flasher, automatic UI tap, global log
setting, Boot change or direct EEPROM/BCB edit. Keep J-Link power uninterrupted.

The input is one legal full successor C30285 -> C30286 / 3.2.86-nt using the
unchanged WAIT_RX executable outside the firmware identity header and unchanged
group16 Boot. This is a new declared diagnostic input, not replay of the completed
C30285 OTA. Use the existing ETU packer and native decoder with four rejection
cases. Record its actual size/hash before serving it. Keep baud921600, v2 pipeline,
requested window28/effective cap24, GATT reuse, no-response writes and PHY policy
unchanged. Do not substitute a small patch or infer general installation time
from this header-only successor. No separate receiver-installation OTA is needed.

One screen is planned, not a stability campaign: establish current full App/Boot,
confirmed idle healthy state, fresh App queries and downloaded-byte admission;
collect original App/native records through ordinary apply/reconnect; verify full
target bytes, unchanged Boot and confirmation. Native query success is already
proved, but DATA timing must have complete sample/length/capture/connection and
clock/status bindings with zero overflow or ambiguous association before use.
If collection fails after OTA succeeds, retrieve original records and reconcile
the actual target instead of repeating the upgrade. Missing evidence stays missing.

Use existing finite owner bounds (network5400s, cell3900s, user-start1500s,
active installation900s), with the MCU sampler started near actual user Start
and a separate 180s read-only postcheck. Do not consume the short device window
while preparing codecs or host tests. After this screen, select a sender change
only if the measured native/API/callback/dispatch split supports it; no fixed
seconds-saving forecast is established. This is development diagnosis, not
independent acceptance or a claim that the P3-4 speed objective is complete.

### Resume Outcome: Standard APK Install Timed Out, Reconcile Before Acting

After the user reported ready, `phone-resume.py launch` ran the prepared route
on 2026-10-08 09:09Z. The fresh `resume1/pre-install1` verified the awake phone,
quiesced the known query-only App and completed the existing non-deleting capacity
gate. The standard installer then invoked `adb install -r --no-streaming` with
the exact `c9809a33...` APK. Its 180-second command wait timed out; this does not
establish whether Android installed or rejected the APK. Preserve
`install1/result.json` and `resume1/runtime/closed.json` (worker exit 1, no forced
termination). Both USB contexts closed normally and port 5062 was closed.

The next finite cell is a read-only installed-APK/data/permission/session check
through the existing private USB and supervisor primitives, using
`.cache/p34-native1/reconcile.py` and fresh `reconcile1` outputs. It performs no
installation, launch, UI tap, logging change, MCU operation or OTA. If the exact
new APK and preserved data are verified, continue query observation using that
state without reinstalling. If the old APK remains, inspect the original system
outcome and any actual prompt before choosing a retry; an empty host receipt is
not permission to repeat installation. All controlled host writes remain under
`D:/github/my/E-Track`; old helpers and failed receipts stay immutable.

### Latest Outcome: Checked APK, Phone Wake Required Before Installation

The native observer is saved on `dev/flutter/p34-native-timing-20261008` at
`ef47dabd51f129c64a0be0945265192d17f70c17`, pending mainline integration. Read its
actual source with `git show COMMIT:app/bluetooth_flutter_Trace/lib/ota/ota_native_write_trace.dart`;
`.cache/p34-native1/src` is a partial source copy, not a Git worktree.
The native plugin, diagnostic lifecycle, App/host prefix registry and tests are
included. No sender, receiver, baud, protocol or backpressure optimization was made.

The first checks run 37742377671 failed one new concurrent-export test on both
hosts; analyze was clean. The async test fixture's conditional returned a Future
as a value rather than explicitly awaiting it. Original failed logs are retained
under `.cache/p34-native1/ci1/original`. The follow-up also moves native start to
the first INFO query so the original runtime stamp remains the first producer
record; a regression verifies that order and one native start. No failed APK was
built or installed. Checks run 37744510794 then passed both hosts.

Explicit APK run: https://github.com/Eitan-S-23/E-Track/actions/runs/37745196875
on the exact `ef47dabd` commit. Linux 700 passed/16 skipped; Windows 683 passed/
33 skipped; zero failures and clean analyze on both. Native Java has 27 observer
checks plus the existing PHY/tag checks. Flutter 3.47.6 / Dart 3.13.5, Flutter
revision `5fc346839b5d0eef006ed8404392afb4dfae428d`. Android debug APK built;
Windows EXE, production release and independent acceptance were not run.

APK: 131707446 bytes, SHA-256
`c9809a339d19d60f6e686ed99dd9329263c21ed2f66679cff76dd2e6417ea25a`,
same fixed signer `9e9b89c5e7fdc802b1fe71806a988a866db49cd988a739caeee56cb69f3df579`.
Metadata is `.cache/p34-native1/apk1/apk.json`. `gh run download` timed out after
600s after retrieving Linux logs. The existing range downloader recovered only
the missing Windows/APK artifacts. Its first 240s window verified 252/288 APK
ranges; the next window reused those and fetched only the final 36. Full archive,
APK, source, both-host results and signer checks passed. Preserve the timeout,
range failures and original Linux bytes; no new CI build or device action was
used to recover downloads. Receipts are in `download1/complete.json`.

The native query correlator has 11 checks and the existing capture-capacity gate
passed its six regressions; installer guard tests were reused unchanged. The
phone preflight on 2026-10-08 08:35Z found `mWakefulness=Asleep` and returned
`NEEDS_PHONE_WAKE_NO_MUTATION`. It did NOT force-stop, archive, install, launch,
change a setting or perform an OTA. Both the 19.5s owner and private USB context
closed normally. The earlier plain-tag APK remains installed; native timing has
NOT yet been verified on the phone. No native query or speed result is claimed.

The required user action is to wake/unlock the phone and keep USB connected for
foreground observation. No new authorization, manual installation or OTA start
is needed for this query-only step. Host continuation is prepared:
`python -I -S -B -X utf8 .cache/p34-native1/phone-resume.py launch`.
After its actual `resume1/runtime/closed.json` and installation result are verified,
use `python -I -S -B -X utf8 .cache/p34-native1/phone.py observe`. The resumed
preflight has a fresh output directory; the standard installer entry is still
unspent. Never replay `phone.py install`, overwrite the first preflight, or launch
another upgrade to work around missing observation. Once query-native binding
passes, a prospective saturated DATA measurement still needs an explicit input
and finite matrix; INFO latency is not DATA throughput.

Continuation on 2026-10-08 retains C30285 / 3.2.85-wr, raw SHA-256
`3392efc8582b3745b8e3c85a32bdb4e36c08ac5e819110e005e664f5d429f75f`,
and unchanged group16 Boot. Latest measured public transfer boundary remains
13.343180s (diagnostic boundary 13.337202s). No subsequent acceleration has been
measured; installing an observation APK does not count as a speed optimization.

The plain-tag diagnostic APK is installed and hash-verified: development commit
`01e424fdb81895e1ee3b4ca020315dba57051427`, APK SHA-256
`f8692d4d7a50ec31de17bcca08fbf259f9b603f0c876d3861bd8875be081e46e`.
Checks run 37729266637 and explicit APK run 37729963790 passed both hosts;
APK-run tests were Linux 690 passed/16 skipped and Windows 673 passed/33 skipped,
on Flutter 3.47.6 / Dart 3.13.5. No Windows EXE or independent acceptance ran.
The update preserved configuration, permissions and completed WAIT_RX snapshot.
The older C30284 capture was backed up and moved to the App's archive, not deleted.
See `.cache/p34-gatt1/{apk1,install1,archive1}` for original receipts.

Correction to the historical logging diagnosis below: global `log.tag=I` was
not proved to be the complete cause. `live2` failed because Android rejects
brackets in property names; `valid-tag1` was a host context-manager adapter error.
`valid-tag2` verified legal `log.tag.FBP-Android=D` and exact restoration.
The fixed APK's real startup INFO queries succeeded with that override enabled
before launch, but `query1` still captured no native markers. All tag/USB owners
closed; no global or persistent logging property was changed. Preserve these
failures rather than rewriting them as successful observation.

Read-only `readback1` compared existing main-buffer reads through shell, App UID
and exact PID 29852. Shell returned 5759 parsed records, none from the target PID;
App-UID/PID reads returned zero bytes. Only selected native lines and aggregate
metadata were retained, not unrelated phone logs. The buffer covered roughly
06:13:33-06:19:33Z, later than the successful startup queries, so absence here
cannot prove suppression at their original time. The existing query-only capture
has 85 records, zero upgrades, no loss/error; its health timestamp advanced but
counters did not. Do not call it a completed-OTA snapshot or a failed upgrade.

DECIDED, diagnostic capability gap: stop expanding logcat plumbing. Existing
ADB 1.0.41 / 34.0.4 and logd work; HCI already supplies packet/completion timing
but not Java callback versus main-thread delivery. Scoped DEBUG logging on the
verified native binary did not supply those markers during real queries. A global
logging change has wider scope and is not selected. A native sender rewrite still
has no evidenced large-gain forecast.

Smallest next implementation: a development-only, bounded native timing recorder
inside the existing Android plugin, explicitly started by the existing diagnostic
capture. Reuse the existing MethodChannel and App observation writer. Record
method entry, Android API submission/return, callback and main-thread dispatch
in one native monotonic clock, with exact capture/target/GATT-object/sample binding,
length and CRC but no payload. Export in batches outside DATA writes; do not add
per-write channel calls, disk I/O, fire-and-forget writes or change backpressure.
Missing callbacks, overflow, old-object callbacks and API failures remain visible.
No change to protocol, baud, credit/durable state, Boot, EEPROM or firmware.

Finite preparation: one owned `dev/flutter/**` source batch, both-host development
checks and one explicit debug APK request; then a hash-verified same-package update
and its existing automatic query-only observation. Reuse standard installer,
archive and USB helpers. Keep completed captures immutable and free a slot only
by verified backup/archive if needed. Host tests must cover disabled mode, wrong
binding, early/late/missing callbacks, API failure, overflow and export boundaries.
Exit oracle: actual query writes produce matching complete native rows in original
App records, with zero overflow/correlation errors. Otherwise reconcile that
failure without another OTA or global logging change. A saturated DATA screen
requires its own declared prospective input/matrix; this is not permission to
replay the completed WAIT_RX OTA to fill a historical log gap.

Outputs: `.cache/p34-native1`, existing task notes and project-local private Git
metadata. Root HEAD/shared index and consumed `.cache/p34-gatt1` helpers remain
untouched. No J-Link operation has occurred in this diagnostic continuation.

## GATT Attribution: Original Transfer Correlated, Native Split Still Unknown

Offline `analysis1/result.json` now verifies all2317 DATA2 frames,2390 cumulative
ACKs,1534 ATT writes and338257 wire bytes against the296551-byte package, session1,
epoch1374363845 and both complete image identities. Every App DATA chunk matches
the HCI chunk size and completed-frame count. The six host tests include negative
cases for changed/truncated package, CRC, epoch/session/sequence, missing DATA or
BEGIN ACK, and malformed cumulative state. These are diagnostics, not acceptance.

| Current observation | Result |
| --- | ---: |
| DATA GATT / nested platform / wrapper | 10.841126 / 10.567545 / 0.273581s |
| HCI first-to-last DATA span | 13.006715s |
| Within that span, no outstanding DATA completion reports | 2.075012s |
| Within that span, outstanding DATA completion reports | 10.931703s |
| Peak reported outstanding DATA packets | 12 |
| Actual DATA PHY / interval / DLE | 2M both ways / 15ms / 251 octets |

There were no DATA-phase link-parameter changes. HCI BEGIN-to-END13.329374s and
END-to-first-target17.070327s independently corroborate the App result but do not
replace its timing domain. The2.075012s is not an isolated/removable Flutter cost;
it can include credit and scheduling waits. Outstanding reports do not establish
actual airtime, queue capacity or buffer saturation. A native rewrite therefore
still has no proven large-gain forecast. Do not change serialization/backpressure.

Initial connection setup briefly used7.5ms, then45ms. Original HCI command20305
requested11.25..15ms and event20318 selected15ms before OTA. This is evidence of
the actual Android request, not an available public API to force7.5ms on API33.
The already-rejected MTU512/advertising-interval routes remain rejected.

`native1` reused the existing current report and exact original live PID22634.
Neither the current native ring nor its Bluetooth-only selection from the report
contains usable FBP write/callback markers. No new report was generated. This is
missing observation, not zero native latency. Inventory preserves all seven old
ZIP names/sizes and exactly one new ZIP plus ordinary sidecars; the original new
report hash is unchanged. All completed status/export/native-reuse owners and
private ADB sessions closed normally. No whole report was saved on the host.

Next bounded step is read-only `live1`, reusing `p34_android_trace.Trace` and its
host tests with the unchanged installed APK. It waits up to450s for a fresh INFO
query from the user's existing firmware page, under a600s owner/USB bound. No
APK rebuild/install, OTA, MCU reset, settings change or report generation. The
actual query marker gate must pass before any DATA profiling request. A query
checks observation capability only; it is not a saturated244-byte throughput
benchmark. If markers remain missing, reconcile logging before choosing a probe;
do not repeat this completed OTA or fabricate a platform/native time split.

Live preflight found the specific observation blocker: Android `log.tag=I`, with
no FBP-specific override, filters the installed library's DEBUG write/callback
markers. This is not a transport fault. Do not ask the user to perform an OTA or
rebuild the APK to fix this logging configuration. The original read-only live1
window is allowed to close at its existing deadline without a query request.

Refined finite probe: after live1 closes normally, live2 temporarily sets only
volatile `log.tag.[FBP-Android]` to `D`, preserving its read original value. Global
`log.tag=I` and all persistent properties remain untouched. Use the existing
native logger on original PID22634/same verified APK and one user-triggered INFO
query. Restore the exact original tag value and read it back BEFORE USB closure,
including timeout/collector-error paths. Four host cases test original empty/I/D
values, a failing collector body and uncertain set-response recovery; the14
original parser/collector checks are reused. No reboot, flash, OTA, install or
new system report. Owner600s/query wait450s; outputs `.cache/p34-gatt1/live2`.
Stop on an unknown tag value, another owner's tag change or restoration failure.
This is an in-scope temporary diagnostic setting, not a sender speed modification.

2026-10-08: user authorized investigating the remaining GATT path. Retain verified
C30285-wr and unchanged group16 Boot; no new OTA, installation or reset is needed
to analyze the completed WAIT_RX transfer. Original App DATA samples pair1534
GATT calls/338257 wire bytes:10.841126s outer GATT,10.567545s nested platform and
0.273581s wrapper. The previous control's1538 calls consumed10.859427s. Most of
the observed WAIT_RX improvement is outside those calls, not a faster GATT path.

The finite diagnostic route reuses the bounded report exporter under standing
LINK-NEXT-02 authority: same phone/APK, one current report, Bluetooth-only host
retention, no upload or deletion. Outputs stay in `.cache/p34-gatt1`. Read-only
status003 closed normally; the old reports predate this transfer. Export1 generated
one current report and closed normally after230.696s. Both original Bluetooth
rotations have zero reported drops/truncation and cover the exact BEGIN package
and old/new raw identities. No additional report/OTA is authorized by a parser
failure; reuse these originals.

The existing HCI/ATT decoder, CRC-preserving stream reassembler, rotation joiner
and FIFO completion accountant are reused. Their v1 correlator assumes command2,
one ACK per DATA and32-segment block waits, which does not describe current v2.
The small task-local `analyze.py` adds only v2 epoch/session/sequence, full package,
cumulative credit/durable and identity binding, with negative host cases. It must
not reinterpret outstanding HCI reports as radio airtime/full buffers or subtract
unsynchronized clocks. Match ordered App/HCI fragmentation before attribution.
Only an evidenced removable cost can justify a sender candidate. No speculative
fire-and-forget, larger MTU, window expansion or patch-distribution substitution.

## WAIT_RX Screen Complete: Modest Improvement, No Large-Gain Claim

2026-10-08: the single forward C30284-wr -> C30285-wr full OTA completed after
standard J-Link receiver installation. No bootstrap OTA, APK reinstall or repeat
transfer was used. Final `.cache/p34-waitrx1/measure/postcheck/result.json` passes
the exact623124-byte target SHA3392efc8582b3745b8e3c85a32bdb4e36c08ac5e819110e005e664f5d429f75f,
complete unchanged group16 Boot, confirmed state, VTOR, SD, no observed fault/halt,
idle session and advancing30-second health. Retain C30285/3.2.85-wr.

Original snapshot `measure/trial/cells/s04/finished/snapshot.jsonl` SHA
e0df135b06b6723cd38ca6307b91eca8e4a4dbd38135f534f3e13ab67e3a9c25 passes the original
strict envelope/identity validator. All2317 DATA ACK latency samples are present,
with0 retransmissions/early-invalid samples. The native reader captured9 identical
receiver-bound END profiles; UART/parser/drop/error counters are clean. Native,
App, network and coordinator owners exited0 without forced termination.

| Same diagnostic timing boundary | Prior ACK control | WAIT_RX screen |
| --- | ---: | ---: |
| Complete ETU bytes | 296376 | 296551 |
| Transfer seconds | 14.757523 | 13.337202 |
| Effective KiB/s | 19.612349 | 21.713744 |
| DATA retransmissions | 0 | 0 |
| ACK P99 microseconds | preserved in original summary | 461169 |
| Separate reconnect/identity seconds | 20.288076 | 17.185792 |

Derived `.cache/p34-waitrx1/screen-result1.json` records1.420321s shorter transfer,
9.6244% lower elapsed time and10.7147% higher normalized throughput. Compared with
the earlier13.814972s best historical pipeline screen, improvement is only0.477770s.
Thus this is a modest positive observation, NOT the requested new large jump and
not a proven stable causal gain. One sample, slightly different full packages and
physical Flash variability remain. Do not present an identical-package A/B,
production selection, soak or independent acceptance result.

Public MONO budget-start-to-END is13.343180s, a different boundary from diagnostic
transfer. Native payload erase/program are1.641531/0.630155s; ACK writes are1021
calls,64585 bytes,1.725123s. WAIT_RX callback time can now be nested inside those
physical-IO wrappers, and ACK/pump work overlaps; do not sum or subtract these as
exclusive hardware savings. Reconnect includes activation/Boot and Android identity
work and is not attributed to WAIT_RX. No combined whole-upgrade gain is claimed.

This bounded screen is finished; broader P3-4 acceptance and the large-throughput
objective remain open. No extra OTA is started to seek a better sample. Any next
candidate or equivalent comparison needs its declared input/state design; it must
not App-only downgrade across the newly confirmed C30285 state. Current wrappers
and original completed evidence remain immutable for future retrieval. The existing
positive pipeline archival commit b6485ca remains saved; this new operational
result is local and has not been merged, released or pushed.

## WAIT_RX Installed; Full Measurement Ready

2026-10-08: standard J-Link installation completed WITHOUT a bootstrap OTA.
`.cache/p34-waitrx1/halt1/result.json` verifies PC0x08041078 at the old
HAL::HAL_Update entry and idle SDIO. `program1` contains the standard loadbin,
reset, original debug-freeze restoration and startup log. `installed1/result.json`
passes exact623124-byte C30284/3.2.84-wr App SHA3d30dfd456616677b976c425073408743ada1ae821f9164a630bcac358917820,
unchanged full group16 Boot, confirmed state, VTOR, SD, no fault/halt, idle session
and advancing30-second health. It is installation evidence, not a speed result.

The original phone was first unauthorized (`phone2`), then authorized with the
same installed APK and awake (`phone3`). No APK reinstall. The log store was full;
`measure/archive/result.json` preserves and moves the older bootstrap capture to
the App's archive, without deletion. Latest measurement snapshot SHA0f062108a58118968580b83ed256658f73ec5e54ae8ade634a2ff117ea0be6da
and configuration remain unchanged. Inspection/archive owners exited0 normally.

The active measurement is `.cache/p34-waitrx1/measure/trial`, not any old trial.
`measure/check1/result.json` validates unchanged sender policy with the new image
bindings. Current `cells/s04/status.json` is READY_FOR_FULL_INSTALL_START for
C30285/3.2.85-wr,296551 bytes. The user has been invited to Start and keep the App
foreground; the last observed health still has upgradeStarts=upgradeEnds=0.
Do not launch another cell or auto-tap the phone. Check actual live state before
acting on this checkpoint, since the user may already have started/completed.

`measure/trace/ready.json` confirms the first standard-Commander sample matches
the installed WAIT_RX image and VTOR. The owned native sampler is finite and
stops when the App cell closes. After completion retrieve/validate the original
snapshot, native terminal profile and normal owner closure, then use
`.cache/p34-waitrx1/observe.py postcheck --arm measure` for complete C30285/Boot/
health verification. No success or speed gain is claimed while awaiting Start.
If a worker expires before Start, reconcile closure and preserve receipts before
renewing the unspent observation; never reflash or repeat a successful OTA just
to replace logs. The wrappers reuse the original lifecycle/sampler; their only
new product binding is the WAIT_RX receiver and its full forward target.

## WAIT_RX Installation Matrix (2026-10-08)

User returned ready. `phone2` saw USB unauthorized (not disconnected); `phone3`
then verified the original phone and installed APK SHA480c527d, awake, with normal
private-ADB closure. No reinstall or App launch. The new task adapter is
`.cache/p34-waitrx1/device.py`, using standard SEGGER Commander through the
existing checked-output/native-history wrapper, not a Flash algorithm.

- Owner/root: Codex root, D:/github/my/E-Track. Board AT32F435RGT7, probe123456,
  SWD1000, uninterrupted J-Link supply. One physical owner at a time.
- Inputs: the exact current C30284-ab and unchanged group16 Boot; new receiver
  C30284-wr SHA3d30dfd456616677b976c425073408743ada1ae821f9164a630bcac358917820,
  followed by the full296551-byte C30285-wr package in assets1/result.json.
- Admission: fresh whole-App/Boot and confirmed/idle/30-second-health checks;
  three SDIO STS observations without DOCMD/DOTX/DORX (mask0x3800). Stop rather
  than program on an identity, confirmation, storage or debugger-ownership failure.
- Halt: set only DEBUGMCU APB1 WDT_PAUSE bit0x1000 at0xE0042008, preserving the
  read original register. Use the standard hardware breakpoint at the verified
  old image's HAL::HAL_Update entry, then verify PC, S_HALT and idle SDIO. The
  synchronous storage task must not be interrupted by an arbitrary halt.
- Program: standard loadbin into App origin0x08010000 only, deliberate reset,
  restore the original debug-freeze register, run and allow40 seconds startup.
  No Boot, option-byte, EEPROM/BCB, staging or backup writes by the host.
- State compatibility: installed Boot CONFIRMED validates/jumps the internal
  image; App ota_confirm_test_boot returns ALREADY_CONFIRMED without committing
  EEPROM. Receiver keeps version30284, layout/hardware/minBoot unchanged, while
  its full raw identity changes. Future OTA_BACKUP stages the actual new current
  image before setting STAGED. This is not an OTA install/rollback acceptance.
- Verification: exact new whole-App bytes, whole unchanged Boot, confirmed
  health/VTOR/SD/idle and advancing30-second health before any phone transfer.
- Recovery: preserve current-device2/app.bin plus complete unchanged Boot and
  all historical readbacks. A failed command is not replay permission. If no
  Flash write occurred, remove the owned breakpoint and restore/resume the old
  image; if programming outcome is uncertain, keep it contained, read state and
  only use a validated standard complete-state route. Never App-only downgrade
  after a Boot/BCB transition or erase backup to manufacture compatibility.
- Matrix: one installation, then one forward full WAIT_RX screen with the
  existing phone/native collection route. No installation OTA. Fix baud921600,
  negotiated window24, batch12, MTU247, APK20f8b878 and group16. Prepare original
  snapshot retrieval before Start. Useful screening may lead to a separately
  declared equivalent comparison, not blind repeats or automatic soak.
- Bounds: native check180s, halt60s, programming/startup180s, readback180s;
  phone/native workers retain their existing finite deadlines and early closure.
  All controllable output stays in .cache/p34-waitrx1; standing automatic SEGGER
  native-history exception only. The task adapter receipts are the action journal.

The unchanged C30284 source and enabled binary have been checked for actual hook
binding. During pending synchronous IO the callback can only parse RAM data and
emit UART responses; CAPS/v1/BEGIN/END paths cannot start new Flash/activation,
and stopped sessions retain their overlay until the outer operation settles.
The primary added DATA/SHA path has static frames16+24+384+32+344 bytes; no recursive
poll/IO is admitted. This is targeted development review, not whole-program stack
or independent acceptance. The 313 existing and58 program-callback checks remain
bound to the actual inputs; no CRC/durable guarantee is relaxed.

## WAIT_RX Continuation: Built, Not Installed

2026-10-08: user approved the WAIT_RX plan and requested saving the previous
speed result first if missing. Verified that the positive pipeline result is
already saved locally at `b6485ca32e86253a53a978a2fc2e905198f63bb2`, branch
`checkpoint/p34-pipeline-20261007`: exact archived sources, tests and original
screen evidence for17.480900 ->13.814972s (+27.5209% normalized throughput).
It is an archival checkpoint, not integrated source on main, a push or acceptance.
Do not archive its large sources.zip again or push it as product integration.

The new App-only build uses the unchanged source records of the measured ACK
control in `.cache/p34-overlap1/f`; only `P34_OTA_PIPELINE_WAIT_RX=1` is added
to its enabled ACK-binding configuration. `.cache/p34-overlap1/fw-wait2/result.json`
records623124 bytes,216 bytes above control,641 warnings and0 errors (same warning
count as control). Actual dependency output selects the Tools ACK header. ELF
disassembly proves qspi_wait_flag -> HAL_OTA_QspiWaitRx -> receive_pending;
the inspected new callback/send/parser functions execute from internal Flash.
These are binding checks, not hardware timing or a complete stack-closure proof.

The original313 WAIT_RX host checks remain source-hash-valid. An additional
58 checks in `.cache/p34-waitrx1/test_program_rx.c` pass for receiving during
program, source-buffer immutability, deferred ABORT/premature END/conflicting
duplicate, no premature durable progress and exact resumed payload. Final host
receipt is `host2/result.json`; `host1` preserves successful tests followed by a
host disassembly CRLF-parser failure, not a firmware failure or device operation.

`.cache/p34-waitrx1/current-device1/result.json` is a fresh standard-Commander
read-only verification: exact C30284/3.2.84-ab, unchanged full group16 Boot,
confirmed snapshot/health, correct VTOR, ready SD, idle session and advancing
30-second health. No halt/reset/program command was sent. Retain this image.

`.cache/p34-waitrx1/assets1/result.json` prepares a623124-byte C30284/3.2.84-wr
receiver for prospective direct J-Link installation, and one full296551-byte
C30285/3.2.85-wr successor package. Existing native decoder exact reconstruction,
header/guard/workspace checks and four negative cases pass. The new receiver
keeps the confirmed version number but has a DIFFERENT raw image identity;
do not confuse either C30284 image or use the old map after installing the new one.
Same-version debug installation is a proposed route, not proof of live BCB,
storage-idle halt, watchdog/restart or recovery admission. Complete those checks
before programming; do not edit EEPROM merely to make the image fit.

The read-only phone check in `.cache/p34-waitrx1/phone1` reports original USB
serial10ADA4197U001CK not found. The private server closed normally, port5062
closed and the read-only ADB key was unchanged. No APK install, launch or OTA
occurred. User was asked to connect/unlock without starting an upgrade. Avoid
installing a receiver while its measurement window cannot be opened.

Next finite work: complete the remaining compiled callback/XIP/stack and live
installation checks; use standard J-Link (not a bootstrap OTA) if admitted;
verify full receiver/unchanged Boot/confirmation/health; rebind the existing
phone/native collectors and prepare original-snapshot retrieval BEFORE Start;
then one forward full-package WAIT_RX screening transfer. Fix baud921600,
MTU247, effective window24, DATA batch12, APK20f8b878 and group16 Boot. Preserve
all CRC/sequence/readback/durable and final identity checks. Stop the candidate
on integrity/recovery failure or absent end-to-end benefit, not by repeating to
find a favorable sample. Historical nonidentical-package comparison is only
screening; an equivalent controlled comparison is required before a causal claim.
No new speed result, formal acceptance, source integration or release is claimed.

## Scope Correction: Stay Within P3-4

See [the 2026-10-08 researched plan](P3-4-researched-speed-plan-2026-10-08.md).
It withdraws the unsupported startup-reordering/5-10s forecast, separates old-App
activation and Boot with original SDK samples, and explains the149/153 versus1/153
changed-block workload difference. Two real code-change pairs now have offline
verified patches of6666/12403 bytes versus296444/296354-byte full packages.
After the user's scope clarification, the reduced-byte patch proposal is DEFERRED
OUTSIDE current P3-4 execution. It is not the next task action. Preserve the offline
results, but do not implement patch distribution or claim link throughput from
smaller packages. Existing admitted patch-format test loads remain permitted;
the transport measurement and reliability requirements are unchanged. No new OTA,
firmware mutation or distribution change followed the conditional authorization.

## Current State: ACK Binding Screen Finished, No Transfer Gain

2026-10-08: measurement 30283 -> 30284 completed. Full readback in
`.cache/p34-overlap1/measure/postcheck/result.json` PASSES: exact 622908-byte
C30284 App, unchanged complete group16 Boot, confirmed BCB, correct VTOR,
SD ready, no observed fault/halt, idle session and advancing 30-second health.
No reset/programming/power cycle was used for verification. All four measurement
owners closed with exit0 and no forced termination.

Derived comparison: `.cache/p34-overlap1/screen-result1.json`, bound to both
original immutable snapshots, original strict validation receipts, full device
readbacks and stable native END profiles. Both transfers had zero DATA retries
and all2316 ACK samples; UART/parser/drop counters are clean.

| Observation | Old receiver bootstrap | Corrected receiver measurement |
| --- | ---: | ---: |
| Versions | 30282 -> 30283 | 30283 -> 30284 |
| ETU bytes | 296444 | 296376 |
| Transfer, same diagnostic boundary | 14.024562s | 14.757523s |
| Normalized throughput | 20.642077KiB/s | 19.612349KiB/s |
| Separate reconnect phase | 34.410558s | 20.288076s |
| Native ACK write calls | 2391 | 734 |
| Native ACK write time | 3.096320s | 1.436907s |

The candidate was 0.732961s slower (+5.2263% transfer time, -4.9885% normalized
throughput) in this screen. ACK batching demonstrably ran and lowered its local
cost, but did NOT deliver an end-to-end transfer improvement. Payload erase and
program times also changed; these phases overlap and one nonidentical-package
pair cannot establish a stable regression or isolate its cause. The shorter
reconnect is not an ACK-batching speed claim or measured whole-upgrade duration.

Decision: the initial ACK-binding speed screen is complete and negative. Do not
start a soak or repeat OTA just to obtain a faster sample. Retain verified C30284
without a speculative rollback; WAIT_RX remains OFF. This is development
screening, not formal acceptance or completion of the broader speed work.
The two OTA operations were one installation plus one measurement: receiving
firmware changes take effect only after the first transfer/reboot. This chosen
OTA installation route does not mean every future speed test requires two OTAs.

## Historical State: ACK Binding Installed, Measurement Pending

2026-10-08: bootstrap 30282 -> 30283 completed. The original finished snapshot
at `.cache/p34-overlap1/bootstrap/trial2/cells/s04/finished/snapshot.jsonl`
passes strict envelope/identity validation (9601 records, 9598 producer lines,
SHA-256 `c1909073d155c1b458bd5cceb56cb8b49e64f66361359de5218c9b29c1bc8e1d`).
All App/network/coordinator/native owners closed with exit0 and no forced stop.
Do not repeat this successful OTA to replace observations.

Full standard-Commander postcheck now PASSES in
`.cache/p34-overlap1/bootstrap/postcheck/result.json`: exact 622908-byte C30283
App, unchanged complete group16 Boot, confirmed BCB, correct VTOR, SD ready,
no observed fault/halt, idle session and advancing 30-second health. This was
read-only, without reset, programming or loss of power.

The bootstrap native trace has 441 samples and nine identical receiver-bound
terminal profiles. It observed v2 credit/END, zero UART/parser/drop errors and
2391 ACK write calls taking 3.096320 seconds. This is the OLD C30282 receiver,
not corrected-ACK performance. Those costs overlap other measured work and
must not be added or advertised as fully removable savings.

Original App `OTA_LINK_STATS` for this bootstrap reports transfer14.024562s,
296444 package bytes, zero DATA retransmits, all2316 ACK samples present and
P99 ACK546982us. Reconnect is a separate34.410558s. Public MONO markers give
14.031219s with their different boundaries; keep these two timing domains
separate. This provides a repaired-logging OLD-receiver observation, not a
speed result for the newly installed correction.

Next is the already prepared 30283 -> 30284 measurement, using the installed
APK without reinstall and the ACK-binding-only candidate. Keep WAIT_RX off.
Verify query/package readiness and the first live native sample before inviting
Start. The historical waiting checkpoints below are superseded by this section.

## Historical Window: ACK Binding Bootstrap

2026-10-08 00:00 local checkpoint: user reconnected the original phone.
APK run37641610751 passed both hosts and was collected/verified; installed APK
SHA-256 is `480c527d180a7a04214e596519ce91a971df8873d61baef3e3cff41d6474d35d`,
commit `20f8b878247afd36e1374f9d15a003a7c9e63af8`. The existing same-signer
installer completed once in `.cache/p34-overlap1/install1`, preserving the
original completed snapshot, configuration and permissions; its owner/USB
closed normally. No install timeout or reinstall occurred.

The old bootstrap capture was copied and moved into the App's existing archive
by `.cache/p34-overlap1/bootstrap/archive`, without deleting anything. The
latest 30282 measurement capture remains protected. Its old validator failure
is still FAILED; `history.py` only binds the exact original envelope/identity
and the complete successful board readback for continued development. Six
positive/negative historical-admission checks pass; this is not acceptance.

The first new download service in `bootstrap/trial` failed before any App launch
or OTA: cloudflared could not resolve `api.trycloudflare.com`. All its owners
and listener closed. A later normal system lookup returned valid A/AAAA records;
`bootstrap/network-recovery1.json` preserves this recovery, no system DNS change.
The original adapter source is retained in `source-revision1/trial.py`.
Do not rerun the consumed installation, archive or failed trial.

Current cell is `.cache/p34-overlap1/bootstrap/trial2/cells/s04`, NOT `trial`.
Its App PID29250, original successful GET_INFO records and downloaded 296444-byte
package have been admitted. `status.json` reports READY_FOR_FULL_INSTALL_START
for C30283. The service is a finite owned development service, not a release.
The native streaming reader is `.cache/p34-overlap1/bootstrap/trace`, owned by
`bootstrap/native-runtime`. Its first header/VTOR sample matches C30282, and
`ready.json` is present. It uses standard Commander and must settle with
`closure.json` and supervisor `closed.json`; do not start another J-Link reader.
The user has been invited to Start C30283. No successful new OTA is claimed here.

Before continuing: read the existing App/native results, not only this waiting
checkpoint. The reader stops when the App collector closes. After completion,
verify the finished original snapshot, native closure/profile and full C30283
App/unchanged group16 Boot/health with `observe.py postcheck --arm bootstrap`.
Only then prepare the measurement cell via `trial.py check --arm measure`.
`TRIAL_DIRS` explicitly binds bootstrap to `trial2`, measurement to `trial`.
Keep the current source-pinned helpers unchanged while their workers are live.

## Latest Continuation: Actual ACK Header Binding

The retained board is C30282. A new standard-Commander full App/Boot readback
and 30-second health check passed in `.cache/p34-overlap1/current-device1`.
No reset, programming, power cycle or new OTA occurred in this continuation.
The measured 13.814972-second baseline is saved on local checkpoint branch
`checkpoint/p34-pipeline-20261007`, commit
`b6485ca32e86253a53a978a2fc2e905198f63bb2`. This is an archival checkpoint,
not source integration or release; root HEAD/index were preserved, no push.

Important correction to prior notes: the measured firmware did NOT batch v2
ACKs. `HAL_Bluetooth.cpp`'s quoted include selected the stale
`USER/HAL/p34_timed_ack_batch.h`, not the updated Tools header tested on host.
Original Ninja dependency output proves that path; the measured ELF's
`s_p34_ack_batch` is 244 bytes rather than the v2 implementation's 344 bytes.
The stale implementation sends 27-byte v2 ACKs immediately. This disproves the
earlier claim that v2 had retained the 2ms/12-frame ACK batching policy; it does
not invalidate the measured transfer duration or completed image verification.

Next screened firmware changes ONLY this binding with opt-in
`P34_OTA_PIPELINE_ACK_BIND=1`. It uses the explicit repository-relative Tools
header, retains FIFO bytes, immediate durable/control responses and the 2ms
deadline. New dependency/ELF checks verify the actual compiled header and
344-byte object, not merely an independently compiled test header.
`.cache/p34-overlap1/ack-tests1/result.json` passes the existing v1/v2 tests,
extra active-pump deadline tests and both real ELF/header checks.
GCC candidate is 622908 bytes; macro-off is byte-identical to the measured
622884-byte pipeline binary. Both build warning counts remain in their reports.

Prepared forward cells are 30282 -> 30283 (`bootstrap`, 296444-byte ETU) and
30283 -> 30284 (`measure`, 296376-byte ETU), under
`.cache/p34-overlap1/assets2`. Both pass native package decoding and four
negative fixtures. Bootstrap installs the change and is not its speed result.
The actual candidate session ABI was rederived (632 bytes). Keep group16 Boot,
baud921600, MTU247, requested window28/negotiated cap24 and App DATA batch12.
No speed claim is established for this candidate yet. Screen once before soak.

The larger-MTU route is rejected for the current module configuration. The
original HCI file's SHA-256 was rechecked against
`.cache/p34-batch12/mtu-evidence.json`: phone MTU512 request, module MTU247 reply.
The last snapshot's 1570 sequential GATT samples sum to 10.451932 seconds
(including its control/query writes); do not call all 13.81 seconds Flash time
or promise 9-10 seconds from Flash overlap alone.

An alternative `P34_OTA_PIPELINE_WAIT_RX` receive-only wait hook is implemented
in the NEW isolated `.cache/p34-overlap1/f` source, with 313 passing host checks
including legacy tests, cancellation, premature END, conflicting duplicate,
buffer ownership and durable resume. It is OFF in the next screened binary.
It reuses synchronous physical operations/XIP ownership, not a new asynchronous
Flash driver. Keep it paused until the ACK-binding candidate is measured.

The sender's missing v2 MONO start/END/durable-reset markers are repaired on the
owned development branch. First CI37638170891 passed all tests (Linux690,
Windows673) but failed one unnecessary-import check, which was fixed in
`20f8b878247afd36e1374f9d15a003a7c9e63af8`; CI37640014093 was started.
That corrected dual-host checks run is now SUCCESS. Explicit debug-APK run
37641610751 was dispatched for the same commit; no APK install has occurred.
The first dispatch precheck saw a stale/not-yet-successful workflow listing and
exited before creating an intent or sending a dispatch. A subsequent fresh
dual-host SUCCESS check preceded the one actual dispatch; do not replay it.
Preserve the old failed observation receipts and never repeat that successful
OTA to replace logs. Future native sampling must run via the existing detached
finite supervisor, near actual package/phone readiness, with first-sample
identity and real closure checked. Do not use foreground exec as lifetime owner.

All preparation, logs and source copies are project-local. The only external
write allowance used is standard J-Link automatic native history/config under
the already-authorized SEGGER directory. Older waiting-state paragraphs below
are historical; they are not new device admission.

The bounded phone read at 2026-10-07 22:58 local time found serial
`10ADA4197U001CK` absent. Private ADB closed normally, port5062 closed and the
original key was unchanged. User intervention is now a real USB reconnect/unlock,
not a new permission request. No App launch/OTA/install was attempted.
The detached supervisor smoke worker survived the launching command and closed
after 10.95 seconds with exit0, no forced termination. The streaming Commander
adapter now runs under that existing owner, stops after the App collector closes,
and retains its own closure receipt. It has not yet collected a hardware trial.
The next entry still needs the new APK's verified installed identity and a fresh
phone trial binding to these packages; never replay old consumed pipeline trials.

The initial local baseline archive intentionally retains its exact historical
input tree, including large pre-existing binaries (sources.zip is 699291357
bytes). Do not push this archival branch or treat it as a lean source-integration
commit. A later integration should select the product delta rather than shipping
historical tool binaries or copying stale governance files into main.

Owner: Codex root. User authorized continued transfer-speed work on 2026-10-07.
Writable root: D:/github/my/E-Track. No new power, Boot, EEPROM or arbitrary NOR
operation is planned. Retain group16/C30278 until an admitted successor exists.
This note records development work, not achieved performance or acceptance.

## Current Decision: Prioritize Cross-Block Pipelining

The user's subsequent direction is to prioritize a materially larger potential
gain instead of repeated sub-second experiments. The early-erase two-OTA plan
below is now ON HOLD, not the next authorized execution entry. Preserve its
source, packages, failed logs and passing checks; do not install it merely
because preparation is complete. No candidate was installed before this change.

Root's selected next route is an opt-in, negotiated cross-block pipeline spanning
sender and receiver. Target the approximately 6.413 s of block-tail stop/wait,
not just the historical 1.605 s of erase calls. These tails include transport,
queue and notification time, so they are an opportunity budget, not all removable
Flash work. The initial investment gate is at least 30% higher package throughput
on comparable roughly 294 kB transfers, with unchanged integrity/recovery rules.
That corresponds to about 13.45 s or less from 17.48 s; 12-13.5 s is a screening
target, NOT a forecast or a promised result. Removing every tail while holding
other costs fixed would leave about 11.07 s / 26.57 kB/s. This route alone does
not establish 50 kB/s.

Implementation scope for the next bounded prototype:

- Negotiate a separate experimental wire revision; preserve v1 behavior and
  rejection/fallback with old peers. Do not silently extend v1's current-block
  credit or redefine its bitmap.
- Distinguish bounded volatile receive credit/accepted block identity from the
  contiguous verified persistent prefix. Two owned block buffers and the ISR
  ring have separate capacities and lifetimes. Enlarging a window alone is not
  the implementation.
- Initial screening uses partial overlap: UART ISR reception during the existing
  synchronous Flash calls, then parsing between calls. A fully cooperative port
  with complete XIP exclusion is deferred pending the first screening result.
  The vendor XIP routine's existing unbounded waits are not fixed or hidden by
  this adapter. Do not build another host flasher.
- Keep readback, ordered journal commit, final SHA/CRC, rollback and post-reboot
  verification. Lost volatile credit after interruption is never durable progress.

Batch the sender/receiver compatibility, fragmentation, delayed ACK, credit,
overflow, disconnect and every persistence-boundary interruption checks before
an integrated candidate build. Then use one bounded screening comparison before
a stability campaign. If it does not support a material gain, stop this route
rather than polishing support tools or rescuing it with sub-second side changes.

Do not simultaneously rewrite the Android queue on the assumption that the
10.258 s of GATT calls is Flutter overhead: the earlier HCI trace already had
reported outstanding DATA for 9.04 of 9.99 feeding seconds. Native batching is
a separately testable hypothesis if link service remains limiting, not a promised
2x gain. The prior feasibility note's raw-service gate still applies to a
50 kB/s claim, not as a reason to reject a smaller but material pipeline gain.

Status update: C storage/session, synchronous screening adapter, full GCC App
and actual Dart sender transport are implemented. The user-provided credential
works. Sender commit `db4f007bf63b43b7c89e2798b88af41fd1a903bd` passed explicit
APK run37604830571: Ubuntu688 pass/16 skip, Windows671 pass/33 skip, zero failures.
The final same-signer APK is installed and raw-hash verified after read-only
reconciliation of a180s host install timeout, with no repeated install. Sync
session258, cooperative session372, separate legacy171 and current core3218
checks pass. Candidate App622884B; disabled App619580B is byte-identical to R2.
Two forward packages are verified but NOT installed. The user has now granted
standing permission for J-Link automatic history/config updates under
`C:/Users/SU/AppData/Roaming/SEGGER/`, without cleanup or broader device scope.
Fresh MCU verification now passes (`current-device1/result.json`): unchanged
group16/C30278, confirmed, SD ready, idle BLE and advancing30s health; no reset or
Flash programming. V2-aware observer and sender offline checks pass, but their
live measurement remains pending. The bounded phone check now returns
PHONE_NOT_READY and Windows USB enumeration also lacks the original phone;
reconnect/unlock it before starting a fresh device window. No App launch or OTA
ran, and private ADB closed normally with the original key unchanged.
See [prototype status and API](P3-4-pipeline-prototype-2026-10-07.md).
Latest successor: the phone returned, bootstrap30278->30281 completed through
v1, and full App/unchanged group16 Boot/confirmation/health readback passed.
Bootstrap transfer17.806480s and zero DATA retransmits are not pipeline speed
evidence. Measurement30281->30282 is now downloaded/admitted in
`measure/trial-dns`, awaiting the user's Start; no v2 timing result yet. The
pre-OTA DNS failure and expired fixed native window are retained, not erased.
Current native reader is `live-capture/measure/trace`, with a finite lifetime
and early closure after the existing App collector finishes. See the latest
prototype checkpoint before resuming; do not replay consumed launch commands.
Result update: the measurement subsequently completed and full30282 App/unchanged
Boot/health readback passed. Transfer17.480900->13.814972s, normalized throughput
+27.5209%, zero DATA retries in one sample;30% target not met. The v1-only log
validator still rejects missing old MONO markers and the native runtime profile
is missing. `screen-result1.json` retains the observed result with these gaps,
not a complete acceptance or finished optimization claim. See the newest
prototype section before acting on the older waiting-state notes.
No frozen binary contract is changed by this task note. Phone USB is still
required for later measurements; the debug APK was updated while connected,
but the latest check now finds the phone offline.
Only the standard Commander readback ran in the permission follow-up, not a new
upgrade or timing measurement. Only scoped development branches were pushed earlier; root HEAD/index and
main were unchanged. Everything below records the paused smaller candidate.

## Evidence And Candidate Selection

Recomputed with the existing `p34_batch_timing.analyze` from the hash-verified
group16 original snapshot: DATA GATT 10.258001 s, last-chunk-to-durable tails
6.413182 s, other disjoint spans 0.809717 s, total diagnostic 17.480900 s.
Public BEGIN/END markers instead give 17.483523 s. Do not mix these boundaries.
The snapshot and source/artifacts are preserved by checkpoint `88549cd`.

The earlier fully instrumented timed-ACK measurement (30272 -> 30273) has
payload erase 1.604549 s, program 0.487973 s, and ACK calls 1.506127 s. These
are nested MCU measurements for an earlier receiver, not additive savings or
current R2 subphase timings. Its original report is
`.cache/p34-timed-ack/trials/measure/analysis/1791105012204966300/result.json`.

Rejected before implementation:

- Android DCK connection priority is API 34+, while the recorded phone is API 33.
  Android's documented request is a preference, not a guaranteed 7.5 ms interval;
  the inspected Android 14 default DCK interval is 24 * 1.25 ms. No APK change,
  Android upgrade, hidden API or unsupported AT command is justified here.
- Simply compacting ACK payloads inside the existing 2 ms UART batching policy
  does not establish a reduction of the dominant per-call settling overhead.
  The whole 1.506127 s must not be advertised as obtainable gain. No ACK change
  or longer ACK-hold policy is included in this first candidate.
- The preserved XY-MBO35A manual documents advertising interval, not a supported
  connection-interval or UART packetization tuning command. Do not invent one.

## First Candidate: Earlier Current-Block Erase

Development-only `P34_STAGING_EARLY_ERASE=1` moves the existing current-block
erase from block completion to arrival of its first validated, nonduplicate DATA
segment. Keep the same synchronous QSPI driver and existing erase-ahead policy;
no new Flash driver, additional block credit, page-program pipeline or buffer.
Subsequent radio/UART reception may overlap this wait through the existing ISR
ring. This is a hypothesis: main-thread processing still blocks during erase.

The default build has no macro and keeps the previous path/layout. The candidate
adds only volatile erase state, cleared on BEGIN, successful commit and failed
write/readback. Invalid, out-of-window and already-durable duplicate DATA cannot
trigger an erase. A new BEGIN re-erases any uncommitted block; partial erase or
unknown completion cannot become persistent progress. Full-block program,
readback, bitmap update and END validation remain unchanged.

Do not assume buffering is sufficient just because the window is 28: verify the
actual ring, active parser/ISR locations, combined wire bytes and retransmission
behavior while erase is blocking. A long erase can span the sender timeout;
UART drops/overflow, retries and recovery must be measured, not hidden by larger
timeouts. Do not enable the candidate on hardware before these checks pass.

## Finite Plan

1. Run existing staging/session faults in default and candidate configurations;
   add first-segment timing, duplicate, early-erase failure and interruption cases.
2. Build an isolated App from the exact R2 source, retaining its early-startup
   fixes. Compare default bytes to the saved executable; audit added RAM/stack and
   UART receive safety. No Boot rebuild or production-default change.
3. Prepare legal 30278 -> 30279 bootstrap and 30279 -> 30280 measurement assets
   only after current identity and source admission. Bootstrap installs the new
   receiver and is not its throughput measurement. Preserve the current image
   and existing complete-state recovery route; no App-only downgrade.
4. Reuse standard SEGGER readback and the existing bounded App/native collectors.
   Prepare retrieval before asking the user to connect/download/Start. Keep baud,
   window28, batch12, MTU247, 2M policy and timeout settings fixed. A new successor
   comparison is not an identical-package A/B test; report package differences.
5. Compare transfer, block tails, native erase timing, UART/parser/drop counters,
   ACK sample completeness and final identity. Stop this candidate on integrity,
   overflow/recovery failure or absent useful gain. Do not start a stability
   campaign until screening supports it. Repetitions need a declared purpose.

No prospective gain is confirmed. Even perfect hiding cannot remove more than
the eligible erase work; the historical 1.60 s is a workload budget, not a promise.
The 50 kB/s and 20 s objectives remain open. Installation/reconnect tuning and
new generic support tooling are outside this candidate.

## Implemented And Verified On Host

Evidence root: `.cache/p34-transfer-early-erase1/`. No OTA, firmware programming,
reset, CI, commit or push was performed in this continuation.

- Staging: default 114 checks, enabled existing suite 114 checks, enabled extended
  suite 360 checks including the original suite, all passing (`tests3/*-run.log`).
- Real BLE session/frame/ring/staging: default 171 checks, enabled 210 checks
  including the original suite, all passing (`tests6/result.json`). Three split
  positions for the remaining 27 DATA frames give peak 3834/4095 and zero drops.
  Window32 and a 501 ms stall plus timeout retransmissions deliberately overflow
  (307 and 3715 dropped bytes). Neither advances false durable progress; the old
  4 KiB prefix survives and a resumed whole package passes SHA/END.
- Existing teardown retains a truncated demux frame. The injected overflow cases
  need two identical BEGIN attempts, as supported by the current sender's bounded
  timeout/CRC retry. Do not reset the parser inside the fixture to hide this.
  `tests5` preserves the failed first-attempt-only assumption. This is host fault
  evidence, not a measured physical erase time or permission to ignore real drops.
- Initial MinGW host binaries exited before main for an undiagnosed host reason.
  The existing MSVC fallback worked. Session compilation uses `/utf-8 /W4 /WX`;
  the fixture's hardware revision conversion is explicitly narrowed to the wire
  uint16 type. `tests1` through `tests5` preserve all failed attempts.
- Isolated GCC App build with the macro absent reproduces the exact saved R2
  executable, 619580 bytes (`off/result.json`). The enabled build is 619628 bytes
  (`on/result.json`), only 48 bytes larger. Both builds have 639 warnings and zero
  errors; the normalized warning multisets are identical, not zero-warning builds.
- All 384 App C/C++ compilation units receive the candidate macro consistently.
  Receiver allocation grows 4168 -> 4172 bytes within the existing 40960-byte
  overlay. The new helper's frame is 16 bytes, not a whole-program stack bound.
  The RX handlers, virtual table, serial accessors and ring functions are in
  internal Flash; their existing session/profile/ring storage is in SRAM. Erase
  still uses the same synchronous polling driver without an IRQ-disable region.
  The staging byte buffer goes through memcpy into the existing aligned DMA
  buffer, not directly into DMA. See `source-audit.json` for exact symbols/inputs.

## Prepared Forward Cells

`assets/result.json` binds executable, package, map, ELF and unchanged group16
Boot. Native package decoding and four rejection cases pass for each cell:

| Cell | Version | Full ETU bytes | Meaning |
| --- | --- | ---: | --- |
| bootstrap | 30278 -> 30279 / 3.2.79-ee | 294045 | Installs the changed receiver; not its speed result |
| measure | 30279 -> 30280 / 3.2.80-ee | 294028 | Uses early erase; header-only successor |

The candidate package differs from the 294068-byte group16 reference. Compare
normalized throughput and phase costs; do not call it an identical-package A/B.
The original group16 result remains the latest actual speed measurement.

`trial.py` is a parameter adapter over the existing R2 USB/phone/network and
strict snapshot validation route. Bootstrap configuration passes the unchanged
sender policy (`bootstrap/check/result.json`); no APK change or reinstall.
`observe.py` prepares standard SEGGER Commander read-only sampling and post-OTA
readback. Its exact-symbol binding check passes; trace and new-target postcheck
have NOT run. Do not claim live observation readiness from this offline check.
Start a single bounded trace near a ready phone window and verify its first
receiver header/VTOR samples before inviting Start. It captures the existing
frozen END profile before reboot; a missing profile is a measurement gap, not
permission to repeat a successful OTA. Final target verification remains full
App/Boot readback plus 30-second advancing health, not an END ACK alone.

## Current Device And Required Intervention

Standard Commander read-only full Boot/App comparison and 30-second paired
health pass (`current-device/result.json`): retain group16/C30278, confirmed,
SD ready and no observed fault/halt. No power or reset operation was sent.

The first bounded phone inspection failed before any App/OTA operation because
the exact phone was not found on USB. Original `bootstrap/inspect-state/usb/commands.jsonl`
records eight unsuccessful `get-state` reads. The USB server and its owner closed
normally, port 5062 closed, and the original adbkey hash is unchanged. Do not
replay that consumed output directory, reinstall the App or launch a network
service to conceal the missing phone.

User action requested: connect/unlock the phone and allow a USB debugging prompt
if present; do not start an upgrade yet. Once it is online, reuse the prepared
archive adapter with a fresh bounded owner: preserve the latest group16 capture,
archive the already verified inactive R2 capture without deleting it, then launch
the bootstrap cell. Actual producer/query/package readiness must precede the
user's connect/download/Start instruction. After bootstrap, complete target
postcheck before admitting the measurement cell. No new speedup is claimed.

References for the rejected standard API route:
https://developer.android.com/reference/android/bluetooth/BluetoothGatt#CONNECTION_PRIORITY_DCK
https://android.googlesource.com/platform/packages/modules/Bluetooth/+/refs/heads/android14-release/android/app/res/values/config.xml
