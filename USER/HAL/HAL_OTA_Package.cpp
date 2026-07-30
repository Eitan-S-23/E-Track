#include "HAL/HAL_OTA_Package.h"

#include "HAL/HAL.h"
#if defined(P2_2_TEST_ENABLE)
#include "EEPROM/eeprom_bcb.h"
#include "OTA/ota_p2_2_test.h"
#include "boot_crypto.h"
#endif
#include "OTA/ota_staging.h"
#include "W25Q128/qspi_cmd_en25qh128a.h"

#include <string.h>

enum ota_overlay_owner_t
{
    OTA_OVERLAY_FREE = 0,
    OTA_OVERLAY_LIVE_MAP = 1,
    OTA_OVERLAY_PACKAGE = 2
};

typedef struct ota_package_port_context_t
{
    uint32_t candidate_prepares;
    uint32_t candidate_programs;
    uint32_t candidate_bytes;
} ota_package_port_context_t;

extern "C"
{
#if defined(__CC_ARM)
__attribute__((section(".ota_overlay"), zero_init, aligned(8)))
#elif defined(__GNUC__) && !defined(_WIN32)
__attribute__((section(".ota_overlay,\"aw\",%nobits @"), aligned(8)))
#endif
uint8_t g_ota_overlay_workspace[OTA_PACKAGE_WORKSPACE_SIZE];
}

static volatile uint8_t g_ota_overlay_owner = OTA_OVERLAY_FREE;
static ota_package_port_context_t g_ota_package_port;

static uint32_t enter_critical(void)
{
    uint32_t primask = __get_PRIMASK();
    __disable_irq();
    return primask;
}

static void leave_critical(uint32_t primask)
{
    if (primask == 0u)
    {
        __enable_irq();
    }
}

static bool overlay_acquire(uint8_t owner)
{
    uint32_t primask = enter_critical();
    bool acquired =
        (uintptr_t)g_ota_overlay_workspace ==
            (uintptr_t)OTA_OVERLAY_ORIGIN &&
        g_ota_overlay_owner == OTA_OVERLAY_FREE;

    if (acquired)
    {
        g_ota_overlay_owner = owner;
    }
    leave_critical(primask);
    return acquired;
}

static void overlay_release(uint8_t owner)
{
    uint32_t primask = enter_critical();

    if (g_ota_overlay_owner == owner)
    {
        g_ota_overlay_owner = OTA_OVERLAY_FREE;
    }
    leave_critical(primask);
}

static int qspi_restore_xip(void)
{
    return en25qh128a_qspi_xip_init() == QSPI_OK ? 0 : -1;
}

static int package_range_ok(uint32_t offset, uint32_t len)
{
    return offset <= OTA_ETU_MAX_LENGTH &&
           len <= OTA_ETU_MAX_LENGTH - offset &&
           OTA_STAGING_PAYLOAD_OFFSET + offset <= OTA_EXT_STAGING_LENGTH &&
           len <= OTA_EXT_STAGING_LENGTH -
                      (OTA_STAGING_PAYLOAD_OFFSET + offset);
}

static int candidate_range_ok(uint32_t offset, uint32_t len)
{
    return offset <= OTA_APP_LENGTH && len <= OTA_APP_LENGTH - offset &&
           OTA_SLOT_HEADER_SIZE + offset <= OTA_EXT_SLOT_LENGTH &&
           len <= OTA_EXT_SLOT_LENGTH - (OTA_SLOT_HEADER_SIZE + offset);
}

static int package_read(void *ctx, uint32_t offset,
                        uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == 0 || !package_range_ok(offset, len) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    memcpy(dst,
           (const void *)(QSPI1_MEM_BASE + OTA_EXT_STAGING +
                          OTA_STAGING_PAYLOAD_OFFSET + offset),
           len);
    return 0;
}

static int candidate_prepare(void *ctx, uint32_t image_len)
{
    ota_package_port_context_t *port =
        (ota_package_port_context_t *)ctx;
    uint32_t erase_len;
    uint32_t offset;
    qspi_status_t result = QSPI_OK;
    int restore_result;

    (void)ctx;
    if (image_len == 0u || image_len > OTA_APP_LENGTH ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    erase_len = OTA_SLOT_HEADER_SIZE +
                ((image_len + OTA_STAGING_BLOCK_SIZE - 1u) &
                 ~(OTA_STAGING_BLOCK_SIZE - 1u));
    if (erase_len > OTA_EXT_SLOT_LENGTH)
    {
        return -1;
    }

    ++port->candidate_prepares;
    qspi_xip_enable(QSPI1, FALSE);
    for (offset = 0u; offset < erase_len;
         offset += OTA_STAGING_BLOCK_SIZE)
    {
        result = qspi_erase(OTA_EXT_CANDIDATE + offset);
        if (result != QSPI_OK)
        {
            break;
        }
    }
    restore_result = qspi_restore_xip();
    return result == QSPI_OK && restore_result == 0 ? 0 : -1;
}

static int candidate_program(void *ctx, uint32_t offset,
                             const uint8_t *src, uint32_t len)
{
    ota_package_port_context_t *port =
        (ota_package_port_context_t *)ctx;
    qspi_status_t result;
    int restore_result;

    (void)ctx;
    if (src == 0 || len == 0u || !candidate_range_ok(offset, len) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    ++port->candidate_programs;
    port->candidate_bytes += len;
    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_data_write(OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE +
                                 offset,
                             len, (uint8_t *)src);
    restore_result = qspi_restore_xip();
    return result == QSPI_OK && restore_result == 0 ? 0 : -1;
}

static int candidate_read(void *ctx, uint32_t offset,
                          uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == 0 || !candidate_range_ok(offset, len) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    memcpy(dst,
           (const void *)(QSPI1_MEM_BASE + OTA_EXT_CANDIDATE +
                          OTA_SLOT_HEADER_SIZE + offset),
           len);
    return 0;
}

static int workspace_acquire(void *ctx, uint8_t **workspace,
                             uint32_t *workspace_len)
{
    (void)ctx;
    if (workspace == 0 || workspace_len == 0 ||
        !overlay_acquire(OTA_OVERLAY_PACKAGE))
    {
        return -1;
    }
    *workspace = g_ota_overlay_workspace;
    *workspace_len = sizeof(g_ota_overlay_workspace);
    return 0;
}

static void workspace_release(void *ctx, uint8_t *workspace,
                              uint32_t workspace_len)
{
    (void)ctx;
    (void)workspace;
    (void)workspace_len;
    overlay_release(OTA_OVERLAY_PACKAGE);
}

bool HAL::OTA_OverlayAcquireLiveMap()
{
    return overlay_acquire(OTA_OVERLAY_LIVE_MAP);
}

void HAL::OTA_OverlayReleaseLiveMap()
{
    overlay_release(OTA_OVERLAY_LIVE_MAP);
}

bool HAL::OTA_OverlayIsOtaOwned()
{
    return g_ota_overlay_owner == OTA_OVERLAY_PACKAGE;
}

ota_package_result_t HAL::OTA_PackageApplyStaging(
    uint32_t package_len,
    uint32_t current_vcode,
    ota_package_info_t *out_info)
{
    ota_package_io_t io;
    ota_package_device_t device;

    if (Qspi_IsOtaDisabled() || qspi_restore_xip() != 0)
    {
        return OTA_PACKAGE_ERR_READ;
    }
    memset(&g_ota_package_port, 0, sizeof(g_ota_package_port));
    io.ctx = &g_ota_package_port;
    io.package_read = package_read;
    io.candidate_prepare = candidate_prepare;
    io.candidate_program = candidate_program;
    io.candidate_read = candidate_read;
    io.workspace_acquire = workspace_acquire;
    io.workspace_release = workspace_release;
    device.current_vcode = current_vcode;
    device.hardware_rev = 1u;
    device.layout_id = 1u;
    device.boot_version = 1u;
    return ota_package_apply_full(&io, &device, package_len, out_info);
}

#if defined(P2_2_TEST_ENABLE)
static uint32_t evidence_control_crc(uint32_t offset, uint32_t len)
{
    return boot_crc32(
        (const uint8_t *)(uintptr_t)(OTA_P2_2_CONTROL_ADDRESS + offset),
        len);
}

static void evidence_write_bytes(uint32_t offset,
                                 const uint8_t *src, uint32_t len)
{
    volatile uint8_t *control = ota_p2_2_control();
    uint32_t index;

    for (index = 0u; index < len; ++index)
    {
        control[offset + index] = src[index];
    }
}

static int evidence_command_valid(void)
{
    uint32_t package_len = ota_p2_2_read_u32(OTA_P2_2_OFF_PACKAGE_LEN);
    uint32_t opcode = ota_p2_2_read_u32(OTA_P2_2_OFF_OPCODE);
    uint32_t cookie = ota_p2_2_read_u32(OTA_P2_2_OFF_COOKIE);

    return ota_p2_2_read_u32(OTA_P2_2_OFF_MAGIC) ==
               OTA_P2_2_COMMAND_MAGIC &&
           ota_p2_2_read_u32(OTA_P2_2_OFF_VERSION) == OTA_P2_2_VERSION &&
           opcode == OTA_P2_2_OPCODE_APPLY &&
           (opcode ^ ota_p2_2_read_u32(
                         OTA_P2_2_OFF_OPCODE_INVERSE)) == UINT32_MAX &&
           cookie == OTA_P2_2_COOKIE &&
           (cookie ^ ota_p2_2_read_u32(
                         OTA_P2_2_OFF_COOKIE_INVERSE)) == UINT32_MAX &&
           package_len >= OTA_PACKAGE_HEADER_SIZE &&
           package_len <= OTA_P2_2_PACKAGE_CAPACITY &&
           ota_p2_2_read_u32(OTA_P2_2_OFF_COMMAND_CRC32) ==
               evidence_control_crc(OTA_P2_2_COMMAND_CRC_OFFSET,
                                    OTA_P2_2_COMMAND_CRC_LENGTH) &&
           ota_p2_2_read_u32(OTA_P2_2_OFF_PACKAGE_CRC32) ==
               evidence_control_crc(OTA_P2_2_PACKAGE_OFFSET,
                                    package_len);
}

static int evidence_read_bcb(uint8_t raw[OTA_P2_2_BCB_SNAPSHOT_SIZE])
{
    return HAL::EEPROM_ReadBufferSafe(BCB_A_ADDR, raw, BCB_SIZE) &&
           HAL::EEPROM_ReadBufferSafe(BCB_B_ADDR, raw + BCB_SIZE,
                                      BCB_SIZE);
}

static int evidence_stage_package(uint32_t package_len)
{
    const uint8_t *package =
        (const uint8_t *)(uintptr_t)(OTA_P2_2_CONTROL_ADDRESS +
                                    OTA_P2_2_PACKAGE_OFFSET);
    uint32_t address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    qspi_status_t result;
    int restore_result;

    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_erase(address);
    if (result == QSPI_OK)
    {
        result = qspi_data_write(address, package_len,
                                 (uint8_t *)package);
    }
    restore_result = qspi_restore_xip();
    if (result != QSPI_OK || restore_result != 0)
    {
        return -1;
    }
    return memcmp((const void *)(QSPI1_MEM_BASE + address), package,
                  package_len) == 0
               ? 0
               : -1;
}

static int evidence_workspace_zero(void)
{
    volatile const uint8_t *workspace = g_ota_overlay_workspace;
    uint32_t index;

    for (index = 0u; index < sizeof(g_ota_overlay_workspace); ++index)
    {
        if (workspace[index] != 0u)
        {
            return 0;
        }
    }
    return 1;
}

static int evidence_candidate_header_erased(void)
{
    volatile const uint8_t *header =
        (volatile const uint8_t *)(QSPI1_MEM_BASE + OTA_EXT_CANDIDATE);
    uint32_t index;

    for (index = 0u; index < OTA_SLOT_HEADER_SIZE; ++index)
    {
        if (header[index] != 0xFFu)
        {
            return 0;
        }
    }
    return 1;
}

static void evidence_finish(uint32_t status, uint32_t detail)
{
    ota_p2_2_write_u32(OTA_P2_2_OFF_DETAIL, detail);
    ota_p2_2_write_u32(OTA_P2_2_OFF_STATUS, status);
    ota_p2_2_write_u32(
        OTA_P2_2_OFF_RESULT_CRC32,
        evidence_control_crc(OTA_P2_2_RESULT_CRC_OFFSET,
                             OTA_P2_2_RESULT_CRC_LENGTH));
    __asm volatile("dsb 0xF" ::: "memory");
    ota_p2_2_write_u32(OTA_P2_2_OFF_MAGIC, OTA_P2_2_DONE_MAGIC);
    __asm volatile("dsb 0xF\nisb 0xF" ::: "memory");
}

extern "C" void HAL_OTA_PackageEvidenceReady(void)
    __attribute__((noinline, noclone, used, externally_visible));

extern "C" void HAL_OTA_PackageEvidenceReady(void)
{
    __asm volatile("nop" ::: "memory");
}

extern "C" void HAL_OTA_PackageEvidenceDone(void)
    __attribute__((noinline, noclone, used, externally_visible));

extern "C" void HAL_OTA_PackageEvidenceDone(void)
{
    volatile uint32_t status =
        ota_p2_2_read_u32(OTA_P2_2_OFF_STATUS);

    (void)status;
    __asm volatile("nop" ::: "memory");
}

bool HAL::OTA_PackageEvidenceRun()
{
    uint8_t bcb_before[OTA_P2_2_BCB_SNAPSHOT_SIZE];
    uint8_t bcb_after[OTA_P2_2_BCB_SNAPSHOT_SIZE];
    ota_package_info_t info;
    ota_package_result_t actual = OTA_PACKAGE_ERR_READ;
    int32_t expected;
    uint32_t package_len;
    uint32_t current_vcode;
    uint32_t actual_package_crc;
    uint32_t detail = 0u;
    uint32_t staging_erases = 0u;
    uint32_t staging_programs = 0u;
    int bcb_before_ok;
    int bcb_after_ok;
    int bcb_equal;
    int workspace_zero;
    int header_erased;

    if (!evidence_command_valid())
    {
        return false;
    }

    package_len = ota_p2_2_read_u32(OTA_P2_2_OFF_PACKAGE_LEN);
    current_vcode = ota_p2_2_read_u32(OTA_P2_2_OFF_CURRENT_VCODE);
    expected = (int32_t)ota_p2_2_read_u32(
        OTA_P2_2_OFF_EXPECTED_RESULT);
    actual_package_crc = evidence_control_crc(OTA_P2_2_PACKAGE_OFFSET,
                                              package_len);
    ota_p2_2_write_u32(OTA_P2_2_OFF_STATUS, OTA_P2_2_STATUS_RUNNING);
    ota_p2_2_write_u32(OTA_P2_2_OFF_DETAIL, 0u);
    memset(&info, 0, sizeof(info));
    memset(bcb_before, 0, sizeof(bcb_before));
    memset(bcb_after, 0, sizeof(bcb_after));

    bcb_before_ok = evidence_read_bcb(bcb_before);
    if (!bcb_before_ok)
    {
        detail = 0x10u;
    }
    else
    {
        evidence_write_bytes(OTA_P2_2_OFF_BCB_BEFORE, bcb_before,
                             sizeof(bcb_before));
    }

    if (detail == 0u)
    {
        if (evidence_stage_package(package_len) != 0)
        {
            detail = 0x20u;
        }
        else
        {
            staging_erases = 1u;
            staging_programs = 1u;
            actual = OTA_PackageApplyStaging(package_len, current_vcode,
                                             &info);
        }
    }

    bcb_after_ok = evidence_read_bcb(bcb_after);
    if (bcb_after_ok)
    {
        evidence_write_bytes(OTA_P2_2_OFF_BCB_AFTER, bcb_after,
                             sizeof(bcb_after));
    }
    else if (detail == 0u)
    {
        detail = 0x30u;
    }

    bcb_equal = bcb_before_ok && bcb_after_ok &&
                memcmp(bcb_before, bcb_after, sizeof(bcb_before)) == 0;
    workspace_zero = evidence_workspace_zero();
    header_erased = evidence_candidate_header_erased();

    ota_p2_2_write_u32(OTA_P2_2_OFF_ACTUAL_RESULT,
                       (uint32_t)(int32_t)actual);
    ota_p2_2_write_u32(OTA_P2_2_OFF_TARGET_VCODE, info.target_vcode);
    ota_p2_2_write_u32(OTA_P2_2_OFF_IMAGE_LEN, info.image_len);
    ota_p2_2_write_u32(OTA_P2_2_OFF_WORKSPACE_PEAK,
                       info.workspace_peak);
    ota_p2_2_write_u32(OTA_P2_2_OFF_PAYLOAD_LEN, info.payload_len);
    ota_p2_2_write_u32(OTA_P2_2_OFF_PAYLOAD_CRC32,
                       info.payload_crc32);
    ota_p2_2_write_u32(OTA_P2_2_OFF_CANDIDATE_PREPARES,
                       g_ota_package_port.candidate_prepares);
    ota_p2_2_write_u32(OTA_P2_2_OFF_CANDIDATE_PROGRAMS,
                       g_ota_package_port.candidate_programs);
    ota_p2_2_write_u32(OTA_P2_2_OFF_CANDIDATE_BYTES,
                       g_ota_package_port.candidate_bytes);
    ota_p2_2_write_u32(OTA_P2_2_OFF_STAGING_ERASES,
                       staging_erases);
    ota_p2_2_write_u32(OTA_P2_2_OFF_STAGING_PROGRAMS,
                       staging_programs);
    ota_p2_2_write_u32(OTA_P2_2_OFF_WORKSPACE_ZERO,
                       (uint32_t)workspace_zero);
    ota_p2_2_write_u32(OTA_P2_2_OFF_CANDIDATE_HEADER_ERASED,
                       (uint32_t)header_erased);
    ota_p2_2_write_u32(OTA_P2_2_OFF_BCB_EQUAL, (uint32_t)bcb_equal);
    ota_p2_2_write_u32(OTA_P2_2_OFF_ACTUAL_PACKAGE_CRC32,
                       actual_package_crc);
    evidence_write_bytes(OTA_P2_2_OFF_IMAGE_SHA256,
                         info.image_sha256, sizeof(info.image_sha256));

    if (detail == 0u && (int32_t)actual != expected)
    {
        detail = 0x40u;
    }
    if (detail == 0u && !bcb_equal)
    {
        detail = 0x41u;
    }
    if (detail == 0u && !workspace_zero)
    {
        detail = 0x42u;
    }
    if (detail == 0u && actual == OTA_PACKAGE_OK &&
        (!header_erased || info.target_vcode != 20800u ||
         info.image_len != 4096u ||
         g_ota_package_port.candidate_prepares != 1u ||
         g_ota_package_port.candidate_programs != 4u ||
         g_ota_package_port.candidate_bytes != 4096u))
    {
        detail = 0x43u;
    }
    if (detail == 0u && actual != OTA_PACKAGE_OK &&
        (g_ota_package_port.candidate_prepares != 0u ||
         g_ota_package_port.candidate_programs != 0u ||
         g_ota_package_port.candidate_bytes != 0u))
    {
        detail = 0x44u;
    }

    SEGGER_RTT_printf(
        0,
        "P2_2: actual=%ld expected=%ld detail=0x%02lX "
        "prepare=%lu program=%lu bytes=%lu bcb=%u wipe=%u\r\n",
        (long)actual, (long)expected, (unsigned long)detail,
        (unsigned long)g_ota_package_port.candidate_prepares,
        (unsigned long)g_ota_package_port.candidate_programs,
        (unsigned long)g_ota_package_port.candidate_bytes,
        (unsigned)bcb_equal, (unsigned)workspace_zero);
    evidence_finish(detail == 0u ? OTA_P2_2_STATUS_PASS
                                 : OTA_P2_2_STATUS_FAIL,
                    detail);
    HAL_OTA_PackageEvidenceDone();
    return true;
}
#endif
