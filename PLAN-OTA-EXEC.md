# PLAN-OTA-EXEC.md — OTA 执行看板（全项目唯一状态源）

> 版本:v1.0(2026-07-23 创建)。本文档是 OTA 项目执行期**唯一**的任务与状态源,执行 agent 必须先读 `AGENTS.md` 的"OTA 执行规约"再操作本文档。
> 文档层级(信息唯一来源,禁止跨层复制):
> - `PLAN-OTA.md` v1.3 = 冻结架构契约(**只读**,改动只走 §9 变更登记回审)
> - `docs/ota-binary-contracts.md` = P0-1 产出后的**实现唯一依据**(产出后同样冻结)
> - 本文档 = 任务卡 + 状态 + 证据(执行 agent 唯一可写的计划文档)
> - `PLAN-OTA-GUIDE.md` = 用户视角驾驶手册(派单话术/人工点/放行判定,给用户看,agent 无需读)
> - `.claude/verification-report-ota-plan.md` = 复审报告(开工前必读,已知坑清单)
> - `AGENTS.md` = 编译/烧录/RTT/防坑权威流程(所有真机操作照此执行)

## 0. 看板操作规则(细则;强制条款见 AGENTS.md 规约)

1. **认领**:把任务卡"状态"从 `待办` 改 `进行中`,填"认领"(agent 标识+日期)。一个会话一次只认领一张卡;不越卡"范围"改文件。
2. **完成**:必须先在"证据"栏填入可核查内容(命令+关键输出摘录、产物路径+时间戳、哈希、截图路径;长输出落盘 `docs/ota-exec-notes/<卡ID>-*.md` 后填链接),才允许置 `完成`。空证据的"完成"视为未完成。
3. **验收分离**:置 `完成` 前,验收命令须由非实现会话执行(另起 agent 或主会话跑验收),验收者在证据栏追加一行"验收人+结果"。
4. **阻塞**:发现契约矛盾、不可实现、依赖缺失 → 状态置 `阻塞`,在卡内追加"阻塞记录:"一行写明,同时在 §9 变更登记表登记,然后**停止该卡**。禁止就地修改契约文档继续实现。
5. **research 落盘**:编码前检索/上下文分析结论一律写 `docs/ota-exec-notes/<卡ID>-<主题>.md`,不许只留在会话回复里(会话会被压缩,文件不会)。
6. **提交收口**:子 agent 不执行 `git commit/push/merge`;由主会话在用户确认后按小步提交收口。
7. **会话收尾**:每个工作会话结束前,回写所动任务卡的状态,并在 §10 会话日志追加一行。
8. 状态取值固定四种:`待办` / `进行中` / `阻塞` / `完成`。

## 1. 阶段状态总表

| 阶段 | 内容 | 状态 | 进度 | 开工门槛 |
|---|---|---|---|---|
| PRE | 前置修正(复审产物) | 进行中 | 2/4 | 无 |
| P0 | 契约冻结+基建 | 待办 | 0/6 | PRE-1/2/3 完成 |
| P1 | bootloader | 待办 | 0/6 | **P0 全部完成(方案硬门槛)** |
| P2 | MCU App 升级链 | 待办 | 0/6 | **P0 全部完成(方案硬门槛)** |
| P3 | BLE+Flutter | 待办 | 0/5 | P2-1/2 完成 |
| P4 | CI/CF | 待办 | 0/4 | P0 完成(可与 P1/P2 并行) |
| P5 | 联调验收 | 待办 | 0/3 | P1-P4 全部完成 |

**人工配合点总览(排期时预留)**:
- git 提交/推送确认:PRE-4 及各阶段收口;
- CF Secrets 与 `firmware-production` environment 审批人配置:P4-4;
- 手机侧操作(Flutter APP 连设备、断连重连):P3-5、P5-2;
- SD 卡拷入测试 .etu(拔卡→电脑拷贝→插回):P2-5、P5-1;
- 物理断电/拔插 SD 卡:P1-6、P5-2 中标注"物理"的注入点(J-Link 复位可近似大部分,真断电需在场)。

---

## 2. PRE 前置修正(来自复审报告,先于一切)

#### PRE-1 version_code 编码重定义(契约修订)
状态: 完成 ｜ 认领: Codex / 2026-07-24 ｜ 更新: 2026-07-24(实现完成,验收通过)
- 目标: 编码从 `major*1000+minor` 改为 `major*10000+minor*100+patch`(u32);在 `PLAN-OTA.md` 头部追加 v1.3.1 修订记录并更新 §3.1/§6.1 相关表述;同步 `firmware-build.yml` 计算与注释(现 :103-106)。旧公式产物 2007 < 新公式 2.7.0=20700,单调性向后成立,须在文档中写明。
- 输入: `.claude/verification-report-ota-plan.md` 补充 D;PLAN-OTA.md §3.1/§4/§6.1。
- 范围: `PLAN-OTA.md`、`.github/workflows/firmware-build.yml`。
- 验收: 2.8.0/2.8.1 映射为 20800/20801 且文档与 workflow 公式一致;全仓 grep 无残留旧公式表述。
- 证据:
  - research: `docs/ota-exec-notes/PRE-1-version-code.md`
  - `PLAN-OTA.md` 升 v1.3.1;§3.1 冻结 `major*10000+minor*100+patch`;§6.1 写明由有效 version_name 推导;迁移 `2007 < 20700`
  - `.github/workflows/firmware-build.yml` version step 改为同公式,从有效 version_name 编码(含 nightly 去后缀、minor/patch 0..99、u32 上界)
  - 本地映射: `2.8.0=>20800` `2.8.1=>20801` `2.7=>20700` `2.7-nightly.N=>20700`;`ACCEPTANCE_OK`
  - 旧公式 active 实现已清;残留仅迁移说明/历史草稿/任务卡表述(见 research)
  - 验收: 验收人 Claude(主会话,非实现者)/2026-07-24;按 §0.3 独立复核:
    1. 公式复算(PowerShell 镜像 workflow 逻辑):`2.8.0=>20800` `2.8.1=>20801` `2.7=>20700` `2.7.0=>20700` `2.7-nightly.N=>20700` `2.8.1-nightly.9=>20801`;单调性 `2007<20700` 成立(ACCEPTANCE_OK)。
    2. firmware-build.yml:113-129 公式与新 §3.1/§6.1 一致;从有效 version_name 编码(nightly 去后缀、minor/patch 0..99 校验、u32 上界校验、非法格式 ::error exit 1)。
    3. PLAN-OTA.md 头部已升 v1.3.1;§3.1:110/§6.1:187 公式与映射写明且一致。
    4. 全仓 grep 旧公式 `major*1000+minor`:active/normative 路径=0(仅 workflow 注释提及"禁止再使用"与历史/审计/任务卡表述,research 已注明属 PRE-1 写范围外)。
    结论: 通过。

#### PRE-2 RAM 基线口径修正(契约修订)
状态: 完成 ｜ 认领: Codex / 2026-07-24 ｜ 更新: 2026-07-24(实现完成,验收通过)
- 目标: 修正 PLAN-OTA.md §1/§9 的"总 RAM 384KB/82.96%/余 65KB"口径:如实记录 EOPB0 已扩展 512KB、GCC 链接划分 RAM 352KB + RW_IRAM2 160KB、`snapshotBuf` 恰好占满 RW_IRAM2(LiveMap.cpp:43-45);把"`.sram_ext` 160KB 升级期 overlay 复用"列为 §9 待评估项(由 P0-6 裁决)。实测数字由 P0-6/P2-6 回填,本卡只改口径与占位。
- 输入: 复审报告补充 C;generated_linker.ld:12-13;LiveMap.cpp:40-45。
- 范围: `PLAN-OTA.md` §1/§9。
- 验收: 文档不再出现与代码矛盾的 384KB 总量表述;overlay 评估项有明确验收定义。
- 证据:
  - research: `docs/ota-exec-notes/PRE-2-ram-baseline.md`
  - `PLAN-OTA.md` 升 v1.3.2;§1 MCU 行改为 EOPB0 512KB + RAM 352KB + RW_IRAM2 160KB + snapshotBuf 163840B 占满;旧 384/82.96/65 口径标作废
  - §9 拆为:RAM 基线(待 P0-6/P2-6 回填数字)、`.sram_ext` overlay 待评估(A 采纳契约化 / B 不采纳+原因,裁决=P0-6,禁止隐式挪用)、升级态峰值预算数字占位(不再写 60KB≤65KB)
  - 核对: `MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld` MEMORY;LiveMap.cpp SNAPSHOT 256×320
  - 验收: 验收人 Claude(主会话,非实现者)/2026-07-24;按 §0.3 独立复核:
    1. 代码核对:generated_linker.ld:12-13 实测 `RAM ORIGIN=0x20000000 LENGTH=0x58000`(352KB)+`RW_IRAM2 ORIGIN=0x20058000 LENGTH=0x28000`(160KB),合计 0x80000=512KB;LiveMap.cpp:`snapshotBuf[SNAPSHOT_W*SNAPSHOT_H]` SNAPSHOT_W=256/SNAPSHOT_H=320,RGB565=163840B=0x28000 恰占满 RW_IRAM2;`.sram_ext (NOLOAD)` 落 RW_IRAM2。与 research 记录一致。
    2. §1(:29)MCU 行已改为 EOPB0 512KB + 352+160 划分 + snapshotBuf 占满,旧 "384KB/82.96%/65KB" 标口径作废,峰值留 P0-6/P2-6 回填。
    3. §9 拆为三条(:217-219):RAM 基线(作废旧分母,实测待回填)+ .sram_ext overlay 待评估(裁决权 P0-6,验收定义 A 采纳/B 不采纳二选一,禁止隐式挪用)+ 升级态峰值预算占位(不再写 60KB≤65KB)。
    4. 头部已升 v1.3.2(含 PRE-2 修订说明)。
    5. 全文 grep:384KB/82.96%/「60KB≤65KB」类矛盾口径在 §1/§9 已消除(仅 §9 作废说明处保留指向性引用,符合"标作废"语义)。
    结论: 通过。

#### PRE-3 firmware-build.yml 与 §6.1 对齐
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 删除 push 事件触发 `register-cloudflare` 的条件分支(push 仅构建+上传 artifact,保留 `workflow_dispatch publish=true` 注册链);artifact 保留期改 14 天对齐 §6.1;push 不再创建 GitHub Release。`isFormalRelease: true` 硬编码在此对齐后语义正确(只剩正式链走注册),无需改脚本。
- 输入: 复审报告补充 A/B;PLAN-OTA.md:185;firmware-build.yml:161/:169-171。
- 范围: `.github/workflows/firmware-build.yml`。
- 验收: yaml 语法校验通过;push 路径的 job 条件不再含注册;`retention-days: 14`。
- 证据: —

#### PRE-4 构建基础设施与 OTA 文档入库
状态: 待办 ｜ 认领: — ｜ 更新: — ｜ **需用户确认提交**
- 目标: 将当前 untracked 的构建输入与方案文档提交入库:`CMakeLists.txt`、`cmake/`、`vendor/`、`MDK-ARM_F435/cmake-generated/`、`.github/workflows/firmware-build.yml`(PRE-3 修正后)、`PLAN-OTA.md`、`PLAN-OTA-DRAFT.md`、`PLAN-OTA-REVIEW-LOG.md`、`PLAN-OTA-EXEC.md`、`PLAN-OTA-GUIDE.md`。vendor/ 体积较大,提交前向用户报告体积。
- 依赖: PRE-1/2/3 完成后一并提交。
- 验收: `git ls-files` 含上述路径;(推送后)Actions 干净 checkout 构建绿。
- 证据: —

---

## 3. P0 契约冻结+基建(估时 3d;门槛:R4 五条全落文,遗漏任一重新阻断 P1/P2)

#### P0-1 五契约字节级成文 `docs/ota-binary-contracts.md`
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 五契约逐字段成文:①fw_header 96B(§3.1);②.etu 64B 外层头 + **40B 规范化内层头逐字段 offset/端序/CRC 覆盖范围表**(§3.2);③EEPROM BCB 64B×2 + seq 仲裁 + 安全写事务(§2.3);④外部槽头 ETSL 32B + staging 接收日志 ETRJ 页布局(§2.2/2.3);⑤BLE 帧协议含状态码表(§5.1)。`FW_HEADER_OFFSET=0x400` 在此定义为四方唯一来源;version_code 用 PRE-1 新编码;CRC16-CCITT/CRC32 多项式与初值、所有端序、错误码全部冻结;R4 五条+R8 五条逐条落文并标号。
- 输入: PLAN-OTA.md §2/§3/§4/§5.1;PLAN-OTA-REVIEW-LOG.md R4/R8 条目。
- 范围: `docs/ota-binary-contracts.md`(新建)。
- 验收: 方案引用的每个字段/数值在契约文档有且仅有一处定义;R4 五条+R8 五条可逐条对号;PRE-1 新编码已体现。
- 证据: —

#### P0-2 打包工具 `tools/etu_pack.py` / `tools/etu_unpack.py`
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: `--finalize` fw_header 回填(SHA 双零法+CRC,严格按 §3.1 顺序);.etu 组包(AES-CTR nonce **每包随机**、payload_crc32、40B 内层头解析后逐字段规范化重写);§2.2 三处上限检查的制包端(超限拒绝);unpack 做逆向解析+校验,供三方比对。
- 输入: P0-1 契约文档;`bsdiff_lzma_AES128-main/` 工具与 4 个已知坑(PLAN-OTA-DRAFT.md)。
- 范围: `tools/etu_pack.py`、`tools/etu_unpack.py`(新建)。
- 验收: pack→unpack 往返字节一致;同输入两次打包 nonce 不同;超限输入被拒并给明确错误。
- 证据: —

#### P0-3 golden vectors `tests/ota-vectors/`
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: toy-old.bin/toy-new.bin(4KB)、toy-patch.etu、toy-full.etu、expected.json(SHA+关键字段);打包器侧单测跑通;向量覆盖 seq 回绕/相等仲裁场景(§8 验收);为 P2 MCU 解析与 P3 Flutter 解析预留同一套向量。
- 范围: `tests/ota-vectors/`(新建)。
- 验收: 单测绿(命令+输出留证);expected.json 字段与契约文档一一对应。
- 证据: —

#### P0-4 EEPROM 安全写驱动 + `eeprom_bcb.c`
状态: 待办 ｜ 认领: — ｜ 更新: — ｜ 需真机(J-Link 全自动)
- 目标: 重写 EEPROM 多字节安全写:逐 8B 页写、每页 ACK polling(≤10ms 超时)、错误返回、全块读回比对(现驱动为无返回值 Wire 薄封装,EEPROM.cpp 全文);实现 BCB 双块单次事务(写非活动块 seq+1→读回→生效)与仲裁;**byte 255=0x55 初始化魔数保持不动**;boot/App 共用源文件。
- 范围: `Libraries/EEPROM/**`、新 `Libraries/EEPROM/eeprom_bcb.c/.h`(或契约文档指定路径)。
- 验收: 真机压测 1000 次写+读回零错(RTT 输出留证);仲裁单测覆盖 A 新/B 新/相等/单坏/双坏/CRC 坏。
- 证据: —

#### P0-5 QSPI API 安全化 + JEDEC 判定
状态: 待办 ｜ 认领: — ｜ 更新: — ｜ 需真机(J-Link 全自动)
- 目标: `qspi_cmd_send`/`qspi_busy_check` 等全部加超时与错误返回(现为无超时忙等,qspi_cmd_send:462),失败 fail-closed;`CONFIG_QSPI_SELFTEST_ENABLE` 默认 0,自检区 0x7F0000-0x7FFFFF 永久避让;开机读 JEDEC ID 按白名单(`EF4018/1C4018/1C4017/EF4017`)判定,不识别→置 OTA 禁用旗标(既有功能不受影响)。
- 范围: `Libraries/W25Q128/**`、`USER/HAL/HAL_W25Q128.cpp`、相关 CONFIG 头。
- 红线: 遵守 AGENTS.md SDIO/LiveMap 防坑清单;不触碰 SDIO 驱动与中断结构。
- 验收: 真机压测 1000 次读/写/擦零错;注错(探测超时路径)返回错误码而非死循环。
- 证据: —

#### P0-6 RAM 基线实测与 overlay 裁决
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 以当前 GCC 构建 map 与 AC5 map 实测各区占用,重算升级态峰值预算(§9 表);裁决:16KB 或 8KB LZMA 字典、是否契约化"升级独占页复用 `.sram_ext` 160KB 作 OTA 缓冲"(若契约化,须定义 LiveMap 排他与恢复规则);结论回填 PLAN-OTA.md §9(此回填属 PRE-2 预留的合法修订)与契约文档。
- 验收: map 摘录留证;预算表全部为实测口径;overlay 裁决有明确"是/否+理由"。
- 证据: —

---

## 4. P1 bootloader(估时 5-7d;门槛:P0 全部完成)

#### P1-1 boot 工程骨架与 fw_header 统一校验
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 64KB boot 工程(GCC,ORIGIN=0x08000000,VECT_TAB_OFFSET=0):BCB 仲裁读、QSPI 槽头读(带超时,失败 fail-closed 跳过外部槽分支)、内 flash 编程、CRC32+SHA-256、按键检测(≥3s 恢复模式)、恢复模式 UART-Ymodem 接收(§5.3 传输层 len/CRC);fw_header 统一校验全项(§3.1:header_crc→SHA 双零重算→hw_rev→layout_id→min_boot_ver→向量表范围)。**boot 永不含 LZMA/bspatch/BLE/AES(方案红线)**。
- 范围: 新 boot 目录(契约文档定名,建议 `boot/`)。
- 验收: boot.bin ≤64KB;校验项与 §3.1 清单逐条对号;golden vectors 中坏头/坏 SHA 样本全部被拒。
- 证据: —

#### P1-2 App 重定位双链接
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: App GCC linker ORIGIN=0x08010000/LENGTH=960K;`system_at32f435_437.c` 的 `VECT_TAB_OFFSET` 改 0x10000(现为 0,SystemInit:100 会重写 VTOR);新增 `.fw_header` 段 @ORIGIN+0x400 + `ASSERT(SIZEOF(.isr_vector)<=0x400)`;App 启动期读 VTOR 与预期比对自检。AC5 工程仅本地对照,OTA 产物一律 GCC(§7)。
- 范围: `MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld`(或其生成源)、`system_at32f435_437.c`、启动自检代码。
- 验收: GCC map 显示 `.fw_header` 落位 0x08010400;isr_vector 尺寸断言在;VTOR 自检代码在。
- 证据: —

#### P1-3 搬运/回滚/试启动状态机
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §4 全部状态转移:STAGED→APPLYING(copy_phase=1,resume_block=0)逐 4KB 块"擦→写→读回→resume_block++ 持久化",重入续搬绝不整区擦;TEST_BOOT try=3 先持久化 try-- 再跳;三连失败→ROLLBACK(首转原子写 copy_phase=2+resume_block=0,R4-①)同法续搬,完成后同样过 fw_header 全项校验;backup 无效→recovery 槽→恢复模式;STAGED→CONFIRMED 期间 backup 槽锁定。
- 验收: 状态机单测(可 PC 侧仿真 flash 层)覆盖每个转移与每个断点重入;真机走通 STAGED→CONFIRMED。
- 证据: —

#### P1-4 boot→App 交接跳转
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §4 字级契约:ICER/ICPR 全清+SCB->ICSR PENDSTCLR/PENDSVCLR、SysTick 停、PRIMASK/BASEPRI/FAULTMASK/CONTROL 交接值、VTOR=0x08010000→DSB+ISB→MSP→DSB+ISB→跳向量[1];不用 PRIMASK 屏蔽做跳转。
- 验收: 注错(跳转前人为挂起 SysTick/外设中断 pending)后 App 正常运行;真机 boot↔App 往返稳定。
- 证据: —

#### P1-5 J-Link bootstrap 脚本与文档
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §7 一次性部署脚本:烧 boot@0x08000000、重定位 app@0x08010000、boot 首启 BCB 自动初始化 CONFIRMED(cur_vcode 读自 fw_header)、(可选)写 recovery 槽;recovery 资产 J-Link 直刷脚本须剥离尾部 8B(R4-⑤)。沿用 AGENTS.md J-Link 流程(设备全名 AT32F435RGT7、SWD 1000kHz)。
- 范围: `tools/`(脚本)+ `docs/`(bootstrap 手册)。
- 验收: 真机从纯 AC5 旧布局一键迁移到 boot+app 新布局并正常开机。
- 证据: —

#### P1-6 注错试验与断电矩阵
状态: 待办 ｜ 认领: — ｜ 更新: — ｜ **部分需用户物理配合**
- 目标: 注错全回滚:候选 CRC 坏/搬运中断电/三连失败;断电矩阵 20 点(§8):J-Link halt+复位注入可自动化的点全自动跑,**标注"物理"的点(擦/写指令飞行中真断电)列清单请用户在场配合**;每例记录状态轨迹+最终版本哈希+"可启动或进恢复"二判。
- 验收: 20 点矩阵表全绿(证据落 `docs/ota-exec-notes/P1-6-*.md`)。
- 证据: —

---

## 5. P2 MCU App 升级链(估时 4-6d;门槛:P0 全部完成;验收:P0 打包器产物真机 SD 升级闭环)

#### P2-1 staging 写入与接收日志
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §2.3 staging 页布局(ETSL+ETRJ+block_bitmap):ETRJ 先写读回;接收期只动位图;**重传已部分写入块前先扇区擦除,写完读回后才清位(R8-1)**;包终验后 ETSL 字段先写读回、commit_marker 最后单独写(R8-2);新 package_sha256 才整页重建。
- 验收: golden vectors 驱动的写入/重入单测;真机断点重入(J-Link 复位)后位图与 durable_off 一致。
- 证据: —

#### P2-2 .etu 解析 + AES-CTR + LZMA-Alone 解包
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 按契约文档逐字段解析(**禁 struct memcpy**);校验链 §4:头 CRC→payload_crc32→hw_rev→layout_id→min_boot_ver→target_vcode>cur_vcode(降级拒绝);全量:解密→LZMA-Alone 解压→candidate 直写,offset+len 逐次钳制(§3.2);candidate 全镜像 SHA 复核(双零法)。AES key 走 `ota_keys.c` 编译期注入,库内示例 key 仅开发。
- 验收: toy-full.etu 真机/PC 仿真解包结果与 expected.json 一致;坏包样本全部被正确拒绝且 BCB 不动。
- 证据: —

#### P2-3 bspatch 流式集成
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 差分链:base_vcode+base_sha8 校验→解密解压→bspatch→candidate。**集成方式(复审修正 2,禁照抄 README 的 malloc(old_size))**:old=内部 flash XIP 指针(0x08010000 直读);patch 输入=QSPI staging 流式 reader(替换 `vfopen` 的 RAM-only 假设,interface.c:281);new 输出=`bs_flash_write` 回调写 QSPI candidate(用 P0-5 安全 API);40B 内层头按契约解析。内层 ph_ocrc 作二重兜底。
- 输入: `bsdiff_lzma_AES128-main/bspatch/`;复审报告修正 2;§9 内存预算(P0-6 裁决值)。
- 验收: toy-patch.etu 合成结果与 toy-new.bin 逐字节一致(真机或 PC 仿真+真机抽验);堆峰值实测≤P0-6 预算。
- 证据: —

#### P2-4 SD 通道:文件管理页 + 二次确认
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §5.2 "关于设备"→"文件管理"(复用 RouteSelect 框架,过滤 `.etu`)→选中→现版/目标版对比弹窗→读文件写 staging→进同一状态机。
- 红线: 遵守 AGENTS.md RouteSelect/LVGL 组、字体子集(`font_cn_16.c.chars` 先查字)、路径剥离契约、禁 shadow/自绘等全部教训;新增 Keil 页面组要拷 `<GroupOption>`(--cpp11 坑)。
- 验收: 模拟器截图(专名保存,不复用 sim_new.png)+真机 SD 选包升级闭环;App.cpp 生产入口恢复 `Pages/Startup`。
- 证据: —

#### P2-5 backup 自拷与 STAGED 提交
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: candidate 复核通过后:当前版自拷 backup(读回 CRC、槽头 marker-last)→BCB=STAGED→UI 提示重启;仅 CONFIRMED 态允许自拷(backup 锁定规则);App 自检(HAL 全初始化+主循环 30s+IWDG 正常)后写 CONFIRMED;TEST_BOOT 期间拒绝发起新 OTA。
- 验收: 真机完整一轮 SD 升级:STAGED→重启→APPLYING→TEST_BOOT→CONFIRMED,RTT 全程留痕。
- 证据: —

#### P2-6 升级态 RAM 峰值实测回填
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 以 StackInfo+堆水位实测升级全流程峰值,回填 §9;若超 P0-6 预算→字典降 8KB 并同步制包端(etu_pack 参数)。
- 验收: 实测数据留证;预算表闭环(实测≤预算或已降档)。
- 证据: —

---

## 6. P3 BLE+Flutter(估时 5-7d;门槛:P2-1/2 完成;验收:真机 BLE 闭环+断连×10 续传)

#### P3-1 MCU BLE 帧层
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §5.1 全部:`A5 5A` demux(其余字节走现有 TinyBTPlus 文本协议);OTA 会话期关闭文本回显/200ms X-Trace(HAL_Bluetooth.cpp:67,HAL.cpp:107 注册)/调试透传;128B 分段、4KB 块窗口、block_bitmap ACK、500ms 活性重发;**off<durable_off 的重复 DATA 幂等(R8-4)**;UART 接收缓冲 ≥4KB(现 512B,mcu_config.h:40;评估全局改或蓝牙串口单独改);seq 16bit 回绕比较。
- 验收: PC 侧模拟发送器(或 Flutter 调试页)对向量包全传;丢段/乱序/重复注错全部正确恢复。
- 证据: —

#### P3-2 GET_INFO 设备身份链
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 0x00 GET_INFO→0x80 INFO{model 8B ASCIIZ,hw_rev,layout_id,boot_ver,cur_vcode,image_sha256,proto_ver,max_window_segs=32};model 定值与 CF `DEVICE_MODEL=e-track-at32f435` 的映射在契约文档冻结。
- 验收: 真机查询回包字段与 fw_header/BCB 实值一致。
- 证据: —

#### P3-3 Flutter 传输与升级 UI
状态: 待办 ｜ 认领: — ｜ 更新: — ｜ **APK 构建走 GitHub Actions(app 子项目禁本地构建)**
- 目标: BLE 帧层(MTU-3 分片、credit 窗口、断点续传);实现 `startOtaUpgrade()`(现固定 false,ota_service.dart:234);删除硬编码机型/0.0.0(ota_upgrade_page.dart:595-596),改 GET_INFO 数据流;进度/续传 UI;minAppVersionCode 兼容提示。
- 验收: Actions 构建绿+APK 可装;对真机传输 toy 包与真包成功。
- 证据: —

#### P3-4 AT 提速实测
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: 115200 基线吞吐实测;AT 提速(至 921600 逐档)稳定性与吞吐记录;超时/重传参数按实测标定(500ms 为初值非契约);流控全靠协议 credit(硬件流控引脚接地,禁启用)。
- 验收: 吞吐/丢包数据表留证;选定生产波特率写入契约文档。
- 证据: —

#### P3-5 真机 BLE 闭环
状态: 待办 ｜ 认领: — ｜ 更新: — ｜ **需用户操作手机**
- 目标: 手机 APP→查询→下载→BLE 传输→MCU 升级→重连 GET_INFO 确认新版本;断连×10 续传成功(§8)。
- 验收: 每轮的 durable_off 恢复记录+最终版本哈希;10/10 通过。
- 证据: —

---

## 7. P4 CI/CF(估时 2-3d;门槛:P0 完成,可与 P1/P2 并行;验收:正式发布→推送→BLE 升级全链演练)

#### P4-1 firmware-build.yml 正式发布链
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §6.1 制包顺序①-⑥:构建占位头 app.bin→`etu_pack.py --finalize`→full.etu+patch.etu(基版=上一正式版**最终** bin,从 R2/Release 取,记录 from_image_sha256)→**bspatch 自验逐字节比对(工具 exit code 恒 0,以 stdout+比对判定)**→recovery 资产(app.bin+尾 8B)→GitHub Release 三资产→注册链;`firmware-production` environment 人工审批;vcode>CF 现值校验;PRE-1 新编码。
- 依赖: PRE-3/4、P0-2。
- 验收: dispatch 演练一轮全绿;Release 含三资产且哈希与 metadata 一致。
- 证据: —

#### P4-2 D1 多资产模型与 latest 选包
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §6.2-1/2:新迁移 `firmware_release_assets`(kind∈{full,patch,recovery};`base_image_sha256 NOT NULL` 哨兵 `''`+CHECK+唯一键 `(release_id,kind,base_image_sha256)`);release 增 draft/ready 原子门槛(事务内校验恰一 full+R2 digest 全过才 ready,渠道晋升仅接受 ready);latest 增 `currentImageSha` 选包(patch 匹配否则退 full);注册脚本改资产数组;recovery 不自动分发;旧单资产数据迁移回填 full。
- 验收: **SQL 实测:同 release 插第二个 full 被拒、同基版第二个 patch 被拒、缺 full 置 ready 被拒(R8-5)**;latest 三场景(匹配 patch/退 full/无更新)接口测试绿。
- 证据: —

#### P4-3 admin 撤回语义与运营开关
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: §6.2-3+"回滚→撤回(retract)"更名:UI 文案/API 注释/确认弹窗写明"仅影响未升级设备,已升级设备不可降级,救治=发更高 vcode";渠道停发开关、reason 必填、差分基版保留策略、晋升事务原子性验证。
- 验收: admin 端演练截图+接口测试。
- 证据: —

#### P4-4 Secrets 与 environment 配置
状态: 待办 ｜ 认领: — ｜ 更新: — ｜ **需用户操作**
- 目标: 用户配置 `CLOUDFLARE_ACCOUNT_ID/API_TOKEN`、`TRACE_UPDATE_SERVICE_URL/DEPLOY_TOKEN`、R2 bucket 变量、`firmware-production` environment 审批人;AES 生产 key 入 CI Secrets(P0-2 打包器读取)。
- 验收: P4-1 演练能走通注册(即 Secrets 生效)。
- 证据: —

---

## 8. P5 联调验收(估时 3-5d;门槛:P1-P4 全部完成)

#### P5-1 双通道回归
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: SD/BLE × 全量/差分 四组合各至少一轮真机升级;升级后 GET_INFO 与 fw_header 复核。
- 验收: 4/4 通过,版本哈希留证。
- 证据: —

#### P5-2 故障注入矩阵
状态: 待办 ｜ 认领: — ｜ 更新: — ｜ **部分需用户物理配合**
- 目标: §8 注入点=每个持久化提交点/擦写/窗口 ACK/重连;每例输出状态轨迹+最终版本哈希+"可启动或进恢复"二判;弱信号/低电量/满 staging/降级包/坏包/错板(hw_rev/layout_id)全过;含 TEST_BOOT 三连失败回滚、recovery 路径、物理断电抽样点。
- 验收: 矩阵表全绿,证据落 `docs/ota-exec-notes/P5-2-*.md`。
- 证据: —

#### P5-3 文档收尾
状态: 待办 ｜ 认领: — ｜ 更新: —
- 目标: bootstrap 手册、升级操作手册(用户视角)、风险台账更新(§9 开口项逐条关闭或转 v2);AGENTS.md 增补 OTA 维护期防坑条目(实施中沉淀的新教训)。
- 验收: 文档齐,§9 开口项无悬空。
- 证据: —

---

## 9. 契约变更登记表(回审通道)

| 日期 | 发起(卡ID/agent) | 冲突点 | 提议 | 处置(用户/审查结论) | 状态 |
|---|---|---|---|---|---|
| — | — | — | — | — | — |

## 10. 会话日志(每会话一行:日期 ｜ agent ｜ 动了哪些卡 ｜ 一句话结果)

- 2026-07-23 ｜ 主会话(Claude) ｜ 创建看板 v1.0;AGENTS.md 增"OTA 执行规约" ｜ 复审结论已并入 PRE 卡与相关卡红线,报告见 `.claude/verification-report-ota-plan.md`

- 2026-07-24 ｜ Codex ｜ PRE-1 ｜ 认领并实现 version_code 新编码(PLAN-OTA.md v1.3.1 + firmware-build.yml);证据已填,待非实现会话验收
- 2026-07-24 ｜ 主会话(Claude) ｜ PRE-1(验收) ｜ 按 §0.3 独立复核:公式复算+grep+文档一致性,通过;卡置完成,PRE 1/4
- 2026-07-24 ｜ 主会话(Claude) ｜ PRE-2(验收) ｜ 按 §0.3 独立复核:linker/LiveMap 代码核对+§1/§9 口径+grep 残留,通过;卡置完成,PRE 2/4

- 2026-07-24 ｜ Codex ｜ PRE-2 ｜ 认领并修正 RAM 基线口径(PLAN-OTA.md v1.3.2 §1/§9);overlay 评估项已写验收定义;待非实现会话验收
