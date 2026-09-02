#include "OTA/ota_ble_ring.h"

#include <stddef.h>

void ota_ble_ring_init(ota_ble_ring_t *ring, uint8_t *buf, uint32_t size)
{
    if (ring == NULL || buf == NULL || size == 0u || (size & (size - 1u)) != 0u)
    {
        if (ring != NULL)
        {
            ring->buf = NULL;
            ring->size = 0u;
            ring->mask = 0u;
            ring->head = 0u;
            ring->tail = 0u;
            ring->dropped = 0u;
        }
        return;
    }

    ring->buf = buf;
    ring->size = size;
    ring->mask = size - 1u;
    ring->head = 0u;
    ring->tail = 0u;
    ring->dropped = 0u;
}

int ota_ble_ring_push_isr(ota_ble_ring_t *ring, uint8_t byte)
{
    uint32_t head;
    uint32_t next;

    if (ring == NULL || ring->buf == NULL)
    {
        return 0;
    }

    head = ring->head;
    next = (head + 1u) & ring->mask;
    if (next == ring->tail)
    {
        /* 环满：丢弃新字节。泵失速（>44ms@921600）才会发生；
         * 丢字节导致该帧 CRC 失败，由发送端重传恢复。 */
        ++ring->dropped;
        return 0;
    }

    ring->buf[head] = byte;
    ring->head = next;
    return 1;
}

int ota_ble_ring_pop(ota_ble_ring_t *ring, uint8_t *out_byte)
{
    uint32_t tail;

    if (ring == NULL || ring->buf == NULL || out_byte == NULL)
    {
        return 0;
    }

    tail = ring->tail;
    if (tail == ring->head)
    {
        return 0;
    }

    *out_byte = ring->buf[tail];
    ring->tail = (tail + 1u) & ring->mask;
    return 1;
}

uint32_t ota_ble_ring_count(const ota_ble_ring_t *ring)
{
    if (ring == NULL || ring->buf == NULL)
    {
        return 0u;
    }

    return (ring->head - ring->tail) & ring->mask;
}
