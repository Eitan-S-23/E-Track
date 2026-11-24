"""Bounded PageManager-owner and non-consuming QSPI configuration reads."""
import struct

from .probe import require

MANAGER = 0x2004f520
PAGE_VPTR, PAGE_NAME = 0x080a0b10, 0x08059956
PAGE_TEXT = b"Pages/FirmwareUpdate\0"
QSPI_REGS = {"qspi_" + name: 0xa0001000 + offset for name, offset in (
    ("cmd0", 0), ("cmd1", 4), ("cmd2", 8), ("cmd3", 12), ("ctrl", 16),
    ("fifo", 24), ("ctrl2", 32), ("cmdsts", 36), ("rsts_stale", 40),
    ("fsize", 44), ("xip0", 48), ("xip1", 52), ("xip2", 56), ("xip3", 60),
    ("ctrl3", 64), ("revision", 80))}
QSPI_REGS["crm_ahben3"] = 0x40023838


def ram_range(address, size):
    require(type(address) is int and type(size) is int and size > 0 and address % 4 == 0 and
            0x20000000 <= address < address+size <= 0x20058000, "bounded App RAM range required")


def collect(reader):
    reader.grant(MANAGER+4, 12)
    pool = reader.read(MANAGER+4, 12)
    begin, end, capacity = struct.unpack("<3I", pool)
    require(begin <= end <= capacity and end-begin == 9*4 and capacity-begin <= 16*4,
            "exact installed page count and bounded vector capacity required")
    ram_range(begin, capacity-begin)
    reader.grant(begin, end-begin)
    pointers = struct.unpack("<9I", reader.read(begin, end-begin))
    require(len(set(pointers)) == 9, "duplicate page pointer")
    candidates, headers = [], []
    for pointer in pointers:
        ram_range(pointer, 16)
        reader.grant(pointer, 16)
        header = struct.unpack("<4I", reader.read(pointer, 16))
        require(header[2] == MANAGER, "foreign PageManager object")
        headers.append(dict(address=pointer, words=list(header)))
        if header[0] == PAGE_VPTR:
            require(header[3] == PAGE_NAME, "updater name pointer mismatch")
            candidates.append(pointer)
    require(len(candidates) == 1, "unique FirmwareUpdate page required")
    require(reader.name_bytes() == PAGE_TEXT, "live updater name mismatch")
    pointer = candidates[0]
    ram_range(pointer, 0x34f0)
    offsets = {"file_word": 0x44, "phase_word": 0x1284, "work_timer": 0x1470,
               "pending_word": 0x34e8, "mode_word": 0x34ec}
    values = {}
    for name, offset in offsets.items():
        reader.grant(pointer+offset, 4)
        values[name] = int.from_bytes(reader.read(pointer+offset, 4), "little")
    reader.grant(pointer+0x13b4, 64)
    error = reader.read(pointer+0x13b4, 64)
    require(b"\0" in error, "unterminated bounded updater error string")
    require(reader.read(MANAGER+4, 12) == pool and reader.read(begin, end-begin) == struct.pack("<9I", *pointers),
            "page pool changed during observation")
    file_open, phase = values["file_word"] & 0xff, values["phase_word"] & 0xff
    apply_pending, stage_pending = values["pending_word"] & 0xff, (values["pending_word"] >> 8) & 0xff
    mode = values["mode_word"] & 0xff
    require(file_open in (0, 1) and apply_pending in (0, 1) and stage_pending in (0, 1) and phase <= 5 and mode <= 3,
            "unknown updater state encoding")
    return dict(page_pool=list((begin, end, capacity)), headers=headers, updater=pointer, raw=values,
                file_open=file_open, phase=phase, apply_pending=apply_pending, stage_pending=stage_pending,
                mode=mode, work_timer=values["work_timer"], last_error_hex=error.hex(),
                no_scheduled_sd_ota_owner=not any((file_open, apply_pending, stage_pending, values["work_timer"]))
                    and mode != 2 and phase in (0, 4, 5),
                updater_error_observed=phase == 5 or error[0] != 0,
                media_safe_reset_proven=False, nor_settled_proven=False)


class Reader:
    def __init__(self, dap, emit):
        self.dap, self.emit, self.ranges = dap, emit, []

    def grant(self, address, size):
        ram_range(address, size)
        require(size <= 64 and len(self.ranges) < 32, "owner read budget exceeded")
        self.ranges.append((address, address+size))

    def _word(self, address):
        require(self.dap.ready, "DAP not ready")
        rc = self.dap._call("JLINKARM_CORESIGHT_WriteAPDPReg", 1, 1, address)
        require(type(rc) is int and rc >= 0, "owner TAR failed")
        value = self.dap._read_reg(3, 1)
        self.dap._power_ready()
        self.emit("owner-word", address=address, value=value)
        return value

    def read(self, address, size):
        require(type(size) is int and 0 < size <= 64 and size % 4 == 0 and address % 4 == 0 and
                any(start <= address and address+size <= end for start, end in self.ranges), "ungranted owner read")
        return b"".join(self._word(a).to_bytes(4, "little") for a in range(address, address+size, 4))

    def name_bytes(self):
        address = PAGE_NAME & ~3
        data = self.dap.read_flash(address, 24)
        return data[PAGE_NAME-address:PAGE_NAME-address+len(PAGE_TEXT)]

    def qspi(self):
        # No FIFO data or key reads; RSTS is explicitly labelled stale.
        return {name: self._word(address) for name, address in QSPI_REGS.items()}
