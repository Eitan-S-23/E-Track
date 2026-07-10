#include "HAL.h"

void HAL::HAL_Init()
{
    Buzz_init();
    Audio_Init();
    GPS_Init();
}

void HAL::HAL_Update()
{
    IMU_Update();
    MAG_Update();
    Audio_Update();
}

/**
 * @brief  Check if USB is connected and configured by host
 * @retval true if USB is connected and configured, false otherwise
 * @note   This does NOT use VBUS detection (PA9 not connected)
 *         Instead, it checks if USB enumeration is complete
 */
bool HAL::USB_IsPlugged(void)
{
    /* Check if USB device is in CONFIGURED state
     * This means USB is connected to host and enumeration is complete */
    return true;
}

bool HAL::USB_IsMassStorageOnSD(void)
{
    /* 模拟器无 USB MSC：返回 false，使 LiveMap/PM_Router 走正常分支（显示地图、不弹 U 盘提示） */
    return false;
}

bool HAL::BT_IsConnected()
{
    return false;
}
