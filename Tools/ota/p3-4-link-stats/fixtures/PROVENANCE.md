# P3-4 解析器夹具来源与身份（fixtures/）

本目录只放两类夹具，二者界限不得模糊：

1. **逐字节真实切片**：从真实 CI 捕获中按连续行范围原样截取，未改动任何字节；
2. **由 selftest 运行时构造**：样本行取自真实切片，摘要按当前契约由
   `selftest.py` 独立重算生成（不落盘为夹具文件，避免与真实捕获混淆）。

不设"人工删改过的真实文件"这一类：需要控制的形状一律在 selftest 内构造并
声明构造方式。

## round6-ubuntu-head.log

| 项 | 值 |
|---|---|
| 来源 | `.cache/ci-35034258547/ubuntu/run-9ed6a289b26f4f9da5c2d3d682df6bdb/logs/tests.log` |
| 来源 SHA-256 | `1cc73fa22e4cb692b685a5fb582380de189a84faa0f6d11927219068dc8406e6`（179,715 B，1,582 行） |
| 来源轮次 | CI run 35034258547（第五轮），提交 `1256e2f`，Ubuntu 任务 `tests.log` |
| 截取范围 | 第 1–274 行（含首尾），**末行是 `OTA_LINK_STATS` 摘要**，故块边界完整 |
| 夹具 SHA-256 | `d482f9ed386a064146992585fdf93ab2738f1b785c2bdc2e910e0d81c37bf645`（41,982 B，274 行） |
| 体量依据 | 只保留能覆盖形状的最短完整前缀，避免把整份 180 KB 日志入库存疑 |

覆盖到的真实形状：

- **噪声行**：同一文件里混有 `00:21 +157: <测试名>`、`Mobile蓝牙扫描已启动`、
  `OTA sent n/total`、`OTA_MONO ...` 等非 `OTA_LINK_` 行 → 解析器不得因噪声行
  报错或错位；
- **整改前发射端**：4 份摘要均为 `schema:1` 但缺 R01/R04/R05 新增字段
  （`transfer.ackEarlyInvalid`、`transfer.ackEarlyUnsent`、`getInfo.failures`、
  `discovers.errors`、`platformWrites.errors`）→ 覆盖 `FIELD_ABSENT`（warn）；
- **单实例已收口块**：4 个观测块（upgrade 30 样本 ×2、probe 4/2 样本），
  块内时钟单调、计数与摘要逐键相等 → 在默认与 `--device-capture` 两种模式下
  都**不得**产生致命发现（严格模式不是"一律打红"）。

本切片**不**覆盖（由 selftest 构造覆盖，见 `selftest.py` 覆盖矩阵）：
多实例同块（`MULTI_INSTANCE`）、摘要后拖尾样本（`STRAGGLER`）、末尾未收口
块（`SUMMARY_MISSING`）、以及全部摘要变异负例。整份真实日志上的解析结果
（0 致命 / 143 告警，含上述三类）记录在
`docs/ota-exec-notes/P3-4-wiring-impl-2026-09-16.md`。
