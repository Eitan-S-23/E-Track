# P3-3-v4 外部输入证据（沿用 v3 核对记录）：EXT-BOARD-STATE（目标板 BCB 恢复终态）

- 输入 ID: EXT-BOARD-STATE（category=hardware_state）
- 核对会话: 独立验收会话（非实现会话，P3-3 冻结办理）
- 日期: 2026-09-13
- freeze_commit: `a178ecc1dca3929e1bca702fb11344f3c5bd2872`
- 恢复执行依据: 恢复方案 v5（`P3-3-bcb-recovery-plan-2026-09-13-v5.md`）+
  用户集中执行授权 P3-3-EXEC-AUTH-20260913 第三节 + 独立准入复核
  ADMISSION_PASS；执行留证 `docs/ota-exec-notes/P3-3-recovery-execution-2026-09-13.md`

## 1. 恢复终态（O 序列合法起点，独立核对实测）

设备现处：

- 生产 Boot 全区恢复：S6 `restored_sha256` =
  `b6b33a82a56a4e974a9a2e2d887ddc598130aae0ab4940c4007ad1feb89b2dd4`
  与 S1A 全区备份 SHA 全等（20,480B 含尾部 5,756B 板上原值还原；verifybin
  成功 + 全区读回 SHA 全等）。
- 生产 App 3.2.0(30200) 零写入：S5 终态 SNAPSHOT `app_vcode=30200` /
  `app_sha256=d97534841302c16d4e026820a6b854c8ee68cc256b0042024d1280001f7401dd`
  与板上镜像身份全等；App 区 0x08010000 由 S1A/S6 地址范围留证保证零写入。
- BCB CONFIRMED cur_vcode=30200：S5 `active=1(A)`、`state=4(CONFIRMED)`、
  `seq=0`、`result_crc_valid=true`——20801 阻断已消除，BCB 与 App 一致。

## 2. v5 §5 完成判据四条映射（全部满足，独立核对）

1. 生产 Boot 已按全区恢复 —— S6 restore-readback（20,480B）SHA 与 S1A
   备份全等（实测文件 `S6-boot-restore.restore-readback.bin`、
   `boot-region-backup.bin` 同 SHA `b6b33a82…`）。
2. App 身份未变 —— S5 `app_result=1(VALID)`、`app_vcode=30200`、
   `app_sha256=d9753484…`（`app_sha256_checked=true`）。
3. BCB 与 App 一致 —— S5 CONFIRMED/30200/CRC 有效。
4. 新鲜终证 —— S6 复位⑥后生产固件 RTT 自报
   `OTA: BCB already CONFIRMED vcode=30200`
   （S4/S6 RTT 日志 SHA `efa65e7dbeac5b24188e0b5d4c307cc315d51296ce3276eea6784f0419408862`，
   RTT 地址 `0x200540A4` 经 map 严格符号行解析 + mem8 `SEGGER RTT` 签名
   会话双重核对）。

## 3. 额度实账（独立核对后如实登记）

| 项 | 授权上限 | 实际消耗 | 说明 |
| --- | --- | --- | --- |
| J-Link 命令会话 | 恰好 10 | **11** | 偏差 +1：S6 的 Boot 全区恢复与复位⑥被执行脚本拆为两个独立会话（S6-boot-restore 无复位 + S6-reset6 独立复位），偏离 v5 §3 S6 行「1 命令会话含尾部复位⑥」的进程边界设计；动作集合与 v5 §3 完全一致，无额外写入/复位/logger（Flash/RAM/EEPROM 写入范围均未超出）。已向协调者报告待用户追认（授权第五节情况 1/2 的事后追认口径） |
| 主动复位 | 6 | 6/6 | ①S1b ②S2 ③S3 ④S4 ⑤S5 ⑥S6，无计划外复位 |
| RTT logger | 2（各 ≤120s） | 2/2 | S4、S6 各 1，120s 硬超时内完成，无残留 logger |
| 身份/RTT 签名核对会话 | ≤2 | 2/2 | S4/S6-rtt-signature（mem8 只读，无写块无复位） |
| FR4 备用会话 | 与 S5 互斥其一 | 未触发 | `invoked_as_fr4_fallback=false` |
| 计划外 nRESET | 单步 ≥2 或全程 >2 即停 | 0 | S1A 仅 loadfile 固有隐式复位 |

写入范围合规：Flash 仅 0x08000000-0x08004FFF（S1a 擦写/S6 还原）；RAM 控制块
仅 0x20057E00-0x20057FFF；EEPROM 0x00-0x7F 仅经固件既有 CLEAR_BCB（S3，
清空前 128B 双块原始字节已备份留档）；App 区与 QSPI 槽零写入。

## 4. 执行中 2 处 HARNESS 修复的独立复核结论

两处均属宿主侧脚本缺陷，设备侧观测真实有效；修复后对已落盘的同一设备
响应做主机侧重判，零新增设备额度。复核（独立验收会话，2026-09-13）：

1. **S2/S3 BCB raw 断言长度 256→128 hex 字符**——忠于协议：`eeprom_bcb.h:26`
   `#define BCB_SIZE 64u`（`bcb_t` 编译期断言 sizeof==64）、
   `boot_p1_6_test.c` `snapshot_bcb()` 的 `raw_a[BCB_SIZE]/raw_b[BCB_SIZE]`
   整块 64B 输出 → 128 hex 字符/块、双块合计 128B（EEPROM 0x00-0x7F）；
   S2 响应 JSON 实测 `bcb_a_raw/bcb_b_raw` len=128、头部 `45 54 42 43`
   （ETBC 魔数）。reassessment 绑定原始落盘证据
   （`S2-snapshot-baseline.start.bin/.json`、`s2-bcb-a/b-raw.bin`）实测在盘
   且内容自洽。**复核结论：PASS**。
2. **Invoke-P1RttCapture 管道泄漏状态行致 S4 结果记录崩溃**——根因为
   `jlink-common.ps1` 该函数尾部 `Write-Output` 状态行混入管道（返回值成为
   Object[]，StrictMode 属性访问崩溃）；修复为 capture 调用补 `| Out-Null`
   （返回值本未被使用，无信息丢失）。S4 reassessment 绑定 `S4-rtt.log`
   （目标行实测在案）、`S4-rtt-signature.log`（SEGGER banner）与
   map/.jlink 地址交叉核对一致。S6 修复后正常执行一次通过。**复核结论：PASS**。

修复代码已随 freeze_commit（a178ecc）入库
（`Tools/jlink/p3-3-recovery-execute.ps1`），供最终验收复核。

## 5. 原始证据指针

- 轮次目录: `.cache/p3-3-recovery-execute/20260913-r1/`（68 文件：
  S1A/S1B/S2/S3/S4/S5/S6 各 `-result.json`、J-Link 会话 `.jlink/.log`、
  二进制读回 `boot-region-backup.bin`、`s1a-flashed-readback.bin`、
  `s1a-invalidate-readback.bin`、`s2-bcb-a/b-raw.bin`、
  `S5-snapshot-final.start.bin`、`S6-boot-restore.restore-readback.bin`、
  `S4/S6-rtt.log` 等）
- 统一留证: `docs/ota-exec-notes/P3-3-recovery-execution-2026-09-13.md`
- 测试 Boot 构建: `.cache/p3-3-recovery-boot/boot/X-Track-Boot.{hex,bin}`
  （`docs/ota-exec-notes/P3-3-recovery-boot-build-2026-09-13.md` 13/13 PASS）

## 6. 边界

- 恢复属独立真机准备操作，不并入本合同判据；本输入的解决证据即上述
  四判据留证。四判据满足前 C-TOY-LOOP/C-REAL-LOOP 不得执行（已满足）。
- 恢复授权与 O 序列、历史 A1/B1-M 配额不互借。

## v4 冻结复核（2026-09-14）

- 恢复执行（20260913-r1）以来板卡未进行任何 J-Link/OTA 操作，BCB CONFIRMED vcode=30200
  一致态维持；恢复证据与额度实账沿用 v3 冻结记录（含 REC 命令会话 11/10 偏差仍待用户追认）。
- 编制：实现会话（DRAFT）；冻结核对待非实现会话。
