#ifndef P34_RESTORE_CORE_H
#define P34_RESTORE_CORE_H
#include "EEPROM/eeprom_bcb.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
    uint32_t from_version, to_version, backup_length, backup_crc32;
} restore_expect_t;
enum {
    RESTORE_OK = 0, RESTORE_STATE = 1, RESTORE_CHANGED = 2,
    RESTORE_JOURNAL = 3, RESTORE_COMMIT = 4, RESTORE_VERIFY = 5
};
int restore_prepare(const bcb_hal_t *hal, const restore_expect_t *expected,
                    bcb_t *before, bcb_arbiter_result_t *active);
int restore_execute(const bcb_hal_t *hal, const restore_expect_t *expected,
                    const bcb_t *before, int (*clear_journal)(void), bcb_t *after);
#ifdef __cplusplus
}
#endif
#endif
