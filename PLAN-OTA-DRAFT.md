# PLAN-OTA-DRAFT.md — 单片机 BLE OTA 全链路方案（grill 过程草稿）

> 状态：Act 1 拷问进行中。每确认一个决策立即更新本文件。
> 最终锁定后整理为 `PLAN-OTA.md`，Act 2 由群内 codex（cc-connect relay）对抗审查，日志写 `PLAN-OTA-REVIEW-LOG.md`。

## 用户原始需求（六条）
1. GitHub Actions 编译构建固件 → 推送到 app 目录下已有 Cloudflare 后台 → CF 存储固件；手机点"更新"→ App 查询单片机固件版本与 CF 最新版本 → 有更新则从 CF 下载 → BLE 传给单片机 → 单片机验证后更新。
2. 先验证 `bsdiff_lzma_AES128-main/` 差分压缩加密代码可用，然后用于单片机差分升级，要求 bootloader + app1 + app2 架构。
3. CF 后台像管理 App 发布一样管理单片机固件发布。
4. 完善整体方案。
5. 一边询问一边把结果写入文件（本文件）。
6. 需求 2 进行时通过 cc-connect 群组 relay 调用 codex（grill-me-codex Act 2 也走群组 relay）。

## 已探明事实（2026-07-10 代码库探索）

### 单片机（AT32F435RGT7）
- 内部 Flash 1MB：`LR_IROM1 0x08000000 0x00100000` 单区，无 bootloader 偏移（`MDK-ARM_F435\Objects\X-Track.sct`，手动维护勿让 MDK 重新生成）。
- 当前固件 `Track.bin` = 553,940 B ≈ 541KB → **双全量 app 槽（2×541KB+boot）> 1MB，纯内部 flash 双槽不可行**。
- RAM 512KB（EOPB0 扩展后；scatter 已用满：主区 352KB + `sram_ext` 160KB）。bootloader 独立运行时 RAM 全部可用。
- 版本号仅字符串 `VERSION_SOFTWARE "v2.7"`（`USER\App\Version.h:28`），**无数字 version_code、无可被外部读取的固件头**。
- 蓝牙 = UART1 115200 透传 BLE 模块（`AT+NAME=XTrace`，`HAL_Bluetooth.cpp`）；`Libraries/Bluetooth/` TinyBTPlus 仅实现 `+MSG\r\n` 文本行解析 + 回显，`OTA()` 是空壳占位。**BLE 传输协议需从零设计**。透传实际吞吐预估 2-6KB/s @115200。
- `Libraries/W25Q128/` + `USER/HAL/HAL_W25Q128.cpp`（QSPI1, EN25QH128A 16MB）驱动代码存在但**未接入 HAL 初始化链**，板上是否焊接待确认（Q1）。
- SD 卡 SDIO+SdFat 常驻可用（地图/GPX 依赖，有写入先例）。
- Keil AC5 工程 → **无法在 GitHub 托管 ubuntu runner 上编译**；本机 `build_f435.ps1` + J-Link 烧录/RTT 闭环完整可用。
- RTT 命令框架（`App.cpp` CONFIG_RTT_DEBUG_CMD_ENABLE）可作为调试命令入口参考。

### bsdiff_lzma_AES128-main
- `bsdiff/`（PC 制包，CMake，已编出 `build/bin/bsdiff.exe`）+ `bspatch/`（还原端，`build/bin/bspatch.exe`、`BinCompare_GUI.exe`）。
- 格式：`patch_header`（osize/nsize/psize/ocrc/ncrc，大端）→ bsdiff 差分 → LZMA 压缩 → AES128-CTR 加密；CRC32 校验旧/新固件。
- MCU 端明确移植文档 `bspatch/MCU_CONFIG_README.md`：需实现 `EraseAndWriteFlash()`、注册 `bs_user_func`；`_7ZIP_ST` 单线程宏；`DCOMPRESS_BUFFER_SIZE` 默认 1KB；LZMA 解码器 ~10-20KB RAM。
- 参考实现将 old 整体 malloc 进 RAM（541KB 装不下 512KB RAM）→ **本项目 old 就在内存映射内部 flash，可直接指针访问规避**（需小改读取路径或用 vFile 抽象）。
- AES 密钥硬编码在固件内，需与制包端一致。
- 验证状态：**未验证**（任务 3：PC 端 diff→patch→比对闭环）。

### Cloudflare 后台（app/bluetooth_flutter_Trace/cloudflare/update-service/）— 固件管理已大半实现！
- 技术栈：Worker(TS) + D1 + R2 + Pages admin（`admin/`）+ vitest。
- 已有 D1 表（`migrations/0003_firmware_releases.sql`）：`firmware_releases`（device_model、version_code 单调、sha256、r2_key、github_url、transport='ble'、target_hardware、state/archived）+ `firmware_channels`（stable/beta、current_release_id、发布/回滚/停用/恢复审计）。
- 已有 Worker 端点（`worker/src/index.ts`）：
  - `GET /api/public/firmware/latest`
  - `GET /api/public/firmware/download`
  - `POST /api/ci/firmware/releases`
  - 实现在 `worker/src/firmware.ts`（656 行）。
- App 自身更新已有 `patches` 表（from_version_code/old_sha256/patch_format tracepatch|vcdiff）→ **固件差分表可直接借鉴此模型**。
- `.github/workflows/mcu-firmware-release.yml` 已有：workflow_dispatch 手动触发、要求 bin 已在仓库中 → GitHub Release + 注册 CF。**不编译固件**。
- 缺口：固件**差分包**的表/端点/生成流水线；`latest` 是否支持按设备当前版本返回差分（待读 firmware.ts 确认）。

### Flutter App（app/bluetooth_flutter_Trace/）
- `flutter_blue_plus ^1.32.11`（Android/iOS）+ `win_ble`（Windows）；已有扫描/连接/服务发现 UI（`lib/controllers/ble_controller.dart` 等）。
- 待确认：是否已有固件更新入口 UI、是否已对接 `firmware/latest`。

## 核心矛盾（grill 焦点）
- **矛盾 A**：用户要求 "bootloader+app1+app2"，但 1MB 内部 flash 放不下双全量槽 → 需重新定义 app2（外部 W25Q128 / SD 卡 / 压缩镜像槽）。
- **矛盾 B**：需求"GitHub Actions 编译构建"，但 AC5 工具链无法上云 → self-hosted runner / 本地编译+手动 dispatch（现状）/ 移植 GCC。
- **矛盾 C**：BLE 透传 115200 吞吐低 → 全量 541KB 传输约 2-5 分钟，差分包几十 KB 约几十秒；波特率可否提升取决于模块型号。

## 决策点清单（按依赖排序，一次一题）
| # | 决策点 | 状态 |
|---|--------|------|
| Q1 | W25Q128 是否焊接可用；BLE 模块型号/最高波特率 | ✅ 已锁 |
| Q2 | 分区架构（app2 的物理落点、防砖回滚布局） | ✅ 已锁 |
| Q3 | bspatch 合成执行位置（app 内 vs bootloader 内）与搬运职责划分 | ✅ 已锁（方案①）|
| Q3b | SD 卡差分包通道 + 菜单"关于设备"→"文件管理"改造 | ✅ 已锁 |
| Q4 | 全量升级兜底路径 | ✅ 已锁（通道 B/C，见 Q2）|
| Q5 | 固件头/版本号方案（version_code 嵌入与 BLE 查询） | 待问 |
| Q6 | BLE 传输协议（帧格式/ACK/续传/CRC） | 待问 |
| Q7 | GitHub Actions 编译模式 | 待问 |
| Q8 | CF 差分包管理（表/端点/谁生成/保留几版）与 AES 密钥管理 | 待问 |
| Q9 | App 端 UI/流程细节 | 待问 |
| Q10 | MCU 端升级 UI 与页面锁定 | 待问 |
| Q11 | 范围边界（F403A、模拟器、bootloader 工程形态、MAX_ROUNDS） | 待问 |

## 已锁定决策

### Q1 硬件事实（已确认 2026-07-10）
- **外部 Flash**：W25Q128 焊位实焊 **8MB** 芯片（EN25QH64 类），`Libraries/W25Q128` 驱动兼容可用；当前未接入 HAL 初始化链，OTA 方案需将 QSPI 驱动接入生产固件。
- **BLE 模块**：XY-MBO35A（深圳新一 Newbit，BLE 5.3 UART 透传，手册 `Doc/ble.pdf`，转档 `.claude/ble.md`）：
  - 默认 115200bps；`AT+UART=NUM` 支持 0:9600 ~ 8:921600（**6:230400 / 7:460800 / 8:921600**），重启生效 → 波特率提升列为传输优化项。
  - BLE 透传服务：**FFF0**（服务）、**FFF1 Notify**（MCU→APP）、**FFF2 Write**（APP→MCU），可用 AT+UUIDS/N/W 自定义 → Flutter flutter_blue_plus 直接对接。
  - Pin6 CTS 流控（高=模块缓冲满禁发）、Pin1 LINK 连接指示（高=已连接）；`+READY`/`+CONNECTED:TYPE,MAC`/`+DISCONN` 串口事件上报。
  - 一对四从机+主机能力（本方案只用单连接从机模式）。
  - 影响：OTA 下行大流量方向为 APP→FFF2→模块→UART→MCU，MCU 串口 RX 缓冲与及时消费是丢包关键；协议需带块级 CRC+ACK 重传兜底。

### 板载资源全清单（`PCB/Trace.enet` 网表提取，2026-07-10）
| 位号 | 器件 | 作用 | OTA 相关性 |
|------|------|------|-----------|
| U28 | **AT32F435RGT7** | 主 MCU，Cortex-M4，内部 flash 1MB | app 运行槽 |
| U30 | **W25Q128JVSIQ**（实焊 8MB，EN25QH 兼容）| **QSPI+EDMA** 外部 flash | download/backup 暂存槽 |
| U27 | **AT24C02CDBVRG** | **I2C EEPROM，256B @0x50**，已有驱动 | ★ 启动控制块（BCB）权威存储 |
| U13 | XY-MBO35A | BLE 5.3 UART 透传模块 | 主 OTA 通道 |
| U18 | **CH340N** | USB-UART 桥 | ★ 有线恢复第三通道 |
| U33 | SPL06-001 | I2C/SPI 气压计 | 与 EEPROM 可能共用 I2C |
| U32 | N10X_BLGA_18P | 6 轴 IMU（LSM6DSM+LIS3MDL 类）| 无关 |
| U35 | XPT2046 | 电阻触摸控制器 | 无关 |
| FPC2 | X05A15L18T 18P | 2.8" TFT 排线 | UI 显示 |
| U15/U31 | HX 3x6 轻触键 ×2 | 按键 | ★ 可作强制恢复入口 |
| U36 | WS-001 | 三向拨轮 | 导航输入/可作恢复入口 |
| U9/U34 | TP4056 / DW06D | 充电/电池保护 | 升级掉电风险相关 |
| U17/U19 | MCP1700 ×2 | 3.3V LDO | 供电 |
| USB2 | Type-C | 供电+CH340 数据 | 有线恢复物理口 |

**结论：OTA 硬件条件教科书级完整**——MCU + QSPI 外部 flash + 独立 I2C EEPROM + BLE + USB-UART + SWD，五路固件输入能力齐备，**硬件无需新增任何器件**。

### EEPROM/QSPI 驱动现状（已读代码确认）
- **AT24C02 真实可用**：`Libraries/EEPROM/EEPROM.{h,cpp}` + `USER/HAL/HAL_EEPROM.cpp`，I2C 地址 0x50，`WriteByte(reg,dat)`/`ReadBytes(reg,buf,len)` 单字节寻址覆盖 0-255。**byte 255 已被占用**为初始化魔数 0x55（`EEPROM_Check`），BCB 只能用 0-254。字节可写、无需擦除、~1M 次寿命 → 天然适合高频更新的启动标志。
- **W25Q128 = QSPI + EDMA**：`Libraries/W25Q128/qspi_cmd_en25qh128a.cpp`（`QSPI_EDMA_STREAM EDMA_STREAM1`），非 BOM 标注的普通 SPI，吞吐远高；仍需接入 HAL 初始化链。

### Q2 分区架构（已确认 2026-07-10，含 AT24C02 重构）

**用户决策**：(a) 接受 app2=外部 W25Q128 槽，但需全量升级作外部 flash 故障兜底（备选方案）；(b) bootloader 预留 64KB；(c) 需要 backup 防砖回滚。新增：板载 AT24C02 纳入设计。

**最终分区布局**：
```
内部 Flash 1MB (AT32F435 @0x08000000)：
  0x08000000  bootloader   64KB   （QSPI读 + I2C EEPROM读 + 内部flash编程 + CRC/SHA校验
                                     + bspatch可选 + BLE-UART/USB-UART最小接收器 + 跳转）
  0x08010000  app 运行槽    960KB  （app1，当前541KB余量充足；即 bootloader+app1 在内部）

外部 W25Q128 8MB (QSPI+EDMA)：
  0x000000  download 槽   1MB   （app2=BLE收到的差分/全量包 + bspatch合成的新全量镜像暂存）
  0x100000  backup 槽     1MB   （升级前当前运行版本的完整备份，防砖回滚源）
  0x200000  镜像清单/头   4KB   （各槽镜像的 size/CRC/SHA/version，双份冗余）
  0x201000  ~6MB 留白     （未来字体/图片资源，本方案不动）

AT24C02 256B I2C EEPROM (@0x50) = 启动控制块 BCB（★核心，独立于外部flash）：
  bytes 0-63    BCB 主副本：magic + struct_ver + boot_mode + upgrade_state
                            + app_ver_current(4) + target_ver(4)
                            + pending{type:full/diff, src:extflash/ble-stream, size(4), crc32(4)}
                            + retry_count + max_retry + ext_flash_healthy + bcb_crc(2)
  bytes 128-191 BCB 影子副本（掉电撕裂写保护，boot 时取 crc 正确的一份）
  byte 255      保留（现有 0x55 初始化魔数，勿动）
```

**为何把 BCB 放 AT24C02 而非内部 flash 页/外部 flash**（直接回应用户 (a) 外部 flash 故障顾虑）：
- 独立于 W25Q128：外部 flash 整片损坏/失焊时，bootloader 仍能从 EEPROM 读到启动决策 → 触发全量兜底恢复。
- 字节可写、无扇区擦除、~1M 寿命：升级状态机每步落盘（幂等、掉电安全），不消耗 flash 擦写寿命。
- 双副本 + 自带 CRC：抗掉电撕裂写与 EEPROM 位翻转。

**三级固件输入（纵深防御，覆盖"外部 flash 出问题"全场景）**：
- **通道 A（主，用户 OTA）**：BLE FFF2 → download 槽 → bspatch(差分)/直存(全量) → 校验 SHA → 备份当前到 backup 槽 → 写 BCB=apply → 重启 → bootloader 擦写内部 app → CRC 通过跳转。
- **通道 B（外部 flash 故障兜底 = 用户要的"全量升级备选"）**：bootloader **BLE 恢复模式**，直接经 BLE-UART 逐页接收**全量镜像**写入内部 app，**完全不依赖外部 flash**；BCB.boot_mode=2 或强制按键触发。慢、需手机全程在线，但绝对可用。
- **通道 C（有线/工厂恢复，白嫖 CH340N）**：bootloader 经 USB-UART 接收全量镜像，救砖不需 J-Link。

**防砖保证**：
- BCB.retry_count：bootloader 应用前自增、成功后清零；达到 max_retry → 放弃升级，从 backup 槽恢复；backup 也坏 → 进入通道 B/C 恢复模式并 UI 提示。
- 每步重启后 bootloader 重读 BCB 走状态机 → 任意步骤掉电均可恢复。
- **强制恢复入口（建议采纳）**：开机按住 U15/U31 轻触键（现有硬件，仅 bootloader 加读脚逻辑）→ 无视 BCB 强制进恢复模式，救"app 坏但 BCB 误标 healthy"的死角。

**建议新增（均为固件逻辑，硬件零新增）**：
1. BCB 结构体版本字段 struct_ver，未来可平滑升级 BCB 布局。
2. 强制恢复按键组合（复用现有轻触键/拨轮）。
3. app 运行槽尾部预留 fw_header（magic+version_code+size+sha256），使 BLE 可直接查询运行版本（解决现状"无数字版本号/无固件头"缺口，见 Q5）。

### Q3 bspatch 执行位置（已确认 2026-07-10）——方案①

**用户决策**：采用方案①（app 合成，bootloader 傻瓜式验证拷贝），并新增 **SD 卡差分包载入**作为第 4 输入通道 + 菜单改造。

- **app1** = 内部运行槽 = bspatch 旧参照（内存映射指针直读，不占 RAM，规避参考代码 541KB>512KB RAM 的坑）。
- **app2** = 外部 download 槽 = bspatch 新输出（合成好的**全量明文镜像**暂存）。
- **bootloader** = 只认全量镜像的验证拷贝器：**永不含 bspatch/LZMA/AES**，只需 QSPI读+I2C读+flash写+CRC/SHA。64KB 极宽裕，boot 逻辑最简=最可靠。
- app 侧 OTA 管线：收包 → AES128-CTR 解密 → LZMA 解压 → bspatch(旧=内部app,新→download槽) → SHA 校验 → 备份当前→backup槽 → 写 BCB → 重启。
- 安全影响：download 槽短暂存明文全量固件；按项目"安全优先级最低"准则接受。

### 第 4 输入通道：SD 卡差分包载入 + 菜单"文件管理"改造（已确认 2026-07-10）

**背景 bug（已定位）**：`MainMenu.cpp` 菜单首项"设备信息"(TXT_DEVICE) 与末项"关于设备"(TXT_ABOUT) 在 `OpenAction()` 里 `case MENU_ACTION_DEVICE:`/`case MENU_ACTION_ABOUT:` **合并 push 同一个 `Pages/SystemInfos`** → 两项功能完全重复（重叠）。

**用户决策**：把冗余的"关于设备"替换为"**文件管理**" → 查看 SD 卡文件 → 选择差分包载入升级 → **二次验证弹窗**确认后执行。

**实现要点**：
- SD 卡（SDIO+SdFat 常驻）作为 OTA 第 4 通道，与 BLE(通道A)/USB(通道C)/BLE恢复(通道B) 并列；**吞吐远超 BLE、无需手机**，且可放全量镜像做外部flash故障恢复。
- 复用 **`Pages/RouteSelect`** 的浏览器模式（正规 Page 类、已注册 AppFactory、走 LVGL fs `'/'` 盘符、目录浏览+扩展名过滤+已修复的行对齐/group 处理），**不要用孤儿 `Pages/FileBrowser`**（C 风格未注册死代码，建议一并清理）。
- 新页面（暂名 `Pages/FirmwareUpdate` 或 `Pages/FileManager`）：列出文件 → 过滤 OTA 包扩展名 → 选中弹二次确认（LVGL msgbox，用简单对象，禁 shadow/draw 回调）→ 确认后进入统一 OTA apply 管线（SD 读包 → 与 BLE 通道相同的 解密/解压/bspatch/校验/写download/BCB/重启）。
- 菜单表 `kMenuItems[]` 末项 `{ ICON_DETAIL, TXT_ABOUT, MENU_ACTION_ABOUT }` → 改为 `{ ICON_?, TXT_FILES, MENU_ACTION_FILES }`；`OpenAction` 拆出独立 case push 新页面；保留"设备信息"→SystemInfos 不动。
- 图标：文件管理需一枚新图标字形（iconfont），或复用现有 ICON_DETAIL/ICON_SETTING 暂代（待 Q10 定 UI 细节）。

### 【重要】分层模型澄清（用户纠正 2026-07-10）——CF 不是传输通道

之前误把 CF 与 BLE/SD 并列。正确分层：
```
① 构建源:   GitHub Actions(本地AC5编译) → Track.bin
② 打包:     打包工具 .bin →(bsdiff差分 / 全量)→ LZMA → AES → 套信封头 → .etu
③ 分发后端:  ★CF = Cloudflare(R2存.etu + D1元数据 + admin管理发布/回滚/渠道 + HTTP下载API)
              CF 是"云端分发中心/管理界面"，非传输方式
④ 到手机/PC: App经HTTP从CF下载.etu  /  用户PC下载.etu拷到SD卡
⑤ 到设备最后一跳【传输通道，彼此并列】:
     BLE(App→设备) | SD卡(卡→设备) | USB-UART(线→设备) | SWD(J-Link救砖)
```
- BLE 与 SD 同层（送字节进 MCU 的最后一跳）；CF 是上游第③层，给 App 提供下载，不直接碰 MCU。
- `.etu` 包格式跨 ③④⑤ 全程一致，只定义一次；SD 里的 `.etu` 通常是用户从 CF 下载后拷入，CF 始终是"最新固件"权威源。

### Q5 包格式与版本号（已确认 2026-07-10）

**bsdiff 已有 `patch_header_t`（`bspatch/user/interface.h:29`，已读代码确认）**：
```c
uint32_t ph_hcrc,ph_psize,ph_osize,ph_nsize,ph_ocrc,ph_ncrc;
uint8_t  ph_lzma_props[5];  uint64_t ph_original_size;
```
- **正确性已完善**：`ph_ocrc`=旧文件CRC32（装前校验"当前app是否正确旧版"，比版本匹配更硬）；`ph_ncrc`=新文件CRC32（合成后校验）；`ph_lzma_props`=解压参数。
- **缺身份信息**：无 magic / 无目标机型 / 无语义版本 / 无 full-diff 类型标识。

**决策：外套薄"OTA 信封头"，不重复 bsdiff 已有字段**：
```
.etu = [OTA信封头: magic"ETU\0" + struct_ver + device_model(F435/F403A)
                    + pkg_type(full/diff) + from_version_code + to_version_code
                    + payload_size + envelope_sha256]
       + [payload]:  diff → 原样(bsdiff patch_header_t + LZMA压缩差分)
                     full → 原样(全量镜像，可选LZMA压缩+AES)
```
- 双层职责：信封头管路由/UX显示/拒绝装错机型或错版本；bsdiff头(ocrc/ncrc)管差分正确性。
- 三通道(BLE/SD/CF)共用同一 `.etu` 格式。

**(a) 需新增打包步骤**：编译产物是 `.bin`（`fromelf --bin`）；`.etu` 由独立打包工具生成（`.bin` →与上一版diff→LZMA→AES→信封头），非编译环节，落点见 Q7/Q8。每次发布产出 **diff 包 + full 包各一**。

**(c) 语义化 version_code**：`主*1000+次`（v2.8→2008），单调递增，对齐 CF `firmware_releases.version_code`。

**固件头内嵌**：app 镜像内固定位置嵌 `fw_header{magic + version_code + version_str + build_time + image_size + sha256}`，供 BLE/SD OTA 查询"当前运行版本"（现状仅字符串"v2.7"、无数字版本、无固件头 → 必须新增）。`AT+VER?` 读的是 BLE 模块版本，**非**本固件版本，不可混用。

### 【更正】Q7 GitHub Actions 编译——"AC5 不能上云"说法不准确（2026-07-10 查证）

上一轮"AC5 无法在云端 runner 编译"**不准确**。查证 ARM 官方 KA006350 + UBL 迁移文档后的精确结论：

- **技术可移植性不是障碍**：AC5 二进制可缓存进仓库/runner 执行（Windows runner 跑 `armcc.exe`，或 Linux DS-5 版）。
- **真正死结 = 授权**，两道叠加：
  1. 固件 541KB → 必须付费 **MDK-Professional**（免费 Community/Lite 有 32KB 上限，出局）。
  2. Keil 传统授权 **node-locked（机器锁 HostID/MAC）**；GitHub 托管 runner 是**临时 VM，每次换 HostID** → 机器锁校验必失败（ARM KA006350 明述："Node-locked licenses unsuitable for ephemeral runners"）。
- **"很多项目 Action 里就能编译"** = 绝大多数用免费 `arm-none-eabi-gcc`（无授权），对本项目即换编译器（方案③，AGENTS.md 禁止 + 回归风险）。
- **ARM 官方 CI 方案 = UBL（User-Based Licensing 订阅授权）**：runner 启动脚本 `armlm activate` 拿 token 激活，**可在云端临时 runner 用** → 衍生方案 ①b。

**更正后选项矩阵**：
| 方案 | 真云端 | 需常驻机器 | 授权前提 | 成本/复杂度 |
|---|---|---|---|---|
| ① 自托管持久 runner（本机 Keil）| 否 | 是 | 现有 Keil 授权即可 | 最低，复用 build_f435.ps1 |
| ①b 托管 runner + UBL | ✅是 | 否 | **需 MDK-Pro UBL 订阅** | 高（每次装 Keil+激活 5-10min）|
| ② 本地编译 + Action 发布打包 | 否 | 否 | 无 | 低，"编译"人肉 |
| ③ 迁 GCC/AC6 | ✅是 | 否 | 无（免费）| 极高 + 违反 AGENTS.md |

**推荐 ①**（业界"私有工具链 CI"标准答案 = 持久自托管 runner）。**①b 是唯一"真云端 + 保留 AC5"路径，但需 UBL 订阅 + 装 Keil 开销**。
**待用户答**：手上 Keil 授权类型（MDK-Pro 永久 node-locked / MDK-Pro UBL 订阅 / 评估版）→ 决定 ①b 是否可行。

来源：ARM KA006350、ARM 109727 UBL 迁移文档。

### Q7 授权查证结果（2026-07-10 实查本机 Keil）

**证据**（`D:\install\keil5 mdk\TOOLS.INI`）：
- `NAME="SU","1"` / `EMAIL="1"` / `ORGANIZATION="1"`（占位符注册信息）
- `TOOL_VARIANT=mdk_std`，`[ARM] VERSION=5.43a`
- `LIC0=76F5U-S9RCY-IIS5V-P4QRT-T05QJ-XSN6B`（经典 Keil MDK PSN 五段式单用户序列号）

**判定：node-locked 单用户授权（PSN 本地激活，绑定本机），非 UBL 订阅。**
- `armlm.exe` 仅因 AC6/armclang 默认自带而存在，不代表配置了 UBL。
- AC5（armcc）早于 UBL 时代，走老式 Keil 授权，不用 armlm/UBL。
- **→ 方案 ①b（云端 runner + UBL）对本机不可行**（无 UBL 订阅；授权锁死本机）。真云端需另购 MDK-Pro UBL / 自建 FlexLM 浮动授权服务器 / 换 GCC，均属更大工程。

**"商业云端编译是否都用 GCC" 澄清**：否。商业团队在 CI 用 ARM Compiler 的三种授权方式：① 自托管 runner（机器锁/座位授权，最常用）② FlexLM 浮动授权服务器（网络借 seat）③ UBL 订阅。**无一是"机器锁 + 托管临时 runner"**。公开 CI 多见 GCC 仅因其免费无授权、适配临时公共 runner。AC5 已 EOL，商业 CI 用它基本靠自托管/浮动授权。

**结论：受本机授权（机器锁）约束，编译只能选 ①（本机作 self-hosted runner）或 ②（本地编译+Action 发布打包）。推荐 ①。待用户最终选 ①/②。**

### Q7 最终定案（2026-07-21 用户拍板）：改用 GCC ✅ 已验证

用户决策：**固件 CI 编译改用 GCC 工具链**。转换脚本 `D:\github\other\keil_translate_cmake\keil_uvprojx2cmake.py` 生成 `MDK-ARM_F435/cmake-generated/` CMake 工程（VSCode tasks.json 指向它；根目录旧 CMakeLists.txt+build-gcc/ 为一代废弃产物建议清理）。AC5 Keil 工程保留本地开发，GCC 走 CI/OTA 发布链路。

**可移植性改造（2026-07-22 完成并验证）**：
- 曾有三类阻塞：46 处项目绝对路径、3 个 Keil PACK include、2 行硬编码工具链 -isystem（multilib C++ 头，实测不可删）
- 处理：PACK 头 vendor 进仓库 `vendor/CMSIS/Include`(2.1MB)+`vendor/AT32F435_437_DFP/{Peripherals/inc,Device/Include}`(844KB)；用户已将修改**回灌转换脚本并重新生成**——路径全部 `${CMAKE_CURRENT_LIST_DIR}` 相对化，multilib 头目录用 `-print-sysroot`/`-dumpfullversion`/`-print-multi-directory` 三级动态推导（含 sysroot 回退、v7e-m+fp→v7+fp 兼容映射、bits/c++config.h 存在性校验）
- **验证（2026-07-22）**：全新目录 configure+Debug 全量构建 exit=0；FLASH 603,112B/1MB=57.52%、RAM 299,024B/352KB=82.96%、RW_IRAM2 100%(固定段)；objcopy 出 bin 与用户 VSCode 构建产物**字节数一致（603,112B）**
- AC5 语法处理：转换副本 `cmake/sources/HAL_FaultHandle_*.cpp`、`main_*.cpp` 替换原文件参与编译；LiveMap.cpp 手写 system_core_clock 声明冲突已删
- CI 产物：ubuntu runner 构建 target X_Track 后直接 `arm-none-eabi-objcopy -O binary/-O ihex`（不依赖 Windows 专用 run_artifacts.bat）
- Release(-Oz) 配置验证进行中（此前疑似 zlib/PNGdec 优化级编译问题待复核；CI 首版可用 Debug(-Og) 与本地验证保持一致）

### CI/CF/APP 现状盘点（2026-07-21 勘察）

**根目录 `.github/workflows/` 已有 5 个工作流**：
- `build.yml`（Flutter APK/EXE）：changes job 以 git diff 判定 `app_build_required`，只匹配 `app/bluetooth_flutter_Trace/(pubspec|lib/|android/|windows/|assets/|third_party/)` → **改固件不触发 APP 构建，互不触发已半实现**
- `mcu-firmware-release.yml`：手动 dispatch(firmware_path/device_model/version_name/version_code/notes/hardware) → GitHub Release → `build-firmware-release-metadata.mjs` → 可选 wrangler d1 migrate+deploy → `upload-firmware-r2-asset.mjs`(R2) → `register-firmware-release.mjs`(worker 注册,TRACE_DEPLOY_TOKEN) → **发布链完整，唯一缺编译环节**
- `cloudflare-update-service.yml`(typecheck,paths 已配)、`deploy-cloudflare-admin.yml`(手动)、`wechat-notify.yml`(全 push)
- Secrets/vars 体系已建：CLOUDFLARE_ACCOUNT_ID/API_TOKEN、TRACE_UPDATE_SERVICE_URL、TRACE_DEPLOY_TOKEN、TRACE_R2_BUCKET、TRACE_UPDATE_SERVICE_WRANGLER_ENV/D1_DATABASE/AUTO_DEPLOY

**CF worker 固件 API 已完备**（`worker/src/firmware.ts`）：`handleFirmwareLatest`(appId/deviceModel/channel/currentVersion(Code)→updateAvailable+签名URL,含限流/CHANNEL_STOPPED/archived/R2校验) + `RegisterFirmwareReleaseRequest`(CI 注册候选,含 sha256/sizeBytes/transport/minAppVersionCode/isFormalRelease) + D1 FirmwareChannelRow/FirmwareReleaseRow(channel.current_release_id 发布指针)。⚠️ **admin_actions.ts 无 firmware 操作 → admin 端固件晋升/发布/回滚待补（任务3 真实缺口）**

**Flutter 端已有**：`lib/services/ota_service.dart`(checkFirmwareUpdate→CF latest + 下载 + SHA256 验证)、`lib/pages/ota_upgrade_page.dart`。**缺 BLE 传输到 MCU 环节**

**版本源**：`USER/App/Version.h`：VERSION_FIRMWARE_NAME "X-TRACK"/VERSION_SOFTWARE "v2.7"/VERSION_HARDWARE "v1.0" → CI 提取 version_name；version_code=`git rev-list --count HEAD`

## 任务2 验证记录：bsdiff_lzma_AES128 闭环（2026-07-21 实测通过 ✅）

**代码**：`bsdiff_lzma_AES128-main/`（bsdiff=PC 制包/bspatch=打补丁，各含 CMake 工程，现成 exe 在 `*/build/bin/`；MinGW gcc 15.2 可重编）

**正向闭环（真实固件）**：旧=GCC X-Track.bin 603,112B，新=模拟改动(200 处异或+尾部 63B)；`bsdiff -aes 1`→LZMA(dict 4KB)+AES-128-CTR→**补丁 1,062B**；`bspatch`→解密+流式解压+合成→**cmp 字节级一致 ✅**

**负路径与四坑**：
- 旧固件 CRC 不匹配→正确拒绝(ph_ocrc)✅；补丁翻转 1 字节→解压中途截断
- 坑1：PC 工具 exit code 恒 0 → CI 解析 stdout + 制包后强制 bspatch 自验
- 坑2：36B 包头(hcrc/psize/osize/nsize/ocrc/ncrc+LZMA props5B+原始大小8B)**无补丁体自身 CRC** → 兜底=合成后对 download 槽全镜像算 CRC 对比 ph_ncrc,通过才置升级标志（方案强制）
- 坑3：PC bspatch 靠文件名 `_encrypt` 判断解密；MCU 走库接口 `bspatch_patch()` 不受影响,加密标记放 .etk 外层头
- 坑4：AES key 硬编码教科书示例 key(2b7e1516...) → **生产必须换**（固件编译期注入/CI Secrets 注入）

**MCU 集成**（`bspatch/user/interface.h`）：注册 `bs_flash_write`(自带擦除)/`bs_malloc`(峰值~20KB 堆)/`bs_free`；DCOMPRESS_BUFFER_SIZE=1024；LZMA 流式解压逐块写 → App 内合成可行(384KB RAM)，**bootloader 无需含 LZMA/bspatch**

### Q7 补充：CMake 生成物绝对路径问题的处理方式（2026-07-21 修订）

- `MDK-ARM_F435/cmake-generated/CMakeLists.txt` 为 `keil_uvprojx2cmake.py` 脚本生成物，**不手工修改**（会被重新生成覆盖）。
- 我方已实测验证可移植改法（46 处项目路径相对化、3 处 PACK 头映射 vendor/、2 处 -isystem 动态推导、1 处 -include 相对化、artifacts 跨平台化），全新目录 configure 通过；手工验证版已回滚，另存参考件 `.claude/CMakeLists-portable-reference.txt`。
- **修复责任移交转换脚本项目的 agent**：提示词已写至 `.claude/prompt-keil2cmake-portable.md`（自包含：背景、VSCode 任务不破坏约束、五类改动 before/after、验收标准 5 条含 603,112 字节基线）。
- 仓库侧已完成的配套：`vendor/CMSIS/Include`、`vendor/AT32F435_437_DFP/{Peripherals/inc,Device/Include}`（2.9MB 59 头文件）已拷入仓库；`USER/App/Pages/LiveMap/LiveMap.cpp` 删除与官方头冲突的 `system_core_clock` 手写声明（源码修复，保留）。
- **CI 工作流落地前置条件 = 脚本 agent 完成生成器修改并重新生成**。
