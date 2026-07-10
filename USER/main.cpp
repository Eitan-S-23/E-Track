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
    PrintResetReason();
    HAL::HAL_Init();

    lv_init();
    lv_port_init();

    App_Init();

    HAL::Power_SetEventCallback(App_Uninit);
    HAL::Memory_DumpInfo();

}

static void loop()
{
    HAL::HAL_Update();
    lv_task_handler();
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
    Core_Init();
    setup();
    for(;;)loop();
}
