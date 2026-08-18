# P5-1 双通道回归验收 Spec

task_id: P5-1

## 任务类型

`ACCEPTANCE`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P5-1` 行。本文件不得另行维护该状态。本文件定义未来验收边界，不是已冻结的版本化 acceptance contract。

## 验收范围

在同一受控发布候选上执行 SD/BLE × full/patch 四个组合，每个组合至少一轮真实 MCU 升级；每轮从已知 CONFIRMED 起点开始，经 staging/candidate/Boot TEST_BOOT 到新 CONFIRMED，并在升级后用 GET_INFO、fw_header/BCB 和目标 metadata 复核版本与镜像身份。

## 非目标

- 不把 P3-5 的 BLE 10 次断连或 P5-2 的故障矩阵全部重复一遍。
- 不在验收会话修改生产实现来“顺手修复”后继续判通过。
- 不创建临时协议、替代摘要或手工改 BCB 作为成功路径。
- 不提前在本轮创建 `docs/acceptance-contracts/P5-1-v1.contract.json`。

## 前置依赖

- `PLAN-OTA-EXEC.md` 既有 P5 阶段门槛：P1-P4 全部完成并各自独立收口。
- 同一目标版本的 finalized App、full、目标基版 patch、recovery/metadata 和 Actions APK 可追溯。
- 四组合所需的当前版本/基版镜像均可恢复到已知状态。
- 相关行为边界见本卡引用的共享候选合同；共享合同仍须独立复核和冻结，不能仅凭候选文本启动验收。

## 权威合同

- `OTA-XC-INFO-MAPPING`
- `OTA-XC-IMAGE-IDENTITY`
- `OTA-XC-HTTP-LATEST`
- `OTA-XC-ASSET-SELECTION`
- `OTA-XC-HTTP-DOWNLOAD`
- `OTA-XC-BLE-LIFECYCLE`
- `OTA-XC-FLUTTER-TRANSPORT`
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

- 输入组必须分别绑定 Production、Validation、Governance manifest；具体文件集合在实现稳定后由正式 contract 冻结。
- 每轮输入记录 source/target versionCode、source/target image identity、asset kind/hash/size、channel/releaseId、设备/Boot/App artifact hash。
- 输出记录完整状态轨迹、staging/BCB 关键提交、最终 GET_INFO、fw_header/BCB 对比和人机 UI 结果。

## 状态机与生命周期所有者

- 渠道只改变包进入 staging 的方式；staging 后 package/apply/Boot 状态机必须共用同一生产实现。
- MCU BCB 是升级状态真相，GET_INFO 是重启后设备身份真相，metadata 是目标期望真相。
- 验收 harness 只采集和注入明确操作，不拥有产品状态，也不得写固定结果。

## 错误、超时、重试、取消、恢复与幂等

- 每轮出现非计划断连、超时、卡/Flash 异常或用户误操作时，该轮失效并从已知起点重跑，不剪掉失败片段拼成成功。
- full/patch 选择必须可由 current image hash 和 latest/SD metadata解释。
- 重复 DATA、SD 两遍读取、Boot resume 等幂等由各冻结合同判定；验收只观察，不放宽。
- 若环境失败与产品失败无法区分，结果为证据缺口，不得判 PASS。

## 允许修改范围

- 原则上只允许验收 harness、版本化 contract/evidence matrix（达到前置后）、项目内证据和验收报告。
- 若发现产品缺陷，停止验收并回对应实现卡；修复后生成新候选、重新冻结输入 manifest，再开始新轮。

## 禁止修改与生产红线

- 禁止在验收工作树修改生产源码、workflow、D1 数据来追求绿灯。
- 禁止使用 debug-only 跳转、跳过 startup/Boot、手工写 candidate/BCB 代替真实通道。
- 禁止混用不同 commit、map、ELF、APK、asset 或旧 evidence。
- 禁止把 UI 100%、END ACK 或 App 断开当最终成功。

## 证据分类与采集

- Production：MCU/Boot/Flutter/Worker/发布脚本和最终 artifacts 的 manifest/hash。
- Validation：harness、命令、工具版本、日志、截图/录像、J-Link/RTT/SQL/API 原始证据。
- Governance：冻结合同、提示词、正式 acceptance contract、evidence matrix、审批和 CI run。
- 每轮至少采集：起点 BCB/INFO、asset metadata、传输完成、TEST_BOOT、CONFIRMED、最终 INFO、最终 fw_header/BCB、包和镜像摘要。

## 判定规则

- 四组合分别独立 PASS，才可汇总 4/4。
- 最终 versionCode 和统一镜像身份必须等于目标 metadata，状态必须 CONFIRMED，设备可正常启动。
- patch 轮必须证明基版匹配且最终 candidate 与目标 finalized App 一致；full 轮必须证明不依赖 patch 基版。
- 任一 required 证据缺失、来源不匹配或 manifest 漂移，整轮不得 PASS。

## 结果分类

按 `docs/acceptance-execution-contract.md` 使用 `PASS`、`PRODUCT_FAIL`、`EVIDENCE_GAP`、`ENV_BLOCKED`、`HARNESS_FAIL`；不得新增“基本通过”“人工认为正常”。

## 失效条件

- 生产/Validation/Governance 任一 manifest 在采集期间变化。
- 使用错误 map/ELF、旧 APK、旧包、旧 signed URL 或未校验 SD 文件。
- harness 结果可由常量、缺命令、缺原始日志或手工编辑产生。
- 设备起点/终点状态不明，或真机观察不能绑定到本轮 artifact。

## 必须新增或调整的测试

- 四组合 evidence matrix 和自动一致性检查。
- 每轮 package/target image hash、BCB/INFO 字段和 manifest 交叉验证。
- 正反向 harness 自检，证明缺证据/错 hash/错 artifact 会失败。
- 最终无测试插桩生产构型静态扫描和必要 fresh build/CI 结果。

## 完成判据

- 4/4 独立通过，所有 required 证据可复算且绑定同一候选。
- 每轮最终设备可启动、CONFIRMED、GET_INFO 与 fw_header/BCB/metadata 一致。
- 失败/失效轮保留并明确排除，不能只报告最后成功轮。
- 正式验收报告列出所有命令、工具版本、hash 和剩余风险。

## 停止条件

- P1-P4 任一卡未完成，或共享候选合同尚未独立复核并冻结时，不开始正式验收。
- 无法建立独立三类 manifest 或设备已知起点时停止。
- 发现产品缺陷后立即停止判定并回实现流程，不在同轮修补。
- 需要用户物理操作而用户不可用时记录环境阻断。

## 正式 acceptance contract 前置

只有在 P1-P4 实现候选稳定、相关共享条款冻结、四组合命令/证据字段可精确绑定、三类 manifest 可生成且独立审查人确认 harness 边界后，才创建首个版本化 P5-1 contract。后续任何生产或判据变化必须升版本并走父链。

## 后续证据

正式 contract、evidence matrix、四轮原始目录、视频/截图、RTT/J-Link/SQL/API 日志、artifact/manifest hash、失败轮和最终报告。

## Luna 可自行决定

证据目录布局、自动采集脚本语言、每轮编号和报告排版；不得自行减少组合、required 证据或改变 PASS 判定。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
