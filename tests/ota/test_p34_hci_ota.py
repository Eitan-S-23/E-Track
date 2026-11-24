"""Offline stream reassembly and exact package binding regressions."""
from pathlib import Path
import sys
import struct
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota'))
import p34_hci_ota as m


def row(data, n, handle=15):
    return dict(generation=1, direction='tx', value_handle=handle, value_hex=data.hex(),
                start_record=n, end_record=n, start_timestamp=n*1000, end_timestamp=n*1000)


class Tests(unittest.TestCase):
    def test_completion_is_bound_to_handle_and_fifo(self):
        packets = [bytes.fromhex('020a200000'), bytes.fromhex('020a200000'),
                   bytes.fromhex('041305010a000200')]
        raw = bytes(16) + b''.join(struct.pack('>IIIIQ',len(p),len(p),0,0,i*1000)+p
                                  for i,p in enumerate(packets,1))
        result = m.completions(raw, dict(start_record=1,end_record=3,handle=10))
        self.assertEqual(result, {1:dict(record=3,timestamp=3000),2:dict(record=3,timestamp=3000)})
        with self.assertRaises(ValueError):
            m.completions(raw, dict(start_record=2,end_record=3,handle=10))

    def test_original_completed_measurement(self):
        base = ROOT / '.cache/p34-hci/export-current-001/hci-02.btsnoop'
        if not base.exists():
            self.skipTest('original local HCI evidence not present')
        import json
        report = json.loads((ROOT / '.cache/p34-crc-screen/trials/measure/analysis/1790966205697885600/result.json').read_bytes())
        package = Path(report['inputs']['download']['path']).read_bytes()
        result = m.analyze(base.read_bytes(), package, report['summary']['input'])
        self.assertEqual((result['data_frames'],result['ack_frames'],result['data_att_chunks']), (2289,2289,1574))
        self.assertEqual(result['parameters_during_data'], [])
        self.assertEqual(result['parameters_before_data'][-1]['interval_ms'], 15)
        totals = result['block_timing']['totals']
        self.assertAlmostEqual(totals['tail_ms'], 8383.299)
        self.assertAlmostEqual(totals['after_controller_report_ms'], 7114.653)
        self.assertFalse(any(result['block_timing']['negative_samples'].values()))

    def test_split_and_batched_frames_preserve_origins(self):
        a = m.compare.frame(2, 1, 1, b'\0\0\0\0abc')
        b = m.compare.frame(2, 1, 2, b'\x03\0\0\0def')
        frames = m.frames([row(a[:7], 1), row(a[7:]+b, 2)])
        self.assertEqual([(x['start_record'],x['end_record']) for x in frames], [(1,2),(2,2)])
        m.verify_data(frames, b'abcdef')

    def test_crc_bad_prefix_and_incomplete_stream_rejected(self):
        good = m.compare.frame(2, 1, 1, b'\0\0\0\0abc')
        for bad in (b'x'+good, good[:-1], good[:-1]+bytes([good[-1]^1])):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                m.frames([row(bad, 1)])

    def test_characteristic_streams_must_not_mix(self):
        with self.assertRaises(ValueError):
            m.frames([row(b'aa', 1), row(b'bb', 2, 12)])

    def test_wrong_package_offset_sequence_and_partial_rejected(self):
        good = dict(sequence=1, payload=b'\0\0\0\0abc')
        for frames, package in (([good], b'abd'), ([good], b'abcd'),
                ([dict(good, sequence=2)], b'abc'),
                ([dict(good, payload=b'\x01\0\0\0abc')], b'abc'), ([], b'')):
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                m.verify_data(frames, package)


if __name__ == '__main__':
    unittest.main(verbosity=2)
