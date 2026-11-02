"""Actual Windows parent-exit/timeout probes; no phone, firmware CI or cloud."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detached as d
import runner as r


@unittest.skipUnless(os.name == 'nt', 'actual Windows Job qualification')
class DetachedTests(unittest.TestCase):
    def setUp(self):
        self.h = r.load_host()
        self.area = self.h.fresh(r.ROOT / '.cache/p35-repeat-20261101/host-cases' / uuid.uuid4().hex)
        self.env = self.h.environment(self.area)

    def wait_result(self, out):
        until = time.monotonic() + 30
        while time.monotonic() < until:
            if (out / 'result.json').exists():
                return self.h.read_json(out / 'result.json')
            time.sleep(.1)
        self.fail('detached worker did not terminate within its bound')

    def test_actual_abrupt_launcher_exit_preserves_output_and_closure(self):
        out = self.area / 'supervisor'
        child = "import time;print('begin',flush=True);time.sleep(3);print('end',flush=True)"
        argv = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', child]
        code = "import sys,os;from pathlib import Path;sys.path.insert(0,'Tools/ota/p35-automation');import detached;detached.launch(Path(%r),%r,os.environ.copy(),seconds=10);os._exit(17)" % (str(out), argv)
        # Inherit the actual terminal Job. The worker must explicitly escape it.
        parent = subprocess.Popen([sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c', code],
            cwd=r.ROOT, env=self.env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = parent.communicate(timeout=15)
        self.h.raw(self.area / 'parent.stdout', stdout)
        self.h.raw(self.area / 'parent.stderr', stderr)
        self.assertEqual(parent.returncode, 17, stderr.decode('utf-8','replace'))
        result = self.wait_result(out)
        self.assertEqual(result['outcome'], 'COMMAND_COMPLETED')
        self.assertEqual(result['exitCode'], 0)
        self.assertFalse(self.h.read_json(out / 'ready.json')['inJob'])
        self.assertEqual((out / 'command.stdout').read_bytes().splitlines(), [b'begin', b'end'])
        closed = self.h.read_json(out / 'command.closed.json')
        self.assertTrue(closed['cleanup_complete'])
        self.assertFalse(closed['stopped_while_running'])
        with self.assertRaises(r.Stop):
            d.launch(out, argv, self.env, seconds=10)

    def test_deadline_kills_only_owned_child_and_preserves_failure(self):
        out = self.area / 'timeout'
        d.launch(out, [sys.executable, '-I', '-S', '-B', '-X', 'utf8', '-c',
                      "import time;print('started',flush=True);time.sleep(30)"], self.env, seconds=1)
        result = self.wait_result(out)
        self.assertEqual(result['outcome'], 'SUPERVISOR_FAILED')
        closed = self.h.read_json(out / 'command.closed.json')
        self.assertTrue(closed['cleanup_complete'])
        self.assertTrue(closed['stopped_while_running'])
        self.assertIn(b'started', (out / 'command.stdout').read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
