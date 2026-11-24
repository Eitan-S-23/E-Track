/* Appended to a generated copy of the source-bound original host harness. */
static void source_at_frontier(unsigned frontier, int replacement)
{
    bcb_t bcb;
    restore();
    fill_upgrade_bcb(&bcb, BCB_STATE_APPLYING, 0, frontier);
    place_bcb(&bcb);
    prefill_blocks(g_candidate_image, frontier);
    REQUIRE(active_bcb().resume_block == frontier);
    if (replacement == 0)
        g_external[OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE + 0x700] ^= 1;
    else
    {
        /* Also reject a different valid image with the SAME candidate version. */
        make_image(g_recovery_image, replacement == 1 ? 20600 : 20800, 0x33);
        install_slot(OTA_EXT_CANDIDATE, BOOT_SLOT_CANDIDATE, g_recovery_image);
    }
    success(run_model(0), 1);
    REQUIRE(rollback_commits == TEST_BLOCK_COUNT);
    install_slot(OTA_EXT_CANDIDATE, BOOT_SLOT_CANDIDATE, g_candidate_image);
}

int main(void)
{
    unsigned frontiers = 0;
    (void)original_campaign_main;
    setvbuf(stdout, NULL, _IONBF, 0);
    g_external = malloc(OTA_EXT_WINDOW_LENGTH);
    g_internal = malloc(OTA_APP_LENGTH);
    REQUIRE(g_external && g_internal);
    setup(146, 65534);
    restore();
    (void)run_model(40);
    REQUIRE(fired);
    printf("OLD_SOURCE_CUT group=%d state=%u frontier=%u verified=%u\n",
           P34_BOOT_APPLY_CHECKPOINT_BLOCKS, active_bcb().state,
           active_bcb().resume_block, verified);
    for (unsigned frontier = 0; frontier <= TEST_BLOCK_COUNT; ++frontier)
    {
        if (frontier % P34_BOOT_APPLY_CHECKPOINT_BLOCKS != 0 &&
            frontier != 3 && frontier != 150 && frontier != TEST_BLOCK_COUNT)
            continue;
        ++frontiers;
        for (int replacement = 0; replacement < 3; ++replacement)
            source_at_frontier(frontier, replacement);
    }
    printf("CHECKPOINT_EXTENSION_PASS group=%d frontiers=%u scenarios=%u\n",
           P34_BOOT_APPLY_CHECKPOINT_BLOCKS, frontiers, scenarios);
    free(g_external);
    free(g_internal);
    return 0;
}
