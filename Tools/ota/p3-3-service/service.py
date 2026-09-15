#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P3-3 受控固件 OTA v2 测试服务（冻结源码，版本 2）。

版本 2（用户 2026-09-13 第四轮裁定整改）：
- requestId 一次请求单一生成：HTTP 层生成后传入状态层，日志、响应体、
  响应头（X-Request-Id）三者使用同一 ID；latest 成功响应补 X-Request-Id 头。
- 协议门禁补齐：protocolVersion 低于 release.minProtocolVersion **或不在
  服务受支持集合内**（当前仅 1）时返回 409 PROTOCOL_UNSUPPORTED
  （契约 OTA-XC-HTTP-LATEST：「或协议版本不受支持时」）。
- download 的 token/资产一致性分类修正：query kind 与目标资产实际类型
  不符（签名有效）时返回 401 TOKEN_INVALID（契约 OTA-XC-HTTP-DOWNLOAD：
  「query 与资产类型或用途不一致时返回 TOKEN_INVALID」）；assetId 不符
  仍为 404 RELEASE_NOT_FOUND。
- 普通请求日志对签名 URL 参数脱敏（signature 值不打明文）。

依据 `docs/ota-cross-system-contracts.md` 冻结契约实现本卡（P3-3）实际
使用的语义子集：OTA-XC-HTTP-LATEST（v2 响应 + 426/409 兼容门禁链）、
OTA-XC-CLOUD-QUERY-MAPPING（latest 十参数）、OTA-XC-HTTP-DOWNLOAD
（token v2 签发与验签、完整响应头）、OTA-XC-HTTP-RESUME（单区间续传）、
OTA-XC-HTTP-ERROR（错误体格式）。App 侧对齐基准是
`app/bluetooth_flutter_Trace/lib/ota/ota_firmware_latest.dart` 与
`ota_download.dart`（fail-closed 解析器，本服务不得要求 App 放宽任何校验；
本服务的 Python「App 解析器镜像」仅为宿主自测辅助，不构成真实 Dart
consumer 验证）。

边界声明（用户 2026-09-13 第三轮裁定）：
- 本服务是**项目内受控测试服务**，覆盖 latest、兼容门禁、token v2、
  下载及摘要语义；**不证明 P4-2 通过**（未实现正式 register/D1/admin
  发布链，也不经这些链路）。
- 不放宽 App 校验、不直接注入 OtaService 状态；App 走真实 HTTP 请求。
- 启动对外服务（含 adb reverse 面向手机的任何一次服务启动）仍需具体
  授权；本文件提交入库只是能力准备。

fixture 激活方式：channel 指针经 `--active-release` 启动参数注入（toy→
真包切换 = 停服重启换参数，全程命令行可审计，不改冻结文件）。
fixture 身份在启动时按 config 内 SHA-256/size 逐字节核验，失配即拒绝启动。

仅使用 Python 3 标准库（验收宿主可直接运行，无第三方依赖）。
"""

import argparse
import base64
import hashlib
import hmac
import json
import logging
import os
import re
import ssl
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlencode, urlsplit

SERVICE_VERSION = '2'

# ---- 冻结契约常量 ----

LATEST_PATH = '/api/public/firmware/latest'
DOWNLOAD_PATH = '/api/public/firmware/download'

# OTA-XC-CLOUD-QUERY-MAPPING：latest 请求参数闭集合。
LATEST_KNOWN_PARAMS = {
    'appId', 'deviceModel', 'channel', 'currentVersionCode', 'currentImageSha',
    'hardwareRevision', 'layoutId', 'bootVersion', 'protocolVersion',
    'appVersionCode',
}
APP_ID_TRACE = 'trace'
DEVICE_MODEL = 'e-track-at32f435'
KNOWN_CHANNELS = ('stable', 'beta')
SUPPORTED_TRANSPORT = 'ble'

# OTA-XC-HTTP-DOWNLOAD：token v2 query 精确集合（顺序即 canonical message）。
TOKEN_QUERY_KEYS = (
    'tokenVersion', 'assetId', 'releaseId', 'kind', 'purpose',
    'expiresAt', 'keyVersion', 'signature',
)
TOKEN_TTL_SECONDS = 300
PUBLIC_OTA_KINDS = ('full', 'patch')
# OTA-XC-HTTP-LATEST：「protocolVersion < minProtocolVersion **或协议版本
# 不受支持时**返回 409 PROTOCOL_UNSUPPORTED」。本服务实现（含 token 签发
# 语义）当前只覆盖协议 1；更高的协议版本即使不低于 release 的最低版本，
# 也必须显式拒绝，不得静默按旧协议应答。
SUPPORTED_PROTOCOL_VERSIONS = (1,)

# App 侧域上限（ota_firmware_latest.dart 同源）：MCU vcode 是 u32，
# appVersionCode 是 0..2100000000。
FIRMWARE_VCODE_MAX = 0xFFFFFFFF
APP_VCODE_MAX = 2100000000
U8_MAX = 255

_SHA256_HEX_RE = re.compile(r'^[0-9a-f]{64}$')
_DECIMAL_RE = re.compile(r'^[0-9]+$')
# App 端强 ETag 判定（RFC 7232 opaque-tag，ota_download.dart 同源）。
_STRONG_ETAG_RE = re.compile(r'^"[!#-~]+"$')
# OTA-XC-HTTP-RESUME：只支持单区间 `bytes=N-`。
_RANGE_OPEN_RE = re.compile(r'^bytes=([0-9]+)-$')
# 请求日志脱敏：签名的 token URL 参数值不打明文（Base64URL 无 `&`，
# 值域为 [A-Za-z0-9_-]，按 `&`/`#` 截断即可覆盖全部编码形态）。
_SIGNATURE_QUERY_RE = re.compile(r'([?&])signature=[^&#]*')


def redact_path_for_log(path):
    """把 path 中 signature 参数的值替换为 <redacted>，其余原样保留。"""
    return _SIGNATURE_QUERY_RE.sub(r'\1signature=<redacted>', path)


class ServiceConfigError(Exception):
    """配置/fixture 身份核验失败（fail-closed，拒绝启动）。"""


class ServiceError(Exception):
    """按 OTA-XC-HTTP-ERROR 语义返回的错误响应。

    错误体必含 requestId（契约）；状态层抛出时携带，HTTP 层兜底补齐，
    保证直调与线级两条路径的错误体一致。
    """

    def __init__(self, http_status, error_code, message, request_id=None,
                 **extra_fields):
        super().__init__(message)
        self.http_status = http_status
        self.error_code = error_code
        self.message = message
        self.request_id = request_id
        self.extra_fields = extra_fields


def new_request_id():
    return uuid.uuid4().hex


def canonical_token_message(asset_id, release_id, kind, purpose,
                            expires_at, key_version):
    """token v2 签名输入：8 行 LF 分隔 UTF-8 字节，末行无 LF（冻结契约）。"""
    return '\n'.join((
        '2', 'GET', asset_id, release_id, kind, purpose,
        str(expires_at), str(key_version),
    ))


def sign_token_v2(key_bytes, asset_id, release_id, kind, purpose,
                  expires_at, key_version):
    """HMAC-SHA256 → Base64URL 无 padding（XC-TOKEN-V2-GOLDEN 可复算）。"""
    msg = canonical_token_message(
        asset_id, release_id, kind, purpose, expires_at, key_version)
    digest = hmac.new(key_bytes, msg.encode('utf-8'), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b'=').decode('ascii')


class ReleaseAsset:
    """一份 fixture 资产（full .etu），启动时绑定字节身份。"""

    def __init__(self, release_key, raw):
        self.release_key = release_key
        cfg = raw
        self.asset_id = cfg['assetId']
        self.kind = cfg['kind']
        self.file_name = cfg['fileName']
        self.sha256_hex = cfg['sha256'].lower()
        self.size_bytes = cfg['sizeBytes']
        self.path = cfg['path']
        self.base_version_code = cfg.get('baseVersionCode', 0)
        self.base_image_sha256 = cfg.get('baseImageSha256')
        self.data = b''
        self.strong_etag = '"sha256-%s"' % self.sha256_hex

    def verify_against_file(self, config_dir):
        """按 config 声明的 size/SHA-256 逐字节核验 fixture 文件（fail-closed）。

        相对 path 以仓库根（find_repo_root(config_dir)）为基准解析，
        不与 config 文件所在目录层级耦合——服务目录在仓库内的位置
        变化不影响 fixture 定位（git worktree 的 .git 文件同样识别）。
        """
        path = self.path
        if not os.path.isabs(path):
            repo_root = find_repo_root(config_dir)
            path = os.path.normpath(os.path.join(repo_root, path))
        if not os.path.isfile(path):
            raise ServiceConfigError(
                'fixture 文件不存在: %s（release=%s）' % (path, self.release_key))
        data = open(path, 'rb').read()
        actual_sha = hashlib.sha256(data).hexdigest()
        if len(data) != self.size_bytes:
            raise ServiceConfigError(
                'fixture size 不符: %s 声明 %d 实际 %d（release=%s）'
                % (path, self.size_bytes, len(data), self.release_key))
        if actual_sha != self.sha256_hex:
            raise ServiceConfigError(
                'fixture SHA-256 不符: %s 声明 %s 实际 %s（release=%s）'
                % (path, self.sha256_hex, actual_sha, self.release_key))
        self.data = data
        self.resolved_path = path

    def content_digest_header(self):
        """RFC 9530 dictionary member：sha-256=:<标准 Base64 含 padding>:。"""
        digest = hashlib.sha256(self.data).digest()
        b64 = base64.b64encode(digest).decode('ascii')
        return 'sha-256=:%s:' % b64


class Release:
    """一个受控 release 条目（含兼容元数据与 full 资产）。"""

    def __init__(self, key, raw, config_dir):
        self.key = key
        self.release_id = raw['releaseId']
        self.version_name = raw['versionName']
        self.version_code = raw['versionCode']
        self.release_tag = raw['releaseTag']
        self.release_notes = raw.get('releaseNotes', '')
        self.target_image_sha256 = raw['targetImageSha256'].lower()
        self.target_hardware = raw['targetHardware']
        self.min_app_version_code = raw.get('minAppVersionCode', 0)
        self.hardware_revision = raw['hardwareRevision']
        self.layout_id = raw['layoutId']
        self.min_boot_version = raw['minBootVersion']
        self.min_protocol_version = raw['minProtocolVersion']
        # 状态机：active 可被 channel 指向；archived 供 409 ASSET_ARCHIVED
        # 自测语义；disabled 语义由「未被 channel 指向」表达（410）。
        self.state = raw.get('state', 'active')
        self.asset = ReleaseAsset(key, raw['asset'])
        self.asset.verify_against_file(config_dir)
        self._validate()

    def _validate(self):
        if self.state not in ('active', 'archived'):
            raise ServiceConfigError(
                'release %s 非法 state: %s' % (self.key, self.state))
        if self.asset.kind != 'full':
            raise ServiceConfigError(
                '本服务 fixture 仅支持 kind=full（release=%s）' % self.key)
        if self.asset.base_version_code != 0 or \
                self.asset.base_image_sha256 is not None:
            raise ServiceConfigError(
                'full 资产 baseVersionCode 必须为 0 且 baseImageSha256 为 null'
                '（release=%s）' % self.key)
        if not _SHA256_HEX_RE.match(self.target_image_sha256):
            raise ServiceConfigError(
                'release %s targetImageSha256 非 64 位小写 hex' % self.key)
        if not (0 <= self.version_code <= FIRMWARE_VCODE_MAX):
            raise ServiceConfigError('release %s versionCode 超域' % self.key)
        if not (0 <= self.min_app_version_code <= APP_VCODE_MAX):
            raise ServiceConfigError(
                'release %s minAppVersionCode 超域' % self.key)
        for name in ('hardware_revision', 'layout_id', 'min_boot_version',
                     'min_protocol_version'):
            v = getattr(self, name)
            if not isinstance(v, int) or not (0 <= v <= U8_MAX):
                raise ServiceConfigError(
                    'release %s %s 超域 0..255' % (self.key, name))


class V2ServiceState:
    """服务核心状态与两个公开端点的处理逻辑（与 HTTP 层解耦，便于自测）。"""

    def __init__(self, config, config_dir, active_release=None, now_fn=time.time):
        self.now_fn = now_fn
        self.public_base_url = config['publicBaseUrl'].rstrip('/')
        token_cfg = config['token']
        self.key_version = int(token_cfg['keyVersion'])
        key_hex = token_cfg['keyHex']
        if not re.match(r'^[0-9a-f]{64}$', key_hex):
            raise ServiceConfigError('token.keyHex 必须为 64 位小写 hex')
        self.token_key = bytes.fromhex(key_hex)
        ttl = int(token_cfg.get('ttlSeconds', TOKEN_TTL_SECONDS))
        if ttl != TOKEN_TTL_SECONDS:
            # 冻结契约固定 TTL=300；受控服务不偏离。
            raise ServiceConfigError('token TTL 必须为 %d（契约固定）'
                                     % TOKEN_TTL_SECONDS)
        self.releases = {}
        for key, raw in config['releases'].items():
            self.releases[key] = Release(key, raw, config_dir)
        # channel 指针：null（未发布）/'stopped'（停发）/release key。
        self.channels = dict(config.get('channels', {'stable': None}))
        for ch, ptr in self.channels.items():
            if ch not in KNOWN_CHANNELS:
                raise ServiceConfigError('非法 channel: %s' % ch)
            self._validate_pointer(ch, ptr)
        if active_release is not None:
            # --active-release 仅作用于 stable（App 端默认查询 channel）。
            self._validate_pointer('stable', active_release)
            self.channels['stable'] = active_release

    def _validate_pointer(self, channel, ptr):
        if ptr is None or ptr == 'stopped':
            return
        if ptr not in self.releases:
            raise ServiceConfigError(
                'channel %s 指向不存在的 release: %s' % (channel, ptr))
        rel = self.releases[ptr]
        if rel.state != 'active':
            raise ServiceConfigError(
                'channel %s 不得指向非 active release: %s（state=%s）'
                % (channel, ptr, rel.state))

    # ---- latest ----

    def handle_latest(self, query_pairs, request_id=None):
        """OTA-XC-HTTP-LATEST。query_pairs 为原始 (key, value) 列表（含重复）。

        request_id 由 HTTP 层传入以贯通「日志/响应体/响应头同一 ID」；
        直调（宿主自测）不传时在此生成，语义不变。
        """
        if request_id is None:
            request_id = new_request_id()
        params = self._parse_latest_params(query_pairs, request_id)
        # 处理顺序（冻结）：参数校验 → 加载 channel/release → 确认存在更新
        # → App 版本门禁 → 设备兼容 → 选包 → 签发 URL。
        pointer = self.channels.get(params['channel'])
        if pointer == 'stopped':
            return self._json_response(200, {
                'schemaVersion': 2,
                'requestId': request_id,
                'updateAvailable': False,
                'errorCode': 'CHANNEL_STOPPED',
                'maintenanceMessage':
                    'P3-3 controlled test service: channel stopped',
            }, request_id=request_id)
        if pointer is None:
            return self._json_response(200, {
                'schemaVersion': 2,
                'requestId': request_id,
                'updateAvailable': False,
                'errorCode': 'NO_UPDATE',
            }, request_id=request_id)
        release = self.releases[pointer]
        if release.version_code <= params['currentVersionCode']:
            return self._json_response(200, {
                'schemaVersion': 2,
                'requestId': request_id,
                'updateAvailable': False,
                'errorCode': 'NO_UPDATE',
            }, request_id=request_id)
        # App 版本门禁（只在确认存在更新后评估）。
        if params['appVersionCode'] < release.min_app_version_code:
            raise ServiceError(
                426, 'CLIENT_TOO_OLD',
                'app version too old for this release',
                request_id=request_id,
                minAppVersionCode=release.min_app_version_code)
        # 设备兼容链（顺序固定：hardware → layout → Boot → protocol）。
        if params['hardwareRevision'] != release.hardware_revision:
            raise ServiceError(
                409, 'HARDWARE_INCOMPATIBLE',
                'hardware revision mismatch',
                request_id=request_id,
                requiredHardwareRevision=release.hardware_revision,
                actualHardwareRevision=params['hardwareRevision'],
                releaseId=release.release_id)
        if params['layoutId'] != release.layout_id:
            raise ServiceError(
                409, 'LAYOUT_INCOMPATIBLE',
                'layout id mismatch',
                request_id=request_id,
                requiredLayoutId=release.layout_id,
                actualLayoutId=params['layoutId'],
                releaseId=release.release_id)
        if params['bootVersion'] < release.min_boot_version:
            raise ServiceError(
                409, 'BOOT_TOO_OLD',
                'boot version too old',
                request_id=request_id,
                minBootVersion=release.min_boot_version,
                bootVersion=params['bootVersion'],
                releaseId=release.release_id)
        if params['protocolVersion'] < release.min_protocol_version or \
                params['protocolVersion'] not in SUPPORTED_PROTOCOL_VERSIONS:
            # 契约 OTA-XC-HTTP-LATEST：低于最低版本**或协议版本不受支持**
            # 都返回 409 PROTOCOL_UNSUPPORTED（本服务只实现协议 1；即使
            # protocolVersion 高于 release.minProtocolVersion 也必须拒绝，
            # 不得静默降级应答）。
            raise ServiceError(
                409, 'PROTOCOL_UNSUPPORTED',
                'protocol version unsupported',
                request_id=request_id,
                minProtocolVersion=release.min_protocol_version,
                protocolVersion=params['protocolVersion'],
                releaseId=release.release_id)
        # 选包：本服务 fixture 为唯一 full 资产（无 patch，无 recovery）。
        asset = release.asset
        # 签发 URL（TTL 固定 300s；expiresAt 为排他截止时刻）。
        expires_at = int(self.now_fn()) + TOKEN_TTL_SECONDS
        signature = sign_token_v2(
            self.token_key, asset.asset_id, release.release_id, asset.kind,
            'public-ota', expires_at, self.key_version)
        query = urlencode({
            'tokenVersion': '2',
            'assetId': asset.asset_id,
            'releaseId': release.release_id,
            'kind': asset.kind,
            'purpose': 'public-ota',
            'expiresAt': str(expires_at),
            'keyVersion': str(self.key_version),
            'signature': signature,
        })
        download_url = '%s%s?%s' % (self.public_base_url, DOWNLOAD_PATH, query)
        body = {
            'schemaVersion': 2,
            'requestId': request_id,
            'updateAvailable': True,
            'appId': APP_ID_TRACE,
            'deviceModel': params['deviceModel'],
            'channel': params['channel'],
            'releaseId': release.release_id,
            'versionName': release.version_name,
            'versionCode': release.version_code,
            'releaseTag': release.release_tag,
            'releaseNotes': release.release_notes,
            'targetImageSha256': release.target_image_sha256,
            'targetHardware': release.target_hardware,
            'transport': SUPPORTED_TRANSPORT,
            'minAppVersionCode': release.min_app_version_code,
            'asset': {
                'assetId': asset.asset_id,
                'kind': asset.kind,
                'fileName': asset.file_name,
                'sha256': asset.sha256_hex,
                'sizeBytes': asset.size_bytes,
                'baseVersionCode': asset.base_version_code,
                'baseImageSha256': asset.base_image_sha256,
                'downloadUrl': download_url,
                'expiresAt': expires_at,
            },
        }
        return self._json_response(200, body, request_id=request_id)

    def _parse_latest_params(self, query_pairs, request_id):
        seen = {}
        for key, value in query_pairs:
            if key not in LATEST_KNOWN_PARAMS:
                raise ServiceError(
                    400, 'INVALID_PARAMETER', 'unknown query param: %s' % key,
                    request_id=request_id)
            if key in seen:
                raise ServiceError(
                    400, 'INVALID_PARAMETER', 'duplicate query param: %s' % key,
                    request_id=request_id)
            seen[key] = value
        missing = LATEST_KNOWN_PARAMS - set(seen)
        if missing:
            raise ServiceError(
                400, 'INVALID_PARAMETER',
                'missing query params: %s' % ','.join(sorted(missing)),
                request_id=request_id)

        def _decimal(name, lo, hi):
            raw = seen[name]
            if not _DECIMAL_RE.match(raw):
                raise ServiceError(
                    400, 'INVALID_PARAMETER',
                    '%s must be a decimal integer: %r' % (name, raw),
                    request_id=request_id)
            v = int(raw)
            if not (lo <= v <= hi):
                raise ServiceError(
                    400, 'INVALID_PARAMETER',
                    '%s out of range %d..%d: %d' % (name, lo, hi, v),
                    request_id=request_id)
            return v

        if seen['appId'] != APP_ID_TRACE:
            raise ServiceError(400, 'INVALID_PARAMETER',
                               'appId must be %r' % APP_ID_TRACE,
                               request_id=request_id)
        if seen['deviceModel'] != DEVICE_MODEL:
            # XC-LATEST-MODEL-UNKNOWN：未知 deviceModel 不得猜测机型。
            raise ServiceError(400, 'UNKNOWN_DEVICE_MODEL',
                               'unregistered deviceModel: %s'
                               % seen['deviceModel'],
                               request_id=request_id)
        if seen['channel'] not in KNOWN_CHANNELS:
            raise ServiceError(400, 'INVALID_PARAMETER',
                               'channel must be stable|beta',
                               request_id=request_id)
        if not _SHA256_HEX_RE.match(seen['currentImageSha']):
            raise ServiceError(
                400, 'INVALID_PARAMETER',
                'currentImageSha must be 64 lowercase hex',
                request_id=request_id)
        return {
            'deviceModel': seen['deviceModel'],
            'channel': seen['channel'],
            'currentVersionCode': _decimal(
                'currentVersionCode', 0, FIRMWARE_VCODE_MAX),
            'hardwareRevision': _decimal('hardwareRevision', 0, U8_MAX),
            'layoutId': _decimal('layoutId', 0, U8_MAX),
            'bootVersion': _decimal('bootVersion', 0, U8_MAX),
            'protocolVersion': _decimal('protocolVersion', 0, U8_MAX),
            'appVersionCode': _decimal('appVersionCode', 0, APP_VCODE_MAX),
        }

    # ---- download ----

    def handle_download(self, query_pairs, range_header, if_range_header,
                        request_id=None):
        """OTA-XC-HTTP-DOWNLOAD/HTTP-RESUME。返回 (status, headers, body)。

        request_id 语义同 handle_latest：HTTP 层传入贯通三端一致，直调自生成。
        """
        if request_id is None:
            request_id = new_request_id()
        token = self._verify_download_token(query_pairs, request_id)
        release = self._find_release_by_id(token['releaseId'], request_id)
        asset = release.asset
        if asset.kind != token['kind']:
            # 契约 OTA-XC-HTTP-DOWNLOAD：purpose=public-ota 的 token「query
            # 与资产类型或用途不一致」时返回 401 TOKEN_INVALID——签名有效
            # 但 kind 与目标资产实际类型不符属于 token 用途不一致，不是
            # 资产不存在。assetId 不符仍为 404 RELEASE_NOT_FOUND。
            raise ServiceError(
                401, 'TOKEN_INVALID',
                'token kind does not match asset type',
                request_id=request_id,
                tokenKind=token['kind'], assetKind=asset.kind)
        if asset.asset_id != token['assetId']:
            raise ServiceError(
                404, 'RELEASE_NOT_FOUND',
                'asset not found for signed token',
                request_id=request_id)
        # 可见性语义（对齐真实链 ensureFirmwareDownloadAllowed）：
        # archived → 409；未被 channel 指向 → 410。
        if release.state == 'archived':
            raise ServiceError(409, 'ASSET_ARCHIVED',
                               'release archived (controlled test state)',
                               request_id=request_id)
        pointer = self.channels.get('stable')
        if pointer != release.key:
            raise ServiceError(
                410, 'ASSET_DISABLED',
                'release not published on stable (controlled test service)',
                request_id=request_id)
        # If-Range 评估先于 Range（RFC 9110）：不匹配则忽略 Range 返回 200。
        honor_range = range_header is not None
        if range_header is not None and if_range_header is not None:
            if if_range_header.strip() != asset.strong_etag:
                honor_range = False
        base_headers = [
            ('Content-Type', 'application/vnd.e-track.etu'),
            ('ETag', asset.strong_etag),
            ('Accept-Ranges', 'bytes'),
            ('Content-Disposition',
             'attachment; filename="%s"' % asset.file_name),
            ('X-Request-Id', request_id),
            ('X-Trace-Asset-Type', 'firmware'),
            ('Cache-Control', 'no-store'),
        ]
        if not honor_range:
            headers = base_headers + [
                ('Content-Length', str(asset.size_bytes)),
                ('Content-Digest', asset.content_digest_header()),
            ]
            return 200, headers, asset.data
        m = _RANGE_OPEN_RE.match(range_header.strip())
        if not m:
            raise ServiceError(
                400, 'INVALID_PARAMETER',
                'only single open range "bytes=N-" is supported',
                request_id=request_id)
        start = int(m.group(1))
        if start >= asset.size_bytes:
            # XC-RANGE-AT-END：416（body errorCode 契约未规定，App 按
            # 状态码分流删除 partial 并重新 latest，不读此 body）。
            body = self._error_body(
                request_id, 'INVALID_PARAMETER',
                'range start beyond end of file')
            headers = [
                ('Content-Type', 'application/json'),
                ('Content-Length', str(len(body))),
                ('X-Request-Id', request_id),
                ('Content-Range', 'bytes */%d' % asset.size_bytes),
            ]
            return 416, headers, body
        remaining = asset.size_bytes - start
        headers = base_headers + [
            ('Content-Length', str(remaining)),
            ('Content-Range', 'bytes %d-%d/%d'
             % (start, asset.size_bytes - 1, asset.size_bytes)),
        ]
        # 206 的 Content-Digest（若存在）只表示本次 response body；
        # 受控服务在 206 上省略该头（契约允许，App 不强制要求）。
        return 206, headers, asset.data[start:]

    def _verify_download_token(self, query_pairs, request_id):
        seen = {}
        for key, value in query_pairs:
            if key not in TOKEN_QUERY_KEYS:
                raise ServiceError(
                    401, 'TOKEN_INVALID', 'unknown token param: %s' % key,
                    request_id=request_id)
            if key in seen:
                raise ServiceError(
                    401, 'TOKEN_INVALID', 'duplicate token param: %s' % key,
                    request_id=request_id)
            if value == '':
                raise ServiceError(
                    401, 'TOKEN_INVALID', 'empty token param: %s' % key,
                    request_id=request_id)
            seen[key] = value
        missing = set(TOKEN_QUERY_KEYS) - set(seen)
        if missing:
            raise ServiceError(
                401, 'TOKEN_INVALID',
                'missing token params: %s' % ','.join(sorted(missing)),
                request_id=request_id)
        if seen['tokenVersion'] != '2':
            # 受控服务只签发/接受 v2（v1 兼容窗口属真实 worker 部署语义）。
            raise ServiceError(401, 'TOKEN_INVALID',
                               'tokenVersion must be 2',
                               request_id=request_id)
        if seen['keyVersion'] != str(self.key_version):
            raise ServiceError(401, 'TOKEN_INVALID', 'unknown keyVersion',
                               request_id=request_id)
        if not _DECIMAL_RE.match(seen['expiresAt']):
            raise ServiceError(401, 'TOKEN_INVALID',
                               'expiresAt must be decimal seconds',
                               request_id=request_id)
        if seen['purpose'] != 'public-ota':
            raise ServiceError(401, 'TOKEN_INVALID',
                               'only purpose=public-ota is served',
                               request_id=request_id)
        if seen['kind'] not in PUBLIC_OTA_KINDS:
            raise ServiceError(401, 'TOKEN_INVALID',
                               'purpose=public-ota only allows full|patch',
                               request_id=request_id)
        expected = sign_token_v2(
            self.token_key, seen['assetId'], seen['releaseId'], seen['kind'],
            seen['purpose'], seen['expiresAt'], seen['keyVersion'])
        if not hmac.compare_digest(expected, seen['signature']):
            raise ServiceError(401, 'TOKEN_INVALID', 'signature mismatch',
                               request_id=request_id)
        expires_at = int(seen['expiresAt'])
        # 排他截止：currentEpochSeconds >= expiresAt 即过期。
        if int(self.now_fn()) >= expires_at:
            raise ServiceError(401, 'TOKEN_EXPIRED', 'token expired',
                               request_id=request_id)
        return seen

    def _find_release_by_id(self, release_id, request_id):
        for release in self.releases.values():
            if release.release_id == release_id:
                return release
        raise ServiceError(404, 'RELEASE_NOT_FOUND',
                           'unknown releaseId: %s' % release_id,
                           request_id=request_id)

    # ---- 响应构造 ----

    def _json_response(self, status, body, request_id=None):
        payload = json.dumps(body, ensure_ascii=True,
                             separators=(',', ':')).encode('utf-8')
        headers = [
            ('Content-Type', 'application/json'),
            ('Content-Length', str(len(payload))),
        ]
        if request_id is not None:
            # 契约 OTA-XC-HTTP-ERROR 要求错误体含 requestId；成功响应同样
            # 提供 X-Request-Id 头，使「响应头/响应体/请求日志」三方可用
            # 同一 ID 交叉关联（用户第四轮裁定）。
            headers.append(('X-Request-Id', request_id))
        return status, headers, payload

    def _error_body(self, request_id, error_code, message):
        body = {
            'errorCode': error_code,
            'message': message,
            'requestId': request_id,
        }
        return json.dumps(body, ensure_ascii=True,
                          separators=(',', ':')).encode('utf-8')


class P33RequestHandler(BaseHTTPRequestHandler):
    """薄 HTTP 层：路由 + 错误体统一格式 + 请求日志。"""

    server_version = 'p33-v2-svc/' + SERVICE_VERSION
    sys_version = ''
    protocol_version = 'HTTP/1.1'
    timeout = 120

    # 由 serve() 注入。
    state = None
    log = None

    def do_GET(self):
        # 一次请求单一生成：此 ID 贯穿请求日志（req=）、响应体 requestId、
        # 响应头 X-Request-Id 三处（用户第四轮裁定）。
        request_id = new_request_id()
        parts = urlsplit(self.path)
        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        try:
            if parts.path == LATEST_PATH:
                status, headers, body = self.state.handle_latest(
                    query_pairs, request_id=request_id)
            elif parts.path == DOWNLOAD_PATH:
                status, headers, body = self.state.handle_download(
                    query_pairs,
                    self.headers.get('Range'),
                    self.headers.get('If-Range'),
                    request_id=request_id)
            else:
                raise ServiceError(
                    404, 'RELEASE_NOT_FOUND', 'unknown path: %s' % parts.path)
        except ServiceError as exc:
            # 状态层与 HTTP 层共用同一 requestId（HTTP 层传入）；兜底保留
            # 以覆盖 HTTP 层自身抛出（未知路径等）的路径。
            err_request_id = exc.request_id or request_id
            body_fields = {
                'errorCode': exc.error_code,
                'message': exc.message,
                'requestId': err_request_id,
            }
            body_fields.update(exc.extra_fields)
            body = json.dumps(body_fields, ensure_ascii=True,
                              separators=(',', ':')).encode('utf-8')
            headers = [
                ('Content-Type', 'application/json'),
                ('Content-Length', str(len(body))),
                ('X-Request-Id', err_request_id),
            ]
            status = exc.http_status
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)
        self.log.info('%s %s -> %d (%d bytes) req=%s',
                      self.command, redact_path_for_log(self.path), status,
                      len(body), request_id)

    def log_message(self, fmt, *args):
        # 关闭默认 stderr 噪声；结构化日志走 self.log。
        pass


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description='P3-3 受控固件 OTA v2 测试服务（冻结源码 v%s）'
                    % SERVICE_VERSION)
    parser.add_argument('--config', required=True,
                        help='服务配置 JSON 路径（相对路径按该文件所在目录解析）')
    parser.add_argument('--active-release', default=None,
                        help="stable channel 指针：release key / 'stopped' /"
                             " 'none'（默认按 config 原值，即未发布）")
    parser.add_argument('--host', default=None, help='覆盖监听地址')
    parser.add_argument('--port', type=int, default=None, help='覆盖监听端口')
    parser.add_argument('--public-base-url', default=None,
                        help='覆盖 downloadUrl 基址（必须与证书域名一致）')
    parser.add_argument('--tls-cert', default=None, help='TLS 证书链 PEM')
    parser.add_argument('--tls-key', default=None, help='TLS 私钥 PEM')
    parser.add_argument('--log-file', default=None,
                        help='请求日志文件（默认 <仓库根>/.cache/p3-3-v2-service/service.log）')
    return parser


def load_config(config_path):
    config_path = os.path.abspath(config_path)
    with open(config_path, 'r', encoding='utf-8') as fh:
        config = json.load(fh)
    return config, os.path.dirname(config_path)


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


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    config, config_dir = load_config(args.config)
    active = args.active_release
    if active == 'none':
        active = None
    if active is not None and active not in ('stopped',) and \
            'releases' in config and active not in config['releases']:
        raise SystemExit('未知 release key: %s（可用: %s）'
                         % (active, ','.join(sorted(config['releases']))))
    state = V2ServiceState(config, config_dir, active_release=active)
    if args.public_base_url:
        state.public_base_url = args.public_base_url.rstrip('/')
    host = args.host or config.get('listenHost', '127.0.0.1')
    port = args.port or int(config.get('listenPort', 8443))
    if args.log_file:
        log_path = os.path.abspath(args.log_file)
    else:
        repo_root = find_repo_root(config_dir)
        log_path = os.path.join(repo_root, '.cache', 'p3-3-v2-service',
                                'service.log')
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s',
        handlers=[logging.FileHandler(log_path, encoding='utf-8'),
                  logging.StreamHandler(sys.stderr)])
    log = logging.getLogger('p33-v2-svc')

    handler_cls = type('BoundHandler', (P33RequestHandler,), {
        'state': state, 'log': log})
    httpd = ThreadingHTTPServer((host, port), handler_cls)
    httpd.daemon_threads = True
    scheme = 'http'
    if args.tls_cert and args.tls_key:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(certfile=args.tls_cert, keyfile=args.tls_key)
        httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)
        scheme = 'https'
    url_host = state.public_base_url
    if url_host.endswith('.invalid'):
        log.warning('publicBaseUrl 仍是占位域（.invalid）：签发的 downloadUrl '
                    '不可被 App 解析使用；正式执行必须传 --public-base-url '
                    'https://<实际回环域名>:<端口>')
    log.info('服务启动 version=%s scheme=%s listen=%s:%d '
             'publicBaseUrl=%s activeStable=%s fixtures=%s',
             SERVICE_VERSION, scheme, host, port, state.public_base_url,
             state.channels.get('stable'),
             ','.join('%s:%s:%d:%s' % (k, r.asset.file_name,
                                       r.asset.size_bytes,
                                       r.asset.sha256_hex[:12])
                      for k, r in sorted(state.releases.items())))
    log.info('日志文件: %s（关闭方式：Ctrl-C 或终止进程；执行后按操作单 '
             'adb reverse --remove 清理端口转发）', log_path)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info('收到 Ctrl-C，服务关闭')
    finally:
        httpd.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
