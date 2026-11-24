import copy
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
from recovery_confirm import install_entry
from recovery_entry import host_nor
import p34_failed_install_audit as audit


class EntryTests(unittest.TestCase):
    def setUp(self):
        self.store = audit.cli.Store(ROOT)
        self.worker = self.store.read(audit.AREA/'worker.json')
        self.sample = self.worker['component_results']['entry']['state_samples'][0]

    def test_exact_double_buffers_preserve_raw_and_historical_single_buffer_policy(self):
        for address in install_entry.DISPLAY_BUFFERS:
            sample = copy.deepcopy(self.sample)
            sample['raw']['display_dma_memory'] = address
            saved = copy.deepcopy(sample)
            install_entry.qualify_masters(sample)
            self.assertEqual(sample,saved)
        with self.assertRaises(ValueError): host_nor.qualify_masters(self.sample)

    def test_unknown_base_count_and_every_other_legacy_invariant_still_reject(self):
        for key,value in (('display_dma_memory',0x200171e4),('display_dma_memory',0x200045df),
                          ('display_dma_memory',0x200171e0+76800),('display_dma_count',1),
                          ('display_dma_peripheral',0x40013010),('sd_dma_count',1),
                          ('sd_dma_memory',0x20052e14),('dma1_3',0x10b3),('dma2_4',0),
                          ('edma_1',self.sample['raw']['edma_1']|1),('qspi_ctrl2',1),
                          ('debug_apb1_frz',0),('crm_cfg',0)):
            sample = copy.deepcopy(self.sample)
            sample['raw'][key] = value
            with self.subTest(key=key),self.assertRaises(ValueError): install_entry.qualify_masters(sample)
        for key in ('ble_state','ble_isr_active','overlay_owner'):
            sample = copy.deepcopy(self.sample);sample[key] = 1
            with self.assertRaises(ValueError): install_entry.qualify_masters(sample)

    def test_failed_original_trace_and_matching_display_build_recompute(self):
        paths = [audit.AREA/'sdk-000.log',audit.AREA/'sdk-001.log']
        rows = list(audit.parser.events(audit.AREA/'events.jsonl'))
        result = audit.trace(paths,rows,self.worker['dap'],True)
        self.assertEqual((result['native_calls'],result['target_writes'],result['native_close']),(1584,15,1))
        self.assertFalse(result['dp_restored'])
        self.assertEqual(audit.build_binding(self.store)['display_buffers'],list(install_entry.DISPLAY_BUFFERS))

    def test_missing_close_extra_reset_and_journal_drift_reject(self):
        class Text:
            def __init__(self,text): self.text = text
            def open(self,**kwargs): return io.StringIO(self.text)
        original = [(audit.AREA/('sdk-%03d.log'%i)).read_text(encoding='utf-8') for i in range(2)]
        rows = list(audit.parser.events(audit.AREA/'events.jsonl'))
        for altered in (original[1]+'\nJLINK_Reset()\n',original[1].replace('JLINK_Close(','MISSING_Close(')):
            with self.assertRaises(ValueError):
                audit.trace([Text(original[0]),Text(altered)],rows,self.worker['dap'],True)
        changed = copy.deepcopy(rows)
        next(row for row in changed if row['event']=='ap-call-returned')['rc'] = -1
        with self.assertRaises(ValueError):
            audit.trace([Text(x) for x in original],changed,self.worker['dap'],True)
        with self.assertRaises(ValueError):
            audit.trace([Text(x) for x in original],rows,self.worker['dap'],False)


if __name__=='__main__': unittest.main()
