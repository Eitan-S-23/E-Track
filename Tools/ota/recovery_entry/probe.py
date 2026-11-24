"""One-attempt observation policy, with no native DLL loading or target-write API.

The injected backend must bound native calls in an owned worker. The monotonic
checks here reject late results but cannot interrupt a blocked DLL call. Native
history permission and worker ownership must precede loading the actual DLL.
"""
import math
import re
import struct
import time


BEFORE_OPEN = (
    "SuppressGUI = 1", "DisableAutoUpdateFW", "SetLogVerbose = 1",
    "SetRestartOnClose = 0", "SetSkipDebugDeInit = 1",
)
BEFORE_CONNECT = (
    "Device = CORTEX-M4", "ForceAttachTarget = 1",
    "SetInitWorkRAMOnConnect = 0", "InhibitConnectRetries = 1",
    "DisableFlashBPs", "DisableFlashDL", "DisableCortexMXPSRAutoCorrectTBit",
    "SetRestartOnClose = 0", "SetSkipDebugDeInit = 1", "SetLogVerbose = 1",
    "ExcludeFlashCacheRange 0x08000000-0x0800FFFF",
)
# DisablePowerSupplyOnClose means turn target power OFF, not preserve it.
CORE_READS = (
    ("dhcsr", 0xE000EDF0, 4), ("cpuid", 0xE000ED00, 4),
    ("vtor", 0xE000ED08, 4), ("cpacr", 0xE000ED88, 4),
    ("demcr", 0xE000EDFC, 4), ("dwt_ctrl_cyccnt", 0xE0001000, 8),
    ("fpccr", 0xE000EF34, 4),
)
DEBUG_REGISTERS = {
    0xE0001000: "DWT_CTRL", 0xE000ED88: "CPACR",
    0xE000EDF0: "DHCSR", 0xE000EDFC: "DEMCR",
}
PREVIOUS_VALUE_COMMANDS = {
    "SetRestartOnClose = 0": 0,
    "InhibitConnectRetries = 1": 1,
    "SetEnableMemCache = 0": 0,
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_allowed(address, size):
    if type(address) is not int or type(size) is not int:
        return False
    return ((address, size) in {(a, n) for _, a, n in CORE_READS} or
            (0x08000000 <= address < address + size <= 0x08010000 and
             address % 4 == 0 and 0 < size <= 4096 and size % 4 == 0))


class Observation:
    """Backend: command/select/open/connected/interface/speed/connect/read/close.

    All command results are (integer, message). Zero and an empty message are
    required except the version-bound PREVIOUS_VALUE_COMMANDS. These are set
    twice; the second response must equal the desired value, not generic zero.
    No successful result here qualifies RAM staging or EEPROM/NOR operations.
    """

    def __init__(self, backend, emit, *, seconds=30, clock=time.monotonic):
        require(type(seconds) in (int, float) and math.isfinite(seconds) and
                0 < seconds <= 600, "finite observation deadline required")
        self.backend, self.emit, self.clock = backend, emit, clock
        self.seconds = seconds
        self.started = None
        self.consumed = self.open_attempted = self.connected = self.closed = False

    def _check(self):
        require(self.started is not None and
                0 <= self.clock() - self.started < self.seconds,
                "observation deadline expired/backward clock")

    def _call(self, name, *args):
        self._check()
        self.emit("attempt", operation=name, arguments=list(args))
        result = getattr(self.backend, name)(*args)
        self.emit("returned", operation=name)
        self._check()
        return result

    def _command(self, command, expected=(0,)):
        result, message = self._call("command", command)
        self.emit("setting", command=command, result=result, message=message)
        require(type(result) is int and result in expected and message == "",
                "SDK setting rejected: " + command)

    def _status(self, name, expected, *args):
        result = self._call(name, *args)
        require(type(result) is int and result == expected,
                "unexpected SDK status: " + name)

    def _setting(self, command):
        if command in PREVIOUS_VALUE_COMMANDS:
            self._command(command, (0, 1))
            self._command(command, (PREVIOUS_VALUE_COMMANDS[command],))
        else:
            self._command(command)

    def connect(self):
        require(not self.consumed and not self.closed, "observation already consumed")
        self.consumed = True
        self.started = self.clock()
        try:
            for setting in BEFORE_OPEN:
                self._setting(setting)
            self._status("select", 0, 123456)
            # OpenEx can fail after partially opening the probe. Cleanup is still
            # needed, with restart/de-init policy set before the attempt.
            self.open_attempted = True
            require(self._call("open") is None, "probe open failed")
            state = self._call("connected")
            require(type(state) is int and state == 0, "unexpected target auto-connect/status")
            for setting in BEFORE_CONNECT:
                self._setting(setting)
            self._setting("SetEnableMemCache = 0")
            self._command("InvalidateCache")
            self._status("interface", 0, 1)
            self._call("speed", 1000)
            result = self._call("connect")
            require(type(result) is int and result == 0, "target connection failed; no retry")
            self._status("connected", 1)
            self.connected = True
        except BaseException:
            self.close()
            raise

    def read(self, address, size):
        require(self.connected and not self.closed, "observation is not connected")
        require(read_allowed(address, size), "read outside observation allowlist")
        try:
            data = self._call("read", address, size)
            require(isinstance(data, bytes) and len(data) == size, "short/invalid target read")
            self.emit("read", address=address, size=size, data_hex=data.hex())
            return data
        except BaseException:
            self.close()
            raise

    def sample(self):
        result = {name: self.read(address, size).hex() for name, address, size in CORE_READS}
        dhcsr, = struct.unpack("<I", bytes.fromhex(result["dhcsr"]))
        return dict(raw=result, halted=bool(dhcsr & (1 << 17)),
                    reset_sticky_observed=bool(dhcsr & (1 << 25)),
                    dhcsr_read_clears_reset_sticky=True,
                    pre_attach_values_known=False, device_execute_ready=False)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.connected = False
        if self.open_attempted:
            # Cleanup has its own worker allowance even after the read deadline.
            # Set closed first: an uncertain close is not permission to retry it.
            try:
                self.emit("attempt", operation="close", arguments=[])
            finally:
                self.backend.close()
            self.emit("returned", operation="close")


def scan_sdk_writes(text):
    """Inventory observed CPU_WriteMem calls; never infer nonmutation from a log.

    The retained V8.18 historical logs omit values. Future verbose payload
    grammar must be bound to real SDK output before values can be decoded.
    Unknown write spellings are retained, not silently counted as zero writes.
    """
    require(isinstance(text, str), "SDK log text required")
    writes, unknown = [], []
    for number, line in enumerate(text.splitlines(), 1):
        if not re.search(r"write\s*_?mem|mem\s*_?write", line, re.I):
            continue
        match = re.fullmatch(r".*?CPU_WriteMem\(([0-9]+) bytes @ (0x[0-9A-Fa-f]{8,16})\)", line)
        if match:
            size, address = int(match[1]), int(match[2], 16)
            if not 0 < size <= 0x100000000 or address + size > 0x100000000:
                unknown.append(dict(line=number, text=line))
                continue
            writes.append(dict(line=number, address=address, size=size,
                register=DEBUG_REGISTERS.get(address) if size == 4 else None,
                values_known=False))
        else:
            unknown.append(dict(line=number, text=line))
    return dict(writes=writes, unknown_write_lines=unknown,
                sdk_write_audit_passed=False, transient_debug_state_proven_unchanged=False,
                device_execute_ready=False)
