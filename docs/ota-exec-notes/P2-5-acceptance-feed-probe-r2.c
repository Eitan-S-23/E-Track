/* P2-5 独立验收探针（第 2 轮，F1 整改后复验）
 *
 * 用途：把整改后 USER/main.cpp 的 OTA_SnapshotState()/OTA_ConfirmUpdate() 控制流
 * 逐行照抄到宿主，仅把 HAL:: 调用换成计数器/可控替身，链接真实
 * Libraries/OTA/ota_confirm_health.c，验证 F1（确认成功后喂狗停止）是否真已关闭。
 *
 * 与第 1 轮探针 P2-5-acceptance-feed-probe.c 的关系：第 1 轮照抄的是缺陷版控制流，
 * 保留原样作为负对照（仍应 FAIL），本文件照抄修复版（应 PASS）。
 *
 * 判据（与第 1 轮一致，不放松）：
 *   1) 确认成功后喂狗次数 > 0；
 *   2) 全程无 >= WDT 超时（9990ms）的喂狗静默窗口；
 *   3) 补充：确认后每个 WDT 周期窗口逐窗检查，而非只看首尾。
 *
 * 构建：
 *   gcc -std=c99 -Wall -Wextra -O2 -ILibraries -Iboot/include \
 *       docs/ota-exec-notes/P2-5-acceptance-feed-probe-r2.c \
 *       Libraries/OTA/ota_confirm_health.c -o .cache/feed_probe_r2.exe
 */
#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "OTA/ota_confirm_health.h"

/* boot/platform/at32/boot_platform_at32.c: WDT_CLK_DIV_256 + reload 1561, LICK 40kHz */
#define WDT_RELOAD      1561u
#define WDT_DIV         256u
#define LICK_HZ         40000u
#define WDT_TIMEOUT_MS  ((WDT_RELOAD * WDT_DIV * 1000u) / LICK_HZ)

/* EEPROM/eeprom_bcb.h 中的状态编码 */
#define BCB_STATE_CONFIRMED   1u
#define BCB_STATE_TEST_BOOT   4u

#define TICK_MS      10u
#define RUN_MS       90000u

/* ---- HAL 替身（对应 USER/HAL/HAL_EEPROM.cpp） ---- */
static uint8_t  hal_bcb_state = BCB_STATE_TEST_BOOT;
static int      hal_wdt_configured = 1;   /* boot 起动参数保持在 WDT 寄存器中 */
static unsigned long feed_count;
static unsigned long last_feed_ms;
static unsigned long now_ms;
static int      confirm_ok;               /* HAL::OTA_ConfirmBoot() 返回值 */
static unsigned long confirmed_at_ms;
static unsigned long feeds_at_confirm;
static int      confirmed_seen;

static uint8_t HAL_OTA_GetBcbState(void)      { return hal_bcb_state; }
static int     HAL_OTA_WatchdogIsConfigured(void) { return hal_wdt_configured; }
static void    HAL_OTA_WatchdogFeed(void)
{
    feed_count++;
    last_feed_ms = now_ms;
}
static int     HAL_OTA_ConfirmBoot(void)
{
    if(confirm_ok && !confirmed_seen)
    {
        confirmed_seen = 1;
        confirmed_at_ms = now_ms;
        feeds_at_confirm = feed_count;
        hal_bcb_state = BCB_STATE_CONFIRMED;   /* 真实 HAL 已把 BCB 提交为 CONFIRMED */
    }
    return confirm_ok;
}

/* ---- 照抄 USER/main.cpp（OTA_TARGET_APP 段） ---- */
static ota_confirm_health_t g_ota_health;
static int      g_ota_confirm_done;
static int      g_ota_state_snapped;
static uint8_t  g_ota_state_snapshot;

static uint8_t OTA_SnapshotState(void)
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
    uint32_t now;
    uint8_t state;
    int wdt_configured;

    now = (uint32_t)now_ms;
    state = OTA_SnapshotState();
    ota_confirm_health_tick(&g_ota_health, now);
    wdt_configured = HAL_OTA_WatchdogIsConfigured();

    if(wdt_configured)
    {
        HAL_OTA_WatchdogFeed();
        ota_confirm_health_feed(&g_ota_health);
    }

    if(state == BCB_STATE_TEST_BOOT)
    {
        if(g_ota_confirm_done)
        {
            return;
        }
        if(!ota_confirm_health_ready(&g_ota_health, now, wdt_configured))
        {
            return;
        }
        if(!ota_confirm_health_retry_ok(&g_ota_health, now))
        {
            return;
        }
        ota_confirm_health_mark_attempt(&g_ota_health, now);
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

/* ---- 逐窗检查：确认后每个 WDT 周期窗口内必须至少喂狗一次 ---- */
static unsigned long max_gap_after_confirm;

static void run_case(const char *name, int confirm_boot_ok, int expect_confirm,
                     int *failures)
{
    unsigned long prev_feed_ms;
    unsigned long gap;

    memset(&g_ota_health, 0, sizeof(g_ota_health));
    g_ota_confirm_done = 0;
    g_ota_state_snapped = 0;
    g_ota_state_snapshot = 0xFFu;
    hal_bcb_state = BCB_STATE_TEST_BOOT;
    hal_wdt_configured = 1;
    feed_count = 0u;
    last_feed_ms = 0u;
    confirm_ok = confirm_boot_ok;
    confirmed_seen = 0;
    confirmed_at_ms = 0u;
    feeds_at_confirm = 0u;
    max_gap_after_confirm = 0u;

    ota_confirm_health_init(&g_ota_health, 0u);
    ota_confirm_health_mark_hal_ready(&g_ota_health);

    prev_feed_ms = 0u;
    for(now_ms = TICK_MS; now_ms <= RUN_MS; now_ms += TICK_MS)
    {
        unsigned long feeds_before = feed_count;
        OTA_ConfirmUpdate();
        if(feed_count > feeds_before)
        {
            if(confirmed_seen && now_ms > confirmed_at_ms)
            {
                gap = now_ms - prev_feed_ms;
                if(gap > max_gap_after_confirm) { max_gap_after_confirm = gap; }
            }
            prev_feed_ms = now_ms;
        }
    }
    if(confirmed_seen)
    {
        gap = RUN_MS - last_feed_ms;
        if(gap > max_gap_after_confirm) { max_gap_after_confirm = gap; }
    }

    printf("[%s]\n", name);
    printf("  confirmed=%d confirmed_at_ms=%lu\n", confirmed_seen, confirmed_at_ms);
    printf("  feeds_total=%lu feeds_at_confirm=%lu feeds_after_confirm=%lu\n",
           feed_count, feeds_at_confirm, feed_count - feeds_at_confirm);
    printf("  last_feed_ms=%lu run_end_ms=%lu silence_after_last_feed_ms=%lu\n",
           last_feed_ms, (unsigned long)RUN_MS, RUN_MS - last_feed_ms);
    printf("  max_feed_gap_after_confirm_ms=%lu (WDT timeout=%u)\n",
           max_gap_after_confirm, (unsigned)WDT_TIMEOUT_MS);

    if(confirmed_seen != expect_confirm)
    {
        printf("  FAIL: confirm expectation mismatch (expect=%d actual=%d)\n",
               expect_confirm, confirmed_seen);
        (*failures)++;
        return;
    }
    if(expect_confirm && feed_count - feeds_at_confirm == 0u)
    {
        printf("  FAIL: no watchdog feed after confirm\n");
        (*failures)++;
    }
    if(RUN_MS - last_feed_ms >= (unsigned long)WDT_TIMEOUT_MS)
    {
        printf("  FAIL: trailing feed silence >= WDT timeout\n");
        (*failures)++;
    }
    if(max_gap_after_confirm >= (unsigned long)WDT_TIMEOUT_MS)
    {
        printf("  FAIL: a feed gap after confirm >= WDT timeout\n");
        (*failures)++;
    }
}

int main(void)
{
    int failures = 0;

    printf("WDT_TIMEOUT_MS=%u\n", (unsigned)WDT_TIMEOUT_MS);
    run_case("A: TEST_BOOT, confirm succeeds", 1, 1, &failures);
    /* 边界：确认一直失败（健康门可用但 BCB 写失败），喂狗同样不得停 */
    run_case("B: TEST_BOOT, confirm always fails", 0, 0, &failures);

    printf("P2_5_FEED_PROBE_R2=%s failures=%d\n",
           failures == 0 ? "PASS" : "FAIL", failures);
    return failures == 0 ? 0 : 1;
}
