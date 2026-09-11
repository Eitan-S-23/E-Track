# P3-3 第九批 设备观测 operations sheet（待批准，**未执行**）

- 日期：2026-09-11　角色：实现 agent（非独立验收）
- 状态：**草稿待批**。本表**未执行**任何设备操作：无烧录、无安装、无 BLE 连接、
  无 logcat 采集、无 RTT。批准前不得按本表操作设备。
- 适用范围：`app/bluetooth_flutter_Trace` OTA 应用层 + AT32F435 目标板上的
  **既有生产固件**。不改 MCU 源码、不改冻结契约、不改历史验收包。
- 本表按 r2 复核第三项（`RC3-07/02: The Observation Plan Remains An Unapproved
  Draft`）的六条要求逐条重写，**不含**「先烧录试一次再补前提」的步骤。

## 0. 结论先行（三条，需裁定）

1. **T1a（应用侧 30s 无 durable 进展）可用现有硬件执行**：真机 + 目标板 +
   J-Link 停机（`h`）即可在真实链路上制造「有连接、无 durable 进展」。
2. **T1b（真实 GATT 写黑洞）需要一台可控外设**：BLE 从机必须能按 FFF0/FFF2/FFF1
   协议应答 INFO/BEGIN ACK 后**停止应答写响应**。现有设备做不到，见 §2.3 决策点 1。
3. **T2（MCU 侧解析器行为）在当前生产固件上不可观测**：BLE OTA 解析层源码
   **零输出调用**，OTА 区域仅有的 RTT 打印在 `P2_x_TEST_ENABLE` 自检宏内
   （生产构型关闭）。按计划自身的规则记 `ENV_BLOCKED`，见 §3 决策点 2。

未获批准前，以上三条的观测一律记 `NOT_RUN`。

## 1. 观测口径（按复核第 1、2 项纠正）

### 1.1 单调时钟（复核第 1 项）

- 冻结契约 `docs/ota-cross-system-contracts.md:1037`（`OTA-XC-BLE-TUNING`）：
  「计时使用单调高精度时钟」。**原草案用 `DateTime.now().microsecondsSinceEpoch`
  作判据时钟，与契约口径冲突**，本表改为：
  - 进程内唯一单调计数器 `final Stopwatch _otaMono = Stopwatch()..start();`
    （模块级），每行日志同时打印 `monoUs` 与 `wallUs`；
  - **判据一律只用 `monoUs` 之差**；`wallUs` 仅用于与 logcat 行、操作时间线对齐，
    不参与任何判据。
- 残余不确定度（明写，不设隐形豁免）：`debugPrint` 的值在调用点构造、不受投递
  延迟影响；`monoUs` 分辨率为微秒级，`wallUs` 为毫秒级；两者差值等于观测窗口内
  的后台停表时长（§1.3）。

### 1.2 无进展锚点（复核第 2 项）

判据窗口的锚点**不是**「某次 BEGIN」也不是「最近一条 durable 日志」，而是产品自身的
预算时钟（`lib/ota/ota_ble_transport.dart`）：

| 事件 | 位置 | 含义 |
| --- | --- | --- |
| 时钟建立 | `:296` `_noProgressClock = Stopwatch()..start()` | transfer 入口；**无任何 durable 进展时锚点即此** |
| 重置 | `:339`、`:436` | **仅** durable 真实前进（BEGIN ACK 带回更大 durable／块尾 ACK 推进） |
| 停表／续走 | `:636`、`:644` | `pauseForBackground()` 停表，`resumeFromBackground()` 续走 |
| 解除 | `:541` | transfer 退出，预算不再约束后续命令 |
| 到期抛错 | `:929-934` | `NO_DURABLE_PROGRESS` |

- **重复的相同 BEGIN／相同 durable 不重置**：`:335` 与 `:433` 都以「严格大于上一次
  durable」为条件，幂等重放不构成进展。
- 判据窗口 = 「锚点 monoUs」→「终止发布 monoUs」，上限仍为 **30s**，不加余量。
- 判据取锚点的方式：`MONO_BUDGET_RESET`（每次 reset 打一行，带当时 durable 值）
  之后到 `MONO_TERMINAL` 之间的差值；若窗口内无 reset，则取 `MONO_BUDGET_START`。

### 1.3 后台暂停（原草案未覆盖的真实干扰）

`pauseForBackground()` 会**停表**，因此墙钟差可合法超过 30s 而预算未超。故：

- 观测期间**保持应用前台**（脚本不切换任务、不锁屏）；logcat 中若出现
  `MONO_PAUSE`，该轮判据记 `HARNESS_FAIL`（场景违规），**不得**当作产品失败，
  也不得用墙钟差值硬判。

### 1.4 插桩（dev 分支 + dev APK，不改语义）

只加观测输出，不参与任何判据计算、不改协议、不改 MCU。各打印一行
`OTA_MONO <event> monoUs=<n> wallUs=<n> [code=<..>] [durable=<n>/<total>]`：

| event | 位置 |
| --- | --- |
| `MONO_BUDGET_START` | `ota_ble_transport.dart:296` 之后 |
| `MONO_BUDGET_RESET` | `:339`、`:436` 之后 |
| `MONO_PAUSE` / `MONO_RESUME` | `:636` / `:644` 之后 |
| `MONO_FAIL_AT` | `:929-934`（`NO_DURABLE_PROGRESS`）与 `_writeFrameLocked` 超时分支抛错前 |
| `MONO_TERMINAL` | `ota_service.dart` 终止发布处（`failClosed` 与失败分支） |

插桩属于执行合同 §7.3.2 的既有授权（dev 分支 WIP 提交 + dev debug APK），
**设备操作不属于**。插桩提交需先跑一次 `flutter-dev-checks.yml` 且绿。

## 2. T1：应用侧预算闭合

### 2.1 T1a —— 真实链路「无 durable 进展」（可执行）

- 拓扑：真机（dev debug APK）+ 目标板（生产固件）+ J-Link（沿用 `AGENTS.md`
  既有烧录/RTT 闭环；本场景**不采集 RTT**，只用 J-Link 停机/复位）。
- 步骤：装 dev APK → 连接并开始一次真实 OTA → 在 DATA 流期间 J-Link `h` 停机
  → 观察应用侧终止；随后 `g` 恢复、断连、清理。
- 判据 A1：`MONO_TERMINAL` − 最近一次 `MONO_BUDGET_RESET`（无则
  `MONO_BUDGET_START`）**< 30s**；错误码为 `NO_DURABLE_PROGRESS`。
- **不预设现象**：停机后若观察到其它终止原因（例如写超时先行触发），如实记录
  实际 `code` 与时刻，并据此分类；不得为了对上 A1 而改用墙钟或放宽阈值。
- 风险：无 UART 硬件流控（`AGENTS.md` 明令 RTS/CTS 接地）时，BT 模块可能在
  缓冲溢出后静默丢字节而非阻塞——那正是 A1 要观测的路径；若模块反而阻塞了
  GATT 写，则同时得到 T1b 的现象（§2.2），按实际观测归类。

### 2.2 T1b —— 真实 GATT 写黑洞（需决策点 1）

- 判据 B1：写响应停摆后，`MONO_TERMINAL` − 锚点 < 30s，且终止前出现
  `WRITE_TIMEOUT`（`_writeFrameLocked` 超时分支）与 `_capByBudget` 封顶后的
  settle 等待；B2：此后一切业务写被拒、隔离不因迟到字节解除。
- **写模式必须绑定**（复核第 3 项）：外设须把 FFF2 广播为 **write-with-response**
  （应用侧优先选有响应写：`bluetooth_service.dart:2173-2187`；仅当只支持无响应写
  才降级）。仿真外设若只支持无响应写，判据 B1 的前提不成立，该轮记 `ENV_BLOCKED`。
- 故障激活点：外设必须**先**完成协议应答（对 GET_INFO 回合法 INFO；对 BEGIN 回
  合法 BEGIN ACK；对 DATA 回 ACK），在应用进入 DATA 稳定态后再**停止应答**，
  不得一开始就不应答。
- 到达目标分支的最小序列（外设按 `docs/ota-binary-contracts.md` §5 实现）：
  1. 广播 FFF0；FFF1 notify、FFF2 write-with-response；
  2. 应答 GET_INFO（`session=0`，seq 回显）→ INFO 含设备身份、`proto_ver`、
     `maxWindowSegments`；
  3. 应答 BEGIN → BEGIN ACK（session/durable_off/bitmap 合法且单调）；
  4. 应答若干 DATA ACK 使 durable 真实前进（至少一次 `MONO_BUDGET_RESET`）；
  5. **停止应答**后续写（不 ACK、不断连），注入点时序记入笔记。
- 前置可行性检查（只读，执行时先做）：确认承载外设的主机确有可用 BLE 适配器、
  且系统 GATT server（WinRT `GattServiceProvider`）可用；不可用则该通道记
  `ENV_BLOCKED` 并转决策点 1 的其它选项。

### 2.3 决策点 1（需用户裁定）

| 选项 | 内容 | 代价 |
| --- | --- | --- |
| A | 在现有 PC 上用 Python（`bless`，WinRT GATT server）实现协议仿真外设 | 需编写仿真脚本；依赖 PC 蓝牙与外设角色可用（§2.2 前置检查） |
| B | 用第二块开发板（nRF52/ESP32）写仿真外设固件 | 需固件开发 + 烧录；硬件需确认在手 |
| C | 第二台 Android 手机跑可编程 GATT server | 需能动态计算 ACK；现成工具能力有限，可行性未证实 |
| D | 不执行 T1b，保持模型级证据 | 真实 native 写时序与「native 是否真取消物理写」**永远无实测** |

**建议 A**：不新增硬件、协议逻辑可复算、注入点=停止应答一行代码；但必须先通过
§2.2 前置检查（若 PC 不支持外设角色即退 D 或 B）。

## 3. T2：MCU 侧帧边界（复核第 4 项）—— `ENV_BLOCKED`

源码核查（只读，无烧录）：

- `Libraries/OTA/ota_ble_frame.c`（411 行）、`ota_ble_ring.c`（82 行）、
  `ota_ble_session.c`（877 行）：`SEGGER_RTT` / `printf` / `DEBUG_SERIAL`
  **各 0 处**——解析器与状态机没有任何输出。
- OTA 区域仅有的 RTT 在 `USER/HAL/HAL_OTA_Staging.cpp:212/348` 与
  `USER/HAL/HAL_OTA_Package.cpp:221/1023/1365`，全部位于
  `#if defined(P2_1_TEST_ENABLE)` / `P2_2_TEST_ENABLE` / `P2_3_TEST_ENABLE` /
  `P2_6_TEST_ENABLE` 自检宏内（`CMakeLists.txt:51-84` 的 `option(...)`），
  生产构型不编译。
- `USER/HAL/HAL_Bluetooth.cpp` 的调试输出全走 `DEBUG_SERIAL`（=`CONFIG_DEBUG_SERIAL`，
  项目规则固定 Serial5 UART）与 `BT_SERIAL`；`JLinkRTTLogger` 采集不到 UART。
- RTT 下行命令集只有 `ping`/`livemap`/`dialplate`/`back`/`gpsreset`
  (`USER/App/App.cpp:70-94`)，**无 OTA 状态查询**，且 `CONFIG_RTT_DEBUG_CMD_ENABLE`
  生产为 0。

**结论**：原草案「MCU 侧 RTT 日志显示悬空帧以 CRC 失败收场」在当前生产固件上
**无法观测**。按草案自身规则记 `ENV_BLOCKED`，**不得**用「RTT 没有错误行」推定
通过，**也不得**为此就地改 MCU。

### 决策点 2（需用户裁定）

- **2a**：另立一个 MCU 插桩任务（在 frame/session 错误分支加少量 `SEGGER_RTT_printf`，
  走标准固件 CI 与后续独立验收），之后 T2 才可执行。属另一组件范围与另一张卡。
- **2b**：接受 T2 永久 `ENV_BLOCKED`，MCU 侧解析器行为只保留模型级/主机侧证据
  （`tests/ota` 中已有的 MCU 语义用例），并在处置表中如实标注。
- 建议 **2b**（本轮）：2a 的价值真实但成本落在另一组件；若后续卡需要 MCU 观测，
  应与其 RTT 需求合并立项，而不是为单条判据改固件。

## 4. 命令、配额与清理（复核第 5 项）

以下命令均落在项目内；`<serial>`、`<run-id>` 在执行时**先解析再替换**，不留下
占位符。

```bat
rem 0) 变量（执行时替换，路径全部为项目内绝对路径）
set RUN=out\acceptance\p3-3-device-obs\<run-id>
mkdir "%RUN%"

rem 1) 安装 dev APK（需另行授权；APK 取自 CI 产物，非本地构建）
adb -s <serial> install -r "%RUN%\trace-dev-debug.apk"

rem 2) 有界 logcat（旋转上限 4 × 8192KB；每轮记录 PID，到点按 PID 结束该进程）
adb -s <serial> logcat -c
adb -s <serial> logcat -v threadtime -s flutter -f "%RUN%\logcat.txt" -r 8192 -n 4
rem    另开窗口执行 OTA；观测结束按记录的 PID 停止上面的 logcat 进程

rem 3) 拉取应用侧证据（applicationId 取自 android/app/build.gradle:74）
adb -s <serial> shell run-as com.wen.gaia.gaia ls -l files\ota
```

- J-Link 停机/复位/RTT 一律沿用 `AGENTS.md` 既有闭环命令（`h`、`g`、`r`、
  SWD 1000 kHz、设备全名 `AT32F435RGT7`、`Stop-Process -Name JLinkRTTLogger` 清残留）。
- **清理**：每轮结束断连 BLE、停 logcat（记 PID 并确认已退出）、`Stop-Process`
  清 JLink 残留、卸载 dev APK 仅在被单独授权时执行、`%RUN%` 保留原始件不删。
- **配额**：每项判据 1 轮 = 1 次前台会话；失败分类后按最小范围复测，全套重跑
  不计入下一轮。**本次批准的总额度：3 轮**（A1/B1/B2 各 1 轮），超出需再次审批。
  固件：**复用既有生产固件**（不重新烧录）；仅当身份核对不符时才需 1 次烧录，
  该次单独计入配额。
- **不得**伪装成免费的步骤：烧录会 halt MCU 并可能打断 SDIO 传输；安装/卸载
  会改变设备状态；这些都要在报告里显式记账，不作为「预检」。

## 5. 探针预算 20×800ms 与 `maxRetries=5` 的关系（复核第 6 项）

- 契约原文：`docs/ota-cross-system-contracts.md:1088`
  「BLE `maxRetries=5`，发送 timeout 由 `OTA-XC-BLE-TUNING` 的 P99 公式得出；
  30 秒无 durable 进展必须中止」。
- 两者**不是同一个界、不是同一失败语义**：
  - `maxRetries=5`（`ota_ble_transport.dart:79`，冻结契约值）：界定 **INFO 载荷损坏**
    时的有界重发（`:226` `attempts > retries`）——这是「有信号但不可用」的循环。
  - `maxResyncProbes=20` × `resyncProbeTimeout=800ms`（`:1127`/`:1121`，
    `probeBudget` 见 `:134`）：界定 **写通道废弃期的盲目重同步探针**——这是
    「无信号、需投递字节逼解析器复位」的循环，其开销含等待在途旧写结算。
  - 调用方 `timeout` 只描述「一次往返」，预算取 `max(timeout, probeBudget)`（`:135`）。
- `20` 与 `800ms` **不是冻结契约值**，是实现内部的有界基线（与 `writeTimeout=10s`
  同属 `P3-4` 待实测的实验基线，见 `docs/ota-prompts/prompt-P3-1-implementation.md:28`）。
  本表**不**把 20 机械改成 5，也**不**申请改契约。

### 决策点 3（需用户裁定）

确认 `maxResyncProbes=20 / 800ms` 作为**观测计划的内部前提**（非契约门槛、
不作为性能判据）；若认为该值需成为合同项，应走契约变更流程另行裁定。

## 6. 批准清单

- [ ] 决策点 1：T1b 通道选型（A 建议 / B / C / D）
- [ ] 决策点 2：T2 的 2a（另立 MCU 插桩卡）或 2b（接受 `ENV_BLOCKED`，建议）
- [ ] 决策点 3：确认 20×800ms 为计划内部前提
- [ ] 授权 T1a 执行（真机安装 dev APK + BLE + J-Link 停机），配额 3 轮
- [ ] 授权 §1.4 插桩提交与一次 dev CI 绿跑（属既有 §7.3.2 授权，此为确认）

未获勾选前：本表整体 `NOT_RUN`，设备一律不动。
