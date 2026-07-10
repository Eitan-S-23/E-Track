#include "HAL.h"
#include "Bluetooth/Bluetooth.h"
#include <stdio.h>
#include <stdarg.h>

#define BT_SERIAL             CONFIG_BT_SERIAL
#define DEBUG_SERIAL          CONFIG_DEBUG_SERIAL
#define BT_USE_TRANSPARENT    CONFIG_BT_USE_TRANSPARENT

static TinyBTPlus bt;
static uint32_t lastRxTick = 0;

void HAL::BT_Init()
{
    BT_SERIAL.begin(115200);
    //pinMode(CONFIG_BT_EN_PIN, OUTPUT);
#ifdef CONFIG_BT_STATE_PIN
    pinMode(CONFIG_BT_STATE_PIN, INPUT);
#endif
    BT_NormalMode();
		delay_ms(50);
		BT_SetName();
		delay_ms(50);
    CONFIG_DEBUG_SERIAL.print("Bluetooth library v. ");
    CONFIG_DEBUG_SERIAL.print(TinyBTPlus::libraryVersion());
    CONFIG_DEBUG_SERIAL.println(" by Eitan Su");
}

void HAL::BT_SleepMode()
{
	//digitalWrite(CONFIG_BT_EN_PIN, HIGH);
	CONFIG_DEBUG_SERIAL.println("Bt: OFF\r\n");
}

void HAL::BT_NormalMode()
{
	//digitalWrite(CONFIG_BT_EN_PIN, LOW);
	CONFIG_DEBUG_SERIAL.println("Bt: ON\r\n");
}

void HAL::BT_SetName()
{
	BT_SERIAL.printf("AT+NAME=XTrace\r\n");
}

void HAL::BT_printf(char *format, ...)
{
	char String[100];
	va_list arg;
	va_start(arg, format);
	vsprintf(String, format, arg);
	va_end(arg);
	BT_SERIAL.print(String);
}

void HAL::BT_Update()
{
#if CONFIG_BT_BUF_OVERLOAD_CHK && !BT_USE_TRANSPARENT
    int available = BT_SERIAL.available();
    DEBUG_SERIAL.printf("BT: Buffer available = %d", available);
    if(available >= SERIAL_RX_BUFFER_SIZE / 2)
    {
        DEBUG_SERIAL.print(", maybe overload!");
    }
    DEBUG_SERIAL.println();
#endif
		BT_SERIAL.printf("X-Trace\r\n");
    while (BT_SERIAL.available() > 0)
    {
        char c = BT_SERIAL.read();
        lastRxTick = millis();
#if BT_USE_TRANSPARENT
        DEBUG_SERIAL.write(c);
#endif
        bt.encode(c);
    }

#if BT_USE_TRANSPARENT
    while (DEBUG_SERIAL.available() > 0)
    {
        BT_SERIAL.write(DEBUG_SERIAL.read());
    }
#endif
}

bool HAL::BT_IsConnected()
{
#ifdef CONFIG_BT_STATE_PIN
    return digitalRead(CONFIG_BT_STATE_PIN) == HIGH;
#else
    return (lastRxTick != 0) && ((uint32_t)(millis() - lastRxTick) < 5000);
#endif
}
