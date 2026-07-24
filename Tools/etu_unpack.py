#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etu_unpack.py — OTA .etu 逆向解析 + 校验工具（P0-2，供三方比对）

功能：读取 .etu → 校验外层头 magic/header_crc32 → AES-CTR 解密 payload →
  - 全量：LZMA-Alone 解压 → candidate.bin；校验 fw_header.header_crc32 + image_sha256 双零法。
  - 差分：解析 40B 规范化内层头（校验 ph_hcrc/be）→ 用 --old 调用 bspatch 还原 → candidate.bin；
         校验 ph_ncrc 对 candidate。
不做升级合法性判定（hw_rev/layout_id/vcode 降级等，属 MCU/App 侧）。
仅做"逆向解析+校验"，与 etu_pack.py 形成 pack→unpack 往返字节一致闭环。

参考契约锚点：§2.1 外层头、§2.2 payload 形态、§2.3 内层头、§1.2 fw_header、§0.2/§0.5。
"""
import argparse
import hashlib
import lzma
import os
import struct
import subprocess
import sys
import tempfile
import zlib

try:
    from Crypto.Cipher import AES
    from Crypto.Util import Counter
except ImportError:
    sys.stderr.write("缺少 pycryptodome：pip install pycryptodome\n")
    raise

# 与 etu_pack.py 共享常量（保持一致；改动走契约变更登记）
FW_HEADER_OFFSET = 0x400   # 契约 §0.4：fw_header 落镜像内 0x400，前 0x400 为向量表
FW_HEADER_SIZE = 96
FW_HEADER_CRC_OFF = 92
FW_HEADER_SHA_OFF = 40
FW_HEADER_SHA_LEN = 32
FW_HEADER_IMAGE_LEN_OFF = 36

ETU_MAGIC = b"ETU1"
ETU_HEADER_LEN = 64
ETU_HEADER_CRC_OFF = 60

PATCH_HCRC_OFF = 0
PATCH_PSIZE_OFF = 4
PATCH_OSIZE_OFF = 8
PATCH_NSIZE_OFF = 12
PATCH_OCRC_OFF = 16
PATCH_NCRC_OFF = 20
PATCH_PROPS_OFF = 24
PATCH_PAD_OFF = 29
PATCH_ORIG_OFF = 32
PATCH_HEADER_SIZE = 40

FLAG_AES = 0x0001
FLAG_LZMA = 0x0002
FLAG_DIFF = 0x0004
FLAG_FULL = 0x0008

DEFAULT_KEY_HEX = "2b7e151628aed2a6abf7158809cf4f3c"


def crc32(buf: bytes) -> int:
    return zlib.crc32(buf) & 0xFFFFFFFF


def sha256(buf: bytes) -> bytes:
    return hashlib.sha256(buf).digest()


def get_aes_key() -> bytes:
    hexstr = os.environ.get("OTA_AES_KEY")
    if hexstr:
        if len(hexstr) != 32:
            raise ValueError("OTA_AES_KEY 必须 32 hex 字符（16B）")
        return bytes.fromhex(hexstr)
    sys.stderr.write("[warn] OTA_AES_KEY 未设，使用 vendor 示例 key（仅开发）\n")
    return bytes.fromhex(DEFAULT_KEY_HEX)


def aesctr(key, nonce, data, encrypt):
    ctr = Counter.new(128, initial_value=int.from_bytes(nonce, "big"))
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return cipher.encrypt(data) if encrypt else cipher.decrypt(data)


def parse_etu_header(etu: bytes):
    if len(etu) < ETU_HEADER_LEN:
        raise ValueError(f".etu 短于 64B：{len(etu)}")
    hdr = etu[:ETU_HEADER_LEN]
    if hdr[0:4] != ETU_MAGIC:
        raise ValueError(f"外层头 magic 非 ETU1：{hdr[0:4].hex()}")
    header_len = struct.unpack_from("<H", hdr, 4)[0]
    if header_len != ETU_HEADER_LEN:
        raise ValueError(f"header_len 非 64：{header_len}")
    stored_crc = struct.unpack_from("<I", hdr, ETU_HEADER_CRC_OFF)[0]
    calc = crc32(hdr[:ETU_HEADER_CRC_OFF])
    if stored_crc != calc:
        raise ValueError(f"外层头 header_crc32 不匹配：stored={stored_crc:08x} calc={calc:08x}")
    flags = struct.unpack_from("<H", hdr, 6)[0]
    alg_id = struct.unpack_from("<I", hdr, 8)[0]
    key_id = struct.unpack_from("<I", hdr, 12)[0]
    nonce = hdr[16:32]
    payload_len = struct.unpack_from("<I", hdr, 32)[0]
    payload_crc = struct.unpack_from("<I", hdr, 36)[0]
    target_vcode = struct.unpack_from("<I", hdr, 40)[0]
    base_vcode = struct.unpack_from("<I", hdr, 44)[0]
    hw_rev = struct.unpack_from("<H", hdr, 48)[0]
    layout_id = hdr[50]
    min_boot_ver = hdr[51]
    base_sha8 = hdr[52:60]
    payload = etu[ETU_HEADER_LEN:ETU_HEADER_LEN + payload_len]
    if len(payload) != payload_len:
        raise ValueError(f"payload 实长 {len(payload)} != 声明 {payload_len}")
    if crc32(payload) != payload_crc:
        raise ValueError("payload_crc32 不匹配（密文损坏）")
    return {
        "flags": flags, "alg_id": alg_id, "key_id": key_id, "nonce": nonce,
        "payload_len": payload_len, "payload_crc": payload_crc,
        "target_vcode": target_vcode, "base_vcode": base_vcode,
        "hw_rev": hw_rev, "layout_id": layout_id, "min_boot_ver": min_boot_ver,
        "base_sha8": base_sha8, "payload": payload,
    }


def parse_patch_header(buf40: bytes):
    if len(buf40) != PATCH_HEADER_SIZE:
        raise ValueError(f"内层头非 40B：{len(buf40)}")
    ph_hcrc_be = struct.unpack_from(">I", buf40, PATCH_HCRC_OFF)[0]
    ph_psize_be = struct.unpack_from(">I", buf40, PATCH_PSIZE_OFF)[0]
    ph_osize = struct.unpack_from("<I", buf40, PATCH_OSIZE_OFF)[0]
    ph_nsize = struct.unpack_from("<I", buf40, PATCH_NSIZE_OFF)[0]
    ph_ocrc_be = struct.unpack_from(">I", buf40, PATCH_OCRC_OFF)[0]
    ph_ncrc_be = struct.unpack_from(">I", buf40, PATCH_NCRC_OFF)[0]
    props = buf40[PATCH_PROPS_OFF:PATCH_PROPS_OFF + 5]
    pad = buf40[PATCH_PAD_OFF:PATCH_PAD_OFF + 3]
    ph_orig = struct.unpack_from("<Q", buf40, PATCH_ORIG_OFF)[0]
    # ph_hcrc 校验：本字段置零算 40B 全头
    tmp = bytearray(buf40)
    struct.pack_into(">I", tmp, PATCH_HCRC_OFF, 0)
    calc = crc32(bytes(tmp))
    if ph_hcrc_be != calc:
        raise ValueError(f"内层头 ph_hcrc 不匹配：stored={ph_hcrc_be:08x} calc={calc:08x}")
    if pad != b"\x00\x00\x00":
        raise ValueError(f"内层头 pad 非 0x000000：{pad.hex()}")
    return {
        "ph_hcrc": ph_hcrc_be, "ph_psize": ph_psize_be, "ph_osize": ph_osize,
        "ph_nsize": ph_nsize, "ph_ocrc": ph_ocrc_be, "ph_ncrc": ph_ncrc_be,
        "props": props, "ph_orig": ph_orig,
    }


def verify_fw_header(image: bytes, label: str = "candidate"):
    """校验 candidate 的 fw_header.header_crc32 + image_sha256 双零法（§1.2）。
    fw_header 落镜像内 FW_HEADER_OFFSET(0x400) 处（契约 §0.4/§1），前 0x400 为向量表区；
    头内 off 相对头首（镜像 0x400+off）；SHA 双零法把镜像内 0x400+40..71 与 0x400+92..95 置零。"""
    if len(image) < FW_HEADER_OFFSET + FW_HEADER_SIZE:
        raise ValueError(f"[{label}] 短于 0x400+96")
    hdr = image[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE]
    if hdr[0:4] != b"ETFW":
        raise ValueError(f"[{label}] fw_header magic 非 ETFW (got {hdr[0:4].hex()})")
    stored_crc = struct.unpack_from("<I", hdr, FW_HEADER_CRC_OFF)[0]
    calc = crc32(hdr[:92])
    if stored_crc != calc:
        raise ValueError(f"[{label}] header_crc32 不匹配：stored={stored_crc:08x} calc={calc:08x}")
    stored_sha = hdr[FW_HEADER_SHA_OFF:FW_HEADER_SHA_OFF + FW_HEADER_SHA_LEN]
    tmp = bytearray(image)
    sha_abs = FW_HEADER_OFFSET + FW_HEADER_SHA_OFF
    crc_abs = FW_HEADER_OFFSET + FW_HEADER_CRC_OFF
    tmp[sha_abs:sha_abs + FW_HEADER_SHA_LEN] = b"\x00" * 32
    tmp[crc_abs:crc_abs + 4] = b"\x00\x00\x00\x00"
    calc_sha = sha256(bytes(tmp))
    if stored_sha != calc_sha:
        raise ValueError(f"[{label}] image_sha256 双零法不匹配")
    image_len = struct.unpack_from("<I", hdr, FW_HEADER_IMAGE_LEN_OFF)[0]
    if image_len != len(image):
        raise ValueError(f"[{label}] image_len={image_len} != 实际 {len(image)}")


def run_bspatch(bspatch_exe: str, old: bytes, patch_stream: bytes,
                props: bytes, ph_orig: int, new_size: int) -> bytes:
    """bspatch.exe 期望 40B 原生头 + LZMA 流；本工具构造一个原生头喂给它。
    native 头布局 = hcrc(BE)/psize(BE)/osize(LE)/nsize(LE)/ocrc(BE)/ncrc(BE)/props5/pad3/orig8。
    hcrc 由 bspatch 自己校验，这里按 native 形式重算（hcrc 置零算 40B 全头，BE 存储）。"""
    hdr = bytearray(PATCH_HEADER_SIZE)
    struct.pack_into(">I", hdr, PATCH_HCRC_OFF, 0)
    struct.pack_into(">I", hdr, PATCH_PSIZE_OFF, len(patch_stream))
    struct.pack_into("<I", hdr, PATCH_OSIZE_OFF, len(old))
    struct.pack_into("<I", hdr, PATCH_NSIZE_OFF, new_size)
    struct.pack_into(">I", hdr, PATCH_OCRC_OFF, crc32(old))
    struct.pack_into(">I", hdr, PATCH_NCRC_OFF, 0)  # bspatch 也会算 candidate crc 比对，先 0；它其实用 header 内值比对
    hdr[PATCH_PROPS_OFF:PATCH_PROPS_OFF + 5] = props
    hdr[PATCH_PAD_OFF:PATCH_PAD_OFF + 3] = b"\x00\x00\x00"
    struct.pack_into("<Q", hdr, PATCH_ORIG_OFF, ph_orig)
    hcrc = crc32(bytes(hdr))
    struct.pack_into(">I", hdr, PATCH_HCRC_OFF, hcrc)
    # 注意：bspatch 校验 ph_ncrc 对 candidate；但 bspatch 用 header 内的 ncrc 比对它自己算的 candidate crc。
    # 这里我们尚未知道 candidate crc（就是要产生 candidate）。需先放真实 ncrc。但 native 流程 bspatch
    # 自己算 candidate crc 并与 header.ph_ncrc 比对——所以 header 必须含真实 ph_ncrc。
    # 我们没有真实 ph_ncrc（规范化头里是 BE 存的，bspatch 用 BigtoLittle32 还原后比对）。
    # 解决：本工具改用 Python 自实现 bspatch 解析（不依赖 bspatch.exe），见 bspatch_py。
    raise RuntimeError("use bspatch_py instead")  # 不应走到


def offtin(buf: bytes) -> int:
    y = buf[7] & 0x7F
    for i in range(6, -1, -1):
        y = y * 256 + buf[i]
    return -y if (buf[7] & 0x80) else y


def bspatch_py(old: bytes, new_size: int,
              lzma_dec: lzma.LZMADecompressor) -> bytes:
    """纯 Python bspatch：读 LZMA 解压后的控制/差分/额外流，合成 new。
    bsdiff 流结构：循环 {ctrl[3] i64 LE(8B each); diff[ctrl[0]]; extra[ctrl[1]]}。"""
    new = bytearray(new_size)
    oldpos = 0
    newpos = 0
    # 流式从 lzma 解压器读
    feed_buf = b""

    def stream_read(n: int) -> bytes:
        nonlocal feed_buf
        while len(feed_buf) < n:
            chunk = lzma_dec.decompress(b"", max_length=max(n - len(feed_buf), 4096))
            if not chunk:
                break
            feed_buf += chunk
        if len(feed_buf) < n:
            raise ValueError(f"LZMA 流不足：需 {n} 仅 {len(feed_buf)}")
        out = feed_buf[:n]
        feed_buf = feed_buf[n:]
        return out

    while newpos < new_size:
        ctrl = [offtin(stream_read(8)) for _ in range(3)]
        if ctrl[0] < 0 or newpos + ctrl[0] > new_size:
            raise ValueError(f"bspatch ctrl[0] 非法：{ctrl[0]} @newpos={newpos}")
        diff = stream_read(ctrl[0])
        new[newpos:newpos + ctrl[0]] = diff
        for i in range(ctrl[0]):
            if 0 <= oldpos + i < len(old):
                new[newpos + i] = (new[newpos + i] + old[oldpos + i]) & 0xFF
        newpos += ctrl[0]
        oldpos += ctrl[0]
        if newpos + ctrl[1] > new_size:
            raise ValueError(f"bspatch ctrl[1] 非法：{ctrl[1]} @newpos={newpos}")
        extra = stream_read(ctrl[1])
        new[newpos:newpos + ctrl[1]] = extra
        newpos += ctrl[1]
        oldpos += ctrl[2]
    return bytes(new)


def lzma_decompress_stream(props: bytes, ph_orig: int, stream: bytes) -> bytes:
    """用 props(5B) 解析 LZMA1 raw 流。props[0]=lc/lp/pb 编码，props[1..4]=dict_size LE。"""
    if len(props) != 5:
        raise ValueError("LZMA props 非 5B")
    d = props[0]
    lc = d % 9
    d //= 9
    pb = d % 5
    lp = d // 5
    dict_size = struct.unpack("<I", props[1:5])[0]
    if dict_size < (1 << 12):
        dict_size = 1 << 12
    filt = [{"id": lzma.FILTER_LZMA1, "dict_size": dict_size, "lc": lc, "lp": lp, "pb": pb}]
    dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt)
    out = dec.decompress(stream, max_length=ph_orig)
    # 某些 bsdiff 流可能不带 eos，decompress 已在 ph_orig 处停
    if len(out) != ph_orig:
        # 尝试继续喂空以触发 flush
        out += dec.decompress(b"", max_length=ph_orig - len(out))
    if len(out) != ph_orig:
        raise ValueError(f"LZMA 解压长度 {len(out)} != ph_orig {ph_orig}")
    return out


def cmd_unpack(args):
    with open(args.input, "rb") as f:
        etu = f.read()
    info = parse_etu_header(etu)
    flags = info["flags"]
    is_full = bool(flags & FLAG_FULL)
    is_diff = bool(flags & FLAG_DIFF)
    if is_full == is_diff:
        sys.stderr.write(f"[err] flags 非法（bit2/bit3 互斥必居其一）：0x{flags:04x}\n")
        return 1
    key = get_aes_key()
    plaintext = aesctr(key, info["nonce"], info["payload"], encrypt=False)

    if is_full:
        # §2.2 全量明文 = 5B props + u64 LE size + LZMA 流
        props = plaintext[:5]
        size = struct.unpack_from("<Q", plaintext, 5)[0]
        stream = plaintext[13:]
        filt_spec = _props_to_filter(props)
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt_spec)
        candidate = dec.decompress(stream, max_length=size)
        if len(candidate) != size:
            candidate += dec.decompress(b"", max_length=size - len(candidate))
        if len(candidate) != size:
            sys.stderr.write(f"[err] 全量 LZMA 解压长度 {len(candidate)} != {size}\n")
            return 1
        if args.verify_fw_header:
            verify_fw_header(candidate, "full")
        with open(args.out, "wb") as f:
            f.write(candidate)
        sys.stdout.write(
            f"unpack(full) OK: {args.out}\n"
            f"  candidate_len={len(candidate)} target_vcode={info['target_vcode']}\n"
            f"  image_sha256={sha256(candidate).hex()}\n"
        )
        return 0

    # 差分
    if not args.old:
        sys.stderr.write("[err] 差分包必须 --old\n")
        return 1
    with open(args.old, "rb") as f:
        old = f.read()
    native_inner = plaintext[:PATCH_HEADER_SIZE]
    lzma_stream = plaintext[PATCH_HEADER_SIZE:]
    ph = parse_patch_header(native_inner)
    if ph["ph_psize"] != len(lzma_stream):
        sys.stderr.write(f"[err] ph_psize={ph['ph_psize']} != 实际 LZMA 流 {len(lzma_stream)}\n")
        return 1
    if ph["ph_osize"] != len(old):
        sys.stderr.write(f"[err] ph_osize={ph['ph_osize']} != len(old)={len(old)}\n")
        return 1
    if crc32(old) != ph["ph_ocrc"]:
        sys.stderr.write(f"[err] old crc32 不匹配 ph_ocrc\n")
        return 1
    # 解 LZMA 流得 bsdiff 原始流
    bsdiff_stream = lzma_decompress_stream(ph["props"], ph["ph_orig"], lzma_stream)
    # 构造一个流式 LZMA 解压器喂 bspatch_py？直接用已解出的 bsdiff_stream 字节流分割
    candidate = bspatch_apply(old, ph["ph_nsize"], bsdiff_stream)
    if len(candidate) != ph["ph_nsize"]:
        sys.stderr.write(f"[err] candidate len {len(candidate)} != ph_nsize {ph['ph_nsize']}\n")
        return 1
    if crc32(candidate) != ph["ph_ncrc"]:
        sys.stderr.write(f"[err] candidate crc32 不匹配 ph_ncrc（stored={ph['ph_ncrc']:08x} calc={crc32(candidate):08x}）\n")
        return 1
    if args.verify_fw_header:
        verify_fw_header(candidate, "patch")
    with open(args.out, "wb") as f:
        f.write(candidate)
    sys.stdout.write(
        f"unpack(patch) OK: {args.out}\n"
        f"  old_len={len(old)} candidate_len={len(candidate)} "
        f"target_vcode={info['target_vcode']} base_vcode={info['base_vcode']}\n"
        f"  base_sha8(etu)={info['base_sha8'].hex()} old_sha8={sha256(old)[:8].hex()}\n"
        f"  candidate_sha256={sha256(candidate).hex()}\n"
    )
    return 0


def bspatch_apply(old: bytes, new_size: int, bsdiff_stream: bytes) -> bytes:
    """bsdiff 原始流（已 LZMA 解压）：循环 {3×i64 LE(24B); diff[ctrl0]; extra[ctrl1]}。"""
    new = bytearray(new_size)
    oldpos = 0; newpos = 0; pos = 0
    n = len(bsdiff_stream)
    while newpos < new_size:
        if pos + 24 > n:
            raise ValueError("bsdiff 流截断（ctrl）")
        ctrl = [offtin(bsdiff_stream[pos + i * 8: pos + (i + 1) * 8]) for i in range(3)]
        pos += 24
        if ctrl[0] < 0 or newpos + ctrl[0] > new_size:
            raise ValueError(f"ctrl[0] 非法 {ctrl[0]}")
        if pos + ctrl[0] > n:
            raise ValueError("bsdiff 流截断（diff）")
        diff = bsdiff_stream[pos:pos + ctrl[0]]; pos += ctrl[0]
        for i in range(ctrl[0]):
            new[newpos + i] = diff[i]
            if 0 <= oldpos + i < len(old):
                new[newpos + i] = (new[newpos + i] + old[oldpos + i]) & 0xFF
        newpos += ctrl[0]; oldpos += ctrl[0]
        if ctrl[1] < 0 or newpos + ctrl[1] > new_size:
            raise ValueError(f"ctrl[1] 非法 {ctrl[1]}")
        if pos + ctrl[1] > n:
            raise ValueError("bsdiff 流截断（extra）")
        new[newpos:newpos + ctrl[1]] = bsdiff_stream[pos:pos + ctrl[1]]
        pos += ctrl[1]; newpos += ctrl[1]
        oldpos += ctrl[2]
    return bytes(new)


def _props_to_filter(props: bytes):
    d = props[0]
    lc = d % 9; d //= 9; pb = d % 5; lp = d // 9  # 标准编码 lc + lp*9 + pb*9*5?
    # LZMA props byte 标准编码: props = (pb*5 + lp)*9 + lc
    lc = props[0] % 9
    rem = props[0] // 9
    lp = rem % 5
    pb = rem // 5
    dict_size = struct.unpack("<I", props[1:5])[0]
    if dict_size < (1 << 12):
        dict_size = 1 << 12
    return [{"id": lzma.FILTER_LZMA1, "dict_size": dict_size, "lc": lc, "lp": lp, "pb": pb}]


def build_parser():
    p = argparse.ArgumentParser(description="OTA .etu 逆向解析+校验（P0-2）")
    p.add_argument("input", help=".etu 路径")
    p.add_argument("--out", required=True, help="candidate.bin 输出")
    p.add_argument("--old", help="差分包基版 old.bin（差分必须）")
    p.add_argument("--verify-fw-header", action="store_true",
                   help="复核 candidate 的 fw_header header_crc32 + image_sha256 双零法")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return cmd_unpack(args)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        sys.stderr.write(f"[err] {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
