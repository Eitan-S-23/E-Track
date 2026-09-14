# P3-3 BCB 恢复实机执行留证（第二轮 r2，S1A-S6）—— 2026-09-14

> 执行依据：修复轮整体授权（用户 2026-09-14 批准：固件修复→重建→重新
> 制包→合同升 v5 重冻结→O 序列重跑）+ 本轮恢复授权（用户 2026-09-14
> 「授权，此外你说的超授权问题也一并授权」：①S1A-S6 按申报额度执行；
> ②追认 REC 轮命令会话 11/10 超授权 1 次，登记见 §6）。
> 背景：§16 烧录事故（实现 agent 误烧裸构建镜像 → boot `validate_internal_app`
> 拒跳 → `begin_rollback` 置 BCB=ROLLBACK → 外部 backup/recovery 槽均无效 →
> `return_recovery` 死等 PA15≥3s YMODEM → 黑屏）。finalize 镜像虽已于
> 2026-09-14 19:07 烧好并逐字节核验，但 **ROLLBACK 分支只看外部槽**，内部
> App 镜像再合法也救不回，必须走 CLEAR_BCB 恢复链（与 r1 同机制）。
> 执行入口：`Tools/jlink/p3-3-recovery-execute.ps1`（逐 Phase，fail-closed）。
> 轮次目录：`.cache/p3-3-recovery-execute/20260914-r2/`（67 个证据文件，
> 每 Phase 的 `<Phase>-result.json` + J-Link 会话日志 + 二进制读回留档）。

## 1. 与 r1（20260913-r1）的差异与脚本适配

本轮基线不是 r1 的 CONFIRMED(20801) 阻断态，而是事故造成的
ROLLBACK(30200)。对 `p3-3-recovery-execute.ps1` 做三处参数化适配，
默认值保持 r1 语义（可复用性不破坏）：

1. **S2 基线参数化**：新增 `-BaselineCurVcode`（默认 20801）与
   `-BaselineState`（默认 -1=只记录不断言；≥0 才断言 state 字节）。
   本轮传 `-BaselineCurVcode 30200 -BaselineState 5`（ROLLBACK）。
   实测不符即停（fail-closed）。原 `$P33BaselineCurVcode` 硬编码常量删除。
2. **S1B 断言模式化**：新增 `-S1BExpectedPcRegion App|BootWait`（默认
   App=r1 语义，走共享库 `Invoke-P16OrdinaryResetEvidence`）。BootWait
   模式为本轮语义：BCB=ROLLBACK 且外部双槽无效 → 测试 Boot 停在物理
   恢复等待循环，断言改为 **PC ∈ [0x08000000,0x08005000)（boot 区）且
   CFSR=0**；会话形状与共享库完全同构（r,g,Sleep 5000,h,regs,
   mem32 VTOR/CFSR,g,qc），断言内联在执行脚本，**不改共享库**
   `jlink-common.ps1`/`p1-6-common.ps1`（其 App 分区语义供 P1-5 等复用）。
   VTOR 记录不断言（恢复等待循环的 VTOR 归 boot 所有，不属恢复契约）。
3. **执行参数**：`-ProductionAppMap` 指向修复版构建
   `.cache/bg/app-gcc/X-Track-App-GCC.map`（`_SEGGER_RTT` 严格符号行
   解析实测 `0x200540AC`，恰一行，r1 生产 3.2.0 为 0x200540A4）；
   `-ExpectedAppSha256 24fc02ea…728126`（finalize 镜像头 image_sha256，
   非 r1 的旧 App `d9753484…`）。

适配后离线自测：①Parser::ParseFile 零错误；②无 `$P33BaselineCurVcode`
残留引用；③ValidateSet 拒绝非法 region 值（Bogus 绑定失败）；④合法参数
（默认集与本轮全参数集）下 S1A fresh-RunDirectory 门禁正常触发（脚本体
正确进入，且未触碰设备）。执行前预检：修复版 map 严格符号行恰一行
`0x200540ac _SEGGER_RTT`（行 24012）。

## 2. 逐 Phase 结果（全部 PASS）

| Phase | 关键实测（result.json 原值） |
| --- | --- |
| S1A | 全区备份 20,480B SHA `b6b33a82a56a4e974a9a2e2d887ddc598130aae0ab4940c4007ad1feb89b2dd4`（**与 r1 的 S1A 备份及 S6 还原后全区 SHA 完全一致**——REC 轮收尾后 boot 区未被改动，身份闭合）；尾部 5,756B SHA `1d9693d1…3523b51`（与 r1 相同，板上原值未变）；生产 Boot bin 锚点 14,724B SHA `5842ff3e…`；烧录读回与测试 Boot bin（18,720B，HEX SHA `409d4f16…`）逐字节全等、擦除尾全 0xFF；RAM magic w4 失效后读回全 0 |
| S1B | 复位①后 **PC=`0x0800227C`（boot 区恢复等待循环）、VTOR=`0x08000000`、CFSR=`0x00000000`**——BootWait 断言通过，测试 Boot 停在 `receive_physical_recovery()` 等待，与 ROLLBACK 死等机理预判一致 |
| S2 | SNAPSHOT 基线（arg1=1 BCB_ONLY）：active=2(B)、**cur_vcode=30200、state=5(ROLLBACK)**（参数化断言命中）、seq=1；BCB 双块各 64B 原始字节强制留档：A `s2-bcb-a-raw.bin` SHA `2a6233b5996ea79aec5b93039e3228515d5dc2aa51fc2b684444e082698649c1`、B `s2-bcb-b-raw.bin` SHA `bfd3eccdb825cfbec0931874391c2a6309f45c994016f8faca6989093e572c45` |
| S3 | CLEAR_BCB：active=0(NONE)、双块 raw 全 0xFF（EEPROM 0x00-0x7F 由固件写全 0xFF，唯一持久 BCB 擦除；清空前 128B 备份即 S2 双块留档） |
| S4 | 复位④触发状态机 NONE→`validate_internal_app`（finalize 镜像合法）→`commit_confirmed`→跳 App；RTT（修复版 map 解析 `0x200540AC`，签名会话验 `SEGGER RTT` 后单 logger ≤120s）采到目标行 **`OTA: BCB already CONFIRMED vcode=30200`**；完整启动序列四行：HANDOFF vtor=0x08010000 / Reset: NRST POR SW / QSPI: JEDEC=0xEF4018 whitelisted, OTA enabled / 目标行 |
| S5 | SNAPSHOT 终态（arg1=0 含 App 快照，正常会话非 FR4 备用）：active=1(A)、cur_vcode=**30200**、state=4(CONFIRMED)、seq=0、app_result=1(VALID)、app_vcode=30200、app_len=603764、**app_sha256=`24fc02ea389eec37e1eda0f896bbf8e90fa7a50fa8a8072450ba0e057e728126`（与 finalize 镜像头 image_sha256 全等，app_sha256_checked=true）** |
| S6 | 生产 Boot 全区恢复（备份 loadbin+verifybin+全区读回）：restored_sha256=`b6b33a82…` **与 S1A 备份全区 SHA 全等**；复位⑥后 RTT 终证（`0x200540AC`）再采到 `OTA: BCB already CONFIRMED vcode=30200`（此时已是恢复后的生产 Boot + 3.2.0-fixed App） |

## 3. 完成判据（全满足）

1. **生产 Boot 已按全区恢复**：S6 restored_sha256 = S1A backup_sha256
   = `b6b33a82…` 全等；App 区 0x08010000 与 QSPI 槽零写入（写入仅
   boot 区 0x08000000-0x08004FFF、EEPROM 0x00-0x7F、RAM 控制块，均在
   授权边界内）。
2. **板上 App 身份**：3.2.0-fixed finalize 镜像（603,764B / vcode 30200 /
   image_sha256 `24fc02ea…` / 头 crc32@0x5C=E5BF739A），S5 快照 SHA
   与之逐字节全等。
3. **BCB 与 App 一致**：S5 CONFIRMED(state=4) / cur_vcode=30200 / seq=0 /
   app_result=VALID——ROLLBACK 阻断已消除。
4. **新鲜终证**：S6 复位⑥后生产 App RTT 自报
   `OTA: BCB already CONFIRMED vcode=30200`。

设备终态（O 序列重跑合法起点）：**生产 Boot（全区原样）+ 3.2.0-fixed
App(30200) + BCB CONFIRMED cur_vcode=30200**；App 启动序列完整（RTT 四行），
黑屏已解除。

## 4. 额度终账（对齐本轮授权申报）

| 项 | 授权上限 | 实际消耗 | 明细 |
| --- | --- | --- | --- |
| J-Link 命令会话 | 10 | **10/10** | S1A 1 + S1B 1 + S2 2 + S3 2 + S4 1 + S5 2 + S6 1 |
| 主动复位 | 6 | **6/6** | ①S1B ②S2 ③S3 ④S4 ⑤S5 ⑥S6 |
| RTT logger | 2（各 ≤120s） | **2/2** | S4、S6 各 1 |
| RTT 签名会话 | ≤2 | **2/2** | S4、S6 各 1（mem8 只读） |
| WFI 连接失败重试 | 单 Phase ≤2、不占会话额度 | **0 次** | 本轮全部会话首连成功（S1B 复位时核已被 S1A halt 停住，DAP init 可靠；后续复位后 halt 均在已连接状态） |

零超授权、零自动重试。

## 5. 授权与写入边界（本轮实际执行面）

- 写入仅：boot 区 0x08000000-0x08004FFF（烧测试 Boot + S6 还原生产
  Boot）、EEPROM 0x00-0x7F（S3 CLEAR_BCB，S2 先双块 128B 留档）、
  RAM 控制块 0x20057E00-0x20057FFF（命令字，复位即失）。
- App 区 0x08010000 与 QSPI backup/recovery/staging 槽零写入。
- 台账 §8 边界事件登记：第二次 cwd 漂移越界（第五轮 APK 下载落主仓
  `.cache/p3-3-apk-r5/`，已 mv 回并哈希复核，空目录壳待清理；§13.4），
  本轮恢复执行全部命令均显式绝对路径，无新增漂移。

## 6. REC 轮超授权追认（用户已批准）

用户 2026-09-14「授权，此外你说的超授权问题也一并授权」追认
20260913-r1 恢复轮命令会话 11/10 超授权 1 次（收尾确认阶段多执行一次
只读性质确认命令，未影响板卡最终一致态；原始登记见
`P3-3-recovery-execution-2026-09-13.md` §4 与台账原 §5）。追认后该偏差
销账，不再列为待决事项。

## 7. 后续（已授权修复轮计划衔接）

1. 重制 .etu 包：**已执行**（2026-09-14 晚）——源 = `1894f9d` 的 GCC 构建
   原件 `.cache/bg/app-gcc/X-Track-App-GCC.bin`（603,764B，SHA
   `4b16048f…830ec`，即板上 3.2.0-fixed 本体；与 finalize 镜像
   `d7cc4194…` 仅差 0x400 头区）取代旧 `7328c1b1…`（O2 缺陷版）。toy/真包
   均已按资产方案 §2.3 同源重建并通过离线验证 A-I 全 PASS，四元组与受控
   服务 fixture 切换见 `P3-3-offline-assets-v5-rebuild-2026-09-14.md`。
2. 合同升 v5 重冻结（parent 绑 v4 `4AABC513…`，task_id 不变）。
3. O 序列重跑（O3 切真包需 `--active-release` 重启服务；D4 只停服务
   不动隧道）。
