"""R2 entry successor: permit running display, bound its held completion."""
from types import SimpleNamespace
from . import boot16_entry as prior


def display_profile(control, memory, count):
    if type(count) is not int or not 0 <= count <= 65535:
        raise ValueError('display count outside one source-bound DMA chunk')
    if control & 1 and (control != 0x1093 or type(memory) is not int or
            not prior.ui.SRAM_START <= memory < prior.ui.SRAM_END):
        raise ValueError('unqualified display mode/source')
    # The decrementing count omits the bytes already transferred. Cover the
    # maximum original chunk, not just its sampled remainder.
    if count and (control != 0x1093 or memory+65535 > prior.ui.SRAM_END):
        raise ValueError('whole possible display chunk is not within SRAM')


class Control(prior.Control):
    display_waited = False
    display_deadline = None

    def native(self, function, *args, seconds):
        if self.display_deadline is not None:
            left = self.display_deadline-self.clock()
            if left <= 0: raise ValueError('held display native allowance expired')
            seconds = min(seconds, left)
        result = super().native(function, *args, seconds=seconds)
        if self.display_deadline is not None and self.clock() >= self.display_deadline:
            raise ValueError('held display native deadline expired')
        return result

    def finish_display_once(self):
        if self.display_waited: return
        self.display_waited = True
        self.display_deadline = min(self.clock()+1., self.words.budget.end)
        try:
            self.observe_display_completion()
        finally:
            self.display_deadline = None

    def observe_display_completion(self):
        start = self.clock()
        deadline = self.display_deadline
        previous = original = None
        while True:
            self.held()
            values = tuple(self.words.read32(address) for address in (
                prior.DMA['dma1_3'], prior.ENDPOINTS['display_peripheral'],
                prior.ENDPOINTS['display_memory'], prior.state_probe.REGISTERS['display_dma_count']))
            control, peripheral, memory, count = values
            display_profile(control, memory, count)
            if control & 1 and peripheral != 0x4001300c:
                raise ValueError('display peripheral changed')
            if original is None: original = values[:3]
            if values[:3] != original or previous is not None and count > previous:
                raise ValueError('held display mode/endpoint/count changed')
            self.held()
            observed = self.clock()
            if observed >= deadline: raise ValueError('held display did not qualify within one second')
            self.emit('boot16-display-completion', count=count, elapsed=observed-start,
                      control=control, peripheral=peripheral, memory=memory)
            if count == 0: return
            previous = count
            self.native(self.sleep, .01, seconds=min(.1, deadline-observed))

    def media(self, halted):
        if halted:
            self.finish_display_once()
            return super().media(True)
        self.status(False)
        def read(op, address, size):
            if op != 'read' or size != 4: raise ValueError('state word only')
            return self.words.read32(address).to_bytes(4, 'little')
        sample = prior.state_probe.sample(SimpleNamespace(_call=read, emit=self.emit))
        row = {label: {key: self.words.read32(addr) for key, addr in fields.items()}
               for label, fields in (('fields', prior.passive.FIELDS), ('clocks', prior.passive.CLOCK_ADDR),
                                     ('qspi', prior.passive.QSPI))}
        view = self.view.sample() if self.view.attempted else self.view.locate()
        dma = {name: self.words.read32(addr) for name, addr in prior.DMA.items()}
        endpoints = {name: self.words.read32(addr) for name, addr in prior.ENDPOINTS.items()}
        epoch = prior.qualify_dma(row, view, dma, endpoints)
        raw = sample['raw']
        display_profile(dma['dma1_3'], endpoints['display_memory'], raw['display_dma_count'])
        if (raw['sd_dma_count'] or raw['sdio2_dtcnt'] or self.words.read32(0x40002c00) != 0):
            raise ValueError('active storage transfer or WWDT prevents long halt')
        if raw['sdio2_dtctrl'] not in (0, 0x98, 0x99, 0x9a, 0x9b):
            raise ValueError('unqualified SDIO2 data mode')
        usb = dict(connection=self.words.read32(prior.USB_CONNECTION) & 255,
                   bot=self.words.read32(prior.USB_BOT) & 0xffff)
        if usb['connection'] not in (0, 1) or usb['bot'] not in (0, 7):
            raise ValueError('USB connection/BOT transaction prevents long halt')
        blockers = prior.rendezvous.stopped_media_observation([sample, sample])['observed_blockers']
        if blockers: raise ValueError('R2 media not settled: '+','.join(blockers))
        if (self.words.read32(prior.health.FLAGS) & 0xffffff != 0x010104 or
                self.words.read32(prior.health.HEALTH+32) != 1):
            raise ValueError('R2 confirmation completion/health readiness absent')
        self.status(False)
        result = dict(state=sample, passive=row, ui=view, dma=dma, endpoints=endpoints, epoch=epoch, usb=usb)
        self.emit('boot16-media', halted=False, **result)
        return result
