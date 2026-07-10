#ifndef __EEPROM_H
#define __EEPROM_H

#include "Arduino.h"

#define EEPROM_I2C_ADDRESS    0x50

class EEPROM
{
public:
    EEPROM(){}
    ~EEPROM(){}

    bool Init(uint8_t addr = EEPROM_I2C_ADDRESS);
		
		void WriteByte(uint8_t reg, uint8_t dat);
    void ReadBytes(uint8_t reg, uint8_t* buf, uint16_t len);
			
private:
    uint8_t Address;
    void WriteReg(uint8_t reg, uint8_t dat);
    uint8_t ReadReg(uint8_t reg);
    void ReadRegs(uint8_t reg, uint8_t* buf, uint16_t len);
    void SetRegisterBits(uint8_t reg, uint8_t data, bool setBits);
};

#endif
