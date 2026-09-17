"""P3-4 解析器整改（PR3 批次）CLI 反例输入生成器（确定性、可重放）。

本脚本生成三类 CLI 反例输入，供 `cli-index.txt` 中 PR3 用例使用：

1. pr3-numeric-tamper.log —— 从 fixtures/round6-ubuntu-head.log 派生，同时注入
   复审 P34-PR3-01 的六类样本数值域缺陷：

   - 非末条 durable 偏移为负（run1 首条 durable 0 → -1）
   - 末条 durable 偏移缺失（run1 第二条 durable 去掉 off）
   - 非末条 durable 偏移非整数（run2 首条 durable 0 → bad）
   - 重传段长度为零 / 为负 / 缺失（追加三条引用已发送偏移的重传样本）

2. sidecar-package-sha-trailing-lf.json —— 身份其余字段与 sidecar-ok.json 相同，
   仅 packageSha256 为 64 位十六进制 + LF（解码后 65 字符）：复现 P34-PR3-02。

3. sidecar-package-sha-uppercase.json —— packageSha256 为合法大写摘要且
   maxRetries=0：PR3-02 的合法对照，必须仍然门槛可用。

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
TAMPER = os.path.join(EV, 'pr3-numeric-tamper.log')

# 六类缺陷的注入点（夹具的 durable 序列：run1 为 6177/0、16841/1024，
# run2 为 3280/0、13217/1024；末条 13217 保持合法，作为"合法末条"对照）。
DURABLE_NEGATIVE = b'kind=durable us=6177 off=0'
DURABLE_NEGATIVE_NEW = b'kind=durable us=6177 off=-1'
DURABLE_MISSING = b'kind=durable us=16841 off=1024'
DURABLE_MISSING_NEW = b'kind=durable us=16841'
DURABLE_TEXT = b'kind=durable us=3280 off=0'
DURABLE_TEXT_NEW = b'kind=durable us=3280 off=bad'
GATT_FIRST = b'kind=gatt_write us=0 bytes=10'
GATT_FIRST_NEW = b'kind=gatt_write us=0 bytes=-1'

# 追加样本：三条重传分别引用已发送偏移 0/128/256；两条 platform 写入净零，
# 使重算出的声明合计仍为合法值，只有非负字节域判据会被触发。
APPENDED = [
    (b'kind=segment_first_send us=12581 off=896 len=128',
     [b'OTA_LINK_SAMPLE label=upgrade kind=segment_retransmit us=16000 '
      b'off=0 len=0',
      b'OTA_LINK_SAMPLE label=upgrade kind=segment_retransmit us=16010 '
      b'off=128 len=-1',
      b'OTA_LINK_SAMPLE label=upgrade kind=segment_retransmit us=16020 '
      b'off=256',
      b'OTA_LINK_SAMPLE label=upgrade kind=platform_write us=16030 '
      b'bytes=-5',
      b'OTA_LINK_SAMPLE label=upgrade kind=platform_write us=16040 bytes=5']),
]


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


def make_numeric_tamper():
    data = open(FIXTURE, 'rb').read()
    assert data.count(b'\r\n') == 0, '夹具为 LF 文件，派生必须保持 LF'
    lines = data.split(b'\n')

    replacements = [
        (DURABLE_NEGATIVE, DURABLE_NEGATIVE_NEW, '非末条 durable 负偏移'),
        (DURABLE_MISSING, DURABLE_MISSING_NEW, '末条 durable 缺偏移'),
        (DURABLE_TEXT, DURABLE_TEXT_NEW, '非末条 durable 非整数偏移'),
        (GATT_FIRST, GATT_FIRST_NEW, 'GATT 负字节数'),
    ]
    for old, new, label in replacements:
        hit = [i for i, line in enumerate(lines) if old in line]
        assert hit, '注入点 %s 未命中，夹具已变' % label
        # 只改第一处命中：`bytes=10` 这类取值在夹具中出现多次，注入点必须
        # 固定为"首条"，否则同一缺陷的落点会随夹具副本漂移。
        lines[hit[0]] = lines[hit[0]].replace(old, new, 1)
        print('  注入 %s：第 %d 行（该取值共 %d 处）' % (label, hit[0] + 1,
                                                     len(hit)))

    for anchor, appended in APPENDED:
        hit = [i for i, line in enumerate(lines) if anchor in line]
        assert len(hit) == 1, '追加锚点命中 %d 处，夹具已变' % len(hit)
        lines[hit[0] + 1:hit[0] + 1] = appended

    write_once(TAMPER, b'\n'.join(lines))


def make_sidecar(name, group_id, package_sha, max_retries):
    fixture = open(FIXTURE, 'rb').read()
    identity = identity_from_ok()
    identity['packageSha256'] = package_sha
    identity['maxRetries'] = max_retries
    payload = {
        'groupId': group_id,
        'identity': identity,
        'inputs': [{'name': os.path.basename(FIXTURE),
                    'sha256': sha256(fixture)}],
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    write_once(os.path.join(EV, name), text.encode('utf-8') + b'\n')


make_numeric_tamper()
make_sidecar('sidecar-package-sha-trailing-lf.json',
             'p3-4-remediation-package-sha-trailing-lf',
             'A' * 64 + '\n', 3)
make_sidecar('sidecar-package-sha-uppercase.json',
             'p3-4-remediation-package-sha-uppercase',
             'ABCDEF0123456789' * 4, 0)

print('输入摘要：')
for name in ('pr3-numeric-tamper.log', 'sidecar-package-sha-trailing-lf.json',
             'sidecar-package-sha-uppercase.json'):
    path = os.path.join(EV, name)
    data = open(path, 'rb').read()
    print('  %-38s %8d bytes sha256=%s' % (name, len(data), sha256(data)))
sys.exit(0)
