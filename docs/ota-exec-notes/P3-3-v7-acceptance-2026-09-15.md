# P3-3 v7 独立验收报告（2026-09-15）

## 1. 本轮结论

**总体：EVIDENCE_GAP，未通过；未判定当前产品发生故障。**

验收人：Codex 独立验收会话。轮次：`P3-3-V7-FREEZE-20260915-R1`。
本轮为 v6 EVIDENCE_GAP 的正式后继复验，不是新的实现自测。

| 判据 | 独立结论 | 摘要 |
| --- | --- | --- |
| C-DEV-CHECKS | PASS | 两轮四个宿主 job 成功，原始 analyze/test 日志独立核对完成。 |
| C-RELEASE-BUILD | PASS | 第六轮 APK 来源、release 构建、包名、签名及 Windows 完整运行包核对完成。 |
| C-APK-INSTALL | ENV_BLOCKED | 指定手机未出现在 ADB 列表，不能完成在装 APK 拉取及双侧签名比对。 |
| C-TOY-LOOP | EVIDENCE_GAP | 设备端新版本/哈希/CONFIRMED 有证据；提交的推导仍不能证明完整六状态。 |
| C-REAL-LOOP | EVIDENCE_GAP | 30203 身份绑定已一致；原始终点记录不能独自补足 App 侧 ACK_END 和原会话复核证据。 |

矩阵使用执行合同 §4 的 schema：两个 PASS，两个 FAIL/failure_owner=evidence；
手机因前检未通过、没有执行合同命令，记录 NOT_OBSERVED，notes 明示 ENV_BLOCKED。
没有给未执行的手机命令伪填退出码。两个闭环的 observed=null 表示完整 gate
尚无充分观测，不以预填 expected 数组或零退出码冒充通过。

## 2. 上轮整改复核

- G01 已解决：五条命令已变为明确的只读取证形式。四条可执行命令均按冻结原文
  独立运行一次并退出 0；手机命令经过工具/路径处理预检，但受设备未连接阻断。
  不再以 dispatch、占位符或中文说明冒充实际命令。
- G02 已解决：v7 真包 fingerprint、外部证据及实物均绑定 30203；
  服务文档明确记录 r5/v6 与 r4/v5 历史归属，不再混用 30202 真包为当前目标。
- ART-DEV-LOGS 已改成实际 JSON 文件，并绑定四份宿主原始 analyze/test 日志。
- v6 报告与终态矩阵保持原字节，未恢复为 NOT_RUN，未改写历史结论。
- 本轮没有要求再次构建 APK、恢复 BCB、部署服务或重跑 OTA。

## 3. 已通过判据的证据

### C-DEV-CHECKS

独立调用冻结 CMD-DEV-CHECKS，并从 GitHub 下载原始 job 输出以及四份
development-log artifact，不仅查看 success 字段。

| run | 提交 | Windows | Ubuntu |
| --- | --- | --- | --- |
| 34861159023 | ce301906736d7b4209a09ad7e42ce080fb7a19a6 | 331 passed | 324 passed、7 skipped |
| 34869549756 | 0fb167cf4c44a6e4741e5a42fcd4945cf29f7780 | 331 passed | 324 passed、7 skipped |

四份 analyze 日志均为 `No issues found!`，实际 analyze/test 命令退出码均为 0，
scope=all，没有 continue-on-error 或失败降级。
Ubuntu 跳过的 7 项明确为 Windows 对象发现/断开分支，对应 Windows 实际执行，
不是遗漏全部宿主都未覆盖的用例。

SDK 自动再生的 analysis_options/插件注册/Gradle 配置差异有有效字节哈希及 diff，
已对照冻结的 `Tools/flutter/dev_checks.py` 再生绑定逻辑复核。
恢复后语义脏文件为空；Windows 残留项仅为 generated_plugin_registrant.h 的 EOL 差异，
没有将生成差异隐瞒为“构建输入完全未动”。

主索引：`evidence/dev-checks/dev-checks-runs.json`；
原始目录：`evidence/dev-checks/<run>-<host>/`；
详细命令和哈希：`evidence/acceptance-20260915/dev-log-artifacts.json`。

### C-RELEASE-BUILD

run `34864052541` 的 Android/Windows release 构建均 success，
Pages/Release 均 skipped。真实 head 为 ce30190，系 freeze_commit 0fb167c 的直接父提交；
既有 App 构建输入等价论证及零差异已复核。未重新 dispatch。

- APK：46699144B，SHA-256
  `fb6a91e69a0ad30dc0b9c79a69c5e638d376898d6e313836191f2b40ebf80a13`。
- Android 原始 artifact ZIP：25509009B，SHA-256
  `0edf01eec20a1bb1af9d30b8259b2a8f915207cbaa20db86e340b9ea8e5baf1a`，
  与 GitHub API digest 一致；ZIP 内 APK 与受验实物哈希一致。
- aapt：`com.wen.gaia.gaia.p33acceptance`，versionCode=86，versionName=1.0.60。
- apksigner verify 退出 0；第六轮证书 SHA-256：
  `f6c0f2247c5054fd5b9e0c2792db8edb8bf694776b9a29cb5b83cace30cdf44d`。
  这是 release 模式的 Android Debug 签名基准，不冒充固定生产签名验证。
- Windows 完整运行 ZIP：20353729B，SHA-256
  `a354f7354ee379433940fc0e6e851735a8c8306bbc6e1ecd965f84b10e332312`；
  26 个条目，CRC 检查通过，含 ble_monitor.exe、Flutter DLL、插件、BLEServer、
  data/icudtl.dat 和 flutter_assets，不是裸 EXE。没有启动 Windows GUI。
- 构建日志有 24 条 warning/deprecation 诊断行，计数规则和逐行内容在
  inspection-summary.json。主要为 Gradle/AGP/Kotlin 兼容提醒、SDK 36 插件要求、
  Actions Node 弃用提醒；不隐瞒为零告警，也不新增合同外“零告警”门禁。

构建、元数据、官方 artifact digest、aapt 和归档检查原始证据已入包；
两个 release 实物已放在合同指定 artifacts 路径。

## 4. 仍未通过的事项

### E01：完整闭环推导不具有排他性

影响 C-TOY-LOOP / C-REAL-LOOP；结论 EVIDENCE_GAP。

本轮并非因为“没有重新上板”拒绝，而是审查了 v7 提交的具体推导。
其关键前提“BCB 提交/复位仅在 ACK_END 成功后发生”不足以证明手机已收到成功 ACK：

1. 冻结 `Libraries/OTA/ota_ble_session.c:79` 以
   `(void)session->env.send(...)` 忽略发送返回值。
2. 同文件 `:700` 调用 ACK_END/OK 的发送函数后，
   `:711` 继续 activate_staged，`:720` 可以 system_reset；
   没有以发送成功或手机收到 ACK 作为后续分支条件。
3. `app/bluetooth_flutter_Trace/lib/services/ota_service.dart:303` 的
   readDeviceInfo 是独立入口，`:340` GET_INFO 后 `:343` 更新身份，
   随后可以检查 latest，不要求该身份来自原升级调用的成功返回。
4. 因此“ACK 未被 App 确认、设备仍成功升级，之后单独重新读取身份并查询 latest”
   与已有终点日志相容。现有日志不能排除此路径，不能据此填满原升级会话六状态。

上述是**静态可达反例，不是本轮实测到 ACK 丢失，更不是认定产品真的升级失败**。
源文件由 freeze_commit 的 Git blob 直接读取，摘录、行号、blob/SHA 在
`evidence/acceptance-20260915/loop-inference-source.json`。

已接受的积极事实仍保留：

- toy 原始 latest 三次为 30201 和完整
  `aeafc96e77d372aea1e893a979f2368ba9176c4999a61090ceb2956cd4085298`，
  首条 21:40:15.699；RTT 两处 CONFIRMED 30201。目标镜像和 ETU 哈希一致。
- real 三次 latest（00:06:05.449、00:06:08.608、00:07:22.431）为 30203 和完整
  `3a2827683cbd2b557dd5d441927d1a490b3b28fe11f8d7a4b4b5c86a594144a3`；
  ETU 284608B/`a543f952dcd1b0f57770669e253b29e9a93b7ffb94263bc7bdc3b1bdf4ef1915`
  与 v7 fingerprint 一致。
- toy 的代码演进范围论证成立：显示/布局和重启复核窗口变动，不是重写传输核心。
  但范围论证不能补出缺失的原会话观测。
- 用户实测成功反馈保留，不被本报告否定。HTTP 终点和代码推导有支持价值，
  但不能单独当作完整 App/BLE 状态链。

处置优先级：先找回并绑定既有 App/BLE 原始记录或能够排除此反例的证据，
不要再仅重写一段“由终点推导全部成功”的说明。若现存证据确已不可恢复，
必须由用户决定是否授权定向补测，并明确目标资产、端点、设备操作及配额。
本轮没有授权或执行回退、补刷、注错或新 OTA，也不要求整卡全量重做。

### E02：指定手机未接入，安装身份判据环境阻断

既有 adb 位于 `D:/install/leidian/LDPlayer4/adb.exe`，版本 1.0.41/34.0.4。
命令的 CR 去除操作已用含 r 字符及 CRLF 的本地样本检查，路径处理正确。

两次只读查询已有 ADB server 的 `host:devices-l` 均没有
`10ADA4197U001CK`，后一次时间为 UTC 2026-09-14T20:08:27.878061Z，
全部 transport 数量也为 0。已请求用户接回 USB，未重启 server 或改调试设置。

因此本轮没有执行 CMD-APK-INSTALL，没有手机 dumpsys/pull/logcat 输出，
无法证明在装包与第六轮 APK 一致，也无法补齐生产包当前状态确认。
第五轮在装回件不用于替代第六轮。缺口来源是设备未连接，不是需要重复申请安装权限。

## 5. 冻结、复验与操作账目

- v7 合同 SHA-256：
  `38279b9fc9f2ebb7e6c18831ff4d8a0ddd719bed1ebdf4cafb637fe68d721b9b`。
- freeze_commit / tree / profile：
  `0fb167cf4c44a6e4741e5a42fcd4945cf29f7780` /
  `b3d1d311645d584c48419b546a061c5648da740f` /
  `3769369d053aad028b67d7e2c17b5827b2b96f55`。
- 执行 HEAD：`7b5961f74f604bf04307f256b1ac97e85912a833`。
- 实际前轮矩阵 SHA：
  `631b14a0ab3c96d231f714c84b4bec9461645a251b5c07ff943bbee43e2fea7c`。
- 执行前校验携带 v6 前驱，退出码 0，VALIDATION=PASS/overall=NOT_RUN。
- 校验器生成 rerun-plan.json：changed_input_groups=[]，rerun=5、reusable=0；
  原因是前轮非 PASS、命令/判据/外部绑定变动，不是要求重新构建或上板。
- 四条冻结只读命令实际各执行一次、退出 0；手机命令未执行。
  详细原文/时点/stdout/stderr 见同名 CMD-*.json。
- 没有 REUSED，矩阵三项 rerun 绑定字段保持 null，但计划生成与最终校验仍携带前驱。

最终校验已执行（UTC 2026-09-14T20:29:24.025Z 起，退出码 0）：

    VALIDATION=PASS contract=P3-3-v7 round=P3-3-V7-FREEZE-20260915-R1 overall=EVIDENCE_GAP

执行前与最终校验均通过，并都携带 v6 前驱。这里的 VALIDATION=PASS
表示本份包含两项 PASS、两项证据失败及手机未观察项的证据包合法，
**不表示总体产品验收 PASS**。原始输出见 final-validation.json。
另行执行 git diff --check，退出码 0、无输出。

统一复校命令：

    python -X utf8 -B -S Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-3-v7.contract.json --matrix docs/acceptance-contracts/P3-3-v7/P3-3-v7.evidence-matrix.json --repo-root . --previous-contract docs/acceptance-contracts/P3-3-v6.contract.json --previous-matrix docs/acceptance-contracts/P3-3-v6/P3-3-v6.evidence-matrix.json

下一轮应以本轮实际矩阵为前驱生成最小计划。若输入未变，本轮已通过的 CI/发布构建
应按规则 REUSED；接回手机不自动要求重建 APK，更不自动授权升级设备。
本轮 E01 尚不能仅靠接回手机消除，手机身份核验与历史闭环证明是不同判据。

## 6. 边界与写入审计

工作树固定为 `D:\github\my\E-Track\.cache\worktrees\p3-3-admission`；所有命令显式指定该目录。
GitHub 登录只读核对为 Eitan-S-23，未输出或落盘 token。
GH/Java/Bash/临时缓存均收敛到项目内 .cache/p3-3-independent-v7-20260915；
未启动本机 PowerShell。证据与产物只写 v7 包内及本报告，未覆盖无关文件。

新增 CI dispatch/build-only/治理 CI、设备写入、J-Link、复位、OTA、
服务/隧道部署及 Cloudflare 账号操作均为 0；没有读写 MCU BCB/App 区。
既有手机 ADB 服务未启动或重启，未安装/卸载/清数据/改权限。
BLE 速度与前台/锁屏限制继续按用户裁定排除，不作失败或退回理由。

冻结合同、v6 报告和矩阵、共享契约与看板未修改；实现认领人未覆盖。
未提交、推送、合并或发布。本报告不宣告任务完成或收口。
