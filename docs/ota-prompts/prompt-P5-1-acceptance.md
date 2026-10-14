# P5-1 双通道回归验收 Spec

task_id: P5-1

## 任务类型

`ACCEPTANCE`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P5-1` 行。本文件不得另行维护该状态。本文件定义未来验收边界，不是已冻结的版本化 acceptance contract。

## 验收范围

在同一受控发布候选上核验 SD/BLE × full/patch 四个组合，每个组合至少有一轮真实 MCU 升级原件；每轮从已知 CONFIRMED 起点开始，经 staging/candidate/Boot TEST_BOOT 到新 CONFIRMED，并在升级后用 GET_INFO、fw_header/BCB 和目标 metadata 复核版本与镜像身份。

按 `OTA-DEC-016`，本卡统一承担稳定交付候选的一套 BLE 同组 30/30 参考包完整成功与真实
四小时 soak，数值/统计规则仍以 `OTA-XC-BLE-TUNING` 为准。先独立评估已有适用原件，
缺什么才新增什么；不要求实现者与验收者各做一套，也不把每个四组合都扩为 30 次。
同一预先声明且条件匹配的观察可同时支撑四组合、30/30 或 soak 的适用判据；统计仍分清
通道、包、版本和参数组，不能事后拼接成功笔或用空闲/恢复耗时凑传输时长。

## 非目标

- 不把 P3-5 的 BLE 10 次断连或 P5-2 的故障矩阵全部重复一遍。
- 不在验收会话修改生产实现来“顺手修复”后继续判通过。
- 不创建临时协议、替代摘要或手工改 BCB 作为成功路径。
- 不提前在本轮创建 `docs/acceptance-contracts/P5-1-v1.contract.json`。

## 前置依赖

- `PLAN-OTA-EXEC.md` 的 P5 阶段门槛：P1-P4 适用阶段完成并独立收口；P3-4 为候选阶段，P4-1/P4-4 为 staging 演练阶段。不等待本卡自己的长测或 P5 后生产晋升，不由本次规则更新自动改变任务状态。
- 同一目标版本的 finalized App、full、目标基版 patch、recovery/metadata 和 Actions APK 可追溯。
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
- 输出记录完整状态轨迹、staging/BCB 关键提交、最终 GET_INFO、fw_header/BCB 对比和人机 UI 结果。

## 状态机与生命周期所有者

- 渠道只改变包进入 staging 的方式；staging 后 package/apply/Boot 状态机必须共用同一生产实现。
- MCU BCB 是升级状态真相，GET_INFO 是重启后设备身份真相，metadata 是目标期望真相。
- 验收 harness 只采集和注入明确操作，不拥有产品状态，也不得写固定结果。

## 错误、超时、重试、取消、恢复与幂等

- 非计划断连、超时、卡/Flash 异常或用户误操作均保留实际尝试并先分类、取证、定位；不自动从起点重跑直至成功。只有实际修复或不可补取的必要观察才按执行合同最小复验，不剪掉失败片段拼成成功。
- full/patch 选择必须可由 current image hash 和 latest/SD metadata解释。
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

- P1-P4 适用阶段未完成，或共享合同发生未重新冻结的变更时，不开始正式验收；不把本卡长测或生产晋升反作入场前置。
- 无法绑定 v3 冻结对象、真实依赖或设备已知起点时停止。
- 发现产品缺陷后立即停止判定并回实现流程，不在同轮修补。
- 需要用户物理操作而用户不可用时记录环境阻断。

## 正式 acceptance contract 前置

只有在 P1-P4 适用阶段完成、候选稳定、相关共享条款冻结、四组合及长测命令/证据字段可精确绑定、v3 冻结对象与已审批 profile 可核对后，才由同一独立验收者准备/检查首个版本化 P5-1 contract，无需第三个冻结 agent。后续按真实生产/判据/runner 变化升版本、走父链及最小复验；换验收者本身不是升版或重测理由。

## 后续证据

正式 contract、evidence matrix、四组合及长测原件、视频/截图、RTT/J-Link/SQL/API 日志、冻结对象及 artifact SHA、全部失败轮、既有原件独立评估和最终报告。

## Luna 可自行决定

证据目录布局、自动采集脚本语言、每轮编号和报告排版；不得自行减少组合、required 证据或改变 PASS 判定。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
