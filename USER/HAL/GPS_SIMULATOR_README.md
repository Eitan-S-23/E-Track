# GPS模拟器使用说明

## 📁 新增文件

需要将以下文件添加到Keil项目中：

1. **USER/HAL/HAL_GPS_Simulator.h** - GPS模拟器头文件
2. **USER/HAL/HAL_GPS_Simulator.cpp** - GPS模拟器实现文件

## 🔧 添加到Keil项目的步骤

1. 打开 `MDK-ARM_F435/proj.uvprojx`
2. 在项目树中找到 **HAL** 组
3. 右键点击 **HAL** 组 → **Add Existing Files to Group 'HAL'**
4. 选择以下文件：
   - `USER\HAL\HAL_GPS_Simulator.cpp`
   - `USER\HAL\HAL_GPS_Simulator.h` (可选，仅用于快速访问)
5. 点击 **Add** → **Close**

## ✅ 编译修复说明

已修复的问题：
- ✅ 添加了 `<math.h>` 头文件支持三角函数
- ✅ 添加了 `lvgl/lvgl.h` 支持日志输出
- ✅ 解决了Arduino `round` 宏与标准库冲突
- ✅ 将 `random()` 改为标准 `rand()` 函数
- ✅ 定义了 `PI` 数学常量
- ✅ 添加了随机数种子初始化
- ✅ **修复了速度计算错误（缺少毫秒转换因子，导致速度快1000倍）**
- ✅ **改进了GPX文件解析（从文件末尾读取4KB，避免跨缓冲区边界问题）**

## 🚀 启用GPS模拟器

在 `USER/App/Config/Config.h` 中已设置：

```cpp
#define CONFIG_GPS_USE_SIMULATOR  1  // 启用GPS模拟器
```

## 🔄 切换回真实GPS

将配置改为：

```cpp
#define CONFIG_GPS_USE_SIMULATOR  0  // 使用真实GPS硬件
```

## ⚙️ 模拟参数调整

在 `HAL_GPS_Simulator.cpp` 中可以调整以下参数：

```cpp
// 速度范围
#define SIM_SPEED_MIN_KPH     5.0f      // 最小速度 km/h
#define SIM_SPEED_MAX_KPH     30.0f     // 最大速度 km/h
#define SIM_SPEED_CHANGE_RATE 2.0f      // 速度变化率 km/h/秒

// 活动范围（相对于基准位置）
#define SIM_MOVEMENT_RANGE    0.001     // 约100米的纬度/经度范围

// 默认位置（如果没有轨迹文件）
#define DEFAULT_LONGITUDE  116.404      // 北京经度
#define DEFAULT_LATITUDE   39.915       // 北京纬度
#define DEFAULT_ALTITUDE   50.0f        // 海拔(米)
```

## 📝 编译注意事项

**当前配置：GPS模拟器已启用 (CONFIG_GPS_USE_SIMULATOR = 1)**

如果编译仍有问题，请检查：
1. HAL_GPS_Simulator.cpp 是否已添加到项目
2. 头文件搜索路径是否包含 USER、Libraries 等目录
3. 是否启用了 C++11 支持

## 🧪 测试验证

编译成功后，运行程序应看到串口输出：
```
GPS: Using GPS Simulator
GPS Simulator: Initializing...
GPS Simulator: Found track file: /Track/TRK_20251219_143052.gpx
GPS Simulator: Parsed last point (116.404123, 39.915678, 50.0)
GPS Simulator: Base position (116.404123, 39.915678), altitude: 50.0 m
```

如果SD卡中没有轨迹文件：
```
GPS: Using GPS Simulator
GPS Simulator: Initializing...
GPS Simulator: Cannot open track directory
GPS Simulator: No track file found, using default location
GPS Simulator: Base position (116.404000, 39.915000), altitude: 50.0 m
```

## 🐛 已知问题修复记录

### 版本 1.1 (2025-12-19)
**问题1：模拟速度过快**
- **现象**：GPS模拟器显示的移动速度比实际设置快约1000倍
- **原因**：速度单位换算缺少毫秒转换因子（只除以3600，缺少÷1000）
- **修复**：修改公式为 `speed / (3600 * 1000 * 111)`
- **影响代码**：HAL_GPS_Simulator.cpp:268

**问题2：无法读取SD卡保存的GPS位置**
- **现象**：模拟器不在轨迹文件最后保存的位置附近运动
- **原因**：使用256字节固定缓冲区逐块读取，可能漏掉跨边界的`<trkpt>`标签
- **修复**：改为从文件末尾向前4KB开始读取，使用动态缓冲区，确保找到最后一个GPS点
- **影响代码**：HAL_GPS_Simulator.cpp:155-256 (ParseLastGPSPoint函数完全重写)

