# P3-5 真机 BLE 闭环集成 Spec

task_id: P3-5

## 任务类型

`INTEGRATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-5` 行。本文件不得另行维护该状态。本卡需要用户操作手机。

## 目标

使用 Actions APK 和生产候选 MCU/Worker 链完成手机查询设备、latest 选包、下载、BLE 传输、MCU 升级、重启重连、GET_INFO 确认的真实闭环，并执行断连 10 次续传验收。

## 非目标

- 不在集成会话重新设计协议、API、UI 或数据库。
- 不用 PC sender 替代本卡要求的手机 App 主路径。
- 不把 toy 包成功替代正式包成功；两者用途分别留证。
- 不执行物理断电故障矩阵，那属于 P5-2。

## 前置依赖

- `P3-1`、`P3-2`、`P3-3`、`P3-4` 的实现和适用冻结合同已完成复核。
- `P4-2` 必须先提供真实 register/latest/download 链、R2 全字节 readback、D1 ready release，以及由 `OTA-XC-SCHEMA-FIXTURE` 约束的 versioned fixture。
- 依赖方向固定为 `P4-2 -> P3-5`。本卡与 `P4-1` 之间不建立自动依赖；不得手改 D1 或使用任意静态 JSON 冒充真实闭环。
- 用户可操作手机安装 APK、授权蓝牙并按步骤制造断连。

## 权威合同

- `OTA-XC-INFO-MAPPING`
- `OTA-XC-IMAGE-IDENTITY`
- `OTA-XC-HTTP-LATEST`
- `OTA-XC-ASSET-SELECTION`
- `OTA-XC-HTTP-DOWNLOAD`
- `OTA-XC-D1-STATE`
- `OTA-XC-SCHEMA-FIXTURE`
- `OTA-XC-BLE-LIFECYCLE`
- `OTA-XC-FLUTTER-TRANSPORT`
- `OTA-XC-CANCEL-RECOVERY`
- `OTA-XC-TEST-VECTORS`
- `docs/ota-binary-contracts.md` §5

## 现有组件和代码入口

- P3-1 MCU transport 和 P3-2 identity provider。
- Flutter `OtaService`/transport/UI 和 GitHub Actions APK artifact。
- Worker public firmware latest/download、R2 测试资产。
- J-Link/RTT 只用于旁证 MCU 状态，不能替代手机端真实操作。

## 输入输出与调用方向

- 输入：同一 commit 的 MCU 固件、Actions APK、ready test release、手机/设备连接、预定义断连脚本。
- 输出：每轮 device info、latest selection、asset metadata/hash、HTTP 下载结果、BLE ACK/durable 轨迹、重连次数、最终 INFO 和 BCB/RTT 辅助证据。
- 每轮必须记录目标包和目标镜像身份，避免跨轮复用旧文件或旧 signed URL。

## 状态机与生命周期所有者

- Flutter 是用户流程和重连 owner，MCU staging/BCB 是 durable owner，Worker 是选包 owner。
- 断连点必须分布在不同 durable 进度；重连后只接受 MCU 返回的恢复位置。
- 升级完成以“重启后新连接 GET_INFO 与目标 version/hash 一致”为终点，不以 END ACK 或 UI 100% 为终点。

## 错误、超时、重试、取消、恢复与幂等

- 10 次断连必须是 10 个独立、可追溯的恢复事件；不得只开关页面而 BLE 未断。
- 旧 signed URL 过期、App 后台、蓝牙权限变化等非目标干扰需单独分类，不得混入续传通过数。
- 同一 durable 段重发必须无额外 Flash 写；最终包 hash 必须一致。
- 任一未知错误按共享合同停止，不允许手动跳过校验继续。

## 允许修改范围

- 原则上只生成项目内集成 harness、证据和必要的最小缺陷修复。
- 若发现真实产品缺陷，可修改 P3-1/P3-2/P3-3 原允许范围及对应测试；不得扩大到冻结合同或无关模块。
- `docs/ota-exec-notes/P3-5-*.md` 和项目内专用验收目录。

## 禁止修改与生产红线

- 禁止手工改 D1/包 hash/MCU 状态来制造成功。
- 禁止使用 debug-only 固件或跳过 startup/Boot/BCB 主路径作为最终证据。
- 禁止把用户手机上的旧 APK、旧包或缓存 metadata 当本轮产物。
- 禁止执行未获用户同意的手机、账号或项目外文件写入。

## 必须新增或调整的测试

- toy 包端到端冒烟，确认诊断链可用。
- 正式 full 或 patch 包完整升级一轮。
- 断连 10 次续传，覆盖未 durable、部分 bitmap、整块刚提交和接近包尾等不同位置。
- 升级后再次 latest 应返回 no update，GET_INFO 版本/摘要与 release metadata 一致。
- 失败轮必须从计数中剔除并在修复后从干净状态重跑。

## 完成判据

- 手机主路径查询、下载、传输、重启、重连全部完成。
- 10/10 断连恢复成功，每轮都有 durable_off/bitmap 前后证据和最终版本摘要。
- 无旧 session、旧文件、旧 URL、第二个 logger 或 debug 构型污染。
- Actions APK、MCU artifact、Worker release 和证据均绑定 commit/SHA。

## 停止条件

- 任一受影响共享条款发生未重新冻结的变更，或 `P3-1`、`P3-2`、`P3-3`、`P3-4`、`P4-2` 任一前置未完成时停止。
- 用户手机操作或权限不可用时记录环境阻断，不用 PC 路径替代最终验收。
- 发现跨层 schema 不一致时回到对应实现卡，不在集成脚本硬编码适配。
- SD/Flash/BCB 处于未知污染状态且无法恢复到已知起点时停止。

## 后续证据

保存 Actions run、APK SHA、手机录屏/截图、每轮日志和时间戳、HTTP metadata、asset SHA、BLE durable 轨迹、RTT/BCB 辅助证据、最终 GET_INFO、失败与重跑关联表。

## Luna 可自行决定

断连自动化辅助工具、日志聚合格式、证据目录组织和每个断连的精确时刻，只要覆盖不同持久化阶段且不替代用户手机主路径。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
