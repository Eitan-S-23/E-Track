"""P3-2 独立验收核验：改动范围、红线路径与 CI fail-closed 语义。

三层核验：
  A 段 —— 枚举本轮全部改动（已提交层 merge-base..HEAD + 工作区层 vs HEAD，
          含未跟踪文件），逐条归入「P3-2 卡内 / P3-7 立卡批次 / 本轮验收产出 /
          既有残留」四类；出现无法归类的路径即失败。
  B 段 —— 红线路径必须与 HEAD 逐字节一致（boot、P3-1 BLE 资产、其他 OTA 模块、
          冻结契约文档、打包工具、CI workflow、冻结测试向量）。
  C 段 —— CI 与验收门禁未被削弱（无 fail-open 逃生模式），且本轮验收脚本自身
          不写入任何产品源（验收方不得兼任实现方）。

fail-closed：任一断言失败即非零退出；未跟踪文件聚合为单一检查项，使检查总数
在不同轮次间保持不变。
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

TIER_P3_2_CARD = (
    r"^Libraries/OTA/ota_device_info\.(c|h)$",
    r"^USER/HAL/HAL_Bluetooth\.cpp$",
    r"^MDK-ARM_F435/cmake-generated/CMakeLists\.txt$",
    r"^MDK-ARM_F435/proj\.uvprojx$",
    r"^tests/ota/test_ota_device_info\.(c|py)$",
    r"^docs/ota-exec-notes/P3-2-(identity-research|implementation-evidence)\.md$",
)

TIER_P3_7_BATCH = (
    r"^docs/ota-prompts/prompt-P3-7-implementation\.md$",
    r"^docs/ota-exec-notes/P3-7-card-creation\.md$",
    r"^tests/ota/test_acceptance_bundle\.py$",
)

TIER_ACCEPTANCE = (
    r"^tests/ota/p3_2_verify_[a-z_]+\.py$",
    r"^docs/acceptance-contracts/P3-2-v1\.contract\.json$",
    r"^docs/acceptance-contracts/P3-2-v1/",
    r"^docs/ota-exec-notes/P3-2-acceptance-.*\.md$",
    r"^\.claude/verification-report-p3-2\.md$",
    r"^\.claude/write_p3_2_acceptance_board\.py$",
)

# 看板与行尾护栏由「立卡批次 + 本轮验收回写」共同持有
TIER_SHARED = (
    r"^PLAN-OTA-EXEC\.md$",
    r"^\.gitattributes$",
)

PREEXISTING_UNTRACKED = (
    ".cache-cmake-time-test.cmake",
    ".claude/cc_recover_s4.js",
    ".claude/ccprobe_hash.js",
    ".claude/ccprobe_plan.js",
    ".claude/write_r5_phase0_board.py",
    ".claude/write_r5_ruling_board.py",
)

RED_LINE_PATHSPECS = (
    r"^boot/",
    r"^Libraries/OTA/ota_ble_",
    r"^Libraries/OTA/ota_(staging|confirm|confirm_health|backup|package|patch|sd|"
    r"keys|slot_header|vtor_check)\.",
    r"^PLAN-OTA\.md$",
    r"^docs/ota-binary-contracts\.md$",
    r"^docs/ota-cross-system-contracts\.md$",
    r"^docs/acceptance-execution-contract\.md$",
    r"^Tools/etu_pack\.py$",
    r"^Tools/acceptance/",
    r"^Tools/provenance/",
    r"^\.github/workflows/",
    r"^tests/ota-vectors/",
)

FAIL_OPEN = (
    r"\|\|\s*true\b",
    r"\|\|\s*:\s*$",
    r"continue-on-error:\s*true",
    r"set\s+\+e",
    r"if:\s*always\(\)",
    r"^\s*exit\s+0\s*$",
)

WORKFLOWS = (
    ".github/workflows/firmware-build.yml",
    ".github/workflows/acceptance-governance.yml",
)

ACCEPTANCE_SCRIPTS = (
    "tests/ota/p3_2_verify_realdevice.py",
    "tests/ota/p3_2_verify_harness.py",
    "tests/ota/p3_2_verify_scope.py",
)

WRITE_CALLS = (r"write_bytes\(", r"write_text\(", r"\.unlink\(", r"open\([^)]*['\"][wa]")

failures = []
checks = 0


def ck(cond, label, got=None, want=None):
    global checks
    checks += 1
    if cond:
        print(f"  ok   {label}" + (f" = {got!r}" if got is not None else ""))
    else:
        failures.append(f"{label}: got={got!r} want={want!r}")
        print(f"  FAIL {label}: got={got!r} want={want!r}")


def git(*args):
    p = subprocess.run(["git", "-C", str(ROOT), *args],
                       capture_output=True, text=True, errors="replace")
    if p.returncode != 0:
        raise SystemExit(f"P3_2_SCOPE=FAIL git {' '.join(args)} -> {p.returncode}\n{p.stderr}")
    return p.stdout


def classify(path):
    for name, pats in (("P3-2", TIER_P3_2_CARD), ("P3-7", TIER_P3_7_BATCH),
                       ("验收", TIER_ACCEPTANCE), ("共有", TIER_SHARED)):
        if any(re.search(pat, path) for pat in pats):
            return name
    return None


print("== A. 改动范围归类 ==")
base = git("merge-base", "HEAD", "origin/main").strip()
committed = [l for l in git("diff", "--name-only", f"{base}..HEAD").splitlines() if l]
ck(committed == [], "本卡未产生已提交改动（实现 agent 不 commit，§0 规则 8）",
   len(committed), 0)

tracked = sorted(set(
    [l for l in git("diff", "--name-only", "HEAD").splitlines() if l]
    + [l for l in git("diff", "--cached", "--name-only").splitlines() if l]
))
untracked = sorted(l for l in git("ls-files", "-o", "--exclude-standard").splitlines() if l)

buckets = {"P3-2": [], "P3-7": [], "验收": [], "共有": []}
unclassified = []
for path in tracked + untracked:
    if path in PREEXISTING_UNTRACKED:
        continue
    tier = classify(path)
    if tier is None:
        unclassified.append(path)
    else:
        buckets[tier].append(path)

for tier, items in buckets.items():
    print(f"  [{tier}] {len(items)} 项: " + ", ".join(items[:4])
          + (" ..." if len(items) > 4 else ""))
ck(not unclassified, "全部改动均可归入既定层级（无越界文件）", unclassified, [])
ck(len(buckets["P3-2"]) == 9,
   "P3-2 卡内改动 9 项（2 身份链源 + 1 HAL + 2 构建注册 + 2 测试 + 2 笔记）",
   len(buckets["P3-2"]), 9)

stray = [p for p in untracked if p not in PREEXISTING_UNTRACKED
         and classify(p) is None]
ck(not stray, "未跟踪文件全部已知（既有残留或本轮产出聚合核验）", stray, [])

print("== B. 红线路径与 HEAD 逐字节一致 ==")
for pat in RED_LINE_PATHSPECS:
    hits = [p for p in tracked + untracked if re.search(pat, p)]
    ck(not hits, f"红线未被改动 /{pat}/", hits, [])

print("== C. 门禁未被削弱、验收方未兼任实现方 ==")
for wf in WORKFLOWS:
    text = (ROOT / wf).read_text(encoding="utf-8")
    hits = [pat for pat in FAIL_OPEN if re.search(pat, text, re.M)]
    ck(not hits, f"{wf} 无 fail-open 逃生模式", hits, [])

for script in ACCEPTANCE_SCRIPTS:
    text = (ROOT / script).read_text(encoding="utf-8")
    hits = [pat for pat in WRITE_CALLS if re.search(pat, text)]
    ck(not hits, f"{script} 为纯只读核验（无任何写入调用）", hits, [])

# 构建段脚本需要落地 finalize 复算产物，唯一允许的输出必须在忽略的 .cache 下
build_text = (ROOT / "tests/ota/p3_2_verify_build.py").read_text(encoding="utf-8")
ck('OUT = ROOT / ".cache"' in build_text,
   "p3_2_verify_build.py 的唯一输出根为 .cache（不落产品目录）", True, True)
ck(not re.search(r"(write_bytes|write_text)\(", build_text),
   "p3_2_verify_build.py 不直接写文件（仅由 etu_pack 输出到 .cache）", True, True)

print()
print(f"P3_2_SCOPE checks={checks} failures={len(failures)}")
print(f"tracked={len(tracked)} untracked_new={len(untracked) - len(PREEXISTING_UNTRACKED)} "
      f"card={len(buckets['P3-2'])} governance={len(buckets['P3-7'])} "
      f"acceptance={len(buckets['验收'])} shared={len(buckets['共有'])}")
if failures:
    print("P3_2_SCOPE=FAIL")
    raise SystemExit(1)
print("P3_2_SCOPE=PASS")
