from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'Tools/ota'))
sys.path.insert(0,str(ROOT/'tests/boot'))
import test_p34_recovery_ports as model
from recovery_confirm import gpio_read as read

class ReadTests(unittest.TestCase):
    def model(self):
        clock=model.Clock();slave=model.Slave(clock,model.BEFORE+b'R'*128)
        sdk=model.SDK(slave);rows=[]
        emit=lambda event,**kw:rows.append(dict(event=event,**kw))
        words=model.Words(model.Dap(sdk),emit,reads=model.gpio.READS,write_allowed=model.gpio.allowed_write,
                          seconds=600,clock=clock,guard=lambda fn,*a,**kw:fn(*a))
        pins=model.gpio.Pins(words,sdk.original,lambda:True)
        return clock,slave,sdk,words,pins,read.Read64(pins,emit,clock=clock,sleep=clock.sleep),rows

    def test_native_read_and_decoder_preserve_all_eeprom_bytes(self):
        clock,slave,sdk,words,pins,probe,rows=self.model()
        result=probe.run()
        raw=bytes.fromhex(result['raw_hex'])
        decoded=read.wire_trace(rows,raw,sdk.original[model.gpio.OUTPUT])
        self.assertEqual(raw,model.BEFORE[:64])
        self.assertEqual(slave.data,model.BEFORE+b'R'*128)
        self.assertEqual(slave.segments,[(0xa0,0),(0xa1,)])
        self.assertEqual(slave.master_acks,[0]*63+[1])
        self.assertEqual(result['gpio_stores'],decoded['gpio_stores'])
        self.assertFalse(result['physical_waveform_timing_qualified'])
        print('HOST_MODEL_CALLS',len(sdk.calls),'GPIO_STORES',words.writes,'READS',words.read_count)
        before=len(sdk.calls)
        with self.assertRaises(ValueError): probe.run()
        self.assertEqual(before,len(sdk.calls))

    def test_page_and_ack_interfaces_are_unavailable_without_io(self):
        _,_,sdk,_,_,probe,_=self.model()
        for fn in (lambda:probe.wire.page(0,b'\x00'*8,120),lambda:probe.wire.ack(30)):
            with self.assertRaises(ValueError): fn()
        self.assertFalse(sdk.calls)

    def test_read_fault_expiry_and_missing_owner_never_retry_or_cleanup(self):
        for fault in ('native','expired','owner','sleep'):
            with self.subTest(fault=fault):
                clock,slave,sdk,words,pins,probe,rows=self.model()
                if fault=='native': sdk.fail_call=100
                if fault=='expired': clock.value=301
                if fault=='owner': pins.owner=lambda:False
                if fault=='sleep': probe.wire.sleep=lambda _:None
                with self.assertRaises((ValueError,OSError)): probe.run()
                count=len(sdk.calls)
                with self.assertRaises(ValueError): probe.run()
                self.assertEqual(count,len(sdk.calls))
                self.assertEqual(slave.data,model.BEFORE+b'R'*128)
                with self.assertRaises(ValueError): read.wire_trace(rows,model.BEFORE[:64],sdk.original[model.gpio.OUTPUT])

    def test_decoder_rejects_different_bytes_gpio_store_return_or_missing_stop(self):
        _,_,sdk,_,_,probe,rows=self.model()
        result=probe.run();raw=bytes.fromhex(result['raw_hex']);original=sdk.original[model.gpio.OUTPUT]
        for fault in ('raw','write-scope','return','latch','end','duplicate'):
            with self.subTest(fault=fault):
                changed=[dict(row) for row in rows];actual=raw
                if fault=='raw': actual=bytes([raw[0]^1])+raw[1:]
                if fault=='write-scope':
                    next(r for r in changed if r['event']=='recovery-word-write-attempt')['address']=0x08010000
                if fault=='return': changed.remove(next(r for r in changed if r['event']=='recovery-word-write-returned'))
                if fault=='latch':
                    next(r for r in changed if r['event']=='recovery-word-read' and r['address']==model.gpio.OUTPUT)['value']^=1
                if fault=='end': changed.pop()
                if fault=='duplicate': changed.insert(1,changed[0])
                with self.assertRaises(ValueError): read.wire_trace(changed,actual,original)

    def test_decoder_rejects_out_of_interval_gpio_writes(self):
        _,_,sdk,_,_,probe,rows=self.model()
        raw=bytes.fromhex(probe.run()['raw_hex'])
        extra=dict(event='recovery-word-write-attempt',address=model.gpio.SET,value=0x40)
        for changed in ([extra]+rows,rows+[extra]):
            with self.assertRaises(ValueError): read.wire_trace(changed,raw,sdk.original[model.gpio.OUTPUT])

    def sample_indices(self,rows):
        output=0xc0;clock=-1;indices={}
        for index,row in enumerate(rows):
            if row['event']=='recovery-word-write-returned':
                old=output
                output=(output|row['value']) if row['address']==model.gpio.SET else output&~row['value']
                if not old&0x40 and output&0x40: clock+=1
            if row['event']=='recovery-word-read' and row['address']==model.gpio.INPUT and output&0x40:
                indices.setdefault(clock,[]).append(index)
        return indices

    def test_review_r_w_bit_last_nack_and_contradictory_samples_fail_closed(self):
        _,_,sdk,_,_,probe,rows=self.model()
        raw=bytes.fromhex(probe.run()['raw_hex'])
        indices=self.sample_indices(rows)
        for fault in ('write-command','last-ack','low-scl','mixed-sda','slave-ack','start-level','stop-level','extra-flash'):
            with self.subTest(fault=fault):
                changed=[dict(row) for row in rows]
                if fault in ('write-command','last-ack'):
                    for index in indices[26 if fault=='write-command' else 603]: changed[index]['value']&=~0x80
                if fault=='low-scl': changed[indices[28][0]]['value']&=~0x40
                if fault=='mixed-sda': changed[indices[28][0]]['value']^=0x80
                if fault=='slave-ack':
                    for index in indices[8]: changed[index]['value']|=0x80
                if fault=='start-level': changed[indices[18][0]]['value']^=0x80
                if fault=='stop-level': changed[indices[604][-1]]['value']^=0x80
                if fault=='extra-flash':
                    changed.extend(dict(event=event,address=0x08010000,value=0) for event in
                                   ('recovery-word-write-attempt','recovery-word-write-returned'))
                with self.assertRaises(ValueError): read.wire_trace(changed,raw,sdk.original[model.gpio.OUTPUT])

    def test_every_start_stop_requires_fresh_pre_and_post_level_witnesses(self):
        _,_,sdk,_,_,probe,rows=self.model()
        raw=bytes.fromhex(probe.run()['raw_hex'])
        indices=self.sample_indices(rows)
        for clocks in ((-1,),(18,),(604,),(-1,18,604)):
            removed={index for clock in clocks for index in indices[clock]}
            with self.assertRaises(ValueError):
                read.wire_trace([row for i,row in enumerate(rows) if i not in removed],raw,sdk.original[model.gpio.OUTPUT])
        for clock in (-1,18,604):
            group=indices[clock]
            levels=[bool(rows[i]['value']&0x80) for i in group]
            first=levels[0]
            for select in (lambda level:level==first,lambda level:level!=first):
                removed={index for index,level in zip(group,levels) if select(level)}
                self.assertTrue(removed)
                with self.assertRaises(ValueError):
                    read.wire_trace([row for i,row in enumerate(rows) if i not in removed],raw,sdk.original[model.gpio.OUTPUT])


if __name__=='__main__': unittest.main()
