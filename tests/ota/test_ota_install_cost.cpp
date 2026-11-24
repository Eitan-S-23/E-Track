#include "HAL/ota_install_cost.h"
#include <stdio.h>
#include <stdlib.h>

static unsigned checks;
#define CHECK(x) do { ++checks; if (!(x)) { \
    fprintf(stderr, "FAIL line %d\n", __LINE__); exit(1); } } while (0)

int main(void)
{
    ota_cost_stats_t s;
    uint32_t rest = 99;
    ota_cost_begin(&s, 100);
    CHECK(ota_cost_finish(&s, 110, &rest) && rest == 10);
    ota_cost_add(&s, OTA_COST_ERASE, 101, 106, 4096, 0);
    ota_cost_add(&s, OTA_COST_PROGRAM, 106, 108, 256, -1);
    CHECK(s.io[OTA_COST_ERASE].calls == 1 && s.io[OTA_COST_ERASE].bytes == 4096);
    CHECK(s.io[OTA_COST_PROGRAM].failures == 1 && s.io[OTA_COST_PROGRAM].ticks == 2);
    CHECK(ota_cost_finish(&s, 110, &rest) && rest == 3);
    ota_cost_add(&s, OTA_COST_PACKAGE_READ, 108, 108, 1024, 0);
    CHECK(s.io[OTA_COST_PACKAGE_READ].calls == 1 && s.io[OTA_COST_PACKAGE_READ].ticks == 0);
    CHECK(ota_cost_finish(&s, 110, &rest) && rest == 3);
    ota_cost_begin(&s, 0xfffffff0u);
    ota_cost_add(&s, OTA_COST_RESTORE, 0xfffffff8u, 8, 0, 0);
    CHECK(s.io[OTA_COST_RESTORE].ticks == 16);
    CHECK(ota_cost_finish(&s, 16, &rest) && rest == 16);
    CHECK(!ota_cost_finish(&s, 0xfffffff1u, &rest));
    ota_cost_begin(&s, 0);
    ota_cost_add(&s, OTA_COST_KINDS, 0, 1, 0, 0);
    CHECK(s.invalid == 1 && !ota_cost_finish(&s, 10, &rest));
    ota_cost_begin(&s, 0);
    s.io[0].calls = UINT32_MAX;
    ota_cost_add(&s, 0, 0, 1, 0, 0);
    CHECK(s.invalid == 1 && s.io[0].calls == UINT32_MAX);
    ota_cost_begin(&s, 0);
    s.io[0].ticks = UINT64_MAX;
    s.io[1].ticks = 1;
    CHECK(!ota_cost_finish(&s, 10, &rest));
    ota_cost_begin(&s, 0);
    for (unsigned i = 0; i < OTA_COST_KINDS; ++i)
        ota_cost_add(&s, i, i, i + 1, i + 1, 0);
    CHECK(ota_cost_finish(&s, 10, &rest) && rest == 10 - OTA_COST_KINDS);
    CHECK(s.invalid == 0);
    printf("INSTALL_COST_PASS checks=%u\n", checks);
    return 0;
}
