#include "OTA/ota_erase_plan.h"
#include <stdio.h>
#include <stdlib.h>

static unsigned checks;
#define CHECK(x) do { ++checks; if (!(x)) { \
    fprintf(stderr, "ERASE_PLAN_FAIL line=%d\n", __LINE__); exit(1); \
} } while (0)

int main(void)
{
    uint32_t start, length;
    unsigned enabled;
    CHECK(ota_erase_next_size(0, 0, 1) == 0);
    CHECK(ota_erase_next_size(1, 4096, 1) == 0);
    CHECK(ota_erase_next_size(0, 4095, 1) == 0);
    CHECK(ota_erase_next_size(0xfffff000u, 4096, 1) == 0);
    for (enabled = 0; enabled <= 1; ++enabled)
    {
        for (start = 0; start < 2 * OTA_ERASE_BLOCK_SIZE; start += 4096)
        {
            for (length = 4096; length <= OTA_APP_LENGTH; length += 4096)
            {
                uint32_t cursor = start;
                while (cursor < start + length)
                {
                    uint32_t remaining = start + length - cursor;
                    uint32_t step = ota_erase_next_size(cursor, remaining, enabled);
                    CHECK(step == 4096 || step == OTA_ERASE_BLOCK_SIZE);
                    CHECK(step <= remaining && cursor % step == 0);
                    CHECK(enabled || step == 4096);
                    CHECK(!enabled || cursor % OTA_ERASE_BLOCK_SIZE != 0 ||
                          remaining < OTA_ERASE_BLOCK_SIZE || step == OTA_ERASE_BLOCK_SIZE);
                    cursor += step;
                }
                CHECK(cursor == start + length);
            }
        }
    }
    for (enabled = 0; enabled <= 1; ++enabled)
    {
        uint32_t cursor = 4096;
        unsigned commands = 1, blocks = 0;
        while (cursor < 622592u)
        {
            uint32_t step = ota_erase_next_size(cursor, 622592u - cursor, enabled);
            ++commands;
            blocks += step == OTA_ERASE_BLOCK_SIZE;
            cursor += step;
        }
        CHECK(commands == (enabled ? 32u : 152u));
        CHECK(blocks == (enabled ? 8u : 0u));
    }
    printf("ERASE_PLAN_PASS checks=%u\n", checks);
    return 0;
}
