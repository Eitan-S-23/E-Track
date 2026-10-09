#include "restore_core.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static uint8_t storage[256], original[256];
static unsigned writes, erases;
static int fail_read, fail_write, fail_erase, corrupt_write;
static restore_expect_t expected = {30287,30286,611892,4058573588u};
static int read_bytes(uint8_t reg, uint8_t *data, uint16_t size)
{
    if (fail_read || (unsigned)reg + size > sizeof(storage)) return -1;
    memcpy(data, storage + reg, size);
    return 0;
}
static int write_bytes(uint8_t reg, const uint8_t *data, uint16_t size)
{
    assert(size == 64 && (reg == 0 || reg == 64));
    ++writes;
    if (fail_write) {
        memcpy(storage + reg, data, 8);
        return -1;
    }
    memcpy(storage + reg, data, size);
    if (corrupt_write) storage[reg + 60] ^= 1;
    return 0;
}
static const bcb_hal_t hal = {write_bytes, read_bytes};
static int clear_journal(void)
{
    ++erases;
    return fail_erase ? -1 : 0;
}
static void fixture(uint16_t seq, int active_b)
{
    bcb_t value;
    memset(storage, 0xa5, sizeof(storage));
    memset(storage, 0xff, 128);
    storage[255] = 0x55;
    bcb_make_idle(&value, expected.from_version);
    value.state = BCB_STATE_CONFIRMED;
    value.boot_try = 0;
    value.backup_len = expected.backup_length;
    value.backup_crc32 = expected.backup_crc32;
    value.backup_vcode = expected.to_version;
    value.cand_addr = 0x1000;
    value.cand_len = 611892;
    value.cand_vcode = 30287;
    value.cand_crc32 = 0x12345678;
    value.seq = seq;
    bcb_serialize(&value, storage + (active_b ? 64 : 0));
    memcpy(original, storage, sizeof(storage));
    writes = erases = 0;
    fail_read = fail_write = fail_erase = corrupt_write = 0;
}
static bcb_t prepare(void)
{
    bcb_t before;
    bcb_arbiter_result_t active;
    assert(restore_prepare(&hal, &expected, &before, &active) == RESTORE_OK);
    assert(!writes && !erases);
    return before;
}
int main(void)
{
    unsigned checks = 0;
    for (int active_b = 0; active_b < 2; ++active_b) {
        for (int wrap = 0; wrap < 2; ++wrap) {
            fixture(wrap ? 65535 : 17, active_b);
            bcb_t before = prepare(), after;
            assert(restore_execute(&hal, &expected, &before, clear_journal, &after) == RESTORE_OK);
            assert(writes == 1 && erases == 1);
            assert(after.state == BCB_STATE_ROLLBACK && after.copy_phase == BCB_COPY_ROLLBACK);
            assert(after.boot_try == 0 && after.resume_block == 0);
            assert(after.seq == (uint16_t)(before.seq + 1));
            assert(after.backup_vcode == 30286 && after.cur_vcode == 30287);
            assert(after.cand_crc32 == before.cand_crc32 && after.backup_crc32 == before.backup_crc32);
            assert(!memcmp(storage + 128, original + 128, 128));
            assert(!memcmp(storage + (active_b ? 64 : 0), original + (active_b ? 64 : 0), 64));
            assert(restore_execute(&hal, &expected, &before, clear_journal, &after) == RESTORE_STATE);
            assert(writes == 1 && erases == 1);
            ++checks;
        }
    }
    for (int bad = 0; bad < 9; ++bad) {
        fixture(10, 0);
        bcb_t before = prepare(), after;
        bcb_arbiter_result_t active;
        if (bad == 0) before.state = BCB_STATE_STAGED;
        if (bad == 1) before.cur_vcode++;
        if (bad == 2) before.backup_vcode--;
        if (bad == 3) before.backup_len--;
        if (bad == 4) before.backup_crc32++;
        if (bad == 5) before.boot_try = 3;
        if (bad == 6) before.copy_phase = BCB_COPY_ROLLBACK;
        if (bad == 7) before.resume_block = 1;
        bcb_serialize(&before, storage);
        if (bad == 8) memset(storage, 0xff, 128);
        assert(restore_prepare(&hal, &expected, &after, &active) == RESTORE_STATE);
        assert(restore_execute(&hal, &expected, &before, clear_journal, &after) == RESTORE_STATE);
        assert(writes == 0 && erases == 0);
        ++checks;
    }
    fixture(10,0);
    bcb_t before = prepare(), after, changed = before;
    changed.seq++;
    bcb_serialize(&changed, storage);
    assert(restore_execute(&hal, &expected, &before, clear_journal, &after) == RESTORE_CHANGED);
    assert(writes == 0 && erases == 0);
    ++checks;
    for (int bad = 0; bad < 4; ++bad) {
        fixture(10,0);
        before = prepare();
        fail_read = bad == 0; fail_erase = bad == 1; fail_write = bad == 2; corrupt_write = bad == 3;
        int result = restore_execute(&hal, &expected, &before, clear_journal, &after);
        assert(result == (bad == 0 ? RESTORE_STATE : bad == 1 ? RESTORE_JOURNAL : RESTORE_COMMIT));
        assert(writes == (unsigned)(bad >= 2) && erases == (unsigned)(bad >= 1));
        assert(!memcmp(storage, original, 64) && !memcmp(storage + 128, original + 128, 128));
        ++checks;
    }
    printf("RESTORE_CORE_TESTS=%u PASS; real bcb_commit, atomic inactive block, no settings writes\n", checks);
    return 0;
}
