# P3-3 独立准入复核报告 —— 2026-09-13

> **总结论：ADMISSION_PASS**（放行 REC0-REC7 设备恢复执行与 Quick Tunnel
> 启动+受验 APK 构建两阶段）。

## 1. 复核元信息

- 复核时间：2026-09-13（本 worktree 会话内完成全部核对）。
- 复核者身份声明：本复核会话**未参与 P3-3 的任何实现工作**（未参与编码、
  制包、服务实现、文档撰写、设备操作、CI 派发）。全部核对基于本报告
  第 2 节所列亲手执行的只读命令与哈希重算。
- 章程版本：`.claude/P3-3-admission-review-charter.md`（2026-09-13 版，
  226 行，全文读取后逐项执行）。
- 工作目录：`D:\github\my\E-Track\.cache\worktrees\p3-3-admission`
  （分支 `dev/flutter/apk/p3-3-admission`）。
- 复核纪律遵守声明：未运行任何 J-Link/adb/设备命令；未启动 cloudflared；
  未 dispatch 任何 workflow（仅 `gh run view` 只读查询）；未做任何 git
  写操作；未删除任何文件；本报告是本次复核创建的唯一文件。
- 本报告性质：**准入复核 ≠ 验收**。本复核只解锁章程 §0 定义的两个阶段
  （REC0-REC7 设备恢复执行、Quick Tunnel 启动+受验 APK 构建）；合同冻结
  与 NOT_RUN 前检由非实现会话另行办理。

## 2. 逐项核对表（章程 §2.A-H）

### A. 实际提交 —— PASS

亲手执行的核对与证据：

1. `git show --stat` 核对两笔提交统计：
   - `0087d17`（feat: P3-3 集中执行授权落地）：10 文件，+1377/-194，与
     章程一致。关键文件含 `app/bluetooth_flutter_Trace/android/app/build.gradle.kts`
     与 `.github/workflows/build.yml`。
   - `a9db139`（docs: 操作单 P3 口径修正）：1 文件 +3/-1
     （`P3-3-device-operation-sheet-2026-09-13.md`，P3 冻结办理权改为
     「独立准入复核通过后由非实现会话办理」）。
2. `build.gradle.kts` 全文审读（169 行）：
   - 顶层校验块（77-85 行）：`TRACE_RELEASE_APP_ID_SUFFIX` 默认空=生产
     包名不变；非空必须匹配 `^\.[A-Za-z][A-Za-z0-9_]*$`，否则 `error()`
     配置期 fail-closed（提示语示例即 `.p33acceptance`）。
   - release buildType 应用 suffix（126-131 行）：非空时
     `applicationIdSuffix = releaseApplicationIdSuffix` 并打 lifecycle 日志。
   - debug 侧既有 `TRACE_DEV_APP_ID_SUFFIX` 机制（62-70、143-150 行）独立
     存在，互不干扰；生产默认包名 `com.wen.gaia.gaia`（103 行）不受影响。
3. `.github/workflows/build.yml` diff 核对：dispatch 输入
   `release_application_id_suffix` → step env
   `TRACE_RELEASE_APP_ID_SUFFIX: ${{ inputs.release_application_id_suffix || '' }}`
   贯通；bash 侧 `[[ ... =~ ^\.[A-Za-z][A-Za-z0-9_]*$ ]]` 校验，与 Kotlin
   正则同一形态（双层校验一致）。
4. CI 证据（`gh run view` 只读查询，复核会话内前后查过两次，最终结论前
   终态复查）：
   - run `34754918841`：completed/success，headSha `0087d175…`，
     windows-2022 与 ubuntu-latest 两 job 均 success。
   - run `34755121482`：completed/success，headSha `a9db1390…`，
     双宿主 job 均 success。
   - 两 run 的 headSha 与被核提交精确对应。

### B. 产物（实物哈希逐个重算） —— PASS（含章程 1 处笔误澄清）

全部用 `sha256sum` / Python hashlib 亲算，比对合同与章程期望值：

| 文件（`.cache/p3-3-assets/` 等） | 实测 SHA-256 | 比对 |
| --- | --- | --- |
| e-track-at32f435-v3.2.1-full.etu（284,092B） | `fc4ae5a9fd1a9c131b548188a7bb66643703cdea7b7007f66c8a71e304d479a2` | 与合同 EXT-TOY-BOOTABLE、章程一致 |
| e-track-at32f435-v3.2.2-full.etu（284,112B） | `0a2eb26a481d8c462b5316a67a151c8241de354d00797fa22f11e77056538ce5` | 与合同 EXT-REAL-ETU、章程一致 |
| toy-3.2.1-pre-finalize.bin（602,984B） | `7328c1b15feff7214378065ca3e7d556ac803b59ebed7029a892d64f15e2153f` | 与合同 pre-finalize 一致（见下方笔误澄清） |
| real-3.2.2-pre-finalize.bin | `7328c1b1…`（与 toy 相同） | 与合同一致（共享生产镜像） |
| toy-3.2.1-30201-final.bin | `43ee943a185f63d70284c7c5a9992d677a9bf8c518dacd2e63df8ec7e5809b55` | 与合同最终镜像 raw 一致 |
| real-3.2.2-30202-final.bin | `c958221392fade8b40520df2d7fd4278632d64bcdd8261b0ac7536c6468a7f39` | 与合同最终镜像 raw 一致 |
| Tools/ota/p3-3-service/service.py（38,737B） | `f71012de119811863d2274fd674a702c69a512f18ea73e3188be2233130ba009` | 与服务文档 §1/合同 EXT-HTTP-TEST-SERVICE 一致 |
| service_config.json（2,589B） | `2facafa60fb4c65944c55168d46a2fbf2b2de7ea05d46e47beffa850cc7ce39c` | 同上 |
| selftest.py（45,777B） | `b96d4e2f05c84c3401c1dff14ee9c0f6e5dc7ee0a076e272180d2f4d4aa202b4` | 同上 |
| tls_hostcheck.py（14,937B） | `f9202b6b47f50526e75710fd2b8048e87b24bb94ab07f82b88716a761821da6c` | 同上 |
| .cache/p3-3-recovery-boot/boot/X-Track-Boot.hex（52,727B） | `409d4f1690b80f5e5b3ce8169119bdd462dea87a60822c104693c5e8c216cbb4` | 与 Boot 构建记录、执行脚本常量一致 |
| X-Track-Boot.bin（18,720B） | `abd042db09b27198d2c52e9ee4e8c15d0c524bd28cb55023dd2aecac9098ce55` | 同上 |

- **章程笔误澄清（发现 B-1，非产物缺陷）**：章程 §2.B 把
  `43ee943a…`/`c9582213…` 标注为两个 pre-finalize 文件的期望哈希；实测
  两个 pre-finalize 文件哈希均为 `7328c1b1…`（相同）。深挖合同 v3
  EXT-TOY-BOOTABLE/EXT-REAL-ETU 后确认：pre-finalize 是**共享同一合格
  生产镜像**（`7328c1b1…`，用户裁定路线）；`43ee943a…`/`c9582213…` 实为
  **最终镜像 raw**（即 `*-3020x-final.bin`）的哈希。即章程撰写时把
  「镜像 raw」的期望值误挂到 pre-finalize 文件名上；产物本身与合同
  四元组（pre-finalize → final raw → fw_header 双零摘要 → ETU 包）完全
  一致。fw_header 双零摘要 `a7ae0387…`（toy）/`85d19304…`（real）亦在
  合同 description 内登记（本轮未重算 header 双零摘要，其输入文件
  `*-final.bin` 已实测绑定）。
- `service_config.json` 内 toy/real fixture 四元组与合同 EXT 绑定值逐项
  交叉核对一致（targetImageSha256、ETU sha、fileName、sizeBytes）。
- **selftest.py 重跑**（章程 §2.B 可选重验）：先审读确认其只绑
  `('127.0.0.1', 0)`、纯 Python 标准库、无外部网络、输出限定 worktree
  `.cache/` 后实际重跑一次：**16/16 PASS、退出码 0**，重跑后用
  `tasklist` 精确匹配确认无残留 python/service 进程。
- **恢复命令离线验证**：`test-p1-6-recovery-cmd.ps1` 设计为 runDir 已
  存在即 throw（fail-closed 防覆盖），`.cache/p3-3-recovery-boot/cmd-verify/`
  已存在故不可重跑；按章程备选路径核对留证
  `.cache/p3-3-recovery-cmd-verify-final.log`：**24/24 PASS**（T11 的
  traceback 为文档声明的预期行为；T17 行 `sha16=ABD042DB09B27198` 与
  Boot bin 实测哈希前缀吻合）。`test-p1-6-matrix.ps1` 审读确认默认只做
  READY 检查即退出、`-ExecuteBoard` 才触碰真实硬件（本次复核未用该开关）。

### C. 设备（只核证据链，不碰设备） —— PASS + 1 项 EVIDENCE_GAP

- 目标板身份：`P3-3-t1a-jlink-board-identification-2026-09-12.md` 全文
  审读——AT32F435RGT7；板上 App 3.2.0(30200) 的 fw_header 逐字段与双零
  SHA 重算记录自洽；Boot 与磁盘 `X-Track-Boot.bin` 逐字节一致；BCB
  cur_vcode=20801 登记在案；§7 证据产物哈希清单（boot16k.bin
  `882d18fb…`、app16k.bin `a2f4133c…`、rtt-terminal.log `320e698d…`）。
- BCB 阻断态：`P3-3-bcb-blocker-clarification-2026-09-13.md` 全文审读
  ——20801≠30200 确证；代码证据链（`ota_backup.c:385-391` 一致性检查
  拒绝 STAGED 提交）；「选更高版本绕不过」论证（385 在 410 之前先失败）。
  操作单 §1「板上 BCB 起点」口径（恢复前 CONFIRMED cur_vcode=20801 阻断态
  → 恢复后 30200 合法起点）与该证据一致。
- 测试手机身份：`P3-3-b1m-minimal-mechanism-2026-09-11.md` 找到原始记录
  （40-42 行）：序列号 `10ADA4197U001CK`、vivo V2312A、Android 13
  （SDK 33）、既有安装 `com.wen.gaia.gaia` 1.0.60(86) release、APK
  SHA-256 `428a5d3a…`（45,951,912B）。操作单 §1 引用逐项核对无失真。
- **EVIDENCE_GAP（发现 C-1）**：t1a 轮的原始 J-Link 产物
  （boot16k.bin/app16k.bin/rtt-terminal.log）不在本 worktree
  （`.cache/p3-3-t1a-step1-r1/jlink/` 不存在，证据在 t1a 执行环境的被
  忽略目录），本复核无法对其 §7 登记哈希做实物重算。缓解：板识别文档
  与 BCB 澄清文档对同一批哈希的两次引用一致，且 BCB 阻断结论另有
  `ota_backup.c` 代码证据独立支撑。**性质判断：非阻断**——该缺口不
  影响恢复方案的前提成立性，恢复执行（REC0 备份/S2 SNAPSHOT）本身会
  重新实测板上状态并与这些登记值对照，若实测不符会 fail-closed 停机。
- 本复核全程未连接、烧录、复位任何设备；未运行 JLink/JLinkRTTLogger/adb。

### D. 端点（Quick Tunnel 路线方案） —— PASS

`P3-3-v2-service-plan-and-selftest-2026-09-13.md`（第五轮修订）§5/§6
逐项核对，七项要素全部与章程清单及授权第二节一致：

1. 只暴露 latest/download 端点与两份绑定 ETU；实现无管理端口，
   127.0.0.1 绑定保证隧道只能到达本服务（§5.1 暴露范围 + §5.2 负例 4）。
2. CF 边缘终止 TLS（公共可信证书、App 校验不放宽），隧道到本机走
   127.0.0.1 HTTP（D1 形态明示无 `--tls-cert`），不开放局域网监听。
3. 不用 Cloudflare 账号、不读旧 token（含与云端写入单 §9 的边界切割）；
   无 adb reverse（§5.1/§6 双处明示）。
4. 8 小时窗口自 D1 起计，到期或本轮结束即关（§5.1 窗口 + §6）。
5. D4 toy→真包切换只重启 service.py（`--active-release real-30202`），
   隧道进程与公网地址不变；地址改变或隧道退出即暂停并申报。
6. D5 清理为判据：按 PID 终止两进程 → 日志归档 → 无残留验证（进程/
   端口/日志齐套），残留记 HARNESS_FAIL。
7. 执行顺序：隧道先行取地址 → 宿主端到端检查（§5.2 四项：latest 十参数
   200 / 整包下载 SHA 一致 / CF 边缘证书默认信任库直接校验 / 路径外
   负例不放大暴露）→ 注入唯一一次受验 APK 构建 → 地址绑定进合同
   （fingerprint 执行时回填）。
- cloudflared 二进制获取收敛 worktree `.cache/p3-3-cloudflared/`、SHA
  登记、不全局安装（§5.1 末条 + §6 缓存收敛注记）——与授权第五节路径
  预检要求一致。
- 替代路线（§5.3 A/B）仅 Quick Tunnel 确实不可用时集中申报，路线 B 的
   申报前置（浏览器鉴权→核对 account ID/资源归属/旧 token 排除）与
  授权第二节末段一致。

### E. 操作单（第五版） —— PASS

`P3-3-device-operation-sheet-2026-09-13.md` 全文（241 行）逐项核对：

- 前置链 P1/P2/P0/P3（§2）：P1 服务准入+隧道宿主检查、P2 受验 APK 身份
  确定、P0 BCB 恢复完成、P3 合同冻结+NOT_RUN 前检；顺序说明与授权第五
  节「安全准备、HTTPS 检查和 APK 构建可独立推进，不必先操作设备」
  一致；8h 窗口时序约束明确。
- O1-O5 时长/次数（§4/§7 表）：5/10/30/30/5 分钟、各 1 次——与授权
  第四节逐字一致。
- 包含项（BLE 权限、目标板连接、候选/备份槽、App Flash、BCB 更新、
  固件重启）与排除项（J-Link 直刷 App、注错）与授权第四节一致（§4
  授权口径 + O3「BCB 授权口径」行 + §6）。
- build-only 同一笔 1 次额度（不追加）、`publish_release=false`、
  `replace_existing_release=false`、Pages/Release 不执行（§7）。
- 并存 applicationId `com.wen.gaia.gaia.p33acceptance`；既有安装不卸载、
  不清数据（O1 安装策略 + §6「任何情况下不得以卸载或清数据解决签名
  冲突」）。
- 恢复额度（§3）：命令会话恰好 10、RTT logger 2（各 ≤120s）、主动复位
  6、身份/RTT 签名核对会话 ≤2；REC6 与成功路径共用额度；计划外 nRESET
  单步 ≥2 或全程累计 >2 即停——与 v5 §7/授权第三节一致。
- 失败处理：留证停报、不盲重试、不互借 A1/B1-M 额度（O2-O4 + §6）。
- P3 冻结办理权：非实现会话办理（a9db139 修正后口径，§2 P3 注记）
  ——与授权第一节一致。
- J-Link 不并入 O 序列（§5 独立授权项）；手机首次网络观测留在 O2。

### F. 恢复方案 v5 与执行脚本 —— PASS

`P3-3-bcb-recovery-plan-2026-09-13-v5.md`（219 行）全文 +
`Tools/jlink/p3-3-recovery-execute.ps1`（509 行）逐行静态审读（按章程
§2.F 不运行该脚本）：

文档侧：
- §2.3 S1a/S1b 失效时序前移：S1a 同一 J-Link 连接内（h → savebin 备份 →
  loadfile 测试 Boot → RAM magic 失效+读回 → qc，全程 halt、
  -ExitOnError 1）完成备份/烧录/失效，S1b 才复位①——满足授权第三节
  「首次启用测试 Boot 前，必须在其第一次启动执行命令之前完成实际 RAM
  magic 失效及验证」。
- BCB 双块 128B 原始字节强制留档不裁剪（S2 落盘+SHA）。
- §3 操作序列表会话/复位算术自洽：1+1+2+2+1+2+1=10 会话、复位①-⑥共 6。
- §5 完成判据四条（生产 Boot 全区恢复+核验、App 身份未变 30200、BCB 与
  App 一致 cur_vcode=30200、生产 App RTT 新鲜自报）；判据全满足前
  C-TOY-LOOP/C-REAL-LOOP 不得执行（合同 CMD-TOY-LOOP 前置同口径）。
- §6 FR4 备用会话与 S5 互斥恰好其一（复位恒 6、会话恒 10）；REC6 失败
  收尾共用额度；§7 额度总账与授权第三节逐项对齐。
- Flash 边界 0x08000000-0x08004FFF、RAM 控制块 0x20057E00-0x20057FFF、
  EEPROM 0x00-0x7F 经既有 CLEAR_BCB（不授权 App 烧录/QSPI/注错/其他
  opcode）。

脚本侧（`p3-3-recovery-execute.ps1`）：
- `ValidateSet('S1A','S1B','S2','S3','S4','S5','S6')` 与 v5 一致；switch
  仅接受单 Phase，**无一键 ALL 模式**；纯 ASCII（实测 non_ascii_count=0，
  规避 PS 5.1 GBK 陷阱）；`Set-StrictMode` + `$ErrorActionPreference='Stop'`。
- `Assert-P33PriorPhase` 前置链：S1B←S1A、S2←S1B、S3←S2、S4←S3、
  S5←S4（AcceptResults 扩展含 `'FR4_MISSING_LINE'`）、S6←S5；每 Phase
  写 `result.json` 留证。
- 常量绑定与实测一致：测试 Boot hex SHA `409d4f16…`、52727/18720/14724
  字节、失效 magic `0x0800491F`、基线 20801、终态 30200。
- S1a 四组主机侧断言全部实现：备份锚点（生产 Boot 前缀 14724B 与生产
  bin 比对）、烧录读回=测试 bin 逐字节+尾部 0xFF、失效读回断言、独立
  HEX 範囲解析的扇区顶边界核对。**比 v5 §2.3 文字更强**：脚本额外做了
  「烧录后读回与测试 bin 逐字节核验」与「erase 边界以读回字节断言为准、
  erase 日志原文另留 result.json 供独立复核」——方向为增强核验，无害。
- S2：基线 cur_vcode=20801 断言 + BCB raw 128B×2 落盘+SHA；S3：active=
  NONE、双块全 0xFF 断言；S5：终态断言（cur_vcode=30200、seq=0、
  app_result=VALID、app_vcode=30200、app_sha256）+ FR4 fallback 标志
  （`invoked_as_fr4_fallback`）；S6：从 S1A 备份全区恢复
  （`Invoke-P16BootRegionRestore` 含 loadbin+verifybin+全区读回 SHA 全等，
  尺寸守卫先于 J-Link 调用）+ 复位⑥ + RTT 终证。
- 配套 Boot 构建记录 `P3-3-recovery-boot-build-2026-09-13.md` 产物身份
  表与实测一致（13/13 为旧版脚本记录、24/24 为新版留证，两份日志均在）。

### G. 合同与矩阵 v3 —— PASS

亲手执行的核对：

1. **validate_bundle.py 串行重跑**（本复核是唯一实例）：
   `PYTHONIOENCODING=utf-8 python Tools/acceptance/validate_bundle.py
   --contract docs/acceptance-contracts/P3-3-v3.contract.json --matrix
   docs/acceptance-contracts/P3-3-v3.evidence-matrix.json --repo-root .
   --allow-draft`
   → **`VALIDATION=PASS contract=P3-3-v3 round=20260913-DRAFT-V3
   overall=NOT_RUN`，退出码 0**。
2. **v2 哈希亲算**：`sha256sum docs/acceptance-contracts/P3-3-v2.contract.json`
   = `5940da0606816fcc90cedd7dd062e664196863d76b9807553856da7c8ba8846a`，
   与 v3 顶层 `parent_contract_sha256` **完全一致**。
3. 顶层字段逐项：contract_id=`P3-3-v3`、version=3、task_id=`P3-3`、
   status=`DRAFT`、freeze_commit/freeze_tree/profile_config_blob 全零
   占位、approved_by/approved_at 为空——冻结前正确形态。
4. 判据集合与 v2 完全相同五项：C-DEV-CHECKS、C-RELEASE-BUILD、
   C-APK-INSTALL、C-TOY-LOOP、C-REAL-LOOP（实测 v2/v3 id 列表相等）。
5. C-TOY-LOOP/C-REAL-LOOP `gate.expected` 六态完整且两判据一致：
   ota_session_info_ok → ota_package_verified →
   ota_transfer_durable_complete → ota_ack_end_ok → device_reboot →
   get_info_target_version_and_raw_sha_match；前置含「EXT-BOARD-STATE
   已按批准恢复方案 v5（S1a-S6 / REC0-REC7）执行完毕且 §5 完成判据四条
   全部满足」与 Quick Tunnel D1-D5/D2 检查/D4 切换口径。
6. CMD-RELEASE-BUILD 命令含
   `-f release_application_id_suffix=.p33acceptance`、
   `-f publish_release=false`、`-f replace_existing_release=false`、
   `-f firmware_latest_url=https://<quicktunnel>…`；C-RELEASE-BUILD
   description 明确「本构建消耗 P3-3-EXEC-AUTH-20260913 第四节保留的
   现有同一笔 build-only 1 次额度」+ 并存包名实测要求 + 签名类型如实
   绑定口径。
7. C-APK-INSTALL：并存安装策略（既有安装不卸载不清数据）、双侧
   apksigner 指纹实测、**ENV_BLOCKED 停点**（包名注入失效 → 停在安装前，
   不改装非受验 APK）、BLE 权限授予（授权第四节）、「参与传输的必须是
   同一 APK（与受控服务 fixture 同源）」。
8. EXT-HTTP-TEST-SERVICE：绑定 Quick Tunnel（description 含 Cloudflare
   Quick Tunnel 公网入口与 D1-D5）；fingerprint=`PENDING: …通过后回填`
   （不预先写死随机 URL）；四件套哈希与 B 项实测一致。
9. EXT-BOARD-STATE：v5 口径（S1a 同连接时序、128B 留档「无任何审批
   路径可裁剪」、FR4 备用会话互斥、复位恒 6/会话恒 10、REC6 共用额度、
   S6 全区恢复）；fingerprint=PENDING。
10. EXT-TOY-BOOTABLE/EXT-REAL-ETU 四元组哈希（7328c1b1 共享 pre-finalize
    → 43ee943a/c9582213 final raw → a7ae0387/85d19304 header 双零 →
    fc4ae5a9/0a2eb26a ETU）与实物及 service_config.json 全部一致。
11. 矩阵（P3-3-v3.evidence-matrix.json）：schema etrack-evidence-matrix-v2、
    contract_sha256 全零占位、overall_result=NOT_RUN、五判据
    NOT_OBSERVED；notes 把旧 CI run（34730007317/34738585857/
    34730618341）明确标注为「参考事实（非本矩阵证据）」；C-DEV-CHECKS
    判据要求「freeze_commit 上 flutter-dev-checks 双宿主……通过，不以
    派发退出码代替」——即 dev-checks 必须在冻结提交上重新派发，旧 run
    不覆盖 suffix 机制改动。与当前状态无矛盾。

### H. 授权一致性（总对照） —— PASS

通读 `P3-3-exec-authorization-2026-09-13.md` 五节（整理记录，非逐字
转录，带优先序条款），将操作单/恢复方案 v5/服务文档/合同 v3 与其逐节
对照：

- **第一节**：admission worktree 内整改自测提交推送、不合并不推主干不
  Release/tag（实际提交 A 项与操作单 §7/合同 CMD 开关一致）；独立复核
  办理冻结（操作单 §2 P3 已修正口径）；「已授权，待前检/执行」状态
  语言在操作单/服务文档/矩阵 notes 统一使用。
- **第二节**：Quick Tunnel 各红线逐条与服务文档 §5/§6、操作单 §2 一致
  （见 D 项七要素）；替代路线申报前置一致。
- **第三节**：恢复授权各边界与额度与 v5/操作单 §3/合同 EXT-BOARD-STATE
  一致（见 F 项与第 4 节额度对账）；「FR4 与 REC5 替代关系只消费一次，
  先消除文档矛盾」——v5 已消除（FR4 备用会话替代 S5，恒 6/恒 10）。
- **第四节**：APK 与 O 序列与操作单 §1/§4/§7、合同 CMD-RELEASE-BUILD/
  CMD-APK-INSTALL 一致（见 E/G 项）；O3 双值匹配后才激活真包进 O4。
- **第五节**：执行边界与停止条件、路径预检收敛 worktree、五种集中问
  用户情况（见第 6 节）、「已授权，待前检/执行」语言、交付一次完整
  结果——均落实。
- **唯一口径差异（非矛盾）**：授权第三节写「正常路径**最多** 10 个
  J-Link 命令会话」，v5/操作单写「命令会话**恰好** 10」。执行文档把
  计划形态定为满额恰好 10（v5 §3 表算术与脚本实现均为 10，FR4 分支
  不增加），未超出授权上限；「恰好」是「最多」的计划满额特化，无
  实质矛盾。
- 各执行文档互相之间未发现口径、额度、边界、顺序上的实质矛盾。

## 3. 发现清单

| # | 级别 | 描述 | 影响 | 处置建议 |
| --- | --- | --- | --- | --- |
| B-1 | 澄清（非缺陷） | 章程 §2.B 把最终镜像 raw 哈希 `43ee943a…`/`c9582213…` 误标为两个 pre-finalize 文件的期望哈希；实测 pre-finalize 两文件均为 `7328c1b1…`（共享生产镜像，用户裁定路线），`43ee943a…`/`c9582213…` 是 `*-3020x-final.bin`（最终镜像 raw）的哈希，与合同四元组完全一致 | 无——产物与合同一致，仅章程文本笔误 | 无须修产物；建议后续修订章程时更正该行表述（本报告已澄清） |
| C-1 | EVIDENCE_GAP | t1a 轮原始 J-Link 产物（boot16k.bin/app16k.bin/rtt-terminal.log）不在本 worktree，无法对板识别文档 §7 登记哈希做实物重算 | 低——两份文档对同一批哈希的引用一致；BCB 阻断结论另有 ota_backup.c 代码证据独立支撑；恢复执行时 REC0/S2 会重新实测板上状态，实测不符即 fail-closed 停机 | 可带条件放行；恢复执行阶段以 S1A 备份/S2 SNAPSHOT 的实测值为准 |
| F-1 | 说明（非缺陷） | 执行脚本 S1a 比 v5 §2.3 文字多两组断言（烧录读回与测试 bin 逐字节核验+尾部 0xFF；erase 边界以读回字节断言为准、erase 日志原文另留档） | 无——断言强于文档，方向为增强核验 | 无须处置；报告中如实登记 |

无 BLOCK、无 CONCERN。

## 4. 额度与边界核对结论（授权第三/四节 vs 文档数字对账）

| 项 | 授权口径 | 文档/脚本口径 | 对账 |
| --- | --- | --- | --- |
| J-Link 命令会话 | 最多 10 | v5 §3 表 1+1+2+2+1+2+1=10（恰好）；脚本每 Phase 会话数一致 | 一致（计划满额未超上限） |
| RTT logger | 2 个，每个 ≤120s | v5 §7/§8、操作单 §3、脚本 S4/S6 各 1 个（120s 硬超时、启动前清残留） | 一致 |
| 主动复位 | 6 次 | v5 复位①-⑥；脚本 S1B/S2/S3/S4/S5/S6 各 1 | 一致 |
| 身份/RTT 签名核对会话 | ≤2（不写块不复位） | v5 §7、脚本 S4/S6 各 1（Test-P1RttSignature 只读 mem8） | 一致 |
| FR4/REC5 | 替代关系只消费一次 | v5 §6 FR4 备用会话替代 S5（互斥恰好其一，恒 6/恒 10）；脚本 S5 AcceptResults 含 FR4_MISSING_LINE + fallback 标志 | 一致 |
| REC6 | 失败收尾共用同一额度 | v5 §7、脚本 S6 与成功路径共用 | 一致 |
| 计划外 nRESET | 单步 ≥2 或全程累计 >2 即停 | v5 §6、操作单 §3 同文 | 一致 |
| Flash 写入边界 | 0x08000000-0x08004FFF | v5 §4 写入范围总账、脚本常量一致 | 一致 |
| RAM 控制块 | 0x20057E00-0x20057FFF | 同上 | 一致 |
| EEPROM | 0x00-0x7F 经既有 CLEAR_BCB | 同上 | 一致 |
| 恢复阶段禁项 | 不授权 App 烧录/QSPI 写入/断电注错/其他 opcode | v5/操作单 §3/合同 EXT-BOARD-STATE 同口径 | 一致 |
| build-only 构建 | 保留现有同一笔 1 次额度；publish_release=false、replace_existing_release=false | 操作单 §7、合同 CMD-RELEASE-BUILD/C-RELEASE-BUILD | 一致 |
| O1-O5 | 各 1 次，5/10/30/30/5 分钟 | 操作单 §4/§7 逐项一致 | 一致 |
| 受验 APK | 同一 APK 贯穿安装与两闭环 | 操作单 O1 留证/合同 C-APK-INSTALL | 一致 |
| 并存包名 | 专用并存 applicationId，不改生产默认包名，不卸载不清数据 | build.gradle.kts 默认空机制 + 操作单 O1 + 合同 | 一致 |
| 额度互借 | 恢复/O 序列/A1/B1-M 不互借 | 操作单 §6 | 一致 |
| 隧道窗口 | 最长 8 小时，到期或本轮结束即关闭 | 服务文档 §5.1/§6、操作单 §2 | 一致 |
| adb reverse | 本路线不需要 | 服务文档 §5.1/§6 明示不创建不删除映射 | 一致 |
| CF 账号/token | 不使用账号、不读旧 token | 服务文档 §5.1 账号边界 | 一致 |

## 5. 总结论：ADMISSION_PASS

理由：

1. 章程 §2.A-H 八项核对全部完成，结论 7 项 PASS + C 项 PASS（附 1 项
   非阻断 EVIDENCE_GAP）；无 BLOCK、无 CONCERN。
2. 全部可重跑的验证均已亲手重跑：validate_bundle（VALIDATION=PASS）、
   selftest.py（16/16 PASS）、CI 终态复查（两 run 双宿主 success）、
   全部产物哈希亲算。
3. 三项发现中无一项指向产物缺陷或授权违规：B-1 是章程文本笔误（产物
   与合同四元组一致）、C-1 是原始留证物理位置导致的复核限制（执行
   阶段会以实测值重新核对）、F-1 是脚本强于文档的增强。
4. 授权五节与全部执行文档（操作单第五版、恢复方案 v5、服务文档第五轮
   修订、合同 v3）总对照无实质矛盾；额度对账 19 项全部一致。
5. 唯一口径差异（最多 10 vs 恰好 10）是执行文档对授权上限的计划满额
   特化，方向更严格。

据此放行章程 §0 定义的两个阶段：
- **REC0-REC7 设备恢复执行**（恢复方案 v5 S1a-S6，入口
  `Tools/jlink/p3-3-recovery-execute.ps1`，逐 Phase 推进）；
- **Quick Tunnel 启动 + 受验 APK 构建**（服务文档 §5/§6 D1-D2 →
  §5.2 宿主端到端检查通过后消耗唯一一笔 build-only 额度）。

合同冻结（FROZEN）与 NOT_RUN 前检仍按授权第一节由非实现会话办理，
不在本放行范围内。

## 6. 是否存在需按授权第五节集中问用户的事项

**无。** 五种情况逐一判定：

1. 扩大资源/设备/写入边界——不需要：cloudflared 下载与缓存收敛 worktree
   `.cache/`，路径预检已在服务文档定义。
2. 增加费用或配额——不需要：build-only 沿用现有同一笔额度，恢复/O 序列
   额度均不追加。
3. 修改验收门槛或目标版本——不需要：判据、六态、终点双值（30201/
   43ee943a…、30202/c9582213…）均未改动。
4. 使用无法唯一确认的账号资源——不需要：Quick Tunnel 不用账号不读
   token。**条件性触发提示**：仅当 Quick Tunnel 实测不可用需走替代路线
   （Named Tunnel/DNS）时，才按服务文档 §5.3 集中申报（含浏览器鉴权
   前置）——属届时申报事项，非当前缺口。
5. 需要不可推断的用户输入——不需要：域名/DNS token/证书策略已被授权
   第二节免除。

## 附：本复核亲手执行的关键命令记录

- `git show --stat` / `git show <sha> -- <file>`（0087d17、a9db139）
- `sha256sum`（ETU×2、镜像×4、四件套×4、Boot×2、v2 合同）
- `gh run view 34755121482 / 34754918841 --json status,conclusion,headSha,jobs`（两次）
- `PYTHONIOENCODING=utf-8 python Tools/acceptance/validate_bundle.py …
  --allow-draft`（VALIDATION=PASS，退出码 0）
- `PYTHONIOENCODING=utf-8 python -B selftest.py`（16/16 PASS，退出码 0，
  重跑后无残留进程）
- Python json 结构化提取（合同顶层/判据/命令/EXT/矩阵字段）
- `tasklist` 残留进程核对（精确匹配，无残留）
