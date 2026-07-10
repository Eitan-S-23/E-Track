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
#ifndef __HAL_CONFIG_H
#define __HAL_CONFIG_H

/*=========================
   Hardware Configuration
 *=========================*/

#  define CONFIG_EEPROM_ENABLE  1

/* Sensors */
#define CONFIG_SENSOR_ENABLE        1

#if CONFIG_SENSOR_ENABLE
#  define CONFIG_SENSOR_IMU_ENABLE  1
#  define CONFIG_SENSOR_MAG_ENABLE  1
#endif

#define NULL_PIN                    PD0

/* Screen */
#define CONFIG_SCREEN_CS_PIN        PB0
#define CONFIG_SCREEN_DC_PIN        PA4
#define CONFIG_SCREEN_RST_PIN       PB11
#define CONFIG_SCREEN_SCK_PIN       PA5
#define CONFIG_SCREEN_MOSI_PIN      PA7
#define CONFIG_SCREEN_BLK_PIN       PB10  // TIM2
#define CONFIG_SCREEN_SPI           SPI

#define CONFIG_SCREEN_HOR_RES       240
#define CONFIG_SCREEN_VER_RES       320

/* Touch */
#define CONFIG_TOUCH_CS_PIN        PB12
#define CONFIG_TOUCH_IRQ_PIN       PC6
#define CONFIG_TOUCH_MISO_PIN      PB14
#define CONFIG_TOUCH_SCK_PIN       PB13
#define CONFIG_TOUCH_MOSI_PIN      PB15
#define CONFIG_TOUCH_SPI           SPI_2

/* Battery */
#define CONFIG_BAT_DET_PIN          PA0
#define CONFIG_BAT_CHG_DET_PIN      PH2

/* Buzzer */
#define CONFIG_BUZZ_PIN             PC7  // TIM3

/* GPS */
#define CONFIG_GPS_SERIAL           Serial2
#define CONFIG_GPS_USE_TRANSPARENT  0
#define CONFIG_GPS_BUF_OVERLOAD_CHK 0
#define CONFIG_GPS_TX_PIN           PA2
#define CONFIG_GPS_RX_PIN           PA3

/* BT */
#define CONFIG_BT_SERIAL           Serial
#define CONFIG_BT_USE_TRANSPARENT  0
#define CONFIG_BT_BUF_OVERLOAD_CHK 0
#define CONFIG_BT_TX_PIN           PA9
#define CONFIG_BT_RX_PIN           PA10
//#define CONFIG_BT_EN_PIN           PA15

/* IMU */
#define CONFIG_IMU_INT1_PIN         PB10
#define CONFIG_IMU_INT2_PIN         PB11

/* I2C */
#define CONFIG_MCU_SDA_PIN          PB7
#define CONFIG_MCU_SDL_PIN          PB6

/* Encoder */
#define CONFIG_ENCODER_B_PIN        PB5
#define CONFIG_ENCODER_A_PIN        PB4
#define CONFIG_ENCODER_PUSH_PIN     PA15
#define CONFIG_KEY_LONG_PRESS       1000

/* Power */
#define CONFIG_POWER_EN_PIN         PD2
#define CONFIG_POWER_WAIT_TIME      1000
#define CONFIG_POWER_SHUTDOWM_DELAY 5000
#define CONFIG_POWER_BATT_CHG_DET_PULLUP    true

/* Debug USART */
#ifndef CONFIG_DEBUG_SERIAL_ENABLE
#  define CONFIG_DEBUG_SERIAL_ENABLE 1
#endif

#ifndef CONFIG_DEBUG_RTT_ENABLE
#  define CONFIG_DEBUG_RTT_ENABLE    1
#endif

#ifndef CONFIG_HARDFAULT_AUTO_REBOOT
#  define CONFIG_HARDFAULT_AUTO_REBOOT 0
#endif

#ifndef CONFIG_HARDFAULT_DUMP_DISPLAY
#  define CONFIG_HARDFAULT_DUMP_DISPLAY 0
#endif

#if CONFIG_DEBUG_RTT_ENABLE
#ifdef __cplusplus
#include "Stream.h"
#include "SEGGER_RTT.h"

class HAL_RTT_Stream : public Stream
{
public:
    void begin(uint32_t baudRate)
    {
        (void)baudRate;
        SEGGER_RTT_Init();
        SEGGER_RTT_SetFlagsUpBuffer(0, SEGGER_RTT_MODE_NO_BLOCK_TRIM);
        SEGGER_RTT_SetFlagsDownBuffer(0, SEGGER_RTT_MODE_NO_BLOCK_SKIP);
    }

    void end(void) {}

    virtual int available(void)
    {
        return (int)SEGGER_RTT_HasData(0);
    }

    virtual int peek(void)
    {
        return -1;
    }

    virtual int read(void)
    {
        return SEGGER_RTT_GetKey();
    }

    virtual void flush(void) {}

    virtual size_t write(uint8_t ch)
    {
        return (size_t)SEGGER_RTT_Write(0, &ch, 1);
    }

    virtual size_t write(const uint8_t *buffer, size_t size)
    {
        return (size_t)SEGGER_RTT_Write(0, buffer, (unsigned)size);
    }

    using Print::write;

    operator bool()
    {
        return true;
    }
};

extern HAL_RTT_Stream RTTSerial;
#endif
#endif

#define CONFIG_DEBUG_SERIAL         Serial5
#define CONFIG_DEBUG_RX_PIN         PB8
#define CONFIG_DEBUG_TX_PIN         PB9

/* SD CARD - Using SDIO Interface */
// SDIO pins are hardcoded in at32_sdio.c:
// PC0  - D0
// PC1  - D1
// PC2 - D2
// PC3 - D3
// PC4 - CLK
// PC5  - CMD
#define CONFIG_SD_CD_PIN            PA8  // Card Detect Pin (active low)

// Legacy SPI pin definitions (not used with SDIO)
// #define CONFIG_SD_SPI               SPI_2
// #define CONFIG_SD_MOSI_PIN          PB15
// #define CONFIG_SD_MISO_PIN          PB14
// #define CONFIG_SD_SCK_PIN           PB13
// #define CONFIG_SD_CS_PIN            PB12

/* HAL Interrupt Update Timer */
#define CONFIG_HAL_UPDATE_TIM       TIM4

/* Show Stack & Heap Info */
#define CONFIG_SHOW_STACK_INFO      0
#define CONFIG_SHOW_HEAP_INFO       0

/* Use Watch Dog */
#define CONFIG_WATCH_DOG_ENABLE     1
#if CONFIG_WATCH_DOG_ENABLE
#  define CONFIG_WATCH_DOG_TIMEOUT (10 * 1000) // [ms]
#endif

#endif
