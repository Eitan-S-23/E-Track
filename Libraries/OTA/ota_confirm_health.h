#ifndef E_TRACK_OTA_CONFIRM_HEALTH_H
#define E_TRACK_OTA_CONFIRM_HEALTH_H

/*
 * App 自检健康门（TEST_BOOT→CONFIRMED 前的判据）。
 *
 * 依据 PLAN-OTA.md §4：“[App] 自检过(HAL 全初始化+主循环 30s+IWDG 喂狗正常)
 * →写 BCB=CONFIRMED”。本模块为纯 C 判据，不触碰硬件；硬件侧喂狗/读狗由 HAL
 * 层（HAL::OTA_WatchdogFeed / OTA_WatchdogIsConfigured）注入。只有全部条件
 * 满足才允许调用 ota_confirm_test_boot() 提交 CONFIRMED。
 */

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define OTA_CONFIRM_HEALTH_WINDOW_MS 30000u
#define OTA_CONFIRM_HEALTH_MIN_LOOPS 30u
#define OTA_CONFIRM_HEALTH_RETRY_MS  1000u

typedef struct ota_confirm_health_t
{
    uint32_t window_ms;      /* 健康窗口时长 */
    uint32_t min_loops;      /* 窗口内主循环最小迭代数 */
    uint32_t retry_ms;       /* CONFIRMED 提交失败后的受控重试间隔 */
    uint32_t start_ms;       /* 窗口起点（setup 完成、main 循环启动处） */
    uint32_t loop_count;     /* 主循环已健康迭代次数 */
    uint32_t feed_count;     /* TEST_BOOT 期间已喂狗次数 */
    uint32_t last_attempt_ms;/* 最近一次尝试确认的时间戳 */
    int      start_valid;    /* init 已调用 */
    int      hal_ready;      /* HAL 全初始化完成标志（setup 结尾置位） */
} ota_confirm_health_t;

/* 窗口启动：应在 setup() 完成、进入主循环前调用一次，now_ms 为当前毫秒。 */
void ota_confirm_health_init(ota_confirm_health_t *health,
                             uint32_t now_ms);

/* setup() 全部完成（HAL::HAL_Init、lv_port_init、App_Init 之后）置位。 */
void ota_confirm_health_mark_hal_ready(ota_confirm_health_t *health);

/* 每圈主循环调用一次：健康迭代计数。 */
void ota_confirm_health_tick(ota_confirm_health_t *health,
                             uint32_t now_ms);

/* 每喂一次独立看门狗调用一次（TEST_BOOT 期间）。 */
void ota_confirm_health_feed(ota_confirm_health_t *health);

/* 全部条件满足返回 1：
 *   start_valid && hal_ready &&
 *   (now - start) >= window_ms && loop_count >= min_loops &&
 *   feed_count > 0 && wdt_configured
 * wdt_configured = boot 以 TEST_BOOT 参数起动过独立看门狗（HAL 注入）。 */
int ota_confirm_health_ready(const ota_confirm_health_t *health,
                             uint32_t now_ms,
                             int wdt_configured);

/* 距上次尝试至少 retry_ms（受控重试间隔）。 */
int ota_confirm_health_retry_ok(const ota_confirm_health_t *health,
                                uint32_t now_ms);

/* 在发起确认尝试前调用，记录 last_attempt_ms。 */
void ota_confirm_health_mark_attempt(ota_confirm_health_t *health,
                                     uint32_t now_ms);

#ifdef __cplusplus
}
#endif

#endif /* E_TRACK_OTA_CONFIRM_HEALTH_H */
