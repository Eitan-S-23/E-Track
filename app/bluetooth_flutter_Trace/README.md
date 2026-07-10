# BLE 广播接收器

## Build Policy

This project must not be built locally. Use GitHub Actions for all compile/build verification and release artifacts. Do not run local build or packaging commands such as `flutter build`, `gradle build`, `./gradlew assemble*`, `xcodebuild`, `dart compile`, or platform package/signing commands.

一个美观的 Flutter BLE (蓝牙低功耗) 广播接收应用，支持扫描、连接和查看附近蓝牙设备的详细信息。

## 功能特性

### 🔍 设备扫描

- 实时扫描附近的 BLE 设备
- 美观的设备列表显示
- 信号强度指示器
- 设备连接状态实时更新

### 📱 设备管理

- 点击连接/断开设备
- 查看设备详细信息
- 支持多种设备类型图标
- 设备属性标签显示

### 📊 设备详情

- 设备基本信息（名称、ID、连接状态）
- 信号强度可视化显示
- 广播数据详细解析
- 服务 UUID 列表
- 制造商数据解码

### 🎨 美观界面

- Material Design 3 设计
- 流畅的动画效果
- 渐变色彩主题
- 响应式布局

### 🔐 权限管理

- 智能权限请求
- 权限教育对话框
- 蓝牙状态检测
- 错误处理机制

## 技术栈

- **Flutter**: 跨平台移动应用框架
- **flutter_blue_plus**: BLE 功能实现
- **GetX**: 状态管理和路由
- **flutter_animate**: 动画效果
- **permission_handler**: 权限管理

## 安装和运行

1. 确保已安装 Flutter SDK (3.0.0+)
2. 克隆项目

```bash
git clone <repository-url>
cd bluetooth_Trace
```

3. 安装依赖

```bash
flutter pub get
```

4. 运行应用

```bash
flutter run
```

## 权限要求

### Android

- `BLUETOOTH` - 蓝牙基础权限
- `BLUETOOTH_ADMIN` - 蓝牙管理权限
- `BLUETOOTH_SCAN` - 蓝牙扫描权限 (API 31+)
- `BLUETOOTH_CONNECT` - 蓝牙连接权限 (API 31+)
- `ACCESS_COARSE_LOCATION` - 粗糙位置权限
- `ACCESS_FINE_LOCATION` - 精确位置权限

### iOS

- `NSBluetoothAlwaysUsageDescription` - 蓝牙使用说明
- `NSBluetoothPeripheralUsageDescription` - 外设使用说明

## 项目结构

```
lib/
├── controllers/
│   └── ble_controller.dart          # BLE 控制器
├── pages/
│   ├── home_page.dart               # 主页面
│   └── device_detail_page.dart      # 设备详情页
├── widgets/
│   └── device_card.dart             # 设备卡片组件
├── utils/
│   └── permission_helper.dart       # 权限管理工具
└── main.dart                        # 应用入口
```

## 使用说明

1. **启动应用**: 应用会自动检查蓝牙状态和权限
2. **权限授予**: 首次使用时会显示权限说明对话框
3. **开始扫描**: 点击"开始扫描"按钮搜索附近设备
4. **查看设备**: 点击设备卡片查看详细信息
5. **连接设备**: 在设备卡片或详情页点击连接按钮
6. **设备信息**: 在详情页查看完整的设备和广播数据

## 支持的设备类型

应用会根据设备名称自动识别设备类型并显示相应图标：

- 📱 手机设备
- ⌚ 智能手表/手环
- 🎧 耳机/音响
- ⌨️ 键盘/鼠标
- 📺 电视设备
- 🚗 车载设备
- 📍 信标设备
- 🔵 通用蓝牙设备

## 兼容性

- **Android**: API 21+ (Android 5.0+)
- **iOS**: iOS 12.0+
- **Flutter**: 3.0.0+

## 常见问题

### Q: 扫描不到设备？

A: 请确保：

- 蓝牙已开启
- 已授予位置权限 (Android)
- 目标设备处于可发现状态

### Q: 连接失败？

A: 请检查：

- 设备是否支持连接（部分设备仅广播）
- 设备是否已被其他应用连接
- 距离是否足够近

### Q: 权限被拒绝？

A: 请在系统设置中手动授予蓝牙和位置权限

## 开发说明

本项目使用 GetX 进行状态管理，采用 MVC 架构模式。主要组件：

- **BleController**: 管理蓝牙扫描、连接和设备状态
- **PermissionHelper**: 处理权限请求和用户教育
- **HomePage**: 主界面，显示设备列表和扫描控制
- **DeviceDetailPage**: 设备详情页，显示完整设备信息

## 许可证

本项目采用 MIT 许可证。
