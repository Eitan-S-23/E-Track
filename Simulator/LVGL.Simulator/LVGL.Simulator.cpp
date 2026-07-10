/*
 * PROJECT:   LVGL ported to Windows Desktop
 * FILE:      LVGL.Windows.Desktop.cpp
 * PURPOSE:   Implementation for LVGL ported to Windows Desktop
 *
 * LICENSE:   The MIT License
 *
 * DEVELOPER: Mouri_Naruto (Mouri_Naruto AT Outlook.com)
 */

#include <Windows.h>
#include <stdio.h>
#include <assert.h>
#include "resource.h"
#include "App.h"
#include "Common/HAL/HAL.h"

#if _MSC_VER >= 1200
 // Disable compilation warnings.
#pragma warning(push)
// nonstandard extension used : bit field types other than int
#pragma warning(disable:4214)
// 'conversion' conversion from 'type1' to 'type2', possible loss of data
#pragma warning(disable:4244)
#endif

#include "lvgl/lvgl.h"
#include "lvgl/examples/lv_examples.h"
#include "lv_drivers/win32drv/win32drv.h"
#include "lv_fs_if/lv_fs_if.h"

#if _MSC_VER >= 1200
// Restore compilation warnings.
#pragma warning(pop)
#endif

#define SCREEN_HOR_RES  240
#define SCREEN_VER_RES  320

#include <stdio.h>
#include <stdint.h>
#include <string.h>

static volatile LONG g_main_loop_tick = 0;

static void SetSimulatorWorkingDirectory()
{
    char path[MAX_PATH];
    DWORD len = GetModuleFileNameA(NULL, path, sizeof(path));
    if (len == 0 || len >= sizeof(path))
    {
        return;
    }

    char* slash = strrchr(path, '\\');
    if (slash == NULL)
    {
        return;
    }
    *slash = '\0';

    SetCurrentDirectoryA(path);
}

static DWORD WINAPI SimulatorWatchdogThread(LPVOID)
{
    while (!lv_win32_quit_signal)
    {
        Sleep(1000);
        LONG last = g_main_loop_tick;
        if (last != 0 && GetTickCount() - (DWORD)last > 30000U)
        {
            TerminateProcess(GetCurrentProcess(), 0xE0000001);
        }
    }
    return 0;
}

int main()
{
    SetSimulatorWorkingDirectory();
    SetPriorityClass(GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS);
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_BELOW_NORMAL);

    lv_init();

    lv_fs_if_init();

    if (!lv_win32_init(
        GetModuleHandleW(NULL),
        SW_HIDE,
        SCREEN_HOR_RES,
        SCREEN_VER_RES,
        LoadIconW(GetModuleHandleW(NULL), MAKEINTRESOURCE(IDI_LVGL))))
    {
        return -1;
    }

    lv_win32_add_all_input_devices_to_group(NULL);

    HAL::HAL_Init();  

    App_Init();

    for (int i = 0; i < 20 && !lv_win32_quit_signal; i++)
    {
        lv_win32_poll_events();
        lv_timer_handler();
        HAL::HAL_Update();
        Sleep(16);
    }
    lv_win32_show_window(SW_SHOWNOACTIVATE);

    InterlockedExchange(&g_main_loop_tick, (LONG)GetTickCount());
    HANDLE watchdog = CreateThread(NULL, 0, SimulatorWatchdogThread, NULL, 0, NULL);
    if (watchdog)
    {
        CloseHandle(watchdog);
    }

    while (!lv_win32_quit_signal)
    {
        InterlockedExchange(&g_main_loop_tick, (LONG)GetTickCount());
        lv_win32_poll_events();
        uint32_t next_ms = lv_timer_handler();
        HAL::HAL_Update();
        InterlockedExchange(&g_main_loop_tick, (LONG)GetTickCount());
        if (next_ms < 5)
        {
            next_ms = 5;
        }
        else if (next_ms > 16)
        {
            next_ms = 16;
        }
        Sleep(next_ms);
    }

    App_Uninit();

    return 0;
}
