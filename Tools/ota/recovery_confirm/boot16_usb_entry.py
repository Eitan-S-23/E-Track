"""Exact suspended-from-default USB exception; no physical detach claim."""
from types import SimpleNamespace
from . import boot16_display_entry as display

prior = display.prior


def usb_idle(connection, bot):
    if any(type(v) is not int or not 0 <= v <= 0xffffffff for v in (connection, bot)):
        raise ValueError('complete USB words required')
    if connection & 255 in (0, 1):
        return bot & 0xffff in (0, 7)
    return connection == 0x00000104 and bot == 0


def usb_snapshot(connection, bot):
    accepted = usb_idle(connection, bot)
    return dict(connection=connection & 255, old_connection=(connection >> 8) & 255,
        device_address=(connection >> 16) & 255, remote_wakeup=connection >> 24,
        bot=bot & 0xffff, raw_connection=connection, raw_bot=bot, admitted=accepted,
        reason=('suspended_from_default_exact' if connection == 0x104 and bot == 0 else
                'unconfigured_idle_existing' if accepted else 'unqualified'), physical_disconnect_proven=False)


class Control(display.Control):
    def media(self, halted):
        if halted: self.finish_display_once()
        self.status(halted)
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
        if not halted:
            display.display_profile(dma['dma1_3'], endpoints['display_memory'], raw['display_dma_count'])
        if ((halted and raw['display_dma_count']) or raw['sd_dma_count'] or raw['sdio2_dtcnt'] or
                self.words.read32(0x40002c00) != 0):
            raise ValueError('active storage/display transfer or WWDT prevents long halt')
        if raw['sdio2_dtctrl'] not in (0, 0x98, 0x99, 0x9a, 0x9b):
            raise ValueError('unqualified SDIO2 data mode')
        connection = self.words.read32(prior.USB_CONNECTION)
        bot = self.words.read32(prior.USB_BOT)
        usb = usb_snapshot(connection, bot)
        if not usb['admitted']:
            raise ValueError('USB connection/BOT transaction prevents long halt')
        blockers = prior.rendezvous.stopped_media_observation([sample, sample])['observed_blockers']
        if blockers: raise ValueError('R2 media not settled: '+','.join(blockers))
        if (self.words.read32(prior.health.FLAGS) & 0xffffff != 0x010104 or
                self.words.read32(prior.health.HEALTH+32) != 1):
            raise ValueError('R2 confirmation completion/health readiness absent')
        self.status(halted)
        result = dict(state=sample, passive=row, ui=view, dma=dma, endpoints=endpoints, epoch=epoch, usb=usb)
        self.emit('boot16-media', halted=halted, **result)
        return result
