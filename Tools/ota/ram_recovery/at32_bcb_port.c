#include "at32_bcb_port.h"
#include "at32f435_437.h"

typedef struct { uint32_t begun; } clock_context;

static int delay(void *opaque)
{
    clock_context *clock = opaque;
    uint32_t start = DWT->CYCCNT;
    unsigned spins;
    /* Five microseconds at the required 288 MHz, 2 s whole-capture deadline.
     * A stopped/changed DWT must never create an unbounded software wait. */
    for (spins = 0; spins < 100000u; ++spins) {
        uint32_t now = DWT->CYCCNT;
        if ((uint32_t)(now-clock->begun) >= 576000000u) return -1;
        if ((uint32_t)(now-start) >= 1440u) return 0;
    }
    return -1;
}

static void sda(void *ctx, int high)
{
    (void)ctx;
    if (high) GPIOB->scr = GPIO_PINS_7;
    else GPIOB->clr = GPIO_PINS_7;
}

static void scl(void *ctx, int high)
{
    (void)ctx;
    if (high) GPIOB->scr = GPIO_PINS_6;
    else GPIOB->clr = GPIO_PINS_6;
}

static int sda_read(void *ctx) { (void)ctx; return (GPIOB->idt & GPIO_PINS_7) != 0; }
static int scl_read(void *ctx) { (void)ctx; return (GPIOB->idt & GPIO_PINS_6) != 0; }

int rr_at32_bcb_capture(rr_bcb_observation *out)
{
    clock_context clock;
    gpio_init_type pins;
    rr_bcb_bus bus;
    if (!out || __get_IPSR() != 0u || __get_PRIMASK() != 1u) return -1;
    /* Clock derivation and safe takeover are separate admission prerequisites;
     * this runtime check only rejects an obviously unbound vector region. */
    if (SCB->VTOR < 0x20058000u || SCB->VTOR >= 0x20080000u) return -1;
    CoreDebug->DEMCR |= CoreDebug_DEMCR_TRCENA_Msk;
    DWT->CYCCNT = 0u;
    DWT->CTRL |= DWT_CTRL_CYCCNTENA_Msk;
    __DSB(); __ISB();
    clock.begun = DWT->CYCCNT;
    if (delay(&clock) != 0) return -1;
    crm_periph_clock_enable(CRM_GPIOB_PERIPH_CLOCK, TRUE);
    GPIOB->scr = GPIO_PINS_6 | GPIO_PINS_7;
    gpio_default_para_init(&pins);
    pins.gpio_pins = GPIO_PINS_6 | GPIO_PINS_7;
    pins.gpio_mode = GPIO_MODE_OUTPUT;
    pins.gpio_pull = GPIO_PULL_UP;
    pins.gpio_out_type = GPIO_OUTPUT_OPEN_DRAIN;
    pins.gpio_drive_strength = GPIO_DRIVE_STRENGTH_MODERATE;
    gpio_init(GPIOB, &pins);
    if (delay(&clock) != 0 || !sda_read(0) || !scl_read(0)) return -1;
    bus.ctx = &clock;
    bus.sda = sda; bus.scl = scl;
    bus.read_sda = sda_read; bus.read_scl = scl_read; bus.pause = delay;
    return rr_bcb_capture(&bus, out);
}
