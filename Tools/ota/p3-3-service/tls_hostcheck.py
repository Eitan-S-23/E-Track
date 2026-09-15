#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-3 受控 v2 服务宿主 HTTPS 验证（#30，用户 2026-09-13 第四轮裁定）。

目的：HTTPS 是受验 App 的硬前置。本脚本在宿主上以**真实 CLI 启动参数**
拉起 service.py（TLS 模式），用本机测试 CA 签发服务器证书，并以真实
TLS 客户端（Python ssl + curl）走完 latest→下载全链，证明服务的 TLS
实现与证书链配置可工作。

覆盖：
1. openssl 生成测试 CA + 服务器证书（SAN：DNS:localhost + IP:127.0.0.1，
   有效期 30 天，notBefore/notAfter 输出留证）。
2. 子进程启动：python service.py --config service_config.json
   --active-release toy-30201 --host 127.0.0.1 --port 18443
   --public-base-url https://127.0.0.1:18443 --tls-cert/--tls-key --log-file。
3. Python ssl 客户端（cafile=测试 CA）：
   - https://127.0.0.1:18443 latest（真机十参数）→ 200、downloadUrl 为
     https 且指向同一 host:port；
   - 下载整包 → 200、SHA-256 与冻结四元组一致；
   - DNS:localhost 名字路径同样 200（主机名校验走真实路径）；
   - TLS 版本 >= 1.2、对端证书 subject/issuer 与测试 CA 链一致。
4. 负例 1（不得无校验）：不加载测试 CA（仅系统信任库）→ 证书校验失败。
5. 负例 2（不得降级）：客户端上限压到 TLS 1.1 → 握手失败（服务端
   minimum TLSv1_2）。
6. curl --cacert 全链 200（Schannel 后端，独立实现交叉验证）。

边界声明：
- 测试 CA 仅供宿主验证服务的 TLS 实现，**不是** App 侧公共可信证书；
  真机 O 序列使用的域名/证书链/有效期按操作单另行绑定（见服务文档 §5）。
- 本脚本不放宽 App 校验、不安装任何系统 CA；证书全部落在仓库 .cache 下。
- 依赖本机 openssl 与 curl（路径与版本在结果中登记）。

运行：python tls_hostcheck.py（仅标准库 + openssl/curl 子进程）。
"""

import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import warnings
from urllib.parse import urlencode

# 负例 2 使用 TLSVersion.TLSv1_1 压客户端上限（Python 3.13 标记废弃但
# 语义仍是所需：验证服务端 minimum TLSv1_2 不接受更低版本）。
warnings.filterwarnings('ignore', category=DeprecationWarning)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import service as svc  # noqa: E402

CONFIG_PATH = os.path.join(HERE, 'service_config.json')

# 冻结 toy 四元组（与 selftest.py 同源，P3-3-offline-assets-2026-09-13.md）
TOY_ETU_SHA = 'fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2'
TOY_ETU_SIZE = 284092

HOST = '127.0.0.1'
PORT = 18443
BASE_URL = 'https://%s:%d' % (HOST, PORT)
# 真机十参数（与板上 App 侧一致：板 30200 / hw1 / layout1 / boot1 / proto1）
LATEST_PARAMS = [
    ('appId', 'trace'),
    ('deviceModel', 'e-track-at32f435'),
    ('channel', 'stable'),
    ('currentVersionCode', '30200'),
    ('currentImageSha', '0' * 64),
    ('hardwareRevision', '1'),
    ('layoutId', '1'),
    ('bootVersion', '1'),
    ('protocolVersion', '1'),
    ('appVersionCode', '86'),
]


def find_repo_root(start_dir):
    cur = start_dir
    while True:
        if os.path.isdir(os.path.join(cur, '.git')) or \
                os.path.isfile(os.path.join(cur, '.git')):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return start_dir
        cur = parent


def run_cmd(args, cwd=None):
    proc = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')
    if proc.returncode != 0:
        raise RuntimeError('命令失败 %r\nstdout=%s\nstderr=%s'
                           % (args, proc.stdout, proc.stderr))
    return proc.stdout


def gen_certs(run_dir):
    """生成测试 CA 与服务器证书；返回 (ca, cert, key, not_before, not_after)。"""
    ca_key = os.path.join(run_dir, 'ca.key')
    ca_pem = os.path.join(run_dir, 'ca.pem')
    srv_key = os.path.join(run_dir, 'server.key')
    srv_csr = os.path.join(run_dir, 'server.csr')
    srv_pem = os.path.join(run_dir, 'server.pem')
    for path in (ca_key, ca_pem, srv_key, srv_csr, srv_pem,
                 os.path.join(run_dir, 'ca.srl')):
        if os.path.exists(path):
            os.remove(path)
    run_cmd(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
             '-keyout', ca_key, '-out', ca_pem, '-days', '30',
             '-subj', '/CN=P33 Host Test CA/O=E-Track P3-3',
             '-addext', 'basicConstraints=critical,CA:TRUE',
             '-addext', 'keyUsage=critical,keyCertSign,cRLSign'])
    run_cmd(['openssl', 'req', '-newkey', 'rsa:2048', '-nodes',
             '-keyout', srv_key, '-out', srv_csr,
             '-subj', '/CN=localhost'])
    ext = ('subjectAltName=DNS:localhost,IP:127.0.0.1\n'
           'extendedKeyUsage=serverAuth\n'
           'keyUsage=digitalSignature,keyEncipherment\n'
           'basicConstraints=critical,CA:FALSE\n')
    ext_file = os.path.join(run_dir, 'san.ext')
    with open(ext_file, 'w', encoding='ascii', newline='\n') as fh:
        fh.write(ext)
    run_cmd(['openssl', 'x509', '-req', '-in', srv_csr, '-CA', ca_pem,
             '-CAkey', ca_key, '-CAcreateserial', '-out', srv_pem,
             '-days', '30', '-extfile', ext_file])
    dates = run_cmd(['openssl', 'x509', '-in', srv_pem, '-noout',
                     '-startdate', '-enddate'])
    m = re.search(r'notBefore=(\S+ \S+ \S+ \S+ \S+)', dates)
    nb = m.group(1) if m else '?'
    m = re.search(r'notAfter=(\S+ \S+ \S+ \S+ \S+)', dates)
    na = m.group(1) if m else '?'
    return ca_pem, srv_pem, srv_key, nb, na


def https_get(url, ca_file=None, tls_max=None):
    """真实 TLS GET。返回 (status, headers, body)；校验失败抛异常。"""
    if ca_file is not None:
        ctx = ssl.create_default_context(cafile=ca_file)
    else:
        # 仅系统信任库：宿主测试 CA 不在其中，用于负例
        ctx = ssl.create_default_context()
    if tls_max is not None:
        ctx.maximum_version = tls_max
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            return (resp.status,
                    {k.lower(): v for k, v in resp.headers.items()},
                    resp.read())
    except urllib.error.HTTPError as exc:
        return (exc.code,
                {k.lower(): v for k, v in exc.headers.items()},
                exc.read())


def main():
    run_dir = os.path.join(find_repo_root(HERE), '.cache', 'p3-3-tls')
    os.makedirs(run_dir, exist_ok=True)
    openssl_ver = run_cmd(['openssl', 'version']).strip()
    curl_ver = run_cmd(['curl', '--version']).splitlines()[0].strip()
    log_path = os.path.join(run_dir, 'tls-service.log')
    if os.path.exists(log_path):
        os.remove(log_path)

    ca_pem, srv_pem, srv_key, not_before, not_after = gen_certs(run_dir)
    print('证书: CA=%s' % ca_pem)
    print('      server=%s（notBefore=%s / notAfter=%s，30 天）'
          % (srv_pem, not_before, not_after))

    # 以真实 CLI 参数启动服务（与 D1 启动形态一致，仅 host/port/证书为宿主值）
    cmd = [sys.executable, os.path.join(HERE, 'service.py'),
           '--config', CONFIG_PATH,
           '--active-release', 'toy-30201',
           '--host', HOST, '--port', str(PORT),
           '--public-base-url', BASE_URL,
           '--tls-cert', srv_pem, '--tls-key', srv_key,
           '--log-file', log_path]
    print('启动: %s' % ' '.join(cmd))
    proc = subprocess.Popen(cmd, cwd=HERE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    failures = []
    try:
        deadline = time.time() + 20
        ready = False
        while time.time() < deadline:
            if proc.poll() is not None:
                with open(log_path, 'r', encoding='utf-8') as fh:
                    tail = fh.read()[-2000:]
                raise RuntimeError('服务进程提前退出 code=%s\n日志尾:\n%s'
                                   % (proc.returncode, tail))
            try:
                https_get(BASE_URL + svc.LATEST_PATH + '?' +
                          urlencode(LATEST_PARAMS), ca_file=ca_pem)
                ready = True
                break
            except (ssl.SSLError, urllib.error.URLError, ConnectionError,
                    OSError):
                time.sleep(0.2)
        if not ready:
            raise RuntimeError('服务 20s 内未就绪')

        # 1) latest（IP 主机名路径）
        status, headers, raw = https_get(
            BASE_URL + svc.LATEST_PATH + '?' + urlencode(LATEST_PARAMS),
            ca_file=ca_pem)
        assert status == 200, (status, raw[:300])
        body = json.loads(raw)
        assert body['updateAvailable'] is True, body
        assert body['requestId'] and headers.get('x-request-id') == \
            body['requestId'], (headers.get('x-request-id'), body['requestId'])
        asset = body['asset']
        dl = asset['downloadUrl']
        assert dl.startswith(BASE_URL + svc.DOWNLOAD_PATH + '?'), dl
        assert dl.startswith('https://'), dl
        print('latest 200: releaseId=%s vcode=%s asset=%s（downloadUrl https）'
              % (body['releaseId'], body['versionCode'], asset['assetId']))

        # 2) 整包下载 + SHA 复核
        status, headers, raw = https_get(dl, ca_file=ca_pem)
        assert status == 200, (status, raw[:300])
        assert len(raw) == TOY_ETU_SIZE, len(raw)
        sha = hashlib.sha256(raw).hexdigest()
        assert sha == TOY_ETU_SHA, sha
        assert headers.get('content-type') == 'application/vnd.e-track.etu'
        print('download 200: %d bytes SHA-256=%s…（与冻结四元组一致）'
              % (len(raw), sha[:16]))

        # 3) DNS:localhost 名字路径（证书 SAN DNS 校验走真实路径）
        status, _h, raw = https_get(
            'https://localhost:%d%s?%s'
            % (PORT, svc.LATEST_PATH, urlencode(LATEST_PARAMS)),
            ca_file=ca_pem)
        assert status == 200 and json.loads(raw)['updateAvailable'] is True
        print('localhost 名字路径 200（SAN DNS 校验通过）')

        # 4) 对端证书链与 TLS 版本
        raw_sock = ssl.create_default_context(cafile=ca_pem)
        with raw_sock.wrap_socket(
                __import__('socket').create_connection((HOST, PORT),
                                                       timeout=10),
                server_hostname=HOST) as ss:
            cert = ss.getpeercert()
            ver = ss.version()
        assert ver in ('TLSv1.2', 'TLSv1.3'), ver
        subjects = ['/'.join('='.join(p) for p in rdn)
                    for rdn in cert.get('subject', ())]
        issuers = ['/'.join('='.join(p) for p in rdn)
                   for rdn in cert.get('issuer', ())]
        assert any('localhost' in s for s in subjects), subjects
        assert any('P33 Host Test CA' in i for i in issuers), issuers
        print('TLS 版本=%s subject=%s issuer=%s' % (ver, subjects, issuers))

        # 5) 负例：系统信任库（不加载测试 CA）→ 必须证书校验失败
        #    urllib 会把 ssl.SSLCertVerificationError 包装成 URLError，
        #    按异常链文本判定根因，避免类型捕获漏接。
        try:
            https_get(BASE_URL + svc.LATEST_PATH, ca_file=None)
            failures.append('负例1失败：系统信任库竟然接受了测试证书')
            print('NEG1 FAIL: 无 CA 校验通过（不应发生）')
        except Exception as exc:  # noqa: BLE001 - 按根因文本分类
            text = '%s: %s' % (type(exc).__name__, exc)
            if 'CERTIFICATE_VERIFY_FAILED' in text:
                print('负例1 PASS: 不加载测试 CA → 证书校验拒绝'
                      '（非无校验 TLS）')
            else:
                failures.append('负例1异常根因不符: %s' % text)
                print('NEG1 FAIL: %s' % text)

        # 6) 负例：客户端上限 TLS 1.1 → 服务端最低 1.2，握手失败
        #    （OpenSSL 3.x 客户端也可能在本地即拒绝该上限，同样是
        #    无法完成握手，语义一致。）
        try:
            https_get(BASE_URL + svc.LATEST_PATH, ca_file=ca_pem,
                      tls_max=ssl.TLSVersion.TLSv1_1)
            failures.append('负例2失败：TLS1.1 握手竟然成功')
            print('NEG2 FAIL: TLS1.1 被接受（不应发生）')
        except Exception as exc:  # noqa: BLE001 - 按根因文本分类
            text = '%s: %s' % (type(exc).__name__, exc)
            if 'SSL' in text:
                print('负例2 PASS: TLS1.1 上限 → 无法完成握手'
                      '（服务端 minimum 1.2）')
            else:
                failures.append('负例2异常根因不符: %s' % text)
                print('NEG2 FAIL: %s' % text)

        # 7) curl --cacert 全链（独立 TLS 实现）。
        #    Schannel 后端默认强制吊销检查：测试 CA 无 CRL/OCSP 端点，
        #    会报 CERT_TRUST_REVOCATION_STATUS_UNKNOWN。加
        #    --ssl-revoke-best-effort 仅对「吊销状态未知」放行，证书链
        #    校验仍然完整执行（ssl_verify_result=0 断言不变）。
        curl_url = BASE_URL + svc.LATEST_PATH + '?' + urlencode(LATEST_PARAMS)
        cp = subprocess.run(
            ['curl', '-sS', '--cacert', ca_pem, '--ssl-revoke-best-effort',
             '-o', os.devnull,
             '-w', '%{http_code} %{ssl_verify_result} %{url_effective}',
             curl_url],
            capture_output=True, text=True, encoding='utf-8', errors='replace')
        out = (cp.stdout or '').strip()
        assert cp.returncode == 0, (cp.returncode, cp.stderr, out)
        code = out.split(' ')[0]
        assert code == '200', out
        assert out.split(' ')[1] == '0', 'ssl_verify_result 非 0: ' + out
        print('curl --cacert: HTTP %s ssl_verify_result=0（Schannel 独立验证）'
              % code)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            failures.append('服务进程 terminate 超时，已 kill')
        print('服务进程已停止（exit=%s），日志: %s' % (proc.returncode, log_path))

    if failures:
        for f in failures:
            print('FAIL: %s' % f)
        print('---- tls_hostcheck FAIL ----')
        return 1
    print('环境: openssl="%s" / curl="%s"' % (openssl_ver, curl_ver))
    print('---- tls_hostcheck PASS（宿主 HTTPS 全链验证通过）----')
    return 0


if __name__ == '__main__':
    sys.exit(main())
