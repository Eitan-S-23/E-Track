from pathlib import Path
import io
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'));sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_install_strict_audit as strict
import test_p34_install_offline_audit as model


class Tests(unittest.TestCase):
    def test_valid_wire_and_every_terminal_low_rejected(self):
        for kind,address,payload,size in (('read',0,b'',64),('read',64,b'',64),('read',56,b'',8),
                                          ('page',56,b'12345678',0),('ack',0,b'',0)):
            rows,data=model.Tests().model_wire(kind,address,payload,size)
            wanted=data[address:address+size] if kind=='read' else b''
            self.assertEqual(strict.wire(rows,kind,address,payload,size,0x18c0),wanted)
            for levels in ((0x1840,),(0x18c0,0x1840,0x18c0),(0x1840,0x18c0)):
                extra=[]
                for level in levels:
                    extra += [dict(event='recovery-word-read',address=strict.legacy.gpio.OUTPUT,value=0x18c0),
                              dict(event='recovery-word-read',address=strict.legacy.gpio.INPUT,value=level)]
                # Preserve the exact legacy reproducer without changing it.
                self.assertEqual(strict.LEGACY_WIRE(rows+extra,kind,address,payload,size,0x18c0),wanted)
                with self.assertRaisesRegex(ValueError,'after STOP'):
                    strict.wire(rows+extra,kind,address,payload,size,0x18c0)

    def test_continuation_plan_719_segments_and_exact_partial_preimage(self):
        a=strict.legacy
        assets={name:path.read_bytes() for name,path in a.host.ASSETS.items()}
        oracle=a.host.cli.Store(ROOT).read(ROOT/'.cache/p34-confirm-page2/result.json')['dll']
        dll,function=a.host.confirm.bind(Path(oracle['path']))
        plan=a.draft(function,assets['bcb'],assets['boot'],assets['image'])
        specs=list(strict.segments(assets,plan,0x1000000,0x05fa0304))
        self.assertEqual(len(specs),719)
        for index,name in ((1,'retained-entry'),(2,'completed-prefix-0'),(4,'completed-prefix-2'),
                           (5,'before-boot'),(26,'before-bcb'),(195,'state-before'),(196,'flash-3'),
                           (495,'flash-302'),(496,'eeprom-0'),(717,'reset'),(719,'health')):
            self.assertEqual(specs[index-1]['name'],name)
        self.assertEqual(b''.join(s['archive'][3] for s in specs if s['name']=='before-envelope'),
                         assets['image'][:6144]+assets['envelope'][6144:])
        self.assertFalse(any(s['name'] in ('flash-0','flash-1','flash-2') for s in specs))

    def test_existing_closed_pair_accepts_strict_terminal_idle(self):
        area=ROOT/'.cache/p34-recovery-install2'
        expected=(area/'before-bcb.bin').read_bytes()
        original=strict.legacy.host.cli.Store(ROOT).read(area/'worker.json')['component_results']['entry']['state_samples'][-1]['raw']['gpiob_output']
        with (area/'events.jsonl').open(encoding='utf-8') as stream:
            for index,rows in enumerate(strict.legacy.partitions(stream)):
                if 23<=index<=26:
                    offset=(index-23)*64;address=(index-23)%2*64
                    self.assertEqual(strict.wire(rows,'read',address,b'',64,original),expected[offset:offset+64])
                if index>=26:break

    def test_early_prefix_and_scope_input_drift_rejected(self):
        import p34_install_continue as current
        area=ROOT/'.cache/model-strict-early'
        for changed in (None,'events.jsonl','plan.json'):
            altered=set()
            def record(path):
                path=Path(path)
                return dict(path=str(path),bytes=1,sha256='new' if path.name in altered else 'old')
            store=SimpleNamespace(checked=lambda p:p,read=lambda p:dict(inputs=[],scope=current.SCOPE))
            def delegated(*args):
                if changed:altered.add(changed)
                return {}
            old_wire,old_segments=strict.legacy.wire,strict.legacy.segments
            with mock.patch.object(current,'sources',return_value=[]), \
                 mock.patch.object(current,'ASSETS',dict(image=SimpleNamespace(read_bytes=lambda:b'x'*6144))), \
                 mock.patch.object(strict.legacy,'record',side_effect=record), \
                 mock.patch.object(strict.legacy,'partitions',return_value=iter([[]]*5)), \
                 mock.patch.object(strict.legacy,'chunks',return_value=b'x'*2048), \
                 mock.patch.object(strict.legacy,'audit',side_effect=delegated), \
                 mock.patch.object(Path,'open',return_value=io.StringIO('')):
                if changed:
                    with self.assertRaisesRegex(ValueError,'early prefix/scope'):strict.audit(store,area)
                else:self.assertEqual(len(strict.audit(store,area)['strict_early_inputs']),2)
            self.assertIs(strict.legacy.wire,old_wire)
            self.assertIs(strict.legacy.segments,old_segments)


if __name__=='__main__':unittest.main()
