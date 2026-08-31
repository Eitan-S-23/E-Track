#!/usr/bin/env python3
"""P2-6-v2 证据包独立复算器（fail-closed）。

用途：对 `docs/acceptance-contracts/P2-6-v2/` 证据包内的原始产物做一次完全独立的
字节级复算，重新导出 12 条判据的实测观测值，并与本文件内冻结的期望门禁逐项比较。
本文件不读取 R5 的任何摘要字段作为判定依据：
  - 门禁数值一律从 `rtt-payload.raw.log` 原始字节里解析出的 `P2_6` 测量行导出；
  - RTT 控制块前后差异一律由 `rtt-cb-pre.bin` / `rtt-cb-post.bin` 逐字节 diff 导出；
  - result.json 只用于导出会话收尾/身份等本身就以字段形式记录的过程事实，
    并且不使用其 `classifications` 分类结论。

fail-closed 契约：任一必需检查不成立即返回退出码 1；不存在常量 PASS 分支，也不存在
"没有错误日志即通过"的推定。`--self-test` 用带正负例的变异实验证明这一点。
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import shutil
import struct
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# 冻结期望值（与 P2-6-v2 合同 gate 一一对应，改动即视为合同变更）
# ---------------------------------------------------------------------------

# C2：overlay workspace 峰值上限。40960 = OTA_OVERLAY_WORKSPACE_LENGTH(0xA000)，
# 即 `.ota_overlay` 段实际保留容量，链接脚本 x-track-app-gcc.ld.S:271 有等值 ASSERT。
WORKSPACE_PEAK_LIMIT = 40960
# C3 的 stack 上限不在 v2 范围内，故本文件不实现 stack 判据。

EXPECT_ELF_SHA256 = "35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019"
EXPECT_MAP_SHA256 = "2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13"
EXPECT_DEVICE_IMAGE_SHA256 = "AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5"
EXPECT_DEVICE_HEADER_SHA256 = "AB40E59EC6DB9E69ABEF88D22F7999FAD222FF3F6F9751251AE0A388C7808BFB"
EXPECT_PACKAGE_SHA256 = "2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B"
EXPECT_PACKAGE_BYTES = 305
EXPECT_MCU_PATH = "/P2-6A-PATCH-v2.8.0-to-v2.8.1-R5-20260830-01.etu"

# SEGGER RTT 控制块布局：16B id + MaxNumUpBuffers(4) + MaxNumDownBuffers(4) = 24，
# 其后为 Up0 描述符 <IIIIiI>(pName,pBuffer,SizeOfBuffer,WrOff,RdOff,Flags)。
RTT_UP0_OFFSET = 24
RTT_UP0_STRUCT = "<IIIIiI"
RTT_UP0_RDOFF_OFFSET = RTT_UP0_OFFSET + 16          # 40
RTT_UP0_RDOFF_END = RTT_UP0_RDOFF_OFFSET + 4        # 44

ART = {
    "preflight_result": "artifacts/logs/p2-6-sd-r5-preflight-hw-02-result.json",
    "upload_result": "artifacts/logs/p2-6-sd-r5-patch-upload-hw-01-result.json",
    "upload_readback": "artifacts/snapshots/p2-6-sd-r5-patch-upload-hw-01-readback.bin",
    "ota_result": "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-result.json",
    "payload": "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-payload.raw.log",
    "pending": "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-pending.bin",
    "cb_pre": "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-cb-pre.bin",
    "cb_post": "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-cb-post.bin",
    "up0_pre": "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-up0-pre.bin",
}

# 保管链全集：包内 23 份 R5 原始产物的冻结字节数与 SHA-256。
# 数值由本会话直接在 R5 证据根 .cache/p2-6-sd-r5-20260830-01-implementation/
# 与 docs/ota-exec-notes/ 上复算得出，且已逐份核对包内副本与源文件逐字节同源；
# 不引用 R5 result.json 里的任何自述哈希。ART 是其中参与门禁计算的子集。
CUSTODY: dict[str, tuple[int, str]] = {
    "artifacts/docs/P2-6-SD-R5-hw-execution-evidence-2026-08-30.md": (
        7964, "525964701BA0E0ECDF14CBAF7A9B693E498C6C44E07B92718CAB773F0416559E"),
    "artifacts/docs/P2-6-SD-R6-dispatch-ruling-2026-08-30.md": (
        17802, "41C10CFE963162FB0A7AAC312752D6FC79B1FEC62D0A8CD1112A0A949044D9FA"),
    "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-gdb.log": (
        2026, "A26008EE419CF09AB45C4CE3E1144B3C16492CA37561323BFE33F07643C6C165"),
    "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-jlink-server.log": (
        70075, "F07D748E4EF07185EBF2AA1EF23169AE8D77BD06BD117B1C512A91353A461904"),
    "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-post-gdb.log": (
        344, "92BFF125184B51CDAF13B063D9AF41FD669B8E7ACCDC7C579095F7C2F47FA90C"),
    "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-post-jlink-server.log": (
        3820, "4557F012DF4FE4883F01243A770B24BC4087E83E67197183E63EC5FEC7C38A33"),
    "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-post-rtt.raw.log": (
        107, "D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0"),
    "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-result.json": (
        12058, "1A5C4F55ADA98A0C1790E2976FDF6C1C92B297F622AD642C6162CFB271620072"),
    "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-rtt-logger-console.log": (
        1152, "4BFB7C020EE598C2F79DD61BA1B6838A5060DEA31387A9776A2BD99420DE6A36"),
    "artifacts/logs/p2-6-sd-r5-patch-ota-hw-01-rtt.raw.log": (
        107, "D859ED3421BBEBBDD78614A9CCAAAEDF147701E74986EB9C7E1C286C39A47FC0"),
    "artifacts/logs/p2-6-sd-r5-patch-upload-hw-01-gdb.log": (
        2680, "790FF97CFB11C4FA3BDA711CF73D07B1152C499CAEE9E91ECC57A0AD8B6108C6"),
    "artifacts/logs/p2-6-sd-r5-patch-upload-hw-01-result.json": (
        4733, "9306B4D438424D9E16BDDE3C2B3E0B69D32D2C27A08F87C31190ED92C6AEEDAB"),
    "artifacts/logs/p2-6-sd-r5-preflight-hw-02-gdb.log": (
        756, "F8A0E517ED57F9ED89F5C5E9ACBAE506A771760BCC900E2BB930A0DACDB1F821"),
    "artifacts/logs/p2-6-sd-r5-preflight-hw-02-jlink-server.log": (
        10799, "A686027E1F11D4E64E1B39E7F724DA29CAD85C35923513A26830044074E93C5B"),
    "artifacts/logs/p2-6-sd-r5-preflight-hw-02-result.json": (
        3580, "9676E29CFC4039E023EA4E7DF1E620C82F15E08B4A1DF17CFA0FD4F39D1AF79F"),
    "artifacts/scripts/p2-6-sd-r5-patch-ota-hw-01-post.gdb": (
        859, "5955D86D98B151BF5A824046AB61D7BF5B4D8AFBD4BFB906C121126906E1E4E1"),
    "artifacts/scripts/p2-6-sd-r5-patch-ota-hw-01.gdb": (
        19818, "89B07A18A002B14050C2B5DBCBA7BF5890FE092D17BEF0CC70DF626F7F33CECB"),
    "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-cb-post.bin": (
        168, "8789F9176E36D36189BBA7F3432A488A3ED5C98494B1EFF0078FF47F017FC420"),
    "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-cb-pre.bin": (
        168, "5806020EE0DFDABDFC1D89E38B236F846014D0ED157CC4386FA7A68F0C9CB9CD"),
    "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-payload.raw.log": (
        737, "7D9C1528D06CCFD0801402C6A8EE92B3E87309F328C7B41FCB1290476ACA8215"),
    "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-pending.bin": (
        737, "7D9C1528D06CCFD0801402C6A8EE92B3E87309F328C7B41FCB1290476ACA8215"),
    "artifacts/snapshots/p2-6-sd-r5-patch-ota-hw-01-rtt-up0-pre.bin": (
        1024, "B154EFDDBD72B3D9F4E4A0A0F02B0BA14020B781F3D1DD34BE67EA532158C4A4"),
    "artifacts/snapshots/p2-6-sd-r5-patch-upload-hw-01-readback.bin": (
        305, "2B0ACCAEABD88572F1DAE98A7AB66DF511F48D099530537281FDA36AF37C9D2B"),
}


class RecomputeError(Exception):
    """复算过程中遇到结构性不可解析输入时抛出，等价于判据不成立。"""


def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_bytes(bundle: Path, key: str) -> bytes:
    path = bundle / ART[key]
    if not path.is_file():
        raise RecomputeError(f"缺少证据文件: {ART[key]}")
    return path.read_bytes()


def read_json(bundle: Path, key: str) -> dict:
    raw = read_bytes(bundle, key)
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecomputeError(f"{ART[key]} 不是可解析 JSON: {exc}") from exc


def parse_measurements(payload: bytes) -> list[dict[str, str]]:
    """从 RTT 原始字节里解析全部 `P2_6 ` 测量行，返回键值字典列表。"""
    text = payload.decode("ascii", errors="replace")
    records: list[dict[str, str]] = []
    for line in text.replace("\r", "\n").split("\n"):
        line = line.strip()
        if not line.startswith("P2_6 "):
            continue
        fields: dict[str, str] = {}
        for token in line[len("P2_6 "):].split():
            if "=" not in token:
                raise RecomputeError(f"测量行含无法解析的 token: {token!r}")
            key, _, value = token.partition("=")
            if key in fields:
                raise RecomputeError(f"测量行字段重复: {key}")
            fields[key] = value
        records.append(fields)
    return records


def field_int(fields: dict[str, str], name: str) -> int:
    if name not in fields:
        raise RecomputeError(f"测量行缺少字段: {name}")
    raw = fields[name]
    try:
        return int(raw, 16) if raw.lower().startswith("0x") else int(raw, 10)
    except ValueError as exc:
        raise RecomputeError(f"字段 {name} 不是整数: {raw!r}") from exc


def decode_up0(cb: bytes) -> dict[str, int]:
    if len(cb) < RTT_UP0_OFFSET + struct.calcsize(RTT_UP0_STRUCT):
        raise RecomputeError(f"RTT 控制块快照过短: {len(cb)} B")
    p_name, p_buffer, size, wr_off, rd_off, flags = struct.unpack_from(
        RTT_UP0_STRUCT, cb, RTT_UP0_OFFSET
    )
    return {
        "pName": p_name,
        "pBuffer": p_buffer,
        "SizeOfBuffer": size,
        "WrOff": wr_off,
        "RdOff": rd_off,
        "Flags": flags,
    }


def bool_field(source: dict, name: str) -> bool:
    value = source.get(name)
    if not isinstance(value, bool):
        raise RecomputeError(f"字段 {name} 不是布尔值: {value!r}")
    return value


def int_field(source: dict, name: str) -> int:
    value = source.get(name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise RecomputeError(f"字段 {name} 不是整数: {value!r}")
    return value


def evaluate(bundle: Path) -> dict:
    """执行全部复算，返回结构化报告。任何结构性问题以 RecomputeError 抛出。"""
    checks: list[dict] = []

    def record(cid: str, observed, expected, ok: bool, note: str = "") -> None:
        checks.append(
            {
                "criterion_id": cid,
                "observed": observed,
                "expected": expected,
                "result": "PASS" if ok else "FAIL",
                "note": note,
            }
        )

    # ---- 原始产物哈希（全部自行读取复算，不引用任何记录值） ----
    digests = {}
    for key in ART:
        data = read_bytes(bundle, key)
        digests[ART[key]] = {"bytes": len(data), "sha256": sha256_upper(data)}

    preflight = read_json(bundle, "preflight_result")
    upload = read_json(bundle, "upload_result")
    ota = read_json(bundle, "ota_result")
    payload = read_bytes(bundle, "payload")
    pending = read_bytes(bundle, "pending")
    cb_pre = read_bytes(bundle, "cb_pre")
    cb_post = read_bytes(bundle, "cb_post")
    readback = read_bytes(bundle, "upload_readback")

    # ---- 1. HW-BOARD-STATE-PREFLIGHT：测量前板载状态门禁通过且本轮零写入 ----
    pf_session = preflight.get("session")
    if not isinstance(pf_session, dict):
        raise RecomputeError("preflight result.json 缺少 session 对象")
    pf_observed = [
        f"preflight_pass_markers={int_field(preflight, 'preflight_pass_markers')}",
        f"state_pass_markers={int_field(preflight, 'state_pass_markers')}",
        f"write_calls={int_field(preflight, 'write_calls')}",
        f"flash_calls={int_field(preflight, 'flash_calls')}",
        f"gdb_exit_code={int_field(pf_session, 'gdb_exit_code')}",
        f"server_natural_exit={str(bool_field(pf_session, 'server_natural_exit')).lower()}",
    ]
    pf_expected = [
        "preflight_pass_markers=1",
        "state_pass_markers=1",
        "write_calls=0",
        "flash_calls=0",
        "gdb_exit_code=0",
        "server_natural_exit=true",
    ]
    record("HW-BOARD-STATE-PREFLIGHT", pf_observed, pf_expected, pf_observed == pf_expected)

    # ---- 2. HW-PACKAGE-IDENTITY：被测 .etu 身份 = 冻结包，且落盘回读逐字节一致 ----
    readback_sha = sha256_upper(readback)
    pkg_observed = [
        f"input_bytes={int_field(upload, 'input_bytes')}",
        f"readback_bytes={len(readback)}",
        f"input_sha256={upload.get('input_sha256')}",
        f"readback_recomputed_sha256={readback_sha}",
        f"readback_matches={str(bool_field(upload, 'readback_matches')).lower()}",
        f"upload_mcu_path={upload.get('mcu_path')}",
        f"ota_package_path={ota.get('package_path')}",
    ]
    pkg_expected = [
        f"input_bytes={EXPECT_PACKAGE_BYTES}",
        f"readback_bytes={EXPECT_PACKAGE_BYTES}",
        f"input_sha256={EXPECT_PACKAGE_SHA256}",
        f"readback_recomputed_sha256={EXPECT_PACKAGE_SHA256}",
        "readback_matches=true",
        f"upload_mcu_path={EXPECT_MCU_PATH}",
        f"ota_package_path={EXPECT_MCU_PATH}",
    ]
    record("HW-PACKAGE-IDENTITY", pkg_observed, pkg_expected, pkg_observed == pkg_expected)

    # ---- 3. HW-INPUTS-IDENTITY：三轮绑定同一构建产物与同一基线镜像资产 ----
    id_observed = []
    id_expected = []
    for label, source in (("preflight", preflight), ("upload", upload), ("ota", ota)):
        id_observed.extend(
            [
                f"{label}.elf_sha256={source.get('elf_sha256')}",
                f"{label}.map_sha256={source.get('map_sha256')}",
                f"{label}.device_image_sha256={source.get('device_image_sha256')}",
                f"{label}.device_header_sha256={source.get('device_header_sha256')}",
            ]
        )
        id_expected.extend(
            [
                f"{label}.elf_sha256={EXPECT_ELF_SHA256}",
                f"{label}.map_sha256={EXPECT_MAP_SHA256}",
                f"{label}.device_image_sha256={EXPECT_DEVICE_IMAGE_SHA256}",
                f"{label}.device_header_sha256={EXPECT_DEVICE_HEADER_SHA256}",
            ]
        )
    record("HW-INPUTS-IDENTITY", id_observed, id_expected, id_observed == id_expected)

    # ---- 4. HW-CAPTURE-BYTE-IDENTITY：logger 采集与 pending 快照逐字节一致 ----
    payload_sha = sha256_upper(payload)
    pending_sha = sha256_upper(pending)
    cap_observed = [
        f"payload_bytes={len(payload)}",
        f"pending_bytes={len(pending)}",
        f"payload_sha256={payload_sha}",
        f"pending_sha256={pending_sha}",
        f"byte_identical={str(payload == pending).lower()}",
    ]
    cap_ok = payload == pending and len(payload) > 0 and payload_sha == pending_sha
    cap_expected = [
        f"payload_bytes={len(pending)}",
        f"pending_bytes={len(pending)}",
        f"payload_sha256={pending_sha}",
        f"pending_sha256={pending_sha}",
        "byte_identical=true",
    ]
    record("HW-CAPTURE-BYTE-IDENTITY", cap_observed, cap_expected, cap_ok)

    # ---- 5. HW-RECORD-UNIQUENESS：恰一条 P2_6 记录，kind=patch，result=0 ----
    records = parse_measurements(payload)
    patch_records = [r for r in records if r.get("kind") == "patch"]
    uniq_observed = [
        f"p2_6_record_count={len(records)}",
        f"kind_patch_record_count={len(patch_records)}",
        f"result={patch_records[0].get('result') if patch_records else 'ABSENT'}",
    ]
    uniq_expected = ["p2_6_record_count=1", "kind_patch_record_count=1", "result=0"]
    record("HW-RECORD-UNIQUENESS", uniq_observed, uniq_expected, uniq_observed == uniq_expected)

    if len(patch_records) != 1:
        # 没有唯一测量行时，五项门禁失去唯一观测源，必须整体判失败而不是跳过。
        raise RecomputeError(
            f"无法导出唯一 PATCH 测量行（记录 {len(records)} 条 / patch {len(patch_records)} 条）"
        )
    m = patch_records[0]

    # ---- 6. HW-POSTCHECK-RDOFF：控制块变化仅限 Up0 RdOff 字 ----
    if len(cb_pre) != len(cb_post):
        raise RecomputeError(f"控制块快照长度不一致: {len(cb_pre)} vs {len(cb_post)}")
    changed = [i for i in range(len(cb_pre)) if cb_pre[i] != cb_post[i]]
    outside = [i for i in changed if not (RTT_UP0_RDOFF_OFFSET <= i < RTT_UP0_RDOFF_END)]
    pre_up0 = decode_up0(cb_pre)
    post_up0 = decode_up0(cb_post)
    post_observed = [
        f"WrOff:{pre_up0['WrOff']}->{post_up0['WrOff']}",
        f"RdOff:{pre_up0['RdOff']}->{post_up0['RdOff']}",
        f"changed_byte_offsets={changed}",
        f"changed_outside_rd_off_word={len(outside)}",
        f"up0_pBuffer_unchanged={str(pre_up0['pBuffer'] == post_up0['pBuffer']).lower()}",
        f"up0_size_unchanged={str(pre_up0['SizeOfBuffer'] == post_up0['SizeOfBuffer']).lower()}",
    ]
    post_ok = (
        not outside
        and changed
        and pre_up0["WrOff"] == post_up0["WrOff"]
        and pre_up0["RdOff"] == 0
        and post_up0["RdOff"] == len(pending)
        and pre_up0["pBuffer"] == post_up0["pBuffer"]
        and pre_up0["SizeOfBuffer"] == post_up0["SizeOfBuffer"]
    )
    post_expected = [
        f"WrOff:{len(pending)}->{len(pending)}",
        f"RdOff:0->{len(pending)}",
        "changed_byte_offsets=[40, 41]",
        "changed_outside_rd_off_word=0",
        "up0_pBuffer_unchanged=true",
        "up0_size_unchanged=true",
    ]
    record("HW-POSTCHECK-RDOFF", post_observed, post_expected, post_ok)

    # ---- 7. PROC-SESSION-CLOSURE：会话自然收尾，无进程强杀，无残留 logger ----
    session = ota.get("session")
    if not isinstance(session, dict):
        raise RecomputeError("ota result.json 缺少 session 对象")
    sess_observed = [
        f"gdb_exit_code={int_field(session, 'gdb_exit_code')}",
        f"server_exit_code={int_field(session, 'server_exit_code')}",
        f"server_natural_exit={str(bool_field(session, 'server_natural_exit')).lower()}",
        f"server_kill_sent={str(bool_field(session, 'server_kill_sent')).lower()}",
        f"ports_closed={str(bool_field(session, 'ports_closed')).lower()}",
        f"session_error={'null' if session.get('session_error') is None else 'present'}",
    ]
    sess_expected = [
        "gdb_exit_code=0",
        "server_exit_code=0",
        "server_natural_exit=true",
        "server_kill_sent=false",
        "ports_closed=true",
        "session_error=null",
    ]
    record("PROC-SESSION-CLOSURE", sess_observed, sess_expected, sess_observed == sess_expected)

    # ---- 8. PATCH-C2：overlay workspace 峰值 <= 40960 B ----
    workspace_peak = field_int(m, "workspace_peak")
    record(
        "PATCH-C2-WORKSPACE-PEAK",
        {"value": workspace_peak, "unit": "byte"},
        {"operator": "le", "limit": WORKSPACE_PEAK_LIMIT, "unit": "byte"},
        workspace_peak <= WORKSPACE_PEAK_LIMIT,
        note="limit = OTA_OVERLAY_WORKSPACE_LENGTH(0xA000)",
    )

    # ---- 9. PATCH-C4：32B guard 进出均完好 ----
    c4_observed = [
        f"guard_entry={field_int(m, 'guard_entry')}",
        f"guard_exit={field_int(m, 'guard_exit')}",
    ]
    c4_expected = ["guard_entry=1", "guard_exit=1"]
    record("PATCH-C4-GUARD-INTACT", c4_observed, c4_expected, c4_observed == c4_expected)

    # ---- 10. PATCH-C5：sbrk 调用增量为 0 ----
    sbrk_delta = field_int(m, "sbrk_delta")
    record(
        "PATCH-C5-SBRK-DELTA-ZERO",
        {"value": sbrk_delta, "unit": "call"},
        {"operator": "eq", "limit": 0, "unit": "call"},
        sbrk_delta == 0,
    )

    # ---- 11. PATCH-C6：lv_tlsf_malloc / lv_tlsf_realloc 增量为 0（free 为交叉核对） ----
    c6_observed = [
        f"tlsf_malloc_delta={field_int(m, 'tlsf_malloc_delta')}",
        f"tlsf_realloc_delta={field_int(m, 'tlsf_realloc_delta')}",
        f"tlsf_free_delta={field_int(m, 'tlsf_free_delta')}",
    ]
    c6_expected = ["tlsf_malloc_delta=0", "tlsf_realloc_delta=0", "tlsf_free_delta=0"]
    record("PATCH-C6-TLSF-DELTA-ZERO", c6_observed, c6_expected, c6_observed == c6_expected)

    # ---- 12. PATCH-C14（辅助项）：lv_mem_monitor 四字段进出净值不变 ----
    c14_pairs = [("lv_free", "free"), ("lv_big", "big"), ("lv_frag", "frag"), ("lv_max", "max")]
    c14_observed = []
    c14_ok = True
    for prefix, _ in c14_pairs:
        entry = field_int(m, f"{prefix}_entry")
        exit_ = field_int(m, f"{prefix}_exit")
        c14_observed.append(f"{prefix} {entry}->{exit_}")
        if entry != exit_:
            c14_ok = False
    c14_expected = [f"{p} {field_int(m, p + '_entry')}->{field_int(m, p + '_entry')}" for p, _ in c14_pairs]
    record("PATCH-C14-LV-POOL-NET", c14_observed, c14_expected, c14_ok)

    # ---- 13. PROC-CUSTODY-COMPLETE：保管链 23 份产物逐份存在且字节数/SHA-256 与冻结值一致 ----
    custody_missing: list[str] = []
    custody_mismatch: list[str] = []
    for rel, (want_bytes, want_sha) in sorted(CUSTODY.items()):
        path = bundle / rel
        if not path.is_file():
            custody_missing.append(rel)
            continue
        data = path.read_bytes()
        if len(data) != want_bytes or sha256_upper(data) != want_sha:
            custody_mismatch.append(rel)
    custody_observed = [
        f"custody_files={len(CUSTODY)}",
        f"present={len(CUSTODY) - len(custody_missing)}",
        f"digest_match={len(CUSTODY) - len(custody_missing) - len(custody_mismatch)}",
        f"missing={custody_missing}",
        f"mismatch={custody_mismatch}",
    ]
    custody_expected = [
        f"custody_files={len(CUSTODY)}",
        f"present={len(CUSTODY)}",
        f"digest_match={len(CUSTODY)}",
        "missing=[]",
        "mismatch=[]",
    ]
    record("PROC-CUSTODY-COMPLETE", custody_observed, custody_expected, custody_observed == custody_expected)

    failed = [c["criterion_id"] for c in checks if c["result"] != "PASS"]
    return {
        "schema": "p2-6-v2-evidence-recompute-v1",
        "workspace_peak_limit": WORKSPACE_PEAK_LIMIT,
        "measurement_record": m,
        "artifact_digests": digests,
        "checks": checks,
        "failed_criteria": failed,
        "overall": "PASS" if not failed else "FAIL",
    }


def run(bundle: Path, report_path: Path | None) -> int:
    try:
        report = evaluate(bundle)
    except RecomputeError as exc:
        print(f"P2_6_V2_RECOMPUTE=FAIL {exc}", file=sys.stderr)
        return 1

    lines = [f"P2_6_V2_RECOMPUTE bundle={bundle.as_posix()}"]
    for item in report["checks"]:
        observed = item["observed"]
        rendered = json.dumps(observed, ensure_ascii=False) if not isinstance(observed, str) else observed
        lines.append(f"  [{item['result']}] {item['criterion_id']}: {rendered}")
    lines.append(f"P2_6_V2_RECOMPUTE={report['overall']} failed={report['failed_criteria']}")
    print("\n".join(lines))

    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    return 0 if report["overall"] == "PASS" else 1


# ---------------------------------------------------------------------------
# 自检：正例必须 0，每个负例必须非 0（证明无常量 PASS 分支）
# ---------------------------------------------------------------------------

def _mutate_payload(root: Path, replace: tuple[str, str]) -> None:
    for key in ("payload", "pending"):
        path = root / ART[key]
        text = path.read_bytes().decode("ascii", errors="strict")
        if replace[0] not in text:
            raise RecomputeError(f"自检变异串未命中: {replace[0]!r}")
        path.write_bytes(text.replace(replace[0], replace[1], 1).encode("ascii"))


def _flip_byte(path: Path, offset: int) -> None:
    data = bytearray(path.read_bytes())
    data[offset] ^= 0xFF
    path.write_bytes(bytes(data))


def _patch_json(path: Path, mutate) -> None:
    doc = json.loads(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def self_test(bundle: Path, work_root: Path) -> int:
    """正例必须退出 0，每个负例必须退出非 0。内层复算输出被吞掉，
    只保留判决行，以保证本函数的 stdout 不含随机临时路径、可稳定复现。"""
    cases: list[tuple[str, object]] = [
        ("negative-pending-byte-flip", lambda r: _flip_byte(r / ART["pending"], 100)),
        ("negative-cb-post-outside-rdoff", lambda r: _flip_byte(r / ART["cb_post"], 60)),
        ("negative-cb-post-rdoff-zeroed", lambda r: _flip_byte(r / ART["cb_post"], 40)),
        ("negative-c2-over-limit", lambda r: _mutate_payload(r, ("workspace_peak=21792", "workspace_peak=40961"))),
        ("negative-c4-guard-broken", lambda r: _mutate_payload(r, ("guard_exit=1", "guard_exit=0"))),
        ("negative-c5-sbrk-nonzero", lambda r: _mutate_payload(r, ("sbrk_delta=0", "sbrk_delta=1"))),
        ("negative-c6-tlsf-nonzero", lambda r: _mutate_payload(r, ("tlsf_malloc_delta=0", "tlsf_malloc_delta=1"))),
        ("negative-c14-pool-drift", lambda r: _mutate_payload(r, ("lv_free_exit=64832", "lv_free_exit=64000"))),
        ("negative-result-nonzero", lambda r: _mutate_payload(r, ("result=0", "result=5"))),
        (
            "negative-session-gdb-nonzero",
            lambda r: _patch_json(r / ART["ota_result"], lambda d: d["session"].__setitem__("gdb_exit_code", 41)),
        ),
        (
            "negative-preflight-write-calls",
            lambda r: _patch_json(r / ART["preflight_result"], lambda d: d.__setitem__("write_calls", 1)),
        ),
        (
            "negative-package-identity",
            lambda r: _patch_json(r / ART["upload_result"], lambda d: d.__setitem__("readback_matches", False)),
        ),
        ("negative-artifact-removed", lambda r: (r / ART["cb_pre"]).unlink()),
        (
            "negative-custody-doc-tampered",
            lambda r: _flip_byte(r / "artifacts/docs/P2-6-SD-R6-dispatch-ruling-2026-08-30.md", 200),
        ),
        (
            "negative-custody-gdb-script-removed",
            lambda r: (r / "artifacts/scripts/p2-6-sd-r5-patch-ota-hw-01.gdb").unlink(),
        ),
    ]

    work_root.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    results: list[str] = []

    def quiet_run(root: Path) -> int:
        sink = io.StringIO()
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            return run(root, None)

    with tempfile.TemporaryDirectory(dir=str(work_root)) as tmp:
        tmp_root = Path(tmp)

        positive = tmp_root / "positive"
        shutil.copytree(bundle / "artifacts", positive / "artifacts")
        code = quiet_run(positive)
        results.append(f"  [{'OK' if code == 0 else 'BAD'}] positive-control exit={code} (expect 0)")
        if code != 0:
            failures.append("positive-control")

        for name, mutate in cases:
            case_root = tmp_root / name
            shutil.copytree(bundle / "artifacts", case_root / "artifacts")
            try:
                mutate(case_root)
            except RecomputeError as exc:
                failures.append(f"{name}(变异失败: {exc})")
                results.append(f"  [BAD] {name} 变异未施加: {exc}")
                continue
            code = quiet_run(case_root)
            ok = code != 0
            results.append(f"  [{'OK' if ok else 'BAD'}] {name} exit={code} (expect non-zero)")
            if not ok:
                failures.append(name)

    print("P2_6_V2_RECOMPUTE_SELFTEST cases=%d" % (len(cases) + 1))
    print("\n".join(results))
    print(f"P2_6_V2_RECOMPUTE_SELFTEST={'PASS' if not failures else 'FAIL'} failures={failures}")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="P2-6-v2 证据包独立复算器")
    parser.add_argument("--bundle", default="docs/acceptance-contracts/P2-6-v2", help="证据包目录")
    parser.add_argument("--report", default=None, help="结构化报告输出路径")
    parser.add_argument("--self-test", action="store_true", help="运行正负例自检，证明 fail-closed")
    parser.add_argument("--self-test-work", default=".cache/p2-6-v2-recompute-selftest", help="自检临时目录（须位于仓库内）")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    bundle = Path(args.bundle)
    if not bundle.is_dir():
        print(f"P2_6_V2_RECOMPUTE=FAIL 证据包目录不存在: {bundle}", file=sys.stderr)
        return 1

    if args.self_test:
        return self_test(bundle, Path(args.self_test_work))

    report = Path(args.report) if args.report else None
    return run(bundle, report)


if __name__ == "__main__":
    raise SystemExit(main())
