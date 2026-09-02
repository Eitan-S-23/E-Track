#include "OTA/ota_ble_frame.h"
#include "OTA/ota_ble_ring.h"

#include <stdio.h>
#include <string.h>

static int checks;
static int failures;

static void check(const char *name, int condition)
{
    ++checks;
    printf("  %-68s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
    {
        ++failures;
    }
}

/* bad_frames 是跨 reset 的累计诊断：parser 结构必须整体清零后再 reset */
static void parser_start(ota_ble_parser_t *parser)
{
    memset(parser, 0, sizeof(*parser));
    ota_ble_parser_reset(parser);
}

static uint32_t lcg_next(uint32_t *seed)
{
    *seed = *seed * 1103515245u + 12345u;
    return (*seed >> 16u) & 0x7FFFu;
}

static void test_crc16_vectors(void)
{
    check("CRC16-CCITT-FALSE check value for 123456789 is 0x29B1",
          ota_ble_crc16((const uint8_t *)"123456789", 9u) == 0x29B1u);
    check("CRC16 of the empty input keeps the init value 0xFFFF",
          ota_ble_crc16((const uint8_t *)"", 0u) == 0xFFFFu);
    check("CRC16 is sensitive to a single-bit payload change",
          ota_ble_crc16((const uint8_t *)"123456789", 9u) !=
              ota_ble_crc16((const uint8_t *)"1234567" "\x89", 9u));
}

static int roundtrip_once(uint8_t cmd, uint8_t session, uint16_t seq,
                          const uint8_t *payload, uint16_t len)
{
    uint8_t wire[OTA_BLE_MAX_FRAME];
    ota_ble_parser_t parser;
    ota_ble_frame_t frame;
    ota_ble_parse_result_t result = OTA_BLE_PARSE_IDLE;
    size_t wire_len;
    uint32_t i;
    int got = 0;

    wire_len = ota_ble_frame_encode(wire, sizeof(wire), cmd, session, seq,
                                    payload, len);
    if (wire_len == 0u ||
        wire_len != OTA_BLE_HEADER_SIZE + (size_t)len + OTA_BLE_CRC_SIZE)
    {
        return 0;
    }
    parser_start(&parser);
    for (i = 0u; i < (uint32_t)wire_len; ++i)
    {
        result = ota_ble_parser_feed(&parser, wire[i], &frame);
        if (result != OTA_BLE_PARSE_IDLE)
        {
            got = 1;
            break;
        }
    }
    if (!got || result != OTA_BLE_PARSE_FRAME)
    {
        return 0;
    }
    return frame.cmd == cmd && frame.session == session &&
           frame.seq == seq && frame.len == len &&
           (len == 0u || memcmp(frame.payload, payload, (size_t)len) == 0);
}

static void test_encode_parse_roundtrip(void)
{
    uint8_t payload[OTA_BLE_MAX_PAYLOAD];
    uint32_t i;

    for (i = 0u; i < (uint32_t)sizeof(payload); ++i)
    {
        payload[i] = (uint8_t)(i * 7u + 3u);
    }
    /* payload 内嵌同步头模式：parser 在 PAYLOAD 态不得中途重同步 */
    payload[10] = OTA_BLE_SYNC0;
    payload[11] = OTA_BLE_SYNC1;
    payload[12] = OTA_BLE_SYNC0;

    check("GET_INFO frame with empty payload round-trips",
          roundtrip_once(OTA_BLE_CMD_GET_INFO, 0u, 0u, NULL, 0u));
    check("ABORT frame with empty payload round-trips",
          roundtrip_once(OTA_BLE_CMD_ABORT, 0u, 0xFFFFu, NULL, 0u));
    check("BEGIN frame with the fixed 101-byte payload round-trips",
          roundtrip_once(OTA_BLE_CMD_BEGIN, 0u, 0x1234u, payload,
                         OTA_BLE_LEN_BEGIN));
    check("END frame with the fixed 32-byte payload round-trips",
          roundtrip_once(OTA_BLE_CMD_END, 0x7Fu, 42u, payload,
                         OTA_BLE_LEN_END));
    check("DATA frame with the minimal 4-byte payload round-trips",
          roundtrip_once(OTA_BLE_CMD_DATA, 0x01u, 11u, payload,
                         OTA_BLE_LEN_DATA_MIN));
    check("DATA frame with the maximal 132-byte payload round-trips",
          roundtrip_once(OTA_BLE_CMD_DATA, 0xFFu, 0xFFFEu, payload,
                         OTA_BLE_MAX_PAYLOAD));
    check("session and seq echo covers the full 16-bit range",
          roundtrip_once(OTA_BLE_CMD_DATA, 0xA5u, 0x5A5Au, payload, 132u));
}

static void test_encode_guards(void)
{
    uint8_t wire[OTA_BLE_MAX_FRAME];
    uint8_t payload[4];

    payload[0] = 1u;
    payload[1] = 2u;
    payload[2] = 3u;
    payload[3] = 4u;

    check("encode rejects a NULL destination",
          ota_ble_frame_encode(NULL, sizeof(wire), OTA_BLE_CMD_DATA, 0u, 0u,
                               payload, 4u) == 0u);
    check("encode rejects a payload beyond the 132-byte cap",
          ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA, 0u, 0u,
                               payload, (uint16_t)(OTA_BLE_MAX_PAYLOAD + 1u)) ==
              0u);
    check("encode rejects a NULL payload with a non-zero length",
          ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA, 0u, 0u,
                               NULL, 4u) == 0u);
    check("encode accepts a NULL payload only with length zero",
          ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_ABORT, 0u, 0u,
                               NULL, 0u) != 0u);
    check("encode refuses to write a half frame into a short buffer",
          ota_ble_frame_encode(wire, OTA_BLE_HEADER_SIZE, OTA_BLE_CMD_DATA, 0u,
                               0u, payload, 4u) == 0u);
}

static void feed_all(const uint8_t *wire, size_t len,
                     ota_ble_parser_t *parser, ota_ble_frame_t *out_frame,
                     ota_ble_parse_result_t *out_result, int *out_got)
{
    uint32_t i;

    *out_got = 0;
    *out_result = OTA_BLE_PARSE_IDLE;
    for (i = 0u; i < (uint32_t)len; ++i)
    {
        *out_result = ota_ble_parser_feed(parser, wire[i], out_frame);
        if (*out_result != OTA_BLE_PARSE_IDLE)
        {
            *out_got = 1;
            break;
        }
    }
}

static void test_parser_error_paths(void)
{
    uint8_t payload[4];
    uint8_t wire[OTA_BLE_MAX_FRAME];
    ota_ble_parser_t parser;
    ota_ble_frame_t frame;
    ota_ble_parse_result_t result;
    size_t wire_len;
    int got;

    payload[0] = 1u;
    payload[1] = 2u;
    payload[2] = 3u;
    payload[3] = 4u;
    wire_len = ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA,
                                    0x07u, 0x1234u, payload, 4u);

    wire[2] = 0x07u;
    parser_start(&parser);
    feed_all(wire, wire_len, &parser, &frame, &result, &got);
    check("unknown command is rejected with zeroed echo fields",
          got && result == OTA_BLE_PARSE_ERR_FRAME && frame.cmd == 0u &&
              frame.session == 0u && frame.seq == 0u && frame.len == 0u &&
              parser.bad_frames == 1u);

    wire[2] = OTA_BLE_CMD_DATA;
    wire[6] = 200u;
    parser_start(&parser);
    feed_all(wire, wire_len, &parser, &frame, &result, &got);
    check("DATA length above the 132-byte cap is rejected with header echo",
          got && result == OTA_BLE_PARSE_ERR_FRAME &&
              frame.cmd == OTA_BLE_CMD_DATA && frame.session == 0x07u &&
              frame.seq == 0x1234u && frame.len == 0u);

    wire[6] = 3u;
    parser_start(&parser);
    feed_all(wire, wire_len, &parser, &frame, &result, &got);
    check("DATA length below the 4-byte minimum is rejected",
          got && result == OTA_BLE_PARSE_ERR_FRAME &&
              frame.cmd == OTA_BLE_CMD_DATA && frame.seq == 0x1234u);

    wire[6] = 4u;
    parser_start(&parser);
    wire[wire_len - 1u] ^= 0x55u;
    feed_all(wire, wire_len, &parser, &frame, &result, &got);
    check("a corrupted trailing CRC byte is rejected as ERR_CRC with echo",
          got && result == OTA_BLE_PARSE_ERR_CRC &&
              frame.cmd == OTA_BLE_CMD_DATA && frame.session == 0x07u &&
              frame.seq == 0x1234u && frame.len == 0u &&
              parser.bad_frames == 1u);

    /* BEGIN 长度不是定长 101：结构性拒绝 */
    wire_len = ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_BEGIN, 0u,
                                    9u, payload, 4u);
    parser_start(&parser);
    feed_all(wire, wire_len, &parser, &frame, &result, &got);
    check("BEGIN with a wrong fixed length is rejected",
          got && result == OTA_BLE_PARSE_ERR_FRAME &&
              frame.cmd == OTA_BLE_CMD_BEGIN && frame.seq == 9u);
}

static void test_parser_resync_after_noise(void)
{
    uint8_t payload[16];
    uint8_t wire[OTA_BLE_MAX_FRAME];
    uint8_t noise[96];
    ota_ble_parser_t parser;
    ota_ble_frame_t frame;
    ota_ble_parse_result_t result;
    uint32_t seed = 20260901u;
    uint32_t i;
    size_t wire_len;
    int got;
    uint32_t frames_seen = 0u;
    uint16_t seqs[2];
    uint32_t noise_idx;

    for (i = 0u; i < (uint32_t)sizeof(payload); ++i)
    {
        payload[i] = (uint8_t)(i * 13u + 5u);
    }
    for (i = 0u; i < (uint32_t)sizeof(noise); ++i)
    {
        /* 噪声避开 0xA5：本用例聚焦“帧间垃圾后重同步” */
        noise[i] = (uint8_t)(lcg_next(&seed) % 0x7Fu);
        if (noise[i] == OTA_BLE_SYNC0)
        {
            noise[i] = 0x00u;
        }
    }

    parser_start(&parser);
    for (noise_idx = 0u; noise_idx < 2u; ++noise_idx)
    {
        uint16_t seq = (uint16_t)(0x1100u + noise_idx);

        for (i = 0u; i < (uint32_t)sizeof(noise); ++i)
        {
            result = ota_ble_parser_feed(&parser, noise[i], &frame);
            if (result != OTA_BLE_PARSE_IDLE)
            {
                break;
            }
        }
        wire_len = ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA,
                                        0x03u, seq, payload,
                                        (uint16_t)sizeof(payload));
        for (i = 0u; i < (uint32_t)wire_len; ++i)
        {
            result = ota_ble_parser_feed(&parser, wire[i], &frame);
            if (result == OTA_BLE_PARSE_FRAME)
            {
                seqs[frames_seen] = frame.seq;
                ++frames_seen;
            }
        }
    }
    check("both frames parse in order after interleaved noise",
          frames_seen == 2u && seqs[0] == 0x1100u && seqs[1] == 0x1101u);

    /* 截断帧 + 纯零噪声 + 新帧：parser 终将回 SYNC1 并解析后续帧 */
    wire_len = ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA, 0x01u,
                                    0x0200u, payload,
                                    (uint16_t)sizeof(payload));
    parser_start(&parser);
    frames_seen = 0u;
    for (i = 0u; i < 3u; ++i)
    {
        (void)ota_ble_parser_feed(&parser, wire[i], &frame);
    }
    for (i = 0u; i < (uint32_t)sizeof(noise); ++i)
    {
        uint8_t zero = 0x00u;

        (void)ota_ble_parser_feed(&parser, zero, &frame);
    }
    for (i = 0u; i < (uint32_t)wire_len; ++i)
    {
        result = ota_ble_parser_feed(&parser, wire[i], &frame);
        if (result == OTA_BLE_PARSE_FRAME)
        {
            ++frames_seen;
        }
    }
    check("a truncated frame followed by zeros still resyncs to the next frame",
          frames_seen == 1u);

    /* 连续 A5 的 parser 规则：A5 A5 5A 仍可开始一帧 */
    parser_start(&parser);
    got = 0;
    (void)ota_ble_parser_feed(&parser, OTA_BLE_SYNC0, &frame);
    (void)ota_ble_parser_feed(&parser, OTA_BLE_SYNC0, &frame);
    (void)ota_ble_parser_feed(&parser, OTA_BLE_SYNC1, &frame);
    for (i = 2u; i < (uint32_t)wire_len; ++i)
    {
        result = ota_ble_parser_feed(&parser, wire[i], &frame);
        if (result != OTA_BLE_PARSE_IDLE)
        {
            got = (result == OTA_BLE_PARSE_FRAME);
            break;
        }
    }
    check("a doubled leading A5 does not break frame start",
          got && frame.seq == 0x0200u);
}

static uint8_t text_out[256];
static uint32_t text_len;

static void text_collect(void *ctx, uint8_t byte)
{
    (void)ctx;
    if (text_len < (uint32_t)sizeof(text_out))
    {
        text_out[text_len] = byte;
        ++text_len;
    }
}

static void test_demux_text_and_binary(void)
{
    ota_ble_demux_t demux;
    ota_ble_frame_t frame;
    ota_ble_parse_result_t result;
    uint8_t payload[8];
    uint8_t wire[OTA_BLE_MAX_FRAME];
    size_t wire_len;
    uint32_t i;
    const char *text = "HE";
    const char *tail = "LO";
    int frame_seen = 0;

    for (i = 0u; i < (uint32_t)sizeof(payload); ++i)
    {
        payload[i] = (uint8_t)(0x40u + i);
    }
    wire_len = ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA, 0x09u,
                                    0x0707u, payload,
                                    (uint16_t)sizeof(payload));

    text_len = 0u;
    ota_ble_demux_init(&demux);
    for (i = 0u; i < strlen(text); ++i)
    {
        (void)ota_ble_demux_feed(&demux, (uint8_t)text[i], text_collect, NULL,
                                 &frame);
    }
    for (i = 0u; i < (uint32_t)wire_len; ++i)
    {
        result = ota_ble_demux_feed(&demux, wire[i], text_collect, NULL,
                                    &frame);
        if (result == OTA_BLE_PARSE_FRAME)
        {
            frame_seen = 1;
        }
    }
    for (i = 0u; i < strlen(tail); ++i)
    {
        (void)ota_ble_demux_feed(&demux, (uint8_t)tail[i], text_collect, NULL,
                                 &frame);
    }
    check("text flows around a complete binary frame",
          frame_seen && text_len == 4u &&
              memcmp(text_out, "HELO", 4u) == 0u);

    /* 孤立 A5 + 普通字符：A5 归还文本，不丢字符 */
    text_len = 0u;
    ota_ble_demux_init(&demux);
    (void)ota_ble_demux_feed(&demux, (uint8_t)'X', text_collect, NULL, &frame);
    (void)ota_ble_demux_feed(&demux, OTA_BLE_SYNC0, text_collect, NULL,
                             &frame);
    (void)ota_ble_demux_feed(&demux, (uint8_t)'Y', text_collect, NULL, &frame);
    check("a lone A5 is returned to the text stream",
          text_len == 3u && memcmp(text_out, "X\xA5" "Y", 3u) == 0u);

    /* A5 A5 5A：文本只漏一个 A5，帧照常解析 */
    text_len = 0u;
    frame_seen = 0;
    ota_ble_demux_init(&demux);
    (void)ota_ble_demux_feed(&demux, OTA_BLE_SYNC0, text_collect, NULL,
                             &frame);
    (void)ota_ble_demux_feed(&demux, OTA_BLE_SYNC0, text_collect, NULL,
                             &frame);
    (void)ota_ble_demux_feed(&demux, OTA_BLE_SYNC1, text_collect, NULL,
                             &frame);
    for (i = 2u; i < (uint32_t)wire_len; ++i)
    {
        result = ota_ble_demux_feed(&demux, wire[i], text_collect, NULL,
                                    &frame);
        if (result == OTA_BLE_PARSE_FRAME)
        {
            frame_seen = 1;
        }
    }
    check("A5 A5 5A leaks exactly one A5 to text and still parses the frame",
          frame_seen && text_len == 1u && text_out[0] == OTA_BLE_SYNC0);

    /* 误触发的 A5 5A + 非法 cmd：两字节被吞为帧尝试，文本通道无损继续 */
    text_len = 0u;
    ota_ble_demux_init(&demux);
    (void)ota_ble_demux_feed(&demux, OTA_BLE_SYNC0, text_collect, NULL,
                             &frame);
    (void)ota_ble_demux_feed(&demux, OTA_BLE_SYNC1, text_collect, NULL,
                             &frame);
    result = ota_ble_demux_feed(&demux, 0x77u, text_collect, NULL, &frame);
    (void)ota_ble_demux_feed(&demux, (uint8_t)'Z', text_collect, NULL, &frame);
    check("a false A5 5A start recovers and text resumes",
          result == OTA_BLE_PARSE_ERR_FRAME && text_len == 1u &&
              text_out[0] == 'Z');

    /* text_sink = NULL（会话活跃期语义）：非帧字节静默丢弃，帧照常出 */
    text_len = 0u;
    frame_seen = 0;
    ota_ble_demux_init(&demux);
    (void)ota_ble_demux_feed(&demux, (uint8_t)'#', NULL, NULL, &frame);
    for (i = 0u; i < (uint32_t)wire_len; ++i)
    {
        result = ota_ble_demux_feed(&demux, wire[i], NULL, NULL, &frame);
        if (result == OTA_BLE_PARSE_FRAME)
        {
            frame_seen = 1;
        }
    }
    check("a NULL sink drops text bytes without affecting frames",
          frame_seen && text_len == 0u);
}

static void test_ring(void)
{
    uint8_t buf[8];
    ota_ble_ring_t ring;
    uint8_t byte;
    uint32_t i;
    int ok = 1;
    int pushed;

    ota_ble_ring_init(&ring, buf, 7u);
    check("ring rejects a non-power-of-two size",
          ring.buf == NULL && ring.size == 0u);
    check("push on a disarmed ring returns 0",
          ota_ble_ring_push_isr(&ring, 1u) == 0);
    check("pop on a disarmed ring returns 0",
          ota_ble_ring_pop(&ring, &byte) == 0);
    check("count on a disarmed ring is 0",
          ota_ble_ring_count(&ring) == 0u);
    check("push on a NULL ring returns 0",
          ota_ble_ring_push_isr(NULL, 1u) == 0);
    check("pop on a NULL ring returns 0",
          ota_ble_ring_pop(NULL, &byte) == 0);

    ota_ble_ring_init(&ring, buf, 8u);
    for (i = 0u; i < 7u; ++i)
    {
        pushed = ota_ble_ring_push_isr(&ring, (uint8_t)i);
        if (pushed != 1)
        {
            ok = 0;
        }
    }
    check("ring accepts size-1 bytes without loss",
          ok && ota_ble_ring_count(&ring) == 7u && ring.dropped == 0u);
    check("a full ring drops the newest byte and counts it",
          ota_ble_ring_push_isr(&ring, 0xEEu) == 0 && ring.dropped == 1u &&
              ota_ble_ring_count(&ring) == 7u);

    ok = 1;
    for (i = 0u; i < 7u; ++i)
    {
        if (ota_ble_ring_pop(&ring, &byte) != 1 || byte != (uint8_t)i)
        {
            ok = 0;
        }
    }
    check("drained bytes keep FIFO order",
          ok && ota_ble_ring_count(&ring) == 0u);
    check("an empty ring pops nothing and keeps the drop counter",
          ota_ble_ring_pop(&ring, &byte) == 0 && ring.dropped == 1u);

    /* 回绕后 FIFO 依然成立 */
    ok = 1;
    for (i = 0u; i < 20u; ++i)
    {
        (void)ota_ble_ring_push_isr(&ring, (uint8_t)(i + 1u));
        if (ota_ble_ring_pop(&ring, &byte) != 1 || byte != (uint8_t)(i + 1u))
        {
            ok = 0;
        }
    }
    check("wrap-around push/pop keeps FIFO order", ok);
}

int main(void)
{
    printf("=== P3-1 BLE frame and ring tests ===\n");
    test_crc16_vectors();
    test_encode_parse_roundtrip();
    test_encode_guards();
    test_parser_error_paths();
    test_parser_resync_after_noise();
    test_demux_text_and_binary();
    test_ring();
    printf("=== summary: %d checks, %d failure(s) ===\n", checks, failures);
    if (failures == 0)
    {
        printf("P3_1_BLE_FRAME=PASS checks=%d failures=0\n", checks);
    }
    return failures == 0 ? 0 : 1;
}
