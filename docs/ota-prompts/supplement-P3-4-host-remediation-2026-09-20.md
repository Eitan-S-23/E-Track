# P3-4 Host 整改执行提示词（2026-09-20）

下一步由原 P3-4 实现 agent 完成本批代码、host 自测和实验资产整改。交付后由主会话集中复核，再裁定具体真机方案与累计操作额度；现在不进入真机。

你负责继续实现，不负责给本卡签独立验收 PASS。请实际修改、运行开发自测并交付证据，不要只回复计划或只改报告措辞。

1. 工作位置、范围与前置资料

唯一活动 worktree：
D:\github\my\E-Track\.cache\worktrees\p3-4-link-stats

先核对当前分支、源码和已有修改，保留原认领及他人改动。遵守该 worktree 的 AGENTS.md、验收执行合同 §7.3、P3-4 Spec 和 OTA-XC-BLE-PERFORMANCE/TUNING。本提示词只限定本批整改，不修改冻结协议、门槛或历史验收结论。

只读参考：
D:\github\my\E-Track\.cache\p3-4-host-audit-20260919\REVIEW.md
D:\github\my\E-Track\docs\ota-exec-notes\P3-4-1MiB-feasibility-2026-09-20.md
D:\github\my\E-Track\.cache\p3-4-size-check-20260920\proof\
以及你 worktree 内的 P3-4-delivery-2026-09-19.md、P3-4-baud-experiment-2026-09-19.md 和相关准入文档。

所有新增输出必须先预检，放在本 worktree 内的专用 .cache 子目录；包括构建、日志、截图、临时文件、harness、缓存。命令显式指定 workdir，使用 cmd.exe，检查子脚本是否启动会向外写缓存的 PowerShell。

主工作树中的上述证据是只读输入，不是额外可写根。不要直接运行原 reproduce.py/size_proof.py，它们把输出锁定在主工作树。通常引用已完成证据即可；确需移植时，将工具放到本 worktree，显式绑定只读输入和本地输出，保留路径守卫，不通过删除守卫绕过边界。

本批允许修改实验 HAL、必要的实验控制/host 测试及 P3-4 文档；优先集中在 USER/HAL/HAL_Bluetooth.cpp、HAL_Config.h 和实验专用目录。不要改共享 Bluetooth 库、Boot 校验、OTA 协议、staging/BCB 或 Flutter 产品代码来规避问题。确需扩围先说明依据。

本批不连接设备、不发送真实 AT、不运行 J-Link、不烧录、不安装、不 OTA，不 commit/push、dispatch、release/deploy 或远端删除。不得借 Flutter 开发预授权提交固件改动；历史硬件额度不沿用。

2. 先隔离实验构型的非预期 UART TX

采用实验 HAL 局部隔离，生产开关默认关闭，生产行为保持一致。

- bt_text_sink() 的生产路径保留 bt.encode()；实验路径不再将模块文本送入会触发回显的 TinyBTPlus。保留原始 RX 观测、OTA demux 和二进制接收，不关闭整个接收服务。
- 在 HAL::BT_SetName() 内抑制实验构型的自动改名，覆盖所有调用者；在 HAL::BT_printf() 内抑制实验构型的遗留文本输出，覆盖 EEPROM 文本出口。
- 保留关闭周期性 X-Trace 的处理；实验开关与透明串口桥同时启用时编译期拒绝，保留原有 RTT 调试命令互斥约束。
- 保留合法 OTA 帧出口和明确执行的实验 AT 命令，不改生产协议。

盘点全部 Bluetooth UART TX 入口，不只检查 BT_Update。注入“+UART: 5\r\n”和“+READY\r\n”时，原始 RX 必须完整记录，UART TX 必须为空；显式发送 AT 时，TX 只能包含该命令及规定行尾。旧实现会丢掉开头的“+”再回显，文档不要继续称“原样回显”。

3. 修复 AT 观测和命令执行

原始观测采用显式长度的字节缓冲，不再使用 %s 输出收到的数据。

- 用有界接收缓冲和封存记录，记录序号、采集时 MCU baud、epoch、长度和 HEX 字节。封存后不能继续拼接新接收数据。
- 一条完整记录编码后以一次 SEGGER_RTT_Write 输出，使用 NO_BLOCK_SKIP，只有返回值等于完整记录长度才算成功。RTT 拒写时保留待输出记录；不要依赖 SEGGER_RTT_printf 的返回值判断末次写入是否成功。
- 核对记录最大长度小于实际 RTT 环容量。队列/接收缓冲溢出必须有准确且不会因日志拥塞丢失的计数或状态，不阻塞主循环等主机读取。存在丢失的观测不能充当完整应答证据。
- OTA active 期间不输出 ATRSP；跨状态边界的记录保留原始代次或明确作废，不能混入下一轮。

命令必须整行校验后才执行：

- 超长输入整条拒绝，并持续消费到行尾；禁止发送截断前缀。命令中的 NUL/非法控制字符整行拒绝，但 RX 观测仍须支持任意字节。
- busy 时继续有界消费并丢弃 RTT down 输入，清除本地半行和待执行命令；不能直接 return 留待空闲补执行。
- 引入控制 epoch，接到真实 OTA 会话获取/释放边界，并结合 feed/pump 状态检查，不能只靠 200ms 轮询发现切换。
- 主机先查询状态，再携当前 epoch 发副作用命令；执行前再次确认 epoch、session active 和 isr_active，防止检查后失去空闲所有权仍发送。
- 可采用 status、at <epoch> <command>、uart <epoch> <rate> 等接口；函数/命令命名可调整，隔离语义不能改变。
- 主机 RTT 写入辅助程序按实际 down descriptor 的容量及 WrOff/RdOff 分段写入，不能假定一行能放进 16 字节环。

必须覆盖：
RX“2B 55 41 52 54 3A 00 35 0D 0A”记录为 len=10、HEX=2b554152543a00350d0a；
RTT 拒写一次后恢复，同一记录只完整输出一次；
busy 排队命令、跨 busy 半行和旧 epoch 命令均零 UART TX；
超长行拒绝后下一条合法命令正常执行。

4. 实现“一份实验固件切换四档 MCU UART”

通过独立 RTT 控制通道，只调整 MCU UART 至 115200、230400、460800、921600；不发送 AT+UART、不复位模块、不重新烧录。

推荐顺序：
检查速率白名单、epoch 和 OTA 空闲所有权；
有界等待 UART 最后一个字节实际发送完成；
在必要的短临界区内停接收/中断、清除旧 RX 残留并重新配置 UART；
恢复原 ISR hook，返回实际 MCU 速率。

本项目 HardwareSerial::flush() 清的是 RX，不能用于等待 TX 完成；write() 等到数据寄存器可写也不等于最后一位发完。使用 getUSART() 和 SDK 的实际发送完成标志，超时不切换。

旧速率记录先封存，保留旧 baud/epoch，无法保存则报告丢失。仅在确认 OTA 空闲后重置 demux 残留，不重新初始化整个 OTA session，不改变 durable staging。返回 MCU 配置成功不代表模块已切换。

覆盖非法速率、busy、旧 epoch、TX 完成超时、成功切换及 ISR/RX 恢复；证明 uart 命令不产生模块 AT 流量。旧四档固定速率 BIN 保留为历史证据，不再作为逐档烧录入口。

5. 用真实控制逻辑重写切速与恢复操作单

分开记录“在哪个 MCU 速率验证了通信”和“模块查询报告的配置值”。模块在旧速率报告目标配置，不证明目标速率已能通信。

实现并测试 KNOWN(old)、PENDING(old,target)、UNKNOWN 状态：

- 在已确认的 old 上只发送一次设置命令，进入 PENDING；无应答不能假定成功。
- 有界探测 old/target，每个速率最多一组 AT+UART?、AT+VER?，每条查询沿用 3 秒等待上限；应答绑定 baud、epoch、记录序号和本次查询窗口，排除旧日志。
- target 上确认通信并核对配置后，才能进入 KNOWN(target)。
- 仅 old 可通信但报告 target 配置时，按可能延迟生效处理；重新确认 old 通信后才允许模块重启，随后再次有界探测。
- 仅 old 可通信且仍报告 old，记录设置未生效，不自动反复设置。
- 两侧均无有效应答或证据矛盾则进入 UNKNOWN，停止设置和下一档实验，不凭沉默判定“不支持”或直接归为 ENV_BLOCKED。
- READY 只是启动观测，不能替代查询确认。按升序测试，恢复使用同一套状态转换，目标为 B1 实际核实的基线速率；模块恢复确认后才能恢复生产镜像。

模块替身只模拟 I/O 和立即生效、重启后生效、设置失败、完全无应答四种行为；测试必须调用实际决策实现，不能另写一份总能成功的流程。

正常预算以“一次实验 App 烧录、一次生产 App 恢复”为起点，不把它当已授权额度。列出设置、查询、本地切速、模块重启、MCU 复位、烧录及失败恢复的累计上限和停止条件；无法闭环的分支明确标为未就绪，不猜测模块状态。

6. 生成可通过真实 Boot 校验的最终资产

旧四档实验 raw BIN 和拟恢复的 raw BIN，其 0x400～0x45F 头区域为 FF，真实 Boot 校验返回 BOOT_FW_ERR_MAGIC。编译成功不能把它们变成可烧录资产。

按“源码/配置身份 → GCC raw App 与匹配 ELF/map → etu_pack finalize → 真实 Boot 校验 → 最终清单”准备一份四档可切换实验镜像和恢复候选。

finalize 必须显式 --out，使用有来源的版本、build timestamp、hw_rev、layout_id、min_boot 元数据，保留 raw 文件和失败对照。若实际准备使用 HEX，必须验证 HEX 代表的也是同一 finalized 镜像，不能验 BIN 却引用旧 raw HEX。

每个资产记录完整 SHA-256、长度、源码/配置/工具链和匹配 ELF/map。恢复候选与真实设备基线的匹配留给获授权 B1，不默认设备当前是 v2.7。

恢复生产默认构型后，在相同工具链、构建参数和 SOURCE_DATE_EPOCH 下重建 App/Boot，和原生产 raw 基线逐字节比较。若不一致，保留差异及原因，不覆盖基线或虚报一致。报告本次错误/警告数量及新增警告，不扩为无关警告清理。

7. 正确使用已完成的 1 MiB 研究

不再研究“所有合法 ETU 是否不可达”，不修改 referencePackageBytes=1048576。

已验证见证：
D:\github\my\E-Track\.cache\p3-4-size-check-20260920\cases\reference-1MiB.etu
长度：1048576
SHA-256：131624717d5972039ee76847d4a410fc21edebf9a5b4730d37b9dfe2ab04573e

固定 count=212295、seed=1931、salt=18，真实 v3.2.4 → v3.2.5，目标镜像 603764 字节未改变。真实 C/Boot 检查、生成器自测及新 nonce 复现均通过；方法和完整证据见只读报告。

它是非最短压力编码，不是默认 bsdiff 产物；有 5698868 字节解码流和 212679 次 candidate 写回调。该代价不得隐藏，也不能将回调次数说成实测物理 Flash 写入次数。

本批将它登记为“尺寸可达性见证”，不能自动升格为正式实验参考资产。先形成参考资产准入方案，说明应用代价、计时边界和基版匹配。B1 若发现设备不是该精确 v3.2.4 构建，不能直接使用，更不能为迁就研究包擅自降级。换基版/目标需重新验证，固定参数不是通用值。

8. 自测、证据复用与事实纠正

按“TX 隔离 → 字节观测 → 命令/epoch → MCU 本地切速 → 切换恢复逻辑 → host 回归 → GCC/finalize → 文档”完成一个整改批次。

host 测试必须调用真实实现，或绑定源码哈希的原文提取；只替代硬件 I/O、时间等边界。不用独立重写的决策模型冒充实际控制逻辑。覆盖所有上述正反例，保留旧失败记录和新结果。

直接复用已核查的候选包离线校验、CI run 35385421548、Linux 378 passed/8 skipped、Windows 386 passed/0 skipped，以及完整 APK 归档下载/CRC/哈希证据。本批不重跑无关 Flutter CI，不重复下载 APK。

同时修正文档：
历史 115200 raw BIN 完整 SHA-256 为 85270b58881265dbeab9dbdfe008cbd92a521b1b402bf0ae2438240ec710ff46；新资产另列身份。
旧实验构建是 0 errors、459 warnings，警告消息集合与生产 reverify 一致。
Windows clean=false 是 generated_plugin_registrant.h 换行差异，不能写成完全 clean。
打包使用公开开发 fixture 密钥，不能写“未使用密钥材料”；不要输出密钥。
CI 上传了开发产物，不等于 release/deploy；1024 字节 HTTP 206 探测与后来完整下载证据分开记载。
不同运行 APK 摘要不同，不能据此断言普遍不可复现。

9. 最终交付与停止边界

交付一份集中清单：问题 ID、修改位置、处理结果、自测证据、剩余缺口。至少包括：

- 实际代码差异及可复跑的 host 测试入口、命令、退出码、原始日志。
- TX/观测/命令拒绝/OTA busy/epoch/本地切速/四类模块模型的测试结果。
- finalized 实验与恢复候选清单、真实 Boot 校验、匹配 ELF/map 和生产构型比较。
- 修订后的 delivery、baud-experiment 及受影响准入文档。
- 包含正常、异常和最终恢复分支的操作单与累计额度申请，列清尚待授权的具体动作。
- 输入身份、写入审计、原证据保持情况，以及未执行项。

P3-4 保持“进行中”和原实现认领；真机准入、B1-B5、S1-S7、R1-R6、吞吐/可靠性 campaign、独立验收保持 NOT_RUN。实验方案写好了不等于已授权，不自验收置完成。

遇到范围外修改、冻结契约冲突、输出越界、同项连续三次失败或无安全恢复路径，停止受影响动作、保存证据并列出具体待裁定问题；其他独立且安全的 host 工作继续，不拉起无关全量回归。

最终按“已修复并自测通过／仍有缺口／等待主会话复核及具体真机授权”报告。先完成本轮可执行工作，再请求明确裁定，不只给计划，也不要再次泛泛询问是否可以开始。

