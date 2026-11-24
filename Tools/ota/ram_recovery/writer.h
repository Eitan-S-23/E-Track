#ifndef P34_RAM_RECOVERY_WRITER_H
#define P34_RAM_RECOVERY_WRITER_H
#include <stdint.h>
#include "boot_fw_header.h"

/* Isolated transaction core. No target port or device command entry exists yet.
 * Ports must be synchronous, bounded and unable to mutate writer-owned RAM.
 * A failed/uncertain operation ends this invocation; callers must not resume it.
 */
typedef struct {
    void *ctx;
    int (*source)(void *, uint32_t, uint8_t *, uint32_t);
    int (*read)(void *, uint32_t, uint8_t *, uint32_t);
    int (*erase)(void *, uint32_t);
    int (*program)(void *, uint32_t, const uint8_t *, uint32_t);
} rr_io;

typedef struct {
    uint8_t chunks[240][32];
    uint8_t block[4096];
    uint8_t check[256];
    uint8_t captured_header[96];
    uint8_t pinned[32];
    boot_fw_header_t header;
    uint32_t length;
    uint32_t payload_crc;
} rr_workspace;

enum { RR_OK = 0, RR_ARGUMENT = -1, RR_SOURCE = -2, RR_IO = -3, RR_VERIFY = -4 };
int rr_run(const rr_io *io, rr_workspace *w, uint32_t length,
           const uint8_t pinned_sha[32]);
#endif
