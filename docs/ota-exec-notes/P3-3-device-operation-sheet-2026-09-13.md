# P3-3 实机合并操作单（第三版，待集中审批）—— 2026-09-13

> 依据：用户 2026-09-13 分项批复第 7 条（O1-O5 现版不予整单批准，修改后
> 集中提交）与第三轮裁定第 4 条。本版（第三版）修订：补身份/签名预检；
> BCB 恢复列为独立准备操作（阶段 0，排在一切升级闭环之前）；正式升级的
> 前置链改写死为「**恢复流程全部完成 + 受控 v2 服务及资产准入 + 同一受验
> APK 身份确定 + 用户审批冻结合同 + FROZEN/NOT_RUN 前检通过**」；云端
> staging 路线暂停，服务侧改走受控 v2 测试服务（D1-D5 部署申请）；O1 双侧
> 证书比对改用**可比的完整证书指纹**（既有安装 dumpsys 取 APK 路径 →
> adb pull → apksigner verify --print-certs，双侧同格式比对）；安装策略
> 在唯一一次受验构建前确定；删除"预期 BCB 拒绝"观测点；toy 闭环终点核对
> （30201 + 完整 raw SHA）通过后才激活真包并进 O4；失败后不假定 STAGED、
> 不自动恢复/重试/进入下一阶段；J-Link 仍不含在 O 序列。
>
> **性质**：申报文档。全部操作均未授权、未执行。取代
> `P3-3-admission-remediation-2026-09-12.md` §11 框架与同日前两版操作单
> （保留为历史，以本版为准）。

## 1. 设备与资产身份（执行前逐项绑定实物哈希）

| 项 | 身份 | 状态 |
| --- | --- | --- |
| 测试手机 | vivo V2312A，序列号 `10ADA4197U001CK`，Android 13（SDK 33）；既有安装 `com.wen.gaia.gaia` 1.0.60(86) release（APK SHA `428a5d3a…`，2026-06-30 首装，历史动作不追认） | 沿用 B1-M r1 identity.md |
| 目标板 | AT32F435RGT7；板上 App 3.2.0(30200)（finalize 头双零摘要链已核）；Boot=磁盘 `X-Track-Boot.bin` 原版 | 板识别文档（2026-09-12） |
| 板上 BCB 起点 | **恢复执行前**：CONFIRMED cur_vcode=20801（阻断态）；**恢复执行后（O 序列合法起点）**：CONFIRMED cur_vcode=30200（§5 完成判据四条全满足） | 恢复方案 v3 §5 |
| 受验 APK | 经 build.yml dispatch 输入 `firmware_latest_url=<受控 v2 服务URL>` 构建（endpoint 方式 iii）；绑定包名/versionCode/APK SHA-256/**证书指纹实测值**（apksigner verify --print-certs） | 待构建（追加 1 次 build-only 配额=上一封已批同一额度的确认，服务就绪后使用） |
| toy 包 | `e-track-at32f435-v3.2.1-full.etu`（284092B，SHA `fc4ae5a9…`）；终点基准=镜像 raw SHA `43ee943a…` + vcode 30201 | 已离线制包；作为受控服务 fixture（config 四元组冻结） |
| 真包 | `e-track-at32f435-v3.2.2-full.etu`（284112B，SHA `0a2eb26a…`）；终点基准=镜像 raw SHA `c9582213…` + vcode 30202 | 同上 |
| 受控 v2 测试服务 | 项目内受控服务（`docs/ota-exec-notes/tools/p3-3-v2-service/` 三件套：`service.py` `98695057…` / `service_config.json` `bb33724…` / `selftest.py` `60a414a…`；13 项宿主自测 PASS）；endpoint 经 dispatch 输入注入 APK | 已实现冻结；D1-D5 部署申请待批（服务文档 §6） |

## 2. 执行前置链（全部满足才可开始 O 序列；2026-09-13 第三轮裁定原文口径）

```
P0 BCB 恢复流程全部完成（恢复方案 v3 S1-S6 / REC1-REC7 执行完毕，
   §5 完成判据四条全满足：生产 Boot 已恢复+核验、App 身份未变(30200)、
   BCB 与 App 一致(cur_vcode=30200)、生产 App RTT 新鲜自报）
P1 受控 v2 服务及资产准入（服务三件套冻结版本 + fixture 四元组经非实现
   会话审定；D1-D5 部署申请获批；回环域名/端口/证书执行前人工验证完成）
P2 同一受验 APK 身份确定（dispatch 注入受控服务 URL 的唯一一次 build-only
   构建；APK SHA-256 + apksigner 证书指纹实测留档；安装策略已按 §4 O1
   在构建前确定）
P3 用户审批冻结合同（FROZEN）+ validate_bundle NOT_RUN 前检通过
→ O1 → O2 → O3（toy 闭环）
→ 【O3 PASS 后】受控服务 D4 切换（停服务 → --active-release real-30202
   重启；不再是云端 stable publish）→ O4 → O5
```

- 云端 staging 写入路线（原 P1/P5 的 R2 上传、D1 登记、stable publish）
  已按第三轮裁定**暂停**（云端写入单 B0-B4 冻结），不再是本单前置。

## 3. 阶段 0：BCB 恢复（独立准备操作，不属本操作单判据）

- 完整方案：`P3-3-bcb-recovery-plan-2026-09-13-v3.md` §3 S1-S6
  （P1_6_TEST_ENABLE 版 Boot 烧录 → SNAPSHOT 基线 → CLEAR_BCB → 显式
  复位触发状态机 commit_confirmed 重建 → SNAPSHOT 终态核验 → 烧回生产
  Boot；**复位合计 6 次**；BCB 原始 128B 字节快照留档[若 S2 未裁剪]；
  App 镜像全程不动）。配套构建与命令离线验证见
  `P3-3-recovery-boot-build-2026-09-13.md`（13/13 PASS）。
- 授权申报：该文档 §7（**REC1-REC7** 独立编号：烧 P1_6 Boot / SNAPSHOT
  基线 / CLEAR_BCB / 显式复位+RTT / SNAPSHOT 验证 / 烧回生产 Boot /
  RTT 终证）——**单独审批，与 O 序列额度不互借，与历史 A1/B1-M 配额
  不混淆**。
- 完成判据：该文档 §5 四条（生产 Boot 恢复+核验、App 身份未变、BCB 与
  App 一致 cur_vcode=30200、生产 App RTT 新鲜自报）全满足，留证回填
  合同 EXT-BOARD-STATE。

## 4. 操作序列 O1-O5（每项含命令/超时/次数/失败处理/证据路径）

### O1 受验 APK 身份/签名预检 + 安装 + 启动

**双侧证书比对方法（2026-09-13 第三轮裁定修订：必须用可比的完整证书
指纹，dumpsys 的签名摘要行不作比对依据）**：

1. **既有安装侧**（只读，可在受验 APK 构建前先行执行）：
   `adb -s 10ADA4197U001CK shell dumpsys package com.wen.gaia.gaia`
   → 从 `codePath`/`baseCodePath` 取既有安装 APK 的设备侧真实路径 →
   `adb pull <设备侧APK路径> evidence/o1-existing.apk` →
   `apksigner verify --print-certs evidence/o1-existing.apk`
   （得到既有安装的**完整证书指纹**，SHA-256 digest 留档）。
2. **受验侧**：`apksigner verify --print-certs <受验APK>`（构建产物
   实测；**不同 CI run 的 debug 签名不能假定相同**，以本次实测为准，
   不以历史 run 推定）。
3. **比对**：两侧 apksigner 输出的 signer certificate SHA-256 digest
   逐一全等 → 继续；**不一致 → 停在安装前**，保留既有安装与数据，
   报用户裁定（不默认卸载/清数据——签名冲突在任何情况下不得通过
   卸载或清数据解决）。

**安装策略前置确定（唯一一次受验构建之前）**：受验 APK 构建消耗的是
唯一一次 build-only 配额（与上一封批复为同一额度），因此既有安装侧
证书指纹必须**在构建前**先行实测（上述步骤 1 只读、不依赖受验 APK），
并把完整安装策略写入冻结合同：指纹一致预期路径、不一致时停在安装前
（ENV_BLOCKED，配额消耗如实登记，不卸载不清数据）、不因冲突改用
非受验 APK 替代安装。策略在构建前冻结，装机时不再临场改。

| 项 | 内容 |
| --- | --- |
| 预检命令 | 双侧 apksigner 完整证书指纹（方法见上）；`adb shell dumpsys package` 只读采集包名/versionCode |
| 比对 | 两侧 SHA-256 digest 全等 → 继续；不一致 → 停在安装前（见上） |
| 安装 | `adb -s 10ADA4197U001CK install -r <apk>`（`-r` 保留数据覆盖安装；签名不一致时此命令不会执行） |
| 启动 | 手动/monkey 启动 App；`adb logcat -v time > evidence/o1-install.log`（受控采集，**不清缓冲**：不执行 `logcat -c`） |
| 超时 / 次数 | 5 min / 各命令 1 次（预检只读不限，但每会话采集一次为准） |
| 留证 | 安装结果、包名/versionCode 实测、双侧 apksigner 完整证书指纹输出、既有安装 APK pull 回件 SHA-256、受验 APK SHA-256（与服务 fixture 同源核对）、启动 logcat；路径 `evidence/o1-*.log`、`evidence/o1-existing.apk` |
| 失败处理 | 安装失败（非签名冲突，如存储不足）→ ENV_BLOCKED 留证停；签名冲突 → 上述停报（不卸载/清数据） |

### O2 App 对受控服务真实 latest/下载请求观测

| 项 | 内容 |
| --- | --- |
| 操作 | App 内进入固件升级入口，触发 latest 检查与下载（观测插桩 `OTA_OBS` 日志经 logcat 采集） |
| 核对 | App 日志证明请求打到受控服务 endpoint（非 legacy GitHub 路径）；latest 响应解析 v2 成功；token 下载链走真实 `/api/public/firmware/download`（非静态直链）；整包 SHA 校验通过（`fc4ae5a9…`） |
| 超时 / 次数 | 10 min / 1 次 |
| 留证 | `evidence/o2-latest-download.log`（logcat 全程）+ 服务端请求日志 `<repo>/.cache/p3-3-v2-service/service.log`（受控服务 D3 持续采集，每请求一行含 requestId，与 App logcat 的 requestId 交叉核对——不再依赖云端写入单执行方） |
| 失败处理 | 网络不可达/服务 5xx → ENV_BLOCKED，不动设备；解析失败 → HARNESS_FAIL（服务配置）或 PRODUCT_FAIL（App 解析）按日志分类留证停——**不自动重试** |

### O3 toy 3.2.1 闭环（App→BLE→MCU 传输→STAGED→重启→GET_INFO 终点核对）

| 项 | 内容 |
| --- | --- |
| 操作 | 在 O2 基础上继续 App 升级流程：BEGIN/DATA 传输→END→确认提交→设备重启→**新连接** GET_INFO |
| 共同终点 | 重启后新连接 GET_INFO 返回 versionCode **30201** 且完整 raw SHA-256 为 **`43ee943a185f63d70284c7c5a9992d677a9bf8c518dacd2e63df8ec7e5809b55`**（与冻结 toy 目标镜像一致） |
| **不含** | ~~"预期 BCB 拒绝"观测点~~（已删除：恢复完成后 385 前置应满足；若仍出现拒绝，即为真实 PRODUCT_FAIL，非预期行为，按失败处理流程留证停） |
| BCB 授权口径 | **禁止未经授权的直接 BCB 改写或绕过检查；正常 OTA 流程中由固件执行的 BCB 状态转换（STAGED→APPLYING→TEST_BOOT→CONFIRMED）包含在本操作单获批范围内**——即本单不写"全程不写 BCB"，固件正常状态机推进是闭环本身的组成部分 |
| 超时 / 次数 | 30 min 传输窗口（`MONO_*` 插桩口径：FAIL_AT 按中止决定时刻计，收尾时长单列观测不设门槛）/ 1 次 |
| 留证 | `evidence/o3-toy-loop.log`（logcat 全程，含 OTA_OBS 状态链 6 态）、GET_INFO 终点两条实测值 |
| 失败处理 | 传输/提交失败：**不得一概假定设备处于 STAGED**——以重启后（或断连前最后一次）GET_INFO/设备状态实测分类；不自动恢复、不自动重试、不自动进入 O4；按 MONO 插桩留证分类 PRODUCT_FAIL/HARNESS_FAIL 后停报 |

**O3 → O4 门禁**：O3 PASS（终点双值核对通过）后，受控服务按 D4 切换
（停服务 → `--active-release real-30202` 重启，启动日志留证），toy 成功
**且仅在其成功后**才激活真包并进 O4。任一不满足即停。

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
| 操作 | App 侧 GET_INFO 只读复核（版本/raw SHA）；`adb shell dumpsys package` 只读（安装未被动过）；不写任何设备状态 |
| 超时 / 次数 | 5 min / 1 次 |
| 留证 | `evidence/o5-final-identity.log` |

## 5. J-Link 连接/采集（独立授权项，不并入 O 序列"只读预检"）

- 依据用户裁定：可能触发复位的 J-Link 连接不能按"只读"免费夹带。O3/O4 的
  全部判定证据以 **App 侧 logcat（OTA_OBS 状态链 + GET_INFO 终点）**为准，
  设计上**不依赖 J-Link**。
- 若验收会话判断需要 RTT/J-Link 补充采集，单独列项申报（连接次数、地址、
  采集窗口、nRESET 回退风险按恢复方案 §4 A2 口径），获批后执行——本单
  **不包含**任何 J-Link 操作。

## 6. 明确不含的操作（须单独列项审批才可能执行）

- 断电注错实验：两个正常成功闭环不默认需要；确需时单独说明原因列项。
- 任何烧录（App/Boot/BCB 直写）：O 序列零烧录；BCB 恢复的烧录在阶段 0 独立授权。
- 额外 B1-M 实验（PC 蓝牙适配器路径）：同上。
- 卸载/清手机数据：O1 签名冲突时明确禁止（第三轮裁定重申：任何情况下
  不得以卸载或清数据解决签名冲突）。
- **额度互借：REC1-REC7（BCB 恢复）、B1-M 与升级闭环额度不得互借**
  （用户原文；恢复项独立 REC 编号，不与历史 A1 混淆）。
- 自动恢复/自动重试/自动进入下一阶段：全部失败分支均"留证停报"。

## 7. 授权配额申报（O 序列；阶段 0 见恢复方案 §4，云端见写入单 §5）

| # | 操作 | 次数 | 超时 |
| --- | --- | --- | --- |
| O1 | 签名预检（只读）+ 安装 + 启动采集 | 1 | 5 min |
| O2 | latest/下载观测（App 操作 + logcat） | 1 | 10 min |
| O3 | toy 30201 闭环（含设备重启 1 次——固件正常状态机行为） | 1 | 30 min 窗口 |
| O4 | 真包 30202 闭环（含设备重启 1 次） | 1 | 30 min 窗口 |
| O5 | 只读身份复核 | 1 | 5 min |

- 设备重启发生在 OTA 闭环内部（升级提交后固件自复位），属获批操作范围内
  的固件状态转换，不另计"复位操作"。
- 受控服务 toy→真包切换（O3 后 D4：停服务换 `--active-release` 重启）
  按服务文档 §6 已含的部署申请执行，不新增云端写入（云端路线整体暂停，
  无 stable publish 动作）。
- J-Link 不含在 O 序列（§5 独立授权项，维持第三轮裁定口径）。

## 8. 边界声明

- 本单全部操作未授权、未执行；零真机、零云端、零代码改动。
- 与合同的关系：本单是合同 C-APK-INSTALL/C-TOY-LOOP/C-REAL-LOOP 判据的
  真机执行载体；冻结时合同 commands 按本单逐项绑定精确命令与证据路径。
- 本单所有设备身份引用既有只读证据（板识别/B1-M identity）；执行前由验收
  会话重测核对（板状态以阶段 0 恢复后为准）。
