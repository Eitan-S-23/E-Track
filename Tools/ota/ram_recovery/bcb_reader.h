#ifndef RR_BCB_READER_H
#define RR_BCB_READER_H
#include "EEPROM/eeprom_bcb.h"

/* Exclusive bus ownership required. All callbacks must be bounded; pause must
 * enforce the transaction deadline without depending on SysTick interrupts.
 * high=1 means open-drain release, not push-pull drive.
 */
typedef struct {
    void *ctx;
    void (*sda)(void *, int);
    void (*scl)(void *, int);
    int (*read_sda)(void *);
    int (*read_scl)(void *);
    int (*pause)(void *);
} rr_bcb_bus;

typedef struct {
    uint8_t raw[2][2][BCB_SIZE];
    unsigned completed;
    bcb_arbiter_result_t active;
    bcb_t value;
    int stable;
} rr_bcb_observation;

/* No EEPROM NVM write interface. Captures A,B,A,B once; never retries. */
int rr_bcb_capture(const rr_bcb_bus *bus, rr_bcb_observation *out);
#endif
