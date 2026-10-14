#include "HAL.h"
#include "OTA/ota_layout.h"
#include "p34_early_fault_policy.h"

#if !defined(OTA_TARGET_APP) || !defined(P34_EARLY_FAULT_VECTORS)
#error This file belongs only to the opt-in GCC App target
#endif

extern "C" const uint32_t p34_runtime_vectors[];
extern "C" int p34_runtime_diagnostics_ready(void);
extern "C" __attribute__((noreturn)) void p34_early_exception(void);

extern "C" __attribute__((noinline)) void p34_enable_runtime_vectors(void)
{
    if (!p34_promotion_allowed(__get_IPSR(), SCB->VTOR, OTA_APP_ORIGIN,
                               p34_runtime_diagnostics_ready()))
        p34_early_exception();

    const uint32_t mask = __get_PRIMASK();
    __disable_irq();
    __DSB();
    SCB->VTOR = (uint32_t)p34_runtime_vectors;
    __DSB();
    __ISB();
    __set_PRIMASK(mask);
}
