/*
 * P2-5 App 自检健康门宿主测试（TEST_BOOT→CONFIRMED 判据）。
 *
 * 覆盖（对应卡内宿主测试要求 7）：
 *   - 30 秒前不确认、无 hal_ready 不确认、loop 数不足不确认、
 *     wdt 未配置不确认、未喂狗不确认；
 *   - 全部条件满足后才 ready；
 *   - Boot WDT 经 HAL_Init 重配置后仍被识别，错误元组不放行；
 *   - CONFIRMED 已存时由调用方幂等（本模块只判据，幂等由 HAL 层）；
 *   - CONFIRMED 提交失败按受控间隔重试（retry_ok 时序）。
 */
#include "OTA/ota_confirm_health.h"
#include "EEPROM/eeprom_bcb.h"

#include <stdio.h>

static int checks;
static int failures;

static void check(const char* name, int condition)
{
    checks++;
    if(!condition)
    {
        failures++;
        fprintf(stderr, "FAIL: %s\n", name);
    }
}

static void exercise(ota_confirm_health_t* h, uint32_t now_ms)
{
    /* 模拟主循环：每 10ms 一次迭代 */
    ota_confirm_health_tick(h, now_ms);
}

static void t_confirm_health(void)
{
    ota_confirm_health_t h;
    uint32_t t;

    ota_confirm_health_init(&h, 0u);

    /* 初始：未 ready */
    check("C0 not ready at start", !ota_confirm_health_ready(&h, 0u, 1));

    /* 提前 29s，仅循环跑满 3000 次，无 hal_ready：不 ready */
    t = 0u;
    for(t = 10u; t < 29000u; t += 10u)
    {
        exercise(&h, t);
        ota_confirm_health_feed(&h);
    }
    check("C1 not ready before 30s", !ota_confirm_health_ready(&h, t, 1));

    /* 到达 30s 但缺 hal_ready：不 ready */
    check("C2 not ready without hal_ready",
          !ota_confirm_health_ready(&h, 30000u, 1));

    /* hal_ready 置位后，wdt 未配置：不 ready */
    ota_confirm_health_mark_hal_ready(&h);
    check("C3 not ready without wdt configured",
          !ota_confirm_health_ready(&h, 30000u, 0));

    /* wdt 配置已给：ready（loop+feed 已满足） */
    check("C4 ready when all met", ota_confirm_health_ready(&h, 30000u, 1));

    /* loop 不足：30s 已过但只 tick 很少次 → 不 ready */
    {
        ota_confirm_health_t h2;
        ota_confirm_health_init(&h2, 0u);
        ota_confirm_health_mark_hal_ready(&h2);
        exercise(&h2, 30000u);            /* 只一次迭代 */
        ota_confirm_health_feed(&h2);
        check("C5 not ready with too few loops",
              !ota_confirm_health_ready(&h2, 30000u, 1));
    }

    /* 30s 后满足条件，但还没喂过狗 → 不 ready */
    {
        ota_confirm_health_t h3;
        ota_confirm_health_init(&h3, 0u);
        ota_confirm_health_mark_hal_ready(&h3);
        for(t = 10u; t <= 30000u; t += 10u)
        {
            exercise(&h3, t);
        }
        check("C6 not ready without feed",
              !ota_confirm_health_ready(&h3, 30000u, 1));
    }

    /* retry_ok 时序：初始可重试；attempt 后 retry_ms 内不可重试，过后可 */
    check("C7 retry ok before attempt",
          ota_confirm_health_retry_ok(&h, 30000u));
    ota_confirm_health_mark_attempt(&h, 30000u);
    check("C8 retry blocked inside interval",
          !ota_confirm_health_retry_ok(&h, 30000u + 500u));
    check("C9 retry ok after interval",
          ota_confirm_health_retry_ok(&h, 30000u + 1500u));
}

/* C10/C11 真实 main() 调用顺序回归（阻断 1）：
 * 生产编排 = main(): ota_confirm_health_init(millis()) → setup()[HAL 全初始化
 * → mark_hal_ready] → 主循环 tick。
 * 因此 init 必须先于 mark_hal_ready；若反序（mark 后再 init），hal_ready 被清零，
 * TEST_BOOT 永远无法确认——必须回归锁死该顺序。 */
static void t_real_ordering(void)
{
    ota_confirm_health_t h;

    /* 正确顺序：init → (HAL init 耗时) → mark_hal_ready → 主循环 30s + 喂狗 */
    {
        uint32_t t;
        ota_confirm_health_init(&h, 100u);
        for(t = 110u; t < 25000u; t += 10u)
        {
            ota_confirm_health_tick(&h, t);   /* HAL init 期也 tick（不喂狗） */
        }
        ota_confirm_health_mark_hal_ready(&h);   /* setup() 结尾 */
        for(t = 25010u; t <= 30200u; t += 10u)
        {
            ota_confirm_health_tick(&h, t);
            ota_confirm_health_feed(&h);
        }
        /* start=100，30200-100=30100 >= 30000 窗口成立 */
        check("C10 all-met after real order",
              ota_confirm_health_ready(&h, 30200u, 1) == 1);
    }

    /* 反序回归：mark_hal_ready 之后再 init 会把 hal_ready 清零，
     * 任何时候都不应就绪（本 bug 曾导致 TEST_BOOT 永不确认）。 */
    {
        uint32_t t;
        ota_confirm_health_init(&h, 100u);
        ota_confirm_health_mark_hal_ready(&h);
        ota_confirm_health_init(&h, 200u);      /* main() 中后置 init = bug */
        for(t = 210u; t <= 30000u; t += 10u)
        {
            ota_confirm_health_tick(&h, t);
            ota_confirm_health_feed(&h);
        }
        check("C11 reversed order never ready",
              !ota_confirm_health_ready(&h, 30000u, 1));
    }
}

/* C12 确认后持续喂狗语义（阻断 2）：WDT 由 boot 起动后，即使确认动作
 * 已完成，TEST_BOOT 状态仍应每圈喂狗（feed_count 持续增长），直到复位。
 * 健康门本身不持有确认完成状态，只保证 feed 计数增长与 ready 判据解耦。 */
static void t_feed_after_confirmed(void)
{
    ota_confirm_health_t h;

    ota_confirm_health_init(&h, 0u);
    ota_confirm_health_mark_hal_ready(&h);
    for(uint32_t t = 10u; t <= 30000u; t += 10u)
    {
        ota_confirm_health_tick(&h, t);
        ota_confirm_health_feed(&h);   /* 确认前每圈喂狗 */
    }
    check("C12 ready before confirm",
          ota_confirm_health_ready(&h, 30000u, 1));

    /* 模拟确认已完成后继续运行：循环照常 tick + feed，计数继续增长 */
    {
        uint32_t before = h.feed_count;
        uint32_t t;
        for(t = 30010u; t <= 33000u; t += 10u)
        {
            ota_confirm_health_tick(&h, t);
            ota_confirm_health_feed(&h);
        }
        check("C12 feed continues after confirmed", h.feed_count > before);
    }
}

/* C14 真实寄存器转换回归：Boot 先写 DIV_256/1561，随后 HAL_Init 的
 * WDG_Init(10000) 选择 DIV_128 并写 reload=3124。两者都表示同一个已启动
 * IWDG；旧实现只接受前者，导致 TEST_BOOT 健康门在 HAL 初始化后永久关闭。 */
static void t_watchdog_config_transition(void)
{
    uint32_t div_code = 6u;
    uint32_t reload = 1561u;

    check("C14 boot WDT tuple accepted",
          ota_confirm_watchdog_config_matches(div_code, reload, 10000u));

    div_code = 5u;
    reload = 3124u;
    check("C14 HAL-reconfigured WDT tuple accepted",
          ota_confirm_watchdog_config_matches(div_code, reload, 10000u));

    check("C14 reset-default tuple rejected",
          !ota_confirm_watchdog_config_matches(0u, 0x0FFFu, 10000u));
    check("C14 adjacent App reload rejected",
          !ota_confirm_watchdog_config_matches(5u, 3123u, 10000u));
    check("C14 wrong App divider rejected",
          !ota_confirm_watchdog_config_matches(4u, 3124u, 10000u));
    check("C14 App tuple rejected when App WDT disabled",
          !ota_confirm_watchdog_config_matches(5u, 3124u, 0u));
    check("C14 Boot tuple accepted when App WDT disabled",
          ota_confirm_watchdog_config_matches(6u, 1561u, 0u));
}

/* C13 跨 OTA_ConfirmUpdate() 编排的确认后喂狗回归（独立验收 F1 打回后补）。
 *
 * 缺陷回顾：OTA_ConfirmUpdate() 在确认成功的同一圈把 g_ota_state_snapshot 改写为
 * CONFIRMED，且 OTA_SnapshotState() 有快照缓存，此后 state==TEST_BOOT 恒假；
 * 若喂狗只在该分支内，则确认后不再喂狗，约 9990ms（WDT reload=1561/DIV_256/
 * LICK 40kHz）后被 IWDG 复位。
 *
 * 修复（方案 2）：喂狗提到状态判断之外——只要 wdt_configured 为真就每圈喂狗，
 * g_ota_confirm_done 只门控"是否再发起确认"。本回归把 main.cpp 的 OTA_ConfirmUpdate()
 * 控制流逐行照抄（HAL:: 换成计数器/可控状态），以真实 ota_confirm_health_* 判定
 * "确认成功后任意一个 WDT 超时周期窗口内喂狗次数必须 > 0"。 */
#define C13_WDT_RELOAD   1561u
#define C13_WDT_DIV      256u
#define C13_LICK_HZ      40000u
#define C13_WDT_TIMEOUT_MS ((C13_WDT_RELOAD * C13_WDT_DIV * 1000u) / C13_LICK_HZ)

static void t_feed_after_confirm_through_orchestration(void)
{
    ota_confirm_health_t g_ota_health;
    int g_ota_confirm_done;
    int g_ota_state_snapped;
    unsigned char g_ota_state_snapshot;
    unsigned char fake_bcb_state;
    unsigned long feed_count;
    unsigned long last_feed_ms;
    int confirmed_once;
    unsigned long g_now;
    unsigned long feeds_at_confirm;

    /* 本地 HAL 替身（与验收探针语义一致） */
    fake_bcb_state = BCB_STATE_TEST_BOOT;
    feed_count = 0u;
    last_feed_ms = 0u;
    confirmed_once = 0;

    /* main.cpp 编排（照抄修复后的 OTA_ConfirmUpdate） */
    {
        unsigned char hal_bcb_state(void)
        {
            return fake_bcb_state;
        }
        int hal_wdt_configured(void)
        {
            /* HAL_Init 已把 Boot tuple 改为 App tuple，修复后仍应识别。 */
            return ota_confirm_watchdog_config_matches(5u, 3124u, 10000u);
        }
        void hal_feed(void)
        {
            feed_count++;
            last_feed_ms = g_now;
        }
        int hal_confirm_boot(void)
        {
            /* 真实 HAL 成功提交 CONFIRMED 后返回 true（仅首圈置位） */
            if(!confirmed_once)
            {
                confirmed_once = 1;
            }
            return 1;
        }
        unsigned char snapshot_state(void)
        {
            if(g_ota_state_snapped)
            {
                return g_ota_state_snapshot;
            }
            g_ota_state_snapshot = hal_bcb_state();
            g_ota_state_snapped = 1;
            return g_ota_state_snapshot;
        }
        void confirm_update(void)
        {
            uint32_t now;
            unsigned char state;
            int wdt_configured;

            now = (uint32_t)g_now;
            state = snapshot_state();
            ota_confirm_health_tick(&g_ota_health, now);
            wdt_configured = hal_wdt_configured();

            /* 修复后：喂狗在状态判断之外，只要 WDT 被配置就每圈喂 */
            if(wdt_configured)
            {
                hal_feed();
                ota_confirm_health_feed(&g_ota_health);
            }

            if(state == BCB_STATE_TEST_BOOT)
            {
                if(g_ota_confirm_done)
                {
                    return;
                }
                if(!ota_confirm_health_ready(&g_ota_health, now,
                                             wdt_configured))
                {
                    return;
                }
                if(!ota_confirm_health_retry_ok(&g_ota_health, now))
                {
                    return;
                }
                ota_confirm_health_mark_attempt(&g_ota_health, now);
                g_ota_confirm_done = hal_confirm_boot();
                if(g_ota_confirm_done &&
                   g_ota_state_snapshot == BCB_STATE_TEST_BOOT)
                {
                    g_ota_state_snapshot = BCB_STATE_CONFIRMED;
                }
                return;
            }

            if(!g_ota_confirm_done)
            {
                g_ota_confirm_done = hal_confirm_boot();
            }
        }

        /* 一轮 TEST_BOOT：10ms/圈跑 90s */
        ota_confirm_health_init(&g_ota_health, 0u);
        g_ota_confirm_done = 0;
        g_ota_state_snapped = 0;
        g_ota_state_snapshot = 0xFFu;
        ota_confirm_health_mark_hal_ready(&g_ota_health);
        feeds_at_confirm = 0u;
        for(g_now = 10u; g_now <= 90000u; g_now += 10u)
        {
            confirm_update();
            if(confirmed_once && feeds_at_confirm == 0u)
            {
                feeds_at_confirm = feed_count;
            }
        }
    }

    check("C13 confirm happened", confirmed_once == 1);
    check("C13 feeds after confirm > 0",
          feed_count - feeds_at_confirm > 0u);
    /* 直白判据：确认后的任意一个 WDT 周期窗口内都应有喂狗，等价于
     * 确认后全程无 ≥ WDT 超时的喂狗静默窗口。 */
    check("C13 feed silence < WDT timeout",
          90000u - last_feed_ms < (unsigned long)C13_WDT_TIMEOUT_MS);
}

int main(void)
{
    checks = 0;
    failures = 0;
    t_confirm_health();
    t_real_ordering();
    t_feed_after_confirmed();
    t_watchdog_config_transition();
    t_feed_after_confirm_through_orchestration();
    printf("P2_5_OTA_CONFIRM_HEALTH checks=%d failures=%d\n",
           checks, failures);
    return failures == 0 ? 0 : 1;
}