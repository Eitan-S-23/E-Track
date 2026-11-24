"""Save the authorized measured half-erase checkpoint with a private Git index."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_half_erase_review as review

cli = review.cli
OUT = review.AREA / "checkpoint-001"
BASE = "10fa716fffc80bfef690769c1712c9cd2861e2c3"
REF = "refs/heads/checkpoint/p34-half-erase-20261003"
FILES = [
    "Tools/ota/p34_half_erase.h", "Tools/ota/p34_half_erase.patch",
    "Tools/ota/p34_half_erase_candidate.py", "Tools/ota/p34_half_erase_tests.py",
    "Tools/ota/p34_half_erase_assets.py", "Tools/ota/p34_half_erase_trial.py",
    "Tools/ota/p34_half_erase_review.py", "Tools/ota/p34_half_erase_checkpoint.py",
    "tests/ota/test_p34_half_erase_plan.c", "tests/ota/test_p34_half_erase_backup.c",
    "tests/ota/p34_half_erase_hal.cpp", "tests/ota/test_p34_half_erase_trial.py",
    "tests/ota/test_p34_half_erase_review.py", "docs/ota-exec-notes/P3-4-fixed-signing-2026-10-01.md",
]


def readgit(*args):
    result = subprocess.run(["git", "--no-optional-locks", *args], cwd=ROOT,
                            capture_output=True, timeout=60, check=True)
    return result.stdout.decode().strip()


def main(save):
    s = cli.Store(ROOT)
    cli.require(not OUT.exists(), "preserve previous checkpoint attempt")
    cli.require(Path(readgit("rev-parse", "--show-toplevel")).resolve() == ROOT and
                Path(readgit("rev-parse", "--absolute-git-dir")).resolve() == ROOT / ".git",
                "unexpected repository or Git output root")
    head, index = readgit("rev-parse", "HEAD"), cli.record(ROOT / ".git/index")
    cli.require(head == "1e1f92f2254bf826b44d9807c5522051991906e8" and index["sha256"] ==
                "edeb7fda3b6bdaeede9611bfb64caadb894c0a7b7c535a5d47947e1c11269099", "root changed")
    cli.require(readgit("rev-parse", "refs/heads/checkpoint/p34-pump-batch12-20261003") == BASE,
                "checkpoint predecessor changed")
    for relative in ("objects", "refs", "logs"):
        path = s.checked(ROOT / ".git" / relative)
        for directory, dirs, names in os.walk(path):
            for name in dirs + names: s.checked(Path(directory) / name)
    for name in ("index", "index.lock", "intent.json", "stage.json", "result.json", "commands.jsonl", "hooks"):
        s.checked(OUT / name)
    for name in (REF, REF + ".lock", "logs/" + REF, "logs/" + REF + ".lock"):
        s.checked(ROOT / ".git" / name)
    evidence = s.read(review.AREA / "review-001/result.json")
    for item in [evidence["source"], *evidence["dependencies"]]:
        cli.require(cli.record(s.checked(item["path"])) == item, "comparison source changed")
    rows = {name: review.receiver.sample(s, root) for name, root in review.TRIALS.items()}
    costs = {name: review.installation_costs(s, row) for name, row in rows.items()}
    cli.require(rows == evidence["samples"] and review.compare(rows) == evidence["comparison"] and
                json.loads(json.dumps(costs)) == evidence["installation_costs"] and
                evidence["erase_command_plan_observed"] and
                evidence["comparison"]["useful_installation_screening_gain"], "measured evidence changed")
    test = s.read(review.AREA / "review-tests-002/result.json")
    cli.require(test["result"] == "PASS" and test["source"] == cli.record(review.__file__) and
                test["test"] == cli.record(ROOT / "tests/ota/test_p34_half_erase_review.py"), "review tests changed")
    files = {name: cli.record(s.checked(ROOT / name)) for name in FILES}
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    for key, leaf in dict(HOME="home", USERPROFILE="home", APPDATA="appdata", LOCALAPPDATA="localappdata",
                         TEMP="tmp", TMP="tmp", TMPDIR="tmp", XDG_CACHE_HOME="home/cache",
                         XDG_CONFIG_HOME="home/config").items():
        env[key] = str(s.checked(OUT / "host" / leaf))
    env.update(GIT_INDEX_FILE=str(OUT / "index"), GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME=readgit("config", "user.name"), GIT_AUTHOR_EMAIL=readgit("config", "user.email"))
    env.update(GIT_COMMITTER_NAME=env["GIT_AUTHOR_NAME"], GIT_COMMITTER_EMAIL=env["GIT_AUTHOR_EMAIL"])
    if not save:
        print("HALF_CHECKPOINT_PREFLIGHT_PASS", len(files), "files; no writes")
        return
    s.write(OUT / "intent.json", dict(base=BASE, ref=REF, head=head, index=index, files=files,
        source=cli.record(__file__), comparison=cli.record(review.AREA / "review-001/result.json"),
        scope="Local checkpoint only; preserve root index/HEAD; no filters/hooks/signing/push"))
    for key in ("HOME", "APPDATA", "LOCALAPPDATA", "TEMP", "XDG_CACHE_HOME", "XDG_CONFIG_HOME"):
        s.checked(env[key]).mkdir(parents=True, exist_ok=True)

    def git(*args, data=None, allowed=(0,)):
        result = subprocess.run(["git", "-c", "gc.auto=0", "-c", "maintenance.auto=false",
            "-c", "commit.gpgsign=false", "-c", "core.hooksPath=" + str(OUT / "hooks"), *args],
            cwd=ROOT, env=env, input=data, capture_output=True, timeout=90)
        with s.checked(OUT / "commands.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(args=args, code=result.returncode,
                stdout=result.stdout.decode(errors="replace"), stderr=result.stderr.decode(errors="replace"))) + "\n")
        cli.require(result.returncode in allowed, "Git operation failed; preserve checkpoint attempt: " + str(args))
        return result.stdout.decode().strip()

    git("show-ref", "--verify", "--quiet", REF, allowed=(1,))
    git("read-tree", BASE)
    for name in FILES:
        data = (ROOT / name).read_bytes()
        cli.require(cli.record(ROOT / name) == files[name], "checkpoint source changed")
        digest = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        s.checked(ROOT / ".git/objects" / digest[:2] / digest[2:])
        cli.require(git("hash-object", "-w", "--stdin", data=data) == digest, "Git blob differs")
        git("update-index", "--add", "--cacheinfo", "100644", digest, name)
    git("diff", "--cached", "--check", BASE, "--", ".", ":(exclude)Tools/ota/p34_half_erase.patch")
    changed = git("diff", "--cached", "--name-only", BASE).splitlines()
    cli.require(set(changed) == set(FILES), "unscoped staged files")
    tree = git("write-tree")
    s.write(OUT / "stage.json", dict(tree=tree, files=changed, stat=git("diff", "--cached", "--stat", BASE)))
    cli.require(cli.record(ROOT / ".git/index") == index and readgit("rev-parse", "HEAD") == head, "root changed")
    commit = git("commit-tree", tree, "-p", BASE, "-m", "perf(p3-4): preserve measured mixed-erase installation gain")
    git("update-ref", "--create-reflog", REF, commit, "0" * 40)
    cli.require(git("rev-parse", REF) == commit and cli.record(ROOT / ".git/index") == index and
                readgit("rev-parse", "HEAD") == head, "checkpoint verification failed")
    s.write(OUT / "result.json", dict(result="CHECKPOINT_SAVED", commit=commit, ref=REF, parent=BASE,
        files=changed, head_unchanged=True, index_unchanged=True, pushed=False))
    print("CHECKPOINT_SAVED", commit, len(changed), "files; main/index unchanged")


if __name__ == "__main__":
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit isolated root required")
    cli.require(sys.argv[1:] in (["check"], ["save"]), "explicit check/save required")
    main(sys.argv[1] == "save")
