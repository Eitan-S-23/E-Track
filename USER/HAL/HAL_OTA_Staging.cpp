#include "HAL/HAL_OTA_Staging.h"

#include "HAL/HAL.h"
#include "OTA/ota_p2_1_test.h"
#include "W25Q128/qspi_cmd_en25qh128a.h"

#include <string.h>

typedef struct staging_port_context_t
{
    uint32_t header_erases;
    uint32_t data_erases;
    uint32_t data_programs;
    uint8_t evidence_enabled;
} staging_port_context_t;

static staging_port_context_t g_staging_port;

static int staging_range_ok(uint32_t address, uint32_t len)
{
    return address >= OTA_EXT_STAGING &&
           len <= OTA_EXT_STAGING_LENGTH &&
           address - OTA_EXT_STAGING <= OTA_EXT_STAGING_LENGTH - len;
}

static int staging_restore_xip(void)
{
    return en25qh128a_qspi_xip_init() == QSPI_OK ? 0 : -1;
}

static int staging_read(void *ctx, uint32_t address,
                        uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == 0 || !staging_range_ok(address, len) ||
        HAL::Qspi_IsOtaDisabled() || staging_restore_xip() != 0)
    {
        return -1;
    }
    memcpy(dst, (const void *)(QSPI1_MEM_BASE + address), len);
    return 0;
}

static int staging_erase(void *ctx, uint32_t address)
{
    staging_port_context_t *port = (staging_port_context_t *)ctx;
    qspi_status_t result;
    int restore_result;

    if (!staging_range_ok(address, OTA_STAGING_BLOCK_SIZE) ||
        (address & (OTA_STAGING_BLOCK_SIZE - 1u)) != 0u ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_erase(address);
    restore_result = staging_restore_xip();
    if (result != QSPI_OK || restore_result != 0)
    {
        return -1;
    }
    if (address == OTA_EXT_STAGING)
    {
        ++port->header_erases;
    }
    else
    {
        ++port->data_erases;
    }
    return 0;
}

static int staging_program(void *ctx, uint32_t address,
                           const uint8_t *src, uint32_t len)
{
    staging_port_context_t *port = (staging_port_context_t *)ctx;
    qspi_status_t result;
    int restore_result;

    if (src == 0 || len == 0u || !staging_range_ok(address, len) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_data_write(address, len, (uint8_t *)src);
    restore_result = staging_restore_xip();
    if (result != QSPI_OK || restore_result != 0)
    {
        return -1;
    }
    if (address >= OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET)
    {
        ++port->data_programs;
    }
    return 0;
}

#if defined(P2_1_TEST_ENABLE)
static uint32_t control_crc(uint32_t offset, uint32_t len)
{
    uint8_t bytes[64];
    uint32_t index;

    if (len > sizeof(bytes))
    {
        return 0u;
    }
    for (index = 0u; index < len; ++index)
    {
        bytes[index] = ota_p2_1_control()[offset + index];
    }
    return ota_staging_crc32(bytes, len);
}

static int control_command_valid(void)
{
    return ota_p2_1_read_u32(OTA_P2_1_OFF_MAGIC) ==
               OTA_P2_1_COMMAND_MAGIC &&
           ota_p2_1_read_u32(OTA_P2_1_OFF_VERSION) == OTA_P2_1_VERSION &&
           ota_p2_1_read_u32(OTA_P2_1_OFF_OPCODE) ==
               OTA_P2_1_OPCODE_REENTRY &&
           (ota_p2_1_read_u32(OTA_P2_1_OFF_OPCODE) ^
            ota_p2_1_read_u32(OTA_P2_1_OFF_OPCODE_INVERSE)) == UINT32_MAX &&
           ota_p2_1_read_u32(OTA_P2_1_OFF_COOKIE) == OTA_P2_1_COOKIE &&
           (ota_p2_1_read_u32(OTA_P2_1_OFF_COOKIE) ^
            ota_p2_1_read_u32(OTA_P2_1_OFF_COOKIE_INVERSE)) == UINT32_MAX &&
           ota_p2_1_read_u32(OTA_P2_1_OFF_COMMAND_CRC32) ==
               control_crc(OTA_P2_1_COMMAND_CRC_OFFSET,
                           OTA_P2_1_COMMAND_CRC_LENGTH);
}

static void control_write_result_crc(void)
{
    ota_p2_1_write_u32(
        OTA_P2_1_OFF_RESULT_CRC32,
        control_crc(OTA_P2_1_RESULT_CRC_OFFSET,
                    OTA_P2_1_RESULT_CRC_LENGTH));
}

static void control_write_counts(void)
{
    ota_p2_1_write_u32(OTA_P2_1_OFF_HEADER_ERASES,
                       g_staging_port.header_erases);
    ota_p2_1_write_u32(OTA_P2_1_OFF_DATA_ERASES,
                       g_staging_port.data_erases);
    ota_p2_1_write_u32(OTA_P2_1_OFF_DATA_PROGRAMS,
                       g_staging_port.data_programs);
}

static void control_finish(uint32_t status, uint32_t detail)
{
    ota_p2_1_write_u32(OTA_P2_1_OFF_DETAIL, detail);
    control_write_counts();
    ota_p2_1_write_u32(OTA_P2_1_OFF_STATUS, status);
    control_write_result_crc();
    __asm volatile("dsb 0xF" ::: "memory");
    ota_p2_1_write_u32(OTA_P2_1_OFF_MAGIC, OTA_P2_1_DONE_MAGIC);
    __asm volatile("dsb 0xF\nisb 0xF" ::: "memory");
}

#if defined(__GNUC__) && !defined(__CC_ARM)
extern "C" void HAL_OTA_StagingEvidenceCheckpoint(void)
    __attribute__((noinline, noclone, used, externally_visible));
extern "C" void HAL_OTA_StagingEvidenceDone(void)
    __attribute__((noinline, noclone, used, externally_visible));
#endif
extern "C" void HAL_OTA_StagingEvidenceCheckpoint(void)
{
    volatile uint32_t status =
        ota_p2_1_read_u32(OTA_P2_1_OFF_STATUS);

    (void)status;
    __asm volatile("nop" ::: "memory");
}

extern "C" void HAL_OTA_StagingEvidenceDone(void)
{
    volatile uint32_t status =
        ota_p2_1_read_u32(OTA_P2_1_OFF_STATUS);

    (void)status;
    __asm volatile("nop" ::: "memory");
}

static int staging_checkpoint(void *ctx, uint32_t point,
                              uint32_t arg0, uint32_t arg1)
{
    staging_port_context_t *port = (staging_port_context_t *)ctx;
    uint8_t persistent = 0u;

    if (!port->evidence_enabled ||
        point != OTA_STAGING_CP_AFTER_BLOCK_READBACK)
    {
        return 0;
    }
    if (staging_read(ctx, OTA_EXT_STAGING + OTA_STAGING_BITMAP_OFFSET,
                     &persistent, 1u) != 0)
    {
        control_finish(OTA_P2_1_STATUS_FAIL, 0x31u);
        return -1;
    }
    ota_p2_1_write_u32(OTA_P2_1_OFF_CHECKPOINT, point);
    ota_p2_1_write_u32(OTA_P2_1_OFF_DURABLE_AFTER, arg1);
    ota_p2_1_write_u32(OTA_P2_1_OFF_PERSISTENT_BITMAP, persistent);
    ota_p2_1_write_u32(OTA_P2_1_OFF_SEGMENT_BITMAP, UINT32_MAX);
    control_write_counts();
    ota_p2_1_write_u32(OTA_P2_1_OFF_STATUS,
                       OTA_P2_1_STATUS_CHECKPOINT);
    control_write_result_crc();
    SEGGER_RTT_printf(0,
        "P2_1: checkpoint=%lu block=%lu durable=%lu bitmap=0x%02X "
        "erase=%lu program=%lu\r\n",
        (unsigned long)point, (unsigned long)arg0,
        (unsigned long)arg1, (unsigned)persistent,
        (unsigned long)port->data_erases,
        (unsigned long)port->data_programs);
    __asm volatile("dsb 0xF\nisb 0xF" ::: "memory");
    HAL_OTA_StagingEvidenceCheckpoint();
    return 0;
}

static uint32_t evidence_pattern_crc(void)
{
    uint8_t data[OTA_STAGING_SEGMENT_SIZE];
    static uint8_t full[OTA_STAGING_BLOCK_SIZE];
    uint32_t offset;
    uint32_t index;

    for (offset = 0u; offset < sizeof(full);
         offset += OTA_STAGING_SEGMENT_SIZE)
    {
        for (index = 0u; index < sizeof(data); ++index)
        {
            data[index] = (uint8_t)((offset + index) * 17u + 3u);
        }
        memcpy(full + offset, data, sizeof(data));
    }
    return ota_staging_crc32(full, sizeof(full));
}

bool HAL::OTA_StagingEvidenceRun()
{
    static ota_staging_receiver_t receiver;
    ota_staging_progress_t progress;
    ota_staging_io_t io;
    uint8_t session_sha256[32];
    uint8_t segment[OTA_STAGING_SEGMENT_SIZE];
    uint8_t persistent = 0u;
    uint8_t begin_resumed = 0u;
    uint32_t prior_status;
    uint32_t offset;
    uint32_t index;
    ota_staging_result_t result = OTA_STAGING_OK;

    if (!control_command_valid())
    {
        return false;
    }
    prior_status = ota_p2_1_read_u32(OTA_P2_1_OFF_STATUS);
    if (prior_status != OTA_P2_1_STATUS_ARMED &&
        prior_status != OTA_P2_1_STATUS_CHECKPOINT)
    {
        control_finish(OTA_P2_1_STATUS_FAIL, 0x10u);
        return true;
    }
    for (index = 0u; index < sizeof(session_sha256); ++index)
    {
        session_sha256[index] =
            ota_p2_1_control()[OTA_P2_1_OFF_SESSION_SHA256 + index];
    }
    if (prior_status == OTA_P2_1_STATUS_CHECKPOINT)
    {
        g_staging_port.header_erases =
            ota_p2_1_read_u32(OTA_P2_1_OFF_HEADER_ERASES);
        g_staging_port.data_erases =
            ota_p2_1_read_u32(OTA_P2_1_OFF_DATA_ERASES);
        g_staging_port.data_programs =
            ota_p2_1_read_u32(OTA_P2_1_OFF_DATA_PROGRAMS);
    }
    else
    {
        g_staging_port.header_erases = 0u;
        g_staging_port.data_erases = 0u;
        g_staging_port.data_programs = 0u;
    }
    g_staging_port.evidence_enabled = 1u;
    OTA_StagingGetIo(&io);
    io.checkpoint = staging_checkpoint;
    ota_p2_1_write_u32(OTA_P2_1_OFF_STATUS, OTA_P2_1_STATUS_RUNNING);
    ota_p2_1_write_u32(OTA_P2_1_OFF_DETAIL, 0u);

    result = ota_staging_begin(&receiver, &io, session_sha256,
                               OTA_STAGING_BLOCK_SIZE, &progress);
    if (result != OTA_STAGING_OK)
    {
        control_finish(OTA_P2_1_STATUS_FAIL, 0x20u - (uint32_t)result);
        return true;
    }
    begin_resumed = progress.resumed;
    ota_p2_1_write_u32(OTA_P2_1_OFF_RESUMED, progress.resumed);
    ota_p2_1_write_u32(OTA_P2_1_OFF_DURABLE_BEFORE,
                       progress.durable_off);

    for (offset = 0u; offset < OTA_STAGING_BLOCK_SIZE;
         offset += OTA_STAGING_SEGMENT_SIZE)
    {
        for (index = 0u; index < sizeof(segment); ++index)
        {
            segment[index] = (uint8_t)((offset + index) * 17u + 3u);
        }
        result = ota_staging_receive(&receiver, offset, segment,
                                     sizeof(segment), &progress);
        if (result < 0 || result == OTA_STAGING_INTERRUPTED)
        {
            control_finish(OTA_P2_1_STATUS_FAIL,
                           0x40u - (uint32_t)result);
            return true;
        }
    }
    if (result != OTA_STAGING_PACKAGE_COMPLETE ||
        ota_staging_finalize(&receiver, evidence_pattern_crc(), 20800u) !=
            OTA_STAGING_OK ||
        staging_read(&g_staging_port,
                     OTA_EXT_STAGING + OTA_STAGING_BITMAP_OFFSET,
                     &persistent, 1u) != 0)
    {
        control_finish(OTA_P2_1_STATUS_FAIL, 0x50u);
        return true;
    }

    ota_p2_1_write_u32(OTA_P2_1_OFF_DURABLE_AFTER,
                       progress.durable_off);
    ota_p2_1_write_u32(OTA_P2_1_OFF_SEGMENT_BITMAP,
                       progress.segment_bitmap);
    ota_p2_1_write_u32(OTA_P2_1_OFF_PERSISTENT_BITMAP, persistent);
    if (prior_status != OTA_P2_1_STATUS_CHECKPOINT ||
        begin_resumed != 1u || progress.durable_off !=
            OTA_STAGING_BLOCK_SIZE || persistent != 0xFEu ||
        g_staging_port.header_erases != 1u ||
        g_staging_port.data_erases != 2u ||
        g_staging_port.data_programs != 2u)
    {
        control_finish(OTA_P2_1_STATUS_FAIL, 0x60u);
        return true;
    }
    SEGGER_RTT_printf(0,
        "P2_1: PASS resumed=%u durable=%lu bitmap=0x%02X "
        "header_erase=%lu data_erase=%lu data_program=%lu\r\n",
        (unsigned)begin_resumed, (unsigned long)progress.durable_off,
        (unsigned)persistent, (unsigned long)g_staging_port.header_erases,
        (unsigned long)g_staging_port.data_erases,
        (unsigned long)g_staging_port.data_programs);
    control_finish(OTA_P2_1_STATUS_PASS, 0u);
    HAL_OTA_StagingEvidenceDone();
    return true;
}
#endif

void HAL::OTA_StagingGetIo(ota_staging_io_t *io)
{
    if (io == 0)
    {
        return;
    }
    io->ctx = &g_staging_port;
    io->read = staging_read;
    io->erase_4k = staging_erase;
    io->program = staging_program;
    io->checkpoint = 0;
}
