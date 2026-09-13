# P3-3 实机合并操作单（第二版，待集中审批）—— 2026-09-13

> 依据：用户 2026-09-13 分项批复第 7 条——O1-O5 现版不予整单批准，修改后
> 集中提交。本版修订：补身份/签名预检；BCB 恢复列为独立准备操作（阶段 0，
> 排在一切升级闭环之前）；正式升级的前置链写死（恢复完成 → 服务与资产准入
> → 用户审批合同 → FROZEN+NOT_RUN 前检通过）；删除"预期 BCB 拒绝"观测点；
> toy 闭环终点核对（30201 + 完整 raw SHA）通过后才进真包 30202；BCB 授权
> 口径改精确表述；失败后不假定 STAGED、不自动恢复/重试/进入下一阶段；
> J-Link 连接/采集单列为独立授权项。
>
> **性质**：申报文档。全部操作均未授权、未执行。取代
> `P3-3-admission-remediation-2026-09-12.md` §11 框架（该节保留为历史，
> 以本单为准）。

## 1. 设备与资产身份（执行前逐项绑定实物哈希）

| 项 | 身份 | 状态 |
| --- | --- | --- |
| 测试手机 | vivo V2312A，序列号 `10ADA4197U001CK`，Android 13（SDK 33）；既有安装 `com.wen.gaia.gaia` 1.0.60(86) release（APK SHA `428a5d3a…`，2026-06-30 首装，历史动作不追认） | 沿用 B1-M r1 identity.md |
| 目标板 | AT32F435RGT7；板上 App 3.2.0(30200)（finalize 头双零摘要链已核）；Boot=磁盘 `X-Track-Boot.bin` 原版 | 板识别文档（2026-09-12） |
| 板上 BCB 起点 | **恢复执行前**：CONFIRMED cur_vcode=20801（阻断态）；**恢复执行后（O 序列合法起点）**：CONFIRMED cur_vcode=30200（R4 终态核验值） | 恢复方案 v2 §3.3 |
| 受验 APK | 经 build.yml dispatch 输入 `firmware_latest_url=<受控服务URL>` 构建（endpoint 方式 iii）；绑定包名/versionCode/APK SHA-256/**证书指纹实测值**（apksigner verify --print-certs） | 待构建（追加 1 次 build-only 配额，待服务就绪后用） |
| toy 包 | `e-track-at32f435-v3.2.1-full.etu`（284092B，SHA `fc4ae5a9…`）→ 云端 fixture 按 R2 对象键上传登记；终点基准=镜像 raw SHA `43ee943a…` + vcode 30201 | 已离线制包；云端写入单待批 |
| 真包 | `e-track-at32f435-v3.2.2-full.etu`（284112B，SHA `0a2eb26a…`）；终点基准=镜像 raw SHA `c9582213…` + vcode 30202 | 同上 |
| 受控 HTTP 服务 | P4-2 固件 worker v2 部署实例（前置，见 §0）；endpoint 经 dispatch 输入注入 APK | 未就绪（P4-2 未认领） |

## 2. 执行前置链（全部满足才可开始 O 序列）

```
P0 BCB 恢复获批并执行（A1-A4，独立授权）→ R4 终态核验通过
P1 受控 HTTP 服务就绪（P4-2 worker v2 部署或用户裁定等价物）+ 云端写入单获批
P2 资产上板资格经非实现会话审定（合同冻结时 EXT-* 回填）
P3 受验 APK 构建（dispatch 注入 endpoint；apksigner 指纹留档）
P4 用户审批冻结合同（FROZEN）+ validate_bundle NOT_RUN 前检通过
P5 云端 toy fixture 按写入单 §5.2 时序登记并激活 stable channel 指针 → 30201
→ O1 → O2 → O3（toy 闭环）→ 【PASS 后】云端 stable 指针 30201→30202 → O4 → O5
```

## 3. 阶段 0：BCB 恢复（独立准备操作，不属本操作单判据）

- 完整方案：`P3-3-bcb-recovery-plan-2026-09-13-v2.md` §3.2 R0-R5
  （P5 变体：P1_6_TEST_ENABLE 版 Boot → CLEAR_BCB → 状态机 commit_confirmed
  重建 → 换回生产 Boot；复位合计 3 次；BCB 原始字节快照留档；App 镜像全程
  不动）。
- 授权申报：该文档 §4（A1 烧 P1_6 Boot ×1、A2 J-Link 会话 ×3、A3 复位 ×1、
  A4 烧回生产 Boot ×1）——**单独审批，与 O 序列额度不互借**。
- 完成判据：R4 终态核验（BCB.cur_vcode == 30200 == App fw_header.version_code）
  留证回填合同 EXT-BOARD-STATE。

## 4. 操作序列 O1-O5（每项含命令/超时/次数/失败处理/证据路径）

### O1 受验 APK 身份/签名预检 + 安装 + 启动

| 项 | 内容 |
| --- | --- |
| 预检命令 | `apksigner verify --print-certs <apk>`（提取受验 APK 实际证书指纹）；`adb -s 10ADA4197U001CK shell dumpsys package com.wen.gaia.gaia`（提取既有安装签名）——**不同 CI run 的 debug 签名不能假定相同，指纹以本次实测为准，不以历史 run 推定** |
| 比对 | 两者一致 → 继续；**不一致 → 停在安装前**，保留既有安装与数据，报用户裁定（不默认卸载/清数据） |
| 安装 | `adb -s 10ADA4197U001CK install -r <apk>`（`-r` 保留数据覆盖安装；签名不一致时此命令不会执行） |
| 启动 | 手动/monkey 启动 App；`adb logcat -v time > evidence/o1-install.log`（受控采集，**不清缓冲**：不执行 `logcat -c`） |
| 超时 / 次数 | 5 min / 各命令 1 次（预检只读不限，但每会话采集一次为准） |
| 留证 | 安装结果、包名/versionCode 实测、证书指纹双侧实测值、APK SHA-256（与云端参与传输的 fixture 同源核对）、启动 logcat；路径 `evidence/o1-*.log` |
| 失败处理 | 安装失败（非签名冲突，如存储不足）→ ENV_BLOCKED 留证停；签名冲突 → 上述停报 |

### O2 App 对受控服务真实 latest/下载请求观测

| 项 | 内容 |
| --- | --- |
| 操作 | App 内进入固件升级入口，触发 latest 检查与下载（观测插桩 `OTA_OBS` 日志经 logcat 采集） |
| 核对 | App 日志证明请求打到受控服务 endpoint（非 legacy GitHub 路径）；latest 响应解析 v2 成功；token 下载链走真实 `/api/public/firmware/download`（非静态直链）；整包 SHA 校验通过（`fc4ae5a9…`） |
| 超时 / 次数 | 10 min / 1 次 |
| 留证 | `evidence/o2-latest-download.log`（logcat 全程）+ 服务端请求日志（由云端写入单执行方提供当次请求记录） |
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

**O3 → O4 门禁**：O3 PASS（终点双值核对通过）+ 云端 stable 指针按写入单 §5.2 切换 30201→30202 完成后，方可进 O4。任一不满足即停。

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
- 卸载/清手机数据：O1 签名冲突时明确禁止。
- **额度互借：A1、B1-M 与升级闭环额度不得互借**（用户原文）。
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
- 云端 stable 指针切换（O3 后 30201→30202）按写入单 §5.2 已含的 publish
  操作执行，不新增云端写入次数。

## 8. 边界声明

- 本单全部操作未授权、未执行；零真机、零云端、零代码改动。
- 与合同的关系：本单是合同 C-APK-INSTALL/C-TOY-LOOP/C-REAL-LOOP 判据的
  真机执行载体；冻结时合同 commands 按本单逐项绑定精确命令与证据路径。
- 本单所有设备身份引用既有只读证据（板识别/B1-M identity）；执行前由验收
  会话重测核对（板状态以阶段 0 恢复后为准）。
