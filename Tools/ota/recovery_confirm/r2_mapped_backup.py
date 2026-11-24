"""Finite guarded mapped-logical backup comparison, never a chip-write port."""
import hashlib
import math
import struct
import time
import zlib

from . import r2_passive_state as passive, r2_ui_binding as ui
from .native_io import Words, guarded

BASE, PAYLOAD = 0x90100000, 0x90101000
BLOCK = 32768
EXPECTED_HEADER = bytes.fromhex('4554534c02ffffff746c09001fb924dd427600006045202787bd0d42544d4f43')
PAYLOAD_BYTES = 617588
PAYLOAD_SHA = '22a0c48da12e24e61368c1617bb9b6098a8416ab598f59dc005a2b594ea70002'
LOG_COUNT = 2 + math.ceil(PAYLOAD_BYTES/BLOCK)
DMA = {f'dma{unit}_{ch+1}': base+8+20*ch
       for unit, base in ((1, 0x40026400), (2, 0x40026600)) for ch in range(7)}
DMA.update({f'edma_{ch+1}': 0x40026010+24*ch for ch in range(8)})
ENDPOINTS = dict(display_peripheral=0x40026438, display_memory=0x4002643c,
                 sd_peripheral=0x4002664c, sd_memory=0x40026650)
NOR_READS = set(range(BASE, BASE+32, 4)) | set(range(PAYLOAD, PAYLOAD+PAYLOAD_BYTES, 4))
READS = passive.READS | set(range(ui.SRAM_START, ui.SRAM_END, 4)) | set(DMA.values()) | set(ENDPOINTS.values()) | NOR_READS


def expected(archive):
    if type(archive) is not bytes or len(archive) != 2097152 or hashlib.sha256(archive).hexdigest() != \
            'c5a72cbf45608b25edcc5939ff8ac8fbbed25b970bb6e1d2830d2a50f36e1a48':
        raise ValueError('fixed closed recovery NOR archive required')
    header = archive[0x100000:0x100020]
    payload = archive[0x101000:0x101000+PAYLOAD_BYTES]
    if (header != EXPECTED_HEADER or hashlib.sha256(payload).hexdigest() != PAYLOAD_SHA or
        struct.unpack_from('<I', header, 12)[0] != zlib.crc32(payload) or header[20:28] != payload[0x428:0x430]):
        raise ValueError('old30274 backup archive differs')
    return header, payload


def qualify(row, view, dma, endpoints):
    decoded = passive.decode(row)
    if not all(decoded[k] for k in ('idle_observed', 'retained_921600', 'actual_uart_matches_requested',
                                    'ota_flash_gate', 'nominal_clock_profile_matched')):
        raise ValueError('mapped backup software/clock owner not idle')
    # In particular CSTS must be zero in the raw XIP word. Do not use the
    # passive decoder's deliberately masked diagnostic comparison as admission.
    if row['qspi'] != passive.CONFIG or not view['unloaded_idle_ui_observed']:
        raise ValueError('mapped backup raw QSPI/UI profile not idle')
    if set(dma) != set(DMA) or set(endpoints) != set(ENDPOINTS):
        raise ValueError('complete DMA endpoint profile required')
    enabled = {k for k, v in dma.items() if v & 1}
    if not enabled <= {'dma1_3', 'dma2_4'}:
        raise ValueError('unqualified DMA/EDMA master enabled')
    for name, stem, peripheral, controls in (
        ('dma1_3', 'display', 0x4001300c, (0x1093,)),
        ('dma2_4', 'sd', 0x50061080, (0x2a81, 0x2a91))):
        if name in enabled and (dma[name] not in controls or endpoints[stem+'_peripheral'] != peripheral or
                               not ui.sram(endpoints[stem+'_memory'])):
            raise ValueError('active DMA may access non-SRAM/non-display/SD endpoint')
    return decoded['ble_epoch']


class Capture(passive.Probe):
    def __init__(self, dap, logs, image, map_bytes, owner, remaining, archive, emit_archive,
                 *, clock=time.monotonic, sleep=time.sleep, guard=guarded):
        self.header, self.payload = expected(archive)
        ui.verify(image, map_bytes)
        self.dap, self.logs, self.image, self.owner, self.remaining = dap, logs, image, owner, remaining
        self.sleep, self.guard, self.emit_archive = sleep, guard, emit_archive
        self.index = logs.gate.index
        self.used = self.active = self.reset_seen = False
        self.error = self.previous_left = self.epoch = None
        self.block_end = None
        self.words = Words(dap, logs.emit, reads=READS, write_allowed=lambda a, v: False,
                           seconds=780, clock=clock, guard=self.native)
        self.view = ui.View(image, map_bytes, self.words.read32, self.ui_owner)
        self.ui_identity = None
        self.check()
        if self.index != 1 or len(logs.gate.paths) != LOG_COUNT:
            raise ValueError('fixed setup/backup/final-Close log layout required')
        self.guard(logs.verify_head, seconds=min(30, self.remaining()-60))

    def check(self):
        super().check()
        if self.block_end is not None and self.words.budget.now() >= self.block_end:
            raise ValueError('mapped backup logical block deadline exhausted')

    def native(self, fn, *args, seconds):
        try:
            self.check()
            if not self.active: raise ValueError('mapped backup inactive')
            left = min(seconds, self.words.budget.left(), self.remaining()-60)
            if self.block_end is not None:
                left = min(left, self.block_end-self.words.budget.now())
            if left <= 0: raise ValueError('mapped operation has no reserved time')
            result = self.guard(fn, *args, seconds=left)
            self.check()
            return result
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise

    def save(self, name, raw):
        self.native(self.emit_archive, name, raw, seconds=30)

    def ui_owner(self):
        self.check()
        return self.active

    def cheap(self):
        self.running()
        values = {key: self.words.read32(passive.FIELDS[key]) for key in ('session', 'isr_active', 'overlay', 'epoch')}
        if any(values[k] & 255 for k in ('session', 'isr_active', 'overlay')) or values['epoch'] != self.epoch:
            raise ValueError('mapped burst software epoch/owner changed')
        for key in ('qspi_ctrl', 'qspi_ctrl2', 'qspi_cmdsts', 'qspi_xip3'):
            if self.words.read32(passive.QSPI[key]) != passive.CONFIG[key]:
                raise ValueError('mapped burst raw QSPI profile changed')

    def snapshot(self):
        row = super().sample()
        view = self.view.locate() if not self.view.attempted else self.view.sample()
        dma = {k: self.words.read32(a) for k, a in DMA.items()}
        endpoints = {k: self.words.read32(a) for k, a in ENDPOINTS.items()}
        epoch = qualify(row, view, dma, endpoints)
        identity = (view['object'], view['slot'], tuple(view['pool']))
        if self.epoch is None: self.epoch, self.ui_identity = epoch, identity
        if self.epoch != epoch or self.ui_identity != identity:
            raise ValueError('mapped capture epoch/UI identity changed')
        self.cheap()
        self.logs.emit('r2-mapped-backup-guard', epoch=epoch, ui=view, dma=dma, endpoints=endpoints,
                       started=row['started'], ended=self.words.budget.now())

    def chunk(self, address, size):
        self.cheap()
        raw = self.words.read_bytes(address, size)
        self.cheap()
        return raw

    def run(self):
        if self.used: raise ValueError('mapped backup capture cannot replay')
        self.used = self.active = True
        data = bytearray()
        try:
            self.identity()
            self.snapshot()
            header = self.chunk(BASE, 32)
            if header != self.header: raise ValueError('mapped backup header differs; payload not admitted')
            for start in range(0, PAYLOAD_BYTES, BLOCK):
                self.block_end = self.words.budget.now()+30
                self.snapshot()
                end = min(PAYLOAD_BYTES, start+BLOCK)
                for offset in range(start, end, 1024):
                    raw = self.chunk(PAYLOAD+offset, min(1024, end-offset))
                    if raw != self.payload[offset:offset+len(raw)]:
                        raise ValueError('mapped backup payload differs')
                    data.extend(raw)
                self.snapshot()
                self.check()
                self.block_end = None
                if end == PAYLOAD_BYTES:
                    self.identity()
                    if hashlib.sha256(data).hexdigest() != PAYLOAD_SHA:
                        raise ValueError('mapped complete backup hash differs')
                    self.save('backup-header', header)
                    self.save('backup-payload', bytes(data))
                self.active = False
                self.guard(lambda: self.logs.switch(read_allowed=lambda a: a in READS, expected_stores=[]),
                           seconds=min(45, self.remaining()-60))
                self.index += 1
                self.check()
                self.active = True
                self.logs.emit('r2-mapped-backup-progress', bytes=end, total=PAYLOAD_BYTES)
            return dict(result='R2_OLD_BACKUP_MAPPED_LOGICAL_MATCH', version=30274, payload_bytes=len(data),
                payload_sha256=PAYLOAD_SHA, header_hex=header.hex(), native_close_audited=False,
                mapped_logical_only=True, uncached_chip_read=False, permanent_writer_exclusion=False,
                ota_ready=False, full_current_image_read=False, physical_bcb_observed=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__+': '+str(error)
            raise
        finally:
            self.active = False
