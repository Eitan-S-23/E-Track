#include "bcb_target.h"
#include "at32f435_437.h"

int re_bcb_pin_config_ok(int require_idle)
{
    /* Compare only the selected pins. Other GPIOB owners are not reconfigured.
       This matches configure_eeprom_gpio in the bound original Boot. */
    if (!(CRM->ahben1 & 2u) || (GPIOB->cfgr & 0xf000u) != 0x5000u ||
        (GPIOB->omode & 0xc0u) != 0xc0u || (GPIOB->pull & 0xf000u) != 0x5000u ||
        (GPIOB->odrvr & 0xf000u) != 0xa000u) return 0;
    if (require_idle && ((GPIOB->odt & 0xc0u) != 0xc0u || (GPIOB->idt & 0xc0u) != 0xc0u))
        return 0;
    return 1;
}
int re_bcb_pin_set(unsigned pin, int high)
{
    uint32_t mask;
    if ((pin != 6 && pin != 7) || (high != 0 && high != 1) || !re_bcb_pin_config_ok(0))
        return -1;
    mask = 1u << pin;
    if (high) GPIOB->scr = mask;
    else GPIOB->clr = mask;
    __DSB();
    return 0;
}
int re_bcb_pin_read(unsigned pin)
{
    if ((pin != 6 && pin != 7) || !re_bcb_pin_config_ok(0)) return -1;
    return (GPIOB->idt & (1u << pin)) != 0;
}
