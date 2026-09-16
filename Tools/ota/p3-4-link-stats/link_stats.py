#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-4 链路观测日志解析器（OTA_LINK_SAMPLE / OTA_LINK_STATS）。

用途：把设备或测试轮次采集到的原始日志解析成可判定的观测记录，并按
`docs/ota-cross-system-contracts.md` 的 `OTA-XC-BLE-TUNING` 冻结口径做
合并统计与一致性检出。解析侧必须 fail-closed：无法解释的输入不得被静默
接受（P3-4 集中预审 §7.4④ 的交付要求）。

行格式契约（发射端 `app/bluetooth_flutter_Trace/lib/ota/ota_link_stats.dart`，
格式冻结见 `docs/ota-exec-notes/P3-4-research-link-timing-2026-09-16.md` §4.2）：

    OTA_LINK_SAMPLE label=<label> kind=<kind> us=<int> [key=value ...]
    OTA_LINK_STATS {json}        ← 每个 stats 实例恰一份（幂等，仅首次）

`us` 的语义按 kind 分两类，解析器必须区分，不能一律当时间戳处理：

  * 时间戳（实例级单调 Stopwatch，组内非递减）：`segment_first_send`、
    `segment_retransmit`、`ack_early`、`ack_early_invalid`、`durable`；
  * 耗时（任意大小但非负）：`ack_latency`、`gatt_write`、`discover`、
    `platform_write`、`get_info`。

## 分组模型与"拖尾样本"

日志是**顺序文本**：一段连续样本 + 紧随其后的摘要 = 一个观测块。但摘要
打印的是"打印时刻的实例累计值"，同一实例（或复用该实例的调用方）在摘要
之后仍可能继续写样本——真实第六轮日志里，每个 upgrade 摘要之后都跟着
`kind=gatt_write bytes=10`（重连身份复核的 INFO 写）。这些**拖尾样本**会
落进下一个观测块的缓冲区，使缓冲区计数大于摘要声明。因此判定规则是：

  * 缓冲区计数 **大于** 摘要声明 → `STRAGGLER`（warn）：摘要后仍有该实例
    的样本，属已知发射行为，需人工确认而非判红；
  * 缓冲区计数 **小于** 摘要声明 → `COUNT_MISMATCH`（fatal）：摘要声明了
    日志中不存在的观测，即日志截断/丢行，测量不可采信；
  * 二者相等（`exact`）时，才具备核对分位数与完整性声明的条件。

## 实测形状：一个块里可能有多个实例

真实捕获（`.cache/ci-*/…/logs/tests.log`）显示：并非每个实例都会输出摘要。
传输级用例只断言样本行、设备采集也可能在传输中途被截断，于是**若干实例的
样本会连续落进同一个缓冲区**，直到下一个摘要出现才被一起收口。此时块内会
出现实例时钟回退（新实例的 Stopwatch 从 0 重新计时）。

因此时钟回退按两种模式判定：

  * 默认：回退处切分为新的实例段，报 `MULTI_INSTANCE`（warn）——块内混有
    多个实例（前序实例未收口），属真实且合法的采集形状；
  * `--device-capture`（设备采集轮次的严格块模型：每块恰一个实例且必须
    收口）：同样的回退报 `CLOCK_NONMONOTONIC`（fatal），文件末尾未收口
    观测块报 `SUMMARY_MISSING`（fatal）。

分位数与计数核对用**整块**样本重算（不猜哪一段属于收口摘要），所以混入的
外来样本只会表现为 `STRAGGLER`（观测多于声明），不会掩盖"摘要声明多于
观测"的 fatal 方向。

## 两类"缺失"必须分开（判定强度不同）

  * **摘要声明多于日志观测** → `COUNT_MISMATCH`（fatal）：摘要声明了日志里
    不存在的观测，即丢行/截断发生在摘要之前，测量不可采信。这是真正的
    "日志缺失"检出（摘要所属实例的样本必然全部在它收口的块内，故该方向
    不会因混组而误报）；
  * **样本之后没有摘要** → `SUMMARY_MISSING`（默认 warn）：该块没有可核对的
    声明，因此**不参与合并统计**（无摘要即无 label/终态权威）。

## 字段缺失（发射端版本）

`schema` 保持为 1 的同时，整改批（P34-R01/R04/R05）新增了
`ackEarlyInvalid`、`ackEarlyUnsent`、`getInfo.failures`、`discovers.errors`、
`platformWrites.errors` 等字段。整改前的真实日志因此**合法地**缺少这些
字段。解析器把缺失字段报为 `FIELD_ABSENT`（warn）并在合并报告里标注
`strictFieldsComplete=false`，绝不按缺省 0 静默通过；但在**同版本**日志
上出现缺字段仍应视为缺陷，需按发射端提交核对，报告不得据此声称契约完整。

只读工具：不修改输入日志，不产生仓库外输出。退出码 0=无致命发现，
1=存在致命发现，2=用法或读取错误。
"""

import argparse
import json
import math
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

# 分位数/完整性核对所需的精确计数键（存在拖尾样本时无法重构样本集合）。
EXACT_KEYS_FOR_QUANTILE = frozenset(['ackLatencyCount'])
EXACT_KEYS_FOR_INTEGRITY = frozenset([
    'segmentsUnique',
    'ackLatencyCount',
    'ackEarlyInvalid',
    'ackEarlyUnsent',
])

_TOKEN_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)=([^=]*)$')
_INT_RE = re.compile(r'^-?\d+$')


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
    严格相等的键集合（是分位数/完整性核对的前置条件）。
    """

    __slots__ = ('samples', 'summary', 'summary_line', 'first_line',
                 'counts', 'declared', 'exact_keys', 'field_absent')

    def __init__(self, samples, summary, summary_line=None):
        self.samples = samples
        self.summary = summary
        self.summary_line = summary_line
        self.first_line = samples[0].line_no if samples else summary_line
        self.counts = {}
        self.declared = {}
        self.exact_keys = set()
        self.field_absent = []

    @property
    def label(self):
        if self.summary is not None:
            return self.summary.get('label')
        return self.samples[0].label if self.samples else None

    def kinds(self, kind):
        return [s for s in self.samples if s.kind == kind]


def _int(value):
    return int(value) if _INT_RE.match(str(value)) else None


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


def parse_log(text, strict_tail=False):
    """按顺序解析整份日志，返回 (groups, findings)。

    [strict_tail] 为真时，文件末尾未收口的观测块按致命处理（设备采集轮次
    要求每块必有摘要）；默认只告警，因为传输级用例与中途截断的合法日志
    同样会留下未收口样本。
    """
    groups, findings, buffer = [], [], []
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith(SAMPLE_PREFIX):
            sample = parse_sample(line, line_no, findings)
            if sample is not None:
                buffer.append(sample)
        elif line.startswith(STATS_PREFIX):
            payload = line[len(STATS_PREFIX):].strip()
            try:
                summary = json.loads(payload)
            except ValueError as exc:
                findings.append(Finding('BAD_JSON', 'fatal',
                                        '摘要 JSON 不可解析: %s' % exc, line_no))
                summary = None
            if summary is not None and not isinstance(summary, dict):
                findings.append(Finding('BAD_JSON', 'fatal',
                                        '摘要 JSON 顶层非对象', line_no))
                summary = None
            groups.append(Group(buffer, summary, line_no))
            buffer = []
    if buffer:
        groups.append(Group(buffer, None))
        findings.append(Finding(
            'SUMMARY_MISSING', 'fatal' if strict_tail else 'warn',
            '文件结束时仍有 %d 条样本未被摘要收口（无声明可核对，该块不参与'
            '合并；若本轮要求每块必收口，用 --strict-tail 判定为致命）'
            % len(buffer), buffer[0].line_no))
    return groups, findings


def _nearest_rank(values, q):
    """nearest-rank 分位数：升序第 ceil(q*N) 个，不插值（与发射端同口径）。"""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(math.ceil(q * len(ordered))))
    return ordered[rank - 1]


def _dig(summary, *path):
    node = summary
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def _sum_bytes(group, kind, findings):
    total, ok = 0, True
    for sample in group.kinds(kind):
        value = _int(sample.extra.get('bytes'))
        if value is None:
            findings.append(Finding('MALFORMED_SAMPLE', 'fatal',
                                    '%s 样本缺 bytes 或非整数' % kind, sample.line_no))
            ok = False
            break
        total += value
    return total if ok else None


def _observed_counts(group, findings):
    """按样本重算各计数键（与摘要声明逐键对照的左侧）。"""
    durable = group.kinds('durable')
    final_off = None
    if durable:
        value = _int(durable[-1].extra.get('off'))
        if value is None:
            findings.append(Finding('MALFORMED_SAMPLE', 'fatal',
                                    'durable 样本缺 off 或非整数', durable[-1].line_no))
        else:
            final_off = value
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


def _check_structure(group, findings):
    summary = group.summary
    line_no = group.summary_line
    if _dig(summary, 'schema') not in SCHEMA_SUPPORTED:
        findings.append(Finding('SCHEMA_UNKNOWN', 'fatal',
                                '摘要 schema=%r 不在受支持集合 %s'
                                % (_dig(summary, 'schema'), sorted(SCHEMA_SUPPORTED)),
                                line_no))
    if _dig(summary, 'clock') != CLOCK_DOMAIN:
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
    """按实例时钟回退把缓冲区切成多个实例段（时间戳类样本非递减为同段）。"""
    segments = []
    high = None
    for sample in samples:
        if sample.kind in TIMESTAMP_KINDS:
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


def _check_counters(group, findings):
    """逐键对照：缺失=warn(FIELD_ABSENT)，少=致命，多=拖尾告警。"""
    summary, line_no = group.summary, group.summary_line
    observed = group.counts
    for path, key in COUNTER_KEYS:
        declared = _dig(summary, *path)
        if key == 'durableFinalOff':
            continue  # 末值单独判定（见下），非计数
        if declared is None:
            group.field_absent.append('.'.join(path))
            findings.append(Finding('FIELD_ABSENT', 'warn',
                                    '摘要缺少字段 %s（整改前发射端版本合法缺失；'
                                    '同版本日志出现即缺陷）' % '.'.join(path), line_no))
            continue
        value = observed.get(key)
        if value is None:
            continue  # bytes 已报畸形，避免级联噪声
        group.declared[key] = declared
        if value == declared:
            group.exact_keys.add(key)
        elif value < declared:
            findings.append(Finding('COUNT_MISMATCH', 'fatal',
                                    '%s 摘要声明多于日志观测：摘要=%r 样本重算=%r'
                                    % ('.'.join(path), declared, value), line_no))
        else:
            findings.append(Finding('STRAGGLER', 'warn',
                                    '%s 日志观测多于摘要声明：摘要=%r 样本重算=%r'
                                    '（摘要后仍有该实例样本，需人工确认）'
                                    % ('.'.join(path), declared, value), line_no))

    declared_final = _dig(summary, 'transfer', 'durable', 'finalOff')
    observed_final = observed.get('durableFinalOff')
    if declared_final is not None:
        group.declared['durableFinalOff'] = declared_final
        offsets = [_int(s.extra.get('off')) for s in group.kinds('durable')]
        if observed_final is None:
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


def _check_quantiles(group, findings):
    """分位数/派生量核对；样本集合可重构（计数精确）时必须逐字段相等。"""
    summary, line_no = group.summary, group.summary_line
    if EXACT_KEYS_FOR_QUANTILE <= group.exact_keys:
        values = [s.us for s in group.kinds('ack_latency')]
        expected = {
            'minUs': min(values) if values else None,
            'p50Us': _nearest_rank(values, 0.50),
            'p95Us': _nearest_rank(values, 0.95),
            'p99Us': _nearest_rank(values, 0.99),
            'maxUs': max(values) if values else None,
        }
        for name, value in expected.items():
            declared = _dig(summary, 'transfer', 'ackLatency', name)
            if declared != value:
                findings.append(Finding('QUANTILE_MISMATCH', 'fatal',
                                        'transfer.ackLatency.%s 不一致：样本重算（nearest-rank）=%r 摘要声明=%r'
                                        % (name, value, declared), line_no))

    elapsed = _dig(summary, 'transfer', 'elapsedUs')
    start = _dig(summary, 'transfer', 'startUs')
    end = _dig(summary, 'transfer', 'endAckUs')
    expected_elapsed = (end - start) if (start is not None and end is not None) else None
    if elapsed != expected_elapsed:
        findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                'transfer.elapsedUs 不一致：endAckUs-startUs=%r 摘要=%r'
                                % (expected_elapsed, elapsed), line_no))


def _check_integrity(group, findings):
    if not (EXACT_KEYS_FOR_INTEGRITY <= group.exact_keys):
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
    if None not in (unique, total, retransmit) and retransmit != total - unique:
        findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                'retransmitFrames != segmentSendTotal - segmentsUnique（%r != %r - %r）'
                                % (retransmit, total, unique), line_no))

    phases = _dig(summary, 'phases')
    if isinstance(phases, dict):
        for name, bounds in phases.items():
            if not isinstance(bounds, list) or not bounds:
                findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                        'phases.%s 结构非法：%r' % (name, bounds), line_no))
                continue
            if not all(isinstance(v, int) for v in bounds):
                findings.append(Finding('INTERNAL_INCONSISTENT', 'fatal',
                                        'phases.%s 含非整数时间戳：%r' % (name, bounds), line_no))
                continue
            if len(bounds) > 1 and bounds[1] < bounds[0]:
                findings.append(Finding('PHASE_REVERSED', 'fatal',
                                        'phases.%s 结束早于开始：%r' % (name, bounds), line_no))
        bind = phases.get('bind')
        declared = _dig(summary, 'bind', 'phaseUs')
        expected = (bind[1] - bind[0]) if isinstance(bind, list) and len(bind) == 2 else None
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
        if not isinstance(value, int) or value < 1:
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
    _check_structure(group, findings)
    group.counts = _observed_counts(group, findings)
    _check_labels(group, findings)
    _check_clock(group, findings, strict_blocks=strict_blocks)
    _check_counters(group, findings)
    _check_quantiles(group, findings)
    _check_integrity(group, findings)
    _check_derived(group, findings)
    _check_attempts(group, findings)


def check(groups, findings, strict_blocks=False):
    for group in groups:
        check_group(group, findings, strict_blocks=strict_blocks)
    return findings


def check_group_only(group, strict_blocks=False):
    findings = []
    check_group(group, findings, strict_blocks=strict_blocks)
    return findings


def analyse(text, device_capture=False):
    """解析 + 检出，返回 (groups, findings)。

    [device_capture] 启用严格块模型（每块恰一个实例且必须收口），供设备
    采集轮次使用；默认放宽为"块内可含多个未收口实例"。
    """
    groups, findings = parse_log(text, strict_tail=device_capture)
    check(groups, findings, strict_blocks=device_capture)
    return groups, findings


def aggregate(groups, label, require_clean=True):
    """按 TUNING 冻结口径合并同一 label 的 clean run 样本。

    clean run = 该块无致命检出且 `transfer.outcome == 'ok'`；合并对象是原始
    ack_latency 样本，分位数用同一 nearest-rank 口径重算。有拖尾样本
    （`STRAGGLER`）或缺失字段的块仍可合并，但报告会标注其严格程度，避免把
    非严格数据当成契约完整证据。
    """
    merged, runs, excluded, devices = [], 0, 0, set()
    retransmit, unique, incomplete, straggled = 0, 0, 0, 0
    unclosed_blocks, unclosed_samples = 0, 0
    for group in groups:
        if group.summary is None:
            if {s.label for s in group.samples} == {label}:
                unclosed_blocks += 1
                unclosed_samples += len(group.samples)
            continue
        if group.label != label:
            continue
        findings = check_group_only(group)
        fatal = [f for f in findings if f.severity == 'fatal']
        if require_clean and (fatal or _dig(group.summary, 'transfer', 'outcome') != 'ok'):
            excluded += 1
            continue
        runs += 1
        devices.add(group.summary.get('device'))
        merged.extend(s.us for s in group.kinds('ack_latency'))
        retransmit += _dig(group.summary, 'transfer', 'retransmitFrames') or 0
        unique += _dig(group.summary, 'transfer', 'segmentsUnique') or 0
        if any(f.code == 'FIELD_ABSENT' for f in findings):
            incomplete += 1
        if any(f.code == 'STRAGGLER' for f in findings):
            straggled += 1
    return {
        'label': label,
        'runs': runs,
        'excludedRuns': excluded,
        'devices': sorted(d for d in devices if d is not None),
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
        'runsWithAbsentFields': incomplete,
        'strictFieldsComplete': incomplete == 0,
        'runsWithStragglerSamples': straggled,
        'unclosedBlocks': unclosed_blocks,
        'unclosedSamples': unclosed_samples,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='解析 OTA_LINK_SAMPLE / OTA_LINK_STATS 并做一致性检出')
    parser.add_argument('--log', required=True, help='原始日志文件路径')
    parser.add_argument('--label', default='upgrade',
                        help='合并统计的 label（默认 upgrade）')
    parser.add_argument('--json', action='store_true', help='以 JSON 输出结论')
    parser.add_argument('--device-capture', action='store_true',
                        help='严格块模型（每块恰一个实例且必须收口）：'
                             '时钟回退与末尾未收口块按致命处理，'
                             '供设备采集轮次使用')
    args = parser.parse_args(argv)

    try:
        with open(args.log, 'r', encoding='utf-8', errors='replace') as handle:
            text = handle.read()
    except OSError as exc:
        print('读取失败: %s' % exc, file=sys.stderr)
        return 2

    groups, findings = analyse(text, device_capture=args.device_capture)
    fatal = [f for f in findings if f.severity == 'fatal']
    report = aggregate(groups, args.label)

    if args.json:
        print(json.dumps({
            'log': args.log,
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
        print('合并统计 %s: %s' % (args.label,
                                  json.dumps(report, ensure_ascii=False, sort_keys=True)))
    return 1 if fatal else 0


if __name__ == '__main__':
    sys.exit(main())
