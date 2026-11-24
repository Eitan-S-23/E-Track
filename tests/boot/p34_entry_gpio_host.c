#include "bcb_target.h"
#include "at32f435_437.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

re_mock_crm re_mock_crm_regs;
re_mock_gpio re_mock_gpio_regs;
static unsigned barriers;
void re_mock_barrier(void) { ++barriers; }
static void reset(void)
{
    memset(&re_mock_gpio_regs, 0, sizeof(re_mock_gpio_regs));
    re_mock_crm_regs.ahben1 = 2;
    re_mock_gpio_regs.cfgr = re_mock_gpio_regs.pull = 0x5000;
    re_mock_gpio_regs.omode = re_mock_gpio_regs.odt = re_mock_gpio_regs.idt = 0xc0;
    re_mock_gpio_regs.odrvr = 0xa000;
    barriers = 0;
}
int main(void)
{
    unsigned kind, pin, high, cases = 0;
    re_mock_gpio before, expected;
    for (pin = 6; pin <= 7; ++pin) for (high = 0; high <= 1; ++high) {
        reset(); before = re_mock_gpio_regs; expected = before;
        assert(re_bcb_pin_config_ok(1));
        assert(re_bcb_pin_set(pin, (int)high) == 0 && barriers == 1);
        if (high) expected.scr = 1u << pin; else expected.clr = 1u << pin;
        assert(memcmp(&expected, &re_mock_gpio_regs, sizeof(expected)) == 0);
        assert(re_mock_crm_regs.ahben1 == 2);
        ++cases;
    }
    for (kind = 0; kind < 5; ++kind) {
        reset();
        if (kind == 0) re_mock_crm_regs.ahben1 = 0;
        if (kind == 1) re_mock_gpio_regs.cfgr = 0;
        if (kind == 2) re_mock_gpio_regs.omode = 0;
        if (kind == 3) re_mock_gpio_regs.pull = 0;
        if (kind == 4) re_mock_gpio_regs.odrvr = 0;
        before = re_mock_gpio_regs;
        assert(!re_bcb_pin_config_ok(0));
        assert(re_bcb_pin_set(6, 1) == -1 && re_bcb_pin_read(7) == -1);
        assert(!barriers && memcmp(&before, &re_mock_gpio_regs, sizeof(before)) == 0);
        ++cases;
    }
    reset(); before = re_mock_gpio_regs;
    assert(re_bcb_pin_set(5, 1) == -1 && re_bcb_pin_set(6, 2) == -1 && re_bcb_pin_read(8) == -1);
    assert(!barriers && memcmp(&before, &re_mock_gpio_regs, sizeof(before)) == 0); ++cases;
    reset(); re_mock_gpio_regs.idt = 0;
    assert(!re_bcb_pin_config_ok(1) && re_bcb_pin_config_ok(0));
    assert(re_bcb_pin_read(6) == 0 && re_bcb_pin_read(7) == 0); ++cases;
    reset(); re_mock_gpio_regs.odt = 0;
    assert(!re_bcb_pin_config_ok(1) && re_bcb_pin_config_ok(0)); ++cases;
    printf("ENTRY_GPIO_HOST_PASS scenarios=%u\n", cases);
    return 0;
}
