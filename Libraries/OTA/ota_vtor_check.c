#include "ota_vtor_check.h"

#include "ota_layout.h"
#include "SEGGER_RTT.h"
#include "at32f435_437.h"

#if !defined(OTA_TARGET_APP)
#error "ota_vtor_check.c is only valid for an OTA App target"
#endif

#if defined(__CC_ARM)
#define OTA_VTOR_NOINIT \
    __attribute__((used, section(".ota_vtor_noinit"), zero_init))
#elif defined(__GNUC__)
#define OTA_VTOR_NOINIT \
    __attribute__((used, section(".ota_vtor_noinit")))
#else
#error "Unsupported compiler for OTA VTOR evidence placement"
#endif

OTA_VTOR_NOINIT volatile uint32_t g_ota_vtor_actual;
OTA_VTOR_NOINIT volatile uint32_t g_ota_vtor_expected;

void ota_vtor_check(void)
{
    const uint32_t actual = SCB->VTOR;

    if(actual == OTA_APP_ORIGIN)
    {
        return;
    }

    __disable_irq();
    g_ota_vtor_actual = actual;
    g_ota_vtor_expected = OTA_APP_ORIGIN;
    __DSB();

    SEGGER_RTT_Init();
    SEGGER_RTT_printf(
        0,
        "OTA: VTOR mismatch actual=0x%08X expected=0x%08X\r\n",
        (unsigned)actual,
        (unsigned)OTA_APP_ORIGIN
    );

    for(;;)
    {
        __DSB();
        __WFI();
    }
}

#undef OTA_VTOR_NOINIT
