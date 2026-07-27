#ifndef E_TRACK_OTA_VTOR_CHECK_H
#define E_TRACK_OTA_VTOR_CHECK_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

extern volatile uint32_t g_ota_vtor_actual;
extern volatile uint32_t g_ota_vtor_expected;

void ota_vtor_check(void);

#ifdef __cplusplus
}
#endif

#endif
