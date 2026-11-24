"""Resume the exact unused Boot cell after its original service became ready."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Tools/ota"))
import p34_session as cli

RUN = "20260930T133457-87100"


def admit(state, attempted):
    cli.require(state["run"] == RUN and not attempted and
                state["worker"]["state"] == "NOT_STARTED" and
                state["network"]["state"] == "LIVE" and state["network"].get("service") == "VERIFIED" and
                state["network"].get("remaining_service_seconds", 0) > cli.CELL_SECONDS + 30,
                "require exact unused cell and live verified service with full remaining allowance")


def run():
    cli.require(Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode,
                "explicit root and isolated Python required")
    store = cli.Store(ROOT)
    with store.command_lock():
        cli.require(store.current() == RUN, "current session changed")
        out = store.run(RUN)
        resume = store.checked(out / "network-resume")
        cell = store.checked(out / "cells/s04")
        runtime = store.checked(out / "runtime/s04")
        cli.require(not resume.exists(), "preserve prior resume attempt")
        admit(cli.status(store, RUN, "s04"), cell.exists() or runtime.exists())
        plan = store.read(out / "plan.json")
        cli.require(plan["group"] in cli.NEW_BOOT_GROUPS and
                    (plan["receiver_version"], plan["target_version"]) == cli.FULL_VERSIONS[plan["group"]] and
                    plan["cells"]["s04"] == [921600, 28],
                    "wrong prepared cell")
        tests = cli.verify_tests(store)
        api = cli.backend(store, Path(plan["profile"]["path"]), plan["group"])
        c = api.context(out)
        api.validate(c, out)
        api.network_ready(c, out)
        admit(cli.status(store, RUN, "s04"), cell.exists() or runtime.exists())
        for name in ("intent.json", "result.json"):
            store.checked(resume / name)
        store.checked(cell / "intent.json")
        store.write(resume / "intent.json", dict(time=cli.now(), source=cli.record(Path(__file__)),
            plan=cli.record(out / "plan.json"), tests=tests, service=cli.record(out / "live-network.json"),
            reason="original parent wait expired before DNS readiness; no previous cell or runtime exists",
            network_restarted=False, package_regenerated=False, ota_replayed=False))
        store.write(cell / "intent.json", dict(time=cli.now(), cell="s04", plan=cli.record(out / "plan.json")))
        c.supervisor.owned.launch(runtime, ROOT / "Tools/ota/p34_session.py",
            ["--root", str(ROOT), "--run", RUN, "--cell", "s04", "_cell"], cli.CELL_SECONDS)
        store.write(resume / "result.json", dict(time=cli.now(), result="UNUSED_CELL_OWNER_LAUNCHED",
            run=RUN, cell="s04", network_restarted=False, ota_started_by_host=False))
        print("UNUSED_CELL_OWNER_LAUNCHED", RUN)


if __name__ == "__main__":
    if sys.argv[1:]:
        cli.require(len(sys.argv) == 3 and sys.argv[1] == "--run" and cli.RUN_NAME.fullmatch(sys.argv[2]),
                    "expected --run with an explicit prepared run")
        RUN = sys.argv[2]
    run()
