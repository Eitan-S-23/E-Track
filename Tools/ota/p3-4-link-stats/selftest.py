#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-4 链路观测日志解析器自测（`link_stats.py` 配套正例控制与负例）。

用途：证明 `link_stats.py` 的检出**有鉴别力**，且整改批
（`docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17.md`）引入的新语义
既检出新缺陷、又不在真实数据上误报。覆盖矩阵：

1. **正例控制（真实数据）**：`fixtures/round6-ubuntu-head.log` 逐字节切片
   （274 行，含噪声行与 4 个已收口单实例块）在默认与 `--device-capture`
   两种模式下都必须 **0 致命、0 告警误报类别**（除 `FIELD_ABSENT`：该轮
   发射端早于整改批新增字段，缺字段是真实的）。这一项同时证明严格模式不是
   "一律打红"；
2. **严格契约正例**：真实样本行 + 由本文件**独立重算**的当前契约摘要
   （计数、分位数、阶段分位数、完整性、时长全部由样本推出，非复用解析器
   实现）→ **0 发现**（无致命也无告警）；
3. **负例（每项一个可检出缺陷）**，按发现 ID 分组：
   * P34-P01 实验身份：设备 / MTU / 写模式不同的块不得合成同一个统计；侧车
     `--group` 声明与原始日志 SHA-256 绑定，未声明即非门槛可用；
   * P34-P02 归属与洁净：解析期致命项归属到所在块、严格模式结论不被重算洗白、
     污染轮进入 `excluded[]` 并保留行号与理由；
   * P34-P03 偏移集合：重复首发 / 重复确认 / 孤儿重传 / 无段确认被检出，而
     重传、多段共用确认、resume 前缀等合法形状不被误报；
   * P34-P04 空捕获与非法收口：空文件、纯噪声、null/非对象/破损摘要都不是
     合法收口，也不能清除已有样本的错误归属；
   * P34-P05 类型与范围：`elapsed<=0` 的成功传输非法、布尔不冒充整数、
     非法类型给结构化结论而非 traceback、阶段分位数与 `getInfo.totalUs`
     逐项重算、绑定字段缺失不得声称契约完整；
   * P34-P06 早到 ACK：发射端合法输出序不报时钟回退，但无关联旧时间重放与
     跨实例挪用必须报致命；
   * P34-P07 鉴别力：逐项施加**保持类型**的变异，要求负例抛出**恰为
     `AssertionError`**，并在同一变异下正例仍然通过（证明失败来自目标判据
     而非夹具损坏）。
4. **分位数口径**：nearest-rank（升序第 ceil(q*N) 个，不插值，N=0 → null）
   与冻结口径一致，含 N=1、整除边界、奇数样本；
5. **CLI 契约**：`--json` 结论形状、致命存在时退出码 1、读取失败退出码 2、
   真实切片默认/严格模式退出码 0；
6. **整份真实捕获（可选）**：主 worktree `.cache/` 下的两份 CI 捕获，若在场
   则断言 0 致命与逐宿主形状一致；不在场则如实 SKIP（外部证据不入库）。

样本行的真实性：负例用的样本行全部取自 `fixtures/` 里的真实切片；只有
"多实例同块""早到 ACK""侧车身份"的拼接方式与摘要字段是构造的，构造方式
在各用例内注明。P34-P06 的早到 ACK 形状来自发射端源码语义
（`ota_link_stats.dart` 的 `_earlyConfirmUs` / `_onSegmentFirstSend`），
**不是**执行过的 Dart 或设备测量，不得当作真机证据。

运行：python selftest.py（仅标准库）。退出码 0 表示全部通过。
"""

import contextlib
import hashlib
import io
import json
import math
import os
import re
import shutil
import sys
import glob
import subprocess
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import link_stats as L  # noqa: E402  （同目录解析器，为其编写自测）

FIXTURE = os.path.join(HERE, 'fixtures', 'round6-ubuntu-head.log')

# 整份真实捕获（不入库的 CI 证据，保存在**主 worktree** 的 .cache/ 下）。
# 两份运行：35034258547 是整改前发射端（缺整改批新增字段），35094204310 是
# 含整改批字段的发射端（`strictFieldsComplete=True`）。前者见证旧版兼容路径，
# 后者见证"字段齐全时完整性标记才为真"。
CAPTURE_RUNS = ('ci-35034258547', 'ci-35094204310')
CAPTURE_EXPECTATIONS = {
    ('ci-35034258547', 'ubuntu'): {
        'blocks': 27,
        'samples': 801,
        'codes': {'FIELD_ABSENT': 182, 'STRAGGLER': 12, 'SUMMARY_MISSING': 1},
        'report': {'runs': 6, 'excludedRuns': 13, 'unclosedBlocks': 1,
                   'unclosedSamples': 434, 'segmentsUnique': 48,
                   'ackLatencyCount': 48, 'strictFieldsComplete': False,
                   'retransmitFrames': 0},
    },
    ('ci-35034258547', 'windows'): {
        'blocks': 27,
        'samples': 821,
        'codes': {'FIELD_ABSENT': 189, 'MULTI_INSTANCE': 1, 'STRAGGLER': 24,
                  'DUPLICATE_SEGMENT_OFFSET': 2, 'DUPLICATE_ACK_OFFSET': 2},
        'report': {'runs': 6, 'excludedRuns': 14, 'unclosedBlocks': 0,
                   'unclosedSamples': 0, 'segmentsUnique': 48,
                   'ackLatencyCount': 48, 'strictFieldsComplete': False,
                   'retransmitFrames': 0},
    },
    ('ci-35094204310', 'ubuntu'): {
        'blocks': 43,
        'samples': 443,
        'codes': {'STRAGGLER': 12, 'SUMMARY_MISSING': 1},
        'report': {'runs': 6, 'excludedRuns': 12, 'unclosedBlocks': 1,
                   'unclosedSamples': 85, 'segmentsUnique': 48,
                   'ackLatencyCount': 48, 'strictFieldsComplete': True,
                   'retransmitFrames': 0},
    },
    ('ci-35094204310', 'windows'): {
        'blocks': 43,
        'samples': 448,
        'codes': {'MULTI_INSTANCE': 1, 'STRAGGLER': 29, 'SUMMARY_MISSING': 1},
        'report': {'runs': 5, 'excludedRuns': 13, 'unclosedBlocks': 1,
                   'unclosedSamples': 6, 'segmentsUnique': 40,
                   'ackLatencyCount': 40, 'strictFieldsComplete': True,
                   'retransmitFrames': 0},
    },
}

# 整改前发射端缺失的字段（该轮日志合法缺失，见 fixtures/PROVENANCE.md）。
# 整改批把 `bind.writeMode`/`bind.mtuSource` 纳入必需字段：它们决定写模式与
# MTU 来源，缺了就无法把观测归入同一实验身份，故一并申报。
LEGACY_ABSENT_FIELDS = frozenset([
    'bind.writeMode',
    'bind.mtuSource',
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
    """返回 [(运行, 宿主, 整份 tests.log 路径), ...]；不在场则为空列表。"""
    root = main_worktree_root()
    if root is None:
        return []
    found = []
    for run in CAPTURE_RUNS:
        for key in sorted(CAPTURE_EXPECTATIONS):
            if key[0] != run:
                continue
            pattern = os.path.join(root, '.cache', run, key[1], '*',
                                   'logs', 'tests.log')
            found.extend((run, key[1], path) for path in sorted(glob.glob(pattern)))
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


def quantiles(values):
    return {
        'minUs': min(values) if values else None,
        'p50Us': nearest_rank(values, 0.50),
        'p95Us': nearest_rank(values, 0.95),
        'maxUs': max(values) if values else None,
    }


def recompute_summary(samples, label='upgrade', device='AA:BB'):
    """按当前契约从样本行独立重算摘要（字段齐全，供严格正例使用）。

    计数、分位数、阶段分位数、完整性与时长字段全部由样本推出；`bind.*` 与
    `phases` 的取值样本无法决定（无对应样本种类），此处给出自洽的固定值，仅为
    让"字段齐全"这一路径可被完整核对，不代表真实绑定观测。
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
    timestamps = [s.us for s in samples if s.kind in L.EVENT_TIME_KINDS]
    start_us = min(timestamps) if timestamps else None
    end_us = max(timestamps) if timestamps else None

    missing = first_send - len(ack_latency)
    parts = []
    if missing > 0:
        parts.append('missing=%d' % missing)
    if early_invalid > 0:
        parts.append('early=%d' % early_invalid)
    integrity = 'complete' if not parts else 'partial:%s' % ','.join(parts)

    gatt = quantiles([s.us for s in kinds.get('gatt_write', [])])
    discover = quantiles([s.us for s in kinds.get('discover', [])])
    platform = quantiles([s.us for s in kinds.get('platform_write', [])])

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
            'minUs': gatt['minUs'], 'p50Us': gatt['p50Us'],
            'p95Us': gatt['p95Us'], 'maxUs': gatt['maxUs'],
        },
        'discovers': {
            'calls': count('discover'), 'errors': errors('discover'),
            'minUs': discover['minUs'], 'p50Us': discover['p50Us'],
            'p95Us': discover['p95Us'], 'maxUs': discover['maxUs'],
        },
        'platformWrites': {
            'calls': count('platform_write'),
            'bytes': total_bytes('platform_write'),
            'errors': errors('platform_write'),
            'minUs': platform['minUs'], 'p50Us': platform['p50Us'],
            'p95Us': platform['p95Us'], 'maxUs': platform['maxUs'],
        },
    }


def summary_line(summary):
    return 'OTA_LINK_STATS ' + json.dumps(summary, ensure_ascii=False, sort_keys=True)


def parse_lines(lines):
    """按解析器口径把样本行解析为样本对象（用于独立重算）。"""
    parsed = [L.parse_sample(line, index + 1, [])
              for index, line in enumerate(lines)]
    return [sample for sample in parsed if sample is not None]


def block_text(lines, mutate=None, drop_summary=False, summary_override=None):
    """样本行 + 独立重算摘要构成的观测块（通用构造）。

    [mutate] 形如 f(summary) -> None 的就地改写（摘要变异）；
    [drop_summary] 为真时不输出摘要行（未收口）；
    [summary_override] 直接替换摘要对象。
    """
    summary = summary_override if summary_override is not None else \
        recompute_summary(parse_lines(lines))
    if mutate is not None:
        mutate(summary)
    out = list(lines)
    if not drop_summary:
        out.append(summary_line(summary))
    return '\n'.join(out)


def strict_block_text(mutate=None, extra_sample_lines=(), drop_summary=False,
                      summary_override=None):
    """以夹具中首个真实 upgrade 块的样本行为基准的严格契约观测块。"""
    sample_lines, _ = real_block(0)
    return block_text(list(sample_lines) + list(extra_sample_lines), mutate=mutate,
                      drop_summary=drop_summary,
                      summary_override=summary_override)


# 合成回退块：2 段，第二段的首发时刻早于第一段（真实时钟回退，非重放语义）。
ROLLBACK_LINES = [
    'OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=100 off=0 len=128',
    'OTA_LINK_SAMPLE label=upgrade kind=ack_latency us=10 off=0',
    'OTA_LINK_SAMPLE label=upgrade kind=durable us=120 off=128',
    'OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=50 off=128 len=128',
    'OTA_LINK_SAMPLE label=upgrade kind=ack_latency us=20 off=128',
    'OTA_LINK_SAMPLE label=upgrade kind=durable us=60 off=256',
]


# -------------------------------------------------- 早到 ACK 形状（构造）

# 发射端合法输出序（源码语义，非执行过的 Dart）：
# `recordAckConfirm()` 先把未登记首发的确认记入 `_earlyConfirmUs[off]` 并打印
# `ack_early(us=到达时刻)`；随后的 `_onSegmentFirstSend()` 取出该时刻打印
# `ack_early_invalid(us=同一个到达时刻)`，再打印 `segment_first_send(us=当前)`。
EMITTER_EARLY_LINES = [
    'OTA_LINK_SAMPLE label=upgrade kind=ack_early us=10 off=0',
    'OTA_LINK_SAMPLE label=upgrade kind=durable us=11 off=128',
    'OTA_LINK_SAMPLE label=upgrade kind=ack_early_invalid us=10 off=0',
    'OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=20 off=0 len=128',
]


def emitter_early_summary(lines=None):
    """与给定发射端样本行自洽的摘要（由样本行独立重算，不手填数字）。

    该实例只覆盖 1 段、0 个确认，另有 1 条早到确认未被采样（resume 前缀），
    因此 `ackSamples` 由重算自然落为 `partial:missing=1,early=1`，不得当作
    完整测量。重算同时给出阶段分位数的空值形态，无需另行手填。
    """
    samples = parse_lines(EMITTER_EARLY_LINES if lines is None else lines)
    return recompute_summary(samples)


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


def fatalities(findings):
    return sorted({f.code for f in findings if f.severity == 'fatal'})


def aggregate_of(text, label='upgrade', device_capture=False, group_identity=None,
                 identity_findings=()):
    """与 `main()` 同构的合并入口：把本轮**全部**检出交给合并判定。

    门槛资格必须消费采集轮次的完整校验结论（`capture_findings`），否则
    "致命项落在别的块上"会被读成门槛可用（P34-PR2-01）。
    """
    groups, findings = check_text(text, device_capture=device_capture)
    report, report_findings = L.aggregate(
        groups, label, group_identity=group_identity,
        identity_findings=identity_findings, capture_findings=findings)
    return report, findings + report_findings


# ------------------------------------------------------------ 临时文件管理

_TEMP_FILES = []
_TEMP_DIRS = []


def temp_file(name, text):
    """在解析器目录内建临时文件。独占创建：已存在即失败，绝不覆盖同名文件。"""
    assert name.startswith('_tmp_'), '临时文件必须用 _tmp_ 前缀：%s' % name
    path = os.path.join(HERE, name)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise
    _TEMP_FILES.append(path)
    return path


def drop_temp(path):
    if path in _TEMP_FILES:
        _TEMP_FILES.remove(path)
    if os.path.exists(path):
        os.remove(path)


def cleanup_temp_files():
    """删除本进程创建的全部临时文件与目录；返回删除清单。"""
    removed = []
    for path in list(_TEMP_DIRS):
        drop_temp_dir(path)
        removed.append(path)
    for path in list(_TEMP_FILES):
        drop_temp(path)
        removed.append(path)
    return removed


def leftover_temp_files():
    return sorted(glob.glob(os.path.join(HERE, '_tmp_*')))


def temp_dir(name):
    """解析器目录内的临时子目录：同名文件来源区分用例需要"两份都写盘"。"""
    assert name.startswith('_tmp_'), '临时目录必须用 _tmp_ 前缀：%s' % name
    path = os.path.join(HERE, name)
    os.mkdir(path)  # 已存在即失败，绝不覆盖同名目录
    _TEMP_DIRS.append(path)
    return path


def temp_tree_file(directory, name, text):
    """在临时子目录内写文件（独占创建，绝不覆盖）。"""
    path = os.path.join(directory, name)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    return path


def drop_temp_dir(path):
    if path in _TEMP_DIRS:
        _TEMP_DIRS.remove(path)
    if os.path.isdir(path):
        shutil.rmtree(path)


def sidecar(text, name='_tmp_group.json'):
    return temp_file(name, text)


# ---------------------------------------------------------------- 正例控制


def test_fixture_is_verbatim_slice():
    """切片身份：274 行、末行为摘要、SHA-256 与 PROVENANCE 一致。"""
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
    _, strict = check_text('\n'.join(fixture_lines()), device_capture=True)
    assert fatal_count(strict) == 0, '缺字段是告警，不得在严格模式下变成致命'


# ------------------------------------------------- P34-P01 实验身份与合并资格


def mixed_block(mutate):
    """同 label、两份摘要但身份参数不同的两块（第二块按 [mutate] 改写）。"""
    other = recompute_summary(real_block(0)[1])
    mutate(other)
    return strict_block_text() + '\n' + strict_block_text(summary_override=other)


def test_mixed_devices_are_not_merged():
    """设备不同 → 拆分为独立输入组，不产出跨组混合统计。"""
    report, findings = aggregate_of(mixed_block(
        lambda s: s.update({'device': 'CC:DD'})))
    assert report['runs'] == 0 and report['ackLatency']['count'] == 0, \
        '跨设备不得合并: %r' % report['ackLatency']
    assert len(report['groups']) == 2, '应按观测签名拆成 2 组'
    assert 'GROUP_IDENTITY_CONFLICT' in {f.code for f in findings}, \
        '应报身份冲突: %s' % [str(f) for f in findings]
    assert report['eligibleForThreshold'] is False


def test_mixed_mtu_is_not_merged():
    """MTU 不同 → 不得合成同一个 P99（PERFORMANCE 要求逐项绑定）。"""
    report, _ = aggregate_of(mixed_block(
        lambda s: s['bind'].update({'mtuChunkBytes': 20})))
    assert report['runs'] == 0, '跨 MTU 不得合并: %r' % report['runs']
    assert len(report['groups']) == 2
    assert {g['signature']['bind.mtuChunkBytes'] for g in report['groups']} == {20, 244}


def test_mixed_write_modes_are_not_merged():
    """写模式不同 → 不得合并（with/withoutResponse 的链路行为不同）。"""
    report, _ = aggregate_of(mixed_block(
        lambda s: s['bind'].update({'writeMode': 'withResponse'})))
    assert report['runs'] == 0, '跨写模式不得合并: %r' % report['runs']
    assert len(report['groups']) == 2


def test_unmerged_signature_keeps_per_group_statistics():
    """拆分后各组仍保留自己的可诊断统计（不是把数据丢掉）。"""
    report, _ = aggregate_of(mixed_block(
        lambda s: s['bind'].update({'mtuChunkBytes': 20})))
    for entry in report['groups']:
        assert entry['runs'] == 1, '每组应各自统计: %r' % entry
        assert entry['ackLatency']['count'] == 8, \
            '每组的样本数应保留: %r' % entry['ackLatency']


def identity_payload(sha, name='tests.log', **overrides):
    identity = {
        'device': 'AA:BB', 'mtuChunkBytes': 244, 'mtuRequested': 247,
        'writeMode': 'withoutResponse', 'baud': 921600, 'timeoutMs': 3000,
        'maxRetries': 3, 'packageSha256': 'a' * 64, 'packageBytes': 262144,
        'senderCommit': '9518361', 'firmwareCommit': '0441f78',
        'captureMethod': 'ci-host-log', 'appState': 'foreground',
    }
    identity.update(overrides)
    return json.dumps({'schema': 1, 'groupId': 'p3-4-link-stats-round6',
                       'identity': identity,
                       'inputs': [{'name': name, 'sha256': sha}]},
                      ensure_ascii=False, sort_keys=True)


def run_with_sidecar(text, payload, label='upgrade'):
    """写出日志与侧车，按 CLI 方式合并；返回 (退出码, JSON 结论)。"""
    log_path = temp_file('_tmp_bound.log', text)
    group_path = sidecar(payload)
    code, out, _ = run_main(['--log', log_path, '--group', group_path,
                             '--label', label, '--json'])
    return code, json.loads(out), log_path, group_path


def test_sidecar_declared_identity_makes_merge_threshold_eligible():
    """声明身份且与观测一致、原始日志 SHA 已绑定 → 门槛可用。"""
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest))
    try:
        assert code == 0, '身份齐备且无致命时应退出 0，实际 %d' % code
        report = payload['report']
        assert report['runs'] == 1, '合并轮数不符: %r' % report['runs']
        assert report['eligibleForThreshold'] is True, \
            '身份已声明且一致时必须门槛可用: %r' % report['ineligibleReasons']
        assert report['identity']['groupId'] == 'p3-4-link-stats-round6'
        assert report['identity']['declared']['baud'] == 921600, \
            '侧车声明的非观测字段必须原样保留在结论里'
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_identity_mismatch_is_fatal():
    """侧车声明与摘要观测不符 → GROUP_IDENTITY_MISMATCH(fatal) 且门槛不可用。

    诊断统计可以保留（单轮不存在"混组"），但必须显式标为不可用于门槛判定，
    并逐字段留痕是哪一项对不上。
    """
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest, writeMode='withResponse'))
    try:
        assert code == 1, '身份不符应退出 1，实际 %d' % code
        codes = {f['code'] for f in payload['findings']}
        assert 'GROUP_IDENTITY_MISMATCH' in codes, '应按字段报身份不符: %s' % codes
        mismatches = [f['detail'] for f in payload['findings']
                      if f['code'] == 'GROUP_IDENTITY_MISMATCH']
        assert any('writeMode' in detail for detail in mismatches), \
            '不符字段必须点名: %r' % mismatches
        report = payload['report']
        assert report['eligibleForThreshold'] is False, \
            '身份不符不得门槛可用: %r' % report['ineligibleReasons']
        assert any('GROUP_IDENTITY_MISMATCH' in reason
                   for reason in report['ineligibleReasons']), \
            '不可用理由必须写明身份不符: %r' % report['ineligibleReasons']
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_unbound_input_is_fatal():
    """日志未列入侧车 inputs[] → INPUT_UNBOUND(fatal)，不得参与门槛合并。"""
    text = strict_block_text()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload('b' * 64))
    try:
        assert code == 1, '未绑定输入应退出 1，实际 %d' % code
        codes = {f['code'] for f in payload['findings']}
        assert 'INPUT_UNBOUND' in codes, '应报未绑定输入: %s' % codes
        assert payload['report']['eligibleForThreshold'] is False
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_declared_sha_mismatch_is_fatal():
    """侧车声明了不在本轮输入中的 SHA → INPUT_SHA_MISMATCH(fatal)。"""
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    payload_text = json.loads(identity_payload(digest))
    payload_text['inputs'].append({'name': 'other.log', 'sha256': 'c' * 64})
    code, payload, log_path, group_path = run_with_sidecar(
        text, json.dumps(payload_text, ensure_ascii=False, sort_keys=True))
    try:
        assert code == 1, '声明了不存在的输入应退出 1，实际 %d' % code
        codes = {f['code'] for f in payload['findings']}
        assert 'INPUT_SHA_MISMATCH' in codes, '应报声明输入不符: %s' % codes
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_incomplete_identity_is_fatal():
    """侧车身份缺字段（如缺波特率）→ GROUP_IDENTITY_INCOMPLETE(fatal)。"""
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    payload_text = json.loads(identity_payload(digest))
    del payload_text['identity']['baud']
    code, payload, log_path, group_path = run_with_sidecar(
        text, json.dumps(payload_text, ensure_ascii=False, sort_keys=True))
    try:
        assert code == 1, '身份不完整应退出 1，实际 %d' % code
        codes = {f['code'] for f in payload['findings']}
        assert 'GROUP_IDENTITY_INCOMPLETE' in codes, '应报身份不完整: %s' % codes
        assert payload['report']['eligibleForThreshold'] is False
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_blank_identity_values_are_not_declared():
    """空串/纯空白不构成声明：字段在场 ≠ 身份已声明（P34-PR2-02）。

    整改前身份完整性只核对"字段是否存在、类型是否合法"：把包 SHA、提交、
    采集方式、应用状态全部写成空串，仍被判定为身份齐备并获得门槛资格。
    """
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest, packageSha256='', senderCommit='   ',
                               firmwareCommit='', captureMethod=' ',
                               appState=''))
    try:
        assert code == 1, '空身份应退出 1，实际 %d' % code
        invalid = [f['detail'] for f in payload['findings']
                   if f['code'] == 'GROUP_IDENTITY_INVALID']
        assert len(invalid) == 5, '五个空/空白字段都应逐项点名: %r' % invalid
        report = payload['report']
        assert report['eligibleForThreshold'] is False, \
            '空身份不得门槛可用'
        assert 'GROUP_IDENTITY_INVALID' in report['ineligibleReasons'], \
            '不可用理由必须写明身份无效: %r' % report['ineligibleReasons']
        assert 'GROUP_IDENTITY_INCOMPLETE' not in report['ineligibleReasons'], \
            '字段在场只是取值无效，不得报成字段缺失'
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_placeholder_identity_is_not_declared():
    """占位符（unknown/n-a/…）只说明未采集，不是声明。"""
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest, senderCommit='unknown',
                               captureMethod='N/A', appState='TBD'))
    try:
        assert code == 1, '占位身份应退出 1，实际 %d' % code
        invalid = [f['detail'] for f in payload['findings']
                   if f['code'] == 'GROUP_IDENTITY_INVALID']
        assert len(invalid) == 3, '三个占位字段都应逐项点名: %r' % invalid
        assert payload['report']['eligibleForThreshold'] is False
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_zero_parameters_are_not_declared():
    """可工作参数取 0 不构成声明：波特率/ACK 超时/包长必须为正。"""
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest, baud=0, timeoutMs=0, packageBytes=0))
    try:
        assert code == 1, '零参数应退出 1，实际 %d' % code
        invalid = [f['detail'] for f in payload['findings']
                   if f['code'] == 'GROUP_IDENTITY_INVALID']
        assert len(invalid) == 3, '三个零值参数都应逐项点名: %r' % invalid
        assert payload['report']['eligibleForThreshold'] is False
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_zero_retries_is_a_legal_declaration():
    """正例控制：`maxRetries=0`（不重试策略）是合法声明，不得被零值规则误杀。

    域规则必须按字段取值语义区分，而不是"见到 0 就判无效"——否则会把真实
    的"不重试"实验配置一起打红，使新规则失去鉴别力。
    """
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest, maxRetries=0))
    try:
        assert code == 0, '零重试是合法声明，应退出 0，实际 %d' % code
        assert 'GROUP_IDENTITY_INVALID' not in {
            f['code'] for f in payload['findings']}
        report = payload['report']
        assert report['runs'] == 1
        assert report['eligibleForThreshold'] is True, \
            '合法零值不得影响门槛资格: %r' % report['ineligibleReasons']
        assert report['identity']['declared']['maxRetries'] == 0
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_package_sha_trailing_newline_is_not_declared():
    """包 SHA 尾部换行（解出 65 字符）不构成声明 → GROUP_IDENTITY_INVALID（P34-PR3-02）。

    域正则若用 `^…$` 锚定，Python 的 `$` 还会匹配末尾换行之前的位置，于是
    `'A'*64 + '\n'` 被当成合法 hex64 包身份、原样保留在结论里并放行门槛。
    全串锚定（`\\A…\\Z`）后必须逐字段点名，且门槛不可用。
    """
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest, packageSha256='A' * 64 + '\n'))
    try:
        assert code == 1, '包 SHA 含尾部换行应退出 1，实际 %d' % code
        invalid = [f['detail'] for f in payload['findings']
                   if f['code'] == 'GROUP_IDENTITY_INVALID']
        assert len(invalid) == 1 and 'packageSha256' in invalid[0], \
            '尾部换行必须被逐字段点名: %r' % invalid
        report = payload['report']
        assert report['eligibleForThreshold'] is False, \
            '无效包身份不得门槛可用: %r' % report['ineligibleReasons']
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_sidecar_uppercase_package_sha_and_zero_retries_are_legal():
    """正例控制：合法大写包 SHA 与 `maxRetries=0` 仍构成声明。

    整串锚定只收紧"末尾多出字符"的取值，不得把大小写域（`[0-9a-fA-F]`）
    连同合法大写摘要、合法零重试一起打红。
    """
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    upper = 'ABCDEF0123456789' * 4
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest, packageSha256=upper, maxRetries=0))
    try:
        assert code == 0, '合法大写摘要应退出 0，实际 %d' % code
        assert 'GROUP_IDENTITY_INVALID' not in {
            f['code'] for f in payload['findings']}
        report = payload['report']
        assert report['eligibleForThreshold'] is True, \
            '合法声明不得影响门槛资格: %r' % report['ineligibleReasons']
        assert report['identity']['declared']['packageSha256'] == upper
        assert report['identity']['declared']['maxRetries'] == 0
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_lexical_regexes_reject_trailing_newline():
    """词法正则必须整串锚定，尾部换行不得被"截取合法前缀"放行（P34-PR3-02）。

    `$` 还匹配末尾换行之前的位置，`^…$` 会让 `'8\\n'`、64 位十六进制 + `\\n`
    这类取值被当成合法。数字域与 hex64 域统一改用 `\\A…\\Z` 后必须整串拒绝；
    其中只有 hex64 身份域能被外部输入直接命中（数字域另有类型闸门）。
    `_TOKEN_RE` 的取值类 `[^=]*` 本身可以吞掉换行，且它的输入来自行内切分后的
    token（不含换行），不是同一根因，这里只锁住合法字段不被误杀。
    """
    assert L._int('8\n') is None and L._int('-1\n') is None, '数字解析必须整串匹配'
    assert L._HEX64_RE.match('a' * 64 + '\n') is None, 'hex64 域必须整串匹配'
    assert L._int('8') == 8 and L._int('-1') == -1, '合法取值不得被整串锚定误杀'
    assert L._TOKEN_RE.match('kind=durable') is not None, '合法字段不得被误杀'
    assert L._HEX64_RE.match('a' * 64) is not None, '合法摘要不得被误杀'


def test_empty_capture_with_sidecar_is_not_threshold_eligible():
    """空捕获 + 齐备身份：不得门槛可用（P34-PR2-01 的核心放行路径）。

    整改前资格门禁只看身份理由，因此"身份齐备、但一轮合格观测都没有"的输入
    会被标成 `eligibleForThreshold=true`（runs=0、ACK=0）。资格必须同时要求
    可用观测与完整的校验结论。
    """
    text = ''
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest))
    try:
        assert code == 1, '空捕获已有致命项，应退出 1，实际 %d' % code
        report = payload['report']
        assert report['runs'] == 0 and report['ackLatency']['count'] == 0
        assert report['eligibleForThreshold'] is False, \
            '没有任何合格轮次不得门槛可用: %r' % report['ineligibleReasons']
        assert sorted(report['ineligibleReasons']) == \
            ['FATAL:NO_OBSERVATIONS', 'NO_ELIGIBLE_RUNS'], \
            '不可用理由必须同时写明无合格轮与本轮致命: %r' \
            % report['ineligibleReasons']
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_fatal_round_elsewhere_still_blocks_threshold_eligibility():
    """本轮存在致命项 → 即使另有合格洁净轮也不得门槛可用。

    构造：一块合格洁净轮 + 一块零时长传输（`ELAPSED_NOT_POSITIVE` 致命）。
    诊断统计仍应给出那 1 轮、8 个确认样本；但门槛比较要求整个采集轮次可
    复核，不能因为致命项落在别的块上就当作没有发生。
    """
    def mutate(summary):
        summary['transfer'].update({'elapsedUs': 0,
                                    'endAckUs': summary['transfer']['startUs']})
        summary['phases']['transfer'] = [summary['transfer']['startUs']] * 2
    text = (strict_block_text() + '\n'
            + strict_block_text(mutate=mutate))
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest))
    try:
        assert code == 1, '含致命项的轮次应退出 1，实际 %d' % code
        report = payload['report']
        assert report['runs'] == 1, '合格洁净轮仍应进入诊断统计: %r' % report['runs']
        assert report['ackLatency']['count'] == 8, \
            '诊断样本数不符: %r' % report['ackLatency']['count']
        assert report['excludedRuns'] == 1, '致命块必须留在排除清单里'
        assert report['eligibleForThreshold'] is False, \
            '本轮存在致命项不得门槛可用: %r' % report['ineligibleReasons']
        assert 'FATAL:ELAPSED_NOT_POSITIVE' in report['ineligibleReasons'], \
            '不可用理由必须点名本轮致命码: %r' % report['ineligibleReasons']
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_partial_round_without_clean_run_is_not_threshold_eligible():
    """诚实的部分覆盖：解析全绿、退出 0，但确认样本不完整 → 不得门槛可用。

    这是最容易被放行的一类：没有任何致命项、没有任何错误，只是
    `ackSamples='partial:missing=1,early=1'`。资格门禁必须自己得出
    "没有合格洁净轮"的结论，不能把身份齐备当成可用性。
    """
    text = ('\n'.join(EMITTER_EARLY_LINES) + '\n'
            + summary_line(emitter_early_summary()))
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = run_with_sidecar(
        text, identity_payload(digest))
    try:
        assert code == 0, '部分覆盖本身不是致命项，应退出 0，实际 %d' % code
        report = payload['report']
        assert not [f for f in payload['findings']
                    if f['severity'] == 'fatal'], \
            '构造失效：该轮不应有致命项: %r' % payload['findings']
        assert report['runs'] == 0 and report['ackLatency']['count'] == 0
        assert report['eligibleForThreshold'] is False, \
            '没有合格洁净轮不得门槛可用: %r' % report['ineligibleReasons']
        assert report['ineligibleReasons'] == ['NO_ELIGIBLE_RUNS'], \
            '理由应为无合格轮（而不是身份问题）: %r' % report['ineligibleReasons']
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_unexpected_analysis_failure_with_sidecar_is_not_threshold_eligible():
    """解析失败（未预期异常）不得被身份齐备放行。

    这是资格放行的第三种形态：输入读得进、侧车身份齐备，但分析期抛出未预期
    异常。兜底分支必须 fail-closed —— 退出码 1、`runs=0`、门槛不可用且理由
    为 `INTERNAL_ERROR`。这里注入必然失败的 `aggregate`，证明该分支确实
    给出结论，而不是靠"恰好没有异常"通过。
    """
    text = strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    original = L.aggregate

    def boom(*args, **kwargs):
        raise RuntimeError('注入的分析期故障')

    try:
        L.aggregate = boom
        code, payload, log_path, group_path = run_with_sidecar(
            text, identity_payload(digest))
    finally:
        L.aggregate = original
    try:
        assert code == 1, '分析期故障应退出 1，实际 %d' % code
        report = payload['report']
        assert report['runs'] == 0, '故障轮不得留下统计'
        assert report['eligibleForThreshold'] is False, \
            '分析失败不得门槛可用: %r' % report['ineligibleReasons']
        assert report['ineligibleReasons'] == ['INTERNAL_ERROR'], \
            '理由应指明内部错误: %r' % report['ineligibleReasons']
        assert 'INTERNAL_ERROR' in {f['code'] for f in payload['findings']}
    finally:
        drop_temp(log_path)
        drop_temp(group_path)


def test_merge_without_declared_identity_is_not_threshold_eligible():
    """未声明身份：仍可诊断，但必须标为非门槛可用并给出理由。"""
    report, findings = aggregate_of(strict_block_text())
    assert report['runs'] == 1, '未声明身份仍应产出诊断统计'
    assert report['eligibleForThreshold'] is False
    assert report['ineligibleReasons'] == ['GROUP_IDENTITY_NOT_DECLARED'], \
        '理由不符: %r' % report['ineligibleReasons']
    assert not [f for f in findings if f.severity == 'fatal'], \
        '未声明身份只是不可作门槛，不是致命发现'


def test_single_signature_merge_reports_observed_signature():
    """单一签名：结论里必须带观测身份，供人工核对（而不是只报一个数字）。"""
    report, _ = aggregate_of(strict_block_text())
    assert len(report['identity']['observedSignatures']) == 1
    signature = report['identity']['observedSignatures'][0]
    assert signature['device'] == 'AA:BB'
    assert signature['bind.mtuChunkBytes'] == 244
    assert report['identity']['mode'] == 'observed'


# ------------------------------------------------- P34-P02 归属、洁净与失败留痕


def test_parse_fatal_is_attached_to_its_block():
    """解析期致命项必须归属到所在块，否则合并阶段会把该块洗白成合格轮。"""
    lines = strict_block_text().splitlines()
    lines.insert(1, 'OTA_LINK_SAMPLE label=upgrade kind=unsupported us=50')
    report, findings = aggregate_of('\n'.join(lines))
    assert 'UNKNOWN_KIND' in fatalities(findings), '应保留解析期致命项'
    assert report['runs'] == 0, '含解析期致命项的块不得进入合并统计'
    assert report['excludedRuns'] == 1, '该块必须留在排除清单里'
    assert 'FATAL:UNKNOWN_KIND' in report['excluded'][0]['reasons'], \
        '排除理由必须写明致命码: %r' % report['excluded'][0]


def test_malformed_sample_disqualifies_its_block():
    """畸形样本行同样归属到块并取消其洁净资格。"""
    lines = strict_block_text().splitlines()
    lines.insert(1, 'OTA_LINK_SAMPLE label=upgrade kind=gatt_write us=x bytes=1')
    report, findings = aggregate_of('\n'.join(lines))
    assert 'MALFORMED_SAMPLE' in fatalities(findings)
    assert report['runs'] == 0 and report['excludedRuns'] == 1


def test_strict_mode_conclusion_is_not_rechecked_in_loose_mode():
    """严格模式的致命结论必须在合并阶段存活（不得用宽松模式重算洗白）。

    构造：同块两个实例（时钟回退）。默认模式只告警，但该块因多实例被取消
    洁净资格；严格模式下它是 `CLOCK_NONMONOTONIC` 致命。两种模式下都不得
    进入合并统计，且严格模式的排除理由里必须能读到 `FATAL:CLOCK_NONMONOTONIC`
    —— 若合并阶段重跑宽松校验，该理由会消失，只剩 `NOT_SINGLE_INSTANCE`。
    """
    second_lines, _ = real_block(2)
    text = strict_block_text(extra_sample_lines=second_lines)
    loose, loose_findings = aggregate_of(text)
    assert 'MULTI_INSTANCE' in {f.code for f in loose_findings}
    assert loose['runs'] == 0, '多实例块不得合并（默认模式）'
    assert not [reason for reason in loose['excluded'][0]['reasons']
                if reason.startswith('FATAL:')], \
        '默认模式该块不应有致命理由: %r' % loose['excluded'][0]['reasons']
    strict, strict_findings = aggregate_of(text, device_capture=True)
    assert 'CLOCK_NONMONOTONIC' in fatalities(strict_findings)
    assert strict['runs'] == 0, '多实例块不得合并（严格模式）'
    assert 'FATAL:CLOCK_NONMONOTONIC' in strict['excluded'][0]['reasons'], \
        '严格模式的致命结论必须原样进入排除理由: %r' % strict['excluded'][0]


def test_excluded_rounds_keep_line_numbers_and_reasons():
    """被排除的轮次必须保留来源、行号与理由（不得静默删除）。"""
    lines = strict_block_text().splitlines()
    lines[-1] = lines[-1].replace('"outcome": "ok"', '"outcome": "fail"')
    report, _ = aggregate_of('\n'.join(lines))
    assert report['runs'] == 0
    assert report['excludedRuns'] == 1
    entry = report['excluded'][0]
    assert entry['reasons'] == ["OUTCOME:'fail'"], '理由不符: %r' % entry['reasons']
    assert entry['firstLine'] == 1 and entry['summaryLine'] == len(lines), \
        '必须保留块的首行与摘要行行号: %r' % entry


def test_outcome_fail_is_excluded_but_not_fatal():
    """非 ok 终态是"不合格轮"而非"日志缺陷"：记入排除清单，不报致命。"""
    lines = strict_block_text().splitlines()
    lines[-1] = lines[-1].replace('"outcome": "ok"', '"outcome": "aborted"')
    report, findings = aggregate_of('\n'.join(lines))
    assert fatal_count(findings) == 0, '终态非 ok 不应报致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0 and report['excludedRuns'] == 1


def test_partial_ack_population_is_excluded_from_merge():
    """ACK 覆盖不完整（partial）的轮次不得当作洁净轮合并。"""
    def mutate(summary):
        summary['transfer']['ackSamples'] = 'partial:missing=1'
    report, findings = aggregate_of(strict_block_text(mutate=mutate))
    assert 'INTEGRITY_MISMATCH' in fatalities(findings), \
        '声明与重算不符应报致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_straggler_round_is_excluded_from_merge():
    """拖尾样本轮次归属不明：可诊断但不得进入数值池。"""
    sample_lines, samples = real_block(0)
    extra = [line for line in sample_lines if 'kind=gatt_write' in line][:1]
    text = '\n'.join(sample_lines + extra
                     + [summary_line(recompute_summary(samples))])
    report, findings = aggregate_of(text)
    assert 'STRAGGLER' in {f.code for f in findings}
    assert report['runs'] == 0, '拖尾轮不得合并: %r' % report['runs']
    assert fatal_count(findings) == 0, '拖尾是告警不是致命'
    assert 'SAMPLE_POPULATION_NOT_ATTRIBUTABLE:STRAGGLER' in \
        report['excluded'][0]['reasons']


def test_diagnostic_pool_is_separate_from_clean_pool():
    """诊断统计与洁净统计必须分开：diagnostic 保留可诊断轮，runs 只算洁净轮。"""
    text = strict_block_text() + '\n' + strict_block_text(mutate=lambda s: s.update(
        {'transfer': dict(s['transfer'], outcome='fail')}))
    report, _ = aggregate_of(text)
    assert report['runs'] == 1, '洁净轮只有 1 个: %r' % report['runs']
    assert report['excludedRuns'] == 1
    assert report['diagnostic']['runs'] == 1, '诊断池应只含可归属块'
    assert report['ackLatency']['count'] == 8


def test_polluted_real_block_is_excluded_with_evidence():
    """真实捕获的污染块：9 个实例段 + 段内重复首发/重复确认 → 被排除且留痕。

    这是 `capture-audit.json` 记录的 Windows 行 307–976 块：摘要只声明 8 个
    ACK，缓冲区里却有 210 个。新语义下该块因"混有多个实例 + 段内偏移重复"
    失去洁净资格，其样本不得进入任何数值池。
    """
    root = main_worktree_root()
    if root is None:
        print('      SKIP 无法定位主 worktree（git 不可用），本项不参与判定')
        return
    path = os.path.join(root, '.cache', CAPTURE_RUNS[0], 'windows',
                        'run-baccd24b786e464b98495ec3cf82806a', 'logs', 'tests.log')
    if not os.path.exists(path):
        print('      SKIP 外部捕获不在场（%s），本项不参与判定' % path)
        return
    with open(path, 'rb') as handle:
        text = handle.read().decode('utf-8', errors='replace')
    groups, findings = check_text(text)
    polluted = [g for g in groups if len(L._clock_segments(g.samples)) > 1]
    assert len(polluted) == 1, '应恰有一个多实例块: %d' % len(polluted)
    group = polluted[0]
    assert group.first_line == 307 and group.summary_line == 976, \
        '污染块行号已变: %r/%r' % (group.first_line, group.summary_line)
    counts = {}
    for sample in group.samples:
        counts[sample.kind] = counts.get(sample.kind, 0) + 1
    assert len(group.samples) == 454, '污染块样本数已变: %d' % len(group.samples)
    assert len(L._clock_segments(group.samples)) == 9, \
        '污染块实例段数已变: %d' % len(L._clock_segments(group.samples))
    assert counts.get('ack_latency') == 210 and counts.get('segment_first_send') == 210, \
        '缓冲区里的 210 条确认/首发是本次污染的核心证据: %r' % counts
    assert group.summary['transfer']['segmentsUnique'] == 8 and \
        group.summary['transfer']['ackLatency']['count'] == 8, \
        '摘要仍只声明 8 个 ACK（污染块自身的声明与观测相差 26 倍）'
    codes = set(group.codes())
    assert {'DUPLICATE_SEGMENT_OFFSET', 'DUPLICATE_ACK_OFFSET',
            'MULTI_INSTANCE'} <= codes, '污染块应报偏移重复与多实例: %s' % sorted(codes)
    assert not group.fatal, '默认模式下这些是告警，由洁净资格负责排除'
    report = L.aggregate(groups, 'upgrade')[0]
    assert report['runs'] == 6, '洁净轮数已变: %r' % report['runs']
    assert report['ackLatency']['count'] == 48, \
        '合并样本数已变（不得再出现 266 的混入值）: %r' % report['ackLatency']['count']
    assert report['segmentsUnique'] == 48, \
        '唯一段数已变（不得再出现 64 的混入值）: %r' % report['segmentsUnique']
    assert report['ackLatency']['p99Us'] == 1328, \
        '洁净池 P99 不应被污染块样本拉动: %r' % report['ackLatency']['p99Us']
    excluded_lines = [entry['summaryLine'] for entry in report['excluded']]
    assert 976 in excluded_lines, '污染块必须出现在排除清单里: %r' % excluded_lines
    entry = [item for item in report['excluded'] if item['summaryLine'] == 976][0]
    assert entry['reasons'] == [
        'NOT_SINGLE_INSTANCE',
        'OFFSET_SET_INCONSISTENT:DUPLICATE_ACK_OFFSET',
        'OFFSET_SET_INCONSISTENT:DUPLICATE_SEGMENT_OFFSET',
        'SAMPLE_POPULATION_NOT_ATTRIBUTABLE:STRAGGLER'], \
        '排除理由必须逐条留痕: %r' % entry['reasons']


# ------------------------------------------------- P34-P03 偏移集合完整性


def duplicate_ack_only_text():
    """只把第二条 ACK 的 off 复制成第一条的 off，其余保持自洽。

    摘要按变异后的样本行重算，因此分位数与计数仍然自洽：这样"恰好只报
    重复确认偏移"才是真正的隔离前提，不会混入 QUANTILE_MISMATCH。
    """
    sample_lines, _ = real_block(0)
    mutated = [line.replace('off=128', 'off=0', 1)
               if 'kind=ack_latency' in line and 'off=128' in line else line
               for line in sample_lines]
    assert sum(1 for line in mutated if 'kind=ack_latency' in line) == 8
    assert sum(1 for line in mutated
               if 'kind=ack_latency' in line and 'off=0' in line) == 2
    return block_text(mutated, summary_override=recompute_summary(parse_lines(mutated)))


def test_duplicate_ack_offset_is_detected():
    """复制一个 ACK 的 off 顶替另一个缺失段 → DUPLICATE_ACK_OFFSET。"""
    report, findings = aggregate_of(duplicate_ack_only_text(), device_capture=True)
    assert 'DUPLICATE_ACK_OFFSET' in fatalities(findings), \
        '应检出重复确认偏移: %s' % [str(f) for f in findings]
    assert 'QUANTILE_MISMATCH' not in {f.code for f in findings}, \
        '该构造的摘要已按变异样本重算，不应混入分位数不符'
    assert report['runs'] == 0, '偏移集合不自洽的块不得合并'


def test_duplicate_ack_offset_is_warn_in_default_mode():
    """默认模式下偏移重复是告警，但必须同时取消该块的洁净资格。"""
    report, findings = aggregate_of(duplicate_ack_only_text())
    pairs = code_pairs(findings)
    assert ('DUPLICATE_ACK_OFFSET', 'warn') in pairs, '默认模式应为告警: %s' % pairs
    assert report['runs'] == 0 and report['excludedRuns'] == 1, \
        '偏移集合不自洽即使只是告警也不得合并: %s' % report['excluded']


def test_missing_first_send_offset_is_fatal():
    """首发样本缺 off → SEGMENT_OFFSET_MISSING(fatal)，零检出不再可能。

    删除首个首发的 `off` 后，摘要仍按剩余采样重算，用于证明"删掉一个首发偏移"
    不会被"行数没变"掩盖。
    """
    sample_lines, _ = real_block(0)
    mutated = [line.replace(' off=128', '', 1)
               if 'kind=segment_first_send' in line and 'off=128' in line else line
               for line in sample_lines]
    assert sum(1 for line in mutated if 'off=' not in line
               and 'kind=segment_first_send' in line) == 1
    text = block_text(mutated, summary_override=recompute_summary(parse_lines(mutated)))
    _, findings = check_text(text, device_capture=True)
    assert 'SEGMENT_OFFSET_MISSING' in fatalities(findings), \
        '缺偏移必须致命: %s' % [str(f) for f in findings]
    assert len(text.splitlines()) == len(sample_lines) + 1, \
        '本负例不改行数，只改偏移字段'


def test_orphan_retransmit_is_detected():
    """重传没有对应首发 → ORPHAN_RETRANSMIT（严格模式致命）。"""
    lines = list(strict_block_text().splitlines())
    lines.insert(1, 'OTA_LINK_SAMPLE label=upgrade kind=segment_retransmit '
                    'us=12 off=8192 len=128')
    _, findings = check_text('\n'.join(lines), device_capture=True)
    assert 'ORPHAN_RETRANSMIT' in fatalities(findings), \
        '应检出孤儿重传: %s' % [str(f) for f in findings]


def test_ack_without_segment_is_detected():
    """确认的偏移在本块内没有任何发送段 → ACK_WITHOUT_SEGMENT。"""
    lines = list(strict_block_text().splitlines())
    lines.insert(1, 'OTA_LINK_SAMPLE label=upgrade kind=ack_latency us=12 off=8192')
    _, findings = check_text('\n'.join(lines), device_capture=True)
    assert 'ACK_WITHOUT_SEGMENT' in fatalities(findings), \
        '应检出无段确认: %s' % [str(f) for f in findings]


def test_retransmit_creates_no_new_unique_segment_or_ack_sample():
    """合法形状：重传不产生新的唯一段、也不产生新的 ACK 样本。

    重传行必须落在对应首发**之后**，否则构造出的是孤儿重传而非合法重传。
    """
    sample_lines, _ = real_block(0)
    first_index = next(index for index, line in enumerate(sample_lines)
                       if 'kind=segment_first_send' in line)
    off = sample_lines[first_index].split('off=')[1].split()[0]
    retransmit = ('OTA_LINK_SAMPLE label=upgrade kind=segment_retransmit '
                  'us=7200 off=%s len=128' % off)
    lines = list(sample_lines)
    lines.insert(first_index + 1, retransmit)
    summary = recompute_summary(parse_lines(lines))
    assert summary['transfer']['segmentsUnique'] == 8, '唯一段数不变'
    assert summary['transfer']['segmentSendTotal'] == 9, '发送次数 +1'
    assert summary['transfer']['retransmitFrames'] == 1
    assert summary['transfer']['ackLatency']['count'] == 8, '不新增确认样本'
    text = block_text(lines, summary_override=summary)
    _, findings = check_text(text)
    assert fatal_count(findings) == 0, \
        '合法重传不得报错: %s' % [str(f) for f in findings]
    assert 'ORPHAN_RETRANSMIT' not in {f.code for f in findings}
    assert 'OFFSET_SET_INCONSISTENT' not in {f.code for f in findings}


def test_multiple_segments_share_one_ack_is_legal():
    """合法形状：一个 ACK 覆盖多个段（确认偏移仍唯一）不得报错。"""
    sample_lines, _ = real_block(0)
    lines = [line for line in sample_lines
             if 'kind=ack_latency' not in line or 'off=0' in line]
    summary = recompute_summary(parse_lines(lines))
    assert summary['transfer']['ackSamples'] == 'partial:missing=7', \
        '该构造应是 ACK 覆盖不足但集合自洽: %r' % summary['transfer']['ackSamples']
    _, findings = check_text(block_text(lines, summary_override=summary))
    assert 'ACK_WITHOUT_SEGMENT' not in {f.code for f in findings}, \
        '多段共用一个合法确认不得报无段确认: %s' % [str(f) for f in findings]
    assert fatal_count(findings) == 0


def test_early_ack_prefix_is_not_a_missing_segment():
    """合法形状：新实例 resume 返回的早到确认不被制造成样本或缺失段。

    `ack_early` 记的是"确认先到、首发后登记"，它既不是 `ack_latency` 样本，
    也不代表缺失发送段；`ackEarlyUnsent` 必须把它算作未送出的确认。
    """
    text = '\n'.join(EMITTER_EARLY_LINES) + '\n' + summary_line(emitter_early_summary())
    report, findings = aggregate_of(text)
    assert fatal_count(findings) == 0, \
        '发射端合法早到确认不得报错: %s' % [str(f) for f in findings]
    assert 'ACK_WITHOUT_SEGMENT' not in {f.code for f in findings}
    assert 'SEGMENT_OFFSET_MISSING' not in {f.code for f in findings}
    assert report['runs'] == 0, 'partial 覆盖不得当作完整测量合并'
    assert report['excluded'][0]['reasons'] == ["ACK_SAMPLES:'partial:missing=1,early=1'"], \
        '排除理由不符: %r' % report['excluded'][0]['reasons']


# ------------------------------------------------- P34-P04 空捕获与非法收口


def test_empty_capture_is_not_success():
    """空文件不是"通过"：任何模式都必须致命，仅看退出码的调用方不得被判绿。"""
    _, strict = check_text('', device_capture=True)
    assert fatalities(strict) == ['NO_OBSERVATIONS'], \
        '空捕获必须报无有效观测: %s' % [str(f) for f in strict]
    _, loose = check_text('')
    assert fatalities(loose) == ['NO_OBSERVATIONS'], \
        '默认模式空输入同样致命（零观测不是宽松口径可容忍的形状问题）: %s' \
        % [str(f) for f in loose]


def test_noise_only_capture_is_not_success():
    """只有噪声行、没有样本也没有摘要 → 同样不是合法输入，两种模式都致命。"""
    noise = '\n'.join(['[INFO] Flutter test runner started',
                       'OTA sent 12/240', '---- 12 tests passed ----'])
    for strict_mode in (True, False):
        _, findings = check_text(noise, device_capture=strict_mode)
        assert fatalities(findings) == ['NO_OBSERVATIONS'], \
            '纯噪声输入应报无观测（strict=%s）: %s' % (
                strict_mode, [str(f) for f in findings])


def test_null_summary_is_not_a_closing_summary():
    """`OTA_LINK_STATS null` 不是合法收口，且不得清除已有样本的错误归属。"""
    sample_lines, samples = real_block(0)
    text = list(sample_lines) + ['OTA_LINK_STATS null']
    groups, findings = check_text('\n'.join(text))
    assert len(groups[-1].samples) == len(samples), \
        '样本必须仍归属该块（不得被静默清空）: %d' % len(groups[-1].samples)
    assert fatalities(findings) == ['BAD_JSON'], \
        '应报合法 JSON 但顶层非对象: %s' % [str(f) for f in findings]


def test_non_object_summary_is_not_a_closing_summary():
    """数组/标量摘要同样不能作为合法收口。"""
    for payload in ('[1, 2, 3]', '42', '"ok"'):
        text = strict_block_text().splitlines()[:-1] + ['OTA_LINK_STATS ' + payload]
        _, findings = check_text('\n'.join(text))
        assert fatalities(findings) == ['BAD_JSON'], \
            '摘要 %s 应报 BAD_JSON: %s' % (payload, [str(f) for f in findings])


def test_null_summary_keeps_blocks_out_of_merge():
    """非法收口的块不得进入合并统计，也不得静默消失。"""
    text = strict_block_text().splitlines()[:-1] + ['OTA_LINK_STATS null']
    report, findings = aggregate_of('\n'.join(text))
    assert report['runs'] == 0, '非法收口的块不得合并: %r' % report['runs']
    assert fatal_count(findings) >= 1


def test_corrupt_summary_is_fatal_and_not_silently_dropped():
    """破损 JSON：报 BAD_JSON(fatal)，块内样本仍被记录（不静默丢弃）。"""
    sample_lines, samples = real_block(0)
    lines = list(sample_lines) + [summary_line(recompute_summary(samples))[:-4]]
    groups, findings = check_text('\n'.join(lines))
    assert 'BAD_JSON' in fatalities(findings)
    assert len(groups) == 1 and len(groups[0].samples) == len(samples), \
        '破损摘要不得连样本一起丢掉: %d' % len(groups[0].samples)


def test_unclosed_tail_block_reports_missing_summary():
    """未收口块：默认告警、严格模式致命，且都不参与合并。"""
    sample_lines, samples = real_block(0)
    text = block_text(sample_lines, drop_summary=True)
    _, loose = check_text(text)
    expect_one(loose, 'SUMMARY_MISSING', 'warn', '默认模式未收口块只应告警')
    _, strict = check_text(text, device_capture=True)
    expect_one(strict, 'SUMMARY_MISSING', 'fatal', '严格模式未收口块应为致命')
    report, _ = aggregate_of(text)
    assert report['runs'] == 0
    assert report['unclosedBlocks'] == 1 and \
        report['unclosedSamples'] == len(samples), \
        '未收口块与样本数必须如实申报: %r/%r' % (report['unclosedBlocks'],
                                                 report['unclosedSamples'])


def test_unclosed_block_samples_are_label_scoped():
    """未收口块只按自身 label 计入未收口统计，不污染其它 label 的报告。"""
    text = strict_block_text(drop_summary=True)
    report, _ = aggregate_of(text, label='probe')
    assert report['unclosedBlocks'] == 0, \
        'upgrade 的未收口块不得算进 probe 报告: %r' % report['unclosedBlocks']


# ------------------------------------------------- P34-P05 类型、范围与重算


def test_success_with_zero_elapsed_is_fatal_and_excluded():
    """成功传输 elapsed=0 非法（OTA-XC-BLE-TUNING）且不得进入合并。"""
    def mutate(summary):
        summary['transfer'].update({'elapsedUs': 0, 'endAckUs': summary['transfer']['startUs']})
        summary['phases']['transfer'] = [summary['transfer']['startUs']] * 2
    report, findings = aggregate_of(strict_block_text(mutate=mutate))
    assert fatalities(findings) == ['ELAPSED_NOT_POSITIVE'], \
        '应报成功传输的零时长: %s' % [str(f) for f in findings]
    assert report['runs'] == 0, '非法时长的轮次不得合并'


def test_missing_elapsed_timing_field_is_fatal():
    """删掉 elapsedUs 不得绕过时长核对（P34-PR2-04 的核心放行路径）。

    整改前 elapsedUs 是"可选呈现字段"：把它连着 endAckUs 一起抹平，整块
    零发现、`strictFieldsComplete` 仍为真，零传输时长直接获得门槛资格。
    `transfer.startUs/endAckUs/elapsedUs` 自 schema 1 起由发射端 `toJson`
    恒定输出，缺失是测量契约缺口，必须致命且不得门槛可用。
    """
    def mutate(summary):
        del summary['transfer']['elapsedUs']
        summary['transfer']['endAckUs'] = summary['transfer']['startUs']
        summary['phases']['transfer'] = [summary['transfer']['startUs']] * 2
    report, findings = aggregate_of(strict_block_text(mutate=mutate))
    assert fatalities(findings) == ['TIMING_INCOMPLETE'], \
        '缺 elapsedUs 必须报时序不完整: %s' % [str(f) for f in findings]
    assert 'FIELD_ABSENT' in {f.code for f in findings}, \
        '缺字段仍应保留兼容性告警（不得只报致命就抹掉缺字段事实）'
    assert report['runs'] == 0, '无法判定时长的一轮不得进入合并'
    assert report['strictFieldsComplete'] is False, \
        '缺时序契约字段时不得声称契约完整: %r' % report['strictFieldsComplete']


def test_missing_start_or_end_timing_field_is_fatal():
    """startUs / endAckUs 任一缺失同样致命（不能只要求 elapsedUs 在场）。"""
    for field in ('startUs', 'endAckUs'):
        def mutate(summary, field=field):
            del summary['transfer'][field]
        report, findings = aggregate_of(strict_block_text(mutate=mutate))
        assert fatalities(findings) == ['TIMING_INCOMPLETE'], \
            '缺 %s 必须报时序不完整: %s' % (field, [str(f) for f in findings])
        assert report['runs'] == 0


def test_success_with_null_timing_fields_is_fatal():
    """成功传输的时序字段为 null → 无时长可判定，不得当作合法缺省。"""
    def mutate(summary):
        summary['transfer'].update({'startUs': None, 'endAckUs': None,
                                    'elapsedUs': None})
    report, findings = aggregate_of(strict_block_text(mutate=mutate))
    assert fatalities(findings) == ['TIMING_INCOMPLETE'], \
        '成功传输的 null 时序必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_non_ok_round_allows_null_timing_fields():
    """正例控制：非成功终态（未启动/失败/探针）允许时序为 null。

    时序字段自 schema 1 起恒定输出，但只有**成功**传输才必须给出正时长；
    把 null 一律打红会把真实捕获里的探针块与失败轮全部误杀。
    """
    def mutate(summary):
        summary['transfer'].update({'outcome': None, 'startUs': None,
                                    'endAckUs': None, 'elapsedUs': None})
    report, findings = aggregate_of(strict_block_text(mutate=mutate))
    assert 'TIMING_INCOMPLETE' not in fatalities(findings), \
        '非成功终态的 null 时序不得误报: %s' % [str(f) for f in findings]
    assert report['runs'] == 0, '非成功终态本就不是合格洁净轮'


def test_negative_segment_offset_is_fatal():
    """负偏移不指向任何数据段 → SEGMENT_OFFSET_INVALID（fatal，不得零发现通过）。"""
    lines = list(real_block(0)[0])
    for index, line in enumerate(lines):
        if 'kind=segment_first_send' in line and 'off=0 ' in line:
            lines[index] = line.replace('off=0 ', 'off=-128 ')
            break
    else:
        raise AssertionError('构造失效：夹具里没有 off=0 的首发样本')
    report, findings = aggregate_of(block_text(lines))
    assert fatalities(findings) == ['SEGMENT_OFFSET_INVALID'], \
        '负偏移必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0, '偏移非法的块不得合并'


def test_zero_length_segment_is_fatal():
    """零长度段不覆盖任何字节 → SEGMENT_LENGTH_INVALID（fatal）。"""
    lines = list(real_block(0)[0])
    for index, line in enumerate(lines):
        if 'kind=segment_first_send' in line:
            lines[index] = line.replace('len=128', 'len=0')
            break
    else:
        raise AssertionError('构造失效：夹具里没有首发样本')
    report, findings = aggregate_of(block_text(lines))
    assert fatalities(findings) == ['SEGMENT_LENGTH_INVALID'], \
        '零段长必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


# ------------------------------------- PR3-01 逐条样本数值域（真实块 0 构造）

DURABLE_FIRST = 'kind=durable us=6177 off=0'
RETRANSMIT_TAIL = ('OTA_LINK_SAMPLE label=upgrade kind=segment_retransmit '
                   'us=16850 off=0 len=128')
PLATFORM_TAIL = 'OTA_LINK_SAMPLE label=upgrade kind=platform_write us=16860 bytes=100'


def block_with(*sample_lines):
    """真实块 0 追加若干样本行（追加在末尾，保持时钟严格递增）。"""
    lines, _ = real_block(0)
    return list(lines) + list(sample_lines)


def mutated_real_block(needle, replacement):
    """真实块 0 中把首处 needle 换成 replacement；找不到即构造失效。"""
    lines, _ = real_block(0)
    for index, line in enumerate(lines):
        if needle in line:
            lines[index] = line.replace(needle, replacement, 1)
            return list(lines)
    raise AssertionError('构造失效：夹具里找不到 %r' % needle)


def test_negative_nonterminal_durable_offset_is_fatal():
    """非末条 durable 的负偏移同样致命 → SEGMENT_OFFSET_INVALID（P34-PR3-01）。

    整改前只读 durable 末条偏移：首条 `off=-1` 因此零发现通过。中间样本既是
    `durableEvents` 的席位，也构成 `finalOff` 的推进足迹，必须逐条过域。
    """
    text = block_text(mutated_real_block(DURABLE_FIRST,
                                         'kind=durable us=6177 off=-1'))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['SEGMENT_OFFSET_INVALID'], \
        '非末条负偏移必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0, '偏移非法的块不得合并'


def test_missing_nonterminal_durable_offset_is_fatal():
    """非末条 durable 缺 off 致命 → SEGMENT_OFFSET_MISSING（P34-PR3-01）。"""
    text = block_text(mutated_real_block(DURABLE_FIRST, 'kind=durable us=6177'))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['SEGMENT_OFFSET_MISSING'], \
        '非末条缺偏移必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_non_integer_nonterminal_durable_offset_is_fatal():
    """非末条 durable 的 off 非整数致命 → SEGMENT_OFFSET_MISSING（P34-PR3-01）。"""
    text = block_text(mutated_real_block(DURABLE_FIRST,
                                         'kind=durable us=6177 off=bad'))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['SEGMENT_OFFSET_MISSING'], \
        '非整数偏移必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_retransmit_zero_length_is_fatal():
    """重传段的零长度致命 → SEGMENT_LENGTH_INVALID（P34-PR3-01）。

    首发与重传都由发射端携带 len（ota_link_stats.dart:257/271）；只对首发要求
    len 会让重传的 `len=0` 零发现通过，而重传帧同样进入 `retransmitFrames` /
    `segmentSendTotal` 计数池。
    """
    text = block_text(block_with(RETRANSMIT_TAIL.replace('len=128', 'len=0')))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['SEGMENT_LENGTH_INVALID'], \
        '重传零长度必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_retransmit_negative_length_is_fatal():
    """重传段的负长度致命 → SEGMENT_LENGTH_INVALID（P34-PR3-01）。"""
    text = block_text(block_with(RETRANSMIT_TAIL.replace('len=128', 'len=-1')))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['SEGMENT_LENGTH_INVALID'], \
        '重传负长度必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_retransmit_missing_length_is_fatal():
    """重传段缺 len（或非整数）致命 → SEGMENT_OFFSET_MISSING（P34-PR3-01）。"""
    text = block_text(block_with(RETRANSMIT_TAIL.replace(' len=128', '')))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['SEGMENT_OFFSET_MISSING'], \
        '重传缺长度必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_gatt_negative_bytes_is_fatal():
    """GATT 写样本的负字节数致命 → BYTE_COUNT_INVALID（P34-PR3-01）。

    字节计数是"确实写出的字节数"观测：负值既不可能来自任何一次写入，也会
    抵消同块其它样本的计数。整改前只查整数性，不查符号。
    """
    text = block_text(mutated_real_block('kind=gatt_write us=0 bytes=10',
                                         'kind=gatt_write us=0 bytes=-1'))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['BYTE_COUNT_INVALID'], \
        'GATT 负字节数必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_platform_negative_bytes_is_fatal():
    """platform 写样本的负字节数致命 → BYTE_COUNT_INVALID（P34-PR3-01）。

    构造取"负值 + 等量正值"使净和为 0：摘要声明的 `platformWrites.bytes`
    因此仍是合法零，负值只能由样本级字节域拦下。否则该反例会退化成"声明字段
    类型非法"的检出，证明不了 `_sum_bytes` 对 platform 调用方也做了域校验。
    """
    text = block_text(block_with(
        PLATFORM_TAIL.replace('bytes=100', 'bytes=-5'),
        PLATFORM_TAIL.replace('us=16860 bytes=100', 'us=16870 bytes=5')))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['BYTE_COUNT_INVALID'], \
        'platform 负字节数必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_legal_retransmit_keeps_block_clean():
    """正例控制：合法重传（len=128）不改变块的洁净与门槛资格。

    重传是发射端的合法行为（重发未确认段）：域校验只拒绝非法长度，不得把真实
    重传一并打红，也不得让它多算唯一段或确认样本。
    """
    report, findings = aggregate_of(block_text(block_with(RETRANSMIT_TAIL)))
    assert findings == [], '合法重传不得产生任何检出: %s' % [
        str(f) for f in findings]
    assert report['runs'] == 1
    assert report['segmentsUnique'] == 8, \
        '重传不得新增唯一段: %r' % report['segmentsUnique']
    assert report['retransmitFrames'] == 1
    assert report['ackLatency']['count'] == 8


def test_durable_zero_offsets_are_legal_resume_marks():
    """正例控制：durable 偏移域是**非负**而不是正，0 不得被拒。

    真实捕获块 0 的首条 durable 就是 `off=0`（resume 起点）。整改只补"逐条
    校验、缺失/非整数/负值致命"，不得顺手把 0 一起打红；末条同样是 0 的序列
    只说明没有新的推进，也不是取值域问题。
    """
    sample_lines, samples = real_block(0)
    offsets = [s.extra.get('off') for s in samples if s.kind == 'durable']
    assert offsets[0] == '0', '夹具首条 durable 偏移已变: %r' % offsets[0]
    report, findings = aggregate_of(block_text(sample_lines))
    assert findings == [], '含零偏移 durable 的块不得误报: %s' % [
        str(f) for f in findings]
    assert report['runs'] == 1
    text = block_text(mutated_real_block('kind=durable us=16841 off=1024',
                                         'kind=durable us=16841 off=0'))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == [], \
        '重复的零偏移属合法取值，不得误报: %s' % [str(f) for f in findings]
    assert report['runs'] == 1


def test_legal_write_byte_sums_over_both_writers_are_accepted():
    """正例控制：GATT 与 platform 两侧的合法字节和被正确累加。

    域校验只拒绝负值；合法计数必须照常进入 `gattWriteBytes` /
    `platformWriteBytes`，否则"两个调用方共用域校验"会变成"两侧都不能用"。
    """
    groups, findings = check_text(block_text(block_with(PLATFORM_TAIL)))
    assert findings == [], '合法字节计数不得误报: %s' % [str(f) for f in findings]
    counts = groups[0].counts
    assert counts['gattWriteCalls'] == 11 and counts['platformWriteCalls'] == 1
    assert counts['gattWriteBytes'] == 1299, \
        '夹具 GATT 字节和已变: %r' % counts['gattWriteBytes']
    assert counts['platformWriteBytes'] == 100, \
        'platform 字节和未按样本累加: %r' % counts['platformWriteBytes']


def test_negative_phase_timestamp_is_fatal():
    """负阶段时间戳 → PHASE_NEGATIVE（fatal）。

    `stopwatch-mono-us` 时钟域不可能出现负值；负值意味着时钟域用错或字段
    被改写，此时阶段边界不能再参与任何区间比较。构造同时把 `bind.phaseUs`
    调成与新边界自洽，以便把 `PHASE_NEGATIVE` 与 `INTERNAL_INCONSISTENT`
    的鉴别力彻底分开。
    """
    def mutate(summary):
        summary['phases']['bind'] = [-5, 100]
        summary['bind']['phaseUs'] = 105
    report, findings = aggregate_of(strict_block_text(mutate=mutate))
    assert fatalities(findings) == ['PHASE_NEGATIVE'], \
        '负阶段时间必须致命: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_non_integer_phase_bound_is_structured_not_a_traceback():
    """非整数阶段边界必须给结构化结论，不得抛异常吞掉整轮结论。

    `phases.bind=[0, null]` 在旧实现里会让 `None` 参与相减：异常从
    `check()` 逃逸后，CLI 只会剩一条 `INTERNAL_ERROR`，本轮所有块与全部
    其他输入的具体结论都被丢掉。结构/类型缺陷应逐项报出（这里由上方循环
    报 `INTERNAL_INCONSISTENT`），而不是让整轮失去结论。
    """
    def mutate(summary):
        summary['phases']['bind'] = [summary['phases']['bind'][0], None]
    report, findings = aggregate_of(strict_block_text(mutate=mutate))
    assert 'INTERNAL_INCONSISTENT' in fatalities(findings), \
        '非整数阶段边界必须给结构化结论: %s' % [str(f) for f in findings]
    assert report['runs'] == 0


def test_legit_zero_microsecond_single_operation_is_allowed():
    """单次操作的零微秒耗时合法：真实捕获里 11 次 gatt_write 全部是 us=0。

    这里不做任何变异——夹具本身就是"零微秒合法"的真实证据；被禁止的只有
    **成功传输整体** elapsed<=0，两者不得混为一谈。
    """
    sample_lines, samples = real_block(0)
    zero = [s for s in samples if s.kind == 'gatt_write' and s.us == 0]
    assert len(zero) == 11, '夹具里零微秒 gatt_write 数量已变: %d' % len(zero)
    _, findings = check_text(block_text(sample_lines))
    assert 'ELAPSED_NOT_POSITIVE' not in {f.code for f in findings}, \
        '零微秒单次操作不得误报: %s' % [str(f) for f in findings]
    assert fatal_count(findings) == 0, '真实捕获块不得有致命项: %s' % [
        str(f) for f in findings]


def test_boolean_is_not_an_integer():
    """`true` 不得冒充计数 1（`True == 1` 会骗过朴素相等比较）。"""
    def mutate(summary):
        summary['transfer']['retransmitFrames'] = True
        summary['transfer']['segmentSendTotal'] = 8
    _, findings = check_text(strict_block_text(mutate=mutate))
    codes = {f.code for f in findings}
    assert 'FIELD_TYPE_INVALID' in codes, '布尔冒充整数应被类型核对拦下: %s' % codes


def test_illegal_types_yield_structured_conclusion_without_traceback():
    """非法类型必须给出结构化致命结论，不能让 --json 因 traceback 失去结论。"""
    cases = [
        ('schema_object', lambda s: s.update({'schema': {}})),
        ('clock_object', lambda s: s.update({'clock': {}})),
        ('counter_string', lambda s: s['gattWrites'].update({'calls': '1'})),
        ('bytes_string', lambda s: s['gattWrites'].update({'bytes': '140'})),
        ('mtu_string', lambda s: s['bind'].update({'mtuChunkBytes': '244'})),
        ('quantile_string', lambda s: s['transfer']['ackLatency'].update({'p99Us': '1'})),
        ('acks_array', lambda s: s.update({'phases': []})),
        ('negative_counter', lambda s: s['gattWrites'].update({'calls': -1})),
    ]
    for name, mutate in cases:
        path = temp_file('_tmp_type.log', strict_block_text(mutate=mutate))
        try:
            code, out, err = run_main(['--log', path, '--json'])
            assert code == 1, '%s 应退出 1（实际 %d）: %s' % (name, code, err)
            payload = json.loads(out)  # 必须仍是合法 JSON
            fatal = [f for f in payload['findings'] if f['severity'] == 'fatal']
            assert fatal, '%s 应给出结构化致命项' % name
            assert 'INTERNAL_ERROR' not in {f['code'] for f in fatal}, \
                '%s 不得退化成内部异常: %s' % (name, fatal)
        finally:
            drop_temp(path)


def test_phase_quantile_tamper_is_detected():
    """阶段分位数被篡改 → QUANTILE_MISMATCH(fatal)（gatt/discover/platform）。"""
    for field in ('gattWrites', 'discovers', 'platformWrites'):
        def mutate(summary, field=field):
            summary[field]['p95Us'] = 999999
        _, findings = check_text(strict_block_text(mutate=mutate))
        assert 'QUANTILE_MISMATCH' in fatalities(findings), \
            '%s 分位数篡改未被检出: %s' % (field, [str(f) for f in findings])


def test_getinfo_total_tamper_is_detected():
    """`getInfo.totalUs` 被篡改 → PHASE_TOTAL_MISMATCH(fatal)。"""
    def mutate(summary):
        summary['getInfo']['totalUs'] += 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    assert 'PHASE_TOTAL_MISMATCH' in fatalities(findings), \
        '合计被篡改应被检出: %s' % [str(f) for f in findings]


def test_missing_binding_fields_lower_strict_completeness():
    """删掉写模式/MTU 来源后不得再声称契约完整（完整性标记必须与实际核对一致）。"""
    def mutate(summary):
        del summary['bind']['writeMode']
        del summary['bind']['mtuSource']
    report, findings = aggregate_of(strict_block_text(mutate=mutate))
    assert 'FIELD_ABSENT' in {f.code for f in findings}
    assert report['strictFieldsComplete'] is False, \
        '缺绑定字段时不得声称完整: %r' % report['strictFieldsComplete']
    assert report['runsWithAbsentFields'] == 1
    assert report['runs'] == 1, '缺字段只降完整性，不阻止诊断合并（旧版本兼容）'


def test_strict_completeness_requires_at_least_one_clean_run():
    """没有任何合格洁净轮时，完整性标记不得为真（避免空集上的假阳性）。"""
    report, _ = aggregate_of(strict_block_text(drop_summary=True))
    assert report['strictFieldsComplete'] is False, \
        '无合格轮时不得声称契约完整: %r' % report
    assert report['runs'] == 0


def test_strict_completeness_is_true_for_current_contract_block():
    """字段齐全的当前契约块：完整性标记为真（标记确实会随核对范围变化）。"""
    report, _ = aggregate_of(strict_block_text())
    assert report['strictFieldsComplete'] is True, \
        '字段齐全的块应标为完整: %r' % report['runsWithAbsentFields']


def test_legacy_absent_fields_do_not_block_diagnostic_merge():
    """旧版本缺字段仍可诊断合并，但合并不被标为门槛可用。"""
    report, findings = aggregate_of('\n'.join(fixture_lines()))
    assert report['runs'] == 2, '旧版切片仍应产出诊断统计: %r' % report['runs']
    assert report['strictFieldsComplete'] is False
    assert report['eligibleForThreshold'] is False
    assert fatal_count(findings) == 0, '缺字段不得升级为致命'


# ------------------------------------------------- P34-P06 早到 ACK 的时序语义


def test_emitter_early_ack_shape_is_legal():
    """发射端合法输出序不得报时钟回退（`ack_early_invalid` 回放的是到达时刻）。

    构造来自发射端源码语义（`_earlyConfirmUs` 暂存 + `_onSegmentFirstSend`
    取出），**不是**执行过的 Dart 或设备测量；该构造仍处于 partial 覆盖状态，
    因此不得被当作完整测量合并。
    """
    text = '\n'.join(EMITTER_EARLY_LINES) + '\n' + summary_line(emitter_early_summary())
    _, findings = check_text(text, device_capture=True)
    codes = {f.code for f in findings}
    assert 'CLOCK_NONMONOTONIC' not in codes, \
        '合法早到确认不得报时钟回退: %s' % [str(f) for f in findings]
    assert 'MULTI_INSTANCE' not in codes
    assert 'EARLY_ACK_UNLINKED' not in codes
    assert fatal_count(findings) == 0, \
        '合法回放不得有任何致命项: %s' % [str(f) for f in findings]


def test_unlinked_early_ack_replay_is_fatal():
    """无关联的旧时间重放（时间对不上）→ EARLY_ACK_UNLINKED(fatal)。"""
    lines = list(EMITTER_EARLY_LINES)
    lines[2] = 'OTA_LINK_SAMPLE label=upgrade kind=ack_early_invalid us=9 off=0'
    text = ('\n'.join(lines) + '\n'
            + summary_line(emitter_early_summary(lines)))
    _, findings = check_text(text, device_capture=True)
    assert fatalities(findings) == ['EARLY_ACK_UNLINKED'], \
        '时间对不上的重放必须致命: %s' % [str(f) for f in findings]


def test_early_ack_offset_mismatch_is_fatal():
    """早到确认关联到不同偏移 → EARLY_ACK_UNLINKED(fatal)。"""
    lines = list(EMITTER_EARLY_LINES)
    lines[0] = 'OTA_LINK_SAMPLE label=upgrade kind=ack_early us=10 off=256'
    text = ('\n'.join(lines) + '\n'
            + summary_line(emitter_early_summary(lines)))
    _, findings = check_text(text, device_capture=True)
    assert 'EARLY_ACK_UNLINKED' in fatalities(findings), \
        '偏移对不上必须致命: %s' % [str(f) for f in findings]


def test_early_ack_cross_instance_pollution_is_detected():
    """跨实例挪用旧时间：早到确认与回放落在不同实例段 → 仍须致命。

    构造：第 1 段记下 `ack_early(us=150)`，随后首发时间回退到 10 进入第 2 段，
    回放行 `ack_early_invalid(us=150)` 落在第 2 段里。若只按"同段内找一条同时刻
    同偏移的早到确认"就放过，跨实例挪用会被漏掉。
    """
    lines = [
        'OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=100 off=0 len=128',
        'OTA_LINK_SAMPLE label=upgrade kind=ack_early us=150 off=0',
        'OTA_LINK_SAMPLE label=upgrade kind=segment_first_send us=10 off=128 len=128',
        'OTA_LINK_SAMPLE label=upgrade kind=ack_early_invalid us=150 off=0',
    ]
    text = '\n'.join(lines) + '\n' + summary_line(emitter_early_summary(lines))
    groups, findings = check_text(text)
    segments = L._clock_segments(groups[0].samples)
    assert len(segments) == 2, '构造未形成两个实例段: %d' % len(segments)
    early_segment = [index for index, segment in enumerate(segments)
                     if any(s.kind == 'ack_early' for s in segment)]
    replay_segment = [index for index, segment in enumerate(segments)
                      if any(s.kind == 'ack_early_invalid' for s in segment)]
    assert early_segment != replay_segment, \
        '构造失效：早到确认与回放落在同一段，无法证明跨实例挪用被拦下'
    codes = {f.code for f in findings}
    assert 'EARLY_ACK_UNLINKED' in fatalities(findings), \
        '跨实例挪用必须致命: %s' % [str(f) for f in findings]
    assert 'MULTI_INSTANCE' in codes, '该构造同时应报多实例段: %s' % sorted(codes)


def test_genuine_clock_rollback_is_still_reported():
    """真实时钟回退仍必须报警（不得为了放过早到确认而放宽单调性）。"""
    text = block_text(ROLLBACK_LINES)
    _, loose = check_text(text)
    assert 'MULTI_INSTANCE' in {f.code for f in loose}, \
        '真实回退应报多实例: %s' % [str(f) for f in loose]
    assert 'CLOCK_NONMONOTONIC' not in fatalities(loose), \
        '默认模式下真实回退只是告警: %s' % [str(f) for f in loose]
    _, strict = check_text(text, device_capture=True)
    assert 'CLOCK_NONMONOTONIC' in fatalities(strict), \
        '严格模式下真实回退必须致命: %s' % [str(f) for f in strict]


def test_early_ack_invalid_is_excluded_from_monotonic_clock():
    """`ack_early_invalid` 不参与单调时钟，但其它时间戳仍参与。"""
    group = L.Group([L.Sample('upgrade', 'ack_early', 10, {}, 1),
                     L.Sample('upgrade', 'durable', 11, {}, 2),
                     L.Sample('upgrade', 'ack_early_invalid', 10, {}, 3),
                     L.Sample('upgrade', 'segment_first_send', 20, {}, 4)], None)
    assert len(L._clock_segments(group.samples)) == 1, \
        '早到确认回放不得切分实例段'
    assert L.EVENT_TIME_KINDS == L.TIMESTAMP_KINDS - {'ack_early_invalid'}, \
        '仅 ack_early_invalid 例外，其它时间戳仍参与单调性'


# -------------------------------------------------------- 负例：混组与结构


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


def test_quantile_tamper_is_fatal():
    """错误摘要：分位数被改 → QUANTILE_MISMATCH(fatal)。"""
    def mutate(summary):
        summary['transfer']['ackLatency']['p99Us'] = \
            summary['transfer']['ackLatency']['p99Us'] + 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect_one(findings, 'QUANTILE_MISMATCH', 'fatal', 'p99 篡改')


def test_missing_sample_line_is_fatal():
    """删掉一条真实样本行但保留原摘要 → COUNT_MISMATCH(fatal)。

    这是"只用行数核对完整性"的反例：行数少一行、摘要没跟着改，旧口径下
    看不出来，重算核对必须报计数不符。
    """
    sample_lines, samples = real_block(0)
    dropped = [index for index, line in enumerate(sample_lines)
               if 'kind=gatt_write' in line][0]
    lines = [line for index, line in enumerate(sample_lines) if index != dropped]
    text = block_text(lines, summary_override=recompute_summary(samples))
    report, findings = aggregate_of(text)
    assert fatalities(findings) == ['COUNT_MISMATCH'], \
        '缺失样本行必须按重算报计数不符: %s' % [str(f) for f in findings]
    assert report['runs'] == 0, '计数不符的块不得合并'


def test_declared_count_inflation_is_fatal():
    """错误摘要：计数大于样本重算 → COUNT_MISMATCH(fatal)。"""
    def mutate(summary):
        summary['gattWrites']['calls'] += 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    assert ('COUNT_MISMATCH', 'fatal') in code_pairs(findings), \
        '计数虚高应被检出: %s' % code_pairs(findings)


def test_retransmit_derivation_tamper_is_fatal():
    """错误摘要：retransmitFrames 与发送总数/唯一段数不符 → 两处独立检出。"""
    def mutate(summary):
        summary['transfer']['retransmitFrames'] += 1
    _, findings = check_text(strict_block_text(mutate=mutate))
    expect(findings, [('COUNT_MISMATCH', 'fatal'), ('INTERNAL_INCONSISTENT', 'fatal')],
           '重传帧数篡改应被计数与派生两层同时检出')


def test_elapsed_tamper_is_fatal():
    """错误摘要：elapsedUs 与 endAckUs-startUs 不符 → INTERNAL_INCONSISTENT。"""
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


def test_durable_final_off_behind_last_sample_is_warn():
    """摘要后 durable 继续推进：声明的 finalOff 是更早的样本 → STRAGGLER(warn)。"""
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

    构造：把第二个真实 upgrade 块（同 label、独立实例）的样本行接在块 1 样本
    之后、块 1 摘要之前——真实捕获中正是这个形状。样本行逐字节取自夹具。
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


def test_bad_json_is_fatal():
    """摘要 JSON 破损 → BAD_JSON(fatal)，且该块按"无合法收口"另行申报。"""
    lines = strict_block_text().splitlines()
    lines[-1] = lines[-1][:-4]
    _, findings = check_text('\n'.join(lines))
    expect(findings, [('BAD_JSON', 'fatal'), ('SUMMARY_MISSING', 'warn')],
           '摘要 JSON 截断：既要报解析失败，也要报该块没有合法收口')


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
    """摘要缺必需对象 → SCHEMA_MISSING(fatal)，其下字段逐项申报缺失。"""
    lines = strict_block_text().splitlines()
    summary = json.loads(lines[-1][len('OTA_LINK_STATS '):])
    del summary['gattWrites']
    lines[-1] = 'OTA_LINK_STATS ' + json.dumps(summary, ensure_ascii=False)
    _, findings = check_text('\n'.join(lines))
    missing_fields = len([1 for f in findings if f.code == 'FIELD_ABSENT'])
    assert ('SCHEMA_MISSING', 'fatal') in code_pairs(findings), \
        '缺必需对象应报致命: %s' % code_pairs(findings)
    assert missing_fields == 7, \
        'gattWrites 下 7 个必需字段应逐项申报缺失（calls/bytes/errors/4 个分位数）: %d' \
        % missing_fields


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


def test_merged_quantiles_use_nearest_rank_over_clean_pool():
    """合并 P99 用洁净池全部样本的 nearest-rank（独立复算，逐块样本必须分开）。"""
    sample_lines, samples = real_block(0)
    single = block_text(sample_lines)
    report, findings = aggregate_of(single + '\n' + single)
    assert fatal_count(findings) == 0, '两块均为合法块: %s' % [str(f) for f in findings]
    assert report['runs'] == 2 and report['excludedRuns'] == 0
    block_values = [s.us for s in samples if s.kind == 'ack_latency']
    pooled = block_values + block_values
    assert report['ackLatency']['count'] == len(pooled) == 16, \
        '合并样本数不符: %r' % report['ackLatency']['count']
    assert report['ackLatency']['p99Us'] == nearest_rank(pooled, 0.99), \
        '合并 P99 不符: %r vs %r' % (report['ackLatency']['p99Us'],
                                     nearest_rank(pooled, 0.99))
    assert report['ackLatency']['maxUs'] == max(pooled)
    # 逐块统计必须仍在 `groups` 里可查，且不与合并池混同（每块只有 8 个样本）。
    per_group = report['groups']
    assert len(per_group) == 1, '同一身份签名应合成一个输入组: %r' % len(per_group)
    assert per_group[0]['runs'] == 2, \
        '输入组内应记录 2 个洁净轮: %r' % per_group[0]['runs']


# ---------------------------------------------------------------- CLI 契约


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = L.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_cli_exit_codes_and_json():
    """CLI：正例退出 0、致命退出 1、文件缺失退出 2、--json 结论形状完整。"""
    ok_path = temp_file('_tmp_ok.log', strict_block_text())
    bad_path = temp_file('_tmp_bad.log', strict_block_text(mutate=lambda s: s.update(
        {'schema': 2})))
    try:
        code, out, _ = run_main(['--log', ok_path, '--json'])
        assert code == 0, '正例退出码应为 0，实际 %d' % code
        payload = json.loads(out)
        for key in ('log', 'inputs', 'groups', 'samples', 'findings', 'report'):
            assert key in payload, '--json 缺字段 %s' % key
        assert payload['inputs'][0]['sha256'], '结论必须带输入 SHA-256 绑定'
        report = payload['report']
        for key in ('runs', 'excludedRuns', 'excluded', 'ackLatency',
                    'retransmitRate', 'strictFieldsComplete', 'unclosedBlocks',
                    'eligibleForThreshold', 'ineligibleReasons', 'identity',
                    'groups', 'diagnostic'):
            assert key in report, '合并报告缺字段 %s' % key

        code, out, _ = run_main(['--log', bad_path])
        assert code == 1, '致命发现应退出 1，实际 %d' % code
        assert 'FATAL' in out, '文本输出应含致命标记'

        code, _, err = run_main(['--log', os.path.join(HERE, '不存在.log')])
        assert code == 2, '读取失败应退出 2，实际 %d' % code
        assert '读取失败' in err
    finally:
        drop_temp(ok_path)
        drop_temp(bad_path)


def test_cli_accepts_multiple_logs():
    """`--log` 可重复：**不同**日志构成同一输入组，块数、样本数与确认数累加。

    两份文件必须是不同字节的观测块；同字节的副本是重复引用而不是第二个独立
    轮次（见 `test_repeated_input_is_deduplicated_and_reported`）。
    """
    lines_a, samples_a = real_block(0)
    lines_b, samples_b = real_block(2)
    first = temp_file('_tmp_multi_a.log', block_text(list(lines_a)))
    second = temp_file('_tmp_multi_b.log', block_text(list(lines_b)))
    try:
        code, out, _ = run_main(['--log', first, '--log', second, '--json'])
        assert code == 0
        payload = json.loads(out)
        assert payload['groups'] == 2, '块数不符: %r' % payload['groups']
        assert payload['samples'] == len(samples_a) + len(samples_b), \
            '样本数不符: %r' % payload['samples']
        assert len(payload['inputs']) == 2
        assert len({meta['sha256'] for meta in payload['inputs']}) == 2, \
            '两份不同文件应各有其 SHA-256'
        assert len({meta['sourceId'] for meta in payload['inputs']}) == 2, \
            '来源标识必须逐份唯一: %r' % payload['inputs']
        assert all(meta['duplicateOf'] is None for meta in payload['inputs']), \
            '不同内容不得被标成重复输入'
        assert payload['report']['runs'] == 2
        assert payload['report']['ackLatency']['count'] == 16, \
            '两轮确认样本应累加: %r' % payload['report']['ackLatency']['count']
        assert len(payload['report']['identity']['observedSignatures']) == 1, \
            '同一身份的输入应合成一个签名组'
    finally:
        drop_temp(first)
        drop_temp(second)


def test_repeated_input_is_deduplicated_and_reported():
    """同一路径传两次：同一份捕获的副本不是独立轮次（P34-PR2-03）。

    整改前重复输入会被解析两次：runs 1→2、ACK 8→16，直接把一轮的观测虚增
    成两轮。这里同时要求"统计不虚增"与"如实报告重复"。
    """
    path = temp_file('_tmp_repeat.log', strict_block_text())
    try:
        code, out, _ = run_main(['--log', path, '--log', path, '--json'])
        assert code == 1, '重复引用不是合法输入，应退出 1，实际 %d' % code
        payload = json.loads(out)
        assert payload['groups'] == 1, '同一份捕获不得算成两块: %r' % payload['groups']
        report = payload['report']
        assert report['runs'] == 1, '重复引用不得虚增轮数: %r' % report['runs']
        assert report['ackLatency']['count'] == 8, \
            '重复引用不得虚增确认样本数: %r' % report['ackLatency']['count']
        assert 'DUPLICATE_INPUT' in {f['code'] for f in payload['findings']}
        assert len(payload['inputs']) == 2, '两份输入记录都要保留（含重复的那份）'
        assert payload['inputs'][1]['duplicateOf'] == payload['inputs'][0]['sourceId'], \
            '重复记录必须指回首次使用的来源标识: %r' % payload['inputs']
        assert report['eligibleForThreshold'] is False, \
            '重复输入不得门槛可用: %r' % report['ineligibleReasons']
        assert 'DUPLICATE_INPUT' in report['ineligibleReasons'], \
            '不可用理由必须写明重复输入: %r' % report['ineligibleReasons']
    finally:
        drop_temp(path)


def test_same_basename_inputs_keep_distinct_source_ids():
    """不同目录下的同名日志必须保留来源区分（P34-PR2-03）。

    整改前排除记录只记 `basename`：`a/tests.log` 与 `b/tests.log` 的排除
    条目在结论里完全无法区分。来源标识必须绑定内容摘要，让每条记录都能
    指回唯一一份捕获。
    """
    dir_a = temp_dir('_tmp_src_a')
    dir_b = temp_dir('_tmp_src_b')
    lines_a = list(EMITTER_EARLY_LINES)
    lines_b = [line.replace('us=11 off=128', 'us=12 off=128')
               for line in EMITTER_EARLY_LINES]
    first = temp_tree_file(dir_a, 'tests.log',
                           '\n'.join(lines_a) + '\n'
                           + summary_line(emitter_early_summary(lines_a)))
    second = temp_tree_file(dir_b, 'tests.log',
                            '\n'.join(lines_b) + '\n'
                            + summary_line(emitter_early_summary(lines_b)))
    try:
        code, out, _ = run_main(['--log', first, '--log', second, '--json'])
        assert code == 0, '两轮部分覆盖本身无致命项，应退出 0，实际 %d' % code
        payload = json.loads(out)
        meta = payload['inputs']
        assert [item['name'] for item in meta] == ['tests.log', 'tests.log'], \
            '构造失效：两份输入应同名: %r' % meta
        assert meta[0]['sha256'] != meta[1]['sha256'], \
            '构造失效：两份输入应字节不同: %r' % meta
        assert meta[0]['sourceId'] != meta[1]['sourceId'], \
            '同名不同内容必须有不同的来源标识: %r' % meta
        excluded = payload['report']['excluded']
        assert len(excluded) == 2, '两轮部分覆盖都应留在排除清单里: %r' % excluded
        assert len({item['source'] for item in excluded}) == 2, \
            '排除记录必须能区分同名来源: %r' % excluded
        assert all(item['source'].startswith('tests.log#') for item in excluded), \
            '来源标识应带内容摘要: %r' % excluded
    finally:
        drop_temp_dir(dir_a)
        drop_temp_dir(dir_b)


def test_cli_on_real_fixture_is_green():
    """真实切片经 CLI：默认与严格模式都退出 0（无致命）。"""
    for extra in ([], ['--device-capture']):
        code, out, _ = run_main(['--log', FIXTURE] + extra)
        assert code == 0, '真实切片退出码应为 0（%s），实际 %d' % (extra, code)
        assert '致命发现 0 项' in out, '输出应报告 0 致命（%s）' % extra


def test_cli_aggregate_merges_only_clean_runs():
    """合并统计只纳入洁净轮，并如实标注缺口、未收口块与门槛资格。"""
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
    assert report['eligibleForThreshold'] is False, \
        '未声明实验身份时不得标为门槛可用'


# ------------------------------------------------- 可选：整份真实捕获


def test_optional_full_capture():
    """整份真实捕获（不入库）：0 致命 + 逐宿主形状一致；不在场则 SKIP。"""
    captures = optional_captures()
    if not captures:
        print('      SKIP 外部捕获不在场（主 worktree .cache/%s/<宿主>/*/logs/'
              'tests.log 不存在或 git 不可用），本项不参与判定'
              % '/'.join(CAPTURE_RUNS))
        return
    seen = set()
    for run, host, path in captures:
        expect_shape = CAPTURE_EXPECTATIONS[(run, host)]
        with open(path, 'rb') as handle:
            text = handle.read().decode('utf-8', errors='replace')
        groups, findings = check_text(text)
        fatal = [f for f in findings if f.severity == 'fatal']
        assert not fatal, '%s/%s 整份捕获应 0 致命: %s' % (
            run, host, [str(f) for f in fatal])
        counts = {}
        for finding in findings:
            counts[finding.code] = counts.get(finding.code, 0) + 1
        assert counts == expect_shape['codes'], \
            '%s/%s 检出计数与冻结形状不符:\n  实际 %r\n  期望 %r' % (
                run, host, counts, expect_shape['codes'])
        assert len(groups) == expect_shape['blocks'], \
            '%s/%s 观测块数不符: %r' % (run, host, len(groups))
        samples = sum(len(g.samples) for g in groups)
        assert samples == expect_shape['samples'], \
            '%s/%s 样本数不符: %r' % (run, host, samples)

        report = L.aggregate(groups, 'upgrade')[0]
        observed = dict(report)
        observed['ackLatencyCount'] = report['ackLatency']['count']
        for key, value in expect_shape['report'].items():
            assert observed[key] == value, \
                '%s/%s 合并报告 %s 不符: 实际 %r 期望 %r' % (
                    run, host, key, observed[key], value)
        assert report['eligibleForThreshold'] is False, \
            '未声明身份的真实捕获不得标为门槛可用'
        seen.add((run, host))
        print('      整份捕获 %s/%s: 块=%d 样本=%d 致命=0 告警=%s '
              'runs=%d excluded=%d unclosed=%d/%d'
              % (run, host, len(groups), samples, counts, report['runs'],
                 report['excludedRuns'], report['unclosedBlocks'],
                 report['unclosedSamples']))
        # 污染识别与排除理由逐条落盘：这是"合法合并范围"的直接证据，
        # 不能只报一个 0 致命的结论。
        for entry in report['excluded']:
            print('        排除 %s/%s 行 %s..%s 检出=%s 理由=%s'
                  % (run, host, entry['firstLine'], entry['summaryLine'],
                     entry['codes'], entry['reasons']))
        empty = 0
        for group in groups:
            if not group.samples:
                # 零样本块是 probe 探针未采集到样本的合法结构，不是污染。
                empty += 1
                continue
            segments = L._clock_segments(group.samples)
            if len(segments) == 1:
                continue
            kinds = {}
            for sample in group.samples:
                kinds[sample.kind] = kinds.get(sample.kind, 0) + 1
            declared = L._dig(group.summary or {}, 'transfer', 'ackLatency', 'count')
            print('        污染块 %s/%s label=%s 行 %s..%s 样本=%d 实例段=%d '
                  '确认样本=%d 摘要声明确认=%r 首发=%d 重传=%d'
                  % (run, host, group.label, group.first_line, group.summary_line,
                     len(group.samples), len(segments),
                     kinds.get('ack_latency', 0), declared,
                     kinds.get('segment_first_send', 0),
                     kinds.get('segment_retransmit', 0)))
        pooled = {'segment_retransmit': report['retransmitFrames'],
                  'segmentsUnique': report['segmentsUnique']}
        print('        合法合并范围 %s/%s: runs=%d 确认样本=%d 唯一段=%d '
              '唯一重传=%d P99=%r 字段完整=%s 门槛可用=%s 零样本块=%d'
              % (run, host, report['runs'], report['ackLatency']['count'],
                 report['segmentsUnique'], report['retransmitFrames'],
                 report['ackLatency']['p99Us'], report['strictFieldsComplete'],
                 report['eligibleForThreshold'], empty))
        assert pooled['segmentsUnique'] == report['ackLatency']['count'], \
            '%s/%s 洁净池里唯一段数应与确认样本数一致（每段一个确认）' % (run, host)
    missing = sorted(set(CAPTURE_EXPECTATIONS) - seen)
    if missing:
        print('      SKIP 未覆盖宿主（证据不在场）: %s' % missing)


# ---------------------------------------------------------------- 鉴别力

def _stub_none(arity):
    """置空核对函数：保持"返回 None"的类型契约。"""
    if arity == 2:
        return lambda group, findings: None
    return lambda group, findings, strict_blocks=False: None


def _mutated_parse_sample(line, line_no, findings):
    """保持返回类型 Sample|None 的宽松解析：不做合法性拒绝。

    变异点：取消 `parse_sample` 的畸形/未知 kind 拒绝行为，只保留类型契约。
    findings 不变，样本仍以 Sample 形式返回。
    """
    tokens = line.split()
    extra = {}
    for token in tokens[1:]:
        if '=' in token:
            key, value = token.split('=', 1)
            extra[key] = value
    if not extra:
        return None
    return L.Sample(extra.get('label'), extra.get('kind', 'unknown'),
                    L._int(extra.get('us')) or 0, extra, line_no)


def _mutated_clock_segments(samples):
    """保持返回类型 list 的变异：整体当作一个实例段。"""
    return [list(samples)]


def _mutated_early_links(group, segments, findings):
    """保持返回类型 None 的变异：不做早到确认关联核对。"""
    assert isinstance(segments, list)
    return None


def _always_clean_classify(group, excluded):
    """保持返回类型 (bool, bool) 的变异：任何块都判为可归属且洁净。

    变异点：取消 `_classify` 的排除判定（fatal / STRAGGLER / 多实例 /
    偏移集合 / 非 ok 终态 / 非 complete 覆盖）。该变异不产生新的 findings，
    只让不合格块混入数值池 —— 正是 P34-P02 要防的"污染块仍被合并"。
    """
    assert isinstance(excluded, list)
    return True, True


def _stub_sample_off(sample, findings, require_len=False):
    """保持返回类型 None|int 的变异：不校验样本偏移与段长。

    变异点：取消 `_sample_off` 的缺失 / 负偏移 / 零段长拒绝（返回值语义
    仍与"取不到偏移"一致）。
    """
    return None


def _stub_identity_domain(key, value):
    """保持返回类型 None|str 的变异：任何取值都被当作有效身份声明。"""
    return None


def _stub_qualification_reasons(*args, **kwargs):
    """保持返回类型 list 的变异：任何输入都判定为门槛可用。"""
    return []


def _fixture_group(index=0):
    """夹具第 index 个观测块（供需要真实 group 的变异探针使用）。"""
    groups, _ = fixture_groups()
    return groups[index]


def _mutated_observed_counts(original):
    """保持返回类型 dict 的变异：durable 只校验末条偏移（P34-PR3-01a）。

    变异点：还原整改前形态——中间 durable 样本的缺失/非整数/负偏移不进域校验，
    `finalOff` 也只要末条合法就给出。其它计数键（含字节域）保持原样，以便把
    "逐条 durable 校验"与"字节计数域"的鉴别力分开。
    """
    durable_codes = ('SEGMENT_OFFSET_MISSING', 'SEGMENT_OFFSET_INVALID')

    def mutated(group, findings):
        scratch = []
        counts = original(group, scratch)
        findings.extend(f for f in scratch if f.code not in durable_codes)
        durable = group.kinds('durable')
        counts['durableFinalOff'] = None
        if durable:
            off = L._int(durable[-1].extra.get('off'))
            if off is not None and off >= 0:
                counts['durableFinalOff'] = off
        return counts

    return mutated


def _mutated_sample_off_len_for_first_send(original):
    """保持返回类型 int|None 的变异：只有首发要求 len（P34-PR3-01b）。

    变异点：还原整改前 `_check_offset_sets` 只对 `segment_first_send` 传
    `require_len=True` 的形态——重传段的零/负/缺长度因此零发现通过。
    """
    def mutated(sample, findings, require_len=False):
        return original(sample, findings,
                        require_len and sample.kind == 'segment_first_send')

    return mutated


def _mutated_sum_bytes(original):
    """保持返回类型 int|None 的变异：字节数只查整数性，不查符号（P34-PR3-01c）。

    变异点：还原整改前 `_sum_bytes` 的形态——GATT 与 platform 两个调用方都不做
    取值域校验，负字节数照常累加（并抵消同块其它样本的计数）。
    """
    def mutated(group, kind, findings):
        total = 0
        for sample in group.kinds(kind):
            value = L._int(sample.extra.get('bytes'))
            if value is None:
                findings.append(L.Finding('MALFORMED_SAMPLE', 'fatal',
                                          '%s 样本缺 bytes 或非整数' % kind,
                                          sample.line_no))
                return None
            total += value
        return total

    return mutated


# 鉴别力配对表：变异点 → 依赖它的负例 → 同变异下仍须通过的正例。
# `contract` 为变异后函数的返回类型契约，生效前先跑 `probe` 校验；
# 类型不符说明变异本身非法（不再计鉴别力），必须换一个保持类型的变异。
DISCRIMINATION = (
    {'target': '_check_quantiles', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_quantile_tamper_is_fatal',
               'test_quantile_check_runs_and_catches_shift',
               'test_phase_quantile_tamper_is_detected',
               'test_getinfo_total_tamper_is_detected'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_integrity', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_integrity_declaration_tamper_is_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_counters', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_missing_sample_line_is_fatal',
               'test_declared_count_inflation_is_fatal',
               'test_bytes_tamper_is_fatal',
               'test_durable_final_off_tamper_is_fatal',
               'test_durable_final_off_behind_last_sample_is_warn',
               'test_straggler_sample_is_warn_not_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_clock', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(3), 'probe': lambda f: f(None, []),
     'tests': ['test_negative_us_is_fatal',
               'test_clock_rollback_is_multi_instance_then_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_clock_segments', 'kind': 'func', 'contract': 'list',
     'replacement': lambda orig: _mutated_clock_segments,
     'probe': lambda f: f([1, 2]),
     'tests': ['test_clock_rollback_is_multi_instance_then_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_early_links', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _mutated_early_links,
     'probe': lambda f: f(None, [], []),
     'tests': ['test_unlinked_early_ack_replay_is_fatal',
               'test_early_ack_offset_mismatch_is_fatal',
               'test_early_ack_cross_instance_pollution_is_detected'],
     'positive': 'test_emitter_early_ack_shape_is_legal'},
    {'target': '_check_offset_sets', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(3), 'probe': lambda f: f(None, []),
     'tests': ['test_duplicate_ack_offset_is_detected',
               'test_missing_first_send_offset_is_fatal',
               'test_orphan_retransmit_is_detected',
               'test_ack_without_segment_is_detected'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_structure', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_clock_domain_mismatch_is_fatal',
               'test_unknown_schema_is_fatal',
               'test_missing_required_object_is_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_derived', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_retransmit_derivation_tamper_is_fatal',
               'test_phase_reversed_is_fatal',
               'test_bind_phase_tamper_is_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_attempts', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_attempt_number_rollback_is_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_labels', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_wrong_label_is_fatal',
               'test_sample_level_label_mixing_is_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_check_required_present', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_missing_binding_fields_lower_strict_completeness',
               'test_absent_field_is_warn_not_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': 'parse_sample', 'kind': 'func', 'contract': 'Sample|None',
     'replacement': lambda orig: _mutated_parse_sample,
     'probe': lambda f: f('OTA_LINK_SAMPLE kind=x us=1', 1, []),
     'tests': ['test_malformed_sample_is_fatal',
               'test_unknown_kind_is_fatal'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    {'target': '_classify', 'kind': 'func', 'contract': 'tuple2bool',
     'replacement': lambda orig: _always_clean_classify,
     'probe': lambda f: f(None, []),
     # 不含 test_polluted_real_block_is_excluded_with_evidence：该用例在外部
     # 捕获不在场时会 SKIP（正常返回），会被误判成"变异后仍然通过"。真实污染
     # 块的排除留痕由 §4 的整份捕获证据与 CLI 用例单独覆盖。
     'tests': ['test_partial_ack_population_is_excluded_from_merge',
               'test_straggler_round_is_excluded_from_merge',
               'test_excluded_rounds_keep_line_numbers_and_reasons'],
     'positive': 'test_strict_contract_block_has_no_findings'},
    # P34-PR2-04：样本偏移/段长取值域（负偏移、零长度段不再零发现通过）。
    {'target': '_sample_off', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_sample_off,
     'probe': lambda f: f(None, []),
     'tests': ['test_negative_segment_offset_is_fatal',
               'test_zero_length_segment_is_fatal',
               'test_missing_first_send_offset_is_fatal'],
     # 正例用同一条合法性判据的合法侧（多段共用一个确认）：变异只取消"缺失/
     # 负偏移/零段长拒绝"，不得让合法段集的管道结论发生变化。
     'positive': 'test_multiple_segments_share_one_ack_is_legal'},
    # P34-PR2-04：传输时序完备性与自洽（缺 elapsedUs 不再绕过正时长核对）。
    {'target': '_check_transfer_timing', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_none(2), 'probe': lambda f: f(None, []),
     'tests': ['test_elapsed_tamper_is_fatal',
               'test_missing_elapsed_timing_field_is_fatal',
               'test_missing_start_or_end_timing_field_is_fatal',
               'test_success_with_null_timing_fields_is_fatal',
               'test_success_with_zero_elapsed_is_fatal_and_excluded'],
     # 正例用同一函数的合法侧（非 ok 终态允许时序为 null）：变异只取消缺字段/
     # null/零时长的核对，不得影响合法非成功轮次的放行。
     'positive': 'test_non_ok_round_allows_null_timing_fields'},
    # P34-PR2-02：身份取值语义（空串/占位符/零参数不再是"已声明"）。
    {'target': '_identity_domain_problem', 'kind': 'func', 'contract': 'NoneType',
     'replacement': lambda orig: _stub_identity_domain,
     'probe': lambda f: f('device', 'AA:BB'),
     'tests': ['test_sidecar_blank_identity_values_are_not_declared',
               'test_sidecar_placeholder_identity_is_not_declared',
               'test_sidecar_zero_parameters_are_not_declared'],
     # 正例用同一条域规则的合法侧（maxRetries=0）：变异只取消"取值不构成
     # 声明"的判定，不得影响合法零值的放行。
     'positive': 'test_sidecar_zero_retries_is_a_legal_declaration'},
    # P34-PR2-01：资格门禁组成（身份齐备但无可用观测/本轮有致命项不得放行）。
    {'target': '_qualification_reasons', 'kind': 'func', 'contract': 'list',
     'replacement': lambda orig: _stub_qualification_reasons,
     'probe': lambda f: f({}, None, False, []),
     'tests': ['test_merge_without_declared_identity_is_not_threshold_eligible',
               'test_empty_capture_with_sidecar_is_not_threshold_eligible',
               'test_fatal_round_elsewhere_still_blocks_threshold_eligibility',
               'test_partial_round_without_clean_run_is_not_threshold_eligible',
               'test_sidecar_identity_mismatch_is_fatal'],
     # 正例用同一函数的合法侧（身份齐备 + 有可用洁净轮 → 门槛可用）：变异只
     # 取消"不可用/有致命项"的阻断，不得把合法轮的资格判定也一并改掉。
     'positive': 'test_sidecar_declared_identity_makes_merge_threshold_eligible'},
    # P34-PR3-01a：durable 偏移逐条校验（非末条的负值/缺失/非整数不再零发现）。
    {'target': '_observed_counts', 'kind': 'func', 'contract': 'dict',
     'replacement': _mutated_observed_counts,
     'probe': lambda f: f(_fixture_group(), []),
     'tests': ['test_negative_nonterminal_durable_offset_is_fatal',
               'test_missing_nonterminal_durable_offset_is_fatal',
               'test_non_integer_nonterminal_durable_offset_is_fatal'],
     # 正例用同一函数的合法侧（durable 偏移 0 是合法 resume 起点）：变异只取消
     # "逐条域校验"，不得影响非负零偏移的放行。
     'positive': 'test_durable_zero_offsets_are_legal_resume_marks'},
    # P34-PR3-01b：首发与重传共用长度域（重传的零/负/缺长度不再零发现）。
    {'target': '_sample_off', 'kind': 'func', 'contract': 'int|None',
     'replacement': _mutated_sample_off_len_for_first_send,
     'probe': lambda f: f(L.Sample('upgrade', 'segment_retransmit', 1,
                                   {'off': '0', 'len': '0'}, 1), []),
     'tests': ['test_retransmit_zero_length_is_fatal',
               'test_retransmit_negative_length_is_fatal',
               'test_retransmit_missing_length_is_fatal'],
     # 正例用同一判据的合法侧（重传携带合法 len=128）：变异只取消"重传也要
     # 长度域"，不得影响合法重传的放行。
     'positive': 'test_legal_retransmit_keeps_block_clean'},
    # P34-PR3-01c：字节计数域必须覆盖 _sum_bytes 的两个调用方（GATT 与 platform）。
    {'target': '_sum_bytes', 'kind': 'func', 'contract': 'int|None',
     'replacement': _mutated_sum_bytes,
     'probe': lambda f: f(_fixture_group(), 'gatt_write', []),
     'tests': ['test_gatt_negative_bytes_is_fatal',
               'test_platform_negative_bytes_is_fatal'],
     # 正例用同一函数的合法侧（两侧都是非负字节数）：变异只取消取值域，不得
     # 影响合法计数的累加。
     'positive': 'test_legal_write_byte_sums_over_both_writers_are_accepted'},
    # P34-PR3-02：词法正则整串锚定（`$` 会匹配末尾换行之前的位置）。
    {'target': '_HEX64_RE', 'kind': 'func', 'contract': 'Match|None',
     'replacement': lambda orig: re.compile(r'^[0-9a-fA-F]{64}$'),
     'probe': lambda f: f.match('a' * 64),
     'tests': ['test_sidecar_package_sha_trailing_newline_is_not_declared',
               'test_lexical_regexes_reject_trailing_newline'],
     # 正例用同一域的合法侧（大写 64 位十六进制摘要）：变异只放开"末尾多出
     # 字符"，不得影响合法摘要声明。
     'positive': 'test_sidecar_uppercase_package_sha_and_zero_retries_are_legal'},
    {'target': '_INT_RE', 'kind': 'func', 'contract': 'Match|None',
     'replacement': lambda orig: re.compile(r'^-?\d+$'),
     'probe': lambda f: f.match('8'),
     'tests': ['test_lexical_regexes_reject_trailing_newline'],
     'positive': 'test_strict_contract_block_has_no_findings'},
)


def _contract_ok(name, value):
    if name == 'NoneType':
        return value is None
    if name == 'list':
        return isinstance(value, list)
    if name == 'dict':
        return isinstance(value, dict)
    if name == 'int|None':
        return value is None or (isinstance(value, int)
                                 and not isinstance(value, bool))
    if name == 'Match|None':
        return value is None or hasattr(value, 'group')
    if name == 'tuple2bool':
        return (isinstance(value, tuple) and len(value) == 2
                and all(isinstance(item, bool) for item in value))
    if name == 'Sample|None':
        return value is None or isinstance(value, L.Sample)
    raise AssertionError('未知类型契约: %s' % name)


# 每个负例"期望被检出"的检出码：变异生效后，该用例必须以这些码失败。
# 表本身可核验 —— 每个码必须在用例源码中出现（见 _expectation_codes_are_declared），
# 避免把期望写成无法追溯的口头声明。
DISCRIMINATION_EXPECT = {
    'test_quantile_tamper_is_fatal': ('QUANTILE_MISMATCH',),
    'test_quantile_check_runs_and_catches_shift': ('QUANTILE_MISMATCH',),
    'test_elapsed_tamper_is_fatal': ('INTERNAL_INCONSISTENT',),
    'test_phase_quantile_tamper_is_detected': ('QUANTILE_MISMATCH',),
    'test_getinfo_total_tamper_is_detected': ('PHASE_TOTAL_MISMATCH',),
    'test_integrity_declaration_tamper_is_fatal': ('INTEGRITY_MISMATCH',),
    'test_missing_sample_line_is_fatal': ('COUNT_MISMATCH',),
    'test_declared_count_inflation_is_fatal': ('COUNT_MISMATCH',),
    'test_bytes_tamper_is_fatal': ('COUNT_MISMATCH',),
    'test_durable_final_off_tamper_is_fatal': ('COUNT_MISMATCH',),
    'test_durable_final_off_behind_last_sample_is_warn': ('STRAGGLER',),
    'test_straggler_sample_is_warn_not_fatal': ('STRAGGLER',),
    'test_negative_us_is_fatal': ('CLOCK_NEGATIVE',),
    'test_clock_rollback_is_multi_instance_then_fatal': ('MULTI_INSTANCE',
                                                         'CLOCK_NONMONOTONIC'),
    'test_unlinked_early_ack_replay_is_fatal': ('EARLY_ACK_UNLINKED',),
    'test_early_ack_offset_mismatch_is_fatal': ('EARLY_ACK_UNLINKED',),
    'test_early_ack_cross_instance_pollution_is_detected': ('EARLY_ACK_UNLINKED',
                                                            'MULTI_INSTANCE'),
    'test_duplicate_ack_offset_is_detected': ('DUPLICATE_ACK_OFFSET',),
    'test_missing_first_send_offset_is_fatal': ('SEGMENT_OFFSET_MISSING',),
    'test_orphan_retransmit_is_detected': ('ORPHAN_RETRANSMIT',),
    'test_ack_without_segment_is_detected': ('ACK_WITHOUT_SEGMENT',),
    'test_clock_domain_mismatch_is_fatal': ('CLOCK_DOMAIN',),
    'test_unknown_schema_is_fatal': ('SCHEMA_UNKNOWN',),
    'test_missing_required_object_is_fatal': ('SCHEMA_MISSING',),
    'test_retransmit_derivation_tamper_is_fatal': ('COUNT_MISMATCH',
                                                   'INTERNAL_INCONSISTENT'),
    'test_phase_reversed_is_fatal': ('PHASE_REVERSED',),
    'test_bind_phase_tamper_is_fatal': ('INTERNAL_INCONSISTENT',),
    'test_attempt_number_rollback_is_fatal': ('MIXED_ATTEMPT',),
    'test_wrong_label_is_fatal': ('MIXED_LABEL',),
    'test_sample_level_label_mixing_is_fatal': ('MIXED_LABEL',),
    'test_missing_binding_fields_lower_strict_completeness': ('FIELD_ABSENT',),
    'test_absent_field_is_warn_not_fatal': ('FIELD_ABSENT',),
    'test_malformed_sample_is_fatal': ('MALFORMED_SAMPLE',),
    'test_unknown_kind_is_fatal': ('UNKNOWN_KIND',),
    'test_partial_ack_population_is_excluded_from_merge': ('INTEGRITY_MISMATCH',),
    'test_straggler_round_is_excluded_from_merge': ('STRAGGLER',),
    'test_excluded_rounds_keep_line_numbers_and_reasons': ("OUTCOME:'fail'",),
    'test_negative_segment_offset_is_fatal': ('SEGMENT_OFFSET_INVALID',),
    'test_zero_length_segment_is_fatal': ('SEGMENT_LENGTH_INVALID',),
    'test_missing_elapsed_timing_field_is_fatal': ('TIMING_INCOMPLETE',
                                                   'FIELD_ABSENT'),
    'test_missing_start_or_end_timing_field_is_fatal': ('TIMING_INCOMPLETE',),
    'test_success_with_null_timing_fields_is_fatal': ('TIMING_INCOMPLETE',),
    'test_success_with_zero_elapsed_is_fatal_and_excluded': ('ELAPSED_NOT_POSITIVE',),
    'test_sidecar_blank_identity_values_are_not_declared': ('GROUP_IDENTITY_INVALID',),
    'test_sidecar_placeholder_identity_is_not_declared': ('GROUP_IDENTITY_INVALID',),
    'test_sidecar_zero_parameters_are_not_declared': ('GROUP_IDENTITY_INVALID',),
    'test_merge_without_declared_identity_is_not_threshold_eligible':
        ('GROUP_IDENTITY_NOT_DECLARED',),
    'test_empty_capture_with_sidecar_is_not_threshold_eligible':
        ('NO_ELIGIBLE_RUNS',),
    'test_fatal_round_elsewhere_still_blocks_threshold_eligibility':
        ('FATAL:ELAPSED_NOT_POSITIVE',),
    'test_partial_round_without_clean_run_is_not_threshold_eligible':
        ('NO_ELIGIBLE_RUNS',),
    'test_sidecar_identity_mismatch_is_fatal': ('GROUP_IDENTITY_MISMATCH',),
    'test_negative_nonterminal_durable_offset_is_fatal': ('SEGMENT_OFFSET_INVALID',),
    'test_missing_nonterminal_durable_offset_is_fatal': ('SEGMENT_OFFSET_MISSING',),
    'test_non_integer_nonterminal_durable_offset_is_fatal':
        ('SEGMENT_OFFSET_MISSING',),
    'test_retransmit_zero_length_is_fatal': ('SEGMENT_LENGTH_INVALID',),
    'test_retransmit_negative_length_is_fatal': ('SEGMENT_LENGTH_INVALID',),
    'test_retransmit_missing_length_is_fatal': ('SEGMENT_OFFSET_MISSING',),
    'test_gatt_negative_bytes_is_fatal': ('BYTE_COUNT_INVALID',),
    'test_platform_negative_bytes_is_fatal': ('BYTE_COUNT_INVALID',),
    'test_sidecar_package_sha_trailing_newline_is_not_declared':
        ('GROUP_IDENTITY_INVALID',),
    'test_lexical_regexes_reject_trailing_newline': (
        '数字解析必须整串匹配', 'hex64 域必须整串匹配'),
}


def test_discrimination_pairs_are_type_preserving():
    """逐项施加**保持类型**的变异，负例必须抛出恰为 AssertionError。

    整改前的版本用 `except Exception` 计数：3/25 配对靠 `len(None)`
    这类运行期异常"通过"，不证明任何判据有鉴别力（P34-P07）。此处的规则：

    1. 变异必须保持被变异函数/对象的**返回类型契约**（先跑 `probe` 校验）；
    2. 同一变异下正例（严格契约块零发现）仍须通过 —— 否则失败来自夹具损坏
       而非目标判据；
    3. 负例必须抛出**恰为** `AssertionError`（不是 TypeError/IndexError 等
       运行期异常）；
    4. `finally` 恢复原函数后，负例必须恢复为通过 —— 证明失败确由该变异造成。

    每对配对记录变异点、期望检出码、实际异常类型与恢复后再跑结果，汇总打印。
    """
    module = sys.modules[__name__]
    source = open(__file__, encoding='utf-8').read()
    checked, invalid = [], []
    declared = {test for pair in DISCRIMINATION for test in pair['tests']}
    assert declared == set(DISCRIMINATION_EXPECT), \
        '期望检出码表与配对表不一致: 缺 %s 多 %s' % (
            sorted(declared - set(DISCRIMINATION_EXPECT)),
            sorted(set(DISCRIMINATION_EXPECT) - declared))
    for test_name, codes in sorted(DISCRIMINATION_EXPECT.items()):
        body = source.split('def %s(' % test_name, 1)
        assert len(body) == 2, '找不到用例源码: %s' % test_name
        for code in codes:
            assert code in body[1][:2000], \
                '用例 %s 未声明期望检出码 %s' % (test_name, code)
    for pair in DISCRIMINATION:
        name = pair['target']
        original = getattr(L, name)
        try:
            setattr(L, name, pair['replacement'](original))
            value = pair['probe'](getattr(L, name))
            if not _contract_ok(pair['contract'], value):
                invalid.append('%s：变异返回类型 %r 违反契约 %s'
                               % (name, type(value).__name__, pair['contract']))
                continue
            getattr(module, pair['positive'])()  # 同一变异下正例必须仍然通过
            for test_name in pair['tests']:
                expect = '+'.join(DISCRIMINATION_EXPECT[test_name])
                try:
                    getattr(module, test_name)()
                except AssertionError as error:
                    reason = str(error).strip().splitlines()
                    checked.append('%s -> %s | 期望=%s | 实际=AssertionError: %s '
                                   '| 恢复='
                                   % (name, test_name, expect,
                                      (reason[0] if reason else '')[:70]))
                except Exception as error:  # 运行期异常不算鉴别力
                    invalid.append('%s -> %s：抛出 %s 而非 AssertionError'
                                   % (name, test_name, type(error).__name__))
                else:
                    invalid.append('%s -> %s：变异后仍然通过，未核对声称的检出'
                                   % (name, test_name))
        finally:
            setattr(L, name, original)
        for test_name in pair['tests']:
            getattr(module, test_name)()  # 恢复后必须回到通过
    for line in checked:
        print('      鉴别力 %s通过' % line)
    assert not invalid, '鉴别力配对不合格:\n  ' + '\n  '.join(invalid)
    assert len(checked) == sum(len(p['tests']) for p in DISCRIMINATION), \
        '配对计数不符: %d' % len(checked)
    assert len(declared) == 61, '期望检出码表条目数变化，需同步复核: %d' % len(declared)


# ---------------------------------------------------------------- 收尾检查


def test_temp_artifacts_are_cleaned():
    """临时文件自净：跑完不得在解析器目录留下 `_tmp_*` 残留。"""
    leftovers = leftover_temp_files()
    if not _TEMP_FILES and not leftovers:
        return
    cleanup_temp_files()
    leftovers = leftover_temp_files()
    assert not leftovers, '临时文件未清理: %s' % leftovers


def test_module_output_paths_are_local():
    """自检产物边界：解析器模块不写任何解析器目录之外的路径。"""
    source = open(os.path.join(HERE, 'link_stats.py'), encoding='utf-8').read()
    assert 'tempfile' not in source, '解析器不得使用系统临时目录'
    assert 'os.environ' not in source, '解析器不得依赖环境变量决定输出位置'


TESTS = [
    ('夹具：逐字节切片身份与 SHA-256', test_fixture_is_verbatim_slice),
    ('正例：真实切片单实例已收口（默认+严格模式）',
     test_fixture_blocks_are_single_instance_and_closed),
    ('正例：严格契约块零发现（默认+严格模式）',
     test_strict_contract_block_has_no_findings),
    ('正例：独立重算摘要与样本行自洽', test_strict_block_counts_match_sample_lines),
    ('正例：整改前缺字段逐项申报', test_legacy_fixture_absent_fields_are_declared),
    ('P01 身份：不同设备不合并', test_mixed_devices_are_not_merged),
    ('P01 身份：不同 MTU 不合并', test_mixed_mtu_is_not_merged),
    ('P01 身份：不同写模式不合并', test_mixed_write_modes_are_not_merged),
    ('P01 身份：拆分后各组保留自身统计', test_unmerged_signature_keeps_per_group_statistics),
    ('P01 侧车：身份声明齐备 → 门槛可用',
     test_sidecar_declared_identity_makes_merge_threshold_eligible),
    ('P01 侧车：身份与观测不符 → 致命', test_sidecar_identity_mismatch_is_fatal),
    ('P01 侧车：日志未绑定 → 致命', test_sidecar_unbound_input_is_fatal),
    ('P01 侧车：声明输入 SHA 不符 → 致命', test_sidecar_declared_sha_mismatch_is_fatal),
    ('P01 侧车：身份字段不全 → 致命', test_sidecar_incomplete_identity_is_fatal),
    ('P01 侧车（PR2-02）：空/空白字段不构成声明',
     test_sidecar_blank_identity_values_are_not_declared),
    ('P01 侧车（PR2-02）：占位符不构成声明',
     test_sidecar_placeholder_identity_is_not_declared),
    ('P01 侧车（PR2-02）：零参数不构成声明',
     test_sidecar_zero_parameters_are_not_declared),
    ('P01 侧车（PR2-02）：零重试是合法声明',
     test_sidecar_zero_retries_is_a_legal_declaration),
    ('P01 侧车（PR3-02）：包 SHA 尾随换行不构成声明',
     test_sidecar_package_sha_trailing_newline_is_not_declared),
    ('P01 正例（PR3-02）：合法大写摘要 + 零重试仍构成声明',
     test_sidecar_uppercase_package_sha_and_zero_retries_are_legal),
    ('P05 范围（PR3-02）：词法正则必须整串锚定',
     test_lexical_regexes_reject_trailing_newline),
    ('P01 身份：未声明身份不得标为门槛可用',
     test_merge_without_declared_identity_is_not_threshold_eligible),
    ('P01 资格（PR2-01）：空捕获+侧车不得放行',
     test_empty_capture_with_sidecar_is_not_threshold_eligible),
    ('P01 资格（PR2-01）：本轮有致命项不得放行',
     test_fatal_round_elsewhere_still_blocks_threshold_eligibility),
    ('P01 资格（PR2-01）：仅 partial 不得放行',
     test_partial_round_without_clean_run_is_not_threshold_eligible),
    ('P01 资格（PR2-01）：分析失败不得放行',
     test_unexpected_analysis_failure_with_sidecar_is_not_threshold_eligible),
    ('P01 身份：单签名结论须带观测身份', test_single_signature_merge_reports_observed_signature),
    ('P02 归属：解析期致命项归属所在块', test_parse_fatal_is_attached_to_its_block),
    ('P02 归属：畸形样本取消块洁净资格',
     test_malformed_sample_disqualifies_its_block),
    ('P02 归属：严格模式结论不被重算洗白',
     test_strict_mode_conclusion_is_not_rechecked_in_loose_mode),
    ('P02 留痕：排除轮保留行号与理由',
     test_excluded_rounds_keep_line_numbers_and_reasons),
    ('P02 留痕：非 ok 终态记入排除而非致命',
     test_outcome_fail_is_excluded_but_not_fatal),
    ('P02 洁净：partial 覆盖不得合并',
     test_partial_ack_population_is_excluded_from_merge),
    ('P02 洁净：拖尾轮次不得合并', test_straggler_round_is_excluded_from_merge),
    ('P02 洁净：诊断池与洁净池分离', test_diagnostic_pool_is_separate_from_clean_pool),
    ('P02 真实污染块被排除且留痕', test_polluted_real_block_is_excluded_with_evidence),
    ('P03 偏移：重复确认被检出', test_duplicate_ack_offset_is_detected),
    ('P03 偏移：默认模式重复确认仅告警但取消资格',
     test_duplicate_ack_offset_is_warn_in_default_mode),
    ('P03 偏移：首发缺 off 致命', test_missing_first_send_offset_is_fatal),
    ('P03 偏移：孤儿重传被检出', test_orphan_retransmit_is_detected),
    ('P03 偏移：无段确认被检出', test_ack_without_segment_is_detected),
    ('P03 合法：重传不新增唯一段与 ACK 样本',
     test_retransmit_creates_no_new_unique_segment_or_ack_sample),
    ('P03 合法：多段共用一个确认', test_multiple_segments_share_one_ack_is_legal),
    ('P03 合法：resume 前缀不被误报为缺失段',
     test_early_ack_prefix_is_not_a_missing_segment),
    ('P04 空捕获：空文件不是成功', test_empty_capture_is_not_success),
    ('P04 空捕获：纯噪声输入不是成功', test_noise_only_capture_is_not_success),
    ('P04 收口：null 摘要不是合法收口', test_null_summary_is_not_a_closing_summary),
    ('P04 收口：非对象摘要不是合法收口',
     test_non_object_summary_is_not_a_closing_summary),
    ('P04 收口：非法收口块不得进入合并',
     test_null_summary_keeps_blocks_out_of_merge),
    ('P04 收口：破损摘要不丢弃样本',
     test_corrupt_summary_is_fatal_and_not_silently_dropped),
    ('P04 收口：未收口块告警/严格致命',
     test_unclosed_tail_block_reports_missing_summary),
    ('P04 收口：未收口统计按 label 归属',
     test_unclosed_block_samples_are_label_scoped),
    ('P05 范围：成功传输零时长非法且不合并',
     test_success_with_zero_elapsed_is_fatal_and_excluded),
    ('P05 范围：单次操作零微秒合法',
     test_legit_zero_microsecond_single_operation_is_allowed),
    ('P05 时序（PR2-04）：缺 elapsedUs 致命',
     test_missing_elapsed_timing_field_is_fatal),
    ('P05 时序（PR2-04）：缺 startUs/endAckUs 致命',
     test_missing_start_or_end_timing_field_is_fatal),
    ('P05 时序（PR2-04）：成功传输时序为 null 致命',
     test_success_with_null_timing_fields_is_fatal),
    ('P05 时序（PR2-04）：非成功终态允许 null',
     test_non_ok_round_allows_null_timing_fields),
    ('P05 范围（PR2-04）：负段偏移致命', test_negative_segment_offset_is_fatal),
    ('P05 范围（PR2-04）：零段长致命', test_zero_length_segment_is_fatal),
    ('P05 范围（PR2-04）：负阶段时间致命', test_negative_phase_timestamp_is_fatal),
    ('P05 健壮（PR2-04）：非整数阶段边界给结构化结论',
     test_non_integer_phase_bound_is_structured_not_a_traceback),
    ('P05 范围（PR3-01）：非末条 durable 负偏移致命',
     test_negative_nonterminal_durable_offset_is_fatal),
    ('P05 范围（PR3-01）：非末条 durable 缺偏移致命',
     test_missing_nonterminal_durable_offset_is_fatal),
    ('P05 范围（PR3-01）：非末条 durable 偏移非整数致命',
     test_non_integer_nonterminal_durable_offset_is_fatal),
    ('P05 范围（PR3-01）：重传零长度致命', test_retransmit_zero_length_is_fatal),
    ('P05 范围（PR3-01）：重传负长度致命', test_retransmit_negative_length_is_fatal),
    ('P05 范围（PR3-01）：重传缺长度致命', test_retransmit_missing_length_is_fatal),
    ('P05 范围（PR3-01）：GATT 负字节数致命', test_gatt_negative_bytes_is_fatal),
    ('P05 范围（PR3-01）：platform 负字节数致命',
     test_platform_negative_bytes_is_fatal),
    ('P05 正例（PR3-01）：合法重传保持洁净与门槛资格',
     test_legal_retransmit_keeps_block_clean),
    ('P05 正例（PR3-01）：durable 零偏移是合法 resume 起点',
     test_durable_zero_offsets_are_legal_resume_marks),
    ('P05 正例（PR3-01）：两类写入的合法字节和被正确累加',
     test_legal_write_byte_sums_over_both_writers_are_accepted),
    ('P05 类型：布尔不冒充整数', test_boolean_is_not_an_integer),
    ('P05 类型：非法类型给结构化结论（无 traceback）',
     test_illegal_types_yield_structured_conclusion_without_traceback),
    ('P05 重算：阶段分位数篡改被检出', test_phase_quantile_tamper_is_detected),
    ('P05 重算：getInfo.totalUs 篡改被检出', test_getinfo_total_tamper_is_detected),
    ('P05 完整性：缺绑定字段降完整性',
     test_missing_binding_fields_lower_strict_completeness),
    ('P05 完整性：无合格轮不得声称完整',
     test_strict_completeness_requires_at_least_one_clean_run),
    ('P05 完整性：字段齐全时为真',
     test_strict_completeness_is_true_for_current_contract_block),
    ('P05 完整性：旧版缺字段仍可诊断合并',
     test_legacy_absent_fields_do_not_block_diagnostic_merge),
    ('P06 早到 ACK：发射端合法输出序不报时钟回退',
     test_emitter_early_ack_shape_is_legal),
    ('P06 早到 ACK：无关联旧时间重放致命',
     test_unlinked_early_ack_replay_is_fatal),
    ('P06 早到 ACK：偏移不匹配致命', test_early_ack_offset_mismatch_is_fatal),
    ('P06 早到 ACK：跨实例挪用被检出',
     test_early_ack_cross_instance_pollution_is_detected),
    ('P06 早到 ACK：真实时钟回退仍报警',
     test_genuine_clock_rollback_is_still_reported),
    ('P06 早到 ACK：仅该 kind 除外于单调时钟',
     test_early_ack_invalid_is_excluded_from_monotonic_clock),
    ('负例·混组：摘要 label 不符 → MIXED_LABEL', test_wrong_label_is_fatal),
    ('负例·混组：样本 label 混用 → MIXED_LABEL',
     test_sample_level_label_mixing_is_fatal),
    ('负例·混组：attempts 序号回退 → MIXED_ATTEMPT',
     test_attempt_number_rollback_is_fatal),
    ('负例·错摘要：分位数篡改 → QUANTILE_MISMATCH', test_quantile_tamper_is_fatal),
    ('负例·错摘要：计数虚高 → COUNT_MISMATCH', test_declared_count_inflation_is_fatal),
    ('负例·错摘要：缺样本行 → COUNT_MISMATCH', test_missing_sample_line_is_fatal),
    ('负例·错摘要：重传派生量篡改 → 双检出',
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
    ('负例·结构：摘要 JSON 破损 → BAD_JSON + 无合法收口',
     test_bad_json_is_fatal),
    ('负例·结构：样本畸形 → MALFORMED_SAMPLE', test_malformed_sample_is_fatal),
    ('负例·结构：未知 kind → UNKNOWN_KIND', test_unknown_kind_is_fatal),
    ('负例·结构：缺必需对象 → SCHEMA_MISSING', test_missing_required_object_is_fatal),
    ('负例·字段缺失只告警 → FIELD_ABSENT(warn)', test_absent_field_is_warn_not_fatal),
    ('负例·拖尾样本只告警 → STRAGGLER(warn)', test_straggler_sample_is_warn_not_fatal),
    ('口径：nearest-rank 与冻结语义一致', test_nearest_rank_semantics),
    ('口径：分位数核对确实执行（非空转）', test_quantile_check_runs_and_catches_shift),
    ('口径：合并分位数口径一致', test_merged_quantiles_use_nearest_rank_over_clean_pool),
    ('CLI：退出码与 --json 形状', test_cli_exit_codes_and_json),
    ('CLI：--log 可重复', test_cli_accepts_multiple_logs),
    ('CLI（PR2-03）：重复输入去重且如实报告',
     test_repeated_input_is_deduplicated_and_reported),
    ('CLI（PR2-03）：同名不同目录保留来源标识',
     test_same_basename_inputs_keep_distinct_source_ids),
    ('CLI：真实切片默认/严格模式退出 0', test_cli_on_real_fixture_is_green),
    ('CLI：合并统计只纳入洁净轮', test_cli_aggregate_merges_only_clean_runs),
    ('鉴别力：保持类型的变异下负例必须失败（P34-P07）',
     test_discrimination_pairs_are_type_preserving),
    ('边界：临时文件自净', test_temp_artifacts_are_cleaned),
    ('边界：解析器不写解析器目录外路径', test_module_output_paths_are_local),
    ('可选：整份真实捕获 0 致命（无则 SKIP）', test_optional_full_capture),
]


def main():
    failed = []
    try:
        for name, fn in TESTS:
            try:
                fn()
                print('PASS  %s' % name)
            except Exception:
                failed.append(name)
                print('FAIL  %s' % name)
                traceback.print_exc()
    finally:
        removed = cleanup_temp_files()
        if removed:
            print('      已清理临时文件 %d 个' % len(removed))
        leftovers = leftover_temp_files()
        if leftovers:
            print('WARN  仍有临时文件残留: %s' % leftovers)
    print('---- selftest 总计 %d 项，失败 %d 项 ----' % (len(TESTS), len(failed)))
    if failed:
        for name in failed:
            print('FAILED: %s' % name)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
