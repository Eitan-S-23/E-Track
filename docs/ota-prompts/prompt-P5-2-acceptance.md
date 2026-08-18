# P5-2 故障注入矩阵验收 Spec

task_id: P5-2

## 任务类型

`ACCEPTANCE`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P5-2` 行。本文件不得另行维护该状态。本文件不提前创建或冻结版本化 acceptance contract。

## 验收范围

按 `PLAN-OTA.md` §8 和冻结状态机，对每个持久化提交点、擦写/搬运、窗口 ACK、HTTP/BLE 重连及运营停发执行可重复故障注入；每例必须输出状态轨迹、最终版本摘要以及“可启动或进入恢复”的二判。覆盖弱信号、低电量、满 staging、降级包、坏包、错板、TEST_BOOT 三连失败、recovery 和物理断电抽样。

## 非目标

- 不通过一次随机“拔电试试”替代系统矩阵。
- 不把 P1-6 已有证据无条件复制为当前候选通过；只可在 manifest/判据完全匹配时复用并说明。
- 不在验收卡发明新的恢复状态、错误码或降级例外。
- 不提前创建 `docs/acceptance-contracts/P5-2-v1.contract.json`。

## 前置依赖

- P1-P4 全部完成，P5-1 基本双通道主路径通过。
- 所有注入点、触发方法、恢复判据和安全边界可由冻结实现/合同定位。
- 物理断电、低电量和手机弱信号项目需要用户配合。
- HTTP 恢复、BLE 参数、App 兼容、保留策略、rehearsal gate、Admin 幂等和 token v2 的用户裁定已传播到共享合同；共享合同仍须独立复核和冻结。

## 权威合同

- `OTA-XC-HTTP-RESUME`
- `OTA-XC-HTTP-DOWNLOAD`
- `OTA-XC-HTTP-ERROR`
- `OTA-XC-BLE-LIFECYCLE`
- `OTA-XC-BLE-TUNING`
- `OTA-XC-CANCEL-RECOVERY`
- `OTA-XC-D1-STATE`
- `OTA-XC-D1-RETENTION`
- `OTA-XC-HTTP-ADMIN`
- `OTA-XC-ADMIN-RETRACT`
- `OTA-XC-ADMIN-STOP`
- `OTA-XC-ADMIN-IDEMPOTENCY`
- `OTA-XC-SECURITY`
- `OTA-XC-TEST-VECTORS`
- `docs/ota-binary-contracts.md` §3、§4、§5、§6、§7
- `docs/acceptance-execution-contract.md`

## 现有组件和代码入口

- Boot BCB/state machine 和 P1-6 断电注入 harness/证据。
- MCU staging/package/patch/backup/SD/BLE transport。
- Flutter download/BLE/重连/UI。
- Worker latest/download/register、D1 channel/assets、admin retract/stop。
- J-Link/RTT、Flash/EEPROM/SQL/API 只读或受控注入工具。

## 输入输出与调用方向

- 输入矩阵每行定义：caseId、通道/包型、起点、注入点、触发方法、期望不变量、允许恢复路径、required evidence、清理步骤。
- 输出每例保存注入前后 BCB/ETSL/ETRJ/bitmap/Flash/INFO、HTTP/BLE/admin 状态和最终可启动性。
- harness 注入只能作用于该 case 指定位置；下一例前恢复并验证干净起点。

## 状态机与生命周期所有者

- 产品状态仍由 BCB/staging/Worker channel 等生产组件拥有。
- harness 只触发断电、IO 错误、网络断开、错误输入或运营操作，不直接写“期望终态”。
- 物理断电案例和可自动复位案例分开标注；自动复位不得冒充真断电。
- recovery 只在冻结物理在场条件和正常链不可用时进入。

## 错误、超时、重试、取消、恢复与幂等

- 每个持久化提交点至少有“提交前中断”和“提交后中断”可区分证据。
- BLE/HTTP 恢复按最终合同，旧 session/URL/metadata 不得静默复用。
- 低电/弱信号等环境条件必须有可量化观测，不仅由用户口述。
- 错板、降级、坏 CRC/SHA、满 staging 必须在合同阶段拒绝且不破坏当前可启动版本。
- TEST_BOOT 三次失败必须进入冻结 rollback/recovery 结果，不能靠额外手工重启改变计数。

## 允许修改范围

- 验收 harness、test-only 注入点、项目内 evidence、正式 contract/evidence matrix（满足前置后）。
- test-only 代码必须受构建开关隔离并有生产构型零命中证明。
- 产品缺陷修复必须退出本验收轮并回对应实现卡。

## 禁止修改与生产红线

- 禁止在生产构型留注入开关、固定结果或绕过 CRC/SHA/版本/错板检查。
- 禁止为了某例通过手工写 BCB/Flash 最终值。
- 禁止复用错误 RTT 地址、旧 logger、旧 map/ELF 或污染 SD/R2 对象。
- 禁止把未执行的物理断电、低电量、手机操作记 PASS。
- 禁止删除失败 evidence，只保留重跑成功结果。

## 证据分类与采集

- Production：每层生产源和 artifacts manifest。
- Validation：注入 harness、case matrix、命令、工具版本、raw logs、Flash/EEPROM/D1/API snapshots、照片/录像。
- Governance：合同/提示词/正式 acceptance contract、审批、CI 和 rerun lineage。
- 每例记录实际注入时间/位置、前后状态、启动结果、最终 version/hash 和清理确认。

## 判定规则

- 每个 case 的 required 不变量全部满足且最终“可启动或进恢复”二判成立才 PASS。
- 拒绝类案例必须证明 current confirmed image 未被破坏；恢复类必须证明从持久化点继续而非从错误中间状态猜测。
- 任何 required case 未执行或证据不可信，矩阵不能“全绿”。
- 物理案例可因用户不可用记环境阻断，但不能降低矩阵要求。

## 结果分类

使用 `PASS`、`PRODUCT_FAIL`、`EVIDENCE_GAP`、`ENV_BLOCKED`、`HARNESS_FAIL`。多次运行保留 lineage，最新 PASS 不覆盖旧 PRODUCT_FAIL 的根因记录。

## 失效条件

- 注入点未实际触发、触发位置无法证明或注入改变了其他状态。
- case 间未恢复干净起点，或 Flash/SD/R2/logger 地址污染。
- manifest、contract、harness 或生产 artifact 在矩阵执行中变化。
- 证据只含汇总结论，没有原始状态/命令/文件 hash。

## 必须新增或调整的测试

- case schema/矩阵完整性检查，确保每个冻结提交点有覆盖。
- harness 正反向自检：未触发、错地址、常量 PASS、缺 evidence、错误终态均被拒。
- 自动 case 与物理 case 分组、rerun lineage 和清理验证。
- HTTP/BLE/D1/admin/Boot/SD 跨层故障和最终摘要交叉校验；覆盖 `XC-DIGEST-DOMAINS` 与 `XC-ADMIN-IDEMPOTENT-TOMBSTONE-RACE`，证明摘要域不混用且 Cron 清理顺序不改变旧 key 边界结果。

## 完成判据

- 所有 required case 有最终分类；报告“全绿”只允许全部为 PASS。
- 每例都有状态轨迹、最终 version/hash 和二判证据。
- TEST_BOOT 三连失败、recovery、错板/降级/坏包、满 staging 和断连恢复均有决定性证据。
- 生产构型无 test-only 注入，设备和云端恢复已知安全状态。

## 停止条件

- 任一受影响共享条款尚未独立复核并冻结、P1-P4 未完成，或 P5-1 主路径未通过时，不开始正式矩阵。
- 注入可能永久损坏 Boot/硬件且无批准恢复方案时停止。
- 用户物理配合不可用时停止对应 case 并准确分类。
- 发现产品失败时停止相关分支，回实现/整改，不继续累积污染证据。

## 正式 acceptance contract 前置

只有在最终生产提交点/符号/接口已稳定、全部 caseId/注入方法/required evidence 可精确描述、test-only 隔离可静态证明、物理配合边界获得确认并经独立审查后，才创建首个版本化 P5-2 contract。

## 后续证据

版本化矩阵、每例 raw 目录、J-Link/RTT/Flash/EEPROM/API/SQL/手机证据、manifest、harness 自检、失败整改和最终清理报告。

## Luna 可自行决定

自动注入 runner、case 文件组织、日志解析和可视化方式；不得自行删减注入点、替换物理案例或改变判定。

## 阻断性决策

- `OTA-DEC-002`：跨系统镜像身份摘要域与 full fallback 边界。
- `OTA-DEC-003`：BLE 性能门槛、统计口径与候选参数组合。
- `OTA-DEC-004`：App 版本查询范围与阻断语义。
- `OTA-DEC-005`：HTTP 单区间恢复、partial 身份与保留窗口。
- `OTA-DEC-007`：资产保留、引用保护与删除治理。
- `OTA-DEC-008`：rehearsal/production 隔离、证据与 release gate。
- `OTA-DEC-011`：Admin release action 幂等范围、持久化与 recovery 重试窗口。
- `OTA-DEC-012`：下载 token v2、排他 expiry 与 v1 cutover。
