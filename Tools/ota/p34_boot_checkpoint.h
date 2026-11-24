#ifndef P34_BOOT_CHECKPOINT_H
#define P34_BOOT_CHECKPOINT_H
#include <stdint.h>

#ifndef P34_BOOT_APPLY_CHECKPOINT_BLOCKS
#define P34_BOOT_APPLY_CHECKPOINT_BLOCKS 1
#endif
#if P34_BOOT_APPLY_CHECKPOINT_BLOCKS != 1 && P34_BOOT_APPLY_CHECKPOINT_BLOCKS != 4 && P34_BOOT_APPLY_CHECKPOINT_BLOCKS != 16
#error Unsupported checkpoint group
#endif

/* Only copy progress is grouped. State transitions never use this predicate. */
static int p34_boot_checkpoint_due(int applying, uint32_t completed, uint32_t total)
{
    return !applying || completed == total ||
           completed % P34_BOOT_APPLY_CHECKPOINT_BLOCKS == 0u;
}
#endif
