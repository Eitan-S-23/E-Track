#ifndef E_TRACK_OTA_BLE_FRAME_H
#define E_TRACK_OTA_BLE_FRAME_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* P3-1 BLE 帧层（合同 §5，冻结）。
 * 帧布局：A5 5A | u8 cmd | u8 session | u16 seq | u16 len | payload[len] | u16 crc16
 * - len = payload 字节数（不含 8B 帧头与 crc16）；
 * - crc16 = CRC16-CCITT-FALSE 覆盖 cmd..payload（不含 A5 5A 与自身），小端存储；
 * - 多字节整数一律小端（合同 §0 默认小端）。
 * 所有解析均为增量式单字节状态机，支持帧跨任意 UART read 边界、
 * 多帧同批与噪声后重新同步；任何校验失败在调用方产生 staging 副作用
 * 之前即可拒绝（CRC 是帧级最后关卡）。 */

#define OTA_BLE_SYNC0 0xA5u
#define OTA_BLE_SYNC1 0x5Au
#define OTA_BLE_HEADER_SIZE 8u
#define OTA_BLE_CRC_SIZE 2u
/* DATA payload 上限 = u32 off + 128B 段净荷（合同 §5.4/§5.5） */
#define OTA_BLE_MAX_PAYLOAD 132u
#define OTA_BLE_MAX_FRAME \
    (OTA_BLE_HEADER_SIZE + OTA_BLE_MAX_PAYLOAD + OTA_BLE_CRC_SIZE)

/* 下行命令（合同 §5.2）；0x80..0x84 为上行，parser 层拒绝其余保留值 */
#define OTA_BLE_CMD_GET_INFO 0x00u
#define OTA_BLE_CMD_BEGIN 0x01u
#define OTA_BLE_CMD_DATA 0x02u
#define OTA_BLE_CMD_END 0x03u
#define OTA_BLE_CMD_ABORT 0x04u
#define OTA_BLE_CMD_INFO 0x80u
#define OTA_BLE_CMD_ACK_BEGIN 0x81u
#define OTA_BLE_CMD_ACK_DATA 0x82u
#define OTA_BLE_CMD_ACK_END 0x83u
#define OTA_BLE_CMD_ACK_ABORT 0x84u

/* payload 定长（合同 §5.2.1/§5.3/§5.6） */
#define OTA_BLE_LEN_GET_INFO 0u
#define OTA_BLE_LEN_BEGIN 101u
#define OTA_BLE_LEN_END 32u
#define OTA_BLE_LEN_ABORT 0u
#define OTA_BLE_LEN_DATA_MIN 4u
#define OTA_BLE_LEN_ACK_BEGIN 10u
#define OTA_BLE_LEN_ACK_OTHER 9u
#define OTA_BLE_LEN_INFO 50u
/* INFO 固定字段（合同 §5.2.1） */
#define OTA_BLE_INFO_PROTO_VER 1u
#define OTA_BLE_INFO_MAX_WINDOW_SEGS 32u

/* ACK status（合同 §5.7 唯一来源；不得新增私有 wire status） */
#define OTA_BLE_STATUS_OK 0x00u
#define OTA_BLE_STATUS_ERR_FRAME 0x01u
#define OTA_BLE_STATUS_ERR_CRC 0x02u
#define OTA_BLE_STATUS_ERR_SEQ 0x03u
#define OTA_BLE_STATUS_ERR_SESSION 0x04u
#define OTA_BLE_STATUS_ERR_STATE 0x05u
#define OTA_BLE_STATUS_ERR_OFFSET 0x06u
#define OTA_BLE_STATUS_ERR_LEN 0x07u
#define OTA_BLE_STATUS_ERR_HDR 0x08u
#define OTA_BLE_STATUS_ERR_HW_REV 0x09u
#define OTA_BLE_STATUS_ERR_LAYOUT 0x0Au
#define OTA_BLE_STATUS_ERR_BOOT_VER 0x0Bu
#define OTA_BLE_STATUS_ERR_VERSION 0x0Cu
#define OTA_BLE_STATUS_ERR_BASE 0x0Du
#define OTA_BLE_STATUS_ERR_BUSY 0x0Eu
#define OTA_BLE_STATUS_ERR_FLASH 0x0Fu
#define OTA_BLE_STATUS_ERR_SHA 0x10u
#define OTA_BLE_STATUS_ERR_OTA_DISABLED 0x11u
#define OTA_BLE_STATUS_ERR_PROTO 0x12u
#define OTA_BLE_STATUS_ABORTED 0xFFu

/* CRC16-CCITT-FALSE（poly 0x1021、init 0xFFFF、不反射、xorout 0） */
uint16_t ota_ble_crc16(const uint8_t *data, size_t len);

typedef struct ota_ble_frame_t
{
    uint8_t cmd;
    uint8_t session;
    uint16_t seq;
    uint16_t len;
    uint8_t payload[OTA_BLE_MAX_PAYLOAD];
} ota_ble_frame_t;

/* 帧编码：payload 可为 NULL（len=0）。返回写入 dst 的总字节数；
 * 容量不足返回 0（不写半帧）。 */
size_t ota_ble_frame_encode(uint8_t *dst, size_t cap,
                            uint8_t cmd, uint8_t session, uint16_t seq,
                            const uint8_t *payload, uint16_t len);

typedef enum ota_ble_parse_result_t
{
    OTA_BLE_PARSE_IDLE = 0,      /* 需要更多字节 */
    OTA_BLE_PARSE_FRAME = 1,     /* 完整帧，out_frame 已填充 */
    OTA_BLE_PARSE_ERR_FRAME = 2, /* 长度/cmd 非法，整帧丢弃重同步 */
    OTA_BLE_PARSE_ERR_CRC = 3    /* crc16 校验失败，整帧丢弃重同步 */
} ota_ble_parse_result_t;

/* 增量 parser。状态机含同步头扫描，帧失败后自复位重新找 A5 5A。
 * ERR_FRAME/ERR_CRC 时 out_frame 的 cmd/session/seq 尽力填充（len=0），
 * 供调用方 NAK 回显被拒帧的 seq。
 * parser->bad_frames 统计被拒帧数（fail-closed 诊断，非测试标记）；
 * 该累计值跨 ota_ble_parser_reset 保留，parser 结构必须先整体清零
 * （如 memset / 所属上层结构的整体初始化）再开始喂字节。 */
typedef struct ota_ble_parser_t
{
    uint8_t state;
    uint8_t cmd;
    uint8_t session;
    uint8_t hdr_index;
    uint16_t seq;
    uint16_t len;
    uint16_t payload_index;
    uint16_t crc_rx;
    uint16_t crc_calc;
    uint32_t bad_frames;
    uint8_t payload[OTA_BLE_MAX_PAYLOAD];
} ota_ble_parser_t;

void ota_ble_parser_reset(ota_ble_parser_t *parser);

/* 喂一个字节；返回非 IDLE 时 *out_frame/错误码 有效。 */
ota_ble_parse_result_t ota_ble_parser_feed(ota_ble_parser_t *parser,
                                           uint8_t byte,
                                           ota_ble_frame_t *out_frame);

/* 顶层分流（合同 §5.1）：UART 收到 A5 5A 进入二进制处理器，
 * 其余字节走现有文本协议。
 * - IDLE：非 A5 字节交 text_sink（可为 NULL=丢弃，会话活跃期用法）；
 *   A5 进入 HOLD（单字节 hold-back，避免误吞文本）。
 * - HOLD：5A → 把 A5 5A 一起喂 parser 进入 BINARY；非 5A → A5 交文本，
 *   当前字节按 IDLE 规则重放（连续 A5 保持 HOLD，文本只漏一个 A5）。
 * - BINARY：字节全喂 parser；帧完成或帧失败后回 IDLE。
 *   帧失败时已消费字节不回吐文本（TinyBTPlus 对垃圾字节是丢弃语义，
 *   异常路径无害）。 */
typedef enum ota_ble_demux_state_t
{
    OTA_BLE_DEMUX_IDLE = 0,
    OTA_BLE_DEMUX_SYNC_HOLD = 1,
    OTA_BLE_DEMUX_BINARY = 2
} ota_ble_demux_state_t;

typedef struct ota_ble_demux_t
{
    ota_ble_demux_state_t state;
    ota_ble_parser_t parser;
} ota_ble_demux_t;

typedef void (*ota_ble_text_sink_t)(void *ctx, uint8_t byte);

void ota_ble_demux_init(ota_ble_demux_t *demux);

/* 喂一个字节。返回：
 *   OTA_BLE_PARSE_FRAME  —— *out_frame 出帧（demux 已回 IDLE）；
 *   OTA_BLE_PARSE_ERR_*  —— 帧被拒（demux 已回 IDLE，错误码供 NAK）；
 *   OTA_BLE_PARSE_IDLE   —— 无帧事件。 */
ota_ble_parse_result_t ota_ble_demux_feed(ota_ble_demux_t *demux,
                                          uint8_t byte,
                                          ota_ble_text_sink_t text_sink,
                                          void *text_ctx,
                                          ota_ble_frame_t *out_frame);

#ifdef __cplusplus
}
#endif

#endif
