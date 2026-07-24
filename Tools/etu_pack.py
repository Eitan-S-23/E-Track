#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
etu_pack.py — OTA .etu 打包工具（P0-2 实现契约 docs/ota-binary-contracts.md v1.0）

子命令:
  finalize       : 回填 App 镜像内嵌 fw_header（SHA 双零法 + header_crc32），原地写回。
  pack-full      : 全量包：app.bin → AES-128-CTR → LZMA-Alone 全量 payload → 64B 外层头 → .etu。
  pack-patch     : 差分包：old/new → 调用 bsdiff.exe 产 40B 原生头 + LZMA 流 → 规范化重写 40B 内层头
                  + 同段 LZMA 流 → AES-128-CTR → 64B 外层头 → .etu。

仅本工具内部自洽：pack 产出的 .etu 由配套 etu_unpack.py 解回 candidate，须与源 app.bin/new.bin 字节一致。
AES key 默认值 = vendor 示例 key（仅开发；生产由 env OTA_AES_KEY=32hex 注入，key_id 递增策略 P4 处理）。
不 commit/push（OTA 规约 §5）；不带升级合法性判定（MCU/App 侧职责）。

参考契约锚点：
  fw_header §1.1/§1.2；.etu 外层头 §2.1；payload 形态 §2.2；40B 内层头 §2.3；
  CRC §0.2；上限 §0.5；version_code §0.6（PRE-1）。
"""
import argparse
import hashlib
import os
import secrets
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

# ---- 契约常量（docs/ota-binary-contracts.md §0.4 / §0.5） -----------------------
FW_HEADER_OFFSET = 0x400
FW_HEADER_SIZE = 96
FW_HEADER_PAD_OFF = 74
FW_HEADER_PAD_LEN = 18
FW_HEADER_CRC_OFF = 92

ETU_MAGIC = b"ETU1"
ETU_HEADER_LEN = 64
ETU_HEADER_CRC_OFF = 60

PATCH_HCRC_OFF = 0   # 4B BE
PATCH_PSIZE_OFF = 4  # 4B BE
PATCH_OSIZE_OFF = 8  # 4B LE
PATCH_NSIZE_OFF = 12 # 4B LE
PATCH_OCRC_OFF = 16  # 4B BE
PATCH_NCRC_OFF = 20  # 4B BE
PATCH_PROPS_OFF = 24 # 5B
PATCH_PAD_OFF = 29   # 3B 0x00
PATCH_ORIG_OFF = 32  # u64 LE
PATCH_HEADER_SIZE = 40

FLAG_AES = 0x0001
FLAG_LZMA = 0x0002
FLAG_DIFF = 0x0004
FLAG_FULL = 0x0008

MAX_ETU_TOTAL = 0x180000   # 1.5MB
MAX_IMAGE_LEN = 0xF0000    # 960KB

DEFAULT_KEY_HEX = "2b7e151628aed2a6abf7158809cf4f3c"  # vendor 教科书示例 key（开发用）


def crc32(buf: bytes) -> int:
    """CRC32-IEEE（§0.2，与 vendor crc32.c / zlib 一致）。"""
    return zlib.crc32(buf) & 0xFFFFFFFF


def sha256(buf: bytes) -> bytes:
    return hashlib.sha256(buf).digest()


def parse_version_name(name: str) -> int:
    """version_code = major*10000+minor*100+patch（§0.6，PRE-1）。
    接受 v 前缀；两段 X.Y 等价 X.Y.0；nightly 后缀去连字符前数字段。"""
    s = name.strip()
    if s.lower().startswith("v"):
        s = s[1:]
    s = s.split("-", 1)[0]
    parts = s.split(".")
    while len(parts) < 3:
        parts.append("0")
    major = int(parts[0]); minor = int(parts[1]); patch = int(parts[2])
    if not (0 <= minor <= 99 and 0 <= patch <= 99):
        raise ValueError(f"minor/patch 必须落入 0..99：{name}")
    vcode = major * 10000 + minor * 100 + patch
    if vcode > 0xFFFFFFFF:
        raise ValueError(f"version_code 超 u32：{name}")
    return vcode


def get_aes_key() -> bytes:
    hexstr = os.environ.get("OTA_AES_KEY")
    if hexstr:
        if len(hexstr) != 32:
            raise ValueError("OTA_AES_KEY 必须 32 hex 字符（16B）")
        return bytes.fromhex(hexstr)
    sys.stderr.write("[warn] OTA_AES_KEY 未设，使用 vendor 示例 key（仅开发）\n")
    return bytes.fromhex(DEFAULT_KEY_HEX)


# ---- AES-128-CTR（nonce 16B 放外层头；counter 初始 = nonce 自身，块递增） -------
def aes_ctr_xcrypt(key: bytes, nonce: bytes, data: bytes, encrypt: bool) -> bytes:
    """CTR 模式加解密同形。nonce 16B 视为初始 128bit 计数器值，每块 +1（big-endian increment
    避免端序歧义；与 pyCryptodome Counter 配合在自包自解场景下自洽，vendor 兼容性由 P0-3/P2 验证）。"""
    if len(nonce) != 16:
        raise ValueError("AES-CTR nonce 必须 16B")
    ctr = Counter.new(128, initial_value=int.from_bytes(nonce, "big"))
    cipher = AES.new(key, AES.MODE_CTR, counter=ctr)
    return cipher.encrypt(data) if encrypt else cipher.decrypt(data)


# ---- fw_header 回填（§1.2 顺序） ----------------------------------------------
# 契约 §0.4/§1：fw_header 落于镜像内 FW_HEADER_OFFSET(0x400) 处，前 0x400 为向量表区
# （linker ASSERT(SIZEOF(.isr_vector) <= 0x400)）；finalize 与 verify 一律按该偏移读写，
# 禁止把头写在 0x00 覆盖向量表。
def build_fw_header(image: bytes, version_name: str, build_ts: int,
                    hw_rev: int = 1, layout_id: int = 1, min_boot_ver: int = 1) -> bytes:
    """image 为完整 App 镜像（含 0x400 向量表区 + 0x400..0x45F 的 fw_header 占位 + 本体）。
    按 §1.2 顺序在 0x400 偏移处回填 96B fw_header：
    ① 填版本/时间/长度/layout/min_boot → ② image_sha256 双零法回填 → ③ header_crc32 回填。
    返回填好的 96B 头字节（由调用方写回 image[0x400:0x460]）。"""
    if len(image) < FW_HEADER_OFFSET + FW_HEADER_SIZE:
        raise ValueError(f"image 短于 0x400+96：{len(image)}")
    if len(image) > MAX_IMAGE_LEN:
        raise ValueError(f"image_len 超 §0.5 上限 0xF0000：{len(image)}")
    vcode = parse_version_name(version_name)
    hdr = bytearray(image[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE])
    # ① 填可控字段（image_len = 整个镜像字节数，含向量表与本头）
    hdr[0:4] = b"ETFW"
    struct.pack_into("<I", hdr, 4, 1)               # header_ver=1
    struct.pack_into("<I", hdr, 8, vcode)           # version_code
    name_b = version_name.encode("ascii", "replace")
    if len(name_b) > 16:
        raise ValueError("version_name 超 16B")
    name_field = name_b.ljust(16, b"\x00")
    hdr[12:28] = name_field
    struct.pack_into("<I", hdr, 28, build_ts & 0xFFFFFFFF)
    struct.pack_into("<I", hdr, 32, hw_rev)
    struct.pack_into("<I", hdr, 36, len(image))     # image_len 含向量表与头
    hdr[72] = layout_id
    hdr[73] = min_boot_ver
    for i in range(FW_HEADER_PAD_OFF, FW_HEADER_PAD_OFF + FW_HEADER_PAD_LEN):
        hdr[i] = 0xFF
    # ② image_sha256 双零法：镜像内 0x400+40..71 与 0x400+92..95 按 0 参与全镜像 SHA-256
    hdr[40:72] = b"\x00" * 32
    hdr[92:96] = b"\x00\x00\x00\x00"
    full = bytearray(image)
    full[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE] = hdr
    digest = sha256(bytes(full))
    hdr[40:72] = digest
    # ③ header_crc32 覆盖头内 off0..91（前 92B），LE 存储
    struct.pack_into("<I", hdr, FW_HEADER_CRC_OFF, crc32(bytes(hdr[:92])))
    return bytes(hdr)


def cmd_finalize(args):
    with open(args.app, "rb") as f:
        image = bytearray(f.read())
    if len(image) < FW_HEADER_OFFSET + FW_HEADER_SIZE:
        sys.stderr.write(f"[err] app.bin 短于 0x400+96：{len(image)}\n")
        return 1
    hdr = build_fw_header(bytes(image), args.ver_name, args.build_ts,
                          args.hw_rev, args.layout_id, args.min_boot)
    image[FW_HEADER_OFFSET:FW_HEADER_OFFSET + FW_HEADER_SIZE] = hdr
    out = args.out or args.app
    with open(out, "wb") as f:
        f.write(image)
    digest = sha256(bytes(image))
    sys.stdout.write(
        f"finalize OK: {out}\n"
        f"  image_len={len(image)} version_name={args.ver_name} vcode={parse_version_name(args.ver_name)}\n"
        f"  image_sha256={digest.hex()}\n"
        f"  header_crc32={struct.unpack_from('<I', hdr, FW_HEADER_CRC_OFF)[0]:08x}\n"
    )
    return 0


# ---- LZMA-Alone 全量 payload -------------------------------------------------
def lzma_alone_encode(data: bytes, dict_size: int = 1 << 14) -> bytes:
    """5B props + u64 LE 原始长度 + LZMA 流（§2.2 全量明文形态）。
    用 lzma.FORMAT_ALONE 产出标准 .lzma（其 u64 size 字段为 0xFF*8 = 未知+eos），
    再把 size 字段替换为真实长度。decoder 在读到 size 字节后即停，尾部 eos 可忽略。"""
    import lzma
    filt = [{"id": lzma.FILTER_LZMA1, "dict_size": dict_size, "lc": 2, "lp": 0, "pb": 0,
             "mode": lzma.MODE_NORMAL, "nice_len": 64, "mf": lzma.MF_BT4, "depth": 0}]
    c = lzma.LZMACompressor(format=lzma.FORMAT_ALONE, filters=filt)
    blob = c.compress(data) + c.flush()
    props = blob[:5]
    stream = blob[13:]  # 跳过 5B props + 8B size
    return props + struct.pack("<Q", len(data)) + stream


# ---- 40B 规范化内层头重写（§2.3） ---------------------------------------------
def normalize_patch_header(native_hdr: bytes, lzma_stream_len: int,
                           old_data: bytes, new_data: bytes) -> bytes:
    """native_hdr=bsdiff.exe 产物前 40B。按 §2.3 规范化形式重写：
    BE：ph_hcrc/ph_psize/ph_ocrc/ph_ncrc；LE：ph_osize/ph_nsize/ph_original_size。"""
    if len(native_hdr) != PATCH_HEADER_SIZE:
        raise ValueError(f"原生内层头非 40B：{len(native_hdr)}")
    # 解析原生（端序见 research 实测：hcrc/psize/ocrc/ncrc BE；osize/nsize LE；orig u64 LE）
    ph_psize_be = struct.unpack_from(">I", native_hdr, PATCH_PSIZE_OFF)[0]
    ph_osize = struct.unpack_from("<I", native_hdr, PATCH_OSIZE_OFF)[0]
    ph_nsize = struct.unpack_from("<I", native_hdr, PATCH_NSIZE_OFF)[0]
    ph_ocrc_be = struct.unpack_from(">I", native_hdr, PATCH_OCRC_OFF)[0]
    ph_ncrc_be = struct.unpack_from(">I", native_hdr, PATCH_NCRC_OFF)[0]
    props = native_hdr[PATCH_PROPS_OFF:PATCH_PROPS_OFF + 5]
    ph_orig = struct.unpack_from("<Q", native_hdr, PATCH_ORIG_OFF)[0]

    # 校验原生值与真实文件一致（防 bsdiff.exe 出错）
    if ph_osize != len(old_data):
        raise ValueError(f"ph_osize({ph_osize}) != len(old)({len(old_data)})")
    if ph_nsize != len(new_data):
        raise ValueError(f"ph_nsize({ph_nsize}) != len(new)({len(new_data)})")
    if ph_psize_be != lzma_stream_len:
        raise ValueError(f"ph_psize({ph_psize_be}) != lzma_stream_len({lzma_stream_len})")
    if ph_ocrc_be != crc32(old_data):
        raise ValueError("ph_ocrc 与 old crc32 不一致")
    if ph_ncrc_be != crc32(new_data):
        raise ValueError("ph_ncrc 与 new crc32 不一致")

    out = bytearray(PATCH_HEADER_SIZE)
    struct.pack_into(">I", out, PATCH_HCRC_OFF, 0)           # 临时置零算 CRC
    struct.pack_into(">I", out, PATCH_PSIZE_OFF, ph_psize_be)
    struct.pack_into("<I", out, PATCH_OSIZE_OFF, ph_osize)
    struct.pack_into("<I", out, PATCH_NSIZE_OFF, ph_nsize)
    struct.pack_into(">I", out, PATCH_OCRC_OFF, ph_ocrc_be)
    struct.pack_into(">I", out, PATCH_NCRC_OFF, ph_ncrc_be)
    out[PATCH_PROPS_OFF:PATCH_PROPS_OFF + 5] = props
    out[PATCH_PAD_OFF:PATCH_PAD_OFF + 3] = b"\x00\x00\x00"
    struct.pack_into("<Q", out, PATCH_ORIG_OFF, ph_orig)
    hcrc = crc32(bytes(out))                                  # 覆盖 40B 全头（hcrc 位已 0）
    struct.pack_into(">I", out, PATCH_HCRC_OFF, hcrc)
    return bytes(out)


# ---- .etu 外层头组装（§2.1） -------------------------------------------------
def build_etu_header(flags: int, aes_nonce: bytes, payload: bytes,
                     target_vcode: int, base_vcode: int, base_sha8: bytes,
                     key_id: int = 1, hw_rev: int = 1, layout_id: int = 1,
                     min_boot_ver: int = 1) -> bytes:
    hdr = bytearray(ETU_HEADER_LEN)
    hdr[0:4] = ETU_MAGIC
    struct.pack_into("<H", hdr, 4, ETU_HEADER_LEN)
    struct.pack_into("<H", hdr, 6, flags)
    struct.pack_into("<I", hdr, 8, 1)              # alg_id=1
    struct.pack_into("<I", hdr, 12, key_id)
    hdr[16:32] = aes_nonce
    struct.pack_into("<I", hdr, 32, len(payload))
    struct.pack_into("<I", hdr, 36, crc32(payload))
    struct.pack_into("<I", hdr, 40, target_vcode)
    struct.pack_into("<I", hdr, 44, base_vcode)
    struct.pack_into("<H", hdr, 48, hw_rev)
    hdr[50] = layout_id
    hdr[51] = min_boot_ver
    hdr[52:60] = base_sha8[:8].ljust(8, b"\x00")
    struct.pack_into("<I", hdr, ETU_HEADER_CRC_OFF, crc32(bytes(hdr[:ETU_HEADER_CRC_OFF])))
    return bytes(hdr)


def check_limits(image_len: int, etu_total: int, label: str):
    if image_len > MAX_IMAGE_LEN:
        raise ValueError(f"[{label}] image_len={image_len} 超 §0.5 上限 0xF0000（960KB）")
    if etu_total > MAX_ETU_TOTAL:
        raise ValueError(f"[{label}] .etu 总长={etu_total} 超 §0.5 上限 0x180000（1.5MB）")


def run_bsdiff(bsdiff_exe: str, old: bytes, new: bytes) -> tuple:
    """调用 bsdiff.exe 产 40B 头 + LZMA 流（-aes 0 不加密，由本工具接管加密）。"""
    with tempfile.TemporaryDirectory() as td:
        old_p = os.path.join(td, "old.bin"); new_p = os.path.join(td, "new.bin")
        patch_p = os.path.join(td, "patch.bin")
        with open(old_p, "wb") as f: f.write(old)
        with open(new_p, "wb") as f: f.write(new)
        cmd = [bsdiff_exe, old_p, new_p, patch_p, "-aes", "0"]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        # 四坑1：bsdiff.exe exit code 恒 0，不看 returncode，看产物
        if not os.path.exists(patch_p):
            sys.stderr.write(f"[err] bsdiff.exe 未产 patch：rc={proc.returncode}\n"
                             f"  stdout={proc.stdout}\n  stderr={proc.stderr}\n")
            raise RuntimeError("bsdiff.exe 失败")
        with open(patch_p, "rb") as f:
            blob = f.read()
        if len(blob) < PATCH_HEADER_SIZE:
            raise RuntimeError(f"bsdiff 产物短于 40B：{len(blob)}")
        return blob[:PATCH_HEADER_SIZE], blob[PATCH_HEADER_SIZE:]


def cmd_pack_full(args):
    key = get_aes_key()
    with open(args.app, "rb") as f:
        app = f.read()
    if len(app) > MAX_IMAGE_LEN:
        sys.stderr.write(f"[err] image_len={len(app)} 超 960KB\n")
        return 1
    target_vcode = args.target_vcode if args.target_vcode is not None else parse_version_name(args.ver_name)
    # 明文 payload = LZMA-Alone 全量
    plaintext = lzma_alone_encode(app, dict_size=args.lzma_dict)
    nonce = secrets.token_bytes(16)  # 每包随机（§2.1）
    payload = aes_ctr_xcrypt(key, nonce, plaintext, encrypt=True)
    flags = FLAG_AES | FLAG_LZMA | FLAG_FULL
    base_sha8 = b"\x00" * 8  # 全量 base_sha8 全 0
    hdr = build_etu_header(flags, nonce, payload, target_vcode, 0, base_sha8,
                           key_id=args.key_id)
    etu = hdr + payload
    check_limits(len(app), len(etu), "pack-full")
    with open(args.out, "wb") as f:
        f.write(etu)
    sys.stdout.write(
        f"pack-full OK: {args.out}\n"
        f"  app_len={len(app)} payload_len={len(payload)} etu_total={len(etu)}\n"
        f"  target_vcode={target_vcode} flags=0x{flags:04x} key_id={args.key_id}\n"
        f"  aes_nonce={nonce.hex()}\n"
        f"  image_sha256={sha256(app).hex()}\n"
        f"  header_crc32={struct.unpack_from('<I', hdr, ETU_HEADER_CRC_OFF)[0]:08x}\n"
    )
    return 0


def cmd_pack_patch(args):
    key = get_aes_key()
    with open(args.old, "rb") as f: old = f.read()
    with open(args.new, "rb") as f: new = f.read()
    if len(new) > MAX_IMAGE_LEN:
        sys.stderr.write(f"[err] new image_len={len(new)} 超 960KB\n")
        return 1
    bsdiff_exe = args.bsdiff_exe or os.path.join(
        "bsdiff_lzma_AES128-main", "bsdiff", "build", "bin", "bsdiff.exe")
    native_hdr, lzma_stream = run_bsdiff(bsdiff_exe, old, new)
    norm_hdr = normalize_patch_header(native_hdr, len(lzma_stream), old, new)
    plaintext = norm_hdr + lzma_stream  # §2.2 差分明文 = 40B 内层头 + LZMA 流
    nonce = secrets.token_bytes(16)
    payload = aes_ctr_xcrypt(key, nonce, plaintext, encrypt=True)
    target_vcode = args.target_vcode if args.target_vcode is not None else parse_version_name(args.ver_name)
    base_vcode = args.base_vcode if args.base_vcode is not None else parse_version_name(args.base_ver_name)
    base_sha8 = sha256(old)[:8]
    flags = FLAG_AES | FLAG_LZMA | FLAG_DIFF
    hdr = build_etu_header(flags, nonce, payload, target_vcode, base_vcode, base_sha8,
                           key_id=args.key_id)
    etu = hdr + payload
    check_limits(len(new), len(etu), "pack-patch")
    with open(args.out, "wb") as f:
        f.write(etu)
    sys.stdout.write(
        f"pack-patch OK: {args.out}\n"
        f"  old_len={len(old)} new_len={len(new)} payload_len={len(payload)} etu_total={len(etu)}\n"
        f"  target_vcode={target_vcode} base_vcode={base_vcode} flags=0x{flags:04x} key_id={args.key_id}\n"
        f"  base_sha8={base_sha8.hex()} aes_nonce={nonce.hex()}\n"
        f"  new_sha256={sha256(new).hex()}\n"
        f"  header_crc32={struct.unpack_from('<I', hdr, ETU_HEADER_CRC_OFF)[0]:08x}\n"
    )
    return 0


def build_parser():
    p = argparse.ArgumentParser(description="OTA .etu 打包工具（P0-2）")
    sub = p.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("finalize", help="回填 fw_header（SHA 双零法 + CRC）")
    pf.add_argument("--app", required=True, help="app.bin（含占位头，原地或 --out 写回）")
    pf.add_argument("--out", help="输出路径（缺省原地写）")
    pf.add_argument("--ver-name", required=True, help="version_name，如 2.8.0")
    pf.add_argument("--build-ts", type=int, required=True, help="UNIX 秒 build_ts")
    pf.add_argument("--hw-rev", type=int, default=1)
    pf.add_argument("--layout-id", type=int, default=1)
    pf.add_argument("--min-boot", type=int, default=1)
    pf.set_defaults(func=cmd_finalize)

    pfull = sub.add_parser("pack-full", help="全量 .etu")
    pfull.add_argument("--app", required=True)
    pfull.add_argument("--out", required=True)
    pfull.add_argument("--target-vcode", type=int, help="目标版本码（缺省由 --ver-name 推导）")
    pfull.add_argument("--ver-name", help="目标 version_name（推导 vcode 用）")
    pfull.add_argument("--lzma-dict", type=int, default=1 << 14, help="LZMA 字典字节，默认 16KB")
    pfull.add_argument("--key-id", type=int, default=1)
    pfull.set_defaults(func=cmd_pack_full)

    ppat = sub.add_parser("pack-patch", help="差分 .etu")
    ppat.add_argument("--old", required=True)
    ppat.add_argument("--new", required=True)
    ppat.add_argument("--out", required=True)
    ppat.add_argument("--target-vcode", type=int)
    ppat.add_argument("--ver-name", help="目标 version_name（推导 vcode 用）")
    ppat.add_argument("--base-vcode", type=int)
    ppat.add_argument("--base-ver-name", help="基版 version_name（推导 base_vcode 用）")
    ppat.add_argument("--bsdiff-exe", help="bsdiff.exe 路径（缺省 bsdiff_lzma_AES128-main/bsdiff/build/bin/bsdiff.exe）")
    ppat.add_argument("--key-id", type=int, default=1)
    ppat.set_defaults(func=cmd_pack_patch)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, RuntimeError, FileNotFoundError) as e:
        sys.stderr.write(f"[err] {e}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
