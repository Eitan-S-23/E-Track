"""Project-preflighted, fsynced exact Boot/App captures; no device operations."""
import hashlib
import os

SIZES = {'before-boot': 65536, 'before-app': 619580,
         'after-boot': 65536, 'after-app': 619580}


class Archive:
    def __init__(self, store, out, binding):
        self.store, self.out, self.binding = store, store.checked(out), binding
        self.paths = {name: store.checked(out / (name+'.bin')) for name in SIZES}
        self.receipt = store.checked(out / 'prewrite.json')
        if any(path.exists() for path in (*self.paths.values(), self.receipt)):
            raise ValueError('preserve prior Boot16 archives')
        self.offsets = dict.fromkeys(SIZES, 0)
        self.failed = self.checkpointed = False
        self.checkpoint_attempted = False

    def __call__(self, name, offset, raw):
        try:
            if (self.failed or name not in SIZES or type(offset) is not int or
                    offset != self.offsets[name] or type(raw) is not bytes or
                    len(raw) != min(32768, SIZES[name]-offset) or not raw):
                raise ValueError('archive order/extent failure')
            path = self.store.checked(self.paths[name])
            if offset and path.stat().st_size != offset:
                raise ValueError('archive size changed')
            with path.open('xb' if offset == 0 else 'ab') as stream:
                if stream.write(raw) != len(raw): raise OSError('short archive write')
                stream.flush()
                os.fsync(stream.fileno())
            self.offsets[name] += len(raw)
        except BaseException:
            self.failed = True
            raise

    def verify(self, label, boot, image):
        try:
            if self.failed: raise ValueError('failed archive cannot verify')
            result = {}
            for name, expected in ((label+'-boot', boot), (label+'-app', image)):
                if self.offsets[name] != SIZES[name] or self.paths[name].read_bytes() != expected:
                    raise ValueError('complete archive differs from physical capture')
                result[name] = dict(path=str(self.paths[name]), bytes=len(expected),
                                    sha256=hashlib.sha256(expected).hexdigest())
            return result
        except BaseException:
            self.failed = True
            raise

    def checkpoint(self, body):
        if self.failed or self.checkpoint_attempted or body.phase != 'PROGRAM' or body.boot_may_have_changed:
            raise ValueError('fresh prewrite checkpoint only')
        self.checkpoint_attempted = True
        try:
            archives = self.verify('before', body.preimage, body.image)
            self.store.write(self.receipt, dict(result='BOOT16_PREWRITE_RECORDED', binding=self.binding,
                direction=body.direction, before=body.control.before, context=body.control.context_before,
                archives=archives, desired_sha256=hashlib.sha256(body.desired).hexdigest(),
                phase=body.phase, release_attempted=False, sectors_audited=0))
            self.checkpointed = True
        except BaseException:
            self.failed = True
            raise
