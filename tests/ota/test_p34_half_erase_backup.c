#define main baseline_backup_main
#include "test_ota_backup.c"
#undef main
#include "OTA/ota_half_erase_plan.h"

static unsigned half_calls, half_fail_on, half_corrupt;

static int erase_half(void *ctx, uint32_t address)
{
    unsigned i;
    (void)ctx;
    check("half aligned payload", address % 32768 == 0 &&
          address >= OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE &&
          address <= g_erase_limit && 32768 <= g_erase_limit - address);
    check("half before programming", g_program_count == 0);
    for (i = 0; i < OTA_SLOT_HEADER_SIZE; ++i)
        check("half after header invalidation", g_flash[OTA_EXT_BACKUP + i] == 0xff);
    ++half_calls;
    if (half_fail_on == half_calls)
    {
        memset(g_flash + address, 0xff, 4096);
        return -1;
    }
    memset(g_flash + address, 0xff, 32768);
    if (half_corrupt && half_calls == 1) g_flash[address] = 0;
    g_erase_count += 8;
    return 0;
}

static void setup_half(uint32_t length)
{
    block_setup(length);
    half_calls = half_fail_on = half_corrupt = 0;
}

int main(int argc, char **argv)
{
    static const uint32_t sizes[] = {1120, 28672, 32768, 61440, 65536, 69632, 131089, 616980, OTA_APP_LENGTH};
    unsigned block, half, i;
    if (baseline_backup_main(argc, argv)) return 1;
    for (block = 0; block <= 1; ++block)
    for (half = 0; half <= 1; ++half)
    for (i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i)
    {
        ota_backup_info_t info;
        setup_half(sizes[i]);
        check("mixed succeeds", ota_backup_stage_with_mixed_erase(&g_flash_io, &g_bcb_hal,
              &info, block ? f_flash_erase_64k : 0, half ? erase_half : 0) == OTA_BACKUP_OK);
        check("mixed commit verified", info.commit_state == OTA_BACKUP_COMMIT_VERIFIED_STAGED &&
              eeprom_active_state() == BCB_STATE_STAGED);
        check("mixed backup exact", memcmp(g_flash + OTA_EXT_BACKUP + 4096, g_current, sizes[i]) == 0);
        check("mixed candidate exact", memcmp(g_flash + OTA_EXT_CANDIDATE + 4096, g_candidate, sizes[i]) == 0);
        check("mixed unchanged extent", g_flash[g_erase_limit] == 0xa7);
        check("mixed sector units", info.erase_count == g_erase_count &&
              info.erase_count == (sizes[i] + 4095) / 4096 + 2);
        check("mixed null callbacks", (block || g_block_attempts == 0) && (half || half_calls == 0));
        if (sizes[i] == 616980 && block && half)
            check("two half eight full blocks", half_calls == 2 && g_block_success == 8);
    }
    for (i = 0; i < 8; ++i)
    {
        ota_backup_info_t info;
        ota_backup_result_t result;
        setup_half(616980);
        if (i < 2) half_fail_on = i + 1;
        if (i == 2) half_corrupt = 1;
        if (i == 3) g_fail_erase_addr = OTA_EXT_BACKUP;
        if (i == 4) g_fail_program_addr = OTA_EXT_BACKUP + 4096 + 65536;
        if (i == 5) g_fail_program_addr = OTA_EXT_BACKUP + 28;
        if (i == 6) g_eeprom_write_fail = 1;
        if (i == 7) g_flash[OTA_EXT_CANDIDATE + 4096 + 100] ^= 1;
        result = ota_backup_stage_with_mixed_erase(&g_flash_io, &g_bcb_hal, &info, f_flash_erase_64k, erase_half);
        check("mixed failure rejects", result != OTA_BACKUP_OK);
        check("mixed failure confirmed", eeprom_active_state() == BCB_STATE_CONFIRMED);
        check("mixed failure honest counter", info.erase_count == g_erase_count);
        check("mixed failure unchanged extent", g_flash[g_erase_limit] == 0xa7);
        if (i < 2) check("partial half stops without writes", half_calls == i + 1 &&
                         g_program_count == 0 && g_eeprom_write_count == 0);
        if (i == 2) check("bad half bits caught", result == OTA_BACKUP_ERR_READBACK);
        if (i == 3 || i == 7) check("early failure no bulk", half_calls == 0 && g_block_attempts == 0);
    }
    printf("HALF_ERASE_BACKUP_PASS checks=%d failures=%d\n", checks, failures);
    return failures ? 1 : 0;
}
