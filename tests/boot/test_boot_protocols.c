#include "boot_slot.h"
#include "boot_ymodem.h"

#include "OTA/ota_layout.h"

#include <stdint.h>
#include <stdio.h>
#include <string.h>

enum
{
    SOH = 0x01,
    STX = 0x02,
    EOT = 0x04,
    ACK = 0x06,
    NAK = 0x15,
    CAN = 0x18,
    BLOCK_128 = 128,
    BLOCK_1K = 1024
};

typedef struct
{
    uint8_t input[8192];
    size_t input_len;
    size_t input_pos;
    uint8_t output[256];
    size_t output_len;
    uint8_t received[2048];
    size_t received_len;
    uint32_t declared_size;
    char file_name[64];
    int begin_calls;
    int end_calls;
    int abort_calls;
    int end_result;
} fixture_t;

static unsigned failures;
static unsigned checks;

static void check(const char *name, int condition)
{
    ++checks;
    if (!condition)
    {
        ++failures;
    }
    printf("  %-48s %s\n", name, condition ? "PASS" : "FAIL");
}

static uint16_t crc16_xmodem(const uint8_t *data, size_t len)
{
    uint16_t crc = 0u;
    size_t i;

    for (i = 0u; i < len; ++i)
    {
        uint32_t bit;
        crc ^= (uint16_t)data[i] << 8;
        for (bit = 0u; bit < 8u; ++bit)
        {
            crc = (crc & 0x8000u) != 0u
                      ? (uint16_t)((crc << 1) ^ 0x1021u)
                      : (uint16_t)(crc << 1);
        }
    }
    return crc;
}

static void append_byte(fixture_t *fixture, uint8_t value)
{
    fixture->input[fixture->input_len++] = value;
}

static void append_packet(fixture_t *fixture,
                          uint8_t first,
                          uint8_t sequence,
                          const uint8_t *data,
                          size_t data_len,
                          int corrupt_crc)
{
    uint8_t block[BLOCK_1K];
    size_t block_len = first == SOH ? BLOCK_128 : BLOCK_1K;
    uint16_t crc;

    memset(block, 0x1A, block_len);
    if (data != NULL && data_len != 0u)
    {
        memcpy(block, data, data_len);
    }
    append_byte(fixture, first);
    append_byte(fixture, sequence);
    append_byte(fixture, (uint8_t)~sequence);
    memcpy(fixture->input + fixture->input_len, block, block_len);
    fixture->input_len += block_len;
    crc = crc16_xmodem(block, block_len);
    if (corrupt_crc)
    {
        crc ^= 1u;
    }
    append_byte(fixture, (uint8_t)(crc >> 8));
    append_byte(fixture, (uint8_t)crc);
}

static void append_transfer(fixture_t *fixture,
                            const uint8_t *payload,
                            size_t payload_len,
                            int retry_first_packet,
                            int duplicate_first_packet)
{
    uint8_t header[BLOCK_128];
    uint8_t empty[BLOCK_128];
    char size_text[16];
    size_t name_len;
    size_t offset = 0u;
    uint8_t sequence = 1u;

    memset(header, 0, sizeof(header));
    memcpy(header, "recovery.bin", sizeof("recovery.bin"));
    name_len = strlen((const char *)header);
    (void)snprintf(size_text, sizeof(size_text), "%lu", (unsigned long)payload_len);
    memcpy(header + name_len + 1u, size_text, strlen(size_text) + 1u);
    append_packet(fixture, SOH, 0u, header, sizeof(header), 0);

    while (offset < payload_len)
    {
        size_t left = payload_len - offset;
        uint8_t first = left > BLOCK_128 ? STX : SOH;
        size_t take = first == STX ? BLOCK_1K : BLOCK_128;
        if (take > left)
        {
            take = left;
        }
        if (sequence == 1u && retry_first_packet)
        {
            append_packet(fixture, first, sequence, payload + offset, take, 1);
        }
        append_packet(fixture, first, sequence, payload + offset, take, 0);
        if (sequence == 1u && duplicate_first_packet)
        {
            append_packet(fixture, first, sequence, payload + offset, take, 0);
        }
        offset += take;
        ++sequence;
    }

    append_byte(fixture, EOT);
    append_byte(fixture, EOT);
    memset(empty, 0, sizeof(empty));
    append_packet(fixture, SOH, 0u, empty, sizeof(empty), 0);
}

static int io_getc(void *ctx, uint8_t *byte, uint32_t timeout_ms)
{
    fixture_t *fixture = (fixture_t *)ctx;
    (void)timeout_ms;
    if (fixture->input_pos >= fixture->input_len)
    {
        return -1;
    }
    *byte = fixture->input[fixture->input_pos++];
    return 0;
}

static void io_putc(void *ctx, uint8_t byte)
{
    fixture_t *fixture = (fixture_t *)ctx;
    fixture->output[fixture->output_len++] = byte;
}

static int sink_begin(void *ctx, const char *name, uint32_t total_size)
{
    fixture_t *fixture = (fixture_t *)ctx;
    ++fixture->begin_calls;
    fixture->declared_size = total_size;
    (void)snprintf(fixture->file_name, sizeof(fixture->file_name), "%s", name);
    return total_size <= sizeof(fixture->received) ? 0 : -1;
}

static int sink_write(void *ctx, const uint8_t *data, size_t len)
{
    fixture_t *fixture = (fixture_t *)ctx;
    if (len > sizeof(fixture->received) - fixture->received_len)
    {
        return -1;
    }
    memcpy(fixture->received + fixture->received_len, data, len);
    fixture->received_len += len;
    return 0;
}

static int sink_end(void *ctx)
{
    fixture_t *fixture = (fixture_t *)ctx;
    ++fixture->end_calls;
    return fixture->end_result;
}

static void sink_abort(void *ctx)
{
    fixture_t *fixture = (fixture_t *)ctx;
    ++fixture->abort_calls;
}

static boot_ymodem_result_t run_transfer(fixture_t *fixture)
{
    boot_ymodem_io_t io = {io_getc, io_putc, fixture};
    boot_ymodem_sink_t sink = {
        sink_begin, sink_write, sink_end, sink_abort, fixture
    };
    return boot_ymodem_receive(&io, &sink);
}

static int output_contains(const fixture_t *fixture, uint8_t value)
{
    size_t i;
    for (i = 0u; i < fixture->output_len; ++i)
    {
        if (fixture->output[i] == value)
        {
            return 1;
        }
    }
    return 0;
}

static void test_ymodem(void)
{
    uint8_t payload[1100];
    fixture_t fixture;
    size_t i;

    for (i = 0u; i < sizeof(payload); ++i)
    {
        payload[i] = (uint8_t)(i * 17u + 3u);
    }

    memset(&fixture, 0, sizeof(fixture));
    append_transfer(&fixture, payload, sizeof(payload), 0, 0);
    check("Ymodem valid transfer", run_transfer(&fixture) == BOOT_YMODEM_OK);
    check("Ymodem declared size", fixture.declared_size == sizeof(payload));
    check("Ymodem file name", strcmp(fixture.file_name, "recovery.bin") == 0);
    check("Ymodem payload exact", fixture.received_len == sizeof(payload) &&
                                      memcmp(fixture.received, payload, sizeof(payload)) == 0);
    check("Ymodem valid sink lifecycle", fixture.begin_calls == 1 &&
                                             fixture.end_calls == 1 &&
                                             fixture.abort_calls == 0);
    check("Ymodem final ACK", fixture.output_len != 0u &&
                                  fixture.output[fixture.output_len - 1u] == ACK);

    memset(&fixture, 0, sizeof(fixture));
    append_transfer(&fixture, payload, sizeof(payload), 1, 1);
    check("Ymodem CRC retry and duplicate", run_transfer(&fixture) == BOOT_YMODEM_OK);
    check("Ymodem retry emits NAK", output_contains(&fixture, NAK));
    check("Ymodem duplicate is idempotent", fixture.received_len == sizeof(payload) &&
                                                memcmp(fixture.received, payload,
                                                       sizeof(payload)) == 0);

    memset(&fixture, 0, sizeof(fixture));
    fixture.end_result = -1;
    append_transfer(&fixture, payload, sizeof(payload), 0, 0);
    check("Ymodem sink end failure", run_transfer(&fixture) == BOOT_YMODEM_ERR_SINK);
    check("Ymodem sink failure aborts", fixture.abort_calls == 1);
    check("Ymodem sink failure sends CAN", fixture.output_len >= 2u &&
                                               fixture.output[fixture.output_len - 2u] == CAN &&
                                               fixture.output[fixture.output_len - 1u] == CAN);
}

static void write_le32(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static void make_slot(uint8_t raw[BOOT_SLOT_HEADER_SIZE],
                      boot_slot_type_t type,
                      uint32_t payload_len)
{
    memset(raw, 0xFF, BOOT_SLOT_HEADER_SIZE);
    memcpy(raw, "ETSL", 4u);
    raw[4] = (uint8_t)type;
    write_le32(raw + 8u, payload_len);
    write_le32(raw + 12u, 0x12345678u);
    write_le32(raw + 16u, 20800u);
    memcpy(raw + 20u, "12345678", 8u);
    write_le32(raw + 28u, 0x434F4D54u);
}

static void test_slot_header(void)
{
    uint8_t raw[BOOT_SLOT_HEADER_SIZE];
    boot_slot_header_t parsed;

    make_slot(raw, BOOT_SLOT_CANDIDATE, OTA_APP_LENGTH);
    check("ETSL candidate valid", boot_slot_header_parse(
              raw, BOOT_SLOT_CANDIDATE, &parsed) == BOOT_SLOT_OK);
    check("ETSL candidate fields", parsed.payload_len == OTA_APP_LENGTH &&
                                        parsed.version_code == 20800u &&
                                        memcmp(parsed.sha8, "12345678", 8u) == 0);

    make_slot(raw, BOOT_SLOT_STAGING, OTA_ETU_MAX_LENGTH);
    check("ETSL staging valid", boot_slot_header_parse(
              raw, BOOT_SLOT_STAGING, NULL) == BOOT_SLOT_OK);

    raw[28] = 0xFFu;
    check("ETSL missing commit rejected", boot_slot_header_parse(
              raw, BOOT_SLOT_STAGING, NULL) == BOOT_SLOT_ERR_COMMIT);

    make_slot(raw, BOOT_SLOT_CANDIDATE, OTA_APP_LENGTH + 1u);
    check("ETSL oversize rejected", boot_slot_header_parse(
              raw, BOOT_SLOT_CANDIDATE, NULL) == BOOT_SLOT_ERR_LENGTH);

    make_slot(raw, BOOT_SLOT_BACKUP, OTA_APP_LENGTH);
    check("ETSL wrong type rejected", boot_slot_header_parse(
              raw, BOOT_SLOT_CANDIDATE, NULL) == BOOT_SLOT_ERR_TYPE);

    make_slot(raw, BOOT_SLOT_CANDIDATE, OTA_APP_LENGTH);
    raw[5] = 0u;
    check("ETSL dirty padding rejected", boot_slot_header_parse(
              raw, BOOT_SLOT_CANDIDATE, NULL) == BOOT_SLOT_ERR_PADDING);
}

int main(void)
{
    printf("=== Boot protocol tests ===\n");
    test_ymodem();
    test_slot_header();
    printf("=== summary: %u checks, %u failure(s) ===\n", checks, failures);
    return failures == 0u ? 0 : 1;
}
