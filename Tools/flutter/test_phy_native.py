"""Contained pure-Java PHY lifecycle tests, not a local Android/Flutter build."""
import argparse
import os
from pathlib import Path
import re
import runpy
import shutil
import sys
import uuid


def log_property(tag):
    if not isinstance(tag, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", tag):
        raise ValueError("native log tag is not Android property-compatible")
    return "log.tag." + tag


def check_native_log_tag(source):
    if log_property("FBP-Android") != "log.tag.FBP-Android":
        raise AssertionError("native log property differs")
    for tag in ("[FBP-Android]", "", "tag space", "tag/name", "tag:name"):
        try:
            log_property(tag)
        except ValueError:
            continue
        raise AssertionError("invalid Android property name admitted")
    tags = re.findall(r'private static final String TAG = "([^"]+)";', source)
    if tags != ["FBP-Android"]:
        raise ValueError("native plugin tag differs from its scoped collector binding")
    return dict(tag=tags[0], property=log_property(tags[0]), checks=6)


def callback_factory(source):
    factories = re.findall(r"(?ms)^    static Handler createCallbackHandler\(\) \{\n.*?^    \}", source)
    if len(factories) != 1:
        raise ValueError("one actual callback Handler factory required")
    if source.count("private final Handler callbackHandler = createCallbackHandler();") != 1 or \
            source.count("callbackHandler.post(() -> {") != 1 or \
            "new Handler(Looper.getMainLooper()).post(" in source or "postAtFrontOfQueue" in source:
        raise ValueError("callback delivery must share one FIFO Handler")
    guard = r"callbackHandler\.post\(\(\) -> \{.*?if \(methodChannel != null\) \{\s*" \
            r"nativeWriteTrace\.dispatched\(trace\);\s*methodChannel\.invokeMethod\(method, data\);"
    if not re.search(guard, source, re.S):
        raise ValueError("main-channel availability and native timing guard changed")
    return factories[0]


def check_callback_wiring(source):
    factory = callback_factory(source)
    for old, new in (("private final Handler callbackHandler", "private final Handler differentHandler"),
                     ("callbackHandler.post(() -> {", "new Handler(Looper.getMainLooper()).post(() -> {"),
                     ("if (methodChannel != null) {", "if (true) {")):
        if old not in source:
            raise AssertionError("negative fixture no longer targets actual source")
        try:
            callback_factory(source.replace(old, new))
        except ValueError:
            continue
        raise AssertionError("invalid callback wiring admitted")
    return factory, dict(checks=4, thread="main-looper", actual_android_barrier_test=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    root = Path(os.path.abspath(args.repo_root))
    if Path.cwd() != root or not sys.dont_write_bytecode:
        raise ValueError("explicit root cwd and no-bytecode required")
    h = runpy.run_path(str(root / "Tools/flutter/dev_checks.py"))
    checked = lambda path: h["checked_path"](root, path)
    out = checked(root / ".cache/p34-phy-native/runs" / uuid.uuid4().hex)
    classes, logs = checked(out / "classes"), checked(out / "logs")
    sources = root / "app/bluetooth_flutter_Trace/vendor/flutter_blue_plus_android/android/src"
    inputs = [sources / "main/java/com/lib/flutter_blue_plus/PhyProbe.java",
              sources / "test/java/com/lib/flutter_blue_plus/PhyProbeTest.java",
              sources / "main/java/com/lib/flutter_blue_plus/NativeWriteTrace.java",
              sources / "test/java/com/lib/flutter_blue_plus/NativeWriteTraceTest.java"]
    plugin = checked(sources / "main/java/com/lib/flutter_blue_plus/FlutterBluePlusPlugin.java")
    plugin_source = plugin.read_text(encoding="utf-8")
    logging = check_native_log_tag(plugin_source)
    print("NATIVE_LOG_TAG_TESTS_PASS", logging["checks"], logging["property"], flush=True)
    factory, wiring = check_callback_wiring(plugin_source)
    template = checked(sources / "test/java/com/lib/flutter_blue_plus/CallbackHandlerTest.java.template")
    generated = checked(out / "CallbackHandlerTest.java")
    fixture = template.read_text(encoding="utf-8")
    if fixture.count("    /* ACTUAL_CALLBACK_FACTORY */") != 1:
        raise ValueError("callback test injection marker")
    fixture = fixture.replace("    /* ACTUAL_CALLBACK_FACTORY */", factory)
    for path in inputs + [template, generated, out / "result.json", logs / "compile.log", logs / "run.log",
                          logs / "native-write.log", logs / "callback-handler.log"]:
        checked(path)
    classes.mkdir(parents=True)
    logs.mkdir()
    with generated.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(fixture)
    env = h["contained_environment"](root, out)
    for key in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "CLASSPATH"):
        env.pop(key, None)
    java_home = os.environ.get("JAVA_HOME_17_X64") or os.environ.get("JAVA_HOME")
    def tool(name):
        candidate = Path(java_home) / "bin" / (name + (".exe" if os.name == "nt" else "")) if java_home else None
        value = str(candidate) if candidate and candidate.is_file() else shutil.which(name)
        if not value:
            raise RuntimeError("JDK required for " + name)
        return value
    java_options = ["-Djava.io.tmpdir=" + env["TEMP"], "-Duser.home=" + env["HOME"],
                    "-XX:-UsePerfData", "-XX:ErrorFile=" + str(checked(out / "hs_err_pid%p.log"))]
    commands = [
        ("compile", [tool("javac"), *("-J" + item for item in java_options),
            "--release", "8", "-Xlint:all", "-Werror", "-d", str(classes), *map(str, inputs), str(generated)]),
        ("run", [tool("java"), *java_options, "-cp", str(classes), "com.lib.flutter_blue_plus.PhyProbeTest"]),
        ("native-write", [tool("java"), *java_options, "-cp", str(classes), "com.lib.flutter_blue_plus.NativeWriteTraceTest"]),
        ("callback-handler", [tool("java"), *java_options, "-cp", str(classes), "com.lib.flutter_blue_plus.CallbackHandlerTest"]),
    ]
    results = []
    for name, argv in commands:
        log = checked(logs / (name + ".log"))
        result = h["run_command"](root, argv, root, env, log, 60)
        results.append(dict(name=name, **result))
        print(log.read_text(encoding="utf-8", errors="replace"), flush=True)
        if result["status"] != "PASS":
            break
    passed = len(results) == 4 and all(item["status"] == "PASS" for item in results)
    native_checks = re.findall(r"^NATIVE_WRITE_TRACE_TESTS_PASS (\d+)$",
        (logs / "native-write.log").read_text(encoding="utf-8"), re.M) if passed else []
    passed = passed and len(native_checks) == 1 and int(native_checks[0]) >= 24
    callback_checks = re.findall(r"^CALLBACK_HANDLER_TESTS_PASS (\d+)$",
        (logs / "callback-handler.log").read_text(encoding="utf-8"), re.M) if passed else []
    passed = passed and len(callback_checks) == 1 and int(callback_checks[0]) == 30
    h["save_report"](root, out / "result.json", dict(passed=passed, results=results,
        inputs={str(p.relative_to(root)): h["file_hash"](p) for p in [*inputs, plugin, template]},
        logging=logging,
        write_trace=dict(checks=int(native_checks[0]) if native_checks else 0),
        callback_handler=dict(wiring=wiring, checks=int(callback_checks[0]) if callback_checks else 0),
        hardware=False, android_plugin_compiled=False))
    print("PHY_NATIVE_RESULT", passed, str(out), flush=True)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
