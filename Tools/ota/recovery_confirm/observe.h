#ifndef RR_CONFIRM_HOST_ONLY
#error "Host-only observer; not a device port"
#endif
#ifndef RC_OBSERVE_H
#define RC_OBSERVE_H
#include "EEPROM/eeprom_bcb.h"
typedef struct {
    uint8_t pair[2][BCB_SIZE];
    bcb_t value;
    bcb_arbiter_result_t active;
    unsigned completed;
    int stable;
} rc_observation;
/* Pure readback: no plan execution, no confirmation, no write callback use.
 * Success means matching reads, not a safe state or a completed operation. */
int rc_readback(const bcb_hal_t *read_hal,rc_observation *out);
#endif
