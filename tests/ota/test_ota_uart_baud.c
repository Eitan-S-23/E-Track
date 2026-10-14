#include "ota_uart_baud.h"
#include <stdio.h>

static unsigned checks, failures;
#define CHECK(condition) do { \
    ++checks; \
    if (!(condition)) { ++failures; printf("UART_BAUD_FAIL line=%d\n", __LINE__); } \
} while (0)

int main(void)
{
    static const uint32_t rates[] = {115200u, 230400u, 460800u, 921600u};
    static const uint32_t words[] = {0x5034fa05u, 0x5034f906u, 0x5034f807u, 0x5034f708u};
    static const uint32_t invalid_rates[] = {0u, 1u, 9600u, 57600u, 115201u, 1000000u, 0xffffffffu};
    unsigned i, bit, slot;

    for (i = 0; i < sizeof(rates) / sizeof(rates[0]); ++i) {
        CHECK(p34_baud_word(rates[i]) == words[i]);
        CHECK(p34_baud_from_word(words[i]) == rates[i]);
        CHECK(p34_baud_from_word(p34_baud_word(rates[i])) == rates[i]);
        for (bit = 0; bit < 32; ++bit) {
            CHECK(p34_baud_from_word(words[i] ^ ((uint32_t)1u << bit)) == 0u);
        }
    }
    for (slot = 0; slot < 256; ++slot) {
        uint32_t word = P34_BAUD_WORD_MAGIC | ((slot ^ 0xffu) << 8) | slot;
        uint32_t expected = slot >= 5u && slot <= 8u ? rates[slot - 5u] : 0u;
        CHECK(p34_baud_from_word(word) == expected);
    }
    for (i = 0; i < sizeof(invalid_rates) / sizeof(invalid_rates[0]); ++i) {
        CHECK(p34_baud_word(invalid_rates[i]) == 0u);
    }
    CHECK(p34_baud_from_word(0u) == 0u);
    CHECK(p34_baud_from_word(0xffffffffu) == 0u);
    printf("UART_BAUD_CHECKS=%u failures=%u\n", checks, failures);
    return failures != 0u;
}
