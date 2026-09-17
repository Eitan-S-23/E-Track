"""P3-4 解析器整改（PR2 批次）CLI 反例输入生成器（确定性、可重放）。

本脚本生成三类 CLI 反例输入，供 `cli-index-pr2.txt` 中的命令使用：

1. sidecar-empty-capture.json —— 身份声明齐备，但绑定的是空捕获（0 字节）：
   用于复现复审 P34-PR2-01「空捕获 + 合法侧车仍被放行」。
2. sidecar-empty-identity.json —— 绑定真实切片，但身份字段全为空串/0：
   用于复现 P34-PR2-02「空身份被视为齐备」。
3. pr2-numeric-tamper.log —— 从 fixtures/round6-ubuntu-head.log 派生，注入
   四类数值缺陷（删 elapsedUs、负段偏移、零段长、负阶段时间）：
   用于复现 P34-PR2-04「删除 elapsedUs / 负偏移 / 零段长 / 负阶段时间零发现通过」。

确定性约束：输出只取决于冻结输入（fixtures/round6-ubuntu-head.log 与
sidecar-ok.json），重复运行不改变字节；脚本绝不覆盖已存在且内容不同的文件。
"""

import hashlib
import json
import os
import sys

EV = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(EV, '..', '..', '..'))
FIXTURE = os.path.join(ROOT, 'Tools', 'ota', 'p3-4-link-stats', 'fixtures',
                       'round6-ubuntu-head.log')
SIDECAR_OK = os.path.join(EV, 'sidecar-ok.json')
TAMPER = os.path.join(EV, 'pr2-numeric-tamper.log')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def write_once(path, data):
    """只在目标不存在（或字节完全相同）时写出；内容不同则拒绝覆盖。"""
    if os.path.exists(path):
        current = open(path, 'rb').read()
        if current == data:
            print('已存在且字节一致：%s' % os.path.basename(path))
            return
        raise SystemExit('拒绝覆盖内容不同的既有文件：%s' % path)
    with open(path, 'xb') as handle:
        handle.write(data)
    print('已生成：%s' % os.path.basename(path))


def identity_from_ok():
    payload = json.loads(open(SIDECAR_OK, 'rb').read().decode('utf-8'))
    return payload['identity']


def make_sidecar_empty_capture():
    empty = os.path.join(EV, 'empty-capture.log')
    data = open(empty, 'rb').read()
    assert len(data) == 0, '空捕获夹具必须为 0 字节，实际 %d' % len(data)
    payload = {
        'groupId': 'p3-4-remediation-empty-capture',
        'identity': identity_from_ok(),
        'inputs': [{'name': 'empty-capture.log', 'sha256': sha256(data)}],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    write_once(os.path.join(EV, 'sidecar-empty-capture.json'),
               text.encode('utf-8') + b'\n')


def make_sidecar_empty_identity():
    fixture = open(FIXTURE, 'rb').read()
    identity = identity_from_ok()
    # 身份字段全部置空/置零：文本域空串、参数域 0。这类取值不构成"已声明"，
    # 必须由 GROUP_IDENTITY_INVALID 拦下（PR2-02）。
    for key, value in list(identity.items()):
        identity[key] = '' if isinstance(value, str) else 0
    payload = {
        'groupId': 'p3-4-remediation-empty-identity',
        'identity': identity,
        'inputs': [{'name': os.path.basename(FIXTURE), 'sha256': sha256(fixture)}],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    write_once(os.path.join(EV, 'sidecar-empty-identity.json'),
               text.encode('utf-8') + b'\n')


def make_numeric_tamper():
    data = open(FIXTURE, 'rb').read()
    assert data.count(b'\r\n') == 0, '夹具为 LF 文件，派生必须保持 LF'
    lines = data.split(b'\n')

    # 1) 删除最后一条收口的 transfer.elapsedUs（缺字段绕过正时长核对）。
    stats_indexes = [i for i, line in enumerate(lines)
                     if line.strip().startswith(b'OTA_LINK_STATS')]
    last = stats_indexes[-1]
    prefix = b'OTA_LINK_STATS '
    payload = json.loads(lines[last].strip()[len(prefix):].decode('utf-8'))
    assert 'elapsedUs' in payload['transfer'], '摘要缺少 elapsedUs，夹具已变'
    del payload['transfer']['elapsedUs']
    lines[last] = prefix + json.dumps(
        payload, ensure_ascii=False, sort_keys=True).encode('utf-8')

    # 2) 负段偏移与 3) 零段长分别落在两条不同样本上：`_sample_off` 对同一条
    #    样本在首个缺陷处返回，同一行注入两种缺陷会互相遮蔽。`len` 只在
    #    segment_first_send 上被要求（segment_retransmit 只核对 off）。
    # 4) 负阶段时间写进 phases.bind 起点（阶段是"块内相对时间"，不可能为负）。
    negative_off_done = zero_len_done = False
    for i, line in enumerate(lines):
        text = line.decode('utf-8')
        if not text.strip().startswith('OTA_LINK_SAMPLE'):
            continue
        if not negative_off_done and 'kind=segment_first_send' in text \
                and ' off=0 len=128' in text:
            lines[i] = line.replace(b' off=0 len=128', b' off=-128 len=128')
            negative_off_done = True
        elif negative_off_done and not zero_len_done \
                and 'kind=segment_first_send' in text \
                and ' off=128 len=128' in text:
            lines[i] = line.replace(b' off=128 len=128', b' off=128 len=0')
            zero_len_done = True
    assert negative_off_done, '未找到可注入负偏移的 segment_first_send 样本'
    assert zero_len_done, '未找到可注入零段长的 segment_first_send 样本'

    # 4) 负阶段时间写进**最后一条带 phases 的收口**（夹具末条收口的 phases 为
    #    空字典，注入点必须前移一条）；阶段是"块内相对时间"，不可能为负。
    phase_index = None
    for i in reversed(stats_indexes):
        candidate = json.loads(lines[i].strip()[len(prefix):].decode('utf-8'))
        bounds = candidate.get('phases', {}).get('bind')
        if isinstance(bounds, list) and bounds:
            phase_index = i
            break
    assert phase_index is not None, '夹具中没有任何带 phases.bind 的收口'
    payload = json.loads(lines[phase_index].strip()[len(prefix):].decode('utf-8'))
    payload['phases']['bind'][0] = -1
    lines[phase_index] = prefix + json.dumps(
        payload, ensure_ascii=False, sort_keys=True).encode('utf-8')

    write_once(TAMPER, b'\n'.join(lines))


make_sidecar_empty_capture()
make_sidecar_empty_identity()
make_numeric_tamper()

print('输入摘要：')
for name in ('empty-capture.log', 'sidecar-empty-capture.json',
             'sidecar-empty-identity.json', 'pr2-numeric-tamper.log'):
    path = os.path.join(EV, name)
    data = open(path, 'rb').read()
    print('  %-32s %8d bytes sha256=%s' % (name, len(data), sha256(data)))
sys.exit(0)
