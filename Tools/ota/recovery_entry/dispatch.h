#ifndef RE_DISPATCH_H
#define RE_DISPATCH_H
#include "supervisor.h"

#define RE_REPORT_COMPLETE 0x52454f42u
typedef struct {
    uint32_t started, epoch, observation, status_valid, status, complete;
    uint8_t operation[32];
} re_report;

extern volatile re_report re_observation_report;
extern const re_profile re_compiled_profile;
/* Trusted immutable profile only; no incoming command/pointer mailbox. The
   report is diagnostic, never an integrity, write, reset or exit permit. */
void re_dispatch_once(const re_profile *);
void re_entry_dispatch(void) __attribute__((noreturn));
void re_terminal(void) __attribute__((noreturn));
#endif
