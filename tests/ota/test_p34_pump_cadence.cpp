#include "HAL/ota_pump_cadence.h"
#include "MillisTaskManager.h"
#include <stdio.h>
#include <stdlib.h>

static unsigned checks, pumps, others;
static void check(bool value)
{
    ++checks;
    if (!value) { fprintf(stderr, "check %u failed\n", checks); exit(1); }
}
static void pump() { ++pumps; }
static void other() { ++others; }

static void run(MillisTaskManager &manager, uint32_t now, bool active)
{
    check(manager.SetIntervalTime(pump, ota_pump_period(active, 20u)));
    manager.Running(now);
}

int main()
{
    const uint32_t fast = CONFIG_OTA_ACTIVE_PUMP ? 2u : 20u;
    check(ota_pump_period(false, 20u) == 20u);
    check(ota_pump_period(true, 20u) == fast);
    check(ota_pump_period(false, 35u) == 35u);
    {
        MillisTaskManager manager;
        manager.Register(pump, 20u);
        manager.Register(other, 10u);
        pumps = others = 0;
        for (uint32_t t = 0; t <= 100; ++t) run(manager, t, false);
        check(pumps == 5 && others == 10);
        for (uint32_t t = 101; t <= 200; ++t) run(manager, t, true);
        check(pumps == 5 + 100 / fast && others == 20);
        for (uint32_t t = 201; t <= 300; ++t) run(manager, t, false);
        check(pumps == 10 + 100 / fast && others == 30);
        unsigned before = pumps;
        run(manager, 300, true);
        run(manager, 300, true);
        check(pumps == before);
        run(manager, 5000, true);
        check(pumps == before + 1);
        run(manager, 5000, true);
        check(pumps == before + 1); // No catch-up storm after a synchronous Flash stall.
        check(manager.Find(other)->Time == 10u);
    }
    {
        MillisTaskManager manager;
        auto *task = manager.Register(pump, 20u);
        task->TimePrev = 0xfffffff0u;
        pumps = 0;
        for (uint32_t t = 0xfffffff1u; t != 0x21u; ++t) run(manager, t, true);
        check(pumps == 48u / fast);
        unsigned before = pumps;
        task->TimePrev = 0xfffffffcu;
        run(manager, 0x0fu, false);
        check(pumps == before);
        run(manager, 0x10u, false);
        check(pumps == before + 1);
    }
    {
        MillisTaskManager manager;
        manager.Register(pump, 20u);
        pumps = 0;
        run(manager, 10, false);
        run(manager, 11, true);
        check(pumps == (CONFIG_OTA_ACTIVE_PUMP ? 1u : 0u));
        manager.SetState(pump, false);
        unsigned before = pumps;
        run(manager, 1000, true);
        check(pumps == before);
        manager.SetState(pump, true);
        run(manager, 1000, true);
        check(pumps == before + 1);
    }
    printf("PUMP_CADENCE=PASS enabled=%d checks=%u\n", CONFIG_OTA_ACTIVE_PUMP, checks);
    return 0;
}
