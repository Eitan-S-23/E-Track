#if !defined(P34_STAGING_EARLY_ERASE) || !P34_STAGING_EARLY_ERASE
#error This test requires the development-only early-erase candidate
#endif

#define main original_staging_tests
#include "test_ota_staging.c"
#undef main

static uint8_t payload[2u * OTA_STAGING_BLOCK_SIZE + 37u];
static int erase_failure;

static int fault_erase(void *ctx, uint32_t address)
{
    if (address >= OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET && erase_failure)
    {
        int mode = erase_failure;
        erase_failure = 0;
        if (mode == 2)
        {
            memset(fixture.flash + flash_offset(address), 0xFF,
                   OTA_STAGING_BLOCK_SIZE / 2u);
        }
        if (mode == 3)
        {
            (void)fixture_erase(ctx, address);
        }
        return -1;
    }
    return fixture_erase(ctx, address);
}

static void early_erase_cases(void)
{
    ota_staging_receiver_t receiver;
    ota_staging_progress_t progress;
    ota_staging_io_t io;
    const uint32_t address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    uint32_t i;

    for (i = 0; i < sizeof(payload); ++i)
    {
        payload[i] = (uint8_t)(i * 17u + i / 128u);
    }
    reset_fixture();
    io = fixture_io();
    check("early erase begin", ota_staging_begin(&receiver, &io, golden_sha256,
          sizeof(payload), &progress) == OTA_STAGING_OK);
    check("BEGIN does not erase payload", count_operations(OP_ERASE, address) == 0);
    check("invalid segment rejected before erase",
          ota_staging_receive(&receiver, 1, payload, 128, &progress) == OTA_STAGING_ERR_RANGE);
    check("next block rejected before erase",
          ota_staging_receive(&receiver, 4096, payload, 128, &progress) == OTA_STAGING_ERR_RANGE);
    check("bad length rejected before erase",
          ota_staging_receive(&receiver, 0, payload, 127, &progress) == OTA_STAGING_ERR_RANGE);
    check("invalid input leaves payload untouched", count_operations(OP_ERASE, address) == 0);
    check("first legal segment erases once",
          ota_staging_receive(&receiver, 0, payload, 128, &progress) == OTA_STAGING_OK &&
          count_operations(OP_ERASE, address) == 1 && receiver.block_erased == 1);
    check("early erase neither programs nor advances durable",
          count_operations(OP_PROGRAM, address) == 0 && progress.durable_off == 0 &&
          progress.segment_bitmap == 1 && fixture.flash[OTA_STAGING_BITMAP_OFFSET] == 0xFF);
    check("duplicate does not erase again",
          ota_staging_receive(&receiver, 0, payload, 128, &progress) == OTA_STAGING_DUPLICATE &&
          count_operations(OP_ERASE, address) == 1);
    {
        uint8_t conflicting[128];
        memcpy(conflicting, payload, sizeof(conflicting));
        conflicting[0] ^= 1;
        check("conflicting duplicate cannot trigger another erase",
              ota_staging_receive(&receiver, 0, conflicting, 128, &progress) == OTA_STAGING_ERR_DATA &&
              count_operations(OP_ERASE, address) == 1);
    }
    check("full package and short tail commit",
          send_all_segments(&receiver, payload, sizeof(payload), &progress) == OTA_STAGING_PACKAGE_COMPLETE);
    check("each block erases once, not again at completion",
          count_operations(OP_ERASE, address) == 1 &&
          count_operations(OP_ERASE, address + 4096) == 1 &&
          count_operations(OP_ERASE, address + 8192) == 1);
    check("exact payload and cleared volatile erase state",
          memcmp(fixture.flash + flash_offset(address), payload, sizeof(payload)) == 0 &&
          receiver.block_erased == 0 && progress.durable_off == sizeof(payload));
    check("already durable duplicate is read-only",
          ota_staging_receive(&receiver, 0, payload, 128, &progress) == OTA_STAGING_DUPLICATE &&
          count_operations(OP_ERASE, address) == 1);
    check("full finalization preserved",
          ota_staging_finalize(&receiver, ota_staging_crc32(payload, sizeof(payload)), 30279) == OTA_STAGING_OK);

    for (i = 1; i <= 3; ++i)
    {
        reset_fixture();
        memset(fixture.flash + flash_offset(address), 0, OTA_STAGING_BLOCK_SIZE);
        io = fixture_io();
        io.erase_4k = fault_erase;
        check("erase-fault begin", ota_staging_begin(&receiver, &io, golden_sha256,
              4096, &progress) == OTA_STAGING_OK);
        erase_failure = (int)i;
        check("failed, partial or uncertain erase rejects first segment",
              ota_staging_receive(&receiver, 0, payload, 128, &progress) == OTA_STAGING_ERR_IO);
        check("erase failure retains no accepted or persistent progress",
              receiver.block_erased == 0 && progress.segment_bitmap == 0 &&
              progress.durable_off == 0 && fixture.flash[OTA_STAGING_BITMAP_OFFSET] == 0xFF &&
              count_operations(OP_PROGRAM, address) == 0);
        check("later valid receive re-erases then reconstructs exactly",
              send_all_segments(&receiver, payload, 4096, &progress) == OTA_STAGING_PACKAGE_COMPLETE &&
              memcmp(fixture.flash + flash_offset(address), payload, 4096) == 0);
    }

    for (i = 1; i < 32; ++i)
    {
        uint32_t segment;
        reset_fixture();
        io = fixture_io();
        check("interruption begin", ota_staging_begin(&receiver, &io, golden_sha256,
              4096, &progress) == OTA_STAGING_OK);
        for (segment = 0; segment < i; ++segment)
        {
            if (ota_staging_receive(&receiver, segment * 128u,
                    payload + segment * 128u, 128, &progress) != OTA_STAGING_OK)
            {
                check("prefix reception", 0);
            }
        }
        memset(&receiver, 0, sizeof(receiver));
        check("re-BEGIN after partial block forgets volatile erase state",
              ota_staging_begin(&receiver, &io, golden_sha256, 4096, &progress) == OTA_STAGING_OK &&
              receiver.block_erased == 0 && progress.segment_bitmap == 0 && progress.durable_off == 0);
        check("resume re-erases uncommitted block and finishes",
              send_all_segments(&receiver, payload, 4096, &progress) == OTA_STAGING_PACKAGE_COMPLETE &&
              count_operations(OP_ERASE, address) == 2 &&
              memcmp(fixture.flash + flash_offset(address), payload, 4096) == 0);
    }

    reset_fixture();
    io = fixture_io();
    check("checkpoint-fault begin", ota_staging_begin(&receiver, &io, golden_sha256,
          4096, &progress) == OTA_STAGING_OK);
    fixture.interrupt_checkpoint = OTA_STAGING_CP_BEFORE_BLOCK_ERASE;
    check("before-erase interruption occurs on first segment without erase",
          ota_staging_receive(&receiver, 0, payload, 128, &progress) == OTA_STAGING_INTERRUPTED &&
          count_operations(OP_ERASE, address) == 0 && receiver.block_erased == 0 &&
          progress.durable_off == 0 && progress.segment_bitmap == 0);
    check("before-erase interruption remains resumable",
          send_all_segments(&receiver, payload, 4096, &progress) == OTA_STAGING_PACKAGE_COMPLETE);
}

int main(void)
{
    (void)original_staging_tests();
    for (use_verify = 0; use_verify <= 1; ++use_verify)
    {
        early_erase_cases();
    }
    printf("EARLY_ERASE_HOST_%s checks=%d failures=%d\n",
           failures ? "FAIL" : "PASS", checks, failures);
    return failures ? 1 : 0;
}
