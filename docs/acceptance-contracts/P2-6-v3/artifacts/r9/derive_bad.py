# -*- coding: utf-8 -*-
# 按 R9 派工书配方由 GOOD-2.8.2.etu 派生 BAD-2.8.2.etu：
#   b[64 + (len(b)-64)//2] ^= 0x01   （payload 中位字节翻转）
#   off36 payload_crc32 = crc32(b[64:])
#   off60 header_crc32  = crc32(b[0:60])
# CRC 使用 Tools.etu_pack 自带的 crc32 实现。
import struct
import sys

sys.path.insert(0, r"D:\github\my\E-Track")
from Tools.etu_pack import crc32

ROOT = r"D:\github\my\E-Track\.cache\p2-6-sd-r9-20260901-01-implementation\tmp"
good = open(ROOT + r"\GOOD-2.8.2.etu", "rb").read()
b = bytearray(good)

flip_off = 64 + (len(b) - 64) // 2
b[flip_off] ^= 0x01
struct.pack_into("<I", b, 36, crc32(bytes(b[64:])))      # payload_crc32
struct.pack_into("<I", b, 60, crc32(bytes(b[0:60])))     # header_crc32

open(ROOT + r"\BAD-2.8.2.etu", "wb").write(bytes(b))

# ---- 自检打印 ----
import hashlib
def fields(x):
    return dict(
        magic=bytes(x[0:4]),
        header_len=struct.unpack_from("<H", x, 4)[0],
        flags=struct.unpack_from("<H", x, 6)[0],
        alg_id=struct.unpack_from("<I", x, 8)[0],
        payload_len=struct.unpack_from("<I", x, 32)[0],
        payload_crc32=struct.unpack_from("<I", x, 36)[0],
        target_vcode=struct.unpack_from("<I", x, 40)[0],
        base_vcode=struct.unpack_from("<I", x, 44)[0],
        header_crc32=struct.unpack_from("<I", x, 60)[0],
    )

print("flip_offset =", flip_off, "(payload 区中位)")
print("GOOD:", fields(good))
print("BAD :", fields(b))
print("GOOD size =", len(good), " SHA-256 =", hashlib.sha256(good).hexdigest().upper())
print("BAD  size =", len(b),  " SHA-256 =", hashlib.sha256(bytes(b)).hexdigest().upper())
print("GOOD payload crc 复算 =", hex(crc32(bytes(good[64:]))), " 头内 =", hex(fields(good)["payload_crc32"]))
print("BAD  payload crc 复算 =", hex(crc32(bytes(b[64:]))), " 头内 =", hex(fields(b)["payload_crc32"]))
print("BAD  header  crc 复算 =", hex(crc32(bytes(b[0:60]))), " 头内 =", hex(fields(b)["header_crc32"]))
assert fields(good)["payload_crc32"] == crc32(bytes(good[64:]))
assert fields(b)["payload_crc32"] == crc32(bytes(b[64:]))
assert fields(b)["header_crc32"] == crc32(bytes(b[0:60]))
assert fields(b)["target_vcode"] == 20802
diffs = [i for i in range(len(good)) if good[i] != b[i]]
print("byte diffs between GOOD and BAD:", diffs, "(应仅 flip_off+36+60 相关字段)")
