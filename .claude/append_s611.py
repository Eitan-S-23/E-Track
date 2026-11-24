# -*- coding: utf-8 -*-
# 向 research 追加 §6.11（第四批整改交付记录）。文件为纯 LF UTF-8，
# 以字节方式追加，不触碰既有 §6.8/§6.9/§6.10 内容。
import io

PATH = r'D:\github\my\E-Track\docs\ota-exec-notes\P3-3-research-flutter-ota.md'

section = u'''### 6.11 RC3 第四批整改交付（P3-3-IMPL-20260907，2026-09-08）

交付者：Claude（实现会话，承接 §6.10 独立复核）。整改对象为 §6.10.2 逐项
处置表确认未闭合的 RC3-01 至 RC3-12，不重新编号。本批交付＝源码/测试修改 +
静态核对；**Flutter analyze/test、Actions APK/EXE、真机全部 NOT_RUN**（本机
无 Flutter SDK，未获 commit/push 授权）。下表「已修」仅指已完成代码修改且
静态核对未再发现 §6.10.2 所列矛盾，不是运行验证通过。P3-3 保持进行中。

#### 6.11.1 本批修改文件与编辑量（从会话记录重建）

96 次 Edit（无新建文件；`.github/workflows/build.yml` 与
`lib/config/share_links.dart` 为更早批次遗留脏文件，本批未触碰）：

- 实现（lib，45 次）：[ota_download.dart](../../app/bluetooth_flutter_Trace/lib/ota/ota_download.dart) 17、
  [ota_service.dart](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart) 11、
  [ota_ble_transport.dart](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart) 10、
  [ota_upgrade_page.dart](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart) 5、
  [bluetooth_service.dart](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart) 2。
- 测试（test/ota，51 次）：ota_ble_transport_test 19、ota_service_upgrade_test 11、
  ota_download_test 9、ota_service_session_test 5、bluetooth_adapter_notify_test 4、
  ota_upgrade_page_test 2、share_links_latest_query_test 1。

#### 6.11.2 原 ID 逐项处置

| 原 ID | 合同依据 | 根因（详见 §6.10.2） | 实际修改及共享依赖 | 源码整改状态 | 实际执行证据 | 未执行项/剩余风险 |
|---|---|---|---|---|---|---|
| RC3-01 | Spec analyze/test；原 RC2-01 | 四处静态编译矛盾（可空传必需参数、不存在的事件 API、可空 public 字段解引用、非 const 字符串乘法） | `_checkLatestLocked` 增 `int? generation` 参数并贯穿重试与发布（[service:340](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L340)），调用方以 `_runExclusive` 的非空代次传入；页面改用 1.35.5 实际 API `OnConnectionStateChangedEvent` + `FlutterBluePlus.events.onConnectionStateChanged`（[页面:44-48](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L44)/[116](../../app/bluetooth_flutter_Trace/lib/pages/ota_upgrade_page.dart#L116)），订阅异常退化为一次性解析；session test 的 `entered` 改为 adapter 构造注入 `Completer<void>?`（test:85/88/223），不再解引用可空 public 字段；query test 改 `final validSha`（test:9-10）。 | 已完成代码修改；grep/sed 核对四处未再发现矛盾 | 静态核验命令见 6.11.3；无编译器验证 | analyze NOT_RUN（无 SDK）；页面事件 API 仅静态对照 §6.10.3 的 flutter_blue_plus 1.35.5 归档源码 |
| RC3-02 | fail-closed harness；Spec 服务状态链测试 | 空 notifyLog 走真实 snackbar、cancel/latest gate 死锁环、hex 摘要 fixture 混淆、空错误体期待与按码分类矛盾 | session test `makeService` 默认注入 onNotify 收集器（空 `notifyLog` 不再触 snackbar）；latest gate 改为在发起 cancel 前完成（死锁环拆除，测试不再依赖 cancel 返回后放行）；upgrade test 摘要 fixture 修正为 `List<int>.filled(32, 0x62)` → hex `'62'*32`，文件头注释固化「0x62 是 ASCII 'b'，勿与 hex 'b'(0xBB) 混淆」口径；download test 409/410 正例补真实稳定码 errorBody（ASSET_ARCHIVED/ASSET_DISABLED），空体改为 fail-closed 闭锁断言（见 RC3-10/11 组）。 | 已完成代码修改；测试用例与 lib 分流语义逐行对照 | 静态写入与逐行对照；未运行 | flutter test NOT_RUN；「测试可信」仍待真实运行佐证 |
| RC3-03 | binary §4.4/§4.5/§5；真实 MCU 语义 | fake 不做 MCU 真实流式 SHA 校验；ACTIVE 分支绕过注入；谎报 durable 与回退拒绝冲突 | 两个 fake（transport test `_McuSim` 与 upgrade test `_UpgradeFakeBle`）统一双层流式 SHA 模型：`_stagedBytes`（journal 持久字节，块提交追加、erase 清零）+ `_shaBytes`（会话层，BEGIN 重置为前者副本、新段按接收顺序 append、END 一次性 sha256 比对）＝ [ota_ble_session.c:664](../../Libraries/OTA/ota_ble_session.c#L664) 内容级摘要语义；ACTIVE 分支尊重 `dropAllBeginAcks` 注入；BEGIN durable 回退/越界与 transport 回退拒绝 fail-closed 对齐；END 复述一致但内容不符 → ERR_SHA 并 erase。 | 已完成代码修改；两个 fake 均带流式 oracle（test/ota/ota_ble_transport_test.dart:1252-1291、ota_service_upgrade_test.dart:724-858） | 静态核对 fake 与真值 :377-702 语义映射；未运行 | flutter test NOT_RUN；「完整 MCU/整包摘要通过」的运行证据待真机/CI |
| RC3-04 | 单一 owner；CANCEL-RECOVERY；Spec 取消后不继续操作 | 恢复 body 前不查取消、read 链与 latest 请求无取消、cancel 清理顺序倒置、owner 解锁后删新操作正用的包 | `_runExclusive` finally 仅当代次未变才复位（防取消后旧 owner 复位新操作状态）；read 链发现后查代次再绑定/GET_INFO；check 的 App-info await 后带代次检查并以 `_activeLatestToken` 挂接在途 latest（cancelUpgrade 第一时间取消）；cancelUpgrade 顺序改为 取消 latest token → 取消下载 token → transport abort → 下载 cancel → `await owner` → owner 空闲才删包（[service:862-924](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L862)）。 | 已完成代码修改；调用链静态核对 | 静态核对 _runExclusive 六个调用点（read/check/download/start/cleanup/cancel 内删包）；未运行 | flutter test NOT_RUN；并发时序仅由测试静态覆盖（upgrade test 传输在途二次 start/取消两例） |
| RC3-05 | HTTP-RESUME:271；FLUTTER-TRANSPORT:1057；取消帧完整性 | ABORT 与 DATA 分片写无串行 owner 可交错半帧；下载校验/rename 无 token 检查；cancel 不等 sink 关闭就删；吞删除失败 | 写帧串行化：`_writeFrameChecked` 更名 `_writeFrameLocked` 并经帧写锁串行（[transport:799-815](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L799)，ABORT 与 DATA 分片不再交错）；下载 `cancel` 先有界等待在途 download future（`_inFlight` 表）再删 partial/sidecar；整文件校验通过后 rename 前核对取消令牌；`invalidatePartial` 统一删除路径且失败上报（不再吞）。 | 已完成代码修改 | 静态核对锁序与取消路径；transport test 增受控 MTU 分片 barrier + 真实 cancelUpgrade 交错用例（静态写入） | flutter test NOT_RUN；交错反例的运行验证待 CI |
| RC3-06 | binary §5.5/§5.6，ACK 是唯一进度真相 | onAck 无当前可提交窗口限制，跨窗伪跳跃可清 inFlight 跳块发 END；BEGIN/END 校验不统一 | onAck 增跨窗伪跳跃 fail closed：`ack.durableOff - durableOff > blockSize` 记畸形（[transport:1000-1009](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L1000)），8192B 包首块在途 ACK 报 durable=8192/bitmap=0 被拒；BEGIN ACK `reset` 过同链 `_durableValid`/`_bitmapValid`；END OK 核对 durable==total。 | 已完成代码修改；§6.10.3 的 8192B 反例路径已封堵 | 静态核对；transport test 跨窗伪跳跃负例（静态写入） | flutter test NOT_RUN |
| RC3-07 | BLE-TUNING/RETRY-POLICY：30 秒无 durable 进展 | 帧外一次 perChunkTimeout，MTU=23 的 8 片各 9s 累计 72s 绕过总预算；BEGIN 复用写前 timeout | 分片循环内逐片重算 `perChunkTimeout` 并按剩余预算封顶（[transport:841-845](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L841)）；BEGIN ACK 等待以剩余预算封顶（重试每轮不再固定 2s）。 | 已完成代码修改；§6.10.3 的 72s 控制流反例已封堵 | 静态核对；transport test 慢分片写用例（静态写入） | flutter test NOT_RUN |
| RC3-08 | DEVICE-DTO:118；BLE-LIFECYCLE；FLUTTER-TRANSPORT:1058 | 页面只改标志不暂停在途 DATA/END；重启等待不用剩余预算；快速重连 MCU 仍 ACTIVE 时低 seq 幂等 ACK 被当写入确认按错误顺序填洞 | transport 增 `_pauseGate`/`_waitIfPaused`（发送/重发/读取三循环挂起，[transport:248/270/317/485](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L248)），cancel/dispose 释放暂停门；页面对 paused/inactive 调 service 暂停、resumed 恢复；重启等待 deadline 前移到 disconnect 之前、循环内查剩余预算；快速重连幂等 OK（durable 未推进且权威位图不含该段）fail closed 记 ERR_STATE → 传输循环 ABORT teardown + BEGIN 重对齐（[transport:1011-1027](../../app/bluetooth_flutter_Trace/lib/ota/ota_ble_transport.dart#L1011)），不按错误 offset 顺序填洞。 | 已完成代码修改；§6.10.3 快速重连模型（真实接收顺序 `20..31,5..19`）由 ERR_STATE fail-closed 阻断 | 静态核对；transport test 快速重连用例改真实流式 SHA 语义 fake（静态写入） | flutter test NOT_RUN；后台暂停/真实重连行为待 Windows CI 与真机 |
| RC3-09 | 精确 FFF0/FFF2/FFF1；真实通知与 adapter 调用链 | 能力读取走 `object.getField(...)`，真实 win_ble `BleCharacteristic` 无该成员，能力全回 null 正常特征被拒 | `_getProperty` 对 'uuid'/'properties' 直接成员访问；新增 `_propField` 按 win_ble 1.1.1 `Properties` 的 9 个 `bool?` 字段读取、`_propContains` Map/List/字段三分支（[bluetooth_service.dart:1742-1816/2013-2072](../../app/bluetooth_flutter_Trace/lib/services/bluetooth_service.dart#L1742)）。测试用真实 `win_ble.BleCharacteristic`/`Properties` 对象覆盖「发现→精确选择（fff5 可写诱饵负例）→写入→订阅→通知」链；Windows 分支以 `skip: !Platform.isWindows` 门控，由 build.yml windows-2022 job 执行；另补重新绑定资源所有权 2 例（退订一一对应、失败不留残留流）。 | 已完成代码修改；win_ble 1.1.1 归档源码级核对（构造器命名参数、无 getField、进程式连接器导入安全） | win_ble 1.1.1 归档下载解包至项目内 `.cache/win_ble-1.1.1/`，src.tar.gz SHA-256 `2a867e13c4b355b101fc2c6e2ac85eeebf965db34eca46856f8b478e93b41e96`，与 §6.10.3 复核者独立下载的哈希一致 | 本机无 SDK 无法运行；Windows 发现链用例仅静态写入；真实 Windows BLE 实测 NOT_RUN |
| RC3-10 | HTTP-ERROR/UNKNOWN-FIELDS；稳定终止闭锁 | latest 先按 429/503 重试不先分类，未知码可被后续 200 洗成成功；下载 400/426 落 generic catch 不闭锁；requestId 丢失 | latest retry 改分类先于重试（仅 `isAutoRetryable` 网络类/429/503 进重试，稳定码与未知码直接闭锁）；终止闭锁扩展到空/坏错误体的稳定 4xx；下载 `validateStatus` 受控放行 + 非受控状态经 Dio badResponse 统一转换 `HTTP_STATUS`（`OtaDownloadException` 增 `httpStatus`，401/409/410 携带 `httpError`）；闭锁文案携带 requestId/errorCode。测试负例组：409/410 空体 fail closed 不猜刷新、400/426 统一转换、401 超大错误体按裸状态码闭锁、未知码不被 200 洗白。 | 已完成代码修改；lib 看码分流（L167-204/207-268）与测试逐行对照 | 静态核对；download test RC3-10/11 组 8 用例（静态写入） | flutter test NOT_RUN；真实 HTTP 服务端行为实测 NOT_RUN |
| RC3-11 | HTTP-RESUME/DOWNLOAD：强 ETag、digest、流关闭 | ETag `[!-~]` 含双引号接受 `"a"b"`；sidecar 不校验旧标签；drain/fold 无界；下载无 receiveTimeout | `_isStrongEtag` 字符集改 `[!#-~]`（排除内部未转义引号 0x22）；sidecar 读取侧同标准校验（坏 ETag 置 null → 作废 partial 从零重下，不发 Range/If-Range）；206 响应 ETag 非强走 ifRangeSent 违规两轮请求重下；`_drainBody` 增 `maxBytes`（64KB）有界消费；下载 Dio 增 receiveTimeout；Content-Digest 保持唯一 sha-256 项 + 规范 base64 校验。测试：sidecar/响应两侧坏 ETag、drain 字节级有界观测（`deliveredBytes` 计数的 async\* 生成器在订阅取消后停止）、digest 多项/短 base64 负例。 | 已完成代码修改；两侧 ETag、有界 drain、digest 语义静态核对 | 静态核对 + 测试静态写入 | flutter test NOT_RUN；恶意/超大响应实测 NOT_RUN |
| RC3-12 | UI 用户意图/领域状态；清包与恢复 | 清包只在入口检查一次 busy；取消先发布再异步删除；稳定终态无实际可执行的恢复入口 | `cleanupFirmware` 纳入 `_runExclusive`（清包期间新传输入口确定性被拒，[service:946-980](../../app/bluetooth_flutter_Trace/lib/services/ota_service.dart#L946)）；`cancelUpgrade` 删包与 cancelled 终态在 owner 退出后同一发布点一次性成立；页面在终止闭锁但身份快照仍在时提供「重新读取身份解锁」实际可执行入口（OutlinedButton → readDeviceInfo 成功即清终止态恢复查询链）；取消按钮 await cancelUpgrade 后刷新 UI。测试：真实 service 状态转换 3 例（清包 owner 互斥、取消删包一次性一致、终止闭锁经真实 readDeviceInfo 解锁后完整走通传输——MCU durable 已满时 BEGIN 续传直达 END）+ page 恢复入口用例（fake readDeviceInfo 对齐真实契约清 terminal）。 | 已完成代码修改；owner/发布/入口三链静态核对 | 静态核对 + upgrade/page test 静态写入（upgrade test:305-416） | flutter test NOT_RUN；真实 UI 联测待 Windows CI |

#### 6.11.3 实际执行与证据

| 检查/命令 | 本轮实际结果 |
|---|---|
| `git --no-optional-locks status --short` | 脏文件与 gitStatus 基线一致（第三批起累计），本批新增修改均落在既有 lib/test 文件内；9 个遗留未跟踪文件与 2 个既有诊断保留未动。 |
| grep/sed 逐点核验 | RC3-01 四处矛盾消除；`_runExclusive` 六调用点；transport 写帧锁/`perChunkTimeout`/`_waitIfPaused` 三循环挂起/onAck 跨窗 fail closed/幂等 OK 判定；download validateStatus 分流、`_drainBody` 边界、`_isStrongEtag` 字符集；bluetooth_service `_getProperty`/`_propField`/`_propContains`；service 文案（`升级已在进行中`/`固件文件不存在`/`固件包已清理`/`设备身份已确认`/`已进入终止状态`）与测试断言逐字一致；fake MCU BEGIN/END 对 durable 已满续传（跳 DATA 直达 END、流式 SHA 重建匹配）的闭环推演。 |
| win_ble 1.1.1 归档核对 | `curl` 下载 pub.dev 归档 + `tar` 解包至项目内 `.cache/win_ble-1.1.1/`（仓库既有忽略目录）；src.tar.gz SHA-256 `2a867e13c4b355b101fc2c6e2ac85eeebf965db34eca46856f8b478e93b41e96`，与 §6.10.3 复核者记录一致。核对结论：`BleCharacteristic({required this.uuid, required this.properties})`、`Properties` 9 个 `bool?` 字段、无 `getField`、`discoverServices` 返回 `List<String>`、`characteristicValueStreamOf` 命名参数三元组、WinConnector 为 Process.start 进程式（flutter_test 导入安全）。 |
| Node transcript 提取（`node .claude/list_batch4_edits.js`） | 本批 96 次 Edit 的文件/次数分布见 6.11.1，用于交付记录重建，不作为源码证据。 |
| `python` 行尾检查 | research 文件纯 LF（CRLF=0）、UTF-8、以换行结尾；本节以 LF 追加，不触碰 §6.8/§6.9/§6.10。 |
| `where flutter`；`where dart` | 沿用 §6.10.4 结论（各 exit 1，无 SDK）；本批未安装 SDK、未本地构建。 |
| Flutter analyze/test；Actions APK/EXE；真机 BLE/J-Link | **全部 NOT_RUN**。测试仅静态写入未运行；Actions 未触发（无 commit/push 授权）；硬件观测消耗 0。 |

#### 6.11.4 未执行项与剩余风险

- **Flutter analyze/test NOT_RUN**：本机无 SDK。本批全部测试（含 RC3-09 Windows
  发现链组、RC3-10/11 负例组、RC3-12 真实 service 状态转换）只完成静态写入，
  未经过编译器与测试宿主检验——不能排除类型/导入/语法层的新矛盾。
- **Actions APK/EXE 未执行**：未获 commit/push/workflow 授权（Actions 构建要求
  不是推送授权）。windows-2022 job 是 RC3-09 Windows 发现链用例的唯一可执行
  宿主；ubuntu job 会按 group skip 跳过该组。
- **真机/J-Link NOT_RUN**：后台暂停、真实重连、MCU 快速恢复 ACTIVE 等 BLE
  时序行为仅静态覆盖。
- `lib/config/share_links.dart` 与 `.github/workflows/build.yml` 为更早批次遗留
  脏文件，本批未触碰，其状态由前批交付记录负责。
- P3-3 卡面 toy/真包真机判据与实施 Spec 的 P3-5 归属差异仍待冻结前确认，
  本批不自行豁免、迁移或降低。

#### 6.11.5 写入审计

本批主动写入全部位于活动根 `D:/github/my/E-Track` 内：

- 产品/测试：`app/bluetooth_flutter_Trace/lib/`（5 文件）与
  `app/bluetooth_flutter_Trace/test/ota/`（7 文件），共 96 次 Edit。
- 本 research 追加 §6.11（LF 追加，不改既有节）。
- `PLAN-OTA-EXEC.md`：P3-3 动态回写 + §10 日志追加一行（Python 字节级编辑
  保 CRLF）。
- 项目内忽略目录 `.cache/win_ble-1.1.1/`：win_ble 1.1.1 归档解包（只读核对
  用）；`.claude/list_batch4_edits.js`：transcript 提取辅助脚本。

未执行：commit/push/merge/workflow dispatch/部署/烧录/设备复位；未修改项目外
SDK、缓存或工具链；未清理任何遗留文件或历史产物；未创建验收合同、未填 PASS
矩阵、未把卡置「完成」。本批自测与正式验收分开记录；正式验收仍须由非实现
独立会话在实现与 runner 提交、合同审批冻结、执行工作树门禁与 NOT_RUN 矩阵
前检满足后推进。
'''

with io.open(PATH, 'ab') as f:
    f.write(section.encode('utf-8'))
print('appended', len(section.encode('utf-8')), 'bytes')
