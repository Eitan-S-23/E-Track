import copy
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
import p34_install_offline_audit as audit
from p34_eeprom_wire_model import Clock,Slave


class Tests(unittest.TestCase):
    def test_segment_plan_exact_positions_and_immutable_geometry(self):
        assets={name:path.read_bytes() for name,path in audit.host.ASSETS.items()}
        oracle=audit.host.cli.Store(ROOT).read(ROOT/'.cache/p34-confirm-page2/result.json')['dll']
        dll,function=audit.host.confirm.bind(Path(oracle['path']))
        plan=audit.draft(function,assets['bcb'],assets['boot'],assets['image'])
        segments=list(audit.segments(assets,plan,0x1000000,0x05fa0304))
        self.assertEqual(len(segments),719)
        for index,name in ((1,'retained-entry'),(23,'before-bcb'),(27,'before-candidate-backup'),
                           (192,'state-before'),(193,'flash-0'),(495,'flash-302'),(496,'eeprom-0'),
                           (525,'eeprom-29'),(526,'after-boot'),(712,'state-after'),
                           (713,'after-bcb'),(717,'reset'),(718,'release'),(719,'health')):
            self.assertEqual(segments[index-1]['name'],name)
        self.assertEqual(len(segments[0]['stores']),12)
        self.assertEqual(len(segments[716]['stores']),7)
        self.assertEqual(len(segments[717]['stores']),6)
        self.assertEqual(sum('eeprom_archive' in s for s in segments),22)

    def test_partition_return_boundary_and_gap_rejection(self):
        rows=[dict(event='first'),dict(event='online-log-switch-returned',old=0,new=1),
              dict(event='second'),dict(event='online-log-switch-returned',old=1,new=2),dict(event='third')]
        def stream(values): return io.StringIO(''.join(json.dumps(r)+'\n' for r in values))
        result=list(audit.partitions(stream(rows)))
        self.assertEqual([len(r) for r in result],[1,2,2])
        self.assertEqual(result[1][0]['event'],'online-log-switch-returned')
        rows[3]['new']=3
        with self.assertRaises(ValueError): list(audit.partitions(stream(rows)))

    def model_wire(self,kind,address=0,payload=b'',size=0):
        clock=Clock();data=bytes(range(256));slave=Slave(clock,data)
        output=0x18c0
        rows=[dict(event='recovery-word-read',address=audit.gpio.INPUT,value=output)]
        for at,value in audit.eeprom.stores(kind,address,payload,size):
            rows.append(dict(event='recovery-word-write-attempt',address=at,value=value))
            slave.set(6 if value==0x40 else 7,int(at==audit.gpio.SET))
            output=output|value if at==audit.gpio.SET else output&~value
            rows.append(dict(event='recovery-word-write-returned',address=at,value=value))
            rows.append(dict(event='recovery-word-read',address=audit.gpio.OUTPUT,value=output))
            physical=(output&~0xc0)|(slave.physical(6)<<6)|(slave.physical(7)<<7)
            rows.append(dict(event='recovery-word-read',address=audit.gpio.INPUT,value=physical))
            clock.sleep(.00001)
        return rows,data

    def test_wire_decodes_both_slots_pages_and_ack(self):
        for kind,address,payload,size in [('read',0,b'',64),('read',64,b'',64),('read',56,b'',8),
                                          ('page',56,b'12345678',0),('ack',0,b'',0)]:
            rows,data=self.model_wire(kind,address,payload,size)
            expected=data[address:address+size] if kind=='read' else b''
            self.assertEqual(audit.wire(rows,kind,address,payload,size,0x18c0),expected)

    def test_wire_and_chunk_negative_oracles(self):
        rows,_=self.model_wire('read',64,size=64)
        changed=copy.deepcopy(rows)
        next(r for r in changed if r['event']=='recovery-word-read' and r['address']==audit.gpio.OUTPUT)['value']^=1
        with self.assertRaises(ValueError): audit.wire(changed,'read',64,b'',64,0x18c0)
        with self.assertRaises(ValueError): audit.wire(rows,'read',0,b'',64,0x18c0)
        chunk=[dict(event='recovery-chunk-read-returned',address=0x8000000,data_hex='01020304')]
        self.assertEqual(audit.chunks(chunk,0x8000000,4),bytes([1,2,3,4]))
        with self.assertRaises(ValueError): audit.chunks(chunk*2,0x8000000,4)
        with self.assertRaises(ValueError): audit.chunks(chunk,0x8000000,8)

    def test_physical_idle_and_boundary_witnesses_are_mandatory(self):
        rows,_=self.model_wire('read',0,size=64)
        with self.assertRaises(ValueError): audit.wire(rows[1:],'read',0,b'',64,0x18c0)
        changed=copy.deepcopy(rows)
        changed[-1]['value']&=~0x80
        with self.assertRaises(ValueError): audit.wire(changed,'read',0,b'',64,0x18c0)
        with self.assertRaises(ValueError): audit.wire(rows[:-1],'read',0,b'',64,0x18c0)
        changed=copy.deepcopy(rows)
        first=next(i for i,r in enumerate(changed) if r['event']=='recovery-word-read' and r['address']==audit.gpio.INPUT and i>0)
        changed[first]['value']|=0x80
        with self.assertRaises(ValueError): audit.wire(changed,'read',0,b'',64,0x18c0)

    def test_asset_oracle_helper_and_missing_consumed_input_reject(self):
        frozen=[dict(path=name,bytes=4,sha256='a'*64) for name in ('asset.bin','oracle.dll','helper.py')]
        self.assertEqual(audit.bind_records(frozen,copy.deepcopy(frozen),['asset.bin','oracle.dll']),frozen)
        for index in range(3):
            changed=copy.deepcopy(frozen);changed[index]['sha256']='b'*64
            with self.assertRaises(ValueError): audit.bind_records(frozen,changed,[])
        with self.assertRaises(ValueError): audit.bind_records(frozen,frozen,['unbound-helper.py'])

    def test_actual_frozen_cell_binds_all_consumed_inputs(self):
        store=audit.host.cli.Store(ROOT)
        plan=store.read(ROOT/'.cache/p34-recovery-install2/plan.json')
        oracle=store.read(ROOT/'.cache/p34-confirm-page2/result.json')['dll']
        self.assertEqual(audit.source_bindings(store,plan,oracle),plan['inputs'])


if __name__=='__main__': unittest.main()
