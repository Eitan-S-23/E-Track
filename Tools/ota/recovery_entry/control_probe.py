"""Narrow WFI stop/observe transport, separate from the read-only DAP adapter."""
from .dap_probe import WORDS
from .probe import require
from .rendezvous import WFI, WFI_COMPARATOR, WDT_PAUSE
from .state_probe import sample

DHCSR, DCRSR, DCRDR = 0xe000edf0, 0xe000edf4, 0xe000edf8
PAUSE, COMP = 0xe0042008, 0xe0002008
EXTRA = {"wwdt_ctrl": 0x40002c00, "usb_connect_word": 0x20053538,
         "usb_bot_word": 0x200007e8}
READ_WORDS = WORDS | {DCRDR, *EXTRA.values()}


class Control:
    def __init__(self, dap, observation, emit, expected_header, *, retained=False):
        require(isinstance(expected_header, bytes) and len(expected_header) == 96, "bound header required")
        self.dap, self.observation, self.emit = dap, observation, emit
        self.expected_header = expected_header
        self.original_pause = None
        self.pause_written = self.pause_confirmed = self.armed = False
        self.mutation_attempted = self.reset_seen = False
        self.retain_debug_requests = retained is True

    def _read32(self, address):
        require(type(address) is int and address in READ_WORDS and self.dap.ready, "control read scope")
        if address in WORDS:
            value = int.from_bytes(self.dap.read(address, 4), "little")
        else:
            rc = self.dap._call("JLINKARM_CORESIGHT_WriteAPDPReg", 1, 1, address)
            require(type(rc) is int and rc >= 0, "control TAR failed")
            value = self.dap._read_reg(3, 1)
            self.dap._power_ready()
        self.emit("control-word", address=address, value=value)
        return value

    def _write(self, operation, value):
        require(type(value) is int and self.dap.ready, "control integer write required")
        if operation == "pause":
            require(self.original_pause is not None and not self.pause_written and
                    value == self.original_pause | WDT_PAUSE, "pause write scope")
            address = PAUSE
            self.pause_written = True
        elif operation == "arm":
            require(self.pause_confirmed and not self.armed and value == WFI_COMPARATOR, "arm write scope")
            address = COMP
            self.armed = True
        elif operation == "disarm":
            require(self.armed and value == 0, "disarm write scope")
            address = COMP
        elif operation == "selector":
            require(value in (15, 16, 17, 20), "core read selector scope")
            status = self.status()
            require(status["halted"] and not status["lockup"] and not status["reset_sticky"],
                    "core reads require a stable halt")
            address = DCRSR
        else:
            raise ValueError("unknown control operation")
        self.mutation_attempted = True
        self.emit("debug-write-attempt", operation=operation, address=address, value=value)
        rc = self.dap._call("JLINKARM_CORESIGHT_WriteAPDPReg", 1, 1, address)
        require(type(rc) is int and rc >= 0, "debug-write TAR failed")
        rc = self.dap._call("JLINKARM_CORESIGHT_WriteAPDPReg", 3, 1, value)
        require(type(rc) is int and rc >= 0, "debug-write data failed")
        self.dap._power_ready()
        self.emit("debug-write-returned", operation=operation, address=address, value=value)

    def status(self):
        value = self._read32(DHCSR)
        self.reset_seen |= bool(value & 0x02000000)
        return dict(halted=bool(value & 0x20000), lockup=bool(value & 0x80000),
                    reset_sticky=self.reset_seen, register_ready=bool(value & 0x10000),
                    dhcsr_control=value & 0xffff)

    def initial(self):
        require(self.original_pause is None, "initial observation already consumed")
        status = self.status()
        require(self._read32(0xe000ed00) == 0x410fc241, "CPU identity changed")
        header = b"".join(self.dap.read(a, 4) for a in range(0x08010400, 0x08010460, 4))
        require(header == self.expected_header, "live App header changed")
        result = dict(status, vtor=self._read32(0xe000ed08),
                      wfi_bytes=self.dap.read_flash(WFI, 4).hex(),
                      fp_ctrl=self._read32(0xe0002000),
                      comparators=[self._read32(COMP + i*4) for i in range(6)],
                      debug_apb1_frz=self._read32(PAUSE), wwdt_ctrl=self._read32(EXTRA["wwdt_ctrl"]))
        self.original_pause = result["debug_apb1_frz"]
        return result

    def set_halt_pause(self, value):
        self._write("pause", value)

    def read_halt_pause(self):
        value = self._read32(PAUSE)
        self.pause_confirmed = self.pause_written and value == self.original_pause | WDT_PAUSE
        return value

    def arm_wfi(self):
        require(self.pause_confirmed and self.read_halt_pause() == self.original_pause | WDT_PAUSE,
                "pause must still be verified")
        status = self.status()
        require(not status["halted"] and not status["lockup"] and not status["reset_sticky"],
                "core changed before arm")
        require(self.read_comparator() == 0, "comparator acquired by another owner")
        self._write("arm", WFI_COMPARATOR)

    def read_comparator(self):
        return self._read32(COMP)

    def disarm_wfi(self):
        require(self.status()["halted"], "do not disarm an unresolved running rendezvous")
        self._write("disarm", 0)

    def _core(self, selector):
        self._write("selector", selector)
        for _ in range(16):
            status = self.status()
            require(status["halted"] and not status["reset_sticky"] and not status["lockup"],
                    "core changed during register read")
            if status["register_ready"]:
                return self._read32(DCRDR)
        raise ValueError("core register ready timeout")

    def context(self):
        status = self.status()
        require(status["halted"], "context requires halted core")
        pc, xpsr, msp, special = (self._core(i) for i in (15, 16, 17, 20))
        end = self.status()
        return dict(halted=end["halted"], lockup=end["lockup"], reset_sticky=end["reset_sticky"],
                    pc=pc, xpsr=xpsr, msp=msp, control=special >> 24,
                    faultmask=(special >> 16) & 0xff, basepri=(special >> 8) & 0xff,
                    primask=special & 0xff, vtor=self._read32(0xe000ed08), fpccr=self._read32(0xe000ef34))

    def media(self):
        require(self.status()["halted"], "stopped media observation requires halt")
        result = sample(self.observation)
        result["control_extra"] = {name: self._read32(address) for name, address in EXTRA.items()}
        return result

    def observe_retained(self, previous):
        require(previous["result"] == "APP_WFI_HALTED_RETAINED_NOT_RESET" and previous["close_returned"],
                "successful retained predecessor required")
        self.retain_debug_requests = True
        status = self.status()
        require(status["halted"] and not status["lockup"] and not status["reset_sticky"],
                "halt was not retained after close")
        pause = self._read32(PAUSE)
        require(pause == previous["before"]["debug_apb1_frz"] | WDT_PAUSE and self.read_comparator() == 0,
                "retained debug configuration changed")
        context = self.context()
        require(context == previous["context"], "retained context changed")
        samples = [self.media(), self.media()]
        require(self.context() == context and self._read32(PAUSE) == pause, "context changed during retained observation")
        return dict(result="APP_WFI_RETAINED_AFTER_RECONNECT", context=context, state_samples=samples,
                    reset_performed=False, automatic_resume=False, device_execute_ready=False)

    def close(self):
        try:
            if self.mutation_attempted or self.retain_debug_requests:
                # Keep logical CoreSight requests, not physical 3.3V control.
                self.dap.power_changed = False
                self.dap.metadata["dp_restore_deferred_for_halt"] = True
                if self.dap.ready:
                    self.dap.metadata["retained_dp_ctrlstat"] = self.dap._power_ready()
        finally:
            self.observation.close()
