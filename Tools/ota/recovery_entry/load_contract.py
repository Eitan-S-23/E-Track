"""Offline exact-scaffold checker, not a physical or general ELF loader."""
import struct

ZERO_SLOTS = {7, 8, 9, 10, 13, 86, 90, 91, 95, 96, 101, 102, 103, 104,
              105, 106, 109, 111, 112, 113, 114, 115, 116, 117}


def require(ok, why):
    if not ok:
        raise ValueError(why)


def context_ok(*, ipsr, control, primask, msp, fpccr):
    return (ipsr == 0 and control & 7 == 0 and primask == 1 and
            0x200570d8 <= msp <= 0x20058000 and msp % 8 == 0 and fpccr & 1 == 0)


def inspect(data, *, dispatched=False, bcb_capture=False):
    require(not (dispatched and bcb_capture), "one entry capability required")
    require(len(data) >= 52 and data[:7] == b"\x7fELF\x01\x01\x01", "ELF32 LE")
    h = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    require(h[0] == 2 and h[1] == 40 and h[3] == 0x20060401, "exact ARM entry")
    require(h[8] == 32 and h[10] == 40 and h[12] < h[11], "table format")
    require(h[4] + h[9]*32 <= len(data) and h[5] + h[11]*40 <= len(data), "tables")
    segments = []
    allowed = [(0x20060000, 0x20060400), (0x20060400, 0x20062000), (0x20062000, 0x20062800)]
    for i in range(h[9]):
        kind, off, vma, lma, size, mem, flags, align = struct.unpack_from("<IIIIIIII", data, h[4]+i*32)
        if kind != 1:
            continue
        require(vma == lma, "LMA must equal VMA")
        require(size <= mem and off+size <= len(data), "segment file bounds")
        require(any(lo <= vma < vma+mem <= hi for lo, hi in allowed), "segment region")
        require(all(vma+mem <= old[1] or old[1]+old[3] <= vma for old in segments), "segment overlap")
        segments.append((off, vma, size, mem, flags))
    require(len(segments) == 3, "three isolated segments")
    sections = [struct.unpack_from("<IIIIIIIIII", data, h[5]+i*40) for i in range(h[11])]
    strings = sections[h[12]]
    require(strings[4]+strings[5] <= len(data), "section names")
    names = data[strings[4]:strings[4]+strings[5]]
    allocated = {}
    for s in sections:
        if not s[2] & 2:
            continue
        require(s[0] < len(names), "name offset")
        name = names[s[0]:].split(b"\0", 1)[0].decode("ascii")
        require(name in (".vectors", ".text", ".bss") and name not in allocated, "allocated section")
        allocated[name] = s
        require(any(v <= s[3] and s[3]+s[5] <= v+m for _, v, _, m, _ in segments), "section mapping")
        if s[1] != 8:
            require(any(v <= s[3] and s[3]+s[5] <= v+n and
                        s[4] == off+s[3]-v for off, v, n, _, _ in segments), "file mapping")
    require(set(allocated) == {".vectors", ".text", ".bss"}, "exact sections")
    bss = allocated[".bss"]
    # BCB adds the original arbiter's 1024-byte CRC table and ready flag.
    zero_size = 1356 if bcb_capture else 64 if dispatched else 4
    require(bss[1] == 8 and bss[3] == 0x20062000 and bss[5] == zero_size, "exact BSS zero range")
    vector = allocated[".vectors"]
    require(vector[3] == 0x20060000 and vector[5] == 524, "vector bounds")
    table = struct.unpack_from("<131I", data, vector[4])
    require(table[:2] == (0x20066000, h[3]), "initial MSP/reset vector")
    require(all(table[i] == (0 if i in ZERO_SLOTS else 0x2006047f)
                for i in range(2, 131)), "all vector targets")
    code = allocated[".text"]
    require(code[3] == 0x20060400, "code base")
    terminal = code[4] + 0x7e
    require(data[terminal:terminal+4] == bytes.fromhex("72b6fee7"), "terminal instructions")
    require(struct.unpack_from("<I", data, code[4]+0x84)[0] == 0x200570d8,
            "old MSP exception margin literal")
    require(struct.unpack_from("<I", data, code[4]+0x9c)[0] == 0x20062000 and
            struct.unpack_from("<I", data, code[4]+0xa0)[0] == 0x20062000+zero_size,
            "bootstrap zero-loop bounds")
    require([(v, n, m, f) for _, v, n, m, f in segments] == [
        (0x20060000, 524, 524, 4), (0x20060400, code[5], code[5], 5),
        (0x20062000, 0, zero_size, 6)], "exact load/zero/permissions")
    return dict(entry=hex(h[3]), initial_msp="0x20066000", vector_words=131,
                zero_ranges=[["0x20062000", hex(0x20062000+zero_size)]],
                device_execute_ready=False, scope="exact scaffold semantics; trusted digest required")
