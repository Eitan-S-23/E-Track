/* P3-1 BLE 会话状态机。帧层见 ota_ble_frame.c，合同依据
 * docs/ota-binary-contracts.md §4.2/§4.5/§5（冻结，只读）。
 * 设计决策与错误码映射见 docs/ota-exec-notes/P3-1-research-ble-transport.md。 */

#include "OTA/ota_ble_session.h"

#include <stddef.h>
#include <string.h>

#include "OTA/ota_layout.h"

static uint32_t pipeline_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void pipeline_put_u32(uint8_t *p, uint32_t value)
{
    p[0] = (uint8_t)value;
    p[1] = (uint8_t)(value >> 8);
    p[2] = (uint8_t)(value >> 16);
    p[3] = (uint8_t)(value >> 24);
}

static int session_pipeline_available(const ota_ble_session_t *session)
{
    const ota_pipeline_io_t *io = session->env.pipeline_io;
    return io != NULL && io->start != NULL && io->poll != NULL && io->cancel != NULL;
}

static void session_pipeline_ack(ota_ble_session_t *session, uint8_t cmd,
    uint8_t status, uint16_t seq, uint32_t epoch, uint8_t sess)
{
    uint8_t payload[OTA_BLE_LEN_ACK_BEGIN2] = {0};
    unsigned base = cmd == OTA_BLE_CMD_ACK_BEGIN2 ? 2u : 1u;
    size_t len;
    if (session->env.send == NULL) return;
    payload[0] = status;
    if (base == 2u) payload[1] = sess;
    pipeline_put_u32(payload + base, epoch);
    if (session->pipeline != NULL && session->pipeline_ack.epoch == epoch)
    {
        pipeline_put_u32(payload + base + 4u, session->pipeline_ack.durable_off);
        pipeline_put_u32(payload + base + 8u, session->pipeline_ack.accepted_off);
        pipeline_put_u32(payload + base + 12u, session->pipeline_ack.credit_end);
    }
    len = ota_ble_frame_encode(session->tx_frame, sizeof(session->tx_frame),
        cmd, sess, seq, payload, (uint16_t)(base + OTA_PIPELINE_ACK_BYTES));
    if (len != 0u) (void)session->env.send(session->tx_frame, (uint16_t)len);
}

static uint32_t session_now(const ota_ble_session_t *session)
{
    if (session == NULL || session->env.now_ms == NULL)
    {
        return 0u;
    }
    return session->env.now_ms();
}

static uint8_t ack_cmd_for(uint8_t cmd)
{
    switch (cmd)
    {
    case OTA_BLE_CMD_BEGIN2:
        return OTA_BLE_CMD_ACK_BEGIN2;
    case OTA_BLE_CMD_DATA2:
        return OTA_BLE_CMD_ACK_DATA2;
    case OTA_BLE_CMD_END2:
        return OTA_BLE_CMD_ACK_END2;
    case OTA_BLE_CMD_ABORT2:
        return OTA_BLE_CMD_ACK_ABORT2;
    default:
        /* GET_INFO 的应答是 INFO 数据帧而非 ACK；未知 cmd 无 NAK 通道 */
        return 0u;
    }
}

/* Only v2 ACKs may be emitted for transfer commands. */
static void session_send_ack(ota_ble_session_t *session,
                             uint8_t ack_cmd, uint8_t status, uint16_t seq)
{
    if (session == NULL || session->env.send == NULL || ack_cmd == 0u) return;
    session_pipeline_ack(session, ack_cmd, status, seq,
        session->pipeline_ack.epoch, session->session_id);
}

static void session_send_ack_begin(ota_ble_session_t *session,
                                   uint8_t status, uint8_t sess,
                                   const ota_ble_frame_t *request)
{
    uint32_t epoch;
    if (session == NULL || request->cmd != OTA_BLE_CMD_BEGIN2) return;
    epoch = request->len == OTA_BLE_LEN_BEGIN2
        ? pipeline_u32(request->payload + OTA_BLE_BEGIN2_EPOCH_OFFSET) : 0u;
    session_pipeline_ack(session, OTA_BLE_CMD_ACK_BEGIN2, status,
        request->seq, epoch, sess);
}

static void session_send_info(ota_ble_session_t *session,
                              const ota_ble_info_t *info, uint16_t seq)
{
    uint8_t payload[OTA_BLE_LEN_INFO];
    size_t len;

    if (session == NULL || session->env.send == NULL || info == NULL)
    {
        return;
    }

    memcpy(&payload[0], info->model, 8u);
    payload[8] = (uint8_t)(info->hw_rev & 0xFFu);
    payload[9] = (uint8_t)((info->hw_rev >> 8) & 0xFFu);
    payload[10] = info->layout_id;
    payload[11] = info->boot_ver;
    payload[12] = (uint8_t)(info->cur_vcode & 0xFFu);
    payload[13] = (uint8_t)((info->cur_vcode >> 8) & 0xFFu);
    payload[14] = (uint8_t)((info->cur_vcode >> 16) & 0xFFu);
    payload[15] = (uint8_t)((info->cur_vcode >> 24) & 0xFFu);
    memcpy(&payload[16], info->image_sha256, 32u);
    payload[48] = OTA_BLE_INFO_PROTO_VER;
    payload[49] = OTA_BLE_INFO_MAX_WINDOW_SEGS;

    len = ota_ble_frame_encode(session->tx_frame, sizeof(session->tx_frame),
                               OTA_BLE_CMD_INFO, 0u, seq, payload,
                               OTA_BLE_LEN_INFO);
    if (len != 0u)
    {
        (void)session->env.send(session->tx_frame, (uint16_t)len);
    }
}

/* 会话清理（END/ABORT/超时/不可恢复错误的公共出口）。
 * 顺序保证 ISR 安全：先撤活跃标志（ISR 停写 overlay 环），再复位环与
 * receiver 指针，最后归还 overlay。staging durable 状态不动（恢复语义
 * 由 ota_staging_begin 承担）。progress 保留，供 idle 期 ACK 报实况。 */
static void session_teardown(ota_ble_session_t *session)
{
    if (session->pipeline != NULL)
    {
        ota_pipeline_abort(session->pipeline);
        if (!ota_pipeline_can_release(session->pipeline))
        {
            /* Keep ISR/ring/overlay ownership until the hardware has settled. */
            session->state = OTA_BLE_SESSION_DRAINING;
            return;
        }
        session->pipeline = NULL;
    }
    session->caps_nonce = 0u;
    session->transfer_info_valid = 0u;
    session->isr_active = 0u;
    ota_ble_ring_init(&session->rx_ring, NULL, 0u);
    session->receiver = NULL;
    session->state = OTA_BLE_SESSION_IDLE;
    session->session_id = 0u;
    if (session->env.overlay_release != NULL)
    {
        session->env.overlay_release();
    }
}

/* 超时清理：先尽力上送 0x84 ABORTED（对端可能已断连，发送失败无害），
 * 再走公共 teardown。 */
static void session_teardown_aborted(ota_ble_session_t *session)
{
    uint16_t seq = session->last_ack_seq;

    if (session->pipeline != NULL)
    {
        session->pipeline_abort_reply = 1u;
        session->pipeline_abort_seq = seq;
        ota_pipeline_abort(session->pipeline);
        if (!ota_pipeline_can_release(session->pipeline))
        {
            session->state = OTA_BLE_SESSION_DRAINING;
            return;
        }
    }

    session_send_ack(session, OTA_BLE_CMD_ACK_ABORT2,
                     OTA_BLE_STATUS_ABORTED, seq);
    session_teardown(session);
}

/* END 复核失败后的“整页擦除重传”（合同 §5.7 ERR_SHA）：
 * 擦除 staging 槽头 4KB 页（ETSL/ETRJ/位图），使下一次同 sha 的
 * BEGIN 无法 resume 而走整页重建。擦除失败时破坏 ETRJ 的 crc 字段，
 * 防止 IO 半故障下复活坏数据（rebuild 分支自身还会再擦，多重 fail-closed）。 */
static void session_erase_staging_header(ota_ble_session_t *session)
{
    const ota_staging_io_t *io = session->env.staging_io;
    static const uint8_t poison[4] = {0x00u, 0x00u, 0x00u, 0x00u};

    if (io == NULL || io->erase_4k == NULL)
    {
        return;
    }
    if (io->erase_4k(io->ctx, OTA_EXT_STAGING) == 0)
    {
        return;
    }
    if (io->program != NULL)
    {
        /* ETRJ hdr_crc32 位于槽头偏移 40（§4.2.1），写入 0 使其必然非法 */
        (void)io->program(io->ctx, OTA_EXT_STAGING + OTA_STAGING_ETRJ_OFFSET + 40u,
                          poison, sizeof(poison));
    }
}

static uint8_t status_for_inspect_error(ota_sd_result_t result)
{
    switch (result)
    {
    case OTA_SD_ERR_HARDWARE:
        return OTA_BLE_STATUS_ERR_HW_REV;
    case OTA_SD_ERR_LAYOUT:
        return OTA_BLE_STATUS_ERR_LAYOUT;
    case OTA_SD_ERR_MIN_BOOT:
        return OTA_BLE_STATUS_ERR_BOOT_VER;
    case OTA_SD_ERR_VERSION:
        return OTA_BLE_STATUS_ERR_VERSION;
    case OTA_SD_ERR_BASE:
        return OTA_BLE_STATUS_ERR_BASE;
    case OTA_SD_ERR_PACKAGE_LENGTH:
        return OTA_BLE_STATUS_ERR_LEN;
    case OTA_SD_ERR_MAGIC:
    case OTA_SD_ERR_HEADER_LENGTH:
    case OTA_SD_ERR_HEADER_CRC:
    case OTA_SD_ERR_FLAGS:
    case OTA_SD_ERR_ALGORITHM:
    case OTA_SD_ERR_KEY:
    default:
        return OTA_BLE_STATUS_ERR_HDR;
    }
}

/* resume 前缀回填：把已 durable 的 [0, durable_off) 从 staging 读回并
 * 喂进增量 SHA 与整包 CRC32（段级增量只覆盖本会话新收的段）。 */
static int session_digest_resume_prefix(ota_ble_session_t *session,
                                        uint32_t durable_off)
{
    const ota_staging_io_t *io = session->env.staging_io;
    uint32_t offset = 0u;

    if (durable_off == 0u)
    {
        return 0;
    }
    if (io == NULL || io->read == NULL || session->receiver == NULL)
    {
        return -1;
    }

    while (offset < durable_off)
    {
        uint32_t take = durable_off - offset;
        if (take > OTA_STAGING_BLOCK_SIZE)
        {
            take = OTA_STAGING_BLOCK_SIZE;
        }
        if (io->read(io->ctx,
                     OTA_EXT_STAGING + OTA_STAGING_PAYLOAD_OFFSET + offset,
                     session->receiver->block, take) != 0)
        {
            return -1;
        }
        boot_sha256_update(&session->sha, session->receiver->block, take);
        boot_crc32_update(&session->pkg_crc, session->receiver->block, take);
        offset += take;
    }
    return 0;
}

/* seq 校验（合同 §5.1）：0=顺序正确并推进，1=重发帧（幂等），-1=断档 */
static int session_seq_check(ota_ble_session_t *session, uint16_t seq)
{
    int16_t delta = (int16_t)(uint16_t)(seq - session->expected_seq);

    if (delta == 0)
    {
        session->expected_seq = (uint16_t)(seq + 1u);
        return 0;
    }
    return (delta < 0) ? 1 : -1;
}

static void session_touch(ota_ble_session_t *session)
{
    session->last_frame_ms = session_now(session);
}

static void session_touch_data(ota_ble_session_t *session)
{
    session->last_data_ms = session_now(session);
}

/* ---- 命令处理 ---- */

static void session_handle_get_info(ota_ble_session_t *session,
                                    const ota_ble_frame_t *frame)
{
    ota_ble_info_t info;

    /* 合同 §5.2：GET_INFO 以 session=0 发送，不创建会话。
     * 违规 session 与无 provider 时静默丢弃（发送端超时重发）。 */
    if (frame->session != 0u)
    {
        return;
    }
    if (session->pipeline != NULL)
    {
        if (session->transfer_info_valid)
            session_send_info(session, &session->transfer_info, frame->seq);
        return;
    }
    if (session->env.info_provider == NULL ||
        session->env.info_provider(&info) == 0)
    {
        return;
    }
    session_send_info(session, &info, frame->seq);
}

static void session_handle_begin(ota_ble_session_t *session,
                                 const ota_ble_frame_t *frame)
{
    const uint8_t *payload = frame->payload;
    uint8_t proto_ver;
    uint32_t total_len;
    const uint8_t *package_sha;
    const uint8_t *etu_header;
    ota_sd_device_t device;
    ota_sd_package_info_t info;
    ota_sd_result_t result;
    ota_staging_result_t st;
    uint32_t ws_size = 0u;
    uint8_t *ws = NULL;
    uint32_t now;
    uint32_t receiver_size = sizeof(ota_pipeline_t);
    uint32_t epoch = pipeline_u32(payload + OTA_BLE_BEGIN2_EPOCH_OFFSET);

    proto_ver = payload[0];
    total_len = (uint32_t)payload[1] | ((uint32_t)payload[2] << 8) |
                ((uint32_t)payload[3] << 16) | ((uint32_t)payload[4] << 24);
    package_sha = &payload[5];
    etu_header = &payload[37];

    {
        if (frame->session != 0u || epoch == 0u ||
            proto_ver != OTA_PIPELINE_VERSION || !session_pipeline_available(session))
        {
            session_send_ack_begin(session, OTA_BLE_STATUS_ERR_PROTO, 0u, frame);
            return;
        }
        if (session->state != OTA_BLE_SESSION_IDLE)
        {
            /* No platform reads or replacement while external Flash may be busy. */
            if (session->state == OTA_BLE_SESSION_ACTIVE && session->pipeline != NULL &&
                session->pipeline_ack.epoch == epoch &&
                session->pipeline_begin_seq == frame->seq &&
                session->total_len == total_len &&
                memcmp(session->package_sha256, package_sha, 32u) == 0)
                session_send_ack_begin(session, OTA_BLE_STATUS_OK, session->session_id, frame);
            else
                session_send_ack_begin(session, OTA_BLE_STATUS_ERR_BUSY, 0u, frame);
            return;
        }
        if (epoch != session->caps_nonce || epoch == session->last_pipeline_epoch)
        {
            session_send_ack_begin(session, OTA_BLE_STATUS_ERR_SESSION, 0u, frame);
            return;
        }
    }
    if (total_len == 0u || total_len > OTA_ETU_MAX_LENGTH)
    {
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_LEN, 0u,
                               frame);
        return;
    }
    if (session->env.ota_disabled != NULL && session->env.ota_disabled())
    {
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_OTA_DISABLED, 0u,
                               frame);
        return;
    }
    if (session->env.get_device == NULL ||
        session->env.get_device(&device) == 0)
    {
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_STATE, 0u,
                               frame);
        return;
    }
    result = ota_sd_inspect_header(etu_header, total_len, &device, &info);
    if (result != OTA_SD_OK)
    {
        session_send_ack_begin(session, status_for_inspect_error(result),
                               0u, frame);
        return;
    }
    if (session->env.bcb_confirmed == NULL ||
        session->env.bcb_confirmed() == 0)
    {
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_BUSY, 0u,
                               frame);
        return;
    }

    session->transfer_info_valid = 0u;
    if (session->env.info_provider != NULL &&
        session->env.info_provider(&session->transfer_info) != 0 &&
        session->transfer_info.cur_vcode == device.current_vcode &&
        session->transfer_info.hw_rev == device.hardware_rev &&
        session->transfer_info.layout_id == device.layout_id &&
        session->transfer_info.boot_ver == device.boot_version &&
        memcmp(session->transfer_info.image_sha256, device.base_image_sha8,
               sizeof(device.base_image_sha8)) == 0)
    {
        session->transfer_info_valid = 1u;
    }

    if (session->env.overlay_acquire == NULL ||
        session->env.overlay_acquire() == 0)
    {
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_BUSY, 0u,
                               frame);
        return;
    }

    if (session->env.overlay_workspace == NULL)
    {
        session_teardown(session);
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_BUSY, 0u,
                               frame);
        return;
    }
    ws = session->env.overlay_workspace(&ws_size);
    if (ws == NULL ||
        ws_size < CONFIG_OTA_BLE_RX_RING_SIZE + receiver_size
        || ((uintptr_t)ws & 7u) != 0u
        )
    {
        session_teardown(session);
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_BUSY, 0u,
                               frame);
        return;
    }

    /* overlay 子分配：[0, ring_size) = RX 环；其后放 staging receiver
     * （ring_size 为 2 的幂且 >=4096，天然 8 对齐）。 */
    ota_ble_ring_init(&session->rx_ring, ws, CONFIG_OTA_BLE_RX_RING_SIZE);
    if (session->rx_ring.buf == NULL)
    {
        /* 配置非 2 的幂：fail-closed（send 端重试无解，构建配置问题） */
        session_teardown(session);
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_BUSY, 0u,
                               frame);
        return;
    }
    session->receiver =
        (ota_staging_receiver_t *)(uintptr_t)(ws + CONFIG_OTA_BLE_RX_RING_SIZE);

    memcpy(session->package_sha256, package_sha, 32u);
    session->total_len = total_len;
    session->target_vcode = info.target_vcode;
    session->pkg_kind = (uint8_t)info.kind;

    {
        session->pipeline = (ota_pipeline_t *)(void *)session->receiver;
        memset(session->pipeline, 0, sizeof(*session->pipeline));
        st = ota_pipeline_begin(session->pipeline, session->env.staging_io,
            session->env.pipeline_io, epoch, package_sha, total_len) == OTA_PIPELINE_OK
            ? OTA_STAGING_OK : OTA_STAGING_ERR_IO;
        if (st == OTA_STAGING_OK)
        {
            (void)ota_pipeline_snapshot(session->pipeline, &session->pipeline_ack);
            session->progress.durable_off = session->pipeline_ack.durable_off;
            session->progress.segment_bitmap = 0u;
            session->pipeline_resume_off = session->progress.durable_off;
            session->pipeline_begin_seq = frame->seq;
            session->pipeline_first_seq = (uint16_t)(frame->seq + 1u);
            session->last_pipeline_epoch = epoch;
            session->pipeline_abort_reply = 0u;
        }
    }
    if (st != OTA_STAGING_OK)
    {
        /* ETRJ 匹配但日志非法、整页重建失败等：staging 不可用 */
        session_teardown(session);
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_FLASH, 0u,
                               frame);
        return;
    }

    boot_sha256_init(&session->sha);
    boot_crc32_init(&session->pkg_crc);
    if (session_digest_resume_prefix(session, session->progress.durable_off) != 0)
    {
        session_teardown(session);
        session_send_ack_begin(session, OTA_BLE_STATUS_ERR_FLASH, 0u,
                               frame);
        return;
    }

    /* 分配会话号（非零，回绕避开 0） */
    session->session_id = session->next_session_id;
    session->next_session_id = (uint8_t)(session->next_session_id + 1u);
    if (session->next_session_id == 0u)
    {
        session->next_session_id = 1u;
    }
    session->expected_seq = (uint16_t)(frame->seq + 1u);
    session->last_ack_seq = frame->seq;
    session->state = OTA_BLE_SESSION_ACTIVE;

    now = session_now(session);
    session->last_frame_ms = now;
    session->last_data_ms = now;
    session->last_liveness_ms = now;
    session->last_durable_ms = now;

    /* ring 与 receiver 全部就绪后才置 ISR 活跃标志（此后 UART 字节
     * 由 ISR 直接分流进 overlay 环） */
    session->isr_active = 1u;

    session_send_ack_begin(session, OTA_BLE_STATUS_OK, session->session_id,
                           frame);
}

static void session_handle_end(ota_ble_session_t *session,
                               const ota_ble_frame_t *frame)
{
    uint8_t digest[32];
    ota_staging_result_t st;
    int seq;

    if (session->state != OTA_BLE_SESSION_ACTIVE)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2,
                         OTA_BLE_STATUS_ERR_STATE, frame->seq);
        return;
    }
    if (frame->session != session->session_id)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2,
                         OTA_BLE_STATUS_ERR_SESSION, frame->seq);
        return;
    }

    seq = session_seq_check(session, frame->seq);
    if (seq < 0)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2,
                         OTA_BLE_STATUS_ERR_SEQ, frame->seq);
        return;
    }
    if (seq > 0)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2, OTA_BLE_STATUS_OK,
                         frame->seq);
        session_touch(session);
        return;
    }

    /* sha 复述不符：发送端与 MCU staged 包身份不一致，
     * 整页擦除重传（合同 §5.7 ERR_SHA） */
    if (memcmp(frame->payload, session->package_sha256, 32u) != 0)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2,
                         OTA_BLE_STATUS_ERR_SHA, frame->seq);
        session_erase_staging_header(session);
        session_teardown(session);
        return;
    }

    /* 缺段：按 ERR_STATE 让发送端重新 BEGIN resume 续传 */
    if (session->progress.durable_off != session->total_len)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2,
                         OTA_BLE_STATUS_ERR_STATE, frame->seq);
        session_teardown(session);
        return;
    }

    boot_sha256_final(&session->sha, digest);
    if (memcmp(digest, session->package_sha256, 32u) != 0)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2,
                         OTA_BLE_STATUS_ERR_SHA, frame->seq);
        session_erase_staging_header(session);
        session_teardown(session);
        return;
    }

    /* ETSL@12 冻结语义 = whole-package CRC32（与 SD 路径
     * verified_package_crc32 同源），故对整包字节流增量收尾 */
    st = ota_staging_finalize(session->receiver,
                              boot_crc32_final(&session->pkg_crc),
                              session->target_vcode);
    if (st != OTA_STAGING_OK)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2,
                         OTA_BLE_STATUS_ERR_FLASH, frame->seq);
        session_teardown(session);
        return;
    }

    /* P3-3 修复：激活钩子缺失 = 平台配置残缺，fail-closed 回
     * ERR_FLASH——不发送伪 OK（ACK OK 后发送端会起算重启复核窗口，
     * 而无激活钩子的固件不会重启）。staging finalize 已持久化，此路径
     * 与「staging 有包、BCB 仍 CONFIRMED」的既有安全态一致。 */
    if (session->env.activate_staged == NULL)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_END2,
                         OTA_BLE_STATUS_ERR_FLASH, frame->seq);
        session_teardown(session);
        return;
    }

    session_send_ack(session, OTA_BLE_CMD_ACK_END2, OTA_BLE_STATUS_OK,
                     frame->seq);
    session_teardown(session);

    /* P3-3 修复：END 成功路径的激活序列（合同 §4.5 退出/恢复——成功
     * 路径随后重启进入 boot；staging→candidate 搬运与 BCB STAGED 提交
     * 与 SD 卡路径 Apply→Stage 同构，同步长跑、内部喂狗）。
     *
     * 顺序约束：ACK 先行——发送端据此释放传输层并起算重启复核窗口，
     * 不与激活时长赛跑；teardown 必须先于激活——释放 BLE overlay
     * owner 后，Apply 才能取得 PACKAGE overlay。 */
    if (session->env.activate_staged(session->target_vcode,
                                     session->total_len,
                                     (ota_sd_kind_t)session->pkg_kind) != 0)
    {
        /* 任一激活环节失败：活动 BCB 保持 CONFIRMED，设备继续运行
         * 旧版；发送端在复核窗口观测到版本未变即如实报失败。 */
        return;
    }
    if (session->env.system_reset != NULL)
    {
        session->env.system_reset();
    }
}

static void session_handle_caps(ota_ble_session_t *session,
    const ota_ble_frame_t *frame)
{
    uint8_t payload[OTA_PIPELINE_CAPS_BYTES];
    uint32_t nonce = pipeline_u32(frame->payload);
    size_t len;
    if (session->state != OTA_BLE_SESSION_IDLE || frame->session != 0u ||
        !session_pipeline_available(session) || session->env.send == NULL ||
        nonce == session->last_pipeline_epoch ||
        ota_pipeline_capabilities(nonce, payload) != OTA_PIPELINE_OK) return;
    len = ota_ble_frame_encode(session->tx_frame, sizeof(session->tx_frame),
        OTA_BLE_CMD_CAPS2_REPLY, 0u, frame->seq, payload, sizeof(payload));
    if (len != 0u && session->env.send(session->tx_frame, (uint16_t)len) == 0)
        session->caps_nonce = nonce;
}

static void session_handle_pipeline(ota_ble_session_t *session,
    const ota_ble_frame_t *frame)
{
    uint32_t epoch = pipeline_u32(frame->payload);
    uint8_t ack_cmd = ack_cmd_for(frame->cmd);
    if (session->pipeline == NULL)
    {
        session_pipeline_ack(session, ack_cmd, OTA_BLE_STATUS_ERR_STATE,
            frame->seq, epoch, 0u);
        return;
    }
    if (frame->session != session->session_id || epoch != session->pipeline_ack.epoch)
    {
        session_pipeline_ack(session, ack_cmd, OTA_BLE_STATUS_ERR_SESSION,
            frame->seq, epoch, frame->session);
        return;
    }
    if (frame->cmd == OTA_BLE_CMD_ABORT2)
    {
        session->last_ack_seq = frame->seq;
        session_teardown_aborted(session);
        return;
    }
    if (session->state != OTA_BLE_SESSION_ACTIVE)
    {
        session_pipeline_ack(session, ack_cmd, OTA_BLE_STATUS_ERR_BUSY,
            frame->seq, epoch, session->session_id);
        return;
    }
    if (frame->cmd == OTA_BLE_CMD_DATA2)
    {
        uint32_t off = pipeline_u32(frame->payload + 4u);
        uint32_t len = frame->len - 8u;
        uint16_t seq;
        int result;
        uint8_t status;
        if (off < session->pipeline_resume_off || off >= session->total_len ||
            off % OTA_STAGING_SEGMENT_SIZE != 0u)
        {
            session_send_ack(session, OTA_BLE_CMD_ACK_DATA2,
                OTA_BLE_STATUS_ERR_OFFSET, frame->seq);
            return;
        }
        /* Bind a retransmitted seq to its original absolute segment offset. */
        seq = (uint16_t)(session->pipeline_first_seq +
            (off - session->pipeline_resume_off) / OTA_STAGING_SEGMENT_SIZE);
        if (seq != frame->seq)
        {
            session_send_ack(session, OTA_BLE_CMD_ACK_DATA2,
                OTA_BLE_STATUS_ERR_SEQ, frame->seq);
            return;
        }
        result = ota_pipeline_receive(session->pipeline, epoch, off,
            frame->payload + 8u, len);
        if (result == OTA_PIPELINE_OK)
        {
            boot_sha256_update(&session->sha, frame->payload + 8u, len);
            boot_crc32_update(&session->pkg_crc, frame->payload + 8u, len);
            session->expected_seq = (uint16_t)(frame->seq + 1u);
            session->last_ack_seq = frame->seq;
        }
        if (result >= 0)
        {
            (void)ota_pipeline_snapshot(session->pipeline, &session->pipeline_ack);
            session_touch(session);
            session_touch_data(session);
            status = OTA_BLE_STATUS_OK;
        }
        else if (result == OTA_PIPELINE_ERR_PARAM) status = OTA_BLE_STATUS_ERR_LEN;
        else if (result == OTA_PIPELINE_ERR_CREDIT) status = OTA_BLE_STATUS_ERR_OFFSET;
        else status = OTA_BLE_STATUS_ABORTED;
        session_send_ack(session, OTA_BLE_CMD_ACK_DATA2, status, frame->seq);
        if (session->pipeline->stopped) session_teardown(session);
        return;
    }
    if (frame->cmd == OTA_BLE_CMD_END2)
    {
        ota_ble_frame_t end = *frame;
        uint16_t seq = (uint16_t)(session->pipeline_first_seq +
            (session->total_len - session->pipeline_resume_off +
                OTA_STAGING_SEGMENT_SIZE - 1u) / OTA_STAGING_SEGMENT_SIZE);
        if (frame->seq != seq)
        {
            session_send_ack(session, OTA_BLE_CMD_ACK_END2, OTA_BLE_STATUS_ERR_SEQ, frame->seq);
            return;
        }
        if (session->progress.durable_off != session->total_len ||
            !ota_pipeline_can_release(session->pipeline))
        {
            /* Do not run SHA-error header erasure against a live payload operation. */
            session_send_ack(session, OTA_BLE_CMD_ACK_END2, OTA_BLE_STATUS_ERR_STATE, frame->seq);
            session_teardown(session);
            return;
        }
        end.len = OTA_BLE_SHA256_SIZE;
        memcpy(end.payload, frame->payload + 4u, OTA_BLE_SHA256_SIZE);
        session_handle_end(session, &end);
    }
}

static void session_poll_pipeline(ota_ble_session_t *session)
{
    uint32_t now = session_now(session);
    int result;
    if (session->pipeline == NULL) return;
    if (session->state == OTA_BLE_SESSION_ACTIVE &&
        (uint32_t)(now - session->last_durable_ms) >= CONFIG_OTA_BLE_SESSION_TIMEOUT_MS)
        session_teardown_aborted(session);
    if (session->pipeline == NULL) return;
    result = ota_pipeline_poll(session->pipeline, now);
    if (session->state == OTA_BLE_SESSION_DRAINING)
    {
        if (ota_pipeline_can_release(session->pipeline))
        {
            if (session->pipeline_abort_reply)
                session_send_ack(session, OTA_BLE_CMD_ACK_ABORT2, OTA_BLE_STATUS_ABORTED,
                    session->pipeline_abort_seq);
            session->pipeline_abort_reply = 0u;
            session_teardown(session);
        }
        return;
    }
    if (result < 0)
    {
        session_send_ack(session, OTA_BLE_CMD_ACK_DATA2, OTA_BLE_STATUS_ERR_FLASH,
            session->last_ack_seq);
        session_teardown(session);
        return;
    }
    (void)ota_pipeline_snapshot(session->pipeline, &session->pipeline_ack);
    if (session->pipeline_ack.durable_off != session->progress.durable_off)
    {
        session->progress.durable_off = session->pipeline_ack.durable_off;
        session->last_durable_ms = now;
        session_send_ack(session, OTA_BLE_CMD_ACK_DATA2, OTA_BLE_STATUS_OK,
            session->last_ack_seq);
    }
}

static void session_handle_frame(ota_ble_session_t *session,
                                 const ota_ble_frame_t *frame)
{
    switch (frame->cmd)
    {
    case OTA_BLE_CMD_CAPS2:
        session_handle_caps(session, frame);
        return;
    case OTA_BLE_CMD_BEGIN2:
        session_handle_begin(session, frame);
        return;
    case OTA_BLE_CMD_DATA2:
    case OTA_BLE_CMD_END2:
    case OTA_BLE_CMD_ABORT2:
        session_handle_pipeline(session, frame);
        return;
    case OTA_BLE_CMD_GET_INFO:
        session_handle_get_info(session, frame);
        return;
    default:
        return;
    }
}

/* 帧级错误 NAK（长度/cmd/CRC 非法）：header 已尽力解出供回显。
 * GET_INFO 与未知 cmd 无 ACK 通道，静默丢弃。 */
static void session_handle_frame_error(ota_ble_session_t *session,
                                       ota_ble_parse_result_t result,
                                       const ota_ble_frame_t *frame)
{
    uint8_t status;
    uint8_t ack_cmd;

    if (result == OTA_BLE_PARSE_ERR_CRC)
    {
        status = OTA_BLE_STATUS_ERR_CRC;
    }
    else if (result == OTA_BLE_PARSE_ERR_FRAME)
    {
        status = OTA_BLE_STATUS_ERR_FRAME;
    }
    else
    {
        return;
    }

    ack_cmd = ack_cmd_for(frame->cmd);
    if (ack_cmd == 0u)
    {
        return;
    }
    if (ack_cmd >= OTA_BLE_CMD_ACK_BEGIN2 && ack_cmd <= OTA_BLE_CMD_ACK_ABORT2)
    {
        /* CRC/length failure cannot authenticate the request's epoch. */
        session_pipeline_ack(session, ack_cmd, status, frame->seq,
            session->pipeline != NULL ? session->pipeline_ack.epoch : 0u,
            session->pipeline != NULL ? session->session_id : 0u);
        return;
    }
}

static void session_feed_byte(ota_ble_session_t *session, uint8_t byte,
                              ota_ble_text_sink_t text_sink, void *text_ctx)
{
    ota_ble_frame_t frame;
    ota_ble_parse_result_t result;

    result = ota_ble_demux_feed(&session->demux, byte, text_sink, text_ctx,
                                &frame);
    if (result == OTA_BLE_PARSE_FRAME)
    {
        session_handle_frame(session, &frame);
    }
    else if (result == OTA_BLE_PARSE_ERR_FRAME ||
             result == OTA_BLE_PARSE_ERR_CRC)
    {
        session_handle_frame_error(session, result, &frame);
    }
}

/* ---- 公共 API ---- */

void ota_ble_session_init(ota_ble_session_t *session,
                          const ota_ble_env_t *env)
{
    if (session == NULL || env == NULL)
    {
        return;
    }
    memset(session, 0, sizeof(*session));
    session->env = *env;
    session->state = OTA_BLE_SESSION_IDLE;
    session->next_session_id = 1u;
    ota_ble_demux_init(&session->demux);
}

int ota_ble_session_active(const ota_ble_session_t *session)
{
    return session != NULL && session->state != OTA_BLE_SESSION_IDLE;
}

int ota_ble_session_isr_active(const ota_ble_session_t *session)
{
    return session != NULL && session->isr_active != 0u;
}

void ota_ble_session_isr_feed(ota_ble_session_t *session, uint8_t byte)
{
    if (session == NULL || session->isr_active == 0u)
    {
        return;
    }
    (void)ota_ble_ring_push_isr(&session->rx_ring, byte);
}

void ota_ble_session_feed_idle(ota_ble_session_t *session,
                               ota_ble_text_sink_t text_sink,
                               void *text_ctx, uint8_t byte)
{
    if (session == NULL)
    {
        return;
    }
    session_feed_byte(session, byte, text_sink, text_ctx);
}

#if defined(P34_OTA_PIPELINE_WAIT_RX) && P34_OTA_PIPELINE_WAIT_RX
void ota_ble_session_receive_pending(ota_ble_session_t *session)
{
    uint8_t byte;
    uint32_t budget = CONFIG_OTA_BLE_RX_RING_SIZE;
    if (session == NULL || session->pipeline == NULL ||
        !session->pipeline->pending || !session->pipeline->in_start) return;
    /* Pending pins both block buffers and the overlay even when parsing ABORT,
     * premature END or malformed DATA changes the session to DRAINING. */
    while (budget-- != 0u && ota_ble_ring_pop(&session->rx_ring, &byte) != 0)
        session_feed_byte(session, byte, NULL, NULL);
}
#endif

void ota_ble_session_pump(ota_ble_session_t *session)
{
    uint8_t byte;
    uint32_t budget = CONFIG_OTA_BLE_RX_RING_SIZE;

    if (session == NULL)
    {
        return;
    }

    /* 排空 overlay RX 环（ISR 产出；会话活跃期间文本字节丢弃）。
     * 一批内可含多帧与帧前缀，逐字节推进状态机。 */
    while (
        budget-- != 0u &&
        ota_ble_ring_pop(&session->rx_ring, &byte) != 0)
    {
        session_feed_byte(session, byte, NULL, NULL);
    }

    session_poll_pipeline(session);

    if (session->state != OTA_BLE_SESSION_ACTIVE)
    {
        return;
    }

    {
        uint32_t now = session_now(session);

        /* 会话超时：以有效帧（CRC 通过）为基准，纯噪声不重置
         * （防噪声流无限压制文本通道）。 */
        if ((uint32_t)(now - session->last_frame_ms) >
            CONFIG_OTA_BLE_SESSION_TIMEOUT_MS)
        {
            session_teardown_aborted(session);
            return;
        }

        /* 活性规则②（合同 §5.5）：500ms 无新段重发当前 block_bitmap，
         * 发送端据此补传缺段。初值非契约。 */
        if ((uint32_t)(now - session->last_data_ms) >=
                CONFIG_OTA_BLE_LIVENESS_MS &&
            (uint32_t)(now - session->last_liveness_ms) >=
                CONFIG_OTA_BLE_LIVENESS_MS)
        {
            session->last_liveness_ms = now;
            session_send_ack(session, OTA_BLE_CMD_ACK_DATA2,
                             OTA_BLE_STATUS_OK, session->last_ack_seq);
        }
    }
}
