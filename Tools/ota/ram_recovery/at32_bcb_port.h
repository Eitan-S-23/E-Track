#ifndef RR_AT32_BCB_PORT_H
#define RR_AT32_BCB_PORT_H
#include "bcb_reader.h"

/* Requires proven RAM vectors/MSP, Thread mode, exclusive GPIO/EEPROM ownership,
 * no relevant DMA and an independently established 288 MHz core clock.
 * Deliberately establishes a NEW DWT baseline. No old register restoration.
 * Does not reset, resume App, service watchdog, or write EEPROM NVM.
 * Not a debugger entry or a takeover implementation.
 */
int rr_at32_bcb_capture(rr_bcb_observation *out);
#endif
