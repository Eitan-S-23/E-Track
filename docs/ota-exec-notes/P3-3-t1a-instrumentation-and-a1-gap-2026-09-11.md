# P3-3 T1a 插桩交付 与 A1 前置核对（含缺口）—— 2026-09-11

> 依据：`docs/ota-exec-notes/P3-3-batch9-device-observation-sheet.md` §1.3、§2、§9。
> 结论：**A1 未执行**——§2.2 前提不成立，按 §0「未满足 §2.2 前提时，不执行 T1a，只报告
> 具体缺口」处理。本报告不冒充观测结果；正式验收保持 `NOT_RUN`；A1 配额 1 次**未消耗**。

## 0. 结论速览

| 项 | 结果 |
| --- | --- |
| T1a 插桩（§1.3） | **已完成**：3 文件 / +38 行，提交 `57e0222` |
| dev CI（插桩提交） | **双宿主绿**：run 34614096727，ubuntu + windows 全部成功 |
| dev debug APK | 已取得；APK 字节内**确证含插桩**、**确证无固件端点** |
| §2.2 第 1/2/3/6 项 | 已核对并记录 |
| §2.2 第 4/5 项 | **未取得**（均依赖可执行场景，见 §4） |
| A1 观测 | **未执行**（缺 §2.2 前提；停机动作未发生） |
| 缺口一 | dev 构建未注入固件服务端点 ⇒ 应用无法发起**检查更新/下载/发起**；**不影响 GET_INFO**（2026-09-12 更正，见 §9.1） |
| 缺口二 | 完整身份字段（镜像 SHA/硬件版本/layout/boot/protocol/窗口）**无观测出口**（见 §9.3） |
| 载体 | dev debug APK 因**签名冲突**无法装入测试手机，身份读取未开始；已停止且无副作用（见 §9.2） |

## 1. 插桩交付（§1.3）

提交 `57e0222079fb2c31b1fdb50137f5a88e5f5ec0fb`（分支 `dev/flutter/apk/p3-3-t1a`，
身份 `Eitan-S-23`），`git show --stat`：

| 文件 | 变更 | 承载事件 |
| --- | --- | --- |
| `lib/ota/ota_mono.dart` | +25（新文件） | 进程级唯一 `Stopwatch` + `otaMonoLog()` |
| `lib/ota/ota_ble_transport.dart` | +8 | `MONO_BUDGET_START`、`MONO_BUDGET_RESET`×2、`MONO_PAUSE`、`MONO_RESUME`、`MONO_FAIL_AT`×2 |
| `lib/services/ota_service.dart` | +5 | `MONO_TERMINAL`×4（传输失败 / 身份异常 / 通用 catch / `failClosed`） |

行格式与 §1.3 一致：`OTA_MONO <event> monoUs=<n> wallUs=<n> [code=..] [durable=..]`；
值在调用点构造（`debugPrint` 投递延迟不影响数值）；只读时钟、不改变任何控制流。
判据只用**同类事件**的 `monoUs` 差值；`wallUs` 仅用于与 logcat / 操作时间线对齐。

## 2. dev CI 证据

- 运行：`https://github.com/Eitan-S-23/E-Track/actions/runs/34614096727`（headSha = `57e0222`）
- 双宿主结论：`development_result=PASS`、`error=None`（ubuntu 与 windows 均成功）
- 测试计数：ubuntu `+289 ~7: All tests passed!` / windows `+296: All tests passed!`
- APK 任务：`apk_result=PASS`（ubuntu）；windows `NOT_REQUESTED`（APK 仅 Linux 构建）
- 两宿主 `source_unchanged=False`、`source_deltas_bound_toolchain_regen=True`
  ——即 `docs/flutter-development-validation.md` 记录的开发运行器工具链重生成路径，
  与 `development_result=PASS` 一并成立，非失败态。
- 产物 `flutter-dev-debug-apk-57e0222079fb2c31b1fdb50137f5a88e5f5ec0fb-34614096727-1`：
  `apk_collect.log` 声明 `sha256=ca6dbdc4d0353d55833c3dadb7b9bb955976b4c4ad211753014c7f867cad14bc`、
  `bytes=131487382`、`release_signing=false`、`formal_acceptance=NOT_RUN`、apksigner `Verifies`。
- 本机复算：下载后的 `trace-dev-debug.apk` SHA-256 与上述声明**逐字节一致**。

## 3. APK 字节级核验（插桩在场 / 端点不在场）

从 APK 内提取 `assets/flutter_assets/kernel_blob.bin`（73738976 B）后，用 Python
字面匹配（`re.escape`，**不是** grep 正则），计数如下：

| 探针 | 计数 | 含义 |
| --- | --- | --- |
| `OTA_MONO` | 4 | 插桩在场（阳性对照） |
| `MONO_BUDGET_START` / `MONO_BUDGET_RESET` | 2 / 3 | 传输侧事件点在产物内 |
| `MONO_PAUSE` / `MONO_RESUME` / `MONO_FAIL_AT` | 2 / 2 / 3 | 同上 |
| `MONO_TERMINAL` | 5 | 服务侧终止发布点在产物内 |
| `nonexist-probe-string` | 0 | 阴性对照（探针本身有效） |
| `pages.dev` | 0 | **无固件服务端点痕迹** |
| `workers.dev` | 0 | 同上 |
| `/api/public/firmware/latest` | 2 | 仅为 `share_links.dart` 的源码路径字面量与符号表，非注入的完整 URL |
| `ble-monitor-update.json` / `releases/download/` | 2 / 2 | 正向对照：硬编码常量确实可被检出 |

对 `kernel_blob.bin` 内全部 1919 个 `http(s)://` 字符串扫描，含 `firmware`/`update`
的仅 `github.com/Eitan-S-23/Trace/releases/...`（APK 自更新回退清单）与一条 sqlite
文档链接——**不存在任何固件服务端点 URL**。

> **方法学警示（避免后人重复误判）**：先用 `grep -o "pages.dev"` 得到 19 次命中，
> 经 Python 字面匹配核实为 **0**。差异来自正则 `.` 的通配语义——`grep -o -E`
> 在二进制流上会把 `pages?dev` 形式的跨字符串巧合计入。本节结论以字面匹配为准。

## 4. §2.2 六项逐项核对

| # | 要求 | 状态 | 实测 / 说明 |
| --- | --- | --- | --- |
| 1 | 手机序列号（只读）+ 独占设备窗口 | 已核对 | `10ADA4197U001CK`（vivo V2312A / PD2312，Android 13）；adb = `D:/install/leidian/LDPlayer4/adb.exe`。只读 `adb devices -l` 触发了 adb server v39→v41 重启（系统侧，无设备写入）。独占窗口未启用（A1 未执行） |
| 2 | J-Link 标识与精确命令 | 已核对（部分） | 工具 `C:\Users\SU\SEGGER\JLink_V818\JLink.exe`（Commander / DLL V8.18）；`ShowEmuList` 无输出——板载调试器为 ARM-OB STM32 2012，非 SEGGER 品牌枚举项。计划命令：`JLink.exe -Device AT32F435RGT7 -If SWD -Speed 1000 -AutoConnect 1 -ExitOnError 1 -CommandFile <脚本>`，脚本仅含 `h` / `regs` / `g`（不 `loadfile`、不烧录）。**未执行**：`regs` 回读本身需要一次连接停机，在场景已被阻断时承担停机风险无收益 |
| 3 | APK：提交 SHA + 文件 SHA-256（来自 dev CI 产物） | 已核对 | 提交 `57e0222`；`sha256=ca6dbdc4d0353d55833c3dadb7b9bb955976b4c4ad211753014c7f867cad14bc`（131487382 B）；来源 run 34614096727 工件，非本地构建 |
| 4 | 固件身份：只读核对方式 + 实测值 | **未取得**（四种状态中属「尚未读取」） | 途径①App 连接读 GET_INFO：**不受端点门禁限制**（§9.1 更正），本轮受阻于载体签名冲突（§9.2），且完整字段无观测出口（§9.3）；途径②J-Link 读 flash：需停机。**未触发任何"例外自动烧录"** |
| 5 | OTA 输入包 `.etu` 路径 + SHA-256（项目内既有资产） | **未取得** | `.etu` 由服务端固件清单下发，端点未配置时清单不可达，无法取得包指纹。项目内现存 `.cache/p2-6-*/**.etu`（P2-6 时期资产）尚未与任何服务端资产建立对应关系 |
| 6 | 输出目录 `.cache/p3-3-t1a-<run-id>/` | 已核对 | `.cache/p3-3-t1a-r1/`（先建后写：`ci/`、`apk/`、`jlink-identity.*`、`kernel_blob.bin`） |

## 5. 缺口根因链：dev APK 无法发起**检查更新**（可逐行复核）

> **范围更正（2026-09-12）**：本节链路止于「检查更新」按钮不可用，**不含 GET_INFO**——
> `readDeviceInfo()` 不受端点门禁限制，见 §9.1。

dev debug APK 无法发起真实 OTA（检查更新 → 下载 → 发起），链路如下（均为只读核对）：

1. `Tools/flutter/dev_apk.py:81-82` —— dev APK 的构建命令为
   `flutter build apk --debug --no-pub --target-platform=android-arm,android-arm64`，
   **不带任何 `--dart-define`**；`.github/workflows/flutter-dev-checks.yml` 也未注入
   `TRACE_*` 环境变量（对 `Tools/flutter/`、该 workflow、`android/app/build.gradle.kts`
   检索 `dart_define|dart-define|dartDefines` 无命中）。
2. `lib/config/share_links.dart:17-20, 46-54, 72` —— `cloudflareFirmwareLatestUrl` 与
   `cloudflareUpdateManifestUrl` 的 `String.fromEnvironment` 默认值均为 `''`；
   `firmwareLatestUrl` 仅由这两个编译期常量派生，**没有任何硬编码回退**；
   `hasFirmwareUpdateEndpoint => firmwareLatestUrl.isNotEmpty` ⇒ `false`。
3. `lib/services/ota_service.dart:239-241` ——
   `isFirmwareServiceConfigured => _latestUriBuilder != _defaultLatestUriBuilder || ShareLinks.hasFirmwareUpdateEndpoint`。
   运行期唯一构造点是 `lib/main.dart:98`（`Get.put(OtaService(), permanent: true)`）与
   `lib/pages/ota_upgrade_page.dart:33-35`，**均使用默认 builder，无运行期覆盖入口**
   ⇒ `isFirmwareServiceConfigured == false`。
4. `lib/pages/ota_upgrade_page.dart:374`、`:430` —— `canCheck` 含
   `otaService.isFirmwareServiceConfigured`，按钮 `onPressed: canCheck ? ... : null`
   ⇒ 「检查更新」被禁用。
5. 入口穷尽性核对：全 `lib/` 内 `OtaUpgradePage` 仅三处
   （`device_detail_page.dart:146`、`speedometer_page.dart:7989`、`:10181`），
   全部进同一页面、受同一门禁；`OtaService.startOtaUpgrade`（`ota_service.dart:769`）
   的前置为 `_firmwareFile` + `_deviceInfo` + `_asset`，其中 `_asset` 只能由服务端
   latest 清单签发（`ota_service.dart:432` `_latestUriBuilder(...)`），
   **不存在本地文件选择 / 侧载 `.etu` 的第二条路径**。
6. 对照（生产路径正常）：`.github/workflows/build.yml:215, 221-224` 在生产 APK 构建时
   注入 `--dart-define=TRACE_CLOUDFLARE_FIRMWARE_LATEST_URL=${update_service_url}/api/public/firmware/latest`，
   值取自仓库 secret（`TRACE_PUBLIC_UPDATE_SERVICE_URL` / `TRACE_UPDATE_SERVICE_URL`）。
   当前仓库变量（`gh api .../actions/variables`）为空集，故该值仅存在于 secret 中，
   本机不可读。

## 6. 后续路径（**均未执行，需另行授权**）

- **甲：为 dev 构建补齐固件端点注入**（改 `Tools/flutter/dev_apk.py` 的 `apk_build`
  命令与 `.github/workflows/flutter-dev-checks.yml`，从仓库 secret 透传同一端点），
  重跑 dev CI 取新 APK，再走 §2.2 第 4/5 项与 A1。
  代价：1 处 dev 工具链改动 + 1 次 CI + 1 次硬件轮（含 §2.3 的 halt 风险）。
  **残余不确定性**：即使端点可达，仍需服务端 latest 版本 > 板载固件才存在"可发起的升级"；
  且该改动会让 dev 产物固定指向生产固件服务，属共享校验工具的语义变化，需明确批准。
- **乙：接受缺口**，把 A1 记为因前置不成立而未执行，缺口登记在看板与后续批次处理，
  不追加工具链改动。
- 两项都无法绕开的客观事实：固件端点值在本机与仓库内均不可得（属仓库 secret），
  `docs/flutter-development-validation.md` 的常设授权也不含 secret 或生产工作流。

## 7. 边界遵守与输出路径审计

| 项 | 实际执行 |
| --- | --- |
| 硬件 | **未停机、未烧录、未连接目标板**；J-Link 仅执行 `ShowEmuList`（不 connect） |
| 设备 | 手机只读命令：`adb devices -l`、`dumpsys package`、`pm path`、一次设备内 `grep`（不改变设备状态）；**一次 `adb install -r` 尝试失败且无副作用**；未卸载、未清数据、未改设置（2026-09-12 补记见 §9.2） |
| 进程 | 未启动任何长期 logger；未按名全局杀进程；后台下载任务自行退出（exit 0） |
| 宿主机 | 未启动 PowerShell；未做项目外写入 |
| 项目内产物 | `.cache/p3-3-t1a-r1/`（`ci/`、`apk/`、`jlink-identity.jlink|.log`、`kernel_blob.bin`） |
| Git | 仅一个提交 `57e0222` 推送到独占 dev 分支；未动 `main`、未合并、未打标签、未跑生产工作流 |
| 验收 | 正式验收保持 `NOT_RUN`；本报告不构成 EXECUTED PASS |

## 8. 未证实项与局限

- **A1 判据未被观测**：`monoUs(MONO_TERMINAL) − monoUs(锚点) < 30s` 与 `NO_DURABLE_PROGRESS`
  在真机上**没有**任何实测数据；本报告只交付插桩与前置核对。
- 插桩的**行级正确性**已由 CI analyze/test 与产物字节核验间接支持，但**未经真机运行验证**：
  `MONO_*` 行在设备日志中的实际出现顺序、`durable` 字段取值、以及 `MONO_PAUSE` 是否会在
  A1 窗口内出现，均待真实观测。
- §2.2 第 4/5 项为空：板载固件身份与 `.etu` 指纹在本轮**未取得**，不得据其它批次记录推定。
- 停机风险（§2.3）在本轮**未被验证**：`h` 后 SD 卡是否可经 `g` 恢复，本轮无数据。
- 「设备是否返回身份」这一原始问题**仍未观测**：本轮四态中只有「尚未读取」成立；
  `设备未暴露 OTA 服务` / `GET_INFO 失败` / `端点未配置` 三者**均无观测数据**（§9.2）。
- §9.4「手机现存生产版早于身份读取代码」为**强证据推定**：依据是版本号/时间戳与 init 提交吻合、
  且 init 版 `ota_upgrade_page.dart` 无身份读取代码；**未直接证实**该 APK 的构建来源。

## 9. 补记（2026-09-12）：身份读取尝试、两处更正与一处新缺口

本轮只做只读核对与**一次安装尝试**；**未连接目标板、未做 BLE 通信、未停机、未烧录、未改手机设置**。

### 9.1 更正：GET_INFO 不受端点门禁限制

本报告初版称"无端点 ⇒ 无法读取板载身份"，**该判断有误**（用户指出，源码复核成立）：

| 位置 | 事实 |
| --- | --- |
| `lib/pages/ota_upgrade_page.dart:145` | `initState` 的 postFrame 回调里 `await _readDeviceInfo();`，无前置条件 |
| `lib/pages/ota_upgrade_page.dart:169-176` | `_readDeviceInfo()` 直接 `otaService.readDeviceInfo(address)` |
| `lib/services/ota_service.dart:281-365` | `readDeviceInfo` 走 服务发现 → 通知订阅 → GET_INFO，**不读 `isFirmwareServiceConfigured`** |
| `lib/pages/ota_upgrade_page.dart:374`、`:430` | 端点门禁只出现在 `canCheck` 与「检查更新」按钮的 `onPressed` |

即：端点门禁限制的是**检查更新/下载/发起**，不是 GET_INFO。真实设备能否返回身份仍需观测。

### 9.2 实测：dev debug APK 装入失败（签名冲突），已按指令停止

```text
$ adb install -r .cache/p3-3-t1a-r1/apk/run-107fbdb9c35740149115023e41c7051c/artifacts/trace-dev-debug.apk
Performing Streamed Install
adb: failed to install .../trace-dev-debug.apk:
  Failure [INSTALL_FAILED_UPDATE_INCOMPATIBLE: Existing package com.wen.gaia.gaia
  signatures do not match newer version; ignoring!]
```

| 项 | 手机现存 | dev debug APK |
| --- | --- | --- |
| 包名 | `com.wen.gaia.gaia` | `com.wen.gaia.gaia`（`android/app/build.gradle.kts:74`，无后缀、无 flavor） |
| versionCode | 86（versionName 1.0.60） | 86（pubspec `1.0.60+86`） |
| 签名 | release 签名，`signatures=[5bcd2e74]`（v2） | debug 签名（dev CI `release_signing=false`） |
| 安装时间 | lastUpdateTime 2026-07-10 | — |

**已停止**：未卸载、未清数据、未改任何设置，手机状态与执行前一致。

### 9.3 一并核实的新缺口：完整身份字段没有观测出口

即使装入成功，现有产物也只能给出两个身份字段：

| 字段 | 出口 |
| --- | --- |
| `deviceModel` | `ota_upgrade_page.dart:318`、`:888`；`ota_service.dart:363` 状态文本 |
| `currentVersionCode` | 同上 |
| `currentImageSha256Hex` | **无**界面、**无**日志出口 |
| `hardwareRevision` / `layoutId` / `bootVersion` / `protocolVersion` / `maxWindowSegments` | **无**界面、**无**日志出口 |

证据：`lib/` 全量检索中这些字段只出现在 `ota_device_info.dart`（定义）、`ota_ble_codec.dart`
（解码）、`share_links.dart:81-163`（拼 latest 查询参数）、`ota_service.dart:143-147`/`:889`/`:1611`
（内部比较）；`lib/services/ota_service.dart` 内 `debugPrint` 命中数为 **0**。

后果：步骤 2「用真实身份的完整字段拼 latest 查询」在现有产物上**参数取不全**——
`currentImageSha256Hex` 等只在 App 内部流转，外部观测不到。这是**观测出口缺口，与 HTTP 端点无关**。

### 9.4 已排除的载体：手机现存生产版（1.0.60+86）不能用于身份读取

| 证据 | 值 |
| --- | --- |
| 手机现存版本 | versionName 1.0.60 / versionCode 86，lastUpdateTime **2026-07-10** |
| 仓库 init 提交 `2ce8cd5`（2026-07-10） | `pubspec.yaml:18` = `1.0.60+86`；该提交的 `ota_upgrade_page.dart` 内 `deviceInfo\|GET_INFO\|readDeviceInfo\|currentVersionCode` 命中数 = **0** |
| `readDeviceInfo` 首次出现 | `3c05963` / `626c0fa`，均为 **2026-09-09** |

即手机上的构建早于身份读取代码约两个月，按下「OTA 页」不会有 GET_INFO 路径。

> **方法学警示（同类坑第二次）**：曾用 `adb shell grep -a -c readDeviceInfo <已装 base.apk>`
> 得 0，想据此断言"代码不存在"。**该探针无鉴别力**——对本地 dev APK 原始文件做同口径 grep，
> 已知含 `OTA_MONO`×4 的产物同样返回 0（APK 条目 deflate 压缩，条目名以外不可读）：

| 探针（原始 APK 字节） | dev APK（已知含插桩） | 结论 |
| --- | --- | --- |
| `OTA_MONO` | 0 | **假阴性**；须先解压 `kernel_blob.bin` 再字面匹配 |
| `kernel_blob.bin`（zip 条目名） | 2 | 仅条目名可读 |
| `com.wen.gaia.gaia` | 0 | 同上假阴性 |

本节结论**只用 git 版本/时间线证据**，不使用该 grep 探针。

### 9.5 待裁定：载体路径

先分清两件事：

- 只回答**步骤 1 的原始问题**（真机是否返回身份）⇒ 用现有已核验 dev APK，**无需重建**。
- 推进**步骤 2**（用完整字段拼 latest 查询）⇒ **必须重建**一次，补身份字段记录逻辑；
  该改动在 `lib/`（app 源码），**不在**第 3 项列举的「开发 workflow / APK helper / 记录逻辑 /
  runner 回归测试」范围，需另行明确授权。

载体选择（互不排斥于上面的重建）：

| 方案 | 内容 | 代价 / 需授权 |
| --- | --- | --- |
| 甲 | 卸载生产版 → 装 dev APK | **清空该 App 数据**；需明确授权；无需改构建配置 |
| 乙 | 给 dev/debug 构建加独立包名（`applicationIdSuffix`，显式启用、默认不变），与生产版共存 | 需授权改 `android/app/build.gradle.kts`；**不丢数据**、不需卸载；需一次 CI 重建 |
| 丁 | 换一台未装生产版的测试手机 | 需你指定设备；可配现有 APK 或重建后的 APK |

本轮建议：**乙**（重建可把「装得上 + 字段可见 + 端点注入」合并到同一次 CI），若只想先要
「设备能否返回身份」这一个答案，则 甲/丁 + 现有 APK 最快，且不消耗 A1 额度。
