# P3-3 BCB 恢复实机执行留证（REC0-REC7，S1A-S6）—— 2026-09-13

> 执行依据：恢复方案 v5（`P3-3-bcb-recovery-plan-2026-09-13-v5.md`）+ 用户集中执行授权
> `P3-3-EXEC-AUTH-20260913` 第三节 + 独立准入复核 ADMISSION_PASS
> （`P3-3-admission-review-2026-09-13.md`，2026-09-13）。
> 执行入口：`Tools/jlink/p3-3-recovery-execute.ps1`（逐 Phase，fail-closed）。
> 轮次目录：`.cache/p3-3-recovery-execute/20260913-r1/`（68 个证据文件，
> 每 Phase 的 `<Phase>-result.json` + J-Link 会话日志 + 二进制读回留档）。

## 1. 执行参数

- `-Phase S1A..S6` 逐段推进，`-ExpectedAppSha256
  d97534841302c16d4e026820a6b854c8ee68cc256b0042024d1280001f7401dd`
  （口径：SNAPSHOT 响应的 app_sha256 来自 App 镜像头 `header.image_sha256`
  双零摘要字段——`boot/src/boot_p1_6_test.c` `snapshot_app()` 经
  `control_copy_out(OTA_P1_6_OFF_APP_SHA256, header.image_sha256, ...)` 拷出；
  板上生产 3.2.0 App 头内值见板识别文档 2026-09-12 行 80-81，与本机双零
  重算一致，离线矩阵 runner 同口径注释 "internal App double-zero SHA"）。
- 生产 Boot/Map 取主 worktree 2026-09-03 构建（板识别轮 2026-09-12 已核对
  板上 Boot 与磁盘逐字节一致）；测试 Boot 取 admission worktree
  `.cache/p3-3-recovery-boot/boot/`（HEX SHA `409d4f16…`，hexLast
  `0x0800491F`）。

## 2. 逐 Phase 结果（全部 PASS）

| Phase | 关键实测（result.json 原值） |
| --- | --- |
| S1A | 全区备份 20,480B SHA `b6b33a82a56a4e974a9a2e2d887ddc598130aae0ab4940c4007ad1feb89b2dd4`；尾部 5,756B 板上原值 SHA `1d9693d1…3523b51`；生产 Boot bin 锚点 SHA `5842ff3e…`（14,724B）；烧录读回 SHA `6d2b26fc…` 与测试 Boot bin 逐字节全等、擦除尾部全 0xFF；RAM magic 失效 w4 后读回全 0。loadfile 的隐式复位为烧录固有动作（AIRCR.SYSRESETREQ，发生于擦写前），RAM 失效在测试 Boot 首启之前完成（v5 fix l 时序满足） |
| S1B | 复位①后 PC=`0x08029D1E`（App 区）、VTOR=`0x08010000`、CFSR=`0x00000000`——测试 Boot 成功跳转生产 App，无 fault |
| S2 | SNAPSHOT 基线（arg1=1 BCB_ONLY）：active=1(A)、cur_vcode=**20801**（阻断态与板识别/B1 澄清证据一致）、state=4、seq=904；BCB 双块各 64B 原始字节强制留档不裁剪：A `s2-bcb-a-raw.bin` SHA `6e07d0d94b119c884c2c5f32369a5bc0bd6b4331547a53b973a4861480770dc3`、B `s2-bcb-b-raw.bin` SHA `5b637d42b2dda371acbf1f07d4672c8070eda8235fcf4bf11834f1a99cd96900`；双块头部 `45 54 42 43`（"ETBC"）魔数；result_crc_valid=true。响应内 App 快照 app_vcode=30200 / app_sha256=`d9753484…`（板上身份旁证） |
| S3 | CLEAR_BCB：active=0(NONE)、双块 raw 全 0xFF（EEPROM 0x00-0x7F 写全 0xFF，由固件既有 CLEAR_BCB 执行，唯一持久 BCB 擦除；清空前 128B 备份即 S2 双块留档） |
| S4 | 复位④触发状态机 NONE→commit_confirmed 重建；RTT（map 严格符号行解析 `0x200540A4`，签名会话验 `SEGGER RTT` 后单 logger ≤120s）采到目标行 **`OTA: BCB already CONFIRMED vcode=30200`**（REC4；rtt_log SHA `efa65e7dbeac5b24188e0b5d4c307cc315d51296ce3276eea6784f0419408862`） |
| S5 | SNAPSHOT 终态（arg1=0 含 App 快照，正常会话非 FR4 备用）：active=1(A)、cur_vcode=**30200**、state=4(CONFIRMED)、seq=0（NONE 分支 commit_confirmed 走 bcb_make_idle）、app_result=1(VALID)、app_vcode=30200、app_len=602984、app_sha256=`d97534841302c16d4e026820a6b854c8ee68cc256b0042024d1280001f7401dd`（与期望值全等，app_sha256_checked=true） |
| S6 | 生产 Boot 全区恢复（备份 loadbin+verifybin+全区读回）：restored_sha256=`b6b33a82…` **与 S1A 备份全区 SHA 全等**（含尾部 5,756B 板上原值还原）；复位⑥后 RTT 终证（`0x200540A4`）再采到 `OTA: BCB already CONFIRMED vcode=30200`（REC7，此时已是恢复后的生产 Boot + 生产 App；S4/S6 日志字节级一致为同固件确定性启动序列，App 全程零写入） |

S4/S6 RTT 日志全文（286B，四行启动序列）：
`OTA: HANDOFF vtor=0x08010000 … / Reset: NRST SW / QSPI: JEDEC=0xEF4018
whitelisted, OTA enabled / OTA: BCB already CONFIRMED vcode=30200`。

## 3. v5 §5 完成判据四条（全满足）

1. **生产 Boot 已按全区恢复**：S6 restored_sha256 = S1A backup_sha256 全等
   （`b6b33a82…`），verifybin 成功，尾部原值随全区还原。
2. **App 身份未变**：S5 app_vcode=30200、app_sha256=`d9753484…` 与板上镜像
   身份证据全等；App 区 0x08010000 零写入由 S1A/S6 地址范围留证保证。
3. **BCB 与 App 一致**：S5 CONFIRMED（state=4）/ cur_vcode=30200 / CRC 有效
   （result=PASS 含 result_crc_valid 断言）。
4. **新鲜终证**：S6 复位⑥后生产 App RTT 自报 `OTA: BCB already CONFIRMED
   vcode=30200`。

设备终态（O 序列合法起点）：生产 Boot（原样）+ 生产 App 3.2.0(30200)（未动）
+ BCB CONFIRMED cur_vcode=30200（与 App 一致，20801 阻断已消除）。

## 4. 额度终账（对齐授权第三节 / v5 §7）

| 项 | 授权上限 | 实际消耗 | 明细 |
| --- | --- | --- | --- |
| J-Link 命令会话 | 恰好 10 | **10/10** | S1a 1 + S1b 1 + S2 2 + S3 2 + S4 1 + S5 2 + S6 1 |
| 主动复位 | 6 | **6/6** | ①S1b ②S2 ③S3 ④S4 ⑤S5 ⑥S6 |
| RTT logger | 2（各 ≤120s） | **2/2** | S4、S6 各 1，默认 120s 硬超时内完成 |
| 身份/RTT 签名核对会话 | ≤2 | **2/2** | S4-rtt-signature、S6-rtt-signature（mem8 只读，无写块无复位） |
| FR4 备用会话 | 与 S5 互斥其一 | 未触发 | S4 目标行直接命中，S5 以正常会话执行（invoked_as_fr4_fallback=false） |
| 计划外 nRESET | 单步 ≥2 或全程 >2 即停 | **0** | S1A 日志仅见 loadfile 固有隐式复位（烧录组成部分），无连接引发 POR 痕迹 |

写入范围合规：Flash 仅 0x08000000-0x08004FFF（S1a 擦写/S6 还原）；RAM 控制块
仅 0x20057E00-0x20057FFF；EEPROM 0x00-0x7F 仅经既有 CLEAR_BCB（S3）；App 区
与 QSPI 槽零写入；未执行任何其他测试 opcode。

## 5. 执行中 HARNESS 修复（2 处，均已主机侧复核，未追加设备额度）

按用户持续推进指令第 3 条（已授权范围内技术问题集中修复自测），两处宿主侧
脚本缺陷当场修复；两处均为 HARNESS 类（设备侧观测真实有效），修复后对
**已落盘的同一设备响应**做主机侧重判，未消耗任何新 J-Link 会话、复位或
logger（额度终账仍为上表 10/10）。

### 5.1 S2/S3 BCB raw 断言长度错误（256→128 hex 字符）

- 现象：S2 抛 `BCB raw length mismatch: A=128 B=128`。
- 根因：脚本断言按 256 hex 字符/块（128B/块）写；协议本义为
  `eeprom_bcb.h:26` `#define BCB_SIZE 64u`（单块 64B，`bcb_t` 静态断言
  sizeof==64），`snapshot_bcb()` 的 `raw_a[BCB_SIZE]` 每块 64B=128 hex 字符，
  双块合计 128B（EEPROM 0x00-0x7F）。实测 128 字符恰为正确值。
- 修复：`p3-3-recovery-execute.ps1` S2 断言 `-ne 256`→`-ne 128`、S3 断言
  `^[fF]{256}$`→`^[fF]{128}$`，注释注明 BCB_SIZE 依据。
- 复核：S2 设备响应已完整落盘（`S2-snapshot-baseline.start.bin/.json`，
  SNAPSHOT 只读不写 BCB），以修正断言对同一响应重判全过（active=1、
  cur_vcode=20801、双块 128 hex、ETBC 魔数、CRC、status=2），落盘
  `s2-bcb-a/b-raw.bin` 与 `S2-result.json`（含 reassessment 说明）。
- 离线测试未暴露原因：24/24 离线验证覆盖 runner 库与命令构造，不含
  execute 脚本的 Phase 断言路径（与复核 F 项"脚本较 v5 文字多增强断言"
  的性质一致——该增强断言本身写错了长度）。

### 5.2 `Invoke-P1RttCapture` 管道泄漏导致 S4 结果记录崩溃

- 现象：S4 设备侧全部完成（复位④+签名会话+单 logger+目标行命中）后，
  脚本在 `$rtt.LogPath` 抛 `PropertyNotFoundStrict`。
- 根因：共享库 `jlink-common.ps1` 的 `Invoke-P1RttCapture` 向管道
  `Write-Output` 状态行；`Invoke-P33RttEvidence` 只对
  `Test-P1RttSignature | Out-Null`，capture 调用漏抑制，函数返回值成为
  `Object[]`（字符串+对象），StrictMode 下属性枚举到字符串元素即抛错。
  S6 同构路径必然复现，一并修复。
- 修复：`p3-3-recovery-execute.ps1` `Invoke-P33RttEvidence` 内 capture 调用
  追加 `| Out-Null`（注释说明保持单一返回对象）。
- 复核：S4 已落盘证据（`S4-rtt.log` 目标行、`S4-rtt-signature.log`
  SEGGER RTT 签名、map 严格符号行与 .jlink mem8 地址交叉核对一致）重判
  全过，写 `S4-result.json`（含 reassessment 说明）。S6 在修复后正常执行，
  一次通过。

两处修复已随本批提交入库（Tools/jlink/p3-3-recovery-execute.ps1），
供独立验收会话复核受影响项。

## 6. 证据索引

- 轮次目录：`.cache/p3-3-recovery-execute/20260913-r1/`
  （S1A/S1B/S2/S3/S4/S5/S6 各 `-result.json`、J-Link 会话 `.jlink/.log`、
  二进制读回 `boot-region-backup.bin`、`s1a-flashed-readback.bin`、
  `s1a-invalidate-readback.bin`、`s2-bcb-a/b-raw.bin`、
  `S5-snapshot-final.start.bin`、`S6-boot-restore.restore-readback.bin`、
  `S4/S6-rtt.log` 等 68 文件）。
- 主 worktree 前置件：`X-Track-Boot.bin`（14,724B，SHA `5842ff3e…`）、
  `X-Track-App-GCC.map`（RTT 地址源）。
- 测试 Boot：`.cache/p3-3-recovery-boot/boot/X-Track-Boot.{hex,bin}`
  （构建验证见 `P3-3-recovery-boot-build-2026-09-13.md`）。
