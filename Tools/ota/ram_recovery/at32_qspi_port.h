#ifndef RR_AT32_QSPI_PORT_H
#define RR_AT32_QSPI_PORT_H
#include <stdint.h>

typedef struct { int initialized; int failed; uint32_t jedec; } rr_qspi_state;

/* Experimental fixed QSPI1 ports. Requires separately proved RAM takeover,
 * idle DMA/controller, configured QSPI GPIO/clock, fresh running DWT at 288MHz,
 * and a watchdog/reset plan. No reset/erase-all/status-register write commands.
 * Any error latches failure. No automatic XIP restoration or App resumption.
 */
int rr_qspi_prepare(rr_qspi_state *state);
int rr_qspi_read(void *state, uint32_t address, uint8_t *dst, uint32_t length);
int rr_qspi_erase(void *state, uint32_t address);
int rr_qspi_program(void *state, uint32_t address, const uint8_t *src, uint32_t length);
#endif
