#ifndef E_TRACK_OTA_UART_BAUD_H
#define E_TRACK_OTA_UART_BAUD_H

#include <stdint.h>

#define P34_BAUD_WORD_MAGIC 0x50340000u

/* Retain the existing ERTC_DT20 format; neither reader writes persistent state. */
static inline uint32_t p34_baud_word(uint32_t baud)
{
    uint32_t slot = baud == 115200u ? 5u : baud == 230400u ? 6u :
                    baud == 460800u ? 7u : baud == 921600u ? 8u : 0u;
    return slot == 0u ? 0u : P34_BAUD_WORD_MAGIC | ((slot ^ 0xffu) << 8) | slot;
}

static inline uint32_t p34_baud_from_word(uint32_t word)
{
    uint32_t slot = word & 0xffu;
    uint32_t baud = slot == 5u ? 115200u : slot == 6u ? 230400u :
                    slot == 7u ? 460800u : slot == 8u ? 921600u : 0u;
    return baud != 0u && p34_baud_word(baud) == word ? baud : 0u;
}

#endif
