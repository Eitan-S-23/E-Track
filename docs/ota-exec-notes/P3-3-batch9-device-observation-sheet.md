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
| T1b / B1-M 最小机制验证（广播 + 连接 + 三策略注错） | **已授权**（判据见 §7，三种策略各一次） |
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
| 时钟建立 | `:297` | transfer 入口；无任何 durable 进展时锚点即此 |
| 重置 | `:341`、`:439` | **仅** durable 真实前进（严格大于上一次） |
| 停表／续走 | `:646`、`:655` | `pauseForBackground()` / `resumeFromBackground()` |
| 解除 | `:545` | transfer 退出 |
| 到期抛错 | `:948-953` | `NO_DURABLE_PROGRESS`（`_checkNoProgress`） |

- 重复的相同 BEGIN／相同 durable **不重置**（`:341`、`:439` 均为严格大于比较）。
- **判据窗口 = `monoUs(MONO_BUDGET_RESET 或 MONO_BUDGET_START)` →
  `monoUs(MONO_FAIL_AT)`；上限 30s，不加余量**（冻结合同
  `ota-cross-system-contracts.md:1033/1088` 的「30 秒无 durable 进展必须中止」
  约束的是**中止决定**，预算时钟恰好封顶到决定点）。
- `MONO_FAIL_AT` **不是**「业务写已停」的时刻（RC3-07/02）：发送循环的下一次
  `_checkUsable` 要等 service 侧 `abortBestEffort→cancel()` 置 `_cancelled`
  （`MONO_WRITE_STOP`）才拒绝新帧；判据不得用 FAIL_AT 代替 WRITE_STOP。
- **决定→终态发布的收尾时长单列观测、不设门槛**：`monoUs(MONO_TERMINAL) −
  monoUs(MONO_TERMINAL_DECIDED)` 含 ABORT 收尾（取消旁路写仅受
  `writeTimeout=10s` 单分片上限约束，不受 30s 预算约束），把它并入 <30s 判据
  是无来源的表述错误——旧表「`MONO_TERMINAL − 锚点 < 30s`」即错在此处，
  已作废。30s 合同窗口用 FAIL_AT 判；收尾时长如实记录，供后续按实际证据定门槛。
- 窗口内若出现 `MONO_PAUSE`：场景前提不成立，该轮记 `HARNESS_FAIL`，
  **不得**用时钟差硬判，也不得据此改判据口径。

### 1.3 插桩（dev 分支 + dev APK，不改语义）

每行格式：`OTA_MONO <event> monoUs=<n> wallUs=<n> [code=..] [durable=..]`。

| event | 位置 |
| --- | --- |
| `MONO_BUDGET_START` | `ota_ble_transport.dart:298` |
| `MONO_BUDGET_RESET` | `:342`、`:440` |
| `MONO_PAUSE` / `MONO_RESUME` | `:647` / `:656` |
| `MONO_FAIL_AT` | `:950`（NO_DURABLE_PROGRESS）、`:1281`（WRITE_TIMEOUT） |
| `MONO_TERMINAL_DECIDED` | `ota_service.dart` 各终止 catch 决定处（`:1004`、`:1053`、`:1075`、`:1303`） |
| `MONO_WRITE_STOP` | `ota_ble_transport.dart:582`（`cancel()` 置 `_cancelled`＝停止业务写物理边界） |
| `MONO_ABORT_BEGIN` / `MONO_ABORT_DONE` | `ota_service.dart` `abortBestEffort()` 前/后（`:1009/1013`、`:1079/1083`、`:1151/1155`、`:1316/1320`） |
| `MONO_TERMINAL` | `ota_service.dart` 真正终态发布处（`:1016`、`:1054`、`:1086`、`:1240`、`:1322`）——**均在 ABORT 收尾完成之后** |

- 四阶段序列（RC3-07/02）：`MONO_FAIL_AT`/用户取消（中止决定）→
  `MONO_TERMINAL_DECIDED`（service 侧决定）→ `MONO_WRITE_STOP`（业务写停）→
  `MONO_ABORT_BEGIN/DONE`（ABORT 收尾）→ `MONO_TERMINAL`（终态发布）。
  身份异常路径无在途业务写，DECIDED 与 TERMINAL 同点落盘（`:1053-1054`）。
- 插桩提交按执行合同 §7.3.2 走（dev 分支 WIP + dev CI）；**不等**正式合同冻结。
- 记录并交付：插桩 commit、dev CI run URL 与结论、APK 的 SHA-256。

## 2. T1a：A1 开发观测（应用侧 30s 无 durable 进展）

### 2.1 场景与判据

- 拓扑：专用测试手机（dev debug APK）+ 指定 AT32F435 板（既有生产固件）+ J-Link。
- 步骤：装/保持不变覆盖安装 dev APK → 连接 → 前台开始一次真实 OTA → DATA 流期间
  J-Link `h` 停机 → 观察应用侧终止 → `g` 恢复 → 断连 → 停止本次创建的进程。
- 判据 A1：`monoUs(MONO_FAIL_AT) − monoUs(锚点)` **≤ 30s**，错误码
  `NO_DURABLE_PROGRESS`。FAIL_AT 是**中止决定**时刻；30s 合同窗口（
  `ota-cross-system-contracts.md:1033/1088`）约束到决定点为止。决定之后的
  ABORT 收尾（`MONO_TERMINAL_DECIDED → MONO_ABORT_DONE → MONO_TERMINAL`）
  另行记录时间线，**不并入本判据也不另设门槛**（取消旁路写不受 30s 预算
  约束，把它塞进 <30s 没有合同依据——旧表述已作废）。
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
| 1 | BEGIN 无应答重试 | `:850`（`++attempts > retries`，抛 `TIMEOUT`） |
| 2 | 块级 resume（ABORT+BEGIN）预算 | `:301` `resumeLeft = retries`；消费点 `:362`、`:427`、`:454`、`:502`；`:747` `resumeLeft <= 0` 判据 |
| 3 | 单段 DATA 重传上限 | `:416` `view.sendCountOf(seg) > retries` → `overLimit` |
| 4 | END 帧重试 | `:529` `++endAttempts > retries` |
| 5 | INFO 载荷损坏重发 | `:227` `++attempts > retries` |

### 5.2 与同步探针的计数边界

- 探针计数器 `probes` 只属于 `getDeviceInfo` 的**废弃态重同步循环**（`:193`、`:216`，
  界 `maxResyncProbes=20`，`ota_ble_transport.dart:1146`）；探针用 `_nextQuerySeq` 取号，
  **不消耗会话 seq 空间**（`:96-104`）；单次探针上限 `resyncProbeTimeout=800ms`（`:1140`）。
- 业务重发用会话 seq 与 `retries` 计数。**两类计数器互不抵扣**：探针失败不计入
  `retries`，业务重传也不计入 20 次探针。
- 探针预算 `probeBudget = 800ms × 20 = 16s`（`:135`），预算取
  `max(调用方 timeout, probeBudget)`（`:136`）；等待在途旧写结算计入同一预算。

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
| **B1-M（T1b 机制）** | **3（每策略 1 次写）** | **0** | **3** | 仅判机制、不判协议；**不占用也不重置** A1 额度 |
| B1（T1b 完整协议仿真） | 0（未授权） | 0 | — | 只在 B1-M 第 3 策略成立后才申请 |
| B2（T1b） | 0（未授权） | 0 | — | 同上 |

## 7. T1b / B1-M 最小机制验证（**已获授权**；判据先固定，再执行）

授权口径（用户 2026-09-11）：批准广播、连接与三种策略的最小验证，范围**仅限**已核对的
PC 蓝牙适配器与本项目专用测试手机；新增额度为三种策略**各一次**实际写观测，单独记为
**B1-M**，不冒充完整 T1b/B1 产品观测，**不占用、不重置** §6.4 的 T1a 额度；**不包括**
完整 OTA 协议仿真、MCU 操作或 J-Link 操作。

### 7.1 判据参数（执行前固定，**不得事后调整**）

依据产品自身计时配置（`lib/ota/ota_ble_transport.dart`）：`ackTimeout=2000ms`（`:78`）、
`noProgressTimeout=30s`（`:82`）、`writeTimeout=10s`（`:84`）；中央端库
`flutter_blue_plus 1.35.5` 的写自身超时 **T_c = 15s**
（`lib/src/bluetooth_characteristic.dart:158` `int timeout = 15`；成功路径必须等到
`onCharacteristicWritten`）。

| 参数 | 固定值 | 依据 |
| --- | --- | --- |
| 延迟应答延迟 **N** | **3s** | 落在产品 `ackTimeout=2s` 之外、`writeTimeout=10s` 之内，三段可区分 |
| 不应答观察窗 **H** | **20s** | 必须覆盖产品写超时 `10s`；且 H ≥ T_c=15s，才能同时观察客户端自身超时 |
| 客户端自身超时 **T_c** | **15s** | 中央端库默认值，本次**不修改** |
| 单策略时限 | **≤ 5 分钟** | 含广播、连接、写入、注错、收尾 |
| 三策略合计 | **≤ 20 分钟** | 同上 |

- H 按本次**实际配置**核实（产品 10s / 客户端 15s），故取 20s；执行中不得为让结果好看
  而放大或缩小。
- 「不返回」必须是**有界观察**：只要求 H 内没有 native 写完成回调，不要求永远没有回调。

### 7.2 判定规则（中央侧 native 事件为准）

| 策略 | 期望 | 判据 |
| --- | --- | --- |
| 立即应答 | 正常完成 | 收到 native 写完成事件（logcat TAG `[FBP-Android]` 的 `onCharacteristicWrite`）且成功 |
| 延迟应答 N=3s | 体现对应延迟后完成 | 完成时刻相对发起时刻 ≈ N，且成功 |
| 不应答 | H 内无完成回调、连接仍有效 | H 内**无** native 写完成事件；同期连接态仍为已连接 |

- **禁止替代物**：不得用「写请求已提交」「UI 卡住」「Dart Future 未完成」代替 native 完成事件。
- Windows 后续超时或断连**不自动意味着** A 不可行——要看此前是否已提供足够长的受控无响应窗口。
- 仅看到超时**也不能**判 A 成立——必须排除客户端、事件循环或采集器自身卡住
  （PC 侧心跳与中央侧 logcat 双端时间线互证）。
- 本实验**不能**自动证明「物理写已取消」；只能区分「未观察到写完成」「未收到 ATT 响应」两类。
- 不同设备的单调时间**不可直接相减**；只与各自设备内的事件序列比较。

### 7.3 工具现状（本轮实测；含一处**方法变更**）

- **bless 在本机不可用（两个版本都不行）**：
  - `bless==0.3.0` 装不上（钉死已不在 PyPI 的 `winrt-Windows.Devices.Bluetooth==2.0.0b1`）；
  - `bless==0.2.6` 装得上但**导不进来**：`backends/winrt/{server,service,characteristic}.py`
    **无条件** `import bleak_winrt.*`（三处，无 `sys.version_info` 分支），且 `service.py`
    依赖的 `bleak.backends.winrt.service` 已被 `bleak>=1.0` 移除（实测 `bleak==3.0.2` 无此模块）；
    补齐需源码编译只有 sdist 的 `bleak-winrt==1.2.0`，并把两代 WinRT 投影
    （pywinrt 1.x 与 winrt-runtime 3.2.1）混进同一进程——不作此变通。
  - 因此**废止**原「bless 包装 + 撤销其处理器」路线（能力报告原 A1），改用已安装的
    `winrt-*==3.2.1` **直连**建 GATT server：这正是 bless 所包装的同一 API 面，
    且**不引入**自研协议栈（仅单特征机制验证）。方法变更的证据见能力报告 §2.5。
- harness：`docs/ota-exec-notes/tools/p3-3-b1m/b1m_peripheral.py`（约 300 行，单文件）。
  `docs/ota-exec-notes/**` **不属**任何验收 profile，不进入 Production/Validation/Governance。
- 本机 API 冒烟（**不广播、不连接、不写**，`--setup-only`）已通过：
  `GattServiceProvider.create_async` `error=0`、`create_characteristic_async` `error=0`、
  写处理器注册成功 → 本机可在**非打包** Python 进程内创建 GATT 服务提供者。
- **必须由中央侧定性的未决项**：本机 `GattLocalCharacteristic.characteristic_properties`
  回读**系统性丢失 WRITE 位**——请求 `READ|WRITE(10)` 回读 2、`WRITE(8)` 回读 0、
  `READ|WRITE|NOTIFY(26)` 回读 18；已排除赋值形式（枚举 / int）、写处理器注册前后、
  `static_value` 与权限级别（权限级别能正确回读），**广播启动后仍为 0**。可能是本机属性
  getter 的投影问题，也可能真的意味着特征对中央不可写——**只有中央侧发现结果能定性**。
  若中央发现结果不含 `write` → A 路径在**发现阶段**即受阻，按 §7.6 止损。
- **本机环回不可行**：Windows 对本地适配器自过滤，同机 `bleak` 扫描（12s / 8s 两次，
  共 8–9 个外部设备）未发现本机广播，故 PC **不能**充当中央端；中央侧判据必须由手机提供。
- `stop_advertising()` 后回读 `advertisement_status` 在 1s 内仍为 2 且无状态变更事件；
  停止后的等待已放宽到 3s，**不以该读数**声称「已停止」——只有「调用过 stop 且进程退出」
  是确定事实。
- 准备记录（逐条命令与原始日志路径）：`docs/ota-exec-notes/P3-3-b1m-prep-2026-09-11.md`。

### 7.4 执行前必须记录（缺一不执行）

1. PC 适配器身份（`.cache/p3-3-t1b/capcheck.py` 的 `device_id` / `bluetooth_address`）。
2. 中央端设备身份（手机序列号）与客户端版本（APK 提交 + SHA-256）。
3. 特征 UUID 与**实际写模式**：harness 只声明 `WRITE(8)`；实测到达的 `request.option`
   必须为 `WRITE_WITH_RESPONSE`（harness 逐条记录），否则该次作废并说明。
4. 输出目录：`.cache/p3-3-t1b/runs/b1m-<strategy>-<run-id>/`（项目内，先建后写）。

### 7.5 收尾（受控，不得擅自动系统状态）

- 到实验截止：释放全部挂起请求（受控 `respond()` + `complete()`）→ 取消延迟任务 →
  停广播 → 只结束**本次记录的**进程。
- 不擅自重置系统蓝牙、不清配对、不清应用数据；不全局按名杀进程；不启动未容纳的 PowerShell。
- 沿用项目内输出预检；所有产物落 §7.4 的项目内目录。

### 7.6 止损

- 正常对照（立即应答）失败 → **先停止定位**，不继续注错、不盲目重试。
- 若 Windows 栈在无响应时自动应答或断开 → A 路径不可行，报**具体 API 限制**后比较 B/C，
  不写「永远无法实测」。

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
