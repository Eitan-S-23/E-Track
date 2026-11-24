"""Instruction-bound R2 FirmwareUpdate lookup over a caller-owned read32 port.

No native driver or mapped NOR capability. The caller must retain reset/error
latches, time bounds and raw read evidence, and recheck this view around reads.
"""
import hashlib

import p34_finalized_vtor_capture as capture
from . import r2_health

MANAGER, GUARD = 0x2004f520, 0x2004f51c
VPTR, NAME = 0x080a12a0, 0x0805a0e6
COST_ACTIVE = 0x20053b00
SRAM_START, SRAM_END = 0x20000000, 0x20058000
FIELD_OFFSETS = dict(root=4, manager=8, name=12, timer=0x1470,
                     async_flags=0x34e4, work_flags=0x34e8, mode=0x34ec)
ANCHORS = {
    0x080484d4: '00f5405585b095f8ec34022b044621d195f8e83400f13806',
    0x0804852e: '95f8e994b9f1000f0dd085f8e934304600f007ff',
    0x080486bc: '06f58055', 0x080486c4: 'd5f87004', 0x080486d0: 'c5f87034',
    0x0803d3b2: 'd0e90157', 0x0803d54c: 'd4e90212019b9142c3e9024505d041f8043b',
    0x0803d568: '201d', 0x08046fb0: '2e4b70b5054640f8383b01f00eff',
    0x08047024: 'c3f870442146c6f8e444c6f8e84486f8ec44', 0x0804706c: 'a0120a08',
}


def verify(image, map_bytes):
    if type(image) is not bytes or hashlib.sha256(image).hexdigest() not in capture.PLANNED:
        raise ValueError('exact R2 image required for UI binding')
    r2_health.verify_map(map_bytes)
    for address, hex_bytes in ANCHORS.items():
        expected = bytes.fromhex(hex_bytes)
        offset = address - capture.policy.ORIGIN
        if image[offset:offset + len(expected)] != expected:
            raise ValueError('UI linked instruction differs')
    name = b'Pages/FirmwareUpdate\0'
    if image.count(name) != 1 or image[NAME - capture.policy.ORIGIN:NAME - capture.policy.ORIGIN + len(name)] != name:
        raise ValueError('unique FirmwareUpdate name literal differs')
    return dict(manager=MANAGER, guard=GUARD, vptr=VPTR, name=NAME, fields=dict(FIELD_OFFSETS),
                read_extent=0x34f0, object_size_independently_derived=False,
                mode_working=2, mode_browser=0, source='exact linked R2 Thumb instructions')


def sram(address, size=4):
    return (type(address) is int and address % 4 == 0 and type(size) is int and size > 0 and
            SRAM_START <= address < address + size <= SRAM_END)


class View:
    def __init__(self, image, map_bytes, read32, owner):
        self.binding = verify(image, map_bytes)
        self.read32, self.owner = read32, owner
        self.error = None
        self.located = self.attempted = False
        self.reads = 0
        self.pool = self.pages = self.object = self.slot = None

    def read(self, address):
        if self.error is not None or self.owner() is not True or not sram(address):
            raise ValueError('UI reader owner/error/address invalid')
        value = self.read32(address)
        self.reads += 1
        if type(value) is not int or not 0 <= value <= 0xffffffff or self.owner() is not True:
            raise ValueError('UI reader value/ownership changed')
        return value

    def pool_words(self):
        if self.read(GUARD) & 255 != 1:
            raise ValueError('PageManager initialization guard missing')
        begin, end, capacity = (self.read(MANAGER + offset) for offset in (4, 8, 12))
        if (not sram(begin) or not begin < end <= capacity <= SRAM_END or
            (end - begin) % 4 or (capacity - begin) % 4 or
            not 1 <= (end - begin) // 4 <= (capacity - begin) // 4 <= 32):
            raise ValueError('bounded PageManager pool invalid')
        return begin, end, capacity

    def locate(self):
        if self.attempted: raise ValueError('UI lookup cannot replay')
        self.attempted = True
        try:
            self.pool = self.pool_words()
            begin, end, _ = self.pool
            pages = tuple(self.read(address) for address in range(begin, end, 4))
            if len(set(pages)) != len(pages) or any(not sram(p) for p in pages):
                raise ValueError('invalid/duplicate PageBase pointers')
            candidates = [index for index, pointer in enumerate(pages) if self.read(pointer) == VPTR]
            if len(candidates) != 1:
                raise ValueError('unique FirmwareUpdate vptr missing')
            index = candidates[0]
            obj = pages[index]
            if not sram(obj, self.binding['read_extent']):
                raise ValueError('FirmwareUpdate fields exceed SRAM')
            if self.pool_words() != self.pool or tuple(self.read(a) for a in range(begin, end, 4)) != pages:
                raise ValueError('page pool changed during lookup')
            self.pages, self.object, self.slot = pages, obj, begin + 4 * index
            self.located = True
            return self.sample()
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__ + ': ' + str(error)
            raise

    def sample(self):
        try:
            if not self.located or self.error is not None:
                raise ValueError('UI lookup not owned/complete')
            before = self.pool_words()
            if before != self.pool or self.read(self.slot) != self.object or self.read(self.object) != VPTR:
                raise ValueError('UI pool/object identity changed')
            fields = {key: self.read(self.object + offset) for key, offset in FIELD_OFFSETS.items()}
            cost = self.read(COST_ACTIVE) & 255
            if fields['manager'] != MANAGER or fields['name'] != NAME:
                raise ValueError('FirmwareUpdate identity/backpointer differs')
            if (self.read(self.object) != VPTR or self.read(self.slot) != self.object or
                self.pool_words() != before):
                raise ValueError('UI pool/object changed after fields')
            # Pending flags clear before synchronous Apply/Stage. Require the
            # unloaded browser with no timer, rather than interpreting flags alone.
            inactive = (fields['root'] == fields['timer'] == 0 and fields['mode'] & 255 == 0 and
                        fields['async_flags'] & 0xffffff == 0 and fields['work_flags'] & 0xffff == 0 and cost == 0)
            return dict(object=self.object, slot=self.slot, pool=list(self.pool), fields=fields,
                cost_active=cost, unloaded_idle_ui_observed=inactive,
                permanent_exclusion=False, nor_access_admitted=False)
        except BaseException as error:
            if self.error is None: self.error = type(error).__name__ + ': ' + str(error)
            raise
