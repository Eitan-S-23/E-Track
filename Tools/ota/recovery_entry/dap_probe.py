"""AP0 memory reads without JLINKARM_Connect or writes to an AP data register."""
import ctypes
import struct

from .native_probe import Native, guarded
from .probe import CORE_READS, require
from .state_probe import STATE_WORDS

WORDS = frozenset([*(a + i for _, a, size in CORE_READS for i in range(0, size, 4)),
                   *range(0x08000000, 0x08000010, 4), *STATE_WORDS])
APP_LENGTH = 617588
APP_SHA = "4d248fd7e3f6db9d08afdc3712f383064779a3b732ae3b7d550a4f2c393114f6"


def app_word(address):
    return type(address) is int and address % 4 == 0 and 0x08010000 <= address < 0x08010000 + APP_LENGTH


class Dap(Native):
    def __init__(self, sdk, log, project, callbacks):
        super().__init__(sdk, log, project, callbacks)
        self.ready, self.original_tar, self.original_csw = False, None, None
        self.original_dp, self.word_csw, self.power_changed = None, None, False
        self.metadata = dict(tar_restored=False, csw_restored=False, dp_restored=False, cpu_connect_called=False)
        signatures = {
            "JLINKARM_CORESIGHT_Configure": ([ctypes.c_char_p], ctypes.c_int),
            "JLINKARM_CORESIGHT_ReadAPDPReg": ([ctypes.c_uint32, ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32)], ctypes.c_int),
            "JLINKARM_CORESIGHT_WriteAPDPReg": ([ctypes.c_uint32, ctypes.c_uint32,
                ctypes.c_uint32], ctypes.c_int),
        }
        for name, (args, result) in signatures.items():
            function = getattr(sdk, name)
            function.argtypes, function.restype = args, result

    def _read_reg(self, index, ap):
        require((ap, index) in ((0, 0), (0, 1), (1, 0), (1, 1), (1, 3)), "DAP register read scope")
        data = ctypes.c_uint32()
        rc = self._call("JLINKARM_CORESIGHT_ReadAPDPReg", index, ap, ctypes.byref(data))
        require(type(rc) is int and rc >= 0, "DAP register read failed")
        return data.value

    def _write_reg(self, index, ap, value, *, restore=False):
        require(type(index) is int and type(ap) is int and type(value) is int, "DAP integer arguments required")
        require((not restore and ap == 0 and index == 2 and value in (0, 0xf0)) or
                (ap == 0 and index == 1 and self.original_dp is not None and
                 value in (self.original_dp & 0x40, (self.original_dp & 0x40) | 0x10000000,
                           (self.original_dp & 0x40) | 0x50000000)) or
                (ap == 1 and index == 0 and self.original_csw is not None and
                 ((restore and value == self.original_csw) or (not restore and value == self.word_csw))) or
                (ap == 1 and index == 1 and
                 ((restore and self.original_tar is not None and value == self.original_tar) or
                  (not restore and self.ready and (value in WORDS or app_word(value))))), "DAP write outside scoped port setup/read addresses")
        rc = self._call("JLINKARM_CORESIGHT_WriteAPDPReg", index, ap, value)
        require(type(rc) is int and rc >= 0, "DAP register write failed")

    def _power_ready(self):
        value = self._read_reg(1, 0)
        require(value & 0xf0000000 == 0xf0000000 and value & 0xb2 == 0,
                "DAP power not already ready or sticky error; no power/error-clear writes")
        return value

    def _wait_power(self, mask):
        for _ in range(32):
            value = self._read_reg(1, 0)
            require(value & 0xb2 == 0, "DAP sticky error during power handshake")
            if value & 0xa0000000 == mask:
                return value
        raise ValueError("DAP power handshake exhausted")

    def connect(self):
        require(not self.ready, "DAP already configured")
        rc = self._call("JLINKARM_CORESIGHT_Configure", b"")
        require(type(rc) is int and rc >= 0, "SWD CoreSight configure failed")
        self.metadata["dp_id"] = self._read_reg(0, 0)
        require(self.metadata["dp_id"] == 0x2ba01477, "unexpected SW-DP")
        self.original_dp = self._read_reg(1, 0)
        self.metadata["original_dp"] = self.original_dp
        require(self.original_dp in (0, 0x40, 0xf0000000, 0xf0000040), "unqualified DP state; no sticky-error/reset repair")
        if self.original_dp & 0xf0000000 == 0:
            self.power_changed = True
            self._write_reg(1, 0, (self.original_dp & 0x40) | 0x50000000)
            self._wait_power(0xa0000000)
        self.metadata["dp_ctrlstat"] = self._power_ready()
        self._write_reg(2, 0, 0xf0)
        self.metadata["ap_id"] = self._read_reg(3, 1)
        require(self.metadata["ap_id"] == 0x24770011, "unexpected AP0 AHB identity")
        self._write_reg(2, 0, 0)
        csw = self._read_reg(0, 1)
        self.metadata["ap_csw"] = csw
        require(csw & 0x40 and not csw & 0x80,
                "AHB port disabled or transfer already active")
        self.original_csw = csw
        self.word_csw = (self.original_csw & ~0x37) | 0x12
        if self.word_csw != self.original_csw:
            self._write_reg(0, 1, self.word_csw)
            require(self._read_reg(0, 1) == self.word_csw, "word/increment CSW verification failed")
        self.original_tar = self._read_reg(1, 1)
        self.metadata["original_tar"] = self.original_tar
        self.ready = True
        return 0

    def connected(self):
        require(super().connected() == 0, "unexpected high-level CPU connection")
        return int(self.ready)

    def read(self, address, size):
        require(self.ready and type(address) is int and type(size) is int and
                0 < size <= 16 and size % 4 == 0 and
                all(a in WORDS for a in range(address, address + size, 4)), "DAP memory read scope")
        values = []
        for a in range(address, address + size, 4):
            self._write_reg(1, 1, a)
            values.append(self._read_reg(3, 1))
        self._power_ready()
        return struct.pack("<" + "I" * len(values), *values)

    def read_flash(self, address, size):
        require(self.ready and app_word(address) and type(size) is int and
                0 < size <= 1024 and size % 4 == 0 and app_word(address + size - 4) and
                address // 1024 == (address + size - 1) // 1024, "fixed App chunk/auto-increment boundary")
        self._write_reg(1, 1, address)
        def burst():
            values, data = [], ctypes.c_uint32()
            for _ in range(size // 4):
                require(self.callback_error is None, "SDK callback evidence failed")
                rc = self.sdk.JLINKARM_CORESIGHT_ReadAPDPReg(3, 1, ctypes.byref(data))
                require(type(rc) is int and rc >= 0, "DAP burst read failed")
                values.append(data.value)
            return struct.pack("<" + "I" * len(values), *values)
        # One bounded burst avoids a watchdog thread per word. A single stuck
        # native call still kills this worker within the same five-second bound.
        data = guarded(burst)
        self._power_ready()
        return data

    def close(self):
        try:
            if self.original_tar is not None and not self.metadata["tar_restored"] and self._opened:
                self._write_reg(1, 1, self.original_tar, restore=True)
                require(self._read_reg(1, 1) == self.original_tar, "AP TAR restore mismatch")
                self.metadata["tar_restored"] = True
            if self.original_csw is not None and self._opened:
                if self.word_csw != self.original_csw:
                    self._write_reg(0, 1, self.original_csw, restore=True)
                require(self._read_reg(0, 1) == self.original_csw, "AP CSW restore mismatch")
                self.metadata["csw_restored"] = True
        finally:
            try:
                if self.power_changed and self._opened:
                    # Remove the system request before the debug request, never
                    # reset the core or toggle J-Link's physical target supply.
                    self._write_reg(1, 0, (self.original_dp & 0x40) | 0x10000000)
                    self._wait_power(0x20000000)
                    self._write_reg(1, 0, self.original_dp & 0x40)
                    self._wait_power(0)
                    self.metadata["dp_restored"] = True
            finally:
                self.ready = False
                super().close()
