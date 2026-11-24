"""Installation-only qualification for the original App's two display buffers.

Historical single-buffer probes are intentionally unchanged. This module adds
no target write capability; the caller must bind the original image/build first.
"""
from copy import deepcopy

from recovery_entry import host_nor, rendezvous

DISPLAY_BUFFERS = (0x200045e0, 0x200171e0)


def qualify_masters(sample):
    address = sample['raw']['display_dma_memory']
    if type(address) is not int or address not in DISPLAY_BUFFERS:
        raise ValueError('display DMA is not an exact original-App buffer base')
    # The legacy predicate validates every other master/control/count invariant.
    # Normalize only this independently qualified field in a private copy.
    normalized = deepcopy(sample)
    normalized['raw']['display_dma_memory'] = DISPLAY_BUFFERS[0]
    host_nor.qualify_masters(normalized)


def retained(control, previous):
    before = control.initial()
    if (not before['halted'] or before['lockup'] or before['reset_sticky'] or
            before['dhcsr_control'] != 3 or before['vtor'] != 0x08010000 or
            before['wfi_bytes'] != rendezvous.WFI_BYTES.hex() or
            before['fp_ctrl'] != 0x261 or before['comparators'] != [0]*6 or
            before['debug_apb1_frz'] != 0x1000 or before['wwdt_ctrl'] != 0):
        raise ValueError('exact retained entry controls required')
    result = control.observe_retained(previous)
    if not rendezvous.stopped_context_ok(result['context']):
        raise ValueError('retained original WFI context required')
    result['media'] = rendezvous.stopped_media_observation(result['state_samples'])
    result['before'] = before
    return result
