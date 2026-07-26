#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_vectors.py — P0-3 golden vectors 生成器

复用 P0-2 已验收的 `tools/etu_pack.py`（finalize / pack-full / pack-patch）产出
tests/ota-vectors/ 下的 golden vectors：
  - toy-old.bin      4KB，旧版基版（2.7.0 / vcode 20700）
  - toy-new.bin      4KB，目标版（2.8.0 / vcode 20800），在 old 基础上做 ~200 处 +1
  - toy-full.etu     全量包（flags=0x000B）
  - toy-patch.etu    差分包（flags=0x0007）
  - expected.json    SHA + 关键字段（字段名与契约文档术语对齐，供 P2/P3 复用）

不做升级合法性判定（属 MCU/App 侧）；不 commit/push（OTA 规约 §5）。
契约依据：docs/ota-binary-contracts.md v1.0。
"""
import datetime
import hashlib
import json
import os
import struct
import sys

# 复用 P0-2 打包器（保持单一真实源，golden vectors 不重写打包逻辑）
HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, TOOLS)
import etu_pack  # noqa: E402

# ---- 常量（与契约一致；引用 etu_pack 内常量，避免分散定义） -------------------
FW_HEADER_OFFSET = etu_pack.FW_HEADER_OFFSET
FW_HEADER_SIZE = etu_pack.FW_HEADER_SIZE
PATCH_HEADER_SIZE = etu_pack.PATCH_HEADER_SIZE

VENV_TOY_SIZE = 4096
VT_REGION = 0x400   # 向量表哨兵区，finalize 不得覆盖（P0-2 §6.3 夹具同风格）
HDR_PLACEHOLDER = 0xFF  # finalize 前 0x400..0x45F 占位字节

OLD_VER_NAME = "2.7.0"
NEW_VER_NAME = "2.8.0"
OLD_BUILD_TS = 1720000000
NEW_BUILD_TS = 1721000000


def sha256(buf: bytes) -> bytes:
    return hashlib.sha256(buf).digest()


def crc32(buf: bytes) -> int:
    return etu_pack.crc32(buf)


def make_toy_image(base_byte: int, *, with_diff: bool, seed: int) -> bytes:
    """构造 4KB toy 镜像：0..0x3FF 向量表哨兵区，0x400..0x45F fw_header 占位（0xFF），
    0x460..0xFFF 本体填充。with_diff=True 时在 0x460 起做若干 +1 改动，bsdiff 产真实 diff。"""
    buf = bytearray(VENV_TOY_SIZE)
    # 0..0x3FF：向量表哨兵区（与 P0-2 验收夹具同风格，确保 finalize 不覆盖）
    for i in range(VT_REGION):
        buf[i] = (0xDE ^ (i & 0xFF)) & 0xFF  # 仅为占位伪向量表
    # 0x400..0x45F：fw_header 占位（finalize 回填，此处保持 0xFF）
    for i in range(VT_REGION, VT_REGION + FW_HEADER_SIZE):
        buf[i] = HDR_PLACEHOLDER
    # 0x460..0xFFF：本体
    body_off = VT_REGION + FW_HEADER_SIZE
    for i in range(body_off, VENV_TOY_SIZE):
        buf[i] = (base_byte + ((i - body_off) & 0xFF)) & 0xFF
    if with_diff:
        # 在本体偏移 0x460 起每 ~20B 做一次 +1，约 180 处改动，bsdiff 出真实 LZMA 流
        for k, off in enumerate(range(body_off, VENV_TOY_SIZE, 20)):
            buf[off] = (buf[off] + 1 + (k & 0x03)) & 0xFF
    return bytes(buf)


def finalize_image(image_path: str, out_path: str, ver_name: str, build_ts: int) -> bytes:
    """调 etu_pack.build_fw_header 在 0x400 偏移回填 fw_header，写回 out_path。"""
    with open(image_path, "rb") as f:
        image = f.read()
    hdr = etu_pack.build_fw_header(image, ver_name, build_ts)
    out = bytearray(image)
    out[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE] = hdr
    with open(out_path, "wb") as f:
        f.write(out)
    return bytes(out)


def pack_full(app_path: str, out_path: str, ver_name: str) -> bytes:
    import subprocess
    rc = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "etu_pack.py"),
         "pack-full", "--app", app_path, "--out", out_path, "--ver-name", ver_name],
        capture_output=True, text=True)
    if rc.returncode != 0:
        raise RuntimeError(f"pack-full 失败: {rc.stderr}")
    with open(out_path, "rb") as f:
        return f.read()


def pack_patch(old_path: str, new_path: str, out_path: str,
               ver_name: str, base_ver_name: str) -> bytes:
    import subprocess
    bsdiff_exe = os.path.normpath(os.path.join(
        HERE, "..", "..", "bsdiff_lzma_AES128-main", "bsdiff", "build", "bin", "bsdiff.exe"))
    rc = subprocess.run(
        [sys.executable, os.path.join(TOOLS, "etu_pack.py"),
         "pack-patch", "--old", old_path, "--new", new_path, "--out", out_path,
         "--ver-name", ver_name, "--base-ver-name", base_ver_name,
         "--bsdiff-exe", bsdiff_exe],
        capture_output=True, text=True)
    if rc.returncode != 0:
        raise RuntimeError(f"pack-patch 失败: {rc.stderr}")
    with open(out_path, "rb") as f:
        return f.read()


def parse_etu_header_dict(etu_bytes: bytes) -> dict:
    """用 etu_unpack.parse_etu_header 解析外层头，返回协议字段 dict。"""
    sys.path.insert(0, TOOLS)
    import etu_unpack  # noqa: E402
    info = etu_unpack.parse_etu_header(etu_bytes)
    return info


def parse_patch_inner(plaintext_head40: bytes) -> dict:
    """解析 40B 规范化内层头（复用 etu_unpack.parse_patch_header）。"""
    sys.path.insert(0, TOOLS)
    import etu_unpack  # noqa: E402
    return etu_unpack.parse_patch_header(plaintext_head40)


def fw_header_fields(image: bytes) -> dict:
    """从镜像 0x400 处读 fw_header 全字段（§1.1，仅读 stored 值，不重算）。"""
    hdr = image[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE]
    return {
        "magic": hdr[0:4].hex(),                              # off0  "ETFW"
        "header_ver": struct.unpack_from("<I", hdr, 4)[0],    # off4
        "version_code": struct.unpack_from("<I", hdr, 8)[0],  # off8
        "version_name": hdr[12:28].rstrip(b"\x00").decode("ascii", "replace"),  # off12 ASCIIZ
        "build_ts": struct.unpack_from("<I", hdr, 28)[0],     # off28
        "hw_rev": struct.unpack_from("<I", hdr, 32)[0],       # off32
        "image_len": struct.unpack_from("<I", hdr, 36)[0],    # off36
        "image_sha256": hdr[40:72].hex(),                     # off40 双零法产物
        "layout_id": hdr[72],                                 # off72
        "min_boot_ver": hdr[73],                              # off73
        "pad": hdr[74:92].hex(),                              # off74 18B 0xFF
        "header_crc32": struct.unpack_from("<I", hdr, 92)[0], # off92
    }


def main():
    out_dir = HERE
    old_raw = make_toy_image(0x10, with_diff=False, seed=1)
    new_raw = make_toy_image(0x10, with_diff=True, seed=2)

    old_path = os.path.join(out_dir, "toy-old.bin")
    new_path = os.path.join(out_dir, "toy-new.bin")
    full_path = os.path.join(out_dir, "toy-full.etu")
    patch_path = os.path.join(out_dir, "toy-patch.etu")
    expected_path = os.path.join(out_dir, "expected.json")

    # 写未 finalize 占位镜像 → finalize 回填 0x400 fw_header
    with open(old_path, "wb") as f: f.write(old_raw)
    with open(new_path, "wb") as f: f.write(new_raw)
    old_fin = finalize_image(old_path, old_path, OLD_VER_NAME, OLD_BUILD_TS)
    new_fin = finalize_image(new_path, new_path, NEW_VER_NAME, NEW_BUILD_TS)

    full_etu = pack_full(new_path, full_path, NEW_VER_NAME)
    patch_etu = pack_patch(old_path, new_path, patch_path,
                           NEW_VER_NAME, OLD_VER_NAME)

    # ---- 解析与字段提取（用 etu_unpack 作单一真实源） -------------------------
    full_info = parse_etu_header_dict(full_etu)
    patch_info = parse_etu_header_dict(patch_etu)

    # 差分内层头：从 payload 解密 → 取前 40B
    sys.path.insert(0, TOOLS)
    import etu_unpack  # noqa: E402
    key = etu_pack.get_aes_key()
    patch_plain = etu_unpack.aesctr(key, patch_info["nonce"], patch_info["payload"], encrypt=False)
    inner = parse_patch_inner(patch_plain[:PATCH_HEADER_SIZE])

    new_fields = fw_header_fields(new_fin)

    def fw_header_entry(img: bytes) -> dict:
        """toy 镜像的 expected 条目：契约 §1.1/§1.2 fw_header 全字段。
        关键点：image_sha256 = 双零法 stored 值（§1.2，与 .etu 同名条目语义一致）；
        file_sha256 = 整文件 SHA-256（与 fw_header.image_sha256 双零法不同，单列以避免前轮验收打回的字段歧义）。"""
        f = fw_header_fields(img)
        return {
            "size": len(img),
            "file_sha256": sha256(img).hex(),
            "fw_header": {
                "magic": f["magic"],
                "header_ver": f["header_ver"],
                "version_code": f["version_code"],
                "version_name": f["version_name"],
                "build_ts": f["build_ts"],
                "hw_rev": f["hw_rev"],
                "image_len": f["image_len"],
                "image_sha256": f["image_sha256"],
                "layout_id": f["layout_id"],
                "min_boot_ver": f["min_boot_ver"],
                "pad": f["pad"],
                "header_crc32": struct.pack("<I", f["header_crc32"]).hex(),
            },
        }

    def etu_common(info: dict, etu_bytes: bytes) -> dict:
        """契约 §2.1 64B 外层头逐字段（与契约文档术语对号）。
        image_sha256 = candidate（toy-new）fw_header.image_sha256 双零法产物（§1.2），
        与 .etu 外层头无关，但作为包内候选镜像的身份放条目内便于跨端比对。"""
        return {
            "size": len(etu_bytes),
            "package_sha256": sha256(etu_bytes).hex(),                 # §4.2.1 整包 SHA
            "outer_header": {
                "magic": etu_bytes[0:4].hex(),                         # §2.1 off0  "ETU1"
                "header_len": struct.unpack_from("<H", etu_bytes, 4)[0], # §2.1 off4
                "flags": struct.pack("<H", info["flags"]).hex(),        # §2.1 off6
                "alg_id": info["alg_id"],                              # §2.1 off8
                "key_id": info["key_id"],                              # §2.1 off12
                "aes_nonce": info["nonce"].hex(),                      # §2.1 off16
                "payload_len": info["payload_len"],                    # §2.1 off32
                "payload_crc32": struct.pack("<I", info["payload_crc"]).hex(),  # §2.1 off36
                "target_vcode": info["target_vcode"],                  # §2.1 off40
                "base_vcode": info["base_vcode"],                      # §2.1 off44
                "hw_rev": info["hw_rev"],                              # §2.1 off48
                "layout_id": info["layout_id"],                        # §2.1 off50
                "min_boot_ver": info["min_boot_ver"],                  # §2.1 off51
                "base_sha8": info["base_sha8"].hex(),                  # §2.1 off52
                "header_crc32": struct.pack("<I", crc32(etu_bytes[:60])).hex(),  # §2.1 off60
            },
            "image_sha256": new_fields["image_sha256"],  # = candidate fw_header.image_sha256 双零值
        }

    full_entry = etu_common(full_info, full_etu)
    full_entry["kind"] = "full"
    patch_entry = etu_common(patch_info, patch_etu)
    patch_entry["kind"] = "patch"
    # §2.3 规范化 40B 内层头全字段（含 ph_lzma_props 5B / pad 3B，前轮验收打回要求补齐）
    patch_entry["patch_inner"] = {
        "ph_hcrc": struct.pack(">I", inner["ph_hcrc"]).hex(),          # off0  BE
        "ph_psize": inner["ph_psize"],                                 # off4  BE
        "ph_osize": inner["ph_osize"],                                 # off8  LE
        "ph_nsize": inner["ph_nsize"],                                 # off12 LE
        "ph_ocrc": struct.pack(">I", inner["ph_ocrc"]).hex(),          # off16 BE
        "ph_ncrc": struct.pack(">I", inner["ph_ncrc"]).hex(),          # off20 BE
        "ph_lzma_props": inner["props"].hex(),                         # off24 5B
        "pad": patch_plain[29:32].hex(),                               # off29 3B 显式 0x000000
        "ph_original_size": inner["ph_orig"],                          # off32 u64 LE
    }

    old_fields = fw_header_fields(old_fin)
    old_file_sha8 = sha256(old_fin)[:8].hex()
    if patch_entry["outer_header"]["base_sha8"] != old_file_sha8:
        raise RuntimeError(
            f"base_sha8 不一致: etu={patch_entry['outer_header']['base_sha8']} old_file_sha8={old_file_sha8}")

    vectors = {
        "toy-old.bin": fw_header_entry(old_fin),
        "toy-new.bin": fw_header_entry(new_fin),
        "toy-full.etu": full_entry,
        "toy-patch.etu": patch_entry,
    }

    # ---- seq 仲裁场景（契约 §3.2 / §8 验收） --------------------------------
    seq_cases = [
        {"name": "A_newer", "a_seq": 5, "b_seq": 3, "a_valid": True, "b_valid": True, "expect": "A"},
        {"name": "B_wrap_newer", "a_seq": 65530, "b_seq": 5, "a_valid": True, "b_valid": True, "expect": "B"},
        {"name": "equal_both_valid", "a_seq": 7, "b_seq": 7, "a_valid": True, "b_valid": True, "expect": "A"},
        {"name": "only_B_valid", "a_seq": 9, "b_seq": 8, "a_valid": False, "b_valid": True, "expect": "B"},
    ]

    expected = {
        "contract_version": "ota-binary-contracts v1.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "aes_key_source": os.environ.get("OTA_AES_KEY",
                                         "vendor default 2b7e1516...(dev only, contract §0.6)"),
        "fw_header_offset": FW_HEADER_OFFSET,
        "fw_header_size": FW_HEADER_SIZE,
        "toys": {
            "toy-old.bin": {"version_name": OLD_VER_NAME, "version_code": vectors["toy-old.bin"]["fw_header"]["version_code"]},
            "toy-new.bin": {"version_name": NEW_VER_NAME, "version_code": vectors["toy-new.bin"]["fw_header"]["version_code"]},
        },
        "vectors": vectors,
        "seq_arbiter_cases": seq_cases,
        "contract_samples_regression": {
            "etw_full_outer_header_crc32_be_bytes": "63aad014",
            "etw_full_outer_header_crc32_u32": "14d0aa63",
            "etrj_hdr_crc32_u32": "c0178c87"
        }
    }

    with open(expected_path, "w", encoding="utf-8") as f:
        json.dump(expected, f, ensure_ascii=False, indent=2)

    print(f"gen_vectors OK")
    print(f"  toy-old.bin  {len(old_fin)}B  vcode={old_fields['version_code']}  file_sha256={vectors['toy-old.bin']['file_sha256'][:16]}  img_sha256={vectors['toy-old.bin']['fw_header']['image_sha256'][:16]}")
    print(f"  toy-new.bin  {len(new_fin)}B  vcode={new_fields['version_code']}  file_sha256={vectors['toy-new.bin']['file_sha256'][:16]}  img_sha256={vectors['toy-new.bin']['fw_header']['image_sha256'][:16]}")
    print(f"  toy-full.etu {len(full_etu)}B  hdr_crc={full_entry['outer_header']['header_crc32']}  pkg_sha={full_entry['package_sha256'][:16]}")
    print(f"  toy-patch.etu {len(patch_etu)}B  hdr_crc={patch_entry['outer_header']['header_crc32']}  base_sha8={patch_entry['outer_header']['base_sha8']}")
    print(f"  expected.json -> {expected_path}")
    print(f"  seq_arbiter_cases: {len(seq_cases)}")


if __name__ == "__main__":
    main()
