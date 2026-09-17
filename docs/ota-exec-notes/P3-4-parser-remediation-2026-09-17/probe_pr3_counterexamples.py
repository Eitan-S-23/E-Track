"""P34-PR3-01/PR3-02 反例与对照探针（只读构造，不写解析器目录以外的任何路径）。

逐项打印 fatalities / 全量检出码 / runs / 身份侧车结论，用于把新自测的期望值
写成"实测且可解释"的精确集合，而不是照抄报告里的口头描述。

证据归档：本脚本 stdout 固化为同目录 `pr3-counterexample-probe.txt`。
运行方式（cwd = 仓库根，工作树根）：

    python -X utf8 -S -B \
      docs/ota-exec-notes/P3-4-parser-remediation-2026-09-17/probe_pr3_counterexamples.py

与 CLI 证据的分工：CLI 用例把六类缺陷合并进一份日志，验证端到端退出码与
资格门禁；本探针把每类缺陷单独注入，逐条给出"恰好命中哪一个码"，与复审
numeric-neighbors.json 的复现粒度一致。
"""
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(ROOT, 'Tools', 'ota', 'p3-4-link-stats'))

import selftest as S  # noqa: E402


def base_lines():
    lines, _ = S.real_block(0)
    return list(lines)


def replace_first(lines, needle, replacement):
    for index, line in enumerate(lines):
        if needle in line:
            lines[index] = line.replace(needle, replacement, 1)
            return lines
    raise AssertionError('构造失效：找不到 %r' % needle)


def report_of(lines, tag):
    report, findings = S.aggregate_of(S.block_text(lines))
    print('%-34s fatal=%s warn=%s runs=%s' % (
        tag, S.fatalities(findings),
        sorted({f.code for f in findings if f.severity == 'warn'}),
        report['runs']))
    for finding in findings:
        print('      %s' % finding)


def identity_probe(tag, **overrides):
    text = S.strict_block_text()
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    code, payload, log_path, group_path = S.run_with_sidecar(
        text, S.identity_payload(digest, **overrides))
    try:
        invalid = [f for f in payload['findings']
                   if f['code'] == 'GROUP_IDENTITY_INVALID']
        print('%-34s exit=%s invalid=%d eligible=%s' % (
            tag, code, len(invalid), payload['report']['eligibleForThreshold']))
        for finding in invalid:
            print('      %s | %s' % (finding['detail'], finding['line']))
        print('      reasons=%s' % payload['report']['ineligibleReasons'])
    finally:
        S.drop_temp(log_path)
        S.drop_temp(group_path)


print('=== 对照：基线块本身 ===')
report_of(base_lines(), 'baseline')

print()
print('=== P34-PR3-01a 非末条 durable 偏移域 ===')
report_of(replace_first(base_lines(), 'kind=durable us=6177 off=0',
                        'kind=durable us=6177 off=-1'), 'durable off=-1')
report_of(replace_first(base_lines(), 'kind=durable us=6177 off=0',
                        'kind=durable us=6177'), 'durable off 缺失')
report_of(replace_first(base_lines(), 'kind=durable us=6177 off=0',
                        'kind=durable us=6177 off=bad'), 'durable off=bad')

print()
print('=== P34-PR3-01b 重传段长度域 ===')
RT = 'OTA_LINK_SAMPLE label=upgrade kind=segment_retransmit us=16850 off=0 len=128'
lines = base_lines() + [RT]
report_of(lines, '重传 len=128（对照）')
lines = base_lines() + [RT.replace('len=128', 'len=0')]
report_of(lines, '重传 len=0')
lines = base_lines() + [RT.replace('len=128', 'len=-1')]
report_of(lines, '重传 len=-1')
lines = base_lines() + [RT.replace(' len=128', '')]
report_of(lines, '重传 len 缺失')
lines = base_lines() + [RT.replace('len=128', 'len=bad')]
report_of(lines, '重传 len=bad')

print()
print('=== P34-PR3-01c 字节计数域（GATT 与 platform 两个调用方） ===')
lines = replace_first(base_lines(), 'kind=gatt_write us=0 bytes=10',
                      'kind=gatt_write us=0 bytes=-1')
report_of(lines, 'GATT bytes=-1')
PW = 'OTA_LINK_SAMPLE label=upgrade kind=platform_write us=16860 bytes=100'
lines = base_lines() + [PW]
report_of(lines, 'platform bytes=100（对照）')
PW_NEG = 'OTA_LINK_SAMPLE label=upgrade kind=platform_write us=16860 bytes=-5'
PW_POS = 'OTA_LINK_SAMPLE label=upgrade kind=platform_write us=16870 bytes=5'
lines = base_lines() + [PW_NEG, PW_POS]
report_of(lines, 'platform bytes=-5,+5（净零）')

print()
print('=== P34-PR3-02 包 SHA 尾随换行 ===')
identity_probe('sha = A*64 + \\n', packageSha256='A' * 64 + '\n')
identity_probe('sha = A*64（大写对照）', packageSha256='A' * 64, maxRetries=0)
identity_probe('sha = A*64 + \\r\\n', packageSha256='A' * 64 + '\r\n')
identity_probe('sha = G*64（非十六进制）', packageSha256='G' * 64)

print()
print('=== 遗留临时文件 ===')
print(S.leftover_temp_files())
