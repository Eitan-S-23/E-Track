#include "boot_handoff.h"

#include "boot_fw_header.h"
#include "boot_platform.h"
#include "OTA/ota_layout.h"

#include "at32f435_437.h"

#include <stdint.h>

#if !defined(OTA_TARGET_BOOT) || defined(OTA_TARGET_APP)
#error "Boot handoff must only be compiled by the OTA Boot target"
#endif

enum
{
    BOOT_NVIC_BANK_COUNT = 8
};

volatile int32_t g_boot_p1_handoff_validation;
volatile uint32_t g_boot_p1_handoff_msp;
volatile uint32_t g_boot_p1_handoff_reset;

static int handoff_flash_read(void *ctx, uint32_t offset,
                              uint8_t *dst, size_t len)
{
    (void)ctx;
    if (offset > OTA_APP_LENGTH || len > OTA_APP_LENGTH - offset)
    {
        return -1;
    }
    return boot_platform_flash_read(OTA_APP_ORIGIN + offset, dst, len);
}

static boot_fw_result_t validate_app(boot_fw_header_t *header)
{
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;

    reader.read = handoff_flash_read;
    reader.ctx = NULL;
    boot_fw_default_expectations(&expected);
    return boot_fw_header_validate(&reader, &expected, header);
}

__attribute__((naked, noreturn))
static void boot_branch_to_app(
    uint32_t initial_msp __attribute__((unused)),
    uint32_t reset_handler __attribute__((unused)))
{
    __asm volatile(
        "msr msp, r0\n"
        "dsb 0xF\n"
        "isb 0xF\n"
        "bx r1\n");
}

#if defined(BOOT_HANDOFF_TEST_INJECT_PENDING)
void boot_handoff_test_inject_pending(void)
{
    __set_PRIMASK(1u);
    SysTick->CTRL = 0u;
    NVIC->ICER[0] = 1u;
    SCB->ICSR = SCB_ICSR_PENDSTSET_Msk;
    NVIC->ISPR[0] = 1u;
    __DSB();
    __ISB();
}
#endif

void boot_handoff_to_app(void)
{
    boot_fw_header_t header;
    uint32_t initial_msp;
    uint32_t reset_handler;
    uint32_t index;

    g_boot_p1_handoff_validation = validate_app(&header);
    if (g_boot_p1_handoff_validation != BOOT_FW_OK)
    {
        boot_platform_log("BOOT: final App validation failed\r\n");
        boot_platform_hold();
    }
    if (__get_IPSR() != 0u)
    {
        boot_platform_log("BOOT: handoff attempted outside Thread mode\r\n");
        boot_platform_hold();
    }

    for (index = 0u; index < BOOT_NVIC_BANK_COUNT; ++index)
    {
        NVIC->ICER[index] = UINT32_MAX;
    }
    for (index = 0u; index < BOOT_NVIC_BANK_COUNT; ++index)
    {
        NVIC->ICPR[index] = UINT32_MAX;
    }

    SysTick->CTRL = 0u;
    SysTick->LOAD = 0u;
    SysTick->VAL = 0u;
    SCB->ICSR = SCB_ICSR_PENDSTCLR_Msk | SCB_ICSR_PENDSVCLR_Msk;
    __DSB();

    __set_PRIMASK(0u);
    __set_BASEPRI(0u);
    __set_FAULTMASK(0u);
    __set_CONTROL(0u);
    __ISB();

    SCB->VTOR = OTA_APP_ORIGIN;
    __DSB();
    __ISB();

    initial_msp = *(const volatile uint32_t *)(uintptr_t)OTA_APP_ORIGIN;
    reset_handler = *(const volatile uint32_t *)(uintptr_t)(OTA_APP_ORIGIN + 4u);
    g_boot_p1_handoff_msp = initial_msp;
    g_boot_p1_handoff_reset = reset_handler;
    if (initial_msp != header.initial_msp ||
        reset_handler != header.reset_handler)
    {
        boot_platform_log("BOOT: App vectors changed after validation\r\n");
        boot_platform_hold();
    }

    boot_branch_to_app(initial_msp, reset_handler);
}
