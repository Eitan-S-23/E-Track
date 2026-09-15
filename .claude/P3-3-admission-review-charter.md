# P3-3 独立准入复核章程（2026-09-13）

> 本文件是 P3-3-EXEC-AUTH-20260913 集中执行授权第一节所指「独立准入
> 复核」的执行章程。复核会话**未参与任何 P3-3 实现工作**，以本章程为
> 唯一任务输入，独立核对实际提交、产物、设备、端点和操作单。

## 0. 你的身份与立场

- 你是**独立准入复核者**，不是实现者，也不是验收者。你没有参与 P3-3
  的任何编码、制包、服务实现或文档撰写。你的价值在于不带实现方偏见
  地重核证据。
- **不采信任何自述**：实现会话在文档/看板中写的「PASS」「已验证」
  一律视为待核主张。你要么亲自重跑可重跑的验证，要么核对原始留证
  （日志、哈希、CI 记录），要么把无法复核的主张明确列为
  EVIDENCE_GAP（这不必然是 BLOCK，按性质判断）。
- 复核通过 ≠ 验收通过。本次复核只解锁：REC0-REC7 设备恢复执行与
  Quick Tunnel 启动+受验 APK 构建两个阶段；合同冻结与 NOT_RUN 前检
  由非实现会话另行办理。

## 1. 工作目录与环境

- 活动 worktree（唯一工作目录，所有读操作在此进行）：
  `D:\github\my\E-Track\.cache\worktrees\p3-3-admission`
  分支 `dev/flutter/apk/p3-3-admission`，远端 `Eitan-S-23/E-Track`。
- bash 路径用正斜杠；Python 输出统一加 `PYTHONIOENCODING=utf-8`。
- 可用只读命令：git（log/show/diff/status/rev-parse 等）、
  sha256sum/python hashlib、`gh run view/list`（只读查询 CI）、
  `python Tools/acceptance/validate_bundle.py`。
- 看板 `PLAN-OTA-EXEC.md` 约 490KB，用精确 grep/锚点分段读，不要整读。
- PowerShell 仅在必须运行 .ps1 时使用 `powershell.exe -NoProfile
  -ExecutionPolicy Bypass -Command "& '...'"` 形式；其启动缓存写入
  是既知宿主行为，不要清理。

## 2. 复核对象与证据指针（逐项核对）

### A. 实际提交

- 提交 `0087d17`（feat: P3-3 集中执行授权落地，10 文件 +1377/-194）
  与 `a9db139`（docs: 操作单 P3 口径修正，1 文件 +3/-1）。
  用 `git show --stat` 与 `git show <sha> -- <file>` 核对：
  - `app/bluetooth_flutter_Trace/android/app/build.gradle.kts`：
    顶层 `TRACE_RELEASE_APP_ID_SUFFIX` 校验块（默认空=生产包名不变；
    非空必须匹配 `^\.[A-Za-z][A-Za-z0-9_]*$`，否则 gradle 配置期
    fail-closed）；debug/release 双 buildType suffix 块；release 侧
    applicationIdSuffix 应用。
  - `.github/workflows/build.yml`：dispatch 输入
    `release_application_id_suffix` → step env
    `TRACE_RELEASE_APP_ID_SUFFIX` 贯通；bash 侧同正则校验。
  - 双侧正则是否一致（bash 与 Kotlin 同一形态）。
- CI 证据：`gh run view 34754918841`（0087d17）与
  `gh run view 34755121482`（a9db139）——两 run 的
  windows-2022 与 ubuntu-latest job conclusion 须均为 success。
  34755121482 在章程撰写时仍在跑（纯文档提交），你核实时若未完成
  先做其他项，最终结论前再查一次终态。

### B. 产物（实物哈希逐个重算）

- toy/真包 ETU 与镜像（`.cache/p3-3-assets/`）：
  - `e-track-at32f435-v3.2.1-full.etu` 284092B，
    SHA-256 `fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2`；
  - `e-track-at32f435-v3.2.2-full.etu` 284112B，
    SHA-256 `0a2eb26a481d8c462b5316a67a151c8241de354d00797fa22f11e77056538ce5`；
  - toy 镜像 raw（`toy-3.2.1-pre-finalize.bin`，602984B）
    SHA-256 `43ee943a185f63d70284c7c5a9992d677a9bf8c518dacd2e63df8ec7e5809b55`；
    真包镜像 raw（`real-3.2.2-pre-finalize.bin`）
    SHA-256 `c958221392fade8b40520df2d7fd4278632d64bcdd8261b0ac7536c6468a7f39`。
- 受控服务四件套（`Tools/ota/p3-3-service/`）：
  `service.py` 38737B `f71012de…`、`service_config.json` 2589B
  `2facafa6…`、`selftest.py` 45777B `b96d4e2f…`、
  `tls_hostcheck.py` 14937B `f9202b6b…`（完整哈希以合同
  EXT-HTTP-TEST-SERVICE 描述为准，与实物重算比对）。
- `service_config.json` 内 toy/real fixture 四元组与合同
  EXT-TOY-BOOTABLE / EXT-REAL-ETU 的绑定值交叉核对。
- 恢复 Boot 构建产物（`.cache/p3-3-recovery-boot/boot/`）：
  - `X-Track-Boot.hex` 52727B，SHA-256
    `409d4f1690b80f5e5b3ce8169119bdd462dea87a60822c104693c5e8c216cbb4`；
  - `X-Track-Boot.bin` 18720B。
  配套构建验证记录：`docs/ota-exec-notes/P3-3-recovery-boot-build-2026-09-13.md`
  （13/13 PASS 主张）与 `.cache/p3-3-recovery-boot/cmd-verify.log`。
- 可选重验（host-only、不碰设备）：读完 `Tools/ota/p3-3-service/selftest.py`
  确认其只在本机回环与 worktree `.cache/` 内工作后，可重跑一次核对
  16 项全 PASS 主张；若其写入 worktree 外或需要外部网络则跳过并记录。
  重跑后确认无残留 python/service 进程。
- 恢复命令离线验证：`Tools/jlink/test-p1-6-recovery-cmd.ps1` 与
  `Tools/jlink/test-p1-6-matrix.ps1`——**先读脚本**确认其为离线/受管
  runner（不调用真实 JLink 硬件）才可重跑；若有任何硬件子进程路径
  则不跑，只核对 `.cache/p3-3-recovery-cmd-verify-final.log` 留证。

### C. 设备（只核证据链，不碰设备）

- 目标板身份：`docs/ota-exec-notes/P3-3-t1a-jlink-board-identification-2026-09-12.md`
  ——AT32F435RGT7、板上 App 3.2.0(30200)、Boot=磁盘 X-Track-Boot.bin 原版。
- BCB 阻断态证据：`docs/ota-exec-notes/P3-3-bcb-blocker-clarification-2026-09-13.md`
  ——CONFIRMED cur_vcode=20801 与 App 30200 不一致是实机前置阻断，
  恢复方案的存在理由。核对操作单 §1「板上 BCB 起点」的口径与该证据一致。
- 测试手机身份：B1-M r1 identity（序列号 `10ADA4197U001CK`、
  vivo V2312A、Android 13、既有安装 `com.wen.gaia.gaia` 1.0.60(86)）。
  在 B1-M 文档（`P3-3-b1m-*.md` 或其引用的 identity 留证）中找到
  原始记录并核对操作单引用无失真。
- 你不得连接、烧录、复位任何设备；不得运行 JLink.exe/JLinkRTTLogger/
  adb。身份核对全部基于已落盘证据。

### D. 端点（Quick Tunnel 路线方案核对）

- 服务文档：`docs/ota-exec-notes/P3-3-v2-service-plan-and-selftest-2026-09-13.md`
  （第五轮修订）。核对 §5（Quick Tunnel）与 §6（D1-D5）：
  - 只暴露 latest/download 端点与两份绑定 ETU，不暴露其他本机服务/
    文件/日志/管理接口；
  - CF 边缘终止 TLS（公共可信证书、App 校验不放宽），隧道到本机走
    127.0.0.1 HTTP，不开放局域网监听；
  - 不用 Cloudflare 账号、不读旧 token、无 adb reverse；
  - 8 小时窗口自 D1 起计，到期或本轮结束即关；
  - D4 toy→真包切换只重启 service.py，隧道进程与公网地址不变；
  - D5 清理为判据（按 PID 关隧道+停服务+日志归档+端口无残留验证）；
  - 执行顺序：隧道先行取地址 → 宿主端到端检查（§5.2 四项）→ 注入
    唯一一次受验 APK 构建 → 地址绑定进合同。
- 上述每项对照授权第二节（见 §3 授权记录）逐条核对无偏差。

### E. 操作单（第五版）

- `docs/ota-exec-notes/P3-3-device-operation-sheet-2026-09-13.md`。
  核对：
  - 前置链 P1/P2/P0/P3 与授权第五节「安全准备、HTTPS 检查和 APK 构建
    可独立推进，不必先操作设备」一致；
  - O1-O5 时长/次数：5/10/30/30/5 分钟、各一次；包含项（BLE 权限、
    候选/备份槽、App Flash、BCB 更新、固件重启）与排除项（J-Link 直刷
    App、注错）与授权第四节一致；
  - build-only 同一笔 1 次额度、publish_release=false、
    replace_existing_release=false；
  - 并存 applicationId `com.wen.gaia.gaia.p33acceptance`；既有安装
    不卸载、不清数据；
  - 恢复额度：命令会话恰好 10、RTT logger 2（各 ≤120s）、主动复位 6、
    身份/RTT 签名核对会话 ≤2；REC6 与成功路径共用额度；计划外 nRESET
    单步 ≥2 或全程累计 >2 即停；
  - 失败处理：留证停报、不盲重试、不互借 A1/B1-M 额度；
  - P3 冻结办理权：非实现会话办理（授权第一节），操作单已修正口径。

### F. 恢复方案 v5 与执行脚本

- `docs/ota-exec-notes/P3-3-bcb-recovery-plan-2026-09-13-v5.md`：
  - S1a 同一 J-Link 连接内完成 Boot 全区备份→烧录测试 Boot→RAM magic
    失效+读回（测试 Boot 首启前完成失效）→S1b 复位①；
  - BCB 双块 128B 原始字节强制留档不裁剪；
  - FR4 与 S5 互斥恰好其一，复位恒 6、命令会话恒 10（核 §7 额度总账
    算术自洽）；
  - §5 完成判据四条全满足前 C-TOY-LOOP/C-REAL-LOOP 不得执行；
  - Flash 边界 0x08000000-0x08004FFF、RAM 控制块
    0x20057E00-0x20057FFF、EEPROM 0x00-0x7F 经既有 CLEAR_BCB。
- `Tools/jlink/p3-3-recovery-execute.ps1`：ValidateSet
  S1A/S1B/S2/S3/S4/S5/S6 与 v5 方案一致；每 Phase fail-closed 断言 +
  result.json 留证；Assert-P33PriorPhase 前置链检查；无一键 ALL 模式；
  纯 ASCII（PS 5.1 GBK 陷阱）。
- 你不运行该执行脚本（它操作真实硬件）；静态审读 + 与 v5 文档比对。

### G. 合同与矩阵 v3

- `docs/acceptance-contracts/P3-3-v3.contract.json` 与
  `P3-3-v3.evidence-matrix.json`：
  - 亲自重跑：
    `PYTHONIOENCODING=utf-8 python Tools/acceptance/validate_bundle.py --contract docs/acceptance-contracts/P3-3-v3.contract.json --matrix docs/acceptance-contracts/P3-3-v3.evidence-matrix.json --repo-root . --allow-draft`
    期望 `VALIDATION=PASS`（串行跑，你是唯一实例）。
  - 顶层：contract_id=P3-3-v3、version=3、task_id=P3-3、
    parent_contract_sha256 必须等于 v2 合同文件实测 SHA-256
    （自己重算 v2 文件哈希比对，期望
    `5940da0606816fcc90cedd7dd062e664196863d76b9807553856da7c8ba8846a`）；
    status=DRAFT 且 freeze_*/profile_config_blob/approved_by 为占位
    零值（冻结前正确形态）。
  - 判据集合与 v2 相同五项；C-TOY-LOOP/C-REAL-LOOP state_chain 六态
    列表完整；
  - CMD-RELEASE-BUILD 含 `release_application_id_suffix=.p33acceptance`
    注入与唯一一笔 build-only 额度口径；CMD-APK-INSTALL 含并存安装
    策略与 ENV_BLOCKED 停点；EXT-HTTP-TEST-SERVICE 绑 Quick Tunnel 且
    fingerprint 标 PENDING（执行时回填，不预先写死随机 URL）；
    EXT-BOARD-STATE 为 v5 口径。
  - 矩阵 notes 与当前状态无矛盾（如 dev-checks 必须在 freeze_commit
    重新派发、旧 run 不覆盖 suffix 机制改动的口径）。

### H. 授权一致性（总对照）

- 授权整理记录：
  `docs/ota-exec-notes/P3-3-exec-authorization-2026-09-13.md`
  （**该文件刻意未提交**，将与你的复核结论文档同批提交——这不是缺陷）。
  通读五节，将操作单/恢复方案 v5/服务文档/合同 v3 与其逐节对照：
  - 第一节：工作边界（admission worktree 内整改自测提交推送、不合并
    不推主干不 Release/tag、独立复核办理冻结）；
  - 第二节：Quick Tunnel 各红线（见 D）；
  - 第三节：恢复授权各边界与额度（见 F）；
  - 第四节：APK 与 O 序列（见 E）；
  - 第五节：执行边界与停止条件、集中问用户的五种情况、「已授权，待
    前检/执行」状态语言。
- 该文件自我声明为「整理记录非逐字转录」并带优先序条款；若你发现
  执行文档与授权记录之间、或各执行文档互相之间有实质矛盾（口径、
  额度、边界、顺序任一），逐条列出并给出你判断的正确口径依据。

## 3. 明确禁止

- 不 git commit/push/merge/checkout/reset；不修改任何既有文件。
- 不碰设备：不运行 JLink/JLinkRTTLogger/adb，不连接手机或目标板。
- 不启动 cloudflared 隧道、不对外网暴露任何端口。
- 不 dispatch 任何 GitHub workflow（gh workflow run 一律禁止；
  `gh run view/list` 只读查询允许）。
- 不删除任何文件；不进入其他 worktree 或项目外目录写入。
- 唯一允许的写操作：创建你的复核报告文件（见 §4）与 §2.B 中
  明确界定的可选重验在其自身受控范围内的输出。

## 4. 产出

写一份复核报告到：
`docs/ota-exec-notes/P3-3-admission-review-2026-09-13.md`
（这是你唯一创建/修改的文件；UTF-8；简体中文），结构：

1. 复核元信息：复核时间、复核者身份声明（未参与实现）、章程版本。
2. 逐项核对表：§2.A-H 每项 → 结论
   （PASS / CONCERN / BLOCK / EVIDENCE_GAP）+ 你亲手取得或复核的
   证据指针（命令、哈希、文件:行）。每项写你实际做了什么核对，不是
   复述文档。
3. 发现清单：所有 CONCERN/BLOCK/EVIDENCE_GAP 的具体描述、影响、
   你建议的处置（须修 / 可带条件放行 / 需用户裁定）。
4. 额度与边界核对结论：授权第三节/第四节数字与文档数字逐一对账。
5. 总结论：ADMISSION_PASS（放行 REC0-REC7 执行与 Quick Tunnel+受验
   APK 构建两阶段）或 ADMISSION_HOLD（列阻断项）。给出明确理由。
6. 是否存在需按授权第五节集中问用户的事项（五种情况之一）。

最终答复里给出总结论与发现清单摘要。
