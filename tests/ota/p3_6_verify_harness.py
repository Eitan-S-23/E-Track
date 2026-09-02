#!/usr/bin/env python3
"""P3-6 独立验收：三个核验脚本自身的鉴别力（fail-closed）证明。

`docs/acceptance-execution-contract.md` 要求 harness 必须 fail-closed，不得存在
常量 PASS 或「没有报错就算过」的路径。本脚本在 `.cache` 下的沙箱影子树里，对
`p3_6_verify_ci_wiring.py`、`p3_6_verify_ci_evidence.py`、`p3_6_verify_scope.py`
的输入逐项注入单点缺陷，断言每种缺陷都必须让对应脚本非零退出；同时先跑一遍
未注错的对照沙箱，断言其为 PASS，以排除「脚本恒失败」这种伪鉴别力。

沙箱只写仓库内已忽略目录 `.cache/p36-accept/mutation/`，不触碰工作区任何被
跟踪文件；接线与范围脚本所需的 git 前提在沙箱内用一次性 `git init` 重建。
"""

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SANDBOX_ROOT = ROOT / ".cache" / "p36-accept" / "mutation"
WORKFLOW_REL = ".github/workflows/firmware-build.yml"
CI_REL = "docs/acceptance-contracts/P3-6-v1/ci"
WIRING_SCRIPT = "p3_6_verify_ci_wiring.py"
EVIDENCE_SCRIPT = "p3_6_verify_ci_evidence.py"
SCOPE_SCRIPT = "p3_6_verify_scope.py"

CI_FILES = (
    "run-33620407886.json",
    "run-33621049995.json",
    "run-33621403637.json",
    "run-33621050015.json",
    "runs-branch.json",
    "pr-14.json",
    "step-33620407886.txt",
    "step-33621049995.txt",
    "step-33621403637.txt",
)

# 范围沙箱所需的最小骨架：产品源、被接线的四个测试、真实的 7 个已提交授权路径、
# 6 个刻意保持未跟踪的预存文件。内容无关，只有路径与跟踪状态参与判定。
PRODUCT_SOURCE_REL = "Libraries/OTA/ota_ble_frame.c"
BLE_TEST_RELS = (
    "tests/ota/test_ota_ble_frame.py",
    "tests/ota/test_ota_ble_frame.c",
    "tests/ota/test_ota_ble_session.py",
    "tests/ota/test_ota_ble_session.c",
)
AUTHORIZED_COMMITTED = (
    ".gitattributes",
    WORKFLOW_REL,
    "PLAN-OTA-EXEC.md",
    "docs/ota-exec-notes/P3-6-ci-wiring-evidence.md",
    "docs/ota-exec-notes/P3-6-governance-change.md",
    "docs/ota-prompts/prompt-P3-6-implementation.md",
    "tests/ota/test_acceptance_bundle.py",
)
PREEXISTING_UNTRACKED = (
    ".cache-cmake-time-test.cmake",
    ".claude/cc_recover_s4.js",
    ".claude/ccprobe_hash.js",
    ".claude/ccprobe_plan.js",
    ".claude/write_r5_phase0_board.py",
    ".claude/write_r5_ruling_board.py",
)

# 每个注错用例必须因「预期的那条判据」而红。只断言退出码非零，会放过「因别的
# 原因偶然红了」这种伪鉴别力，故逐例绑定失败文案。
EXPECTED_REASONS = {
    "wiring/drop-session-line": "缺少接线命令：python3 tests/ota/test_ota_ble_session.py",
    "wiring/swallow-exit-code": "削弱写法 '|| true'",
    "wiring/drop-pipefail": "步骤首行必须是 set -euo pipefail",
    "wiring/continue-on-error": "接线步骤带 continue-on-error",
    "wiring/trigger-tampered": "触发器段相对基点发生改动",
    "evidence/red-log-replaced-by-green": "缺少帧层失败汇总行",
    "evidence/defect-run-marked-success": "run 33621049995 结论不是 failure",
    "evidence/baseline-session-marker-removed": "run 33620407886 缺少会话层标记",
    "evidence/governance-contrast-red": "注错提交上的治理运行不是 success",
    "evidence/red-run-session-executed": "出现会话层输出，说明步骤未在首个失败处终止",
    "scope/unauthorized-committed": "已提交层出现未授权路径：docs/ota-exec-notes/OTHER-CARD-note.md",
    "scope/red-line-committed": "红线路径在已提交层有改动：Tools/",
    "scope/product-source-tampered": "注错未完全还原",
    "scope/preexisting-file-tracked": "预存未跟踪文件状态改变：.claude/ccprobe_hash.js",
    "scope/ble-test-missing-on-main": "被接线的测试文件未在 main 上被跟踪：tests/ota/test_ota_ble_session.py",
}

failures = []
checks = 0


def check(condition, message):
    global checks
    checks += 1
    if condition is not True:
        failures.append(message)


def _on_remove_error(func, path, exc):
    """git 对象在 Windows 上是只读的，删除前先放开写权限。"""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def remove_tree(path):
    if not path.exists():
        return
    try:
        shutil.rmtree(path, onexc=_on_remove_error)
    except TypeError:  # Python < 3.12 只有 onerror
        shutil.rmtree(path, onerror=lambda func, p, exc: _on_remove_error(func, p, exc[1]))


def run_script(sandbox, script_name):
    """在沙箱内以子进程执行核验脚本，返回 (退出码, 合并输出)。"""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-B", str(sandbox / "tests" / "ota" / script_name)],
        capture_output=True,
        check=False,
        cwd=str(sandbox),
        env=env,
    )
    output = result.stdout.decode("utf-8", "replace") + result.stderr.decode("utf-8", "replace")
    return result.returncode, output


def git(sandbox, *args):
    return subprocess.run(
        ["git", "-C", str(sandbox), *args],
        capture_output=True,
        check=True,
    )


def make_wiring_sandbox(name):
    """建沙箱：main 上是基线 workflow，工作区是当前 workflow。"""
    sandbox = SANDBOX_ROOT / f"wiring-{name}"
    remove_tree(sandbox)
    (sandbox / ".github" / "workflows").mkdir(parents=True)
    (sandbox / "tests" / "ota").mkdir(parents=True)
    shutil.copy2(ROOT / "tests" / "ota" / WIRING_SCRIPT, sandbox / "tests" / "ota" / WIRING_SCRIPT)

    base = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "HEAD", "main"],
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8").strip()
    base_bytes = subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{base}:{WORKFLOW_REL}"],
        capture_output=True,
        check=True,
    ).stdout

    target = sandbox / WORKFLOW_REL
    target.write_bytes(base_bytes)
    git(sandbox, "init", "--initial-branch=main", "--quiet")
    git(sandbox, "config", "user.email", "acceptance@local")
    git(sandbox, "config", "user.name", "acceptance")
    git(sandbox, "add", "--all")
    git(sandbox, "commit", "--quiet", "-m", "base")
    # 工作区放当前版本，使脚本的 diff 判定与真实仓库同构。
    target.write_bytes((ROOT / WORKFLOW_REL).read_bytes())
    return sandbox


def make_evidence_sandbox(name):
    sandbox = SANDBOX_ROOT / f"evidence-{name}"
    remove_tree(sandbox)
    (sandbox / "tests" / "ota").mkdir(parents=True)
    (sandbox / CI_REL).mkdir(parents=True)
    shutil.copy2(ROOT / "tests" / "ota" / EVIDENCE_SCRIPT, sandbox / "tests" / "ota" / EVIDENCE_SCRIPT)
    for item in CI_FILES:
        shutil.copy2(ROOT / CI_REL / item, sandbox / CI_REL / item)
    return sandbox


def make_scope_sandbox(
    name,
    extra_committed=(),
    omit_from_main=(),
    track_at_main=(),
    tamper_product=False,
):
    """建沙箱：main 为基线，特性分支带 7 个授权提交改动，工作区带授权脏改动。

    沙箱内显式关掉 `core.autocrlf`，把行尾变量从鉴别力实验中剔除；真实仓库的
    行尾策略由 `.gitattributes` 与 manifest 校验器另行把关。
    """
    sandbox = SANDBOX_ROOT / f"scope-{name}"
    remove_tree(sandbox)
    sandbox.mkdir(parents=True)

    def put(rel, data=b"placeholder\n"):
        path = sandbox / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    # main 基线：真实产品源字节（供哈希与逐字节比对）+ 被接线的四个测试。
    product = put(PRODUCT_SOURCE_REL, (ROOT / PRODUCT_SOURCE_REL).read_bytes())
    for rel in BLE_TEST_RELS:
        if rel not in omit_from_main:
            put(rel)
    for rel in track_at_main:
        put(rel)
    git(sandbox, "init", "--initial-branch=main", "--quiet")
    git(sandbox, "config", "user.email", "acceptance@local")
    git(sandbox, "config", "user.name", "acceptance")
    git(sandbox, "config", "core.autocrlf", "false")
    git(sandbox, "add", "--all")
    git(sandbox, "commit", "--quiet", "-m", "main baseline")

    # 特性分支：提交授权路径（可注入越权路径）。
    git(sandbox, "checkout", "--quiet", "-b", "ota/p3-6-ci-wiring")
    for rel in AUTHORIZED_COMMITTED:
        put(rel, b"authorized\n")
    for rel in extra_committed:
        put(rel, b"injected\n")
    git(sandbox, "add", "--all")
    git(sandbox, "commit", "--quiet", "-m", "authorized changes")

    # 工作区层：核验脚本自身未跟踪、授权脏改动、预存未跟踪文件。
    (sandbox / "tests" / "ota").mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tests" / "ota" / SCOPE_SCRIPT, sandbox / "tests" / "ota" / SCOPE_SCRIPT)
    put(".gitattributes", b"authorized\n/dirty -text\n")
    for rel in PREEXISTING_UNTRACKED:
        if rel not in track_at_main:
            put(rel)
    if tamper_product:
        product.write_bytes(product.read_bytes() + b"/* injected */\n")
    return sandbox


def mutate_bytes(path, old, new, expected_hits=1):
    raw = path.read_bytes()
    hits = raw.count(old)
    if hits != expected_hits:
        failures.append(f"注错锚点命中数不符（期望 {expected_hits} 实得 {hits}）：{path.name} {old[:40]!r}")
        return False
    path.write_bytes(raw.replace(old, new))
    return True


def mutate_run_conclusion(path, value):
    """只改 run 顶层 conclusion，保持 job/step 层不动（单点缺陷）。"""
    data = json.loads(path.read_bytes().decode("utf-8"))
    if "conclusion" not in data:
        failures.append(f"注错目标缺少 conclusion 字段：{path.name}")
        return False
    data["conclusion"] = value
    path.write_bytes(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    return True


def expect_fail(sandbox, script_name, case):
    code, output = run_script(sandbox, script_name)
    marker_fail = "=FAIL " in output
    reason = EXPECTED_REASONS.get(case)
    check(code != 0, f"{case}：注错后仍以 0 退出，鉴别力不成立")
    check(marker_fail, f"{case}：注错后结论行未标记 FAIL")
    check(reason is not None, f"{case}：未登记预期失败判据")
    # 只在 `FAIL:` 行内匹配，避免被脚本的进度输出误命中。
    reason_hit = reason is not None and any(
        line.startswith("FAIL: ") and reason in line
        for line in output.replace("\r\n", "\n").split("\n")
    )
    check(reason_hit, f"{case}：未因预期判据而红（期望 {reason!r}）")
    print(f"  {case}: exit={code} marker_fail={marker_fail} reason_hit={reason_hit}")


def wiring_case(name, mutator):
    sandbox = make_wiring_sandbox(name)
    if mutator(sandbox / WORKFLOW_REL) is not False:
        expect_fail(sandbox, WIRING_SCRIPT, f"wiring/{name}")


def evidence_case(name, mutator):
    sandbox = make_evidence_sandbox(name)
    if mutator(sandbox / CI_REL) is not False:
        expect_fail(sandbox, EVIDENCE_SCRIPT, f"evidence/{name}")


def scope_case(name, **kwargs):
    sandbox = make_scope_sandbox(name, **kwargs)
    expect_fail(sandbox, SCOPE_SCRIPT, f"scope/{name}")


def main():
    SANDBOX_ROOT.mkdir(parents=True, exist_ok=True)

    # 对照组：未注错的沙箱必须 PASS，否则后续「注错即红」毫无意义。
    print("对照组（未注错）：")
    control_wiring = make_wiring_sandbox("control")
    code, output = run_script(control_wiring, WIRING_SCRIPT)
    check(code == 0, f"wiring 对照沙箱未通过（exit={code}）：{output[-400:]}")
    check("P3_6_CI_WIRING=PASS" in output, "wiring 对照沙箱结论行不是 PASS")
    print(f"  wiring/control: exit={code}")

    control_evidence = make_evidence_sandbox("control")
    code, output = run_script(control_evidence, EVIDENCE_SCRIPT)
    check(code == 0, f"evidence 对照沙箱未通过（exit={code}）：{output[-400:]}")
    check("P3_6_CI_EVIDENCE=PASS" in output, "evidence 对照沙箱结论行不是 PASS")
    print(f"  evidence/control: exit={code}")

    control_scope = make_scope_sandbox("control")
    code, output = run_script(control_scope, SCOPE_SCRIPT)
    check(code == 0, f"scope 对照沙箱未通过（exit={code}）：{output[-400:]}")
    check("P3_6_SCOPE=PASS" in output, "scope 对照沙箱结论行不是 PASS")
    print(f"  scope/control: exit={code}")

    print("接线脚本注错组：")
    # 1. 删掉会话层接线行 -> 接线不完整必须被抓到。
    wiring_case(
        "drop-session-line",
        lambda p: mutate_bytes(p, b"          python3 tests/ota/test_ota_ble_session.py\n", b""),
    )
    # 2. 用 `|| true` 吞掉失败 -> fail-closed 被削弱必须被抓到。
    wiring_case(
        "swallow-exit-code",
        lambda p: mutate_bytes(
            p,
            b"python3 tests/ota/test_ota_ble_frame.py\n",
            b"python3 tests/ota/test_ota_ble_frame.py || true\n",
        ),
    )
    # 3. 去掉步骤内的 shell 守卫 -> 首个失败不再终止步骤。
    wiring_case(
        "drop-pipefail",
        lambda p: mutate_bytes(
            p,
            b"        run: |\n          set -euo pipefail\n"
            b"          python3 tests/boot/test_fw_header_vectors.py\n",
            b"        run: |\n          python3 tests/boot/test_fw_header_vectors.py\n",
        ),
    )
    # 4. 给步骤挂 continue-on-error -> 步骤失败不再让 job 变红。
    wiring_case(
        "continue-on-error",
        lambda p: mutate_bytes(
            p,
            b"      - name: Test Boot fw_header validator vectors\n",
            b"      - name: Test Boot fw_header validator vectors\n        continue-on-error: true\n",
        ),
    )
    # 5. 改动触发器 -> 接线可能永不触发。
    wiring_case(
        "trigger-tampered",
        lambda p: mutate_bytes(p, b'      - "Libraries/**"\n', b"", expected_hits=2),
    )

    print("证据脚本注错组：")
    # 6. 用绿日志冒充红运行 -> 反证造假必须被抓到。
    def swap_red_log(ci_dir):
        shutil.copy2(ci_dir / "step-33620407886.txt", ci_dir / "step-33621049995.txt")
        return True

    evidence_case("red-log-replaced-by-green", swap_red_log)

    # 7. 把注错运行的顶层结论篡改为 success -> 元数据与日志不一致必须被抓到。
    evidence_case(
        "defect-run-marked-success",
        lambda ci: mutate_run_conclusion(ci / "run-33621049995.json", "success"),
    )
    # 8. 改掉基线绿日志里的会话层校验点计数 -> 「计数与 P3-1 基线一致」不再成立。
    evidence_case(
        "baseline-session-marker-removed",
        lambda ci: mutate_bytes(
            ci / "step-33620407886.txt",
            b"P3_1_BLE_SESSION=PASS checks=105 failures=0",
            b"P3_1_BLE_SESSION=PASS checks=104 failures=0",
        ),
    )
    # 9. 让治理对比运行变红 -> 鉴别力归属论证不再成立。
    evidence_case(
        "governance-contrast-red",
        lambda ci: mutate_run_conclusion(ci / "run-33621050015.json", "failure"),
    )
    # 10. 让红运行出现会话层输出 -> set -euo pipefail 短路语义不再成立。
    evidence_case(
        "red-run-session-executed",
        lambda ci: mutate_bytes(
            ci / "step-33621049995.txt",
            b"2026-09-02T10:45:57.3759040Z ##[error]Process completed with exit code 1.",
            b"2026-09-02T10:45:57.3759000Z P3_1_BLE_SESSION=PASS checks=105 failures=0\n"
            b"Build firmware (arm-none-eabi-gcc)\tTest Boot fw_header validator vectors\t"
            b"2026-09-02T10:45:57.3759040Z ##[error]Process completed with exit code 1.",
        ),
    )

    print("范围脚本注错组：")
    # 11. 提交层混入白名单外的路径 -> 越权改动必须被抓到（该路径不在红线内，
    #     因此本例单独证明白名单本身有牙齿，而不是靠红线兜底）。
    scope_case("unauthorized-committed", extra_committed=("docs/ota-exec-notes/OTHER-CARD-note.md",))
    # 12. 提交层碰红线目录 -> 生产红线必须被抓到。
    scope_case("red-line-committed", extra_committed=("Tools/injected_helper.py",))
    # 13. 工作区篡改被接线的产品源 -> 「注错已逐字节还原」不再成立。
    scope_case("product-source-tampered", tamper_product=True)
    # 14. 预存未跟踪文件变成被跟踪 -> 刻意排除的文件被悄悄入库必须被抓到。
    scope_case("preexisting-file-tracked", track_at_main=(".claude/ccprobe_hash.js",))
    # 15. main 上缺少被接线的测试 -> 接线的前置依赖不成立必须被抓到。
    scope_case("ble-test-missing-on-main", omit_from_main=("tests/ota/test_ota_ble_session.py",))

    print(f"=== 失败项 {len(failures)} / 核对项 {checks} ===")
    for item in failures:
        print(f"FAIL: {item}")
    status = "PASS" if not failures else "FAIL"
    print(f"P3_6_HARNESS_DISCRIMINATION={status} checks={checks} failures={len(failures)}")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
