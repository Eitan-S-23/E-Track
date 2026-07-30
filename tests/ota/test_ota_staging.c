#include "OTA/ota_staging.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum
{
    OP_READ = 1,
    OP_ERASE = 2,
    OP_PROGRAM = 3,
    MAX_OPS = 4096
};

typedef struct operation_t
{
    int type;
    uint32_t address;
    uint32_t len;
} operation_t;

typedef struct fixture_t
{
    uint8_t flash[OTA_EXT_STAGING_LENGTH];
    operation_t operations[MAX_OPS];
    uint32_t operation_count;
    uint32_t interrupt_checkpoint;
    uint32_t checkpoint_hits;
    int corrupt_data_read_once;
} fixture_t;

static fixture_t fixture;
static int checks;
static int failures;

static const uint8_t golden_sha256[32] = {
    0xD8, 0xE2, 0x6E, 0x51, 0xCF, 0x57, 0x45, 0x70,
    0xD6, 0x98, 0x42, 0xB6, 0xDC, 0xC9, 0x26, 0xC7,
    0xBE, 0xCB, 0x2F, 0x05, 0x0A, 0x2F, 0x99, 0x67,
    0x02, 0xC1, 0x07, 0x5F, 0xC1, 0x61, 0x7B, 0xFC
};

static void check(const char *name, int condition)
{
    ++checks;
    printf("  %-66s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
    {
        ++failures;
    }
}

static uint32_t get_u32le(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static uint32_t flash_offset(uint32_t address)
{
    return address - OTA_EXT_STAGING;
}

static int range_ok(uint32_t address, uint32_t len)
{
    return address >= OTA_EXT_STAGING &&
           len <= OTA_EXT_STAGING_LENGTH &&
           address - OTA_EXT_STAGING <= OTA_EXT_STAGING_LENGTH - len;
}

static void record_operation(fixture_t *state, int type,
                             uint32_t address, uint32_t len)
{
    if (state->operation_count < MAX_OPS)
    {
        operation_t *operation = &state->operations[state->operation_count++];
        operation->type = type;
        operation->address = address;
        operation->len = len;
    }
}

static int fixture_read(void *ctx, uint32_t address,
                        uint8_t *dst, uint32_t len)
{
    fixture_t *state = (fixture_t *)ctx;

    if (dst == 0 || !range_ok(address, len))
    {
        return -1;
    }
    record_operation(state, OP_READ, address, len);
    memcpy(dst, state->flash + flash_offset(address), len);
    if (state->corrupt_data_read_once &&
        address >= OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET)
    {
        dst[0] ^= 0x01u;
        state->corrupt_data_read_once = 0;
    }
    return 0;
}

static int fixture_erase(void *ctx, uint32_t address)
{
    fixture_t *state = (fixture_t *)ctx;

    if (!range_ok(address, OTA_STAGING_BLOCK_SIZE) ||
        (address & (OTA_STAGING_BLOCK_SIZE - 1u)) != 0u)
    {
        return -1;
    }
    record_operation(state, OP_ERASE, address, OTA_STAGING_BLOCK_SIZE);
    memset(state->flash + flash_offset(address), 0xFF,
           OTA_STAGING_BLOCK_SIZE);
    return 0;
}

static int fixture_program(void *ctx, uint32_t address,
                           const uint8_t *src, uint32_t len)
{
    fixture_t *state = (fixture_t *)ctx;
    uint32_t offset;

    if (src == 0 || len == 0u || !range_ok(address, len))
    {
        return -1;
    }
    for (offset = 0u; offset < len; ++offset)
    {
        uint8_t old_value = state->flash[flash_offset(address) + offset];
        if ((old_value & src[offset]) != src[offset])
        {
            return -1;
        }
    }
    record_operation(state, OP_PROGRAM, address, len);
    for (offset = 0u; offset < len; ++offset)
    {
        state->flash[flash_offset(address) + offset] &= src[offset];
    }
    return 0;
}

static int fixture_checkpoint(void *ctx, uint32_t point,
                              uint32_t arg0, uint32_t arg1)
{
    fixture_t *state = (fixture_t *)ctx;
    (void)arg0;
    (void)arg1;
    ++state->checkpoint_hits;
    if (state->interrupt_checkpoint == point)
    {
        state->interrupt_checkpoint = 0u;
        return -1;
    }
    return 0;
}

static ota_staging_io_t fixture_io(void)
{
    ota_staging_io_t io;

    io.ctx = &fixture;
    io.read = fixture_read;
    io.erase_4k = fixture_erase;
    io.program = fixture_program;
    io.checkpoint = fixture_checkpoint;
    return io;
}

static void reset_fixture(void)
{
    memset(&fixture, 0, sizeof(fixture));
    memset(fixture.flash, 0xFF, sizeof(fixture.flash));
}

static uint32_t count_operations(int type, uint32_t address)
{
    uint32_t count = 0u;
    uint32_t index;

    for (index = 0u; index < fixture.operation_count; ++index)
    {
        operation_t *operation = &fixture.operations[index];
        if (operation->type == type && operation->address == address)
        {
            ++count;
        }
    }
    return count;
}

static int find_operation(int type, uint32_t address, uint32_t len)
{
    uint32_t index;

    for (index = 0u; index < fixture.operation_count; ++index)
    {
        operation_t *operation = &fixture.operations[index];
        if (operation->type == type && operation->address == address &&
            operation->len == len)
        {
            return (int)index;
        }
    }
    return -1;
}

static uint8_t *load_file(const char *path, uint32_t *length)
{
    FILE *file = fopen(path, "rb");
    long size;
    uint8_t *data;

    if (file == 0)
    {
        return 0;
    }
    if (fseek(file, 0, SEEK_END) != 0)
    {
        fclose(file);
        return 0;
    }
    size = ftell(file);
    if (size <= 0 || (unsigned long)size > (unsigned long)UINT32_MAX ||
        fseek(file, 0, SEEK_SET) != 0)
    {
        fclose(file);
        return 0;
    }
    data = (uint8_t *)malloc((size_t)size);
    if (data == 0 || fread(data, 1u, (size_t)size, file) != (size_t)size)
    {
        free(data);
        fclose(file);
        return 0;
    }
    fclose(file);
    *length = (uint32_t)size;
    return data;
}

static ota_staging_result_t send_all_segments(
    ota_staging_receiver_t *receiver,
    const uint8_t *data,
    uint32_t len,
    ota_staging_progress_t *progress)
{
    uint32_t offset;
    ota_staging_result_t result = OTA_STAGING_OK;

    for (offset = 0u; offset < len; offset += OTA_STAGING_SEGMENT_SIZE)
    {
        uint32_t take = len - offset;
        if (take > OTA_STAGING_SEGMENT_SIZE)
        {
            take = OTA_STAGING_SEGMENT_SIZE;
        }
        result = ota_staging_receive(receiver, offset, data + offset,
                                     take, progress);
        if (result < 0 || result == OTA_STAGING_INTERRUPTED)
        {
            return result;
        }
    }
    return result;
}

static void test_contract_crc_sample(void)
{
    uint8_t prefix[40];

    memset(prefix, 0, sizeof(prefix));
    memcpy(prefix, "ETRJ", 4u);
    prefix[36] = 100u;
    check("contract ETRJ sample CRC32 is 0xC0178C87",
          ota_staging_crc32(prefix, sizeof(prefix)) == 0xC0178C87u);
}

static void test_begin_and_session_rebuild(void)
{
    ota_staging_receiver_t receiver;
    ota_staging_receiver_t resumed_receiver;
    ota_staging_progress_t progress;
    ota_staging_io_t io;
    uint8_t other_sha[32];
    uint8_t *etrj;
    uint8_t *bitmap;
    uint32_t header_erases;

    reset_fixture();
    io = fixture_io();
    check("new session begin succeeds",
          ota_staging_begin(&receiver, &io, golden_sha256, 748u,
                            &progress) == OTA_STAGING_OK);
    check("new session reports resumed=0 durable_off=0 bitmap=0",
          progress.resumed == 0u && progress.durable_off == 0u &&
              progress.segment_bitmap == 0u);
    check("new session erases only the 4 KiB header sector",
          count_operations(OP_ERASE, OTA_EXT_STAGING) == 1u);
    etrj = fixture.flash + OTA_STAGING_ETRJ_OFFSET;
    bitmap = fixture.flash + OTA_STAGING_BITMAP_OFFSET;
    check("ETRJ magic, package SHA, and total_len are serialized by offset",
          memcmp(etrj, "ETRJ", 4u) == 0 &&
              memcmp(etrj + 4u, golden_sha256, 32u) == 0 &&
              get_u32le(etrj + 36u) == 748u);
    check("ETRJ CRC covers exactly the immutable 40-byte prefix",
          get_u32le(etrj + 40u) == ota_staging_crc32(etrj, 40u));
    check("fresh persistent block bitmap remains erased",
          bitmap[0] == 0xFFu && bitmap[63] == 0xFFu);
    check("fresh staging commit marker remains erased",
          get_u32le(fixture.flash + 28u) == UINT32_MAX);

    header_erases = count_operations(OP_ERASE, OTA_EXT_STAGING);
    check("matching reconnect resumes without erasing the header page",
          ota_staging_begin(&resumed_receiver, &io, golden_sha256, 748u,
                            &progress) == OTA_STAGING_OK &&
              progress.resumed == 1u && progress.durable_off == 0u &&
              count_operations(OP_ERASE, OTA_EXT_STAGING) == header_erases);

    fixture.flash[OTA_STAGING_ETRJ_OFFSET + 40u] ^= 0x01u;
    check("invalid ETRJ CRC rebuilds the session page from zero",
          ota_staging_begin(&receiver, &io, golden_sha256, 748u,
                            &progress) == OTA_STAGING_OK &&
              progress.resumed == 0u &&
              count_operations(OP_ERASE, OTA_EXT_STAGING) ==
                  header_erases + 1u);

    memcpy(other_sha, golden_sha256, sizeof(other_sha));
    other_sha[31] ^= 0x5Au;
    header_erases = count_operations(OP_ERASE, OTA_EXT_STAGING);
    check("a different package SHA is the only normal new-session rebuild",
          ota_staging_begin(&receiver, &io, other_sha, 748u,
                            &progress) == OTA_STAGING_OK &&
              progress.resumed == 0u &&
              count_operations(OP_ERASE, OTA_EXT_STAGING) ==
                  header_erases + 1u);
}

static void test_golden_vector_receive_and_finalize(void)
{
    ota_staging_receiver_t receiver;
    ota_staging_receiver_t rebooted;
    ota_staging_progress_t progress;
    ota_staging_io_t io;
    ota_staging_result_t result;
    uint8_t *package;
    uint32_t package_len = 0u;
    uint32_t offset;
    uint32_t data_address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    uint32_t erase_count;
    uint32_t program_count;
    uint32_t package_crc;
    int fields_program;
    int marker_program;

    package = load_file("tests/ota-vectors/toy-full.etu", &package_len);
    check("golden toy-full.etu fixture is available and 748 bytes",
          package != 0 && package_len == 748u);
    if (package == 0)
    {
        return;
    }

    reset_fixture();
    io = fixture_io();
    check("golden session begin succeeds",
          ota_staging_begin(&receiver, &io, golden_sha256, package_len,
                            &progress) == OTA_STAGING_OK);

    result = ota_staging_receive(&receiver, 128u, package + 128u,
                                 128u, &progress);
    check("out-of-order segment is buffered only in the 4 KiB RAM window",
          result == OTA_STAGING_OK && progress.durable_off == 0u &&
              progress.segment_bitmap == 0x2u &&
              count_operations(OP_ERASE, data_address) == 0u);
    check("same in-RAM segment retransmit is idempotent",
          ota_staging_receive(&receiver, 128u, package + 128u,
                              128u, &progress) == OTA_STAGING_DUPLICATE);
    package[128u] ^= 0x01u;
    check("conflicting in-RAM retransmit is rejected",
          ota_staging_receive(&receiver, 128u, package + 128u,
                              128u, &progress) == OTA_STAGING_ERR_DATA);
    package[128u] ^= 0x01u;

    for (offset = 0u; offset < package_len;
         offset += OTA_STAGING_SEGMENT_SIZE)
    {
        uint32_t take = package_len - offset;
        if (offset == 128u)
        {
            continue;
        }
        if (take > OTA_STAGING_SEGMENT_SIZE)
        {
            take = OTA_STAGING_SEGMENT_SIZE;
        }
        result = ota_staging_receive(&receiver, offset, package + offset,
                                     take, &progress);
    }
    check("tail segment completion commits the golden package",
          result == OTA_STAGING_PACKAGE_COMPLETE &&
              progress.complete == 1u && progress.durable_off == package_len);
    check("golden payload is byte-exact in staging after erase/write/readback",
          memcmp(fixture.flash + OTA_STAGING_PAYLOAD_OFFSET,
                 package, package_len) == 0);
    check("block bit clears only after the verified package tail is durable",
          fixture.flash[OTA_STAGING_BITMAP_OFFSET] == 0xFEu);
    check("one-block golden package used one data erase and one data program",
          count_operations(OP_ERASE, data_address) == 1u &&
              count_operations(OP_PROGRAM, data_address) == 1u);

    erase_count = count_operations(OP_ERASE, data_address);
    program_count = count_operations(OP_PROGRAM, data_address);
    check("reboot reconstructs completed durable_off from persistent bitmap",
          ota_staging_begin(&rebooted, &io, golden_sha256, package_len,
                            &progress) == OTA_STAGING_OK &&
              progress.resumed == 1u && progress.complete == 1u &&
              progress.durable_off == package_len);
    check("DATA before durable_off returns ACK state without rewriting flash",
          ota_staging_receive(&rebooted, 0u, package, 128u,
                              &progress) == OTA_STAGING_DUPLICATE &&
              count_operations(OP_ERASE, data_address) == erase_count &&
              count_operations(OP_PROGRAM, data_address) == program_count);

    package_crc = ota_staging_crc32(package, package_len);
    check("finalize writes validated ETSL fields then marker",
          ota_staging_finalize(&rebooted, package_crc, 20800u) ==
              OTA_STAGING_OK);
    check("ETSL fields encode staging type, length, CRC, vcode, and SHA8",
          memcmp(fixture.flash, "ETSL", 4u) == 0 &&
              fixture.flash[4] == 3u &&
              get_u32le(fixture.flash + 8u) == package_len &&
              get_u32le(fixture.flash + 12u) == package_crc &&
              get_u32le(fixture.flash + 16u) == 20800u &&
              memcmp(fixture.flash + 20u, golden_sha256, 8u) == 0);
    check("ETSL commit marker has the contracted little-endian value",
          get_u32le(fixture.flash + 28u) == OTA_STAGING_COMMIT_MARKER);
    fields_program = find_operation(OP_PROGRAM, OTA_EXT_STAGING, 28u);
    marker_program = find_operation(OP_PROGRAM, OTA_EXT_STAGING + 28u, 4u);
    check("commit marker is a later, separate program operation",
          fields_program >= 0 && marker_program > fields_program);
    erase_count = count_operations(OP_PROGRAM, OTA_EXT_STAGING);
    program_count = count_operations(OP_PROGRAM, OTA_EXT_STAGING + 28u);
    check("repeated finalize is idempotent and never rewrites an old marker",
          ota_staging_finalize(&rebooted, package_crc, 20800u) ==
                  OTA_STAGING_OK &&
              count_operations(OP_PROGRAM, OTA_EXT_STAGING) == erase_count &&
              count_operations(OP_PROGRAM, OTA_EXT_STAGING + 28u) ==
                  program_count);

    free(package);
}

static void fill_pattern(uint8_t data[OTA_STAGING_BLOCK_SIZE])
{
    uint32_t index;

    for (index = 0u; index < OTA_STAGING_BLOCK_SIZE; ++index)
    {
        data[index] = (uint8_t)(index * 17u + 3u);
    }
}

static void test_readback_checkpoint_reentry(void)
{
    ota_staging_receiver_t first;
    ota_staging_receiver_t rebooted;
    ota_staging_progress_t progress;
    ota_staging_io_t io;
    ota_staging_result_t result;
    uint8_t data[OTA_STAGING_BLOCK_SIZE];
    uint8_t session_sha[32];
    uint32_t data_address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;

    reset_fixture();
    io = fixture_io();
    fill_pattern(data);
    memset(session_sha, 0xA5, sizeof(session_sha));
    check("fault-injection session begin succeeds",
          ota_staging_begin(&first, &io, session_sha, sizeof(data),
                            &progress) == OTA_STAGING_OK);
    fixture.interrupt_checkpoint = OTA_STAGING_CP_AFTER_BLOCK_READBACK;
    result = send_all_segments(&first, data, sizeof(data), &progress);
    check("reset injection stops after data readback and before bitmap clear",
          result == OTA_STAGING_INTERRUPTED);
    check("interrupted block data is present but persistent bit remains one",
          memcmp(fixture.flash + OTA_STAGING_PAYLOAD_OFFSET,
                 data, sizeof(data)) == 0 &&
              fixture.flash[OTA_STAGING_BITMAP_OFFSET] == 0xFFu);
    check("first interrupted attempt erased and programmed the data sector",
          count_operations(OP_ERASE, data_address) == 1u &&
              count_operations(OP_PROGRAM, data_address) == 1u);

    check("post-reset begin resumes session with durable_off still zero",
          ota_staging_begin(&rebooted, &io, session_sha, sizeof(data),
                            &progress) == OTA_STAGING_OK &&
              progress.resumed == 1u && progress.durable_off == 0u &&
              progress.segment_bitmap == 0u);
    result = send_all_segments(&rebooted, data, sizeof(data), &progress);
    check("full block retransmit succeeds after reset",
          result == OTA_STAGING_PACKAGE_COMPLETE &&
              progress.durable_off == sizeof(data));
    check("retransmit erased the partially programmed sector a second time",
          count_operations(OP_ERASE, data_address) == 2u &&
              count_operations(OP_PROGRAM, data_address) == 2u);
    check("durable bit clears only on the successful second attempt",
          fixture.flash[OTA_STAGING_BITMAP_OFFSET] == 0xFEu);
}

static void test_readback_failure_and_marker_interruption(void)
{
    ota_staging_receiver_t receiver;
    ota_staging_progress_t progress;
    ota_staging_io_t io;
    ota_staging_result_t result;
    uint8_t data[OTA_STAGING_BLOCK_SIZE];
    uint8_t session_sha[32];
    uint32_t data_address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    uint32_t fields_programs;

    reset_fixture();
    io = fixture_io();
    fill_pattern(data);
    memset(session_sha, 0x3C, sizeof(session_sha));
    check("readback-failure session begin succeeds",
          ota_staging_begin(&receiver, &io, session_sha, sizeof(data),
                            &progress) == OTA_STAGING_OK);
    fixture.corrupt_data_read_once = 1;
    result = send_all_segments(&receiver, data, sizeof(data), &progress);
    check("data readback mismatch fails closed",
          result == OTA_STAGING_ERR_VERIFY);
    check("readback mismatch leaves durable bit set and drops RAM progress",
          fixture.flash[OTA_STAGING_BITMAP_OFFSET] == 0xFFu &&
              progress.durable_off == 0u && progress.segment_bitmap == 0u);
    result = send_all_segments(&receiver, data, sizeof(data), &progress);
    check("whole block can be retransmitted after readback failure",
          result == OTA_STAGING_PACKAGE_COMPLETE &&
              count_operations(OP_ERASE, data_address) == 2u);

    fixture.interrupt_checkpoint = OTA_STAGING_CP_ETSL_READBACK;
    result = ota_staging_finalize(&receiver,
                                  ota_staging_crc32(data, sizeof(data)),
                                  20801u);
    check("finalize interruption occurs after fields readback",
          result == OTA_STAGING_INTERRUPTED);
    check("interrupted finalize leaves marker erased and fields intact",
          memcmp(fixture.flash, "ETSL", 4u) == 0 &&
              get_u32le(fixture.flash + 28u) == UINT32_MAX);
    fields_programs = count_operations(OP_PROGRAM, OTA_EXT_STAGING);
    check("retry after finalize interruption writes only the marker",
          ota_staging_finalize(&receiver,
                               ota_staging_crc32(data, sizeof(data)),
                               20801u) == OTA_STAGING_OK &&
              count_operations(OP_PROGRAM, OTA_EXT_STAGING) ==
                  fields_programs &&
              get_u32le(fixture.flash + 28u) == OTA_STAGING_COMMIT_MARKER);
}

static void test_input_guards(void)
{
    ota_staging_receiver_t receiver;
    ota_staging_progress_t progress;
    ota_staging_io_t io;
    uint8_t sha[32];
    uint8_t data[128];

    reset_fixture();
    io = fixture_io();
    memset(sha, 0x11, sizeof(sha));
    memset(data, 0x22, sizeof(data));
    check("zero-length and oversized sessions are rejected",
          ota_staging_begin(&receiver, &io, sha, 0u, &progress) ==
                  OTA_STAGING_ERR_RANGE &&
              ota_staging_begin(&receiver, &io, sha,
                                OTA_ETU_MAX_LENGTH + 1u, &progress) ==
                  OTA_STAGING_ERR_RANGE);
    check("valid guard-test session begins",
          ota_staging_begin(&receiver, &io, sha, 4096u,
                            &progress) == OTA_STAGING_OK);
    check("unaligned DATA offset is rejected",
          ota_staging_receive(&receiver, 1u, data, sizeof(data),
                              &progress) == OTA_STAGING_ERR_RANGE);
    check("short non-tail DATA segment is rejected",
          ota_staging_receive(&receiver, 0u, data, 64u,
                              &progress) == OTA_STAGING_ERR_RANGE);
    check("DATA outside the current 4 KiB window is rejected",
          ota_staging_receive(&receiver, 4096u, data, sizeof(data),
                              &progress) == OTA_STAGING_ERR_RANGE);
    check("finalize before durable completion is rejected",
          ota_staging_finalize(&receiver, 0u, 20800u) ==
              OTA_STAGING_ERR_STATE);
}

int main(void)
{
    printf("=== P2-1 OTA staging tests ===\n");
    test_contract_crc_sample();
    test_begin_and_session_rebuild();
    test_golden_vector_receive_and_finalize();
    test_readback_checkpoint_reentry();
    test_readback_failure_and_marker_interruption();
    test_input_guards();
    printf("=== summary: %d checks, %d failure(s) ===\n", checks, failures);
    if (failures == 0)
    {
        printf("P2_1_STAGING=PASS checks=%d failures=0\n", checks);
    }
    return failures == 0 ? 0 : 1;
}
