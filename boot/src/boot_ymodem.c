#include "boot_ymodem.h"

#include <string.h>

enum
{
    YMODEM_SOH = 0x01,
    YMODEM_STX = 0x02,
    YMODEM_EOT = 0x04,
    YMODEM_ACK = 0x06,
    YMODEM_NAK = 0x15,
    YMODEM_CAN = 0x18,
    YMODEM_CRC_REQUEST = 0x43,
    YMODEM_PAD = 0x1A,
    YMODEM_BLOCK_128 = 128,
    YMODEM_BLOCK_1K = 1024,
    YMODEM_MAX_RETRIES = 16,
    YMODEM_BYTE_TIMEOUT_MS = 1000,
    YMODEM_PACKET_TIMEOUT_MS = 3000
};

typedef struct
{
    uint8_t sequence;
    size_t data_len;
    uint8_t data[YMODEM_BLOCK_1K];
} ymodem_packet_t;

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

static int read_byte(const boot_ymodem_io_t *io, uint8_t *byte, uint32_t timeout_ms)
{
    return io->getc(io->ctx, byte, timeout_ms);
}

static boot_ymodem_result_t read_packet(const boot_ymodem_io_t *io,
                                        uint8_t first,
                                        ymodem_packet_t *packet)
{
    uint8_t sequence;
    uint8_t inverse;
    uint8_t crc_hi;
    uint8_t crc_lo;
    uint16_t expected_crc;
    uint16_t actual_crc;
    size_t i;

    packet->data_len = first == YMODEM_SOH ? YMODEM_BLOCK_128 : YMODEM_BLOCK_1K;
    if (first != YMODEM_SOH && first != YMODEM_STX)
    {
        return BOOT_YMODEM_ERR_PROTOCOL;
    }
    if (read_byte(io, &sequence, YMODEM_BYTE_TIMEOUT_MS) != 0 ||
        read_byte(io, &inverse, YMODEM_BYTE_TIMEOUT_MS) != 0)
    {
        return BOOT_YMODEM_ERR_TIMEOUT;
    }
    if ((uint8_t)(sequence + inverse) != 0xFFu)
    {
        return BOOT_YMODEM_ERR_SEQUENCE;
    }

    for (i = 0u; i < packet->data_len; ++i)
    {
        if (read_byte(io, packet->data + i, YMODEM_BYTE_TIMEOUT_MS) != 0)
        {
            return BOOT_YMODEM_ERR_TIMEOUT;
        }
    }
    if (read_byte(io, &crc_hi, YMODEM_BYTE_TIMEOUT_MS) != 0 ||
        read_byte(io, &crc_lo, YMODEM_BYTE_TIMEOUT_MS) != 0)
    {
        return BOOT_YMODEM_ERR_TIMEOUT;
    }

    expected_crc = ((uint16_t)crc_hi << 8) | crc_lo;
    actual_crc = crc16_xmodem(packet->data, packet->data_len);
    if (expected_crc != actual_crc)
    {
        return BOOT_YMODEM_ERR_CRC;
    }
    packet->sequence = sequence;
    return BOOT_YMODEM_OK;
}

static int parse_file_header(const uint8_t *data,
                             size_t len,
                             char name[64],
                             uint32_t *size)
{
    size_t name_len = 0u;
    size_t pos;
    uint32_t value = 0u;
    int digits = 0;

    while (name_len < len && data[name_len] != 0u)
    {
        if (name_len + 1u >= 64u)
        {
            return -1;
        }
        name[name_len] = (char)data[name_len];
        ++name_len;
    }
    if (name_len == len || name_len == 0u)
    {
        return -1;
    }
    name[name_len] = '\0';

    pos = name_len + 1u;
    while (pos < len && data[pos] == ' ')
    {
        ++pos;
    }
    while (pos < len && data[pos] >= '0' && data[pos] <= '9')
    {
        uint32_t digit = (uint32_t)(data[pos] - '0');
        if (value > (0xFFFFFFFFu - digit) / 10u)
        {
            return -1;
        }
        value = value * 10u + digit;
        digits = 1;
        ++pos;
    }
    if (!digits || value == 0u)
    {
        return -1;
    }
    *size = value;
    return 0;
}

static void cancel_transfer(const boot_ymodem_io_t *io)
{
    io->putc(io->ctx, YMODEM_CAN);
    io->putc(io->ctx, YMODEM_CAN);
}

boot_ymodem_result_t boot_ymodem_receive(const boot_ymodem_io_t *io,
                                         const boot_ymodem_sink_t *sink)
{
    ymodem_packet_t packet;
    char file_name[64];
    uint32_t total_size = 0u;
    uint32_t remaining = 0u;
    uint8_t expected_sequence = 1u;
    uint8_t first = 0u;
    unsigned retries;
    int sink_started = 0;
    boot_ymodem_result_t result = BOOT_YMODEM_ERR_TIMEOUT;

    if (io == NULL || io->getc == NULL || io->putc == NULL ||
        sink == NULL || sink->begin == NULL || sink->write == NULL ||
        sink->end == NULL)
    {
        return BOOT_YMODEM_ERR_ARGUMENT;
    }

    for (retries = 0u; retries < YMODEM_MAX_RETRIES; ++retries)
    {
        io->putc(io->ctx, YMODEM_CRC_REQUEST);
        if (read_byte(io, &first, YMODEM_PACKET_TIMEOUT_MS) == 0)
        {
            break;
        }
    }
    if (retries == YMODEM_MAX_RETRIES)
    {
        return BOOT_YMODEM_ERR_TIMEOUT;
    }
    if (first == YMODEM_CAN)
    {
        return BOOT_YMODEM_ERR_CANCELLED;
    }

    result = read_packet(io, first, &packet);
    if (result != BOOT_YMODEM_OK || packet.sequence != 0u)
    {
        cancel_transfer(io);
        return result == BOOT_YMODEM_OK ? BOOT_YMODEM_ERR_SEQUENCE : result;
    }
    if (parse_file_header(packet.data, packet.data_len, file_name, &total_size) != 0)
    {
        cancel_transfer(io);
        return BOOT_YMODEM_ERR_FILE_SIZE;
    }
    if (sink->begin(sink->ctx, file_name, total_size) != 0)
    {
        cancel_transfer(io);
        return BOOT_YMODEM_ERR_SINK;
    }
    sink_started = 1;
    remaining = total_size;
    io->putc(io->ctx, YMODEM_ACK);
    io->putc(io->ctx, YMODEM_CRC_REQUEST);

    retries = 0u;
    while (retries < YMODEM_MAX_RETRIES)
    {
        if (read_byte(io, &first, YMODEM_PACKET_TIMEOUT_MS) != 0)
        {
            io->putc(io->ctx, YMODEM_NAK);
            ++retries;
            continue;
        }
        if (first == YMODEM_CAN)
        {
            result = BOOT_YMODEM_ERR_CANCELLED;
            goto fail;
        }
        if (first == YMODEM_EOT)
        {
            uint8_t second;
            if (remaining != 0u)
            {
                result = BOOT_YMODEM_ERR_FILE_SIZE;
                goto fail;
            }
            io->putc(io->ctx, YMODEM_NAK);
            if (read_byte(io, &second, YMODEM_PACKET_TIMEOUT_MS) != 0 ||
                second != YMODEM_EOT)
            {
                result = BOOT_YMODEM_ERR_PROTOCOL;
                goto fail;
            }
            io->putc(io->ctx, YMODEM_ACK);
            io->putc(io->ctx, YMODEM_CRC_REQUEST);

            if (read_byte(io, &first, YMODEM_PACKET_TIMEOUT_MS) != 0)
            {
                result = BOOT_YMODEM_ERR_TIMEOUT;
                goto fail;
            }
            result = read_packet(io, first, &packet);
            if (result != BOOT_YMODEM_OK || packet.sequence != 0u ||
                packet.data[0] != 0u)
            {
                result = result == BOOT_YMODEM_OK ? BOOT_YMODEM_ERR_PROTOCOL : result;
                goto fail;
            }
            if (sink->end(sink->ctx) != 0)
            {
                result = BOOT_YMODEM_ERR_SINK;
                goto fail;
            }
            io->putc(io->ctx, YMODEM_ACK);
            return BOOT_YMODEM_OK;
        }

        result = read_packet(io, first, &packet);
        if (result != BOOT_YMODEM_OK)
        {
            io->putc(io->ctx, YMODEM_NAK);
            ++retries;
            continue;
        }
        if (packet.sequence == (uint8_t)(expected_sequence - 1u))
        {
            io->putc(io->ctx, YMODEM_ACK);
            continue;
        }
        if (packet.sequence != expected_sequence)
        {
            io->putc(io->ctx, YMODEM_NAK);
            result = BOOT_YMODEM_ERR_SEQUENCE;
            ++retries;
            continue;
        }

        {
            size_t accepted = packet.data_len;
            if (accepted > remaining)
            {
                accepted = remaining;
            }
            if (accepted == 0u || sink->write(sink->ctx, packet.data, accepted) != 0)
            {
                result = accepted == 0u ? BOOT_YMODEM_ERR_FILE_SIZE
                                        : BOOT_YMODEM_ERR_SINK;
                goto fail;
            }
            remaining -= (uint32_t)accepted;
        }
        ++expected_sequence;
        retries = 0u;
        io->putc(io->ctx, YMODEM_ACK);
    }

    result = BOOT_YMODEM_ERR_TIMEOUT;

fail:
    if (sink_started && sink->abort != NULL)
    {
        sink->abort(sink->ctx);
    }
    cancel_transfer(io);
    return result;
}

const char *boot_ymodem_result_name(boot_ymodem_result_t result)
{
    static const char *const names[] = {
        "ok",
        "argument",
        "timeout",
        "cancelled",
        "protocol",
        "sequence",
        "crc",
        "file_size",
        "sink"
    };

    if ((unsigned)result >= sizeof(names) / sizeof(names[0]))
    {
        return "unknown";
    }
    return names[result];
}
