"""One explicit same-signer APK request for the verified DATA-batch candidate."""
from pathlib import Path
import runpy
import sys
import types
import time

ROOT = Path(__file__).resolve().parents[2]
SHA = "70a41c848099b3051a5244abaae899bd9d6027d5"


def runtime():
    b = runpy.run_path(str(ROOT / "Tools/ota/p34_batch_validation.py"))["runtime"]()
    original_save = b.save
    def save(path, value):
        if path == 'apk-g1/intent.json':
            value = dict(value, purpose='bounded DATA batching experiment; same application ID and fixed development signer')
        return original_save(path, value)
    b.save = save
    return b


def wait_for_apk():
    b = runtime()
    accepted = b.read('apk-g1/accepted.json')
    intent = b.read('apk-g1/intent.json')
    b.require(accepted['sha'] == intent['sha'] == SHA, 'APK request identity changed')
    token = b.credential()
    progress = b.checked(b.OUT / 'apk-g1/build-progress.json')
    deadline = time.monotonic() + 2400
    while time.monotonic() < deadline:
        runs = b.api('/repos/' + b.REPO + '/actions/runs?head_sha=' + SHA + '&per_page=100', token)[1]['workflow_runs']
        selected = [r for r in runs if r['id'] not in intent['prior_ids'] and
                    r['event'] == 'workflow_dispatch' and r['head_branch'] == b.BRANCH and
                    r['path'] == '.github/workflows/flutter-dev-checks.yml']
        b.require(len(selected) <= 1, 'ambiguous APK run; do not collect')
        if selected:
            run = selected[0]
            b.require(run['head_sha'] == SHA and run['run_attempt'] == 1, 'APK source/attempt changed')
            b.io.write_json(ROOT, progress,
                dict(time=b.now(), run=run['id'], status=run['status'], conclusion=run['conclusion']),
                replace=progress.exists())
            if run['status'] == 'completed':
                b.require(run['conclusion'] == 'success', 'APK build failed; preserve original run')
                return
        time.sleep(30)
    raise RuntimeError('APK build wait expired; inspect original run, do not redispatch')


if __name__ == '__main__':
    if not (Path.cwd() == ROOT and sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError('isolated explicit root required')
    if sys.argv[1:] == ['wait-collect']:
        wait_for_apk()
        sys.argv = [__file__, 'collect']
    entry = runpy.run_path(str(ROOT / 'Tools/ota/p34_connect_artifacts.py'))['main']
    def load(path):
        path = Path(path)
        if path == ROOT / 'Tools/ota/p34_connect_validation.py':
            return dict(runtime=runtime)
        if path == ROOT / 'Tools/ota/p34_signing_artifacts.py':
            return runpy.run_path(str(path))
        raise RuntimeError('unexpected batch artifact dependency')
    entry.__globals__.update(SHA=SHA, runpy=types.SimpleNamespace(run_path=load))
    entry()
