# 验收会话提示词模板（派给独立验收 agent）

> 用途：把一张已「完成实现、待验收」的看板任务卡冻结成一份可直接派发的验收提示词。
> 撰写者：主会话或立卡方。执行者：**非实现会话**（强模型/验收侧）。
> 配套：`docs/ota-prompts/prompt-template-implementation.md`（执行侧模板）。
>
> 本文件分两部分：
> - **Part A 撰写检查表** —— 给撰写者看，**禁止复制进派发的 prompt**。
> - **Part B prompt 骨架** —— 复制到 `docs/ota-prompts/prompt-<卡ID>-acceptance.md`
>   后逐项填空。派单提示词是规范性文件，必须落在 `docs/ota-prompts/`（纳入 Governance
>   profile 与 Acceptance Governance workflow），**不得放在 `.claude/`**。

---

# Part A：撰写检查表（不要复制到派发文件）

## A.1 验收侧的失控是真实成本，必须先设上限

P2-5 F4 独立验收（证据目录 `.acceptance-p2-5-f4/20260810-200500`）耗时约 **43 小时**，
产出 33 PASS / 0 FAIL / **33 NOT_OBSERVED**，真机 OTA 与封包一项未做。三个结构性根因：

| 根因 | 表现 | 本模板对应条款 |
|---|---|---|
| **审计递归** | 把「执行前审计 harness」理解成每次 harness 编辑都重建全链证明，做了 R3–R22 共 19 轮，审计生成器代码 768 KB，而被验收的生产改动只有 12 文件 / 350 行。矩阵冻结在 33 PASS 后又做 R18–R22 五轮，产品证据增量为 **0** | Part B §2 harness 冻结 + §3 轮次上限 |
| **门禁自指** | 917 ms 门禁 = 历史观测 817 ms + 100 ms 输入轮询，**不是产品需求**。实测 914.387 ms，余量 2.6 ms（0.28%），正常抖动即翻转结论 | Part B §4 门禁来源审查 |
| **边缘 fixture 误当强制项** | 某判据实际已被既有 fixture 覆盖同一行代码，真正独立的只是一个纯函数分支（宿主测试即可），却按模拟器路线试了 4 次，全部撞 Win32 `MAX_PATH` 260 上限 | Part B §5 路线选择前置 |

**结论**：验证基础设施的复杂度一旦超过被验证产品，验收就不再收敛，并且会把 harness
故障误报成产品 FAIL（P2-5 的 r3 报告 FAIL 结论即被后续 6/6 PASS 推翻，根因是截图
harness 干扰）。

## A.2 撰写完成前自检

- [ ] 已指明冻结合同路径与版本（`docs/acceptance-contracts/<卡ID>-v<n>.contract.json`）
- [ ] 已列出本卡全部数值门禁**及其来源分类**，历史观测值来源的已标注「需用户裁定」
- [ ] 已写明有限执行计划与真实停止条件，收敛绑定 rerun plan，不机械套默认三轮上限
- [ ] 已要求失败分层（PRODUCT_FAIL / HARNESS_FAIL / EVIDENCE_GAP / ENV_BLOCKED）
- [ ] 已要求一次汇总当前可安全检查的问题和未覆盖项，非首错即打回
- [ ] 反馈遵守 `docs/agent-collaboration-contract.md`，给出方向、不可变约束及验证判据
- [ ] 已查 `docs/agent-collaboration/index.md`；未把历史一次性硬件额度当作永久项目规则
- [ ] 已核对实现批次的已知阻断、自测和前置条件，未用正式高成本验收代替开发排错
- [ ] 每项判据只列真实依赖，多输入组已填 `dependency_rationale`，未漏掉 runner/探针
- [ ] 已检查粗组是否造成不必要的多数判据失效，保留粗组时已说明真实共享依赖或不确定性
- [ ] 合同命令已标明 preflight/product/evidence 阶段、超时、观测配额与恢复/重试条件
- [ ] 已区分 rerun plan 的失效范围与操作授权，未把计划非空视为追加硬件配额
- [ ] 已列出需用户物理配合的项，并禁止以其他方式替代
- [ ] prompt 里没有任何 `git commit/push/merge` 指令

---

# Part B：prompt 骨架（复制此段并填空）

```text
# 任务：独立验收 OTA 看板任务卡 <卡ID>（<一句话标题>）

> 本文件是 <卡ID> 验收会话的提示词。落盘时间 <YYYY-MM-DD>。
> 你**不是**本卡的实现者。实现证据见 <实现证据文档路径>。

## 0. 你的身份与规约（先读，违约按影响范围处理）

你是 **<卡ID> 的独立验收会话**。强制生效：

1. `AGENTS.md`「独立验收执行规约」+ `docs/acceptance-execution-contract.md` v3。
2. **不得覆盖实现认领人**。你只在证据栏追加「验收人 + 轮次 + 单轮结果」。
3. 单轮结果固定五种，**必须分层**，不得混同：
   `PASS` / `PRODUCT_FAIL` / `HARNESS_FAIL` / `EVIDENCE_GAP` / `ENV_BLOCKED`。
   **harness 失败绝不能写成产品不通过**（P2-5 曾因此误报 FAIL 后被推翻）。
4. **不提交**：禁止 `git commit` / `push` / `merge`，由主会话收口。
5. **绝对禁止** `git checkout -- <file>` / `git restore`。
6. 收尾：回写卡状态（只改状态字段允许的四种取值），看板 §10 追加一行。

全局准则：**一切输出用简体中文**（代码标识符除外）。

## 1. 冻结合同（唯一标准）

- 合同：`docs/acceptance-contracts/<卡ID>-v<n>.contract.json`，状态必须为 `FROZEN`
- 矩阵：`.acceptance-<卡ID>/<round>/evidence-matrix.json`
- **本 prompt 不是标准**。prompt 只解释合同，冲突时以合同为准
  （`docs/acceptance-execution-contract.md` §1.2）。
- 验收开始后**不得原地改合同**。新增或改变门禁必须升版本重新审批：
  同一 `task_id`、版本严格加一、用 `parent_contract_sha256` 绑定上一份。

合同顶层必须写死 `freeze_commit`（被验实现所在提交）、`freeze_tree` 与
`profile_config_blob`。profile 范围取自冻结 tree 内的
`Tools/provenance/manifest_profiles.json`，不得用当前 checkout 的配置解释历史 tree，
也不再生成 manifest 文件。实现与 harness 必须先提交再验收；profile 内脏文件或未跟踪
文件会被执行门禁拒绝。

每项判据只列直接依赖；多个 `input_groups` 必须填 `dependency_rationale`。仓库内
验收 runner/探针参与采集或解释观测时必须包含 `validation` 或已审批的 validation_inputs
组件组，不得照抄单组模板来减少复验。已由 production_source 覆盖的生产构建入口无需重复
绑定 Validation，但不能遗漏它调用的验收探针。组件合同的 commands 还必须声明 input_groups 和
runner_paths；判据包含命令全部依赖。构建、采集、解析、封包分开列判据，不塞进一条全量命令。
命令阶段、硬件配额和重试条件以合同 `commands[].description` 的已批准说明为准。

执行前先用 `FROZEN` 合同和 `NOT_RUN` 矩阵运行下列命令；最终报告前再运行一次。任一次
失败都不得执行或宣告通过：

  python Tools/acceptance/validate_bundle.py \
    --contract docs/acceptance-contracts/<卡ID>-v<n>.contract.json \
    --matrix .acceptance-<卡ID>/<round>/evidence-matrix.json \
    --repo-root <本轮精确 Git worktree>

### 1.1 批量审查与准入

按执行合同 §7.3 先审一个完整、有限的变更批次：契约/SLA、调用与构建链、依赖、harness
正反例、环境边界和配额。完成当前可安全检查的相关范围后，一次反馈发现与未覆盖项；
不得首错即打回实现者，也不得为“审查完备”无限扩展到范围外事项或另造审计 harness。

冻结前的代码预审可以读取未提交批次，但不能采正式证据或宣告产品 PASS。本批已知阻断
缺陷无修复/针对性自测、必要宿主检查未过或前置条件不满足时，不启动依赖它的高成本
正式验收。仍需真实观测的未知项列入合同计划，不能要求它们在首次正式观测前先通过。
正式执行仍须已提交冻结基线，自测不替代独立验收。

发现安全风险或污染时立即暂停受影响动作；继续其他独立安全的检查并汇总。清单复用现有
证据文档的 `发现ID | 依据/判据 | 影响范围 | 处置 | 自测证据`，不为每个问题开一套报告。
整改反馈按批次返回，只核对该批修复、受影响依赖与未覆盖项，不重复全量审计无关文件。

### 1.2 可执行反馈而非模糊打回

遵守 `docs/agent-collaboration-contract.md`，回复实现问题或缺陷时沿用稳定 ID，标明
DECIDED / NEED_EVIDENCE / OUT_OF_SCOPE。给出规则/代码/原始证据依据、首选最小
修复方向及入口、不可变约束、最小验证与负例、责任人和下一步。未查明原因时提出有界
鉴别检查并说明各结果的下一步，不能把假设当结论，也不能只说“增强健壮性”“重测”。
明确哪些是必修产品缺陷、非阻断建议、harness/证据问题或需要主会话裁定的范围变化。
指出函数、推荐设计和测试判据不损害独立性；代写产品修复则披露角色变化，由其他非实现者
复核受影响范围。先完成本批可安全检查项再集中返回，按 ID 和实际自测证据关闭问题。
Flutter 调试/取证先读 `.agents/skills/e-track-flutter-debug/SKILL.md`；不得因主机采集
失败就要求重复成功的 OTA，也不把开发自测或建议方向写成独立验收 PASS。

## 2. harness 一次性冻结（防审计递归，硬约束）

1. **准入检查时**：确定本卡 harness 全集（runner、探针、截图脚本、注错脚本），
   一次完成相关静态检查、正反例与安全 dry-run，问题集中修复后再冻结稳定批次。
   dry-run 不能偷偷启动未授权的烧录/产品观测；负例不得省略。
2. 冻结后 harness 若必须修改：**只对被改文件做增量审计**
   （语法/AST、常量结论、动态加载、强杀路径、路径边界），
   **不得**因一次编辑就重建绑定全部历史审计产物的证明链。修改后停止执行，把文件交给
   主会话先提交，再按新冻结点生成 rerun plan；禁止直接在脏 harness 上继续采证。
3. 完整 provenance 复核**只做两次**：封包前一次、最终报告前一次。
4. 硬编码结论、日志污染、来源/哈希失配等会使受影响证据失效，不能继续判 PASS。
   普通 harness 编辑不自动作废全部结论，按真实依赖和 rerun plan 确定范围，不默认整卡重来。
5. harness 必须 fail-closed：缺日志、超时、地址漂移、解析失败、进程异常一律失败，
   禁止常量 PASS、无条件汇总字段，禁止用「没有错误日志」推定通过。
6. 至少保留一个负例或故障注入，证明判据具有鉴别力。

**红线**：不得递归构造“证明 harness 的 harness”和重复历史审计套件。工具规模异常时先
说明必要性并复用已有工具；必要单元测试、负例与路径守卫不能因为测试行数多于产品而省略。

## 3. 有限计划与收敛条件（硬约束）

- 执行计划：**<判据/实验矩阵、有限次数、停止条件>**。不默认三轮上限；只有用户明确
  上限或已冻结合同的实际边界才是审批门禁。开发批次按 `docs/device-experiment-policy.md`
  连续执行，不能每修一项或每跑一次 OTA 就向用户申请同一权限。
- **开新轮次的唯一判据是机器生成的 rerun plan，不是人工回答**。开轮前先用
  `validate_bundle.py --write-rerun-plan` 生成计划（失效规则见
  `docs/acceptance-execution-contract.md` §6）。若 `rerun_criteria` 为空，
  且不存在任何 required 命令、产物或证据缺口，**不得开启新轮次**。
- 因 `HARNESS_FAIL`、`EVIDENCE_GAP`、`ENV_BLOCKED` 修复后**重新采集同一条产品观测值
  是允许的**（这类轮次的 rerun plan 非空或存在 required 缺口）。不得用「产品值没变」
  为由拒绝重采，也不得反过来用「换个说法就是新观测」为由绕过上一条。
- **rerun plan 只计算失效范围，不授予操作权限或追加配额**。先保存失败原始输出和分类；
  在已有授权及剩余配额内，记录已提交的产品/harness 修复或外部状态变化后才可复测。
  用户明确上限/冻结计划耗尽，或需超出已授权路线及风险范围时先审批，不能靠换轮次
  或证据目录抹掉历史动作。既定计划内的必要动作不再逐次请示。
- 只重跑 `required_commands` 所列观测/采集命令；必要的只读预检、证据整理与完整性校验
  仍可执行。未失效的 `EXECUTED PASS` 使用 `REUSED`；日志缺失、污染或测量不可信的观测
  必须按计划重新采集，不能只改分类就复用。不得无条件重跑整套宿主、构建或硬件流程。
- 如果未失效判据的全部命令已被其他失效判据纳入计划，可消费同一次真实输出，不另执行
  共享命令，也不带跑额外命令。最终校验拒绝本可复用却新增计划外命令的 EXECUTED PASS。
- 首轮后即使全部 EXECUTED，也要传实际前轮的 --previous-contract / --previous-matrix。
  --write-rerun-plan 输出 FINAL_VALIDATION=NOT_RUN，只是计划生成；必须去掉该选项完成
  最终校验。无 REUSED 时矩阵 rerun 绑定字段仍为 null，不得伪造复用来填字段。
- 多轮复用用 origin_contract_sha256 / origin_matrix_sha256 直接绑定原始实测 PASS，
  reused_from_round 填原始轮次。将原始和所需中间包通过可重复的 --reuse-source 两路径参数
  交给校验器；上一轮仍是实际上一轮，不能跳过 FAIL。缺包、计划或哈希先补证据，不默认重采。
  校验器只读检查历史合法性，不另写证明 harness，不逐轮重建旧固件。
- 对纯解析/封包修复，只重新处理未污染的原始字节；不得复制旧 observed 冒充新解析结果。
  只有采集依赖变化、原始观测缺失或污染时重采相应判据。
- 矩阵一旦冻结在某个结果集上，除以下情况不得重开：
  ① 发现 required outcome 被硬编码；② 产品源（Production profile 路径集）变化；
  ③ 自动 rerun plan 判定该判据必须重跑；④ 用户裁定重开。

## 4. 门禁来源审查（防门禁自指，先做再测）

**在跑任何性能/耗时判据之前**，逐条检查数值门禁来源，只允许三类：

- `product_sla`：产品需求或规格
- `protocol_contract`：协议/契约推导
- `safety_ratio`：明确的安全比例

若某门禁实际是「历史观测值 + 极小余量」→ **停止该判据，请用户裁定**。
不得由你自行放宽，也不得硬扛。历史测量值只能作基线或告警阈值。

同时检查余量：实测与门槛的余量若小于正常抖动幅度，该判据**不具鉴别力**，
必须在报告中如实标注，不得凭一次通过就写 PASS。

## 5. 路线选择前置（防边缘 fixture 浪费）

对每个判据，动手前先回答两问：

1. **是否已被既有 fixture 覆盖同一代码路径？** 是 → 标注覆盖来源，不重复搭环境。
2. **最省的可信路线是什么？** 纯函数 → 宿主测试；需要 LVGL/文件系统 → 模拟器；
   只有涉及真实外设/时序/供电才上真机。

已知环境上限（撞上就换路线，不要反复试）：
- Win32 物理路径 `MAX_PATH` = 260，构造超长 LVGL 路径的模拟器方案不可行
- <本卡相关的其他已知环境上限>

同一路线连续 2 次因环境限制失败 → 只在合同已批准的替代路线内切换，否则申请更版或标
`ENV_BLOCKED`；不得为试第 3 次绕过配额。

## 6. 本卡判据与执行要点

<逐条列出合同里的 required 判据，给出：判据ID、要观测什么、用哪条路线、
 已知坑。不要在此重复合同正文，只写执行要点。>

1. <判据ID>：<观测目标> ｜ 路线：<宿主/模拟器/真机> ｜ 注意：<已知坑>
2. ...

需用户物理配合的项（**你做不了，如实标注「待用户配合」，
不得以其他方式替代或声称通过**）：

- <例如：拔掉 J-Link 与 USB 后电池供电开机；拔卡拷贝 .etu 后插回>

## 7. 真机执行纪律（若本卡涉及）

先做有超时的 preflight，默认只读；必要的暂停 WDT/调试域写入须有合同规定的地址、值、
非持久性和恢复方式。若需部署镜像，先检查工具、连接和操作边界，再按授权部署并核对固件
身份，最后启动观测。烧录、擦除、写 SD 不属于免费预检；不得因身份检查顺序错误反复重刷。

严格按 `AGENTS.md`「J-Link 闭环防卡死清单」。RTT 地址必须从**本次烧录目标本次
链接生成的 map** 取 `_SEGGER_RTT`：

- GCC 生产：`MDK-ARM_F435\cmake-generated\build-gcc-release\app-gcc\X-Track-App-GCC.map`
- AC5 辅助：`MDK-ARM_F435\Listings-App-AC5\X-Track-App-AC5.map`

顺序：查 map → `mem8 <RTT> 16` 验「SEGGER RTT」签名 → 读 down descriptor →
启动**单个** `JLinkRTTLogger` 且带明确超时。启动前清残留：

  Stop-Process -Name JLinkRTTLogger -Force -ErrorAction SilentlyContinue

污染日志（旧 RTT 地址 / 残留 logger / 错误命令回显 / 与当前源码不匹配）一律标记
污染并重测，不得参与判定。

设备风险：烧录会 halt MCU，可能把传输中的 SD 卡打成软复位救不回的挂死态
（现象 `SD_IsReady=0`、stat 全 0、瓦片消失）。恢复方式是拔插 SD 卡或整机断电，
**不是代码 bug**，不要去改代码。

## 8. 交付清单

- 最终矩阵：每项判据填 `result` / `execution` / `observed` / `evidence`，
  `observed` 必须是可与 gate 机械比较的布尔值、带单位数值或完整状态链。
- 紧凑证据包（`docs/acceptance-execution-contract.md` §8）：冻结合同（含三个冻结对象）、
  最终矩阵、rerun plan（若复用）、命令输出、决定性原始日志、最终产物、
  外部输入证据。**默认不保留完整构建目录与源码副本。**
- 验收报告：逐判据结论 + 单轮结果分类 + **未观测项如实列出及原因**。
- 问题反馈一次汇总本批已发现项与未覆盖项；新一轮发现注明新观测/回归/前次遗漏，并检查
  范围内同类问题。不得压下真实失败、删减 required 判据或降低门槛来强行“一轮通过”。
- 执行账目：命令阶段、失败分类、修复/状态变化证据、已用/剩余观测配额、rerun plan；
  明确本轮执行哪些观测、复用哪些证据，不把本地校验或失效计划写成硬件授权。
- 若出现 `HARNESS_FAIL`：明确写「这是验证工具问题，不是产品不通过」。
- 回写卡状态 + 看板 §10 追加一行。
- **不 commit**。主会话先把上述包单独提交为 `bundle_commit`，再用后续提交登记
  `FREEZE-INDEX.md`；禁止让包提交记录自身 SHA。
```
