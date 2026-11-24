#ifndef RE_GPIO_MOCK_H
#define RE_GPIO_MOCK_H
#include <stdint.h>
typedef struct { volatile uint32_t ahben1; } re_mock_crm;
typedef struct { volatile uint32_t cfgr, omode, pull, odrvr, odt, idt, scr, clr; } re_mock_gpio;
extern re_mock_crm re_mock_crm_regs;
extern re_mock_gpio re_mock_gpio_regs;
#define CRM (&re_mock_crm_regs)
#define GPIOB (&re_mock_gpio_regs)
void re_mock_barrier(void);
#define __DSB() re_mock_barrier()
#endif
