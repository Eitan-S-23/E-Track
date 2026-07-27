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
volatile uint32_t g_ota_handoff_vtor;
volatile uint32_t g_ota_handoff_primask;
volatile uint32_t g_ota_handoff_basepri;
volatile uint32_t g_ota_handoff_faultmask;
volatile uint32_t g_ota_handoff_control;
volatile uint32_t g_ota_handoff_systick_ctrl;
volatile uint32_t g_ota_handoff_icsr;
volatile uint32_t g_ota_handoff_iser_or;
volatile uint32_t g_ota_handoff_ispr_or;

void ota_handoff_capture(void)
{
    uint32_t index;
    uint32_t enabled = 0u;
    uint32_t pending = 0u;

    g_ota_handoff_vtor = SCB->VTOR;
    g_ota_handoff_primask = __get_PRIMASK();
    g_ota_handoff_basepri = __get_BASEPRI();
    g_ota_handoff_faultmask = __get_FAULTMASK();
    g_ota_handoff_control = __get_CONTROL();
    g_ota_handoff_systick_ctrl = SysTick->CTRL;
    g_ota_handoff_icsr = SCB->ICSR;
    for(index = 0u; index < 8u; ++index)
    {
        enabled |= NVIC->ISER[index];
        pending |= NVIC->ISPR[index];
    }
    g_ota_handoff_iser_or = enabled;
    g_ota_handoff_ispr_or = pending;
}

void ota_handoff_report(void)
{
    SEGGER_RTT_printf(
        0,
        "OTA: HANDOFF vtor=0x%08X primask=%u basepri=%u faultmask=%u "
        "control=%u systick=0x%08X icsr=0x%08X iser=0x%08X ispr=0x%08X\r\n",
        (unsigned)g_ota_handoff_vtor,
        (unsigned)g_ota_handoff_primask,
        (unsigned)g_ota_handoff_basepri,
        (unsigned)g_ota_handoff_faultmask,
        (unsigned)g_ota_handoff_control,
        (unsigned)g_ota_handoff_systick_ctrl,
        (unsigned)g_ota_handoff_icsr,
        (unsigned)g_ota_handoff_iser_or,
        (unsigned)g_ota_handoff_ispr_or
    );
}

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
