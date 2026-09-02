#include "HAL/HAL_OTA_Package.h"

#include "HAL/HAL.h"
#include "HAL/HAL_OTA_Backup.h"
#if defined(P2_2_TEST_ENABLE)
#include "EEPROM/eeprom_bcb.h"
#include "OTA/ota_p2_2_test.h"
#include "boot_crypto.h"
#endif
#if defined(P2_3_TEST_ENABLE)
#include "EEPROM/eeprom_bcb.h"
#include "OTA/ota_p2_3_test.h"
#include "boot_crypto.h"
#endif
#include "OTA/ota_staging.h"
#include "W25Q128/qspi_cmd_en25qh128a.h"
#if !defined(_WIN32)
#include "wdg.h"
#endif
#if defined(P2_6_TEST_ENABLE)
#include "SEGGER_RTT.h"
#include "StackInfo/StackInfo.h"
#include "lvgl/src/misc/lv_tlsf.h"
#include "lvgl/src/misc/lv_mem.h"
#endif

#include <stddef.h>
#include <stdint.h>
#include <string.h>

enum ota_overlay_owner_t
{
    OTA_OVERLAY_FREE = 0,
    OTA_OVERLAY_LIVE_MAP = 1,
    OTA_OVERLAY_PACKAGE = 2,
    OTA_OVERLAY_BLE = 3
};

typedef struct ota_package_port_context_t
{
    uint32_t candidate_prepares;
    uint32_t candidate_programs;
    uint32_t candidate_bytes;
} ota_package_port_context_t;

extern "C"
{
#if defined(__CC_ARM)
__attribute__((section(".ota_overlay"), zero_init, aligned(8)))
#elif defined(__GNUC__) && !defined(_WIN32)
__attribute__((section(".ota_overlay,\"aw\",%nobits @"), aligned(8)))
#endif
uint8_t g_ota_overlay_workspace[OTA_PACKAGE_WORKSPACE_SIZE];
}

static volatile uint8_t g_ota_overlay_owner = OTA_OVERLAY_FREE;
static ota_package_port_context_t g_ota_package_port;

#if defined(P2_6_TEST_ENABLE)
extern "C" uint32_t P2_6_sbrk_call_count(void);
extern "C" uintptr_t P2_6_sbrk_peak(void);

static volatile uint32_t P2_6_lv_tlsf_malloc_calls;
static volatile uint32_t P2_6_lv_tlsf_realloc_calls;
static volatile uint32_t P2_6_lv_tlsf_free_calls;
static volatile uint32_t P2_6_lv_tlsf_sequence;
static volatile size_t P2_6_last_tlsf_size;
static volatile uintptr_t P2_6_last_tlsf_return;

extern "C" void *__real_lv_tlsf_malloc(lv_tlsf_t tlsf, size_t size);
extern "C" void *__real_lv_tlsf_realloc(lv_tlsf_t tlsf, void *ptr,
                                          size_t size);
extern "C" size_t __real_lv_tlsf_free(lv_tlsf_t tlsf, const void *ptr);

extern "C" void *__wrap_lv_tlsf_malloc(lv_tlsf_t tlsf, size_t size)
{
    void *result;

    ++P2_6_lv_tlsf_malloc_calls;
    P2_6_last_tlsf_size = size;
    result = __real_lv_tlsf_malloc(tlsf, size);
    P2_6_last_tlsf_return = (uintptr_t)result;
    P2_6_lv_tlsf_sequence = P2_6_lv_tlsf_sequence * 5u + 1u;
    return result;
}

extern "C" void *__wrap_lv_tlsf_realloc(lv_tlsf_t tlsf, void *ptr,
                                          size_t size)
{
    void *result;

    ++P2_6_lv_tlsf_realloc_calls;
    P2_6_last_tlsf_size = size;
    result = __real_lv_tlsf_realloc(tlsf, ptr, size);
    P2_6_last_tlsf_return = (uintptr_t)result;
    P2_6_lv_tlsf_sequence = P2_6_lv_tlsf_sequence * 5u + 2u;
    return result;
}

extern "C" size_t __wrap_lv_tlsf_free(lv_tlsf_t tlsf, const void *ptr)
{
    size_t result = __real_lv_tlsf_free(tlsf, ptr);

    ++P2_6_lv_tlsf_free_calls;
    P2_6_last_tlsf_return = (uintptr_t)result;
    P2_6_lv_tlsf_sequence = P2_6_lv_tlsf_sequence * 5u + 3u;
    return result;
}

typedef struct ota_p2_6_measurement_t
{
    uint32_t valid;
    uint32_t kind;
    uint32_t entry_stack_peak;
    uint32_t exit_stack_peak;
    uint32_t stack_total;
    uint32_t entry_guard_intact;
    uint32_t exit_guard_intact;
    uint32_t entry_sbrk_calls;
    uint32_t exit_sbrk_calls;
    uintptr_t entry_sbrk_peak;
    uintptr_t exit_sbrk_peak;
    uint32_t entry_tlsf_malloc;
    uint32_t exit_tlsf_malloc;
    uint32_t entry_tlsf_realloc;
    uint32_t exit_tlsf_realloc;
    uint32_t entry_tlsf_free;
    uint32_t exit_tlsf_free;
    uint32_t tlsf_sequence;
    size_t last_tlsf_size;
    uintptr_t last_tlsf_return;
    lv_mem_monitor_t entry_mem;
    lv_mem_monitor_t exit_mem;
} ota_p2_6_measurement_t;

static ota_p2_6_measurement_t g_ota_p2_6_measurement;

extern "C" __attribute__((noinline, used))
uint32_t P2_6_StartupStackScanProbe(void)
{
    volatile uint32_t scratch[16];

    for (uint32_t index = 0u; index < 16u; ++index)
    {
        scratch[index] = 0xC13A0000u + index;
    }
    uint32_t usage = StackInfo_GetMaxUsageSize();
    __asm volatile("" : : "r"(scratch[0]) : "memory");
    return usage;
}

static void p2_6_measure_mem(lv_mem_monitor_t *monitor)
{
    memset(monitor, 0, sizeof(*monitor));
    lv_mem_monitor(monitor);
}

static void p2_6_measure_begin(uint32_t kind)
{
    memset(&g_ota_p2_6_measurement, 0,
           sizeof(g_ota_p2_6_measurement));
    g_ota_p2_6_measurement.kind = kind;
    g_ota_p2_6_measurement.stack_total = StackInfo_GetTotalSize();
    g_ota_p2_6_measurement.entry_stack_peak =
        StackInfo_GetMaxUsageSize();
    g_ota_p2_6_measurement.entry_guard_intact =
        StackInfo_IsGuardIntact();
    g_ota_p2_6_measurement.entry_sbrk_calls =
        P2_6_sbrk_call_count();
    g_ota_p2_6_measurement.entry_sbrk_peak = P2_6_sbrk_peak();
    g_ota_p2_6_measurement.entry_tlsf_malloc =
        P2_6_lv_tlsf_malloc_calls;
    g_ota_p2_6_measurement.entry_tlsf_realloc =
        P2_6_lv_tlsf_realloc_calls;
    g_ota_p2_6_measurement.entry_tlsf_free = P2_6_lv_tlsf_free_calls;
    p2_6_measure_mem(&g_ota_p2_6_measurement.entry_mem);
}

static void p2_6_measure_end(void)
{
    g_ota_p2_6_measurement.exit_stack_peak =
        StackInfo_GetMaxUsageSize();
    g_ota_p2_6_measurement.exit_guard_intact =
        StackInfo_IsGuardIntact();
    g_ota_p2_6_measurement.exit_sbrk_calls =
        P2_6_sbrk_call_count();
    g_ota_p2_6_measurement.exit_sbrk_peak = P2_6_sbrk_peak();
    g_ota_p2_6_measurement.exit_tlsf_malloc =
        P2_6_lv_tlsf_malloc_calls;
    g_ota_p2_6_measurement.exit_tlsf_realloc =
        P2_6_lv_tlsf_realloc_calls;
    g_ota_p2_6_measurement.exit_tlsf_free = P2_6_lv_tlsf_free_calls;
    g_ota_p2_6_measurement.tlsf_sequence = P2_6_lv_tlsf_sequence;
    g_ota_p2_6_measurement.last_tlsf_size = P2_6_last_tlsf_size;
    g_ota_p2_6_measurement.last_tlsf_return = P2_6_last_tlsf_return;
    p2_6_measure_mem(&g_ota_p2_6_measurement.exit_mem);
    g_ota_p2_6_measurement.valid = 1u;
}

static uint32_t p2_6_delta(uint32_t before, uint32_t after)
{
    return after - before;
}

static const char *p2_6_kind_name(uint32_t kind)
{
    return kind == 1u ? "full" : "patch";
}

static void p2_6_report_common(long result, const char *name,
                               uint32_t workspace_peak,
                               uint32_t arena_peak_observed,
                               uint32_t failed_request_size)
{
    const ota_p2_6_measurement_t *m = &g_ota_p2_6_measurement;

    if (!m->valid)
    {
        return;
    }
    SEGGER_RTT_printf(
        0,
        "P2_6 kind=%s result=%ld workspace_peak=%lu "
        "arena_peak_observed=%lu failed_request_size=%lu "
        "stack_entry=%lu stack_peak=%lu stack_total=%lu "
        "guard_entry=%lu guard_exit=%lu "
        "sbrk_delta=%lu sbrk_peak=%lu "
        "tlsf_malloc_delta=%lu tlsf_realloc_delta=%lu tlsf_free_delta=%lu "
        "lv_free_entry=%lu lv_free_exit=%lu lv_big_entry=%lu "
        "lv_big_exit=%lu lv_frag_entry=%u lv_frag_exit=%u "
        "lv_max_entry=%lu lv_max_exit=%lu seq=%lu last_size=%lu "
        "last_ret=0x%lX\r\n",
        name, result, (unsigned long)workspace_peak,
        (unsigned long)arena_peak_observed,
        (unsigned long)failed_request_size,
        (unsigned long)m->entry_stack_peak,
        (unsigned long)m->exit_stack_peak,
        (unsigned long)m->stack_total,
        (unsigned long)m->entry_guard_intact,
        (unsigned long)m->exit_guard_intact,
        (unsigned long)p2_6_delta(m->entry_sbrk_calls,
                                  m->exit_sbrk_calls),
        (unsigned long)m->exit_sbrk_peak,
        (unsigned long)p2_6_delta(m->entry_tlsf_malloc,
                                  m->exit_tlsf_malloc),
        (unsigned long)p2_6_delta(m->entry_tlsf_realloc,
                                  m->exit_tlsf_realloc),
        (unsigned long)p2_6_delta(m->entry_tlsf_free,
                                  m->exit_tlsf_free),
        (unsigned long)m->entry_mem.free_size,
        (unsigned long)m->exit_mem.free_size,
        (unsigned long)m->entry_mem.free_biggest_size,
        (unsigned long)m->exit_mem.free_biggest_size,
        (unsigned)m->entry_mem.frag_pct,
        (unsigned)m->exit_mem.frag_pct,
        (unsigned long)m->entry_mem.max_used,
        (unsigned long)m->exit_mem.max_used,
        (unsigned long)m->tlsf_sequence,
        (unsigned long)m->last_tlsf_size,
        (unsigned long)m->last_tlsf_return);
}
#endif

static void service_app_watchdog(void)
{
#if !defined(_WIN32) && CONFIG_WATCH_DOG_ENABLE
    /* Apply/backup are synchronous, so the main-loop watchdog task cannot run. */
    WDG_ReloadCounter();
#endif
}

static uint32_t enter_critical(void)
{
    uint32_t primask = __get_PRIMASK();
    __disable_irq();
    return primask;
}

static void leave_critical(uint32_t primask)
{
    if (primask == 0u)
    {
        __enable_irq();
    }
}

static bool overlay_acquire(uint8_t owner)
{
    uint32_t primask = enter_critical();
    bool acquired =
        (uintptr_t)g_ota_overlay_workspace ==
            (uintptr_t)OTA_OVERLAY_ORIGIN &&
        g_ota_overlay_owner == OTA_OVERLAY_FREE;

    if (acquired)
    {
        g_ota_overlay_owner = owner;
    }
    leave_critical(primask);
    return acquired;
}

static void overlay_release(uint8_t owner)
{
    uint32_t primask = enter_critical();

    if (g_ota_overlay_owner == owner)
    {
        g_ota_overlay_owner = OTA_OVERLAY_FREE;
    }
    leave_critical(primask);
}

static int qspi_restore_xip(void)
{
    int result;

    service_app_watchdog();
    result = en25qh128a_qspi_xip_init() == QSPI_OK ? 0 : -1;
    service_app_watchdog();
    return result;
}

static int package_range_ok(uint32_t offset, uint32_t len)
{
    return offset <= OTA_ETU_MAX_LENGTH &&
           len <= OTA_ETU_MAX_LENGTH - offset &&
           OTA_STAGING_PAYLOAD_OFFSET + offset <= OTA_EXT_STAGING_LENGTH &&
           len <= OTA_EXT_STAGING_LENGTH -
                      (OTA_STAGING_PAYLOAD_OFFSET + offset);
}

static int candidate_range_ok(uint32_t offset, uint32_t len)
{
    return offset <= OTA_APP_LENGTH && len <= OTA_APP_LENGTH - offset &&
           OTA_SLOT_HEADER_SIZE + offset <= OTA_EXT_SLOT_LENGTH &&
           len <= OTA_EXT_SLOT_LENGTH - (OTA_SLOT_HEADER_SIZE + offset);
}

static int package_read(void *ctx, uint32_t offset,
                        uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == 0 || !package_range_ok(offset, len) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    service_app_watchdog();
    memcpy(dst,
           (const void *)(QSPI1_MEM_BASE + OTA_EXT_STAGING +
                          OTA_STAGING_PAYLOAD_OFFSET + offset),
           len);
    service_app_watchdog();
    return 0;
}

static int candidate_prepare(void *ctx, uint32_t image_len)
{
    ota_package_port_context_t *port =
        (ota_package_port_context_t *)ctx;
    uint32_t erase_len;
    uint32_t offset;
    qspi_status_t result = QSPI_OK;
    int restore_result;

    (void)ctx;
    if (image_len == 0u || image_len > OTA_APP_LENGTH ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    erase_len = OTA_SLOT_HEADER_SIZE +
                ((image_len + OTA_STAGING_BLOCK_SIZE - 1u) &
                 ~(OTA_STAGING_BLOCK_SIZE - 1u));
    if (erase_len > OTA_EXT_SLOT_LENGTH)
    {
        return -1;
    }

    ++port->candidate_prepares;
    service_app_watchdog();
    qspi_xip_enable(QSPI1, FALSE);
    for (offset = 0u; offset < erase_len;
         offset += OTA_STAGING_BLOCK_SIZE)
    {
        service_app_watchdog();
        result = qspi_erase(OTA_EXT_CANDIDATE + offset);
        service_app_watchdog();
        if (result != QSPI_OK)
        {
            break;
        }
    }
    restore_result = qspi_restore_xip();
    return result == QSPI_OK && restore_result == 0 ? 0 : -1;
}

static int candidate_program(void *ctx, uint32_t offset,
                             const uint8_t *src, uint32_t len)
{
    ota_package_port_context_t *port =
        (ota_package_port_context_t *)ctx;
    qspi_status_t result;
    int restore_result;

    (void)ctx;
    if (src == 0 || len == 0u || !candidate_range_ok(offset, len) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    ++port->candidate_programs;
    port->candidate_bytes += len;
    service_app_watchdog();
    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_data_write(OTA_EXT_CANDIDATE + OTA_SLOT_HEADER_SIZE +
                                 offset,
                             len, (uint8_t *)src);
    service_app_watchdog();
    restore_result = qspi_restore_xip();
    return result == QSPI_OK && restore_result == 0 ? 0 : -1;
}

static int candidate_read(void *ctx, uint32_t offset,
                          uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == 0 || !candidate_range_ok(offset, len) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    service_app_watchdog();
    memcpy(dst,
           (const void *)(QSPI1_MEM_BASE + OTA_EXT_CANDIDATE +
                          OTA_SLOT_HEADER_SIZE + offset),
           len);
    service_app_watchdog();
    return 0;
}

static int workspace_acquire(void *ctx, uint8_t **workspace,
                             uint32_t *workspace_len)
{
    (void)ctx;
    if (workspace == 0 || workspace_len == 0 ||
        !overlay_acquire(OTA_OVERLAY_PACKAGE))
    {
        return -1;
    }
    *workspace = g_ota_overlay_workspace;
    *workspace_len = sizeof(g_ota_overlay_workspace);
    return 0;
}

static void workspace_release(void *ctx, uint8_t *workspace,
                              uint32_t workspace_len)
{
    (void)ctx;
    (void)workspace;
    (void)workspace_len;
    overlay_release(OTA_OVERLAY_PACKAGE);
}

bool HAL::OTA_OverlayAcquireLiveMap()
{
    return overlay_acquire(OTA_OVERLAY_LIVE_MAP);
}

void HAL::OTA_OverlayReleaseLiveMap()
{
    overlay_release(OTA_OVERLAY_LIVE_MAP);
}

/* P3-1 BLE 会话 overlay 通道：会话期间子分配 workspace 前部
 * （RX 环 + staging receiver），与 PACKAGE/LIVE_MAP 互斥。 */
bool HAL::OTA_OverlayAcquireBle()
{
    return overlay_acquire(OTA_OVERLAY_BLE);
}

void HAL::OTA_OverlayReleaseBle()
{
    overlay_release(OTA_OVERLAY_BLE);
}

uint8_t* HAL::OTA_OverlayGetWorkspace(uint32_t *out_size)
{
    if (out_size != 0)
    {
        *out_size = (uint32_t)sizeof(g_ota_overlay_workspace);
    }
    return g_ota_overlay_workspace;
}

bool HAL::OTA_OverlayIsOtaOwned()
{
    return g_ota_overlay_owner == OTA_OVERLAY_PACKAGE;
}

/* 基版镜像读：内部 flash XIP 直读当前运行 App。按块取到调用方的 1KiB 缓冲，
 * 不把整个基版镜像复制到 RAM（契约 §512）。 */
static int base_read(void *ctx, uint32_t offset,
                     uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == 0 || offset > OTA_APP_LENGTH ||
        len > OTA_APP_LENGTH - offset)
    {
        return -1;
    }
    service_app_watchdog();
    memcpy(dst, (const void *)(uintptr_t)(OTA_APP_ORIGIN + offset), len);
    service_app_watchdog();
    return 0;
}

/* ---- P2-5 backup/STAGED 槽 IO（candidate/backup 两槽域 + XIP + QSPI 双门） ---- */

static int backup_slot_range_ok(uint32_t address, uint32_t len,
                                int allow_zero_len)
{
    uint32_t slot_start;
    uint32_t slot_end;
    int in_candidate;
    int in_backup;

    /* 仅放行 candidate/backup 两槽域（OTA_EXT_CANDIDATE==0，无需 < 下界检查，
     * 避免 AC5 #186-D pointless comparison with zero）。 */
    in_candidate = address < OTA_EXT_CANDIDATE + OTA_EXT_SLOT_LENGTH;
    in_backup = address >= OTA_EXT_BACKUP &&
                address < OTA_EXT_BACKUP + OTA_EXT_SLOT_LENGTH;
    if (!in_candidate && !in_backup)
    {
        return 0;
    }
    slot_start = in_backup ? OTA_EXT_BACKUP : OTA_EXT_CANDIDATE;
    slot_end = slot_start + OTA_EXT_SLOT_LENGTH;
    if (len == 0u)
    {
        return allow_zero_len && address >= slot_start &&
               address <= slot_end;
    }
    return address <= slot_end && len <= slot_end - address;
}

static int backup_flash_read(void *ctx, uint32_t address,
                             uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == 0 || !backup_slot_range_ok(address, len, 0) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    service_app_watchdog();
    memcpy(dst, (const void *)(QSPI1_MEM_BASE + address), len);
    service_app_watchdog();
    return 0;
}

static int backup_flash_erase_4k(void *ctx, uint32_t address)
{
    qspi_status_t result;
    int restore_result;

    (void)ctx;
    if ((address & (OTA_SLOT_HEADER_SIZE - 1u)) != 0u ||
        !backup_slot_range_ok(address, OTA_SLOT_HEADER_SIZE, 0) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    service_app_watchdog();
    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_erase(address);
    service_app_watchdog();
    restore_result = qspi_restore_xip();
    return result == QSPI_OK && restore_result == 0 ? 0 : -1;
}

static int backup_flash_program(void *ctx, uint32_t address,
                                const uint8_t *src, uint32_t len)
{
    qspi_status_t result;
    int restore_result;

    (void)ctx;
    if (src == 0 || len == 0u ||
        !backup_slot_range_ok(address, len, 0) ||
        HAL::Qspi_IsOtaDisabled())
    {
        return -1;
    }
    service_app_watchdog();
    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_data_write(address, len, (uint8_t *)src);
    service_app_watchdog();
    restore_result = qspi_restore_xip();
    return result == QSPI_OK && restore_result == 0 ? 0 : -1;
}

ota_backup_result_t HAL::OTA_BackupStage(ota_backup_info_t *out)
{
    ota_backup_io_t io;

    if (Qspi_IsOtaDisabled() || qspi_restore_xip() != 0)
    {
        return OTA_BACKUP_ERR_DISABLED;
    }
    memset(&io, 0, sizeof(io));
    io.ctx = 0;
    io.app_read = base_read;
    io.flash_read = backup_flash_read;
    io.flash_erase_4k = backup_flash_erase_4k;
    io.flash_program = backup_flash_program;
    return ota_backup_stage(&io, HAL::OTA_GetBcbHal(), out);
}

ota_package_result_t HAL::OTA_PackageApplyStaging(
    uint32_t package_len,
    uint32_t current_vcode,
    ota_package_info_t *out_info)
{
    ota_package_io_t io;
    ota_package_device_t device;
#if defined(P2_6_TEST_ENABLE)
    p2_6_measure_begin(1u);
#endif

    if (Qspi_IsOtaDisabled() || qspi_restore_xip() != 0)
    {
#if defined(P2_6_TEST_ENABLE)
        p2_6_measure_end();
#endif
        return OTA_PACKAGE_ERR_READ;
    }
    memset(&g_ota_package_port, 0, sizeof(g_ota_package_port));
    io.ctx = &g_ota_package_port;
    io.package_read = package_read;
    io.candidate_prepare = candidate_prepare;
    io.candidate_program = candidate_program;
    io.candidate_read = candidate_read;
    io.workspace_acquire = workspace_acquire;
    io.workspace_release = workspace_release;
    device.current_vcode = current_vcode;
    device.hardware_rev = 1u;
    device.layout_id = 1u;
    device.boot_version = 1u;
    ota_package_result_t result =
        ota_package_apply_full(&io, &device, package_len, out_info);
#if defined(P2_6_TEST_ENABLE)
    p2_6_measure_end();
#endif
    return result;
}

ota_patch_result_t HAL::OTA_PatchApplyStaging(
    uint32_t package_len,
    uint32_t current_vcode,
    uint32_t base_image_len,
    const uint8_t base_image_sha8[OTA_PATCH_BASE_SHA8_SIZE],
    ota_patch_info_t *out_info)
{
    ota_patch_io_t io;
    ota_patch_device_t device;
#if defined(P2_6_TEST_ENABLE)
    p2_6_measure_begin(2u);
#endif

    if (base_image_sha8 == 0)
    {
#if defined(P2_6_TEST_ENABLE)
        p2_6_measure_end();
#endif
        return OTA_PATCH_ERR_ARGUMENT;
    }
    if (Qspi_IsOtaDisabled() || qspi_restore_xip() != 0)
    {
#if defined(P2_6_TEST_ENABLE)
        p2_6_measure_end();
#endif
        return OTA_PATCH_ERR_READ;
    }
    memset(&g_ota_package_port, 0, sizeof(g_ota_package_port));
    io.ctx = &g_ota_package_port;
    io.package_read = package_read;
    io.base_read = base_read;
    io.candidate_prepare = candidate_prepare;
    io.candidate_program = candidate_program;
    io.candidate_read = candidate_read;
    io.workspace_acquire = workspace_acquire;
    io.workspace_release = workspace_release;
    device.current_vcode = current_vcode;
    device.hardware_rev = 1u;
    device.layout_id = 1u;
    device.boot_version = 1u;
    device.base_image_len = base_image_len;
    memcpy(device.base_image_sha8, base_image_sha8,
           sizeof(device.base_image_sha8));
    ota_patch_result_t result =
        ota_patch_apply(&io, &device, package_len, out_info);
#if defined(P2_6_TEST_ENABLE)
    p2_6_measure_end();
#endif
    return result;
}

#if defined(P2_6_TEST_ENABLE)
void HAL::OTA_P2_6_ReportPackageApply(
    ota_package_result_t result, const ota_package_info_t *info)
{
    ota_package_info_t empty;

    memset(&empty, 0, sizeof(empty));
    if (info == 0)
    {
        info = &empty;
    }
    p2_6_report_common((long)result, p2_6_kind_name(1u),
                       info->workspace_peak,
                       info->arena_peak_observed,
                       info->failed_request_size);
}

void HAL::OTA_P2_6_ReportPatchApply(
    ota_patch_result_t result, const ota_patch_info_t *info)
{
    ota_patch_info_t empty;

    memset(&empty, 0, sizeof(empty));
    if (info == 0)
    {
        info = &empty;
    }
    p2_6_report_common((long)result, p2_6_kind_name(2u),
                       info->workspace_peak,
                       info->arena_peak_observed,
                       info->failed_request_size);
}
#endif

#if defined(P2_2_TEST_ENABLE)
static uint32_t evidence_control_crc(uint32_t offset, uint32_t len)
{
    return boot_crc32(
        (const uint8_t *)(uintptr_t)(OTA_P2_2_CONTROL_ADDRESS + offset),
        len);
}

static void evidence_write_bytes(uint32_t offset,
                                 const uint8_t *src, uint32_t len)
{
    volatile uint8_t *control = ota_p2_2_control();
    uint32_t index;

    for (index = 0u; index < len; ++index)
    {
        control[offset + index] = src[index];
    }
}

static int evidence_command_valid(void)
{
    uint32_t package_len = ota_p2_2_read_u32(OTA_P2_2_OFF_PACKAGE_LEN);
    uint32_t opcode = ota_p2_2_read_u32(OTA_P2_2_OFF_OPCODE);
    uint32_t cookie = ota_p2_2_read_u32(OTA_P2_2_OFF_COOKIE);

    return ota_p2_2_read_u32(OTA_P2_2_OFF_MAGIC) ==
               OTA_P2_2_COMMAND_MAGIC &&
           ota_p2_2_read_u32(OTA_P2_2_OFF_VERSION) == OTA_P2_2_VERSION &&
           opcode == OTA_P2_2_OPCODE_APPLY &&
           (opcode ^ ota_p2_2_read_u32(
                         OTA_P2_2_OFF_OPCODE_INVERSE)) == UINT32_MAX &&
           cookie == OTA_P2_2_COOKIE &&
           (cookie ^ ota_p2_2_read_u32(
                         OTA_P2_2_OFF_COOKIE_INVERSE)) == UINT32_MAX &&
           package_len >= OTA_PACKAGE_HEADER_SIZE &&
           package_len <= OTA_P2_2_PACKAGE_CAPACITY &&
           ota_p2_2_read_u32(OTA_P2_2_OFF_COMMAND_CRC32) ==
               evidence_control_crc(OTA_P2_2_COMMAND_CRC_OFFSET,
                                    OTA_P2_2_COMMAND_CRC_LENGTH) &&
           ota_p2_2_read_u32(OTA_P2_2_OFF_PACKAGE_CRC32) ==
               evidence_control_crc(OTA_P2_2_PACKAGE_OFFSET,
                                    package_len);
}

static int evidence_read_bcb(uint8_t raw[OTA_P2_2_BCB_SNAPSHOT_SIZE])
{
    return HAL::EEPROM_ReadBufferSafe(BCB_A_ADDR, raw, BCB_SIZE) &&
           HAL::EEPROM_ReadBufferSafe(BCB_B_ADDR, raw + BCB_SIZE,
                                      BCB_SIZE);
}

static int evidence_stage_package(uint32_t package_len)
{
    const uint8_t *package =
        (const uint8_t *)(uintptr_t)(OTA_P2_2_CONTROL_ADDRESS +
                                    OTA_P2_2_PACKAGE_OFFSET);
    uint32_t address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    qspi_status_t result;
    int restore_result;

    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_erase(address);
    if (result == QSPI_OK)
    {
        result = qspi_data_write(address, package_len,
                                 (uint8_t *)package);
    }
    restore_result = qspi_restore_xip();
    if (result != QSPI_OK || restore_result != 0)
    {
        return -1;
    }
    return memcmp((const void *)(QSPI1_MEM_BASE + address), package,
                  package_len) == 0
               ? 0
               : -1;
}

static int evidence_workspace_zero(void)
{
    volatile const uint8_t *workspace = g_ota_overlay_workspace;
    uint32_t index;

    for (index = 0u; index < sizeof(g_ota_overlay_workspace); ++index)
    {
        if (workspace[index] != 0u)
        {
            return 0;
        }
    }
    return 1;
}

static int evidence_candidate_header_erased(void)
{
    volatile const uint8_t *header =
        (volatile const uint8_t *)(QSPI1_MEM_BASE + OTA_EXT_CANDIDATE);
    uint32_t index;

    for (index = 0u; index < OTA_SLOT_HEADER_SIZE; ++index)
    {
        if (header[index] != 0xFFu)
        {
            return 0;
        }
    }
    return 1;
}

static void evidence_finish(uint32_t status, uint32_t detail)
{
    ota_p2_2_write_u32(OTA_P2_2_OFF_DETAIL, detail);
    ota_p2_2_write_u32(OTA_P2_2_OFF_STATUS, status);
    ota_p2_2_write_u32(
        OTA_P2_2_OFF_RESULT_CRC32,
        evidence_control_crc(OTA_P2_2_RESULT_CRC_OFFSET,
                             OTA_P2_2_RESULT_CRC_LENGTH));
    __asm volatile("dsb 0xF" ::: "memory");
    ota_p2_2_write_u32(OTA_P2_2_OFF_MAGIC, OTA_P2_2_DONE_MAGIC);
    __asm volatile("dsb 0xF\nisb 0xF" ::: "memory");
}

extern "C" void HAL_OTA_PackageEvidenceReady(void)
    __attribute__((noinline, noclone, used, externally_visible));

extern "C" void HAL_OTA_PackageEvidenceReady(void)
{
    __asm volatile("nop" ::: "memory");
}

extern "C" void HAL_OTA_PackageEvidenceDone(void)
    __attribute__((noinline, noclone, used, externally_visible));

extern "C" void HAL_OTA_PackageEvidenceDone(void)
{
    volatile uint32_t status =
        ota_p2_2_read_u32(OTA_P2_2_OFF_STATUS);

    (void)status;
    __asm volatile("nop" ::: "memory");
}

bool HAL::OTA_PackageEvidenceRun()
{
    uint8_t bcb_before[OTA_P2_2_BCB_SNAPSHOT_SIZE];
    uint8_t bcb_after[OTA_P2_2_BCB_SNAPSHOT_SIZE];
    ota_package_info_t info;
    ota_package_result_t actual = OTA_PACKAGE_ERR_READ;
    int32_t expected;
    uint32_t package_len;
    uint32_t current_vcode;
    uint32_t actual_package_crc;
    uint32_t detail = 0u;
    uint32_t staging_erases = 0u;
    uint32_t staging_programs = 0u;
    int bcb_before_ok;
    int bcb_after_ok;
    int bcb_equal;
    int workspace_zero;
    int header_erased;

    if (!evidence_command_valid())
    {
        return false;
    }

    package_len = ota_p2_2_read_u32(OTA_P2_2_OFF_PACKAGE_LEN);
    current_vcode = ota_p2_2_read_u32(OTA_P2_2_OFF_CURRENT_VCODE);
    expected = (int32_t)ota_p2_2_read_u32(
        OTA_P2_2_OFF_EXPECTED_RESULT);
    actual_package_crc = evidence_control_crc(OTA_P2_2_PACKAGE_OFFSET,
                                              package_len);
    ota_p2_2_write_u32(OTA_P2_2_OFF_STATUS, OTA_P2_2_STATUS_RUNNING);
    ota_p2_2_write_u32(OTA_P2_2_OFF_DETAIL, 0u);
    memset(&info, 0, sizeof(info));
    memset(bcb_before, 0, sizeof(bcb_before));
    memset(bcb_after, 0, sizeof(bcb_after));

    bcb_before_ok = evidence_read_bcb(bcb_before);
    if (!bcb_before_ok)
    {
        detail = 0x10u;
    }
    else
    {
        evidence_write_bytes(OTA_P2_2_OFF_BCB_BEFORE, bcb_before,
                             sizeof(bcb_before));
    }

    if (detail == 0u)
    {
        if (evidence_stage_package(package_len) != 0)
        {
            detail = 0x20u;
        }
        else
        {
            staging_erases = 1u;
            staging_programs = 1u;
            actual = OTA_PackageApplyStaging(package_len, current_vcode,
                                             &info);
        }
    }

    bcb_after_ok = evidence_read_bcb(bcb_after);
    if (bcb_after_ok)
    {
        evidence_write_bytes(OTA_P2_2_OFF_BCB_AFTER, bcb_after,
                             sizeof(bcb_after));
    }
    else if (detail == 0u)
    {
        detail = 0x30u;
    }

    bcb_equal = bcb_before_ok && bcb_after_ok &&
                memcmp(bcb_before, bcb_after, sizeof(bcb_before)) == 0;
    workspace_zero = evidence_workspace_zero();
    header_erased = evidence_candidate_header_erased();

    ota_p2_2_write_u32(OTA_P2_2_OFF_ACTUAL_RESULT,
                       (uint32_t)(int32_t)actual);
    ota_p2_2_write_u32(OTA_P2_2_OFF_TARGET_VCODE, info.target_vcode);
    ota_p2_2_write_u32(OTA_P2_2_OFF_IMAGE_LEN, info.image_len);
    ota_p2_2_write_u32(OTA_P2_2_OFF_WORKSPACE_PEAK,
                       info.workspace_peak);
    ota_p2_2_write_u32(OTA_P2_2_OFF_PAYLOAD_LEN, info.payload_len);
    ota_p2_2_write_u32(OTA_P2_2_OFF_PAYLOAD_CRC32,
                       info.payload_crc32);
    ota_p2_2_write_u32(OTA_P2_2_OFF_CANDIDATE_PREPARES,
                       g_ota_package_port.candidate_prepares);
    ota_p2_2_write_u32(OTA_P2_2_OFF_CANDIDATE_PROGRAMS,
                       g_ota_package_port.candidate_programs);
    ota_p2_2_write_u32(OTA_P2_2_OFF_CANDIDATE_BYTES,
                       g_ota_package_port.candidate_bytes);
    ota_p2_2_write_u32(OTA_P2_2_OFF_STAGING_ERASES,
                       staging_erases);
    ota_p2_2_write_u32(OTA_P2_2_OFF_STAGING_PROGRAMS,
                       staging_programs);
    ota_p2_2_write_u32(OTA_P2_2_OFF_WORKSPACE_ZERO,
                       (uint32_t)workspace_zero);
    ota_p2_2_write_u32(OTA_P2_2_OFF_CANDIDATE_HEADER_ERASED,
                       (uint32_t)header_erased);
    ota_p2_2_write_u32(OTA_P2_2_OFF_BCB_EQUAL, (uint32_t)bcb_equal);
    ota_p2_2_write_u32(OTA_P2_2_OFF_ACTUAL_PACKAGE_CRC32,
                       actual_package_crc);
    evidence_write_bytes(OTA_P2_2_OFF_IMAGE_SHA256,
                         info.image_sha256, sizeof(info.image_sha256));

    if (detail == 0u && (int32_t)actual != expected)
    {
        detail = 0x40u;
    }
    if (detail == 0u && !bcb_equal)
    {
        detail = 0x41u;
    }
    if (detail == 0u && !workspace_zero)
    {
        detail = 0x42u;
    }
    if (detail == 0u && actual == OTA_PACKAGE_OK &&
        (!header_erased || info.target_vcode != 20800u ||
         info.image_len != 4096u ||
         g_ota_package_port.candidate_prepares != 1u ||
         g_ota_package_port.candidate_programs != 4u ||
         g_ota_package_port.candidate_bytes != 4096u))
    {
        detail = 0x43u;
    }
    if (detail == 0u && actual != OTA_PACKAGE_OK &&
        (g_ota_package_port.candidate_prepares != 0u ||
         g_ota_package_port.candidate_programs != 0u ||
         g_ota_package_port.candidate_bytes != 0u))
    {
        detail = 0x44u;
    }

    SEGGER_RTT_printf(
        0,
        "P2_2: actual=%ld expected=%ld detail=0x%02lX "
        "prepare=%lu program=%lu bytes=%lu bcb=%u wipe=%u\r\n",
        (long)actual, (long)expected, (unsigned long)detail,
        (unsigned long)g_ota_package_port.candidate_prepares,
        (unsigned long)g_ota_package_port.candidate_programs,
        (unsigned long)g_ota_package_port.candidate_bytes,
        (unsigned)bcb_equal, (unsigned)workspace_zero);
    evidence_finish(detail == 0u ? OTA_P2_2_STATUS_PASS
                                 : OTA_P2_2_STATUS_FAIL,
                    detail);
    HAL_OTA_PackageEvidenceDone();
    return true;
}
#endif

#if defined(P2_3_TEST_ENABLE)
/* P2-3 差分取证 harness：结构与 P2-2 同构，只多出内层头/基版身份回填。
 * 基版镜像取当前运行 App（XIP），身份由 harness 侧现算，不预置常量。 */
static uint32_t p2_3_control_crc(uint32_t offset, uint32_t len)
{
    return boot_crc32(
        (const uint8_t *)(uintptr_t)(OTA_P2_3_CONTROL_ADDRESS + offset),
        len);
}

static void p2_3_write_bytes(uint32_t offset,
                             const uint8_t *src, uint32_t len)
{
    volatile uint8_t *control = ota_p2_3_control();
    uint32_t index;

    for (index = 0u; index < len; ++index)
    {
        control[offset + index] = src[index];
    }
}

static int p2_3_command_valid(void)
{
    uint32_t package_len = ota_p2_3_read_u32(OTA_P2_3_OFF_PACKAGE_LEN);
    uint32_t opcode = ota_p2_3_read_u32(OTA_P2_3_OFF_OPCODE);
    uint32_t cookie = ota_p2_3_read_u32(OTA_P2_3_OFF_COOKIE);

    return ota_p2_3_read_u32(OTA_P2_3_OFF_MAGIC) ==
               OTA_P2_3_COMMAND_MAGIC &&
           ota_p2_3_read_u32(OTA_P2_3_OFF_VERSION) == OTA_P2_3_VERSION &&
           opcode == OTA_P2_3_OPCODE_APPLY &&
           (opcode ^ ota_p2_3_read_u32(
                         OTA_P2_3_OFF_OPCODE_INVERSE)) == UINT32_MAX &&
           cookie == OTA_P2_3_COOKIE &&
           (cookie ^ ota_p2_3_read_u32(
                         OTA_P2_3_OFF_COOKIE_INVERSE)) == UINT32_MAX &&
           package_len >= OTA_PATCH_HEADER_SIZE &&
           package_len <= OTA_P2_3_PACKAGE_CAPACITY &&
           ota_p2_3_read_u32(OTA_P2_3_OFF_COMMAND_CRC32) ==
               p2_3_control_crc(OTA_P2_3_COMMAND_CRC_OFFSET,
                                OTA_P2_3_COMMAND_CRC_LENGTH) &&
           ota_p2_3_read_u32(OTA_P2_3_OFF_PACKAGE_CRC32) ==
               p2_3_control_crc(OTA_P2_3_PACKAGE_OFFSET, package_len);
}

static int p2_3_read_bcb(uint8_t raw[OTA_P2_3_BCB_SNAPSHOT_SIZE])
{
    return HAL::EEPROM_ReadBufferSafe(BCB_A_ADDR, raw, BCB_SIZE) &&
           HAL::EEPROM_ReadBufferSafe(BCB_B_ADDR, raw + BCB_SIZE,
                                      BCB_SIZE);
}

static int p2_3_stage_package(uint32_t package_len)
{
    const uint8_t *package =
        (const uint8_t *)(uintptr_t)(OTA_P2_3_CONTROL_ADDRESS +
                                    OTA_P2_3_PACKAGE_OFFSET);
    uint32_t address = OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;
    qspi_status_t result;
    int restore_result;

    qspi_xip_enable(QSPI1, FALSE);
    result = qspi_erase(address);
    if (result == QSPI_OK)
    {
        result = qspi_data_write(address, package_len,
                                 (uint8_t *)package);
    }
    restore_result = qspi_restore_xip();
    if (result != QSPI_OK || restore_result != 0)
    {
        return -1;
    }
    return memcmp((const void *)(QSPI1_MEM_BASE + address), package,
                  package_len) == 0
               ? 0
               : -1;
}

static int p2_3_workspace_zero(void)
{
    volatile const uint8_t *workspace = g_ota_overlay_workspace;
    uint32_t index;

    for (index = 0u; index < sizeof(g_ota_overlay_workspace); ++index)
    {
        if (workspace[index] != 0u)
        {
            return 0;
        }
    }
    return 1;
}

static int p2_3_candidate_header_erased(void)
{
    volatile const uint8_t *header =
        (volatile const uint8_t *)(QSPI1_MEM_BASE + OTA_EXT_CANDIDATE);
    uint32_t index;

    for (index = 0u; index < OTA_SLOT_HEADER_SIZE; ++index)
    {
        if (header[index] != 0xFFu)
        {
            return 0;
        }
    }
    return 1;
}

/* 当前运行镜像身份：整镜像 SHA-256 前 8B，按 1KiB 块 XIP 读，不整镜像入 RAM。 */
static int p2_3_base_identity(uint32_t base_len,
                              uint8_t sha8[OTA_PATCH_BASE_SHA8_SIZE])
{
    boot_sha256_ctx_t sha;
    uint8_t digest[32];
    uint8_t block[256];
    uint32_t offset = 0u;

    if (base_len == 0u || base_len > OTA_APP_LENGTH)
    {
        return -1;
    }
    boot_sha256_init(&sha);
    while (offset < base_len)
    {
        uint32_t take = base_len - offset;

        if (take > sizeof(block))
        {
            take = (uint32_t)sizeof(block);
        }
        if (base_read(0, offset, block, take) != 0)
        {
            return -1;
        }
        boot_sha256_update(&sha, block, take);
        offset += take;
    }
    boot_sha256_final(&sha, digest);
    memcpy(sha8, digest, OTA_PATCH_BASE_SHA8_SIZE);
    return 0;
}

static void p2_3_finish(uint32_t status, uint32_t detail)
{
    ota_p2_3_write_u32(OTA_P2_3_OFF_DETAIL, detail);
    ota_p2_3_write_u32(OTA_P2_3_OFF_STATUS, status);
    ota_p2_3_write_u32(
        OTA_P2_3_OFF_RESULT_CRC32,
        p2_3_control_crc(OTA_P2_3_RESULT_CRC_OFFSET,
                         OTA_P2_3_RESULT_CRC_LENGTH));
    __asm volatile("dsb 0xF" ::: "memory");
    ota_p2_3_write_u32(OTA_P2_3_OFF_MAGIC, OTA_P2_3_DONE_MAGIC);
    __asm volatile("dsb 0xF\nisb 0xF" ::: "memory");
}

extern "C" void HAL_OTA_PatchEvidenceReady(void)
    __attribute__((noinline, noclone, used, externally_visible));

extern "C" void HAL_OTA_PatchEvidenceReady(void)
{
    __asm volatile("nop" ::: "memory");
}

extern "C" void HAL_OTA_PatchEvidenceDone(void)
    __attribute__((noinline, noclone, used, externally_visible));

extern "C" void HAL_OTA_PatchEvidenceDone(void)
{
    volatile uint32_t status = ota_p2_3_read_u32(OTA_P2_3_OFF_STATUS);

    (void)status;
    __asm volatile("nop" ::: "memory");
}

bool HAL::OTA_PatchEvidenceRun()
{
    uint8_t bcb_before[OTA_P2_3_BCB_SNAPSHOT_SIZE];
    uint8_t bcb_after[OTA_P2_3_BCB_SNAPSHOT_SIZE];
    uint8_t base_sha8[OTA_PATCH_BASE_SHA8_SIZE];
    ota_patch_info_t info;
    ota_patch_result_t actual = OTA_PATCH_ERR_READ;
    int32_t expected;
    uint32_t package_len;
    uint32_t current_vcode;
    uint32_t base_len;
    uint32_t actual_package_crc;
    uint32_t detail = 0u;
    uint32_t staging_erases = 0u;
    uint32_t staging_programs = 0u;
    int bcb_before_ok;
    int bcb_after_ok;
    int bcb_equal;
    int workspace_zero;
    int header_erased;

    if (!p2_3_command_valid())
    {
        return false;
    }

    package_len = ota_p2_3_read_u32(OTA_P2_3_OFF_PACKAGE_LEN);
    current_vcode = ota_p2_3_read_u32(OTA_P2_3_OFF_CURRENT_VCODE);
    base_len = ota_p2_3_read_u32(OTA_P2_3_OFF_BASE_LEN);
    expected = (int32_t)ota_p2_3_read_u32(OTA_P2_3_OFF_EXPECTED_RESULT);
    actual_package_crc = p2_3_control_crc(OTA_P2_3_PACKAGE_OFFSET,
                                          package_len);
    ota_p2_3_write_u32(OTA_P2_3_OFF_STATUS, OTA_P2_3_STATUS_RUNNING);
    ota_p2_3_write_u32(OTA_P2_3_OFF_DETAIL, 0u);
    memset(&info, 0, sizeof(info));
    memset(bcb_before, 0, sizeof(bcb_before));
    memset(bcb_after, 0, sizeof(bcb_after));
    memset(base_sha8, 0, sizeof(base_sha8));

    bcb_before_ok = p2_3_read_bcb(bcb_before);
    if (!bcb_before_ok)
    {
        detail = 0x10u;
    }
    else
    {
        p2_3_write_bytes(OTA_P2_3_OFF_BCB_BEFORE, bcb_before,
                         sizeof(bcb_before));
    }

    if (detail == 0u && p2_3_base_identity(base_len, base_sha8) != 0)
    {
        detail = 0x18u;
    }
    if (detail == 0u)
    {
        p2_3_write_bytes(OTA_P2_3_OFF_BASE_SHA8, base_sha8,
                         sizeof(base_sha8));
        if (p2_3_stage_package(package_len) != 0)
        {
            detail = 0x20u;
        }
        else
        {
            staging_erases = 1u;
            staging_programs = 1u;
            actual = OTA_PatchApplyStaging(package_len, current_vcode,
                                           base_len, base_sha8, &info);
        }
    }

    bcb_after_ok = p2_3_read_bcb(bcb_after);
    if (bcb_after_ok)
    {
        p2_3_write_bytes(OTA_P2_3_OFF_BCB_AFTER, bcb_after,
                         sizeof(bcb_after));
    }
    else if (detail == 0u)
    {
        detail = 0x30u;
    }

    bcb_equal = bcb_before_ok && bcb_after_ok &&
                memcmp(bcb_before, bcb_after, sizeof(bcb_before)) == 0;
    workspace_zero = p2_3_workspace_zero();
    header_erased = p2_3_candidate_header_erased();

    ota_p2_3_write_u32(OTA_P2_3_OFF_ACTUAL_RESULT,
                       (uint32_t)(int32_t)actual);
    ota_p2_3_write_u32(OTA_P2_3_OFF_TARGET_VCODE, info.target_vcode);
    ota_p2_3_write_u32(OTA_P2_3_OFF_IMAGE_LEN, info.image_len);
    ota_p2_3_write_u32(OTA_P2_3_OFF_WORKSPACE_PEAK, info.workspace_peak);
    ota_p2_3_write_u32(OTA_P2_3_OFF_PAYLOAD_LEN, info.payload_len);
    ota_p2_3_write_u32(OTA_P2_3_OFF_PAYLOAD_CRC32, info.payload_crc32);
    ota_p2_3_write_u32(OTA_P2_3_OFF_BASE_VCODE, info.base_vcode);
    ota_p2_3_write_u32(OTA_P2_3_OFF_BASE_CRC32, info.base_crc32);
    ota_p2_3_write_u32(OTA_P2_3_OFF_IMAGE_CRC32, info.image_crc32);
    ota_p2_3_write_u32(OTA_P2_3_OFF_PATCH_STREAM_LEN,
                       info.patch_stream_len);
    ota_p2_3_write_u32(OTA_P2_3_OFF_DECODED_LEN, info.decoded_len);
    ota_p2_3_write_u32(OTA_P2_3_OFF_CANDIDATE_PREPARES,
                       g_ota_package_port.candidate_prepares);
    ota_p2_3_write_u32(OTA_P2_3_OFF_CANDIDATE_PROGRAMS,
                       g_ota_package_port.candidate_programs);
    ota_p2_3_write_u32(OTA_P2_3_OFF_CANDIDATE_BYTES,
                       g_ota_package_port.candidate_bytes);
    ota_p2_3_write_u32(OTA_P2_3_OFF_STAGING_ERASES, staging_erases);
    ota_p2_3_write_u32(OTA_P2_3_OFF_STAGING_PROGRAMS, staging_programs);
    ota_p2_3_write_u32(OTA_P2_3_OFF_WORKSPACE_ZERO,
                       (uint32_t)workspace_zero);
    ota_p2_3_write_u32(OTA_P2_3_OFF_CANDIDATE_HEADER_ERASED,
                       (uint32_t)header_erased);
    ota_p2_3_write_u32(OTA_P2_3_OFF_BCB_EQUAL, (uint32_t)bcb_equal);
    ota_p2_3_write_u32(OTA_P2_3_OFF_ACTUAL_PACKAGE_CRC32,
                       actual_package_crc);
    p2_3_write_bytes(OTA_P2_3_OFF_IMAGE_SHA256, info.image_sha256,
                     sizeof(info.image_sha256));

    if (detail == 0u && (int32_t)actual != expected)
    {
        detail = 0x40u;
    }
    if (detail == 0u && !bcb_equal)
    {
        detail = 0x41u;
    }
    if (detail == 0u && !workspace_zero)
    {
        detail = 0x42u;
    }
    if (detail == 0u && actual == OTA_PATCH_OK &&
        (!header_erased || info.target_vcode != 20800u ||
         info.base_vcode != 20700u || info.image_len != 4096u ||
         info.base_len != 4096u || info.decoded_len != 4120u ||
         info.workspace_peak > OTA_PATCH_WORKSPACE_SIZE ||
         g_ota_package_port.candidate_prepares != 1u ||
         g_ota_package_port.candidate_bytes != 4096u))
    {
        detail = 0x43u;
    }
    if (detail == 0u && actual != OTA_PATCH_OK &&
        (g_ota_package_port.candidate_prepares != 0u ||
         g_ota_package_port.candidate_programs != 0u ||
         g_ota_package_port.candidate_bytes != 0u))
    {
        detail = 0x44u;
    }

    SEGGER_RTT_printf(
        0,
        "P2_3: actual=%ld expected=%ld detail=0x%02lX "
        "prepare=%lu program=%lu bytes=%lu peak=%lu bcb=%u wipe=%u\r\n",
        (long)actual, (long)expected, (unsigned long)detail,
        (unsigned long)g_ota_package_port.candidate_prepares,
        (unsigned long)g_ota_package_port.candidate_programs,
        (unsigned long)g_ota_package_port.candidate_bytes,
        (unsigned long)info.workspace_peak,
        (unsigned)bcb_equal, (unsigned)workspace_zero);
    p2_3_finish(detail == 0u ? OTA_P2_3_STATUS_PASS
                             : OTA_P2_3_STATUS_FAIL,
                detail);
    HAL_OTA_PatchEvidenceDone();
    return true;
}
#endif
