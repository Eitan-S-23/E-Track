"""Source-pinned uncached J-Link readers for the fixed three-rate screen."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
TEST = SELF.with_name("test_baud_uncached.py")
SUPPLEMENT = "uncached-reader-004.json"
DWT_CTRL = 0xE0001000
DWT_COUNT = DWT_CTRL + 4


class ProcessEntry(ctypes.Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.c_size_t),
                ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]


def process_inventory():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    for name in ("Process32FirstW", "Process32NextW"):
        function = getattr(kernel, name)
        function.argtypes, function.restype = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)], wintypes.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [wintypes.HANDLE], wintypes.BOOL
    snapshot = kernel.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    result, started = [], time.monotonic()
    try:
        entry = ProcessEntry()
        entry.dwSize = ctypes.sizeof(entry)
        ok = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            if len(result) >= 16384 or time.monotonic() - started > 3:
                raise RuntimeError("native process inventory exceeded its bound")
            result.append((entry.szExeFile, str(entry.th32ProcessID)))
            ok = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        if not result or ctypes.get_last_error() != 18:
            raise ctypes.WinError(ctypes.get_last_error())
        return result
    finally:
        kernel.CloseHandle(snapshot)


def validate_presence(usb, processes):
    if usb != ["USB\\VID_1366&PID_0101\\000000123456"]:
        raise RuntimeError("absent/different/ambiguous USB target")
    debuggers = [item for item in processes if any(part in item[0].lower()
                 for part in ("jlink", "openocd", "uv4", "gdb"))]
    if debuggers:
        raise RuntimeError("another debugger is active: " + str(debuggers))
    return dict(usb=usb, debugger_processes=debuggers, process_inventory="Windows Toolhelp32; no tasklist subprocess")


def native_presence():
    cfg = ctypes.WinDLL("cfgmgr32", use_last_error=True)
    size = wintypes.ULONG()
    cfg.CM_Get_Device_ID_List_SizeW.argtypes = [ctypes.POINTER(wintypes.ULONG), wintypes.LPCWSTR, wintypes.ULONG]
    cfg.CM_Get_Device_ID_ListW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG]
    if cfg.CM_Get_Device_ID_List_SizeW(ctypes.byref(size), None, 0x100) != 0 or not 0 < size.value < 1000000:
        raise RuntimeError("USB inventory size")
    data = ctypes.create_unicode_buffer(size.value)
    if cfg.CM_Get_Device_ID_ListW(None, data, size.value, 0x100) != 0:
        raise RuntimeError("USB inventory")
    usb = [value for value in data[:].split("\0") if "VID_1366" in value.upper()]
    return validate_presence(usb, process_inventory())


def disable_cache(link):
    for expected_previous in (None, 0):
        error = ctypes.create_string_buffer(1024)
        command = "SetEnableMemCache = 0"
        previous = link.sdk.JLINKARM_ExecCommand(command.encode("ascii"), error, len(error))
        link.e.emit("sdk-cache-setting", command=command, previous=previous,
                    error=error.value.decode("ascii", errors="replace"))
        if error.value or previous not in (0, 1) or (expected_previous is not None and previous != expected_previous):
            raise RuntimeError("SDK cache setting failed or disabled state was not confirmed")


def uncached_link(base, evidence):
    class UncachedLink(base):
        def read(self, address, size):
            if size == 4 and address in (DWT_CTRL, DWT_COUNT):
                if not any(start <= address and address + 4 <= end for start, end in self.ram_reads):
                    raise RuntimeError("DWT word is outside the admitted read scope")
                block = (DWT_CTRL, DWT_CTRL + 8)
                if block not in self.ram_reads:
                    self.ram_reads.append(block)
                # V8.18 shadows scalar debug registers even with its memory
                # cache disabled. An aligned CTRL+CYCCNT read reaches hardware.
                data = super().read(DWT_CTRL, 8)
                if len(data) != 8:
                    raise RuntimeError("short DWT hardware block")
                offset = address - DWT_CTRL
                return data[offset:offset + 4]
            return super().read(address, size)

        def connect(self):
            scope = base.connect.__globals__
            original = scope.get("host_presence")
            if original is not None:
                scope["host_presence"] = native_presence
            try:
                super().connect()
            finally:
                if original is not None:
                    scope["host_presence"] = original
            # DWT_CYCCNT is volatile, but ReadMemEx may return a cached debug
            # register. These documented DLL settings do not write the MCU.
            disable_cache(self)
            self.command("InvalidateCache")
            self.e.emit("host-memory-cache-disabled", **evidence())

    return UncachedLink


def runtime():
    r = runpy.run_path(str(SELF.with_name("baud_memory_fix.py")),
                      run_name="uncached_memory_adapter")["configure"]()
    r.PHONE = r.RUNTIME / "phone-r2"

    def evidence():
        return dict(adapter=r.b.record(SELF), supplement=r.b.record(r.b.OUT / SUPPLEMENT))

    r.m.BoundLink = uncached_link(r.m.BoundLink, evidence)
    original_load = r.load

    def load(name, path):
        module = original_load(name, path)
        if Path(path).name == "baud_tune.py":
            module.ControlLink = uncached_link(module.ControlLink, evidence)
        return module

    r.load = load

    def launch(name, mode, seconds, run=None):
        return r.supervisor.owned.launch(r.RUNTIME / name, SELF,
            [mode] + (["--run", run] if run else []), seconds)

    r.launch_worker = launch
    return r


def verified_tests(r):
    path = r.b.OUT / "host-tests-uncached-004/result.json"
    value = r.read(path)
    r.b.require(value["passed"] and value["source"] == r.b.record(SELF) and
                value["test_source"] == r.b.record(TEST) and value["runtime_sources"] == r.sources(),
                "source-bound uncached-reader tests required")
    return r.b.record(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("open-phone", "phone-worker", "launch", "prepare-worker", "capture-worker", "coordinate", "advance", "advance-worker"))
    parser.add_argument("--run", default="baud-115200-r5")
    args = parser.parse_args()
    r = runtime()
    r.b.require(Path.cwd().resolve() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated explicit root required")
    os.environ.update(r.environment())
    r.authority()
    tests = verified_tests(r)
    supplement = r.b.checked(r.b.OUT / SUPPLEMENT)
    if args.mode == "open-phone":
        old_phone = r.RUNTIME / "phone-r1"
        r.b.require(not r.PHONE.exists() and not (r.RUNTIME / "phone-worker-r2").exists(), "preserve phone renewal")
        if not (old_phone / "closed.json").exists():
            current = r.PHONE
            r.PHONE = old_phone
            r.b.require(not r.phone().command(["shell", "pidof", r.PKG], check=False).strip(),
                        "reconcile running App before renewing its USB observer")
            r.PHONE = current
            r.save(old_phone / "stop.json", dict(time=r.b.now(), reason="renew full transfer/apply observation reserve"))
        closed = r.wait_file(old_phone / "closed.json", 30)
        owner = r.wait_file(r.RUNTIME / "phone-worker/closed.json", 30)
        r.b.require(closed["port_closed"] and closed["stop_exit"] == 0 and not closed.get("forced_cleanup") and
                    owner["worker_exit"] == 0 and not owner["forced_termination"] and not r.phone().alive(),
                    "old USB observer did not close normally")
        r.launch_worker("phone-worker-r2", "phone-worker", 5430)
        r.wait_file(r.PHONE / "ready.json", 30)
        r.phone().phone_identity()
        r.b.require(r.phone().installed("runtime") is not None, "installed APK changed")
        r.event("renew-private-usb-window", "completed", phone=str(r.PHONE))
        return
    if args.mode == "phone-worker":
        r.b.require(r.supervisor.owned.in_job(), "bounded phone worker required")
        r.phone().server()
        return
    if args.mode == "launch":
        r.b.require(args.run == "baud-115200-r5" and not supplement.exists(), "preserve uncached-reader preparation")
        prior = r.read(r.b.OUT / "rates/baud-115200-r4.json")
        closed = r.read(r.RUNTIME / "prepare-baud-115200-r4/closed.json")
        r.b.require(prior["result"] == "NOT_ADMITTED" and prior["reader_closed"] and
                    prior["commands"] == [] and prior["ota"] == prior["flash"] == prior["mcu_reset"] == 0 and
                    prior["error"] == "RuntimeError: DWT disabled/frozen after debugger attachment" and
                    closed["worker_exit"] == 1 and not closed["forced_termination"], "old tuning outcome must be reconciled")
        probe = r.read(r.b.OUT / "cache-api-probe-001.json")
        r.b.require(not probe["hardware_opened"] and not probe["device_connected"] and
                    [item["result"] for item in probe["observations"]] == [1, 0, 0, 1] and
                    not any(item["message"] for item in probe["observations"]) and
                    probe["sdk"] == r.b.record(r.m.c.JLINK / "JLink_x64.dll"), "native cache API return semantics not verified")
        blocks = r.read(r.b.OUT / "clock-probe-003/result.json")
        r.b.require(blocks["reader_closed"] and blocks["result"] == "REGISTER_BLOCK_COMPARISON_OBSERVED" and
                    len({x["cycles"] for x in blocks["samples"] if x["size"] == 4}) == 1 and
                    all(len({x["cycles"] for x in blocks["samples"] if x["size"] == size}) == 3 for size in (8, 16)),
                    "actual block-vs-scalar hardware comparison missing")
        old = r.read(r.b.OUT / "uncached-reader-003.json")
        r.b.require(r.b.record(r.b.OUT / "baud-uncached-v3.py")["sha256"] == old["source"]["sha256"],
                    "original failed adapter source was not preserved")
        r.b.require(r.read(r.cell("bootstrap") / "completed.json")["result"] == "COMPLETED_RETAINED",
                    "fixed bootstrap must remain verified")
        r.save(supplement, dict(time=r.b.now(), source=r.b.record(SELF), tests=tests,
            parent_plan=r.b.record(r.b.OUT / "plan.json"), prior=r.b.record(r.b.OUT / "rates/baud-115200-r4.json"),
            native_api_probe=r.b.record(r.b.OUT / "cache-api-probe-001.json"),
            hardware_block_probe=r.b.record(r.b.OUT / "clock-probe-003/result.json"),
            commands=["SetEnableMemCache = 0", "InvalidateCache"],
            reference="https://kb.segger.com/J-Link_Command_Strings#SetEnableMemCache",
            purpose="fresh hardware reads, unchanged DWT/identity/baud guards; preserve failed pre-AT attempt",
            rates=[115200, 460800, 921600], first_run=args.run,
            new_ota_for_host_repair=False, memory_register_writes=False))
        print(r.launch_worker("prepare-" + args.run, "prepare-worker", 900, args.run), flush=True)
        return
    value = r.read(supplement)
    r.b.require(value["source"] == r.b.record(SELF) and value["tests"] == tests and
                value["parent_plan"] == r.b.record(r.b.OUT / "plan.json"), "uncached-reader supplement changed")
    if args.mode == "advance":
        print(r.launch_worker("advance-" + args.run + "-uncached", "advance-worker", 1800, args.run), flush=True)
        return
    r.b.require(r.supervisor.owned.in_job(), "bounded owned worker required")
    if args.mode == "prepare-worker":
        r.b.require(args.run == value["first_run"] and not r.cell(args.run).exists(), "do not reprovision existing run")
        r.b.require(not r.phone().command(["shell", "pidof", r.PKG], check=False).strip(),
                    "previous debug App must remain reconciled/stopped before AT work")
        cycle = r.load("uncached_prepare_lock", SELF.with_name("repeat_cycle.py"))
        tune = r.load("uncached_initial_tune", SELF.with_name("baud_tune.py"))
        with cycle.device_lock():
            tune.tune(args.run, 115200, 30208)
        r.start(args.run, 115200, "screen")
    elif args.mode == "capture-worker":
        cycle = r.load("uncached_capture_lock", SELF.with_name("repeat_cycle.py"))
        with cycle.device_lock():
            raise SystemExit(r.m.capture(args.run))
    elif args.mode == "coordinate":
        r.coordinate(args.run)
    else:
        r.advance(args.run)


if __name__ == "__main__":
    main()
