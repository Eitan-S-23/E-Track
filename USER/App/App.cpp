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
#include "Config/Config.h"
#include "Common/DataProc/DataProc.h"
#include "Resource/ResourcePool.h"
#include "Pages/AppFactory.h"
#include "Pages/StatusBar/StatusBar.h"
#include "Utils/PageManager/PageManager.h"

#if defined(ARDUINO) && CONFIG_RTT_DEBUG_CMD_ENABLE
#include "SEGGER_RTT.h"
#include "Common/HAL/HAL.h"
#include <string.h>
#endif

#define ACCOUNT_SEND_CMD(ACT, CMD) \
do{ \
    DataProc::ACT##_Info_t info; \
    DATA_PROC_INIT_STRUCT(info); \
    info.cmd = DataProc::CMD; \
    DataProc::Center()->AccountMain.Notify(#ACT, &info, sizeof(info)); \
}while(0)

#if defined(ARDUINO) && CONFIG_RTT_DEBUG_CMD_ENABLE
/* RTT 下行调试命令轮询：主机经 J-Link 向 down channel 0 写入行命令
 * （ping / livemap / dialplate / back），实现无人值守的页面控制与
 * 性能测量。命令走白名单，未知命令仅回显不执行。 */
static void RttDebugCmd_Poll(lv_timer_t* timer)
{
    static char line[32];
    static uint32_t lineLen = 0;

    char buf[16];
    unsigned n = SEGGER_RTT_Read(0, buf, sizeof(buf));
    for (unsigned i = 0; i < n; i++)
    {
        char ch = buf[i];
        if (ch == '\n' || ch == '\r')
        {
            if (lineLen == 0)
            {
                continue;
            }
            line[lineLen] = '\0';
            lineLen = 0;

            PageManager* manager = (PageManager*)timer->user_data;
            if (strcmp(line, "ping") == 0)
            {
                SEGGER_RTT_printf(0, "RTTCMD: pong\r\n");
            }
            else if (strcmp(line, "livemap") == 0)
            {
                bool ok = manager->Push("Pages/LiveMap");
                SEGGER_RTT_printf(0, "RTTCMD: livemap ok=%d\r\n", (int)ok);
            }
            else if (strcmp(line, "dialplate") == 0)
            {
                bool ok = manager->Push("Pages/Dialplate");
                SEGGER_RTT_printf(0, "RTTCMD: dialplate ok=%d\r\n", (int)ok);
            }
            else if (strcmp(line, "back") == 0)
            {
                bool ok = manager->Pop();
                SEGGER_RTT_printf(0, "RTTCMD: back ok=%d\r\n", (int)ok);
            }
            else if (strcmp(line, "gpsreset") == 0)
            {
                HAL::GPS_SimulatorResetPosition();
                SEGGER_RTT_printf(0, "RTTCMD: gpsreset ok\r\n");
            }
            else
            {
                SEGGER_RTT_printf(0, "RTTCMD: unknown '%s'\r\n", line);
            }
        }
        else if (lineLen < sizeof(line) - 1)
        {
            line[lineLen++] = ch;
        }
    }
}
#endif

void App_Init()
{
    static AppFactory factory;
    static PageManager manager(&factory);

#if CONFIG_MONKEY_TEST_ENABLE
    lv_monkey_config_t config;
    lv_monkey_config_init(&config);
    config.type = CONFIG_MONKEY_INDEV_TYPE;
    config.period_range.min = CONFIG_MONKEY_PERIOD_MIN;
    config.period_range.max = CONFIG_MONKEY_PERIOD_MAX;
    config.input_range.min = CONFIG_MONKEY_INPUT_RANGE_MIN;
    config.input_range.max = CONFIG_MONKEY_INPUT_RANGE_MAX;
    lv_monkey_t* monkey = lv_monkey_create(&config);
    lv_monkey_set_enable(monkey, true);

    lv_group_t* group = lv_group_create();
    lv_indev_set_group(lv_monkey_get_indev(monkey), group);
    lv_group_set_default(group);

    LV_LOG_USER("lv_monkey test started!");
#endif

    /* Make sure the default group exists */
    if(!lv_group_get_default())
    {
        lv_group_t* group = lv_group_create();
        lv_group_set_default(group);
    }

    /* Initialize the data processing node */
    DataProc_Init();
    ACCOUNT_SEND_CMD(Storage, STORAGE_CMD_LOAD);
    ACCOUNT_SEND_CMD(SysConfig, SYSCONFIG_CMD_LOAD);

    /* Set screen style */
    lv_obj_t* scr = lv_scr_act();
    lv_obj_remove_style_all(scr);
    lv_obj_set_style_bg_opa(lv_scr_act(), LV_OPA_COVER, 0);
    lv_obj_set_style_bg_color(lv_scr_act(), lv_color_black(), 0);
    lv_obj_clear_flag(scr, LV_OBJ_FLAG_SCROLLABLE);
    lv_disp_set_bg_color(lv_disp_get_default(), lv_color_black());

    /* Set root default style */
    static lv_style_t rootStyle;
    lv_style_init(&rootStyle);
    lv_style_set_width(&rootStyle, LV_HOR_RES);
    lv_style_set_height(&rootStyle, LV_VER_RES);
    lv_style_set_bg_opa(&rootStyle, LV_OPA_COVER);
    lv_style_set_bg_color(&rootStyle, lv_color_black());
    manager.SetRootDefaultStyle(&rootStyle);

    /* Initialize resource pool */
    ResourcePool::Init();

    /* Initialize status bar */
    Page::StatusBar_Create(lv_layer_top());

    /* Initialize pages */
    manager.Install("Template",    "Pages/_Template");
    manager.Install("LiveMap",     "Pages/LiveMap");
    manager.Install("Dialplate",   "Pages/Dialplate");
    manager.Install("MainMenu",    "Pages/MainMenu");
    manager.Install("SystemInfos", "Pages/SystemInfos");
    manager.Install("Startup",     "Pages/Startup");
    manager.Install("RouteSelect", "Pages/RouteSelect");
    manager.Install("RouteImport", "Pages/RouteImport");

    manager.SetGlobalLoadAnimType(PageManager::LOAD_ANIM_OVER_LEFT);

    manager.Push("Pages/Startup");

#if defined(ARDUINO) && CONFIG_RTT_DEBUG_CMD_ENABLE
    lv_timer_create(RttDebugCmd_Poll, 100, &manager);
#endif
}

void App_Uninit()
{
    ACCOUNT_SEND_CMD(SysConfig, SYSCONFIG_CMD_SAVE);
    ACCOUNT_SEND_CMD(Storage,   STORAGE_CMD_SAVE);
    ACCOUNT_SEND_CMD(Recorder,  RECORDER_CMD_STOP);
}
