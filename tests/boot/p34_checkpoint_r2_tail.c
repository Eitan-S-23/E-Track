/* Appended to the frozen harness with only its main renamed; R2 shape only. */
static unsigned tail_cuts;
static int durable_final_seen;

static int final_checkpoint_present(void)
{
    int found = 0;
    for (unsigned slot = 0; slot < 2; ++slot)
    {
        bcb_t record;
        const uint8_t *raw = g_eeprom + (slot ? BCB_B_ADDR : BCB_A_ADDR);
        if (!bcb_is_valid(raw)) continue;
        bcb_deserialize(raw, &record);
        if (record.state == BCB_STATE_APPLYING && record.resume_block == TEST_BLOCK_COUNT)
            found = 1;
    }
    for (int i = 0; i < g_history_count; ++i)
        if (g_history[i].state == BCB_STATE_APPLYING &&
            g_history[i].resume_block == TEST_BLOCK_COUNT)
            found = 1;
    return found;
}

static void final_frontier(void)
{
    REQUIRE(durable_final_seen || final_checkpoint_present());
    for (unsigned i = TEST_IMAGE_LEN; i < TEST_BLOCK_COUNT * TEST_BLOCK_SIZE; ++i)
        REQUIRE(g_internal[i] == 0xff);
}

static void seed_tail(unsigned changed)
{
    bcb_t bcb;
    setup(changed, 65534);
    fill_upgrade_bcb(&bcb, BCB_STATE_APPLYING, 0, 144);
    bcb.seq = 65534;
    place_bcb(&bcb);
    prefill_blocks(g_candidate_image, 144);
    memcpy(template_internal, g_internal, OTA_APP_LENGTH);
    memcpy(template_eeprom, g_eeprom, 256);
    restore();
}

static void r2_tail(unsigned changed)
{
    int events, transactions;
    durable_final_seen = 0;
    setup(changed, 65534);
    restore();
    success(run_model(0), 0);
    REQUIRE(apply_commits == (152 + P34_BOOT_APPLY_CHECKPOINT_BLOCKS - 1) /
                            P34_BOOT_APPLY_CHECKPOINT_BLOCKS);
    REQUIRE(g_total_erases == (int)changed);
    final_frontier();
    printf("R2_NORMAL group=%d changed=%u commits=%d blocks=152 last_bytes=1084\n",
           P34_BOOT_APPLY_CHECKPOINT_BLOCKS, changed, apply_commits);

    seed_tail(changed);
    success(run_model(0), 0);
    events = event_count;
    transactions = g_eeprom_write_calls;
    REQUIRE(apply_commits == (P34_BOOT_APPLY_CHECKPOINT_BLOCKS == 16 ? 1 : 8));
    final_frontier();
    /* Only the changed policy's final eight blocks and subsequent transitions. */
    if (P34_BOOT_APPLY_CHECKPOINT_BLOCKS == 16)
        for (int at = 1; at <= events; ++at)
        {
            restore();
            (void)run_model(at);
            REQUIRE(fired);
            ++tail_cuts;
            /* A cut can commit EEPROM before the synthetic history callback. */
            durable_final_seen = final_checkpoint_present();
            success(run_model(0), 0);
            final_frontier();
            durable_final_seen = 0;
        }
    for (int call = 1; call <= transactions; ++call)
        for (int after = 0; after < 2; ++after)
        {
            restore();
            g_fail_eeprom_write_call = call;
            g_fail_eeprom_after_write = after;
            REQUIRE(run_model(0).action != BOOT_STATE_ACTION_JUMP_APP);
            durable_final_seen = final_checkpoint_present();
            g_fail_eeprom_write_call = 0;
            success(run_model(0), 0);
            final_frontier();
            durable_final_seen = 0;
        }
    if (changed == 152)
        for (int kind = 0; kind < 3; ++kind)
        {
            restore();
            if (kind == 0) g_fail_erase_block = 151;
            if (kind == 1) g_fail_program_block = 151;
            if (kind == 2) g_inject_readback_block = 151;
            REQUIRE(run_model(0).action != BOOT_STATE_ACTION_JUMP_APP);
            REQUIRE(active_bcb().resume_block < 152);
            g_fail_erase_block = g_fail_program_block = g_inject_readback_block = -1;
            g_readback_armed = 0;
            success(run_model(0), 0);
            final_frontier();
        }
    restore();
    success(run_model(0), 0);
    REQUIRE(run_model(0).bcb.boot_try == 1);
    REQUIRE(run_model(0).bcb.boot_try == 0);
    rollback_commits = 0;
    success(run_model(0), 1);
    REQUIRE(rollback_commits == 152);
}

int main(void)
{
    (void)original_campaign_main;
    setvbuf(stdout, NULL, _IONBF, 0);
    REQUIRE(TEST_IMAGE_LEN == 619580 && TEST_BLOCK_COUNT == 152);
    REQUIRE(TEST_IMAGE_LEN - 151 * TEST_BLOCK_SIZE == 1084);
    g_external = malloc(OTA_EXT_WINDOW_LENGTH);
    g_internal = malloc(OTA_APP_LENGTH);
    REQUIRE(g_external && g_internal);
    r2_tail(1);
    r2_tail(152);
    printf("R2_CHECKPOINT_TAIL_PASS group=%d scenarios=%u cuts=%u max_rework=%u\n",
           P34_BOOT_APPLY_CHECKPOINT_BLOCKS, scenarios, tail_cuts, max_rework);
    free(g_external);
    free(g_internal);
    return 0;
}
