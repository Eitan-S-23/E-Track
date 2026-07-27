#ifndef E_TRACK_BOOT_STATE_MACHINE_H
#define E_TRACK_BOOT_STATE_MACHINE_H

#include <stddef.h>
#include <stdint.h>

#include "boot_fw_header.h"
#include "EEPROM/eeprom_bcb.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef int (*boot_state_read_fn)(void *ctx, uint32_t address,
                                  uint8_t *dst, size_t len);
typedef int (*boot_state_erase_fn)(void *ctx, uint32_t address);
typedef int (*boot_state_program_fn)(void *ctx, uint32_t address,
                                     const uint8_t *src, size_t len);
typedef void (*boot_state_log_fn)(void *ctx, const char *text);

typedef struct
{
    const bcb_hal_t *bcb_hal;
    void *ctx;
    boot_state_read_fn external_read;
    boot_state_read_fn internal_read;
    boot_state_erase_fn internal_erase_4k;
    boot_state_program_fn internal_program;
    boot_state_log_fn log;
    int external_available;
} boot_state_io_t;

typedef enum
{
    BOOT_STATE_ACTION_HOLD = 0,
    BOOT_STATE_ACTION_JUMP_APP,
    BOOT_STATE_ACTION_PHYSICAL_RECOVERY
} boot_state_action_t;

typedef enum
{
    BOOT_STATE_STATUS_OK = 0,
    BOOT_STATE_STATUS_ARGUMENT = -1,
    BOOT_STATE_STATUS_BCB = -2,
    BOOT_STATE_STATUS_SLOT = -3,
    BOOT_STATE_STATUS_COPY = -4,
    BOOT_STATE_STATUS_COMMIT = -5,
    BOOT_STATE_STATUS_APP = -6,
    BOOT_STATE_STATUS_LOOP = -7
} boot_state_status_t;

typedef struct
{
    boot_state_action_t action;
    boot_state_status_t status;
    bcb_t bcb;
    boot_fw_header_t app_header;
} boot_state_outcome_t;

boot_state_status_t boot_state_machine_run(const boot_state_io_t *io,
                                           boot_state_outcome_t *outcome);

boot_state_status_t boot_state_machine_accept_physical_recovery(
    const boot_state_io_t *io,
    boot_state_outcome_t *outcome);

#ifdef __cplusplus
}
#endif

#endif
