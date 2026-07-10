#include "HAL.h"
#include "App/Version.h"
#include "MillisTaskManager/MillisTaskManager.h"

#if CONFIG_DEBUG_RTT_ENABLE
HAL_RTT_Stream RTTSerial;
#endif

static MillisTaskManager taskManager;

#if CONFIG_SENSOR_ENABLE

static void HAL_Sensor_Init()
{
    if(HAL::I2C_Scan() <= 0)
    {
        CONFIG_DEBUG_SERIAL.println("I2C: disable sensors");
        return;
    }

#if CONFIG_SENSOR_IMU_ENABLE
    if(HAL::IMU_Init())
    {
        taskManager.Register(HAL::IMU_Update, 1000);
    }
#endif

#if CONFIG_SENSOR_MAG_ENABLE
    if(HAL::MAG_Init())
    {
        taskManager.Register(HAL::MAG_Update, 1000);
    }
#endif
}

#endif

static void HAL_TimerInterrputUpdate()
{
    HAL::Power_Update();
    HAL::Encoder_Update();
    HAL::Audio_Update();
}

void HAL::HAL_Init()
{
    CONFIG_DEBUG_SERIAL.begin(115200);
    CONFIG_DEBUG_SERIAL.println(VERSION_FIRMWARE_NAME);
    CONFIG_DEBUG_SERIAL.println("Version: " VERSION_SOFTWARE);
    CONFIG_DEBUG_SERIAL.println("Author: "  VERSION_AUTHOR_NAME);
    CONFIG_DEBUG_SERIAL.println("Project: " VERSION_PROJECT_LINK);

    FaultHandle_Init();

    Memory_DumpInfo();

    Power_Init();
    Backlight_Init();
    Encoder_Init();
    Clock_Init();
    Buzz_init();
    GPS_Init();
	BT_Init();
#if CONFIG_SENSOR_ENABLE
    HAL_Sensor_Init();
#endif

#if CONFIG_EEPROM_ENABLE
    EEPROM_Init();
#endif
//	EEPROM_Write(0,1);
//	delay_ms(50);
//	EEPROM_Write(100,0x20);
//	delay_ms(5);
//	EEPROM_Write(1,10);
//	delay_ms(10);
	u8 buf;
	EEPROM_Read(0, &buf, 1);
	CONFIG_DEBUG_SERIAL.printf("EEPROM_Read: %d\r\n", buf);
	BT_printf("%d\r\n",buf);
	EEPROM_Read(100, &buf, 1);
	CONFIG_DEBUG_SERIAL.printf("EEPROM_Read: %d\r\n", buf);
	BT_printf("%d\r\n",buf);
	EEPROM_Read(1, &buf, 1);
	CONFIG_DEBUG_SERIAL.printf("EEPROM_Read: %d\r\n", buf);
	BT_printf("%d\r\n",buf);
    Audio_Init();
	Qspi_Init();

	// USB needs QSPI XIP mode, so init after Qspi_Init
	CONFIG_DEBUG_SERIAL.printf("USB: Initializing...\r\n");
	Usb_Init();
	CONFIG_DEBUG_SERIAL.printf("USB: Ready\r\n");

	SD_Init();

  Display_Init();
	Touch_Init();
#if CONFIG_WATCH_DOG_ENABLE
    uint32_t timeout = WDG_Init(CONFIG_WATCH_DOG_TIMEOUT);
    taskManager.Register(WDG_ReloadCounter, CONFIG_WATCH_DOG_TIMEOUT / 10);
    CONFIG_DEBUG_SERIAL.printf("WatchDog: Timeout = %dms\r\n", timeout);
#endif

    taskManager.Register(Power_EventMonitor, 100);
    taskManager.Register(GPS_Update, 200);
		taskManager.Register(BT_Update, 200);
    taskManager.Register(SD_Update, 500);
    taskManager.Register(Memory_DumpInfo, 1000);
	//taskManager.Register(Touch_Update, 100);

    Timer_SetInterrupt(CONFIG_HAL_UPDATE_TIM, 10 * 1000, HAL_TimerInterrputUpdate);
    Timer_SetEnable(CONFIG_HAL_UPDATE_TIM, true);
}

void HAL::HAL_Update()
{
    taskManager.Running(millis());
}
