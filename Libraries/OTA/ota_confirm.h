#ifndef E_TRACK_OTA_CONFIRM_H
#define E_TRACK_OTA_CONFIRM_H

#include "EEPROM/eeprom_bcb.h"

#ifdef __cplusplus
extern "C" {
#endif

enum
{
    OTA_CONFIRM_COMMITTED = 0,
    OTA_CONFIRM_ALREADY_CONFIRMED = 1,
    OTA_CONFIRM_ERR_ARGUMENT = -1,
    OTA_CONFIRM_ERR_ARBITER = -2,
    OTA_CONFIRM_ERR_STATE = -3,
    OTA_CONFIRM_ERR_COMMIT = -4,
    OTA_CONFIRM_ERR_VERIFY = -5
};

static inline int ota_confirm_test_boot(const bcb_hal_t *hal,
                                        bcb_t *out_confirmed)
{
    bcb_arbiter_result_t active;
    bcb_arbiter_result_t observed;
    bcb_t current;
    bcb_t next;

    if (hal == NULL)
    {
        return OTA_CONFIRM_ERR_ARGUMENT;
    }
    active = bcb_arbiter(hal, &current);
    if (active != BCB_ARBITER_A && active != BCB_ARBITER_B)
    {
        return OTA_CONFIRM_ERR_ARBITER;
    }
    if (current.state == BCB_STATE_CONFIRMED)
    {
        if (out_confirmed != NULL)
        {
            *out_confirmed = current;
        }
        return OTA_CONFIRM_ALREADY_CONFIRMED;
    }
    if (current.state != BCB_STATE_TEST_BOOT)
    {
        return OTA_CONFIRM_ERR_STATE;
    }

    next = current;
    next.state = BCB_STATE_CONFIRMED;
    next.boot_try = 0u;
    next.copy_phase = BCB_COPY_NONE;
    next.resume_block = 0u;
    next.cur_vcode = current.cand_vcode;
    if (bcb_commit(hal, active, &next) != BCB_COMMIT_OK)
    {
        return OTA_CONFIRM_ERR_COMMIT;
    }

    observed = bcb_arbiter(hal, &current);
    if ((observed != BCB_ARBITER_A && observed != BCB_ARBITER_B) ||
        current.state != BCB_STATE_CONFIRMED ||
        current.copy_phase != BCB_COPY_NONE ||
        current.resume_block != 0u ||
        current.cur_vcode != current.cand_vcode)
    {
        return OTA_CONFIRM_ERR_VERIFY;
    }
    if (out_confirmed != NULL)
    {
        *out_confirmed = current;
    }
    return OTA_CONFIRM_COMMITTED;
}

#ifdef __cplusplus
}
#endif

#endif
