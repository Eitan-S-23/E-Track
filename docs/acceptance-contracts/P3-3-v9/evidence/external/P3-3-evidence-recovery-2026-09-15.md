# P3-3 剩余证据缺口：恢复搜索结论与最小补测操作单（2026-09-15）

- 执行会话：P3-3-IMPL-20260907（实现会话，worktree
  `D:\github\my\E-Track\.cache\worktrees\p3-3-admission`，分支
  `dev/flutter/apk/p3-3-admission`）
- 依据：v7 独立验收报告 `P3-3-v7-acceptance-2026-09-15.md`（总体
  EVIDENCE_GAP：C-DEV-CHECKS/C-RELEASE-BUILD PASS、C-APK-INSTALL
  ENV_BLOCKED、C-TOY-LOOP/C-REAL-LOOP EVIDENCE_GAP）+ 用户 2026-09-15
  派单「P3-3 剩余证据缺口补齐」（目标：补足真实证据，不是修改措辞
  获得 PASS）
- 性质：只读搜索 + 人证登记 + 补测操作单（**本文件不授权任何执行**；
  操作单获用户一次性批准后才生效）
- 单轮判定权归属独立验收会话；本文件为实现侧事实输入与申请材料。

## 1. 既有原始证据搜索结论：App 侧历史证据不可恢复

搜索范围：worktree `.cache/` 全域、主仓 `D:\github\my\E-Track\.cache\`
（含 T1a 目录）、`docs/`、`.claude/`；类别覆盖 logcat、录屏、截图、
BLE 接收记录、升级完成记录、操作记录文档；并按 mtime 复核
2026-09-14 20:00 ~ 2026-09-15 02:30 升级时段时间窗内新增的全部文件。

| # | 类别 | 结论 | 依据 |
| --- | --- | --- | --- |
| 1 | toy 轮（09-14 21:33~21:40）App logcat | 不可恢复（当时就未取到） | O 序列执行记录 §2 原文：「toy 轮未单独取 logcat（该时段缓冲已滚动）」 |
| 2 | 第六轮 real（09-14 23:59~00:07）App logcat | 不可恢复（当时未采集） | r6 记录全程仅服务日志+用户飞书确认，无 logcat 取证步骤；至今逾一天，设备缓冲必已再滚动 |
| 3 | 升级时段录屏 | 不存在 | 全盘无 .mp4/.webm/.gif；用户 2026-09-15 确认「没有录屏截图」 |
| 4 | 升级时段截图 | 不存在 | 既有截图全部属 09-13 BCB 恢复轮（o2-screen-*.png）与 09-14 凌晨 UI 修复轮（fix-0*.png），mtime 均不在升级时段 |
| 5 | O4 轮（30202）logcat | 未落盘 | O 序列记录 §5.1 引用过其内容（22:10:34 MONO_BUDGET_START 等），但 `.cache` 无对应文件——当时为流式读取，未保存 |
| 6 | App 持久化日志 | 机制不存在 | 源码确认（freeze_tree b3d1d31 内）：无文件日志；数据库表全部为设置/骑行数据（device_settings/scan_settings/power/custom_buttons/devices/device_data/rides）；`getUpgradeHistory()` 自 2ce8cd5 起为桩（return const []） |
| 7 | 设备端 BLE 接收/BCB 记录 | toy 已有、real 当时未采 | toy=o-verify-boot-rtt.log（已在 v7 证据包）；real 轮按当时操作单口径「终点双值按 App 侧证据闭合」未做 RTT |
| 8 | 主仓 T1a logcat | 与本案无关 | p3-3-t1a-step1-r1/r2 为 09-12 15:10~15:24 的 T1a 观测扫描任务产物，时间与对象均不符 |

**结论：按派单第三部分口径，「历史 App 侧原始记录不可恢复」成立。**

## 2. 用户人证登记（2026-09-15，飞书）

| # | 人证内容 | 记录 |
| --- | --- | --- |
| H1 | 升级时段无录屏、无截图 | 用户原话「没有录屏截图」 |
| H2 | 第六轮（real 30203）升级结束时 App UI 终态显示「升级完成」 | 用户原话「显示的是升级完成」 |

### 2.1 H2 的代码分支互斥性分析（事实输入，非判定）

- 用户所见「升级完成」对应 `ota_service.dart` `_RebootKind.targetVerified`
  分支（:966-973）：唯一产生「固件升级完成: 设备已运行 3.2.3
  （vcode 30203）」文案的路径。
- `targetVerified` 仅由复核链单轮探测 `_probeTargetIdentity`
  （:1691-1694）产生，条件为**新连接 GET_INFO 返回的
  currentVersionCode==latest.versionCode 且
  currentImageSha256Hex==latest.targetImageSha256**（全等比对）。
- 验收 E01 反例路径（ACK 未被 App 确认→设备仍激活→复核 timedOut→
  用户手动 readDeviceInfo+手动检查更新）下，App 终态必然是
  timedOut 分支（:974-986）文案「等待设备重启复核超时
  （180 秒，升级可能已完成…）」——与 H2 观察互斥。
- 因此 H2 在分支互斥性支持下，经验性地排除「第六轮复核超时后手动
  查询」这一具体反例，直接支持六状态第 5/6 项（重启后新连接
  GET_INFO 目标身份；原升级调用成功完成）。
- **H2 不覆盖第 4 项（ACK_END/OK 解析）**：ACK_END 丢失与复核成功
  在代码上可并存（复核链是独立重连+GET_INFO，不依赖 END ACK）。
  从产品语义看，复核链 GET_INFO 返回目标身份是强于 END ACK 的终点
  证据（设备已在运行目标镜像），但形式六状态仍留此缺口。
- 人证无原始记录佐证（H1 已确认无截图/录屏/logcat）。是否足以补足
  判据，由独立验收会话裁定；本会话不以人证替代原始记录宣告通过。

## 3. 六状态对照（现状）

以 real 30203（第六轮，2026-09-14 23:59~00:07）为准；toy 30201 同构。

| 状态 | 证据现状 |
| --- | --- |
| 1. 会话开始设备身份+目标资产身份 | ✔ 服务日志（23:59:30/00:00:11 latest 参数 30202+ab0585f7…；返回 3.2.3/30203+3a282768…） |
| 2. App 对下载整包的实际校验结果 | ✗ 无记录（服务端仅见发出 284,608B；App 校验为内存行为；手机私存 firmware/ 目录待接回后只读检查有无 ETU 残留——即使有也只补「下载实物」，不补校验结果） |
| 3. durableOff 达到 totalLen | ✗ App 端无记录（MONO_BUDGET_RESET durable=… 打点未采集） |
| 4. App 解析 ACK_END/OK 且关联本次会话 | ✗ 无记录；且 `ota_ble_transport.dart:526` 成功收尾路径**无打点**（即使当时采了 logcat 也只能间接推证） |
| 5. 重启后新连接 GET_INFO 返回目标身份 | ◐ 服务日志三次 latest（00:06:05/00:06:08/00:07:22）携带 30203+3a282768…；代码上 latest 仅由「检查更新」触发、复核链不发 latest，单凭日志无法区分来源——**H2 人证+分支互斥支持复核链完成**，采信权在验收 |
| 6. 原升级调用的成功完成结果 | ◐ 同上：H2（completed 终态）即「原升级调用返回 true」的人证 |

toy 30201 差异：第 1/5 项有服务日志（21:40:15.699 起三次
30201+aeafc96e…）；另有设备端 J-Link 读回 App 区=目标镜像、RTT
「BCB already CONFIRMED vcode=30201」——设备侧终点强于 real 轮，但
App 侧第 2/3/4/6 项同样无记录；toy 轮无 H2 对应人证（用户当时表述
「升级似乎成功了」+复核对时序观察，弱于 H2）。

## 4. 最小补测操作单（一次性集中授权申请）

> 目标：以高于当前 30203 的受控目标各补一次**带完整 App 端取证**的
> 升级闭环，闭合两条判据的六状态观测。不回退烧录、不重刷已验证环节。
> 本操作单获批后范围内连续执行，不再逐条申请同一权限。

### 4.1 日志增强（前置整改项，先自测提交再冻结）

现状缺口：transfer() END ACK OK 成功收尾（`ota_ble_transport.dart`
:526 return 前）与复核 targetVerified（`ota_service.dart` :966）均无
打点。增强为**真实观测点**（只记录已发生事实，禁止注入成功状态）：

1. END ACK OK 收尾：`otaMonoLog('MONO_END_ACK_OK', durable: <endAck.durableOff>)`
2. 复核成功：`otaMonoLog('MONO_REBOOT_VERIFIED')`（targetVerified 分支）

流程：改动 → flutter-dev-checks 双宿主自测（既有 standing
authorization）→ build-only dispatch 构建新 APK → 后继合同 v8 重冻结
（新 freeze_commit/新 APK/新目标/新服务身份如实登记，不塞回 v7 身份）。

### 4.2 目标资产（两条闭环独立身份，均高于 30203）

| 轮 | 目标 | 说明 |
| --- | --- | --- |
| toy 演练轮 | 3.2.4（30204） | 同源镜像（4b16048f… 本体）+ toy fixture 身份；先行验证取证模式 |
| real 判据轮 | 3.2.5（30205） | 同源镜像 + real fixture 身份；正式闭环判据轮 |

制包与 v5/v6 同法同工具（etu_pack.py，开发密钥 key_id=1），逐轮
离线验证四元组后登记。

### 4.3 服务/隧道/APK（必要的一次构建申请）

- r5 Quick Tunnel 域名已随 cloudflared（PID 3868）终止死亡（Quick
  Tunnel 域名每次启动随机）→ 重启 Quick Tunnel（新域名）+ 服务实例
  （`Tools/ota/p3-3-service/`，按轮切 active-release toy-30204 /
  real-30205，同端口 8443）。
- 第六轮 APK 固化旧 endpoint → **申请 build-only dispatch 1 次**：
  注入新隧道 endpoint + `release_application_id_suffix=.p33verify`。
- **签名不兼容预案（申请采用独立并存包）**：CI debug 证书逐轮不同
  （第五轮 f5e838ef… vs 第六轮 f6c0f224… 实证），新 APK 无法覆盖安装
  p33acceptance → 新包名 `com.wen.gaia.gaia.p33verify` 全新安装。
  p33acceptance 在装包（第六轮证据）与生产包 com.wen.gaia.gaia
  原样保留，不卸载、不清数据。
- 新并存包为干净安装（无历史状态），OTA 全流程从头执行一遍，正是
  干净会话取证；同一 APK 两轮复用（服务端切 fixture）。

### 4.4 取证设计（先于操作启动，结束立即归档）

- **采集先行**：任何升级操作前，先启动 `adb logcat -v time` 持续落盘
  （.cache/p33-verify-r7/logcat-live-*.log，不清空不清 buffer）+ 服务
  日志 + 隧道日志落盘。
- **设备端 RTT**（申请 J-Link 只读授权）：升级期间 JLinkRTTLogger 采集
  BCB 状态机行（STAGED→APPLYING→CONFIRMED）；不烧录、不写 BCB、
  不主动复位（设备走自然状态机）。toy 轮可加 App 区读回比对（既有
  伪影仲裁方法）。
- **归档**：每轮结束立即停采集、落盘、登记 SHA-256+时间戳。
- **关联**：logcat ↔ 服务日志 ↔ RTT 三方时间戳对齐；App 请求以
  参数指纹（currentVersionCode/currentImageSha 全等）+时间窗与服务端
  请求行关联；六状态逐项绑定到具体行号。
- 用户全程手动操作 App（检查更新→下载→升级），可选手机自带录屏
  作为补充（非必需）。

### 4.5 次数与停止条件

| 项 | 限额 |
| --- | --- |
| 设备升级次数 | 至多 2 次（30204 toy → 30205 real） |
| 每轮主测 | 1 次 |
| harness 取证重试 | 每轮至多 1 次，且仅当取证故障（logcat/服务/隧道故障）且设备未离开起点版本——不消耗新目标版本 |
| 停止条件 | ①设备到达目标版本+复核 completed 即该轮结束；②PRODUCT_FAIL 判定事实成立即停（不盲重试，先留证分类）；③toy 轮 PRODUCT_FAIL 则 real 轮不启动，转缺陷修复流程；④设备状态异常（BCB 非 CONFIRMED/App 区异常）即停并留证 |

### 4.6 清理范围

只覆盖本批启动的：Quick Tunnel 进程、服务进程、logcat 采集进程、
RTT logger 进程；日志全部落项目内 `.cache/` 后按 PID 核验终止，
残留验证（端口/进程零残留）。不动 p33acceptance/生产包。

### 4.7 边界与授权申请汇总

| # | 申请项 | 说明 |
| --- | --- | --- |
| A1 | build-only dispatch ×1 | 新并存包 .p33verify + 新 endpoint（4.1+4.3） |
| A2 | 设备升级 ×2（30204/30205） | 固件自然状态机升级，含各自重启 |
| A3 | J-Link 只读（RTT 采集；toy 轮读回） | 不烧录、不写 BCB、不复位 |
| A4 | 服务+隧道启停（每轮切换+收尾清理） | 项目内进程 |
| A5 | 日志增强代码改动+自测+重冻结 v8 | flutter-dev-checks standing authorization 范围内自测；冻结走既有流程 |

**不申请**：回退烧录、BCB 写入、生产包/p33acceptance 任何操作、
新 OTA 协议改动（不为取证修改协议或升级行为——日志增强仅限
4.1 两个真实观测点）。

## 5. 交付与复验规则（遵循派单）

- 交付紧凑表：判据/状态 → 原始文件及 SHA → 实际观测 → 直接证据或
  推导 → 剩余缺口（手机接回补 C-APK-INSTALL 后随本文件更新）。
- 保留 v7 独立报告与终态矩阵原样（EVIDENCE_GAP 不改 PASS、不退
  NOT_RUN），不自验收。
- 仅手机只读核验+人证登记、实现/资产/门禁未变 → 不升合同；后继
  轮次由独立会话以 v7 终态矩阵为前驱安排。
- 补测若落地（新 APK/新目标/新服务身份）→ 后继合同 v8 如实更新
  身份；已 PASS 的 CI/构建按复用规则 REUSED（输入未失效时）。
- 本批不含 BLE 提速、后台传输、通知、P4-2，不扩大到完整 BCB 恢复
  战役。

## 6. 手机接回后只读取证（2026-09-15 执行）

### 6.1 C-APK-INSTALL 五段命令（v7 冻结原文逐字执行）

| 段 | 观测值 | 对基准 |
| --- | --- | --- |
| dumpsys 受验包 | versionCode=86（minSdk 24/targetSdk 36）/ versionName=1.0.60 | ✔ 合同 expected |
| pm path → adb pull | `/data/app/~~AsgJIVGo21x47nN9Tiqd3A==/com.wen.gaia.gaia.p33acceptance-RZZ2O2bVlZC0WK0ofIP3PQ==/base.apk` → `.cache/p3-3-v7-installed-base.apk`（1 file pulled, 0 skipped） | ✔ |
| 在装包 SHA-256 / 字节数 | `fb6a91e69a0ad30dc0b9c79a69c5e638d376898d6e313836191f2b40ebf80a13` / 46,699,144 B | **全等**第六轮受验 APK 基准 |
| 在装证书（java -jar apksigner.jar） | Signer #1 CN=Android Debug，证书 SHA-256 `f6c0f2247c5054fd5b9e0c2792db8edb8bf694776b9a29cb5b83cace30cdf44d` | **全等** C-RELEASE-BUILD 判据 2 实测基准（第六轮证书） |
| 生产包 com.wen.gaia.gaia 只读 | versionName=1.0.60，lastUpdateTime=**2026-07-10 19:05:06** | ✔ 全程未动（与 O5 记录一致） |

零安装/零卸载/零清数据/零权限改动；仅 dumpsys/pm path/pull/verify 四类只读操作。

### 6.2 补充只读检查（两项均无收获，与 §1 结论一致）

- **App 私存 firmware/ 目录**：release 包不可 run-as（`package not
  debuggable`）；外置私有目录
  `/sdcard/Android/data/com.wen.gaia.gaia.p33acceptance/` 不存在。
  深入读取需 root（写入级操作，不申请）。→ 在装第六轮 ETU 是否
  残留不可观测。
- **logcat 当前缓冲**：最早行 09-15 02:13:13（凌晨已清空过，晚于
  升级时段近 14 小时）；`grep -c '^09-14'` = 0；全缓冲 MONO_/OTA
  相关行 = 0。缓冲内有 09-15 09:5x 的 flutter 扫描行（App 今日
  正常使用），无任何升级时段痕迹。→ 佐证「App 侧历史证据不可恢复」。

### 6.3 C-APK-INSTALL 供独立验收复核的实测口径

本轮实现会话按 v7 冻结命令原文执行并登记（实现者不自验收）。单轮
判定与矩阵回填由独立验收会话完成；命令输出原文已在本节表格内，
pull 产物 `.cache/p3-3-v7-installed-base.apk`（SHA fb6a91e6…）可复核。

## 8. 补测资产批（2026-09-15 执行，操作单 §4.2/§4.3）

### 8.1 服务/隧道（r6 轮身份）

- Quick Tunnel：域名
  `checkout-sheep-full-evening.trycloudflare.com`（r6 隧道，cloudflared
  进程 PID 20712，`--no-autoupdate tunnel --url http://127.0.0.1:8443`，
  日志 `.cache/p3-3-cloudflared/tunnel-r6-20260915.log`，1 条 Registered
  tunnel connection）。预检无残留进程、8443 空闲。
- v7 服务实例：`Tools/ota/p3-3-service/service.py --config
  service_config.json --active-release toy-30204 --host 127.0.0.1 --port
  8443 --public-base-url https://checkout-sheep-full-evening.trycloudflare.com
  --log-file .cache/p3-3-v2-service/service-v7-toy-20260915.log`，python
  PID 23232（pid 文件 service-v7-toy.pid）。启动横幅五 fixture fail-closed
  核验通过（含 toy-30204 `284581:81a77336…` 与 real-30205
  `284590:32577aa5…`）。
- `service_config.json` 新增 `toy-30204`（3.2.4/30204，target
  43faf0ca…，asset 81a77336…/284,581B，path
  `.cache/p3-3-assets-v7/`）与 `real-30205`（3.2.5/30205，target
  ab8528ec…，asset 32577aa5…/284,590B）两条 release；既有三 fixture
  原样保留。本轮唯一 tracked 改动。

### 8.2 宿主检查（本机+公网，取证在操作前）

| 检查 | 结果 |
| --- | --- |
| 本机 latest（30203+3a282768… 参数） | 200 updateAvailable，release-30204/3.2.4/30204，target 43faf0ca…，downloadUrl 指向新隧道域名 |
| 公网 latest（经 Quick Tunnel） | 同上（requestId af69faac…） |
| 公网整包下载（Range 0-） | 206，284,581B，SHA-256 与 ETU 四元组第 3 行全等（81a77336…），`full==etu` True |
| 公网断点续传（Range 128-） | 206，284,453B，与 ETU[128:] 字节全等 |
| 闭区间 Range 0-63（负例） | 400 INVALID_PARAMETER「only single open range」——契约行为（App 只用开区间） |

探针产物：`.cache/p33-verify-r7/v7-download-probe.etu` /
`v7-download-probe-resume.bin` / `v7-download-probe-head.bin`。

### 8.3 .p33verify 并存 APK（build-only dispatch ×1，授权 A1）

- 构建命令：`gh workflow run build.yml --ref dev/flutter/apk/p3-3-admission
  -f publish_release=false -f replace_existing_release=false
  -f firmware_latest_url=https://checkout-sheep-full-evening.trycloudflare.com/api/public/firmware/latest
  -f release_application_id_suffix=.p33verify`。
- CI run 34923921739（Eitan-S-23/E-Track）：Build Android APK=success、
  Build Windows EXE=success、Detect changed paths=success、Pages/Release
  skipped，conclusion=success（watch 日志
  `.cache/p33-verify-r7/build-p33verify-watch.log` CI_EXIT=0）。
- CI 日志确认注入：`TRACE_RELEASE_APP_ID_SUFFIX: .p33verify`、
  `Release application id suffix enabled: .p33verify`。
- APK 三元组（`.cache/p3-3-apk-r7/ble-monitor-android.apk`）：
  - aapt badging：`package: name='com.wen.gaia.gaia.p33verify'
    versionCode='86' versionName='1.0.60'`（与 p33acceptance 同版本号，
    包名独立并存）。
  - 大小 46,699,140B；SHA-256
    `85ce64dfe7952e3de215a8bf38af5a0766122b6da2bc6aa002bca92f7b6223e9`。
  - apksigner verify --print-certs（build-tools r35，worktree 内工具）：
    Signer #1 CN=Android Debug，证书 SHA-256
    `6f51a6a64e21b50b0d7cace2fdf0ca4b978fbdff1814d7bbab90fad08832e658`
    （r7 轮 CI debug 证书，与第六轮 f6c0f224… 不同——签名不兼容预案
    生效：新包全新安装，不覆盖 p33acceptance）。
- endpoint 注入核验（APK 二进制扫描）：arm64/arm32 `libapp.so` 均含
  `https://checkout-sheep-full-evening.trycloudflare.com/api/public/firmware/latest`；
  旧 r5 域名与 `.invalid` 占位均不存在。
- 手机 10ADA4197U001CK 已连接（adb devices 确认）。

## 7. 状态

- 手机 10ADA4197U001CK 已接回，C-APK-INSTALL 五段只读取证完成
  （§6，全等：在装包=第六轮 APK 基准、在装证书=第六轮证书、生产包
  未动）。两项补充只读检查无收获（firmware 目录不可观测、logcat
  缓冲已清）。
- v7 终态矩阵中 C-APK-INSTALL 保持 ENV_BLOCKED（由独立会话以后继轮
  复核本轮 §6 实测，不自改）。
- 操作单（§4）已获用户批准并执行完毕：**两轮补测全部完成**。
  - toy 轮（30204）2026-09-15 11:37~11:43 实机闭环成功，六状态
    闭合（第 2 项为必经控制流推导、其余五项直接观测），证据归档
    `toy-loop-r7-evidence/`，交付表 `P3-3-toy-loop-r7-2026-09-15.md`；
    全黑截图误判（adb shell cat 二进制损坏）已修复（adb pull 重取）。
  - real 判据轮（30205）同日 13:41~13:46 实机闭环成功，六状态同构
    闭合（与 toy 轮同一 APK/同一 App 进程/同一服务隧道，两轮连续），
    证据归档 `real-loop-r7-evidence/`，交付表
    `P3-3-real-loop-r7-2026-09-15.md`；用户截图 UI 耗时 5分11秒与
    logcat 时间线吻合。升级次数限额 2/2 用满（§4.5）。
- 补测会话 11:51 起因网关 API 500 中断后，由收尾会话接手：完成 toy
  轮归档回写、执行 real 轮全部流程（服务切 real-30205 预检→采集→
  用户操作→归档回写）。
- 两轮证据采信与 C-TOY-LOOP/C-REAL-LOOP 判定属独立验收会话职权；
  本文件与两份交付表均为实现侧事实登记，不预判判定结果；v7 报告
  与终态矩阵原样保留。v8 重冻结（新 freeze_commit/新 APK/新目标
  身份）由独立会话以 v7 终态矩阵为前驱安排。
