#ifndef P34_ACK_GAP_H
#define P34_ACK_GAP_H

#include <stdint.h>

/* Diagnostic only: preserve RX interrupts and start the gap after the final
 * stop bit, not after loading the transmit data register. Clock must advance. */
template <typename Clock, typename Idle>
static bool p34_ack_gap(Clock clock, Idle idle, uint32_t gap_cycles,
                        uint32_t drain_timeout_cycles)
{
    uint32_t start = clock();
    while (!idle())
    {
        if ((uint32_t)(clock() - start) >= drain_timeout_cycles)
        {
            return false;
        }
    }
    start = clock();
    while ((uint32_t)(clock() - start) < gap_cycles)
    {
    }
    return true;
}

#endif
