/*
 * P2-5 独立验收探针（非实现会话 / 2026-08-03）——阻断 2「确认后喂狗」核查。
 *
 * 目的：宿主测试 C12 只对 ota_confirm_health_* 直接调用 feed 并断言 feed_count
 * 增长，未经过 USER/main.cpp 的 OTA_ConfirmUpdate() 编排。本探针把 main.cpp
 * 的控制流逐行照抄（仅把 HAL:: 调用换成计数器与可控状态），以验证
 * 「TEST_BOOT 期间每圈喂狗，且确认完成后仍持续喂狗直到复位」是否真的成立。
 *
 * 判据：确认动作发生后，若在一个 WDT 超时周期（boot reload=1561 /
 * WDT_CLK_DIV_256 / LICK 40kHz ⇒ 约 9990ms）内喂狗次数为 0，则独立看门狗会
 * 复位设备，阻断 2 未关闭。
 */
#include "OTA/ota_confirm_health.h"
#include "EEPROM/eeprom_bcb.h"

#include <stdio.h>

/* boot 起动 TEST_BOOT 看门狗的参数（HAL_EEPROM.cpp:121-122 实读） */
#define WDT_RELOAD        1561u
#define WDT_DIV           256u
#define LICK_HZ           40000u
#define WDT_TIMEOUT_MS    ((WDT_RELOAD * WDT_DIV * 1000u) / LICK_HZ)

/* ---- main.cpp 状态变量（照抄） ---- */
static ota_confirm_health_t g_ota_health;
static int  g_ota_confirm_done;
static int  g_ota_state_snapped;
static unsigned char g_ota_state_snapshot;

/* ---- HAL 替身 ---- */
static unsigned char fake_bcb_state;       /* OTA_GetBcbState() 返回值 */
static unsigned long feed_count;           /* OTA_WatchdogFeed() 次数 */
static unsigned long last_feed_ms;         /* 最近一次喂狗时刻 */
static unsigned long confirm_ms;           /* 确认成功时刻 */
static int  confirmed_once;

static unsigned char HAL_OTA_GetBcbState(void) { return fake_bcb_state; }
static int  HAL_OTA_WatchdogIsConfigured(void) { return 1; }

static unsigned long g_now;
static void HAL_OTA_WatchdogFeed(void)
{
    feed_count++;
    last_feed_ms = g_now;
}
static int HAL_OTA_ConfirmBoot(void)
{
    /* 真实 HAL 成功提交 CONFIRMED 后返回 true */
    if(!confirmed_once)
    {
        confirmed_once = 1;
        confirm_ms = g_now;
    }
    return 1;
}

/* ---- USER/main.cpp:38-100 逐行照抄（HAL:: → 替身） ---- */
static unsigned char OTA_SnapshotState(void)
{
    if(g_ota_state_snapped)
    {
        return g_ota_state_snapshot;
    }
    g_ota_state_snapshot = HAL_OTA_GetBcbState();
    g_ota_state_snapped = 1;
    return g_ota_state_snapshot;
}

static void OTA_ConfirmUpdate(void)
{
    unsigned long now;
    unsigned char state;

    now = g_now;
    state = OTA_SnapshotState();
    ota_confirm_health_tick(&g_ota_health, (uint32_t)now);

    if(state == BCB_STATE_TEST_BOOT)
    {
        HAL_OTA_WatchdogFeed();
        ota_confirm_health_feed(&g_ota_health);
        if(g_ota_confirm_done)
        {
            return;
        }
        if(!ota_confirm_health_ready(&g_ota_health, (uint32_t)now,
                                     HAL_OTA_WatchdogIsConfigured()))
        {
            return;
        }
        if(!ota_confirm_health_retry_ok(&g_ota_health, (uint32_t)now))
        {
            return;
        }
        ota_confirm_health_mark_attempt(&g_ota_health, (uint32_t)now);
        g_ota_confirm_done = HAL_OTA_ConfirmBoot();
        if(g_ota_confirm_done && g_ota_state_snapshot == BCB_STATE_TEST_BOOT)
        {
            g_ota_state_snapshot = BCB_STATE_CONFIRMED;
        }
        return;
    }

    if(!g_ota_confirm_done)
    {
        g_ota_confirm_done = HAL_OTA_ConfirmBoot();
    }
}

int main(void)
{
    unsigned long feeds_at_confirm = 0u;
    int failures = 0;

    /* 真机 TEST_BOOT 一轮：boot 交接后 App 以 10ms/圈跑 90s */
    fake_bcb_state = BCB_STATE_TEST_BOOT;
    ota_confirm_health_init(&g_ota_health, 0u);
    g_ota_confirm_done = 0;
    g_ota_state_snapped = 0;
    g_ota_state_snapshot = 0xFFu;
    ota_confirm_health_mark_hal_ready(&g_ota_health);   /* setup() 结尾 */

    for(g_now = 10u; g_now <= 90000u; g_now += 10u)
    {
        OTA_ConfirmUpdate();
        if(confirmed_once && feeds_at_confirm == 0u)
        {
            feeds_at_confirm = feed_count;
        }
    }

    printf("WDT_TIMEOUT_MS=%lu\n", (unsigned long)WDT_TIMEOUT_MS);
    printf("confirmed_at_ms=%lu\n", confirm_ms);
    printf("feeds_total=%lu feeds_at_confirm=%lu\n",
           feed_count, feeds_at_confirm);
    printf("feeds_after_confirm=%lu\n", feed_count - feeds_at_confirm);
    printf("last_feed_ms=%lu run_end_ms=90000\n", last_feed_ms);
    printf("silence_after_last_feed_ms=%lu\n", 90000u - last_feed_ms);

    if(!confirmed_once)
    {
        printf("FAIL: confirm never happened\n");
        failures++;
    }
    /* 判据：确认后必须持续喂狗；一个 WDT 周期内 0 次喂狗 = 会被看门狗复位 */
    if(feed_count - feeds_at_confirm == 0u)
    {
        printf("FAIL: no watchdog feed after confirm -> IWDG resets at ~%lums\n",
               confirm_ms + (unsigned long)WDT_TIMEOUT_MS);
        failures++;
    }
    if(90000u - last_feed_ms >= (unsigned long)WDT_TIMEOUT_MS)
    {
        printf("FAIL: feed silence %lums >= WDT timeout %lums\n",
               90000u - last_feed_ms, (unsigned long)WDT_TIMEOUT_MS);
        failures++;
    }

    printf("P2_5_FEED_PROBE=%s failures=%d\n",
           failures == 0 ? "PASS" : "FAIL", failures);
    return failures == 0 ? 0 : 1;
}
