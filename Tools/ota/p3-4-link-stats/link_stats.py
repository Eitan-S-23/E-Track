#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-4 链路观测日志解析器（OTA_LINK_SAMPLE / OTA_LINK_STATS）。

用途：把设备或测试轮次采集到的原始日志解析成可判定的观测记录，并按
`docs/ota-cross-system-contracts.md` 的 `OTA-XC-BLE-TUNING` /
`OTA-XC-BLE-PERFORMANCE` 冻结口径做合并统计与一致性检出。解析侧必须
fail-closed：无法解释的输入不得被静默接受（P3-4 集中预审 §7.4④ 的交付要求）。

行格式契约（发射端 `app/bluetooth_flutter_Trace/lib/ota/ota_link_stats.dart`，
格式冻结见 `docs/ota-exec-notes/P3-4-research-link-timing-2026-09-16.md` §4.2）：

    OTA_LINK_SAMPLE label=<label> kind=<kind> us=<int> [key=value ...]
    OTA_LINK_STATS {json}        ← 每个 stats 实例恰一份（幂等，仅首次）

`us` 的语义按 kind 分两类，解析器必须区分，不能一律当时间戳处理：

  * 事件时间（实例级 Stopwatch，段内非递减）：`segment_first_send`、
    `segment_retransmit`、`ack_early`、`durable`；
  * **回放时间**：`ack_early_invalid` 打印的**不是**当前时刻，而是它对应的
    `ack_early` 早到确认的到达时刻（见下节），因此不参与单调时钟；
  * 耗时（任意大小但非负）：`ack_latency`、`gatt_write`、`discover`、
    `platform_write`、`get_info`。

## 分组模型与"拖尾样本"

日志是**顺序文本**：一段连续样本 + 紧随其后的摘要 = 一个观测块。但摘要
打印的是"打印时刻的实例累计值"，同一实例（或复用该实例的调用方）在摘要
之后仍可能继续写样本——真实第六轮日志里，每个 upgrade 摘要之后都跟着
`kind=gatt_write bytes=10`（重连身份复核的 INFO 写）。这些**拖尾样本**会
落进下一个观测块的缓冲区，使缓冲区计数大于摘要声明。因此判定规则是：

  * 缓冲区计数 **大于** 摘要声明 → `STRAGGLER`（warn）：该块的样本population
    **归属不明**（含不属于本块的观测），不得进入任何数值池；
  * 缓冲区计数 **小于** 摘要声明 → `COUNT_MISMATCH`（fatal）：摘要声明了
    日志中不存在的观测，即日志截断/丢行，测量不可采信；
  * 二者相等（`exact`）时，才具备核对分位数与完整性声明的条件。

## 实测形状：一个块里可能有多个实例

真实捕获（`.cache/ci-*/…/logs/tests.log`）显示：并非每个实例都会输出摘要。
传输级用例只断言样本行、设备采集也可能在传输中途被截断，于是**若干实例的
样本会连续落进同一个缓冲区**，直到下一个摘要出现才被一起收口。此时块内会
出现实例时钟回退（新实例的 Stopwatch 从 0 重新计时），也可能**不出现回退**
（多个实例复用同一条连续 Stopwatch）。

因此时钟回退按两种模式判定：

  * 默认：回退处切分为新的实例段，报 `MULTI_INSTANCE`（warn）——块内混有
    多个实例（前序实例未收口），属真实且合法的采集形状；
  * `--device-capture`（设备采集轮次的严格块模型：每块恰一个实例且必须
    收口）：同样的回退报 `CLOCK_NONMONOTONIC`（fatal），文件末尾未收口
    观测块报 `SUMMARY_MISSING`（fatal）。

分位数与计数核对用**整块**样本重算（不猜哪一段属于收口摘要），所以混入的
外来样本只会表现为 `STRAGGLER`（观测多于声明），不会掩盖"摘要声明多于
观测"的 fatal 方向。

## `ack_early_invalid` 的回放语义（不得当普通时间戳）

发射端 `recordAckConfirm()` 遇到"该偏移尚未登记首发结束时刻"的确认时，把
到达时刻存入 `_earlyConfirmUs[offset]` 并打印 `ack_early(us=到达时刻)`；
此后 `recordSegmentSendEnd()` 首次登记该偏移时，`_onSegmentFirstSend()` 取出
该时刻并打印 `ack_early_invalid(us=同一个到达时刻)`，再打印
`segment_first_send(us=当前时刻)`。所以同一实例的合法输出序可以是：

    ack_early(us=10) → durable(us=11) → ack_early_invalid(us=10) → segment_first_send(us=20)

第三行的 `us=10` 早于第二行，但**不是**时钟回退。解析器因此把
`ack_early_invalid` 排除在单调时钟之外，并要求它关联到**同一实例段内尚未被
消费**的同 `off`、同 `us` 的 `ack_early`；关联失败报 `EARLY_ACK_UNLINKED`
（fatal）——"无关联旧时间重放"仍是必须检出的错误，不能靠放宽单调性掩盖。

## 偏移集合完整性（不按行数核对）

计数相等不能证明集合相等：复制一个 ACK 的 `off` 可以顶替另一个缺失段。
解析器按**实例段**核对首发/重传/确认的字节偏移集合：

  * 段内 `segment_first_send` 的 `off` 必须唯一（发射端 `_sentOffsets.add()`
    保证同一实例不重复首发）→ 重复报 `DUPLICATE_SEGMENT_OFFSET`；
  * 段内 `ack_latency` 的 `off` 必须唯一 → 重复报 `DUPLICATE_ACK_OFFSET`；
  * 块内每条确认的 `off` 必须能对上一条已发送（首发或重传）偏移 →
    `ACK_WITHOUT_SEGMENT`；重传的 `off` 必须先有首发 → `ORPHAN_RETRANSMIT`；
  * 首发/重传缺 `off` 或 `len` → `SEGMENT_OFFSET_MISSING`（fatal，两种模式）。

合法形状必须保留：重传不产生新的唯一段、也不产生新的 ACK 样本；多段可以
共用一个合法 ACK；新实例 resume 返回、本实例从未发送的前缀只表现为
`ack_early`/`ackEarlyUnsent`，既不制造成 ACK 样本，也不报成普通缺失段。

在严格块模型（`--device-capture`，每块恰一个实例）下上述集合违例是 fatal；
默认模式下它们是 warn，但该块随即失去"可归属性"，不进入任何数值池。

## 两类"缺失"必须分开（判定强度不同）

  * **摘要声明多于日志观测** → `COUNT_MISMATCH`（fatal）：摘要声明了日志里
    不存在的观测，即丢行/截断发生在摘要之前，测量不可采信。这是真正的
    "日志缺失"检出（摘要所属实例的样本必然全部在它收口的块内，故该方向
    不会因混组而误报）；
  * **样本之后没有摘要** → `SUMMARY_MISSING`（默认 warn）：该块没有可核对的
    声明，因此**不参与合并统计**（无摘要即无 label/终态权威）。

## 字段缺失、类型与范围（发射端版本）

`schema` 保持为 1 的同时，整改批（P34-R01/R04/R05）新增了
`ackEarlyInvalid`、`ackEarlyUnsent`、`getInfo.failures`、`discovers.errors`、
`platformWrites.errors` 等字段。整改前的真实日志因此**合法地**缺少这些
字段。解析器把缺失字段报为 `FIELD_ABSENT`（warn）并在合并报告里标注
`strictFieldsComplete=false`，绝不按缺省 0 静默通过；但在**同版本**日志
上出现缺字段仍应视为缺陷，需按发射端提交核对，报告不得据此声称契约完整。
`strictFieldsComplete` 只在"必需字段（计数键 + 绑定身份键 + 分位数键）零缺失
且至少有一个合格洁净轮"时为真——即该标记与解析器**实际执行过的核对范围**一致。

声明字段的类型与范围由 `DECLARED_FIELDS` 表逐项核对，非法类型报
`FIELD_TYPE_INVALID`（fatal）并给出结构化结论，不能让 `--json` 因 traceback
而失去结论。布尔值不当作整数（`True == 1` 不得蒙混通过）；计数相等的
声明还必须逐项等于样本重算值（含阶段分位数与 `getInfo.totalUs`）。
成功传输（`outcome == 'ok'`）的 `elapsedUs <= 0` 属非法测量
（`OTA-XC-BLE-TUNING`），报 `ELAPSED_NOT_POSITIVE`（fatal）；但单次操作的
零微秒耗时（如 `gatt_write us=0`）是合法观测，不受此限制。

## 实验身份与合并资格（`OTA-XC-BLE-PERFORMANCE`）

不同设备、MTU、写模式、波特率、超时、重试、包或发送器版本的观测不得
合成同一个门槛统计。解析器从摘要里提取**观测身份签名**
（device / mtuChunkBytes / mtuRequested / mtuSource / writeMode），并可用
`--group <sidecar.json>` 侧车声明完整的实验身份（含 baud / timeoutMs /
maxRetries / packageSha256 / packageBytes / senderCommit / firmwareCommit /
captureMethod / appState）与 `inputs[]`（原始日志路径 + SHA-256 绑定）：

  * 观测签名冲突 → 拆分为多个独立输入组并报 `GROUP_IDENTITY_CONFLICT`（warn），
    不产出跨组混合统计；
  * 侧车声明的身份与观测不符 → `GROUP_IDENTITY_MISMATCH`（fatal）；
  * 日志未列入侧车 `inputs[]` / SHA 不符 → `INPUT_UNBOUND` /
    `INPUT_SHA_MISMATCH`（fatal）；
  * 未声明身份 → 仍输出诊断统计，但 `eligibleForThreshold=false`、理由
    `GROUP_IDENTITY_NOT_DECLARED`，不得当作门槛判定依据；
  * 同一份捕获被重复引用（含同一路径重复传入、同一内容的不同副本）→
    `DUPLICATE_INPUT`（fatal）：副本不是独立轮次，重复解析会让轮数与样本数
    成倍虚增；来源标识为 `<文件名>#<内容 SHA-256 前 12 位>`，不同目录下的
    同名日志因此不会互相顶替。

侧车身份的**字段存在**不等于**身份已声明**：空串、纯空白、`unknown`/`n/a`
之类占位符与无意义的零值只说明"未采集"。除缺字段/类型非法
（`GROUP_IDENTITY_INCOMPLETE`）外，语义不值一提的取值报
`GROUP_IDENTITY_INVALID`（fatal），取值域见 `GROUP_IDENTITY_DOMAINS`：各域
取自发射端与采集流程的真实取值范围（波特率、ACK 超时、MTU、包长必须为正；
重试次数允许 0 的"不重试"策略；包 SHA-256 必须是 64 位十六进制），**不是**
新增的性能门槛。

门槛资格由"可用观测 + 本轮完整校验结论 + 已声明身份"共同决定
（见 `_qualification_reasons`）：没有合格洁净轮（`NO_ELIGIBLE_RUNS`）、没有
确认样本（`NO_ACK_SAMPLES`），或本轮仍存在致命检出（`FATAL:<CODE>`）时，
即使侧车身份齐备也不得标记 `eligibleForThreshold=true`——被排除的块与致命
检出记录仍然保留在 `excluded`/`findings` 里，不因资格标记而丢弃。

只读工具：不修改输入日志，不产生仓库外输出。退出码 0=无致命发现，
1=存在致命发现，2=用法或读取错误。
"""

import argparse
import collections
import hashlib
import json
import math
import os
import re
import sys

# 冻结契约值（与 ota_link_stats.dart 的 toJson/emitSummary 一致）。
CLOCK_DOMAIN = 'stopwatch-mono-us'
SCHEMA_SUPPORTED = frozenset([1])

TIMESTAMP_KINDS = frozenset([
    'segment_first_send',
    'segment_retransmit',
    'ack_early',
    'ack_early_invalid',
    'durable',
])
# 事件时间（参与实例单调时钟）；`ack_early_invalid` 打印的是被回放的到达时刻，
# 明确排除在外（见模块文档 §ack_early_invalid 的回放语义）。
EVENT_TIME_KINDS = frozenset([
    'segment_first_send',
    'segment_retransmit',
    'ack_early',
    'durable',
])
DURATION_KINDS = frozenset([
    'ack_latency',
    'gatt_write',
    'discover',
    'platform_write',
    'get_info',
])
KNOWN_KINDS = TIMESTAMP_KINDS | DURATION_KINDS

SAMPLE_PREFIX = 'OTA_LINK_SAMPLE'
STATS_PREFIX = 'OTA_LINK_STATS'

# 摘要必须存在的顶层嵌套对象（缺一即无法判定，不允许按缺省值继续）。
REQUIRED_SUMMARY_OBJECTS = (
    ('bind',),
    ('getInfo',),
    ('transfer',),
    ('transfer', 'acks'),
    ('transfer', 'ackLatency'),
    ('transfer', 'durable'),
    ('gattWrites',),
    ('discovers',),
    ('platformWrites',),
)

# 计数类字段：值与样本重算的对照键。整改批新增的键在旧日志上缺失属合法。
COUNTER_KEYS = (
    (('transfer', 'segmentsUnique'), 'segmentsUnique'),
    (('transfer', 'segmentSendTotal'), 'segmentSendTotal'),
    (('transfer', 'retransmitFrames'), 'retransmitFrames'),
    (('transfer', 'ackLatency', 'count'), 'ackLatencyCount'),
    (('transfer', 'durable', 'events'), 'durableEvents'),
    (('transfer', 'ackEarlyInvalid'), 'ackEarlyInvalid'),
    (('transfer', 'ackEarlyUnsent'), 'ackEarlyUnsent'),
    (('getInfo', 'calls'), 'getInfoCalls'),
    (('getInfo', 'failures'), 'getInfoFailures'),
    (('gattWrites', 'calls'), 'gattWriteCalls'),
    (('gattWrites', 'bytes'), 'gattWriteBytes'),
    (('gattWrites', 'errors'), 'gattWriteErrors'),
    (('discovers', 'calls'), 'discoverCalls'),
    (('discovers', 'errors'), 'discoverErrors'),
    (('platformWrites', 'calls'), 'platformWriteCalls'),
    (('platformWrites', 'bytes'), 'platformWriteBytes'),
    (('platformWrites', 'errors'), 'platformWriteErrors'),
)

# 确定"这条观测属于哪次实验"的绑定身份键（PERFORMANCE 要求逐项可核对）。
BINDING_IDENTITY_FIELDS = (
    ('bind', 'writeMode'),
    ('bind', 'mtuRequested'),
    ('bind', 'mtuChunkBytes'),
    ('bind', 'mtuSource'),
)

# 必须能与样本逐项重算的分位数/合计字段（缺失即无法核对，故计入必需集合）。
METRIC_FIELDS = (
    ('transfer', 'ackLatency', 'minUs'),
    ('transfer', 'ackLatency', 'p50Us'),
    ('transfer', 'ackLatency', 'p95Us'),
    ('transfer', 'ackLatency', 'p99Us'),
    ('transfer', 'ackLatency', 'maxUs'),
    ('gattWrites', 'minUs'),
    ('gattWrites', 'p50Us'),
    ('gattWrites', 'p95Us'),
    ('gattWrites', 'maxUs'),
    ('discovers', 'minUs'),
    ('discovers', 'p50Us'),
    ('discovers', 'p95Us'),
    ('discovers', 'maxUs'),
    ('platformWrites', 'minUs'),
    ('platformWrites', 'p50Us'),
    ('platformWrites', 'p95Us'),
    ('platformWrites', 'maxUs'),
    ('getInfo', 'totalUs'),
)

# 传输时序契约字段：发射端 `toJson` 自 schema 1 起恒定输出，缺任一项即
# 无从判定传输时长与成功传输的正时长要求（见 `_check_transfer_timing`）。
TIMING_FIELDS = (
    ('transfer', 'startUs'),
    ('transfer', 'endAckUs'),
    ('transfer', 'elapsedUs'),
)

# 缺失即 `strictFieldsComplete=false`，且逐项报 FIELD_ABSENT。
# `TIMING_FIELDS` 一并计入：只有三者齐备，成功传输的时长才可核对，
# 否则"删掉 elapsedUs 就没有可判定的时长"会成为绕过通道。
REQUIRED_PRESENT_FIELDS = tuple(
    [path for path, _ in COUNTER_KEYS] + list(BINDING_IDENTITY_FIELDS)
    + list(TIMING_FIELDS) + list(METRIC_FIELDS))

# 声明字段的类型/范围表：kind 见 `_kind_ok`。缺字段由 REQUIRED_PRESENT_FIELDS
# 负责，本表只在字段**存在**时判定类型，避免与缺字段告警重复。
DECLARED_FIELDS = (
    (('schema',), 'int'),
    (('label',), 'str'),
    (('device',), 'strn'),
    (('attempt',), 'int0n'),
    (('clock',), 'str'),
    (('phases',), 'obj'),
    (('failure',), 'obj'),
    (('attempts',), 'list'),
    (('attemptEndUs',), 'int0n'),
    # bind 未完成（found=false）时 charsUs/mtuUs/subscribeUs 均为 null，合法。
    (('bind', 'charsUs'), 'int0n'),
    (('bind', 'found'), 'bool'),
    (('bind', 'writeMode'), 'strn'),
    (('bind', 'mtuRequested'), 'int0'),
    (('bind', 'mtuChunkBytes'), 'int0'),
    (('bind', 'mtuSource'), 'strn'),
    (('bind', 'mtuUs'), 'int0n'),
    (('bind', 'subscribeUs'), 'int0n'),
    (('bind', 'subscribeOk'), 'bool'),
    (('bind', 'phaseUs'), 'int0n'),
    (('getInfo', 'calls'), 'int0'),
    (('getInfo', 'failures'), 'int0'),
    (('getInfo', 'totalUs'), 'int0'),
    # 非传输用例（label=probe）从不启动传输，这三项与 outcome 合法为 null。
    (('transfer', 'startUs'), 'int0n'),
    (('transfer', 'endAckUs'), 'int0n'),
    (('transfer', 'elapsedUs'), 'int0n'),
    (('transfer', 'outcome'), 'strn'),
    (('transfer', 'segmentsUnique'), 'int0'),
    (('transfer', 'segmentSendTotal'), 'int0'),
    (('transfer', 'retransmitFrames'), 'int0'),
    (('transfer', 'acks'), 'obj'),
    (('transfer', 'ackSamples'), 'str'),
    (('transfer', 'ackEarlyInvalid'), 'int0'),
    (('transfer', 'ackEarlyUnsent'), 'int0'),
    (('transfer', 'ackLatency'), 'obj'),
    (('transfer', 'ackLatency', 'count'), 'int0'),
    (('transfer', 'ackLatency', 'minUs'), 'int0n'),
    (('transfer', 'ackLatency', 'p50Us'), 'int0n'),
    (('transfer', 'ackLatency', 'p95Us'), 'int0n'),
    (('transfer', 'ackLatency', 'p99Us'), 'int0n'),
    (('transfer', 'ackLatency', 'maxUs'), 'int0n'),
    (('transfer', 'durable'), 'obj'),
    (('transfer', 'durable', 'events'), 'int0'),
    (('transfer', 'durable', 'finalOff'), 'int0n'),
    (('gattWrites', 'calls'), 'int0'),
    (('gattWrites', 'bytes'), 'int0'),
    (('gattWrites', 'errors'), 'int0'),
    (('gattWrites', 'minUs'), 'int0n'),
    (('gattWrites', 'p50Us'), 'int0n'),
    (('gattWrites', 'p95Us'), 'int0n'),
    (('gattWrites', 'maxUs'), 'int0n'),
    (('discovers', 'calls'), 'int0'),
    (('discovers', 'errors'), 'int0'),
    (('discovers', 'minUs'), 'int0n'),
    (('discovers', 'p50Us'), 'int0n'),
    (('discovers', 'p95Us'), 'int0n'),
    (('discovers', 'maxUs'), 'int0n'),
    (('platformWrites', 'calls'), 'int0'),
    (('platformWrites', 'bytes'), 'int0'),
    (('platformWrites', 'errors'), 'int0'),
    (('platformWrites', 'minUs'), 'int0n'),
    (('platformWrites', 'p50Us'), 'int0n'),
    (('platformWrites', 'p95Us'), 'int0n'),
    (('platformWrites', 'maxUs'), 'int0n'),
)

# 阶段指标：声明路径 → 样本 kind（分位数逐项重算）。
PHASE_METRICS = (
    (('gattWrites',), 'gatt_write', 'gattWriteCalls'),
    (('discovers',), 'discover', 'discoverCalls'),
    (('platformWrites',), 'platform_write', 'platformWriteCalls'),
)

# 观测身份签名：任一变化即构成不同的输入组（PERFORMANCE 冻结口径）。
SIGNATURE_FIELDS = (
    ('device',),
    ('bind', 'mtuChunkBytes'),
    ('bind', 'mtuRequested'),
    ('bind', 'mtuSource'),
    ('bind', 'writeMode'),
)

# 侧车（`--group`）声明的实验身份中必须齐备的字段。
GROUP_IDENTITY_FIELDS = (
    ('device', 'str'),
    ('mtuChunkBytes', 'int0'),
    ('mtuRequested', 'int0'),
    ('writeMode', 'strn'),
    ('baud', 'int0'),
    ('timeoutMs', 'int0'),
    ('maxRetries', 'int0'),
    ('packageSha256', 'str'),
    ('packageBytes', 'int0'),
    ('senderCommit', 'str'),
    ('firmwareCommit', 'str'),
    ('captureMethod', 'str'),
    ('appState', 'str'),
)
# 侧车声明后可与日志观测逐项对照的字段（其余为仅声明字段，日志无对应观测）。
GROUP_IDENTITY_OBSERVABLE = {
    'device': ('device',),
    'mtuChunkBytes': ('bind', 'mtuChunkBytes'),
    'mtuRequested': ('bind', 'mtuRequested'),
    'writeMode': ('bind', 'writeMode'),
}

# 侧车身份的**语义域**：字段存在且类型合法（`_kind_ok`）不等于"身份已声明"。
# 取值域取自发射端与采集流程的真实取值范围，不是另设的性能门槛：
#   * text     非空、非纯空白，且不是 unknown/n/a 之类占位符——占位符只说明
#              "没采集到"，把它当作声明会让无法归属的观测混进门槛比较；
#   * positive 正整数（波特率、ACK 超时、MTU、包长）：0 不是可工作配置；
#   * nonneg   非负整数：0 次重试是明确的"不重试"策略，属合法声明；
#   * hex64    64 位十六进制（包 SHA-256 的冻结表示，大小写不敏感）。
IDENTITY_PLACEHOLDERS = frozenset(['unknown', 'none', 'null', 'n/a', 'na',
                                   'tbd', '?'])
GROUP_IDENTITY_DOMAINS = (
    ('device', 'text'),
    ('mtuChunkBytes', 'positive'),
    ('mtuRequested', 'positive'),
    ('writeMode', 'text'),
    ('baud', 'positive'),
    ('timeoutMs', 'positive'),
    ('maxRetries', 'nonneg'),
    ('packageSha256', 'hex64'),
    ('packageBytes', 'positive'),
    ('senderCommit', 'text'),
    ('firmwareCommit', 'text'),
    ('captureMethod', 'text'),
    ('appState', 'text'),
)
# 域表必须与字段表一一对应，否则会出现"没人校验的声明字段"（fail-closed）。
if [name for name, _ in GROUP_IDENTITY_DOMAINS] \
        != [name for name, _ in GROUP_IDENTITY_FIELDS]:
    raise AssertionError('GROUP_IDENTITY_DOMAINS 必须与 GROUP_IDENTITY_FIELDS 一一对应')

# 偏移集合核对中"严格模式 fatal / 默认模式 warn"的检出码。
OFFSET_SET_CODES = frozenset([
    'DUPLICATE_SEGMENT_OFFSET',
    'DUPLICATE_ACK_OFFSET',
    'ORPHAN_RETRANSMIT',
    'ACK_WITHOUT_SEGMENT',
])

# 身份绑定类致命检出：一旦出现，身份即不可归属，合并统计不得用于门槛判定。
IDENTITY_BLOCKING_CODES = frozenset([
    'INPUT_UNBOUND',
    'INPUT_SHA_MISMATCH',
    'DUPLICATE_INPUT',
    'GROUP_IDENTITY_INCOMPLETE',
    'GROUP_IDENTITY_INVALID',
])

# 词法正则一律用 \A…\Z 全串锚定，不用 ^…$：Python 的 `$` 还匹配末尾换行之前的
# 位置，一个尾部多出 \n 的值（例如 64 位十六进制 + \n 的 65 字符包 SHA）会被
# `_identity_domain_problem()` 与 `_int()` 当成合法值接受（P34-PR3-02）。
_TOKEN_RE = re.compile(r'\A([A-Za-z_][A-Za-z0-9_]*)=([^=]*)\Z')
_INT_RE = re.compile(r'\A-?\d+\Z')
_HEX64_RE = re.compile(r'\A[0-9a-fA-F]{64}\Z')


class Finding(object):
    """一条检出。severity 为 fatal（测量不可采信）或 warn（需人工确认）。"""

    __slots__ = ('code', 'severity', 'detail', 'line_no')

    def __init__(self, code, severity, detail, line_no=None):
        self.code = code
        self.severity = severity
        self.detail = detail
        self.line_no = line_no

    def as_dict(self):
        return {
            'code': self.code,
            'severity': self.severity,
            'detail': self.detail,
            'line': self.line_no,
        }

    def __str__(self):
        where = '' if self.line_no is None else ' 行 %d' % self.line_no
        return '[%s] %s:%s %s' % (self.severity.upper(), self.code, where,
                                  self.detail)


class Sample(object):
    __slots__ = ('label', 'kind', 'us', 'extra', 'line_no')

    def __init__(self, label, kind, us, extra, line_no):
        self.label = label
        self.kind = kind
        self.us = us
        self.extra = extra
        self.line_no = line_no


class Group(object):
    """一个观测块：样本缓冲 + 收口其的摘要（可能缺失）+ 逐键对照结果。

    `counts` 为样本重算值，`declared` 为摘要声明值，`exact_keys` 为二者
    严格相等的键集合（是分位数/完整性核对的前置条件）。`findings` 保存本节
    点**本篇一次**的结论（含解析期致命项与严格模式结论），`aggregate()` 只
    复用该结论、不得重跑宽松模式。
    """

    __slots__ = ('samples', 'summary', 'summary_line', 'first_line',
                 'counts', 'declared', 'exact_keys', 'field_absent',
                 'findings', 'checked', 'strict', 'source', 'invalid_summary',
                 'invalid_fields', 'parse_findings')

    def __init__(self, samples, summary, summary_line=None, source=None,
                 invalid_summary=False, parse_findings=None):
        self.samples = samples
        self.summary = summary
        self.summary_line = summary_line
        self.first_line = samples[0].line_no if samples else summary_line
        self.counts = {}
        self.declared = {}
        self.exact_keys = set()
        self.field_absent = []
        self.findings = []
        self.checked = False
        self.strict = False
        self.source = source
        self.invalid_summary = invalid_summary
        self.invalid_fields = set()
        # 解析阶段的检出（畸形样本/未知 kind）：必须归属到所在块，否则该块的
        # 解析缺陷会在合并阶段被"洗白"成合格轮。
        self.parse_findings = list(parse_findings or ())

    @property
    def label(self):
        if self.summary is not None:
            return self.summary.get('label')
        return self.samples[0].label if self.samples else None

    @property
    def fatal(self):
        return [f for f in self.findings if f.severity == 'fatal']

    def kinds(self, kind):
        return [s for s in self.samples if s.kind == kind]

    def codes(self):
        return sorted({f.code for f in self.findings})


def _int(value):
    return int(value) if _INT_RE.match(str(value)) else None


def _dig(summary, *path):
    """按键路径取值；任一层缺失或非 dict 返回 None。"""
    node = summary
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _has(summary, *path):
    """区分"字段缺失"与"字段存在但为 null"（分位数允许为 null）。"""
    node = summary
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return False
        node = node[key]
    return True


def _is_int(value):
    """布尔值不是整数：`True == 1` 不得蒙混通过计数与时间戳核对。"""
    return isinstance(value, int) and not isinstance(value, bool)


def _kind_ok(value, kind):
    if kind == 'bool':
        return isinstance(value, bool)
    if kind == 'int':
        return _is_int(value)
    if kind == 'int0':
        return _is_int(value) and value >= 0
    if kind == 'int0n':
        return value is None or (_is_int(value) and value >= 0)
    if kind == 'str':
        return isinstance(value, str)
    if kind == 'strn':
        return value is None or isinstance(value, str)
    if kind == 'obj':
        return isinstance(value, dict)
    if kind == 'list':
        return isinstance(value, list)
    raise AssertionError('未知类型约束: %s' % kind)


_IDENTITY_DOMAIN_MAP = dict(GROUP_IDENTITY_DOMAINS)


def _identity_domain_problem(key, value):
    """判定身份字段的取值域；合法返回 None，否则返回问题描述。

    `_kind_ok` 只回答"字段填了正确类型"，本函数回答"它是否构成有效声明"：
    空串、纯空白、占位符与无意义的零值都只说明未采集（见
    `GROUP_IDENTITY_DOMAINS`）。调用前提是类型已通过 `_kind_ok`。
    """
    domain = _IDENTITY_DOMAIN_MAP[key]
    if value is None:
        return 'null 值不构成声明'
    if domain == 'text':
        if not value.strip():
            return '空串或纯空白不构成声明'
        if value.strip().lower() in IDENTITY_PLACEHOLDERS:
            return '占位符 %r 只说明未采集，不是声明' % value
        return None
    if domain == 'positive':
        return None if value > 0 else '0（或负值）不是可工作的实验参数取值'
    if domain == 'nonneg':
        return None if value >= 0 else '负值不是合法取值'
    if domain == 'hex64':
        return None if _HEX64_RE.match(value) \
            else '包 SHA-256 必须是 64 位十六进制（实际 %d 字符）' % len(value)
    raise AssertionError('未知身份域: %s' % domain)


def parse_sample(line, line_no, findings):
    """解析一条 OTA_LINK_SAMPLE；畸形行进 findings 并返回 None。"""
    tokens = line.split()
    if len(tokens) < 4:
        findings.append(Finding('MALFORMED_SAMPLE', 'fatal',
                                '样本行字段不足: %r' % line, line_no))
        return None
    extra = {}
    for token in tokens[1:]:
        match = _TOKEN_RE.match(token)
        if not match:
            findings.append(Finding('MALFORMED_SAMPLE', 'fatal',
                                    '样本行字段非 key=value: %r' % token, line_no))
            return None
        key, value = match.group(1), match.group(2)
        if key in extra:
            findings.append(Finding('MALFORMED_SAMPLE', 'fatal',
                                    '样本行字段重复: %r' % key, line_no))
            return None
        extra[key] = value
    for key in ('label', 'kind', 'us'):
        if key not in extra or extra[key] == '':
            findings.append(Finding('MALFORMED_SAMPLE', 'fatal',
                                    '样本行缺少必需字段 %s: %r' % (key, line), line_no))
            return None
    us = _int(extra.pop('us'))
    if us is None:
        findings.append(Finding('MALFORMED_SAMPLE', 'fatal',
                                '样本行 us 非整数: %r' % extra.get('us'), line_no))
        return None
    label, kind = extra.pop('label'), extra.pop('kind')
    if kind not in KNOWN_KINDS:
        findings.append(Finding('UNKNOWN_KIND', 'fatal',
                                '未知样本 kind=%r（解析器无法归类，拒绝继续）' % kind,
                                line_no))
        return None
    return Sample(label, kind, us, extra, line_no)


def parse_log(text, strict_tail=False, source=None):
    """按顺序解析整份日志，返回 (groups, findings)。

    [strict_tail] 为真时，文件末尾未收口的观测块按致命处理（设备采集轮次
    要求每块必有摘要）；默认只告警，因为传输级用例与中途截断的合法日志
    同样会留下未收口样本。

    摘要 JSON 非法或顶层非对象时：报 `BAD_JSON`（fatal），该块按"没有合法
    收口"记录（严格模式下再报 `SUMMARY_MISSING`），其样本仍归属本块，
    **不**被静默清空后与后续块混为一谈。
    """
    groups, findings, buffer = [], [], []
    parse_findings = []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith(SAMPLE_PREFIX):
            where = len(findings)
            sample = parse_sample(line, line_no, findings)
            if sample is not None:
                buffer.append(sample)
            else:
                # 解析期致命项同时归属到当前块：该块不得再被视为合格轮。
                parse_findings.extend(findings[where:])
        elif line.startswith(STATS_PREFIX):
            payload = line[len(STATS_PREFIX):].strip()
            summary, invalid = None, False
            try:
                summary = json.loads(payload)
            except ValueError as exc:
                findings.append(Finding('BAD_JSON', 'fatal',
                                        '摘要 JSON 不可解析: %s' % exc, line_no))
                invalid = True
            if not invalid and not isinstance(summary, dict):
                findings.append(Finding('BAD_JSON', 'fatal',
                                        '摘要 JSON 顶层非对象（null/数组/标量都不能作为'
                                        '合法收口，也不能清除已有样本的错误归属）',
                                        line_no))
                invalid = True
            if invalid:
                summary = None
                findings.append(Finding(
                    'SUMMARY_MISSING', 'fatal' if strict_tail else 'warn',
                    '该块的摘要行非法（行 %d），块内 %d 条样本没有可核对的声明'
                    % (line_no, len(buffer)), buffer[0].line_no if buffer else line_no))
            groups.append(Group(buffer, summary, line_no, source=source,
                               invalid_summary=invalid,
                               parse_findings=parse_findings))
            buffer, parse_findings = [], []
    if buffer:
        groups.append(Group(buffer, None, source=source,
                            parse_findings=parse_findings))
        parse_findings = []
        findings.append(Finding(
            'SUMMARY_MISSING', 'fatal' if strict_tail else 'warn',
            '文件结束时仍有 %d 条样本未被摘要收口（无声明可核对，该块不参与'
            '合并；若本轮要求每块必收口，用 --strict-tail 判定为致命）'
            % len(buffer), buffer[0].line_no))
    if parse_findings:
        findings.extend(parse_findings)
    if not groups:
        # 零观测不是"宽松/严格"的口径差异，而是被测量对象本身缺失：默认模式
        # 可以容忍未收口、多实例等形状问题，但没有任何模式可以把"没测到东西"
        # 报成通过，否则仅看退出码的调用方会把空捕获当成合格测量。
        findings.append(Finding(
            'NO_OBSERVATIONS', 'fatal',
            '输入中没有可判定的观测（既无样本也无摘要）：这不是"通过"，'
            '而是"没有有效观测"', None))
    return groups, findings


def _nearest_rank(values, q):
    """nearest-rank 分位数：升序第 ceil(q*N) 个，不插值（与发射端同口径）。"""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(math.ceil(q * len(ordered))))
    return ordered[rank - 1]


def _sum_bytes(group, kind, findings):
    """按样本累加已写字节数；缺失、非整数与负值一律致命。

    字节计数是 OTA-XC-BLE-PERFORMANCE 要求的"确实写出的字节数"观测，
    负值不可能是任何一次写入的结果，且会抵消同块其它样本的计数，使
    `gattWriteBytes`/`platformWriteBytes` 的相等判定失去意义。GATT 与
    platform 两个调用方共用本函数，域校验不得只覆盖其中一侧。
    """
    total, ok = 0, True
    for sample in group.kinds(kind):
        value = _int(sample.extra.get('bytes'))
        if value is None:
            findings.append(Finding('MALFORMED_SAMPLE', 'fatal',
                                    '%s 样本缺 bytes 或非整数' % kind, sample.line_no))
            ok = False
            break
        if value < 0:
            findings.append(Finding(
                'BYTE_COUNT_INVALID', 'fatal',
                '%s 样本的 bytes=%d 为负：字节计数是已写出的字节数，负值既不'
                '可能是任何写入的结果，也会抵消同块其它样本的计数'
                % (kind, value), sample.line_no))
            ok = False
            break
        total += value
    return total if ok else None


def _observed_counts(group, findings):
    """按样本重算各计数键（与摘要声明逐键对照的左侧）。

    durable 样本**逐条**过偏移域（缺 off、非整数、负值都致命）：每条既是
    `durableEvents` 的席位，也构成 `finalOff` 的推进足迹，只看末条会放过
    中间样本的非法偏移，让畸形观测进入计数与门槛池。末值 `finalOff` 只在
    整串样本都合法时给出，避免用不可信的末值做相等/拖尾判定。
    """
    durable = group.kinds('durable')
    final_off = None
    durable_usable = bool(durable)
    for sample in durable:
        off = _sample_off(sample, findings)
        if off is None:
            durable_usable = False
        else:
            final_off = off
    if not durable_usable:
        final_off = None
    gatt_bytes = _sum_bytes(group, 'gatt_write', findings)
    platform_bytes = _sum_bytes(group, 'platform_write', findings)
    return {
        'segmentsUnique': len(group.kinds('segment_first_send')),
        'segmentSendTotal': len(group.kinds('segment_first_send'))
                            + len(group.kinds('segment_retransmit')),
        'retransmitFrames': len(group.kinds('segment_retransmit')),
        'ackLatencyCount': len(group.kinds('ack_latency')),
        'durableEvents': len(durable),
        'durableFinalOff': final_off,
        'ackEarlyInvalid': len(group.kinds('ack_early_invalid')),
        'ackEarlyUnsent': len(group.kinds('ack_early'))
                          - len(group.kinds('ack_early_invalid')),
        'getInfoCalls': len(group.kinds('get_info')),
        'getInfoFailures': len([s for s in group.kinds('get_info')
                                if s.extra.get('ok') == '0']),
        'gattWriteCalls': len(group.kinds('gatt_write')),
        'gattWriteBytes': gatt_bytes,
        'gattWriteErrors': len([s for s in group.kinds('gatt_write')
                                if s.extra.get('error') == '1']),
        'discoverCalls': len(group.kinds('discover')),
        'discoverErrors': len([s for s in group.kinds('discover')
                               if s.extra.get('error') == '1']),
        'platformWriteCalls': len(group.kinds('platform_write')),
        'platformWriteBytes': platform_bytes,
        'platformWriteErrors': len([s for s in group.kinds('platform_write')
                                    if s.extra.get('error') == '1']),
    }


def _check_types(group, findings):
    """声明字段的类型/范围核对（非法类型给出结构化致命项，不抛异常）。"""
    summary, line_no = group.summary, group.summary_line
    for path, kind in DECLARED_FIELDS:
        if not _has(summary, *path):
            continue
        value = _dig(summary, *path)
        if not _kind_ok(value, kind):
            group.invalid_fields.add('.'.join(path))
            findings.append(Finding(
                'FIELD_TYPE_INVALID', 'fatal',
                '%s 类型或取值非法：要求 %s，实际 %r（%s）'
                % ('.'.join(path), kind, value, type(value).__name__), line_no))


def _check_structure(group, findings):
    summary = group.summary
    line_no = group.summary_line
    schema = _dig(summary, 'schema')
    if not _has(summary, 'schema'):
        findings.append(Finding('SCHEMA_UNKNOWN', 'fatal',
                                '摘要缺少 schema，无法确认解析口径', line_no))
    elif _is_int(schema):
        if schema not in SCHEMA_SUPPORTED:
            findings.append(Finding('SCHEMA_UNKNOWN', 'fatal',
                                    '摘要 schema=%r 不在受支持集合 %s'
                                    % (schema, sorted(SCHEMA_SUPPORTED)), line_no))
    # 类型非法已由 _check_types 报出，避免同一缺陷重复报码。
    if not _has(summary, 'clock'):
        findings.append(Finding('CLOCK_DOMAIN', 'fatal',
                                '摘要缺少 clock，无法确认时间戳域（跨时钟域不可合并）',
                                line_no))
    elif isinstance(_dig(summary, 'clock'), str) \
            and _dig(summary, 'clock') != CLOCK_DOMAIN:
        findings.append(Finding('CLOCK_DOMAIN', 'fatal',
                                '摘要 clock=%r 非冻结时间戳域 %r（跨时钟域不可合并）'
                                % (_dig(summary, 'clock'), CLOCK_DOMAIN), line_no))
    for path in REQUIRED_SUMMARY_OBJECTS:
        if not isinstance(_dig(summary, *path), dict):
            findings.append(Finding('SCHEMA_MISSING', 'fatal',
                                    '摘要缺少必需对象 %s' % '.'.join(path), line_no))


def _check_labels(group, findings):
    labels = sorted({s.label for s in group.samples})
    declared = group.summary.get('label')
    if len(labels) > 1:
        findings.append(Finding('MIXED_LABEL', 'fatal',
                                '同一观测块混用多个 label：%s' % labels, group.first_line))
    elif labels and labels[0] != declared:
        findings.append(Finding('MIXED_LABEL', 'fatal',
                                '样本 label=%r 与摘要 label=%r 不一致'
                                % (labels[0], declared), group.first_line))


def _clock_segments(samples):
    """按实例时钟回退把缓冲区切成多个实例段。

    只有**事件时间**样本参与单调性判定；`ack_early_invalid` 打印的是被回放的
    早到确认到达时刻，按发射端语义允许早于前一条，因此不参与、也不触发分段。
    """
    segments = []
    high = None
    for sample in samples:
        if sample.kind in EVENT_TIME_KINDS:
            if high is not None and sample.us < high:
                segments.append([])
                high = sample.us
            elif high is None or sample.us > high:
                high = sample.us
        if not segments:
            segments.append([])
        segments[-1].append(sample)
    return segments


def _check_clock(group, findings, strict_blocks=False):
    """时间戳单调性：段内非递减；回退即新实例（默认 warn，严格块模型 fatal）。"""
    for sample in group.samples:
        if sample.us < 0:
            findings.append(Finding('CLOCK_NEGATIVE', 'fatal',
                                    '样本 us 为负（kind=%s）' % sample.kind,
                                    sample.line_no))
    segments = _clock_segments(group.samples)
    if len(segments) > 1:
        detail = ('同一观测块内出现 %d 个实例段（实例时钟回退），前序实例未收口；'
                  '该块不构成单一实例的完整观测' % len(segments))
        if strict_blocks:
            findings.append(Finding('CLOCK_NONMONOTONIC', 'fatal', detail,
                                    segments[1][0].line_no))
        else:
            findings.append(Finding('MULTI_INSTANCE', 'warn', detail,
                                    segments[1][0].line_no))
    _check_early_links(group, segments, findings)


def _check_early_links(group, segments, findings):
    """`ack_early_invalid` 必须关联到同段内未被消费的同 off、同 us 的早到确认。

    这是"事件时间 vs 输出顺序"的判别点：合法回放不报时钟回退，但**无关联的
    旧时间重放**（凭空出现的更早时间、跨实例挪用、重复消费）必须报
    `EARLY_ACK_UNLINKED`（fatal）。
    """
    for segment in segments:
        pending = collections.defaultdict(collections.Counter)
        for sample in segment:
            if sample.kind == 'ack_early':
                pending[sample.extra.get('off')][sample.us] += 1
            elif sample.kind == 'ack_early_invalid':
                off = sample.extra.get('off')
                if off is None:
                    continue  # 缺 off 已由 SEGMENT_OFFSET_MISSING 报出
                bucket = pending.get(off)
                if bucket and bucket.get(sample.us):
                    bucket[sample.us] -= 1
                    if not bucket[sample.us]:
                        del bucket[sample.us]
                else:
                    findings.append(Finding(
                        'EARLY_ACK_UNLINKED', 'fatal',
                        'ack_early_invalid(us=%r off=%r) 无法关联同段内未被消费的'
                        'ack_early 早到确认：要么时间/偏移对不上，要么该旧时间属'
                        '其它实例（多实例污染），不得当作合法时钟回放'
                        % (sample.us, off), sample.line_no))


def _sample_off(sample, findings, require_len=False):
    """读取样本的 off（发送类还要 len）；缺失或非法按致命畸形处理。

    取值域：偏移是"块内字节位置"，负数不可能指向任何段；`len` 是数据段
    长度，0 长度的段发送不存在。二者与缺失同样属畸形样本，必须致命化——
    否则负偏移/零长度会绕过 `_check_quantiles` 的整套一致性核对。
    """
    off = _int(sample.extra.get('off'))
    if off is None:
        findings.append(Finding(
            'SEGMENT_OFFSET_MISSING', 'fatal',
            '%s 样本缺少唯一字节偏移 off（无偏移的段/确认无法做集合完整性核对）'
            % sample.kind, sample.line_no))
        return None
    if off < 0:
        findings.append(Finding(
            'SEGMENT_OFFSET_INVALID', 'fatal',
            '%s 样本的 off=%d 为负：偏移是块内字节位置，负值不指向任何数据段'
            '（该样本无法与任何段做集合核对）' % (sample.kind, off),
            sample.line_no))
        return None
    if require_len:
        length = _int(sample.extra.get('len'))
        if length is None:
            findings.append(Finding(
                'SEGMENT_OFFSET_MISSING', 'fatal',
                '%s 样本缺少 len（无法确认该段长度）' % sample.kind,
                sample.line_no))
            return None
        if length <= 0:
            findings.append(Finding(
                'SEGMENT_LENGTH_INVALID', 'fatal',
                '%s 样本的 len=%d 不是有效数据段长度：零长度段发送不存在，'
                '且该段不会被重传/确认样本引用' % (sample.kind, length),
                sample.line_no))
            return None
    return off


def _check_offset_sets(group, findings, strict_blocks=False):
    """按实例段核对首发/重传/确认的偏移集合（不按行数）。

    重复类核对按**实例段**（同一实例内首发偏移唯一）；引用类核对按**整块**
    累积的已发送集合（跨段引用不算孤儿，避免因分段粒度误报）。
    """
    severity = 'fatal' if strict_blocks else 'warn'
    segments = _clock_segments(group.samples)
    sent = {}
    send_missing = False
    for segment in segments:
        seen_first, seen_ack = {}, {}
        for sample in segment:
            if sample.kind in ('segment_first_send', 'segment_retransmit'):
                # 首发与重传都由发射端携带 len（ota_link_stats.dart:257/271）；
                # 只对首发要求 len 会让重传的 len=0/-1 以零发现通过，重传帧
                # 同样进入 retransmitFrames/segmentSendTotal 计数池。
                off = _sample_off(sample, findings, require_len=True)
                if off is None:
                    send_missing = True
                    continue
                if sample.kind == 'segment_first_send':
                    if off in seen_first:
                        findings.append(Finding(
                            'DUPLICATE_SEGMENT_OFFSET', severity,
                            '同一实例段内首发偏移 off=%d 重复（发射端 _sentOffsets '
                            '保证唯一）；重复首发意味着段内混有多个实例' % off,
                            sample.line_no))
                    seen_first[off] = sample.line_no
                    sent[off] = sample.line_no
                elif not send_missing and off not in sent:
                    findings.append(Finding(
                        'ORPHAN_RETRANSMIT', severity,
                        '重传样本 off=%d 没有对应的首发段（无重传对象）' % off,
                        sample.line_no))
            elif sample.kind == 'ack_latency':
                off = _sample_off(sample, findings)
                if off is None:
                    continue
                if off in seen_ack:
                    findings.append(Finding(
                        'DUPLICATE_ACK_OFFSET', severity,
                        '同一实例段内确认偏移 off=%d 出现多条 ack_latency；'
                        '重复确认会顶替另一个缺失段的样本' % off, sample.line_no))
                seen_ack[off] = sample.line_no
                if not send_missing and off not in sent:
                    findings.append(Finding(
                        'ACK_WITHOUT_SEGMENT', severity,
                        'ack_latency off=%d 在本块内没有对应的发送段'
                        '（确认样本无法归属到任何一段）' % off, sample.line_no))
            elif sample.kind in ('ack_early', 'ack_early_invalid'):
                _sample_off(sample, findings)


def _check_required_present(group, findings):
    """必需字段缺失逐项申报（不按缺省 0 静默通过）。"""
    summary, line_no = group.summary, group.summary_line
    for path in REQUIRED_PRESENT_FIELDS:
        if _has(summary, *path):
            continue
        name = '.'.join(path)
        group.field_absent.append(name)
        findings.append(Finding('FIELD_ABSENT', 'warn',
                                '摘要缺少字段 %s（整改前发射端版本合法缺失；'
                                '同版本日志出现即缺陷，且不得据此声称契约完整）'
                                % name, line_no))


def _check_counters(group, findings):
    """逐键对照：少=致命，多=拖尾告警（拖尾样本使样本population归属不明）。"""
    summary, line_no = group.summary, group.summary_line
    observed = group.counts
    for path, key in COUNTER_KEYS:
        name = '.'.join(path)
        if name in group.invalid_fields or not _has(summary, *path):
            continue
        declared = _dig(summary, *path)
        value = observed.get(key)
        if value is None:
            continue  # bytes 已报畸形，避免级联噪声
        group.declared[key] = declared
        if value == declared:
            group.exact_keys.add(key)
        elif value < declared:
            findings.append(Finding('COUNT_MISMATCH', 'fatal',
                                    '%s 摘要声明多于日志观测：摘要=%r 样本重算=%r'
                                    % (name, declared, value), line_no))
        else:
            findings.append(Finding('STRAGGLER', 'warn',
                                    '%s 日志观测多于摘要声明：摘要=%r 样本重算=%r'
                                    '（该块含不属于本块声明的观测，样本归属不明，'
                                    '不得进入任何数值池）'
                                    % (name, declared, value), line_no))

    if 'transfer.durable.finalOff' in group.invalid_fields \
            or not _has(summary, 'transfer', 'durable', 'finalOff'):
        return
    declared_final = _dig(summary, 'transfer', 'durable', 'finalOff')
    observed_final = observed.get('durableFinalOff')
    group.declared['durableFinalOff'] = declared_final
    offsets = [_int(s.extra.get('off')) for s in group.kinds('durable')]
    if observed_final is None:
        # 无可用末值有两种成因：真的没有 durable 样本（无样本时摘要声明
        # finalOff=null 是合法形状，声明了具体偏移才是丢行）；或样本存在但
        # 至少一条 off 非法——后者已由 `_observed_counts` 按行报致命项，
        # 此处不得再谎称"日志无 durable 样本"。
        if declared_final is None:
            group.exact_keys.add('durableFinalOff')
        elif not group.kinds('durable'):
            findings.append(Finding('COUNT_MISMATCH', 'fatal',
                                    '摘要声明 durable.finalOff=%r，但日志无 durable 样本'
                                    % (declared_final,), line_no))
    elif observed_final == declared_final:
        group.exact_keys.add('durableFinalOff')
    elif declared_final in offsets:
        findings.append(Finding('STRAGGLER', 'warn',
                                'durable.finalOff=%r 非末条 durable 样本（摘要后仍有推进）'
                                % (declared_final,), line_no))
    else:
        findings.append(Finding('COUNT_MISMATCH', 'fatal',
                                'durable.finalOff=%r 不在日志的 durable 序列中'
                                % (declared_final,), line_no))


def _quantiles(values):
    return {
        'minUs': min(values) if values else None,
        'p50Us': _nearest_rank(values, 0.50),
        'p95Us': _nearest_rank(values, 0.95),
        'maxUs': max(values) if values else None,
    }


def _check_quantiles(group, findings):
    """分位数/派生量核对；样本集合可重构（计数精确）时必须逐字段相等。"""
    summary, line_no = group.summary, group.summary_line
    if 'ackLatencyCount' in group.exact_keys:
        expected = _quantiles([s.us for s in group.kinds('ack_latency')])
        expected['p99Us'] = _nearest_rank(
            [s.us for s in group.kinds('ack_latency')], 0.99)
        for name in ('minUs', 'p50Us', 'p95Us', 'p99Us', 'maxUs'):
            path = ('transfer', 'ackLatency', name)
            if not _has(summary, *path) or '.'.join(path) in group.invalid_fields:
                continue
            declared = _dig(summary, *path)
            if declared != expected[name]:
                findings.append(Finding('QUANTILE_MISMATCH', 'fatal',
                                        'transfer.ackLatency.%s 不一致：样本重算（nearest-rank）'
                                        '=%r 摘要声明=%r' % (name, expected[name], declared),
                                        line_no))

    for prefix, kind, count_key in PHASE_METRICS:
        if count_key not in group.exact_keys:
            continue  # 样本集合不可重构时不做逐项重算，避免用错样本集合
        expected = _quantiles([s.us for s in group.kinds(kind)])
        for name, value in expected.items():
            path = prefix + (name,)
            if not _has(summary, *path) or '.'.join(path) in group.invalid_fields:
                continue
            declared = _dig(summary, *path)
            if declared != value:
                findings.append(Finding('QUANTILE_MISMATCH', 'fatal',
                                        '%s.%s 不一致：样本重算（nearest-rank）=%r 摘要声明=%r'
                                        % ('.'.join(prefix), name, value, declared),
                                        line_no))

    if 'getInfoCalls' in group.exact_keys \
            and _has(summary, 'getInfo', 'totalUs') \
            and 'getInfo.totalUs' not in group.invalid_fields:
        expected_total = sum(s.us for s in group.kinds('get_info'))
        declared_total = _dig(summary, 'getInfo', 'totalUs')
        if declared_total != expected_total:
            findings.append(Finding('PHASE_TOTAL_MISMATCH', 'fatal',
                                    'getInfo.totalUs 不一致：样本重算=%r 摘要声明=%r'
                                    % (expected_total, declared_total), line_no))

    _check_transfer_timing(group, findings)


def _check_transfer_timing(group, findings):
    """核对传输时序契约：三键齐备、成功传输区间为正且自洽。

    时序核对**独立于**可选呈现字段：不能因为删掉 `transfer.elapsedUs`（或它
    被判为类型非法）就让成功传输没有可判定的时长。三种时序键自 schema 1 起
    由 `toJson` 恒定输出，缺失属测量契约缺口而非"整改前版本合法缺字段"，
    因此报 `TIMING_INCOMPLETE`（fatal，同时由 REQUIRED_PRESENT_FIELDS 记
    FIELD_ABSENT 告警）。

    非成功终态（probe / 失败 / 未启动，outcome 为 null 或非 ok）允许三项为
    null，也不要求正时长；但只要三项齐备且为整数，声明的时长仍必须自洽。
    """
    summary, line_no = group.summary, group.summary_line
    outcome = _dig(summary, 'transfer', 'outcome')
    absent = ['.'.join(path) for path in TIMING_FIELDS
              if not _has(summary, *path)]
    if absent:
        findings.append(Finding(
            'TIMING_INCOMPLETE', 'fatal',
            '时序契约字段缺失：%s。transfer.startUs/endAckUs/elapsedUs 自 '
            'schema 1 起恒由 toJson 输出，缺失即无传输时长可判定，'
            '删除呈现字段不得绕过时长核对' % '、'.join(absent), line_no))
        return
    values = {
        'transfer.startUs': _dig(summary, 'transfer', 'startUs'),
        'transfer.endAckUs': _dig(summary, 'transfer', 'endAckUs'),
        'transfer.elapsedUs': _dig(summary, 'transfer', 'elapsedUs'),
    }
    if [name for name, value in sorted(values.items())
            if value is not None and not _is_int(value)]:
        return  # 类型非法由 DECLARED_FIELDS 的 FIELD_TYPE_INVALID 负责
    nulls = sorted(name for name, value in values.items() if value is None)
    start, end = values['transfer.startUs'], values['transfer.endAckUs']
    elapsed = values['transfer.elapsedUs']
    if outcome == 'ok':
        if nulls:
            findings.append(Finding(
                'TIMING_INCOMPLETE', 'fatal',
                '成功传输（outcome=ok）的时序字段为 null：%s（无时长即无法判定'
                '该轮是否可用于门槛比较）' % '、'.join(nulls), line_no))
            return
        if end - start != elapsed:
            findings.append(Finding(
                'INTERNAL_INCONSISTENT', 'fatal',
                'transfer.elapsedUs 不一致：endAckUs-startUs=%r 摘要=%r'
                % (end - start, elapsed), line_no))
        elif elapsed <= 0:
            findings.append(Finding(
                'ELAPSED_NOT_POSITIVE', 'fatal',
                '成功传输（outcome=ok）的 elapsedUs=%r 必须为正'
                '（OTA-XC-BLE-TUNING：elapsedSeconds <= 0 无效）；'
                '单次操作的零微秒耗时不受此限制' % (elapsed,), line_no))
        return
    if not nulls and end - start != elapsed:
        findings.append(Finding(
            'INTERNAL_INCONSISTENT', 'fatal',
            'transfer.elapsedUs 不一致：endAckUs-startUs=%r 摘要=%r'
            % (end - start, elapsed), line_no))


def _check_integrity(group, findings):
    keys = ('segmentsUnique', 'ackLatencyCount', 'ackEarlyInvalid',
            'ackEarlyUnsent')
    if not set(keys) <= group.exact_keys:
        return
    segments = group.declared['segmentsUnique']
    sampled = group.declared['ackLatencyCount']
    early_invalid = group.declared['ackEarlyInvalid']
    missing = segments - sampled
    parts = []
    if missing > 0:
        parts.append('missing=%d' % missing)
    if early_invalid > 0:
        parts.append('early=%d' % early_invalid)
    expected = 'complete' if not parts else 'partial:%s' % ','.join(parts)
    if 'transfer.ackSamples' in group.invalid_fields:
        return
    declared = _dig(group.summary, 'transfer', 'ackSamples')
    if declared != expected:
        findings.append(Finding('INTEGRITY_MISMATCH', 'fatal',
                                'transfer.ackSamples 不一致：按样本重算=%r 摘要声明=%r'
                                % (expected, declared), group.summary_line))


def _check_derived(group, findings):
    summary, line_no = group.summary, group.summary_line
    unique = _dig(summary, 'transfer', 'segmentsUnique')
    total = _dig(summary, 'transfer', 'segmentSendTotal')
    retransmit = _dig(summary, 'transfer', 'retransmitFrames')
    names = ('transfer.segmentsUnique', 'transfer.segmentSendTotal',
             'transfer.retransmitFrames')
    if all(_is_int(v) for v in (unique, total, retransmit)) \
            and not (set(names) & group.invalid_fields):
        if retransmit != total - unique:
            findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                    'retransmitFrames != segmentSendTotal - segmentsUnique'
                                    '（%r != %r - %r）' % (retransmit, total, unique),
                                    line_no))

    phases = _dig(summary, 'phases')
    if isinstance(phases, dict):
        for name, bounds in phases.items():
            if not isinstance(bounds, list) or not bounds:
                findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                        'phases.%s 结构非法：%r' % (name, bounds), line_no))
                continue
            if not all(_is_int(v) for v in bounds):
                findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                        'phases.%s 含非整数时间戳：%r' % (name, bounds),
                                        line_no))
                continue
            if any(value < 0 for value in bounds):
                findings.append(Finding('PHASE_NEGATIVE', 'fatal',
                                        'phases.%s 含负时间戳：%r（时钟域 '
                                        'stopwatch-mono-us 不可能出现负值，'
                                        '负值意味着时钟域用错或字段被改写）'
                                        % (name, bounds), line_no))
                continue
            if len(bounds) > 1 and bounds[1] < bounds[0]:
                findings.append(Finding('PHASE_REVERSED', 'fatal',
                                        'phases.%s 结束早于开始：%r' % (name, bounds),
                                        line_no))
        bind = phases.get('bind')
        # `phases.bind` 的结构/类型缺陷已在上面的循环里逐项报过；这里只在
        # 边界能安全参与比较时做与 `bind.phaseUs` 的交叉核对。非列表或含非
        # 整数的边界绝不能参与相减：`None - int` 会抛未预期异常，使整轮
        # （连同其他块与其他输入）退化成一条 `INTERNAL_ERROR`，丢掉全部
        # 具体结论。
        if isinstance(bind, list) and all(_is_int(value) for value in bind):
            comparable = True
            expected = bind[1] - bind[0] if len(bind) == 2 else None
        elif bind is None:
            comparable, expected = True, None
        else:
            comparable, expected = False, None
        if comparable and 'bind.phaseUs' not in group.invalid_fields \
                and _has(summary, 'bind', 'phaseUs'):
            declared = _dig(summary, 'bind', 'phaseUs')
            if declared != expected:
                findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                        'bind.phaseUs 不一致：phases.bind=%r 摘要=%r'
                                        % (expected, declared), line_no))


def _check_attempts(group, findings):
    attempts = _dig(group.summary, 'attempts')
    if not isinstance(attempts, list):
        return
    numbers = []
    for entry in attempts:
        value = entry.get('n') if isinstance(entry, dict) else None
        if not _is_int(value) or value < 1:
            findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                    'attempts[].n 非正整数：%r' % (value,),
                                    group.summary_line))
            return
        numbers.append(value)
    if numbers != sorted(set(numbers)):
        findings.append(Finding('MIXED_ATTEMPT', 'fatal',
                                'attempts[].n 未严格递增（轮次归属会被读错）：%s' % numbers,
                                group.summary_line))


def check_group(group, findings, strict_blocks=False):
    """对单个观测块做一致性检出（缺摘要的块只报 SUMMARY_MISSING）。"""
    if group.summary is None:
        return
    _check_types(group, findings)
    _check_structure(group, findings)
    group.counts = _observed_counts(group, findings)
    _check_labels(group, findings)
    _check_clock(group, findings, strict_blocks=strict_blocks)
    _check_offset_sets(group, findings, strict_blocks=strict_blocks)
    _check_required_present(group, findings)
    _check_counters(group, findings)
    _check_quantiles(group, findings)
    _check_integrity(group, findings)
    _check_derived(group, findings)
    _check_attempts(group, findings)


def check(groups, findings, strict_blocks=False):
    for group in groups:
        group.findings = list(group.parse_findings)
        group.strict = strict_blocks
        check_group(group, group.findings, strict_blocks=strict_blocks)
        group.checked = True
        findings.extend(group.findings)
    return findings


def check_group_only(group, strict_blocks=False):
    findings = list(group.parse_findings)
    check_group(group, findings, strict_blocks=strict_blocks)
    return findings


def analyse(text, device_capture=False, source=None):
    """解析 + 检出，返回 (groups, findings)。

    [device_capture] 启用严格块模型（每块恰一个实例且必须收口），供设备
    采集轮次使用；默认放宽为"块内可含多个未收口实例"。
    """
    groups, findings = parse_log(text, strict_tail=device_capture, source=source)
    check(groups, findings, strict_blocks=device_capture)
    return groups, findings


def analyse_logs(inputs, device_capture=False):
    """[inputs] 为 [(name, text), ...]；返回 (groups, findings)（顺序保留）。"""
    all_groups, all_findings = [], []
    for name, text in inputs:
        groups, findings = analyse(text, device_capture=device_capture,
                                   source=name)
        all_groups.extend(groups)
        all_findings.extend(findings)
    return all_groups, all_findings


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _identity_signature(summary):
    return tuple(json.dumps(_dig(summary, *path), sort_keys=True)
                 for path in SIGNATURE_FIELDS)


def _signature_label(summary):
    signature = collections.OrderedDict()
    for path in SIGNATURE_FIELDS:
        signature['.'.join(path)] = _dig(summary, *path)
    return signature


def load_group_identity(path, inputs, findings):
    """读取并校验 `--group` 侧车：实验身份声明 + 原始日志 SHA-256 绑定。

    [inputs] 为 [(name, path), ...]。返回已校验的身份 dict；任一项非法时返回
    None（调用方据此把合并标记为非门槛可用）。
    """
    try:
        with open(path, 'r', encoding='utf-8') as handle:
            payload = json.load(handle)
    except (OSError, ValueError) as exc:
        findings.append(Finding('GROUP_IDENTITY_INVALID', 'fatal',
                                '侧车身份文件不可读取或不是合法 JSON：%s' % exc, None))
        return None
    if not isinstance(payload, dict):
        findings.append(Finding('GROUP_IDENTITY_INVALID', 'fatal',
                                '侧车身份文件顶层必须是对象', None))
        return None
    identity = payload.get('identity')
    if not isinstance(identity, dict):
        findings.append(Finding('GROUP_IDENTITY_INVALID', 'fatal',
                                '侧车缺少 identity 对象', None))
        return None
    complete = True
    for key, kind in GROUP_IDENTITY_FIELDS:
        if not _has(identity, key) or not _kind_ok(_dig(identity, key), kind):
            complete = False
            findings.append(Finding('GROUP_IDENTITY_INCOMPLETE', 'fatal',
                                    '侧车身份缺少字段或类型非法：%s（要求 %s）'
                                    % (key, kind), None))
            continue
        problem = _identity_domain_problem(key, _dig(identity, key))
        if problem is not None:
            complete = False
            findings.append(Finding('GROUP_IDENTITY_INVALID', 'fatal',
                                    '侧车身份字段 %s 的取值不构成有效声明：%r（%s）'
                                    % (key, _dig(identity, key), problem), None))
    declared_inputs = payload.get('inputs')
    if not isinstance(declared_inputs, list) or not declared_inputs:
        findings.append(Finding('INPUT_UNBOUND', 'fatal',
                                '侧车 missing inputs[]：未绑定任何原始日志，'
                                '合并统计不得用于门槛判定', None))
        return None
    bound = {}
    for entry in declared_inputs:
        if not isinstance(entry, dict) or not isinstance(entry.get('sha256'), str):
            findings.append(Finding('INPUT_UNBOUND', 'fatal',
                                    '侧车 inputs[] 条目必须是含 sha256 的对象：%r'
                                    % (entry,), None))
            return None
        bound[entry['sha256'].lower()] = entry.get('name') or entry.get('path')
    for name, file_path in inputs:
        digest = _sha256_file(file_path)
        if digest not in bound:
            findings.append(Finding('INPUT_UNBOUND', 'fatal',
                                    '日志 %s（sha256=%s）未列入侧车 inputs[]：'
                                    '未绑定的输入不得参与门槛合并'
                                    % (name, digest), None))
    for digest, name in sorted(bound.items(), key=lambda item: str(item[1])):
        if digest not in {_sha256_file(p) for _, p in inputs}:
            findings.append(Finding('INPUT_SHA_MISMATCH', 'fatal',
                                    '侧车声明的输入 %s（sha256=%s）不在本轮 --log 中，'
                                    '或字节已变化' % (name, digest), None))
    if not complete:
        return None
    identity = dict(identity)
    identity['groupId'] = payload.get('groupId')
    identity['declaredInputs'] = sorted(bound.values(), key=str)
    return identity


def _classify(group, excluded):
    """判定一个块的可用等级，并把不合格理由写入 [excluded]。

    返回 (attributable, clean)；两者皆假时该块的样本不进入任何数值池。
    """
    codes = set(group.codes())
    reasons = []
    if group.summary is None:
        return False, False
    for finding in group.findings:
        if finding.severity == 'fatal':
            reasons.append('FATAL:%s' % finding.code)
    if 'STRAGGLER' in codes:
        reasons.append('SAMPLE_POPULATION_NOT_ATTRIBUTABLE:STRAGGLER')
    if 'MULTI_INSTANCE' in codes or 'CLOCK_NONMONOTONIC' in codes:
        reasons.append('NOT_SINGLE_INSTANCE')
    for code in sorted(OFFSET_SET_CODES):
        if code in codes:
            reasons.append('OFFSET_SET_INCONSISTENT:%s' % code)
    outcome = _dig(group.summary, 'transfer', 'outcome')
    if outcome != 'ok':
        reasons.append('OUTCOME:%r' % (outcome,))
    ack_samples = _dig(group.summary, 'transfer', 'ackSamples')
    if ack_samples != 'complete':
        reasons.append('ACK_SAMPLES:%r' % (ack_samples,))
    if reasons:
        excluded.append({
            'source': group.source,
            'firstLine': group.first_line,
            'summaryLine': group.summary_line,
            'codes': group.codes(),
            'reasons': sorted(set(reasons)),
        })
        # 无 fatal 且 outcome=ok 的块仍是可诊断的洁净度不足轮次；含 fatal 的
        # 块连诊断样本都不采信（"不得把失败洗成成功"）。
        return False, False
    return True, True


def _pool(blocks):
    merged, retransmit, unique, absent, straggled = [], 0, 0, 0, 0
    for group in blocks:
        merged.extend(s.us for s in group.kinds('ack_latency'))
        retransmit += _dig(group.summary, 'transfer', 'retransmitFrames') or 0
        unique += _dig(group.summary, 'transfer', 'segmentsUnique') or 0
        codes = set(group.codes())
        if 'FIELD_ABSENT' in codes:
            absent += 1
        if 'STRAGGLER' in codes:
            straggled += 1
    return {
        'runs': len(blocks),
        'ackLatency': {
            'count': len(merged),
            'minUs': min(merged) if merged else None,
            'p50Us': _nearest_rank(merged, 0.50),
            'p95Us': _nearest_rank(merged, 0.95),
            'p99Us': _nearest_rank(merged, 0.99),
            'maxUs': max(merged) if merged else None,
        },
        'retransmitFrames': retransmit,
        'segmentsUnique': unique,
        'retransmitRate': (float(retransmit) / unique) if unique else None,
        'runsWithAbsentFields': absent,
        'runsWithStragglerSamples': straggled,
    }


def _qualification_reasons(merged, group_identity, conflicts, mismatches,
                           identity_findings=(), label_fatal_codes=(),
                           capture_fatal_codes=()):
    """门槛资格的不合格理由清单；**空清单**才表示"可用于门槛比较"。

    资格 = 已声明身份 ∧ 有可归属的合格洁净轮 ∧ 有确认样本 ∧ 本轮无致命发现。
    只判身份会让空捕获、解析失败或仅 partial 的输入也拿到资格：`runs=0` 时
    合并统计里没有一条样本可供比较，`eligibleForThreshold=true` 属伪结论。
    理由逐条列出（不折叠为单个布尔或笼统字符串），调用方可直接看出是哪一项
    不成立；被排除的块与致命检出记录仍随 `excluded`/`findings` 完整保留。
    """
    reasons = []

    def add(reason):
        if reason not in reasons:
            reasons.append(reason)

    if group_identity is None:
        add('GROUP_IDENTITY_NOT_DECLARED')
    if conflicts:
        add('GROUP_IDENTITY_CONFLICT')
    if mismatches:
        add('GROUP_IDENTITY_MISMATCH')
    for code in sorted({finding.code for finding in identity_findings
                        if finding.severity == 'fatal'
                        and finding.code in IDENTITY_BLOCKING_CODES}):
        add(code)
    if merged['runs'] == 0:
        add('NO_ELIGIBLE_RUNS')
    elif merged['ackLatency']['count'] == 0:
        add('NO_ACK_SAMPLES')
    for code in sorted(set(label_fatal_codes) | set(capture_fatal_codes)):
        add('FATAL:%s' % code)
    return reasons


def aggregate(groups, label, group_identity=None, identity_findings=(),
              capture_findings=()):
    """按 TUNING/PERFORMANCE 冻结口径合并同一 label 的合格洁净轮样本。

    只消费 `analyse()`/`check()` 已经写回 `group.findings` 的结论（含解析期
    致命项与严格模式结论），**不**在此重跑宽松模式判定。

    可用等级：
      * `attributable`：无致命、无拖尾（样本population归属明确）、单实例段、
        偏移集合自洽；只有这一级的样本允许进入数值池；
      * `clean`：另需 `transfer.outcome == 'ok'` 且 `ackSamples == 'complete'`；
      * `threshold`：另需实验身份已声明、与观测一致，且输入绑定无致命项。

    观测身份签名冲突时拆分为多个独立输入组并报 `GROUP_IDENTITY_CONFLICT`
    （warn），此时不产出跨组混合统计（`runs=0`）。

    [identity_findings] 为侧车身份校验（含输入 SHA 绑定与重复输入）产生的
    检出；其中 `IDENTITY_BLOCKING_CODES` 里的致命项会使合并失去门槛资格——
    身份不可归属时诊断统计可以保留，但不得被拿去和门槛比较。

    [capture_findings] 为本轮输入产生的**全部**检出（`analyse_logs` 的返回）。
    只要其中存在致命项，门槛资格即不成立（理由 `FATAL:<CODE>`）：门槛比较
    要求整个采集轮次可复核，不能因为致命项落在别的块上就当作没有发生。
    """
    candidates, excluded, unclosed_blocks, unclosed_samples = [], [], 0, 0
    invalid_summary_blocks = 0
    for group in groups:
        if group.summary is None:
            if group.invalid_summary:
                invalid_summary_blocks += 1
            if {s.label for s in group.samples} == {label}:
                unclosed_blocks += 1
                unclosed_samples += len(group.samples)
            continue
        if group.label != label:
            continue
        if not group.checked:
            group.findings = check_group_only(group)
            group.checked = True
        attributable, clean = _classify(group, excluded)
        if attributable and clean:
            candidates.append(group)

    by_signature = collections.OrderedDict()
    for group in candidates:
        by_signature.setdefault(_identity_signature(group.summary),
                                []).append(group)

    conflicts = len(by_signature) > 1
    findings = []
    if conflicts:
        findings.append(Finding(
            'GROUP_IDENTITY_CONFLICT', 'warn',
            '同一 label 下出现 %d 个不同的观测身份签名（设备/MTU/写模式等参数'
            '不一致），已拆分为独立输入组，不产出跨组混合统计：%s'
            % (len(by_signature),
               json.dumps([_signature_label(b[0].summary)
                           for b in by_signature.values()],
                          ensure_ascii=False, sort_keys=True)), None))

    signature_groups = []
    for blocks in by_signature.values():
        entry = _pool(blocks)
        entry['signature'] = _signature_label(blocks[0].summary)
        signature_groups.append(entry)

    mismatches = []
    if group_identity is not None:
        for group in candidates:
            for key, path in GROUP_IDENTITY_OBSERVABLE.items():
                if not _has(group.summary, *path):
                    continue  # 日志未提供该观测字段（仅声明字段）
                if _dig(group.summary, *path) != group_identity.get(key):
                    mismatches.append({
                        'field': key,
                        'declared': group_identity.get(key),
                        'observed': _dig(group.summary, *path),
                        'summaryLine': group.summary_line,
                    })
        for item in mismatches:
            findings.append(Finding(
                'GROUP_IDENTITY_MISMATCH', 'fatal',
                '摘要 %s 的观测身份与侧车声明不符：声明=%r 观测=%r'
                % (item['field'], item['declared'], item['observed']),
                item['summaryLine']))

    if conflicts:
        merged = {'runs': 0, 'ackLatency': {'count': 0, 'minUs': None,
                                            'p50Us': None, 'p95Us': None,
                                            'p99Us': None, 'maxUs': None},
                  'retransmitFrames': 0, 'segmentsUnique': 0,
                  'retransmitRate': None, 'runsWithAbsentFields': 0,
                  'runsWithStragglerSamples': 0}
    elif signature_groups:
        merged = dict(signature_groups[0])
        merged.pop('signature', None)
    else:
        merged = _pool([])

    reasons = _qualification_reasons(
        merged, group_identity, conflicts, mismatches, identity_findings,
        label_fatal_codes={finding.code for group in groups
                           if group.label == label
                           for finding in group.findings
                           if finding.severity == 'fatal'},
        capture_fatal_codes={finding.code for finding in capture_findings
                             if finding.severity == 'fatal'})
    merged['eligibleForThreshold'] = not reasons
    merged['ineligibleReasons'] = reasons
    merged['identity'] = {
        'mode': 'declared' if group_identity is not None else 'observed',
        'groupId': (group_identity or {}).get('groupId'),
        'declared': group_identity,
        'observedSignatures': [_signature_label(blocks[0].summary)
                               for blocks in by_signature.values()],
    }
    merged['groups'] = signature_groups
    merged['excluded'] = excluded
    merged['excludedRuns'] = len(excluded)
    merged['diagnostic'] = _pool(candidates)
    merged['strictFieldsComplete'] = bool(candidates) and \
        merged['runsWithAbsentFields'] == 0
    merged['label'] = label
    merged['unclosedBlocks'] = unclosed_blocks
    merged['unclosedSamples'] = unclosed_samples
    merged['invalidSummaryBlocks'] = invalid_summary_blocks
    merged['findings'] = [f.as_dict() for f in findings]
    return merged, findings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='解析 OTA_LINK_SAMPLE / OTA_LINK_STATS 并做一致性检出')
    parser.add_argument('--log', required=True, action='append', default=None,
                        help='原始日志文件路径（可重复；多个文件构成同一实验输入组）')
    parser.add_argument('--group', default=None,
                        help='实验身份侧车 JSON：声明 device/MTU/写模式/波特率/'
                             '超时/重试/包/sender 并绑定各 --log 的 SHA-256')
    parser.add_argument('--label', default='upgrade',
                        help='合并统计的 label（默认 upgrade）')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出结论')
    parser.add_argument('--device-capture', action='store_true',
                        help='严格块模型（每块恰一个实例且必须收口）：'
                             '时钟回退、偏移集合违例与末尾未收口块按致命处理，'
                             '供设备采集轮次使用')
    args = parser.parse_args(argv)

    inputs, inputs_meta, binding_findings = [], [], []
    seen_digest = {}
    for path in args.log:
        try:
            with open(path, 'r', encoding='utf-8', errors='replace') as handle:
                text = handle.read()
        except OSError as exc:
            print('读取失败: %s' % exc, file=sys.stderr)
            return 2
        digest = _sha256_file(path)
        name = os.path.basename(path)
        # 来源标识带内容摘要：不同目录下的同名日志不会互相顶替，排除记录
        # 与结论都能指回唯一一份捕获。
        source_id = '%s#%s' % (name, digest[:12])
        meta = {'path': path, 'name': name, 'sourceId': source_id,
                'sha256': digest, 'bytes': os.path.getsize(path),
                'duplicateOf': None}
        first = seen_digest.get(digest)
        if first is not None:
            # 同一份捕获的副本不是独立轮次。重复解析会把 runs 与样本数直接
            # 成倍虚增（1 份日志报成 2 轮），因此只解析一次并如实报告重复。
            meta['duplicateOf'] = first['sourceId']
            binding_findings.append(Finding(
                'DUPLICATE_INPUT', 'fatal',
                '输入 %s 与 %s 字节相同（sha256=%s）：同一捕获的副本不是独立'
                '轮次，重复引用会使轮数与确认样本数成倍虚增；本轮按一次输入'
                '合并，并据此判定该输入集合不具备门槛资格'
                % (source_id, first['sourceId'], digest), None))
            inputs_meta.append(meta)
            continue
        seen_digest[digest] = meta
        inputs.append((source_id, text))
        inputs_meta.append(meta)
    unique_meta = [meta for meta in inputs_meta if meta['duplicateOf'] is None]

    findings = []
    try:
        groups, findings = analyse_logs(inputs, device_capture=args.device_capture)
        identity = None
        identity_findings = list(binding_findings)
        if args.group is not None:
            identity = load_group_identity(
                args.group, [(meta['sourceId'], meta['path'])
                             for meta in unique_meta], identity_findings)
        report, report_findings = aggregate(
            groups, args.label, group_identity=identity,
            identity_findings=identity_findings, capture_findings=findings)
        findings.extend(identity_findings)
        findings.extend(report_findings)
    except Exception as exc:  # 兜底：任何未预期异常也必须给出结构化结论
        import traceback
        groups = []
        findings.append(Finding('INTERNAL_ERROR', 'fatal',
                                '解析器内部异常（输入形状超出已建模范围）：%s: %s'
                                % (type(exc).__name__, exc), None))
        report = {'label': args.label, 'runs': 0, 'excludedRuns': 0,
                  'excluded': [], 'eligibleForThreshold': False,
                  'ineligibleReasons': ['INTERNAL_ERROR'],
                  'ackLatency': {'count': 0, 'minUs': None, 'p50Us': None,
                                 'p95Us': None, 'p99Us': None, 'maxUs': None},
                  'groups': [], 'diagnostic': {'runs': 0},
                  'strictFieldsComplete': False, 'unclosedBlocks': 0,
                  'unclosedSamples': 0, 'runsWithAbsentFields': 0,
                  'runsWithStragglerSamples': 0, 'identity': None,
                  'traceback': traceback.format_exc()}

    fatal = [f for f in findings if f.severity == 'fatal']
    if args.json:
        print(json.dumps({
            'log': args.log,
            'inputs': inputs_meta,
            'groups': len(groups),
            'samples': sum(len(g.samples) for g in groups),
            'findings': [f.as_dict() for f in findings],
            'report': report,
        }, ensure_ascii=False, sort_keys=True))
    else:
        for finding in findings:
            print(finding)
        print('---- 观测块 %d 个，样本 %d 条，致命发现 %d 项，告警 %d 项 ----'
              % (len(groups), sum(len(g.samples) for g in groups),
                 len(fatal), len(findings) - len(fatal)))
        print('合并统计 %s（门槛可用=%s）：%s'
              % (args.label, report.get('eligibleForThreshold'),
                 json.dumps({k: v for k, v in report.items()
                             if k not in ('groups', 'excluded')},
                            ensure_ascii=False, sort_keys=True)))
    return 1 if fatal else 0


if __name__ == '__main__':
    sys.exit(main())
