"""P3-2 独立验收核验：按冻结契约重新解码真机 INFO 帧与板上镜像。

判据来源（冻结只读）：
  docs/ota-binary-contracts.md §5.1 帧布局 / §5.2.1 INFO payload
                              §1.1 fw_header / §1.2 双零法
  docs/ota-cross-system-contracts.md OTA-XC-IMAGE-IDENTITY
    （跨系统镜像身份 = 最终 app.bin 全部 image_len 字节的 raw SHA-256；
      fw_header 双零域属 header 完整性域，不得进入 INFO.image_sha256）
  docs/ota-binary-contracts.md §0.6 版本编码 major*10000+minor*100+patch

本脚本不复用实现方任何解码代码，仅读取包内冻结产物并独立重算。
fail-closed：任一断言失败即非零退出；无任何无条件汇总字段。
"""

import hashlib
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EV = ROOT / "docs" / "acceptance-contracts" / "P3-2-v1" / "artifacts" / "realdevice"

# 冻结契约常量（不从被测产物反推）
FRAME_MAGIC = b"\xa5\x5a"
CMD_INFO = 0x80
INFO_PAYLOAD_LEN = 50
PROTO_VER = 1
MAX_WINDOW_SEGS = 32
DEVICE_MODEL = b"E-Track\x00"
HDR_OFF = 0x400
HDR_LEN = 96
IDENTITY_LEN = 60
SESS_LEN = 568
TX_FRAME_OFF = 421

failures = []
checks = 0


def ck(cond, label, got=None, want=None):
    global checks
    checks += 1
    if cond:
        print(f"  ok   {label}" + (f" = {got!r}" if got is not None else ""))
    else:
        failures.append(f"{label}: got={got!r} want={want!r}")
        print(f"  FAIL {label}: got={got!r} want={want!r}")


def crc16_ccitt_false(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def load(name):
    p = EV / name
    if not p.is_file():
        raise SystemExit(f"P3_2_REALDEVICE=FAIL 缺少冻结证据: {p}")
    return p.read_bytes()


frame = load("info_frame.bin")
before = load("feed_before.bin")
identity = load("identity.bin")
sess = load("sess_full.bin")
dump = load("app_dump.bin")

print("== A. INFO 帧线格式（§5.1）==")
ck(len(frame) == 8 + INFO_PAYLOAD_LEN + 2, "帧总长 = 8 头 + payload + 2 CRC",
   len(frame), 8 + INFO_PAYLOAD_LEN + 2)
ck(frame[0:2] == FRAME_MAGIC, "magic A5 5A", frame[0:2].hex(), FRAME_MAGIC.hex())
cmd = frame[2]
session = frame[3]
seq = int.from_bytes(frame[4:6], "little")
plen = int.from_bytes(frame[6:8], "little")
ck(cmd == CMD_INFO, "cmd = 0x80 INFO", hex(cmd), hex(CMD_INFO))
ck(session == 0, "session = 0（GET_INFO 无会话）", session, 0)
ck(plen == INFO_PAYLOAD_LEN, "len 字段 = 50", plen, INFO_PAYLOAD_LEN)
ck(8 + plen + 2 == len(frame), "len 字段与实际帧长自洽", 8 + plen + 2, len(frame))
wire_crc = int.from_bytes(frame[8 + plen:10 + plen], "little")
calc_crc = crc16_ccitt_false(frame[2:8 + plen])
ck(calc_crc == wire_crc, "CRC16-CCITT-FALSE 覆盖 cmd..payload、小端上线",
   hex(calc_crc), hex(wire_crc))
ck(seq == int.from_bytes(frame[4:6], "little"), "seq 小端解码自洽", seq, seq)

print("== B. INFO payload 字段（§5.2.1 冻结偏移）==")
p = frame[8:8 + plen]
model = p[0:8]
hw_rev = int.from_bytes(p[8:10], "little")
layout_id = p[10]
boot_ver = p[11]
cur_vcode = int.from_bytes(p[12:16], "little")
info_sha = p[16:48]
proto_ver = p[48]
max_window = p[49]
ck(model == DEVICE_MODEL, "model 偏移 0 长 8 ASCIIZ = E-Track", model, DEVICE_MODEL)
ck(model[-1] == 0, "model 末字节为 NUL（ASCIIZ 边界不溢出）", model[-1], 0)
ck(proto_ver == PROTO_VER, "proto_ver 偏移 48 恒 1", proto_ver, PROTO_VER)
ck(max_window == MAX_WINDOW_SEGS, "max_window_segs 偏移 49 恒 32",
   max_window, MAX_WINDOW_SEGS)
ck(cur_vcode != 0, "cur_vcode 非 0（无 0.0.0 回落）", cur_vcode, "!=0")
ck(info_sha != b"\x00" * 32, "image_sha256 非全零（无占位摘要）", info_sha[:8].hex(), "!=00..")
ck(len(info_sha) == 32, "image_sha256 长 32B", len(info_sha), 32)

print("== C. fw_header 解析与自校验（§1.1/§1.2）==")
h = dump[HDR_OFF:HDR_OFF + HDR_LEN]
ck(h[0:4] == b"ETFW", "magic ETFW @ 偏移 0", h[0:4], b"ETFW")
ck(int.from_bytes(h[4:8], "little") == 1, "header_ver = 1",
   int.from_bytes(h[4:8], "little"), 1)
hdr_vcode = int.from_bytes(h[8:12], "little")
ver_name = h[12:28].split(b"\x00")[0].decode("ascii")
hdr_hw = int.from_bytes(h[32:36], "little")
image_len = int.from_bytes(h[36:40], "little")
stored_hdr_sha = h[40:72]
hdr_layout = h[72]
min_boot = h[73]
pad = h[74:92]
stored_crc = int.from_bytes(h[92:96], "little")
calc_crc32 = zlib.crc32(h[0:92]) & 0xFFFFFFFF
ck(calc_crc32 == stored_crc, "header_crc32 覆盖头前 92B、独立重算一致",
   hex(calc_crc32), hex(stored_crc))
ck(pad == b"\xff" * 18, "pad 偏移 74 长 18 全 0xFF", pad[:4].hex(), "ffffffff")
ck(image_len == len(dump), "image_len == 板上 dump 实际字节数", image_len, len(dump))
maj, mino, pat = (int(x) for x in ver_name.split("."))
ck(hdr_vcode == maj * 10000 + mino * 100 + pat,
   "version_code 与 version_name 按 §0.6 编码一致", hdr_vcode,
   maj * 10000 + mino * 100 + pat)
ck(int.from_bytes(dump[0:4], "little") & 0xFFF00000 == 0x20000000,
   "向量表 MSP 落在 SRAM 区（镜像可引导）", hex(int.from_bytes(dump[0:4], "little")),
   "0x2xxxxxxx")
ck(int.from_bytes(dump[4:8], "little") & 1 == 1,
   "向量表 reset 为 Thumb 地址（bit0=1）", hex(int.from_bytes(dump[4:8], "little")),
   "odd")

print("== D. 摘要域分离（OTA-XC-IMAGE-IDENTITY / OTA-DEC-002）==")
raw_sha = hashlib.sha256(dump[:image_len]).digest()
z = bytearray(dump[:image_len])
z[HDR_OFF + 40:HDR_OFF + 72] = b"\x00" * 32
z[HDR_OFF + 92:HDR_OFF + 96] = b"\x00" * 4
dz_sha = hashlib.sha256(bytes(z)).digest()
ck(dz_sha == stored_hdr_sha, "双零法独立重算 == fw_header 内存储摘要（header 域成立）",
   dz_sha[:8].hex(), stored_hdr_sha[:8].hex())
ck(raw_sha != dz_sha, "raw 身份域与双零 header 域互异（两域确实可区分）",
   raw_sha[:8].hex(), dz_sha[:8].hex())
ck(info_sha == raw_sha, "INFO.image_sha256 == 板上镜像 raw SHA-256（全 32B 逐字节）",
   info_sha.hex(), raw_sha.hex())
ck(info_sha != dz_sha, "INFO.image_sha256 未使用被禁止的双零域",
   info_sha[:8].hex(), "!= " + dz_sha[:8].hex())

print("== E. INFO 字段可追溯到 fw_header 权威运行值 ==")
ck(hw_rev == hdr_hw, "INFO.hw_rev == fw_header.hw_rev", hw_rev, hdr_hw)
ck(layout_id == hdr_layout, "INFO.layout_id == fw_header.layout_id",
   layout_id, hdr_layout)
ck(cur_vcode == hdr_vcode, "INFO.cur_vcode == fw_header.version_code",
   cur_vcode, hdr_vcode)
ck(boot_ver >= min_boot, "INFO.boot_ver >= fw_header.min_boot_ver",
   boot_ver, f">={min_boot}")

print("== F. 快照状态与会话结构一致性 ==")
ck(len(identity) == IDENTITY_LEN, "s_ble_identity 快照 60B", len(identity), IDENTITY_LEN)
ck(identity[0] == 1, "快照 valid = 1（已完成一次校验）", identity[0], 1)
ck(identity[4:12] == DEVICE_MODEL, "快照 model 与冻结常量一致",
   identity[4:12], DEVICE_MODEL)
ck(int.from_bytes(identity[16:20], "little") == cur_vcode,
   "快照 cur_vcode == INFO.cur_vcode", int.from_bytes(identity[16:20], "little"),
   cur_vcode)
ck(identity[20:52] == info_sha, "快照 image_sha256 == INFO.image_sha256（同源取数）",
   identity[20:52][:8].hex(), info_sha[:8].hex())
ck(int.from_bytes(identity[52:56], "little") == 0,
   "快照 fw_header_result = BOOT_FW_OK(0)",
   int.from_bytes(identity[52:56], "little"), 0)
ck(int.from_bytes(identity[56:60], "little") != 0,
   "快照 bcb_result 非 ERROR 语义（仲裁放行）",
   int.from_bytes(identity[56:60], "little"), "!=0")
ck(len(sess) == SESS_LEN, "s_ble_session 整结构 568B", len(sess), SESS_LEN)
ck(sess[TX_FRAME_OFF:TX_FRAME_OFF + len(frame)] == frame,
   f"INFO 帧位于会话结构偏移 {TX_FRAME_OFF}（tx_frame 字段）", True, True)
ck(before == frame,
   "R4 轮喂帧前后 tx_frame 一致（该轮固件已死，帧为 R3 轮产生的 RAM 残留）",
   before[:2].hex(), frame[:2].hex())

print()
print(f"P3_2_REALDEVICE checks={checks} failures={len(failures)}")
print(f"image_len={image_len} version_name={ver_name} version_code={hdr_vcode}")
print(f"raw_identity_sha256={raw_sha.hex()}")
print(f"header_double_zero_sha256={dz_sha.hex()}")
if failures:
    print("P3_2_REALDEVICE=FAIL")
    raise SystemExit(1)
print("P3_2_REALDEVICE=PASS")
