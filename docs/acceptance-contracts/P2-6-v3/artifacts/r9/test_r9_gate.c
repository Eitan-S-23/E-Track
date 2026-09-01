/* P2-6-SD-R9 宿主离线闸门：GOOD 正例对照 + BAD 中途失败注入。
 * 构型仿 tests/ota/test_p2_6_capacity_package.c（#define main 重命名 + include 源测试）。
 * 判据：
 *   GOOD: result=OK, workspace_peak==arena_peak_observed>0, candidate==源镜像逐字节,
 *         prepare/program 计数非 0, BCB 不变。
 *   BAD : result!=OK 且 !=PAYLOAD_CRC（外层 CRC 自洽），acquire_count==1（CRC 过
 *         后才 acquire——证明失败点在 acquire 之后），release_count==1（cleanup
 *         释放），workspace_zeroed==1，arena_peak_observed!=0（arena 已初始化），
 *         prepare_count>=1（candidate_prepare 已执行=失败更靠后），BCB 不变。
 */
#define main p2_2_package_original_main
#include "test_ota_package.c"
#undef main

#define R9_GOOD_ETU ".cache/p2-6-sd-r9-20260901-01-implementation/tmp/GOOD-2.8.2.etu"
#define R9_BAD_ETU  ".cache/p2-6-sd-r9-20260901-01-implementation/tmp/BAD-2.8.2.etu"
#define R9_SRC_IMG  ".cache/p2-6-sd-r9-20260901-01-implementation/tmp/app-src-2.8.1.bin"

static int r9_failures;

static void r9_check(const char *name, int condition)
{
    printf("P2_6_R9_GATE check %-52s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
    {
        ++r9_failures;
    }
}

int main(void)
{
    ota_package_device_t device;
    ota_package_info_t info;
    ota_package_result_t result;
    uint8_t *src_image;
    uint32_t src_image_len;

    /* 设备构型对齐板卡现态：v2.8.1 / hw=1 / layout=1 / boot=1 */
    device = default_device();
    device.current_vcode = 20801u;

    src_image = load_file(R9_SRC_IMG, &src_image_len);
    if (src_image == 0)
    {
        fprintf(stderr, "P2_6_R9_GATE ERROR source image load failed\n");
        return 2;
    }

    /* ---------- GOOD 正例 ---------- */
    golden_package = load_file(R9_GOOD_ETU, &golden_package_len);
    if (golden_package == 0)
    {
        fprintf(stderr, "P2_6_R9_GATE ERROR GOOD etu load failed\n");
        return 2;
    }
    reset_fixture();
    memset(&info, 0, sizeof(info));
    result = apply_with_device(&device, &info);
    printf("P2_6_R9_GATE kind=good result=%s package_len=%lu payload_len=%lu "
           "target_vcode=%lu image_len=%lu workspace_peak=%lu "
           "arena_peak_observed=%lu failed_request_size=%lu prepares=%lu "
           "programs=%lu acquires=%lu releases=%lu\n",
           ota_package_result_name(result),
           (unsigned long)info.package_len, (unsigned long)info.payload_len,
           (unsigned long)info.target_vcode, (unsigned long)info.image_len,
           (unsigned long)info.workspace_peak,
           (unsigned long)info.arena_peak_observed,
           (unsigned long)info.failed_request_size,
           (unsigned long)fixture.prepare_count,
           (unsigned long)fixture.program_count,
           (unsigned long)fixture.acquire_count,
           (unsigned long)fixture.release_count);
    r9_check("good result is ok", result == OTA_PACKAGE_OK);
    r9_check("good target_vcode=20802", info.target_vcode == 20802u);
    r9_check("good workspace_peak>0",
             info.workspace_peak != 0u &&
                 info.workspace_peak == info.arena_peak_observed);
    r9_check("good candidate equals source image",
             fixture.prepared_len == src_image_len &&
                 memcmp(fixture.candidate, src_image, src_image_len) == 0);
    r9_check("good candidate prepared and programmed",
             fixture.prepare_count != 0u && fixture.program_count != 0u);
    r9_check("good acquire/release paired",
             fixture.acquire_count == 1u && fixture.release_count == 1u);
    check_bcb_unchanged("good apply");
    free(golden_package);
    golden_package = 0;

    /* ---------- BAD 中途失败注入 ---------- */
    golden_package = load_file(R9_BAD_ETU, &golden_package_len);
    if (golden_package == 0)
    {
        fprintf(stderr, "P2_6_R9_GATE ERROR BAD etu load failed\n");
        return 2;
    }
    reset_fixture();
    memset(&info, 0, sizeof(info));
    result = apply_with_device(&device, &info);
    printf("P2_6_R9_GATE kind=bad result=%s workspace_peak=%lu "
           "arena_peak_observed=%lu failed_request_size=%lu prepares=%lu "
           "programs=%lu acquires=%lu releases=%lu workspace_zeroed=%u\n",
           ota_package_result_name(result),
           (unsigned long)info.workspace_peak,
           (unsigned long)info.arena_peak_observed,
           (unsigned long)info.failed_request_size,
           (unsigned long)fixture.prepare_count,
           (unsigned long)fixture.program_count,
           (unsigned long)fixture.acquire_count,
           (unsigned long)fixture.release_count,
           (unsigned)fixture.workspace_zeroed);
    r9_check("bad result is failure", result != OTA_PACKAGE_OK);
    r9_check("bad result is not payload_crc", result != OTA_PACKAGE_ERR_PAYLOAD_CRC);
    r9_check("bad outer crc passed (acquired once)",
             fixture.acquire_count == 1u);
    r9_check("bad workspace released exactly once",
             fixture.release_count == 1u);
    r9_check("bad workspace secured zeroed", fixture.workspace_zeroed == 1u);
    r9_check("bad arena initialized (peak observed)",
             info.arena_peak_observed != 0u);
    r9_check("bad failed after candidate_prepare",
             fixture.prepare_count >= 1u);
    r9_check("bad bcb untouched",
             memcmp(fixture.bcb, fixture.bcb_before,
                    sizeof(fixture.bcb)) == 0);
    free(golden_package);
    golden_package = 0;
    free(src_image);

    printf("P2_6_R9_GATE summary failures=%d status=%s\n", r9_failures,
           r9_failures == 0 ? "PASS" : "FAIL");
    return r9_failures == 0 ? 0 : 1;
}
