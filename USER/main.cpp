/*
 * MIT License
 * Copyright (c) 2021 _VIFEXTech
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */
#include "Arduino.h"
#include "App/App.h"
#include "HAL/HAL.h"
#include "lvgl/lvgl.h"
#include "lv_port/lv_port.h"

#if defined(OTA_TARGET_APP)
#include "OTA/ota_vtor_check.h"
#include "HAL/HAL_OTA_Backup.h"
#include "OTA/ota_confirm_health.h"
#include "EEPROM/eeprom_bcb.h"

static ota_confirm_health_t g_ota_health;
static bool g_ota_confirm_done;
static bool g_ota_state_snapped;
static uint8_t g_ota_state_snapshot;

static uint8_t OTA_SnapshotState()
{
    if(g_ota_state_snapped)
    {
        return g_ota_state_snapshot;
    }
    /* 状态只可能经 boot 重启或本侧 CONFIRMED 提交改变，启动后快照一次即可。 */
    g_ota_state_snapshot = HAL::OTA_GetBcbState();
    g_ota_state_snapped = true;
    return g_ota_state_snapshot;
}

static void OTA_ConfirmUpdate()
{
    uint32_t now;
    uint8_t state;
    int wdt_configured;

    now = millis();
    state = OTA_SnapshotState();
    ota_confirm_health_tick(&g_ota_health, now);
    wdt_configured = HAL::OTA_WatchdogIsConfigured();

    /* 阻断 2（独立验收打回 F1）：喂狗必须提到状态判断之外。boot 仅在 TEST_BOOT
     * 交接前起动独立看门狗（Boot reload=1561 / DIV_256 / LICK 40kHz ⇒ 约 9990ms），
     * AT32 IWDG 一经 wdt_enable() 只能由复位清除，本次 App 运行内必须持续喂狗
     * 直到下一个 boot 复位——即使确认成功后快照被改写为 CONFIRMED，state 不再
     * 等于 TEST_BOOT，WDT 仍在跑。因此只要 boot 起动参数仍可读（寄存器保持），
     * 就每圈喂狗，与"WDT 只能复位清除"的物理事实对齐。 */
    if(wdt_configured)
    {
        HAL::OTA_WatchdogFeed();
        ota_confirm_health_feed(&g_ota_health);
    }

    if(state == BCB_STATE_TEST_BOOT)
    {
        /* g_ota_confirm_done 只门控"是否再发起确认"，不控制喂狗（喂狗在上面）。 */
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
        g_ota_confirm_done = HAL::OTA_ConfirmBoot();
        if(g_ota_confirm_done && g_ota_state_snapshot == BCB_STATE_TEST_BOOT)
        {
            g_ota_state_snapshot = BCB_STATE_CONFIRMED;
        }
        return;
    }

    /* 非 TEST_BOOT（常态 CONFIRMED）：无状态转移，幂等确认一次，
     * 维持既有 RTT 行节奏。 */
    if(!g_ota_confirm_done)
    {
        g_ota_confirm_done = HAL::OTA_ConfirmBoot();
    }
}
#endif


#if LV_USE_DEMO_BENCHMARK

#include "benchmark.inc"

#else

static bool PrintResetFlag(const char* name, uint32_t flag)
{
    if(crm_flag_get(flag) != RESET)
    {
        SEGGER_RTT_printf(0, " %s", name);
        return true;
    }

    return false;
}

static void PrintResetReason()
{
    bool hasFlag = false;

    SEGGER_RTT_printf(0, "Reset:");
    hasFlag |= PrintResetFlag("NRST", CRM_NRST_RESET_FLAG);
    hasFlag |= PrintResetFlag("POR", CRM_POR_RESET_FLAG);
    hasFlag |= PrintResetFlag("SW", CRM_SW_RESET_FLAG);
    hasFlag |= PrintResetFlag("WDT", CRM_WDT_RESET_FLAG);
    hasFlag |= PrintResetFlag("WWDT", CRM_WWDT_RESET_FLAG);
    hasFlag |= PrintResetFlag("LOWPWR", CRM_LOWPOWER_RESET_FLAG);

    if(!hasFlag)
    {
        SEGGER_RTT_printf(0, " none");
    }

    SEGGER_RTT_printf(0, "\r\n");
    crm_flag_clear(CRM_ALL_RESET_FLAG);
}

static void setup()
{
    SEGGER_RTT_Init();
    SEGGER_RTT_SetFlagsUpBuffer(0, SEGGER_RTT_MODE_NO_BLOCK_TRIM);
    SEGGER_RTT_printf(0, "\r\n========================================\r\n");
#if defined(OTA_TARGET_APP)
    ota_handoff_report();
#endif
    PrintResetReason();
#if defined(OTA_TARGET_APP) && defined(__GNUC__) && !defined(__CC_ARM)
    /* Match the converted GCC target: HAL display setup starts an LVGL animation. */
    lv_init();
    HAL::HAL_Init();
#else
    HAL::HAL_Init();
    lv_init();
#endif
    lv_port_init();

    App_Init();

    HAL::Power_SetEventCallback(App_Uninit);
    HAL::Memory_DumpInfo();

#if defined(OTA_TARGET_APP)
    ota_confirm_health_mark_hal_ready(&g_ota_health);
#endif
}

static void loop()
{
    HAL::HAL_Update();
    lv_task_handler();
#if defined(OTA_TARGET_APP)
    OTA_ConfirmUpdate();
#endif
    __wfi();
}

#endif

/**
  * @brief  Main Function
  * @param  None
  * @retval None
  */
int main(void)
{
#if defined(OTA_TARGET_APP)
    ota_vtor_check();
    ota_handoff_capture();
#endif
    Core_Init();
#if defined(OTA_TARGET_APP)
    /* 健康门初始化必须先于 setup() 末尾的 mark_hal_ready（阻断 1）：
     * init 把 hal_ready 复位为未就绪，若在 mark 之后才 init，TEST_BOOT
     * 永远无法确认。 */
    ota_confirm_health_init(&g_ota_health, millis());
    g_ota_confirm_done = false;
    g_ota_state_snapped = false;
    g_ota_state_snapshot = 0xFFu;
#endif
    setup();
    for(;;)loop();
}
