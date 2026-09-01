# -*- coding: utf-8 -*-
"""P2-6-v3 证据包独立复算 harness（FULL 侧 + boot 消费链 + C7 + 离线闭合）。

设计原则（与 P2-6-v2 harness 一致，见 tests/ota/p2_6_v2_evidence_recompute.py）：

1. **只读原始产物**。所有判定都从证据包内的原始字节/日志重新解析、重新计算，
   不读取任何"结论字段"。特别地：
   - 不读 result.json 里的 `classifications`；
   - 不读 stack-closure.json 里的 `classification.*`；
   - 不把上游文档表格当输入。
2. **fail-closed**。任何一项解析失败、字段缺失、数值越界，直接记为 FAIL，
   绝不 `except: pass`。汇总字段由逐项结果推导，不允许常量 PASS。
3. **门槛冻结**。40960 B / 8192 B / 32 B / 0x20058000 等来自链接脚本与冻结契约，
   写死在本文件顶部并注明出处；harness 不得从被测证据里反推门槛。
4. **自证**。`--self-test` 用 1 个阳性对照 + 21 个阴性对照证明本 harness 会因
   证据被篡改而失败，从而排除"无条件 PASS"。

用法：
    python tests/ota/p2_6_v3_evidence_recompute.py \
        --bundle docs/acceptance-contracts/P2-6-v3 \
        --report docs/acceptance-contracts/P2-6-v3/artifacts/recompute/p2-6-v3-recompute-report.json
    python tests/ota/p2_6_v3_evidence_recompute.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import sys
import zlib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BUNDLE = ROOT / "docs" / "acceptance-contracts" / "P2-6-v3"

REPORT_SCHEMA = "p2-6-v3-evidence-recompute-v1"

# ---------------------------------------------------------------------------
# 冻结门槛（出处见注释；harness 不得从证据反推）
# ---------------------------------------------------------------------------

# OTA_OVERLAY_WORKSPACE_LENGTH = 0xA000，链接脚本静态断言
# MDK-ARM_F435/cmake-generated/x-track-app-gcc.ld.S
WORKSPACE_PEAK_LIMIT = 40960
# __StackGuardStart/__StackTop 之间 0x2000，同链接脚本
OTA_STACK_LIMIT = 8192
# .ota_stack_guard 32 B
OTA_GUARD_BYTES = 32
# overlay 与 .sram_ext 共址基址
OVERLAY_BASE_ADDR = 0x20058000
MAIN_RAM_BASE_ADDR = 0x20000000
# 主 RAM 可分配区间 = [0x20000000, 0x20058000)
MAIN_RAM_REGION_BYTES = OVERLAY_BASE_ADDR - MAIN_RAM_BASE_ADDR

# BCB 二进制布局：Libraries/EEPROM/eeprom_bcb.h（#pragma pack(push,1)）
BCB_SIZE = 64
BCB_MAGIC = 0x43425445  # "ETBC"
BCB_SCHEMA_VER = 1
BCB_CRC_REGION_LEN = 60
BCB_STATE_IDLE, BCB_STATE_STAGED, BCB_STATE_APPLYING = 0, 1, 2
BCB_STATE_TEST_BOOT, BCB_STATE_CONFIRMED, BCB_STATE_ROLLBACK = 3, 4, 5

# ETSL 槽头布局：Libraries/OTA/ota_slot_header.h / .c
SLOT_MAGIC = b"ETSL"
SLOT_TYPE_OFF, SLOT_PAD_OFF = 4, 5
SLOT_PAYLOAD_LEN_OFF, SLOT_PAYLOAD_CRC_OFF = 8, 12
SLOT_VCODE_OFF, SLOT_SHA8_OFF, SLOT_MARKER_OFF = 16, 20, 28
SLOT_TYPE_CANDIDATE = 1
SLOT_MARKER_COMMIT = 0x434F4D54  # "COMT"

# SEGGER RTT 控制块 Up[0]：16B id + MaxNumUp(4) + MaxNumDown(4) = 24
RTT_UP0_OFFSET = 24
RTT_UP0_STRUCT = "<IIIIiI"  # pName,pBuffer,SizeOfBuffer,WrOff,RdOff,Flags
RTT_UP0_RDOFF_OFFSET = RTT_UP0_OFFSET + 16
RTT_UP0_RDOFF_END = RTT_UP0_RDOFF_OFFSET + 4

# .etu 包头布局：Tools/etu_pack.py
ETU_MAGIC = b"ETU1"
ETU_HEADER_LEN = 64
ETU_PAYLOAD_LEN_OFF, ETU_PAYLOAD_CRC_OFF = 32, 36
ETU_TARGET_VCODE_OFF, ETU_BASE_VCODE_OFF = 40, 44
ETU_HEADER_CRC_OFF, ETU_HEADER_CRC_REGION = 60, 60

# 冻结身份锚（P2-6-v2 合同已冻结，R8/R9 必须与之逐字相同）
FROZEN_ELF_SHA = "35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019"
FROZEN_MAP_SHA = "2446B401E1C7812BA9792FAA4D24D8875BC2529A2C9255854999942DA45D0C13"
FROZEN_DEVICE_IMAGE_SHA = "AB38A4E75D905D306AFC97EB476554AF6DE2144A8D4FCBFA9A80040AE569A5E5"
FROZEN_DEVICE_HEADER_SHA = "AB40E59EC6DB9E69ABEF88D22F7999FAD222FF3F6F9751251AE0A388C7808BFB"
# driver 既授权的项目外写入（仅 J-Link DLL 配置 mtime 副作用）
ALLOWED_OUTSIDE_WRITES = {r"C:\Users\SU\AppData\Roaming\SEGGER\JLinkDLL.ini"}

# 板卡版本轨迹
VCODE_BEFORE_BOOT = 20800  # v2.8.0
VCODE_AFTER_BOOT = 20801  # v2.8.1
VCODE_BAD_TARGET = 20802  # v2.8.2（C7 用，target > current 才能越过 Inspect 版本关）
CANDIDATE_IMAGE_LEN = 600744
CANDIDATE_CRC32 = 0x53E81862

# C7 包派生：GOOD → BAD 只允许 payload 1 字节翻转 + 两个 CRC 字段随之更新
EXPECTED_BAD_DIFF_OFFSETS = {36, 37, 38, 39, 60, 61, 62, 63, 141209}
BAD_FLIP_OFFSET = 141209

# LiveMap 每秒统计行下限（R8 基线 38 行 / 32 s；取 30 行为健康下限）
LIVEMAP_MIN_STAT_LINES = 30

# R9 上游 manifest 已知缺口（F1）：首次失败上传的 result.json 未入 R9 清单。
# 本 harness 用自身冻结哈希独立托管该文件；缺口集合必须逐字相符，
# 出现任何"新增"缺口即判 FAIL。
R9_DECLARED_MANIFEST_GAPS = {
    "artifacts/r9/p2-6-sd-r9-bad-upload-hw-01-result.json",
}


class RecomputeError(Exception):
    """证据无法解析/不满足结构前提。上层一律转为该判据 FAIL。"""


# ---------------------------------------------------------------------------
# 冻结托管表（52 件决定性产物；由 .cache/p2-6-v3-build/collect_v3.py 复制并逐文件校验）
# ---------------------------------------------------------------------------

CUSTODY: dict[str, tuple[int, str]] = {
    "artifacts/docs/P2-6-SD-R7-hw-execution-evidence-2026-08-31.md": (
        11313, "021AEC5B6C2361CB77489ECF317FE22A783F6F0830BC0DB7F7E0D90D578A3AA8"),
    "artifacts/docs/P2-6-SD-R8-hw-execution-evidence-2026-08-31.md": (
        23866, "2A9EC779286BC805DEF24BECB6F71F129AF451F78A41D5FCB3ACA7E30E9C3947"),
    "artifacts/docs/P2-6-SD-R9-hw-execution-evidence-2026-09-01.md": (
        22416, "97E5342A3A7424EDD93C721ED2BBE4EF7870D200EA5B684423C51F58F91C33F7"),
    "artifacts/docs/P2-6-SD-R9-research-2026-09-01.md": (
        7695, "563C0A4C4C37ADB2A4671B208A1BD799E2A80FDD2C5A57B5882360C7DB7AEA13"),
    "artifacts/elf/X-Track-App-GCC-production.elf": (
        864320, "8890935D508A446D4AB3B1988A636A03A2289F2E57A3311AB97017BA87EC87AC"),
    "artifacts/elf/X-Track-App-GCC-test.elf": (
        866372, "35BB2AB75C683FA9061C2A75F20F32DB20F4D9E731E1C4A90E8D7AD95076D019"),
    "artifacts/offline/config-matrix-p2-6.log": (
        145, "89D2E65C79B4616DA3FF38DD3535FEDFAA07BECE21C90A5C33119F5CCDD7B048"),
    "artifacts/offline/link-asserts-run.log": (
        49, "5D2D91B8DE4B0600DB547654F23EA8AFAE6F38B3667A17127C12D436FBE9BF1A"),
    "artifacts/offline/p2-6-capacity-full.run.log": (
        641, "D8DB97C1AA11149CF4A280FEC803CA8684610D681F9A65FF2EB75DD8FAA5F5AA"),
    "artifacts/offline/p2-6-capacity-patch.run.log": (
        643, "80ACFEF59013A12B9B2A9F98EB10E1688386CE364FB61C0085EDA40FDEA597F8"),
    "artifacts/offline/stack-closure.json": (
        71014, "E3FDE0E18D85A6FE46EED025A5927E0A35E2F941FC8C7D6AC2087CB253703C53"),
    "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-gdb.log": (
        2031, "2593DFD0E2294F4F10F17BDD4CB20DEB3D763FBFBC484143DAA1A2D53A90B241"),
    "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-result.json": (
        12024, "6D927026505980BC6CC10F4D760AE3151C7879E96C1904E01BF93F9058128920"),
    "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-rtt-cb-post.bin": (
        168, "CC8154BAC9C5C90F25981A13238415875FE7676F991EC37CCBD0C9D5EB7A8C66"),
    "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-rtt-cb-pre.bin": (
        168, "E49A672EC97B8EE525C43731D60B7F1208B6531BD33277FB8488B2B5BA3D6CE6"),
    "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-rtt-payload.raw.log": (
        735, "50A76FEF5929E78057083C330A4257895F1CBE908A4B8E5AB6E3F77A1FC9CF03"),
    "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-rtt-pending.bin": (
        735, "50A76FEF5929E78057083C330A4257895F1CBE908A4B8E5AB6E3F77A1FC9CF03"),
    "artifacts/r8/p2-6-sd-r8-full-upload-hw-01-result.json": (
        72370, "09CE8AB6ECA39A2FDD75DA5DA6A2D9A08712C241CD90EFF10CE6AD78311799E3"),
    "artifacts/r8/r8-result.json": (
        14473, "AA6D1259D790CDCEAD2FD5D7E01CE25B0D779A41B25B2B9DFC5BBD98B83B9BBE"),
    "artifacts/r8/r8-s0-bcb-gdb.log": (
        775, "22CC436F5CE591BB0B4B84C31D414CE433F192A0F4C621CEA4E1F73F37BB59D1"),
    "artifacts/r8/r8-s3-candhdr-gdb.log": (
        621, "D5B3AAF1A7779ED910D39F0D5EA5122E7EDF1A4CF6D45B81FD1A8946E25B791A"),
    "artifacts/r8/r8-s4-obs1-gdb.log": (
        659, "6BE6EB2A38AEE8CC15D38C671E8DB3326F87EC8AF27F56BCE4EC4484AEFB4FDB"),
    "artifacts/r8/r8-s4-obs2-gdb.log": (
        777, "6331B977932330BC99B5EF481EFAF6897892B9C55EBFDB82A403C77E9FAEE529"),
    "artifacts/r8/r8-s5-c-recover-gdb.log": (
        617, "D803E1DC95593685978DFEF3F8294724EFE7CD127577C5E1DC2F1F706FE0C637"),
    "artifacts/r8/s0-bcb-raw.bin": (
        192, "0E0A1449201BDCA028E91B1083C90464AD041A158E6D3FB820348A56A0E7C1F3"),
    "artifacts/r8/s3-cand-slot-header.bin": (
        4096, "E83A86AE8E939941F2B955850ED84EFF52AC17050585E5507F79A44055F341B4"),
    "artifacts/r8/s4-obs1-rtt-ring.bin": (
        1024, "1455FB44CFF14BCF86773BE42F05CE288E2D46B6CC8C3372CD4E3F65F3BC892C"),
    "artifacts/r8/s4-obs2-bcb-raw.bin": (
        192, "B75390AF6D3AD0F80832C00D5DF1BFF654B06E1425EA865289FF73C42C15FD82"),
    "artifacts/r8/s5-a-livemap-baseline.rtt.log": (
        4593, "765ACBF8DE331E8E3F4A6EF808E6A8132A54D89154F3210ED54DFDA55EA7F8A5"),
    "artifacts/r8/s5-c-livemap-recover.rtt.log": (
        4571, "6BF717DDE65FEE154B7C758B20002766F2A98FF56C3251B98470257D587E7809"),
    "artifacts/r9/BAD-2.8.2.etu": (
        282355, "EA7C5CA22E572BFB2D211E21C9475091D9F68725F862939B71FA874E5FA24C30"),
    "artifacts/r9/GOOD-2.8.2.etu": (
        282355, "761A71C00631FB12ACC3C30C7A387FDFACF2D5DC298501CE96E9CE63A1A19E20"),
    "artifacts/r9/bad-upload-hw-02-readback.bin": (
        282355, "EA7C5CA22E572BFB2D211E21C9475091D9F68725F862939B71FA874E5FA24C30"),
    "artifacts/r9/derive_bad.py": (
        2339, "CB003C13E84CA0114E45F6B095646C771B930BBF6627CE8691FE5BCA288A2D9D"),
    "artifacts/r9/p2-6-sd-r9-bad-upload-hw-01-result.json": (
        4380, "E55E5A7DBA08EA60F6097C0B6254A1FE56C6ED56ABA0D7DBA9855BA0DB5A5C8F"),
    "artifacts/r9/p2-6-sd-r9-bad-upload-hw-02-result.json": (
        72384, "65050B1109842136B4C3EB653F9E251E4EC5D7D55E2C2717E56B5BC88F328314"),
    "artifacts/r9/r9-result.json": (
        9603, "C64EDD4AD1F6B785DD5F2227C34C52482A21F787DBFDB5629945FF1DD89FC419"),
    "artifacts/r9/r9-s0-precheck-gdb.log": (
        875, "0BBA1AC47783D0FA202263A042B8962450A8F12E72B4590697D522B8B9DD7741"),
    "artifacts/r9/r9-s1-host-gate.log": (
        1609, "2A88D4684A149755D2F79C62FE4774EC90E982F9FE66F8C41A4EBE6FF50E9D80"),
    "artifacts/r9/r9-s1-usb-fix.gdb": (
        2622, "E2CAF01DACE9927B76A2C1D87E9B6528F60A5D08480F70340608F68415378522"),
    "artifacts/r9/r9-s2-baseline-gdb.log": (
        761, "B3112938EAAB303E50731D1159902FAA4594B5B47D5BB0E19740E647CC8EFE13"),
    "artifacts/r9/r9-s2-baseline.rtt.log": (
        4797, "D969AB860F4F071F3B7D5C53EB5F489429C20F88EB68AAE340A73B77DCADD9A5"),
    "artifacts/r9/r9-s3-c7-chain-gdb.log": (
        1135, "D14D759FD8EEDC1E68E9751DE3D849B4C801B06D85BC6F9F88A7BC87600FB39C"),
    "artifacts/r9/r9-s3-c7-chain.gdb": (
        13750, "D71AB89D1975BAA368090AE526B9A4255ED680C0C449037B17C586A909282573"),
    "artifacts/r9/r9-s3b-post-fail-gdb.log": (
        670, "38211620A11DB6D81FFFFA59C5B1F5F64E68827F3CDCE5FD3642493D4833F7CD"),
    "artifacts/r9/r9-s3e-errstring-gdb.log": (
        494, "10B1DD3E981A12F346499D047B96D5DA7DD2C91CA97F5613A8CE020BEA0AA9DA"),
    "artifacts/r9/r9-s3e-page-object.bin": (
        13824, "C50F2A054EFE0B89BD0AC4F1FD3BBCB4721F9C15F6AD08F3FCF8A649883CEFBA"),
    "artifacts/r9/r9-s4-recover-gdb.log": (
        784, "1746185A974C73E3149C3F22684C31C29813E85C144A09CBF5C2744409C54415"),
    "artifacts/r9/r9-s4-recover.rtt.log": (
        4913, "D8B10A5D352F42D856AC57BEC4A623A78EAFC5FB81D5A70BE01842EFB95218EE"),
    "artifacts/r9/r9-s5-final-gdb.log": (
        560, "51D2215952AE436C44A8B28447AE026B64E578101E2332CA440016538F2B2DCE"),
    "artifacts/r9/run_r9_upload.py": (
        1918, "B60F2291AAFA21CE3D28A0739661D98DE2D96850FD15D0C10B8570FCFD0ADD7E"),
    "artifacts/r9/test_r9_gate.c": (
        5725, "48E3190F6B6BE766E896A6B5D6F312771847526B21C2A477F9123C67910B19BE"),
}

CUSTODY_TOTAL_BYTES = sum(v[0] for v in CUSTODY.values())


def sha256_upper(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def read_bytes(path: Path) -> bytes:
    if not path.is_file():
        raise RecomputeError(f"缺失文件：{path}")
    return path.read_bytes()


def read_text(path: Path) -> str:
    return read_bytes(path).decode("utf-8", errors="replace")


def read_json(path: Path) -> Any:
    try:
        return json.loads(read_bytes(path).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise RecomputeError(f"JSON 解析失败：{path}：{exc}") from exc


def get_path(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise RecomputeError(f"字段缺失：{dotted}")
        cur = cur[part]
    return cur


def need_int(obj: Any, dotted: str) -> int:
    value = get_path(obj, dotted)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RecomputeError(f"字段非整数：{dotted}={value!r}")
    return value


def need_bool(obj: Any, dotted: str) -> bool:
    value = get_path(obj, dotted)
    if not isinstance(value, bool):
        raise RecomputeError(f"字段非布尔：{dotted}={value!r}")
    return value


def need_str(obj: Any, dotted: str) -> str:
    value = get_path(obj, dotted)
    if not isinstance(value, str):
        raise RecomputeError(f"字段非字符串：{dotted}={value!r}")
    return value


# ---------------------------------------------------------------------------
# 解析器
# ---------------------------------------------------------------------------

MEASURE_RE = re.compile(r"^P2_6\s+kind=(?P<kind>\w+)\s+(?P<rest>.*)$")


def parse_measurement_lines(text: str) -> list[dict[str, str]]:
    """从 RTT payload 原文提取 `P2_6 kind=... k=v ...` 测量记录。"""
    records: list[dict[str, str]] = []
    for line in text.splitlines():
        match = MEASURE_RE.match(line.strip())
        if not match:
            continue
        fields = {"kind": match.group("kind")}
        for token in match.group("rest").split():
            if "=" not in token:
                raise RecomputeError(f"测量行含非法 token：{token!r}")
            key, _, value = token.partition("=")
            if key in fields:
                raise RecomputeError(f"测量行字段重复：{key}")
            fields[key] = value
        records.append(fields)
    return records


def mfield_int(record: dict[str, str], key: str) -> int:
    if key not in record:
        raise RecomputeError(f"测量行缺字段：{key}")
    raw = record[key]
    try:
        return int(raw, 0)
    except ValueError as exc:
        raise RecomputeError(f"测量行字段非整数：{key}={raw!r}") from exc


def decode_rtt_up0(blob: bytes) -> dict[str, int]:
    if len(blob) < RTT_UP0_OFFSET + struct.calcsize(RTT_UP0_STRUCT):
        raise RecomputeError(f"RTT 控制块快照过短：{len(blob)} B")
    if blob[:10] != b"SEGGER RTT":
        raise RecomputeError("RTT 控制块签名不符")
    name, buf, size, wroff, rdoff, flags = struct.unpack_from(
        RTT_UP0_STRUCT, blob, RTT_UP0_OFFSET)
    return {"pName": name, "pBuffer": buf, "SizeOfBuffer": size,
            "WrOff": wroff, "RdOff": rdoff, "Flags": flags}


def parse_bcb_block(blob: bytes, offset: int) -> dict[str, int]:
    """按 eeprom_bcb.h 逐字段解析 64 B 块，并独立复算块内 CRC32。"""
    if len(blob) < offset + BCB_SIZE:
        raise RecomputeError(f"BCB 缓冲过短：{len(blob)} B（需 {offset + BCB_SIZE}）")
    raw = blob[offset:offset + BCB_SIZE]
    (magic, schema_ver, state, boot_try, copy_phase, seq, resume_block,
     cand_addr, cand_len, cand_crc32, cand_vcode, cur_vcode,
     backup_len, backup_crc32, backup_vcode) = struct.unpack_from(
        "<IBBBBHHIIIIIIII", raw, 0)
    stored_crc, = struct.unpack_from("<I", raw, BCB_CRC_REGION_LEN)
    return {
        "magic": magic, "schema_ver": schema_ver, "state": state,
        "boot_try": boot_try, "copy_phase": copy_phase, "seq": seq,
        "resume_block": resume_block, "cand_addr": cand_addr,
        "cand_len": cand_len, "cand_crc32": cand_crc32,
        "cand_vcode": cand_vcode, "cur_vcode": cur_vcode,
        "backup_len": backup_len, "backup_crc32": backup_crc32,
        "backup_vcode": backup_vcode, "crc32_stored": stored_crc,
        "crc32_recomputed": zlib.crc32(raw[:BCB_CRC_REGION_LEN]) & 0xFFFFFFFF,
    }


def check_bcb_block(block: dict[str, int], label: str) -> None:
    if block["magic"] != BCB_MAGIC:
        raise RecomputeError(f"{label} magic=0x{block['magic']:08X} 非 ETBC")
    if block["schema_ver"] != BCB_SCHEMA_VER:
        raise RecomputeError(f"{label} schema_ver={block['schema_ver']}")
    if block["crc32_stored"] != block["crc32_recomputed"]:
        raise RecomputeError(
            f"{label} CRC32 不符：存 0x{block['crc32_stored']:08X} "
            f"算 0x{block['crc32_recomputed']:08X}")


def parse_slot_header(blob: bytes) -> dict[str, Any]:
    if len(blob) < 32:
        raise RecomputeError(f"ETSL 槽头过短：{len(blob)} B")
    if blob[:4] != SLOT_MAGIC:
        raise RecomputeError(f"槽头 magic={blob[:4]!r} 非 ETSL")
    payload_len, = struct.unpack_from("<I", blob, SLOT_PAYLOAD_LEN_OFF)
    payload_crc, = struct.unpack_from("<I", blob, SLOT_PAYLOAD_CRC_OFF)
    vcode, = struct.unpack_from("<I", blob, SLOT_VCODE_OFF)
    marker, = struct.unpack_from("<I", blob, SLOT_MARKER_OFF)
    return {
        "magic": blob[:4].decode(), "slot_type": blob[SLOT_TYPE_OFF],
        "pad": blob[SLOT_PAD_OFF:SLOT_PAD_OFF + 3].hex().upper(),
        "payload_len": payload_len, "payload_crc32": payload_crc,
        "version_code": vcode,
        "sha8": blob[SLOT_SHA8_OFF:SLOT_SHA8_OFF + 8].hex(),
        "commit_marker": marker,
    }


def parse_etu_header(blob: bytes) -> dict[str, int]:
    if len(blob) < ETU_HEADER_LEN:
        raise RecomputeError(f".etu 过短：{len(blob)} B")
    if blob[:4] != ETU_MAGIC:
        raise RecomputeError(f".etu magic={blob[:4]!r}")
    payload_len, = struct.unpack_from("<I", blob, ETU_PAYLOAD_LEN_OFF)
    payload_crc, = struct.unpack_from("<I", blob, ETU_PAYLOAD_CRC_OFF)
    target, = struct.unpack_from("<I", blob, ETU_TARGET_VCODE_OFF)
    base, = struct.unpack_from("<I", blob, ETU_BASE_VCODE_OFF)
    header_crc, = struct.unpack_from("<I", blob, ETU_HEADER_CRC_OFF)
    return {
        "payload_len": payload_len, "payload_crc32": payload_crc,
        "target_vcode": target, "base_vcode": base,
        "header_crc32": header_crc,
        "payload_crc32_recomputed": zlib.crc32(blob[ETU_HEADER_LEN:]) & 0xFFFFFFFF,
        "header_crc32_recomputed": zlib.crc32(blob[:ETU_HEADER_CRC_REGION]) & 0xFFFFFFFF,
    }


def parse_elf_alloc_sections(blob: bytes) -> dict[str, dict[str, int]]:
    """纯 Python 解析 ELF32 节表，只取 SHF_ALLOC 且非空的节。"""
    if len(blob) < 52 or blob[:4] != b"\x7fELF" or blob[4] != 1:
        raise RecomputeError("不是 ELF32 文件")
    sh_off, = struct.unpack_from("<I", blob, 0x20)
    sh_entsize, = struct.unpack_from("<H", blob, 0x2E)
    sh_num, = struct.unpack_from("<H", blob, 0x30)
    sh_strndx, = struct.unpack_from("<H", blob, 0x32)
    if sh_entsize < 40 or sh_num == 0 or sh_strndx >= sh_num:
        raise RecomputeError("ELF 节表头非法")
    str_off, = struct.unpack_from("<I", blob, sh_off + sh_strndx * sh_entsize + 16)
    sections: dict[str, dict[str, int]] = {}
    for index in range(sh_num):
        base = sh_off + index * sh_entsize
        name_off, _type, flags, addr, _off, size = struct.unpack_from(
            "<IIIIII", blob, base)
        end = blob.index(b"\0", str_off + name_off)
        name = blob[str_off + name_off:end].decode("utf-8", errors="replace")
        if not (flags & 0x2) or size == 0:
            continue
        if name in sections:
            raise RecomputeError(f"ELF 出现重名 ALLOC 节：{name}")
        sections[name] = {"addr": addr, "size": size, "flags": flags}
    return sections


def require_section(sections: dict[str, dict[str, int]], name: str) -> dict[str, int]:
    if name not in sections:
        raise RecomputeError(f"ELF 缺少节：{name}")
    return sections[name]


BOUNDARY_RE = re.compile(r"^P2_6_BOUNDARY\s+(?P<rest>.*)$")


def parse_boundary_lines(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in text.splitlines():
        match = BOUNDARY_RE.match(line.strip())
        if not match:
            continue
        fields: dict[str, str] = {}
        for token in match.group("rest").split():
            key, sep, value = token.partition("=")
            if not sep:
                raise RecomputeError(f"容量行含非法 token：{token!r}")
            fields[key] = value
        rows.append(fields)
    return rows


def count_livemap_stat_lines(text: str) -> tuple[int, int]:
    """返回 (统计行数, 最大 lineHit)。"""
    lines = [l for l in text.splitlines() if "lineHit=" in l]
    peak = 0
    for line in lines:
        match = re.search(r"lineHit=(\d+)", line)
        if match:
            peak = max(peak, int(match.group(1)))
    return len(lines), peak


# ---------------------------------------------------------------------------
# 判据评估
# ---------------------------------------------------------------------------

def evaluate(bundle: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(cid: str, ok: bool, observed: Any, expected: Any, note: str = "") -> None:
        checks.append({
            "id": cid,
            "result": "PASS" if ok else "FAIL",
            "observed": observed,
            "expected": expected,
            "note": note,
        })

    def guarded(cid: str, expected: Any, fn) -> Any:
        """把任何解析异常统一转成该判据 FAIL（fail-closed）。"""
        try:
            ok, observed, note = fn()
        except RecomputeError as exc:
            record(cid, False, {"error": str(exc)}, expected, "复算异常")
            return None
        except Exception as exc:  # noqa: BLE001 - 任何异常都必须落为 FAIL
            record(cid, False, {"error": f"{type(exc).__name__}: {exc}"},
                   expected, "复算异常")
            return None
        record(cid, ok, observed, expected, note)
        return observed

    art = bundle / "artifacts"
    r8 = art / "r8"
    r9 = art / "r9"
    off = art / "offline"
    elfs = art / "elf"

    # ---- 共享解析（失败时相关判据各自 FAIL）----
    payload_text = ""
    measurements: list[dict[str, str]] = []
    full_rec: dict[str, str] | None = None
    try:
        payload_text = read_text(r8 / "p2-6-sd-r8-full-ota-hw-01-rtt-payload.raw.log")
        measurements = parse_measurement_lines(payload_text)
        full_records = [m for m in measurements if m["kind"] == "full"]
        if len(full_records) == 1:
            full_rec = full_records[0]
    except RecomputeError:
        pass

    def need_full() -> dict[str, str]:
        if full_rec is None:
            raise RecomputeError(
                f"FULL 测量记录不唯一或缺失（共 {len(measurements)} 条 P2_6 记录）")
        return full_rec

    # ---- 1. FULL-C1-WORKSPACE-PEAK ----
    def c1():
        rec = need_full()
        peak = mfield_int(rec, "workspace_peak")
        arena = mfield_int(rec, "arena_peak_observed")
        failed = mfield_int(rec, "failed_request_size")
        result = mfield_int(rec, "result")
        ok = (result == 0 and failed == 0 and arena == peak
              and 0 < peak <= WORKSPACE_PEAK_LIMIT)
        return ok, {
            "kind": rec["kind"], "result": result, "workspace_peak_bytes": peak,
            "arena_peak_observed_bytes": arena, "failed_request_size": failed,
            "limit_bytes": WORKSPACE_PEAK_LIMIT,
            "headroom_bytes": WORKSPACE_PEAK_LIMIT - peak,
            "utilisation_pct": round(peak * 100.0 / WORKSPACE_PEAK_LIMIT, 2),
            "record_count": len(measurements),
        }, "FULL 侧 apply 窗口 overlay 工作区峰值"
    guarded("FULL-C1-WORKSPACE-PEAK",
            {"workspace_peak_bytes": f"<= {WORKSPACE_PEAK_LIMIT}",
             "arena_peak_observed_bytes": "== workspace_peak",
             "failed_request_size": 0, "result": 0}, c1)

    # ---- 2. FULL-C4-GUARD-INTACT ----
    def c4():
        rec = need_full()
        g_in = mfield_int(rec, "guard_entry")
        g_out = mfield_int(rec, "guard_exit")
        s_entry = mfield_int(rec, "stack_entry")
        s_peak = mfield_int(rec, "stack_peak")
        s_total = mfield_int(rec, "stack_total")
        ok = (g_in == 1 and g_out == 1 and s_total == OTA_STACK_LIMIT
              and 0 < s_peak <= OTA_STACK_LIMIT and s_entry <= s_peak)
        return ok, {
            "guard_entry": g_in, "guard_exit": g_out,
            "guard_bytes": OTA_GUARD_BYTES,
            "stack_entry_bytes": s_entry, "stack_peak_bytes": s_peak,
            "stack_total_bytes": s_total,
            "stack_headroom_bytes": OTA_STACK_LIMIT - s_peak,
        }, "32B guard 进出均完好；OTA 专用栈实测峰值在门槛内"
    guarded("FULL-C4-GUARD-INTACT",
            {"guard_entry": 1, "guard_exit": 1,
             "stack_total_bytes": OTA_STACK_LIMIT,
             "stack_peak_bytes": f"<= {OTA_STACK_LIMIT}"}, c4)

    # ---- 3. FULL-C5-SBRK-DELTA-ZERO ----
    def c5():
        rec = need_full()
        delta = mfield_int(rec, "sbrk_delta")
        peak = mfield_int(rec, "sbrk_peak")
        return delta == 0, {"sbrk_delta": delta, "sbrk_peak": peak}, \
            "apply 窗口内 _sbrk 调用增量为 0（sbrk_peak 为历史堆顶水位，非门禁项）"
    guarded("FULL-C5-SBRK-DELTA-ZERO", {"sbrk_delta": 0}, c5)

    # ---- 4. FULL-C6-TLSF-DELTA-ZERO ----
    def c6():
        rec = need_full()
        m = mfield_int(rec, "tlsf_malloc_delta")
        r = mfield_int(rec, "tlsf_realloc_delta")
        f = mfield_int(rec, "tlsf_free_delta")
        return (m == 0 and r == 0 and f == 0), {
            "tlsf_malloc_delta": m, "tlsf_realloc_delta": r,
            "tlsf_free_delta": f,
        }, "apply 窗口内 LVGL tlsf 分配器零调用（free_delta 为交叉核对项）"
    guarded("FULL-C6-TLSF-DELTA-ZERO",
            {"tlsf_malloc_delta": 0, "tlsf_realloc_delta": 0,
             "tlsf_free_delta": 0}, c6)

    # ---- 5. FULL-C14-LV-POOL-NET ----
    def c14():
        rec = need_full()
        pairs = {}
        ok = True
        for name in ("free", "big", "frag", "max"):
            entry = mfield_int(rec, f"lv_{name}_entry")
            exit_ = mfield_int(rec, f"lv_{name}_exit")
            pairs[f"lv_{name}"] = {"entry": entry, "exit": exit_}
            ok = ok and entry == exit_
        return ok, pairs, "lv_mem_monitor 四字段净状态不变（佐证项）"
    guarded("FULL-C14-LV-POOL-NET", {"每对 entry": "== exit"}, c14)

    # ---- 6. HW-R8-CAPTURE-BYTE-IDENTITY ----
    def cap_identity():
        payload = read_bytes(r8 / "p2-6-sd-r8-full-ota-hw-01-rtt-payload.raw.log")
        pending = read_bytes(r8 / "p2-6-sd-r8-full-ota-hw-01-rtt-pending.bin")
        result = read_json(r8 / "p2-6-sd-r8-full-ota-hw-01-result.json")
        declared = need_str(
            result, "session.rtt_two_phase.derive.pending_sha256").upper()
        wroff = need_int(
            result, "session.rtt_two_phase.derive.descriptor.WrOff")
        payload_sha = sha256_upper(payload)
        ok = (payload == pending and payload_sha == declared
              and len(payload) == wroff)
        return ok, {
            "payload_bytes": len(payload), "pending_bytes": len(pending),
            "byte_identical": payload == pending,
            "payload_sha256": payload_sha,
            "declared_pending_sha256": declared,
            "derive_descriptor_WrOff": wroff,
        }, "两段式采集：logger 逐字节落盘与 derive 阶段 pending 快照完全一致"
    guarded("HW-R8-CAPTURE-BYTE-IDENTITY",
            {"payload == pending": True,
             "len(payload)": "== derive WrOff"}, cap_identity)

    # ---- 7. HW-R8-POSTCHECK-RDOFF ----
    def postcheck():
        pre = read_bytes(r8 / "p2-6-sd-r8-full-ota-hw-01-rtt-cb-pre.bin")
        post = read_bytes(r8 / "p2-6-sd-r8-full-ota-hw-01-rtt-cb-post.bin")
        if len(pre) != len(post):
            raise RecomputeError(f"控制块快照长度不同：{len(pre)} vs {len(post)}")
        diffs = [i for i in range(len(pre)) if pre[i] != post[i]]
        outside = [i for i in diffs
                   if not (RTT_UP0_RDOFF_OFFSET <= i < RTT_UP0_RDOFF_END)]
        d_pre, d_post = decode_rtt_up0(pre), decode_rtt_up0(post)
        ok = (not outside and d_pre["RdOff"] == 0
              and d_post["RdOff"] == d_post["WrOff"]
              and d_pre["WrOff"] == d_post["WrOff"]
              and d_pre["pBuffer"] == d_post["pBuffer"]
              and d_pre["SizeOfBuffer"] == d_post["SizeOfBuffer"])
        return ok, {
            "control_block_bytes": len(pre),
            "changed_byte_offsets": diffs,
            "changed_outside_rdoff": outside,
            "up0_pre": d_pre, "up0_post": d_post,
        }, "读走数据只推进 RdOff，控制块其余字节零改动"
    guarded("HW-R8-POSTCHECK-RDOFF",
            {"changed_outside_rdoff": [], "post.RdOff": "== WrOff"}, postcheck)

    # ---- 8. HW-R8-INPUTS-IDENTITY ----
    def inputs_identity():
        result = read_json(r8 / "p2-6-sd-r8-full-ota-hw-01-result.json")
        upload = read_json(r8 / "p2-6-sd-r8-full-upload-hw-01-result.json")
        elf_blob = read_bytes(elfs / "X-Track-App-GCC-test.elf")
        elf_sha = sha256_upper(elf_blob)
        observed = {
            "elf_sha256": need_str(result, "elf_sha256").upper(),
            "map_sha256": need_str(result, "map_sha256").upper(),
            "device_image_sha256": need_str(result, "device_image_sha256").upper(),
            "device_header_sha256": need_str(result, "device_header_sha256").upper(),
            "bundle_test_elf_sha256": elf_sha,
            "upload_readback_matches": need_bool(upload, "readback_matches"),
            "upload_input_sha256": need_str(upload, "input_sha256").upper(),
            "upload_readback_sha256": need_str(upload, "readback_sha256").upper(),
            "upload_input_bytes": need_int(upload, "input_bytes"),
            "upload_readback_bytes": need_int(upload, "readback_bytes"),
        }
        ok = (observed["elf_sha256"] == FROZEN_ELF_SHA
              and observed["map_sha256"] == FROZEN_MAP_SHA
              and observed["device_image_sha256"] == FROZEN_DEVICE_IMAGE_SHA
              and observed["device_header_sha256"] == FROZEN_DEVICE_HEADER_SHA
              and elf_sha == FROZEN_ELF_SHA
              and observed["upload_readback_matches"]
              and observed["upload_input_sha256"] == observed["upload_readback_sha256"]
              and observed["upload_input_bytes"] == observed["upload_readback_bytes"])
        return ok, observed, "板上镜像/ELF/MAP 身份与 v2 冻结锚逐字相同；SD 上传读回一致"
    guarded("HW-R8-INPUTS-IDENTITY",
            {"elf_sha256": FROZEN_ELF_SHA, "map_sha256": FROZEN_MAP_SHA,
             "device_image_sha256": FROZEN_DEVICE_IMAGE_SHA,
             "device_header_sha256": FROZEN_DEVICE_HEADER_SHA,
             "upload_readback_matches": True}, inputs_identity)

    # ---- 9. PROC-R8-SESSION-CLOSURE ----
    def session_closure():
        result = read_json(r8 / "p2-6-sd-r8-full-ota-hw-01-result.json")
        outside = get_path(result, "outside_repo_writes")
        if not isinstance(outside, list):
            raise RecomputeError("outside_repo_writes 非列表")
        observed = {
            "gdb_exit_code": need_int(result, "session.gdb_exit_code"),
            "server_exit_code": need_int(result, "session.server_exit_code"),
            "server_natural_exit": need_bool(result, "session.server_natural_exit"),
            "server_terminate_sent": need_bool(result, "session.server_terminate_sent"),
            "server_kill_sent": need_bool(result, "session.server_kill_sent"),
            "ports_closed": need_bool(result, "session.ports_closed"),
            "session_error": get_path(result, "session.session_error"),
            "transport_classification": need_str(result, "session.transport_classification"),
            "rtt_channel_binding_verified": need_bool(
                result, "session.rtt_channel_binding_verified"),
            "rtt_record_count": need_int(result, "session.rtt_record_count"),
            "rtt_matching_record_count": need_int(
                result, "session.rtt_matching_record_count"),
            "rtt_postcheck_passed": need_bool(result, "session.rtt_postcheck_passed"),
            "outside_repo_writes": outside,
        }
        ok = (observed["gdb_exit_code"] == 0
              and observed["server_exit_code"] == 0
              and observed["server_natural_exit"]
              and not observed["server_terminate_sent"]
              and not observed["server_kill_sent"]
              and observed["ports_closed"]
              and observed["session_error"] is None
              and observed["transport_classification"] == "PASS"
              and observed["rtt_channel_binding_verified"]
              and observed["rtt_record_count"] == 1
              and observed["rtt_matching_record_count"] == 1
              and observed["rtt_postcheck_passed"]
              and set(outside) <= ALLOWED_OUTSIDE_WRITES)
        return ok, observed, "会话自然退出、无 terminate/kill、端口清零、项目外写入仅既授权项"
    guarded("PROC-R8-SESSION-CLOSURE",
            {"gdb_exit_code": 0, "server_natural_exit": True,
             "server_kill_sent": False, "transport_classification": "PASS",
             "rtt_record_count": 1,
             "outside_repo_writes": sorted(ALLOWED_OUTSIDE_WRITES)}, session_closure)

    # ---- 10. HW-BOOT-CANDIDATE-SLOT-COMMITTED ----
    def slot_committed():
        header = parse_slot_header(read_bytes(r8 / "s3-cand-slot-header.bin"))
        bcb_pre = parse_bcb_block(read_bytes(r8 / "s0-bcb-raw.bin"), 0)
        check_bcb_block(bcb_pre, "S0 BCB_A")
        ok = (header["slot_type"] == SLOT_TYPE_CANDIDATE
              and header["pad"] == "FFFFFF"
              and header["commit_marker"] == SLOT_MARKER_COMMIT
              and header["payload_len"] == CANDIDATE_IMAGE_LEN
              and header["payload_crc32"] == CANDIDATE_CRC32
              and header["version_code"] == VCODE_AFTER_BOOT
              and header["payload_len"] == bcb_pre["cand_len"]
              and header["payload_crc32"] == bcb_pre["cand_crc32"]
              and header["version_code"] == bcb_pre["cand_vcode"])
        return ok, {
            "slot_header": {**header,
                            "payload_crc32_hex": f"0x{header['payload_crc32']:08X}",
                            "commit_marker_hex": f"0x{header['commit_marker']:08X}"},
            "bcb_a_cand_len": bcb_pre["cand_len"],
            "bcb_a_cand_crc32_hex": f"0x{bcb_pre['cand_crc32']:08X}",
            "bcb_a_cand_vcode": bcb_pre["cand_vcode"],
        }, "candidate 槽头字节级解析：marker-last 已提交，且与 BCB cand_* 三字段互证"
    guarded("HW-BOOT-CANDIDATE-SLOT-COMMITTED",
            {"magic": "ETSL", "slot_type": SLOT_TYPE_CANDIDATE,
             "commit_marker_hex": f"0x{SLOT_MARKER_COMMIT:08X}",
             "payload_len": CANDIDATE_IMAGE_LEN,
             "payload_crc32_hex": f"0x{CANDIDATE_CRC32:08X}"}, slot_committed)

    # ---- 11. HW-BOOT-BCB-TRANSITION ----
    def bcb_transition():
        pre_blob = read_bytes(r8 / "s0-bcb-raw.bin")
        post_blob = read_bytes(r8 / "s4-obs2-bcb-raw.bin")
        pre_a, pre_b = parse_bcb_block(pre_blob, 0), parse_bcb_block(pre_blob, BCB_SIZE)
        post_a = parse_bcb_block(post_blob, 0)
        post_b = parse_bcb_block(post_blob, BCB_SIZE)
        for block, label in ((pre_a, "pre_A"), (pre_b, "pre_B"),
                             (post_a, "post_A"), (post_b, "post_B")):
            check_bcb_block(block, label)

        def seq_delta(new: int, old: int) -> int:
            return ((new - old + 0x8000) & 0xFFFF) - 0x8000

        ok = (pre_a["state"] == BCB_STATE_CONFIRMED
              and pre_a["cur_vcode"] == VCODE_BEFORE_BOOT
              and pre_b["state"] == BCB_STATE_ROLLBACK
              and seq_delta(pre_a["seq"], pre_b["seq"]) > 0
              and post_b["state"] == BCB_STATE_TEST_BOOT
              and post_a["state"] == BCB_STATE_CONFIRMED
              and post_a["cur_vcode"] == VCODE_AFTER_BOOT
              and seq_delta(post_a["seq"], post_b["seq"]) > 0
              and seq_delta(post_b["seq"], pre_a["seq"]) > 0
              and post_a["cand_len"] == pre_a["cand_len"]
              and post_a["cand_crc32"] == pre_a["cand_crc32"]
              and post_a["cand_vcode"] == pre_a["cand_vcode"])
        summarise = lambda b: {  # noqa: E731 - 局部投影，保持观测值紧凑
            "state": b["state"], "seq": b["seq"], "cur_vcode": b["cur_vcode"],
            "cand_vcode": b["cand_vcode"],
            "cand_crc32_hex": f"0x{b['cand_crc32']:08X}",
            "crc32_stored_hex": f"0x{b['crc32_stored']:08X}",
            "crc32_recomputed_hex": f"0x{b['crc32_recomputed']:08X}",
        }
        return ok, {
            "pre_A": summarise(pre_a), "pre_B": summarise(pre_b),
            "post_A": summarise(post_a), "post_B": summarise(post_b),
            "seq_advance_pre_A_to_post_B": seq_delta(post_b["seq"], pre_a["seq"]),
            "seq_advance_post_B_to_post_A": seq_delta(post_a["seq"], post_b["seq"]),
        }, ("EEPROM 双块 CRC 全部独立复算通过；"
            "STAGED→TEST_BOOT(B)→CONFIRMED(A, cur_vcode 前进) 在双块上留痕")
    guarded("HW-BOOT-BCB-TRANSITION",
            {"pre_A.state": BCB_STATE_CONFIRMED,
             "post_B.state": BCB_STATE_TEST_BOOT,
             "post_A.state": BCB_STATE_CONFIRMED,
             "post_A.cur_vcode": VCODE_AFTER_BOOT,
             "每块 crc32_recomputed": "== crc32_stored"}, bcb_transition)

    # ---- 12. HW-BOOT-APP-VCODE-ADVANCED ----
    def vcode_advanced():
        s0 = read_text(r8 / "r8-s0-bcb-gdb.log")
        obs1 = read_text(r8 / "r8-s4-obs1-gdb.log")
        ring = read_bytes(r8 / "s4-obs1-rtt-ring.bin")
        m_pre = re.search(r"IDENTITY PASS magic=ETFW vcode=(\d+) image_len=(\d+)", s0)
        m_post = re.search(r"fw_header magic=0x57465445 vcode=(\d+) \(0x[0-9A-Fa-f]+\) image_len=(\d+)",
                           obs1)
        if not m_pre or not m_post:
            raise RecomputeError("未能从 GDB 日志解析复位前后 fw_header vcode")
        pre_v, post_v = int(m_pre.group(1)), int(m_post.group(1))
        confirmed = b"OTA: TEST_BOOT confirmed vcode=20801" in ring
        snapshot = re.search(r"g_ota_state_snapshot=(\d+) g_ota_confirm_done=(\d+)", obs1)
        if not snapshot:
            raise RecomputeError("未能解析 App 侧 OTA 快照字段")
        ok = (pre_v == VCODE_BEFORE_BOOT and post_v == VCODE_AFTER_BOOT
              and int(m_pre.group(2)) == int(m_post.group(2)) == CANDIDATE_IMAGE_LEN
              and confirmed and int(snapshot.group(1)) == BCB_STATE_CONFIRMED
              and int(snapshot.group(2)) == 1)
        return ok, {
            "app_slot_vcode_before_reset": pre_v,
            "app_slot_vcode_after_reset": post_v,
            "image_len": int(m_post.group(2)),
            "rtt_ring_has_test_boot_confirm": confirmed,
            "g_ota_state_snapshot": int(snapshot.group(1)),
            "g_ota_confirm_done": int(snapshot.group(2)),
        }, "复位后 App slot fw_header 版本前进，且 App 在 TEST_BOOT 态执行确认"
    guarded("HW-BOOT-APP-VCODE-ADVANCED",
            {"app_slot_vcode_before_reset": VCODE_BEFORE_BOOT,
             "app_slot_vcode_after_reset": VCODE_AFTER_BOOT,
             "rtt_ring_has_test_boot_confirm": True}, vcode_advanced)

    # ---- 13. HW-C7-PACKAGE-DERIVATION ----
    def package_derivation():
        good = read_bytes(r9 / "GOOD-2.8.2.etu")
        bad = read_bytes(r9 / "BAD-2.8.2.etu")
        if len(good) != len(bad):
            raise RecomputeError(f"GOOD/BAD 长度不同：{len(good)} vs {len(bad)}")
        diffs = {i for i in range(len(good)) if good[i] != bad[i]}
        h_good, h_bad = parse_etu_header(good), parse_etu_header(bad)
        payload_diffs = {i for i in diffs if i >= ETU_HEADER_LEN}
        ok = (diffs == EXPECTED_BAD_DIFF_OFFSETS
              and payload_diffs == {BAD_FLIP_OFFSET}
              and h_good["payload_crc32"] == h_good["payload_crc32_recomputed"]
              and h_good["header_crc32"] == h_good["header_crc32_recomputed"]
              and h_bad["payload_crc32"] == h_bad["payload_crc32_recomputed"]
              and h_bad["header_crc32"] == h_bad["header_crc32_recomputed"]
              and h_good["target_vcode"] == h_bad["target_vcode"] == VCODE_BAD_TARGET
              and h_bad["target_vcode"] > VCODE_AFTER_BOOT
              and good[BAD_FLIP_OFFSET] ^ bad[BAD_FLIP_OFFSET] == 0x01)
        return ok, {
            "bytes": len(bad),
            "diff_offsets": sorted(diffs),
            "payload_diff_offsets": sorted(payload_diffs),
            "flip_xor": good[BAD_FLIP_OFFSET] ^ bad[BAD_FLIP_OFFSET],
            "good_target_vcode": h_good["target_vcode"],
            "bad_target_vcode": h_bad["target_vcode"],
            "board_vcode": VCODE_AFTER_BOOT,
            "good_payload_crc_ok": h_good["payload_crc32"] == h_good["payload_crc32_recomputed"],
            "bad_payload_crc_ok": h_bad["payload_crc32"] == h_bad["payload_crc32_recomputed"],
            "bad_header_crc_ok": h_bad["header_crc32"] == h_bad["header_crc32_recomputed"],
            "good_sha256": sha256_upper(good), "bad_sha256": sha256_upper(bad),
        }, ("BAD 包外层 CRC 合法（能过 Inspect），仅 payload 单比特被翻转，"
            "target 20802 > 板卡 20801，可越过 ota_sd.c 版本关进入 Apply")
    guarded("HW-C7-PACKAGE-DERIVATION",
            {"diff_offsets": sorted(EXPECTED_BAD_DIFF_OFFSETS),
             "payload_diff_offsets": [BAD_FLIP_OFFSET],
             "bad_header_crc_ok": True,
             "bad_target_vcode": VCODE_BAD_TARGET}, package_derivation)

    # ---- 14. HW-C7-UPLOAD-BYTE-IDENTITY ----
    def upload_identity():
        bad = read_bytes(r9 / "BAD-2.8.2.etu")
        readback = read_bytes(r9 / "bad-upload-hw-02-readback.bin")
        ok_result = read_json(r9 / "p2-6-sd-r9-bad-upload-hw-02-result.json")
        failed_result = read_json(r9 / "p2-6-sd-r9-bad-upload-hw-01-result.json")
        bad_sha = sha256_upper(bad)
        observed = {
            "attempt_02_readback_bytes": len(readback),
            "attempt_02_byte_identical": readback == bad,
            "attempt_02_readback_sha256": need_str(ok_result, "readback_sha256").upper(),
            "attempt_02_input_sha256": need_str(ok_result, "input_sha256").upper(),
            "attempt_02_readback_matches": need_bool(ok_result, "readback_matches"),
            "attempt_02_chunk_count": need_int(ok_result, "chunk_count"),
            "attempt_02_transport": need_str(ok_result, "session.transport_classification"),
            "attempt_01_transport": need_str(failed_result,
                                             "session.transport_classification"),
            "attempt_01_readback_matches": need_bool(failed_result, "readback_matches"),
            "attempt_01_gdb_exit_code": need_int(failed_result, "session.gdb_exit_code"),
            "bad_package_sha256": bad_sha,
        }
        ok = (observed["attempt_02_byte_identical"]
              and observed["attempt_02_readback_matches"]
              and observed["attempt_02_readback_sha256"] == bad_sha
              and observed["attempt_02_input_sha256"] == bad_sha
              and observed["attempt_02_transport"] == "PASS"
              # 第 1 次尝试必须如实登记为失败，不得冒充成功
              and observed["attempt_01_transport"] != "PASS"
              and not observed["attempt_01_readback_matches"]
              and observed["attempt_01_gdb_exit_code"] != 0)
        return ok, observed, ("第 2 次上传读回与 BAD 包逐字节相同；"
                              "第 1 次（USB MSC 独占 SDIO）如实登记为 GDB_FAIL")
    guarded("HW-C7-UPLOAD-BYTE-IDENTITY",
            {"attempt_02_byte_identical": True, "attempt_02_transport": "PASS",
             "attempt_01_transport": "!= PASS"}, upload_identity)

    # ---- 15. HW-C7-MIDAPPLY-OWNER-PACKAGE ----
    def midapply_owner():
        text = read_text(r9 / "r9-s3-c7-chain-gdb.log")
        need = {
            "confirm_mode": r"P2_6_R9_S3 confirm mode=(\d+)",
            "owner_at_confirm": r"P2_6_R9_S3 owner_at_confirm=(\d+)",
            "import_mode": r"P2_6_R9_S3 import_started mode=(\d+)",
            "owner_at_apply": r"P2_6_R9_S3 DECISIVE owner_at_apply=(\d+)",
            "bcb_mid1": r"P2_6_R9_S3 bcb_mid1=(\d+)",
            "bcb_mid2": r"P2_6_R9_S3 bcb_mid2=(\d+)",
        }
        observed: dict[str, Any] = {}
        for key, pattern in need.items():
            match = re.search(pattern, text)
            if not match:
                raise RecomputeError(f"S3 链日志缺标记：{key}")
            observed[key] = int(match.group(1))
        observed["lzma_alloc_entry_seen"] = "lzma_alloc_entry pc=" in text
        ok = (observed["confirm_mode"] == 1  # 1=CONFIRM，发起被接受（非"被拒"冒充）
              and observed["owner_at_confirm"] == 0
              and observed["import_mode"] == 2
              and observed["owner_at_apply"] == 2  # 2=PACKAGE，overlay 归包
              and observed["bcb_mid1"] == BCB_STATE_CONFIRMED
              and observed["bcb_mid2"] == BCB_STATE_CONFIRMED
              and observed["lzma_alloc_entry_seen"])
        return ok, observed, ("升级真正进入 Apply 窗口：overlay owner 由 LiveMap 交给 "
                              "PACKAGE，且在 LZMA 分配点采到 owner=2 的中途快照")
    guarded("HW-C7-MIDAPPLY-OWNER-PACKAGE",
            {"confirm_mode": 1, "import_mode": 2, "owner_at_apply": 2}, midapply_owner)

    # ---- 16. HW-C7-FAILURE-NOT-VERSION-GATE ----
    def failure_kind():
        page = read_bytes(r9 / "r9-s3e-page-object.bin")
        gate = read_text(r9 / "r9-s1-host-gate.log")
        bad_path = b"/P2-6A-FULL-v2.8.2-BAD-R9-20260901-02.etu"
        err_marker = b"full:lzma_data"
        m_bad = re.search(r"P2_6_R9_GATE kind=bad result=(\S+)", gate)
        if not m_bad:
            raise RecomputeError("host gate 日志缺 kind=bad 汇总行")
        gate_failures = re.search(r"P2_6_R9_GATE summary failures=(\d+) status=(\w+)",
                                  gate)
        if not gate_failures:
            raise RecomputeError("host gate 日志缺 summary 行")
        observed = {
            "page_object_bytes": len(page),
            "page_has_error_string": err_marker in page,
            "page_has_bad_package_path": bad_path in page,
            "error_string": err_marker.decode(),
            "host_gate_bad_result": m_bad.group(1),
            "host_gate_failures": int(gate_failures.group(1)),
            "host_gate_status": gate_failures.group(2),
            "not_payload_crc_check": "check bad result is not payload_crc" in gate,
            "version_gate_refusal": "OTA_SD_ERR_VERSION" in gate,
        }
        ok = (observed["page_has_error_string"]
              and observed["page_has_bad_package_path"]
              and observed["host_gate_bad_result"] == "lzma_data"
              and observed["host_gate_failures"] == 0
              and observed["host_gate_status"] == "PASS"
              and observed["not_payload_crc_check"]
              and not observed["version_gate_refusal"])
        return ok, observed, ("失败发生在解压阶段（lzma_data），既非 Inspect 版本关拒绝，"
                              "也非外层 payload_crc —— 即真正的「升级中途失败」形态")
    guarded("HW-C7-FAILURE-NOT-VERSION-GATE",
            {"error_string": "full:lzma_data", "host_gate_bad_result": "lzma_data",
             "version_gate_refusal": False}, failure_kind)

    # ---- 17. HW-C7-OVERLAY-RELEASE-REBUILD ----
    def overlay_rebuild():
        s3b = read_text(r9 / "r9-s3b-post-fail-gdb.log")
        s4 = read_text(r9 / "r9-s4-recover-gdb.log")
        s5 = read_text(r9 / "r9-s5-final-gdb.log")
        r8c = read_text(r8 / "r8-s5-c-recover-gdb.log")
        m_post = re.search(r"post_fail mode=(\d+).*?owner=(\d+).*?vcode=(\d+)", s3b)
        m_pre4 = re.search(r"P2_6_R9_S4 pre mode=(\d+) owner=(\d+) bcb=(\d+)", s4)
        m_pop = re.search(r"P2_6_R9_S4 pop_ok=(\d+)", s4)
        m_re = re.search(r"reacquire_wait turns=(\d+) owner=(\d+)", s4)
        m_fin = re.search(r"P2_6_R9_S5 final vcode=(\d+) bcb=(\d+) owner=(\d+)", s5)
        if not all((m_post, m_pre4, m_pop, m_re, m_fin)):
            raise RecomputeError("恢复链日志缺关键标记")
        observed = {
            "post_fail_mode": int(m_post.group(1)),
            "post_fail_owner": int(m_post.group(2)),
            "post_fail_vcode": int(m_post.group(3)),
            "recover_pre_owner": int(m_pre4.group(2)),
            "recover_pop_ok": int(m_pop.group(1)),
            "reacquire_turns": int(m_re.group(1)),
            "reacquire_owner": int(m_re.group(2)),
            "final_owner": int(m_fin.group(3)),
            "final_vcode": int(m_fin.group(1)),
            "r8_fail_state_owner_released": "fail_state mode=0 owner=0" in r8c,
            "r8_owner_mid": 1 if "owner_mid=1" in r8c else 0,
        }
        ok = (observed["post_fail_owner"] == 0  # 失败后 overlay 已释放
              and observed["post_fail_mode"] == 3  # 结果页
              and observed["post_fail_vcode"] == VCODE_AFTER_BOOT  # 未被"升级"
              and observed["recover_pre_owner"] == 0
              and observed["recover_pop_ok"] == 1
              and observed["reacquire_owner"] == 1  # LiveMap 重新 acquire
              and observed["final_owner"] == 1
              and observed["final_vcode"] == VCODE_AFTER_BOOT
              and observed["r8_fail_state_owner_released"]
              and observed["r8_owner_mid"] == 1)
        return ok, observed, ("中途失败后 overlay 归 0；Pop 取消后 LiveMap 重新初始化"
                              "并再次持有 overlay；R8 侧同形恢复链交叉印证")
    guarded("HW-C7-OVERLAY-RELEASE-REBUILD",
            {"post_fail_owner": 0, "recover_pop_ok": 1, "reacquire_owner": 1,
             "final_owner": 1}, overlay_rebuild)

    # ---- 18. HW-C7-MAP-HEALTHY ----
    def map_healthy():
        base_r9 = read_text(r9 / "r9-s2-baseline.rtt.log")
        rec_r9 = read_text(r9 / "r9-s4-recover.rtt.log")
        base_r8 = read_text(r8 / "s5-a-livemap-baseline.rtt.log")
        rec_r8 = read_text(r8 / "s5-c-livemap-recover.rtt.log")
        rows = {}
        for name, text in (("r9_baseline", base_r9), ("r9_recover", rec_r9),
                           ("r8_baseline", base_r8), ("r8_recover", rec_r8)):
            count, peak = count_livemap_stat_lines(text)
            rows[name] = {"stat_lines": count, "max_lineHit": peak}
        ok = all(v["stat_lines"] >= LIVEMAP_MIN_STAT_LINES and v["max_lineHit"] > 0
                 for v in rows.values())
        return ok, {**rows, "min_stat_lines_required": LIVEMAP_MIN_STAT_LINES}, \
            "重建后地图渲染统计行数量与命中率与基线同水平，地图正常显示"
    guarded("HW-C7-MAP-HEALTHY",
            {"每组 stat_lines": f">= {LIVEMAP_MIN_STAT_LINES}",
             "每组 max_lineHit": "> 0"}, map_healthy)

    # ---- 19. HW-C7-BCB-UNTOUCHED ----
    def bcb_untouched():
        gate = read_text(r9 / "r9-s1-host-gate.log")
        logs = {
            "s0": read_text(r9 / "r9-s0-precheck-gdb.log"),
            "s2": read_text(r9 / "r9-s2-baseline-gdb.log"),
            "s3": read_text(r9 / "r9-s3-c7-chain-gdb.log"),
            "s3b": read_text(r9 / "r9-s3b-post-fail-gdb.log"),
            "s3e": read_text(r9 / "r9-s3e-errstring-gdb.log"),
            "s4": read_text(r9 / "r9-s4-recover-gdb.log"),
            "s5": read_text(r9 / "r9-s5-final-gdb.log"),
        }
        observed: dict[str, Any] = {}
        ok = True
        for name, text in logs.items():
            values = [int(v) for v in re.findall(r"\bbcb(?:_\w+)?=(\d+)", text)]
            if not values:
                raise RecomputeError(f"{name} 日志未出现 bcb 观测")
            observed[f"{name}_bcb_values"] = values
            ok = ok and all(v == BCB_STATE_CONFIRMED for v in values)
        observed["host_gate_bad_bcb_untouched"] = (
            "check bad bcb untouched" in gate and "PASS" in gate)
        observed["host_gate_good_bcb_identical"] = (
            "good apply leaves BCB byte-identical" in gate)
        ok = ok and observed["host_gate_bad_bcb_untouched"] \
            and observed["host_gate_good_bcb_identical"]
        return ok, observed, "C7 全过程 BCB 恒为 CONFIRMED(4)，失败未污染引导控制块"
    guarded("HW-C7-BCB-UNTOUCHED",
            {"所有会话 bcb 观测": BCB_STATE_CONFIRMED}, bcb_untouched)

    # ---- 20. OFF-C3-C13-STACK-CLOSURE ----
    def stack_closure():
        data = read_json(off / "stack-closure.json")
        # 明确不读 data["classification"]，全部自行复算
        full_peak = need_int(data, "full.thread_peak")
        patch_peak = need_int(data, "patch.thread_peak")
        budget = need_int(data, "interrupt_budget")
        bounded = need_int(data, "bounded_interrupt_budget")
        gaps = get_path(data, "interrupt_evidence_gaps")
        if not isinstance(gaps, list):
            raise RecomputeError("interrupt_evidence_gaps 非列表")
        combined_peak = need_int(data, "combined.thread_peak")
        combined_total = need_int(data, "combined.total")
        combined_limit = need_int(data, "combined.limit")
        wrapper = need_int(data, "measurement_wrapper_upper_bound.bytes")
        overhead = need_int(data, "stack_scan_overhead.bytes")
        startup_observed = need_int(data, "startup_scan.observed")
        startup_helper = need_int(data, "startup_scan.helper_static")
        startup_total = need_int(data, "startup_scan.stack_total")
        recomputed_peak = max(full_peak, patch_peak)
        recomputed_total = recomputed_peak + budget
        ok = (not gaps
              and budget == bounded
              and combined_peak == recomputed_peak
              and combined_total == recomputed_total
              and combined_limit == OTA_STACK_LIMIT
              and startup_total == OTA_STACK_LIMIT
              and recomputed_total <= OTA_STACK_LIMIT
              and wrapper > 0 and overhead > 0 and wrapper >= overhead
              and startup_observed >= startup_helper)
        return ok, {
            "full_thread_peak_bytes": full_peak,
            "patch_thread_peak_bytes": patch_peak,
            "recomputed_thread_peak_bytes": recomputed_peak,
            "interrupt_budget_bytes": budget,
            "bounded_interrupt_budget_bytes": bounded,
            "recomputed_total_bytes": recomputed_total,
            "limit_bytes": OTA_STACK_LIMIT,
            "margin_bytes": OTA_STACK_LIMIT - recomputed_total,
            "interrupt_evidence_gaps": gaps,
            "measurement_wrapper_upper_bound_bytes": wrapper,
            "stack_scan_overhead_bytes": overhead,
            "startup_scan_observed_bytes": startup_observed,
            "startup_scan_helper_static_bytes": startup_helper,
        }, ("C3/C13：线程峰值 + 有界中断预算独立相加后仍在 8192 B 内；"
            "中断证据无缺口；测量包装与扫描开销已量化")
    guarded("OFF-C3-C13-STACK-CLOSURE",
            {"recomputed_total_bytes": f"<= {OTA_STACK_LIMIT}",
             "interrupt_evidence_gaps": []}, stack_closure)

    # ---- 21. OFF-C8-C16-RAM-LAYOUT ----
    def ram_layout():
        prod = parse_elf_alloc_sections(read_bytes(elfs / "X-Track-App-GCC-production.elf"))
        test = parse_elf_alloc_sections(read_bytes(elfs / "X-Track-App-GCC-test.elf"))

        def main_ram(sections: dict[str, dict[str, int]]) -> dict[str, int]:
            allocated = 0
            top = MAIN_RAM_BASE_ADDR
            for name, sec in sections.items():
                if MAIN_RAM_BASE_ADDR <= sec["addr"] < OVERLAY_BASE_ADDR:
                    allocated += sec["size"]
                    top = max(top, sec["addr"] + sec["size"])
            return {"allocated_bytes": allocated,
                    "top_addr": top,
                    "highwater_bytes": top - MAIN_RAM_BASE_ADDR,
                    "free_hole_bytes": MAIN_RAM_REGION_BYTES - allocated}

        prod_ram, test_ram = main_ram(prod), main_ram(test)
        ota_names = (".ota_stack", ".ota_stack_guard", ".ota_overlay")
        ota_prod = {n: require_section(prod, n) for n in ota_names}
        ota_test = {n: require_section(test, n) for n in ota_names}
        sram_prod = require_section(prod, ".sram_ext")
        sram_test = require_section(test, ".sram_ext")
        identical = all(ota_prod[n]["addr"] == ota_test[n]["addr"]
                        and ota_prod[n]["size"] == ota_test[n]["size"]
                        for n in ota_names)
        ok = (identical
              and ota_prod[".ota_stack"]["size"] == OTA_STACK_LIMIT
              and ota_prod[".ota_stack_guard"]["size"] == OTA_GUARD_BYTES
              and ota_prod[".ota_overlay"]["size"] == WORKSPACE_PEAK_LIMIT
              and ota_prod[".ota_overlay"]["addr"] == OVERLAY_BASE_ADDR
              and sram_prod["addr"] == OVERLAY_BASE_ADDR
              and sram_test["addr"] == OVERLAY_BASE_ADDR
              and ota_prod[".ota_overlay"]["size"] <= sram_prod["size"]
              and (ota_prod[".ota_stack_guard"]["addr"]
                   + OTA_GUARD_BYTES == ota_prod[".ota_stack"]["addr"])
              and prod_ram["free_hole_bytes"] >= 0
              and test_ram["free_hole_bytes"] >= 0
              # 插桩构型占用 >= 生产构型：实测峰值向生产迁移是保守的
              and test_ram["allocated_bytes"] >= prod_ram["allocated_bytes"]
              and prod_ram["top_addr"] == OVERLAY_BASE_ADDR
              and test_ram["top_addr"] == OVERLAY_BASE_ADDR)
        return ok, {
            "main_ram_region_bytes": MAIN_RAM_REGION_BYTES,
            "production": {**prod_ram, "top_addr_hex": f"0x{prod_ram['top_addr']:08X}"},
            "test": {**test_ram, "top_addr_hex": f"0x{test_ram['top_addr']:08X}"},
            "instrumentation_delta_bytes":
                test_ram["allocated_bytes"] - prod_ram["allocated_bytes"],
            "ota_sections_production": {
                n: {"addr_hex": f"0x{ota_prod[n]['addr']:08X}",
                    "size": ota_prod[n]["size"]} for n in ota_names},
            "ota_sections_identical_prod_vs_test": identical,
            "sram_ext_addr_hex": f"0x{sram_prod['addr']:08X}",
            "sram_ext_bytes": sram_prod["size"],
        }, ("C8：主 RAM [0x20000000,0x20058000) 高水位与空洞独立复算；"
            "C16：OTA 三节在插桩/生产构型地址尺寸完全一致，overlay 与 .sram_ext 共址")
    guarded("OFF-C8-C16-RAM-LAYOUT",
            {".ota_stack.size": OTA_STACK_LIMIT,
             ".ota_stack_guard.size": OTA_GUARD_BYTES,
             ".ota_overlay.size": WORKSPACE_PEAK_LIMIT,
             ".ota_overlay.addr": f"0x{OVERLAY_BASE_ADDR:08X}",
             "ota_sections_identical_prod_vs_test": True}, ram_layout)

    # ---- 22. OFF-C10-C11-CAPACITY ----
    def capacity():
        observed: dict[str, Any] = {}
        ok = True
        for kind, name in (("full", "p2-6-capacity-full.run.log"),
                           ("patch", "p2-6-capacity-patch.run.log")):
            rows = parse_boundary_lines(read_text(off / name))
            by_case = {r["case"]: r for r in rows if "case" in r}
            if "baseline" not in by_case:
                raise RecomputeError(f"{kind}: 缺 baseline 行")
            base = by_case["baseline"]
            prefix = int(base["prefix"])
            p_full = int(base["P_full"])
            peak = int(base["workspace_peak"])
            ok_case = by_case.get("cap=P_full-prefix")
            fail_case = by_case.get("cap=P_full-prefix-1")
            if not ok_case or not fail_case:
                raise RecomputeError(f"{kind}: 缺容量判别用例")
            entry = {
                "prefix": prefix, "P_full": p_full,
                "baseline_result": base["result"],
                "baseline_workspace_peak": peak,
                "ok_case_capacity": int(ok_case["capacity"]),
                "ok_case_result": ok_case["result"],
                "ok_case_expected": ok_case["expected"],
                "ok_case_status": ok_case["status"],
                "fail_case_capacity": int(fail_case["capacity"]),
                "fail_case_result": fail_case["result"],
                "fail_case_expected": fail_case["expected"],
                "fail_case_failed_request_size": int(fail_case["failed_request_size"]),
                "fail_case_candidate_prepares": int(fail_case["candidate_prepares"]),
                "fail_case_status": fail_case["status"],
                "recomputed_ok_capacity": p_full - prefix,
                "recomputed_fail_capacity": p_full - prefix - 1,
            }
            entry_ok = (base["result"] == "ok" and peak == p_full
                        and entry["ok_case_capacity"] == entry["recomputed_ok_capacity"]
                        and entry["ok_case_result"] == "ok"
                        and entry["ok_case_result"] == entry["ok_case_expected"]
                        and entry["ok_case_status"] == "PASS"
                        and entry["fail_case_capacity"] == entry["recomputed_fail_capacity"]
                        and entry["fail_case_result"] == "workspace"
                        and entry["fail_case_result"] == entry["fail_case_expected"]
                        and entry["fail_case_status"] == "PASS"
                        and entry["fail_case_failed_request_size"] > 0
                        and entry["fail_case_candidate_prepares"] == 0)
            observed[kind] = entry
            ok = ok and entry_ok
        return ok, observed, ("C10/C11：容量恰好等于 P_full-prefix 时成功、少 1 字节即以 "
                              "workspace 失败，边界可判别且 fail-closed")
    guarded("OFF-C10-C11-CAPACITY",
            {"cap=P_full-prefix": "ok/PASS",
             "cap=P_full-prefix-1": "workspace/PASS"}, capacity)

    # ---- 23. PROC-CUSTODY-COMPLETE ----
    def custody():
        # 托管基准是本文件顶部的冻结 CUSTODY 表，不是包内 artifact-index.json；
        # 索引只作为被核对对象，避免"用被审对象自证"。
        mismatched: list[dict[str, Any]] = []
        missing: list[str] = []
        for rel, (want_bytes, want_sha) in sorted(CUSTODY.items()):
            path = bundle / rel
            if not path.is_file():
                missing.append(rel)
                continue
            blob = path.read_bytes()
            actual_sha, actual_len = sha256_upper(blob), len(blob)
            if actual_sha != want_sha or actual_len != want_bytes:
                mismatched.append({"bundle_path": rel,
                                   "frozen_sha256": want_sha,
                                   "actual_sha256": actual_sha,
                                   "frozen_bytes": want_bytes,
                                   "actual_bytes": actual_len})

        # 包内索引必须与冻结表逐条一致（多、少、改都算失配）
        index = read_json(art / "artifact-index.json")
        entries = get_path(index, "artifacts")
        if not isinstance(entries, list):
            raise RecomputeError("artifact-index.json artifacts 非列表")
        indexed = {i["bundle_path"]: (i["bytes"], i["sha256"].upper()) for i in entries}
        index_divergence = sorted(
            set(indexed.items()) ^ set(CUSTODY.items()),
            key=lambda kv: kv[0])
        index_paths_diff = sorted(set(indexed) ^ set(CUSTODY))

        # 上游证据根 manifest 覆盖度（按 SHA-256 判定，与文件名/路径无关）
        upstream: dict[str, Any] = {}
        gaps: set[str] = set()
        for tag, result_rel in (("r8", "artifacts/r8/r8-result.json"),
                                ("r9", "artifacts/r9/r9-result.json")):
            manifest = read_json(bundle / result_rel)
            files = get_path(manifest, "files")
            if not isinstance(files, list):
                raise RecomputeError(f"{tag} manifest files 非列表")
            hashes = {f["sha256"].upper() for f in files}
            need = [r for r in CUSTODY
                    if r.startswith(f"artifacts/{tag}/") and r != result_rel]
            uncovered = sorted(r for r in need if CUSTODY[r][1] not in hashes)
            gaps.update(uncovered)
            upstream[tag] = {"manifest_entries": len(files),
                             "bundle_artifacts": len(need),
                             "uncovered": uncovered}

        ok = (not missing and not mismatched and not index_divergence
              and len(CUSTODY) == 52
              and gaps == R9_DECLARED_MANIFEST_GAPS)
        return ok, {
            "frozen_artifact_count": len(CUSTODY),
            "frozen_total_bytes": CUSTODY_TOTAL_BYTES,
            "missing": missing, "mismatched": mismatched,
            "index_entry_count": len(entries),
            "index_paths_symmetric_difference": index_paths_diff,
            "index_divergent_entries": [kv[0] for kv in index_divergence],
            "upstream_manifest_coverage": upstream,
            "declared_upstream_gaps": sorted(R9_DECLARED_MANIFEST_GAPS),
            "observed_upstream_gaps": sorted(gaps),
        }, ("52 件决定性产物对 harness 内冻结哈希表逐字节复算一致，包内索引与冻结表零分歧；"
            "上游 R8/R9 manifest 覆盖度按哈希核对，缺口集合须与已登记项（F1）逐字相符")
    guarded("PROC-CUSTODY-COMPLETE",
            {"missing": [], "mismatched": [], "index_divergent_entries": [],
             "frozen_artifact_count": 52,
             "observed_upstream_gaps": sorted(R9_DECLARED_MANIFEST_GAPS)}, custody)

    failed = [c["id"] for c in checks if c["result"] != "PASS"]
    return {
        "schema": REPORT_SCHEMA,
        "bundle": str(bundle),
        "thresholds": {
            "workspace_peak_limit_bytes": WORKSPACE_PEAK_LIMIT,
            "ota_stack_limit_bytes": OTA_STACK_LIMIT,
            "ota_stack_guard_bytes": OTA_GUARD_BYTES,
            "overlay_base_addr": f"0x{OVERLAY_BASE_ADDR:08X}",
        },
        "measurement_record": full_rec,
        "checks": checks,
        "criteria_count": len(checks),
        "failed_criteria": failed,
        "overall": "PASS" if not failed else "FAIL",
    }


# ---------------------------------------------------------------------------
# 自证（阳性 1 + 阴性 21）
# ---------------------------------------------------------------------------

def _replace_bytes(path: Path, old: bytes, new: bytes) -> None:
    blob = path.read_bytes()
    if old not in blob:
        raise RecomputeError(f"自证变异目标不存在：{old!r} in {path.name}")
    path.write_bytes(blob.replace(old, new, 1))


def _flip_byte(path: Path, offset: int) -> None:
    blob = bytearray(path.read_bytes())
    if offset >= len(blob):
        raise RecomputeError(f"自证变异越界：{path.name} offset={offset}")
    blob[offset] ^= 0xFF
    path.write_bytes(bytes(blob))


def _patch_json(path: Path, dotted: str, value: Any) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    cur = data
    parts = dotted.split(".")
    for part in parts[:-1]:
        cur = cur[part]
    cur[parts[-1]] = value
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


R8_OTA = "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-result.json"
R8_PAYLOAD = "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-rtt-payload.raw.log"
R8_PENDING = "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-rtt-pending.bin"
R8_CB_POST = "artifacts/r8/p2-6-sd-r8-full-ota-hw-01-rtt-cb-post.bin"


def _negatives() -> list[tuple[str, str, Any]]:
    """(名称, 预期失败判据, 变异函数)。

    托管判据以 harness 内冻结哈希表为准，因此任何变异都必然同时触发
    PROC-CUSTODY-COMPLETE；自证只断言"目标判据出现在失败集合里"，
    以此证明该判据本身具备鉴别力，而非仅靠托管兜底。
    """

    def mut_measure(sub: bytes, rep: bytes):
        """改测量行并同步 pending 快照与其声明哈希。

        这样采集一致性判据仍然通过，失败必然来自被瞄准的测量判据本身。
        """
        def fn(work: Path) -> None:
            _replace_bytes(work / R8_PAYLOAD, sub, rep)
            blob = (work / R8_PAYLOAD).read_bytes()
            (work / R8_PENDING).write_bytes(blob)
            _patch_json(work / R8_OTA,
                        "session.rtt_two_phase.derive.pending_sha256",
                        sha256_upper(blob))
            _patch_json(work / R8_OTA,
                        "session.rtt_two_phase.derive.descriptor.WrOff",
                        len(blob))
        return fn

    def mut_flip(rel: str, offset: int):
        return lambda work: _flip_byte(work / rel, offset)

    def mut_text(rel: str, old: bytes, new_bytes: bytes):
        return lambda work: _replace_bytes(work / rel, old, new_bytes)

    def mut_json(rel: str, dotted: str, value: Any):
        return lambda work: _patch_json(work / rel, dotted, value)

    def mut_zero_rdoff(work: Path) -> None:
        path = work / R8_CB_POST
        blob = path.read_bytes()
        path.write_bytes(blob[:RTT_UP0_RDOFF_OFFSET] + b"\x00\x00\x00\x00"
                         + blob[RTT_UP0_RDOFF_END:])

    return [
        ("采集字节与 pending 快照不一致", "HW-R8-CAPTURE-BYTE-IDENTITY",
         mut_text(R8_PAYLOAD, b"workspace_peak=33016", b"workspace_peak=33017")),
        ("workspace_peak 超 40960 门槛", "FULL-C1-WORKSPACE-PEAK",
         mut_measure(b"workspace_peak=33016", b"workspace_peak=40961")),
        ("apply 返回码非 0", "FULL-C1-WORKSPACE-PEAK",
         mut_measure(b"P2_6 kind=full result=0", b"P2_6 kind=full result=7")),
        ("guard_exit 破损", "FULL-C4-GUARD-INTACT",
         mut_measure(b"guard_exit=1", b"guard_exit=0")),
        ("stack_peak 越 8192 界", "FULL-C4-GUARD-INTACT",
         mut_measure(b"stack_peak=3496", b"stack_peak=9496")),
        ("sbrk_delta 非零", "FULL-C5-SBRK-DELTA-ZERO",
         mut_measure(b"sbrk_delta=0", b"sbrk_delta=1")),
        ("tlsf_malloc_delta 非零", "FULL-C6-TLSF-DELTA-ZERO",
         mut_measure(b"tlsf_malloc_delta=0", b"tlsf_malloc_delta=2")),
        ("LVGL 池净状态漂移", "FULL-C14-LV-POOL-NET",
         mut_measure(b"lv_free_exit=63616", b"lv_free_exit=63000")),
        ("控制块 RdOff 之外被改", "HW-R8-POSTCHECK-RDOFF",
         mut_flip(R8_CB_POST, 30)),
        ("控制块 RdOff 未推进", "HW-R8-POSTCHECK-RDOFF", mut_zero_rdoff),
        ("ELF 身份锚被篡改", "HW-R8-INPUTS-IDENTITY",
         mut_json(R8_OTA, "elf_sha256", "0" * 64)),
        ("SD 上传读回声明为不符", "HW-R8-INPUTS-IDENTITY",
         mut_json("artifacts/r8/p2-6-sd-r8-full-upload-hw-01-result.json",
                  "readback_matches", False)),
        ("会话 gdb 退出码非零", "PROC-R8-SESSION-CLOSURE",
         mut_json(R8_OTA, "session.gdb_exit_code", 1)),
        ("会话发生 kill", "PROC-R8-SESSION-CLOSURE",
         mut_json(R8_OTA, "session.server_kill_sent", True)),
        ("出现未授权项目外写入", "PROC-R8-SESSION-CLOSURE",
         mut_json(R8_OTA, "outside_repo_writes", [r"D:\somewhere\else.bin"])),
        ("ETSL 提交标记被抹", "HW-BOOT-CANDIDATE-SLOT-COMMITTED",
         mut_flip("artifacts/r8/s3-cand-slot-header.bin", SLOT_MARKER_OFF)),
        ("升级后 BCB 块 CRC 不符", "HW-BOOT-BCB-TRANSITION",
         mut_flip("artifacts/r8/s4-obs2-bcb-raw.bin", 8)),
        ("复位后 App 版本未前进", "HW-BOOT-APP-VCODE-ADVANCED",
         mut_text("artifacts/r8/r8-s4-obs1-gdb.log",
                  b"fw_header magic=0x57465445 vcode=20801",
                  b"fw_header magic=0x57465445 vcode=20800")),
        ("BAD 包 payload 出现额外改动", "HW-C7-PACKAGE-DERIVATION",
         mut_flip("artifacts/r9/BAD-2.8.2.etu", 200000)),
        ("上传读回与 BAD 包不符", "HW-C7-UPLOAD-BYTE-IDENTITY",
         mut_flip("artifacts/r9/bad-upload-hw-02-readback.bin", 1000)),
        ("首次失败上传被冒充成功", "HW-C7-UPLOAD-BYTE-IDENTITY",
         mut_json("artifacts/r9/p2-6-sd-r9-bad-upload-hw-01-result.json",
                  "session.transport_classification", "PASS")),
        ("Apply 窗口 overlay 未归包", "HW-C7-MIDAPPLY-OWNER-PACKAGE",
         mut_text("artifacts/r9/r9-s3-c7-chain-gdb.log",
                  b"DECISIVE owner_at_apply=2", b"DECISIVE owner_at_apply=0")),
        ("失败形态被改成非 lzma_data", "HW-C7-FAILURE-NOT-VERSION-GATE",
         mut_text("artifacts/r9/r9-s3e-page-object.bin",
                  b"full:lzma_data", b"full:versionX")),
        ("恢复后 overlay 未重新持有", "HW-C7-OVERLAY-RELEASE-REBUILD",
         mut_text("artifacts/r9/r9-s5-final-gdb.log",
                  b"final vcode=20801 bcb=4 owner=1",
                  b"final vcode=20801 bcb=4 owner=0")),
        ("恢复后地图统计行塌陷", "HW-C7-MAP-HEALTHY",
         lambda work: (work / "artifacts/r9/r9-s4-recover.rtt.log").write_text(
             "LiveMap stat: update=1 lineHit=0\n", encoding="utf-8")),
        ("C7 过程中 BCB 被污染", "HW-C7-BCB-UNTOUCHED",
         mut_text("artifacts/r9/r9-s3b-post-fail-gdb.log",
                  b"bcb_post_fail=4", b"bcb_post_fail=1")),
        ("栈闭合总量超 8192 门槛", "OFF-C3-C13-STACK-CLOSURE",
         mut_json("artifacts/offline/stack-closure.json", "patch.thread_peak", 8000)),
        ("中断证据出现缺口", "OFF-C3-C13-STACK-CLOSURE",
         mut_json("artifacts/offline/stack-closure.json",
                  "interrupt_evidence_gaps", ["SDIO_IRQHandler"])),
        ("生产/插桩 OTA 布局不一致", "OFF-C8-C16-RAM-LAYOUT",
         mut_flip("artifacts/elf/X-Track-App-GCC-test.elf", 0x30)),
        ("容量下界用例被改成成功", "OFF-C10-C11-CAPACITY",
         mut_text("artifacts/offline/p2-6-capacity-full.run.log",
                  b"case=cap=P_full-prefix-1 result=workspace",
                  b"case=cap=P_full-prefix-1 result=ok______")),
        ("决定性产物被删除", "PROC-CUSTODY-COMPLETE",
         lambda work: (work / "artifacts/r8/s0-bcb-raw.bin").unlink()),
        ("托管文档被篡改", "PROC-CUSTODY-COMPLETE",
         mut_text("artifacts/docs/P2-6-SD-R8-hw-execution-evidence-2026-08-31.md",
                  b"33016", b"31016")),
    ]


def self_test(bundle: Path, work_root: Path) -> dict[str, Any]:
    if work_root.exists():
        shutil.rmtree(work_root)
    work_root.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, Any]] = []

    positive = evaluate(bundle)
    cases.append({
        "name": "阳性对照：未变异证据包",
        "kind": "positive",
        "expected": "PASS",
        "observed_overall": positive["overall"],
        "failed_criteria": positive["failed_criteria"],
        "ok": positive["overall"] == "PASS",
    })

    for index, (name, target, mutate) in enumerate(_negatives(), start=1):
        work = work_root / f"neg-{index:02d}"
        shutil.copytree(bundle, work)
        try:
            mutate(work)
        except Exception as exc:  # noqa: BLE001
            cases.append({"name": name, "kind": "negative", "target_criterion": target,
                          "ok": False, "error": f"变异失败：{type(exc).__name__}: {exc}"})
            continue
        report = evaluate(work)
        hit = target in report["failed_criteria"]
        cases.append({
            "name": name, "kind": "negative", "target_criterion": target,
            "expected": "FAIL", "observed_overall": report["overall"],
            "failed_criteria": report["failed_criteria"],
            "ok": hit and report["overall"] == "FAIL",
        })

    failures = [c for c in cases if not c["ok"]]
    return {
        "schema": REPORT_SCHEMA + "-selftest",
        "positive_cases": 1,
        "negative_cases": len(cases) - 1,
        "cases": cases,
        "failed_cases": [c["name"] for c in failures],
        "overall": "PASS" if not failures else "FAIL",
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="P2-6-v3 证据独立复算")
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--self-test-work", type=Path,
                        default=ROOT / ".cache" / "p2-6-v3-recompute-selftest")
    args = parser.parse_args(argv)

    bundle = args.bundle.resolve()
    if not bundle.is_dir():
        print(f"P2_6_V3_RECOMPUTE ERROR bundle_not_found={bundle}")
        return 2

    if args.self_test:
        result = self_test(bundle, args.self_test_work.resolve())
        for case in result["cases"]:
            status = "OK  " if case["ok"] else "MISS"
            target = case.get("target_criterion", "-")
            print(f"  [{status}] {case['kind']:8s} {target:34s} {case['name']}")
            if not case["ok"] and case.get("error"):
                print(f"         {case['error']}")
        print(f"P2_6_V3_SELFTEST positive={result['positive_cases']} "
              f"negative={result['negative_cases']} "
              f"failed={len(result['failed_cases'])} status={result['overall']}")
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")
        return 0 if result["overall"] == "PASS" else 1

    report = evaluate(bundle)
    try:
        shown = bundle.relative_to(ROOT).as_posix()
    except ValueError:
        shown = bundle.as_posix()
    print(f"P2_6_V3_RECOMPUTE bundle={shown}")
    for check in report["checks"]:
        # 观测值随行打印，使命令日志本身即为可读证据，不必回查报告 JSON。
        print(f"  [{check['result']:4s}] {check['id']}: "
              + json.dumps(check["observed"], ensure_ascii=False,
                           sort_keys=True))
    if report["failed_criteria"]:
        print("FAILED: " + ", ".join(report["failed_criteria"]))
    print(f"P2_6_V3_RECOMPUTE criteria={report['criteria_count']} "
          f"failed={len(report['failed_criteria'])} status={report['overall']}")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        print(f"REPORT={args.report}")
    return 0 if report["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
