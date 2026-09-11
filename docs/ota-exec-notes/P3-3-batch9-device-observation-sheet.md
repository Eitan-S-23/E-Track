# P3-3 T1a/T1b 设备观测 operations sheet（开发观测；授权范围见 §6）

- 日期：2026-09-11（授权更新）
- 性质：**开发观测**，**不是**正式验收，不豁免任何既有门槛；`formal_acceptance`
  全程 `NOT_RUN`。
- 授权来源：用户 2026-09-11 决定——同意继续获取真实设备数据，按本表范围执行。
- 本表**未执行**任何设备操作：无安装、无烧录、无 BLE 连接、无 logcat 采集、无 RTT。
- 适用范围：`app/bluetooth_flutter_Trace` OTA 应用层 + AT32F435 目标板**既有生产固件**。
  不改 MCU 源码、不改冻结契约、不改历史验收包。

## 0. 授权范围速览（对应 §6 的完整口径）

| 项 | 状态 |
| --- | --- |
| T1b / A 路径探索（项目内 harness + 隔离依赖 + 只读能力检查） | **已完成**（结论见 §7 与能力报告） |
| T1b / B1 最小机制验证（广播 + 连接 + 三策略注错） | **未授权**（方案见 §7，待批） |
| T1a / A1 开发观测（真机 + 目标板 + J-Link h/g） | **已授权 1 次**（前提见 §2.2） |
| T1a / B1、B2 注错观测 | **未授权** |
| T2 MCU 侧 RTT 观测 | **本轮 ENV_BLOCKED**（非永久豁免） |
| 改 MCU 源码 / 烧录插桩固件 | **未授权** |
| 卸载、清应用数据、擦除、重烧、改 WDT/调试寄存器、额外断电 | **未授权** |

未满足 §2.2 前提时，不执行 T1a，只报告具体缺口。

## 1. 观测口径

### 1.1 计时（修正）

- 契约依据：`docs/ota-cross-system-contracts.md:1037`（`OTA-XC-BLE-TUNING`）
  「计时使用单调高精度时钟」。
- **判据只用单调计数器的差值**：进程内唯一 `final Stopwatch _otaMono = Stopwatch()..start();`，
  每行日志打印 `monoUs`；`wallUs`（`DateTime.now()`）只用于与 logcat 行、操作时间线
  对齐，**不参与任何判据**。
- **禁止的算法（原草案错误）**：不得把「墙钟与全局单调时钟的差」解释成后台停表时长——
  预算时钟（`_noProgressClock`）在 transfer 入口才启动，与进程级 `_otaMono` 起点不同，
  两者之差不是停表时长。
- 停表时长只能由成对事件算出：`MONO_PAUSE` 与 `MONO_RESUME` 各自的 `monoUs` 之差。
- 残余不确定度：`debugPrint` 的值在调用点构造（不受投递延迟影响）；`monoUs` 微秒级、
  `wallUs` 毫秒级。

### 1.2 无进展锚点

判据锚点是产品自身的预算时钟（`lib/ota/ota_ble_transport.dart`）：

| 事件 | 位置 | 含义 |
| --- | --- | --- |
| 时钟建立 | `:296` | transfer 入口；无任何 durable 进展时锚点即此 |
| 重置 | `:339`、`:436` | **仅** durable 真实前进（严格大于上一次） |
| 停表／续走 | `:636`、`:644` | `pauseForBackground()` / `resumeFromBackground()` |
| 解除 | `:541` | transfer 退出 |
| 到期抛错 | `:929-934` | `NO_DURABLE_PROGRESS` |

- 重复的相同 BEGIN／相同 durable **不重置**（`:335`、`:433` 均为严格大于比较）。
- 判据窗口 = `monoUs(MONO_BUDGET_RESET 或 MONO_BUDGET_START)` →
  `monoUs(MONO_TERMINAL)`；上限仍是 **30s**，不加余量。
- 窗口内若出现 `MONO_PAUSE`：场景前提不成立，该轮记 `HARNESS_FAIL`，
  **不得**用时钟差硬判，也不得据此改判据口径。

### 1.3 插桩（dev 分支 + dev APK，不改语义）

每行格式：`OTA_MONO <event> monoUs=<n> wallUs=<n> [code=..] [durable=..]`。

| event | 位置 |
| --- | --- |
| `MONO_BUDGET_START` | `ota_ble_transport.dart:296` 之后 |
| `MONO_BUDGET_RESET` | `:339`、`:436` 之后 |
| `MONO_PAUSE` / `MONO_RESUME` | `:636` / `:644` 之后 |
| `MONO_FAIL_AT` | `:929-934`、`_writeFrameLocked` 超时分支抛错前 |
| `MONO_TERMINAL` | `ota_service.dart` 终止发布处（`failClosed` 与失败分支） |

- 插桩提交按执行合同 §7.3.2 走（dev 分支 WIP + dev CI）；**不等**正式合同冻结。
- 记录并交付：插桩 commit、dev CI run URL 与结论、APK 的 SHA-256。

## 2. T1a：A1 开发观测（应用侧 30s 无 durable 进展）

### 2.1 场景与判据

- 拓扑：专用测试手机（dev debug APK）+ 指定 AT32F435 板（既有生产固件）+ J-Link。
- 步骤：装/保持不变覆盖安装 dev APK → 连接 → 前台开始一次真实 OTA → DATA 流期间
  J-Link `h` 停机 → 观察应用侧终止 → `g` 恢复 → 断连 → 停止本次创建的进程。
- 判据 A1：`monoUs(MONO_TERMINAL) − monoUs(锚点)` **< 30s**，错误码
  `NO_DURABLE_PROGRESS`。
- **不预设现象**：若实际终止原因为写超时、断连、复位、应用转后台等，如实记录实际
  `code` 与时间线，并判定场景前提是否成立；**不得**硬填 A1 通过。
- **不越界**：T1a 结果**不得**替代 ATT 写黑洞（T1b/B1）或物理写取消（B2）的证据。

### 2.2 执行前必须补齐并核对（缺一不执行）

1. 手机序列号（`adb devices`，只读）与独占设备窗口（本表执行期间不使用该机做其它事）。
2. J-Link 标识（本机板载调试器）与本次涉及的精确命令。
3. APK：提交 SHA + 文件 SHA-256（来自 dev CI 产物，非本地构建）。
4. 固件身份：板上当前固件的身份核对方式与实测值（**只读**）；不符即停止核实，
   **不触发**任何「例外自动烧录」。
5. OTA 输入包：`.etu` 文件路径与 SHA-256，且来源为**项目内**已存在资产。
6. 输出目录：`.cache/p3-3-t1a-<run-id>/`（项目内，先建后写）。

### 2.3 halt 的影响与有界收尾（执行前必读）

- `h` 会 halt MCU：正在进行的 **SDIO 传输可能被打断**，`g` **不保证**能恢复被打断的
  SD 卡操作（既往现象的恢复手段是拔插 SD 或整机断电——**本次均未授权**）。
- 看门狗与连接状态：halt 期间 BLE 连接可能断开或降级；应用侧可能先收到断连而非
  无进展超时——这属于**提前终止**，按 §2.1 如实记录并判定前提。
- **恢复条件不具备时不要先停机试一次**。停机前先确认：本表的输出目录可写、
  J-Link 命令可回读（`regs` 只读）、操作者可在场完成 `g` 与断连收尾。
- 若 halt 后出现 SD 挂死迹象（`SD_IsReady=0` 等），按既有防坑清单定位，
  且**不得**自行拔插/断电——说明准确动作后单独申请。

### 2.4 记录与配额

- 保留历史配额、失败与尝试记录，**不因换方案或换会话清零**（累计表见 §6.4）。
- 失败先留证定位，不盲目重试；同一动作不重复请示，超出配额后需再次申请。

## 3. T2：MCU 侧解析器观测 —— 本轮 `ENV_BLOCKED`

源码核查（只读）：

- `Libraries/OTA/ota_ble_frame.c`(411 行)、`ota_ble_ring.c`(82 行)、
  `ota_ble_session.c`(877 行)：`SEGGER_RTT`/`printf`/`DEBUG_SERIAL` **各 0 处**。
- OTA 区域仅有的 RTT 在 `USER/HAL/HAL_OTA_Staging.cpp:212/348` 与
  `USER/HAL/HAL_OTA_Package.cpp:221/1023/1365`，全部位于
  `P2_1/P2_2/P2_3/P2_6_TEST_ENABLE` 自检宏内（生产构型不编译）。
- `USER/HAL/HAL_Bluetooth.cpp` 输出全走 `DEBUG_SERIAL`（固定 Serial5 UART，RTT logger 采集不到）
  与 `BT_SERIAL`；RTT 下行命令只有 `ping/livemap/dialplate/back/gpsreset`
  （`USER/App/App.cpp:70-94`），无 OTA 状态查询，且 `CONFIG_RTT_DEBUG_CMD_ENABLE` 生产为 0。

**口径**：

- 记录「现有生产固件缺少本判据所需的观测通道」，其运行验证保持 `NOT_RUN`；
  模型级/主机侧证据继续保留。
- **缺少 RTT 输出 ≠ 解析器行为已通过**；也**≠** 所有其它观测方式均不可行。
- 本轮**不授权**改 MCU、不授权为此烧录插桩固件；后续是否采用替代证据或另立
  MCU 插桩任务，按实际合同判据另定。
- `OTA-DEC-013` 已保留的 P3-3 真机要求**不因此降低或迁移**。

## 4. 命令与进程边界（按授权修正）

项目内路径统一前缀：`<RUN> = .cache/p3-3-t1a-<run-id>`。

```bat
rem 0) 输出目录（项目内；先建）
mkdir .cache\p3-3-t1a-<run-id>

rem 1) 只读身份核对：手机 / 设备 / APK / 固件 / 输入包
adb devices -l
adb -s <serial> shell getprop ro.product.model
certutil -hashfile "<RUN>\trace-dev-debug.apk" SHA256
rem 固件身份与 .etu 哈希按 §2.2 的第 4、5 项逐项记录

rem 2) 安装（保持不变覆盖安装；不卸载、不清数据）
adb -s <serial> install -r "<RUN>\trace-dev-debug.apk"

rem 3) 主机侧日志采集（受控）：stdout 重定向到主机文件，不用 -f（-f 写的是设备端路径），
rem    不清设备既有日志（不执行 logcat -c）；记录并保持 PID，到点按 PID 结束
start "" /b adb -s <serial> logcat -v threadtime -s flutter > "<RUN>\logcat.txt" 2>&1
rem    另开窗口执行 OTA 与 J-Link h/g；到时用记录的 PID 结束上面的 adb 进程

rem 4) 收尾：断连、停止本次创建的进程、复核输出文件
adb -s <serial> shell dumpsys bluetooth_manager | findstr /i "state"
```

- **不启动未容纳的 PowerShell**；不按进程名全局结束 J-Link / RTT logger；
  只管理本次记录在案的 PID（含本表创建的 `adb` 与 J-Link 进程）。
- 日志有界：主机侧文件由采集窗口限时（本表限 **每轮 ≤ 15 分钟**），到时按 PID 停止；
  不写无界流。
- **不得**伪装成免费的步骤：halt 可能打断 SDIO；安装会改变设备状态——都要在报告里
  显式记账，不作为「预检」。

## 5. 探针与业务重发的计数边界（纠正与澄清）

### 5.1 纠正（原表述错误）

原表称「`maxRetries=5` 界定 INFO 载荷损坏时的有界重发」——**该说法不完整，已作废**。
`retries`（`ota_ble_transport.dart:86`，默认 `maxRetries=5`）在源码中界定**五个**循环：

| # | 循环 | 位置 |
| --- | --- | --- |
| 1 | BEGIN 无应答重试 | `:838`（`++attempts > retries`，`:839` 抛 `TIMEOUT`） |
| 2 | 块级 resume（ABORT+BEGIN）预算 | `:299` `resumeLeft = retries`；消费点 `:359`、`:424`、`:450`、`:498`；`:735` `resumeLeft <= 0` 判据 |
| 3 | 单段 DATA 重传上限 | `:413` `view.sendCountOf(seg) > retries` → `overLimit` |
| 4 | END 帧重试 | `:525` `++endAttempts > retries` |
| 5 | INFO 载荷损坏重发 | `:226` `++attempts > retries` |

### 5.2 与同步探针的计数边界

- 探针计数器 `probes` 只属于 `getDeviceInfo` 的**废弃态重同步循环**（`:192`、`:215`，
  界 `maxResyncProbes=20`，`ota_ble_transport.dart:1127`）；探针用 `_nextQuerySeq` 取号，
  **不消耗会话 seq 空间**（`:159-160`）；单次探针上限 `resyncProbeTimeout=800ms`（`:1121`）。
- 业务重发用会话 seq 与 `retries` 计数。**两类计数器互不抵扣**：探针失败不计入
  `retries`，业务重传也不计入 20 次探针。
- 探针预算 `probeBudget = 800ms × 20 = 16s`（`:134`），预算取
  `max(调用方 timeout, probeBudget)`（`:135`）；等待在途旧写结算计入同一预算。

### 5.3 时限口径（不得越界解释）

- `20 × 800ms` 的**乘积本身不构成任何总时限证明**；即便写/结算/应答等待已被
  `_capByBudget` 封顶（`:137-144` 注释所述改动），也**不得**据此声称 30s 无进展上界
  已被证明或被替代。
- 30s 上界（`noProgressTimeout`）仍由 `_noProgressClock` 独立约束；两段不得相加，
  也不得用内部参数绕开。
- 计数边界与端到端截止的**合同符合性仍需独立复核**；本表只把 20×800ms 作为
  **开发观测输入**，不机械改成 5，也不申请改契约。

## 6. 授权状态、边界与配额

### 6.1 已授权

- **T1b / A 路径探索**：在项目根内准备仿真 harness、项目内隔离依赖环境、只读能力检查。
  先**固定 `bless` 版本**，核实其能否控制 **ATT Write Response**，再决定是否开发完整协议仿真。
  审查已指出：`bless` 当前 WinRT 后端在写回调返回后会自动 `request.respond()`；
  **停止 FFF1 的 OTA ACK 通知 ≠ 停止 ATT 写响应**，不能据此声称制造了 native 写黑洞；
  仅「支持外设角色」也不足以证明方案可行。
- **T1a / A1**：按 §2 执行**最多 1 次**实际观测，前提见 §2.2。
- 插桩 APK：按 §7.3.2 提交并取得对应开发 CI 证据，不等正式合同冻结。

### 6.2 未授权（需另行申请）

- T1b 的**实际广播、连接及 B1/B2 注错观测**（不得借 T1a 授权执行）。
- 修改 MCU 源码、烧录插桩固件。
- 卸载、清应用数据、擦除、重新烧录、修改 WDT/调试寄存器、额外断电。
- 固件身份不符时的任何「例外自动烧录」；确需额外恢复动作时，说明准确动作后单独申请。

### 6.3 A 路径的退出条件

- 若 A 不可行：报告**具体的 API 限制**（含 `bless` 版本与源码位置），再比较 B/C；
  不盲目投入，也**不得**把「暂不执行」写成「永远无法实测」。

### 6.4 配额（累计，不因换方案或换会话清零）

| 判据 | 授权轮数 | 已用 | 剩余 | 备注 |
| --- | --- | --- | --- | --- |
| A1（T1a） | 1 | 0 | 1 | 历史失败/尝试记录一并保留 |
| B1（T1b） | 0（未授权） | 0 | — | 待最小操作方案获批 |
| B2（T1b） | 0（未授权） | 0 | — | 同上 |

## 7. T1b / B1 最小操作方案（**待批，未执行**）

能力依据已落盘：`docs/ota-exec-notes/P3-3-t1b-pathA-capability-report.md`。

- **源码结论**：`bless==0.2.6`（本机唯一可安装版本）公开 API **无**写响应控制点——
  回调返回后无条件 `request.respond()`（`bless/backends/winrt/server.py:347-353`；
  0.3.0 `:409-415` 同构），回调返回值被丢弃（`backends/server.py:271`）。
  「停止 FFF1 的 OTA ACK 通知 ≠ 停止 ATT 写响应」经源码确认成立。
- **控制点位置**：WinRT 层存在（`GattWriteRequest.respond` /
  `respond_with_protocol_error` / `option`；`GattLocalCharacteristic.add_/remove_write_requested`），
  经 `BlessServer.get_characteristic(uuid).obj` 可达。
- **只读能力**：本机适配器 `is_peripheral_role_supported=true`（同时 central/LE/offload 为 true）。
  该自述能力**不**证明 Windows GATT server 实际可被 Android 发现。
- **最小机制验证（只判机制、不判协议）**：
  1. 外设侧用 bless 起服务，声明一个 **write-with-response** 特征，由自定义处理器接管
     （撤销 bless 处理器，或子类覆写后再注册——两条路均需实测确认）；
  2. 中央侧（Android 测试机）对该特征发一次有响应写；
  3. 三种策略分别观测：立即 `respond()` / 推迟 N 秒 `respond()` /
     **不 `respond()` 且不 `complete()` deferral**；
  4. 判据：仅第 3 种策略下中央侧写回调**不返回**（并在观测窗内复核连接是否仍在）。
- **本次申请授权**：上述第 1–4 步的**广播、连接与注错观测**（B1）。**不**申请完整
  FFF0/FFF1/FFF2 协议仿真——它只在第 3 种策略成立后才申请。
- **止损**：若 Windows 栈在无响应时自动应答或断开 → A 路径不可行，报**具体 API 限制**
  再比较 B/C，不写「永远无法实测」。
- **未决项**：见能力报告 §7（delegate 同一性、系统超时/断连语义、扣住响应期能否继续
  notify、客户端写模式、bless 每回调新建事件循环的影响）。

## 8. 交付物（开发观测）

- 绑定身份的**原始日志**（logcat 原文，含 `OTA_MONO` 行）、实际时间线、错误码、
  相关命令的**退出码**、输出路径审计。
- 身份绑定项：手机序列号、APK 提交与 SHA-256、固件身份、`.etu` 路径与 SHA-256、
  插桩 commit 与 dev CI run。
- 开发观测结果与正式验收**分开**陈述；正式验收继续保持 `NOT_RUN`。

## 9. 执行前检查清单

- [ ] §2.2 六项核对全部完成并记录
- [ ] 插桩 APK 的 dev CI 为绿，且已记录 commit/run/SHA-256
- [ ] §2.3 的恢复条件具备（可 `g`、可断连、输出目录可写）
- [ ] 本轮配额剩余 ≥ 1（§6.4）
- [ ] 不执行任何 §6.2 未授权动作
