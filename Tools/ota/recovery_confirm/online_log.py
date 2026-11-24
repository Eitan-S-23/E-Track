"""Same-connection log-switch coordinator; not an install or device entry point."""
import time
from copy import copy

from .ap_journal import JournalSDK, valid_time
from .mutation_audit import journal, target_events


class OnlineLog:
    """Own the event partition and inhibit target operations during every seal.

    Caller must route JournalSDK and Words events through emit, intersect every
    target writer's owner predicate with target_allowed, and supply preflighted
    files to SealedGate. Entry, native close and hardware authority are external.
    """
    def __init__(self, dap, gate, persist, left, *, initial_rows=(), clock=time.monotonic):
        if not isinstance(dap.sdk, JournalSDK) or gate.index != 0 or gate.active:
            raise ValueError('fresh journal/gate required')
        self.dap, self.gate, self.persist, self.left, self.clock = dap, gate, persist, left, clock
        self.rows = list(initial_rows)
        self.error = None
        self.mode = 'OPEN'
        self.previous = None
        self.gate.begin(0)
        # The caller retains pre-construction events as initial_rows.
        dap.sdk.emit = self.emit

    def fail(self, error):
        if self.error is None:
            self.error = type(error).__name__ + ': ' + str(error)
        self.mode = 'FAILED'

    def emit(self, event, **fields):
        try:
            if self.error is not None:
                raise ValueError('online event sink failed')
            self.persist(event, **fields)
            self.rows.append(dict(event=event, **fields))
        except BaseException as error:
            self.fail(error)
            raise

    def target_allowed(self):
        return (self.mode == 'OPEN' and self.error is None and self.gate.error is None and
                self.gate.active and self.dap.ready and self.dap.sdk.error is None)

    def time_check(self, minimum=5):
        now, left = self.clock(), self.left()
        if (not valid_time(now) or not valid_time(left) or left < minimum or
                self.previous is not None and now < self.previous):
            raise ValueError('online log clock/native-call allowance exhausted')
        self.previous = now
        return now

    def state(self):
        values = []
        for index, ap in ((1, 0), (0, 1), (1, 1)):
            self.time_check()
            values.append(self.dap._read_reg(index, ap))
            self.time_check()
        if values[0] & 0xf0000000 != 0xf0000000 or values[0] & 0xb2 or values[1] != self.dap.word_csw:
            raise ValueError('unhealthy DP/AP boundary')
        return values

    def complete_frames(self):
        for _ in journal(self.rows, self.gate.cursor.state.sequence, self.gate.cursor.state.previous_end):
            pass
        for _ in target_events(self.rows):
            pass

    def verify_head(self):
        """Read the active raw prefix without advancing the real sealed cursor."""
        path = self.gate.paths[self.gate.index]
        before = self.gate.record(path)
        if before['path'] != str(path) or not 0 < before['bytes'] <= 65536:
            raise ValueError('new raw SDK head missing/oversized')
        cursor = copy(self.gate.cursor)
        with path.open('r', encoding='utf-8', errors='strict') as stream:
            result = cursor.verify(stream, self.rows, read_allowed=lambda _:False, expected_stores=[])
        if (result['native_calls'] != 3 or result['target_reads'] or result['target_writes'] or
                result['first'] != self.gate.boundary or self.gate.record(path) != before):
            raise ValueError('new raw SDK head incomplete/changed/not AP-only')
        self.emit('online-log-head-verified', record=before, trace=result)

    def switch(self, *, read_allowed, expected_stores, expected_dp_writes=(), bind_words=True):
        try:
            if not self.target_allowed() or self.dap.sdk.busy or self.gate.index+1 >= len(self.gate.paths):
                raise ValueError('online switch ownership/position failure')
            self.mode = 'SEALING'
            index = self.gate.index
            # Reject a partial logical operation before touching the SDK log.
            self.complete_frames()
            started = self.time_check()
            before = self.state()
            self.emit('online-log-switch-attempt', old=index, new=index+1)
            self.time_check()
            self.dap._call('JLINKARM_SetLogFile', str(self.gate.paths[index+1]).encode('ascii'))
            old_rows, self.rows = self.rows, []
            self.emit('online-log-switch-returned', old=index, new=index+1)
            after = self.state()
            ended = self.time_check()
            if before != after:
                raise ValueError('AP state changed across native log switch')
            self.emit('online-log-state', before=before, after=after, started=started, ended=ended)
            result = self.gate.seal(index, old_rows, read_allowed=read_allowed, expected_stores=expected_stores,
                                    expected_dp_writes=expected_dp_writes, bind_words=bind_words)
            self.time_check()
            self.verify_head()
            self.time_check()
            self.emit('online-log-sealed', index=index, record=self.gate.records[-1], trace=result)
            self.gate.begin(index+1)
            self.mode = 'OPEN'
            return result
        except BaseException as error:
            self.fail(error)
            raise

    def prepare_close(self):
        try:
            if not self.target_allowed() or self.dap.sdk.busy or self.gate.index != len(self.gate.paths)-1:
                raise ValueError('final log position/ownership required')
            self.mode = 'CLOSING'
            self.time_check(minimum=60)
            self.complete_frames()
            self.time_check(minimum=60)
        except BaseException as error:
            self.fail(error)
            raise

    def finish(self, *, read_allowed, expected_stores, expected_dp_writes=(), bind_words=True):
        try:
            if self.mode != 'CLOSING' or self.error is not None or self.dap.close_returned is not True:
                raise ValueError('actual native close return required')
            result = self.gate.seal(self.gate.index, self.rows, read_allowed=read_allowed,
                                    expected_stores=expected_stores, expected_dp_writes=expected_dp_writes,
                                    final=True, bind_words=bind_words, native_closed=self.dap.close_returned)
            self.mode = 'FINISHED'
            return result
        except BaseException as error:
            self.fail(error)
            raise
