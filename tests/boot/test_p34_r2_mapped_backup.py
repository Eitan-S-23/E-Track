import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'Tools/ota'))
sys.path.insert(0, str(ROOT/'tests/boot'))
from recovery_confirm import r2_mapped_backup as run
from recovery_confirm.ap_journal import JournalSDK
from recovery_confirm.online_log import OnlineLog
from recovery_confirm.mutation_audit import SealedGate
from test_p34_r2_passive_state import Native
from test_p34_install_bridges import Buffer
from test_p34_mutation_audit import record, META
from test_p34_recovery_ports import Clock
from test_p34_online_log import Dap
from test_p34_r2_checkpoint import MAP

ARCHIVE = ROOT/'.cache/p34-recovery-continue1/after-candidate-backup.bin'


class Tests(unittest.TestCase):
    def make(self, problem=None):
        clock = Clock()
        image = (ROOT/'.cache/p34-recovery-sources1/r2-a.bin').read_bytes()
        raw = ARCHIVE.read_bytes()
        header, payload = run.expected(raw)
        native = Native(clock, image, None)
        ui = run.ui
        obj, pool = 0x20010000, 0x20040000
        native.memory.update({ui.GUARD: 1, ui.MANAGER+4: pool, ui.MANAGER+8: pool+4,
            ui.MANAGER+12: pool+4, pool: obj, obj: ui.VPTR, ui.COST_ACTIVE: 0,
            **{obj+k: 0 for k in ui.FIELD_OFFSETS.values()}, obj+8: ui.MANAGER, obj+12: ui.NAME})
        native.memory.update({a: 0 for a in (*run.DMA.values(), *run.ENDPOINTS.values())})
        for base, data in ((run.BASE, header), (run.PAYLOAD, payload)):
            native.memory.update({base+i: int.from_bytes(data[i:i+4], 'little') for i in range(0, len(data), 4)})
        if problem == 'header': native.memory[run.BASE] ^= 1
        if problem == 'payload': native.memory[run.PAYLOAD] ^= 1
        if problem == 'csts': native.memory[run.passive.QSPI['qspi_xip3']] |= 8
        if problem == 'dma': native.memory[run.DMA['edma_1']] = 1
        if problem == 'ui': native.memory[obj+ui.FIELD_OFFSETS['timer']] = 0x20001000
        paths = [Buffer(str(i), '') for i in range(run.LOG_COUNT)]
        native.initialize_log(paths)
        dap = Dap(JournalSDK(native, lambda *a, **k: None, clock=clock))
        rows, saved = [], {}
        def persist(event, **fields): rows.append(dict(event=event, **fields))
        logs = OnlineLog(dap, SealedGate(paths, META, record), persist, lambda: 900-clock.value, clock=clock)
        logs.switch(read_allowed=lambda _: False, expected_stores=[])
        probe = run.Capture(dap, logs, image, MAP, lambda: True, lambda: 900-clock.value, raw,
            lambda name, data: saved.__setitem__(name, data), clock=clock, sleep=clock.sleep,
            guard=lambda f, *a, **k: f(*a))
        return probe, native, logs, saved, rows

    def test_complete_raw_word_capture_matches_original_and_seals_all_blocks(self):
        probe, native, logs, saved, rows = self.make()
        value = probe.run()
        self.assertEqual(value['result'], 'R2_OLD_BACKUP_MAPPED_LOGICAL_MATCH')
        self.assertEqual(saved, {'backup-header': probe.header, 'backup-payload': probe.payload})
        self.assertEqual(logs.gate.index, run.LOG_COUNT-1)
        self.assertFalse(value['uncached_chip_read'])
        self.assertFalse(value['ota_ready'])
        self.assertFalse(native.write_log)
        self.assertEqual(len([r for r in rows if r['event'] == 'r2-mapped-backup-progress']), run.LOG_COUNT-2)
        before = len(native.calls)
        with self.assertRaises(ValueError): probe.run()
        self.assertEqual(len(native.calls), before)

    def test_admission_and_content_failures_latch_without_archive_or_replay(self):
        for problem in ('csts', 'dma', 'ui', 'header', 'payload'):
            probe, native, _, saved, rows = self.make(problem)
            with self.subTest(problem=problem), self.assertRaises(ValueError): probe.run()
            self.assertFalse(saved)
            self.assertFalse(native.write_log)
            nor = [r for r in rows if r['event'] == 'recovery-chunk-read-attempt' and r['address'] >= run.BASE]
            if problem in ('csts', 'dma', 'ui'): self.assertFalse(nor)
            if problem == 'header': self.assertEqual([r['address'] for r in nor], [run.BASE])
            before = len(native.calls)
            with self.assertRaises(ValueError): probe.run()
            self.assertEqual(len(native.calls), before)

    def test_mid_chunk_epoch_and_reset_changes_invalidate_whole_capture(self):
        for problem in ('epoch', 'reset', 'qspi', 'owner', 'read-error', 'block-deadline'):
            probe, native, _, saved, _ = self.make()
            original = probe.words.read_bytes
            def read(address, size):
                raw = original(address, size)
                if address == run.PAYLOAD:
                    if problem == 'epoch': native.memory[run.passive.FIELDS['epoch']] = 1
                    if problem == 'reset': native.problem = 'reset'; native.dhcsr_reads = 2
                    if problem == 'qspi': native.memory[run.passive.QSPI['qspi_ctrl']] = 0x80
                    if problem == 'owner': probe.owner = lambda: False
                    if problem == 'read-error': raise OSError('simulated read failure')
                    if problem == 'block-deadline': native.clock.value += 31
                return raw
            probe.words.read_bytes = read
            with self.subTest(problem=problem), self.assertRaises((ValueError, OSError)): probe.run()
            self.assertFalse(saved)
            self.assertIsNotNone(probe.error)
            self.assertFalse(native.write_log)

    def test_block_expiry_prevents_next_chunk_and_caps_actual_native_timeout(self):
        probe, native, _, saved, rows = self.make()
        original = probe.words.read_bytes
        def read(address, size):
            raw = original(address, size)
            if address == run.PAYLOAD: native.clock.value += 31
            return raw
        probe.words.read_bytes = read
        with self.assertRaisesRegex(ValueError, 'block deadline'): probe.run()
        payload = [r for r in rows if r['event'] == 'recovery-chunk-read-attempt' and r['address'] >= run.PAYLOAD]
        self.assertEqual(len(payload), 1)
        self.assertFalse(saved)
        before = len(native.calls)
        with self.assertRaises(ValueError): probe.run()
        self.assertEqual(len(native.calls), before)
        probe, native, _, _, _ = self.make()
        probe.active = True
        probe.block_end = native.clock.value+.25
        caps = []
        def guard(fn, *args, seconds):
            caps.append(seconds)
            return fn(*args)
        probe.guard = guard
        probe.words.read32(run.passive.health.VTOR)
        self.assertTrue(caps)
        self.assertTrue(all(0 < seconds <= .25 for seconds in caps))

    def test_real_archive_callback_failure_expiry_reserve_and_owner_loss_stop_next_save(self):
        for problem in ('exception', 'component-expiry', 'reserve-loss', 'owner-loss'):
            probe, native, _, _, _ = self.make()
            probe.active = True
            calls, caps = [], []
            def save(name, raw):
                calls.append(name)
                if problem == 'exception': raise OSError('real archive callback failure')
                if problem == 'component-expiry': native.clock.value = probe.words.budget.end
                if problem == 'reserve-loss': probe.remaining = lambda: 60
                if problem == 'owner-loss': probe.owner = lambda: False
            def guard(fn, *args, seconds):
                caps.append(seconds)
                return fn(*args)
            probe.emit_archive, probe.guard = save, guard
            with self.subTest(problem=problem), self.assertRaises((ValueError, OSError)):
                probe.save('backup-header', probe.header)
                probe.save('backup-payload', probe.payload)
            self.assertEqual(calls, ['backup-header'])
            self.assertIsNotNone(probe.error)
            self.assertEqual(caps, [30])
            before = len(native.calls)
            with self.assertRaises(ValueError): probe.run()
            self.assertEqual(len(native.calls), before)
        probe, native, _, _, _ = self.make()
        probe.active = True
        probe.remaining = lambda: 60.125
        caps = []
        probe.guard = lambda fn, *args, seconds: (caps.append(seconds), fn(*args))[1]
        probe.save('backup-header', probe.header)
        self.assertEqual(caps, [.125])
        probe, native, _, _, _ = self.make()
        probe.active = True
        probe.words.budget.end = native.clock.value+.25
        caps = []
        probe.guard = lambda fn, *args, seconds: (caps.append(seconds), fn(*args))[1]
        probe.save('backup-header', probe.header)
        self.assertEqual(caps, [.25])

    def test_dma_endpoints_and_raw_profile_not_masked_diagnostic_boolean(self):
        probe, native, _, _, _ = self.make()
        probe.active = True
        row = run.passive.Probe.sample(probe)
        view = probe.view.locate()
        dma = {k: 0 for k in run.DMA}
        ends = dict(display_peripheral=0x4001300c, display_memory=0x20002000,
                    sd_peripheral=0x50061080, sd_memory=0x20003000)
        dma.update(dma1_3=0x1093, dma2_4=0x2a91)
        self.assertEqual(run.qualify(row, view, dma, ends), 0)
        for stem in ('display', 'sd'):
            with self.assertRaises(ValueError): run.qualify(row, view, dma, dict(ends, **{stem+'_memory': run.BASE}))
        changed = copy.deepcopy(row)
        changed['qspi']['qspi_xip3'] = 8
        self.assertTrue(run.passive.decode(changed)['qspi_config_matches_prior'])
        with self.assertRaises(ValueError): run.qualify(changed, view, dma, ends)
        self.assertFalse(native.write_log)


if __name__ == '__main__': unittest.main()
