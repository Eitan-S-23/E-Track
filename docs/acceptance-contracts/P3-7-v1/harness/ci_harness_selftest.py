"""p3_7_verify_ci_evidence.py 的双向鉴别力自检（派工书 v2，四条接线 / 11 条腿）。

fail-closed 只保证「没证据必红」。还必须证明两件事，否则这个门禁没有鉴别力：
1. 面对**格式良好的完整证据**能变绿——否则它是永久红，等于没门禁；
2. 面对每一类伪造/无效证据能变红——重点是本卡特有的「无效注错选点」：
   缺陷若打红了新增四行**之前**的既有测试，步骤在那里就短路，新增行从未执行，
   这种「红」不构成反证。

做法：把核验器复制到 .cache 并只改 CI_DIR 与 run 标识常量（判据逻辑一字不动），
用合成证据驱动。docs/ 全程不落任何文件。
"""

import json
import pathlib
import re
import shutil
import subprocess
import sys
import hashlib

ROOT = pathlib.Path("D:/github/my/E-Track")
WORK = ROOT / ".cache/p3-7-accept/selftest"
CI = WORK / "ci"
SRC = ROOT / "tests/ota/p3_7_verify_ci_evidence.py"
COPY = ROOT / ".cache/p3-7-accept/ci_evidence_under_test.py"

JOB = "Build firmware (arm-none-eabi-gcc)"
STEP = "Run host tests (boot vectors, OTA host tests, P3-1 product regressions)"
ECHO = [
    "set -euo pipefail",
    "python3 tests/boot/test_fw_header_vectors.py",
    "python3 tests/boot/test_boot_protocols.py",
    "python3 tests/boot/test_boot_state_machine.py",
    "python3 tests/ota/test_ota_staging.py",
    "python3 tests/ota/test_ota_package.py",
    "python3 tests/ota/test_ota_patch.py",
    "python3 tests/ota/test_ota_ble_frame.py",
    "python3 tests/ota/test_ota_ble_session.py",
    "python3 tests/ota/p3_1_verify_contract_alignment.py",
    "python3 tests/ota/p3_1_verify_text_isolation.py",
    "python3 tests/ota/p3_1_verify_portability.py",
    "python3 tests/ota/test_ota_device_info.py",
]
PRECEDING = [
    "P1_1_FW_HEADER_VECTORS=PASS",
    "P1_1_BOOT_PROTOCOLS=PASS",
    "P1_3_STATE_MACHINE=PASS",
    "P2_1_STAGING=PASS",
    "P2_2_PACKAGE=PASS",
    "P2_3_VECTOR_PREFLIGHT=PASS",
    "P3_1_BLE_FRAME=PASS checks=39 failures=0",
    "P3_1_BLE_SESSION=PASS checks=105 failures=0",
]
# 每条接线在绿运行里应出现的行（cmd12 有两行）。
WIRED_PASS = [
    ["P3_1_CONTRACT_ALIGNMENT=PASS drift=0 checks=47"],
    ["P3_1_TEXT_ISOLATION=PASS cases=3 transparent=0 trace_points=1 sink_guard=True"],
    ["P3_1_PORTABILITY=PASS scanned=895 control_hits=1 live_hits=0 new_src_hits=0"],
    ["P3_2_OTA_DEVICE_INFO checks=114 failures=0", "P3_2_OTA_DEVICE_INFO_ALL=PASS"],
]
# 每条接线在其被注错的红运行里应出现的行。
WIRED_FAIL = [
    ["[DRIFT] ACK_BEGIN: contract=10 impl=11",
     "P3_1_CONTRACT_ALIGNMENT=FAIL drift=1 checks=47"],
    ["P3_1_TEXT_ISOLATION=FAIL cases=3 transparent=0 trace_points=1 sink_guard=False"],
    ["P3_1_PORTABILITY=FAIL scanned=895 control_hits=1 live_hits=1 new_src_hits=1"],
    ["FAIL: T1 model exact 8B", "P3_2_OTA_DEVICE_INFO checks=114 failures=1"],
]
# 四次反证各自的冻结注错目标（须与核验器 WIRED[*]["target"] 一致）。
TARGETS = [
    "Libraries/OTA/ota_ble_frame.h",
    "USER/HAL/HAL_Bluetooth.cpp",
    "USER/HAL/HAL_USB.cpp",
    "Libraries/OTA/ota_device_info.c",
]
BASE_CHANGED = [
    ".github/workflows/firmware-build.yml",
    "docs/ota-exec-notes/P3-7-wiring-evidence.md",
]

RUNS = {
    "base": ("40000000001", "a" * 40),
    "trigA": ("40000000002", "b" * 40),
    "trigB": ("40000000003", "9" * 40),
    "red0": ("40000000010", "c" * 40),
    "grn0": ("40000000011", "d" * 40),
    "red1": ("40000000020", "e" * 40),
    "grn1": ("40000000021", "f" * 40),
    "red2": ("40000000030", "0" * 40),
    "grn2": ("40000000031", "1" * 40),
    "red3": ("40000000040", "2" * 40),
    "grn3": ("40000000041", "3" * 40),
}

# 收口批次已把真实 run 号回填进核验器。被测副本必须一个不剩地换成合成号，否则
# 每个变异用例都会以「证据文件缺失」变红——看似全红，实则零鉴别力。
REAL_RUNS = sorted(set(re.findall(r"\b33\d{9}\b", SRC.read_text(encoding="utf-8"))))
assert len(REAL_RUNS) == 11, f"预期 11 个真实 run 号，实得 {len(REAL_RUNS)}"

# 真实证据目录必须逐字节不受自检影响（自检只在 .cache 下合成证据）。
REAL_CI = ROOT / "docs" / "acceptance-contracts" / "P3-7-v1"


def tree_digest(root):
    if not root.exists():
        return "<不存在>"
    acc = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            acc.update(path.relative_to(root).as_posix().encode("utf-8"))
            acc.update(hashlib.sha256(path.read_bytes()).digest())
    return acc.hexdigest().upper()


def flat(rows):
    return [line for row in rows for line in row]

def step_log(path, body_lines, step_conclusion_error):
    """按 gh run view --log 的真实列格式合成一段步骤日志。"""
    out = []
    stamp = "2026-09-04T01:02:{:02d}.1234567Z"
    counter = [0]

    def emit(content, bom=False):
        counter[0] = (counter[0] + 1) % 60
        prefix = "\ufeff" if bom else ""
        out.append(f"{JOB}\t{STEP}\t{prefix}{stamp.format(counter[0])} {content}")

    emit(f"##[group]Run {ECHO[0]}", bom=True)
    for command in ECHO:
        emit(f"^[[36;1m{command}^[[0m")
    emit("shell: /usr/bin/bash --noprofile --norc -e -o pipefail {0}")
    emit("##[endgroup]")
    for line in body_lines:
        emit(line)
    if step_conclusion_error:
        emit("##[error]Process completed with exit code 1.")
    path.write_bytes(("\n".join(out) + "\n").encode("utf-8"))


def run_json(path, run_id, head, conclusion, step_conclusion):
    payload = {
        "databaseId": int(run_id),
        "workflowName": "MCU Firmware Build",
        "status": "completed",
        "conclusion": conclusion,
        "headSha": head,
        "jobs": [
            {
                "name": JOB,
                "conclusion": conclusion,
                "steps": [
                    {"name": "Checkout", "number": 1, "conclusion": "success"},
                    {"name": STEP, "number": 10, "conclusion": step_conclusion},
                ],
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


def changed_json(run_id, names):
    (CI / f"changed-{run_id}.json").write_text(
        json.dumps([{"filename": n, "sha": "0" * 40} for n in names], ensure_ascii=False),
        encoding="utf-8",
    )


def build_fixture():
    if WORK.exists():
        shutil.rmtree(WORK)
    CI.mkdir(parents=True)

    # 正例
    rid, head = RUNS["base"]
    run_json(CI / f"run-{rid}.json", rid, head, "success", "success")
    step_log(CI / f"step-{rid}.txt", PRECEDING + flat(WIRED_PASS), False)
    changed_json(rid, BASE_CHANGED)
    shutil.copyfile(
        ROOT / ".github/workflows/firmware-build.yml", CI / f"workflow-at-{head[:12]}.yml"
    )
    # 触发器反证 A（新增精确条目）与 B（既有通配）
    rid, head = RUNS["trigA"]
    run_json(CI / f"run-{rid}.json", rid, head, "success", "success")
    step_log(CI / f"step-{rid}.txt", PRECEDING + flat(WIRED_PASS), False)
    changed_json(rid, ["tests/ota/p3_1_verify_portability.py"])
    rid, head = RUNS["trigB"]
    run_json(CI / f"run-{rid}.json", rid, head, "success", "success")
    step_log(CI / f"step-{rid}.txt", PRECEDING + flat(WIRED_PASS), False)
    changed_json(rid, ["tests/ota/test_ota_device_info.py"])
    # 四次红/绿
    for index in range(4):
        rid, head = RUNS[f"red{index}"]
        run_json(CI / f"run-{rid}.json", rid, head, "failure", "failure")
        step_log(
            CI / f"step-{rid}.txt",
            PRECEDING + flat(WIRED_PASS[:index]) + WIRED_FAIL[index],
            True,
        )
        changed_json(rid, [TARGETS[index]])
        rid, head = RUNS[f"grn{index}"]
        run_json(CI / f"run-{rid}.json", rid, head, "success", "success")
        step_log(CI / f"step-{rid}.txt", PRECEDING + flat(WIRED_PASS), False)
        changed_json(rid, [TARGETS[index]])
    (CI / "pr-99.json").write_text(
        json.dumps(
            {"baseRefName": "main", "headRefName": "ota/p3-7-host-test-wiring",
             "commits": [{"oid": "c" * 40}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def make_copy(glob_run=None):
    text = SRC.read_text(encoding="utf-8")
    text = text.replace(
        'CI_DIR = ROOT / "docs" / "acceptance-contracts" / "P3-7-v1" / "ci"',
        'CI_DIR = ROOT / ".cache" / "p3-7-accept" / "selftest" / "ci"',
    )

    def pin(name, value):
        """把常量整行改写成合成值。

        收口批次回填真实 run 号后，原来的 `<NAME> = None` 字面替换已全部失配，
        导致被测副本仍指向真实 run，每个变异用例都以「证据文件缺失」变红——看似
        全红实则零鉴别力。故改成按常量名匹配整行，与其当前取值无关。
        """
        nonlocal text
        text, n = re.subn(rf"(?m)^{name} = .*$", lambda _m: f"{name} = {value}", text, count=1)
        assert n == 1, f"常量 {name} 未被改写"

    pin("BASELINE_RUN", f'"{RUNS["base"][0]}"')
    pin("TRIGGER_RUN", f'"{RUNS["trigA"][0]}"')
    pin("TRIGGER_GLOB_RUN", f'"{glob_run or RUNS["trigB"][0]}"')
    text = re.sub(
        r"DEFECT_RUNS\s*= \{[^}]*\}",
        "DEFECT_RUNS = {"
        + ", ".join(f'{i}: "{RUNS[f"red{i}"][0]}"' for i in range(4))
        + "}",
        text,
        count=1,
    )
    text = re.sub(
        r"RESTORE_RUNS\s*= \{[^}]*\}",
        "RESTORE_RUNS = {"
        + ", ".join(f'{i}: "{RUNS[f"grn{i}"][0]}"' for i in range(4))
        + "}",
        text,
        count=1,
    )
    pin("PR_NUMBER", '"99"')
    pin("HEAD_BRANCH", '"ota/p3-7-host-test-wiring"')
    for real in REAL_RUNS:
        assert real not in text, f"被测副本仍残留真实 run 号 {real}"
    assert RUNS["base"][0] in text and RUNS["grn3"][0] in text, "合成 run 号未写入副本"
    COPY.write_text(text, encoding="utf-8")


def run_under_test():
    result = subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(COPY)],
        capture_output=True, check=False, cwd=str(ROOT),
    )
    out = result.stdout.decode("utf-8", "replace")
    reds = [l[6:] for l in out.split("\n") if l.startswith("FAIL: ")]
    marker = next((l for l in out.split("\n") if l.startswith("P3_7_CI_EVIDENCE=")), "<无标记>")
    return result.returncode, reds, marker


REAL_CI_BEFORE = tree_digest(REAL_CI)
build_fixture()
make_copy()
rc, reds, marker = run_under_test()
print(f"[完整良好证据] rc={rc} {marker}")
for item in reds:
    print(f"   红: {item[:160]}")
green_ok = rc == 0 and not reds
print(f"   => 可变绿: {green_ok}")

MUTATIONS = [
    ("M1 正例缺 cmd12 的结论标记",
     lambda: step_log(CI / f"step-{RUNS['base'][0]}.txt",
                      PRECEDING + flat(WIRED_PASS[:3]), False),
     "接线结论标记缺失"),
    ("M2 无效注错选点：红运行缺前置标记（缺陷打红了既有测试，新增行从未执行）",
     lambda: step_log(CI / f"step-{RUNS['red0'][0]}.txt",
                      PRECEDING[:5] + WIRED_FAIL[0], True),
     "缺少前置标记"),
    ("M3 红运行里后续接线仍有输出（步骤未在首个失败处终止）",
     lambda: step_log(CI / f"step-{RUNS['red1'][0]}.txt",
                      PRECEDING + WIRED_PASS[0] + WIRED_FAIL[1] + WIRED_PASS[2]
                      + WIRED_PASS[3], True),
     "仍有输出"),
    ("M4 绿运行的 workflow 与当前树不一致（绿的不是最终门禁）",
     lambda: (CI / f"workflow-at-{RUNS['base'][1][:12]}.yml").write_bytes(
         b"name: something else\n"),
     "workflow 与当前树不一致"),
    ("M5 触发器反证A 提交改了不止一个文件",
     lambda: changed_json(RUNS["trigA"][0],
                          ["tests/ota/p3_1_verify_portability.py",
                           "Libraries/OTA/ota_ble_ring.h"]),
     "不是恰好一个"),
    ("M6 红运行元数据谎报为 success",
     lambda: run_json(CI / f"run-{RUNS['red2'][0]}.json", RUNS["red2"][0], RUNS["red2"][1],
                      "success", "success"),
     "结论不是 failure"),
    ("M7 cmd12 红运行里 _ALL=PASS 仍在（缺陷未被该行捕获）",
     lambda: step_log(CI / f"step-{RUNS['red3'][0]}.txt",
                      PRECEDING + flat(WIRED_PASS[:3]) + WIRED_FAIL[3]
                      + ["P3_2_OTA_DEVICE_INFO_ALL=PASS"], True),
     "仍报通过标记"),
    ("M8 还原绿运行的提交改的不是注错目标（红绿因果无法归属）",
     lambda: changed_json(RUNS["grn2"][0], ["docs/ota-exec-notes/P3-7-wiring-evidence.md"]),
     "不是恰为注错目标"),
    ("M9 触发器反证B 复用正例的 run（同一 run 充当多条腿）",
     lambda: None,
     "存在复用"),
    ("M10 正例提交触碰了产品红线目录",
     lambda: changed_json(RUNS["base"][0], BASE_CHANGED + ["Libraries/OTA/ota_ble_frame.h"]),
     "触碰了产品红线目录"),
    ("M11 触发器反证B 改的是新增精确条目脚本（未证明既有通配覆盖）",
     lambda: changed_json(RUNS["trigB"][0], ["tests/ota/p3_1_verify_portability.py"]),
     "不是恰好一个"),
]

summary = []
for label, mutate, keyword in MUTATIONS:
    build_fixture()
    mutate()
    make_copy(glob_run=RUNS["base"][0] if label.startswith("M9 ") else None)
    rc_bad, reds_bad, marker_bad = run_under_test()
    hit = any(keyword in r for r in reds_bad)
    print(f"\n[{label}] rc={rc_bad} {marker_bad}")
    for item in reds_bad[:4]:
        print(f"   红: {item[:150]}")
    print(f"   关键词 {keyword!r} 命中: {hit}")
    summary.append((label, rc_bad == 1 and hit))

shutil.rmtree(WORK)
COPY.unlink()
assert not WORK.exists() and not COPY.exists(), "自检临时件未清理"
assert tree_digest(REAL_CI) == REAL_CI_BEFORE, "真实证据目录被自检改动"
print(f"\n真实证据目录逐字节未变: {REAL_CI_BEFORE[:24]}")

print("\n=== 双向鉴别力汇总 ===")
ok = green_ok and all(passed for _, passed in summary)
print(f"{'OK' if green_ok else 'BAD'} 完整良好证据可变绿")
for label, passed in summary:
    print(f"{'OK' if passed else 'BAD'} {label}")
print(f"P3_7_CI_HARNESS_SELFTEST={'PASS' if ok else 'FAIL'} mutations={len(summary)}")
sys.exit(0 if ok else 1)
