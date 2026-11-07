"""Native-Commander plan/oracle tests; no debugger or device is invoked."""
import copy
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Tools/ota/p51-acceptance'))
import state_chain as s


def inputs():
    image = bytearray(0x1000)
    image[0x126:0x12c] = bytes.fromhex('204640b070bd')
    for offset in (0x200, 0x208, 0x300, 0x308):
        image[offset:offset+4] = bytes.fromhex('00f000f8')
    struct.pack_into('<I', image, 0x408, 30317)
    base = bytes(image)
    struct.pack_into('<I', image, 0x408, 30319)
    images = dict(base=base, target=bytes(image))
    table = dict(bcb_arbiter=(0x08010100, 48), __StackLimit=(0x20056000, 0), __StackTop=(0x20058000, 0))
    table[s.m.SYMBOLS['main_loop']] = (0x08010480, 48)
    table[s.m.SYMBOLS['owner']] = (0x20050000, 1)
    def caller(address):
        return (' %08x: f000 f800 bl 8010100 <bcb_arbiter>\n'
                ' %08x: f000 f900 bl 8010130 <bcb_commit>\n'
                ' %08x: f000 f800 bl 8010100 <bcb_arbiter>\n') % (address, address+4, address+8)
    disassembly = dict(bcb_arbiter='push\t{r4, r5, r6, lr}\nsub\tsp, #256\n 08010128: b040 add sp, #256\n',
        ota_backup_stage_impl=caller(0x08010200) + 'mov.w r3, #4096\n str r3, [sp, #220]\n',
        _ZN3HAL15OTA_ConfirmBootEv=caller(0x08010300))
    tables = {role: copy.deepcopy(table) for role in images}
    text = {role: copy.deepcopy(disassembly) for role in images}
    return images, tables, text


def distinct_inputs():
    images, tables, text = inputs()
    target = bytearray(images['target'] + bytes(0x800))
    target[:16] = b'new-vector-table'
    for offset, size in ((0x126, 6), (0x200, 4), (0x208, 4), (0x300, 4), (0x308, 4)):
        target[offset+0x800:offset+0x800+size] = target[offset:offset+size]
        target[offset:offset+size] = bytes(size)
    images['target'] = bytes(target)
    tables['target']['bcb_arbiter'] = (0x08010900, 48)
    tables['target']['__StackLimit'] = (0x20054000, 0)
    tables['target']['__StackTop'] = (0x20056000, 0)
    for name, value in text['target'].items():
        for old, new in (('08010128', '08010928'), ('8010100', '8010900'),
                         ('8010130', '8010930'), ('080102', '08010a'), ('080103', '08010b')):
            value = value.replace(old, new)
        text['target'][name] = value
    return images, tables, text


def sample(points, phase, seq=None):
    role = 'base' if phase in s.PHASES[:2] else 'target'
    model, images = points['roles'][role], points['images']
    phase_index = s.PHASES.index(phase)
    state, tries = ((4, 0), (1, 3), (3, 2), (4, 0))[phase_index]
    seq = (100, 101, 125, 126)[phase_index] if seq is None else seq
    part = bytearray(64)
    part[:8] = b'ETBC\x01' + bytes((state, tries, 0))
    struct.pack_into('<H', part, 8, seq)
    struct.pack_into('<5I', part, 12, 0x1000, images['target']['size'], images['target']['crc'],
                     images['target']['version'], images['target' if phase == 'confirmed' else 'base']['version'])
    struct.pack_into('<3I', part, 32, images['base']['size'], images['base']['crc'], images['base']['version'])
    struct.pack_into('<I', part, 60, zlib.crc32(part[:60]))
    stack, offset = bytearray(8192), 8192-0x300
    stack[offset:offset+128] = part + b'\xff'*64
    struct.pack_into('<I', stack, offset+268, model['points'][phase]['savedLR'])
    data = dict(stack_original=bytes(stack), header_original=bytes.fromhex(images[role]['header']),
        dhcsr=struct.pack('<I', 0x20000), dhcsr_after=struct.pack('<I', 0x20000), freeze=struct.pack('<I', 0x1000))
    console = 'PC = %08X\nR0 = 00000001\nSP(R13)= %08X\n' % (model['epilogue'], model['lower']+offset)
    return data, console


def native_console(console, waits=2):
    automatic = 'J-Link>CPU halted.\nPC = 08010000\nR0 = FFFFFFFF\nSP(R13)= 00000000\n'
    return automatic * waits + 'J-Link>' + console + 'J-Link>Opening binary file for writing...\n'


class FakeMCU:
    def __init__(self, points, table, failure=None):
        self.out = ROOT / '.cache/p51-state-chain-test-unused'
        self.points, self.table, self.failure, self.commands = points, table, failure, []

    def inspect(self, role, label):
        return dict(role=role, registers=dict(freeze=0), storage=dict(journal=dict(expected_begin_durable=0)))

    def bind(self, role):
        return dict(table=self.table)

    def wait_boot(self, role):
        self.commands.append(('wait-boot', [role], {}))

    def execute(self, commands, reads, label, **kwargs):
        self.commands.append((label, commands, kwargs))
        if label == self.failure:
            raise RuntimeError('injected standard tool failure')
        data = {key: bytes(size) for key, size in reads.items()}
        console = ''
        if label.startswith('arm-'):
            phase = label.removeprefix('arm-')
            role = 'base' if phase in s.PHASES[:2] else 'target'
            call = self.points['roles'][role]['points'][phase]['call']
            words = [0]*10
            words[2] = (call & ~3) | (0x40000000 if call % 4 == 0 else 0x80000000) | 1
            data.update(fpb=struct.pack('<10I', *words), freeze=struct.pack('<I', 0x1000))
        elif label.startswith('capture-'):
            data, console = sample(self.points, label.removeprefix('capture-'))
            console = native_console(console)
        elif label == 'sd-idle-before-reset':
            console = native_console('PC = %08X\n' % self.table[s.m.SYMBOLS['main_loop']][0], waits=1)
            data['dhcsr'] = struct.pack('<I', 0x20000)
        for line in commands:
            if isinstance(line, str) and line.startswith('SetBP '):
                console += 'Breakpoint set @ addr %s (Handle = 1)\n' % line.split()[1].rstrip(',')
        return data, console, self.out / label


class FakeCommander:
    def __init__(self, mcu, deadline):
        self.mcu = mcu
        mcu.commands.append(('session-connect', [], {}))

    def execute(self, *args, **kwargs):
        return self.mcu.execute(*args, **kwargs)

    def close(self):
        self.mcu.commands.append(('session-close', [], {}))


class StateChainTests(unittest.TestCase):
    def setUp(self):
        self.images, self.tables, self.text = inputs()
        self.points = s.bind_points(self.images, self.tables, self.text)

    def test_real_call_order_and_opcode_binding(self):
        self.assertEqual(self.points['roles']['base']['points']['staged']['savedLR'], 0x0801020d)
        for mutate in ('image', 'frame', 'caller', 'candidate', 'commit'):
            images, tables, text = copy.deepcopy((self.images, self.tables, self.text))
            if mutate == 'image':
                images['base'] = images['base'][:0x200] + b'X' + images['base'][0x201:]
            else:
                name = 'bcb_arbiter' if mutate == 'frame' else 'ota_backup_stage_impl'
                old, new = dict(frame=('sp, #256', 'sp, #252'), caller=('8010100', '8010102'),
                    candidate=('#4096', '#1052672'), commit=('bcb_commit', 'other'))[mutate]
                text['base'][name] = text['base'][name].replace(old, new)
            with self.subTest(mutate=mutate), self.assertRaises(RuntimeError):
                s.bind_points(images, tables, text)

    def test_distinct_executables_use_each_roles_own_code_and_stack(self):
        images, tables, text = distinct_inputs()
        points = s.bind_points(images, tables, text)
        self.assertNotEqual(points['images']['base']['size'], points['images']['target']['size'])
        self.assertNotEqual(points['images']['base']['sha256'], points['images']['target']['sha256'])
        self.assertEqual(points['roles']['base']['epilogue'], 0x08010128)
        self.assertEqual(points['roles']['target']['epilogue'], 0x08010928)
        self.assertEqual(points['roles']['target']['lower'], 0x20054000)
        for phase, expected in zip(s.PHASES, (4, 1, 3, 4)):
            data, console = sample(points, phase)
            _, value = s.extract(data, console, points, phase)
            self.assertEqual(value['state'], expected)
            self.assertEqual(value['currentVersion'], 30319 if phase == 'confirmed' else 30317)

    def test_each_role_rejects_foreign_code_frame_and_symbols(self):
        for role in ('base', 'target'):
            for damage in ('opcode', 'frame', 'caller', 'symbols', 'foreign-disassembly'):
                images, tables, text = distinct_inputs()
                if damage == 'opcode':
                    offset = 0x200 if role == 'base' else 0xa00
                    image = bytearray(images[role])
                    image[offset] ^= 1
                    images[role] = bytes(image)
                elif damage == 'frame':
                    text[role]['bcb_arbiter'] = text[role]['bcb_arbiter'].replace('sp, #256', 'sp, #252')
                elif damage == 'caller':
                    text[role]['ota_backup_stage_impl'] = text[role]['ota_backup_stage_impl'].replace(
                        'bl 8010100' if role == 'base' else 'bl 8010900', 'bl 8010110')
                elif damage == 'symbols':
                    tables[role]['bcb_arbiter'] = (0x08010110, 48)
                else:
                    text[role] = text['target' if role == 'base' else 'base']
                with self.subTest(role=role, damage=damage), self.assertRaises(RuntimeError):
                    s.bind_points(images, tables, text)

    def test_all_four_observed_states(self):
        for phase, expected in zip(s.PHASES, (4, 1, 3, 4)):
            data, console = sample(self.points, phase)
            pair, value = s.extract(data, console, self.points, phase)
            self.assertEqual(len(pair), 128)
            self.assertEqual(value['state'], expected)

    def test_explicit_regs_disambiguates_automatic_waithalt_outputs(self):
        for phase in s.PHASES:
            data, console = sample(self.points, phase)
            expected = s.extract(data, console, self.points, phase)
            for waits in (1, 2):
                with self.subTest(phase=phase, waits=waits):
                    self.assertEqual(s.extract(data, native_console(console, waits), self.points, phase), expected)
                    self.assertEqual(s.extract(data, native_console(console, waits).replace('\n', '\r\n'),
                                               self.points, phase), expected)

    def test_missing_duplicate_and_incomplete_explicit_regs_fail_closed(self):
        data, console = sample(self.points, 'beforeBackup')
        automatic = native_console(console).split('J-Link>PC')[0]
        for damaged in (automatic, automatic.split('J-Link>CPU halted.')[0] +
                'J-Link>CPU halted.\n' + console,
                native_console(console) + native_console(console),
                native_console(console.replace('SP(R13)', 'other')),
                native_console(console + 'R0 = 00000001\n'),
                native_console(console).replace('J-Link>PC =', 'J-Link>PC invalid=')):
            with self.subTest(console=damaged), self.assertRaises(RuntimeError):
                s.extract(data, damaged, self.points, 'beforeBackup')

    def test_explicit_regs_cannot_borrow_correct_pc_or_frame_from_waithalt(self):
        data, console = sample(self.points, 'beforeBackup')
        for damaged in (console.replace('PC = 08010128', 'PC = 0801012A'),
                        console.replace('SP(R13)= 20057D00', 'SP(R13)= 20050000')):
            with self.subTest(console=damaged), self.assertRaises(RuntimeError):
                s.extract(data, 'J-Link>CPU halted.\n' + console + native_console(damaged),
                          self.points, 'beforeBackup')

    def test_wrong_caller_header_stack_and_halt_rejected(self):
        for phase in s.PHASES:
            for damage in ('caller', 'header', 'short', 'halt-before', 'halt-after', 'register', 'duplicate'):
                data, console = sample(self.points, phase)
                if damage == 'caller':
                    stack = bytearray(data['stack_original'])
                    struct.pack_into('<I', stack, 8192-0x300+268, 0x08010001)
                    data['stack_original'] = bytes(stack)
                elif damage == 'header':
                    data['header_original'] = bytes(96)
                elif damage == 'short':
                    data['stack_original'] = data['stack_original'][:-1]
                elif damage.startswith('halt'):
                    data['dhcsr' if damage == 'halt-before' else 'dhcsr_after'] = bytes(4)
                elif damage == 'register':
                    console = console.replace('R0 = 00000001', 'R0 = FFFFFFFF')
                else:
                    console += console
                with self.subTest(phase=phase, damage=damage), self.assertRaises(RuntimeError):
                    s.extract(data, console, self.points, phase)

    def test_rechecks_crc_and_identity_not_only_state(self):
        for offset, value in ((12, 0x101000), (16, 8), (20, 8), (24, 30320), (28, 30313),
                              (32, 8), (36, 8), (40, 30316)):
            data, console = sample(self.points, 'staged')
            stack = bytearray(data['stack_original'])
            pos = 8192-0x300
            struct.pack_into('<I', stack, pos+offset, value)
            struct.pack_into('<I', stack, pos+60, zlib.crc32(stack[pos:pos+60]))
            data['stack_original'] = bytes(stack)
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                s.extract(data, console, self.points, 'staged')

    def test_arbitration_wrap_and_rejects_bad_crc(self):
        def block(seq):
            data, console = sample(self.points, 'staged', seq)
            return s.extract(data, console, self.points, 'staged')[0][:64]
        for a, b, winner in ((0, 65535, 1), (65535, 0, 2), (5, 5, 1), (3, 4, 2)):
            pair = block(a) + block(b)
            self.assertEqual(s.bcb_pair(pair, winner)['active'], winner)
            with self.assertRaises(RuntimeError):
                s.bcb_pair(pair, 3-winner)
        with self.assertRaises(RuntimeError):
            s.bcb_pair(bytes(128), 1)

    def run_fake(self, channel, failure=None, ready=None):
        fake = FakeMCU(self.points, self.tables['base'], failure)
        collector = s.Collector(fake, self.points, 999999999.0)
        with patch.object(s.h, 'save'), patch.object(s.h, 'raw'), patch.object(s.h, 'record', return_value={}), \
                patch.object(s, 'Commander', FakeCommander):
            try:
                result = collector.run(channel, ready or (lambda before, armed: None))
            except RuntimeError as error:
                return fake, collector, error
        return fake, collector, result

    def test_sd_sequence_uses_one_safe_reset_and_restores_debugger(self):
        fake, collector, result = self.run_fake('sd')
        self.assertIsInstance(result, dict)
        self.assertEqual(result['stateChain'], [4, 1, 3, 4])
        labels = [row[0] for row in fake.commands]
        self.assertLess(labels.index('sd-idle-before-reset'), labels.index('arm-testBoot'))
        self.assertEqual(sum(cmd == 'r' for _, lines, _ in fake.commands for cmd in lines), 1)
        self.assertFalse(collector.touched)
        self.assertFalse(result['timingCredit'])
        self.assertEqual(labels.count('session-connect'), 1)
        self.assertEqual(labels.count('session-close'), 1)
        self.assertLess(labels.index('debug-cleanup'), labels.index('session-close'))
        self.assertTrue(any(isinstance(line, str) and line.startswith('ClearBP ') for _, lines, _ in fake.commands for line in lines))

    def test_ble_sequence_never_resets_or_calls_sd_idle(self):
        fake, _, result = self.run_fake('ble')
        self.assertIsInstance(result, dict)
        self.assertNotIn('sd-idle-before-reset', [row[0] for row in fake.commands])
        self.assertFalse(any(cmd == 'r' for _, lines, _ in fake.commands for cmd in lines))

    def test_failure_at_each_device_step_keeps_cleanup_and_never_replays(self):
        labels = [row[0] for row in self.run_fake('sd')[0].commands if row[0] not in
                  ('debug-precheck', 'debug-cleanup', 'cleanup-state', 'session-connect', 'session-close', 'wait-boot')]
        for label in labels:
            fake, _, error = self.run_fake('sd', failure=label)
            with self.subTest(label=label):
                self.assertIsInstance(error, RuntimeError)
                observed = [row[0] for row in fake.commands]
                self.assertEqual(observed.count(label), 1)
                self.assertEqual(observed[-2:], ['debug-cleanup', 'session-close'])
                self.assertNotIn('wait-boot', observed)
                if label == 'sd-idle-before-reset':
                    self.assertNotIn('arm-testBoot', observed)

    def test_no_reset_without_proved_idle_and_no_duplicate_arm(self):
        fake = FakeMCU(self.points, self.tables['base'])
        collector = s.Collector(fake, self.points, 999999999.0)
        collector.samples = [{'state': 4}, {'state': 1}]
        with self.assertRaises(RuntimeError):
            collector.arm('testBoot', reset=True)
        self.assertEqual(fake.commands, [])
        collector.samples = []
        collector.armed = 'beforeBackup'
        with self.assertRaises(RuntimeError):
            collector.arm('beforeBackup')

    def test_snapshot_uses_one_connection_and_no_flash_commands(self):
        fake, _, _ = self.run_fake('sd')
        for label, commands, _ in fake.commands:
            for command in commands:
                if isinstance(command, str):
                    self.assertFalse(command.lower().startswith(('load', 'erase', 'setpc', 'h\n')))
            if label.startswith('capture-'):
                names = [row[0] for row in commands if isinstance(row, tuple)]
                self.assertEqual(names, ['dhcsr', 'stack_original', 'header_original', 'freeze', 'dhcsr_after'])
                self.assertEqual(commands.count('regs'), 1)
                self.assertEqual(sum(isinstance(row, str) and row.startswith('WaitHalt ') for row in commands), 2)


if __name__ == '__main__':
    unittest.main()
