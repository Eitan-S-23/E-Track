"""Actual owned stdin lifecycle checks without J-Link or any device."""
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p34-acceptance'))
import live_host as h
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import state_chain as s


class InteractiveProcessTests(unittest.TestCase):
    def test_console_requires_complete_current_batch_not_prompt_or_prior_marker(self):
        marker = Path('D:/project/batch_complete.bin')
        body = str(marker).encode('ascii') + b']\r\nReading 4 bytes from addr 0xE000EDF0 into file...O.K.'
        self.assertEqual(s.completed_console(b'old'+body+b'help text', 3, marker), body)
        self.assertFalse(s.completed_console(body, len(body), marker))
        self.assertFalse(s.completed_console(body[:-1], 0, marker))
        self.assertFalse(s.completed_console(b'J-Link>', 0, marker))

    def test_two_batches_keep_one_child_and_close_normally(self):
        out = h.fresh(h.checked(Path(os.environ['P51_COMM_TEST_OUT']) / 'two-batches'))
        code = ('import os,sys\nfor line in sys.stdin:\n'
                ' if line.strip()=="quit": break\n'
                ' print(str(os.getpid())+":"+line.strip(),flush=True)\n')
        p = h.Process(out, 'child', [sys.executable, '-I', '-S', '-B', '-u', '-c', code],
                      h.environment(out), interactive=True)
        try:
            p.send(b'first\n')
            h.wait_for(lambda: b':first\n' in p.paths['stdout'].read_bytes().replace(b'\r', b''), 5)
            p.send(b'second\n')
            h.wait_for(lambda: b':second\n' in p.paths['stdout'].read_bytes().replace(b'\r', b''), 5)
            p.send(b'quit\n')
            p.process.stdin.close()
            result = p.wait(10).decode().splitlines()
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0].split(':')[0], result[1].split(':')[0])
            receipt = h.read_json(p.paths['closed.json'])
            self.assertEqual(receipt['exit_code'], 0)
            self.assertTrue(receipt['cleanup_complete'])
            self.assertFalse(receipt['stopped_while_running'])
            with self.assertRaises(RuntimeError):
                p.send(b'again\n')
        finally:
            p.close('test-finally')

    def test_owned_timeout_and_invalid_input_are_not_replayed(self):
        out = h.fresh(h.checked(Path(os.environ['P51_COMM_TEST_OUT']) / 'timeout'))
        p = h.Process(out, 'child', [sys.executable, '-I', '-S', '-B', '-c', 'import time;time.sleep(30)'],
                      h.environment(out), interactive=True)
        try:
            with self.assertRaises(RuntimeError):
                p.send(b'no-newline')
            with self.assertRaises(RuntimeError):
                p.wait(.2)
            self.assertFalse(p.alive())
            self.assertTrue(h.read_json(p.paths['closed.json'])['cleanup_complete'])
        finally:
            p.close('test-finally')


if __name__ == '__main__':
    unittest.main()
