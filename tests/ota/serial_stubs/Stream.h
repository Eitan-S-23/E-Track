#ifndef SERIAL_TEST_STREAM_H
#define SERIAL_TEST_STREAM_H
#include "Print.h"
class Stream : public Print
{
public:
    virtual int available() = 0;
    virtual int peek() = 0;
    virtual int read() = 0;
    virtual void flush() = 0;
};
#endif
