/* Host-only stack ownership for the unchanged portable transaction core. */
#include "writer.h"
#include <stddef.h>

size_t rr_host_workspace_size(void)
{
    return sizeof(rr_workspace);
}

size_t rr_host_io_size(void)
{
    return sizeof(rr_io);
}

int rr_host_run(const rr_io *io, uint32_t length, const uint8_t pinned_sha[32])
{
    rr_workspace workspace;
    return rr_run(io, &workspace, length, pinned_sha);
}
