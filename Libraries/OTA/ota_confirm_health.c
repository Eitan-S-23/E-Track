/*
 * ota_confirm_health.c —— App 自检健康门判据（纯 C）。
 *
 * 只有当：① setup() 已全量完成（HAL 全初始化）；② 主循环健康运行满窗口
 * （window_ms=30s、迭代 ≥ min_loops）；③ 独立看门狗被 boot 以 TEST_BOOT
 * 参数起动（wdt_configured）且本侧已喂狗 ≥1 次；三者同时成立，才允许进入
 * TEST_BOOT→CONFIRMED 提交。仅依赖毫秒时间差与计数，避免硬编码单调时钟。
 */
#include "OTA/ota_confirm_health.h"

void ota_confirm_health_init(ota_confirm_health_t *health,
                             uint32_t now_ms)
{
    if (health == 0)
    {
        return;
    }
    health->window_ms = OTA_CONFIRM_HEALTH_WINDOW_MS;
    health->min_loops = OTA_CONFIRM_HEALTH_MIN_LOOPS;
    health->retry_ms = OTA_CONFIRM_HEALTH_RETRY_MS;
    health->start_ms = now_ms;
    health->loop_count = 0u;
    health->feed_count = 0u;
    health->last_attempt_ms = 0u;
    health->start_valid = 1;
    health->hal_ready = 0;
}

void ota_confirm_health_mark_hal_ready(ota_confirm_health_t *health)
{
    if (health != 0)
    {
        health->hal_ready = 1;
    }
}

void ota_confirm_health_tick(ota_confirm_health_t *health,
                             uint32_t now_ms)
{
    (void)now_ms;
    if (health != 0)
    {
        health->loop_count++;
    }
}

void ota_confirm_health_feed(ota_confirm_health_t *health)
{
    if (health != 0)
    {
        health->feed_count++;
    }
}

int ota_confirm_health_ready(const ota_confirm_health_t *health,
                             uint32_t now_ms,
                             int wdt_configured)
{
    if (health == 0 || !health->start_valid || !health->hal_ready)
    {
        return 0;
    }
    if ((uint32_t)(now_ms - health->start_ms) < health->window_ms)
    {
        return 0;
    }
    if (health->loop_count < health->min_loops)
    {
        return 0;
    }
    if (health->feed_count == 0u || !wdt_configured)
    {
        return 0;
    }
    return 1;
}

int ota_confirm_health_retry_ok(const ota_confirm_health_t *health,
                                uint32_t now_ms)
{
    if (health == 0 || health->last_attempt_ms == 0u)
    {
        return 1;
    }
    return (uint32_t)(now_ms - health->last_attempt_ms) >=
           health->retry_ms;
}

void ota_confirm_health_mark_attempt(ota_confirm_health_t *health,
                                     uint32_t now_ms)
{
    if (health != 0)
    {
        health->last_attempt_ms = now_ms;
    }
}
