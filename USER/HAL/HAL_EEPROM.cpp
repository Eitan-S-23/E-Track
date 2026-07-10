#include "HAL.h"
#include "EEPROM/EEPROM.h"

static EEPROM at24c;

bool HAL::EEPROM_Init()
{
    CONFIG_DEBUG_SERIAL.print("EEPROM: init...");

    bool success = at24c.Init();

    CONFIG_DEBUG_SERIAL.println(success ? "success" : "failed");
		
		if(EEPROM_Check())
			CONFIG_DEBUG_SERIAL.print("EEPROM: read failed...");
	
    return success;
}

void HAL::EEPROM_Read(uint8_t reg, uint8_t* buf, uint16_t len)
{
    at24c.ReadBytes(reg,buf,len);
}

void HAL::EEPROM_WritePage(uint8_t reg, uint8_t* buf, uint16_t len)
{
		for(int i = 0; i < len; i++)
    {
       at24c.WriteByte(reg++, buf[i]);
    }   
}

void HAL::EEPROM_Write(uint8_t reg, uint8_t buf)
{	
    at24c.WriteByte(reg, buf);   
}

uint8_t HAL::EEPROM_Check(void)
{
	u8 buf;
	EEPROM_Read(255, &buf, 1);//避免每次开机都写AT24CXX			   
	if((buf)==0X55)
	{
		return 0;
	}
	else
	{				//排除第一次初始化的情况
		EEPROM_Write(255,0X55);
		delay_ms(5);
		EEPROM_Read(255, &buf, 1);
		if((buf)==0X55)
			return 0;
		else
			return 1;
	}							  
}
