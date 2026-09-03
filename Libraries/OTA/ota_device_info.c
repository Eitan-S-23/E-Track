/* P3-2 设备身份链实现。合同依据 docs/ota-binary-contracts.md §1/§3/§5.2.1
 * 与 docs/ota-cross-system-contracts.md（OTA-XC-INFO-MAPPING /
 * OTA-XC-DEVICE-MODEL / OTA-XC-IMAGE-IDENTITY，冻结，只读）。
 * 设计决策见 docs/ota-exec-notes/P3-2-identity-research.md。 */

#include "OTA/ota_device_info.h"

#include "boot_crypto.h"

#include <stddef.h>
#include <string.h>

/* hw_rev 的 wire 宽度是 u16（§5.2.1），fw_header 内为 u32；超过 u16 范围
 * 无法在 INFO 上表达，fail closed 而非截断。 */
#define OTA_DEVICE_HW_REV_MAX 0xFFFFu

/* raw SHA-256 分块读大小（与 boot_fw_header.c 的 FW_HASH_CHUNK_SIZE 同量级，
 * 栈占用与读次数的平衡点）。 */
#define OTA_DEVICE_HASH_CHUNK_SIZE 256u

/* OTA-XC-DEVICE-MODEL 冻结线端值："E-Track" + NUL 恰 8 字节。 */
static const char k_ota_device_model[8] = {
    'F', '-', 'T', 'r', 'a', 'c', 'k', '\0'
};

static ota_device_result_t device_raw_sha256(const boot_image_reader_t *reader,
                                             uint32_t image_len,
                                             uint8_t out[32])
{
    boot_sha256_ctx_t sha;
    uint8_t chunk[OTA_DEVICE_HASH_CHUNK_SIZE];
    uint32_t offset = 0u;

    boot_sha256_init(&sha);
    while (offset < image_len)
    {
        uint32_t take = image_len - offset;
        if (take > sizeof(chunk))
        {
            take = sizeof(chunk);
        }
        if (reader->read(reader->ctx, offset, chunk, take) != 0)
        {
            return OTA_DEVICE_ERR_IMAGE_READ;
        }
        boot_sha256_update(&sha, chunk, take);
        offset += take;
    }
    boot_sha256_final(&sha, out);
    return OTA_DEVICE_OK;
}

/* 快照重计算：fw_header 完整校验（含向量范围）→ raw SHA-256 → 字段填充。
 * 任一步失败保持 state->valid = 0（下次调用重试整链）。 */
static ota_device_result_t device_snapshot_build(
    ota_device_identity_t *state,
    const boot_image_reader_t *image_reader)
{
    boot_fw_expectations_t expectations;
    boot_fw_header_t header;
    boot_fw_result_t fw;
    ota_device_result_t result;

    boot_fw_default_expectations(&expectations);
    fw = boot_fw_header_validate(image_reader, &expectations, &header);
    state->fw_header_result = (int)fw;
    if (fw != BOOT_FW_OK)
    {
        return OTA_DEVICE_ERR_FW_HEADER;
    }
    if (header.hardware_rev > OTA_DEVICE_HW_REV_MAX)
    {
        return OTA_DEVICE_ERR_HW_RANGE;
    }

    result = device_raw_sha256(image_reader, header.image_len,
                               state->info.image_sha256);
    if (result != OTA_DEVICE_OK)
    {
        return result;
    }

    memcpy(state->info.model, k_ota_device_model,
           sizeof(state->info.model));
    state->info.hw_rev = (uint16_t)header.hardware_rev;
    state->info.layout_id = header.layout_id;
    state->info.boot_ver = (uint8_t)BOOT_VERSION;
    state->info.cur_vcode = header.version_code;
    state->valid = 1u;
    return OTA_DEVICE_OK;
}

ota_device_result_t ota_device_identity_get(
    ota_device_identity_t *state,
    ota_device_info_t *out,
    const boot_image_reader_t *image_reader,
    const bcb_hal_t *bcb_hal)
{
    ota_device_result_t result;
    bcb_arbiter_result_t arb;

    if (state == NULL || out == NULL || image_reader == NULL ||
        image_reader->read == NULL || bcb_hal == NULL)
    {
        return OTA_DEVICE_ERR_ARGUMENT;
    }

    if (state->valid == 0u)
    {
        result = device_snapshot_build(state, image_reader);
        if (result != OTA_DEVICE_OK)
        {
            return result;
        }
    }

    /* 每次调用重验 BCB 仲裁：身份权威在 fw_header，但 EEPROM IO 失败属
     * 底层异常，按派工书 fail closed（仲裁结果 A/B/NONE 均放行）。 */
    arb = bcb_arbiter(bcb_hal, NULL);
    state->bcb_result = (int)arb;
    if (arb == BCB_ARBITER_ERROR)
    {
        return OTA_DEVICE_ERR_BCB_IO;
    }

    *out = state->info;
    return OTA_DEVICE_OK;
}
