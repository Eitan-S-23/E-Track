"""Offline rejection controls for P1-7 timing; no device operations."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('p17', ROOT/'Tools/acceptance/p17_observe.py')
p17 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p17)


def fixture():
    addresses = dict(rtt=1, pd2=2, vtor=3, crm=4, boot_millis=5, boot_clock=6)
    events = [dict(kind='Reset',start_ms=0,end_ms=10),dict(kind='Go',start_ms=10,end_ms=11)]
    for i in range(60):
        t = 20+i*100
        for key, address in addresses.items():
            values = dict(pd2=0 if i < 10 else 4, vtor=0 if i < 12 else 0x08010800,
                          boot_millis=i*100, boot_clock=288000000)
            data = (b'SEGGER RTT'+b'\0'*6 if i >= 12 else b'\0'*16) if key == 'rtt' else (
                b'\0'*4+(1+(72 << 6)+(1 << 16)).to_bytes(4,'little')+(8).to_bytes(4,'little')
                if key == 'crm' else values[key].to_bytes(4,'little'))
            events.append(dict(kind='ReadMemEx_64',address=address,size=len(data),data=data,start_ms=t,end_ms=t+1))
    return events, addresses


class Tests(unittest.TestCase):
    def test_native_exact_bytes(self):
        log = ('T1 000:001.000 JLINK_ReadMemEx_64(0x20000000, 0x4 Bytes, ...)\n'
               'T1 000:002.000   Data:  53 45 47 47\n'
               'T1 000:003.000 - 2.000ms returns 4 (0x4)\n')
        value, = p17.sdk_events(log)
        self.assertEqual(value['data'], b'SEGG')
        self.assertEqual(value['end_ms'], 3)

    def test_native_truncation_rejected(self):
        with self.assertRaises(RuntimeError):
            p17.sdk_events('T1 000:001.000 JLINK_ReadMemEx_64(0x20000000, 0x4 Bytes, ...)\n')

    def test_short_read_rejected(self):
        with self.assertRaises(RuntimeError):
            p17.sdk_events('T1 000:001.000 JLINK_ReadMemEx_64(0x20000000, 0x4 Bytes, ...)\n'
                           'T1 000:002.000 - 1.000ms returns 0 (0x0)\n')

    def test_clock_reversal_rejected(self):
        with self.assertRaises(RuntimeError):
            p17.sdk_events('T1 000:002.000 x\nT1 000:001.000 y\n')

    def test_nominal_and_scope(self):
        events, addresses = fixture()
        value = p17.summarize(events,addresses,60)
        for key in ('startup','powerHold','clock','tickCalibration'):
            self.assertEqual(value[key]['result'],'PASS')
        self.assertEqual(value['recoveryKey'],'NOT_OBSERVED')
        self.assertEqual(value['batteryStartup'],'NOT_OBSERVED')

    def test_delayed_start_fails(self):
        events, addresses = fixture()
        for event in events:
            if event.get('address') == addresses['rtt'] and event['start_ms'] < 1720:
                event['data'] = b'\0'*16
        self.assertEqual(p17.summarize(events,addresses,60)['startup']['result'],'PRODUCT_FAIL')

    def test_power_drop_fails(self):
        events, addresses = fixture()
        [event for event in events if event.get('address') == addresses['pd2']][25]['data'] = b'\0'*4
        self.assertEqual(p17.summarize(events,addresses,60)['powerHold']['result'],'PRODUCT_FAIL')

    def test_stale_signature_rejected(self):
        events, addresses = fixture()
        [event for event in events if event.get('address') == addresses['rtt']][0]['data'] = b'SEGGER RTT'+b'\0'*6
        with self.assertRaises(RuntimeError):
            p17.summarize(events,addresses,60)

    def test_missing_sample_rejected(self):
        events, addresses = fixture()
        with self.assertRaises(RuntimeError):
            p17.summarize(events[:-1],addresses,60)

    def test_repeated_reset_rejected(self):
        events, addresses = fixture()
        events.insert(0,copy.deepcopy(events[0]))
        with self.assertRaises(RuntimeError):
            p17.summarize(events,addresses,60)

    def test_accelerated_tick_not_pass(self):
        events, addresses = fixture()
        for event in events:
            if event.get('address') == addresses['boot_millis']:
                event['data'] = (int.from_bytes(event['data'],'little')*36).to_bytes(4,'little')
        self.assertNotEqual(p17.summarize(events,addresses,60)['tickCalibration']['result'],'PASS')

    def test_bounded_native_sampling(self):
        _, addresses = fixture()
        self.assertEqual(len(p17.commands(addresses,200)),1400)
        with self.assertRaises(RuntimeError):
            p17.commands(addresses,100000)

    def test_wrong_pll_multiplier_fails(self):
        events, addresses = fixture()
        for event in events:
            if event.get('address') == addresses['crm']:
                event['data'] = b'\0'*4+(1+(36 << 6)+(1 << 16)).to_bytes(4,'little')+(8).to_bytes(4,'little')
        self.assertEqual(p17.summarize(events,addresses,60)['clock']['result'],'PRODUCT_FAIL')

    def test_invalid_pll_rejected(self):
        with self.assertRaises(RuntimeError):
            p17.decode_clock(b'\0'*8+(8).to_bytes(4,'little'))


if __name__ == '__main__':
    unittest.main()
