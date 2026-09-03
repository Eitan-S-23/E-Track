"""P3-7 CI 证据采集：把一次 run 的元数据、步骤日志与改动文件清单落到证据目录。

用法: python -X utf8 -B .cache/p3-7-accept/collect_run.py <run_id> [--workflow]
`--workflow` 额外冻结该 run headSha 处的 workflow blob（仅正例 run 需要）。

只读远端，不改工作树；产物一律写入 docs/acceptance-contracts/P3-7-v1/ci/。
"""

import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path("D:/github/my/E-Track")
CI = ROOT / "docs" / "acceptance-contracts" / "P3-7-v1" / "ci"
STEP_NAME = "Run host tests (boot vectors, OTA host tests, P3-1 product regressions)"
WF_PATH = ".github/workflows/firmware-build.yml"


def gh(args, binary=False):
    r = subprocess.run(["gh", *args], capture_output=True, cwd=str(ROOT))
    if r.returncode != 0:
        raise SystemExit(f"gh {' '.join(args)} 失败 rc={r.returncode}: {r.stderr.decode('utf-8','replace')[:400]}")
    return r.stdout if binary else r.stdout.decode("utf-8", "replace")


def write(path, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    path.write_bytes(data)
    print(f"  写入 {path.relative_to(ROOT).as_posix()} len={len(data)} sha256={hashlib.sha256(data).hexdigest().upper()[:24]}")


def main():
    run_id = sys.argv[1]
    want_wf = "--workflow" in sys.argv[2:]
    CI.mkdir(parents=True, exist_ok=True)

    meta = gh([
        "run", "view", run_id, "--json",
        "databaseId,workflowName,name,displayTitle,event,status,conclusion,"
        "headSha,headBranch,createdAt,updatedAt,jobs",
    ])
    obj = json.loads(meta)
    head = obj["headSha"]
    write(CI / f"run-{run_id}.json", json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

    log = gh(["run", "view", run_id, "--log"])
    prefix = None
    lines = []
    for raw in log.split("\n"):
        parts = raw.split("\t", 2)
        if len(parts) == 3 and parts[1] == STEP_NAME:
            prefix = parts[0]
            lines.append(raw.rstrip("\r"))
    if not lines:
        raise SystemExit(f"run {run_id} 中未找到步骤日志：{STEP_NAME}")
    write(CI / f"step-{run_id}.txt", "\n".join(lines) + "\n")
    print(f"  步骤日志 job={prefix!r} 行数={len(lines)}")

    files = json.loads(gh(["api", f"repos/:owner/:repo/commits/{head}", "--jq", "[.files[] | {filename, sha}]"]))
    write(CI / f"changed-{run_id}.json", json.dumps(files, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"  改动文件 {len(files)} 个: {[f['filename'] for f in files]}")

    if want_wf:
        blob = gh(["api", f"repos/:owner/:repo/contents/{WF_PATH}?ref={head}",
                   "-H", "Accept: application/vnd.github.raw"], binary=True)
        write(CI / f"workflow-at-{head[:12]}.yml", blob)
        local = (ROOT / WF_PATH).read_bytes()
        print(f"  与工作树字节一致: {blob == local}")


if __name__ == "__main__":
    main()
