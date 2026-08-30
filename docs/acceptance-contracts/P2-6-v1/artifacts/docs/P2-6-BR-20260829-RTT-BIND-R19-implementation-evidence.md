# P2-6-BR-20260829-RTT-BIND-R19 离线实现、根因修复与双分支冒烟证据

- 日期：2026-08-29（撰写）/ 2026-08-30（冒烟与定稿）
- 会话：R19 实现 agent（非验收；不自验收、不 commit/push）
- 分支：`p2-6-implementation-20260819`，HEAD=`99173123cae8c487b86efa8a4eecbbe73b1bb512`（与 origin/main 一致）
- 输入：`docs/ota-exec-notes/P2-6-R18-watchdog-root-cause-and-verified-fix.md`（R18 三臂受控实验根因）、R17 冻结脚本（`.cache/p2-6-rtt-binding-20260829-15`，只读）
- research 落盘：`docs/ota-exec-notes/P2-6-R19-wdt-pause-research-2026-08-29.md`

## 0. 结论摘要

R19 在 R18 已坐实的看门狗根因之上交付了四件事：

1. **WDT 暂停修复落地（含语法纠正）**：每个 halt 会话在 `monitor halt` 之后写
   `monitor WriteU32 0xE0042008 0x00001000`（**空格分隔**，逗号形式被 server 拒绝，
   见 §2.1）。两模板（readback.gdb.in / binding.gdb.in / binding-post.gdb.in）全部
   插入，生成器与静态审计双向钉死唯一性与位置。
2. **三项冒烟暴露的新缺陷全部修复**（§3）：GDB 无法在 attach 后重开
   may-insert-breakpoints；GDB server 的 RTT telnet 通道在本 J-Link 上永远只给
   107B banner（R4 现象复现并定因）；postcheck 的全 SRAM 不变断言依赖旧单会话假设。
3. **两个决策分支全部真机验穿**（§5）：no-flash 分支（根 -21）与 flash 恢复分支
   （根 -23，含 gate-post 三遍复读）均以 `RTT_CHANNEL_BINDING_VERIFIED` 收官，
   manifest 封存复算通过。
4. **R18 两缺陷修复**（§4）：s_halt=0 全量上报；R17 文档 §7 计数矛盾就地更正。

附带发现（§6）：板载 boot 会对漂移 App 做全镜像 SHA 校验并从备份槽自主恢复
v2.8.0——该机制解释了 R12"flash drift"现象的来源，也是本冒烟 B 注入策略的约束。

## 1. 证据根清单

| 根 | 用途 | audit-id | 硬件 |
|---|---|---|---|
| `.cache/p2-6-rtt-binding-20260829-18` | **正式验收根**（母版，pristine） | `P2-6-BR-20260829-RTT-BIND-R19-03` | 0 次 |
| `.cache/p2-6-rtt-binding-20260829-21` | 冒烟 A（no-flash 分支） | `P2-6-BR-20260829-RTT-BIND-R19-06` | 已消耗 |
| `.cache/p2-6-rtt-binding-20260829-23` | 冒烟 B（flash 分支） | `P2-6-BR-20260829-RTT-BIND-R19-08` | 已消耗 |
| `.cache/p2-6-rtt-binding-20260829-16/-19/-20/-22` | 冒烟迭代消耗根（缺陷暴露轮次） | R19-01/04/05/07 | 已消耗 |
| `.cache/p2-6-r19-wdtpause-probe-01` | 探针根（语法/并发/RTT 通道行为） | — | 诊断 |
| `.cache/p2-6-r19-drift-inject-01` | 漂移注入/恢复工具根 | — | 诊断 |
| `.cache/p2-6-r19-offline-tests` | 离线测试/审计输出根 | — | 无 |

冒烟根由母版复制后仅替换 3 个文件（run_recovery_binding.py / run_binding.py /
test_recovery_policy.py）中的根名与 audit-id 字面量；其余 10 个冻结脚本逐字节一致。

## 2. WDT 暂停修复（R18 根因的落地）

### 2.1 语法实测纠正（任务书预判成立）

任务书第 3 条要求先低成本验证 monitor 写与 `set may-write-memory off` 的交互。
探针根 `.cache/p2-6-r19-wdtpause-probe-01` 两轮实测：

- 第一轮脚本 B（负对照）：完整五开关 off 下，GDB 级写
  `set *(unsigned int*)0xE0042008 = ...` 被正确拒绝（`Writing to memory is not
  allowed (addr 0xe0042008, len 4)`）；同时 `monitor WriteU32 0xE0042008, 0x00001000`
  （**逗号形式**）被 server 拒绝（`Expected an decimal digit (0-9)`），读回
  0x00000000 证明未写入。
- 第二轮四个变体（空格十六进制 WriteU32 / MemU32 / mww / 空格十进制）全部生效：
  server 回显 `Writing 0x00001000 @ address 0xE0042008`，GDB 读回 0x00001000，
  且全部会话都在 `set may-write-memory off` 下运行——**monitor 写直达 GDB server，
  不受该开关阻断**（R18 §6.2 的未证实点就此闭合）。

结论：**正确语法是空格分隔** `monitor WriteU32 0xE0042008 0x00001000`；R18 推荐的
逗号形式不可用。该行不匹配 generate_readback_gdb.py 与 run_binding.py:638 的任何
禁令模式，已按任务要求纳入静态审计白名单（见 §7 偏离登记）。

### 2.2 插入点与钉死

- 三个模板（`readback.gdb.in`、`binding.gdb.in`、`binding-post.gdb.in`）的
  `monitor halt` 之后各插入一行（binding 会话 halt 数分钟——441 chunk + 3×512KB
  SRAM dump——同样超 10 s WDT 窗口，必须暂停；任务书点名 readback，冒烟证明
  binding 缺它同样必死）。
- 钉死断言：`generate_readback_gdb.generate` / `generate_binding_gdb.generate` /
  `generate_binding_gdb.generate_post` 均断言该行唯一存在且紧跟 `monitor halt`；
  `run_recovery_binding.audit_readback_scripts` 与 `run_binding.audit_scripts`
  同步校验；server log 侧新增 `Received monitor command: WriteU32 ...` 回显
  count==1 校验（recovery_policy.validate_readback_server_log 与 binding 两侧），
  证明每个 halt 会话确实施加。
- `wdt_pause` 断电即失、不复位跨会话：每个 halt 会话自设，result JSON 按
  会话分别记录回显计数（冒烟实测 1+1）。

## 3. 冒烟暴露的三个新缺陷与修复

冒烟 A 第一轮（根 -16）在恢复阶段全链通过（gate-pre 三遍 s_halt=1、共识
AUTHORITATIVE、最终 reset 证据齐全——**R18 根因修复端到端生效**），binding 阶段
连续暴露以下缺陷，逐一修复并重跑：

### 3.1 GDB 无法在 attach 后重开 may-insert-breakpoints（缺陷 1）

- 现象：`binding.gdb:959: Error in sourced command file: Cannot change this setting
  while the inferior is running.`——三个开关（memory/registers/call-functions）
  可切换，唯独 `set may-insert-breakpoints on` 在 attach 后无条件被拒。
- 探针 E 最小复现：`monitor halt` 后立即切换同样被拒，与 dump/shell 无关，是
  GDB 13.3 对该 remote 会话设置的硬限制。R4 真机成功脚本从未关过该开关（默认开）。
- 修复（Fix A）：binding 模板永不触碰 may-insert-breakpoints（脚本内无任何
  break 命令，受控调用需要返回地址断点；其余四重保护照旧在调用窗口外关闭）。
  audit_scripts 钉死该开关零出现（行首命令形式）。
- 测试：`test_binding_template_never_toggles_insert_breakpoints`。

### 3.2 GDB server 的 RTT telnet 通道在本 J-Link 上只给 banner（缺陷 2）

- 现象：capture 阶段 telnet 连接 24363 只收到 107B banner（`RTT payload timeout`）
  ——与 R4 时代的"107B banner-only"完全同形。
- 探针 F1 定因：telnet 客户端先连接、目标 `monitor reset`+`monitor go` 让固件
  全速运行并输出 RTT 突发，telnet 仍零 payload。**该通道在这套
  V8.18 server + ARM-OB V7.00 J-Link 上永远不投递环数据，与核心状态无关。**
- 替代通道实证（探针 G/H）：`JLinkRTTLogger`（项目全程的权威 RTT 读取器）在
  **独立 probe 连接**下完整读出环内容（286B 恰等于 [RdOff,WrOff) 待读字节，
  与 GDB 快照逐字节一致，且推进 RdOff 0→286）；存活的 logger 与 GDB 会话
  并发无碍。`-singlerun` server 在首个 GDB 断开后退出是探针 G"post 连接失败"
  的真实原因（非 logger 干扰）。
- 修复（结构重构，binding 拆两会话）：
  1. 会话 1（binding.gdb）至 precheck ELIGIBLE 结束（`PRECHECK_COMPLETE` 后
     disconnect；capture/postcheck shell 阶段移出）。
  2. 会话间：`binding_host.py --phase capture`（重写为 logger 版）以独立
     JLinkRTTLogger 连接读取 Up0 待读字节，与 precheck 的 pending 逐字节比对，
     静默期确认无多余字节；logger 按 AGENTS.md 残留清理模式停止（该工具无自然
     退出，此为本流程唯一由 host 终止的进程，capture.json 显式披露），验证零残留。
  3. 会话 2（新模板 binding-post.gdb）：halt + wdt 暂停 + 4 个 post 快照 dump +
     postcheck shell + 状态检查 + `CAPTURE_PASS`/`PASS channel_binding=1` 终标。
  4. run_binding.py：两会话 + 中间 capture 的编排、marker/分类/结果字段扩展、
     server 双实例自然退出与端口清零校验。
- 计数变化：binding.gdb dump 458→454（post 4 dump 移入会话 2）；生成物
  +binding-post.gdb；FROZEN_SCRIPTS +binding-post.gdb.in。
- postcheck 语义保留：payload==pending、WrOff 不变、RdOff 恰好推进到 WrOff、
  环字节不变、measurement 不变——全部原样保留。

### 3.3 postcheck 全 SRAM 不变断言依赖旧单会话假设（缺陷 3）

- 现象：冒烟 A 第三轮（根 -20）capture PASS（737B 逐字节）后 postcheck 报
  `SRAM changed outside the four-byte Up0 RdOff word`。
  > **更正（R20 收口，2026-08-30；来源：本轮对 `.cache/` 的实地枚举 + 独立验收
  > 通过判定所依据的正式验收根 -18 执行记录 `logs/result.json`）**：该缺陷叙述
  > 属实并保留，但**根 `-20` 已被后续冒烟迭代覆盖/未留存，磁盘上现已不存在**
  > （现存根为 -16/-18/-19/-21/-22/-23 等），因此本条现象无法再由 -20 自身
  > 复算。缺陷与修复本身由两条独立证据链坐实：①离线变异测试
  > `PostcheckSemanticsTests` 三例（无关 SRAM 变化放行、控制块越界 fail-closed、
  > 环/measurement 变化 fail-closed）；②根 -21、-23 两轮真机全链复现修复后语义
  > （postcheck PASS，控制块 RdOff 字外零变化）。本更正不新增、不推定、不编造
  > 任何证据根。
- 定因（探针 I6）：GDB server 退出时把核心恢复为运行态（"Restoring target
  state"），两会话之间固件合法地改写 RAM——全 SRAM 字节稳定断言在两段式结构下
  结构性不成立。
- 修复（重定域）：改为 **RTT 控制块整体字节 diff（0xA8B 中只许 4B RdOff 字变化）**
  + 环字节不变 + measurement 不变（原有）；全 SRAM 断言移除并在结果中显式记录
  `sram_mutation_scope` 说明（核心在会话间合法运行，RTT 结构外 SRAM 允许变化）。
  logger 的唯一合法写目标就是 RdOff 字，控制块级 diff 恰好覆盖其副作用面。
- 测试：`PostcheckSemanticsTests` 三例（无关 SRAM 变化放行、控制块越界变化
  fail-closed、环/measurement 变化 fail-closed）。

## 4. R18 两缺陷修复

- **缺陷 a（s_halt=0 严重少报）**：`recovery_policy.validate_readback_pass_log`
  的 `running[:8]` 截断改为全量上报——错误串给出真实计数与完整 chunk/phase 列表，
  details 附全量结构化标记。测试 `test_core_running_mid_pass_fails_closed`
  强化（294/294 全列断言）+ 新增 `test_partial_running_marker_list_is_fully_reported`
  （13 条部分翻转全报）。
- **缺陷 b（R17 文档 §7 计数矛盾）**：`P2-6-BR-20260829-RTT-BIND-R17-01-offline-evidence.md`
  §7 就地更正为"新增 2 条离线测试、43→45"，并标注 R19 更正来源（该文档其余
  内容不动）。

## 5. 双分支端到端冒烟结果（任务 6）

### 5.1 冒烟 A：no-flash 分支（根 -21，audit-id R19-06）

| 阶段 | 结果 |
|---|---|
| gate-pre 三遍 | 147×3 chunk，s_halt 全 1，WDT 暂停回显 1/遍 |
| 共识 | `BOARD_IMAGE_AUTHORITATIVE`（板卡=权威 SHA A2D3083B...） |
| flash 决策 | 不 flash（loadbin=0），一次最终 reset（PC=0x0802BC34、VTOR=0x08010000、CFSR=0、SD=1、owner=0） |
| binding 会话 1 | identity 441 chunk+4 spot PASS、STATE_PASS、precall PASS、受控 PATCH/REPORT 调用 PASS、MEASUREMENT_PASS、INVENTORY_ELIGIBLE、PRECHECK_COMPLETE |
| capture | logger 独立连接 1.9s 读出 731B，与 pending 逐字节一致，静默期无多余，零残留进程 |
| binding 会话 2 | POST_SESSION_ATTACHED、STATE_UNCHANGED、post 快照 4 dump、postcheck PASS（控制块 RdOff 外零变化） |
| 判定 | **`RTT_CHANNEL_BINDING_VERIFIED / UP0_RING_BYTES_AND_RD_OFF_PROVEN`**，14 marker 全 1，两会话 gdb rc=0 |
| 封存 | manifest 965 文件，verify_manifest 复算通过（missing/extra/late 全 0） |

### 5.2 冒烟 B：flash 恢复分支（根 -23，audit-id R19-08）

漂移注入（§6）后板卡为 v2.8.1+1 字 clear-only 漂移（0x08062DF8：
0xFFFFFFFF→0xFFFFFF3F，注入方式 noreset 保持核心在 App 内、boot 不运行）：

| 阶段 | 结果 |
|---|---|
| gate-pre 三遍 | 共识 `STABLE_CLEAR_ONLY_FLASH_DRIFT`（difference=1、clear-only=1、reverse=0） |
| flash 决策 | `loadbin=1 + verifybin=1`（全镜像权威恢复，JLink Commander 默认设置） |
| gate-post 三遍 | 共识 `BOARD_IMAGE_AUTHORITATIVE`（恢复后复读为权威） |
| 最终 reset | 通过（reset 证据齐全） |
| binding 全链 | 同冒烟 A：capture 735B 逐字节、postcheck PASS、**`RTT_CHANNEL_BINDING_VERIFIED`** |
| 封存 | manifest 1489 文件（含 gate-post 441 chunk+3 镜像），verify_manifest 复算通过 |

### 5.3 板卡终态

冒烟 B 后真值直读：`0x08010408=0x00005141`（vcode 20801）、`0x08062DF8=0xFFFFFFFF`
（漂移已恢复）、核心运行中；零残留 J-Link/GDB 进程、24361-24364 零监听。

## 6. 附带发现：boot 的备份自主恢复机制（R12 "drift" 同源）

冒烟 B 首轮注入失败的完整因果链（证据：`.cache/p2-6-r19-drift-inject-01/logs/`）：

1. 首次注入用 `loadbin`（隐式复位并 halt 在复位向量）+ `g`——`g` 从复位向量
   恢复运行 = **boot 运行**。
2. boot 对 App 做全镜像 SHA 校验（P1-7 已证 handoff 全镜像 SHA），发现漂移 →
   从备份槽恢复 App → 板卡整体变成 v2.8.0（sha 精确等于冻结 v2.8.0 测试镜像
   AB38A4E7...E569A5E5，冒烟 B 首轮 gate-pre 三遍一致读出并正确判
   `UNEXPECTED_BOARD_IMAGE` fail-closed）。
3. **这解释了 R12 "board Flash drift after R11" 的来源**：任何让带缺陷 App 走过
   一次 boot 的流程都会触发备份恢复/改写，历史上的"漂移"很可能是 boot 自主行为
   的副产物而非闪存位衰减。此判断留待后续裁定会话复核，本会话不改任何产品代码。
4. 正确注入方式（本轮实证）：`loadbin <chunk>, <addr>, noreset` 保持核心在 App
   内 halted，编程后 `g` 直接恢复 App——boot 全程不运行，漂移稳定存活到
   gate-pre。另：R17 的 `jlink-settings.ini` 含 `EnableFlashDL=0`（只读会话专用），
   用它跑 loadbin 会静默不写闪存（"Downloading...O.K." 无任何 erase/program
   时序行）——注入/恢复必须用默认设置。

## 7. 冻结交付与 §6 命令（正式验收根 -18）

### 7.1 交付脚本 SHA-256（母版根 -18，13 冻结）

| 文件 | 字节 | SHA-256 |
|---|---|---|
| binding.gdb.in | 8674 | 663CE9D5FCA71E388EFF27D884B7B9488896B56AB38D2AFDABA3AA153AC48964 |
| binding-post.gdb.in | 3008 | E27346FFAB896D5591F81E179B441EE457D581FAC2D38189778995A6AF3944C2 |
| binding_host.py | 40592 | 9C8BCDED2D0EAF3A536749C57D64D0268E3D50CF49C3EA444EE797A196AF66EE |
| generate_binding_gdb.py | 9103 | 64A4797F01B836AC2585B59A33C0C2B06BB98E4B70153CDBFD9E88BB820921BC |
| generate_readback_gdb.py | 12437 | 68B6B8518A6E686CE72856C6111D4470D247CF93069A68C02EEE3C7E05C6107E |
| jlink-settings.ini | 767 | 849D80A1B2985411396B1884A8BE4717ECE4B4A77BA10E08E36FE408A80B1C13 |
| precall_audit.py | 5149 | CCA63DDB0760C46BD02DADF2578B50F394949DB2557B378EF06F367982E50A24 |
| readback.gdb.in | 1031 | 080DB3FA56CB2306A82D8EA271B26B82DEE524CC07DEB1FBF92C04D79CF8B0B7 |
| recovery_policy.py | 36048 | 6748C94E76489F0FB4EFC99D7AFEB8494FE6115D676B445A6FB6656AF745AE10 |
| run_binding.py | 86968 | CB7798D476D25FBCB6468B45C86DA864827F5C35CA209F025C97F6D2C9E1C3B2 |
| run_readback.py | 14684 | 386746076DCF4CDFFF5DE10EABC7B3BF6174A675580143C1E0405D77D546241D |
| run_recovery_binding.py | 38891 | E8313CC64B151C75587E9CBA2C31348AD8C621F7CB9D8DD826D9D87D6825D666 |
| test_recovery_policy.py | 52359 | 26565FDC34B12E681C3C3666F63C63719CB218FADAA1084403867713B7A62018 |

生成物（由生成器按 `--evidence-name p2-6-rtt-binding-20260829-18` 物化，验收方
可复算）。下表为 R20 收口会话在正式验收根 -18 的 `scripts/` 内**实读复算**结果：

| 生成脚本 | 字节 | SHA-256 |
|---|---|---|
| binding.gdb | 103655 | BD3B5445C53096F01C5FDDFDA4AF8DA332C4D0FB25E4E2F051780D05702121D8 |
| binding-post.gdb | 3051 | 90DF212F4BBB73DA071B18E629B7D798CAF320AB3BD28A846171BB0BFDB117E9 |
| readback-gate-pre-a.gdb | 84573 | BE33110E49E3EA890F8B5E927F9965213C6B3DCA3A239184256C69F96FCE331D |
| readback-gate-pre-b.gdb | 84573 | 4786363036AA637FF4042A7A8229471C172EFE47EBEB7BD393717239B4DE6C3F |
| readback-gate-pre-c.gdb | 84573 | 82921E9548861E3D61E89E638761B1D1EAADD73625EF86D3FAE8F986345BE55C |
| readback-gate-post-a.gdb | 84870 | 7093742584419F90D83A3808A0641880D718E0DDD3B553A0FCA2DCB39AF978E1 |
| readback-gate-post-b.gdb | 84870 | 331537AF3BAC80A6BC8B5F8CABEB1C4E331EE63C2D86DAF5A328E60D9C1C5588 |
| readback-gate-post-c.gdb | 84870 | 123A7C46E7C25590A821CDCB2A79DB4AC739DB7D851AD38294F2D3655A8B0E16 |

6 个 `readback-gate-*.gdb` 每脚本 147 dump + 294 DHCSR 标记 + 1 行 wdt 暂停。

> **更正（R20 收口，2026-08-30；来源：对根 -18 `scripts/` 的逐文件 SHA-256 复算，
> 该根为独立验收通过判定所依据的正式验收根）**：
> ① 原文 `binding.gdb` 的缩写尾部写作 `BD3B5445...121AD8`，实测尾部为
> `...702121D8`，已按实读值更正为完整 SHA-256；
> ② 原文 6 个 `readback-gate-*.gdb` 只给了形状计数、缺字节数与 SHA-256，
> 现按实读补齐（pre 三份各 84573 B、post 三份各 84870 B，互不相同）。
> 其余行（binding-post.gdb 3051B）复算与原文一致。

冒烟根 -21/-23 与母版仅 3 个根名钉死文件不同
（run_recovery_binding.py 的 validate_pristine_root 根名、run_binding.py 的
DEFAULT_EVIDENCE、test_recovery_policy.py 的样例根名/AUDIT_ID）。

### 7.2 硬件启动命令（唯一，供独立验收会话执行）

```
C:/Users/SU/AppData/Local/Programs/Python/Python313/python.exe ^
  D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-18/scripts/run_recovery_binding.py ^
  --audit-id P2-6-BR-20260829-RTT-BIND-R19-03 ^
  --evidence-root D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-18
```

bash 形式：

```
cd /d/github/my/E-Track && "C:/Users/SU/AppData/Local/Programs/Python/Python313/python.exe" \
  .cache/p2-6-rtt-binding-20260829-18/scripts/run_recovery_binding.py \
  --audit-id P2-6-BR-20260829-RTT-BIND-R19-03 \
  --evidence-root "D:/github/my/E-Track/.cache/p2-6-rtt-binding-20260829-18"
```

前置条件：端口 24361-24364 无监听、无 J-Link/GDB/RTT-logger 残留进程；
根保持 baseline/logs/snapshots/tmp 全空（当前实测如此）；板卡当前为权威
v2.8.1 运行态（预期走 no-flash 分支；若板卡状态变化，flash 分支已在冒烟 B
同构验穿）。命令零环境前缀（B-1 自举在位，默认环境实测 exit 0 零污染）。

### 7.3 显式偏离登记（复核者必读）

**本命令执行的硬件动作包含一项 host 侧调试域写入偏离与一项 logger 生命周期偏离，
未施加二者而逐字复现 §7.2 的旧式复核者必然失败或误判：**

1. **每 halt 会话一次调试域寄存器写**：`monitor WriteU32 0xE0042008 0x00001000`
   （`debug apb1_frz` bit12 `DEBUG_WDT_PAUSE`）。非 flash、断电即失、不改被测
   镜像字节与其 SHA-256；是 >10 s 连续 halt 读回的物理前置条件（R18 根因）。
   每个生成 GDB 脚本恰一行、紧跟 `monitor halt`，server log 回显 count==1 被
   fail-closed 校验。
2. **RTT logger 的 host 侧停止**：capture 步骤的 JLinkRTTLogger 是长运行采集器、
   无自然退出，按 AGENTS.md 残留清理模式（Stop-Process）停止并验证零残留；
   这是本流程唯一由 host 终止的进程（server/GDB 仍严格自然退出），
   capture.json 显式记录 `logger_stopped_by`/`logger_stopped`/残留计数。
3. **两段式 binding 结构**：GDB server 的 RTT telnet 在本 J-Link 上只给 banner
   （探针 F1 定因），payload 由会话间独立 logger 连接采集；两会话之间核心被
   server 恢复为运行态，postcheck 的字节稳定断言因此重定域到 RTT 控制块
   （RdOff 字外零变化）。复核 RTT 证据时以 capture.json + postcheck.json +
   rtt-payload.bin + rtt-cb-pre/post 快照为准，不再有 telnet 通道产物。

## 8. 离线自证（全部可复跑）

- `py_compile` 9 脚本全绿（pyc 落 `.cache/p2-6-r19-offline-tests/pycache`，
  scripts/ 零 `__pycache__`）。
- `test_recovery_policy.py`：**59/59 OK**（P2_6_OFFLINE_TEST_ROOT 指向
  `.cache/p2-6-r19-offline-tests/scratch`；45→59：+2 watchdog 模板钉死/移位负例、
  +1 binding 模板不碰 may-insert-breakpoints、+1 会话 1 尾部形状、+1 post 模板
  形状、+1 post 模板缺 watchdog 负例、+1 postcheck 语义源断言、+3 postcheck
  语义行为例、+1 server log 无 WriteU32 回显负例、+1 部分翻转全报例、
  +1 s_halt 全量上报强化——计入强化不改名）。
- 离线静态审计（`--offline-audit`，母版根）：exit 0，pass=true，
  schema `p2-6-r19-offline-static-audit-v1`；readback 6 脚本 147 dump/294 DHCSR/
  wdt 行齐全；binding/post 脚本零禁令命中；19→21 脚本集；14 项钉死输入哈希
  复核通过；git 三元组一致。
- 默认环境（剥除全部字节码变量）复现：exit 0、零 `__pycache__`、
  scripts 集合与 SHA 运行前后一致。

## 9. 边界合规

- 被测镜像权威身份未动：600744 B / SHA-256 `A2D3083B...D58E00` 全程不变；
  未调用 `debug_apb1_periph_mode_set`，未改任何固件/生产源码/boot。
- `S_HALT=1` 闸门语义未动：修复只让前置条件成立（冒烟实测三遍 294/294 全 1）。
- R14/R15/R16/R17/R18 证据根只读（R17 根仅在离线比对时读取快照，未写入）。
- 无 terminate/kill/taskkill 于 server/GDB 进程（两会话均自然退出、端口清零）；
  唯一 host 终止的是 RTT logger（AGENTS.md 规定流程，§7.3 已披露）。
- 全部产物落项目内（TEMP/APPDATA 重定向至各根 tmp/）；探针期间的诊断输出
  未写项目外（一处临时 /tmp 诊断文件已删除）。
- 未创建验收合同（按 R17 流程，由验收侧在候选稳定后冻结）；
  未 commit/push；本卡交非实现会话验收。
  > **状态更新（R20 收口，2026-08-30）**：独立验收已判 PASS，合同与证据矩阵已由
  > R20 收口会话按该流程冻结于 `docs/acceptance-contracts/P2-6-v1.contract.json`
  > 与 `docs/acceptance-contracts/P2-6-v1/P2-6-v1.evidence-matrix.json`；
  > "合同在验收之后冻结" 已作为流程偏离在合同内如实登记。

## 10. 与 R17 交付的差异总表

| 维度 | R17 | R19 |
|---|---|---|
| WDT 暂停 | 无（R18 根因） | 每 halt 会话一行，生成器+审计+server 回显三重钉死 |
| binding 结构 | 单会话（telnet capture 内嵌） | 两会话 + 会话间 logger capture |
| capture 通道 | GDB server RTT telnet（真机不可用） | JLinkRTTLogger 独立连接（真机 737/731B 逐字节验证） |
| may-insert-breakpoints | 头部 off + 调用前 on（真机必死） | 全程不触碰（钉死零出现） |
| postcheck 稳定性断言 | 全 SRAM 仅 RdOff 字变化 | RTT 控制块仅 RdOff 字变化 + 环/measurement 不变 |
| s_halt=0 上报 | [:8] 截断（185 报 8） | 计数+全量列表+结构化 details |
| 离线测试 | 45 条 | 59 条 |
| dump 总数（binding） | 458 | 454（post 4 dump 移会话 2） |
| 真机验证 | 从未跑通 | 双分支全链 RTT_CHANNEL_BINDING_VERIFIED |
