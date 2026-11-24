"""One retained-App resume store, followed only by running-safe observations."""
import struct
import time

from .probe import require

DHCSR = 0xe000edf0
REGISTERS = dict(dhcsr=DHCSR, vtor=0xe000ed08, icsr=0xe000ed04, scr=0xe000ed10,
                 shpr3=0xe000ed20, shcsr=0xe000ed24, cfsr=0xe000ed28, hfsr=0xe000ed2c,
                 dfsr=0xe000ed30, demcr=0xe000edfc, systick_ctrl=0xe000e010,
                 systick_load=0xe000e014, systick_value=0xe000e018,
                 millis=0x20004440, loop=0x20053aac, feed=0x20053ab0)
REGISTERS.update({f'iser{i}': 0xe000e100+4*i for i in range(4)})
REGISTERS.update({f'ispr{i}': 0xe000e200+4*i for i in range(4)})
CFSR_MASK, HFSR_MASK = 0x030fbfbb, 0xc0000002


def entry(sample, vectors):
    require(sample['dhcsr'] & 0x020a0000 == 0x20000 and sample['dhcsr'] & 0xffff == 3,
            'exact retained DHCSR halt required')
    require(sample['vtor'] == 0x08010000 and sample['icsr'] & 0x900001ff == 0,
            'active/NMI/PendSV exception prevents resume')
    require(sample['shcsr'] & 0xfd8b == 0 and sample['demcr'] & 0x60000 == 0,
            'active/pending fault/SVC/DebugMon hazard')
    require(sample['systick_ctrl'] & 7 == 7 and sample['systick_load'] == 287999 and
            sample['systick_value'] <= 287999 and sample['shpr3'] >> 24 == 0 and sample['scr'] & 6 == 0,
            'source-bound normal SysTick wake configuration required')
    require(len(vectors) == 524 and struct.unpack_from('<I', vectors, 60)[0] == 0x08017a9d,
            'source-bound SysTick vector required')
    for bank in range(4):
        pending = sample[f'iser{bank}'] & sample[f'ispr{bank}']
        for bit in range(32):
            if not pending & (1 << bit): continue
            offset = (16+bank*32+bit)*4
            require(offset+4 <= len(vectors), 'pending IRQ outside captured vector table')
            handler = struct.unpack_from('<I', vectors, offset)[0]
            require(handler & 1 and handler not in (0xffffffff, 0x0801b835), 'pending absent/default-loop IRQ')


class Port:
    def __init__(self, dap, emit, header):
        require(isinstance(header, bytes) and len(header) == 96, 'original App header required')
        self.dap, self.emit, self.header = dap, emit, header
        self.attempted, self.returned, self.reset_seen = False, False, False
        self.last_snapshot = None

    def read(self, address):
        require(address in REGISTERS.values() and self.dap.ready, 'resume read-only word scope')
        rc = self.dap._call('JLINKARM_CORESIGHT_WriteAPDPReg', 1, 1, address)
        require(type(rc) is int and rc >= 0, 'resume read TAR failed')
        value = self.dap._read_reg(3, 1); self.dap._power_ready()
        if address == DHCSR: self.reset_seen |= bool(value & 0x02000000)
        self.emit('resume-read', address=address, value=value)
        return value

    def snapshot(self, *, halted=False):
        names = REGISTERS if halted else ('dhcsr', 'vtor', 'cfsr', 'hfsr', 'millis', 'loop', 'feed')
        value = {name: self.read(REGISTERS[name]) for name in names}
        self.last_snapshot = value
        require(not self.reset_seen and not value['dhcsr'] & 0x80000, 'reset/lockup during resume observation')
        header = self.dap.read_flash(0x08010400, 96)
        require(header == self.header and value['vtor'] == 0x08010000, 'original running App identity changed')
        return value

    def resume_once(self):
        require(not self.attempted, 'resume must never be replayed')
        require(self.read(DHCSR) & 0x020affff == 0x20003 and not self.reset_seen, 'halt changed before resume')
        self.attempted = True
        self.emit('resume-write-attempt', address=DHCSR, value=0xa05f0001)
        rc = self.dap._call('JLINKARM_CORESIGHT_WriteAPDPReg', 1, 1, DHCSR)
        require(type(rc) is int and rc >= 0, 'resume TAR failed/uncertain')
        rc = self.dap._call('JLINKARM_CORESIGHT_WriteAPDPReg', 3, 1, 0xa05f0001)
        require(type(rc) is int and rc >= 0, 'resume store failed/uncertain')
        self.dap._power_ready()
        self.returned = True
        self.emit('resume-write-returned', address=DHCSR, value=0xa05f0001)


def observe(port, baseline, *, seconds=20, clock=time.monotonic, sleep=time.sleep):
    require(seconds == 20, 'fixed sustained observation interval required')
    start, checkpoint = clock(), clock()
    previous, samples, first_running = baseline, [], None
    def sample():
        value = port.snapshot()
        require(value['dhcsr'] & 0xffff == 1 and not value['dhcsr'] & 0x20000,
                'App is still halted or debug control changed')
        require((value['cfsr'] ^ baseline['cfsr']) & CFSR_MASK == 0 and
                (value['hfsr'] ^ baseline['hfsr']) & HFSR_MASK == 0, 'new sticky fault observation')
        samples.append(value)
        return value
    def advancing(value, previous):
        for key, maximum in (('millis', 30000), ('loop', 10000000), ('feed', 10000000)):
            delta = (value[key]-previous[key]) & 0xffffffff
            require(0 < delta <= maximum, 'stagnant/reset-like running '+key)
    while clock()-start < seconds:
        require(0 <= clock()-start < 25, 'resume observation timebase/deadline')
        value = sample()
        if first_running is None: first_running = value
        if clock()-checkpoint >= 5:
            advancing(value, previous)
            previous, checkpoint = value, clock()
        sleep(1)
    # Do not let progress before the final checkpoint hide a later stall/reset.
    final = sample()
    advancing(final, previous)
    require(20 <= clock()-start < 25 and len(samples) >= 15, 'sustained running interval not observed')
    for key in ('millis', 'loop', 'feed'):
        require(0 < ((samples[-1][key]-first_running[key]) & 0xffffffff) <= 10000000,
                'no sustained counter progress')
    return dict(samples=samples, elapsed_seconds=clock()-start, original_app_version=30275)


def execute(port, vectors, *, clock=time.monotonic, sleep=time.sleep):
    before = [port.snapshot(halted=True), port.snapshot(halted=True)]
    for value in before: entry(value, vectors)
    for key in ('cfsr', 'hfsr', 'scr', 'shpr3', 'demcr', 'systick_load'):
        require(before[0][key] == before[1][key], 'halted baseline changed: '+key)
    write_error = None
    try:
        port.resume_once()
    except BaseException as error:
        if not port.attempted: raise
        write_error = type(error).__name__+': '+str(error)
    # Even a negative write return may mean the core is running. Observe only;
    # neither this path nor cleanup is allowed another DHCSR control store.
    after = observe(port, before[-1], clock=clock, sleep=sleep)
    return dict(result='ORIGINAL_APP_RESUMED_STABLE' if write_error is None else
                'ORIGINAL_APP_RUNNING_AFTER_UNCERTAIN_RESUME', write_error=write_error,
                before=before, running=after, resume_attempts=int(port.attempted), resume_returned=port.returned,
                watchdog_pause_changed=False, reset_performed=False)
