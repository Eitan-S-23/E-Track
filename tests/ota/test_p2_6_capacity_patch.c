/* P2-6 host boundary harness for the patch arena capacity. */
#define main p2_3_patch_original_main
#include "test_ota_patch.c"
#undef main

#include <stdint.h>

static size_t p2_6_capacity_override = (size_t)-1;
static size_t p2_6_prefix_observed;

size_t ota_p2_6_host_arena_capacity(size_t prefix)
{
    p2_6_prefix_observed = prefix;
    if (p2_6_capacity_override == (size_t)-1)
    {
        return OTA_PATCH_WORKSPACE_SIZE - prefix;
    }
    return p2_6_capacity_override;
}

static int run_case(const char *name, size_t capacity,
                    ota_patch_result_t expected, int expect_success,
                    uint32_t p_full)
{
    ota_patch_info_t info;
    ota_patch_result_t result;
    int ok;

    reset_fixture();
    memset(&info, 0, sizeof(info));
    p2_6_capacity_override = capacity;
    result = apply_default(&info);
    ok = (result == expected);
    if (expect_success)
    {
        ok = ok && info.workspace_peak == p_full &&
             info.arena_peak_observed == p_full &&
             info.failed_request_size == 0u &&
             fixture.prepare_count != 0u && fixture.program_count != 0u;
    }
    else
    {
        ok = ok && info.arena_peak_observed != 0u &&
             info.failed_request_size != 0u &&
             fixture.prepare_count == 0u && fixture.program_count == 0u;
    }
    printf("P2_6_BOUNDARY kind=patch case=%s result=%s expected=%s "
           "prefix=%lu capacity=%lu workspace_peak=%lu "
           "arena_peak_observed=%lu failed_request_size=%lu "
           "candidate_prepares=%lu candidate_programs=%lu status=%s\n",
           name, ota_patch_result_name(result),
           ota_patch_result_name(expected),
           (unsigned long)p2_6_prefix_observed, (unsigned long)capacity,
           (unsigned long)info.workspace_peak,
           (unsigned long)info.arena_peak_observed,
           (unsigned long)info.failed_request_size,
           (unsigned long)fixture.prepare_count,
           (unsigned long)fixture.program_count, ok ? "PASS" : "FAIL");
    return ok ? 0 : 1;
}

int main(void)
{
    ota_patch_info_t info;
    ota_patch_result_t result;
    uint32_t p_full;
    size_t prefix;
    int failures = 0;

    golden_package = load_file("tests/ota-vectors/toy-patch.etu",
                               &golden_package_len);
    golden_base = load_file("tests/ota-vectors/toy-old.bin",
                            &golden_base_len);
    golden_image = load_file("tests/ota-vectors/toy-new.bin",
                             &golden_image_len);
    if (golden_package == 0 || golden_base == 0 || golden_image == 0)
    {
        fprintf(stderr, "P2_6_BOUNDARY patch vector load failed\n");
        return 2;
    }

    reset_fixture();
    memset(&info, 0, sizeof(info));
    p2_6_capacity_override = (size_t)-1;
    result = apply_default(&info);
    p_full = info.arena_peak_observed;
    prefix = p2_6_prefix_observed;
    printf("P2_6_BOUNDARY kind=patch case=baseline result=%s prefix=%lu "
           "P_full=%lu workspace_peak=%lu arena_peak_observed=%lu "
           "failed_request_size=%lu candidate_prepares=%lu "
           "candidate_programs=%lu\n",
           ota_patch_result_name(result), (unsigned long)prefix,
           (unsigned long)p_full, (unsigned long)info.workspace_peak,
           (unsigned long)info.arena_peak_observed,
           (unsigned long)info.failed_request_size,
           (unsigned long)fixture.prepare_count,
           (unsigned long)fixture.program_count);
    if (result != OTA_PATCH_OK || p_full == 0u ||
        p_full > OTA_PATCH_WORKSPACE_SIZE || p_full <= prefix)
    {
        fprintf(stderr, "P2_6_BOUNDARY patch baseline invalid\n");
        failures = 1;
    }
    else
    {
        failures += run_case("cap=P_full-prefix", p_full - prefix,
                             OTA_PATCH_OK, 1, p_full);
        failures += run_case("cap=P_full-prefix-1", p_full - prefix - 1u,
                             OTA_PATCH_ERR_WORKSPACE, 0, p_full);
    }

    free(golden_package);
    free(golden_base);
    free(golden_image);
    return failures == 0 ? 0 : 1;
}
