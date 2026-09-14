#include "OTA/ota_ble_session.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* NOR flash 模拟与 test_ota_sd.c 同一模式：program 只能清位、erase 整页
 * 置 FF，全部操作记录日志供幂等性断言使用。 */

enum
{
    OP_ERASE = 1,
    OP_PROGRAM = 2,
    MAX_OPS = 8192,
    TX_MAX = 256
};

typedef struct operation_t
{
    int type;
    uint32_t address;
    uint32_t len;
} operation_t;

typedef struct flash_fixture_t
{
    uint8_t bytes[OTA_EXT_STAGING_LENGTH];
    operation_t operations[MAX_OPS];
    uint32_t operation_count;
} flash_fixture_t;

static flash_fixture_t flash_fixture;

static int checks;
static int failures;

static void check(const char *name, int condition)
{
    ++checks;
    printf("  %-68s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
    {
        ++failures;
    }
}

static uint32_t read_u32le(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static void write_u32le(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static int flash_range_ok(uint32_t address, uint32_t len)
{
    return address >= OTA_EXT_STAGING &&
           len <= OTA_EXT_STAGING_LENGTH &&
           address - OTA_EXT_STAGING <= OTA_EXT_STAGING_LENGTH - len;
}

static void record_operation(int type, uint32_t address, uint32_t len)
{
    if (flash_fixture.operation_count < MAX_OPS)
    {
        operation_t *operation =
            &flash_fixture.operations[flash_fixture.operation_count++];
        operation->type = type;
        operation->address = address;
        operation->len = len;
    }
}

static int flash_read(void *ctx, uint32_t address,
                      uint8_t *dst, uint32_t len)
{
    (void)ctx;
    if (dst == NULL || !flash_range_ok(address, len))
    {
        return -1;
    }
    memcpy(dst, flash_fixture.bytes + address - OTA_EXT_STAGING, len);
    return 0;
}

static int flash_erase(void *ctx, uint32_t address)
{
    (void)ctx;
    if (!flash_range_ok(address, OTA_STAGING_BLOCK_SIZE) ||
        (address & (OTA_STAGING_BLOCK_SIZE - 1u)) != 0u)
    {
        return -1;
    }
    record_operation(OP_ERASE, address, OTA_STAGING_BLOCK_SIZE);
    memset(flash_fixture.bytes + address - OTA_EXT_STAGING, 0xFF,
           OTA_STAGING_BLOCK_SIZE);
    return 0;
}

static int flash_program(void *ctx, uint32_t address,
                         const uint8_t *src, uint32_t len)
{
    uint32_t index;
    uint8_t *dst;

    (void)ctx;
    if (src == NULL || len == 0u || !flash_range_ok(address, len))
    {
        return -1;
    }
    dst = flash_fixture.bytes + address - OTA_EXT_STAGING;
    for (index = 0u; index < len; ++index)
    {
        if ((dst[index] & src[index]) != src[index])
        {
            return -1;
        }
    }
    record_operation(OP_PROGRAM, address, len);
    for (index = 0u; index < len; ++index)
    {
        dst[index] &= src[index];
    }
    return 0;
}

static ota_staging_io_t staging_io;

static void make_staging_io(void)
{
    memset(&staging_io, 0, sizeof(staging_io));
    staging_io.read = flash_read;
    staging_io.erase_4k = flash_erase;
    staging_io.program = flash_program;
}

static void reset_flash(void)
{
    memset(&flash_fixture, 0, sizeof(flash_fixture));
    memset(flash_fixture.bytes, 0xFF, sizeof(flash_fixture.bytes));
}

static uint32_t count_erase_at(uint32_t address)
{
    uint32_t count = 0u;
    uint32_t index;

    for (index = 0u; index < flash_fixture.operation_count; ++index)
    {
        operation_t *operation = &flash_fixture.operations[index];
        if (operation->type == OP_ERASE && operation->address == address)
        {
            ++count;
        }
    }
    return count;
}

static uint32_t count_programs_in(uint32_t address, uint32_t len)
{
    uint32_t count = 0u;
    uint32_t index;

    for (index = 0u; index < flash_fixture.operation_count; ++index)
    {
        operation_t *operation = &flash_fixture.operations[index];
        if (operation->type == OP_PROGRAM &&
            operation->address >= address &&
            operation->address < address + len)
        {
            ++count;
        }
    }
    return count;
}

/* ================= env 注入与 TX 捕获 ================= */

typedef struct tx_frame_t
{
    uint8_t bytes[OTA_BLE_MAX_FRAME];
    uint16_t len;
} tx_frame_t;

typedef struct test_env_t
{
    uint32_t now_ms;
    tx_frame_t frames[TX_MAX];
    uint32_t tx_count;
    int bcb_confirmed;
    int ota_disabled;
    int overlay_available;
    uint32_t overlay_acquire_count;
    uint32_t overlay_release_count;
    uint8_t workspace[40960];
    uint32_t workspace_size;
    ota_sd_device_t device;
    int info_provider_null;
    uint8_t image_sha[32];
    /* P3-3 激活钩子打点：activate_result 注入返回值（默认 0 成功）；
     * activate_hook_null 注入 NULL 测会话层 fail-closed。 */
    int activate_hook_null;
    int activate_result;
    uint32_t activate_calls;
    uint32_t activate_vcode;
    uint32_t activate_total_len;
    uint8_t activate_kind;
    uint32_t reset_calls;
} test_env_t;

static test_env_t te;

static uint32_t env_now_ms(void)
{
    return te.now_ms;
}

static int env_send(const uint8_t *frame, uint16_t len)
{
    if (te.tx_count < TX_MAX && len <= OTA_BLE_MAX_FRAME)
    {
        memcpy(te.frames[te.tx_count].bytes, frame, len);
        te.frames[te.tx_count].len = len;
    }
    ++te.tx_count;
    return 0;
}

static int env_bcb_confirmed(void)
{
    return te.bcb_confirmed;
}

static int env_ota_disabled(void)
{
    return te.ota_disabled;
}

static int env_overlay_acquire(void)
{
    if (!te.overlay_available)
    {
        return 0;
    }
    ++te.overlay_acquire_count;
    return 1;
}

static void env_overlay_release(void)
{
    ++te.overlay_release_count;
}

static uint8_t *env_overlay_workspace(uint32_t *out_size)
{
    if (out_size != NULL)
    {
        *out_size = te.workspace_size;
    }
    return te.workspace;
}

static int env_get_device(ota_sd_device_t *out_device)
{
    if (out_device == NULL)
    {
        return 0;
    }
    *out_device = te.device;
    return 1;
}

static int env_info_provider(ota_ble_info_t *out_info)
{
    if (out_info == NULL)
    {
        return 0;
    }
    memset(out_info, 0, sizeof(*out_info));
    memcpy(out_info->model, "X-Track", sizeof("X-Track"));
    out_info->hw_rev = te.device.hardware_rev;
    out_info->layout_id = te.device.layout_id;
    out_info->boot_ver = te.device.boot_version;
    out_info->cur_vcode = te.device.current_vcode;
    memcpy(out_info->image_sha256, te.image_sha, sizeof(te.image_sha));
    return 1;
}

static int env_activate_staged(uint32_t target_vcode, uint32_t total_len,
                               ota_sd_kind_t kind)
{
    ++te.activate_calls;
    te.activate_vcode = target_vcode;
    te.activate_total_len = total_len;
    te.activate_kind = (uint8_t)kind;
    return te.activate_result;
}

static void env_system_reset(void)
{
    ++te.reset_calls;
}

static ota_ble_session_t session;

static void build_session(void)
{
    ota_ble_env_t env;

    memset(&env, 0, sizeof(env));
    env.now_ms = env_now_ms;
    env.send = env_send;
    env.bcb_confirmed = env_bcb_confirmed;
    env.ota_disabled = env_ota_disabled;
    env.overlay_acquire = env_overlay_acquire;
    env.overlay_release = env_overlay_release;
    env.overlay_workspace = env_overlay_workspace;
    env.get_device = env_get_device;
    env.info_provider = te.info_provider_null ? NULL : env_info_provider;
    env.activate_staged = te.activate_hook_null ? NULL : env_activate_staged;
    env.system_reset = env_system_reset;
    env.staging_io = &staging_io;
    ota_ble_session_init(&session, &env);
}

static void begin_case(void)
{
    uint32_t i;

    reset_flash();
    memset(&te, 0, sizeof(te));
    te.now_ms = 1000u;
    te.bcb_confirmed = 1;
    te.overlay_available = 1;
    te.workspace_size = (uint32_t)sizeof(te.workspace);
    te.device.current_vcode = 20700u;
    te.device.hardware_rev = 1u;
    te.device.layout_id = 1u;
    te.device.boot_version = 1u;
    for (i = 0u; i < sizeof(te.device.base_image_sha8); ++i)
    {
        te.device.base_image_sha8[i] = (uint8_t)(0x30u + i);
    }
    for (i = 0u; i < sizeof(te.image_sha); ++i)
    {
        te.image_sha[i] = (uint8_t)(0xC0u + i);
    }
    build_session();
}

/* ================= 帧构造与驱动 ================= */

static uint8_t wire[OTA_BLE_MAX_FRAME];
static uint16_t wire_len;

static size_t build_begin_frame(uint16_t seq, uint32_t total_len,
                                const uint8_t sha[32], const uint8_t etu[64],
                                uint8_t proto_ver)
{
    uint8_t payload[OTA_BLE_LEN_BEGIN];

    payload[0] = proto_ver;
    write_u32le(payload + 1u, total_len);
    memcpy(payload + 5u, sha, 32u);
    memcpy(payload + 37u, etu, 64u);
    return ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_BEGIN, 0u, seq,
                                payload, OTA_BLE_LEN_BEGIN);
}

static size_t build_data_frame(uint16_t seq, uint8_t sess, uint32_t off,
                               const uint8_t *seg, uint32_t seg_len)
{
    uint8_t payload[OTA_BLE_MAX_PAYLOAD];

    write_u32le(payload, off);
    memcpy(payload + 4u, seg, seg_len);
    return ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_DATA, sess,
                                seq, payload, (uint16_t)(4u + seg_len));
}

static size_t build_end_frame(uint16_t seq, uint8_t sess,
                              const uint8_t sha[32])
{
    return ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_END, sess, seq,
                                sha, OTA_BLE_LEN_END);
}

static size_t build_abort_frame(uint16_t seq, uint8_t sess)
{
    return ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_ABORT, sess,
                                seq, NULL, 0u);
}

static size_t build_get_info_frame(uint16_t seq, uint8_t sess)
{
    return ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_GET_INFO, sess,
                                seq, NULL, 0u);
}

static void feed_idle(size_t len)
{
    size_t i;

    for (i = 0u; i < len; ++i)
    {
        ota_ble_session_feed_idle(&session, NULL, NULL, wire[i]);
    }
}

static void feed_isr(size_t len)
{
    size_t i;

    for (i = 0u; i < len; ++i)
    {
        ota_ble_session_isr_feed(&session, wire[i]);
    }
}

static void pump_once(void)
{
    ota_ble_session_pump(&session);
}

typedef struct tx_view_t
{
    uint8_t cmd;
    uint8_t session;
    uint16_t seq;
    uint16_t len;
    uint8_t payload[OTA_BLE_MAX_PAYLOAD];
} tx_view_t;

static int get_tx(uint32_t index, tx_view_t *v)
{
    tx_frame_t *f;
    uint16_t crc;

    if (index >= te.tx_count || index >= TX_MAX)
    {
        return 0;
    }
    f = &te.frames[index];
    if (f->len < OTA_BLE_HEADER_SIZE + OTA_BLE_CRC_SIZE)
    {
        return 0;
    }
    if (f->bytes[0] != OTA_BLE_SYNC0 || f->bytes[1] != OTA_BLE_SYNC1)
    {
        return 0;
    }
    v->cmd = f->bytes[2];
    v->session = f->bytes[3];
    v->seq = (uint16_t)(f->bytes[4] | ((uint16_t)f->bytes[5] << 8));
    v->len = (uint16_t)(f->bytes[6] | ((uint16_t)f->bytes[7] << 8));
    if (v->len > OTA_BLE_MAX_PAYLOAD ||
        f->len != (uint16_t)(OTA_BLE_HEADER_SIZE + v->len + OTA_BLE_CRC_SIZE))
    {
        return 0;
    }
    memcpy(v->payload, f->bytes + OTA_BLE_HEADER_SIZE, v->len);
    crc = ota_ble_crc16(f->bytes + 2u, (size_t)v->len + 6u);
    return f->bytes[OTA_BLE_HEADER_SIZE + v->len] == (uint8_t)(crc & 0xFFu) &&
           f->bytes[OTA_BLE_HEADER_SIZE + v->len + 1u] ==
               (uint8_t)(crc >> 8);
}

static int last_tx(tx_view_t *v)
{
    return te.tx_count > 0u && get_tx(te.tx_count - 1u, v);
}

static uint32_t tx_status(const tx_view_t *v)
{
    return v->len >= 1u ? v->payload[0] : 0x100u;
}

/* ACK_OTHER：status@0、durable_off@1、bitmap@5；ACK_BEGIN 多 1B session，base=2 */
static uint32_t tx_durable_off(const tx_view_t *v, uint32_t base)
{
    return v->len >= base + 4u ? read_u32le(v->payload + base) : 0xDEADu;
}

static uint32_t tx_bitmap(const tx_view_t *v, uint32_t base)
{
    return v->len >= base + 8u ? read_u32le(v->payload + base + 4u) : 0xDEADu;
}

/* ================= 包构造 ================= */

static void sha256_of(const uint8_t *data, uint32_t len, uint8_t out[32])
{
    boot_sha256_ctx_t sha;

    boot_sha256_init(&sha);
    boot_sha256_update(&sha, data, len);
    boot_sha256_final(&sha, out);
}

static uint8_t *make_full_package(uint32_t package_len)
{
    uint8_t *package;
    uint32_t payload_len;
    uint32_t index;

    if (package_len <= OTA_SD_HEADER_SIZE)
    {
        return NULL;
    }
    package = (uint8_t *)calloc(1u, package_len);
    if (package == NULL)
    {
        return NULL;
    }
    payload_len = package_len - OTA_SD_HEADER_SIZE;
    memcpy(package, "ETU1", 4u);
    package[4] = (uint8_t)OTA_SD_HEADER_SIZE;
    package[5] = 0u;
    package[6] = (uint8_t)(OTA_SD_FULL_FLAGS & 0xFFu);
    package[7] = (uint8_t)(OTA_SD_FULL_FLAGS >> 8);
    write_u32le(package + 8u, 1u);
    write_u32le(package + 12u, 1u);
    write_u32le(package + 32u, payload_len);
    write_u32le(package + 40u, 20800u);
    package[48] = 1u;
    package[50] = 1u;
    package[51] = 1u;
    for (index = OTA_SD_HEADER_SIZE; index < package_len; ++index)
    {
        package[index] = (uint8_t)(index * 29u + 7u);
    }
    write_u32le(package + 36u,
                boot_crc32(package + OTA_SD_HEADER_SIZE, payload_len));
    write_u32le(package + 60u, boot_crc32(package, 60u));
    return package;
}

/* 与 make_full_package 同骨架，仅 flags/base 域按差分头规则填
 * （base_vcode=20700、base_sha8=0x30..0x37，与 begin_case 的设备身份
 * 耦合）。inspect 只校验头部合法性，patch payload 语义由 ota_patch
 * 测试覆盖；本 fixture 用于验证 kind 透传到激活钩子。 */
static uint8_t *make_patch_kind_package(uint32_t package_len)
{
    uint8_t *package;
    uint32_t payload_len;
    uint32_t index;

    if (package_len <= OTA_SD_HEADER_SIZE + 41u)
    {
        return NULL;
    }
    package = (uint8_t *)calloc(1u, package_len);
    if (package == NULL)
    {
        return NULL;
    }
    payload_len = package_len - OTA_SD_HEADER_SIZE;
    memcpy(package, "ETU1", 4u);
    package[4] = (uint8_t)OTA_SD_HEADER_SIZE;
    package[5] = 0u;
    package[6] = (uint8_t)(OTA_SD_PATCH_FLAGS & 0xFFu);
    package[7] = (uint8_t)(OTA_SD_PATCH_FLAGS >> 8);
    write_u32le(package + 8u, 1u);
    write_u32le(package + 12u, 1u);
    write_u32le(package + 32u, payload_len);
    write_u32le(package + 40u, 20800u);
    write_u32le(package + 44u, 20700u);
    for (index = 0u; index < 8u; ++index)
    {
        package[52u + index] = (uint8_t)(0x30u + index);
    }
    package[48] = 1u;
    package[50] = 1u;
    package[51] = 1u;
    for (index = OTA_SD_HEADER_SIZE; index < package_len; ++index)
    {
        package[index] = (uint8_t)(index * 29u + 7u);
    }
    write_u32le(package + 36u,
                boot_crc32(package + OTA_SD_HEADER_SIZE, payload_len));
    write_u32le(package + 60u, boot_crc32(package, 60u));
    return package;
}

/* ================= 各测试用例 ================= */

static void test_get_info(void)
{
    tx_view_t v;

    memset(&v, 0, sizeof(v));
    begin_case();
    te.ota_disabled = 1;
    te.bcb_confirmed = 0;
    build_session();

    wire_len = (uint16_t)build_get_info_frame(0x21u, 0u);
    feed_idle(wire_len);
    check("GET_INFO is answered even when OTA is disabled and BCB is open",
          te.tx_count == 1u && last_tx(&v) && v.cmd == OTA_BLE_CMD_INFO &&
              v.session == 0u && v.seq == 0x21u && v.len == OTA_BLE_LEN_INFO);
    check("INFO payload carries model, identity, proto and window fields",
          v.len == 50u && memcmp(v.payload, "X-Track", 8u) == 0u &&
              v.payload[8] == 1u && v.payload[9] == 0u &&
              v.payload[10] == 1u && v.payload[11] == 1u &&
              read_u32le(v.payload + 12u) == 20700u &&
              memcmp(v.payload + 16u, te.image_sha, 32u) == 0u &&
              v.payload[48] == OTA_BLE_INFO_PROTO_VER &&
              v.payload[49] == OTA_BLE_INFO_MAX_WINDOW_SEGS);
    check("GET_INFO does not open a session",
          !ota_ble_session_active(&session) &&
              !ota_ble_session_isr_active(&session));

    te.tx_count = 0u;
    wire_len = (uint16_t)build_get_info_frame(1u, 9u);
    feed_idle(wire_len);
    check("GET_INFO with a non-zero session byte is ignored",
          te.tx_count == 0u);

    te.tx_count = 0u;
    te.info_provider_null = 1;
    build_session();
    wire_len = (uint16_t)build_get_info_frame(5u, 0u);
    feed_idle(wire_len);
    check("GET_INFO without an info provider stays silent",
          te.tx_count == 0u);
}

static void test_begin_rejections(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("rejection fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);

    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 2u);
    feed_idle(wire_len);
    check("BEGIN with proto_ver 2 is rejected with ERR_PROTO",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_BEGIN &&
              tx_status(&v) == OTA_BLE_STATUS_ERR_PROTO &&
              v.payload[1] == 0u &&
              !ota_ble_session_active(&session));

    wire_len = (uint16_t)build_begin_frame(10u, 0u, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN with total_len 0 is rejected with ERR_LEN",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_LEN);

    wire_len = (uint16_t)build_begin_frame(
        10u, OTA_ETU_MAX_LENGTH + 1u, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN above OTA_ETU_MAX_LENGTH is rejected with ERR_LEN",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_LEN);

    /* OTA 禁用先于 ETU 头检查（坏 magic 也不改变错误码） */
    te.ota_disabled = 1;
    pkg[0] = 'X';
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN is rejected with ERR_OTA_DISABLED before header checks",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_OTA_DISABLED);
    te.ota_disabled = 0;
    pkg[0] = 'E';

    /* ETU 头检查先于 BCB 门槛 */
    pkg[0] = 'X';
    write_u32le(pkg + 60u, boot_crc32(pkg, 60u));
    te.bcb_confirmed = 0;
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("a corrupt ETU magic is rejected with ERR_HDR before BCB gating",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_HDR);
    pkg[0] = 'E';
    te.bcb_confirmed = 1;

    write_u32le(pkg + 40u, 20700u);
    write_u32le(pkg + 60u, boot_crc32(pkg, 60u));
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("target equal to the running version is rejected with ERR_VERSION",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_VERSION);
    write_u32le(pkg + 40u, 20800u);

    pkg[48] = 2u;
    write_u32le(pkg + 60u, boot_crc32(pkg, 60u));
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("hardware revision mismatch is rejected with ERR_HW_REV",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_HW_REV);
    pkg[48] = 1u;

    pkg[50] = 2u;
    write_u32le(pkg + 60u, boot_crc32(pkg, 60u));
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("layout mismatch is rejected with ERR_LAYOUT",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_LAYOUT);
    pkg[50] = 1u;

    pkg[51] = 2u;
    write_u32le(pkg + 60u, boot_crc32(pkg, 60u));
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("an old boot version is rejected with ERR_BOOT_VER",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_BOOT_VER);
    pkg[51] = 1u;
    write_u32le(pkg + 60u, boot_crc32(pkg, 60u));

    te.bcb_confirmed = 0;
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN without a confirmed BCB is rejected with ERR_BUSY",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_BUSY &&
              !ota_ble_session_active(&session));
    te.bcb_confirmed = 1;

    te.overlay_available = 0;
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN without the overlay workspace is rejected with ERR_BUSY",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_BUSY);
    te.overlay_available = 1;

    te.workspace_size = 4096u;
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("an undersized workspace is rejected and the overlay is released",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_BUSY &&
              !ota_ble_session_active(&session) &&
              te.overlay_acquire_count == te.overlay_release_count);
    te.workspace_size = (uint32_t)sizeof(te.workspace);

    check("rejected BEGINs never leak an overlay acquisition",
          te.overlay_acquire_count == te.overlay_release_count);
    free(pkg);
}

/* 泵节奏：ISR 环 4KB、DATA 帧 142B；每 4 帧泵一次（同批多帧粘包 + 环不过载） */
static uint32_t send_segments(uint32_t pkg_len, const uint8_t *pkg,
                              uint32_t from_off, uint16_t first_seq)
{
    uint32_t off;
    uint32_t batch = 0u;
    uint32_t count = 0u;
    uint16_t seq = first_seq;
    uint8_t sess = session.session_id;

    for (off = from_off; off < pkg_len; off += OTA_STAGING_SEGMENT_SIZE)
    {
        uint32_t take = pkg_len - off;

        if (take > OTA_STAGING_SEGMENT_SIZE)
        {
            take = OTA_STAGING_SEGMENT_SIZE;
        }
        wire_len = (uint16_t)build_data_frame(seq, sess, off, pkg + off, take);
        feed_isr(wire_len);
        ++seq;
        ++count;
        ++batch;
        if (batch >= 4u)
        {
            pump_once();
            batch = 0u;
        }
    }
    if (batch > 0u)
    {
        pump_once();
    }
    return count;
}

static void test_full_transfer(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;
    uint32_t segments;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("full transfer fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);

    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN is acknowledged OK with session id 1",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_BEGIN &&
              tx_status(&v) == OTA_BLE_STATUS_OK && v.session == 1u &&
              v.payload[1] == 1u && v.seq == 10u);
    check("BEGIN ACK reports zero durable progress and empty bitmap",
          tx_durable_off(&v, 2u) == 0u && tx_bitmap(&v, 2u) == 0u);
    check("session is active and ISR feeding is armed",
          ota_ble_session_active(&session) &&
              ota_ble_session_isr_active(&session));
    check("overlay workspace is acquired exactly once",
          te.overlay_acquire_count == 1u &&
              te.overlay_release_count == 0u);

    segments = send_segments(pkg_len, pkg, 0u, 11u);
    check("all 40 DATA segments are acknowledged",
          segments == 40u && te.tx_count == 41u);
    check("the block-boundary ACK reports the committed 4 KiB",
          get_tx(32u, &v) && v.cmd == OTA_BLE_CMD_ACK_DATA &&
              v.seq == 42u && tx_status(&v) == OTA_BLE_STATUS_OK &&
              tx_durable_off(&v, 1u) == OTA_STAGING_BLOCK_SIZE &&
              tx_bitmap(&v, 1u) == 0u);
    check("the first segment of the next block sets bitmap bit 0",
          get_tx(33u, &v) && tx_durable_off(&v, 1u) == OTA_STAGING_BLOCK_SIZE &&
              tx_bitmap(&v, 1u) == 1u);
    check("the tail segment ACK reports the whole package as durable",
          get_tx(40u, &v) && tx_durable_off(&v, 1u) == pkg_len);
    check("the ISR ring is fully drained",
          ota_ble_ring_count(&session.rx_ring) == 0u);

    wire_len = (uint16_t)build_end_frame(51u, 1u, sha);
    feed_isr(wire_len);
    pump_once();
    check("END is acknowledged OK and tears the session down",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END &&
              tx_status(&v) == OTA_BLE_STATUS_OK && v.seq == 51u &&
              !ota_ble_session_active(&session) &&
              !ota_ble_session_isr_active(&session));
    check("overlay workspace is released after END",
          te.overlay_acquire_count == 1u &&
              te.overlay_release_count == 1u);
    check("staged payload is byte-exact",
          memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg,
                 pkg_len) == 0);
    check("ETSL records whole-package length, CRC, target and SHA8",
          memcmp(flash_fixture.bytes, "ETSL", 4u) == 0u &&
              read_u32le(flash_fixture.bytes + 8u) == pkg_len &&
              read_u32le(flash_fixture.bytes + 12u) ==
                  boot_crc32(pkg, pkg_len) &&
              read_u32le(flash_fixture.bytes + 16u) == 20800u &&
              memcmp(flash_fixture.bytes + 20u, sha, 8u) == 0);
    check("the commit marker is written",
          read_u32le(flash_fixture.bytes + 28u) ==
              OTA_STAGING_COMMIT_MARKER);
    free(pkg);
}

static void test_duplicate_begin_and_idempotent_data(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;
    uint32_t programs_before;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("idempotency fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);

    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    wire_len = (uint16_t)build_data_frame(11u, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    wire_len = (uint16_t)build_data_frame(12u, 1u, 128u, pkg + 128u, 128u);
    feed_isr(wire_len);
    pump_once();
    check("two in-flight segments are acknowledged",
          te.tx_count == 3u && get_tx(2u, &v) &&
              tx_bitmap(&v, 1u) == 0x3u);

    /* 重复 BEGIN（重试语义，同 seq）：回当前进度，不重建 staging */
    programs_before = count_programs_in(OTA_EXT_STAGING,
                                        OTA_STAGING_PAYLOAD_OFFSET);
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_isr(wire_len);
    pump_once();
    check("a duplicate BEGIN is idempotent and echoes live progress",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_BEGIN &&
              tx_status(&v) == OTA_BLE_STATUS_OK && v.payload[1] == 1u &&
              tx_durable_off(&v, 2u) == 0u && tx_bitmap(&v, 2u) == 0x3u);
    check("the duplicate BEGIN neither re-acquires nor rewrites staging",
          te.overlay_acquire_count == 1u &&
              count_programs_in(OTA_EXT_STAGING,
                                OTA_STAGING_PAYLOAD_OFFSET) ==
                  programs_before);

    /* 续传补齐块 0（段 0/1 走 DUPLICATE 幂等，其余 30 段新写入） */
    send_segments(OTA_STAGING_BLOCK_SIZE, pkg, 0u, 13u);
    check("a full block is durably committed",
          session.progress.durable_off == OTA_STAGING_BLOCK_SIZE);
    programs_before = count_programs_in(
        OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET,
        OTA_STAGING_BLOCK_SIZE);
    wire_len = (uint16_t)build_data_frame(45u, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("a fresh-seq DATA below durable_off is idempotent without rewrites",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_DATA &&
              tx_status(&v) == OTA_BLE_STATUS_OK &&
              count_programs_in(
                  OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET,
                  OTA_STAGING_BLOCK_SIZE) == programs_before);

    wire_len = (uint16_t)build_data_frame(45u, 1u, 3968u, pkg + 3968u, 128u);
    feed_isr(wire_len);
    pump_once();
    check("a replayed DATA seq is acknowledged idempotently",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_DATA &&
              tx_status(&v) == OTA_BLE_STATUS_OK);

    check("the active session keeps the overlay acquired",
          te.overlay_acquire_count == 1u &&
              te.overlay_release_count == 0u);
    free(pkg);
}

static void test_seq_semantics(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("seq fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);

    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);

    wire_len = (uint16_t)build_data_frame(13u, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("a DATA seq gap is rejected with ERR_SEQ",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_DATA &&
              tx_status(&v) == OTA_BLE_STATUS_ERR_SEQ && v.seq == 13u);

    wire_len = (uint16_t)build_data_frame(11u, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("the correct in-order seq is still accepted after a gap NAK",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              session.expected_seq == 12u);

    wire_len = (uint16_t)build_data_frame(11u, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("a replayed old seq is acknowledged idempotently",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              session.expected_seq == 12u);

    wire_len = (uint16_t)build_data_frame(12u, 1u, 128u, pkg + 128u, 128u);
    feed_isr(wire_len);
    pump_once();
    check("the next in-order seq advances",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              session.expected_seq == 13u);

    /* seq 回绕：0xFFFE -> 0xFFFF -> 0x0000 */
    begin_case();
    sha256_of(pkg, pkg_len, sha);
    wire_len = (uint16_t)build_begin_frame(0xFFFEu, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN near the seq wrap is accepted",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              session.expected_seq == 0xFFFFu);

    wire_len = (uint16_t)build_data_frame(0xFFFFu, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("seq 0xFFFF is accepted and wraps expected to 0",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              session.expected_seq == 0u);

    wire_len = (uint16_t)build_data_frame(0xFFFFu, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("a replayed 0xFFFF across the wrap is idempotent",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK);

    wire_len = (uint16_t)build_data_frame(0u, 1u, 128u, pkg + 128u, 128u);
    feed_isr(wire_len);
    pump_once();
    check("seq 0 after the wrap is accepted in order",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK);
    free(pkg);
}

static void test_data_validation(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;
    uint16_t seq = 11u;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("data validation fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);

    wire_len = (uint16_t)build_data_frame(seq, 1u, 4u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    ++seq;
    check("a non-128-aligned offset is rejected with ERR_OFFSET",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_DATA &&
              tx_status(&v) == OTA_BLE_STATUS_ERR_OFFSET);

    wire_len = (uint16_t)build_data_frame(seq, 1u, 0u, pkg, 64u);
    feed_isr(wire_len);
    pump_once();
    ++seq;
    check("a short mid-package segment is rejected with ERR_FRAME",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_FRAME);

    wire_len = (uint16_t)build_data_frame(seq, 1u, pkg_len + 128u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    ++seq;
    check("a DATA beyond total_len is rejected with ERR_OFFSET",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_OFFSET);

    wire_len = (uint16_t)build_data_frame(seq, 9u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("DATA with a wrong session byte is rejected with ERR_SESSION",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SESSION);

    /* 尾段只能在其块成为当前块后接受：先补齐块 0 */
    send_segments(OTA_STAGING_BLOCK_SIZE, pkg, 0u, seq);
    check("block 0 is committed so the tail block becomes current",
          session.progress.durable_off == OTA_STAGING_BLOCK_SIZE);
    seq = (uint16_t)(seq + 32u);

    wire_len = (uint16_t)build_data_frame(seq, 1u, pkg_len - 8u,
                                          pkg + pkg_len - 8u, 8u);
    feed_isr(wire_len);
    pump_once();
    check("the short tail segment with off+len == total is accepted",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK);

    check("format errors leave the session active for the sender to retry",
          ota_ble_session_active(&session) &&
              te.overlay_acquire_count == 1u &&
              te.overlay_release_count == 0u);
    free(pkg);
}

static void test_err_data_fail_closed(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("ERR_DATA fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);

    wire_len = (uint16_t)build_data_frame(11u, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("the first off-0 segment is accepted",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK);

    pkg[3] ^= 0xA5u;
    wire_len = (uint16_t)build_data_frame(12u, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    pump_once();
    check("conflicting content at the same offset fails closed with ABORTED",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_DATA &&
              tx_status(&v) == OTA_BLE_STATUS_ABORTED);
    check("the ERR_DATA path tears the session down and frees the overlay",
          !ota_ble_session_active(&session) &&
              !ota_ble_session_isr_active(&session) &&
              te.overlay_acquire_count == te.overlay_release_count);
    pkg[3] ^= 0xA5u;

    wire_len = (uint16_t)build_begin_frame(20u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("a fresh BEGIN after fail-closed restarts at zero progress",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              v.payload[1] == 2u && tx_durable_off(&v, 2u) == 0u);

    send_segments(pkg_len, pkg, 0u, 21u);
    wire_len = (uint16_t)build_end_frame(61u, 2u, sha);
    feed_isr(wire_len);
    pump_once();
    check("the retried transfer completes and stages byte-exact data",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END &&
              tx_status(&v) == OTA_BLE_STATUS_OK &&
              memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg,
                     pkg_len) == 0);
    free(pkg);
}

static void test_end_paths(void)
{
    uint8_t *pkg;
    uint8_t *pkg_p;
    uint8_t sha[32];
    uint8_t sha_p[32];
    uint8_t wrong_sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("END path fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);
    memcpy(wrong_sha, sha, sizeof(wrong_sha));
    wrong_sha[0] ^= 0x01u;

    /* A. 空闲期 END */
    wire_len = (uint16_t)build_end_frame(5u, 1u, sha);
    feed_idle(wire_len);
    check("END while idle is rejected with ERR_STATE",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END &&
              tx_status(&v) == OTA_BLE_STATUS_ERR_STATE);

    /* B. 缺段 END：ERR_STATE + teardown；staging 保留可 resume */
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    wire_len = (uint16_t)build_data_frame(11u, 1u, 0u, pkg, 128u);
    feed_isr(wire_len);
    wire_len = (uint16_t)build_data_frame(12u, 1u, 128u, pkg + 128u, 128u);
    feed_isr(wire_len);
    pump_once();
    wire_len = (uint16_t)build_end_frame(13u, 1u, sha);
    feed_isr(wire_len);
    pump_once();
    check("END before the package is complete is rejected with ERR_STATE",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_STATE &&
              !ota_ble_session_active(&session));
    wire_len = (uint16_t)build_begin_frame(20u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("staging survives the incomplete END and a fresh BEGIN continues",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              tx_durable_off(&v, 2u) == 0u && tx_bitmap(&v, 2u) == 0u);

    /* C. sha 复述不符：ERR_SHA + 槽头页擦除（同 sha 不可 resume） */
    send_segments(pkg_len, pkg, 0u, 21u);
    wire_len = (uint16_t)build_end_frame(61u, 2u, wrong_sha);
    feed_isr(wire_len);
    pump_once();
    check("END with a mismatching sha restatement is rejected with ERR_SHA",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SHA &&
              !ota_ble_session_active(&session));
    check("the ERR_SHA path erases the staging header page",
          flash_fixture.bytes[OTA_STAGING_ETRJ_OFFSET] == 0xFFu &&
              flash_fixture.bytes[OTA_STAGING_ETRJ_OFFSET + 1u] == 0xFFu);
    wire_len = (uint16_t)build_begin_frame(30u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("after the header erase the same package cannot resume",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              tx_durable_off(&v, 2u) == 0u);
    wire_len = (uint16_t)build_abort_frame(31u, 3u);
    feed_isr(wire_len);
    pump_once();
    check("the probe session is torn down by ABORT",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_ABORT &&
              tx_status(&v) == OTA_BLE_STATUS_ABORTED &&
              !ota_ble_session_active(&session));

    /* D. BEGIN 声明 sha 与实际内容不符：复述一致但整包摘要校验失败 */
    wire_len = (uint16_t)build_begin_frame(40u, pkg_len, wrong_sha, pkg, 1u);
    feed_idle(wire_len);
    check("a BEGIN declaring a mismatching sha still opens a session",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              v.payload[1] == 4u);
    send_segments(pkg_len, pkg, 0u, 41u);
    wire_len = (uint16_t)build_end_frame(81u, 4u, wrong_sha);
    feed_isr(wire_len);
    pump_once();
    check("a declared sha that mismatches the staged bytes fails with ERR_SHA",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SHA &&
              !ota_ble_session_active(&session));

    /* E. 错会话号 END 不清理；正确 END 收尾 */
    wire_len = (uint16_t)build_begin_frame(90u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    send_segments(pkg_len, pkg, 0u, 91u);
    wire_len = (uint16_t)build_end_frame(131u, 9u, sha);
    feed_isr(wire_len);
    pump_once();
    check("END with a wrong session is rejected and keeps the session",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_ERR_SESSION &&
              ota_ble_session_active(&session));
    wire_len = (uint16_t)build_end_frame(131u, 5u, sha);
    feed_isr(wire_len);
    pump_once();
    check("the correct END afterwards completes the transfer",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END &&
              tx_status(&v) == OTA_BLE_STATUS_OK &&
              read_u32le(flash_fixture.bytes + 28u) ==
                  OTA_STAGING_COMMIT_MARKER);
    check("the finally staged package is byte-exact",
          memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg,
                 pkg_len) == 0);

    /* F. 激活成功：ACK OK 先行，激活钩子以 BEGIN inspect 的三元组被调，
     * 成功后触发复位钩子（合同 §4.5：成功路径随后重启进入 boot）。 */
    check("the successful END activated the staged package once",
          te.activate_calls == 1u && te.activate_vcode == 20800u &&
              te.activate_total_len == pkg_len &&
              te.activate_kind == (uint8_t)OTA_SD_KIND_FULL);
    check("the successful END triggered the reset hook after the ACK",
          te.reset_calls == 1u &&
              te.overlay_acquire_count == te.overlay_release_count);

    /* G. 激活失败：ACK OK 仍先行（发送端起算重启复核窗口），不复位、
     * 会话干净收尾（BCB 保持 CONFIRMED 的平台语义由设备侧保证）。 */
    te.tx_count = 0u;
    te.activate_result = -1;
    wire_len = (uint16_t)build_begin_frame(140u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    send_segments(pkg_len, pkg, 0u, 141u);
    wire_len = (uint16_t)build_end_frame(181u, 6u, sha);
    feed_isr(wire_len);
    pump_once();
    check("a failing activation still ACKs END OK first",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END &&
              tx_status(&v) == OTA_BLE_STATUS_OK);
    check("a failing activation does not reset and tears down cleanly",
          te.activate_calls == 2u && te.reset_calls == 1u &&
              !ota_ble_session_active(&session) &&
              te.overlay_acquire_count == te.overlay_release_count);

    /* H. 激活钩子缺失：fail-closed 回 ERR_FLASH，不发送伪 OK。 */
    te.tx_count = 0u;
    te.activate_hook_null = 1;
    build_session();
    wire_len = (uint16_t)build_begin_frame(150u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    send_segments(pkg_len, pkg, 0u, 151u);
    wire_len = (uint16_t)build_end_frame(191u, 1u, sha);
    feed_isr(wire_len);
    pump_once();
    check("a missing activation hook fails closed with ERR_FLASH",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END &&
              tx_status(&v) == OTA_BLE_STATUS_ERR_FLASH &&
              !ota_ble_session_active(&session));
    check("the missing-hook path never reaches activation or reset",
          te.activate_calls == 2u && te.reset_calls == 1u);

    /* I. 差分 kind 透传：patch 头包的激活钩子收到 OTA_SD_KIND_PATCH。 */
    te.tx_count = 0u;
    te.activate_calls = 0u;
    te.activate_vcode = 0u;
    te.activate_total_len = 0u;
    te.activate_kind = 0u;
    te.reset_calls = 0u;
    te.activate_result = 0;
    te.activate_hook_null = 0;
    build_session();
    pkg_p = make_patch_kind_package(pkg_len);
    check("patch-kind fixture package is generated", pkg_p != NULL);
    if (pkg_p != NULL)
    {
        sha256_of(pkg_p, pkg_len, sha_p);
        wire_len = (uint16_t)build_begin_frame(160u, pkg_len, sha_p, pkg_p,
                                               1u);
        feed_idle(wire_len);
        send_segments(pkg_len, pkg_p, 0u, 161u);
        wire_len = (uint16_t)build_end_frame(201u, 1u, sha_p);
        feed_isr(wire_len);
        pump_once();
        check("a patch-kind package activates with OTA_SD_KIND_PATCH",
              last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_END &&
                  tx_status(&v) == OTA_BLE_STATUS_OK &&
                  te.activate_calls == 1u &&
                  te.activate_kind == (uint8_t)OTA_SD_KIND_PATCH &&
                  te.activate_vcode == 20800u &&
                  te.activate_total_len == pkg_len);
        check("the patch-kind activation path also resets",
              te.reset_calls == 1u);
        free(pkg_p);
    }
    free(pkg);
}

static void test_abort_and_resume(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;
    uint32_t first_payload_addr =
        OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("abort/resume fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);

    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    send_segments(OTA_STAGING_BLOCK_SIZE, pkg, 0u, 11u);
    check("one full block is durable before the abort",
          session.progress.durable_off == OTA_STAGING_BLOCK_SIZE);

    wire_len = (uint16_t)build_abort_frame(50u, 9u);
    feed_isr(wire_len);
    pump_once();
    check("ABORT with a wrong session is rejected with ERR_SESSION",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_ABORT &&
              tx_status(&v) == OTA_BLE_STATUS_ERR_SESSION &&
              ota_ble_session_active(&session));

    wire_len = (uint16_t)build_abort_frame(50u, 1u);
    feed_isr(wire_len);
    pump_once();
    check("ABORT is acknowledged ABORTED and tears the session down",
          last_tx(&v) && v.cmd == OTA_BLE_CMD_ACK_ABORT &&
              tx_status(&v) == OTA_BLE_STATUS_ABORTED &&
              !ota_ble_session_active(&session) &&
              !ota_ble_session_isr_active(&session) &&
              te.overlay_acquire_count == te.overlay_release_count);

    wire_len = (uint16_t)build_begin_frame(60u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("the resumed BEGIN reports the durable offset and a new session id",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              v.payload[1] == 2u &&
              tx_durable_off(&v, 2u) == OTA_STAGING_BLOCK_SIZE &&
              tx_bitmap(&v, 2u) == 0u);

    send_segments(pkg_len, pkg, OTA_STAGING_BLOCK_SIZE, 61u);
    wire_len = (uint16_t)build_end_frame(69u, 2u, sha);
    feed_isr(wire_len);
    pump_once();
    check("the resumed transfer completes with END OK",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK);
    check("the resumed staging is byte-exact",
          memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg,
                 pkg_len) == 0);
    check("resume never re-erases the already durable first block",
          count_erase_at(first_payload_addr) == 1u);
    check("ETSL keeps the whole-package CRC semantics after resume",
          read_u32le(flash_fixture.bytes + 12u) == boot_crc32(pkg, pkg_len));
    free(pkg);
}

static void test_session_replacement(void)
{
    uint8_t *pkg_a;
    uint8_t *pkg_b;
    uint8_t sha_a[32];
    uint8_t sha_b[32];
    tx_view_t v;
    uint32_t len_a = 5000u;
    uint32_t len_b = 4200u;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg_a = make_full_package(len_a);
    pkg_b = make_full_package(len_b);
    check("replacement fixture packages are generated",
          pkg_a != NULL && pkg_b != NULL);
    if (pkg_a == NULL || pkg_b == NULL)
    {
        free(pkg_a);
        free(pkg_b);
        return;
    }
    sha256_of(pkg_a, len_a, sha_a);
    sha256_of(pkg_b, len_b, sha_b);

    wire_len = (uint16_t)build_begin_frame(10u, len_a, sha_a, pkg_a, 1u);
    feed_idle(wire_len);
    check("package A opens session 1",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              v.payload[1] == 1u);

    /* 不同 sha 的 BEGIN：整体替换（释放再获取 overlay，staging 重建） */
    wire_len = (uint16_t)build_begin_frame(20u, len_b, sha_b, pkg_b, 1u);
    feed_isr(wire_len);
    pump_once();
    check("a different package BEGIN replaces the live session",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              v.payload[1] == 2u && tx_durable_off(&v, 2u) == 0u &&
              ota_ble_session_active(&session));
    check("replacement releases and re-acquires the overlay exactly once",
          te.overlay_acquire_count == 2u &&
              te.overlay_release_count == 1u);

    send_segments(len_b, pkg_b, 0u, 21u);
    wire_len = (uint16_t)build_end_frame(54u, 2u, sha_b);
    feed_isr(wire_len);
    pump_once();
    check("package B completes on the replaced session",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK &&
              memcmp(flash_fixture.bytes + OTA_STAGING_PAYLOAD_OFFSET, pkg_b,
                     len_b) == 0);
    free(pkg_a);
    free(pkg_b);
}

static void test_liveness_and_timeout(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("liveness fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);
    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    te.tx_count = 0u;

    te.now_ms += 400u;
    pump_once();
    check("no liveness ACK before the 500 ms threshold",
          te.tx_count == 0u);

    te.now_ms += 101u;
    pump_once();
    check("a liveness ACK is resent at the 500 ms threshold",
          te.tx_count == 1u && get_tx(0u, &v) &&
              v.cmd == OTA_BLE_CMD_ACK_DATA &&
              tx_status(&v) == OTA_BLE_STATUS_OK && v.seq == 10u);
    pump_once();
    check("a second pump in the same period does not double-send",
          te.tx_count == 1u);

    /* 噪声帧（坏 CRC）不重置会话超时 */
    te.now_ms += 499u;
    wire_len = (uint16_t)build_data_frame(11u, 1u, 0u, pkg, 128u);
    wire[wire_len - 1u] ^= 0x55u;
    feed_isr(wire_len);
    pump_once();
    check("a corrupt frame draws an ERR_CRC NAK but keeps the session",
          te.tx_count == 2u && get_tx(1u, &v) &&
              tx_status(&v) == OTA_BLE_STATUS_ERR_CRC &&
              ota_ble_session_active(&session));

    /* 30s 无有效帧：ABORTED 清理（坏帧时刻不重置超时基准） */
    te.now_ms += 30001u;
    pump_once();
    check("the session times out to an ABORTED ACK after 30 s of silence",
          te.tx_count == 3u && get_tx(2u, &v) &&
              v.cmd == OTA_BLE_CMD_ACK_ABORT &&
              tx_status(&v) == OTA_BLE_STATUS_ABORTED &&
              !ota_ble_session_active(&session) &&
              !ota_ble_session_isr_active(&session));
    check("the timeout path frees the overlay",
          te.overlay_acquire_count == te.overlay_release_count);
    free(pkg);
}

static uint8_t text_out[256];
static uint32_t text_len;

static void text_collect(void *ctx, uint8_t byte)
{
    (void)ctx;
    if (text_len < (uint32_t)sizeof(text_out))
    {
        text_out[text_len] = byte;
        ++text_len;
    }
}

static void feed_text_idle(const char *text)
{
    uint32_t i;

    for (i = 0u; i < (uint32_t)strlen(text); ++i)
    {
        ota_ble_session_feed_idle(&session, text_collect, NULL,
                                  (uint8_t)text[i]);
    }
}

static void test_text_isolation(void)
{
    uint8_t *pkg;
    uint8_t sha[32];
    tx_view_t v;
    uint32_t pkg_len = 5000u;

    memset(&v, 0, sizeof(v));
    begin_case();
    pkg = make_full_package(pkg_len);
    check("text isolation fixture package is generated", pkg != NULL);
    if (pkg == NULL)
    {
        return;
    }
    sha256_of(pkg, pkg_len, sha);

    text_len = 0u;
    feed_text_idle("hello");
    check("idle-phase text bytes reach the text sink",
          text_len == 5u && memcmp(text_out, "hello", 5u) == 0);

    wire_len = (uint16_t)build_begin_frame(10u, pkg_len, sha, pkg, 1u);
    feed_idle(wire_len);
    check("BEGIN opens the session",
          last_tx(&v) && tx_status(&v) == OTA_BLE_STATUS_OK);

    /* 活跃期：文本字节经 ISR 环由泵丢弃，不进文本通道 */
    {
        uint32_t i;

        for (i = 0u; i < 5u; ++i)
        {
            ota_ble_session_isr_feed(&session, (uint8_t)"world"[i]);
        }
    }
    pump_once();
    check("active-phase text bytes are dropped and never reach the sink",
          text_len == 5u && ota_ble_session_active(&session) &&
              te.tx_count == 1u);
    check("the ISR ring is empty after the pump",
          ota_ble_ring_count(&session.rx_ring) == 0u);

    wire_len = (uint16_t)build_abort_frame(20u, 1u);
    feed_isr(wire_len);
    pump_once();
    feed_text_idle("world");
    check("text passthrough resumes after teardown",
          text_len == 10u && memcmp(text_out, "helloworld", 10u) == 0);
    free(pkg);
}

int main(void)
{
    make_staging_io();
    printf("=== P3-1 BLE session tests ===\n");
    test_get_info();
    test_begin_rejections();
    test_full_transfer();
    test_duplicate_begin_and_idempotent_data();
    test_seq_semantics();
    test_data_validation();
    test_err_data_fail_closed();
    test_end_paths();
    test_abort_and_resume();
    test_session_replacement();
    test_liveness_and_timeout();
    test_text_isolation();
    printf("=== summary: %d checks, %d failure(s) ===\n", checks, failures);
    if (failures == 0)
    {
        printf("P3_1_BLE_SESSION=PASS checks=%d failures=0\n", checks);
    }
    return failures == 0 ? 0 : 1;
}
