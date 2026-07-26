#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_vectors.py — P0-3 golden vectors 打包器侧单测（stdlib unittest）

覆盖：
  1. toy 镜像：fw_header（0x400）全字段与 expected 一致；双零法 image_sha256 + header_crc32
     复算；file_sha256 == 整文件 SHA。image_sha256 一律双零语义（不混用整文件 sha）。
  2. .etu 外层头：逐字段（magic/header_len/flags/alg_id/key_id/aes_nonce/payload_len/
     payload_crc32/target_vcode/base_vcode/hw_rev/layout_id/min_boot_ver/base_sha8/
     header_crc32）与 expected 一致；payload_crc32 复算覆盖加密后 payload；header_crc32
     复算覆盖前 60B；package_sha256 == 整包 SHA。
  3. .etu.image_sha256 == candidate fw_header.image_sha256 双零值（与 toy-new.fw_header
     .image_sha256 同值）。
  4. 全量 / 差分 unpack 往返字节一致 + verify_fw_header。
  5. 差分内层头 40B 全字段（含 ph_lzma_props 5B / pad 3B）：实解析 == expected；ph_hcrc
     置零重算；ph_ocrc==crc32(old) / ph_ncrc==crc32(new)；base_sha8 == sha256(old)[:8]。
  6. seq 仲裁（§3.2）四场景 + 显式回绕数值。
  7. 契约 §8 样例 CRC 回归：0x14D0AA63 / 0xC0178C87。

契约依据：docs/ota-binary-contracts.md v1.0。
"""
import hashlib
import json
import lzma
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.normpath(os.path.join(HERE, "..", "..", "tools"))
sys.path.insert(0, TOOLS)
import etu_pack  # noqa: E402
import etu_unpack  # noqa: E402

FW_HEADER_OFFSET = etu_pack.FW_HEADER_OFFSET
FW_HEADER_SIZE = etu_pack.FW_HEADER_SIZE
PATCH_HEADER_SIZE = etu_pack.PATCH_HEADER_SIZE
VEC_DIR = HERE


def load(name):
    with open(os.path.join(VEC_DIR, name), "rb") as f:
        return f.read()


def load_expected():
    with open(os.path.join(VEC_DIR, "expected.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def int16(x):
    x &= 0xFFFF
    return x - 0x10000 if x & 0x8000 else x


def seq_arbiter_pick(a_seq, b_seq, a_valid, b_valid):
    """契约 §3.2：(int16)(a.seq - b.seq) > 0 → A 新；双合法相等取 A；单合法取有效者；
    双坏 → None（恢复模式）。"""
    if a_valid and b_valid:
        diff = int16((a_seq - b_seq) & 0xFFFF)
        if diff > 0: return "A"
        if diff < 0: return "B"
        return "A"
    if a_valid: return "A"
    if b_valid: return "B"
    return None


class GoldenVectorsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.exp = load_expected()
        cls.full_etu = load("toy-full.etu")
        cls.patch_etu = load("toy-patch.etu")
        cls.toy_old = load("toy-old.bin")
        cls.toy_new = load("toy-new.bin")
        cls.key = etu_pack.get_aes_key()

    # -- 1. toy 镜像 fw_header 字段 ---------------------------------------
    def test_toy_fw_header_fields(self):
        for name in ["toy-old.bin", "toy-new.bin"]:
            img = load(name)
            exp_v = self.exp["vectors"][name]
            exp_h = exp_v["fw_header"]
            self.assertEqual(len(img), exp_v["size"])
            self.assertEqual(hashlib.sha256(img).hexdigest(), exp_v["file_sha256"])
            hdr = img[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE]
            # 逐字段比对（expected 全字段）
            self.assertEqual(hdr[0:4].hex(), exp_h["magic"])
            self.assertEqual(struct.unpack_from("<I", hdr, 4)[0], exp_h["header_ver"])
            self.assertEqual(struct.unpack_from("<I", hdr, 8)[0], exp_h["version_code"])
            self.assertEqual(hdr[12:28].rstrip(b"\x00").decode("ascii", "replace"),
                             exp_h["version_name"])
            self.assertEqual(struct.unpack_from("<I", hdr, 28)[0], exp_h["build_ts"])
            self.assertEqual(struct.unpack_from("<I", hdr, 32)[0], exp_h["hw_rev"])
            self.assertEqual(struct.unpack_from("<I", hdr, 36)[0], exp_h["image_len"])
            self.assertEqual(hdr[40:72].hex(), exp_h["image_sha256"])
            self.assertEqual(hdr[72], exp_h["layout_id"])
            self.assertEqual(hdr[73], exp_h["min_boot_ver"])
            self.assertEqual(hdr[74:92].hex(), exp_h["pad"])
            stored_crc = struct.unpack_from("<I", hdr, 92)[0]
            self.assertEqual(struct.pack("<I", stored_crc).hex(), exp_h["header_crc32"])
            # image_sha256 双零法复算（§1.2）
            tmp = bytearray(img)
            tmp[FW_HEADER_OFFSET + 40:FW_HEADER_OFFSET + 72] = b"\x00" * 32
            tmp[FW_HEADER_OFFSET + 92:FW_HEADER_OFFSET + 96] = b"\x00\x00\x00\x00"
            self.assertEqual(hashlib.sha256(bytes(tmp)).digest(), hdr[40:72],
                             f"{name} image_sha256 双零法复算不一致")
            # header_crc32 复算覆盖前 92B
            self.assertEqual(etu_pack.crc32(bytes(hdr[:92])), stored_crc)
            # pad 必须全 0xFF（§1.1）
            self.assertEqual(hdr[74:92], b"\xFF" * 18)
            # image_len == 整镜像长度
            self.assertEqual(struct.unpack_from("<I", hdr, 36)[0], len(img))

    # -- 2/3. .etu 外层头逐字段 + image_sha256 一致性 ----------------------
    def _assert_outer_header(self, etu_bytes, exp_v):
        info = etu_unpack.parse_etu_header(etu_bytes)
        oh = exp_v["outer_header"]
        self.assertEqual(etu_bytes[0:4].hex(), oh["magic"])
        self.assertEqual(struct.unpack_from("<H", etu_bytes, 4)[0], oh["header_len"])
        self.assertEqual(struct.unpack("<H", bytes.fromhex(oh["flags"]))[0], info["flags"])
        self.assertEqual(info["alg_id"], oh["alg_id"])
        self.assertEqual(info["key_id"], oh["key_id"])
        self.assertEqual(info["nonce"].hex(), oh["aes_nonce"])
        self.assertEqual(info["payload_len"], oh["payload_len"])
        self.assertEqual(struct.pack("<I", info["payload_crc"]).hex(), oh["payload_crc32"])
        self.assertEqual(info["target_vcode"], oh["target_vcode"])
        self.assertEqual(info["base_vcode"], oh["base_vcode"])
        self.assertEqual(info["hw_rev"], oh["hw_rev"])
        self.assertEqual(info["layout_id"], oh["layout_id"])
        self.assertEqual(info["min_boot_ver"], oh["min_boot_ver"])
        self.assertEqual(info["base_sha8"].hex(), oh["base_sha8"])
        stored = struct.unpack_from("<I", etu_bytes, 60)[0]
        self.assertEqual(struct.pack("<I", stored).hex(), oh["header_crc32"])
        # 整包与整包 SHA
        self.assertEqual(len(etu_bytes), exp_v["size"])
        self.assertEqual(hashlib.sha256(etu_bytes).hexdigest(), exp_v["package_sha256"])
        # payload_crc32 复算覆盖加密后 payload
        payload = etu_bytes[64:64 + info["payload_len"]]
        self.assertEqual(etu_pack.crc32(payload), info["payload_crc"])
        # header_crc32 复算覆盖前 60B
        self.assertEqual(etu_pack.crc32(etu_bytes[:60]), stored)
        # header_len 必须 == 64（§2.1）
        self.assertEqual(oh["header_len"], 64)
        # magic == "ETU1"
        self.assertEqual(oh["magic"], "45545531")
        return info

    def test_full_outer_header(self):
        exp_v = self.exp["vectors"]["toy-full.etu"]
        info = self._assert_outer_header(self.full_etu, exp_v)
        # 全量 flags == 0x000B；base_vcode==0；base_sha8 全 0
        flags_int = struct.unpack("<H", bytes.fromhex(exp_v["outer_header"]["flags"]))[0]
        self.assertEqual(flags_int, 0x000B)
        self.assertEqual(info["base_vcode"], 0)
        self.assertEqual(info["base_sha8"], b"\x00" * 8)

    def test_patch_outer_header(self):
        exp_v = self.exp["vectors"]["toy-patch.etu"]
        info = self._assert_outer_header(self.patch_etu, exp_v)
        flags_int = struct.unpack("<H", bytes.fromhex(exp_v["outer_header"]["flags"]))[0]
        self.assertEqual(flags_int, 0x0007)  # 差分
        # base_sha8 == sha256(toy-old)[:8]（§2.1 / 打包器口径）
        self.assertEqual(info["base_sha8"], hashlib.sha256(self.toy_old).digest()[:8])

    def test_etu_image_sha256_consistency(self):
        """各 .etu 条目 image_sha256 == candidate fw_header.image_sha256 双零值
        == toy-new.fw_header.image_sha256（统一语义，杜绝前轮验收打回的字段歧义）。"""
        new_img_sha = self.exp["vectors"]["toy-new.bin"]["fw_header"]["image_sha256"]
        for etu_name in ["toy-full.etu", "toy-patch.etu"]:
            self.assertEqual(self.exp["vectors"][etu_name]["image_sha256"], new_img_sha,
                             f"{etu_name}.image_sha256 与 toy-new fw_header.image_sha256 不同源")

    # -- 4. unpack 往返 ---------------------------------------------------
    def test_full_roundtrip(self):
        info = etu_unpack.parse_etu_header(self.full_etu)
        plain = etu_unpack.aesctr(self.key, info["nonce"], info["payload"], encrypt=False)
        props = plain[:5]
        size = struct.unpack_from("<Q", plain, 5)[0]
        stream = plain[13:]
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW,
                                    filters=etu_unpack._props_to_filter(props))
        candidate = dec.decompress(stream, max_length=size)
        if len(candidate) != size:
            candidate += dec.decompress(b"", max_length=size - len(candidate))
        self.assertEqual(len(candidate), size)
        self.assertEqual(candidate, self.toy_new)
        etu_unpack.verify_fw_header(candidate, "full")

    def test_patch_roundtrip(self):
        info = etu_unpack.parse_etu_header(self.patch_etu)
        plain = etu_unpack.aesctr(self.key, info["nonce"], info["payload"], encrypt=False)
        inner = etu_unpack.parse_patch_header(plain[:PATCH_HEADER_SIZE])
        lzma_stream = plain[PATCH_HEADER_SIZE:]
        self.assertEqual(inner["ph_psize"], len(lzma_stream))
        self.assertEqual(inner["ph_osize"], len(self.toy_old))
        self.assertEqual(etu_pack.crc32(self.toy_old), inner["ph_ocrc"])
        bsdiff_stream = etu_unpack.lzma_decompress_stream(
            inner["props"], inner["ph_orig"], lzma_stream)
        candidate = etu_unpack.bspatch_apply(self.toy_old, inner["ph_nsize"], bsdiff_stream)
        self.assertEqual(candidate, self.toy_new)
        self.assertEqual(etu_pack.crc32(candidate), inner["ph_ncrc"])
        etu_unpack.verify_fw_header(candidate, "patch")

    # -- 5. 差分内层头 40B 全字段 -----------------------------------------
    def test_patch_inner_full_fields(self):
        info = etu_unpack.parse_etu_header(self.patch_etu)
        plain = etu_unpack.aesctr(self.key, info["nonce"], info["payload"], encrypt=False)
        head40 = plain[:PATCH_HEADER_SIZE]
        inner = etu_unpack.parse_patch_header(head40)
        ip = self.exp["vectors"]["toy-patch.etu"]["patch_inner"]
        # 逐字段比对
        self.assertEqual(struct.pack(">I", inner["ph_hcrc"]).hex(), ip["ph_hcrc"])
        self.assertEqual(inner["ph_psize"], ip["ph_psize"])
        self.assertEqual(inner["ph_osize"], ip["ph_osize"])
        self.assertEqual(inner["ph_nsize"], ip["ph_nsize"])
        self.assertEqual(struct.pack(">I", inner["ph_ocrc"]).hex(), ip["ph_ocrc"])
        self.assertEqual(struct.pack(">I", inner["ph_ncrc"]).hex(), ip["ph_ncrc"])
        self.assertEqual(inner["props"].hex(), ip["ph_lzma_props"])     # 5B
        self.assertEqual(head40[29:32].hex(), ip["pad"])                 # 3B 显式 0x000000
        self.assertEqual(inner["ph_orig"], ip["ph_original_size"])
        # ph_hcrc 置零重算（§2.3 hcrc off0..3 全零算 40B 全头）
        tmp = bytearray(head40)
        struct.pack_into(">I", tmp, 0, 0)
        self.assertEqual(etu_pack.crc32(bytes(tmp)), inner["ph_hcrc"])
        # pad 必须 0x000000
        self.assertEqual(head40[29:32], b"\x00\x00\x00")
        # ph_lzma_props 必须 5B
        self.assertEqual(len(inner["props"]), 5)
        # ph_ocrc == crc32(old) / ph_ncrc == crc32(new)（§2.3 二重兜底）
        self.assertEqual(inner["ph_ocrc"], etu_pack.crc32(self.toy_old))
        self.assertEqual(inner["ph_ncrc"], etu_pack.crc32(self.toy_new))
        # ph_original_size == bsdiff 解压流长度（与 ph_psize 区别：psize=压缩流，orig_size=解压 bsdiff 流）
        bsdiff_stream = etu_unpack.lzma_decompress_stream(
            inner["props"], inner["ph_orig"], plain[PATCH_HEADER_SIZE:])
        self.assertEqual(len(bsdiff_stream), inner["ph_orig"])

    # -- 6. seq 仲裁（§3.2） ---------------------------------------------
    def test_seq_arbiter(self):
        for c in self.exp["seq_arbiter_cases"]:
            got = seq_arbiter_pick(c["a_seq"], c["b_seq"],
                                   c.get("a_valid", True), c.get("b_valid", True))
            self.assertEqual(got, c["expect"],
                             f"seq case {c['name']}: got {got} expect {c['expect']}")
        # 显式回绕数值
        self.assertEqual(seq_arbiter_pick(65530, 5, True, True), "B")
        self.assertEqual(seq_arbiter_pick(5, 65530, True, True), "A")
        self.assertEqual(seq_arbiter_pick(7, 7, True, True), "A")
        self.assertEqual(seq_arbiter_pick(9, 8, False, True), "B")
        self.assertEqual(seq_arbiter_pick(9, 8, True, False), "A")
        self.assertIsNone(seq_arbiter_pick(9, 8, False, False))

    # -- 7. 契约 §8 样例 CRC 回归 ----------------------------------------
    def test_contract_samples_regression(self):
        # §8.2 全量外层头（60B）→ header_crc32 = 0x14D0AA63
        sample = bytes.fromhex(
            "45545531"                                  # 4 magic
            "4000"                                      # 2 header_len
            "0b00"                                      # 2 flags
            "01000000"                                  # 4 alg_id
            "01000000"                                  # 4 key_id
            "00000000000000000000000000000000"          # 16 nonce(全0)
            "64000000"                                  # 4 payload_len
            "11111111"                                  # 4 payload_crc32
            "40510000"                                  # 4 target_vcode
            "00000000"                                  # 4 base_vcode
            "0100"                                      # 2 hw_rev
            "01"                                        # 1 layout_id
            "01"                                        # 1 min_boot_ver
            "0000000000000000"                          # 8 base_sha8
        )
        self.assertEqual(len(sample), 60)
        crc = etu_pack.crc32(sample)
        self.assertEqual(crc, 0x14D0AA63, f"§8.2 全量外层头 CRC got 0x{crc:08X}")
        # §8.5 ETRJ（40B）→ hdr_crc32 = 0xC0178C87
        etrj = bytes.fromhex("4554524a" + "00" * 32 + "64000000")
        self.assertEqual(len(etrj), 40)
        ecrc = etu_pack.crc32(etrj)
        self.assertEqual(ecrc, 0xC0178C87, f"§8.5 ETRJ CRC got 0x{ecrc:08X}")
        reg = self.exp["contract_samples_regression"]
        self.assertEqual(f"{crc:08x}", reg["etw_full_outer_header_crc32_u32"])
        self.assertEqual(struct.pack("<I", crc).hex(), reg["etw_full_outer_header_crc32_be_bytes"])
        self.assertEqual(f"{ecrc:08x}", reg["etrj_hdr_crc32_u32"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
