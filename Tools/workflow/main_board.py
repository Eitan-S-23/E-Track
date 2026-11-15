"""Read-only authoritative-board discovery. Never fetch, switch, or edit files."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def git(cwd, *arguments):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(key, None)
    result = subprocess.run(
        ["git", "-c", "safe.directory=" + Path(cwd).as_posix(),
         "-c", "core.fsmonitor=false", "--no-optional-locks", *arguments],
        cwd=cwd, env=env, capture_output=True, timeout=30, check=False,
    )
    if result.returncode:
        # Git errors can contain credential-bearing remote URLs. Do not echo them.
        raise RuntimeError("Git query failed: " + arguments[0])
    return result.stdout.decode("utf-8", errors="strict").strip()


def parse_worktrees(raw):
    records = []
    current = {}
    for field in raw.split("\0"):
        if not field:
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = field.partition(" ")
        current[key] = value
    if current:
        records.append(current)
    return records


def fresh_main(cwd):
    remote = git(cwd, "remote", "get-url", "origin")
    if not re.fullmatch(r"https://github\.com/Eitan-S-23/E-Track(?:\.git)?", remote, re.I):
        raise RuntimeError("Unrecognized remote; refusing automatic authentication or SSH writes")
    value = git(cwd, "-c", "credential.helper=", "-c", "core.askPass=",
                "ls-remote", "--exit-code", "origin", "refs/heads/main")
    match = re.fullmatch(r"([0-9a-f]{40})\s+refs/heads/main", value)
    if not match:
        raise RuntimeError("Remote main response is invalid")
    return match.group(1)


def reject_redirected(path):
    path = Path(path).absolute()
    for candidate in (path, *path.parents):
        if not candidate.exists():
            continue
        stat = candidate.lstat()
        if candidate.is_symlink() or getattr(stat, "st_file_attributes", 0) & 0x400:
            raise RuntimeError("Redirected authoritative entry")
    return path.resolve(strict=True)


def inspect(repo_root, remote_reader=fresh_main):
    caller = Path(repo_root).resolve(strict=True)
    common = Path(git(caller, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    if common.name != ".git":
        raise RuntimeError("Expected a non-bare primary checkout with a .git directory")
    primary = reject_redirected(common.parent)
    worktrees = parse_worktrees(git(caller, "worktree", "list", "--porcelain", "-z"))
    mains = [item for item in worktrees if item.get("branch") == "refs/heads/main"]
    report = {
        "ok": False, "caller": str(caller), "primaryRoot": str(primary),
        "callerBranch": git(caller, "branch", "--show-current") or "DETACHED",
        "callerHead": git(caller, "rev-parse", "HEAD"), "errors": [],
        "remoteVerified": False, "delivery": "UNVERIFIED",
    }
    if len(mains) != 1:
        report["errors"].append("MAIN_WORKTREE_MISSING_OR_AMBIGUOUS")
        return report
    main_root = reject_redirected(mains[0]["worktree"])
    report["mainRoot"] = str(main_root)
    report["localMain"] = mains[0]["HEAD"]
    if main_root != primary:
        report["errors"].append("MAIN_NOT_AT_PRIMARY_ROOT")
    board = reject_redirected(main_root / "PLAN-OTA-EXEC.md")
    report["board"] = str(board)
    report["boardSha256"] = hashlib.sha256(board.read_bytes()).hexdigest()
    report["localBoardPending"] = bool(git(main_root, "status", "--porcelain=v1",
                                          "--untracked-files=no", "--", "PLAN-OTA-EXEC.md"))
    try:
        remote = remote_reader(caller)
        if not re.fullmatch(r"[0-9a-f]{40}", remote):
            raise RuntimeError("Invalid remote revision")
        report["remoteMain"] = remote
        report["remoteVerified"] = True
        if remote != report["localMain"]:
            report["errors"].append("LOCAL_MAIN_NOT_CURRENT")
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        report["errors"].append("REMOTE_MAIN_UNVERIFIED")
        report["remoteFailureType"] = type(error).__name__
    report["ok"] = not report["errors"]
    if report["ok"]:
        report["delivery"] = "LOCAL_PENDING" if report["localBoardPending"] else "MAIN_MATCHED"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True)
    args = parser.parse_args()
    try:
        result = inspect(args.repo_root)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        result = {"ok": False, "errors": ["ENTRY_CHECK_FAILED"], "failureType": type(error).__name__}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
