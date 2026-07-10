/*
 * bsdiff_wrapper.c - Wrapper for bsdiff library for embedded systems
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "bsdiff.h"
#include "vFile.h"
#include "bs_user_interface.h"

// Stream implementation for embedded systems using vFile
struct bsdiff_stream bs_stream;

// Write callback for bsdiff
static int bs_write(struct bsdiff_stream *stream, const void *buffer, int size)
{
    uint32_t addr = (uint32_t)(uintptr_t)stream->opaque;

    // Use the user-provided flash write function
    if (bs_user_func.bs_flash_write != NULL)
    {
        return bs_user_func.bs_flash_write(addr, buffer, size);
    }

    return -1;
}

/**
 * @brief Create a binary diff between old and new data
 *
 * @param old Pointer to old data
 * @param oldsize Size of old data
 * @param new Pointer to new data
 * @param newsize Size of new data
 * @param patch_addr Flash address where to write the patch
 * @return int 0 on success, negative value on error
 */
int create_binary_diff(const uint8_t *old, int64_t oldsize,
                       const uint8_t *new, int64_t newsize,
                       uint32_t patch_addr)
{
    // Initialize the stream
    bs_stream.malloc = (void *(*)(size_t))bs_user_func.bs_malloc;
    bs_stream.free = bs_user_func.bs_free;
    bs_stream.write = bs_write;
    bs_stream.opaque = (void *)(uintptr_t)patch_addr;

    // Create the diff
    return bsdiff(old, oldsize, new, newsize, &bs_stream);
}