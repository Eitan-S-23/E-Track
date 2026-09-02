#ifndef E_TRACK_OTA_BLE_RING_H
#define E_TRACK_OTA_BLE_RING_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/* P3-1 BLE 传输层受控 RX 环（合同 §5.1：MCU UART 环形缓冲 >=4KB）。
 *
 * 环本体存放于 OTA overlay workspace（BEGIN 时获取、会话结束释放），
 * 只有会话活跃期间存在。生产者 = UART ISR（attachInterrupt 回调，
 * push），消费者 = 主循环泵（pop）：SPSC，head 仅 ISR 写、tail 仅泵写，
 * 与 Platform HardwareSerial 的 RX 环同一并发模型。
 * 环容量必须是 2 的幂（用掩码取模，避免 ISR 中除法）。 */
typedef struct ota_ble_ring_t
{
    uint8_t *buf;
    uint32_t size;
    uint32_t mask;
    volatile uint32_t head;   /* ISR 写 */
    volatile uint32_t tail;   /* 泵写 */
    volatile uint32_t dropped; /* ISR 写：环满丢弃的字节数（fail-closed 诊断） */
} ota_ble_ring_t;

/* size 必须是 2 的幂且非零；buf 由调用方提供（overlay 内子分配）。
 * 初始化只在无 ISR 竞争的上下文调用（BEGIN 流程内、置活跃标志之前）。 */
void ota_ble_ring_init(ota_ble_ring_t *ring, uint8_t *buf, uint32_t size);

/* ISR 上下文专用：压入一字节；环满丢弃并计数，返回 0。
 * 丢字节属于 fail-closed（下游 CRC 必然失败并触发重传），不试图扩容。 */
int ota_ble_ring_push_isr(ota_ble_ring_t *ring, uint8_t byte);

/* 泵上下文专用：弹出一字节；空返回 0。 */
int ota_ble_ring_pop(ota_ble_ring_t *ring, uint8_t *out_byte);

uint32_t ota_ble_ring_count(const ota_ble_ring_t *ring);

#ifdef __cplusplus
}
#endif

#endif
