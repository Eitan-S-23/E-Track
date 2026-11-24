"""Post-normal-OTA R2-A backup expectation, observed while exact R2-B runs."""
import hashlib
import struct
import zlib
from . import r2_mapped_backup as old, r2_mapped_backup_byte as byte

PAYLOAD_BYTES = 619580
PAYLOAD_SHA = '7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf'
READS = old.READS | set(range(old.PAYLOAD, old.PAYLOAD+PAYLOAD_BYTES, 4))


def expected(image):
    if type(image) is not bytes or len(image) != PAYLOAD_BYTES or hashlib.sha256(image).hexdigest() != PAYLOAD_SHA:
        raise ValueError('exact original R2-A backup expectation required')
    header = b'ETSL\x02\xff\xff\xff' + struct.pack('<III', len(image), zlib.crc32(image), 30276)
    return header + image[0x428:0x430] + b'TMOC', image


class Capture(byte.Capture):
    def __init__(self, dap, logs, image, *args, **kwargs):
        if hashlib.sha256(image).hexdigest() != 'e4737cfcbbb884c4a7fa407ea733486425674c7ed2723d0f8cf3263beb4e8802':
            raise ValueError('post-OTA backup observation requires exact R2-B')
        byte.bind(old.Capture.__init__, expected=expected, READS=READS)(self, dap, logs, image, *args, **kwargs)
    _capture = byte.bind(old.Capture.run, PAYLOAD_BYTES=PAYLOAD_BYTES, PAYLOAD_SHA=PAYLOAD_SHA, READS=READS)

    def run(self):
        value = self._capture()
        return dict(value, result='R2A_BACKUP_MAPPED_LOGICAL_MATCH', version=30276)
