# P3-2 research：设备身份链权威来源与 provider 设计决策

日期：2026-09-03 ｜ 状态：编码前研究结论（派工书 docs/ota-prompts/prompt-P3-2-implementation.md）

## 1. 现状盘点（P3-1 留下的接入边界）

- `Libraries/OTA/ota_ble_session.h:52-70`：`ota_ble_env_t.info_provider(ota_ble_info_t*)`
  是 P3-1 预留的 INFO 内容口；session 层（`session_handle_get_info`，
  ota_ble_session.c:296）在 provider 为 NULL 或返回 0 时静默丢弃 GET_INFO，
  proto_ver=1 / max_window_segs=32 由 session 层填（frame.h:51-52 冻结常量）。
- `USER/HAL/HAL_Bluetooth.cpp:29-98`：P3-1 放的占位身份链 `ble_device_init()`，
  注释明示「P3-2 增强时替换此处」。占位实现的缺陷：
  - `model = "X-Track"`（违反 OTA-XC-DEVICE-MODEL，正式值 `E-Track\0`）；
  - `hw_rev/layout_id/boot_version` 硬编码 1（未从校验后的 fw_header 实值取）；
  - 不读 BCB（派工书要求 BCB 仲裁为输入、IO 失败 fail closed）。
  - raw SHA-256 的计算本身正确（全镜像 [0,image_len) 原始字节，含 sha/crc 实值字段）。
- `USER/App/Utils/OtaUpdate/OtaUpdate.cpp:237-286`：SD 路径 `InitializeDevice()`
  做同样的 fw_header 校验 + raw SHA8（`CurrentImageRawSha8`），字段语义与新链一致。
  **本卡不改它**（P2 已收口资产，行为等价无需迁移；重复实现是既存债务，
  在 §7 登记后续迁移建议）。

## 2. INFO 各字段的唯一权威来源（逐字段裁定）

| 字段 | 权威来源 | 依据 |
|---|---|---|
| model | 冻结常量 `"E-Track\0"`（7 ASCII + NUL = 8B） | OTA-XC-DEVICE-MODEL：正式线端值；binary §5.2.1 的 `X-Track\0` 是「如」示例，权威裁定覆盖之；MCU 不得截断发送 `e-track-at32f435` |
| hw_rev | 校验通过后的 `fw_header.hardware_rev` 实值 | OTA-XC-INFO-MAPPING「真实身份来自运行镜像」；validate 已确保 == BOOT_FW_HARDWARE_REV，取实值即「运行设备真实状态」 |
| layout_id | 校验通过后的 `fw_header.layout_id` 实值 | 同上（== BOOT_FW_LAYOUT_ID） |
| boot_ver | `BOOT_VERSION` 常量（boot_fw_header.h:16） | 派工书「Boot 常量」为输入；fw_header 只有 min_boot_ver（下界），Boot 版本本身无运行时可读寄存器，编译期常量是唯一来源；validate 已确保 min_boot_ver ≤ BOOT_VERSION |
| cur_vcode | 校验通过后的 `fw_header.version_code` | §3.2「镜像真伪始终以 fw_header SHA 为准」；BCB.cur_vcode 可能 stale（J-Link 直刷场景），不得作为身份来源 |
| image_sha256 | 全镜像 [0, image_len) 原始字节 SHA-256（raw 域，32B） | OTA-XC-IMAGE-IDENTITY：跨系统镜像身份固定为最终 app.bin 的全部 image_len 字节原始 SHA-256；与 fw_header.image_sha256 双零域严格分离 |
| proto_ver / max_window_segs | session 层冻结常量 1 / 32 | P3-1 已实现（frame.h:51-52），本卡不动 |

## 3. 摘要域分离（本卡最大坑，测试逐字节锁死）

以 golden fixture `tests/ota-vectors/toy-old.bin`（4096B, vcode=20700）为例
（tests/ota-vectors/expected.json）：

- raw SHA-256（INFO.image_sha256 用）= `3081fa0a fc5bb2f3 ...`（= 整个文件字节的
  SHA-256，因为 image_len=4096=文件大小）→ 前 8B `3081fa0afc5bb2f3` 供
  `.etu base_sha8` 与设备 raw SHA8 比较（ota_sd.c:331-333 已实现）。
- fw_header 双零摘要（header-integrity 域）= `e025e068 3ea00f5c ...`
  （fw_header.image_sha256 字段存储值）→ 前 8B 供 ETSL.sha8 /
  candidateImageSha8（ota_slot_header/ota_backup 已实现）。
- 两域不等；禁止互换、禁止「两个都接受」。

## 4. BCB 仲裁在 INFO 链中的语义（决策记录）

派工书：「fw_header CRC/SHA、BCB 仲裁或镜像读失败时 fail closed」+
「BCB 两副本仲裁、无效 BCB、版本不一致的明确行为」+「禁止从 stale BCB 返回身份」。

裁定（与 §3.2 冻结规则「双块均坏且 fw_header 有效 → 直接引导；镜像真伪始终以
fw_header SHA 为准」对齐）：

| BCB 仲裁结果 | INFO 行为 | 理由 |
|---|---|---|
| A / B（至少一块合法） | 正常返回身份 | 身份来源是 fw_header，不是 BCB；BCB.cur_vcode 与 fw_header.version_code 不一致时**以 fw_header 为准**（J-Link 直刷后 BCB 必然 stale；升级资格由 BEGIN 的 bcb_confirmed 门槛管，GET_INFO 不重复该门槛） |
| NONE（双块无效） | 正常返回身份 | §3.2：fw_header 有效即可直接引导，设备在跑、身份可信；「无法可信读取当前镜像」不成立（镜像读取可信度由 fw_header 校验保证，与 EEPROM 无关） |
| ERROR（HAL 读写失败） | **fail closed**（provider 返回 0，无 INFO） | 派工书明文「BCB 仲裁……失败时 fail closed」；EEPROM IO 故障属底层异常，宁可无应答也不发不可验证身份 |

每次 GET_INFO 都重新执行仲裁（轻量，EEPROM 读 128B）；fw_header 校验 + raw SHA
计算较重（约百毫秒），快照缓存复用——运行期 App 无法改写自身 Flash，快照物理
不变；重启后 RAM 清零天然失效（满足「升级重启后旧缓存必失效」）。

## 5. 实现方案

新增 `Libraries/OTA/ota_device_info.{c,h}`（派工书允许条目「职责单一的 image
identity helper」，复用价值：get_device 与 info_provider 双消费点同源）：

- `ota_device_info_t`：model[8]/hw_rev(u16)/layout_id/boot_ver/cur_vcode/
  image_sha256[32]（即派工书的 OtaDeviceInfo 值对象）。
- `ota_device_identity_t`：调用方拥有的快照状态（valid 标志 + info +
  fw_header_result/bcb_result 诊断字段）。
- `int ota_device_identity_get(state, out, image_reader, bcb_hal)`：
  ① 参数检查 ② 快照无效时 fw_header 完整校验（boot_fw_header_validate，
  含向量范围）→ raw SHA-256（256B 块增量）→ 填字段（fw_header 实值 +
  BOOT_VERSION + 冻结 model；hw_rev 超 u16 wire 范围 fail closed）
  ③ 每次调用 BCB 仲裁（ERROR → fail closed）④ 成功才复制到 *out。
  纯只读，无任何写路径。
- 依赖注入：`boot_image_reader_t`（镜像读）+ `bcb_hal_t`（EEPROM 读），
  与 boot_fw_header/eeprom_bcb 既有抽象一致，host 测试注入内存 stub。

HAL_Bluetooth.cpp 接线替换：`s_ble_device/s_ble_image_sha256/s_ble_device_ready`
→ 单一 `s_ble_identity`；`ble_env_info_provider`/`ble_env_get_device` 都从
`ota_device_identity_get` 取数（get_device 的 base_image_sha8 = raw SHA 前 8B，
与 .etu base_sha8 同域）。BCB hal 复用 `HAL::OTA_GetBcbHal()`。

工程接线（P3-1 先例 a305f66）：cmake-generated/CMakeLists.txt 的
APP_PROJECT_SOURCES APPEND 列表 + proj.uvprojx OTA 组。模拟器不接
（模拟器 HAL 是独立副本，不编 USER/HAL/HAL_Bluetooth.cpp；OtaUpdate.cpp 不动
则模拟器零影响）。

## 6. 真机取证方案（不改产品源、全自动）

J-Link GDB inferior call（P2-6 已验证 BCB 只读 inferior call 可行）：

1. 烧录 AC5 产物（真机流程基线），GDB attach。
2. 逐字节 `call ota_ble_session_feed_idle(&s_ble_session, 0, 0, <b>)` 喂入
   完整 GET_INFO 帧（10B：`A5 5A 00 00 <seq LE> 00 00 00 00 <crc LE>`）——
   走生产代码全路径 demux→session→info_provider→fw_header 校验→raw SHA→
   BCB 仲裁→session_send_info→`BT_SERIAL.write`（无连接时字节丢弃，无害）。
3. 读 `s_ble_session.tx_frame[0..59]`（send 后不清零）+ 60B 帧长 = 真实 INFO 帧；
   host 侧 CRC16 校验 + 按 §5.2.1 解码 50B payload，逐字段断言。
4. 同固件 dump App 区 [0x08010000, +image_len) 到文件，host 独立计算 raw
   SHA-256 与 INFO.image_sha256 逐字节比对；fw_header 各字段从同一 dump 摘录。
5. BCB 仲裁结果经 `OTA_GetBcbState()`（或 arbiter 结果字段）读出留证。

比「BLE 无线主机」方案优：无需手机/蓝牙 dongle、不依赖 P3-3/P3-5 的 Flutter
侧资产、路径全自动且逐字节可审计。

## 7. 后续建议（非本卡范围）

- OtaUpdate.cpp::InitializeDevice() 的 SD 路径身份初始化可在后续卡迁移到
  ota_device_info（消除 CurrentImageRawSha8 与新 helper 的重复）；本卡不动
  P2 已验收资产。
- firmware-build.yml 的 host 测试执行步骤接入新测试须另立卡（P3-6/P3-7 的
  治理先例：接线是 Production top_file 变更，本卡只交付测试文件与本地证据）。

## 8. 派工书测试要求 → 测试用例映射

| 派工书要求 | 测试 |
|---|---|
| 有效镜像+有效 BCB 完整正例 | T1：golden toy-old.bin + 合法 BCB，全字段断言（model=E-Track\0、hw=1、layout=1、boot=BOOT_VERSION、vcode=20700、sha=file_sha256） |
| fw_header magic/CRC/SHA、image_len、向量范围、读 IO 负例 | T2-T6：逐项注入缺陷，断言 fail closed + fw_header_result 诊断码 |
| BCB 两副本仲裁、无效 BCB、版本不一致 | T7-T10：A/B 仲裁、单块无效取合法、双块无效照常、cur_vcode 不一致以 fw_header 为准、IO 失败 fail closed |
| model ASCIIZ 边界、协议版本、max window 常量 | T11：model 8B 精确 E-Track\0（无越界）；proto/max_window 由 session 层冻结常量覆盖（P3-1 已有测试），本卡断言 provider 不污染 |
| 摘要与 CI/Tools 同 fixture 逐字节一致 | T1（读 tests/ota-vectors/toy-old.bin 实文件，期望值取 expected.json） |
| raw/header 双摘要域分离 | T12：同一 fixture 断言 raw ≠ header 双零值，前 8B 分别等于 .etu base_sha8 域与 ETSL sha8 域语义 |
| 重复查询无副作用、升级后刷新 | T13：连续两次调用输出一致且 stub 零写操作；快照重置（模拟重启）+ 换镜像 → 新值 |
