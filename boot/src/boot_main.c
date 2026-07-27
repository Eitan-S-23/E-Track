#include "boot_fw_header.h"
#include "boot_platform.h"
#include "boot_recovery.h"
#include "boot_slot.h"

#include "EEPROM/eeprom_bcb.h"
#include "OTA/ota_layout.h"

#include <stdint.h>
#include <string.h>

#if !defined(OTA_TARGET_BOOT) || defined(OTA_TARGET_APP)
#error "Boot sources must only be compiled by the OTA Boot target"
#endif

volatile int32_t g_boot_p1_bcb_result;
volatile int32_t g_boot_p1_qspi_result;
volatile int32_t g_boot_p1_slot_result;
volatile int32_t g_boot_p1_app_result;
volatile int32_t g_boot_p1_recovery_result;

static int eeprom_read(uint8_t address, uint8_t *dst, uint16_t len)
{
    return boot_platform_eeprom_read(address, dst, len);
}

static int eeprom_write(uint8_t address, const uint8_t *src, uint16_t len)
{
    return boot_platform_eeprom_write(address, src, len);
}

static int internal_flash_read(void *ctx, uint32_t offset, uint8_t *dst, size_t len)
{
    const uint8_t *src;
    (void)ctx;

    if (dst == NULL || offset > OTA_APP_LENGTH || len > OTA_APP_LENGTH - offset)
    {
        return -1;
    }
    src = (const uint8_t *)(uintptr_t)(OTA_APP_ORIGIN + offset);
    memcpy(dst, src, len);
    return 0;
}

int main(void)
{
    static const bcb_hal_t bcb_hal = {eeprom_write, eeprom_read};
    boot_image_reader_t app_reader;
    boot_fw_expectations_t expected;
    uint8_t slot_raw[BOOT_SLOT_HEADER_SIZE];
    bcb_t active_bcb;

    g_boot_p1_bcb_result = BCB_ARBITER_ERROR;
    g_boot_p1_qspi_result = -1;
    g_boot_p1_slot_result = BOOT_SLOT_ERR_ARGUMENT;
    g_boot_p1_app_result = BOOT_FW_ERR_ARGUMENT;
    g_boot_p1_recovery_result = -1;

    if (boot_platform_init() != 0)
    {
        boot_platform_hold();
    }

    if (boot_platform_recovery_key_held())
    {
        boot_platform_log("BOOT: physical recovery condition accepted\r\n");
        do
        {
            g_boot_p1_recovery_result = boot_recovery_receive();
        } while (g_boot_p1_recovery_result != 0);

        boot_platform_log("BOOT: recovery verified; P1-4 handoff not installed\r\n");
        boot_platform_hold();
    }

    g_boot_p1_bcb_result = bcb_arbiter(&bcb_hal, &active_bcb);
    if (g_boot_p1_bcb_result == BCB_ARBITER_ERROR)
    {
        boot_platform_log("BOOT: BCB read failed\r\n");
    }

    g_boot_p1_qspi_result = boot_platform_qspi_init();
    if (g_boot_p1_qspi_result == 0)
    {
        if (boot_platform_qspi_read(OTA_EXT_CANDIDATE, slot_raw, sizeof(slot_raw)) == 0)
        {
            g_boot_p1_slot_result =
                boot_slot_header_parse(slot_raw, BOOT_SLOT_CANDIDATE, NULL);
        }
        else
        {
            g_boot_p1_slot_result = BOOT_SLOT_ERR_ARGUMENT;
        }
    }
    else
    {
        boot_platform_log("BOOT: QSPI unavailable, external slot branch skipped\r\n");
    }

    app_reader.read = internal_flash_read;
    app_reader.ctx = NULL;
    boot_fw_default_expectations(&expected);
    g_boot_p1_app_result = boot_fw_header_validate(&app_reader, &expected, NULL);
    boot_platform_log("BOOT: app fw_header: ");
    boot_platform_log(boot_fw_result_name((boot_fw_result_t)g_boot_p1_app_result));
    boot_platform_log("\r\n");

    boot_platform_log("BOOT: P1-4 handoff not installed; holding\r\n");
    boot_platform_hold();
    return 0;
}
