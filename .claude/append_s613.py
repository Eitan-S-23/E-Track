# -*- coding: utf-8 -*-
# 向 research 文档追加第五批整改交付记录（§6.13）。
# 模式沿用 append_s611.py：二进制追加，UTF-8 纯 LF，不动既有字节。
import io

PATH = r"D:\github\my\E-Track\docs\ota-exec-notes\P3-3-research-flutter-ota.md"

section = """
### 6.13 RC3 第五批整改交付（P3-3-IMPL-20260907，2026-09-08）

交付者：Claude（实现会话）。整改对象为 §6.12.2 逐项结论中仍未闭合的测试
可信度、fake MCU 真值、取消交错、ACK 末块错误传播、慢写预算反例、身份恢复
闭锁、HTTP 闭锁与下载流清理缺口；§6.12.3 反例纠正按复核结论维持不改。
本批跨多个上下文窗口完成：lib 侧修复（ota_download/ota_service/
ota_ble_transport/ota_upgrade_page）先落盘，随后收尾测试侧并完成本节交付。
**Flutter analyze/test、Actions APK/EXE、真机全部 NOT_RUN**（本机无 Flutter
SDK，`where flutter` / `where dart` 均未找到；未获 commit/push 授权）。本文
「已修」仅指完成代码修改且静态落盘复核未再发现 §6.12.2 所列矛盾，不等于
运行验证通过。P3-3 卡保持「进行中」。

#### 6.13.1 本批修改文件（交付时逐项落盘复核）

- 实现（lib，均在既有 P3-3 改动文件内）：
  - `lib/ota/ota_download.dart`：RC3-11⑤ 首块停滞时间界 + 早退 drain 主动
    取消 token（4 处编辑覆盖 6 个 drain 调用点与 `_parseContentDigest`
    签名扩展）。
  - `lib/services/ota_service.dart`：RC3-04⑤ 取消绑定原 owner 快照
    （`ownerAtCancel = _ownerDone` 同步快照，不追等快照后新进入的 owner）、
    RC3-10⑤ 残留刷新标志稳定终止态守卫、RC3-08⑤/12⑤ 身份重验先于恢复
    放行与身份变更失效旧清单旧包。
  - `lib/ota/ota_ble_transport.dart`：RC3-06⑤ 块结束锁存错误消费
    （transfer 块尾 `takeError()` + `_classifyAckError` 同链处置）、
    RC3-05⑤ 迟到物理写隔离（帧取消后迟到的底层写经 2×writeTimeout settle
    隔离，不再污染写串行化链）。
  - `lib/pages/ota_upgrade_page.dart`：RC3-08⑤ 终态恢复入口
    （`_readDeviceInfo` 重新读取身份解锁终止态，入口按钮文案
    「重新读取身份解锁」）。
- 测试（test/ota）：
  - `ota_service_session_test.dart`：RC3-02⑤ notifyLog 默认改为可增长列表。
  - `ota_ble_transport_test.dart`：RC3-02⑤ 丢 ACK 期望修正、RC3-03⑤ fake
    4KB 窗口门禁/durable 幂等/新包清 journal、RC3-06⑤ bitmapOverride=0
    鉴别力与块尾锁存错误用例、RC3-07⑤ 慢写用例重写、RC3-05⑤ MTU=23 在途
    ABORT 用例。
  - `ota_service_upgrade_test.dart`：RC3-02⑤ 块提交 barrier、RC3-03⑤
    fakeInspectEtuHeader 门禁、RC3-08⑤/12⑤ 身份漂移作废旧包用例、
    RC3-10⑤ INVALID_PARAMETER 闭锁用例、RC3-05⑤ 小 MTU 分片在途取消用例。
  - `ota_download_test.dart`：RC3-11⑤ drain token 断言与首块停滞用例。

#### 6.13.2 逐项处置（对 §6.12.2）

| 项 | §6.12.2 批评要点 | 处置 |
|---|---|---|
| RC3-02⑤ | session test makeService 默认 `notifyLog = const []` 仍无条件 add；transport test:326 丢 ACK 可续传成功却期望 TIMEOUT；upgrade test:282/292 等的是第一份 ACK 挂起而非第八段提交（durable=1024 断言无 barrier） | session test 默认改为可增长 `<String>[]`；transport test 丢 ACK 场景改为期望续传成功（丢失窗口过后 ACK 恢复、durable 推进到位），NO_DURABLE_PROGRESS 用例改用 `respondDataAck=false`（真无 ACK）构造；upgrade test 取消前轮询等待 `stagedDurable >= 1024`（真实 journal 块提交 barrier）再取消，durable 断言不再依赖 ACK 到达时刻 |
| RC3-03⑤ | 两个 fake 写段前缺 4KB 窗口检查（真值 ota_staging.c:499-503）；upgrade fake 缺已 durable offset 幂等与新包清 journal；BEGIN:695 缺真实 MCU 包头/版本检查；test:854 注入 bitmap=1 无独立鉴别力 | `_McuSim` 写段前增越当前 4KB 窗段 ERR_OFFSET 门禁（含独立验证用例「fake 门禁：越当前 4KB 窗的段 → ERR_OFFSET」）+ 已 durable offset 幂等 + 不同 sha 新包 `_eraseStaged` 清 journal；`_UpgradeFakeBle` 增 `fakeInspectEtuHeader`（magic/header_len/CRC/flags/algorithm/key/hw_rev/layout/min_boot/target_vcode/full base 检查链，错误映射对齐真值 BEGIN 前置校验）；跨窗伪跳跃注入改 `bitmapOverride=0`（`_bitmapValid(0,·)` 恒真，唯一可拒谓词落到 durable 跨窗检查，负例有独立鉴别力） |
| RC3-04⑤ | 取消可能等待后来进入的新 owner 再删其包（service:888） | `cancelUpgrade` 发起处同步快照 `ownerAtCancel = _ownerDone`，只等待快照时已在途的 owner；快照后新进入的 owner 不被旧取消链删除其包。测试见 upgrade test owner 快照用例 |
| RC3-05⑤ | transport test:761 先等 transfer 退出再 ABORT（未测在途交错）；service fake 单片 247（撕裂永不发生） | transport test 增「MTU=23 下取消：在途 DATA 写完后 ABORT 从帧边界发出」用例（transfer 在途时 `abortBestEffort`，断言 ABORT 完整帧 + `pendingByteCount==0`）；service 侧 `_UpgradeFakeBle` 增 `otaMtu` 注入（语义对齐真值 `requestOtaMtu` 返回写净荷上限，注入 20 等价 ATT MTU 23）与 `writeChunkDelay` 慢速写，新增「小 MTU 分片在途取消」用例：两段 DATA 落地后 `cancelUpgrade`，断言 `abortCalls==1`（经 fake 跨 chunk 重组 + `decodeFrame` 同步字/长度/CRC16 校验，撕裂即失败）、`dataOffsets` 按 128 步长连续无撕裂、`endCalls==0` |
| RC3-06⑤ | 末块 ACK 错误可能被后续提交进度掩盖继续进 END（transport:258）；跨窗负例需 bitmap=0 | lib：transfer 块结束处锁存并消费错误（`takeError` → `_classifyAckError` → resume/terminal/抛出处置链），错误不再被块提交进度冲掉。测试：新增「块尾提交不得掩盖在途畸形 ACK」用例（伪跳跃 8192 注入 + 后续整块提交仍提交，期望 ACK_MALFORMED、`endCalls==0`）；跨窗负例注入改 bitmapOverride=0 |
| RC3-07⑤ | 慢写对 BEGIN 帧也延迟（111B 在 MTU=23 下 6 片×80ms=480ms，500ms 预算剩 20ms，首个 DATA 分片进 WRITE_TIMEOUT 而非断言的 NO_DURABLE_PROGRESS）；未构造「同一 DATA 帧各片未单独超时、累计超期」反例 | 慢写用例重写：写延迟仅作用于 DATA 帧分片（控制帧不受预算）；预算 520ms 并按片间边界检查与写完成间隔各留 40ms 计时余量；期望码修正为 WRITE_TIMEOUT（片级 cap 先于累计无进度检查触发，与协议语义一致）；截断证据断言完整 DATA 帧 0、`pendingByteCount==140`（7 片×20B 半帧滞留）——修复缺失时用例红 |
| RC3-08⑤/12⑤ | upgrade test:413 恰把「身份变化后沿用旧清单旧包」当成功 | lib：恢复链改为身份重验先于恢复放行（后台恢复不先放行传输）、重读身份返回新 DTO、身份变更即失效旧清单与旧包；page 终态恢复入口走 `_readDeviceInfo`。测试改写为「终止闭锁经重新读取身份解锁：身份漂移作废旧清单与包」：rev3→4 漂移后终止态解锁但旧包作废（`downloadedFirmwareFile isNull`、不触 BLE 重建、入口指引明确），原「沿用旧包」断言删除 |
| RC3-10⑤ | 残留刷新标志可绕过稳定终止态再次 latest/download（service:475） | lib：稳定终止态守卫拦截残留刷新标志，终止态不洗白；requestId 贯通、retry 状态约束收紧。测试：新增「下载 INVALID_PARAMETER 稳定闭锁」用例——三步状态机 adapter（401/TOKEN_EXPIRED → 400/INVALID_PARAMETER → 401 残留），断言终止态 code/requestId 贯通/phase failed/包清理；终止后第二轮 401 再置残留标志被守卫拦截（`_LatestOkAdapter.calls` 停在 2） |
| RC3-11⑤ | 64KB 后退出包装流不保证取消 Dio 底层响应；首块正文停滞仍可能挂起（download:585） | lib：主读循环对包装流套 `Stream.timeout(receiveIdleTimeout)` 首块停滞界（Dio 5.9.0 接收空闲计时器只在首个 data 事件后启动，响应头已到而正文永不到时裸 await for 无限挂起）；早退路径 `_drainBody` 增 `cancelToken` 参数并在达 64KB 界主动取消——补接线 6 个调用点：未请求 206、200 Content-Length 不符、`_parseContentDigest` 内 3 处 fail-closed drain（经新参数传入）及调用点传 token；续传头违规分支仅反复失败（即将 throw）路径取消 token（`restartUsed ? token : null`）——首次违规要走 continue 从零重下，取消同一 token 会让重试请求立即 CANCELLED、把协议违规误归因为用户取消，首次违规由有界 drain 限流量。测试：drain 用例传入自有 `CancelToken` 并断言 `token.isCancelled`（达界主动取消的直接观测，修复前仅 break、断言红）；新增「首块正文停滞」用例（`stallAfterChunks=1` 注入、receiveTimeout 压至 200ms、期望 TimeoutException、partial 已收 1024B 保留供续传、用例自身 10s 超时防挂起假绿） |

§6.12.3 反例纠正处置（均不改，维持复核结论）：

- latestGate：第四批已修，本批无动作。
- `_runExclusive` identical 释放：释放语义正确，不改。
- END OK 非零 bitmap 不是合法残留：不改冻结合同，不为 fake 注释改产品
  校验。fake 的 END 上报在 ACTIVE 会话下携带真实位图、teardown 后置 0，
  与真值语义一致；该反例不构成缺陷。

#### 6.13.3 实际执行与证据

| 检查 | 命令/方式 | 结果 |
|---|---|---|
| SDK 可用性 | `where flutter` / `where dart` | 均未找到——Flutter analyze/test NOT_RUN 的直接依据 |
| 产品改动范围 | `git status --short`（app 子目录） | tracked 修改仍为 P3-3 既有 5 文件（share_links/ota_upgrade_page/app_update_service/bluetooth_service/ota_service）叠加本批内容；`lib/ota/`、`test/` 为本卡新增未跟踪目录（提交前须逐路径显式 add，沿 P3-1 收口先例） |
| 第五批落盘复核 | grep + Read 逐项核对四个测试文件与三个 lib 文件的批评点锚点 | §6.13.2 表中全部处置在交付前逐项确认存在：session test L97-102 notifyLog、transport test 丢 ACK 期望与 fake 门禁用例、upgrade test barrier L362-366/门禁 L421-450/恢复链 L511-550/INVALID_PARAMETER L552+/小 MTU 用例、download test token 断言与停滞用例、lib owner 快照 L912、块尾锁存 L302-319、写串行化 L788-820、drain 接线 L332-372、page 恢复入口 L145-460 |
| 真机/Actions | 未执行 | 无 commit/push/dispatch/烧录授权，一律 NOT_RUN |

#### 6.13.4 未执行项与剩余风险

- Flutter analyze/test NOT_RUN：全部测试修改仅经静态写入与人工推理核对，
  不排除类型/语法层新矛盾；须在有 SDK 的环境（或 Actions）跑绿后才可视为
  验证通过。
- Actions APK/EXE 未触发：未获 commit/push 授权；本批不满足 app 子项目
  AGENTS.md 的 Actions 验证门，不得报告为「完成」。
- 真机/J-Link NOT_RUN；真机判据归属（P3-3 卡面 toy/真包真机判据与实施
  Spec P3-5 的归属差异）仍待冻结前裁定。
- 慢写用例（RC3-07⑤）依赖真实计时（`Future.delayed` 抖动），CI 慢 runner
  上存在理论偶发红面；已按片间检查与写完成间隔各留 40ms 双侧余量压缩。
- 小 MTU 交错用例（RC3-05⑤ service 级）依赖 30ms/片写延迟与 5ms 轮询的
  相对时序（单 DATA 帧写窗口 240ms ≫ 轮询粒度）；极端调度抖动下若取消
  恰落帧间缝隙，ABORT 先入写串行队列、下帧在 `_checkUsable()` 处 CANCELLED
  停写，断言仍成立（无撕裂），但段数下界用 `>= 2` 而非精确值以容纳该边界。
- `lib/ota/`、`test/` 未跟踪目录提交前的显式路径清单未生成（收口时由主
  会话处理）。

#### 6.13.5 写入审计

本批主动写入：上述 lib 4 文件、test 4 文件、research 本节追加、
PLAN-OTA-EXEC.md P3-3 卡回写（状态行更新字段 + 复核记录后追加交付记录 +
§10 日志一行）。全部位于活动项目根 D:\\github\\my\\E-Track 内。未执行
commit/push/workflow dispatch/部署/烧录/设备复位；未创建冻结验收合同、
未填 PASS 矩阵。既有脏文件、遗留未跟踪文件、历史诊断与证据原样保留。
"""

with io.open(PATH, "ab") as f:
    f.write(section.encode("utf-8"))

print("appended", len(section.encode("utf-8")), "bytes to", PATH)
