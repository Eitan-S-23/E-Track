"""One read-only passive/UI state phase; still no mapped NOR or native entry."""
from . import r2_passive_state as passive
from . import r2_ui_binding as ui
from .native_io import Words

READS = passive.READS | set(range(ui.SRAM_START, ui.SRAM_END, 4))


class Probe(passive.Probe):
    def __init__(self, *args, **kwargs):
        self.ui_words = None
        self.ui_samples = []
        super().__init__(*args, **kwargs)
        self.ui_words = Words(self.dap, self.logs.emit, reads=range(ui.SRAM_START, ui.SRAM_END, 4),
            write_allowed=lambda a, v: False, seconds=60, clock=self.words.budget.clock, guard=self.native)
        self.view = ui.View(self.image, args[3] if len(args) > 3 else kwargs['map_bytes'],
                            self.ui_words.read32, self.ui_owner)

    def check(self):
        super().check()
        if self.ui_words is not None:
            self.ui_words.check()

    def ui_owner(self):
        self.check()
        return self.active

    def sample(self):
        row = super().sample()
        self.running()
        started = self.words.budget.now()
        value = self.view.locate() if not self.view.attempted else self.view.sample()
        self.running()
        self.check()
        self.logs.emit('r2-ui-state-sample', started=started, ended=self.words.budget.now(), **value)
        self.ui_samples.append(value)
        return row

    def run(self):
        if self.used: raise ValueError('combined passive/UI state cannot replay')
        self.used = self.active = True
        try:
            self.identity()
            before = self.sample()
            self.native(self.sleep, 1., seconds=2)
            after = self.sample()
            self.identity()
            a, b = passive.decode(before), passive.decode(after)
            self.active = False
            trace = self.guard(lambda: self.logs.switch(read_allowed=lambda a: a in READS, expected_stores=[]),
                               seconds=min(30, self.remaining()-60))
            self.index += 1
            self.check()
            if trace['target_writes'] or trace['native_close'] or len(self.ui_samples) != 2:
                raise ValueError('combined passive/UI phase did not seal read-only')
            return dict(result='R2_PASSIVE_UI_STATE_OBSERVED', before=a, after=b, ui=self.ui_samples,
                sampled_epoch_stable=a['ble_epoch'] == b['ble_epoch'],
                unloaded_ui_idle_observed=all(x['unloaded_idle_ui_observed'] for x in self.ui_samples),
                full_image_verified=False, native_close_audited=False, reset_seen=False,
                nor_bytes_read=0, permanent_writer_exclusion=False, ota_ready=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__ + ': ' + str(error)
            raise
        finally:
            self.active = False
