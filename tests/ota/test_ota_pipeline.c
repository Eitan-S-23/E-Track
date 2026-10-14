#define main original_staging_tests
#include "test_ota_staging.c"
#undef main
#include "OTA/ota_pipeline.h"

static ota_pipeline_t pipe;
static uint8_t bytes[3u * OTA_STAGING_BLOCK_SIZE + 17u];
static struct
{
    uint32_t operation, address, len, calls, fail_at, fault, busy, cancels;
    const uint8_t *src;
    uint8_t original[256];
    int pending, hold;
} async_io;

static int async_start(void *ctx, uint32_t op, uint32_t address,
                       const uint8_t *src, uint32_t len)
{
    (void)ctx;
    if (async_io.pending) return -1;
    async_io.operation = op;
    async_io.address = address;
    async_io.len = len;
    async_io.src = src;
    async_io.pending = 1;
    async_io.busy = 2u;
    ++async_io.calls;
    if (src != 0)
    {
        if (len > sizeof(async_io.original)) return -1;
        memcpy(async_io.original, src, len);
    }
    return OTA_PIPELINE_BUSY;
}

static int async_poll(void *ctx)
{
    uint32_t fault;
    (void)ctx;
    if (!async_io.pending) return -1;
    if (async_io.src && memcmp(async_io.src, async_io.original, async_io.len) != 0)
    {
        check("pending DMA source remains immutable", 0);
        return -1;
    }
    if (async_io.hold || async_io.busy-- != 0u) return OTA_PIPELINE_BUSY;
    async_io.pending = 0;
    fault = async_io.fail_at == async_io.calls ? async_io.fault : 0u;
    if (fault == 1u) return -1;
    if (fault == 2u)
    {
        if (async_io.operation == OTA_PIPELINE_ERASE)
            memset(fixture.flash + flash_offset(async_io.address), 0xFF, async_io.len / 2u);
        else
            (void)fixture_program(&fixture, async_io.address, async_io.src, async_io.len / 2u);
        return -1;
    }
    if (async_io.operation == OTA_PIPELINE_ERASE)
        (void)fixture_erase(&fixture, async_io.address);
    else
        (void)fixture_program(&fixture, async_io.address, async_io.src, async_io.len);
    return fault == 3u ? -1 : OTA_PIPELINE_OK;
}

static void async_cancel(void *ctx)
{
    (void)ctx;
    ++async_io.cancels;
}

static int begin_pipe(uint32_t epoch)
{
    ota_staging_io_t store = fixture_io();
    ota_pipeline_io_t io = {0, async_start, async_poll, async_cancel};
    return ota_pipeline_begin(&pipe, &store, &io, epoch, golden_sha256, sizeof(bytes));
}

static void reset_pipe(void)
{
    uint32_t i;
    reset_fixture();
    memset(&pipe, 0, sizeof(pipe));
    memset(&async_io, 0, sizeof(async_io));
    for (i = 0; i < sizeof(bytes); ++i) bytes[i] = (uint8_t)(i * 13u + i / 17u);
    check("pipeline begin uses the existing staging journal", begin_pipe(123u) == OTA_PIPELINE_OK);
}

static int feed_to(uint32_t epoch, uint32_t end)
{
    while (pipe.accepted_off < end)
    {
        uint32_t off = pipe.accepted_off;
        uint32_t len = end - off;
        int result;
        if (len > 128u) len = 128u;
        result = ota_pipeline_receive(&pipe, epoch, off, bytes + off, len);
        if (result != OTA_PIPELINE_OK) return result;
    }
    return OTA_PIPELINE_OK;
}

static int finish(uint32_t epoch)
{
    uint32_t now;
    for (now = 0; now < 5000u; ++now)
    {
        ota_pipeline_ack_t ack;
        int result = ota_pipeline_snapshot(&pipe, &ack);
        if (result < 0) return result;
        if (feed_to(epoch, ack.credit_end) != OTA_PIPELINE_OK) return -1;
        result = ota_pipeline_poll(&pipe, now);
        if (result == OTA_PIPELINE_COMPLETE || result < 0) return result;
    }
    return -1;
}

static void ownership_and_credit(void)
{
    ota_pipeline_ack_t ack;
    uint32_t now, before;
    reset_pipe();
    check("old epoch is rejected without accepting bytes",
          ota_pipeline_receive(&pipe, 122u, 0u, bytes, 128u) == OTA_PIPELINE_ERR_EPOCH && pipe.accepted_off == 0u);
    check("gaps and malformed segments cannot consume credit",
          ota_pipeline_receive(&pipe, 123u, 128u, bytes + 128u, 128u) == OTA_PIPELINE_ERR_CREDIT &&
          ota_pipeline_receive(&pipe, 123u, 0u, bytes, 127u) == OTA_PIPELINE_ERR_PARAM && pipe.accepted_off == 0u);
    check("first block accepts", feed_to(123u, 4096u) == OTA_PIPELINE_OK);
    check("erase starts asynchronously", ota_pipeline_poll(&pipe, 0u) == OTA_PIPELINE_BUSY && pipe.pending);
    async_io.hold = 1;
    check("second block receives while the first erase is busy", feed_to(123u, 8192u) == OTA_PIPELINE_OK);
    check("snapshot separates accepted, durable and granted capacity",
          ota_pipeline_snapshot(&pipe, &ack) == OTA_PIPELINE_OK && ack.durable_off == 0u &&
          ack.accepted_off == 8192u && ack.credit_end == 8192u &&
          fixture.flash[OTA_STAGING_BITMAP_OFFSET] == 0xFFu);
    check("third block cannot overwrite either owned buffer",
          ota_pipeline_receive(&pipe, 123u, 8192u, bytes + 8192u, 128u) == OTA_PIPELINE_ERR_CREDIT);
    check("identical retransmit while busy is idempotent",
          ota_pipeline_receive(&pipe, 123u, 128u, bytes + 128u, 128u) == OTA_PIPELINE_DUPLICATE);
    check("BEGIN cannot reclaim memory owned by pending Flash", begin_pipe(124u) == OTA_PIPELINE_BUSY);
    async_io.hold = 0;
    for (now = 1; now < 1000u && pipe.store.durable_off == 0u; ++now) (void)ota_pipeline_poll(&pipe, now);
    check("verified commit releases exactly one block of credit",
          ota_pipeline_snapshot(&pipe, &ack) == OTA_PIPELINE_OK && ack.durable_off == 4096u &&
          ack.accepted_off == 8192u && ack.credit_end == 12288u &&
          memcmp(pipe.second_block, bytes + 4096u, 4096u) == 0);
    before = count_operations(OP_ERASE, OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET);
    check("durable duplicates do not start Flash work",
          ota_pipeline_receive(&pipe, 123u, 0u, bytes, 128u) == OTA_PIPELINE_DUPLICATE &&
          before == count_operations(OP_ERASE, OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET));
    check("alternating buffers and a short final page finish", finish(123u) == OTA_PIPELINE_COMPLETE);
    check("later commit never clears the other filling buffer",
          memcmp(fixture.flash + OTA_STAGING_PAYLOAD_OFFSET, bytes, sizeof(bytes)) == 0);
    check("existing finalization validates the complete staged package",
          ota_staging_finalize(&pipe.store, ota_staging_crc32(bytes, sizeof(bytes)), 30281u) == OTA_STAGING_OK);
    check("one erase per block", before == 1u && count_operations(OP_ERASE,
          OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET + 4096u) == 1u);
}

static void operation_faults(void)
{
    uint32_t operation, fault;
    for (operation = 1; operation <= 53u; ++operation)
    {
        for (fault = 1; fault <= 3u; ++fault)
        {
            uint32_t block = (operation - 1u) / 17u;
            uint32_t expected_prefix = block * 4096u;
            reset_pipe();
            async_io.fail_at = operation;
            async_io.fault = fault;
            check("erase/page failure is reported", finish(123u) == OTA_PIPELINE_ERR_IO);
            check("failed, partial or uncertain Flash retains the old durable prefix",
                  pipe.store.durable_off == expected_prefix &&
                  fixture.flash[OTA_STAGING_BITMAP_OFFSET] == (uint8_t)(0xFFu << block) &&
                  memcmp(fixture.flash + OTA_STAGING_PAYLOAD_OFFSET, bytes, expected_prefix) == 0 &&
                  ota_pipeline_can_release(&pipe));
            memset(&async_io, 0, sizeof(async_io));
            check("new BEGIN loses only volatile progress", begin_pipe(124u) == OTA_PIPELINE_OK &&
                  pipe.accepted_off == expected_prefix);
            check("faulted operation resumes to byte-exact completion",
                  finish(124u) == OTA_PIPELINE_COMPLETE &&
                  memcmp(fixture.flash + OTA_STAGING_PAYLOAD_OFFSET, bytes, sizeof(bytes)) == 0);
        }
    }
}

static void reset_at_each_step(void)
{
    uint32_t cut;
    for (cut = 0; cut < 240u; ++cut)
    {
        uint32_t step, acknowledged;
        reset_pipe();
        for (step = 0; step < cut; ++step)
        {
            ota_pipeline_ack_t ack;
            if (ota_pipeline_snapshot(&pipe, &ack) != OTA_PIPELINE_OK ||
                feed_to(123u, ack.credit_end) != OTA_PIPELINE_OK)
            {
                check("reset fixture remains valid", 0);
                break;
            }
            (void)ota_pipeline_poll(&pipe, step);
        }
        acknowledged = pipe.store.durable_off;
        /* Simulated power loss clears RAM and settles/stops pending hardware;
         * only the NOR image survives. This is not a live abort shortcut. */
        memset(&pipe, 0, sizeof(pipe));
        memset(&async_io, 0, sizeof(async_io));
        check("reset reconstructs no less than acknowledged verified prefix",
              begin_pipe(124u) == OTA_PIPELINE_OK && pipe.store.durable_off >= acknowledged &&
              memcmp(fixture.flash + OTA_STAGING_PAYLOAD_OFFSET, bytes, pipe.store.durable_off) == 0);
        check("every reset point resumes to the exact whole package",
              finish(124u) == OTA_PIPELINE_COMPLETE &&
              memcmp(fixture.flash + OTA_STAGING_PAYLOAD_OFFSET, bytes, sizeof(bytes)) == 0);
    }
}

static void payload_vectors(void)
{
    static const uint8_t caps[16] = {80, 50, 66, 76, 2, 2, 128, 0, 123, 0, 0, 0, 24, 0, 0, 0};
    static const uint8_t ack[16] = {123, 0, 0, 0, 0, 0, 0, 0, 0, 32, 0, 0, 0, 32, 0, 0};
    uint8_t out[16];
    reset_pipe();
    check("CAPS wire vector matches Dart", ota_pipeline_capabilities(123u, out) == OTA_PIPELINE_OK &&
          memcmp(out, caps, sizeof(out)) == 0);
    check("zero nonce cannot negotiate", ota_pipeline_capabilities(0u, out) == OTA_PIPELINE_ERR_PARAM);
    (void)feed_to(123u, 8192u);
    check("ACK wire vector matches Dart", ota_pipeline_ack_encode(&pipe, out) == OTA_PIPELINE_OK &&
          memcmp(out, ack, sizeof(out)) == 0);
    ota_pipeline_abort(&pipe);
    check("aborted pipeline never encodes success credit", ota_pipeline_ack_encode(&pipe, out) < 0);
}

static void stop_and_commit_faults(void)
{
    uint32_t now;
    uint8_t bad[128];
    reset_pipe();
    (void)feed_to(123u, 8192u);
    (void)ota_pipeline_poll(&pipe, UINT32_MAX - 20u);
    async_io.hold = 1;
    check("timeout arithmetic wraps safely", ota_pipeline_poll(&pipe, 10u) == OTA_PIPELINE_BUSY);
    check("operation timeout requests cancellation once",
          ota_pipeline_poll(&pipe, 4000u) == OTA_PIPELINE_ERR_TIMEOUT && async_io.cancels == 1u);
    check("timeout does not free a pending DMA buffer", !ota_pipeline_can_release(&pipe) &&
          begin_pipe(124u) == OTA_PIPELINE_BUSY);
    (void)ota_pipeline_poll(&pipe, 5000u);
    check("repeated polls do not repeat cancel", async_io.cancels == 1u);
    async_io.hold = 0;
    for (now = 0; now < 10u && !ota_pipeline_can_release(&pipe); ++now) (void)ota_pipeline_poll(&pipe, 5001u + now);
    check("only quiescent completion releases ownership", ota_pipeline_can_release(&pipe) && pipe.store.durable_off == 0u);
    check("cancelled operation is recoverable", begin_pipe(124u) == OTA_PIPELINE_OK && finish(124u) == OTA_PIPELINE_COMPLETE);

    reset_pipe();
    (void)feed_to(123u, 4096u);
    (void)ota_pipeline_poll(&pipe, 0u);
    memcpy(bad, bytes, sizeof(bad)); bad[3] ^= 1u;
    check("conflicting retransmit stops without overwriting pending data",
          ota_pipeline_receive(&pipe, 123u, 0u, bad, 128u) == OTA_PIPELINE_ERR_DATA &&
          !ota_pipeline_can_release(&pipe) && memcmp(pipe.store.block, bytes, 4096u) == 0);
    for (now = 0; now < 10u && !ota_pipeline_can_release(&pipe); ++now) (void)ota_pipeline_poll(&pipe, now);

    reset_pipe();
    fixture.interrupt_checkpoint = OTA_STAGING_CP_AFTER_BLOCK_READBACK;
    check("readback interruption cannot persist credit", finish(123u) == OTA_PIPELINE_ERR_IO &&
          fixture.flash[OTA_STAGING_BITMAP_OFFSET] == 0xFFu);
    check("readback interruption reconstructs on resume", begin_pipe(124u) == OTA_PIPELINE_OK && finish(124u) == OTA_PIPELINE_COMPLETE);
    reset_pipe();
    fixture.interrupt_checkpoint = OTA_STAGING_CP_BITMAP_READBACK;
    check("uncertain journal completion is not reported as durable", finish(123u) == OTA_PIPELINE_ERR_IO && pipe.store.durable_off == 0u);
    check("resume derives durable from the real journal", begin_pipe(124u) == OTA_PIPELINE_OK && pipe.accepted_off == 4096u);
    check("already committed prefix is not erased on resume", finish(124u) == OTA_PIPELINE_COMPLETE &&
          count_operations(OP_ERASE, OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET) == 1u);
}

int main(void)
{
    (void)original_staging_tests();
    for (use_verify = 0; use_verify <= 1; ++use_verify)
    {
        ownership_and_credit();
        operation_faults();
        stop_and_commit_faults();
        reset_at_each_step();
        payload_vectors();
    }
    printf("PIPELINE_HOST_%s checks=%d failures=%d receiver_bytes=%u\n",
           failures ? "FAIL" : "PASS", checks, failures, (unsigned)sizeof(pipe));
    return failures ? 1 : 0;
}
