/* Host-only access to the unchanged snapshot's private recovery validator. */
#include "boot_state_machine.c"
#include <stdio.h>
#include <stdlib.h>

typedef struct {
    unsigned char data[0x100000];
    size_t length;
    unsigned calls;
    unsigned fail_at;
} fixture_t;

static fixture_t fixture;

static int external_read(void *ctx, uint32_t address, uint8_t *dst, size_t len)
{
    fixture_t *f = (fixture_t *)ctx;
    uint32_t offset;
    ++f->calls;
    if (f->calls == f->fail_at || address < OTA_EXT_RECOVERY)
        return -1;
    offset = address - OTA_EXT_RECOVERY;
    if (offset > f->length || len > f->length - offset)
        return -1;
    memcpy(dst, f->data + offset, len);
    return 0;
}

int main(int argc, char **argv)
{
    FILE *file;
    boot_state_io_t io;
    image_source_t source;
    source_result_t result;
    int expected;
    if (argc != 4)
        return 2;
    file = fopen(argv[1], "rb");
    if (file == NULL)
        return 2;
    fixture.length = fread(fixture.data, 1, sizeof(fixture.data), file);
    if (ferror(file) || fgetc(file) != EOF) {
        fclose(file);
        return 2;
    }
    fclose(file);
    fixture.fail_at = (unsigned)strtoul(argv[3], NULL, 10);
    expected = atoi(argv[2]);
    memset(&io, 0, sizeof(io));
    memset(&source, 0, sizeof(source));
    io.ctx = &fixture;
    io.external_read = external_read;
    io.external_available = 1;
    result = validate_external_source(&io, NULL, SOURCE_RECOVERY, &source);
    printf("RECOVERY_ADMISSION result=%d reads=%u version=%lu\n",
           (int)result, fixture.calls, (unsigned long)source.version_code);
    return ((int)result == expected) ? 0 : 1;
}
