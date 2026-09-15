# P3-3 v8 独立验收报告（2026-09-15）

## 1. 结论

**本轮结果：EVIDENCE_GAP。四项 PASS；两条 OTA 补测闭环的旧证据缺口已关闭。**

| 判据 | 本轮结果 | 核心事实 |
| --- | --- | --- |
| C-DEV-CHECKS | PASS | 新实现双宿主 strict analyze 与全部适用测试通过 |
| C-RELEASE-BUILD | PASS | release APK / Windows 完整运行包有效，构建及端点身份闭合 |
| C-APK-INSTALL | EVIDENCE_GAP | 新包安装、实物和证书全部符合；旧包被卸载的操作来源待用户确认 |
| C-TOY-LOOP | PASS | 30203 → 30204；六状态及原升级调用 completed 有效 |
| C-REAL-LOOP | PASS | 30204 → 30205；六状态及原升级调用 completed 有效 |

这不是要求再补测，也不是判定固件或新 APK 安装失败。唯一待决事实为 §2：
旧 `.p33acceptance` 的卸载是否为用户手动操作。不能把本次两条闭环重新退回
“没有 ACK_END / App 完成证据”；这些证据现已存在且通过独立核验。

验收人：Codex 独立非实现会话；未参与 P3-3 产品实现。没有提交、推送、合并、
登记新的 bundle_commit 或宣告整卡收口；不覆盖实现认领人。看板按本次只读边界未改。

## 2. 唯一待决事实 E01

- 新受验包 `com.wen.gaia.gaia.p33verify` 正常在装：
  versionCode=86，versionName=1.0.60，lastUpdateTime=2026-09-15 11:36:08。
  CI 下载件、本地受验件及本轮手机 pull 回件均为
  46,699,140B / SHA-256
  `85ce64dfe7952e3de215a8bf38af5a0766122b6da2bc6aa002bca92f7b6223e9`。
- 双侧 apksigner 证书均为
  `6f51a6a64e21b50b0d7cace2fdf0ca4b978fbdff1814d7bbab90fad08832e658`。
- 生产包 `com.wen.gaia.gaia` 仍为 86/1.0.60，
  lastUpdateTime=2026-07-10 19:05:06，与历史锚点一致。
- **旧包不是“原样保留”**：
  `CMD-PREVIOUS-INSTALL` 退出码虽为 0，实际输出为
  `Unable to find package: com.wen.gaia.gaia.p33acceptance`。
  不能以命令退出码 0 冒充包仍存在。
- 原始 toy 全量 logcat 第 184822 行：
  `09-15 11:35:31.067 ... Package removed ... com.wen.gaia.gaia.p33acceptance`；
  第 184861 行：11:35:32.305 `doRemovePackageData`。
  卸载发生在新包安装及两轮补测之前，不是此次独立验收造成。
  原始摘录、行号和整份日志 SHA 已存
  `evidence/old-package-removal-context.json`。

移交文档及获批补测操作单声明旧包不卸载、不清数据，故此处存在事实冲突。
现有日志尚不能确定操作人，**不推定实现 agent 越权，也不捏造用户授权**。
本轮已向用户提出一次具体问题：是否由用户手动卸载、在补测前还是补测后；
报告写入时尚未取得回答。

最小后续：补这一项操作事实/授权来源并由独立验收会话裁定。
若是用户自主卸载，应将其与 agent 操作边界区分，按真实来源处理；
若不是，则核查实现侧操作记录。**不需要新 APK、CI、OTA、J-Link、回退或烧录。**
本轮保留四项 PASS，后续按实际 v8 终态矩阵生成最小复核计划，不能全套重来。

## 3. 冻结、授权和执行

活动 worktree：
`D:\github\my\E-Track\.cache\worktrees\p3-3-admission`。

- 合同：`docs/acceptance-contracts/P3-3-v8.contract.json`，FROZEN。
- 合同 SHA-256：
  `D739C5BCF5C65D6FCC5E3BA38A616F018C45343C48A65E6267C63F878837FE4F`。
- freeze_commit：`ceaf8d2b7bb8e78968462af51a57ff1250731b61`。
- freeze_tree：`4fd600a48a25654fe82db3cb6fd6f6338392bc48`。
- profile_config_blob：`3769369d053aad028b67d7e2c17b5827b2b96f55`。
- App/构建提交：`253f15371f2a0aeef0e7c5feb10af3118494c9e1`。
  冻结点必须用 ceaf8d2，而不能忽略其新增的服务 fixture 配置。
- 轮次：`P3-3-V8-ACCEPTANCE-20260915-R1`。
- 用户本线程的“请验收”为本次 v8 绑定及只读独立复核授权；
  不含提交推送或新增设备操作。冻结时间不倒签，不宣称补测执行前已有 v8。
  原补测来自获批的 `P3-3-evidence-recovery-2026-09-15.md` §4 操作单。
- v7 合同/终态矩阵/报告均原样保留；v7 真实结果仍为 EVIDENCE_GAP。
  矩阵 SHA=`646613539c4905a89948e91803251e69066ca1528bca830d1938b303649c2eca`，
  报告 SHA=`1963f9862713bf1bcf50598f4be6f594901258164afc003151454d2bbebfda40`。

执行前 FROZEN + NOT_RUN 校验：**VALIDATION=PASS**。
以实际 v7 前驱生成 rerun plan：5 项需要复核，0 项可 REUSED。
本轮 20 条冻结命令各执行一次，均退出 0；E01 证明退出码本身不是验收结论。
命令原文、起止时间、退出码和 stdout/stderr 均在
`P3-3-v8/evidence/commands/`。

阶段为输入/路径预检 → 新 CI 及实物只读复核 → 补测原始证据审查 → 封包。
本轮新增 CI=0、OTA=0、J-Link=0、部署=0、安装/卸载/清数据=0。
原补测升级配额已用 2/2，本轮没有借用或重置任何历史配额。

准备矩阵时第一次检查因 contract_sha256 小写与校验器的大写精确比较失败；
仅修正尚未执行的 NOT_RUN 矩阵绑定大小写，合同字节未变，随后前检通过。
失败原始输出保存在 `evidence/matrix-preflight-case-error.json`，
不冒充产品失败，也没有因此重跑产品观测。

最终校验：**VALIDATION=PASS**，输出为
`VALIDATION=PASS contract=P3-3-v8 round=P3-3-V8-ACCEPTANCE-20260915-R1 overall=EVIDENCE_GAP`。
原始命令记录在 `evidence/final-validation.json`。校验器通过表示包结构、Git 冻结链、
前驱、实物哈希及结果记录有效，不把 EVIDENCE_GAP 变成产品 PASS。

复校命令（在本 worktree，或未来保留本冻结输入的 bundle 提交上执行）：

    python -X utf8 -B -S Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-3-v8.contract.json --matrix docs/acceptance-contracts/P3-3-v8/P3-3-v8.evidence-matrix.json --repo-root . --previous-contract docs/acceptance-contracts/P3-3-v7.contract.json --previous-matrix docs/acceptance-contracts/P3-3-v7/P3-3-v7.evidence-matrix.json

## 4. CI 和安装实物

开发 run：https://github.com/Eitan-S-23/E-Track/actions/runs/34922411533
为 253f153 的 push run。两个宿主均 `No issues found!`；
Windows `+331 All tests passed!`，Ubuntu `+324 ~7 All tests passed!`。
7 项为平台专属 skip，Windows 对应覆盖；scope=all。
成功闭环中两个新增打点断言及已有 ACK 畸形、摘要不符、超时等负例均有实际测试日志。
不能将开发记录本身的 PASS 字段当独立验收，本轮核对了原始日志及执行记录。

SDK 再生文件差异已绑定到 runner 输出；Windows 收尾仅 generated header 的 EOL-only
差异，无语义脏文件。253f153 至 ceaf8d2 的 App、测试、工作流、开发 runner
`git diff` 为零。服务配置变化未从 loop 的 Validation 依赖中漏掉。

构建 run：https://github.com/Eitan-S-23/E-Track/actions/runs/34923921739
为同提交的 build-only dispatch。Android/Windows success，Pages/Release skipped。
本轮重新下载既有产物，不重新构建。
APK 两 ABI 的 `libapp.so` 均含本次隧道 latest URL 和两个新增观测打点。
aapt 实测包名/版本与 §2 全等。

Windows ZIP：
20,353,958B /
`b1fa08b1a8caae97494be18c1ff5ad4c7dc6166a7e0254d78d593c1cce8ded97`。
包含 ble_monitor.exe、flutter_windows.dll、插件 DLL、data/icudtl.dat、
flutter_assets 及 BLEServer.exe。本轮没有启动 Windows GUI，不把裸 EXE 当运行包。

原构建日志按明确 Warning/DeprecationWarning 行提取共 24 行，
主要为 SDK/Gradle/AGP/Kotlin 及依赖弃用提示，保存在
`evidence/build-warning-lines.txt`；不是 analyzer issue，不声称“零警告”。
两次离线解包各出现一次已批准开发样例密钥提示；
受验 APK 使用 CI debug 证书，本报告不授予生产发布/签名资格。

## 5. 两轮六状态的独立裁定

完整 raw SHA 与 ETU 身份：

| 项 | toy | real |
| --- | --- | --- |
| 目标 | 3.2.4 / 30204 | 3.2.5 / 30205 |
| raw SHA-256 | `43faf0cac092f54d862a4266e661fbf739db973a224180744d85c0169ff3fc13` | `ab8528ecb8c4bc756dc2d12fddeb2eb454fa3c91472129f1881edecdff2bcfb4` |
| ETU SHA-256 | `81a773363711adff31cd788217ba18445b462e675042682bdd22302123f0228b` | `32577aa5d0d98cab071440b455151bcc536f33a9a9d930e832f8bb140a607d77` |
| ETU 大小 | 284,581B | 284,590B |

两镜像均为 603,764B，保留相同 GCC 功能本体；
对原 GCC pre-finalize 文件的 78 字节差异均限于 0x400..0x45f 头区。
独立 `etu_unpack.py --verify-fw-header` 和 `cmp` 均通过：
外层 CRC、密文 CRC、fw_header CRC、双零 SHA 及解包 raw 字节一致。

| 状态 | toy 观测 | real 观测 | 采信依据 |
| --- | --- | --- | --- |
| 会话起点/目标 | 11:37:36.512，30203 + 完整 raw → toy30204 | 13:41:13.459，30204 + toy完整 raw → real30205 | 服务原始请求、active fixture、实际资产及 App 强制身份复核 |
| App 整包校验 | 11:38:02.768 BUDGET_START | 13:41:22.794 BUDGET_START | service:843-858 对同一传输字节的长度/SHA 检查失败必 return；其后才调用 transfer |
| durable 达 total | 70 次递进，末值 284581 | 70 次递进，末值 284590 | MCU ACK 驱动的 durable 记录，不拿 GATT sent 代替 |
| 本会话 ACK_END/OK | 11:42:22.685，durable284581 | 13:45:29.078，durable284590 | END 等待者按 cmd/session/seq 关联；结合后续 ack.isOk 门禁及原调用成功 |
| 自然重启 | RTT BLEACT reset / TEST_BOOT confirmed30204 | RTT BLEACT reset / TEST_BOOT confirmed30205 | 实际设备输出，与 App 断连/复核时间窗一致 |
| 新连接 GET_INFO 双值全等且 completed | 11:43:25.529 REBOOT_VERIFIED | 13:46:32.251 REBOOT_VERIFIED | 主动断旧连接后新建 transport 读 INFO；完整 vcode/raw SHA 比对通过的唯一成功分支 |

`MONO_END_ACK_OK` 本身可能在部分非 OK 状态下打印，因此**不单独采信其名字**。
`OtaAckResult.fromAck` 保留真实 status；service:925-935 对 !ack.isOk 必失败返回，
不能到达 :970 的 REBOOT_VERIFIED。:1695-1698 又要求新 INFO 的版本和完整 raw SHA
与目标全等。:974-977 才置 completed 并返回 true。两个补测轮均仅一次开始/END/成功
打点，PID 24733 和单调时钟连续；该组合排除了旧轮“ACK 丢失后手动查询”的反例。

32,087,068B toy 全量日志 SHA=`d31d49688d5e2176305da7f6579f8fa3836fe4b95b6fec7eb7656fa7146d6c00`；
17,964,197B real 全量日志 SHA=`6a8d7d5f8c118e4a52df99ef3317a7a7cb771226ec8c6a9fcff78359625a507b`。
79/77 行决定性原文全部能在对应全量日志找到；无缺行替换。
PID 到新包及其 base.apk 路径的原始记录也已归档，不只按进程号猜测身份。

成功截图已实际查看。两轮原升级调用的直接成功标记、受验代码强制路径、
RTT 及实物共同闭合，不靠人证或“日志没报错”推定。

## 6. 非阻断勘误与边界

- 原资产报告把双零摘要写成 `8a823a70...` 且 real 写“同左”，不符实物。
  正确 toy 为 `a30d8802e69efe4ec729ac045bde3f614ee88ac23d49028a19c2a505946dd88b`；
  real 为 `5bb216a64dfab6a4bc317598811372a351ab292e1ddb018b54a9646e8e9340da`。
  头内值与独立复算全等，v8 绑定正确值，旧报告不篡改。
- real 原件截图实际显示“设备身份已确认 / 固件 v3.2.5”和
  “固件升级完成 / vcode30205”；成功卡版本名为 `--`。
  未显示交付表所称“3.2.4→3.2.5 / 5分11秒”，不以其作耗时证据。
  本轮不扩大为未列入冻结门禁的 UI 改造；完整终点版本/SHA 由上节证据证明。
- BUDGET_START 至 REBOOT_VERIFIED：toy 322.762s，real 309.456s；
  END 至目标复核分别 62.845s / 63.173s。仅为优化基线。
  BLE 速度、后台/锁屏支持及通知按用户裁定不作本轮缺陷或扣分依据。
- 服务/隧道只消费原始落盘日志，无重新部署、账号登录或 token 读取。
  P4-2 后台发布链仍不在本轮结论内。

## 7. 写入与收尾审计

本轮使用 cmd.exe；临时文件、日志、GH 下载、Java/ADB/Python 可控输出
均收敛到此 worktree 内 `.cache/p3-3-v8-acceptance/` 和
`docs/acceptance-contracts/P3-3-v8/`，报告位于 `docs/ota-exec-notes/`。
写前检查规范化路径和父链，拒绝 reparse point；未修改产品源码、冻结契约或旧证据。

本轮只读手机预检启动过原本未运行的 ADB server，手机取证完成后已清理本次 server。
收尾 tasklist 与 netstat 退出 0：
无 adb/J-Link/RTT logger/cloudflared/python 残留，8443/5037 无连接/监听。
本机原默认 adbkey 的时间仍为 2022-02-21；系统临时 adb.log
修改时间 2026-09-15 13:57:19 早于本轮，不曾由本轮覆盖或清理。
Node 外部 compile cache/startup 注入未启用；没有运行 PowerShell。

审计原件：`evidence/cleanup-and-write-audit.json`。
v7 未提交终态产物继续原样保留；本轮 v8 产物同样未提交。
未经用户确认，不执行 git 提交/push/merge 或虚填冻结索引。
