#include "boot_recovery.h"

#include "boot_crypto.h"
#include "boot_fw_header.h"
#include "boot_platform.h"
#include "boot_ymodem.h"

#include "OTA/ota_layout.h"

#include <stdint.h>
#include <string.h>

enum
{
    RECOVERY_TRAILER_SIZE = 8,
    RECOVERY_FLASH_PAGE_SIZE = 256,
    RECOVERY_FLASH_SECTOR_SIZE = 4096
};

typedef struct
{
    uint32_t total_size;
    uint32_t image_len;
    uint32_t total_received;
    uint32_t image_received;
    uint32_t flash_address;
    uint8_t page[RECOVERY_FLASH_PAGE_SIZE];
    size_t page_len;
    uint8_t trailer[RECOVERY_TRAILER_SIZE];
    size_t trailer_len;
    boot_crc32_ctx_t crc;
} recovery_context_t;

static uint32_t read_le32(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static int internal_flash_read(void *ctx, uint32_t offset, uint8_t *dst, size_t len)
{
    const uint8_t *src;
    (void)ctx;

    if (dst == NULL || offset > OTA_APP_LENGTH || len > OTA_APP_LENGTH - offset)
    {
        return -1;
    }
    src = (const uint8_t *)(uintptr_t)(OTA_APP_ORIGIN + offset);
    memcpy(dst, src, len);
    return 0;
}

static int recovery_flush_page(recovery_context_t *ctx)
{
    size_t program_len;

    if (ctx->page_len == 0u)
    {
        return 0;
    }
    program_len = (ctx->page_len + 3u) & ~(size_t)3u;
    memset(ctx->page + ctx->page_len, 0xFF, program_len - ctx->page_len);

    if ((ctx->flash_address & (RECOVERY_FLASH_SECTOR_SIZE - 1u)) == 0u &&
        boot_platform_flash_erase_4k(ctx->flash_address) != 0)
    {
        return -1;
    }
    if (boot_platform_flash_program(ctx->flash_address, ctx->page, program_len) != 0)
    {
        return -1;
    }
    ctx->flash_address += (uint32_t)program_len;
    ctx->page_len = 0u;
    return 0;
}

static int recovery_begin(void *opaque, const char *name, uint32_t total_size)
{
    recovery_context_t *ctx = (recovery_context_t *)opaque;
    (void)name;

    if (ctx == NULL || total_size <= RECOVERY_TRAILER_SIZE ||
        total_size > OTA_APP_LENGTH + RECOVERY_TRAILER_SIZE)
    {
        return -1;
    }

    memset(ctx, 0, sizeof(*ctx));
    ctx->total_size = total_size;
    ctx->image_len = total_size - RECOVERY_TRAILER_SIZE;
    ctx->flash_address = OTA_APP_ORIGIN;
    boot_crc32_init(&ctx->crc);
    return 0;
}

static int recovery_write(void *opaque, const uint8_t *data, size_t len)
{
    recovery_context_t *ctx = (recovery_context_t *)opaque;
    size_t offset = 0u;

    if (ctx == NULL || (data == NULL && len != 0u) ||
        ctx->total_received > ctx->total_size ||
        len > ctx->total_size - ctx->total_received)
    {
        return -1;
    }

    while (offset < len && ctx->image_received < ctx->image_len)
    {
        size_t image_left = ctx->image_len - ctx->image_received;
        size_t page_room = sizeof(ctx->page) - ctx->page_len;
        size_t take = len - offset;

        if (take > image_left)
        {
            take = image_left;
        }
        if (take > page_room)
        {
            take = page_room;
        }
        memcpy(ctx->page + ctx->page_len, data + offset, take);
        boot_crc32_update(&ctx->crc, data + offset, take);
        ctx->page_len += take;
        ctx->image_received += (uint32_t)take;
        ctx->total_received += (uint32_t)take;
        offset += take;

        if (ctx->page_len == sizeof(ctx->page) && recovery_flush_page(ctx) != 0)
        {
            return -1;
        }
    }

    while (offset < len)
    {
        size_t take = len - offset;
        size_t trailer_room = sizeof(ctx->trailer) - ctx->trailer_len;

        if (take > trailer_room)
        {
            take = trailer_room;
        }
        if (take == 0u)
        {
            return -1;
        }
        memcpy(ctx->trailer + ctx->trailer_len, data + offset, take);
        ctx->trailer_len += take;
        ctx->total_received += (uint32_t)take;
        offset += take;
    }
    return 0;
}

static int recovery_end(void *opaque)
{
    recovery_context_t *ctx = (recovery_context_t *)opaque;
    uint32_t trailer_len;
    uint32_t trailer_crc;

    if (ctx == NULL || ctx->total_received != ctx->total_size ||
        ctx->image_received != ctx->image_len ||
        ctx->trailer_len != sizeof(ctx->trailer))
    {
        return -1;
    }
    if (recovery_flush_page(ctx) != 0)
    {
        return -1;
    }

    trailer_len = read_le32(ctx->trailer);
    trailer_crc = read_le32(ctx->trailer + 4u);
    if (trailer_len != ctx->image_len || trailer_crc != boot_crc32_final(&ctx->crc))
    {
        boot_platform_log("BOOT: recovery trailer rejected\r\n");
        return -1;
    }

    boot_platform_log("BOOT: recovery transport verified\r\n");
    return 0;
}

static int recovery_validate_image(const recovery_context_t *ctx)
{
    boot_image_reader_t reader;
    boot_fw_expectations_t expected;
    boot_fw_header_t header;
    boot_fw_result_t validation;

    if (ctx == NULL)
    {
        return -1;
    }

    reader.read = internal_flash_read;
    reader.ctx = NULL;
    boot_fw_default_expectations(&expected);
    validation = boot_fw_header_validate(&reader, &expected, &header);
    if (validation != BOOT_FW_OK)
    {
        boot_platform_log("BOOT: recovery fw_header rejected: ");
        boot_platform_log(boot_fw_result_name(validation));
        boot_platform_log("\r\n");
        return -1;
    }
    if (header.image_len != ctx->image_len)
    {
        boot_platform_log("BOOT: recovery image length disagrees with fw_header\r\n");
        return -1;
    }

    boot_platform_log("BOOT: recovery fw_header verified\r\n");
    return 0;
}

static void recovery_abort(void *opaque)
{
    recovery_context_t *ctx = (recovery_context_t *)opaque;
    if (ctx != NULL)
    {
        memset(ctx, 0, sizeof(*ctx));
    }
}

static int uart_getc(void *ctx, uint8_t *byte, uint32_t timeout_ms)
{
    (void)ctx;
    return boot_platform_uart_getc(byte, timeout_ms);
}

static void uart_putc(void *ctx, uint8_t byte)
{
    (void)ctx;
    boot_platform_uart_putc(byte);
}

int boot_recovery_receive(void)
{
    recovery_context_t context;
    boot_ymodem_io_t io;
    boot_ymodem_sink_t sink;
    boot_ymodem_result_t result;

    memset(&context, 0, sizeof(context));
    io.getc = uart_getc;
    io.putc = uart_putc;
    io.ctx = NULL;
    sink.begin = recovery_begin;
    sink.write = recovery_write;
    sink.end = recovery_end;
    sink.abort = recovery_abort;
    sink.ctx = &context;

    result = boot_ymodem_receive(&io, &sink);
    if (result != BOOT_YMODEM_OK)
    {
        boot_platform_log("BOOT: Ymodem failed: ");
        boot_platform_log(boot_ymodem_result_name(result));
        boot_platform_log("\r\n");
        return -1;
    }
    return recovery_validate_image(&context);
}
