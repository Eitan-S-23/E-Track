/* Freestanding byte primitives: compile with -fno-builtin. No runtime state. */
#include <stddef.h>
#include "writer.h"

rr_workspace rr_workspace_storage;

void *memcpy(void *destination, const void *source, size_t length)
{
    unsigned char *d = destination;
    const unsigned char *s = source;
    size_t i;
    for (i = 0; i < length; ++i) d[i] = s[i];
    return destination;
}

void *memset(void *destination, int value, size_t length)
{
    unsigned char *d = destination;
    size_t i;
    for (i = 0; i < length; ++i) d[i] = (unsigned char)value;
    return destination;
}

int memcmp(const void *left, const void *right, size_t length)
{
    const unsigned char *a = left, *b = right;
    size_t i;
    for (i = 0; i < length; ++i)
        if (a[i] != b[i]) return (int)a[i] - (int)b[i];
    return 0;
}
