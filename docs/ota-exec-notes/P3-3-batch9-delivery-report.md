# P3-3 第九批交付报告（集中整改）

- 日期：2026-09-11
- 角色：实现 agent（**非**独立验收 agent）。本报告是开发自测层面的交付记录，
  不是独立验收结论；`formal_acceptance` 全程为 `NOT_RUN`。
- 基线：`PLAN-OTA-EXEC.md` 第九批提示词 + 第八批独立复核
  `.cache/p3-3-review-batch8-20260910/review.md`。
- 范围：`app/bluetooth_flutter_Trace`（Flutter OTA 应用层）+ 三份执行笔记。
  **未修改** MCU 源码、冻结契约（`PLAN-OTA.md`、`docs/ota-binary-contracts.md`）、
  历史冻结验收包与 `Tools/provenance/manifest_profiles.json`。

## 1. 范围、起始与最终 SHA

| 项 | 值 |
| --- | --- |
| 活动项目根 | `D:\github\my\E-Track` |
| 分支 | `dev/flutter/apk/p3-3-batch6` |
| 起始 SHA（第八批交接） | `0d648e611cfbadb4f928e89a5fd3532f34ba0215` |
| 起始 tree | `8ba7bf0f7732526866a65ee910b34292c38646be` |
| 起始 profile blob | `15512870de154a59e870145b98403117da96cc83` |
| **实现最终 SHA** | `526267e5de507ca9d90ec242fa1c1c7a127cc2a7` |
| 实现最终 tree | `f6a600413b743e29ed9b52267e32b87b45e7e36b` |
| 本批改动规模 | 10 个文件，+1271 / −186 |

改动文件（`git diff --stat 0d648e6..526267e`）：

```text
lib/ota/ota_ble_transport.dart                     | 210 ++++++++---
lib/ota/ota_download.dart                          | 175 +++++++--
lib/services/bluetooth_service.dart                |  43 ++-
lib/services/ota_service.dart                      |  83 +++--
test/ota/ota_ble_transport_test.dart               | 403 ++++++++++++++++++---
test/ota/ota_download_test.dart                    |   8 +-
test/ota/ota_service_upgrade_test.dart             | 240 +++++++++++-
docs/ota-exec-notes/P3-3-batch9-rc3-05-poison-release-truth.md   | 135 +++++++
docs/ota-exec-notes/P3-3-batch9-rc3-07-settle-bound.md           |  92 +++++
docs/ota-exec-notes/P3-3-batch9-rc3-12-cancel-publication.md     |  68 +++
```

## 2. 提交链与远端映射

```text
f850c87  fix  其一——同资产文件族串行闸与闸内归属复核
9093295  test 其一补正——RC3-04/05 用例诊断前置与目录快照
bbd1009  test 其一补正——RC3-04/05 用例改有界观察并加编排遥测
7d23572  fix  其二——写通道废弃标记按设备作用域，解除须由 GET_INFO 往返证明
384b896  test 其二补正——修正 begin 断言取值并补设备复位重同步用例
79d8703  fix  其三——取消文案不再抢在清理前发布，fail-closed 文案不被覆盖
f1d6ea4  fix  其四——settle 宽限由 durable 预算封顶
526267e  test 其四补正——取消交错用例改用同设备新 transport 复核废弃标记
```

远端映射（`git ls-remote --heads origin dev/flutter/apk/p3-3-batch6`）：

```text
526267e5de507ca9d90ec242fa1c1c7a127cc2a7  refs/heads/dev/flutter/apk/p3-3-batch6
```

本地 `dev/flutter/apk/p3-3-batch6` 与 `origin/dev/flutter/apk/p3-3-batch6`
完全一致（无 ahead/behind）。**未**推送 main/master/tag，**未**强制推送，
**未**合并，**未**触发生产构建/发布工作流。

## 3. 最终 SHA 双宿主回归

`526267e` 的双宿主开发自测**全绿**：

| 项 | Linux | Windows |
| --- | --- | --- |
| run URL | `https://github.com/Eitan-S-23/E-Track/actions/runs/34543372459` | 同（job 级） |
| run attempt | 1 | 1 |
| job | `Flutter self-tests (ubuntu-latest)` | `Flutter self-tests (windows-2022)` |
| 结论 | success | success |
| `development_result` | PASS | PASS |
| `scope` | `all` | `all` |
| `apk_requested` / `apk_result` | true / PASS | false / NOT_REQUESTED |
| `source_before.head` | `526267e5de…`（clean=true） | `526267e5de…`（clean=true） |
| `lock_sha256_before/after` | `95ba3703…` / 同（未变） | `ed54e102…` / 同（未变） |
| `python` | 3.12.3 | 3.12.10 |
| `host` | `Linux-6.17.0-1022-azure-x86_64-with-glibc2.39` | `Windows-2022Server-10.0.20348-SP0` |

SDK 身份（`sdk_version.log` 的 `--machine` JSON，两宿主同源）：

```text
frameworkVersion = 3.47.3     channel = stable
frameworkRevision = e8113bf45620cbeb8aff64947ee4c93e16adb4cf
frameworkCommitDate = 2026-09-04 13:20:08 -0700
engineRevision = 06a2e2a110089dff50fe635cffd2a61e1b24fbcd
dartSdkVersion = 3.13.3       devToolsVersion = 2.60.0
```

命令记录与退出码（`result.json.commands`，逐条 `status=PASS`、`exit_code=0`）：

| 命令 | Linux 退出码 | Windows 退出码 |
| --- | --- | --- |
| `git clone … flutter.git --branch stable`（sdk_checkout） | 0 | 0 |
| `flutter --version --machine`（sdk_version） | 0 | 0 |
| `flutter pub get --enforce-lockfile`（dependencies） | 0 | 0 |
| `flutter analyze --no-pub`（analyze） | 0 | 0 |
| `flutter test --no-pub --reporter expanded --timeout 2m test`（tests） | 0 | 0 |
| `flutter build apk --debug --no-pub --target-platform=android-arm,android-arm64` | 0（552.9 s） | 未请求 |
| `apksigner verify --verbose <app-debug.apk>` | 0 | 未请求 |

原始日志（本轮已下载进 `.cache-ci/batch9/run-34543372459/`）：

```text
ubuntu/run-b25fcc66abf54023b4b5810dc403589d/{result.json,logs/*.log}
windows/run-5cd62992826941b5ac38d521c0f74fa3/{result.json,logs/*.log}
```

- analyze：两宿主均为 `No issues found!`（Linux 13.1 s / Windows 13.6 s），0 issue。
- tests：Linux `+281 ~7: All tests passed!`（281 通过、7 跳过）；Windows
  `+288: All tests passed!`（288 通过、0 跳过）。跳过的 7 项为 Linux 上不适用
  的 Windows 专有用例，**不作为** 其 Windows 对应项的替代证据。

### 3.1 真实告警（未掩饰）

`apk_build.log`（Linux）含 **11 条 warning、0 条 error**，均为工具链既有告警，
非本批引入：

```text
Warning: Flutter support for your project's Gradle version (8.14.0) will soon be dropped…
Warning: Flutter support for your project's Android Gradle Plugin version (8.11.1) will soon be dropped…
Warning: Flutter support for your project's Kotlin version (2.2.20) will soon be dropped…
Warning: 插件 flutter_plugin_android_lifecycle / geolocator_android / package_info_plus /
         path_provider_android / share_plus … requires Android SDK version 36 or higher
```

## 4. debug APK（不是 release 产物，也不是独立验收）

| 项 | 值 |
| --- | --- |
| 结果 | PASS（`apk_result: PASS`，Linux job） |
| 产物名 | `flutter-dev-debug-apk-526267e5de507ca9d90ec242fa1c1c7a127cc2a7-34543372459-1` |
| 文件 | `trace-dev-debug.apk` |
| SHA-256 | `4f13b33fd6e6ec5a2d61c88ae1c6863b1d47147d65926bc607fc183810471574` |
| 大小 | 131 472 494 字节 |
| `release_signing` | **false** |
| 签名校验 | `apksigner verify --verbose` 退出码 0；v2 scheme true；signer 数 1 |

来源为 `logs/apk_collect.log` 的产物 JSON（`artifact_kind:
development-debug-apk`、`formal_acceptance: NOT_RUN`、`commit: 526267e5de…`）。

**分开记录、不合并陈述**：

- Windows 侧 **无 APK 任务**（`apk_result: NOT_REQUESTED`，作业内 `Upload debug APK`
  步骤状态 `skipped`）。
- Windows EXE（`LVGL.Simulator` / 桌面打包）本批 **未构建**：本批未改
  `pubspec.yaml` / `pubspec.lock` / 平台打包输入，按应用级 `AGENTS.md`
  不触发 EXE 重建；因此 **EXE 结论 NOT_RUN**。
- release 模式 APK **NOT_RUN**（工作流无 release 签名密钥，也不产出 release 包）。
- 真机安装、卸载旧版、清数据、物理观测 **全部未执行**（需另行授权）。

## 5. 依赖锁与有效配置

以 Git 对象直接比对，不用「某个 Dart 文件哈希没变」推而广之：

| 文件 | 起始 blob | 最终 blob | 是否变化 |
| --- | --- | --- | --- |
| `app/bluetooth_flutter_Trace/pubspec.yaml` | `7559e21d9941250657f4a0cbb885223bdeff4480` | 同 | **未变** |
| `app/bluetooth_flutter_Trace/pubspec.lock` | `589617428b22c4c1026ad2dc35b4825223247794` | 同 | **未变** |
| `.github/workflows/flutter-dev-checks.yml` | `17fb60aff3fadffc587772844ffe6cf73326527a` | 同 | **未变** |
| `Tools/provenance/manifest_profiles.json` | `15512870de154a59e870145b98403117da96cc83` | 同 | **未变** |

两宿主 `result.json` 的 `lock_sha256_before == lock_sha256_after`，
`lockfile_unchanged` 为真，`flutter pub get --enforce-lockfile` 退出码 0。

**有效配置（migration）≠ 提交内容**：工作流在运行期把
`analysis_options.yaml` 由提交的 `b51e1221…`（blob `61b6c4d`）改写为
有效内容（Linux `62d50015…` / blob `862c906`，Windows `cfe7a312…` /
blob `06dcbd36…`），用于排除 `build` 与平台目录；`result.json` 的
`toolchain_regen`、`source_deltas_bound_toolchain_regen` 如实记录了该差异与
`gradle.properties` 的工作树改动（`dirty_semantic_sha: cd4198da…`，
由 `apk_prepare` 生成，`source_after.clean=false` 是**预期**结果）。
这些不是本批交付的源码内容，未提交、未混入任何提交。

## 6. RC3-01 … RC3-12 全量处置表

「源码处置状态」只描述源码/用例层面的处置；「运行验证状态」只描述**实际执行过**
的观测。二者不互相顶替。引用行号为最终 SHA `526267e` 的工作树行号。

| 原 ID | 合同依据 | 第九批实际修改与共享依赖影响 | 本次证据 | 源码处置状态 | 运行验证状态 | 剩余缺口 |
| --- | --- | --- | --- | --- | --- | --- |
| RC3-01 | P3-3 Spec 编译/analyze/test/build；执行合同 §7.3 | 无源码改动；本批全部 app 改动经两宿主编译 | `run-34543372459` 双宿主 `analyze`/`tests` 退出码 0 与原始日志 | 前批已修，保留 | **EXECUTED PASS（双宿主）** | release APK/EXE 与安装 NOT_RUN |
| RC3-02 | 可执行且有鉴别力的测试；fail-closed 提交输入证据 | 本批未改 runner；新增用例全部可执行、失败可见（3 次真实红灯均以修复收场，未弱化断言） | `tests.log` 计数 281/288；§7 失败链 | 前批已修（collector fail-closed），保留 | **EXECUTED PASS（双宿主）** | 开发指南 166/179 与已允许的迁移记录冲突 → 共享文档协调项（§10） |
| RC3-03 | Binary 2.4/4.4/4.5/5；MCU parser/session/staging 真值 | 替身 `reconnect()` 删除无依据的 `_pending.clear()`；替身按 MCU 语义处理坏帧（吃完→CRC 失败→继续扫描）；新增「设备复位后重同步」用例 | 笔记 §2 逐条行号（`ota_ble_frame.c:260-272/286-313`、`ota_ble_session.c:158-169/799/821-830`）；`ota_ble_transport_test.dart` | **模型侧前提已按 MCU 真值修正** | PASS（模型层） | 真机接收方复位/重同步边界的原生观测 NOT_RUN |
| RC3-04 | Spec 单一 owner 与取消/重入；CANCEL-RECOVERY | 删除边界改为**同资产文件族串行闸内三删 + 闸内复核归属**（`_deletePartial`：`ota_download.dart:1094-1101`；闸为 `OtaFilePathGate`，实例 `_fileGate`，桶键 `_gateBucketOf`，见 `:68/:101/:106`）；写入/rename/删除共用一把闸（`:262/:543/:617/:1002/:1066/:1095`）；用例改有界观察并加编排遥测 | `run-34518819004`/`34520463986` 红灯 → `f850c87`+`9093295`+`bbd1009` 修复；最终 `tests.log` 全绿 | **已修复**（在真实破坏性 IO 边界，非再加外层 guard） | **EXECUTED PASS（双宿主）** | 迟到 MTU/探针的原生集成观测 NOT_RUN |
| RC3-05 | HTTP-RESUME；FLUTTER-TRANSPORT 1057；取消/帧边界 | 废弃标记作用域由「链路代次」改为**设备**（`BluetoothService` 按地址恒定）；废弃期间唯一放行 `GET_INFO` 探针；解除须由**本实例探针**收到 `session=0` 且 `seq` 匹配的 INFO 证明；探针重试 ≤20 次 × 800 ms | 笔记 §2/§3 行号与候选条件表；`run-34540367912` 红灯（用例编译错）→ `384b896` 修正 → `run-34541634700` 绿 | **已修复** | **EXECUTED PASS（双宿主）** | 真机「截断写后同设备重连，无 INFO 证据前业务帧必须失败」NOT_RUN |
| RC3-06 | Binary 5.5/5.6/5.7 ACK 权威与有界恢复 | 本批未改 | 既有 ACK/恢复用例随全量 tests 执行 | 前批已修，保留 | **EXECUTED PASS（双宿主）** | 无新硬件 ACK 观测；不回炉已被纠正的旧反例 |
| RC3-07 | BLE-TUNING 1033；RETRY-POLICY 1088 | 超时后 settle 宽限由 `_capByBudget(writeTimeout*2)` 封顶（`ota_ble_transport.dart` 超时分支）；新增 4 条注入时长用例（接近预算挂起／迟到成功／迟到错误／取消交错） | `P3-3-batch9-rc3-07-settle-bound.md` §3 鉴别力表；`run-34542776512` 红灯（用例自锁）→ `526267e` 修复 → `run-34543372459` 绿 | **已修复**；**未降低任何门槛**（30 s / 10 s / 2×writeTimeout 均不变） | 注入时长用例 **EXECUTED PASS**；真机 bound **NOT_RUN** | 真机 GATT 写黑洞下的终止发布时刻、宽限归零后与探针字节的交错（§8） |
| RC3-08 | BLE-LIFECYCLE 1017/1018；FLUTTER-TRANSPORT 1058；DEVICE-DTO | 本批未新增该类源码；废弃标记作用域改动与 disconnect 记账共享 `deviceScope` 路径，经双宿主全量回归 | `tests.log`；`P3-3-batch9-rc3-05-poison-release-truth.md` §3.1 | 前批已修，保留 | **EXECUTED PASS（双宿主）** | 真实重连下 watcher 保留的物理观测 NOT_RUN |
| RC3-09 | 精确 FFF0/FFF2/FFF1 发现与锁定平台 API | 本批未改 | Windows `tests.log`（288 通过，含 Windows 专有用例）；Linux 7 项跳过**不计入** | 前批已修，保留 | **EXECUTED PASS（Windows 实跑；Linux 跳过不替代）** | 物理 BLE 与平台生命周期测量 NOT_RUN |
| RC3-10 | HTTP-ERROR；UNKNOWN-FIELDS；稳定状态/诊断 | 本批未改 | 既有分类用例随全量 tests 执行；`analyze` 0 issue | 前批已修，保留 | **EXECUTED PASS（双宿主）** | 真实 HTTP 集成观测（单独计划），本批未立新缺陷 |
| RC3-11 | HTTP-DOWNLOAD/RESUME；有界 body 释放 | 本批未改 | 既有终止/取消用例随全量 tests 执行 | 前批已修（含替身观测缺口），保留 | **EXECUTED PASS（双宿主）** | 真实 Dio IOAdapter 的 socket 终止观测 NOT_RUN |
| RC3-12 | Spec 可观测状态与清理一致性；单一身份/查询链 | 传输 catch 的**用户取消分支**与 **fail-closed 分支**均不再写 `_upgradeStatus`；`phase=cancelled` 与「操作已取消」仍由 `cancelUpgrade` 在包清理完成后同段发布；用例观测取消窗口内**每一次**发布 | `P3-3-batch9-rc3-12-cancel-publication.md` §2（`3e10311` 四处原始行号）与 §4；`run-34541634700` 绿 | **已修复** | **EXECUTED PASS（双宿主）** | 无新增缺口；取消窗口文案的真机观测可并入 §8 同一计划 |

## 7. 逐条反例处置（不用「都有处置，因此全部完成」的口径）

| # | 复核反例 | 处置 | 依据 |
| --- | --- | --- | --- |
| 1 | **RC3-03/05/07**：新链路令牌不能证明接收方已重新同步；替身 `_pending.clear()` 把未证明的结论固化进用例 | **已修复** | 删除重连即解除；作用域改设备；解除须由 INFO 正向证据；替身不再清缓冲。笔记 §2.3/§2.4/§3.1 |
| 2 | **RC3-04/05**：归属只在删除**之前**检查，不在**每个**删除边界；`_deleteStrict` 在 `exists()` 上挂起期间可被后来者接管 | **已修复** | 三删在同一把文件族串行闸内执行并在闸内复核归属（`_deletePartial`，`ota_download.dart:1094-1101`，闸内 `await _deleteStrict(...)` ×3）；新增边界排期用例 |
| 3 | **RC3-12**：取消文案仍在清理前带着「取消」字样发布；文本监听只看最终标签 | **已修复** | 两个分支均不再写文案；用例改为观测窗口内全部发布。笔记 §3/§4 |
| 4 | **RC3-07**：超时后的 settle 等待独立于 durable 预算，默认再多等 20 s（终止发布可达 50 s） | **已修复（源码+用例）** | 宽限由剩余预算封顶；新增 4 条鉴别用例。笔记 §2/§3 |
| 5 | RC3-04/05 复核术语纠正：共享资源是**路径/文件名/assetId**，不是「旧 downloader 一定取消新对象的 token」 | **证据纠正（接受）** | 已按「同资产文件族串行闸」命名与实现；服务内 1033-1041 陈旧注释不再作为证据 |
| 6 | 复核保留纠正：`maxRetries` 默认是 5，非某预算用例里的 1 | **证据纠正（接受）** | 全量 tests 绿；本批未改该默认值 |
| 7 | RC3-07「`Future.timeout` 不物理取消 native 写」 | **仍开放** | 源码已承认该事实并把等待上界收回预算内；**native 层**是否真的取消仍需真机观测（§8） |
| 8 | RC3-08 Windows 迟到断开用例未证明「真实重连下 watcher 保留」 | **仍开放** | 无真机/原生观测；本批未声称已证明 |
| 9 | RC3-09 Linux 跳过不等于 Windows 证据 | **已按此口径记录** | 报告 §3 分列两宿主计数；跳过项不替代 |
| 10 | RC3-10/11 真实 HTTP 与真实 Dio adapter 退出 | **仍开放** | 需单独观测计划；本批未立新缺陷 |
| 11 | RC3-02 开发指南 166/179 行与已允许的迁移记录冲突 | **仍开放（共享文档协调项）** | 属共享文档/治理面，交主会话处理（§10），实现批不擅自改 |

## 8. 真实失败链（保留，不掩饰）

| run | 提交 | 结论 | 真实原因（原始日志） |
| --- | --- | --- | --- |
| 34518819004 | `f850c87` | 双宿主 failure | `ota_service_upgrade_test.dart`「清理已取删除闸、删除体未执行时后来者接管：part/sidecar/tmp 均不得按路径删除」`Expected: true / Actual: <false>`（Linux `+147 -1`；Windows `+242 -1`） |
| 34520463986 | `9093295` | 双宿主 failure | 同上用例，同一断言仍失败（`+275 -1` / `+282 -1`）；证明首轮补正未触及根因 |
| 34521462921 | `bbd1009` | 双宿主 success | 修复生效；Linux 出 debug APK |
| 34540367912 | `7d23572` | 双宿主 failure | `analyze`：`error • The getter 'isOk' isn't defined for the type 'OtaBeginAck' • test/ota/ota_ble_transport_test.dart:1667:18 • undefined_getter`；`tests`：该测试文件编译失败（`+154 -1` / Windows `+219 -1`） |
| 34541634700 | `79d8703` | 双宿主 success | `384b896` 修正断言取值后通过 |
| 34542776512 | `f1d6ea4` | 双宿主 failure | 「预算耗尽前取消交错」用例 `Expected: 'WRITE_TIMEOUT' / Actual: 'CANCELLED'`（Linux `+212 -1`；Windows `+99 -1`）。根因：`abortBestEffort()` 已取消该 transport，`begin()` 在 `_checkUsable()` 即抛 CANCELLED，未到写闸 |
| **34543372459** | **`526267e`** | **双宿主 success** | 改用同设备作用域的**第二个 transport** 复核废弃标记（`_ReboundWrapper`，沿用 RC3-05⑤ 既有模式），该用例全部断言通过 |

红灯期间未合并、未发布、未改分支保护，也未把红灯说成绿。

## 9. 运行验证状态汇总（严格区分）

- **已在 CI 实跑通过**：`flutter analyze`、`flutter test`（全量 `all` 档位）、
  `flutter pub get --enforce-lockfile`、`flutter build apk --debug`、
  `apksigner verify`（两宿主 analyze/test；APK 仅 Linux）。
- **本批 NOT_RUN（需另行计划与授权）**：真机 BLE GATT 写黑洞观测（§8 计划见
  `P3-3-batch9-rc3-07-settle-bound.md` §4）、release APK/EXE、安装/卸载/清数据、
  物理设备观测、MCU 侧真机 RTT 复现。
- **不带入结论**：本报告**不**主张任何独立验收结论；`formal_acceptance` 全程
  `NOT_RUN`。

## 10. 共享文档与协调项（不属本实现批，需主会话处理）

- `docs/flutter-development-validation.md` 第 166/179 行与「允许的迁移记录」冲突
  （复核 RC3-02 遗留）。
- 看板 `PLAN-OTA-EXEC.md` 的任务卡状态与 §10 会话日志回写。
- OTA-DEC-013 治理结论保持不动（本批未重新裁定，也未擅自迁移 toy/真包真机要求）。
- 共享索引/工作树的串行化：本批仅在独占的 `dev/flutter/**` 分支提交与推送，
  未与其它 agent 并发操作同一索引。

## 11. 工作树与输出路径审计

- 最终 `git status --short --branch` 与起始相比：**8 个既有 tracked 修改原样保留**
  （`PLAN-OTA-EXEC.md`、`docs/flutter-development-validation.md`、
  `docs/ota-exec-notes/P3-3-dispatch-readiness-2026-09-07.md`、
  `docs/ota-exec-notes/P3-3-research-flutter-ota.md`、
  `docs/ota-prompts/prompt-P3-3-implementation.md`、
  `docs/ota-prompts/prompt-P3-5-integration.md`、`docs/ota-spec-decisions.md`、
  `tests/ota/test_acceptance_bundle.py`），**全部未暂存、未提交、未改动**。
- 遗留未跟踪文件（`.P3-5`、`.claude/*.py`、`.claude/*.js`、`err.txt`、
  `docs/ota-exec-notes/P3-3-acceptance-scope-ruling-2026-09-10.md` 等）
  原样保留，未被删除、未被暂存。
- 本批每次提交只显式暂存本任务的文件（源码 4 个 + 用例 3 个 + 笔记 3 个），
  无夹带、无治理改动、无覆盖原认领人内容。
- 输出路径：本批一切写入均在项目根 `D:\github\my\E-Track` 内——
  `docs/ota-exec-notes/P3-3-batch9-*.md`（3 份笔记）、
  `.cache-ci/batch9/**`（CI 证据包与原始日志）。未使用项目外临时目录，
  未写 `%TEMP%`、盘符根或兄弟仓库；下载失败产生的空 `apk.zip` 已删除，
  未留下零字节残留。
- 未在共享工作树上使用 `git checkout/restore`；未做本地 Flutter/Gradle 构建；
  未用 PowerShell 执行构建类命令；未做 Python 字节手术（本批编辑一律走
  Edit/apply_patch 等价工具）。

## 12. 追加轮：r2 复核 RC3-07 / RC3-08/12 关闭（2026-09-11 晚场）

本节接续 §1 的「实现最终 SHA」`526267e`，记录第二轮独立复核
（`.cache/p3-3-review-batch9-r2-20260911/review.md`）中两项**代码发现**的关闭
过程与证据。该复核第三项「真机观测计划仍未获批」（P2）**不在本节关闭范围**，
见 §13。

### 12.1 提交链（526267e → 7ca1929，5 个提交）

```text
f6e3462  docs  第九批交付报告——范围/提交链/双宿主回归/RC3 全量处置表
40e503d  fix   集中整改——隔离解除围栏/取消期发布让出/持锁互斥用例
b29954c  fix   CI 红修复——可空接收者/迟到片字节下界/异常类型判据
e512515  fix   RC3-07/08/12 整改——恢复探测端到端截止与 failClosed 迟到错误围栏
7ca1929  fix   RC3-07 黑洞用例——fake 分片归属按自身同步字判定
```

`git diff --stat 526267e..7ca1929`：6 个文件，**+1494 / −113**
（`ota_ble_transport.dart` 365、`ota_service.dart` 88、
`ota_ble_transport_test.dart` 327、`ota_service_upgrade_test.dart` 427、
本报告 267、`P3-3-batch9-rc3-07-settle-bound.md` 133）。逐文件增删行数与真实
编辑量一致，无整文件行尾翻转型伪变更。

远端映射（`git ls-remote --heads origin dev/flutter/apk/p3-3-batch6`）：

```text
7ca19297d051ad22856a9aec5339399ff9e49bb6  refs/heads/dev/flutter/apk/p3-3-batch6
```

本地 HEAD、远端分支、本轮 CI 的 `source_before.head` 三者一致。**未**推送
main/master/tag，**未**强制推送，**未**合并，**未**触发生产构建/发布工作流。

### 12.2 RC3-07：恢复探测的端到端截止（`e512515`）

§8 计划面要求的「终止发布不得晚于恢复预算截止」，此前只覆盖探针循环入口与
应答等待；写分片等待（`writeTimeout` 10 s）与写后结算宽限（2 × `writeTimeout`）
落在探针之外，可把终止推迟到预算 16 s 之外（最坏 10 s + 20 s 量级的无界第三段）。

- 探针入口建立单一单调时钟与预算（`_recoveryClock` / `_recoveryBudget`，
  剩余量 `_recoveryLeft`），写分片、写后结算、应答等待三处统一经 `_capByBudget`
  取 `min(本段上限, _hardDeadlineLeft)`，其中
  `_hardDeadlineLeft = min(_noProgressLeft, _recoveryLeft)`。
- 到期后**同步**清探针登记（zero-guard），停止后续探测；隔离状态**不**因到期
  解除——解除仍须由本实例探针收到 `session=0` 且 `seq` 匹配的 INFO 证据。
- 迟到的物理写仍被安全跟踪：在途写未结算时 `_awaitDeviceWritesIdle(0)` 抛
  `TIMEOUT`，`getDeviceInfo` 以 `OtaTransportException(code: 'TIMEOUT')` 退出，
  不把在途字节当作已证据化。**未降低任何门槛**（30 s / 10 s / 2×`writeTimeout`
  / 20 探针 × 800 ms 全部不变）。

### 12.3 RC3-08/12：failClosed 已决终止的迟到错误围栏（`e512515`）

`ota_service.dart` 新增 `_failClosedDecided`（`startOtaUpgrade` 复位、`failClosed()`
发布终止态前置位），三处 catch 在链路代次校验后经 `_consumeFailClosedDecision()`
消费：已决时不再以通用失败文案覆盖 `terminalState` / `retryableLater` /
`upgradeStatus`，也不把相位打回 `failed`。

### 12.4 真实失败链（保留，不掩饰）

| run | 提交 | 结论 | 真实原因（原始日志） |
| --- | --- | --- | --- |
| 34571974895 | `40e503d` | 双宿主 failure | Linux `analyze` exit 1；测试文件编译失败（可空 `File.exists`）；`tests` `+251 ~7` 含 2 条 transport 断言失败（20 与 30 字节、期望传输异常实为注入的 `StateError`）。Windows `analyze` exit 1、`tests` `+258` 同 3 项失败 |
| 34573026537 | `b29954c` | 双宿主 success | 上述 3 项修复生效 |
| **34587263364** | **`e512515`** | 双宿主 failure | 两宿主 `analyze` 均 `No issues found!`；`tests` **仅一条**失败：`恢复探针写卡死…（RC3-07 黑洞）`，`Expected: <122> / Actual: <0>`（Linux `00:58 +223 -1`，终局 `01:32 +288 ~7 -1`；Windows `00:38 +106 -1`，终局 `01:33 +295 -1`）。Linux 检查未过 → APK 链 8 条命令全部 `NOT_RUN`，未产出 APK |
| **34588728713** | **`7ca1929`** | **双宿主 success** | 见 §12.5 |

红灯根因在**测试替身**，不在产品源码，且**未**改断言、**未**弱化注入：

- `_McuSim._chunkFrameCmd` 已按「chunk 首字节是否为同步字」区分首片/续片，但对
  **首片**仍先拼上悬空的 `_pending`（122 B 的 DATA 半帧）前缀，于是 GET_INFO
  探针首片被归类为 `cmdData`，`hangControlCmd: cmdGetInfo` 的卡死注入连续两次
  落空。
- 落空的两次探针各写 10 B 进 `_pending`，恰好把 142 B 的 DATA 帧补满并被消费，
  `_pending` 归零，第三次探针才真正卡死——末态因此是 `pendingByteCount == 0`，
  与真实链路语义（探针写卡死在传输层、字节根本到不了 MCU、悬空 122 B 恒在）
  不符。
- 修复（`7ca1929`）：chunk 自身以同步字开头即**新帧首片**，直接读自身帧头；
  只有续片（不以同步字开头）才拼接 `_pending` 恢复所属帧。修复不改变 DATA
  分片注入与续片归类行为（既有注入用例仍全绿）。

### 12.5 最终 SHA 双宿主回归（run 34588728713）

| 项 | Linux | Windows |
| --- | --- | --- |
| run URL | `https://github.com/Eitan-S-23/E-Track/actions/runs/34588728713` | 同（job 级） |
| 事件 / attempt | push / 1 | push / 1 |
| 结论 | success | success |
| `development_result` | PASS | PASS |
| `scope` | `all` | `all` |
| `apk_requested` / `apk_result` | true / **PASS** | false / `NOT_REQUESTED` |
| `source_before.head` | `7ca19297d0…`（clean=true） | `7ca19297d0…`（clean=true） |
| `lock_sha256_before/after` | `95ba3703…` / 同（未变） | `ed54e102…` / 同（未变） |
| 命令条数/退出码 | 13 条全 `PASS`、exit 0 | 5 条全 `PASS`、exit 0 |
| `analyze` | `No issues found!`（15.2 s） | `No issues found!`（11.8 s） |
| `tests` | `+289 ~7: All tests passed!` | `+296: All tests passed!` |

三个新用例在两宿主逐条可见（Linux 展开计数）：

```text
00:21 +152  ota_service_upgrade_test.dart: failClosed 已决终止不被迟到在途写原生错误覆盖…
00:43 +223  ota_ble_transport_test.dart:   恢复探针写卡死…（RC3-07 黑洞）
00:59 +224  ota_ble_transport_test.dart:   探针写完成但 INFO 迟到于恢复预算…（RC3-07 迟应答）
```

Ubuntu job 墙钟 10:20:30 → 10:32:46（736 s）；Windows job 10:20:30 → 10:23:50
（200 s，无 APK 任务）。原始日志本轮已下载进
`.cache/p3-3-r2-ci-34588728713/{flutter-dev-ubuntu-latest,flutter-dev-windows-2022}-*`
（各含 `result.json` + `logs/*.log`），红轮原始日志保留在
`.cache/p3-3-r2-ci-34587263364/`。两侧均在项目根内，无项目外写入。

### 12.6 debug APK（run 34588728713，Linux）

| 项 | 值 |
| --- | --- |
| 产物名 | `flutter-dev-debug-apk-7ca19297d051ad22856a9aec5339399ff9e49bb6-34588728713-1` |
| 文件 / 大小 | `trace-dev-debug.apk` / 131 485 342 字节 |
| SHA-256 | `5c38ad11b5d4373906b36e0f4c0ddd9a031fda8755aefa17b6470289d82e4f05` |
| `release_signing` / `formal_acceptance` | false / `NOT_RUN` |
| 签名校验 | `apksigner verify --verbose` exit 0；v1 false、**v2 true**、v3/v3.1/v4 false、SourceStamp false、`Number of signers: 1` |

来源为 `logs/apk_collect.log` 的产物 JSON（`artifact_kind:
development-debug-apk`、`commit: 7ca19297d0…`）。仍是**开发自测产物**，不是
release 包，也不是独立验收证据；Windows 侧无 APK 任务，EXE 仍 `NOT_RUN`。

### 12.7 处置表增量（覆盖 §6 中 RC3-07/08/12 三行）

| 原 ID | 本轮实际修改 | 本次证据 | 源码处置状态 | 运行验证状态 | 剩余缺口 |
| --- | --- | --- | --- | --- | --- |
| RC3-07 | 探针预算升级为**端到端**：写分片、写后结算、应答等待全部经 `_capByBudget` 封顶；到期同步退休且不解除隔离；新增黑洞/迟应答两条鉴别用例 | `run-34587263364` 真实红灯（黑洞用例暴露替身缺陷）→ `7ca1929` 修复 → `run-34588728713` 双宿主绿 | **已修复（端到端）** | 注入时长用例 **EXECUTED PASS（双宿主）**；真机 bound **NOT_RUN** | 真机 GATT 写黑洞下的终止发布时刻与 native 层是否真的取消物理写（§13 相关项 1/7） |
| RC3-08 | `_failClosedDecided` 围栏：三处 catch 在代次校验后消费已决结论，迟到非 CANCELLED 错误不再覆盖 reason/retryability/closing 状态 | 新增用例 `ota_service_upgrade_test.dart:1605` 双宿主通过；Linux `+152` | **已修复** | **EXECUTED PASS（双宿主）** | 真实重连下 watcher 保留的物理观测 **NOT_RUN** |
| RC3-12 | 与 RC3-08 同一围栏：已决终止的文案/相位不被迟到错误回跳 | 同上（同一用例同时断言 `terminalState.code`、`retryableLater`、`phase`、`upgradeStatus`、通知日志） | **已修复** | **EXECUTED PASS（双宿主）** | 无新增缺口；取消窗口文案的真机观测并入 §13 |

§6 其余各行（RC3-01～06、09～11）本轮**未触碰**，其处置状态与剩余缺口保持
原样；本轮未新增或回退任何此前接受的修复。

### 12.8 NOT_RUN 清单（本轮不变）

`flutter analyze`、`flutter test`（`all` 档位）、`flutter pub get --enforce-lockfile`、
`flutter build apk --debug`、`apksigner verify` 已在 CI 实跑；以下仍 **NOT_RUN**：

- 真机 BLE GATT 写黑洞观测（终止发布时刻、native 写是否真被取消、迟到片交错）；
- release APK / Windows EXE；真机安装、卸载旧版、清数据；
- MCU 侧真机 RTT 复现；物理 BLE 与平台生命周期测量。

本报告仍**不**主张任何独立验收结论，`formal_acceptance` 全程 `NOT_RUN`。

### 12.9 本轮工作树与输出审计

- 起始与结束的 `git status --short` 完全一致：**8 个既有 tracked 修改**与
  **21 项未跟踪条目**原样保留，全部未暂存、未提交、未改动。
- 本轮提交只显式暂存本任务文件（源码 2 + 用例 2 + 笔记 1 + 报告 1 及中间批次），
  无夹带、无治理改动、无覆盖原认领人内容。
- 未在共享工作树上使用 `git checkout/restore`；未做本地 Flutter/Gradle 构建；
  未用 PowerShell 执行构建类命令；全部写入均在项目根
  `D:\github\my\E-Track` 内（`.cache/p3-3-r2-ci-*`、本报告）。

## 13. r2 复核第三项（观测计划）的处置状态：改为待批表，仍未执行

r2 复核第三项 `RC3-07/02: The Observation Plan Remains An Unapproved Draft`（P2）
**不是代码缺陷**，本轮按复核给出的六条要求把原草案重写为可执行、可批准的
operations sheet：`P3-3-batch9-device-observation-sheet.md`（**待批**）。

重写期间的只读源码核查得到三条**改变计划形态**的事实，均已写入该表：

1. 原草案用 `DateTime.now().microsecondsSinceEpoch` 作判据时钟，与冻结契约
   `OTA-XC-BLE-TUNING`（`docs/ota-cross-system-contracts.md:1037`「计时使用单调
   高精度时钟」）冲突；改为进程内唯一 `Stopwatch` 单调计数器，判据只用其差值。
2. 无进展锚点改为产品自身的预算时钟（`ota_ble_transport.dart:296/339/436/541`），
   并明写「重复的相同 BEGIN／durable 不重置」，同时补上原草案漏掉的后台停表
   （`:636/:644`）干扰口径。
3. T2 所依赖的 MCU 侧 RTT 通道**在当前生产固件上不存在**：
   `Libraries/OTA/ota_ble_frame.c`、`ota_ble_ring.c`、`ota_ble_session.c`
   （共 1370 行）零输出调用；OTA 区域仅有的 RTT 打印全部在
   `P2_1/P2_2/P2_3/P2_6_TEST_ENABLE` 自检宏内（生产构型不编译）。
   按草案自身规则记 `ENV_BLOCKED`，不得用「RTT 没有错误行」推定通过。

该表另列三个需用户裁定的决策点（T1b 可控外设选型、T2 是否另立 MCU 插桩卡、
20×800ms 作为计划内部前提的确认）与总配额 3 轮。

**本轮未执行任何设备操作**：无烧录、无安装、无 BLE 连接、无 logcat 采集、
无 RTT；§12.8 的 NOT_RUN 清单因此保持不变。
