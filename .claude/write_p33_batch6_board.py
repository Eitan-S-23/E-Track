# -*- coding: utf-8 -*-
"""P3-3 第六批回写：research 追加 §6.15 + 看板 P3-3 卡/§9/§10 字节编辑。

看板为混合行尾（728 CRLF + 299 LF），必须字节手术，禁止 Edit 工具
（会规范化行尾混入上百行伪变更）。research 为纯 LF，做尾部字节追加。
锚点已用 .claude/probe_board_lines.py 证实（行 622/638/791/1027 LF，
#### P3-4 唯一，§9 前缀唯一）。
"""
import hashlib
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = "D:/github/my/E-Track"
RESEARCH = ROOT + "/docs/ota-exec-notes/P3-3-research-flutter-ota.md"
BOARD = ROOT + "/PLAN-OTA-EXEC.md"


def sha256(b):
    return hashlib.sha256(b).hexdigest()


research_old = open(RESEARCH, "rb").read()
board_old = open(BOARD, "rb").read()
r_before = sha256(research_old)
b_before = sha256(board_old)
board_crlf_before = board_old.count(b"\r\n")
assert board_crlf_before == 728, "看板基线 CRLF 行数非 728"

# ---------------------------------------------------------------- research
RESEARCH_ADD = """
### 6.15 RC3 第六批整改交付与开发验证闭环（P3-3-IMPL-20260907，2026-09-09/10）

- 身份： P3-3 实现 agent 开发自测批次（非独立验收，实现者不自验收）
- 分支： dev/flutter/apk/p3-3-batch6（本会话独占验证分支，Eitan-S-23 推送）
- 授权： 执行合同 §7.3.2 + docs/flutter-development-validation.md 持续预授权
- 输入： 本文件 §6.14（第五批复核遗留）+ §6.12/§6.13 历史子项
- 工作流： .github/workflows/flutter-dev-checks.yml（push 自动触发，
  Ubuntu + Windows 双宿主）
- 终态： run 34376805924（commit 6177a8b）completed success——ubuntu
  13 命令全 PASS（sdk_checkout→apk_collect）、windows job success、
  debug APK 首次产出（元数据见 6.15.7）

#### 6.15.1 交付总览

本批共 22 个提交（3c05963..6177a8b，origin/main..HEAD），对应 22 个
CI run（34323219799..34376805924；另有 34346195207 重复触发手动取消）。
前 21 个 run 为 failure，各自驱动一次「日志取证→定位→修复→changed
inputs 重触发」迭代；关键日志收纳于仓库 .cache-ci/run*/（本地证据
副本）。工作分四条线：

1. 产品修复（RC3 清单）：RC3-01 编译准入、RC3-02⑥ 幽灵重发、
   RC3-04 owner epoch、RC3-05 写通道废弃、RC3-06 takeError 双扣、
   RC3-07 恢复点时钟、RC3-08 身份复核 fail closed、RC3-10 下载分类/
   兼容字段、RC3-11 包装流取消、RC3-12 地址漂移作废。
2. 测试保真度：transport 订阅竞态（broadcast 通知语义）、
   waitForChange 孤儿 completer、取消用例 uncaught 时序、fake
   broadcast 化、BEGIN 全丢断言 flaky 修正。
3. analyze 清零：719 issues → 0（轨迹见 6.15.4）。
4. 验证入口：workflow 语法/治理配套/lockfile 对齐、APK 门禁三轮
   加固（6.15.5）、Android 构建链三连升级（6.15.6）。

#### 6.15.2 RC3 逐项处置（原编号保留，已修子项不归零）

「运行证据」列只给该子项的诊断 run；全批终态全绿证据统一见 6.15.7。

| 原 ID | 合同依据 | 本批修改（提交） | 回归用例 | 运行证据 | 源码状态 | 开发验证状态 | 剩余缺口 |
|---|---|---|---|---|---|---|---|
| RC3-01 / P1 | Spec analyze/test/build 编译准入 | 3c05963：download 补 dart:async 导入、测试 crc32Of/fakeDevice* 常量提层；1de5ce2+cfe6b11：15 个 analyze error 清零（闭合链、dio Response 歧义、0x1F、typed_data、const 默认值） | analyze 全包即回归 | run 34331841801 实测 15 error→run 34335992426 起 error=0 | 已提交（分支） | CI analyze PASS（双宿主） | 无 |
| RC3-02 / P1 | 执行合同 §7/§7.3 fail-closed；Spec 服务状态链 | 2975767：发窗/重发循环迭代头 durableOff>=blockEnd 即 break（幽灵重发根除，单字节 46 段/慢 ACK 36 段/credit 三用例同源）；BEGIN 全丢断言改「预算优先于次数、<=3」（Ubuntu 红/Windows 绿 flaky 实证）；3853555：三处 _error ??= 首错保留恢复（见 6.15.3） | 单字节/慢 ACK/credit 窗口用例；MCU 会话超时 teardown 用例 | run 34356078507 tests -3→run 34358386750 tests PASS（打点期）；??= 回归由 run 34365599668 tests -1 抓获 | 已提交 | CI tests PASS | download test:836 只捕获 TimeoutException、upgrade test:599 第三份 401 未消费（§6.14.2 oracle，未动） |
| RC3-03 / P1 | binary §4.4/§4.5/§5；ota_sd_inspect 真值 | d4ae8cd：fake _notifyController 改 broadcast（续传用例二次 listen Bad state）、续传用例先 dispose 旧 transport | retries=0 续传用例 | run 34348433721 双平台失败之一即该 Bad state | 已提交 | CI tests PASS | inspect patch 分支（base_vcode/base_sha8/最小 payload）、非尾短段 1098、重复段内容 1124（未动） |
| RC3-04 / P1 | Spec 单一 owner；CANCEL-RECOVERY | 626c0fa：cancelUpgrade owner epoch 屏障（等待期间后来 owner 进出不越权删包/覆盖终态）、下载资源快照前移至首个 await 前、迟到 bind 产物 dispose | 现有取消/双 start 回归 | 随批 CI tests PASS | 已提交 | CI tests PASS | owner 快照竞态专项负例未新增（§6.14 已指出缺该窗口用例） |
| RC3-05 / P1 | HTTP-RESUME:271；FLUTTER-TRANSPORT:1057；安全帧边界 | 1de5ce2：写通道废弃 _writeChannelPoisoned（分片写超时后出站帧全拒、须重连重建——修 transport:873 超时留半帧后放行 ABORT）；cfe6b11：waitForChange 超时路径注销收尾孤儿 completer；62437a1：取消用例 uncaught 时序（产品无缺陷，测试先同步 abort 再 await 注册 listener） | MTU=23 取消用例 | run 34342123013/34346176030 逐轮诊断 | 已提交 | CI tests PASS | download cancel:482/496 无 inFlight 跳过 partial 清理、正文取消兜底删除、慢写用例 1227 后续 ABORT 验证（未动） |
| RC3-06 / P1 | binary §5.5/§5.6/§5.7 ACK 权威及恢复 | 1de5ce2：takeError 读取即清锁存（防块循环头已处置错误在块尾重复处置、同一错误双扣 resumeLeft——修 §6.14 所指整改回归） | 全量 transport 回归（含块尾锁存错误用例） | run 34331841801 起随批回归 | 已提交 | CI tests PASS | 跨窗负例独立证据不足（§6.14.2 遗留） |
| RC3-07 / P1 | BLE-TUNING/RETRY-POLICY 30s 无 durable 进展 | 1de5ce2：BEGIN 恢复点 durable 前进时重置无进展时钟（修 §6.14 前次遗漏） | 全量 transport 回归 | 随批 CI tests PASS | 已提交 | CI tests PASS | settle 预算耗尽后物理写隔离证明（未动） |
| RC3-08 / P1 | DEVICE-DTO:118；BLE-LIFECYCLE；FLUTTER-TRANSPORT:1058 | 626c0fa：后台恢复设备身份复核失败改 fail closed（终态+尽力 ABORT，不盲发旧包字节到未知设备——修 service:1014 吞错放行） | 现有 upgrade 回归 | 随批 CI tests PASS | 已提交 | CI tests PASS | service:1002 旧 transport、真实连接代次失效、disconnect:1158 封顶、迟到 1268/1275 退订（未动） |
| RC3-09 / P1 | FFF0/FFF2/FFF1 精确发现、真实通知 | 707eae9：transport 改构造内同步显式订阅——async* 生成器初始运行延迟到微任务，真实 BLE broadcast 通知流下同步回投 ACK 整帧丢弃、未启动即 dispose 时 cancel 永不完成（升级测试挂死根因） | bluetooth_adapter_notify_test（真实 win_ble 对象，Windows 分支执行） | windows-2022 job 实测：run 34368114030-windows tests +233 全绿（含 adapter 通知链），此后每轮 PASS | 已提交 | Windows 宿主 CI PASS；真实 BLE 硬件 NOT_RUN | 物理设备验证待授权/环境 |
| RC3-10 / P1 | HTTP-ERROR/UNKNOWN-FIELDS；稳定终止与诊断 | 626c0fa：下载 autoRetryable 对齐 _terminalFromDioError 的 429/503 状态约束（修 service:605）；终态携带 minAppVersionCode/required/actual 兼容上下文（修 service:624 丢字段） | 现有 latest/upgrade 回归 | 随批 CI tests PASS | 已提交 | CI tests PASS | 跨调用残留标志反例（§6.14.3，未动） |
| RC3-11 / P2 | HTTP-RESUME/DOWNLOAD 流关闭、时间边界 | 1de5ce2：读流异常（TimeoutException/receiveTimeout）主动 token.cancel() 后 rethrow——Dio 5.9.0 包装流 onCancel 不回传底层 source，不主动取消则底层连接悬挂（修 download:393）；测试侧 fake adapter 补 Dio cancelFuture 契约、stall 判定移 yield 前消同值竞态 | drain 有界断言、首块停滞用例 | run 34331841801 两个运行时失败为诊断起点 | 已提交 | CI tests PASS | download:332 首次坏 206 不取消上游、655/683 drain/错误体首事件 timeout、stall test:836 非零正文负例（未动） |
| RC3-12 / P2 | UI 确定状态；Spec 同一 DTO 查询链 | 626c0fa：设备地址漂移独立判定（同型号同版本换机、身份字段巧合相同时，旧地址的清单/包/终态仍作废） | 现有身份复核回归 | 随批 CI tests PASS | 已提交 | CI tests PASS | previousInfo=null 失败重读窗口、取消 catch:590/872 早于清理发布、upgrade test:491 断言深度（未动） |

#### 6.15.3 首错保留语义回归事故（b8426b3 引入，3853555 修复）

第五批起 transport 三处 ACK 错误锁存点为首错保留语义（迟到的 ERR ACK
不得覆盖已锁存的 terminal ABORTED）：

    if (_error == null) { _error = _AckError(...); }

第六批早期为定位 RC3-02⑥ 在这些分支加入 [diag] 打点（626c0fa）；
b8426b3 移除打点时把三处误收敛为无条件 `_error = _AckError(...)`，
破坏该语义。实测反例（run 34365599668 ubuntu tests +226 -1）：
rspAckAbort 先锁存 ABORTED → 迟到 DATA ERR ACK 在 onAck 分支覆盖为
ERR_STATE → _classifyAckError 将其分类 resume → ABORT+BEGIN 重试成功
→ 传输误报完成；「MCU 会话超时主动 teardown（RC3-06）」用例
expect(ack.isOk, isFalse) Actual true 抓获。

修复（3853555）：三处恢复 `_error ??=`（恰为 lint
prefer_conditional_assignment 的推荐写法）；run 34367240368 起该用例
双平台转绿。教训：移除诊断代码的「等价改写」必须逐字核对条件语义；
本次回归被第五批补的 RC3-06 teardown 负例守住，fail-closed 负例的
回归价值得到实证。[diag] 打点现已全部移除（grep 零残留）。

#### 6.15.4 CI 反馈链全记录（22 run）

| run | commit | 失败点（日志取证） | 修复 |
|---|---|---|---|
| 34323219799 | 3c05963 | workflow 解析 0 秒失败：steps.shell 拒绝 matrix 上下文（Unrecognized named-value） | 1bff4ae：shell 移 job 级 defaults.run.shell |
| 34327578837 | 1bff4ae | dev-checks 宿主回归 3 项红：Validation profile 未登记 workflow、build.yml analyze 吞错、app AGENTS 缺 standing authorization 段 | ca9c559：携带治理会话已审查的配套文件 |
| 34328633319 | ca9c559 | standing authorization 断言要求看板 §0 规则 8 预授权表述 | f5fbaaf：携带 2026-09-09 授权治理看板回写 |
| 34328985011 | f5fbaaf | dependencies --enforce-lockfile 红：lockfile 自 init 未更新（geolocator/share_plus 缺 17 条目；test_api 等低于 stable 要求） | 95b7943：按 CI resolver 实际输出对齐 lockfile |
| 34331841801 | 95b7943 | analyze 719 issues（含 15 error）+ 2 个运行时测试失败（drain 断言失真/stall 同值竞态） | 1de5ce2：error→0、RC3-05/06/07/11 产品修复、fake Dio 契约 |
| 34335992426 | 1de5ce2 | analyze 剩 562 deprecated/unused 等存量 lint（挡 dev workflow 与生产 analyze 步骤） | 3004bb3：562 处清理（withOpacity→withValues 480 处/26 文件等） |
| 34337630148 | 3004bb3 | 升级测试挂死（transport 订阅竞态）+3 analyze error+剩余 warning | 707eae9：构造内同步显式订阅 |
| 34342123013 | 707eae9 | MTU=23 取消用例 uncaught async error（waitForChange 孤儿 completer） | cfe6b11：超时路径注销并收尾孤儿 completer |
| 34346176030 | cfe6b11 | 取消用例仍 uncaught（Dart uncaught 语义：cancel→fail→completeError 级联无 listener） | 62437a1：先同步 abort 再 await 注册 listener |
| 34348433721 | 62437a1 | 续传用例二次 listen Bad state（fake 单订阅 stream.map 包装） | d4ae8cd：fake broadcast 化+先 dispose 旧 transport |
| 34350778403 | d4ae8cd | 单字节用例 ACK 停投/46 段新 seq 重发（[diag] 定位中） | 626c0fa：service 集中修复+transport 全轨迹打点 |
| 34356078507 | 626c0fa | 打点确认幽灵重发根因（块提交 ACK 清 inFlight+bitmap 覆写 0）；analyze 136、tests -3 | 2975767：发窗/重发循环块完成即停 |
| 34358386750 | 2975767 | analyze 136（存量 lint 挡门禁；tests 已 PASS） | b8426b3：136 清零+[diag] 移除（引入 ??= 回归，见 6.15.3） |
| 34365599668 | b8426b3 | analyze 38（36 const 传播冗余+1 error）；tests -1：RC3-06 teardown（??= 回归） | 3853555：三处 ??= 恢复+36 const 清理 |
| 34367240368 | 3853555 | analyze 1（main_home_page AppBar 非 const 构造） | 878753e：AppBar 内 Text 单独 const |
| 34368114030 | 878753e | ubuntu dev FAIL：apk_prepare NOT_RUN——checkout 字节比较下 pub get 再生 3 文件标脏（windows job 已 PASS） | 6c3fc4b：门禁改语义比较（--ignore-cr-at-eol） |
| 34370203372 | 6c3fc4b | 仍 NOT_RUN：三文件为实质内容差异（dependencies.log 末行 "Upgrading analysis_options.yaml to exclude build and platform directories"） | e7d8410：工具链再生白名单+构建前恢复提交字节 |
| 34371494632 | e7d8410 | apk_build：Gradle 8.12.0 < Flutter stable 最低 8.14.0 | e104022：wrapper 升 8.14 |
| 34372469528 | e104022 | apk_build：AGP 8.9.1 < 最低 8.11.1 | a570f38：AGP 8.11.1 |
| 34373308395 | a570f38 | apk_build：Kotlin 2.1.0 < 最低 2.2.20 | 97f80e4：Kotlin 2.2.20 |
| 34374350155 | 97f80e4 | 13 命令全 PASS 但 development_result=FAIL：收尾 source_unchanged=False（flutter build 期再生 gradle.properties） | 6177a8b：入白名单+收尾恢复+审计快照 |
| 34376805924 | 6177a8b | （无）ubuntu 13 命令全 PASS+windows success+debug APK 产出 | — |

analyze 清零轨迹：719（run 34331841801，含 15 error）→ 562 存量清理
（3004bb3）→ 136（run 34356078507/34358386750）→ 38（run
34365599668）→ 1（run 34367240368）→ 0（run 34368114030 起 PASS）。

#### 6.15.5 dev_checks harness 三轮加固

1. 语义 checkout 比较（6c3fc4b）：checkout_identity 逐条用
   `git diff --quiet --ignore-cr-at-eol`（--cached 与 worktree 两端）
   判定 eol_only；门禁比较 `(head, dirty_semantic)`，porcelain status
   原样保留审计。动机：run 34368114030 的 apk_prepare 因 pub get 改写
   3 个文件标脏被拦，当时怀疑行尾差异。
2. 工具链再生白名单+构建前恢复（e7d8410）：语义比较仍拦（run
   34370203372）——实为实质内容改写而非行尾。新增
   TOOLCHAIN_REGENERATED 白名单（analysis_options.yaml、
   windows/flutter/generated_plugin_registrant.cc/.h、
   generated_plugins.cmake）；apk_prepare 三重条件（起点 clean+head
   未变+语义脏仅白名单）下 git checkout 恢复提交字节后重取再比较。
3. 收尾恢复（6177a8b）：flutter build 期间 "Upgrading
   gradle.properties" 再次再生（run 34374350155：13 命令全 PASS 但
   development_result=FAIL）；gradle.properties 入白名单，收尾同样
   恢复，原始状态留 source_after_pre_restore 审计快照。
   宿主回归 tests/ota/test_flutter_dev_checks.py 37 项全绿（新增 3
   用例：门禁白名单恢复、非白名单仍拦截、构建后恢复审计快照）。

#### 6.15.6 Android 构建链升级

Flutter stable 3.47.2 的最低支持要求逐项撞墙逐项升级，每次以 push
取得真实 apk_build 反馈：Gradle wrapper 8.12→8.14（e104022）→
AGP 8.9.1→8.11.1（a570f38）→ Kotlin 2.1.0→2.2.20（97f80e4），对应
run 34371494632/34372469528/34373308395 的原始报错。遗留：Flutter
对 Gradle 8.14 发出 "support will soon be dropped, please upgrade
to 9.1.0" 弃用警告（非失败），留待后续大版本批次评估。

#### 6.15.7 终态证据（run 34376805924，commit 6177a8b）

- workflow run：34376805924，2026-09-09T16:27:09Z 创建，completed
  success（本地证据副本 .cache-ci/run34376805924-apk/）
- ubuntu job：13 命令全 PASS；analyze 0 issues；tests +227
  All tests passed
- windows-2022 job：success；tests +233 All tests passed（含真实
  win_ble 对象的 adapter 通知链用例）
- result.json：development_result=PASS、apk_result=PASS、
  source_unchanged=true、lockfile_unchanged=true；
  source_after_pre_restore.status='M
  app/bluetooth_flutter_Trace/android/gradle.properties'（构建期
  改写已恢复并留审计）
- APK 产物：GitHub artifact
  flutter-dev-debug-apk-6177a8b70c3aa941fa082be845db756704a70a6d-34376805924-1
  （压缩 75,165,958 bytes，14 天保留期）；apk_collect.log 元数据：
  file=trace-dev-debug.apk、bytes=131,436,066、
  sha256=09c3331adc5dca14a4a531497a026599a464567cd93c04b929d453a717e08e43、
  artifact_kind=development-debug-apk、release_signing=false、
  formal_acceptance=NOT_RUN、
  commit=6177a8b70c3aa941fa082be845db756704a70a6d
- 签名校验（apk_verify.log）：APK Signature Scheme v2 true、
  Number of signers: 1（debug 签名，非发布签名）
- SDK 身份：每 run 重新 clone stable，本轮 Flutter 3.47.2 /
  Dart 3.13.2

#### 6.15.8 本批未处置遗留（沿用 §6.14 编号，后续批次）

- RC3-02：download test:836 先发 1KB 只捕获 TimeoutException 的
  oracle；upgrade test:599 第三份 401 未被消费
- RC3-03：fake inspect patch 分支（base_vcode/base_sha8/最小
  payload）、非尾短段 1098、重复段内容 1124
- RC3-04：owner 快照竞态专项负例未新增
- RC3-05：download cancel:482/496 无 inFlight 跳过 partial 清理、
  正文取消兜底删除、慢写用例 1227 的后续 ABORT 验证
- RC3-06：跨窗负例独立证据
- RC3-07：settle 预算耗尽后物理写隔离证明
- RC3-08：service:1002 旧 transport、真实连接代次失效、disconnect
  封顶、迟到 1268/1275 退订
- RC3-10：跨调用残留标志反例
- RC3-11：download:332 首次坏 206 不取消上游、655/683 drain/错误体
  首事件 timeout、stall test:836 非零正文负例
- RC3-12：previousInfo=null 失败重读窗口、取消 catch:590/872 早于
  清理发布、upgrade test:491 断言深度
- RC3-09：真实 BLE 硬件（物理设备）NOT_RUN，待授权/环境
- Windows EXE 打包验证：本批未请求（dev/flutter/apk/** 只产
  Linux debug APK），卡面 EXE 验证仍 NOT_RUN
- Gradle 9.1.0+ 升级评估（弃用警告）

除 ??= 回归（本批内引入并修复验证，见 6.15.3）外，本批未新增整改
回归。

#### 6.15.9 结论与边界

- 本批首次为 P3-3 取得 Actions 全绿闭环与 debug APK 产物；§6.14
  所列产品侧（lib/ota+service）整改回归与主要 P1 残留中，RC3-01/
  04/06/07/08/10 全部所指子项与 RC3-02⑥/03/05/11/12 部分子项已
  落地并经双宿主 analyze+tests 实测通过。
- 开发自测通过 ≠ 正式验收：flutter-dev-checks 是 §7.3.2 开发验证
  入口，不是验收合同。本报告不填任何 EXECUTED PASS，不创建/冻结
  验收合同；P3-3 保持进行中。
- debug APK 为开发产物（release_signing=false），不可发布/部署；
  本批未安装/卸载 APK、未清设备数据、无任何真机操作。
- 正式验收（含卡面「真机传输 toy 包与真包成功」）仍须非实现独立
  会话按 docs/acceptance-execution-contract.md 执行。

#### 6.15.10 写入审计

本次主动写入：本 research 追加 §6.15（纯 LF 尾部字节追加）与
PLAN-OTA-EXEC.md 四处（P3-3 卡状态行「更新」字段替换、卡内追加
第六批交付记录一行、§9 追加一行、§10 追加一行）。追加/编辑前
research 全文 SHA-256=__R_BEFORE__，看板全文 SHA-256=__B_BEFORE__；
research 追加后历史字节前缀不变；看板 728 个 CRLF 对应行数量不变
（全部新增行 LF，与各插入点邻近行一致），看板编辑用 Python 字节
手术（非 Edit 工具）避免混合行尾被规范化。既有脏文件、未跟踪文件
与历史证据全部保留；未运行历史 .claude 脚本，未清理无关产物，无
项目外写入，未输出密钥。
"""

add_text = RESEARCH_ADD.replace("__R_BEFORE__", r_before).replace("__B_BEFORE__", b_before)
add_bytes = add_text.encode("utf-8")
research_new = research_old + add_bytes
assert research_new[: len(research_old)] == research_old
assert b"\r" not in add_bytes
assert "__R_BEFORE__" not in add_text and "__B_BEFORE__" not in add_text

# ------------------------------------------------------------------ 看板
# 1) P3-3 卡状态行「更新」字段替换（行 622，LF）
OLD_UPD = (
    "更新: 2026-09-09(RC3 第五批独立集中复核：确认 §6.13 新交付，沿 "
    "RC3-01 至 RC3-12 保留已修子项；仍有新增导入/作用域与 ACK 双扣预"
    "算回归、测试 oracle/鉴别力、取消资源归属/清理、超时写隔离、后台"
    "/重连与 HTTP 流关闭残留，见 research §6.14；analyze/test/APK/EXE"
    "/真机及正式验收 NOT_RUN，整改未闭合)"
)
NEW_UPD = (
    "更新: 2026-09-10(第六批整改开发自测闭环：产品侧修 RC3-01 编译准入、"
    "02⑥ 幽灵重发、04 owner epoch、05 写通道废弃、06 takeError 双扣、"
    "07 恢复点时钟、08 身份复核 fail-closed、10 下载分类/兼容字段、11 "
    "包装流取消、12 地址漂移作废及 transport 订阅竞态根因；analyze "
    "719→0 清零；flutter-dev-checks 双宿主全绿 run 34376805924，debug "
    "APK 首产(release_signing=false)；§6.14 测试侧遗留未动，真机 "
    "NOT_RUN；开发自测≠正式验收，保持进行中，正式验收 NOT_RUN，详见 "
    "research §6.15)"
)
old_upd_b = OLD_UPD.encode("utf-8")
new_upd_b = NEW_UPD.encode("utf-8")
assert board_old.count(old_upd_b) == 1, "更新字段锚点不唯一"
board_new = board_old.replace(old_upd_b, new_upd_b)

# 2) 卡内追加第六批交付记录（插在 #### P3-4 标题前，LF 行尾）
CARD_BULLET = (
    "- RC3 第六批整改交付与开发自测闭环(实现会话): Claude(P3-3-IMPL-"
    "20260907)/2026-09-10；在独占验证分支 dev/flutter/apk/p3-3-batch6 "
    "按 §6.14 遗留清单完成 22 提交整改与 22 轮 CI 反馈迭代：产品侧修 "
    "RC3-01 编译准入、RC3-02⑥ 幽灵重发(发窗/重发循环块完成即停)、"
    "RC3-04 owner epoch、RC3-05 写通道废弃、RC3-06 takeError 双扣、"
    "RC3-07 恢复点时钟、RC3-08 身份复核 fail-closed、RC3-10 下载分类/"
    "兼容字段、RC3-11 包装流取消、RC3-12 地址漂移作废，及 transport "
    "订阅竞态/waitForChange 孤儿 completer 根因修复；[diag] 打点全部"
    "移除(其中一处 ??= 首错保留回归在本批内被 RC3-06 teardown 负例"
    "抓获并修复验证)。analyze 719→0 清零；Android 构建链升 Gradle "
    "8.14/AGP 8.11.1/Kotlin 2.2.20；dev_checks 门禁三轮加固(语义比"
    "较/工具链再生白名单恢复/收尾审计快照，宿主回归 37 项全绿)。终态 "
    "run 34376805924(commit 6177a8b) completed success：ubuntu 13 命令"
    "全 PASS+windows job success，debug APK 首产(trace-dev-debug.apk "
    "131,436,066 B，sha256 09c3331adc5dca14a4a531497a026599a464567"
    "cd93c04b929d453a717e08e43，release_signing=false，"
    "formal_acceptance=NOT_RUN)。§6.14 测试侧遗留(oracle/负例/资源"
    "清理)未动，真机与 EXE NOT_RUN。逐项处置、run 链与 APK 元数据见 "
    "docs/ota-exec-notes/P3-3-research-flutter-ota.md §6.15。开发自测"
    "通过不等于正式验收，P3-3 保持进行中；按 §7.3.2 预授权提交推送"
    "(3c05963..6177a8b)，未合并/发布/部署/真机。\n"
)
p34_b = "#### P3-4 AT 提速实测".encode("utf-8")
assert board_new.count(p34_b) == 1, "P3-4 标题锚点不唯一"
idx = board_new.index(p34_b)
board_new = board_new[:idx] + CARD_BULLET.encode("utf-8") + board_new[idx:]

# 3) §9 追加一行（插在 2026-09-09 授权治理行之后，LF 行尾）
S9_ROW = (
    "| 2026-09-10 | P3-3 / Claude 实现 agent（第六批开发自测） | 开发"
    "验证入口真实 CI 首跑暴露三处 harness 缺陷：checkout 字节比较把 "
    "Flutter 工具链 migration 再生文件误判为源码漂移而拦 APK；构建期"
    "再生未恢复致收尾误红；早期 workflow 语法/治理配套/lockfile 漂移"
    "阻断首跑 | dev_checks 门禁改语义比较+工具链再生白名单(构建前恢"
    "复提交字节、收尾恢复留 source_after_pre_restore 审计快照)；"
    "Android 构建链升 Gradle 8.14/AGP 8.11.1/Kotlin 2.2.20 满足 "
    "Flutter stable 最低要求；宿主回归 37 项全绿 | 属 §7.3.2 预授权"
    "范围内的开发验证工具修复，不改冻结合同/矩阵/判据；每轮修复以 "
    "changed inputs 重新触发(22 run 反馈链留痕 .cache-ci/ 与 "
    "research §6.15)，终态 run 34376805924 全绿+debug APK 首产；开发"
    "自测≠正式验收 | 已执行/开发自测全绿 |\n"
)
s9_anchor = (
    "| 2026-09-09 | P3-3 / Codex 实现自测授权治理 | 上一版开发入口不"
    "产 APK，且仍须主会话逐批授权提交推送，实现 agent 缺少独立运行反"
    "馈通道 | 用户本轮明确要求增加实现 agent 自测权限与 Actions APK "
    "能力；只预授权独占 dev/flutter/** 验证分支和 flutter-dev-checks"
    ".yml，补 debug APK 模式，不借用生产发布工作流 | 授权来源为本轮"
    "用户决定；规范与工作流已回写。主干/标签、force-push、合并、发布"
    "、部署、真机及绕过沙箱仍不允许；仅完成宿主验证，未代替实现 "
    "agent 推送或运行远端 CI | 已授权/入口已落盘，远端首跑待执行 |"
)
s9_b = s9_anchor.encode("utf-8")
assert board_new.count(s9_b) == 1, "§9 末行锚点不唯一"
board_new = board_new.replace(s9_b + b"\n", s9_b + b"\n" + S9_ROW.encode("utf-8"))

# 4) §10 追加一行（文件末尾，LF 行尾）
S10_LINE = (
    "- 2026-09-10 ｜ Claude(P3-3 实现 agent，第六批整改与开发自测闭环)"
    " ｜ P3-3(保持进行中，开发自测全绿，正式验收 NOT_RUN) ｜ 按 §6.14 "
    "遗留清单在 dev/flutter/apk/p3-3-batch6 完成 22 提交整改与 22 轮 "
    "CI 反馈迭代：产品侧 RC3-01/02⑥/04/05/06/07/08/10/11/12 子项修复"
    "+transport 订阅竞态/幽灵重发/写通道废弃根因，??= 首错保留回归"
    "本批内被负例抓获并修复；analyze 719→0 清零；dev_checks 门禁语义"
    "比较+白名单恢复；Android 构建链三连升级。终态 run 34376805924 "
    "全绿(ubuntu 13 命令 PASS+windows success)，debug APK 首产"
    "(sha256 09c3331a…，release_signing=false)。§6.14 测试侧遗留未"
    "动，真机与 EXE NOT_RUN，未填 EXECUTED PASS；按 §7.3.2 预授权提交"
    "推送(3c05963..6177a8b)，未合并/发布/部署/真机。逐项处置、run 链"
    "与 APK 元数据见 research §6.15。\n"
)
assert board_new.endswith(b"\n")
board_new = board_new + S10_LINE.encode("utf-8")

# ------------------------------------------------------------------ 校验
assert board_new.count(b"\r\n") == board_crlf_before == 728, "CRLF 行数漂移"
assert board_new.count("2026-09-10".encode("utf-8")) == 4, "四处编辑未全部落位"
assert research_new.count(b"### 6.15 ") == 1

open(RESEARCH, "wb").write(research_new)
open(BOARD, "wb").write(board_new)

print("research: before", r_before)
print("research: after ", sha256(research_new), "(+%d bytes)" % len(add_bytes))
print("board   : before", b_before)
print("board   : after ", sha256(board_new))
print("board CRLF 行数保持:", board_new.count(b"\r\n"))
print("OK")
