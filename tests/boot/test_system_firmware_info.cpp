#include "USER/App/Utils/OtaUpdate/FirmwareInfo.h"
#include <stdlib.h>
#include <string.h>

struct Image { const uint8_t* data; size_t length; };

static int Read(void* ctx, uint32_t offset, uint8_t* dst, size_t length)
{
    const Image* image = (const Image*)ctx;
    if (offset > image->length || length > image->length - offset) return -1;
    memcpy(dst, image->data + offset, length);
    return 0;
}

int main(int argc, char** argv)
{
    if (argc != 3) return 2;
    FILE* file = fopen(argv[1], "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0) return 2;
    const long length = ftell(file);
    if (length < (long)(OTA_FW_HEADER_OFFSET + OTA_FW_HEADER_SIZE)) return 2;
    rewind(file);
    uint8_t* bytes = (uint8_t*)malloc((size_t)length);
    if (bytes == NULL || fread(bytes, 1, (size_t)length, file) != (size_t)length) return 2;
    fclose(file);
    Image image = { bytes, (size_t)length };
    boot_image_reader_t reader = { Read, &image };
    char out[48];
    int checks = 0;
#define CHECK(condition) do { if (!(condition)) { fprintf(stderr, "failed at %d\n", __LINE__); free(bytes); return 1; } ++checks; } while (0)
    CHECK(OtaUpdate::FormatFirmwareInfo(&reader, "E-Track", out, sizeof(out)));
    CHECK(strcmp(out, argv[2]) == 0);
    char shortOut[4] = { 'x', 'x', 'x', 'x' };
    CHECK(!OtaUpdate::FormatFirmwareInfo(&reader, "E-Track", shortOut, sizeof(shortOut)));
    CHECK(shortOut[3] == '\0');
    CHECK(!OtaUpdate::FormatFirmwareInfo(&reader, "E-Track", NULL, 10));
    CHECK(!OtaUpdate::FormatFirmwareInfo(&reader, NULL, out, sizeof(out)));
    out[0] = 'x';
    CHECK(!OtaUpdate::FormatFirmwareInfo(&reader, "E-Track", out, 0) && out[0] == 'x');
    image.length = 1;
    CHECK(!OtaUpdate::FormatFirmwareInfo(&reader, "E-Track", out, sizeof(out)));
    CHECK(strcmp(out, "E-Track (unknown)") == 0);
    image.length = (size_t)length;
    bytes[OTA_FW_HEADER_OFFSET + OTA_FW_HEADER_SIZE - 1] ^= 1;
    CHECK(!OtaUpdate::FormatFirmwareInfo(&reader, "E-Track", out, sizeof(out)));
    CHECK(strcmp(out, "E-Track (unknown)") == 0);
    free(bytes);
    printf("SYSTEM_FIRMWARE_INFO_CHECKS=%d failures=0\n", checks);
    return 0;
}
