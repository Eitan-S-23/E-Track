# PLAN-OTA-REVIEW-LOG.md — OTA 方案对抗审查日志

## 第一部分:codex 审查意见(18 条,2026-07-22,原文保留)

## codex 审查意见

1. 严重度[高]；问题描述：§1.1 将 W25Q128 写成 8MB，但常见 W25Q128 的容量是 128Mbit（16MB），实际料号、JEDEC ID 与可用地址范围没有锁定；download 和 backup 各 1MB 也没有计入包头、签名、擦除对齐及最坏压缩包开销。容量或型号一旦判断错误，会造成越界写或把资源区当成升级区。；具体修改建议：在方案中固定实际料号、JEDEC ID、容量和地址译码，给出每个槽的起止地址、扇区边界和保留区；CI 与 bootloader 都强制检查 package_size、candidate_size 和 image_size，超限立即拒绝。

2. 严重度[高]；问题描述：download 槽同时承担 BLE/SD 原始 .etu 包暂存和 bspatch/解压后的候选全量镜像，§4.2 还要求从 download 读并写回 download。原地变换会覆盖尚未读取的补丁或密文，差分和全量路径都不能据此保证断电后可重试。；具体修改建议：拆出互不重叠且按擦除扇区对齐的 package_staging、candidate_image、backup_image 三个槽；接收只写 staging，合成只读 staging 并写 candidate，候选通过签名和全量哈希后才允许提交 BCB。

3. 严重度[高]；问题描述：manifest 仅写“4KB×2”，没有精确地址、记录格式、代数号、提交标记、擦写顺序或有效性定义。外部 Flash 的擦除和页编程都不是原子的，backup 或候选清单可能半写却被 boot 当作完整源使用。；具体修改建议：为每个副本定义固定二进制记录，包含 generation、事务 ID、状态、长度、目标哈希、已验证连续偏移和记录 CRC；采用写新副本、读回校验、最后写 commit marker 的 copy-on-write 流程，并保留上一份 confirmed backup 直到新版本确认启动。

4. 严重度[高]；问题描述：BCB 双副本只有“各含 CRC”，没有 generation/sequence、当前副本、事务关联或两份都合法但内容不同时的仲裁规则。掉电发生在影子副本写入中途时，CRC 只能判断损坏，不能判断哪份更新。；具体修改建议：定义带 schema 版本和单调 generation 的 BCB v1；每次写入非活动副本并读回，再以更高 generation 生效，generation 相同或双副本异常时按明确的安全规则进入恢复模式；BCB 必须引用 manifest generation/包哈希，避免状态与数据错配。

5. 严重度[高]；问题描述：状态机只有“应用 download、从 backup 恢复、恢复模式”等粗粒度分支，没有覆盖备份、擦除、逐块拷贝、终验各阶段的持久化检查点。若在擦除内部 app 或复制中途断电，boot 不知道从哪一块续做，也不知道 backup 是否可用。；具体修改建议：补充 RECEIVING、PACKAGE_VERIFIED、CANDIDATE_READY、BACKUP_COPYING、BACKUP_VERIFIED、APP_ERASING、APP_COPYING、APP_VERIFIED、TRIAL、CONFIRMED、ROLLBACK 等状态；记录 source/destination offset、已验证哈希和错误原因，每个扇区/页操作可重复且幂等，只有 backup 验证完成后才擦除 app。

6. 严重度[高]；问题描述：retry_count/max_retry 没有定义递增时机、看门狗触发条件、应用确认点和回滚时限。新 app 可能启动到一半后卡死而没有写入确认，或者在一次失败后被当成正常版本；连续 OTA 还可能覆盖唯一的回滚源。；具体修改建议：boot 每次进入未确认 app 前持久化一次试运行计数并设置 watchdog；app 完成向量表、时钟、存储、通信和主循环自检后写 CONFIRMED；超出次数只从已验证 backup 回滚，backup 在确认前加锁，并规定人工复位、HardFault、看门狗和掉电的统一转移规则。

7. 严重度[高]；问题描述：ext_flash_healthy 只是一个字段，没有定义 JEDEC 读取失败、擦除超时、读回不一致、掉电中断等故障的判定和清除方式。若 QSPI 在备份或读取候选时失效，boot 可能继续执行依赖该 Flash 的分支；B/C 通道的认证、帧格式和错误恢复也没有写清。；具体修改建议：boot 启动时和每次事务前做带超时的容量/读写探测，按错误类型记录并 fail-closed；为 B/C 定义不依赖外部 Flash 的、只接受固定地址和固定长度的已签名 raw recovery 镜像，并将该路径纳入掉电和通信故障测试。

8. 严重度[高]；问题描述：协议规定 payload 不超过 512 字节，同时又把“块”定义为 512 字节且块内还包含 4 字节 offset；8 块窗口实际传输大小因此不明确。ACK 只有 next_offset，没有选择性位图、窗口编号、seq 回显、乱序和重复包语义；丢一个块或丢 ACK 后，发送端无法知道该重传单块还是整窗。；具体修改建议：冻结字节级 wire spec，明确 data_len（是否为 508 字节）、端序和 ACK 字段；采用 session_id + cumulative_ack_base + selective bitmap（或严格的只收连续块策略），接收端只推进连续且 CRC/读回验证通过的 offset，重复块必须幂等并重新 ACK，明确 1 字节 seq 回绕规则。

9. 严重度[高]；问题描述：断点续传只比较包 SHA 的前 8 字节并保存一个 resume_offset，没有说明 manifest 更新的原子时机。掉电发生在 Flash 写成功但 offset 尚未落盘、或窗口内有乱序块时，设备可能错误跳过缺块；重连后也没有会话代次来拒绝旧连接残留帧。；具体修改建议：用完整 package_sha256、package_size、target_sha256、包 UUID 和协议版本建立续传身份；以双记录或日志方式持久化“最后一个连续已验证块”，每次 OTA_QUERY 先重新校验尾部；重连创建新的 session/epoch，旧 seq、旧包和超出窗口的帧一律拒绝，必要时回退到最近检查点。

10. 严重度[中]；问题描述：500ms 超时、3 次重传和 4KB 在途窗口没有考虑 GATT MTU 分片、BLE Write Without Response 的发送配额、UART 缓冲、QSPI 擦除延迟及 115200/460800 切换失败。Flutter 不能假设一次 GATT Write 能承载 512 字节，实际可能先溢出再触发无意义重传。；具体修改建议：连接后协商 MTU，按 MTU-3 分片并在 MCU 端重组；增加 credit/ACK 流控、DMA 或足够大的环形缓冲和在途字节上限，超时按连接参数和 Flash 操作自适应；记录缓冲溢出、CRC 错、重传、断链和降窗计数。

11. 严重度[高]；问题描述：bootloader 被设计为“永不升级”，因此复制逻辑、签名校验、BCB 解析、Flash 驱动、密钥轮换或镜像格式一旦有现场缺陷，B/C 恢复仍然使用同一份坏 boot，无法修复；换 Flash 料号或修复安全漏洞也没有路径。；具体修改建议：采用不可变最小一级启动代码加可签名、可回滚的二级 boot A/B，或明确保留受保护的工厂 USB/SWD 救援路径；定义 boot ABI 和最低 boot 版本，支持公钥轮换/撤销，给 boot 单独做尺寸、越界和故障注入门槛测试。若坚持不可升级，须在发布准入中记录其寿命风险和现场维修方案。

12. 严重度[高]；问题描述：boot 明确不含 LZMA/AES/bspatch，但 full .etu 又允许 LZMA+AES，B/C 恢复模式没有说明接收 raw bin 还是 .etu。这样恢复端可能拿到 boot 无法解析的资产，或者被迫增加复杂解析器，违背“最小 boot”约束。；具体修改建议：为恢复通道单独定义 full-recovery 资产：固定地址、固定长度、未压缩、可选不加密的 App-only 镜像加已签名清单；Cloudflare 和 APP 明确区分普通 OTA 与 recovery 资产，boot 在任何擦写前验证地址边界、签名和目标哈希。

13. 严重度[高]；问题描述：差分包只声明 from_version_code/to_version_code，无法证明补丁的基准字节就是设备当前镜像；相同版本码可能有不同构建、渠道或 GCC/AC5 产物。device_model 也不足以区分硬件修订、Flash 容量、App 起始地址和 boot ABI。；具体修改建议：差分元数据增加 from_image_sha256/from_build_id、to_image_sha256、to_image_size、layout_id、hardware_revision、min_boot_version、patch_algorithm_version 和 channel；云端按旧镜像哈希而非只按版本码选 patch，并始终提供可验证的 full fallback，设备在合成前后都检查这些字段。

14. 严重度[高]；问题描述：CRC、SHA-256、下载 URL 和固件内置 AES 对称密钥只能发现偶然损坏或提供保密，不能证明发布者；BLE、SD、UART 都是可注入包的入口，攻击者可重算裸哈希并重放旧版本。方案也没有安全版本计数器。；具体修改建议：在 boot 固化发布公钥，CI 对规范化 manifest 和目标镜像签名（Ed25519 或 ECDSA-P256）；签名覆盖设备/硬件、布局、版本、安全计数器、包类型、源/目标哈希和算法字段；使用单调 security_version 防回滚，密钥用 key_id 管理并支持轮换/撤销，AES 只作为可选保密层。

15. 严重度[中]；问题描述：.etu 的 envelope_sha256 是否包含自身、fw_header 的 image SHA 是否包含头部、签名覆盖压缩前还是压缩后数据都未定义；字段长度、字节序、对齐、未知版本处理也没有规范。GCC、boot 和 CI 若直接序列化 C struct，可能得到互不兼容的包。；具体修改建议：发布固定的 .etu v1、fw_header v1、BCB v1 字节布局，使用定宽整数和显式小端编码，不直接落盘 C struct；明确 header_size、payload_offset、哈希/签名覆盖范围、nonce、key_id 和 flags，并提供跨工具链的 golden test vectors。

16. 严重度[高]；问题描述：push 到 main 会自动注册候选，workflow_dispatch(publish=true) 可发布正式版本，但方案没有描述 GitHub 环境保护、工作流变更审查、最小权限、短期凭证或签名私钥隔离。被篡改的提交、Action 依赖或长期 Secret 可直接把恶意固件推到 CF。；具体修改建议：正式发布使用受保护 environment 和至少一名独立审批者，GitHub Actions 使用 OIDC 短期、最小权限凭证；固定 Action/工具链摘要，签名私钥放离线/HSM，上传后由独立任务核对 SHA/签名/尺寸并生成构建证明，禁止把密钥或完整包写入日志。

17. 严重度[高]；问题描述：candidate、channel.current_release_id、nightly/formal、回滚和停发之间没有原子状态转换、权限边界或缓存失效规则。旧的 signed URL、R2 可变对象或 Worker 缓存可能让设备拿到已撤销包；回滚又可能与设备端反回滚策略冲突。；具体修改建议：使用不可变、内容寻址的 R2 对象和不可变 release ID，D1 以事务原子晋升 channel；明确 nightly 与 formal 的设备可见范围、分阶段灰度、撤销/kill switch、缓存失效和回滚的安全版本策略，所有 admin 操作记录审计、原因和幂等键。

18. 严重度[中]；问题描述：P5 只列出“升级中断电、坏包、错版本、外部 Flash 故障、回滚”等类别，没有规定在哪个字节/状态切断电源、如何验证 BLE 丢块/丢 ACK/重连、如何证明错误发布无法被接受，也没有可判定的通过标准。；具体修改建议：把每个持久化提交点、每个擦除/页写、每个窗口 ACK 和每次重连列为故障注入点；增加错误设备/硬件修订、篡改签名、重放、降级、CF 越权和缓存旧包测试，要求输出状态轨迹、最终版本/哈希和“可启动或进入恢复模式”的明确验收结果。


---

## 第二部分:审查处置记录(2026-07-22,Claude 逐条验证后落实)

### 审查来源说明
- **A 组(8 条)**:另一 agent 审查,用户转达。已验证 7 条属实(含纠正本方案两处盘点错误),1 条为设计权衡。→ 触发 v1.2 全文重写。
- **B 组(18 条)**:codex 写入本文件的清单(上文)。与 A 组高度重叠,对照 v1.2 盘点出 7 个增量点。→ v1.2.1 吸收。

### A 组处置表(触发 v1.2 重写)
| # | 指控 | 验证 | 处置 |
|---|---|---|---|
| 高1 | nightly 撞 D1 UNIQUE(version_code);worker 拒 isFormalRelease=false | 属实(0003 migration;firmware.ts:157) | nightly 只出 Actions artifact 不注册 CF;正式发布 dispatch 显式 vcode 且校验>现值(§6.1) |
| 高2 | image_sha 自引用;.etu 缺 flags/alg_id/nonce/key_id;内层混合字节序 | 属实 | sha 置零法(§3.1);.etu 头补全字段+payload_crc32(§3.2);内层按文档解析禁 memcpy |
| 高3 | v1 无真实性保证 | 属实(权衡) | §0.2 威胁模型声明;recovery 物理按键≥3s;Ed25519 列 v2 |
| 高4 | EEPROM/QSPI 驱动不能承载 fail-closed | 属实(EEPROM.cpp:46 无 ACK polling;QSPI void+死循环) | P0 强制基建+压测 1000 次验收(§8) |
| 中5 | 正文与 §8 两套矛盾 | 属实 | v1.2 全文合并重写 |
| 中6 | 盘点过期(QSPI 已在 HAL_Init 且自检擦末尾 64KB;admin 固件 UI 已有) | 属实(HAL.cpp:88;[[path]].ts:231-300)——纠正本方案两处错误 | §1 修正;自检区 0x7F0000 永久避让+CONFIG 默认关;CF 缺口重估(§6.2) |
| 中7 | Flash 容量未闭环(网表 16MiB vs 口头 8MB) | 属实(Trace.enet:2169) | JEDEC ID 白名单运行时判定;分区表固定前 8MiB 窗口(§1/§2.2) |
| 中8 | 首次部署未闭环;P2 依赖 P3 打包器 | 属实(linker ORIGIN=0x08000000) | §7 J-Link bootstrap;打包器+vectors 提前 P0(§8) |
| 总 | 建议加 P0 | 采纳 | §8 P0 硬门槛 |

### B 组(codex 18 条)对照处置表(v1.2 已覆盖 11 条,v1.2.1 吸收 7 条)
| # | 主题 | 状态 |
|---|---|---|
| 1 | 容量/JEDEC/槽边界/尺寸上限 | v1.2 已覆盖(§1/§2.2);尺寸上限常量入 P0 契约 |
| 2 | staging/candidate 分槽 | v1.2 已覆盖(§2.2 五槽) |
| 3 | manifest 精确格式/copy-on-write | v1.2 已覆盖(EEPROM BCB 双写替代;槽自描述头入 P0 契约) |
| 4 | BCB generation/仲裁 | v1.2 已覆盖(seq 仲裁+双坏规则,§2.3) |
| 5 | 状态机细粒度检查点 | **v1.2.1 吸收**:APPLYING 态持久化 resume_block 断电续搬;各转移持久化前提写明(§4) |
| 6 | watchdog/试运行/确认点 | **v1.2.1 吸收**:跳 app 前开 IWDG;try-- 先持久化;CONFIRMED=HAL+30s+喂狗(§4) |
| 7 | ext_flash 健康判定 fail-closed | **v1.2.1 吸收**:boot 每次事务前带超时探测(§4);App 侧 JEDEC 失败禁 OTA(§2.2) |
| 8 | BLE wire spec 细节(data_len/端序/回绕/bitmap) | **v1.2.1 吸收**:seq 16bit 回绕明确;字节级 spec 冻结入 P0(§5.1) |
| 9 | 续传身份/会话代次 | **v1.2.1 吸收**:BEGIN 带完整 package_sha256+session_id;残留重验尾部;旧 session 帧丢弃(§5.1) |
| 10 | MTU 分片/流控 | **v1.2.1 吸收**:Flutter 按 MTU-3 分片;MCU 环形缓冲+CTS(§5.1);实测入 P3 |
| 11 | boot 不可升级风险 | 明确接受并留档(§9):家用单台+J-Link 可救;二级 A/B 不做 |
| 12 | recovery 资产格式 | **v1.2.1 吸收**:恢复模式仅收 raw app.bin(固定地址/未压缩/未加密/len+CRC 尾),boot 不解析 .etu(§4) |
| 13 | 差分基准 from_image_sha | **v1.2.1 吸收**:.etu 头 base_sha8 字段;合成前校验当前镜像 SHA 前 8B;ph_ocrc 二重兜底(§3.2/§4) |
| 14 | 签名/安全版本计数器 | 同 A3:v1 威胁模型声明;v2 项(§0.2/§9) |
| 15 | 格式冻结/golden vectors | v1.2 已覆盖(P0 硬门槛,§3.3/§8) |
| 16 | CI 供应链(environment/OIDC/审批) | **v1.2.1 部分吸收**:正式发布 environment `firmware-production`+人工审批(§6.1);OIDC/摘要固定列 v2(§9) |
| 17 | CF 原子晋升/不可变对象/缓存失效 | **v1.2.1 吸收**:P4 缺口加 R2 不可变验证+D1 事务晋升验证(§6.2);灰度列 v2 |
| 18 | 故障注入可判定标准 | **v1.2.1 吸收**:P5 验收=每个持久化提交点注入+状态轨迹+二判输出(§8) |

### 过程备注
- codex relay 通道两次超时未回传(其会话每次 relay 重新初始化陷入全仓库勘察),最终以"写文件"方式交付,结论有效。后续跨 agent 协作规范:任务书首条写明"只读指定文件+结论写指定文件"。
- 本方案作者两处盘点错误由外部审查纠出(QSPI 生产链状态、admin 固件 UI),教训:调用链与旁路实现(Pages Functions/worker 分离)必须查全再下结论。

## 状态
- **PLAN-OTA.md v1.2.1 = 当前生效版本,A/B 两组审查全部闭环(26 条:19 落实、5 已覆盖确认、2 记录性接受)。**
- 下一步:按 §8 进入 P0(等用户开工指令)。

---

## R3 codex 复审结论

### 逐条判定表

| # | 判定 | 复审核对 |
|---|---|---|
| 1 | [部分解决] | JEDEC 白名单、前 8MiB 保守窗口和各槽起址已经明确，容量误判主问题已收敛；但正文仍未给出 staging/candidate/backup 的可用净容量、槽头占用位置，以及 CI、App、boot 三处各自必须执行的上限判断，处置表仅写“入 P0 契约”。 |
| 2 | [已解决] | staging 2MB、candidate 1MB、backup 1MB 已物理分离，接收、解包/合成和回滚源不再原地互相覆盖。 |
| 3 | [部分解决] | EEPROM 双 BCB 的 copy-on-write 改善了控制状态原子性，但“槽自描述镜像头+CRC”没有字节布局、提交标记或准确存放位置；BCB 也没有 backup/recovery 的长度、CRC、generation 或事务 ID，无法仅凭当前正文判定半写槽是否有效。 |
| 4 | [部分解决] | 已增加双块、seq、CRC、写非活动块和读回，基本仲裁方向正确；但缺少 BCB schema 版本、事务关联和 seq 相等/16bit 回绕规则。“过验后 seq+1”的表述还可能被实现成二次非原子改写。 |
| 5 | [处置不当] | §4 声称 APPLYING 持久化 resume_block，但 §2.3 的 64B BCB 没有该字段；擦 app 前后何时提交 APPLYING、检查点代表“待写块”还是“已验块”、断电后是否先重擦当前 4KB 也未定义，ROLLBACK 搬运同样没有进度字段。该状态机目前无法按正文实现。 |
| 6 | [部分解决] | try=3、跳转前持久化递减、IWDG 和 App 30s 后确认已经补齐；但未规定 TEST_BOOT 期间禁止再次发起 OTA，也未明确 backup 在确认前不可覆盖、首次跳新 App 是否先消耗一次 try、确认/回滚时如何同步 cur_vcode。 |
| 7 | [部分解决] | JEDEC 白名单、事务前超时探测、fail-closed 及不依赖外部 Flash 的 UART/J-Link 恢复方向已经加入；仍缺槽有效性契约和错误分级，且 UART 恢复只有 CRC。真实性问题另见第 14 条。 |
| 8 | [部分解决] | payload 已降到 128、seq 扩为 16bit并增加缺失 bitmap；但 ACK 未定义 ack_base/window_id、bitmap 位映射、session 绑定、端序、重复包响应和回绕比较。DATA 含 4B off 后实际 data 上限也未明确，8 帧窗口已不等于 4KB。 |
| 9 | [处置不当] | BEGIN 增加完整 package_sha256 和 session_id 是正确方向，但 BCB/槽头没有持久化 package identity、连续 offset 或 bitmap；BEGIN 中 resume_off 由发送端给出，ACK 又没有设备确认的 durable_resume_off。session_id 不在 DATA/ACK 帧内，“旧 session 帧一律丢弃”无法由当前 wire spec 实现，“重验尾部 CRC”也没有对应的分段期望 CRC 来源。 |
| 10 | [部分解决] | MTU-3 分片、UART 环形缓冲和 CTS 已纳入；仍未定义 ring/聚合缓冲容量、credit/窗口推进条件、Write Without Response 溢出处理、Flash 忙时的反压以及按连接参数自适应的超时。固定 500ms 仍只是估值。 |
| 11 | [已解决] | 风险没有被技术消除，但已经按原建议明确接受单级不可变 boot，并给出“单台家用设备+本机 J-Link 重刷”的现场救援边界和风险留档。该判定仅对当前单设备部署成立；产品化前仍需 boot ABI/min_boot_version。 |
| 12 | [部分解决] | boot 不再解析 .etu，恢复固定写 0x08010000 且未压缩/未加密，解决了 boot 能力冲突；但“raw app.bin”与“尾部 len+CRC32”是两种不同资产定义，CI/CF 也未规定生成、命名和保留该 recovery 资产，CRC-only 的主动伪造风险仍被保留。 |
| 13 | [部分解决] | hw_rev、base_vcode、base_sha8、云端 from_image_sha256 记录以及候选最终 SHA 已降低刷错基版概率；设备端仍只绑定 64bit 前缀，.etu 缺 layout_id、min_boot_version、完整 base hash 和明确 patch format version/channel，无法完整防止同版本跨布局/boot ABI 误刷。 |
| 14 | [处置不当] | “v1 不保证主动伪造”是风险声明，不是关闭措施。物理按键只约束 raw recovery，正常 BLE/SD .etu 仍可被构造为更高 version_code，CRC/SHA/AES-CTR 均不能证明发布者；一旦 APP、CF 或 BLE 输入被控制，boot 会接受自洽的恶意镜像。 |
| 15 | [处置不当] | 固定偏移、小端、禁 struct memcpy 和 golden vectors 已加入，但 fw_header 新定义产生了 SHA/CRC 循环依赖：image SHA 仅将 image_sha256 清零，却仍覆盖 header_crc32；header_crc32 又覆盖实际 image_sha256。按任一普通填充顺序都会使另一个校验失效。BCB 也仍无 schema 版本。 |
| 16 | [部分解决] | firmware-production environment 和人工审批显著降低误发布概率；OIDC 短期凭证、Action/工具链摘要固定、签名私钥隔离、独立制品证明均被推迟，长期 Secret 或工作流依赖被攻破仍可发布。 |
| 17 | [部分解决] | nightly 已与正式渠道隔离，P4 也列入 R2 不可变和 D1 事务验证；但这些仍是待验证项，不是已冻结契约，且缓存失效、幂等、RBAC/双人控制和撤销语义未定义。服务端“回滚”到更低 vcode 与设备 target_vcode>cur_vcode 的拒降级规则直接冲突。 |
| 18 | [部分解决] | P5 已明确持久化点、擦写、ACK、重连、状态轨迹和最终二判，可靠性验收明显改进；仍缺篡改/重放、未授权晋升、旧缓存/旧 URL 和发布并发等安全与 CF 故障用例，而且当前 BCB/BLE 契约缺字段，尚无法枚举真实检查点。 |

### 修订引入的新高危问题

1. [高] fw_header 校验定义不可同时满足。image_sha256 的计算必须同时将 image_sha256 与 header_crc32 置零（或明确排除整个 header），随后填 SHA，最后计算 header_crc32；boot、CI 和 vectors 必须使用完全相同顺序。
2. [高] BCB 字节表没有 resume_block，却要求 APPLYING 断点续搬；backup/recovery 校验元数据也无明确落点。若照正文实现，内部 app 擦除后断电可能无法确定安全续搬或回滚源。应在 BCB 中显式增加 copy_phase、resume_block、backup_len/CRC 或引用带 generation 的槽头，并把提交顺序写成转移表。
3. [高] §6.1 的正式发布顺序是“制 full/patch .etu并自验 → fw_header 回填”。这会让包内目标镜像不是最终回填后的 app.bin，候选校验必然失败或发布资产互不一致。正确顺序应为：构建占位镜像 → 回填并验证最终 fw_header → 以最终 app.bin 生成 full/diff → bspatch 比对最终 app.bin → 上传。
4. [高] BLE 声称旧 session 可丢弃、断点可恢复，但 DATA/ACK 不携带 session_id，持久化布局也没有 package_sha/offset；同时每 8 帧 ACK、4KB 才聚合写 Flash，使“已 ACK”与“已持久化”可能不是同一进度。必须区分 received_ack 与 durable_ack，或只在落盘读回后推进累计 ACK。
5. [高] CF admin 的“回滚”与 MCU 严格拒绝 target_vcode<=cur_vcode 不兼容。它只能阻止尚未升级的设备继续取得坏版，不能救回已升级设备；方案必须定义更高 vcode 的修复版、受控 recovery override，或把后台动作改名为撤回/停发并明确其能力边界。

### 总体判定

**总体判定：不同意。**

理由：v1.2.1 已明显改善分区、试运行和测试框架，但仍有会让升级链无法实现或在断电后失去确定性的结构性问题，尤其是 fw_header 循环校验、BCB 缺失 resume 字段、制包顺序错误和 BLE durable resume 契约缺失；第 14、16、17 条的发布真实性与 CF 供应链风险也仍处于显式接受或延期状态。建议先发布 v1.2.2 修正上述五个新增高危问题，并把 BCB/槽头/BLE ACK 的字段及提交顺序真正冻结，再进入 P0 实现。

---

## R4 codex 复审结论

### R3 五个新高危复核

| # | 判定 | 复核结论 |
|---|---|---|
| 1 | [已消除] | §3.1 已明确计算 image_sha256 时同时将 image_sha256 与 header_crc32 置零，并固定“填普通字段→算 SHA→最后算 header CRC”的顺序；boot、CI、vectors 使用同一算法，不再存在循环依赖。 |
| 2 | [已消除] | §2.3 已把 schema_ver、copy_phase、resume_block、backup_len/CRC/vcode 纳入 64B BCB，定义 resume_block 为“已读回验证的块数”，并规定带 seq+1 的单次副本事务；§4 也在擦 app 前先提交 APPLYING，具备幂等续搬基础。P0 转移表仍须把首次进入 ROLLBACK 明写为 resume_block=0。 |
| 3 | [已消除] | §6.1 已改为先 finalize 最终 fw_header，再以最终 app.bin 生成 full/diff，bspatch 输出逐字节比对同一最终 app.bin，原先包内镜像与发布镜像不一致的问题已消失。 |
| 4 | [已消除] | §5.1 已把 session 放入公共帧头，BEGIN 由 MCU 分配会话，DATA/ACK/END 均绑定该 session；ACK 的 durable_off 只在 staging 写入并读回后推进，bitmap 仅用于其后的选择性补传，已解决旧会话污染和“先 ACK、后落盘”的核心漏洞。 |
| 5 | [已消除] | §6.2 已将后台回滚更名为撤回，并明确只影响尚未升级设备；已升级设备只能通过更高 vcode 修复版救治，与 MCU 拒绝降级规则不再冲突。 |

### 部分解决项复核

| 项目 | 判定 | 复核结论 |
|---|---|---|
| 槽头与半写判定 | [已补齐] | §2.3 给出 32B 槽头、payload 起点、CRC、sha8 和 commit_marker，能够区分未提交槽。P0 契约应明确“先擦槽头扇区、marker 保持擦除态→写 payload/其余头并验读→最后单独写 marker”，禁止复用旧 marker。 |
| 净容量与三处上限 | [已补齐] | §2.2 已给出扣除 4KB 槽头页后的净容量、1.5MB/960KB 上限，并明确 CI、App、boot 三处拒绝点。 |
| BCB seq 回绕 | [已补齐] | §2.3 已给出 int16 差值仲裁和相等取 A，配合每次只生成相邻 seq 的双副本可跨 0xFFFF→0 回绕。P0 vectors 应覆盖回绕与相等场景。 |
| TEST_BOOT 与 backup | [已补齐] | §4 已禁止 TEST_BOOT 期间再次 OTA，并把 backup 从 STAGED 到 CONFIRMED 全程锁定；确认和回滚时也明确同步 cur_vcode。 |
| layout_id/min_boot_ver | [部分补齐] | §3.2 已加入字段，但 §4 的 .etu 接收校验清单仍只列 hw_rev/版本/CRC。P0 必须明确执行 layout_id==本机布局且 min_boot_ver<=当前 boot 版本，否则字段只是未使用元数据。 |
| recovery 资产 | [已补齐] | §5.3 与 §6.1 已统一 recovery-vX.Y.Z.bin 的生成、尾部格式、发布和 UART/recovery 槽使用。J-Link 直刷时必须由脚本剥离尾部 8B，或改刷最终 app.bin，不能把容器尾部无条件写入内部 App 分区边界。 |

### v1 权衡边界确认

- 第 14 条边界清晰：v1 明确只保证偶发损坏、防误刷和防错板，不保证主动伪造；物理按键只约束 raw recovery。该风险是产品决策接受，不应被描述为已经具备固件真实性。
- 第 16 条边界清晰：v1 使用受保护 environment 和人工审批；OIDC、Action 摘要固定等供应链加固明确列为 v2。
- 第 17 条边界清晰：撤回能力已准确限定；R2 不可变与 D1 原子晋升仍是 P4 验收项，灰度发布列为 v2。

### P0 必须固化的剩余约束

1. TEST_BOOT 首次转入 ROLLBACK 时原子写 copy_phase=2、resume_block=0；后续 ROLLBACK 才沿用已持久化进度。
2. 把 layout_id/min_boot_ver 的拒绝规则写入 §4 对应实现契约和 golden vectors。
3. 明确槽头 marker-last 的擦写顺序，以及 MCU 复位发生在 BLE 收包阶段时“持久化会话恢复”或“清除未提交 staging 并从零重传”二选一；不得依据无法复算的尾部 CRC 猜测 durable_off。
4. BLE 活跃窗口必须受实际聚合缓冲容量约束；64bit bitmap 覆盖 7.5KB，而当前环形缓冲下限是 4KB，P0 需给出允许的最大在途段数和溢出处理。
5. CI 明确上一正式版最终 raw bin 的来源（直接保留，或从 recovery 资产验尾后剥离），并明确 J-Link recovery 脚本不写尾部 8B。

### 总体判定

**总体判定：同意收敛。**

理由：R3 指出的五个新增高危均已从数据结构、状态转换或发布语义上得到实质修复，未发现新的架构级高危问题；其余缺口已收敛为 P0 字节契约和边界处理细节，不需要再次调整总体架构。该结论表示可以进入 P0 契约冻结与实现，不等同于构建或真机验收通过；上述五项 P0 约束遗漏时应重新阻断 P1/P2。


---

## R5:C 组审查(2026-07-22,另一 agent,用户转达;10 条全采纳 → v1.2.3)

关键事实验证(Claude 逐条核实):
- C1 向量表 0x20C:**实锤**(X-Track.map:10976 `.isr_vector 0x08000000 0x20c`)→ fw_header 迁 0x400+专用链接段+ASSERT
- C2 SystemInit 覆盖 VTOR:**实锤**(system_at32f435_437.c:100,VECT_TAB_OFFSET=0)→ App 侧 OFFSET=0x10000+boot→App 交接冻结(禁中断/停 SysTick/清 pending/VTOR/MSP/跳转)
- C3 内层头 40B 非 36B(3B ABI 填充+sizeof 直写):属实 → etu_pack.py 规范化重写 40B,ph_*crc 大端补记
- C4 CF 单资产模型:属实(0003:14 单组字段;firmware.ts:100 单地址)→ P4 新增 firmware_release_assets 迁移+latest 资产数组+recovery 不自动分发
- C5 设备身份缺失:属实(ota_upgrade_page.dart:593 硬编码)→ BLE GET_INFO 命令+latest currentImageSha 参数+基准不符退 full
- C6 CTS 物理不存在:**实锤**(网表 XY-MBO35A Pin5/Pin6 均接 GND,仅 BT_RX/BT_TX 连 MCU)→ 协议级 credit 窗口(window_segs=min(缓冲/120,64)),删除 CTS 依赖
- C7 文本协议无分流:属实(Bluetooth.cpp:20 全字节进文本解析;HAL_Bluetooth.cpp:67 200ms 周期上行)→ A5 5A demux+OTA 会话静默
- C8 layout/min_boot 未闭环+recovery 绕过校验:属实 → fw_header 增 layout_id/min_boot_ver 字段(pad 区);.etu 接收清单+boot 擦前统一校验(SHA/hw/layout/boot ABI/向量范围);recovery 写完后仍走统一校验
- C9 搬运歧义:属实 → 逐块擦写读回、重入不整擦、ROLLBACK 终验、首跳耗 try(共 3 次)
- C10 LZMA 形态未冻结:属实(interface.c:294 需 5B props+8B len)→ 全量=LZMA-Alone 形态+字典 64KB 上限+candidate 净容量溢出钳制

状态:v1.2.3 发布,待 codex R6 交叉复审。

---

## R6 codex 交叉复审

### C 组 10 条逐项核对

| C# | 判定 | 与 R4 的兼容性及复核意见 |
|---|---|---|
| C1 向量表/头位置 | [部分到位] | 将 fw_header 迁到 app+0x400、增加专用链接段和向量表 SIZEOF 断言是正确修复，不与 R4 的双零校验冲突；但 §2.1 仍写“fw_header @app+0x200”，与 §3.1、版本摘要直接矛盾。字节级地址存在两套答案，必须统一为 0x400。 |
| C2 SystemInit/VTOR | [基本到位] | App 的 VECT_TAB_OFFSET=0x10000、boot 交接时设置 VTOR/MSP 并清理 SysTick/NVIC，方向正确且补强 R4。P1 契约还必须保证 boot 工程自身 OFFSET=0、App 工程才是 0x10000，并明确跳转前恢复 PRIMASK=0、BASEPRI=0、FAULTMASK=0；否则若“禁中断”用全局屏蔽实现，App 可能永久不响应中断。 |
| C3 40B 内层头 | [部分到位] | 从宿主 ABI struct 改为规范化 40B 显式序列化是必要修复，外层 .etu 64B 契约不受影响；当前正文仍缺 40B 每个字段的精确 offset、hcrc 覆盖范围/清零规则和 LZMA 流起点的表格。“CRC 按规范化后字节重算”也应区分头 CRC 与 old/new 内容 CRC，须由 P0 vectors 锁死。 |
| C4 CF 多资产 | [设计到位] | 独立 assets 表、full/patch/recovery 分类、recovery 不自动分发及 full fallback 与 R4 撤回语义兼容。P4 仍需定义多 patch 唯一键、旧单资产数据回填、release 的 draft/ready 状态，以及“至少 full 完整且所有 R2 digest 验证后才可原子晋升渠道”，避免半注册 release 对外可见。 |
| C5 GET_INFO 身份链 | [到位] | model/hw/layout/boot/vcode/完整 image SHA 由设备提供，再由 CF 精确匹配 patch、否则退 full，闭合了差分基准来源，与 R4 的设备端最终校验形成双层防错。P0 只需补齐 INFO 各整数宽度、端序、session=0 规则及 CF 参数的规范编码。 |
| C6 CTS/credit | [部分到位] | 用协议 credit 替代不存在的硬件 CTS 是正确方向，但 §1 的 BLE 事实表仍写“CTS 流控”，必须删除，P3 禁止启用 UART 硬件流控。credit 的持久化记录和窗口活性仍存在高危缺口，见下文。 |
| C7 二进制/文本 demux | [到位] | A5 5A 分流、OTA 会话静默并暂停周期文本上行，解决了二进制帧被 TinyBTPlus 消费和双协议争用问题，不与 R4 冲突。P3 测试需覆盖半个帧头、CRC 错后重同步、ABORT/超时恢复文本通道。 |
| C8 layout/recovery 校验 | [部分到位] | fw_header 与 .etu 均加入 layout/min_boot，§3.1/§4 也列出统一校验和向量范围，方向正确；但 §5.3 仍写 boot“只验尾部 len/CRC”，与 §4“写完后仍走 fw_header 全项校验”冲突。§3.1 又称擦 App 前统一校验，而 §4 的 STAGED 分支擦前只列槽头 CRC，候选 fw_header 全项检查需明确前置。 |
| C9 搬运重入/试启动 | [到位] | APPLYING/ROLLBACK 均逐 4KB 擦写读回、重入不整擦、ROLLBACK 从 resume=0 原子起步并终验，首跳也先消耗一次 try，完整落实 R4 的断电和试运行要求。 |
| C10 LZMA 形态/上限 | [部分到位] | LZMA-Alone 5B+u64+流、64KB 字典上限和逐次 offset+len 钳制消除了格式及越界歧义；但 64KB 字典没有与现有 82.96% RAM 占用、约 20KB bspatch 堆、4KB BLE 缓冲及解码器状态形成可执行的峰值预算，存在新的可行性高危。 |

### 五处大改专项结论

| 大改 | 结论 |
|---|---|
| fw_header 迁 0x400 | 技术选择正确，但 §2.1 残留 0x200 使当前文档仍不具备唯一实现含义，暂不能判为闭环。 |
| App VECT_TAB_OFFSET=0x10000 | 不与 R4 冲突，地址也满足对齐；需把 boot/App 两套构建配置隔离及全局中断屏蔽恢复写进 P1 契约。 |
| credit 窗口替代 CTS | 方向正确，但持久化会话布局不存在，且必须定义“credits 用尽前强制落盘并 ACK”的 flush 规则，否则自然沿用 4KB 整块聚合时会出现 34×120=4080<4096 的无进展窗口。 |
| 40B 规范化内层头 | 不引入架构冲突，反而去除了 ABI 依赖；在精确 offset/CRC 覆盖和 golden vectors 完成前仍只是格式草案。 |
| CF 多资产模型 | 未发现新的架构级高危；必须以 release-ready 原子门槛、资产唯一约束和 full 必备规则防止半发布。 |

### 新增或尚未消除的高危问题

1. [高] **fw_header 地址自相矛盾**：§2.1 是核心内存图却仍指定 app+0x200，§3.1 指定 app+0x400。linker、CI 注入器、boot 解析器和 recovery 校验只要有一处按旧值实现，就会覆盖向量或读错头。全文必须只保留 0x400，并给四方共享常量。
2. [高] **BLE durable resume 没有可落盘的数据结构**：§5.1 声称“BCB 会话记录、staging 槽头记 package_sha+durable_off”，但 §2.3 的 64B BCB没有这些字段，32B 槽头也只有 sha8、无完整 package SHA 和 durable_off。durable_off 每 4KB 更新还不能反复原地改写 NOR 字段。应在预留的 4KB 槽头页定义独立、掉电安全的接收日志，例如完整 SHA/total_len 加只做 1→0 的块位图或双记录 journal；无合法日志必须从零重传。
3. [高] **credit 窗口缺少保证前进的落盘规则**：window_segs=34 时最多接收 4080B，而 ACK 只确认已落盘数据。若实现继续等待完整 4KB 才写，发送端因 34 段全在途而不能发送补足 16B，双方永久等待。契约必须规定按窗口满/超时刷写不足 4KB 的连续数据，或把缓冲与窗口提高到至少 ceil(4096/120)=35 段，并明确扇区预擦和短尾段规则。
4. [高] **64KB LZMA 字典的 RAM 可行性未闭环**：按正文 384KB×(1-82.96%) 仅约 65KB 余量，64KB 字典本身已接近耗尽，尚未计约 20KB bspatch、解码状态、栈和 I/O 缓冲。P0/P2 前必须给出分阶段峰值内存表和真实分配来源；若复用 LVGL/既有静态缓冲，要写明暂停、释放、恢复顺序，否则应降低字典上限。
5. [高] **recovery 校验仍有互斥指令**：§4 要求 recovery 写后执行 fw_header CRC/SHA/hw/layout/min_boot/向量校验，§5.3 却写“只验尾部 len/CRC”。必须删去“只验”，并明确尾部校验是传输容器校验、fw_header 全项校验是启动前强制校验；同时明确物理 recovery 是否允许版本降级，不能一边宣称“不绕过防旧版”一边没有版本比较规则。
6. [高] **boot→App 全局中断状态未冻结**：如果“禁用所有已启用中断”包含 __disable_irq 而跳转前不恢复 PRIMASK，SystemInit 修正 VTOR 后 App 仍可能无中断运行。契约应明确 NVIC ICER/ICPR 清理与 PRIMASK/BASEPRI/FAULTMASK/CONTROL 的交接值，并对 boot=offset0、App=offset0x10000 分别做链接/启动断言。

### 总体判定

**总体判定：不同意。**

理由：C 组十条在方向上均与 R4 已认可的分区、BCB、校验和发布模型兼容，C4/C5/C7/C9 已形成实质闭环；但 v1.2.3 同时存在两个明确的正文矛盾（fw_header 0x200/0x400、recovery 只验 CRC/统一校验）、一个无法由现有布局实现的 BLE 持久化声明、credit 窗口活性缺口以及未闭环的 64KB 字典 RAM 预算。这些问题会分别导致向量覆盖/头解析错误、恢复路径绕检、断点状态误判、传输死锁或 OTA 无法分配内存，不能留到普通实现细节阶段。修正上述六项并补齐 40B 头与 CF release-ready 契约后，可继续沿用 R4 架构，无需推倒重来。


---

## R6 处置记录(2026-07-23,Claude → v1.2.4)

六条高危全部采纳修复:
1. fw_header 0x200/0x400 矛盾 → §2.1 统一 0x400,新增 FW_HEADER_OFFSET 四方共享常量(linker/CI/boot/recovery 唯一来源);§1 BLE 行 CTS 残留同步删除
2. BLE durable resume 无落盘结构 → §2.3 新增 staging 接收日志字节级定义:magic+package_sha256(32B)+total_len+journal_crc+512B 块位图(NOR 1→0 免擦除特性,4KB/位)+乒乓 journal 记短尾;BCB 明确不承载会话状态;无合法日志从零重传
3. credit 窗口活性死锁(34×120=4080<4096)→ 窗口下限 35 段+三条件强制落盘(凑满 4KB/窗口收齐短尾/500ms 超时),QSPI 预擦+256B 页续写
4. 64KB 字典 RAM 不可行 → 降 16KB(CI -dict 16);§9 新增升级态峰值预算表:16+16+20+4+4≈60KB ≤ 65KB 常态余量,升级独占页释放量作安全垫;P2 实测回填,超限降 8KB
5. recovery 校验互斥表述 → §5.3 两层职责分离(尾部 len/CRC=传输容器校验;启动前强制 fw_header 全项);物理 recovery 允许降级显式声明(防旧版保证范围=OTA 通道)
6. boot→App 中断交接 → 字级冻结:ICER/ICPR 全清(不用 PRIMASK 屏蔽跳转)+SysTick 停+PRIMASK/BASEPRI/FAULTMASK/CONTROL=0+VTOR/MSP/跳转;boot(OFFSET=0)与 App(OFFSET=0x10000)双工程链接 ASSERT+启动自检

附带:CF release-ready 原子门槛(draft/ready 状态+full 必备+R2 digest 全验+渠道只晋升 ready)、资产唯一键 (release_id,kind,base_image_sha256)、40B 内层头精确 offset 表列入 P0 契约。

状态:v1.2.4 发布,待 codex R7 复审。

---

## R7 codex 复审

### R6 六项逐条核对

| # | 判定 | 复核结论 |
|---|---|---|
| 1. fw_header 0x400 统一 | [已消除] | §2.1 与 §3.1 已统一为 app+0x400，并明确 FW_HEADER_OFFSET 是 linker、CI 注入器、boot 解析和 recovery 校验的唯一共享常量；向量表 SIZEOF 断言仍保留，未发现地址回退或与 R4 双零算法冲突。 |
| 2. staging 持久化接收日志 | [未消除] | 已正确把会话状态移出 64B BCB，并采用完整 package SHA 与 NOR 1→0 块位图；但当前所谓“字节级”布局仍缺 ETSL 与 ETRJ 在同一 4KB 页内的非重叠 offset，journal_crc32 对固定字段/位图的覆盖范围也未定义。更严重的是 2×8B 乒乓记录无法在同一 NOR 擦除扇区内支持多次任意数值更新，第三次更新前若擦除会同时毁掉固定头和块位图。 |
| 3. credit 活性 | [未消除] | 三个强制刷写条件和“只 ACK 已写入读回数据”方向正确；但公式 window_segs=min(buffer/120,64) 在正文仍只保证 4KB 缓冲时得到 34，不可能同时满足“下限 35”。若按 35×120 配置又至少需要 4200B，且第 35 段会跨 4KB 边界，durable_off 前移后 bitmap 的段基准未定义。 |
| 4. LZMA/RAM | [已消除] | 字典从 64KB 降为 16KB，并给出 16+16+20+4+4≈60KB、常态余量约 65KB、页面释放安全垫、8KB fallback 和 P2 水位实测门槛。该项已从架构不可行收敛为必须实测的资源风险，未引入新的高危。 |
| 5. recovery 两层校验/降级 | [部分消除] | §5.3 已清楚区分尾部 len/CRC 的传输校验与 fw_header 的启动前校验，并明确物理 recovery 可降级、J-Link 必须剥尾；但 §4 仍写 recovery“不绕过防错板/防旧版”，与物理降级例外冲突。应改为“不绕过完整性、防错板与 boot ABI；vcode 按 §5.3 例外处理”。 |
| 6. boot→App 中断交接 | [已消除] | 已冻结 NVIC ICER/ICPR、SysTick、PRIMASK/BASEPRI/FAULTMASK/CONTROL、VTOR/MSP 以及 boot/App 两工程 OFFSET/ORIGIN 断言，原先携带 PRIMASK=1 跳入 App 的风险已消除。P1 实现仍应补清 PENDST/PENDSV 并在 VTOR/CONTROL/MSP 切换处使用 DSB/ISB，但这不构成新的架构级高危。 |

### 新高危与新增一致性问题

1. [高] **接收日志的 NOR 更新模型仍不可实现**。block_bitmap 可安全做 1→0，但可变的 short-tail durable 字节数不能靠仅两个 8B 槽反复乒乓；NOR 无法把旧记录恢复为 0xFF，擦除又会清掉整页。建议二选一：只把 4KB 整块进度作为跨复位持久化状态，部分块复位后回退重传；或在剩余槽头页定义带 seq/len/CRC/commit 的 append-only 记录数组，并规定耗尽策略。journal_crc 必须明确只覆盖不可变前缀，位图和每条记录分别校验。
2. [高] **credit 下限与缓冲容量自相矛盾**。4KB/120 向下取整只能给 34 段，不能宣告 35。最小改法是规定 DATA 不得跨 4KB：每块固定为 34×120B+1×16B，共 35 段但总字节仍为 4096，window credit 按实际待收字节而不是 buffer/120 计算；另一方案是把聚合缓冲明确增至至少 4200B，并定义跨块段在 ACK bitmap 中的绝对索引。未冻结其中一种前，丢包/补传和 durable_off 无唯一实现。
3. [高] **ETSL 与 ETRJ 可能占用同一槽头起点**。通用槽头声明 ETSL 位于各槽起始，接收日志又以 ETRJ 描述“staging 槽头页内”但没有 offset。P0 必须给完整 0x000-0xFFF 表，例如 ETSL@0x000、ETRJ 固定头@0x020、位图及 append journal 后续排列；commit_marker 仍只能在完整包终验后最后写。
4. [中] **CF 资产唯一键对 NULL 未必形成唯一性**。若 full/recovery 的 base_image_sha256 为 NULL，D1/SQLite 的 UNIQUE(release_id,kind,base_image_sha256) 可容纳多行 NULL，无法保证每个 release 只有一个 full/recovery。应使用 partial unique index，或令非 patch 的 base key 为非 NULL 固定哨兵并加 CHECK；release-ready 事务还应要求“恰好一个 full”。
5. [中] **recovery 版本语义仍有一处旧文字**。§5.3 已是明确规则，应同步删改 §4 的“不绕过防旧版”，避免 boot 实现者错误拒绝真正用于救砖的旧黄金镜像。
6. [中] **中断交接还应处理系统 pending**。ICPR 只处理外部 IRQ，P1 契约应额外清 SCB ICSR 的 PENDST/PENDSV，并在 VTOR、CONTROL、MSP 修改后执行必要的 DSB/ISB，防止旧 SysTick/PendSV 状态在 App 首跳时触发。

### 未引入高危的修订

- 0x400 共享常量、16KB LZMA 字典与分阶段内存预算、物理 recovery 降级边界、中断寄存器交接以及 CF release-ready 原子门槛均与 R4/R6 的总体架构兼容。
- 40B 内层头继续留在 P0 以精确 offset、CRC 覆盖和 golden vectors 冻结是可接受的前置门槛，不因本轮六项修订产生新冲突。
- RAM 预算目前只有约 5KB 常态余量，但方案已给页面释放安全垫、分配来源回填、实测水位和 8KB 字典 fallback，可在 P2 作为硬验收而非再次改架构。

### 总体判定

**总体判定：不同意。**

理由：0x400、RAM 和中断交接三项已闭环，recovery 只需同步一处文案；但 BLE 接收日志的可变进度无法由“位图+2×8B 乒乓”在单个 NOR 扇区内持续更新，credit 的 35 段下限又与 4KB 缓冲及 120B 分段公式直接矛盾。这两项会导致断点状态不可恢复或传输协议没有唯一、可保证前进的实现，仍属于 P3 前的阻断性高危。修正槽头完整 offset/CRC/journal 方案并冻结一种 4KB 对齐的分段策略后，可继续沿用现有架构，无需推倒 R4 已认可部分。


---

## R7 处置记录(2026-07-23,v1.2.5)

| R7# | 处置 |
|---|---|
| 1 接收日志 NOR 模型不可实现 | **采纳建议一(整块进度)**:去乒乓 journal;跨复位持久化仅整 4KB 块位图(1→0 单调),不足块断电即整块重传(≤4KB 代价);槽头页偏移表冻结 ETSL@0x000(32B)/保留@0x020/ETRJ 固定头@0x040(44B,hdr_crc 仅覆盖 40B 不可变前缀)/bitmap@0x070(64B,无 CRC,写后读回);新会话才整页擦除(§2.3) |
| 2 credit 35 段 vs 4KB 矛盾 | **冻结 128B 分段**(优于 34×120+16 异形段):4096/128=32 整除,段不跨块,off 128 对齐;credit=当前块未确认段(≤32);ACK 载荷 block_bitmap 改 u32=当前块 32 段位图;活性=收齐落盘 ACK+500ms 位图重发(§5.1) |
| 3 ETSL/ETRJ 同页冲突 | 同 #1 偏移表消除(§2.3) |
| 4 CF 唯一键 NULL 陷阱 | base_image_sha256 NOT NULL+非 patch 哨兵空串+CHECK(kind='patch'↔≠'')+UNIQUE 三列;ready 事务改"恰好一个 full"(§6.2) |
| 5 §4 recovery 旧文字 | 已同步:"不绕过完整性/防错板/boot ABI;vcode 按 §5.3 物理例外"(§4) |
| 6 PENDST/PENDSV+DSB/ISB | v1.2.4 交接段已含(PENDSTCLR/PENDSVCLR+两处 DSB/ISB),无需再改;R7 亦确认不构成架构级高危 |

附带一致性清理:INFO.max_window_segs 注明恒 32(扩展预留);全文 120B/35 段/乒乓仅存于消除性描述。

状态:v1.2.5 发布,待 codex R8 复审。

---

## R8 codex 复审

### 四处最小范围核对

| # | 判定 | 复核结论 |
|---|---|---|
| 1. staging 纯整块位图日志 | [已解决] | §2.3 已给出互不重叠的完整页内布局：ETSL@0x000、ETRJ@0x040、bitmap@0x070；ETRJ 的 hdr_crc32 只覆盖 40B 不可变前缀，bitmap 仅做 NOR 1→0 并在每次清位后读回。跨复位只承诺完整 4KB 块，未完成块整体重传，已彻底移除无法反复更新的 short-tail/乒乓 journal。最终 payload CRC/包 SHA 仍负责发现位图或数据的潜在静默错误。 |
| 2. 128B×32 credit/ACK | [已解决] | DATA 固定 128B、每块恰 32 段、窗口只覆盖当前块，4KB 缓冲与 credit 精确相等；ACK 用 durable_off 表示已落盘整块、u32 block_bitmap 表示当前块 RAM 接收状态，500ms 仅重发 bitmap 促使补缺，不再提前确认未落盘数据。原 34×120=4080 的无进展窗口和跨块段歧义均已消失。 |
| 3. CF 资产唯一约束 | [已解决] | base_image_sha256 改为 NOT NULL，非 patch 使用空串哨兵，并以 CHECK 约束 patch/非 patch 取值，再配合 (release_id,kind,base_image_sha256) 唯一键，已避开 SQLite NULL 不参与去重的问题；release-ready 事务另要求恰好一个 full 且全部资产 digest 验证通过，半发布和多 full 均被阻断。 |
| 4. recovery 版本例外 | [已解决] | §4 已与 §5.3 一致：recovery 仍强制执行完整性、hw_rev、layout、min_boot 和向量校验，但物理在场恢复明确不比较 vcode；OTA 通道继续严格拒绝降级。两层校验职责与救砖例外不再互相冲突。 |

### 新高危检查

未发现 v1.2.5 引入新的架构级高危。纯整块位图只牺牲最多 4KB 的重传量，不削弱最终包校验；128B 分段不会改变外层 .etu、BCB 或候选搬运契约；CF 哨兵值只改变资产索引规范；recovery 例外仍受物理按键和 fw_header 全项校验约束。

### P0/P3 实现验收项

1. staging 某块写入中掉电而持久位仍为 1 时，重传前必须重新擦除该 4KB 数据块；只有写完、读回通过后才允许清对应持久位。
2. ETSL 的 payload_len/payload_crc 等字段应先写并读回，commit_marker 仍最后单独写；“随 commit_marker 填写”不得实现成一次同时提交。
3. DATA 包尾段仍应保持 off 为 128 对齐，仅 data_len 可以短于 128；§5.1 的“off 必须 128 对齐（尾段除外）”建议改成“off 始终对齐，尾段仅长度例外”。
4. ACK 丢失后收到 off<durable_off 的重复 DATA 时，MCU 不得重写已提交块，只需返回当前 durable_off；重连后按既定策略丢弃未落盘 RAM bitmap并从当前整块重传。
5. D1 迁移用实际 SQL 表达 CHECK 等价关系，并用测试证明同一 release 无法插入第二个 full、同基版第二个 patch，且缺 full 的 release 无法置 ready。

### 总体判定

**总体判定：同意收敛。**

理由：R7 剩余的两个阻断项已经分别收敛为可由 NOR 单调位图实现的整块断点模型和严格整除的单块 credit 协议，两处小改也正确关闭了 CF NULL 唯一性与 recovery 文案冲突。当前剩余事项均是 P0/P3 的实现顺序、边界测试和措辞精化，不再要求修改总体架构；可以进入 P0 契约冻结，构建与真机结果仍按既定阶段验收。


---

## 最终状态(2026-07-23)

**R8 总体判定:同意收敛 → PLAN-OTA.md 冻结为 v1.3(P0 契约基线)。**

- 八轮审查全程:自审 12 → A 组 8(7 实 1 权衡)→ codex 18 → R3 复审 5 高危 → R4 同意 → C 组 10(全实)→ R6 复审 6 高危 → R7 复审 6 项 → R8 同意收敛。
- R8 附带 5 条实现验收项已固化:重传块先擦+读回后清位(§2.3)、ETSL 先写校验+commit_marker 最后写(§2.3)、尾段 off 对齐仅长度短(§5.1)、重复 DATA 幂等(§5.1)、D1 SQL 验证恰一 full(§8-P4)。
- 边界声明:"同意收敛"=方案可进入 P0 契约冻结,不代表实现/生产发布已验证(codex 未跑构建与真机);v1 不防主动伪造为已接受产品风险。
- 下一步:P0 开工(五契约文档+etu_pack/unpack+golden vectors+EEPROM/QSPI 安全驱动+JEDEC 判定+自检 CONFIG 化)。
