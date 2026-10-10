#include "HAL/HAL_OTA_Staging.h"
#include "W25Q128/qspi_cmd_en25qh128a.h"

#include <stdio.h>
#include <string.h>

#ifndef CONFIG_OTA_STAGING_QE_REUSE
#define CONFIG_OTA_STAGING_QE_REUSE 0
#endif

namespace
{
uint8_t flash_bytes[OTA_EXT_STAGING_LENGTH];
uint8_t payload[OTA_STAGING_BLOCK_SIZE];
const uint32_t payload_address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
unsigned checks;
unsigned failures;
unsigned restores;
unsigned full_restores;
unsigned checked_restores;
unsigned reused_restores;
uint32_t verified_id;
uint8_t sr1, sr2;
unsigned mapped_reads;
unsigned invalid_mapped_reads;
unsigned fail_restore_at;
unsigned data_erases;
uint32_t corrupt_at;
uint32_t corrupt_journal_address;
uint32_t interrupt_at;
bool xip_ready;
bool disabled;
bool fail_erase;
bool fail_program;

void check(const char *name, bool condition)
{
    ++checks;
    printf("  %-68s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
        ++failures;
}

bool range_ok(uint32_t address, uint32_t len)
{
    return address >= OTA_EXT_STAGING && len <= sizeof(flash_bytes) &&
           address - OTA_EXT_STAGING <= sizeof(flash_bytes) - len;
}

uint8_t *at(uint32_t address)
{
    return flash_bytes + address - OTA_EXT_STAGING;
}

void reset_model()
{
    memset(flash_bytes, 0xFF, sizeof(flash_bytes));
    for (unsigned i = 0; i < sizeof(payload); ++i)
        payload[i] = (uint8_t)(i * 37u + 11u);
    restores = mapped_reads = invalid_mapped_reads = fail_restore_at = 0;
    full_restores = checked_restores = reused_restores = 0;
    verified_id = QSPI_JEDEC_W25Q128;
    sr1 = sr2 = 0;
    data_erases = interrupt_at = 0;
    corrupt_at = UINT32_MAX;
    corrupt_journal_address = UINT32_MAX;
    xip_ready = disabled = fail_erase = fail_program = false;
}

ota_staging_io_t port_io()
{
    ota_staging_io_t io;
    memset(&io, 0xA5, sizeof(io));
    HAL::OTA_StagingGetIo(&io);
    return io;
}

bool begin(ota_staging_receiver_t *receiver, ota_staging_progress_t *progress,
           const ota_staging_io_t *io, uint32_t len)
{
    uint8_t sha[32];
    memset(sha, 0x31, sizeof(sha));
    return ota_staging_begin(receiver, io, sha, len, progress) == OTA_STAGING_OK;
}

ota_staging_result_t receive(ota_staging_receiver_t *receiver,
                             ota_staging_progress_t *progress, uint32_t len)
{
    ota_staging_result_t result = OTA_STAGING_OK;
    for (uint32_t offset = 0; offset < len; offset += OTA_STAGING_SEGMENT_SIZE)
    {
        uint32_t take = len - offset;
        if (take > OTA_STAGING_SEGMENT_SIZE)
            take = OTA_STAGING_SEGMENT_SIZE;
        result = ota_staging_receive(receiver, offset, payload + offset, take,
                                     progress);
        if (result < 0 || result == OTA_STAGING_INTERRUPTED)
            break;
    }
    return result;
}

int checkpoint(void *, uint32_t point, uint32_t, uint32_t)
{
    if (point == interrupt_at)
    {
        interrupt_at = 0;
        return -1;
    }
    return 0;
}

void test_complete(uint32_t len)
{
    ota_staging_receiver_t receiver;
    ota_staging_progress_t progress;
    reset_model();
    ota_staging_io_t io = port_io();
    check("real HAL begins a fresh staging session", begin(&receiver, &progress, &io, len));
    unsigned before = restores;
    unsigned reused_before = reused_restores;
    check("real HAL receives a complete full or short block",
          receive(&receiver, &progress, len) == OTA_STAGING_PACKAGE_COMPLETE);
    printf("    block_bytes=%lu xip_restores=%u\n", (unsigned long)len, restores - before);
    check("one block commit uses six restores, not one per 128-byte read",
          restores - before == 6);
    check("all six commit restores reuse configuration only in the candidate",
          reused_restores - reused_before == (CONFIG_OTA_STAGING_QE_REUSE ? 6u : 0u));
    check("all payload bytes and durable progress match",
          memcmp(at(payload_address), payload, len) == 0 &&
          progress.durable_off == len && progress.complete &&
          flash_bytes[OTA_STAGING_BITMAP_OFFSET] == 0xFE);
    check("tail bytes beyond the package remain untouched",
          len == sizeof(payload) || at(payload_address)[len] == 0xFF);
    check("marker-last finalization remains successful",
          ota_staging_finalize(&receiver, ota_staging_crc32(payload, len),
                               30209u) == OTA_STAGING_OK &&
          memcmp(flash_bytes + 28, "TMOC", 4) == 0);
    check("mapped reads never occur before successful XIP restoration",
          invalid_mapped_reads == 0);
}

void test_corruption()
{
    const uint32_t positions[] = {0, 127, 128, 255, 256, 1023, 1024,
                                 2047, 2048, 3967, 3968, 4095};
    for (unsigned i = 0; i < sizeof(positions) / sizeof(positions[0]); ++i)
    {
        ota_staging_receiver_t receiver;
        ota_staging_progress_t progress;
        reset_model();
        ota_staging_io_t io = port_io();
        check("corruption case begins", begin(&receiver, &progress, &io, sizeof(payload)));
        corrupt_at = positions[i];
        printf("    corrupt_byte=%lu\n", (unsigned long)corrupt_at);
        check("corruption anywhere in the block is rejected",
              receive(&receiver, &progress, sizeof(payload)) == OTA_STAGING_ERR_VERIFY);
        check("failed readback cannot publish durable progress or clear its bit",
              progress.durable_off == 0 && progress.segment_bitmap == 0 &&
              flash_bytes[OTA_STAGING_BITMAP_OFFSET] == 0xFF);
        HAL::OtaStagingError error;
        check("first mismatch retains its actual address and compared bytes",
              HAL::OTA_StagingGetFirstError(&error) &&
              error.operation == HAL::OTA_STAGING_OP_VERIFY &&
              error.phase == HAL::OTA_STAGING_ERROR_VERIFY &&
              error.result == OTA_STAGING_ERR_VERIFY &&
              error.mismatch_address == payload_address + positions[i] &&
              error.expected_byte == payload[positions[i]] &&
              error.observed_byte == (uint8_t)(payload[positions[i]] ^ 1u));
        check("retransmission erases the failed block and verifies it again",
              receive(&receiver, &progress, sizeof(payload)) == OTA_STAGING_PACKAGE_COMPLETE &&
              data_erases == 2 && invalid_mapped_reads == 0);
    }
}

void test_restore_failures()
{
    for (unsigned phase = 1; phase <= 6; ++phase)
    {
        ota_staging_receiver_t receiver;
        ota_staging_progress_t progress;
        reset_model();
        ota_staging_io_t io = port_io();
        check("restore-failure case begins", begin(&receiver, &progress, &io, sizeof(payload)));
        fail_restore_at = restores + phase;
        check("each failed XIP restore propagates an I/O error",
              receive(&receiver, &progress, sizeof(payload)) == OTA_STAGING_ERR_IO);
        check("failed XIP restoration never leads to a mapped read or success",
              invalid_mapped_reads == 0 && progress.durable_off == 0 && !progress.complete);
        HAL::OtaStagingError error;
        check("restore error is distinct from a byte comparison failure",
              HAL::OTA_StagingGetFirstError(&error) &&
              error.phase == HAL::OTA_STAGING_ERROR_RESTORE &&
              error.result == QSPI_ERR_TIMEOUT && error.mismatch_address == UINT32_MAX);
    }
}

void test_write_failures()
{
    for (unsigned phase = 0; phase < 2; ++phase)
    {
        ota_staging_receiver_t receiver;
        ota_staging_progress_t progress;
        reset_model();
        ota_staging_io_t io = port_io();
        check("write-failure case begins", begin(&receiver, &progress, &io, sizeof(payload)));
        fail_erase = phase == 0;
        fail_program = phase == 1;
        check("erase/program failures remain terminal for the block",
              receive(&receiver, &progress, sizeof(payload)) == OTA_STAGING_ERR_IO);
        check("write failure still restores XIP without confirming data",
              xip_ready && invalid_mapped_reads == 0 && progress.durable_off == 0 &&
              flash_bytes[OTA_STAGING_BITMAP_OFFSET] == 0xFF);
    }
}

void test_interruption()
{
    ota_staging_receiver_t first, restarted;
    ota_staging_progress_t progress;
    reset_model();
    ota_staging_io_t io = port_io();
    io.checkpoint = checkpoint;
    check("interrupted session begins", begin(&first, &progress, &io, sizeof(payload)));
    interrupt_at = OTA_STAGING_CP_AFTER_BLOCK_READBACK;
    check("reset point remains after full readback and before bitmap commit",
          receive(&first, &progress, sizeof(payload)) == OTA_STAGING_INTERRUPTED &&
          flash_bytes[OTA_STAGING_BITMAP_OFFSET] == 0xFF);
    xip_ready = false;
    check("a fresh receiver reloads persistent state after mode loss",
          begin(&restarted, &progress, &io, sizeof(payload)) &&
          progress.resumed && progress.durable_off == 0);
    check("recovery retransmits the whole uncommitted block",
          receive(&restarted, &progress, sizeof(payload)) == OTA_STAGING_PACKAGE_COMPLETE &&
          data_erases == 2 && invalid_mapped_reads == 0);
}

void test_metadata_corruption()
{
    const uint32_t addresses[] = {
        OTA_EXT_STAGING + OTA_STAGING_ETRJ_OFFSET,
        OTA_EXT_STAGING + OTA_STAGING_BITMAP_OFFSET,
        OTA_EXT_STAGING,
        OTA_EXT_STAGING + 28u
    };
    for (unsigned i = 0; i < sizeof(addresses) / sizeof(addresses[0]); ++i)
    {
        ota_staging_receiver_t receiver;
        ota_staging_progress_t progress;
        uint8_t sha[32];
        memset(sha, 0x31, sizeof(sha));
        reset_model();
        ota_staging_io_t io = port_io();
        ota_staging_result_t result;
        if (i == 0)
        {
            corrupt_journal_address = addresses[i];
            result = ota_staging_begin(&receiver, &io, sha, sizeof(payload), &progress);
        }
        else
        {
            check("metadata-corruption session begins",
                  begin(&receiver, &progress, &io, sizeof(payload)));
            if (i == 1)
                corrupt_journal_address = addresses[i];
            result = receive(&receiver, &progress, sizeof(payload));
            if (i > 1)
            {
                check("metadata test first completes and verifies the payload",
                      result == OTA_STAGING_PACKAGE_COMPLETE);
                corrupt_journal_address = addresses[i];
                result = ota_staging_finalize(&receiver,
                                              ota_staging_crc32(payload, sizeof(payload)),
                                              30209u);
            }
        }
        check("ETRJ/bitmap/ETSL/marker corruption is rejected by readback",
              result == OTA_STAGING_ERR_VERIFY && invalid_mapped_reads == 0);
        check("metadata corruption never leaves a valid completion marker",
              memcmp(flash_bytes + 28, "TMOC", 4) != 0);
    }
}

void test_hal_fallback()
{
    ota_staging_receiver_t receiver;
    ota_staging_progress_t progress;
    reset_model();
    ota_staging_io_t io = port_io();
    io.verify = 0;
    check("real HAL can still use the portable readback fallback",
          begin(&receiver, &progress, &io, sizeof(payload)));
    unsigned before = restores;
    check("fallback preserves the original full read/compare behavior",
          receive(&receiver, &progress, sizeof(payload)) == OTA_STAGING_PACKAGE_COMPLETE &&
          restores - before == 37 && invalid_mapped_reads == 0 &&
          memcmp(at(payload_address), payload, sizeof(payload)) == 0);
}

void test_guards()
{
    reset_model();
    ota_staging_io_t io = port_io();
    uint8_t byte = 0;
    check("invalid reads fail before hardware access",
          io.read(io.ctx, OTA_EXT_STAGING - 1, &byte, 1) != 0 &&
          io.read(io.ctx, UINT32_MAX, &byte, 2) != 0 &&
          io.read(io.ctx, OTA_EXT_STAGING, 0, 1) != 0 && restores == 0);
    disabled = true;
    check("OTA-disabled guard still blocks all storage operations",
          io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) != 0 &&
          io.erase_4k(io.ctx, OTA_EXT_STAGING) != 0 &&
          io.program(io.ctx, OTA_EXT_STAGING, &byte, 1) != 0 && restores == 0);
    disabled = false;
    fail_restore_at = 1;
    check("an initial read restore failure does not touch mapped memory",
          io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) != 0 && mapped_reads == 0);
    fail_restore_at = 0;
    check("subsequent read can recover without cached success",
          io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 && byte == 0xFF);
    xip_ready = false;
    check("mode loss between calls is repaired rather than trusted",
          io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 &&
          restores == 3 && invalid_mapped_reads == 0);
    unsigned before = restores;
    check("whole-region verification rejects invalid input before restoring",
          io.verify(io.ctx, OTA_EXT_STAGING - 1, &byte, 1) == OTA_STAGING_ERR_IO &&
          io.verify(io.ctx, UINT32_MAX, &byte, 2) == OTA_STAGING_ERR_IO &&
          io.verify(io.ctx, OTA_EXT_STAGING, 0, 1) == OTA_STAGING_ERR_IO &&
          io.verify(io.ctx, OTA_EXT_STAGING, &byte, 0) == OTA_STAGING_ERR_IO &&
          io.verify(io.ctx, OTA_EXT_STAGING, &byte, OTA_STAGING_BLOCK_SIZE + 1) == OTA_STAGING_ERR_IO &&
          restores == before);
    disabled = true;
    check("whole-region verification honors OTA-disabled state",
          io.verify(io.ctx, OTA_EXT_STAGING, &byte, 1) == OTA_STAGING_ERR_IO &&
          restores == before);
    disabled = false;
    xip_ready = false;
    check("whole-region verification restores lost mode and checks bytes",
          io.verify(io.ctx, OTA_EXT_STAGING, &byte, 1) == OTA_STAGING_OK &&
          restores == before + 1 && invalid_mapped_reads == 0);
    byte ^= 1;
    check("whole-region comparison reports mismatch instead of success",
          io.verify(io.ctx, OTA_EXT_STAGING, &byte, 1) == OTA_STAGING_ERR_VERIFY);
}

void test_restore_policy()
{
    reset_model();
    ota_staging_io_t io = port_io();
    uint8_t byte = 0;
    check("first restore always performs full initialization",
          io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 &&
          full_restores == 1 && checked_restores == 0);
    xip_ready = false;
    check("second restore uses checked configuration only when enabled",
          io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 &&
          checked_restores == (CONFIG_OTA_STAGING_QE_REUSE ? 1u : 0u) &&
          full_restores == (CONFIG_OTA_STAGING_QE_REUSE ? 1u : 2u) && xip_ready);
    const uint8_t states[][2] = {{0, 0}, {4, 2}, {0, 6}, {0x80, 0x82}};
    for (unsigned i = 0; i < sizeof(states) / sizeof(states[0]); ++i)
    {
        sr1 = states[i][0]; sr2 = states[i][1];
        unsigned before = full_restores;
        check("changed status bytes force full configuration, not cached QE",
              io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 &&
              full_restores == before + 1 && sr1 == 0 && sr2 == 2);
    }
    const uint32_t ids[] = {0, QSPI_JEDEC_EN25QH128A, QSPI_JEDEC_EN25QH64A};
    for (unsigned i = 0; i < sizeof(ids) / sizeof(ids[0]); ++i)
    {
        verified_id = ids[i];
        unsigned before = full_restores;
        check("non-W25Q verified IDs keep the full initializer",
              io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 &&
              full_restores == before + 1);
    }
    verified_id = QSPI_JEDEC_W25Q128;
    unsigned before = full_restores;
    io = port_io();
    check("rebinding resets restore eligibility without touching flash",
          full_restores == before &&
          io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 &&
          full_restores == before + 1);

    for (unsigned operation = 0; operation < 4; ++operation)
    {
        fail_restore_at = restores + 1;
        unsigned old_reads = mapped_reads;
        int result;
        if (operation == 0)
            result = io.read(io.ctx, OTA_EXT_STAGING, &byte, 1);
        else if (operation == 1)
            result = io.verify(io.ctx, OTA_EXT_STAGING, &byte, 1);
        else if (operation == 2)
            result = io.erase_4k(io.ctx, OTA_EXT_STAGING);
        else
            result = io.program(io.ctx, OTA_EXT_STAGING, &byte, 1);
        check("restore failure is not silently retried or mapped",
              result < 0 && restores == fail_restore_at &&
              mapped_reads == old_reads && !xip_ready);
        before = full_restores;
        fail_restore_at = 0;
        check("next recovery uses full initialization after any restore failure",
              io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 &&
              full_restores == before + 1);
    }
    check("restore policy never exposes invalid mapped memory", invalid_mapped_reads == 0);
}

void test_failed_operation_invalidation()
{
    for (unsigned operation = 0; operation < 2; ++operation)
    for (unsigned restore_fails = 0; restore_fails < 2; ++restore_fails)
    {
        reset_model();
        ota_staging_io_t io = port_io();
        uint8_t byte = 0;
        check("operation failure case establishes restore eligibility",
              io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0);
        unsigned before = full_restores;
        fail_erase = operation == 0;
        fail_program = operation == 1;
        fail_restore_at = restore_fails ? restores + 1 : 0;
        int result = operation == 0 ? io.erase_4k(io.ctx, OTA_EXT_STAGING)
                                   : io.program(io.ctx, OTA_EXT_STAGING, &byte, 1);
        check("failed operation uses full restore and remains failed",
              result != 0 && full_restores == before + 1 &&
              xip_ready == (restore_fails == 0));
        fail_erase = fail_program = false;
        fail_restore_at = 0;
        check("operation error invalidates even a successful cleanup restore",
              io.read(io.ctx, OTA_EXT_STAGING, &byte, 1) == 0 &&
              full_restores == before + 2 && invalid_mapped_reads == 0);
    }
}

void test_first_error_ownership()
{
    reset_model();
    ota_staging_io_t io = port_io();
    HAL::OtaStagingError first, second;
    uint8_t byte = 0;
    check("fresh binding has no first error", !HAL::OTA_StagingGetFirstError(&first));
    fail_program = true;
    fail_restore_at = restores + 1u;
    check("a failed program and failed cleanup still return failure",
          io.program(io.ctx, payload_address, &byte, 1u) != 0);
    check("original IO error wins over a subsequent restore error",
          HAL::OTA_StagingGetFirstError(&first) &&
          first.operation == HAL::OTA_STAGING_OP_PROGRAM &&
          first.phase == HAL::OTA_STAGING_ERROR_IO && first.result == QSPI_ERR_TIMEOUT &&
          first.address == payload_address && first.length == 1u);
    fail_program = false;
    fail_restore_at = restores + 1u;
    check("later errors do not replace the first failure",
          io.read(io.ctx, payload_address, &byte, 1u) != 0 &&
          HAL::OTA_StagingGetFirstError(&second) &&
          second.phase == first.phase && second.operation == first.operation &&
          second.address == first.address);
    first.phase = HAL::OTA_STAGING_ERROR_NONE;
    check("returned diagnostics are a copy, not writable live state",
          HAL::OTA_StagingGetFirstError(&second) && second.phase == HAL::OTA_STAGING_ERROR_IO);
    unsigned restores_before = restores;
    (void)port_io();
    check("next binding resets the record without a Flash operation",
          !HAL::OTA_StagingGetFirstError(&second) && !HAL::OTA_StagingGetFirstError(0) &&
          restores == restores_before);
}
}

uintptr_t staging_test_mapped_base(void)
{
    ++mapped_reads;
    if (!xip_ready)
        ++invalid_mapped_reads;
    return (uintptr_t)flash_bytes - OTA_EXT_STAGING;
}

void qspi_xip_enable(void *, int enabled)
{
    xip_ready = enabled != FALSE;
}

bool HAL::Qspi_IsOtaDisabled()
{
    return disabled;
}

uint32_t HAL::Qspi_GetJedecId()
{
    return verified_id;
}

extern "C" qspi_status_t en25qh128a_qspi_xip_init(void)
{
    ++full_restores;
    ++restores;
    xip_ready = restores != fail_restore_at;
    if (xip_ready) { sr1 = 0; sr2 = 2; }
    return xip_ready ? QSPI_OK : QSPI_ERR_TIMEOUT;
}

extern "C" qspi_status_t qspi_xip_restore_checked(uint32_t id, bool *reused_qe)
{
    ++checked_restores;
    if (reused_qe) *reused_qe = false;
    if (id != QSPI_JEDEC_W25Q128 || sr1 != 0 || sr2 != 2)
        return en25qh128a_qspi_xip_init();
    ++restores;
    xip_ready = restores != fail_restore_at;
    if (!xip_ready) return QSPI_ERR_TIMEOUT;
    ++reused_restores;
    if (reused_qe) *reused_qe = true;
    return QSPI_OK;
}

extern "C" qspi_status_t qspi_erase(uint32_t address)
{
    if (xip_ready || !range_ok(address, OTA_STAGING_BLOCK_SIZE) ||
        address % OTA_STAGING_BLOCK_SIZE)
        return QSPI_ERR_PARAM;
    if (fail_erase)
        return QSPI_ERR_TIMEOUT;
    memset(at(address), 0xFF, OTA_STAGING_BLOCK_SIZE);
    if (address >= payload_address)
        ++data_erases;
    return QSPI_OK;
}

extern "C" qspi_status_t qspi_data_write(uint32_t address, uint32_t len, uint8_t *src)
{
    if (xip_ready || !range_ok(address, len) || !src || !len)
        return QSPI_ERR_PARAM;
    if (fail_program)
        return QSPI_ERR_TIMEOUT;
    for (uint32_t i = 0; i < len; ++i)
    {
        if ((at(address)[i] & src[i]) != src[i])
            return QSPI_ERR_VERIFY;
        at(address)[i] &= src[i];
    }
    if (address == payload_address && corrupt_at < len)
    {
        at(address)[corrupt_at] ^= 1;
        corrupt_at = UINT32_MAX;
    }
    if (address == corrupt_journal_address)
    {
        at(address)[0] ^= 1;
        corrupt_journal_address = UINT32_MAX;
    }
    return QSPI_OK;
}

int main()
{
    puts("=== Real HAL staging readback tests (modeled NOR/XIP, no hardware) ===");
    test_complete(OTA_STAGING_BLOCK_SIZE);
    test_complete(129);
    test_complete(1);
    test_complete(OTA_STAGING_BLOCK_SIZE - 1);
    test_corruption();
    test_restore_failures();
    test_write_failures();
    test_interruption();
    test_metadata_corruption();
    test_hal_fallback();
    test_guards();
    test_restore_policy();
    test_failed_operation_invalidation();
    test_first_error_ownership();
    printf("OTA_STAGING_HAL=%s checks=%u failures=%u\n",
           failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
