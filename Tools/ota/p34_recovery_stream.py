"""Offline two-pass recovery transaction using finalized R2 and native admission.

No hardware backend exists. The NOR model is reused without changing its old
tests. Chunk fingerprints are RAM-manifest equivalents, not transport CRCs.
"""
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_install_cost as host
import p34_recovery_admission as admission
import p34_recovery_sources as sources
import p34_recovery_transaction_model as model


class ReadNor(model.Nor):
    def __init__(self, initial, fault=None, read_fault=None):
        super().__init__(initial, fault)
        self.read_fault = read_fault

    def read(self, offset, length, phase):
        if self.read_fault == phase:
            raise model.Interrupted("read failure: " + phase)
        return bytes(self.data[offset:offset+length])


def stream(nor, source, pinned, receive, oracle, *, base=model.BASE, kind=4):
    if base != model.BASE or kind != 4 or hashlib.sha256(source).hexdigest() != pinned:
        raise ValueError("invalid source/scope")
    sources.verify(source)
    # The native snapshot validator runs before ANY modeled NOR mutation.
    oracle(admission.slot(source), 0, "preflight")
    digests = [hashlib.sha256(source[i:i+4096]).digest()
               for i in range(0, len(source), 4096)]
    nor.mutate("erase", model.BASE, b"\xff"*4096)
    if nor.read(0, 4096, "header_erased") != b"\xff"*4096:
        raise model.Interrupted("header erase mismatch")
    for index, digest in enumerate(digests):
        chunk = receive(index)
        expected = min(4096, len(source)-index*4096)
        if len(chunk) != expected or hashlib.sha256(chunk).digest() != digest:
            raise model.Interrupted("chunk rejected before erase/program")
        address = model.BASE+4096+index*4096
        nor.mutate("erase", address, b"\xff"*4096)
        if nor.read(address-model.BASE, 4096, "payload_erased") != b"\xff"*4096:
            raise model.Interrupted("payload erase mismatch")
        for offset in range(0, len(chunk), 256):
            page = chunk[offset:offset+256]
            nor.mutate("program", address+offset, page)
            if nor.read(address-model.BASE+offset, len(page), "page") != page:
                raise model.Interrupted("page mismatch")
    if nor.read(4096, len(source), "payload") != source:
        raise model.Interrupted("full payload mismatch")
    metadata = admission.slot(source)[:28]
    # Virtual header in host memory permits full Boot payload checks before
    # committing actual NOR metadata. This is not a physical marker write.
    virtual = bytearray(nor.data)
    virtual[:32] = metadata+b"TMOC"
    oracle(bytes(virtual), 0, "precommit")
    nor.mutate("program", model.BASE, metadata)
    if nor.read(0, 32, "header") != metadata+b"\xff"*4:
        raise model.Interrupted("metadata mismatch")
    nor.mutate("program", model.BASE+28, b"TMOC")
    oracle(nor.read(0, 0x100000, "committed"), 0, "committed")


def main():
    cli = host.cli
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
                sys.dont_write_bytecode, "isolated root required")
    store = cli.Store(ROOT)
    out = store.checked(ROOT/".cache/p34-recovery-stream1")
    cli.require(not out.exists(), "preserve evidence")
    previous = ROOT/".cache/p34-recovery-admission2/result.json"
    binding = store.read(previous)
    for item in binding["inputs"]+[binding["executable"]]:
        cli.require(cli.record(item["path"]) == item, "native admission drift")
    exe = Path(binding["executable"]["path"])
    image = ROOT/".cache/p34-recovery-sources1/r2-a.bin"
    source = image.read_bytes()
    pinned = "7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf"
    # All native temporary/log paths are numeric under this fixed checked root.
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP", "TMPDIR",
                "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "PYTHONUSERBASE",
                "PYTHONPYCACHEPREFIX", "CCACHE_DIR", "SCCACHE_DIR"):
        store.checked(out/"host"/key.lower())
    for i in range(128):
        for suffix in (".bin", ".log", ".json"):
            store.checked(out/(str(i)+suffix))
    store.checked(out/"result.json")
    env = host.environment(store, out)
    native = []

    def oracle(raw, expected, phase):
        number = str(len(native))
        cli.require(len(native) < 128, "bounded native checks")
        path = out/(number+".bin")
        store.raw(path, raw)
        host.command(store, out, number, [exe, path, expected, 0], env, 30)
        native.append(dict(phase=phase, expected=expected, file=cli.record(path)))

    receive = lambda i: source[i*4096:(i+1)*4096]
    initial = b"\xa5"*0x100000
    complete = ReadNor(initial)
    stream(complete, source, pinned, receive, oracle)
    cases = ["normal"]
    end = (4096+len(source)+4095)//4096*4096
    cli.require(complete.data[end:] == initial[end:], "trailing sector changed")

    for index in (0, 75, 151):
        for mode in ("changed", "short"):
            def bad_receive(i):
                part = receive(i)
                if i == index:
                    return part[:-1] if mode == "short" else bytes([part[0]^1])+part[1:]
                return part
            nor = ReadNor(initial)
            try:
                stream(nor, source, pinned, bad_receive, oracle)
            except model.Interrupted:
                pass
            else:
                raise AssertionError("changed stream accepted")
            boundary = model.BASE+4096+index*4096
            cli.require(all(a+n <= boundary for _, a, n in nor.trace), "rejected chunk mutated")
            oracle(bytes(nor.data), 1, "rejected_stream")
            cases.append(mode+str(index))

    for phase in ("header_erased", "payload_erased", "page", "payload", "header", "committed"):
        nor = ReadNor(initial, read_fault=phase)
        try:
            stream(nor, source, pinned, receive, oracle)
        except model.Interrupted:
            pass
        else:
            raise AssertionError("read failure hidden")
        oracle(bytes(nor.data), 0 if phase == "committed" else 1, "read_failure_"+phase)
        cases.append("read_failure_"+phase)

    # Retain real modeled bytes over three interruptions, then complete once.
    nor = ReadNor(initial, fault=(len(complete.trace)-1, 4))
    for event, prefix in ((len(complete.trace)-1, 4), (0, 29), (2, 127)):
        nor.fault = (len(nor.trace)+event, prefix)
        try:
            stream(nor, source, pinned, receive, oracle)
        except model.Interrupted:
            pass
        else:
            raise AssertionError("write failure hidden")
        cli.require(len(nor.trace) == nor.fault[0]+1, "continued after error")
        oracle(bytes(nor.data), 0 if event == len(complete.trace)-1 else 1, "retained_interruption")
    nor.fault = None
    stream(nor, source, pinned, receive, oracle)
    cases.append("three_retained_interruptions_then_retry")

    for data, digest, options in ((source, "0"*64, {}), (source+b"TRAILER!", pinned, {}),
                                  (source, pinned, {"base": model.BASE-1}),
                                  (source, pinned, {"kind": 2})):
        nor = ReadNor(initial)
        try:
            stream(nor, data, digest, receive, oracle, **options)
        except ValueError:
            pass
        else:
            raise AssertionError("bad preflight accepted")
        cli.require(not nor.trace, "bad preflight wrote NOR")
        cases.append("zero_write_preflight")
    store.write(out/"result.json", dict(result="STREAM_MODEL_WITH_NATIVE_ADMISSION_PASS",
        cases=cases, native=native, inputs=[cli.record(p) for p in
        (Path(__file__), Path(model.__file__), Path(admission.__file__), Path(sources.__file__),
         previous, image)], hardware=False, scope="host model only; RAM loader not implemented"))
    print("STREAM_MODEL_WITH_NATIVE_ADMISSION_PASS cases="+str(len(cases))+" native="+str(len(native)))


if __name__ == "__main__":
    main()
