"""Pure HOST_ONLY R2-A erase geometry and preservation model, not a writer."""
from dataclasses import dataclass
import hashlib

APP_START = 0x08010000
APP_LIMIT = 0x08100000
BANK2_START = 0x08080000
SECTOR_SIZE = 0x800
IMAGE_SIZE = 619580
IMAGE_SHA256 = '7445ef63d5f4cbef95761f27075333d7d09c9d43585a28b84e6575ccfb274fcf'


@dataclass(frozen=True)
class Envelope:
    start: int
    payload_end: int
    erase_end: int
    unit: int

    @property
    def collateral(self):
        return self.erase_end - self.payload_end

    @property
    def sectors(self):
        return tuple((address, 1 if address < BANK2_START else 2)
                     for address in range(self.start, self.erase_end, SECTOR_SIZE))


def geometry(image, *, unit=SECTOR_SIZE):
    if type(image) is not bytes or len(image) != IMAGE_SIZE or hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError('exact finalized R2-A required')
    if type(unit) is not int or unit not in (SECTOR_SIZE, 0x1000):
        raise ValueError('only physical 2KiB or existing 4KiB geometry')
    end = APP_START + len(image)
    erase_end = (end + unit - 1) // unit * unit
    if not APP_START < end <= erase_end <= APP_LIMIT:
        raise ValueError('App boundary')
    return Envelope(APP_START, end, erase_end, unit)


def model_manifest(image, preimage):
    """Require every collateral byte; never synthesize an FF suffix for callers."""
    extent = geometry(image)
    if type(preimage) is not bytes or len(preimage) != extent.erase_end - extent.start:
        raise ValueError('complete exact erase-envelope preimage required')
    desired = image + preimage[len(image):]
    sectors = tuple(dict(address=address, bank=bank,
                         before=preimage[address-APP_START:address-APP_START+SECTOR_SIZE],
                         after=desired[address-APP_START:address-APP_START+SECTOR_SIZE])
                    for address, bank in extent.sectors)
    return dict(host_only=True, device_entry=False, physical_preimage_verified=False,
                extent=extent, desired=desired, sectors=sectors)


def simulate(manifest, *, fail_after=None):
    """Finite in-memory erase/program model; failure never invents a reset exit."""
    sectors = manifest['sectors']
    if fail_after is not None and (type(fail_after) is not int or not 0 <= fail_after <= 2*len(sectors)):
        raise ValueError('invalid model cut')
    actual = bytearray(b''.join(item['before'] for item in sectors))
    completed = 0
    for item in sectors:
        offset = item['address'] - APP_START
        for data in (b'\xff' * SECTOR_SIZE, item['after']):
            if completed == fail_after:
                return dict(actual=bytes(actual), completed=completed, reset_allowed=False, complete=False)
            actual[offset:offset+SECTOR_SIZE] = data
            completed += 1
    return dict(actual=bytes(actual), completed=completed, reset_allowed=False, complete=True)
