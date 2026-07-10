#include "HAL.h"
#include "Wire.h"

int HAL::I2C_Scan()
{
    if(!Wire.begin())
    {
        CONFIG_DEBUG_SERIAL.println("I2C: init failed");
        return -1;
    }

    uint8_t error, address;
    int nDevices;

    CONFIG_DEBUG_SERIAL.println("I2C: device scanning...");

    nDevices = 0;
    for (address = 1; address < 127; address++ )
    {
        // The i2c_scanner uses the return value of
        // the Write.endTransmisstion to see if
        // a device did acknowledge to the address.
        Wire.beginTransmission(address);
        error = Wire.endTransmission();

        if (error == 0)
        {
            CONFIG_DEBUG_SERIAL.print("I2C: device found at address 0x");
            if (address < 16)
                CONFIG_DEBUG_SERIAL.print("0");
            CONFIG_DEBUG_SERIAL.print(address, HEX);
            CONFIG_DEBUG_SERIAL.println(" !");

            nDevices++;
        }
        else if (error == 4)
        {
            CONFIG_DEBUG_SERIAL.print("I2C: unknow error at address 0x");
            if (address < 16)
                CONFIG_DEBUG_SERIAL.print("0");
            CONFIG_DEBUG_SERIAL.println(address, HEX);
        }
    }

    CONFIG_DEBUG_SERIAL.printf("I2C: %d devices was found\r\n", nDevices);
    return nDevices;
}
