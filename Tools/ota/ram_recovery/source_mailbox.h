#ifndef RR_SOURCE_MAILBOX_H
#define RR_SOURCE_MAILBOX_H
#include <stdint.h>

/* One aligned MCU request producer and one exclusive host reply producer.
 * Host clears response_commit before writing, then commits matching sequence
 * last. Only source file offsets exist: no target addresses or execute opcode.
 */
typedef struct {
    volatile uint32_t generation[2];
    volatile uint32_t request_offset, request_length, request_commit;
    volatile uint32_t response_generation[2];
    volatile uint32_t response_offset, response_length, response_crc;
    volatile uint8_t response_data[4096];
    volatile uint32_t response_commit;
} rr_source_mailbox;

typedef struct {
    rr_source_mailbox *box;
    void *clock_ctx;
    uint32_t (*now)(void *);
    uint32_t generation[2], source_length, timeout_ticks, sequence;
    uint32_t cache_offset, cache_length;
    uint8_t cache[4096];
    int failed;
} rr_source;

int rr_source_init(rr_source *source, rr_source_mailbox *box, uint32_t length,
                   const uint32_t generation[2], uint32_t timeout_ticks,
                   uint32_t (*now)(void *), void *clock_ctx);
int rr_source_read(void *source, uint32_t offset, uint8_t *dst, uint32_t length);
#endif
