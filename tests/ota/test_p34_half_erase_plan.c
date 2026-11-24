#include "OTA/ota_half_erase_plan.h"
#include <stdio.h>
#include <stdlib.h>

static unsigned checks;
#define CHECK(x) do { ++checks; if (!(x)) { \
    fprintf(stderr, "HALF_ERASE_PLAN_FAIL line=%d\n", __LINE__); exit(1); \
} } while (0)

int main(void)
{
    uint32_t start, length;
    unsigned block, half;
    for (block = 0; block <= 1; ++block)
    for (half = 0; half <= 1; ++half)
    {
        CHECK(ota_erase_next_size_mixed(0, 0, block, half) == 0);
        CHECK(ota_erase_next_size_mixed(1, 4096, block, half) == 0);
        CHECK(ota_erase_next_size_mixed(0, 4095, block, half) == 0);
        CHECK(ota_erase_next_size_mixed(0xfffff000u, 4096, block, half) == 0);
        CHECK(ota_erase_next_size_mixed(0x8000u, 0x7000u, block, half) == 4096);
        for (start = 0; start < 2 * OTA_ERASE_BLOCK_SIZE; start += 4096)
        for (length = 4096; length <= OTA_APP_LENGTH; length += 4096)
        {
            uint32_t cursor = start;
            while (cursor < start + length)
            {
                uint32_t remaining = start + length - cursor;
                uint32_t step = ota_erase_next_size_mixed(cursor, remaining, block, half);
                CHECK(step == 4096 || step == 32768 || step == 65536);
                CHECK(step <= remaining && cursor % step == 0);
                CHECK(block || step != 65536);
                CHECK(half || step != 32768);
                if (!half) CHECK(step == ota_erase_next_size(cursor, remaining, block));
                if (block && cursor % 65536 == 0 && remaining >= 65536) CHECK(step == 65536);
                cursor += step;
            }
            CHECK(cursor == start + length);
        }
        {
            uint32_t cursor = 4096;
            unsigned commands = 1, blocks = 0, halves = 0;
            while (cursor < 622592u)
            {
                uint32_t step = ota_erase_next_size_mixed(cursor, 622592u - cursor, block, half);
                ++commands;
                blocks += step == 65536;
                halves += step == 32768;
                cursor += step;
            }
            CHECK(commands == (block ? (half ? 18u : 32u) : (half ? 26u : 152u)));
            CHECK(blocks == (block ? 8u : 0u));
            CHECK(halves == (half ? (block ? 2u : 18u) : 0u));
        }
    }
    printf("HALF_ERASE_PLAN_PASS checks=%u\n", checks);
    return 0;
}
