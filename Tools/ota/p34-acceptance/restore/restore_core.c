#include "restore_core.h"
#include <string.h>

static int same_record(const bcb_t *a, const bcb_t *b)
{
    uint8_t left[BCB_SIZE], right[BCB_SIZE];
    bcb_serialize(a, left);
    bcb_serialize(b, right);
    return memcmp(left, right, sizeof(left)) == 0;
}

int restore_prepare(const bcb_hal_t *hal, const restore_expect_t *expected,
                    bcb_t *before, bcb_arbiter_result_t *active)
{
    if (!hal || !expected || !before || !active) return RESTORE_STATE;
    *active = bcb_arbiter(hal, before);
    if ((*active != BCB_ARBITER_A && *active != BCB_ARBITER_B) ||
        before->state != BCB_STATE_CONFIRMED || before->copy_phase != BCB_COPY_NONE ||
        before->resume_block != 0 || before->boot_try != 0 ||
        before->cur_vcode != expected->from_version ||
        before->backup_vcode != expected->to_version ||
        before->backup_len != expected->backup_length ||
        before->backup_crc32 != expected->backup_crc32 ||
        expected->from_version != 30287u || expected->to_version != 30286u)
        return RESTORE_STATE;
    return RESTORE_OK;
}

int restore_execute(const bcb_hal_t *hal, const restore_expect_t *expected,
                    const bcb_t *before, int (*clear_journal)(void), bcb_t *after)
{
    bcb_t current, next;
    bcb_arbiter_result_t active, observed;
    int result;
    if (!before || !after || !clear_journal) return RESTORE_STATE;
    result = restore_prepare(hal, expected, &current, &active);
    if (result != RESTORE_OK) return result;
    if (!same_record(before, &current)) return RESTORE_CHANGED;
    if (clear_journal() != 0) return RESTORE_JOURNAL;
    /* Match Boot's begin_rollback, preserving its verified backup reference. */
    next = current;
    next.state = BCB_STATE_ROLLBACK;
    next.boot_try = 0;
    next.copy_phase = BCB_COPY_ROLLBACK;
    next.resume_block = 0;
    result = bcb_commit(hal, active, &next);
    observed = bcb_arbiter(hal, after);
    if (result != BCB_COMMIT_OK) return RESTORE_COMMIT;
    next.seq = (uint16_t)(current.seq + 1u);
    if ((observed != BCB_ARBITER_A && observed != BCB_ARBITER_B) || !same_record(&next, after))
        return RESTORE_VERIFY;
    return RESTORE_OK;
}
