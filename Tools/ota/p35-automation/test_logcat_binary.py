"""Synthetic binary framing and optional original-phone replay."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
import runner as r
import logcat_binary as b
import test_scenarios as s
import test_runner as u


def entry(message, header=28, pid=321):
    body=struct.pack('<IBI',b.TAG,2,len(message))+message
    head=struct.pack('<HHiiii',len(body),header,pid,pid,1793546030,1000)
    if header>=24:head+=struct.pack('<I',2)
    if header>=28:head+=struct.pack('<I',10123)
    return head+body


class BinaryTests(unittest.TestCase):
    def test_mixed_original_binary_mirror_covers_states_and_diagnostic_tail(self):
        original = u.mixed_archive(interleaved=True)
        rows = r.Decoder().feed(original)
        lines = original.splitlines()
        wire = b''.join(entry(line) for line in lines)
        report, decoded, _ = b.audit_pair(wire, wire, 321, 'a' * 32, original, rows, {})
        self.assertEqual(decoded, original)
        self.assertTrue(report['completeCombinedCoverage'])
        self.assertTrue(report['exactEquality'])
        self.assertEqual(report['originalRecords'], 5)
        for missing in (2, 4, 5):
            incomplete = b''.join(entry(line) for i, line in enumerate(lines) if i != missing)
            report, _, _ = b.audit_pair(incomplete, incomplete, 321, 'a' * 32, original, rows, {})
            self.assertFalse(report['completeCombinedCoverage'])
            self.assertEqual(report['missingSequences'], [missing])

    def test_mixed_partial_tail_recovery_retains_original_and_rejects_changed_owner(self):
        original = u.mixed_archive(interleaved=True)
        rows = r.Decoder().feed(original)
        lines = original.splitlines()
        live = b''.join(entry(line) for line in lines[:-2]) + entry(lines[-2])[:70]
        terminal = entry(lines[-2]) + entry(lines[-1])
        report, _, _ = b.audit_pair(live, terminal, 321, 'a' * 32, original, rows, {})
        self.assertTrue(report['completeCombinedCoverage'])
        self.assertFalse(report['exactEquality'])
        self.assertIsNotNone(report['partialLiveTail'])
        changed = terminal.replace(b'"ownerEpoch": 7', b'"ownerEpoch": 8')
        report, _, _ = b.audit_pair(live, changed, 321, 'a' * 32, original, rows, {})
        self.assertFalse(report['retainedMatch'])
        self.assertFalse(report['completeCombinedCoverage'])

    def test_long_record_is_lossless_for_supported_headers(self):
        import json
        row=s.state();row['runtime']['task']['taskId']='f'*100
        raw=(r.PREFIX+json.dumps(row)).encode()
        self.assertGreater(len(raw),1024)
        for header in (20,24,28):
            decoded,count=b.decode(entry(raw,header),321)
            self.assertEqual(decoded,raw+b'\n');self.assertEqual(count,1)
            self.assertEqual(r.Decoder().feed(decoded),[row])

    def test_partial_foreign_pid_wrong_buffer_or_string_length_rejected(self):
        raw=entry((r.PREFIX+'{}').encode())
        bad_buffer=bytearray(raw);struct.pack_into('<I',bad_buffer,20,0)
        bad_length=bytearray(raw);struct.pack_into('<I',bad_length,33,9000)
        for data in (raw[:3],raw[:-1],entry(b'OTA_P35_STATE {}',22),
                     bytes(bad_buffer),bytes(bad_length),entry(b'OTA_P35_STATE {}\n')):
            with self.subTest(data=data),self.assertRaises(r.Stop):b.decode(data,321)

    def test_actual_header_pid_filter_excludes_foreign_messages(self):
        wanted=b'OTA_P35_STATE {}'
        decoded,count=b.decode(entry(b'OTA_P35_STATE foreign',pid=555)+entry(wanted),321)
        self.assertEqual(decoded,wanted+b'\n');self.assertEqual(count,2)

    def test_opt_in_uses_byte_preserving_adb_entry(self):
        p=s.plan();p['preparation']['logcat_binary']=True
        r.validate_plan(p,scenarios=True)
        io=r.Android.__new__(r.Android);io.p=p;io.base=['ADB'];io.pid='321'
        self.assertEqual(io.logcat_command(),['ADB','exec-out','logcat','-B','-b','events','--pid=321','-T','1'])
        p['preparation']['logcat_binary']=1
        with self.assertRaises(r.Stop):r.validate_plan(p,scenarios=True)

    def test_original_long_messages_match_app_without_text_reconstruction(self):
        area=r.ROOT/'.cache/p35-scenarios-20261101'
        if not (area/'binary-preflight-02/logcat.bin').exists():self.skipTest('optional local original')
        raw=(area/'binary-preflight-02/logcat.bin').read_bytes()
        decoded,count=b.decode(raw,649)
        expected=r.Decoder().feed((area/'resume-once/pipeline-01/device/app-capture.jsonl').read_bytes())
        observed=[]
        for line in decoded.splitlines():
            if line.startswith(r.PREFIX.encode()):observed.append(r.validate_state(r.strict_json(line[len(r.PREFIX):])))
        self.assertEqual(len(observed),3111)
        self.assertEqual(observed,expected[2147:])
        with self.assertRaises(r.Stop):b.decode((area/'binary-preflight-01/logcat.bin').read_bytes(),649)

    def test_partial_tail_is_explicit_and_not_a_strict_decode_success(self):
        raw=entry(b'OTA_P35_STATE {}')
        decoded,count,tail=b.decode_prefix(raw+raw[:35],321)
        self.assertEqual(decoded,b'OTA_P35_STATE {}\n');self.assertEqual(count,1)
        self.assertEqual(tail['bytes'],35);self.assertEqual(tail['offset'],len(raw))
        with self.assertRaises(r.Stop):b.decode(raw+raw[:35],321)
        corrupt=bytearray(raw);struct.pack_into('<H',corrupt,2,99)
        with self.assertRaises(r.Stop):b.decode_prefix(bytes(corrupt),321)

    def test_terminal_original_covers_tail_without_rewriting_live(self):
        import hashlib,json
        rows=[u.state(seq=i,monoUs=i*1000) for i in (1,2,3)]
        lines=[(r.PREFIX+json.dumps(x)+'\n').encode() for x in rows]
        cid=rows[0]['captureId']
        header=('OTA_P35_CAPTURE '+json.dumps(dict(schema=1,kind='open',captureId=cid))+'\n').encode()
        footer=('OTA_P35_CAPTURE '+json.dumps(dict(schema=1,kind='close',captureId=cid,records=3,
            sha256=hashlib.sha256(b''.join(lines)).hexdigest(),healthy=True,lost=0,error=None))+'\n').encode()
        original=header+b''.join(lines)+footer
        live=entry(header.rstrip(b'\n'))+entry(lines[0].rstrip(b'\n'))+entry(lines[1].rstrip(b'\n'))[:80]
        terminal=b''.join(entry(x.rstrip(b'\n')) for x in lines[1:]+[footer])
        report,prefix,end=b.audit_pair(live,terminal,321,cid,original,rows,{})
        self.assertTrue(report['completeCombinedCoverage']);self.assertFalse(report['exactEquality'])
        self.assertTrue(report['partialLiveTail']);self.assertEqual(report['missingSequences'],[])
        self.assertNotEqual(prefix,original);self.assertNotEqual(end,original)
        short=b''.join(entry(x.rstrip(b'\n')) for x in [lines[2],footer])
        self.assertFalse(b.audit_pair(live,short,321,cid,original,rows,{})[0]['completeCombinedCoverage'])


if __name__=='__main__':unittest.main()
