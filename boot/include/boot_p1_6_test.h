#ifndef E_TRACK_BOOT_P1_6_TEST_H
#define E_TRACK_BOOT_P1_6_TEST_H

#include <stdint.h>

#include "OTA/ota_p1_6_test.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum
{
    BOOT_P1_6_NO_REQUEST = 0,
    BOOT_P1_6_HOLD = 1
} boot_p1_6_result_t;

boot_p1_6_result_t boot_p1_6_process_command(void);

#if defined(P1_6_TEST_ENABLE)
void boot_p1_6_capture_checkpoint_state(void);

static inline void boot_p1_6_checkpoint(uint32_t checkpoint,
                                        uint32_t arg0,
                                        uint32_t arg1)
{
    if (!ota_p1_6_checkpoint_matches(checkpoint, arg0, arg1))
    {
        return;
    }
    boot_p1_6_capture_checkpoint_state();
    ota_p1_6_checkpoint(checkpoint, arg0, arg1);
}
#else
#define boot_p1_6_checkpoint(checkpoint, arg0, arg1) ((void)0)
#endif

#ifdef __cplusplus
}
#endif

#endif
