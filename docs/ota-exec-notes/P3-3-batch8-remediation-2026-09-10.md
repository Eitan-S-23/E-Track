# P3-3 第八批集中整改（2026-09-10）

- 活动根目录：`D:\github\my\E-Track`
- 分支：`dev/flutter/apk/p3-3-batch6`
- 起点 HEAD：`3e10311e98b79b7fb975b2425b4946739cfc6630`（tree
  `195aa9b1bb502e336bd31baa8c117570ce4d422e`，profile blob
  `15512870de154a59e870145b98403117da96cc83`）
- 输入：`.cache/p3-3-review-batch7-20260910/review.md`（第七批独立审查）
- 性质：实现 agent 的集中整改 + 自测，**不是**独立验收；正式验收状态仍为
  `NOT_RUN`，任务卡保持「进行中」，本轮不得据此改状态。
- 本机无 Flutter/Dart SDK，Dart 侧结果一律只能由
  `.github/workflows/flutter-dev-checks.yml` 产出；本文件不记录任何未实际
  执行过的 Dart 测试结论。

## 1. 结论摘要

| 组 | 审查问题 | 本轮处置 |
|---|---|---|
| RC3-05/07 | 写通道 poison 作用域绑到包装对象，重建 wrapper 即可洗白 | 链路身份对象（`BluetoothService.otaLinkIdentity`）+ `OtaBleChannel.linkIdentity` 快照；`Expando` 键改为链路身份 |
| RC3-04/08 | owner fencing：probe/后台复核/断开收尾的迟到动作 | `aborted()` 在每个 await 后复核代次；probe 绑定后复核并当场释放；断开收尾按发起代次设防 |
| RC3-04/05 | 取消清理与后来者同资产写盘竞争 | `stillOwns` 归属判定下沉到 downloader，在**删除边界**复核；`_deleteIfOwned`/`invalidatePartial` 同步收敛 |
| RC3-02/05 | 取消可落在「在途 future 可见、令牌尚未登记」的窗口被静默吞掉；慢退出时清理被放弃 | 令牌与在途登记同一同步段；`abortIfCancelled` 检查点；等待超时改为 `pendingCancelCleanup` 延后清理，由 `cancelUpgrade` 在 owner 退出后收口 |
| RC3-12 | 取消文案/phase 抢在包清理之前发布 | 传输 catch 不再发布取消态；终态与文案在 `cancelUpgrade` 的包清理之后同段赋值 |
| RC3-10 | 刷新标志复位用例空转 | 重建前置响应序列，使稳定拒绝分支进入时标志**真实为 true**，再由后续普通失败鉴别复位 |
| RC3-02（runner） | 迁移证据收集失败不 fail-closed，豁免判据只比路径 | 收集失败（`git show`/`git diff` 非零、路径非普通文件）直接抛错；豁免判据要求同阶段、字段完整、`effective_blob` 与当前观测一致 |
| RC3-11 | 停滞源 fake 无法观测上游终止 | 已改为可取消的 `StreamController`（`onCancel` → `stalledSourceClosed`），两条用例分别断言「取消请求到达 adapter」与「源头订阅被取消」 |

## 2. 需要纠正的审查前提

1. **RC3-12「更早的 cancelled phase 写入」不成立**：全仓库唯一
   `_phase.value = OtaPhase.cancelled` 就在 `cancelUpgrade` 的配对发布处
   （`ota_service.dart:1105`），并非「早于清理的既有写入」。真正的残留是
   **取消文案**（`upgradeStatus`）在传输 catch 里被提前发布——进度卡的 `Obx`
   直接读 `upgradeStatus`，文案先到就等于「已取消且包已处置」提前成立。本轮
   按此纠正后的前提整改，未为了迎合审查去制造不可达状态。
2. **RC3-10 原用例的鉴别力声明为假**：原序列的第二条响应是稳定拒绝码，而
   外层自动刷新路径在刷新**前**就已把刷新标志清成 false，于是稳定拒绝分支
   里的 `_needsFreshManifest = false` 在该序列下**删掉也不会变红**。修正为
   四条响应：可重试码 → 外层刷新后再次可重试码（让调用结束时标志真实残留
   true）→ 稳定拒绝（被测行）→ 普通失败（鉴别点）。
3. **RC3-11 不是产品缺陷**：产品侧 attempt token 与空闲超时已把取消送到 Dio
   的真实取消路径；缺的是 fake 的观测能力。本轮只核对 fake 与断言，未改产品。

## 3. runner 迁移证据 fail-closed 的实现口径

- `bind_toolchain_regen`：`git show`/`git diff` 非零退出、或白名单路径在检出
  中不是普通文件，一律 `raise ValueError`。字段不再有 `None` 分支——收集失败
  必须显式失败，而不是留下一条「已绑定」的残骸。异常经 `main` 的
  `(OSError, ValueError, SubprocessError)` 兜底返回 1，CI 步骤红。
- 记录新增 `effective_blob`（本阶段 `worktree_fingerprints` 的工作树指纹），
  使豁免判据能证明「这条证据描述的正是被判定的那份输入」。
- `deltas_are_bound_toolchain_regen(source, current, bound, stage)`：除白名单与
  发生漂移外，还要求该路径存在**属于本阶段**、`committed_sha256`/`diff` 非空、
  `effective_blob` 等于 `current` 观测的记录。路径出现过不再构成证据。
- 文档口径（`docs/flutter-development-validation.md` 第 166/179 行仍写「必须是
  提交输入」「不重写已跟踪 Gradle/app 配置」）与本轮的「记录式迁移」不一致，
  属需主会话协调的治理层对齐；该文件当前带有其他认领人的未提交改动，本轮
  **未**改动它。

## 4. 本轮自测

- 宿主回归（可本地执行）：`python -m unittest -v tests.ota.test_flutter_dev_checks`
  → `Ran 50 tests ... OK`（含新增的
  `test_bind_toolchain_regen_fails_closed_on_collection_failure`、
  `test_bound_regen_exemption_requires_complete_current_evidence`）。
- Dart 静态分析与测试：本机无 SDK，**NOT_RUN**；以 CI 双宿主结果为准，
  结论记录在交付报告的运行链接与原始日志中。

## 5. 已知遗留

- 上节文档口径对齐（治理层，需主会话串行窗口）。
- RC3-11 的「真实 IOAdapter 终止」仍由 fake 同构证明，不是真实 Dio 适配器的
  运行时证据；产品侧未改，属证据强度说明而非新缺陷。

## 6. 首轮双宿主回归（run 34480053998，SHA 94bf3bd）与整改

结论：**红**。两宿主均在 `Analyze, test and optionally build a debug APK` 步骤
失败（analyze exit=1、tests exit=1；Linux APK 因此 NOT_RUN）。根因四项，全部
是本批自身引入，逐条整改：

| # | 现象（原始日志） | 根因 | 处置 |
|---|---|---|---|
| 1 | Ubuntu/Windows `tests`：`Expected: OtaPhase:<OtaPhase.cancelled>` / `Actual: OtaPhase:<OtaPhase.failed>`，3 条后台恢复复核用例 | 本批把 `startOtaUpgrade` 传输 catch 的**非用户取消**分支由 `cancelled` 改成 `failed`，属超出审查范围的语义改动 | 回退该分支为 `cancelled`（`ota_service.dart:953-961`），仅保留 RC3-12 要求的「用户取消分支静默」 |
| 2 | Windows `tests`：`晚到的断开完成不得拆掉新链路资源（RC3-08⑦）` TimeoutException after 30s | 本批新增用例复用同一个未完成的 `disconnectGate` 发起第二次断开，第二次调用停在闸门上原地自锁（用例缺陷，非产品缺陷） | 第二次断开前置空 `fake.disconnectGate`，并用局部 `staleGate` 收尾旧断开 |
| 3 | 两宿主 `analyze`：`test/ota/ota_download_test.dart:1250 unused_local_variable 'emitted'` | 本批改写 `_bodyStream` 后遗留只写不读的计数变量 | 删除声明与自增（观测口径本就是 `deliveredBytes`） |
| 4 | 两宿主 `analyze`：`test/ota/ota_service_upgrade_test.dart:1003 unnecessary_non_null_assertion` | 同一用例上文已有 `!` 完成非空提升 | 去掉多余的 `!` |

关于第 1 项的口径说明：`OtaPhase.cancelled` 的枚举注释写作「用户取消」，但
fail-closed（后台复核失败 → abortBestEffort）沿用的收尾语义历来是 `cancelled`，
且被既有绿用例固化；该路径**不删任何资产**，UI 正是据此保留「开始 BLE 传输」
入口配合 `retryableLater` 终止态的「可重试续传」文案。本批不单方面改变该语义，
仅把审查指出的**用户取消**窗口（文案/phase 抢在清理之前发布）修掉。枚举注释
与 fail-closed 语义的措辞差异记在此处备查，不在本批范围内改。

第 2 项的用例缺陷本身就说明该用例在第一轮没有真正校验过迟到收尾：超时会让
整条用例跳过全部断言。整改后其断言链（两次平台调用、代次不重复前进、新设备
不被清除）才可执行。

自测（本地可执行部分）：`python -m unittest tests.ota.test_flutter_dev_checks`
→ `Ran 50 tests ... OK`。Dart 侧仍为 NOT_RUN（本机无 SDK），以第二轮双宿主
CI 为准。

## 7. 第二轮双宿主回归（run 34483261169，SHA bbe27dd）——开发自测通过

运行：<https://github.com/Eitan-S-23/E-Track/actions/runs/34483261169>
attempt 1，headSha `bbe27ddc28e28ffd5d4240c4dc952a8d15d733c7`，整体
`completed / success`；两宿主 `Analyze, test and optionally build a debug APK`
步骤均 success（退出码 0）。

| 项 | ubuntu-latest | windows-2022 |
|---|---|---|
| 静态分析 | `No issues found!`（15.0s，退出码 0） | `No issues found!`（17.1s，退出码 0） |
| 测试 | `+275 ~7: All tests passed!`（273 通过用例 + 7 条 Windows 专属 skip） | `+282: All tests passed!`（Windows 专属用例在此执行） |
| scope | `all`（分支前缀 `dev/flutter/apk/` 强制） | `all` |
| pubspec.lock sha256 | `95ba37036efedb9df8de68ee83ba643b5ad9753ec3adbcd3a03bf3ff6e2325ea`（run 前后不变） | `ed54e10209a46f0ed9673245d6d400427db886d08f4bcae04c0e5d26ddb5e0fd`（run 前后不变） |
| 调试 APK | 已构建：`trace-dev-debug.apk` | `NOT_REQUESTED`（Windows 不构建 APK） |

SDK 身份（`sdk_version.log`）：Flutter `3.47.3` stable，frameworkRevision
`e8113bf45620cbeb8aff64947ee4c93e16adb4cf`，engineRevision
`06a2e2a110089dff50fe635cffd2a61e1b24fbcd`，dartSdkVersion `3.13.3`。

调试 APK（开发用，非发布）：`131464330` 字节，SHA-256
`22f311282a6f72706afeb05ca19cea09754a2b28999a525fa8be2736e3cca453`，
`release_signing: false`；`apksigner verify --verbose` 结果
`Verified using v2 scheme (APK Signature Scheme v2): true`、`Number of signers: 1`。
构建期告警均为非阻断的版本升级提示（Gradle 8.14.0 / AGP 8.11.1 / Kotlin
2.2.20 即将停止支持、7 个插件要求 compileSdk 36、sdkmanager 弃用提示），
无构建错误。

**本轮 runner 新判据在 CI 实跑**（RC3-02 fail-closed 与豁免证据完整性）：
两宿主 `toolchain_regen` 记录均带 `committed_sha256` / `effective_sha256` /
`effective_blob` / `diff`，`source_deltas_bound_toolchain_regen = true`
（Linux 记在 `before_apk` 阶段，Windows 记在 `after_run`）；Windows 的
`windows/flutter/generated_plugin_registrant.h` 只有行尾差异，落在
`dirty_eol_only` 而未计入语义脏。

首轮红证据保留在 `.cache-ci/batch8-run-34480053998/`（`failed.log` 与两宿主
`analyze`/`tests` 原始日志、`result.json`），未清理、未改写。

**结论口径**：以上是**开发自测**结果（`evidence_kind:
development-self-test`、`formal_acceptance: NOT_RUN`），不是独立验收；任务卡
状态与 §10 会话日志由主会话回写。


