#include "boot_fw_header.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct
{
    const uint8_t *data;
    size_t len;
} memory_image_t;

static int memory_read(void *ctx, uint32_t offset, uint8_t *dst, size_t len)
{
    const memory_image_t *image = (const memory_image_t *)ctx;

    if (image == NULL || dst == NULL || offset > image->len || len > image->len - offset)
    {
        return -1;
    }
    memcpy(dst, image->data + offset, len);
    return 0;
}

int main(int argc, char **argv)
{
    FILE *file;
    long file_size;
    uint8_t *data;
    memory_image_t image;
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;
    boot_fw_result_t result;
    int exit_code = 1;

    if (argc != 3)
    {
        fprintf(stderr, "usage: %s IMAGE EXPECTED_RESULT\n", argv[0]);
        return 2;
    }

    file = fopen(argv[1], "rb");
    if (file == NULL || fseek(file, 0, SEEK_END) != 0)
    {
        fprintf(stderr, "cannot open %s\n", argv[1]);
        if (file != NULL)
        {
            fclose(file);
        }
        return 2;
    }
    file_size = ftell(file);
    if (file_size <= 0 || fseek(file, 0, SEEK_SET) != 0)
    {
        fclose(file);
        return 2;
    }
    data = (uint8_t *)malloc((size_t)file_size);
    if (data == NULL || fread(data, 1u, (size_t)file_size, file) != (size_t)file_size)
    {
        free(data);
        fclose(file);
        return 2;
    }
    fclose(file);

    image.data = data;
    image.len = (size_t)file_size;
    reader.read = memory_read;
    reader.ctx = &image;
    boot_fw_default_expectations(&expected);
    result = boot_fw_header_validate(&reader, &expected, NULL);

    printf("%s: %s\n", argv[1], boot_fw_result_name(result));
    if (strcmp(boot_fw_result_name(result), argv[2]) == 0)
    {
        exit_code = 0;
    }
    free(data);
    return exit_code;
}
