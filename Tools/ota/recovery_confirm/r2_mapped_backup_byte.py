"""Source-backed byte-display DMA qualification; all other mapped guards retained."""
from types import FunctionType
from . import r2_mapped_backup as prior


def qualify(row, view, dma, endpoints):
    decoded = prior.passive.decode(row)
    if not all(decoded[k] for k in ('idle_observed', 'retained_921600', 'actual_uart_matches_requested',
                                    'ota_flash_gate', 'nominal_clock_profile_matched')):
        raise ValueError('mapped backup software/clock owner not idle')
    if row['qspi'] != prior.passive.CONFIG or not view['unloaded_idle_ui_observed']:
        raise ValueError('mapped backup raw QSPI/UI profile not idle')
    if set(dma) != set(prior.DMA) or set(endpoints) != set(prior.ENDPOINTS):
        raise ValueError('complete DMA endpoint profile required')
    enabled = {k for k, v in dma.items() if v & 1}
    if not enabled <= {'dma1_3', 'dma2_4'}:
        raise ValueError('unqualified DMA/EDMA master enabled')
    for name, stem, peripheral, controls in (
        ('dma1_3', 'display', 0x4001300c, (0x1093,)),
        ('dma2_4', 'sd', 0x50061080, (0x2a81, 0x2a91))):
        memory = endpoints[stem+'_memory']
        # HAL_Display splits BYTE transfers at65535; continuation is often odd.
        valid_memory = (type(memory) is int and prior.ui.SRAM_START <= memory < prior.ui.SRAM_END
                        if stem == 'display' else prior.ui.sram(memory))
        if name in enabled and (dma[name] not in controls or endpoints[stem+'_peripheral'] != peripheral or not valid_memory):
            raise ValueError('active DMA may access non-SRAM/non-display/SD endpoint')
    return decoded['ble_epoch']


def bind(function, **values):
    result = FunctionType(function.__code__, dict(function.__globals__, **values), function.__name__,
                          function.__defaults__, function.__closure__)
    result.__kwdefaults__ = dict(function.__kwdefaults__ or {})
    return result


class Capture(prior.Capture):
    # Only the qualification lookup differs; all actual raw values stay intact
    # in the original snapshot and SDK journal. No frozen globals are changed.
    snapshot = bind(prior.Capture.snapshot, qualify=qualify)
