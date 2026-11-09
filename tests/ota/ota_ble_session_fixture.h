#ifndef E_TRACK_OTA_BLE_SESSION_FIXTURE_H
#define E_TRACK_OTA_BLE_SESSION_FIXTURE_H

/* Shared NOR, identity and package fixtures. No retired transfer implementation. */
#include "OTA/ota_ble_session.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

static inline void check(const char *name, int condition)
{
    ++checks;
    printf("  %-68s %s\n", name, condition ? "PASS" : "FAIL");
    if (!condition)
    {
        ++failures;
    }
}

static inline uint32_t read_u32le(const uint8_t *src)
{
    return (uint32_t)src[0] |
           ((uint32_t)src[1] << 8) |
           ((uint32_t)src[2] << 16) |
           ((uint32_t)src[3] << 24);
}

static inline void write_u32le(uint8_t *dst, uint32_t value)
{
    dst[0] = (uint8_t)value;
    dst[1] = (uint8_t)(value >> 8);
    dst[2] = (uint8_t)(value >> 16);
    dst[3] = (uint8_t)(value >> 24);
}

static inline int flash_range_ok(uint32_t address, uint32_t len)
{
    return address >= OTA_EXT_STAGING &&
           len <= OTA_EXT_STAGING_LENGTH &&
           address - OTA_EXT_STAGING <= OTA_EXT_STAGING_LENGTH - len;
}

static inline void record_operation(int type, uint32_t address, uint32_t len)
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

static inline int flash_read(void *ctx, uint32_t address,
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

static inline int flash_erase(void *ctx, uint32_t address)
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

static inline int flash_program(void *ctx, uint32_t address,
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

static inline void make_staging_io(void)
{
    memset(&staging_io, 0, sizeof(staging_io));
    staging_io.read = flash_read;
    staging_io.erase_4k = flash_erase;
    staging_io.program = flash_program;
}

static inline void reset_flash(void)
{
    memset(&flash_fixture, 0, sizeof(flash_fixture));
    memset(flash_fixture.bytes, 0xFF, sizeof(flash_fixture.bytes));
}

static inline uint32_t count_erase_at(uint32_t address)
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

static inline uint32_t count_programs_in(uint32_t address, uint32_t len)
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
    
    int activate_hook_null;
    int activate_result;
    uint32_t activate_calls;
    uint32_t activate_vcode;
    uint32_t activate_total_len;
    uint8_t activate_kind;
    uint32_t reset_calls;
} test_env_t;

static test_env_t te;

static inline uint32_t env_now_ms(void)
{
    return te.now_ms;
}

static inline int env_send(const uint8_t *frame, uint16_t len)
{
    if (te.tx_count < TX_MAX && len <= OTA_BLE_MAX_FRAME)
    {
        memcpy(te.frames[te.tx_count].bytes, frame, len);
        te.frames[te.tx_count].len = len;
    }
    ++te.tx_count;
    return 0;
}

static inline int env_bcb_confirmed(void)
{
    return te.bcb_confirmed;
}

static inline int env_ota_disabled(void)
{
    return te.ota_disabled;
}

static inline int env_overlay_acquire(void)
{
    if (!te.overlay_available)
    {
        return 0;
    }
    ++te.overlay_acquire_count;
    return 1;
}

static inline void env_overlay_release(void)
{
    ++te.overlay_release_count;
}

static inline uint8_t *env_overlay_workspace(uint32_t *out_size)
{
    if (out_size != NULL)
    {
        *out_size = te.workspace_size;
    }
    return te.workspace;
}

static inline int env_get_device(ota_sd_device_t *out_device)
{
    if (out_device == NULL)
    {
        return 0;
    }
    *out_device = te.device;
    return 1;
}

static inline int env_info_provider(ota_ble_info_t *out_info)
{
    if (out_info == NULL)
    {
        return 0;
    }
    memset(out_info, 0, sizeof(*out_info));
    memcpy(out_info->model, "E-Track", sizeof("E-Track"));
    out_info->hw_rev = (uint16_t)te.device.hardware_rev;
    out_info->layout_id = te.device.layout_id;
    out_info->boot_ver = te.device.boot_version;
    out_info->cur_vcode = te.device.current_vcode;
    memcpy(out_info->image_sha256, te.image_sha, sizeof(te.image_sha));
    return 1;
}

static inline int env_activate_staged(uint32_t target_vcode, uint32_t total_len,
                               ota_sd_kind_t kind)
{
    ++te.activate_calls;
    te.activate_vcode = target_vcode;
    te.activate_total_len = total_len;
    te.activate_kind = (uint8_t)kind;
    return te.activate_result;
}

static inline void env_system_reset(void)
{
    ++te.reset_calls;
}

static ota_ble_session_t session;

static inline void build_session(void)
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

static inline void begin_case(void)
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
    for (i = 0u; i < sizeof(te.image_sha); ++i)
    {
        te.image_sha[i] = (uint8_t)(0xC0u + i);
    }
    memcpy(te.device.base_image_sha8, te.image_sha, sizeof(te.device.base_image_sha8));
    build_session();
}

static uint8_t wire[OTA_BLE_MAX_FRAME];
static inline size_t build_get_info_frame(uint16_t seq, uint8_t sess)
{
    return ota_ble_frame_encode(wire, sizeof(wire), OTA_BLE_CMD_GET_INFO, sess,
                                seq, NULL, 0u);
}

static inline void feed_idle(size_t len)
{
    size_t i;

    for (i = 0u; i < len; ++i)
    {
        ota_ble_session_feed_idle(&session, NULL, NULL, wire[i]);
    }
}

static inline void feed_isr(size_t len)
{
    size_t i;

    for (i = 0u; i < len; ++i)
    {
        ota_ble_session_isr_feed(&session, wire[i]);
    }
}

static inline void pump_once(void)
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

static inline int get_tx(uint32_t index, tx_view_t *v)
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

static inline int last_tx(tx_view_t *v)
{
    return te.tx_count > 0u && get_tx(te.tx_count - 1u, v);
}

static inline uint32_t tx_status(const tx_view_t *v)
{
    return v->len >= 1u ? v->payload[0] : 0x100u;
}

static inline void sha256_of(const uint8_t *data, uint32_t len, uint8_t out[32])
{
    boot_sha256_ctx_t sha;

    boot_sha256_init(&sha);
    boot_sha256_update(&sha, data, len);
    boot_sha256_final(&sha, out);
}

static inline uint8_t *make_full_package(uint32_t package_len)
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

static inline uint8_t *make_patch_kind_package(uint32_t package_len)
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
        package[52u + index] = te.device.base_image_sha8[index];
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

static inline void test_get_info(void)
{
    tx_view_t v;
    uint16_t wire_len;

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
          v.len == 50u && memcmp(v.payload, "E-Track", 8u) == 0u &&
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

#endif
