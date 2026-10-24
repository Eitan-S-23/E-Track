"""Standard hidden Windows breakaway launch for finite existing host workers."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from prepare import ROOT, h


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("launch", "supervise", "probe"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--seconds", type=int, required=True)
    parser.add_argument("--worker", choices=("probe", "network", "observe"), default="probe")
    args, tail = parser.parse_known_args()
    h.require(not tail or tail[0] == "--", "worker arguments require an explicit separator")
    args.args = tail[1:] if tail else []
    h.require(os.name == "nt" and Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and
              sys.dont_write_bytecode and 5 <= args.seconds <= 8400, "finite isolated Windows worker required")
    out = h.checked(args.out)
    for name in ("host", "stdout", "stderr", "launch.json", "exit.json", "probe-start.json", "probe-end.json"):
        h.checked(out / name)
    prefix = [sys.executable, "-I", "-S", "-B", "-X", "utf8"]
    if args.action == "launch":
        h.fresh(out)
        env = h.environment(out)
        argv = prefix + [str(Path(__file__).resolve()), "supervise", "--out", str(out), "--seconds", str(args.seconds),
                         "--worker", args.worker, "--", *args.args]
        with (out / "stdout").open("xb") as stdout, (out / "stderr").open("xb") as stderr:
            process = subprocess.Popen(argv, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr,
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_BREAKAWAY_FROM_JOB)
        h.save(out / "launch.json", dict(pid=process.pid, argv=argv, seconds=args.seconds, no_device_action_by_launcher=True))
        print("BOUNDED_WORKER_LAUNCHED", process.pid)
        return
    if args.action == "probe":
        h.save(out / "probe-start.json", dict(pid=os.getpid(), monotonic=time.monotonic()))
        time.sleep(args.seconds)
        h.save(out / "probe-end.json", dict(pid=os.getpid(), monotonic=time.monotonic()))
        return
    tail = list(args.args)
    while tail and tail[0] == "--":
        tail.pop(0)
    if args.worker == "probe":
        argv = prefix + [str(Path(__file__).resolve()), "probe", "--out", str(out), "--seconds", str(args.seconds - 2)]
    else:
        argv = prefix + [str(Path(__file__).with_name(args.worker + ".py")), *tail]
    status = dict(result="WORKER_INCOMPLETE", argv=argv)
    try:
        h.command(out, "worker", argv, h.environment(out), seconds=args.seconds)
        status["result"] = "WORKER_EXITED_ZERO"
    except BaseException as error:
        status.update(result="WORKER_FAILED", error=type(error).__name__ + ": " + str(error))
        raise
    finally:
        h.save(out / "exit.json", status)


if __name__ == "__main__":
    main()
