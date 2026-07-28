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

enum
{
    OTA_CONFIRM_DELAY_MS = 30000,
    OTA_CONFIRM_RETRY_MS = 1000
};

static uint32_t g_ota_confirm_start_ms;
static uint32_t g_ota_confirm_last_attempt_ms;
static bool g_ota_confirm_done;

static void OTA_ConfirmUpdate()
{
    uint32_t now;

    if(g_ota_confirm_done)
    {
        return;
    }
    now = millis();
    if((uint32_t)(now - g_ota_confirm_start_ms) < OTA_CONFIRM_DELAY_MS ||
       (uint32_t)(now - g_ota_confirm_last_attempt_ms) < OTA_CONFIRM_RETRY_MS)
    {
        return;
    }
    g_ota_confirm_last_attempt_ms = now;
    g_ota_confirm_done = HAL::OTA_ConfirmBoot();
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
    setup();
#if defined(OTA_TARGET_APP)
    g_ota_confirm_start_ms = millis();
    g_ota_confirm_last_attempt_ms = g_ota_confirm_start_ms;
    g_ota_confirm_done = false;
#endif
    for(;;)loop();
}
