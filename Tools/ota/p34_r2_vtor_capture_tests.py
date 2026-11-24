"""Offline fault-injection tests for the bounded read-only capture adapter."""
import json
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_r2_vtor_capture as cap


class Memory:
    def __init__(self, image, vtor=cap.policy.RUNTIME, fault=None):
        self.image, self.vtor, self.fault = image, vtor, fault
        self.calls, self.now = [], 0.0

    def clock(self):
        return self.now

    def __call__(self, address, length, timeout):
        assert 0 < timeout <= 120 and 0 < length <= cap.CHUNK
        self.calls.append((address, length, timeout))
        self.now += .001
        number = len(self.calls)
        if self.fault == "io" and number == 4:
            raise OSError("injected read failure")
        if self.fault == "deadline" and number == 4:
            self.now += 121
        if self.fault == "clock" and number == 4:
            self.now -= 10
        if address == cap.DHCSR:
            flags = 0
            if self.fault == "reset_before" or self.fault == "reset_after" and number > 1:
                flags = 1 << 25
            if self.fault == "halt":
                flags = 1 << 17
            data = struct.pack("<I", flags)
        elif address == cap.VTOR:
            value = cap.policy.ORIGIN if self.fault == "switch" and number > 2 else self.vtor
            data = struct.pack("<I", value)
        else:
            assert cap.policy.ORIGIN <= address < address+length <= cap.policy.ORIGIN+cap.IMAGE_BYTES
            data = self.image[address-cap.policy.ORIGIN:address-cap.policy.ORIGIN+length]
            if self.fault == "table" and length == cap.policy.TABLE_BYTES:
                data = bytes(length)
            if self.fault == "image" and number == 3:
                data = bytes(length)
        if self.fault == "short" and number == 4:
            return data[:-1]
        if self.fault == "type" and number == 4:
            return bytearray(data)
        return data


def main():
    p = json.loads((ROOT / ".cache/p34-early-use1/profile.json").read_text())
    image = (ROOT / ".cache/p34-early-usb-r2/on/b/app-gcc/X-Track-App-GCC.bin").read_bytes()
    count = 0
    for vtor in (cap.policy.ORIGIN, cap.policy.RUNTIME):
        reader = Memory(image, vtor)
        value = cap.capture(reader, p, clock=reader.clock)
        assert len(reader.calls) == cap.MAX_READS == 157
        assert value["raw_image"] == image and value["boot_generation"] == "NOT_ESTABLISHED"
        assert value["result"]["runtime_vectors_active"] == (vtor == cap.policy.RUNTIME)
        assert value["result"]["operational_readiness"] == "NOT_ESTABLISHED"
        count += 1
    expected = {"io": 4, "deadline": 4, "clock": 4, "reset_before": 1, "reset_after": 157,
                "halt": 1, "switch": 157, "table": 157, "image": 157, "short": 4, "type": 4}
    for fault, calls in expected.items():
        reader = Memory(image, fault=fault)
        try:
            cap.capture(reader, p, clock=reader.clock)
        except cap.CaptureError as error:
            assert len(reader.calls) == calls and len(error.reads) == calls
        else:
            raise AssertionError("fault accepted: " + fault)
        count += 1
    for address in (0, 0x08000000, cap.policy.RUNTIME+4, 0x20000000):
        reader = Memory(image, address)
        try:
            cap.capture(reader, p, clock=reader.clock)
        except cap.CaptureError:
            assert len(reader.calls) == 2
        else:
            raise AssertionError("unbound VTOR accepted")
        count += 1
    for seconds in (0, -1, 121, float("nan"), float("inf"), True):
        reader = Memory(image)
        try:
            cap.capture(reader, p, seconds=seconds, clock=reader.clock)
        except cap.CaptureError:
            assert not reader.calls
        else:
            raise AssertionError("invalid deadline accepted")
        count += 1
    for bad in (dict(p, image_bytes=1 << 31), dict(p, runtime=0x20000000), dict(p, schema="future")):
        reader = Memory(image)
        try:
            cap.capture(reader, bad, clock=reader.clock)
        except cap.CaptureError:
            assert not reader.calls
        else:
            raise AssertionError("invalid profile accepted")
        count += 1
    print("R2_VTOR_CAPTURE_PASS cases=" + str(count))


if __name__ == "__main__":
    assert Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    main()
