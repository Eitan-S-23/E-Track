from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
import p34_finalized_reader_audit as a


def fixture():
    raw=b'12345678';base=a.ORIGIN;old=0x12345678
    lines=[f'JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x01, 0x{base:08X})','returns 0']
    for offset in (0,4):
        lines.extend(['JLINK_CORESIGHT_ReadAPDPReg(AP reg 0x03)',
                      f'Value=0x{int.from_bytes(raw[offset:offset+4],"little"):08X}','returns 0'])
    lines.extend([f'JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x01, 0x{old:08X})','returns 0','JLINK_Close()'])
    events=[dict(event='finalized-read-attempt',address=base,bytes=8),
            dict(event='finalized-read-returned',address=base,data_hex=raw.hex())]
    return lines,events,dict(ap_csw=0x23000052,original_tar=old),raw


class AuditTests(unittest.TestCase):
    def test_complete_sdk_frame_file_match(self):
        result=a.trace(*fixture())
        self.assertEqual(result['matched_words'],2)
        self.assertEqual(result['target_memory_data_writes'],0)

    def test_target_write_rejected(self):
        lines,events,meta,raw=fixture()
        lines.insert(2,'JLINK_CORESIGHT_WriteAPDPReg(AP reg 0x03, 0xA05F0001)')
        with self.assertRaises(RuntimeError):a.trace(lines,events,meta,raw)

    def test_wrong_returned_bytes_or_file_rejected(self):
        lines,events,meta,raw=fixture()
        lines[3]='Value=0x00000000'
        with self.assertRaises(RuntimeError):a.trace(lines,events,meta,raw)
        lines,events,meta,raw=fixture()
        with self.assertRaises(RuntimeError):a.trace(lines,events,meta,b'xxxxxxxx')

    def test_truncated_sdk_or_missing_return_rejected(self):
        lines,events,meta,raw=fixture()
        with self.assertRaises(RuntimeError):a.trace(lines[:6],events,meta,raw)
        with self.assertRaises(RuntimeError):a.trace(lines,events[:1],meta,raw)

    def test_incomplete_file_coverage_and_bad_restore_rejected(self):
        lines,events,meta,raw=fixture()
        with self.assertRaises(RuntimeError):a.trace(lines,events,meta,raw+b'xxxx')
        meta['original_tar']+=4
        with self.assertRaises(RuntimeError):a.trace(lines,events,meta,raw)


if __name__=='__main__':unittest.main()
