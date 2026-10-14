#define main staging_baseline_main
#include "test_ota_staging_hal.cpp"
#undef main
#include "../../Tools/ota/p34_staging_erase.h"

namespace
{
unsigned bulk_erases;

void bulk_model()
{
    reset_model();
    bulk_erases = 0;
    memset(flash_bytes + OTA_STAGING_PAYLOAD_OFFSET, 0,
           sizeof(flash_bytes) - OTA_STAGING_PAYLOAD_OFFSET);
}

ota_staging_result_t send_block(ota_staging_receiver_t *receiver,
                                ota_staging_progress_t *progress)
{
    const uint32_t start = receiver->durable_off;
    uint32_t len = receiver->total_len - start;
    if (len > OTA_STAGING_BLOCK_SIZE) len = OTA_STAGING_BLOCK_SIZE;
    ota_staging_result_t result = OTA_STAGING_OK;
    for (uint32_t off = 0; off < len; off += OTA_STAGING_SEGMENT_SIZE)
    {
        const uint32_t take = len - off < OTA_STAGING_SEGMENT_SIZE ?
                              len - off : OTA_STAGING_SEGMENT_SIZE;
        result = ota_staging_receive(receiver, start + off, payload + off, take, progress);
        if (result < 0 || result == OTA_STAGING_INTERRUPTED) break;
    }
    return result;
}

bool prefix_matches(uint32_t bytes)
{
    for (uint32_t off = 0; off < bytes; ++off)
        if (at(payload_address)[off] != payload[off % sizeof(payload)]) return false;
    return true;
}

void finish(ota_staging_receiver_t *receiver, ota_staging_progress_t *progress)
{
    for (unsigned limit = 0; receiver->durable_off < receiver->total_len && limit < 257; ++limit)
    {
        const uint32_t before = receiver->durable_off;
        const ota_staging_result_t result = send_block(receiver, progress);
        check("every remaining block commits only after verified data",
              (result == OTA_STAGING_BLOCK_COMMITTED || result == OTA_STAGING_PACKAGE_COMPLETE) &&
              receiver->durable_off > before && prefix_matches(receiver->durable_off));
        if (receiver->durable_off == before) break;
    }
    check("full package bytes and marker-last finalization remain correct",
          receiver->durable_off == receiver->total_len && prefix_matches(receiver->total_len) &&
          ota_staging_finalize(receiver, ota_staging_crc32(at(payload_address), receiver->total_len),
                               30260u) == OTA_STAGING_OK);
    check("erase-ahead never touches outside the staging payload or exposes unmapped reads",
          invalid_mapped_reads == 0 && flash_bytes[sizeof(flash_bytes)-1] == 0);
}

void test_plan()
{
    OtaStagingEraseAhead plan = {0, 0};
    const uint32_t aligned = OTA_EXT_STAGING + OTA_ERASE_BLOCK_SIZE;
    const uint32_t limit = OTA_EXT_STAGING + OTA_EXT_STAGING_LENGTH;
    check("header, unaligned and overflow addresses cannot be planned",
          plan.size(OTA_EXT_STAGING, true) == UINT32_MAX &&
          plan.size(aligned + 1, true) == UINT32_MAX &&
          plan.size(limit, true) == UINT32_MAX && plan.size(UINT32_MAX, true) == UINT32_MAX);
    check("first unaligned payload sector uses the portable erase",
          plan.size(payload_address, true) == OTA_STAGING_BLOCK_SIZE);
    check("aligned future payload permits a whole block erase",
          plan.size(aligned, true) == OTA_ERASE_BLOCK_SIZE);
    plan.consume(aligned, OTA_ERASE_BLOCK_SIZE);
    for (uint32_t i = 1; i < 16; ++i)
    {
        const uint32_t address = aligned + i * OTA_STAGING_BLOCK_SIZE;
        check("only the exact next erased sector may skip physical erase", plan.size(address, true) == 0);
        check("unsupported chip cannot use erased-region eligibility", plan.size(address, false) == OTA_STAGING_BLOCK_SIZE);
        plan.consume(address, 0);
        check("consumed or retransmitted sector is never skipped", plan.size(address, true) != 0);
    }
    check("out-of-order and next-block requests cannot reuse prior eligibility",
          plan.size(aligned + OTA_ERASE_BLOCK_SIZE, true) == OTA_ERASE_BLOCK_SIZE &&
          plan.size(aligned + OTA_STAGING_BLOCK_SIZE, true) == OTA_STAGING_BLOCK_SIZE);
    plan.reset();
    check("reset loses eligibility and partition tail remains sector-only",
          plan.size(aligned + OTA_STAGING_BLOCK_SIZE, true) == OTA_STAGING_BLOCK_SIZE &&
          plan.size(limit - OTA_STAGING_BLOCK_SIZE, true) == OTA_STAGING_BLOCK_SIZE);
}

void test_streams()
{
    const uint32_t lengths[] = {1, 15*4096, 16*4096, 17*4096+1, 31*4096, 33*4096, 293036, 1048576};
    for (unsigned i = 0; i < sizeof(lengths)/sizeof(lengths[0]); ++i)
    {
        bulk_model();
        ota_staging_receiver_t receiver;
        ota_staging_progress_t progress;
        ota_staging_io_t io = port_io();
        check("fresh patterned-flash stream begins", begin(&receiver, &progress, &io, lengths[i]));
        finish(&receiver, &progress);
        const unsigned blocks = (lengths[i]+4095)/4096;
        const unsigned expected_bulk = CONFIG_OTA_STAGING_BLOCK_ERASE && blocks > 15 ? (blocks-15+15)/16 : 0;
        const unsigned expected_erases = CONFIG_OTA_STAGING_BLOCK_ERASE && blocks > 15 ? 15+expected_bulk : blocks;
        check("physical erases reduce only in the enabled aligned candidate",
              bulk_erases == expected_bulk && data_erases == expected_erases);
        const unsigned saved = data_erases;
        check("old durable segment remains a duplicate without physical erase",
              ota_staging_receive(&receiver, 0, payload, lengths[i] < 128 ? lengths[i] : 128, &progress)
                  == OTA_STAGING_DUPLICATE && data_erases == saved);
    }
}

void test_resume()
{
    for (unsigned reset = 0; reset < 2; ++reset)
    for (unsigned stopped = 15; stopped <= 32; ++stopped)
    {
        bulk_model();
        ota_staging_receiver_t first, second;
        ota_staging_progress_t progress;
        ota_staging_io_t io = port_io();
        check("resume matrix begins", begin(&first, &progress, &io, 33*4096));
        for (unsigned n = 0; n < stopped; ++n) send_block(&first, &progress);
        if (reset) io = port_io();
        check("reentry reloads the exact durable offset without erasing its prefix",
              begin(&second, &progress, &io, 33*4096) && progress.resumed &&
              progress.durable_off == stopped*4096 && prefix_matches(stopped*4096));
        finish(&second, &progress);
    }
}

void test_bulk_faults()
{
    for (unsigned phase = 0; phase < 11; ++phase)
    {
        bulk_model();
        ota_staging_receiver_t first, resumed;
        ota_staging_progress_t progress;
        ota_staging_io_t io = port_io();
        io.checkpoint = checkpoint;
        check("bulk failure matrix begins", begin(&first, &progress, &io, 33*4096));
        for (unsigned n = 0; n < 15; ++n) send_block(&first, &progress);
        fail_erase = phase == 0;
        fail_program = phase == 1;
        if (phase >= 2 && phase < 8) fail_restore_at = restores + phase - 1;
        if (phase == 8) interrupt_at = OTA_STAGING_CP_BEFORE_BLOCK_ERASE;
        if (phase == 9) interrupt_at = OTA_STAGING_CP_AFTER_BLOCK_READBACK;
        if (phase == 10) interrupt_at = OTA_STAGING_CP_BITMAP_READBACK;
        const ota_staging_result_t result = send_block(&first, &progress);
        check("failed or interrupted operation does not report new RAM durable progress",
              (result < 0 || result == OTA_STAGING_INTERRUPTED) && progress.durable_off == 15*4096 &&
              prefix_matches(15*4096) && invalid_mapped_reads == 0);
        if (phase == 0)
        {
            HAL::OtaStagingError error;
            check("bulk erase first error records the actual physical extent",
                  HAL::OTA_StagingGetFirstError(&error) &&
                  error.operation == HAL::OTA_STAGING_OP_ERASE &&
                  error.phase == HAL::OTA_STAGING_ERROR_IO &&
                  error.address == payload_address + 15*4096 &&
                  error.length == (CONFIG_OTA_STAGING_BLOCK_ERASE ?
                                    OTA_ERASE_BLOCK_SIZE : OTA_STAGING_BLOCK_SIZE) &&
                  error.result == QSPI_ERR_TIMEOUT);
        }
        fail_erase = fail_program = false;
        fail_restore_at = interrupt_at = 0;
        io = port_io();
        check("recovery consults persistent bitmap rather than erased-ahead state",
              begin(&resumed, &progress, &io, 33*4096) &&
              progress.durable_off == ((phase == 6 || phase == 7 || phase == 10) ? 16u : 15u)*4096);
        finish(&resumed, &progress);
    }
}

void test_chip_fallback()
{
    bulk_model();
    verified_id = QSPI_JEDEC_EN25QH128A;
    ota_staging_receiver_t receiver;
    ota_staging_progress_t progress;
    ota_staging_io_t io = port_io();
    check("non-selected chip begins with ordinary semantics", begin(&receiver, &progress, &io, 33*4096));
    finish(&receiver, &progress);
    check("non-selected chip never uses bulk erase", bulk_erases == 0 && data_erases == 33);
}

void test_cached_sector_invalidation()
{
    for (unsigned mode = 0; mode < 2; ++mode)
    {
        bulk_model();
        ota_staging_receiver_t receiver;
        ota_staging_progress_t progress;
        ota_staging_io_t io = port_io();
        check("cached-sector invalidation case begins", begin(&receiver, &progress, &io, 33*4096));
        for (unsigned n = 0; n < 16; ++n) send_block(&receiver, &progress);
        const unsigned before = data_erases;
        if (mode == 0)
        {
            fail_restore_at = restores + 1;
            check("failed cached-sector restore cannot confirm or damage the prefix",
                  send_block(&receiver, &progress) == OTA_STAGING_ERR_IO &&
                  progress.durable_off == 16*4096 && prefix_matches(16*4096));
            HAL::OtaStagingError error;
            check("cached-sector restore records the failed logical sector",
                  HAL::OTA_StagingGetFirstError(&error) &&
                  error.operation == HAL::OTA_STAGING_OP_ERASE &&
                  error.phase == HAL::OTA_STAGING_ERROR_RESTORE &&
                  error.address == payload_address + 16*4096 &&
                  error.length == OTA_STAGING_BLOCK_SIZE &&
                  error.result == QSPI_ERR_TIMEOUT);
            fail_restore_at = 0;
        }
        else
        {
            uint8_t dirty = 0;
            check("direct write to a previously erased future sector invalidates eligibility",
                  io.program(io.ctx, payload_address + 16*4096, &dirty, 1) == 0);
        }
        check("the next attempt physically erases and verifies the uncommitted sector",
              send_block(&receiver, &progress) == OTA_STAGING_BLOCK_COMMITTED &&
              prefix_matches(17*4096) && data_erases >= before + 1);
        finish(&receiver, &progress);
    }
}
}

extern "C" qspi_status_t qspi_erase_64k(uint32_t address)
{
    if (xip_ready || address < payload_address || !range_ok(address, OTA_ERASE_BLOCK_SIZE) ||
        address % OTA_ERASE_BLOCK_SIZE) return QSPI_ERR_PARAM;
    if (fail_erase)
    {
        memset(at(address), 0xFF, OTA_ERASE_BLOCK_SIZE/2);
        return QSPI_ERR_TIMEOUT;
    }
    memset(at(address), 0xFF, OTA_ERASE_BLOCK_SIZE);
    ++bulk_erases;
    ++data_erases;
    return QSPI_OK;
}

int main()
{
    staging_baseline_main();
    test_plan();
    test_streams();
    test_resume();
    test_bulk_faults();
    test_chip_fallback();
    test_cached_sector_invalidation();
    printf("STAGING_ERASE_AHEAD=%s checks=%u failures=%u\n", failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
