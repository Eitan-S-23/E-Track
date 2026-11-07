"""P5 BCB observation through standard Commander and the existing MCU owner.

This module does not start an import, grant device authority, or replace the
formal contract gate. The caller owns admission, the phone and user notices.
"""
import hashlib
import re
import struct
import sys
import time
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'p34-acceptance'))
import live_host as h
import live_mcu as m

PHASES = ('beforeBackup', 'staged', 'testBoot', 'confirmed')
SYMBOLS = ('bcb_arbiter', 'ota_backup_stage_impl', '_ZN3HAL15OTA_ConfirmBootEv')
FPB = 0xe0002000
FREEZE = m.REGISTERS['freeze']


def calls(text, symbol):
    pattern = (r'(?m)^\s*([0-9a-f]{7,8}):\s+([0-9a-f]{4}) ([0-9a-f]{4})'
               r'\s+bl\s+([0-9a-f]+) <' + re.escape(symbol) + r'>\s*$')
    return [(int(pc, 16), int(target, 16), bytes.fromhex(lo)[::-1] + bytes.fromhex(hi)[::-1])
            for pc, lo, hi, target in re.findall(pattern, text)]


def bind_points(images, tables, disassembly):
    # MCU.bind verifies each finalized executable against its own pinned ELF.
    # Real code deltas may relocate callers and stacks between the two roles.
    result = dict(roles={}, images={})
    for role in ('base', 'target'):
        image, table, text = images[role], tables[role], disassembly[role]
        epilogue = re.findall(r'(?m)^\s*([0-9a-f]{7,8}):\s+b040\s+add\s+sp, #256', text['bcb_arbiter'])
        h.require(len(epilogue) == 1 and 'sub\tsp, #256' in text['bcb_arbiter'] and
                  'push\t{r4, r5, r6, lr}' in text['bcb_arbiter'], 'unrecognized arbiter stack frame')
        end = int(epilogue[0], 16)
        h.require(image[end-0x08010000-2:end-0x08010000+4] == bytes.fromhex('204640b070bd'),
                  'arbiter epilogue differs from finalized image')
        stage = calls(text['ota_backup_stage_impl'], 'bcb_arbiter')
        stage_commit = calls(text['ota_backup_stage_impl'], 'bcb_commit')
        confirm = calls(text['_ZN3HAL15OTA_ConfirmBootEv'], 'bcb_arbiter')
        confirm_commit = calls(text['_ZN3HAL15OTA_ConfirmBootEv'], 'bcb_commit')
        h.require(len(stage) == len(confirm) == 2 and len(stage_commit) == len(confirm_commit) == 1,
                  'ambiguous real commit/readback callers')
        h.require(stage[0][0] < stage_commit[0][0] < stage[1][0] and
                  confirm[0][0] < confirm_commit[0][0] < confirm[1][0], 'commit ordering changed')
        h.require(re.search(r'mov.w\s+r3, #4096[^\r\n]*[\r\n]+[^\r\n]*str\s+r3, \[sp, #220\]',
                            text['ota_backup_stage_impl']), 'candidate payload address instruction changed')
        points = dict(zip(PHASES, (stage[0], stage[1], confirm[0], confirm[1])))
        for pc, destination, opcode in points.values():
            h.require(destination == table['bcb_arbiter'][0] and
                      image[pc-0x08010000:pc-0x08010000+4] == opcode, 'caller not in finalized image')
        lower, upper = table['__StackLimit'][0], table['__StackTop'][0]
        h.require(upper - lower == 8192, 'unexpected stack reservation')
        result['roles'][role] = dict(epilogue=end, lower=lower, upper=upper,
            points={phase: dict(call=pc, savedLR=(pc+4) | 1, opcode=opcode.hex())
                    for phase, (pc, _, opcode) in points.items()})
        result['images'][role] = dict(version=struct.unpack_from('<I', image, 0x408)[0],
            size=len(image), crc=zlib.crc32(image), sha256=hashlib.sha256(image).hexdigest(),
            header=image[0x400:0x460].hex())
    h.require(result['images']['base']['version'] < result['images']['target']['version'], 'not an upgrade')
    return result


def bind(mcu):
    out = h.fresh(mcu.out / 'state-bindings')
    images, tables, text = {}, {}, {}
    for role in ('base', 'target'):
        bound = mcu.bind(role)
        images[role], tables[role], text[role] = bound['image'].read_bytes(), bound['table'], {}
        for i, symbol in enumerate(SYMBOLS):
            raw = h.command(out, role + '-%d' % i,
                [mcu.tool('objdump'), '-d', '--disassemble=' + symbol,
                 h.pinned(mcu.plan['images'][role]['elf'])], mcu.env, seconds=30)
            text[role][symbol] = raw.decode('utf-8')
    points = bind_points(images, tables, text)
    h.save(out / 'points.json', points)
    return points


def register(console, name):
    # WaitHalt prints registers too. Only the explicit regs response starts
    # with J-Link>PC; never pick an arbitrary last register from a whole batch.
    starts = list(re.finditer(r'(?m)^J-Link>PC\b', console))
    if starts:
        h.require(len(starts) == 1, 'ambiguous explicit regs blocks')
        console = console[starts[0].start():]
        boundary = re.search(r'(?m)^J-Link>', console[len('J-Link>'):])
        if boundary:
            console = console[:len('J-Link>') + boundary.start()]
    else:
        h.require(not re.search(r'(?m)^J-Link>CPU halted\.', console), 'missing explicit regs block')
    pattern = r'SP\(R13\)\s*=\s*([0-9A-Fa-f]{8})' if name == 'SP' else r'\b' + name + r'\s*=\s*([0-9A-Fa-f]{8})'
    found = re.findall(pattern, console)
    h.require(len(found) == 1, 'missing/ambiguous register: ' + name)
    return int(found[0], 16)


def bcb_pair(raw, selected):
    h.require(len(raw) == 128 and selected in (1, 2), 'invalid BCB pair/result')
    parts = (raw[:64], raw[64:])
    valid = [part[:5] == b'ETBC\x01' and zlib.crc32(part[:60]) == int.from_bytes(part[60:], 'little')
             for part in parts]
    h.require(any(valid), 'both BCB copies invalid')
    if all(valid):
        seq = [int.from_bytes(part[8:10], 'little') for part in parts]
        expected = 1 if (seq[0] - seq[1]) & 0xffff < 0x8000 else 2
    else:
        expected = 1 if valid[0] else 2
    h.require(selected == expected, 'raw BCB arbitration disagrees with firmware')
    part = parts[selected-1]
    return dict(active=selected, valid=valid, state=part[5], bootTry=part[6], copyPhase=part[7],
        sequence=int.from_bytes(part[8:10], 'little'), resumeBlock=int.from_bytes(part[10:12], 'little'),
        candidateVersion=int.from_bytes(part[24:28], 'little'), currentVersion=int.from_bytes(part[28:32], 'little'),
        backupVersion=int.from_bytes(part[40:44], 'little'))


def extract(data, console, points, phase):
    h.require(phase in PHASES, 'unknown capture phase')
    role = 'base' if phase in PHASES[:2] else 'target'
    model, images = points['roles'][role], points['images']
    h.require(len(data['stack_original']) == 8192 and
              data['header_original'] == bytes.fromhex(images[role]['header']), 'wrong sample image/stack')
    for key in ('dhcsr', 'dhcsr_after'):
        h.require(len(data[key]) == 4 and int.from_bytes(data[key], 'little') & 0x20000,
                  'sample not bracketed by halted CPU')
    h.require(register(console, 'PC') == model['epilogue'], 'not at bound BCB epilogue')
    sp, active = register(console, 'SP'), register(console, 'R0')
    h.require(sp % 4 == 0 and model['lower'] <= sp and sp + 272 <= model['upper'], 'wrong stack frame')
    offset = sp - model['lower']
    saved, = struct.unpack_from('<I', data['stack_original'], offset + 268)
    h.require(saved == model['points'][phase]['savedLR'], 'unrelated BCB caller')
    pair = data['stack_original'][offset:offset+128]
    value = bcb_pair(pair, active)
    state, tries = dict(beforeBackup=(4, 0), staged=(1, 3), testBoot=(3, 2), confirmed=(4, 0))[phase]
    version = images['target' if phase == 'confirmed' else 'base']['version']
    h.require(value['state'] == state and value['bootTry'] == tries and
              value['copyPhase'] == value['resumeBlock'] == 0 and value['currentVersion'] == version,
              'unexpected real BCB state/version')
    if phase != 'beforeBackup':
        part = pair[(active-1)*64:active*64]
        h.require(value['candidateVersion'] == images['target']['version'] and
                  value['backupVersion'] == images['base']['version'], 'wrong candidate/backup versions')
        h.require(struct.unpack_from('<3I', part, 12) == (0x1000, images['target']['size'], images['target']['crc']) and
                  struct.unpack_from('<2I', part, 32) == (images['base']['size'], images['base']['crc']),
                  'candidate/backup address, length or CRC mismatch')
    return pair, value


def completed_console(raw, start, marker):
    tail = raw[start:]
    position = tail.find(str(marker).encode('ascii'))
    if position < 0:
        return False
    end = tail.find(b'Reading 4 bytes from addr 0xE000EDF0 into file...O.K.', position)
    return tail[:end+len(b'Reading 4 bytes from addr 0xE000EDF0 into file...O.K.')] if end >= 0 else False


class Commander:
    """One standard Commander process; each batch is retained before submission."""
    def __init__(self, mcu, deadline):
        self.mcu, self.deadline = mcu, deadline
        self.out = h.fresh(mcu.out / 'native-session')
        h.require(mcu.logger is None, 'another RTT reader is active')
        mcu.foreign_debuggers(self.out, deadline=deadline)
        for leaf in ('settings.jlink', 'sdk.log', 'result.json'):
            h.checked(self.out / leaf)
        self.process = h.Process(self.out, 'commander', [mcu.tool('commander'),
            '-Device', 'AT32F435RGT7', '-If', 'SWD', '-Speed', '1000', '-USB', str(mcu.plan['probe_serial']),
            '-AutoConnect', '0', '-ExitOnError', '1', '-NoGui', '1',
            '-SettingsFile', self.out / 'settings.jlink', '-Log', self.out / 'sdk.log'],
            mcu.env, interactive=True)
        try:
            self.execute(m.START, {}, 'session-connect', seconds=30)
        except BaseException:
            self.close()
            raise

    def execute(self, commands, reads, label, *, seconds=60, cleanup=False):
        deadline = time.monotonic() + seconds
        if not cleanup:
            deadline = min(deadline, self.deadline)
        h.require(deadline > time.monotonic() and self.process.alive(), 'Commander session expired/closed')
        self.mcu.count += 1
        out = h.fresh(self.mcu.out / ('%04d-' % self.mcu.count + label))
        paths = {name: h.checked(out / (name + '.bin')) for name in reads}
        marker = h.checked(out / 'batch_complete.bin')
        lines = []
        for command in commands:
            if isinstance(command, tuple):
                name, address, size = command
                h.require(name in paths and reads[name] == size and 0 < size <= 0x180000,
                          'unbound original readback')
                lines.append('savebin "%s", 0x%08X, 0x%X' % (paths[name], address, size))
            else:
                h.require(command not in ('q', 'qc', 'exit'), 'session closure is owned')
                lines.append(command)
        lines.append('savebin "%s", 0x%08X, 0x4' % (marker, m.REGISTERS['dhcsr']))
        # Commander buffers redirected stdout. Console-only help flushes the
        # preceding batch; no extra target command or connection is needed.
        lines += ['?', '?', '?']
        packet = ('\n'.join(lines) + '\n').encode('ascii')
        h.raw(out / 'commands.jlink', packet)
        original = self.process.paths['stdout']
        start = original.stat().st_size
        self.process.send(packet)
        def complete():
            h.require(self.process.alive(), 'Commander exited before batch completion')
            if not marker.is_file() or marker.stat().st_size != 4:
                return False
            return completed_console(original.read_bytes(), start, marker)
        console = h.wait_for(complete, max(.001, deadline-time.monotonic()), interval=.05)
        h.raw(out / 'commander.stdout', console)
        h.save(out / 'console-source.json', dict(path=str(original.relative_to(h.ROOT)),
            offset=start, length=len(console), sha256=hashlib.sha256(console).hexdigest()))
        data = {}
        for name, size in reads.items():
            h.require(paths[name].is_file() and paths[name].stat().st_size == size, 'missing/short native readback')
            data[name] = paths[name].read_bytes()
        text = console.decode('utf8', 'replace')
        h.require(not re.search(r'(?im)^.*(?:ERROR:|Error:|Unknown command|Cannot connect|CPU is not halted)', text),
                  'native Commander diagnostic; preserve originals')
        return data, text, out

    def close(self):
        if self.process.closed:
            return
        try:
            if self.process.alive():
                self.process.send(b'qc\n')
                self.process.process.stdin.close()
            self.process.wait(10)
            h.save(self.out / 'result.json', dict(stdout=h.record(self.process.paths['stdout']),
                stderr=h.record(self.process.paths['stderr']), receipt=h.record(self.process.paths['closed.json']),
                singleConnection=True))
        finally:
            self.process.close('commander-session-closed')


class Collector:
    def __init__(self, mcu, points, deadline):
        self.mcu, self.points, self.deadline = mcu, points, deadline
        self.original = None
        self.touched = False
        self.samples = []
        self.armed = None
        self.idle_proved = False
        self.session = None
        self.handles = []

    def execute(self, commands, reads, label, seconds=60):
        if self.session is None:
            return self.mcu.execute(commands, reads, label, seconds=seconds, deadline=self.deadline)
        data, console, out = self.session.execute(commands, reads, label, seconds=seconds)
        new = [int(value) for value in re.findall(r'Breakpoint set @ addr 0x[0-9A-Fa-f]+ \(Handle = (\d+)\)', console)]
        self.handles += new
        h.require(len(new) == sum(isinstance(line, str) and line.startswith('SetBP ') for line in commands),
                  'missing native breakpoint handle')
        return data, console, out

    def clear(self):
        h.require(self.original is not None, 'no original debugger state')
        lines = ['ClearBP %d' % handle for handle in self.handles]
        self.handles = []
        return lines + ['w4 0x%08X, 0x%08X' % (FPB+8+i*4, value)
                        for i, value in enumerate(self.original['comparators'])]

    def prepare(self):
        h.require(self.original is None, 'duplicate preparation')
        before = self.mcu.inspect('base', 'pre-upgrade')
        h.require(before['storage']['journal']['expected_begin_durable'] == 0, 'not a zero-durable start')
        data, _, _ = self.execute([('fpb', FPB, 40)], dict(fpb=40), 'debug-precheck')
        words = struct.unpack('<10I', data['fpb'])
        h.require(all(not word & 1 for word in words[2:8]) and before['registers']['freeze'] == 0,
                  'existing breakpoint/freeze; do not take ownership')
        self.original = dict(comparators=list(words[2:8]), freeze=0)
        h.save(self.mcu.out / 'debug-original.json', self.original)
        return before

    def arm(self, phase, *, resume=False, reset=False):
        h.require(len(self.samples) < len(PHASES) and self.armed is None and
                  phase == PHASES[len(self.samples)] and not (resume and reset), 'out-of-order arm')
        h.require(not reset or (phase == 'testBoot' and self.idle_proved), 'reset requires verified STAGED and SD idle')
        role = 'base' if phase in PHASES[:2] else 'target'
        point = self.points['roles'][role]['points'][phase]
        lines = self.clear() + (['r'] if reset else [])
        lines += ['w4 0x%08X, 0x00001000' % FREEZE, 'SetBP 0x%08X, T, H' % point['call']]
        if resume or reset:
            lines += ['g']
        lines += [('fpb', FPB, 40), ('freeze', FREEZE, 4)]
        self.touched = True
        self.armed = phase
        data, _, folder = self.execute(lines, dict(fpb=40, freeze=4), 'arm-' + phase)
        values = struct.unpack('<10I', data['fpb'])[2:8]
        active = [value for value in values if value & 1]
        halfword = 1 if point['call'] % 4 == 0 else 2
        h.require(len(active) == 1 and (active[0] & 0x1ffffffc) == (point['call'] & 0x1ffffffc) and
                  (active[0] >> 30) & halfword and
                  int.from_bytes(data['freeze'], 'little') == 0x1000, 'breakpoint/freeze not armed')
        h.save(folder / 'armed.json', dict(phase=phase, call=point['call'], resume=resume, normalReset=reset))
        return folder

    def capture(self, phase, wait_seconds):
        h.require(len(self.samples) < len(PHASES) and phase == self.armed == PHASES[len(self.samples)] and
                  1 <= wait_seconds <= 600, 'invalid capture order/deadline')
        role = 'base' if phase in PHASES[:2] else 'target'
        model = self.points['roles'][role]
        # The call stop and EEPROM return stay in this same Commander connection.
        lines = ['WaitHalt %d' % (wait_seconds*1000), 'w4 0x%08X, 0x00001000' % FREEZE] + self.clear()
        lines += ['SetBP 0x%08X, T, H' % model['epilogue'], 'g', 'WaitHalt 5000', 'regs',
            ('dhcsr', m.REGISTERS['dhcsr'], 4), ('stack_original', model['lower'], 8192),
            ('header_original', 0x08010400, 96), ('freeze', FREEZE, 4),
            ('dhcsr_after', m.REGISTERS['dhcsr'], 4)]
        data, console, out = self.execute(lines, dict(dhcsr=4, stack_original=8192,
            header_original=96, freeze=4, dhcsr_after=4), 'capture-' + phase, wait_seconds+30)
        pair, value = extract(data, console, self.points, phase)
        h.require(int.from_bytes(data['freeze'], 'little') == 0x1000, 'debug halt freeze lost')
        if self.samples:
            delta = (value['sequence'] - self.samples[-1]['sequence']) & 0xffff
            h.require(0 < delta < 0x8000, 'BCB sequence did not advance')
            if phase in ('staged', 'confirmed'):
                h.require(delta == 1, 'unexpected extra BCB commit')
        h.raw(out / 'pair.bin', pair)
        h.save(out / 'sample.json', dict(phase=phase, observed=value, original=h.record(out / 'pair.bin'),
            stack=h.record(out / 'stack_original.bin'), console=h.record(out / 'commander.stdout'),
            source='same-connection native EEPROM readbacks in the real firmware caller'))
        self.samples.append(value)
        self.armed = None
        return value

    def sd_idle(self):
        h.require(len(self.samples) == 2 and self.samples[-1]['state'] == 1, 'no verified STAGED commit')
        bound = self.mcu.bind('base')
        idle = bound['table'][m.SYMBOLS['main_loop']][0]
        owner = bound['table'][m.SYMBOLS['owner']][0]
        lines = self.clear() + ['SetBP 0x%08X, T, H' % idle, 'g', 'WaitHalt 10000', 'regs',
            ('sdio', m.REGISTERS['sdio'], 4), ('dhcsr', m.REGISTERS['dhcsr'], 4), ('owner', owner, 1)]
        data, console, _ = self.execute(lines, dict(sdio=4, dhcsr=4, owner=1), 'sd-idle-before-reset', 30)
        h.require(register(console, 'PC') == idle and int.from_bytes(data['dhcsr'], 'little') & 0x20000 and
                  not int.from_bytes(data['sdio'], 'little') & 0x3800 and data['owner'] == b'\0',
                  'SD/overlay not idle; do not reset')
        self.idle_proved = True

    def close(self):
        if self.session is not None and hasattr(self.session, 'process') and not self.session.process.alive():
            ended, self.session = self.session, None
            try:
                ended.close()
            except BaseException as error:
                h.save(self.mcu.out / 'native-exit-failure.json', dict(type=type(error).__name__, message=str(error)))
            # Only after this owned process closes may the standard one-shot
            # route reconcile and restore our debugger registers.
            self.handles = []
        try:
            if not self.touched:
                return
            execute = self.session.execute if self.session is not None else self.mcu.execute
            options = dict(seconds=60, cleanup=True) if self.session is not None else dict(seconds=60)
            status, _, _ = execute([('dhcsr', m.REGISTERS['dhcsr'], 4)], dict(dhcsr=4), 'cleanup-state', **options)
            resume = ['g'] if int.from_bytes(status['dhcsr'], 'little') & 0x20000 else []
            lines = self.clear() + resume + ['w4 0x%08X, 0x%08X' % (FREEZE, self.original['freeze']),
                ('fpb', FPB, 40), ('freeze', FREEZE, 4), ('dhcsr', m.REGISTERS['dhcsr'], 4)]
            data, _, out = execute(lines, dict(fpb=40, freeze=4, dhcsr=4), 'debug-cleanup', **options)
            h.require(list(struct.unpack('<10I', data['fpb'])[2:8]) == self.original['comparators'] and
                      int.from_bytes(data['freeze'], 'little') == self.original['freeze'] and
                      not int.from_bytes(data['dhcsr'], 'little') & 0x20000, 'debugger cleanup incomplete')
            self.touched = False
            h.save(out / 'restored.json', dict(breakpointsRestored=True, freezeRestored=True, cpuNotHalted=True))
        finally:
            if self.session is not None:
                self.session.close()

    def run(self, channel, ready):
        h.require(channel in ('sd', 'ble'), 'unknown transport')
        try:
            before = self.prepare()
            self.session = Commander(self.mcu, self.deadline)
            armed = self.arm('beforeBackup')
            ready(before, armed)
            self.capture('beforeBackup', 600)
            self.arm('staged', resume=True)
            self.capture('staged', 300)
            if channel == 'sd':
                self.sd_idle()
            self.arm('testBoot', resume=channel == 'ble', reset=channel == 'sd')
            self.capture('testBoot', 300)
            self.arm('confirmed', resume=True)
            self.capture('confirmed', 60)
        finally:
            self.close()
        self.mcu.wait_boot('target')
        final = self.mcu.inspect('target', 'final-full-readback')
        result = dict(stateChain=[value['state'] for value in self.samples], samples=self.samples,
            final=final, channel=channel, normalResets=1 if channel == 'sd' else 0,
            initiatesTransfer=False, timingCredit=False, formalVerdict='NOT_ADJUDICATED')
        h.save(self.mcu.out / 'state-chain.json', result)
        return result
