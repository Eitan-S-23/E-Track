# P3-3-v5 外部输入证据：EXT-BOARD-STATE（目标板 BCB/镜像一致态，r2 恢复终态）

- 输入 ID: EXT-BOARD-STATE（category=hardware_state）
- 编制: 实现会话（P3-3-IMPL-20260907，DRAFT）；冻结核对: 待非实现会话
- 日期: 2026-09-14
- freeze_commit: `6415226b8c30abcffa2b9bab52f0db717f8f7cb9`
- 恢复执行依据: 修复轮整体授权 + 本轮恢复授权（用户 2026-09-14
  「授权，此外你说的超授权问题也一并授权」：①恢复轮 20260914-r2
  S1A-S6 按申报额度执行；②追认 REC 轮 20260913-r1 命令会话 11/10
  超授权 1 次，销账登记见 §4）；执行留证
  `docs/ota-exec-notes/P3-3-recovery-execution-2026-09-14-r2.md`

## 1. 当前终态（O 序列重跑合法起点）

- **生产 Boot 全区原样**：r2 S6 `restored_sha256` =
  `b6b33a82a56a4e974a9a2e2d887ddc598130aae0ab4940c4007ad1feb89b2dd4`
  与 S1A 全区备份 SHA 全等（20,480B，含尾部 5,756B 板上原值还原；
  loadbin+verifybin+全区读回三重核验）——且与 r1 轮 S1A/S6 同 SHA，
  两次恢复间 boot 区未被改动的身份闭合。
- **板上 App = 3.2.0-fixed（30200）**：S5 终态 SNAPSHOT `app_vcode=30200`、
  `app_result=1(VALID)`、`app_sha256=24fc02ea389eec37e1eda0f896bbf8e90fa7a50fa8a8072450ba0e057e728126`
  与 finalize 镜像头 image_sha256 全等（`app_sha256_checked=true`）；
  App 区 0x08010000 由 S1A/S6 地址范围留证保证 r2 零写入（该 App 为
  修复提交 `1894f9d` 的 finalize 产物烧入，即 v5 重制包同源本体）。
- **BCB 与 App 一致**：S5 `active=1(A)`、`state=4(CONFIRMED)`、
  `cur_vcode=30200`、`seq=0`——ROLLBACK 阻断已消除。
- **新鲜终证**：S6 复位⑥后 RTT 自报 `OTA: BCB already CONFIRMED
  vcode=30200`（RTT 地址 `0x200540AC`，修复版 map 严格符号行解析 +
  `SEGGER RTT` 签名会话双重核对）；完整启动序列四行在案（HANDOFF/
  Reset/QSPI/目标行），黑屏已解除。

## 2. 板卡状态历史链（如实登记）

1. **20801 阻断**（原始前置）：BCB vcode 20801 与运行镜像 3.2.0(30200)
   不一致，`ota_backup.c:385` 一致性检查会拒绝 STAGED 提交——2026-09-13
   经批准恢复方案 v5（S1A-S6）消除，r1 终态=生产 App 3.2.0(30200)
   `d9753484…` + BCB CONFIRMED/30200（v3/v4 冻结绑定的板卡事实）。
2. **O2 实测（2026-09-14 17:0x）**：PRODUCT_FAIL，但板卡未被改动——
   缺陷固件只完成传输+落盘 staging，未写 BCB 未复位；J-Link 三次只读
   实证（staging 槽头 `ETSL`+COMMIT_MARKER、payload 头与旧 toy ETU
   逐字节全等、板上 fw_header 仍 3.2.0 `d9753484…`；BCB=CONFIRMED 由
   断电重启后版本不变的运行行为反证闭合）。证据
   `.cache/p3-3-o2-jlink/`（staging-slot.bin `a095bbd1…`、
   staging-payload-head.bin `cbdb2346…`、app-fw-header.bin
   `ddff9540…`）与主执行笔记 §14。
3. **烧录事故（2026-09-14 晚）**：实现 agent 重建固件烧板时误烧未
   finalize 裸构建镜像 → boot `validate_internal_app` 拒跳 →
   `begin_rollback` 置 BCB=ROLLBACK(30200) → 外部 backup/recovery 槽均
   无效 → 恢复等待死等 → 黑屏。无持久损伤；复盘与教训见主执行笔记
   §16（GCC 产物烧板前必须 finalize）。
4. **r2 恢复（2026-09-14 晚，本轮）**：CLEAR_BCB 链 S1A-S6 全 PASS，
   终态见 §1。脚本 `Tools/jlink/p3-3-recovery-execute.ps1` 三处参数化
   适配（S2 基线 30200/ROLLBACK、S1B BootWait 断言模式、修复版 map/
   ExpectedAppSha256）随 freeze_commit 入库，离线自测与执行前预检
   留证见 r2 留证 §1。

## 3. r2 完成判据四条映射（全部满足）

1. 生产 Boot 已按全区恢复 —— S6 restored SHA = S1A backup SHA =
   `b6b33a82…` 全等。
2. 板上 App 身份 —— S5 app_sha256 与 finalize 头 image_sha256
   `24fc02ea…` 全等，app_vcode=30200。
3. BCB 与 App 一致 —— S5 CONFIRMED(4)/cur_vcode=30200/seq=0/
   app_result=VALID。
4. 新鲜终证 —— S6 复位⑥后生产 App RTT 自报 `OTA: BCB already
   CONFIRMED vcode=30200`（RTT 日志与签名会话在
   `.cache/p3-3-recovery-execute/20260914-r2/`）。

## 4. 额度实账（对齐申报口径）

| 项 | 授权上限 | 实际消耗 |
| --- | --- | --- |
| J-Link 命令会话 | 10 | **10/10**（S1A 1+S1B 1+S2 2+S3 2+S4 1+S5 2+S6 1） |
| 主动复位 | 6 | **6/6** |
| RTT logger | 2（各 ≤120s） | **2/2**（S4、S6 各 1） |
| RTT 签名会话 | ≤2 | **2/2**（mem8 只读） |
| WFI 重试 | 单 Phase ≤2 | 0（全部首连成功） |

r2 零超授权、零自动重试。历史偏差销账：r1 轮命令会话 11/10（+1 只读
确认，收尾确认阶段拆会话所致）已经用户 2026-09-14 追认（「此外你说的
超授权问题也一并授权」），不再列为待决。

## 5. 写入边界（r2 实际执行面）

写入仅：boot 区 0x08000000-0x08004FFF（测试 Boot 烧录+S6 还原生产
Boot）、EEPROM 0x00-0x7F（S3 CLEAR_BCB，清空前双块 128B 留档）、RAM
控制块 0x20057E00-0x20057FFF（命令字，复位即失）。App 区 0x08010000
与 QSPI 槽零写入。恢复授权与 O 序列、历史 A1/B1-M 配额不互借。

## 6. 原始证据指针

- 轮次目录: `.cache/p3-3-recovery-execute/20260914-r2/`（67 文件：各
  Phase `-result.json`、J-Link 会话日志、二进制读回留档、S2 BCB 双块
  raw、S4/S6 RTT 日志等）
- 统一留证: `docs/ota-exec-notes/P3-3-recovery-execution-2026-09-14-r2.md`
- 事故复盘: `docs/ota-exec-notes/P3-3-speedometer-real-ble-fix-2026-09-14.md` §16
- r1 历史轮: `.cache/p3-3-recovery-execute/20260913-r1/` +
  `P3-3-recovery-execution-2026-09-13.md`（额度偏差追认见其 §4）

## 7. 边界

- 恢复属独立真机准备操作，不并入本合同判据；本输入的解决证据即上述
  四判据留证。四判据满足前 C-TOY-LOOP/C-REAL-LOOP 不得执行（已满足）。
- v5 toy（30201）与板上 3.2.0-fixed（30200）功能本体逐字节同源（仅
  41 字节头身份字段差异，见 EXT-TOY-BOOTABLE 证据 §3），O2 升级烧写
  的镜像与当前板上运行代码本体一致。
