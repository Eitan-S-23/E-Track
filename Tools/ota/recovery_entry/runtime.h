#ifndef RE_RUNTIME_H
#define RE_RUNTIME_H
#include <stdint.h>

typedef struct { uint32_t epoch, ticks, hz; } re_sample;
typedef struct {
    void *ctx;
    int (*sample)(void *, re_sample *);
} re_clock;
typedef struct {
    re_sample start;
    uint32_t budget, previous, polls, poll_limit;
    int failed;
} re_deadline;
int re_begin(const re_clock *, uint32_t epoch, uint32_t hz,
             uint32_t budget, re_deadline *);
int re_begin_limited(const re_clock *, uint32_t epoch, uint32_t hz,
                     uint32_t budget, uint32_t poll_limit, re_deadline *);
int re_alive(const re_clock *, re_deadline *);
/* Minimum ticks within the existing deadline, not a new epoch or proof of
   physical media settlement. Failure consumes the deadline permanently. */
int re_wait_minimum(const re_clock *, re_deadline *, uint32_t ticks);

typedef struct {
    void *ctx;
    /* Qualification is external evidence, not a hardware-idle detector. */
    int (*owned)(void *);
    int (*read32)(void *, uint32_t offset, uint32_t *);
    int (*write32)(void *, uint32_t offset, uint32_t value);
    int (*read8)(void *, uint32_t offset, uint8_t *);
} re_status_io;
typedef enum { RE_OBS_UNKNOWN, RE_OBS_BUSY, RE_OBS_IDLE_STATUS_ONLY } re_observation;
/* No writer pointer, reset, completion/exit permit, or timebase reset API. */
re_observation re_observe(const re_status_io *, const re_clock *,
                          uint32_t epoch, uint32_t hz, uint32_t budget,
                          uint8_t *raw_status);
#endif
