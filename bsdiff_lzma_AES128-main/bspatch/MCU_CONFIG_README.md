# 单片机端配置指南

本文档说明如何在单片机端配置和使用 bspatch 差分还原功能（支持 AES128 解密 + LZMA 解压）。

---

## 一、编译配置

### 1.1 关闭调试模式
在单片机端，**必须关闭** `bspatch_debug` 宏，使用 Flash 写入模式：

```c
// 方法1: 在编译选项中不定义 bspatch_debug（默认为0）
// 方法2: 在 user/interface.h 中确保：
#define bspatch_debug 0
```

### 1.2 编译宏定义
根据你的平台添加以下宏定义：

```makefile
# Windows平台（如果使用Windows工具链）
-D_WIN32

# LZMA单线程模式（推荐）
-D_7ZIP_ST
```

### 1.3 内存优化配置
根据单片机RAM大小，可以调整解压缓冲区大小：

```c
// 在 user/interface.h 中修改（必须是4的倍数）
#define DCOMPRESS_BUFFER_SIZE 1024  // 默认1KB，可根据RAM调整为512/2048等
```

---

## 二、必须实现的函数

### 2.1 EraseAndWriteFlash 函数
这是**必须实现**的Flash写入函数，用于将还原后的数据写入Flash。

#### 函数原型：
```c
int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length);
```

#### 参数说明：
- `address`: 要写入的Flash地址
- `data`: 要写入的数据缓冲区
- `length`: 要写入的数据长度
- **返回值**: 0表示成功，非0表示失败

#### 实现要求：
1. **自动擦除**: 函数内部需要处理扇区擦除
2. **地址对齐**: 函数需要处理未对齐的地址和长度
3. **分块写入**: 如果需要，应支持跨扇区写入

#### 实现示例（STM32）：
```c
#include "stm32f4xx_hal.h"

// Flash扇区大小（根据实际芯片修改）
#define FLASH_SECTOR_SIZE 4096

int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length)
{
    HAL_StatusTypeDef status;
    uint32_t sector_start = address & ~(FLASH_SECTOR_SIZE - 1);  // 扇区起始地址
    uint32_t sector_count = ((address + length - sector_start) + FLASH_SECTOR_SIZE - 1) / FLASH_SECTOR_SIZE;

    // 解锁Flash
    HAL_FLASH_Unlock();

    // 擦除需要的扇区
    FLASH_EraseInitTypeDef erase_init;
    uint32_t sector_error;

    erase_init.TypeErase = FLASH_TYPEERASE_SECTORS;
    erase_init.Sector = Get_Sector(sector_start);  // 需要实现获取扇区号
    erase_init.NbSectors = sector_count;
    erase_init.VoltageRange = FLASH_VOLTAGE_RANGE_3;

    status = HAL_FLASHEx_Erase(&erase_init, &sector_error);
    if (status != HAL_OK) {
        HAL_FLASH_Lock();
        return -1;
    }

    // 写入数据（按字节或字写入，根据HAL库调整）
    for (uint32_t i = 0; i < length; i++) {
        status = HAL_FLASH_Program(FLASH_TYPEPROGRAM_BYTE, address + i, data[i]);
        if (status != HAL_OK) {
            HAL_FLASH_Lock();
            return -2;
        }
    }

    // 锁定Flash
    HAL_FLASH_Lock();

    return 0;
}
```

#### 实现示例（ESP32）：
```c
#include "esp_partition.h"
#include "esp_flash.h"

int EraseAndWriteFlash(uint32_t address, const unsigned char *data, uint32_t length)
{
    esp_err_t err;

    // 获取分区（假设是OTA分区）
    const esp_partition_t *partition = esp_partition_find_first(
        ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_0, NULL);

    if (partition == NULL) {
        return -1;
    }

    // 计算相对地址
    uint32_t offset = address - partition->address;

    // 擦除Flash（ESP32会自动对齐到4KB）
    uint32_t erase_size = (length + 4095) & ~4095;  // 向上对齐到4KB
    err = esp_partition_erase_range(partition, offset & ~4095, erase_size);
    if (err != ESP_OK) {
        return -1;
    }

    // 写入数据
    err = esp_partition_write(partition, offset, data, length);
    if (err != ESP_OK) {
        return -2;
    }

    return 0;
}
```

### 2.2 注册用户函数
在单片机启动时，需要注册内存和Flash操作函数：

```c
#include "interface.h"
#include <stdlib.h>  // for malloc/free

// 用户接口实例
interface bs_user_func = {
    .bs_malloc = (bs_malloc_func)malloc,          // 或使用自定义内存分配
    .bs_free = free,                               // 或使用自定义内存释放
    .bs_flash_write = NULL                         // 单片机端不使用此接口
};

int main(void)
{
    // 系统初始化
    HAL_Init();
    SystemClock_Config();

    // 注册用户函数（如果需要）
    bs_user_func_register(&bs_user_func);

    // ... 其他代码
}
```

---

## 三、使用流程

### 3.1 单片机端差分升级流程

```c
#include "interface.h"

int perform_ota_update(void)
{
    patch_header_t header;
    uint8_t *old_data = NULL;
    uint8_t *patch_data = NULL;
    uint32_t old_size, new_size, patch_size;
    uint32_t new_firmware_addr = 0x08040000;  // 新固件Flash地址（根据实际修改）

    // 1. 读取差分包头
    // 从存储设备（如SD卡、外部Flash等）读取patch header
    read_patch_header(&header);

    // 2. 解析头部信息
    old_size = header.ph_osize;
    new_size = header.ph_nsize;
    patch_size = BigtoLittle32(header.ph_psize);

    // 3. 读取旧固件数据（当前运行的固件）
    old_data = (uint8_t *)bs_user_func.bs_malloc(old_size);
    if (old_data == NULL) {
        return -1;
    }
    read_old_firmware(old_data, old_size);  // 从Flash读取旧固件

    // 4. 验证旧固件CRC
    uint32_t calc_crc = crc32(old_data, old_size);
    if (BigtoLittle32(header.ph_ocrc) != calc_crc) {
        bs_user_func.bs_free(old_data);
        return -2;  // 旧固件CRC不匹配
    }

    // 5. 读取压缩的差分包数据
    patch_data = (uint8_t *)bs_user_func.bs_malloc(patch_size);
    if (patch_data == NULL) {
        bs_user_func.bs_free(old_data);
        return -3;
    }
    read_patch_data(patch_data, patch_size);  // 从存储设备读取

    // 6. 执行差分还原（解密 + 解压 + patch）
    // 注意：new_data传NULL，因为单片机端直接写Flash
    int ret = bspatch_patch(header, old_data, old_size,
                           patch_data, patch_size,
                           new_firmware_addr,
                           NULL,  // 单片机端传NULL，直接写Flash
                           new_size);

    if (ret != 0) {
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(patch_data);
        return -4;  // 差分还原失败
    }

    // 7. 验证新固件（从Flash读回验证）
    uint8_t *verify_buffer = (uint8_t *)bs_user_func.bs_malloc(4096);
    uint32_t verify_crc = 0;
    // 分块读取新固件并计算CRC
    for (uint32_t i = 0; i < new_size; i += 4096) {
        uint32_t read_len = (new_size - i > 4096) ? 4096 : (new_size - i);
        read_flash(new_firmware_addr + i, verify_buffer, read_len);
        verify_crc = crc32_continue(verify_buffer, read_len, verify_crc);
    }

    if (BigtoLittle32(header.ph_ncrc) != verify_crc) {
        bs_user_func.bs_free(old_data);
        bs_user_func.bs_free(patch_data);
        bs_user_func.bs_free(verify_buffer);
        return -5;  // 新固件CRC不匹配
    }

    // 8. 清理资源
    bs_user_func.bs_free(old_data);
    bs_user_func.bs_free(patch_data);
    bs_user_func.bs_free(verify_buffer);

    // 9. 标记升级成功，准备重启
    mark_ota_success();

    return 0;  // 升级成功
}
```

---

## 四、内存需求评估

### 4.1 堆内存需求
- **旧固件**: `old_size` 字节（根据固件大小）
- **差分包**: `patch_size` 字节（压缩后，通常比新固件小很多）
- **解压缓冲**: `DCOMPRESS_BUFFER_SIZE` 字节（默认1KB）
- **LZMA解码器**: 约10-20KB

**总计**: 约 `old_size + patch_size + 20KB`

### 4.2 优化建议
如果RAM不足，可以考虑：
1. 减小 `DCOMPRESS_BUFFER_SIZE`（但会影响性能）
2. 使用外部RAM
3. 分块处理旧固件（需修改代码）

---

## 五、调试配置

### 5.1 启用调试输出
```c
// 在 user/interface.h 中
#define __DEBUG  // 启用调试打印

// 实现串口打印（根据你的平台）
#define bs_printf(...) printf("\r\n" __VA_ARGS__)
```

### 5.2 关闭调试输出（发布版本）
```c
// 在 user/interface.h 中
// #define __DEBUG  // 注释掉

#define bs_printf(...)  // 空宏，不输出
```

---

## 六、常见问题

### Q1: 内存不足怎么办？
A:
- 减小 `DCOMPRESS_BUFFER_SIZE`
- 使用外部SDRAM
- 考虑使用双Bank Flash，避免同时加载旧固件到RAM

### Q2: Flash写入失败？
A:
- 检查 `EraseAndWriteFlash` 函数实现
- 确认Flash区域没有写保护
- 验证地址范围合法

### Q3: CRC校验失败？
A:
- 确认大小端转换正确（使用 `BigtoLittle32` 宏）
- 检查数据传输完整性
- 验证差分包是否匹配当前固件版本

### Q4: 如何处理AES密钥？
A:
- AES密钥应硬编码在固件中或存储在安全区域
- 确保密钥长度为16字节（AES-128）
- 密钥应与生成差分包时使用的密钥一致

---

## 七、文件清单

单片机端需要的源文件：
```
bspatch/
├── bspatch/bspatch.c          # 核心差分算法
├── file/vFile.c               # 虚拟文件系统
├── user/interface.c           # 用户接口实现
├── lib/crc32.c                # CRC32校验
├── lzma/lzma_decompress.c     # LZMA解压（含AES解密）
├── lzma/7zFile.c              # 7z文件操作
├── lzma/LzmaDec.c             # LZMA解码器
├── lzma/LzFind.c              # LZMA查找算法
└── user/EraseAndWriteFlash.c  # 用户实现的Flash写入（需自己实现）
```

---

## 八、编译示例

### Keil MDK:
```
C/C++ Options:
  - Define: _7ZIP_ST
  - Include Paths: 添加所有头文件目录

Linker:
  - 确保有足够的堆空间（至少 old_size + patch_size + 20KB）
```

### GCC/Makefile:
```makefile
CFLAGS += -D_7ZIP_ST
CFLAGS += -I./bspatch -I./file -I./user -I./lib -I./lzma

SOURCES = main.c \
          bspatch/bspatch.c \
          file/vFile.c \
          user/interface.c \
          user/EraseAndWriteFlash.c \
          lib/crc32.c \
          lzma/lzma_decompress.c \
          lzma/7zFile.c \
          lzma/LzmaDec.c \
          lzma/LzFind.c
```

---

## 九、注意事项

1. ⚠️ **确保 `bspatch_debug = 0`**，否则不会调用Flash写入
2. ⚠️ **必须实现 `EraseAndWriteFlash` 函数**
3. ⚠️ **Flash地址必须合法且未被写保护**
4. ⚠️ **确保堆空间足够**（至少 old_size + patch_size + 20KB）
5. ⚠️ **差分包和固件版本必须匹配**
6. ⚠️ **AES密钥必须与生成差分包时一致**

---

## 十、技术支持

如有问题，请检查：
- `bspatch_debug` 宏是否正确设置
- `EraseAndWriteFlash` 函数是否正确实现
- 内存是否充足
- Flash地址和权限是否正确
