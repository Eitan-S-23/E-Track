/**
 * @file EraseAndWriteFlash_template.c
 * @brief Flash擦除和写入函数模板 - 用户需要根据实际硬件平台实现
 *
 * 说明：
 * 1. 此文件仅作为参考模板，不参与电脑端编译
 * 2. 单片机端必须实现此函数，否则链接时会报错
 * 3. 函数需要处理Flash扇区擦除和数据写入
 * 4. 支持未对齐的地址和长度
 */

#include "interface.h"

// ============================================================================
// 根据你的硬件平台选择对应的实现
// ============================================================================

// ----------------------------------------------------------------------------
// 方案1: STM32 HAL库实现示例
// ----------------------------------------------------------------------------
#ifdef USE_STM32_HAL

#include "stm32f4xx_hal.h"  // 根据实际芯片修改头文件

// Flash配置（根据实际芯片修改）
#define FLASH_SECTOR_SIZE       4096    // Flash扇区大小（字节）
#define FLASH_BASE_ADDR         0x08000000
#define FLASH_APP_START_ADDR    0x08020000  // 应用程序起始地址

/**
 * @brief 获取Flash扇区号（根据地址）
 * @note 不同STM32芯片扇区大小可能不同，需要根据手册调整
 */
static uint32_t Get_Flash_Sector(uint32_t address)
{
    uint32_t sector = 0;

    // STM32F4系列示例（需根据实际芯片调整）
    if (address < 0x08004000) sector = FLASH_SECTOR_0;
    else if (address < 0x08008000) sector = FLASH_SECTOR_1;
    else if (address < 0x0800C000) sector = FLASH_SECTOR_2;
    else if (address < 0x08010000) sector = FLASH_SECTOR_3;
    else if (address < 0x08020000) sector = FLASH_SECTOR_4;
    else if (address < 0x08040000) sector = FLASH_SECTOR_5;
    // ... 添加更多扇区

    return sector;
}

/**
 * @brief Flash擦除和写入函数
 */
int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length)
{
    HAL_StatusTypeDef status;

    // 1. 解锁Flash
    HAL_FLASH_Unlock();

    // 2. 计算需要擦除的扇区范围
    uint32_t sector_start = address & ~(FLASH_SECTOR_SIZE - 1);
    uint32_t sector_end = (address + length - 1) & ~(FLASH_SECTOR_SIZE - 1);

    // 3. 擦除扇区
    FLASH_EraseInitTypeDef erase_init;
    uint32_t sector_error = 0;

    erase_init.TypeErase = FLASH_TYPEERASE_SECTORS;
    erase_init.Sector = Get_Flash_Sector(sector_start);
    erase_init.NbSectors = (sector_end - sector_start) / FLASH_SECTOR_SIZE + 1;
    erase_init.VoltageRange = FLASH_VOLTAGE_RANGE_3;  // 电压范围根据实际调整

    status = HAL_FLASHEx_Erase(&erase_init, &sector_error);
    if (status != HAL_OK) {
        HAL_FLASH_Lock();
        return -1;  // 擦除失败
    }

    // 4. 写入数据（按字节写入，也可以按字/双字写入以提高速度）
    for (uint32_t i = 0; i < length; i++) {
        status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_BYTE, address + i, data[i]);
        if (status != HAL_OK) {
            HAL_FLASH_Lock();
            return -2;  // 写入失败
        }
    }

    // 5. 锁定Flash
    HAL_FLASH_Lock();

    // 6. 验证写入（可选，但建议）
    if (memcmp((void *)address, data, length) != 0) {
        return -3;  // 验证失败
    }

    return 0;  // 成功
}

#endif // USE_STM32_HAL


// ----------------------------------------------------------------------------
// 方案2: ESP32实现示例
// ----------------------------------------------------------------------------
#ifdef USE_ESP32

#include "esp_partition.h"
#include "esp_flash.h"
#include "esp_log.h"

static const char *TAG = "OTA_FLASH";

/**
 * @brief Flash擦除和写入函数（ESP32）
 */
int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length)
{
    esp_err_t err;

    // 1. 获取OTA分区（假设写入到OTA_0分区）
    const esp_partition_t *partition = esp_partition_find_first(
        ESP_PARTITION_TYPE_APP,
        ESP_PARTITION_SUBTYPE_APP_OTA_0,
        NULL);

    if (partition == NULL) {
        ESP_LOGE(TAG, "OTA partition not found");
        return -1;
    }

    // 2. 计算相对于分区的偏移
    uint32_t offset = address - partition->address;

    // 3. 擦除Flash（ESP32按4KB扇区自动对齐）
    uint32_t erase_addr = offset & ~0xFFF;  // 4KB对齐
    uint32_t erase_size = ((offset + length + 0xFFF) & ~0xFFF) - erase_addr;

    err = esp_partition_erase_range(partition, erase_addr, erase_size);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Erase failed: %s", esp_err_to_name(err));
        return -2;
    }

    // 4. 写入数据
    err = esp_partition_write(partition, offset, data, length);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "Write failed: %s", esp_err_to_name(err));
        return -3;
    }

    // 5. 验证写入（可选）
    uint8_t *verify_buf = malloc(length);
    if (verify_buf != NULL) {
        err = esp_partition_read(partition, offset, verify_buf, length);
        if (err == ESP_OK) {
            if (memcmp(verify_buf, data, length) != 0) {
                free(verify_buf);
                ESP_LOGE(TAG, "Verify failed");
                return -4;
            }
        }
        free(verify_buf);
    }

    return 0;  // 成功
}

#endif // USE_ESP32


// ----------------------------------------------------------------------------
// 方案3: 通用RTOS + 外部Flash实现示例
// ----------------------------------------------------------------------------
#ifdef USE_EXTERNAL_FLASH

#include "spi_flash.h"  // 假设有外部Flash驱动

// 外部Flash配置
#define EXT_FLASH_SECTOR_SIZE   4096
#define EXT_FLASH_PAGE_SIZE     256

/**
 * @brief Flash擦除和写入函数（外部Flash）
 */
int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length)
{
    uint32_t sector_start = address & ~(EXT_FLASH_SECTOR_SIZE - 1);
    uint32_t sector_count = ((address + length - sector_start) + EXT_FLASH_SECTOR_SIZE - 1) / EXT_FLASH_SECTOR_SIZE;

    // 1. 擦除扇区
    for (uint32_t i = 0; i < sector_count; i++) {
        if (spi_flash_erase_sector((sector_start + i * EXT_FLASH_SECTOR_SIZE) / EXT_FLASH_SECTOR_SIZE) != 0) {
            return -1;  // 擦除失败
        }
    }

    // 2. 按页写入（通常外部Flash按页写入，如256字节）
    uint32_t offset = 0;
    while (offset < length) {
        uint32_t write_len = (length - offset > EXT_FLASH_PAGE_SIZE) ? EXT_FLASH_PAGE_SIZE : (length - offset);

        if (spi_flash_write(address + offset, (uint8_t *)data + offset, write_len) != 0) {
            return -2;  // 写入失败
        }

        offset += write_len;
    }

    // 3. 验证（可选）
    uint8_t verify_buf[EXT_FLASH_PAGE_SIZE];
    offset = 0;
    while (offset < length) {
        uint32_t read_len = (length - offset > EXT_FLASH_PAGE_SIZE) ? EXT_FLASH_PAGE_SIZE : (length - offset);

        if (spi_flash_read(address + offset, verify_buf, read_len) != 0) {
            return -3;
        }

        if (memcmp(verify_buf, data + offset, read_len) != 0) {
            return -4;  // 验证失败
        }

        offset += read_len;
    }

    return 0;  // 成功
}

#endif // USE_EXTERNAL_FLASH


// ----------------------------------------------------------------------------
// 方案4: 裸机实现示例（自定义Flash驱动）
// ----------------------------------------------------------------------------
#ifdef USE_BARE_METAL

// 假设你有以下底层Flash驱动函数
extern int flash_erase_sector(uint32_t sector_addr);
extern int flash_write_byte(uint32_t addr, uint8_t data);
extern uint8_t flash_read_byte(uint32_t addr);

#define FLASH_SECTOR_SIZE 4096

/**
 * @brief Flash擦除和写入函数（裸机）
 */
int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length)
{
    // 1. 计算需要擦除的扇区
    uint32_t start_sector = address & ~(FLASH_SECTOR_SIZE - 1);
    uint32_t end_addr = address + length - 1;
    uint32_t end_sector = end_addr & ~(FLASH_SECTOR_SIZE - 1);

    // 2. 擦除扇区
    for (uint32_t sector = start_sector; sector <= end_sector; sector += FLASH_SECTOR_SIZE) {
        if (flash_erase_sector(sector) != 0) {
            return -1;  // 擦除失败
        }
    }

    // 3. 写入数据
    for (uint32_t i = 0; i < length; i++) {
        if (flash_write_byte(address + i, data[i]) != 0) {
            return -2;  // 写入失败
        }
    }

    // 4. 验证
    for (uint32_t i = 0; i < length; i++) {
        if (flash_read_byte(address + i) != data[i]) {
            return -3;  // 验证失败
        }
    }

    return 0;  // 成功
}

#endif // USE_BARE_METAL


// ----------------------------------------------------------------------------
// 方案5: 调试模式（使用RAM模拟Flash，用于PC端测试）
// ----------------------------------------------------------------------------
#ifdef USE_DEBUG_MODE

#include <stdlib.h>
#include <string.h>

// 模拟Flash存储（仅用于调试）
static uint8_t simulated_flash[1024 * 1024];  // 1MB模拟Flash

/**
 * @brief Flash擦除和写入函数（调试模式，使用RAM模拟）
 */
int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length)
{
    // 检查地址范围
    if (address + length > sizeof(simulated_flash)) {
        return -1;  // 地址越界
    }

    // 擦除（填充0xFF）
    memset(&simulated_flash[address], 0xFF, length);

    // 写入数据
    memcpy(&simulated_flash[address], data, length);

    return 0;  // 成功
}

#endif // USE_DEBUG_MODE


// ============================================================================
// 通用注意事项
// ============================================================================

/*
 * 实现EraseAndWriteFlash函数时的注意事项：
 *
 * 1. **线程安全**: 如果使用RTOS，需要考虑互斥锁保护Flash操作
 *
 * 2. **性能优化**:
 *    - 尽量使用字/双字写入而非字节写入
 *    - 预先读取整个扇区，修改后再写回（如果需要保留扇区其他数据）
 *    - 使用DMA加速大块数据传输
 *
 * 3. **错误处理**:
 *    - 擦除失败应立即返回
 *    - 写入失败后应考虑是否需要恢复
 *    - 建议添加写入验证
 *
 * 4. **地址对齐**:
 *    - 函数应能处理未对齐的地址和长度
 *    - 擦除时需要计算完整的扇区范围
 *
 * 5. **电源管理**:
 *    - Flash操作期间避免进入低功耗模式
 *    - 考虑添加看门狗喂狗
 *
 * 6. **调试建议**:
 *    - 添加日志输出便于排查问题
 *    - 可以先在RAM中模拟测试
 *    - 验证读写是否成功
 */
