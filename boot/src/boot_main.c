#include "boot_fw_header.h"
#include "boot_handoff.h"
#include "boot_platform.h"
#include "boot_recovery.h"
#include "boot_state_machine.h"

#include "EEPROM/eeprom_bcb.h"

#include <stdint.h>
#include <string.h>

#if !defined(OTA_TARGET_BOOT) || defined(OTA_TARGET_APP)
#error "Boot sources must only be compiled by the OTA Boot target"
#endif

volatile int32_t g_boot_p1_bcb_result;
volatile int32_t g_boot_p1_qspi_result;
volatile int32_t g_boot_p1_app_result;
volatile int32_t g_boot_p1_recovery_result;
volatile int32_t g_boot_p1_state_status;
volatile uint32_t g_boot_p1_state_action;
volatile uint32_t g_boot_p1_state_value;
volatile uint32_t g_boot_p1_state_resume;

static int eeprom_read(uint8_t address, uint8_t *dst, uint16_t len)
{
    return boot_platform_eeprom_read(address, dst, len);
}

static int eeprom_write(uint8_t address, const uint8_t *src, uint16_t len)
{
    return boot_platform_eeprom_write(address, src, len);
}

#if defined(BOOT_HANDOFF_TEST_CLEAR_BCB)
static int clear_test_bcb(void)
{
    uint8_t blank[BCB_SIZE];

    memset(blank, 0xFF, sizeof(blank));
    if (eeprom_write(BCB_A_ADDR, blank, sizeof(blank)) != 0)
    {
        return -1;
    }
    return eeprom_write(BCB_B_ADDR, blank, sizeof(blank));
}
#endif

static int state_external_read(void *ctx, uint32_t address,
                               uint8_t *dst, size_t len)
{
    (void)ctx;
    return boot_platform_qspi_read(address, dst, len);
}

static int state_internal_read(void *ctx, uint32_t address,
                               uint8_t *dst, size_t len)
{
    (void)ctx;
    return boot_platform_flash_read(address, dst, len);
}

static int state_internal_erase(void *ctx, uint32_t address)
{
    (void)ctx;
    return boot_platform_flash_erase_4k(address);
}

static int state_internal_program(void *ctx, uint32_t address,
                                  const uint8_t *src, size_t len)
{
    (void)ctx;
    return boot_platform_flash_program(address, src, len);
}

static void state_log(void *ctx, const char *text)
{
    (void)ctx;
    boot_platform_log(text);
}

static void publish_outcome(const boot_state_outcome_t *outcome)
{
    if (outcome == NULL)
    {
        return;
    }
    g_boot_p1_state_status = outcome->status;
    g_boot_p1_state_action = (uint32_t)outcome->action;
    g_boot_p1_state_value = outcome->bcb.state;
    g_boot_p1_state_resume = outcome->bcb.resume_block;
    g_boot_p1_app_result = outcome->action == BOOT_STATE_ACTION_JUMP_APP
                               ? BOOT_FW_OK
                               : BOOT_FW_ERR_ARGUMENT;
}

static int receive_physical_recovery(const boot_state_io_t *io,
                                     boot_state_outcome_t *outcome,
                                     int key_already_held)
{
    while (!key_already_held && !boot_platform_recovery_key_held())
    {
        boot_platform_log("BOOT: hold recovery key for 3 seconds\r\n");
        boot_platform_delay_ms(100u);
    }

    boot_platform_log("BOOT: physical recovery condition accepted\r\n");
    do
    {
        g_boot_p1_recovery_result = boot_recovery_receive();
    } while (g_boot_p1_recovery_result != 0);

    g_boot_p1_state_status =
        boot_state_machine_accept_physical_recovery(io, outcome);
    publish_outcome(outcome);
    return outcome->action == BOOT_STATE_ACTION_JUMP_APP ? 0 : -1;
}

int main(void)
{
    static const bcb_hal_t bcb_hal = {eeprom_write, eeprom_read};
    boot_state_io_t state_io;
    boot_state_outcome_t outcome;

    g_boot_p1_bcb_result = BCB_ARBITER_ERROR;
    g_boot_p1_qspi_result = -1;
    g_boot_p1_app_result = BOOT_FW_ERR_ARGUMENT;
    g_boot_p1_recovery_result = -1;
    g_boot_p1_state_status = BOOT_STATE_STATUS_ARGUMENT;
    g_boot_p1_state_action = BOOT_STATE_ACTION_HOLD;
    g_boot_p1_state_value = 0xFFFFFFFFu;
    g_boot_p1_state_resume = 0u;

    if (boot_platform_init() != 0)
    {
        boot_platform_hold();
    }

#if defined(BOOT_HANDOFF_TEST_CLEAR_BCB)
    if (clear_test_bcb() != 0)
    {
        boot_platform_log("BOOT: test BCB clear failed\r\n");
        boot_platform_hold();
    }
#endif

    memset(&state_io, 0, sizeof(state_io));
    state_io.bcb_hal = &bcb_hal;
    state_io.external_read = state_external_read;
    state_io.internal_read = state_internal_read;
    state_io.internal_erase_4k = state_internal_erase;
    state_io.internal_program = state_internal_program;
    state_io.log = state_log;

    if (boot_platform_recovery_key_held())
    {
        if (receive_physical_recovery(&state_io, &outcome, 1) != 0)
        {
            boot_platform_hold();
        }
    }
    else
    {
        g_boot_p1_qspi_result = boot_platform_qspi_init();
        state_io.external_available = g_boot_p1_qspi_result == 0;
        if (!state_io.external_available)
        {
            boot_platform_log("BOOT: QSPI unavailable, external slot branch skipped\r\n");
        }

        g_boot_p1_bcb_result = bcb_arbiter(&bcb_hal, NULL);
        g_boot_p1_state_status = boot_state_machine_run(&state_io, &outcome);
        publish_outcome(&outcome);
        if (outcome.action == BOOT_STATE_ACTION_PHYSICAL_RECOVERY)
        {
            if (receive_physical_recovery(&state_io, &outcome, 0) != 0)
            {
                boot_platform_hold();
            }
        }
    }

    if (outcome.action == BOOT_STATE_ACTION_JUMP_APP)
    {
        if (outcome.bcb.state == BCB_STATE_TEST_BOOT &&
            boot_platform_watchdog_start() != 0)
        {
            boot_platform_log("BOOT: TEST_BOOT watchdog start failed\r\n");
            boot_platform_hold();
        }
#if defined(BOOT_HANDOFF_TEST_INJECT_PENDING)
        boot_handoff_test_inject_pending();
#endif
        boot_handoff_to_app();
    }

    boot_platform_log("BOOT: no valid App handoff action\r\n");
    boot_platform_hold();
    return 0;
}
