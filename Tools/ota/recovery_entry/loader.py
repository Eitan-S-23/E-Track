"""Qualified RAM staging only. No debugger adapter, execute, reset or retry API."""
from dataclasses import dataclass
import hashlib
import struct
import time

from .load_contract import context_ok, inspect

BOOT_SHA = "a63346db0dc673dc42adf6064892c466af5c4571df53cb55fe5b6ea154c1fdf4"


@dataclass(frozen=True)
class EntryContext:
    epoch: str
    board: str
    probe: str
    boot_sha: str
    pc: int
    ipsr: int
    control: int
    primask: int
    msp: int
    fpccr: int
    vtor: int
    xpsr: int
    halted: bool
    power_qualified: bool
    ownership_qualified: bool
    watchdog_qualified: bool


@dataclass
class LoadSession:
    consumed: bool = False
    write_attempts: int = 0


def require(condition, message):
    if not condition:
        raise ValueError(message)


def qualified(context):
    return (isinstance(context, EntryContext) and all(isinstance(s, str) and s for s in
            (context.epoch, context.board, context.probe)) and context.boot_sha == BOOT_SHA and
            context.pc == 0x0800199c and context.vtor == 0x08000000 and
            bool(context.xpsr & 0x01000000) and context.xpsr & 0x1ff == context.ipsr and
            context.halted is True and
            context.power_qualified is True and context.ownership_qualified is True and
            context.watchdog_qualified is True and context_ok(ipsr=context.ipsr,
                control=context.control, primask=context.primask, msp=context.msp, fpccr=context.fpccr))


def stage_elf(session, elf, *, expected_sha256, context, transport, capability,
              timeout_seconds=30, clock=time.monotonic):
    """transport.context/read/write must themselves have finite call deadlines.

    A real adapter must obtain context from qualified acquisition, not construct
    the booleans from a request. Any exception leaves the consumed session and
    potentially partial RAM in place; this function never resumes the core.
    """
    require(isinstance(session, LoadSession) and not session.consumed, "load session already consumed")
    session.consumed = True
    require(qualified(context), "unqualified original-Boot context")
    require(capability in ("nor", "bcb"), "unknown capability")
    require(isinstance(elf, bytes) and hashlib.sha256(elf).hexdigest() == expected_sha256,
            "trusted ELF digest mismatch")
    layout = inspect(elf, dispatched=capability == "nor", bcb_capture=capability == "bcb")
    require(type(timeout_seconds) in (int, float) and 0 < timeout_seconds <= 60, "finite host deadline required")
    started = clock()

    def check():
        elapsed = clock() - started
        require(0 <= elapsed < timeout_seconds, "host deadline expired/backward clock")
        require(transport.context() == context, "entry context changed")
        require(0 <= clock() - started < timeout_seconds, "context read exhausted deadline")

    ph, = struct.unpack_from("<I", elf, 28)
    stride, count = struct.unpack_from("<HH", elf, 42)
    segments = []
    for i in range(count):
        kind, off, vma, lma, size, mem, flags, align = struct.unpack_from("<8I", elf, ph+i*stride)
        if kind == 1 and size:
            segments.append((vma, elf[off:off+size]))
    check()
    chunks = 0
    for address, data in segments:
        for offset in range(0, len(data), 256):
            check()
            part = data[offset:offset+256]
            session.write_attempts += 1
            written = transport.write(address+offset, part)
            require(type(written) is int and written == len(part), "short/uncertain RAM write")
            check()
            require(transport.read(address+offset, len(part)) == part, "RAM chunk verification failed")
            check()
            chunks += 1
    # Detect cross-chunk corruption, not merely the last write's readback.
    for address, data in segments:
        check()
        require(transport.read(address, len(data)) == data, "final segment verification failed")
        check()
    return dict(result="RAM_IMAGE_VERIFIED_NOT_EXECUTED", elf_sha256=expected_sha256,
                verified_chunks=chunks, bytes=sum(len(d) for _, d in segments),
                zeroed_by_host=False, bootstrap_zero_ranges=layout["zero_ranges"],
                device_execute_ready=False)
