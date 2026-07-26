# OTA P1/P2 开工前问题清单与推进方案

- 日期：2026-07-26
- 范围：P1/P2 开工顺序、App 重定位、AC5/GCC 配置一致性、构建生成链和验收可证性。
- 本文性质：研究与决策记录，不修改冻结契约，不代表 P1/P2 已实现或已验收。
- 状态来源：PLAN-OTA-EXEC.md；契约来源：PLAN-OTA.md 与 docs/ota-binary-contracts.md。

## 0. 当前硬门槛（最高优先级）

当前磁盘上的 PLAN-OTA-EXEC.md 已在 2026-07-26 14:45 发生收口后整改：P0-4、P0-5 因实现继续变化被打回“进行中”，P0 总进度为 4/6，P1/P2 的“P0 全部完成”硬门槛重新关闭。此前会话中“P0 已完成 6/6、P1/P2 门槛已开”的判断已经过期，不能再据此派单。

### 0.1 P0-4 历史真机证据已失效

P0-4 在原 1000 次 RTT 验收后又修改了 bcb_commit 核心 seq+1、提交期重新仲裁、EEPROM 0xFF/初始化魔数保护等逻辑。当前看板记录宿主测试 25/25、AC5 默认/stress 构建通过，但尚未对这版实现重新执行真机 1000 次 RTT 压测。

**放行条件**：使用当前源码重新构建 stress 固件，烧录后验证 RTT 控制块签名，取得新的 start→done ok=1000 fail=0 日志且无 commit/arbiter/seq 错误；随后恢复 stress=0、重建并回刷默认固件。旧日志不得复用。

### 0.2 P0-5 历史真机证据已失效

P0-5 在原 JEDEC/selftest 验收后又修改了 QSPI 初始化状态传播、最终 OTA enable gate、QSPI-MSC 自检区避让/错误返回和 C/C++ linkage。当前看板记录默认/selftest/可选 MSC 构建通过，但尚未对这版实现重新采集真机 JEDEC 与 1000 次 selftest RTT。

**放行条件**：使用当前源码重新构建并烧录 selftest 固件，取得新的白名单 JEDEC、OTA enabled、注错 timeout PASS、1000/1000 日志和运行态 disabled=0/JEDEC 实值；随后恢复 selftest=0、重建并回刷默认固件。旧日志不得复用。

## 1. 结论摘要

1. P0-6 本身已完成独立验收，但 P0-4/P0-5 在收口后又有实现变化，当前 P0 总表已退回 4/6；P1/P2 尚未开始，且硬门槛当前关闭。
2. “先做 P1-2、P2-1/P2-2 并行”的方向合理，但“P1-2 改完后可直接用普通 J-Link reset/run 启动 App”的说法不成立。App 搬到 0x08010000 后，正常复位仍从 0x08000000 取向量，必须先有 boot，或使用明确的 debugger 设置 MSP/VTOR/PC 进行受限测试。
3. P1-1 不需要等 P1-2 才能开始写 parser、校验器和 PC/golden-vector 测试；但是 boot→App 的集成验收依赖 P1-2、P1-4、P1-5。
4. 对同一个 App 目标，AC5 与 GCC 的内存语义必须相同：Flash origin/length、向量表位置、VTOR、fw_header 偏移、RAM/overlay 边界和启动交接契约必须一致。编译器选项语法、链接脚本语法和最终代码大小可以不同。当前 AC5 旧布局不能作为重定位 GCC App 的真机等价证据。
5. P1-2 卡的现有文字“AC5 仅本地对照”不足以支撑后续硬件取证，应在实现前把“AC5 App 对照目标也必须使用同一重定位布局”写入执行卡；OTA 发布产物仍可按契约只取 GCC。
6. P0-4/P0-5 重新验收通过后，P1 与 P2 都只受 P0 门槛约束，彼此不阻塞；P3 明确卡在 P2-1/P2-2，因此门槛重开后应尽早并行启动 P2-1/P2-2。

## 2. 已确认的当前状态

| 项目 | 事实证据 | 影响 |
|---|---|---|
| GCC Flash 布局 | MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld 的 FLASH 仍为 ORIGIN=0x08000000, LENGTH=0x100000 | 当前 GCC 产物仍是旧的单体布局 |
| GCC 向量/头段 | 当前脚本只有 .isr_vector > FLASH，没有 .fw_header、KEEP 或向量大小 ASSERT | fw_header 尚未由链接器落位，P1-2 验收条件尚未满足 |
| AC5 Flash 布局 | MDK-ARM_F435/Objects/X-Track.sct 的 LR_IROM1/ER_IROM1 均从 0x08000000 开始 | AC5 与目标 App 重定位不一致 |
| AC5 工程入口 | MDK-ARM_F435/proj.uvprojx 只有 X-Track 目标，Linker 指向 .\Objects\X-Track.sct | 没有 boot/App/legacy 的目标隔离 |
| AC5 scatter 可追溯性 | 当前 Objects/X-Track.sct 未被 Git 跟踪；文件自身说明可能被 uVision 重新生成 | 直接改生成物不可复现，重建可能丢失布局 |
| VTOR 配置 | system_at32f435_437.c 的 VECT_TAB_OFFSET 仍为 0x0，SystemInit() 会写 FLASH_BASE + VECT_TAB_OFFSET | App 即使链接到新地址，也会被启动代码改回错误 VTOR |
| GCC 启动文件 | cmake/startup_at32f435_437_gcc.S 的 .isr_vector 从镜像链接 Flash 起点开始 | 重定位后向量应位于 App image offset 0，而不是 boot 起点；需由 App linker/boot 共同定义 |
| GCC 生成链 | MDK-ARM_F435/cmake-generated/CMakeLists.txt 和 conversion-report.json 将 linker 标记为 generated；仓库内没有受版本控制的转换脚本副本 | 手改 generated .ld 会被下次转换覆盖，且目前有根目录与 cmake-generated 两份旧 linker |
| AC5 增量构建 | MDK-ARM_F435/build_f435.ps1 固定使用 proj_X-Track.dep、X-Track.lnp 和 X-Track 输出 | 新 target 若继续复用这些文件，可能误编/误链旧布局 |
| P0 状态 | 当前总表为进行中 / 4/6；P0-4/P0-5 因收口后实现变化待重新真机验收，P0-6 仍为完成 | P1/P2 硬门槛当前关闭，不能正式认领或改实现 |

## 3. 统一地址与布局口径

以下地址是实现和验收唯一应使用的数值。消息或旧草稿中出现的 0x0801000、0x1000 是少一个零的写法，不能作为配置值。

| 区域 | 地址/长度 | 说明 |
|---|---:|---|
| Boot | ORIGIN=0x08000000, LENGTH=0x10000（64 KiB） | Boot 自身向量表在 offset 0，VTOR=0x08000000 |
| App | ORIGIN=0x08010000, LENGTH=0xF0000（960 KiB） | App raw bin 的 offset 0 对应绝对地址 0x08010000 |
| App VTOR | 0x08010000 | VECT_TAB_OFFSET=0x10000，且由 boot 交接和 App SystemInit 保持一致 |
| App fw_header | image offset 0x400，绝对地址 0x08010400 | 前 0x400 字节保留给向量表；契约固定 FW_HEADER_OFFSET=0x400、大小 96 B |
| 向量表上限 | SIZEOF(.isr_vector) <= 0x400 | linker 必须硬断言，防止覆盖 fw_header |

0x08010000 是 App 的加载/执行起点；0x08010400 不是独立槽起点，而是 App 镜像内 0x400 偏移处的头部地址。

## 4. 必须解决的问题

### 4.1 App 仍是旧布局（高，已证实）

GCC 与 AC5 当前都从 0x08000000 链接整个 1 MiB Flash，向量表也位于该地址。这样生成的 Track.bin 不能作为 boot 之后加载到 0x08010000 的 App，也不能通过 fw_header 的绝对地址契约验收。

**解决条件**：为 App 目标建立 0x08010000/0xF0000 的双工具链链接布局，并保留 boot 的 0x08000000/0x10000 布局；legacy 旧布局只能作为过渡目标，不能参与 OTA 验收。

### 4.2 .fw_header 没有链接器落位（高，已证实）

P0 打包器已经按镜像内 0x400 读写 96 B 头，但当前 GCC/AC5 链接脚本没有 .fw_header 段。若没有 96 B 占位对象和 KEEP，链接器不会为最终 bin 保留稳定位置，finalize 可能覆盖代码或产生空洞不一致。

**解决条件**：

- 增加 AC5/GCC 都能编译的固定大小 96 B 占位对象；
- 将其放入专用 .fw_header 段并 KEEP；
- 将该段固定到 APP_ORIGIN + 0x400；
- 保留 ASSERT(SIZEOF(.isr_vector) <= 0x400)；
- 验证 raw bin 的 0x400:0x460 与 finalizer、boot parser、golden vectors 四方一致。

### 4.3 AC5 与 GCC 的 App 语义分叉（高，已证实为流程风险）

当前 P1-2 卡只要求 GCC map，而日常真机仍主要使用 AC5。若 GCC 已重定位、AC5 仍从 0x08000000 链接，则两者不是同一个 App target：AC5 烧录得到的向量、VTOR、头部和 boot 交接行为都不同。此时“AC5 编过/真机运行”不能证明 GCC OTA 产物正确。

**正确边界**：

- 必须相同：内存区域、地址、长度、向量偏移、fw_header 偏移/大小、RAM/.sram_ext overlay 约束、启动自检和 boot 交接契约。
- 可以不同：ARMCC/GCC 的编译参数表达、scatter/LD 语法、代码尺寸、map 排版和调试信息。
- OTA 发布仍可只取 GCC；AC5 应作为同布局的本地对照和硬件调试目标，而不是另一个布局的“近似固件”。

### 4.4 生成物没有受控源（高，已证实）

MDK-ARM_F435/cmake-generated 明确由 keil_uvprojx2cmake.py 生成，conversion-report.json 说明 linker 是从 uvprojx 的内存区域生成的。当前仓库没有可直接修改、纳管和复现该转换的脚本入口；根目录 cmake/generated_linker.ld 与目标目录 linker 也都保持旧布局。

**禁止做法**：直接编辑 MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld 并把它当永久修复。下一次转换会覆盖它。

**解决条件（二选一，需在实现前定案）**：

1. 把转换脚本/模板纳管，并让它按 target 生成 relocated App linker；或
2. 新增受版本控制的稳定 linker 源文件（例如 cmake/linker/X-Track-App.ld），让 CMake target 显式引用它；generated 目录只作为构建输出，不作为人工编辑入口。

AC5 同样需要受版本控制的 scatter 源文件，不能依赖 Objects/X-Track.sct 这一临时生成位置。

### 4.5 Boot、App、legacy 目标未隔离（高，已证实）

当前 Keil 工程只有 X-Track 目标，build_f435.ps1 也固定读取同一组 dep/lnp。若把 relocated App 直接覆盖到现有 target，旧的 X-Track.axf/hex/bin、调试下载地址和 map 很容易被混用。

**建议目标矩阵**：

| 目标 | 工具链 | Flash 布局 | 用途 |
|---|---|---|---|
| X-Track-Boot | GCC（P1-1 规范要求） | 0x08000000/0x10000，VTOR 0 | boot 骨架、校验、搬运、恢复 |
| X-Track-App-GCC | GCC | 0x08010000/0xF0000，VTOR 0x10000 | OTA/CI 正式产物 |
| X-Track-App-AC5 | AC5 | 与 App-GCC 完全相同 | 本地对照、J-Link 硬件证据 |
| X-Track-Legacy | AC5（临时） | 旧 0x08000000 | 迁移过渡；不得用于 OTA 验收 |

目标名、输出目录、dep/lnp、map 和下载脚本必须能从文件名上区分，不能继续共享含糊的 X-Track.*。

### 4.6 VECT_TAB_OFFSET 不能全局硬改（高，已证实）

system_at32f435_437.c 目前把 VECT_TAB_OFFSET 写死为 0x0。直接改成 0x10000 会让 boot 或 legacy target 使用错误 VTOR；不改则 App 运行时会被 SystemInit() 重置回 0x08000000。

**解决条件**：让 offset 按 target 选择（编译宏、独立 system source 或 target-specific define 均可），并明确：Boot/legacy=0，App=0x10000。GCC startup、AC5 startup、boot 跳转代码和自检应使用同一共享常量，而不是各自复制数字。

### 4.7 不能把“App 单独 J-Link reset/run”当作重定位验收（高，已证实）

普通 Cortex-M4 复位后先从 0x08000000 读取 MSP/Reset_Handler。只把 App 写到 0x08010000 后执行 r/g，并不会自动跳到 App；0x08000000 可能是空白、旧固件或未验证 boot。显式 debugger 设置 MSP/PC/VTOR 可以做局部调试，但不等于正常启动链。

**验收分层**：

- P1-2 静态/局部测试：可用 map、bin、debugger 寄存器设置验证布局和 SystemInit 自检；
- P1-4/P1-5 集成测试：烧 boot@0x08000000 + App@0x08010000，由 boot 交接后验证 App 正常运行；
- 普通 J-Link reset/run 只有在 boot 已烧入且 boot→App 已通过后才有意义。

### 4.8 Boot→App 交接是硬件闭环前置条件（高，尚未实现）

App 重定位不只改变链接地址，还要求 boot 在跳转前完成字级清理：清 ICER/ICPR 和 PENDSTCLR/PENDSVCLR，停 SysTick，恢复 PRIMASK/BASEPRI/FAULTMASK/CONTROL，设置 VTOR 后执行 DSB/ISB，加载 App MSP 并跳转向量 [1]。这些属于 P1-4，不应被 P1-2 的 map 通过掩盖。

**退出条件**：人为挂起 SysTick/外设 pending 后，boot 仍能稳定交接；App 首次中断来自 App 向量表而非 boot 向量表。

### 4.9 P1-2 当前验收标准过窄（中高，流程缺口）

现卡只写 GCC map、.fw_header 地址、向量断言和 VTOR 自检，没有要求：

- AC5 同布局 map；
- raw bin 0x400 偏移验证；
- finalizer 后 ETFW/双零 SHA/CRC 与 map 的关联；
- boot 目标与 App 目标不混链；
- 运行时 VTOR 是在 boot 交接后取得，而非普通 reset 的假绿。

**解决条件**：在不改冻结契约的前提下，修订执行卡验收项和证据清单；若发现契约本身矛盾，按看板规则置卡 阻塞 并登记 §9，不得就地改契约继续实现。

### 4.10 CI 可能继续使用旧 linker（中高，流程风险）

OTA 产物按契约只取 GCC，但当前 CMake target 显式引用 MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld，该文件仍是旧 0x08000000 布局；根目录还有另一份同名旧 linker。若只修改了 AC5 或只修改了某一份 generated 文件，CI 可能构建出地址正确但头部/向量错误的产物。

**解决条件**：CI target 只引用一个受控 App linker 源；构建后强制检查 FLASH ORIGIN、.fw_header、向量断言、raw bin 偏移和最终 header 校验，失败即停止发布。

### 4.11 P0-6 overlay 契约尚未落到 P1/P2 linker/代码（中高，设计已冻结、实现未做）

P0-6 已裁决升级期间 OTA 独占 [0x20058000,0x20080000)，池上限 40 KiB，LiveMap .sram_ext 与 OTA overlay 互斥；这不是“多留一块可随便 malloc 的 RAM”。P1/P2 实现必须在 AC5/GCC 两套 linker 和运行时都保留相同边界、进入/退出/失败清理规则，不能只在 GCC 做。

**退出条件**：P2-6 用 StackInfo、堆水位和 overlay 水位真机复核；超 40 KiB 才能按变更登记降到 8 KiB 字典并同步制包端。

### 4.12 Boot 资源和尺寸尚无证据（中，尚未开始）

P1-1 要求 boot 不超过 64 KiB，且不得包含 LZMA、bspatch、BLE、AES。当前没有 boot 工程、map 或尺寸证据，不能把 P1-1 视为“只差一个 parser”。

**退出条件**：独立 boot target 产出 boot.bin，大小、校验项、golden vectors 拒绝样本和 fail-closed 路径均有证据。

### 4.13 物理断电验收需要排期（中，已确认）

P1-6 的擦/写指令飞行中真断电不能由 J-Link reset 完全替代。J-Link 可自动化的点与标注“物理”的点必须分开记录；真断电需用户在场并记录状态轨迹、最终版本哈希和“可启动/进恢复”二判。


## 5. 对实施顺序的判定

按当前看板规则，P1/P2 现在都不能正式认领或修改实现；可以继续做问题分析和验收设计，但必须先让 P0-4/P0-5 的当前实现重新取得独立真机证据。

| 工作 | 当前是否可正式开工 | 门槛重开后的依赖/限制 |
|---|---|---|
| P0-4 重新验收 | 应立即执行 | 当前实现重新跑 1000 次 BCB RTT，恢复默认固件 |
| P0-5 重新验收 | 应立即执行 | 当前实现重新跑 JEDEC/注错/1000 次 selftest RTT，恢复默认固件 |
| P1-1 parser、fw_header 校验器、golden-vector 负例 | 当前不可认领 | P0 重回 6/6 后可用合成镜像并行开发；boot→App 集成仍依赖 P1-2/P1-4/P1-5 |
| P1-2 链接/启动重定位 | 当前不可认领 | P0 重回 6/6 后优先启动；先定受控 linker/scatter 源和 target 矩阵 |
| P2-1 staging 写入 | 当前不可认领 | P0 重回 6/6 后可做 PC/flash 仿真；硬件闭环需 relocated App |
| P2-2 .etu 解析/AES/LZMA | 当前不可认领 | P0 重回 6/6 后可做 PC/golden vectors；真机需遵守 overlay 边界 |
| P2-3 bspatch | 当前不可认领 | 真机需 relocated App、QSPI 流式 reader 和 overlay |
| P1-4/P1-5 boot 交接/bootstrap | 后置 | 没有双布局和 header 落位时不能做完整启动验收 |
| P1-6 断电矩阵 | 先排期、后执行 | 需要用户配合真断电 |

推荐顺序：

1. 重新独立验收当前 P0-4；通过后在证据栏追加新验收行并置完成。
2. 重新独立验收当前 P0-5；通过后在证据栏追加新验收行并置完成。
3. 确认 P0 总表恢复完成 6/6，P1/P2 硬门槛重新打开。
4. 在 P1-2 执行卡中冻结双工具链 App 布局、target 名称和验收口径；不改冻结二进制契约。
5. 纳管 linker/scatter 生成源，建立 X-Track-Boot、X-Track-App-GCC、X-Track-App-AC5，暂留并标记 X-Track-Legacy。
6. 同时实现 GCC/AC5 App 的 0x08010000、VTOR=0x10000、.fw_header@+0x400、向量断言和启动自检。
7. P1-1 parser 与 P2-1/P2-2 的 PC/golden-vector 工作并行推进。
8. 建立 boot→App 交接和 J-Link bootstrap，之后才做 relocated App 的普通复位/真机证据。
9. 预留 P1-6/P5 的物理断电窗口，最后做完整 SD/BLE 闭环。
## 6. 建议的双工具链验收矩阵

| 验收项 | GCC App | AC5 App | 当前状态 |
|---|---|---|---|
| Flash origin/length | 0x08010000/0xF0000 | 相同语义 | 未实现 |
| .isr_vector 起点 | 0x08010000 | 0x08010000 | 当前均为旧地址 |
| 向量大小断言 | <=0x400 | 等价 scatter 限制/检查 | 未实现 |
| .fw_header | 0x08010400，96 B，KEEP | 相同绝对地址 | 当前不存在 |
| raw bin | header 位于文件 offset 0x400 | 同样验证 | 未执行 |
| finalizer | ETFW、双零 SHA、header CRC 一致 | 使用同一镜像语义 | 未执行 |
| VTOR | boot 交接后为 0x08010000 | 同样 | 当前 SystemInit 写 0x08000000 |
| RAM/overlay | 与 P0-6 §10 同边界 | 相同语义 | 设计已定，实现未做 |
| 产物隔离 | 独立 App/boot 输出 | 独立 App/legacy 输出 | 未实现 |
| 真实启动 | boot@0x08000000 跳 App | 同一硬件流程 | 未执行 |

P1-2 置完成前应至少通过 GCC/AC5 静态布局、raw bin 和 VTOR 自检项；boot 交接证据属于 P1-4/P1-5 的集成门槛，不应伪装成 P1-2 的普通 reset 证据。整条启动链通过后，OTA 发布仍可只上传 GCC 最终 bin/etu。

## 7. 已关闭的问题（防止回归）

以下问题在此前复审/P0 验收中已经处理，不应在 P1 实现时重新引入：

| 已关闭项 | 当前唯一口径 |
|---|---|
| fw_header 位于 app+0x200 还是 app+0x400 | 统一为 image offset 0x400，绝对地址随 App origin 计算；共享常量 FW_HEADER_OFFSET=0x400 |
| fw_header SHA/CRC 循环依赖 | 按契约双零法计算；boot、pack、unpack、vectors 必须复用同一顺序 |
| P0 golden vectors 字段/端序/CRC | P0-1/P0-2/P0-3 已独立验收通过，勿回退到旧字段名或整文件 SHA 语义 |
| NOR staging 日志与 credit 矛盾 | R8 已收敛为整 4 KiB 块位图、128 B×32 段；不恢复 120 B/35 段或短尾乒乓 journal |
| 64 KiB LZMA 字典不可行 | P0-6 选 16 KiB + OTA 独占 overlay；P2-6 只做实测，超预算走变更登记 |
| recovery 两层校验和版本例外 | 传输尾部 len/CRC 与启动前 fw_header 全项校验分层；物理 recovery 的 vcode 例外按契约执行 |

## 8. 开工前的禁止事项与放行条件

禁止：

- 直接编辑 cmake-generated 下的 .ld 并把它当永久源文件；
- 让 GCC 使用 relocated App、AC5 继续使用旧布局，却把两者当同一 OTA App；
- 只用 App@0x08010000 + 普通 J-Link reset/run 宣称启动验收通过；
- 复用 X-Track 旧 dep/lnp/输出文件验证新 target；
- 为了绕过实现困难就地修改冻结契约；发现矛盾应按看板规则阻塞并登记。

放行 P1-2 实现前必须具备：

- P0-4/P0-5 当前实现已经重新独立真机验收，P0 总表恢复完成 6/6；
- 双工具链 target/布局决策和受控 linker/scatter 源；
- FW_HEADER_OFFSET=0x400、App origin、VTOR 的共享常量来源；
- 明确 boot、App、legacy 的输出和烧录脚本边界；
- P1-2 扩展后的 GCC+AC5 map/raw-bin/VTOR 验收清单。

## 9. 参考文件

- PLAN-OTA-EXEC.md：P0 状态、P1/P2 任务卡、验收和阻塞规则。
- PLAN-OTA.md §7、§9：首次部署地址、GCC 发布口径、RAM/overlay 契约。
- docs/ota-binary-contracts.md §0.4、§1、§10：fw_header 偏移、双零校验和升级内存契约。
- MDK-ARM_F435/cmake-generated/cmake/generated_linker.ld：当前 GCC 生成 linker。
- cmake/generated_linker.ld：另一份当前旧 linker，需避免与 CI target 漂移。
- MDK-ARM_F435/Objects/X-Track.sct：当前 AC5 scatter（生成/未跟踪）。
- MDK-ARM_F435/proj.uvprojx：当前单一 Keil target 与 scatter 引用。
- MDK-ARM_F435/build_f435.ps1：当前固定 X-Track dep/lnp 的增量构建脚本。
- MDK-ARM_F435/RTE/Device/-AT32F435RGT7/system_at32f435_437.c：当前 VECT_TAB_OFFSET=0。
- cmake/startup_at32f435_437_gcc.S：当前 GCC 向量表段定义。
