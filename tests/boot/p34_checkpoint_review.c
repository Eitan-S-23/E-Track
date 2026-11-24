/* Appended to the preserved r3 harness with its main/checkpoint renamed. */
static int tx, reads, fail_read, mismatch_read, fault_seen;
static int tear_tx, tear_page, tear_bytes, uncertain_tx;
static unsigned stop_point, stop_phase, stop_block;
static int cut_seen, failed_tx, failed_erases, failed_reads;
static int pre_reads[200], target_regs[200];
static unsigned tear_cases, io_cases, sequence_cases, negative_cases;
static bcb_t last_write;
static int wrote_this_run;

static int padded_match(const uint8_t *image, unsigned blocks)
{
    size_t bytes = (size_t)blocks * TEST_BLOCK_SIZE;
    size_t body = bytes < TEST_IMAGE_LEN ? bytes : TEST_IMAGE_LEN;
    if (blocks > TEST_BLOCK_COUNT || memcmp(g_internal, image, body)) return 0;
    for (size_t i = body; i < bytes; ++i)
        if (g_internal[i] != 0xff) return 0;
    return 1;
}

/* Uses surviving storage and independent expected bytes, not checkpoint_due. */
static int storage_ok(unsigned verified_limit)
{
    bcb_t b;
    bcb_arbiter_result_t a = bcb_arbiter(&g_bcb_hal, &b);
    if (a != BCB_ARBITER_A && a != BCB_ARBITER_B) return 0;
    switch (b.state)
    {
    case BCB_STATE_STAGED:
        return b.copy_phase == BCB_COPY_NONE && b.resume_block == 0;
    case BCB_STATE_APPLYING:
        return b.copy_phase == BCB_COPY_APPLY && b.resume_block <= verified_limit &&
               padded_match(g_candidate_image, b.resume_block);
    case BCB_STATE_ROLLBACK:
        return b.copy_phase == BCB_COPY_ROLLBACK && b.resume_block <= verified_limit &&
               padded_match(g_current_image, b.resume_block);
    case BCB_STATE_TEST_BOOT:
        return b.copy_phase == BCB_COPY_NONE && b.resume_block == 0 &&
               b.boot_try <= 3 && padded_match(g_candidate_image, TEST_BLOCK_COUNT);
    case BCB_STATE_CONFIRMED:
        return b.copy_phase == BCB_COPY_NONE && b.resume_block == 0 &&
               b.boot_try == 0 && b.cur_vcode == 20700 &&
               padded_match(g_current_image, TEST_BLOCK_COUNT);
    default: return 0;
    }
}

static void interrupt_now(void)
{
    REQUIRE(storage_ok(verified));
    cut_seen = 1;
    longjmp(power_cut, 1);
}

void p34_model_checkpoint(uint32_t point, uint32_t phase, uint32_t block)
{
    original_checkpoint(point, phase, block);
    if (point == stop_point && phase == stop_phase && block == stop_block)
        interrupt_now();
}

static int review_read(uint8_t reg, uint8_t *dst, uint16_t len)
{
    ++reads;
    REQUIRE(!fault_seen); /* Failure must stop this invocation immediately. */
    if (reads == fail_read || reads == mismatch_read)
    {
        fault_seen = 1; failed_tx = tx; failed_erases = g_total_erases;
        failed_reads = reads;
        if (reads == fail_read) return -1;
        REQUIRE(eeprom_read(reg, dst, len) == 0);
        dst[0] ^= 1;
        return 0;
    }
    return eeprom_read(reg, dst, len);
}

static int review_write(uint8_t reg, const uint8_t *src, uint16_t len)
{
    bcb_t before, next;
    uint8_t old[BCB_SIZE];
    bcb_arbiter_result_t a = bcb_arbiter(&g_bcb_hal, &before);
    unsigned old_reg = a == BCB_ARBITER_A ? BCB_A_ADDR : BCB_B_ADDR;
    REQUIRE(!fault_seen && len == BCB_SIZE && (a == BCB_ARBITER_A || a == BCB_ARBITER_B));
    REQUIRE(reg != old_reg);
    memcpy(old, g_eeprom + old_reg, BCB_SIZE);
    bcb_deserialize(src, &next);
    REQUIRE(next.seq == (uint16_t)(before.seq + 1));
    if (next.state == BCB_STATE_APPLYING)
        REQUIRE(next.resume_block <= verified && padded_match(g_candidate_image, next.resume_block));
    if (next.state == BCB_STATE_ROLLBACK)
    {
        if (before.state != BCB_STATE_ROLLBACK)
            REQUIRE(next.copy_phase == BCB_COPY_ROLLBACK && next.resume_block == 0);
        else
            REQUIRE(next.resume_block == before.resume_block + 1);
    }
    if (next.state == BCB_STATE_TEST_BOOT)
        REQUIRE(next.boot_try == (before.state == BCB_STATE_TEST_BOOT ? before.boot_try - 1 : 3));
    ++tx; REQUIRE(tx < 200);
    pre_reads[tx] = reads; target_regs[tx] = reg;
    for (int page = 0; page < 8; ++page)
    {
        for (int byte = 1; byte <= 8; ++byte)
        {
            g_eeprom[reg + page * 8 + byte - 1] = src[page * 8 + byte - 1];
            REQUIRE(memcmp(old, g_eeprom + old_reg, BCB_SIZE) == 0);
            if (tx == tear_tx && page == tear_page && byte == tear_bytes)
                interrupt_now();
        }
    }
    record_bcb(src); last_write = next; wrote_this_run = 1;
    if (tx == uncertain_tx)
    {
        fault_seen = 1; failed_tx = tx; failed_erases = g_total_erases;
        failed_reads = reads;
        return -1;
    }
    return 0;
}

static const bcb_hal_t review_hal = {review_write, review_read};

static void clear_injection(void)
{
    fail_read = mismatch_read = tear_tx = uncertain_tx = 0;
    stop_point = stop_phase = stop_block = 0;
}

static boot_state_outcome_t invoke(void)
{
    boot_state_io_t io;
    boot_state_outcome_t outcome;
    bcb_t entry = active_bcb();
    unsigned expected_try = entry.state == BCB_STATE_TEST_BOOT ? entry.boot_try - 1 : 2;
    REQUIRE(storage_ok(TEST_BLOCK_COUNT));
    verified = entry.resume_block;
    tx = reads = cut_seen = fault_seen = wrote_this_run = 0;
    cut_at = 0; event_count = 0;
    memset(&io, 0, sizeof(io)); memset(&outcome, 0, sizeof(outcome));
    io.bcb_hal = &review_hal; io.external_read = external_read;
    io.internal_read = internal_read; io.internal_erase_4k = model_erase;
    io.internal_program = model_program; io.external_available = 1;
    if (setjmp(power_cut) == 0) (void)boot_state_machine_run(&io, &outcome);
    else memset(&outcome, 0, sizeof(outcome));
    REQUIRE(storage_ok(TEST_BLOCK_COUNT));
    if (fault_seen)
    {
        REQUIRE(outcome.action != BOOT_STATE_ACTION_JUMP_APP);
        REQUIRE(tx == failed_tx && reads == failed_reads && g_total_erases == failed_erases);
    }
    if (outcome.action == BOOT_STATE_ACTION_JUMP_APP)
    {
        bcb_t b = active_bcb();
        REQUIRE(wrote_this_run);
        REQUIRE(last_write.seq == b.seq && last_write.state == b.state);
        if (b.state == BCB_STATE_TEST_BOOT)
            REQUIRE(b.boot_try == expected_try && last_write.boot_try == expected_try);
        else REQUIRE(b.state == BCB_STATE_CONFIRMED && b.boot_try == 0);
        REQUIRE(memcmp(g_external + OTA_EXT_BACKUP + OTA_SLOT_HEADER_SIZE,
                       g_current_image, TEST_IMAGE_LEN) == 0);
    }
    return outcome;
}

static void finish(int rollback)
{
    clear_injection();
    boot_state_outcome_t o = invoke();
    REQUIRE(o.action == BOOT_STATE_ACTION_JUMP_APP);
    REQUIRE(active_bcb().state == (rollback ? BCB_STATE_CONFIRMED : BCB_STATE_TEST_BOOT));
}

static void fresh(void)
{
    clear_injection(); setup(146, 65534); restore();
}

static void oracle_negatives(void)
{
    bcb_t b;
    fresh();
    fill_upgrade_bcb(&b, BCB_STATE_APPLYING, 0, 16); place_bcb(&b);
    prefill_blocks(g_candidate_image, 16);
    REQUIRE(storage_ok(16)); REQUIRE(!storage_ok(15)); ++negative_cases;
    g_internal[10 * TEST_BLOCK_SIZE + 17] ^= 1;
    REQUIRE(!storage_ok(16)); ++negative_cases;
    prefill_blocks(g_candidate_image, TEST_BLOCK_COUNT);
    fill_upgrade_bcb(&b, BCB_STATE_APPLYING, 0, TEST_BLOCK_COUNT); place_bcb(&b);
    REQUIRE(storage_ok(TEST_BLOCK_COUNT));
    g_internal[TEST_IMAGE_LEN + 1] = 0;
    REQUIRE(!storage_ok(TEST_BLOCK_COUNT)); ++negative_cases;
}

static void transaction_matrix(void)
{
    static const int selected[] = {1, 2, 3, 11, 12, 13};
    int read_anchors[200], regs[200];
    fresh(); finish(0); REQUIRE(tx == 13);
    memcpy(read_anchors, pre_reads, sizeof(read_anchors));
    memcpy(regs, target_regs, sizeof(regs));
    REQUIRE(regs[2] != regs[3]);
    for (unsigned i = 0; i < sizeof(selected)/sizeof(selected[0]); ++i)
    {
        int at = selected[i];
        for (int page = 0; page < 8; ++page)
        for (int byte = 1; byte <= 7; ++byte)
        {
            fresh(); tear_tx = at; tear_page = page; tear_bytes = byte;
            (void)invoke(); REQUIRE(cut_seen); finish(0); ++tear_cases;
        }
        /* Last two reads before writing: pre-arbitration A/B; then readback,
         * post-arbitration A/B. The readback targets alternate slots. */
        for (int kind = 0; kind < 6; ++kind)
        {
            fresh();
            int ordinal = read_anchors[at] + kind - 1;
            if (kind == 5) mismatch_read = read_anchors[at] + 1;
            else fail_read = ordinal;
            (void)invoke(); REQUIRE(fault_seen); finish(0); ++io_cases;
        }
        printf("TRANSACTION_PASS tx=%d target=%d tears=56 read_faults=6\n", at, regs[at]);
    }
}

static void stop_copy(unsigned phase, unsigned block)
{
    stop_point = OTA_P1_6_CP_COPY_AFTER_READBACK;
    stop_phase = phase; stop_block = block;
}

static void sequences(void)
{
    fresh(); tear_tx = 2; tear_page = 1; tear_bytes = 3;
    (void)invoke(); REQUIRE(cut_seen);
    clear_injection(); stop_copy(BCB_COPY_APPLY, 2);
    (void)invoke(); REQUIRE(cut_seen); finish(0); ++sequence_cases;

    fresh(); uncertain_tx = 2;
    (void)invoke(); REQUIRE(fault_seen && active_bcb().resume_block == 16);
    clear_injection(); tear_tx = 1; tear_page = 2; tear_bytes = 5;
    (void)invoke(); REQUIRE(cut_seen); finish(0); ++sequence_cases;

    for (int at = 1; at <= 2; ++at)
    {
        fresh(); stop_point = OTA_P1_6_CP_COPY_RESUME_COMMITTED;
        stop_phase = BCB_COPY_APPLY; stop_block = TEST_BLOCK_COUNT;
        (void)invoke(); REQUIRE(cut_seen);
        clear_injection(); tear_tx = at; tear_page = 7; tear_bytes = 7;
        (void)invoke(); REQUIRE(cut_seen); finish(0); ++sequence_cases;
    }
    /* Three persisted try decrements interrupted before any jump exhaust tries. */
    fresh(); stop_point = OTA_P1_6_CP_TRY_DECREMENT_COMMITTED;
    stop_phase = 2; stop_block = BCB_COPY_NONE;
    (void)invoke(); REQUIRE(cut_seen);
    stop_phase = 1; (void)invoke(); REQUIRE(cut_seen);
    stop_phase = 0; (void)invoke(); REQUIRE(cut_seen);
    finish(1); ++sequence_cases;

    for (int replacement = 0; replacement < 3; ++replacement)
    for (int rollback_cut = 1; rollback_cut <= 2; ++rollback_cut)
    {
        fresh(); stop_copy(BCB_COPY_APPLY, 20);
        (void)invoke(); REQUIRE(cut_seen && active_bcb().resume_block == 16);
        REQUIRE(bcb_is_valid(g_eeprom + BCB_A_ADDR) && bcb_is_valid(g_eeprom + BCB_B_ADDR));
        if (!replacement) g_external[OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE + 0x700] ^= 1;
        else
        {
            make_image(g_recovery_image, replacement == 1 ? 20600 : 20800, 0x33);
            install_slot(OTA_EXT_CANDIDATE, BOOT_SLOT_CANDIDATE, g_recovery_image);
        }
        clear_injection(); tear_tx = rollback_cut; tear_page = 7; tear_bytes = 7;
        (void)invoke(); REQUIRE(cut_seen); finish(1); ++sequence_cases;
    }
}

int main(void)
{
    (void)original_campaign_main;
    setvbuf(stdout, NULL, _IONBF, 0);
    g_external = malloc(OTA_EXT_WINDOW_LENGTH); g_internal = malloc(OTA_APP_LENGTH);
    REQUIRE(g_external && g_internal && P34_BOOT_APPLY_CHECKPOINT_BLOCKS == 16);
    oracle_negatives(); transaction_matrix(); sequences();
    printf("CHECKPOINT_REVIEW_PASS tears=%u io_faults=%u sequences=%u oracle_negatives=%u\n",
           tear_cases, io_cases, sequence_cases, negative_cases);
    free(g_external); free(g_internal); return 0;
}
