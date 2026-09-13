#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-3 受控 v2 测试服务宿主自测（冻结源码 v2 配套，#24 交付 + #27-#29 回归）。

覆盖矩阵（对齐 `docs/ota-cross-system-contracts.md` 冻结契约与本卡 App 端
`ota_firmware_latest.dart` / `ota_download.dart` 的 fail-closed 解析器）：

1. token v2 黄金向量（XC-TOKEN-V2-GOLDEN）：独立复算 HMAC hex 与 Base64URL、
   规范消息 67 字节、query 参数顺序与契约逐字节一致、verify 路径接受黄金
   token、expiresAt 排他过期边界（>= 即过期）。
   注：黄金向量是 patch token；本服务 fixture 为 full-only（本卡语义子集），
   故黄金向量在 sign/verify 单元层验证，不经过 full-only 的 release 配置。
2. 配置加载 fail-closed：真实配置身份核验通过；篡改 sha/size/路径、指针
   指向未知或 archived release、非 300 TTL、kind=patch 全部拒绝启动。
3. latest 参数校验（十参数闭集合、重复/未知/缺失、各数值域、appId/
   deviceModel/channel/currentImageSha 形态）。
4. latest 业务语义：未发布 NO_UPDATE 精简体、stopped CHANNEL_STOPPED、
   toy 激活后 30200→true 30201、30201/30202 对 toy NO_UPDATE、真包激活后
   30201→true 30202；App 门禁（426）先于兼容链（409）；四维度兼容链顺序
   hardware→layout→Boot→protocol 且各自错误体字段名与 App 读取键一致、
   不折叠成 UNKNOWN_DEVICE_MODEL/NO_UPDATE；真机参数组合（hw/layout/
   boot/proto=1、app 86）必然通过。
5. download token：八参数精确集合（缺失/未知/重复/空值）、签名篡改、
   keyVersion/tokenVersion/purpose/kind 拒绝、过期。
6. 下载可见性：未激活 release → 410 ASSET_DISABLED；archived → 409
   ASSET_ARCHIVED；未知 releaseId → 404；激活切换后旧 URL 作废（410）。
7. Range/If-Range：200 完整头集（含 RFC 9530 Content-Digest 复算）、
   206 头集与字节正确性、If-Range 失配回退 200、416（含 Content-Length，
   App drain 不挂起）、闭合区间/suffix/非十进制 Range → 400、206 省略
   Content-Digest（契约允许）。
8. App 解析器镜像（Python 重实现关键 fail-closed 判定）：true 响应逐字段
   （fileName 正则/sizeBytes 域/full 的 baseVersionCode=0 且
   baseImageSha256 键存在值 null/downloadUrl 绝对 https）、false 精简体
   不含 asset、426/409 错误体字段。
   注：镜像是宿主自测辅助，**不构成真实 Dart consumer 验证**（用户第四轮
   裁定口径；真实 App 消费行为由 O 序列真机观测覆盖）。
9. 线级回环：ThreadingHTTPServer + urllib 真实 HTTP 请求（latest→下载→
   断点续传→416→401 篡改签名）。
10. fail-closed 启动语义整体：ServiceConfigError 拒绝构造（等价拒绝启动）。

v2 回归新增（用户 2026-09-13 第四轮裁定，原 13 项保留不改写）：

11. 协议门禁补齐：protocolVersion 不低于 release.minProtocolVersion 但
    不在服务受支持集合（当前仅 1）→ 409 PROTOCOL_UNSUPPORTED；协议 1
    正常通过；低于最低版本仍拒绝（双臂对照）。
12. token kind 与资产类型不符（签名有效，为 full 资产签 kind=patch）→
    401 TOKEN_INVALID（错误体含 tokenKind/assetKind）；对照：签名有效、
    kind=full 但 assetId 不存在 → 仍为 404 RELEASE_NOT_FOUND。
13. 线级 requestId 三方一致：成功 latest / 错误 401 / 下载 200 三场景，
    响应头 X-Request-Id == 响应体 requestId == 请求日志 req=；同时断言
    请求日志中签名 URL 参数已脱敏（signature=<redacted>，无明文签名），
    外加 redact_path_for_log 的单元形态（多参数/无签名/空值）。

运行：python selftest.py（仅标准库；从本文件所在目录或任意 cwd 均可）。
"""

import base64
import copy
import hashlib
import hmac
import json
import logging
import os
import re
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qsl, urlencode, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import service as svc  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, 'service_config.json')

# ---- XC-TOKEN-V2-GOLDEN 黄金向量（冻结契约值，docs/ota-cross-system-contracts.md）----
GOLDEN_KEY_HEX = ('000102030405060708090a0b0c0d0e0f'
                  '101112131415161718191a1b1c1d1e1f')
GOLDEN_KEY_VERSION = 7
GOLDEN_ASSET_ID = 'asset-patch-20801'
GOLDEN_RELEASE_ID = 'release-20801'
GOLDEN_EXPIRES_AT = '1800000300'
GOLDEN_SIGNATURE = 'DmjZ33S6hz_9jrbUtdv_BqGNvOY4GCjNJqIcBpvZuzU'
GOLDEN_HMAC_HEX = ('0e68d9df74ba873ffd8eb6d4b5dbff06'
                   'a18dbce6381828cd26a21c069bd9bb35')
GOLDEN_QUERY = ('tokenVersion=2&assetId=asset-patch-20801&releaseId='
                'release-20801&kind=patch&purpose=public-ota&expiresAt='
                '1800000300&keyVersion=7&signature=' + GOLDEN_SIGNATURE)

# ---- 冻结资产四元组（P3-3-offline-assets-2026-09-13.md）----
TOY_ETU_SHA = 'fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2'
TOY_ETU_SIZE = 284092
TOY_IMAGE_SHA = '43ee943a185f63d70284c7c5a9992d677a9bf8c518dacd2e63df8ec7e5809b55'
REAL_ETU_SHA = '0a2eb26a481d8c462b5316a67a151c8241de354d00797fa22f11e77056538ce5'
REAL_ETU_SIZE = 284112
REAL_IMAGE_SHA = 'c958221392fade8b40520df2d7fd4278632d64bcdd8261b0ac7536c6468a7f39'

SHA256_HEX_RE = re.compile(r'^[0-9a-f]{64}$')
FILE_NAME_RE = re.compile(r'^[A-Za-z0-9._-]+$')


# ---- 构造辅助 ----

def load_real_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def make_state(config=None, active=None, now_fn=None):
    cfg = config if config is not None else load_real_config()
    return svc.V2ServiceState(cfg, HERE, active_release=active,
                              now_fn=now_fn or (lambda: 1800000000))


def latest_pairs(current_vcode=30200, app_vcode=86, hw=1, layout=1,
                 boot=1, proto=1, device_model='e-track-at32f435',
                 channel='stable', app_id='trace',
                 image_sha='0' * 64, extra=None, drop=None):
    pairs = [
        ('appId', app_id),
        ('deviceModel', device_model),
        ('channel', channel),
        ('currentVersionCode', str(current_vcode)),
        ('currentImageSha', image_sha),
        ('hardwareRevision', str(hw)),
        ('layoutId', str(layout)),
        ('bootVersion', str(boot)),
        ('protocolVersion', str(proto)),
        ('appVersionCode', str(app_vcode)),
    ]
    if drop:
        pairs = [p for p in pairs if p[0] not in drop]
    if extra:
        pairs = pairs + extra
    return pairs


def call_latest(state, pairs):
    """调用 latest，ServiceError 转为 (status, body_dict)。"""
    try:
        status, _headers, body = state.handle_latest(pairs)
        return status, json.loads(body)
    except svc.ServiceError as exc:
        return exc.http_status, _error_to_dict(exc)


def _error_to_dict(exc):
    d = {'errorCode': exc.error_code, 'message': exc.message,
         'requestId': exc.request_id}
    d.update(exc.extra_fields)
    return d


def call_download(state, query_pairs, range_header=None, if_range=None):
    try:
        status, headers, body = state.handle_download(
            query_pairs, range_header, if_range)
        return status, dict(headers), body
    except svc.ServiceError as exc:
        return exc.http_status, {}, json.dumps(
            _error_to_dict(exc), ensure_ascii=True).encode('utf-8')


def url_query_pairs(url):
    return parse_qsl(urlsplit(url).query, keep_blank_values=True)


def get_latest_asset(state, current_vcode):
    status, body = call_latest(state, latest_pairs(current_vcode))
    assert status == 200, (status, body)
    assert body['updateAvailable'] is True, body
    return body['asset']


def sign_url_for(state, release_key):
    """绕过 latest 直接为指定 release 签发下载 URL（可见性/归档测试用）。"""
    rel = state.releases[release_key]
    expires_at = int(state.now_fn()) + svc.TOKEN_TTL_SECONDS
    signature = svc.sign_token_v2(
        state.token_key, rel.asset.asset_id, rel.release_id, rel.asset.kind,
        'public-ota', expires_at, state.key_version)
    query = urlencode({
        'tokenVersion': '2',
        'assetId': rel.asset.asset_id,
        'releaseId': rel.release_id,
        'kind': rel.asset.kind,
        'purpose': 'public-ota',
        'expiresAt': str(expires_at),
        'keyVersion': str(state.key_version),
        'signature': signature,
    })
    return '%s%s?%s' % (state.public_base_url, svc.DOWNLOAD_PATH, query)


# ---- App 解析器镜像（ota_firmware_latest.dart fail-closed 判定的 Python 重实现）----

def mirror_latest_true(body, device_model='e-track-at32f435', channel='stable',
                       require_https=True):
    assert body['schemaVersion'] == 2, body
    assert isinstance(body['requestId'], str) and body['requestId']
    assert body['updateAvailable'] is True
    assert 'errorCode' not in body, 'true 分支不得带 errorCode'
    assert body['appId'] == 'trace'
    assert body['deviceModel'] == device_model
    assert body['channel'] == channel
    assert body['transport'] == 'ble'
    for key in ('releaseId', 'versionName', 'releaseTag', 'releaseNotes',
                'targetImageSha256', 'targetHardware'):
        assert isinstance(body[key], str) and body[key], key
    assert SHA256_HEX_RE.match(body['targetImageSha256'])
    assert isinstance(body['versionCode'], int) and \
        0 <= body['versionCode'] <= 0xFFFFFFFF
    assert isinstance(body['minAppVersionCode'], int) and \
        0 <= body['minAppVersionCode'] <= 2100000000
    asset = body['asset']
    for key in ('assetId', 'kind', 'fileName', 'sha256', 'sizeBytes',
                'baseVersionCode', 'baseImageSha256', 'downloadUrl',
                'expiresAt'):
        assert key in asset, 'asset 缺键 %s' % key
    assert FILE_NAME_RE.match(asset['fileName']) and \
        len(asset['fileName']) <= 128 and asset['fileName'].endswith('-full.etu')
    assert SHA256_HEX_RE.match(asset['sha256'])
    assert isinstance(asset['sizeBytes'], int) and \
        1 <= asset['sizeBytes'] <= 0x180000
    assert asset['kind'] == 'full'
    assert asset['baseVersionCode'] == 0
    assert asset['baseImageSha256'] is None
    url = urlsplit(asset['downloadUrl'])
    assert url.hostname, 'downloadUrl 必须带 host'
    if require_https:
        assert url.scheme == 'https', 'downloadUrl 必须为 https'
    assert isinstance(asset['expiresAt'], int)


def mirror_latest_false(body):
    """false 精简体：只允许 schemaVersion/requestId/updateAvailable/
    errorCode(+maintenanceMessage)，不得含 asset/URL。"""
    assert body['schemaVersion'] == 2
    assert isinstance(body['requestId'], str) and body['requestId']
    assert body['updateAvailable'] is False
    assert body['errorCode'] in ('NO_UPDATE', 'CHANNEL_STOPPED')
    allowed = {'schemaVersion', 'requestId', 'updateAvailable', 'errorCode',
               'maintenanceMessage'}
    assert set(body.keys()) <= allowed, body.keys()


def assert_compat_error(status, body, code, required_key, actual_key,
                        required_value, actual_value):
    """App OtaHttpError.fromBody 读取键名逐一对齐（OTA-XC-HTTP-ERROR）。"""
    assert status == 409, (status, body)
    assert body['errorCode'] == code
    assert body[required_key] == required_value
    assert body[actual_key] == actual_value
    assert isinstance(body['requestId'], str) and body['requestId']
    assert body['releaseId']
    assert 'asset' not in body and 'downloadUrl' not in body


# ---- 测试组 ----

def test_golden_vector_sign():
    """黄金向量：独立复算 HMAC hex/Base64URL，规范消息 67 字节，参数顺序一致。"""
    key = bytes.fromhex(GOLDEN_KEY_HEX)
    msg = svc.canonical_token_message(
        GOLDEN_ASSET_ID, GOLDEN_RELEASE_ID, 'patch', 'public-ota',
        GOLDEN_EXPIRES_AT, GOLDEN_KEY_VERSION)
    msg_bytes = msg.encode('utf-8')
    assert len(msg_bytes) == 67, len(msg_bytes)
    # 双重复算：不经 service.sign_token_v2 独立算 HMAC
    digest_hex = hmac.new(key, msg_bytes, hashlib.sha256).hexdigest()
    assert digest_hex == GOLDEN_HMAC_HEX, digest_hex
    b64 = base64.urlsafe_b64encode(bytes.fromhex(digest_hex)).rstrip(b'=')
    assert b64.decode('ascii') == GOLDEN_SIGNATURE
    # 生产签名路径
    assert svc.sign_token_v2(
        key, GOLDEN_ASSET_ID, GOLDEN_RELEASE_ID, 'patch', 'public-ota',
        GOLDEN_EXPIRES_AT, GOLDEN_KEY_VERSION) == GOLDEN_SIGNATURE
    # URL 参数顺序与冻结契约逐字节一致（tokenVersion→…→signature）
    query = urlencode({
        'tokenVersion': '2', 'assetId': GOLDEN_ASSET_ID,
        'releaseId': GOLDEN_RELEASE_ID, 'kind': 'patch',
        'purpose': 'public-ota', 'expiresAt': GOLDEN_EXPIRES_AT,
        'keyVersion': str(GOLDEN_KEY_VERSION), 'signature': GOLDEN_SIGNATURE,
    })
    assert query == GOLDEN_QUERY, query


def _golden_state(now):
    return svc.V2ServiceState(
        {'publicBaseUrl': 'https://golden.invalid',
         'token': {'keyVersion': GOLDEN_KEY_VERSION,
                   'keyHex': GOLDEN_KEY_HEX},
         'releases': {}, 'channels': {'stable': None}},
        HERE, now_fn=lambda: now)


def test_golden_vector_verify_and_expiry():
    """verify 路径接受黄金 token；expiresAt 排他边界（>= 即 TOKEN_EXPIRED）。"""
    pairs = parse_qsl(GOLDEN_QUERY, keep_blank_values=True)
    state = _golden_state(1799999999)  # < 1800000300
    seen = state._verify_download_token(pairs, 'selftest-golden')
    assert seen['assetId'] == GOLDEN_ASSET_ID
    assert seen['kind'] == 'patch'
    state_at_edge = _golden_state(1800000300)  # == expiresAt
    try:
        state_at_edge._verify_download_token(pairs, 'selftest-golden')
        raise AssertionError('expiresAt 排他边界未拒绝')
    except svc.ServiceError as exc:
        assert exc.http_status == 401 and exc.error_code == 'TOKEN_EXPIRED'
        assert exc.request_id == 'selftest-golden'
    state_before = _golden_state(1800000299)
    state_before._verify_download_token(pairs, 'selftest-golden')  # 边界前一秒通过


def test_config_real_identity():
    """真实配置加载：两份 fixture 身份核验通过，字节与冻结四元组一致。"""
    state = make_state()
    assert state.releases['toy-30201'].asset.size_bytes == TOY_ETU_SIZE
    assert state.releases['toy-30201'].asset.sha256_hex == TOY_ETU_SHA
    assert len(state.releases['toy-30201'].asset.data) == TOY_ETU_SIZE
    assert state.releases['real-30202'].asset.size_bytes == REAL_ETU_SIZE
    assert state.releases['real-30202'].asset.sha256_hex == REAL_ETU_SHA
    assert hashlib.sha256(
        state.releases['toy-30201'].asset.data).hexdigest() == TOY_ETU_SHA
    assert hashlib.sha256(
        state.releases['real-30202'].asset.data).hexdigest() == REAL_ETU_SHA


def _expect_config_error(mutate, label):
    cfg = copy.deepcopy(load_real_config())
    mutate(cfg)
    try:
        svc.V2ServiceState(cfg, HERE)
        raise AssertionError('%s 未被 fail-closed 拒绝' % label)
    except svc.ServiceConfigError:
        pass


def test_config_fail_closed():
    """篡改 sha/size/路径、未知或 archived 指针、非 300 TTL、kind=patch 拒绝。"""
    _expect_config_error(
        lambda c: c['releases']['toy-30201']['asset'].update(
            sha256='0' * 64), '篡改 fixture sha')
    _expect_config_error(
        lambda c: c['releases']['toy-30201']['asset'].update(
            sizeBytes=TOY_ETU_SIZE + 1), '篡改 fixture size')
    _expect_config_error(
        lambda c: c['releases']['toy-30201']['asset'].update(
            path='.cache/p3-3-assets/not-exist.etu'),
        'fixture 文件不存在')

    def _archived(cfg):
        cfg['releases']['toy-30201']['state'] = 'archived'
        cfg['channels']['stable'] = 'toy-30201'
    _expect_config_error(_archived, 'channel 指向 archived release')
    _expect_config_error(
        lambda c: c['channels'].update(stable='no-such-release'),
        'channel 指向未知 release')
    _expect_config_error(
        lambda c: c['token'].update(ttlSeconds=299), '非 300 TTL')
    _expect_config_error(
        lambda c: c['releases']['toy-30201']['asset'].update(kind='patch'),
        'kind=patch 资产')
    _expect_config_error(
        lambda c: c['releases']['toy-30201'].update(state='draft'),
        '非法 state')
    # full 资产带 base 镜像（App 解析器要求 full 的 baseImageSha256 为 null）
    _expect_config_error(
        lambda c: c['releases']['toy-30201']['asset'].update(
            baseVersionCode=30200, baseImageSha256='1' * 64),
        'full 资产带 base 字段')


def test_latest_param_validation():
    """十参数闭集合：重复/未知/缺失/数值域/appId/deviceModel/channel/hash。"""
    state = make_state(active='toy-30201')
    cases = [
        (latest_pairs(drop=['appVersionCode']), 400, 'INVALID_PARAMETER'),
        (latest_pairs(extra=[('foo', '1')]), 400, 'INVALID_PARAMETER'),
        (latest_pairs(extra=[('channel', 'stable')]), 400, 'INVALID_PARAMETER'),
        (latest_pairs(app_vcode=2100000001), 400, 'INVALID_PARAMETER'),
        (latest_pairs(app_vcode='8x'), 400, 'INVALID_PARAMETER'),
        (latest_pairs(app_id='other'), 400, 'INVALID_PARAMETER'),
        (latest_pairs(channel='rc'), 400, 'INVALID_PARAMETER'),
        (latest_pairs(image_sha='ABC'), 400, 'INVALID_PARAMETER'),
        (latest_pairs(current_vcode=-1), 400, 'INVALID_PARAMETER'),
        (latest_pairs(current_vcode=4294967296), 400, 'INVALID_PARAMETER'),
        (latest_pairs(hw=256), 400, 'INVALID_PARAMETER'),
        (latest_pairs(boot='x'), 400, 'INVALID_PARAMETER'),
        (latest_pairs(device_model='other-model'), 400, 'UNKNOWN_DEVICE_MODEL'),
    ]
    for pairs, want_status, want_code in cases:
        status, body = call_latest(state, pairs)
        assert (status, body.get('errorCode')) == (want_status, want_code), \
            (pairs, status, body)


def test_latest_semantics_and_mirror():
    """未发布/激活/无更新语义 + App 解析器镜像全字段核对。"""
    # 未发布：NO_UPDATE 精简体
    state_none = make_state(active=None)
    status, body = call_latest(state_none, latest_pairs(30200))
    assert status == 200
    mirror_latest_false(body)
    assert body['errorCode'] == 'NO_UPDATE'

    # stopped：CHANNEL_STOPPED（可附 maintenanceMessage，不得含 URL）
    state_stopped = make_state(active='stopped')
    status, body = call_latest(state_stopped, latest_pairs(30200))
    assert status == 200
    mirror_latest_false(body)
    assert body['errorCode'] == 'CHANNEL_STOPPED'
    assert 'maintenanceMessage' in body

    # 激活 toy：30200 → true 30201，App 镜像逐字段
    state_toy = make_state(active='toy-30201')
    status, body = call_latest(state_toy, latest_pairs(30200))
    assert status == 200
    mirror_latest_true(body)
    assert body['releaseId'] == 'release-30201'
    assert body['versionCode'] == 30201
    assert body['targetImageSha256'] == TOY_IMAGE_SHA
    asset = body['asset']
    assert asset['assetId'] == 'asset-full-30201'
    assert asset['fileName'] == 'e-track-at32f435-v3.2.1-full.etu'
    assert asset['sha256'] == TOY_ETU_SHA
    assert asset['sizeBytes'] == TOY_ETU_SIZE
    # downloadUrl 解析为 8 参数 token v2
    q = dict(url_query_pairs(asset['downloadUrl']))
    assert set(q) == set(svc.TOKEN_QUERY_KEYS)
    assert q['tokenVersion'] == '2' and q['kind'] == 'full' and \
        q['purpose'] == 'public-ota'
    assert int(q['expiresAt']) - 1800000000 == svc.TOKEN_TTL_SECONDS

    # 30201（已装 toy）/30202（更高）对 toy 指针均 NO_UPDATE
    for vcode in (30201, 30202):
        status, body = call_latest(state_toy, latest_pairs(vcode))
        assert status == 200
        mirror_latest_false(body)
        assert body['errorCode'] == 'NO_UPDATE'

    # beta 渠道未发布 → NO_UPDATE
    status, body = call_latest(state_toy, latest_pairs(30200, channel='beta'))
    assert status == 200 and body['errorCode'] == 'NO_UPDATE'

    # 切真包：30201 → true 30202；30200 → true 30202
    state_real = make_state(active='real-30202')
    for current in (30200, 30201):
        status, body = call_latest(state_real, latest_pairs(current))
        assert status == 200
        mirror_latest_true(body)
        assert body['versionCode'] == 30202
        assert body['targetImageSha256'] == REAL_IMAGE_SHA

    # 真机参数组合必然通过（hw/layout/boot/proto=1、app 86、板 30200）
    state_toy2 = make_state(active='toy-30201')
    status, body = call_latest(
        state_toy2, latest_pairs(30200, app_vcode=86, hw=1, layout=1,
                                 boot=1, proto=1))
    assert status == 200 and body['updateAvailable'] is True


def test_latest_gate_order():
    """处理顺序：存在更新后先 App 门禁（426）再兼容链（409），不折叠维度。"""
    cfg = copy.deepcopy(load_real_config())
    cfg['releases']['toy-30201']['minAppVersionCode'] = 99999
    cfg['releases']['toy-30201']['hardwareRevision'] = 2  # 同时不兼容
    state = svc.V2ServiceState(cfg, HERE, active_release='toy-30201',
                               now_fn=lambda: 1800000000)
    # app 86 < 99999 且 hardware 不匹配 → 必须 426 先于 409
    status, body = call_latest(state, latest_pairs(30200, app_vcode=86, hw=1))
    assert status == 426, (status, body)
    assert body['errorCode'] == 'CLIENT_TOO_OLD'
    assert body['minAppVersionCode'] == 99999
    assert 'asset' not in body and 'downloadUrl' not in body
    # 无更新时即使 app 过旧也不评估 426（只有确认存在更新才评估）
    status, body = call_latest(state, latest_pairs(30201, app_vcode=86))
    assert status == 200 and body['updateAvailable'] is False


def test_latest_compat_chain():
    """四维度兼容链顺序 hardware→layout→Boot→protocol，错误体字段名对齐 App。"""
    base = copy.deepcopy(load_real_config())

    def make(rel_key, **override):
        cfg = copy.deepcopy(base)
        rel = cfg['releases'][rel_key]
        rel.update(override)
        return svc.V2ServiceState(cfg, HERE, active_release=rel_key,
                                  now_fn=lambda: 1800000000)

    # hardware（即使 layout/boot/proto 也不匹配，只报 hardware）
    state = make('toy-30201', hardwareRevision=2, layoutId=3, minBootVersion=9,
                 minProtocolVersion=9)
    status, body = call_latest(state, latest_pairs(30200, hw=1, layout=1,
                                                   boot=1, proto=1))
    assert_compat_error(status, body, 'HARDWARE_INCOMPATIBLE',
                        'requiredHardwareRevision', 'actualHardwareRevision',
                        2, 1)
    # layout（hardware 匹配后）
    state = make('toy-30201', layoutId=3, minBootVersion=9,
                 minProtocolVersion=9)
    status, body = call_latest(state, latest_pairs(30200, layout=1))
    assert_compat_error(status, body, 'LAYOUT_INCOMPATIBLE',
                        'requiredLayoutId', 'actualLayoutId', 3, 1)
    # Boot
    state = make('toy-30201', minBootVersion=2, minProtocolVersion=9)
    status, body = call_latest(state, latest_pairs(30200, boot=1))
    assert_compat_error(status, body, 'BOOT_TOO_OLD',
                        'minBootVersion', 'bootVersion', 2, 1)
    # protocol
    state = make('toy-30201', minProtocolVersion=2)
    status, body = call_latest(state, latest_pairs(30200, proto=1))
    assert_compat_error(status, body, 'PROTOCOL_UNSUPPORTED',
                        'minProtocolVersion', 'protocolVersion', 2, 1)


def _download_url(state):
    asset = get_latest_asset(state, 30200)
    return asset['downloadUrl'], state.releases[
        'toy-30201' if state.channels.get('stable') == 'toy-30201'
        else 'real-30202'].asset


def test_download_token_validation():
    """八参数精确集合与签名/版本/purpose/kind 拒绝语义。"""
    state = make_state(active='toy-30201')
    url, asset = _download_url(state)
    pairs = url_query_pairs(url)

    # 合法请求先确认 200
    status, headers, body = call_download(state, pairs)
    assert status == 200 and body == asset.data, status

    def expect_reject(mutated, code):
        status, _h, body = call_download(state, mutated)
        assert status == 401, (status, body)
        assert json.loads(body)['errorCode'] == code, body

    # 缺参数/未知参数/重复/空值
    expect_reject([p for p in pairs if p[0] != 'signature'], 'TOKEN_INVALID')
    expect_reject(pairs + [('extra', 'x')], 'TOKEN_INVALID')
    expect_reject(pairs + [('kind', 'full')], 'TOKEN_INVALID')
    expect_reject([(k, '' if k == 'signature' else v) for k, v in pairs],
                  'TOKEN_INVALID')
    # 签名篡改（首字符翻转）
    expect_reject([(k, ('A' if v[0] != 'A' else 'B') + v[1:]
                    if k == 'signature' else v) for k, v in pairs],
                  'TOKEN_INVALID')
    # tokenVersion / keyVersion / purpose / kind
    expect_reject([(k, '1' if k == 'tokenVersion' else v)
                   for k, v in pairs], 'TOKEN_INVALID')
    expect_reject([(k, '9' if k == 'keyVersion' else v)
                   for k, v in pairs], 'TOKEN_INVALID')
    expect_reject([(k, 'ci-download' if k == 'purpose' else v)
                   for k, v in pairs], 'TOKEN_INVALID')
    expect_reject([(k, 'recovery' if k == 'kind' else v)
                   for k, v in pairs], 'TOKEN_INVALID')


def test_download_token_expiry():
    """TTL 固定 300s，expiresAt 排他截止：now>=expiresAt → TOKEN_EXPIRED。"""
    t0 = 1800000000
    state_signed = make_state(active='toy-30201', now_fn=lambda: t0)
    asset = get_latest_asset(state_signed, 30200)
    pairs = url_query_pairs(asset['downloadUrl'])
    expires = int(dict(pairs)['expiresAt'])
    assert expires == t0 + 300
    # 299s 后仍有效
    state_late = make_state(active='toy-30201', now_fn=lambda: expires - 1)
    status, _h, body = call_download(state_late, pairs)
    assert status == 200, (status, body)
    # 300s 整（== expiresAt）过期
    state_edge = make_state(active='toy-30201', now_fn=lambda: expires)
    status, _h, body = call_download(state_edge, pairs)
    assert status == 401 and \
        json.loads(body)['errorCode'] == 'TOKEN_EXPIRED', (status, body)


def test_download_visibility():
    """未激活 410 ASSET_DISABLED / archived 409 / 未知 release 404 / 切换作废。"""
    state_toy = make_state(active='toy-30201')
    # 直接为未激活的真包签 URL → 410
    url = sign_url_for(state_toy, 'real-30202')
    status, _h, body = call_download(state_toy, url_query_pairs(url))
    assert status == 410 and \
        json.loads(body)['errorCode'] == 'ASSET_DISABLED', (status, body)

    # archived release → 409 ASSET_ARCHIVED
    cfg = copy.deepcopy(load_real_config())
    cfg['releases']['real-30202']['state'] = 'archived'
    state_arch = svc.V2ServiceState(cfg, HERE, active_release='toy-30201',
                                    now_fn=lambda: 1800000000)
    url = sign_url_for(state_arch, 'real-30202')
    status, _h, body = call_download(state_arch, url_query_pairs(url))
    assert status == 409 and \
        json.loads(body)['errorCode'] == 'ASSET_ARCHIVED', (status, body)

    # 未知 releaseId（签名有效）→ 404
    rel = state_toy.releases['toy-30201']
    expires = 1800000300
    signature = svc.sign_token_v2(
        state_toy.token_key, rel.asset.asset_id, 'release-99999',
        'full', 'public-ota', expires, state_toy.key_version)
    pairs = [('tokenVersion', '2'), ('assetId', rel.asset.asset_id),
             ('releaseId', 'release-99999'), ('kind', 'full'),
             ('purpose', 'public-ota'), ('expiresAt', str(expires)),
             ('keyVersion', str(state_toy.key_version)),
             ('signature', signature)]
    status, _h, body = call_download(state_toy, pairs)
    assert status == 404 and \
        json.loads(body)['errorCode'] == 'RELEASE_NOT_FOUND', (status, body)

    # 激活切换后旧 URL 作废（toy URL 在 real 激活态 → 410）
    asset = get_latest_asset(state_toy, 30200)
    state_real = make_state(active='real-30202')
    status, _h, body = call_download(state_real,
                                     url_query_pairs(asset['downloadUrl']))
    assert status == 410 and \
        json.loads(body)['errorCode'] == 'ASSET_DISABLED', (status, body)


def test_download_range_semantics():
    """200 头集与 RFC 9530 摘要复算、206 头集、If-Range、416、非法 Range。"""
    state = make_state(active='toy-30201')
    url, asset = _download_url(state)
    pairs = url_query_pairs(url)
    data = asset.data
    etag = '"sha256-%s"' % TOY_ETU_SHA

    # 200 完整下载：头集 + 摘要复算 + 字节一致
    status, headers, body = call_download(state, pairs)
    assert status == 200 and body == data
    assert headers['Content-Type'] == 'application/vnd.e-track.etu'
    assert int(headers['Content-Length']) == TOY_ETU_SIZE
    assert headers['ETag'] == etag
    assert headers['Accept-Ranges'] == 'bytes'
    assert headers['Content-Disposition'] == \
        'attachment; filename="%s"' % asset.file_name
    assert headers['X-Trace-Asset-Type'] == 'firmware'
    assert 'X-Request-Id' in headers and headers['X-Request-Id']
    digest = headers['Content-Digest']
    expected_digest = 'sha-256=:%s:' % base64.b64encode(
        hashlib.sha256(data).digest()).decode('ascii')
    assert digest == expected_digest, digest
    # RFC 9530 结构：sha-256=:<标准 Base64 含 padding>:（32B → 43 数据 + 1 padding）
    digest_value = digest[len('sha-256=:'):-1]
    assert len(digest_value) == 44 and digest_value.endswith('=')
    assert base64.b64encode(
        hashlib.sha256(data).digest()).decode('ascii') == digest_value

    # 206 续传：头集 + 字节切片
    status, headers, body = call_download(
        state, pairs, range_header='bytes=100000-', if_range=etag)
    assert status == 206
    assert headers['Content-Range'] == \
        'bytes 100000-%d/%d' % (TOY_ETU_SIZE - 1, TOY_ETU_SIZE)
    assert int(headers['Content-Length']) == TOY_ETU_SIZE - 100000
    assert headers['ETag'] == etag
    assert headers['Accept-Ranges'] == 'bytes'
    assert body == data[100000:]
    # 206 省略 Content-Digest（契约允许：若存在只表示本次 body）
    assert 'Content-Digest' not in headers

    # bytes=0- 全区间
    status, headers, body = call_download(
        state, pairs, range_header='bytes=0-', if_range=etag)
    assert status == 206 and body == data

    # If-Range 失配 → 200 全量（App 先截断旧 partial）
    status, headers, body = call_download(
        state, pairs, range_header='bytes=100000-', if_range='"stale"')
    assert status == 200 and body == data

    # N >= sizeBytes → 416 + Content-Range bytes */size + Content-Length（可读完）
    status, headers, body = call_download(
        state, pairs, range_header='bytes=%d-' % TOY_ETU_SIZE, if_range=etag)
    assert status == 416
    assert headers['Content-Range'] == 'bytes */%d' % TOY_ETU_SIZE
    assert int(headers['Content-Length']) == len(body)
    assert json.loads(body)['errorCode'] == 'INVALID_PARAMETER'

    # 闭合区间 / suffix / 非十进制 → 400 INVALID_PARAMETER
    for bad in ('bytes=100-200', 'bytes=-500', 'bytes=abc-'):
        status, _h, body = call_download(
            state, pairs, range_header=bad, if_range=etag)
        assert status == 400, (bad, status)
        assert json.loads(body)['errorCode'] == 'INVALID_PARAMETER'


def _http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, \
                resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, \
            exc.read()


def test_wire_loop():
    """线级回环：真实 HTTP latest→下载→续传→416→签名篡改 401。"""
    state = make_state(active='toy-30201')
    log = logging.getLogger('p33-selftest-wire')
    log.addHandler(logging.NullHandler())
    handler_cls = type('SelftestHandler', (svc.P33RequestHandler,),
                       {'state': state, 'log': log})
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler_cls)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = 'http://127.0.0.1:%d' % httpd.server_address[1]
        state.public_base_url = base  # 测试专用回环基址（生产为 https 域名）

        latest_url = base + svc.LATEST_PATH + '?' + urlencode(
            dict(latest_pairs(30200)))
        status, headers, raw = _http_get(latest_url)
        assert status == 200, (status, raw)
        body = json.loads(raw)
        assert headers['content-type'].startswith('application/json')
        mirror_latest_true(body, require_https=False)
        assert urlsplit(body['asset']['downloadUrl']).hostname == '127.0.0.1'

        # 完整下载（真实 HTTP 字节流）
        status, headers, raw = _http_get(body['asset']['downloadUrl'])
        assert status == 200
        assert raw == state.releases['toy-30201'].asset.data
        assert int(headers['content-length']) == TOY_ETU_SIZE
        assert headers['x-trace-asset-type'] == 'firmware'
        assert 'x-request-id' in headers
        etag = headers['etag']

        # 断点续传 206
        status, headers, raw = _http_get(
            body['asset']['downloadUrl'],
            headers={'Range': 'bytes=200000-',
                     'If-Range': etag})
        assert status == 206
        assert raw == state.releases['toy-30201'].asset.data[200000:]
        assert headers['content-range'] == \
            'bytes 200000-%d/%d' % (TOY_ETU_SIZE - 1, TOY_ETU_SIZE)

        # 416（线级确认响应可完整读取，不挂起）
        status, headers, raw = _http_get(
            body['asset']['downloadUrl'],
            headers={'Range': 'bytes=%d-' % TOY_ETU_SIZE,
                     'If-Range': etag})
        assert status == 416
        assert json.loads(raw)['errorCode'] == 'INVALID_PARAMETER'

        # 签名篡改 → 401 TOKEN_INVALID
        url = body['asset']['downloadUrl']
        tampered = url.replace('signature=', 'signature=X')
        status, headers, raw = _http_get(tampered)
        assert status == 401
        assert json.loads(raw)['errorCode'] == 'TOKEN_INVALID'
        assert 'x-request-id' in headers

        # 未知路径 → 404
        status, _h, raw = _http_get(base + '/api/other')
        assert status == 404 and \
            json.loads(raw)['errorCode'] == 'RELEASE_NOT_FOUND'
    finally:
        httpd.shutdown()
        httpd.server_close()


class _ListLogHandler(logging.Handler):
    """内存日志捕获：线级 requestId 一致性断言用。"""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


_REQ_ID_RE = re.compile(r'req=([0-9a-f]{32})')


def test_protocol_unsupported_above_min():
    """协议门禁补齐：不低于最低版本但不受支持（2/3/255）→ 409，不静默按协议 1 应答。"""
    state = make_state(active='toy-30201')
    # 高于 min=1 但不在受支持集合 → 409（第四轮裁定实测缺陷：此前返回 200）
    for proto in (2, 3, 255):
        status, body = call_latest(state, latest_pairs(30200, proto=proto))
        assert status == 409, (proto, status, body)
        assert body['errorCode'] == 'PROTOCOL_UNSUPPORTED', (proto, body)
        assert body['minProtocolVersion'] == 1
        assert body['protocolVersion'] == proto
        assert body['releaseId'] == 'release-30201'
        assert 'asset' not in body and 'downloadUrl' not in body
    # 低于最低版本（0 < 1）仍拒绝（原语义保持）
    status, body = call_latest(state, latest_pairs(30200, proto=0))
    assert status == 409 and body['errorCode'] == 'PROTOCOL_UNSUPPORTED'
    assert body['minProtocolVersion'] == 1 and body['protocolVersion'] == 0
    # 受支持边界：协议 1 正常通过（防门禁误伤）
    status, body = call_latest(state, latest_pairs(30200, proto=1))
    assert status == 200 and body['updateAvailable'] is True
    # 最低版本抬高后，协议 1 走下限分支拒绝（双臂对照）
    cfg = copy.deepcopy(load_real_config())
    cfg['releases']['toy-30201']['minProtocolVersion'] = 2
    state2 = svc.V2ServiceState(cfg, HERE, active_release='toy-30201',
                                now_fn=lambda: 1800000000)
    status, body = call_latest(state2, latest_pairs(30200, proto=1))
    assert status == 409 and body['errorCode'] == 'PROTOCOL_UNSUPPORTED'
    assert body['minProtocolVersion'] == 2 and body['protocolVersion'] == 1


def test_download_token_kind_mismatch():
    """签名有效但 kind 与 full 资产类型不符 → 401 TOKEN_INVALID（非 404）。"""
    state = make_state(active='toy-30201')
    rel = state.releases['toy-30201']
    expires = int(state.now_fn()) + svc.TOKEN_TTL_SECONDS
    # 用真实 key 为「目标资产 + 错误 kind」重新签名：签名本身有效，
    # 穿过验签层后到达资产一致性比对（第四轮裁定实测缺陷：此前 404）。
    signature = svc.sign_token_v2(
        state.token_key, rel.asset.asset_id, rel.release_id, 'patch',
        'public-ota', expires, state.key_version)
    pairs = [('tokenVersion', '2'), ('assetId', rel.asset.asset_id),
             ('releaseId', rel.release_id), ('kind', 'patch'),
             ('purpose', 'public-ota'), ('expiresAt', str(expires)),
             ('keyVersion', str(state.key_version)),
             ('signature', signature)]
    status, _h, body = call_download(state, pairs)
    parsed = json.loads(body)
    assert status == 401, (status, parsed)
    assert parsed['errorCode'] == 'TOKEN_INVALID', parsed
    assert parsed.get('tokenKind') == 'patch'
    assert parsed.get('assetKind') == 'full'
    # purpose 允许集合之外的 kind（recovery）在验签层即拒绝，同样 401
    signature_rec = svc.sign_token_v2(
        state.token_key, rel.asset.asset_id, rel.release_id, 'recovery',
        'public-ota', expires, state.key_version)
    pairs_rec = [('tokenVersion', '2'), ('assetId', rel.asset.asset_id),
                 ('releaseId', rel.release_id), ('kind', 'recovery'),
                 ('purpose', 'public-ota'), ('expiresAt', str(expires)),
                 ('keyVersion', str(state.key_version)),
                 ('signature', signature_rec)]
    status, _h, body = call_download(state, pairs_rec)
    assert status == 401 and \
        json.loads(body)['errorCode'] == 'TOKEN_INVALID', (status, body)
    # 对照：签名有效、kind=full 正确但 assetId 不存在 → 仍 404 RELEASE_NOT_FOUND
    signature_other = svc.sign_token_v2(
        state.token_key, 'asset-full-99999', rel.release_id, 'full',
        'public-ota', expires, state.key_version)
    pairs_other = [('tokenVersion', '2'), ('assetId', 'asset-full-99999'),
                   ('releaseId', rel.release_id), ('kind', 'full'),
                   ('purpose', 'public-ota'), ('expiresAt', str(expires)),
                   ('keyVersion', str(state.key_version)),
                   ('signature', signature_other)]
    status, _h, body = call_download(state, pairs_other)
    assert status == 404 and \
        json.loads(body)['errorCode'] == 'RELEASE_NOT_FOUND', (status, body)


def test_wire_request_id_and_redaction():
    """线级 requestId 三方一致（成功/错误/下载）+ 日志签名 URL 脱敏。"""
    state = make_state(active='toy-30201')
    log = logging.getLogger('p33-selftest-wire-ids')
    capture = _ListLogHandler()
    log.handlers = [capture]
    log.setLevel(logging.INFO)
    log.propagate = False
    handler_cls = type('SelftestHandlerIds', (svc.P33RequestHandler,),
                       {'state': state, 'log': log})
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler_cls)
    httpd.daemon_threads = True
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = 'http://127.0.0.1:%d' % httpd.server_address[1]
        state.public_base_url = base  # 测试专用回环基址（生产为 https 域名）

        def wait_log(n):
            # do_GET 在写完响应体后才 log.info；客户端拿到响应时日志行
            # 可能尚未落 handler，按行数轮询等待（上限 5s）。
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if len(capture.messages) >= n:
                    return capture.messages[n - 1]
                time.sleep(0.01)
            raise AssertionError('日志行 #%d 未出现: %r' % (n, capture.messages))

        # 场景 1（成功 latest）：头 == 体 == 日志
        latest_url = base + svc.LATEST_PATH + '?' + urlencode(
            dict(latest_pairs(30200)))
        status, headers, raw = _http_get(latest_url)
        assert status == 200, (status, raw)
        body = json.loads(raw)
        line = wait_log(1)
        rid_log = _REQ_ID_RE.search(line)
        assert rid_log, line
        assert headers['x-request-id'] == body['requestId'] == \
            rid_log.group(1), (headers.get('x-request-id'),
                               body['requestId'], line)

        # 场景 2（错误 401）：头 == 体 == 日志，且该行日志已脱敏
        download_url = body['asset']['downloadUrl']
        sig_value = dict(url_query_pairs(download_url))['signature']
        tampered = download_url.replace(
            'signature=' + sig_value, 'signature=' + ('X' + sig_value[1:]))
        status, headers, raw = _http_get(tampered)
        assert status == 401, (status, raw)
        err_body = json.loads(raw)
        line = wait_log(2)
        rid_log = _REQ_ID_RE.search(line)
        assert rid_log, line
        assert headers['x-request-id'] == err_body['requestId'] == \
            rid_log.group(1), (headers.get('x-request-id'),
                               err_body['requestId'], line)
        assert 'signature=<redacted>' in line, line
        assert sig_value not in line, '日志泄漏签名明文'

        # 场景 3（下载 200）：头 x-request-id 与日志一致，日志已脱敏
        status, headers, raw = _http_get(download_url)
        assert status == 200
        line = wait_log(3)
        rid_log = _REQ_ID_RE.search(line)
        assert rid_log, line
        assert headers['x-request-id'] == rid_log.group(1), \
            (headers.get('x-request-id'), line)
        assert 'signature=<redacted>' in line and sig_value not in line, line
        assert raw == state.releases['toy-30201'].asset.data

        # redact_path_for_log 单元形态：多参数/无签名/空值/尾参数
        assert svc.redact_path_for_log(
            '/x?tokenVersion=2&signature=AbC_123&kind=full') == \
            '/x?tokenVersion=2&signature=<redacted>&kind=full'
        assert svc.redact_path_for_log(
            '/latest?appId=trace') == '/latest?appId=trace'
        assert svc.redact_path_for_log(
            '/d?signature=') == '/d?signature=<redacted>'
        assert svc.redact_path_for_log(
            '/d?a=1&signature=tok') == '/d?a=1&signature=<redacted>'
    finally:
        httpd.shutdown()
        httpd.server_close()


TESTS = [
    ('黄金向量签名（独立复算+生产路径+参数顺序）', test_golden_vector_sign),
    ('黄金向量验签与排他过期边界', test_golden_vector_verify_and_expiry),
    ('真实配置 fixture 身份核验', test_config_real_identity),
    ('配置加载 fail-closed（9 类拒绝）', test_config_fail_closed),
    ('latest 参数闭集合校验', test_latest_param_validation),
    ('latest 业务语义与 App 解析器镜像', test_latest_semantics_and_mirror),
    ('latest 门禁顺序（426 先于 409）', test_latest_gate_order),
    ('latest 四维兼容链顺序与错误体字段', test_latest_compat_chain),
    ('download token 八参数与签名拒绝', test_download_token_validation),
    ('download token TTL 排他过期', test_download_token_expiry),
    ('下载可见性（410/409/404/切换作废）', test_download_visibility),
    ('Range/If-Range/416/摘要复算', test_download_range_semantics),
    ('线级回环（真实 HTTP 全链）', test_wire_loop),
    ('协议门禁：不低于最低但不受支持 → 409', test_protocol_unsupported_above_min),
    ('token kind 与资产不符（签名有效）→ 401', test_download_token_kind_mismatch),
    ('线级 requestId 三方一致与日志脱敏', test_wire_request_id_and_redaction),
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
    print('---- selftest 总计 %d 项，失败 %d 项 ----'
          % (len(TESTS), len(failed)))
    if failed:
        for name in failed:
            print('FAILED: %s' % name)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
