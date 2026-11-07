# P5-1 双通道回归验收 Spec

task_id: P5-1

## 任务类型

`ACCEPTANCE`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P5-1` 行。本文件不得另行维护该状态。本文件定义未来验收边界，不是已冻结的版本化 acceptance contract。

## 验收范围

在同一受控发布候选上核验 SD/BLE × full/patch 四个组合，每个组合至少有一轮真实 MCU 升级原件；每轮从已知 CONFIRMED 起点开始，经 staging/candidate/Boot TEST_BOOT 到新 CONFIRMED，并在升级后用 GET_INFO、fw_header/BCB 和目标 metadata 复核版本与镜像身份。

按 `OTA-DEC-020`，四组合主样本必须来自正常发布制包流程。PATCH 使用现有 vendor bsdiff + LZMA，绑定有真实代码/资源变化的新旧 finalized App，并记录相对同目标 full 的最终 ETU 大小和节省比例。只改版本头的正常小包保留为边界用例；刻意非最小化的 1 MiB 参考包只属于固定负载基准，二者不能替代代表性主样本。已有特殊样本原件仍证明其实际输入上的行为，不改写成正常差分收益。

按 `OTA-DEC-016`，本卡统一承担稳定交付候选的一套 BLE 同组 30/30 参考包完整成功与真实
四小时 soak，数值/统计规则仍以 `OTA-XC-BLE-TUNING` 为准。先独立评估已有适用原件，
缺什么才新增什么；不要求实现者与验收者各做一套，也不把每个四组合都扩为 30 次。
同一预先声明且样本目的和条件均匹配的观察可支撑多个适用判据；不能默认用特殊参考包同时代替正常四组合样本。统计仍分清
通道、包、版本和参数组，不能事后拼接成功笔或用空闲/恢复耗时凑传输时长。

## 非目标

- 不把 P3-5 的 BLE 10 次断连或 P5-2 的故障矩阵全部重复一遍。
- 不在验收会话修改生产实现来“顺手修复”后继续判通过。
- 不创建临时协议、替代摘要或手工改 BCB 作为成功路径。
- 不提前在本轮创建 `docs/acceptance-contracts/P5-1-v1.contract.json`。

## 前置依赖

- `PLAN-OTA-EXEC.md` 的 P5 阶段门槛：P1-P4 适用阶段完成并独立收口；P3-4 为候选阶段，P4-1/P4-4 为 staging 演练阶段。不等待本卡自己的长测或 P5 后生产晋升，不由本次规则更新自动改变任务状态。
- 同一目标版本的 finalized App、full、目标基版 patch、recovery/metadata 和 Actions APK 可追溯。
- `OTA-DEC-018` 的有限例外：P1 其他卡与 P2-P4 适用阶段完成、P1-6 的 14 项 AUTO 已逐项独立收口且无相关未决失败时，本卡可不等待 PHYSICAL `03/05/07/15/16/17`。AUTO 原件缺口不可豁免；六项断电义务继续留在 P1-6/P5-2，阻断整体与发布。本卡全部四组合、30/30 和四小时判据不变。
- 四组合所需的当前版本/基版镜像均可恢复到已知状态。
- 相关行为边界见本卡引用的共享冻结合同；验收输入必须绑定当前冻结版本，不能仅凭未冻结文本启动验收。

## 权威合同

- `OTA-XC-INFO-MAPPING`
- `OTA-XC-IMAGE-IDENTITY`
- `OTA-XC-HTTP-LATEST`
- `OTA-XC-ASSET-SELECTION`
- `OTA-XC-HTTP-DOWNLOAD`
- `OTA-XC-BLE-LIFECYCLE`
- `OTA-XC-FLUTTER-TRANSPORT`
- `OTA-XC-BLE-TUNING`
- `OTA-XC-RETRY-POLICY`
- `OTA-XC-TEST-VECTORS`
- `docs/ota-binary-contracts.md` 全部适用冻结条款
- `docs/acceptance-execution-contract.md`

## 现有组件和代码入口

- SD：FirmwareUpdate/OtaUpdate、`Libraries/OTA/ota_sd.*`、staging/package/patch/backup。
- BLE：P3-1 MCU transport、P3-3 Flutter transport/UI、P3-5 真机闭环。
- Boot：BCB/state machine、J-Link map/RTT 辅助读取。
- 发布：P4-1 三资产、P4-2 latest/D1/R2 metadata。
- 验证：`Tools/etu_unpack.py`、仓库内 addr2line/J-Link 工具和既有 OTA host tests。

## 输入输出与调用方向

- 输入按 v3 绑定 `freeze_commit`、`freeze_tree`、`profile_config_blob`、已审批组件 profile 和真实 `depends_on`；原始设备/资产记录用哈希绑定的 `external_inputs`，不再生成旧工作树 manifest。
- 正式 `REUSED` 保持同任务原始执行锚点；开发/用户或跨任务原件须实际执行独立离线核验并保留原操作日期、操作者和输入身份，不伪造正式来源或新的物理执行。
- 每轮输入记录 source/target versionCode、source/target image identity、asset kind/hash/size、channel/releaseId、设备/Boot/App artifact hash。
- 正常 PATCH cell 的 `functional_sample` 必须绑定 `purpose=normal-upgrade`、正常制包 `verification.json` 的 `preparation` 文件摘要，以及同目标 `full_package` 的完整文件摘要。runner 在 channel/device ownership 前复核工具编码、实际包大小与输入身份，并直接比较镜像头之外的内容；缺失、参考/诊断用途、仅改版本头或差分不更小均不得进入代表性功能 cell。该字段不追写旧合同或旧原件。
- 制包证明须保留同目录的 metadata、`steps.json`、逐步 stdout/stderr、原始 App/base、full/patch apply candidate 及资产文件；制包工具实物由现有 `tool_dependencies` 绑定。准入复算这些原件的摘要、命令输入关系及 candidate 与目标逐字节一致，并复用现有字节校验器核验实际 ETU 的包型、长度、CRC、算法/密钥编号和基版/目标身份，不能只信成功布尔值或自洽的 JSON 声明。原始 CI 命令路径只作关系核验，不在验收机重放；已验证制包原件无需每次设备执行重新制包。
- `normal-delta` 候选入口只消费受保护原始 GCC 构建与同一受保护 run 的正常制包原件，保持 `isFormalRelease=false`；不得伪装为正式基版或首发 bootstrap。若为安全起点重新封头，原始源码/构建身份、时间戳、派生版本和包装 runner 必须分开记录。初始化 full 不计作重复 full 功能验收；是否需要初始化由真实 App/BCB/备份约束决定，不因现有 runner 方便而增加 OTA。普通发布入口仍拒绝候选来源。
- 输出记录完整状态轨迹、staging/BCB 关键提交、最终 GET_INFO、fw_header/BCB 对比和人机 UI 结果。

## 状态机与生命周期所有者

- 渠道只改变包进入 staging 的方式；staging 后 package/apply/Boot 状态机必须共用同一生产实现。
- MCU BCB 是升级状态真相，GET_INFO 是重启后设备身份真相，metadata 是目标期望真相。
- 验收 harness 只采集和注入明确操作，不拥有产品状态，也不得写固定结果。

## 隔离固定负载长测入口

本节仅规定 `OTA-DEC-020` 已区分的基准样本执行方式，不改变正常四组合、共同最终候选、
30/30、真实四小时或同参数组要求。旧版本化合同及失败原件不回写；正式执行须在后继
合同中绑定实际前驱、冻结输入与机器计算的最小复验。

- 制包复用 `firmware-build.yml` 的 `candidate_mode=archived-benchmark`：只消费已归档
  的 30320/30321 finalized 镜像和两份原始 GCC/真实密钥证明，调用既有 progressing-stream、
  ETU 及 native decoder，不重新编译或封头。输入须为 `fixed-load-benchmark`，完整 ETU
  恰为 1048576 字节；metadata/source proof/native verification 与实物均须绑定。
  `benchmark.package_delivery` 必须绑定原始 run/jobs、artifact ZIP 及摘要；
  `package_binding(plan)` 复算既有归档输入的 GCC/密钥来源，并核对原生编译及 11 个
  case 的命令、stdout/observation、退出码和进程清理原件。只有成功 JSON 或缺日志不得准入。
- 交付复用 `Tools/ota/p3-3-service/service.py` 的单资产 HTTPS fixture，不改公共选择器、
  D1/R2 或正常 full/patch。`Tools/ota/p51-acceptance/fixture.py --inputs INPUT --out OUT
  --seconds 25200` 维持同一 origin；APK 构建和长测间不得重启隧道换域名。启动/停止及
  ready/status 原件必须绑定所有者，开测前剩余寿命至少为 18000+180 秒。
- App 使用现有 `build.yml` 的 `firmware_latest_url`、独立后缀 `.p51benchmark` 和相同
  `release_ota_link_profile`，`publish_release=false`。绑定实际 release-mode APK、
  application ID、版本、源码、成功 CI 及编译 endpoint；正常 APK98 准入不改变。
  `benchmark.app_build` 绑定原始 dispatch、canonical repository/run/jobs、artifact ZIP、
  双宿主成功结果和 APK 原生 badging/signature 回执。`apk_binding(plan)` 验证实际二进制
  manifest、两种 ABI 的编译 endpoint/profile、固定签名及应用身份。无 attempt 后缀的
  `android-apk` 仅接受本次新建 run 的 attempt 1，不用后来重跑的成功状态冒认旧 artifact。
- 执行复用 `run.py long --inputs INPUT --out OUT --contract CONTRACT --matrix MATRIX
  --command-id LONG`。后继输入须显式绑定 `benchmark.controls=semantic-v1`；只用既有
  package-owned UI 控件和已观测状态驱动，点击结果不明时禁止再次点击。
- 每份 recording 最多两次传输，128 MiB 上限内每次 BEGIN 前留出 64 MiB 传输预算和
  4 MiB 封存余量，剩余 recording 时间必须超过 1800 秒。开新组须留出 3000 秒；
  campaign 总计最多 18000 秒、`32-C0` 份新日志和 64 次传输，C0 为实际已有日志数。
  首组须有至少 15 个空槽，后续只校验剩余槽位；真实空间/字节不足即保留并停止，不删旧档。
  MCU 子调用共用不晚于 recording/campaign 截止前 180 秒的绝对期限；写入命令须另有
  其完整原生操作时限加 30 秒所有权检查余量，否则不启动，不将 Flash 写入截短来赶期限。
- 每次成功先保存最终 INFO、完整镜像和 BCB 原件，再在真实 30321 上查询 fixture 得到
  NO_UPDATE 清为 idle，随后按既有完整状态恢复到 30320、重连 GET_INFO 并验证
  `phase=idle,protocol=null,session=0,durable=0`，才可封存或进入下一次传输。GET_INFO
  自身不能清除 completed。已关闭 recorder 仅经现有已校验的 App 进程重启路径重新开启。
- 已封存的本地规范原件可在核对手机文件长度/SHA 后引用复用，禁止每组再次复制全部旧档；
  未知原件仍完整取回并在 seal 校验后加入 `canonicalCaptures`；该映射须包含 C0 并跨重启、
  跨组完整传递。第一次恢复必须绑定先前真实正常 BLE cell 及 normal-patch 输入，
  不伪造“先前 benchmark 成功”。旧的未执行恢复动作仍记 NOT_RUN。
- `test_p51_benchmark_execution.py` 必须覆盖错包/失效 heartbeat/非本包或禁用控件拒绝、
  一次点击后拒绝不明重试、真实服务 PATCH/target NO_UPDATE、清理前保存成功、恢复 idle、
  两组及最后可用日志槽、C0 仅下载一次、旧档更改拒绝、fixture 寿命/关闭与双宿主 CI 接线。
  原始保护包及实际 APK 必须有正例；缺原生日志/非零退出/错原始源码、非 APK/错仓库/
  错 run 或 artifact/错 endpoint 或 profile 均须离线拒绝。延迟 MCU 调用验证绝对期限和
  写入启动余量，不能仅检查源码里包含 timeout 设置。

正确：正常小差分用于功能和收益，独立 1 MiB PATCH 用于固定负载，首 30 笔全部保留。
错误：为测大包隐藏生产 full、把恢复/空闲算成载荷传输、丢失败凑 30/30，或把旧 SD
不同最终版本改写为四路均到 30321。已有 SD 原件继续独立评估，共同最终候选缺项不豁免。

## 错误、超时、重试、取消、恢复与幂等

- 非计划断连、超时、卡/Flash 异常或用户误操作均保留实际尝试并先分类、取证、定位；不自动从起点重跑直至成功。只有实际修复或不可补取的必要观察才按执行合同最小复验，不剪掉失败片段拼成成功。
- full/patch 选择必须可由 current image hash 和 latest/SD metadata解释；公共 latest 按 `OTA-XC-ASSET-SELECTION` 仅自动选择比 full 严格更小的匹配 patch，不为测试强制绕过。
- 重复 DATA、SD 两遍读取、Boot resume 等幂等由各冻结合同判定；验收只观察，不放宽。
- 若环境失败与产品失败无法区分，结果为证据缺口，不得判 PASS。

## 允许修改范围

- 原则上只允许验收 harness、版本化 contract/evidence matrix（达到前置后）、项目内证据和验收报告。
- 若发现产品缺陷，停止受影响分支并回对应实现卡；修复后按 v3 冻结新候选和计算的最小 rerun plan 复验，不默认重跑所有组合或历史 campaign。

## 禁止修改与生产红线

- 禁止在验收工作树修改生产源码、workflow、D1 数据来追求绿灯。
- 禁止使用 debug-only 跳转、跳过 startup/Boot、手工写 candidate/BCB 代替真实通道。
- 禁止混用不同 commit、map、ELF、APK、asset 或旧 evidence。
- 禁止把 UI 100%、END ACK 或 App 断开当最终成功。

## 证据分类与采集

- Production：MCU/Boot/Flutter/Worker/发布脚本的冻结 Git 对象和最终 artifacts 的 SHA-256。
- Validation：harness、命令、工具版本、日志、截图/录像、J-Link/RTT/SQL/API 原始证据。
- Governance：冻结合同、提示词、正式 acceptance contract、evidence matrix、审批和 CI run。
- 每轮至少采集：起点 BCB/INFO、asset metadata、传输完成、TEST_BOOT、CONFIRMED、最终 INFO、最终 fw_header/BCB、包和镜像摘要。
- 先保存有效窗口内必要的瞬时原件，再做可重复的语义核验；解析失败不放行，也不丢失原件或用重启后 RAM 替换传输期 RAM。

## 判定规则

- 四组合分别独立 PASS，才可汇总 4/4。
- 最终 versionCode 和统一镜像身份必须等于目标 metadata，状态必须 CONFIRMED，设备可正常启动。
- patch 轮必须证明基版匹配且最终 candidate 与目标 finalized App 一致；full 轮必须证明不依赖 patch 基版。
- 正常 PATCH 主样本须绑定正常制包命令、工具/输入摘要、真实代码/资源变化与离线 apply 逐字节一致证据；报告大小以及传输、应用、重连阶段的实际耗时，不用固定负载数据代表真实差分收益。
- 任一 required 证据缺失、来源不匹配或其冻结输入漂移，对应判据不得 PASS；未受影响结果的适用性由真实依赖决定。
- BLE 参考包必须是完整合法 `.etu` 且 `total_len=1048576`；P95 不超过 120 秒、任一轮不超过 150 秒、有效吞吐不低于 9 KiB/s、clean run DATA 重传率不超过 1%，`maxRetries=5`，30 秒无 durable 进展中止。
- timeout 与 ACK 取样仍按 `clamp(3*P99_ACK, 500ms, 2000ms)` 和共享 nearest-rank 规则；30/30、四小时及 P3-5 的 10/10 必须适用于同一候选参数组合，不从不同组合拼接。

## 结果分类

按 `docs/acceptance-execution-contract.md` 使用 `PASS`、`PRODUCT_FAIL`、`EVIDENCE_GAP`、`ENV_BLOCKED`、`HARNESS_FAIL`；不得新增“基本通过”“人工认为正常”。

## 失效条件

- 当前命令实际依赖的生产/Validation/Governance 冻结输入在采集期间变化；正式前检/终检和计算的 rerun plan 不可跳过，不把无关文案变化当成设备结果全失效。
- 使用错误 map/ELF、旧 APK、旧包、旧 signed URL 或未校验 SD 文件。
- harness 结果可由常量、缺命令、缺原始日志或手工编辑产生。
- 设备起点/终点状态不明，或真机观察不能绑定到本轮 artifact。

## 必须新增或调整的测试

- 四组合 evidence matrix 和自动一致性检查。
- 每轮 package/target image hash、BCB/INFO 字段和冻结输入交叉验证。
- 正反向 harness 自检，证明缺证据/错 hash/错 artifact 会失败。
- 最终无测试插桩生产构型静态扫描和必要 fresh build/CI 结果。
- 一套同组 30/30 和真实四小时 soak，保留全部尝试、有效 ACK 样本和不可恢复错误计数；不能用四次通道冒烟代替，也不从 P3-4 自动再复制一套。

## 完成判据

- 4/4 独立判定通过，所有 required 证据可复算且绑定同一候选；本卡负责的 30/30、四小时和性能门槛也须通过，四小时不可恢复错误数为 0。
- 每轮最终设备可启动、CONFIRMED、GET_INFO 与 fw_header/BCB/metadata 一致。
- 失败/失效轮保留并分类，不能剔除后凑 30/30 或只报告最后成功轮；确需修复后的新统计组必须事前声明并关联旧失败，不能清零历史账目。
- 正式验收报告列出所有命令、工具版本、hash 和剩余风险。

## 停止条件

- P1-P4 适用阶段未完成且不满足 `OTA-DEC-018` 有限例外，或共享合同发生未重新冻结的变更时，不开始正式验收；不把本卡长测或生产晋升反作入场前置。
- 无法绑定 v3 冻结对象、真实依赖或设备已知起点时停止。
- 发现产品缺陷后立即停止判定并回实现流程，不在同轮修补。
- 需要用户物理操作而用户不可用时记录环境阻断。

## 正式 acceptance contract 前置

只有在 P1-P4 适用阶段完成、候选稳定、相关共享条款冻结、四组合及长测命令/证据字段可精确绑定、v3 冻结对象与已审批 profile 可核对后，才由同一独立验收者准备/检查首个版本化 P5-1 contract，无需第三个冻结 agent。后续按真实生产/判据/runner 变化升版本、走父链及最小复验；换验收者本身不是升版或重测理由。

此处 P1-P4 适用阶段允许上述 `OTA-DEC-018` 例外，冻结时必须绑定 P1-6 AUTO 的独立结论并显式列出仍未完成的物理项。不能借本卡 PASS 将 P1-6/P5-2 或生产发布门禁一并关闭。

## 后续证据

正式 contract、evidence matrix、四组合及长测原件、视频/截图、RTT/J-Link/SQL/API 日志、冻结对象及 artifact SHA、全部失败轮、既有原件独立评估和最终报告。

## Luna 可自行决定

证据目录布局、自动采集脚本语言、每轮编号和报告排版；不得自行减少组合、required 证据或改变 PASS 判定。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
