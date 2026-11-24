# -*- coding: utf-8 -*-
"""探测看板关键行 exact bytes，为回写脚本提供权威锚点。只读，不写入。"""
import sys

sys.stdout.reconfigure(encoding="utf-8")

p = "D:/github/my/E-Track/PLAN-OTA-EXEC.md"
data = open(p, "rb").read()
lines = data.split(b"\n")
print("total bytes:", len(data))
print("CRLF lines:", data.count(b"\r\n"))
print("split parts:", len(lines), "trailing empty:", lines[-1] == b"")

for n in (621, 622, 623, 636, 637, 638, 639, 640, 790, 791, 792, 1025, 1026, 1027):
    b = lines[n - 1]
    print("=== line", n, "len", len(b), "endswith_cr", b.endswith(b"\r"))
    print(ascii(b.decode("utf-8")))

print("count P3-4 header:", data.count("#### P3-4 AT 提速实测".encode("utf-8")))
print("count P3-3-IMPL-20260907:", data.count(b"P3-3-IMPL-20260907"))
print("count s9 prefix:", data.count("| 2026-09-09 | P3-3 / Codex 实现自测授权治理".encode("utf-8")))
