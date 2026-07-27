#ifndef E_TRACK_OTA_VTOR_CHECK_H
#define E_TRACK_OTA_VTOR_CHECK_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

extern volatile uint32_t g_ota_vtor_actual;
extern volatile uint32_t g_ota_vtor_expected;
extern volatile uint32_t g_ota_handoff_vtor;
extern volatile uint32_t g_ota_handoff_primask;
extern volatile uint32_t g_ota_handoff_basepri;
extern volatile uint32_t g_ota_handoff_faultmask;
extern volatile uint32_t g_ota_handoff_control;
extern volatile uint32_t g_ota_handoff_systick_ctrl;
extern volatile uint32_t g_ota_handoff_icsr;
extern volatile uint32_t g_ota_handoff_iser_or;
extern volatile uint32_t g_ota_handoff_ispr_or;

void ota_handoff_capture(void);
void ota_handoff_report(void);
void ota_vtor_check(void);

#ifdef __cplusplus
}
#endif

#endif
