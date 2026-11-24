# -*- coding: utf-8 -*-
"""P3-3 设备观测：手机已装 APK 的只读探针。

输入 = 已用 adb pull 拉取的 base.apk（只读），输出 = 签名证书指纹 + 字符串在场表。
不联网、不接触设备、不写入除标准输出以外的任何位置。
"""
import hashlib
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import zipfile

APK = r"D:\github\my\E-Track\.cache\p3-3-t1a-r1\phone-apk\base.apk"
MAGIC = b"APK Sig Block 42"
V2_ID = 0x7109871A


def _u32(buf, off):
    return struct.unpack_from("<I", buf, off)[0]


def _parse_v2_signer_cert(v2_value):
    """v2 块 -> 第一个 signer 的 signed-data -> certificates -> 首张 DER。"""
    off = 0
    n = _u32(v2_value, off)
    signers = v2_value[4:4 + n]
    n = _u32(signers, 0)
    signer = signers[4:4 + n]
    n = _u32(signer, 0)
    signed_data = signer[4:4 + n]
    n = _u32(signed_data, 0)          # digests（跳过）
    off = 4 + n
    n = _u32(signed_data, off)        # certificates
    certs = signed_data[off + 4:off + 4 + n]
    c0 = _u32(certs, 0)
    return certs[4:4 + c0]


def v2_cert(apk_path):
    data = open(apk_path, "rb").read()
    idx = data.rfind(MAGIC)
    if idx < 0:
        return None, "无 APK Signing Block"
    size2 = struct.unpack_from("<Q", data, idx - 8)[0]
    start = idx + 8 - size2
    size1 = struct.unpack_from("<Q", data, start)[0]
    if size1 != size2:
        return None, "签名块长度字段自相矛盾"
    pos = start + 8
    end = idx - 8
    while pos < end:
        pair_len = struct.unpack_from("<Q", data, pos)[0]
        pid = _u32(data, pos + 8)
        if pid == V2_ID:
            return _parse_v2_signer_cert(data[pos + 12:pos + 8 + pair_len]), "v2"
        pos += 8 + pair_len
    return None, "未找到 v2 块"


def java_array_hashcode(bs):
    """复算 Java Arrays.hashCode(byte[])（byte 有符号），用于与 dumpsys 的哈希对齐。"""
    h = 1
    for b in bs:
        h = (31 * h + (b if b < 128 else b - 256)) & 0xFFFFFFFF
    return "%08x" % h


def read_entry(apk_path, info):
    """stored 条目按偏移直读（Dart AOT 快照通常 stored）；deflate 条目走 zipfile。"""
    if info.compress_type:
        return zipfile.ZipFile(apk_path).read(info.filename)
    with open(apk_path, "rb") as fh:
        fh.seek(info.header_offset)
        hdr = fh.read(30)
        name_len = struct.unpack_from("<H", hdr, 26)[0]
        extra_len = struct.unpack_from("<H", hdr, 28)[0]
        fh.seek(info.header_offset + 30 + name_len + extra_len)
        return fh.read(info.file_size)


def probe_strings(apk_path, needles):
    z = zipfile.ZipFile(apk_path)
    targets = [n for n in z.namelist()
               if n.endswith("libapp.so") or n.endswith("kernel_blob.bin")]
    hits = {}
    for name in targets:
        blob = read_entry(apk_path, z.getinfo(name))
        for n in needles:
            hits.setdefault(n, {})[name] = blob.count(n)
    return targets, hits


def main():
    cert, how = v2_cert(APK)
    if cert is None:
        print("cert: FAIL", how)
        return 1
    print("签名方案:", how)
    print("证书 DER 长度:", len(cert))
    print("证书 SHA-256:", hashlib.sha256(cert).hexdigest())
    print("Java Arrays.hashCode(cert) =", java_array_hashcode(cert))

    needles = [
        b"OTA_MONO ",            # 插桩在场？（预期 0）
        "设备身份已确认".encode("utf-8"),   # 身份读取代码在场？
        "设备未暴露 OTA 服务".encode("utf-8"),
        b"/api/public/firmware/latest",   # 正向对照：该字符串在旧版即存在
        b"nonexist-probe-string",         # 阴性对照
    ]
    targets, hits = probe_strings(APK, needles)
    print("探针目标:", targets)
    for n in needles:
        label = n.decode("utf-8", "replace")
        per = hits.get(n, {})
        print("探针 %-28s -> %s" % (label, per if per else "无目标"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
