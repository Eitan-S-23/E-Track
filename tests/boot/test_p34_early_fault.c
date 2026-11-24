#include <assert.h>
#include <stdio.h>
#include "p34_early_fault_policy.h"

int main(void)
{
    unsigned checks = 0;
    for (unsigned irq = 0; irq < 16; ++irq)
    for (unsigned wrong_table = 0; wrong_table < 2; ++wrong_table)
    for (int ready = 0; ready < 2; ++ready)
    {
        int expected = irq == 0 && wrong_table == 0 && ready == 1;
        assert(p34_promotion_allowed(irq, 0x08010000u + wrong_table * 1024,
                                    0x08010000u, ready) == expected);
        ++checks;
    }
    assert(!p34_promotion_allowed(0, 0x08010000, 0x08010000, -1)); ++checks;
    assert(!p34_promotion_allowed(0, 0x08010000, 0x08010000, 2)); ++checks;
    printf("EARLY_PROMOTION_POLICY_PASS checks=%u\n", checks);
    return 0;
}
