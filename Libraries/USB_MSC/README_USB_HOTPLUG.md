# USB热插拔功能说明

## 功能概述

本项目实现了USB MSC（大容量存储设备）热插拔功能，使用外部QSPI Flash (W25Q128, 16MB)作为存储介质。

### 主要特性

- ✅ **热插拔支持**：USB线缆插入/拔出自动识别
- ✅ **16MB存储空间**：使用W25Q128 QSPI Flash
- ✅ **启动时不初始化USB**：避免干扰Display等外设
- ✅ **自动连接/断开**：检测VBUS状态自动管理USB
- ✅ **高速读取**：通过XIP模式直接从QSPI读取
- ✅ **安全写入**：自动管理扇区擦除和XIP模式切换

## 工作原理

### 1. 启动流程
```
系统启动 → 初始化Display/SD等外设 → 启动USB热插拔检测任务 → 等待USB插入
```

### 2. USB插入检测
- 每200ms检测一次VBUS引脚（PA9）状态
- VBUS为高电平（5V）→ USB线缆已连接
- 检测到连接后等待100ms防抖
- 再次确认连接稳定后初始化USB

### 3. USB初始化流程
```
检测到USB插入
  ↓
配置USB GPIO（DP/DM/VBUS）
  ↓
启用OTG时钟和48MHz时钟源
  ↓
初始化USB设备（MSC模式）
  ↓
电脑识别为16MB U盘
```

### 4. USB断开流程
```
检测到USB拔出
  ↓
断开USB连接
  ↓
禁用中断和时钟
  ↓
释放资源
```

## 文件说明

### 核心文件
- **HAL_USB_Hotplug.cpp**: USB热插拔管理
- **msc_diskio.cpp**: QSPI Flash存储接口
- **qspi_cmd_en25qh128a.cpp**: QSPI Flash驱动

### 关键函数

#### USB_HotplugUpdate()
- 每200ms调用一次
- 检测USB线缆状态
- 自动调用USB_Connect()或USB_Disconnect()

#### USB_IsPlugged()
- 读取VBUS引脚状态
- 返回true表示USB已连接

#### USB_Connect()
- 初始化USB设备
- 配置为MSC设备（大容量存储）

#### USB_Disconnect()
- 断开USB连接
- 释放所有资源

## 配置说明

### 中断优先级
```c
USB OTG:    优先级1 (高)
QSPI EDMA:  优先级2 (中)
SDIO DMA2:  DMA2_Channel4中断已处理
Display:    使用DMA1_CHANNEL3
```

### VBUS检测
- 引脚：PA9 (OTG_PIN_VBUS)
- 模式：输入，下拉
- 检测周期：200ms

### 存储配置
```c
总容量：16MB (W25Q128)
块大小：512字节 (USB标准)
扇区大小：4KB
基地址：0x90000000 (QSPI1_MEM_BASE)
```

## 使用示例

### 正常工作流程

1. **设备启动**
```
Power: ON
...
W25Q128 Flash Test: PASS
SD: init...success
Display: init...success  ← 不再卡死
```

2. **插入USB线**
```
USB: Cable detected
USB: Initializing...
USB: Connected as MSC device (16MB W25Q128 QSPI Flash)
```
电脑识别为16MB U盘，可以读写文件

3. **拔出USB线**
```
USB: Disconnecting...
USB: Disconnected
```
U盘消失，程序继续正常运行

### 测试步骤

1. **验证Display不卡死**
   - 不连接USB
   - 观察Display能否正常初始化

2. **测试USB插入**
   - 插入USB线
   - 观察串口输出和电脑设备管理器
   - 电脑应识别为"AT32 QSPI Flash"

3. **测试文件读写**
   - 向U盘写入文件
   - 拔出USB，重新插入
   - 验证文件是否保存

4. **测试热拔插**
   - 多次插拔USB线
   - 观察程序是否稳定运行

## 故障排除

### 问题1：Display初始化卡死
**原因**：USB在启动时初始化干扰了Display的DMA
**解决**：已通过延迟USB初始化解决

### 问题2：USB无法识别
**检查项**：
- VBUS引脚连接是否正确（PA9连接到USB VBUS）
- USB线缆是否为数据线（非充电线）
- 串口是否显示"USB: Connected"

### 问题3：读写失败
**检查项**：
- QSPI Flash是否正常工作
- W25Q128测试是否通过
- XIP模式是否正确初始化

### 问题4：热插拔不工作
**检查项**：
- USB_HotplugUpdate任务是否已注册
- VBUS检测是否正常（可打印gpio_input_data_bit_read结果）
- 防抖延迟是否合适

## 技术细节

### VBUS检测原理
- PA9配置为输入模式，下拉
- 当USB线插入时，VBUS（5V）通过分压电阻作用到PA9
- MCU读取PA9为高电平，判断USB已连接

### XIP模式管理
- **读取**：使用XIP模式，直接从0x90000000地址读取
- **写入**：
  1. 关闭XIP模式
  2. 擦除扇区（4KB对齐）
  3. 写入数据
  4. 重新启用XIP模式

### DMA冲突避免
- Display: DMA1_CHANNEL3
- SDIO: DMA2_CHANNEL4 (已添加中断处理)
- QSPI: EDMA_STREAM1
- USB: 不使用DMA（使用FIFO模式）

## 版本信息

- 创建日期：2025-12-20
- MCU型号：AT32F435RGT7
- Flash型号：W25Q128 (16MB)
- USB协议：USB 2.0 Full Speed
- 设备类型：MSC (Mass Storage Class)

## 注意事项

1. ⚠️ **不要在启动时调用Usb_Init()**，这会导致Display卡死
2. ⚠️ **写入QSPI Flash前会擦除扇区**，确保数据备份
3. ⚠️ **USB仅在线缆连接时工作**，未连接时完全不影响系统
4. ⚠️ **VBUS必须正确连接**，否则无法检测USB插入
5. ⚠️ **HAL_USB_Hotplug.cpp需加入工程编译**
