#include "EEPROM.h"
#include "Wire.h"

// Wire endTransmission 返回码（ArduinoAPI/WireBase.h）
#define WIRE_SUCCESS   0

bool EEPROM::Init(uint8_t addr)
{
    Address = addr;
    lastOk = true;

    // 探活：发一次零载荷事务，从机应答即存在。
    Wire.beginTransmission(Address);
    uint8_t r = Wire.endTransmission();
    lastOk = (r == WIRE_SUCCESS);
    return lastOk;
}

bool EEPROM::WaitAckPoll(uint8_t addr)
{
    // ACK polling（Atmel 推荐）：写后从机在 tWR 内不应答。
    // 循环发零载荷 beginTransmission+endTransmission，SUCCESS 即写周期结束。
    uint32_t start = millis();
    for (;;)
    {
        Wire.beginTransmission(addr);
        uint8_t r = Wire.endTransmission();
        if (r == WIRE_SUCCESS)
        {
            return true;
        }
        if ((uint32_t)(millis() - start) >= EEPROM_ACK_POLL_MS)
        {
            return false;  // 超时：从机仍 NACK 或总线异常
        }
        delay_ms(1);
    }
}

bool EEPROM::WritePageRaw(uint8_t reg, const uint8_t* data, uint8_t n)
{
    // 单页写事务：START + addr(W) + reg + data[0..n-1] + STOP。
    // n 不得 > EEPROM_PAGE_SIZE，且 (reg, reg+n-1] 不得跨页（由 WriteBuffer 保证）。
    Wire.beginTransmission(Address);
    Wire.write(reg);
    for (uint8_t i = 0; i < n; i++)
    {
        Wire.write(data[i]);
    }
    uint8_t r = Wire.endTransmission();
    return (r == WIRE_SUCCESS);
}

bool EEPROM::WriteBuffer(uint8_t reg, const uint8_t* buf, uint16_t len)
{
    lastOk = false;
    if (buf == 0 && len > 0)
    {
        return false;
    }

    if (len == 0)
    {
        lastOk = true;
        return true;
    }
    // End is exclusive. A value above 0xFF means the write touches the
    // reserved marker byte or crosses the physical EEPROM boundary.
    if ((uint16_t)reg + len > EEPROM_INIT_MAGIC_ADDR)
    {
        return false;
    }

    uint16_t off = 0;
    while (off < len)
    {
        // 当前页起点（向下按 8B 对齐），页内剩余可写量。
        uint8_t pageBase = reg + off;
        uint8_t pageOff  = pageBase & (EEPROM_PAGE_SIZE - 1);
        uint8_t pageRoom = EEPROM_PAGE_SIZE - pageOff;
        uint16_t left    = len - off;
        uint8_t n        = (left < pageRoom) ? (uint8_t)left : pageRoom;

        if (!WritePageRaw(pageBase, buf + off, n))
        {
            return false;  // NACK/总线错误
        }
        if (!WaitAckPoll(Address))
        {
            return false;  // 写周期超时
        }
        off += n;
    }

    // 全块读回逐字节比对（契约 §3.3）。
    uint8_t readback[EEPROM_PAGE_SIZE];
    uint16_t voff = 0;
    while (voff < len)
    {
        uint8_t chunk = (len - voff > EEPROM_PAGE_SIZE) ? EEPROM_PAGE_SIZE
                                                        : (uint8_t)(len - voff);
        if (!ReadBytes(reg + voff, readback, chunk))
        {
            return false;
        }
        for (uint8_t i = 0; i < chunk; i++)
        {
            if (readback[i] != buf[voff + i])
            {
                return false;  // 读回失配
            }
        }
        voff += chunk;
    }

    lastOk = true;
    return true;
}

bool EEPROM::EnsureInitMagic(void)
{
    uint8_t value = 0;
    if (!ReadBytes(EEPROM_INIT_MAGIC_ADDR, &value, 1))
    {
        return false;
    }
    if (value == EEPROM_INIT_MAGIC_VALUE)
    {
        return true;
    }

    lastOk = false;
    value = EEPROM_INIT_MAGIC_VALUE;
    if (!WritePageRaw(EEPROM_INIT_MAGIC_ADDR, &value, 1))
    {
        return false;
    }
    if (!WaitAckPoll(Address))
    {
        return false;
    }

    uint8_t readback = 0;
    if (!ReadBytes(EEPROM_INIT_MAGIC_ADDR, &readback, 1))
    {
        return false;
    }
    lastOk = (readback == EEPROM_INIT_MAGIC_VALUE);
    return lastOk;
}

bool EEPROM::ReadBytes(uint8_t reg, uint8_t* buf, uint16_t len)
{
    lastOk = false;
    if (buf == 0 && len > 0)
    {
        return false;
    }
    if (len == 0)
    {
        lastOk = true;
        return true;
    }
    if ((uint16_t)reg + len > EEPROM_CAPACITY_BYTES)
    {
        return false;
    }

    // 现有 Wire 缓冲 WIRE_BUFF_SIZE=32，一次可读 ≤32B；BCB 64B 跨两次读。
    uint16_t off = 0;
    while (off < len)
    {
        uint16_t chunk = (len - off > 32u) ? 32u : (len - off);

        Wire.beginTransmission(Address);
        Wire.write((uint8_t)(reg + off));
        uint8_t r = Wire.endTransmission();
        if (r != WIRE_SUCCESS)
        {
            return false;
        }

        uint8_t got = Wire.requestFrom(Address, (int)chunk);
        if (got != chunk)
        {
            return false;  // 未读齐
        }
        for (uint16_t i = 0; i < chunk; i++)
        {
            buf[off + i] = Wire.read();
        }
        off += chunk;
    }

    lastOk = true;
    return true;
}

void EEPROM::WriteByte(uint8_t reg, uint8_t dat)
{
    // 旧 void 签名保留兼容；内部走安全路径，结果存 lastOk。
    (void)WriteBuffer(reg, &dat, 1);
}

bool EEPROM::ReadByte(uint8_t reg, uint8_t* out)
{
    return ReadBytes(reg, out, 1);
}
