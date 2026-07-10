# BSDiff GUI

一个现代化、简约的图形界面，用于生成、管理和推送二进制差分（bsdiff）补丁包。

## 功能特性

- 基于 PySide6 的现代简约界面
- 选择新旧文件路径及补丁生成路径
- 生成补丁前输入新旧文件版本号
- 自定义补丁文件名（默认为 patch.bin）
- 补丁包推送功能，可将生成的补丁上传至服务器
- 通过 MQTT 协议发送 OTA 升级信息
- 内置 bsdiff.exe 工具，无需单独安装

## 系统要求

- Windows 10+（已打包为可执行文件）

## 安装说明

### 方式一：使用可执行文件

1. 下载最新的发布版本
2. 解压缩到任意目录
3. 运行 `BSDiff_GUI.exe`

### 方式二：从源代码运行

1. 克隆代码库:

```
git clone https://github.com/yourusername/bsdiff_gui.git
cd bsdiff_gui
```

2. 安装依赖:

```
pip install -r requirements.txt
```

3. 运行应用程序：

```
python bsdiff_gui.py
```

## 使用方法

1. 通过界面选择旧版本和新版本文件
2. 输入旧版本号和新版本号
3. 指定补丁文件的保存位置（可选）
4. 点击"生成补丁"按钮
5. 如需上传到服务器，请勾选"生成后上传到云服务器"选项
6. 如需发送 OTA 通知，请勾选"通过 MQTT 发送 OTA 信息"选项并选择目标设备

## 服务器配置

服务器部分已集成到现有的 Flask 应用中，提供以下新功能：

- `/api/patches/upload` - 用于接收补丁文件
- `/api/patches/download/<filename>` - 用于下载补丁文件
- `/api/patches/notify` - 用于发送 MQTT 通知
- `/api/patches/list` - 获取补丁文件列表

启动服务器:

```
cd app
python http_server.py
```

## 打包与测试

### 打包为可执行文件

运行以下命令生成 Windows 可执行文件：

```
python package_app.py
# 或者直接运行
package.bat
```

生成的可执行文件位于`dist`目录下。

### 测试应用程序

运行测试脚本验证功能正常：

```
python test_app.py
# 或者直接运行
test.bat
```

## 数据库结构

补丁相关数据存储在以下表结构中:

```sql
CREATE TABLE IF NOT EXISTS patches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    old_version TEXT NOT NULL,
    new_version TEXT NOT NULL,
    file_path TEXT NOT NULL,
    download_url TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
)
```

## OTA 信息结构

发送到 MQTT 主题的 OTA 升级信息结构如下:

```json
{
  "ota_url": "http://example.com/api/patches/download/patch_123.bin",
  "client_version": "1.0.0",
  "package_version": "1.1.0",
  "timestamp": "2023-06-10 12:00:00"
}
```

## MQTT 主题格式

OTA 通知发送到 `ota/info/{user_id}/{device_id}` 主题。

## 故障排除

1. 如果补丁生成失败:

   - 确保 bsdiff 已正确安装并添加到系统 PATH
   - 检查文件权限是否正确

2. 如果上传到服务器失败:

   - 确认服务器 URL 是否正确
   - 验证会话 Cookie 是否有效
   - 检查网络连接

3. 如果 MQTT 通知发送失败:

   - 确认服务器 MQTT 连接是否正常
   - 验证选择的设备是否存在

4. 如果可执行文件运行失败:
   - 确保已安装 Visual C++ Redistributable
   - 确保 bsdiff.exe 位于系统 PATH 中

## 许可

MIT
