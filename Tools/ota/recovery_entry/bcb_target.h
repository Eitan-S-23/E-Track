#ifndef RE_BCB_TARGET_H
#define RE_BCB_TARGET_H
#include "capture.h"

typedef struct {
    uint32_t started, epoch, completed, result, stable, active, complete;
    uint8_t operation[32];
    uint8_t raw[2][2][BCB_SIZE];
} re_bcb_report;
extern volatile re_bcb_report re_bcb_observation_report;

int re_capture_target_once(re_session *, const re_profile *, rr_bcb_observation *);
void re_bcb_dispatch_once(const re_profile *);
void re_bcb_entry_dispatch(void) __attribute__((noreturn));
/* Fixed GPIOB 6/7 only; no configure/reset/clock-enable primitive exists. */
int re_bcb_pin_config_ok(int require_idle);
int re_bcb_pin_set(unsigned pin, int high);
int re_bcb_pin_read(unsigned pin);
#endif
