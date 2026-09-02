#include "OTA/ota_ble_frame.h"

#include <stddef.h>

uint16_t ota_ble_crc16(const uint8_t *data, size_t len)
{
    uint16_t crc = 0xFFFFu;
    size_t i;
    uint8_t bit;

    /* CRC16-CCITT-FALSE：poly 0x1021、init 0xFFFF、不反射、xorout 0。
     * 逐位实现：921600 波特全速收包约占 0.3% CPU，换取零查表 flash。 */
    for (i = 0u; i < len; ++i)
    {
        crc |= (uint16_t)((uint16_t)data[i] << 8);
        for (bit = 0u; bit < 8u; ++bit)
        {
            if ((crc & 0x8000u) != 0u)
            {
                crc = (uint16_t)((crc << 1) ^ 0x1021u);
            }
            else
            {
                crc = (uint16_t)(crc << 1);
            }
        }
    }
    return crc;
}

size_t ota_ble_frame_encode(uint8_t *dst, size_t cap,
                            uint8_t cmd, uint8_t session, uint16_t seq,
                            const uint8_t *payload, uint16_t len)
{
    uint16_t crc;
    size_t need;
    size_t i;

    if (dst == NULL || len > OTA_BLE_MAX_PAYLOAD ||
        (payload == NULL && len != 0u))
    {
        return 0u;
    }
    need = OTA_BLE_HEADER_SIZE + (size_t)len + OTA_BLE_CRC_SIZE;
    if (cap < need)
    {
        return 0u;
    }

    crc = 0xFFFFu;
    dst[0] = OTA_BLE_SYNC0;
    dst[1] = OTA_BLE_SYNC1;
    dst[2] = cmd;
    dst[3] = session;
    dst[4] = (uint8_t)(seq & 0xFFu);
    dst[5] = (uint8_t)((seq >> 8) & 0xFFu);
    dst[6] = (uint8_t)(len & 0xFFu);
    dst[7] = (uint8_t)((len >> 8) & 0xFFu);
    for (i = 0u; i < (size_t)len; ++i)
    {
        dst[OTA_BLE_HEADER_SIZE + i] = payload[i];
    }

    /* crc16 覆盖 cmd..payload（不含 A5 5A 与自身） */
    crc = ota_ble_crc16(&dst[2], (size_t)len + 6u);
    dst[OTA_BLE_HEADER_SIZE + len] = (uint8_t)(crc & 0xFFu);
    dst[OTA_BLE_HEADER_SIZE + len + 1u] = (uint8_t)((crc >> 8) & 0xFFu);
    return need;
}

/* parser 内部状态：hdr_index 同时充当多字节字段（seq/len/crc）的
 * 子字段计数器，由各状态分支自增。 */
enum
{
    OTA_BLE_PS_SYNC1 = 0,
    OTA_BLE_PS_SYNC2,
    OTA_BLE_PS_CMD,
    OTA_BLE_PS_SESSION,
    OTA_BLE_PS_SEQ,
    OTA_BLE_PS_LEN,
    OTA_BLE_PS_PAYLOAD,
    OTA_BLE_PS_CRC
};

void ota_ble_parser_reset(ota_ble_parser_t *parser)
{
    if (parser == NULL)
    {
        return;
    }
    parser->state = OTA_BLE_PS_SYNC1;
    parser->cmd = 0u;
    parser->session = 0u;
    parser->hdr_index = 0u;
    parser->seq = 0u;
    parser->len = 0u;
    parser->payload_index = 0u;
    parser->crc_rx = 0u;
    parser->crc_calc = 0u;
}

static int ota_ble_cmd_known(uint8_t cmd)
{
    return cmd == OTA_BLE_CMD_GET_INFO || cmd == OTA_BLE_CMD_BEGIN ||
           cmd == OTA_BLE_CMD_DATA || cmd == OTA_BLE_CMD_END ||
           cmd == OTA_BLE_CMD_ABORT;
}

/* cmd 对应的合法 payload 长度域。DATA 为 [4,132]（包尾短段语义由
 * 会话层按 total_len 判定，parser 只做结构性上限）。 */
static int ota_ble_len_accept(uint8_t cmd, uint16_t len)
{
    switch (cmd)
    {
    case OTA_BLE_CMD_GET_INFO:
        return len == OTA_BLE_LEN_GET_INFO;
    case OTA_BLE_CMD_BEGIN:
        return len == OTA_BLE_LEN_BEGIN;
    case OTA_BLE_CMD_END:
        return len == OTA_BLE_LEN_END;
    case OTA_BLE_CMD_ABORT:
        return len == OTA_BLE_LEN_ABORT;
    case OTA_BLE_CMD_DATA:
        return len >= OTA_BLE_LEN_DATA_MIN && len <= OTA_BLE_MAX_PAYLOAD;
    default:
        return 0;
    }
}

static uint16_t ota_ble_crc16_update_byte(uint16_t crc, uint8_t byte)
{
    uint8_t bit;

    crc ^= (uint16_t)((uint16_t)byte << 8);
    for (bit = 0u; bit < 8u; ++bit)
    {
        if ((crc & 0x8000u) != 0u)
        {
            crc = (uint16_t)((crc << 1) ^ 0x1021u);
        }
        else
        {
            crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

ota_ble_parse_result_t ota_ble_parser_feed(ota_ble_parser_t *parser,
                                           uint8_t byte,
                                           ota_ble_frame_t *out_frame)
{
    ota_ble_parse_result_t result = OTA_BLE_PARSE_IDLE;

    if (parser == NULL || out_frame == NULL)
    {
        return OTA_BLE_PARSE_IDLE;
    }

    switch (parser->state)
    {
    case OTA_BLE_PS_SYNC1:
        if (byte == OTA_BLE_SYNC0)
        {
            parser->state = OTA_BLE_PS_SYNC2;
        }
        /* 非 A5 字节静默丢弃（重新同步语义） */
        break;

    case OTA_BLE_PS_SYNC2:
        if (byte == OTA_BLE_SYNC1)
        {
            parser->state = OTA_BLE_PS_CMD;
            parser->crc_calc = 0xFFFFu;
        }
        else if (byte == OTA_BLE_SYNC0)
        {
            /* 连续 A5：保持 SYNC2，等下一个字节（A5 A5 5A 语义） */
        }
        else
        {
            parser->state = OTA_BLE_PS_SYNC1;
        }
        break;

    case OTA_BLE_PS_CMD:
        if (!ota_ble_cmd_known(byte))
        {
            /* 未知 cmd：整帧丢弃。header 尚未解出，echo 字段全零 */
            ++parser->bad_frames;
            out_frame->cmd = 0u;
            out_frame->session = 0u;
            out_frame->seq = 0u;
            out_frame->len = 0u;
            ota_ble_parser_reset(parser);
            result = OTA_BLE_PARSE_ERR_FRAME;
            break;
        }
        parser->cmd = byte;
        parser->crc_calc = ota_ble_crc16_update_byte(parser->crc_calc, byte);
        parser->state = OTA_BLE_PS_SESSION;
        break;

    case OTA_BLE_PS_SESSION:
        parser->session = byte;
        parser->crc_calc = ota_ble_crc16_update_byte(parser->crc_calc, byte);
        parser->state = OTA_BLE_PS_SEQ;
        parser->hdr_index = 0u;
        break;

    case OTA_BLE_PS_SEQ:
        if (parser->hdr_index == 0u)
        {
            parser->seq = byte;
        }
        else
        {
            parser->seq = (uint16_t)(parser->seq | ((uint16_t)byte << 8));
        }
        parser->crc_calc = ota_ble_crc16_update_byte(parser->crc_calc, byte);
        if (++parser->hdr_index >= 2u)
        {
            parser->state = OTA_BLE_PS_LEN;
            parser->hdr_index = 0u;
        }
        break;

    case OTA_BLE_PS_LEN:
        if (parser->hdr_index == 0u)
        {
            parser->len = byte;
        }
        else
        {
            parser->len = (uint16_t)(parser->len | ((uint16_t)byte << 8));
        }
        parser->crc_calc = ota_ble_crc16_update_byte(parser->crc_calc, byte);
        if (++parser->hdr_index >= 2u)
        {
            if (!ota_ble_len_accept(parser->cmd, parser->len))
            {
                ++parser->bad_frames;
                /* 长度非法：整帧丢弃。cmd/seq 已解出，填入 out_frame
                 * 供调用方 NAK 回显（调用方收到 ERR 后 parser 已复位）。 */
                out_frame->cmd = parser->cmd;
                out_frame->session = parser->session;
                out_frame->seq = parser->seq;
                out_frame->len = 0u;
                result = OTA_BLE_PARSE_ERR_FRAME;
                ota_ble_parser_reset(parser);
                break;
            }
            parser->state = (parser->len == 0u) ? OTA_BLE_PS_CRC
                                                : OTA_BLE_PS_PAYLOAD;
            parser->payload_index = 0u;
            parser->hdr_index = 0u;
        }
        break;

    case OTA_BLE_PS_PAYLOAD:
        if (parser->payload_index < parser->len)
        {
            parser->payload[parser->payload_index] = byte;
            ++parser->payload_index;
            parser->crc_calc = ota_ble_crc16_update_byte(parser->crc_calc, byte);
        }
        if (parser->payload_index >= parser->len)
        {
            parser->state = OTA_BLE_PS_CRC;
            parser->hdr_index = 0u;
        }
        break;

    case OTA_BLE_PS_CRC:
        if (parser->hdr_index == 0u)
        {
            parser->crc_rx = byte;
        }
        else
        {
            parser->crc_rx =
                (uint16_t)(parser->crc_rx | ((uint16_t)byte << 8));
        }
        if (++parser->hdr_index >= 2u)
        {
            if (parser->crc_rx == parser->crc_calc)
            {
                out_frame->cmd = parser->cmd;
                out_frame->session = parser->session;
                out_frame->seq = parser->seq;
                out_frame->len = parser->len;
                if (parser->len != 0u)
                {
                    size_t i;
                    for (i = 0u; i < parser->len; ++i)
                    {
                        out_frame->payload[i] = parser->payload[i];
                    }
                }
                result = OTA_BLE_PARSE_FRAME;
                ota_ble_parser_reset(parser);
            }
            else
            {
                ++parser->bad_frames;
                /* CRC 失败：整帧丢弃，header 已完整解出可供 NAK 回显 */
                out_frame->cmd = parser->cmd;
                out_frame->session = parser->session;
                out_frame->seq = parser->seq;
                out_frame->len = 0u;
                result = OTA_BLE_PARSE_ERR_CRC;
                ota_ble_parser_reset(parser);
            }
        }
        break;

    default:
        ota_ble_parser_reset(parser);
        break;
    }

    return result;
}

void ota_ble_demux_init(ota_ble_demux_t *demux)
{
    if (demux == NULL)
    {
        return;
    }
    demux->state = OTA_BLE_DEMUX_IDLE;
    ota_ble_parser_reset(&demux->parser);
}

static void ota_ble_demux_emit_text(ota_ble_text_sink_t sink,
                                    void *ctx, uint8_t byte)
{
    if (sink != NULL)
    {
        sink(ctx, byte);
    }
}

ota_ble_parse_result_t ota_ble_demux_feed(ota_ble_demux_t *demux,
                                          uint8_t byte,
                                          ota_ble_text_sink_t text_sink,
                                          void *text_ctx,
                                          ota_ble_frame_t *out_frame)
{
    ota_ble_parse_result_t result = OTA_BLE_PARSE_IDLE;

    if (demux == NULL || out_frame == NULL)
    {
        return OTA_BLE_PARSE_IDLE;
    }

    switch (demux->state)
    {
    case OTA_BLE_DEMUX_IDLE:
        if (byte == OTA_BLE_SYNC0)
        {
            demux->state = OTA_BLE_DEMUX_SYNC_HOLD;
        }
        else
        {
            ota_ble_demux_emit_text(text_sink, text_ctx, byte);
        }
        break;

    case OTA_BLE_DEMUX_SYNC_HOLD:
        if (byte == OTA_BLE_SYNC1)
        {
            /* A5 5A 确认：同步头喂入 parser 后进入二进制模式 */
            (void)ota_ble_parser_feed(&demux->parser, OTA_BLE_SYNC0,
                                      out_frame);
            result = ota_ble_parser_feed(&demux->parser, OTA_BLE_SYNC1,
                                         out_frame);
            demux->state = OTA_BLE_DEMUX_BINARY;
        }
        else
        {
            /* 误触发：暂存的 A5 归还文本流；当前字节按 IDLE 规则重放 */
            ota_ble_demux_emit_text(text_sink, text_ctx, OTA_BLE_SYNC0);
            if (byte == OTA_BLE_SYNC0)
            {
                demux->state = OTA_BLE_DEMUX_SYNC_HOLD;
            }
            else
            {
                demux->state = OTA_BLE_DEMUX_IDLE;
                ota_ble_demux_emit_text(text_sink, text_ctx, byte);
            }
        }
        break;

    case OTA_BLE_DEMUX_BINARY:
        result = ota_ble_parser_feed(&demux->parser, byte, out_frame);
        if (result != OTA_BLE_PARSE_IDLE)
        {
            /* 帧完成或失败：回到顶层扫描，文本流恢复接收 */
            demux->state = OTA_BLE_DEMUX_IDLE;
        }
        break;

    default:
        demux->state = OTA_BLE_DEMUX_IDLE;
        break;
    }

    return result;
}
