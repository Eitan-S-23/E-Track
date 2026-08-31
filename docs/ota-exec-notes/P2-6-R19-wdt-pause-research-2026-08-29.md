# P2-6 R19 WDT 暂停修复研究落盘（实现前检索结论）

- 日期：2026-08-29
- 会话：R19 实现 agent（非验收）
- 输入：`docs/ota-exec-notes/P2-6-R18-watchdog-root-cause-and-verified-fix.md`（R18 三臂受控实验根因）、`.cache/p2-6-rtt-binding-20260829-15/scripts/`（R17 冻结脚本，只读）、`.cache/p2-6-r18-audit-tmp/`（R18 验收证据，只读）

## 1. 根因与修复向量（引用 R18，不重新调查）

- AT32 独立看门狗 10 s 超时（`HAL_Config.h:222-224`，喂狗在主循环 `HAL_Update()`）；核心被 halt 后喂狗停止，10 s 后 WDT 自复位。
- 单遍 147 chunk 读回 halt 约 26 s；R18 在 gate-pre pass-a chunk 54（≈10 s）处 `S_RESET_ST=1`，其后 93 chunk（63%）在非 halt 态读出，7 字节撕裂。
- 修复向量已真机验证：`0xE0042008`（`debug_type.apb1_frz`）bit12 = `DEBUG_WDT_PAUSE`。写 `0x00001000` 后 29 s halt 零复位、零 WDT 标志（R18 臂 B'）；错误地址 `0xE0042004` 写同值为阴性对照（臂 B，与纯只读逐位相同）。
- 语法已实测（R18 §6）：`monitor MemU32 <addr> <值>` 是**写**不是读（勿用）；正确写法 `monitor WriteU32 0xE0042008, 0x00001000`。

## 2. 插入点决策：两个模板都要插，不只 readback

任务点名 readback-gate-*.gdb，但分析证明 **binding.gdb 同样必须插**，否则冒烟无法跑通、正式轮必然在 binding 阶段复发同一复位：

- binding.gdb 的 `monitor halt`（binding.gdb.in:13）之后全程无 `monitor go`，核心持续 halt。
- identity 阶段 441 chunk dump（147×3 遍，单遍实测 ≈26 s ⇒ 仅此一项 >75 s）+ 3×512KB SRAM dump + up0/measurement dump，总 halt 时长达分钟级，远超 10 s WDT 窗口。
- R18 已证明该失效模式与读回脚本无关，只与"连续 halt >10 s"有关。binding 阶段若不暂停 WDT，gate-pre 修好后在 binding 内 chunk dump ~10 s 处同样自复位。
- 任务书本身把 `run_binding.py:638` 的禁令模式列为核对对象，且任务 6 要求冒烟"binding 测量"跑通——二者共同指向 binding 模板同样落点。
- 结论：`readback.gdb.in` 与 `binding.gdb.in` 两模板的 `monitor halt` 之后各插入一行 `monitor WriteU32 0xE0042008, 0x00001000`；生成器与静态审计两侧都钉死该行唯一存在且紧跟 `monitor halt`。

## 3. 审计面核对（该行是否触雷）

- `generate_readback_gdb.py` `FORBIDDEN_COMMAND_RES`：`^\s*(reset|load|...)\b`（行首裸命令）与 `^\s*monitor\s+(reset|load|loadbin|loadfile|erase)\b`——`monitor WriteU32` 均不匹配。
- `run_binding.py:634-642`（audit_scripts 对 binding.gdb）：`monitor\s+(reset|go|load)\b` 不匹配；`monitor halt` count==1 不受影响。
- `run_recovery_binding.py:365`（audit_readback_scripts）：`^\s*(reset|load|loadbin|loadfile|restore|flash|call|shell)\b` 不匹配。
- 生成的 readback 文本将被 `test_readback_scripts_are_never_generated_with_reset_or_flash` 断言 lowered 文本不含 `reset`/`loadbin`/`erase`——新行与注释必须避开这三个子串（含注释行）。
- `test_scripts_are_free_of_forbidden_words` 全脚本扫描 `majority`/`vote`/`retry`/`taskkill`/`TerminateProcess`——新代码与注释同样避开。
- server log 新增回显 `Received monitor command: WriteU32 ...`：不命中任何错误行正则；但 `validate_readback_server_log` 需新增该回显 count==1 校验（钉死每个 halt 会话确实施加该位），对应 synthetic server log 测试同步更新。
- 该行是对靶机的**调试域寄存器写**（非 flash、断电即失、不改被测镜像内容与哈希），必须在 baseline authorization 文本、recovery-static-audit JSON 与 R19 文档 §6 显式登记为偏离（任务 5）。

## 4. R18 两缺陷定位

- 缺陷 a（s_halt=0 严重少报）：`recovery_policy.py` `validate_readback_pass_log()` 中 `running[:8]` 截断——R18 实测 185 条 s_halt=0 只报 8 条。修复：错误串给出真实计数 + 全量 `chunk/phase` 列表，details 附全量结构化列表；`test_core_running_mid_pass_fails_closed` 增加全量计数断言钉死。
- 缺陷 b（R17 文档 §7 计数矛盾）：`P2-6-BR-20260829-RTT-BIND-R17-01-offline-evidence.md` §7 写"新增 3 条离线测试"实列 2 条（`test_static_audit_requires_bytecode_bootstrap`、`test_entry_points_bootstrap_bytecode_flag_before_local_imports`）；"原有 45 条总数不变"与实际 43→45 矛盾（R18 由整改前 .pyc 取证）。修复：就地更正为"新增 2 条、43→45"并标注 R19 更正来源。

## 5. 证据根命名与 per-root 差异

- 根名须匹配 `p2-6-rtt-binding-\d{8}-\d{2}`，且 `validate_audit_identity` 要求 audit-id 日期 == 根日期。
- 三个新根（R17 用 -15，顺延）：
  1. `p2-6-rtt-binding-20260829-16` — 冒烟 A（板卡当前态），audit-id `P2-6-BR-20260829-RTT-BIND-R19-01`
  2. `p2-6-rtt-binding-20260829-17` — 冒烟 B（另一决策分支），audit-id `P2-6-BR-20260829-RTT-BIND-R19-02`
  3. `p2-6-rtt-binding-20260829-18` — 正式验收根（pristine，硬件 0 次，交非实现会话），audit-id `P2-6-BR-20260829-RTT-BIND-R19-03`
- 母版在 -18 上开发与离线自证；冒烟根由母版复制后仅替换 3 个文件中的根名/audit-id 字面量：
  - `run_recovery_binding.py`（validate_pristine_root 钉死根名）
  - `run_binding.py`（DEFAULT_EVIDENCE）
  - `test_recovery_policy.py`（样例根名 5 处 + AUDIT_ID）
- dump 路径内嵌旧根名共 294 处（6 个 readback 脚本 × (147 dump + 147 DUMP_EXPECTED)），由生成器按新 `--evidence-name` 重新物化，不可复用旧生成物。

## 6. 板卡当前状态评估（决定冒烟顺序）

- R18 失败轮从未 flash（loadbin=0/reset=0）；其 gate-pre pass-a 的 chunk 0..53（含历史漂移字 0x08037D80=chunk 39 区域）与权威镜像逐字节一致（本会话离线复算，54 chunk 全 0 差异）。
- `p2-6-board-restore-20260828-01` 结论 `TARGET_ALREADY_MATCHED_FROZEN_SECTOR_NO_FLASH_NEEDED`。
- 判断：板卡大概率整体 authoritative；chunks 54..146 无任何漂移证据。
- 冒烟两分支覆盖策略：
  - 冒烟 A 跑当前态。若 gate-pre 判 AUTHORITATIVE（预期）→ no-flash 分支全覆盖（决策、最终 reset、RTT 采集、binding 测量、封存复算）；随后注入最小 clear-only 漂移再跑冒烟 B → flash 决策分支 + gate-post 全覆盖。
  - 若冒烟 A 意外判漂移 → flash 分支已覆盖且板子恢复 authoritative → 冒烟 B 免注入直接跑 no-flash 分支。
  - 两种结果都保证两分支各跑一次；正式轮（板卡 authoritative）走的恰是 no-flash 分支，故该分支必须冒烟。
- 漂移注入原则：优先选镜像内部**非头（0x400..0x460）、非哨兵 0x08037D80、非 identity spots（0x50948/0x51368）**的 0xFF padding 区清 2 位；若存在则注入后可 `r`+`g` 让固件正常运行（漂移字节永不执行）；否则 halt 挂起 + 本会话设置 wdt_pause。注入工具独立根 `.cache/p2-6-r19-drift-inject-01/`，JLink `w4` 写调试域 + `mem32` 读回确认。

## 7. 低成本未证实点（任务 3，先于一切正式动作）

`monitor WriteU32` 是否被 `set may-write-memory off` 阻断：R18 未实证（其验证脚本未设该开关）。验证设计（独立根 `.cache/p2-6-r19-wdtpause-probe-01/`）：
- 脚本 A（主证明）：完整关闭五开关（与 readback 模板一致）→ halt → `monitor WriteU32 0xE0042008, 0x00001000` → GDB 读回 `*(unsigned int*)0xE0042008` 打印 → `monitor go`。预期读回 0x00001000。
- 脚本 B（负对照）：同头部 → halt → 先 monitor 写 0x00001000 → 打印 pre → 尝试 GDB 级写 `set *(unsigned int*)0xE0042008 = 0x00002000` → 打印 post → go。预期 GDB 级写被拒（错误行进日志、值不变或脚本中止），证明开关确实在挡 GDB 写路径而 monitor 直达 GDB Server 不受影响。
- 验不过就换落点（例如改由 JLink Commander 会话设置该位再进入 GDB），不硬上正式轮。
- 注：DHCSR（0xE000EDF0）在 R18 轮已由 GDB `*(unsigned int*)` 读出成功，PPB 读路径无障碍；apb1_frz 同域。

## 8. 冒烟必验链路（任务 6 清单）

gate-pre 三遍 → flash 决策分支 → （注入轮）loadbin/verifybin + gate-post 三遍 → 最终 reset（reset plan 的 PC/VTOR/CFSR/SD_IsReady/owner 证据解析）→ binding 子进程（identity 441 chunk + 4 spot、precall、受控 PATCH/REPORT 调用、precheck ELIGIBLE、capture telnet payload==pending、postcheck RdOff 前移）→ manifest 封存 + `verify_manifest` 复算。
已知未证实风险（冒烟正是为暴露它们）：JLinkGDBServerCL 的 RTT telnet 在无客户端连接时是否自动排空 Up0 环（若排空，precheck 可能 EMPTY 或 capture payload≠pending）；capture 静默期检查对 server 行为的假设。任何一环失败即停下分析，不带缺陷进正式根。

## 9. 边界遵守

- 不改固件：被测镜像权威身份 600744 B / SHA-256 `A2D3083B...D58E00` 必须不变；不在固件里调 `debug_apb1_periph_mode_set`。
- `S_HALT=1` 闸门语义不动；修复只是让前置条件成立。
- wdt_pause 断电即失；每个 halt 会话（每个生成 GDB 脚本）自己设置；不假设跨会话存活。
- R14（20260828-12）/R15（20260828-13）/R16（20260829-14）/R17（20260829-15）/R18（p2-6-r18-audit-tmp）证据根与生产源码只读。
- 禁止 terminate/kill/taskkill；全部产物落项目内（TEMP/APPDATA 重定向至根内 tmp/）。
- 不 commit/push；不自验收；完成后回写看板 §10。
