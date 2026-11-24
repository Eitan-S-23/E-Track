#include <stdint.h>
#include <stdio.h>

typedef struct { uint32_t marker; } tmr_type;
typedef void (*Timer_CallbackFunction_t)(void);

static uint32_t clock_hz = 288000000u;
static unsigned calls;
static tmr_type *last_timer;
static Timer_CallbackFunction_t last_callback;
static uint16_t last_period, last_prescaler;
static uint8_t last_preemption, last_subpriority;

static uint32_t Timer_GetClockMax(tmr_type *timer)
{
    (void)timer;
    return clock_hz;
}

static void Timer_SetInterruptBase(tmr_type *timer, uint16_t period,
    uint16_t prescaler, Timer_CallbackFunction_t callback,
    uint8_t preemption, uint8_t subpriority)
{
    ++calls;
    last_timer = timer;
    last_callback = callback;
    last_period = period;
    last_prescaler = prescaler;
    last_preemption = preemption;
    last_subpriority = subpriority;
}

#include "timer_config_under_test.inc"

static void callback(void) {}

#define CHECK(value) do { ++checks; if (!(value)) { \
    ++failures; printf("FAIL line=%u: %s\n", (unsigned)__LINE__, #value); \
} } while (0)

int main(void)
{
    tmr_type timer = {4u};
    unsigned checks = 0u, failures = 0u;
    const uint32_t clocks[] = {288000000u, 96000000u};
    unsigned i;
    for (i = 0; i < sizeof(clocks) / sizeof(clocks[0]); ++i)
    {
        uint16_t period, prescaler;
        clock_hz = clocks[i];
        calls = 0u;
        Timer_SetInterrupt(&timer, 10000u, callback);
        CHECK(calls == 1u);
        CHECK(last_timer == &timer && last_callback == callback);
        CHECK(last_preemption == TIMER_PREEMPTIONPRIORITY_DEFAULT);
        CHECK(last_subpriority == TIMER_SUBPRIORITY_DEFAULT);
        CHECK((uint32_t)last_period * last_prescaler == clock_hz / 100u);
        period = last_period;
        prescaler = last_prescaler;
        Timer_SetInterruptWithPriority(&timer, 10000u, callback, 2u, 0u);
        CHECK(calls == 2u);
        CHECK(last_timer == &timer && last_callback == callback);
        CHECK(last_preemption == 2u && last_subpriority == 0u);
        CHECK(last_period == period && last_prescaler == prescaler);
        Timer_SetInterruptWithPriority(&timer, 10000u, callback, 3u, 1u);
        CHECK(last_preemption == 3u && last_subpriority == 1u);
        CHECK(last_period == period && last_prescaler == prescaler);
        calls = 0u;
        Timer_SetInterrupt(&timer, 0u, callback);
        Timer_SetInterruptWithPriority(&timer, 0u, callback, 2u, 0u);
        CHECK(calls == 0u);
    }
    printf("TIMER_PRIORITY checks=%u failures=%u\n", checks, failures);
    return failures ? 1 : 0;
}
