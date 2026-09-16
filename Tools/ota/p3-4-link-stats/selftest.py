#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-4 链路观测日志解析器自测（`link_stats.py` 配套正例控制与负例）。

用途：证明 `link_stats.py` 的检出**有鉴别力**——正常输入不报致命，四类预审
要求（预审 §7.4④）的缺陷各自可被检出并给出预期检出码。覆盖矩阵：

1. **正例控制（真实数据）**：`fixtures/round6-ubuntu-head.log` 逐字节切片
   （274 行，含噪声行与 4 个已收口单实例块）在默认与 `--device-capture`
   两种模式下都必须 **0 致命、0 告警误报类别**（除 `FIELD_ABSENT`：该轮
   发射端早于 R01/R04/R05，缺字段是真实的）。这一项同时证明严格模式不是
   "一律打红"；
2. **严格契约正例**：真实样本行 + 由本文件**独立重算**的当前契约摘要
   （计数、分位数、完整性、时长全部由样本推出，非复用解析器实现）→
   **0 发现**（无致命也无告警），证明计数/分位数/完整性三组核对在字段齐全
   时能整体通过；
3. **负例（每项一个可检出缺陷）**：
   * 日志缺失：删样本行、改小声明计数 → `COUNT_MISMATCH`(fatal)；
   * 混组：样本 label 与摘要不符、样例 label 混用、`attempts[].n` 回退 →
     `MIXED_LABEL` / `MIXED_ATTEMPT`(fatal)；
   * 错误摘要：分位数、计数、内部派生量、完整性声明被篡改 →
     `QUANTILE_MISMATCH` / `COUNT_MISMATCH` / `INTERNAL_INCONSISTENT` /
     `INTEGRITY_MISMATCH`(fatal)；
   * 时钟域错配：`clock` 非冻结域、`schema` 未知、`us` 为负、阶段倒置、
     实例时钟回退 → `CLOCK_DOMAIN` / `SCHEMA_UNKNOWN` / `CLOCK_NEGATIVE` /
     `PHASE_REVERSED`(fatal)，回退在默认模式为 `MULTI_INSTANCE`(warn)、
     在 `--device-capture` 为 `CLOCK_NONMONOTONIC`(fatal)；
   * 结构：摘要 JSON 破损、样本畸形、未知 kind、必需对象缺失 →
     `BAD_JSON` / `MALFORMED_SAMPLE` / `UNKNOWN_KIND` / `SCHEMA_MISSING`；
   * 未收口：删摘要、摘要后拖尾样本 → `SUMMARY_MISSING` / `STRAGGLER`
     （默认 warn，`--device-capture` 下前者为 fatal）；
4. **分位数口径**：nearest-rank（升序第 ceil(q*N) 个，不插值，N=0 → null）
   与冻结口径一致，含 N=1、整除边界、奇数样本；
5. **CLI 契约**：`--json` 结论形状、致命存在时退出码 1、读取失败退出码 2、
   真实切片默认/严格模式退出码 0；
6. **整份真实日志（可选）**：`.cache/ci-35034258547/.../tests.log` 若在场，
   断言 0 致命且告警类别闭集；不在场则如实 SKIP（外部证据不入库）。

样本行的真实性：负例用的样本行全部取自 `fixtures/` 里的真实切片；只有
"多实例同块"的拼接方式与摘要字段是构造的，构造方式在各用例内注明。

运行：python selftest.py（仅标准库）。退出码 0 表示全部通过。
"""

import io
import json
import math
import os
import sys
import glob
import subprocess
import traceback
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import link_stats as L  # noqa: E402  （同目录解析器，为其编写自测）

FIXTURE = os.path.join(HERE, 'fixtures', 'round6-ubuntu-head.log')

# 整份真实捕获（不入库的 CI 证据，保存在**主 worktree** 的 .cache/ 下）。
CAPTURE_RUN = 'ci-35034258547'
CAPTURE_EXPECTATIONS = {
    # 每宿主一份真实形状：块/样本数、检出计数、合并报告的关键量。
    'ubuntu': {
        'blocks': 27,
        'samples': 801,
        'codes': {'FIELD_ABSENT': 130, 'SUMMARY_MISSING': 1, 'STRAGGLER': 12},
        'report': {'runs': 7, 'excludedRuns': 12, 'unclosedBlocks': 1,
                   'unclosedSamples': 434, 'segmentsUnique': 56,
                   'ackLatencyCount': 56},
    },
    'windows': {
        'blocks': 27,
        'samples': 821,
        'codes': {'FIELD_ABSENT': 135, 'MULTI_INSTANCE': 1, 'STRAGGLER': 24},
        'report': {'runs': 8, 'excludedRuns': 12, 'unclosedBlocks': 0,
                   'unclosedSamples': 0, 'segmentsUnique': 64,
                   'ackLatencyCount': 266},
    },
}

# 整改前发射端缺失的字段（该轮日志合法缺失，见 fixtures/PROVENANCE.md）。
LEGACY_ABSENT_FIELDS = frozenset([
    'transfer.ackEarlyInvalid',
    'transfer.ackEarlyUnsent',
    'getInfo.failures',
    'discovers.errors',
    'platformWrites.errors',
])


# ---------------------------------------------------------------- 夹具读取


def main_worktree_root():
    """定位主 worktree 根（CI 证据保存在那里，不在本 worktree 内）。

    只读查询；git 不可用或输出不可解释时返回 None，由调用方按 SKIP 处理。
    """
    for extra in (['--path-format=absolute'], []):
        try:
            result = subprocess.run(
                ['git', 'rev-parse'] + extra + ['--git-common-dir'],
                cwd=HERE, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            continue
        common = result.stdout.strip()
        if not common:
            continue
        if not os.path.isabs(common):
            common = os.path.normpath(os.path.join(HERE, common))
        # <主 worktree>/.git ← 上一级即主 worktree 根
        return os.path.dirname(common)
    return None


def optional_captures():
    """返回 [(宿主, 整份 tests.log 路径), ...]；不在场则为空列表。"""
    root = main_worktree_root()
    if root is None:
        return []
    found = []
    for host in sorted(CAPTURE_EXPECTATIONS):
        pattern = os.path.join(root, '.cache', CAPTURE_RUN, host, '*',
                               'logs', 'tests.log')
        found.extend((host, path) for path in sorted(glob.glob(pattern)))
    return found


# ---------------------------------------------------------------- 夹具读取


def fixture_lines():
    with open(FIXTURE, 'rb') as handle:
        return handle.read().decode('utf-8').splitlines()


def fixture_groups():
    """解析真实切片，返回 (groups, findings)（默认模式）。"""
    return L.analyse('\n'.join(fixture_lines()))


def real_block(index):
    """取真实切片里第 index 个观测块的 (样本行, 样本对象)。

    块内可能夹着噪声行（测试名、`OTA sent n/total` 等），因此按样本前缀
    过滤，而不是直接对行号区间取整段。
    """
    groups, _ = fixture_groups()
    group = groups[index]
    lines = fixture_lines()
    window = lines[group.samples[0].line_no - 1:group.summary_line - 1]
    sample_lines = [ln for ln in window if ln.strip().startswith(L.SAMPLE_PREFIX)]
    if len(sample_lines) != len(group.samples):
        raise AssertionError('夹具行范围与样本数不符：块%d' % index)
    return sample_lines, group.samples


# ------------------------------------------------- 独立重算（不复用解析器）


def nearest_rank(values, q):
    """独立实现的 nearest-rank（对照解析器口径，故意不复用其实现）。"""
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, int(math.ceil(q * len(ordered))))
    return ordered[rank - 1]


def recompute_summary(samples, label='upgrade', device='AA:BB'):
    """按当前契约从样本行独立重算摘要（字段齐全，供严格正例使用）。

    计数、分位数、完整性与时长字段全部由样本推出；`bind.*` 与 `phases`
    的取值样本无法决定（无对应样本种类），此处给出自洽的固定值，仅为让
    "字段齐全"这一路径可被完整核对，不代表真实绑定观测。
    """
    kinds = {}
    for sample in samples:
        kinds.setdefault(sample.kind, []).append(sample)

    def count(kind):
        return len(kinds.get(kind, []))

    def errors(kind):
        return len([s for s in kinds.get(kind, []) if s.extra.get('error') == '1'])

    def total_bytes(kind):
        return sum(int(s.extra.get('bytes', '0')) for s in kinds.get(kind, []))

    first_send = count('segment_first_send')
    retransmit = count('segment_retransmit')
    ack_latency = [s.us for s in kinds.get('ack_latency', [])]
    early_invalid = count('ack_early_invalid')
    early_unsent = count('ack_early') - early_invalid
    durable = kinds.get('durable', [])
    timestamps = [s.us for s in samples if s.kind in L.TIMESTAMP_KINDS]
    start_us = min(timestamps) if timestamps else None
    end_us = max(timestamps) if timestamps else None

    missing = first_send - len(ack_latency)
    parts = []
    if missing > 0:
        parts.append('missing=%d' % missing)
    if early_invalid > 0:
        parts.append('early=%d' % early_invalid)
    integrity = 'complete' if not parts else 'partial:%s' % ','.join(parts)

    return {
        'schema': 1,
        'label': label,
        'device': device,
        'attempt': None,
        'clock': L.CLOCK_DOMAIN,
        'phases': {
            'bind': [0, start_us],
            'transfer': [start_us, end_us],
        },
        'failure': {'stage': None, 'reason': None},
        'attempts': [],
        'attemptEndUs': None,
        'bind': {
            'charsUs': 1000,
            'found': True,
            'writeMode': 'withoutResponse',
            'mtuRequested': 247,
            'mtuChunkBytes': 244,
            'mtuSource': 'negotiated',
            'mtuUs': 500,
            'subscribeUs': 300,
            'subscribeOk': True,
            'phaseUs': start_us,
        },
        'getInfo': {
            'calls': count('get_info'),
            'failures': len([s for s in kinds.get('get_info', [])
                             if s.extra.get('ok') == '0']),
            'totalUs': sum(s.us for s in kinds.get('get_info', [])),
        },
        'transfer': {
            'startUs': start_us,
            'endAckUs': end_us,
            'elapsedUs': (end_us - start_us)
                         if (start_us is not None and end_us is not None) else None,
            'outcome': 'ok',
            'segmentsUnique': first_send,
            'segmentSendTotal': first_send + retransmit,
            'retransmitFrames': retransmit,
            'acks': {'ok': len(ack_latency), 'duplicate': 0, 'error': 0,
                     'malformed': 0, 'noProgress': 0, 'abort': 0},
            'ackSamples': integrity,
            'ackEarlyInvalid': early_invalid,
            'ackEarlyUnsent': early_unsent,
            'ackLatency': {
                'count': len(ack_latency),
                'minUs': min(ack_latency) if ack_latency else None,
                'p50Us': nearest_rank(ack_latency, 0.50),
                'p95Us': nearest_rank(ack_latency, 0.95),
                'p99Us': nearest_rank(ack_latency, 0.99),
                'maxUs': max(ack_latency) if ack_latency else None,
            },
            'durable': {
                'events': len(durable),
                'finalOff': int(durable[-1].extra['off']) if durable else None,
            },
        },
        'gattWrites': {
            'calls': count('gatt_write'),
            'bytes': total_bytes('gatt_write'),
            'errors': errors('gatt_write'),
        },
        'discovers': {'calls': count('discover'), 'errors': errors('discover')},
        'platformWrites': {
            'calls': count('platform_write'),
            'bytes': total_bytes('platform_write'),
            'errors': errors('platform_write'),
        },
    }


def summary_line(summary):
    return 'OTA_LINK_STATS ' + json.dumps(summary, ensure_ascii=False, sort_keys=True)


def strict_block_text(mutate=None, extra_sample_lines=(), drop_summary=False,
                      summary_override=None):
    """真实样本行 + 独立重算摘要构成的严格契约观测块。

    [mutate] 形如 f(summary) -> None 的就地改写（摘要变异）；
    [extra_sample_lines] 追加到摘要之前的样本行（拖尾/混入用）；
    [drop_summary] 为真时不输出摘要行（未收口）；
    [summary_override] 直接替换摘要对象。
    """
    sample_lines, samples = real_block(0)
    summary = summary_override if summary_override is not None else \
        recompute_summary(samples)
    if mutate is not None:
        mutate(summary)
    lines = list(sample_lines) + list(extra_sample_lines)
    if not drop_summary:
        lines.append(summary_line(summary))
    return '\n'.join(lines)


# ---------------------------------------------------------------- 断言工具


def check_text(text, device_capture=False):
    groups, findings = L.analyse(text, device_capture=device_capture)
    return groups, findings


def code_pairs(findings):
    return sorted((f.code, f.severity) for f in findings)


def expect(findings, expected, context):
    """断言检出集合**恰好**为 expected（多报与漏报都算失败）。"""
    got = code_pairs(findings)
    want = sorted(expected)
    if got != want:
        detail = '\n'.join('    ' + str(f) for f in findings)
        raise AssertionError(
            '%s\n  期望检出: %s\n  实际检出: %s\n%s' % (context, want, got, detail))


def expect_one(findings, code, severity, context):
    expect(findings, [(code, severity)], context)


def no_findings(text, context, device_capture=False):
    _, findings = check_text(text, device_capture=device_capture)
    expect(findings, [], context)


def fatal_count(findings):
    return len([f for f in findings if f.severity == 'fatal'])


# ---------------------------------------------------------------- 正例控制


def test_fixture_is_verbatim_slice():
    """切片身份：274 行、末行为摘要、SHA-256 与 PROVENANCE 一致。"""
    import hashlib
    with open(FIXTURE, 'rb') as handle:
        raw = handle.read()
    assert raw.count(b'\n') == 274, '行数不符: %d' % raw.count(b'\n')
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == 'd482f9ed386a064146992585fdf93ab2738f1b785c2bdc2e910e0d81c37bf645', \
        '夹具字节已变（PROVENANCE.md 需同步）: %s' % digest
    assert raw.split(b'\n')[273].startswith(b'OTA_LINK_STATS'), '末行必须是摘要'


def test_fixture_blocks_are_single_instance_and_closed():
    """真实切片：4 个已收口块，两种模式下都无致命发现。"""
    text = '\n'.join(fixture_lines())
    groups, findings = check_text(text)
    assert len(groups) == 4, '观测块数不符: %d' % len(groups)
    for group in groups:
        assert group.summary is not None, '切片内不得有未收口块'
        assert len(L._clock_segments(group.samples)) == 1, '切片块应为单实例'
    assert fatal_count(findings) == 0, '真实切片不得有致命发现'
    codes = {f.code for f in findings}
    assert codes <= {'FIELD_ABSENT'}, '意外告警类别: %s' % sorted(codes)
    strict_groups, strict_findings = check_text(text, device_capture=True)
    assert len(strict_groups) == 4
    assert fatal_count(strict_findings) == 0, \
        '--device-capture 对单实例已收口块不得报致命（严格模式不是一律打红）'


def test_strict_contract_block_has_no_findings():
    """严格契约正例：真实样本 + 独立重算摘要 → 零发现（正向鉴别力控制）。"""
    no_findings(strict_block_text(), '严格契约块应在默认模式下零发现')
    no_findings(strict_block_text(), '严格契约块应在严格模式下零发现',
                device_capture=True)


def test_strict_block_counts_match_sample_lines():
    """独立重算摘要与样本行自洽（防止夹具自身写错导致负例失去意义）。"""
    _, samples = real_block(0)
    summary = recompute_summary(samples)
    assert summary['transfer']['segmentsUnique'] == 8, \
        '样本块形状已变: %r' % summary['transfer']['segmentsUnique']
    assert summary['transfer']['ackLatency']['count'] == 8
    assert summary['gattWrites']['calls'] == 11
    assert summary['transfer']['ackSamples'] == 'complete'
    assert summary['transfer']['elapsedUs'] == \
        summary['transfer']['endAckUs'] - summary['transfer']['startUs']


def test_legacy_fixture_absent_fields_are_declared():
    """整改前切片：缺字段必须逐项报 FIELD_ABSENT(warn)，不静默按 0 通过。"""
    _, findings = check_text('\n'.join(fixture_lines()))
    reported = {f.detail.split('（')[0].split('字段 ')[-1] for f in findings
                if f.code == 'FIELD_ABSENT'}
    assert reported == LEGACY_ABSENT_FIELDS, \
        '缺字段集合不符: %s' % sorted(reported)


# ---------------------------------------------------------------- 负例：缺失


def test_missing_sample_line_is_fatal():
    """日志缺失（摘要声明多于观测）→ COUNT_MISMATCH(fatal)。"""
    text = strict_block_text()
    sample_lines = text.splitlines()[:-1]
    trimmed = '\n'.join(sample_lines[:-1] + [text.splitlines()[-1]])
    _, findings = check_text(trimmed)
    assert fatal_count(findings) >= 1, '删掉一条样本后应报致命'
    assert ('COUNT_MISMATCH', 'fatal') in code_pairs(findings), \
        '应检出摘要声明多于日志观测: %s' % code_pairs(findings)


def test_dropped_summary_is_warn_then_fatal():
    """未收口块：默认 warn(SUMMARY_MISSING)，严格模式 fatal。"""
    text = strict_block_text(drop_summary=True)
    _, findings = check_text(text)
    expect_one(findings, 'SUMMARY_MISSING', 'warn', '默认模式未收口块只应告警')
    _, strict = check_text(text, device_capture=True)
    expect_one(strict, 'SUMMARY_MISSING', 'fatal', '严格模式未收口块应为致命')


# ---------------------------------------------------------------- 负例：混组


def test_wrong_label_is_fatal():
    """混组：摘要 label 与样本不符 → MIXED_LABEL(fatal)。"""
    text = strict_block_text(summary_override=recompute_summary(
        real_block(0)[1], label='probe'))
    _, findings = check_text(text)
    expect_one(findings, 'MIXED_LABEL', 'fatal', '样本与摘要 label 不符')


def test_sample_level_label_mixing_is_fatal():
    """混组：同块样本混用两个 label → MIXED_LABEL(fatal)。"""
    lines = strict_block_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('OTA_LINK_SAMPLE') and 'kind=gatt_write' in line:
            lines[i] = line.replace('label=upgrade', 'label=probe')
            break
    _, findings = check_text('\n'.join(lines))
    assert ('MIXED_LABEL', 'fatal') in code_pairs(findings), \
        '同块混用 label 应被检出: %s' % code_pairs(findings)


def test_attempt_number_rollback_is_fatal():
    """混组：attempts[].n 非严格递增 → MIXED_ATTEMPT(fatal)。"""
    def mutate(summary):
        summary['attempts'] = [{'n': 2, 'outcome': 'completed'},
                               {'n': 1, 'outcome': 'completed'}]
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'MIXED_ATTEMPT', 'fatal', 'attempts 序号回退')


# ------------------------------------------------------------ 负例：错摘要


def test_quantile_tamper_is_fatal():
    """错误摘要：分位数被改 → QUANTILE_MISMATCH(fatal)。"""
    def mutate(summary):
        summary['transfer']['ackLatency']['p99Us'] = \
            summary['transfer']['ackLatency']['p99Us'] + 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'QUANTILE_MISMATCH', 'fatal', 'p99 篡改')


def test_declared_count_inflation_is_fatal():
    """错误摘要：计数大于样本重算 → COUNT_MISMATCH(fatal)。"""
    def mutate(summary):
        summary['gattWrites']['calls'] += 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    assert ('COUNT_MISMATCH', 'fatal') in code_pairs(findings), \
        '计数虚高应被检出: %s' % code_pairs(findings)


def test_retransmit_derivation_tamper_is_fatal():
    """错误摘要：retransmitFrames 与发送总数/唯一段数不符 → 两处独立检出。

    该字段同时是「计数对照」键与「派生自洽」输入，故篡改会同时触发
    COUNT_MISMATCH（与样本重算不符）与 INTERNAL_INCONSISTENT（派生式不成立）；
    两处都必须在，缺一即说明某一层核对没跑。
    """
    def mutate(summary):
        summary['transfer']['retransmitFrames'] += 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect(findings, [('COUNT_MISMATCH', 'fatal'), ('INTERNAL_INCONSISTENT', 'fatal')],
           '重传帧数篡改应被计数与派生两层同时检出')


def test_elapsed_tamper_is_fatal():
    """错误摘要：elapsedUs 与 endAckUs-startUs 不符 → INTERNAL_INCONSISTENT。

    该核对与分位数同在一趟核对里执行（`_check_quantiles`），因此它与分位数
    用例的鉴别力来源相同。
    """
    def mutate(summary):
        summary['transfer']['elapsedUs'] += 10
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'INTERNAL_INCONSISTENT', 'fatal', '传输时长自洽性被破坏')


def test_integrity_declaration_tamper_is_fatal():
    """错误摘要：ackSamples 与样本重算不符 → INTEGRITY_MISMATCH(fatal)。"""
    def mutate(summary):
        summary['transfer']['ackSamples'] = 'partial:missing=1'
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'INTEGRITY_MISMATCH', 'fatal', '完整性声明篡改')


def test_durable_final_off_tamper_is_fatal():
    """错误摘要：durable.finalOff 不在样本序列中 → COUNT_MISMATCH(fatal)。"""
    def mutate(summary):
        summary['transfer']['durable']['finalOff'] += 128
    _, findings = check_text(strict_block_text(mutate=mutate))
    assert ('COUNT_MISMATCH', 'fatal') in code_pairs(findings), \
        'durable 末值不在样本序列: %s' % code_pairs(findings)


def test_bytes_tamper_is_fatal():
    """错误摘要：GATT 写字节数被改 → COUNT_MISMATCH(fatal)。"""
    def mutate(summary):
        summary['gattWrites']['bytes'] += 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    assert ('COUNT_MISMATCH', 'fatal') in code_pairs(findings), \
        '字节数篡改: %s' % code_pairs(findings)


def test_phase_reversed_is_fatal():
    """错误摘要：阶段结束早于开始 → PHASE_REVERSED(fatal)。"""
    def mutate(summary):
        start = summary['transfer']['startUs']
        summary['phases']['transfer'] = [start + 1000, start]
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'PHASE_REVERSED', 'fatal', '阶段区间倒置')


def test_bind_phase_tamper_is_fatal():
    """错误摘要：bind.phaseUs 与 phases.bind 不符 → INTERNAL_INCONSISTENT。"""
    def mutate(summary):
        summary['bind']['phaseUs'] += 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'INTERNAL_INCONSISTENT', 'fatal', 'bind 阶段时长不符')


# -------------------------------------------------------- 负例：时钟域错配


def test_clock_domain_mismatch_is_fatal():
    """时钟域错配：clock 非冻结域 → CLOCK_DOMAIN(fatal)。"""
    def mutate(summary):
        summary['clock'] = 'wall-clock-ms'
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'CLOCK_DOMAIN', 'fatal', '非冻结时钟域')


def test_unknown_schema_is_fatal():
    """schema 不在受支持集合 → SCHEMA_UNKNOWN(fatal)。"""
    def mutate(summary):
        summary['schema'] = 2
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'SCHEMA_UNKNOWN', 'fatal', '未知 schema')


def test_negative_us_is_fatal():
    """负 us（耗时或时间戳都不可能为负）→ CLOCK_NEGATIVE(fatal)。"""
    lines = strict_block_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('OTA_LINK_SAMPLE') and 'kind=ack_latency' in line:
            lines[i] = line.replace('us=', 'us=-', 1)
            break
    _, findings = check_text('\n'.join(lines))
    assert ('CLOCK_NEGATIVE', 'fatal') in code_pairs(findings), \
        '负 us 应被检出: %s' % code_pairs(findings)


def test_clock_rollback_is_multi_instance_then_fatal():
    """实例时钟回退：默认 MULTI_INSTANCE(warn)，严格模式 CLOCK_NONMONOTONIC(fatal)。

    构造：把第二个真实 upgrade 块（同 label、独立实例、Stopwatch 从较小值
    重新计时，见夹具块 2）的样本行接在块 1 样本之后、块 1 摘要之前——真实
    捕获中正是这个形状：前一个传输级实例未收口，样本连续落进同一缓冲区。
    样本行逐字节取自夹具，未改写；只有"拼接"这一动作是构造的。
    """
    second_lines, _ = real_block(2)
    text = strict_block_text(extra_sample_lines=second_lines)
    _, findings = check_text(text)
    assert ('MULTI_INSTANCE', 'warn') in code_pairs(findings), \
        '默认模式应报多实例段: %s' % code_pairs(findings)
    assert fatal_count(findings) == 0, \
        '默认模式的多实例段不得为致命: %s' % [str(f) for f in findings]
    _, strict = check_text(text, device_capture=True)
    assert ('CLOCK_NONMONOTONIC', 'fatal') in code_pairs(strict), \
        '严格模式应报时钟回退: %s' % code_pairs(strict)


# ------------------------------------------------------------ 负例：结构


def test_bad_json_is_fatal():
    """摘要 JSON 破损 → BAD_JSON(fatal)，且同块仍完成其余解析。"""
    lines = strict_block_text().splitlines()
    lines[-1] = lines[-1][:-4]  # 截断 JSON 尾部
    _, findings = check_text('\n'.join(lines))
    expect_one(findings, 'BAD_JSON', 'fatal', '摘要 JSON 截断')


def test_malformed_sample_is_fatal():
    """样本 us 非整数 → MALFORMED_SAMPLE(fatal)。"""
    lines = strict_block_text().splitlines()
    for i, line in enumerate(lines):
        if line.startswith('OTA_LINK_SAMPLE'):
            lines[i] = line.replace('us=', 'us=x', 1)
            break
    _, findings = check_text('\n'.join(lines))
    assert any(code == 'MALFORMED_SAMPLE' and sev == 'fatal'
               for code, sev in code_pairs(findings)), \
        '畸形样本行应被检出: %s' % code_pairs(findings)


def test_unknown_kind_is_fatal():
    """未知样本 kind → UNKNOWN_KIND(fatal)（解析器拒绝猜测归类）。"""
    lines = strict_block_text().splitlines()
    for i, line in enumerate(lines):
        if 'kind=gatt_write' in line:
            lines[i] = line.replace('kind=gatt_write', 'kind=write_packet')
            break
    _, findings = check_text('\n'.join(lines))
    assert ('UNKNOWN_KIND', 'fatal') in code_pairs(findings), \
        '未知 kind 应被检出: %s' % code_pairs(findings)


def test_missing_required_object_is_fatal():
    """摘要缺必需对象 → SCHEMA_MISSING(fatal)，且其下三个字段同时报缺失。"""
    lines = strict_block_text().splitlines()
    summary = json.loads(lines[-1][len('OTA_LINK_STATS '):])
    del summary['gattWrites']
    lines[-1] = 'OTA_LINK_STATS ' + json.dumps(summary, ensure_ascii=False)
    _, findings = check_text('\n'.join(lines))
    expect(findings, [('SCHEMA_MISSING', 'fatal')] + [('FIELD_ABSENT', 'warn')] * 3,
           '缺少 gattWrites 对象（其下 calls/bytes/errors 三个字段同时缺失）')


def test_durable_final_off_behind_last_sample_is_warn():
    """摘要后 durable 继续推进：声明的 finalOff 是更早的样本 → STRAGGLER(warn)。

    这是真实形状（摘要打印后同实例继续 running）：声明值仍在日志序列中、
    只是不是末条，属"观测多于声明"，不得判为致命。
    """
    _, samples = real_block(0)
    durable = [s for s in samples if s.kind == 'durable']
    assert len(durable) >= 2, '该块需至少两条 durable 样本才能构造此形状'
    first_off = int(durable[0].extra['off'])
    last_off = int(durable[-1].extra['off'])
    assert first_off != last_off, '两条 durable 的 off 必须不同'

    def mutate(summary):
        summary['transfer']['durable']['finalOff'] = first_off
    _, findings = check_text(strict_block_text(mutate=mutate))
    assert ('STRAGGLER', 'warn') in code_pairs(findings), \
        '应报 durable 拖尾而非致命: %s' % code_pairs(findings)
    assert fatal_count(findings) == 0, \
        'durable 推进不得判红: %s' % [str(f) for f in findings]


def test_absent_field_is_warn_not_fatal():
    """字段缺失是可申报的告警（FIELD_ABSENT），不是致命。"""
    def mutate(summary):
        del summary['transfer']['ackEarlyInvalid']
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'FIELD_ABSENT', 'warn', '缺一个字段只应告警')


def test_straggler_sample_is_warn_not_fatal():
    """摘要后拖尾样本（同实例继续写入）→ STRAGGLER(warn)，不得误判为致命。"""
    sample_lines, samples = real_block(0)
    extra = [line for line in sample_lines if 'kind=gatt_write' in line][:1]
    text = '\n'.join(sample_lines + extra + [summary_line(recompute_summary(samples))])
    _, findings = check_text(text)
    codes = {f.code for f in findings}
    assert 'STRAGGLER' in codes, '拖尾样本应报 STRAGGLER: %s' % code_pairs(findings)
    assert fatal_count(findings) == 0, '拖尾样本不得为致命: %s' % code_pairs(findings)


# ------------------------------------------------------------ 分位数口径


def test_nearest_rank_semantics():
    """nearest-rank：升序第 ceil(q*N) 个，不插值；N=0 → null。"""
    assert L._nearest_rank([], 0.99) is None
    assert L._nearest_rank([7], 0.99) == 7
    assert L._nearest_rank([1, 2, 3, 4, 5], 0.50) == 3          # ceil(2.5)=3
    assert L._nearest_rank([1, 2, 3, 4, 5], 0.99) == 5
    assert L._nearest_rank(list(range(1, 101)), 0.99) == 99      # ceil(99.0)=99
    assert L._nearest_rank([5, 1, 3], 0.95) == 5                 # 排序后取最大
    assert nearest_rank([1, 2, 3, 4, 5], 0.5) == L._nearest_rank([1, 2, 3, 4, 5], 0.5)


def test_quantile_check_runs_and_catches_shift():
    """分位数核对确实执行：整体右移 p95 必被检出（非空转）。"""
    def mutate(summary):
        summary['transfer']['ackLatency']['p95Us'] += 5
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'QUANTILE_MISMATCH', 'fatal', 'p95 位移')


# ---------------------------------------------------------------- CLI 契约


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = L.main(argv)
    return code, out.getvalue(), err.getvalue()


def write_temp(name, text):
    path = os.path.join(HERE, name)
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    return path


def test_cli_exit_codes_and_json():
    """CLI：正例退出 0、致命退出 1、文件缺失退出 2、--json 结论形状完整。"""
    ok_path = write_temp('_tmp_ok.log', strict_block_text())
    bad_path = write_temp('_tmp_bad.log', strict_block_text(mutate=lambda s: s.update(
        {'schema': 2})))
    try:
        code, out, _ = run_main(['--log', ok_path, '--json'])
        assert code == 0, '正例退出码应为 0，实际 %d' % code
        payload = json.loads(out)
        for key in ('log', 'groups', 'samples', 'findings', 'report'):
            assert key in payload, '--json 缺字段 %s' % key
        for key in ('runs', 'excludedRuns', 'ackLatency', 'retransmitRate',
                    'strictFieldsComplete', 'unclosedBlocks'):
            assert key in payload['report'], '合并报告缺字段 %s' % key

        code, out, _ = run_main(['--log', bad_path])
        assert code == 1, '致命发现应退出 1，实际 %d' % code
        assert 'FATAL' in out, '文本输出应含致命标记'

        code, _, err = run_main(['--log', os.path.join(HERE, '不存在.log')])
        assert code == 2, '读取失败应退出 2，实际 %d' % code
        assert '读取失败' in err
    finally:
        for path in (ok_path, bad_path):
            if os.path.exists(path):
                os.remove(path)


def test_cli_on_real_fixture_is_green():
    """真实切片经 CLI：默认与严格模式都退出 0（无致命）。"""
    for extra in ([], ['--device-capture']):
        code, out, _ = run_main(['--log', FIXTURE] + extra)
        assert code == 0, '真实切片退出码应为 0（%s），实际 %d' % (extra, code)
        assert '致命发现 0 项' in out, '输出应报告 0 致命（%s）' % extra


def test_cli_aggregate_merges_only_clean_runs():
    """合并统计只纳入 ok 且无致命的块，并如实标注缺口与未收口块。"""
    code, out, _ = run_main(['--log', FIXTURE, '--label', 'upgrade', '--json'])
    assert code == 0
    report = json.loads(out)['report']
    assert report['runs'] == 2, 'upgrade 块数不符: %r' % report['runs']
    assert report['excludedRuns'] == 0, '本切片无应排除块: %r' % report['excludedRuns']
    assert report['ackLatency']['count'] == 16, \
        '合并样本数不符: %r' % report['ackLatency']['count']
    assert report['strictFieldsComplete'] is False, \
        '整改前切片必须如实标注字段不完整'
    assert report['runsWithAbsentFields'] == 2


# ------------------------------------------------- 可选：整份真实捕获


def test_optional_full_capture():
    """整份真实捕获（不入库）：0 致命 + 逐宿主检出计数一致；不在场则 SKIP。"""
    captures = optional_captures()
    if not captures:
        print('      SKIP 外部捕获不在场（主 worktree .cache/%s/<宿主>/*/logs/'
              'tests.log 不存在或 git 不可用），本项不参与判定' % CAPTURE_RUN)
        return
    seen = set()
    for host, path in captures:
        expect = CAPTURE_EXPECTATIONS[host]
        with open(path, 'rb') as handle:
            text = handle.read().decode('utf-8', errors='replace')
        groups, findings = check_text(text)
        fatal = [f for f in findings if f.severity == 'fatal']
        assert not fatal, '%s 整份捕获应 0 致命: %s' % (
            host, [str(f) for f in fatal])
        counts = {}
        for finding in findings:
            counts[finding.code] = counts.get(finding.code, 0) + 1
        assert counts == expect['codes'], \
            '%s 告警计数与冻结形状不符:\n  实际 %r\n  期望 %r' % (
                host, counts, expect['codes'])
        assert len(groups) == expect['blocks'], \
            '%s 观测块数不符: %r' % (host, len(groups))
        samples = sum(len(g.samples) for g in groups)
        assert samples == expect['samples'], \
            '%s 样本数不符: %r' % (host, samples)

        report = L.aggregate(groups, 'upgrade')
        observed = dict(report)
        observed['ackLatencyCount'] = report['ackLatency']['count']
        for key, value in expect['report'].items():
            assert observed[key] == value, \
                '%s 合并报告 %s 不符: 实际 %r 期望 %r' % (
                    host, key, observed[key], value)
        seen.add(host)
        print('      整份捕获 %s: 块=%d 样本=%d 致命=0 告警=%s '
              'runs=%d excluded=%d unclosed=%d/%d'
              % (host, len(groups), samples, counts, report['runs'],
                 report['excludedRuns'], report['unclosedBlocks'],
                 report['unclosedSamples']))
    missing = sorted(set(CAPTURE_EXPECTATIONS) - seen)
    if missing:
        print('      SKIP 未覆盖宿主（证据不在场）: %s' % missing)


# 核对函数 → 必须因其失效而失败的负例（鉴别力配对表）。
# 新增负例时必须在此登记，否则该负例不参与鉴别力检查。
DISCRIMINATION_PAIRS = {
    '_check_quantiles': [
        'test_quantile_tamper_is_fatal',
        'test_quantile_check_runs_and_catches_shift',
        'test_elapsed_tamper_is_fatal',
    ],
    '_check_integrity': ['test_integrity_declaration_tamper_is_fatal'],
    '_check_counters': [
        'test_missing_sample_line_is_fatal',
        'test_declared_count_inflation_is_fatal',
        'test_bytes_tamper_is_fatal',
        'test_durable_final_off_tamper_is_fatal',
        'test_durable_final_off_behind_last_sample_is_warn',
        'test_absent_field_is_warn_not_fatal',
        'test_straggler_sample_is_warn_not_fatal',
    ],
    '_check_clock': [
        'test_negative_us_is_fatal',
        'test_clock_rollback_is_multi_instance_then_fatal',
    ],
    '_clock_segments': ['test_clock_rollback_is_multi_instance_then_fatal'],
    '_check_structure': [
        'test_clock_domain_mismatch_is_fatal',
        'test_unknown_schema_is_fatal',
        'test_missing_required_object_is_fatal',
    ],
    '_check_derived': [
        'test_retransmit_derivation_tamper_is_fatal',
        'test_phase_reversed_is_fatal',
        'test_bind_phase_tamper_is_fatal',
    ],
    '_check_attempts': ['test_attempt_number_rollback_is_fatal'],
    '_check_labels': [
        'test_wrong_label_is_fatal',
        'test_sample_level_label_mixing_is_fatal',
    ],
    'parse_sample': [
        'test_malformed_sample_is_fatal',
        'test_unknown_kind_is_fatal',
    ],
}


def test_negative_cases_discriminate_on_check_removal():
    """逐项置空解析器的核对函数，对应负例必须失败——防"零鉴别力"。

    夹具字面量失配或核对未接线时，负例仍可能因为别的原因通过（或反过来
    恒过），此时整套负例是空的。这里把每条检出对应的核对函数临时置空，
    要求其负例**确实失败**；置空后仍通过即说明该负例没在核对它声称的东西。
    改动只在内存中进行，finally 恢复原函数。
    """
    checked = 0
    module = sys.modules[__name__]
    for name, tests in sorted(DISCRIMINATION_PAIRS.items()):
        original = getattr(L, name)
        try:
            setattr(L, name, lambda *args, **kwargs: None)
            for test_name in tests:
                try:
                    getattr(module, test_name)()
                except Exception:
                    checked += 1
                else:
                    raise AssertionError(
                        '置空 %s 后 %s 仍然通过：该负例没有核对它声称的检出'
                        % (name, test_name))
        finally:
            setattr(L, name, original)
    assert checked >= 20, '鉴别力配对过少（%d），覆盖不足' % checked


TESTS = [
    ('夹具：逐字节切片身份与 SHA-256', test_fixture_is_verbatim_slice),
    ('正例：真实切片单实例已收口（默认+严格模式）',
     test_fixture_blocks_are_single_instance_and_closed),
    ('正例：严格契约块零发现（默认+严格模式）',
     test_strict_contract_block_has_no_findings),
    ('正例：独立重算摘要与样本行自洽', test_strict_block_counts_match_sample_lines),
    ('正例：整改前缺字段逐项申报', test_legacy_fixture_absent_fields_are_declared),
    ('负例·日志缺失：删样本行 → COUNT_MISMATCH', test_missing_sample_line_is_fatal),
    ('负例·未收口：warn → 严格模式 fatal', test_dropped_summary_is_warn_then_fatal),
    ('负例·混组：摘要 label 不符 → MIXED_LABEL', test_wrong_label_is_fatal),
    ('负例·混组：样本 label 混用 → MIXED_LABEL',
     test_sample_level_label_mixing_is_fatal),
    ('负例·混组：attempts 序号回退 → MIXED_ATTEMPT',
     test_attempt_number_rollback_is_fatal),
    ('负例·错摘要：分位数篡改 → QUANTILE_MISMATCH', test_quantile_tamper_is_fatal),
    ('负例·错摘要：计数虚高 → COUNT_MISMATCH', test_declared_count_inflation_is_fatal),
    ('负例·错摘要：重传派生量篡改 → INTERNAL_INCONSISTENT',
     test_retransmit_derivation_tamper_is_fatal),
    ('负例·错摘要：传输时长篡改 → INTERNAL_INCONSISTENT', test_elapsed_tamper_is_fatal),
    ('负例·错摘要：完整性声明篡改 → INTEGRITY_MISMATCH',
     test_integrity_declaration_tamper_is_fatal),
    ('负例·错摘要：durable 末值不在序列 → COUNT_MISMATCH',
     test_durable_final_off_tamper_is_fatal),
    ('负例·错摘要：durable 末值落后于样本 → STRAGGLER(warn)',
     test_durable_final_off_behind_last_sample_is_warn),
    ('负例·错摘要：字节数篡改 → COUNT_MISMATCH', test_bytes_tamper_is_fatal),
    ('负例·错摘要：阶段区间倒置 → PHASE_REVERSED', test_phase_reversed_is_fatal),
    ('负例·错摘要：bind 阶段时长不符 → INTERNAL_INCONSISTENT',
     test_bind_phase_tamper_is_fatal),
    ('负例·时钟域：非冻结域 → CLOCK_DOMAIN', test_clock_domain_mismatch_is_fatal),
    ('负例·时钟域：未知 schema → SCHEMA_UNKNOWN', test_unknown_schema_is_fatal),
    ('负例·时钟域：负 us → CLOCK_NEGATIVE', test_negative_us_is_fatal),
    ('负例·时钟域：实例回退 → MULTI_INSTANCE / CLOCK_NONMONOTONIC',
     test_clock_rollback_is_multi_instance_then_fatal),
    ('负例·结构：摘要 JSON 破损 → BAD_JSON', test_bad_json_is_fatal),
    ('负例·结构：样本畸形 → MALFORMED_SAMPLE', test_malformed_sample_is_fatal),
    ('负例·结构：未知 kind → UNKNOWN_KIND', test_unknown_kind_is_fatal),
    ('负例·结构：缺必需对象 → SCHEMA_MISSING', test_missing_required_object_is_fatal),
    ('负例·字段缺失只告警 → FIELD_ABSENT(warn)', test_absent_field_is_warn_not_fatal),
    ('负例·拖尾样本只告警 → STRAGGLER(warn)', test_straggler_sample_is_warn_not_fatal),
    ('口径：nearest-rank 与冻结语义一致', test_nearest_rank_semantics),
    ('口径：分位数核对确实执行（非空转）', test_quantile_check_runs_and_catches_shift),
    ('CLI：退出码与 --json 形状', test_cli_exit_codes_and_json),
    ('CLI：真实切片默认/严格模式退出 0', test_cli_on_real_fixture_is_green),
    ('CLI：合并统计只纳入 clean run', test_cli_aggregate_merges_only_clean_runs),
    ('鉴别力：置空核对函数后负例必须失败',
     test_negative_cases_discriminate_on_check_removal),
    ('可选：整份真实捕获 0 致命（无则 SKIP）', test_optional_full_capture),
]


def main():
    failed = []
    for name, fn in TESTS:
        try:
            fn()
            print('PASS  %s' % name)
        except Exception:
            failed.append(name)
            print('FAIL  %s' % name)
            traceback.print_exc()
    print('---- selftest 总计 %d 项，失败 %d 项 ----' % (len(TESTS), len(failed)))
    if failed:
        for name in failed:
            print('FAILED: %s' % name)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
