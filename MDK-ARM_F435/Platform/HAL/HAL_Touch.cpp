#include "HAL/HAL.h"
#include "XPT2046/XPT2046.h"

#define TOUCH_PRESSURE_THRESHOLD  200

static XPT2046 touch(
    CONFIG_TOUCH_CS_PIN,
    CONFIG_TOUCH_IRQ_PIN,
    &CONFIG_TOUCH_SPI
);

static bool touchPressed = false;
static int16_t touchX = 0;
static int16_t touchY = 0;

static int16_t Touch_Constrain(int32_t value, int16_t min, int16_t max)
{
    if (value < min)
    {
        return min;
    }
    if (value > max)
    {
        return max;
    }
    return (int16_t)value;
}

static bool Touch_ReadPoint(int16_t* x, int16_t* y)
{
    if (digitalRead(CONFIG_TOUCH_IRQ_PIN))
    {
        return false;
    }

    uint16_t rawX;
    uint16_t rawY;
    uint16_t pressure;
    touch.read(&rawX, &rawY, &pressure);

    if (digitalRead(CONFIG_TOUCH_IRQ_PIN) || pressure < TOUCH_PRESSURE_THRESHOLD)
    {
        return false;
    }

    /* Existing calibration maps panel axes as 320x240; swap to LVGL's 240x320. */
    int16_t lvX = Touch_Constrain(rawY, 0, CONFIG_SCREEN_HOR_RES - 1);
    int16_t lvY = Touch_Constrain(rawX, 0, CONFIG_SCREEN_VER_RES - 1);

    if (x)
    {
        *x = lvX;
    }
    if (y)
    {
        *y = lvY;
    }

    return true;
}

void HAL::Touch_Init()
{
    CONFIG_DEBUG_SERIAL.printf("Touch: init...%d\r\n", digitalRead(CONFIG_SCREEN_CS_PIN));

    touch.begin(CONFIG_SCREEN_VER_RES, CONFIG_SCREEN_HOR_RES);
    touch.setRotation(0);
    touch.setCalibration(350, 550, 3550, 3600);
}

void HAL::Touch_Update()
{
    Touch_GetPoint(NULL, NULL);
}

bool HAL::Touch_GetPoint(int16_t* x, int16_t* y)
{
    int16_t curX = touchX;
    int16_t curY = touchY;
    touchPressed = Touch_ReadPoint(&curX, &curY);

    if (touchPressed)
    {
        touchX = curX;
        touchY = curY;
    }

    if (x)
    {
        *x = touchX;
    }
    if (y)
    {
        *y = touchY;
    }

    return touchPressed;
}
