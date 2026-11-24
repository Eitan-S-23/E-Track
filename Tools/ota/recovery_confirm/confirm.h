#ifndef RR_CONFIRM_HOST_ONLY
#error "Offline model only: no approved device entry or EEPROM write port"
#endif
#ifndef RR_CONFIRM_H
#define RR_CONFIRM_H
#include <stddef.h>
#include <stdint.h>
#include "EEPROM/eeprom_bcb.h"

/* Immutable supervisor-owned plan, not a caller-selected BCB write request.
 * This host-only interface is serialized/non-reentrant. It does not establish
 * physical presence, authorize hardware operations or expose a device entry.
 */
typedef struct {
    uint8_t operation[16];
    uint8_t before[2][BCB_SIZE];
} rc_plan;
typedef struct {
    const uint8_t *boot, *image;
    size_t boot_length, image_length;
    uint8_t operation[16];
} rc_request;
typedef enum {
    RC_UNKNOWN = -2, RC_REJECTED = -1, RC_NOT_CONFIRMED = 0,
    RC_CONFIRMED = 1, RC_ALREADY = 2
} rc_status;
typedef struct {
    uint8_t before[2][BCB_SIZE], after[2][BCB_SIZE];
    unsigned write_attempts;
    int transaction_status, before_read, after_read;
    bcb_arbiter_result_t active;
} rc_result;

rc_status rc_confirm(const rc_plan *plan, const rc_request *request,
                     const bcb_hal_t *host_hal, rc_result *result);
#endif
