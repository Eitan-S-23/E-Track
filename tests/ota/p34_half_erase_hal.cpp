#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "OTA/ota_half_erase_plan.h"
#include "OTA/ota_backup.h"
#include "OTA/ota_staging.h"

/* Driver and restore internals have separate tests; these stubs observe HAL ordering. */
typedef enum { QSPI_OK, QSPI_ERR_PARAM, QSPI_ERR_REGION, QSPI_ERR_TIMEOUT } qspi_status_t;
static unsigned checks, calls, halves, blocks, restore_calls, fail_at, watchdogs;
static uint32_t addresses[300], sizes[300];
static bool disabled, restore_fail;
static uint32_t jedec = 0xef4018;
static unsigned stage_route;
static bcb_hal_t bcb;
#define CHECK(x) do { ++checks; if (!(x)) { fprintf(stderr, "HALF_ERASE_HAL_FAIL %d\n", __LINE__); exit(1); } } while (0)
#define QSPI_JEDEC_W25Q128 0xef4018
#define QSPI1 0
#define FALSE 0
#define OTA_COST_ERASE 0
#define OTA_COST_START(name)
#define OTA_COST_END(kind, name, bytes, result)

namespace HAL {
bool Qspi_IsOtaDisabled() { return disabled; }
uint32_t Qspi_GetJedecId() { return jedec; }
const bcb_hal_t *OTA_GetBcbHal() { return &bcb; }
ota_backup_result_t OTA_BackupStage(ota_backup_info_t *out);
}
typedef struct { uint32_t candidate_prepares; } ota_package_port_context_t;
static ota_package_port_context_t port;
static void service_app_watchdog() { ++watchdogs; }
static void qspi_xip_enable(int, int) {}
static int qspi_restore_xip(bool = true) { ++restore_calls; return restore_fail ? -1 : 0; }
static void install_cost_begin() {}
static void install_cost_end(const char *, int) {}
static void install_profile_begin() {}
static void install_profile_end(const char *, int) {}
static int base_read(void *, uint32_t, uint8_t *, uint32_t) { return 0; }
static int backup_flash_read(void *, uint32_t, uint8_t *, uint32_t) { return 0; }
static int backup_flash_program(void *, uint32_t, const uint8_t *, uint32_t) { return 0; }
static qspi_status_t erased(uint32_t address, uint32_t size) {
    CHECK(calls < 300); addresses[calls] = address; sizes[calls] = size;
    ++calls; halves += size == 32768; blocks += size == 65536;
    return calls == fail_at ? QSPI_ERR_TIMEOUT : QSPI_OK;
}
qspi_status_t qspi_erase(uint32_t a) { return erased(a, 4096); }
qspi_status_t qspi_erase_64k(uint32_t a) { return erased(a, 65536); }
qspi_status_t qspi_erase_32k(uint32_t a) { return erased(a, 32768); }

/* The generator inserts exact production functions here, not rewritten models. */
/* EXTRACTED_HAL */

ota_backup_result_t ota_backup_stage(const ota_backup_io_t *, const bcb_hal_t *, ota_backup_info_t *) {
    stage_route = 4; return OTA_BACKUP_OK;
}
ota_backup_result_t ota_backup_stage_with_block_erase(const ota_backup_io_t *, const bcb_hal_t *,
    ota_backup_info_t *, ota_backup_erase_64k_fn callback) {
    CHECK(callback != 0); stage_route = 64; return OTA_BACKUP_OK;
}
ota_backup_result_t ota_backup_stage_with_mixed_erase(const ota_backup_io_t *, const bcb_hal_t *,
    ota_backup_info_t *, ota_backup_erase_64k_fn full, ota_backup_erase_32k_fn half) {
    CHECK(full != 0 && half != 0); stage_route = 32; return OTA_BACKUP_OK;
}
static void reset() {
    calls = halves = blocks = restore_calls = fail_at = watchdogs = stage_route = 0;
    disabled = restore_fail = false; jedec = QSPI_JEDEC_W25Q128;
    memset(&port, 0, sizeof(port));
}

int main() {
    const bool mixed = CONFIG_OTA_INSTALL_BLOCK_ERASE && CONFIG_OTA_INSTALL_HALF_ERASE;
    const unsigned expected = CONFIG_OTA_INSTALL_BLOCK_ERASE ? (mixed ? 18 : 32) : 152;
    reset(); CHECK(candidate_prepare(&port, 616980) == 0);
    CHECK(calls == expected && restore_calls == 1 && port.candidate_prepares == 1);
    CHECK(halves == (mixed ? 2u : 0u));
    CHECK(blocks == (CONFIG_OTA_INSTALL_BLOCK_ERASE ? 8u : 0u));
    uint32_t cursor = OTA_EXT_CANDIDATE;
    for (unsigned i = 0; i < calls; ++i) {
        CHECK(addresses[i] == cursor && cursor % sizes[i] == 0);
        CHECK(i != 0 || sizes[i] == 4096);
        cursor += sizes[i];
    }
    CHECK(cursor == OTA_EXT_CANDIDATE + 622592);
    for (unsigned failure = 1; failure <= expected; ++failure) {
        reset(); fail_at = failure;
        CHECK(candidate_prepare(&port, 616980) == -1);
        CHECK(calls == failure && restore_calls == 1 && watchdogs >= calls + 1);
    }
    reset(); restore_fail = true; CHECK(candidate_prepare(&port, 616980) == -1 && restore_calls == 1);
    reset(); disabled = true; CHECK(candidate_prepare(&port, 616980) == -1 && calls == 0);
    reset(); CHECK(candidate_prepare(&port, 0) == -1 && calls == 0);
    CHECK(candidate_prepare(&port, OTA_APP_LENGTH + 1) == -1 && calls == 0);
    reset(); jedec = 0x1c7018; CHECK(candidate_prepare(&port, 616980) == 0 && calls == 152 && halves == 0 && blocks == 0);
    reset(); CHECK(HAL::OTA_BackupStage(0) == OTA_BACKUP_OK);
    CHECK(stage_route == (CONFIG_OTA_INSTALL_BLOCK_ERASE ? (mixed ? 32u : 64u) : 4u));
    reset(); jedec = 0x1c7018; CHECK(HAL::OTA_BackupStage(0) == OTA_BACKUP_OK && stage_route == 4);
    reset(); disabled = true; CHECK(HAL::OTA_BackupStage(0) == OTA_BACKUP_ERR_DISABLED && stage_route == 0);
#if CONFIG_OTA_INSTALL_HALF_ERASE
    reset(); CHECK(backup_flash_erase_32k(0, OTA_EXT_BACKUP) == -1 && calls == 0);
    CHECK(backup_flash_erase_32k(0, OTA_EXT_BACKUP + 4096) == -1 && calls == 0);
    CHECK(backup_flash_erase_32k(0, OTA_EXT_RECOVERY) == -1 && calls == 0);
    CHECK(backup_flash_erase_32k(0, OTA_EXT_CANDIDATE + 32768) == -1 && calls == 0);
    if (mixed) {
        reset(); CHECK(backup_flash_erase_32k(0, OTA_EXT_BACKUP + 32768) == 0 && calls == 1 && restore_calls == 1);
        reset(); fail_at = 1; CHECK(backup_flash_erase_32k(0, OTA_EXT_BACKUP + 32768) == -1 && calls == 1 && restore_calls == 1);
        reset(); restore_fail = true; CHECK(backup_flash_erase_32k(0, OTA_EXT_BACKUP + 32768) == -1 && calls == 1);
    } else {
        CHECK(backup_flash_erase_32k(0, OTA_EXT_BACKUP + 32768) == -1 && calls == 0);
    }
#endif
    printf("HALF_ERASE_HAL_PASS checks=%u block=%d half=%d\n", checks, CONFIG_OTA_INSTALL_BLOCK_ERASE, CONFIG_OTA_INSTALL_HALF_ERASE);
    return 0;
}
