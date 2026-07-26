#ifndef __EEPROM_H
#define __EEPROM_H

#include "Arduino.h"

// AT24C02 I2C 设备地址（7-bit， Wire 自动左移）
#define EEPROM_I2C_ADDRESS    0x50

// AT24C02 页大小（字节）。跨页写会回卷到页首，安全写必须按页切片。
#define EEPROM_PAGE_SIZE      8

// EEPROM 单次写周期 tWR（datasheet 5ms）。ACK polling 上限 10ms。
#define EEPROM_ACK_POLL_MS    10

// byte 0xFF is reserved for the one-time EEPROM presence marker.
#define EEPROM_CAPACITY_BYTES   256u
#define EEPROM_INIT_MAGIC_ADDR  0xFFu
#define EEPROM_INIT_MAGIC_VALUE 0x55u

class EEPROM
{
public:
    EEPROM(){}
    ~EEPROM(){}

    // 初始化设备地址并探活（ACK poll 一次）。成功 true。
    bool Init(uint8_t addr = EEPROM_I2C_ADDRESS);

    // 安全多字节写：逐 8B 页写 + 每页 ACK polling（≤10ms）+ 全块读回比对。
    // 非空写必须完整落在 0x00..0xFE；0xFF 为初始化魔数保留地址。
    bool WriteBuffer(uint8_t reg, const uint8_t* buf, uint16_t len);

    // 检查保留魔数，并仅在缺失时通过底层单页路径初始化。此函数是 byte 0xFF
    // 唯一允许的写入口。
    bool EnsureInitMagic(void);

    // 多字节读。返回 true 仅当 Wire 事务全成且读齐 len 字节。
    bool ReadBytes(uint8_t reg, uint8_t* buf, uint16_t len);

    // 旧单字节 API（向后兼容）。内部走 WriteBuffer/ReadBytes 安全路径。
    // 保留 void 签名以不破坏既有调用方；写入失败仅记录于内部 lastError。
    void WriteByte(uint8_t reg, uint8_t dat);
    bool ReadByte(uint8_t reg, uint8_t* out);

    // 最近一次写/读是否成功（供 OTA 链路诊断）。
    bool LastOk(void) const { return lastOk; }

private:
    uint8_t Address;
    bool lastOk;

    // 单页（≤EEPROM_PAGE_SIZE）写事务：beginTransmission(addr)+write(reg)+write(data..)
    // +endTransmission，根据返回码判 NACK。
    bool WritePageRaw(uint8_t reg, const uint8_t* data, uint8_t n);
    // 写后 ACK polling：循环发零载荷 beginTransmission+endTransmission，
    // 从机应答 SUCCESS 即写周期结束；超时 EEPROM_ACK_POLL_MS 返回 false。
    bool WaitAckPoll(uint8_t addr);
};

#endif
