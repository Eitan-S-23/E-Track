"""Diagnostic render failures cannot erase a separately verified primary stream."""
import hashlib
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runner as r
import test_runner as u


class MirrorTests(unittest.TestCase):
    def test_complete_and_clipped_rows_are_distinguished(self):
        rows=[u.state(seq=i,monoUs=i*1000) for i in (1,2,3)]
        status=dict(status='NO_NATIVE_ERROR_OBSERVED')
        whole=b''.join(u.line(x) for x in rows)
        self.assertTrue(r.audit_logcat_mirror(whole,rows[0]['captureId'],rows,status)['exactEquality'])
        clipped=u.line(rows[1])[:160]+b'^\n'
        raw=u.line(rows[0])+clipped+u.line(rows[2])
        value=r.audit_logcat_mirror(raw,rows[0]['captureId'],rows,status)
        self.assertFalse(value['exactEquality'])
        self.assertEqual(value['missingSequences'],[2])
        self.assertTrue(value['retainedMatch'])
        self.assertEqual(value['parseErrors'][0]['sha256'],hashlib.sha256(clipped.rstrip(b'\n')).hexdigest())
        self.assertEqual(value['parseErrors'][0]['line'],2)
        with self.assertRaises(r.Stop):r.Decoder().feed(raw)

    def test_empty_wrong_and_malformed_diagnostics_never_claim_equality(self):
        original=u.state()
        for raw in (b'',u.line(dict(original,durable=4096)),u.line(dict(original,seq=0)),
                    u.line(dict(original,captureId='f'*32)),r.PREFIX.encode()+b'\xff\n'):
            with self.subTest(raw=raw):
                value=r.audit_logcat_mirror(raw,original['captureId'],[original],{})
                self.assertFalse(value['exactEquality'])
                self.assertFalse(value['usedForInjection'])

    def test_original_clipping_is_reported_without_new_device_reads(self):
        root=r.ROOT/'.cache/p35-scenarios-20261101/resume-once/pipeline-01/device'
        if not root.exists():self.skipTest('optional original-evidence replay')
        raw=(root/'app-capture.jsonl').read_bytes()
        rows=r.Decoder().feed(raw)
        r.audit_capture(raw,rows[0]['captureId'])
        self.assertEqual(raw,(root/'live-stream.stdout').read_bytes())
        status=r.audit_logcat_status((root/'logcat-native-status.json').read_bytes(),rows[0]['captureId'],raw)
        value=r.audit_logcat_mirror((root/'logcat.stdout').read_bytes(),rows[0]['captureId'],rows,status)
        self.assertTrue(value['parseErrors'])
        self.assertFalse(value['exactEquality'])
        self.assertTrue(value['retainedMatch'])


if __name__=='__main__':unittest.main()
