# P3-2 GET_INFO 设备身份链实施 Spec

task_id: P3-2

## 任务类型

`IMPLEMENTATION`

## Readiness 引用

唯一任务状态见 `PLAN-OTA-EXEC.md` readiness 矩阵的 `P3-2` 行。本文件不得另行维护该状态。

## 目标

实现 MCU 设备身份 provider 和 GET_INFO/INFO 接线，使 wire model、硬件修订、布局、Boot 版本、当前版本码、当前镜像摘要、协议版本和最大窗口全部来自运行设备真实状态，并能被 P3-1 transport 安全查询。

## 非目标

- 不重新定义 INFO 字节布局或扩大 model 字段。
- 不实现 Flutter DTO、latest API 或 BLE 文件传输。
- 不从广播名、UI 常量或 Cloudflare 默认值反向填 MCU 身份。
- 不改变 fw_header、BCB 或 `.etu` 校验算法。

## 前置依赖

- 阶段门槛 `P2-1` staging 与 `P2-2` package path 已收口。
- 当前镜像校验、Boot 常量和 BCB 读取实现已存在；P3-1 的 dispatcher/provider 是接入边界，不新增先于本卡完成的硬依赖。
- 正式 model 映射和镜像摘要域的用户裁定已传播到共享合同；实现只能消费 `OTA-XC-DEVICE-MODEL` 与 `OTA-XC-IMAGE-IDENTITY`，不得再引入临时值、默认值或第二摘要域。

## 权威合同

- `OTA-XC-INFO-MAPPING`
- `OTA-XC-DEVICE-MODEL`
- `OTA-XC-IMAGE-IDENTITY`
- `OTA-XC-FLUTTER-DEVICE-DTO`
- `OTA-XC-SECURITY`
- `docs/ota-binary-contracts.md` §1、§3、§5.2.1

## 现有组件和代码入口

- `USER/App/Utils/OtaUpdate/OtaUpdate.cpp::Session::InitializeDevice()`：当前 hw/layout/boot/current vcode 和 raw SHA8 来源。
- `boot/include/boot_fw_header.h`、`boot/src/boot_fw_header.c`：当前镜像头校验和 Boot/layout 常量。
- `Libraries/EEPROM/eeprom_bcb.h`、`USER/HAL/HAL_EEPROM.cpp`：当前持久化状态、版本事实和 App 侧安全读取封装。
- `USER/App/Version.h`：只可作构建展示，不得覆盖运行镜像/BCB 实值。
- P3-1 新增的 BLE command provider 接口。

## 输入输出与调用方向

- 输入：当前 App Flash、fw_header 校验结果、BCB 仲裁结果、Boot/layout/hardware 常量。
- 输出：内部 `OtaDeviceInfo` 值对象，由 P3-1 encoder 只读消费。
- provider 返回成功前必须验证所有 required 来源；部分有效不得生成 INFO。
- 镜像摘要必须按 `OTA-XC-IMAGE-IDENTITY` 定义的域计算完整 32 字节，禁止只扩展现有 SHA8 缓存而未证明同一摘要域。

## 状态机与生命周期所有者

- identity provider 拥有一次查询的完整快照，不拥有 BLE session。
- BCB/Flash 读取组件仍拥有底层真相；provider 不写 BCB。
- GET_INFO 每次调用重新取得或验证缓存；升级重启后旧缓存必失效。
- 若设备处于无法可信读取当前镜像的状态，返回合同错误，不发送伪造零值。

## 错误、超时、重试、取消、恢复与幂等

- GET_INFO 只读且幂等，可在无活跃 OTA session 时有界重试。
- fw_header CRC/SHA、BCB 仲裁或镜像读失败时 fail closed；不得退回 `0.0.0`、全零 SHA 或编译期默认版本。
- `OTA-XC-DEVICE-MODEL` 或 `OTA-XC-IMAGE-IDENTITY` 发生未重新冻结的变更时，只允许编译测试 provider 接口，不得产生正式对外值。
- 查询取消只丢弃本次快照，不改变设备持久化状态。

## 允许修改范围

- `USER/App/Utils/OtaUpdate/`、必要的 `USER/HAL/HAL_OTA_*` 只读 helper。
- P3-1 的 provider 接口接线文件。
- `Libraries/OTA/` 中职责单一的 image identity helper（如确有复用价值）。
- `tests/ota/` 下 host 测试、Flash reader stubs 和工程接线测试。

## 禁止修改与生产红线

- 禁止修改冻结 binary contract、fw_header 布局、BCB 布局或 hash 算法。
- 禁止偏离 `OTA-XC-DEVICE-MODEL` 的唯一映射，或把二进制合同中的示例、默认值和未知名称当作兼容 fallback。
- 禁止同时接受 raw SHA 和双零 SHA 作为“等价”身份。
- 禁止从未校验的 Flash 或 stale BCB 返回身份。
- 禁止为 INFO 查询写 Flash、EEPROM、staging 或改变 OTA state。

## 必须新增或调整的测试

- 有效当前镜像 + 有效 BCB 的完整字段正例。
- fw_header magic/CRC/SHA、image_len、向量范围和读 IO 失败负例。
- BCB 两副本仲裁、无效 BCB、版本不一致的明确行为。
- model ASCIIZ 边界、协议版本和 max window 常量。
- 选定摘要域后，与 CI/Tools 对同一 finalized app fixture 计算 32B 摘要逐字节一致。
- 同一 fixture 同时计算 raw SHA-256、`fw_header.image_sha256` 双零摘要及各自前 8B；断言 `.etu base_sha8` 使用 raw 前 8B，ETSL/`candidateImageSha8` 使用 header 双零摘要前 8B，raw/header 值不等时不得混用。
- GET_INFO 重复查询无副作用，升级后新镜像查询刷新。

## 完成判据

- 真机 INFO 的 hw/layout/boot/vcode 可分别追溯到权威运行值。
- 完整镜像摘要与独立 host/CI 计算一致，且明确不混用另一摘要域。
- P3-1 对合法/非法 provider 结果有确定 ACK/错误行为。
- host 测试、适用固件构建和静态生产符号检查通过。

## 停止条件

- `OTA-XC-DEVICE-MODEL` 或 `OTA-XC-IMAGE-IDENTITY` 发生未重新冻结的变更时停止正式 wire 值实施，不得用临时映射或双摘要兼容绕过。
- 发现冻结 INFO 语义与 patch base 合同无法同时满足时记录冲突，不修改冻结文件。
- 需要信任未校验镜像或改变 BCB 才能返回字段时停止。

## 后续证据

保存同一真机/同一固件的 fw_header 摘录、BCB 仲裁结果、独立镜像摘要、INFO 解码结果、构建产物 hash 和所有负例日志。敏感 Flash 全量不得无必要进入公开日志。

## Luna 可自行决定

provider 的内部类型、缓存策略、reader 抽象、测试 stub 和文件命名，只要每次快照一致、无副作用且可独立验证。

## 阻断性决策

- 无。全部相关决定已由用户批准；执行要求以“权威合同”章节引用的冻结 OTA-XC 条款为准。
