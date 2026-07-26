# P0 阶段审查报告（是否可进入 P1）

> 历史快照说明：本文记录 2026-07-26 收口提交前的独立审查状态。报告中关于“尚未提交”和“待补 CI”的事项，随后已由 `1398d5c`、`7e108d2`、`270e389`、`bd42749` 及 MCU Firmware Build run `30199252465` 完成。本文保留为审计轨迹，不代表当前 `HEAD` 状态。

审查时间：2026-07-26 ｜ 审查人：主会话 Claude（独立复核，非实现者）

## 一、审查范围与方法

- 状态源：`PLAN-OTA-EXEC.md`（工作区最新版）
- 证据核验：独立重跑 PC 侧测试 + 抽查真机 RTT 日志 + git 工作区状态
- 参考：`docs/ota-exec-notes/P1-P2-layout-toolchain-issues-2026-07-26.md`（P1/P2 开工前问题清单）

## 二、P0 六卡状态核验

| 卡 | 看板状态 | 本次独立抽查 | 结论 |
|---|---|---|---|
| P0-1 契约成文 | 完成（三轮打回后过） | 契约文档在库（ffeaef8 已提交） | ✅ |
| P0-2 打包工具 | 完成 | —（d2c851a 已提交，历史验收链完整） | ✅ |
| P0-3 golden vectors | 完成 | 本次重跑 `test_vectors.py` = **9/9 OK** | ✅ |
| P0-4 EEPROM/BCB | 完成（2026-07-26 复审整改后重新真机验收） | 本次重编重跑宿主单测 = **27/27 PASS, 0 failure**；RTT 日志核验 `BCBSTRESS: done ok=1000 fail=0`，错误行 grep=0 | ✅ |
| P0-5 QSPI 安全化 | 完成（同上重新真机验收） | RTT 日志核验 `JEDEC=0xEF4018 whitelisted, OTA enabled` + `inject timeout rc=1 (PASS)` + `done ok=1000 fail=0` | ✅ |
| P0-6 RAM/overlay | 完成 | 契约 §10 回填在库（cff22d5） | ✅ |

关键风险点已闭环：2026-07-26 复审整改（bcb_commit seq+1、EEPROM 0xFF 保护、QSPI 状态传播等）导致历史真机证据失效、P0 曾回退 4/6 —— 已由非实现会话用**当前源码**重新构建/烧录/采集全新 RTT 日志（`P0-4-P0-5-independent-rtt-2026-07-26.log`）复核通过，旧日志未复用。调试宏 `CONFIG_EEPROM_BCB_STRESS` / `CONFIG_QSPI_SELFTEST_ENABLE` 已确认复位为 0，默认固件已重建（Track.bin / X-Track.axf mtime 2026-07-26 17:44）。

## 三、遗留问题（不阻断 P0 结论，但需在进入 P1 前处理）

1. **【收口未完成，最高优先】P0-4/P0-5 复审整改的实现与看板更新尚未提交**。
   HEAD 停在 `cff22d5`，工作区有 15 个实质改动文件未提交（EEPROM/eeprom_bcb/msc_diskio/qspi 头/HAL_EEPROM/HAL_W25Q128/test_bcb_arbiter/PLAN-OTA-EXEC.md 及 4 份证据文档），另有 2 份新证据文档未跟踪（`P0-final-combined-rtt-2026-07-26.md`、`P1-P2-layout-toolchain-issues-2026-07-26.md`）。
   → 已验收的真机证据对应的是**工作区代码**，不提交则"验收的代码"与"库里的代码"不一致，P1 基线漂移。按 OTA 规约 §0.6 需用户确认后由主会话小步收口。
2. **提交推送后需补一次 MCU Firmware Build 干净 checkout 绿证**（Libraries 源已变，上次 CI 绿证对应 f914854 时代码）。
3. **工作区杂物待清理/忽略**：`ssh`、`.ssh-config-github-*`、`.cache/`、`MDK-ARM_F435/cmake-generated/build-pre4-verify/`、`Tools/apply-github-ssh-schemeB.ps1` 等与 OTA 无关的未跟踪文件，勿混入收口提交。
4. 大量 USER/App/Simulator 文件在 `git status` 显示 modified，但 `--ignore-all-space` diff 为空 → 仅为换行符（LF/CRLF）触碰，非实质改动，收口时不应纳入。
5. `AGENTS.md` 的 UV4/手工 fallback 示例仍硬编码 AT32 旧路径（P0-4 验收时标注的非阻断残留，建议纯文档同步）。

## 四、进入 P1 的前置提醒（来自 P1-P2 问题清单，属 P1 工作项非 P0 缺陷）

- App/boot 当前均为旧 0x08000000 单体布局；`.fw_header` 无链接器落位；`VECT_TAB_OFFSET=0`；linker/scatter 均为无受控源的生成物 —— 这些正是 P1-1/P1-2 要解决的内容，开工前需先冻结双工具链 target 矩阵与受控 linker 源（清单 §8 放行条件）。
- 禁止：直接编辑 cmake-generated 的 .ld 当永久修复；App@0x08010000 + 普通 reset/run 当启动验收；复用旧 X-Track dep/lnp 验证新 target。
- P1-6 物理断电点需提前与用户排期。

## 五、评分与结论

- 技术维度：92（六卡证据链完整、验收分离执行到位、打回-整改-复验闭环规范）
- 战略维度：90（P1/P2 风险已前置分析成文；扣分项=收口提交未落地）
- **综合评分：91 ｜ 建议：通过**

**结论：P0 六卡实质工作与独立验收均已完成，无技术遗留缺陷；P1/P2 硬门槛已重开。可以进入 P1，但必须先完成第三节第 1 条的提交收口（用户确认后主会话执行），并在推送后补 CI 绿证。**
