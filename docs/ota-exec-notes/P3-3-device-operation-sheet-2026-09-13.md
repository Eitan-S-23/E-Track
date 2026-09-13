# P3-3 实机合并操作单（第五版）—— 2026-09-13

> 第四版修订依据：同日第四轮裁定。**第五版修订依据：用户集中执行授权
> `P3-3-EXEC-AUTH-20260913`**（2026-09-13，五节全文），变化点：
> - **HTTPS 路线直接确定**（第二节）：Quick Tunnel 为主线（测试专用、
>   不用 CF 账号、不读 token；先启动隧道取得实际 HTTPS 地址 → 宿主端到端
>   检查 → 注入唯一一次受验 APK 构建 → 绑定进合同）。域名/DNS token/
>   证书策略不再要求用户提供；路线 A/B 降为 Quick Tunnel 不可用时的
>   替代申报。**本路线不需要 adb reverse**，不创建、不删除任何映射。
> - **安装策略确定**（第四节）：受验 APK 使用显式启用的专用并存
>   applicationId `com.wen.gaia.gaia.p33acceptance`（release 构建注入，
>   生产默认包名不变）；既有安装 `com.wen.gaia.gaia` 不卸载、不清数据。
> - **O1-O5 与 REC0-REC7 均已获条件授权**（第三、四节）：以独立复核通过
>   （操作单本版 + 恢复方案 v5）为前置，状态一律标「已授权，待前检/执行」，
>   不再写「全部未授权」。
> - **恢复方案升 v5**（第三节）：S1a/S1b 失效时序前移、FR4 备用会话替代
>   REC5（复位恒 6、会话恒 10）、备份不裁剪、额度总账对齐；执行入口
>   `Tools/jlink/p3-3-recovery-execute.ps1`（分 Phase，fail-closed）。
> - 执行顺序按第五节：安全准备、HTTPS 检查和 APK 构建可独立推进，不必
>   先操作设备；准备充分后再安排恢复和升级。
> - 其余（O1 双侧完整证书指纹实测、O3/O4 终点双值、失败即停、J-Link 不
>   并入 O 序列）沿用第四版，继续有效。
>
> **性质**：申报文档（已获条件授权，待独立复核与前检）。取代同日前四版
> 操作单（保留为历史，以本版为准）。

## 1. 设备与资产身份（执行前逐项绑定实物哈希）

| 项 | 身份 | 状态 |
| --- | --- | --- |
| 测试手机 | vivo V2312A，序列号 `10ADA4197U001CK`，Android 13（SDK 33）；既有安装 `com.wen.gaia.gaia` 1.0.60(86) release（APK SHA `428a5d3a…`，2026-06-30 首装，历史动作不追认）——**本轮不动该安装** | 沿用 B1-M r1 identity.md |
| 目标板 | AT32F435RGT7；板上 App 3.2.0(30200)（finalize 头双零摘要链已核）；Boot=磁盘 `X-Track-Boot.bin` 原版 | 板识别文档（2026-09-12） |
| 板上 BCB 起点 | **恢复执行前**：CONFIRMED cur_vcode=20801（阻断态）；**恢复执行后（O 序列合法起点）**：CONFIRMED cur_vcode=30200（v5 §5 完成判据四条全满足） | 恢复方案 v5 §5 |
| 受验 APK | 经 build.yml dispatch 构建注入 `firmware_latest_url=https://<隧道地址>/api/public/firmware/latest`（endpoint 方式 iii）+ **release 侧并存 applicationId 后缀 `.p33acceptance`**（`TRACE_RELEASE_APP_ID_SUFFIX` 机制，默认空=生产包名不变）；绑定包名 `com.wen.gaia.gaia.p33acceptance`、versionCode、APK SHA-256、证书指纹实测值（apksigner verify --print-certs） | **已授权，待前检/执行**：保留现有同一笔 build-only 1 次额度（不追加），Quick Tunnel 宿主检查（服务文档 §5.2）通过后使用 |
| toy 包 | `e-track-at32f435-v3.2.1-full.etu`（284092B，SHA `fc4ae5a9…`）；终点基准=镜像 raw SHA `43ee943a…` + vcode 30201 | 已离线制包；作为受控服务 fixture（config 四元组冻结） |
| 真包 | `e-track-at32f435-v3.2.2-full.etu`（284112B，SHA `0a2eb26a…`）；终点基准=镜像 raw SHA `c9582213…` + vcode 30202 | 同上 |
| 受控 v2 测试服务 | `Tools/ota/p3-3-service/` 四件套：`service.py` `f71012de…` / `service_config.json` `2facafa6…` / `selftest.py` `b96d4e2f…`（16 项宿主自测 PASS）/ `tls_hostcheck.py` `f9202b6b…`（宿主 HTTPS 全链 PASS）；runner 依赖经 Validation profile required_paths 冻结；endpoint 经 dispatch 输入注入 APK | 已实现冻结；**HTTPS 路线已定 Quick Tunnel（服务文档 §5.1，已授权待前检/执行）**；D1-D5 部署序列见服务文档 §6 |

## 2. 执行前置链（O 序列开始前须全部完成；三项可并行推进——授权第五节）

```
P1 受控 v2 服务及资产准入（四件套冻结版本 + fixture 四元组经非实现
   会话审定）+ Quick Tunnel 启动与宿主端到端检查（服务文档 §5.1/§5.2/
   §6 D1/D2：隧道地址取得、latest/下载/证书链/暴露面四项全过）
P2 同一受验 APK 身份确定（dispatch 注入隧道 https URL + release 侧
   .p33acceptance 后缀的唯一一次 build-only 构建；APK SHA-256 +
   apksigner 证书指纹实测留档；并存安装策略已写入合同）
P0 BCB 恢复流程全部完成（恢复方案 v5 S1a-S6 / REC0-REC7 执行完毕，
   §5 完成判据四条全满足：生产 Boot 已按全区恢复+核验、App 身份未变
   (30200)、BCB 与 App 一致(cur_vcode=30200)、生产 App RTT 新鲜自报）
P3 用户审批冻结合同（FROZEN）+ validate_bundle NOT_RUN 前检通过
→ O1 → O2 → O3（toy 闭环）
→ 【O3 PASS 后】受控服务 D4 切换（只停服务 → --active-release real-30202
   重启；**隧道进程与公网地址不变**）→ O4 → O5 → D5 完整清理
```

- **顺序说明**（授权第五节原文口径）：安全准备、HTTPS 检查和 APK 构建
  （P1/P2）可独立推进，不必先操作设备（P0）；准备充分后再安排恢复和
  升级，避免设备长期停留在测试状态。P1-P3 任意项未完成时不开始 O1。
- **8 小时窗口时序约束**：Quick Tunnel 窗口自 D1 启动起计；受验 APK 构建
  与 O1-O5 全部活动须落在窗口内。执行顺序为 D1 隧道+服务 → D2 宿主检查
  → P2 受验 APK 构建 → P0/P3 收尾核对 → O1-O5 → D5。窗口内未完成即
  暂停并申报，不自动续窗口、不换地址、不追加 APK 构建。
- 云端 staging 写入路线（R2 上传、D1 登记、stable publish）维持冻结
  （云端写入单 B0-B4），不再是本单前置。
- **手机首次网络观测留在 O2**：P1-P3 准入证据不通过提前操作手机补齐。

## 3. 阶段 0：BCB 恢复（独立授权项 REC0-REC7；已授权，待独立复核后执行）

- 完整方案：`P3-3-bcb-recovery-plan-2026-09-13-v5.md` §3 S1a-S6
  （**S1a 同一 J-Link 连接内完成 REC0 Boot 全区备份（0x08000000-
  0x08004FFF，20,480B，含生产 Boot 前缀锚点断言与尾部 5,756B 原值 SHA
  登记）+ REC1 烧录测试 Boot + RAM magic 失效（测试 Boot 首启前实测
  失效并验证）** → S1b 复位① → SNAPSHOT 基线（BCB 双块 128B 原始字节
  强制留档，不裁剪）→ CLEAR_BCB（EEPROM 0x00-0x7F 写全 0xFF）→ 复位④
  触发状态机 commit_confirmed 重建 + RTT 采集 → SNAPSHOT 终态核验
  （arg1=0 含内部 App 快照；FR4 触发时被备用会话替代，复位恒 6、会话
  恒 10）→ S6 Boot 全区恢复（loadbin 备份 + verifybin + 全区读回 SHA
  全等）+ 复位⑥ + RTT 终证；App 镜像全程零写入）。配套构建与命令离线
  验证见 `P3-3-recovery-boot-build-2026-09-13.md`（13/13 PASS）与
  `Tools/jlink/test-p1-6-recovery-cmd.ps1`（24/24 PASS，受管 runner）。
- 执行入口：`Tools/jlink/p3-3-recovery-execute.ps1`（分 Phase
  S1A/S1B/S2/S3/S4/S5/S6，每 Phase 主机侧 fail-closed 断言 + result.json
  留证；前置链检查 `Assert-P33PriorPhase`；无一键 ALL 模式，逐 Phase
  核对证据后推进）。
- 授权额度（v5 §7，对齐 P3-3-EXEC-AUTH-20260913 第三节）：命令会话
  **恰好 10**、RTT logger **2**（每个 ≤120s）、主动复位 **6**、身份/RTT
  签名核对会话 **≤2**（不写块不复位）；REC6 失败收尾与成功路径共用同
  一额度；计划外 nRESET 单步 ≥2 次或全程累计 >2 次即停；Flash 边界限定
  0x08000000-0x08004FFF，RAM 控制块 0x20057E00-0x20057FFF；EEPROM
  0x00-0x7F 经既有 CLEAR_BCB 清空；**不授权** App 烧录、QSPI 槽写入、
  断电注错或其他测试 opcode。恢复授权与 O 序列、历史 A1/B1-M 配额
  不互借。
- RTT 采集纪律（REC4/REC7）：v5 §8 数值化条款（120s 硬超时、每编号至多
  1 个 logger、启动前清残留、map 严格符号行 + 签名验证、复位会话内
  Sleep 8000 先让自报行落入 buffer）。
- 完成判据：v5 §5 四条（生产 Boot 全区恢复+核验、App 身份未变、BCB 与
  App 一致 cur_vcode=30200、生产 App RTT 新鲜自报）全满足，留证回填
  合同 EXT-BOARD-STATE。

## 4. 操作序列 O1-O5（每项含命令/超时/次数/失败处理/证据路径；已授权，待前检/执行）

授权口径（第四节原文）：恢复完成、服务与资产准入、合同冻结和 NOT_RUN
前检通过后，授权指定测试手机与已绑定目标板执行 O1 一次 5 分钟、O2 一次
10 分钟、O3 一次 30 分钟、O4 一次 30 分钟、O5 一次 5 分钟；包括该 App
必要的正常 BLE 权限授予、目标板连接，以及正常 OTA 所需的候选/备份槽、
App Flash、BCB 更新和固件重启；不包括通过 J-Link 直接刷 App 或注错。

### O1 受验 APK 身份/签名预检 + 并存安装 + 启动

**安装策略（已按授权第四节确定，构建前写入合同）**：受验 APK 使用专用
并存 applicationId `com.wen.gaia.gaia.p33acceptance`；既有安装
`com.wen.gaia.gaia` 全程不动——**不卸载、不清数据**（任何情况下不得以
卸载或清数据解决签名冲突；并存包名下也不存在覆盖冲突）。

**双侧证书指纹实测（沿用第三轮裁定方法，全部实测留档）**：

1. **既有安装侧**（只读，可在受验 APK 构建前先行执行）：
   `adb -s 10ADA4197U001CK shell dumpsys package com.wen.gaia.gaia`
   → 从 `codePath`/`baseCodePath` 取既有安装 APK 的设备侧真实路径 →
   `adb pull <设备侧APK路径> evidence/o1-existing.apk` →
   `apksigner verify --print-certs evidence/o1-existing.apk`
   （完整证书指纹，SHA-256 digest 留档）。
2. **受验侧**：`apksigner verify --print-certs <受验APK>`（构建产物
   实测；**不同 CI run 的 debug 签名不能假定相同**，以本次实测为准）。
3. **记录与用途**：两侧指纹逐项登记留证；因包名并存，指纹差异**不构成
   安装阻断**——本比对用于证明并存策略的必要性与受验侧签名身份绑定。
   若出现受验 APK 包名不是 `com.wen.gaia.gaia.p33acceptance`（构建注入
   失效）→ 停在安装前报 ENV_BLOCKED，不消耗安装动作。

| 项 | 内容 |
| --- | --- |
| 预检命令 | 双侧 apksigner 完整证书指纹（方法见上）；`adb shell dumpsys package com.wen.gaia.gaia.p33acceptance` 确认安装前不存在（全新安装） |
| 安装 | `adb -s 10ADA4197U001CK install -r <apk>`（并存包名全新安装；既有 `com.wen.gaia.gaia` 不受影响） |
| 启动与权限 | 手动/monkey 启动 App；**正常 BLE 权限授予**（Android 13 运行时权限 BLUETOOTH_CONNECT/BLUETOOTH_SCAN/BLUETOOTH_ADVERTISE 按系统弹窗或 `adb shell pm grant` 正常授予——授权第四节明示包含）；`adb logcat -v time > evidence/o1-install.log`（受控采集，**不清缓冲**：不执行 `logcat -c`） |
| 超时 / 次数 | 5 min / 各命令 1 次（预检只读不限，但每会话采集一次为准） |
| 留证 | 安装结果、受验包名/versionCode 实测、双侧 apksigner 完整证书指纹输出、既有安装 APK pull 回件 SHA-256、受验 APK SHA-256（与服务 fixture 同源核对）、既有安装未被触碰的 dumpsys 只读确认、启动 logcat；路径 `evidence/o1-*.log`、`evidence/o1-existing.apk` |
| 失败处理 | 安装失败（如存储不足）→ ENV_BLOCKED 留证停；包名注入失效/签名异常 → 上述停报（不卸载/不清数据、不改装非受验 APK） |

### O2 App 对受控服务真实 latest/下载请求观测

| 项 | 内容 |
| --- | --- |
| 操作 | App 内进入固件升级入口，触发 latest 检查与下载（观测插桩 `OTA_OBS` 日志经 logcat 采集）；endpoint = 受验 APK 构建时注入的 Quick Tunnel https URL（服务文档 §5.1），证书为 Cloudflare 边缘公共可信链（App 校验不放宽） |
| 核对 | App 日志证明请求打到受控服务 endpoint（非 legacy GitHub 路径）；latest 响应解析 v2 成功；token 下载链走真实 `/api/public/firmware/download`（非静态直链）；整包 SHA 校验通过（`fc4ae5a9…`） |
| 超时 / 次数 | 10 min / 1 次 |
| 留证 | `evidence/o2-latest-download.log`（logcat 全程）+ 服务端请求日志 `<repo>/.cache/p3-3-v2-service/service.log`（服务文档 §6 D3 持续采集，每请求一行含 requestId，与 App logcat 的 requestId 交叉核对） |
| 失败处理 | 网络不可达/服务 5xx/隧道退出 → ENV_BLOCKED，不动设备（隧道地址改变或退出时暂停相关阶段，不偷偷换地址、不自动消耗额外 APK 构建）；解析失败 → HARNESS_FAIL（服务配置）或 PRODUCT_FAIL（App 解析）按日志分类留证停——**不自动重试** |

### O3 toy 3.2.1 闭环（App→BLE→MCU 传输→STAGED→重启→GET_INFO 终点核对）

| 项 | 内容 |
| --- | --- |
| 操作 | 在 O2 基础上继续 App 升级流程：目标板连接 → BEGIN/DATA 传输→END→确认提交→设备重启→**新连接** GET_INFO |
| 共同终点 | 重启后新连接 GET_INFO 返回 versionCode **30201** 且完整 raw SHA-256 为 **`43ee943a185f63d70284c7c5a9992d677a9bf8c518dacd2e63df8ec7e5809b55`**（与冻结 toy 目标镜像一致） |
| **不含** | ~~"预期 BCB 拒绝"观测点~~（已删除：恢复完成后 385 前置应满足；若仍出现拒绝，即为真实 PRODUCT_FAIL，非预期行为，按失败处理流程留证停） |
| BCB 授权口径 | **禁止未经授权的直接 BCB 改写或绕过检查；正常 OTA 流程中由固件执行的 BCB 状态转换（STAGED→APPLYING→TEST_BOOT→CONFIRMED）、候选/备份槽与 App Flash 写入、固件重启均包含在授权第四节获批范围内**——固件正常状态机推进是闭环本身的组成部分；通过 J-Link 直接刷 App 或注错明确不授权 |
| 超时 / 次数 | 30 min 传输窗口（`MONO_*` 插桩口径：FAIL_AT 按中止决定时刻计，收尾时长单列观测不设门槛）/ 1 次 |
| 留证 | `evidence/o3-toy-loop.log`（logcat 全程，含 OTA_OBS 状态链 6 态）、GET_INFO 终点两条实测值 |
| 失败处理 | 传输/提交失败：**不得一概假定设备处于 STAGED**——以重启后（或断连前最后一次）GET_INFO/设备状态实测分类；不自动恢复、不自动重试、不自动进入 O4；按 MONO 插桩留证分类 PRODUCT_FAIL/HARNESS_FAIL 后停报。失败留证，不互借历史 A1/B1-M 额度 |

**O3 → O4 门禁**：O3 PASS（终点双值核对通过）后，受控服务按 D4 切换
（**只停服务** → `--active-release real-30202` 重启，启动日志留证；
**隧道进程与公网地址维持不变**——授权第二节原文），toy 成功**且仅在其
成功后**才激活真包并进 O4。任一不满足即停。

### O4 真包 3.2.2 闭环（同 O3，目标 30202）

| 项 | 内容 |
| --- | --- |
| 操作 | 同 O3（App 重新触发 latest：此时应取到 30202 fixture） |
| 共同终点 | 重启后新连接 GET_INFO 返回 versionCode **30202** 且完整 raw SHA-256 为 **`c958221392fade8b40520df2d7fd4278632d64bcdd8261b0ac7536c6468a7f39`** |
| 约束 | 不得由 toy 结果代替；与 O3 分别绑定各自终点双值 |
| 超时 / 次数 / 失败处理 | 同 O3 |

### O5 验收后只读身份复核

| 项 | 内容 |
| --- | --- |
| 操作 | App 侧 GET_INFO 只读复核（版本/raw SHA）；`adb shell dumpsys package com.wen.gaia.gaia.p33acceptance` 与 `com.wen.gaia.gaia` 双包名只读（受验安装未被动过、既有安装仍未被触碰）；不写任何设备状态 |
| 超时 / 次数 | 5 min / 1 次 |
| 留证 | `evidence/o5-final-identity.log` |

## 5. J-Link 连接/采集（独立授权项，不并入 O 序列"只读预检"）

- 依据用户裁定：可能触发复位的 J-Link 连接不能按"只读"免费夹带。O3/O4 的
  全部判定证据以 **App 侧 logcat（OTA_OBS 状态链 + GET_INFO 终点）**为准，
  设计上**不依赖 J-Link**。
- 授权第四节的 O 序列授权**不包括通过 J-Link 直接刷 App 或注错**；BCB
  恢复阶段的 J-Link 操作属阶段 0 独立授权（恢复方案 v5 §7），与 O 序列
  分离。
- 若验收会话判断需要额外 RTT/J-Link 补充采集，单独列项申报，获批后
  执行——本单 **不包含**任何 O 序列期间的新增 J-Link 操作。

## 6. 明确不含的操作（须单独列项审批才可能执行）

- 断电注错实验：两个正常成功闭环不默认需要；确需时单独说明原因列项。
- 任何烧录（App/Boot/BCB 直写）：O 序列零烧录；BCB 恢复的烧录在阶段 0
  独立授权（Flash 边界 0x08000000-0x08004FFF）。
- 额外 B1-M 实验（PC 蓝牙适配器路径）：同上。
- 卸载/清手机数据：任何情况下不得以卸载或清数据解决签名冲突；本轮并存
  包名策略下既有安装全程不动。
- **额度互借：REC0-REC7（BCB 恢复）、B1-M 与升级闭环额度不得互借**
  （用户原文；恢复项独立 REC 编号，不与历史 A1 混淆）。
- 自动恢复/自动重试/自动进入下一阶段：全部失败分支均"留证停报"。

## 7. 授权配额（O 序列；已授权，待前检/执行；阶段 0 见恢复方案 v5 §7，服务部署见服务文档 §6）

| # | 操作 | 次数 | 超时 |
| --- | --- | --- | --- |
| O1 | 签名预检（只读）+ 并存安装 + BLE 权限 + 启动采集 | 1 | 5 min |
| O2 | latest/下载观测（App 操作 + logcat） | 1 | 10 min |
| O3 | toy 30201 闭环（含设备重启 1 次——固件正常状态机行为） | 1 | 30 min 窗口 |
| O4 | 真包 30202 闭环（含设备重启 1 次） | 1 | 30 min 窗口 |
| O5 | 只读身份复核（双包名） | 1 | 5 min |

- 受验 APK 构建配额：**保留现有同一笔 build-only 1 次额度**（授权第四
  节原文，不重复追加）；`publish_release=false`、
  `replace_existing_release=false`，Pages/Release 不得执行。
- 设备重启发生在 OTA 闭环内部（升级提交后固件自复位），属获批操作范围内
  的固件状态转换，不另计"复位操作"。
- 受控服务与隧道部署序列（D1 服务+隧道启动 / D2 宿主端到端检查 / D3
  观测期日志 / D4 toy→真包切换（隧道不动）/ D5 完整清理+无残留验证）按
  服务文档 §6 执行；隧道窗口最长 8 小时，本轮结束或到期即关闭；无
  adb reverse；不新增云端写入（云端路线整体冻结）。
- J-Link 不含在 O 序列（§5 独立授权项，维持既有裁定口径）。

## 8. 边界声明

- 本单 O1-O5 与阶段 0 REC0-REC7 均已获 P3-3-EXEC-AUTH-20260913 条件
  授权；**尚未执行**——前置（独立复核通过、P1-P3 全部完成、NOT_RUN
  前检通过）满足后方可开工。
- **手机首次网络观测留在 O2**：P1-P3 准入证据不通过提前操作手机补齐；
  HTTPS 可用性以服务文档 §5.2 Quick Tunnel 宿主检查为准。
- 与合同的关系：本单是合同 C-APK-INSTALL/C-TOY-LOOP/C-REAL-LOOP 判据的
  真机执行载体；冻结时合同 commands 按本单逐项绑定精确命令与证据路径
  （含并存 applicationId 安装策略与隧道地址回填规则）。
- 本单所有设备身份引用既有只读证据（板识别/B1-M identity）；执行前由验收
  会话重测核对（板状态以阶段 0 恢复后为准）。
