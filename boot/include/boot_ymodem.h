#ifndef E_TRACK_BOOT_YMODEM_H
#define E_TRACK_BOOT_YMODEM_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct
{
    int (*getc)(void *ctx, uint8_t *byte, uint32_t timeout_ms);
    void (*putc)(void *ctx, uint8_t byte);
    void *ctx;
} boot_ymodem_io_t;

typedef struct
{
    int (*begin)(void *ctx, const char *name, uint32_t total_size);
    int (*write)(void *ctx, const uint8_t *data, size_t len);
    int (*end)(void *ctx);
    void (*abort)(void *ctx);
    void *ctx;
} boot_ymodem_sink_t;

typedef enum
{
    BOOT_YMODEM_OK = 0,
    BOOT_YMODEM_ERR_ARGUMENT,
    BOOT_YMODEM_ERR_TIMEOUT,
    BOOT_YMODEM_ERR_CANCELLED,
    BOOT_YMODEM_ERR_PROTOCOL,
    BOOT_YMODEM_ERR_SEQUENCE,
    BOOT_YMODEM_ERR_CRC,
    BOOT_YMODEM_ERR_FILE_SIZE,
    BOOT_YMODEM_ERR_SINK
} boot_ymodem_result_t;

boot_ymodem_result_t boot_ymodem_receive(const boot_ymodem_io_t *io,
                                         const boot_ymodem_sink_t *sink);
const char *boot_ymodem_result_name(boot_ymodem_result_t result);

#ifdef __cplusplus
}
#endif

#endif
