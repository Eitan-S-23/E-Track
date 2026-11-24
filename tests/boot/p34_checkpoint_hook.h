#ifndef P34_CHECKPOINT_HOOK_H
#define P34_CHECKPOINT_HOOK_H
#include <stdint.h>
#include "OTA/ota_p1_6_test.h"
/* Replace only the test checkpoint macro, never the BCB implementation. */
#define E_TRACK_BOOT_P1_6_TEST_H
void p34_model_checkpoint(uint32_t point, uint32_t phase, uint32_t block);
#define boot_p1_6_checkpoint(point, phase, block) p34_model_checkpoint(point, phase, block)
#endif
