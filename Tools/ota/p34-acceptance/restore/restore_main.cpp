#include "Arduino.h"
#include "Wire.h"
#include "EEPROM/EEPROM.h"
#include "HAL/HAL.h"
#include "HAL/HAL_OTA_Staging.h"
#include "OTA/ota_layout.h"
#include "OTA/ota_vtor_check.h"
#include "boot_crypto.h"
#include "boot_fw_header.h"
#include "boot_slot.h"
#include "restore_core.h"
#include <stddef.h>
#include <string.h>

#if CONFIG_QSPI_SELFTEST_ENABLE || CONFIG_EEPROM_BCB_STRESS
#error "Restoration must not include unrelated storage self-tests"
#endif

struct RestoreControl {
    uint32_t magic, schema, phase, error, tick, command, command_inverse, active;
    uint32_t from_version, to_version, backup_length, backup_crc32;
    uint32_t mutation_started, bcb_result, journal_clean, reserved;
    uint8_t eeprom_before[256], eeprom_after[256], boot_sha256[32], backup_sha256[32];
};
static_assert(sizeof(RestoreControl) == 640, "Host mailbox layout");
static_assert(offsetof(RestoreControl, eeprom_before) == 64, "Host EEPROM layout");
extern "C" {
volatile RestoreControl g_restore_control __attribute__((used, externally_visible));
}
static EEPROM eeprom;
static ota_staging_io_t staging;
static bcb_t before;
static restore_expect_t expected = {30287u, 30286u, 613952u, 2889683253u};
static const uint32_t COMMAND = 0x52333441u;
static const uint8_t wanted_boot[32] = {
    0x01,0xe4,0xb9,0xe1,0x62,0xbf,0xaa,0xf9,0xfd,0xa0,0x70,0xaa,0x13,0xc0,0xce,0xc3,0xf3,0x77,0xb8,0xd6,0x96,0xdb,0x01,0xf7,0x31,0xe0,0xab,0x3d,0x14,0x64,0xe5,0x27
};
static const uint8_t wanted_backup[32] = {
    0x9b,0x3a,0x4a,0x21,0x40,0x9c,0x59,0xb9,0x16,0x97,0x63,0x85,0xec,0x87,0x7b,0x7d,0x90,0xbd,0x7e,0x4c,0x90,0xb3,0x55,0x3f,0x0b,0x8d,0xf2,0xb0,0x2f,0xd7,0x87,0xdc
};

static int ee_read(uint8_t reg, uint8_t *data, uint16_t size)
{
    return eeprom.ReadBytes(reg, data, size) ? 0 : -1;
}
static int ee_write(uint8_t reg, const uint8_t *data, uint16_t size)
{
    if (size != BCB_SIZE || (reg != BCB_A_ADDR && reg != BCB_B_ADDR)) return -1;
    return eeprom.WriteBuffer(reg, data, size) ? 0 : -1;
}
static const bcb_hal_t bcb_hal = {ee_write, ee_read};

static void hash_bytes(const uint8_t *data, size_t size, uint8_t out[32])
{
    boot_sha256_ctx_t hash;
    boot_sha256_init(&hash);
    boot_sha256_update(&hash, data, size);
    boot_sha256_final(&hash, out);
}
static int backup_read(void *, uint32_t offset, uint8_t *data, size_t size)
{
    if (offset > expected.backup_length || size > expected.backup_length - offset) return -1;
    memcpy(data, (const void *)(QSPI1_MEM_BASE + OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE + offset), size);
    return 0;
}
static int validate_images()
{
    uint8_t sha[32];
    boot_slot_header_t slot;
    boot_fw_header_t image;
    boot_fw_expectations_t constraints;
    boot_image_reader_t reader = {backup_read, NULL};
    const uint8_t *backup = (const uint8_t *)(QSPI1_MEM_BASE + OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE);
    if (HAL::Qspi_IsOtaDisabled()) return 3;
    hash_bytes((const uint8_t *)OTA_BOOT_ORIGIN, OTA_BOOT_LENGTH, sha);
    memcpy((void *)g_restore_control.boot_sha256, sha, 32);
    if (memcmp(sha, wanted_boot, 32)) return 4;
    if (boot_slot_header_parse((const uint8_t *)(QSPI1_MEM_BASE + OTA_EXT_BACKUP),
                              BOOT_SLOT_BACKUP, &slot) != BOOT_SLOT_OK ||
        slot.payload_len != expected.backup_length || slot.version_code != expected.to_version ||
        slot.payload_crc32 != expected.backup_crc32) return 5;
    hash_bytes(backup, expected.backup_length, sha);
    memcpy((void *)g_restore_control.backup_sha256, sha, 32);
    if (memcmp(sha, wanted_backup, 32) || boot_crc32(backup, expected.backup_length) != expected.backup_crc32)
        return 6;
    boot_fw_default_expectations(&constraints);
    if (boot_fw_header_validate(&reader, &constraints, &image) != BOOT_FW_OK ||
        image.version_code != expected.to_version || image.image_len != expected.backup_length ||
        memcmp(slot.sha8, image.image_sha256, 8)) return 7;
    return 0;
}

static int clear_journal()
{
    uint8_t bytes[128];
    if (staging.erase_4k(staging.ctx, OTA_EXT_STAGING) != 0) return -1;
    for (uint32_t offset = 0; offset < OTA_STAGING_PAYLOAD_OFFSET; offset += sizeof(bytes)) {
        if (staging.read(staging.ctx, OTA_EXT_STAGING + offset, bytes, sizeof(bytes)) != 0) return -1;
        for (size_t i = 0; i < sizeof(bytes); ++i) if (bytes[i] != 0xff) return -1;
    }
    g_restore_control.journal_clean = 1;
    return 0;
}

static void fail(uint32_t error)
{
    g_restore_control.error = error;
    __DMB();
    g_restore_control.phase = 4;
    SEGGER_RTT_printf(0, "RESTOREP34: FAILED error=%lu\r\n", (unsigned long)error);
}

int main()
{
    ota_vtor_check();
    ota_handoff_capture();
    Core_Init();
    SEGGER_RTT_Init();
    g_restore_control.magic = 0x41343352u;
    g_restore_control.schema = 1;
    g_restore_control.from_version = expected.from_version;
    g_restore_control.to_version = expected.to_version;
    g_restore_control.backup_length = expected.backup_length;
    g_restore_control.backup_crc32 = expected.backup_crc32;
    if (!Wire.begin() || !eeprom.Init()) fail(1);
    else if (!eeprom.ReadBytes(0, (uint8_t *)g_restore_control.eeprom_before, 256) ||
             g_restore_control.eeprom_before[255] != 0x55) fail(2);
    else {
        HAL::Qspi_Init();
        HAL::OTA_StagingGetIo(&staging);
        int error = validate_images();
        bcb_arbiter_result_t active;
        if (error) fail((uint32_t)error);
        else if (restore_prepare(&bcb_hal, &expected, &before, &active) != RESTORE_OK) fail(8);
        else {
            g_restore_control.active = (uint32_t)active;
            __DMB();
            g_restore_control.phase = 1;
            SEGGER_RTT_printf(0, "RESTOREP34: READY backup verified; waiting for host command\r\n");
        }
    }
    uint32_t start = millis();
    for (;;) {
        g_restore_control.tick = millis();
        if (g_restore_control.phase == 1 && g_restore_control.command == COMMAND &&
            g_restore_control.command_inverse == ~COMMAND) {
            g_restore_control.command = 0;
            g_restore_control.phase = 2;
            int error = validate_images();
            if (error) fail((uint32_t)error);
            else {
                bcb_t after;
                memset(&after, 0, sizeof(after));
                g_restore_control.mutation_started = 1;
                error = restore_execute(&bcb_hal, &expected, &before, clear_journal, &after);
                g_restore_control.bcb_result = (uint32_t)error;
                bool read_ok = eeprom.ReadBytes(0, (uint8_t *)g_restore_control.eeprom_after, 256);
                if (!read_ok || memcmp((const void *)(g_restore_control.eeprom_before + 128),
                                      (const void *)(g_restore_control.eeprom_after + 128), 128)) fail(9);
                else if (error) fail(20u + (uint32_t)error);
                else {
                    __DMB();
                    g_restore_control.phase = 3;
                    SEGGER_RTT_printf(0, "RESTOREP34: ROLLBACK_COMMITTED; reset via host after readback\r\n");
                }
            }
        }
        if (g_restore_control.phase == 1 && (uint32_t)(millis() - start) >= 180000u) {
            g_restore_control.phase = 5;
        }
        __WFI();
    }
}
