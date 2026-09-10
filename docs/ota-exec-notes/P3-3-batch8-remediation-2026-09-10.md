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
