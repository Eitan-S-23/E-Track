#ifndef SERIAL_TEST_PRINT_H
#define SERIAL_TEST_PRINT_H
#include <stddef.h>
#include <stdint.h>
class Print
{
public:
    virtual ~Print() {}
    virtual size_t write(uint8_t value) = 0;
    size_t write(const char *) { return 0u; }
};
#endif
