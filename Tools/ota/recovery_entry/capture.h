#ifndef RE_CAPTURE_H
#define RE_CAPTURE_H
#include "supervisor.h"
#include "bcb_reader.h"

typedef struct {
    void *ctx;
    int (*owned)(void *);
    void (*sda)(void *, int);
    void (*scl)(void *, int);
    int (*read_sda)(void *);
    int (*read_scl)(void *);
} re_capture_pins;

/* Qualified, already-configured open-drain pins only. Never reconfigures GPIO,
   clocks or DWT; never retries. Success is stable BCB bytes, not settlement.
   On loss of time/ownership, suppress ALL further pin changes, including the
   reader's best-effort release. Physical disposition remains UNKNOWN. */
int re_capture_once(re_session *, const re_profile *, const re_clock *,
                    const re_capture_pins *, rr_bcb_observation *);
#endif
