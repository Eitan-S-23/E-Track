#include "EEPROM.h"
#include "Wire.h"
#include <math.h>

bool EEPROM::Init(uint8_t addr)
{
    Address = addr;
		
		return true;
}

uint8_t EEPROM::ReadReg(uint8_t reg)
{
    Wire.beginTransmission(Address);
    Wire.write(reg);
    Wire.endTransmission();

    Wire.requestFrom(Address, 1);
    uint8_t data = Wire.read();
    Wire.endTransmission();

    return data;
}

void EEPROM::ReadRegs(uint8_t reg, uint8_t* buf, uint16_t len)
{
    Wire.beginTransmission(Address);
    Wire.write(reg);
    Wire.endTransmission();

    Wire.requestFrom(Address, len);
    for(int i = 0; i < len; i++)
    {
        buf[i] = Wire.read();
    }
    Wire.endTransmission();
}

void EEPROM::SetRegisterBits(uint8_t reg, uint8_t data, bool setBits)
{
    uint8_t val = ReadReg(reg);
    setBits ? val |= data : val &= ~data;
    WriteReg(reg, val);
}

void EEPROM::WriteReg(uint8_t reg, uint8_t value)
{
    Wire.beginTransmission(Address);
    Wire.write(reg);
    Wire.write(value);
    Wire.endTransmission();
}

void EEPROM::WriteByte(uint8_t reg, uint8_t dat)
{
	  WriteReg(reg, dat);
}

void EEPROM::ReadBytes(uint8_t reg, uint8_t* buf, uint16_t len)
{
		ReadRegs(reg, buf,  len);
}
