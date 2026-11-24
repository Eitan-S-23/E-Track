#include <assert.h>
#include <stdint.h>
#include "p34_ack_gap.h"

int main()
{
    uint32_t now = 0;
    assert(p34_ack_gap([&]() { return now++; }, [&]() { return now >= 10; }, 20, 100));
    assert(now >= 31);
    now = UINT32_MAX - 8;
    assert(p34_ack_gap([&]() { return now++; }, []() { return true; }, 20, 100));
    assert(now >= 12 && now < 20);
    now = 0;
    assert(!p34_ack_gap([&]() { return now++; }, []() { return false; }, 20, 10));
    assert(now == 11);
    now = 0;
    assert(p34_ack_gap([&]() { return now++; }, []() { return true; }, 0, 10));
    assert(now == 3);
    return 0;
}
