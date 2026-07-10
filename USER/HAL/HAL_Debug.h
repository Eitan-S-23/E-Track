/*
 * Debug print switches.
 *
 * Set CONFIG_DEBUG_SERIAL_ENABLE or CONFIG_DEBUG_RTT_ENABLE to 0 in
 * HAL_Config.h, or override them from the project preprocessor definitions.
 */
#ifndef __HAL_DEBUG_H
#define __HAL_DEBUG_H

#include <stddef.h>
#include <stdint.h>

#include "HAL_Config.h"
#include "SEGGER_RTT.h"

#if !CONFIG_DEBUG_SERIAL_ENABLE
namespace HAL {

class DebugNullSerial_t
{
public:
    void begin(uint32_t baudRate)
    {
        (void)baudRate;
    }

    void end(void)
    {
    }

    void flush(void)
    {
    }

    int available(void)
    {
        return 0;
    }

    int peek(void)
    {
        return -1;
    }

    int read(void)
    {
        return -1;
    }

    size_t write(uint8_t value)
    {
        (void)value;
        return 0;
    }

    size_t write(const uint8_t* buffer, size_t size)
    {
        (void)buffer;
        (void)size;
        return 0;
    }

    size_t write(const char* str)
    {
        (void)str;
        return 0;
    }

    int printf(const char* format, ...)
    {
        (void)format;
        return 0;
    }

    template<typename T>
    size_t print(const T& value)
    {
        (void)value;
        return 0;
    }

    template<typename T, typename U>
    size_t print(const T& value, U format)
    {
        (void)value;
        (void)format;
        return 0;
    }

    size_t println(void)
    {
        return 0;
    }

    template<typename T>
    size_t println(const T& value)
    {
        (void)value;
        return 0;
    }

    template<typename T, typename U>
    size_t println(const T& value, U format)
    {
        (void)value;
        (void)format;
        return 0;
    }

    operator bool()
    {
        return false;
    }
};

static DebugNullSerial_t DebugNullSerial;

}

#undef CONFIG_DEBUG_SERIAL
#define CONFIG_DEBUG_SERIAL HAL::DebugNullSerial
#endif

#if !CONFIG_DEBUG_RTT_ENABLE
#undef SEGGER_RTT_Init
#undef SEGGER_RTT_SetFlagsUpBuffer
#undef SEGGER_RTT_printf
#undef SEGGER_RTT_Write
#undef SEGGER_RTT_WriteString

#define SEGGER_RTT_Init()                  do { } while (0)
#define SEGGER_RTT_SetFlagsUpBuffer(...)   do { } while (0)
#define SEGGER_RTT_printf(...)             do { } while (0)
#define SEGGER_RTT_Write(...)              do { } while (0)
#define SEGGER_RTT_WriteString(...)        do { } while (0)
#endif

#endif
